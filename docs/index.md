Type: GUIDE
Authority: PRODUCT.md

# TranscriptX documentation

Local-first personal transcript analysis workbench. Start with the product definition, then installation and task guides.

Hosted navigation mirrors [USER_INDEX.md](USER_INDEX.md) for user-facing pages (plus a short Developers section). Sphinx builds the same Markdown tree as the repo — there is no separate docs corpus.

```{toctree}
:maxdepth: 2
:caption: Start here

PRODUCT
comparison
USER_INDEX
known_limitations
runtime/installation
runtime/settings
runtime/transcription
runtime/directory_watcher
runtime/docker
runtime/export
backup_and_restore
```

```{toctree}
:maxdepth: 2
:caption: Workflow walkthroughs

workflows/index
workflows/first-analysis
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
:caption: Reference

runtime/models
runtime/llm
runtime/corrections-viewer
runtime/karaoke-playback
runtime/corrections-llm
generated/modules
generated/cli
TERMS
public_surfaces
CONTRACT_INDEX
runtime/STORAGE
recipes/whisperx/README
recipes/whisper-webui/README
```

```{toctree}
:maxdepth: 1
:caption: Module notes

runtime/lexical_diversity
runtime/keyphrases
runtime/epistemic_markers
runtime/politeness
runtime/topic_shift
runtime/transcript_quality
```

```{toctree}
:maxdepth: 1
:caption: Developers

DEV_INDEX
ROADMAP
ARCHITECTURE
developer_quickstart
```

## Indexes

- [User documentation index](USER_INDEX.md)
- [Developer documentation index](DEV_INDEX.md)
- [Contract index](CONTRACT_INDEX.md)

Historical material is tracked under `docs/archive/` but is excluded from this hosted navigation.
