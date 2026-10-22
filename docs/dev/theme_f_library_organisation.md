# Theme F — Library organisation

Status: kind tags, Groups picker filter, and opt-in YouTube Data API rename shipped; pin/favourite deferred  
Roadmap: [ROADMAP.md](../ROADMAP.md) §F

## Locked decisions

1. **Tags find and filter transcripts.** They are organisation metadata on `processing_state.json` (`tags` / `tag_details`), not an analysis module.
2. **Groups are analysis cohorts.** Tagging must not create, update, or imply `.group.json` membership.
3. **Groups picker may AND-filter by tags.** Filtering is not membership. Shipped on Create group and Edit membership.
4. **Kind vocabulary (first-class chips):** `meeting`, `voice note`, `lone speaker`. Existing semantic tags (`idea`, `reflection`, `todo`, `question`) remain valid free-form tags.
5. **Auto-seed is optional and manual-wins.** Suggested kind tags use `source=auto` only when the tag is not already present. Manual tags are never overwritten.
6. **Visibility this wave is facets only.** Pin/favourite is deferred.
7. **YouTube Data API rename** is opt-in via `TRANSCRIPTX_YOUTUBE_API_KEY` (title queries only). DuckDuckGo remains the no-key path. It is not required for tagging.

## Storage

Canonical store: `{data_dir}/state/processing_state.json`. Do not write organisation tags into group manifests, group run schemas, import sidecars, or canonical transcript JSON.
