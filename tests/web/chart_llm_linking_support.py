"""Shared fixtures for gallery/export ↔ chart_descriptions linking tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from transcriptx.core.analysis.chart_descriptions.inventory_builder import (
    build_logical_chart_inventory,
)
from transcriptx.core.pipeline.manifest_builder import build_output_manifest
from transcriptx.web.models.artifact import Artifact

# Minimal valid PNG (1x1)
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def write_active_generation(
    run_root: Path,
    *,
    run_target_id: str,
    run_kind: str,
    entries: list[dict[str, Any]],
) -> None:
    """Write ACTIVE generation covering multiple chart_key → description entries."""
    root = run_root / ".chart_descriptions"
    gen_id = "gen1"
    epoch = "epoch1"
    gdir = root / "generations" / gen_id
    desc_dir = gdir / "descriptions"
    desc_dir.mkdir(parents=True)
    (root / "ACTIVE.json").write_text(
        json.dumps(
            {
                "generation_id": gen_id,
                "attempt_epoch": epoch,
                "overall_status": "success",
            }
        ),
        encoding="utf-8",
    )
    (root / "LATEST_ATTEMPT.json").write_text(
        json.dumps({"attempt_epoch": epoch}),
        encoding="utf-8",
    )
    (gdir / "inventory_snapshot.json").write_text(
        json.dumps(
            {
                "run_target_id": run_target_id,
                "run_kind": run_kind,
                "chart_count": len(entries),
            }
        ),
        encoding="utf-8",
    )
    index_entries = []
    for entry in entries:
        chart_key = entry["chart_key"]
        viz_id = entry.get("viz_id", "stats.foo.global")
        rel = f"descriptions/{chart_key}.json"
        index_entries.append(
            {
                "chart_key": chart_key,
                "status": "success",
                "description_rel": rel,
                "viz_id": viz_id,
            }
        )
        (gdir / rel).write_text(
            json.dumps(
                {
                    "schema_id": "transcriptx.chart_description.v1",
                    "chart_key": chart_key,
                    "logical_chart_id": entry.get("logical_chart_id", "x"),
                    "viz_id": viz_id,
                    "module": entry.get("module", "stats"),
                    "scope": entry.get("scope", "global"),
                    "speaker": entry.get("speaker"),
                    "status": "success",
                    "chart_set": "all",
                    "description": entry["description"],
                    "representations": [],
                    "evidence_sha256": "",
                    "evidence_rel_path": None,
                    "request_hash": "",
                    "prompt_version": "1",
                    "model": "test",
                    "reused": False,
                    "error_code": None,
                    "error_message_safe": None,
                }
            ),
            encoding="utf-8",
        )
    (gdir / "index.json").write_text(
        json.dumps({"entries": index_entries}),
        encoding="utf-8",
    )


def write_single_active(
    run_root: Path,
    *,
    run_target_id: str,
    run_kind: str,
    chart_key: str,
    description: str,
    viz_id: str = "stats.foo.global",
    **extra: Any,
) -> None:
    write_active_generation(
        run_root,
        run_target_id=run_target_id,
        run_kind=run_kind,
        entries=[
            {
                "chart_key": chart_key,
                "description": description,
                "viz_id": viz_id,
                **extra,
            }
        ],
    )


def chart_artifact(*, viz_id: str = "stats.foo.global") -> Artifact:
    return Artifact(
        id="a1",
        kind="chart_static",
        module="stats",
        scope="global",
        speaker=None,
        subview=None,
        slice_id=None,
        rel_path="stats/charts/global/static/foo.png",
        bytes=10,
        mtime="0",
        mime="image/png",
        tags=["stats"],
        title="Foo",
        meta={
            "viz_id": viz_id,
            "module": "stats",
            "scope": "global",
            "name": "foo",
        },
    )


def seed_linking_fixture_run(run: Path, *, transcript_key: str) -> dict[str, str]:
    """Build on-disk charts + meta that stress known linking mismatches.

    Returns map of inventory chart_key → expected LLM description text.
    """
    meta: dict[str, Any] = {}

    stats_png = run / "stats" / "charts" / "global" / "static" / "foo.png"
    stats_png.parent.mkdir(parents=True)
    stats_png.write_bytes(PNG_BYTES)
    meta[stats_png.relative_to(run).as_posix()] = {
        "viz_id": "stats.foo.global",
        "module": "stats",
        "scope": "global",
        "artifact_kind": "chart",
        "name": "foo",
        "format": "png",
        "render_hint": "static",
        "title": "Foo",
    }

    voice_png = (
        run
        / "voice"
        / "v1"
        / "charts"
        / "speakers"
        / "Ana"
        / "static"
        / "burstiness"
        / "burstiness__speaker__Ana.png"
    )
    voice_png.parent.mkdir(parents=True)
    voice_png.write_bytes(PNG_BYTES)
    voice_html = (
        run
        / "voice"
        / "v1"
        / "charts"
        / "speakers"
        / "Ana"
        / "dynamic"
        / "burstiness"
        / "burstiness__speaker__Ana.html"
    )
    voice_html.parent.mkdir(parents=True)
    voice_html.write_text("<html>burstiness</html>", encoding="utf-8")
    for path, fmt, hint, kind_hint in (
        (voice_png, "png", "static", "chart"),
        (voice_html, "html", "dynamic", "chart"),
    ):
        meta[path.relative_to(run).as_posix()] = {
            "viz_id": "voice.burstiness.speaker",
            "module": "voice_charts_core",
            "scope": "speaker",
            "speaker": "Ana",
            "artifact_kind": kind_hint,
            "name": "burstiness__speaker__Ana",
            "format": fmt,
            "render_hint": hint,
            "title": "Burstiness Ana",
        }

    ner_png = run / "ner" / "maps" / "images" / "session-locations-ALL.png"
    ner_png.parent.mkdir(parents=True)
    ner_png.write_bytes(PNG_BYTES)
    meta[ner_png.relative_to(run).as_posix()] = {
        "artifact_kind": "chart",
        "format": "png",
        "render_hint": "static",
        "title": "Locations",
    }

    meta_dir = run / ".transcriptx"
    meta_dir.mkdir(parents=True)
    (meta_dir / "artifacts_meta.json").write_text(json.dumps(meta), encoding="utf-8")

    inventory, skips = build_logical_chart_inventory(
        run, run_kind="transcript", run_target_id=transcript_key
    )
    assert not any(
        s.get("reason") == "missing_viz_id" and "burstiness" in str(s) for s in skips
    )
    assert len(inventory.charts) >= 2

    descriptions: dict[str, str] = {}
    entries: list[dict[str, Any]] = []
    for chart in inventory.charts:
        text = f"LLM summary for {chart.viz_id} / {chart.speaker or 'global'}"
        descriptions[chart.chart_key] = text
        entries.append(
            {
                "chart_key": chart.chart_key,
                "logical_chart_id": chart.logical_chart_id,
                "viz_id": chart.viz_id,
                "module": chart.module,
                "scope": chart.scope,
                "speaker": chart.speaker,
                "description": text,
            }
        )
    write_active_generation(
        run,
        run_target_id=transcript_key,
        run_kind="transcript",
        entries=entries,
    )

    manifest = build_output_manifest(
        run_dir=run,
        run_id=run.name,
        transcript_key=transcript_key,
        modules_enabled=["stats", "voice_charts_core", "ner"],
    )
    (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return descriptions
