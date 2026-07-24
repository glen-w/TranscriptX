"""Golden / contract tests for llm_action_items v2 (B10)."""

from __future__ import annotations

import json

import pytest

from transcriptx.core.analysis.llm_support.action_items_contract import (
    LLM_ACTION_ITEMS_SCHEMA_ID,
    LLM_ACTION_ITEMS_SCHEMA_ID_V1,
    MAX_ITEMS_PER_TYPE,
    MAX_ITEMS_TOTAL,
    RECORD_TYPES,
    build_llm_action_items_cache_key,
    coerce_v1_action_items_payload,
    dedupe_action_items,
    empty_diagnostics,
    finalize_action_items,
    ground_action_items,
    is_v1_action_items_payload,
    order_action_items,
    parse_action_items_json,
    truncate_action_items,
)
from transcriptx.core.analysis.llm_support.action_items_render import (
    escape_markdown,
    render_action_items_markdown,
)
from transcriptx.core.llm.errors import LLMResponseError

from .fixtures.llm_action_items_v2 import (
    EMPTY_EXTRACTS_MESSAGE,
    HUMAN_REVIEW_BANNER,
    LLM_ACTION_ITEMS_RENDER_CONTRACT_ID,
    RECORD_TYPE_LABELS,
    TITLE_MEETING_EXTRACTS,
    V2_DIAGNOSTIC_KEYS,
    example_v1_artifact,
    example_v2_artifact,
    example_v2_item,
)


def _item(**overrides: object) -> dict:
    return example_v2_item(**overrides)


def _raw(items: list[dict]) -> str:
    return json.dumps({"items": items})


@pytest.mark.unit
def test_fixture_diagnostics_keys_match_contract() -> None:
    assert set(empty_diagnostics().keys()) == V2_DIAGNOSTIC_KEYS
    assert set(empty_diagnostics()["counts_by_type"].keys()) == set(RECORD_TYPES)


@pytest.mark.unit
def test_build_llm_action_items_cache_key_changes_on_version_bumps() -> None:
    base_kwargs = dict(
        transcript_fingerprint="tf",
        bounded_input_fingerprint="bf",
        model="qwen3:8b",
        runtime={"max_input_chars": 48000},
        generation_options={"temperature": 0.0},
        llm_request_sha256="rh",
    )
    v1 = build_llm_action_items_cache_key(
        module_version="1",
        prompt_version="4",
        schema_id=LLM_ACTION_ITEMS_SCHEMA_ID_V1,
        **base_kwargs,
    )
    v2 = build_llm_action_items_cache_key(
        module_version="2",
        prompt_version="5",
        schema_id=LLM_ACTION_ITEMS_SCHEMA_ID,
        **base_kwargs,
    )
    assert v1 != v2
    bumped_prompt = build_llm_action_items_cache_key(
        module_version="2",
        prompt_version="7",
        schema_id=LLM_ACTION_ITEMS_SCHEMA_ID,
        **base_kwargs,
    )
    assert bumped_prompt != v2


@pytest.mark.unit
def test_build_llm_action_items_cache_key_golden_stable_payload() -> None:
    cache_key = build_llm_action_items_cache_key(
        module_version="1.0.0",
        prompt_version="v1",
        schema_id="action_items_v1",
        transcript_fingerprint="tf",
        bounded_input_fingerprint="bf",
        model="qwen3:8b",
        runtime={"max_input_chars": 48000},
        generation_options={"temperature": 0.0},
        llm_request_sha256="rh",
    )
    assert (
        cache_key == "adca868f7de308fd306681794caca189674b2595363563bfc2908e730bf0edb2"
    )


@pytest.mark.unit
def test_parse_partial_survival_malformed_sibling() -> None:
    good = _item()
    bad = _item(text="")
    parsed, diagnostics = parse_action_items_json(_raw([bad, good]))
    assert len(parsed) == 1
    assert parsed[0]["text"] == "Send the report"
    assert parsed[0]["_model_index"] == 1
    assert diagnostics["items_raw"] == 2
    assert diagnostics["items_parsed_valid"] == 1
    assert diagnostics["items_invalid_dropped"] == 1


