# Deep Test / Harden After Plan (# deep-test)

Probe and harden after a plan has been implemented. Verify the plan landed end-to-end, deepen tests, exercise real analysis workloads (small / large / group), then finish with a pre-release gate.

Execute from the workspace root.

This command is **mutating when fixing issues**: fix plan gaps, test failures, and runtime errors found during analysis probes. Prefer minimal, targeted fixes. Do not expand scope into unrelated refactors or new features.

Do not publish, push, tag, or deploy unless explicitly instructed.

---

## Inputs (resolve before starting)

1. **Plan** (required): the plan just implemented — attached Cursor plan, linked plan file under `.cursor/plans/` / `docs/`, or a path the user names. If none is clear, ask once, then stop.
2. **Small transcript** (default): `tests/fixtures/mini_transcript.json` (fallback: `data/transcripts/mini_transcript.json` if present and valid).
3. **Large transcript** (default preference order):
   - Path the user names
   - A real multi-speaker managed transcript under `data/transcripts/` (e.g. meeting-length JSON used in recent Docker runs)
   - If none exists, stop and ask — do not invent a synthetic “large” file by duplicating the mini fixture
4. **Group** (default preference order):
   - Group UUID / `.group.json` the user names
   - An existing file-backed group under `data/groups/` with ≥2 resolvable member transcripts
   - If none is usable, create a temporary two-member group from the small + large transcripts (or two distinct real transcripts) via the group service / documented group workflow, then use that UUID
5. **Analysis mode**: prefer `full` when the change under test touches many modules; otherwise `quick` is acceptable. Record which mode and module list/profile were used.

There is **no** `transcriptx analyze` CLI. Use the Python API (`run_analysis` / `run_group_analysis`) and/or Docker Compose web + log watch. See `docs/generated/cli.md`.

---

## 0. Run backup first (mandatory)

Before doing anything else, run the **backup** custom command (`# backup`). Wait for it to complete, then proceed.

When later executing `# tests` and `# pre-release`, **skip their nested backup steps** if backup already succeeded in this deep-test run (note that in the summary).

---

## 1. Plan landing review (mandatory) — fix gaps

Compare the implementation to the plan. Do not treat “mostly done” as done.

### 1.1 Checklist against the plan

For every plan phase / todo / acceptance criterion:

| Check | Action |
|-------|--------|
| Code landed | Locate symbols/files named in the plan; confirm behavior matches the written decision |
| Tests landed | Confirm planned tests exist and cover the stated cases |
| Docs landed | Confirm planned doc updates exist and match code |
| Explicit non-goals | Confirm out-of-scope items were not accidentally implemented |
| Contracts / schemas | Confirm versioned artifacts, loaders, and invariants match the plan |

Use `git status`, `git diff`, and targeted searches. Prefer reading the plan’s todo list and marking each item `landed` / `partial` / `missing`.

### 1.2 Fix issues

- **Missing or partial plan items:** implement the minimum fix to land them.
- **Drift from plan decisions:** correct code/docs/tests to match the plan (or stop and ask if the plan itself is wrong).
- **Broken imports, schema mismatches, obvious regressions:** fix immediately.
- Re-run focused tests for anything you change in this phase before moving on.

### 1.3 Gate

Do not proceed to §2 until every **required** plan item is landed or explicitly waived by the user. Record waived items in the final summary.

---

## 2. Run `# tests` — expand and deepen (mandatory)

Execute the **tests** custom command (`# tests`) in full (except skip backup if already done in §0).

Deep-test-specific emphasis on top of `# tests`:

- Prefer expansion around **code touched by the plan** (new modules, changed contracts, loaders, pipeline/group paths).
- Add or deepen contract/unit tests for any gap found in §1.
- Keep default suite fast/offline; do not re-enable quarantined tests without justification.
- Baseline must be green (or failures classified) before expansion; after expansion, `pytest -q` must pass.

If `# tests` surfaces production bugs related to the plan, fix them, then continue.

---

## 3. Small transcript analysis — Python + Docker (mandatory)

Goal: prove the happy path on a tiny fixture in both runtimes. Watch logs; fix failures.

### 3.1 Python (host)

Run via the Python API, for example:

```python
from pathlib import Path
from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.workflows.analysis import run_analysis

result = run_analysis(AnalysisRequest(
    transcript_path=Path("tests/fixtures/mini_transcript.json"),
    mode="quick",   # or "full" if the plan requires it
    modules=None,   # None = recommended; or plan-relevant modules
    run_label="_deep_test_mini_py",
))
print(result.success, result.errors, getattr(result, "run_dir", None))
```

Adjust `transcript_path` / `mode` / `modules` / `output_dir` as needed. Prefer writing under `data/outputs/` with a clear `_deep_test_*` label.

**Watch for:** traceback, `success=False`, non-empty `errors`, failed/blocked module outcomes in `run_results.json`, missing `manifest.json` / `run_results.json`.

**On failure:** diagnose, fix, re-run this step until green (or classify as known environmental skip with user confirmation — e.g. missing optional model).

### 3.2 Docker

Ensure the image is usable (`docker compose build` only if needed; prefer existing `transcriptx:latest`). Then either:

**A. One-shot API in compose (preferred when non-interactive):**

