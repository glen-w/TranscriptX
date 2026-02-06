"""
Output Service for TranscriptX.

This module provides a centralized service for handling all file output operations,
ensuring consistent output formats and directory structures across all analysis modules.

Key Features:
- Standardized output directory structure
- Consistent file naming conventions
- Multiple output format support (JSON, CSV, TXT)
- Chart/image saving utilities
- Summary generation
"""

from pathlib import Path
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union, Literal

from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.path_utils import (
    get_canonical_base_name,
    get_transcript_dir,
)
from transcriptx.core.utils.artifact_writer import write_text
from transcriptx.core.utils.output_standards import (
    create_standard_output_structure,
    OutputStructure,
    get_global_static_chart_path,
    get_speaker_static_chart_path,
    get_global_dynamic_chart_path,
    get_speaker_dynamic_chart_path,
    create_summary_json,
)
from transcriptx.core.viz.charts import (
    save_static_chart,
    save_dynamic_chart,
    is_plotly_available,
    warn_missing_plotly_once,
)
from transcriptx.utils.text_utils import is_eligible_named_speaker
from transcriptx.core.viz.mpl_renderer import render_mpl
from transcriptx.core.viz.charts import render_plotly
from transcriptx.core.viz.specs import ChartSpec
from transcriptx.io import save_json, save_csv
from transcriptx.core.utils.artifact_writer import write_text, write_json

logger = get_logger()


