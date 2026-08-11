# Karaoke playback (Transcript viewer)

Theme D adds clip-scoped karaoke reading on the Transcript page.

## Behaviour

1. Press **▶** on a Turns/Segments line (or chapter **Play**).
2. The sticky player loads that segment clip (same ffmpeg extract path as before).
3. When imported `words[]` timings align and cover enough of the clip, the player
   highlights **word-by-word** from the browser playhead and supports
   **click-a-word → seek**.
4. When timings are missing, incomplete, or nulled by corrections, the player
   uses **segment-level** highlight only and shows an honesty caption — timings
   are never invented.
5. The list marks the active line with a **Playing** badge and scrolls it into
   view once.

## Honesty / limits

- Playhead stays **browser-local** (iframe); it is not streamed into Streamlit
  session state.
- Clips remain capped at the existing ClipService window (60s); words outside
  that window are not timed for karaoke.
- Continuous full-file karaoke and a CCv2-native reader surface are follow-ons
  (see [ROADMAP Theme D](../ROADMAP.md)).

## Related

- Correct mode nulls timings on edited tokens — see [corrections-viewer.md](corrections-viewer.md).
- PlaybackHost contract: `transcriptx.web.workspaces.playback_host`.
