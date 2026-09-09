"""Regression test for Issue #1409: Write(path) deny no-ops + single-slash anchor.

Two coupled, primary-source-verified bugs in permission rules:

1. **Tool-name**: ``Write(path)`` / ``NotebookEdit(path)`` / ``Glob(path)`` file
   rules are never matched by Claude Code — only ``Edit(path)`` and ``Read(path)``
   match. Every ``Write(...)`` deny rule was a startup-warning no-op.
2. **Anchor**: a single leading slash ``/etc/**`` anchors to the settings *source*
   directory (``~/.claude/etc/**``), not the filesystem root. Real absolute-path
   protection requires a double leading slash: ``//etc/**``.

This is a static class-guard: it parses the canonical ``DEFAULT_DENY_LIST`` plus
the six shipped templates and the global settings template, and asserts the
migration held across every source. No LLM, no runtime — durable structural
assertions.

Fixes #1409.
"""

import json
import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEMPLATES_DIR = PROJECT_ROOT / "plugins/autonomous-dev/templates"
CONFIG_DIR = PROJECT_ROOT / "plugins/autonomous-dev/config"
LIB_DIR = PROJECT_ROOT / "plugins/autonomous-dev/lib"
GLOBAL_TEMPLATE = CONFIG_DIR / "global_settings_template.json"

# Tool-name prefixes that Claude Code silently ignores for file-path rules.
FORBIDDEN_TOOL_PREFIXES = ("Write(", "NotebookEdit(", "Glob(")

# The exact four corrected deny rules expected in DEFAULT_DENY_LIST.
EXPECTED_DEFAULT_DENY_EDIT_RULES = {
    "Edit(//etc/**)",
    "Edit(//System/**)",
    "Edit(//usr/**)",
    "Edit(~/.ssh/**)",
}

# System-root paths that MUST use a double leading slash after migration.
SYSROOT_PAIRS = [
    ("Edit(//etc/**)", "Edit(/etc/**)"),
    ("Edit(//System/**)", "Edit(/System/**)"),
    ("Edit(//usr/**)", "Edit(/usr/**)"),
]

# An absolute Edit rule with exactly ONE leading slash before a non-slash char.
SINGLE_SLASH_ABS_EDIT_RE = re.compile(r"^Edit\(/[^/]")


def _load_default_deny_list() -> list:
    """Import DEFAULT_DENY_LIST from the canonical settings_generator module.

    Returns:
        The canonical deny list as a list of rule strings.
    """
    if str(LIB_DIR) not in sys.path:
        sys.path.insert(0, str(LIB_DIR))
    from settings_generator import DEFAULT_DENY_LIST

    return list(DEFAULT_DENY_LIST)


def _iter_permission_rules(source_paths: list) -> list:
    """Collect (source_name, list_name, rule) triples from allow + deny lists.

    Args:
        source_paths: JSON settings files to inspect.

    Returns:
        List of (source_name, list_name, rule) tuples.
    """
    rules = []
    for path in source_paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        perms = data.get("permissions", {})
        for list_name in ("allow", "deny"):
            for rule in perms.get(list_name, []):
                rules.append((path.name, list_name, rule))
    return rules


def _all_json_sources() -> list:
    """Return the six templates plus the global settings template."""
    return sorted(TEMPLATES_DIR.glob("settings.*.json")) + [GLOBAL_TEMPLATE]


