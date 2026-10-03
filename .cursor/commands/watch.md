# Watch a Long Run to Completion (# watch)

Babysit one long run until it finishes. Log the pass as a local assessment. On failure or hang: fix, prove the fix with a focused test, then continue or restart the same run. Iterate until the run completes or a non-code blocker stops you.

Execute from the workspace root.

This command is **mutating when fixing issues**. Prefer minimal, targeted fixes. Do not expand into unrelated refactors or new features.

Do not publish, push, tag, or deploy unless explicitly instructed.

## Project card (fill before first use)

| Key | Value |
| --- | --- |
| Package | `transcriptx` |
| Default suite | `pytest -q` |
| E2E / restart recipe | `Continue a running analysis (Python API / Docker compose log watch). Do not invent a transcriptx analyze CLI. Restart only the same analysis/group recipe the user started.` |
| Resume / continue hint | `Resume or re-invoke the same analysis/group job; prefer in-place continue over a fresh full analysis when the product supports it.` |
| Hang quiet window (minutes) | `10` |
| Assessment directory | `assessments/` |
| Sibling ports never to touch | `none` |

---

## Inputs (resolve before starting)

1. **Target run** (required): the terminal file, PID, or command the user attached or named. Prefer an **already running** process. Do **not** start a new long run unless the user asked to start one.
2. **Restart recipe**: `Continue a running analysis (Python API / Docker compose log watch). Do not invent a transcriptx analyze CLI. Restart only the same analysis/group recipe the user started.` — use only to restart or continue the **same** kind of run after a fix. Do not invent a different workload.
3. **Resume hint**: `Resume or re-invoke the same analysis/group job; prefer in-place continue over a fresh full analysis when the product supports it.` — how to continue in-place when the tool supports resume (otherwise restart `Continue a running analysis (Python API / Docker compose log watch). Do not invent a transcriptx analyze CLI. Restart only the same analysis/group recipe the user started.`).
4. Record: terminal path, command line, started-at (if known), and whether this is watch-only or start+watch.

---

## 0. Open the assessment log (mandatory)

Create or append:

`assessments//YYYY-MM-DD-<slug>-watch.md`

Use today's date and a short slug from the run (e.g. `dossier-run`, `digest`, `ocr-probe`). Ensure `assessments//` exists and is gitignored in the product. Do **not** write under `docs/reviews/` or `docs/archive/`.

This file is a **run log**, not a stocktake. Seed it with:

- Command / terminal path
- Goal: watch until complete
- Started watching (timestamp)

Keep the log updated as events happen (failure, hang, kill, fix, test, restart).

---

## 1. Watch (mandatory)

Stay on the run. Read the terminal / logs periodically. Do not fire-and-forget.

**Progress is not a hang.** A moving counter, new log lines, or an advancing stage means the run is alive — keep watching.

**Failure signals:** non-zero exit when success was expected, uncaught traceback, crash, or explicit error that stops the run.

**Hang signals:** no new progress for `10` minutes (default 10). If the last line is one known-slow step (e.g. a single model call, a large file parse), wait longer before treating it as hung — then inspect.

While only watching, do **not** run `# backup` yet.

---

## 2. On failure — fix, test, continue

1. Diagnose from the last logs / exit code.
2. Before the **first** code edit in this watch session, run `# backup`. Wait for it. Skip if `# deep-test` (or an earlier watch step) already backed up in this session — note that in the assessment.
3. Apply the minimal fix.
4. Prove the fix with the smallest relevant test (`pytest -q` or a focused subset that covers the failure).
5. Continue the run if the tool resumes (`Resume or re-invoke the same analysis/group job; prefer in-place continue over a fresh full analysis when the product supports it.`); otherwise restart `Continue a running analysis (Python API / Docker compose log watch). Do not invent a transcriptx analyze CLI. Restart only the same analysis/group recipe the user started.`.
6. Log: failure, fix summary, test command + result, continue vs restart.
7. Return to §1.

---

## 3. On hang — wait, check, kill if needed

1. Confirm no progress for the quiet window (or the extended window for a known-slow step).
2. Inspect process state and last logs.
3. If still hung: kill **only** that run's process. Never inspect, bind, or kill `none`. Do not `docker compose down` or prune.
4. Then follow §2 (backup before first edit, fix, test, continue/restart).
5. Log: quiet duration, kill decision, then the fix path.

---

## 4. Stop conditions (do not loop forever)

Stop and report when:

- The same failure returns after a tested fix.
- The blocker is not a code bug (missing data, secrets, user confirmation, environmental skip).
- The user cancels.

Mark the assessment final result `blocked` with the reason. Do not keep restarting blindly.

---

## 5. On success

When the run exits successfully (or reaches its documented completion state):

1. Finalize the assessment: result `completed`, duration, failures fixed, hangs/kills, `git diff --stat` for code changes made during the watch.
2. Brief chat summary: completed / blocked; assessment path; what was fixed.

---

## Execution rules

- Prefer the attached running terminal over starting `Continue a running analysis (Python API / Docker compose log watch). Do not invent a transcriptx analyze CLI. Restart only the same analysis/group recipe the user started.`.
- Order after a problem: diagnose → backup (once, before first edit) → fix → focused test → continue/restart → watch again.
- Artifact cleanup, `docker compose down`, and docker prune stay **disabled**.
- No `/Users/…` literals. Resolve paths from `REPO_ROOT` / `$HOME`.
- Secrets stay out of git and out of the assessment log when avoidable (redact tokens).

---

## Final summary (required)

1. **Run** — command, terminal, outcome (`completed` / `blocked`)
2. **Assessment** — path under `assessments//`
3. **Incidents** — failures, hangs, kills (or none)
4. **Fixes** — each change and the test that proved it
5. **Diff** — `git diff --stat` for edits made during this watch
