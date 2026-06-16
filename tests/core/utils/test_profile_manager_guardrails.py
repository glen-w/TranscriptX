from __future__ import annotations

import json
import os
from pathlib import Path

from transcriptx.core.utils.profile_manager import ProfileManager


def test_profile_rename_updates_embedded_identity(tmp_path: Path) -> None:
    pm = ProfileManager(profiles_dir=tmp_path)
    assert pm.save_profile("acts", "alpha", {"ml_model_name": "x"}, "desc")
    assert pm.rename_profile("acts", "alpha", "beta")
    payload = pm.load_profile("acts", "beta")
    assert payload is not None
    assert payload["name"] == "beta"
    assert payload["module"] == "acts"


def test_import_profile_rejects_invalid_shape(tmp_path: Path) -> None:
    pm = ProfileManager(profiles_dir=tmp_path)
    import_file = tmp_path / "invalid.json"
    import_file.write_text(json.dumps({"name": "x", "module": "acts"}))
    assert not pm.import_profile("acts", "x", import_file)


def test_import_profile_rejects_module_mismatch(tmp_path: Path) -> None:
    pm = ProfileManager(profiles_dir=tmp_path)
    import_file = tmp_path / "mismatch.json"
    import_file.write_text(
        json.dumps(
            {
                "name": "x",
                "module": "topic_modeling",
                "description": "desc",
                "config": {"max_features": 10},
            }
        )
    )
    assert not pm.import_profile("acts", "x", import_file)


def test_list_profiles_returns_saved_only_when_no_profiles_exist(
    tmp_path: Path,
) -> None:
    pm = ProfileManager(profiles_dir=tmp_path)
    assert pm.list_profiles("workflow") == []


def test_list_profiles_excludes_persisted_default_artifact(tmp_path: Path) -> None:
    pm = ProfileManager(profiles_dir=tmp_path)
    legacy_default = pm.get_profile_path("acts", "default")
    legacy_default.write_text(
        json.dumps(
            {
                "name": "default",
                "module": "acts",
                "description": "legacy",
                "config": {"ml_model_name": "legacy"},
            }
        )
    )
    assert pm.save_profile("acts", "team", {"ml_model_name": "team"}, "team")
    profiles = pm.list_profiles("acts")
    assert "default" not in profiles
    assert "team" in profiles


def test_list_profiles_is_deterministic_and_not_alphabetical(tmp_path: Path) -> None:
    pm = ProfileManager(profiles_dir=tmp_path)
    assert pm.save_profile("acts", "zeta", {"ml_model_name": "z"}, "z")
    assert pm.save_profile("acts", "alpha", {"ml_model_name": "a"}, "a")
    acts_dir = tmp_path / "acts"
    zeta_path = acts_dir / "zeta.json"
    alpha_path = acts_dir / "alpha.json"
    os.utime(zeta_path, ns=(1, 1))
    os.utime(alpha_path, ns=(2, 2))
    # mtime-desc ordering should keep alpha before zeta even if that happens to differ from sort policy.
    assert pm.list_profiles("acts") == ["alpha", "zeta"]


def test_rename_profile_keeps_old_file_when_new_write_fails(
    tmp_path: Path, monkeypatch
) -> None:
    pm = ProfileManager(profiles_dir=tmp_path)
    assert pm.save_profile("acts", "alpha", {"ml_model_name": "x"}, "desc")

    monkeypatch.setattr(
        ProfileManager,
        "_atomic_write_json",
        staticmethod(lambda _path, _payload: False),
    )
    assert not pm.rename_profile("acts", "alpha", "beta")
    assert pm.profile_exists("acts", "alpha")
    assert not pm.profile_exists("acts", "beta")


