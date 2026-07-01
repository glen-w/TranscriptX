"""Pydantic schema for logging."""

from pydantic import BaseModel, Field


class LoggingSettingsModel(BaseModel):
    level: str = Field(default="INFO")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_logging: bool = Field(default=True)
    log_file: str = Field(default="transcriptx.log")
    max_log_size: int = Field(default=10485760)
    backup_count: int = Field(default=5)
