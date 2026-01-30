"""Dashboard configuration editor."""

from __future__ import annotations

import questionary
from rich import print as rich_print
from typing import Any, Dict

from transcriptx.core.utils.chart_registry import (  # type: ignore[import-not-found]
    get_default_overview_charts,
    iter_chart_definitions,
)
from ._dirty_tracker import is_dirty, mark_dirty


def _sorted_registry() -> list:
    return sorted(
        list(iter_chart_definitions()),
        key=lambda c: (c.rank_default, c.label),
    )


def _format_chart_title(chart_def: Any) -> str:
    return f"[{chart_def.rank_default:>3}] {chart_def.label} ({chart_def.viz_id})"


def _print_overview_preview(viz_ids: list[str], registry_map: Dict[str, Any]) -> None:
    rich_print("[bold]Overview charts (ordered):[/bold]")
    if not viz_ids:
        rich_print("[dim]No charts selected.[/dim]")
        return
    for idx, viz_id in enumerate(viz_ids, start=1):
        chart_def = registry_map.get(viz_id)
        label = chart_def.label if chart_def else viz_id
        cardinality = chart_def.cardinality if chart_def else "unknown"
        rich_print(f" {idx:>2}. {label} [dim]({viz_id})[/dim] [{cardinality}]")


def _sanitize_overview_charts(
    overview_charts: list[str] | None, registry_viz_ids: list[str]
) -> tuple[list[str], list[str]]:
    normalized = [str(viz_id) for viz_id in (overview_charts or [])]
    registry_set = set(registry_viz_ids)
    filtered = [viz_id for viz_id in normalized if viz_id in registry_set]
    removed = [viz_id for viz_id in normalized if viz_id not in registry_set]
    return filtered, removed


def edit_dashboard_config(config) -> None:
    """Edit dashboard configuration."""
    registry = _sorted_registry()
    registry_map = {c.viz_id: c for c in registry}
    registry_viz_ids = [c.viz_id for c in registry]
    current_overview, removed = _sanitize_overview_charts(
        config.dashboard.overview_charts, registry_viz_ids
    )
    if removed:
        rich_print(
            "[yellow]Removed invalid chart IDs from dashboard config:[/yellow] "
            + ", ".join(removed)
        )
        config.dashboard.overview_charts = current_overview
        mark_dirty()

    while True:
        dirty_suffix = " (unsaved changes)" if is_dirty() else ""
        menu_title = f"🌐 Dashboard Settings{dirty_suffix}"
        choice = questionary.select(
            menu_title,
            choices=[
                questionary.Choice("Add/remove charts", value="add_remove"),
                questionary.Choice("Reorder charts", value="reorder"),
                questionary.Choice("Reset to defaults", value="reset"),
                questionary.Choice("Preview overview list", value="preview"),
                questionary.Choice("Missing chart behavior", value="missing_behavior"),
                questionary.Choice("Max overview items", value="max_items"),
                questionary.Choice("🔙 Back", value="back"),
            ],
        ).ask()

        if choice in (None, "back"):
            return

        if choice == "add_remove":
            choices = [
                questionary.Choice(
                    title=_format_chart_title(chart_def),
                    value=chart_def.viz_id,
                    checked=chart_def.viz_id in (config.dashboard.overview_charts or []),
                )
                for chart_def in registry
            ]
            try:
                selected = questionary.checkbox(
                    "Select overview charts",
                    choices=choices,
                ).ask()
            except Exception as exc:
                rich_print(f"[red]Failed to load chart selector: {exc}[/red]")
                continue
            if selected is None:
                continue
            selected_set = set(selected)
            new_order = [
                viz_id
                for viz_id in (config.dashboard.overview_charts or [])
                if viz_id in selected_set
            ]
            for viz_id in registry_viz_ids:
                if viz_id in selected_set and viz_id not in new_order:
                    new_order.append(viz_id)
            config.dashboard.overview_charts = new_order
            mark_dirty()
            continue

        if choice == "reorder":
            current = config.dashboard.overview_charts or []
            if not current:
                rich_print("[dim]No charts selected to reorder.[/dim]")
                continue
            selected_viz_id = questionary.select(
                "Select chart to move",
                choices=[
                    questionary.Choice(
                        f"{idx + 1}. {registry_map.get(viz_id, viz_id).label if registry_map.get(viz_id) else viz_id}",
                        value=viz_id,
                    )
                    for idx, viz_id in enumerate(current)
                ],
            ).ask()
            if not selected_viz_id:
                continue

            action = questionary.select(
                "Reorder action",
                choices=[
                    questionary.Choice("Move up", value="up"),
                    questionary.Choice("Move down", value="down"),
                    questionary.Choice("Move to position", value="move_to"),
                    questionary.Choice("Back", value="back"),
                ],
            ).ask()
            if action in (None, "back"):
                continue

            index = current.index(selected_viz_id)
            if action == "up" and index > 0:
                current[index - 1], current[index] = current[index], current[index - 1]
                mark_dirty()
            elif action == "down" and index < len(current) - 1:
                current[index + 1], current[index] = current[index], current[index + 1]
                mark_dirty()
            elif action == "move_to":
                new_pos_str = questionary.text(
                    f"Move to position (1-{len(current)})"
                ).ask()
                if not new_pos_str:
                    continue
                try:
                    new_pos = int(new_pos_str)
                except ValueError:
                    rich_print("[red]Invalid position.[/red]")
                    continue
                new_pos = max(1, min(len(current), new_pos))
                current.pop(index)
                current.insert(new_pos - 1, selected_viz_id)
                mark_dirty()
            config.dashboard.overview_charts = current
            continue

        if choice == "reset":
            confirm = questionary.confirm(
                "Reset overview charts to defaults?", default=False
            ).ask()
            if confirm:
                config.dashboard.overview_charts = get_default_overview_charts()
                mark_dirty()
            continue

        if choice == "preview":
            _print_overview_preview(config.dashboard.overview_charts or [], registry_map)
            continue

        if choice == "missing_behavior":
            selected = questionary.select(
                "Missing chart behavior",
                choices=[
                    questionary.Choice("Skip missing charts", value="skip"),
                    questionary.Choice("Show placeholder", value="show_placeholder"),
                ],
                default=config.dashboard.overview_missing_behavior,
            ).ask()
            if selected:
                config.dashboard.overview_missing_behavior = selected
                mark_dirty()
            continue

        if choice == "max_items":
            current = config.dashboard.overview_max_items
            default = "" if current is None else str(current)
            entered = questionary.text(
                "Max overview items (blank for no limit)", default=default
            ).ask()
            if entered is None:
                continue
            entered = entered.strip()
            if entered == "":
                config.dashboard.overview_max_items = None
                mark_dirty()
                continue
            try:
                value = int(entered)
            except ValueError:
                rich_print("[red]Invalid number.[/red]")
                continue
            if value <= 0:
                rich_print("[red]Value must be > 0.[/red]")
                continue
            config.dashboard.overview_max_items = value
            mark_dirty()
