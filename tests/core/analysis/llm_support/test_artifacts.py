"""Failure-injection suite for the artifact-pair contract.

Asserts the documented contract: atomic pair promotion with rollback, then
registration; no filesystem rollback after registration begins.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from transcriptx.core.analysis.llm_support.artifacts import (
    write_llm_artifacts,
    write_llm_speaker_artifacts,
)

_ARTIFACTS_MODULE = "transcriptx.core.analysis.llm_support.artifacts"


def _output_service(tmp_path: Path, *, record=None):
    from transcriptx.core.output.output_service import OutputService
    from transcriptx.core.utils.output_structure import OutputStructure

    structure = OutputStructure(
        transcript_dir=str(tmp_path),
        module_dir=str(tmp_path / "llm_summary"),
        data_dir=str(tmp_path / "llm_summary" / "data"),
        global_data_dir=str(tmp_path / "llm_summary" / "data" / "global"),
        speaker_data_dir=str(tmp_path / "llm_summary" / "data" / "speakers"),
    )
    svc = OutputService.__new__(OutputService)
    svc.base_name = "mini"
    svc.module_name = "llm_summary"
    svc.output_structure = structure
    svc._artifacts = []

    if record is None:

        def record(path, artifact_type="json"):
            svc._artifacts.append({"path": str(path), "type": artifact_type})

    svc.record_file = record  # type: ignore[method-assign]
    return svc


def _global_dir(svc) -> Path:
    return Path(svc.output_structure.global_data_dir)


def _seed_priors(out_dir: Path, *, json_file: bool = True, md_file: bool = True):
    out_dir.mkdir(parents=True, exist_ok=True)
    priors = {}
    if json_file:
        p = out_dir / "mini_llm_summary.json"
        p.write_text('{"summary": "keep"}', encoding="utf-8")
        priors["json"] = p
    if md_file:
        p = out_dir / "mini_llm_summary.md"
        p.write_text("# keep\n", encoding="utf-8")
        priors["md"] = p
    return priors


def _write(svc, payload=None, markdown="# Summary\n"):
    return write_llm_artifacts(
        svc,
        artifact_stem="llm_summary",
        payload=payload or {"summary": "new"},
        markdown=markdown,
    )


def _assert_no_staging(out_dir: Path) -> None:
    assert not (out_dir / ".staging").exists()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_happy_path_final_paths_and_registration_order(tmp_path) -> None:
    svc = _output_service(tmp_path)
    json_path, md_path = _write(svc, payload={"summary": "ok"})
    expected_dir = _global_dir(svc)
    assert json_path == str(expected_dir / "mini_llm_summary.json")
    assert md_path == str(expected_dir / "mini_llm_summary.md")
    assert json.loads(Path(json_path).read_text(encoding="utf-8")) == {"summary": "ok"}
    assert Path(md_path).read_text(encoding="utf-8") == "# Summary\n"
    assert [a["type"] for a in svc._artifacts] == ["json", "md"]
    _assert_no_staging(expected_dir)


@pytest.mark.unit
def test_speaker_happy_path_final_paths(tmp_path) -> None:
    svc = _output_service(tmp_path)
    json_path, md_path = write_llm_speaker_artifacts(
        svc,
        speaker="Alice Smith/QA",
        artifact_filename="llm_speaker_summary",
        payload={"summary": "ok"},
        markdown="# Alice\n",
    )
    expected_dir = Path(svc.output_structure.speaker_data_dir)
    assert json_path == str(
        expected_dir / "mini_Alice_Smith_QA_llm_speaker_summary.json"
    )
    assert md_path == str(expected_dir / "mini_Alice_Smith_QA_llm_speaker_summary.md")
    assert Path(json_path).exists()
    assert Path(md_path).exists()
    _assert_no_staging(expected_dir)


@pytest.mark.unit
def test_happy_path_overwrites_both_priors(tmp_path) -> None:
    svc = _output_service(tmp_path)
    priors = _seed_priors(_global_dir(svc))
    _write(svc, payload={"summary": "new"})
    assert json.loads(priors["json"].read_text(encoding="utf-8")) == {"summary": "new"}
    assert priors["md"].read_text(encoding="utf-8") == "# Summary\n"


# ---------------------------------------------------------------------------
# Staging failures (before any promotion)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_write_json_failure_promotes_nothing(tmp_path, monkeypatch) -> None:
    recorded: list = []
    svc = _output_service(tmp_path, record=lambda *a, **k: recorded.append(a))
    out_dir = _global_dir(svc)
    priors = _seed_priors(out_dir)
    monkeypatch.setattr(
        f"{_ARTIFACTS_MODULE}.write_json",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("json fail")),
    )
    with pytest.raises(OSError, match="json fail"):
        _write(svc)
    assert priors["json"].read_text(encoding="utf-8") == '{"summary": "keep"}'
    assert priors["md"].read_text(encoding="utf-8") == "# keep\n"
    assert recorded == []
    _assert_no_staging(out_dir)


@pytest.mark.unit
def test_write_text_failure_promotes_nothing(tmp_path, monkeypatch) -> None:
    svc = _output_service(tmp_path, record=lambda *_a, **_k: None)
    out_dir = _global_dir(svc)
    out_dir.mkdir(parents=True)
    monkeypatch.setattr(
        f"{_ARTIFACTS_MODULE}.write_text",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("disk full")),
    )
    with pytest.raises(OSError, match="disk full"):
        _write(svc)
    assert not list(out_dir.glob("mini_llm_summary.*"))
    _assert_no_staging(out_dir)


@pytest.mark.unit
def test_write_text_failure_preserves_existing_pair(tmp_path, monkeypatch) -> None:
    svc = _output_service(tmp_path, record=lambda *_a, **_k: None)
    out_dir = _global_dir(svc)
    priors = _seed_priors(out_dir)
    monkeypatch.setattr(
        f"{_ARTIFACTS_MODULE}.write_text",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("disk full")),
    )
    with pytest.raises(OSError):
        _write(svc)
    assert priors["json"].read_text(encoding="utf-8") == '{"summary": "keep"}'
    assert priors["md"].read_text(encoding="utf-8") == "# keep\n"
    assert len(svc._artifacts) == 0
    _assert_no_staging(out_dir)


@pytest.mark.unit
def test_staging_directory_creation_failure(tmp_path, monkeypatch) -> None:
    svc = _output_service(tmp_path)
    out_dir = _global_dir(svc)
    priors = _seed_priors(out_dir)

    real_mkdir = Path.mkdir

    def _fail_staging_mkdir(self, *args, **kwargs):
        if ".staging" in str(self):
            raise OSError("mkdir denied")
        return real_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", _fail_staging_mkdir)
    with pytest.raises(OSError, match="mkdir denied"):
        _write(svc)
    assert priors["json"].read_text(encoding="utf-8") == '{"summary": "keep"}'
    assert priors["md"].read_text(encoding="utf-8") == "# keep\n"
    assert len(svc._artifacts) == 0


@pytest.mark.unit
def test_backup_copy_failure_promotes_nothing(tmp_path, monkeypatch) -> None:
    svc = _output_service(tmp_path)
    out_dir = _global_dir(svc)
    priors = _seed_priors(out_dir)
    monkeypatch.setattr(
        f"{_ARTIFACTS_MODULE}.shutil.copy2",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("copy fail")),
    )
    with pytest.raises(OSError, match="copy fail"):
        _write(svc)
    assert priors["json"].read_text(encoding="utf-8") == '{"summary": "keep"}'
    assert priors["md"].read_text(encoding="utf-8") == "# keep\n"
    assert len(svc._artifacts) == 0
    _assert_no_staging(out_dir)


# ---------------------------------------------------------------------------
# Promotion failures
# ---------------------------------------------------------------------------


def _fail_replace_at(monkeypatch, n: int, error: str = "promote failed"):
    """Fail the n-th promotion-level ``os.replace``.

    ``write_json`` / ``write_text`` also call ``os.replace`` internally for
    their own staging-local atomic writes; those have destinations inside
    ``.staging`` and are excluded from the count. Counted calls: 1 = JSON
    promotion, 2 = Markdown promotion, 3 = rollback restore.
    """
    real_replace = os.replace
    calls = {"n": 0}

    def _replace(src, dst):
        if ".staging" not in str(dst):
            calls["n"] += 1
            if calls["n"] == n:
                raise OSError(error)
        real_replace(src, dst)

    monkeypatch.setattr(f"{_ARTIFACTS_MODULE}.os.replace", _replace)
    return calls


@pytest.mark.unit
def test_first_replace_failure_leaves_priors_untouched(tmp_path, monkeypatch) -> None:
    svc = _output_service(tmp_path)
    out_dir = _global_dir(svc)
    priors = _seed_priors(out_dir)
    _fail_replace_at(monkeypatch, 1, "json promote failed")
    with pytest.raises(OSError, match="json promote failed"):
        _write(svc)
    assert priors["json"].read_text(encoding="utf-8") == '{"summary": "keep"}'
    assert priors["md"].read_text(encoding="utf-8") == "# keep\n"
    assert len(svc._artifacts) == 0
    _assert_no_staging(out_dir)


@pytest.mark.unit
def test_second_replace_failure_restores_json_once_with_both_priors(
    tmp_path, monkeypatch
) -> None:
    svc = _output_service(tmp_path, record=lambda *_a, **_k: None)
    out_dir = _global_dir(svc)
    priors = _seed_priors(out_dir)
    _fail_replace_at(monkeypatch, 2, "md promote failed")
    with pytest.raises(OSError, match="md promote failed"):
        _write(svc)
    # Prior JSON restored (not deleted by a double rollback) and prior MD intact.
    assert priors["json"].read_text(encoding="utf-8") == '{"summary": "keep"}'
    assert priors["md"].read_text(encoding="utf-8") == "# keep\n"
    assert len(svc._artifacts) == 0
    _assert_no_staging(out_dir)


@pytest.mark.unit
def test_second_replace_failure_unlinks_json_when_no_priors(
    tmp_path, monkeypatch
) -> None:
    svc = _output_service(tmp_path, record=lambda *_a, **_k: None)
    out_dir = _global_dir(svc)
    out_dir.mkdir(parents=True)
    _fail_replace_at(monkeypatch, 2, "md promote failed")
    with pytest.raises(OSError, match="md promote failed"):
        _write(svc)
    assert not list(out_dir.glob("mini_llm_summary.*"))
    _assert_no_staging(out_dir)


@pytest.mark.unit
def test_second_replace_failure_restores_when_json_existed_but_md_did_not(
    tmp_path, monkeypatch
) -> None:
    svc = _output_service(tmp_path, record=lambda *_a, **_k: None)
    out_dir = _global_dir(svc)
    priors = _seed_priors(out_dir, md_file=False)
    _fail_replace_at(monkeypatch, 2, "md promote failed")
    with pytest.raises(OSError, match="md promote failed"):
        _write(svc)
    assert priors["json"].read_text(encoding="utf-8") == '{"summary": "keep"}'
    assert not (out_dir / "mini_llm_summary.md").exists()
    _assert_no_staging(out_dir)


@pytest.mark.unit
def test_second_replace_failure_unlinks_json_when_only_md_existed(
    tmp_path, monkeypatch
) -> None:
    svc = _output_service(tmp_path, record=lambda *_a, **_k: None)
    out_dir = _global_dir(svc)
    priors = _seed_priors(out_dir, json_file=False)
    _fail_replace_at(monkeypatch, 2, "md promote failed")
    with pytest.raises(OSError, match="md promote failed"):
        _write(svc)
    assert not (out_dir / "mini_llm_summary.json").exists()
    assert priors["md"].read_text(encoding="utf-8") == "# keep\n"
    _assert_no_staging(out_dir)


@pytest.mark.unit
def test_rollback_failure_preserves_original_promotion_exception(
    tmp_path, monkeypatch
) -> None:
    """If restoring the JSON backup also fails, the Markdown promotion error
    is still the raised exception (rollback failure only as context)."""
    svc = _output_service(tmp_path, record=lambda *_a, **_k: None)
    out_dir = _global_dir(svc)
    _seed_priors(out_dir)

    real_replace = os.replace
    calls = {"n": 0}

    def _replace(src, dst):
        if ".staging" in str(dst):
            real_replace(src, dst)
            return
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("md promote failed")
        if calls["n"] == 3:
            raise OSError("rollback failed")
        real_replace(src, dst)

    monkeypatch.setattr(f"{_ARTIFACTS_MODULE}.os.replace", _replace)
    with pytest.raises(OSError, match="md promote failed") as exc_info:
        _write(svc)
    assert calls["n"] == 3
    context = exc_info.value.__context__
    assert context is not None and "rollback failed" in str(context)


# ---------------------------------------------------------------------------
# Registration failures (no filesystem rollback after registration begins)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_first_record_file_failure_leaves_both_files_promoted(tmp_path) -> None:
    def _fail_first(path, artifact_type="json"):
        raise RuntimeError("registration backend down")

    svc = _output_service(tmp_path, record=_fail_first)
    out_dir = _global_dir(svc)
    _seed_priors(out_dir)
    with pytest.raises(RuntimeError, match="registration backend down"):
        _write(svc, payload={"summary": "new"})
    # Both files remain promoted with the NEW content; nothing registered.
    assert json.loads(
        (out_dir / "mini_llm_summary.json").read_text(encoding="utf-8")
    ) == {"summary": "new"}
    assert (out_dir / "mini_llm_summary.md").read_text(encoding="utf-8") == (
        "# Summary\n"
    )
    assert svc._artifacts == []
    _assert_no_staging(out_dir)


@pytest.mark.unit
def test_second_record_file_failure_keeps_json_registration(tmp_path) -> None:
    registered: list = []

    def _fail_second(path, artifact_type="json"):
        if artifact_type == "md":
            raise RuntimeError("md registration failed")
        registered.append((str(path), artifact_type))

    svc = _output_service(tmp_path, record=_fail_second)
    out_dir = _global_dir(svc)
    with pytest.raises(RuntimeError, match="md registration failed"):
        _write(svc, payload={"summary": "new"})
    # Both files remain promoted; JSON registration succeeded and is kept.
    assert json.loads(
        (out_dir / "mini_llm_summary.json").read_text(encoding="utf-8")
    ) == {"summary": "new"}
    assert (out_dir / "mini_llm_summary.md").exists()
    assert registered == [
        (str(out_dir / "mini_llm_summary.json"), "json"),
    ]
    _assert_no_staging(out_dir)


# ---------------------------------------------------------------------------
# Staging cleanup
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_staging_cleaned_in_finally_even_when_rmtree_partially_fails(
    tmp_path, monkeypatch
) -> None:
    """Cleanup runs in ``finally`` on both success and failure paths."""
    svc = _output_service(tmp_path)
    out_dir = _global_dir(svc)
    _write(svc)
    _assert_no_staging(out_dir)

    monkeypatch.setattr(
        f"{_ARTIFACTS_MODULE}.write_text",
        lambda *_a, **_k: (_ for _ in ()).throw(OSError("disk full")),
    )
    with pytest.raises(OSError):
        _write(svc)
    _assert_no_staging(out_dir)


@pytest.mark.unit
def test_staging_root_left_when_other_writer_active(tmp_path) -> None:
    """A concurrent writer's staging subdirectory must not be removed."""
    svc = _output_service(tmp_path)
    out_dir = _global_dir(svc)
    out_dir.mkdir(parents=True)
    other = out_dir / ".staging" / "other-writer"
    other.mkdir(parents=True)
    _write(svc)
    assert other.exists()
    shutil.rmtree(out_dir / ".staging")
