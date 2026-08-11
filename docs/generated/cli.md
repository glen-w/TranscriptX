Type: GUIDE
Authority: ../ARCHITECTURE.md

# Web launcher and Python API

The **`transcriptx` console script** only starts the Streamlit web application (same as `python -m transcriptx.web`). There are no `transcriptx <subcommand>` analysis commands.

Current launcher help:

```
usage: transcriptx [-h] [--host HOST] [--port PORT]

TranscriptX — launch the web interface

options:
  -h, --help   show this help message and exit
  --host HOST  Host to bind to (default: 127.0.0.1)
  --port PORT  Port to listen on (default: 8501)
```

For scripting and automation, use the Python API directly:

## Analysis

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
