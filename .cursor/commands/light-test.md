# Light Test on the Change Set (# light-test)

Narrow sibling of `# deep-test`. Check **what changed**, fix failures on that path, and stay fast and offline.

Execute from the workspace root.

This command is **mutating when fixing issues** found in the selected tests or the cheap probe. Prefer minimal, targeted fixes. Do not expand into unrelated refactors, new features, or a whole-suite coverage pass.

Do not publish, push, tag, or deploy unless explicitly instructed.

This is **not** a substitute for `# deep-test`. It does not land a plan, expand the suite, run a large workload, exercise extra surfaces, or finish with `# pre-release`.

## Project card (fill before first use)

| Key | Value |
| --- | --- |
| Package | `transcriptx` |
| On-disk package | `src/transcriptx` |
| Default suite (runner only) | `pytest -q` |
| Small probe | Host Python only: `run_analysis` on `tests/fixtures/mini_transcript.json` with `mode="quick"` and `TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS=1`. No Docker, no UI, no `full` mode. Skip if the call needs a model. |
| Small fixture | `tests/fixtures/mini_transcript.json` |
| Sibling ports never to touch | `none` |

---

## Out of scope (do not run)

- The full `pytest -q` when that command walks the whole tree
- `# tests` (review and expansion of the suite)
- `# pre-release` (packaging, Docker, hygiene scripts, release confidence)
- Large-fixture and extra probes (real-sized workloads, UI, resume, compose)
- Live models, LLM APIs, embedding or weight downloads, GPU jobs
- Network, Docker build / up / down / prune, or any install of optional heavy extras
- `# watch`, and any job that sits for many minutes

If the only way to exercise a change is one of the above, mark that part `skipped (heavy)` and say why. Do not install the missing stack to make it runnable.

---

## Inputs (resolve before starting)

1. **Change set** (required). Preference order:
   - Paths, a diff range, or a plan the user names
   - Files changed in this session
   - Staged, unstaged, and untracked files (`git status --short`, `git diff --name-only`, `git diff --cached --name-only`, `git ls-files --others --exclude-standard`)
   - Commits on this branch since the merge-base with the default branch (`main` or `master`, whichever exists)
2. If that set is empty, ask once what to test, then stop. Do not fall back to the whole suite.
3. Record the list before running anything. Drop generated output, caches, and secrets from the test selection. Docs-only and command-template-only diffs have nothing to execute.

---

## 0. Run backup first (mandatory)

Run `# backup`. Wait for it to complete, then proceed.

This command does not call `# tests` or `# pre-release`. If a later step in the same session does, skip that command's nested backup and note it.

---

## 1. Map the change set to light tests (mandatory)

For each changed path:

| Change | Tests to consider |
| --- | --- |
| A test module (`test_*.py`) | That file |
| A module under `src/transcriptx` | Test files that import it or name its module path |
| `conftest.py` or a shared test helper | Tests that use it, after the heavy filter below |
| Docs, prompts, or config with no runtime effect | None |

Search with the module path. Do not add the rest of `tests/`.

**Drop a test before running it** when any of these are true:

- It is marked slow, llm, gpu, network, integration, e2e, docker, or `requires_*` (only markers this project actually defines — do not pass `-m` for markers it does not have)
- The body calls a model API, loads weights, needs a key, opens the network, talks to Docker, or reads a fixture other than `tests/fixtures/mini_transcript.json`
- Collection imports an optional heavy stack that is not part of the default test env (for example a local LLM runtime, a deep-learning framework, or a browser driver)
- Setup in `conftest.py` boots a service, model, or compose stack for that test

If a file mixes light and heavy cases, run only the light node ids. If every covering test is heavy, report `skipped (heavy)` for that changed file. Do not `pip install` the extra.

When a changed behavior has **no** light test, add one small deterministic test (`tmp_path`, no network, no model, no extra install). One focused test is enough. Do not start a `# tests` expansion.

---

## 2. Run the selected tests (mandatory)

Use the same runner style as `pytest -q`, with the selected files or node ids in place of any whole-tree path.

If `pytest -q` is a Makefile (or other) target that always runs the full suite, invoke the underlying pytest (or project equivalent) on the selected paths instead.

```bash
python -m pytest tests/test_changed_area.py -q --tb=short
```

Replace that path with the files resolved in §1. Use ASCII hyphens.

- Nothing testable in the change set → `skipped` with reason. Do not run the default suite "just in case".
- Failure in a selected light test that this change caused → minimal fix, then re-run that test before continuing.
- Failure that predates the change and sits outside it → classify it; do not boil the ocean.
- A selected test starts a download, a model load, or runs with no progress toward a fast assertion → stop it and mark `skipped (heavy)`.

Prefer disposable dirs under `/tmp/transcriptx-light-test-*` or the project's documented test-output root.

---

## 3. Small probe (only when it stays light)

Run Host Python only: `run_analysis` on `tests/fixtures/mini_transcript.json` with `mode="quick"` and `TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS=1`. No Docker, no UI, no `full` mode. Skip if the call needs a model. on `tests/fixtures/mini_transcript.json` only when all of these hold:

- The change set touches the code that probe exercises
- The probe is offline, uses the mini fixture, and needs no new dependency, service, or model
- You can watch it finish promptly (a short run, not a babysat job)

Otherwise mark the probe `skipped` with reason.

**Never** run a large-fixture probe or an extra / UI / Docker probe.

**Never inspect, bind, or kill `none`.** Stop leftover processes this probe started.

On failure of a probe you did run: diagnose, apply a minimal fix, re-run it.

---

## Execution rules

- Order is §0 → §1 → §2 → §3. Do not skip ahead to a broader command.
- Work from the workspace root.
- Stay on the change set. A green subset is the goal; a green whole tree is `# deep-test`.
- Do not delete run artifacts. Cleanup, `docker compose down`, and docker prune stay disabled.
- After any fix, re-run the smallest failing test or probe before finishing.

---

## Final summary (required)

1. **Change set** — paths in scope
2. **Tests** — commands run, pass / fail, and what was `skipped (heavy)` or left out because it did not touch the diff
3. **Tests added** — the one light test, if any
4. **Small probe** — ran / skipped, path, result
5. **Overall verdict** — `LIGHT PASS` / `NEEDS FIXES` / `BLOCKED`

`LIGHT PASS` means the light checks for this diff are green. It does not mean the branch is hardened.

Also list `git diff --stat` for changes made during this run.
