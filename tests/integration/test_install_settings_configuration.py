#!/usr/bin/env python3
"""
Integration tests for install.sh settings configuration - TDD Red Phase

Tests the end-to-end integration of settings.json configuration during
install.sh execution, including:
1. Fresh install scenario
2. Upgrade scenario
3. Settings format validation
4. Pattern completeness verification
5. Hook configuration validation

Expected to FAIL until implementation is complete.

Security Requirements (GitHub Issue #116):
1. Settings format: Claude Code 2.0 permissions structure
2. Pattern coverage: All 45+ required allow patterns
3. Deny list: Comprehensive security blocks
4. Hook configuration: PreToolUse hook with correct path
5. Integration: install.sh → configure_global_settings.py → SettingsGenerator

Test Strategy:
- Test complete install.sh workflow (mocked)
- Test settings format matches Claude Code 2.0 spec
- Test all required patterns present
- Test deny list comprehensive
- Test hook configuration correct
- Test upgrade preserves customizations
- Test fresh install from scratch

Coverage Target: 95%+ for install integration

Author: test-master agent
Date: 2025-12-13
Issue: #116
Phase: TDD Red (tests written BEFORE implementation)
Status: RED (expected to fail - no implementation yet)
"""

import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from typing import Dict, Any, List
import tempfile
import shutil
import subprocess

# Add plugins directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "plugins"))

# Import will fail until implementation exists
try:
    from autonomous_dev.scripts import configure_global_settings
    from autonomous_dev.lib.settings_generator import SettingsGenerator
except ImportError:
    # Mock for test discovery
    class MockModule:
        @staticmethod
        def create_fresh_settings(template_path, global_path):
            raise NotImplementedError("Implementation pending - TDD Red Phase")

        @staticmethod
        def upgrade_existing_settings(global_path, template_path):
            raise NotImplementedError("Implementation pending - TDD Red Phase")

    configure_global_settings = MockModule()

    class MockSettingsGenerator:
        pass

    SettingsGenerator = MockSettingsGenerator


# Test Constants - Claude Code 2.0 Format
# These are the MINIMUM required patterns - actual template may have more
REQUIRED_ALLOW_PATTERNS = [
    # File operations
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",

    # Git operations
    "Bash(git:*)",

    # Python ecosystem
    "Bash(python:*)",
    "Bash(python3:*)",
    "Bash(pytest:*)",
    "Bash(pip:*)",
    "Bash(pip3:*)",

    # GitHub CLI
    "Bash(gh:*)",

    # Package managers
    "Bash(npm:*)",

    # Safe utilities
    "Bash(ls:*)",
    "Bash(cat:*)",
    "Bash(head:*)",
    "Bash(tail:*)",
    "Bash(grep:*)",
    "Bash(find:*)",
    "Bash(which:*)",
    "Bash(pwd:*)",
    "Bash(echo:*)",
    "Bash(cd:*)",
    "Bash(mkdir:*)",
    "Bash(touch:*)",
    "Bash(cp:*)",
    "Bash(mv:*)",

    # Claude Code tools
    "Task",
    "WebFetch",
    "WebSearch",
    "TodoWrite",
    "NotebookEdit"
]

# These are the MINIMUM required deny patterns - actual template may have more
REQUIRED_DENY_PATTERNS = [
    # Sensitive file reads
    "Read(./.env)",
    "Read(~/.ssh/**)",
    "Read(~/.aws/**)",

    # Sensitive file writes (Issue #1409): Edit(<path>) is the only path-scoped
    # file rule Claude Code consults — it governs Write, Edit and NotebookEdit
    # alike, so a Write(<path>) deny is accepted but never matched. The DOUBLE
    # leading slash is also required: a single slash anchors to the settings
    # source directory, not the filesystem root.
    "Edit(//etc/**)",
    "Edit(//System/**)",
    "Edit(//usr/**)",
    "Edit(~/.ssh/**)",

    # Privilege escalation
    "Bash(sudo:*)",

    # Code execution
    "Bash(eval:*)",

    # Disk operations
    "Bash(dd:*)",
    "Bash(mkfs:*)",
    "Bash(fdisk:*)",

    # System control
    "Bash(shutdown:*)",
    "Bash(reboot:*)",
    "Bash(init:*)"
]

