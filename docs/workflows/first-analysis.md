Type: GUIDE
Authority: docs/PRODUCT.md

# First analysis: from transcript to useful results

The shortest realistic path from importing a transcript to reading your first analysis results.

## Outcome

You will have imported a transcript, completed a **Balanced** analysis run, and identified several useful outputs on **Overview**.

## Starting point

TranscriptX is running and you can open the sidebar. You do not need local AI for this workflow.

Download or copy the sample file [planning_review.json](fixtures/planning_review.json) so you can import it.

## What you’ll do

1. Import the sample transcript.
2. Glance at the transcript text.
3. Run analysis with the **Balanced** preset.
4. Open **Overview** and note the main results.
5. Decide where to go next.

## Walkthrough

1. Open **Import Transcript**. Upload `planning_review.json` and confirm the import. The library should list **Launch planning review (docs walkthrough)** (or the filename stem if the title is shown differently).

```{image} /_static/workflows/first-analysis-import.png
:alt: Import Transcript page with the planning review JSON selected for upload
:width: 720px
```

2. Open **Library**, select the new transcript, then open **Transcript**. Skim a few turns so you know the cast uses diarized labels such as `SPEAKER_00`. Most speaker-aware modules need human-readable names; if Overview looks sparse after the first run, complete [Speaker-aware trust](speaker-trust.md) and re-run.

3. Open **Run Analysis**. Keep the target as **Transcript** and the analysis preset as **Balanced** (the default). Balanced runs a practical core set without requiring local AI for the non-LLM modules.

```{image} /_static/workflows/first-analysis-run-analysis.png
:alt: Run Analysis page showing the Balanced preset ready to launch
:width: 720px
```

4. Choose **Run analysis** and wait until the progress panel reports completion. A success message naming the output folder appears when the run finishes.

```{image} /_static/workflows/first-analysis-run-complete.gif
:alt: Short clip of launching Balanced analysis and seeing the run progress panel advance
:width: 720px
```

5. Open **Overview** for the selected transcript and run. Check **At a glance**, the speaker cards, and the compact highlights strip.

```{image} /_static/workflows/first-analysis-overview.png
:alt: Overview page after a Balanced run showing at-a-glance metrics and highlights
:width: 720px
```

6. Pick two or three outputs that look useful for this meeting — for example a theme-related highlight, a speaker card, or run status. You do not need every panel yet.

7. From here, either improve speaker names (**Speaker Identification**) or dig into a specific question (**Insights**). Export can wait until you trust the results.

## What to notice

- **Balanced** is the recommended first preset: enough signal to explore, without Thorough’s full cost.
- Overview is a landing surface, not the whole analysis. Deeper detail lives under **Insights**, **Charts**, and **Transcript**.
- Diarized labels (`SPEAKER_00`, …) are placeholders until you name speakers; many modules skip until names exist.
- Run status on Overview tells you whether modules completed, skipped, or failed — useful before you trust a blank panel.

## You should now have…

An imported sample transcript, a completed Balanced run, and a mental map of Overview’s main blocks.

## Next

- [Make speaker-aware analysis trustworthy](speaker-trust.md)
- [Investigate a question and trace it back to evidence](investigate-evidence.md)
- [Installation](../runtime/installation.md) if you still need a durable install profile
