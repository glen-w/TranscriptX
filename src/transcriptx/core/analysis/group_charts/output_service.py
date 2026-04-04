"""OutputService subclass that tags group aggregate chart artifacts."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transcriptx.core.output.output_service import OutputService


class GroupChartOutputService(OutputService):
    """
    Writes charts under group_run_root/{module}/charts/... and records
    artifacts_meta tags for manifest union (group_aggregate).
    """

    def __init__(
        self,
        *,
        virtual_transcript_path: str,
        module_name: str,
        output_dir: str,
        run_id: str,
        agg_id: str,
        group_uuid: Optional[str] = None,
    ) -> None:
        super().__init__(
            virtual_transcript_path,
            module_name,
            output_dir=output_dir,
            run_id=run_id,
        )
        self._agg_id = agg_id
        self._group_uuid = group_uuid
        self._group_tags: List[str] = ["group_aggregate"]

    def _record_artifact_metadata(self, path: Any, metadata: Dict[str, Any]) -> None:
        prior_tags = list(metadata.get("tags") or [])
        merged_tags = sorted(set(prior_tags) | set(self._group_tags))
        extra: Dict[str, Any] = {
            **metadata,
            "tags": merged_tags,
            "agg_id": self._agg_id,
        }
        if self._group_uuid:
            extra["group_uuid"] = self._group_uuid
        super()._record_artifact_metadata(path, extra)
