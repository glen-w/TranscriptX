# TranscriptX Roadmap

**Current version:** see [pyproject.toml](../pyproject.toml) (package version).

**Product definition:** [PRODUCT.md](PRODUCT.md)  
**Programme plan (0.9.x → 1.0):** [pre_release_roadmap_1_0.md](dev/pre_release_roadmap_1_0.md)  
**Decision foundation:** [stocktake_2026-07-17.md](dev/stocktake_2026-07-17.md)

**North star:** a credible **1.0** local-first transcript analysis workbench governed by release evidence and explicit severity rules — not feature count or fixed patch assignments.

> **Status legend:** [ ] planned · [x] done · [~] in progress

---

## Now (owner, top priority)

**Clean up local corpus folders before any further import / analysis work on this machine.**

Host STT (`inbox-watch` / `whispermlx-missing`) writes raw JSON under the managed library’s `originals/` subtree. **Import all from folder** scans a *different* directory (`HOST_TRANSCRIPT_INBOX_DIR` → `/mnt/transcript-inbox`) and **refuses** `transcripts/` and `originals/`. Near-homonym host folders (managed library vs a sibling inbox whose name looks like “transcripts originals”) drift: new recordings transcribe successfully and then never appear in the library.

Owner checklist (do this first):

- [ ] Inventory host mounts: managed library, `originals/`, import inbox, recordings, wav backup, outputs — names must not be confusable
- [ ] Rename the inbox to an unambiguous path (prefer `transcript-inbox`, not a space-variant of `transcripts/originals`)
- [ ] Decide the copy/sync rule until auto-admit exists: new `originals/` JSON → inbox, then Import eligible
- [ ] Confirm library listing vs inbox vs `originals/` so “imported all” cannot miss new stems

This is **owner machine hygiene**, not a 1.0 product feature. It still outranks unfamiliar-user prep on this corpus. Layout contracts: [STORAGE.md](runtime/STORAGE.md), [docker.md](runtime/docker.md), [transcription.md](runtime/transcription.md). Programme note: [pre_release_roadmap_1_0.md](dev/pre_release_roadmap_1_0.md) §20 / §21.

---

## Current state

- Streamlit GUI + typed Python API; managed import; file-backed storage/sidecars
- Broad analysis module set (language, speakers, interactions, emotion, voice, groups, optional Ollama)
- Contracts for storage, run outcomes, outputs, and public surfaces
- Package on a **0.9.x** stabilisation track toward 1.0

Install honesty: runtime markers are **`core` | `full`** only; Streamlit is the separate **`[web]`** extra. Transcription remains external, with in-app **command-generation** handoff shipped in **0.9.4**. Sphinx hosted-docs revive + harden scaffolds shipped in **0.9.5**. Guided/Full + demo + onboarding checklist were trialled in **0.9.6** and later **removed** (prefer docs + clear GUI). Automatable harden + public surfaces (website, trust drafts, audit judgements, release-ops) shipped in **0.9.7**. Hygiene/honesty kits **0.9.8**; Overview presentation cut **0.9.9**. Post-0.9.9 wave cut as interim **`0.9.9.5`**: early 1.x Themes **A–D**, Tools/Merge/watcher, rename, Builder/Edit, GUI perf, backup/restore — [post_0_9_9_shipped_overview.md](dev/post_0_9_9_shipped_overview.md). Theme **B** viewer corrections **done**; Theme **C** CCv2 workspaces **in progress** (default-on); Theme **D** Transcript karaoke MVP. Screenshot workflow walkthroughs live under [workflows/](workflows/index.md).

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
| Maintainer acceptance | Manual acceptance + a11y/browser; severity-justified fixes | **done** 2026-08-07 (kit journeys closed; see [manual_acceptance_1_0.md](dev/manual_acceptance_1_0.md)) |
| Overview / results presentation | Retire Insights Analysis tab; redistribute into Summary / Speakers / Actions / Highlights — [overview_presentation_0_9_9.md](dev/overview_presentation_0_9_9.md) | **0.9.9** (Charts/Overview hierarchy residuals deferred) |
| Post-0.9.9 wave (interim) | Early 1.x A–D + operator UX — [post_0_9_9_shipped_overview.md](dev/post_0_9_9_shipped_overview.md) | **0.9.9.5** (pre-unfamiliar-user) |
| **Owner local folder cleanup** | Unambiguous library / `originals/` / inbox / recordings mounts — see **Now** above | **now (top priority)** |
| Unfamiliar-user → RC | Clean-room validation; clean-env soak; RTD slug (owner) | after folder cleanup (pre-RC) |

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