@pytest.mark.unit
def test_parse_strips_extra_fields_instead_of_dropping() -> None:
    noisy = _item(priority="high", id=3)
    parsed, diagnostics = parse_action_items_json(_raw([noisy]))
    assert len(parsed) == 1
    assert "priority" not in parsed[0]
    assert diagnostics["extra_fields_stripped"] == 1
    assert diagnostics["items_invalid_dropped"] == 0


@pytest.mark.unit
def test_parse_aliases_record_type_and_defaults_missing_confidence() -> None:
    unknown = _item(record_type="task")
    del unknown["confidence"]
    missing = _item()
    del missing["record_type"]
    null_type = _item(record_type=None)
    parsed, diagnostics = parse_action_items_json(_raw([unknown, missing, null_type]))
    assert len(parsed) == 3
    assert all(item["record_type"] == "action_item" for item in parsed)
    assert diagnostics["items_invalid_dropped"] == 0
    assert diagnostics["record_type_aliased"] == 1
    assert diagnostics["record_type_defaulted"] == 2
    assert diagnostics["confidence_defaulted"] == 1


@pytest.mark.unit
def test_parse_tolerates_unknown_top_level_keys() -> None:
    payload = json.dumps({"items": [_item()], "extra": True, "summary": "nope"})
    parsed, diagnostics = parse_action_items_json(payload)
    assert len(parsed) == 1
    assert diagnostics["items_parsed_valid"] == 1


@pytest.mark.unit
def test_parse_invalid_confidence_drops_record() -> None:
    parsed, diagnostics = parse_action_items_json(
        _raw([_item(confidence=1.5), _item(text="Keep me", quote=None)])
    )
    assert len(parsed) == 1
    assert parsed[0]["text"] == "Keep me"
    assert diagnostics["items_invalid_dropped"] == 1


@pytest.mark.unit
def test_parse_coerces_percent_confidence() -> None:
    parsed, diagnostics = parse_action_items_json(
        _raw([_item(confidence=80), _item(confidence="high", text="Other", quote=None)])
    )
    assert [item["confidence"] for item in parsed] == [pytest.approx(0.8), pytest.approx(0.9)]
    assert diagnostics["confidence_coerced"] == 2


@pytest.mark.unit
def test_parse_rejects_truly_unknown_record_type() -> None:
    parsed, diagnostics = parse_action_items_json(_raw([_item(record_type="agenda")]))
    assert parsed == []
    assert diagnostics["items_invalid_dropped"] == 1


@pytest.mark.unit
def test_parse_invalid_status_drops_as_unsupported() -> None:
    parsed, diagnostics = parse_action_items_json(_raw([_item(status="paused")]))
    assert parsed == []
    assert diagnostics["status_unsupported_dropped"] == 1


@pytest.mark.unit
def test_parse_done_without_evidence_dropped_for_decision() -> None:
    parsed, diagnostics = parse_action_items_json(
        _raw(
            [
                _item(
                    record_type="decision",
                    text="We will use Postgres",
                    status="done",
                    quote="We will use Postgres",
                )
            ]
        )
    )
    assert parsed == []
    assert diagnostics["status_unsupported_dropped"] == 1


@pytest.mark.unit
def test_parse_done_with_evidence_kept_for_open_question() -> None:
    parsed, diagnostics = parse_action_items_json(
        _raw(
            [
                _item(
                    record_type="open_question",
                    text="Budget question is resolved",
                    status="done",
                    quote="The budget question is resolved",
                )
            ]
        )
    )
    assert len(parsed) == 1
    assert diagnostics["status_unsupported_dropped"] == 0


@pytest.mark.unit
def test_parse_enforces_output_length_gate() -> None:
    with pytest.raises(LLMResponseError, match="exceeds expected length"):
        parse_action_items_json(_raw([_item()]), max_output_tokens=1)


@pytest.mark.unit
def test_parse_salvages_truncated_unterminated_string() -> None:
    """Canal-walk failure mode: num_predict cuts mid-string after valid items."""
    complete = _item(text="Book lock passage", quote="book the lock")
    prefix = json.dumps({"items": [complete]}, separators=(",", ":"))
    assert prefix.endswith("]}")
    truncated = (
        prefix[:-2]
        + ',{"record_type":"action_item","text":"Unfinished item with "open quote'
    )
    with pytest.raises(json.JSONDecodeError):
        json.loads(truncated)

    parsed, diagnostics = parse_action_items_json(truncated)
    assert len(parsed) == 1
    assert parsed[0]["text"] == "Book lock passage"
    assert diagnostics["items_raw"] == 1
    assert diagnostics["items_parsed_valid"] == 1
    assert diagnostics["output_truncated"] == 1


