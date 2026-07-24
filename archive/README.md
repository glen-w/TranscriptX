# Archive

This directory contains **non-production**, **historical**, or **one-off** scripts and artifacts.

**Canonical script archive location:** `archive/scripts/` (not `scripts/archive/`).

- Items under `archive/scripts/` are kept for reference only.
- They are **not** part of the supported TranscriptX API surface.
- They may be outdated, rely on ad hoc environments, or encode assumptions that no longer hold.
- Archived scripts must include an `[ARCHIVED]` banner in the header and must not appear on normal PATHs, packaging manifests, Docker images, or user-facing docs.

When in doubt, prefer the main `scripts/`, documented workflows in `README.md`, `docs/developer_quickstart.md`, and `Makefile` over anything in `archive/`.

See also: [docs/dev/script_inventory_1_0.md](../docs/dev/script_inventory_1_0.md).

## Contents

| Script | Notes |
|--------|-------|
| `validate_dependencies.py` | Historical dependency validator |
| `validate_transcript_storage.py` | Historical storage layout check |
| `run_tests_with_timeout.py` | Historical timeout test runner |
| `build_docs.sh` | Stale Sphinx builder (missing `docs/conf.py` at archive time) |
