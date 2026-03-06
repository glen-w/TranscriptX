# Output Contract v1

Single source of truth for TranscriptX analysis output layout, naming, manifest schemas, and speaker-exclusion rules. Implementation: `output_standards.py`, `manifest_builder.py`, `run_manifest.py`, `run_schema.py`.

## 1. Directory layout

- **Root:** `TRANSCRIPTX_OUTPUT_DIR` (default `{DATA_DIR}/outputs`).
- **Run root:** `outputs/<slug>/<run_id>/` where:
  - `slug` is the human-friendly folder name from the slug manager (derived from transcript identity).
  - `run_id` is `YYYYMMDD_HHMMSS_<8-char-uuid>` (or overridden via `RunManifestInput.run_id`).
- **Per run:** At run root:
  - `manifest.json` — artifact index (see §4).
  - `run_results.json` — run summary (schema in `run_schema.RunResultsSummary`).
  - `.transcriptx/manifest.json` — run manifest for reproducibility (`manifest_type: "run_manifest"`).
  - `.transcriptx/run_config_effective.json` — effective config snapshot.
- **Per module:** `<run_root>/<module_name>/` with standard subdirs:
  - `data/global/` — global (all-speaker) data files.
  - `data/speakers/` — per-speaker data (when applicable).
  - `charts/` (or `charts/global/`, `charts/speakers/`) — chart outputs.
- **Versioned namespaces:** Modules that need a stable contract use `<run_root>/<namespace>/<version>/` (e.g. `voice/v1/`). See `ModuleInfo.output_namespace` and `output_version`.

## 2. Naming rules

- **Canonical base name:** From `path_utils.get_canonical_base_name(transcript_path)` (used for run dir and file prefixes).
- **File prefixes:** Module artifacts use the canonical base name where applicable; e.g. `{base_name}_{module}_{descriptor}.{ext}` or as defined by `create_standard_output_structure()` and helpers in `output_standards.py`.
- **Manifest and run summary:** `manifest.json` and `run_results.json` at run root only.

## 3. Required artifacts and scope

- **Per-module:** Modules use `create_standard_output_structure()` and the helpers (`save_global_data`, `save_speaker_data`, `save_global_chart`, etc.) so paths stay consistent.
- **Global vs per-speaker:** Unidentified speakers (e.g. `SPEAKER_00`) are excluded from per-speaker outputs when `exclude_unidentified_from_speaker_charts` (or equivalent) is true. Exceptions: transcript/CSV output and NER include all speakers.
- **NER:** May use a distinct path for entity maps (e.g. `ner/maps/` or `ner/{base}_ner-entities.json`); see module implementation.

## 4. Manifest schemas

### 4.1 Artifact manifest (`manifest.json` at run root)

- **Discriminator:** `manifest_type: "artifact_manifest"` (required in new manifests; backward compat accepts missing as artifact).
- **Required keys:** `schema_version`, `run_id`, `run_metadata`, `artifacts`.
- **run_metadata:** Includes `transcript_key`, `modules_enabled`, `version_hash`, `config_effective_path`, `config_hash`, `config_schema_version`, `config_source`.
- **artifacts:** List of entries with `id`, `kind`, `rel_path`, `mime`, `tags`; optional `module`, `scope`, `speaker`. Load via `load_artifact_manifest(path)`; do not raw `json.load()` and guess type.

### 4.2 Run manifest (`.transcriptx/manifest.json`)

- **Discriminator:** `manifest_type: "run_manifest"`.
- Used for reproducibility. Load via `load_run_manifest(path)`.

## 5. Speaker exclusion (unidentified)

- **Default:** Unidentified speakers (e.g. `SPEAKER_00`) are excluded from per-speaker charts and per-speaker data when config says so (`analysis.exclude_unidentified_from_speaker_charts` or equivalent).
- **Included:** Transcript output, CSV export, and NER entity lists include all speakers (including unidentified).
- **Predicate:** `is_named_speaker()` in `text_utils` (or equivalent) determines eligibility for per-speaker outputs.

## 6. Schema stamps (transcript JSON)

- **Speaker mapping:** After any mapping write, transcript JSON must include:
  - `speaker_map_schema_version` (e.g. `"1.0"`).
  - `speaker_map_provenance` (tool, version, timestamp, method) when written via `SpeakerMappingService` / `TranscriptStore`.

## 7. Exceptions and versioning

- **NER:** Path variance allowed for entity maps; see NER module.
- **Voice:** Versioned namespace `voice/v1/` (and possible `voice/v2/` later).
- **Stability (v0.41+):** Do not rename output folders or top-level layout without versioning. Prefer versioned namespaces for new layouts.

---

*This document supersedes `output_conventions.md` as the authority for output layout and contracts. Keep `output_conventions.md` for backward reference or redirect to this file.*
