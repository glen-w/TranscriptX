Type: CONTRACT
Authority: self

# Speaker profiles — voice phase v1 (R2)

Local voice fingerprinting and suggested speaker matches. Confirmed
`transcriptx.speaker_profile_link.v1` records remain the **sole** cross-transcript identity
authority. Voice artefacts are suggestive evidence only.

Companion to [`speaker_profiles_v1.md`](speaker_profiles_v1.md). Same
`speaker_profiles_dir`, same root `operations/` journal (`OperationEngine`).
**No** `voice/operations/` subtree.

Related storage: `docs/runtime/STORAGE.md`.

---

## Product rules (frozen)

- Assistive only — never auto-create, replace, or confirm a profile link from scores.
- `privacy.voice_settings.json` is the **sole** activation and consent authority.
  No parallel config/env enable flag may disagree with it.
- Single `ActivationBarrier`: production analyse, Settings enablement, enrolment,
  and UI acceptance stay inaccessible until lifecycle, recovery, deletion,
  privacy, and integrity stages complete (`FEATURE_GATE_COMPLETE`).
- Explicit bootstrap enrols trusted references; privacy opt-in alone enrols nothing.
- Confirmed `speaker_profile_link` rows are **not** voice evidence. Matching
  compares query excerpts only to enrolled samples under `voice/samples/`,
  `voice/embeddings/`, and `voice/vectors/`. An empty reference corpus is
  expected to analyse successfully and return **no suggestion**
  (`NoReliableMatch`) — that is not a model failure.
- Leave unlinked is session-only — not a durable rejection.
- Never put raw cosine scores in immutable Phase 1 events.

---

## Layout

```
speaker_profiles_dir/
  profiles/ links/ events/ operations/     # Phase 1; voice files use same journal
  voice/
    privacy.voice_settings.json
    operator.voice_settings.json           # enrol link cap etc. (not consent)
    active_generation.json
    generations/{model_generation_id}.json
    samples/{sample_id}.voice_sample.json
    embeddings/{embedding_id}.voice_embedding.json
    vectors/{embedding_id}.npy
    decisions/{decision_id}.voice_decision.json
  .cache/voice/                            # disposable; wipe with voice data
    excerpts/
    query/
    suggestions/
    summaries/
    indexes/
```

Path policy: reject absolute paths and `..` **before** any `stat`, read, staging,
or backup (`assert_safe_relpath`). Same symlink / containment rules as Phase 1.

---

## Schema IDs (Stage 0+)

| Artifact | `schema_id` |
|----------|-------------|
| Privacy settings | `transcriptx.voice_privacy_settings.v1` |
| Operator settings | `transcriptx.voice_operator_settings.v1` |
| Active generation pointer | `transcriptx.voice_active_generation.v1` |
| Model generation pin | `transcriptx.voice_model_generation.v1` |
| Voice sample | `transcriptx.voice_sample.v1` |
| Embedding metadata | `transcriptx.voice_embedding.v1` |
| Match decision | `transcriptx.voice_match_decision.v1` |
| Suggestion cache | `transcriptx.voice_match_suggestion.v1` |
| Profile voice summary | `transcriptx.profile_voice_summary.v1` |

Privacy notice version (user-facing copy pin): `voice_privacy_notice.v1`.
Bump requires re-consent.

---

## Typed link provenance

`LinkProvenanceV1` (`extra=forbid`) is required on create/link/relink; optional on
supersede. Methods accept this model only — never an unrestricted UI dict.

`link_method`: `manual` | `suggestion_assisted` | `choose_other` | `create_new` |
`relink` | `supersede`.

Suggestion-assisted requires `suggestion_id` and `suggestion_digest`.

---

## Activation barrier

`ActivationBarrier.status()` / `assert_processing_allowed()`:

1. `FEATURE_GATE_COMPLETE` must be true (code constant; Stage 8 exit).
2. Privacy `enabled` and current `privacy_notice_version`.
3. `wipe_required` must be false.

Until the gate opens, Settings must not offer enablement.

**Current tree status:** `FEATURE_GATE_COMPLETE = True` after Stage 8 exit.
Privacy still defaults to disabled — users must consent via journalled
`privacy.voice_settings.json` (Settings → Storage) before analyse/enrol/accept.
Local/dev exception: when that file is **absent**,
`TRANSCRIPTX_VOICE_PRIVACY_DEFAULT_ENABLED=1` (set in
`docker-compose.override.yml`) may treat voice as enabled. An existing settings
file remains sole authority and is never overridden by the env var.

