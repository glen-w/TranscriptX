"""Output validation rule exists for semantic_similarity."""

from __future__ import annotations

from transcriptx.core.utils.output_validation import MODULE_VALIDATION_RULES


def test_semantic_similarity_validation_rule_registered() -> None:
    rule = MODULE_VALIDATION_RULES.get("semantic_similarity")
    assert rule is not None
    assert any("semantic_similarity_summary" in p for p in rule.required_files)
    assert "charts/global" in rule.required_dirs
    assert ".png" in rule.file_extensions
