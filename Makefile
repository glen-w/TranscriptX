# TranscriptX Makefile
# Main targets for documentation and development

.PHONY: docs-gen docs docs-clean help test-smoke test-fast test-all test-contracts test-integration-core test-optional docker-smoke run prune clean-test-artifacts

help:
	@echo "TranscriptX Makefile"
	@echo ""
	@echo "Documentation targets:"
	@echo "  docs-gen     No-op; CLI docs in docs/generated/ are maintained manually (see CONTRIBUTING.md)"
	@echo "  docs         Same as docs-gen (Sphinx build deferred; see docs/ROADMAP.md)"
	@echo "  docs-clean   Remove generated docs and build artifacts"
	@echo ""
	@echo "Docker:"
	@echo "  run            Interactive CLI in Docker (full TTY; arrow keys work)"
	@echo ""
	@echo "Testing targets:"
	@echo "  test-smoke       Run CI smoke gate"
	@echo "  test-fast        Run fast core (Gate B)"
	@echo "  test-contracts   Run offline contract tests"
	@echo "  test-all         Run full test suite (may be slow)"
	@echo "  docker-smoke     Run Docker first-run smoke test (build + validate/canonicalize/analyze)"
	@echo ""
	@echo "Maintenance:"
	@echo "  prune               Dry-run prune old pipeline runs"
	@echo "  prune-apply         Prune old runs (--apply --yes)"
	@echo "  clean-test-artifacts  Remove test artifact slugs (e.g. test__*) from outputs and index (run manually if needed)"
	@echo ""
	@echo "Usage:"
	@echo "  make run          # Docker interactive CLI (use this for menus)"
	@echo "  make docs        # Generate docs from code"
	@echo "  make docker-smoke  # Docker smoke test (requires docker compose build)"

run:
	docker compose run -it --rm transcriptx

docs-gen:
	@echo "CLI docs are in docs/generated/ and maintained manually. Run transcriptx --help and transcriptx <command> --help, then update docs/generated/cli.md when commands change (see docs/CONTRIBUTING.md)."

docs: docs-gen

docs-clean:
	@echo "Cleaning documentation build and generated files..."
	@rm -rf docs/_build docs/generated docs/api/generated
	@echo "Documentation cleaned!"

clean-test-artifacts:
	@echo "Clearing test artifact slugs (test__*) from outputs and index..."
	@python scripts/clean_test_artifacts.py --prefix test__ --apply --yes

prune:
	@echo "Pruning old pipeline runs (dry-run)..."
	@python scripts/prune_old_pipeline_runs.py

prune-apply:
	@echo "Pruning old pipeline runs (apply)..."
	@python scripts/prune_old_pipeline_runs.py --apply --yes

test-smoke:
	@echo "Running CI smoke gate..."
	@pytest -m smoke

test-fast:
	@echo "Running fast core tests (Gate B)..."
	@pytest -m "not integration and not slow and not requires_models and not requires_docker and not requires_ffmpeg and not requires_api and not quarantined"

test-contracts:
	@echo "Running contract tests..."
	@pytest tests/contracts -m "not quarantined"

test-integration-core:
	@echo "Running integration core tests..."
	@pytest -m integration_core

test-optional:
	@echo "Running optional capability tests (ffmpeg, docker, models, slow, integration)..."
	@pytest -m "slow or requires_models or requires_docker or requires_ffmpeg or requires_api or integration"

test-all:
	@echo "Running full test suite (including optional and quarantined)..."
	@pytest -m "quarantined or not quarantined"

docker-smoke:
	@echo "Running Docker first-run smoke test..."
	@bash scripts/docker-smoke-test.sh
