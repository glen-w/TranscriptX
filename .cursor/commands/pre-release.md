# Pre-Release Check (# pre-release)

Local **developer-confidence** report for TranscriptX. Execute from the workspace root.

## Authority (hard rules)

This command is **not** the release gate and **must not**:

- Change the package version
- Edit `CHANGELOG.md`
- Create, inspect, or approve git tags for release
- Push commits
- Recommend a push or tag
- Claim to block, verify, or create tags
- Present itself as authoritative release governance

**Authoritative next-tag checklist:** [`docs/dev/release_governance.md`](../../docs/dev/release_governance.md).

**Outcomes for every check:** `pass` / `warning` / `failure` / `skipped` (with reason). Environment-dependent checks that cannot run report **`skipped`**, never a silent pass.

Release model: versioned git tags + Docker Compose image. Do **not** run `twine` / PyPI upload checks. The package is **not on PyPI**.

---

## Shared scripts (prefer these over ad-hoc commands)

| Check | Script |
|-------|--------|
| Compose bind | `bash scripts/release/assert_compose_bind.sh` |
| Tracked data allowlist | `python3 scripts/release/check_tracked_data.py` |
| Denylist / secrets | `bash scripts/secrets_check.sh` |
| Stale refs + TODO gate | `bash scripts/release/stale_refs.sh` |
| Clean-env audit | `bash scripts/release/clean_env_audit.sh` |
| Image pip check | `bash scripts/release/image_pip_check.sh` |

---

## 0. Optional backup

If the user has not already run `# backup` in this session, recommend running it. Backup failure is a **warning** for this local-confidence command (not a tag authority).

---

## 1. Worktree snapshot

- Report `git status --short` / porcelain v1 with `--untracked-files=all`.
- Dirty or unexpected paths → **failure** for local readiness (do not advise tagging).
- Branch / remote sync are informational; being behind remote → **warning**.

---

## 2. Tests (when locally available)

- Interpreter gate: `python --version` must satisfy `requires-python` in `pyproject.toml` (`>=3.10,<3.13`).
- Run in order via Makefile:
  1. `make test-smoke`
  2. `make test-contracts`
  3. `make test-fast`
- Config 1.7 / atomicity: `pytest -q tests/core/config/test_file_overrides_atomicity.py tests/core/config/test_nested_file_overrides_probe.py tests/core/config/test_settings_file_load_pilots.py`
- Failures → **failure**. Unavailable pytest/env → **skipped** with reason.

---

## 3. Packaging smoke

- `python -m build` (install `build` if needed).
- Install wheel with `--no-deps` into a throwaway check or report import of built wheel path; prefer clean venv when practical.
- Failure → **failure**.

---

## 4. Compose + Docker

- Always: `bash scripts/release/assert_compose_bind.sh` (`docker-compose.yml` only).
- When Docker available: prefer fresh `docker compose -f docker-compose.yml build` then `make docker-smoke`; then `bash scripts/release/image_pip_check.sh` when image exists.
- Docker unavailable → **skipped (Docker not available)** — never pretend pass.

---

## 5. Hygiene gates

- `python3 scripts/release/check_tracked_data.py`
- `bash scripts/secrets_check.sh`
- `bash scripts/release/stale_refs.sh`
- Optional: `bash scripts/release/clean_env_audit.sh` (may be slow; **skipped** if tooling missing)
- Any denylist / secrets / tracked-data / stale-ref failure → **failure** for the local readiness report. **Do not** recommend tagging or pushing.

---

## 6. Soft / optional

- `black --check` / `ruff check` / `mypy` → report; auto-fix only if the user asks (this command is non-mutating by default for Wave 0 local confidence).
- Docs drift → **warning**.
- CI status via `gh` when available → informational; missing CI/gh → **skipped**.

---

## Final summary

| Area | Outcome |
|------|---------|
| Worktree | pass / failure / warning |
| Tests | pass / failure / skipped |
| Packaging | pass / failure / skipped |
| Compose | pass / failure / skipped |
| Docker | pass / failure / skipped |
| Hygiene | pass / failure / skipped |

Then list failures and warnings. End with a **local confidence** line: `CONFIDENT` / `NEEDS FIXES` / `HIGH RISK` — explicitly **not** a release approval.
