# External transcription guide

TranscriptX is **analysis-only**: it does not run WhisperX or any transcription engine. You bring your own transcript JSON. This guide explains what format TranscriptX expects and how to produce it.

## What TranscriptX expects (canonical schema)

TranscriptX accepts **canonical** transcript JSON with this structure (schema version 1.0):

```json
{
  "schema_version": "1.0",
  "source": {
    "type": "whisperx",
    "original_path": "recording.mp3",
    "imported_at": "2026-02-26T12:00:00Z"
  },
  "metadata": {
    "duration_seconds": 3600.0,
    "segment_count": 450,
    "speaker_count": 3
  },
  "segments": [
    {
      "start": 0.0,
      "end": 5.2,
      "speaker": "SPEAKER_00",
      "text": "Hello, welcome to the session."
    }
  ]
}
```

- **schema_version**: `"1.0"`.
- **source**: type (e.g. `whisperx`, `vtt`, `assemblyai`, `manual`), original_path, imported_at (ISO 8601).
- **metadata**: duration_seconds, segment_count, speaker_count.
- **segments**: list of objects with `start`, `end`, `speaker`, `text`.

Filenames ending with `*_transcriptx.json` are treated as canonical; use `--accept-noncanonical` to analyze other filenames when the content is valid.

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

WhisperX writes JSON with segments (often with `words` arrays). TranscriptX can **load** that format directly for analysis; for full canonical metadata, run **canonicalize** (see below).

## Validate and canonicalize

- **Validate** a file against the canonical schema:
  ```bash
  transcriptx transcript validate --file path/to/transcript.json
  ```
  Exit 0 = valid, 1 = invalid or loadable-but-not-canonical, 2 = file/parse error.

- **Canonicalize** raw or legacy JSON (e.g. WhisperX output) into canonical form:
  ```bash
  transcriptx transcript canonicalize --in whisperx_output.json --out meeting_transcriptx.json
  ```
  If you omit `--out`, output is written to `<stem>_transcriptx.json` (e.g. `whisperx_output_transcriptx.json`). Missing or empty speakers are normalized to `SPEAKER_UNKNOWN`; segment_count, speaker_count, and duration_seconds are computed if missing.

Then analyze:

```bash
transcriptx analyze --transcript-file meeting_transcriptx.json
```

## Other tools

You can produce compatible JSON from other engines (e.g. AssemblyAI, Deepgram, Google, manual edits). Ensure each segment has `start`, `end`, `speaker`, and `text`. Use **validate** to check and **canonicalize** to fill schema_version, source, and metadata if needed.

## Golden path

1. **Get JSON** — Use any tool that produces compatible JSON: WhisperX, AssemblyAI, Deepgram, Otter, Colab, or manual export. See [recipes/whisperx](recipes/whisperx/README.md) for an optional WhisperX reference recipe.
2. **Canonicalize (optional but recommended)** — `transcriptx transcript canonicalize --in <file> --out <stem>_transcriptx.json`.
3. **Analyze** — `transcriptx analyze --transcript-file <stem>_transcriptx.json`.

You can also point `analyze` at raw JSON directly (e.g. from WhisperX); TranscriptX will load it and show a one-line tip to canonicalize for best results.
