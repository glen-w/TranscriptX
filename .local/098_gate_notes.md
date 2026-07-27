# 0.9.8 gate notes (local)

## Passed
- targeted epoch/packaging clusters
- make test-smoke
- make test-contracts
- make test-fast (7713 passed, 3 skipped)
- clean base wheel install (`transcriptx-0.9.8`) + import/enumerate; bertopic/hdbscan/umap not imported
- A14: default suite via `make test-fast`; collection 7716/7894 (178 deselected)
- version consistency: pyproject / root / web / CHANGELOG `0.9.8`

## Documented skips (not cut blockers)
| Item | Repro | Frequency | Owner | Severity | 0.9.8 caused? |
|------|-------|-----------|-------|----------|---------------|
| Host `[bertopic]` clean-wheel | `pip install wheel[bertopic]` in fresh venv | this Mac (llvmlite source build fails) | packaging | known limitation — matrix already documents; Docker/`requirements.txt` remain fuller-stack proof | No — expected host gap that motivated BERTopic-out-of-base |
| `make image_pip_check` | target missing; use `make docker-smoke` / image scripts | this session | release | use Docker smoke/image proof at tag time | No — Makefile naming |
| packaging `missing_extra` skip when bertopic present in dev env | `pytest tests/packaging/test_bertopic_boundary.py` | when extra installed | packaging | covered by base-wheel probe | No |
