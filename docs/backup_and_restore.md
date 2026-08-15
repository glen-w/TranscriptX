Type: GUIDE
Authority: user flows and examples — summarizes [contracts/workspace-backup.md](contracts/workspace-backup.md); does not redefine schemas

# Workspace backup and restore

Full-workspace ZIP archives let you copy transcripts, durable app state, and config between machines or recover after a bad change. TranscriptX never uploads these files.

Normative rules: [contracts/workspace-backup.md](contracts/workspace-backup.md). Storage roots: [runtime/STORAGE.md](runtime/STORAGE.md).

## What is packed

| Always (when present) | Optional (default off) | Never |
|-----------------------|------------------------|-------|
| Transcripts under `TRANSCRIPTX_TRANSCRIPTS_DIR` (not `imports/`) | Recordings (`--include-recordings`) | `data/cache/`, `data/preprocessing/` |
| `TRANSCRIPTX_CONFIG_DIR` | Outputs (`--include-outputs`) | `*.lock`, `*.partial`, `.staging/`, `.cache/` |
| Durable data: groups, speaker_profiles (incl. voice), corrections, state, watcher | | Default backup dir nesting (`data/backups/workspace/`) |
| WAV backup tree when present | | Absolute host paths (role roots only) |

Archives use format `transcriptx.workspace-backup` (schema v1). Members are **role roots** remapped onto the **current** `TRANSCRIPTX_*` mounts — useful when Docker volume paths differ on a new host.

Workspace archives may contain **PII and biometric voice evidence**. Keep them offline and access-controlled.

## Recommended practice

1. Keep backups under `{data_dir}/backups/workspace/` (default create path).
2. Prefer the **script** for large corpora; the Settings UI only accepts on-disk paths (no browser upload/download of multi-GB ZIPs).
3. Run `verify` after copying an archive to another disk or machine.
4. Always dry-run restore before a live replace.
5. Create a backup before major workspace changes (bulk cleanup, host moves, upgrades you care about rolling back).

## Create a backup

**Script**

```bash
# Default: {DATA}/backups/workspace/transcriptx-workspace-<stamp>.zip
uv run python scripts/workspace_backup.py create

# Custom destination (refuses overwrite unless --force)
uv run python scripts/workspace_backup.py create --dest /safe/path/workspace.zip
uv run python scripts/workspace_backup.py create --dest /safe/path/workspace.zip --force

# Also pack recordings and/or analysis outputs
uv run python scripts/workspace_backup.py create --include-recordings --include-outputs
```

Create refuses while speaker-profile or managed-rename locks are held, when free disk space is too low, or when the destination already exists without `--force`.

**UI:** **Settings → Storage → Workspace backup** → optional Include recordings / Include outputs → **Create backup**.

**Python API:** `transcriptx.services.workspace_backup.WorkspaceBackupService`.

## Verify an archive

```bash
uv run python scripts/workspace_backup.py verify /path/to/workspace.zip
```

Checks the manifest, rejects zip-slip / unexpected top-level members, and recomputes `file_index_sha256`. Does not change the workspace.

**UI:** paste the archive path → **Verify archive**.

## Restore (replace-only)

Restore **replaces** transcripts, config, and durable data from the archive (plus recordings/outputs when those were packed). There is no merge or per-transcript restore in v1.

```bash
# Preview only
uv run python scripts/workspace_backup.py restore /path/to/workspace.zip --dry-run

# Write: requires --yes; writes a safety ZIP first
uv run python scripts/workspace_backup.py restore /path/to/workspace.zip --yes

# Skip the automatic pre-restore safety ZIP (not recommended)
uv run python scripts/workspace_backup.py restore /path/to/workspace.zip --yes --no-safety-backup
```

Default safety archive: `{DATA}/backups/workspace/pre-restore-<stamp>.zip` with **default** create options (recordings/outputs **not** included). After replace, TranscriptX deletes rebuildable `data/cache/` and runs a speaker-profiles integrity scan when applicable.

**UI:** paste path → optional **Dry-run restore** → confirm checkbox → **Restore from backup**. Safety ZIP is always written for real restores.

### Guards

- Archive must not sit under a tree restore will wipe.
- Archives under `{data_dir}/backups/workspace/` are safe.
- Insufficient free disk space refuses before destructive work.
- Busy locks refuse create and restore.

## Moving machines or remounting Docker volumes

1. On the source host: create a backup (add recordings/outputs flags if needed).
2. Copy the ZIP to the destination. Keep it outside trees you will replace, or under the destination’s `data/backups/workspace/`.
3. Point the new host’s `TRANSCRIPTX_*` / Compose `HOST_*` mounts at the desired empty or disposable volumes ([runtime/docker.md](runtime/docker.md)).
4. Verify the copied ZIP.
5. Dry-run restore, then restore with `--yes`.
6. Open **System → Diagnostics** and confirm the workspace looks healthy.

Role-root layout means you do **not** need identical absolute paths on the new machine.

## If restore fails

1. Read the error: if a safety ZIP was written, the message includes its path.
2. Do **not** keep using a half-replaced workspace for import/analysis until recovered.
3. Restore from the `pre-restore-*.zip` safety archive, or from an older known-good backup.

## Related surfaces (not the same)

| Surface | Purpose |
|---------|---------|
| Artifacts / run ZIP export | Per-run portable export, not full workspace |
| Ordinary speaker-profile backup inventory | Excludes `voice/` — not this workspace archive |
| Interface “restore built-in” menus | Resets menu defaults only |
| `.cursor/commands/backup.md` | Developer **source-code** zip for agents — not user data |
| Analysis run cleanup (Settings → Storage) | Deletes reconstructable outputs only |
