Type: GUIDE
Authority: docs/PRODUCT.md

# Make speaker-aware analysis trustworthy

Inspect and improve speaker identity before you lean on speaker-level analysis.

## Outcome

You will have named (or deliberately ignored) the diarized speakers on the sample transcript and confirmed the labels on **Transcript**.

## Starting point

The sample [planning_review.json](fixtures/planning_review.json) is imported (see [First analysis](first-analysis.md)). Speakers still show as `SPEAKER_00`, `SPEAKER_01`, and `SPEAKER_02`.

Audio is optional for this workflow; sample text lines are enough.

## What you’ll do

1. Open **Speaker Identification** for the sample transcript.
2. Review sample lines for each diarized speaker.
3. Assign clear names (and ignore any junk label if present).
4. Confirm the names on **Transcript**.
5. Understand why this matters for later speaker results.

## Walkthrough

1. From **Library** or the post-import actions, open **Speaker Identification**. Select the planning-review transcript if it is not already selected.

```{image} /_static/workflows/speaker-trust-page.png
:alt: Speaker Identification page showing sample lines for the active diarized speaker
:width: 720px
```

2. Read the sample lines for the first speaker. Decide who that person is from the dialogue (in this fixture: facilitator / product, engineering, and support roles).

3. Enter a display name and choose **Save name** (or **Assign name**, depending on the control shown). Move on with **Next →**.

```{image} /_static/workflows/speaker-trust-naming.gif
:alt: Naming one speaker and advancing to the next candidate in Speaker Identification
:width: 720px
```

4. Repeat for the remaining speakers. Suggested names for this fixture: **Maya** (`SPEAKER_00`), **Jordan** (`SPEAKER_01`), **Sam** (`SPEAKER_02`). Use any stable names you prefer; consistency matters more than the exact strings.

5. If a diarized ID is clearly noise (rare in this short fixture), choose **Ignore** so it does not pollute speaker summaries. You can **Unignore** later if needed.

6. Open **Transcript** and confirm turns now show your chosen names instead of `SPEAKER_00`-style IDs.

```{image} /_static/workflows/speaker-trust-transcript.png
:alt: Transcript viewer showing named speakers after Speaker Identification
:width: 720px
```

7. Re-run or refresh analysis views that depend on named speakers when you care about per-speaker summaries. A prior run may still reflect old labels until modules that key on speaker identity are run again.

> **Note:** Speaker Identification uses the Components v2 workspace by default
> when `transcriptx-workspaces` is installed. Roll back to the classic UI with
> `TX_SPEAKER_ID_WORKSPACE_COMPONENT=0`. Naming controls for this walkthrough
> remain the same either way. See [known limitations](../known_limitations.md).

## What to notice

- Speaker identity is part of analysis trust, not a cosmetic rename.
- **Ignore** is for unusable diarization IDs; prefer naming real participants.
- Longitudinal profile linking (when offered) is optional; naming alone is enough for single-transcript work.
- Downstream speaker cards, per-speaker LLM summaries, and interaction-style views are only as good as these labels.

## You should now have…

A multi-speaker transcript with stable human-readable names confirmed in the transcript viewer.

## Next

- [Investigate a question and trace it back to evidence](investigate-evidence.md)
- [First analysis](first-analysis.md) if you still need a Balanced run after renaming
- [Known limitations](../known_limitations.md) for diarization and naming caveats
