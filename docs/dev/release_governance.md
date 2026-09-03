# Release governance (manual next-tag checklist)

This document is the **authoritative release gate** for public version tags. It is **not** enforced by `.cursor/commands/pre-release.md` (local developer confidence only).

**Do not create the next version tag until every item below is green.**

## Wave 0 eng criteria (closed)

Release hygiene **A1–A10**, Config **1.7** atomic apply, Config **1.8** curated `to_dict`, and docs/inventory parity are **implemented in-tree** (stocktake refreshed for **0.9.7**). Remaining work before a public **1.0** tag is this checklist + evidence runbook, plus programme gates in [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) (human-testing wave, unfamiliar-user validation, [severity triage](release_severity_triage_1_0.md), performance/trust owner sign-off, RTD go-live) — not missing Wave 0 code.

**Hardening triage:** classify findings with [release_severity_triage_1_0.md](release_severity_triage_1_0.md) before scheduling RC work.

## Checklist

1. All Wave 0 acceptance criteria green (release hygiene A1–A10 + Config 1.7 atomic apply + docs/inventory parity).
2. **Green CI on the exact intended release commit** (full Python matrix 3.10–3.12 + `compose-config` + `release-checks`). Failed or cancelled matrix members block.
3. `pyproject.toml` version matches the intended tag (`v` prefix aside).
4. Dated Keep-a-Changelog section for that version in `CHANGELOG.md`.
5. Clean worktree (`git status --porcelain=v1 --untracked-files=all` empty of unexpected paths).
6. Fresh-clone installation evidence per `docs/runtime/install_verification_matrix.md`.
7. Release-evidence bundle complete (see below).
8. Fixable CVEs cleared **or** exceptional waiver fully filled + approved in `docs/dev/dependency_audit.md`.
9. No denylist violations; `scripts/secrets_check.sh` green.
10. **Recommended (GUI primary surface):** `make test-gui-acceptance` green on the intended commit, and the residual AppTest-blind items in [`gui_acceptance_residual_checklist.md`](gui_acceptance_residual_checklist.md) recorded as pass/fail/skip in the evidence notes.

Humans (or an explicit user instruction outside the pre-release command) perform tag/push after this checklist is satisfied.

## Release-evidence bundle

Attach (machine- or human-readable) at tag time:

- Stale-reference sweep (`scripts/release/stale_refs.sh`)
- Repo hygiene audit (`scripts/release/repo_hygiene_audit.py` — warn mode until promoted)
- Dependency audit + installed-package inventory (clean-env and, where practical, image)
- Documented-install matrix results
- Tracked-data allowlist comparison (`scripts/release/check_tracked_data.py`)
- Secrets and denylist results
- Package-version check
- Canonical Compose assertions (`scripts/release/assert_compose_bind.sh`)
- Docker smoke result after fresh build
- Config 1.7 inventory / parity evidence
- (Recommended) GUI acceptance: `make test-gui-acceptance` result + residual checklist notes ([`gui_acceptance_residual_checklist.md`](gui_acceptance_residual_checklist.md))

## Local evidence runbook (checklist item 7)

Run from the repository root on the **intended release commit** (clean worktree preferred). Record each outcome as `pass` / `failure` / `skipped` (with reason). Environment-dependent checks that cannot run must be **`skipped`**, never a silent pass. Write machine-readable artefacts under `artifacts/pre-release/` when a script does so (that directory is gitignored).

### A. Always-run hygiene (no Docker required)

```bash
bash scripts/release/stale_refs.sh
bash scripts/release/assert_compose_bind.sh
python3 scripts/release/check_tracked_data.py
bash scripts/secrets_check.sh
PYTHONPATH=src python3 -c "import re, pathlib, transcriptx; t=pathlib.Path('pyproject.toml').read_text(); m=re.search(r'^version\\s*=\\s*\"([^\"]+)\"', t, re.M); assert m and m.group(1)==transcriptx.__version__, (m.group(1) if m else None, transcriptx.__version__); print(transcriptx.__version__)"
```

Use `PYTHONPATH=src` so the check reads the tree under release, not a stale site-packages install.

Expected: each script prints `OK` / exits 0. Denylist may **soft-warn** on ignored forbidden paths; that is not a hard failure unless `TRANSCRIPTX_STRICT_IGNORED_FORBIDDEN=1`.

Unit coverage for helpers:

```bash
python -m pytest -q tests/release/test_wave0_release_hygiene.py
```

### B. Config 1.7 / inventory parity evidence

```bash
python -m pytest -q \
  tests/core/config/test_file_overrides_atomicity.py \
  tests/core/config/test_registry_ownership.py \
  tests/core/config/test_nested_file_overrides_probe.py \
  tests/core/config/test_settings_file_load_pilots.py
```

Expected: green. Ownership invariant (authoritative): **47 pilots / 660 Pydantic leaves / 16 legacy** (676 total) via `test_ownership_invariant_counts`. Behaviour matrix: `docs/dev/../archive/plans/file_override_behaviour_matrix.md`.

### C. Dependency / clean-env audit (optional locally; required for tag when tooling available)

```bash
bash scripts/release/clean_env_audit.sh
```

Expected: `pass`, or `skipped` with reason (missing `build` / network / host blockers). Host `pip install '.[full]'` is **not** required for Wave 0 when platform blockers apply — see `docs/dev/dependency_audit.md`. Attach waiver rows for any accepted CVEs.

### D. Docker smoke + image audit (optional locally; required for tag when Docker available)

```bash
docker compose -f docker-compose.yml build
make docker-smoke
bash scripts/release/image_pip_check.sh
```

Expected: `pass`, or `skipped (Docker not available)`.

### E. Install-matrix cells

Execute the cells claimed in `docs/runtime/install_verification_matrix.md` (core extras, Docker production-image proof, Python 3.10–3.12 as practical). Record pass/fail/skip per cell; do not claim a cell green without evidence.

### F. CI on exact commit

Confirm GitHub Actions on the intended SHA: jobs `tests` (3.10–3.12), `compose-config`, and `release-checks` are green. Failed or cancelled matrix members block tagging.

### Bundle contents checklist

| Artefact | Command / source | Location / note |
|----------|------------------|-----------------|
| Stale refs | `scripts/release/stale_refs.sh` | stdout / CI log |
| Compose bind | `scripts/release/assert_compose_bind.sh` | stdout / CI log |
| Tracked data | `scripts/release/check_tracked_data.py` | stdout / CI log |
| Secrets + denylist | `scripts/secrets_check.sh` | stdout / CI log |
| Package version | pyproject ↔ `transcriptx.__version__` | stdout |
| Config atomicity + ownership | pytest commands in §B | pytest log |
| Clean-env audit | `scripts/release/clean_env_audit.sh` | `artifacts/pre-release/` when produced |
| Image pip check | `scripts/release/image_pip_check.sh` | stdout / artefacts |
| Docker smoke | `make docker-smoke` | stdout |
| Install matrix | manual / scripted per matrix doc | notes attached at tag |
| CI | Actions on exact SHA | link or run IDs |
