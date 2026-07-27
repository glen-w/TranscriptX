# Manual acceptance §0 — prerequisites log

**Status:** measured (not signed-off RC evidence)  
**Date:** 2026-07-26  
**SHA tip:** `bb6b8fe3fed5171187240ca74a9097277d82bcb4` (`v0.9.8.2`)  
**Package:** `0.9.8.2` (Compose container + `pyproject.toml`)  
**OS:** macOS 26.5 (arm64)  
**Profile:** Docker Compose (`transcriptx-web`)

## Checks

| Check | Outcome |
|-------|---------|
| Candidate identity | Recorded above |
| Clean worktree | Dirty vs SHA (Compose bind-mounts live `src/`) |
| Backup | Owner responsibility; not re-verified here |
| Disposable data root | Compose `/data` ← host `./data` (has deep-test artifacts); confirm disposable before journeys |
| Install profile | Compose up / healthy |
| `make test-gui-acceptance` | exit 0; 7 passed, 7837 deselected; ~11.84s; 2026-07-26 |
| Streamlit | Compose **1.60.0**; host AppTest env **1.52.2** |
| Official Streamlit browsers | Two most recent of Chrome, Firefox, Edge, Safari ([docs](https://docs.streamlit.io/knowledge-base/using-streamlit/supported-browsers)) |
| Maintainer browser smoke | Safari 26.5; Firefox 152.0.4 (aarch64); Waterfox 6.6.17 (aarch64). Waterfox not official. Chrome/Edge not yet smoked (§3.11 still open) |

## AppTest detail

```
make test-gui-acceptance
platform darwin -- Python 3.10.13, pytest-9.1.1
7 selected / 7 passed
tests/web/gui_acceptance/test_default_preset.py
tests/web/gui_acceptance/test_export.py
tests/web/gui_acceptance/test_group_run.py
tests/web/gui_acceptance/test_insights_charts.py
tests/web/gui_acceptance/test_managed_import.py
tests/web/gui_acceptance/test_partial_failed_run.py
tests/web/gui_acceptance/test_speaker_profile.py
```
