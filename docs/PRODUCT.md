Type: PRODUCT
Authority: self

# TranscriptX product definition

**One sentence:** TranscriptX is a local-first personal transcript analysis workbench for people who want to think with transcripts.

## Promise

Import and organise transcripts; explore language, themes, speakers, interactions, emotion, voice and conversational dynamics; use structured analyses and local AI to find useful patterns; compare over time; inspect and export machine-readable results — while retaining local control of source material and outputs.

## Audience

**Primary:** any thoughtful person who already has (or can obtain) transcripts and wants to explore them seriously — meetings, interviews, notes, longitudinal personal recordings, and similar corpora. The standing bar is that an unfamiliar user can complete the core journey without undocumented developer knowledge (see Boundaries).

**Emerging:** researchers and analysts who need trustworthy structured outputs. They care especially about:

| Concern | Meaning in TranscriptX |
|---------|------------------------|
| **Contracts** | Stable, documented rules for storage layout, run outcomes, artifact shapes, and schemas — so files and statuses mean the same thing tomorrow as today. Users configure analyses *within* these rules; they do not redefine them in Settings. See [CONTRACT_INDEX.md](CONTRACT_INDEX.md). |
| **Provenance** | Traceability of results: which transcript, settings, module versions, models, and pipeline steps produced an artifact. |
| **Reproducibility** | Ability to re-run (or explain) an analysis with known inputs and effective config, and to compare structured exports across sessions. |

**Positioning:** keep contracts, provenance, and exportable structure first-class — **without** framing the product as specialist-only research software. Approachability and a clear GUI remain mandatory; research-grade structure is a product strength, not a gate that excludes general users.

**Not the primary job:** replacing a transcription engine, meeting bot, CRM coach, or hosted team SaaS. Those sit upstream or adjacent — see [comparison.md](comparison.md).

## Surfaces

| Role | Surface |
|------|---------|
| Primary | Streamlit GUI (`transcriptx` / `python -m transcriptx.web`) |
| Secondary | Typed Python API (`transcriptx.app.workflows`, managed import) |
| Transcription | External for now (in-app **command-generation** handoff). Optional local in-app STT is a roadmap theme — see [ROADMAP.md](ROADMAP.md) |
| Operational | Docker Compose; modest `website/` (GitHub Pages); hosted docs pending RTD go-live |

First-run experience relies on **task documentation** (including [five workflow walkthroughs](workflows/index.md)) and a **clear, complete GUI** — not Guided/Full presentation modes, in-app checklists, or a bundled demo project (those were trialled and removed; see [pre_release_roadmap_1_0.md](dev/pre_release_roadmap_1_0.md) §16). Surfaces: [public surfaces](public_surfaces.md).

## AI position

First-class, optional (Ollama today). Deterministic/statistical, model-based, and LLM interpretation are complementary; label them honestly. Do not keep weak deterministic fallbacks merely to claim non-AI coverage.

## Local-first

Source material and analysis outputs stay on the user’s machine. There is no hosted SaaS analysis path in current scope. File-backed storage and sidecars are the default (see [STORAGE.md](runtime/STORAGE.md)).

Local-first and contracts reinforce each other: durable files you can inspect, export, and script against are the unit of trust — not a remote black-box session.

## Development mode

TranscriptX is in **continuous long-term development**: ship coherent increments, keep contracts honest, and deepen the workbench over time. Version numbers mark releases; they are not a product-positioning device. Living themes and deferred tracks live in [ROADMAP.md](ROADMAP.md). The pre-release programme note ([pre_release_roadmap_1_0.md](dev/pre_release_roadmap_1_0.md)) is historical context for the stabilisation arc, not the default planning lens.

## Long-term vision

Evolve toward a **personal audio intelligence companion**: personal recordings, voice-note workflows, optional **local in-app transcription**, deeper conversational analytics, and stronger local AI — still local-first and modular. Themes such as playback, capture/STT, installable shell, and analytics DB live in [ROADMAP.md](ROADMAP.md).

## Boundaries

**Standing credibility bar:** install → import/build a useful corpus, run appropriate analysis, understand results, recover from failures, and export artifacts — preferably validated with unfamiliar-user feedback, not only maintainer testing.

**Explicitly out of scope unless the roadmap says otherwise:** hosted SaaS analysis, replacing upstream transcription/meeting tools, or treating “every backlog module” / polished marketing surfaces as release blockers.

## Governing docs

- Living roadmap: [ROADMAP.md](ROADMAP.md)
- Support policy: [public_surfaces.md](public_surfaces.md)
- Comparison (public): [comparison.md](comparison.md)
- Contracts map: [CONTRACT_INDEX.md](CONTRACT_INDEX.md)
- Navigation: [USER_INDEX.md](USER_INDEX.md) · [DEV_INDEX.md](DEV_INDEX.md)
- Historical stabilisation programme: [pre_release_roadmap_1_0.md](dev/pre_release_roadmap_1_0.md)
