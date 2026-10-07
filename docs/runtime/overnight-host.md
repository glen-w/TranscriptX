# Overnight / host automation

Cron- and launchd-shaped commands that run **without Streamlit**. Nightshift’s Mac job [`transcriptx-night`](https://github.com/glen-w/nightshift/tree/main/jobs/transcriptx-night) (local path `~/Documents/nightshift/jobs/transcriptx-night/`) is the house scheduler for these; this page documents the TranscriptX side only.

Interactive workspaces (Corrections, Speaker ID review, Charts/Ask) stay in the GUI.

## Allowlisted host CLI

```bash
transcriptx --help
# equivalent modules: python -m transcriptx.<command>
```

| Command | Role |
|---------|------|
| `cleanup-runs` | Bulk-delete analysis runs (`delete-old` keeps newest per subject) |
| `analyze-modules` | Catch up selected modules across the library |
| `analyze-backlog` | Thorough analysis for ready, unanalyzed transcripts |
| `warm-suggestions` | Assistive rename / speaker-name LLM caches ([llm-suggestion-batch.md](llm-suggestion-batch.md)) |
| `analyze` | One managed transcript |
| `admit-originals` / `import` / `rename` / `identify-speakers` / `backup` | Other host ops (see [cli.md](../generated/cli.md)) |

Companion script (not a `transcriptx` subcommand): `scripts/inbox-watch.py` — see [host-stt.md](host-stt.md).

## Nightshift phase mapping

Typical overnight order (01:00–07:00 local):

1. **`cleanup-runs --mode delete-old --keep-human-readable --keep-llm-summaries`**  
   Delete older run directories; salvage readable transcripts, `report.md`/`report.txt`, and `*_llm_summary.*` into `{subject}/.retained/{run_id}/` first.

2. **`inbox-watch.py --once`**  
   One admit/STT pass from the configured inbox (USB may be absent).

3. **`analyze-modules --modules transcript_output,llm_summary --allow-unnamed-speakers`**  
   Whole library. Speakers need not be identified. Skips a transcript when the newest committed run’s `modules_run` already includes every requested module.

4. **`analyze-backlog --preset thorough --require-complete-speakers --require-named-speaker Glen`**  
   Only transcripts with **no** analysis outputs yet, a **complete** speaker map, and **Glen** among effective display names.

5. **`warm-suggestions --all`**  
   Cache only; no renames, no speaker-map writes.

## analyze-modules

```bash
transcriptx analyze-modules --help
transcriptx analyze-modules --dry-run --max 5
transcriptx analyze-modules --modules transcript_output,llm_summary --allow-unnamed-speakers
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--modules` | `transcript_output,llm_summary` | Comma-separated module ids |
| `--allow-unnamed-speakers` | on | Diarized labels count; use `--no-allow-unnamed-speakers` to require names |
| `--force` | off | Re-run even when newest run already has every module |
| `--max N` | `0` | Cap transcripts (`0` = no limit) |
| `--dry-run` | off | List targets only |

Presence check: newest run dir under the subject outputs root → `run_results.json` → `modules_run`.

## analyze-backlog

```bash
transcriptx analyze-backlog --dry-run --require-named-speaker Glen --max 5
transcriptx analyze-backlog --preset thorough --mode full \
  --require-complete-speakers --require-named-speaker Glen
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--require-complete-speakers` | on | Speaker map status must be `complete` |
| `--require-named-speaker NAME` | none | Repeatable; all names must appear (case-insensitive) among effective display names |
| `--preset` / `--mode` | `thorough` / `full` | Pipeline selection |
| `--max N` | `0` | Cap |

Skips transcripts that already have analysis outputs (non-empty subject output tree).

## cleanup-runs

```bash
transcriptx cleanup-runs --mode delete-old \
  --keep-human-readable --keep-llm-summaries --dry-run
transcriptx cleanup-runs --mode delete-old \
  --keep-human-readable --keep-llm-summaries --yes
```

Non-interactive confirm: `--yes` or `TRANSCRIPTX_CLEANUP_YES=1`. Prefer `--dry-run` before the first real delete.

Retain flags copy keep-files aside before deleting an older run tree. Newest run per subject is retained in place.

## Prerequisites

1. Managed library (admitted transcripts with sidecars).
2. Ollama up for LLM modules and warmers ([llm.md](llm.md)).
3. For inbox: `.transcriptx/inbox-watch.json` (or env overrides) pointing at a real inbox/recordings/transcripts layout ([host-stt.md](host-stt.md)).
