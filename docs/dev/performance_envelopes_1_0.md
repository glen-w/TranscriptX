Type: PRODUCT
Authority: self

# Performance and resource envelopes (1.0)

**Status:** planning  
**Programme:** [pre_release_roadmap_1_0.md](pre_release_roadmap_1_0.md) §12  
**Related:** [release_severity_triage_1_0.md](release_severity_triage_1_0.md)

Documented expectations and regression indicators — not necessarily strict universal guarantees. Capacity failures that corrupt data or hang without recovery are release blockers / must-fix; non-critical misses may ship as known limitations.

## Representative corpus sizes

| Class | Working definition (fill) | Notes |
|-------|---------------------------|-------|
| Small | TBD | First useful result |
| Medium | TBD | Default preset |
| Large-for-1.0 | TBD | Upper documented expectation |

## Metrics checklist

- [ ] Startup time
- [ ] Import time
- [ ] Time to first useful result
- [ ] Default-preset runtime
- [ ] Memory and disk use
- [ ] Model download sizes
- [ ] Docker image size
- [ ] Group-analysis scaling
- [ ] UI responsiveness with a large library
- [ ] Behaviour when disk, RAM, or model capacity is insufficient

## Recording

Record measured values per environment (Docker vs native) in release-evidence notes when claiming envelopes.
