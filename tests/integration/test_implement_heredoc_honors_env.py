"""
Integration tests verifying that all migrated heredoc sites in
commands/implement.md, commands/implement-batch.md, and
commands/implement-fix.md honor the PIPELINE_STATE_FILE env var
instead of using a hardcoded literal path.

These tests inspect the source files directly (content regex checks) —
no subprocess execution required, making them fast and deterministic.

Issues: #1041 #1048
"""

import re
import sys
from pathlib import Path

import pytest

# Repo root is 3 levels up from tests/integration/test_*.py
REPO_ROOT = Path(__file__).resolve().parents[2]

IMPLEMENT_MD = REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement.md"
IMPLEMENT_BATCH_MD = (
    REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement-batch.md"
)
IMPLEMENT_FIX_MD = (
    REPO_ROOT / "plugins" / "autonomous-dev" / "commands" / "implement-fix.md"
)

# The env-var-aware form every migrated site must use.
# Matches both shell-expansion form and os.environ.get() form.
ENV_VAR_SHELL_RE = re.compile(
    r'\$\{PIPELINE_STATE_FILE:-/tmp/implement_pipeline_state\.json\}'
)
ENV_VAR_PYTHON_RE = re.compile(
    r"""os\.environ\.get\(['"]PIPELINE_STATE_FILE['"],\s*['"]/tmp/implement_pipeline_state\.json['"]\)"""
)

# Post-#1206 per-repo forms. NONE of implement.md, implement-batch.md or
# implement-fix.md carries the machine-global /tmp literal any more —
# get_legacy_sentinel_path() resolves
# <repo>/.claude/local/implement_pipeline_state.json, which is the path the hook
# reads. implement-fix.md was the LAST holdout and was migrated with the rest;
# the ENV_VAR_*_RE constants above now describe only the pre-migration shape and
# are retained as the refused form, not as an expectation of any live file.
ENV_VAR_PYTHON_PER_REPO_RE = re.compile(
    r"""_?os\.environ\.get\(['"]PIPELINE_STATE_FILE['"],\s*str\(get_legacy_sentinel_path\(\)\)\)"""
)
ENV_VAR_SHELL_PER_REPO_RE = re.compile(
    r'CLEANUP_STATE_FILE="\$\{PIPELINE_STATE_FILE:-'
)

# Literal that must NOT appear in functional (non-comment, non-exclusion) code.
BARE_LITERAL = "/tmp/implement_pipeline_state.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _functional_lines(text: str) -> list[tuple[int, str]]:
    """Return (lineno, line) pairs that are functional code, not comment-only lines.

    Lines that start with '#' (after stripping) are treated as pure comments
    and excluded. Doc-comment lines inside triple-quoted strings are NOT
    excluded by this simple heuristic, but those are the security-guard/HMAC
    lines that we verify separately.
    """
    result = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith("#"):
            continue
        result.append((lineno, raw))
    return result


def _has_env_var_form(line: str) -> bool:
    """Return True if line contains an env-var-aware reference."""
    return bool(ENV_VAR_SHELL_RE.search(line) or ENV_VAR_PYTHON_RE.search(line))


# ---------------------------------------------------------------------------
# Tests: implement.md
# ---------------------------------------------------------------------------


