Type: CONTRACT
Authority: self

# Acts group charts: pooled single view (audited)

## Existing charts

`ActsGroupChartGenerator` already emits **corpus-level** dialogue-act distributions via `generate_acts_charts` with `group_aggregate_viz_ids=True`, notably:

- `group.acts.global_acts_pie.global`
- `group.acts.global_acts_bar.global` (when emitted)

Counts come from **`reconstruct_act_counters`**: act-type columns summed across all `session_rows` (and speaker rows merged by canonical id). That is semantically **pooled**: the full group as one summed conversation.

## Family

`pooled_single_view` is listed for `acts` to document this behavior. **No duplicate** pooled-only chart is added.

## Not

- Temporal overlay remains a separate family (session-relative timelines).
