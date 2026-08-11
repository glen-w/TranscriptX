Type: GUIDE
Authority: docs/runtime/STORAGE.md + docs/public_surfaces.md

# Settings, profiles, and analysis knobs

How to change TranscriptX behaviour from the GUI, env, and config files — without mixing up the several things named “profile”.

## Where to start

| Goal | Where |
|------|--------|
| Everyday analysis depth (which modules run) | **Run Analysis** preset: Quick / Balanced / Thorough / Custom — edit policies under **Settings → Analysis** |
| Common model and similarity knobs | **Settings → Configuration** → Common Settings |
| Full registry of knobs | **Settings → Configuration** → enable **Show advanced/raw settings editor** |
| Named module/workflow presets (disk JSON) | **Profiles** page (sidebar) — activate from Configuration for Project / Run |
| Paths, watcher, speakers, LLM models, questions | Other **Settings** tabs (Storage, Watcher, Speakers, Interface, Models, Questions, Corrections) |
| Install capability (`core` vs `full`) | Env / install marker — see [installation.md](installation.md); **not** the Profiles page |

Speaker identity/voice stores are a separate subsystem (Settings → Speakers). See [speaker_profiles_v1](../contracts/speaker_profiles_v1.md) and [STORAGE.md](STORAGE.md).

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

- **Common Settings** are a curated allowlist (`COMMON_SETTINGS_SCHEMA`): models, semantic similarity, a few workflow/output/display keys.
- **Advanced/raw** exposes every registered config leaf (except profile activation keys). Registry fields may mark `advanced=True` for documentation; the GUI does not yet use that flag to partition the form — the toggle is the partition.
- Prefer Common or Analysis presets unless you know why a leaf matters.

## “Profile” taxonomy (do not conflate)

| Name | Meaning | Surface |
|------|---------|---------|
| **Install profile** | `core` \| `full` capability / dep story | `TRANSCRIPTX_CORE`, `{config_dir}/install_profile`, [install_profiles_matrix.md](../dev/install_profiles_matrix.md) |
| **Analysis UI preset** | Quick / Balanced / Thorough module sets | Run Analysis + Settings → Analysis |
| **Module / workflow profile** | Named JSON under `{config_dir}/profiles/<target>/` | Profiles page + Active Profiles in Configuration |
| **In-config semantic profiles** | Mapping `analysis.semantic_similarity_profiles` (`fast` / `balanced` / `deep`) | Advanced config / code — shares activation key naming with disk profiles; different store |
| **STT command / UI layout profiles** | Other named JSON under `profiles/` | Transcribe Audio / layout store |
| **Speaker profile** | Longitudinal identity (+ optional voice) | Settings → Speakers — **out of scope** for knob docs |

Tracked files under repo `data/profiles/*/default.json` are **fixtures / allowlisted samples**. Runtime defaults are virtual (dataclass/Pydantic); ProfileManager does not treat disk `default` as loadable user presets. Runtime profiles live under `{config_dir}/profiles/` (override with `TRANSCRIPTX_PROFILES_DIR`).

## Env overrides

Copy [`.env.example`](../../.env.example) to `.env`. Infra path keys (`TRANSCRIPTX_*_DIR`, host/port, downloads, …) are separate from config-bag overrides. Set `TRANSCRIPTX_CONFIG_STRICT=1` to reject unknown `TRANSCRIPTX_*` keys.

Legacy `TRANSCRIPTX_AUDIO_*_ENABLED` variables are **rejected** — use the corresponding `*_MODE` keys.

## Related docs

- [installation.md](installation.md) — install profiles and Analysis presets
- [STORAGE.md](STORAGE.md) — config_dir layout and precedence
- [models.md](models.md) / [llm.md](llm.md) — model and Ollama knobs
- Developer architecture: [config_architecture.md](../dev/config_architecture.md)
- Assessment / backlog: [settings_knobs_assessment.md](../dev/settings_knobs_assessment.md)
