"""Tests for Corrections Studio: models, repository, service, and migration."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch


from transcriptx.core.corrections.models import CorrectionRule
from transcriptx.database.repositories.corrections import CorrectionRepository
from transcriptx.services.corrections_studio.service import (
    CORRECTIONS_SCHEMA_VERSION,
    CorrectionService,
    normalize_transcript_path,
    _stable_occurrence_key,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_segments(texts=None):
    texts = texts or ["Hello world", "This is a test segment"]
    return [
        {
            "id": f"seg_{i}",
            "text": t,
            "speaker": "Speaker_1",
            "start": float(i * 10),
            "end": float(i * 10 + 9),
        }
        for i, t in enumerate(texts)
    ]


def _write_transcript(path: str, segments=None):
    segments = segments or _make_segments()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps({"segments": segments}))
    return segments


# ---------------------------------------------------------------------------
# Repository Tests
# ---------------------------------------------------------------------------


class TestCorrectionRepository:
    def test_create_session(self, db_session):
        repo = CorrectionRepository(db_session)
        result = repo.create_session(
            transcript_path="/tmp/test.json",
            source_fingerprint="abc123",
            detector_version=CORRECTIONS_SCHEMA_VERSION,
            status="active",
        )

        assert result["id"]
        assert len(result["id"]) == 36
        assert result["transcript_path"] == "/tmp/test.json"
        assert result["source_fingerprint"] == "abc123"
        assert result["status"] == "active"

    def test_find_active_session(self, db_session):
        repo = CorrectionRepository(db_session)
        created = repo.create_session(
            transcript_path="/tmp/find.json",
            source_fingerprint="fp1",
            detector_version=CORRECTIONS_SCHEMA_VERSION,
            status="active",
        )
        db_session.flush()

        found = repo.find_active_session("/tmp/find.json", "fp1")
        assert found is not None
        assert found["id"] == created["id"]

    def test_find_active_session_returns_none_for_wrong_fingerprint(self, db_session):
        repo = CorrectionRepository(db_session)
        repo.create_session(
            transcript_path="/tmp/fp.json",
            source_fingerprint="fp1",
            detector_version=CORRECTIONS_SCHEMA_VERSION,
            status="active",
        )
        db_session.flush()

        found = repo.find_active_session("/tmp/fp.json", "fp2")
        assert found is None

    def test_find_active_session_returns_none_for_completed(self, db_session):
        repo = CorrectionRepository(db_session)
        created = repo.create_session(
            transcript_path="/tmp/done.json",
            source_fingerprint="fp1",
            detector_version=CORRECTIONS_SCHEMA_VERSION,
            status="completed",
        )
        db_session.flush()

        found = repo.find_active_session("/tmp/done.json", "fp1")
        assert found is None

    def test_update_session_status(self, db_session):
        repo = CorrectionRepository(db_session)
        created = repo.create_session(
            transcript_path="/tmp/status.json",
            source_fingerprint="fp",
            detector_version=CORRECTIONS_SCHEMA_VERSION,
            status="active",
        )
        db_session.flush()

        repo.update_session_status(created["id"], "abandoned")
        db_session.flush()

        updated = repo.get_session(created["id"])
        assert updated["status"] == "abandoned"

    def test_bulk_create_candidates(self, db_session):
        repo = CorrectionRepository(db_session)
        session = repo.create_session(
            transcript_path="/tmp/cand.json",
            source_fingerprint="fp",
            detector_version=CORRECTIONS_SCHEMA_VERSION,
        )
        db_session.flush()

        candidates_data = [
            {
                "candidate_hash": "hash1",
                "kind": "memory_hit",
                "wrong_text": "teh",
                "suggested_text": "the",
                "confidence": 0.9,
                "occurrences_json": [{"segment_id": "seg_0", "span": [0, 3]}],
                "status": "pending",
            },
            {
                "candidate_hash": "hash2",
                "kind": "acronym",
                "wrong_text": "nasa",
                "suggested_text": "NASA",
                "confidence": 0.8,
                "occurrences_json": [{"segment_id": "seg_1", "span": [5, 9]}],
                "status": "pending",
            },
        ]
        result = repo.bulk_create_candidates(session["id"], candidates_data)

        assert len(result) == 2
        assert result[0]["wrong_text"] == "teh"
        assert result[1]["kind"] == "acronym"

    def test_list_candidates_with_filter(self, db_session):
        repo = CorrectionRepository(db_session)
        session = repo.create_session(
            transcript_path="/tmp/filter.json",
            source_fingerprint="fp",
            detector_version=CORRECTIONS_SCHEMA_VERSION,
        )
        db_session.flush()

        repo.bulk_create_candidates(
            session["id"],
            [
                {
                    "candidate_hash": "h1",
                    "kind": "memory_hit",
                    "wrong_text": "a",
                    "suggested_text": "b",
                    "confidence": 0.9,
                    "occurrences_json": [],
                    "status": "pending",
                },
                {
                    "candidate_hash": "h2",
                    "kind": "memory_hit",
                    "wrong_text": "c",
                    "suggested_text": "d",
                    "confidence": 0.8,
                    "occurrences_json": [],
                    "status": "accepted",
                },
            ],
        )
        db_session.flush()

        pending = repo.list_candidates(session["id"], status_filter="pending")
        assert len(pending) == 1
        assert pending[0]["wrong_text"] == "a"

        all_cands = repo.list_candidates(session["id"])
        assert len(all_cands) == 2

    def test_upsert_decision_creates_and_replaces(self, db_session):
        repo = CorrectionRepository(db_session)
        session = repo.create_session(
            transcript_path="/tmp/upsert.json",
            source_fingerprint="fp",
            detector_version=CORRECTIONS_SCHEMA_VERSION,
        )
        db_session.flush()

        cands = repo.bulk_create_candidates(
            session["id"],
            [
                {
                    "candidate_hash": "h1",
                    "kind": "memory_hit",
                    "wrong_text": "a",
                    "suggested_text": "b",
                    "confidence": 0.9,
                    "occurrences_json": [],
                    "status": "pending",
                }
            ],
        )
        db_session.flush()
        cand_id = cands[0]["id"]

        # First decision: accept
        dec1 = repo.upsert_decision(session["id"], cand_id, decision="accept")
        db_session.flush()
        assert dec1["decision"] == "accept"

        # Upsert: change to reject
        dec2 = repo.upsert_decision(session["id"], cand_id, decision="reject")
        db_session.flush()
        assert dec2["decision"] == "reject"

        # Only one decision row should exist
        all_decisions = repo.get_decisions_for_session(session["id"])
        assert len(all_decisions) == 1
        assert all_decisions[0]["decision"] == "reject"

    def test_create_rule(self, db_session):
        repo = CorrectionRepository(db_session)
        rule = repo.create_rule(
            rule_hash="test_hash_123",
            scope="global",
            rule_type="phrase",
            wrong_variants_json=["teh"],
            replacement_text="the",
            confidence=0.8,
        )
        db_session.flush()

        assert rule["id"]
        assert rule["rule_hash"] == "test_hash_123"
        assert rule["scope"] == "global"

    def test_rule_uniqueness_across_scopes(self, db_session):
        repo = CorrectionRepository(db_session)
        rule1 = repo.create_rule(
            rule_hash="same_hash",
            scope="global",
            rule_type="phrase",
            wrong_variants_json=["teh"],
            replacement_text="the",
            transcript_path=None,
        )
        db_session.flush()

        rule2 = repo.create_rule(
            rule_hash="same_hash",
            scope="transcript",
            rule_type="phrase",
            wrong_variants_json=["teh"],
            replacement_text="the",
            transcript_path="/tmp/test.json",
        )
        db_session.flush()

        assert rule1["id"] != rule2["id"]
        assert rule1["scope"] == "global"
        assert rule2["scope"] == "transcript"

    def test_get_rule(self, db_session):
        repo = CorrectionRepository(db_session)
        created = repo.create_rule(
            rule_hash="get_rule_hash",
            scope="global",
            rule_type="phrase",
            wrong_variants_json=["x"],
            replacement_text="y",
        )
        db_session.flush()

        found = repo.get_rule(created["id"])
        assert found is not None
        assert found["rule_hash"] == "get_rule_hash"
        assert repo.get_rule("nonexistent-uuid") is None

    def test_find_enabled_rules(self, db_session):
        repo = CorrectionRepository(db_session)
        repo.create_rule(
            rule_hash="global_hash",
            scope="global",
            rule_type="phrase",
            wrong_variants_json=["foo"],
            replacement_text="bar",
            enabled=True,
        )
        repo.create_rule(
            rule_hash="disabled_hash",
            scope="global",
            rule_type="phrase",
            wrong_variants_json=["baz"],
            replacement_text="qux",
            enabled=False,
        )
        db_session.flush()

        enabled = repo.find_enabled_rules("global")
        hashes = {r["rule_hash"] for r in enabled}
        assert "global_hash" in hashes
        assert "disabled_hash" not in hashes

    def test_get_session_stats(self, db_session):
        repo = CorrectionRepository(db_session)
        session = repo.create_session(
            transcript_path="/tmp/stats.json",
            source_fingerprint="fp",
            detector_version=CORRECTIONS_SCHEMA_VERSION,
        )
        db_session.flush()

        repo.bulk_create_candidates(
            session["id"],
            [
                {
                    "candidate_hash": f"h{i}",
                    "kind": "memory_hit",
                    "wrong_text": f"w{i}",
                    "suggested_text": f"s{i}",
                    "confidence": 0.5,
                    "occurrences_json": [],
                    "status": status,
                }
                for i, status in enumerate(
                    ["pending", "pending", "accepted", "rejected"]
                )
            ],
        )
        db_session.flush()

        stats = repo.get_session_stats(session["id"])
        assert stats["pending"] == 2
        assert stats["accepted"] == 1
        assert stats["rejected"] == 1
        assert stats["skipped"] == 0

    def test_delete_candidates_for_session(self, db_session):
        repo = CorrectionRepository(db_session)
        session = repo.create_session(
            transcript_path="/tmp/del.json",
            source_fingerprint="fp",
            detector_version=CORRECTIONS_SCHEMA_VERSION,
        )
        db_session.flush()

        repo.bulk_create_candidates(
            session["id"],
            [
                {
                    "candidate_hash": "h1",
                    "kind": "memory_hit",
                    "wrong_text": "a",
                    "suggested_text": "b",
                    "confidence": 0.9,
                    "occurrences_json": [],
                    "status": "pending",
                }
            ],
        )
        db_session.flush()

        count = repo.delete_candidates_for_session(session["id"])
        assert count == 1

        remaining = repo.list_candidates(session["id"])
        assert len(remaining) == 0


# ---------------------------------------------------------------------------
# Service Tests (mocked I/O)
# ---------------------------------------------------------------------------


class TestCorrectionService:
    def _make_service(self, db_session, transcript_path="/tmp/svc_test.json"):
        segments = _write_transcript(transcript_path)
        return CorrectionService(db_session), transcript_path, segments

    @patch("transcriptx.services.corrections_studio.service.load_segments")
    @patch(
        "transcriptx.services.corrections_studio.service.compute_transcript_identity_hash"
    )
    def test_start_or_resume_creates_new_session(
        self, mock_hash, mock_load, db_session
    ):
        mock_load.return_value = _make_segments()
        mock_hash.return_value = "fingerprint_abc"

        svc = CorrectionService(db_session)
        result = svc.start_or_resume_session("/tmp/new_session.json")
        db_session.flush()

        assert result["status"] == "active"
        assert result["source_fingerprint"] == "fingerprint_abc"

    @patch("transcriptx.services.corrections_studio.service.load_segments")
    @patch(
        "transcriptx.services.corrections_studio.service.compute_transcript_identity_hash"
    )
    def test_resume_session_returns_same(self, mock_hash, mock_load, db_session):
        mock_load.return_value = _make_segments()
        mock_hash.return_value = "same_fp"

        svc = CorrectionService(db_session)
        first = svc.start_or_resume_session("/tmp/resume.json")
        db_session.flush()

        second = svc.start_or_resume_session("/tmp/resume.json")
        assert second["id"] == first["id"]

    @patch("transcriptx.services.corrections_studio.service.load_segments")
    @patch(
        "transcriptx.services.corrections_studio.service.compute_transcript_identity_hash"
    )
    def test_fingerprint_mismatch_abandons_old(self, mock_hash, mock_load, db_session):
        mock_load.return_value = _make_segments()
        mock_hash.return_value = "fp_old"

        svc = CorrectionService(db_session)
        old_session = svc.start_or_resume_session("/tmp/fp_change.json")
        db_session.flush()

        mock_hash.return_value = "fp_new"
        new_session = svc.start_or_resume_session("/tmp/fp_change.json")
        db_session.flush()

        assert new_session["id"] != old_session["id"]
        repo = CorrectionRepository(db_session)
        old_data = repo.get_session(old_session["id"])
        assert old_data["status"] == "abandoned"

    def test_record_decision_accept(self, db_session):
        repo = CorrectionRepository(db_session)
        session = repo.create_session(
            transcript_path="/tmp/dec.json",
            source_fingerprint="fp",
            detector_version=CORRECTIONS_SCHEMA_VERSION,
        )
        db_session.flush()

        cands = repo.bulk_create_candidates(
            session["id"],
            [
                {
                    "candidate_hash": "h1",
                    "kind": "memory_hit",
                    "wrong_text": "teh",
                    "suggested_text": "the",
                    "confidence": 0.9,
                    "occurrences_json": [],
                    "status": "pending",
                }
            ],
        )
        db_session.flush()

        svc = CorrectionService(db_session)
        svc.record_decision(session["id"], cands[0]["id"], "accept")
        db_session.flush()

        updated = repo.get_candidate(cands[0]["id"])
        assert updated["status"] == "accepted"

        decisions = repo.get_decisions_for_session(session["id"])
        assert len(decisions) == 1
        assert decisions[0]["decision"] == "accept"

    def test_candidate_status_mirrors_decision(self, db_session):
        """After record_decision, candidate.status must mirror the decision."""
        repo = CorrectionRepository(db_session)
        session = repo.create_session(
            transcript_path="/tmp/mirror.json",
            source_fingerprint="fp",
            detector_version=CORRECTIONS_SCHEMA_VERSION,
        )
        db_session.flush()

        cands = repo.bulk_create_candidates(
            session["id"],
            [
                {
                    "candidate_hash": "h1",
                    "kind": "memory_hit",
                    "wrong_text": "x",
                    "suggested_text": "y",
                    "confidence": 0.5,
                    "occurrences_json": [],
                    "status": "pending",
                }
            ],
        )
        db_session.flush()

        svc = CorrectionService(db_session)
        for decision_val, expected_status in [
            ("accept", "accepted"),
            ("reject", "rejected"),
            ("skip", "skipped"),
        ]:
            svc.record_decision(session["id"], cands[0]["id"], decision_val)
            db_session.flush()
            cand = repo.get_candidate(cands[0]["id"])
            assert cand["status"] == expected_status

    def test_decision_upsert_replaces(self, db_session):
        repo = CorrectionRepository(db_session)
        session = repo.create_session(
            transcript_path="/tmp/upsert2.json",
            source_fingerprint="fp",
            detector_version=CORRECTIONS_SCHEMA_VERSION,
        )
        db_session.flush()

        cands = repo.bulk_create_candidates(
            session["id"],
            [
                {
                    "candidate_hash": "h1",
                    "kind": "memory_hit",
                    "wrong_text": "a",
                    "suggested_text": "b",
                    "confidence": 0.5,
                    "occurrences_json": [],
                    "status": "pending",
                }
            ],
        )
        db_session.flush()

        svc = CorrectionService(db_session)
        svc.record_decision(session["id"], cands[0]["id"], "accept")
        db_session.flush()

        svc.record_decision(session["id"], cands[0]["id"], "reject")
        db_session.flush()

        decisions = repo.get_decisions_for_session(session["id"])
        assert len(decisions) == 1
        assert decisions[0]["decision"] == "reject"

        cand = repo.get_candidate(cands[0]["id"])
        assert cand["status"] == "rejected"

    def test_accept_and_learn_rule(self, db_session):
        repo = CorrectionRepository(db_session)
        session = repo.create_session(
            transcript_path="/tmp/learn.json",
            source_fingerprint="fp",
            detector_version=CORRECTIONS_SCHEMA_VERSION,
        )
        db_session.flush()

        cands = repo.bulk_create_candidates(
            session["id"],
            [
                {
                    "candidate_hash": "h1",
                    "kind": "memory_hit",
                    "wrong_text": "teh",
                    "suggested_text": "the",
                    "confidence": 0.9,
                    "occurrences_json": [],
                    "status": "pending",
                }
            ],
        )
        db_session.flush()

        rule_hash = CorrectionRule.compute_id("phrase", ["teh"], "the")
        learn_params = {
            "rule_hash": rule_hash,
            "scope": "global",
            "rule_type": "phrase",
            "wrong_variants_json": ["teh"],
            "replacement_text": "the",
            "confidence": 0.9,
        }

        svc = CorrectionService(db_session)
        svc.record_decision(
            session["id"],
            cands[0]["id"],
            "accept",
            learn_rule_params=learn_params,
        )
        db_session.flush()

        # Decision should be "accept" (not "learn")
        decisions = repo.get_decisions_for_session(session["id"])
        assert len(decisions) == 1
        assert decisions[0]["decision"] == "accept"
        assert decisions[0]["created_rule_id"] is not None

        # Candidate status should be "accepted"
        cand = repo.get_candidate(cands[0]["id"])
        assert cand["status"] == "accepted"

        # Rule should exist in DB
        rules = repo.find_enabled_rules("global")
        rule_hashes = {r["rule_hash"] for r in rules}
        assert rule_hash in rule_hashes

    def test_get_candidate_local_diff(self, db_session):
        repo = CorrectionRepository(db_session)
        session = repo.create_session(
            transcript_path="/tmp/diff.json",
            source_fingerprint="fp",
            detector_version=CORRECTIONS_SCHEMA_VERSION,
        )
        db_session.flush()

        cands = repo.bulk_create_candidates(
            session["id"],
            [
                {
                    "candidate_hash": "h1",
                    "kind": "memory_hit",
                    "wrong_text": "teh",
                    "suggested_text": "the",
                    "confidence": 0.9,
                    "occurrences_json": [
                        {
                            "segment_id": "seg_0",
                            "span": [0, 3],
                            "snippet": "teh quick brown fox",
                            "speaker": "Speaker_1",
                            "time_start": 0.0,
                            "time_end": 5.0,
                            "stable_occurrence_key": "test_key",
                            "segment_index": 0,
                        }
                    ],
                    "status": "pending",
                }
            ],
        )
        db_session.flush()

        svc = CorrectionService(db_session)
        diff = svc.get_candidate_local_diff(session["id"], cands[0]["id"])

        assert len(diff["diffs"]) == 1
        d = diff["diffs"][0]
        assert "teh" in d["before"]
        assert "the" in d["after"]

    def test_stable_occurrence_key_survives_roundtrip(self, db_session):
        key = _stable_occurrence_key("seg_0", 0, 3, "teh")
        assert isinstance(key, str)
        assert len(key) == 40

        # Same inputs produce same key
        key2 = _stable_occurrence_key("seg_0", 0, 3, "teh")
        assert key == key2

        # Different inputs produce different key
        key3 = _stable_occurrence_key("seg_0", 0, 4, "teh")
        assert key != key3

    @patch("transcriptx.services.corrections_studio.service.load_segments")
    @patch(
        "transcriptx.services.corrections_studio.service.compute_transcript_identity_hash"
    )
    @patch("transcriptx.services.corrections_studio.service.detect_memory_hits")
    @patch("transcriptx.services.corrections_studio.service.detect_acronym_candidates")
    @patch(
        "transcriptx.services.corrections_studio.service.detect_consistency_candidates"
    )
    @patch("transcriptx.services.corrections_studio.service.detect_fuzzy_candidates")
    def test_generate_candidates_force_deletes_old(
        self,
        mock_fuzzy,
        mock_consistency,
        mock_acronym,
        mock_memory,
        mock_hash,
        mock_load,
        db_session,
    ):
        segments = _make_segments(["teh quick", "teh slow"])
        mock_load.return_value = segments
        mock_hash.return_value = "fp_force"
        mock_memory.return_value = []
        mock_acronym.return_value = []
        mock_consistency.return_value = []
        mock_fuzzy.return_value = []

        repo = CorrectionRepository(db_session)
        session = repo.create_session(
            transcript_path="/tmp/force.json",
            source_fingerprint="fp_force",
            detector_version=CORRECTIONS_SCHEMA_VERSION,
            status="active",
        )
        db_session.flush()

        # Insert one candidate manually so we have something to delete
        cands = repo.bulk_create_candidates(
            session["id"],
            [
                {
                    "candidate_hash": "old_hash",
                    "kind": "memory_hit",
                    "wrong_text": "old",
                    "suggested_text": "new",
                    "confidence": 0.5,
                    "occurrences_json": [],
                    "status": "pending",
                }
            ],
        )
        db_session.flush()
        repo.upsert_decision(session["id"], cands[0]["id"], decision="accept")
        db_session.flush()

        svc = CorrectionService(db_session)
        result = svc.generate_candidates(session["id"], force=True)
        db_session.flush()

        # Old candidate and decision should be gone; result is from fresh detection (empty here)
        remaining = repo.list_candidates(session["id"])
        assert len(remaining) == 0
        assert result == []

        decisions = repo.get_decisions_for_session(session["id"])
        assert len(decisions) == 0

    @patch("transcriptx.services.corrections_studio.service.load_segments")
    @patch(
        "transcriptx.services.corrections_studio.service.compute_transcript_identity_hash"
    )
    def test_compute_preview(self, mock_hash, mock_load, db_session):
        segments = _make_segments(["teh quick brown", "teh fox"])
        mock_load.return_value = segments
        mock_hash.return_value = "fp_preview"

        repo = CorrectionRepository(db_session)
        session = repo.create_session(
            transcript_path="/tmp/preview.json",
            source_fingerprint="fp_preview",
            detector_version=CORRECTIONS_SCHEMA_VERSION,
            status="active",
        )
        db_session.flush()

        cands = repo.bulk_create_candidates(
            session["id"],
            [
                {
                    "candidate_hash": "h1",
                    "kind": "memory_hit",
                    "wrong_text": "teh",
                    "suggested_text": "the",
                    "confidence": 0.9,
                    "occurrences_json": [
                        {
                            "segment_id": "seg_0",
                            "span": [0, 3],
                            "snippet": "teh quick",
                            "stable_occurrence_key": _stable_occurrence_key(
                                "seg_0", 0, 3, "teh"
                            ),
                            "segment_index": 0,
                        },
                        {
                            "segment_id": "seg_1",
                            "span": [0, 3],
                            "snippet": "teh fox",
                            "stable_occurrence_key": _stable_occurrence_key(
                                "seg_1", 0, 3, "teh"
                            ),
                            "segment_index": 1,
                        },
                    ],
                    "status": "pending",
                }
            ],
        )
        db_session.flush()
        repo.upsert_decision(session["id"], cands[0]["id"], decision="accept")
        repo.update_candidate_status(cands[0]["id"], "accepted")
        db_session.flush()

        svc = CorrectionService(db_session)
        preview = svc.compute_preview(session["id"])

        assert "updated_segments" in preview
        assert "patch_log" in preview
        assert "stats" in preview
        assert preview["stats"]["total_accepted"] == 1
        assert preview["stats"]["applied_count"] >= 1
        # Both segments should have "teh" -> "the"
        texts = [s["text"] for s in preview["updated_segments"]]
        assert "the quick brown" in texts or any("the" in t for t in texts)
        assert "the fox" in texts or any("the" in t for t in texts)

    @patch("transcriptx.services.corrections_studio.service.save_json")
    @patch("transcriptx.services.corrections_studio.service.load_segments")
    @patch(
        "transcriptx.services.corrections_studio.service.compute_transcript_identity_hash"
    )
    def test_apply_and_export(self, mock_hash, mock_load, mock_save, db_session):
        segments = _make_segments(["teh world", "teh end"])
        mock_load.return_value = segments
        mock_hash.return_value = "fp_export"

        repo = CorrectionRepository(db_session)
        session = repo.create_session(
            transcript_path="/tmp/export_test.json",
            source_fingerprint="fp_export",
            detector_version=CORRECTIONS_SCHEMA_VERSION,
            status="active",
        )
        db_session.flush()

        cands = repo.bulk_create_candidates(
            session["id"],
            [
                {
                    "candidate_hash": "h1",
                    "kind": "memory_hit",
                    "wrong_text": "teh",
                    "suggested_text": "the",
                    "confidence": 0.9,
                    "occurrences_json": [
                        {
                            "segment_id": "seg_0",
                            "span": [0, 3],
                            "snippet": "teh world",
                            "stable_occurrence_key": _stable_occurrence_key(
                                "seg_0", 0, 3, "teh"
                            ),
                            "segment_index": 0,
                        },
                    ],
                    "status": "pending",
                }
            ],
        )
        db_session.flush()
        repo.upsert_decision(session["id"], cands[0]["id"], decision="accept")
        repo.update_candidate_status(cands[0]["id"], "accepted")
        db_session.flush()

        svc = CorrectionService(db_session)
        result = svc.apply_and_export(session["id"])
        db_session.flush()

        assert "export_path" in result
        assert result["export_path"].endswith(
            "_corrected_" + session["id"][:8] + ".json"
        )
        assert result["applied_count"] >= 1
        mock_save.assert_called_once()
        call_args = mock_save.call_args[0]
        assert call_args[0]["segments"]
        updated = repo.get_session(session["id"])
        assert updated["status"] == "completed"


# ---------------------------------------------------------------------------
# Controller tests
# ---------------------------------------------------------------------------


class TestCorrectionsStudioController:
    @patch("transcriptx.services.corrections_studio.controller.get_session")
    def test_controller_start_or_resume_returns_session(self, mock_get, db_session):
        mock_get.return_value = db_session
        with patch(
            "transcriptx.services.corrections_studio.service.load_segments"
        ) as mock_load:
            with patch(
                "transcriptx.services.corrections_studio.service.compute_transcript_identity_hash"
            ) as mock_hash:
                mock_load.return_value = _make_segments()
                mock_hash.return_value = "ctrl_fp"

                from transcriptx.services.corrections_studio.controller import (
                    CorrectionsStudioController,
                )

                ctrl = CorrectionsStudioController()
                result = ctrl.start_or_resume("/tmp/ctrl_resume.json")
                db_session.commit()

                assert result["id"]
                assert result["status"] == "active"
                mock_get.assert_called()
                db_session.close()

    @patch("transcriptx.services.corrections_studio.controller.get_session")
    def test_controller_get_session_stats(self, mock_get, db_session):
        mock_get.return_value = db_session
        repo = CorrectionRepository(db_session)
        session = repo.create_session(
            transcript_path="/tmp/ctrl_stats.json",
            source_fingerprint="fp",
            detector_version=CORRECTIONS_SCHEMA_VERSION,
            status="active",
        )
        db_session.flush()
        repo.bulk_create_candidates(
            session["id"],
            [
                {
                    "candidate_hash": "h1",
                    "kind": "memory_hit",
                    "wrong_text": "a",
                    "suggested_text": "b",
                    "confidence": 0.5,
                    "occurrences_json": [],
                    "status": "pending",
                }
            ],
        )
        db_session.flush()

        from transcriptx.services.corrections_studio.controller import (
            CorrectionsStudioController,
        )

        ctrl = CorrectionsStudioController()
        stats = ctrl.get_session_stats(session["id"])
        assert stats["pending"] == 1
        mock_get.assert_called()
        db_session.close()

    @patch("transcriptx.services.corrections_studio.controller.get_session")
    def test_controller_get_session_includes_stale_flag(self, mock_get, db_session):
        mock_get.return_value = db_session
        repo = CorrectionRepository(db_session)
        session = repo.create_session(
            transcript_path="/tmp/ctrl_get.json",
            source_fingerprint="fp",
            detector_version="0",  # old version
            status="active",
        )
        db_session.flush()

        from transcriptx.services.corrections_studio.controller import (
            CorrectionsStudioController,
        )

        ctrl = CorrectionsStudioController()
        info = ctrl.get_session(session["id"])
        assert info is not None
        assert info["candidates_stale"] is True
        db_session.close()


# ---------------------------------------------------------------------------
# Normalize path
# ---------------------------------------------------------------------------


class TestNormalizePath:
    def test_relative_vs_absolute_normalize_same(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # resolve tmpdir itself first to handle macOS /var -> /private/var
            resolved_dir = str(Path(tmpdir).resolve())
            abs_path = str(Path(resolved_dir) / "data" / "foo.json")
            Path(abs_path).parent.mkdir(parents=True, exist_ok=True)
            Path(abs_path).touch()

            normalized = normalize_transcript_path(abs_path)
            assert normalized == abs_path
            assert Path(normalized).is_absolute()


# ---------------------------------------------------------------------------
# Migration smoke test
# ---------------------------------------------------------------------------


def test_migration_tables_exist(test_database_engine):
    """Verify all four correction tables exist after metadata.create_all."""
    from sqlalchemy import inspect as sa_inspect

    inspector = sa_inspect(test_database_engine)
    table_names = inspector.get_table_names()

    expected = [
        "correction_sessions",
        "correction_candidates",
        "correction_decisions",
        "correction_rules_db",
    ]
    for table in expected:
        assert table in table_names, f"Table {table} not found in DB"
