# Optional LiteLLM sidecar

Theme **N** optional gateway. TranscriptX does **not** embed the LiteLLM SDK in the analysis image. Run this proxy on the host (or beside Compose), then point `llm.provider=openai_compatible` at it.

Ollama stays the default local path. There is **no multi-vendor catalog UI**.

## When to use this

- One `base_url` should reach several upstreams (OpenAI, Anthropic, vLLM, …).
- You already run LiteLLM elsewhere and want TranscriptX to speak Chat Completions to it.

If you only need a single OpenAI-compatible server (vLLM, llama.cpp, OpenAI itself), skip this recipe and set `llm.base_url` directly.

## Privacy

If the LiteLLM upstream is **not** loopback, **transcript text leaves this machine**. Settings labels that as Remote AI. A loopback proxy that forwards to the public internet is still a remote data flow at the upstream.

## Run

From this directory:

```bash
cp litellm.env.example .env   # edit keys; do not commit
docker compose -f docker-compose.litellm.yml --env-file .env up -d
```

Validate YAML without pulling:

```bash
docker compose -f docker-compose.litellm.yml config
```

Then in TranscriptX (env or Settings → Configuration):

```bash
export TRANSCRIPTX_LLM_ENABLED=1
export TRANSCRIPTX_LLM_PROVIDER=openai_compatible
export TRANSCRIPTX_LLM_BASE_URL=http://127.0.0.1:4000/v1
export TRANSCRIPTX_LLM_MODEL=default
export TRANSCRIPTX_LLM_API_KEY=sk-local   # LiteLLM master key
```

The bind is **127.0.0.1:4000** by default. Do not publish `0.0.0.0` unless you intend LAN access.

## What this is not

- Not added to root `docker-compose.yml` / `transcriptx:latest`.
- Not a replacement for Ollama on this machine.
- Not YouTube ingest, H6 streaming, or silent cloud LLM.

## Related

- [llm.md](../../runtime/llm.md)
- [trust_privacy_model_governance_1_0.md](../../dev/trust_privacy_model_governance_1_0.md)
- Client: `transcriptx.core.llm.openai_compatible_client`
