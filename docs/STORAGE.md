# TranscriptX Storage Policy

This document defines the storage contract for path roots and the serialization rule. It is the reference for the path/storage architecture.

## Serialization rule

**Internally**, filesystem paths are always represented as `Path` objects.

**At configuration, CLI, JSON, or API boundaries**, paths are serialized as strings.

Implications:

- Internal code uses `Path` everywhere.
- Config dataclasses keep `str`-typed fields for path values.
- JSON serialization uses `json.dump(..., default=str)` or equivalent.
- No `Path` objects should appear in serialized config files.

---

## Storage roots

| Root | Meaning | Owner | Mountable | Safe to delete/rebuild | Authored by |
|------|---------|--------|-----------|------------------------|-------------|
| **recordings_dir** | User media library (source audio) | user | yes | no (never auto-clean) | user |
| **transcripts_dir** | User transcript library | user | yes | no (never auto-clean) | user |
| **data_dir** | App working state, outputs, cache | app | optional | partially reconstructable | app |
| **config_dir** | User/app configuration | user/app | optional | no (not safe to auto-delete) | user/app |
| **outputs_dir** | Analysis run outputs | app | optional | yes (re-run to rebuild) | app |
| **state_dir** | DB, processing state | app | under data_dir | partially reconstructable | app |
| **wav_backup_dir** | WAV archive / reproducibility | user/app | optional | no (unless explicit) | app |

### Details

- **recordings_dir**: User-owned, persistent, mountable, never auto-clean, user-authored content.
- **transcripts_dir**: User-owned, persistent, mountable, never auto-clean, user-authored content.  
  - `readable/` is a derived child within this library (not a peer root).  
  - Naming leaves room for future subtypes (`diarised/`, `normalized/`, `export/`).
- **data_dir**: App-owned, persistent but partially reconstructable, not user-authored.
- **config_dir**: User/app config, persistent, not safe to auto-delete.  
  - `profiles/` lives under config_dir (user-editable config presets).
- **outputs_dir**: App-managed analysis outputs, reconstructable by re-running.
- **state_dir**: App state (DB, processing state), persistent, reconstructable in part. Lives under `data_dir/state/`.
- **wav_backup_dir**: Archive, persistent, not auto-clean unless explicit user action.

---

## Final intended directory model

```
recordings_dir/                 # user library (mountable)
transcripts_dir/                # user library (mountable)
  readable/                     # derived transcripts

config_dir/                     # configuration
  profiles/                     # analysis presets

data_dir/                       # app-managed working state
  outputs/
    groups/
  preprocessing/
  cache/
    audio_playback/
    voice/
  state/                        # DB + processing state
    transcriptx.db
    processing_state.json
  backups/
    wav/
    processing_state/
```

This model separates:

- **User libraries**: recordings, transcripts (mountable, never auto-clean).
- **Configuration**: config_dir and profiles.
- **Application state and cache**: data_dir (outputs, preprocessing, cache, state).
- **Backups and reproducibility artefacts**: under data_dir/backups/.
