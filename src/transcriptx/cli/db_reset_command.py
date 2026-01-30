"""
Dev-only database reset command.
"""

from __future__ import annotations

import os
from pathlib import Path

from transcriptx.core.utils.paths import PROJECT_ROOT
from transcriptx.core.utils.logger import get_logger
from transcriptx.database.database import get_database_manager, get_database_url
from transcriptx.database.migrations import run_migrations
from transcriptx.database.models import Base

logger = get_logger()


def _is_safe_db_url(database_url: str) -> bool:
    if database_url.startswith("sqlite"):
        db_path = database_url.replace("sqlite:///", "")
        try:
            db_path = str(Path(db_path).resolve())
            return db_path.startswith(str(PROJECT_ROOT))
        except Exception:
            return False
    return False


def reset_database(force: bool = False) -> None:
    """
    Reset the database (dev-only).
    """
    env = os.getenv("TRANSCRIPTX_ENV", "").lower()
    db_url = get_database_url()

    if not force and env != "dev" and not _is_safe_db_url(db_url):
        raise RuntimeError(
            "Database reset is only allowed in dev mode or for local SQLite DB under project root."
        )

    manager = get_database_manager()
    if not manager.engine:
        manager.initialize()

    Base.metadata.drop_all(bind=manager.engine)
    Base.metadata.create_all(bind=manager.engine)
    run_migrations()
    logger.info("✅ Database reset completed")
