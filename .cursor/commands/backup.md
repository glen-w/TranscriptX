# Backup workspace (# backup)

Back up all code from the workspace to a date-stamped folder, excluding gitignored and library/cache content.
Execute from the workspace root: `/Users/89298/Documents/transcriptx`.

---

## What to do

1. **Resolve backup path and date**
   - Base directory: `/Users/89298/Documents/transcriptx backup`
   - Subfolder name: `YYMMDD` (e.g. `250306` for 6 Mar 2025). Use shell: `date +%y%m%d`
   - Full destination: `/Users/89298/Documents/transcriptx backup/YYMMDD`

2. **Create destination**
   - Create the base directory if it does not exist.
   - Create the `YYMMDD` subfolder (do not overwrite; **if it already exists**, use a suffix like `YYMMDD-HHMM` so each backup gets its own folder).

3. **Copy files (exclude gitignored-style paths)**
   - Copy from workspace root (current project directory) into the chosen subfolder.
   - **Exclude** (so backup has no libraries, caches, or generated cruft):
     - `.git`
     - `node_modules`, `__pycache__`, `.venv`, `venv`, `env`, `.env`
     - `.pytest_cache`, `.mypy_cache`, `.ruff_cache`
     - `*.pyc`, `*.pyo`, `*.egg-info`, `dist/`, `build/`
     - `.DS_Store`, `*.log`, `*.tmp`
   - Prefer **rsync** so exclusions are reliable and only changed files are considered. **Use a suffix when the date-folder already exists** (run from workspace root):
     ```bash
     BACKUP_ROOT="/Users/89298/Documents/transcriptx backup"
     STAMP=$(date +%y%m%d)
     if [ -d "$BACKUP_ROOT/$STAMP" ]; then
       STAMP=$(date +%y%m%d-%H%M)
     fi
     mkdir -p "$BACKUP_ROOT/$STAMP"
     rsync -a --exclude='.git' --exclude='node_modules' --exclude='__pycache__' --exclude='.venv' --exclude='venv' --exclude='.pytest_cache' --exclude='.mypy_cache' --exclude='.ruff_cache' --exclude='*.pyc' --exclude='*.egg-info' --exclude='dist' --exclude='build' --exclude='.DS_Store' . "$BACKUP_ROOT/$STAMP/"
     ```

4. **Back up Cursor custom commands to the backup folder**
   - Create `custom-commands` in the backup root (not inside the dated subfolder): `mkdir -p "$BACKUP_ROOT/custom-commands"`.
   - Copy the contents of `.cursor/commands/` into it (e.g. `cp -r .cursor/commands/. "$BACKUP_ROOT/custom-commands/"` or `rsync -a .cursor/commands/ "$BACKUP_ROOT/custom-commands/"` from workspace root).
   - This keeps the latest command `.md` files at `transcriptx backup/custom-commands/` for easy restore or inspection.

5. **Confirm**
   - After the command, report: backup path (e.g. `/Users/89298/Documents/transcriptx backup/250306`), approximate file count or size if easy to obtain, and that it completed successfully.

---

## Execution rules

- Run from workspace root: `/Users/89298/Documents/transcriptx`.
- Do not delete or modify the existing workspace; only create the backup directory and copy into it.
- If creation or rsync fails, report the error and do not assume success.
