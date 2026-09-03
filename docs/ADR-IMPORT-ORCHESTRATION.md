# ADR: Transcript Import Orchestration Architecture

## Status
Accepted

## Context

Transcript import previously concentrated detection, adapter behavior, normalization, canonical writing, and managed workflow concerns in loosely separated modules. As adapter count grows, this invites vendor branching, detection drift, and inconsistent diagnostics policy.

## Decision

TranscriptX uses a strict layered import architecture:

- Adapters parse format-specific input only.
- Orchestrator performs detection + parse pipeline + semantic normalization + canonical document build in memory.
- Writer persists canonical artifacts atomically (or fails with no partial visibility).
- Managed workflow handles archival, sidecar, admission, and retry behavior.

`ImportResult` is the single handoff object from orchestrator to caller/writer/managed layers.

Diagnostics use a typed schema (`code`, `severity`, `stage`, `message`, `location`, `recoverable`, `context`) and policy keys off `code`/`severity`/`stage`, not message text.

## Anti-patterns (forbidden)

- Vendor-name branching in orchestrator.
- Filesystem side effects in adapters.
- String-matching warning policy.
- Silent parse fallback after adapter selection.
- Canonical schema writing from adapters.
- Adding adapter support by stealth changes to normalization semantics.

## Consequences

- Adapter onboarding remains local and bounded.
- Detection is deterministic and testable across collisions.
- Failure modes are explicit (unknown, recognized-but-unsupported, malformed, ambiguous).
- Diagnostics become stable contract artifacts and are regression-testable.

