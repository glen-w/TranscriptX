from transcriptx.core.pipeline.module_registry import get_default_modules


def _audio_resolver(value):
    if isinstance(value, (list, tuple)):
        return all(bool(item) for item in value)
    return bool(value)


def _dep_resolver_factory(ok: bool):
    def _resolver(_info):
        return ok

    return _resolver


def test_default_modules_selection_matrix():
    # 1) no audio, deps missing
    modules = get_default_modules(
        transcript_targets=[False],
        audio_resolver=_audio_resolver,
        dep_resolver=_dep_resolver_factory(False),
    )
    assert "voice_features" not in modules
    assert "prosody_dashboard" not in modules
    assert "voice_charts_core" not in modules

    # 2) no audio, deps present
    modules = get_default_modules(
        transcript_targets=[False],
        audio_resolver=_audio_resolver,
        dep_resolver=_dep_resolver_factory(True),
    )
    assert "voice_features" not in modules
    assert "prosody_dashboard" not in modules
    assert "voice_charts_core" not in modules

    # 3) audio present, deps missing
    modules = get_default_modules(
        transcript_targets=[True],
        audio_resolver=_audio_resolver,
        dep_resolver=_dep_resolver_factory(False),
    )
    assert "voice_features" not in modules
    assert "prosody_dashboard" not in modules
    assert "voice_charts_core" not in modules

    # 4) audio present, deps present
    modules = get_default_modules(
        transcript_targets=[True],
        audio_resolver=_audio_resolver,
        dep_resolver=_dep_resolver_factory(True),
    )
    assert "voice_features" in modules
    assert "prosody_dashboard" in modules
    assert "voice_charts_core" in modules
    assert "voice_contours" not in modules

    # Ordering: voice_features before consumers
    assert modules.index("voice_features") < modules.index("prosody_dashboard")
    assert modules.index("voice_features") < modules.index("voice_charts_core")
