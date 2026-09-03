# Settings, profiles, and analysis knobs

How to change TranscriptX behaviour from the GUI, env, and config files — without mixing up the several things named “profile”.

## Where to start

| Goal | Where |
|------|--------|
| Everyday analysis depth (which modules run) | **Run Analysis** preset: Quick / Balanced / Thorough / Custom — edit policies under **Settings → Analysis** |
| Charts page **Overview** strip (which charts, order) | **Settings → Configuration** → **Charts overview** (`dashboard.overview_charts`) — not Dashboard Builder |
| Overview / Insights **page panels** (layout profiles) | **Settings → Dashboard Builder** — see [dashboard_builder.md](../dev/dashboard_builder.md) |
| Common model and similarity knobs | **Settings → Configuration** → Common Settings |
| Full registry of knobs | **Settings → Configuration** → enable **Show advanced/raw settings editor** |
| Named module/workflow presets (disk JSON) | **Profiles** page (sidebar) — activate from Configuration for Project / Run |
| Paths, watcher, speakers, LLM models, questions | Other **Settings** tabs (Storage, Watcher, Speakers, Interface, Models, Questions, Corrections) |
| Duplicate recordings / transcripts | **Settings → Storage** → Duplicate library files (preview, then typed `DELETE DUPLICATES`) |
| Show/hide instructional ⓘ tips (widget help + Speakers methodology notes) | **Settings → Interface** → Help / info tips (`show_info_tooltips` in `interface_menus.json`; run-id ⓘ stays on) |
| Action-menu icon vs text | **Settings → Interface** → Action appearance (`action_display`: `icon` / `text` / `both`; per-section may `inherit`) |
| Install capability (`core` vs `full`) | Env / install marker — see [installation details](installation-advanced.md); **not** the Profiles page |

Speaker identity/voice stores are a separate subsystem (Settings → Speakers). See [speaker_profiles_v1](../contracts/speaker_profiles_v1.md) and [STORAGE.md](STORAGE.md).

## Analysis presets

When you run analysis, choose a **Preset** that determines which modules run:

- **Quick** — no LLM modules and no heavy modules (fast local path). Modules that hard-depend on excluded heavy/LLM modules are omitted so the DAG cannot pull them back in.
- **Balanced** — recommended default: non-heavy modules plus a limited heavy allowlist (`semantic_similarity`, `fine_grained_emotion`) and **global transcript LLM summary only** (`llm_summary`).
- **Thorough** — all suitable modules for the target (including LLM and heavy).
- **Custom** — pick exactly which modules to run for this launch.

Edit Quick / Balanced / Thorough policies (and optional full module overrides) under **Settings → Analysis**. Mode `quick` vs `full` still controls depth knobs (semantic/NER limits) for the chosen preset.

### Single-speaker / unnamed-speaker behavior

By default, modules require **human-named** speakers. Diarized placeholders (`SPEAKER_00`, …) do not count until you name speakers in Speaker Identification. Modules that need multiple speakers (conversation loops, contagion, interactions, semantic similarity, Q&A, echoes, and others) skip when the named-speaker count is below their minimum. For group runs, the module list is filtered by the minimum named speaker count across members.

To run modules on diarized labels without naming speakers:

- **Global:** Settings → `analysis.allow_unnamed_speakers` (or env `TRANSCRIPTX_ANALYSIS_ALLOW_UNNAMED_SPEAKERS`)
- **Per run:** Run Analysis checkbox **Allow analysis without named speakers**

Either knob ungates the pipeline (global **or** per-run). When ungated, speaker-count gates use turn-taking labels and per-speaker artifacts include unidentified speakers.

## Configuration scopes

Effective config for a run merges layers (highest wins first):

1. Environment (`TRANSCRIPTX_*`)
2. Run override (or Draft override when no run is selected)
3. Project `config.json`
4. Built-in defaults (plus active module/workflow profiles loaded into the runtime facade)

Authoritative precedence and path roots: [STORAGE.md](STORAGE.md).

In **Settings → Configuration**:

| Scope | Editable? | Persists to |
|-------|-----------|-------------|
| Default | Read-only | — |
| Project | Yes | `{config_dir}/config.json` |
| Draft override | Yes (no Active Profiles) | `{config_dir}/drafts/...` |
| Run override | Yes (needs a run selected) | under the run directory |

Draft overrides are reported with run-layer provenance (`source: run`) by design — see STORAGE.

## Common vs advanced knobs

