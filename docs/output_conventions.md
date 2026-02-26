# Output conventions

Single reference for output directory layout, artifact naming, and versioned namespaces. Implementation lives in `src/transcriptx/core/utils/output_standards.py` and `src/transcriptx/core/utils/path_utils.py`.

## Directory layout

- **Run root:** For a transcript at `.../foo.json`, outputs live under `outputs/<transcript_dir>/` (or a custom base). The run root is a timestamped directory `YYYYMMDD_HHMMSS_<hash>/` containing module subdirs and `manifest.json`, `run_results.json`.
- **Per-module:** Each analysis module writes under `<run_root>/<module_name>/` unless it uses a versioned namespace (see below).
- **Standard subdirs (per module):** `data/`, `charts/`, `global/`, `speakers/` as created by `create_standard_output_structure()` in `output_standards.py`.

## Versioned namespaces

Modules that need a stable, versioned contract write under `<run_root>/<namespace>/<version>/`. Example: voice artifacts use `voice/v1/` so that future changes can introduce `voice/v2/` without breaking consumers. See `ModuleInfo.output_namespace` and `output_version` in `module_registry.py`.

## Artifact naming

- **Canonical base name:** From `path_utils.get_base_name(transcript_path)` (filename without extension). Used for run directories and file prefixes.
- **Manifest and run summary:** `manifest.json` and `run_results.json` at run root. Built by `manifest_builder.py`; schema validated in tests (see `run_schema.py` and `tests/contracts/test_run_results_and_manifest_contracts.py`).
- **Module data/charts:** Use `create_standard_output_structure()` and the helpers in `output_standards.py` (e.g. `save_global_data`, `save_speaker_data`) so paths stay consistent.

## Single canonical path source

New code should use `path_utils` and `output_standards` only. Do not build output paths manually; use `get_transcript_dir()`, `get_module_output_dir()`, and `create_standard_output_structure()` so there is one canonical way.

## Stability (v0.42+)

- Do not rename output folders or top-level layout without versioning (prefer versioned namespaces for new layouts).
- Do not change `manifest.json` or run results schema without bumping version or documenting migration.
