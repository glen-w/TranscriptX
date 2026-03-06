from transcriptx.core.config.coercion import coerce
from transcriptx.core.config.registry import FieldMetadata


def test_coerce_bool():
    meta = FieldMetadata(key="flag", path="flag", type=bool, default=False)
    assert coerce("true", meta) is True
    assert coerce("0", meta) is False


def test_coerce_list():
    meta = FieldMetadata(key="items", path="items", type=list, default=[])
    assert coerce("a,b", meta) == ["a", "b"]