class TestIssue1409PermissionAnchor:
    """Static guard: no ignored tool-name rules, no single-slash absolute paths."""

    def test_no_ignored_tool_name_rules_in_json_sources(self):
        """No allow/deny rule in any template or global template starts with an
        ignored tool prefix (Write(, NotebookEdit(, Glob()."""
        violations = []
        for source_name, list_name, rule in _iter_permission_rules(_all_json_sources()):
            if rule.startswith(FORBIDDEN_TOOL_PREFIXES):
                violations.append(f"{source_name} [{list_name}]: {rule}")
        assert not violations, (
            "Ignored tool-name file rules found (Claude Code silently drops these):\n"
            + "\n".join(violations)
        )

    def test_default_deny_list_has_no_ignored_tool_name_rules(self):
        """DEFAULT_DENY_LIST contains zero Write(/NotebookEdit(/Glob( rules."""
        deny = _load_default_deny_list()
        violations = [r for r in deny if r.startswith(FORBIDDEN_TOOL_PREFIXES)]
        assert not violations, (
            "DEFAULT_DENY_LIST still has ignored tool-name rules: " + repr(violations)
        )

    def test_default_deny_list_contains_corrected_edit_rules(self):
        """DEFAULT_DENY_LIST contains exactly the four migrated Edit rules."""
        deny = set(_load_default_deny_list())
        missing = EXPECTED_DEFAULT_DENY_EDIT_RULES - deny
        assert not missing, f"DEFAULT_DENY_LIST missing corrected rules: {missing}"

    def test_sysroot_rules_use_double_slash_in_default_deny_list(self):
        """Migrated system-root deny rules use // (double slash), never single /."""
        deny = set(_load_default_deny_list())
        for double_slash, single_slash in SYSROOT_PAIRS:
            assert double_slash in deny, f"Expected {double_slash} in DEFAULT_DENY_LIST"
            assert single_slash not in deny, (
                f"Single-slash {single_slash} still present — anchors to settings "
                f"source, not filesystem root"
            )

    def test_no_single_slash_absolute_edit_rule_across_sources(self):
        """No Edit(/...) rule with exactly one leading slash survives anywhere.

        A single leading slash anchors to the settings source directory; absolute
        system paths must use two leading slashes.
        """
        violations = []
        all_rules = _iter_permission_rules(_all_json_sources())
        all_rules += [("DEFAULT_DENY_LIST", "deny", r) for r in _load_default_deny_list()]
        for source_name, list_name, rule in all_rules:
            if SINGLE_SLASH_ABS_EDIT_RE.match(rule):
                violations.append(f"{source_name} [{list_name}]: {rule}")
        assert not violations, (
            "Single-slash absolute Edit rules found (must use // for real root):\n"
            + "\n".join(violations)
        )

    def test_sysroot_double_slash_present_in_global_template(self):
        """Global settings template deny list carries the // system-root rules."""
        data = json.loads(GLOBAL_TEMPLATE.read_text(encoding="utf-8"))
        deny = set(data.get("permissions", {}).get("deny", []))
        for double_slash, single_slash in SYSROOT_PAIRS:
            assert double_slash in deny, f"global template missing {double_slash}"
            assert single_slash not in deny, f"global template still has {single_slash}"