```bash
docker compose run --rm transcriptx-web python - <<'PY'
from pathlib import Path
from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.workflows.analysis import run_analysis

result = run_analysis(AnalysisRequest(
    transcript_path=Path("/mnt/transcripts/mini_transcript.json"),
    mode="quick",
    modules=None,
    run_label="_deep_test_mini_docker",
))
print(result.success, result.errors, getattr(result, "run_dir", None))
raise SystemExit(0 if result.success else 1)
PY
```

If the mini fixture is not under the transcripts mount, copy/import it into `data/transcripts/` first (managed import workflow is fine), or mount/pass an equivalent path. Host fixture `tests/fixtures/mini_transcript.json` is not on `/mnt/transcripts` by default.

**B. UI path:** `docker compose up` (or attach to a running `transcriptx-web`), run the small analysis in the UI, and **watch compose logs** for ERROR / Traceback / “Pipeline completed … with N errors”.

**Watch terminal continuously** during the run. On ERROR/traceback/failed modules: stop, fix, re-run §3.2 until clean.

Record both run dirs and whether Python vs Docker outcomes agree on success.

---

## 4. Large transcript analysis (mandatory)

Run analysis on the resolved **large** transcript (prefer Python API on host; Docker UI/API optional if the plan or user requires Docker parity for large runs).

```python
from pathlib import Path
from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.workflows.analysis import run_analysis

result = run_analysis(AnalysisRequest(
    transcript_path=Path("PATH/TO/LARGE.json"),
    mode="full",  # prefer full for large probe unless user/plan says otherwise
    modules=None,
    run_label="_deep_test_large",
))
print(result.success, result.errors, getattr(result, "run_dir", None))
```

**Watch the terminal / logs for the entire run.** Treat these as failures to fix:

- Uncaught exceptions / tracebacks
- Modules failing that should succeed for this transcript
- Run marked failed or incomplete when modules were expected to finish
- Persistence errors (manifest / run_results / sidecar write failures that the plan says must not break the run — verify soft-fail vs hard-fail semantics)

After the run, spot-check:

- `run_results.json` module outcomes (status + `duration_ms` when expected)
- `manifest.json` present
- Any plan-specific artifacts (e.g. `.transcriptx/run_performance.json` if that was in scope)

**Fix and re-run** until the large probe is clean or remaining issues are explicitly waived.

Timebox: if hung with no progress for an unreasonable period (roughly 10+ minutes with zero log activity on a stuck module), kill, capture last logs, fix or classify as blocker.

---

## 5. Group analysis (mandatory)

Resolve a usable group (§ Inputs). Run group analysis via API:

```python
from transcriptx.app.models.requests import GroupAnalysisRequest
from transcriptx.app.workflows.analysis import run_group_analysis

result = run_group_analysis(GroupAnalysisRequest(
    group_uuid="GROUP-UUID",
    mode="quick",  # or "full" if plan requires
    modules=None,
    run_label="_deep_test_group",
))
print(result.success, result.errors, getattr(result, "run_dir", None))
```

Alternatively trigger from the Docker/Streamlit Groups UI while watching compose logs.

**Watch terminal for errors** through member runs and group finalisation (aggregation, charts, group `run_results.json` / manifest).

Verify:

- Group run directory under `data/outputs/groups/<uuid>/<run_id>/` (or configured output root)
- Group `run_results.json` + `manifest.json`
- Member runs completed or failures are explained
- Plan-specific group behavior (e.g. separate group performance sidecar, soft-fail sidecar warnings)

**Fix and re-run** until green or explicitly waived.

---

## 6. Run `# pre-release` (mandatory)

Execute the **pre-release** custom command (`# pre-release`) in full (except skip backup if already done in §0).

Deep-test context:

- Treat failures related to this plan’s surface as **blockers to fix now** when safe and in-scope.
- Do not tag/push/publish.
- Carry forward any deep-test analysis run paths into the pre-release summary if useful for output-sanity cross-checks (pre-release still runs its own canonical sample check).

---

## Execution rules

- Work from the workspace root.
- Order is strict: §0 → §1 → §2 → §3 → §4 → §5 → §6. Do not skip ahead unless a step is impossible (missing large transcript / group) — then ask and wait.
- **Watch terminals** during §§3–5; do not fire-and-forget long analyses.
- Prefer minimal fixes tied to plan landing or probe failures.
- Do not delete run artifacts; cleanup remains disabled (same policy as `# tests` / `# pre-release`).
- Do not run destructive docker prune / compose down unless the user explicitly asks.
- If Docker daemon is unavailable: §3.2 is `skipped (not available)` with a **warning**; §§3.1, 4, 5, 6 still required unless they also need Docker.
- After any fix, re-run the smallest failing probe before continuing.

---

## Final summary (required)

Provide:

1. **Plan landing**
   - Table of plan items: landed / fixed during deep-test / waived / still open
2. **Tests (`# tests`)**
   - Suite result; what was expanded/deepened; key new tests
3. **Analysis probes**
   - Small (Python): success, run_dir, issues fixed
   - Small (Docker): success / skipped, run_dir, issues fixed
   - Large: success, run_dir, issues fixed
   - Group: success, group UUID, run_dir, issues fixed
4. **Pre-release (`# pre-release`)**
   - Readiness: `READY` / `NEEDS FIXES` / `HIGH RISK`
   - Blocking issues and warnings
5. **Overall deep-test verdict**
   - `HARDENED` (plan landed, probes green, pre-release READY or only soft warnings)
   - `NEEDS FIXES` (open blockers)
   - `BLOCKED` (could not complete probes or plan review)

Also list `git diff --stat` for changes made during this deep-test run.
