"""Unit tests for OllamaClient (mocked urllib)."""

from __future__ import annotations

import io
import json
import socket
import urllib.error
from unittest.mock import patch

import pytest

from transcriptx.core.llm.errors import (
    LLM_GENERATION_ERROR,
    LLM_INVALID_RESPONSE,
    LLM_MODEL_MISSING,
    LLM_UNAVAILABLE,
    LLMConfigurationError,
    LLMGenerationError,
    LLMModelMissingError,
    LLMResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from transcriptx.core.llm.ollama_client import (
    DEFAULT_OLLAMA_BASE_URL,
    OllamaClient,
    _is_model_not_found_body,
    build_ollama_client,
    normalize_base_url,
)


@pytest.mark.unit
def test_normalize_base_url_strips_trailing_slash() -> None:
    assert normalize_base_url("http://localhost:11434/") == "http://localhost:11434"


@pytest.mark.unit
def test_is_available_true_on_tags_success() -> None:
    client = OllamaClient()
    with patch.object(client, "_http_get", return_value='{"models":[]}'):
        assert client.is_available() is True


@pytest.mark.unit
def test_is_available_false_on_failure() -> None:
    client = OllamaClient()
    with patch.object(client, "_http_get", side_effect=OSError("down")):
        assert client.is_available() is False


@pytest.mark.unit
def test_generate_success() -> None:
    client = OllamaClient(model="qwen3:8b")
    body = json.dumps({"response": "Hello summary"})
    with patch.object(client, "_http_post", return_value=body):
        out = client.generate(prompt="hi", temperature=0.0)
    assert out == "Hello summary"


@pytest.mark.unit
def test_generate_malformed_json_raises_invalid_response() -> None:
    client = OllamaClient()
    with patch.object(client, "_http_post", return_value="not json"):
        with pytest.raises(LLMResponseError) as exc:
            client.generate(prompt="hi", temperature=0.0)
    assert exc.value.error_code == LLM_INVALID_RESPONSE


@pytest.mark.unit
def test_generate_missing_response_field() -> None:
    client = OllamaClient()
    with patch.object(client, "_http_post", return_value=json.dumps({"done": True})):
        with pytest.raises(LLMResponseError) as exc:
            client.generate(prompt="hi", temperature=0.0)
    assert exc.value.error_code == LLM_INVALID_RESPONSE


@pytest.mark.unit
def test_generate_empty_response_field() -> None:
    client = OllamaClient()
    with patch.object(
        client, "_http_post", return_value=json.dumps({"response": "  "})
    ):
        with pytest.raises(LLMResponseError):
            client.generate(prompt="hi", temperature=0.0)


@pytest.mark.unit
def test_http_404_maps_to_model_missing() -> None:
    client = OllamaClient(model="missing:1b")
    err = urllib.error.HTTPError(
        url="http://x/api/generate",
        code=404,
        msg="Not Found",
        hdrs=None,
        fp=io.BytesIO(b'{"error":"model \'missing:1b\' not found"}'),
    )
    with patch.object(client, "_http_post", side_effect=err):
        with pytest.raises(LLMModelMissingError) as exc:
            client.generate(prompt="hi", temperature=0.0)
    assert exc.value.error_code == LLM_MODEL_MISSING


@pytest.mark.unit
def test_http_404_empty_body_maps_to_generation_error() -> None:
    client = OllamaClient(model="missing:1b")
    err = urllib.error.HTTPError(
        url="http://x/api/generate",
        code=404,
        msg="Not Found",
        hdrs=None,
        fp=io.BytesIO(b""),
    )
    with patch.object(client, "_http_post", side_effect=err):
        with pytest.raises(LLMGenerationError) as exc:
            client.generate(prompt="hi", temperature=0.0)
    assert exc.value.error_code == LLM_GENERATION_ERROR


@pytest.mark.unit
def test_http_401_maps_to_generation_error_no_retry() -> None:
    client = OllamaClient()
    err = urllib.error.HTTPError(
        url="http://x/api/generate",
        code=401,
        msg="Unauthorized",
        hdrs=None,
        fp=io.BytesIO(b""),
    )
    with patch.object(client, "_http_post", side_effect=err):
        with pytest.raises(LLMGenerationError) as exc:
            client.generate(prompt="hi", temperature=0.0)
    assert exc.value.error_code == LLM_GENERATION_ERROR


@pytest.mark.unit
def test_connection_refused_retries_then_unavailable() -> None:
    client = OllamaClient()
    refused = urllib.error.URLError(ConnectionRefusedError())
    with patch.object(client, "_http_post", side_effect=refused) as mock_post:
        with pytest.raises(LLMUnavailableError) as exc:
            client.generate(prompt="hi", temperature=0.0)
    assert exc.value.error_code == LLM_UNAVAILABLE
    assert mock_post.call_count == 3


@pytest.mark.unit
def test_timeout_urlerror_maps_to_timeout_after_retries() -> None:
    client = OllamaClient()
    timeout_err = urllib.error.URLError(socket.timeout("timed out"))
    with patch.object(client, "_http_post", side_effect=timeout_err) as mock_post:
        with pytest.raises(LLMTimeoutError) as exc:
            client.generate(prompt="hi", temperature=0.0)
    assert exc.value.error_code == "llm_timeout"
    assert mock_post.call_count == 3


@pytest.mark.unit
def test_http_404_generic_maps_to_generation_error() -> None:
    client = OllamaClient(model="qwen3:8b")
    err = urllib.error.HTTPError(
        url="http://x/api/generate",
        code=404,
        msg="Not Found",
        hdrs=None,
        fp=io.BytesIO(b'{"error":"endpoint missing"}'),
    )
    with patch.object(client, "_http_post", side_effect=err) as mock_post:
        with pytest.raises(LLMGenerationError) as exc:
            client.generate(prompt="hi", temperature=0.0)
    assert exc.value.error_code == LLM_GENERATION_ERROR
    assert mock_post.call_count == 1


@pytest.mark.unit
def test_constructor_rejects_empty_model() -> None:
    with pytest.raises(LLMConfigurationError):
        OllamaClient(model="  ")


@pytest.mark.unit
def test_retryable_5xx_then_generation_error() -> None:
    client = OllamaClient()
    err = urllib.error.HTTPError(
        url="http://x/api/generate",
        code=503,
        msg="Service Unavailable",
        hdrs=None,
        fp=io.BytesIO(b""),
    )
    with patch.object(client, "_http_post", side_effect=err) as mock_post:
        with pytest.raises(LLMGenerationError) as exc:
            client.generate(prompt="hi", temperature=0.0)
    assert exc.value.error_code == LLM_GENERATION_ERROR
    assert mock_post.call_count == 3


@pytest.mark.unit
def test_http_400_maps_to_generation_error_single_attempt() -> None:
    client = OllamaClient()
    err = urllib.error.HTTPError(
        url="http://x/api/generate",
        code=400,
        msg="Bad Request",
        hdrs=None,
        fp=io.BytesIO(b""),
    )
    with patch.object(client, "_http_post", side_effect=err) as mock_post:
        with pytest.raises(LLMGenerationError) as exc:
            client.generate(prompt="hi", temperature=0.0)
    assert exc.value.error_code == LLM_GENERATION_ERROR
    assert mock_post.call_count == 1


@pytest.mark.unit
def test_generate_request_body_omits_system_and_includes_options() -> None:
    client = OllamaClient(model="qwen3:8b", seed=7, max_output_tokens=512)
    captured: dict = {}

    def _fake_post(path: str, body: dict, *, timeout: float) -> str:
        captured["path"] = path
        captured["body"] = body
        return json.dumps({"response": "ok"})

    with patch.object(client, "_http_post", side_effect=_fake_post):
        client.generate(prompt="user text", temperature=0.2, max_tokens=128)

    assert captured["path"] == "/api/generate"
    body = captured["body"]
    assert body["model"] == "qwen3:8b"
    assert body["prompt"] == "user text"
    assert body["stream"] is False
    assert "system" not in body
    assert body["options"]["temperature"] == 0.2
    assert body["options"]["seed"] == 7
    assert body["options"]["num_predict"] == 128


@pytest.mark.unit
def test_generate_includes_system_when_provided() -> None:
    client = OllamaClient()
    captured: dict = {}

    def _fake_post(path: str, body: dict, *, timeout: float) -> str:
        captured["body"] = body
        return json.dumps({"response": "ok"})

    with patch.object(client, "_http_post", side_effect=_fake_post):
        client.generate(
            prompt="user",
            system_prompt="be concise",
            temperature=0.0,
        )
    assert captured["body"]["system"] == "be concise"


@pytest.mark.unit
def test_generate_includes_json_response_format() -> None:
    client = OllamaClient()
    captured: dict = {}

    def _fake_post(path: str, body: dict, *, timeout: float) -> str:
        captured["body"] = body
        return json.dumps({"response": '{"items":[]}'})

    with patch.object(client, "_http_post", side_effect=_fake_post):
        out = client.generate(
            prompt="user",
            temperature=0.0,
            response_format="json",
        )
    assert out == '{"items":[]}'
    assert captured["body"]["format"] == "json"


@pytest.mark.unit
def test_generate_rejects_unknown_response_format() -> None:
    client = OllamaClient()
    with pytest.raises(LLMConfigurationError, match="response_format"):
        client.generate(prompt="user", temperature=0.0, response_format="xml")


@pytest.mark.unit
@pytest.mark.parametrize("temperature", [-0.1, 2.1])
def test_generate_rejects_out_of_range_temperature(temperature: float) -> None:
    client = OllamaClient()
    with pytest.raises(LLMConfigurationError, match="temperature"):
        client.generate(prompt="user", temperature=temperature)


@pytest.mark.unit
def test_constructor_rejects_empty_base_url() -> None:
    with pytest.raises(LLMConfigurationError, match="base_url"):
        OllamaClient(base_url="   ")


@pytest.mark.unit
def test_constructor_rejects_non_http_scheme() -> None:
    with pytest.raises(LLMConfigurationError, match="http or https"):
        OllamaClient(base_url="ftp://localhost:11434")


@pytest.mark.unit
def test_constructor_rejects_non_positive_request_timeout() -> None:
    with pytest.raises(LLMConfigurationError, match="request_timeout"):
        OllamaClient(request_timeout=0)


@pytest.mark.unit
def test_constructor_rejects_non_positive_availability_timeout() -> None:
    with pytest.raises(LLMConfigurationError, match="availability_timeout"):
        OllamaClient(availability_timeout=-1)


@pytest.mark.unit
def test_constructor_rejects_non_positive_max_output_tokens() -> None:
    with pytest.raises(LLMConfigurationError, match="max_output_tokens"):
        OllamaClient(max_output_tokens=0)


@pytest.mark.unit
def test_build_ollama_client_defaults_and_normalizes_base_url() -> None:
    client = build_ollama_client(
        model="qwen3:8b",
        seed=7,
        request_timeout=30.0,
        availability_timeout=5.0,
    )
    assert client.base_url == DEFAULT_OLLAMA_BASE_URL
    assert client.model == "qwen3:8b"

    with_slash = build_ollama_client(
        model="qwen3:8b",
        seed=7,
        request_timeout=30.0,
        availability_timeout=5.0,
        base_url="http://remote:11434/",
    )
    assert with_slash.base_url == "http://remote:11434"


@pytest.mark.unit
def test_is_available_caches_tags_payload() -> None:
    client = OllamaClient()
    tags = {"models": [{"name": "qwen3:8b"}]}
    assert client.tags_cache is None
    with patch.object(client, "_http_get", return_value=json.dumps(tags)):
        assert client.is_available() is True
    assert client.tags_cache == tags


@pytest.mark.unit
def test_generate_rejects_json_array_body() -> None:
    client = OllamaClient()
    with patch.object(client, "_http_post", return_value="[1, 2]"):
        with pytest.raises(LLMResponseError, match="must be an object"):
            client.generate(prompt="hi", temperature=0.0)


@pytest.mark.unit
def test_is_model_not_found_body_matrix() -> None:
    assert _is_model_not_found_body("", "qwen3:8b") is False
    assert _is_model_not_found_body("   ", "qwen3:8b") is False
    # Generic 'model not found' text matches even without the model name.
    assert _is_model_not_found_body('{"error":"model was not found"}', "other") is True
    assert _is_model_not_found_body('{"error":"endpoint missing"}', "qwen3:8b") is False


@pytest.mark.unit
def test_transport_http_post_maps_404_model_body_via_urlopen() -> None:
    """End-to-end wrap path: urlopen HTTPError -> _wrap_network_error -> typed error."""
    client = OllamaClient(model="missing:1b")
    err = urllib.error.HTTPError(
        url="http://localhost:11434/api/generate",
        code=404,
        msg="Not Found",
        hdrs=None,
        fp=io.BytesIO(b'{"error":"model \'missing:1b\' not found"}'),
    )
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(LLMModelMissingError):
            client.generate(prompt="hi", temperature=0.0)


@pytest.mark.unit
def test_transport_http_get_success_via_urlopen() -> None:
    client = OllamaClient()

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"models": []}'

    with patch("urllib.request.urlopen", return_value=_Resp()):
        assert client.is_available() is True


