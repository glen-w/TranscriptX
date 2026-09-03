# Rename a managed transcript

Give a managed library transcript a clearer file name (and rename linked working-copy audio when present) from **Rename Transcript**.

## Outcome

You will have renamed the planning-review sample to a deliberate new stem and confirmed Library lists the new name.

## Starting point

The sample is [imported](../runtime/transcription.md) (see [First analysis](first-analysis.md)). You do not need a completed analysis run for rename itself.

## What you’ll do

1. Open **Rename Transcript**.
2. Select the planning-review transcript.
3. Review the preview clips / current stem when shown.
4. Enter a new file name and submit **Rename**.
5. Confirm Library shows the new name.

## Walkthrough

1. Open **Rename Transcript** from the sidebar workflow section.

2. Choose the planning-review transcript in the page picker. Skim the content preview if shown so you are renaming the intended recording.

3. Under **Rename transcript**, note **Current file name**. Edit **New file name** to something stable and descriptive (for example `planning_review_launch` or a `YYMMDD_`-prefixed stem when the UI suggests a date root).

4. Submit **Rename**. A success message reports the old and new base names (and whether linked audio was renamed).

5. Open **Library** and confirm the transcript list / picker shows the new stem. Downstream outputs stay associated via managed identity; if a run was open, re-select the transcript if the sidebar label looks stale.

Smart suggestions from device filename patterns may appear as token buttons when enabled — optional helpers, not required for this walkthrough.

## What to notice

- Rename updates managed library naming; it is not an export/share step.
- Prefer descriptive stems early — Speaker ID, groups, and exports are easier to recognise later.
- If the picker is empty, import or transcribe first; rename only operates on managed paths.

## You should now have…

A renamed planning-review transcript visible in Library under the new stem.

## Next

- [Identify and name speakers](speaker-identification.md)
- [Bundle transcripts into a group](groups.md)
- [Export a finished analysis](export-results.md)
