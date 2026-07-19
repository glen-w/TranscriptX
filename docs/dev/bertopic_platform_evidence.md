"""Platform install evidence for BERTopic optional stack.

Blocking matrix (from BERTopic re-enable plan):

| Platform | Python | Role | Status |
|----------|--------|------|--------|
| Linux x86_64 | 3.10 | Blocking | pending — run in release env |
| Linux x86_64 | 3.11 | Blocking | pending — run in release env |
| Linux x86_64 | 3.12 | Blocking | pending — run in release env |
| macOS Apple Silicon (arm64) | 3.11 | Blocking | pending — run in release env |
| macOS Apple Silicon | 3.10 / 3.12 | Non-blocking | optional |
| macOS Intel | any | Non-blocking | not required |

Per platform run, record:

1. `python -V`, `uname -m`
2. Fresh venv + `pip install <wheel-or-sdist>` (bertopic stack is in base; `[bertopic]` is a compat alias)
3. Whether HDBSCAN/UMAP installed from **wheel** or **source**
4. `pip check`
5. Smoke: `python -c "from bertopic import BERTopic; ..."` and optional real-model fit
6. Significant warnings triage

Default CI asserts the stack is in base deps and catalogue isolation still holds (see
`tests/packaging/test_extras_metadata.py`, `tests/contracts/test_bertopic_optional_extra.py`).

This environment (dev workstation) did not complete the full blocking matrix;
code + default-lane tests ship with that gap documented.
