# Relational pooling model (group charts)

Normative reference for **speaker-pooled** vs **edge-pooled** relational modules and for `interactions_pooled` / `contagion_pooled`. Module contracts (`group_charts_interactions_pooled_contract.md`, `group_charts_contagion_pooled_contract.md`) must stay aligned with this document.

## A. Pooling classes

| Class | Meaning | Example |
| ----- | ------- | ------- |
| **Speaker-pooled relational analogue** | Pool **per canonical speaker** where the source metric is **speaker-role-based** (e.g. initiated/received counts per speaker). | **interactions** |
| **Edge-pooled relational analogue** | Pool **per canonical directed pair** where the source metric is **dyadic** (from→to). | **contagion** |

Do not apply the wrong template to a new module.

## B. Metric types

- **Additive counts:** Pool by **sum** when the group analogue is the **total count of observed events** in the corpus (identity contract satisfied).
- **Rates, ratios, scores:** Require an explicit **denominator / exposure** model in the contract, or **exclude** from `pooled_single_view` until specified.
- **Session-topology artifacts** (turn indices, per-session matrices): Not pooled for group single view unless separately modeled.

## C. Identity contract

- **Speaker-pooled:** Canonical speaker id is authoritative; mapping uses `_build_display_to_canonical` and `_fallback_canonical_id` in `aggregation/rows.py` per the row-mapping contract.
- **Directed edges:** Identity is **`(from_canonical_id, to_canonical_id)`**; direction is preserved.
- **`From->To` string keys (contagion):** Parse to two non-empty display endpoints (single `->` split). **Invalid formats:** drop the edge and emit a **structured consistency warning** (`RELATIONAL_POOL_PARSE`); **no heuristic repair**.
- **Self-edges (v1, fixed):** After canonicalization, if `from_canonical_id == to_canonical_id`, the edge is **invalid**, **dropped**, with a **consistency warning** (`RELATIONAL_POOL_SELF_EDGE`).

## D. Warning / drop policy (global)

- Use documented mapping only (including fallback canonical id **only** where the row contract allows).
- If identity cannot be satisfied: **drop** the row or edge + **consistency warning**.
- **Never merge on raw display labels** in pooled payloads; merge keys are always canonical ids.

## Display surfaces (edge-pooled)

For each endpoint, `from_display` / `to_display` in `contagion_pooled`:

1. Use **`canonical_speaker_map.canonical_to_display`** when present for that canonical id.
2. Otherwise use the **lexicographically smallest** display string observed for that canonical id during the aggregation merge, in **`per_transcript_results` iteration order** (same inputs and stable ordering ⇒ same labels on rerun).
3. Display strings are **never** merge keys.

## Empty pooled payloads

A **structurally valid** pooled object with **no chartable content** (e.g. `edges: []` after merge, or all speaker counts zero) yields **no pooled chart** and a clear **skip** path—**not** a placeholder chart that could be read as a claim about relations.

## Dominance (interactions)

**v1:** `interactions_pooled` includes **additive role counts only** (`interruptions_*`, `responses_*`). **`dominance_score` is not included** in `interactions_pooled` until a denominator-backed group definition is specified and implemented.

Directional pooling of those additive counts (and dominance-derived `speaker_rows`) requires every included run to use current interactions `semantics_version` (see [`group_charts_interactions_equity_contract.md`](group_charts_interactions_equity_contract.md)). Mixed or legacy versions skip directional pool with one structured warning; session rows remain.

## `speaker_rows` vs `interactions_pooled`

- **`speaker_rows`** remain for **CSV / row writers** and existing consumers.
- **`interactions_pooled`** is the **authoritative chart contract** for pooled interaction charts: versioned schema, independent evolution; charts **must not** read `speaker_rows` for pooled views.

## Contagion roster semantics

**Event-count pooling:** Summing observed directed events across sessions is valid as an **aggregate of observed events** under changing rosters; it is **not** evidence of **equal opportunity for interaction** across pairs. **Pooled contagion v1** is a pooled **counts** view of observed directed transfer events, **not** a normalized social-network comparison.

## Contagion `contagion_pooled` schema (authoritative)

- **`schema_version`:** `1`
- **`edges`:** list of objects, **one per directed canonical pair** after merge:
  - `from_canonical_id`, `to_canonical_id` (int)
  - `from_display`, `to_display` (str, per display rules above)
  - `emotions`: map `emotion_label -> count` (non-negative integers)
  - `total`: optional int, sum of `emotions` for convenience

Flattened `(from, to, emotion)` rows are for writers only if ever needed, not the chart contract.
