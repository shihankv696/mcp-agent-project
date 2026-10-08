"""
test_search_files.py — Complete test suite for the search_files tool.

Test Categories:
    1. Correctness Tests   — does it find the right files?
    2. Security Tests      — does it block malicious inputs?
    3. Edge Case Tests     — does it handle unusual situations?
    4. Performance Tests   — does it stay within time limits?

How to run all tests:
    pytest tests/ -v

How to run one category:
    pytest tests/ -v -m correctness
    pytest tests/ -v -m security
    pytest tests/ -v -m edge_case
    pytest tests/ -v -m performance

How to run with coverage report:
    pytest tests/ -v --cov=tools --cov-report=term-missing
"""

from __future__ import annotations

import time
import asyncio
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ── Import the functions under test ──────────────────────────────────────────
from tools.file_searcher import (
    search_files,
    _validate_inputs,
    _resolve_directory,
    _collect_matches,
    _should_include_file,
    _build_result_message,
    initialize_search_tool,
    AccessDeniedError,
    DirectoryNotFoundError,
    NotADirectoryError,
    ValidationError,
)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def create_file(path: Path, content: str = "test content") -> Path:
    """
    Helper — create a file with given content.
    Creates parent directories automatically.
    Returns the file path for convenience.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def extract_text(result) -> str:
    """
    Helper — pull the text string out of a list[TextContent] result.
    Every search_files() call returns [TextContent(type="text", text="...")]
    This helper makes assertions cleaner: extract_text(result) == "..."
    """
    assert len(result) == 1, f"Expected 1 TextContent item, got {len(result)}"
    assert result[0].type == "text"
    return result[0].text


def run(coroutine):
    """
    Helper — run an async coroutine synchronously in tests.
    asyncio.run() creates a fresh event loop for each call.
    """
    return asyncio.run(coroutine)


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES — local to this file
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=False)
def patched_search(tmp_path, mock_config):
    """
    Patches the module-level config and resolved directories
    so every test uses tmp_path as the only allowed directory.

    autouse=False means you must explicitly request this fixture.
    """
    with patch("tools.file_searcher.config", mock_config), \
         patch(
             "tools.file_searcher._resolved_allowed_dirs",
             [tmp_path.resolve()]
         ), \
         patch(
             "tools.file_searcher._excluded_extensions",
             {".pyc", ".log"}
         ):
        yield tmp_path


@pytest.fixture(autouse=False)
def patched_search_exclude_hidden(tmp_path, mock_config_exclude_hidden):
    """Same as patched_search but with hidden files excluded."""
    with patch("tools.file_searcher.config", mock_config_exclude_hidden), \
         patch(
             "tools.file_searcher._resolved_allowed_dirs",
             [tmp_path.resolve()]
         ), \
         patch(
             "tools.file_searcher._excluded_extensions",
             {".pyc", ".log"}
         ):
        yield tmp_path


@pytest.fixture(autouse=False)
def patched_search_small_limit(tmp_path, mock_config_small_limit):
    """Same as patched_search but with MAX_SEARCH_RESULT = 3."""
    with patch("tools.file_searcher.config", mock_config_small_limit), \
         patch(
             "tools.file_searcher._resolved_allowed_dirs",
             [tmp_path.resolve()]
         ), \
         patch(
             "tools.file_searcher._excluded_extensions",
             set()
         ):
        yield tmp_path


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 1 — CORRECTNESS TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.correctness
class TestCorrectness:
    """
    Verifies the tool finds exactly the right files
    under normal, expected operating conditions.
    """

    # ── Test 1 ────────────────────────────────────────────────────────────────
    def test_query_matches_file_in_root_directory(self, patched_search):
        """
        SCENARIO:
            A file matching the query exists directly in the
            allowed root directory (not in any subfolder).

        EXPECTED:
            Tool finds it and returns its relative path.
        """
        root = patched_search

        # Arrange — create the file
        create_file(root / "project_notes.txt")

        # Act
        result = run(search_files("project", str(root)))
        text   = extract_text(result)

        # Assert
        assert "project_notes.txt" in text
        assert "No files found" not in text

    # ── Test 2 ────────────────────────────────────────────────────────────────
    def test_query_matches_file_in_nested_subdirectory(self, patched_search):
        """
        SCENARIO:
            The matching file is buried two levels deep:
            root/level1/level2/project_data.csv

        EXPECTED:
            Tool recurses into subfolders and finds the file.
        """
        root = patched_search

        # Arrange
        create_file(root / "level1" / "level2" / "project_data.csv")

        # Act
        result = run(search_files("project", str(root)))
        text   = extract_text(result)

        # Assert
        assert "project_data.csv" in text

    # ── Test 3 ────────────────────────────────────────────────────────────────
    def test_query_matches_multiple_files_all_returned(self, patched_search):
        """
        SCENARIO:
            Three files all match the query.
            They are spread across different directories.

        EXPECTED:
            All three appear in the result.
        """
        root = patched_search

        # Arrange
        create_file(root / "project_alpha.txt")
        create_file(root / "sub" / "project_beta.txt")
        create_file(root / "sub" / "deep" / "project_gamma.txt")

        # Act
        result = run(search_files("project", str(root)))
        text   = extract_text(result)

        # Assert
        assert "project_alpha.txt"  in text
        assert "project_beta.txt"   in text
        assert "project_gamma.txt"  in text

    # ── Test 4 ────────────────────────────────────────────────────────────────
    def test_query_matches_nothing_returns_empty_result(self, patched_search):
        """
        SCENARIO:
            Files exist in the directory but none match the query.
            This is a valid outcome — NOT an error condition.

        EXPECTED:
            Returns a helpful "no files found" message, not an error.
        """
        root = patched_search

        # Arrange — files that do NOT contain "zzzzzz"
        create_file(root / "readme.txt")
        create_file(root / "notes.md")

        # Act
        result = run(search_files("zzzzzz", str(root)))
        text   = extract_text(result)

        # Assert
        assert "No files found" in text
        assert "Error" not in text

    # ── Test 5 ────────────────────────────────────────────────────────────────
    def test_results_truncate_at_max_results(self, patched_search_small_limit):
        """
        SCENARIO:
            5 matching files exist but max_results = 3.

        EXPECTED:
            Exactly 3 results returned, not 4 or 5.
            is_truncated information appears in the message.
        """
        root = patched_search_small_limit

        # Arrange — create 5 matching files
        for i in range(1, 6):
            create_file(root / f"match_file_{i}.txt")

        # Act
        result = run(search_files("match_file", str(root)))
        text   = extract_text(result)

        # Assert — count bullet points in output
        bullet_count = text.count("  •")
        assert bullet_count == 3, (
            f"Expected exactly 3 results, got {bullet_count}"
        )

    # ── Test 6 ────────────────────────────────────────────────────────────────
    def test_is_truncated_flag_true_when_limit_hit(
        self, patched_search_small_limit
    ):
        """
        SCENARIO:
            More files match than max_results allows.

        EXPECTED:
            Output message mentions truncation / "3+" or "Showing first".
        """
        root = patched_search_small_limit

        # Arrange — 5 matches, limit is 3
        for i in range(5):
            create_file(root / f"report_{i}.txt")

        # Act
        result = run(search_files("report", str(root)))
        text   = extract_text(result)

        # Assert — truncation language appears
        truncation_indicated = (
            "3+" in text or
            "Showing first" in text or
            "limited to" in text
        )
        assert truncation_indicated, (
            f"Expected truncation message in output.\nGot: {text}"
        )

    # ── Test 7 ────────────────────────────────────────────────────────────────
    def test_is_truncated_flag_false_when_under_limit(self, patched_search):
        """
        SCENARIO:
            2 files match, max_results = 50 (default).

        EXPECTED:
            No truncation language in the output.
            Exact count shown.
        """
        root = patched_search

        # Arrange
        create_file(root / "alpha_report.txt")
        create_file(root / "beta_report.txt")

        # Act
        result = run(search_files("report", str(root)))
        text   = extract_text(result)

        # Assert
        assert "2 file(s)" in text
        assert "Showing first" not in text
        assert "limited to"   not in text

    # ── Test 8 ────────────────────────────────────────────────────────────────
    def test_search_is_case_insensitive(self, patched_search):
        """
        SCENARIO:
            File is named "ProjectNotes.txt" (mixed case).
            Query is "project" (all lowercase).

        EXPECTED:
            File is found — search must be case-insensitive.
        """
        root = patched_search

        # Arrange
        create_file(root / "ProjectNotes.txt")

        # Act
        result = run(search_files("project", str(root)))
        text   = extract_text(result)

        # Assert
        assert "ProjectNotes.txt" in text

    # ── Test 9 ────────────────────────────────────────────────────────────────
    def test_result_paths_are_relative_not_absolute(self, patched_search):
        """
        SCENARIO:
            A matching file is found.

        EXPECTED:
            The path shown in results is RELATIVE to the search root,
            not an absolute system path like C:\\Users\\...
        """
        root = patched_search

        # Arrange
        create_file(root / "sub" / "target_file.txt")

        # Act
        result = run(search_files("target_file", str(root)))
        text   = extract_text(result)

        # Assert — should show sub/target_file.txt not full absolute path
        assert str(root) not in text, (
            "Absolute path leaked into result output"
        )
        assert "target_file.txt" in text


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 2 — SECURITY TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.security
class TestSecurity:
    """
    Verifies the tool correctly blocks all path traversal,
    injection, and boundary-violation attempts.
    """

    # ── Test 10 ───────────────────────────────────────────────────────────────
    def test_directory_traversal_relative_path_blocked(
        self, patched_search
    ):
        """
        SCENARIO:
            Attacker passes "../../etc" hoping to escape the
            allowed directory and search system folders.

        EXPECTED:
            AccessDeniedError raised — path outside allowed dirs.
        """
        root = patched_search

        with pytest.raises(AccessDeniedError):
            _resolve_directory("../../etc")

    # ── Test 11 ───────────────────────────────────────────────────────────────
    def test_absolute_path_outside_allowed_blocked(self, patched_search):
        """
        SCENARIO:
            Attacker passes an absolute path like "/etc/passwd"
            (Linux) or "C:\\Windows\\System32" (Windows).

        EXPECTED:
            AccessDeniedError raised.
        """
        with pytest.raises(AccessDeniedError):
            _resolve_directory("/etc/passwd")

    # ── Test 12 ───────────────────────────────────────────────────────────────
    def test_windows_style_traversal_blocked(self, patched_search):
        """
        SCENARIO:
            Windows-style traversal attempt using backslashes.

        EXPECTED:
            AccessDeniedError raised.
        """
        with pytest.raises(AccessDeniedError):
            _resolve_directory("..\\..\\Windows\\System32")

    # ── Test 13 ───────────────────────────────────────────────────────────────
    def test_symlink_to_outside_allowed_directory_blocked(
        self, patched_search, tmp_path
    ):
        """
        SCENARIO:
            Inside the allowed directory, a symlink points to
            a folder OUTSIDE the allowed directory.
            Attacker passes the symlink path as directory_path.

        EXPECTED:
            AccessDeniedError raised because the RESOLVED path
            (where symlink actually points) is outside allowed dirs.
        """
        root = patched_search

        # Create a folder outside the allowed area
        outside_dir = tmp_path.parent / "outside_safe_zone"
        outside_dir.mkdir(exist_ok=True)

        # Create a symlink INSIDE allowed area pointing OUTSIDE
        symlink_path = root / "sneaky_link"
        try:
            symlink_path.symlink_to(outside_dir)
        except (OSError, NotImplementedError):
            pytest.skip("Symlink creation not supported on this OS/user")

        # Act + Assert — resolving the symlink reveals outside path
        with pytest.raises(AccessDeniedError):
            _resolve_directory(str(symlink_path))

    # ── Test 14 ───────────────────────────────────────────────────────────────
    def test_empty_search_query_raises_validation_error(
        self, patched_search
    ):
        """
        SCENARIO:
            search_query = "" (completely empty string)

        EXPECTED:
            ValidationError raised before any file system access.
        """
        root = patched_search

        with pytest.raises(ValidationError) as exc_info:
            _validate_inputs("", str(root))

        assert "empty" in exc_info.value.message.lower()

    # ── Test 15 ───────────────────────────────────────────────────────────────
    def test_whitespace_only_query_raises_validation_error(
        self, patched_search
    ):
        """
        SCENARIO:
            search_query = "   " (spaces only, no real content)

        EXPECTED:
            ValidationError raised — whitespace-only is treated as empty.
        """
        root = patched_search

        with pytest.raises(ValidationError):
            _validate_inputs("   ", str(root))

    # ── Test 16 ───────────────────────────────────────────────────────────────
    def test_query_exceeding_max_length_raises_validation_error(
        self, patched_search
    ):
        """
        SCENARIO:
            search_query is 201 characters (over the 200-char limit).

        EXPECTED:
            ValidationError raised with message mentioning length limit.
        """
        root        = patched_search
        long_query  = "a" * 201

        with pytest.raises(ValidationError) as exc_info:
            _validate_inputs(long_query, str(root))

        assert "200" in exc_info.value.message or \
               "long" in exc_info.value.message.lower()

    # ── Test 17 ───────────────────────────────────────────────────────────────
    def test_query_exactly_at_max_length_is_accepted(self, patched_search):
        """
        SCENARIO:
            search_query is exactly 200 characters (at the limit).

        EXPECTED:
            No ValidationError — 200 characters is allowed.
        """
        root          = patched_search
        exact_query   = "a" * 200

        # Should NOT raise
        cleaned_query, _ = _validate_inputs(exact_query, str(root))
        assert len(cleaned_query) == 200

    # ── Test 18 ───────────────────────────────────────────────────────────────
    def test_access_denied_error_message_reveals_no_system_path(
        self, patched_search
    ):
        """
        SCENARIO:
            An AccessDeniedError is triggered.

        EXPECTED:
            The error message does NOT reveal the actual allowed
            directory paths (information disclosure prevention).
        """
        root = patched_search

        try:
            _resolve_directory("/etc/passwd")
        except AccessDeniedError as exc:
            # Allowed dir path should NOT appear in error message
            assert str(root) not in exc.message, (
                "Allowed directory path leaked in error message"
            )

    # ── Test 19 ───────────────────────────────────────────────────────────────
    def test_single_dot_query_blocked_by_min_length(self, patched_search):
        """
        SCENARIO:
            search_query = "." — single dot matches almost every file
            because most files have extensions containing a dot.
            This is a reconnaissance attack.

        EXPECTED:
            ValidationError raised due to minimum query length.
        """
        root = patched_search

        with pytest.raises(ValidationError):
            _validate_inputs(".", str(root))

    # ── Test 20 ───────────────────────────────────────────────────────────────
    def test_result_returned_as_textcontent_not_raw_exception(
        self, patched_search
    ):
        """
        SCENARIO:
            An error condition is triggered via the public entry point.

        EXPECTED:
            search_files() NEVER raises an exception to the caller.
            It always returns list[TextContent] with an error message.
            Raw exceptions must never reach the MCP protocol layer.
        """
        root = patched_search

        # Empty query — would raise ValidationError internally
        result = run(search_files("", str(root)))

        # Must return list, not raise
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].type == "text"
        assert "Error" in result[0].text


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 3 — EDGE CASE TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.edge_case
class TestEdgeCases:
    """
    Verifies the tool handles unusual, boundary, and
    unexpected inputs gracefully without crashing.
    """

    # ── Test 21 ───────────────────────────────────────────────────────────────
    def test_empty_directory_returns_empty_result_no_crash(
        self, patched_search
    ):
        """
        SCENARIO:
            The target directory exists but contains no files at all.

        EXPECTED:
            Returns "No files found" message.
            Does NOT crash or raise an exception.
        """
        root = patched_search
        # root directory is empty — no files created

        result = run(search_files("anything", str(root)))
        text   = extract_text(result)

        assert "No files found" in text

    # ── Test 22 ───────────────────────────────────────────────────────────────
    def test_only_hidden_files_with_exclude_hidden_returns_empty(
        self, patched_search_exclude_hidden
    ):
        """
        SCENARIO:
            Directory contains ONLY hidden files (.hidden_notes.txt).
            EXCLUDE_HIDDEN_FILES = True in config.

        EXPECTED:
            Hidden files are skipped entirely.
            Returns empty result.
        """
        root = patched_search_exclude_hidden

        # Arrange — create only hidden files
        create_file(root / ".hidden_notes.txt")
        create_file(root / ".secret_config.json")

        # Act
        result = run(search_files("notes", str(root)))
        text   = extract_text(result)

        # Assert
        assert "No files found" in text

    # ── Test 23 ───────────────────────────────────────────────────────────────
    def test_only_excluded_extensions_returns_empty(self, patched_search):
        """
        SCENARIO:
            Directory has files but all have excluded extensions
            (.pyc and .log are in EXCLUDED_EXTENSIONS).

        EXPECTED:
            All files skipped. Returns empty result.
        """
        root = patched_search

        # Arrange — only .pyc and .log files
        create_file(root / "notes_cache.pyc")
        create_file(root / "notes_server.log")

        # Act
        result = run(search_files("notes", str(root)))
        text   = extract_text(result)

        # Assert
        assert "No files found" in text

    # ── Test 24 ───────────────────────────────────────────────────────────────
    def test_file_with_no_extension_is_handled_correctly(
        self, patched_search
    ):
        """
        SCENARIO:
            A file has no extension at all — e.g. "Makefile", "README"

        EXPECTED:
            File is matched correctly if query matches.
            No crash from extension-parsing code.
        """
        root = patched_search

        # Arrange — file with no extension
        create_file(root / "README")
        create_file(root / "Makefile")

        # Act
        result = run(search_files("make", str(root)))
        text   = extract_text(result)

        # Assert
        assert "Makefile" in text
        assert "Error" not in text

    # ── Test 25 ───────────────────────────────────────────────────────────────
    def test_very_deeply_nested_file_is_found(self, patched_search):
        """
        SCENARIO:
            A matching file is buried 6 levels deep in subfolders.

        EXPECTED:
            Recursive walk finds it regardless of depth.
        """
        root = patched_search

        # Arrange — 6 levels deep
        deep_path = (
            root / "a" / "b" / "c" / "d" / "e" / "f" / "deep_target.txt"
        )
        create_file(deep_path)

        # Act
        result = run(search_files("deep_target", str(root)))
        text   = extract_text(result)

        # Assert
        assert "deep_target.txt" in text

    # ── Test 26 ───────────────────────────────────────────────────────────────
    def test_directory_path_not_provided_uses_default(
        self, patched_search
    ):
        """
        SCENARIO:
            directory_path = "" (empty string — not provided by agent).

        EXPECTED:
            Tool uses the first allowed directory as the default.
            Does NOT crash or raise ValidationError.
        """
        root = patched_search

        # Arrange — file in the default (first allowed) directory
        create_file(root / "default_dir_file.txt")

        # Act — empty string for directory_path
        result = run(search_files("default_dir_file", ""))
        text   = extract_text(result)

        # Assert
        assert "default_dir_file.txt" in text

    # ── Test 27 ───────────────────────────────────────────────────────────────
    def test_nonexistent_directory_returns_error_message(
        self, patched_search
    ):
        """
        SCENARIO:
            directory_path points to a folder that does not exist.

        EXPECTED:
            DirectoryNotFoundError raised internally.
            Public search_files() returns a helpful error message.
        """
        root = patched_search
        nonexistent = str(root / "this_does_not_exist")

        # Act
        result = run(search_files("anything", nonexistent))
        text   = extract_text(result)

        # Assert
        assert "Error" in text
        assert "exist" in text.lower() or "not found" in text.lower()

    # ── Test 28 ───────────────────────────────────────────────────────────────
    def test_file_path_passed_as_directory_returns_error(
        self, patched_search
    ):
        """
        SCENARIO:
            directory_path points to a FILE, not a directory.
            Agent made a mistake passing a file path.

        EXPECTED:
            NotADirectoryError raised internally.
            Public search_files() returns an informative error message.
        """
        root = patched_search

        # Arrange — a real file (not a directory)
        file_path = create_file(root / "some_file.txt")

        # Act — pass a file path as the directory to search
        result = run(search_files("anything", str(file_path)))
        text   = extract_text(result)

        # Assert
        assert "Error" in text

    # ── Test 29 ───────────────────────────────────────────────────────────────
    def test_query_with_special_characters_handled_safely(
        self, patched_search
    ):
        """
        SCENARIO:
            search_query contains special characters like * ; | &
            These are dangerous in shell contexts.

        EXPECTED:
            Treated as plain text substring search.
            No command injection. No crash.
        """
        root = patched_search

        # Arrange
        create_file(root / "normal_file.txt")

        # Act — special chars treated as literal search text
        result = run(search_files("*.txt", str(root)))
        text   = extract_text(result)

        # Assert — does not crash, returns valid response
        assert isinstance(text, str)
        assert "Error" not in text or "No files found" in text

    # ── Test 30 ───────────────────────────────────────────────────────────────
    def test_unicode_filename_found_correctly(self, patched_search):
        """
        SCENARIO:
            Filename contains Unicode characters (common in
            non-English file systems).

        EXPECTED:
            File found correctly — no encoding crash.
        """
        root = patched_search

        try:
            create_file(root / "日本語_notes.txt")
        except (OSError, UnicodeEncodeError):
            pytest.skip("File system does not support Unicode filenames")

        # Act
        result = run(search_files("notes", str(root)))
        text   = extract_text(result)

        # Assert
        assert "notes" in text or "No files found" in text


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 4 — PERFORMANCE TESTS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.performance
class TestPerformance:
    """
    Verifies the tool completes within acceptable time limits
    and that optimizations like early-exit work correctly.
    """

    # ── Test 31 ───────────────────────────────────────────────────────────────
    def test_1000_files_completes_under_2_seconds(self, patched_search):
        """
        SCENARIO:
            Directory contains 1000 files.
            None of them match the query.

        EXPECTED:
            Full search completes in under 2 seconds.
        """
        root = patched_search

        # Arrange — create 1000 non-matching files
        for i in range(1000):
            create_file(root / f"irrelevant_file_{i:04d}.txt")

        # Act + Time
        start  = time.monotonic()
        result = run(search_files("zzzzzz_no_match", str(root)))
        elapsed = time.monotonic() - start

        # Assert
        text = extract_text(result)
        assert "No files found" in text
        assert elapsed < 2.0, (
            f"Search took {elapsed:.2f}s — expected under 2.0s"
        )

    # ── Test 32 ───────────────────────────────────────────────────────────────
    def test_truncation_stops_walk_early(
        self, patched_search_small_limit
    ):
        """
        SCENARIO:
            1000 matching files exist. max_results = 3.

        EXPECTED:
            Tool returns exactly 3 results AND completes
            significantly faster than scanning all 1000 files.
            (Early exit is working.)
        """
        root = patched_search_small_limit

        # Arrange — 1000 matching files
        for i in range(1000):
            create_file(root / f"target_{i:04d}.txt")

        # Time the full scan (no match) for baseline
        start_baseline = time.monotonic()
        run(search_files("xxxxxx_no_match", str(root)))
        baseline_time = time.monotonic() - start_baseline

        # Time the truncated scan
        start_search = time.monotonic()
        result = run(search_files("target", str(root)))
        search_time = time.monotonic() - start_search

        text = extract_text(result)

        # Assert — exactly 3 results returned
        bullet_count = text.count("  •")
        assert bullet_count == 3, (
            f"Expected 3 results after truncation, got {bullet_count}"
        )

        # Assert — truncated search was faster than full scan
        assert search_time < baseline_time, (
            f"Early exit not working: "
            f"truncated={search_time:.3f}s baseline={baseline_time:.3f}s"
        )

    # ── Test 33 ───────────────────────────────────────────────────────────────
    def test_deeply_nested_1000_files_performance(self, patched_search):
        """
        SCENARIO:
            1000 files spread across 100 subdirectories (10 per dir).

        EXPECTED:
            Completes in under 2 seconds despite deep structure.
        """
        root = patched_search

        # Arrange — files spread across nested dirs
        for i in range(100):
            subdir = root / f"dir_{i:03d}"
            for j in range(10):
                create_file(subdir / f"file_{i:03d}_{j:02d}.txt")

        # Act + Time
        start   = time.monotonic()
        result  = run(search_files("zzzzzz_no_match", str(root)))
        elapsed = time.monotonic() - start

        # Assert
        assert elapsed < 2.0, (
            f"Nested search took {elapsed:.2f}s — expected under 2.0s"
        )


# ═════════════════════════════════════════════════════════════════════════════
# SECTION 5 — UNIT TESTS FOR HELPER FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestHelperFunctions:
    """
    Tests internal helper functions in isolation.
    Faster than full integration tests.
    """

    # ── Test 34 ───────────────────────────────────────────────────────────────
    def test_validate_inputs_strips_whitespace_from_query(
        self, patched_search
    ):
        """_validate_inputs should strip leading/trailing whitespace."""
        root = patched_search

        cleaned_query, _ = _validate_inputs("  project  ", str(root))
        assert cleaned_query == "project"

    # ── Test 35 ───────────────────────────────────────────────────────────────
    def test_validate_inputs_returns_lowercase_query(self, patched_search):
        """_validate_inputs should return query in lowercase."""
        root = patched_search

        cleaned_query, _ = _validate_inputs("PROJECT", str(root))
        assert cleaned_query == "project"

    # ── Test 36 ───────────────────────────────────────────────────────────────
    def test_build_result_message_empty_matches(self):
        """_build_result_message returns correct text for no results."""
        message = _build_result_message(
            matches=[],
            search_query="project",
            is_truncated=False,
            max_results=50,
            permission_errors=0,
        )
        assert "No files found" in message
        assert "project" in message

    # ── Test 37 ───────────────────────────────────────────────────────────────
    def test_build_result_message_with_permission_errors_note(self):
        """_build_result_message appends permission error note."""
        message = _build_result_message(
            matches=["file.txt"],
            search_query="file",
            is_truncated=False,
            max_results=50,
            permission_errors=3,
        )
        assert "3" in message
        assert "permission" in message.lower()

    # ── Test 38 ───────────────────────────────────────────────────────────────
    def test_should_include_file_false_for_hidden_when_excluded(
        self, tmp_path
    ):
        """_should_include_file returns False for hidden files when excluded."""
        hidden_file = tmp_path / ".hidden_notes.txt"
        hidden_file.touch()

        result = _should_include_file(
            filename=".hidden_notes.txt",
            file_path=hidden_file,
            query_lower="notes",
            exclude_hidden=True,
        )
        assert result is False

    # ── Test 39 ───────────────────────────────────────────────────────────────
    def test_should_include_file_true_for_matching_file(self, tmp_path):
        """_should_include_file returns True for valid matching file."""
        normal_file = tmp_path / "project_notes.txt"
        normal_file.touch()

        with patch(
            "tools.file_searcher._excluded_extensions", set()
        ):
            result = _should_include_file(
                filename="project_notes.txt",
                file_path=normal_file,
                query_lower="project",
                exclude_hidden=False,
            )
        assert result is True

    # ── Test 40 ───────────────────────────────────────────────────────────────
    def test_initialize_search_tool_raises_on_bad_config(self):
        """initialize_search_tool raises RuntimeError on invalid config."""
        bad_config = MagicMock()
        bad_config.ALLOWED_DIRECTORIES  = "not_a_list"  # wrong type
        bad_config.MAX_SEARCH_RESULT    = 50
        bad_config.EXCLUDED_EXTENSIONS  = []
        bad_config.EXCLUDE_HIDDEN_FILES = False

        with patch("tools.file_searcher.config", bad_config):
            with pytest.raises(RuntimeError) as exc_info:
                initialize_search_tool()
            assert "ALLOWED_DIRECTORIES" in str(exc_info.value)