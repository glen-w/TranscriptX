# Workspace Cleanup & Quality Pass (# cleanup)

Run a code quality and hygiene pass to ensure the codebase is clean, consistent, and type-safe.
Execute from the workspace root.

After running, summarize issues found and confirm whether the workspace is clean.

---

## 1. Formatting

- **Run formatter**  
  Use the project formatter: `black .` (config in `pyproject.toml`).
- **Sort imports**  
  If the project uses ruff for import sorting, run `ruff check --fix .` (handled in step 2). Otherwise ensure no separate isort step is required.
- **Ensure no formatting diffs remain**  
  After formatting, run `black --check .` to confirm no further changes; fix any remaining diffs.

---

## 2. Linting

- **Run ruff** (or the configured linter)  
  `ruff check . --fix`
- **Fix auto-fixable issues**  
  Apply fixes from the first run; re-run if ruff made changes.
- **Summarize remaining issues**  
  List any remaining warnings or errors that are not auto-fixable.

---

## 3. Type Checking

- **Run mypy**  
  `mypy src/` (or project roots as in `pyproject.toml` [tool.mypy]). Use `--ignore-missing-imports` if the project does so (e.g. pre-commit).
- **Summarize type errors**  
  List file and line for each error.
- **Suggest minimal fixes**  
  Propose only the minimal change to satisfy the type checker. Do not refactor beyond that unless explicitly requested.

---

## 4. Tests (Quick Pass)

- **Run pytest in fast mode**  
  e.g. `pytest -q` or `pytest -x`, or `make test-fast` to match CI’s fast gate.
- **Confirm tests pass**  
  Note pass/fail and count.
- **Summarize failures**  
  For any failures, list test name, file, and a brief reason if obvious.

---

## Execution Rules

- Do **not** introduce new features.
- Do **not** perform structural refactors.
- Only fix **formatting**, **lint**, and **type** issues unless explicitly asked.
- After completion, provide a short summary with:
  - **Formatting:** what was changed (files/lines) or “no changes.”
  - **Lint:** issues fixed and any remaining warnings/errors.
  - **Types:** type errors found and minimal fixes applied or suggested.
  - **Tests:** status (e.g. “all passed” or “N failed” with summary).
