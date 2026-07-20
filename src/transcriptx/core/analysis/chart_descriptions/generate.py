"""Serial chart-description generation with reuse and circuit breaker."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from transcriptx.core.analysis.chart_descriptions.digests import sha256_text
from transcriptx.core.analysis.chart_descriptions.evidence_loader import (
    load_evidence_for_chart,
)
from transcriptx.core.analysis.chart_descriptions.inventory import (
    LogicalChartInventory,
)
from transcriptx.core.analysis.chart_descriptions.models import (
    ChartDescriptionArtifact,
    ChartDescriptionsIndex,
    ChartDescriptionsOutcome,
    IndexEntry,
    OutcomeCounts,
    RepresentationModel,
)
from transcriptx.core.analysis.chart_descriptions.paths import (
    description_md_rel,
    description_rel,
    generation_dir,
)
from transcriptx.core.analysis.chart_descriptions.prompts import (
    build_system_prompt,
    build_user_prompt,
)
from transcriptx.core.analysis.chart_descriptions.publisher import (
    copy_into_generation,
    ensure_generation_dir,
    gc_uncommitted_generations,
    new_attempt_epoch,
    new_generation_id,
    publish_generation,
    read_active,
    read_commit,
    write_attempt_epoch,
    write_json_under_generation,
    write_text_under_generation,
)
from transcriptx.core.analysis.chart_descriptions.schemas import (
    CHART_DESCRIPTIONS_PROMPT_VERSION,
    DEFAULT_MAX_DESCRIPTION_CHARS,
    MODULE_ID,
    SAFE_ERROR_MESSAGE_MAX,
    OverallStatus,
)
from transcriptx.core.analysis.chart_descriptions.selection import select_charts_for_set
from transcriptx.core.analysis.llm_support.hashing import sha256_llm_request
from transcriptx.core.utils.logger import get_logger

logger = get_logger()


@dataclass
class ChartDescriptionsAttemptResult:
    attempt_status: str
    published: bool
    generation_id: str | None = None
    attempt_epoch: str | None = None
    overall_status: OverallStatus | None = None
    inventory_entries: list[dict[str, str]] = field(default_factory=list)
    module_result: dict[str, Any] = field(default_factory=dict)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    error_code: str | None = None
    error_message_safe: str | None = None


def _safe_err(msg: str) -> str:
    text = (msg or "").replace("\n", " ").strip()
    return text[:SAFE_ERROR_MESSAGE_MAX]


def _client_with_request_timeout(client: Any, request_timeout: float) -> Any:
    """Cap OllamaClient HTTP timeout to the chart_descriptions knob when longer."""
    try:
        from transcriptx.core.llm import OllamaClient
    except Exception:
        return client
    if not isinstance(client, OllamaClient):
        return client
    current = float(getattr(client, "_request_timeout", request_timeout) or request_timeout)
    if current <= request_timeout:
        return client
    return OllamaClient(
        base_url=client.base_url,
        model=client.model,
        seed=int(getattr(client, "_seed", 42)),
        request_timeout=request_timeout,
        availability_timeout=float(getattr(client, "_availability_timeout", 7.5)),
        max_output_tokens=getattr(client, "_max_output_tokens", 2048),
        metrics_sink=getattr(client, "_metrics_sink", None),
        effort=getattr(client, "_effort", None),
    )


def _parse_description_json(raw: str, *, max_chars: int) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        payload = json.loads(text)
    except Exception as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(payload, dict) or "description" not in payload:
        raise ValueError("missing description field")
    desc = str(payload.get("description") or "").strip()
    if not desc:
        raise ValueError("empty description")
    if len(desc) > max_chars:
        desc = desc[:max_chars]
    return desc


def _prior_reusable_artifact(
    run_root: Path,
    *,
    chart_key: str,
    evidence_sha: str | None,
    request_hash: str,
) -> Path | None:
    """Find a prior committed description artifact matching hashes."""
    active = read_active(run_root)
    if not active:
        return None
    gen_id = str(active.get("generation_id") or "")
    commit = read_commit(run_root, gen_id) if gen_id else None
    if not commit:
        return None
    index_path = generation_dir(run_root, gen_id) / "index.json"
    if not index_path.is_file():
        return None
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    for entry in index.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("chart_key") != chart_key:
            continue
        if entry.get("status") != "success":
            continue
        if entry.get("request_hash") != request_hash:
            continue
        if evidence_sha and entry.get("evidence_sha256") != evidence_sha:
            continue
        rel = entry.get("description_rel")
        if not rel:
            continue
        path = generation_dir(run_root, gen_id) / rel
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            ChartDescriptionArtifact.model_validate(payload)
        except Exception:
            continue
        return path
    return None


def run_chart_descriptions(
    *,
    run_root: Path,
    run_id: str,
    inventory: LogicalChartInventory,
    inventory_snapshot_sha256: str,
    chart_set: str,
    selected: bool,
    enabled: bool,
    llm_enabled: bool,
    config: Any,
    client_factory: Callable[[], Any] | None = None,
    user_overview: list[str] | None = None,
) -> ChartDescriptionsAttemptResult:
    """Generate and publish one chart-descriptions generation under caller lock."""
    started = time.perf_counter()
    run_root = Path(run_root)
    generation_id = new_generation_id()
    attempt_epoch = new_attempt_epoch()
    write_attempt_epoch(
        run_root, attempt_epoch=attempt_epoch, generation_id=generation_id
    )
    ensure_generation_dir(run_root, generation_id)
    gc_uncommitted_generations(run_root, keep_generation_id=generation_id)

    warnings: list[dict[str, Any]] = []
    counts = OutcomeCounts()

    # Gate: selected AND enabled AND llm
    if not selected or not enabled or not llm_enabled:
        reason = (
            "module_not_selected"
            if not selected
            else ("disabled" if not enabled else "llm_disabled")
        )
        outcome = ChartDescriptionsOutcome(
            generation_id=generation_id,
            overall_status="skipped",
            chart_set=chart_set,
            inventory_snapshot_sha256=inventory_snapshot_sha256,
            counts=counts,
            warnings=[{"code": "SKIPPED", "message": reason}],
            duration_seconds=time.perf_counter() - started,
        )
        index = ChartDescriptionsIndex(
            generation_id=generation_id,
            chart_set=chart_set,
            inventory_snapshot_sha256=inventory_snapshot_sha256,
            entries=[],
        )
        try:
            entries = publish_generation(
                run_root,
                generation_id=generation_id,
                attempt_epoch=attempt_epoch,
                overall_status="skipped",
                inventory_snapshot_sha256=inventory_snapshot_sha256,
                chart_set=chart_set,
                index=index,
                outcome=outcome,
                inventory_rels=[],
            )
        except Exception as exc:
            return ChartDescriptionsAttemptResult(
                attempt_status="failed",
                published=False,
                generation_id=generation_id,
                attempt_epoch=attempt_epoch,
                error_code="PUBLISH_FAILED",
                error_message_safe=_safe_err(str(exc)),
                module_result=_module_result(
                    status="failed",
                    reason=reason,
                    duration=time.perf_counter() - started,
                    counts=counts,
                ),
            )
        return ChartDescriptionsAttemptResult(
            attempt_status="skipped",
            published=True,
            generation_id=generation_id,
            attempt_epoch=attempt_epoch,
            overall_status="skipped",
            inventory_entries=entries,
            module_result=_module_result(
                status="skipped",
                reason=reason,
                duration=time.perf_counter() - started,
                counts=counts,
            ),
            warnings=[{"code": "SKIPPED", "message": reason}],
        )

    cd_cfg = getattr(getattr(config, "analysis", None), "chart_descriptions", None)
    max_chars = int(
        getattr(cd_cfg, "max_description_chars", DEFAULT_MAX_DESCRIPTION_CHARS)
        or DEFAULT_MAX_DESCRIPTION_CHARS
    )
    max_retries = int(getattr(cd_cfg, "max_retries", 1) or 0)
    breaker_limit = int(getattr(cd_cfg, "circuit_breaker_failures", 3) or 3)
    # Cap per-chart HTTP wait; must not inherit the global llm.request_timeout (~1350s).
    request_timeout = float(getattr(cd_cfg, "request_timeout", 120.0) or 120.0)
    temperature = 0.0

    selected_charts = select_charts_for_set(
        inventory.charts,
        chart_set=chart_set,  # type: ignore[arg-type]
        run_kind=inventory.run_kind,
        user_overview=user_overview,
    )
    counts.selected = len(selected_charts)

    # Persist snapshot for audit
    write_json_under_generation(
        run_root,
        generation_id,
        "inventory_snapshot.json",
        {
            "sha256": inventory_snapshot_sha256,
            "run_kind": inventory.run_kind,
            "run_target_id": inventory.run_target_id,
            "chart_count": len(inventory.charts),
            "selected_count": len(selected_charts),
            "chart_keys": [c.chart_key for c in selected_charts],
        },
    )

    if client_factory is None:
        from transcriptx.core.analysis.llm_support.model_selection import (
            require_resolved_model,
        )
        from transcriptx.core.llm import get_llm_client

        resolved = require_resolved_model(config.llm, "chart_descriptions")
        model_selection_source = resolved.source

        def client_factory() -> Any:
            return get_llm_client(config, model=resolved.model)

    else:
        model_selection_source = None

    client = _client_with_request_timeout(client_factory(), request_timeout)
    model = str(
        getattr(client, "model", None)
        or getattr(getattr(config, "llm", None), "model", "")
        or ""
    )

    system_prompt = build_system_prompt()
    consecutive_failures = 0
    circuit_open = False
    index_entries: list[IndexEntry] = []
    inventory_rels: list[dict[str, str]] = [
        {
            "rel_path": "inventory_snapshot.json",
            "module": MODULE_ID,
            "kind": "data_json",
        }
    ]

    allowed_roots = [run_root]

    for chart_idx, chart in enumerate(selected_charts, start=1):
        logger.info(
            "[CHART_DESCRIPTIONS] %s/%s viz_id=%s chart_key=%s timeout=%.0fs",
            chart_idx,
            counts.selected,
            chart.viz_id,
            chart.chart_key,
            request_timeout,
        )
        if circuit_open:
            counts.skipped += 1
            index_entries.append(
                IndexEntry(
                    chart_key=chart.chart_key,
                    logical_chart_id=chart.logical_chart_id,
                    viz_id=chart.viz_id,
                    status="skipped",
                    error_code="CIRCUIT_OPEN",
                )
            )
            continue

        evidence, skip_reason, is_legacy = load_evidence_for_chart(
            chart, run_root=run_root, allowed_roots=allowed_roots
        )
        if evidence is None:
            counts.skipped += 1
            index_entries.append(
                IndexEntry(
                    chart_key=chart.chart_key,
                    logical_chart_id=chart.logical_chart_id,
                    viz_id=chart.viz_id,
                    status="skipped",
                    error_code=skip_reason or "NO_EVIDENCE",
                    representations=[
                        RepresentationModel(**r.__dict__) for r in chart.representations
                    ],
                )
            )
            continue
        if is_legacy:
            warnings.append(
                {
                    "code": "LEGACY_EVIDENCE_FALLBACK",
                    "message": f"No evidence sidecar for {chart.viz_id}",
                    "chart_key": chart.chart_key,
                }
            )

        evidence_sha = evidence.content_sha256()
        chart_meta = {
            "viz_id": chart.viz_id,
            "module": chart.module,
            "scope": chart.scope,
            "speaker": chart.speaker,
            "title": chart.title,
            "logical_chart_id": chart.logical_chart_id,
        }
        user_prompt = build_user_prompt(
            chart_meta=chart_meta,
            evidence=evidence.to_dict(),
            registry_description=chart.registry_description,
        )
        request_hash = sha256_llm_request(
            user_prompt,
            system_prompt=system_prompt,
        )
        # Fold model/prompt version into request identity for reuse policy
        request_hash = sha256_text(
            f"{request_hash}|{model}|{CHART_DESCRIPTIONS_PROMPT_VERSION}|{temperature}"
        )

        desc_rel = description_rel(chart.chart_key)
        md_rel = description_md_rel(chart.chart_key)
        reused = False
        description_text: str | None = None

        prior = _prior_reusable_artifact(
            run_root,
            chart_key=chart.chart_key,
            evidence_sha=evidence_sha,
            request_hash=request_hash,
        )
        if prior is not None:
            try:
                copy_into_generation(run_root, generation_id, desc_rel, prior)
                md_prior = prior.with_suffix(".md")
                if md_prior.is_file():
                    copy_into_generation(run_root, generation_id, md_rel, md_prior)
                payload = json.loads(
                    (generation_dir(run_root, generation_id) / desc_rel).read_text(
                        encoding="utf-8"
                    )
                )
                description_text = str(payload.get("description") or "")
                reused = True
                counts.reused += 1
            except Exception:
                description_text = None
                reused = False

        if description_text is None:
            last_err: Exception | None = None
            for _attempt in range(max_retries + 1):
                try:
                    counts.llm_calls += 1
                    raw = client.generate(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        response_format="json",
                    )
                    description_text = _parse_description_json(
                        str(raw), max_chars=max_chars
                    )
                    consecutive_failures = 0
                    last_err = None
                    break
                except Exception as exc:
                    last_err = exc
                    consecutive_failures += 1
                    if consecutive_failures >= breaker_limit:
                        circuit_open = True
                        counts.circuit_trips += 1
                        warnings.append(
                            {
                                "code": "CIRCUIT_BREAKER",
                                "message": _safe_err(str(exc)),
                            }
                        )
                        break
            if last_err is not None and description_text is None:
                counts.failed += 1
                index_entries.append(
                    IndexEntry(
                        chart_key=chart.chart_key,
                        logical_chart_id=chart.logical_chart_id,
                        viz_id=chart.viz_id,
                        status="failed",
                        error_code="LLM_FAILED",
                        error_message_safe=_safe_err(str(last_err)),
                        representations=[
                            RepresentationModel(**r.__dict__)
                            for r in chart.representations
                        ],
                        evidence_sha256=evidence_sha,
                        request_hash=request_hash,
                    )
                )
                continue

        assert description_text is not None
        artifact = ChartDescriptionArtifact(
            chart_key=chart.chart_key,
            logical_chart_id=chart.logical_chart_id,
            viz_id=chart.viz_id,
            module=chart.module,
            scope=chart.scope,
            speaker=chart.speaker,
            description=description_text,
            status="success",
            chart_set=chart_set,
            representations=[
                RepresentationModel(**r.__dict__) for r in chart.representations
            ],
            evidence_sha256=evidence_sha,
            evidence_rel_path=chart.evidence_rel_path,
            request_hash=request_hash,
            prompt_version=CHART_DESCRIPTIONS_PROMPT_VERSION,
            model=model,
            model_selection_source=model_selection_source,
            reused=reused,
        )
        write_json_under_generation(
            run_root, generation_id, desc_rel, artifact.model_dump()
        )
        md = f"# Chart description\n\n{description_text}\n"
        write_text_under_generation(run_root, generation_id, md_rel, md)
        inventory_rels.append(
            {"rel_path": desc_rel, "module": MODULE_ID, "kind": "data_json"}
        )
        inventory_rels.append(
            {"rel_path": md_rel, "module": MODULE_ID, "kind": "data_txt"}
        )
        counts.succeeded += 1
        index_entries.append(
            IndexEntry(
                chart_key=chart.chart_key,
                logical_chart_id=chart.logical_chart_id,
                viz_id=chart.viz_id,
                status="success",
                description_rel=desc_rel,
                markdown_rel=md_rel,
                representations=[
                    RepresentationModel(**r.__dict__) for r in chart.representations
                ],
                evidence_sha256=evidence_sha,
                request_hash=request_hash,
                reused=reused,
            )
        )

    if counts.failed and counts.succeeded:
        overall: OverallStatus = "partial"
    elif counts.failed and not counts.succeeded:
        overall = "failed"
    elif counts.succeeded:
        overall = "success"
    else:
        overall = "skipped" if counts.selected == 0 or counts.skipped else "partial"

    duration = time.perf_counter() - started
    outcome = ChartDescriptionsOutcome(
        generation_id=generation_id,
        overall_status=overall,
        chart_set=chart_set,
        inventory_snapshot_sha256=inventory_snapshot_sha256,
        counts=counts,
        warnings=warnings,
        duration_seconds=duration,
    )
    index = ChartDescriptionsIndex(
        generation_id=generation_id,
        chart_set=chart_set,
        inventory_snapshot_sha256=inventory_snapshot_sha256,
        entries=index_entries,
    )
    try:
        entries = publish_generation(
            run_root,
            generation_id=generation_id,
            attempt_epoch=attempt_epoch,
            overall_status=overall,
            inventory_snapshot_sha256=inventory_snapshot_sha256,
            chart_set=chart_set,
            index=index,
            outcome=outcome,
            inventory_rels=inventory_rels,
        )
    except Exception as exc:
        logger.exception("chart_descriptions publish failed")
        return ChartDescriptionsAttemptResult(
            attempt_status="failed",
            published=False,
            generation_id=generation_id,
            attempt_epoch=attempt_epoch,
            error_code="PUBLISH_FAILED",
            error_message_safe=_safe_err(str(exc)),
            warnings=warnings,
            module_result=_module_result(
                status="failed",
                reason="publish_failed",
                duration=duration,
                counts=counts,
            ),
        )

    return ChartDescriptionsAttemptResult(
        attempt_status=overall,
        published=True,
        generation_id=generation_id,
        attempt_epoch=attempt_epoch,
        overall_status=overall,
        inventory_entries=entries,
        warnings=warnings,
        module_result=_module_result(
            status="completed" if overall in {"success", "partial"} else overall,
            reason=None,
            duration=duration,
            counts=counts,
        ),
    )


def _module_result(
    *,
    status: str,
    reason: str | None,
    duration: float,
    counts: OutcomeCounts,
) -> dict[str, Any]:
    return {
        "module": MODULE_ID,
        "finalize_phase": True,
        "status": status,
        "skip_reason": reason,
        "duration_seconds": duration,
        "llm_metrics": {
            "calls": counts.llm_calls,
            "reused": counts.reused,
            "circuit_trips": counts.circuit_trips,
            "selected": counts.selected,
            "succeeded": counts.succeeded,
            "skipped": counts.skipped,
            "failed": counts.failed,
        },
    }
