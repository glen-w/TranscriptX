# Theme C — High-interaction workspaces (Components v2)

Status: 1.0 named workspaces landed (Speaker ID Phase 9, Studio review, viewer click-drag)  
Last updated: 2026-10-07

**Roadmap home:** [docs/ROADMAP.md](../ROADMAP.md) §C  
**Product constraint:** Streamlit shell + Python domain; specialised CCv2 workspaces only. Theme D full-file reader shares the package but is owned by [ROADMAP §D](../ROADMAP.md) / [karaoke-playback.md](../runtime/karaoke-playback.md).

## Goal

Escape Streamlit’s rerun model for workstation pages (Speaker ID, Corrections review, per-segment word selection) without abandoning Streamlit for the analysis workbench. Manuscript-style rich edit stays out of this theme. Theme D full-file reader is a separate CCv2 component (`reader_workspace`); see [karaoke-playback.md](../runtime/karaoke-playback.md).

## Locked decisions

1. Shared `SpeakerIdActionService` owns Speaker ID mutations (Phase −1). After Phase 9 the naming/playback surface is CCv2-only.
2. Three state tiers: browser-local ephemeral · sparse Streamlit `setStateValue` · revisioned domain triggers. **Never** stream `current_time_ms` via `setStateValue`.
3. Every domain trigger is a revisioned command envelope; acks carry authoritative revisions.
4. Optimistic reconciliation: one mutating speaker action in flight; nav may be optimistic; ignore stale/out-of-order acks by `action_seq`; duplicate `action_id` never writes twice; protocol/build mismatch fails closed.
5. Python CCv2 `key=` is **transcript-scoped** (`speaker_id_ws:{transcript_id}`), not global.
6. ClipTransport **T0 = measured base64** in JSON `data`. Binary only via a separate tested conduit (T1); no undocumented Streamlit media URLs.
7. CCv2 bridge uses **only** non-blocking ClipService APIs (`cached_clip_status` / `get_cached_clip_bytes` / `enqueue_clip`). Never cold `get_clip_path` / `get_clip_bytes`.
8. Packaged CCv2 from Streamlit `component-template` v2 layout: component-level `[[tool.streamlit.component.components]]`, assets in wheel/sdist.
9. Dist policy: **commit built `frontend/build` assets** into the workspaces package (reproducible installs without Node at runtime). CI rebuilds and fails on drift. Lockfile + Node engines pinned.
10. Shadow DOM = style isolation only. Render text via `textContent`. `asset_dir` is public.
11. Feature flag for **Corrections** default **on**. Rollback with `TX_CORRECTIONS_WORKSPACE_COMPONENT=0`. Speaker ID CCv2 is required (Phase 9); missing `transcriptx-workspaces` is an install error, not a classic-UI fallback.

## Protocol

See `transcriptx.app.speaker_id.protocol` and `transcriptx_workspaces` protocol modules.

| Field | Role |
|-------|------|
| `protocol_version` | Fail closed on mismatch (`1`) |
| `frontend_build_id` | Fail closed → reload/fallback |
| `action_id` | Idempotency |
| `action_seq` | Monotonic; ignore out-of-order acks |
| `transcript_id` / `transcript_revision` | Workspace identity |
| `expected_speaker_id` / `expected_mapping_revision` | Stale reject |
| `audio_fingerprint` | When clip-relevant |

## Prefetch / memory budgets

| Budget | Default |
|--------|---------|
| Max clips per warm request | 8 |
| Max bytes per clip into browser | 1_500_000 |
| Max total Blob memory / workspace | 8_000_000 |
| Max concurrent miss retries | 2 |
| Retry count | 4 |
| Backoff | 200ms × 2^n (cap 3s) |
| Global ClipService inflight | existing `_MAX_INFLIGHT` (8) |

Revoke Blob URLs on replacement, transcript switch, and unmount.

## Quantitative gates

### Phase 0

