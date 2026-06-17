Type: GUIDE
Authority: group_analysis_module_outputs.md

# Group charts: default overview vs gallery (operator guide)

Short reference for **what shows first** on a group run versus **what exists in the full chart gallery**. This doc stays product-facing; it does not describe internal pipeline architecture.

## Default group overview strip

These charts are listed in `DEFAULT_GROUP_OVERVIEW_VIZ_IDS` in [`chart_registry.py`](../src/transcriptx/core/utils/chart_registry.py). They are the **default strip** for a group run (not the single-transcript overview and not the global transcript list).

Typical contents today:

1. Dialogue acts pie (this chart is also the **pooled** dialogue-act mix for the whole group; see [`group_charts_acts_pooled_contract.md`](group_charts_acts_pooled_contract.md))  
2. Session-level sentiment and stats (`compound_mean`, `total_words`)  
3. Selected temporal overlays (acts, sentiment, pauses, emotion) — same “session-relative minutes” idea  

Exact membership is **code-defined** in `DEFAULT_GROUP_OVERVIEW_VIZ_IDS`; change it there when product wants a different default strip.

## Four group chart modes (product vocabulary)

1. **Session-based** — one bar (or table) per transcript in the group (e.g. words per session).  
2. **Temporal overlay** — multiple sessions on one time axis using **session-relative** minutes (not one wall-clock timeline).  
3. **Cross-session speaker** — same canonical speaker compared **across** sessions (gallery-first; opt-in to the default strip via allowlist).  
4. **Pooled single view** — “if the whole group were **one** conversation,” the closest honest global-style chart (NER types, entity sentiment, topic prevalence, corpus totals, etc.). Most pooled charts are **gallery-only** unless promoted via **`POOLED_GROUP_OVERVIEW_ALLOWLIST`** (today only the acts global pie overlaps the default strip and is allowlisted there).

## Gallery-only (not on the default strip unless you promote them)

Examples operators should expect **only in the gallery** unless you deliberately opt in:

- **Cross-session speaker** families (per-speaker bars across sessions), including stats **word count** and **segment count across sessions**, and sentiment compound cross-session — see chart definitions under `group.*.cross_session_speaker.*`.  
- **Prosody temporal** (`group.prosody.temporal_overlay.global`) — gallery-visible by default, **not** on the default strip.  
- **Pooled** charts whose `viz_id` contains `.pooled.` — default strip uses **`POOLED_GROUP_OVERVIEW_ALLOWLIST`**; leave it minimal unless product wants more pooled tiles up front.

## Where allowlists and overrides live

| What you want to change | Where |
| --- | --- |
| Default **group** overview strip | `DEFAULT_GROUP_OVERVIEW_VIZ_IDS` in [`chart_registry.py`](../src/transcriptx/core/utils/chart_registry.py) |
| Which **temporal** overlays are in that strip (CI sync) | `in_default_group_overview` in [`test_chart_registry.py`](../tests/core/utils/test_chart_registry.py) — must match the temporal family policy you intend |
| Allow a **cross-session speaker** chart onto the default strip | Add its exact `viz_id` to **`CROSS_SESSION_SPEAKER_OVERVIEW_ALLOWLIST`** in `chart_registry.py` **and** add that `viz_id` to `DEFAULT_GROUP_OVERVIEW_VIZ_IDS`; tests require both |
| Allow a **pooled** chart onto the default strip | Add its exact `viz_id` to **`POOLED_GROUP_OVERVIEW_ALLOWLIST`** **and** to `DEFAULT_GROUP_OVERVIEW_VIZ_IDS`; pooled sync tests require both when the chart is on the strip |

## Ordering in the registry

`rank_default` on `group.*` entries in [`chart_definitions.json`](../src/transcriptx/core/utils/chart_definitions.json) affects **gallery ordering** relative to other charts. The default strip order is **not** derived from `rank_default`; it follows `DEFAULT_GROUP_OVERVIEW_VIZ_IDS`.

### `group.*` ordering is intentionally split (context-sensitive)

`group.*` definitions are **deliberately not** kept in one contiguous rank block. The split is by chart **role**, so the gallery surfaces group-level summaries in the order operators expect:

- **Ranks 2–50** — overview-eligible group charts that should appear **first**: the pooled acts pie (default-strip anchor), session-based bars (`compound_mean`, `total_words`), temporal overlays (acts, sentiment, pauses, emotion, prosody), and the cross-session-speaker pattern charts.
- **Ranks 751–760** — **pooled single-view** corpus charts ("if the whole group were one conversation": NER types/top entities, entity sentiment, topic prevalence, mean emotion, tic counts, corpus totals, interruptions, contagion edges). These sit at the **end** of the gallery on purpose, after the per-session/per-speaker single-transcript charts.

This split is **by design**, not an accident of numbering. When adding a new `group.*` chart, place its `rank_default` in the band that matches its role (overview/session/temporal/cross-session → low band; pooled corpus view → 75x band) rather than forcing all `group.*` ranks adjacent.

## Scope semantics (`scope: global` vs per-speaker)

`scope` describes **how artifacts are produced and matched**, not how the chart visually breaks down speakers:

- `scope: "global"` + `cardinality: "single"` can be **one comparison chart that contains every speaker** (e.g. `interactions.dominance.global`, and the `understandability.*` bar charts). These render all speakers inside a single global artifact.
- `scope: "speaker"` (`cardinality: "speaker_set"`) means **one artifact per speaker** (e.g. `emotion.radar.speaker`).

Do **not** change a definition from `global` to `speaker` scope solely because its label reads "Per Speaker" / "All Speakers". The label describes the visual; the scope describes the artifact set. The `understandability.*` charts are global single artifacts that compare all speakers as bars, so they are labelled "(All Speakers)" and keep `scope: "global"`.
