# User documentation sitemap

Every user-facing page, grouped by job. This is a **list**, not a second start page.

First visit: [docs home](index.md) or [First analysis](workflows/first-analysis.md). Developers: [DEV_INDEX.md](DEV_INDEX.md).

## Product and first run

| Doc | Purpose |
|-----|---------|
| [README.md](../README.md) | What it is, screenshots, first analysis, install |
| [Website](../website/index.html) | Public landing (GitHub Pages) |
| [docs home](index.md) | Hosted docs start |
| [PRODUCT.md](PRODUCT.md) | Product definition |
| [Comparison](comparison.md) | Is TranscriptX the right tool? |
| [Comparison reference](comparison-reference.md) | Vendor-by-vendor notes |
| [Known limitations](known_limitations.md) | Optional stacks, AI, privacy |
| [Terminology](TERMS.md) | Term index |

## Workflows

| Doc | Purpose |
|-----|---------|
| [Using TranscriptX](workflows/index.md) | Outcome-led walkthrough index |
| [First analysis](workflows/first-analysis.md) | Import a sample → Balanced run → Overview |
| [Identify and name speakers](workflows/speaker-identification.md) | Name diarized labels |
| [Investigate with evidence](workflows/investigate-evidence.md) | Question → transcript lines |
| [Local AI synthesis](workflows/local-ai-synthesis.md) | Optional Ollama summary / extracts |
| [Export results](workflows/export-results.md) | ZIP / HTML / EPUB |
| [Explore Charts](workflows/charts.md) | Run-scoped charts |
| [Bundle into a group](workflows/groups.md) | Several transcripts together |
| [Correct while reading](workflows/corrections.md) | Propose/apply in Transcript |
| [Rename a transcript](workflows/rename-transcript.md) | Clearer library name |
| [Browse speaker profiles](workflows/speakers.md) | Longitudinal speaker pages |

## Install and run

| Doc | Purpose |
|-----|---------|
| [Installation](runtime/installation.md) | Docker and `./transcriptx.sh` |
| [Installation details](runtime/installation-advanced.md) | Extras, profiles, env, gates |
| [Docker](runtime/docker.md) | Compose-based runtime |
| [Settings](runtime/settings.md) | GUI scopes, presets, knobs |
| [LLM (Ollama)](runtime/llm.md) | Optional local AI |
| [Models](runtime/models.md) | Analysis model defaults |
| [Workspace backup / restore](backup_and_restore.md) | Full-workspace ZIP |

## Bring files

| Doc | Purpose |
|-----|---------|
| [Transcription](runtime/transcription.md) | Bring a file, or generate a host STT command |
| [Host STT automation](runtime/host-stt.md) | whispermlx-missing, inbox-watch, Python import |
| [Audio prep](runtime/audio-prep.md) | Tools → Preprocessing / Auto-merge |
| [Directory watcher](runtime/directory_watcher.md) | In-app inbox → import |
| [WhisperX recipe](recipes/whisperx/README.md) | Optional WhisperX Docker |
| [Whisper-WebUI recipe](recipes/whisper-webui/README.md) | Optional Gradio recipe |

## Read, correct, export

| Doc | Purpose |
|-----|---------|
| [Export](runtime/export.md) | ZIP / HTML / EPUB packages |
| [Corrections viewer](runtime/corrections-viewer.md) | Propose/apply while reading |
| [Corrections LLM](runtime/corrections-llm.md) | LLM discovery in Corrections Studio |
| [Karaoke playback](runtime/karaoke-playback.md) | Word-timed playback |

## Module notes

| Doc | Purpose |
|-----|---------|
| [Lexical diversity](runtime/lexical_diversity.md) | `lexical_diversity` |
| [Keyphrases](runtime/keyphrases.md) | `keyphrases` |
| [Epistemic markers](runtime/epistemic_markers.md) | `epistemic_markers` |
| [Politeness](runtime/politeness.md) | `politeness` |
| [Topic shift](runtime/topic_shift.md) | `topic_shift` |
| [Transcript quality](runtime/transcript_quality.md) | ASR confidence |

## Generated catalogs

| Doc | Purpose |
|-----|---------|
| [Module catalog](generated/modules.md) | Analysis modules |
| [CLI / Python API](generated/cli.md) | Web launcher and typed API |

Not listed here: contracts, storage rules, and programme notes — [DEV_INDEX.md](DEV_INDEX.md) and [CONTRACT_INDEX.md](CONTRACT_INDEX.md).
