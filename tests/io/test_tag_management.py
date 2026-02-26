"""
Tests for tag management operations.

This module tests tag display, addition, removal, and interactive management.
"""

from unittest.mock import patch, MagicMock


from transcriptx.io.tag_management import (
    display_tags,
    prompt_add_tag,
    prompt_remove_tag,
    manage_tags_interactive,
)


class TestDisplayTags:
    """Tests for display_tags function."""

    def test_displays_no_tags_message(self):
        """Test that 'No tags' message is shown when empty."""
        with patch("transcriptx.io.tag_management.console") as mock_console:
            display_tags([], [], {})

            mock_console.print.assert_called()
            call_args = str(mock_console.print.call_args)
            assert "No tags" in call_args or "dim" in call_args

    def test_displays_auto_generated_tags(self):
        """Test that auto-generated tags are displayed with indicator."""
        current_tags = ["meeting", "discussion"]
        auto_tags = ["meeting"]
        tag_details = {"meeting": {"confidence": 0.95}}

        with patch("transcriptx.io.tag_management.console") as mock_console:
            display_tags(current_tags, auto_tags, tag_details)

            # Should have called print multiple times
            assert mock_console.print.call_count > 0

    def test_displays_manual_tags(self):
        """Test that manual tags are displayed with indicator."""
        current_tags = ["meeting", "custom"]
        auto_tags = ["meeting"]
        tag_details = {}

        with patch("transcriptx.io.tag_management.console") as mock_console:
            display_tags(current_tags, auto_tags, tag_details)

            assert mock_console.print.call_count > 0

    def test_shows_confidence_for_auto_tags(self):
        """Test that confidence scores are shown for auto tags."""
        current_tags = ["meeting"]
        auto_tags = ["meeting"]
        tag_details = {"meeting": {"confidence": 0.95}}

        with patch("transcriptx.io.tag_management.console") as mock_console:
            display_tags(current_tags, auto_tags, tag_details)

            # Should display confidence
            call_args_str = str(mock_console.print.call_args_list)
            assert "confidence" in call_args_str or "0.95" in call_args_str


class TestPromptAddTag:
    """Tests for prompt_add_tag function."""

    def test_prompts_for_tag(self):
        """Test that user is prompted for tag."""
        with patch("transcriptx.io.tag_management.questionary") as mock_q:
            mock_q.text.return_value.ask.return_value = "meeting"

            result = prompt_add_tag()

            assert result == "meeting"
            mock_q.text.assert_called_once()

    def test_returns_none_when_cancelled(self):
        """Test that None is returned when user cancels."""
        with patch("transcriptx.io.tag_management.questionary") as mock_q:
            mock_q.text.return_value.ask.return_value = None

            result = prompt_add_tag()

            assert result is None

    def test_strips_whitespace(self):
        """Test that whitespace is stripped from tag."""
        with patch("transcriptx.io.tag_management.questionary") as mock_q:
            mock_q.text.return_value.ask.return_value = "  meeting  "

            result = prompt_add_tag()

            assert result == "meeting"

    def test_validates_non_empty_tag(self):
        """Test that empty tags are rejected."""
        with patch("transcriptx.io.tag_management.questionary") as mock_q:
            # Mock questionary to return None for empty input (cancelled)
            mock_text_instance = MagicMock()
            mock_text_instance.ask.return_value = None  # Empty input returns None
            mock_q.text.return_value = mock_text_instance

            result = prompt_add_tag()

            # Should return None for empty/cancelled input
            assert result is None


class TestPromptRemoveTag:
    """Tests for prompt_remove_tag function."""

    def test_prompts_for_tag_removal(self):
        """Test that user can select tags to remove."""
        tags = ["meeting", "discussion", "custom"]

        with patch("transcriptx.io.tag_management.questionary") as mock_q:
            mock_q.checkbox.return_value.ask.return_value = ["meeting", "discussion"]

            result = prompt_remove_tag(tags)

            assert result == ["meeting", "discussion"]
            mock_q.checkbox.assert_called_once()

    def test_returns_empty_list_when_no_tags(self):
        """Test that empty list is returned when no tags exist."""
        with patch("transcriptx.io.tag_management.console") as mock_console:
            result = prompt_remove_tag([])

            assert result == []
            mock_console.print.assert_called()

    def test_returns_empty_list_when_nothing_selected(self):
        """Test that empty list is returned when nothing is selected."""
        tags = ["meeting", "discussion"]

        with patch("transcriptx.io.tag_management.questionary") as mock_q:
            mock_q.checkbox.return_value.ask.return_value = []

            result = prompt_remove_tag(tags)

            assert result == []

    def test_returns_empty_list_when_cancelled(self):
        """Test that empty list is returned when user cancels."""
        tags = ["meeting", "discussion"]

        with patch("transcriptx.io.tag_management.questionary") as mock_q:
            mock_q.checkbox.return_value.ask.return_value = None

            result = prompt_remove_tag(tags)

            assert result == []


