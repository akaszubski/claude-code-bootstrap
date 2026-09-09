#!/usr/bin/env python3
"""Regression tests for Issue #1726: activity-log dir resolved against cwd.

Problem: ``_find_log_dir()`` in ``session_activity_logger.py`` (and its twin in
``unified_session_tracker.py``, and the inline ``Path(os.getcwd())`` resolution
in ``unified_pre_tool.py``) walked up from ``Path.cwd()`` to the FIRST
``.claude/`` directory, with an unconditional fallback to
``cwd / ".claude" / "logs" / "activity"``. Neither ``CLAUDE_PROJECT_DIR`` nor
the repo root was consulted.

Consequence: once a stray ``.claude/`` exists below the repo root (e.g.
``plugins/autonomous-dev/commands/.claude/``), every hook invoked from a deeper
cwd writes there forever — the defect is self-perpetuating, and the stray tree
lives inside shipped plugin source.

Fix: all three producers route through ``path_utils.resolve_activity_log_dir()``,
which resolves worktree-parent (Issue #755) -> ``CLAUDE_PROJECT_DIR`` ->
``find_project_root()`` -> loud failure. It never derives a path from cwd.

Both arms are exercised for each producer: the stray path must LOSE (refuse arm)
and the legitimate root path must WIN (permit arm).
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# tests/regression/test_x.py -> parents[0]=regression, parents[1]=tests, parents[2]=repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks"
LIB_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib"

for _p in (str(HOOKS_DIR), str(LIB_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import session_activity_logger as sal  # noqa: E402
import unified_session_tracker as ust  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every arm controls CLAUDE_PROJECT_DIR explicitly."""
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)


