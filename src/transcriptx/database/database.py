"""
Database management for TranscriptX.

This module provides database initialization, connection management, and configuration
for the TranscriptX database backend. It supports multiple database backends and
provides a unified interface for database operations.

Key Features:
- Database initialization and migration
- Connection pooling and management
- Multiple backend support (SQLite, PostgreSQL)
- Configuration management
- Session management
- Error handling and logging

The database system is designed to be:
- Flexible: Supports multiple database backends
- Robust: Includes connection pooling and error handling
- Performant: Optimized for read/write operations
- Maintainable: Clear separation of concerns
"""

import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


class DatabaseManager:
    """
    Database manager for TranscriptX.

    This class provides a unified interface for database operations,
    including initialization, connection management, and session handling.

    The manager supports:
    - Multiple database backends (SQLite, PostgreSQL)
    - Connection pooling and optimization
    - Session management and cleanup
    - Error handling and logging
    - Configuration management
    """

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize the database manager.

        Args:
            database_url: Database connection URL. If not provided,
                        will use configuration or default to SQLite.

        Note:
            The database URL can be:
            - SQLite: sqlite:///path/to/database.db
            - PostgreSQL: postgresql://user:pass@host:port/database
            - Environment variable: TRANSCRIPTX_DATABASE_URL
        """
        self.database_url = database_url or self._get_database_url()
        self.engine = None
        self.SessionLocal = None
        self._initialized = False

        logger.info(
            f"🔧 Initializing database manager with URL: {self._mask_database_url()}"
        )

    def _get_database_url(self) -> str:
        """
        Get the database URL from configuration or environment.

        Returns:
            Database connection URL

        Note:
            Priority order:
            1. Environment variable TRANSCRIPTX_DATABASE_URL
            2. Configuration file
            3. Default SQLite database in data directory
        """
        # Check environment variable first
        env_url = os.getenv("TRANSCRIPTX_DATABASE_URL")
        if env_url:
            logger.info("📋 Using database URL from environment variable")
            return env_url

        # Check configuration
        config = get_config()
        if hasattr(config, "database_url") and config.database_url:
            logger.info("📋 Using database URL from configuration")
            return config.database_url

        # Default to SQLite in data directory (respects TRANSCRIPTX_DATA_DIR in Docker)
        from transcriptx.core.utils.paths import DATA_DIR

        db_dir = DATA_DIR / "transcriptx_data"
        db_dir.mkdir(parents=True, exist_ok=True)
        default_url = f"sqlite:///{db_dir / 'transcriptx.db'}"

        logger.info(f"📋 Using default SQLite database: {default_url}")
        return default_url

    def _mask_database_url(self) -> str:
        """Mask sensitive information in database URL for logging."""
        if not self.database_url:
            return "None"

        parsed = urlparse(self.database_url)
        if parsed.password:
            # Replace password with asterisks
            netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
            return f"{parsed.scheme}://{netloc}{parsed.path}"

        return self.database_url

    def initialize(self) -> None:
        """
        Initialize the database engine and session factory.

        This method:
        - Creates the database engine with appropriate configuration
        - Sets up connection pooling
        - Creates the session factory
        - Configures SQLite-specific optimizations

        Note:
            The initialization process includes:
            - Engine creation with connection pooling
            - SQLite-specific optimizations (WAL mode, foreign keys)
            - Session factory setup
            - Connection testing
        """
        if self._initialized:
            logger.warning("⚠️ Database already initialized")
            return

        logger.info("🔧 Initializing database engine...")

        # Determine engine configuration based on database type
        if self.database_url.startswith("sqlite"):
            self._initialize_sqlite()
        elif self.database_url.startswith("postgresql"):
            self._initialize_postgresql()
        else:
            self._initialize_generic()

        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

        # Test connection
        self._test_connection()

        self._initialized = True
        logger.info("✅ Database initialization completed")

    def _initialize_sqlite(self) -> None:
        """Initialize SQLite engine with optimizations."""
        logger.info("🔧 Configuring SQLite engine...")

        # SQLite-specific configuration
        connect_args = {
            "check_same_thread": False,
            "timeout": 30,
        }

        self.engine = create_engine(
            self.database_url,
            connect_args=connect_args,
            poolclass=StaticPool,  # SQLite doesn't need connection pooling
            echo=False,  # Set to True for SQL debugging
        )

        # Configure SQLite optimizations
        @event.listens_for(Engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=10000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.close()

        logger.info("✅ SQLite engine configured with optimizations")

    def _initialize_postgresql(self) -> None:
        """Initialize PostgreSQL engine with connection pooling."""
        logger.info("🔧 Configuring PostgreSQL engine...")

        self.engine = create_engine(
            self.database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,  # Set to True for SQL debugging
        )

        logger.info("✅ PostgreSQL engine configured with connection pooling")

    def _initialize_generic(self) -> None:
        """Initialize generic database engine."""
        logger.info("🔧 Configuring generic database engine...")

        self.engine = create_engine(
            self.database_url,
            pool_pre_ping=True,
            echo=False,  # Set to True for SQL debugging
        )

        logger.info("✅ Generic database engine configured")

    def _test_connection(self) -> None:
        """Test database connection."""
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            logger.info("✅ Database connection test successful")
        except Exception as e:
            logger.error(f"❌ Database connection test failed: {e}")
            raise

    def get_session(self) -> Session:
        """
        Get a database session.

        Returns:
            SQLAlchemy session

        Note:
            The session should be used in a context manager or
            explicitly closed after use to prevent connection leaks.

            Example:
                with db_manager.get_session() as session:
                    # Use session
                    pass
        """
        if not self._initialized:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        return self.SessionLocal()

    def create_tables(self) -> None:
        """
        Create all database tables.

        This method creates all tables defined in the models module.
        It's typically called during initial setup or when migrating
        from a file-based system to the database.
        """
        from .models import Base

        logger.info("🔧 Creating database tables...")

        try:
            Base.metadata.create_all(bind=self.engine)
            self._ensure_transcript_file_columns()
            self._ensure_transcript_speaker_columns()
            logger.info("✅ Database tables created successfully")
        except Exception as e:
            logger.error(f"❌ Failed to create database tables: {e}")
            raise

    def _ensure_transcript_file_columns(self) -> None:
        """
        Ensure TranscriptFile columns exist for legacy databases.

        Existing SQLite DBs can predate newer metadata fields. Add missing
        columns defensively so ORM queries don't fail with missing-column errors.
        """
        inspector = inspect(self.engine)
        if not inspector.has_table("transcript_files"):
            return

        existing_columns = {
            column["name"] for column in inspector.get_columns("transcript_files")
        }
        missing_columns = []

        if "source_uri" not in existing_columns:
            missing_columns.append(("source_uri", "VARCHAR(1000)"))
        if "import_timestamp" not in existing_columns:
            missing_columns.append(("import_timestamp", "DATETIME"))
        if "transcript_content_hash" not in existing_columns:
            missing_columns.append(("transcript_content_hash", "VARCHAR(64)"))
        if "schema_version" not in existing_columns:
            missing_columns.append(("schema_version", "VARCHAR(50)"))
        if "sentence_schema_version" not in existing_columns:
            missing_columns.append(("sentence_schema_version", "VARCHAR(50)"))
        if "source_hash" not in existing_columns:
            missing_columns.append(("source_hash", "VARCHAR(64)"))

        if not missing_columns:
            return

        with self.engine.begin() as connection:
            for column_name, column_type in missing_columns:
                connection.execute(
                    text(
                        f"ALTER TABLE transcript_files ADD COLUMN {column_name} {column_type}"
                    )
                )

            # Add supporting indexes if they don't exist.
            if "transcript_content_hash" not in existing_columns:
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_transcript_content_hash "
                        "ON transcript_files (transcript_content_hash)"
                    )
                )
            if "schema_version" not in existing_columns:
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_transcript_schema_version "
                        "ON transcript_files (schema_version)"
                    )
                )
            if "sentence_schema_version" not in existing_columns:
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_transcript_sentence_schema_version "
                        "ON transcript_files (sentence_schema_version)"
                    )
                )
            if "source_hash" not in existing_columns:
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_transcript_source_hash "
                        "ON transcript_files (source_hash)"
                    )
                )

    def _ensure_transcript_speaker_columns(self) -> None:
        """
        Ensure transcript_speaker_id columns exist for legacy databases.

        SQLite's create_all does not alter existing tables, so older databases
        can be missing new columns required by the ORM models.
        """
        inspector = inspect(self.engine)
        if not inspector.has_table("transcript_segments"):
            return

        segment_columns = {
            column["name"] for column in inspector.get_columns("transcript_segments")
        }
        has_sentence_table = inspector.has_table("transcript_sentences")
        sentence_columns = set()
        if has_sentence_table:
            sentence_columns = {
                column["name"]
                for column in inspector.get_columns("transcript_sentences")
            }

        with self.engine.begin() as connection:
            if "transcript_speaker_id" not in segment_columns:
                connection.execute(
                    text(
                        "ALTER TABLE transcript_segments ADD COLUMN transcript_speaker_id INTEGER"
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_segment_transcript_speaker "
                        "ON transcript_segments (transcript_speaker_id)"
                    )
                )

            if has_sentence_table and "transcript_speaker_id" not in sentence_columns:
                connection.execute(
                    text(
                        "ALTER TABLE transcript_sentences ADD COLUMN transcript_speaker_id INTEGER"
                    )
                )
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_sentence_transcript_speaker "
                        "ON transcript_sentences (transcript_speaker_id)"
                    )
                )

    def drop_tables(self) -> None:
        """
        Drop all database tables.

        Warning: This will delete all data in the database.
        Use with extreme caution.
        """
        from .models import Base

        logger.warning("⚠️ Dropping all database tables...")

        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.info("✅ Database tables dropped successfully")
        except Exception as e:
            logger.error(f"❌ Failed to drop database tables: {e}")
            raise

    def reset_database(self) -> None:
        """
        Reset the database by dropping and recreating all tables.

        Warning: This will delete all data in the database.
        Use with extreme caution.
        """
        logger.warning("⚠️ Resetting database...")

        self.drop_tables()
        self.create_tables()

        logger.info("✅ Database reset completed")

    def get_database_info(self) -> dict:
        """
        Get information about the database.

        Returns:
            Dictionary containing database information

        Note:
            The returned information includes:
            - Database URL (masked)
            - Database type
            - Connection status
            - Table counts
            - Database size (if available)
        """
        info = {
            "database_url": self._mask_database_url(),
            "database_type": self._get_database_type(),
            "initialized": self._initialized,
            "connection_status": "unknown",
        }

        if self._initialized:
            try:
                with self.get_session() as session:
                    # Test connection
                    session.execute(text("SELECT 1"))
                    info["connection_status"] = "connected"

                    # Get table counts
                    info["table_counts"] = self._get_table_counts(session)

                    # Get database size (SQLite only)
                    if self.database_url.startswith("sqlite"):
                        info["database_size"] = self._get_sqlite_size()

            except Exception as e:
                info["connection_status"] = f"error: {e}"

        return info

    def _get_database_type(self) -> str:
        """Get the database type from the URL."""
        if self.database_url.startswith("sqlite"):
            return "SQLite"
        elif self.database_url.startswith("postgresql"):
            return "PostgreSQL"
        elif self.database_url.startswith("mysql"):
            return "MySQL"
        else:
            return "Unknown"

    def _get_table_counts(self, session: Session) -> dict:
        """Get row counts for all tables."""
        from .models import (
            Speaker,
            Conversation,
            Session,
            SpeakerProfile,
            BehavioralFingerprint,
            AnalysisResult,
            SpeakerStats,
        )

        tables = {
            "speakers": Speaker,
            "conversations": Conversation,
            "sessions": Session,
            "speaker_profiles": SpeakerProfile,
            "behavioral_fingerprints": BehavioralFingerprint,
            "analysis_results": AnalysisResult,
            "speaker_stats": SpeakerStats,
        }

        counts = {}
        for table_name, model in tables.items():
            try:
                count = session.query(model).count()
                counts[table_name] = count
            except Exception:
                counts[table_name] = "error"

        return counts

    def _get_sqlite_size(self) -> Optional[str]:
        """Get SQLite database file size."""
        try:
            parsed = urlparse(self.database_url)
            if parsed.path:
                db_path = Path(parsed.path.lstrip("/"))
                if db_path.exists():
                    size_bytes = db_path.stat().st_size
                    if size_bytes < 1024:
                        return f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        return f"{size_bytes / 1024:.1f} KB"
                    else:
                        return f"{size_bytes / (1024 * 1024):.1f} MB"
        except Exception:
            pass

        return None

    def close(self) -> None:
        """Close database connections and cleanup resources."""
        if self.engine:
            self.engine.dispose()
            logger.info("🔧 Database connections closed")

        self._initialized = False


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """
    Get the global database manager instance.

    Returns:
        Database manager instance

    Note:
        This function ensures that only one database manager instance
        exists throughout the application lifecycle.
    """
    global _db_manager

    if _db_manager is None:
        _db_manager = DatabaseManager()
        _db_manager.initialize()

    return _db_manager


def get_database_url() -> str:
    """
    Get the current database URL.

    Returns:
        Database connection URL
    """
    manager = get_database_manager()
    return manager.database_url


def init_database() -> DatabaseManager:
    """
    Initialize the database system.

    Returns:
        Initialized database manager

    Note:
        This function:
        - Creates the database manager
        - Initializes the engine and session factory
        - Creates tables if they don't exist
        - Returns the manager for use
    """
    manager = get_database_manager()

    # Create tables if they don't exist
    try:
        manager.create_tables()
    except Exception as e:
        logger.warning(f"⚠️ Table creation failed (tables may already exist): {e}")

    return manager


def get_session() -> Session:
    """
    Get a database session.

    Returns:
        SQLAlchemy session

    Note:
        The session should be used in a context manager or
        explicitly closed after use.
    """
    manager = get_database_manager()
    return manager.get_session()


def close_database() -> None:
    """Close database connections and cleanup resources."""
    global _db_manager

    if _db_manager:
        _db_manager.close()
        _db_manager = None
        logger.info("🔧 Database connections closed")