## 1.x themes (post-1.0)

After **1.0**, plan by **theme**, not by patch ID. Cut releases around coherent increments. Early capacity should usually favour themes that strengthen the analysis workbench users already have; capture/transcription and shell UX themes are deliberate product bets — design before build, with explicit invest/narrow/defer forks.

**Not required for 1.0** (unchanged): every backlog feature, PyPI, hosted SaaS, built-in transcription, highly polished website / PWA.

### Theme map

| Theme | Intent | Suggested timing |
|-------|--------|------------------|
| A. Insights & analysis quality | Stronger deterministic/hybrid insights; clearer result UX | Early 1.x |
| B. Corrections & transcript editing | Word-level propose/apply in the reader; studio as batch/review | Early 1.x — **done** ([corrections-viewer.md](runtime/corrections-viewer.md)) |
| C. High-interaction workspaces | Streamlit Components v2 for Speaker ID / Corrections (and later rich edit) | Near-term 1.x — **[~] in progress** (default-on; see [theme_c_workspaces_ccv2.md](dev/theme_c_workspaces_ccv2.md)) |
| D. Playback & reading UX | Karaoke-style word highlight; reader polish that Components unlock | With / after C — **[~] Transcript karaoke MVP** |
| E. Performance & hardware guidance | Run-time estimates; smarter model/backend recommendations | Early 1.x |
| F. Library & organisation | Transcript tagging; Groups interaction rules | Mid 1.x |
| G. Audio & recording workflows | Inline audio ± transcript merge; directory watcher | Mid 1.x (merge = former §1.2) |
| H. In-app transcription | Local NVIDIA Parakeet/Canary + Whisper; CUDA/CPU; YouTube ingest | Mid–late 1.x (product decision) |
| I. Installable / native-feeling shell | Honest local-install (PWA or wrapper); optional loopback API; custom SPA only after C evidence | Mid–late 1.x (depends on shell) |
| J. Local analytics layer (SQLite) | Derived query store for Speakers/Groups views | ~1.5 |
| K. External STT command generation | Broader copyable host CLIs until / beside theme H | Ongoing light |
| L. Polish & onboarding extras | Coach-marks, bundled demos, aesthetics — only if capacity | Anytime light |
| M. Research / citeable methods | Optional B4-style methods; multilingual beyond small subset | Later 1.x+ |
| N. Multi-provider LLM (opt-in) | OpenAI-compatible / LiteLLM gateway beyond Ollama; never silent cloud default | Mid–late 1.x |
| → 2.0 | Personal audio intelligence companion | Vision |

**GUI / shell path (post-1.0):** Streamlit remains the analysis workbench shell. Theme **C** is the escape hatch for workstation pages, not a prelude to abandoning Streamlit. A fully custom non-Streamlit UI is **architecturally feasible** (`app/` and `core/` are already UI-agnostic) but **timing-poor and high-cost** (no HTTP API today; dual-run of the Streamlit page surface and GUI tests dominates). Theme **I** owns installable-shell spikes and, if capacity exists after 1.0, the only reversible enabling step: a loopback application API over existing controllers. Escalate to a custom local frontend only after the Theme C evidence gate — see §C and §I.

Public positioning today: [comparison.md](comparison.md). Analysis backlog: [analysis_module_backlog_2026-07-17.md](dev/analysis_module_backlog_2026-07-17.md).

---

### A. Insights & analysis quality

Insights and related analysis presentation work for 1.0; do not freeze quality here.

Design: [theme_a_insights_quality.md](dev/theme_a_insights_quality.md).

- Stronger **deterministic** outputs (clearer, more useful non-LLM / hybrid insights; less noise)
- Reassess **GUI layout** for Insights and analysis result surfaces (hierarchy, scannability, what to show first)
- Align with Overview presentation polish from **0.9.9** where patterns overlap; keep LLM insights honestly labelled
- Revisit module-level insight eligibility / empty states so partial runs stay trustworthy
- Continue ranked deepen-in-place work from the analysis-module backlog as capacity allows (no 0.9.x-style freeze after 1.0 unless re-declared)