class TestImplementMdHereDocMigration:
    """Verify implement.md migrated heredoc sites use env-var form."""

    def test_file_exists(self) -> None:
        assert IMPLEMENT_MD.exists(), f"Expected {IMPLEMENT_MD} to exist"

    def test_heredoc_uses_pipeline_state_file_when_set(self) -> None:
        """Migrated write sites use os.environ.get('PIPELINE_STATE_FILE', ...).

        The DEFAULT moved from the machine-global ``/tmp`` literal to
        ``get_legacy_sentinel_path()`` (per-repo, Issue #1206) — measured to be
        a different file, and the one the hook actually reads (#1376). The
        env-var-honouring property this test was written for (#1041/#1048) is
        unchanged; only the fallback literal is gone.
        """
        text = IMPLEMENT_MD.read_text()
        assert ENV_VAR_PYTHON_PER_REPO_RE.search(text), (
            "implement.md must contain "
            "os.environ.get('PIPELINE_STATE_FILE', str(get_legacy_sentinel_path()))"
        )

    def test_heredoc_shell_rm_uses_env_var(self) -> None:
        """Shell cleanup sites still honour ${PIPELINE_STATE_FILE:-...}.

        The shell default is now a ``get_legacy_sentinel_path()`` subshell
        rather than the ``/tmp`` literal, for the same #1206 reason.
        """
        text = IMPLEMENT_MD.read_text()
        assert ENV_VAR_SHELL_PER_REPO_RE.search(text), (
            'implement.md must contain CLEANUP_STATE_FILE="${PIPELINE_STATE_FILE:-...}"'
        )

    def test_sentinel_read_in_resolve_session_id_uses_env_var(self) -> None:
        """All _resolve_session_id() sentinel reads use os.environ.get form."""
        text = IMPLEMENT_MD.read_text()
        # Count env-var-aware Python sentinel reads
        python_matches = len(
            re.findall(
                r"""os\.environ\.get\(['"]PIPELINE_STATE_FILE['"]""",
                text,
            )
        )
        assert python_matches >= 3, (
            f"Expected at least 3 env-var-aware sentinel references in implement.md, "
            f"found {python_matches}"
        )

    def test_gc_call_present_before_run_id_generation(self) -> None:
        """GC call (_gc_stale_states) appears before RUN_ID is generated in STEP 0."""
        text = IMPLEMENT_MD.read_text()
        gc_pos = text.find("_gc_stale_states")
        run_id_pos = text.find("RUN_ID=\"$(python3")
        assert gc_pos != -1, "implement.md must call _gc_stale_states"
        assert run_id_pos != -1, "implement.md must set RUN_ID"
        assert gc_pos < run_id_pos, (
            "GC call must appear BEFORE RUN_ID generation in implement.md"
        )

    def test_no_bare_literal_in_functional_open_calls(self) -> None:
        """No bare (unguarded) /tmp/implement_pipeline_state.json in open() or rm -f calls.

        Lines that use the env-var-aware form (os.environ.get or shell expansion)
        are allowed — they contain the literal as a default fallback, which is
        the correct migrated pattern.
        """
        text = IMPLEMENT_MD.read_text()
        violations = []
        for lineno, line in _functional_lines(text):
            if BARE_LITERAL not in line:
                continue
            # If the line already uses the env-var-aware form, it's correctly migrated
            if _has_env_var_form(line):
                continue
            # Reject if the line contains open(), rm -f, or with open( WITHOUT env-var form
            if re.search(r"""(open\(|rm\s+-f\b)""", line):
                violations.append((lineno, line.strip()))
        assert violations == [], (
            "Found bare (unguarded) literal in open()/rm-f in implement.md:\n"
            + "\n".join(f"  L{ln}: {l}" for ln, l in violations)
        )

    def test_legacy_tmp_literal_is_fully_retired(self) -> None:
        """implement.md carries ZERO machine-global /tmp sentinel literals.

        Inverted from the original assertion, deliberately. That assertion
        required the legacy literal to survive "in comments/docs" — which is
        exactly how a doc keeps instructing the wrong path. Every sentinel
        reference now resolves through get_legacy_sentinel_path() (#1206,
        #1376), so the literal has no remaining legitimate home here.
        """
        text = IMPLEMENT_MD.read_text()
        assert BARE_LITERAL not in text, (
            f"{BARE_LITERAL} must not appear in implement.md — "
            "get_legacy_sentinel_path() is the only sanctioned resolution"
        )
        # Positive control: the replacement IS present, so this is not passing
        # merely because the sentinel machinery was deleted wholesale.
        assert "get_legacy_sentinel_path()" in text


