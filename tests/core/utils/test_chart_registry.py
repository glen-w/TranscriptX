"""Tests for chart registry."""

from __future__ import annotations

"""Tests for chart registry defaults."""

from dataclasses import dataclass
from pathlib import Path

from typing import Any

from transcriptx.core.utils.chart_registry import (
    CHART_DEFINITIONS,
    CROSS_SESSION_SPEAKER_OVERVIEW_ALLOWLIST,
    DEFAULT_GROUP_OVERVIEW_VIZ_IDS,
    DEFAULT_OVERVIEW_VIZ_IDS,
    POOLED_GROUP_OVERVIEW_ALLOWLIST,
    find_chart_definition_for_artifact,
    get_chart_definition,
    get_chart_registry,
    get_default_overview_charts,
    iter_chart_definitions,
    select_preferred_artifacts,
)


def is_acceptable_pooled_group_generator(agg_id: str, gen: Any) -> bool:
    """
    Predicate for pooled-family sync tests.

    Default: reject GenericNumericGroupChartGenerator (pooled must be dedicated).

    Acts: ``ActsGroupChartGenerator`` is the audited pooled path (global pie/bar
    already sum sessions); no separate pooled-only class required.
    """
    from transcriptx.core.analysis.group_charts.acts import ActsGroupChartGenerator
    from transcriptx.core.analysis.group_charts.generic_numeric import (
        GenericNumericGroupChartGenerator,
    )

    if isinstance(gen, GenericNumericGroupChartGenerator):
        return False
    if agg_id == "acts":
        return isinstance(gen, ActsGroupChartGenerator)
    return True


@dataclass
class FakeArtifact:
    id: str
    kind: str
    module: str | None
    scope: str | None
    speaker: str | None
    rel_path: str
    meta: dict | None = None
    title: str | None = None


def test_chart_definitions_json_load_count():
    """Packaged JSON must produce the expected number of definitions (regression guard)."""
    assert len(CHART_DEFINITIONS) == 161
    assert get_chart_definition("sentiment.multi_speaker_sentiment.global") is not None
    assert get_chart_definition("contextual_emotion.label_counts.global") is not None
    assert get_chart_definition("contextual_emotion.label_counts.speaker") is not None
    assert get_chart_definition("fine_grained_emotion.label_counts.global") is not None
    assert get_chart_definition("fine_grained_emotion.label_counts.speaker") is not None
    assert (
        get_chart_definition("contextual_emotion.label_counts_excluding_neutral.global")
        is not None
    )
    assert (
        get_chart_definition("fine_grained_emotion.label_share_non_neutral.global")
        is not None
    )
    assert get_chart_definition("group.pauses.temporal_overlay.global") is not None
    assert get_chart_definition("group.acts.temporal_overlay.global") is not None
    assert get_chart_definition("group.sentiment.temporal_overlay.global") is not None
    assert get_chart_definition("group.emotion.temporal_overlay.global") is not None
    assert (
        get_chart_definition("group.sentiment.cross_session_speaker.pattern")
        is not None
    )
    assert get_chart_definition("group.stats.cross_session_speaker.pattern") is not None
    assert (
        get_chart_definition("group.stats.cross_session_speaker.segment_count.pattern")
        is not None
    )
    assert get_chart_definition("group.ner.pooled.entity_types.global") is not None
    assert get_chart_definition("group.stats.pooled.totals.global") is not None
    assert (
        get_chart_definition("group.interactions.pooled.interruptions_initiated.global")
        is not None
    )
    assert (
        get_chart_definition("group.interactions.pooled.interruptions_received.global")
        is not None
    )
    assert (
        get_chart_definition("group.contagion.pooled.top_directed_edges.global")
        is not None
    )
    assert (
        get_chart_definition(
            "semantic_similarity_v2.speaker_repetition_frequency.global"
        )
        is not None
    )


