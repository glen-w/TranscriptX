Type: GUIDE
Authority: self

# Security Policy

TranscriptX is a **local-first, single-user beta**. The trust domain is the machine user who runs the process, plus the default loopback web bind.

## Reporting a vulnerability

Please use **[GitHub private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability)** on [glen-w/TranscriptX](https://github.com/glen-w/TranscriptX) (Security Advisories).

Do **not** open a public Issue for sensitive vulnerability details. Public Issues are appropriate only for **non-sensitive** security questions (for example clarifying local trust-domain assumptions).

## Trust model (summary)

- Default Docker Compose publishes the web UI on **`127.0.0.1:8501` only**.
- The process inside the container still listens on `0.0.0.0` so the published host port can reach it.
- Setting `TRANSCRIPTX_BIND_HOST=0.0.0.0` exposes the UI on the LAN **without authentication**.
- LAN exposure grants unauthenticated access to **transcripts**, **generated artefacts**, **configuration-visible operations**, and **destructive cleanup** actions available in the UI.

## Related surfaces

- Model / weight downloads and third-party ToS (Hugging Face, pyannote): see runtime docs under `docs/runtime/`.
- Optional local LLM (Ollama): see `docs/runtime/llm.md` and corrections LLM docs.
- Dependency CVE policy and waivers: `docs/dev/dependency_audit.md`.
