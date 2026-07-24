Type: PRODUCT
Authority: self

# Release operations and support (1.0)

**Status:** drafted (**0.9.7**); publish with public 1.0 tag  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) §17  
**Extends:** [release_governance.md](release_governance.md)  
**Severity:** [release_severity_triage_1_0.md](release_severity_triage_1_0.md)

Define the maintenance promise so it matches the strength of contracts and release governance.

## Supported install profiles and platforms

Authoritative matrix: [install_profiles_matrix.md](install_profiles_matrix.md).

- **Recommended:** Docker full analysis (+ optional host Ollama).
- **Candidate:** Native full / native + Ollama — confirm on RC clean-env soak.
- **Optional:** Voice / speaker-match extras.
- **Python:** versions declared in `pyproject.toml` / CI; document the intersection that passes release CI.
- **OS:** macOS and Linux for supported Docker/native cells; Windows best-effort unless a matrix cell says otherwise.

## CHANGELOG and migration notes

- Keep [CHANGELOG.md](../../CHANGELOG.md) in Keep a Changelog form.
- Each 0.9.x / 1.0 cut: Added / Changed / Fixed / Removed as applicable.
- Schema or storage behaviour changes require an explicit **migration note** (epoch stores, demo pack, redirect removals).
- Do not invent PyPI install instructions while distribution is Git/Docker.

## RC naming and duration

- Tags: `v1.0.0-rc.N` (integer N starting at 1).
- Default soak: **≥7 days** or until severity backlog is clear of blockers/must-fix — whichever is longer — unless release governance tightens this.
- RC may start when product gates pass even if ops polish continues; the **public 1.0 tag** requires this policy published.

## Branch / tag convention

- Integration branch: `main` (or the repository default).
- Release tags: `vMAJOR.MINOR.PATCH` and `vMAJOR.MINOR.PATCH-rc.N`.
- Do not rewrite published tags.

## Release artifacts and checksums

- Prefer GitHub Release attaching: source archive, optional Docker image digest note, CHANGELOG excerpt.
- Record image digests (`docker images --digests`) in the release-evidence bundle ([release_governance.md](release_governance.md)).
- Checksums: publish SHA-256 for attached archives when cutting public 1.0.

## Issue reporting

- Use GitHub Issues with the templates under `.github/ISSUE_TEMPLATE/`.
- Security-sensitive reports: **GitHub private vulnerability reporting** only — see [SECURITY.md](../../SECURITY.md). Do not file public Issues for vulns.

## Support expectations (1.0.x)

- Best-effort maintainer response on GitHub for supported profiles.
- No SLA / paid support in 1.0 scope.
- Unsupported profiles and experimental modules may be closed as known limitations.

## Patch-release policy

- 1.0.x patches: blockers, must-fix regressions, security fixes, documentation corrections.
- No new analysis modules in patch releases unless required to repair a release-critical journey.
- Known limitations stay documented rather than silently “fixed” by removing features.

## Deprecation

- Public schema IDs and epoch-1 stores: **no renumber/reuse** after 1.0 (schema epoch policy).
- Public Python surfaces (`app.workflows`, managed import): deprecate with CHANGELOG notice and a minimum **one minor** (1.x) migration window before removal unless a security blocker forces faster action.

## Rollback

- Prefer previous Docker image tag / previous Git tag.
- Epoch-1 data roots must open on later 1.0.x; rolling back application code is safe when schemas are unchanged.
- If a bad 1.0 build writes corrupt derived state: stop, restore from user backup, open an advisory; do not auto-delete user transcripts.

## Checklist

- [x] Supported install profiles and OS/hardware matrix (link install_profiles_matrix)
- [x] How users report issues (GitHub templates); maintainer expectations
- [x] Security reporting (SECURITY.md)
- [x] Rollback / downgrade expectations (epoch stores; Docker tags)
- [x] Deprecation policy for public schemas and surfaces after 1.0
- [x] Compatibility promise for epoch-1 data roots across 1.0.x
- [ ] Owner confirms RC duration / security contact channel if different from SECURITY.md defaults

## Non-goals

- SLA / paid support
- Multi-tenant hosted operations
