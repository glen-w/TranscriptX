# Speaker-map diagnostics (B19)

Per-run honesty for diarized labels vs the speaker-map sidecar.

**What it is:** a light Foundations module (`speaker_map_diagnostics`) that reports named vs unnamed counts, map↔segment mismatches, T0–T3 tier, duplicate display names, and voice-link conflicts.

**What it is not:** a second speaker map, an auto-namer, or STT. BYO SRT still runs; missing STT provenance is reported as `has_sidecar: false`, not a skip.

**Outputs:** `{base}_speaker_map_diagnostics.json` — `status` `ok` / `partial` / `absent`.

**Config:** none (no Settings knobs).