---

### B. Corrections & transcript editing

Corrections Studio remains the batch / review surface. **Theme B (Early 1.x) viewer propose/apply is implemented:** Transcript viewer Correct mode supports word/span propose, atomic auto-accept, and scoped sidecar apply without silent overwrite of the managed original.

- Free-read the transcript and propose corrections at **word level** (not only current studio flows) — **done** (Correct mode)
- Prefer building word-level propose/apply into the **Transcript viewer** (read → select word/span → propose) so correction is part of reading, not a separate dead-end — **done**
- Keep Corrections Studio as the batch / review surface or fold it into viewer workflows after design — **Studio retained**; Start/Resume no longer auto-generates
- Honesty: mixed auto/assist quality must stay labelled; no silent overwrite of canonical text without clear apply/review — **sidecar + provenance; scoped apply**

Follow-ons: Components v2 click-drag selection (theme **C**); karaoke timings honesty already aligned with null timings on edited tokens (theme **D**).

See also [docs/runtime/corrections-viewer.md](runtime/corrections-viewer.md).

---

### C. High-interaction workspaces (Streamlit Components v2)

Speaker ID is reaching Streamlit’s architectural edge; TranscriptX as a whole is not. Streamlit remains a strong fit for analysis pages (select files, launch modules, tables/charts, compare runs, review artefacts) where a brief rerender is fine. Speaker Identification is becoming a stateful media-annotation workstation — rapid playback, editing, navigation, background clip prep, keyboard-like interaction, persistent local state, partial UI updates — exactly where Streamlit’s rerun model fights you.

**Pre-1.0 stop line:** finish current low-risk Speaker ID fixes until naming/navigation feel acceptably immediate, playback no longer visibly disrupts the whole app, writes are robust and tested, and cold clips have a tolerable fallback. Do **not** pursue endless nested fragments or speculative cache layers merely to remove the last flicker. Do **not** rewrite TranscriptX or abandon Streamlit before 1.0.

**1.x plan:** keep Streamlit as the application shell. Allow a small category of high-interaction workspaces to escape ordinary Streamlit widget trees: **Speaker Identification**, **Corrections Studio**, and possibly rich transcript editing later. Prototype a **Streamlit Components v2** Speaker ID surface against the existing controller. The component owns persistent audio player, play/pause/seek, sample-row paging, active-speaker selection, name input, keyboard shortcuts, optimistic navigation, and loading/disabled states. Python keeps transcript/sidecar reading, mapping mutations, profile creation, voice analysis, clip extraction, validation/locking, and domain services. Meaningful actions still cause Python reruns; routine browser-side interactions can stay local. If it works, migrate only interaction-heavy workspaces. Avoid wholesale jumps to Gradio/NiceGUI.

**Trajectory:** Streamlit shell + Python domain services + specialised frontend components for workstation-like interactions. CCv2 workspaces are the prototype of any later custom UI (browser owns ephemeral UI and media; Python owns transcripts, sidecars, mappings, clips, validation). They are not a commitment to retire Streamlit.

**Implementation status (2026-08):** Phase −1 `SpeakerIdActionService` shared by legacy + CCv2; non-blocking ClipService APIs; packaged `transcriptx-workspaces` CCv2 Speaker ID surface (**default-on**; rollback with `TX_SPEAKER_ID_WORKSPACE_COMPONENT=0`; missing package falls through to legacy); Corrections revisioned command protocol wired through `CorrectionsActionService` on the legacy studio page; PlaybackHost handoff for Theme D; legacy fragment path retained until Phase 9 criteria. Design authority: [theme_c_workspaces_ccv2.md](dev/theme_c_workspaces_ccv2.md).

**Shell review (2026-08):** The analysis engine is already UI-agnostic (`app/` workflows/controllers and `core/` have no Streamlit imports). The Streamlit GUI is a large mature surface (~55k Python lines under `web/`; ~100 files import Streamlit; ~40k lines of `tests/web`). There is **no HTTP or IPC application API** to hang a second client on. Analysis/settings pages remain a good Streamlit fit; workstation pages are the constraint Theme C already names. A full custom frontend is a **late 1.x / 2.0-scale** programme (parity plus dual-run), not an early-1.x rewrite. First escalation, if CCv2 remount/bytes/focus limits block product goals: loopback API over existing controllers (theme **I**), then grow workspaces off Streamlit hosting — not a new Python GUI toolkit and not an OS-native (Swift/Qt) workbench.