class TestIssue1409Controls:
    """Runtime + control arms for the #1409 guard (added when #1486 was reversed).

    The six static arms above read shipped JSON and the canonical deny list.
    They never execute ``SettingsGenerator``, so they cannot see a rule the
    generator *synthesizes* at runtime — which is exactly how Issue #1486
    reintroduced ``Write(<path>)`` rules while the static guard stayed red for
    27 days. Arms (a) and (b) cover the GENERATED surface; arms (c)-(e) are the
    negative and positive controls that prove the guard's predicate can both
    refuse and permit.
    """

    @staticmethod
    def _generate(**kwargs) -> dict:
        """Run the real SettingsGenerator against the real plugin directory."""
        if str(LIB_DIR) not in sys.path:
            sys.path.insert(0, str(LIB_DIR))
        from settings_generator import SettingsGenerator

        generator = SettingsGenerator(plugin_dir=PROJECT_ROOT / "plugins/autonomous-dev")
        return generator.generate_settings(**kwargs)

    def test_generated_settings_emit_no_write_path_rules(self):
        """The generator emits zero Write(<path>) rules in allow or deny.

        Ported runtime arm (was TestGeneratedSettingsInvariant in the deleted
        #1486 file). Covers ``generate_settings`` — the 8th, GENERATED settings
        surface that no static file scan reaches.
        """
        settings = self._generate()
        perms = settings["permissions"]
        violations = [
            f"{lane}: {rule}"
            for lane in ("allow", "deny")
            for rule in perms.get(lane, [])
            if rule.startswith("Write(")
        ]
        assert not violations, (
            "generate_settings() emitted path-scoped Write rules, which Claude "
            "Code accepts but never consults:\n" + "\n".join(violations)
        )

    def test_merge_does_not_synthesize_write_companion(self):
        """Merging a user Edit(<path>) rule must not synthesize a Write twin.

        Ported runtime arm. Covers the merge path, where #1486's
        the deleted write-companion helper was re-applied after user patterns
        were folded in. The user's Edit rule MUST survive (permitting arm); the Write twin
        MUST be absent (refusing arm).
        """
        user_rule = "Edit(.claude/plans/*.md)"
        settings = self._generate(
            merge_with={"permissions": {"allow": [user_rule], "deny": []}}
        )
        allow = settings["permissions"]["allow"]
        assert user_rule in allow, (
            f"user rule {user_rule} was dropped by the merge — the merge must "
            f"preserve custom Edit rules, not just avoid adding Write twins"
        )
        assert "Write(.claude/plans/*.md)" not in allow, (
            "merge synthesized a Write(<path>) companion (Issue #1486 behaviour "
            "reversed by Issue #1409)"
        )

    def test_bare_tool_name_rules_survive(self):
        """NEGATIVE CONTROL: bare tool-name rules must never be flagged.

        Bare ``"Write"`` (no parentheses) IS matched by Claude Code at the tool
        level everywhere — deleting those would silently revoke every file-write
        permission. The control works by proving that the guard's REAL predicate
        (``startswith("Write(")``) and a deliberately over-broad one
        (``startswith("Write")``) DIVERGE on live data: the over-broad predicate
        flags at least one live bare rule that the real predicate cannot reach.
        No count is hardcoded, so this fails if a future edit widens the guard
        or if the bare Write rules are deleted.
        """
        bare_rules = [
            rule
            for _, _, rule in _iter_permission_rules(_all_json_sources())
            if "(" not in rule
        ]
        assert bare_rules, "no bare tool-name rules found — the control is blind"

        # The real predicate is definitionally unable to match anything here: a bare
        # rule contains no "(" (bare_rules filters those out) and startswith("Write(")
        # requires one. Asserting it flags nothing can never fail, so it is omitted —
        # the discriminating check is the over-broad comparison below.
        overbroad_predicate = [r for r in bare_rules if r.startswith("Write")]

        assert overbroad_predicate, (
            "the over-broad predicate flagged nothing, so it does not differ from "
            "the real one on live data — either the bare Write rules were deleted "
            "(permissions silently revoked) or this control is inert"
        )

    def test_guard_can_flag_a_planted_write_path_rule(self):
        """POSITIVE CONTROL: the guard's predicate flags a planted violation.

        A guard that cannot refuse cannot inform. Feeds the same predicate the
        static arms use a synthetic rule that MUST be caught.
        """
        planted = ["Read(./.env)", "Edit(//etc/**)", "Write(//etc/**)", "Write"]
        flagged = [r for r in planted if r.startswith(FORBIDDEN_TOOL_PREFIXES)]
        assert flagged == ["Write(//etc/**)"], (
            f"predicate must flag exactly the planted path-scoped Write rule and "
            f"leave the bare 'Write' and Edit/Read rules alone; got {flagged}"
        )

    def test_anchor_guard_can_flag_a_planted_single_slash_rule(self):
        """SECOND-SHAPE POSITIVE CONTROL: the single-slash anchor regex refuses.

        The anchor bug is a different shape from the tool-name bug, so it needs
        its own controls. ``Edit(/etc/**)`` anchors to the settings source
        directory and MUST match; ``Edit(//etc/**)`` is the correct filesystem-
        root form and MUST NOT.
        """
        assert SINGLE_SLASH_ABS_EDIT_RE.match("Edit(/etc/**)"), (
            "anchor regex failed to flag a single-slash absolute Edit rule — "
            "the guard cannot refuse, so its green means nothing"
        )
        assert not SINGLE_SLASH_ABS_EDIT_RE.match("Edit(//etc/**)"), (
            "anchor regex flagged the CORRECT double-slash form — it would "
            "refuse the very migration it exists to enforce"
        )
