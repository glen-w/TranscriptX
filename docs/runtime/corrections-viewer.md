# Corrections in the Transcript viewer

Theme B adds word/span propose–apply while reading. Corrections Studio remains the batch detector/LLM review surface.

## Correct mode

1. Open **Transcript** and enable **Correct mode** (or use library action **Correct in viewer**).
2. Expand **Propose correction** on a segment.
3. Select a word range (when `words[]` align) or enter **exact unique** find text (ambiguous matches are rejected).
4. Enter a replacement, then:
   - **Propose** — adds a `manual` / `viewer_manual` candidate to the current Studio session (no detector run required).
   - **Accept & apply this** — accepts that candidate and writes a **scoped** corrected sidecar only (other accepted Studio candidates are not applied).

The managed original transcript is never overwritten by this path.

## Sessions and generation

- **Start / Resume** in Corrections Studio opens a session without generating detector candidates.
- First viewer propose may create a `manual_seed` generation.
- **Generate Candidates** runs detectors; existing viewer manuals and their reviews are **carried forward** into the new detector generation.
- Listing and stats default to the **current generation** only.

## Opening a corrected sidecar

Opening the corrected file establishes it as a new subject with a **new** transcript identity and Corrections session. Further proposes bind to the sidecar, not the parent session.

## Honesty

- Auto/assist detector and LLM candidates stay labelled in Studio.
- Low ASR confidence chips in Correct mode are propose affordances only — replacements remain human-entered.
- Edited / new word tokens get **null timings** (no fabricated proportional timings) so Theme D karaoke can degrade honestly — see [karaoke-playback.md](karaoke-playback.md).
