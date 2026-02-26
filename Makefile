# TranscriptX Makefile
# Main targets for documentation and development

.PHONY: docs-gen docs docs-clean help test-smoke test-fast test-all test-contracts test-integration-core test-optional secrets-hf up-secrets

help:
	@echo "TranscriptX Makefile"
	@echo ""
	@echo "Documentation targets:"
	@echo "  docs-gen     Generate documentation from code (CLI, modules) -> docs/generated/"
	@echo "  docs         Same as docs-gen (Sphinx build deferred; see docs/ROADMAP.md)"
	@echo "  docs-clean   Remove generated docs and build artifacts"
	@echo ""
	@echo "Docker secrets (Hugging Face token):"
	@echo "  secrets-hf   Create ./secrets/hf_token (prompt for token, chmod 600)"
	@echo "  up-secrets   docker compose with secrets override"
	@echo ""
	@echo "Testing targets:"
	@echo "  test-smoke       Run CI smoke gate"
	@echo "  test-fast        Run fast core (Gate B)"
	@echo "  test-contracts   Run offline contract tests"
	@echo "  test-all         Run full test suite (may be slow)"
	@echo ""
	@echo "Usage:"
	@echo "  make docs          # Generate docs from code"
	@echo "  make docs-clean    # Clean generated docs"

docs-gen:
	@echo "Generating documentation from code..."
	@python scripts/generate_docs.py

docs: docs-gen
	@echo "Documentation generated. Outputs in docs/generated/"
	@echo "(Full Sphinx HTML build deferred — see docs/ROADMAP.md; README is canonical.)"

docs-clean:
	@echo "Cleaning documentation build and generated files..."
	@rm -rf docs/_build docs/generated docs/api/generated
	@echo "Documentation cleaned!"

secrets-hf:
	@mkdir -p secrets
	@bash -c 'echo "Enter your Hugging Face token (will be written to ./secrets/hf_token, chmod 600):"; read -s token; printf "%s" "$$token" > secrets/hf_token; chmod 600 secrets/hf_token; echo "Done. File secrets/hf_token created."'

up-secrets:
	docker compose -f docker-compose.yml -f docker-compose.secrets.yml up

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
	@echo "Running optional capability tests..."
	@pytest -m "slow or requires_models or requires_docker or requires_ffmpeg"

test-all:
	@pytest