# ---------------------------------------------------------------------------
# Tests: implement-batch.md
# ---------------------------------------------------------------------------


class TestImplementBatchMdMigration:
    """Verify implement-batch.md cleanup site uses env-var form."""

    def test_file_exists(self) -> None:
        assert IMPLEMENT_BATCH_MD.exists(), f"Expected {IMPLEMENT_BATCH_MD} to exist"

    def test_rm_cleanup_uses_env_var(self) -> None:
        """The batch cleanup honours ${PIPELINE_STATE_FILE:-...}.

        Adjusted to the same post-#1206/#1376 form already asserted for
        implement.md by ``test_heredoc_shell_rm_uses_env_var``: the
        env-var-honouring property this test was written for (#1041/#1048) is
        unchanged, but the DEFAULT is now a ``get_legacy_sentinel_path()``
        subshell, not the machine-global /tmp literal. This file never exports
        PIPELINE_STATE_FILE, so that default is the path used on every batch run.
        """
        text = IMPLEMENT_BATCH_MD.read_text()
        assert ENV_VAR_SHELL_PER_REPO_RE.search(text), (
            'implement-batch.md must contain CLEANUP_STATE_FILE="${PIPELINE_STATE_FILE:-...}"'
        )
        assert BARE_LITERAL not in text, (
            f"{BARE_LITERAL} must not appear in implement-batch.md — "
            "get_legacy_sentinel_path() is the only sanctioned resolution"
        )
        # Positive control: the replacement IS present, so this does not pass
        # merely because the cleanup was deleted wholesale.
        assert "get_legacy_sentinel_path()" in text

    def test_no_bare_literal_in_functional_rm_calls(self) -> None:
        """No bare (unguarded) literal in rm -f calls inside implement-batch.md."""
        text = IMPLEMENT_BATCH_MD.read_text()
        violations = []
        for lineno, line in _functional_lines(text):
            if BARE_LITERAL not in line:
                continue
            if _has_env_var_form(line):
                continue
            if re.search(r"rm\s+-f\b", line):
                violations.append((lineno, line.strip()))
        assert violations == [], (
            "Found bare (unguarded) literal in rm-f in implement-batch.md:\n"
            + "\n".join(f"  L{ln}: {l}" for ln, l in violations)
        )


# ---------------------------------------------------------------------------
# Tests: implement-fix.md
# ---------------------------------------------------------------------------