@pytest.mark.unit
def test_transport_urlopen_connection_refused_maps_to_unavailable() -> None:
    client = OllamaClient()
    refused = urllib.error.URLError(ConnectionRefusedError())
    with patch("urllib.request.urlopen", side_effect=refused):
        with pytest.raises(LLMUnavailableError):
            client.generate(prompt="hi", temperature=0.0)


@pytest.mark.unit
def test_transport_urlopen_generic_oserror_reason_maps_to_unavailable() -> None:
    client = OllamaClient()
    err = urllib.error.URLError(OSError("network unreachable"))
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(LLMUnavailableError):
            client.generate(prompt="hi", temperature=0.0)


@pytest.mark.unit
def test_transport_raw_socket_timeout_maps_to_timeout() -> None:
    client = OllamaClient()
    with patch("urllib.request.urlopen", side_effect=socket.timeout("timed out")):
        with pytest.raises(LLMTimeoutError):
            client.generate(prompt="hi", temperature=0.0)


@pytest.mark.unit
def test_transport_connection_error_maps_to_unavailable() -> None:
    client = OllamaClient()
    with patch("urllib.request.urlopen", side_effect=ConnectionResetError("reset")):
        with pytest.raises(LLMUnavailableError):
            client.generate(prompt="hi", temperature=0.0)


@pytest.mark.unit
def test_read_http_error_body_swallows_read_failure() -> None:
    from transcriptx.core.llm.ollama_client import _read_http_error_body

    class _Broken:
        def read(self):
            raise OSError("cannot read")

    assert _read_http_error_body(_Broken()) == ""  # type: ignore[arg-type]
