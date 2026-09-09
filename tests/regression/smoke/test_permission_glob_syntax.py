"""Regression test for permission deny rule glob syntax validation.

Incident 1: A deny rule like "Bash(*$(rm*)" has mismatched parentheses because
$( introduces a subshell but the glob parser treats ( as a grouping operator
needing a matching ). Claude Code skips the ENTIRE settings file when it
encounters invalid glob syntax, silently disabling all hooks and permissions.

Incident 2: A deny rule like "Bash(npm:*install*-g*)" is invalid because
Claude Code's Tool(command:pattern) syntax requires :* to be at the END of
the pattern. Content after :* causes the rule to be flagged as invalid and
skipped with: 'Invalid permission rule ... was skipped: The :* pattern must
be at the end.'

This test ensures all deny rules in settings files have valid glob syntax,
specifically balanced parentheses and correct :* placement.

Three distinct subjects (Issue #1762)
-------------------------------------
Incident 3: this module previously named ``.claude/settings.json`` "installed"
and asserted it carried a non-empty global deny list. That collapsed three
different things into aliases of one another and made the node fail on a
correctly-configured repo. The three subjects are separate and MUST NOT be
re-aliased:

1. ``project`` -- ``PROJECT_SETTINGS_PATH`` (``.claude/settings.json``).
   THIS repo's own settings. Hooks and the deny list deliberately live in the
   user-level profile; duplicating them here made every hook run twice
   (measured 2026-09-03). Its deny list is expected to be EMPTY. Whatever
   rules it does carry must still be syntactically valid, and it carries a
   NEGATIVE CONTROL asserting the canonical global rules are absent.

2. ``template`` -- ``CANONICAL_DENY_SOURCES``: the product's canonical deny
   sources shipped in the source tree (``templates/settings.default.json``,
   ``config/global_settings_template.json``) plus ``DEFAULT_DENY_LIST`` in
   ``lib/settings_generator.py``. These MUST be non-empty and valid.

3. ``installed`` -- a settings profile materialized by the
   ``installed_config_root`` fixture into an isolated ``tmp_path``
   configuration root from the EXACT canonical bytes. It is never ``$HOME``,
   never runner state, and never the source checkout read as a substitute.
   Missing or stale installed bytes FAIL; they are never skipped.
"""

import ast
import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest


def _extract_deny_rules(settings_path: Path) -> List[str]:
    """Extract all deny rules from a settings JSON file.

    Args:
        settings_path: Path to the settings JSON file

    Returns:
        List of deny rule strings
    """
    data = json.loads(settings_path.read_text())
    permissions = data.get("permissions", {})
    return permissions.get("deny", [])


def _check_balanced_parentheses(rule: str) -> bool:
    """Check if a deny rule has balanced parentheses.

    Counts raw ( and ) characters in the rule string.
    A valid glob pattern must have equal counts.

    Args:
        rule: The deny rule string (e.g. "Bash(rm:-rf*)")

    Returns:
        True if parentheses are balanced, False otherwise
    """
    return rule.count("(") == rule.count(")")


def _check_inner_pattern_balanced(rule: str) -> bool:
    """Check if the pattern inside the outer Tool(...) wrapper has balanced parens.

    For a rule like "Bash(some*pattern)", extracts "some*pattern" and checks
    that any parentheses within it are balanced.

    Args:
        rule: The deny rule string

    Returns:
        True if inner pattern has balanced parentheses, False otherwise
    """
    # Find the first ( and last ) which form the Tool(...) wrapper
    first_open = rule.find("(")
    last_close = rule.rfind(")")

    if first_open == -1 or last_close == -1 or first_open >= last_close:
        # No wrapper pattern found -- treat as valid (other tests catch format issues)
        return True

    inner = rule[first_open + 1 : last_close]
    return inner.count("(") == inner.count(")")


def _find_unbalanced_rules(rules: List[str]) -> List[Tuple[str, str]]:
    """Find all deny rules with unbalanced parentheses.

    Args:
        rules: List of deny rule strings

    Returns:
        List of (rule, reason) tuples for rules that failed validation
    """
    failures = []
    for rule in rules:
        if not _check_balanced_parentheses(rule):
            open_count = rule.count("(")
            close_count = rule.count(")")
            failures.append(
                (rule, f"unbalanced parens: {open_count} open, {close_count} close")
            )
        elif not _check_inner_pattern_balanced(rule):
            first_open = rule.find("(")
            last_close = rule.rfind(")")
            inner = rule[first_open + 1 : last_close]
            failures.append(
                (
                    rule,
                    f"inner pattern has unbalanced parens: "
                    f"{inner.count('(')} open, {inner.count(')')} close",
                )
            )
    return failures