class TestImplementFixMdMigration:
    """Verify implement-fix.md migrated sites use env-var form."""

    def test_file_exists(self) -> None:
        assert IMPLEMENT_FIX_MD.exists(), f"Expected {IMPLEMENT_FIX_MD} to exist"

    def test_write_site_uses_env_var(self) -> None:
        """Pipeline state initialization write uses the per-repo env-var form.

        Adjusted to the post-#1206/#1376 form already asserted for
        implement.md: the env-var-honouring property this test was written for
        (#1041/#1048) is unchanged, but the DEFAULT is now
        ``str(get_legacy_sentinel_path())``, not the machine-global /tmp
        literal. This test previously REQUIRED THE BUG — it asserted the /tmp
        form and would have blocked the migration it now locks.
        """
        text = IMPLEMENT_FIX_MD.read_text()
        assert ENV_VAR_PYTHON_PER_REPO_RE.search(text), (
            "implement-fix.md must use "
            "os.environ.get('PIPELINE_STATE_FILE', str(get_legacy_sentinel_path()))"
        )
        assert BARE_LITERAL not in text, (
            f"{BARE_LITERAL} must not appear in implement-fix.md — "
            "get_legacy_sentinel_path() is the only sanctioned resolution"
        )
        # Positive control: the replacement IS present, so this does not pass
        # merely because the state-init write was deleted wholesale.
        assert "get_legacy_sentinel_path()" in text

    def test_rm_cleanup_uses_env_var(self) -> None:
        """The STEP F6.5 cleanup honours ${PIPELINE_STATE_FILE:-...}.

        Same adjustment, and same reason, as ``TestImplementBatchMdMigration::
        test_rm_cleanup_uses_env_var``: implement-fix.md never exports
        PIPELINE_STATE_FILE, so the ``:-`` default IS the path used on every
        ``--fix`` run.
        """
        text = IMPLEMENT_FIX_MD.read_text()
        assert ENV_VAR_SHELL_PER_REPO_RE.search(text), (
            'implement-fix.md must contain CLEANUP_STATE_FILE="${PIPELINE_STATE_FILE:-...}"'
        )
        assert BARE_LITERAL not in text, (
            f"{BARE_LITERAL} must not appear in implement-fix.md — "
            "get_legacy_sentinel_path() is the only sanctioned resolution"
        )
        # Positive control: the replacement IS present, so this does not pass
        # merely because the cleanup was deleted wholesale.
        assert "get_legacy_sentinel_path()" in text

    def test_no_bare_literal_in_functional_open_or_rm_calls(self) -> None:
        """No bare (unguarded) literal in open() or rm -f calls in implement-fix.md."""
        text = IMPLEMENT_FIX_MD.read_text()
        violations = []
        for lineno, line in _functional_lines(text):
            if BARE_LITERAL not in line:
                continue
            if _has_env_var_form(line):
                continue
            if re.search(r"""(open\(|rm\s+-f\b)""", line):
                violations.append((lineno, line.strip()))
        assert violations == [], (
            "Found bare (unguarded) literal in open()/rm-f in implement-fix.md:\n"
            + "\n".join(f"  L{ln}: {l}" for ln, l in violations)
        )


# ---------------------------------------------------------------------------
# Tests: Scope-out preservation
# ---------------------------------------------------------------------------


class TestScopeOutPreservation:
    """Verify excluded sites remain unchanged (security guards, HMAC sentinel)."""

    def test_unified_pre_tool_security_guard_unchanged(self) -> None:
        """unified_pre_tool.py _check_bash_state_deletion still has literal path."""
        hook_path = (
            REPO_ROOT
            / "plugins"
            / "autonomous-dev"
            / "hooks"
            / "unified_pre_tool.py"
        )
        if not hook_path.exists():
            pytest.skip(f"Hook not found at {hook_path}")
        text = hook_path.read_text()
        # The guard function must still contain the literal string
        assert '"/tmp/implement_pipeline_state.json"' in text or (
            "'/tmp/implement_pipeline_state.json'" in text
        ), (
            "unified_pre_tool.py _check_bash_state_deletion must still use the "
            "literal path (scope-out per plan)"
        )

    def test_pipeline_state_legacy_sentinel_resolver_present(self) -> None:
        """pipeline_state.py provides the per-repo resolver (Issue #1206 update).

        Issue #1206 replaced the static LEGACY_SENTINEL_PATH constant with a
        per-repo resolver. The sentinel semantic role (HMAC fail-open activity
        indicator) is preserved; only the path resolution is now per-repo.
        """
        lib_path = (
            REPO_ROOT / "plugins" / "autonomous-dev" / "lib" / "pipeline_state.py"
        )
        if not lib_path.exists():
            pytest.skip(f"Lib not found at {lib_path}")
        text = lib_path.read_text()
        assert 'def get_legacy_sentinel_path' in text, (
            "pipeline_state.py must define get_legacy_sentinel_path() resolver"
        )
        assert 'LEGACY_SENTINEL_FILENAME' in text, (
            "pipeline_state.py must define LEGACY_SENTINEL_FILENAME constant"
        )
        # Confirm the new resolver anchors under .claude/local
        assert '.claude' in text and 'local' in text, (
            "Resolver must anchor at <repo>/.claude/local/"
        )
