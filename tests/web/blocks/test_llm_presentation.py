"""Unit tests for shared LLM artifact presentation helpers."""

from __future__ import annotations

import pytest

from transcriptx.web.blocks import llm_presentation as lp


@pytest.mark.unit
class TestProvenanceBadges:
    def test_non_dict_returns_empty(self) -> None:
        assert lp.provenance_badges(None) == []
        assert lp.provenance_badges("not a dict") == []  # type: ignore[arg-type]

    def test_full_provenance_yields_prompt_and_model_badges(self) -> None:
        badges = lp.provenance_badges({"prompt_version": "1.2", "model": "qwen3:8b"})
        assert badges == ["Prompt v1.2", "qwen3:8b"]

    def test_prompt_only(self) -> None:
        assert lp.provenance_badges({"prompt_version": "2"}) == ["Prompt v2"]

    def test_model_only(self) -> None:
        assert lp.provenance_badges({"model": "m"}) == ["m"]

    def test_blank_values_are_skipped(self) -> None:
        assert lp.provenance_badges({"prompt_version": "  ", "model": None}) == []


@pytest.mark.unit
class TestStripLeadingMarkdownHeading:
    def test_removes_single_leading_heading(self) -> None:
        out = lp.strip_leading_markdown_heading("# Title\n\nBody text")
        assert out == "Body text"

    def test_no_heading_is_noop(self) -> None:
        assert lp.strip_leading_markdown_heading("Body only") == "Body only"

    def test_only_first_heading_removed(self) -> None:
        out = lp.strip_leading_markdown_heading("# T\n\n## Section\nBody")
        assert out.startswith("## Section")


@pytest.mark.unit
class TestStripProvenanceFooter:
    def test_removes_prompt_and_model_footer(self) -> None:
        md = "Body\n\n---\nPrompt version: 1\nModel: qwen3:8b\n"
        assert lp.strip_provenance_footer(md) == "Body\n"

    def test_removes_model_only_footer(self) -> None:
        md = "Body\n\n---\nModel: qwen3:8b\n"
        assert lp.strip_provenance_footer(md) == "Body\n"

    def test_no_footer_is_preserved(self) -> None:
        md = "Body paragraph\n"
        assert lp.strip_provenance_footer(md) == "Body paragraph\n"

    def test_mid_document_rule_is_not_removed(self) -> None:
        md = "Intro\n\n---\n\nMore content after a rule\n"
        assert "More content after a rule" in lp.strip_provenance_footer(md)


@pytest.mark.unit
class TestStripCommitmentsSection:
    def test_removes_commitments_section(self) -> None:
        md = (
            "# Summary\n\nOverview text\n\n"
            "## Commitments / Next steps\n- do a thing\n- do another\n\n"
            "## Other section\nKept\n"
        )
        out = lp.strip_commitments_section(md)
        assert "Commitments" not in out
        assert "do a thing" not in out
        assert "## Other section" in out
        assert "Kept" in out

    def test_commitments_at_end_removed_up_to_footer(self) -> None:
        md = (
            "Overview\n\n## Commitments / Next steps\n- item\n\n"
            "---\nModel: m\n"
        )
        out = lp.strip_commitments_section(md)
        assert "item" not in out
        assert "Model: m" in out

    def test_no_section_is_noop_modulo_trailing_newline(self) -> None:
        md = "Overview\n\n## Themes\n- t\n"
        assert lp.strip_commitments_section(md) == md

    def test_collapses_excess_blank_lines(self) -> None:
        md = "A\n\n## Commitments / Next steps\n- x\n\n## B\nend\n"
        out = lp.strip_commitments_section(md)
        assert "\n\n\n" not in out


@pytest.mark.unit
class TestRenderHelpers:
    def test_render_badge_row_emits_single_markdown_call(self, monkeypatch) -> None:
        calls: list = []
        monkeypatch.setattr(lp.st, "markdown", lambda *a, **k: calls.append((a, k)))
        lp.render_badge_row(["Prompt v1", "", "qwen3:8b"])
        assert len(calls) == 1
        html = calls[0][0][0]
        assert 'class="tx-badge"' in html
        assert "Prompt v1" in html and "qwen3:8b" in html
        assert calls[0][1].get("unsafe_allow_html") is True

    def test_render_badge_row_skips_when_all_labels_empty(self, monkeypatch) -> None:
        calls: list = []
        monkeypatch.setattr(lp.st, "markdown", lambda *a, **k: calls.append(a))
        lp.render_badge_row(["", ""])
        assert calls == []

    def test_render_markdown_strips_heading_and_footer(self, monkeypatch) -> None:
        calls: list = []
        monkeypatch.setattr(lp.st, "markdown", lambda *a, **k: calls.append(a[0]))
        lp.render_markdown_without_heading_or_provenance(
            "# Title\n\nBody\n\n---\nPrompt version: 1\nModel: m\n"
        )
        assert calls == ["Body\n"]

    def test_render_markdown_skips_empty_body(self, monkeypatch) -> None:
        calls: list = []
        monkeypatch.setattr(lp.st, "markdown", lambda *a, **k: calls.append(a[0]))
        lp.render_markdown_without_heading_or_provenance("# Title only\n")
        assert calls == []
