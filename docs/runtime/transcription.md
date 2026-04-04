Type: GUIDE
Authority: runtime/STORAGE.md

# External transcription guide

TranscriptX is **analysis-only**: it does not run WhisperX or any transcription engine. You bring your own transcript JSON. This guide explains what format TranscriptX expects and how to produce it.

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
docker run --rm \
  -v "$(pwd)/data/recordings:/data/input:ro" \
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

from transcriptx.io.managed_import_workflow import run_managed_import_workflow

result = run_managed_import_workflow(
    PATHS.transcript_originals_dir / "whisperx_output.json",
    overwrite=False,
)
print(result.json_path)
print(result.sidecar_path)
print(result.archived_original_path)
```

The managed workflow detects the format, normalizes speakers (missing or empty → `SPEAKER_UNKNOWN` where applicable), writes canonical `schema_version/source/metadata`, writes a sidecar, and archives the original source. Web flow does not overwrite existing canonical JSON by default; CLI/programmatic callers may opt into overwrite as a new import attempt.

Downstream analysis APIs (for example `AnalysisRequest` + `run_analysis`) assume the input `transcript_path` refers to a library-valid, canonically validated transcript produced by this workflow or an equivalent canonical loader.

Then analyze from the web interface or via `AnalysisRequest` + `run_analysis` (see [generated/cli.md](generated/cli.md)).

## Other tools

You can produce compatible JSON from other engines (e.g. AssemblyAI, Deepgram, Google, manual edits). Ensure each segment has `start`, `end`, `speaker`, and `text`. Use **validate** (above) to check structure and the **managed import workflow** to add canonical metadata + sidecar + archive.

## Golden path

1. **Get JSON** — Use any tool that produces compatible JSON: WhisperX, AssemblyAI, Deepgram, Otter, Colab, or manual export. See `docs/recipes/whisperx/README.md` for an optional WhisperX reference recipe.
2. **Managed import (required for library admission)** — run the managed import workflow (or use the web Import Transcript page) to produce canonical JSON + sidecar + archived original under the managed storage contract (see `docs/runtime/STORAGE.md`).
3. **Analyze** — open the web interface and select the transcript, or use the Python API (`AnalysisRequest` + `run_analysis`).

For managed library analysis, always use a **library-valid managed transcript** as defined in `docs/TERMS.md` and `docs/runtime/STORAGE.md`. Raw canonicalization via low-level helpers alone does not satisfy managed-library admission rules.
