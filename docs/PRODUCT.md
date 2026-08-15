Type: PRODUCT
Authority: self

# TranscriptX product definition

**One sentence:** TranscriptX is a local-first personal transcript analysis workbench for people who want to think with transcripts.

## Promise

Import and organise transcripts; explore language, themes, speakers, interactions, emotion, voice and conversational dynamics; use structured analyses and local AI to find useful patterns; compare over time; inspect and export machine-readable results — while retaining local control of source material and outputs.

## Audience

**Primary:** any thoughtful person who already has (or can obtain) transcripts and wants to explore them seriously — meetings, interviews, notes, longitudinal personal recordings, and similar corpora. The 1.0 bar is that an unfamiliar user can complete the core journey without undocumented developer knowledge (see Boundaries).

**Emerging:** researchers and analysts who need trustworthy structured outputs. They care especially about:

| Concern | Meaning in TranscriptX |
|---------|------------------------|
| **Contracts** | Stable, documented rules for storage layout, run outcomes, artifact shapes, and schemas — so files and statuses mean the same thing tomorrow as today. Users configure analyses *within* these rules; they do not redefine them in Settings. See [CONTRACT_INDEX.md](CONTRACT_INDEX.md). |
| **Provenance** | Traceability of results: which transcript, settings, module versions, models, and pipeline steps produced an artifact. |
| **Reproducibility** | Ability to re-run (or explain) an analysis with known inputs and effective config, and to compare structured exports across sessions. |

**Positioning:** serve that emerging audience by keeping contracts, provenance, and exportable structure first-class — **without** framing 1.0 as specialist-only research software. Approachability and a clear GUI remain mandatory; research-grade structure is a product strength, not a gate that excludes general users.

**Not the primary job for 1.0:** replacing a transcription engine, meeting bot, CRM coach, or hosted team SaaS. Those sit upstream or adjacent — see [comparison.md](comparison.md).

## Surfaces

| Role | Surface |
|------|---------|
| Primary | Streamlit GUI (`transcriptx` / `python -m transcriptx.web`) |
| Secondary | Typed Python API (`transcriptx.app.workflows`, managed import) |
| Transcription | External for **1.0** (in-app **command-generation** handoff). Optional local in-app STT is a **1.x** theme — see [ROADMAP.md](ROADMAP.md) |
| Operational | Docker Compose; modest `website/` (GitHub Pages); hosted docs pending RTD go-live |

First-run experience relies on **task documentation** (including [five workflow walkthroughs](workflows/index.md)) and a **clear, complete GUI** — not Guided/Full presentation modes, in-app checklists, or a bundled demo project (those were trialled in **0.9.6** and removed; see [pre_release_roadmap_1_0.md](dev/pre_release_roadmap_1_0.md) §16). Surfaces: [public surfaces](public_surfaces.md).

## AI position

First-class, optional (Ollama today). Deterministic/statistical, model-based, and LLM interpretation are complementary; label them honestly. Do not keep weak deterministic fallbacks merely to claim non-AI coverage.

## Local-first

Source material and analysis outputs stay on the user’s machine. There is no hosted SaaS analysis path in 1.0 scope. File-backed storage and sidecars are the default (see [STORAGE.md](runtime/STORAGE.md)).

Local-first and contracts reinforce each other: durable files you can inspect, export, and script against are the unit of trust — not a remote black-box session.

## Long-term vision

Evolve toward a **personal audio intelligence companion**: personal recordings, voice-note workflows, optional **local in-app transcription**, deeper conversational analytics, and stronger local AI — still local-first and modular. Post-1.0 themes (playback, capture/STT, installable shell, analytics DB) live in [ROADMAP.md](ROADMAP.md).

## Boundaries (1.0)

**In scope for 1.0 credibility:** install → import/build a useful corpus, run appropriate analysis, understand results, recover from failures, and export artifacts — validated by an unfamiliar-user clean-room round.

**Not required for 1.0:** every backlog module, PyPI publication, hosted SaaS, built-in transcription engine, PWA, or a highly polished website.

## Governing docs

- Programme plan: [pre_release_roadmap_1_0.md](dev/pre_release_roadmap_1_0.md)
- Outcome roadmap: [ROADMAP.md](ROADMAP.md)
- Support policy: [public_surfaces.md](public_surfaces.md)
- Comparison (public): [comparison.md](comparison.md)
- Contracts map: [CONTRACT_INDEX.md](CONTRACT_INDEX.md)
- Navigation: [USER_INDEX.md](USER_INDEX.md) · [DEV_INDEX.md](DEV_INDEX.md)