def _check_colon_star_at_end(rule: str) -> bool:
    """Check that :* in a deny rule is only at the end of the pattern.

    Claude Code's Tool(command:pattern) syntax requires that :* appears
    only at the END of the pattern. Having content after :* (e.g.,
    "Bash(npm:*install*-g*)") causes the rule to be skipped as invalid.

    The :* must be followed only by the closing ) or end of string.
    Patterns like "Bash(npm:*)" are valid. Patterns like "Bash(npm:*foo*)"
    are invalid.

    Args:
        rule: The deny rule string

    Returns:
        True if the rule is valid (no content after :*), False otherwise
    """
    # Find all occurrences of :* in the rule
    idx = 0
    while True:
        pos = rule.find(":*", idx)
        if pos == -1:
            break
        # Check what follows :* — only ) or " or end-of-string is valid
        after_pos = pos + 2
        if after_pos < len(rule):
            next_char = rule[after_pos]
            if next_char not in (")", '"'):
                return False
        idx = after_pos
    return True


def _find_colon_star_violations(rules: List[str]) -> List[Tuple[str, str]]:
    """Find deny rules where :* is not at the end of the pattern.

    Args:
        rules: List of deny rule strings

    Returns:
        List of (rule, reason) tuples for rules that have content after :*
    """
    failures = []
    for rule in rules:
        if not _check_colon_star_at_end(rule):
            failures.append(
                (rule, "has content after ':*' — Claude Code requires :* at the end")
            )
    return failures


def _extract_deny_rules_from_python(source_path: Path) -> List[str]:
    """Extract string literals from the DEFAULT_DENY_LIST in settings_generator.py.

    Parses the Python AST to find the DEFAULT_DENY_LIST assignment and
    extracts all string constant elements.

    Args:
        source_path: Path to settings_generator.py

    Returns:
        List of deny rule strings from the Python source
    """
    source = source_path.read_text()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "DEFAULT_DENY_LIST":
                    if isinstance(node.value, ast.List):
                        return [
                            elt.value
                            for elt in node.value.elts
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                        ]
    return []


# =============================================================================
# Subject 1: project settings (THIS repo) -- deny list expected EMPTY
# =============================================================================

PROJECT_SETTINGS_PATH = ".claude/settings.json"

# =============================================================================
# Subject 2: canonical deny sources shipped by the product
# =============================================================================

CANONICAL_DENY_SOURCES = {
    "default_template": "plugins/autonomous-dev/templates/settings.default.json",
    "global_template": "plugins/autonomous-dev/config/global_settings_template.json",
}

# The canonical bytes an installed user-level profile is materialized from.
CANONICAL_GLOBAL_DENY_SOURCE = CANONICAL_DENY_SOURCES["global_template"]

GENERATOR_SOURCE_PATH = "plugins/autonomous-dev/lib/settings_generator.py"


def _validate_canonical_deny_payload(data: Dict[str, Any]) -> List[str]:
    """Validate a settings payload that is REQUIRED to carry canonical deny rules.

    Applied to canonical templates and to installed profiles -- never to
    project settings, whose deny list is legitimately empty.

    Args:
        data: Parsed settings JSON payload

    Returns:
        List of failure reasons. Empty list means the payload is valid.
    """
    permissions = data.get("permissions")
    if not isinstance(permissions, dict):
        return ["missing 'permissions' object"]

    if "deny" not in permissions:
        return ["missing 'deny' key under 'permissions'"]

    rules = permissions["deny"]
    if not isinstance(rules, list):
        return [f"'deny' is {type(rules).__name__}, expected list"]

    if len(rules) == 0:
        return ["empty deny list -- a canonical deny source must be non-empty"]

    problems: List[str] = []
    for rule, reason in _find_unbalanced_rules(rules):
        problems.append(f"{rule!r} -- {reason}")
    for rule, reason in _find_colon_star_violations(rules):
        problems.append(f"{rule!r} -- {reason}")
    return problems


