# §3.4 Failure recovery — measured cases

**Status:** measured (≥2) — not signed-off RC evidence  
**Date:** 2026-07-27  
**Environment:** Docker Compose (`transcriptx-web`), package **0.9.8.x** (sidecar / compose), Streamlit 1.60.0  
**SHA tip:** bb6b8fe3fed5171187240ca74a9097277d82bcb4 (dirty worktree + live src mount)

## Cases exercised (2/2 required)

### 1. Partial module failure — **pass (recovery)**

Observed on Thorough run `20260726_015208_30728241` for `R20241026-121652` (see `run_R20241026-121652_thorough.md`):

- `llm_action_items` and `llm_custom_qa` timed out at **600s** → module **FAIL**
- Pipeline continued; other modules completed
- `final_status=partial`
- Outcomes honest; remaining modules usable

### 2. Malformed / missing path — **pass (rejection)**

Deliberate folder-import path rejects via Compose (`docker compose exec transcriptx-web python`), same code path as Import Transcript → “Scan folder” (`scan_folder_for_import` / `resolve_absolute_directory`):

| Input | Result |
|-------|--------|
| empty string | `AdmissionError`: Folder path is empty. · scan `closed_ok=False` |
| relative `relative/not/absolute` | `AdmissionError`: Folder path must be absolute … · scan `closed_ok=False` |
| missing abs `/tmp/transcriptx-acceptance-missing-folder-does-not-exist-3.4` | `AdmissionError`: Folder does not exist. · scan `closed_ok=False` |
| file-not-dir `/etc/hosts` | `AdmissionError`: Path is not a directory. · scan `closed_ok=False` |

**Index honesty:** failed scans return zero candidates and do not admit; no probe folder created; no partial corrupt registration from these rejects.

GUI exercise of the same banner was deferred this session (Streamlit busy generating chart descriptions on the Thorough run). Code path is the Import folder scan used by the GUI.

## Not exercised this pass (optional extras)

- Missing Ollama when Local AI selected
- Cancelled operation
- Unavailable optional module (BERTopic without extra) — BERTopic **RUN** on Thorough in this Compose profile
