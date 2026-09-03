# Transcription (bring your own files)

TranscriptX **analyses** transcripts. It does **not** transcribe audio in the app.

You produce JSON, SRT, or VTT with another tool, then **Import Transcript** in the web UI. The **Transcribe Audio** page only **generates a copyable command** — Streamlit never runs transcription.

This page is the mainstream path: you already have a transcript, or you have audio and will run a command on the host. Host watchers, bulk scripts, merge profiles, and the Python import API are under [Host STT automation](host-stt.md) and [Audio prep](audio-prep.md).

## If you already have a transcript

1. Open **Import Transcript** and upload the file (JSON, SRT, VTT, TXT, or HTML — [formats](#what-files-you-can-bring)).
2. Optionally attach the source recording, or place same-stem audio in the mounted recordings folder so playback can link.
3. Open **Run Analysis**, keep **Balanced**, and run it.
4. Read **Overview**. If labels still look like `SPEAKER_00`, [name the speakers](../workflows/speaker-identification.md) and re-run.

Walkthrough with screenshots: [First analysis](../workflows/first-analysis.md).

## If you still need to transcribe audio

1. Put the audio files in one folder on your computer.
2. Open **Transcribe Audio** in the web UI.
3. Choose a tool: **whispermlx** (macOS host), **whispermlx-missing** (skip files that already have JSON), **WhisperX Docker**, or **Whisper-WebUI Docker**.
4. Set input path, output folder, model, language, diarization, and (for the bulk helper) dry-run / force flags. For Whisper-WebUI, set outputs folder, port, and CPU/CUDA.
5. **Copy** the generated shell snippet (paths with spaces are quoted). Run it on the host — macOS for whispermlx; the Docker host for WhisperX / Whisper-WebUI. Do **not** expect Streamlit to run it.
6. Open **Import Transcript** and upload the result (WhisperX/whispermlx JSON, or Whisper-WebUI SRT/VTT).

**Saved presets:** on the same page, save/load/delete command-gen fields (tool, paths, model, language, diarize, tool-specific knobs) under `.transcriptx/profiles/stt_commands/`. Presets store host paths and flags only — never `HF_TOKEN` (tokens stay in `whisperx.env`).

| Step | Typical corpus path (whispermlx-missing) |
|------|------------------------------------------|
| 1 | Put audio files in one folder |
| 2 | Transcribe Audio → **whispermlx-missing** → set source + output folders → enable **Dry-run** → copy/run once to preview |
| 3 | Re-run without dry-run; already-transcribed stems are skipped (resume-friendly) |
| 4 | Import Transcript → upload JSON → optionally attach recordings |
| 5 | Run a Balanced or Quick analysis preset |

Keep analysis in Docker if you like; still run whispermlx on the Mac host. WhisperX Docker and Whisper-WebUI are separate recipes — [WhisperX](../recipes/whisperx/README.md) and [Whisper-WebUI](../recipes/whisper-webui/README.md). Installing the bulk helper: [Host STT automation](host-stt.md#whispermlx-missing-bulk-script).

## What files you can bring

Compatible JSON from WhisperX, [Scriberr](https://scriberr.app/), AssemblyAI, Deepgram, Otter, Google, Colab, or a manual edit. Subtitle exports (**SRT** / **WebVTT**) from Whisper-WebUI, [RiverScript](https://riverscript.com/), or [noScribe](https://noscribe.de/en/) are importable, as are [aTrain](https://github.com/aTrainTranscription/aTrain) **TXT** (and JSON if it matches the segment shape).

TranscriptX does not run any transcription engine; it consumes files you provide. Where it sits next to STT, meeting, and qualitative-research products: [comparison.md](../comparison.md).

Naming such as `*_transcriptx.json` matches project conventions, but **naming alone is not enough**. Add files through **Import Transcript** so the library copy, sidecar, and archived original are created. Schema and layout: [STORAGE.md](STORAGE.md). Programmatic import: [Host STT automation](host-stt.md#python-api).

## Optional recipes

These stay outside the analysis app. The GUI only copies a command; you run it on the host.

- **WhisperX** — Transcribe Audio → **WhisperX Docker** → copy the `docker run` command → **Import Transcript** on the JSON. Full recipe: [docs/recipes/whisperx/](../recipes/whisperx/README.md).
- **Whisper-WebUI** — Gradio UI; hand-off is **SRT/VTT → Import Transcript**. Full recipe (including Apple Silicon notes): [docs/recipes/whisper-webui/README.md](../recipes/whisper-webui/README.md). On Apple Silicon the container is expected to use **CPU** inference; prefer host **whispermlx** when Metal/MLX speed matters.

## Import a whole folder

On **Import Transcript**, section **Import all from folder** scans an **absolute** local directory and imports eligible files (JSON, SRT, VTT, TXT, HTML). Source files are never deleted or modified.

- Docker: mount the host folder (typically `HOST_TRANSCRIPT_INBOX_DIR` → `/mnt/transcript-inbox`). Do not scan `/mnt/transcripts` or its subdirs.
- Preview first. Already-imported stems, stem conflicts, and unrepairable files are blocked. Duplicate stems in the folder are all marked conflict.
- Same-stem audio in approved recordings folders is listed as found or none; it is not copied automatically.

Limits and eligibility rules: [Host STT automation](host-stt.md#import-a-whole-folder-details).

## Language variants

Import an alternate-language version next to an existing transcript using a filename suffix: `meeting.json` (base) and `meeting_fr.json` (French). Identify speakers on the base first; import then copies display names into the variant when the IDs match. Details: [Host STT automation](host-stt.md#multi-language-variants).

## Why transcription stays outside the GUI

Transcription runs on the **host** (terminal, WhisperX Docker, or Whisper-WebUI). The GUI generates copyable commands and imports the result.

| Where | What runs |
|-------|-----------|
| Host (Mac terminal) | `whispermlx`, `whispermlx-missing`, `inbox-watch`, optional WhisperX / Whisper-WebUI Docker |
| `transcriptx-web` (Docker or native) | Import, library, analysis, artifacts |

The recommended install runs analysis in a **Linux** container. **whispermlx** typically lives in a **macOS** venv and cannot be run from inside that container. Keeping engines out of the analysis image avoids bloating it and matches how most people already arrive (JSON from another tool).

**Future (1.x):** optional in-app / host-orchestrated transcription is a post-1.0 theme — [ROADMAP.md](../ROADMAP.md) theme **H**. Until that ships, 1.0 stays bring-your-own + command generation. In-app directory watch for transcript auto-import is theme **G2** — [directory_watcher.md](directory_watcher.md).

## Advanced

- [Host STT automation](host-stt.md) — whispermlx-missing, inbox-watch, config, Python import API
- [Audio prep](audio-prep.md) — Tools → Preprocessing / Auto-merge before you transcribe
- [Directory watcher](directory_watcher.md) — in-app inbox (transcripts), not host STT
