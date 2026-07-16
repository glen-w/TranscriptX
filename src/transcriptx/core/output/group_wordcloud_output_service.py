"""OutputService for group pooled wordclouds: Studio tags and pooled semantic metadata."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from transcriptx.core.output.output_service import OutputService
from transcriptx.core.utils.run_writer_locks import RunWriterLease

# Stable basis string for cross-session speaker bucket merge (see plan).
CANONICAL_MERGE_BASIS_VALUE = "canonical_display_from_cross_transcript_normalization"

WORDCLOUD_GROUP_TAGS: List[str] = [
    "group_aggregate",
    "group_visual_special_path",
    "pooled_cross_session",
    "pooled_single_view",
]


class GroupWordcloudOutputService(OutputService):
    """
    Writes under group_run_root/wordclouds/ and merges artifact metadata so
    pooled wordclouds appear under Studio's tag-based Group aggregate filter.
    """

    def __init__(
        self,
        *,
        transcript_path: str,
        module_name: str,
        output_dir: str,
        run_id: str,
        group_uuid: Optional[str],
        canonical_merge_basis: str = CANONICAL_MERGE_BASIS_VALUE,
    ) -> None:
        super().__init__(
            transcript_path,
            module_name,
            output_dir=output_dir,
            run_id=run_id,
        )
        self._group_uuid = group_uuid
        self._canonical_merge_basis = canonical_merge_basis
        self._pooled_per_artifact: Dict[str, Any] = {}

    def prepare_pooled_artifact(
        self,
        *,
        pooled_view_kind: str,
        pooled_input_basis: str,
        pooled_lexicon_scope: str,
    ) -> None:
        """Set metadata applied to the next chart/data/view writes (one logical artifact)."""
        self._pooled_per_artifact = {
            "pooled_view_kind": pooled_view_kind,
            "pooled_input_basis": pooled_input_basis,
            "pooled_lexicon_scope": pooled_lexicon_scope,
        }

    def clear_pooled_artifact_context(self) -> None:
        self._pooled_per_artifact = {}

    def _sticky_pooled_fields(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "agg_id": "wordclouds",
            "canonical_merge_basis": self._canonical_merge_basis,
        }
        if self._group_uuid:
            out["group_uuid"] = self._group_uuid
        return out

    def _record_artifact_metadata(self, path: Any, metadata: Dict[str, Any]) -> None:
        merged: Dict[str, Any] = dict(metadata)
        merged.update(self._sticky_pooled_fields())
        merged.update(self._pooled_per_artifact)
        tags = {str(t) for t in (merged.get("tags") or []) if t is not None}
        tags.update(WORDCLOUD_GROUP_TAGS)
        merged["tags"] = sorted(tags)
        super()._record_artifact_metadata(path, merged)

    def save_data(
        self,
        data: Union[Dict[str, Any], List[Any], str],
        filename: str,
        format_type: str = "json",
        subdirectory: Optional[str] = None,
        speaker: Optional[str] = None,
        *,
        lease: RunWriterLease | None = None,
    ) -> str:
        path_str = super().save_data(
            data,
            filename,
            format_type=format_type,
            subdirectory=subdirectory,
            speaker=speaker,
            lease=lease,
        )
        if not path_str or format_type != "json":
            return path_str
        from pathlib import Path

        rel_meta = {
            "module": self.module_name,
            "artifact_kind": "data",
            "name": filename,
            "scope": "speaker" if speaker else "global",
            "speaker": self.resolve_speaker_display(str(speaker)) if speaker else None,
            "run_id": self.run_id,
        }
        self._record_artifact_metadata(Path(path_str), rel_meta)
        return path_str
