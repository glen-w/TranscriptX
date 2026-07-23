Type: CONTRACT
Authority: self

# Speaker profiles v1 (Phase 1)

Longitudinal speaker records are **canonical versioned project files** under
`speaker_profiles_dir` (default `data_dir/speaker_profiles/`; override with
`TRANSCRIPTX_SPEAKER_PROFILES_DIR`). Profiles store real display names — treat
the tree as local PII. Prefer a path outside the git clone for real use; the
repo-local default is gitignored. All writes pass through `SpeakerProfileService`.
Any later SQLite/index is a rebuildable query accelerator only.

This contract freezes Phase 1 identity, storage layout, operation journaling,
fingerprints, aggregates, and date precedence. Implementation stages must not
weaken fail-closed rules below.

Related storage roots: `docs/runtime/STORAGE.md`.

---

## Canonical vs derived

| Kind | Location | Durable? |
|------|----------|----------|
| Profiles, live links, events, operation journals | `speaker_profiles_dir` (default `data_dir/speaker_profiles/`) | Yes — canonical (PII; do not commit) |
| Project operation lock | `state_dir/speaker_profiles.lock` | Lock only |
| Listing / aggregate caches / optional file index | `data_dir/speaker_profiles/.cache/` | No — disposable |
| Managed transcript JSON | `transcripts_dir` (library-admitted) | Canonical for content/metrics |
| Speaker-map sidecars | `transcripts/metadata/speaker_maps/` | Current display labels / ignore lists only |

Deleting `.cache/` must not lose profiles, links, events, or journals.

Phase 1 starts **without SQLite**. A derived file index may be added only after
documented reference-environment measurement (Stage 8); absolute millisecond
thresholds are not CI acceptance gates.

---

## Layout

```
speaker_profiles_dir/   # default: data_dir/speaker_profiles/; env: TRANSCRIPTX_SPEAKER_PROFILES_DIR
  profiles/{profile_id}.speaker_profile.json
  links/{link_file_key}.speaker_link.json
  events/{idempotency_id}.speaker_event.json    # filename stem == event idempotency key
  operations/{operation_id}.op.json
  operations/{operation_id}/staging/            # after-images while active
  operations/{operation_id}/backup/             # before-images while active
  .cache/                                       # disposable only

state_dir/
  speaker_profiles.lock                         # project operation lock only
```

### Symlink policy

Reject a symlinked `speaker_profiles` root. Reject symlink/alias escapes for
directories, files, staging, and operation paths: resolve and require realpath
under the canonical root.

---

## Schema IDs (frozen)

| Artifact | `schema_id` | Filename suffix |
|----------|-------------|-----------------|
| Profile | `speaker_profile.v1` | `.speaker_profile.json` |
| Live link | `speaker_profile_link.v1` | `.speaker_link.json` |
| Event | `speaker_profile_event.v1` | `.speaker_event.json` |
| Operation | `speaker_profile_operation.v1` | `.op.json` |

Wire `version` / `schema_version` fields are integers frozen at `1` for Phase 1.

---

## Transcript identity

`managed_transcript_id = str(uuid.UUID(import_id))` → lowercase hyphenated
`8-4-4-4-12` form. Reject non-UUID import ids. Never treat “hex as stored” as
ambiguous alternate forms.

`ManagedTranscriptResolver` maps `managed_transcript_id` → exactly one admitted
managed library transcript path. Fail closed when:

- duplicate `import_id` across admitted sidecars
- missing / invalid import sidecar
- `current_json_filename` does not match the transcript file beside the mirrored
  sidecar (stale)
- resolved path outside `transcripts_dir` library / not admitted
- symlink escape of library roots (same realpath discipline)

`observed_transcript_relpath` is an immutable audit snapshot written at link
time only. Never used for resolution. Always resolve the current path via
resolver + `import_id`.

