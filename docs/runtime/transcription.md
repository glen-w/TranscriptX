Type: GUIDE
Authority: runtime/STORAGE.md

# Integrated GUI transcription (macOS whispermlx v1)

TranscriptX now includes an integrated **Transcribe Audio** page for macOS hosts running **whispermlx**. WhisperX Docker GUI orchestration is listed in the provider picker as **coming soon**; use the external recipe below for manual Docker workflows.

## Integrated GUI (v1: macOS + whispermlx)

1. Open **Transcribe Audio** in the web UI.
2. Select **Whisper MLX (Mac)** as the provider (default when available).
3. Add files via **Upload**, **Pick existing**, or **Folder path** (server-side path on the machine running Streamlit).
4. Configure model, language, and diarization. **HF_TOKEN** is required only when diarization is enabled.
5. Optionally enable **Import into library when done** (default on). Use **Overwrite existing transcript if names collide** only when you intend to replace an existing library entry (default off).
6. Click **Transcribe**.

### Finding whispermlx

```bash
which whispermlx
```

If not found, set `WHISPERMLX` in `whisperx.env` at the repo root to the full binary path.

### Environment defaults (`whisperx.env`)

Copy `docs/recipes/whisperx/whisperx.env.example` to `whisperx.env` and configure:

| Variable | Purpose |
|----------|---------|
| `WHISPERMLX` | Path to whispermlx binary |
| `WHISPERMLX_MODEL` | Default model (e.g. `large-v3`) |
| `WHISPERMLX_LANGUAGE` | Default language |
| `WHISPERMLX_DIARIZE` | Default diarization on/off |
| `WHISPERMLX_TIMEOUT_SECONDS` | Per-file timeout (0 = no limit) |
| `HF_TOKEN` | Required when diarization is on |
| `TRANSCRIPTX_TRANSCRIPTION_PROVIDER` | Default provider in picker |
| `TRANSCRIPTION_MP3_*` | Conversion defaults (128k stereo MP3) |
| `TRANSCRIPTION_FORCE_REENCODE` | Re-encode existing MP3 inputs |
| `TRANSCRIPTION_KEEP_INTERMEDIATES` | Keep staged MP3 after success (request default) |

### Workflows

- **Upload** — multi-file upload (500 MB per file); files saved via RecordingsService.
- **Pick existing** — multiselect from recordings/imports with metadata.
- **Folder path** — enter an absolute server path, click **Preview files**, then run. Large batches (>50 files) require an explicit acknowledgment.

### Conversion defaults

Inputs are converted to stereo MP3 (`libmp3lame`, 128k, 2 channels) unless the input is already MP3 and force re-encode is off. Sample rate defaults to keeping the source (`TRANSCRIPTION_MP3_SAMPLE_RATE=0`).

---

## External transcription (all platforms)

TranscriptX remains **analysis-first**: you can still bring your own transcript JSON from any tool. The sections below describe external workflows and the managed import API.


This is an operational GUIDE. The authoritative storage, terminology, and run-outcome rules live in:

- `docs/runtime/STORAGE.md`
- `docs/TERMS.md`
- `docs/run_outcome_contract.md`

## What TranscriptX expects (canonical schema)

TranscriptX expects transcripts to satisfy a canonical JSON schema (schema_version/source/metadata/segments) and to participate in the managed storage contract (canonical JSON + sidecar + archived original). The full schema and storage rules are defined in:

- `docs/runtime/STORAGE.md`
- `docs/TERMS.md`

Filenames ending with `*_transcriptx.json` (or `*_canonical.json`) match project conventions, but **naming alone is not enough**; for managed library admission, import through the web UI or use the managed import workflow API below so the full managed artifact set is created.

## Generate transcript JSON

You can produce compatible JSON with any tool: WhisperX, AssemblyAI, Deepgram, Otter, Google, Colab, or manual edits. TranscriptX does not run any transcription engine; it consumes JSON you provide.

### WhisperX (optional reference example)

WhisperX is one example of an external transcription workflow. The recipe below is a **standalone reference** — optional, not required. Run WhisperX yourself (Docker or local), then feed the output into TranscriptX.

**Docker (copy-paste):** Use the reference recipe in [docs/recipes/whisperx/](recipes/whisperx/README.md). From that directory:

```bash
cp whisperx.env.example whisperx.env
# Edit whisperx.env and set HF_TOKEN
docker compose -f docker-compose.whisperx.yml up -d
# Run WhisperX on your audio (see WhisperX docs for exact docker exec command).
```

**Single `docker run` (snippet):**

