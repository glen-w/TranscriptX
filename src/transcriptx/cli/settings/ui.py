from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import questionary
from rich import print as rich_print

BACK_CHOICE_KEY = "__back__"
NONE_SENTINEL = object()


def default_formatter(value: Any, max_length: int = 40) -> str:
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3g}"
    text = str(value)
    if len(text) > max_length:
        return f"{text[: max_length - 1]}…"
    return text


@dataclass(order=True)
class SettingItem:
    order: int
    key: str = field(compare=False)
    label: str = field(compare=False)
    getter: Callable[[], Any] = field(compare=False)
    setter: Callable[[Any], None] = field(compare=False)
    editor: Callable[[SettingItem], Optional[Any]] = field(compare=False)
    formatter: Callable[[Any], str] = field(default=default_formatter, compare=False)
    hint: Optional[str] = field(default=None, compare=False)

    def display_title(self) -> str:
        formatted = self.formatter(self.getter())
        return f"{self.label} [{formatted}]"


def settings_menu_loop(
    title: str,
    items: list[SettingItem],
    on_back: Callable[[], None],
    dirty_tracker: Optional[Callable[[], bool]] = None,
    mark_dirty: Optional[Callable[[], None]] = None,
) -> None:
    mark_dirty = mark_dirty or (lambda: None)

    while True:
        dirty_suffix = " (unsaved changes)" if (dirty_tracker and dirty_tracker()) else ""
        menu_title = f"{title}{dirty_suffix}"
        choices = [
            questionary.Choice(title=item.display_title(), value=item.key)
            for item in sorted(items)
        ]
        choices.append(questionary.Choice(title="🔙 Back", value=BACK_CHOICE_KEY))

        selected_key = questionary.select(menu_title, choices=choices).ask()
        if selected_key in (None, BACK_CHOICE_KEY):
            on_back()
            return

        selected_item = next((item for item in items if item.key == selected_key), None)
        if not selected_item:
            rich_print("[red]Invalid selection. Please try again.[/red]")
            continue

        new_value = selected_item.editor(selected_item)
        if new_value is None:
            continue

        if new_value is NONE_SENTINEL:
            selected_item.setter(None)
        else:
            selected_item.setter(new_value)
        mark_dirty()


def _prompt_text(
    prompt: str, default: Optional[str] = None, hint: Optional[str] = None
) -> Optional[str]:
    if hint:
        rich_print(f"[dim]{hint}[/dim]")
    try:
        return questionary.text(prompt, default=default).ask()
    except KeyboardInterrupt:
        return None


def create_int_editor(
    min_val: int | None = None,
    max_val: int | None = None,
    hint: Optional[str] = None,
    allow_none: bool = False,
) -> Callable[[SettingItem], Optional[Any]]:
    def editor(item: SettingItem) -> Optional[Any]:
        prompt = f"Enter {item.label.lower()}"
        current_value = item.getter()
        default = "" if (allow_none and current_value is None) else str(current_value)
        value = _prompt_text(prompt, default=default, hint=hint)
        if value is None:
            return None
        value = value.strip()
        if allow_none and value == "":
            return NONE_SENTINEL
        try:
            parsed = int(value)
        except ValueError:
            rich_print("[red]Invalid number. No change made.[/red]")
            return None
        if min_val is not None and parsed < min_val:
            rich_print(f"[red]Value must be >= {min_val}. No change made.[/red]")
            return None
        if max_val is not None and parsed > max_val:
            rich_print(f"[red]Value must be <= {max_val}. No change made.[/red]")
            return None
        return parsed

    return editor


def create_float_editor(
    min_val: float | None = None,
    max_val: float | None = None,
    hint: Optional[str] = None,
    allow_none: bool = False,
) -> Callable[[SettingItem], Optional[Any]]:
    def editor(item: SettingItem) -> Optional[Any]:
        prompt = f"Enter {item.label.lower()}"
        current_value = item.getter()
        default = "" if (allow_none and current_value is None) else str(current_value)
        value = _prompt_text(prompt, default=default, hint=hint)
        if value is None:
            return None
        value = value.strip()
        if allow_none and value == "":
            return NONE_SENTINEL
        try:
            parsed = float(value)
        except ValueError:
            rich_print("[red]Invalid number. No change made.[/red]")
            return None
        if min_val is not None and parsed < min_val:
            rich_print(f"[red]Value must be >= {min_val}. No change made.[/red]")
            return None
        if max_val is not None and parsed > max_val:
            rich_print(f"[red]Value must be <= {max_val}. No change made.[/red]")
            return None
        return parsed

    return editor


def create_bool_editor(hint: Optional[str] = None) -> Callable[[SettingItem], Optional[Any]]:
    def editor(item: SettingItem) -> Optional[Any]:
        if hint:
            rich_print(f"[dim]{hint}[/dim]")
        try:
            return questionary.confirm(
                f"Enable {item.label.lower()}?",
                default=bool(item.getter()),
            ).ask()
        except KeyboardInterrupt:
            return None

    return editor


