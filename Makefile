# TranscriptX Makefile
# Main targets for documentation and development

.PHONY: docs-gen docs docs-clean pages-site help test-smoke test-smoke-nlp test-fast test-heavy test-heavy-all test-all test-contracts test-integration-core test-integration test-optional test-coverage test-config-coverage test-release-only test-gui-acceptance test-workspaces test-theme-c-browser workspaces-build docker-smoke run clean-test-artifacts perf-envelopes

help:
	@echo "TranscriptX Makefile"
	@echo ""
	@echo "Documentation targets:"
	@echo "  docs-gen     Regenerate module catalog + quality-audit scaffold from registry"
	@echo "  docs         Build Sphinx HTML into docs/_build/html (requires .[docs])"
	@echo "  docs-clean   Remove Sphinx build artifacts (keeps docs/generated/)"
	@echo "  pages-site   Assemble website/ + Sphinx guide into _site/ (GitHub Pages payload)"
	@echo "  perf-envelopes  Print performance-envelope measurement recipe (0.9.7)"
	@echo ""
	@echo "Workspaces (Theme C):"
	@echo "  workspaces-build       Build CCv2 frontend assets"
	@echo "  test-workspaces        Protocol/clip/action + Vitest lifecycle tests"
	@echo "  test-theme-c-browser   Playwright browser suite (Theme C)"
	@echo ""
	@echo "Docker:"
	@echo "  run            Streamlit web app in Docker (full TTY)"
	@echo ""
	@echo "Testing targets:"
	@echo "  test-smoke       Run CI smoke gate (Core+dev; spaCy-gated modules skip without [nlp])"
	@echo "  test-smoke-nlp   Run smoke with [nlp] + en_core_web_md available"
	@echo "  test-fast        Run fast core (Gate B)"
	@echo "  test-heavy       Run explicit heavy profile (excludes quarantined)"
	@echo "  test-heavy-all   Run explicit heavy profile (includes quarantined)"
	@echo "  test-contracts   Run offline contract tests"
	@echo "  test-integration Run integration + integration_core + integration_extended lane"
	@echo "  test-all         Run all tests except quarantined"
	@echo "  test-coverage    Default fast suite + coverage (fail_under from .coveragerc)"
	@echo "  test-config-coverage  Config package coverage gate (≥85% on core.config + utils.config)"
	@echo "  test-release-only  Run release-only packaging/install smoke"
	@echo "  test-gui-acceptance  Streamlit AppTest GUI acceptance journeys (heavy)"
	@echo "  docker-smoke     Run Docker web launcher smoke test (build + --help)"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean-test-artifacts  Remove test artifact slugs (e.g. test__*) from outputs and index (run manually if needed)"
	@echo ""
	@echo "Usage:"
	@echo "  make run          # Docker Streamlit web app"
	@echo "  make docs        # Build Sphinx HTML (requires pip install -e '.[docs]')"
	@echo "  make docker-smoke  # Docker smoke test (requires docker compose build)"

run:
	docker compose run -it --rm transcriptx-web

docs-gen:
	@echo "Regenerating module catalog and analysis-quality audit scaffold..."
	@python3 scripts/release/regen_module_docs.py

perf-envelopes:
	@python3 scripts/release/perf_envelope_recipe.py

docs:
	@bash scripts/release/build_docs.sh

pages-site:
	@bash scripts/release/assemble_pages_site.sh

docs-clean:
	@echo "Cleaning Sphinx build artifacts..."
	@rm -rf docs/_build docs/api/generated _site
	@echo "Documentation build cleaned (docs/generated/ preserved)."

clean-test-artifacts:
	@echo "Clearing test artifact slugs (test__*) from outputs and index..."
	@python scripts/clean_test_artifacts.py --prefix test__ --apply --yes

test-smoke:
	@echo "Running CI smoke gate..."
	@pytest -q tests/smoke -m "smoke and not quarantined and not requires_ffmpeg and not requires_docker and not requires_models and not requires_api and not slow and not release_only"

test-smoke-nlp:
	@echo "Running NLP-enabled CI smoke gate..."
	@python -c "import spacy; spacy.load('en_core_web_md'); print('spaCy en_core_web_md ready')"
	@$(MAKE) test-smoke

test-fast:
	@echo "Running fast core tests (Gate B)..."
	@pytest -q -m "not quarantined and not smoke and not release_only and not integration and not integration_core and not integration_extended and not requires_ffmpeg and not requires_docker and not requires_models and not requires_api and not slow and not legacy and not semantic_v2_slow and not gui_acceptance"

test-gui-acceptance:
	@echo "Running Streamlit AppTest GUI acceptance journeys..."
	@pytest --override-ini addopts="-ra --strict-markers --strict-config --import-mode=importlib --verbose --tb=short --timeout=300 --timeout-method=thread" -m "gui_acceptance and not quarantined"

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
		-m "not quarantined and not smoke and not release_only and not integration and not integration_core and not integration_extended and not requires_ffmpeg and not requires_docker and not requires_models and not requires_api and not slow and not legacy and not semantic_v2_slow and not gui_acceptance"

test-config-coverage:
	@echo "Running config-scoped coverage gate (≥85% on transcriptx.core.config + utils.config)..."
	@pytest tests/core/config/ \
		tests/core/utils/config/ \
		tests/core/utils/test_config_loading_contracts.py \
		--cov=transcriptx.core.config --cov=transcriptx.core.utils.config \
		--cov-report=term-missing --cov-fail-under=85 -q

test-release-only:
	@echo "Running release-only packaging smoke..."
	@pytest -q tests/release -m "release_only and not quarantined"

workspaces-build:
	@echo "Building Theme C CCv2 workspace frontend..."
	@cd packages/transcriptx_workspaces/transcriptx_workspaces/frontend && npm ci && npm run build

test-workspaces:
	@echo "Theme C unit/protocol + Vitest lifecycle..."
	@pytest -q tests/app/test_speaker_id_action_service.py tests/app/test_corrections_action_service.py tests/web/test_workspaces_theme_c.py tests/services/speaker_studio/test_clip_service.py
	@cd packages/transcriptx_workspaces/transcriptx_workspaces/frontend && npm ci && npm test

test-theme-c-browser:
	@echo "Theme C Playwright browser suite..."
	@pytest -q tests/browser -m browser

docker-smoke:
	@echo "Running Docker first-run smoke test..."
	@bash scripts/docker-smoke-test.sh
