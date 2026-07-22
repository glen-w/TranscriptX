Type: CONTRACT
Authority: self

# Topic-shift (`topic_shift`) contracts — Wave 1

Schema: `topic_shift_result_schema_v1`. Semantics per backend: see `SEMANTICS_BY_BACKEND` in `src/transcriptx/core/analysis/topic_shift/semantics.py`.

## Analytical vs pipeline status

- Pipeline / `run_results`: module `error` → consumer **`failed`**.
- Committed `analytical_status`: `success` | `no_shift_detected` | `insufficient_content` | `unsupported_language` | `backend_unavailable` | `invalid_input`.
- Never commit `analytical_status=error`; failed writes leave generation inactive.

## Artifacts (versioned envelopes)

| File | Contents |
|------|----------|
| `topic_shift.spans.json` | coverage spans + identity + generation id |
| `topic_shift.events.json` | envelope + Event list (unwrap via `load_topic_shift_events`) |
| `topic_shift.stats.json` | deterministic metrics (no volatile cache/device/timing) |

Boundary strength lives on **events** (`evidence`): `raw_distance`, `local_prominence`, `decision_threshold`, `normalized_strength` (backend-local). Spans carry nullable `leading_boundary_id` and `viewer_target_source_index`.

## ACTIVE

Intra-run generation under `.topic_shift_generations/`. Failed attempt does not replace `current_complete_generation`. Viewer/availability must consult `run_results` for the current execution (`resolve_topic_shift_visibility`).

## Chunking

Overlapping chunks with fixed `window_size`/`stride`; global peak reconcile prefers higher `local_prominence`; coverage map must be complete.

## Dual ACTIVE matrix

| Deterministic ACTIVE | Enrichment ACTIVE | Viewer / exports |
|----------------------|-------------------|------------------|
| yes (succeeded / abstaining) | yes (success/partial) | Chapters + LLM titles/summaries |
| yes | skipped / failed / absent | Chapters with deterministic labels only |
| failed execution (`run_results`) | any | **Suppress** chapters, artifacts, charts, exports |
| incomplete generation (no COMMIT) | any | Invisible (no ACTIVE) |

Failed enrichment never invalidates deterministic ACTIVE. Deterministic spans/events/stats stay **byte-identical** with LLM on or off.

## LLM enrichment

Optional sidecar under `.topic_shift_enrichment/` (shared `llm_generational_store`; empty digests rejected). Boundaries immutable. Resolve `consumer_id=topic_shift` without `DEFAULT_OLLAMA_MODEL` fallthrough; configured model must be **installed** or enrichment is `skipped`. `no_shift_detected` enrichment UI uses **overall summary**, not chapter title. Transcript downloads expose chapters (+ optional enrichment) when visibility is `show`.

## Viewer

Chapters tab in Transcript viewer (`_transcript_interaction_fragment`). Jump/Play uses pending chapter action so playback is re-applied after view-signature reset.

## Group

Dedicated aggregation by provenance cohort; `shifts_per_hour` with min valid duration; session bars + temporal marker overlay (unwrap-aware events).
