# Karaoke playback (Transcript viewer)

Theme D provides **full-file** karaoke reading on the Transcript page via the
CCv2 **reader workspace** (default-on). The legacy **clip-scoped** iframe player
remains available when `TX_READER_WORKSPACE_COMPONENT=0`.

## Behaviour (reader workspace, default)

1. Open a transcript with a resolved audio file. The reader mounts above the
   turns/segments tabs and plays the **source recording** (not a 60s extract).
2. Word-by-word highlight and **click-a-word → seek** use absolute `words[]`
   timings when coverage is honest (same rules as clip karaoke).
3. When timings are missing, incomplete, or nulled by corrections, the reader
   uses **segment-level** highlight only and shows an honesty caption — timings
   are never invented.
4. Follow-along scroll keeps the active turn in view while audio plays.
5. Chapter **Jump** / **Play** still work; Play seeks the reader and starts
   playback when the workspace is mounted.
6. **Correct mode** disables the reader and uses the clip player + `viewer_edit`
   word selection (editing does not depend on the loopback media route).

## Rollback (clip player)

Set `TX_READER_WORKSPACE_COMPONENT=0` (or `false` / `off`) to restore the
previous clip-scoped player:

1. Press **▶** on a Turns/Segments line (or chapter **Play**).
2. The sticky player loads that segment clip (ffmpeg extract, 60s cap).
3. Karaoke rules match the reader; words beyond the clip window are not timed.

## Honesty / limits

- Playhead stays **browser-local**; it is not streamed into Streamlit session
  state.
- Full-file audio is served from a **loopback-only** HTTP route
  (`127.0.0.1`, session token). It does not work when Streamlit binds a
  non-loopback host or over HTTPS without a matching media URL.
- Very large transcripts may omit per-word timings in the JSON payload
  (`word_timing_omitted`); playback and segment highlight still work.
- Speaker ID clip extracts are unchanged (ClipService 60s cap).

## Related

- Correct mode nulls timings on edited tokens — see [corrections-viewer.md](corrections-viewer.md).
- PlaybackHost contract: `transcriptx.web.workspaces.playback_host`.
- Theme C workspaces (shared package): [theme_c_workspaces_ccv2.md](../dev/theme_c_workspaces_ccv2.md).
- Code: `src/transcriptx/web/media_route.py`, `src/transcriptx/web/workspaces/reader_bridge.py`,
  `packages/transcriptx_workspaces` `reader_workspace`, flag `TX_READER_WORKSPACE_COMPONENT`.
