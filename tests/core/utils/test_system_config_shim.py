from __future__ import annotations


def test_system_to_dict_delegates_to_main_canonical_serializer(monkeypatch) -> None:
    from transcriptx.core.utils.config.main import TranscriptXConfig as MainConfig
    from transcriptx.core.utils.config.system import TranscriptXConfig as SystemConfig

    called = {"count": 0}

    def _fake_main_to_dict(self):
        called["count"] += 1
        return {"canonical": True}

    monkeypatch.setattr(MainConfig, "to_dict", _fake_main_to_dict)
    cfg = SystemConfig()
    assert cfg.to_dict() == {"canonical": True}
    assert called["count"] == 1