def _canonical_deny_rules(project_root: Path) -> List[str]:
    """Collect every deny rule the product ships as canonical policy.

    Union of the two canonical template files and DEFAULT_DENY_LIST in the
    generator. Used as the NEGATIVE CONTROL corpus for project settings.

    Args:
        project_root: Repository root

    Returns:
        Sorted list of canonical deny rule strings
    """
    rules: set = set()
    for rel_path in CANONICAL_DENY_SOURCES.values():
        path = project_root / rel_path
        if path.exists():
            rules.update(_extract_deny_rules(path))

    generator_path = project_root / GENERATOR_SOURCE_PATH
    if generator_path.exists():
        rules.update(_extract_deny_rules_from_python(generator_path))

    return sorted(rules)


def _installed_profile_drift(installed_path: Path, canonical_path: Path) -> Optional[str]:
    """Report drift between an installed profile and its canonical source.

    Args:
        installed_path: Path to the installed settings profile
        canonical_path: Path to the canonical source bytes

    Returns:
        None when byte-for-byte identical, otherwise a reason string.
    """
    if not installed_path.exists():
        return f"missing installed profile: {installed_path}"

    installed_bytes = installed_path.read_bytes()
    canonical_bytes = canonical_path.read_bytes()
    if installed_bytes != canonical_bytes:
        return (
            f"stale installed profile: {len(installed_bytes)} bytes vs "
            f"{len(canonical_bytes)} canonical bytes -- content differs"
        )
    return None


@pytest.fixture
def installed_config_root(tmp_path: Path, project_root: Path) -> Path:
    """Materialize the EXACT canonical bytes into an isolated configuration root.

    This is the ONLY source of an "installed" settings profile in this module.
    It never reads ``$HOME``, CI runner state, or the source checkout as an
    installed substitute -- it writes canonical bytes into ``tmp_path`` so the
    proof is portable across Linux CI and macOS local runs.

    Args:
        tmp_path: pytest-provided isolated directory
        project_root: Repository root

    Returns:
        Path to the isolated config root containing ``.claude/settings.json``
    """
    canonical_path = project_root / CANONICAL_GLOBAL_DENY_SOURCE
    assert canonical_path.exists(), (
        f"Canonical global deny source missing: {CANONICAL_GLOBAL_DENY_SOURCE}"
    )

    config_root = tmp_path / "isolated-claude-config-root"
    (config_root / ".claude").mkdir(parents=True)
    (config_root / ".claude" / "settings.json").write_bytes(canonical_path.read_bytes())
    return config_root


