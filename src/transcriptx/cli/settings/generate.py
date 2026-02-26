from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any, Optional, Union, get_args, get_origin, get_type_hints, Literal

from .ui import (
    SettingItem,
    create_bool_editor,
    create_choice_editor,
    create_float_editor,
    create_int_editor,
    create_str_editor,
)


def _normalize_label(name: str) -> str:
    return name.replace("_", " ").title()


def _unwrap_optional(type_hint: Any) -> tuple[Any, bool]:
    origin = get_origin(type_hint)
    if origin is Union:
        args = get_args(type_hint)
        non_none_args = [arg for arg in args if arg is not type(None)]
        if len(non_none_args) == 1 and len(non_none_args) != len(args):
            return non_none_args[0], True
    return type_hint, False


def _is_enum_type(type_hint: Any) -> bool:
    return isinstance(type_hint, type) and issubclass(type_hint, Enum)


def _is_list_of_str(type_hint: Any) -> bool:
    origin = get_origin(type_hint)
    if origin is list:
        args = get_args(type_hint)
        return len(args) == 1 and args[0] is str
    return False


def build_setting_items_from_dataclass(
    instance: Any,
    prefix: str = "",
    overrides: Optional[dict[str, SettingItem]] = None,
) -> list[SettingItem]:
    if not is_dataclass(instance):
        raise TypeError(
            "build_setting_items_from_dataclass expects a dataclass instance"
        )

    overrides = overrides or {}
    items: list[SettingItem] = []

    type_hints = get_type_hints(type(instance))

    for idx, field in enumerate(fields(instance)):
        if field.name in overrides:
            items.append(overrides[field.name])
            continue

        if field.metadata.get("exclude"):
            continue

        type_hint = type_hints.get(field.name, field.type)
        inner_type, is_optional = _unwrap_optional(type_hint)

        value = getattr(instance, field.name)
        if is_dataclass(value):
            continue

        if _is_list_of_str(inner_type):
            continue

        label = field.metadata.get("label", _normalize_label(field.name))
        hint = field.metadata.get("hint")
        min_val = field.metadata.get("min")
        max_val = field.metadata.get("max")
        choices = field.metadata.get("choices")

        key = f"{prefix}.{field.name}" if prefix else field.name

        def getter(name: str = field.name) -> Any:
            return getattr(instance, name)

        def setter(new_value: Any, name: str = field.name) -> None:
            setattr(instance, name, new_value)

        editor = None

        if choices:
            editor = create_choice_editor(
                list(choices), hint=hint, allow_none=is_optional
            )
        elif get_origin(inner_type) is Literal:
            literal_choices = list(get_args(inner_type))
            editor = create_choice_editor(
                literal_choices, hint=hint, allow_none=is_optional
            )
        elif _is_enum_type(inner_type):
            enum_choices = list(inner_type)
            editor = create_choice_editor(
                enum_choices, hint=hint, allow_none=is_optional
            )
        elif inner_type is bool:
            if is_optional:
                editor = create_choice_editor([True, False], hint=hint, allow_none=True)
            else:
                editor = create_bool_editor(hint=hint)
        elif inner_type is int:
            editor = create_int_editor(
                min_val=min_val, max_val=max_val, hint=hint, allow_none=is_optional
            )
        elif inner_type is float:
            editor = create_float_editor(
                min_val=min_val, max_val=max_val, hint=hint, allow_none=is_optional
            )
        elif inner_type is str:
            editor = create_str_editor(hint=hint, allow_none=is_optional)
        else:
            continue

        items.append(
            SettingItem(
                order=idx,
                key=key,
                label=label,
                getter=getter,
                setter=setter,
                editor=editor,
                hint=hint,
            )
        )

    return items


def build_analysis_settings_items(config: Any) -> list[SettingItem]:
    # Auto-generation example (manual overrides can be applied as needed).
    return build_setting_items_from_dataclass(
        config.analysis,
        prefix="analysis",
        overrides={},
    )
