# Correct wording while reading

Use **Correct mode** in the Transcript viewer to propose (and optionally apply) word/span fixes without leaving the reading surface.

## Outcome

You will have proposed at least one manual correction on the planning-review transcript and know how **Corrections Studio** relates to viewer proposes.

## Starting point

The planning-review transcript is [imported](../runtime/transcription.md) and a run is selected so **Transcript** opens (see [First analysis](first-analysis.md)). Local AI is not required for manual propose.

## What you’ll do

1. Open **Transcript** for the sample.
2. Enable **Correct mode**.
3. Expand **Propose correction** on a segment.
4. Find unique text, enter a replacement, and **Propose**.
5. Optionally open **Corrections Studio** for batch review.

## Walkthrough

1. Select the planning-review transcript (and a run if prompted), then open **Transcript**.

2. Enable **Correct mode**. The viewer shows propose affordances on segments; low ASR-confidence chips (when present) are assists only — you still enter the replacement.

3. Expand **Propose correction** on a segment that contains a clear unique phrase (for this fixture, something like `Northwind Notes` works).

4. Because this sample has no word-timing array, use **Find exact text in segment** with a unique substring, then enter a **Replacement** (for example `Northwind Notes App`). Choose **Propose**.

5. Confirm the pending-manual strip updates (pending count / viewer proposals). The managed original transcript is not overwritten by Propose alone.

6. Use **Accept & apply this** only when you want a scoped corrected sidecar for that candidate. For batch detector/LLM review, open **Corrections Studio** (or **Open Studio** from the propose panel).

Details: [Corrections in the Transcript viewer](../runtime/corrections-viewer.md).

## What to notice

- Propose adds a `manual` / `viewer_manual` candidate; it does not require running detectors first.
- Ambiguous find text is rejected — keep the needle unique within the segment.
- Studio remains the place for detector generations and batch accept/reject; viewer Correct mode is the reading-time path.

## You should now have…

At least one pending manual proposal on the planning-review transcript, plus a mental model of viewer vs Studio.

## Next

- [Identify and name speakers](speaker-identification.md)
- [Investigate a question and trace it back to evidence](investigate-evidence.md)
- [Rename a managed transcript](rename-transcript.md)
