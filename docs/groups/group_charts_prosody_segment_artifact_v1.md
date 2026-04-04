Type: CONTRACT
Authority: self

# Contract: prosody overlay segment artifact (v1)

**Machine artifact** consumed by `group.prosody.temporal_overlay.global` after Phase 13B. Written by `prosody_dashboard` when voice features are available.

## Path (deterministic)

```
{output_dir}/prosody_dashboard/data/global/{base_name}_prosody_overlay_segments.v1.json
```

`base_name` = `get_canonical_base_name(transcript_path)` for the member run (matches [`OutputService.base_name`](src/transcriptx/core/output/output_service.py)).

## Versioning

- Filename suffix `.v1.json` and top-level `"schema_version": 1`.

## JSON shape

```json
{
  "schema_version": 1,
  "y_field": "rms_db",
  "segments": [
    { "start": 0.0, "rms_db": -23.5 }
  ]
}
```

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | `1` | Layout version. |
| `y_field` | string | Must be `"rms_db"` for v1 (single fixed **y**). |
| `segments` | array | One object per voice segment row, sorted ascending by `start`. |

Each segment object:

| Key | Type | Meaning |
| --- | --- | --- |
| `start` | number | Segment start time in **seconds** (same timeline as transcript segments / voice feature rows). |
| `rms_db` | number | RMS energy in dB for that segment (raw feature, **not** z-scored). |

## Semantics

- **v1** `rms_db` is the same quantity as the `rms_db` column in voice feature tables merged into the prosody dashboard (`CORE_FEATURES` in `voice/dashboard.py`).
- Rows with non-finite or missing `start` or `rms_db` are omitted at write time.
- Empty `segments` is valid (no overlay chart for that run).

## Evolution

- **v2+** must use a new filename pattern (e.g. `_prosody_overlay_segments.v2.json`) and a new doc; readers must not guess layout across versions.
