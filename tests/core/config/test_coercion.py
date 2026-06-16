import pytest

from transcriptx.core.config.coercion import coerce
from transcriptx.core.config.registry import FieldMetadata


def _meta(target: type) -> FieldMetadata:
    return FieldMetadata(key="k", path="k", type=target, default=None)


@pytest.mark.unit
def test_coerce_none_returns_none_regardless_of_target():
    for target in (bool, int, float, list, dict, str):
        assert coerce(None, _meta(target)) is None


@pytest.mark.unit
def test_coerce_bool():
    meta = _meta(bool)
    assert coerce("true", meta) is True
    assert coerce("0", meta) is False


@pytest.mark.unit
def test_coerce_bool_already_bool_passthrough():
    meta = _meta(bool)
    assert coerce(True, meta) is True
    assert coerce(False, meta) is False


@pytest.mark.unit
@pytest.mark.parametrize("raw", ["1", "yes", "on", "TRUE", " On "])
def test_coerce_bool_truthy_strings(raw):
    assert coerce(raw, _meta(bool)) is True


@pytest.mark.unit
@pytest.mark.parametrize("raw", ["0", "no", "off", "FALSE", " Off "])
def test_coerce_bool_falsy_strings(raw):
    assert coerce(raw, _meta(bool)) is False


@pytest.mark.unit
def test_coerce_bool_unrecognized_string_passthrough():
    # Unknown string is returned unchanged so validation can reject it later.
    assert coerce("maybe", _meta(bool)) == "maybe"


@pytest.mark.unit
def test_coerce_int_from_string_and_passthrough():
    meta = _meta(int)
    assert coerce("42", meta) == 42
    assert coerce("  7  ", meta) == 7
    assert coerce(5, meta) == 5


@pytest.mark.unit
def test_coerce_int_rejects_bool_and_invalid_string():
    meta = _meta(int)
    # bool is not treated as int (returned unchanged)
    assert coerce(True, meta) is True
    # non-numeric string is returned unchanged
    assert coerce("not-an-int", meta) == "not-an-int"


@pytest.mark.unit
def test_coerce_float_from_string_int_and_passthrough():
    meta = _meta(float)
    assert coerce("3.14", meta) == pytest.approx(3.14)
    assert coerce(2, meta) == pytest.approx(2.0)
    assert isinstance(coerce(2, meta), float)
    assert coerce("nan-ish", meta) == "nan-ish"


@pytest.mark.unit
def test_coerce_float_rejects_bool():
    assert coerce(True, _meta(float)) is True


@pytest.mark.unit
def test_coerce_list():
    meta = _meta(list)
    assert coerce("a,b", meta) == ["a", "b"]


@pytest.mark.unit
def test_coerce_list_json_array_and_passthrough():
    meta = _meta(list)
    assert coerce('["x", "y"]', meta) == ["x", "y"]
    already = ["z"]
    assert coerce(already, meta) is already


@pytest.mark.unit
def test_coerce_list_csv_trims_and_drops_empty():
    assert coerce(" a , , b ,", _meta(list)) == ["a", "b"]


@pytest.mark.unit
def test_coerce_list_empty_string_passthrough():
    # Empty/whitespace-only string is not coerced to a list.
    assert coerce("   ", _meta(list)) == "   "


@pytest.mark.unit
def test_coerce_list_json_object_falls_back_to_csv():
    # JSON parses to a dict, not a list, so the CSV fallback applies.
    assert coerce('{"a": 1}', _meta(list)) == ['{"a": 1}']


@pytest.mark.unit
def test_coerce_dict_from_json_and_passthrough():
    meta = _meta(dict)
    assert coerce('{"a": 1}', meta) == {"a": 1}
    already = {"b": 2}
    assert coerce(already, meta) is already


@pytest.mark.unit
def test_coerce_dict_invalid_json_passthrough():
    assert coerce("not json", _meta(dict)) == "not json"


@pytest.mark.unit
def test_coerce_dict_json_non_object_passthrough():
    # Valid JSON but not an object is returned unchanged.
    assert coerce("[1, 2]", _meta(dict)) == "[1, 2]"


@pytest.mark.unit
def test_coerce_unknown_target_passthrough():
    # str (and any non-handled target) returns the raw value unchanged.
    assert coerce("hello", _meta(str)) == "hello"
    assert coerce(123, _meta(str)) == 123