class TestPermissionGlobSyntax:
    """Validate glob syntax in permission deny rules across settings files.

    Claude Code's glob parser requires balanced parentheses. A single
    mismatched paren causes the entire settings file to be skipped,
    silently disabling all hooks and permissions.
    """

    # On-disk files whose deny rules must be syntactically valid IF present.
    # NOTE (Issue #1762): the key for .claude/settings.json is "project", NOT
    # "installed". It is this repo's own settings file, not an installed
    # product profile. The installed subject is the tmp_path fixture below.
    SETTINGS_FILES = {
        "template": CANONICAL_DENY_SOURCES["default_template"],
        "project": PROJECT_SETTINGS_PATH,
        "global_template": CANONICAL_DENY_SOURCES["global_template"],
    }

    GENERATOR_PATH = GENERATOR_SOURCE_PATH

    def test_deny_rules_have_balanced_parentheses(self, project_root: Path) -> None:
        """All deny rules in all settings files must have balanced parentheses."""
        all_failures: List[str] = []

        for label, rel_path in self.SETTINGS_FILES.items():
            settings_path = project_root / rel_path
            if not settings_path.exists():
                continue

            rules = _extract_deny_rules(settings_path)
            failures = _find_unbalanced_rules(rules)

            for rule, reason in failures:
                all_failures.append(f"  [{label}] {rule!r} -- {reason}")

        if all_failures:
            pytest.fail(
                f"Deny rules with invalid glob syntax ({len(all_failures)}):\n"
                + "\n".join(all_failures)
                + "\n\nClaude Code skips the ENTIRE settings file on invalid glob syntax, "
                "silently disabling all hooks and permissions."
            )

    def test_settings_default_template_deny_rules(self, project_root: Path) -> None:
        """All deny rules in the default template must have balanced parentheses."""
        template_path = project_root / self.SETTINGS_FILES["template"]
        if not template_path.exists():
            pytest.skip(f"Template not found: {self.SETTINGS_FILES['template']}")

        rules = _extract_deny_rules(template_path)
        assert len(rules) > 0, "Template has no deny rules -- expected a non-empty deny list"

        failures = _find_unbalanced_rules(rules)
        if failures:
            details = "\n".join(f"  {rule!r} -- {reason}" for rule, reason in failures)
            pytest.fail(
                f"Template deny rules with unbalanced parentheses ({len(failures)}):\n"
                + details
            )

    # -------------------------------------------------------------------
    # Subject 1: project settings (.claude/settings.json)
    # -------------------------------------------------------------------

    def test_project_settings_deny_rules_have_valid_syntax(
        self, project_root: Path
    ) -> None:
        """Any deny rules THIS repo's project settings carries must be valid.

        The deny list is expected to be empty (policy lives in the user-level
        profile), so emptiness is NOT a failure. Coverage is retained so that
        if project settings ever does carry rules, their glob syntax is still
        validated.
        """
        project_path = project_root / PROJECT_SETTINGS_PATH
        assert project_path.exists(), (
            f"Project settings missing: {PROJECT_SETTINGS_PATH} -- this repo "
            "tracks it via an explicit `git add -f` despite .gitignore's "
            "`.claude/*` rule (there is no negation line for it)"
        )

        rules = _extract_deny_rules(project_path)
        failures = _find_unbalanced_rules(rules) + _find_colon_star_violations(rules)
        if failures:
            details = "\n".join(f"  {rule!r} -- {reason}" for rule, reason in failures)
            pytest.fail(
                f"Project settings deny rules with invalid glob syntax "
                f"({len(failures)}):\n" + details
            )

    def test_project_settings_must_not_duplicate_canonical_deny_rules(
        self, project_root: Path
    ) -> None:
        """NEGATIVE CONTROL: canonical global deny rules must be ABSENT here.

        Duplicating the global deny list and hooks into project settings made
        every hook run twice (measured 2026-09-03). If anyone restores that
        duplication, this test goes red.
        """
        project_path = project_root / PROJECT_SETTINGS_PATH
        assert project_path.exists(), (
            f"Project settings missing: {PROJECT_SETTINGS_PATH}"
        )

        canonical = _canonical_deny_rules(project_root)
        assert len(canonical) > 0, (
            "Canonical deny corpus is empty -- the negative control would pass "
            "vacuously. Check the canonical sources are readable."
        )

        project_rules = set(_extract_deny_rules(project_path))
        duplicated = sorted(project_rules & set(canonical))
        if duplicated:
            details = "\n".join(f"  {rule!r}" for rule in duplicated)
            pytest.fail(
                f"Project settings duplicates {len(duplicated)} canonical "
                f"global deny rule(s):\n" + details
                + f"\n\nPolicy belongs in the user-level profile only. "
                f"Duplicating it into {PROJECT_SETTINGS_PATH} makes every hook "
                "run twice (measured 2026-09-03)."
            )

    # -------------------------------------------------------------------
    # Subject 2: canonical deny sources -- positive + one-at-a-time negatives
    # -------------------------------------------------------------------

    @pytest.mark.parametrize("label", sorted(CANONICAL_DENY_SOURCES))
    def test_canonical_deny_source_is_valid(
        self, project_root: Path, label: str
    ) -> None:
        """POSITIVE ARM: each canonical deny source is non-empty and valid."""
        canonical_path = project_root / CANONICAL_DENY_SOURCES[label]
        assert canonical_path.exists(), (
            f"Canonical deny source missing: {CANONICAL_DENY_SOURCES[label]}"
        )

        data = json.loads(canonical_path.read_text())
        assert len(data["permissions"]["deny"]) > 0, (
            f"Canonical source {label} has an empty deny list"
        )

        problems = _validate_canonical_deny_payload(data)
        assert problems == [], (
            f"Canonical deny source {label} is invalid:\n"
            + "\n".join(f"  {p}" for p in problems)
        )

    def test_canonical_validator_rejects_malformed_rule(
        self, project_root: Path
    ) -> None:
        """NEGATIVE ARM 1: exactly one malformed rule added, nothing else changed."""
        canonical_path = project_root / CANONICAL_GLOBAL_DENY_SOURCE
        data = json.loads(canonical_path.read_text())
        assert _validate_canonical_deny_payload(data) == [], "baseline must be clean"

        perturbed = copy.deepcopy(data)
        perturbed["permissions"]["deny"].append("Bash(*$(rm*)")

        problems = _validate_canonical_deny_payload(perturbed)
        assert len(problems) == 1, (
            f"Expected exactly 1 problem from 1 malformed rule, got: {problems}"
        )
        assert "unbalanced parens" in problems[0], problems[0]

    def test_canonical_validator_rejects_empty_deny_list(
        self, project_root: Path
    ) -> None:
        """NEGATIVE ARM 2: deny list emptied, nothing else changed."""
        canonical_path = project_root / CANONICAL_GLOBAL_DENY_SOURCE
        data = json.loads(canonical_path.read_text())
        assert _validate_canonical_deny_payload(data) == [], "baseline must be clean"

        perturbed = copy.deepcopy(data)
        perturbed["permissions"]["deny"] = []

        problems = _validate_canonical_deny_payload(perturbed)
        assert problems == ["empty deny list -- a canonical deny source must be non-empty"]

    def test_canonical_validator_rejects_missing_deny_key(
        self, project_root: Path
    ) -> None:
        """NEGATIVE ARM 3: deny key removed, nothing else changed."""
        canonical_path = project_root / CANONICAL_GLOBAL_DENY_SOURCE
        data = json.loads(canonical_path.read_text())
        assert _validate_canonical_deny_payload(data) == [], "baseline must be clean"

        perturbed = copy.deepcopy(data)
        del perturbed["permissions"]["deny"]

        problems = _validate_canonical_deny_payload(perturbed)
        assert problems == ["missing 'deny' key under 'permissions'"]

    # -------------------------------------------------------------------
    # Subject 3: installed profile (fixture-materialized, tmp_path only)
    # -------------------------------------------------------------------

    def test_installed_profile_deny_rules_are_valid(
        self, installed_config_root: Path
    ) -> None:
        """Installed profile carries a non-empty, syntactically valid deny list.

        Reads ONLY the isolated fixture config root -- never $HOME, never
        runner state, never the source checkout as a substitute.
        """
        installed_path = installed_config_root / ".claude" / "settings.json"
        assert installed_path.exists(), (
            f"Fixture failed to materialize installed profile at {installed_path}"
        )

        data = json.loads(installed_path.read_text())
        rules = data["permissions"]["deny"]
        assert len(rules) > 0, "Installed profile has an empty deny list"

        problems = _validate_canonical_deny_payload(data)
        assert problems == [], (
            "Installed profile deny rules are invalid:\n"
            + "\n".join(f"  {p}" for p in problems)
        )

    # The byte-identical POSITIVE ARM is carried by the pre-perturbation
    # ``assert _installed_profile_drift(...) is None`` inside each negative arm
    # below. A separate standalone test asserting only that line killed no
    # mutant the negative arms do not already kill, so it was removed.

    def test_stale_installed_profile_fails(
        self, installed_config_root: Path, project_root: Path
    ) -> None:
        """NEGATIVE ARM: stale installed bytes are RED, never green, never skipped."""
        installed_path = installed_config_root / ".claude" / "settings.json"
        canonical_path = project_root / CANONICAL_GLOBAL_DENY_SOURCE
        assert _installed_profile_drift(installed_path, canonical_path) is None

        # Vary exactly one thing: drop a single deny rule from the installed copy.
        stale = json.loads(installed_path.read_text())
        stale["permissions"]["deny"].pop()
        installed_path.write_text(json.dumps(stale, indent=2))

        drift = _installed_profile_drift(installed_path, canonical_path)
        assert drift is not None and "stale" in drift, (
            f"Stale installed bytes must be detected as drift, got: {drift!r}"
        )

    def test_missing_installed_profile_fails(
        self, installed_config_root: Path, project_root: Path
    ) -> None:
        """NEGATIVE ARM: an absent installed profile is RED, not a skip."""
        installed_path = installed_config_root / ".claude" / "settings.json"
        canonical_path = project_root / CANONICAL_GLOBAL_DENY_SOURCE
        assert _installed_profile_drift(installed_path, canonical_path) is None

        # Vary exactly one thing: remove the installed file.
        installed_path.unlink()

        drift = _installed_profile_drift(installed_path, canonical_path)
        assert drift is not None and "missing" in drift, (
            f"Missing installed profile must be detected, got: {drift!r}"
        )

    # All on-disk files to validate for :* placement: the two canonical deny
    # sources plus this repo's project settings (whose deny list is expected
    # empty, but must be valid if it is ever non-empty).
    COLON_STAR_SOURCE_FILES = {
        "template": CANONICAL_DENY_SOURCES["default_template"],
        "global_template": CANONICAL_DENY_SOURCES["global_template"],
        "project": PROJECT_SETTINGS_PATH,
    }

    def test_colon_star_must_be_at_end_in_settings_files(self, project_root: Path) -> None:
        """Deny rules with :* must have it at the end of the pattern.

        Regression test for: 'Invalid permission rule "Bash(npm:*install*-g*)"
        was skipped: The :* pattern must be at the end.'

        Claude Code's Tool(command:pattern) syntax requires :* to terminate
        the pattern. Content after :* causes the rule to be silently skipped.

        Validates the two canonical deny sources plus this repo's project
        settings. The installed profile is a separate subject validated via
        the ``installed_config_root`` fixture, not here.
        """
        all_failures: List[str] = []

        for label, rel_path in self.COLON_STAR_SOURCE_FILES.items():
            settings_path = project_root / rel_path
            if not settings_path.exists():
                continue

            rules = _extract_deny_rules(settings_path)
            failures = _find_colon_star_violations(rules)

            for rule, reason in failures:
                all_failures.append(f"  [{label}] {rule!r} -- {reason}")

        if all_failures:
            pytest.fail(
                f"Deny rules with content after ':*' ({len(all_failures)}):\n"
                + "\n".join(all_failures)
                + "\n\nClaude Code requires ':*' to be at the end of the pattern. "
                "Content after ':*' causes the rule to be silently skipped."
            )

    def test_colon_star_must_be_at_end_in_generator(self, project_root: Path) -> None:
        """DEFAULT_DENY_LIST in settings_generator.py must not have content after :*.

        Regression test for the source of truth: the Python deny list that
        generates settings files. If the generator has invalid rules, every
        generated settings file will inherit them.
        """
        generator_path = project_root / self.GENERATOR_PATH
        if not generator_path.exists():
            pytest.skip(f"Generator not found: {self.GENERATOR_PATH}")

        rules = _extract_deny_rules_from_python(generator_path)
        assert len(rules) > 0, (
            "DEFAULT_DENY_LIST not found or empty in settings_generator.py"
        )

        failures = _find_colon_star_violations(rules)
        if failures:
            details = "\n".join(f"  {rule!r} -- {reason}" for rule, reason in failures)
            pytest.fail(
                f"DEFAULT_DENY_LIST rules with content after ':*' ({len(failures)}):\n"
                + details
                + "\n\nFix: ensure ':*' is at the end, e.g., 'Bash(npm:*)' not "
                "'Bash(npm:*install*-g*)'"
            )

    def test_global_settings_template_deny_rules(self, project_root: Path) -> None:
        """All deny rules in global_settings_template.json must have valid syntax.

        Validates both balanced parentheses and :* placement for the global
        settings template used for user-level Claude Code configuration.
        """
        template_path = project_root / self.SETTINGS_FILES["global_template"]
        if not template_path.exists():
            pytest.skip(
                f"Global template not found: {self.SETTINGS_FILES['global_template']}"
            )

        rules = _extract_deny_rules(template_path)
        assert len(rules) > 0, (
            "Global template has no deny rules -- expected a non-empty deny list"
        )

        # Check balanced parens
        paren_failures = _find_unbalanced_rules(rules)
        # Check :* placement
        colon_star_failures = _find_colon_star_violations(rules)

        all_failures = []
        for rule, reason in paren_failures:
            all_failures.append(f"  {rule!r} -- {reason}")
        for rule, reason in colon_star_failures:
            all_failures.append(f"  {rule!r} -- {reason}")

        if all_failures:
            pytest.fail(
                f"Global template deny rules with invalid syntax ({len(all_failures)}):\n"
                + "\n".join(all_failures)
            )