def test_rename_profile_rolls_back_new_when_old_delete_fails(
    tmp_path: Path, monkeypatch
) -> None:
    pm = ProfileManager(profiles_dir=tmp_path)
    assert pm.save_profile("acts", "alpha", {"ml_model_name": "x"}, "desc")
    old_path = pm.get_profile_path("acts", "alpha")
    original_unlink = Path.unlink

    def _raise_for_old(path_obj, *args, **kwargs):
        if path_obj == old_path:
            raise OSError("simulated delete failure")
        return original_unlink(path_obj, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", _raise_for_old)
    assert not pm.rename_profile("acts", "alpha", "beta")
    assert pm.profile_exists("acts", "alpha")
    assert not pm.profile_exists("acts", "beta")


def test_import_profile_overwrite_contract(tmp_path: Path) -> None:
    pm = ProfileManager(profiles_dir=tmp_path)
    assert pm.save_profile("acts", "alpha", {"ml_model_name": "x"}, "desc")
    import_file = tmp_path / "import.json"
    import_file.write_text(
        json.dumps(
            {
                "name": "alpha",
                "module": "acts",
                "description": "new",
                "config": {"ml_model_name": "y"},
            }
        )
    )
    assert not pm.import_profile("acts", "alpha", import_file, overwrite=False)
    assert pm.import_profile("acts", "alpha", import_file, overwrite=True)


def test_create_profile_fails_if_destination_exists(tmp_path: Path) -> None:
    pm = ProfileManager(profiles_dir=tmp_path)
    assert pm.create_profile("acts", "alpha", {"ml_model_name": "x"}, "desc")
    assert not pm.create_profile("acts", "alpha", {"ml_model_name": "y"}, "desc")


def test_rename_rolls_back_when_payload_rewrite_fails(
    tmp_path: Path, monkeypatch
) -> None:
    pm = ProfileManager(profiles_dir=tmp_path)
    assert pm.save_profile("acts", "alpha", {"ml_model_name": "x"}, "desc")
    call_count = {"count": 0}
    original = ProfileManager._atomic_write_json

    def _fail_once(path, payload):
        call_count["count"] += 1
        if call_count["count"] == 1:
            return False
        return original(path, payload)

    monkeypatch.setattr(ProfileManager, "_atomic_write_json", staticmethod(_fail_once))
    assert not pm.rename_profile("acts", "alpha", "beta")
    assert pm.profile_exists("acts", "alpha")
    assert not pm.profile_exists("acts", "beta")


def test_rename_profile_fails_when_destination_exists(tmp_path: Path) -> None:
    pm = ProfileManager(profiles_dir=tmp_path)
    assert pm.save_profile("acts", "alpha", {"ml_model_name": "x"}, "desc-a")
    assert pm.save_profile("acts", "beta", {"ml_model_name": "y"}, "desc-b")
    assert not pm.rename_profile("acts", "alpha", "beta")
    assert pm.profile_exists("acts", "alpha")
    assert pm.profile_exists("acts", "beta")


def test_load_profile_rejects_invalid_payload_shape(tmp_path: Path) -> None:
    pm = ProfileManager(profiles_dir=tmp_path)
    raw_path = pm.get_profile_path("acts", "bad")
    raw_path.write_text(json.dumps({"name": "bad", "module": "acts"}))
    assert pm.load_profile("acts", "bad") is None


def test_virtual_default_is_not_exposed_by_storage_apis(tmp_path: Path) -> None:
    pm = ProfileManager(profiles_dir=tmp_path)
    import_file = tmp_path / "import.json"
    import_file.write_text(
        json.dumps(
            {
                "name": "default",
                "module": "acts",
                "description": "x",
                "config": {"ml_model_name": "x"},
            }
        )
    )
    assert pm.load_profile("acts", "default") is None
    assert "default" not in pm.list_profiles("acts")
    assert pm.profile_exists("acts", "default") is False
    assert not pm.save_profile("acts", "default", {"ml_model_name": "x"})
    assert not pm.create_profile("acts", "default", {"ml_model_name": "x"})
    assert not pm.rename_profile("acts", "default", "renamed")
    assert not pm.rename_profile("acts", "renamed", "default")
    assert not pm.delete_profile("acts", "default")
    assert not pm.import_profile("acts", "default", import_file, overwrite=True)
    assert not pm.export_profile("acts", "default", tmp_path / "out.json")


def test_save_profile_failure_keeps_last_valid_artifact(
    tmp_path: Path, monkeypatch
) -> None:
    pm = ProfileManager(profiles_dir=tmp_path)
    assert pm.save_profile("acts", "team", {"ml_model_name": "v1"}, "d1")
    original = pm.get_profile_path("acts", "team").read_text(encoding="utf-8")
    monkeypatch.setattr(
        ProfileManager,
        "_atomic_write_json",
        staticmethod(lambda _path, _payload: False),
    )
    assert not pm.save_profile(
        "acts", "team", {"ml_model_name": "v2"}, "d2", overwrite=True
    )
    assert pm.get_profile_path("acts", "team").read_text(encoding="utf-8") == original


def test_create_profile_failure_leaves_no_partial_artifact(
    tmp_path: Path, monkeypatch
) -> None:
    pm = ProfileManager(profiles_dir=tmp_path)
    monkeypatch.setattr(
        ProfileManager,
        "_atomic_write_json",
        staticmethod(lambda _path, _payload: False),
    )
    assert not pm.create_profile("acts", "new_profile", {"ml_model_name": "x"}, "d")
    assert not pm.get_profile_path("acts", "new_profile").exists()


def test_import_overwrite_failure_keeps_last_valid_artifact(
    tmp_path: Path, monkeypatch
) -> None:
    pm = ProfileManager(profiles_dir=tmp_path)
    assert pm.save_profile("acts", "team", {"ml_model_name": "v1"}, "d1")
    original = pm.get_profile_path("acts", "team").read_text(encoding="utf-8")
    import_file = tmp_path / "import_overwrite.json"
    import_file.write_text(
        json.dumps(
            {
                "name": "team",
                "module": "acts",
                "description": "new",
                "config": {"ml_model_name": "v2"},
            }
        )
    )
    monkeypatch.setattr(
        ProfileManager,
        "_atomic_write_json",
        staticmethod(lambda _path, _payload: False),
    )
    assert not pm.import_profile("acts", "team", import_file, overwrite=True)
    assert pm.get_profile_path("acts", "team").read_text(encoding="utf-8") == original


def test_delete_profile_false_when_missing_true_when_present(tmp_path: Path) -> None:
    pm = ProfileManager(profiles_dir=tmp_path)
    assert not pm.delete_profile("acts", "ghost")
    assert pm.save_profile("acts", "p1", {"ml_model_name": "a"}, "d")
    assert pm.delete_profile("acts", "p1")
    assert not pm.profile_exists("acts", "p1")


def test_export_profile_success(tmp_path: Path) -> None:
    pm = ProfileManager(profiles_dir=tmp_path)
    assert pm.save_profile("acts", "p1", {"ml_model_name": "a"}, "d")
    dest = tmp_path / "out.json"
    assert pm.export_profile("acts", "p1", dest)
    assert dest.exists()


def test_import_profile_rejects_missing_source_file(tmp_path: Path) -> None:
    pm = ProfileManager(profiles_dir=tmp_path)
    assert not pm.import_profile("acts", "x", tmp_path / "missing.json")


def test_load_profile_returns_none_on_invalid_json(tmp_path: Path) -> None:
    pm = ProfileManager(profiles_dir=tmp_path)
    bad = pm.get_profile_path("acts", "badjson")
    bad.write_text("{not json", encoding="utf-8")
    assert pm.load_profile("acts", "badjson") is None
