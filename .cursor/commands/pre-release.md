# Pre-Release Check (# pre-release)

Run a final validation pass before tagging or publishing a release.
Execute from the workspace root.

Do not publish, push, or deploy unless explicitly instructed. After completion, summarize readiness and any blocking issues.

---

## 1. Tests

- Run full pytest suite.
- Ensure all tests pass.
- Confirm no skipped tests that should be active.
- Check for newly failing or flaky tests.

---

## 2. Code Quality

- Run formatter (ensure no diffs).
- Run linter (ruff or configured tool).
- Run type checking (mypy).
- Confirm no critical warnings remain.

---

## 3. Version & Metadata

- Confirm version number is updated consistently:
  - pyproject.toml
  - Package init (if applicable)
  - README (if version is displayed)
- Ensure changelog is updated.
- Verify license and author metadata are correct.

---

## 4. CLI & Documentation

- Verify CLI help output matches documented usage.
- Confirm README examples still work.
- Remove references to deprecated features.
- Ensure installation instructions are accurate.

---

## 5. Build & Packaging

- Build package locally (if applicable).
- Confirm no build errors.
- Verify generated artifacts (dist/, wheels, etc.).
- Ensure no unwanted files are included.

---

## 6. Docker (if applicable)

- Build Docker image.
- Confirm entrypoint works.
- Run a basic command inside container.
- Verify volume mounting and outputs behave as expected.

---

## 7. Output Sanity Check

- Run pipeline on a known sample transcript.
- Confirm expected outputs are generated:
  - Stats file
  - JSON outputs
  - CSV outputs
  - Charts
- Verify canonical naming conventions.

---

## Execution Rules

- Do not introduce new features.
- Do not refactor during pre-release unless fixing a blocking issue.
- Prioritize stability over improvements.
- After completion, summarize:
  - Pass / fail status
  - Blocking issues
  - Recommended next steps
  - Release readiness (ready / needs fixes / high risk)

If requested, generate a concise release checklist suitable for GitHub release notes.
