# Theme C — High-interaction workspaces (Components v2)

Type: DEVELOPER  
Authority: self  
Status: active (1.x)  
Last updated: 2026-08-10

**Roadmap home:** [docs/ROADMAP.md](../ROADMAP.md) §C  
**Product constraint:** Streamlit shell + Python domain; specialised CCv2 workspaces only.

## Goal

Escape Streamlit’s rerun model for workstation pages (Speaker ID → Corrections → later rich edit) without abandoning Streamlit for the analysis workbench.

## Locked decisions

1. Shared `SpeakerIdActionService` owns mutations for **legacy and CCv2** (Phase −1 shipped).
2. Three state tiers: browser-local ephemeral · sparse Streamlit `setStateValue` · revisioned domain triggers. **Never** stream `current_time_ms` via `setStateValue`.
3. Every domain trigger is a revisioned command envelope; acks carry authoritative revisions.
4. Optimistic reconciliation: one mutating speaker action in flight; nav may be optimistic; ignore stale/out-of-order acks by `action_seq`; duplicate `action_id` never writes twice; protocol/build mismatch fails closed.
5. Python CCv2 `key=` is **transcript-scoped** (`speaker_id_ws:{transcript_id}`), not global.
6. ClipTransport **T0 = measured base64** in JSON `data`. Binary only via a separate tested conduit (T1); no undocumented Streamlit media URLs.
7. CCv2 bridge uses **only** non-blocking ClipService APIs (`cached_clip_status` / `get_cached_clip_bytes` / `enqueue_clip`). Never cold `get_clip_path` / `get_clip_bytes`.
8. Packaged CCv2 from Streamlit `component-template` v2 layout: component-level `[[tool.streamlit.component.components]]`, assets in wheel/sdist.
9. Dist policy: **commit built `frontend/build` assets** into the workspaces package (reproducible installs without Node at runtime). CI rebuilds and fails on drift. Lockfile + Node engines pinned.
10. Shadow DOM = style isolation only. Render text via `textContent`. `asset_dir` is public.
11. Feature flag default **off** until Phase 5 browser suite green on Streamlit **min (`>=1.55`) + current pin**. Legacy retired only in Phase 9.

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

### Phase 5 (before default-on)

- Browser suite green on Streamlit min + current
- Rerun counts per common journey within documented budgets
- Payload/Blob memory within budgets
- Zero duplicate mutations under replayed `action_id`

## Feature flags

| Flag | Default | Meaning |
|------|---------|---------|
| `speaker_id_workspace_component` | **`true`** (Phase 5) | CCv2 Speaker ID workspace |
| `corrections_workspace_component` | `false` | CCv2 Corrections |

Env override: `TX_SPEAKER_ID_WORKSPACE_COMPONENT=0` forces legacy rollback.

## Frontend toolchain

- Node `>=20 <23` (CI uses 22.x)
- npm lockfile committed
- `@streamlit/component-v2-lib` pinned in workspaces package
- Vite, `base: "./"`, hashed `index-*.js` / `index-*.css`

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
- **T3:** documented local route — escalation only

## Invest / narrow / defer (after Phase 3)

Written decision required before Corrections expansion or SPA rewrite. Escalate to local frontend + Python API only with evidence that CCv2 remount/bytes/focus limits block product goals.

## Phase 9 legacy retirement

Remove legacy fragment contracts **only when all** are true:

1. Shared `SpeakerIdActionService` means both paths have identical domain semantics (enforced by tests) — **done**
2. Rollback / flag-off path has survived the stated release window after default-on
3. Browser acceptance suite remains green in CI (Streamlit min + current)
4. Explicit changelog + known-limitations update

Until then: keep “single `@st.fragment` on Speaker ID” and flag-off characterisation contracts. **Do not remove legacy merely because CCv2 is default-on.**

## Related code

- `src/transcriptx/app/speaker_id/` — action service
- `packages/transcriptx_workspaces/` — CCv2 package
- `src/transcriptx/web/workspaces/` — Streamlit adapters / flags
- `src/transcriptx/services/speaker_studio/clip_service.py` — non-blocking APIs
