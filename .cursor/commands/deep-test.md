# Deep Test / Harden After Plan (# deep-test)

Probe and harden after a plan has been implemented. Verify the plan landed end-to-end, deepen tests, run **scoped** analysis workloads only when the plan implicates the analysis pipeline (not for GUI-only / workspaces-only / docs-only lanes), then finish with a pre-release gate.

Execute from the workspace root.

This command is **mutating when fixing issues**: fix plan gaps, test failures, and runtime errors found during analysis probes. Prefer minimal, targeted fixes. Do not expand scope into unrelated refactors or new features.

Do not publish, push, tag, or deploy unless explicitly instructed.

---

## Inputs (resolve before starting)

1. **Plan** (required): the plan just implemented — attached Cursor plan, linked plan file under `.cursor/plans/` / `docs/`, or a path the user names. If none is clear, ask once, then stop.
2. **Small transcript** (default): `tests/fixtures/mini_transcript.json`.
3. **Large transcript** (default preference order):
   - Path the user names
   - `tests/fixtures/analysis_probes/large_norm.json` (reusable large probe; speaker map beside it)
   - A real multi-speaker transcript the user names under their library (`HOST_TRANSCRIPTS_DIR`)
   - If none of the above is usable, stop and ask — do not invent a synthetic “large” file by duplicating the mini fixture, and **do not copy probes into the user library**
4. **Group** (default preference order):
   - Group UUID / `.group.json` the user names
   - An existing file-backed group under `data/groups/` with ≥2 resolvable member transcripts
   - If none is usable, create a temporary two-member group from the small + large transcripts (or two distinct real transcripts) via the group service / documented group workflow, then use that UUID
5. **Analysis probe scope** (decide in §1.4): `skipped` | `rag-only` | `scoped`. Do **not** run the full default module set on every deep-test.
6. **Analysis mode** (when probes run): `quick` unless a touched module is heavy/LLM/audio-bound or §4 is required; use `full` only for large probe when §4 runs. Record mode + final module list.
7. **Skip LLM chart descriptions** (mandatory unless the plan under test *is* `chart_descriptions`): do **not** pass `modules=None` or `modules=[]` — both resolve to the default set, which includes finalize-phase `chart_descriptions` and will call Ollama once per chart. Other LLM modules run only when implicated by §1.4.

```python
from transcriptx.core.pipeline.dag_pipeline import DAGPipeline
from transcriptx.core.pipeline.module_registry import get_default_modules
from transcriptx.core.pipeline.module_registry_specs import MODULE_CLASS_MAP

def modules_implied_by_path(rel_path: str) -> set[str]:
    rel_path = rel_path.replace("\\", "/")
    hits: set[str] = set()
    for mod_id, (pkg, _) in MODULE_CLASS_MAP.items():
        src_prefix = "src/" + pkg.replace(".", "/") + "/"
        if rel_path.startswith(src_prefix):
            hits.add(mod_id)
    if "/core/pipeline/module_specs/" in rel_path:
        hits.add("_pipeline_specs")  # treat as shared pipeline; use minimal seed in §1.4
    return hits

def deep_test_modules(
    transcript_paths,
    seed_modules: list[str],
    *,
    for_group: bool = False,
    include_chart_descriptions: bool = False,
) -> list[str]:
    allowed = set(get_default_modules(transcript_paths, for_group=for_group))
    pipeline = DAGPipeline()
    ordered = pipeline.resolve_dependencies([m for m in seed_modules if m != "_pipeline_specs"])
    out = [
        m
        for m in ordered
        if m in allowed and (include_chart_descriptions or m != "chart_descriptions")
    ]
    return out
```

There is **no** `transcriptx analyze` CLI. Use the Python API (`run_analysis` / `run_group_analysis`) and/or Docker Compose web + log watch. See `docs/generated/cli.md`. The image `ENTRYPOINT` is `transcriptx`; one-shot Python in Compose needs `--entrypoint python`.

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

### 1.4 Analysis probe scope (mandatory)

Before §§3–5, classify the plan using the **implementation diff** (`git diff` + untracked files from the plan work) and the plan text. Record: `analysis_probe_scope`, `seed_modules`, and which of §§3–5 apply.

#### Lanes that skip §§3–5 (`analysis_probe_scope = skipped`)

Skip transcript/group analysis probes when changes are confined to lanes that do not execute or reshape the analysis DAG, for example:

| Lane | Typical paths (not exhaustive) |
|------|------------------------------|
| Streamlit GUI | `src/transcriptx/web/` (pages, widgets, transcript viewer UI) |
| Workspaces CC | `packages/transcriptx_workspaces/` **frontend** (`frontend/src`, build output) |
| Bridges / IPC only | `src/transcriptx/web/workspaces/*_bridge.py` when they only marshal UI actions and do not change `run_analysis` / pipeline contracts |
| Speaker ID UI | `src/transcriptx/web/page_modules/speaker_id.py`, `app/speaker_id/` when protocol/service behavior is unchanged |
| Docs / commands / packaging-only | `docs/`, `.cursor/commands/` (except when the plan *is* pipeline/analysis), `CHANGELOG`, release scripts with no `src/transcriptx/core` or `app/workflows` changes |

