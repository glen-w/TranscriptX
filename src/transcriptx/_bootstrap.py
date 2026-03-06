"""Env bootstrap — must be imported before any path/config modules.

Entrypoints (CLI or scripts) should call bootstrap() immediately before
importing application modules that compute path constants, so environment
overrides are loaded first.
"""

from pathlib import Path

_bootstrapped = False


def bootstrap(env_path: Path | None = None) -> None:
    """Load .env from repo root (or env_path) so TRANSCRIPTX_* env vars are set."""
    global _bootstrapped
    if _bootstrapped:
        return
    _bootstrapped = True
    try:
        from dotenv import load_dotenv

        if env_path is None:
            # Repo root: src/transcriptx/_bootstrap.py -> 3 parents up
            env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)
    except ImportError:
        pass