Profile linking eligibility: **managed-library only**. Ad-hoc / run-output JSON
may use local naming on Speaker Identification, but must not create profile
links.

---

## Occurrence keys and fingerprints

Natural key: `(managed_transcript_id, local_speaker_key)` where
`local_speaker_key = normalize_diarized_id(raw segment speaker)`. Never display
name / `speaker_db_id`.

`link_file_key`: SHA-256 of UTF-8 canonical JSON

```json
["speaker_occurrence_key.v1", managed_transcript_id, local_speaker_key]
```

with `separators=(",", ":")`, `ensure_ascii=False`, `allow_nan=False`.

Normalisation collision gate: distinct raw speakers collapsing to one normalised
key → `SpeakerKeyCollisionError`; block linking; integrity warning.

### Fingerprint `occurrence_fingerprint.v1`

Ordered matching raw segments; fields `start`, `end`, `text`, `speaker` only.

**Timestamp canonicalisation (frozen)** before hash: for each of `start`/`end`,
if value is `int` or `float` (finite), convert to `float` then format with
exactly 6 decimal places via `format(x, ".6f")` (e.g. `1` and `1.0` →
`"1.000000"`). Non-finite → segment excluded from fingerprint input and treated
as timing-invalid for metrics. Strings that parse as finite floats are accepted
then canonicalised the same way; unparsable → timing-invalid.

Test vectors required for `1` vs `1.0` vs `"1.0"`.

Fingerprint mismatch on read: effective `needs_review`; no mutation.
Supersession is a separate journalled op.

---

## Live links, events, operations

- Live link v1: one confirmed live file per occurrence key. No suggested/rejected
  until voice phase.
- Unlink: journalled op writes `link_unlinked` event (after-image) + deletes live
  link (with before-image backup). No tombstone file. Absence = unlinked.
- Corrupt live link at the occurrence’s hashed path: `repair_required` / block
  new link and intersecting reads until repair quarantines or restores a valid
  file. Not “safely unlinked”.
- Event filename stem = `idempotency_id`. Payload may also carry `event_id`
  equal to the same UUID. Lookup by path; no full-tree scan for idempotency.
- Every mutation API accepts `operation_idempotency_key`. Retry of
  create-profile-and-link, unlink, relink, merge, archive, migration,
  supersession, profile update → replay original result; do not create
  duplicates.
- Portable operation protocol applies to every mutation that touches more than
  one canonical file or that pairs a domain write with an event.
- Phases: `prepared` → `staged` → `transaction_committed` → `finalized` →
  `complete` | `failed` | `needs_repair`.
- `transaction_committed` only when all planned profile, link, deletion, and
  event outcomes already match after-state.
- Read gating: only ops in `complete` or proven-aborted unblock affected
  records. `partial`, ambiguous, or `recovery_failed` → `needs_repair`;
  intersecting profile/link reads blocked.
- Optimistic concurrency on profile edits: `expected_content_sha256` of the
  profile file. Mismatch → `StaleUpdateError`.
- No new links to archived/merged profiles; merged redirect with cycle
  detection.
- Local naming vs linking separate; combined create+link is one profile-store op
  then best-effort sidecar name. Naming failure → `PartialSuccess` +
  `CacheInvalidationSignal` for committed parts; sidecar not in profile op
  atomicity.
- Ignored speakers: reject new links while ignored. Already-linked then ignored:
  visible and flagged `ignored=true`, excluded from headline aggregate totals
  and share denominators unless `include_ignored=True`.
- `observed_label`: audit only; UI resolves current sidecar label.
- Language variants: no auto profile-link inheritance.
- No new analysis module; do not reuse `speaker_id_to_db_id`.

---

## Phase 1.5 additions

### Profile `accent_color`

Optional `accent_color` on `speaker_profile.v1`: uppercase `#RRGGBB` or null
(auto name-hash at display time). Create without an accent assigns an unused
palette colour (then freeform `#RRGGBB` if the palette is exhausted). Update
supports `clear_accent`. GUI may pick any validated hex via colour wheel.