When scope is `skipped`, still run §2 (`# tests`) and §6 (`# pre-release`). Note `Analysis probes: skipped (non-analysis lane)` in the summary.

#### RAG-only plans (`analysis_probe_scope = rag-only`)

When the plan touches `src/transcriptx/core/rag/` (or RAG settings/ingest) **without** implicating analysis modules or group aggregation:

- Run `python scripts/deep_test_rag_probe.py` from the repo root (host venv).
- Skip §§3–5 unless the plan also implicates analysis (then run both: RAG probe + scoped §§3–5).

#### When analysis is implicated (`analysis_probe_scope = scoped`)

Treat analysis as implicated if **any** of:

- Paths under `src/transcriptx/core/analysis/`, `src/transcriptx/core/pipeline/`, `src/transcriptx/app/workflows/`, `src/transcriptx/app/models/requests.py`
- Group aggregation / member finalize paths (`services` group analysis, group charts, group `run_results`)
- Output/run truth loaders the plan names (`manifest`, `run_results`, finalization coordinator, performance sidecars)
- Plan text explicitly names analysis **modules**, presets, DAG behavior, or group analysis
- Tests added/changed under `tests/core/analysis/`, `tests/pipeline/`, `tests/smoke/test_all_modules_smoke.py`, or contract tests for module artifacts

**Do not** expand to “run everything” when implicated. Build a **seed list**:

1. Module IDs named in the plan (exact registry ids, e.g. `keyphrases`, `bertopic`).
2. Module IDs implied by changed files (`modules_implied_by_path` above; map `module_specs/*.py` edits to the modules defined in that file).
3. If implicated only via shared pipeline/finalization (no specific module files), seed `["stats", "sentiment"]` — enough to prove DAG wiring, not a full preset.
4. Resolve seeds: `deep_test_modules(..., seed_modules=seeds)` (dependency closure + transcript/group gates).

**Which probes to run (scoped):**

| Step | Run when |
|------|----------|
| §3 Small (Python + Docker) | Always when `scoped` (happy path for touched modules) |
| §4 Large | Any seed module is `heavy` / `requires_llm` / `requires_audio`, or plan/tests require large-corpus behavior, or shared finalization/DAG changed without a single-module focus |
| §5 Group | Plan or diff touches group aggregation, `for_group=True` modules in seeds, or group UI/workflow named in the plan; otherwise **skip** with reason |

User may override (e.g. “run large anyway”); default is the table above.

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

## 3. Small transcript analysis — Python + Docker (when §1.4 scope is `scoped`)

**Skip entire section** when §1.4 is `skipped` or `rag-only`.

Goal: prove the happy path for **seed modules** on a tiny fixture in both runtimes. Watch logs; fix failures.

### 3.1 Python (host)

Run via the Python API, for example:

```python
import os
from pathlib import Path
from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.workflows.analysis import run_analysis
# deep_test_modules / seed_modules from § Inputs + §1.4

os.environ["TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS"] = "1"
path = Path("tests/fixtures/mini_transcript.json")
modules = deep_test_modules([str(path)], seed_modules)
result = run_analysis(AnalysisRequest(
    transcript_path=path,
    mode="quick",
    modules=modules,  # never None/[] — those include chart_descriptions
    run_label="_deep_test_mini_py",
))
print(result.success, result.errors, getattr(result, "run_dir", None))
```

Adjust `transcript_path` / `mode` / `modules` / `output_dir` as needed. Prefer writing under `data/outputs/` with a clear `_deep_test_*` label. **Never import or copy probe transcripts into `TRANSCRIPTX_TRANSCRIPTS_DIR`.** Fixture JSON is unmanaged; `TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS=1` is required.

**Watch for:** traceback, `success=False`, non-empty `errors`, failed/blocked module outcomes in `run_results.json`, missing `manifest.json` / `run_results.json`.

**On failure:** diagnose, fix, re-run this step until green (or classify as known environmental skip with user confirmation — e.g. missing optional model).

### 3.2 Docker

Ensure the image is usable (`docker compose build` only if needed; prefer existing `transcriptx:latest`). Then either:

**A. One-shot API in compose (preferred when non-interactive):**

```bash
docker compose run --rm --entrypoint python \
  -e TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS=1 \
  -v "$(pwd)/tests/fixtures:/mnt/fixtures:ro" \
  transcriptx-web - <<'PY'
from pathlib import Path
from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.workflows.analysis import run_analysis
path = Path("/mnt/fixtures/mini_transcript.json")
modules = deep_test_modules([str(path)], seed_modules)
result = run_analysis(AnalysisRequest(
    transcript_path=path,
    mode="quick",
    modules=modules,
    run_label="_deep_test_mini_docker",
))
print(result.success, result.errors, getattr(result, "run_dir", None))
raise SystemExit(0 if result.success else 1)
PY
```

