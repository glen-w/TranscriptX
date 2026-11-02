# Evidence / provenance v1 (P2)

**Status:** first adopters only. Not a public schema-epoch bump.

Shared envelope for inferred analysis rows so Insights, Highlights, and
`llm_action_items` do not invent three different evidence shapes.

```json
{
  "schema_id": "transcriptx.evidence_provenance.v1",
  "source_module": "insights",
  "quote_ids": ["q:..."],
  "confidence": "high",
  "abstention": null,
  "spans": []
}
```

| Field | Meaning |
|-------|---------|
| `source_module` | Module id that produced the row |
| `quote_ids` | Existing highlight / stable quote ids (never invented) |
| `confidence` | `high` / `medium` / `low` / `null` |
| `abstention` | Optional `{status, reason}` when the producer abstains |
| `spans` | Optional `{start, end, text?}` dicts |

Python: `transcriptx.core.analysis.provenance.evidence_provenance`.

**Adopters (this wave):** `insights` schema-v3 theme/idea rows, `highlights` theme groups, `llm_action_items` committed records. Full-DAG adoption is later.
