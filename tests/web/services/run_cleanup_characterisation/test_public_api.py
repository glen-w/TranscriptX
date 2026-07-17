"""Characterisation: public constructor / method signatures and observable attrs."""

from __future__ import annotations

import inspect
from pathlib import Path

from transcriptx.web.services.run_cleanup import CleanupMode, CleanupPreview
from transcriptx.web.services.run_cleanup.service import RunCleanupService

from . import assert_golden, make_service, mk_run


def _param_snapshot(sig: inspect.Signature) -> list[dict]:
    rows = []
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        default = param.default
        if default is inspect.Parameter.empty:
            default_repr = None
        elif default is None:
            default_repr = None
        else:
            default_repr = repr(default)
        rows.append(
            {
                "name": name,
                "kind": str(param.kind),
                "annotation": (
                    str(param.annotation)
                    if param.annotation is not inspect.Parameter.empty
                    else None
                ),
                "default": default_repr,
                "keyword_only": param.kind is inspect.Parameter.KEYWORD_ONLY,
            }
        )
    return rows


def _return_annotation(sig: inspect.Signature) -> str | None:
    if sig.return_annotation is inspect.Parameter.empty:
        return None
    return str(sig.return_annotation)


def test_public_api_signatures_snapshot():
    methods = (
        "__init__",
        "preview_cleanup",
        "execute_cleanup",
        "list_pending_staging",
        "retry_interrupted_staging",
    )
    payload = {}
    for name in methods:
        sig = inspect.signature(getattr(RunCleanupService, name))
        payload[name] = {
            "parameters": _param_snapshot(sig),
            "return_annotation": _return_annotation(sig),
        }
    # Explicit contracts called out in the plan.
    assert payload["__init__"]["parameters"][0]["keyword_only"] is True
    preview_params = {p["name"]: p for p in payload["preview_cleanup"]["parameters"]}
    assert set(preview_params) == {"mode", "session_id"}
    assert "session_id" in {p["name"] for p in payload["execute_cleanup"]["parameters"]}
    assert_golden("public_api_signatures.json", payload)


def test_observable_service_attributes(tmp_path: Path):
    svc = make_service(tmp_path)
    attrs = {
        "outputs_dir": str(svc.outputs_dir),
        "group_outputs_dir": str(svc.group_outputs_dir),
        "state_dir": str(svc.state_dir),
        "project_root": str(svc.project_root),
        "data_dir": str(svc.data_dir),
        "config_dir": str(svc.config_dir),
    }
    assert Path(attrs["outputs_dir"]) == tmp_path / "outputs"
    assert Path(attrs["group_outputs_dir"]) == tmp_path / "outputs" / "groups"
    assert Path(attrs["state_dir"]) == tmp_path / "state"
    assert Path(attrs["project_root"]) == tmp_path
    assert Path(attrs["data_dir"]) == tmp_path / "data"
    assert Path(attrs["config_dir"]) == tmp_path / "config"
    # Attribute *names* are the frozen contract (values are tmp-specific).
    assert_golden(
        "observable_attribute_names.json",
        {"attributes": sorted(attrs.keys())},
    )


def test_preview_return_type_contract(tmp_path: Path):
    svc = make_service(tmp_path)
    mk_run(svc.outputs_dir, "slug_a", "20200101_000000_00000001")
    token, preview = svc.preview_cleanup(CleanupMode.DELETE_ALL, "char-session")
    assert isinstance(token, str) and token
    assert isinstance(preview, CleanupPreview)
    assert preview.mode is CleanupMode.DELETE_ALL


def test_package_export_all_snapshot():
    import transcriptx.web.services.run_cleanup as pkg

    assert_golden("package_all.json", {"__all__": list(pkg.__all__)})
