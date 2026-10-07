# Batch warm: assistive LLM suggestions

High-compute **assistive** passes (speaker name dropdowns, rename stem prefills) can run overnight so the GUI opens with caches already warm. Nothing is renamed and no speaker-map names are written until you confirm in the UI.

## What this warms

| Consumer | GUI surface | Cache location |
|----------|-------------|----------------|
| `speaker_name_suggestions` | Speaker Identification → Name dropdown (after warm, no **Suggest names** click) | `speaker_profiles/.cache/identify/{managed_id}.name_suggestions.v1.json` |
| `rename_suggestions` | Rename Transcript / import rename forms when **Content rename suggestions** is `auto` | `{data_dir}/.cache/rename/*.rename_suggestions.v1.json` |

Caches invalidate when transcript content fingerprints change or when rename knobs / model tags in the cache key change (see [llm.md](llm.md) consumers).

## What this is not

- **Voice pre-load** (Settings → Speakers → Pre-load voice suggestions) warms ECAPA voice match caches under `speaker_profiles/.cache/voice/` — different stack. See [speaker-voice-matching.md](../workflows/speaker-voice-matching.md).
- **`python -m transcriptx.identify_speakers`** fuses voice + text and can **write** speaker-map names and profile links — not the assistive Suggest-names LLM cache.
- **Run Analysis → Batch** runs analysis pipeline LLM modules — not rename/name suggestion warmers.

## Prerequisites

1. Managed library transcripts (admitted with import sidecars).
2. For LLM passes: Ollama running; Models preset assigns non-thinking tags for `speaker_name_suggestions` and/or `rename_suggestions` ([llm.md](llm.md)).
3. Rename warm: `input.rename_content_suggestions=auto` and optional `rename_suggest_llm` / web knobs ([settings.md](settings.md)).

## GUI

- **Settings → Speakers → Assistive LLM suggestions → Pre-load name suggestions (LLM)** — library-wide speaker-name cache warm.
- **Settings → Configuration** — when content rename suggestions are `auto`, **Pre-load rename suggestions** appears above the config editor.

## CLI (cron-shaped)

```bash
transcriptx warm-suggestions --help
# equivalent:
python -m transcriptx.warm_suggestions --help
```

Python API:

```python
from transcriptx.app.models.requests import WarmSuggestionsRequest
from transcriptx.app.workflows import run_warm_suggestions

result = run_warm_suggestions(WarmSuggestionsRequest(warm_all=True))
```

| Flag | Meaning |
|------|---------|
| `--speaker-names` | Warm speaker name suggestion caches (managed transcripts only). |
| `--rename` | Warm rename suggestion caches (`rename_content_suggestions=auto`). |
| `--all` | Both passes. |
| `--path FILE` | Repeatable; default is entire managed library. |
| `--force` | Recompute even when cache is fresh. |
| `--dry-run` | List actionable targets without LLM or writes. |

Exit code `0` on success, `1` if any transcript failed, `2` for usage errors.

### Cron example (Linux / macOS)

```bash
# Nightly at 02:00 — warm both suggestion types
0 2 * * * cd /path/to/transcriptx && . .venv/bin/activate && \
  TRANSCRIPTX_DATA_DIR=/path/to/data \
  transcriptx warm-suggestions --all \
  >> ~/.transcriptx/warm-suggestions.log 2>&1
```

### launchd example (macOS, templated)

Save as `~/Library/LaunchAgents/com.example.transcriptx.warm-suggestions.plist` (replace paths):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.example.transcriptx.warm-suggestions</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/transcriptx/.venv/bin/python</string>
    <string>-m</string>
    <string>transcriptx.warm_suggestions</string>
    <string>--all</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>TRANSCRIPTX_DATA_DIR</key>
    <string>/path/to/data</string>
  </dict>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>2</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>/path/to/.transcriptx/warm-suggestions.log</string>
  <key>StandardErrorPath</key>
  <string>/path/to/.transcriptx/warm-suggestions.log</string>
</dict>
</plist>
```

Load: `launchctl load ~/Library/LaunchAgents/com.example.transcriptx.warm-suggestions.plist`

STT ingest scheduling uses [`inbox-watch`](host-stt.md) (`--once` for cron) — a separate job from suggestion warm.

### Dry-run smoke

```bash
TRANSCRIPTX_DATA_DIR=/path/to/data \
  python -m transcriptx.warm_suggestions --all --dry-run
```

## Related

- [settings.md](settings.md) — rename and voice knobs
- [STORAGE.md](STORAGE.md) — disposable `.cache/` under `speaker_profiles` and `data_dir`
- [speaker-identification.md](../workflows/speaker-identification.md) — Suggest names UX
- [rename-transcript.md](../workflows/rename-transcript.md) — content rename suggestions
