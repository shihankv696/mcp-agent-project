"""
search_files tool — finds files by name within allowed directories.

Required config attributes:
    ALLOWED_DIRECTORIES  (list[str])  — folders the tool may search
    MAX_SEARCH_RESULT    (int)        — maximum matches to return
    EXCLUDED_EXTENSIONS  (list|set)   — file extensions to skip
    EXCLUDE_HIDDEN_FILES (bool)       — whether to skip dotfiles

Initialization:
    Call initialize_search_tool() once at server startup.
"""

from __future__ import annotations

import os
import stat
import logging
from pathlib import Path

from server import config
from mcp.types import TextContent

__all__ = ["search_files", "initialize_search_tool"]

logger = logging.getLogger(__name__)

MAX_QUERY_LENGTH = 200
MIN_QUERY_LENGTH = 2

CONFIG_TYPE_EXPECTATIONS: dict[str, tuple[type, ...]] = {
    "ALLOWED_DIRECTORIES":  (list,),
    "MAX_SEARCH_RESULT":    (int,),
    "EXCLUDED_EXTENSIONS":  (list, set),
    "EXCLUDE_HIDDEN_FILES": (bool,),
}


# ─────────────────────────────────────────────
# Custom Exceptions
# ─────────────────────────────────────────────

class SearchToolError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

class AccessDeniedError(SearchToolError):
    pass

class DirectoryNotFoundError(SearchToolError):
    pass

class NotADirectoryError(SearchToolError):
    pass

class ValidationError(SearchToolError):
    pass


# ─────────────────────────────────────────────
# Runtime State (populated by initialize_search_tool)
# ─────────────────────────────────────────────

_resolved_allowed_dirs: list[Path] = []
_excluded_extensions: set[str] = set()


# ─────────────────────────────────────────────
# Startup Initialization
# ─────────────────────────────────────────────

def initialize_search_tool() -> None:
    """
    Validate config and resolve paths.
    Must be called once at server startup before any search requests.
    """
    global _resolved_allowed_dirs, _excluded_extensions

    for attr, expected_types in CONFIG_TYPE_EXPECTATIONS.items():
        if not hasattr(config, attr):
            raise RuntimeError(f"config.{attr} is not defined.")
        value = getattr(config, attr)
        if not isinstance(value, expected_types):
            raise RuntimeError(
                f"config.{attr} must be {expected_types} "
                f"but got {type(value).__name__!r}."
            )

    _resolved_allowed_dirs = [
        Path(d).resolve() for d in config.ALLOWED_DIRECTORIES
    ]
    _excluded_extensions = {
        ext.lower() for ext in config.EXCLUDED_EXTENSIONS
    }

    logger.info(
        "search_files tool initialized. "
        "Allowed directories: %d",
        len(_resolved_allowed_dirs),
    )


# ─────────────────────────────────────────────
# Security Helpers
# ─────────────────────────────────────────────

def _is_path_allowed(absolute_path: Path) -> bool:
    """Return True if absolute_path is inside an allowed directory."""
    for allowed in _resolved_allowed_dirs:
        try:
            absolute_path.relative_to(allowed)
            return True
        except ValueError:
            continue
    return False


# ─────────────────────────────────────────────
# Input Validation
# ─────────────────────────────────────────────

def _validate_inputs(
    search_query: str,
    directory_path: str,
) -> tuple[str, str]:
    """
    Validate and normalise inputs.
    Returns (cleaned_query_lowercase, directory_path).
    Raises ValidationError on invalid inputs.
    """
    cleaned = search_query.strip() if search_query else ""

    if not cleaned:
        raise ValidationError("Search query cannot be empty.")

    if len(cleaned) < MIN_QUERY_LENGTH:
        raise ValidationError(
            f"Search query must be at least {MIN_QUERY_LENGTH} characters."
        )

    if len(cleaned) > MAX_QUERY_LENGTH:
        raise ValidationError(
            f"Search query too long. Maximum {MAX_QUERY_LENGTH} characters."
        )

    if not directory_path or not directory_path.strip():
        if not _resolved_allowed_dirs:
            raise ValidationError("No allowed directories are configured.")
        directory_path = str(_resolved_allowed_dirs[0])

    # Return lowercase query — single responsibility for case handling
    return cleaned.lower(), directory_path


# ─────────────────────────────────────────────
# Directory Resolution
# ─────────────────────────────────────────────

def _resolve_directory(directory_path: str) -> Path:
    """
    Resolve, security-check, and validate the target directory.
    Raises appropriate SearchToolError subclass on any failure.
    """
    absolute_path = Path(directory_path).resolve()

    if not _is_path_allowed(absolute_path):
        logger.warning("SECURITY: Access denied — path outside allowed dirs.")
        raise AccessDeniedError(
            "Access denied. Path is outside allowed directories."
        )

    if not absolute_path.exists():
        raise DirectoryNotFoundError(
            f"Directory does not exist: '{directory_path}'"
        )

    if not absolute_path.is_dir():
        raise NotADirectoryError(
            f"Path is a file, not a directory: '{directory_path}'"
        )

    return absolute_path


# ─────────────────────────────────────────────
# File Filter
# ─────────────────────────────────────────────

