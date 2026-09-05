# AGENTS.md

Repo-specific guidance for agents. For product/architecture/contracts, start at `README.md`,
`docs/ARCHITECTURE.md`, and `docs/CONTRACT_INDEX.md`. For install/run details, see
`docs/runtime/installation.md` and `docs/dev/CONTRIBUTING.md`.

## Cursor Cloud specific instructions

TranscriptX is a local-first transcript analysis workbench. The primary surface is a
**Streamlit GUI**; there is also a **Python API** (`transcriptx.app.workflows`) and a
managed-import workflow. There is no long-running backend beyond the Streamlit process.

### Environment (already provisioned in the VM snapshot)

- **Python 3.10 is canonical.** The Dockerfile uses `python:3.10-slim` and the pinned deps in
  `requirements.txt` only resolve on 3.10/3.11 (e.g. `wordcloud==1.9.2` has no cp3.12 wheel and
  fails to build on Python 3.12). Do not use the system `python3` (3.12) for this project.
- System packages baked into the snapshot (installed via `apt`, not the update script): the
  deadsnakes `python3.10` + `python3.10-venv`/`-dev`, `libsndfile1-dev` (soundfile/opensmile),
  `libgomp1` (tokenizers), and `ffmpeg` (audio modules). These match the Dockerfile's build/runtime libs.
- Dependencies live in the project venv at **`/workspace/.venv`** (Python 3.10). Use
  `. .venv/bin/activate` or call binaries directly, e.g. `.venv/bin/python`, `.venv/bin/pytest`.
- The update script refreshes deps only: `requirements.txt` (full functional stack, incl. torch,
  spaCy, streamlit, bertopic) + `pip install -e ".[dev]"` (test/lint tools) + `hypothesis`.
- **`hypothesis` is an undeclared test dependency** required for `make test-fast` collection
  (imported by `tests/core/analysis/llm_custom_qa/test_plan_coverage.py`); the update script installs it.
- NLP model data is **pre-downloaded into the snapshot**, not the update script: spaCy
  `en_core_web_md` + `en_core_web_sm`, NLTK `vader_lexicon`/`punkt`/`punkt_tab`/`cmudict`, and
  TextBlob corpora. If any are missing, re-fetch using the commands in the `Dockerfile`.

### Running the app

- GUI (primary): `python -m transcriptx.web --host 0.0.0.0 --port 8501` (console script:
  `transcriptx`). Opens at `http://localhost:8501`. Flags/env: `--host`/`--port`,
  `TRANSCRIPTX_HOST`/`TRANSCRIPTX_PORT`.
- Point the app at writable, out-of-repo dirs so runs don't pollute the tree:
  `TRANSCRIPTX_DATA_DIR` (library) and `TRANSCRIPTX_OUTPUT_DIR` (run outputs). Analysis runs can
  write >100 MB of artifacts per run.
- **First-run gotcha:** starting the app against a fresh/empty `TRANSCRIPTX_DATA_DIR` (or one seeded
  only via the Python API) shows a "Data directory needs an update" screen because the schema-epoch
  marker is missing. Create the fresh data dir / confirm the reset in the UI to proceed — this is
  expected first-run behavior, not a crash.
- Python API hello-world (import + analyze) is in `README.md`; `run_analysis(AnalysisRequest(...))`
  returns `success`/`status`/`errors` and writes artifacts under the output dir.

### Tests, lint, build

- Standard commands live in the `Makefile` and CI (`.github/workflows/ci.yml`). Common ones:
  `make test-smoke` (fast CI gate, ~1.5 min), `make test-fast` (full fast lane), `make test-contracts`,
  `make docs` (needs `.[docs]`). Run from repo root with the venv active.
- Lint: `flake8`, `black`, and `mypy` come from `.[dev]`. Note there is no `.flake8`/`setup.cfg`, so
  bare `flake8` uses its 79-char default while the code targets black's 88. The **authoritative lint
  gate is pre-commit**, whose config is at the non-default path `config/.pre-commit-config.yaml`
  (pinned `black 23.12.1`, `ruff 0.1.6`, `mypy 1.8.0`); run it with
  `pre-commit run -a -c config/.pre-commit-config.yaml`. `ruff` is only provided via pre-commit, not `.[dev]`.
- **Known pre-existing `make test-fast` failures (NOT environment problems):** ~36 tests fail because
  committed golden snapshots embed machine-specific values — the original author's absolute paths
  (`/Users/89298/Documents/transcriptx/...`, e.g. `tests/core/config/test_pydantic_bridge_drift.py`)
  and a fixed `torch_version` (`2.2.2`, e.g. `tests/unit/test_emotion_family_characterization.py`).
  These fail on any other machine / newer torch and are unrelated to setup. Smoke gate is green.