def test_group_pooled_single_view_family_sync() -> None:
    """Pooled family: dedicated generator (acts audited), contract, defs, overview."""
    from transcriptx.core.analysis.group_charts.registry import (
        GROUP_AGGREGATE_CHART_FAMILIES,
        GROUP_CHART_REGISTRY,
    )

    pooled_contracts = {
        "acts": "group_charts_acts_pooled_contract.md",
        "ner": "group_charts_ner_pooled_contract.md",
        "entity_sentiment": "group_charts_entity_sentiment_pooled_contract.md",
        "topic_modeling": "group_charts_topic_modeling_pooled_contract.md",
        "bertopic": "group_charts_bertopic_pooled_contract.md",
        "emotion": "group_charts_emotion_pooled_contract.md",
        "tics": "group_charts_tics_pooled_contract.md",
        "stats": "group_charts_stats_pooled_contract.md",
        "interactions": "group_charts_interactions_pooled_contract.md",
        "contagion": "group_charts_contagion_pooled_contract.md",
    }
    pooled_viz_ids = {
        "acts": ["group.acts.global_acts_pie.global"],
        "ner": [
            "group.ner.pooled.entity_types.global",
            "group.ner.pooled.top_entities.global",
        ],
        "entity_sentiment": ["group.entity_sentiment.pooled.top_entities.global"],
        "topic_modeling": ["group.topic_modeling.pooled.topic_share.global"],
        "bertopic": ["group.bertopic.pooled.topic_share.global"],
        "emotion": ["group.emotion.pooled.profile.global"],
        "tics": ["group.tics.pooled.by_tic.global"],
        "stats": ["group.stats.pooled.totals.global"],
        "interactions": [
            "group.interactions.pooled.interruptions_initiated.global",
            "group.interactions.pooled.interruptions_received.global",
        ],
        "contagion": ["group.contagion.pooled.top_directed_edges.global"],
    }
    repo_root = Path(__file__).resolve().parents[3]

    pooled_aggs = sorted(
        aid
        for aid, fam in GROUP_AGGREGATE_CHART_FAMILIES.items()
        if "pooled_single_view" in fam
    )
    assert set(pooled_contracts.keys()) == set(pooled_aggs)
    assert set(pooled_viz_ids.keys()) == set(pooled_aggs)

    for agg_id in pooled_aggs:
        gen = GROUP_CHART_REGISTRY[agg_id]
        assert is_acceptable_pooled_group_generator(agg_id, gen), (agg_id, type(gen))
        doc_path = repo_root / "docs" / "groups" / pooled_contracts[agg_id]
        assert doc_path.is_file(), doc_path
        for vid in pooled_viz_ids[agg_id]:
            assert get_chart_definition(vid) is not None, vid
            if vid in DEFAULT_GROUP_OVERVIEW_VIZ_IDS:
                assert vid in POOLED_GROUP_OVERVIEW_ALLOWLIST, vid


def test_relational_pooled_bidirectional_invariant() -> None:
    """Family ↔ allowlisted payload ↔ dedicated generator stay aligned for relational aggs."""
    from transcriptx.core.analysis.group_charts.contagion_pooled_charts import (
        ContagionPooledGroupChartGenerator,
    )
    from transcriptx.core.analysis.group_charts.interactions_charts import (
        InteractionsGroupChartGenerator,
    )
    from transcriptx.core.analysis.group_charts.registry import (
        GROUP_AGGREGATE_CHART_FAMILIES,
        GROUP_CHART_REGISTRY,
    )
    from transcriptx.core.pipeline.chart_outcome import (
        GROUP_CHART_OUTCOME_OPTIONAL_KEYS,
    )

    rel = (
        ("interactions", "interactions_pooled", InteractionsGroupChartGenerator),
        ("contagion", "contagion_pooled", ContagionPooledGroupChartGenerator),
    )
    for agg_id, key, gen_type in rel:
        fam = GROUP_AGGREGATE_CHART_FAMILIES[agg_id]
        has_fam = "pooled_single_view" in fam
        has_key = key in GROUP_CHART_OUTCOME_OPTIONAL_KEYS
        if has_fam:
            assert has_key, agg_id
        if has_key:
            assert has_fam, agg_id
        assert isinstance(GROUP_CHART_REGISTRY[agg_id], gen_type), agg_id


def test_default_group_overview_pooled_requires_allowlist() -> None:
    for vid in DEFAULT_GROUP_OVERVIEW_VIZ_IDS:
        if ".pooled." in vid:
            assert vid in POOLED_GROUP_OVERVIEW_ALLOWLIST, vid


