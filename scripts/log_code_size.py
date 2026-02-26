#!/usr/bin/env python3
"""
Append current date and code size to code_size.log (gitignored).
Run from repo root: python scripts/log_code_size.py
"""
from pathlib import Path
import re
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = REPO_ROOT / "code_size.log"

# Directories to count (relative to repo root)
INCLUDE_DIRS = ("src", "config", "scripts")
# File extensions to count as code
CODE_EXTENSions = (".py", ".yml", ".yaml", ".toml", ".md", ".json", ".sh", ".sql")
# Exclude patterns (path segments)
EXCLUDE = ("__pycache__", ".git", "node_modules", ".venv", "archived", ".egg-info", "build", "dist")


def is_excluded(rel_path: Path) -> bool:
    for part in rel_path.parts:
        if part in EXCLUDE or part.startswith("."):
            return True
    return False


def count_lines(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return len(text.splitlines())
    except Exception:
        return 0


def main() -> None:
    total_lines = 0
    total_files = 0
    for dir_name in INCLUDE_DIRS:
        base = REPO_ROOT / dir_name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(REPO_ROOT)
            if is_excluded(rel):
                continue
            if path.suffix not in CODE_EXTENSions and path.name not in ("Dockerfile", "Dockerfile.ui", "Dockerfile.whisperx"):
                continue
            total_lines += count_lines(path)
            total_files += 1

    # Also count key root files
    for name in ("pyproject.toml", "requirements.txt", "constraints.txt", "pytest.ini", "Dockerfile", "Dockerfile.ui", "Dockerfile.whisperx"):
        p = REPO_ROOT / name
        if p.is_file():
            total_lines += count_lines(p)
            total_files += 1

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"{now}\t{total_lines}\t{total_files}\n"
    LOG_PATH.open("a").write(line)
    print(f"Appended to {LOG_PATH.name}: {now}  lines={total_lines}  files={total_files}")


if __name__ == "__main__":
    main()
