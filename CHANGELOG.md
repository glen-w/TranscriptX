# Changelog

All notable changes to TranscriptX will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Deep Playwright GUI E2E coverage for Speaker Identification: speaker switching (Next/Prev/Jump), rename + Transcript confirm, ignore/unignore, and clip load/play with linked audio (`tests/e2e_gui/test_speaker_identification_deep.py`).
- Settings → Interface **action appearance**: icon, text, or both, with a global default and per-section override (`inherit`). Icon-only buttons keep the action name as a hover tooltip even when instructional ⓘ tips are off. Contract: [interface-menus.md](docs/contracts/interface-menus.md).
- Host **`whispermlx-missing --skip-serial`** (and `inbox-watch --skip-serial`) leaves Auto-merge serial parts / voice-note runs untranscribed so you merge first and transcribe the combined file.
- Run Analysis: **Cancel analysis** and **Skip module** stay available while a run is in progress (cooperative; the current module is abandoned, remaining work is not started on cancel).
- Playwright **GUI E2E** expanded to **ten key flows** under `tests/e2e_gui/` (`make test-gui-e2e`): workflows 1–5 plus Charts, Groups, Corrections (Correct mode), Rename Transcript, and Speakers.
- Workflow walkthroughs expanded to ten guides under [docs/workflows/](docs/workflows/index.md); root [README](README.md) lists the ten key GUI workflows.

### Changed

