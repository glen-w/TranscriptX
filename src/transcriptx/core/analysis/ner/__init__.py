"""
Named Entity Recognition (NER) Module for TranscriptX.
"""

from __future__ import annotations
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.utils.config import get_config
from transcriptx.utils.text_utils import is_named_speaker
from transcriptx.utils.html_utils import wrap_tooltip_text
from transcriptx.utils.location_cache import geocode_with_cache
from transcriptx.core.utils.viz_ids import (
    VIZ_NER_ENTITY_TYPES_GLOBAL,
    VIZ_NER_ENTITY_TYPES_SPEAKER,
)
from transcriptx.core.viz.specs import BarCategoricalSpec


def _get_ner_nlp():
    from transcriptx.core.utils.nlp_runtime import get_nlp_model

    config = get_config()
    if getattr(config.analysis, "ner_use_light_model", False):
        try:
            return get_nlp_model("en_core_web_sm")
        except Exception:
            return get_nlp_model("en_core_web_md")
    return get_nlp_model()


def extract_named_entities(text: str) -> list:
    """Extract named entities from text using spaCy."""
    doc = _get_ner_nlp()(text)
    return [(ent.text, ent.label_) for ent in doc.ents]


class NERAnalysis(AnalysisModule):
    """
    Named Entity Recognition analysis module.

    This module extracts named entities from transcript segments and provides:
    - Entity counts per speaker
    - Entity type distribution
    - Location mapping with geocoding
    - Visualizations and maps
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the NER analysis module."""
        super().__init__(config)
        self.module_name = "ner"
        self.config = get_config()
        self.nlp = _get_ner_nlp()

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Perform NER analysis on transcript segments (pure logic, no I/O).

        Uses database-driven speaker identification. speaker_map parameter is deprecated
        and no longer used - speaker names come directly from segments.

        Args:
            segments: List of transcript segments (should have speaker_db_id for proper identification)
            speaker_map: Deprecated - Speaker ID to name mapping (kept for backward compatibility only, not used)

        Returns:
            Dictionary containing NER analysis results
        """
        from transcriptx.core.utils.speaker_extraction import (
            extract_speaker_info,
            get_speaker_display_name,
        )

        # Apply segment limits from config to prevent timeouts
        max_segments = getattr(self.config.analysis, "ner_max_segments", 5000)
        batch_size = getattr(self.config.analysis, "ner_batch_size", 100)

        # Limit segments if transcript is very large
        if len(segments) > max_segments:
            print(
                f"Large transcript detected ({len(segments)} segments). "
                f"Limiting to {max_segments} segments for NER analysis."
            )
            segments = segments[:max_segments]

        total_segments = len(segments)
        print(f"Processing {total_segments} segments for NER analysis...")

        entity_counts_per_speaker = defaultdict(Counter)
        label_counts_per_speaker = defaultdict(Counter)
        location_entities_per_speaker = defaultdict(Counter)
        entity_sentences_per_speaker = defaultdict(lambda: defaultdict(list))

        # Process segments in batches
        for i in range(0, total_segments, batch_size):
            batch = segments[i : i + batch_size]
            print(
                f"Processing batch {i//batch_size + 1}/{(total_segments + batch_size - 1)//batch_size} "
                f"({len(batch)} segments)"
            )

            for seg in batch:
                speaker_info = extract_speaker_info(seg)
                if speaker_info is None:
                    continue
                speaker = get_speaker_display_name(
                    speaker_info.grouping_key, [seg], segments
                )
                if not speaker or not is_named_speaker(speaker):
                    continue

                text = seg.get("text", "")
                entities = extract_named_entities(text)

                for ent_text, label in entities:
                    entity_counts_per_speaker[speaker][ent_text] += 1
                    label_counts_per_speaker[speaker][label] += 1
                    entity_sentences_per_speaker[speaker][ent_text].append(text)
                    if label in {"GPE", "LOC"}:
                        location_entities_per_speaker[speaker][ent_text] += 1

        print("NER processing complete.")

        # Aggregate all speaker entities
        all_entity_counter = Counter()
        all_sentences = defaultdict(list)
        for speaker, ents in entity_counts_per_speaker.items():
            if not is_named_speaker(speaker):
                continue
            for ent, count in ents.items():
                all_entity_counter[ent] += count
                all_sentences[ent].extend(entity_sentences_per_speaker[speaker][ent])

        # Prepare summary data
        summary_json = {
            speaker: dict(counter)
            for speaker, counter in entity_counts_per_speaker.items()
            if is_named_speaker(speaker)
        }

        # Prepare per-speaker CSV rows
        speaker_csv_rows = {}
        for speaker, ents in entity_counts_per_speaker.items():
            if not is_named_speaker(speaker):
                continue
            rows = [
                [ent, count, " | ".join(entity_sentences_per_speaker[speaker][ent])]
                for ent, count in ents.most_common(100)
            ]
            speaker_csv_rows[speaker] = rows

        # Prepare all-entities CSV rows
        all_rows = [
            [ent, count, " | ".join(all_sentences[ent])]
            for ent, count in all_entity_counter.most_common(200)
        ]

        # Aggregate label counts globally
        all_label_counter = Counter()
        for speaker, labels in label_counts_per_speaker.items():
            if not is_named_speaker(speaker):
                continue
            for label, count in labels.items():
                all_label_counter[label] += count

        result = {
            "entity_counts_per_speaker": dict(entity_counts_per_speaker),
            "label_counts_per_speaker": dict(label_counts_per_speaker),
            "location_entities_per_speaker": dict(location_entities_per_speaker),
            "entity_sentences_per_speaker": {
                k: dict(v) for k, v in entity_sentences_per_speaker.items()
            },
            "summary_json": summary_json,
            "speaker_csv_rows": speaker_csv_rows,
            "all_rows": all_rows,
            "all_label_counter": dict(all_label_counter),
        }
        # Backward-compatible keys for tests/legacy consumers
        result["entities"] = list(all_entity_counter.keys())
        result["segments"] = segments
        return result

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        """
        Save results using OutputService (new interface).

        Args:
            results: Analysis results dictionary
            output_service: OutputService instance
        """
        entity_counts_per_speaker = results["entity_counts_per_speaker"]
        label_counts_per_speaker = results["label_counts_per_speaker"]
        location_entities_per_speaker = results["location_entities_per_speaker"]
        entity_sentences_per_speaker = results["entity_sentences_per_speaker"]
        summary_json = results["summary_json"]
        speaker_csv_rows = results["speaker_csv_rows"]
        all_rows = results["all_rows"]
        all_label_counter = results["all_label_counter"]
        # speaker_map is no longer used - speaker names come from segments
        base_name = output_service.base_name

        # Save summary JSON
        output_service.save_data(summary_json, "ner-entities", format_type="json")

        # Save all entities CSV
        output_service.save_data(all_rows, "ner-entities-ALL", format_type="csv")

        # Save per-speaker data and charts
        for speaker, ents in entity_counts_per_speaker.items():
            if not is_named_speaker(speaker):
                continue

            # Speaker is already a display name from segments
            display_name = speaker

            # Save speaker CSV
            if speaker in speaker_csv_rows:
                output_service.save_data(
                    speaker_csv_rows[speaker],
                    f"ner-entities-{display_name}",
                    format_type="csv",
                    subdirectory="speakers",
                )

            # Create entity types chart
            labels = label_counts_per_speaker.get(speaker, Counter())
            if labels:
                spec = BarCategoricalSpec(
                    viz_id=VIZ_NER_ENTITY_TYPES_SPEAKER,
                    module=self.module_name,
                    name="ner-types",
                    scope="speaker",
                    speaker=display_name,
                    chart_intent="bar_categorical",
                    title=f"Entity Types: {display_name}",
                    x_label="Entity Type",
                    y_label="Count",
                    categories=list(labels.keys()),
                    values=list(labels.values()),
                )
                output_service.save_chart(spec, chart_type="entity_types")

        # Create global entity types chart only when more than one identified speaker
        named_speakers = [s for s in entity_counts_per_speaker if is_named_speaker(s)]
        if all_label_counter and len(named_speakers) > 1:
            labels = Counter(all_label_counter)
            spec = BarCategoricalSpec(
                viz_id=VIZ_NER_ENTITY_TYPES_GLOBAL,
                module=self.module_name,
                name="ner-types-ALL",
                scope="global",
                chart_intent="bar_categorical",
                title="Entity Types: ALL",
                x_label="Entity Type",
                y_label="Count",
                categories=list(labels.keys()),
                values=list(labels.values()),
            )
            output_service.save_chart(spec, chart_type="entity_types")

        # Handle geocoding and maps (special directory structure)
        if getattr(self.config.analysis, "ner_include_geocoding", True):
            self._save_location_maps(
                location_entities_per_speaker,
                entity_sentences_per_speaker,
                output_service,
            )

        # Save summary text file
        summary_text = self._generate_summary_text(entity_counts_per_speaker)
        output_service.save_data(summary_text, "ner-summary", format_type="txt")

        # Save summary JSON
        speaker_stats = {
            speaker: dict(counter)
            for speaker, counter in entity_counts_per_speaker.items()
            if is_named_speaker(speaker)
        }
        global_stats = dict(all_label_counter)

        output_service.save_summary(global_stats, speaker_stats, analysis_metadata={})

    def _create_entity_types_chart(self, speaker_name: str, labels: Counter):
        """Create entity types bar chart."""
        return None

    def _generate_summary_text(self, entity_counts_per_speaker: Dict) -> str:
        """Generate summary text file content."""
        lines = []
        for speaker, ents in entity_counts_per_speaker.items():
            if not is_named_speaker(speaker):
                continue
            lines.append(f"Speaker: {speaker}\n")
            for ent, count in ents.most_common(15):
                lines.append(f"  {ent}: {count}\n")
            lines.append("\n")
        return "".join(lines)

    def _save_location_maps(
        self,
        location_entities_per_speaker: Dict,
        entity_sentences_per_speaker: Dict,
        output_service: "OutputService",
    ) -> None:
        """Save location maps with geocoding."""
        from transcriptx.core.utils.lazy_imports import (
            get_folium,
            get_playwright_sync_api,
        )

        folium = get_folium()
        # Lazy load Playwright with runtime installation support
        # Returns None if playwright or browser cannot be installed
        # Pass silent=False to show installation progress
        sync_playwright = get_playwright_sync_api(silent=False)

        # Create maps directories (not part of standard output structure)
        output_structure = output_service.get_output_structure()
        maps_dir = output_structure.module_dir / "maps"
        html_dir = maps_dir / "html"
        image_dir = maps_dir / "images"
        for d in [html_dir, image_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Filter for named speakers only
        filtered_locations = {
            speaker: counter
            for speaker, counter in location_entities_per_speaker.items()
            if is_named_speaker(speaker)
        }

        per_speaker_coords = {}
        global_coord_records = []
        base_name = output_service.base_name

        for speaker, counter in filtered_locations.items():
            # Speaker is already a display name from segments
            if not is_named_speaker(speaker):
                continue
            display_name = speaker

            coords = geocode_with_cache(counter.items())
            enriched = []
            for loc in coords:
                name = loc["name"]
                sentence = next(
                    iter(entity_sentences_per_speaker.get(speaker, {}).get(name, [])),
                    "",
                )
                enriched.append(
                    {
                        **loc,
                        "speaker": display_name,
                        "sentence": sentence,
                    }
                )
                global_coord_records.append(
                    {
                        **loc,
                        "speaker": display_name,
                        "sentence": sentence,
                    }
                )

            per_speaker_coords[display_name] = enriched

            if enriched:
                # Create per-speaker map
                fmap = folium.Map(zoom_start=3)
                for loc in enriched:
                    folium.Marker(
                        [loc["lat"], loc["lon"]],
                        tooltip=wrap_tooltip_text(
                            loc["name"],
                            speaker=loc["speaker"],
                            sentence=loc["sentence"],
                        ),
                        popup=folium.Popup(
                            wrap_tooltip_text(
                                loc["name"],
                                speaker=loc["speaker"],
                                sentence=loc["sentence"],
                            ),
                            max_width=300,
                        ),
                    ).add_to(fmap)

                safe = display_name.replace(" ", "_")
                html_path = html_dir / f"{base_name}-locations-{safe}.html"
                png_path = image_dir / f"{base_name}-locations-{safe}.png"
                fmap.save(str(html_path))
                # Record HTML map as dynamic artifact
                output_service._record_artifact(html_path, "html", artifact_role="primary")
                output_service._record_artifact_metadata(
                    html_path,
                    {
                        "title": f"Location Map: {display_name}",
                        "format": "html",
                        "render_hint": "dynamic",
                        "renderer": "folium",
                        "scope": "speaker",
                        "speaker": display_name,
                    },
                )
                self._render_html_to_png(html_path, png_path, sync_playwright)
                # Record PNG map as static artifact (if created)
                if png_path.exists():
                    output_service._record_artifact(png_path, "png", artifact_role="primary")
                    output_service._record_artifact_metadata(
                        png_path,
                        {
                            "title": f"Location Map: {display_name}",
                            "format": "png",
                            "render_hint": "static",
                            "renderer": "playwright",
                            "scope": "speaker",
                            "speaker": display_name,
                        },
                    )

        # Create global map only when more than one identified speaker
        if global_coord_records and len(filtered_locations) > 1:
            fmap = folium.Map(zoom_start=2)
            for loc in global_coord_records:
                folium.Marker(
                    [loc["lat"], loc["lon"]],
                    tooltip=wrap_tooltip_text(
                        loc["name"], speaker=loc["speaker"], sentence=loc["sentence"]
                    ),
                    popup=folium.Popup(
                        wrap_tooltip_text(
                            loc["name"],
                            speaker=loc["speaker"],
                            sentence=loc["sentence"],
                        ),
                        max_width=300,
                    ),
                ).add_to(fmap)
            html_path = html_dir / f"{base_name}-locations-ALL.html"
            png_path = image_dir / f"{base_name}-locations-ALL.png"
            fmap.save(str(html_path))
            # Record HTML map as dynamic artifact
            output_service._record_artifact(html_path, "html", artifact_role="primary")
            output_service._record_artifact_metadata(
                html_path,
                {
                    "title": "Location Map: ALL",
                    "format": "html",
                    "render_hint": "dynamic",
                    "renderer": "folium",
                    "scope": "global",
                },
            )
            self._render_html_to_png(html_path, png_path, sync_playwright)
            # Record PNG map as static artifact (if created)
            if png_path.exists():
                output_service._record_artifact(png_path, "png", artifact_role="primary")
                output_service._record_artifact_metadata(
                    png_path,
                    {
                        "title": "Location Map: ALL",
                        "format": "png",
                        "render_hint": "static",
                        "renderer": "playwright",
                        "scope": "global",
                    },
                )

        # Save location coordinates JSON
        output_service.save_data(
            per_speaker_coords, "ner-locations", format_type="json"
        )

    def _render_html_to_png(
        self, html_path: Path, image_path: Path, sync_playwright: Any = None, width: int = 1000
    ):
        """
        Render HTML map to PNG image.

        Gracefully handles missing Playwright/Chromium by skipping PNG rendering
        but still saving the HTML map. Attempts to auto-install browser if missing.
        """
        if sync_playwright is None:
            warnings.warn(
                f"Playwright not available. Skipping PNG rendering for {html_path.name}. "
                f"HTML map is still available at {html_path}. "
                f"To enable PNG rendering, install playwright: pip install playwright && python -m playwright install chromium",
                UserWarning,
                stacklevel=2,
            )
            return

        uri = html_path.resolve().as_uri()

        def _is_missing_executable_error(exc: Exception) -> bool:
            msg = str(exc).lower()
            return "executable doesn't exist" in msg or "browser_type.launch" in msg

        def _render_with(browser_type: Any, *, launch_kwargs: Dict[str, Any], label: str) -> Exception | None:
            """
            Attempt rendering using a specific Playwright browser type.

            Returns:
                None on success, or the exception on failure.
            """
            browser = None
            try:
                browser = browser_type.launch(**launch_kwargs)
                page = browser.new_page(viewport={"width": width, "height": 800})
                # Folium/Leaflet maps can take a moment to settle.
                page.goto(uri, wait_until="load", timeout=60_000)
                page.wait_for_timeout(1000)
                page.screenshot(path=str(image_path), full_page=True)
                return None
            except Exception as exc:
                return exc
            finally:
                if browser is not None:
                    try:
                        browser.close()
                    except Exception:
                        pass

        def _attempt_render() -> Exception | None:
            with sync_playwright() as p:
                # 1) Prefer system-installed Chrome (often more stable on newer macOS)
                exc = _render_with(
                    p.chromium,
                    launch_kwargs={"headless": True, "channel": "chrome"},
                    label="chrome-channel",
                )
                if exc is None:
                    return None

                # 2) Bundled Playwright Chromium
                exc2 = _render_with(p.chromium, launch_kwargs={"headless": True}, label="chromium")
                if exc2 is None:
                    return None

                # 3) Bundled Chromium again with conservative flags
                exc3 = _render_with(
                    p.chromium,
                    launch_kwargs={
                        "headless": True,
                        "args": [
                            "--disable-gpu",
                            "--disable-dev-shm-usage",
                            "--disable-background-timer-throttling",
                            "--disable-renderer-backgrounding",
                        ],
                    },
                    label="chromium-safe",
                )
                if exc3 is None:
                    return None

                # Return the most informative failure we saw.
                return exc2 if not _is_missing_executable_error(exc2) else (exc3 or exc2 or exc)

        try:
            exc = _attempt_render()
            if exc is None:
                return

            if _is_missing_executable_error(exc):
                # Try to install the browser one more time before giving up
                from transcriptx.core.utils.lazy_imports import _ensure_playwright_browser_installed

                print("Attempting to install Playwright Chromium browser...")
                if _ensure_playwright_browser_installed(silent=False):
                    retry_exc = _attempt_render()
                    if retry_exc is None:
                        return
                    warnings.warn(
                        f"Playwright browser install succeeded but PNG rendering still failed for {html_path.name}: {retry_exc}. "
                        f"HTML map is still available at {html_path}. "
                        f"If you are on a newer macOS version, upgrading Playwright may help.",
                        UserWarning,
                        stacklevel=2,
                    )
                    return

                warnings.warn(
                    f"Playwright Chromium browser not found. Skipping PNG rendering for {html_path.name}. "
                    f"HTML map is still available at {html_path}. "
                    f"To enable PNG rendering, run: python -m playwright install chromium",
                    UserWarning,
                    stacklevel=2,
                )
                return

            warnings.warn(
                f"Failed to render PNG from HTML map {html_path.name}: {exc}. "
                f"HTML map is still available at {html_path}",
                UserWarning,
                stacklevel=2,
            )
        except Exception as e:
            warnings.warn(
                f"Failed to render PNG from HTML map {html_path.name}: {e}. "
                f"HTML map is still available at {html_path}",
                UserWarning,
                stacklevel=2,
            )