def test_group_temporal_overlay_family_matches_definitions_contracts_and_overview():
    """Authoritative sync: temporal_overlay families, chart defs, docs, default overview."""
    from transcriptx.core.analysis.group_charts.registry import (
        GROUP_AGGREGATE_CHART_FAMILIES,
    )

    temporal_aggs = sorted(
        aid
        for aid, fam in GROUP_AGGREGATE_CHART_FAMILIES.items()
        if "temporal_overlay" in fam
    )
    contract_docs = {
        "acts": "group_charts_acts_temporal_contract.md",
        "emotion": "group_charts_emotion_temporal_contract.md",
        "pauses": "group_charts_pauses_temporal_contract.md",
        "prosody": "group_charts_prosody_temporal_contract.md",
        "sentiment": "group_charts_sentiment_temporal_contract.md",
    }
    assert set(contract_docs.keys()) == set(temporal_aggs), (
        temporal_aggs,
        sorted(contract_docs.keys()),
    )

    repo_root = Path(__file__).resolve().parents[3]
    in_default_group_overview = frozenset({"acts", "sentiment", "pauses", "emotion"})

    for agg_id in temporal_aggs:
        vid = f"group.{agg_id}.temporal_overlay.global"
        assert get_chart_definition(vid) is not None, vid
        doc_path = repo_root / "docs" / "groups" / contract_docs[agg_id]
        assert doc_path.is_file(), doc_path
        if agg_id in in_default_group_overview:
            assert vid in DEFAULT_GROUP_OVERVIEW_VIZ_IDS, vid
        else:
            assert vid not in DEFAULT_GROUP_OVERVIEW_VIZ_IDS, vid


def test_default_group_overview_cross_session_requires_allowlist() -> None:
    for vid in DEFAULT_GROUP_OVERVIEW_VIZ_IDS:
        if "cross_session_speaker" not in vid:
            continue
        assert vid in CROSS_SESSION_SPEAKER_OVERVIEW_ALLOWLIST, vid


def test_cross_session_speaker_family_has_pattern_def_and_contract_doc() -> None:
    from transcriptx.core.analysis.group_charts.registry import (
        GROUP_AGGREGATE_CHART_FAMILIES,
    )

    contracts = {
        "stats": "group_charts_stats_cross_session_contract.md",
        "sentiment": "group_charts_sentiment_cross_session_contract.md",
    }
    repo_root = Path(__file__).resolve().parents[3]
    for agg_id, fam in GROUP_AGGREGATE_CHART_FAMILIES.items():
        if "cross_session_speaker" not in fam:
            continue
        assert agg_id in contracts, agg_id
        pattern_vid = f"group.{agg_id}.cross_session_speaker.pattern"
        assert get_chart_definition(pattern_vid) is not None, pattern_vid
        doc = repo_root / "docs" / "groups" / contracts[agg_id]
        assert doc.is_file(), doc


def test_registry_unique_viz_ids():
    viz_ids = [c.viz_id for c in CHART_DEFINITIONS]
    assert len(viz_ids) == len(set(viz_ids))


def test_registry_fields_are_valid():
    allowed_scopes = {"global", "speaker"}
    allowed_cardinality = {"single", "multi", "speaker_set", "paired_static_dynamic"}
    for chart_def in CHART_DEFINITIONS:
        assert chart_def.viz_id
        assert chart_def.label
        assert isinstance(chart_def.rank_default, int)
        assert chart_def.scope in allowed_scopes
        assert chart_def.cardinality in allowed_cardinality
        matcher = chart_def.match
        assert any(
            [
                matcher.by_viz_id,
                matcher.by_artifact_key_prefix,
                matcher.by_chart_slug_regex,
                matcher.by_filename_glob,
            ]
        )


def test_registry_stability_core_viz_ids():
    core_viz_ids = [
        "sentiment.multi_speaker_sentiment.global",
        "emotion.radar.global",
        "interactions.network.global",
        "interactions.dominance.global",
        "temporal_dynamics.temporal_dashboard.global",
        "wordcloud.wordcloud.global.basic",
    ]
    for viz_id in core_viz_ids:
        assert get_chart_definition(viz_id) is not None


def test_semantic_similarity_v2_chart_definitions_match_artifacts():
    expected = {
        "speaker_repetition_frequency",
        "agreement_disagreement_breakdown",
        "similarity_distribution",
        "speaker_repetitions",
        "classification",
        "speaker_similarity",
    }
    for slug in expected:
        viz_id = f"semantic_similarity_v2.{slug}.global"
        chart_def = get_chart_definition(viz_id)
        assert chart_def is not None
        artifact = FakeArtifact(
            id=f"{slug}_png",
            kind="chart_static",
            module="semantic_similarity_v2",
            scope="global",
            speaker=None,
            rel_path=f"semantic_similarity_v2/charts/global/static/base_{slug}.png",
            meta={"viz_id": viz_id},
        )
        assert chart_def.match.matches(artifact, chart_def) is True