class OutputService:
    """
    Service for handling all output operations in TranscriptX.

    This service provides a unified interface for saving analysis results,
    ensuring consistent output formats and directory structures.
    """

    def __init__(
        self,
        transcript_path: str,
        module_name: str,
        output_dir: Optional[str] = None,
        run_id: Optional[str] = None,
        runtime_flags: Optional[Dict[str, Any]] = None,
        output_namespace: Optional[str] = None,
        output_version: Optional[str] = None,
    ):
        """
        Initialize the output service for a specific transcript and module.

        Args:
            transcript_path: Path to the transcript file
            module_name: Name of the analysis module
        """
        self.transcript_path = transcript_path
        self.module_name = module_name
        self.base_name = get_canonical_base_name(transcript_path)
        self.transcript_dir = output_dir or get_transcript_dir(transcript_path)
        self.output_structure = create_standard_output_structure(
            self.transcript_dir,
            module_name,
            output_namespace=output_namespace,
            output_version=output_version,
        )
        self._artifacts: List[Dict[str, Any]] = []
        self._artifact_metadata: Dict[str, Dict[str, Any]] = {}
        self._artifact_metadata_path = (
            Path(self.transcript_dir) / ".transcriptx" / "artifacts_meta.json"
        )
        self._load_artifact_metadata()
        self.run_id = run_id or "unknown"
        self._runtime_flags = runtime_flags if runtime_flags is not None else {}

    def _record_artifact(
        self, path: Path, artifact_type: str, artifact_role: str = "primary"
    ) -> None:
        try:
            relative_path = path.relative_to(Path(self.transcript_dir)).as_posix()
        except ValueError:
            relative_path = path.as_posix()
        self._artifacts.append(
            {
                "path": str(path),
                "relative_path": relative_path,
                "artifact_type": artifact_type,
                "artifact_role": artifact_role,
            }
        )

    def _load_artifact_metadata(self) -> None:
        if not self._artifact_metadata_path.exists():
            return
        try:
            payload = self._artifact_metadata_path.read_text(encoding="utf-8")
            data = json.loads(payload)
            if isinstance(data, dict):
                self._artifact_metadata = data
        except Exception:
            return

    def _record_artifact_metadata(
        self, path: Path | None, metadata: Dict[str, Any]
    ) -> None:
        if not path:
            return
        try:
            relative_path = path.relative_to(Path(self.transcript_dir)).as_posix()
        except ValueError:
            relative_path = path.as_posix()

        existing = self._artifact_metadata.get(relative_path, {})
        merged = {**existing, **metadata}
        self._artifact_metadata[relative_path] = merged
        try:
            write_json(self._artifact_metadata_path, self._artifact_metadata, indent=2)
        except Exception:
            return

    def save_data(
        self,
        data: Union[Dict[str, Any], List[Any], str],
        filename: str,
        format_type: str = "json",
        subdirectory: Optional[str] = None,
        speaker: Optional[str] = None,
    ) -> str:
        """
        Save data in the specified format.

        Args:
            data: Data to save (dict, list, or string)
            filename: Name of the file (without extension)
            format_type: Format to save in ("json", "csv", "txt")
            subdirectory: Optional subdirectory within the module directory

        Returns:
            Path to the saved file
        """
        if speaker is not None and self._should_skip_speaker_artifact(speaker):
            return ""
        if format_type == "json":
            if subdirectory:
                output_dir = self.output_structure.data_dir / subdirectory
                output_dir.mkdir(parents=True, exist_ok=True)
            else:
                output_dir = self.output_structure.global_data_dir

            file_path = output_dir / f"{self.base_name}_{filename}.json"
            save_json(self._apply_speaker_mapping_to_json(data), str(file_path))
            self._record_artifact(file_path, "json")
            logger.debug(f"Saved JSON data to: {file_path}")
            return str(file_path)

        elif format_type == "csv":
            if not isinstance(data, (list, dict)):
                raise ValueError("CSV format requires list or dict data")

            if subdirectory:
                output_dir = self.output_structure.data_dir / subdirectory
                output_dir.mkdir(parents=True, exist_ok=True)
            else:
                output_dir = self.output_structure.global_data_dir

            file_path = output_dir / f"{self.base_name}_{filename}.csv"

            # Convert data to CSV format
            if isinstance(data, list):
                # Assume list of dicts
                if data and isinstance(data[0], dict):
                    mapped_rows = [self._map_speaker_field(row) for row in data]
                    headers = list(mapped_rows[0].keys())
                    rows = [list(row.values()) for row in mapped_rows]
                    save_csv(rows, str(file_path), header=headers)
                else:
                    save_csv(data, str(file_path))
            elif isinstance(data, dict):
                # Convert dict to rows
                mapped = self._apply_speaker_mapping_to_json(data)
                rows = [[k, str(v)] for k, v in mapped.items()]
                save_csv(rows, str(file_path), header=["key", "value"])

            logger.debug(f"Saved CSV data to: {file_path}")
            self._record_artifact(file_path, "csv")
            return str(file_path)

        elif format_type == "txt":
            if subdirectory:
                output_dir = self.output_structure.data_dir / subdirectory
                output_dir.mkdir(parents=True, exist_ok=True)
            else:
                output_dir = self.output_structure.global_data_dir
                # Ensure global_data_dir exists
                output_dir.mkdir(parents=True, exist_ok=True)

            file_path = output_dir / f"{self.base_name}_{filename}.txt"

            if isinstance(data, dict):
                content = (
                    "\n".join([f"{key}: {value}" for key, value in data.items()]) + "\n"
                )
            elif isinstance(data, list):
                content = "\n".join([str(item) for item in data]) + "\n"
            else:
                content = str(data)
            write_text(file_path, content)

            logger.debug(f"Saved TXT data to: {file_path}")
            self._record_artifact(file_path, "txt")
            return str(file_path)

        else:
            raise ValueError(f"Unsupported format type: {format_type}")

    def _should_skip_speaker_artifact(self, speaker: Optional[str]) -> bool:
        if self._runtime_flags.get("include_unidentified_speakers"):
            return False
        if not speaker:
            return False
        config = get_config()
        exclude = getattr(
            getattr(config, "analysis", None),
            "exclude_unidentified_from_speaker_charts",
            False,
        )
        if not exclude:
            return False
        ignored_ids = self._runtime_flags.get("ignored_speaker_ids")
        if not isinstance(ignored_ids, set):
            ignored_ids = set()
        speaker_str = str(speaker)
        aliases = self._runtime_flags.get("speaker_key_aliases", {})
        speaker_key = aliases.get(speaker_str, speaker_str)
        return not is_eligible_named_speaker(
            display_name=speaker_str,
            speaker_id=speaker_key,
            ignored_ids=ignored_ids,
        )

    def resolve_speaker_display(self, speaker_key: Optional[str]) -> Optional[str]:
        if speaker_key is None:
            return None
        if self._runtime_flags.get("anonymise_speakers"):
            mapping = self._runtime_flags.get("speaker_anonymisation_map", {})
            if speaker_key in mapping:
                return mapping.get(speaker_key, speaker_key)
            aliases = self._runtime_flags.get("speaker_key_aliases", {})
            aliased_key = aliases.get(speaker_key)
            if aliased_key:
                return mapping.get(aliased_key, speaker_key)
            return speaker_key
        return speaker_key

    def _map_speaker_field(self, row: Dict[str, Any]) -> Dict[str, Any]:
        if "speaker" not in row:
            return row
        mapped = dict(row)
        mapped["speaker"] = self.resolve_speaker_display(str(row.get("speaker")))
        return mapped

    def _apply_speaker_mapping_to_json(
        self, data: Union[Dict[str, Any], List[Any], str]
    ) -> Union[Dict[str, Any], List[Any], str]:
        mapping = self._runtime_flags.get("speaker_anonymisation_map")
        if not mapping or not self._runtime_flags.get("anonymise_speakers"):
            return data
        if isinstance(data, dict):
            remapped: Dict[str, Any] = {}
            for key, value in data.items():
                mapped_key = mapping.get(str(key), key)
                if isinstance(value, dict):
                    remapped_value = self._map_speaker_field(value)
                elif isinstance(value, list):
                    remapped_value = [
                        self._map_speaker_field(item) if isinstance(item, dict) else item
                        for item in value
                    ]
                else:
                    remapped_value = value
                remapped[mapped_key] = remapped_value
            return remapped
        if isinstance(data, list):
            return [
                self._map_speaker_field(item) if isinstance(item, dict) else item
                for item in data
            ]
        return data

    def save_text(
        self,
        content: str,
        filename: str,
        *,
        ext: str = ".txt",
        subdirectory: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Save text-based artifacts (e.g., .md, .txt, .log).

        Args:
            content: Text content to write
            filename: Base filename (without extension)
            ext: File extension, including leading dot (default: ".txt")
            subdirectory: Optional subdirectory within the module data directory
            metadata: Optional artifact metadata to record

        Returns:
            Path to the saved file
        """
        if not ext.startswith("."):
            ext = f".{ext}"
        if subdirectory:
            output_dir = self.output_structure.data_dir / subdirectory
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = self.output_structure.global_data_dir
            output_dir.mkdir(parents=True, exist_ok=True)

        file_path = output_dir / f"{self.base_name}_{filename}{ext}"
        write_text(file_path, content)
        self._record_artifact(file_path, "txt")
        if metadata:
            self._record_artifact_metadata(file_path, metadata)
        logger.debug(f"Saved text data to: {file_path}")
        return str(file_path)

    def save_view_html(
        self,
        name: str,
        html_content: str,
        *,
        module: str | None = None,
        scope: Literal["global", "speaker"] = "global",
        speaker: str | None = None,
        view_kind: str | None = None,
        viz_id: str | None = None,
        depends_on: List[str] | None = None,
        tags: List[str] | None = None,
        metadata: Dict[str, Any] | None = None,
    ) -> Optional[Path]:
        """
        Save an interactive HTML view artifact (not a ChartSpec).

        Args:
            name: Base filename for the view (without extension)
            html_content: Full HTML content to write
            module: Optional module name override for metadata
            scope: "global" or "speaker"
            speaker: Speaker name if scope="speaker"
            view_kind: View type identifier (e.g. "wordcloud_explorer")
            viz_id: Optional stable visualization identifier
            depends_on: Artifact-relative paths within run this view depends on
            tags: Optional list of tags
            metadata: Additional metadata to merge

        Returns:
            Path to the saved HTML file
        """
        if scope == "speaker":
            if not speaker:
                raise ValueError("speaker is required when scope='speaker'")
            if self._should_skip_speaker_artifact(speaker):
                return None
            speaker_display = self.resolve_speaker_display(str(speaker))
            safe_speaker = str(speaker_display).replace(" ", "_").replace("/", "_")
            view_dir = (
                Path(self.output_structure.speaker_dynamic_charts_dir)
                / safe_speaker
                / "dynamic"
                / "views"
            )
        else:
            view_dir = Path(self.output_structure.global_dynamic_charts_dir) / "views"

        view_dir.mkdir(parents=True, exist_ok=True)
        file_path = view_dir / f"{self.base_name}_{name}.html"
        write_text(file_path, html_content)
        self._record_artifact(file_path, "html", artifact_role="view")

        view_metadata = {
            "viz_id": viz_id,
            "module": module or self.module_name,
            "artifact_kind": "view",
            "view_kind": view_kind,
            "scope": scope,
            "speaker": self.resolve_speaker_display(str(speaker)) if speaker else None,
            "name": name,
            "depends_on": depends_on or [],
            "tags": tags or [],
            "run_id": self.run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            view_metadata.update(metadata)
        self._record_artifact_metadata(file_path, view_metadata)
        return file_path

    def save_chart(
        self,
        spec: ChartSpec | None = None,
        dpi: int = 300,
        chart_type: Optional[str] = None,
        *,
        chart_id: Optional[str] = None,
        scope: Optional[Literal["global", "speaker"]] = None,
        speaker: Optional[str] = None,
        static_fig: Optional[Any] = None,
        dynamic_fig: Optional[Any] = None,
        viz_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Dict[str, Optional[Path]]:
        """
        Save static and/or dynamic charts.

        Args:
            spec: ChartSpec object defining the chart intent and payload
            dpi: DPI for static chart
            chart_type: Optional subdirectory for chart type
            chart_id: Legacy chart identifier (used with static_fig/dynamic_fig)
            scope: "global" or "speaker" (required for legacy usage)
            speaker: Speaker name (required if scope="speaker")
            static_fig: Matplotlib figure (legacy usage)
            dynamic_fig: Plotly figure (legacy usage)
            viz_id: Stable visualization identifier (preferred for legacy usage)
            title: Optional display title override (legacy usage)
        """
        if spec is not None:
            return self._save_chart_spec(spec, dpi=dpi, chart_type=chart_type)
        return self._save_chart_legacy(
            chart_id=chart_id,
            scope=scope,
            speaker=speaker,
            static_fig=static_fig,
            dynamic_fig=dynamic_fig,
            dpi=dpi,
            chart_type=chart_type,
            viz_id=viz_id,
            title=title,
        )

    def _save_chart_spec(
        self,
        spec: ChartSpec,
        dpi: int = 300,
        chart_type: Optional[str] = None,
    ) -> Dict[str, Optional[Path]]:
        if spec.scope == "speaker" and not spec.speaker:
            raise ValueError("speaker is required when scope='speaker'")
        if spec.scope == "speaker" and self._should_skip_speaker_artifact(spec.speaker):
            return {"static": None, "dynamic": None}

        if spec.scope == "speaker":
            speaker_display = self.resolve_speaker_display(str(spec.speaker))
            static_path = get_speaker_static_chart_path(
                self.output_structure,
                None,
                speaker_display,
                spec.name,
                chart_type,
            )
            dynamic_path = get_speaker_dynamic_chart_path(
                self.output_structure,
                None,
                speaker_display,
                spec.name,
                chart_type,
            )
        else:
            static_path = get_global_static_chart_path(
                self.output_structure, None, spec.name, chart_type
            )
            dynamic_path = get_global_dynamic_chart_path(
                self.output_structure, None, spec.name, chart_type
            )

        derived_viz_id = False
        final_viz_id = spec.viz_id

        created_at = datetime.now(timezone.utc).isoformat()
        base_metadata = {
            "viz_id": final_viz_id,
            "derived": derived_viz_id,
            "module": spec.module,
            "artifact_kind": "chart",
            "scope": spec.scope,
            "speaker": self.resolve_speaker_display(str(spec.speaker))
            if spec.speaker
            else None,
            "name": spec.name,
            "chart_intent": spec.chart_intent,
            "chart_type": chart_type,
            "title": spec.title,
            "x_label": spec.x_label,
            "y_label": spec.y_label,
            "run_id": self.run_id,
            "created_at": created_at,
        }

        static_result = None
        if static_path:
            static_fig = render_mpl(spec)
            if static_fig is None:
                raise ValueError("render_mpl() returned None for static chart")
            try:
                static_result = save_static_chart(static_fig, static_path, dpi=dpi)
                self._record_artifact(Path(static_result), "png")
                self._record_artifact_metadata(
                    Path(static_result),
                    {
                        **base_metadata,
                        "format": "png",
                        "render_hint": "static",
                        "renderer": "matplotlib",
                    },
                )
            finally:
                # Always close render_mpl-created figures to avoid accumulating open figures
                # during batch analysis runs (which can trigger matplotlib's max_open_warning).
                try:
                    from transcriptx.core.utils.lazy_imports import get_matplotlib_pyplot

                    plt = get_matplotlib_pyplot()
                    plt.close(static_fig)
                except Exception:
                    pass

        dynamic_result = None
        if self.should_generate_dynamic():
            if dynamic_path:
                dynamic_fig = render_plotly(spec)
                if dynamic_fig is not None:
                    dynamic_result = save_dynamic_chart(dynamic_fig, dynamic_path)
                if dynamic_result:
                    self._record_artifact(Path(dynamic_result), "html")
                    self._record_artifact_metadata(
                        Path(dynamic_result),
                        {
                            **base_metadata,
                            "format": "html",
                            "render_hint": "dynamic",
                            "renderer": "plotly",
                        },
                    )

        return {"static": static_result, "dynamic": dynamic_result}

    def _save_chart_legacy(
        self,
        chart_id: Optional[str],
        scope: Optional[Literal["global", "speaker"]],
        speaker: Optional[str],
        static_fig: Optional[Any],
        dynamic_fig: Optional[Any],
        dpi: int,
        chart_type: Optional[str],
        viz_id: Optional[str],
        title: Optional[str],
    ) -> Dict[str, Optional[Path]]:
        if not chart_id:
            raise ValueError("chart_id is required for legacy save_chart() usage")
        if not scope:
            raise ValueError("scope is required for legacy save_chart() usage")
        if static_fig is None:
            raise ValueError("static_fig is required for legacy save_chart() usage")
        if scope == "speaker" and not speaker:
            raise ValueError("speaker is required when scope='speaker'")
        if scope == "speaker" and self._should_skip_speaker_artifact(speaker):
            return {"static": None, "dynamic": None}

        if scope == "speaker":
            speaker_display = self.resolve_speaker_display(str(speaker))
            static_path = get_speaker_static_chart_path(
                self.output_structure,
                None,
                speaker_display,
                chart_id,
                chart_type,
            )
            dynamic_path = get_speaker_dynamic_chart_path(
                self.output_structure,
                None,
                speaker_display,
                chart_id,
                chart_type,
            )
        else:
            static_path = get_global_static_chart_path(
                self.output_structure, None, chart_id, chart_type
            )
            dynamic_path = get_global_dynamic_chart_path(
                self.output_structure, None, chart_id, chart_type
            )

        if viz_id:
            derived_viz_id = False
            final_viz_id = viz_id
        else:
            derived_viz_id = True
            final_viz_id = f"{self.module_name}.{chart_id}.{scope}"

        base_metadata = {
            "viz_id": final_viz_id,
            "derived": derived_viz_id,
            "module": self.module_name,
            "scope": scope,
            "speaker": self.resolve_speaker_display(str(speaker)) if speaker else None,
            "chart_id": chart_id,
            "chart_type": chart_type,
            "title": title,
        }

        static_result = None
        if static_path:
            try:
                static_result = save_static_chart(static_fig, static_path, dpi=dpi)
                self._record_artifact(Path(static_result), "png")
                self._record_artifact_metadata(
                    Path(static_result),
                    {
                        **base_metadata,
                        "format": "png",
                        "render_hint": "static",
                    },
                )
            finally:
                # Close legacy matplotlib figures after saving to prevent figure buildup
                # in long-running batch processes.
                try:
                    from transcriptx.core.utils.lazy_imports import get_matplotlib_pyplot

                    plt = get_matplotlib_pyplot()
                    plt.close(static_fig)
                except Exception:
                    pass

        dynamic_result = None
        if dynamic_fig is not None and self.should_generate_dynamic():
            if dynamic_path:
                dynamic_result = save_dynamic_chart(dynamic_fig, dynamic_path)
                if dynamic_result:
                    self._record_artifact(Path(dynamic_result), "html")
                    self._record_artifact_metadata(
                        Path(dynamic_result),
                        {
                            **base_metadata,
                            "format": "html",
                            "render_hint": "dynamic",
                        },
                    )

        return {"static": static_result, "dynamic": dynamic_result}

    def should_generate_dynamic(self) -> bool:
        """Check if dynamic charts should be generated."""
        config = get_config()
        mode = getattr(config.output, "dynamic_charts", "auto")
        if mode == "off":
            return False
        if mode == "on":
            if not is_plotly_available():
                raise RuntimeError(
                    "Plotly is required when dynamic_charts='on'. Install transcriptx[plotly]."
                )
            return True
        if not is_plotly_available():
            warn_missing_plotly_once(self._runtime_flags)
            return False
        return True

    def save_summary(
        self,
        global_data: Dict[str, Any],
        speaker_data: Dict[str, Any],
        analysis_metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """
        Create and save a comprehensive summary JSON file.

        Args:
            global_data: Global analysis results
            speaker_data: Per-speaker analysis results
            analysis_metadata: Optional metadata about the analysis

        Returns:
            Path to the saved summary file
        """
        if analysis_metadata is None:
            analysis_metadata = {}

        summary_path = create_summary_json(
            self.module_name,
            self.base_name,
            global_data,
            speaker_data,
            analysis_metadata,
            self.output_structure,
        )
        if summary_path:
            self._record_artifact(Path(summary_path), "json", artifact_role="summary")
        return summary_path

    def get_artifacts(self) -> List[Dict[str, Any]]:
        return list(self._artifacts)

    def get_output_structure(self) -> OutputStructure:
        """
        Get the output structure for this service.

        Returns:
            OutputStructure object
        """
        return self.output_structure


def create_output_service(
    transcript_path: str,
    module_name: str,
    output_dir: Optional[str] = None,
    run_id: Optional[str] = None,
    runtime_flags: Optional[Dict[str, Any]] = None,
    output_namespace: Optional[str] = None,
    output_version: Optional[str] = None,
) -> OutputService:
    """
    Create an output service for a transcript and module.

    Args:
        transcript_path: Path to the transcript file
        module_name: Name of the analysis module

    Returns:
        OutputService instance
    """
    return OutputService(
        transcript_path,
        module_name,
        output_dir=output_dir,
        run_id=run_id,
        runtime_flags=runtime_flags,
        output_namespace=output_namespace,
        output_version=output_version,
    )
