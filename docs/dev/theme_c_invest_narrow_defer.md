# Theme C invest / narrow / defer decision

Status: 1.0 close (Speaker ID Phase 9 + Corrections CCv2 + viewer click-drag); Theme D reader landed separately  
Date: 2026-10-07

## Decision: **Invest** completed for named Theme C workspaces; SPA still deferred

### Evidence

- Phase −1 action service; Speaker ID CCv2-only after Phase 9.
- Corrections CCv2 review pane default-on; generate/apply_export remain Streamlit + service.
- Viewer Correct mode click-drag over `words[]`; find-text when tokens missing.
- Voice confirm/reject routed through `SpeakerIdActionService`.
- `[web]` extra installs `transcriptx-workspaces` from the sibling package path.
- Theme **D** (not Theme C): CCv2 `reader_workspace` full-file karaoke with loopback media route; see [karaoke-playback.md](../runtime/karaoke-playback.md).

### Narrowing

- Do not remove Corrections Studio Streamlit review widgets until a later soak (`TX_CORRECTIONS_WORKSPACE_COMPONENT=0`).
- No manuscript-style rich editor (still out of Theme C / Theme D scope).
- Theme D reader is a separate component; Theme C named workspaces remain Speaker ID / Corrections / viewer_edit.

### Defer / escalate

- Full SPA + Python API remains deferred until written evidence that CCv2 remount/bytes/focus limits block product goals.
