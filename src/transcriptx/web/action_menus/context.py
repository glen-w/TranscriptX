"""Action context, canonical identity, and derived capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from transcriptx.core.utils.paths import OUTPUTS_DIR
from transcriptx.web.action_menus.ids import NavStyle


@dataclass(frozen=True)
class CanonicalIdentity:
    """Validated subject + optional run identity for navigation and export keys."""

    subject_type: str  # "transcript" | "group"
    subject_id: str
    transcript_path: Path | None
    run_id: str | None
    run_dir: Path | None

    @property
    def export_key_suffix(self) -> str:
        run = self.run_id or "norun"
        return f"{self.subject_type}_{self.subject_id}_{run}"


@dataclass(frozen=True)
class ActionContext:
    """Immutable strip context. Capabilities are derived, not stored here."""

    identity: CanonicalIdentity
    widget_identity: str
    nav_style: NavStyle
    instance_prefix: str
    corrections_workspace_available: bool = False
    export_supported: bool = True
    rename_supported: bool = True
    run_completed: bool = False


@dataclass(frozen=True)
class ContextCapabilities:
    subject_type: str
    has_transcript_path: bool
    has_valid_run: bool
    has_completed_compatible_run: bool
    export_supported: bool
    rename_supported: bool
    corrections_workspace_available: bool


class IdentityError(ValueError):
    """Raised when subject/run fields disagree."""


def build_canonical_identity(
    *,
    subject_type: str,
    subject_id: str,
    transcript_path: Path | str | None = None,
    run_id: str | None = None,
    run_dir: Path | str | None = None,
) -> CanonicalIdentity:
    """Build identity and validate run_id against run_dir when both are set."""
    tp: Path | None
    if transcript_path is None or transcript_path == "":
        tp = None
    else:
        tp = Path(transcript_path)

    rd: Path | None
    if run_dir is None or run_dir == "":
        rd = None
    else:
        rd = Path(run_dir)

    rid = (run_id or "").strip() or None

    if rid is not None and rd is not None:
        if rd.name != rid:
            raise IdentityError(
                f"run_id {rid!r} does not match run_dir name {rd.name!r}"
            )
    if rid is not None and rd is None:
        raise IdentityError("run_id set without run_dir")
    if rd is not None and rid is None:
        raise IdentityError("run_dir set without run_id")

    if subject_type not in ("transcript", "group"):
        raise IdentityError(f"unsupported subject_type: {subject_type!r}")
    if not (subject_id or "").strip():
        raise IdentityError("subject_id is required")

    return CanonicalIdentity(
        subject_type=subject_type,
        subject_id=subject_id.strip(),
        transcript_path=tp,
        run_id=rid,
        run_dir=rd,
    )


def build_transcript_identity_with_run(
    *,
    subject_id: str,
    transcript_path: Path | str | None = None,
    run_id: str | None = None,
) -> CanonicalIdentity:
    """Transcript identity; pairs ``run_id`` with ``OUTPUTS_DIR/subject_id/run_id``."""
    rid = (run_id or "").strip() or None
    run_dir = Path(OUTPUTS_DIR) / subject_id.strip() / rid if rid else None
    return build_canonical_identity(
        subject_type="transcript",
        subject_id=subject_id,
        transcript_path=transcript_path,
        run_id=rid,
        run_dir=run_dir,
    )


def capabilities_from_context(ctx: ActionContext) -> ContextCapabilities:
    """Pure derivation of availability flags from ActionContext."""
    ident = ctx.identity
    has_tp = False
    if ident.transcript_path is not None:
        try:
            has_tp = ident.transcript_path.is_file() or ident.transcript_path.exists()
        except OSError:
            has_tp = False

    has_run = False
    if (
        ident.run_id
        and ident.run_dir is not None
        and ident.run_dir.name == ident.run_id
    ):
        has_run = True
        try:
            # A path that exists as a file (not a directory) is stale/invalid.
            # Missing paths stay valid so navigation can still establish run context.
            if ident.run_dir.is_file():
                has_run = False
        except OSError:
            has_run = False

    completed = bool(has_run and ctx.run_completed)
    export_ok = bool(has_run and ctx.export_supported)
    rename_ok = bool(ctx.rename_supported and ident.transcript_path is not None)
    corrections_ok = bool(
        ident.subject_type == "transcript"
        and has_tp
        and ctx.corrections_workspace_available
    )

    return ContextCapabilities(
        subject_type=ident.subject_type,
        has_transcript_path=has_tp,
        has_valid_run=has_run,
        has_completed_compatible_run=completed,
        export_supported=export_ok,
        rename_supported=rename_ok,
        corrections_workspace_available=corrections_ok,
    )
