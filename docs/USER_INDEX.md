Type: GUIDE
Authority: docs/PRODUCT.md

# User documentation index

Curated entry points for people using TranscriptX (not repository historians).

## Start here

| Doc | Purpose |
|-----|---------|
| [README.md](../README.md) | Product landing and quickstart |
| [Website](../website/index.html) | Modest public landing (GitHub Pages) |
| [PRODUCT.md](PRODUCT.md) | Product definition |
| [Comparison](comparison.md) | TranscriptX vs STT, meeting assistants, and CI products |
| [Installation](runtime/installation.md) | Install profiles and configuration |
| [Settings & knobs](runtime/settings.md) | GUI scopes, Common vs Advanced, profile taxonomy |
| [Transcription](runtime/transcription.md) | External transcription workflows |
| [Directory watcher](runtime/directory_watcher.md) | Optional inbox watch → import (default-off) |
| [Docker](runtime/docker.md) | Compose-based runtime |
| [NOTICE](../NOTICE) | Third-party model / dataset notice |
| [Known limitations](known_limitations.md) | User-facing limits (experimental, optional stacks, AI, privacy, EPUB, Speaker ID CCv2 rollback) |
| [Export (ZIP / HTML / EPUB)](runtime/export.md) | Overview artifact export packages |
| [Using TranscriptX: five workflows](workflows/index.md) | Outcome-focused walkthroughs with screenshots |

## Reference

| Doc | Purpose |
|-----|---------|
| [Models](runtime/models.md) | Analysis models |
| [LLM (Ollama)](runtime/llm.md) | Optional local AI |
| [Corrections (viewer)](runtime/corrections-viewer.md) | Theme B: propose/apply while reading |
| [Karaoke playback](runtime/karaoke-playback.md) | Theme D: word highlight while listening |
| [Corrections Studio LLM](runtime/corrections-llm.md) | Optional Ollama discovery in Studio |
| [Module catalog](generated/modules.md) | Generated module list |
| [Web launcher / Python API](generated/cli.md) | Supported entry flags and API |
| [Terminology](TERMS.md) | Non-authoritative term index |
| [WhisperX recipe](recipes/whisperx/README.md) | Optional standalone WhisperX Docker recipe |
| [Whisper-WebUI recipe](recipes/whisper-webui/README.md) | Optional third-party Gradio recipe (ownership disclaimer; SRT/VTT → import) |

## Contracts (rules, not tutorials)

Prefer the [Contract index](CONTRACT_INDEX.md) for invariants. Key user-visible contracts:

- [Public surfaces](public_surfaces.md)
- [Storage](runtime/STORAGE.md)
- [Run outcomes](run_outcome_contract.md)
- [Output layout](contracts/output-contract-v1.md)

## Module runtime notes

- [Lexical diversity](runtime/lexical_diversity.md)
- [Keyphrases](runtime/keyphrases.md)
- [Epistemic markers](runtime/epistemic_markers.md)
- [Politeness](runtime/politeness.md)
- [Topic shift](runtime/topic_shift.md)
- [Transcript quality](runtime/transcript_quality.md)

## Not in this index

Developer plans, inventories, and historical archives live under [DEV_INDEX.md](DEV_INDEX.md) and [archive/ARCHIVE_INDEX.md](archive/ARCHIVE_INDEX.md).
