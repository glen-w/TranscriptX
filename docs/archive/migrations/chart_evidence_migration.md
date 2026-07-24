> **Archived / superseded.** Historical context only. Current authority: [output-contract-v1.md](../../contracts/output-contract-v1.md). Do not treat as live roadmap or support policy.

# Chart evidence sidecar migration

Type: GUIDE
Status: **Done** (primary path)

Chart LLM descriptions ground prompts in **plotted evidence** written beside
chart artifacts (`*.evidence.json`, schema `transcriptx.chart_evidence.v1`).

## Primary path (required for full fidelity)

[`OutputService._save_chart_spec`](../../src/transcriptx/core/output/output_service.py)
writes an evidence sidecar from `ChartSpec` (labels, values, series sample,
filters/transformations when present) and records `evidence_rel` /
`evidence_sha256` on chart `artifacts_meta`. Evidence write failures are logged
but do not fail the chart PNG save. Evidence sidecars themselves are **not**
inventory chart units (`artifact_kind=chart_evidence` / `*.evidence.json` are
skipped when building the logical chart inventory).

## Writers (ChartSpec path)

| Area | Status |
|------|--------|
| Spec-based module charts | Covered via `save_chart(spec=...)` |
| Understandability bars | `BarCategoricalSpec` (grouped series) |
| Topic diagnostic / discourse composites | `PreRenderedFigureSpec` with panel evidence |
| Topic heatmaps / bars / timelines | Native `HeatmapMatrixSpec` / `BarCategoricalSpec` / `LineTimeSeriesSpec` |
| Wordclouds | `PreRenderedFigureSpec` + top-term frequencies |
| Group chart generators under `group_charts/` | ChartSpec through `GroupChartOutputService` |

`PreRenderedFigureSpec` (`chart_intent=pre_rendered`) wraps an already-drawn
matplotlib figure for raster/special charts and multi-panel composites that are
not a single registry intent. Evidence fields (`labels` / `values` / `series`)
still produce `*.evidence.json`; Plotly dynamic rendering is skipped.

## Legacy / residuals

Logical charts **without** a sidecar still enter `chart_set=all` selection.
The generator uses title / registry help only and emits a
`LEGACY_EVIDENCE_FALLBACK` warning. Generic module JSON dumps are **not**
scraped. This remains for historical runs that predate sidecars.

`OutputService.save_chart(..., static_fig=...)` is **deprecated** (emits
`DeprecationWarning`). It remains for tests and emergency escape hatches and
does **not** write evidence. Production writers must use a `ChartSpec`.

Inventory still **reads** either `evidence_rel` or legacy `chart_evidence_rel`
(and may guess a sibling `*.evidence.json` when meta is missing). New writes
use **`evidence_rel` only**.

## Inventory fields

Authoritative logical inventory includes `logical_chart_id`, `source_run` /
member identity, evidence refs, and format **representations**. Description identity
(`chart_key`) does not change when a static or dynamic rendering is added or
removed.

## Done checklist

- [x] New charts via `save_chart(spec=...)` attempt an evidence sidecar
- [x] Chart meta uses `evidence_rel` (+ `evidence_sha256`); no new `chart_evidence_rel` writes
- [x] Wordclouds / topic PreRendered composites populate evidence when data exists
- [x] No production analysis `fig.write_html` chart writers bypassing OutputService
- [x] Focused OutputService + viz + chart_descriptions + topic/wordcloud tests cover the path