- **Charts overview** (Configuration, edit mode): checkbox + ordered list for `dashboard.overview_charts`. Empty list → registry defaults for the run kind (transcript vs group). See [group_charts_default_overview.md](../groups/group_charts_default_overview.md).
- **Common Settings** are a curated allowlist (`COMMON_SETTINGS_SCHEMA`): models, semantic similarity, a few workflow/output/display keys.
  - Speakers: `analysis.allow_unnamed_speakers` — when on, analysis runs on diarized labels (`SPEAKER_00`, …) without naming; default off. Per-run override: Run Analysis checkbox.
- **Advanced/raw** exposes every registered config leaf (except profile activation keys). Registry fields may mark `advanced=True` for documentation; the GUI does not yet use that flag to partition the form — the toggle is the partition.
- Prefer Common or Analysis presets unless you know why a leaf matters.

## Smart rename (device filenames)

Settings → Configuration → **Rename** (also under Advanced as `input.*`):

| Knob | Default | Meaning |
|------|---------|---------|
| `input.smart_rename_mode` | `suggest_import` | `auto_import` / `suggest_import` / `suggest_rename_only` / `off` |
| `input.smart_rename_pattern` | `{yymmdd}_{period}_{n}` | Deterministic template rendered from the recording datetime |
| `input.prefill_rename_with_date_prefix` | `true` | Legacy YYMMDD_ + stem prefill when smart mode is `off` |

Supported pattern tokens: `{yymmdd}`, `{yyyymmdd}`, `{yyyy}`, `{yy}`, `{mm}`, `{dd}`, `{hhmmss}`, `{hhmm}`, `{hh}`, `{period}` (`morning`/`afternoon`/`evening`/`night`), `{n}` (collision sequence), `{stem}`.

Device stems understood include `RYYYYMMDD-HHMMSS`, `YYYYMMDDHHMMSS`, and `YYMMDD-HHMMSS`. In rename forms, the date root is prefilled and other tokens appear as clickable append buttons.

## “Profile” taxonomy (do not conflate)

| Name | Meaning | Surface |
|------|---------|---------|
| **Install profile** | `core` \| `full` capability / dep story | `TRANSCRIPTX_CORE`, `{config_dir}/install_profile`, [install_profiles_matrix.md](../dev/install_profiles_matrix.md) |
| **Analysis UI preset** | Quick / Balanced / Thorough module sets | Run Analysis + Settings → Analysis |
| **Module / workflow profile** | Named JSON under `{config_dir}/profiles/<target>/` | Profiles page + Active Profiles in Configuration |
| **In-config semantic profiles** | Mapping `analysis.semantic_similarity_profiles` (`fast` / `balanced` / `deep`) | Advanced config / code — shares activation key naming with disk profiles; different store |
| **UI layout profiles** | Ordered blocks for Overview / Insights | Settings → Dashboard Builder (`profiles/ui_layouts/`) — not Charts overview |
| **STT command profiles** | Named JSON under `profiles/` | Transcribe Audio |
| **Merge source profile** | Match + day/gap rules for Tools → Merge suggestions / auto-merge | Merge tab expander; `{config_dir}/audio_merge_profiles.json` |
| **Merge dismissed groups** | Auto-merge **Don't suggest again** keys (rule + stem) | Auto-merge tab; `{config_dir}/audio_merge_dismissed.json` |
| **Speaker profile** | Longitudinal identity (+ optional voice) | Settings → Speakers — **out of scope** for knob docs |

Tracked files under repo `data/profiles/*/default.json` are **fixtures / allowlisted samples**. Runtime defaults are virtual (dataclass/Pydantic); ProfileManager does not treat disk `default` as loadable user presets. Runtime profiles live under `{config_dir}/profiles/` (override with `TRANSCRIPTX_PROFILES_DIR`).

## Env overrides

Copy [`.env.example`](../../.env.example) to `.env`. Infra path keys (`TRANSCRIPTX_*_DIR`, host/port, downloads, …) are separate from config-bag overrides. Set `TRANSCRIPTX_CONFIG_STRICT=1` to reject unknown `TRANSCRIPTX_*` keys.

Legacy `TRANSCRIPTX_AUDIO_*_ENABLED` variables are **rejected** — use the corresponding `*_MODE` keys.

## Related docs

- [installation.md](installation.md) — normal install; [installation details](installation-advanced.md) — extras and install profiles
- [STORAGE.md](STORAGE.md) — config_dir layout and precedence
- [models.md](models.md) / [llm.md](llm.md) — model and Ollama knobs
- Developer architecture: [config_architecture.md](../dev/config_architecture.md)
- Assessment / backlog: [settings_knobs_assessment.md](../dev/settings_knobs_assessment.md)
