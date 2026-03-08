# CLI Command Reference

*This documentation reflects the CLI help output. Run `transcriptx --help` and `transcriptx <command> --help` for the latest. When commands or options change, update this file to match (see docs/CONTRIBUTING.md).*

## Main Command

Invoke the CLI as **`transcriptx`** (when the package is installed) or **`python -m transcriptx.cli.main`** from the project root with `PYTHONPATH=src`.

```
                                                                                
 Usage: transcriptx [OPTIONS] COMMAND [ARGS]...              
                                                                                
 🎤 TranscriptX - Advanced Transcript Analysis Toolkit                          
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --config      -c      PATH  Path to configuration file                       │
│ --log-level           TEXT  Logging level (DEBUG, INFO, WARNING, ERROR)      │
│ --output-dir  -o      PATH  Custom output directory                          │
│ --core                      Force core mode (only core modules, no           │
│                             auto-install of optional deps)                   │
│ --no-core                   Disable core mode (all modules, allow            │
│                             auto-install)                                    │
│ --help                      Show this message and exit.                      │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ gui                   Launch the integrated Streamlit GUI (primary           │
│                       interactive experience)                                │
│ web-viewer            Launch the Streamlit web viewer interface              │
│ analyze               Analyze a transcript file with specified modules and   │
│                       settings.                                              │
│ transcribe            [DEPRECATED] TranscriptX no longer transcribes audio   │
│                       directly. See docs/transcription.md.                   │
│ identify-speakers     Identify speakers in a transcript file.                │
│ preprocess            Run audio preprocessing on a single file (MP3, WAV, or │
│                       other supported format).                               │
│ prep-audio            Batch audio preparation: convert and normalize audio   │
│                       files to MP3. No transcription.                        │
│ batch-analyze         Bulk analysis on existing transcript JSON files in a   │
│                       folder.                                                │
│ deduplicate           Find and remove duplicate files in a folder.           │
│ simplify-transcript   Simplify a transcript by removing tics, hesitations,   │
│                       repetitions, and agreements, focusing on substantive   │
│                       content and decision points, while maintaining         │
│                       conversational flow.                                   │
│ interactive           Launch the interactive menu (default when run with no  │
│                       arguments).                                            │
│ settings              Manage settings via flags (show/edit/save).            │
│ test-analysis         Run test analysis via flags (non-interactive).         │
│ whisperx-web-gui      [DEPRECATED] TranscriptX no longer ships WhisperX Web  │
│                       GUI. See docs/transcription.md.                        │
│ database              Database management commands                           │
│ cross-session         Cross-session speaker tracking commands                │
│ transcript            Transcript management commands                         │
│ artifacts             Artifact validation commands                           │
│ group                 TranscriptSet group commands                           │
│ perf                  Performance span queries                               │
│ analysis              Analysis commands                                      │
│ deps                  Optional dependency status and install (extras)        │
│ doctor                Diagnostics commands                                   │
│ audit                 Audit pipeline runs                                    │
│ process-wav           Process audio files: convert, merge, or compress (WAV, │
│                       MP3, OGG, etc.)                                        │
╰──────────────────────────────────────────────────────────────────────────────╯


```

**Usage:** Run `transcriptx` with no arguments for the interactive menu. For any command, run `transcriptx <command> --help` for full options. The **doctor** and **audit** groups run their default action when invoked with only global options (e.g. `transcriptx doctor`, `transcriptx audit -r <run_id>`).

## Subcommands

Only a subset of subcommands are expanded below. For the rest (e.g. `gui`, `web-viewer`, `batch-analyze`, `preprocess`, `prep-audio`, `simplify-transcript`, `settings`, `test-analysis`, `deduplicate`, `cross-session`, `perf`, `analysis`, `deps`, `artifacts`, `group`), run `transcriptx <command> --help`.

### analyze

