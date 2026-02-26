from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Dict, Iterable, Optional

import yaml

from transcriptx.core.corrections.models import (
    CorrectionMemory,
    CorrectionRule,
    Decision,
)
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


def resolve_project_root(transcript_path: Optional[str] = None) -> Optional[Path]:
    """
    Resolve project root using TranscriptX conventions, git root, or cwd.
    """
    # 1) TranscriptX project root (if available)
    try:
        from transcriptx.core.utils.paths import PROJECT_ROOT

        if PROJECT_ROOT and Path(PROJECT_ROOT).exists():
            project_root = Path(PROJECT_ROOT).resolve()
            if transcript_path:
                transcript = Path(transcript_path).resolve()
                if project_root in transcript.parents:
                    return project_root
            else:
                return project_root
    except Exception:
        pass

    # 2) Walk up from transcript_path or cwd looking for .git/.transcriptx
    start_path = (
        Path(transcript_path).resolve().parent
        if transcript_path
        else Path.cwd().resolve()
    )
    current = start_path
    while current != current.parent:
        if (current / ".git").exists() or (current / ".transcriptx").exists():
            return current
        if (current / "transcriptx_corrections.yml").exists():
            return current
        current = current.parent

    # 3) Fallback to cwd
    return Path.cwd().resolve()


def _get_global_memory_path() -> Path:
    home = Path.home()
    if platform.system() == "Darwin":
        return (
            home / "Library" / "Application Support" / "transcriptx" / "corrections.yml"
        )
    return home / ".config" / "transcriptx" / "corrections.yml"


def _get_project_memory_path(project_root: Optional[Path]) -> Optional[Path]:
    if not project_root:
        return None
    primary = project_root / "transcriptx_corrections.yml"
    fallback = project_root / ".transcriptx" / "corrections.yml"
    return primary if primary.exists() or not fallback.exists() else fallback


def _load_rules_from_yaml(path: Path) -> Dict[str, CorrectionRule]:
    if not path.exists():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        logger.warning(f"Failed to load corrections from {path}: {exc}")
        return {}

    if isinstance(raw, dict) and "rules" in raw:
        raw = raw["rules"]

    rules: Dict[str, CorrectionRule] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            if not isinstance(value, dict):
                continue
            # Key wins: use key as id when keyed YAML (authoritative)
            if key and isinstance(key, str):
                existing_id = value.get("id")
                if existing_id is not None and str(existing_id) != str(key):
                    logger.warning(
                        f"YAML key {key!r} overrides rule id {existing_id!r} in {path}"
                    )
                value = {**value, "id": key}
            try:
                rule = CorrectionRule.model_validate(value)
                rules[rule.id] = rule
            except Exception as exc:
                logger.warning(f"Skipping invalid correction rule in {path}: {exc}")
    elif isinstance(raw, list):
        for item in raw:
            try:
                rule = CorrectionRule.model_validate(item)
                rules[rule.id] = rule
            except Exception as exc:
                logger.warning(f"Skipping invalid correction rule in {path}: {exc}")

    return rules


def _load_rules_from_decisions(path: Path) -> Dict[str, CorrectionRule]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"Failed to load decisions from {path}: {exc}")
        return {}

    decisions_raw = payload.get("decisions", payload)
    if not isinstance(decisions_raw, list):
        return {}

    rules: Dict[str, CorrectionRule] = {}
    for item in decisions_raw:
        try:
            decision = Decision.model_validate(item)
        except Exception:
            continue
        if decision.new_rule:
            rules[decision.new_rule.id] = decision.new_rule

    return rules


def load_memory(
    transcript_path: Optional[str] = None,
    transcript_decisions_path: Optional[str] = None,
) -> CorrectionMemory:
    project_root = resolve_project_root(transcript_path)
    global_path = _get_global_memory_path()
    project_path = _get_project_memory_path(project_root)

    global_rules = _load_rules_from_yaml(global_path)
    project_rules = _load_rules_from_yaml(project_path) if project_path else {}

    transcript_rules: Dict[str, CorrectionRule] = {}
    if transcript_decisions_path:
        transcript_rules = _load_rules_from_decisions(Path(transcript_decisions_path))

    memory = CorrectionMemory(rules=global_rules)
    memory = memory.merge(CorrectionMemory(rules=project_rules))
    memory = memory.merge(CorrectionMemory(rules=transcript_rules))
    return memory


def save_memory_layer(layer_path: str | Path, rules: Iterable[CorrectionRule]) -> None:
    path = Path(layer_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"rules": [rule.model_dump() for rule in rules]}
    content = yaml.safe_dump(payload, sort_keys=False)
    tmp_path = path.parent / (path.name + ".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        tmp_path.replace(path)
    except Exception as exc:
        logger.warning(f"Failed to write corrections memory to {path}: {exc}")
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def promote_rule(
    rule: CorrectionRule,
    target_layer: str,
    transcript_path: Optional[str] = None,
) -> Optional[Path]:
    target = target_layer.lower()
    if target == "global":
        path = _get_global_memory_path()
    elif target == "project":
        path = _get_project_memory_path(resolve_project_root(transcript_path))
        if path is None:
            return None
    else:
        raise ValueError(f"Unknown target layer: {target_layer}")

    existing = _load_rules_from_yaml(path)
    # Do not mutate in-memory rule; write a copy with scope=project so file is consistent
    rule_to_save = rule
    if target == "project" and rule.scope != "project":
        rule_to_save = rule.model_copy(update={"scope": "project"})
    existing[rule_to_save.id] = rule_to_save
    save_memory_layer(path, existing.values())
    return path