Explicit bootstrap: Speakers detail → “Enrol trusted voice from confirmed links”
(`VoiceBootstrapService`). Promote suggestion-assisted samples before they enter
the reference corpus. Bootstrap walks confirmed links in deterministic path
order up to `bootstrap_max_links` from `operator.voice_settings.json`
(Settings → Storage → **Max confirmed links per voice enrol**; default **40**,
range 1–200). That file is operator config only — not consent — and survives
privacy revoke / evidence wipe. Match-time still caps refs per source link
(`MAX_REFS_PER_SOURCE_LINK`).

**Operator expectation:** enabling voice privacy (or the local privacy-default
env exception) only unlocks analyse/enrol/accept. Until at least one profile
has eligible enrolled embeddings, Speakers “Find voice match” / analyse will
not propose a profile — check for `voice/embeddings/*.voice_embedding.json`
(and matching vectors) before debugging thresholds or SpeechBrain.

---

## Evidence enrolment (Stage 3)

`VoiceEvidenceService.enrol_trusted_excerpts_from_link` journals samples,
embeddings, vectors, and a `voice_evidence_enrolled` event (ids/counts only —
no raw scores) through the **root** `OperationEngine`. Deterministic
`sample_id` / `embedding_id` prevent duplicate evidence on retry. Explicit
bootstrap enrol (`VoiceBootstrapService`) caps confirmed links via
`bootstrap_max_links` in `operator.voice_settings.json` (default 40).

Trust: `suggestion_assisted` → `ineligible_trust` until journalled promotion.
Opt-in alone enrols nothing.

---

## Matching (Stages 4–5 provisional)

Open-set ranking: mean of top-k ref cosines per query excerpt, then mean across
queries. `tau_no_match` suppresses weak nearest neighbours. Threshold constants
in `voice/thresholds.py` are **provisional** until eval freeze
(`threshold_policy_id` separate from `model_generation_id`).
Reference load caps duplicate evidence per source link
(`MAX_REFS_PER_SOURCE_LINK`).

With **zero** eligible reference embeddings, ranking has no candidates and the
analyse outcome is `NoReliableMatch` (same as scores below `tau_no_match`).
Enrol trusted voice from confirmed links first; only then can scores clear
thresholds and surface `SuggestionAvailable`.

Reject decisions suppress re-suggestion until generation or
`reference_corpus_digest` changes. Leave-unlinked writes no decision.

---

## Lock protocol

Snapshot under `speaker_profiles.lock` → extract/infer **outside** the lock →
reacquire and revalidate privacy, active generation, link owner, fingerprint,
audio identity, and corpus digest before commit or cache write.

---

## Journals

Cross-domain acceptance (link/event + voice decision + retained query-evidence
enrolment) is one `operation_idempotency_key` and one root journal plan via
`extra_writes` / `extra_writes_builder` on Phase 1 link APIs. Accept
preconditions include optional audio identity checks.
`CacheInvalidationSignal` may include scope `speaker_voice`.

Query excerpts enrolled on accept use trust `suggestion_assisted` /
eligibility `ineligible_trust` until an explicit promote.
---

## Export / backup

Ordinary exports and project backup discovery must exclude `voice/` and
`.cache/voice/`. Canonical entry point:

`transcriptx.core.speaker_profiles.layout.iter_paths_for_ordinary_backup`

(also `voice.backup_inventory.iter_speaker_profiles_paths_for_backup` /
`is_voice_excluded_relpath`). Do not ad-hoc `rglob` the profiles root for
archives. Profiles and confirmed links remain.

---

## Delivery residuals (honest)

Closed in the file-backed residual wave:

- Accept co-journals retained query-evidence as `suggestion_assisted` /
  `ineligible_trust` (promote still required for corpus eligibility).
- Eval harness (`scripts/eval_speaker_voice_match.py` + `voice/eval_metrics.py`)
  reports FAR/FRR against provisional bands; **do not invent new thresholds**
  without a labeled held-out library run.
- Merge voice transfer uses chunked continuation journals
  (`voice_merge_transfer_chunk`) with content-addressed idempotency keys.
- Stage 9 disposable file matrix under `.cache/voice/indexes/` is implemented
  and preferred when digest-fresh (see
  [`speaker_voice_match_index_gate.md`](../dev/speaker_voice_match_index_gate.md)).

Still open / provisional:

- Threshold constants in `voice/thresholds.py` remain **`voice_threshold.v1`**
  until an operator-labeled speaker/recording-held eval freezes
  `threshold_policy_id` to v2 (keep current taus until then).
- Multiprocess crash-injection matrix can deepen further beyond accept+evidence,
  promote, and chunked merge coverage.
- SQLite/DB analytics views and group gallery keyed by `profile_id` are
  **not** voice-file work (B5 remainder without DB is closed).
