# prune

Run a workspace cleanup to free disk space. Do the following in order:

## 1. Docker

- **Prune unused images**
  `docker image prune -a -f`
  Optional (only remove images older than 7 days):
  `docker image prune -a -f --filter "until=168h"`
- **Prune build cache**
  `docker builder prune -f`
- **Optionally prune unused volumes**  
  Only if the user is okay losing unused volumes:
  `docker volume prune -f`

## 2. Python caches and artifacts

- **Remove __pycache__ directories**
  `find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null`
- **Remove .pytest_cache**
  `find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null`
- **Remove .mypy_cache**
  `find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null`
- **Remove .ruff_cache**
  `find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null`
- **Remove *.egg-info and *.egg directories**
  `find . -type d \( -name "*.egg-info" -o -name "*.egg" \) -exec rm -rf {} + 2>/dev/null`
- **Remove dist/ and build/ at repo root (if present)**
  `rm -rf dist build 2>/dev/null`

## 3. Other artifacts

- **Remove .coverage**
  `rm -f .coverage 2>/dev/null`
- **Remove htmlcov/**
  `rm -rf htmlcov 2>/dev/null`
- **Remove .tox (tox test envs, if present)**
  `rm -rf .tox 2>/dev/null`
- **Optionally clear pip download cache**  
  Only if explicitly requested: `pip cache purge`

## Execution rules

- Run from the workspace root.
- Do not perform any step requiring network access.
- Skip **docker volume prune** and **pip cache purge** unless the user explicitly asks for an aggressive or “everything” prune.
- After running, summarize what was removed or confirm that cleanup completed successfully.
