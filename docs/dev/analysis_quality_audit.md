Type: PRODUCT
Authority: self

# Analysis quality audit (1.0)

**Status:** scaffolded (**0.9.5**) — registry rows generated; human judgements open  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) §11  
**Related:** [release_severity_triage_1_0.md](release_severity_triage_1_0.md), [analysis_module_backlog_2026-07-17.md](analysis_module_backlog_2026-07-17.md)  
**Scaffold:** [analysis_quality_audit_scaffold.md](analysis_quality_audit_scaffold.md) (`make docs-gen`)

Living sheet — one row per user-visible analysis. Prefer real corpora over fixtures alone.

**0.9.x freeze:** no new modules unless audit proves a release-critical repair.

## Column template

| Field | Meaning |
|-------|---------|
| Analysis / module | User-visible name + id |
| Intended question | What the user can answer |
| Output type | JSON / chart / text / … |
| Algorithm / model | Method identity |
| Meaningfulness | On real transcripts |
| Languages | Supported / known limits |
| Min data | Minimum segments / speakers |
| Confidence / abstention | How uncertainty is shown |
| Failure modes | Skip / empty / misleading |
| Overlap | Related modules |
| GUI presentation | Where shown; prominence |
| Group semantics | If applicable |
| Test quality | Coverage notes |
| Performance | Cost class |
| **Recommendation** | retain / improve / relabel / hide under Full / deprecate / remove |
| **Severity** | blocker / must-fix / known limitation / post-1.0 |

## Mandatory scrutiny

Deterministic highlights, summaries, and action-item extraction vs LLM equivalents — improve, restrict claims, reduce prominence, or remove misleading fallbacks.

## Rows

Machine-generated registry scaffold (module id, description, category, dependencies, determinism) lives in [analysis_quality_audit_scaffold.md](analysis_quality_audit_scaffold.md). Fill Recommendation / Severity / Notes there during the quality theme; keep this file as the column authority and scrutiny checklist.
