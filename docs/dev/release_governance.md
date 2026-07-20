# Release governance (manual next-tag checklist)

This document is the **authoritative release gate** for public version tags. It is **not** enforced by `.cursor/commands/pre-release.md` (local developer confidence only).

**Do not create the next version tag until every item below is green.**

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

Humans (or an explicit user instruction outside the pre-release command) perform tag/push after this checklist is satisfied.

## Release-evidence bundle

Attach (machine- or human-readable) at tag time:

- Stale-reference sweep (`scripts/release/stale_refs.sh`)
- Dependency audit + installed-package inventory (clean-env and, where practical, image)
- Documented-install matrix results
- Tracked-data allowlist comparison (`scripts/release/check_tracked_data.py`)
- Secrets and denylist results
- Package-version check
- Canonical Compose assertions (`scripts/release/assert_compose_bind.sh`)
- Docker smoke result after fresh build
- Config 1.7 inventory / parity evidence