- Zero `<audio>` element replacement on metadata-only `data` refresh (element identity)
- Cleanup revokes Blob URLs / clears timers
- Dist policy locked (this doc § Locked #9)

### Phase 2

- Zero audio replacement on mapping/metadata refresh for same transcript key
- Bridge handlers return pending without joining cold ffmpeg (no multi-second block)
- Prefetch budgets held; multi-session backpressure respected
- Record p50/p95 trigger→ack for nav/warm in CI artefacts when measured

### Phase 5 (default-on, historical)

- Browser harness green (audio identity, transcript switch, keyboard suppression)
- Docker/web images install `transcriptx-workspaces` wheel
- Corrections flag defaults **on**; env rollback retained for one release after 1.0
- Speaker ID missing-package fallback to classic widgets **removed in Phase 9** (install error instead)
- Zero duplicate mutations under replayed `action_id`

## Feature flags

| Flag | Default | Meaning |
|------|---------|---------|
| `corrections_workspace_component` | **`true`**; rollback with env `0`/`false`/`off` | CCv2 Corrections review pane |

Env rollback: `TX_CORRECTIONS_WORKSPACE_COMPONENT=0`. Theme D reader flag (`TX_READER_WORKSPACE_COMPONENT`) is documented in [karaoke-playback.md](../runtime/karaoke-playback.md), not Theme C.

## Frontend toolchain

- Node `>=20 <23` (CI uses 22.x)
- npm lockfile committed
- `@streamlit/component-v2-lib` pinned in workspaces package
- Vite, `base: "./"`, hashed `speaker_id-*.js` / `corrections-*.js` / `viewer_edit-*.js` / `reader-*.js` (Theme D) plus named CSS

## Keyboard map (Phase 3)

Active only when workspace focused; suppressed in inputs/contenteditable.

| Key | Action |
|-----|--------|
| `j` / `ArrowDown` | Next speaker |
| `k` / `ArrowUp` | Prev speaker |
| `Space` | Play/pause |
| `Enter` | Save name |
| `i` | Ignore toggle |
| `?` | Help |

Avoid browser/AT reserved chords.

## ClipTransport

- **T0:** base64 (or data-URL string) inside JSON metadata `data`
- **T1:** only if measured need — dedicated binary conduit component whose entire `data=` is bytes, correlated by `clip_id` + revision in the metadata component; tested on min + current Streamlit
- **T2:** browser `Map<clipId, BlobURL>` under budgets
- **T3:** documented local route — Theme D `reader_workspace` uses loopback Range media (`src/transcriptx/web/media_route.py`); Speaker ID stays on T0

## Invest / narrow / defer (after Phase 3)

Corrections CCv2 review and viewer click-drag landed for 1.0. SPA rewrite still needs written remount/bytes/focus evidence. Escalate to a custom local frontend only with evidence that CCv2 remount/bytes/focus limits block product goals.

**First escalation (if the gate fires):** loopback application API over existing `app.controllers` / workflows, with Streamlit remaining the only client until that API is stable — then grow workspaces off Streamlit hosting. Do **not** jump to Gradio/NiceGUI or an OS-native workbench rewrite. Full Streamlit retirement is a late 1.x / 2.0 programme (theme **I**), not a Theme C deliverable. Roadmap: [ROADMAP.md](../ROADMAP.md) §C (shell review) and §I.

## Phase 9 legacy retirement

**Done for 1.0** (2026-10-06). Soak evidence: CI `workspaces-theme-c`, GUI E2E, and Docker wheel install since default-on (2026-08-11). Native `[web]` now installs the package. Classic Speaker ID naming/playback widgets are removed. Missing package → install error.

Previous criteria (all true):

1. Shared `SpeakerIdActionService` means both paths have identical domain semantics (enforced by tests) — **done**
2. Rollback / flag-off path survived the stated release window after default-on — **waived in favour of CI/E2E/Docker soak; native extra now required**
3. Browser acceptance suite remains green in CI (Streamlit min + current)
4. Explicit changelog + known-limitations update

## Related code

- `src/transcriptx/app/speaker_id/` — Speaker ID action service (`voice_confirm` / `voice_reject` included)
- `src/transcriptx/app/corrections/` — Studio review / export action service
- `packages/transcriptx_workspaces/` — named CCv2 entries (`speaker_id`, `corrections`, `viewer_edit`, Theme D `reader`)
- `src/transcriptx/web/workspaces/` — Streamlit adapters / Corrections + reader flags
- `src/transcriptx/web/page_modules/speaker_id.py` — CCv2-only naming/playback
- `src/transcriptx/web/page_modules/corrections_studio.py` — CCv2 review + Streamlit generate/export
- `src/transcriptx/web/transcript_viewer/corrections_panel.py` — click-drag host when `words[]` exist
- `src/transcriptx/web/page_modules/transcript.py` / `workspaces/reader_bridge.py` / `media_route.py` — Theme D reader
- `src/transcriptx/services/speaker_studio/clip_service.py` — non-blocking APIs (Speaker ID / clip rollback)
