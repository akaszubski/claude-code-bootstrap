#!/usr/bin/env python3
"""
Path Utilities - Centralized project root detection and path resolution

This module provides centralized path resolution for tracking infrastructure:
- Dynamic PROJECT_ROOT detection (searches for .git/ or .claude/)
- Session directory resolution
- Batch state file resolution
- Directory creation with proper permissions

Fixes Issue #79: Hardcoded paths in tracking infrastructure

Security Features:
- All paths resolve from PROJECT_ROOT (not current working directory)
- Works from any subdirectory
- Creates directories with safe permissions (0o755)
- No hardcoded relative paths

Usage:
    from path_utils import get_project_root, get_session_dir, get_batch_state_file

    # Get project root
    root = get_project_root()

    # Get session directory (creates if missing)
    session_dir = get_session_dir()

    # Get batch state file path
    state_file = get_batch_state_file()

Date: 2025-11-17
Issue: GitHub #79 (Tracking infrastructure hardcoded paths)
Agent: implementer

Design Patterns:
    See library-design-patterns skill for standardized design patterns.
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional, List, Callable


# Cache for project root (avoid repeated filesystem searches)
_PROJECT_ROOT_CACHE: Optional[Path] = None

# Cache for policy file (avoid repeated filesystem searches)
_POLICY_FILE_CACHE: Optional[Path] = None

# Lazy import of is_worktree (to avoid circular import)
# This is initialized on first use in get_batch_state_file()
_is_worktree_func: Optional[Callable[[], bool]] = None


class PolicyFileNotFoundError(Exception):
    """Exception raised when policy file cannot be found in any location."""
    pass


class LogDirResolutionError(RuntimeError):
    """Raised when the activity-log directory cannot be tied to a project root.

    Issue #1726: the previous behaviour on this path was an unconditional
    ``cwd / ".claude" / "logs" / "activity"`` fallback, which silently split
    the session record across whatever directory the hook happened to run in.
    Failing loudly is the point — a partial log that nobody can tell is
    partial is worse than no log.
    """
    pass


def _worktree_parent_log_dir(start: Path) -> Optional[Path]:
    """Resolve the PARENT repo's activity-log dir when ``start`` is a worktree.

    Issue #755: hooks running inside ``<repo>/.worktrees/<name>/`` must write to
    the parent repo's log so post-session analysis sees one record, not two.

    Args:
        start: Absolute path to resolve from (normally the current directory).

    Returns:
        ``<parent_repo>/.claude/logs/activity`` when ``start`` is inside a
        ``.worktrees/`` tree AND the parent repo has a ``.claude`` directory;
        otherwise None (caller falls through to the normal resolution).
    """
    start_str = str(start)
    if "/.worktrees/" not in start_str and "\\.worktrees\\" not in start_str:
        return None
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, timeout=5, cwd=start_str,
        )
        if result.returncode != 0:
            return None
        common_dir = Path(result.stdout.strip())
        parent_repo = common_dir.parent if common_dir.name == ".git" else common_dir
        claude_dir = parent_repo / ".claude"
        if claude_dir.exists():
            return claude_dir / "logs" / "activity"
    except Exception:
        return None
    return None


def resolve_activity_log_dir(*, start_path: Optional[Path] = None) -> Path:
    """Resolve ``<project_root>/.claude/logs/activity`` — never relative to cwd.

    Canonical resolver for every hook that appends to the session activity log.
    Issue #1726: three producers (``session_activity_logger``,
    ``unified_session_tracker``, ``unified_pre_tool``) each walked up from the
    current directory to the FIRST ``.claude/`` they found and fell back to
    ``cwd/.claude/logs/activity`` when there was none. One stray ``.claude/``
    below the repo root therefore captured every subsequent hook invocation
    from a deeper directory — permanently, because the walk-up keeps finding
    it first.

    Resolution order:

    1. **Worktree parent** (Issue #755) — when ``start_path`` is inside a
       ``.worktrees/`` tree, the parent repo's ``.claude`` wins. Checked first
       so a ``CLAUDE_PROJECT_DIR`` pointing at the worktree cannot reopen the
       split #755 closed.
    2. ``CLAUDE_PROJECT_DIR`` when set to an existing directory.
    3. :func:`find_project_root`, which searches for ``.git`` all the way up
       before considering ``.claude`` — that priority is precisely what makes
       a stray ``.claude`` below the root lose.
    4. Loud failure — :class:`LogDirResolutionError`, never a cwd fallback.

    Args:
        start_path: Directory to resolve from. Defaults to the current
            working directory.

    Returns:
        Absolute path to the activity-log directory. The directory is NOT
        created; callers do that.

    Raises:
        LogDirResolutionError: If no project root can be determined.
    """
    start = Path(start_path) if start_path is not None else Path.cwd()

    worktree_dir = _worktree_parent_log_dir(start)
    if worktree_dir is not None:
        return worktree_dir

    env_root = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    if env_root:
        candidate = Path(env_root)
        try:
            if candidate.is_dir():
                return candidate / ".claude" / "logs" / "activity"
        except OSError:
            pass  # Unreadable value is not a reason to fall back to cwd

    try:
        root = find_project_root(start_path=start)
    except FileNotFoundError as exc:
        message = (
            f"Cannot resolve the activity-log directory from {start}\n"
            f"Expected: CLAUDE_PROJECT_DIR set, or a .git/.claude marker in an "
            f"ancestor directory\n"
            f"Refusing to fall back to the current directory (Issue #1726)"
        )
        try:
            sys.stderr.write(f"[path_utils] {message}\n")
        except Exception:
            pass
        raise LogDirResolutionError(message) from exc

    return root / ".claude" / "logs" / "activity"


def find_project_root(
    marker_files: Optional[List[str]] = None,
    start_path: Optional[Path] = None
) -> Path:
    """Find project root by searching upward for marker files.

    Searches from current working directory upward until it finds a directory
    containing one of the marker files (.git/, .claude/, etc).

    Search strategy:
    - Prioritizes .git over .claude (searches all the way up for .git first)
    - Only searches for .claude if .git not found anywhere
    - This ensures git repos with nested .claude dirs work correctly

    Args:
        marker_files: List of marker files/directories to search for.
                     Defaults to [".git", ".claude"] (priority order)
        start_path: Starting path for search. Defaults to current working directory.

    Returns:
        Path to project root (directory containing marker file)

    Raises:
        FileNotFoundError: If no marker file found (reached filesystem root)

    Examples:
        >>> root = find_project_root()  # Search from cwd
        >>> root = find_project_root(start_path=Path("/path/to/nested/dir"))
        >>> root = find_project_root(marker_files=[".git", "setup.py"])

    Security:
        - No path traversal risk (only searches upward, never downward)
        - Stops at filesystem root (prevents infinite loops)
        - Validates marker files exist before returning
    """
    if marker_files is None:
        marker_files = [".git", ".claude"]

    if start_path is None:
        start_path = Path.cwd()

    # Resolve to absolute path (handles symlinks)
    start = start_path.resolve()

    # Priority-based search: Search ALL the way up for each marker in order
    # This ensures .git takes precedence over .claude even if .claude is closer
    for marker in marker_files:
        current = start
        while True:
            marker_path = current / marker
            if marker_path.exists():
                return current

            # Move to parent directory
            parent = current.parent

            # If we've reached the filesystem root, stop this marker search
            if parent == current:
                break

            current = parent

    # If we get here, no markers were found
    raise FileNotFoundError(
        f"Could not find project root. Searched upward from {start_path} "
        f"looking for: {', '.join(marker_files)}. "
        f"Ensure you're running from within a git repository or have .claude/PROJECT.md"
    )


def get_project_root(use_cache: bool = True) -> Path:
    """Get cached project root (or detect and cache it).

    This function caches the project root to avoid repeated filesystem searches.
    Safe to call multiple times - only searches once per process.

    Args:
        use_cache: If True, use cached value (default). If False, force re-detection.
                  Set to False in tests that change working directory.

    Returns:
        Path to project root

    Raises:
        FileNotFoundError: If no project root found

    Examples:
        >>> root = get_project_root()
        >>> session_dir = root / "docs" / "sessions"

        # In tests that change cwd
        >>> root = get_project_root(use_cache=False)

    Thread Safety:
        Not thread-safe (uses module-level cache). If needed for multi-threading,
        wrap with threading.Lock.
    """
    global _PROJECT_ROOT_CACHE

    if not use_cache or _PROJECT_ROOT_CACHE is None:
        _PROJECT_ROOT_CACHE = find_project_root()

    return _PROJECT_ROOT_CACHE


def is_worktree() -> bool:
    """Check if current directory is a git worktree (lazy import wrapper).

    This function wraps git_operations.is_worktree() with lazy import to avoid
    circular dependencies. It caches the function reference for performance.

    Returns:
        True if current directory is a worktree, False otherwise

    Note:
        This is a module-level function that can be mocked in tests by patching
        'path_utils.is_worktree'.
    """
    global _is_worktree_func

    # Lazy import on first use
    if _is_worktree_func is None:
        try:
            from git_operations import is_worktree as git_is_worktree
            _is_worktree_func = git_is_worktree
        except (ImportError, Exception):
            # Fallback: If import fails, create a function that always returns False
            _is_worktree_func = lambda: False

    return _is_worktree_func()


def get_main_repo_activity_log_dir() -> Optional[Path]:
    """Get the activity log directory of the main (parent) repository.

    When running inside a git worktree, session activity logs may be written
    to the main repo's ``.claude/logs/activity/`` directory instead of the
    worktree's own directory.  This function resolves that parent path so
    callers can merge logs from both locations.

    Returns:
        Path to ``<parent_repo>/.claude/logs/activity/`` if currently inside
        a worktree and the directory exists, otherwise ``None``.
    """
    if not is_worktree():
        return None

    try:
        from git_operations import get_worktree_parent
        parent = get_worktree_parent()
    except (ImportError, Exception):
        return None

    if parent is None:
        return None

    activity_dir = parent / ".claude" / "logs" / "activity"
    if activity_dir.is_dir():
        return activity_dir

    return None


def get_session_dir(create: bool = True, use_cache: bool = True) -> Path:
    """Get session directory path (PROJECT_ROOT/docs/sessions).

    Args:
        create: If True, create directory if it doesn't exist (default: True)
        use_cache: If True, use cached project root (default). Set False in tests.

    Returns:
        Path to session directory

    Raises:
        FileNotFoundError: If project root not found
        OSError: If directory creation fails

    Examples:
        >>> session_dir = get_session_dir()
        >>> session_file = session_dir / "20251117-session.md"

        # In tests that change cwd
        >>> session_dir = get_session_dir(use_cache=False)

    Security:
        - Creates with restrictive permissions (0o700 = rwx------)
        - No path traversal risk (uses get_project_root())
    """
    project_root = get_project_root(use_cache=use_cache)
    session_dir = project_root / "docs" / "sessions"

    if create and not session_dir.exists():
        session_dir.mkdir(parents=True, exist_ok=True)
        # Set restrictive permissions (owner only)
        session_dir.chmod(0o700)  # rwx------

    return session_dir


def get_batch_state_file() -> Path:
    """Get batch state file path with worktree isolation support.

    Behavior:
    - Worktrees: Returns CWD/.claude/batch_state.json (isolated per worktree)
    - Main repo: Returns PROJECT_ROOT/.claude/batch_state.json (backward compatible)

    This enables concurrent batch processing in different worktrees without conflicts.
    Each worktree maintains its own batch state, isolated from the main repo and
    other worktrees.

    Detection Fallback:
    - If worktree detection fails, falls back to main repo behavior
    - If is_worktree() unavailable, falls back to main repo behavior
    - Graceful degradation ensures existing workflows continue working

    Note: Does NOT create the file (only returns path).
    Directory (.claude/) is created if it doesn't exist.

    Returns:
        Path to batch state file (isolated for worktrees, shared for main repo)

    Raises:
        FileNotFoundError: If project root not found (main repo only)
        OSError: If directory creation fails

    Examples:
        >>> # In main repo
        >>> state_file = get_batch_state_file()
        >>> # Returns: PROJECT_ROOT/.claude/batch_state.json

        >>> # In worktree
        >>> state_file = get_batch_state_file()
        >>> # Returns: WORKTREE_DIR/.claude/batch_state.json

        >>> from batch_state_manager import save_batch_state
        >>> save_batch_state(state_file, state)

    Security:
        - Creates parent directory with safe permissions (0o755)
        - No path traversal risk (uses get_project_root() or Path.cwd())
        - Worktree detection is fail-safe (falls back to main repo)

    Issue: GitHub #226 (Per-worktree batch state isolation)
    """
    # Check if we're in a worktree using module-level function
    # (which handles lazy import and can be mocked in tests)
    try:
        in_worktree = is_worktree()
    except Exception:
        # Fallback: If detection fails, treat as main repo
        in_worktree = False

    # Determine base directory based on worktree status
    if in_worktree:
        # Worktree: Use current working directory for isolation
        base_dir = Path.cwd()
    else:
        # Main repo: Use project root (backward compatible)
        base_dir = get_project_root()

    claude_dir = base_dir / ".claude"

    # Create .claude/ directory if missing
    claude_dir.mkdir(parents=True, exist_ok=True, mode=0o755)

    return claude_dir / "batch_state.json"


def get_research_dir(create: bool = True, use_cache: bool = True) -> Path:
    """Get research directory path (PROJECT_ROOT/docs/research).

    Args:
        create: If True, create directory if it doesn't exist (default: True)
        use_cache: If True, use cached project root (default). Set False in tests.

    Returns:
        Path to research directory

    Raises:
        FileNotFoundError: If project root not found
        OSError: If directory creation fails

    Examples:
        >>> research_dir = get_research_dir()
        >>> research_file = research_dir / "JWT_AUTHENTICATION.md"

        # In tests that change cwd
        >>> research_dir = get_research_dir(use_cache=False)

    Security:
        - Creates with standard permissions (0o755 = rwxr-xr-x)
        - No path traversal risk (uses get_project_root())
    """
    project_root = get_project_root(use_cache=use_cache)
    research_dir = project_root / "docs" / "research"

    if create and not research_dir.exists():
        research_dir.mkdir(parents=True, exist_ok=True)
        # Set standard permissions (owner read/write/execute, group/others read/execute)
        research_dir.chmod(0o755)  # rwxr-xr-x

    return research_dir


def reset_project_root_cache() -> None:
    """Reset cached project root and worktree function (for testing only).

    This function resets both the project root cache and the is_worktree function
    cache to ensure tests start with a clean state.

    Warning: Only use this in test teardown. In production, the cache should
    persist for the lifetime of the process.

    Examples:
        >>> # In test teardown
        >>> reset_project_root_cache()
    """
    global _PROJECT_ROOT_CACHE, _is_worktree_func
    _PROJECT_ROOT_CACHE = None
    _is_worktree_func = None


def reset_worktree_cache() -> None:
    """Reset cached is_worktree function (for testing only).

    Warning: Only use this in test teardown. In production, the cache should
    persist for the lifetime of the process.

    Examples:
        >>> # In test teardown
        >>> reset_worktree_cache()
    """
    global _is_worktree_func
    _is_worktree_func = None


def get_policy_file(use_cache: bool = True) -> Path:
    """Get policy file path via cascading lookup with fallback.

    Cascading lookup order:
    1. .claude/config/auto_approve_policy.json (project-local)
    2. plugins/autonomous-dev/config/auto_approve_policy.json (plugin default)
    3. Return path to minimal fallback (may not exist)

    Security validations:
    - Rejects symlinks (CWE-59)
    - Prevents path traversal (CWE-22)
    - Validates JSON format
    - Handles permission errors gracefully

    Args:
        use_cache: If True, use cached value (default). If False, force re-detection.
                  Set to False in tests that change working directory.

    Returns:
        Path to policy file (validated and readable)

    Examples:
        >>> policy_file = get_policy_file()
        >>> validator = ToolValidator(policy_file=policy_file)

        # In tests that change cwd
        >>> policy_file = get_policy_file(use_cache=False)

    Thread Safety:
        Not thread-safe (uses module-level cache). If needed for multi-threading,
        wrap with threading.Lock.

    Note:
        This function prioritizes project-local policy over plugin default.
        This enables per-project customization while maintaining a sensible default.
    """
    global _POLICY_FILE_CACHE

    if not use_cache or _POLICY_FILE_CACHE is None:
        _POLICY_FILE_CACHE = _find_policy_file()

    return _POLICY_FILE_CACHE


def _find_policy_file() -> Path:
    """Find policy file via cascading lookup.

    Internal implementation for get_policy_file().

    Returns:
        Path to validated policy file
    """
    try:
        project_root = get_project_root()
    except FileNotFoundError:
        # No project root found - return plugin default path
        # (may not exist, but that's okay - caller handles missing file)
        plugin_path = Path(__file__).parent.parent / "config" / "auto_approve_policy.json"
        return plugin_path

    # Define cascading lookup locations
    home = Path.home()
    locations = [
        project_root / ".claude" / "config" / "auto_approve_policy.json",  # Project-local
        project_root / "plugins" / "autonomous-dev" / "config" / "auto_approve_policy.json",  # Plugin in project
        home / ".claude" / "config" / "auto_approve_policy.json",  # Global user config
        home / ".claude" / "plugins" / "autonomous-dev" / "config" / "auto_approve_policy.json",  # Global plugin
    ]

    # Try each location in priority order
    for policy_path in locations:
        if _is_valid_policy_file(policy_path):
            return policy_path

    # No valid policy found - return minimal fallback path
    # Return first location that doesn't exist (not symlink or invalid)
    # This ensures we never return a path we rejected for security reasons
    for policy_path in locations:
        if not policy_path.exists():
            return policy_path

    # All locations exist but all rejected (symlinks, invalid JSON, etc.)
    # Return project-local as last resort (caller will handle the issue)
    return locations[0]


def _is_valid_policy_file(policy_path: Path) -> bool:
    """Validate policy file for security and format.

    Checks:
    - File exists
    - Is not a symlink (CWE-59)
    - Is a regular file (not directory)
    - Is readable
    - Contains valid JSON

    Args:
        policy_path: Path to validate

    Returns:
        True if valid, False otherwise
    """
    # Check symlink FIRST (before exists, which follows symlinks)
    # Reject symlinks (CWE-59: Improper Link Resolution Before File Access)
    if policy_path.is_symlink():
        return False

    # Check existence (now we know it's not a symlink)
    if not policy_path.exists():
        return False

    # Must be a regular file (not directory)
    if not policy_path.is_file():
        return False

    # Check readability and validate JSON
    try:
        with open(policy_path, 'r') as f:
            json.load(f)
        return True
    except (PermissionError, json.JSONDecodeError, OSError):
        # Permission denied, invalid JSON, or other IO error
        return False


def reset_policy_cache() -> None:
    """Reset cached policy file path (for testing only).

    Warning: Only use this in test teardown. In production, the cache should
    persist for the lifetime of the process.

    Examples:
        >>> # In test teardown
        >>> reset_policy_cache()
    """
    global _POLICY_FILE_CACHE
    _POLICY_FILE_CACHE = None
