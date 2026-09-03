Type: GUIDE
Authority: PRODUCT.md

# TranscriptX documentation

TranscriptX is a local-first workbench for people who want to think with transcripts. You import files you already have, run analysis on your machine, and keep the results.

It does **not** transcribe audio in the app. Bring JSON, SRT, VTT, or similar files, then use **Import Transcript**.

**See how it works:** [first analysis](workflows/first-analysis.md) — import the sample, run **Balanced**, read **Overview**.  
**Everyday jobs:** [Using TranscriptX](workflows/index.md).  
**Is this for me?** [How TranscriptX compares](comparison.md).  
**Privacy:** files stay on your computer; optional local AI is [Ollama](runtime/llm.md) and off by default.

The GitHub [README](https://github.com/glen-w/TranscriptX#readme) is the same first-run story.

```{toctree}
:maxdepth: 2
:caption: Start here

comparison
workflows/first-analysis
workflows/index
runtime/installation
runtime/transcription
PRODUCT
```

```{toctree}
:maxdepth: 2
:caption: Workflows

workflows/speaker-identification
workflows/investigate-evidence
workflows/local-ai-synthesis
workflows/export-results
workflows/charts
workflows/groups
workflows/corrections
workflows/rename-transcript
workflows/speakers
```

```{toctree}
:maxdepth: 2
:caption: Using TranscriptX

runtime/settings
runtime/docker
runtime/directory_watcher
runtime/export
backup_and_restore
known_limitations
runtime/models
runtime/llm
runtime/corrections-viewer
runtime/karaoke-playback
runtime/corrections-llm
TERMS
recipes/whisperx/README
recipes/whisper-webui/README
```

```{toctree}
:maxdepth: 1
:caption: Developers

DEV_INDEX
ROADMAP
ARCHITECTURE
developer_quickstart
reviews/index
CONTRACT_INDEX
public_surfaces
runtime/STORAGE
generated/modules
generated/cli
runtime/lexical_diversity
runtime/keyphrases
runtime/epistemic_markers
runtime/politeness
runtime/topic_shift
runtime/transcript_quality
```

## More indexes

- [User documentation index](USER_INDEX.md)
- [Developer documentation index](DEV_INDEX.md)
