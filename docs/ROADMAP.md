Type: PRODUCT
Authority: self

# TranscriptX Roadmap

**Current version:** see [pyproject.toml](../pyproject.toml) (package version).

**Product definition:** [PRODUCT.md](PRODUCT.md)  
**Programme plan (0.9.x → 1.0):** [pre_release_roadmap_1_0.md](dev/pre_release_roadmap_1_0.md)  
**Decision foundation:** [stocktake_2026-07-17.md](dev/stocktake_2026-07-17.md)

**North star:** a credible **1.0** local-first transcript analysis workbench governed by release evidence and explicit severity rules — not feature count or fixed patch assignments.

> **Status legend:** [ ] planned · [x] done · [~] in progress

---

## Current state

- Streamlit GUI + typed Python API; managed import; file-backed storage/sidecars
- Broad analysis module set (language, speakers, interactions, emotion, voice, groups, optional Ollama)
- Contracts for storage, run outcomes, outputs, and public surfaces
- Package on a **0.9.x** stabilisation track toward 1.0

Install honesty: runtime markers are **`core` | `full`** only; Streamlit is the separate **`[web]`** extra. Transcription remains external, with in-app **command-generation** handoff shipped in **0.9.4**. Sphinx hosted-docs revive + harden scaffolds shipped in **0.9.5**. Guided/Full + demo + onboarding checklist were trialled in **0.9.6** and later **removed** (prefer docs + clear GUI). Automatable harden + public surfaces (website, trust drafts, audit judgements, release-ops) shipped in **0.9.7**.

---

## 0.9.x programme (flexible themes)

Prefer thematic workstreams over fixed patch IDs. Cut releases around coherent, tested increments.

| Theme | Focus | Status |
|-------|--------|--------|
| Pre-pre-release | Stabilisation ahead of the 1.0 programme | **0.9.0** shipped |
| Hygiene + product docs | Phase 0A/0B inventories, archive, PRODUCT/README/ROADMAP | **0.9.1** shipped |
| Planning stubs + schema inventory | Phase 0B stubs; schema-epoch inventory signed off (integer `1`) | **0.9.2** |
| Schema epoch | Public schema epoch + compatibility removal; data-epoch transition UX; module-id hygiene | **0.9.3** |
| Install + transcription | Install-profile audit; Transcribe command generation; corpus docs | **0.9.4** |
| Hosted docs + harden scaffolds | Sphinx revive; hygiene strict subset; quality-audit scaffold; draft model-licence matrix | **0.9.5** |
| Modes + demo (trial) | Guided / Full + demo + onboarding checklist — **trialled then removed** (docs + clear GUI) | **0.9.6** (removed later) |
| Harden + public surfaces (automatable) | Audit judgements draft; perf recipe; trust drafts + AI labelling + NOTICE; website + Pages; release-ops; Data/Explorer redirects removed | **0.9.7** |
| Hygiene + honesty + human-pass prep | Epoch/deps cleanup; BERTopic-out-of-base; Balanced emotion honesty; known-limitations; acceptance kits | **0.9.8** |
| Maintainer acceptance | Manual acceptance + a11y/browser; severity-justified fixes | **in progress** |
| Overview / results presentation | Organisation & presentation (Actions/Highlights/Analysis, etc.) — [overview_presentation_0_9_9.md](dev/overview_presentation_0_9_9.md) | **0.9.9** (after maintainer; before unfamiliar-user) |
| Unfamiliar-user → RC | Clean-room validation; clean-env soak; owner Hub-card / RTD slug; Large-library soak | next (pre-RC) |

**Module freeze:** no new analysis modules in 0.9.x unless required to complete or repair the 1.0 journey. Backlog: [analysis_module_backlog_2026-07-17.md](dev/analysis_module_backlog_2026-07-17.md).

---

## 1.0 gate

Mandatory themes (detail in the programme plan):

