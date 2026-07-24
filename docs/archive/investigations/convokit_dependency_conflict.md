Type: ARCHIVE
Authority: historical

> **Archived / superseded.** Historical context only. Current authority: [dependency_audit.md](../../dev/dependency_audit.md). Do not treat as live roadmap or support policy.

# ConvoKit dependency conflict (historical)

> Archived note only. Live policy: post-1.0 optional citeable research methods (B4) in [`docs/ROADMAP.md`](../ROADMAP.md) and [`docs/dev/analysis_module_backlog_2026-07-17.md`](../dev/analysis_module_backlog_2026-07-17.md). ConvoKit is **not** on the TranscriptX 1.0 critical path.

ConvoKit coordination/accommodation analysis was previously archived from the product stack due to **dependency conflicts**.

**Dependency issues (as recorded when archived):** convokit 3.5.0 required `numpy>=2.0.0`, `spacy>=3.8.2`, and `thinc>=8.3.0,<8.4.0`. Those conflicted with project pins used by NER and other modules (e.g. numpy 1.26.4, spacy 3.7.5, thinc 8.2.5 at the time of the note).

**Superseded revive sketch (do not treat as live plan):** resolve convokit/numpy/spacy/thinc versions, then re-implement under `src/transcriptx/core/analysis/convokit/` and re-wire the pipeline module registry, analysis config, and aggregation registry.

**Current post-1.0 direction (supersedes the sketch above):** method-named modules (`fighting_words`, etc.), shared canonical adapter, isolated subprocess/sidecar — not an in-process `[convokit]` extra unless explicitly revisited; not “ConvoKit enabled” as the product goal.
