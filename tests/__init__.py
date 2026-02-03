"""Test package marker for reliable intra-test imports."""
"""
Test package marker.

This file prevents Python from treating `tests` as a namespace package across multiple
checkouts on `sys.path`, which can cause pytest to import and execute the wrong test
modules when another `tests/` directory exists elsewhere on the machine.
"""

"""
Test suite for TranscriptX.

This package contains comprehensive unit and integration tests for the TranscriptX
transcript analysis toolkit. Tests are organized into:

- unit/: Unit tests for individual functions and classes
- integration/: Integration tests for workflows and pipelines
- fixtures/: Shared test data and fixtures

The test suite uses pytest with coverage reporting and includes mocks for
heavy dependencies like ML models and external APIs.
"""
