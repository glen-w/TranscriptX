# Workspace backup

## Purpose

Portable ZIP of the **authoritative workspace** (transcripts + config + durable app state) so operators can move machines, remount Docker volumes, or recover after mistakes. Archives are local files; TranscriptX does not upload them.

## Format

- Envelope: `format: transcriptx.workspace-backup`, `schema_version: 1`
- Container: ZIP with `ZIP_DEFLATED` (Zip64 allowed)
- Manifest member (required, zip root): `transcriptx.workspace-backup.json`

## Package layout (role roots)

Absolute host paths are **not** authority. Members use fixed role prefixes remapped to current `PathSettings` on restore:

```text
transcriptx.workspace-backup.json
transcripts/           # TRANSCRIPTX_TRANSCRIPTS_DIR (excludes ephemeral imports/)
config/                # TRANSCRIPTX_CONFIG_DIR
data/
  groups/
  speaker_profiles/    # remapped to TRANSCRIPTX_SPEAKER_PROFILES_DIR when set
  corrections/
  state/               # locks excluded
  watcher/             # when present
wav_backup/            # TRANSCRIPTX_WAV_BACKUP_DIR when present
recordings/            # only when includes.recordings
outputs/               # only when includes.outputs
```

## Manifest fields (v1)

| Field | Required | Meaning |
|-------|----------|---------|
| `format` | yes | `transcriptx.workspace-backup` |
| `schema_version` | yes | `1` |
| `created_at` | yes | ISO-8601 UTC timestamp |
| `transcriptx_version` | yes | Application version string that wrote the archive |
| `includes` | yes | Object: `transcripts`, `config`, `durable_data`, `wav_backup`, `recordings`, `outputs` (booleans) |
| `counts` | yes | Object: `transcripts`, `files`, `uncompressed_bytes` (non-negative ints; best-effort) |
| `file_index_sha256` | yes | Hex SHA-256 of the sorted file-index lines used at pack time |
| `roots_note` | no | Operator notes; may list role names; must not be required for restore |

**File index** (internal, used to compute `file_index_sha256`): one line per packed file (excluding the manifest itself), sorted lexicographically by member path:

```text
<path>\t<size>\t<sha256>
```

Verify recomputes this index over non-manifest members and compares the digest. Pack and verify stream file bytes (chunked) so large corpora do not require loading each member fully into memory.

## Always include (when present on disk)

- Entire transcripts tree except ephemeral `imports/`
- Entire `config_dir` tree
- Durable data subtrees: `groups/`, `speaker_profiles/` (including `voice/` and avatar assets), `corrections/`, `state/` (minus locks), `watcher/`
- `wav_backup_dir` when it contains files

`includes.transcripts`, `includes.config`, and `includes.durable_data` are always `true` in valid v1 archives. `includes.wav_backup` is `true` only when wav backup files were packed.

Workspace backup **includes** speaker-profile `voice/` evidence. This differs from ordinary export / inventory helpers that must exclude `voice/` ([speaker_profiles_voice_v1.md](speaker_profiles_voice_v1.md)). Treat archives as biometric-capable PII.

## Optional includes (default off)

| Flag | Packs |
|------|-------|
| `include_recordings` | `TRANSCRIPTX_RECORDINGS_DIR` → `recordings/` (skips `imports/` staging) |
| `include_outputs` | `TRANSCRIPTX_OUTPUT_DIR` → `outputs/` (never pack the destination archive being written) |

## Always exclude

- `data/cache/**`, `data/preprocessing/**`
- `data/outputs/**` unless `include_outputs`
- `transcripts/imports/**` and recordings `imports/**` staging
- `*.lock` files
- `*.partial` files (interrupted zip writes)
- `.staging/` directories
- `.cache/**`, `thumbs/`, `__pycache__/`
- The destination ZIP path itself when it would fall under a packed root
- `{data_dir}/backups/workspace/**` (default backup destination tree; avoid nesting archives)

## Create semantics

1. Refuse if the speaker-profiles project lock is held.
2. Refuse if a managed-rename lock is held.
3. Refuse if the destination `.zip` already exists unless `force` / `--force`.
4. Refuse when free disk space on the destination filesystem is below a fixed headroom (256 MiB) plus the estimated uncompressed payload size.
5. Write via `*.zip.partial` then atomic rename to the destination.
6. Member names must stay under the role prefixes above (zip-slip rejected on write and read).

Default destination: `{data_dir}/backups/workspace/transcriptx-workspace-<YYYYMMDD-HHMMSS>.zip`.

## Verify semantics

1. Open ZIP; require and parse the root manifest (`format` must be `transcriptx.workspace-backup`, `schema_version` must be `1`).
2. Reject members that escape role roots (`..`, absolute paths, unexpected top-level names).
3. Require role presence consistent with `includes` (empty trees may soft-note).
4. Recompute `file_index_sha256` over packed files; mismatch → fail.

Verify does **not** mutate the workspace.

## Restore semantics (v1)

**Replace-only.** Restore remaps archive role roots onto the **current** `PathSettings` (env/Docker mounts). Absolute paths recorded in notes are ignored for placement.

1. `verify` the archive (fail closed).
2. Refuse busy locks (same as create).
3. Refuse if the archive path resolves under a tree that restore will replace (`transcripts`, `config`, durable data subtrees, `wav_backup`, and `recordings`/`outputs` when those includes are true). Archives under `{data_dir}/backups/workspace/` are allowed.
4. Unless disabled, create a **safety backup** of the current workspace (same create path; default options — recordings/outputs off) under `{data_dir}/backups/workspace/pre-restore-<stamp>.zip`.
5. Refuse when free disk space is below fixed headroom plus estimated restore payload (and safety backup size when enabled).
6. Replace role roots present in the archive:
   - Clear children of `transcripts_dir`, then extract `transcripts/`
   - Replace `config_dir`
   - Replace `data/groups`, `data/corrections`, `data/state`, `data/watcher` under `data_dir`; replace `speaker_profiles` onto `speaker_profiles_dir`
   - Replace `wav_backup_dir` when packed
   - When `includes.recordings` / `includes.outputs`: replace those roots (`outputs` preserves nothing under `{data_dir}/backups/workspace` because that tree is outside outputs by default; if outputs somehow overlaps, preserve `backups/workspace` when present under the outputs root)
7. Delete `data_dir/cache/` when present (rebuildable).
8. Run speaker-profiles integrity scan when the profiles tree exists; report findings. Point operators to System → Diagnostics.

If replace fails after a safety backup was written, errors include the safety archive path so operators can recover.

Dry-run: perform verify + lock checks + archive-location guard + describe replacements (counts and mapped paths); write nothing.

## Non-goals (v1)

- Merge / per-transcript restore
- Incremental or differential backups
- Encryption or cloud upload
- Treating analysis outputs or caches as backup authority
- In-browser Streamlit transfer of full archives
- Expanding the `transcriptx` console script with backup subcommands
