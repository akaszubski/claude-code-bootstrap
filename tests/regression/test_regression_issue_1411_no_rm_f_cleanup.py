"""Regression test for Issue #1411.

The `/implement` pipeline's cleanup steps hardcoded `rm -f "$STATE_FILE"`
for removing the pipeline sentinel/state file, but the shipped safety deny
list (`Bash(rm:-f*)`, `Bash(rm:-rf*)`) hard-blocks that exact command --
making the pipeline's own cleanup un-runnable under the config it ships.
Verified live: blocked a spektiv `/implement --fix` cleanup step.

This test locks two things:

1. No pipeline STATE-FILE cleanup line in any coordinator uses the denied
   `rm -f`/`rm -rf` flags (the actual #1411 bug class).
2. The state-file cleanup step still references/removes the state file
   (the fix must not have silently deleted cleanup behavior).

Coverage: the file list is IMPORTED from
`tests/regression/test_implement_md_state_contract.py` as `ALL_COORDINATORS`
rather than restated here. That module discovers coordinators by file CONTENT
and pins the result against disk, so a fifth coordinator joins this test's
scope automatically. Arm 1 runs over all four; arms 2 and 3 run over
`CLEANUP_COORDINATORS`, derived by SUBTRACTION with per-arm reasons that are
NOT the same reason — read them, they differ in polarity.

Scope note: #1411 intentionally fixed only the pipeline STATE-FILE
cleanup sites (4 of them, across implement.md / implement-fix.md /
implement-batch.md). A handful of *other*, unrelated `rm -f`/`rm -rf`
invocations exist in these same files (temp scratch-file cleanup,
worktree deletion) that are a related-but-distinct instance of the same
deny-list bug class, deliberately left out of #1411's scope. Those are
locked below via a negative-assertion scope lock so a future pass can
find and fix them deliberately instead of this test silently widening.
"""

import re
from pathlib import Path

import pytest

# ONE list, not two. ``ALL_COORDINATORS`` is content-discovered and pinned
# against disk by ``TestCoordinatorCoverageIsMechanical`` in that module; a
# second literal list here would be a fourth hand-maintained copy of the same
# fact. Package import (no ``sys.path.insert``) — ``tests/__init__.py`` and
# ``tests/regression/__init__.py`` both exist, so this resolves under pytest's
# default ``prepend`` import mode without binding a second module object under
# a different ``__name__``.
from tests.regression.test_implement_md_state_contract import ALL_COORDINATORS

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "commands"

IMPLEMENT_MD = COMMANDS_DIR / "implement.md"
IMPLEMENT_FIX_MD = COMMANDS_DIR / "implement-fix.md"
IMPLEMENT_BATCH_MD = COMMANDS_DIR / "implement-batch.md"

FILES = list(ALL_COORDINATORS)

# Derived by SUBTRACTION, so a fifth coordinator joins both sets by default.
# implement-resume.md is the sole exclusion and the reason differs per arm —
# see the two inline reasons on the tests below. They are NOT the same reason.
CLEANUP_COORDINATORS = tuple(
    c for c in ALL_COORDINATORS if c.name != "implement-resume.md"
)

# Matches an *actual* rm invocation (not prose that merely mentions
# "rm -f" while explaining the deny rule) targeting one of the known
# pipeline state-file variables/paths.
STATE_FILE_RM_PATTERN = re.compile(
    r'rm\s+-r?f\s+"?\$\{?(?:PIPELINE_STATE_FILE|CLEANUP_STATE_FILE)\b'
    r'|rm\s+-r?f\s+["\']?\S*implement_pipeline_state\.json'
)

STATE_FILE_REFERENCES = (
    "PIPELINE_STATE_FILE",
    "CLEANUP_STATE_FILE",
    "implement_pipeline_state.json",
)


@pytest.mark.parametrize("file_path", FILES, ids=lambda p: p.name)
def test_no_denied_rm_flags_for_state_file_cleanup(file_path: Path) -> None:
    """No pipeline state-file cleanup line uses denied `rm -f`/`rm -rf`.

    The shipped safety deny list (`Bash(rm:-f*)`, `Bash(rm:-rf*)`) hard-blocks
    these flags, which previously made STEP 15 (implement.md), STEP L5
    (implement.md light mode), STEP F6.5 (implement-fix.md), and the
    post-batch-merge cleanup (implement-batch.md) un-runnable under the
    pipeline's own shipped config (#1411).
    """
    content = file_path.read_text()
    matches = STATE_FILE_RM_PATTERN.findall(content)
    assert not matches, (
        f"{file_path.name} contains a denied `rm -f`/`rm -rf` invocation "
        f"targeting the pipeline state file: {matches}. The shipped deny "
        "rules `Bash(rm:-f*)`/`Bash(rm:-rf*)` block this -- use a "
        'force-free deletion instead, e.g. `rm -- "$FILE" 2>/dev/null || '
        "true` or `pathlib.Path(...).unlink(missing_ok=True)`."
    )


