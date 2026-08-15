"""User-configurable merge source profiles (match + day/gap grouping).

Persisted under ``CONFIG_DIR/audio_merge_profiles.json``. Builtin defaults preserve
the 2afe3ad voice-note behaviour (20-minute consecutive gap); users can retune
per profile (e.g. WhatsApp 2h, Telegram 6h, Zoom full day).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from transcriptx.core.utils.paths import CONFIG_DIR
from transcriptx.io.atomic_json import locked_path, write_bytes_atomic

SCHEMA_VERSION = 1
PROFILES_FILENAME = "audio_merge_profiles.json"

MatchKind = Literal["voice_note_family", "filename_regex", "builtin_serial"]
GroupingMode = Literal["serial", "time_window"]

# Default consecutive gap matches SerialDetectionConfig.voice_note_max_gap_seconds.
DEFAULT_VOICE_NOTE_GAP_HOURS = 20.0 / 60.0  # 20 minutes

_SERIAL_RULES: tuple[str, ...] = (
    "timestamp_suffix",
    "part_suffix",
    "numeric_index",
    "duplicate_suffix",
)


class MatchSpecModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: MatchKind
    families: list[str] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)
    builtin_rules: list[str] = Field(default_factory=list)

    @field_validator("patterns")
    @classmethod
    def _validate_patterns(cls, value: list[str]) -> list[str]:
        out: list[str] = []
        for raw in value:
            pattern = str(raw).strip()
            if not pattern:
                continue
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"Invalid regex {pattern!r}: {exc}") from exc
            out.append(pattern)
        return out

    @field_validator("builtin_rules")
    @classmethod
    def _validate_builtin_rules(cls, value: list[str]) -> list[str]:
        known = set(_SERIAL_RULES)
        out: list[str] = []
        for rule in value:
            name = str(rule).strip()
            if name not in known:
                raise ValueError(f"Unknown serial rule {name!r}")
            if name not in out:
                out.append(name)
        return out

    @model_validator(mode="after")
    def _require_match_payload(self) -> MatchSpecModel:
        if self.kind == "voice_note_family" and not self.families:
            raise ValueError("voice_note_family profiles need at least one family")
        if self.kind == "filename_regex" and not self.patterns:
            raise ValueError("filename_regex profiles need at least one pattern")
        if self.kind == "builtin_serial" and not self.builtin_rules:
            raise ValueError("builtin_serial profiles need at least one rule")
        return self


class GroupingSpecModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: GroupingMode = "time_window"
    same_day_days: int = Field(default=0, ge=0, le=30)
    max_gap_hours: float = Field(default=DEFAULT_VOICE_NOTE_GAP_HOURS, ge=0.0, le=168.0)


class MergeSourceProfileModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    enabled: bool = True
    builtin: bool = False
    match: MatchSpecModel
    grouping: GroupingSpecModel = Field(default_factory=GroupingSpecModel)
    priority: int = 100

    @field_validator("id")
    @classmethod
    def _slug_id(cls, value: str) -> str:
        slug = str(value).strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", slug):
            raise ValueError(
                "Profile id must be a lowercase slug (letters, digits, _-)"
            )
        return slug


class MergeProfilesFileModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = SCHEMA_VERSION
    profiles: list[MergeSourceProfileModel] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> MergeProfilesFileModel:
        seen: set[str] = set()
        for profile in self.profiles:
            if profile.id in seen:
                raise ValueError(f"Duplicate profile id {profile.id!r}")
            seen.add(profile.id)
        return self


@dataclass(frozen=True)
class MatchSpec:
    kind: MatchKind
    families: tuple[str, ...] = ()
    patterns: tuple[str, ...] = ()
    builtin_rules: tuple[str, ...] = ()


@dataclass(frozen=True)
class GroupingSpec:
    mode: GroupingMode = "time_window"
    same_day_days: int = 0
    max_gap_hours: float = DEFAULT_VOICE_NOTE_GAP_HOURS


@dataclass(frozen=True)
class MergeSourceProfile:
    id: str
    name: str
    enabled: bool
    builtin: bool
    match: MatchSpec
    grouping: GroupingSpec = field(default_factory=GroupingSpec)
    priority: int = 100


def _family_profile(
    profile_id: str,
    name: str,
    families: tuple[str, ...],
    *,
    priority: int,
) -> MergeSourceProfile:
    return MergeSourceProfile(
        id=profile_id,
        name=name,
        enabled=True,
        builtin=True,
        match=MatchSpec(kind="voice_note_family", families=families),
        grouping=GroupingSpec(
            mode="time_window",
            same_day_days=0,
            max_gap_hours=DEFAULT_VOICE_NOTE_GAP_HOURS,
        ),
        priority=priority,
    )


def builtin_merge_source_profiles() -> tuple[MergeSourceProfile, ...]:
    """Factory defaults: serial always-merge + voice-note families at 20 minutes."""
    return (
        MergeSourceProfile(
            id="serial_parts",
            name="Serial parts",
            enabled=True,
            builtin=True,
            match=MatchSpec(kind="builtin_serial", builtin_rules=_SERIAL_RULES),
            grouping=GroupingSpec(mode="serial", same_day_days=0, max_gap_hours=0.0),
            priority=10,
        ),
        _family_profile(
            "whatsapp",
            "WhatsApp",
            ("WhatsApp Audio", "WhatsApp Voice Notes", "WhatsApp PTT", "WhatsApp"),
            priority=20,
        ),
        _family_profile("telegram", "Telegram", ("Telegram Audio",), priority=30),
        _family_profile("signal", "Signal", ("Signal",), priority=40),
        _family_profile(
            "zoom_recorder",
            "Zoom Recorder",
            ("Zoom Recorder",),
            priority=50,
        ),
        _family_profile(
            "instagram",
            "Instagram / Messenger",
            ("Instagram Audio", "Messenger Audio"),
            priority=60,
        ),
        _family_profile(
            "android_recorder",
            "Android Recorder",
            ("Android Recorder",),
            priority=70,
        ),
        _family_profile(
            "philips",
            "Philips VoiceTracer",
            ("Philips VoiceTracer",),
            priority=80,
        ),
        _family_profile("sony_icd", "Sony ICD", ("Sony ICD",), priority=90),
        _family_profile(
            "device_recorder",
            "Device Recorder",
            ("Device Recorder",),
            priority=100,
        ),
        _family_profile("tascam", "Tascam", ("Tascam",), priority=110),
        _family_profile(
            "voice_message",
            "Voice Message / Viber",
            ("Voice Message", "Viber Voice"),
            priority=120,
        ),
    )


def profiles_path(config_dir: Path | None = None) -> Path:
    root = Path(config_dir) if config_dir is not None else Path(CONFIG_DIR)
    return root / PROFILES_FILENAME


def profile_to_dict(profile: MergeSourceProfile) -> dict[str, Any]:
    return {
        "id": profile.id,
        "name": profile.name,
        "enabled": profile.enabled,
        "builtin": profile.builtin,
        "match": {
            "kind": profile.match.kind,
            "families": list(profile.match.families),
            "patterns": list(profile.match.patterns),
            "builtin_rules": list(profile.match.builtin_rules),
        },
        "grouping": {
            "mode": profile.grouping.mode,
            "same_day_days": profile.grouping.same_day_days,
            "max_gap_hours": profile.grouping.max_gap_hours,
        },
        "priority": profile.priority,
    }


def profile_from_model(model: MergeSourceProfileModel) -> MergeSourceProfile:
    return MergeSourceProfile(
        id=model.id,
        name=model.name,
        enabled=model.enabled,
        builtin=model.builtin,
        match=MatchSpec(
            kind=model.match.kind,
            families=tuple(model.match.families),
            patterns=tuple(model.match.patterns),
            builtin_rules=tuple(model.match.builtin_rules),
        ),
        grouping=GroupingSpec(
            mode=model.grouping.mode,
            same_day_days=model.grouping.same_day_days,
            max_gap_hours=float(model.grouping.max_gap_hours),
        ),
        priority=int(model.priority),
    )


def validate_profiles_payload(
    payload: dict[str, Any] | list[Any],
) -> list[MergeSourceProfile]:
    """Validate a file payload or bare profile list; return runtime profiles."""
    if isinstance(payload, list):
        envelope = {"schema_version": SCHEMA_VERSION, "profiles": payload}
    elif isinstance(payload, dict):
        envelope = payload
    else:
        raise TypeError("Profiles payload must be an object or list")
    model = MergeProfilesFileModel.model_validate(envelope)
    return [profile_from_model(item) for item in model.profiles]


def family_matches(family: str, configured: Iterable[str]) -> bool:
    """True when a parsed voice-note family matches a profile family list."""
    needle = (family or "").strip().lower()
    if not needle:
        return False
    for raw in configured:
        target = (raw or "").strip().lower()
        if not target:
            continue
        if (
            needle == target
            or needle.startswith(target + " ")
            or target.startswith(needle)
        ):
            return True
    return False


def _merge_with_builtins(
    loaded: Iterable[MergeSourceProfile],
) -> list[MergeSourceProfile]:
    """Keep user edits by id; append any missing builtin ids."""
    by_id = {p.id: p for p in loaded}
    builtins = {p.id: p for p in builtin_merge_source_profiles()}
    out: list[MergeSourceProfile] = []
    for profile in loaded:
        if profile.id in builtins:
            # Builtin flag is sticky; users may edit match/grouping/enabled.
            out.append(replace(profile, builtin=True))
        else:
            out.append(replace(profile, builtin=False))
    for builtin in sorted(builtins.values(), key=lambda p: (p.priority, p.id)):
        if builtin.id not in by_id:
            out.append(builtin)
    return out


def load_merge_source_profiles(
    path: Path | None = None,
) -> list[MergeSourceProfile]:
    """Load profiles from disk, merging builtins. Missing file → builtins only."""
    target = path if path is not None else profiles_path()
    if not target.is_file():
        return list(builtin_merge_source_profiles())
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return list(builtin_merge_source_profiles())
    try:
        loaded = validate_profiles_payload(raw)
    except Exception:
        return list(builtin_merge_source_profiles())
    return _merge_with_builtins(loaded)


def save_merge_source_profiles(
    profiles: Iterable[MergeSourceProfile],
    path: Path | None = None,
) -> Path:
    """Validate and atomically write profiles."""
    target = path if path is not None else profiles_path()
    validated = validate_profiles_payload(
        {
            "schema_version": SCHEMA_VERSION,
            "profiles": [profile_to_dict(p) for p in profiles],
        }
    )
    # Re-apply builtin merge so missing builtins are not silently dropped on save.
    merged = _merge_with_builtins(validated)
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "profiles": [profile_to_dict(p) for p in merged],
    }
    payload = (json.dumps(envelope, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    with locked_path(target):
        write_bytes_atomic(target, payload)
    return target


def reset_builtin_profile(
    profiles: Iterable[MergeSourceProfile],
    profile_id: str,
) -> list[MergeSourceProfile]:
    """Replace one builtin id with its factory default."""
    builtins = {p.id: p for p in builtin_merge_source_profiles()}
    if profile_id not in builtins:
        raise KeyError(f"Not a builtin profile: {profile_id}")
    out: list[MergeSourceProfile] = []
    replaced = False
    for profile in profiles:
        if profile.id == profile_id:
            out.append(builtins[profile_id])
            replaced = True
        else:
            out.append(profile)
    if not replaced:
        out.append(builtins[profile_id])
    return out


def max_gap_hours_to_seconds(hours: float) -> int | None:
    """Return gap seconds, or None when unlimited (0 hours)."""
    if hours <= 0:
        return None
    return int(round(float(hours) * 3600))