- Unfamiliar-user clean-room validation — [unfamiliar_user_validation_1_0.md](dev/unfamiliar_user_validation_1_0.md)
- Release severity triage — [release_severity_triage_1_0.md](dev/release_severity_triage_1_0.md)
- Performance/resource envelopes — [performance_envelopes_1_0.md](dev/performance_envelopes_1_0.md)
- Trust / privacy / model-governance — [trust_privacy_model_governance_1_0.md](dev/trust_privacy_model_governance_1_0.md)
- Release ops and support — [release_ops_support_1_0.md](dev/release_ops_support_1_0.md); governance evidence on an exact clean commit
- Schema epoch inventory (before reset) — [schema_epoch_inventory.md](dev/schema_epoch_inventory.md)
- Usable hosted documentation and a credible public landing (may be modest) — website + Pages landed in **0.9.7**; RTD project go-live still owner-gated

Not required: every backlog feature, PyPI, hosted SaaS, built-in transcription, highly polished website.

---

## 1.1 – 1.x (early post-1.0)

Prefer a short **corrections** wave, a **deeper performance** wave, and an **Insights / analysis quality** wave soon after 1.0, then other 1.x themes as capacity allows.

- **Corrections strengthen (early 1.x wave)** — Corrections Studio is usable for 1.0 but results are **mixed**; do not treat it as finished. Dedicated wave:

  - Free-read the transcript and propose corrections at **word level** (not only current studio flows)
  - Prefer building word-level propose/apply into the **Transcript viewer** page (read → select word/span → propose correction) so correction is part of reading, not a separate dead-end
  - Keep Corrections Studio as the batch / review surface or fold it into viewer workflows after design
  - Honesty: mixed auto/assist quality must stay labelled; no silent overwrite of canonical text without clear apply/review

- **Deeper performance features (early 1.x wave)** — beyond 1.0 resource envelopes: help users plan and choose runs on *their* machine. Examples:

  - Realistic **time estimates** for analysis runs given detected hardware (CPU/GPU/memory, install profile)
  - **Smarter model recommendations** (which backend/size/settings fit this hardware and workload without over-promising)
  - Keep estimates labelled as guidance; do not block runs on uncertain forecasts

- **Insights & analysis enhance (early 1.x wave)** — Insights (and related analysis presentation) work for 1.0; do not freeze quality here. Dedicated wave:

  - Stronger **deterministic** outputs (clearer, more useful non-LLM / hybrid insights; less noise)
  - Reassess **GUI layout** for Insights and analysis result surfaces (hierarchy, scannability, what to show first)
  - Align with Overview presentation polish from **0.9.9** where patterns overlap; keep LLM insights honestly labelled
  - Revisit module-level insight eligibility / empty states so partial runs stay trustworthy

- Elaborate guided coach-mark tour (if needed)
- Large bundled completed demo runs (if risky at 1.0)
- Archive taxonomy refinements; aesthetic polish
- Specialist convenience and non-supported configurations
- **Broader local transcription command generation** — Transcribe Audio already generates copyable host commands for **whispermlx** / **whispermlx-missing** (Apple **MLX**, macOS / Apple Silicon), a WhisperX Docker recipe, and **jhj0517/Whisper-WebUI** Gradio deploy (SRT/VTT → import). Extend further for other Whisper stacks/platforms (e.g. more CUDA Linux / CPU-only CLIs) as needed, still copy/run-on-host only (no in-container MLX; no built-in orchestration — that stays deferred). Keep import as the GUI admission gate.
- **Transcript tagging** — library visibility / kind labels so users can surface certain transcripts (e.g. `meeting`, `voice note`, `lone speaker` for one-sided phone recordings). Tags are organisation metadata, not an analysis module.

  **Design before build — interaction with Groups:** tags and groups must stay distinct. Tags find/filter/surface individual transcripts; Groups are analysis cohorts for cross-session runs. Tagging must not create or imply group membership. Tags may act as **filters** in the group member picker, but must not auto-materialise a Group without an explicit user action. Decide whether “more visible” means facet filters, optional pin/favourite, or both — without overlapping Groups as the named-collection surface. Kind tags like `lone speaker` may later feed soft suitability hints (e.g. interaction modules), but must remain optional metadata, not silent default changes. Prefer transcript-local / library storage; keep tags out of group run schemas unless a deliberate filter snapshot is needed.

## 1.2 – audio / transcript merge (product decision)

Recorder devices often cut long sessions into chunks. Today:

- Host helper `scripts/audio_merge.py` concatenates parts → one MP3 (ffmpeg; documented in [transcription.md](runtime/transcription.md))
- `scripts/audio_preprocess.py` remains a separate pre-transcribe helper
- GUI merge/preprocess pages were removed (not core); Library/serial-group copy still points people at the merge script **before** transcription
- Manual “merge audio first, then transcribe/import” is a real pain for the personal-recording workflow

