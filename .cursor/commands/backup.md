# Backup workspace (# backup)

Back up all code from the workspace to a date-stamped zip file, excluding gitignored and library/cache content.

Execute from the repository root. Resolve paths relative to the repo — do **not** hard-code a personal home directory.

---

## What to do

1. **Resolve backup path and date**
   - `REPO_ROOT` = current workspace / git root (e.g. `$(git rev-parse --show-toplevel)` or `$PWD` when already at root)
   - Base directory: `"$REPO_ROOT backup"` (sibling folder next to the repo, same basename + ` backup`)
   - Archive name: `YYMMDD.zip` (e.g. `250306.zip` for 6 Mar 2025). Use shell: `date +%y%m%d`
   - Full destination: `"$REPO_ROOT backup/YYMMDD.zip"`

2. **Create destination**
   - Create the base directory if it does not exist.
   - **Do not overwrite** an existing zip; if `YYMMDD.zip` already exists, use a suffix like `YYMMDD-HHMM.zip`.

3. **Create zip (code only — exclude data, models, caches)**
   - Stage filtered files to a temp directory, then zip and remove the staging dir.
   - **Goal:** source code, config, docs, and tests — not user data, model weights, or generated artifacts.
   - **Expected size:** ~2–5 MB compressed (~10–15 MB uncompressed). Small zips are correct; old subfolder backups were huge because they copied `data/`, `.test_outputs/`, and model caches.
   - **Foundational paths (must end up in the zip):** `src/`, `tests/`, `scripts/`, `docs/`, `assets/`, root manifests (`pyproject.toml`, `requirements*.txt`, `Dockerfile`, `docker-compose*.yml`, `Makefile`, `pytest.ini`, `.env.example`), and `.cursor/commands/`.
   - **Always exclude** (these dominate backup size if included):
     - `data/` — recordings, caches, model weights (`data/cache/voice` is ~7 GB), corrections, outputs
     - `.test_outputs/` — local test run artifacts (~20 GB)
     - `.release-test-env/`, `.docs-verify-venv/`, `.local/` — disposable / local scratch
     - `processing_state/`, `transcriptx_data/`, `outputs/`, `.transcriptx/`
     - `.git`, `node_modules`, `__pycache__`, `.venv`, `venv`, `env`, `.env`
     - `.pytest_cache`, `.mypy_cache`, `.ruff_cache`
     - `*.pyc`, `*.pyo`, `*.egg-info`, `dist/`, `build/`
     - Model / weight files anywhere: `*.pt`, `*.pth`, `*.bin`, `*.onnx`, `*.safetensors`
     - `.DS_Store`, `*.log`, `*.tmp`, `.coverage`, `coverage.xml`, `coverage.json`, `htmlcov/`
   - Also apply patterns from `.gitignore` via `--exclude-from`.
   - **Use a suffix when the date-zip already exists** (run from repository root):
     ```bash
     REPO_ROOT="$(git rev-parse --show-toplevel)"
     BACKUP_ROOT="${REPO_ROOT} backup"
     STAMP=$(date +%y%m%d)
     ZIP_PATH="$BACKUP_ROOT/${STAMP}.zip"
     if [ -f "$ZIP_PATH" ]; then
       STAMP=$(date +%y%m%d-%H%M)
       ZIP_PATH="$BACKUP_ROOT/${STAMP}.zip"
     fi
     mkdir -p "$BACKUP_ROOT"
     STAGING=$(mktemp -d "${TMPDIR:-/tmp}/tx-backup.XXXXXX")
     rsync -a \
       --exclude='.git' \
       --exclude='data' \
       --exclude='.test_outputs' \
       --exclude='.release-test-env' \
       --exclude='.docs-verify-venv' \
       --exclude='.local' \
       --exclude='processing_state' \
       --exclude='transcriptx_data' \
       --exclude='outputs' \
       --exclude='.transcriptx' \
       --exclude='node_modules' \
       --exclude='__pycache__' \
       --exclude='.venv' \
       --exclude='venv' \
       --exclude='env' \
       --exclude='.pytest_cache' \
       --exclude='.mypy_cache' \
       --exclude='.ruff_cache' \
       --exclude='*.pyc' \
       --exclude='*.egg-info' \
       --exclude='dist' \
       --exclude='build' \
       --exclude='*.pt' \
       --exclude='*.pth' \
       --exclude='*.bin' \
       --exclude='*.onnx' \
       --exclude='*.safetensors' \
       --exclude='.DS_Store' \
       --exclude='.coverage' \
       --exclude='coverage.xml' \
       --exclude='coverage.json' \
       --exclude='htmlcov' \
       --include='src/***' \
       --include='tests/***' \
       --include='scripts/***' \
       --include='docs/***' \
       --include='assets/***' \
       --include='archive/***' \
       --include='artifacts/***' \
       --include='reports/***' \
       --include='.cursor/***' \
       --include='*.md' \
       --include='*.toml' \
       --include='*.txt' \
       --include='*.yml' \
       --include='*.yaml' \
       --include='*.ini' \
       --include='*.sh' \
       --include='*.example' \
       --include='Makefile' \
       --include='Dockerfile' \
       --include='LICENSE' \
       --include='.coveragerc' \
       --include='.dockerignore' \
       --include='.gitignore' \
       --include='TranscriptX.code-workspace' \
       --exclude='*' \
       --exclude-from='.gitignore' \
       . "$STAGING/"
     (cd "$STAGING" && zip -rq "$ZIP_PATH" .)
     rm -rf "$STAGING"
     # Verify foundational paths made it into the archive
     for req in src/transcriptx tests scripts pyproject.toml requirements.txt docs; do
       unzip -l "$ZIP_PATH" | grep -q "$req" || { echo "BACKUP VERIFY FAILED: missing $req in $ZIP_PATH"; exit 1; }
     done
     ```

4. **Back up Cursor custom commands to the backup folder**
   - Create `custom-commands` in the backup root (not inside the zip): `mkdir -p "$BACKUP_ROOT/custom-commands"`.
   - Copy the contents of `.cursor/commands/` into it (e.g. `rsync -a .cursor/commands/ "$BACKUP_ROOT/custom-commands/"` from repository root).
   - This keeps the latest command `.md` files at `"$REPO_ROOT backup/custom-commands/"` for easy restore or inspection.

5. **Confirm**
   - After the command, report: zip path (under `"$REPO_ROOT backup/"`), file size (`ls -lh`), and that it completed successfully.

---

## Execution rules

- Run from repository root (`REPO_ROOT`).
- Do not delete or modify the existing workspace; only create the backup zip and update `custom-commands/`.
- If staging, zip, or cleanup fails, report the error and do not assume success (remove any leftover staging dir under `/tmp` if present).