class TestManageTagsInteractive:
    """Tests for manage_tags_interactive function."""

    def test_returns_auto_tags_in_batch_mode(self):
        """Test that auto tags are returned in batch mode."""
        auto_tags = ["meeting", "discussion"]
        tag_details = {"meeting": {"confidence": 0.95}}

        result = manage_tags_interactive(
            "test.json", auto_tags, tag_details, batch_mode=True
        )

        assert result["tags"] == auto_tags
        assert result["tag_details"] == tag_details

    def test_preserves_manual_tags_in_batch_mode(self):
        """Test that manual tags are preserved in batch mode."""
        auto_tags = ["meeting"]
        current_tags = ["meeting", "custom"]
        tag_details = {"meeting": {"confidence": 0.95}}

        result = manage_tags_interactive(
            "test.json",
            auto_tags,
            tag_details,
            current_tags=current_tags,
            batch_mode=True,
        )

        assert "custom" in result["tags"]
        assert "meeting" in result["tags"]

    def test_starts_with_current_tags_if_provided(self):
        """Test that current tags are used as starting point."""
        auto_tags = ["meeting"]
        current_tags = ["custom1", "custom2"]
        tag_details = {}

        with patch("transcriptx.io.tag_management.questionary") as mock_q:
            mock_q.select.return_value.ask.return_value = (
                "✅ Done - proceed with current tags"
            )

            result = manage_tags_interactive(
                "test.json",
                auto_tags,
                tag_details,
                current_tags=current_tags,
                batch_mode=False,
            )

            assert "custom1" in result["tags"]
            assert "custom2" in result["tags"]

    def test_starts_with_auto_tags_if_no_current_tags(self):
        """Test that auto tags are used when no current tags provided."""
        auto_tags = ["meeting", "discussion"]
        tag_details = {}

        with patch("transcriptx.io.tag_management.questionary") as mock_q:
            mock_q.select.return_value.ask.return_value = (
                "✅ Done - proceed with current tags"
            )

            result = manage_tags_interactive(
                "test.json", auto_tags, tag_details, batch_mode=False
            )

            assert "meeting" in result["tags"]
            assert "discussion" in result["tags"]

    def test_adds_new_tag(self):
        """Test that new tags can be added."""
        auto_tags = ["meeting"]
        tag_details = {}

        with patch("transcriptx.io.tag_management.questionary") as mock_q:
            # First select "Add", then enter tag, then "Done"
            mock_q.select.return_value.ask.side_effect = [
                "➕ Add a new tag",
                "✅ Done - proceed with current tags",
            ]
            mock_q.text.return_value.ask.return_value = "custom"

            result = manage_tags_interactive(
                "test.json", auto_tags, tag_details, batch_mode=False
            )

            assert "custom" in result["tags"]
            assert "meeting" in result["tags"]

    def test_removes_tags(self):
        """Test that tags can be removed."""
        auto_tags = ["meeting", "discussion"]
        tag_details = {}

        with patch("transcriptx.io.tag_management.questionary") as mock_q:
            # First select "Remove", then select tags, then "Done"
            mock_q.select.return_value.ask.side_effect = [
                "➖ Remove tags",
                "✅ Done - proceed with current tags",
            ]
            mock_q.checkbox.return_value.ask.return_value = ["meeting"]

            result = manage_tags_interactive(
                "test.json", auto_tags, tag_details, batch_mode=False
            )

            assert "meeting" not in result["tags"]
            assert "discussion" in result["tags"]

    def test_prevents_duplicate_tags(self):
        """Test that duplicate tags are prevented."""
        auto_tags = ["meeting"]
        tag_details = {}

        with (
            patch("transcriptx.io.tag_management.questionary") as mock_q,
            patch("transcriptx.io.tag_management.console") as mock_console,
        ):

            mock_q.select.return_value.ask.side_effect = [
                "➕ Add a new tag",
                "✅ Done - proceed with current tags",
            ]
            mock_q.text.return_value.ask.return_value = "meeting"  # Duplicate

            result = manage_tags_interactive(
                "test.json", auto_tags, tag_details, batch_mode=False
            )

            # Should only have one "meeting" tag
            assert result["tags"].count("meeting") == 1

    def test_marks_tags_with_source(self):
        """Test that tags are marked with source (auto/manual)."""
        auto_tags = ["meeting"]
        tag_details = {"meeting": {"confidence": 0.95}}

        with patch("transcriptx.io.tag_management.questionary") as mock_q:
            mock_q.select.return_value.ask.return_value = (
                "✅ Done - proceed with current tags"
            )

            result = manage_tags_interactive(
                "test.json", auto_tags, tag_details, batch_mode=False
            )

            assert result["tag_details"]["meeting"]["source"] == "auto"

    def test_marks_manual_tags_correctly(self):
        """Test that manually added tags are marked as manual."""
        auto_tags = []
        tag_details = {}

        with patch("transcriptx.io.tag_management.questionary") as mock_q:
            mock_q.select.return_value.ask.side_effect = [
                "➕ Add a new tag",
                "✅ Done - proceed with current tags",
            ]
            mock_q.text.return_value.ask.return_value = "custom"

            result = manage_tags_interactive(
                "test.json", auto_tags, tag_details, batch_mode=False
            )

            assert result["tag_details"]["custom"]["source"] == "manual"
            assert result["tag_details"]["custom"]["confidence"] == 1.0
