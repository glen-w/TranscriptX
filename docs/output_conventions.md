# Output conventions

**Authority:** For the formal output contract (layout, manifests, speaker exclusion), see **[docs/contracts/output-contract-v1.md](contracts/output-contract-v1.md)**.

This document remains a short reference. Implementation lives in `src/transcriptx/core/utils/output_standards.py` and `src/transcriptx/core/utils/path_utils.py`.

## Directory layout

- **Run root:** Outputs live under `outputs/<slug>/<run_id>/` where `slug` is the human-friendly folder name (from the slug manager) and `run_id` is `YYYYMMDD_HHMMSS_<hash>`. The run root contains module subdirs, `manifest.json`, and `run_results.json`. See [output-contract-v1.md](contracts/output-contract-v1.md) for the full contract.
- **Per-module:** Each analysis module writes under `<run_root>/<module_name>/` unless it uses a versioned namespace (see below).
- **Standard subdirs (per module):** `data/`, `charts/`, `global/`, `speakers/` as created by `create_standard_output_structure()` in `output_standards.py`.

## Versioned namespaces

Modules that need a stable, versioned contract write under `<run_root>/<namespace>/<version>/`. Example: voice artifacts use `voice/v1/` so that future changes can introduce `voice/v2/` without breaking consumers. See `ModuleInfo.output_namespace` and `output_version` in `module_registry.py`.

## Artifact naming

- **Canonical base name:** From `path_utils.get_canonical_base_name(transcript_path)` (used for run dir and file prefixes). See contract for naming rules.
- **Manifest and run summary:** `manifest.json` and `run_results.json` at run root. Built by `manifest_builder.py`; schema validated in tests (see `run_schema.py` and `tests/contracts/test_run_results_and_manifest_contracts.py`).
- **Module data/charts:** Use `create_standard_output_structure()` and the helpers in `output_standards.py` (e.g. `save_global_data`, `save_speaker_data`) so paths stay consistent.

## Single canonical path source

New code should use `path_utils` and `output_standards` only. Do not build output paths manually; use `get_transcript_dir()`, `get_module_output_dir()`, and `create_standard_output_structure()` so there is one canonical way.

## Stability (v0.41+)

- Do not rename output folders or top-level layout without versioning (prefer versioned namespaces for new layouts).
- Do not change `manifest.json` or run results schema without bumping version or documenting migration.
