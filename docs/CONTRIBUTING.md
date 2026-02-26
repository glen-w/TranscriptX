# Contributing to TranscriptX

This document covers contribution workflow and how to keep documentation in sync with the codebase.

## Documentation sync checklist

To avoid drift between the CLI, Docker setup, and docs, use this checklist when changing CLI commands, compose files, or architecture:

1. **Regenerate and review `--help` output**  
   Run `transcriptx --help` and `transcriptx <command> --help` for any changed commands. Update [docs/CLI.md](CLI.md) so flags and options match exactly. Do not document internal-only parameters.

2. **Verify README examples**  
   Ensure installation (pip/venv and Docker), CLI examples, and “golden path” commands in [README.md](../README.md) are runnable with the current code.

3. **Verify Docker examples**  
   Ensure [docs/docker.md](docker.md) and README Docker sections match [docker-compose.yml](../docker-compose.yml) (service names, volume paths, ENTRYPOINT usage). Any reference to `docker-compose.whisperx.yml` or profiles should match the repo.

4. **Confirm no deleted commands are referenced**  
   Search docs and README for command names and flags that have been removed or renamed; remove or update those references.

5. **Confirm version consistency**  
   If the package version is displayed anywhere (e.g. in docs or image labels), it should match [pyproject.toml](../pyproject.toml) `version`.

Keep this process lightweight and manual unless a small local helper (e.g. script that runs `--help` and diffs) is clearly justified.

## Source of truth

- **CLI flags and options** — `transcriptx` and `transcriptx <command> --help` output.
- **Docker behavior** — Compose files and Dockerfile(s) in the repo.
- **Architecture and module layout** — Current `src/transcriptx/` layout and [ARCHITECTURE.md](ARCHITECTURE.md).

## Development and testing

See [developer_quickstart.md](developer_quickstart.md) for pipeline structure, adding analysis modules, and testing. Run tests from the repo root (e.g. `pytest`); see `tests/README.md` and the Makefile for CI and smoke tests.