def create_str_editor(
    hint: Optional[str] = None,
    allow_none: bool = False,
) -> Callable[[SettingItem], Optional[Any]]:
    def editor(item: SettingItem) -> Optional[Any]:
        prompt = f"Enter {item.label.lower()}"
        default = str(item.getter() or "")
        value = _prompt_text(prompt, default=default, hint=hint)
        if value is None:
            return None
        if allow_none and value.strip() == "":
            return NONE_SENTINEL
        return value

    return editor


def create_choice_editor(
    choices: list[Any],
    hint: Optional[str] = None,
    allow_none: bool = False,
) -> Callable[[SettingItem], Optional[Any]]:
    def editor(item: SettingItem) -> Optional[Any]:
        if hint:
            rich_print(f"[dim]{hint}[/dim]")
        selection_choices: list[questionary.Choice]
        selection_choices = [
            questionary.Choice(title=str(choice), value=choice) for choice in choices
        ]
        if allow_none:
            selection_choices.insert(0, questionary.Choice(title="—", value=NONE_SENTINEL))
        current_value = item.getter()
        if allow_none and current_value is None:
            default_value = NONE_SENTINEL
        else:
            default_value = (
                current_value
                if any(choice.value == current_value for choice in selection_choices)
                else None
            )
        try:
            return questionary.select(
                f"Select {item.label.lower()}",
                choices=selection_choices,
                default=default_value,
            ).ask()
        except KeyboardInterrupt:
            return None

    return editor


def create_multiselect_editor(
    choices: list[Any],
    hint: Optional[str] = None,
    allow_empty: bool = True,
) -> Callable[[SettingItem], Optional[Any]]:
    def editor(item: SettingItem) -> Optional[Any]:
        if hint:
            rich_print(f"[dim]{hint}[/dim]")
        selection_choices: list[questionary.Choice] = []
        for choice in choices:
            if isinstance(choice, questionary.Choice):
                selection_choices.append(choice)
            else:
                selection_choices.append(
                    questionary.Choice(title=str(choice), value=choice)
                )
        current_values = item.getter() or []
        # Get all valid choice values as a set for fast lookup
        choice_value_set = {choice.value for choice in selection_choices}
        
        # Create a mapping for normalized comparison (handles type mismatches)
        # Map both the original value and string representation to the original value
        choice_value_map: dict[str, Any] = {}
        for v in choice_value_set:
            choice_value_map[str(v)] = v
            choice_value_map[str(v).strip()] = v
            if v is not None:
                choice_value_map[str(v).lower()] = v
        
        # Filter current values to only include those that exactly match choice values
        # Try exact match first, then normalized match for type flexibility
        valid_defaults: list[Any] = []
        seen_values: set[Any] = set()
        for value in current_values:
            matched_value: Any = None
            if value in choice_value_set:
                # Exact match - use as is
                matched_value = value
            else:
                # Try normalized match (string comparison)
                normalized = str(value).strip() if value is not None else None
                if normalized and normalized in choice_value_map:
                    # Use the original choice value to ensure type consistency
                    matched_value = choice_value_map[normalized]
            
            # Only add if we found a match and haven't seen it before
            if matched_value is not None and matched_value not in seen_values:
                valid_defaults.append(matched_value)
                seen_values.add(matched_value)
        
        # questionary.checkbox doesn't accept empty list as default - use None instead
        # Also ensure we only pass values that are in the choice set
        default_value: list[Any] | None = valid_defaults if valid_defaults else None
        
        try:
            selected = questionary.checkbox(
                f"Select {item.label.lower()}",
                choices=selection_choices,
                default=default_value,  # type: ignore[arg-type]
            ).ask()
        except (KeyboardInterrupt, ValueError) as e:
            # Handle ValueError from questionary when default values don't match
            # This can happen if there's a type mismatch or invalid values
            if isinstance(e, ValueError) and "default" in str(e).lower():
                # Retry with None as default if there's a default value error
                try:
                    selected = questionary.checkbox(
                        f"Select {item.label.lower()}",
                        choices=selection_choices,
                        default=None,  # type: ignore[arg-type]
                    ).ask()
                except KeyboardInterrupt:
                    return None
            else:
                return None
        if selected is None:
            return None
        if not selected and not allow_empty:
            return current_values
        return selected

    return editor


def create_list_editor(
    hint: Optional[str] = None,
    allow_empty: bool = True,
) -> Callable[[SettingItem], Optional[Any]]:
    def editor(item: SettingItem) -> Optional[Any]:
        current = item.getter() or []
        default = ", ".join(current) if current else ""
        value = _prompt_text(
            f"Enter {item.label.lower()} (comma-separated)",
            default=default,
            hint=hint,
        )
        if value is None:
            return None
        if value.strip() == "":
            return [] if allow_empty else current
        return [part.strip() for part in value.split(",") if part.strip()]

    return editor
