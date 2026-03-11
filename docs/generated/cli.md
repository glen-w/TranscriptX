# Python API Reference

TranscriptX no longer has a terminal CLI. The primary interface is the **Streamlit web application** (`transcriptx` command launches it).

For scripting and automation, use the Python API directly:

## Analysis

```python
from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.workflows.analysis import run_analysis

result = run_analysis(AnalysisRequest(
    transcript_path="path/to/transcript.json",
    mode="quick",            # "quick" or "full"
    modules=["stats"],       # None = recommended modules
    skip_speaker_mapping=True,
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
from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.workflows.batch import run_batch_analysis

results = run_batch_analysis([
    AnalysisRequest(transcript_path="a.json", modules=["stats"]),
    AnalysisRequest(transcript_path="b.json", modules=["stats"]),
])
```

## Starting the Web Interface Programmatically

```bash
transcriptx                     # default: http://127.0.0.1:8501
transcriptx --host 0.0.0.0     # bind all interfaces (Docker)
transcriptx --port 8502         # custom port
python -m transcriptx.web      # equivalent
```