**Desired direction (design before build):** a simple **inline merge** in the product surface that:

1. Merges the **audio** parts in order into one managed recording, and
2. Optionally / correspondingly **stitches transcripts** (timestamp rebase, segment continuity, canonical + sidecars) when parts were already transcribed separately

**Why this is hard (expect a real design spike):** ordered part selection UX; ffmpeg/path honesty under Docker vs host; backup/overwrite policy; partial failure; matching audio duration to transcript times; speaker-id continuity across parts; managed-library admission for the merged artifact; whether merge happens pre-transcription only, post-transcription only, or both. Do not ship a half-merge that corrupts library identity.

**1.2 decision fork:**

- **Invest** — first-class merge (audio ± transcript stitch) as a supported library/import workflow; keep or fold the scripts into that path
- **Defer / remove** — if usage stays niche, delete the helpers and keep “merge outside TranscriptX” as the documented escape hatch

Until that decision: helpers stay **non-core** (not GUI nav / not public surfaces). Not a 1.0 gate; not a casual 1.1 polish item.

---

## 1.5 – DB backing (local analytics layer)

1.0 stays **file-backed** (managed library + sidecars). **1.5** is the first deliberate DB wave: a **local** query/analytics layer so longitudinal and cross-session views stop paying full-scan / ad-hoc JSON costs — without abandoning local-first or turning TranscriptX into a hosted multi-tenant product.

**Desired direction (design before build):**

- Start with **SQLite** (or equivalent embedded) as an **optional / derived** analytics store, not a second source of truth for canonical transcripts
- First product slice: **speaker-profile analytics views** and related B5 remainder (DB views; group gallery keyed by `profile_id`) — see [analysis_module_backlog_2026-07-17.md](dev/analysis_module_backlog_2026-07-17.md)
- Keep file/sidecar layout as the durable library contract; DB is rebuildable from files (or explicitly journalled) so wipe/rebuild stays honest
- Define sync/invalidation on import, profile edits, run finalize, and wipe paths before expanding beyond Speakers

**Out of scope for 1.5 unless redesign says otherwise:** remote Postgres/SaaS, multi-user auth, replacing the entire managed-file library with ORM rows, or making SQLite mandatory on day one of 1.0.

**1.5 decision fork:**

- **Invest** — ship Speakers (then Groups) analytics on SQLite views with clear rebuild/migration UX; document file = durable, DB = query cache/index
- **Narrow** — only indexes needed for Speakers charts; leave broader library search/file stores as-is until a later 1.x cut
- **Defer again** — if file-backed scale stays acceptable, keep SQLite off the default path and leave this theme parked

Not a 1.0 gate; not a casual 1.1 polish item. Depends on post-1.0 capacity after corrections / performance / merge decisions.

---

## 2.0 vision

Personal audio intelligence companion: personal recordings, voice-note workflows, deeper conversational analytics, stronger local AI — still local-first and modular.

---

## Non-near-term / deferred

- Built-in or orchestrated transcription engine
- Multilingual routing beyond a small reliable subset
- B4 ConvoKit-family methods as product defaults
- Mode systems that duplicate page logic
- Elaborate interactive website effects
- Broader “everything in the DB” library migration (beyond the 1.5 analytics layer)

Historical sprint dumps: [sprint_archive.md](archive/plans/sprint_archive.md) (archived).

---

## Engineering backlogs

- [analysis_module_backlog_2026-07-17.md](dev/analysis_module_backlog_2026-07-17.md)
- [DEV_INDEX.md](DEV_INDEX.md) · [archive/ARCHIVE_INDEX.md](archive/ARCHIVE_INDEX.md)
- [release_governance.md](dev/release_governance.md)
- [release_severity_triage_1_0.md](dev/release_severity_triage_1_0.md)
- Phase 0B planning stubs: [docs_architecture_1_0.md](dev/docs_architecture_1_0.md), [install_profiles_matrix.md](dev/install_profiles_matrix.md), [manual_acceptance_1_0.md](dev/manual_acceptance_1_0.md), [analysis_quality_audit.md](dev/analysis_quality_audit.md) (Guided/demo design stubs retired after trial)