@pytest.mark.unit
def test_parse_salvages_truncated_after_complete_objects() -> None:
    first = _item(text="Send the report", quote="send the report")
    second = _item(
        record_type="decision",
        text="Use the north route",
        quote="north route",
        status="open",
    )
    prefix = json.dumps({"items": [first, second]}, separators=(",", ":"))
    assert prefix.endswith("]}")
    truncated = prefix[:-2] + ',{"record_type":"proposal","text":"Maybe later'
    parsed, diagnostics = parse_action_items_json(truncated)
    assert [item["text"] for item in parsed] == [
        "Send the report",
        "Use the north route",
    ]
    assert diagnostics["output_truncated"] == 1
    assert diagnostics["items_parsed_valid"] == 2


@pytest.mark.unit
def test_parse_truncated_with_no_complete_items_still_fails() -> None:
    truncated = '{"items":[{"record_type":"action_item","text":"Only a fragment'
    with pytest.raises(LLMResponseError, match="not valid JSON"):
        parse_action_items_json(truncated)


@pytest.mark.unit
def test_finalize_salvages_truncated_json_end_to_end() -> None:
    transcript = "Alice: I will send the report by Friday."
    complete = _item(
        text="send the report by Friday",
        quote="send the report by Friday",
        owner="Alice",
    )
    prefix = json.dumps({"items": [complete]}, separators=(",", ":"))
    truncated = prefix[:-2] + ',{"record_type":"action_item","text":"Broken trailing'
    items, diagnostics = finalize_action_items(truncated, transcript)
    assert len(items) == 1
    assert items[0]["text"] == "send the report by Friday"
    assert diagnostics["output_truncated"] == 1
    assert diagnostics["items_committed"] == 1


@pytest.mark.unit
def test_proposal_done_without_lexicon_dropped() -> None:
    parsed, diagnostics = parse_action_items_json(
        _raw(
            [
                _item(
                    record_type="proposal",
                    text="Maybe migrate later",
                    status="done",
                    quote="Maybe migrate later",
                )
            ]
        )
    )
    assert parsed == []
    assert diagnostics["status_unsupported_dropped"] == 1


@pytest.mark.unit
def test_finalize_mistral_missing_confidence_and_ellipsis_quotes() -> None:
    """Canal-walk failure mode: mistral omits confidence and joins quote spans."""
    transcript = (
        "Glen: But I think I'm going to try and re-jig my finances a bit. "
        "Glen: I've cancelled all my cards I've re-ordered the well some of the cards. "
        "Glen: I say that but I've already just gone and bought £130 worth of stuff off Amazon. "
        "Glen: Which an idea I have is I want to make somehow my things that magnetic so that they stay."
    )
    raw = json.dumps(
        {
            "items": [
                {
                    "record_type": "open_question",
                    "text": "Is there any plan for managing finances?",
                    "owner": None,
                    "deadline": None,
                    "status": "open",
                    "quote": "I'm going to try and re-jig my finances a bit",
                },
                {
                    "record_type": "action_item",
                    "text": "Lower spending next month.",
                    "owner": "Glen",
                    "deadline": "Next month",
                    "status": "open",
                    "quote": (
                        "I say that but I've already just gone and bought "
                        "£130 worth of stuff off Amazon... Mom has even taken "
                        "back most of her stuff now"
                    ),
                },
                {
                    "type": "task",
                    "description": "Make pocket items magnetic",
                    "assignee": "Glen",
                    "due": None,
                    "status": "pending",
                    "evidence": (
                        "I think I might have lost that... I want to make "
                        "somehow my things that magnetic"
                    ),
                    "priority": "high",
                },
            ]
        }
    )
    items, diagnostics = finalize_action_items(raw, transcript)
    assert len(items) == 3
    assert diagnostics["confidence_defaulted"] == 3
    assert diagnostics["extra_fields_stripped"] >= 1
    assert diagnostics["record_type_aliased"] >= 1
    assert diagnostics["status_aliased"] >= 1
    assert diagnostics["quotes_salvaged"] >= 1
    assert diagnostics["items_committed"] == 3
    assert any("£130 worth of stuff off Amazon" in (item.get("quote") or "") for item in items)


