# LLM feedback v1 (collect-only)

Local-first, append-only user ratings of LLM analysis outputs shown in the
Streamlit GUI. v1 **collects only** — no model-recommendation consumption.

Related: `docs/runtime/STORAGE.md`, LLM provenance under analysis modules.

---

## Layout

```
{data_dir}/state/llm_feedback/
  events.jsonl                 # append-only event log
  submission_tokens.json       # token → feedback_id (under same lock)
  events.jsonl.lock            # FileLock sibling (implementation detail)
```

Resolve `data_dir` outside the UI widget; inject a configured store/service.

### Safety

- Create `llm_feedback/` with restrictive directory mode (`0o700` where supported).
- Events file mode `0o600` where supported.
- Reject symlinks for the store directory, events file, token index, and lock path.
- Reject non-regular existing target files.
- Enforce containment beneath the resolved `data_dir` (resolve + `relative_to`).
- Writer: cross-process `FileLock`, open with `O_APPEND`, write one UTF-8 line + `\n`,
  `flush` + `fsync` before success. Do **not** use `artifact_writer.write_json`.

### Truncated tail

Never rewrite or truncate earlier valid lines to “repair” the file. If the file
does not end with a newline, the next append seals the incomplete line with `\n`
then writes the new event (so new events are never glued onto a truncated line).
Readers must tolerate and **report** a malformed final line (`tail_error`).

---

## Schema ID

| Artifact | `schema_id` |
|----------|-------------|
| Feedback event | `transcriptx.llm_feedback_event.v1` |

Top-level `schema_id` is **only** the feedback event schema. Artifact/response
schema is `provenance.output_schema_id` — never a sibling field named `schema_id`
inside provenance.

---

## Rating ↔ reason

| Rating | Allowed reasons |
|--------|-----------------|
| `up` | `helpful`, `other` |
| `down` | `too_vague`, `inaccurate`, `too_long`, `too_short`, `wrong_style`, `other` |

Reject incompatible pairs at validation time.

---

## Null policy

Every declared schema key is always present. Unavailable optionals are JSON
`null` (never omitted). `note` is always a string (`""` when empty).

---

## Event fields

| Field | Rules |
|-------|--------|
| `feedback_id` | UUID4 string |
| `created_at` | ISO-8601 UTC with explicit `Z` |
| `target_instance_id` | Hex digest over immutable identity parts |
| `submission_token` | UUID4; idempotent under lock |
| `supersedes_feedback_id` | Prior latest for instance, or `null` |
| `rating` | `up` \| `down` |
| `reason` | See matrix |
| `note` | NFC, ≤ 2000 code points, no NULs; privacy warning in UI |
| `output_sha256` | 64 lowercase hex of exact rated text (UTF-8 of NFC) |

### Target (required combinations by surface)

| Surface | Required non-null |
|---------|-------------------|
| `insights_block` | `block_id`, `module`, `run_id`, `subject_type`, `subject_id`, `artifact_rel_path` |
| `overview_hero` | same |
| `custom_qa_answer` | above + `question_id` + `questions_hash` |
| `chart_caption` | `module`, `run_id`, subject fields, `logical_chart_id`; `artifact_rel_path` when known; `block_id` may be `null` |

Do not use display titles, speaker display names, absolute FS paths, or
`question_index` alone as identity. `artifact_rel_path` is relative to run root,
no `..`, no absolute forms.

`subject_type` ∈ `{transcript, group}` (matches BlockContext / run identity).

### Provenance

Always present keys: `provider`, `model`, `prompt_version`, `llm_request_sha256`,
`output_schema_id` — each string or `null`. Missing provenance must not block
submit when required target identity + `output_sha256` are present.

`llm_request_sha256` alone does not identify the rated output; `output_sha256`
plus artifact path/version fields are required.

---

## `target_instance_id`

Deterministic SHA-256 hex over:

`surface | run_id | subject_type | subject_id | module | artifact_rel_path | output_sha256 | question_id | questions_hash | logical_chart_id | block_id`

Null parts encoded as empty string. Same rated output → same instance id.

---

## Submission semantics

- Append-only. New ratings for the same `target_instance_id` supersede prior ones
  (readers take latest `created_at`).
- `submission_token` allocated when the form opens; retries reuse it until success.
- Duplicate token under lock → no second line; return prior `feedback_id`.
- Clear Streamlit form state only after confirmed durable append (or idempotent ack).
- Persistence failures are non-fatal to page render; preserve form; no success toast
  before durable completion.

---

## Non-goals (v1)

Model guidance consumption, REST/DB/sync, export HTML controls, JSONL compaction,
multi-user identity, feedback on non-LLM modules.
