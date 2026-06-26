# Backup workspace (# backup)

Back up all code from the workspace to a date-stamped zip file, excluding gitignored and library/cache content.
Execute from the workspace root: `/Users/89298/Documents/transcriptx`.

---

## What to do

1. **Resolve backup path and date**
   - Base directory: `/Users/89298/Documents/transcriptx backup`
   - Archive name: `YYMMDD.zip` (e.g. `250306.zip` for 6 Mar 2025). Use shell: `date +%y%m%d`
   - Full destination: `/Users/89298/Documents/transcriptx backup/YYMMDD.zip`

2. **Create destination**
   - Create the base directory if it does not exist.
   - **Do not overwrite** an existing zip; if `YYMMDD.zip` already exists, use a suffix like `YYMMDD-HHMM.zip`.

3. **Create zip (code only — exclude data, models, caches)**
   - Stage filtered files to a temp directory, then zip and remove the staging dir.
   - **Goal:** source code, config, docs, and tests — not user data, model weights, or generated artifacts.
   - **Always exclude** (these dominate backup size if included):
     - `data/` — recordings, caches, model weights (`data/cache/voice` is ~7 GB), corrections, outputs
     - `.test_outputs/` — local test run artifacts (~20 GB)
     - `.release-test-env/`, `.docs-verify-venv/` — disposable virtualenvs
     - `processing_state/`, `transcriptx_data/`, `outputs/`, `.transcriptx/`
     - `.git`, `node_modules`, `__pycache__`, `.venv`, `venv`, `env`, `.env`
     - `.pytest_cache`, `.mypy_cache`, `.ruff_cache`
     - `*.pyc`, `*.pyo`, `*.egg-info`, `dist/`, `build/`
     - Model / weight files anywhere: `*.pt`, `*.pth`, `*.bin`, `*.onnx`, `*.safetensors`
     - `.DS_Store`, `*.log`, `*.tmp`, `.coverage`, `coverage.xml`, `coverage.json`, `htmlcov/`
   - Also apply patterns from `.gitignore` via `--exclude-from`.
   - **Use a suffix when the date-zip already exists** (run from workspace root):
     ```bash
     BACKUP_ROOT="/Users/89298/Documents/transcriptx backup"
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
       --exclude-from='.gitignore' \
       . "$STAGING/"
     (cd "$STAGING" && zip -rq "$ZIP_PATH" .)
     rm -rf "$STAGING"
     ```

4. **Back up Cursor custom commands to the backup folder**
   - Create `custom-commands` in the backup root (not inside the zip): `mkdir -p "$BACKUP_ROOT/custom-commands"`.
   - Copy the contents of `.cursor/commands/` into it (e.g. `rsync -a .cursor/commands/ "$BACKUP_ROOT/custom-commands/"` from workspace root).
   - This keeps the latest command `.md` files at `transcriptx backup/custom-commands/` for easy restore or inspection.

5. **Confirm**
   - After the command, report: zip path (e.g. `/Users/89298/Documents/transcriptx backup/250306.zip`), file size (`ls -lh`), and that it completed successfully.

---

## Execution rules

- Run from workspace root: `/Users/89298/Documents/transcriptx`.
- Do not delete or modify the existing workspace; only create the backup zip and update `custom-commands/`.
- If staging, zip, or cleanup fails, report the error and do not assume success (remove any leftover staging dir under `/tmp` if present).