def test_matcher_prefers_viz_id_metadata():
    chart_def = get_chart_definition("sentiment.multi_speaker_sentiment.global")
    assert chart_def is not None
    artifact = FakeArtifact(
        id="a1",
        kind="chart_static",
        module="sentiment",
        scope="global",
        speaker=None,
        rel_path="sentiment/charts/global/static/multi_speaker_sentiment.png",
        meta={"viz_id": "sentiment.multi_speaker_sentiment.global"},
    )
    assert chart_def.match.matches(artifact, chart_def) is True


def test_matcher_falls_back_to_path():
    chart_def = get_chart_definition("sentiment.multi_speaker_sentiment.global")
    assert chart_def is not None
    artifact = FakeArtifact(
        id="a2",
        kind="chart_static",
        module="sentiment",
        scope="global",
        speaker=None,
        rel_path="sentiment/charts/global/static/multi_speaker_sentiment.png",
        meta=None,
    )
    assert chart_def.match.matches(artifact, chart_def) is True


def test_matcher_falls_back_to_path_when_viz_id_is_legacy_derived():
    chart_def = get_chart_definition("wordcloud.wordcloud.speaker.tfidf")
    assert chart_def is not None
    artifact = FakeArtifact(
        id="speaker-tfidf",
        kind="chart_static",
        module="wordclouds",
        scope="speaker",
        speaker="Ana",
        rel_path="wordclouds/charts/speakers/Ana/static/tfidf/tfidf.png",
        meta={"viz_id": "wordclouds.tfidf.speaker"},
    )
    assert chart_def.match.matches(artifact, chart_def) is True
    cd = find_chart_definition_for_artifact(artifact)
    assert cd is not None
    assert cd.viz_id == "wordcloud.wordcloud.speaker.tfidf"


def test_find_chart_definition_for_artifact_prefers_viz_id():
    """When both viz_id and path could match, the viz_id lookup wins."""
    artifact = FakeArtifact(
        id="a3",
        kind="chart_static",
        module="sentiment",
        scope="global",
        speaker=None,
        rel_path="sentiment/charts/global/static/multi_speaker_sentiment.png",
        meta={"viz_id": "sentiment.multi_speaker_sentiment.global"},
    )
    cd = find_chart_definition_for_artifact(artifact)
    assert cd is not None
    assert cd.viz_id == "sentiment.multi_speaker_sentiment.global"


def test_find_chart_definition_for_artifact_path_fallback():
    """An artifact without viz_id resolves via the registry path/slug match."""
    artifact = FakeArtifact(
        id="a4",
        kind="chart_static",
        module="sentiment",
        scope="global",
        speaker=None,
        rel_path="sentiment/charts/global/static/multi_speaker_sentiment.png",
        meta=None,
    )
    cd = find_chart_definition_for_artifact(artifact)
    assert cd is not None
    assert cd.viz_id == "sentiment.multi_speaker_sentiment.global"


def test_affect_tension_viz_ids_have_registry_definitions():
    """Every affect_tension VIZ_* constant must resolve to a registry definition."""
    import transcriptx.core.utils.viz_ids as viz_ids

    affect_ids = {
        getattr(viz_ids, name)
        for name in dir(viz_ids)
        if name.startswith("VIZ_AFFECT_TENSION_")
    }
    missing = sorted(v for v in affect_ids if get_chart_definition(v) is None)
    assert not missing, f"affect_tension viz_ids without a definition: {missing}"