Mount `tests/fixtures` at `/mnt/fixtures`. **Do not copy or import probes into `/mnt/transcripts`** (that is the user library). Local `docker-compose.override.yml` may already mount fixtures at `/mnt/fixtures`.

**B. UI path:** `docker compose up` (or attach to a running `transcriptx-web`), run the small analysis in the UI with **Chart descriptions** unchecked, and **watch compose logs** for ERROR / Traceback / “Pipeline completed … with N errors”. Treat `[CHART_DESCRIPTIONS] 1/N` LLM loops as a miss of the skip unless the plan requires that module.

**Watch terminal continuously** during the run. On ERROR/traceback/failed modules: stop, fix, re-run §3.2 until clean.

Record both run dirs and whether Python vs Docker outcomes agree on success.

---

## 4. Large transcript analysis (when §1.4 requires it)

**Skip** when §1.4 says §4 does not apply (typical GUI-only / single light module plans).

Run analysis on the resolved **large** transcript with the **same `seed_modules` closure** as §3 (prefer Python API on host; Docker optional).

```python
import os
from pathlib import Path
from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.workflows.analysis import run_analysis
# deep_test_modules / seed_modules / needs_full_mode from §1.4

os.environ["TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS"] = "1"
path = Path("tests/fixtures/analysis_probes/large_norm.json")
modules = deep_test_modules([str(path)], seed_modules)
result = run_analysis(AnalysisRequest(
    transcript_path=path,
    mode="full" if needs_full_mode else "quick",  # needs_full_mode: heavy/LLM/audio or §1.4 table
    modules=modules,
    run_label="_deep_test_large",
))
print(result.success, result.errors, getattr(result, "run_dir", None))
```

Docker large probe: same `/mnt/fixtures` mount as §3.2, path `/mnt/fixtures/analysis_probes/large_norm.json`. Still do not import into the user library.

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

## 5. Group analysis (when §1.4 requires it)

**Skip** when the plan did not touch group paths or group-capable modules in seeds.

Resolve a usable group (§ Inputs). Run group analysis via API with group-scoped module closure:

```python
from transcriptx.app.models.requests import GroupAnalysisRequest
from transcriptx.app.workflows.analysis import run_group_analysis
modules = deep_test_modules([], seed_modules, for_group=True)
result = run_group_analysis(GroupAnalysisRequest(
    group_uuid="GROUP-UUID",
    mode="quick",  # or "full" if plan requires
    modules=modules,
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
- Order is strict: §0 → §1 → §2 → §3 → §4 → §5 → §6. §§3–5 follow §1.4 (may be skipped entirely). Do not skip §1, §2, or §6 unless impossible — then ask and wait.
- **Watch terminals** during any analysis probe you run; do not fire-and-forget long analyses.
- Never run the full default module list “because deep-test always does.” Use `seed_modules` + `deep_test_modules`. Omit `chart_descriptions` unless the plan changed that module. `modules=None` / `[]` is not a skip.
- Prefer minimal fixes tied to plan landing or probe failures.
- Do not delete run artifacts; cleanup remains disabled (same policy as `# tests` / `# pre-release`).
- Do not run destructive docker prune / compose down unless the user explicitly asks.
- If Docker daemon is unavailable: §3.2 is `skipped (not available)` with a **warning** when §3 runs; §6 still required.
- If §1.4 is `rag-only`: run `scripts/deep_test_rag_probe.py` instead of §§3–5.
- After any fix, re-run the smallest failing probe before continuing.

---

## Final summary (required)

Provide:

1. **Plan landing**
   - Table of plan items: landed / fixed during deep-test / waived / still open
2. **Tests (`# tests`)**
   - Suite result; what was expanded/deepened; key new tests
3. **Analysis probes** (include §1.4: scope, `seed_modules`, skipped steps + reason)
   - RAG-only script (if run): result
   - Small (Python): success / skipped, run_dir, modules run, issues fixed
   - Small (Docker): success / skipped, run_dir, issues fixed
   - Large: success / skipped, run_dir, issues fixed
   - Group: success / skipped, group UUID, run_dir, issues fixed
4. **Pre-release (`# pre-release`)**
   - Readiness: `READY` / `NEEDS FIXES` / `HIGH RISK`
   - Blocking issues and warnings
5. **Overall deep-test verdict**
   - `HARDENED` (plan landed, probes green, pre-release READY or only soft warnings)
   - `NEEDS FIXES` (open blockers)
   - `BLOCKED` (could not complete probes or plan review)

Also list `git diff --stat` for changes made during this deep-test run.
