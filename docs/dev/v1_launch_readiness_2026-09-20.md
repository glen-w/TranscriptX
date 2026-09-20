# v1 launch readiness snapshot (2026-09-20)

Maintainer/agent prep pass on package **0.9.9.5**. Not a 1.0 tag — programme gates
in [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) still require
unfamiliar-user validation and RC evidence. This note records what was verified,
fixed, and left open.

## Verdict

**Codebase is close to RC-ready on automated gates**, with residual owner-gated
and human-validation work still blocking the public **1.0** tag.

| Gate | Status |
|------|--------|
| Wave 0 hygiene / secrets / stale refs | Pass (after packages.md caveat + review path redaction) |
| SR-01 / SR-02 path traversal | Fixed (2026-09-02); review docs synced |
| SR-07 temp audio cleanup | Fixed this pass + failure-injection tests |
| Clean-env `pip check` | Pass |
| Clean-env `pip-audit` | One **no-fix** finding: nltk 3.10.3 / CVE-2026-81726 (no PyPI fix yet) — [dependency_audit.md](dependency_audit.md) |
| Smoke + previously red fast-lane failures | Pass |
| Fast suite (Gate B) | **8475 passed** after fixing names/module/icon/hygiene flakes. One intermittent `hypothesis.FlakyFailure` on `test_normalize_property_dedupe_and_limits` when `speechbrain` is installed (lazy `k2` import during Hypothesis module introspection) — passes in isolation; not a product defect. |
| Docker image build / image pip-check | Skipped (Docker unavailable in this environment) |
| Unfamiliar-user round | Open (mandatory) |
| RTD project slug | Owner-gated |
| Owner local folder cleanup | Owner machine (not product) |

## Fixes landed this pass

- Pin tightening: `beautifulsoup4==4.15.0`, `ebooklib==0.20`, `rapidfuzz`/`webrtcvad` upper bounds in `pyproject.toml` + `requirements.txt`
- `.dockerignore`: exclude `.venv`, `venv`, `.transcriptx`, `artifacts`, `.local`, `website`
- Compose: `security_opt: no-new-privileges:true`
- Names module completeness: group aggregation, pydantic goldens, UI pin order, Overview “Open profile” icon
- Flaky tests: whispermlx JSON discovery mtimes; cleanup signature size+mtime change
- Docs honesty: install caveat, security/architecture review status sync, owner-path redaction in host-compat review

## Still open before public 1.0 (severity)

**Must fix / evidence (programme)**

1. Unfamiliar-user clean-room round ([unfamiliar_user_validation_1_0.md](unfamiliar_user_validation_1_0.md))
2. Fresh clean-install matrix + Docker production image audit on release hardware
3. RC rehearsal on exact commit ([release_governance.md](release_governance.md))
4. Re-run `pip-audit` when nltk ≥3.10.4 (or successor) publishes; clear no-fix row

**May ship as known limitation / post-1.0**

- SR-04 profile import/export raw paths (local-operator power surface)
- SR-05 dynamic HTML escaping (exported reports highest risk)
- SR-06 LLM arbitrary HTTP destinations (document + warn; allowlist later)
- SR-08–SR-12 supply-chain / digest pins / privacy egress profile
- Overview hierarchy + Charts catalogue residuals
- Theme C depth beyond default-on Speaker ID CCv2

## Efficiency notes

- Dockerfile already multi-stage, pip cache mounts, runtime without pip — solid.
- Context hygiene improved via `.dockerignore` (local venvs and website no longer enter build context).
- Playwright OS libs in the production image remain large; acceptable for maps PNG; revisit if image size becomes a release pain.
- `requirements-lock.txt` is a partial/stale freeze (pydantic 2.11.7 vs project 2.9.2) and is **not** used by Docker — prefer `constraints.txt` + `requirements.txt` + `uv.lock` for reproducibility narratives.

## Suggested next owner actions

1. Local corpus folder cleanup (ROADMAP **Now**)
2. Recruit unfamiliar-user cohort and run the kit
3. On a Docker-capable host: `docker compose build` → `make docker-smoke` → `image_pip_check.sh`
4. When nltk fix ships: bump pin, re-run `clean_env_audit.sh`, drop no-fix row
5. Cut `1.0.0-rc.1` only when blockers above are green
