"""Tests for shared LLM analysis helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.analysis.llm_common import (
    build_bounded_user_prompt,
    format_transcript_lines,
    parse_narrative_json,
    resolve_summary_payload,
    sha256_llm_request,
    sha256_text,
    strip_json_fence,
    summary_has_content,
    truncate_transcript_block,
    write_llm_artifacts,
)
from transcriptx.core.analysis.llm_module_errors import (
    LLM_DEPENDENCY_MISSING,
    ModuleDependencyMissingError,
)
from transcriptx.core.llm.errors import LLMResponseError


@pytest.mark.unit
def test_summary_has_content_false_on_empty() -> None:
    assert summary_has_content({}) is False
    assert summary_has_content({"overview": {}, "key_themes": {"bullets": []}}) is False


@pytest.mark.unit
def test_summary_has_content_true_with_overview() -> None:
    payload = {"overview": {"paragraph": "Something happened"}}
    assert summary_has_content(payload) is True


@pytest.mark.unit
def test_strip_json_fence_only() -> None:
    raw = '```json\n{"narrative": "ok"}\n```'
    assert strip_json_fence(raw) == '{"narrative": "ok"}'


@pytest.mark.unit
def test_parse_narrative_json_rejects_prose_wrapped() -> None:
    raw = 'Here is JSON:\n```json\n{"narrative": "ok"}\n```\nThanks!'
    with pytest.raises(LLMResponseError):
        parse_narrative_json(raw)


@pytest.mark.unit
def test_parse_narrative_json_accepts_fenced() -> None:
    raw = '```json\n{"narrative": "Executive update."}\n```'
    parsed = parse_narrative_json(raw)
    assert parsed["narrative"] == "Executive update."


@pytest.mark.unit
def test_truncate_head_tail_includes_early_and_late_segments() -> None:
    lines = [f"Speaker: EARLY-{i:02d} tail-marker-{i:02d}-LATE" for i in range(20)]
    text, meta = truncate_transcript_block(lines, max_chars=220)
    assert meta["truncated"] is True
    assert meta["truncation_strategy"] == "head_tail"
    assert "EARLY-00" in text
    assert "LATE" in text and ("17" in text or "18" in text or "19" in text)
    assert "[... transcript content omitted ...]" in text
    assert len(text) <= 220


@pytest.mark.unit
def test_truncate_single_segment_hard_truncate() -> None:
    lines = ["Speaker: " + ("word " * 500)]
    text, meta = truncate_transcript_block(lines, max_chars=50)
    assert meta["truncation_strategy"] == "single_segment_hard_truncate"
    assert meta["included_segments"] == 1
    assert meta["partially_included_segments"] == 1
    assert len(text) <= 50


@pytest.mark.unit
def test_write_llm_artifacts_atomic(tmp_path, monkeypatch) -> None:
    from transcriptx.core.output.output_service import OutputService
    from transcriptx.core.utils.output_structure import OutputStructure

    structure = OutputStructure(
        transcript_dir=str(tmp_path),
        module_dir=str(tmp_path / "llm_summary"),
        data_dir=str(tmp_path / "llm_summary" / "data"),
        global_data_dir=str(tmp_path / "llm_summary" / "data" / "global"),
    )
    (tmp_path / "llm_summary" / "data" / "global").mkdir(parents=True)

    svc = OutputService.__new__(OutputService)
    svc.base_name = "mini"
    svc.module_name = "llm_summary"
    svc.output_structure = structure
    svc._artifacts = []

    def _record(path, artifact_type="json"):
        svc._artifacts.append({"path": str(path), "type": artifact_type})

    svc.record_file = _record  # type: ignore[method-assign]

    payload = {"summary": "ok", "provenance": {}}
    json_path, md_path = write_llm_artifacts(
        svc,
        artifact_stem="llm_summary",
        payload=payload,
        markdown="# Summary\n\nok\n",
    )
    assert Path(json_path).exists()
    assert Path(md_path).exists()
    assert len(svc._artifacts) == 2
    loaded = json.loads(Path(json_path).read_text(encoding="utf-8"))
    assert loaded["summary"] == "ok"


@pytest.mark.unit
def test_write_llm_artifacts_cleans_up_on_markdown_failure(
    tmp_path, monkeypatch
) -> None:
    from transcriptx.core.output.output_service import OutputService
    from transcriptx.core.utils.output_structure import OutputStructure

    structure = OutputStructure(
        transcript_dir=str(tmp_path),
        module_dir=str(tmp_path / "llm_summary"),
        data_dir=str(tmp_path / "llm_summary" / "data"),
        global_data_dir=str(tmp_path / "llm_summary" / "data" / "global"),
    )
    (tmp_path / "llm_summary" / "data" / "global").mkdir(parents=True)

    svc = OutputService.__new__(OutputService)
    svc.base_name = "mini"
    svc.module_name = "llm_summary"
    svc.output_structure = structure
    svc._artifacts = []
    svc.record_file = lambda *_a, **_k: None  # type: ignore[method-assign]

    def _fail_md(path, text):
        raise OSError("disk full")

    monkeypatch.setattr(
        "transcriptx.core.analysis.llm_common.write_text",
        _fail_md,
    )

    out_dir = Path(structure.global_data_dir)
    with pytest.raises(OSError):
        write_llm_artifacts(
            svc,
            artifact_stem="llm_summary",
            payload={"summary": "ok"},
            markdown="# Summary\n",
        )

    assert not list(out_dir.glob("mini_llm_summary.json"))
    assert not list(out_dir.glob("mini_llm_summary.md"))
    assert not list(out_dir.glob("**/.staging/**"))


@pytest.mark.unit
def test_write_llm_artifacts_preserves_existing_on_markdown_failure(
    tmp_path, monkeypatch
) -> None:
    from transcriptx.core.output.output_service import OutputService
    from transcriptx.core.utils.output_structure import OutputStructure

    structure = OutputStructure(
        transcript_dir=str(tmp_path),
        module_dir=str(tmp_path / "llm_summary"),
        data_dir=str(tmp_path / "llm_summary" / "data"),
        global_data_dir=str(tmp_path / "llm_summary" / "data" / "global"),
    )
    out_dir = Path(structure.global_data_dir)
    out_dir.mkdir(parents=True)
    existing_json = out_dir / "mini_llm_summary.json"
    existing_md = out_dir / "mini_llm_summary.md"
    existing_json.write_text('{"summary": "keep"}', encoding="utf-8")
    existing_md.write_text("# keep\n", encoding="utf-8")

    svc = OutputService.__new__(OutputService)
    svc.base_name = "mini"
    svc.module_name = "llm_summary"
    svc.output_structure = structure
    svc._artifacts = []
    svc.record_file = lambda *_a, **_k: None  # type: ignore[method-assign]

    monkeypatch.setattr(
        "transcriptx.core.analysis.llm_common.write_text",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("disk full")),
    )

    with pytest.raises(OSError):
        write_llm_artifacts(
            svc,
            artifact_stem="llm_summary",
            payload={"summary": "new"},
            markdown="# Summary\n",
        )

    assert existing_json.read_text(encoding="utf-8") == '{"summary": "keep"}'
    assert existing_md.read_text(encoding="utf-8") == "# keep\n"
    assert len(svc._artifacts) == 0


@pytest.mark.unit
def test_write_llm_artifacts_json_write_failure(tmp_path, monkeypatch) -> None:
    from transcriptx.core.output.output_service import OutputService
    from transcriptx.core.utils.output_structure import OutputStructure

    structure = OutputStructure(
        transcript_dir=str(tmp_path),
        module_dir=str(tmp_path / "llm_summary"),
        data_dir=str(tmp_path / "llm_summary" / "data"),
        global_data_dir=str(tmp_path / "llm_summary" / "data" / "global"),
    )
    (tmp_path / "llm_summary" / "data" / "global").mkdir(parents=True)
    svc = OutputService.__new__(OutputService)
    svc.base_name = "mini"
    svc.module_name = "llm_summary"
    svc.output_structure = structure
    svc._artifacts = []
    recorded: list = []
    svc.record_file = lambda *a, **k: recorded.append(a)  # type: ignore[method-assign]

    monkeypatch.setattr(
        "transcriptx.core.analysis.llm_common.write_json",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("json fail")),
    )

    with pytest.raises(OSError):
        write_llm_artifacts(
            svc,
            artifact_stem="llm_summary",
            payload={"summary": "ok"},
            markdown="# Summary\n",
        )
    assert recorded == []


@pytest.mark.unit
def test_parse_narrative_json_accepts_raw_json_without_fence() -> None:
    parsed = parse_narrative_json('{"narrative": "Plain JSON works."}')
    assert parsed["narrative"] == "Plain JSON works."


@pytest.mark.unit
def test_resolve_summary_payload_from_registered_artifact_meta(tmp_path) -> None:
    summary_dir = tmp_path / "summary" / "data" / "global"
    summary_dir.mkdir(parents=True)
    payload = {"overview": {"paragraph": "from disk"}}
    rel = "summary/data/global/mini_summary.json"
    (summary_dir / "mini_summary.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    meta_dir = tmp_path / ".transcriptx"
    meta_dir.mkdir(parents=True)
    (meta_dir / "artifacts_meta.json").write_text(
        json.dumps({rel: {"module": "summary"}}),
        encoding="utf-8",
    )

    context = type(
        "Ctx",
        (),
        {
            "get_analysis_result": lambda self, name: None,
            "get_base_name": lambda self: "mini",
            "get_transcript_dir": lambda self: str(tmp_path),
        },
    )()

    resolved = resolve_summary_payload(context)
    assert resolved["overview"]["paragraph"] == "from disk"


@pytest.mark.unit
def test_resolve_summary_payload_rejects_unregistered_disk_file(tmp_path) -> None:
    summary_dir = tmp_path / "summary" / "data" / "global"
    summary_dir.mkdir(parents=True)
    (summary_dir / "mini_summary.json").write_text(
        json.dumps({"overview": {"paragraph": "stale"}}),
        encoding="utf-8",
    )

    context = type(
        "Ctx",
        (),
        {
            "get_analysis_result": lambda self, name: None,
            "get_base_name": lambda self: "mini",
            "get_transcript_dir": lambda self: str(tmp_path),
        },
    )()
    with pytest.raises(ModuleDependencyMissingError):
        resolve_summary_payload(context)


@pytest.mark.unit
def test_resolve_summary_payload_failed_summary_in_context() -> None:
    context = type(
        "Ctx",
        (),
        {
            "get_analysis_result": lambda self, name: {"status": "error"},
            "get_base_name": lambda self: "mini",
            "get_transcript_dir": lambda self: "/missing",
        },
    )()
    with pytest.raises(ModuleDependencyMissingError) as exc:
        resolve_summary_payload(context)
    assert exc.value.error_code == LLM_DEPENDENCY_MISSING


@pytest.mark.unit
def test_format_transcript_lines_uses_stable_unnamed_label() -> None:
    segments = [{"speaker": "", "text": "hello world"}]
    lines = format_transcript_lines(segments)
    assert lines == ["Speaker: hello world"]


@pytest.mark.unit
def test_parse_narrative_json_rejects_extra_keys() -> None:
    with pytest.raises(LLMResponseError, match="unexpected keys"):
        parse_narrative_json('{"narrative": "ok", "extra": 1}')


@pytest.mark.unit
def test_sha256_llm_request_includes_system_prompt() -> None:
    user_only = sha256_llm_request("user")
    with_system = sha256_llm_request("user", system_prompt="sys")
    assert user_only != with_system


@pytest.mark.unit
def test_truncate_no_overlap_between_head_and_tail() -> None:
    lines = [f"Speaker: seg-{i}" for i in range(10)]
    _text, meta = truncate_transcript_block(lines, max_chars=120)
    assert meta["included_segments"] <= meta["total_segments"]
    assert (
        meta["omitted_segments"] == meta["total_segments"] - meta["included_segments"]
    )


@pytest.mark.unit
def test_truncate_very_small_budget() -> None:
    lines = ["Speaker: hello", "Speaker: goodbye"]
    text, meta = truncate_transcript_block(lines, max_chars=10)
    assert len(text) <= 10
    assert meta["truncated"] is True


@pytest.mark.unit
def test_build_bounded_user_prompt_counts_instruction_overhead() -> None:
    lines = ["Speaker: " + ("word " * 200)]
    transcript_block = "\n".join(lines)
    prompt, meta = build_bounded_user_prompt(
        instruction="Summarise this transcript:",
        transcript_block=transcript_block,
        max_input_chars=500,
    )
    assert len(prompt) <= 500
    assert meta["input_chars"] == len(prompt)
    assert meta["truncated"] is True
    assert "<<<END TRANSCRIPT>>>" in prompt
    assert sha256_text(prompt) != sha256_text(transcript_block)
