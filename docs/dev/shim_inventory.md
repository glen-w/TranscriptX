# Compatibility shim inventory (2026-07-20)

Behaviour-preserving cleanup only. Symbols below remain until callers, public exports, documented imports, plugins, and tests are audited. Do **not** delete on guesswork.

| Symbol / module | Role | Decision | Review date |
|-----------------|------|----------|-------------|
| `transcriptx.core.utils.file_rename` | Compatibility re-export for managed transcript rename | keep | 2026-10-20 |
| `transcriptx.core.utils.rename.io_atomic` | Re-export; canonical in `transcriptx.io.atomic_json` | keep | 2026-10-20 |
| `transcriptx.web.perf` | Compatibility re-exports; prefer `transcriptx.core.observability.perf` | keep | 2026-10-20 |
| Deprecated `speaker_map` parameters across analysis modules | Backward-compatible kwargs | keep | 2026-10-20 |
| `transcriptx.utils.text_utils` deprecated helpers | Point to `nlp_utils` | keep | 2026-10-20 |

## TODO / FIXME policy

`src/` must contain **zero** `TODO` / `FIXME` matches. CI / `scripts/release/stale_refs.sh` fails on new additions.