**Evidence gate before SPA / shell rewrite:** written invest/narrow/defer after Speaker ID Phase 9 and a Corrections CCv2 prototype. Escalate only with measured remount, bytes, or focus failures — [theme_c_workspaces_ccv2.md](dev/theme_c_workspaces_ccv2.md) § Invest / narrow / defer. Do not start a second primary GUI while Streamlit remains the supported surface in [public_surfaces.md](public_surfaces.md).

---

### D. Playback & reading UX

Builds on theme C (and existing playback surfaces). Inspired by polished self-hosted readers (e.g. Scriberr); keep analysis-first — do not become a notes-only app.

**Implementation status (2026-08):** Transcript viewer MVP landed — browser-local karaoke clip player with word-by-word highlight when imported `words[]` timings cover the clip; segment-level highlight + honesty caption when timings are missing/edited-null; Playing badge + follow-along scroll; seek-from-word inside the karaoke panel; `TranscriptKaraokeHost` implements the PlaybackHost contract without streaming `current_time` to Python. Continuous full-file karaoke and CCv2-native reader surface remain follow-ons.

- **Karaoke-style playback** — synchronised **word-by-word** (or tight span) highlighting during audio playback; seek-from-text ↔ seek-from-audio. Requires reliable word-level timings in imported or in-app transcripts. **[x] clip-scoped MVP in Transcript** · [ ] continuous media / full-file seek
- Follow-along scrolling, clearer active-segment emphasis, and annotation/highlight affordances that do not fight Streamlit reruns (prefer Components v2 where needed) — **[~] Playing emphasis + scroll on ▶**; CCv2-native reader polish still open
- Honesty: degrade gracefully when word timings are missing (segment-level only); never invent timings — **[x]**

---

### E. Performance & hardware guidance

Beyond 1.0 resource envelopes: help users plan and choose runs on *their* machine.

- Realistic **time estimates** for analysis runs given detected hardware (CPU/GPU/memory, install profile)
- **Smarter model recommendations** (which backend/size/settings fit this hardware and workload without over-promising)
- Keep estimates labelled as guidance; do not block runs on uncertain forecasts
- Reuse the same hardware-detection honesty when theme **H** lands (STT backend / CUDA vs CPU recommendations)

---

### F. Library & organisation

- **Transcript tagging** — library visibility / kind labels (e.g. `meeting`, `voice note`, `lone speaker`). Tags are organisation metadata, not an analysis module.

  **Design before build — interaction with Groups:** tags and groups must stay distinct. Tags find/filter/surface individual transcripts; Groups are analysis cohorts. Tagging must not create or imply group membership. Tags may filter the group member picker but must not auto-materialise a Group. Decide whether “more visible” means facet filters, pin/favourite, or both. Kind tags may later feed soft suitability hints; keep them optional metadata. Prefer transcript-local / library storage; keep tags out of group run schemas unless a deliberate filter snapshot is needed.

---

### G. Audio & recording workflows

#### G1. Audio / transcript merge (product decision; former §1.2)

Recorder devices often cut long sessions into chunks. Today:

- GUI **System → Tools → Merge** concatenates parts → one MP3 (ffmpeg); **Preprocessing** assesses/applies DSP before external transcription
- Host helpers `scripts/audio_merge.py` / `scripts/audio_preprocess.py` remain for CLI/automation (documented in [audio-prep.md](runtime/audio-prep.md))
- Serial-group prompts point operators at **System → Tools → Merge** before transcription

**Desired direction (design before build):** inline merge that (1) merges **audio** parts in order into one managed recording, and (2) optionally **stitches transcripts** (timestamp rebase, segment continuity, canonical + sidecars) when parts were already transcribed separately.

**Hard parts:** ordered part selection UX; ffmpeg/path honesty under Docker vs host; backup/overwrite; partial failure; duration vs transcript times; speaker-id continuity; managed-library admission; pre- vs post-transcription merge. Do not ship a half-merge that corrupts library identity.

