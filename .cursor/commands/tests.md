Review and Expand Test Suite (# tests)

Review the TranscriptX test suite for health, coverage gaps, and quarantined/skipped tests; then propose and, where safe, implement targeted test expansions.

Execute from the workspace root.

⸻

0. Run backup first (mandatory)

Before doing anything else, run the backup custom command (# backup). Wait for it to complete, then proceed.

⸻

1. Operating rules

Primary goal: improve test confidence without broad production refactors.

* Bias toward tests-only changes.
* Do not run destructive clean-test-artifacts flows.
* If production-code changes appear necessary, stop and report the proposed fix unless it is a trivial import/path compatibility correction.
* If the default suite is failing before changes, do not expand tests until failures are understood and classified.
* Do not re-enable quarantined tests by default.
* New tests must not be marked quarantined, slow, requires_docker, requires_ffmpeg, requires_models, or requires_api unless explicitly justified.
* Keep default test runs fast and offline.

⸻

2. Test Artifact Cleanup

Cleanup is disabled.

Do not run destructive cleanup flows. Only report that cleanup is disabled unless explicitly requested to run a preview-only cleanup audit with a documented script.

⸻

3. Review Phase

3.1 Run and summarize current suite

Run:

pytest –co -q
pytest -q

If debugging a failure, use:

pytest -x

Report:

* Total collected tests
* Passed / failed / skipped / xfailed / xpassed
* Collection errors or import failures
* Whether baseline is green before adding tests

Optional full collection comparison:

pytest –co -q -m “”

Compare with tests/TEST_SUITE_ASSESSMENT.md if it notes an expected count (e.g. ~1558 tests).

⸻

3.2 Structure and markers

List test directories under tests/, including where present:

analysis, contracts, core, integration, io, pipeline, regression, services, smoke, unit, utils, web

Inspect pytest.ini.

Confirm markers including, where present:

smoke, unit, integration, contract, slow, requires_models, requires_docker, requires_ffmpeg, requires_api, quarantined, integration_core, integration_extended

Confirm default addopts excludes heavy/quarantined/API/model tests, especially:

quarantined, requires_ffmpeg, requires_docker, requires_models, requires_api, slow, integration

⸻

3.3 Quarantined and skipped tests

Read:

tests/TEST_SUITE_ASSESSMENT.md

Identify:

* Quarantined files and reasons
* Skipped-at-collection files (missing modules, obsolete imports, etc.)
* Tests skipped due to removed modules or API changes
* Quarantined tests that are candidates for update-or-remove

Report:

* Number of quarantined tests/files
* Number of skipped-at-collection files
* Whether quarantined tests should remain quarantined, be updated, or be removed

Do not re-enable quarantined tests unless updated to current APIs and passing.

⸻

3.4 Coverage and gaps

If coverage is available and reasonable, run:

pytest --cov=src --cov-config=.coveragerc --cov-fail-under=0 --cov-report=term-missing --cov-report=json:coverage.json -q -m "not quarantined and not smoke and not release_only and not integration and not integration_core and not integration_extended and not requires_ffmpeg and not requires_docker and not requires_models and not requires_api and not slow"

If full coverage is too slow/noisy, run targeted coverage:

pytest tests/core tests/pipeline tests/contracts –cov=src/transcriptx/core –cov-report=term-missing -q

If coverage cannot be run, manually compare src/ packages to tests/.

Focus on high-leverage areas:

* Config lifecycle
* Validation
* Module registry
* Transcript loader
* Pipeline run / DAG execution
* State persistence
* Output builder
* Manifest/run outcome contracts
* Artifact invariants

Report which areas already have tests and which lack coverage.

⸻

4. Expansion Phase

Only proceed if the baseline is green, or if baseline failures are unrelated and clearly documented.

4.1 Prioritize expansion targets

Prefer, in order:

1. Critical paths with minimal or no tests (config, validation, pipeline, state, registry, loader)
2. New or refactored code without tests
3. Contract tests for output shapes, manifest semantics, run outcomes, artifact invariants
4. Stable integration tests (integration_core) that do not require external dependencies

Avoid broad end-to-end tests unless explicitly requested.

⸻

4.2 Add or extend tests

Use existing patterns and fixtures where possible.

Locations:

* Unit: tests/unit/, tests/core/, tests/core/utils/, tests/io/
* Integration: tests/integration/core/
* Contract: tests/contracts/

Reference patterns:

tests/unit/test_high_leverage.py
tests/integration/core/test_high_leverage_integration.py

Add small, focused tests. Examples:

* Config lifecycle behavior is deterministic
* Validation rejects malformed input with explicit errors
* Registry enforces uniqueness and schema correctness
* Loader handles missing/partial data safely
* Pipeline preserves canonical status vocabulary
* Manifest loader enforces schema versioning
* Output builder uses stable naming independent of artifact presence

⸻

4.3 Style and constraints

* File names: test_*.py
* Classes: Test*
* Functions: test_*
* Markers: @pytest.mark.unit, @pytest.mark.contract, @pytest.mark.integration_core

Tests must be:

* Offline
* Deterministic
* Small and fast
* Independent
* tmp_path-based when filesystem is involved

Avoid dependencies on:

* Absolute paths
* Wall-clock timing
* Network access
* External services
* Models / Docker / FFmpeg

⸻

5. Validation

After changes:

pytest -q

Optional:

pytest -m “integration_core” -q

If coverage was used, rerun relevant coverage command.

Report changes:

git diff –stat
git diff –name-only

Clearly separate production-code changes from test/doc changes.

⸻

6. Optional documentation update

If high-leverage tests were added, update:

tests/TEST_SUITE_ASSESSMENT.md

Add a brief note under:

* High-leverage tests added
* Recommendations
* Coverage gaps reduced
* Quarantine notes

⸻

7. Execution summary

Provide:

1. Review

* Suite status
* Collection counts
* Pass/fail/skip summary
* Collection/import errors
* Structure and markers
* Quarantined/skipped summary
* Coverage or gap analysis

2. Expansion

* Files added or modified
* Tests added or extended
* Targeted high-leverage areas
* Status of quarantined tests

3. Result

* Final pytest -q result
* Optional integration_core result
* Optional coverage result
* git diff –stat
* Note of any production-code changes

⸻

## Canonical gate commands

- Default fast coverage gate:
  - `pytest -q --cov=src --cov-config=.coveragerc --cov-fail-under=0 --cov-report=term-missing --cov-report=json:coverage.json -m "not quarantined and not smoke and not release_only and not integration and not integration_core and not integration_extended and not requires_ffmpeg and not requires_docker and not requires_models and not requires_api and not slow"`
- Integration gate:
  - `pytest -q tests/integration -m "not quarantined and (integration or integration_core or integration_extended) and not requires_ffmpeg and not requires_docker and not requires_models and not requires_api and not release_only"`
- Smoke gate:
  - `pytest -q tests/smoke -m "smoke and not quarantined and not requires_ffmpeg and not requires_docker and not requires_models and not requires_api and not slow and not release_only"`
- Release-only gate:
  - `pytest -q tests/release -m "release_only and not quarantined"`