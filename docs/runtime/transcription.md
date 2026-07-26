Type: GUIDE
Authority: runtime/STORAGE.md

# Transcription (external workflow)

TranscriptX is **analysis-first**: transcription produces JSON elsewhere; the web app **imports** it. The **Transcribe Audio** page is a **parameterised command generator** (copyable shell only — Streamlit never executes transcription). **Import Transcript** is the GUI admission gate. WhisperX Docker remains an external recipe, not orchestrated from Streamlit.

## Design: why transcription stays outside the GUI

We intentionally removed in-app transcription forms and `subprocess` orchestration. Transcription runs on the **host** (terminal, `whispermlx-missing`, or WhisperX Docker); the GUI only **generates copyable commands**, documents boundaries, and imports the result.

**Docker vs macOS venv.** The recommended install runs `transcriptx-web` in a **Linux** container. **whispermlx** typically lives in a **macOS** Python venv and depends on Apple MLX. That venv binary cannot be run reliably from inside the container: different OS, no MLX in Linux images, and paths like `~/venvs/whispermlx/bin/whispermlx` refer to the host—not the container filesystem. Mounting the venv or sourcing `whisperx.env` inside `transcriptx-web` does not fix this; at best you get “file not found” or an incompatible executable.

**Practical split.**

| Where | What runs |
|-------|-----------|
| Host (Mac terminal) | `whispermlx`, `whispermlx-missing`, optional WhisperX Docker |
| `transcriptx-web` (Docker or native) | Import, library, analysis, artifacts |

**Why not merge stacks?** Transcription jobs are long-running and toolchain-heavy (ffmpeg, HF tokens, model weights, platform quirks). Keeping engines out of the analysis container avoids bloating the image, avoids coupling releases, and matches how most users already arrive (JSON from an external tool).

**Future (optional):** a **host-side HTTP transcribe service** (same pattern as Ollama via `host.docker.internal`) could let the GUI orchestrate jobs without executing MLX inside Linux. Built-in transcription remains **non-near-term** — see [ROADMAP.md](../ROADMAP.md).

## Transcribe Audio page (command generator)

1. Open **Transcribe Audio** in the web UI.
2. Choose a tool: **whispermlx** (macOS host), **whispermlx-missing** (skip existing JSON), or **WhisperX Docker** (external recipe).
3. Set input path, output folder, model, language, diarize, and (for the bulk helper) dry-run / force / fuzzy-match flags.
4. **Copy** the generated shell snippet. Paths with spaces are shell-quoted. Do **not** expect Streamlit to run it.
5. Run the command on the appropriate host (macOS for whispermlx; Linux/GPU for WhisperX Docker).
6. Open **Import Transcript** and upload the resulting JSON (optionally attach the source recording; same-stem audio in the mounted recordings folder will be linked).

### Non-technical corpus path (short)

| Step | Action |
|------|--------|
| 1 | Put audio files in one folder on your computer |
| 2 | Install `whispermlx-missing` once (see below) if needed → Transcribe Audio → pick **whispermlx-missing** → set source + output folders → enable **Dry-run** → copy/run once to preview |
| 3 | Re-run without dry-run; already-transcribed stems are skipped (resume-friendly) |
| 4 | Import Transcript → upload JSON → optionally attach recordings (same-stem audio in the mounted recordings folder is linked) |
| 5 | Run a Balanced or Quick analysis preset |

**Spaces in folder names:** use the generator (quoting is automatic) or wrap paths in quotes yourself.

**Docker analysis vs transcription:** keep analysis in Docker if you like; still run whispermlx on the Mac host. WhisperX Docker is a separate container recipe — see [docs/recipes/whisperx/README.md](../recipes/whisperx/README.md).

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

### whispermlx-missing bulk script

Install once from the repo root (not shipped as a package entrypoint):

```bash
mkdir -p ~/.local/bin
install -m 755 scripts/whispermlx-missing.py ~/.local/bin/whispermlx-missing
# ensure ~/.local/bin is on PATH (new shell, or: export PATH="$HOME/.local/bin:$PATH")
which whispermlx-missing
```

If `command not found`, either PATH is missing `~/.local/bin` or the install step was skipped. You can also run without installing:

```bash
python3 scripts/whispermlx-missing.py --dry-run …
```

It processes MP3s in a source folder that lack matching JSON in a transcripts output folder.

**Resume / duplicates:** stems with matching JSON are skipped by default. Use `--force` / `--rerun` to replace after a valid new JSON is produced. `--fuzzy-json-match` also treats `foo-….json` / `foo_….json` / `foo.….json` as already done.

**Dry-run:** `--dry-run` previews work without requiring HF_TOKEN or a working whispermlx binary.

**Partial failures:** failed items leave temps under `transcripts/.whispermlx-missing/tmp/`; no partial JSON is written to the transcripts root. `--clean-failed` removes those temps.

**Spaces:** pass paths via quoted CLI args (the Transcribe Audio generator does this) or via the JSON config file.

**Local config (gitignored):** copy [`config/whispermlx-missing.example.json`](../config/whispermlx-missing.example.json) to `.transcriptx/whispermlx-missing.json` and set your paths. For standalone use outside the repo, pass `--config /path/to/config.json` or set `WHISPERMLX_MISSING_CONFIG`.

**Config merge order:** portable repo defaults ← `TRANSCRIPTX_*` / `WHISPERMLX*` env ← local JSON ← CLI flags.

**When the script will process**

