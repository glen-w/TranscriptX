# Chart evidence sidecar migration

Type: GUIDE

Chart LLM descriptions ground prompts in **plotted evidence** written beside
chart artifacts (`*.evidence.json`, schema `transcriptx.chart_evidence.v1`).

## Primary path (required for full fidelity)

[`OutputService._save_chart_spec`](../../src/transcriptx/core/output/output_service.py)
writes an evidence sidecar from `ChartSpec` (labels, values, series sample,
filters/transformations when present) and records `evidence_rel` /
`evidence_sha256` on chart `artifacts_meta`. Evidence sidecars themselves are
**not** inventory chart units (`artifact_kind=chart_evidence` / `*.evidence.json`
are skipped when building the logical chart inventory).

## Legacy fallback

Logical charts **without** a sidecar still enter `chart_set=all` selection.
The generator uses title / registry help only and emits a
`LEGACY_EVIDENCE_FALLBACK` warning. Generic module JSON dumps are **not**
scraped.

## Writers to migrate (prefer ChartSpec → save_chart)

| Area | Notes |
|------|--------|
| Spec-based module charts | Already covered when using `save_chart(spec=...)` |
| Legacy `save_chart` (figs only) | No automatic evidence; migrate to `ChartSpec` or write sidecar manually |
| Group chart generators under `group_charts/` | Prefer emitting ChartSpec through group output service; otherwise add evidence sidecar next to PNG/HTML |
| Wordcloud / special paths | Add explicit evidence payload when values are available |

## Inventory fields

Authoritative logical inventory includes `logical_chart_id`, `source_run` /
member identity, evidence refs, and format **representations**. Description identity
(`chart_key`) does not change when a static or dynamic rendering is added or
removed.
