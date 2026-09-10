#!/usr/bin/env python3
"""Regression tests for Issue #1726: refuse new .claude/ trees in plugin source.

The resolver fix stops the three hooks from *writing* stray activity logs into
``plugins/autonomous-dev/**/.claude/``. This guard closes the other half: no
tool call may CREATE such a directory again, from any write transport.

Both arms are proven for every case:

* REFUSE — writes creating ``<repo>/plugins/autonomous-dev/**/.claude/...``
* PERMIT — the legitimate repo-root ``.claude/...``, the marketplace install
  layout ``~/.claude/plugins/autonomous-dev/...`` (where ``.claude`` precedes
  the plugin directory), the shipped ``.claude-plugin/`` directory, ordinary
  writes under ``plugins/autonomous-dev/``, and look-alike layouts that are not
  a real autonomous-dev source tree.

The refuse cases are deliberately authored to SHAPES OTHER THAN the reproducer
(``plugins/autonomous-dev/commands/.claude/logs/activity/2026-09-05.jsonl``):
the guard covers the class "any ``.claude`` segment below a real
``plugins/autonomous-dev/`` source tree", not that one directory.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# tests/regression/test_x.py -> parents[2] == repo root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = PROJECT_ROOT / "plugins" / "autonomous-dev" / "hooks"
HOOK = HOOKS_DIR / "unified_pre_tool.py"

for _p in (str(HOOKS_DIR), str(PROJECT_ROOT / "plugins" / "autonomous-dev" / "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import unified_pre_tool as upt  # noqa: E402

MARKER = "Issue #1726"


@pytest.fixture()
def source_tree(tmp_path: Path) -> Path:
    """A look-alike that IS a real autonomous-dev source tree (canonical marker)."""
    root = tmp_path / "repo"
    plugin = root / "plugins" / "autonomous-dev"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "marketplace.json").write_text("{}")
    (root / ".claude").mkdir(parents=True)
    return root


class TestTargetClassification:
    """Pure predicate: which paths belong to the refused class."""

    @pytest.mark.parametrize(
        "relative",
        [
            # NOT the reproducer shape — directly under the plugin root
            "plugins/autonomous-dev/.claude/settings.json",
            # deep, under a different subdirectory than commands/
            "plugins/autonomous-dev/skills/testing-guide/.claude/notes.md",
            # the reproducer's own class, for completeness
            "plugins/autonomous-dev/commands/.claude/logs/activity/2026-09-05.jsonl",
            # a .claude nested several levels down
            "plugins/autonomous-dev/hooks/a/b/c/.claude/x",
        ],
    )
    def test_refuses_nested_claude_paths(self, source_tree: Path, relative: str) -> None:
        assert upt._targets_nested_claude_dir(str(source_tree / relative)) is True

    @pytest.mark.parametrize(
        "relative",
        [
            # the legitimate repo-root .claude tree
            ".claude/logs/activity/2026-09-05.jsonl",
            ".claude/settings.json",
            # shipped plugin content that merely LOOKS similar
            "plugins/autonomous-dev/.claude-plugin/marketplace.json",
            # ordinary plugin source writes
            "plugins/autonomous-dev/hooks/unified_pre_tool.py",
            "plugins/autonomous-dev/docs/COMMANDS.md",
            # a .claude ABOVE the plugin dir (marketplace install layout)
            ".claude/plugins/autonomous-dev/lib/path_utils.py",
        ],
    )
    def test_permits_legitimate_paths(self, source_tree: Path, relative: str) -> None:
        assert upt._targets_nested_claude_dir(str(source_tree / relative)) is False

    def test_permits_lookalike_outside_a_real_source_tree(self, tmp_path: Path) -> None:
        """NEGATIVE control: same layout, no canonical marker -> not our tree."""
        fake = tmp_path / "not_adev" / "plugins" / "autonomous-dev" / ".claude" / "x.json"
        fake.parent.mkdir(parents=True)
        assert upt._targets_nested_claude_dir(str(fake)) is False

    def test_empty_path_is_permitted(self) -> None:
        assert upt._targets_nested_claude_dir("") is False


class TestEnforcementBothArms:
    """The gate function itself: does it deny, and does it stay quiet otherwise."""

    def _run(self, monkeypatch: pytest.MonkeyPatch, tool_name: str, tool_input: dict):
        """Invoke the gate, capturing any deny instead of exiting the process."""
        captured: dict = {}

        def fake_output_decision(decision, reason, *, system_message=""):
            captured["decision"] = decision
            captured["reason"] = reason

        monkeypatch.setattr(upt, "output_decision", fake_output_decision)
        monkeypatch.setattr(upt, "_log_deviation", lambda *a, **k: None)
        monkeypatch.setattr(upt, "_log_pretool_activity", lambda *a, **k: None)
        try:
            upt._enforce_no_nested_claude_dir(tool_name, tool_input)
        except SystemExit:
            pass
        return captured

    def test_write_creating_nested_claude_is_denied(
        self, monkeypatch: pytest.MonkeyPatch, source_tree: Path
    ) -> None:
        target = source_tree / "plugins" / "autonomous-dev" / ".claude" / "logs" / "x.jsonl"
        result = self._run(monkeypatch, "Write", {"file_path": str(target)})
        assert result.get("decision") == "deny"
        assert MARKER in result.get("reason", "")

    def test_mcp_editor_transport_is_denied(
        self, monkeypatch: pytest.MonkeyPatch, source_tree: Path
    ) -> None:
        """An MCP writer carrying ``relative_path`` must not walk through."""
        bad = source_tree / "plugins" / "autonomous-dev" / "skills" / ".claude" / "y.txt"
        result = self._run(
            monkeypatch,
            "mcp__serena__create_text_file",
            {"relative_path": str(bad), "content": "x"},
        )
        assert result.get("decision") == "deny"
        assert MARKER in result.get("reason", "")

    def test_bash_is_out_of_scope_and_not_gated(
        self, monkeypatch: pytest.MonkeyPatch, source_tree: Path
    ) -> None:
        """Documented scope boundary, measured not assumed.

        ``tool_intent.write_targets`` reports the SOURCE of a deletion as a
        write target (``rm -rf plugins/autonomous-dev/commands/.claude`` ->
        ``['plugins/autonomous-dev/commands/.claude']``), so routing Bash
        through this gate would block the authorised relocation of the two
        existing stray trees. Bash is excluded on purpose; this arm locks that
        decision so a future widening is a deliberate act, not a silent one.
        """
        bad = source_tree / "plugins" / "autonomous-dev" / ".claude" / "logs"
        result = self._run(monkeypatch, "Bash", {"command": f"mkdir -p {bad}"})
        assert result == {}

    def test_notebookedit_transport_is_denied(
        self, monkeypatch: pytest.MonkeyPatch, source_tree: Path
    ) -> None:
        """A transport other than Write/Edit must not walk through the gate."""
        target = source_tree / "plugins" / "autonomous-dev" / ".claude" / "nb.ipynb"
        result = self._run(monkeypatch, "NotebookEdit", {"notebook_path": str(target)})
        assert result.get("decision") == "deny"

    def test_repo_root_claude_write_is_permitted(
        self, monkeypatch: pytest.MonkeyPatch, source_tree: Path
    ) -> None:
        """PERMIT arm: the legitimate root .claude tree is untouched."""
        target = source_tree / ".claude" / "logs" / "activity" / "2026-09-05.jsonl"
        result = self._run(monkeypatch, "Write", {"file_path": str(target)})
        assert result == {}

    def test_ordinary_plugin_source_write_is_permitted(
        self, monkeypatch: pytest.MonkeyPatch, source_tree: Path
    ) -> None:
        """PERMIT arm: a normal write under plugins/autonomous-dev/."""
        target = source_tree / "plugins" / "autonomous-dev" / "docs" / "TROUBLESHOOTING.md"
        result = self._run(monkeypatch, "Write", {"file_path": str(target)})
        assert result == {}

    def test_read_tool_is_not_gated(
        self, monkeypatch: pytest.MonkeyPatch, source_tree: Path
    ) -> None:
        """PERMIT arm: reading a stray path stays possible (they are evidence)."""
        target = source_tree / "plugins" / "autonomous-dev" / ".claude" / "logs" / "x.jsonl"
        result = self._run(monkeypatch, "Read", {"file_path": str(target)})
        assert result == {}


class TestExecutingCopy:
    """Both arms against the copy that actually runs, via its stdin contract."""

    def _invoke(self, payload: dict) -> str:
        proc = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(PROJECT_ROOT),
        )
        return proc.stdout + proc.stderr

    def test_executing_hook_refuses_nested_claude_write(self) -> None:
        target = PROJECT_ROOT / "plugins" / "autonomous-dev" / ".claude" / "probe_1726.json"
        out = self._invoke(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(target), "content": "{}"},
                "session_id": "test-1726",
            }
        )
        assert "deny" in out, f"executing hook did not deny: {out[:600]}"
        assert MARKER in out, f"denied for an unrelated reason: {out[:600]}"
        assert not target.exists(), "probe path must never be created"

    def test_executing_hook_permits_repo_root_claude_write(self) -> None:
        target = PROJECT_ROOT / ".claude" / "logs" / "probe_1726.json"
        out = self._invoke(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(target), "content": "{}"},
                "session_id": "test-1726",
            }
        )
        assert MARKER not in out, f"root .claude write hit the 1726 guard: {out[:600]}"

    def test_executing_hook_permits_ordinary_docs_write(self) -> None:
        target = PROJECT_ROOT / "plugins" / "autonomous-dev" / "docs" / "probe_1726.md"
        out = self._invoke(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": str(target), "content": "x"},
                "session_id": "test-1726",
            }
        )
        assert MARKER not in out, f"ordinary plugin write hit the 1726 guard: {out[:600]}"