@pytest.mark.parametrize("file_path", CLEANUP_COORDINATORS, ids=lambda p: p.name)
def test_state_file_cleanup_still_happens(file_path: Path) -> None:
    """The fix must not have deleted the cleanup call itself.

    implement-resume.md is subtracted because widening this arm to it would be
    GREEN-ON-PROSE, **not** RED. ``STATE_FILE_REFERENCES`` includes the bare
    string ``"PIPELINE_STATE_FILE"``, and implement-resume.md:65 mentions it in
    a PROSE SENTENCE ("Restore ``PIPELINE_STATE_FILE`` env var to point at
    ``/tmp/pipeline_state_<run_id>.json``"). So the assertion would pass while
    resume has no cleanup construct at all — a vacuous green of exactly the
    polarity ``test_implement_md_state_contract.py``'s resume pins exist to
    reverse.

    Tightening this arm instead was considered and REJECTED: a tightened
    version demanding an actual deletion construct is byte-for-byte the check
    ``test_state_file_cleanup_uses_force_free_deletion`` already performs — a
    second copy of one check, which is a "one canonical way" violation.
    """
    content = file_path.read_text()
    assert any(ref in content for ref in STATE_FILE_REFERENCES), (
        f"{file_path.name} no longer references the pipeline state file in "
        "any cleanup context -- the #1411 fix must preserve cleanup "
        "behavior, not remove it."
    )


@pytest.mark.parametrize("file_path", CLEANUP_COORDINATORS, ids=lambda p: p.name)
def test_state_file_cleanup_uses_force_free_deletion(file_path: Path) -> None:
    """Each file's state-file cleanup uses a non-denied deletion form.

    Accepts either `rm -- "$FILE" ... || true` (plain rm, no -f/-rf flag,
    guarded with `--`) or a Python `pathlib.Path(...).unlink(missing_ok=True)`
    one-liner. Either form avoids the denied `-f`/`-rf` flags entirely.

    implement-resume.md is subtracted for a DIFFERENT reason than the arm
    above, and this one genuinely goes RED when widened: MEASURED, resume has
    ZERO ``rm`` invocations and ZERO ``unlink(missing_ok=True)``, so neither
    accepted form is present. **Resume has no cleanup by design** — it hands
    the run back to a live pipeline rather than ending one.
    """
    content = file_path.read_text()
    has_plain_rm_guard = bool(
        re.search(r"rm\s+--\s+\"?\$\{?(?:PIPELINE_STATE_FILE|CLEANUP_STATE_FILE)", content)
    )
    has_unlink_missing_ok = "unlink(missing_ok=True)" in content
    assert has_plain_rm_guard or has_unlink_missing_ok, (
        f"{file_path.name} does not appear to use either accepted "
        "force-free deletion form (`rm -- \"$FILE\"` or "
        "`Path(...).unlink(missing_ok=True)`) for pipeline state-file "
        "cleanup."
    )


# --- Scope lock: known, intentionally out-of-scope rm -f/-rf uses -------
#
# These lines also use denied `rm -f`/`rm -rf` flags and would also be
# blocked by the shipped deny list, but they are NOT pipeline state-file
# cleanup -- they are a related-but-distinct instance of the same bug
# class (temp scratch-file cleanup, worktree deletion). #1411 explicitly
# scoped the fix to the 4 pipeline STATE-FILE cleanup sites only. This
# lock documents what's left so a future fix finds them deliberately
# instead of this test silently expanding scope. If one of these is
# fixed, update this list (and celebrate one less denied-command bug).
KNOWN_OUT_OF_SCOPE_RM = [
    # Temp scratch-file cleanup (issue body draft), not pipeline state.
    (IMPLEMENT_MD, "rm -f /tmp/implement_issue_body_$RUN_ID.txt"),
    # Worktree cleanup after a successful --batch merge/discard. Appears
    # twice (success path + discard path) with identical text.
    (IMPLEMENT_BATCH_MD, "rm -rf .worktrees/$BATCH_ID && git worktree prune"),
]


@pytest.mark.parametrize(
    "file_path,expected_snippet",
    KNOWN_OUT_OF_SCOPE_RM,
    ids=[f"{p.name}-{i}" for i, (p, _s) in enumerate(KNOWN_OUT_OF_SCOPE_RM)],
)
def test_known_out_of_scope_rm_uses_unchanged(file_path: Path, expected_snippet: str) -> None:
    """Lock the out-of-scope rm -f/-rf sites #1411 intentionally left alone.

    If this fails, one of these lines was fixed (great) -- update this
    list, and confirm the state-file tests above don't need to widen to
    cover the newly-fixed site.
    """
    content = file_path.read_text()
    assert expected_snippet in content, (
        f"{file_path.name} no longer contains the known out-of-scope "
        f"snippet {expected_snippet!r} -- update KNOWN_OUT_OF_SCOPE_RM in "
        "this test to match the current state."
    )
