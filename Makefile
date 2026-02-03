# TranscriptX Makefile
# Main targets for documentation and development

.PHONY: docs-gen docs docs-serve docs-clean help test-smoke test-fast test-all test-contracts test-integration-core test-optional

help:
	@echo "TranscriptX Makefile"
	@echo ""
	@echo "Documentation targets:"
	@echo "  docs-gen     Generate documentation from code (CLI, modules)"
	@echo "  docs         Generate and build documentation"
	@echo "  docs-serve   Generate, build, and serve documentation with live reload"
	@echo "  docs-clean   Clean documentation build and generated files"
	@echo ""
	@echo "Testing targets:"
	@echo "  test-smoke       Run CI smoke gate"
	@echo "  test-fast        Run fast core (Gate B)"
	@echo "  test-contracts   Run offline contract tests"
	@echo "  test-all         Run full test suite (may be slow)"
	@echo ""
	@echo "Usage:"
	@echo "  make docs-serve    # Start local documentation server"
	@echo "  make docs          # Build documentation"
	@echo "  make docs-clean    # Clean all documentation files"

docs-gen:
	@echo "Generating documentation from code..."
	@python scripts/generate_docs.py

docs: docs-gen
	@echo "Building documentation..."
	@$(MAKE) -C docs html
	@echo ""
	@echo "Documentation built successfully!"
	@echo "Open docs/_build/html/index.html in your browser"

docs-serve: docs-gen
	@echo "Starting documentation server with live reload..."
	@echo "Documentation will be available at http://localhost:8000"
	@echo "Press Ctrl+C to stop the server"
	@sphinx-autobuild docs docs/_build/html --open-browser

docs-clean:
	@echo "Cleaning documentation build and generated files..."
	@rm -rf docs/_build docs/generated docs/api/generated
	@$(MAKE) -C docs clean
	@echo "Documentation cleaned!"

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