@pytest.mark.unit
def test_parse_accepts_action_items_or_extracts_wrapper_keys() -> None:
    via_alias = json.dumps(
        {
            "action_items": [
                {
                    "record_type": "action_item",
                    "text": "Send the report",
                    "owner": "Alice",
                    "deadline": None,
                    "status": "open",
                    "quote": None,
                    "confidence": 0.7,
                }
            ]
        }
    )
    via_extracts = json.dumps(
        {
            "extracts": [
                {
                    "record_type": "decision",
                    "text": "Use Postgres",
                    "owner": None,
                    "deadline": None,
                    "status": "open",
                    "quote": None,
                    "confidence": 0.8,
                }
            ]
        }
    )
    parsed_a, diag_a = parse_action_items_json(via_alias)
    parsed_b, diag_b = parse_action_items_json(via_extracts)
    assert [item["text"] for item in parsed_a] == ["Send the report"]
    assert [item["record_type"] for item in parsed_b] == ["decision"]
    assert diag_a["items_raw"] == 1
    assert diag_b["items_raw"] == 1


@pytest.mark.unit
def test_parse_field_aliases_description_assignee_evidence() -> None:
    raw = json.dumps(
        {
            "items": [
                {
                    "type": "question",
                    "description": "Who owns the budget?",
                    "assignee": "Alice",
                    "due": "Friday",
                    "status": "todo",
                    "evidence": "who owns the budget",
                    "score": 80,
                    "priority": "high",
                }
            ]
        }
    )
    parsed, diagnostics = parse_action_items_json(raw)
    assert len(parsed) == 1
    item = parsed[0]
    assert item["record_type"] == "open_question"
    assert item["text"] == "Who owns the budget?"
    assert item["owner"] == "Alice"
    assert item["deadline"] == "Friday"
    assert item["status"] == "open"
    assert item["quote"] == "who owns the budget"
    assert item["confidence"] == pytest.approx(0.8)
    assert diagnostics["extra_fields_stripped"] == 1
    assert diagnostics["record_type_aliased"] == 1
    assert diagnostics["status_aliased"] == 1
    assert diagnostics["confidence_coerced"] == 1


@pytest.mark.unit
def test_ground_salvages_ellipsis_joined_quote() -> None:
    items, _ = parse_action_items_json(
        _raw(
            [
                _item(
                    text="Paraphrased magnetic plan",
                    quote=(
                        "I might have lost that... I want to make somehow my "
                        "things that magnetic"
                    ),
                )
            ]
        )
    )
    transcript = (
        "Glen: I think I might have lost that. "
        "Glen: Which an idea I have is I want to make somehow my things that "
        "magnetic so that they stay."
    )
    grounded, diagnostics = ground_action_items(items, transcript)
    assert len(grounded) == 1
    assert grounded[0]["quote"] == "I want to make somehow my things that magnetic"
    assert diagnostics["quotes_salvaged"] == 1
    assert diagnostics["quotes_nulled"] == 0


@pytest.mark.unit
def test_ground_nulls_quote_without_rewriting_fields() -> None:
    items, _ = parse_action_items_json(
        _raw([_item(text="send the report by Friday", quote="Fabricated quote.")])
    )
    original = {
        k: items[0][k]
        for k in ("record_type", "text", "owner", "deadline", "status")
    }
    grounded, diagnostics = ground_action_items(
        items, "Alice: I will send the report by Friday."
    )
    assert len(grounded) == 1
    assert grounded[0]["quote"] is None
    assert grounded[0]["confidence"] == pytest.approx(0.45)
    assert diagnostics["quotes_nulled"] == 1
    for key, value in original.items():
        assert grounded[0][key] == value


@pytest.mark.unit
def test_ground_drops_fully_ungrounded() -> None:
    items, _ = parse_action_items_json(
        _raw(
            [
                _item(text="Totally fabricated", quote="Also fabricated."),
                _item(text="send the report by Friday", quote=None),
            ]
        )
    )
    grounded, diagnostics = ground_action_items(
        items, "Alice: I will send the report by Friday."
    )
    assert [i["text"] for i in grounded] == ["send the report by Friday"]
    assert diagnostics["items_ungrounded_dropped"] == 1