- `source` and `transcripts` are each set via **CLI**, **local JSON**, or **`TRANSCRIPTX_*` env** (not portable defaults alone).
- A fresh clone with no local JSON and no env overrides will **not** auto-run batch transcription.

**When it only saves or prints config**

- `--show-config` — print effective settings; never runs whispermlx.
- `--save-config` without meaningful paths — writes `.transcriptx/whispermlx-missing.json` and exits.
- Normal run with portable defaults only — prints guidance; does not process.

**Transcripts path semantics**

| Source | Meaning |
|--------|---------|
| `TRANSCRIPTX_TRANSCRIPTS_DIR` env | Transcripts **base** directory; script appends `/originals` for batch output |
| `transcripts` in JSON or `--transcripts` CLI | Exact **output** directory (no `/originals` append; use `.../originals` explicitly if desired) |
| `TRANSCRIPTX_RECORDINGS_DIR` env | Maps directly to `source` (recordings folder) |

**`whisperx.env`** is used only for the whispermlx **subprocess** environment (`HF_TOKEN`, etc.), not for resolving config paths. Repo `.env` is loaded early (without overriding existing shell env) for `TRANSCRIPTX_*` path overrides — same pattern as Docker/native TranscriptX.

### Audio prep / merge helpers (non-core)

Optional host-side helpers for recordings **before** external transcription. Not part of the core GUI (removed from the Tools nav) and candidates for removal in **1.2** — see [ROADMAP.md](../ROADMAP.md).

**Assess / preprocess** (`scripts/audio_preprocess.py`):

```bash
uv run python scripts/audio_preprocess.py assess recording.wav
uv run python scripts/audio_preprocess.py run recording.wav --mode auto
uv run python scripts/audio_preprocess.py run recording.wav \
  --mode selected --step denoise --step normalize -o ./out --format mp3
```

**Merge split parts** (`scripts/audio_merge.py`):

```bash
uv run python scripts/audio_merge.py part_1.wav part_2.wav -o merged.mp3
uv run python scripts/audio_merge.py --list paths.txt --no-backup --overwrite
```

Requires `ffmpeg` (and typically `pydub` via the project install). Transcribe the resulting files externally, then use **Import Transcript**.

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

There is no `transcriptx transcript …` terminal subcommand. Validate and normalize JSON from code or a short script. Canonical validation is required for library admission and analysis — see [`docs/runtime/STORAGE.md`](STORAGE.md) (canonical transcript validation) for the contract.

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

**Requirements:** variant segments should use the same diarized speaker IDs as the base (`SPEAKER_00`, `SPEAKER_01`, …). See [`STORAGE.md`](STORAGE.md) for managed variant rules.

**What is copied:** display names, ignored speakers, and `speaker_id_to_db_id`. Each variant gets its own sidecar under `metadata/speaker_maps/` (see [STORAGE.md](STORAGE.md)).

**When inheritance is skipped:** the filename is not `{base}_{lang}`, the base transcript is missing, the base has no speaker-map sidecar, or the variant already has its own speaker-map sidecar (re-import safe).

**Fallback:** if inheritance does not apply, segment `original_cue.original_speaker` names are used as on a normal import.

## Folder import (Import Transcript)

On **Import Transcript**, section **Import all from folder** scans an **absolute** local directory (Docker: mount the host folder into the container — typically `HOST_TRANSCRIPT_INBOX_DIR` → `/mnt/transcript-inbox`; do not scan `/mnt/transcripts` or its subdirs) and imports only eligible files:

- Supported extensions: `.json`, `.srt`, `.vtt`, `.txt`, `.html`, `.htm` (case-insensitive).
- Skips stems that are already managed (canonical JSON + import sidecar). Incomplete JSON without a safe `originals/` provenance is **not** treated as a new import.
- Duplicate stems in the folder (including case variants) are all marked conflict — none are imported.
- Source files in the scanned folder are **never** deleted or modified; the app copies into `transcripts/imports/` then runs managed admission.
- Defaults: **100 MiB** per file (`TRANSCRIPTX_FOLDER_IMPORT_MAX_FILE_BYTES`) and **500** candidates (`TRANSCRIPTX_FOLDER_IMPORT_MAX_CANDIDATES`). Exceeding the candidate limit fails the scan closed (Import eligible stays disabled).
- Preview is invalidated if the path, transcripts root, limits, or admission policy change.

Programmatic admission with registration under one lock: `transcriptx.io.admit_and_register.admit_and_register`.

## Other tools

You can produce compatible JSON from other engines (e.g. AssemblyAI, Deepgram, Google, manual edits). Ensure each segment has `start`, `end`, `speaker`, and `text`. Use **validate** (above) to check structure and the **managed import workflow** to add canonical metadata + sidecar + archive.

## Golden path

1. **Get JSON** — Use any tool that produces compatible JSON: WhisperX, AssemblyAI, Deepgram, Otter, Colab, or manual export. See `docs/recipes/whisperx/README.md` for an optional WhisperX reference recipe.
2. **Managed import (required for library admission)** — run the managed import workflow (or use the web Import Transcript page) to produce canonical JSON + sidecar + archived original under the managed storage contract (see `docs/runtime/STORAGE.md`).
3. **Analyze** — open the web interface and select the transcript, or use the Python API (`AnalysisRequest` + `run_analysis`).

For managed library analysis, always use a **library-valid managed transcript** as defined in `docs/TERMS.md` and `docs/runtime/STORAGE.md`. Raw canonicalization via low-level helpers alone does not satisfy managed-library admission rules.
