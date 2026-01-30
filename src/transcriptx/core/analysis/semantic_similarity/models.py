"""
Transformer model management for semantic similarity analysis.
"""

from __future__ import annotations

import warnings
from typing import Any, Callable, Optional

from transcriptx.core.utils.logger import log_error, log_info
from transcriptx.core.utils.lazy_imports import get_torch, get_transformers


class SemanticModelManager:
    """Load and manage transformer models for semantic similarity."""

    def __init__(
        self,
        config: Any | None = None,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        log_tag: str = "SEMANTIC",
        progress_context: Optional[Callable[[str], Any]] = None,
        progress_logger: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.config = config
        self.model_name = model_name
        self.log_tag = log_tag
        self.progress_context = progress_context
        self.progress_logger = progress_logger

        self.torch = get_torch()
        self.device = self.torch.device(
            "cuda" if self.torch.cuda.is_available() else "cpu"
        )
        self.model = None
        self.tokenizer = None

    def initialize(self) -> None:
        """Initialize transformer model and tokenizer."""
        try:
            transformers = get_transformers()
            # Suppress FutureWarning about resume_download deprecation in huggingface_hub
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=".*resume_download.*",
                    category=FutureWarning,
                )
                if self.progress_context:
                    with self.progress_context("🤖 Loading semantic similarity models"):
                        self.tokenizer = transformers.AutoTokenizer.from_pretrained(
                            self.model_name
                        )
                        self.model = transformers.AutoModel.from_pretrained(
                            self.model_name
                        ).to(self.device)
                        self.model.eval()
                    if self.progress_logger:
                        self.progress_logger(f"Loaded semantic model: {self.model_name}")
                else:
                    self.tokenizer = transformers.AutoTokenizer.from_pretrained(
                        self.model_name
                    )
                    self.model = transformers.AutoModel.from_pretrained(
                        self.model_name
                    ).to(self.device)
                    self.model.eval()
                    log_info(self.log_tag, f"Loaded semantic model: {self.model_name}")
        except Exception as exc:
            log_error(
                self.log_tag, f"Failed to load semantic model: {exc}", exception=exc
            )
            self.model = None
            self.tokenizer = None