**Decision fork:** **Invest** (first-class library/import workflow including transcript stitch) · **Defer / remove** (drop helpers). Audio-only GUI + CLI helpers are restored; transcript stitching remains undecided.

#### G2. Directory watcher

Automatically notice new recordings (and/or transcript files) in a monitored folder and offer or run admit/transcribe pipelines.

- **Phase 1 (landed):** default-off watcher service + Settings → Watcher; transcript **New → Import** via `admit_and_register`; audio **offer** queues `queued_transcription` (no STT yet). Ops guide: [runtime/directory_watcher.md](runtime/directory_watcher.md)
- Today: folder import also exists for **manual** transcript admission — watcher reuses the same admission primitives
- Design: watch scope, debounce + stability, size limits, failure surfacing, Docker bind-mount honesty, no silent library corruption
- Prefer explicit user enablement; default-off on shared machines
- **Next:** audio → host STT → import once theme **H** (or a host STT service) exists; optional host-side watcher helper if in-process lifecycle is insufficient

---

### H. In-app transcription (product decision)

**1.0 stance unchanged:** transcription remains **external**, with in-app **command generation** only. Built-in STT is **not** a 1.0 gate.

**1.x intent:** make local transcription a **supported product path** so the personal-recording journey (record/download → text → analyse) can stay inside TranscriptX when the user wants it — without abandoning BYO import or analysis-first positioning. Complementary tools ([Scriberr](https://scriberr.app/), [noScribe](https://noscribe.de/en/), [aTrain](https://github.com/aTrainTranscription/aTrain), [RiverScript](https://riverscript.com/), WhisperX, …) remain valid upstreams; see [comparison.md](comparison.md).

**Candidate capabilities (design before build):**

| Capability | Notes |
|------------|--------|
| **NVIDIA Parakeet / Canary + Whisper-class models** | User-selectable backends; accuracy/speed trade-offs documented; word-level timings where the stack supports them |
| **Hardware acceleration** | NVIDIA **CUDA** where available; optimised **CPU** path otherwise; Apple **MLX** remains a host/command path until a coherent native story exists |
| **YouTube transcription** | Paste a URL → download audio/video → local STT → managed import. Legal/ToS, yt-dlp (or equivalent) ops, size limits, and offline-default honesty are part of the design spike |
| **Diarization** | Prefer optional/local; align speaker labels with Speaker ID / import contracts |
| **Job UX** | Queue, progress, cancel, retry; never block the analysis GUI on a stuck STT job. A durable job/progress channel (not Streamlit `session_state` alone) is also the prerequisite if theme **I** ever grows a second client |

**Architecture fork (decide early):**

1. **In-process / same-image STT** — simplest UX; heaviest Docker/image and GPU story  
2. **Host-side STT service** (Ollama-like: GUI orchestrates via HTTP; ML stays on host) — cleaner Docker analysis vs GPU split  
3. **Keep external-only + richer command gen** (theme **K**) — if in-app cost/risk stays too high

**Decision fork:** **Invest** (supported optional STT path + clear install profiles) · **Narrow** (Whisper-only or CUDA-Docker-only) · **Defer** (stay BYO + command gen). Do not half-ship a silent cloud STT. Prefer local models; optional remote APIs only with explicit user opt-in and labelling.

**Non-goals for this theme:** meeting bots that auto-join Zoom/Meet; becoming a chat-over-audio product; replacing the analysis module DAG.

---

### I. Installable / native-feeling shell

**1.0 stance unchanged:** Streamlit in the browser is the supported primary surface. An installable / native-feeling shell is **not** a 1.0 gate.

**What “native” means here:** TranscriptX stays a **local Python engine** (file-backed storage, optional local ML). A native-feeling product is a custom local client plus that process — not a Swift/Qt/WinUI rewrite of the analysis workbench, and not wrapping Streamlit in a webview as if that were a new UI.

**1.x intent:** honest local-install feel (home-screen / dock icon, dark/light polish) without faking an offline app while the Python server must be running.

**Candidate slices (design before build; later slices depend on earlier ones):**

| Slice | Notes |
|-------|--------|
| **PWA or thin wrapper around Streamlit** | Spike only. Streamlit’s hosting model is a design constraint; a credible PWA may be weak or impossible. A Tauri/Electron webview of the current GUI is a Theme I experiment, not a customised interface. |
| **Loopback application API** | Optional after 1.0 if capacity exists. Expose `app.controllers` / workflows over loopback HTTP (or equivalent IPC) with existing request models; add job ids and progress events. **Streamlit stays the only client** until the API is boring. This is the reversible enabling step for a later SPA — it does not retire Streamlit. |
| **Custom local SPA** | Only after the Theme **C** evidence gate (CCv2 remount/bytes/focus limits block product goals), or if installable-shell / theme **H** job UX cannot be honest on Streamlit. Grow `transcriptx-workspaces` (or equivalent) into the real UI; dual-run, then update [public_surfaces.md](public_surfaces.md) only when Streamlit is no longer primary. Treat as **late 1.x / 2.0-scale** (parity + GUI test rewrite), not an early-1.x cutover. |
| **Desktop wrapper after a real frontend** | Tauri/Electron (or equivalent) around the SPA + Python sidecar. Useful once slice 3 exists; wrapping Streamlit alone does not count as a custom UI. |

**Decision fork:** **Narrow** (honest PWA/wrapper spike around Streamlit; document limits) · **Invest in API** (loopback API, Streamlit remains primary) · **Defer SPA** (default until C evidence) · **Escalate** (custom frontend + wrapper) only with a written Theme C decision. Do not migrate to Gradio/NiceGUI to “escape” Streamlit.

**Non-goals for this theme:** retiring Streamlit before 1.0; two supported primary GUIs indefinitely; OS-native workbench rewrite; hosted multi-user frontend.

---

### J. Local analytics layer — SQLite (~1.5)

1.0 stays **file-backed**. First deliberate DB wave: a **local** query/analytics layer so longitudinal views stop paying full-scan / ad-hoc JSON costs — without hosted multi-tenant SaaS.

- Start with **SQLite** (or equivalent) as an **optional / derived** store, not a second source of truth for canonical transcripts
- First slice: **speaker-profile analytics views** and related B5 remainder (group gallery keyed by `profile_id`) — see analysis-module backlog
- File/sidecar layout remains the durable library contract; DB rebuildable from files
- Define sync/invalidation on import, profile edits, run finalize, and wipe before expanding beyond Speakers

**Out of scope unless redesign says otherwise:** remote Postgres/SaaS, multi-user auth, replacing the managed-file library with ORM rows, mandatory SQLite on day one of 1.0.

**Decision fork:** **Invest** · **Narrow** (Speakers indexes only) · **Defer again**.

---

### K. External STT command generation (bridge)

Until/beside theme **H**, keep improving **copyable host commands** on Transcribe Audio: whispermlx / whispermlx-missing (Apple MLX), WhisperX Docker, Whisper-WebUI, plus further CUDA Linux / CPU CLIs as needed. Still copy/run-on-host only (no in-container MLX; no silent orchestration). Import remains the GUI admission gate for BYO files.

**Saved presets:** Transcribe Audio can save/load/delete command-gen form presets under `.transcriptx/profiles/stt_commands/` (host paths and flags only — never `HF_TOKEN`; tokens stay in `whisperx.env`).

---

### L. Polish & onboarding extras

Only if capacity remains after core themes:

- Elaborate guided coach-mark tour (if still needed after docs + clear GUI)
- Large bundled completed demo runs (if risky at 1.0, revisit later)
- Archive taxonomy refinements; aesthetic polish
- Specialist convenience and non-supported configurations

---

### M. Research / citeable methods (later)

- Multilingual routing beyond a small reliable subset
- Optional B4 ConvoKit-family / citeable research methods as **non-default** packs — see analysis-module backlog §3.2
- Not product defaults for early 1.x

---

### N. Multi-provider LLM (opt-in)

**1.0 stance unchanged:** optional local AI is **Ollama-only** (`provider=ollama`). Analysis modules already use a pluggable `LLMClient`; the factory and UI (model tags, presets, thinking-model gates) are Ollama-specific.

**1.x intent:** let operators optionally call **other LLM providers** (OpenAI, Anthropic, Azure, Bedrock, vLLM, …) without rewriting each LLM analysis module — while staying **local-first** and never making cloud the silent default.

**Candidate approach (design before build):**

| Piece | Notes |
|-------|--------|
| **OpenAI-compatible `LLMClient`** | New provider (e.g. `openai_compatible`) behind the existing `generate` / `is_available` interface; map JSON consumers to `response_format` (or equivalent) |
| **LiteLLM (or equivalent) gateway** | Prefer a **sidecar / proxy** ([LiteLLM](https://github.com/BerriAI/litellm)) over embedding the full SDK in the analysis image; one `base_url` reaches many backends |
| **Keep Ollama as default path** | Do not force local traffic through the gateway; Settings / Run Analysis Ollama UX stays for `provider=ollama` |
| **Model selection honesty** | Free-form model ids (and/or gateway catalog) when not on Ollama tags; clear labelling that remote endpoints receive transcript content |
| **Privacy / trust** | Explicit opt-in only; document remote data flow; align with [trust_privacy_model_governance_1_0.md](dev/trust_privacy_model_governance_1_0.md) |

**Hard parts:** structured JSON parity with Ollama `format=json`; seed/reproducibility across vendors; long timeouts and large prompts vs cloud limits; Corrections Studio + Run Analysis pickers that today assume `/api/tags`; dependency/image weight if the SDK is in-process.

**Decision fork:** **Invest** (OpenAI-compatible client + optional LiteLLM compose service) · **Narrow** (single remote OpenAI-compatible endpoint, no multi-vendor catalog) · **Defer**. Do not ship cloud LLM as a silent default (that remains deferred below).

**Non-goals for this theme:** replacing Ollama as the recommended local path; hosted multi-tenant LLM SaaS; chat-over-corpus as the primary product.

---

## 2.0 vision

**Personal audio intelligence companion:** personal recordings, voice-note workflows, optional local STT, deeper conversational analytics, stronger local AI — still local-first and modular. Themes **G–I** (recording workflows, in-app transcription, installable shell) are the main 1.x bridges toward that vision; themes **A–F** and **J** keep the analysis workbench excellent on the way; theme **N** optionally widens LLM backends without abandoning local-first. A **custom local frontend** (theme **I** escalate) belongs here if the companion needs installable-desktop feel that Streamlit + CCv2 cannot provide — it is not a 1.x default.

---

## Deferred / out of near-term scope

Still **not** near-term product goals (unless a later roadmap rewrite says otherwise):

- Meeting bots / auto-join Zoom–Meet–Teams capture
- Hosted multi-user SaaS analysis; CRM / revenue-pipeline platforms
- Chat-over-corpus / RAG meeting assistant as the primary product
- Cloud STT or cloud LLM as **silent defaults** (explicit opt-in multi-provider LLM is theme **N**)
- Mode systems that duplicate page logic
- Elaborate interactive marketing-website effects
- Broader “everything in the DB” library migration (beyond theme **J**)
- Wholesale GUI rewrite or migration to Gradio/NiceGUI (prefer Components v2 first — theme **C**)
- Full custom local frontend replacing Streamlit (late 1.x / 2.0; only after the Theme **C** evidence gate; loopback API first — theme **I**; not an early-1.x project)
- OS-native workbench rewrite (Swift / Qt / WinUI) — the engine stays Python; a sidecar + custom web client is the native path if one is needed

Historical sprint dumps: [sprint_archive.md](archive/plans/sprint_archive.md) (archived).

---

## Engineering backlogs

- [analysis_module_backlog_2026-07-17.md](dev/analysis_module_backlog_2026-07-17.md)
- [DEV_INDEX.md](DEV_INDEX.md) · [archive/ARCHIVE_INDEX.md](archive/ARCHIVE_INDEX.md)
- [release_governance.md](dev/release_governance.md)
- [release_severity_triage_1_0.md](dev/release_severity_triage_1_0.md)
- Phase 0B planning stubs: [docs_architecture_1_0.md](dev/docs_architecture_1_0.md), [install_profiles_matrix.md](dev/install_profiles_matrix.md), [manual_acceptance_1_0.md](dev/manual_acceptance_1_0.md), [analysis_quality_audit.md](dev/analysis_quality_audit.md) (Guided/demo design stubs retired after trial)
