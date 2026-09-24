"""Shared pytest configuration.

Registers the ``docker`` marker (opt-in, ``-m docker``): tests that build/run real
Docker containers, e.g. ``tests/test_validate_docker.py``. Kept here, not in
``pyproject.toml``, so the pytest dependency/config owner and this marker's owner
can land independently without touching each other's files.
"""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "docker: opt-in, end-to-end tests that build/run real Docker containers"
    )