- [Identify and name speakers](docs/workflows/speaker-identification.md) walkthrough expanded for switch / clip / ignore / rename flows; media promoted to `speaker-identification-*` filenames (legacy `speaker-trust-*` retained).
- Auto-merge groups start **unchecked**, with **Select all** / **Select none**. **Don't suggest again** persists a false match in `{config_dir}/audio_merge_dismissed.json` (Hide remains session-only). `whispermlx-missing --skip-serial` does not skip dismissed groups.
- Comparison page: added [nanosamur.ai](https://nanosamur.ai) as a complementary org-grade self-hosted STT upstream (not an analysis substitute).
- Security pins: `cryptography` 48.0.1 → 50.0.0 and `nltk` 3.9.4 → 3.10.3 (fixable pip-audit findings on the clean-env wheel gate).
- Docs surfaces aligned: Sphinx [docs/index.md](docs/index.md) toctrees match [USER_INDEX](docs/USER_INDEX.md) (backup, corrections viewer/karaoke/LLM, recipes, STORAGE under Reference); PRODUCT/website/inventory say **ten** workflows; public series badge **0.9.9.5**; website install snippet includes `.env` / `HOST_RECORDINGS_DIR`.

### Fixed

- Auto-merge / recordings discovery accept **Opus** (`.opus`) so WhatsApp Desktop voice-note bursts appear in Tools → Auto-merge (ffmpeg/pydub already decode them).
- Managed admit replaces marker-less library JSON (raw WhisperX, including vendor NaNs) instead of failing mid-sidecar-repair; Speakers/Run pickers omit library paths without an import sidecar; `inbox-watch` / `whispermlx-missing` refuse writing into the managed library root (require `…/originals`).
- `whispermlx-missing` skips stems that already have JSON in the parent library root, as `foo (N).json` archives, or as a sidecar next to the MP3 — not only files inside `--transcripts` (`originals/`).
- `inbox-watch` audio convert: pass `-f mp3` so ffmpeg 8+ can mux to a `.mp3.partial` temp file (it no longer infers MP3 from that extension). Terminal feedback mirrors analysis Review / Run summary (`[i/n]` progress, elapsed times, streamed ffmpeg stats); Sphinx guide covers the UX under [transcription.md](docs/runtime/transcription.md#terminal-feedback) and links it from [directory_watcher.md](docs/runtime/directory_watcher.md).

## [0.9.9.5] - 2026-08-15

Interim cut of the post-**0.9.9** wave before unfamiliar-user validation. Programme narrative: [post_0_9_9_shipped_overview.md](docs/dev/post_0_9_9_shipped_overview.md); checklist: [pre_release_roadmap_1_0.md](docs/dev/pre_release_roadmap_1_0.md).

### Added

- Full-workspace **backup / verify / replace-restore** (Settings → Storage + `scripts/workspace_backup.py`); guides: [backup_and_restore.md](docs/backup_and_restore.md), [workspace-backup.md](docs/contracts/workspace-backup.md).
- Analysis **unnamed-speaker ungate**: named speakers required by default; global `analysis.allow_unnamed_speakers` and per-run flag treat diarized labels as valid speakers when enabled.
- Playwright **GUI E2E** lane (`tests/e2e_gui/`, `make test-gui-e2e`) for workflows 1–3; complementary to AppTest (not a PR gate).
- GitHub Actions **nightly** workflow (`.github/workflows/nightly.yml`): scheduled + manual `make test-integration-core`.
- CI **lint** job: ruff critical/unused gate on `src/transcriptx` (`E9,F63,F7,F82,F401,F841`).
- Audio **Merge** source profiles (`CONFIG_DIR/audio_merge_profiles.json`): per-source day / time-gap sliders, custom regex profiles, and **Auto-merge selected groups**. Builtin defaults keep the 20-minute voice-note gap; users can retune (e.g. WhatsApp same day within 2 hours).
- Dashboard Builder **Edit** mode: select and ↑↓ reorder Overview/Insights blocks; save custom layouts in place. Charts Overview strip selector (checkboxes + order) under **Settings → Configuration**. Guides: [dashboard_builder.md](docs/dev/dashboard_builder.md), [settings.md](docs/runtime/settings.md).
- **System → Tools** hub: audio **Preprocessing** and **Merge** tabs restored under the renamed System sidebar section (formerly Settings), with dependency checks, guided assess/apply-suggested flow, serial-group one-click fill, and handoffs to Transcribe Audio. CLI scripts remain for automation.
- Dashboard Builder / layout presets: three curated built-ins — **Meeting follow-up** (`meeting_followup`), **Speakers** (`speaker_focus`), **Minimal** (`minimal`) — plus Schema overwrite confirmation, delete-custom, layout-id slug hardening, and param type checks. Guide: [docs/dev/dashboard_builder.md](docs/dev/dashboard_builder.md).
- **Theme B (corrections in the Transcript viewer):** Correct mode supports word/span propose, atomic accept-and-apply for the current candidate, and scoped corrected-sidecar writes without overwriting the managed original. Corrections Studio remains the batch/detector/LLM review surface (Start/Resume no longer auto-generates). Guide: [docs/runtime/corrections-viewer.md](docs/runtime/corrections-viewer.md).
- **Theme C (high-interaction workspaces):** shared `SpeakerIdActionService` (revisioned command/ack) used by legacy Speaker ID callbacks; non-blocking ClipService APIs (`cached_clip_status` / `get_cached_clip_bytes` / `enqueue_clip`); packaged Streamlit Components v2 `transcriptx-workspaces` Speaker ID surface (transcript-scoped keys, ClipTransport base64, prefetch budgets; **feature flag default-on**; missing package falls through to classic UI); Corrections revisioned command protocol on the studio page; PlaybackHost handoff for Theme D; Playwright browser harness; design docs under `docs/dev/theme_c_*.md`.
- **Workflow walkthroughs:** five outcome-focused Sphinx user guides under [docs/workflows/](docs/workflows/index.md) (import → speaker identification → investigate → optional local AI → export) with screenshots/GIFs and a shared planning-review fixture.
- Overview artifact ZIP export writes selection-scoped **`index.epub`** beside **`index.html`** when `ebooklib` is available (`[visualization]` / `[full]` / Docker `requirements.txt`). Guide: [docs/runtime/export.md](docs/runtime/export.md); limits: [docs/known_limitations.md](docs/known_limitations.md).
- Unit coverage for subprocess-isolated BERTopic fit helpers, raw config unwrap/validation messages, and export chart-prep / transcript-meta helpers.

### Changed

- CI `tests` / `tests-nlp` install `.[dev,web]` / `.[dev,nlp,web]` so Streamlit web modules collect under contracts/fast (fixes missing-`streamlit` collection failures).
- Dev extra includes `hypothesis` (fast-lane property tests); `tests/e2e_gui/helpers.py` soft-imports Playwright so Core+dev collection no longer hard-fails.
- Sphinx / Pages assemble keeps hosted docs current with `docs/` on every push.
- [PRODUCT.md](docs/PRODUCT.md) reframed for continuous long-term development alongside the 1.0 programme gate.
- Workflow walkthrough 2 renamed from “speaker trust” to [Identify and name speakers](docs/workflows/speaker-identification.md) — wording now emphasizes naming diarized speakers for readable transcripts, not analysis “trust”.
- Audio **Merge** concatenates only by default. Optional **Preprocess files while merging** checkbox (CLI `--preprocess`) applies current preprocessing defaults in the same pass; otherwise run Preprocessing separately. Serial detection and optional post-merge cleanup for messaging / field-recorder runs.
- Sidebar section **Settings** renamed to **System** (page keys unchanged: Settings, Tools, Profiles, Dashboard Builder, Diagnostics).
- Legacy bookmarks **Audio Prep** / **Audio Merge** redirect to **Tools** (Preprocessing / Merge tabs) instead of Transcribe Audio.
- Executive layout preset now tags Insights `section:` values and includes a Charts page for consistent section nav / Builder preview.
- Composition docs: layout envelope is schema_version **1** only (optional `section` on placements); preset catalog expanded in composition / web_blocks docs.
- Speaker ID CCv2 workspace feature flag defaults **on**; rollback with `TX_SPEAKER_ID_WORKSPACE_COMPONENT=0`. When `transcriptx-workspaces` is not installed, Speaker ID automatically uses the classic `@st.fragment` path. Legacy path retained until Phase 9 retirement criteria.

### Fixed

- Run Analysis **Batch** progress panel now keeps showing the current transcript (`N/M · name`) while nested module events update the bar and latest-event line.

## [0.9.9] - 2026-08-09

### Changed

- Cut **0.9.9** Overview / results presentation theme: Insights **Analysis** tab retirement (landed earlier in 0.9.8.7) plus export EPUB and batch progress honesty. Remaining Overview hierarchy polish and full Charts catalogue audit stay deferred for pre-unfamiliar-user follow-up ([overview_presentation_0_9_9.md](docs/dev/overview_presentation_0_9_9.md)).

## [0.9.8.9] - 2026-08-08

### Changed

- Record final Thorough stress-pass evidence for speaker-complete transcripts **and** qualifying groups (`qwen2.5:7b`, corpus wall **68.7 min**, 0 module failures) in the 1.0 performance envelope / pre-release roadmap, with scratch + private release-evidence mirrors.
- Capture BERTopic macOS deep-test / pre-release verification logs from the 2026-08-08 isolated-fit hardening follow-up.

## [0.9.8.8] - 2026-08-08

### Fixed

- BERTopic on macOS host Python: pin native thread env early and force UMAP/HDBSCAN single-thread backends (`n_jobs=1` / `core_dist_n_jobs=1`) to avoid OpenMP/Numba oversubscription SIGSEGVs during `fit_transform`.
- Run BERTopic fits in a subprocess (`transcriptx.core.utils.bertopic_fit`) so a residual native crash soft-fails the module instead of killing the parent pipeline; group aggregation uses the same isolation path.

### Changed

- Document macOS BERTopic mitigations in `docs/dev/bertopic_optional_module.md`; deepen unit coverage for thread-safe backends and isolated-fit soft-fail behavior.
- Record thorough `qwen2.5:7b` corpus timing notes in the 1.0 performance envelope / pre-release roadmap.

## [0.9.8.7] - 2026-08-07

### Changed

- Insights: **retired the "Analysis" section** from the section nav (Summary · Speakers · Actions · Highlights). Former Analysis blocks are redistributed rather than removed: keyphrases and content themes/ideas move to **Summary**; lexical diversity, epistemic markers, politeness, and style markers move to **Speakers** as speaker-comparison content. Charts and Artifacts remain unaffected sibling pages; per-block raw JSON/CSV provenance links stay reachable without a consolidated Analysis tab.
- `insights_contract` block now supports a `focus=content|style` placement param so the same underlying module can present themes/ideas (Summary) and style markers (Speakers) as two distinct, independently keyed placements.
- A stale `insights_section` session value of `"analysis"` (from a prior session) now remaps to `"summary"` instead of erroring.

### Fixed

- Web package version metadata (`transcriptx.web.__version__`) was left at `0.9.8.5` after the `0.9.8.6` release; resynced with the root package version.

## [0.9.8.6] - 2026-08-07

### Changed

- Run Analysis / Batch: **LLM setup** is shown only when the effective modules (or enabled group LLM synthesis) need a live LLM; non-LLM presets hide the section.
- Home: detailed statistics, sessions, and recent runs use lazy Streamlit expanders (`on_change="rerun"`) instead of toggles — sessions is its own top-level block, not nested under detailed statistics.
- [docs/ROADMAP.md](docs/ROADMAP.md): post-1.0 work regrouped by **theme** (A–M); added 1.x candidates for optional in-app STT (NVIDIA Parakeet/Canary + Whisper, CUDA/CPU, YouTube), directory watcher, karaoke-style playback, and PWA/installable shell — 1.0 stays BYO transcription.
- Analysis-module backlog and `.local` competitive inspiration marked **living / changeable**; STT/playback/PWA cross-linked to ROADMAP themes (not analysis-module non-goals).

### Fixed

- Run Analysis **Batch** target now shows the same live progress bar and recent logs as single/group runs (spinner-only was hiding per-module updates); stage starts clear a prior transcript's Completed banner mid-batch.
- Run Analysis / Batch: **Project default** Model preset now seeds the shared-model picker from global `llm.model` when `model_selection.shared_model` is empty (matching runtime resolution), and re-applies after an empty Ollama tags list so Run stays enabled without a forced re-select.
- LLM rating form on Transcript Summary (and other badge-row surfaces) no longer squeezes Submit/Cancel into a one-character-wide column; thumbs stay trailing, the form opens full-width below.
- Run Analysis progress no longer flips to Completed after the DAG’s last module (`wordclouds`) while finalize-phase `chart_descriptions` is still running; the panel stays on Finalizing with matching module totals until chart descriptions finish.

## [0.9.8.5] - 2026-08-04

### Added

- Transcribe Audio command generator + docs: **jhj0517/Whisper-WebUI** Docker/Gradio deploy option (SRT/VTT → Import Transcript); recipe under `docs/recipes/whisper-webui/` with ownership disclaimer, Apple Silicon CPU caveat, localhost bind, pinned image tag, removal, and tiny maintainer smoke obligation.
- Home light-summary caches and optional detailed statistics / recent-runs panels (faster first paint).
- Speaker Identification index cache and playback audio-resolve session cache with fingerprint validation.

### Changed

- Speaker Identification: workspace-fragment playback (no nested playback fragment), clearer warm-queue / cold-clip behaviour, and further naming/navigation hardening toward the pre-1.0 stop line.
- Sidebar session listing uses a lighter cached name list; file-service listing helpers support that path.
- Roadmap / pre-release notes: declare **Streamlit Components v2** high-interaction workspaces (Speaker ID / Corrections Studio) as a near-term 1.x experiment after the Speaker ID stop line—not a pre-1.0 rewrite.

### Fixed

- Playback panel resolves audio without sticky-caching missing paths; prefer body renderer inside outer fragments.

## [0.9.8.4] - 2026-07-26

### Changed
- Speaker Identification: fragment workspace, action-menu transcript handoff, per-path listing/segment caches, and clearer voice-suggestion rendering.
- Transcript picker caches: path-addressable summary/segment signatures instead of one all-paths cache entry.
- Roadmap: slot **0.9.9** Overview/results presentation polish after maintainer acceptance; expand **1.2** toward an inline audio±transcript merge decision (helpers remain non-core until then).
- Maintainer acceptance kit progress recorded; Transcribe → Import copy clarifies same-stem recording link in the mounted folder.

### Fixed
- Run-cleanup journal readers recover leftover schema-3 envelopes after epoch renumber (writers remain schema 1).
- Sidebar / Speakers picker path resolution for Docker-friendly discovery and identity navigation.

## [0.9.8.3] - 2026-07-26

### Removed
- Guided / Full controls presentation mode, Getting started checklist, and bundled demo project (Home/Settings CTAs, `transcriptx.demo`, `scripts/generate_demo_runs.py`). Trialled in **0.9.6**; decided against in favour of documentation and a clear complete GUI ([pre_release_roadmap_1_0.md](docs/dev/pre_release_roadmap_1_0.md) §16).

### Changed
- Transcribe Audio command generator: shared model option list; host-safe defaults for `whisperx.env` / `whispermlx-missing` when the app runs from a Docker/venv install path; clearer whispermlx-missing install docs.

### Fixed
- Voice Speakers UX: pre-epoch / corrupt `privacy.voice_settings.json` no longer crashes the panel; surfaces `privacy_settings_invalid` with replace-and-enable recovery.

## [0.9.8.2] - 2026-07-25

### Changed
- Remove Audio Pre-processing and Audio Merge from the GUI Tools nav (not core). Capability moved to helper scripts `scripts/audio_preprocess.py` and `scripts/audio_merge.py`; documented in transcription docs; **1.2** roadmap notes consider full removal.

## [0.9.8.1] - 2026-07-25

### Changed
- Guided mode on/off toggle on Home / Settings (off = Full controls); Settings subheader renamed from Presentation.

### Fixed
- Demo project install/remove/refresh always reruns and surfaces failures via a flash error after toggle sync (avoids sticky wrong toggle state).

## [0.9.8] - 2026-07-24

### Added
- User-facing [known limitations](docs/known_limitations.md); linked from README, USER_INDEX, and Sphinx.
- Executable maintainer acceptance runbook and unfamiliar-user validation run kit (execution remains after the tag).
- Retired public module/schema-id invariant tests; 0.9.7→current epoch-1 forward-compat open test.
- BERTopic base-install boundary packaging tests (stack not imported by catalogue load).

### Changed
- Move BERTopic stack (`bertopic` / `hdbscan` / `umap-learn`) out of base deps into `[bertopic]` (still in `[full]` / Docker `requirements.txt`) so clean core wheel installs avoid `llvmlite` host builds. See `docs/dev/bertopic_optional_module.md`.
- Balanced preset heavy allowlist: `semantic_similarity` only (experimental `fine_grained_emotion` / `contextual_emotion` off Guided defaults).
- Epoch-align Custom QA / action-items / semantic-similarity / journal / delegation tests and fixtures to sole live schema ids; strip retired `semantic_similarity_advanced` / `_v2` live lookups.
- Sphinx `release` uses package metadata with neutral `0.9.dev0` fallback (no stale patch hard-code).
- Native Mac MPS documented as supported-with-caveats; Docker CPU recommended; `TRANSCRIPTX_FORCE_CPU=1` actionable fallback.
- `clean_env_audit.sh` invokes `pip-audit` console script (not `python -m pip-audit`).
- Roadmap: **0.9.8** cut; next sequence maintainer pass → unfamiliar-user → RC.

### Fixed
- Custom QA committed-payload reader no longer routes epoch-1 artifacts through `validate_artifact_v2` solely because schema constants collided.
- Insights action-items caption no longer refers to a dual-writer “native v2” world.

## [0.9.7] - 2026-07-24

### Added
- Modest public `website/` landing + GitHub Pages workflow (Buy Me a Coffee placeholder).
- Release ops / support policy draft; GitHub Issue templates; root `NOTICE` draft for third-party models.
- Analysis-quality provisional judgements overlay; performance envelope sizes + measurement recipe.
- RTD go-live checklist (hostname still denylisted until owner slug).
- Local AI badges on Insights/Overview LLM surfaces; Overview badges deterministic summaries as `Deterministic`.
- Local AI badges on Charts LLM descriptions and Custom Questions block.
- Voice privacy user notice (`voice_privacy_notice.v2`) in Settings → Speakers.
- Maintainer `make perf-envelopes` / `scripts/release/perf_envelope_recipe.py` recipe printer.

### Changed
- Removed legacy GUI page aliases `Data` / `Explorer` (use Artifacts Preview / Browse).
- Trust / privacy governance drafts marked review-ready for owner sign-off.
- Align voice Pydantic `schema_id` Literals with epoch `transcriptx.*.v1` constants (privacy round-trip).
- Docs/roadmap: Guided/demo marked **shipped (0.9.6)** with human-acceptance residual; §20 owner judgements updated for UI copy + synthetic demo pack.

### Fixed
- Demo same-members group collision uses canonical group paths (not cwd-resolved relatives).
- Demo remove revalidates managed identity and takes per-run writer locks; `refresh_demo_project` recovers stale/partial installs.
- Home empty-library primary CTA for demo load; plan-coverage tests for guard, allowlist, collisions, symlink escape.
- Align layout preset `default.yaml` and speaker-profile Pydantic `schema_id` Literals with public schema epoch-1 (`schema_version: 1`, `transcriptx.*.v1`).
- Emotion-family / contagion characterisation fixtures use `transcriptx.contextual_emotion_result.v1` / `transcriptx.fine_grained_emotion_result.v1` (not pre-epoch prefixed ids).
- Epoch-aligned contract expects for run_results / dashboard / import / speaker-map / corrections-studio schema `1`; drop obsolete `semantic_similarity_advanced` from module UI groups; collect-ignore removed v1 semantic viz helpers.
## [0.9.6] - 2026-07-24

### Added
- **Guided / Full controls** presentation mode: atomic prefs, empty→Guided / existing→Full seed, sidebar visibility filter, Full-only unlock banner, Guided Settings tabs + curated config schema, Custom analysis read-only under Guided.
- **Demo project**: bundled synthetic pack (`demo__*`), transactional install/remove with ownership inventory + journal, deterministic placeholder runs, Home/Settings CTAs, `scripts/generate_demo_runs.py`.
- Lightweight **Getting started** onboarding checklist prefs (stable item IDs; dismissible).

### Changed
- Pre-release programme: Guided/demo cut ships as **0.9.6** (no longer deferred past 0.9.5).

## [0.9.5] - 2026-07-24

### Added
- Sphinx revive (`docs/conf.py`, MyST/Furo), `make docs`, CI `docs` job, and `.readthedocs.yml` scaffold (RTD hostname still denylisted until go-live).
- Maintainer `scripts/release/regen_module_docs.py` regenerates `docs/generated/modules.md` and analysis-quality audit scaffold rows from `MODULE_REGISTRY_ORDER`.
- Draft model/licence matrix in trust/privacy governance planning doc.
- Hygiene audit `--checks` subset; CI promotes root MD allowlist + archive banners to strict.
- Release unit tests for hygiene subset, generated module-catalog/scaffold drift, Sphinx scaffold wiring, and optional Sphinx HTML smoke.

### Changed
- Pre-release programme: Guided/demo/example datasets deferred past 0.9.5; hosted-docs + harden scaffolds are the current cut.
- `docs-clean` no longer deletes tracked `docs/generated/`.

Install-profile honesty and Transcribe Audio command-generation handoff.

### Added

- `[web]` optional extra owning Streamlit (GUI is not part of `[full]`).
- Parameterised Transcribe Audio **command generator** (copyable shell only; never executed from Streamlit) for whispermlx, whispermlx-missing, and WhisperX Docker.
- Install capability matrix and `speaker_match` / `web` verification cells.

### Changed

- Optional-dep install hints use editable `pip install -e '.[extra]'` from a git checkout (not PyPI).
- Runtime auto-install targets the underlying package name instead of `transcriptx[extra]` from PyPI.
- `transcriptx.sh` leaves CUDA visible by default; `TRANSCRIPTX_FORCE_CPU=1` opts into clearing `CUDA_VISIBLE_DEVICES`.
- Docker / `requirements.txt` includes `yake` and `keybert` for keyphrases parity with `[full]`.
- Transcription docs: non-technical corpus path, resume/dry-run/spaces, host vs Docker boundaries.

### Fixed

- Misleading PyPI-style install strings in voice/NLP/BERTopic/semantic-similarity hints and packaging tests.

## [0.9.3] - 2026-07-24

Public schema epoch-1 reset and compatibility removal.

### Added

- Data-root `schema_epoch.json` marker (`CURRENT_SCHEMA_EPOCH = 1`) with assess/ensure APIs.
- GUI preflight gate and typed remediation helpers (fresh data directory, transcript inventory/export, derived-state reset + report). Never auto-deletes; recordings and transcripts preserved by default.

### Changed

- Public persisted `schema_version` values → integer `1` only; public string IDs → `transcriptx.<domain>.v1`.
- Cleanup journal / result envelopes → epoch-1; layout dual-accept dropped; custom QA dual V1/V2 writer symbols collapsed to a single epoch-1 constant.
- Retired legacy `semantic_similarity` / `semantic_similarity_advanced`; renamed former `semantic_similarity_v2` package and public module id to `semantic_similarity`.
- Fixtures, goldens, and outcome/output contracts aligned to epoch-1.

### Removed

- Pre-public dual-accept / coerce paths for wiped schema generations (fail closed with remediation UX).

## [0.9.2] - 2026-07-24

Phase 0B planning stubs and schema-epoch inventory sign-off ahead of the public schema reset.

### Added

- Twelve Phase 0B planning stubs under `docs/dev/` (schema epoch inventory, install profiles, manual acceptance, analysis quality audit, docs architecture, UI presentation modes, demo project, performance envelopes, trust/privacy/model governance, release ops/support, unfamiliar-user validation, release severity triage).
- Human-approved [`docs/dev/schema_epoch_inventory.md`](docs/dev/schema_epoch_inventory.md): integer public schemas → `1` only (no dotted `.x`); retain/wipe decisions; transition UX; versioned module-id cleanup plan (`semantic_similarity_v2` → `semantic_similarity` after retiring legacy siblings).

### Changed

- Programme roadmap, ROADMAP, CONTRACT_INDEX, DEV_INDEX, release governance, stocktake, and analysis backlog aligned to stubs + freeze + capacity language.
- Locked decision: no `_vN` in public analysis module ids for 1.0; schema-epoch theme checklist includes module-id hygiene (implementation still open).

## [0.9.1] - 2026-07-24

Phase 0A/0B baseline: repository hygiene, documentation information architecture, and product-doc alignment on the 0.9.x → 1.0 programme.

### Added

- Documentation and script inventories (`docs/dev/documentation_inventory_1_0.md`, `docs/dev/script_inventory_1_0.md`).
- Curated navigation indexes: `docs/USER_INDEX.md`, `docs/DEV_INDEX.md`, tracked `docs/archive/` with archive banners.
- Authoritative short product definition (`docs/PRODUCT.md`).
- Local scratch convention (`.local/`) and `docs/dev/local_scratch.md`.
- Repo hygiene audit (`scripts/release/repo_hygiene_audit.py` + root markdown allowlist) in CI warn mode.
- Programme plan relocated to `docs/dev/pre_release_roadmap_1_0.md`.

### Changed

- README and `docs/ROADMAP.md` rewritten for the 1.0 north star; stocktake/backlog retargeted to 0.9.x stabilisation (module freeze).
- Install/transcription docs honesty: runtime markers `core`|`full` only; Docker smoke no longer oversold; `transcriptx.sh` CUDA caveat documented.
- Public surfaces note Guided/Full as presentation-only and transcription command generation as a GUI capability.
- Canonical script archive remains `archive/scripts/`; stale setup/Docker helpers removed; broken Sphinx builder archived.

### Removed

- Disposable root/setup helpers (`activate_env.sh`, `scripts/setup_env.sh`, misleading Docker cleanup/data-setup scripts, orphan assess README).

## [0.9.0] - 2026-07-24

Pre-pre-release. Stabilising ahead of the pre-release programme, targeting 1.0.

### Added

- Streamlit AppTest GUI acceptance lane (`make test-gui-acceptance`, marker `gui_acceptance`) with journey coverage and residual AppTest-blind checklist.
- Speakers page thin orchestration unit coverage.
- Pre-release roadmap for the path from 0.9 toward 1.0.

### Changed

- Group manifest listing sorts by name / `group_id` (stable, case-insensitive).
- Analysis preset help copy uses clearer paragraph breaks.
- Release governance recommends GUI acceptance + residual checklist notes at tag time.
- Docs/backlog alignment for post-1.0 optional citeable research methods (B4) and GUI test assessment.

## [0.8.1] - 2026-07-24

### Fixed

- Group `keyphrases` aggregation session rows now include `order_index` (row writer no longer skips the agg).
- `keyphrases_pooled` allowlisted on group chart_outcome so `keyphrases.phrases.global` can render.
- Project `config.json` (including saved custom questions / analysis presets) is hydrated into the live facade on web startup so Settings survive Docker recreate.

### Changed

- Docker Compose mounts `HOST_CONFIG_DIR` (default `./data/.transcriptx`) for durable project settings outside a wiped `./data` tree; document in `.env.example` / docker runtime notes.
- B16 documentation and ownership snapshots refreshed (runtime `keyphrases` guide, group contracts, install matrix, stocktake/backlog/ROADMAP).

### Added

- Packaging check that `[keyphrases]` extras are included in `[full]`.

## [0.8.0] - 2026-07-24

### Added

- **B14** cross-session concept drift / recurring motifs: `semantic_similarity_v2` schema `1.1.1` motif envelope (centroids, provenance, export status), hardened clustering, group centroid matching with transition `drift_score`, additive `motif_rows` + `semantic_similarity_pooled` (persisted on group runs), composite group charts ([`docs/groups/group_charts_semantic_motifs_contract.md`](docs/groups/group_charts_semantic_motifs_contract.md)).
- **B16** `keyphrases` module (noun-chunks / YAKE / KeyBERT) with optional `[keyphrases]` extra, group aggregation, wordcloud integration, and Insights extractor.
- LLM feedback v1 (collect-only): append-only local ratings for LLM analysis cards (`docs/contracts/llm_feedback_v1.md`).
- Speaker profile analytics packs: interactions/equity and sentiment across linked appearances, plus shared run-artifact join helpers.
- Topic-shift chapter title usability helpers and enrichment/keyword improvements for viewer chapters.
- Overview / run-summary badge for named analysis presets (Quick / Balanced / Thorough); Custom runs omit the badge.
- Extra offline coverage: voice bootstrap early paths, `llm_custom_qa` analyze_v2 helpers, locations-pack path fallbacks, geo utils.
- Voice enrol **Max confirmed links** operator setting (Settings → Storage → Local voice matching), stored in `operator.voice_settings.json` (default 40; survives privacy revoke).

### Fixed

- `llm_action_items` no longer drops otherwise-valid meeting extracts when local models omit `confidence`, add extra keys, use field/type aliases, or join quote spans with ellipses (mistral:latest canal-walk failure mode). Prompt v7; empty-extract runs also write a `.raw.txt` debug dump.

### Changed

- Speakers UI / accent / navigation polish; Docker Compose and image path hygiene for local runs.

## [0.7.5] - 2026-07-24

### Added

- Configurable analysis presets under **Settings → Analysis** (`analysis.ui_presets`): policy knobs plus optional module overrides for Quick / Balanced / Thorough, with defaults Quick = no LLM/no heavy, Balanced = `llm_summary` + heavy allowlist `semantic_similarity_v2`/`fine_grained_emotion`, Thorough = all suitable modules. Preset resolution also drops modules whose hard deps would reintroduce disallowed heavy/LLM modules via the DAG.
- Speaker profile **Locations** analytics pack from NER location mentions across linked appearances.
- Speaker voice match file residuals: accept query-evidence co-journal, eval harness, chunked merge transfer, Stage 9 disposable file index under `.cache/voice/indexes/`.
- NER `location_mentions_per_speaker` rich mention records (segment index + start) feeding the locations pack.

### Changed

- Run Analysis / Batch preset help copy points at Settings → Analysis; heavy-module counting treats registry `category` or `cost_tier` as heavy.
- Speakers voice UX / privacy defaults and contract docs updated for the residual voice match work.

## [0.7.4] - 2026-07-23

### Added

- Speakers voice match Phase 2 R2: local ECAPA fingerprints, suggested matches, consent/privacy wipe, bootstrap from confirmed links, shared project lock journaling, `[speaker_match]` extra, and contract coverage (`docs/contracts/speaker_profiles_voice_v1.md`).

### Changed

- Custom QA answered rows omit redundant Status captions in markdown/UI; storage Settings panel covers speaker-profile visibility and voice wipe controls.

## [0.7.3] - 2026-07-23

### Added

- Speakers Phase 1.6 profile analytics pack: typed Trends (headline + optional all-appearances) and Conversation partners from `AggregationSnapshot`, with shared freshness tokens, partial-availability timing, and contract/test coverage.

## [0.7.2] - 2026-07-23

### Added

- B13 speaker interaction graphs: durable `{base}_interaction_graph.json` + `.graphml` under `interactions/data/`, upgraded `interactions.network_graph.global` (seeded layout, equity-aware node sizes), empty-rerun stale artifact removal; design doc `docs/dev/wave_b13_interaction_graphs_2026-07-23.md`.
- Speaker profile avatars: optional photo on `speaker_profile.v1` (`avatar_relpath` / `avatar_sha256` / `avatar_content_type`), journalled set/clear, merge adopt/target-wins, integrity checks, fixed-size photo-or-initials Speakers chip.

## [0.7.1] - 2026-07-23

### Added

- Speakers Phase 1.5: authoritative `AggregationSnapshot`, dual headline/all over-time charts, directory top-N + Other activity chart, freeform profile `accent_color` (colour-wheel picker; unused palette colour auto-assigned on create), Speakers lifecycle UX (edit/unlink/link/relink/unarchive/fingerprint accept), Diagnostics speaker-ops recovery panel, and expanded integrity typing.
- Wave 2 lexicon linguistics (B6/B7): shared `lexicon_markers` kit plus `epistemic_markers` and `politeness` modules (EN lexicons, rates, group pooled charts, Insights/Overview extractors, runtime docs).
- Emotion family shared `classifier_inference` / `work_items` helpers with offline characterization fixtures.

### Changed

- Speaker profile mutations assert readable entities under the project lock; `relink` requires a live link (`link_existing_profile` for first link); destructive confirms bind expected link/owner/fingerprint; operation receipts carry full cache-invalidation metadata; speaking share is transcript-relative (unique-transcript denoms in date buckets).
- Lexical / contextual / fine-grained emotion modules route through the shared emotion-family work-item and classifier-inference helpers.

### Fixed

- Appearance flags use single-winner precedence (`collision` is not overwritten by `needs_review`); corrupt canonical/operation files surface as incomplete rather than silent skips.

## [0.7.0] - 2026-07-23

### Added

- Speaker profiles v1: longitudinal identity store under `speaker_profiles_dir` (default `data/speaker_profiles/`, override via `TRANSCRIPTX_SPEAKER_PROFILES_DIR`), Speakers directory/detail UI, create-and-name from speaker maps, backfill script, integrity/recovery, and contract docs.
- Settings → **Models** tab for Ollama refresh, model guidance, and Model preset create/overwrite/activate (moved off the Run Analysis form).

### Changed

- Run Analysis page configures one run: Analysis preset (Quick / Balanced / Thorough / Custom), compact custom questions, collapsed LLM setup, and a sticky Run footer with two-phase launch. Model management lives under Settings → Models.
- `analysis.llm_action_items.effort` default is now `max` (was `high`) so dense meeting-extract JSON has a larger `num_predict` budget by default.
- `llm_action_items` prompt v6 asks models to close the items array cleanly rather than emit truncated JSON.
- Speaker profiles (real display names) are gitignored under `data/speaker_profiles/` and can be pointed outside the clone via `TRANSCRIPTX_SPEAKER_PROFILES_DIR` (same mountable-root pattern as transcripts/outputs).
- Charts Gallery: Analysis scope filter helper, export/download as action links under badges.

### Fixed

- `llm_action_items` salvages complete items from truncated / unterminated LLM JSON instead of failing the whole module with no artifacts.
- Empty/failed `llm_action_items` UI no longer tells users only to re-run: availability and Insights/Overview show why it failed and what to change (effort max + stronger model) before retrying.
- When `llm_action_items` publishes an empty `items` list after dropping invalid/unsupported/ungrounded records, Insights/Overview explain the drop counts and discourage tiny/small models (e.g. `llama3.2:3b`). LLM model-selection guidance now flags those tags as unreliable for meeting extracts.

## [0.6.9] - 2026-07-23

### Added

- `llm_custom_qa` v2 staged migration: activation-gated writer (`v2_live`), structured scopes (global / per-speaker), evidence catalog + routing plan, deterministic scheduler, soft quote grounding, and immutable generation-named artifacts (`{stem}.json.{gid}`) with marker schema v2 + `run_execution_id`.
- Settings/Run structured question library (scopes + evidence packs); Insights placement under summary/speaker fallbacks (Actions placements removed).
- Dual-compatible readers (canonical stem under `llm_custom_qa/data/global/`), export via authoritative loader, and consumer activation inventory.

### Changed

- Config ownership goldens for expanded `llm_custom_qa` settings (47 pilots / 660 Pydantic leaves / 16 legacy).
- Group aggregation for custom QA remains registry-disabled pending v2 group loader.

### Fixed

- Empty-run orphan sweep preserves the active generation under the writer lock.
- V2 answer rows no longer leave `question_index` in committed artifacts.

## [0.6.8] - 2026-07-23

### Changed

- Charts Gallery UI: compact filters (Search, Source, Analysis scope, Static/Dynamic pills), View options popover with Chart text mode, filtered Run overview section, searchable module rows with Module family / A–Z sort, and dirty-only Reset.
- Studio presentation polish: LLM text cleanup helpers, speaker accents in the transcript viewer, and shell spacing fixes.

### Fixed

- Charts filter state categories (resettable filters vs persistent Chart text vs run-scoped open modules); Source presets no longer leave invisible free-form tag filters.

## [0.6.7] - 2026-07-23

### Added

- `llm_action_items` v2 meeting extracts (B10): typed records (`decision`, `commitment`, `action_item`, `proposal`, `open_question`), sectioned render with human-review banner, and group aggregation schema 2 with fixed per-type count columns.
- Config flag `llm_action_items.coerce_v1_artifacts` (default `false`) for optional v1 group-row coercion.

### Changed

- Presentation copy uses “Meeting extracts”; empty state “No meeting extracts found.”
- Group row writer persists aggregator `schema_version` (no longer hardcodes `1`).

### Fixed

- `llm_custom_qa` artifact commit respects the orchestrator-bound run-writer lease (avoids worker-thread lock timeouts).
- Smoke suite skips `llm_custom_qa` with other Ollama-backed LLM modules.

## [0.6.6] - 2026-07-23

### Added

- Analysis module `llm_custom_qa` (B21): Settings question library, Run/Batch picker, cite-or-unavailable Insights cards, generation commit-marker artifacts, and group `qa_answer_rows` / `qa_member_failures` aggregation.
- Project-config `FileLock` writers (`config_write_lock` / `patch_project_config_keys`) with typed lock/corrupt errors.
- Settings → Questions tab and conditional LLM gating when the effective question set is empty.

### Changed

- Config ownership pilots include `llm_custom_qa_settings` (**47** pilots / **651** Pydantic leaves / **667** registry keys).
- Topic-shift embedding hardening (offline Hub scope, enrichment/spans coverage) and related docs/tests.

### Fixed

- Settings page orchestration for the Questions tab; module UI pinned order and audit guardrails for custom-QA commit writes.

## [0.6.5] - 2026-07-23

### Added

- Analysis module `topic_shift` (B9): embedding change-point chapter spans, deterministic generational store, optional LLM enrichment sidecar, Transcript Chapters tab, Moments point-event soft-read, and group cohort aggregation with session bars plus temporal overlay.
- Shared `llm_generational_store` helpers with empty-digest rejection and parity coverage for enrichment-style stores.

### Changed

- Config ownership pilots include `topic_shift` (**46** pilots / **642** Pydantic leaves / **658** registry keys).
- Pin native BLAS/OpenMP/Numba thread env defaults before optional-extra imports so BERTopic/UMAP smoke does not conflict with a sticky Numba pool size.

### Fixed

- Optional-module smoke uses non-importing distribution probes for extras; Numba thread env is re-applied in pytest setup after env teardown.

## [0.6.4] - 2026-07-22

### Fixed

- ASR confidence group aggregation prefers evidence-rich provenance cohorts when sizes tie, so mixed absent/present groups still emit cohort-safe charts.
- Align `transcriptx.web` package version with the root package (`0.6.4`).

## [0.6.3] - 2026-07-22

### Added

- Per-segment audio playback in Transcript viewer and Speaker ID, reusing the Speaker Studio clip stack with shared controller lifecycle, warm-clip gating, and safe timestamp display.
- Foundations module `transcript_quality` (ASR Confidence): word-level score coverage, low-confidence spans/clusters with playback refs, provenance-aware group aggregation and charts.
- Expanded LLM model guidance (`model_guidance`) and thinking-model selection helpers for the Run Analysis selector.

### Changed

- Shared `SpeakerStudioController` factory returns a live controller (no Streamlit `cache_resource` generator); process registry + atexit close all instances; `clear_shared_speaker_studio_controller` closes then clears cache.
- Warm clips require `WarmClipsResult` with `requested` / `fully_accepted`; warm signatures include audio path size and mtime; unavailable audio/ffmpeg clears stale play + warm state.
- Config ownership pilots include `transcript_quality` (45 pilots / 619 Pydantic leaves / 635 registry keys).

### Fixed

- Playback degraded to `controller_error` when the shared factory yielded a generator instead of a controller.
- Canonical transcript path resolution falls back independently when `loaded_path` is unresolvable but artifacts JSON remains; disappeared files disable playback without crashing the page.
- Nested `analysis.transcript_quality` file overrides hydrate as dataclasses (avoids `asdict()` failures on plain dict subtrees).

## [0.6.2] - 2026-07-21

### Added

- Run Analysis / Batch LLM model selector with shared or per-module Ollama tags, savable `llm_models` profiles, and module guidance table.
- Request-scoped `llm_model_selection` on transcript, group, and batch analysis with ContextVar binding and fail-loud missing-model errors.
- Provenance `model_selection_source` (`request` | `profile` | `global`) on LLM consumers including chart descriptions and group synthesis.

### Changed

- Consumer model precedence is request bind → active `llm.model_selection` → global `llm.model` (effort-profile model no longer sits in the consumer chain).
- GUI launch gates when selected LLM modules need Ollama but LLM is disabled, tags are empty, or picks are unset; no silent substitution of unavailable tags.
- Strict validation of explicit `llm_model_selection` at readiness (invalid payloads fail; omitted/`None` keeps prior global-only behaviour).

### Fixed

- Group synthesis provenance access when runtime mocks omit `model_source`.
- Wordcloud speaker eligibility test isolation against leftover active output-service state.

## [0.6.1] - 2026-07-20

### Added

- `PreRenderedFigureSpec` for already-drawn matplotlib figures (wordclouds, topic composites) with plotted evidence sidecars.
- Overview speaker summary cards use bordered containers and per-speaker accent colors.

### Changed

- Chart evidence migration marked complete for primary writers (understandability bars, topic heatmaps/bars/timelines, wordclouds, group ChartSpec path).
- Evidence sidecar write failures are logged without failing chart PNG saves.

### Fixed

- Topic and wordcloud chart paths emit ChartSpec evidence instead of legacy fig-only saves.

## [0.6.0] - 2026-07-20

### Added

- Per-chart LLM descriptions as a finalize-phase module: atomic ACTIVE generations, evidence sidecars, Charts gallery toggles, and ZIP/HTML export materialisation.
- Run-finalization coordinator and lock owning chart descriptions → group synthesis → single manifest write.

### Fixed

- Finalize-phase modules are excluded from the DAG planner (no peer execution with chart writers).
- Post-run console summary runs after finalize persistence so `chart_descriptions` is not reported as a false failure.
- Chart inventory ignores `*.evidence.json` / `chart_evidence` artifacts so plotted evidence sidecars are used instead of legacy metadata fallback.
- LLM client calls use keyword-only `prompt=` for Ollama compatibility.
- Coordinator returns only newly appended finalization warnings (no duplication into group aggregation warnings).
- Chart dispatch exceptions record `GROUP_CHART_FAILED` aggregation warnings.

## [0.5.4.1] - 2026-07-20

### Added

- Module wall-clock timeout enforcement in the DAG (BERTopic default 3600s, configurable via `TRANSCRIPTX_BERTOPIC_TIMEOUT_SECONDS`) so a hung fit no longer blocks later modules.
- Native thread pinning helpers and bound run-writer leases so timeout worker threads can write under the orchestrator lock.
- Chart descriptions finalize-phase module and related Charts UI / export wiring.

### Fixed

- BERTopic hang/timeout isolation: abandon timed-out modules with `module_timeout` and continue the pipeline.
- Soft-fail BERTopic fits that collapse to zero samples on tiny corpora (smoke/mini fixtures).
- Cross-thread run-writer lock deadlocks when modules execute in a timeout ThreadPoolExecutor.

## [0.5.4] - 2026-07-19

### Added

- BERTopic as an opt-in analysis module again: registry/UI surfaces, transcript + group pooled charts, zip/summary export, packaging extras, and configurable knobs (`TRANSCRIPTX_BERTOPIC_*`) with sensible defaults.
- Retained-run performance snapshot exporter (Prometheus textfile gauges) plus `scripts/export_run_performance_snapshot.py` and `TRANSCRIPTX_RUN_PERF_EXPORT_*` env knobs.
- Folder/admit import helpers and related upload-transcript workflow hardening.

### Fixed

- BERTopic module packaging metadata (`required_extras` / `exclude_from_default`) so the optional path stays opt-in while packages remain available.
- HF safetensors / sentiment local-load edge cases covered by new unit tests.

## [0.5.3] - 2026-07-19

### Added

- Analysis-run performance telemetry: `.transcriptx/run_performance.json` sidecar, module `duration_ms` round-trip in `run_results.json`, LLM call metrics wiring, and a Streamlit Performance page.
- Host-side Ollama URL rewrite: `host.docker.internal` → `127.0.0.1` outside Docker so CLI/host runs can reach local Ollama.

### Fixed

- Group emotion aggregation crash on lexical-v2 nested `speaker_stats` (`float + dict`); prefer flat `emotion_scores` maps.
- Register `TRANSCRIPTX_TRANSCRIPTION_PROVIDER` on the infra env allowlist to match `.env.example`.
- Refresh dashboard overview pydantic golden fixtures for new chart registry IDs.

## [0.5.2] - 2026-07-19

### Fixed

- Group Insights/Overview blocks are dual-aware: show group rollups (`*_rows.json` / blobs / synthesis) and per-session member artifacts via a session picker. `ArtifactContentLoader` honors member `storage_root`; Overview compact blocks stay rollup-or-quiet (no session pickers).

### Added

- Shared `web/blocks/group_content` helpers; tests for group per-member module execution, partial-member aggregation, and Insights dual UI.

## [0.5.1] - 2026-07-19

### Added

- Exclude-neutral count and non-neutral share bar charts for experimental `contextual_emotion` and `fine_grained_emotion` (global + per-speaker). Fine-grained share charts use the full non-neutral denominator before top-15 truncation, so displayed bars may sum to less than 1. Derived presentation artifacts only (no schema / semantics / fingerprint / aggregation-cache bump).

## [0.5.0] - 2026-07-19

### Added

- Cross-session **group LLM synthesis**: after group finalize collects member `llm_summary` / `llm_speaker_summary` artifacts, an Ollama second pass publishes generation-scoped global and per-speaker rollups (ACTIVE/COMMIT under `.group_llm_synthesis/`). Config: `analysis.group_llm_synthesis.enabled` / `effort`. Overview/Insights use the validating resolver. Contract: `docs/groups/group_llm_synthesis_contract.md`.

## [0.4.9.2] - 2026-07-19

### Added

- Per-speaker label-count charts for experimental `contextual_emotion` and `fine_grained_emotion` (`*.label_counts.speaker`), with gallery registry captions and emotion-family contract docs for all four single-transcript viz IDs.
- Unit coverage for fine-grained emotion projections and HF text-classification profile helpers.

### Fixed

- Contextual Hartmann profile loads via `pytorch_model.bin` (`prefer_safetensors=False`) for the pinned Hub revision that does not ship safetensors.

## [0.4.9.1] - 2026-07-19

### Fixed

- Offline `@pytest.mark.unit` emotion/contagion analysis tests are no longer auto-tagged `requires_models` (and thus skipped) by path heuristics; contagion analysis tests marked unit.

## [0.4.9] - 2026-07-18

### Added

- Emotion family hardening: shared generational store, split cache, consumer contracts, and HF text-classification runtime for experimental `contextual_emotion` / `fine_grained_emotion`.
- Lexical `emotion` v2 projections with deferred enrichment until after canonical persist, plus repair helpers for enriched projections.
- Emotion-family calibration fixtures/protocol docs and release-matrix unit coverage.

### Changed

- Contagion and affect-tension consumers read emotion via family contracts (lexical projection gate tightened; reconstruction path removed).
- Config pilots for `emotion_lexical`, `contextual_emotion`, and `fine_grained_emotion` (ownership/registry goldens updated).

### Fixed

- Sidebar Streamlit test double honors keyed selectbox session state (no-runs hint coverage).

## [0.4.8] - 2026-07-18

### Added

- Interactions turn-taking equity pack (B12): floor share/entropy, interruption asymmetry, response-latency fairness; shared segment-duration helper; equity charts and session-row indices.

### Changed

- Interactions `semantics_version` **2**: initiated/received and matrices use actor→target roles (interrupter→interrupted, responder→addressee). Group directional pooling skips mixed/legacy versions with one structured warning.
- `speaker_stats` duration summation adopts the shared segment-duration helper (eligible-speaker and invalid-timestamp rules aligned with interactions).

### Fixed

- Interactions initiated/received polarity was historically inverted relative to event comments and chart labels. **Existing runs require re-analysis** for correct directional counts, dominance, and equity.

## [0.4.7] - 2026-07-18

### Added

- Module-run prompt CTA (`module_run_prompt`) for Insights empty states that need a fresh analysis run.
- Broad Streamlit page coverage tests (artifacts, audio merge, diagnostics, groups, insights, overview, search, settings, action-menu navigation).

### Changed

- Action-menu identity navigation clears stale transcript pickers and syncs Run Analysis target mode with the destination subject.
- Sidebar subject/run widgets stay aligned after external navigation; Batch Ops is a legacy redirect that sets batch mode before rewrite.
- Action-link column separators use column `::after` pipes (avoids Streamlit button clipping).

### Fixed

- Preserve hydrated transcript `subject_id` when clearing auto-picked `run_id` during identity apply.

## [0.4.6] - 2026-07-17

### Added

- Run-cleanup Phase B closeout: `CLEANUP_POLICY_VERSION` **7** binds classifier and newest-run policy into plan IDs; journal target/status updates take a per-operation RMW lock; recovery synthesizes terminal retries with safe target reconstruction; adversarial FS + dir-fsync outcome tests.
- Export resolve helpers (`resolve_summaries`, `resolve_transcript`) and expanded export-service coverage.
- Group functional-module finalize integration coverage and shared analysis I/O characterisation updates.

### Changed

- Run-cleanup polish: façade calls journal module directly (no temporary private shims); FD/path/prune unit coverage expanded.
- Align `OutputService.transcript_dir` with safety redirects from `create_standard_output_structure`.
- Move charts/export index/markdown helpers under `transcriptx.export` (remove `transcriptx.utils` export shims).
- Drop explicit `supports_group: False` from core/export/speaker module specs (default remains unsupported).

### Fixed

- Artifact-metadata tests follow redirected run roots under `OUTPUTS_DIR`.
- Raise transitive `tornado` floor to `>=6.5.7` (Streamlit stack CVE fixes).

## [0.4.5] - 2026-07-17

### Added

- Complete Phase A run-cleanup extract: façade delegates to `planning`, `locking`, `staging_phase`, `deletion_phase`, `execution`, `recovery`, `finalization`, and `journal_ops`.
- Expanded unit/integration coverage for status reduction, journal durability, runtime late-binding, façade shims, and finalization demotion.
- Characterisation goldens for plans, partitions, side-effect parity, retry/pending, and newest-run sort identity.
- Codebase stocktake doc and links from README/ROADMAP.

### Fixed

- Keep `CLEANUP_POLICY_VERSION` frozen at 4 for Phase A; release-blocker crash test uses version constants.
- Document WhisperMLX and Streamlit perf optional env keys in `.env.example`.

### Changed

- Thin `RunCleanupService` to a public façade over extracted orchestration modules.

## [0.4.4] - 2026-07-17

### Added

- Run-cleanup characterisation suite (API signatures, fault-point order, golden snapshots) and AST import-cycle check.
- `staging_identity` helper module; `CleanupRuntime` / `ExecutionContext` scaffolding; status helpers in `results.py`.
- Contracts/assessment docs for the run-cleanup refactor.

### Fixed

- Restore `journal.intended_staging_path` / staging re-exports after the identity extract.
- Black/ruff clean-up across recent web and characterisation tests.

### Security

- Raise floors for `urllib3`, `werkzeug`, `ujson`, and `wheel` (constraints + requirements).
- Document `TOKENIZERS_PARALLELISM` in `.env.example`.

## [0.4.3] - 2026-07-17

### Fixed

- Artifacts Browse→Preview defers Streamlit widget key writes until the next run to avoid mid-script assignment errors.
- Subject context updates pop a locked sidebar type selector instead of raising after the widget is instantiated.
- Charts overview resolves effective config from `transcriptx.core.config`.

### Changed

- Search and Corrections Studio drop redundant empty-state prompts before a session or query is ready.

## [0.4.2] - 2026-07-17

### Added

- Shared recent-run row component reused on Home and Batch Ops, with post-batch run action links.
- Batch analysis results carry successful `RunSummary` entries for UI follow-up.
- Tertiary download-link helper aligned with action-link styling for transcript downloads.

### Fixed

- Narrative LLM JSON recovers when local models emit unescaped quotes inside the narrative string.
- Document-strict LLM JSON parsing (`loads_llm_json_document`) rejects prose-wrapped payloads.
- Corrections Studio discovery prompts require escaped quotes in string values; avoid double fence-stripping.

### Changed

- Home recent-runs rendering extracted into the shared row component; page headers drop decorative emoji prefixes.

## [0.4.1] - 2026-07-17

### Fixed

- Artifacts Browse→Preview and deep links sync Streamlit widget keys so section/selector state is not clobbered.
- Storage cleanup execute defers result rendering across a rerun to avoid mid-run widget key assignment errors.
- Directory fsync on Docker Desktop bind mounts tolerates `EBADF`/`EINVAL` instead of aborting cleanup.

### Changed

- Run cleanup logs preview/execute progress and per-target stage/delete outcomes for easier diagnosis.

## [0.4.0] - 2026-07-17

### Added

- Safe run-cleanup pipeline for storage management (plan/staging/journal/physical delete with identity and handle guards).
- Per-run writer locks, path canonicalization, and run-identity helpers to serialize mutating output writes.
- Web layout/context shell upgrades: context bar formatting, run-id info, action links, and refreshed branding assets.
- Storage settings UI wired to cleanup discovery, compare, and recoverability flows.

### Changed

- Home/shell navigation and run-scoped pages share a clearer workspace layout; standalone Statistics page removed in favor of integrated surfaces.
- Pipeline/output services acquire run writer leases for concurrent-safe artifact writes.
- Corrections Studio input/service paths tightened for batch commit and candidate generation.

### Fixed

- Group wordcloud output `save_data` signature aligned with `OutputService` lease parameter for type-checker compatibility.

## [0.3.9.1] - 2026-07-16

### Security

- Bump `click` to `8.3.3` to address a published vulnerability on the previous pin.

## [0.3.9] - 2026-07-16

### Changed

- Split rename and Corrections Studio orchestrators into focused phase modules while preserving public import contracts.
- Advance config ownership collapse: broader nested/system/workflow delegation and flatter analysis config ownership.
- Share dynamics/group-chart artifact I/O helpers and tighten affect/sentiment module boundaries.

### Added

- Characterization and contract tests for shared analysis I/O, rename phase matrix, corrections studio public imports, and config delegation slices.

## [0.3.8.2] - 2026-07-16

### Added

- Broad offline unit coverage for analysis helpers (semantic similarity, wordclouds, acts/affect, corrections, pipeline/output branches) lifting core coverage past 85%.

## [0.3.8.1] - 2026-07-15

### Fixed

- Corrections Studio LLM discovery accepts common local-model JSON shapes (bare candidate arrays, `short_rationale` / related aliases) instead of failing every chunk with `llm_invalid_response`.
- Action-items optional fields coerce common LLM scalar/list mistakes instead of failing the whole parse.
- Artifact file preview no longer crashes on binary files (UTF-8 decode).
- Config default-shape tests isolate `TRANSCRIPTX_*` env from repo `.env` bootstrap.

### Added

- Multi-model LLM response fixture corpus and deeper unit coverage for discovery, narrative, action-items, and summary intake.
- Gated live Ollama diversity helpers/matrix for corrections discovery, overall summary, and speaker summaries.
- Local compose defaults and docs for enabling Corrections Studio LLM against host Ollama.

## [0.3.8] - 2026-07-15

### Added

- Corrections Studio LLM discovery path (`corrections_studio/llm/`) with chunking, grounding, merge, and confidence controls; config via `corrections.llm` / `docs/runtime/corrections-llm.md`.
- Import adapter engine modules for vendor formats (WhisperX, Zoom, SRT/VTT, Otter, Rev, Fireflies, Sembly, generic text).
- FileLock same-thread re-entrancy to avoid Darwin nested-lock self-deadlocks during managed import.

### Changed

- Removed legacy `core/adapters` and `io/adapters` packages in favor of store + `io/import_adapters`.
- Makefile `test-fast` / `test-coverage` marker filters aligned with `pytest.ini` (`legacy`, `semantic_v2_slow`).
- Web composition/layout and public-surface docs updated for current block and entrypoint contracts.

### Fixed

- Blocking FileLock timeouts no longer proceed unlocked; processing-state lock tests use cross-thread contention.
- Version surfaces kept in sync (`transcriptx` / `transcriptx.web`).

## [0.3.7] - 2026-07-14

### Added

- `io/import_metadata/` package (paths, schema, persist, validate, layout) with a thin `import_metadata_sidecar` facade.
- `io/atomic_json.py` for crash-safe JSON writes (re-exported from `rename.io_atomic` for compatibility).
- Mocked-spaCy golden tests characterizing `nlp_utils` preprocess variants before any future split.
- Rename robustness contract tests (lock failure, rollback incomplete, audio classification, speaker-map moves, repair prepared-phase matrix, slug index reconcile).

### Changed

- Managed rename: extracted phase helpers in `plan.py` and `pipeline.py`; migrated remaining production callers off the `file_rename` shim to `rename.*`.
- Consolidated managed import onto `managed_import_workflow`; removed the `import_managed` package.
- Moved import sidecar layout resolution into IO to break the IO↔rename import cycle.

### Fixed

- Library audio-resolution contract tests retargeted to `rename.audio_association` after caller migration.

## [0.3.6] - 2026-07-13

### Added

- Shared `phrase_quality` analyser and theme-phrase resources for deterministic key-theme / highlight / insight phrase filtering.
- Curated Overview blocks (summary hero, at-a-glance, speaker cards, compact highlights/status) and primary-summary precedence across LLM, narrative, and executive summaries.
- Merged **Artifacts** page (Browse / Preview / Export) replacing legacy Data and Explorer routes, with presentation-oriented artifact index and export selection helpers.
- Run-health presentation helpers separating artifact storage health from execution outcomes.

### Changed

- Summary and highlights key-theme extraction prefer noun-led topical phrases and diversity fill over discourse formulas and light-verb constructions.
- Default Overview layout uses the curated Standard profile; Insights gains quieter empty states and related summary blocks.

### Fixed

- Overview composer contract tests updated for curated block IDs; Black/Ruff hygiene on new surfaces.

## [0.3.5] - 2026-07-13

### Added

- Group analysis aggregations for LLM modules (`llm_summary`, `narrative_summary`, `llm_speaker_summary`, `llm_action_items`), `insights`, semantic similarity (legacy/advanced/v2), and voice modules (`voice_mismatch`, `voice_tension`, `voice_fingerprint`).
- Group chart allowlists and generic session-bar wiring for the new aggregations.
- Expanded unit and integration coverage for group infrastructure (output scaffold, artifact merge edges, finalize deps/disabled paths, workflow missing-path branches).

### Changed

- Group module resolution/readiness honors `supports_group` / `for_group` so unsupported modules are filtered from group runs.
- Prosody/group dashboard summary keys use session-prefixed fields for safer multi-transcript aggregation.

### Fixed

- Pre-release hygiene: document optional Streamlit perf env vars; ignore `.env.*` (keep `.env.example`) and `data/perf/`; stop tracking large streamlit load-profile JSONL.

## [0.3.4] - 2026-07-13

### Added

- `llm_action_items` analysis module: structured Ollama extraction of action items (owner, deadline, status, quote) with quote grounding, dedupe, and distinct cache identity.
- `analysis.llm_action_items.effort` config (low/medium/high/max; default `high`).
- Insights/executive UI blocks and zip-export summary section for action items.
- `lexical_diversity` analysis module: deterministic TTR, MTLD, and hapax-rate metrics (optional time buckets), CSV/JSON artifacts, and chart gallery entries.
- Insights block and overview summary extractor for lexical diversity; group aggregation allowlist for descriptive session metrics.

## [0.3.3] - 2026-07-13

### Added

- `llm_speaker_summary` analysis module: abstractive Ollama summaries for each named speaker, with per-speaker artifacts and a global index.
- `analysis.llm_speaker_summary.effort` config (low/medium/high/max), mirroring `llm_summary` effort tiers.
- Insights block for per-speaker LLM summaries.

## [0.3.2] - 2026-07-02

### Added

- `analysis.llm_summary.effort` config (low/medium/high/max) with builtin Ollama profiles for input size, timeout, and output tokens.
- Pydantic pilot for `llm_summary` settings and integration tests with golden fixtures.
- Input coverage metadata in llm_summary provenance.

### Changed

- `llm_summary` uses effort-tier runtime resolution instead of global `llm.max_input_chars` / `max_output_tokens` on the Ollama path.
- Dockerfile builds the wheel after spaCy/NLTK/TextBlob downloads so NLP assets are baked into the image.
- Transcript viewer segment timestamps render with millisecond precision when sub-second.

### Removed

- `speaker_profiling` utility and its unit tests (unused).

## [0.3.1] - 2026-07-02

### Added

- Config delegation tests and golden fixtures for pauses, voice, and corrections settings.
- Contract tests for stale surface references and expanded unit coverage (lazy imports, perf instrumentation, voice skip paths).

### Changed

- `src/transcriptx/web/streamlit_app.py` is now a deprecation stub. Use `transcriptx`, `python -m transcriptx.web`, or `streamlit run src/transcriptx/web/app.py`.
- Analysis config helpers delegate pauses, voice, and corrections to dedicated Pydantic pilots.
- Dependency pins: `watchdog==5.0.3` (dagster-compatible), `marshmallow==4.1.2` and `scikit-learn==1.5.0` aligned across `pyproject.toml` and `requirements.txt`.

### Removed

- Tracked pre-release report artifacts under `artifacts/pre-release/` and `reports/pre_release*/` (now gitignored).

## [0.3.0] - 2026-07-02

### Added

- Module registry snapshot and contract tests with golden fixture for 39 modules.
- Domain-split module definition builders under `module_specs/` composed via explicit `MODULE_REGISTRY_ORDER`.

### Changed

- `build_module_definitions` in `module_registry_specs.py` is now a thin compatibility wrapper; `MODULE_CLASS_MAP` and `EXTRA_REPRESENTATIVE` remain on the public façade.

## [0.2.0] - 2026-06-17

### Added

- Local LLM integration via Ollama (`llm_summary`, `narrative_summary` opt-in modules).
- `LLMConfig`, env/file overrides, `requires_llm` gating, and stable `error_code` propagation through the DAG adapter.
- Shared LLM helpers (truncation, provenance, artifact staging) and documentation (`docs/runtime/llm.md`).

## [0.1.2] - 2026-06-17

### Fixed

- Declare `networkx` as a core package dependency so wheel installs can build the module registry (conversation-loops and network chart renderers import it at load time).
- Defer analysis module class imports until execution so optional extras (e.g. maps/NLP) are not required to plan or run unrelated modules such as `stats`.
- Document `TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS` in `.env.example`.

### Added

- Multi-language transcript import: flat `{base}_{lang}.json` variants (e.g. `meeting_fr.json`) inherit the base transcript's speaker map on managed import when the base has a speaker-map sidecar and the variant does not (`io/speaker_map_inheritance.py`, `core/utils/transcript_variant_paths.py`). `speaker_id_to_db_id` is copied because those IDs are canonical cross-segment grouping keys shared by the same physical speakers.
- Combined Overview export: a single self-contained `index.html` (`utils/export_index.py`) that server-renders a transcript view plus an unfiltered charts gallery so exports open correctly over `file://` (no client-side `fetch()` of local JSON). The transcript and charts sections fail independently. Inline, CDN-free CSS and chart-section rendering are shared with the charts-only export (`utils/charts_export.py`).
- `semantic_similarity_v2` analyzer package (intake, candidates, embedding, similarity, cluster, classify, output, diagnostics, visualization); `momentum` and `qa_analysis` now consume its results with fallback to the legacy variants.
- SRT writer for transcript segments (`io/srt_writer.py`).

### Changed

- Pipeline (DAG) internals decomposed from the monolithic `dag_pipeline.py` into focused modules (contracts/ports DTOs, `dag_planner`, `dag_executor`, `dag_execution_adapter`, `run_orchestrator`, `run_bootstrap`, `run_configurator`, `run_persistence`, `run_presenter`, `run_outcome`, `run_workspace`) with file-backed store/reporter adapters behind ports. Legacy compatibility shims preserve existing callers.
- Chart fixes for modules that were not rendering on diarized-but-unnamed transcripts: `echoes` falls back to the raw diarization label (e.g. `SPEAKER_00`) when no human-readable name exists and accepts a configurable embedding model; the contagion matrix uses `is_turn_taking_speaker_label` instead of `is_named_speaker`.
- Matplotlib rendering split into a `core/viz/mpl` package with per-type renderers (bar, box, heatmap, line, network, scatter) and a dispatcher.
- Web UI decomposed: `web/app.py` split into `router`, `navigation`, `sidebar` (+ state/options), `page_flash`, and view-state helpers, plus a `transcript_viewer` package (segments, highlight, metadata, downloads, modules panel, preflight).
- `speaker_map_resolver`: placeholder self-maps (e.g. `SPEAKER_00 -> SPEAKER_00`) are treated as still-unnamed via `is_effective_speaker_name`, so UI progress and pipeline gating do not count them as identified speakers.
- Stats summary lifecycle cleanup: `create_comprehensive_summary` is the maintained plain-text summary helper, now split into section renderers without output-schema/heading drift.
- Legacy HTML export path `generate_enhanced_html_summary` is retained for temporary manual compatibility and now emits a deprecation warning pointing users to `report.json`/`report.md`/`report.txt`.
- Config env override handling is now unified under a canonical registry (`env_key_registry.apply_env_to_config`) used by both `env_overrides.apply_transcriptx_env` and `system_env.apply_env_overrides`. This intentionally adds previously missing `system`-path coverage for `TRANSCRIPTX_CORE`, `TRANSCRIPTX_FILE_SELECTION_MODE`, semantic/module progress interval keys, and `TRANSCRIPTX_SPEAKER_GATE_*` keys.
- Added opt-in strict unknown env enforcement with `TRANSCRIPTX_CONFIG_STRICT=1`: unknown `TRANSCRIPTX_*` keys now raise `ConfigLoadError` in strict mode; default mode logs a diagnostic warning while preserving mutation/error behavior.

### Removed

- Removed dead `generate_summary_stats` from `stats/summary.py` (no supported call sites; stale unresolved dependencies).

### Dependencies

- **Security:** bumped `cryptography` 46.0.6 → 48.0.1 (PYSEC-2026-36, GHSA-537c-gmf6-5ccf) and `python-dotenv` 1.1.1 → 1.2.2 (CVE-2026-28684). `cryptography` is a transitive/security pin (not imported directly); `python-dotenv` is used only via the stable `load_dotenv` API. `setuptools` remains capped `>=64,<70` for llvmlite/numba build compatibility; the remaining setuptools advisories are build-time only and blocked by that cap.

## [0.1.1] - 2026-04-06

### Changed

- Code style: Black formatting across touched modules; Ruff fix (remove unused variable in corrections studio fuzzy speaker inputs).
- **Pytest:** register the `optional` marker in `pytest.ini` so release-profile expressions such as `not optional and not heavy and not quarantined` match project policy.
- **README:** document the canonical development sample transcript (`tests/fixtures/mini_transcript.json`) and how it relates to `scripts/docker-smoke-test.sh`.

### Dependencies

- **Typer:** use `typer==0.16.0` without the `[all]` extra. Pip warned that 0.16.0 does not ship that extra name; runtime behavior for the `transcriptx` launcher is unchanged because Rich and Click are already direct dependencies and the CLI surface is minimal.
- **Security-related pins:** `cryptography` 46.0.6, `nltk` 3.9.4 (addresses published advisories for the previous pins).

**Note for upgrades:** If you install from a custom constraints file, an air-gapped mirror, or a monorepo lockfile, re-resolve dependencies after this release. Mixed pins (e.g. an older `cryptography` forced by another package) can make `pip check` or Docker builds fail until constraints are aligned.

## [0.1] - 2026-03-25

First supported public contract (v0.1). Artifact schema numbers are unchanged: transcript `schema_version` string `"1.0"`, `run_results.schema_version` integer `2`.

### Added

- Stricter validation: `validate_manifest_shape` requires `manifest_type: artifact_manifest`.
- `RunResultsSummary.validate_run_results` rejects non-dict `modules_skipped` entries.
- Tests for manifest and run_results contract failures.

### Changed

- **Stats output:** only `report.json`, `report.md`, and `report.txt` at run root; removed duplicate `{base}_stats.json` and its manifest registration.
- **Path resolution:** `resolve_file_path` uses `PathResolver` first when available (migration flag removed).
- **Pipeline:** `build_execute_pipeline_context` always returns a validated `PipelineContext` or raises; no legacy execution path when context creation or validation fails.
- **Paths:** removed `TRANSCRIPTX_WAV_STORAGE_DIR` and startup `_migrate_state_paths`; removed module aliases `WAV_STORAGE_DIR` and `WAV_OUTPUT_DIR` (use `PATHS.wav_backup_dir` and `PATHS.recordings_dir`).
- **Requirements:** removed `Requirement.LEGACY_UNUSED` (`database`).
- **Transcript filenames:** canonical check accepts only `*_transcriptx.json` (dropped `*_canonical.json` alias).

### Removed

- `parallel_executor.py` and `TRANSCRIPTX_ENABLE_LEGACY_PARALLEL_EXECUTOR` (`.env.example`).
- `scripts/migrate_speaker_maps.py` and its tests.
- Legacy fixtures `tests/fixtures/whisperx_legacy*.json`; WhisperX adapter tests use `fixtures/transcripts/whisperx/word_level.json`.
- `docs/legacy_transitional_compatibility_register.md`.
- Duplicate stats JSON artifact and deprecated env/migration hooks as above.

### Documentation

- `docs/transcription.md`: golden path emphasizes import + v1.0 runtime contract (no compatibility register link).

