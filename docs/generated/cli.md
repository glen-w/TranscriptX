# Web launcher and host CLI

The **`transcriptx` console script** (`transcriptx.cli:main`) dispatches **allowlisted** host automation commands, then launches the Streamlit web application when no command is given (same as `python -m transcriptx.web`). Interactive workspaces (Corrections, Speaker ID review, Charts/Ask) stay in the GUI.

`transcriptx --help` lists the allowlist. With no command, launcher flags are `--host` and `--port`.

Web launcher help (`python -m transcriptx.web --help`):

```
usage: transcriptx [-h] [--host HOST] [--port PORT]

TranscriptX — launch the web interface

options:
  -h, --help   show this help message and exit
  --host HOST  Host to bind to (default: 127.0.0.1)
  --port PORT  Port to listen on (default: 8501)
```

For scripting beyond the allowlist, use the Python API directly. Contract: [public surfaces](../public_surfaces.md) §1.7.

From a clean venv, install analysis and chart extras before expecting a full **Balanced** run (for example `pip install -e ".[visualization]"` or `.[full]` from this repository). Core-only `pip install -e .` can complete runs with many modules skipped or failed when speakers are still diarized labels and when matplotlib is missing. See [Installation](../runtime/installation.md).

## Import

```bash
transcriptx import path/to/raw.json
transcriptx import a.json b.json --overwrite
python -m transcriptx.import_transcript path/to/raw.json
```

```python
from pathlib import Path

from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.workflows.analysis import run_analysis
from transcriptx.io.managed_import_workflow import run_managed_import_workflow

imported = run_managed_import_workflow(
    Path("path/to/raw_transcript.json"),
    overwrite=False,
)

result = run_analysis(AnalysisRequest(
    transcript_path=imported.json_path,
    mode="quick",            # pipeline mode: "quick" or "full"
    analysis_preset="balanced",  # optional UI preset: quick | balanced | thorough | custom
    modules=["stats"],       # None = recommended modules
    include_unidentified_speakers=False,
))
print("success:", result.success)
print("errors:", result.errors)
```

## Analyze (single managed transcript)

```bash
transcriptx analyze --path /path/to/library/foo.json --preset balanced
transcriptx analyze --path foo.json --mode quick --modules stats --allow-unnamed-speakers
python -m transcriptx.analyze --path foo.json --preset quick
```

Batch and group analysis remain Python API only (`run_batch_analysis`, `run_group_analysis`).

## Admit originals

`transcriptx admit-originals` (same as `python -m transcriptx.admit_originals`) admits raw files already under `transcripts/originals/` (or another host dest) through `admit_and_register`. `inbox-watch --admit` invokes this helper.

```bash
transcriptx admit-originals \
  --dir /path/to/transcripts/originals \
  --transcripts-root /path/to/transcripts
```

Optional `--auto-name` / `--auto-link` (and `--no-auto-*`) run speaker auto-identify after each successful admit. `--auto-name` with no link flag defaults auto-link on. Identify failure does not fail admit. Operator guide: [auto-identify.md](../runtime/auto-identify.md).

## Rename

```bash
transcriptx rename --path /path/to/library/old.json --stem clearer_name
transcriptx rename --path old.json --stem clearer_name --dry-run
python -m transcriptx.rename_managed --path old.json --stem clearer_name
```

## Backup

```bash
transcriptx backup create
transcriptx backup create --dest /safe/ws.zip --force
transcriptx backup verify /safe/ws.zip
transcriptx backup restore /safe/ws.zip --dry-run
python -m transcriptx.backup create
```

`scripts/workspace_backup.py` remains a thin shim for source checkouts. Normative rules: [workspace-backup.md](../contracts/workspace-backup.md).

## Auto-identify speakers (host helper)

`transcriptx identify-speakers` (same as `python -m transcriptx.identify_speakers`) fuses local voice match with in-transcript names and can write speaker-map names and/or `auto_identified` profile links. It is distinct from the Python API `identify_speakers` below (that API is the Speaker Identification workspace rename path).

```bash
transcriptx identify-speakers --path FILE.json --auto-name --auto-link
transcriptx identify-speakers --all-unnamed --dry-run
```

Flags override `{config_dir}/identify.json` for that run. `--dry-run` prints decisions and writes nothing. Host USB path: `inbox-watch --auto-name`.

## Warm assistive LLM suggestion caches

`transcriptx warm-suggestions` (or `python -m transcriptx.warm_suggestions`) precomputes assistive **speaker name** and **rename** suggestion caches for managed transcripts (confirm-to-apply in the GUI; does not rename files or write speaker maps). See [llm-suggestion-batch.md](../runtime/llm-suggestion-batch.md).

```bash
transcriptx warm-suggestions --all
transcriptx warm-suggestions --speaker-names --dry-run
transcriptx warm-suggestions --rename --force --path FILE.json
```

```python
from transcriptx.app.models.requests import WarmSuggestionsRequest
from transcriptx.app.workflows import run_warm_suggestions

run_warm_suggestions(WarmSuggestionsRequest(warm_all=True))
```

## Speaker Identification

```python
from transcriptx.app.models.requests import SpeakerIdentificationRequest
from transcriptx.app.workflows.speaker import identify_speakers
from pathlib import Path

result = identify_speakers(SpeakerIdentificationRequest(
    transcript_paths=[Path("transcript.json")],
    skip_rename=True,
))
```

## Batch Analysis

```python
from pathlib import Path

from transcriptx.app.models.requests import BatchAnalysisRequest
from transcriptx.app.workflows.batch import run_batch_analysis

result = run_batch_analysis(BatchAnalysisRequest(
    transcript_paths=[Path("a.json"), Path("b.json")],
    analysis_mode="quick",
    selected_modules=["stats"],
))
print(result.success, result.message, result.errors)
```

## Starting the Web Interface Programmatically

```bash
transcriptx                     # default: http://127.0.0.1:8501
transcriptx --host 0.0.0.0     # bind all interfaces (Docker)
transcriptx --port 8502         # custom port
python -m transcriptx.web      # equivalent
```
