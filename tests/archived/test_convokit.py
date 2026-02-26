"""
Tests for the ConvoKit analysis module.
"""

from unittest.mock import MagicMock, patch

import os

from transcriptx.core.analysis.convokit import ConvoKitAnalysis


class TestConvoKitAnalysis:
    def test_build_utterance_records_excludes_unidentified(self):
        module = ConvoKitAnalysis(config={"exclude_unidentified": True})
        segments = [
            {
                "speaker": "Alice",
                "speaker_db_id": 1,
                "text": "Hello there",
                "start": 0.0,
                "end": 1.0,
            },
            {
                "speaker": "SPEAKER_01",
                "text": "Unknown speaker text",
                "start": 1.2,
                "end": 2.0,
            },
        ]

        records, stats = module._build_utterance_records(segments, "test")
        assert len(records) == 1
        assert stats["excluded_speakers"] == ["SPEAKER_01"]

    def test_reply_links_prev_diff_speaker(self):
        module = ConvoKitAnalysis(config={"exclude_unidentified": True})
        segments = [
            {"speaker": "A", "text": "one", "start": 0.0, "end": 0.5},
            {"speaker": "B", "text": "two", "start": 1.0, "end": 1.5},
            {"speaker": "A", "text": "three", "start": 2.0, "end": 2.5},
            {"speaker": "B", "text": "four", "start": 3.0, "end": 3.5},
        ]
        records, _ = module._build_utterance_records(segments, "test")
        module._build_reply_to_links(records, "prev_diff_speaker", 2.0)

        assert records[0]["reply_to"] is None
        assert records[1]["reply_to"] == records[0]["id"]
        assert records[2]["reply_to"] == records[1]["id"]
        assert records[3]["reply_to"] == records[2]["id"]

    def test_reply_links_threshold_gap(self):
        module = ConvoKitAnalysis(config={"exclude_unidentified": True})
        segments = [
            {"speaker": "A", "text": "one", "start": 0.0, "end": 0.5},
            {"speaker": "B", "text": "two", "start": 1.0, "end": 1.2},
            {"speaker": "A", "text": "late reply", "start": 10.0, "end": 10.5},
        ]
        records, _ = module._build_utterance_records(segments, "test")
        module._build_reply_to_links(records, "threshold_gap", 2.0)

        assert records[0]["reply_to"] is None
        assert records[1]["reply_to"] == records[0]["id"]
        assert records[2]["reply_to"] is None

    def test_reply_links_monologue(self):
        module = ConvoKitAnalysis(config={"exclude_unidentified": True})
        segments = [
            {"speaker": "A", "text": "one", "start": 0.0, "end": 0.5},
            {"speaker": "A", "text": "two", "start": 1.0, "end": 1.5},
            {"speaker": "A", "text": "three", "start": 2.0, "end": 2.5},
        ]
        records, _ = module._build_utterance_records(segments, "test")
        module._build_reply_to_links(records, "prev_diff_speaker", 2.0)

        assert all(record["reply_to"] is None for record in records)

    def test_missing_dependency_graceful_skip(self):
        module = ConvoKitAnalysis(config={"exclude_unidentified": True})
        segments = [
            {"speaker": "Alice", "text": "Hello", "start": 0.0, "end": 1.0},
            {"speaker": "Bob", "text": "Hi", "start": 1.2, "end": 2.0},
        ]

        with patch(
            "transcriptx.core.analysis.convokit.optional_import",
            side_effect=ImportError("convokit is required"),
        ):
            result = module.analyze(segments, {})

        assert result["skipped"] is True
        assert result["skipped_reason"] == "convokit_not_installed"

    def test_insufficient_speakers_skip(self):
        module = ConvoKitAnalysis(config={"exclude_unidentified": True})
        segments = [
            {"speaker": "Alice", "text": "Hello", "start": 0.0, "end": 1.0},
            {"speaker": "Alice", "text": "Still me", "start": 1.5, "end": 2.0},
        ]

        with patch(
            "transcriptx.core.analysis.convokit.optional_import",
            return_value=MagicMock(),
        ):
            result = module.analyze(segments, {})

        assert result["skipped"] is True
        assert result["skipped_reason"] == "insufficient_named_speakers"

    def test_run_from_context_missing_dependency_writes_summary(self, tmp_path):
        module = ConvoKitAnalysis(config={"exclude_unidentified": True})
        transcript_path = tmp_path / "sample.json"
        transcript_path.write_text("[]")

        segments = [
            {"speaker": "Alice", "text": "Hello", "start": 0.0, "end": 1.0},
            {"speaker": "Bob", "text": "Hi", "start": 1.2, "end": 2.0},
        ]

        context = MagicMock()
        context.transcript_path = str(transcript_path)
        context.get_segments.return_value = segments
        context.get_speaker_map.return_value = {}
        context.get_base_name.return_value = "sample"
        context.get_transcript_dir.return_value = str(tmp_path)
        context.store_analysis_result = MagicMock()

        with patch(
            "transcriptx.core.analysis.convokit.optional_import",
            side_effect=ImportError("convokit is required"),
        ):
            result = module.run_from_context(context)

        assert result["status"] == "success"
        assert result["payload"]["skipped"] is True
        assert any(os.path.exists(artifact["path"]) for artifact in result["artifacts"])
