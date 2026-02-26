# Pytest Suite Maintenance & Expansion (# tests)

Clean, improve, and expand the pytest suite to increase reliability, coverage, and clarity. Run from the workspace root.

After completion, summarize changes made and any remaining test gaps.

---

## 1. Cleanup Existing Tests

- Remove obsolete or redundant tests.
- Update tests that reference deprecated APIs.
- Ensure test names clearly describe expected behavior.
- Remove duplicated setup logic (extract fixtures if needed).
- Ensure no brittle time-based or order-dependent tests.

---

## 2. Improve Structure

- Ensure consistent test file naming.
- Group related tests logically.
- Use fixtures instead of repeated setup.
- Mark slow or integration tests appropriately.

---

## 3. Expand Coverage

- Add tests for:
  - Edge cases
  - Error handling
  - CLI flags and argument parsing
  - Boundary conditions
- Add regression tests for previously fixed bugs.
- Ensure public-facing APIs are covered.

---

## 4. Coverage Review

- Run coverage.
- Identify untested critical paths.
- Prioritize core logic over trivial lines.
- Avoid writing tests purely to inflate coverage numbers.

---

## Execution Rules

- Do not change production behavior unless fixing a clear bug.
- Keep tests readable and minimal.
- Avoid over-mocking.
- Prefer deterministic tests.
- After completion, summarize:
  - Tests added
  - Tests removed
  - Coverage improvements
  - Remaining high-risk untested areas
