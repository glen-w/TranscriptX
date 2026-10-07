# Transcription (bring your own files, optional in-app STT)

TranscriptX **analyses** transcripts after they are in the library.

**Import Transcript** admits JSON, SRT, VTT, and other supported files in the web UI. **Transcribe Audio** can **run a host-orchestrated provider** (whispermlx on macOS, WhisperX Docker when the daemon is reachable) or **generate a copyable command** for host-side tools. Engines stay **out of the analysis image**. Running Compose analysis, host whispermlx, and optional WhisperX/WebUI **together**: [STT stacks](../recipes/stt-stacks/README.md).

This page is the mainstream path: you already have a transcript, or you have audio and will transcribe it here or on the host. Host watchers, bulk scripts, merge profiles, and the Python import API are under [Host STT automation](host-stt.md) and [Audio prep](audio-prep.md).

## If you already have a transcript

1. Open **Import Transcript** and upload the file (JSON, SRT, VTT, TXT, or HTML — [formats](#what-files-you-can-bring)).
2. Optionally attach the source recording, or place same-stem audio in the mounted recordings folder so playback can link.
3. If labels look like `SPEAKER_00`, [name the speakers](../workflows/speaker-identification.md) before you analyse. Most **Balanced** modules skip until speakers are named. Host USB ingest can auto-name after admit: [auto-identify.md](auto-identify.md).
4. Open **Run Analysis**, keep **Balanced**, and run it.
5. Read **Overview**. If you already ran on placeholder labels, name the speakers and run again.

Walkthrough with screenshots: [First analysis](../workflows/first-analysis.md).

## If you still need to transcribe audio

1. Put the audio files in one folder on your computer (absolute path the Streamlit process can read).
2. Open **Transcribe Audio**.
3. Prefer **Run in app** when a provider is available (native GUI on the Mac for whispermlx; see [STT stacks](../recipes/stt-stacks/README.md)):
   - **whispermlx** — macOS host with `whispermlx` on PATH (or `WHISPERMLX` in `whisperx.env`).
   - **WhisperX Docker** — `docker` on PATH and a reachable daemon; CUDA uses `--gpus all`.
4. If no provider is available from this process (typical when Streamlit runs inside `transcriptx-web`), switch to **Copy command**, pick a tool, and run the snippet **on the host**.
5. POSIX snippets paste into macOS, Linux, Git Bash, or WSL. **PowerShell** snippets are a second builder for Windows hosts. Streamlit does not execute copied snippets.
6. With **Import result into library** on, a successful Run admits JSON automatically. Otherwise open **Import Transcript**.

**Saved presets:** on Copy command, save/load/delete command-gen fields under `.transcriptx/profiles/stt_commands/`. Presets store host paths and flags only — never `HF_TOKEN` (tokens stay in `whisperx.env`).

| Step | Typical corpus path (whispermlx-missing) |
|------|------------------------------------------|
| 1 | Put audio files in one folder |
| 2 | Transcribe Audio → **whispermlx-missing** → set source + output folders → enable **Dry-run** → copy/run once to preview |
| 3 | Re-run without dry-run; already-transcribed stems are skipped (resume-friendly) |
| 4 | Import Transcript → upload JSON → optionally attach recordings |
| 5 | Name speakers if labels are still placeholders, then run Balanced or Quick |

Keep analysis in Docker if you like; still run whispermlx on the Mac host, or mount the Docker socket if you want WhisperX Docker orchestration from the GUI. WhisperX Docker and Whisper-WebUI copyable recipes remain — [WhisperX](../recipes/whisperx/README.md) and [Whisper-WebUI](../recipes/whisper-webui/README.md). Installing the bulk helper: [Host STT automation](host-stt.md#whispermlx-missing-bulk-script).

## What files you can bring

Compatible JSON from WhisperX, [Scriberr](https://scriberr.app/), AssemblyAI, Deepgram, Otter, Google, Colab, or a manual edit. Subtitle exports (**SRT** / **WebVTT**) from Whisper-WebUI, [RiverScript](https://riverscript.com/), or [noScribe](https://noscribe.de/en/) are importable, as are [aTrain](https://github.com/aTrainTranscription/aTrain) **TXT** (and JSON if it matches the segment shape).

The analysis image does not embed a transcription engine. The GUI can orchestrate **whispermlx** or **WhisperX Docker** when those tools are visible to the Streamlit process; otherwise it consumes files you provide (BYO import or Copy command). Where it sits next to STT, meeting, and qualitative-research products: [comparison.md](../comparison.md).

Naming such as `*_transcriptx.json` matches project conventions, but **naming alone is not enough**. Add files through **Import Transcript** so the library copy, sidecar, and archived original are created. Schema and layout: [STORAGE.md](STORAGE.md). Programmatic import: [Host STT automation](host-stt.md#python-api).

## Optional recipes

These stay outside the analysis image. **Run in app** orchestrates `docker run` / `whispermlx` from the Streamlit process when those binaries are visible. **Copy command** still never executes the snippet.

- **WhisperX** — Transcribe Audio → **Run in app** (WhisperX Docker) or **Copy command** → **WhisperX Docker**. Full recipe: [docs/recipes/whisperx/](../recipes/whisperx/README.md).
- **Whisper-WebUI** — Gradio UI; hand-off is **SRT/VTT → Import Transcript**. Full recipe (including Apple Silicon notes): [docs/recipes/whisper-webui/README.md](../recipes/whisper-webui/README.md). On Apple Silicon the container is expected to use **CPU** inference; prefer host **whispermlx** when Metal/MLX speed matters.

## Import a whole folder

On **Import Transcript**, section **Import all from folder** scans an **absolute** local directory and imports eligible files (JSON, SRT, VTT, TXT, HTML). Source files are never deleted or modified.

- Docker: mount the host folder (typically `HOST_TRANSCRIPT_INBOX_DIR` → `/mnt/transcript-inbox`). Do not scan `/mnt/transcripts` or its subdirs.
- Preview first. Already-imported stems, stem conflicts, and unrepairable files are blocked. Duplicate stems in the folder are all marked conflict.
- Same-stem audio in approved recordings folders is listed as found or none; it is not copied automatically.

Limits and eligibility rules: [Host STT automation](host-stt.md#import-a-whole-folder-details).

## Language variants

Import an alternate-language version next to an existing transcript using a filename suffix: `meeting.json` (base) and `meeting_fr.json` (French). Identify speakers on the base first; import then copies display names into the variant when the IDs match. Details: [Host STT automation](host-stt.md#multi-language-variants).

## Why engines stay outside the analysis image

Transcription runs on the **host** (whispermlx binary, WhisperX Docker, or Whisper-WebUI). The GUI either orchestrates those host tools or copies a command.

| Where | What runs |
|-------|-----------|
| Host (terminal or in-app provider) | `whispermlx` / `whispermlx-missing` (macOS), WhisperX `docker run`, optional Whisper-WebUI Docker, `inbox-watch` |
| `transcriptx-web` (Docker or native) | Import, library, analysis, artifacts; optional STT **orchestration** only when the provider binary/daemon is visible to that process |

The recommended install runs analysis in a **Linux** container. **whispermlx** must run on the **macOS host** (Metal/MLX); it cannot run inside that container. Keeping engines out of the analysis image avoids bloating it. Stacks, shared folders, and when **Run in app** works: [STT stacks](../recipes/stt-stacks/README.md).

**Theme H:** optional in-app / host-orchestrated transcription is shipped for Whisper-class providers — [ROADMAP.md](../ROADMAP.md) theme **H**. NVIDIA Parakeet/Canary and YouTube ingest are later. In-app directory watch for audio auto-transcribe is theme **G2** + **H3** — [directory_watcher.md](directory_watcher.md).

## Advanced

- [STT stacks](../recipes/stt-stacks/README.md) — Compose + host whispermlx + optional WhisperX / WebUI
- [Host STT automation](host-stt.md) — whispermlx-missing, inbox-watch `--transcribe`, config, Python import API
- [Audio prep](audio-prep.md) — Tools → Preprocessing / Auto-merge before you transcribe
- [Directory watcher](directory_watcher.md) — in-app inbox; audio `auto_transcribe` when an STT provider is available
