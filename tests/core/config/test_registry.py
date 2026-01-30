from transcriptx.core.config.registry import flatten, unflatten, build_registry


def test_flatten_unflatten_roundtrip():
    nested = {"analysis": {"sentiment_window_size": 10}, "output": {"base": "x"}}
    dotmap = flatten(nested)
    assert dotmap["analysis.sentiment_window_size"] == 10
    assert dotmap["output.base"] == "x"
    rebuilt = unflatten(dotmap)
    assert rebuilt == nested


def test_build_registry_contains_defaults():
    registry = build_registry()
    assert "analysis.sentiment_window_size" in registry
