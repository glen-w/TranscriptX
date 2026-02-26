# Issue Summary: No Analysis Modules Available (Speaker Map / Database)

## Symptom

When running **Analyze → Files → Explore file system** and selecting multiple transcript files (e.g. 11–13), then choosing:

- **"All eligible modules"** → **"No analysis modules selected. Returning to main menu."**
- **"Choose modules manually"** → Every module is disabled (greyed out) with reasons like "needs 1+ named speakers" or "needs 2+ named speakers".

So it appears as if **no analysis modules are available at all** for the selected transcripts.

---

## Root Cause

Module availability is gated on **named speaker count**:

1. For each selected transcript file, the CLI computes a **named speaker count** (how many distinct speakers have “real” names, not placeholders like `SPEAKER_01` or `Speaker 1`).
2. The **effective** count used for eligibility is the **minimum** of these per-file counts across all selected files.
3. If that minimum is **0**, then:
   - Every module that requires “1+ named speakers” or “2+ named speakers” is filtered out.
   - So “Recommended” and “All eligible” return an empty list, and in “Choose modules manually” every module is disabled.

So the issue is: **the effective named speaker count is 0** for the current selection.

---

## Why the Count Can Be Zero

Named speaker count is derived only from **the transcript JSON file** (and optionally its in-file `speaker_map`). It is **not** derived from the database.

### How the count is computed (current behavior)

- **Segments** are loaded with `load_segments(path)` from `src/transcriptx/io/transcript_loader.py` (file-only).
- A **speaker_map** is read from the same file via `extract_speaker_map_from_transcript(path)` (top-level `"speaker_map"` key in the JSON).
- For each segment, if `segment["speaker"]` is a key in that map (e.g. `SPEAKER_01`), it is treated as the mapped name (e.g. `"Rana"`) when counting.
- “Named” means: the name passes `is_named_speaker()` (real-name style); placeholders like `SPEAKER_01`, `Speaker 1`, `Unknown` do **not** count.

So the count is 0 when, for **at least one** of the selected files:

- The transcript has **no** top-level **`speaker_map`** in the JSON, **or**
- Segments only have **`speaker`** (or speaker from `words[]`) set to IDs like **`SPEAKER_00`** / **`SPEAKER_01`**, and either:
  - There is no **`speaker_map`** in the file to resolve them, or
  - The logic that applies **`speaker_map`** is not used for that path (see below).

### Fix already implemented (file-only)

In **`src/transcriptx/cli/analysis_utils.py`**:

- **`_named_speaker_count_for_path(path)`** now:
  - Loads segments from the file.
  - Reads **`speaker_map`** from the same file.
  - Builds a copy of segments and replaces `segment["speaker"]` with **`speaker_map[speaker]`** when the key exists.
  - Returns **`count_named_speakers(resolved_segments)`**.

So **if** the transcript JSON contains a **`speaker_map`** and segments use **`SPEAKER_XX`** (or similar) in **`speaker`**, the count should now be correct for that file.

If the count is **still** 0 after this fix, then for at least one selected file:

- The JSON has **no** **`speaker_map`**, **or**
- Segments never got **`speaker`** (or only got it from **`words[]`**) and the file was never updated with a **`speaker_map`**.

---

## Database vs File: Why Some Transcripts Have “No” Speaker Map

Speaker identity can be stored in two places:

1. **Transcript JSON file**  
   - Top-level **`speaker_map"`** (e.g. `{"SPEAKER_01": "Rana"}`).  
   - Segment-level **`speaker"`** (human name) and optionally **`speaker_db_id"`**.

2. **Database**  
   - **Speaker**, **TranscriptSpeaker**, **TranscriptSegment**, etc.  
   - **TranscriptDbAdapter.load_segments_by_path()** returns segments with **`speaker`** = display name from the DB.

The **module availability** logic uses only:

- **`load_segments(path)`** (file).
- **`extract_speaker_map_from_transcript(path)`** (file).

It does **not** use:

- **TranscriptService.load_segments(path, use_db=True)**.
- Any DB-backed speaker resolution.

So:

- If speaker identification was done **only in the database** (e.g. ingestion, **SegmentStorageService**, identity resolution) and the transcript JSON was **never** updated with **`speaker_map`** and segment **`speaker`** names, then the **file** has no speaker map from the CLI’s point of view.
- Even if the DB has correct speaker names for that transcript, the CLI does not query the DB for the “named speaker count” check, so the effective count stays 0.

Relevant code:

- **File-only loading:** `src/transcriptx/io/transcript_loader.py` (`load_segments`, `extract_speaker_map_from_transcript`).
- **DB-backed loading (not used for this check):** `src/transcriptx/io/transcript_service.py` (`load_segments(..., use_db=True)`), `src/transcriptx/database/transcript_adapter.py` (`load_segments_by_path`).
- **Writing speaker map to file:** `src/transcriptx/io/speaker_mapping/core.py` (`update_transcript_json_with_speaker_names`); called when speaker identification is run via **build_speaker_map** with a **transcript_path** (e.g. interactive CLI flow).

So the situation “we have speaker maps in the DB but not in the file” is consistent with the observed behaviour.

---

## Summary Table

| Question | Answer |
|----------|--------|
| Why does “All eligible” / manual selection show no modules? | Effective named speaker count is 0 → all modules are filtered out or disabled. |
| Where does the count come from? | Only from the **transcript JSON file** (segments + optional in-file **`speaker_map`**). |
| Does the count use the database? | **No.** Only file-based loading is used for module availability. |
| Why might the file have no speaker map? | Speaker mapping may have been done only in the DB, or the JSON was never updated after mapping. |
| What was fixed already? | In-file **`speaker_map`** is now applied when counting (so files that have **`speaker_map`** but **SPEAKER_XX** in segments are counted correctly). |
| When would the issue still occur? | When the transcript JSON has **no** **`speaker_map`** (and no human names in **`segment["speaker"]`**) for at least one selected file. |

---

## Possible Next Steps (for consideration)

1. **Verify files**  
   For a selection that still shows “no modules”, inspect one or two transcript JSONs:  
   - Is there a top-level **`speaker_map`**?  
   - Do segments have **`speaker`** set to human names or only to **SPEAKER_XX**?

2. **Ensure file is updated when mapping is done**  
   Ensure that any flow that performs speaker identification (including DB-backed or batch) also calls **update_transcript_json_with_speaker_names** (or equivalent) so the transcript JSON always gets **`speaker_map`** and segment **`speaker`** updated.

3. **Optional DB fallback for module availability**  
   When computing named speaker count for the CLI:  
   - If the file has no **`speaker_map`** (or the file-based count is 0), optionally try **TranscriptService.load_segments(path, use_db=True)** and compute the named speaker count from the returned segments (which already have **`speaker`** = display name from the DB).  
   - This would require the CLI to use the transcript service and to handle “DB not configured” or “transcript not in DB” without breaking the file-only path.

4. **Documentation**  
   Document that for “All eligible” and manual module selection to show modules, transcripts must have at least one “named” speaker per file (either via in-file **`speaker_map`** + **SPEAKER_XX** in segments, or via segment **`speaker`** already set to human names), and that running speaker identification from the CLI (so that **update_transcript_json_with_speaker_names** runs) is one way to achieve that.

---

## References (code locations)

- Module availability and named speaker count: **`src/transcriptx/cli/analysis_utils.py`**  
  - `_named_speaker_count_for_path`, `select_analysis_modules`, `resolve_modules_for_selection_kind`
- Segment loading (file): **`src/transcriptx/io/transcript_loader.py`**  
  - `load_segments`, `extract_speaker_map_from_transcript`
- Segment loading (with optional DB): **`src/transcriptx/io/transcript_service.py`**  
  - `load_segments(..., use_db=True)`, `_load_segments_from_db`
- DB segment payload (includes speaker display name): **`src/transcriptx/database/transcript_adapter.py`**  
  - `load_segments_by_path`, `load_segments_by_file_id`
- Writing speaker map into transcript JSON: **`src/transcriptx/io/speaker_mapping/core.py`**  
  - `update_transcript_json_with_speaker_names`, `build_speaker_map`
- “Named” speaker predicate: **`src/transcriptx/utils/text_utils.py`**  
  - `is_named_speaker`
- Filtering modules by speaker count: **`src/transcriptx/core/analysis/selection.py`**  
  - `filter_modules_for_speaker_count`