@pytest.mark.unit
def test_dedupe_winner_prefers_quote_then_earlier_index() -> None:
    # Same confidence: quote presence beats null (plan: confidence then evidence).
    a = dict(
        _item(quote=None, confidence=0.9),
        _model_index=0,
        _grounded=True,
    )
    b = dict(_item(confidence=0.9), _model_index=1, _grounded=True)
    deduped, removed = dedupe_action_items([a, b])
    assert removed == 1
    assert len(deduped) == 1
    assert deduped[0]["quote"] is not None


@pytest.mark.unit
def test_dedupe_higher_confidence_beats_quote() -> None:
    a = dict(
        _item(quote=None, confidence=0.95),
        _model_index=0,
        _grounded=True,
    )
    b = dict(_item(confidence=0.6), _model_index=1, _grounded=True)
    deduped, removed = dedupe_action_items([a, b])
    assert removed == 1
    assert deduped[0]["confidence"] == pytest.approx(0.95)
    assert deduped[0]["quote"] is None


@pytest.mark.unit
def test_dedupe_earlier_model_index_wins_on_tie() -> None:
    a = dict(_item(confidence=0.9), _model_index=5, _grounded=True)
    b = dict(_item(confidence=0.9), _model_index=1, _grounded=True)
    deduped, removed = dedupe_action_items([a, b])
    assert removed == 1
    assert deduped[0]["_model_index"] == 1


@pytest.mark.unit
def test_dedupe_keeps_different_record_types() -> None:
    decision = dict(
        _item(record_type="decision", text="Use Postgres"),
        _model_index=0,
        _grounded=True,
    )
    action = dict(
        _item(record_type="action_item", text="Use Postgres"),
        _model_index=1,
        _grounded=True,
    )
    deduped, removed = dedupe_action_items([decision, action])
    assert removed == 0
    assert len(deduped) == 2


@pytest.mark.unit
def test_order_by_type_then_transcript_strips_internals() -> None:
    transcript = "Alice: first task here. Bob: second task here. We decided on Postgres."
    items = [
        dict(
            _item(record_type="action_item", text="second task here", quote=None),
            _model_index=0,
            _grounded=True,
        ),
        dict(
            _item(
                record_type="decision",
                text="We decided on Postgres",
                quote=None,
                status="open",
            ),
            _model_index=1,
            _grounded=True,
        ),
        dict(
            _item(record_type="action_item", text="first task here", quote=None),
            _model_index=2,
            _grounded=True,
        ),
    ]
    ordered = order_action_items(items, transcript)
    assert [i["record_type"] for i in ordered] == [
        "decision",
        "action_item",
        "action_item",
    ]
    assert [i["text"] for i in ordered] == [
        "We decided on Postgres",
        "first task here",
        "second task here",
    ]
    assert all("_model_index" not in i for i in ordered)
    assert all("_grounded" not in i for i in ordered)


@pytest.mark.unit
def test_truncate_bounds_and_counts_keys() -> None:
    items = []
    for i in range(MAX_ITEMS_PER_TYPE + 3):
        items.append(
            dict(
                _item(text=f"Task {i}", quote=None, confidence=0.5),
                _model_index=i,
                record_type="action_item",
                _grounded=True,
            )
        )
    for i in range(5):
        items.append(
            dict(
                _item(
                    record_type="decision",
                    text=f"Decision {i}",
                    quote=None,
                    confidence=0.5,
                ),
                _model_index=100 + i,
                _grounded=True,
            )
        )
    kept, truncated = truncate_action_items(items)
    assert truncated > 0
    assert len(kept) <= MAX_ITEMS_TOTAL
    assert (
        sum(1 for item in kept if item["record_type"] == "action_item")
        <= MAX_ITEMS_PER_TYPE
    )


@pytest.mark.unit
def test_finalize_empty_diagnostics_and_counts() -> None:
    items, diagnostics = finalize_action_items(
        json.dumps({"items": []}), "Alice: hello"
    )
    assert items == []
    assert diagnostics["items_committed"] == 0
    assert diagnostics["counts_by_type"] == {name: 0 for name in RECORD_TYPES}


