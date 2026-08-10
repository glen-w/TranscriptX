# Theme C invest / narrow / defer decision

Type: DEVELOPER  
Authority: self  
Status: provisional after Phase 3 scaffolding  
Date: 2026-08-10

## Decision: **Invest** (narrowed to Speaker ID first, Corrections protocol ready)

### Evidence

- Phase −1 action service landed; legacy + CCv2 share mutation semantics.
- Non-blocking ClipService APIs prevent cold ffmpeg joins from the bridge.
- Packaged CCv2 Speaker ID workspace mounts behind feature flag with
  transcript-scoped keys, revisioned commands, and ClipTransport T0 (base64).
- Corrections revisioned command/ack service exists; apply/export duplicate-safe.
- Browser harness tests cover audio identity, transcript switch, and keyboard
  input suppression.
- PlaybackHost contract extracted for Theme D without inventing word timings.

### Narrowing

- Do **not** remove the legacy Speaker ID fragment path (Phase 9 criteria).
- Default flag remains off until the browser suite is green in CI on Streamlit
  min + current (Phase 5 gate). When flipping default-on, keep flag-off rollback
  for one release window.
- Corrections CCv2 UI migration follows Speaker ID default-on; protocol is ready.

### Defer / escalate

- Full SPA + Python API remains deferred until written evidence that CCv2
  remount/bytes/focus limits block product goals after default-on soak.