```
                                                                                
 Usage: transcriptx analyze [OPTIONS]                        
                                                                                
 Analyze a transcript file with specified modules and settings.                 
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --transcript-file               -t      PATH  Path to transcript JSON file   │
│ --transcripts                           PATH  Analyze multiple transcripts   │
│                                               as a group (repeat flag for    │
│                                               each file)                     │
│ --all-transcripts                             Analyze all available          │
│                                               transcript JSON files          │
│ --mode                          -m      TEXT  Analysis mode: quick or full   │
│                                               [default: quick]               │
│ --modules                               TEXT  Comma-separated list of        │
│                                               modules or 'all'               │
│                                               [default: all]                 │
│ --profile                               TEXT  Semantic profile for full      │
│                                               mode: balanced, academic,      │
│                                               business, casual, technical,   │
│                                               interview                      │
│ --skip-confirm                                Skip confirmation prompts      │
│ --output-dir                    -o      PATH  Custom output directory        │
│ --include-unidentified-speake…                Include unidentified speakers  │
│                                               in per-speaker outputs         │
│ --anonymise-speakers                          Anonymise speaker display      │
│                                               names in outputs               │
│ --skip-speaker-identification                 Skip the speaker               │
│                                               identification gate            │
│ --non-interactive                             Run in non-interactive mode    │
│                                               (skip all prompts)             │
│ --persist                                     Persist run metadata and       │
│                                               artifacts to DB                │
│ --manifest                              PATH  Load run input from a          │
│                                               RunManifestInput JSON file     │
│                                               (overrides -t and              │
│                                               module/speaker flags)          │
│ --accept-noncanonical                         Allow analyzing transcript     │
│                                               files that do not use the      │
│                                               canonical filename             │
│                                               (*_transcriptx.json). Use only │
│                                               when the file is already in    │
│                                               TranscriptX schema.            │
│ --help                                        Show this message and exit.    │
╰──────────────────────────────────────────────────────────────────────────────╯


```

### database

```
                                                                                
 Usage: transcriptx database [OPTIONS] COMMAND [ARGS]...     
                                                                                
 Database management commands                                                   
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ reset                  Reset the database (dev-only).                        │
│ init                   Initialize the TranscriptX database.                  │
│ clean-test-artifacts   Remove old testing artifacts to fix stagnant          │
│                        dropdowns and transcript-not-found warnings.          │
│ status                 Display database status and information.              │
│ migrate                Manage database migrations.                           │
│ history                Display migration history.                            │
│ profile-speaker        Create or update a speaker profile from transcript    │
│                        data.                                                 │
│ list-speakers          List all speakers in the database.                    │
│ speakers-list          List all speakers with their statistics.              │
│ speakers-show          Show detailed information about a speaker.            │
│ speakers-merge         Merge two speakers into one.                          │
│ speakers-stats         Show aggregate speaker statistics.                    │
│ export-speaker-maps    Export speaker identity from the database into        │
│                        transcript JSON files.                                │
╰──────────────────────────────────────────────────────────────────────────────╯


```

### identify-speakers

```
                                                                                
 Usage: transcriptx identify-speakers [OPTIONS]              
                                                                                
 Identify speakers in a transcript file.                                        
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ *  --transcript-file  -t      PATH  Path to transcript JSON file [required]  │
│    --overwrite                      Overwrite existing speaker               │
│                                     identification without confirmation      │
│    --skip-rename                    Skip transcript rename after speaker     │
│                                     identification                           │
│    --help                           Show this message and exit.              │
╰──────────────────────────────────────────────────────────────────────────────╯


```

### process-wav

```
                                                                                
 Usage: transcriptx process-wav [OPTIONS] COMMAND [ARGS]...  
                                                                                
 Process audio files: convert, merge, or compress (WAV, MP3, OGG, etc.)         
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ convert    Convert audio files (WAV, MP3, OGG, etc.) to MP3.                 │
│ merge      Merge multiple audio files (WAV, MP3, OGG, etc.) into one MP3     │
│            file.                                                             │
│ compress   Compress WAV files in backups directory into zip archives.        │
╰──────────────────────────────────────────────────────────────────────────────╯


```

### transcribe

```
                                                                                
 Usage: transcriptx transcribe [OPTIONS]                     
                                                                                
 [DEPRECATED] TranscriptX no longer transcribes audio directly. See             
 docs/transcription.md.                                                         
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --audio-file                    -a      PATH  Path to audio file             │
│ --engine                                TEXT  (Deprecated) [default: auto]   │
│ --analyze                                     (Deprecated)                   │
│ --analysis-mode                 -m      TEXT  (Deprecated) [default: quick]  │
│ --analysis-modules                      TEXT  (Deprecated) [default: all]    │
│ --skip-confirm                                (Deprecated)                   │
│ --print-output-json-path,--js…                (Deprecated)                   │
│ --help                                        Show this message and exit.    │
╰──────────────────────────────────────────────────────────────────────────────╯


```

### transcript

```
                                                                                
 Usage: transcriptx transcript [OPTIONS] COMMAND [ARGS]...   
                                                                                
 Transcript management commands                                                 
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ validate       Validate transcript JSON against canonical schema             │
│ canonicalize   Convert transcript JSON to canonical TranscriptX format       │
│ list           List all conversations in the database.                       │
│ show           Show detailed information about a conversation.               │
│ delete         Delete a conversation and all associated data.                │
│ export         Export conversation data to JSON file.                        │
│ store          Store a transcript file in the database.                      │
│ status         Show database status and statistics.                          │
╰──────────────────────────────────────────────────────────────────────────────╯


```