### Appearance flag precedence

Single winner: `repair_required` → `missing_source` → `collision` →
`needs_review` → `ignored` → `ok`. Higher flags must not be overwritten.

### Speaking share

Per-appearance share = occurrence duration ÷ transcript duration denominator.
Same-date / multi-appearance share buckets:
`sum(durations) ÷ sum(unique transcript denominators)` (each
`managed_transcript_id` counted once). Do not sum percentage shares.

### Aggregates and charts

Public `headline_eligible` is shared by aggregates and time-series builders.
Time-series emit separate `headline` and `all` series (no mixed-eligibility
point flag). `AggregationSnapshot` is the Speakers listing/aggregation entry
(one-pass links + memoized `TranscriptBundle` per managed transcript). Corrupt
canonical/operation files and blocking ops mark the snapshot incomplete —
partial totals must not be presented as complete.

### Link APIs

- `link_existing_profile`: unlinked occurrence → existing active profile.
- `relink`: requires a live link; same-owner is a service-level no-op;
  cross-owner requires expected link/owner preconditions.
- `unlink` / fingerprint supersede bind expected link id/hash/fingerprint;
  already-current fingerprint is a no-op; reject collision/ignored on supersede.

### Integrity

`run_integrity_scan` returns typed blocking details (`recovery_class`, affected
paths, entity intersections) and corrupt profile/link/event/operation paths.
Mutations assert intersecting entities are readable under the project lock.
Operation receipts must persist full cache-invalidation metadata for replay;
`recover_operation` invalidates affected profile/link caches.

### Completed-operation retention

After `complete`: delete staging/ and backup/ bytes; retain compact operation
receipt in the `.op.json`. Never cleanup ops that are active or `needs_repair`.

---

## Aggregate definitions (raw local speaker key)

New calculator; reuse `valid_segment_duration` only; **not** `compute_speaker_stats`.

| Metric | Rule |
|--------|------|
| Words | `str.split()` on segment text |
| Turns | Matching segment count; no coalescing |
| Durations | `valid_segment_duration`; invalid timing → no duration, turn still counts; `end==start` → `0.0` |
| speaking_share | Duration-only when denominator > 0; else `null` + `speaking_share_basis: "unavailable"` — never silent turn fallback |
| turn_share | Separate field |

Headline profile aggregates sum only appearances that are not `needs_review`,
not `missing_source`, not collision-affected, and not currently ignored.
Excluded rows listed separately with `pending_review_count`,
`missing_source_count`, `ignored_linked_count`.

### Appearance date precedence (frozen — verified against codebase)

1. Transcript document `source.imported_at` if parseable ISO datetime → date
2. Else import sidecar `imported_at` if parseable
3. Else `null` (sort nulls last; UI “Unknown date”)

Do **not** reference nonexistent `recording_date` / `session_date`.
Do **not** use filesystem mtime. Future session-date fields require a contract bump.

Verification note (2026-07): `transcript_schema.py` exposes `source.imported_at`
only among date-like source fields; import sidecars expose `imported_at`. No
`metadata.recording_date` / `session_date` fields exist today.

---

## Cache invalidation

Service returns `CacheInvalidationSignal` (frozen dataclass: scopes such as
`speaker_profiles`, `speaker_links`, `transcript_summaries`, optional ids).
Web layer maps signal → clear `@st.cache_data` helpers. Core must not import
Streamlit.

---

## Lock ordering

1. Acquire `state_dir/speaker_profiles.lock` (project op).
2. Per-file IO only via `locked_path` / `write_json_atomic_locked`
   (process-local → FileLock).
3. Never manually nest incompatible FileLocks around atomic writers.

---

## Not in Phase 1

- Suggested/rejected link states (voice phase)
- New analysis module ID
- Required SQLite
- Migrate-on-read
- Rename-transaction coupling for link keys