EXPECTED_PRETOOLUSE_HOOK = {
    "matcher": "*",
    "hooks": [
        {
            "type": "command",
            "command": "MCP_AUTO_APPROVE=true python3 ~/.claude/hooks/pre_tool_use.py",
            "timeout": 5
        }
    ]
}


class TestInstallSettingsConfiguration:
    """Integration tests for install.sh settings configuration"""

    def test_settings_have_correct_format(self, tmp_path):
        """
        Test: Generated settings.json matches Claude Code 2.0 format

        Scenario:
        - Run configure_global_settings.py
        - Check output format matches Claude Code 2.0 spec
        - Verify structure: permissions.allow, permissions.deny, hooks

        Expected Result:
        - Top-level keys: permissions, hooks
        - permissions contains: allow (list), deny (list)
        - hooks contains: PreToolUse (list of hook configs)
        - All values are correct types
        """
        # ARRANGE
        template_path = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "config" / "global_settings_template.json"
        global_path = tmp_path / "settings.json"

        # Ensure template exists for test
        if not template_path.exists():
            pytest.skip("Template file not yet created")

        # ACT
        result = configure_global_settings.create_fresh_settings(template_path, global_path)

        # ASSERT - Format validation
        assert result["success"] is True
        assert global_path.exists()

        settings = json.loads(global_path.read_text())

        # Top-level structure
        assert "permissions" in settings, "Missing permissions key"
        assert "hooks" in settings, "Missing hooks key"

        # Permissions structure
        permissions = settings["permissions"]
        assert "allow" in permissions, "Missing permissions.allow"
        assert "deny" in permissions, "Missing permissions.deny"
        assert isinstance(permissions["allow"], list), "permissions.allow must be list"
        assert isinstance(permissions["deny"], list), "permissions.deny must be list"

        # Hooks structure
        hooks = settings["hooks"]
        assert "PreToolUse" in hooks, "Missing hooks.PreToolUse"
        assert isinstance(hooks["PreToolUse"], list), "hooks.PreToolUse must be list"

        # Hook configuration structure
        for hook_config in hooks["PreToolUse"]:
            assert "matcher" in hook_config, "Hook config missing matcher"
            assert "hooks" in hook_config, "Hook config missing hooks list"
            assert isinstance(hook_config["hooks"], list), "Hook config hooks must be list"

            for hook in hook_config["hooks"]:
                assert "type" in hook, "Hook missing type"
                assert "command" in hook, "Hook missing command"
                assert hook["type"] == "command", "Hook type must be 'command'"

    def test_all_required_patterns_present(self, tmp_path):
        """
        Test: All 45+ required allow patterns are present in generated settings

        Scenario:
        - Generate fresh settings
        - Verify all REQUIRED_ALLOW_PATTERNS present
        - Check for file ops, git, python, npm, utilities, etc.

        Expected Result:
        - All patterns from REQUIRED_ALLOW_PATTERNS present
        - No broken wildcard patterns (Bash(:*))
        - Patterns are specific (e.g., Bash(git:*) not Bash(*))
        """
        # ARRANGE
        template_path = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "config" / "global_settings_template.json"
        global_path = tmp_path / "settings.json"

        if not template_path.exists():
            pytest.skip("Template file not yet created")

        # ACT
        result = configure_global_settings.create_fresh_settings(template_path, global_path)

        # ASSERT
        assert result["success"] is True

        settings = json.loads(global_path.read_text())
        allow_patterns = settings["permissions"]["allow"]

        # Verify all required patterns present
        missing_patterns = []
        for pattern in REQUIRED_ALLOW_PATTERNS:
            if pattern not in allow_patterns:
                missing_patterns.append(pattern)

        assert len(missing_patterns) == 0, f"Missing required patterns: {missing_patterns}"

        # Verify NO broken wildcard patterns
        broken_patterns = ["Bash(:*)", "Bash(*)", "Bash(**)"]
        for broken in broken_patterns:
            assert broken not in allow_patterns, f"Broken pattern found: {broken}"

        # Verify minimum pattern count (should be 45+)
        assert len(allow_patterns) >= 45, f"Expected 45+ patterns, found {len(allow_patterns)}"

    def test_deny_list_comprehensive(self, tmp_path):
        """
        Test: Deny list contains all critical security blocks

        Scenario:
        - Generate fresh settings
        - Verify all REQUIRED_DENY_PATTERNS present
        - Check blocks for: rm -rf, sudo, eval, destructive ops, etc.

        Expected Result:
        - All patterns from REQUIRED_DENY_PATTERNS present
        - Covers: file destruction, privilege escalation, code execution
        - Covers: network tools, system control, sensitive files
        """
        # ARRANGE
        template_path = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "config" / "global_settings_template.json"
        global_path = tmp_path / "settings.json"

        if not template_path.exists():
            pytest.skip("Template file not yet created")

        # ACT
        result = configure_global_settings.create_fresh_settings(template_path, global_path)

        # ASSERT
        assert result["success"] is True

        settings = json.loads(global_path.read_text())
        deny_patterns = settings["permissions"]["deny"]

        # Verify all required deny patterns present
        missing_denies = []
        for pattern in REQUIRED_DENY_PATTERNS:
            if pattern not in deny_patterns:
                missing_denies.append(pattern)

        assert len(missing_denies) == 0, f"Missing required deny patterns: {missing_denies}"

        # Verify critical security blocks (must match actual template patterns)
        critical_blocks = [
            "Bash(sudo:*)",
            "Bash(rm -rf /)",  # Match actual template format
            "Bash(rm -rf ~)",  # Match actual template format
            "Bash(eval:*)",
            "Read(./.env)",
            "Read(~/.ssh/**)"
        ]

        for critical in critical_blocks:
            assert critical in deny_patterns, f"Critical security block missing: {critical}"

    def test_pretooluse_hook_configured(self, tmp_path):
        """
        Test: PreToolUse hook configured correctly with portable path

        Scenario:
        - Generate fresh settings
        - Verify PreToolUse hook present
        - Check command uses ~/.claude/hooks/pre_tool_use.py
        - Verify timeout configured

        Expected Result:
        - PreToolUse hook configured
        - Command: MCP_AUTO_APPROVE=true python3 ~/.claude/hooks/pre_tool_use.py
        - Timeout: 5 seconds
        - Matcher: * (all tools)
        """
        # ARRANGE
        template_path = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "config" / "global_settings_template.json"
        global_path = tmp_path / "settings.json"

        if not template_path.exists():
            pytest.skip("Template file not yet created")

        # ACT
        result = configure_global_settings.create_fresh_settings(template_path, global_path)

        # ASSERT
        assert result["success"] is True

        settings = json.loads(global_path.read_text())

        # Verify PreToolUse hook exists
        assert "PreToolUse" in settings["hooks"], "PreToolUse hook missing"

        pretooluse_hooks = settings["hooks"]["PreToolUse"]
        assert len(pretooluse_hooks) > 0, "No PreToolUse hooks configured"

        # Find the auto-approve hook
        auto_approve_hook = None
        for hook_config in pretooluse_hooks:
            if hook_config["matcher"] == "*":
                for hook in hook_config["hooks"]:
                    if "pre_tool_use.py" in hook["command"]:
                        auto_approve_hook = hook
                        break

        assert auto_approve_hook is not None, "Auto-approve hook not found"

        # Verify hook configuration
        assert auto_approve_hook["type"] == "command"
        assert "MCP_AUTO_APPROVE=true" in auto_approve_hook["command"]
        assert "~/.claude/hooks/pre_tool_use.py" in auto_approve_hook["command"]
        assert "timeout" in auto_approve_hook
        assert auto_approve_hook["timeout"] == 5

    def test_fresh_install_end_to_end(self, tmp_path):
        """
        Test: Complete fresh install workflow

        Scenario:
        - No existing ~/.claude/settings.json
        - Run configure_global_settings.py
        - Verify directory created, settings created, format correct

        Expected Result:
        - ~/.claude/ directory created
        - settings.json created with correct format
        - All required patterns present
        - PreToolUse hook configured
        """
        # ARRANGE
        template_path = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "config" / "global_settings_template.json"
        claude_dir = tmp_path / ".claude"
        global_path = claude_dir / "settings.json"

        # Verify starting state
        assert not claude_dir.exists()
        assert not global_path.exists()

        if not template_path.exists():
            pytest.skip("Template file not yet created")

        # ACT
        result = configure_global_settings.create_fresh_settings(template_path, global_path)

        # ASSERT - Complete validation
        assert result["success"] is True
        assert result["created"] is True

        # Verify directory created
        assert claude_dir.exists()
        assert claude_dir.is_dir()

        # Verify settings file created
        assert global_path.exists()

        # Verify content
        settings = json.loads(global_path.read_text())

        # Structure validation
        assert "permissions" in settings
        assert "allow" in settings["permissions"]
        assert "deny" in settings["permissions"]
        assert "hooks" in settings
        assert "PreToolUse" in settings["hooks"]

        # Pattern count validation
        assert len(settings["permissions"]["allow"]) >= 45
        assert len(settings["permissions"]["deny"]) >= 20

        # Critical patterns present
        assert "Bash(git:*)" in settings["permissions"]["allow"]
        assert "Bash(sudo:*)" in settings["permissions"]["deny"]

    def test_upgrade_preserves_customizations(self, tmp_path):
        """
        Test: Upgrade scenario preserves user customizations

        Scenario:
        - Existing settings.json with custom patterns
        - Run configure_global_settings.py upgrade
        - Verify custom patterns preserved
        - Verify broken patterns fixed
        - Verify new patterns added from template

        Expected Result:
        - User custom allow patterns preserved
        - User custom deny patterns preserved
        - Broken Bash(:*) patterns removed
        - New safe patterns from template added
        """
        # ARRANGE
        template_path = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "config" / "global_settings_template.json"
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(parents=True)
        global_path = claude_dir / "settings.json"

        if not template_path.exists():
            pytest.skip("Template file not yet created")

        # Create existing settings with customizations and broken patterns
        existing_settings = {
            "permissions": {
                "allow": [
                    "Bash(:*)",  # BROKEN - should be removed
                    "Bash(custom-tool:*)",  # USER CUSTOM - should be preserved
                    "Bash(git:*)",
                    "Read",
                    "Write"
                ],
                "deny": [
                    "Bash(custom-dangerous:*)"  # USER CUSTOM - should be preserved
                ]
            },
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "python3 ~/.my-hooks/custom_hook.py",
                                "timeout": 10
                            }
                        ]
                    }
                ]
            }
        }
        global_path.write_text(json.dumps(existing_settings, indent=2))

        # ACT
        result = configure_global_settings.upgrade_existing_settings(global_path, template_path)

        # ASSERT
        assert result["success"] is True

        merged_settings = json.loads(global_path.read_text())

        # Verify user customizations preserved
        assert "Bash(custom-tool:*)" in merged_settings["permissions"]["allow"], "User custom allow pattern lost"
        assert "Bash(custom-dangerous:*)" in merged_settings["permissions"]["deny"], "User custom deny pattern lost"

        # Verify broken pattern removed
        assert "Bash(:*)" not in merged_settings["permissions"]["allow"], "Broken pattern not removed"

        # Verify new safe patterns added
        assert "Bash(pytest:*)" in merged_settings["permissions"]["allow"], "New template pattern not added"
        assert "Bash(gh:*)" in merged_settings["permissions"]["allow"], "New template pattern not added"

        # Verify custom hook preserved
        custom_hook_found = False
        for hook_config in merged_settings["hooks"]["PreToolUse"]:
            for hook in hook_config["hooks"]:
                if "custom_hook.py" in hook["command"]:
                    custom_hook_found = True
                    assert hook["timeout"] == 10
        assert custom_hook_found, "User custom hook lost"

    def test_install_sh_integration(self, tmp_path):
        """
        Test: Integration with install.sh script

        Scenario:
        - Simulate install.sh calling configure_global_settings.py
        - Check exit code handling
        - Verify JSON output parsing
        - Test non-blocking behavior on errors

        Expected Result:
        - Script callable from shell
        - Outputs valid JSON to stdout
        - Exits 0 on success and errors (non-blocking)
        - install.sh can parse result
        """
        # ARRANGE
        template_path = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "config" / "global_settings_template.json"
        global_path = tmp_path / "settings.json"

        if not template_path.exists():
            pytest.skip("Template file not yet created")

        # ACT - Simulate shell invocation
        script_path = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "scripts" / "configure_global_settings.py"

        if not script_path.exists():
            pytest.skip("configure_global_settings.py not yet created")

        # Run as subprocess (like install.sh would)
        # Use --template and --home flags as script expects named arguments
        result = subprocess.run(
            [
                sys.executable, str(script_path),
                "--template", str(template_path),
                "--home", str(tmp_path)  # global_path is <tmp_path>/settings.json
            ],
            capture_output=True,
            text=True
        )

        # ASSERT
        # Exit code should be 0
        assert result.returncode == 0, f"Script exited with code {result.returncode}"

        # stdout should contain valid JSON
        try:
            output = json.loads(result.stdout)
            assert "success" in output
            assert isinstance(output["success"], bool)
        except json.JSONDecodeError as e:
            pytest.fail(f"Script output is not valid JSON: {result.stdout}\nError: {e}")

    def test_multiple_runs_idempotent(self, tmp_path):
        """
        Test: Multiple runs are idempotent (don't corrupt settings)

        Scenario:
        - Run configure_global_settings.py twice
        - Verify second run doesn't corrupt settings
        - Verify patterns don't duplicate

        Expected Result:
        - First run: creates settings
        - Second run: preserves settings, no duplicates
        - Settings remain valid JSON
        """
        # ARRANGE
        template_path = Path(__file__).parent.parent.parent / "plugins" / "autonomous-dev" / "config" / "global_settings_template.json"
        global_path = tmp_path / "settings.json"

        if not template_path.exists():
            pytest.skip("Template file not yet created")

        # ACT - Run twice
        result1 = configure_global_settings.create_fresh_settings(template_path, global_path)
        settings_after_first = json.loads(global_path.read_text())

        result2 = configure_global_settings.upgrade_existing_settings(global_path, template_path)
        settings_after_second = json.loads(global_path.read_text())

        # ASSERT
        assert result1["success"] is True
        assert result2["success"] is True

        # Verify no pattern duplication
        allow_patterns_1 = set(settings_after_first["permissions"]["allow"])
        allow_patterns_2 = set(settings_after_second["permissions"]["allow"])

        # Should have same unique patterns (no duplicates added)
        assert len(allow_patterns_1) == len(settings_after_first["permissions"]["allow"]), "First run created duplicates"
        assert len(allow_patterns_2) == len(settings_after_second["permissions"]["allow"]), "Second run created duplicates"

        # Both should be valid and similar
        assert allow_patterns_1 == allow_patterns_2 or len(allow_patterns_2) >= len(allow_patterns_1), "Second run lost patterns"


# Test helpers
def validate_claude_code_2_format(settings: Dict[str, Any]) -> List[str]:
    """
    Validate settings match Claude Code 2.0 format

    Returns: List of validation errors (empty if valid)
    """
    errors = []

    # Top-level structure
    if "permissions" not in settings:
        errors.append("Missing 'permissions' key")
    if "hooks" not in settings:
        errors.append("Missing 'hooks' key")

    # Permissions structure
    if "permissions" in settings:
        perms = settings["permissions"]
        if "allow" not in perms:
            errors.append("Missing 'permissions.allow'")
        elif not isinstance(perms["allow"], list):
            errors.append("'permissions.allow' must be a list")

        if "deny" not in perms:
            errors.append("Missing 'permissions.deny'")
        elif not isinstance(perms["deny"], list):
            errors.append("'permissions.deny' must be a list")

    # Hooks structure
    if "hooks" in settings:
        hooks = settings["hooks"]
        if "PreToolUse" not in hooks:
            errors.append("Missing 'hooks.PreToolUse'")
        elif not isinstance(hooks["PreToolUse"], list):
            errors.append("'hooks.PreToolUse' must be a list")

    return errors


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
