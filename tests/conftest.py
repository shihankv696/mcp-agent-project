"""
conftest.py — Shared pytest fixtures for all test files.

Fixtures defined here are automatically available to every
test file in the tests/ directory without any imports.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────
# Config Mock Fixture
# ─────────────────────────────────────────────

@pytest.fixture
def mock_config(tmp_path):
    """
    Provides a mock config object pointing to a safe
    temporary directory that is deleted after each test.

    tmp_path is a built-in pytest fixture that creates
    a unique temporary folder for each test automatically.
    """
    config = MagicMock()
    config.ALLOWED_DIRECTORIES  = [str(tmp_path)]
    config.MAX_SEARCH_RESULT    = 50
    config.EXCLUDED_EXTENSIONS  = [".pyc", ".log"]
    config.EXCLUDE_HIDDEN_FILES = False
    config.DEBUG_MODE           = False
    return config


@pytest.fixture
def mock_config_exclude_hidden(tmp_path):
    """Config variant with hidden file exclusion enabled."""
    config = MagicMock()
    config.ALLOWED_DIRECTORIES  = [str(tmp_path)]
    config.MAX_SEARCH_RESULT    = 50
    config.EXCLUDED_EXTENSIONS  = [".pyc", ".log"]
    config.EXCLUDE_HIDDEN_FILES = True
    config.DEBUG_MODE           = False
    return config


@pytest.fixture
def mock_config_small_limit(tmp_path):
    """Config variant with a very small result limit for truncation tests."""
    config = MagicMock()
    config.ALLOWED_DIRECTORIES  = [str(tmp_path)]
    config.MAX_SEARCH_RESULT    = 3
    config.EXCLUDED_EXTENSIONS  = []
    config.EXCLUDE_HIDDEN_FILES = False
    config.DEBUG_MODE           = False
    return config