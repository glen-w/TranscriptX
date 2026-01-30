"""
Database migrations for TranscriptX.

This module provides database migration functionality using Alembic,
enabling schema versioning and evolution for the TranscriptX database.

Key Features:
- Database schema migrations
- Version control for database changes
- Automatic migration generation
- Migration rollback capabilities
- Migration status tracking

The migration system supports:
- Schema evolution over time
- Data migration and transformation
- Migration testing and validation
- Rollback to previous versions
- Migration history tracking
"""

from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from transcriptx.core.utils.logger import get_logger
from .database import get_database_manager

logger = get_logger()


class MigrationManager:
    """
    Migration manager for TranscriptX database.

    This class provides methods for managing database migrations,
    including creating, running, and rolling back migrations.

    The migration manager supports:
    - Automatic migration generation
    - Migration execution and rollback
    - Migration status checking
    - Migration history tracking
    """

    def __init__(self, alembic_cfg_path: Optional[str] = None):
        """
        Initialize the migration manager.

        Args:
            alembic_cfg_path: Path to Alembic configuration file
        """
        self.alembic_cfg_path = alembic_cfg_path or self._get_alembic_config_path()
        self.alembic_cfg = self._create_alembic_config()

        logger.info(
            f"🔧 Initialized migration manager with config: {self.alembic_cfg_path}"
        )

    def _get_alembic_config_path(self) -> str:
        """Get the path to the Alembic configuration file."""
        # Look for alembic.ini in the config directory
        project_root = Path(__file__).parent.parent.parent.parent
        config_path = project_root / "config" / "alembic.ini"

        if not config_path.exists():
            # Create default alembic.ini
            self._create_default_alembic_config(config_path)

        return str(config_path)

    def _create_default_alembic_config(self, config_path: Path) -> None:
        """Create a default Alembic configuration file."""
        logger.info("🔧 Creating default Alembic configuration...")

        # Create migrations directory
        migrations_dir = config_path.parent / "migrations"
        migrations_dir.mkdir(exist_ok=True)

        # Create alembic.ini content
        alembic_ini_content = f"""[alembic]
# path to migration scripts
script_location = {migrations_dir}

# template used to generate migration file names; The default value is %%(rev)s_%%(slug)s
# Uncomment the line below if you want the files to be prepended with date and time
# file_template = %%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s

# sys.path path, will be prepended to sys.path if present.
# defaults to the current working directory.
prepend_sys_path = .

# timezone to use when rendering the date within the migration file
# as well as the filename.
# If specified, requires the python-dateutil library that can be
# installed by adding `alembic[tz]` to the pip requirements
# string value is passed to dateutil.tz.gettz()
# leave blank for localtime
# timezone =

# max length of characters to apply to the
# "slug" field
# truncate_slug_length = 40

# set to 'true' to run the environment during
# the 'revision' command, regardless of autogenerate
# revision_environment = false

# set to 'true' to allow .pyc and .pyo files without
# a source .py file to be detected as revisions in the
# versions/ directory
# sourceless = false

# version number format
version_num_format = %04d

# version path separator; As mentioned above, this is the character used to split
# version_locations. The default within new alembic.ini files is "os", which uses
# os.pathsep. If this key is omitted entirely, it falls back to the legacy
# behavior of splitting on spaces and/or commas.
# Valid values for version_path_separator are:
#
# version_path_separator = :
# version_path_separator = ;
# version_path_separator = space
version_path_separator = os

# the output encoding used when revision files
# are written from script.py.mako
# output_encoding = utf-8

sqlalchemy.url = {get_database_manager().database_url}


[post_write_hooks]
# post_write_hooks defines scripts or Python functions that are run
# on newly generated revision scripts.  See the documentation for further
# detail and examples

# format using "black" - use the console_scripts runner, against the "black" entrypoint
# hooks = black
# black.type = console_scripts
# black.entrypoint = black
# black.options = -l 79 REVISION_SCRIPT_FILENAME

# Logging configuration
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""

        config_path.write_text(alembic_ini_content)
        logger.info(f"✅ Created Alembic configuration: {config_path}")

    def _create_alembic_config(self) -> Config:
        """Create Alembic configuration object."""
        config = Config(self.alembic_cfg_path)

        # Set the database URL
        db_manager = get_database_manager()
        config.set_main_option("sqlalchemy.url", db_manager.database_url)

        # Set the script location
        script_location = Path(self.alembic_cfg_path).parent / "migrations"
        config.set_main_option("script_location", str(script_location))

        return config

    def init_migrations(self) -> None:
        """
        Initialize the migration system.

        This method:
        - Creates the migrations directory
        - Initializes Alembic
        - Creates the initial migration
        """
        logger.info("🔧 Initializing migration system...")

        try:
            # Initialize Alembic
            command.init(self.alembic_cfg, "migrations")
            logger.info("✅ Alembic initialized")

            # Create initial migration
            self.create_initial_migration()

        except Exception as e:
            logger.error(f"❌ Failed to initialize migrations: {e}")
            raise

    def create_initial_migration(self) -> None:
        """Create the initial migration with all current models."""
        logger.info("🔧 Creating initial migration...")

        try:
            # Generate initial migration
            command.revision(
                self.alembic_cfg, message="Initial migration", autogenerate=True
            )

            logger.info("✅ Initial migration created")

        except Exception as e:
            logger.error(f"❌ Failed to create initial migration: {e}")
            raise

    def create_migration(
        self, message: str, autogenerate: bool = True
    ) -> Optional[str]:
        """
        Create a new migration.

        Args:
            message: Migration message
            autogenerate: Whether to auto-generate migration from model changes

        Returns:
            Migration revision ID or None if failed
        """
        logger.info(f"🔧 Creating migration: {message}")

        try:
            if autogenerate:
                command.revision(self.alembic_cfg, message=message, autogenerate=True)
            else:
                command.revision(self.alembic_cfg, message=message)

            # Get the latest revision
            script_dir = ScriptDirectory.from_config(self.alembic_cfg)
            latest_revision = script_dir.get_current_head()

            logger.info(f"✅ Created migration: {latest_revision}")
            return latest_revision

        except Exception as e:
            logger.error(f"❌ Failed to create migration: {e}")
            return None

    def run_migrations(self, target: Optional[str] = None) -> bool:
        """
        Run database migrations.

        Args:
            target: Target revision (defaults to latest)

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"🔧 Running migrations to target: {target or 'latest'}")

        try:
            command.upgrade(self.alembic_cfg, target or "head")
            logger.info("✅ Migrations completed successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to run migrations: {e}")
            return False

    def rollback_migration(self, target: str) -> bool:
        """
        Rollback to a specific migration.

        Args:
            target: Target revision to rollback to

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"🔧 Rolling back to migration: {target}")

        try:
            command.downgrade(self.alembic_cfg, target)
            logger.info(f"✅ Rollback completed to: {target}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to rollback migration: {e}")
            return False

    def get_current_revision(self) -> Optional[str]:
        """
        Get the current database revision.

        Returns:
            Current revision ID or None if not available
        """
        try:
            from alembic.migration import MigrationContext
            from sqlalchemy import create_engine

            db_manager = get_database_manager()
            engine = create_engine(db_manager.database_url)

            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                return context.get_current_revision()

        except Exception as e:
            logger.error(f"❌ Failed to get current revision: {e}")
            return None

    def get_migration_history(self) -> list:
        """
        Get migration history.

        Returns:
            List of migration information
        """
        try:
            script_dir = ScriptDirectory.from_config(self.alembic_cfg)
            revisions = script_dir.walk_revisions()

            history = []
            for revision in revisions:
                history.append(
                    {
                        "revision": revision.revision,
                        "down_revision": revision.down_revision,
                        "message": revision.message,
                        "date": revision.date,
                    }
                )

            return history

        except Exception as e:
            logger.error(f"❌ Failed to get migration history: {e}")
            return []

    def get_pending_migrations(self) -> list:
        """
        Get pending migrations that haven't been applied.

        Returns:
            List of pending migration revisions
        """
        try:
            current_revision = self.get_current_revision()
            script_dir = ScriptDirectory.from_config(self.alembic_cfg)
            head_revision = script_dir.get_current_head()

            if current_revision == head_revision:
                return []

            if current_revision is None:
                return [revision.revision for revision in script_dir.walk_revisions()][
                    ::-1
                ]

            # Get all revisions between current and head
            pending = []
            current = current_revision

            while current != head_revision:
                revision = script_dir.get_revision(current)
                if revision:
                    pending.append(revision.revision)
                    current = revision.down_revision
                else:
                    break

            return pending

        except Exception as e:
            logger.error(f"❌ Failed to get pending migrations: {e}")
            return []

    def check_migration_status(self) -> dict:
        """
        Check the current migration status.

        Returns:
            Dictionary with migration status information
        """
        try:
            current_revision = self.get_current_revision()
            script_dir = ScriptDirectory.from_config(self.alembic_cfg)
            head_revision = script_dir.get_current_head()
            pending_migrations = self.get_pending_migrations()

            return {
                "current_revision": current_revision,
                "head_revision": head_revision,
                "is_up_to_date": current_revision == head_revision,
                "pending_count": len(pending_migrations),
                "pending_migrations": pending_migrations,
            }

        except Exception as e:
            logger.error(f"❌ Failed to check migration status: {e}")
            return {
                "current_revision": None,
                "head_revision": None,
                "is_up_to_date": False,
                "pending_count": 0,
                "pending_migrations": [],
                "error": str(e),
            }


# Global migration manager instance
_migration_manager: Optional[MigrationManager] = None


def get_migration_manager() -> MigrationManager:
    """
    Get the global migration manager instance.

    Returns:
        Migration manager instance
    """
    global _migration_manager

    if _migration_manager is None:
        _migration_manager = MigrationManager()

    return _migration_manager


def run_migrations(target: Optional[str] = None) -> bool:
    """
    Run database migrations.

    Args:
        target: Target revision (defaults to latest)

    Returns:
        True if successful, False otherwise
    """
    manager = get_migration_manager()
    return manager.run_migrations(target)


def create_migration(message: str, autogenerate: bool = True) -> Optional[str]:
    """
    Create a new migration.

    Args:
        message: Migration message
        autogenerate: Whether to auto-generate migration from model changes

    Returns:
        Migration revision ID or None if failed
    """
    manager = get_migration_manager()
    return manager.create_migration(message, autogenerate)


def init_migration_system() -> None:
    """
    Initialize the migration system.

    This function:
    - Creates the migrations directory
    - Initializes Alembic
    - Creates the initial migration
    """
    manager = get_migration_manager()
    manager.init_migrations()


def check_migration_status() -> dict:
    """
    Check the current migration status.

    Returns:
        Dictionary with migration status information
    """
    manager = get_migration_manager()
    return manager.check_migration_status()


def require_up_to_date_schema() -> None:
    """Raise if database schema is behind the current migration head."""
    status = check_migration_status()
    if status.get("is_up_to_date", False):
        return

    # Try to auto-apply migrations before failing.
    manager = get_migration_manager()
    manager.run_migrations()

    status = check_migration_status()
    if status.get("is_up_to_date", False):
        return

    db_url = get_database_manager().database_url
    pending = status.get("pending_migrations", [])
    pending_list = ", ".join(pending) if pending else "unknown"
    raise RuntimeError(
        "Database schema is behind migrations. "
        f"Pending revisions: {pending_list}. "
        f"Database: {db_url}. "
        "Run: python -m transcriptx.cli.main database migrate"
    )


def get_migration_history() -> list:
    """
    Get migration history.

    Returns:
        List of migration information
    """
    manager = get_migration_manager()
    return manager.get_migration_history()