def test_emotion_family_label_count_viz_ids_have_registry_definitions():
    """Contextual and fine-grained label-count viz IDs must resolve in the registry."""
    import transcriptx.core.utils.viz_ids as viz_ids

    family_ids = {
        getattr(viz_ids, name)
        for name in dir(viz_ids)
        if name.startswith("VIZ_CONTEXTUAL_EMOTION_")
        or name.startswith("VIZ_FINE_GRAINED_EMOTION_")
    }
    missing = sorted(v for v in family_ids if get_chart_definition(v) is None)
    assert not missing, f"emotion-family viz_ids without a definition: {missing}"

    expected_new = {
        "contextual_emotion.label_counts_excluding_neutral.global": (
            "contextual_emotion",
            "global",
        ),
        "contextual_emotion.label_counts_excluding_neutral.speaker": (
            "contextual_emotion",
            "speaker",
        ),
        "contextual_emotion.label_share_non_neutral.global": (
            "contextual_emotion",
            "global",
        ),
        "contextual_emotion.label_share_non_neutral.speaker": (
            "contextual_emotion",
            "speaker",
        ),
        "fine_grained_emotion.label_counts_excluding_neutral.global": (
            "fine_grained_emotion",
            "global",
        ),
        "fine_grained_emotion.label_counts_excluding_neutral.speaker": (
            "fine_grained_emotion",
            "speaker",
        ),
        "fine_grained_emotion.label_share_non_neutral.global": (
            "fine_grained_emotion",
            "global",
        ),
        "fine_grained_emotion.label_share_non_neutral.speaker": (
            "fine_grained_emotion",
            "speaker",
        ),
    }
    for viz_id, (module, scope) in expected_new.items():
        chart_def = get_chart_definition(viz_id)
        assert chart_def is not None
        assert chart_def.module == module
        assert chart_def.scope == scope
        assert viz_id in family_ids
    slugs = {
        get_chart_definition(vid).match.by_chart_slug_regex for vid in expected_new
    }
    assert None not in slugs
    assert len(slugs) == 4


def test_bertopic_viz_ids_have_registry_definitions():
    """The bertopic chart viz_ids must resolve to registry definitions."""
    for viz_id in (
        "bertopic.topic_word_heatmap.global",
        "bertopic.topic_prevalence.global",
        "group.bertopic.pooled.topic_share.global",
    ):
        chart = get_chart_definition(viz_id)
        assert chart is not None, viz_id
        assert chart.module == "bertopic"
        assert chart.label, viz_id
        assert chart.description and len(chart.description) > 40, viz_id
        assert chart.match.by_artifact_key_prefix.startswith("bertopic/")


def test_bertopic_registry_default_plan_metadata() -> None:
    """BERTopic is included in recommended defaults and declares the bertopic extra."""
    from transcriptx.core.pipeline.module_registry import get_module_info

    info = get_module_info("bertopic")
    assert info is not None
    assert info.exclude_from_default is False
    assert "bertopic" in info.required_extras
    assert "insight_eligibility" in info.dependencies
    assert info.description
    assert "BERTopic" in info.description


def test_select_preferred_artifacts_single():
    chart_def = get_chart_definition("emotion.radar.global")
    assert chart_def is not None
    artifacts = [
        FakeArtifact(
            id="a_html",
            kind="chart_dynamic",
            module="emotion",
            scope="global",
            speaker=None,
            rel_path="emotion/charts/global/dynamic/emotion_all_radar.html",
            meta={"format": "html"},
        ),
        FakeArtifact(
            id="a_png",
            kind="chart_static",
            module="emotion",
            scope="global",
            speaker=None,
            rel_path="emotion/charts/global/static/emotion_all_radar.png",
            meta={"format": "png"},
        ),
    ]
    selected = select_preferred_artifacts(artifacts, chart_def)
    assert len(selected) == 1
    assert selected[0].id == "a_html"


def test_default_overview_viz_ids_exist():
    for viz_id in DEFAULT_OVERVIEW_VIZ_IDS:
        assert get_chart_definition(viz_id) is not None


def test_default_overview_charts_exist_in_registry():
    registry = get_chart_registry()
    missing = [
        viz_id for viz_id in get_default_overview_charts() if viz_id not in registry
    ]
    assert not missing


def test_iter_chart_definitions_returns_definitions():
    defs = list(iter_chart_definitions())
    assert defs
    assert all(hasattr(defn, "viz_id") for defn in defs)


def test_all_chart_definitions_have_description():
    """Every chart definition must carry a non-trivial human-readable description."""
    missing = [c.viz_id for c in CHART_DEFINITIONS if not (c.description or "").strip()]
    assert not missing, f"Chart definitions missing description: {missing}"

    too_short = [
        c.viz_id for c in CHART_DEFINITIONS if len((c.description or "").strip()) < 20
    ]
    assert (
        not too_short
    ), f"Chart descriptions too short (likely placeholders): {too_short}"


