Type: GUIDE
Authority: ARCHITECTURE.md

# Contributing to TranscriptX

This document covers contribution workflow and how to keep documentation in sync with the codebase.

## Documentation authority model

TranscriptX documentation is structured into explicit layers:

- **CONTRACT** — owns invariants, schemas, support policy, and rule definitions.
- **GUIDE** — owns user/developer flows and examples; may summarize contracts briefly, but may not define rules.
- **ARCHITECTURE** — owns system shape, boundaries, and extension points; defers to contracts for invariants.
- **PRODUCT** — owns roadmap, vision, and planning/status material.

Hard rules:

- Every major concept must have **one authoritative home**.
- Guides must **not** define rules.
- Architecture docs must **not** define rules.
- Runtime docs (`docs/runtime/*`) must describe **behavior and operations only**; they must **not** define invariants or support policy.
- If a GUIDE, ARCHITECTURE, or runtime doc contains normative language for storage, run truth, output layout, or support policy, you must move or delete it and replace it with a short summary plus a link to the authoritative contract.
- New rule definitions must be added to an existing contract doc whenever possible (`docs/runtime/STORAGE.md`, `docs/run_outcome_contract.md`, `docs/contracts/output-contract-v1.md`, `docs/public_surfaces.md`). Do **not** create new contract docs lightly.

## Contract authorities (single source of truth)

Each core concept has exactly one authoritative contract:

- **Storage** → `docs/runtime/STORAGE.md`
- **Run truth** → `docs/run_outcome_contract.md`
- **Outputs** → `docs/contracts/output-contract-v1.md`
- **Support surfaces** → `docs/public_surfaces.md`
- **Terminology index** → `docs/TERMS.md` (GUIDE; aggregates terms from contracts — not authoritative by itself).

When you change behavior for any of these concepts, you **must** update the corresponding contract first, then adjust guides to summarize and link to it.

## Documentation sync and failure checklist

Use this checklist when changing entrypoints, compose files, workflows, or any behavior covered by contracts.

### 1. Contract changes

If you change:

- storage layout, sidecar paths, metadata subtrees, imports, or rename behavior → update `docs/runtime/STORAGE.md`.
- run outcome semantics, allowed statuses, or precedence vs `manifest.json` and artifacts → update `docs/run_outcome_contract.md`.
- output directory layout, output naming, manifest schemas, or run_results placement → update `docs/contracts/output-contract-v1.md`.
- supported/unsupported interfaces or support policy → update `docs/public_surfaces.md`.

It is a docs failure if these changes are only described in README, runtime guides, or architecture docs without being reflected in the contracts.

### 2. Guides, architecture, and runtime docs (must not define rules)

Treat the following as **hard failure conditions** in reviews and automated checks:

- Any GUIDE or ARCHITECTURE doc that defines:
  - storage paths or layout rules,
  - sidecar or metadata subtree rules,
  - run status or run truth semantics,
  - support policy rules.
- Any runtime doc (`docs/runtime/*`) that contains invariant or rule definitions for:
  - storage paths/layout,
  - sidecars or metadata trees,
  - run status semantics or execution truth,
  - support or public-surface policy.

In all these cases, fix the doc by:

- moving the rule (if valid) into the appropriate contract, and
- replacing the original text with a ≤2-line summary and a direct link to the contract.

### 3. Entry points and examples

To avoid drift between the web launcher, Docker setup, Python API docs, and architecture docs, also check:

1. **Regenerate and review `--help` output**  
   Run `transcriptx --help` (or `python -m transcriptx.web --help`). The installed console script only launches Streamlit (`--host`, `--port`). Update [docs/generated/cli.md](generated/cli.md) so launcher flags and Python API examples match the code. Do not document removed terminal subcommands.

2. **Verify README examples**  
   Ensure installation (Docker happy path and native helper) and first-analysis steps in [README.md](../README.md) are runnable with the current code. README is a user-guide entry: outcomes, GUI labels, install, privacy. It must summarize and link to contracts instead of restating rules. Do not put schema-epoch, install-marker, or public-surfaces tables on the README.

3. **Verify Docker examples**  
   Ensure [docs/runtime/docker.md](../runtime/docker.md) and README Docker sections match [docker-compose.yml](../docker-compose.yml) (service names, volume paths, ENTRYPOINT usage). Docker docs must describe operational behavior only; detailed storage layout and output rules belong in contracts.

4. **Confirm no removed interfaces are referenced**  
   Search docs and README for old terminal subcommands (e.g. `transcriptx transcript …`, `transcriptx analyze`) and deprecated entry paths (e.g. `streamlit_app.py`, `transcriptx web-viewer`). Replace runnable examples with supported surfaces from [public_surfaces.md](../public_surfaces.md). Automated coverage: `tests/contracts/test_stale_surface_references.py`.

5. **Confirm version consistency and public-entry parity**  
   If the package version is displayed anywhere (e.g. in docs or image labels), it should match [pyproject.toml](../pyproject.toml) `version`. Keep [website/index.html](../../website/index.html) public-series badge, README outline (product → screenshot → first analysis → five workflows → install → privacy), and [docs/index.md](../index.md) Start-here toctree in sync with [USER_INDEX.md](../USER_INDEX.md). Voices: user guide vs technical reference vs maintainer — [docs_architecture_1_0.md](docs_architecture_1_0.md).

Keep this process lightweight and manual unless a small local helper (e.g. script that runs `--help` and diffs) is clearly justified.

## Source of truth

- **Storage invariants** — [docs/runtime/STORAGE.md](../runtime/STORAGE.md).
- **Run outcome semantics** — [docs/run_outcome_contract.md](../run_outcome_contract.md).
- **Output layout, manifests, run_results placement** — [docs/contracts/output-contract-v1.md](../contracts/output-contract-v1.md).
- **Public surfaces and support policy** — [docs/public_surfaces.md](../public_surfaces.md).
- **Terminology index** — [docs/TERMS.md](../TERMS.md).
 - **Contract boundary map** — [docs/CONTRACT_INDEX.md](../CONTRACT_INDEX.md).
- **Web launcher flags** — `transcriptx --help` output.
- **Docker behavior** — Compose files and Dockerfile(s) in the repo.
- **Architecture and module layout** — Current `src/transcriptx/` layout and [ARCHITECTURE.md](../ARCHITECTURE.md).
- **Import architecture rules** — [ADR-IMPORT-ORCHESTRATION.md](../ADR-IMPORT-ORCHESTRATION.md).

---

## No implicit contracts

- If a rule (invariant, requirement, or guarantee) exists, it **must** be written in a CONTRACT document.
- If a rule is not written in a CONTRACT document, it is **not** part of the system’s contract and must not be treated as such in code or guides.
- When introducing new behavior or invariants, update the appropriate CONTRACT doc first, then adjust guides, architecture, and runtime docs to summarize and link back to it.

## Import adapter contribution guardrails

When adding/changing transcript import adapters:

1. Keep adapters thin: source-legibility normalization only; semantic normalization belongs in import core.
2. Do not add vendor-name branching in orchestrator, writer, or managed workflow.
3. Do not write files from adapters.
4. Do not parse-fallback silently to other adapters after selection.
5. Treat diagnostic codes as stable contracts; code changes require explicit tests/docs updates.

## Development and testing

See [developer_quickstart.md](../developer_quickstart.md) for pipeline structure, adding analysis modules, and testing. Run tests from the repo root (e.g. `pytest`); see `tests/README.md` and the Makefile for CI and smoke tests.
