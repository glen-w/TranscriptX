Type: PRODUCT
Authority: self

# TranscriptX product definition

**One sentence:** TranscriptX is a local-first personal transcript analysis workbench for people who want to think with transcripts.

## Promise

Import and organise transcripts; explore language, themes, speakers, interactions, emotion, voice and conversational dynamics; use structured analyses and local AI to find useful patterns; compare over time; inspect and export machine-readable results — while retaining local control of source material and outputs.

## Audience

Approachable to any thoughtful user with transcripts. Researchers and analysts are an important emerging audience (contracts, provenance, reproducibility) without positioning 1.0 solely as specialist research software.

## Surfaces

| Role | Surface |
|------|---------|
| Primary | Streamlit GUI (`transcriptx` / `python -m transcriptx.web`) |
| Secondary | Typed Python API (`transcriptx.app.workflows`, managed import) |
| Transcription | External to the analysis runtime, with an in-app **command-generation** handoff (not a built-in engine) |
| Operational | Docker Compose; modest `website/` (GitHub Pages); hosted docs pending RTD go-live |

Presentation modes (**Guided** / **Full controls**, aliases Simple/Advanced) are a config/presentation layer only — one execution system. An optional **demo project** (synthetic pack + one-click remove) ships for first-run exploration. See [public surfaces](public_surfaces.md), [ui_presentation_modes.md](dev/ui_presentation_modes.md), and [demo_project.md](dev/demo_project.md).

## AI position

First-class, optional (Ollama today). Deterministic/statistical, model-based, and LLM interpretation are complementary; label them honestly. Do not keep weak deterministic fallbacks merely to claim non-AI coverage.

## Local-first

Source material and analysis outputs stay on the user’s machine. There is no hosted SaaS analysis path in 1.0 scope. File-backed storage and sidecars are the default (see [STORAGE.md](runtime/STORAGE.md)).

## Boundaries (1.0)

**In scope for 1.0 credibility:** install → import/build a useful corpus → run appropriate analysis → understand results → recover from failures → export artifacts — validated by an unfamiliar-user clean-room round.

**Not required for 1.0:** every backlog module, PyPI publication, hosted SaaS, built-in transcription engine, or a highly polished website.

## Long-term vision

Evolve toward a **personal audio intelligence companion**: personal recordings, voice-note workflows, deeper conversational analytics, and stronger local AI — still local-first and modular.

## Governing docs

- Programme plan: [pre_release_roadmap_1_0.md](dev/pre_release_roadmap_1_0.md)
- Outcome roadmap: [ROADMAP.md](ROADMAP.md)
- Support policy: [public_surfaces.md](public_surfaces.md)
- Navigation: [USER_INDEX.md](USER_INDEX.md) · [DEV_INDEX.md](DEV_INDEX.md) · [CONTRACT_INDEX.md](CONTRACT_INDEX.md)