```bash
# Use a host audio folder outside the repo (same idea as HOST_RECORDINGS_DIR in compose).
export HOST_RECORDINGS_DIR=/path/to/your/recordings
docker run --rm \
  -v "$HOST_RECORDINGS_DIR:/data/input:ro" \
  -v "$(pwd)/data/transcripts:/data/output" \
  --env-file whisperx.env \
  ghcr.io/jim60105/whisperx:no_model \
  /bin/bash -c "whisperx /data/input/your_audio.wav --output_dir /data/output"
```

WhisperX writes JSON with segments (often with `words` arrays). TranscriptX can load that format, but for managed library admission use the managed workflow API (below) so sidecar + archive are created.

## Canonical validation and import (Python API)

There is no `transcriptx transcript …` terminal subcommand. Validate and normalize JSON from code or a short script. **Canonical validation is a hard gate for library admission and analysis**: any API that consumes a transcript path must either receive a pre-validated canonical transcript handle or perform validation itself and fail closed.

**Validate** a document already loaded as a dict (raises `ValueError` if invalid):

```python
import json
from pathlib import Path

from transcriptx.io.transcript_schema import validate_transcript_document

path = Path("path/to/transcript.json")
data = json.loads(path.read_text(encoding="utf-8"))
validate_transcript_document(data)
```

**Managed import** raw or legacy transcript files (e.g. WhisperX JSON, SRT, VTT) into the full managed artifact set:

```python
from pathlib import Path

from transcriptx.core.utils.paths import PATHS
from transcriptx.io.managed_import_workflow import run_managed_import_workflow

result = run_managed_import_workflow(
    PATHS.transcripts_originals_dir / "whisperx_output.json",
    overwrite=False,
)
print(result.json_path)
print(result.sidecar_path)
print(result.archived_original_path)
```

The managed workflow detects the format, normalizes speakers (missing or empty → `SPEAKER_UNKNOWN` where applicable), writes canonical `schema_version/source/metadata`, writes a sidecar, and archives the original source. Web flow does not overwrite existing canonical JSON by default; CLI/programmatic callers may opt into overwrite as a new import attempt.

Downstream analysis APIs (for example `AnalysisRequest` + `run_analysis`) assume the input `transcript_path` refers to a library-valid, canonically validated transcript produced by this workflow or an equivalent canonical loader.

Then analyze from the web interface or via `AnalysisRequest` + `run_analysis` (see [generated/cli.md](generated/cli.md)).

## Multi-language variants

Import alternate-language versions of an existing transcript using a flat filename suffix in the same directory:

- Base (default): `meeting.json`
- French variant: `meeting_fr.json`
- English explicit variant: `meeting_en.json` (optional; `meeting.json` remains the conventional default English path)

**Workflow:**

1. Import and identify speakers on the base transcript first (Speaker ID page, or segment-derived names on import).
2. Import the language variant via the same managed import path (web **Import Transcript** or `run_managed_import_workflow`).
3. On import, speaker-map inheritance runs automatically when the base has a speaker-map sidecar and the variant does not yet.

**Requirements:** variant segments must use the same diarized speaker IDs as the base (`SPEAKER_00`, `SPEAKER_01`, …).

**What is copied:** display names, ignored speakers, and `speaker_id_to_db_id`. Each variant gets its own sidecar under `metadata/speaker_maps/` (see [STORAGE.md](STORAGE.md)).

**When inheritance is skipped:** the filename is not `{base}_{lang}`, the base transcript is missing, the base has no speaker-map sidecar, or the variant already has its own speaker-map sidecar (re-import safe).

**Fallback:** if inheritance does not apply, segment `original_cue.original_speaker` names are used as on a normal import.

## Other tools

You can produce compatible JSON from other engines (e.g. AssemblyAI, Deepgram, Google, manual edits). Ensure each segment has `start`, `end`, `speaker`, and `text`. Use **validate** (above) to check structure and the **managed import workflow** to add canonical metadata + sidecar + archive.

## Golden path

1. **Get JSON** — Use any tool that produces compatible JSON: WhisperX, AssemblyAI, Deepgram, Otter, Colab, or manual export. See `docs/recipes/whisperx/README.md` for an optional WhisperX reference recipe.
2. **Managed import (required for library admission)** — run the managed import workflow (or use the web Import Transcript page) to produce canonical JSON + sidecar + archived original under the managed storage contract (see `docs/runtime/STORAGE.md`).
3. **Analyze** — open the web interface and select the transcript, or use the Python API (`AnalysisRequest` + `run_analysis`).

For managed library analysis, always use a **library-valid managed transcript** as defined in `docs/TERMS.md` and `docs/runtime/STORAGE.md`. Raw canonicalization via low-level helpers alone does not satisfy managed-library admission rules.
