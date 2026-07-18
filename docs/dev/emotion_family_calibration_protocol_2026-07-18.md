Type: GUIDE
Authority: self

# Emotion family threshold calibration protocol

`threshold_profile_v1` must not be published from a single small fixture.

## Datasets

| Set | Path | Use |
|-----|------|-----|
| Calibration | `tests/fixtures/emotion_family/calibration/` | Tune provisional thresholds only |
| Held-out | `tests/fixtures/emotion_family/held_out/` | Promotion decision only |
| Gates | `tests/fixtures/emotion_family/promotion_gates.json` | Predefined floors/bands (set before held-out scoring) |

Never calibrate and approve against the same segments.

## Predefined promotion metrics (locked in `promotion_gates.json`)

1. Contextual macro-F1 ≥ `contextual_macro_f1_min`.
2. Neutral rate within `contextual_neutral_rate_band` on professional-neutral speech.
3. Fine-grained `no_label` rate within `fine_grained_no_label_rate_band` and distinct from native-neutral rate.
4. Abstention delta vs provisional ≤ `abstention_rate_delta_max_vs_provisional`.
5. Positivity bias: positive-label share on neutral-professional ≤ `positivity_bias_max_positive_share_on_neutral_professional`.

Helper (coverage + refuse auto-promote): `tools/emotion_family_calibrate.py`.

## Current status (2026-07-18)

**Promotion deferred.** Profiles remain `threshold_profile_provisional_v0` / `release_channel=experimental`. Hub revisions are pinned to immutable commit SHAs in `profiles.py` / `docs/runtime/models.md`; stable promotion still requires this calibration protocol plus held-out gate pass.

## Release

Phases 3–4 ship `release_channel=experimental` with `threshold_profile_provisional_v0`.
Stable promotion requires this protocol plus pinned Hub revisions and licence verification in `docs/runtime/models.md`.
