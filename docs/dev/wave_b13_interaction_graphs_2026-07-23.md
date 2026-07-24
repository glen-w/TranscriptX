Type: PRODUCT
Authority: self

# Wave B13 — speaker interaction graphs

Companion to [`analysis_module_backlog_2026-07-17.md`](analysis_module_backlog_2026-07-17.md). Deepen `interactions` (no new module ID).

## Artifacts

| Artifact | Path under run |
|----------|----------------|
| JSON | `interactions/data/global/{base}_interaction_graph.json` |
| GraphML | `interactions/data/global/{base}_interaction_graph.graphml` |
| Chart | `interactions/charts/.../network/network_graph.{png,html}` |
| Evidence | sibling `network_graph.evidence.json` |

Chart identity unchanged: `viz_id=interactions.network_graph.global`.

## JSON schema (`schema_version` = 1)

- `schema_id`: `transcriptx.interactions.interaction_graph.v1`
- `directed`: true
- Node `id`: immutable `grouping_key`; `label`: display name only
- Edge: `source`, `target`, `interruptions`, `responses`, `weight` (= sum, same direction)
- Optional node floats (`floor_share`, `interruption_asymmetry`, `dominance_score`) may be null
- Byte-deterministic: sorted nodes/edges, `sort_keys=True`, `separators=(",", ":")`, `allow_nan=False`, trailing `\n`

## Mapping

- Roles: semantics_version 2 (interrupter/responder → actor; interrupted/addressee → target)
- Self-loops dropped; zero-weight edges omitted; negatives clamped via finite non-negative int
- Empty = no edges after filter → **no** JSON/GraphML/chart/evidence; **delete** prior files on rerun
- GraphML: semantic determinism tested (not raw NetworkX bytes)

## Chart

- Undirected overview: combined weight = sum of both directed weights
- Seeded layout `seed=42` after sorting nodes/edges
- Size from `floor_share` when varied finite values exist; else `degree_total`

## Out of scope

Group-pooled digraph, Speakers-page embed, new viz_id, migrate-on-read of graph files.
