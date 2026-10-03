# First analysis: from transcript to useful results

The shortest realistic path from importing a transcript to reading your first analysis results.

## Outcome

You will have [imported](../runtime/transcription.md) a transcript, **named diarized speakers**, completed a [**Balanced**](../runtime/settings.md#analysis-presets) analysis run, and identified several useful outputs on [**Overview**](../public_surfaces.md).

## Starting point

TranscriptX is running and you can open the sidebar. You do not need local AI for this workflow.

Download or copy the sample file [planning_review.json](fixtures/planning_review.json) so you can import it.

For a **native** install from git (not Docker), install chart dependencies before **Balanced** — for example `./transcriptx.sh` or `pip install -e ".[full,web]"` — so modules that write charts do not fail mid-run. See [Installation](../runtime/installation.md).

## What you’ll do

1. Import the sample transcript.
2. Glance at the transcript text.
3. Name speakers in **Speaker Identification** (required for most **Balanced** modules on diarized labels).
4. Run analysis with the **Balanced** preset.
5. Open **Overview** and note the main results.
6. Decide where to go next.

## Walkthrough

1. Open **Import Transcript**. Upload `planning_review.json` and confirm the import. The library should list **Launch planning review (docs walkthrough)** (or the filename stem if the title is shown differently).

![Import Transcript page with the planning review JSON selected for upload](../_static/workflows/first-analysis-import.png)

2. Open **Library**, select the new transcript in the table, then open **Transcript**. Skim a few turns so you know the cast uses diarized labels such as `SPEAKER_00`.

3. Open [**Speaker Identification**](speaker-identification.md) for the same transcript. Assign a display name to each diarized speaker (or ignore junk labels). Most speaker-aware modules **skip** until names exist — running **Balanced** before this step usually yields an empty or sparse **Overview**.

4. Open **Run Analysis**. Keep the target as **Transcript** and the analysis preset as **Balanced** (the default). Balanced runs a practical core set without requiring local AI for the non-LLM modules.

![Run Analysis page showing the Balanced preset ready to launch](../_static/workflows/first-analysis-run-analysis.png)

5. Choose **Run analysis** and wait until the progress panel reports completion. A success message naming the output folder appears when the run finishes.

![Short clip of launching Balanced analysis and seeing the run progress panel advance](../_static/workflows/first-analysis-run-complete.gif)

6. Open **Overview** for the selected transcript and run. Check **At a glance**, the speaker cards, and the compact highlights strip.

![Overview page after a Balanced run showing at-a-glance metrics and highlights](../_static/workflows/first-analysis-overview.png)

7. Pick two or three outputs that look useful for this meeting — for example a theme-related highlight, a speaker card, or run status. You do not need every panel yet.

8. From here, refine names if needed, dig into a specific question ([**Insights**](investigate-evidence.md)), or [export](../runtime/export.md) once you trust the results.

## What to notice

- **Balanced** is the recommended first preset: enough signal to explore, without Thorough’s full cost.
- Overview is a landing surface, not the whole analysis. Deeper detail lives under **Insights**, **Charts**, and **Transcript**.
- Diarized labels (`SPEAKER_00`, …) are placeholders until you name speakers; many modules skip until names exist.
- Run status on Overview tells you whether modules completed, skipped, or failed — useful before you trust a blank panel.

## You should now have…

An imported sample transcript, named speakers, a completed Balanced run, and a mental map of Overview’s main blocks.

## Next

- [Identify and name speakers](speaker-identification.md) (deeper naming, profiles, audio clips)
- [Investigate a question and trace it back to evidence](investigate-evidence.md)
- [Installation](../runtime/installation.md) if the UI is not running yet
