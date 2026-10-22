# Archive a transcript

Hide a managed transcript from dropdowns and default lists without deleting it. It stays on disk and remains findable from Library and Search.

## Outcome

You will have archived the planning-review sample from the Library inspector, confirmed it disappeared from a picker, then found it again with **Include archived transcripts** and unarchived it.

## Starting point

The sample is [imported](../runtime/transcription.md) (see [First analysis](first-analysis.md)). Local AI is not required.

## What you’ll do

1. Open **Library** and select the planning-review transcript.
2. Choose **Archive transcript** in the inspector.
3. Confirm a picker (sidebar or Run Analysis) no longer lists it.
4. On Library (or Search), tick **Include archived transcripts**, select it, and **Unarchive transcript**.

## Walkthrough

1. Open **Library**. Leave **Include archived transcripts** unchecked. Select the planning-review row.

2. In the inspector, choose **Archive transcript**. The table caption reports archived items as hidden. The inspector caption reads **Archived — hidden from dropdowns and default lists.**

3. Open **Run Analysis** (or the sidebar transcript dropdown). The archived item is omitted. Home **Continue** / **Needs attention** also omit it. This is not a Settings toggle.

4. Return to **Library** and tick **Include archived transcripts**. The row reappears with an `(archived)` title suffix. Select it and choose **Unarchive transcript**. Search has the same checkbox (default off) so archived sessions stay findable without cluttering pickers.

Storage rules (sidecar field, what pickers omit, not a delete): [STORAGE.md](../runtime/STORAGE.md#library-archive). Distinct from Speakers profile archive (Settings → Speakers **show archived**) and from `originals/` source-file archive.

## What to notice

- Archive is a visibility flag on the import sidecar, not organisation tags and not Groups.
- Files, sidecars, originals, and analysis runs stay on disk.
- If the sidebar already has an archived transcript selected, that current selection can remain so the session does not blank.
- There is no bulk-archive action.

## You should now have…

Archived and unarchived the planning-review transcript, and seen that pickers hide it until you opt in on Library or Search.

## Next

- [Rename a transcript](rename-transcript.md)
- [Bundle into a group](groups.md)
- [Export results](export-results.md)