def _infer_group_chart_family_from_viz_id(viz_id: str) -> str | None:
    """Expected GROUP_AGGREGATE_CHART_FAMILIES token for a concrete group.* viz_id."""
    if ".temporal_overlay." in viz_id:
        return "temporal_overlay"
    if "cross_session_speaker" in viz_id:
        return "cross_session_speaker"
    if ".pooled." in viz_id:
        return "pooled_single_view"
    if ".session." in viz_id:
        return "session_bars"
    if "global_acts_pie" in viz_id:
        return "aggregate_pie_bar"
    return None


def test_registry_unique_rank_defaults():
    """rank_default must be unique across all chart definitions (gallery ordering)."""
    from collections import Counter

    counts = Counter(c.rank_default for c in CHART_DEFINITIONS)
    dupes = {rank: n for rank, n in counts.items() if n > 1}
    assert not dupes, f"Duplicate rank_default values: {dupes}"


def test_registry_slug_regexes_compile():
    """Every by_chart_slug_regex must be a valid, compilable regular expression."""
    import re

    invalid = []
    for chart_def in CHART_DEFINITIONS:
        pattern = chart_def.match.by_chart_slug_regex
        if not pattern:
            continue
        try:
            re.compile(pattern)
        except re.error as exc:  # pragma: no cover - failure path
            invalid.append((chart_def.viz_id, pattern, str(exc)))
    assert not invalid, f"Invalid slug regexes: {invalid}"


def test_registry_no_ambiguous_slug_fallback():
    """
    No two definitions in the same (module, scope) may share an identical
    by_chart_slug_regex. Such a collision makes the path-based fallback match
    ambiguous when an artifact lacks viz_id metadata.
    """
    from collections import defaultdict

    seen: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for chart_def in CHART_DEFINITIONS:
        pattern = chart_def.match.by_chart_slug_regex
        if not pattern:
            continue
        seen[(chart_def.module, chart_def.scope, pattern)].append(chart_def.viz_id)
    ambiguous = {k: v for k, v in seen.items() if len(v) > 1}
    assert not ambiguous, f"Ambiguous slug-regex fallbacks: {ambiguous}"


def test_registry_by_viz_id_matches_definition_viz_id():
    """When set, match.by_viz_id must equal the definition's own viz_id."""
    mismatched = [
        (c.viz_id, c.match.by_viz_id)
        for c in CHART_DEFINITIONS
        if c.match.by_viz_id and c.match.by_viz_id != c.viz_id
    ]
    assert not mismatched, f"by_viz_id != viz_id: {mismatched}"


def test_all_registered_overview_viz_ids_resolve():
    """Every viz_id registered in overview lists/allowlists must resolve to a def."""
    registered = (
        set(DEFAULT_OVERVIEW_VIZ_IDS)
        | set(DEFAULT_GROUP_OVERVIEW_VIZ_IDS)
        | set(POOLED_GROUP_OVERVIEW_ALLOWLIST)
        | set(CROSS_SESSION_SPEAKER_OVERVIEW_ALLOWLIST)
    )
    missing = [
        viz_id for viz_id in sorted(registered) if get_chart_definition(viz_id) is None
    ]
    assert not missing, f"Registered viz_ids without a definition: {missing}"


def test_group_chart_definitions_align_with_aggregate_chart_families() -> None:
    """
    Every chart_definitions.json entry with viz_id group.* must map to a module
    that lists the inferred chart family in GROUP_AGGREGATE_CHART_FAMILIES.
    """
    from transcriptx.core.analysis.group_charts.registry import (
        GROUP_AGGREGATE_CHART_FAMILIES,
    )

    for defn in CHART_DEFINITIONS:
        vid = defn.viz_id
        if not vid.startswith("group."):
            continue
        mod = defn.module
        assert (
            mod in GROUP_AGGREGATE_CHART_FAMILIES
        ), f"{vid}: module {mod!r} missing from GROUP_AGGREGATE_CHART_FAMILIES"
        inferred = _infer_group_chart_family_from_viz_id(vid)
        assert inferred is not None, f"Add viz_id pattern for {vid}"
        allowed = GROUP_AGGREGATE_CHART_FAMILIES[mod]
        assert (
            inferred in allowed
        ), f"{vid}: inferred family {inferred!r} not in {allowed} for module {mod!r}"
        if defn.family_id is not None:
            allowed_tokens = {
                t for fam in GROUP_AGGREGATE_CHART_FAMILIES.values() for t in fam
            }
            assert (
                defn.family_id in allowed_tokens
            ), f"{vid}: family_id {defn.family_id!r} not a known aggregate family token"
