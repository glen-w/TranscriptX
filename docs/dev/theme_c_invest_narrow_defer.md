# Theme C invest / narrow / defer decision

Status: 1.0 close (Speaker ID Phase 9 + Corrections CCv2 + viewer click-drag)  
Date: 2026-10-06

## Decision: **Invest** completed for named workspaces; SPA still deferred

### Evidence

- Phase −1 action service; Speaker ID CCv2-only after Phase 9.
- Corrections CCv2 review pane default-on; generate/apply_export remain Streamlit + service.
- Viewer Correct mode click-drag over `words[]`; find-text when tokens missing.
- Voice confirm/reject routed through `SpeakerIdActionService`.
- `[web]` extra installs `transcriptx-workspaces` from the sibling package path.

### Narrowing

- Do not remove Corrections Studio Streamlit review widgets until a later soak (`TX_CORRECTIONS_WORKSPACE_COMPONENT=0`).
- No manuscript-style rich editor; no CCv2 karaoke reader (Theme D).

### Defer / escalate

- Full SPA + Python API remains deferred until written evidence that CCv2 remount/bytes/focus limits block product goals.
