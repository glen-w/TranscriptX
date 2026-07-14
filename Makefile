# TranscriptX Makefile
# Main targets for documentation and development

.PHONY: docs-gen docs docs-clean help test-smoke test-fast test-heavy test-heavy-all test-all test-contracts test-integration-core test-integration test-optional test-coverage test-release-only docker-smoke run clean-test-artifacts

help:
	@echo "TranscriptX Makefile"
	@echo ""
	@echo "Documentation targets:"
	@echo "  docs-gen     No-op; CLI docs in docs/generated/ are maintained manually (see CONTRIBUTING.md)"
	@echo "  docs         Same as docs-gen (Sphinx build deferred; see docs/ROADMAP.md)"
	@echo "  docs-clean   Remove generated docs and build artifacts"
	@echo ""
	@echo "Docker:"
	@echo "  run            Streamlit web app in Docker (full TTY)"
	@echo ""
	@echo "Testing targets:"
	@echo "  test-smoke       Run CI smoke gate"
	@echo "  test-fast        Run fast core (Gate B)"
	@echo "  test-heavy       Run explicit heavy profile (excludes quarantined)"
	@echo "  test-heavy-all   Run explicit heavy profile (includes quarantined)"
	@echo "  test-contracts   Run offline contract tests"
	@echo "  test-integration Run integration + integration_core + integration_extended lane"
	@echo "  test-all         Run all tests except quarantined"
	@echo "  test-coverage    Default fast suite + coverage (fail_under from .coveragerc)"
	@echo "  test-release-only  Run release-only packaging/install smoke"
	@echo "  docker-smoke     Run Docker web launcher smoke test (build + --help)"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean-test-artifacts  Remove test artifact slugs (e.g. test__*) from outputs and index (run manually if needed)"
	@echo ""
	@echo "Usage:"
	@echo "  make run          # Docker Streamlit web app"
	@echo "  make docs        # Generate docs from code"
	@echo "  make docker-smoke  # Docker smoke test (requires docker compose build)"

run:
	docker compose run -it --rm transcriptx-web

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

test-smoke:
	@echo "Running CI smoke gate..."
	@pytest -q tests/smoke -m "smoke and not quarantined and not requires_ffmpeg and not requires_docker and not requires_models and not requires_api and not slow and not release_only"

test-fast:
	@echo "Running fast core tests (Gate B)..."
	@pytest -q -m "not quarantined and not smoke and not release_only and not integration and not integration_core and not integration_extended and not requires_ffmpeg and not requires_docker and not requires_models and not requires_api and not slow and not legacy and not semantic_v2_slow"

test-heavy:
	@echo "Running heavy profile (excluding quarantined)..."
	@pytest --override-ini addopts="-ra --strict-markers --strict-config --import-mode=importlib --verbose --tb=short --timeout=300 --timeout-method=thread" -m "heavy and not quarantined"

test-heavy-all:
	@echo "Running heavy profile (including quarantined)..."
	@pytest --override-ini addopts="-ra --strict-markers --strict-config --import-mode=importlib --verbose --tb=short --timeout=300 --timeout-method=thread" -m "heavy"

test-contracts:
	@echo "Running contract tests..."
	@pytest tests/contracts -m "not quarantined"

test-integration-core:
	@echo "Running integration core tests..."
	@pytest -m integration_core

test-integration:
	@echo "Running integration gate (integration/integration_core/integration_extended)..."
	@pytest -q tests/integration -m "not quarantined and (integration or integration_core or integration_extended) and not requires_ffmpeg and not requires_docker and not requires_models and not requires_api and not release_only"

test-optional:
	@echo "Running optional capability tests (ffmpeg, docker, models, slow, integration)..."
	@pytest --override-ini addopts="-ra --strict-markers --strict-config --import-mode=importlib --verbose --tb=short --timeout=300 --timeout-method=thread" -m "slow or requires_models or requires_docker or requires_ffmpeg or requires_api or integration"

test-all:
	@echo "Running all tests except quarantined..."
	@pytest --override-ini addopts="-ra --strict-markers --strict-config --import-mode=importlib --verbose --tb=short --timeout=300 --timeout-method=thread" -m "not quarantined"

test-coverage:
	@echo "Running default-marker suite with coverage (see .coveragerc fail_under)..."
	@pytest --cov=src --cov-config=.coveragerc --cov-fail-under=0 --cov-report=term-missing --cov-report=json:coverage.json -q \
		-m "not quarantined and not smoke and not release_only and not integration and not integration_core and not integration_extended and not requires_ffmpeg and not requires_docker and not requires_models and not requires_api and not slow and not legacy and not semantic_v2_slow"

test-release-only:
	@echo "Running release-only packaging smoke..."
	@pytest -q tests/release -m "release_only and not quarantined"

docker-smoke:
	@echo "Running Docker first-run smoke test..."
	@bash scripts/docker-smoke-test.sh
