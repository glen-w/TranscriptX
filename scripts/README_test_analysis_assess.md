# Test Analysis Assessment Script

This script implements the comprehensive test analysis assessment plan, providing a unified CLI command for:

1. Running test analysis on transcripts
2. Capturing environment snapshots for determinism
3. Assessing file outputs (schema-level, not filename-level)
4. Assessing database writes (with run boundary invariants)
5. Comparing actual vs expected results
6. Generating comprehensive reports

## Usage

### Basic Usage

Run analysis and assess:
```bash
python scripts/test_analysis_assess.py --transcript tests/fixtures/data/tiny_diarized.json --modules stats,sentiment
```

### Assess Existing Run

Only assess an existing analysis run (don't run analysis):
```bash
python scripts/test_analysis_assess.py --transcript path/to/transcript.json --assess-only --modules stats,sentiment
```

### With Expected Output Specification

Compare against expected outputs:
```bash
python scripts/test_analysis_assess.py \
  --transcript tests/fixtures/data/tiny_diarized.json \
  --modules stats,sentiment \
  --expected tests/fixtures/expected_outputs/tiny_diarized_expected.json
```

### Rerun Check (Idempotency)

Test idempotency by running analysis twice:
```bash
python scripts/test_analysis_assess.py --transcript path/to/transcript.json --rerun-check
```

### Custom Output Location

Save report to specific location:
```bash
python scripts/test_analysis_assess.py \
  --transcript path/to/transcript.json \
  --modules stats,sentiment \
  --output /path/to/report.json
```

## Exit Codes

- `0`: All checks passed or only low severity issues
- `1`: Medium or higher severity issues found
- `2`: Critical issues found

This makes the script CI-friendly - it will fail builds on critical issues.

## Report Structure

The generated report includes:

- **environment**: Complete environment snapshot (git, Python, OS, dependencies, models, config)
- **transcript_path**: Path to analyzed transcript
- **modules_requested**: Modules that were requested
- **modules_run**: Modules that actually ran
- **file_inventory**: Complete file output inventory (no sizes, schema-level)
- **database_inventory**: Complete database state snapshot
- **comparison**: Comparison results with severity levels

## Expected Output Specification

See `tests/fixtures/expected_outputs/tiny_diarized_expected.json` for an example expected output specification.

Key principles:
- Schema-level, not filename-level
- Artifact roles, not specific filenames
- Semantic invariants, not byte sizes
- Database relationship constraints

## Features

### Environment Snapshot
- Git commit hash and dirty state
- Python version, OS, platform
- Dependency lock snapshot (pip freeze)
- Model versions (spaCy, transformers, etc.)
- Timezone and locale
- Config sources and hashes

### File Output Assessment
- Scans all generated files
- Categorizes by artifact role (data, chart, summary, etc.)
- Validates file formats (JSON, PNG, CSV)
- NO file size checks (too flaky)
- Schema validation for JSON files

### Database Assessment
- TranscriptFile record validation
- PipelineRun validation (exactly one per invocation)
- ModuleRun validation (one per requested module, none for unrequested)
- ArtifactIndex validation (all files registered)
- Hash verification (transcript, pipeline input, artifacts)
- Run boundary invariants

### Comparison
- Missing artifacts detection
- Schema violations
- Invariant violations
- Hash mismatches
- Run boundary violations
- Severity classification (critical, high, medium, low)

## Integration with CI/CD

The script is designed to be CI-friendly:

```yaml
# Example GitHub Actions workflow
- name: Test Analysis Assessment
  run: |
    python scripts/test_analysis_assess.py \
      --transcript tests/fixtures/data/tiny_diarized.json \
      --modules stats,sentiment \
      --expected tests/fixtures/expected_outputs/tiny_diarized_expected.json
```

The script will exit with non-zero code on issues, causing the CI build to fail.