def _make_repo(tmp_path: Path) -> Path:
    """Build a minimal project root: .git marker + legitimate .claude tree."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".claude" / "logs" / "activity").mkdir(parents=True)
    return repo


def _expected(repo: Path) -> Path:
    return repo / ".claude" / "logs" / "activity"


class TestResolverArms:
    """Filesystem arms for session_activity_logger._find_log_dir()."""

    def test_cwd_repo_root_resolves_to_root_activity_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PERMIT arm: cwd == repo root -> <root>/.claude/logs/activity."""
        repo = _make_repo(tmp_path)
        monkeypatch.chdir(repo)
        assert sal._find_log_dir().resolve() == _expected(repo).resolve()

    def test_nested_cwd_without_stray_still_resolves_to_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CONTROL arm: nested cwd, no stray .claude -> root still wins.

        This arm passes both before and after the fix. It is the negative
        control that proves the refuse arm below is caused by the stray
        directory and not by nesting alone.
        """
        repo = _make_repo(tmp_path)
        nested = repo / "plugins" / "autonomous-dev" / "commands"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        assert sal._find_log_dir().resolve() == _expected(repo).resolve()

    def test_preexisting_stray_claude_between_cwd_and_root_loses(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """REFUSE arm (fails before the fix): a stray .claude must not win.

        Self-perpetuation arm: the stray sits between cwd and the root, which
        is exactly what a cwd walk-up finds first.
        """
        repo = _make_repo(tmp_path)
        nested = repo / "plugins" / "autonomous-dev" / "commands"
        stray = nested / ".claude" / "logs" / "activity"
        stray.mkdir(parents=True)
        monkeypatch.chdir(nested)

        resolved = sal._find_log_dir().resolve()
        assert resolved == _expected(repo).resolve()
        assert resolved != stray.resolve(), "stray .claude won the resolution"

    def test_stray_at_intermediate_level_also_loses(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """REFUSE arm, DIFFERENT shape: stray one level above cwd, not at cwd.

        Aimed at the class (any stray marker below the root), not at the
        ``commands/`` instance that prompted the issue.
        """
        repo = _make_repo(tmp_path)
        mid = repo / "plugins" / "autonomous-dev"
        (mid / ".claude" / "logs" / "activity").mkdir(parents=True)
        deep = mid / "commands" / "sub" / "deeper"
        deep.mkdir(parents=True)
        monkeypatch.chdir(deep)

        assert sal._find_log_dir().resolve() == _expected(repo).resolve()

    def test_claude_project_dir_wins_over_walk_up(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLAUDE_PROJECT_DIR, when set to a real directory, takes precedence."""
        repo = _make_repo(tmp_path)
        other = tmp_path / "explicit_root"
        other.mkdir()
        nested = repo / "plugins" / "autonomous-dev" / "commands"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(other))

        assert sal._find_log_dir().resolve() == (
            other / ".claude" / "logs" / "activity"
        ).resolve()

    def test_claude_project_dir_pointing_nowhere_is_ignored(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NEGATIVE control for the env arm: a bogus value must not win."""
        repo = _make_repo(tmp_path)
        monkeypatch.chdir(repo)
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path / "does_not_exist"))

        assert sal._find_log_dir().resolve() == _expected(repo).resolve()

    def test_unresolvable_root_raises_instead_of_writing_to_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LOUD FAILURE arm: no project root -> raise, never a cwd fallback.

        The unresolvable condition is injected at the collaborator boundary
        because this machine has stray ``.claude`` markers above every temp
        directory (``/private/tmp/.claude`` and
        ``/private/var/folders/**/.claude`` — themselves produced by this very
        defect), so no real filesystem location here is marker-free.
        """
        import path_utils

        from path_utils import LogDirResolutionError

        def _boom(*_args, **_kwargs):
            raise FileNotFoundError("no markers")

        monkeypatch.setattr(path_utils, "find_project_root", _boom)
        monkeypatch.chdir(tmp_path)

        with pytest.raises(LogDirResolutionError) as exc:
            sal._find_log_dir()
        assert "cwd" not in str(exc.value).lower() or "never" in str(exc.value).lower()

    def test_real_repo_nested_commands_cwd_resolves_to_repo_root(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In-situ arm against the real repo (read-only, resolves no writes).

        ``plugins/autonomous-dev/commands/.claude/`` exists in this checkout
        (Issue #1726 receipts). Resolution from that cwd must still land at the
        repo root. This arm fails before the fix on a checkout that carries the
        stray, and is a no-op assertion on a clean checkout.
        """
        nested = PROJECT_ROOT / "plugins" / "autonomous-dev" / "commands"
        monkeypatch.chdir(nested)
        assert sal._find_log_dir().resolve() == (
            PROJECT_ROOT / ".claude" / "logs" / "activity"
        ).resolve()


class TestWorktreeParentPreserved:
    """Issue #755 guard, exercised against a REAL git worktree."""

    def test_worktree_cwd_resolves_to_parent_repo_log_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()

        def git(*args: str, cwd: Path = repo) -> None:
            subprocess.run(
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
                cwd=str(cwd),
                check=True,
                capture_output=True,
            )

        git("init", "-q", "-b", "main")
        (repo / "README.md").write_text("x\n")
        git("add", "README.md")
        git("commit", "-qm", "init")
        (repo / ".claude" / "logs" / "activity").mkdir(parents=True)

        worktree = repo / ".worktrees" / "batch-1726"
        git("worktree", "add", "-q", "-b", "wt", str(worktree))
        (worktree / ".claude" / "logs" / "activity").mkdir(parents=True)

        monkeypatch.chdir(worktree)
        resolved = sal._find_log_dir().resolve()

        assert resolved == (repo / ".claude" / "logs" / "activity").resolve()
        assert resolved != (worktree / ".claude" / "logs" / "activity").resolve()


class TestOtherProducersOfTheSameSplit:
    """The stray tree has three producers, not one — all must resolve to root.

    Measured on ``plugins/autonomous-dev/commands/.claude/logs/activity/
    2026-09-05.jsonl``: 12 PreToolUse records (unified_pre_tool), 8 PostToolUse
    + 1 Stop + 1 UserPromptSubmit (session_activity_logger), 3 Heartbeat + 2
    SubagentStop (unified_session_tracker).
    """

    def test_unified_session_tracker_resolves_to_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = _make_repo(tmp_path)
        nested = repo / "plugins" / "autonomous-dev" / "commands"
        (nested / ".claude" / "logs" / "activity").mkdir(parents=True)
        monkeypatch.chdir(nested)

        assert ust._find_log_dir().resolve() == _expected(repo).resolve()

    def test_unified_pre_tool_activity_log_lands_at_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """unified_pre_tool._log_pretool_activity must not write under cwd."""
        upt = importlib.import_module("unified_pre_tool")
        repo = _make_repo(tmp_path)
        nested = repo / "plugins" / "autonomous-dev" / "commands"
        stray = nested / ".claude" / "logs" / "activity"
        stray.mkdir(parents=True)
        monkeypatch.chdir(nested)

        upt._log_pretool_activity("Bash", {"command": "echo 1726"}, "allow", "test")

        root_files = list(_expected(repo).glob("*.jsonl"))
        assert root_files, "no activity record written at the repo root"
        assert "1726" in root_files[0].read_text()
        assert not list(stray.glob("*.jsonl")), "record written into the stray tree"

    def test_unified_pre_tool_deviation_log_lands_at_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """unified_pre_tool._log_deviation must not write under cwd."""
        upt = importlib.import_module("unified_pre_tool")
        repo = _make_repo(tmp_path)
        nested = repo / "plugins" / "autonomous-dev" / "commands"
        (nested / ".claude" / "logs").mkdir(parents=True)
        monkeypatch.chdir(nested)

        upt._log_deviation("some_file.py", "Write", "test_reason_1726")

        root_dev = repo / ".claude" / "logs" / "deviations.jsonl"
        stray_dev = nested / ".claude" / "logs" / "deviations.jsonl"
        assert root_dev.exists(), "deviation not written at the repo root"
        assert "test_reason_1726" in root_dev.read_text()
        assert not stray_dev.exists(), "deviation written into the stray tree"

    def test_unified_pre_tool_loggers_are_silent_no_ops_when_unresolvable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Unresolvable root -> warn on stderr, write nothing under cwd."""
        upt = importlib.import_module("unified_pre_tool")
        import path_utils

        def _boom(*_args, **_kwargs):
            raise FileNotFoundError("no markers")

        monkeypatch.setattr(path_utils, "find_project_root", _boom)
        workdir = tmp_path / "nowhere"
        workdir.mkdir()
        monkeypatch.chdir(workdir)

        upt._log_pretool_activity("Bash", {"command": "echo x"}, "allow", "r")
        upt._log_deviation("f.py", "Write", "r")

        assert not (workdir / ".claude").exists(), "silent cwd write on failure"
        assert "1726" in capsys.readouterr().err


class TestNoCwdFallbackRemains:
    """Structural guard: the deleted cwd fallback must not come back."""

    @pytest.mark.parametrize(
        "hook_name",
        ["session_activity_logger.py", "unified_session_tracker.py"],
    )
    def test_hook_has_no_cwd_derived_log_path(self, hook_name: str) -> None:
        source = (HOOKS_DIR / hook_name).read_text()
        assert 'cwd / ".claude" / "logs"' not in source, (
            f"{hook_name} still derives a log path from cwd"
        )

    def test_unified_pre_tool_has_no_getcwd_log_path(self) -> None:
        source = (HOOKS_DIR / "unified_pre_tool.py").read_text()
        assert 'Path(os.getcwd()) / ".claude" / "logs"' not in source, (
            "unified_pre_tool.py still derives a log path from os.getcwd()"
        )
