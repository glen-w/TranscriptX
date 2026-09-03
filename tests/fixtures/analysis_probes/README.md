# Analysis probe transcripts

Reusable transcripts for maintainer analysis probes (deep-test small/large runs). They are **not** the user library.

| File | Role |
|------|------|
| [`../mini_transcript.json`](../mini_transcript.json) | Default **small** probe |
| `large_norm.json` (+ `large_norm.speaker_map.json`) | Default **large** multi-speaker probe |
| `demo__interview.json`, `demo__meeting_decisions.json`, `demo__multispeaker.json` | Tiny synthetic samples (former bundled demo pack) |

## Rules

- Analyse these paths **in place**. Do not import or copy them into `TRANSCRIPTX_TRANSCRIPTS_DIR` / `HOST_TRANSCRIPTS_DIR`.
- Pipeline admission is fail-closed for unmanaged files. Probe runs must set `TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS=1`.
- Docker: mount this tree at `/mnt/fixtures` (see `.cursor/commands/deep-test.md`). The user transcripts mount stays the library.
