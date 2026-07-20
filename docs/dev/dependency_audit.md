# Dependency audit & CVE waiver policy

TranscriptX Wave 0 audit gate:

1. **Clean environment** with the **built wheel + core dependencies**: `pip check` + `pip-audit`
2. **Freshly built Docker production image**: `pip check` inside the image
3. Host `pip install '.[full]'` is **not** required for Wave 0 when platform blockers (e.g. llvmlite) apply

Scripts:

- `scripts/release/clean_env_audit.sh`
- `scripts/release/image_pip_check.sh`

Artefacts land under `artifacts/pre-release/` (gitignored).

## Fixable CVE policy

Any CVE with a **published fix** **blocks the next public tag** unless an exceptional, time-bounded waiver below is complete and approved.

### Waiver schema (required fields)

| Field | Description |
|-------|-------------|
| CVE | CVE identifier |
| Package / version | Affected package and installed version |
| Rationale | Why the tag may proceed |
| Compensating controls | Mitigations in place |
| Owner | Responsible person |
| Issue reference | Tracking issue URL or id |
| Review date | When the waiver must be re-reviewed |
| Explicit approval | Named approver + date |

### Active waivers

_None._

### No-fix CVEs

Document as warnings with owner + review date. Do not silently ignore.

| CVE | Package | Owner | Review date | Notes |
|-----|---------|-------|-------------|-------|
| — | — | — | — | — |