def _should_include_file(
    filename: str,
    file_path: Path,
    query_lower: str,
    exclude_hidden: bool,
) -> bool:
    """
    Single responsibility filter — returns True if file
    matches all inclusion criteria.
    """
    # Cheapest check first — query match in filename
    if query_lower not in filename.lower():
        return False

    # Hidden file check
    if exclude_hidden and filename.startswith("."):
        return False

    # Extension check — only compute splitext when needed
    _, ext = os.path.splitext(filename)
    if ext.lower() in _excluded_extensions:
        return False

    # Symlink check using lstat for atomicity
    try:
        stat_result = file_path.lstat()
        if stat.S_ISLNK(stat_result.st_mode):
            return False
    except OSError:
        return False

    return True


# ─────────────────────────────────────────────
# Core Search Logic
# ─────────────────────────────────────────────

def _collect_matches(
    absolute_path: Path,
    query_lower: str,
    max_results: int,
    exclude_hidden: bool,
) -> tuple[list[str], bool, int]:
    """
    Walk directory recursively and collect matching filenames.

    Returns:
        (matches, is_truncated, permission_error_count)
    """
    matches: list[str] = []
    is_truncated = False
    error_count = [0]   # mutable container avoids nonlocal

    def _on_walk_error(error: OSError) -> None:
        error_count[0] += 1
        logger.warning("Permission denied reading a directory during search.")

    stop_search = False

    for root, dirs, files in os.walk(
        absolute_path,
        followlinks=False,
        onerror=_on_walk_error,
    ):
        if stop_search:
            break

        if exclude_hidden:
            dirs[:] = [d for d in dirs if not d.startswith(".")]

        root_path = Path(root)

        for filename in files:
            file_path = root_path / filename

            try:
                if not _should_include_file(
                    filename, file_path, query_lower, exclude_hidden
                ):
                    continue

                # Check limit BEFORE appending (fixes off-by-one)
                if len(matches) >= max_results:
                    is_truncated = True
                    dirs.clear()
                    stop_search = True
                    break

                try:
                    relative = file_path.relative_to(absolute_path)
                    matches.append(str(relative))
                except ValueError:
                    logger.debug(
                        "Could not compute relative path for: %s", filename
                    )

            except PermissionError:
                error_count[0] += 1
                logger.warning("Permission denied accessing a file.")
            except OSError as exc:
                logger.warning("OS error accessing a file: %s", exc)

    return matches, is_truncated, error_count[0]


# ─────────────────────────────────────────────
# Result Formatting
# ─────────────────────────────────────────────

def _build_result_message(
    matches: list[str],
    search_query: str,
    is_truncated: bool,
    max_results: int,
    permission_errors: int,
) -> str:
    """Build a human-readable summary of search results."""
    if not matches:
        return f"No files found matching '{search_query}'."

    matches_text = "\n".join(f"  • {m}" for m in matches)

    count_label = (
        f"{max_results}+" if is_truncated else str(len(matches))
    )
    base = (
        f"Found {count_label} file(s) matching '{search_query}'.\n\n"
        f"Matches:\n{matches_text}"
    )

    if is_truncated:
        base += (
            f"\n\nResults limited to {max_results}. "
            f"Narrow your search for more precise results."
        )

    if permission_errors > 0:
        base += (
            f"\n\nNote: {permission_errors} location(s) skipped "
            f"due to permission errors."
        )

    return base


# ─────────────────────────────────────────────
# Public Tool Entry Point
# ─────────────────────────────────────────────

async def search_files(
    search_query: str,
    directory_path: str = "",
) -> list[TextContent]:
    """
    Search for files whose names contain search_query.

    Args:
        search_query:   Text to find in filenames (case-insensitive,
                        min 2 chars, max 200 chars).
        directory_path: Folder to search. Defaults to first allowed dir.

    Returns:
        list[TextContent] — MCP protocol requires list wrapper.
        Always returns a list, never raises to caller.
    """
    # --- Validation and Resolution ---
    try:
        query_lower, directory_path = _validate_inputs(
            search_query, directory_path
        )
        absolute_path = _resolve_directory(directory_path)

    except SearchToolError as exc:
        return [TextContent(type="text", text=f"Error: {exc.message}")]

    except Exception as exc:
        logger.error(
            "Unexpected error during validation: %s", exc, exc_info=True
        )
        return [TextContent(type="text", text="An unexpected error occurred.")]

    # --- Search ---
    try:
        matches, is_truncated, permission_errors = _collect_matches(
            absolute_path=absolute_path,
            query_lower=query_lower,
            max_results=config.MAX_SEARCH_RESULT,
            exclude_hidden=config.EXCLUDE_HIDDEN_FILES,
        )
    except Exception as exc:
        logger.error(
            "Unexpected error during search: %s", exc, exc_info=True
        )
        return [TextContent(
            type="text",
            text="Search failed due to an unexpected error."
        )]

    # --- Format and Return ---
    # MCP protocol requires list[TextContent] even for single responses
    message = _build_result_message(
        matches=matches,
        search_query=search_query,   # original case for display
        is_truncated=is_truncated,
        max_results=config.MAX_SEARCH_RESULT,
        permission_errors=permission_errors,
    )

    return [TextContent(type="text", text=message)]