@pytest.mark.unit
def test_finalize_end_to_end_committed_counts() -> None:
    transcript = (
        "Alice: We decided on Postgres. "
        "Bob: I will send the report by Friday. "
        "Carol: Should we hire a contractor?"
    )
    raw = _raw(
        [
            _item(
                record_type="decision",
                text="We decided on Postgres",
                quote="We decided on Postgres",
                owner=None,
                deadline=None,
            ),
            _item(
                text="send the report by Friday",
                quote="I will send the report by Friday.",
            ),
            _item(
                record_type="open_question",
                text="Should we hire a contractor?",
                quote="Should we hire a contractor?",
                owner=None,
                deadline=None,
            ),
            _item(text="Invented task", quote="Not in transcript"),
        ]
    )
    items, diagnostics = finalize_action_items(raw, transcript)
    assert diagnostics["items_committed"] == 3
    assert diagnostics["counts_by_type"]["decision"] == 1
    assert diagnostics["counts_by_type"]["action_item"] == 1
    assert diagnostics["counts_by_type"]["open_question"] == 1
    assert diagnostics["items_ungrounded_dropped"] == 1
    assert [i["record_type"] for i in items] == [
        "decision",
        "action_item",
        "open_question",
    ]


@pytest.mark.unit
def test_v1_compat_detection_and_coerce() -> None:
    v1 = example_v1_artifact()
    assert is_v1_action_items_payload(v1)
    assert not is_v1_action_items_payload(example_v2_artifact())
    coerced = coerce_v1_action_items_payload(v1)
    assert coerced["schema_id"] == LLM_ACTION_ITEMS_SCHEMA_ID_V1
    assert coerced["items"][0]["record_type"] == "action_item"
    assert coerced["provenance"]["compat"] == "v1_coerced"


@pytest.mark.unit
def test_render_sections_banner_escape_empty() -> None:
    payload = example_v2_artifact(
        [
            _item(text="Send *the* report", record_type="action_item"),
            _item(
                record_type="decision",
                text="Ship v2",
                quote="Ship v2",
                owner=None,
                deadline=None,
            ),
        ]
    )
    md = render_action_items_markdown(payload)
    assert md.startswith(f"# {TITLE_MEETING_EXTRACTS}")
    assert HUMAN_REVIEW_BANNER in md
    assert f"## {RECORD_TYPE_LABELS['decision']}" in md
    assert f"## {RECORD_TYPE_LABELS['action_item']}" in md
    assert r"Send \*the\* report" in md
    assert LLM_ACTION_ITEMS_RENDER_CONTRACT_ID in md
    empty_md = render_action_items_markdown({"items": []})
    assert f"_{EMPTY_EXTRACTS_MESSAGE}_" in empty_md
    assert HUMAN_REVIEW_BANNER in empty_md


@pytest.mark.unit
def test_render_normalises_multiline_quote_and_escapes() -> None:
    assert escape_markdown("a*b_c[d]") == r"a\*b\_c\[d\]"
    payload = example_v2_artifact(
        [
            _item(
                quote="line one\nline two",
                owner="Alice\nBob",
                deadline="next\nFriday",
            )
        ]
    )
    md = render_action_items_markdown(payload)
    assert "line one line two" in md
    assert "Alice Bob" in md
    assert "next Friday" in md


@pytest.mark.unit
def test_parse_coerces_owner_deadline_and_nulls_bad_optionals() -> None:
    parsed, _ = parse_action_items_json(
        _raw(
            [
                _item(owner=3, deadline=["Fri", "PM"]),
                _item(
                    text="Other",
                    owner={"name": "Alice"},
                    deadline=True,
                    quote=123,
                    confidence=0.5,
                ),
            ]
        )
    )
    assert parsed[0]["owner"] == "3"
    assert parsed[0]["deadline"] == "Fri, PM"
    assert parsed[1]["owner"] is None
    assert parsed[1]["deadline"] is None
    assert parsed[1]["quote"] is None


@pytest.mark.unit
def test_parse_strips_fence_and_rejects_invalid_json() -> None:
    payload = f"```json\n{_raw([_item()])}\n```"
    parsed, _ = parse_action_items_json(payload)
    assert parsed[0]["text"] == "Send the report"
    with pytest.raises(LLMResponseError, match="not valid JSON"):
        parse_action_items_json("definitely not json at all")
