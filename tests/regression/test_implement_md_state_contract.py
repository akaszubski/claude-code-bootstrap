"""State-plumbing contract for ALL FOUR ``/implement`` coordinators.

``implement.md``, ``implement-batch.md``, ``implement-fix.md`` and
``implement-resume.md``. Guards a CLASS of defect, not the instance that
prompted it: the coordinator markdown is executable instruction text, so a
wrong literal in it is production code that no linter, type-checker or import
graph can see.

Four shapes are refused here:

1. **Non-atomic sentinel writes.** ``open(path, 'w')`` truncates at OPEN time.
   A kill between the open and the ``json.dump`` left a 0-byte sentinel with
   the prior content already gone; ``ensure_sentinel_heartbeat`` then failed
   ``json.loads`` and recreated it as a bare ``{session_id, recovered,
   recovered_at}``, which ``_is_pipeline_active()`` classifies NOT-active by
   design (#1384) — blocking STEP 11 issue filing during a live pipeline.
   ``sentinel.write_text(...)`` is the SAME class in a different shape and is
   refused too (#1512). So is the VARIABLE-INDIRECTED form — the resolved
   path parked in a local first, then ``open(that_local, 'w')``. The arm
   originally matched only the inline shape plus two hardcoded variable
   NAMES, which the indirected form evaded silently; scoping is now DATAFLOW
   (any name BOUND to ``PIPELINE_STATE_FILE`` or ``get_legacy_sentinel_path``
   is tainted), because a longer name list is the hand-maintained thing this
   module exists to remove.
2. **A ``/tmp`` sentinel default.** ``get_legacy_sentinel_path()`` returns
   ``<repo>/.claude/local/implement_pipeline_state.json``. Measured: a
   different file. A doc-side ``/tmp`` default writes where the hook never reads.
3. **Hand-rolled ``_resolve_session_id()`` copies**, and calls to the canonical
   ``resolve_session_id()`` that omit ``sentinel_path=`` (the helper does not
   read ``PIPELINE_STATE_FILE`` itself, so omitting it silently drops env
   honouring).
4. **``gh issue create`` inside an executable ```bash fence.** That route is
   gated on ``_is_pipeline_active()``, which returns False for the remainder
   of any run whose sentinel was recovered.

EVERY extraction-based assertion carries a positive control over an inline
fixture with a KNOWN count, and pins an EXACT number. An extractor that
matches zero must FAIL here rather than report a clean doc.

COVERAGE — stated in BOTH directions, because a false claim of completeness
is the defect this module exists to remove and an OVERSTATED residual is the
same defect with the sign flipped.

**Membership does NOT mechanically imply coverage.** ``TestCoordinatorCoverage
IsMechanical`` proves the LIST (``ALL_COORDINATORS``) is complete against
disk. It proves NOTHING about whether any given CHECK is applied to every
member. So:

* **Universal** — parametrized over ``ALL_COORDINATORS`` (all four):
  ``test_no_tmp_literal_default_remains``, ``test_zero_handrolled_resolvers``,
  ``test_every_call_passes_sentinel_path``,
  ``test_no_non_atomic_sentinel_write``, and the widened
  ``test_resolve_session_id_call_sites_are_pinned``.
* **Singletons** — deliberately one-file, each with a stated reason:
  ``test_implement_md_bash_fence_count_is_pinned`` (an arbitrary structural
  count; four pins would churn on unrelated edits),
  ``test_export_pipeline_state_file_is_retained`` (``implement.md`` is the
  only producer; batch and fix deliberately have none), the gh-issue-create
  pins (fix mode has no STEP 11 and resume has no filing route, so a widened
  assertion would be a tautology), and the STEP-0 behavioural set (anchored on
  ``STEP0_ANCHOR``, unique to ``implement.md``) which gains exactly ONE
  fix-mode sibling pair and no more.

WHAT THIS GUARD STILL CANNOT SEE — measured, not guessed:

1. **A coordinator that manipulates the sentinel without naming
   ``PIPELINE_STATE_FILE`` or ``resolve_session_id`` in its own text** (e.g.
   through a helper wrapper). Invisible to ``discover_coordinators()`` AND to
   every arm. LIVE class, no live instance.
2. **Executable instructions outside any fence** — inline-backtick commands.
   **LIVE**: this shape ran in ``implement-fix.md``'s STEP F6.5 cleanup, a
   full ``rm -- "${PIPELINE_STATE_FILE:-…}"`` in running prose inside no
   fence. That instance is now fenced; the CLASS stays unseen.
3. **``state_file_reads()`` counts only PYTHON reads.** ``_PSF_ANY`` is
   ``os.environ.get('PIPELINE_STATE_FILE'…)`` — a **shell** ``export
   PIPELINE_STATE_FILE=`` or ``${PIPELINE_STATE_FILE:-…}`` never matches.
   **LIVE**, and the enumeration below is the COMPLETE measured inventory as
   of 2026-09-05, not an illustration — an understated residual is the same
   defect this module exists to remove, with the sign flipped. SIX shell-form
   sites across three coordinators — ``implement.md`` 4, ``implement-batch.md``
   1, ``implement-fix.md`` 1, ``implement-resume.md`` 0 — reproduced by::

       grep -cE '^[[:space:]]*(export[[:space:]]+PIPELINE_STATE_FILE$|PIPELINE_STATE_FILE=)|[$][{]PIPELINE_STATE_FILE' \\
           plugins/autonomous-dev/commands/implement*.md

   ``implement.md`` — line 318 (``PIPELINE_STATE_FILE="$(python3 …)"``
   assignment), line 326 (``export PIPELINE_STATE_FILE``), lines 2661 and 2940
   (both ``CLEANUP_STATE_FILE="${PIPELINE_STATE_FILE:-$(python3 …)}"``);
   ``implement-batch.md`` — line 498 (same cleanup form);
   ``implement-fix.md`` — line 726, the STEP F6.5 cleanup (same form). An
   earlier revision of this list named only FOUR of the six, omitting
   ``implement.md:2661`` and ``:2940`` while reading as an inventory — a
   recorded reason that did not match the behaviour, which is precisely the
   defect class this module refuses. Line numbers drift with edits; re-run the
   grep rather than trusting them. This is why the
   ``RESUME_MD == (0,0,0)`` pin is weaker than it looks — see its inline
   comment.
4. **Fences tagged ``sh``/``shell``/``py``/``console``/``zsh``.** MEASURED
   ZERO live instances across all four coordinators
   (``grep -cE '^[ \\t]*```(sh|shell|py|console|zsh)\\b'`` returns 0) — unlike
   residuals 2 and 3, this one is genuinely HYPOTHETICAL.
5. **Whether any block other than ``implement.md`` STEP 0 and
   ``implement-fix.md``'s state-init actually executes** — the other blocks
   carry text-only assertions.

Issues: #989, #1041, #1206, #1376, #1384, #1481, #1512
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "lib"
HOOK_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "hooks"
COMMANDS_DIR = REPO_ROOT / "plugins" / "autonomous-dev" / "commands"
IMPLEMENT_MD = COMMANDS_DIR / "implement.md"
BATCH_MD = COMMANDS_DIR / "implement-batch.md"
FIX_MD = COMMANDS_DIR / "implement-fix.md"
RESUME_MD = COMMANDS_DIR / "implement-resume.md"

# The single list. Every universal check parametrizes over exactly this tuple,
# and TestCoordinatorCoverageIsMechanical proves it complete against disk by
# CONTENT, not by filename.
ALL_COORDINATORS = (IMPLEMENT_MD, BATCH_MD, FIX_MD, RESUME_MD)
COORDINATOR_IDS = ("implement", "batch", "fix", "resume")

# The two read-only-parent REFUSE arms below cannot be produced under uid 0.
# Hoisted to ONE definition because the predicate and its reason were
# duplicated at two call sites, and a duplicated reason is a reason that
# drifts — as this one had.
#
# The wording matters and the earlier text got the polarity backwards. It said
# the control would be "vacuous" under root. It would not: uid 0 bypasses the
# ``chmod(0o500)``, ``mkstemp`` therefore SUCCEEDS, the child exits 0, and
# ``assert proc.returncode != 0`` FAILS. The test goes RED, not silently
# green. Naming the wrong failure mode in a skip reason is the same defect
# this module exists to refuse — a recorded reason that does not match the
# behaviour — so the skip is justified but its stated cause was not.
_IS_ROOT = hasattr(os, "getuid") and os.getuid() == 0
_ROOT_SKIP = (
    "uid 0 bypasses directory mode bits: the read-only-parent REFUSE arm "
    "cannot be produced, so this control would fail spuriously rather than "
    "discriminate"
)

# Per-coordinator inventory of canonical ``resolve_session_id(sentinel_path=…)``
# call sites. This replaced two hardcoded ``impl.count(...)``/``batch.count(...)``
# literals — the THIRD hand-maintained list, and it lived inside this module.
EXPECTED_SENTINEL_PATH_CALLS = {
    "implement.md": 3,  # :145, :186, :378
    "implement-batch.md": 2,  # :745 (indented fence), :849
    "implement-fix.md": 1,  # the STEP F3 pytest-gate ```python block
    "implement-resume.md": 0,  # ZERO-SUBJECT — see TestResumeZeroSubjectPins
}


# ---------------------------------------------------------------------------
# Extractors (each has a positive control below)
# ---------------------------------------------------------------------------

# Indentation-tolerant. The previous anchored ``^```bash`` form could not see
# an INDENTED fence, and that was a LIVE blind spot, not a hypothetical one:
# implement-batch.md carries 23 executable fences of which the anchored regex
# read 6. The single largest casualty was implement-batch.md:488 — the
# 3-space-indented ``CLEANUP_STATE_FILE="${PIPELINE_STATE_FILE:-…}"`` block
# this module holds up as the correct reference implementation. The guard had
# never read it. See TestFenceExtractorAxes for the live control.
_BASH_FENCE = re.compile(r"^[ \t]*```bash[^\n]*\n(.*?)^[ \t]*```", re.M | re.S)
# Both executable tags. A ```python fence is executable instruction text too:
# implement-fix.md's pytest-gate block is a ```python fence, and its bare
# ``resolve_session_id()`` call was invisible to a bash-only extractor even
# once the file was added to the coordinator list.
_EXEC_FENCE = re.compile(
    r"^[ \t]*```(?:bash|python)[^\n]*\n(.*?)^[ \t]*```", re.M | re.S
)
_PSF_ANY = re.compile(r"_?os\.environ\.get\(\s*['\"]PIPELINE_STATE_FILE['\"]")
_PSF_SANCTIONED_DEFAULT = re.compile(
    r"_?os\.environ\.get\(\s*['\"]PIPELINE_STATE_FILE['\"]\s*,\s*"
    r"str\(get_legacy_sentinel_path\(\)\)\s*\)"
)
_PSF_NO_DEFAULT = re.compile(
    r"_?os\.environ\.get\(\s*['\"]PIPELINE_STATE_FILE['\"]\s*\)\s*or\s*None"
)
_HANDROLLED_RESOLVER = re.compile(r"^\s*def\s+_resolve_session_id\s*\(", re.M)
_RESOLVE_CALL = re.compile(r"resolve_session_id\(\s*(?P<args>[^)]*)")
_NON_ATOMIC_SENTINEL_WRITE = re.compile(
    r"open\(\s*_?os\.environ\.get\(\s*['\"]PIPELINE_STATE_FILE['\"][^\n]*['\"]w['\"]\s*\)"
    r"|sentinel\.write_text\(|state_path\.write_text\("
)

# The INDIRECTED arm. The pattern above matches the INLINE ``open(os.environ
# .get(...), 'w')`` form plus two hardcoded variable NAMES — i.e. the shapes
# we HAPPENED to have. Park the resolved path in a local first and it misses:
#
#     p = os.environ.get('PIPELINE_STATE_FILE', str(get_legacy_sentinel_path()))
#     with open(p, 'w') as f: json.dump(state, f)
#
# Byte-identical bug, invisible guard. That is this module's own defect class
# one level down, so the fix removes the CATEGORY rather than adding ``p`` to
# a list: any name BOUND to a sentinel expression is tainted, and a
# truncating write through a tainted name is refused whatever it is called.
#
# Scoping is DATAFLOW, not name shape, and that scoping is load-bearing:
# MEASURED, the name-blind form the reviewer first proposed
# (``open\(\s*[A-Za-z_][\w.]*\s*,\s*['"]w['"]``) matches THREE live sites in
# implement.md — the ``# ATOMIC. open(path,'w') truncates…`` comment plus two
# legitimate ``open(log_file, 'w')`` / ``open(ack_file, 'w')`` writes. Two of
# those three are real over-captures that no comment filter removes, so the
# guard would have been deleted rather than fixed. See
# FIXTURE_LEGITIMATE_NON_SENTINEL_WRITE for the control that pins this.
_SENTINEL_BINDING = re.compile(
    r"^[ \t]*(?P<name>[A-Za-z_]\w*)\s*=\s*[^\n]*?"
    r"(?:_?os\.environ\.get\(\s*['\"]PIPELINE_STATE_FILE['\"]"
    r"|get_legacy_sentinel_path\()",
    re.M,
)
_TRUNCATING_WRITE_TMPL = r"open\(\s*(?:{names})\s*,\s*['\"]w['\"]|(?:{names})\.write_text\("


def bash_fences(text: str) -> list[str]:
    """Return the body of every ```bash fence, indented or not."""
    return _BASH_FENCE.findall(text)


def executable_fences(text: str) -> list[str]:
    """Return the body of every executable fence: ```bash AND ```python.

    Indentation-tolerant on both tags — a fence nested inside a numbered list
    item is still an instruction the coordinator runs.
    """
    return _EXEC_FENCE.findall(text)


def executable_text(text: str) -> str:
    """Return ONLY the executable portion: the concatenated ```bash and
    ```python fences.

    Prose and comments describing the contract (``pass
    ``sentinel_path=os.environ.get('PIPELINE_STATE_FILE') or None``…``) are
    documentation, not instructions the coordinator runs. Counting them would
    make every pin drift on a wording change while the executable text was
    unchanged — the exact way a contract guard becomes noise and gets deleted.

    RESIDUALS this exclusion still buys, stated so nobody reads a green here
    as full coverage (details in the module docstring):

    * **LIVE** — executable instructions in INLINE BACKTICKS, outside any
      fence, are not returned. That shape ran in implement-fix.md's cleanup.
    * **LIVE** — ``state_file_reads`` reads this body with a PYTHON-only
      regex, so a shell ``export PIPELINE_STATE_FILE=`` or
      ``${PIPELINE_STATE_FILE:-…}`` inside a returned fence is still not
      counted.
    * **MEASURED ZERO / hypothetical** — fences tagged ``sh``/``shell``/
      ``py``/``console``/``zsh`` are not returned; there are none live.
    """
    return "\n".join(executable_fences(text))


def gh_issue_create_in_bash_fences(text: str) -> int:
    """Count ``gh issue create`` occurrences inside ```bash fences only.

    Deliberately NOT routed through ``executable_text``: the gate this mirrors
    is a Bash-tool gate. Measured: implement.md's sole ``gh issue create``
    occurrence sits inside a top-level ```python fence and is already pinned
    whole-file by ``test_gh_issue_create_occurrences_are_pinned``. Widening
    this to python fences would flip that pin from 0 to 1 for no gain.
    """
    return sum(f.count("gh issue create") for f in bash_fences(text))


# Tokens that make a commands/*.md file a sentinel-state coordinator. CONTENT,
# never filename — a filename predicate (``implement*.md``) is an exclusion
# list wearing a prefix, and a future ``pipeline-fix.md`` carrying sentinel
# logic would sit silently outside it. That is the fifth recurrence of the
# defect class this module closes.
COORDINATOR_TOKENS = ("PIPELINE_STATE_FILE", "resolve_session_id")


def discover_coordinators(commands_dir: Path) -> set[Path]:
    """Return every ``*.md`` in ``commands_dir`` whose TEXT names a sentinel
    token.

    An unreadable file is NOT a coordinator, and its name is surfaced by the
    caller rather than swallowed into a silent pass.
    """
    found: set[Path] = set()
    for path in sorted(commands_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if any(tok in text for tok in COORDINATOR_TOKENS):
            found.add(path)
    return found


def unreadable_command_files(commands_dir: Path) -> list[str]:
    """Names of ``*.md`` files ``discover_coordinators`` could not read."""
    bad: list[str] = []
    for path in sorted(commands_dir.glob("*.md")):
        try:
            path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            bad.append(path.name)
    return bad


def state_file_reads(text: str) -> tuple[int, int, int]:
    """Return (total PIPELINE_STATE_FILE reads, sanctioned-default, no-default).

    Scoped to executable fences.
    """
    body = executable_text(text)
    return (
        len(_PSF_ANY.findall(body)),
        len(_PSF_SANCTIONED_DEFAULT.findall(body)),
        len(_PSF_NO_DEFAULT.findall(body)),
    )


def handrolled_resolvers(text: str) -> int:
    return len(_HANDROLLED_RESOLVER.findall(executable_text(text)))


def resolve_calls_missing_sentinel_path(text: str) -> list[str]:
    """Return every executable ``resolve_session_id(...)`` call lacking
    ``sentinel_path=``. Comment lines inside fences are skipped."""
    bad = []
    for line in executable_text(text).splitlines():
        if line.lstrip().startswith("#"):
            continue
        for m in _RESOLVE_CALL.finditer(line):
            if "sentinel_path=" not in m.group("args"):
                bad.append(m.group(0))
    return bad


def sentinel_bound_names(body: str) -> set[str]:
    """Return every local name BOUND to a sentinel-path expression in ``body``.

    A name is tainted when it is assigned from ``os.environ.get(
    'PIPELINE_STATE_FILE'…)`` or ``get_legacy_sentinel_path()`` anywhere in
    the same text. Comment lines do not taint.

    Deliberately over-inclusive in one direction: a line such as ``sid =
    resolve_session_id(sentinel_path=os.environ.get('PIPELINE_STATE_FILE')
    or None)`` taints ``sid``, which holds a session id and not a path. That
    is the CONSERVATIVE direction — it can only cause a refusal, never a
    silent pass — and it is measured to cost nothing: no coordinator writes
    through any of those names. Tightening it to "the sentinel expression is
    the whole RHS" would drop the ``Path(os.environ.get(…))`` wrapper form,
    which is a real evasion.
    """
    names: set[str] = set()
    for match in _SENTINEL_BINDING.finditer(body):
        line_start = body.rfind("\n", 0, match.start()) + 1
        if body[line_start:].lstrip().startswith("#"):
            continue
        names.add(match.group("name"))
    return names


def non_atomic_sentinel_writes(text: str) -> int:
    """Count truncate-at-open sentinel writes: inline shapes PLUS indirected.

    Reads RAW ``text``, not ``executable_text``, and that is deliberate on
    both counts:

    * The callers include ``test_step0_block_is_extractable_and_uses_atomic_write``
      and its fix-mode sibling, which pass an already-extracted ``python3 -c``
      body carrying NO fence. Scoping to ``executable_text`` would return the
      empty string for exactly the two blocks that are proven to EXECUTE, and
      the arm would silently stop applying where it matters most.
    * The prose-over-capture that normally forces fence-scoping is dissolved
      by the taint scoping: MEASURED, raw and fence-scoped bodies give the
      identical count (0) on all four live coordinators.

    If a coordinator's PROSE ever documents the anti-pattern verbatim this
    will refuse it; the repair is to fence the example, not to loosen this.
    """
    # Counted as SPANS, not as two independent tallies: ``state_path`` is both
    # a hardcoded name in the inline pattern AND tainted by its own binding,
    # so a naive sum would report one write twice.
    spans: set[tuple[int, int]] = {m.span() for m in _NON_ATOMIC_SENTINEL_WRITE.finditer(text)}

    names = sentinel_bound_names(text)
    if names:
        alternation = "|".join(re.escape(n) for n in sorted(names))
        indirected = re.compile(_TRUNCATING_WRITE_TMPL.format(names=alternation))
        offset = 0
        for line in text.splitlines(keepends=True):
            if not line.lstrip().startswith("#"):
                for m in indirected.finditer(line):
                    spans.add((offset + m.start(), offset + m.end()))
            offset += len(line)
    return len(spans)


def extract_python_c_block(text: str, anchor: str) -> str:
    """Return the body of the ``python3 -c "..."`` block containing ``anchor``."""
    idx = text.index(anchor)
    start = text.rindex('python3 -c "', 0, idx) + len('python3 -c "')
    end = text.index('\n"\n', start)
    return text[start:end]


# ---------------------------------------------------------------------------
# Inline fixtures for the positive controls (KNOWN counts)
# ---------------------------------------------------------------------------

FIXTURE_TWO_GH_IN_BASH = """\
Prose mentioning gh issue create must NOT be counted.

```bash
gh issue create --title "one"
```

```python
gh issue create --title "not bash, not counted"
```

```bash
echo hi
gh issue create --title "two"
```
"""

FIXTURE_TWO_STATE_DEFAULTS = """\
```bash
python3 -c "
a = os.environ.get('PIPELINE_STATE_FILE', str(get_legacy_sentinel_path()))
b = _os.environ.get('PIPELINE_STATE_FILE', str(get_legacy_sentinel_path()))
c = os.environ.get('PIPELINE_STATE_FILE') or None
"
```
"""

FIXTURE_TMP_LITERAL_DEFAULT = """\
```bash
python3 -c "
p = os.environ.get('PIPELINE_STATE_FILE', '/tmp/implement_pipeline_state.json')
"
```
"""

FIXTURE_HANDROLLED_RESOLVER = """\
```bash
python3 -c "
def _resolve_session_id():
    return os.environ.get('CLAUDE_SESSION_ID', 'unknown')
sid = _resolve_session_id()
"
```
"""

FIXTURE_BARE_RESOLVE_CALL = """\
```bash
python3 -c "
sid = resolve_session_id()
"
```
"""

FIXTURE_OPEN_W_WRITE = """\
```bash
python3 -c "
with open(os.environ.get('PIPELINE_STATE_FILE', str(get_legacy_sentinel_path())), 'w') as f:
    json.dump(state, f)
"
```
"""

FIXTURE_WRITE_TEXT_WRITE = """\
```bash
python3 -c "
sentinel.write_text(json.dumps(state), encoding='utf-8')
"
```
"""

# 1h, VARIABLE-INDIRECTED refuse control — a DIFFERENT SHAPE from either of
# the two above, and from the live instance that prompted the arm.
#
# The original arm matched an INLINE ``open(os.environ.get(...), 'w')`` plus
# two hardcoded variable NAMES (``sentinel``, ``state_path``). Park the
# resolved path in a local first and every one of those misses, while the bug
# is byte-identical: ``open`` truncates at OPEN time, so a kill before the
# ``json.dump`` leaves a 0-byte sentinel with the prior content already gone.
# That is the same defect class the arm exists to close, one level down —
# a guard scoped to the shape that prompted it.
#
# The variable is named ``p`` DELIBERATELY: no name-based widening
# (``sentinel``/``state``/``psf``…) can green this, so the control forces the
# taint-based scoping in ``non_atomic_sentinel_writes`` rather than a longer
# name list, which would be the same hand-maintained enumeration again.
FIXTURE_VARIABLE_INDIRECTED_WRITE = """\
```bash
python3 -c "
p = os.environ.get('PIPELINE_STATE_FILE', str(get_legacy_sentinel_path()))
with open(p, 'w') as f:
    json.dump(state, f)
"
```
"""

# 1i, the SECOND variable-indirected shape: ``write_text`` on a name that is
# neither ``sentinel`` nor ``state_path``. Proves the widening removed the
# name ENUMERATION rather than extending it.
FIXTURE_INDIRECTED_WRITE_TEXT = """\
```bash
python3 -c "
psf = Path(os.environ.get('PIPELINE_STATE_FILE', str(get_legacy_sentinel_path())))
psf.write_text(json.dumps(state), encoding='utf-8')
"
```
"""

# 1j, the PERMIT control for that widening, aimed at OVER-capture. A sentinel
# binding is present (so the taint set is non-empty) AND two legitimate
# non-sentinel writes happen in the same body.
#
# MEASURED, not invented: implement.md carries exactly this pair —
# ``with open(log_file, 'w')`` and ``with open(ack_file, 'w')`` — alongside
# three sentinel bindings. A name-blind ``open(<var>, 'w')`` widening refuses
# both and takes the whole guard down with it. Reproduce with::
#
#     grep -nE "open\\(\\s*[A-Za-z_][\\w.]*\\s*,\\s*['\\\"]w['\\\"]" \\
#         plugins/autonomous-dev/commands/implement.md
FIXTURE_LEGITIMATE_NON_SENTINEL_WRITE = """\
```bash
python3 -c "
state_path = os.environ.get('PIPELINE_STATE_FILE', str(get_legacy_sentinel_path()))
with open(log_file, 'w') as f:
    f.write('a log line')
with open(ack_file, 'w') as f:
    f.write('ack')
"
```
"""

FIXTURE_PYTHON_C_BLOCK = '''\
```bash
python3 -c "
import os
MARKER_ANCHOR = 1
print('done')
"
```
'''

# 1b-control, INDENTATION axis. One top-level fence and one 3-space-indented
# fence inside a numbered list item — the exact shape of
# implement-batch.md:488. KNOWN exact count: 2.
FIXTURE_INDENTED_FENCE = """\
Prose.

```bash
echo MARKER_TOP
```

4. **A step with a nested fence**:
   ```bash
   echo MARKER_INDENTED
   ```

More prose.
"""

# 1f, DIFFERENT-SHAPE negative control. The observed bug was "a file the guard
# does not read"; this control is "a fence the guard does not read", inside a
# file it does. Against the pre-widening extractor the file is read, the arm
# exists, and the assertion silently does not apply.
FIXTURE_PYTHON_FENCE_BARE_CALL = """\
```python
from pipeline_completion_state import resolve_session_id

SESSION_ID = resolve_session_id()
```
"""


# ---------------------------------------------------------------------------
# 1. VACUITY GUARDS — run these first
# ---------------------------------------------------------------------------


class TestExtractorPositiveControls:
    """Every extractor must return a KNOWN non-zero count on a known input."""

    def test_bash_fence_extractor_finds_exactly_two(self) -> None:
        assert len(bash_fences(FIXTURE_TWO_GH_IN_BASH)) == 2
        assert gh_issue_create_in_bash_fences(FIXTURE_TWO_GH_IN_BASH) == 2
        # And it does NOT count the prose line or the ```python fence.
        assert FIXTURE_TWO_GH_IN_BASH.count("gh issue create") == 4

    def test_state_file_extractor_finds_exactly_two_and_one(self) -> None:
        total, sanctioned, no_default = state_file_reads(FIXTURE_TWO_STATE_DEFAULTS)
        assert (total, sanctioned, no_default) == (3, 2, 1)

    def test_handrolled_resolver_extractor_finds_exactly_one(self) -> None:
        assert handrolled_resolvers(FIXTURE_HANDROLLED_RESOLVER) == 1

    def test_missing_sentinel_path_extractor_finds_exactly_one(self) -> None:
        assert len(resolve_calls_missing_sentinel_path(FIXTURE_BARE_RESOLVE_CALL)) == 1
        assert resolve_calls_missing_sentinel_path(FIXTURE_TWO_STATE_DEFAULTS) == []

    def test_non_atomic_write_extractor_finds_each_shape(self) -> None:
        assert non_atomic_sentinel_writes(FIXTURE_OPEN_W_WRITE) == 1
        assert non_atomic_sentinel_writes(FIXTURE_WRITE_TEXT_WRITE) == 1
        assert non_atomic_sentinel_writes(FIXTURE_VARIABLE_INDIRECTED_WRITE) == 1
        assert non_atomic_sentinel_writes(FIXTURE_INDIRECTED_WRITE_TEXT) == 1
        # …and a KNOWN ZERO, so the extractor is not merely match-everything.
        assert non_atomic_sentinel_writes(FIXTURE_LEGITIMATE_NON_SENTINEL_WRITE) == 0

    def test_python_c_block_extractor_returns_the_body(self) -> None:
        body = extract_python_c_block(FIXTURE_PYTHON_C_BLOCK, "MARKER_ANCHOR")
        assert body.strip().startswith("import os")
        assert "MARKER_ANCHOR = 1" in body
        assert "```" not in body


class TestFenceExtractorAxes:
    """Both axes of the fence extractor, each with its own control.

    The extractor was scoped to the SHAPE of the file where the original bug
    was found. implement.md uses top-level fences, so the ``^```bash`` anchor
    was never exercised — and implement-batch.md's 3-space-indented fences,
    17 of 23 executable blocks, were silently unread for the entire life of
    this module.
    """

    def test_indented_fence_is_extracted_with_a_known_count(self) -> None:
        """INDENTATION axis, synthetic control with a KNOWN exact count."""
        # If the regex is ever re-anchored, this literal is what makes the
        # marker assertion below go RED instead of the case being quietly
        # deleted along with the indentation.
        assert "\n   ```bash" in FIXTURE_INDENTED_FENCE
        assert len(bash_fences(FIXTURE_INDENTED_FENCE)) == 2
        body = executable_text(FIXTURE_INDENTED_FENCE)
        assert "MARKER_TOP" in body
        assert "MARKER_INDENTED" in body

    def test_indented_fence_axis_reads_the_live_reference_implementation(
        self,
    ) -> None:
        """INDENTATION axis, LIVE arm — the strongest one available.

        ``CLEANUP_STATE_FILE=`` occurs in implement-batch.md at :498, inside
        the 3-space-indented fence 488-510, and at :514 in prose between
        fences. So this assertion is FALSE against the pre-widening guard and
        TRUE after it: **the guard had never read the reference implementation
        it holds up as correct.**
        """
        assert "CLEANUP_STATE_FILE=" in executable_text(BATCH_MD.read_text())

    def test_python_fence_is_extracted_but_bash_fences_stays_bash_only(
        self,
    ) -> None:
        """TAG axis. ``executable_fences`` sees both tags; ``bash_fences``
        (which backs the Bash-tool gh gate) deliberately still sees one."""
        assert len(executable_fences(FIXTURE_PYTHON_FENCE_BARE_CALL)) == 1
        assert len(bash_fences(FIXTURE_PYTHON_FENCE_BARE_CALL)) == 0
        assert len(executable_fences(FIXTURE_TWO_GH_IN_BASH)) == 3
        assert len(bash_fences(FIXTURE_TWO_GH_IN_BASH)) == 2

    def test_python_fence_bare_call_is_refused(self) -> None:
        """1f — DIFFERENT-SHAPE negative control for the TAG axis."""
        assert resolve_calls_missing_sentinel_path(
            FIXTURE_PYTHON_FENCE_BARE_CALL
        ) == ["resolve_session_id("]

    def test_no_live_coordinator_uses_an_unread_fence_tag(self) -> None:
        """Residual 4 is HYPOTHETICAL, and this is the measurement.

        If a coordinator ever gains an ``sh``/``shell``/``py``/``console``/
        ``zsh`` fence this goes RED and the residual becomes LIVE — at which
        point widen ``_EXEC_FENCE`` rather than editing this number.
        """
        pattern = re.compile(r"^[ \t]*```(sh|shell|py|console|zsh)\b", re.M)
        offenders = {
            doc.name: len(pattern.findall(doc.read_text()))
            for doc in ALL_COORDINATORS
            if pattern.search(doc.read_text())
        }
        assert offenders == {}, offenders


class TestPinnedOccurrenceCounts:
    """Exact counts on the LIVE docs. Never ``>= 1`` — a drifted extractor
    that matched nothing would sail through an at-least assertion."""

    def test_implement_md_state_file_reads_are_pinned(self) -> None:
        total, sanctioned, no_default = state_file_reads(IMPLEMENT_MD.read_text())
        assert (total, sanctioned, no_default) == (9, 6, 3), (
            "PIPELINE_STATE_FILE read sites changed. Every read MUST be either "
            "the sanctioned get_legacy_sentinel_path() default or the "
            "`or None` pass-through; update this pin deliberately."
        )
        # Nothing outside the two sanctioned forms exists.
        assert sanctioned + no_default == total

    def test_batch_md_state_file_reads_are_pinned(self) -> None:
        """Re-pinned from (1,0,1) by the indentation widening.

        implement-batch.md:745 lives inside the indented fence 725-778 and was
        invisible; :849 lives inside the top-level fence 831-856 and was
        visible. Both are ``or None`` no-default forms.
        """
        total, sanctioned, no_default = state_file_reads(BATCH_MD.read_text())
        assert (total, sanctioned, no_default) == (2, 0, 2)
        assert sanctioned + no_default == total

    def test_fix_md_state_file_reads_are_pinned(self) -> None:
        """MEASURED after FIX 1: (7, 6, 1). Matches the plan's prediction.

        Derivation, verified against the live file: pre-widening (5,0,0) —
        :95,:138,:352,:392,:647 are in bash fences. The ```python-tag half of
        the widening added :273 from the pytest-gate fence, giving (6,0,0)
        pre-fix. FIX 1 turned those six into sanctioned
        get_legacy_sentinel_path() defaults and added the seventh read as the
        sole ``or None`` pass-through at the resolve_session_id() call site.

        The STEP F6.5 cleanup is NOT counted here and never was, before or
        after its conversion to a fence: it resolves through the SHELL form
        ``${PIPELINE_STATE_FILE:-$(python3 -c …)}``, and ``_PSF_ANY`` matches
        only ``os.environ.get``. That is LIVE residual 3 from the module
        docstring, visible right here.
        """
        total, sanctioned, no_default = state_file_reads(FIX_MD.read_text())
        assert (total, sanctioned, no_default) == (7, 6, 1)
        assert sanctioned + no_default == total

    def test_fix_md_state_init_block_uses_atomic_write(self) -> None:
        """Static arm for FIX 1's headline change (the behavioural pair is
        ``test_fix_state_write_permit_arm`` / ``…_dir_readonly``)."""
        block = extract_python_c_block(FIX_MD.read_text(), FIX_STEP0_ANCHOR)
        assert "atomic_write_json(" in block
        assert non_atomic_sentinel_writes(block) == 0
        # No FUNCTIONAL open() survives. Comment lines are skipped on purpose:
        # the block's rationale comment quotes ``open(path,'w')`` by name, and
        # a naive substring check would refuse the very explanation of the fix.
        functional_opens = [
            ln
            for ln in block.splitlines()
            if "open(" in ln and not ln.lstrip().startswith("#")
        ]
        assert functional_opens == [], functional_opens

    def test_fix_md_cleanup_is_fenced_and_force_free(self) -> None:
        """STEP F6.5 used to be a full ``rm -- "${PIPELINE_STATE_FILE:-…}"``
        living in RUNNING PROSE, inside no fence — invisible to every
        fence-scoped arm in this module. It is now a ```bash fence mirroring
        implement-batch.md:488-510."""
        fences = bash_fences(FIX_MD.read_text())
        cleanup = [f for f in fences if 'rm -- "$CLEANUP_STATE_FILE"' in f]
        assert len(cleanup) == 1, "STEP F6.5 cleanup must live in exactly one bash fence"
        body = cleanup[0]
        assert 'CLEANUP_STATE_FILE="${PIPELINE_STATE_FILE:-' in body
        assert "get_legacy_sentinel_path" in body
        assert "Issue #1411" in body
        assert not re.search(r"rm\s+-r?f\b", body), "denied force flags"
        assert "2>/dev/null || true" in body

    def test_implement_md_bash_fence_count_is_pinned(self) -> None:
        """Re-pinned 36 -> 39 by the indentation widening.

        The three newly-visible openers are implement.md:2082,2131,2168. All
        eight indented fence pairs in that file are balanced and sit OUTSIDE
        every top-level fence, so opener count == regex match count.

        Deliberately NOT widened to the other three coordinators: this is an
        arbitrary structural count and four such pins would churn on unrelated
        edits.
        """
        assert len(bash_fences(IMPLEMENT_MD.read_text())) == 39

    def test_gh_issue_create_occurrences_are_pinned(self) -> None:
        text = IMPLEMENT_MD.read_text()
        assert text.count("gh issue create") == 1, (
            "The ONLY sanctioned occurrence is the deferred placeholder comment "
            "in the MEDIUM-convergence DEFER branch."
        )
        sole = [ln for ln in text.splitlines() if "gh issue create" in ln]
        assert sole == ["            # Note: Actual gh issue create command would go here"]

    @pytest.mark.parametrize("doc", ALL_COORDINATORS, ids=COORDINATOR_IDS)
    def test_resolve_session_id_call_sites_are_pinned(self, doc: Path) -> None:
        """The THIRD hand-maintained file list used to live right here.

        ``impl.count(...) == 3`` / ``batch.count(...) == 2`` — two hardcoded
        literals inside the very module doing the de-hand-maintaining. A new
        call site in a third coordinator was neither counted nor noticed.

        Reads RAW text, not ``executable_text``: deliberate, this is a
        whole-file inventory.
        """
        expected = EXPECTED_SENTINEL_PATH_CALLS[doc.name]
        actual = doc.read_text().count("resolve_session_id(sentinel_path=")
        assert actual == expected, (
            f"{doc.name}: expected {expected} canonical resolve_session_id("
            f"sentinel_path=…) call sites, found {actual}. Update this pin "
            "deliberately — every call MUST pass sentinel_path= because "
            "resolve_session_id() does not read PIPELINE_STATE_FILE itself."
        )


DISCOVERY_REPAIR_POLARITY = (
    "A member that stops being discovered is a CLAIM that this coordinator no "
    "longer has a sentinel surface. RE-MEASURE it (state_file_reads, "
    "resolve_calls_missing_sentinel_path, handrolled_resolvers, the raw /tmp "
    "literal scan) and pin the new numbers. DELETING the entry from "
    "ALL_COORDINATORS to green this test is FORBIDDEN — it retires every arm "
    "covering that file."
)


class TestCoordinatorCoverageIsMechanical:
    """FIX 3 — the coordinator list is machine-checkable, not hand-maintained.

    Predicated on file CONTENT, never on filename. A glob (``implement*.md``)
    is an exclusion list wearing a prefix: a future ``pipeline-fix.md`` or
    ``drain-fix.md`` carrying sentinel logic sits silently outside it, and the
    repair when it bites is to widen the glob — a hand-maintained thing
    wearing a different hat, for the fifth time.
    """

    def test_discovery_equals_the_declared_list(self) -> None:
        discovered = discover_coordinators(COMMANDS_DIR)
        declared = set(ALL_COORDINATORS)
        missing_from_list = discovered - declared
        missing_from_disk = declared - discovered
        assert discovered == declared, (
            "coordinator coverage drifted.\n"
            f"  on disk but NOT in ALL_COORDINATORS: "
            f"{sorted(p.name for p in missing_from_list)}\n"
            f"  in ALL_COORDINATORS but NOT discovered: "
            f"{sorted(p.name for p in missing_from_disk)}\n"
            + DISCOVERY_REPAIR_POLARITY
        )

    def test_call_site_inventory_covers_exactly_the_declared_list(self) -> None:
        """``EXPECTED_SENTINEL_PATH_CALLS`` is the LAST hand-maintained list here.

        It survived FIX 3 by being a dict instead of a list — one level below
        the three lists that fix eliminated, and never pinned against
        ``ALL_COORDINATORS``. Two silent failures without this arm:

        * A FIFTH coordinator joins ``ALL_COORDINATORS`` (via the mechanical
          discovery arm above) and ``test_resolve_session_id_call_sites_are
          _pinned`` dies on a bare ``KeyError`` at the dict lookup — an ERROR
          carrying none of ``DISCOVERY_REPAIR_POLARITY``'s guidance about what
          to re-measure.
        * A coordinator is RENAMED and its stale key sits here forever,
          asserting nothing about anything.

        Both directions are named because a one-directional check is how the
        first three lists drifted.
        """
        declared = {p.name for p in ALL_COORDINATORS}
        inventoried = set(EXPECTED_SENTINEL_PATH_CALLS)
        assert inventoried == declared, (
            "EXPECTED_SENTINEL_PATH_CALLS drifted from ALL_COORDINATORS.\n"
            f"  in ALL_COORDINATORS but NOT inventoried: "
            f"{sorted(declared - inventoried)}\n"
            f"  inventoried but NOT in ALL_COORDINATORS: "
            f"{sorted(inventoried - declared)}\n"
            "MEASURE the new member's canonical resolve_session_id("
            "sentinel_path=…) call sites and add the count; deleting a key to "
            "green this retires that file's pin."
        )

    def test_call_site_inventory_pin_is_refused_when_it_drifts(self) -> None:
        """REFUSE arm for the pin above, in BOTH directions.

        A DIFFERENT shape from the arm's subject: the live dict is not
        mutated, two synthetic inventories are compared against a synthetic
        declared set, so the control cannot pass by accident of the live
        files happening to agree.
        """
        declared = {"a.md", "b.md"}
        assert set({"a.md": 1}) != declared, "a MISSING key must be refused"
        stale = {"a.md": 1, "b.md": 0, "stale.md": 2}
        assert set(stale) != declared, "a STALE key must be refused"
        exact = {"a.md": 1, "b.md": 0}
        assert set(exact) == declared, "PERMIT: an exactly-matching inventory is accepted"

    def test_unreadable_command_files_are_surfaced_not_swallowed(self) -> None:
        """An unreadable file is NOT a coordinator — but it is NAMED."""
        bad = unreadable_command_files(COMMANDS_DIR)
        assert bad == [], (
            f"unreadable commands/*.md files were skipped by "
            f"discover_coordinators and would be an invisible coverage hole: "
            f"{bad}"
        )

    def test_non_implement_prefixed_file_is_discovered(self, tmp_path: Path) -> None:
        """REFUSE arm — the arm a filename glob could not pass.

        ``pipeline-fix.md`` does not start with ``implement``. Content is the
        predicate, so it is returned.
        """
        d = tmp_path / "commands"
        d.mkdir()
        rogue = d / "pipeline-fix.md"
        rogue.write_text(
            "# /pipeline-fix\n\n```bash\n"
            "python3 -c \"import os; p = os.environ.get('PIPELINE_STATE_FILE')\"\n"
            "```\n"
        )
        assert discover_coordinators(d) == {rogue}

    def test_second_token_alone_is_enough(self, tmp_path: Path) -> None:
        """Either token qualifies — not just the first one."""
        d = tmp_path / "commands"
        d.mkdir()
        rogue = d / "drain-fix.md"
        rogue.write_text("```python\nsid = resolve_session_id(sentinel_path=None)\n```\n")
        assert discover_coordinators(d) == {rogue}

    def test_unrelated_sibling_is_not_over_matched(self, tmp_path: Path) -> None:
        """NON-OVER-MATCH arm — synthetic."""
        d = tmp_path / "commands"
        d.mkdir()
        (d / "notes.md").write_text("# Notes\n\nNo sentinel tokens here at all.\n")
        assert discover_coordinators(d) == set()

    def test_live_non_coordinator_is_not_over_matched(self) -> None:
        """NON-OVER-MATCH arm — against the LIVE commands dir.

        Measured: exactly 4 of the 26 commands/*.md files carry either token.
        ``improve.md`` is a real, substantial command that does not.
        """
        discovered = discover_coordinators(COMMANDS_DIR)
        assert (COMMANDS_DIR / "improve.md") not in discovered
        assert len(list(COMMANDS_DIR.glob("*.md"))) > len(discovered)


# ---------------------------------------------------------------------------
# 2. FIX 3 — no /tmp sentinel default; export retained
# ---------------------------------------------------------------------------


class TestSentinelPathDefault:
    @pytest.mark.parametrize("doc", ALL_COORDINATORS, ids=COORDINATOR_IDS)
    def test_no_tmp_literal_default_remains(self, doc: Path) -> None:
        """All four coordinators, not just the one the defect was found in.

        WAIVED from the resume subject-size pin, deliberately: this arm's
        subject is the RAW FULL FILE, not a fence extract. It scans 100% of
        implement-resume.md's bytes and finds 0 hits, so it cannot be
        green-on-unread and no subject-size pin can strengthen it.

        Scoped to IMPLEMENT_MD alone, this passed while
        ``implement-batch.md:494`` still ran
        ``rm -- "${PIPELINE_STATE_FILE:-/tmp/implement_pipeline_state.json}"``
        on every batch merge — deleting a file that does not exist while the
        real per-repo sentinel accumulated under ``.claude/local/``. The
        sibling ``TestSessionIdResolver`` already parametrised over both docs
        for a materially identical shape; this class did not.
        """
        offenders = [
            f"{doc.name}:{lineno}: {line.strip()}"
            for lineno, line in enumerate(doc.read_text().splitlines(), 1)
            if "/tmp/implement_pipeline_state.json" in line
        ]
        assert offenders == [], (
            "machine-global /tmp sentinel literal survives; the canonical "
            "default is get_legacy_sentinel_path() "
            "(<repo>/.claude/local/implement_pipeline_state.json). Offenders:\n"
            + "\n".join(offenders)
        )

    def test_synthetic_tmp_default_is_refused(self) -> None:
        """REFUSE arm — a doc with the old literal fails the same check."""
        total, sanctioned, no_default = state_file_reads(FIXTURE_TMP_LITERAL_DEFAULT)
        assert total == 1
        assert sanctioned + no_default == 0, (
            "the /tmp literal must NOT be classified as a sanctioned form"
        )
        assert "/tmp/implement_pipeline_state.json" in FIXTURE_TMP_LITERAL_DEFAULT

    def test_export_pipeline_state_file_is_retained(self) -> None:
        """The producer of a PROTECTED variable must not be deleted."""
        text = IMPLEMENT_MD.read_text()
        assert text.count("export PIPELINE_STATE_FILE") == 1
        assert 'mkdir -p "$(dirname "$PIPELINE_STATE_FILE")"' in text, (
            "atomic_write_json requires the parent directory to exist"
        )
        sys.path.insert(0, str(HOOK_DIR))
        sys.path.insert(0, str(LIB_DIR))
        import unified_pre_tool as upt

        assert "PIPELINE_STATE_FILE" in upt.PROTECTED_ENV_VARS


# ---------------------------------------------------------------------------
# 3. FIX 1b — one canonical resolver, sentinel_path= always passed
# ---------------------------------------------------------------------------


class TestSessionIdResolver:
    @pytest.mark.parametrize("doc", ALL_COORDINATORS, ids=COORDINATOR_IDS)
    def test_zero_handrolled_resolvers(self, doc: Path) -> None:
        assert handrolled_resolvers(doc.read_text()) == 0

    def test_synthetic_handrolled_resolver_is_refused(self) -> None:
        """REFUSE arm, different shape from the live doc."""
        assert handrolled_resolvers(FIXTURE_HANDROLLED_RESOLVER) == 1

    @pytest.mark.parametrize("doc", ALL_COORDINATORS, ids=COORDINATOR_IDS)
    def test_every_call_passes_sentinel_path(self, doc: Path) -> None:
        bad = resolve_calls_missing_sentinel_path(doc.read_text())
        assert bad == [], (
            f"{doc.name}: resolve_session_id() called without sentinel_path=. "
            "The helper does not read PIPELINE_STATE_FILE itself, so omitting "
            f"it silently drops env honouring. Offenders: {bad}"
        )

    def test_synthetic_bare_call_is_refused(self) -> None:
        assert resolve_calls_missing_sentinel_path(FIXTURE_BARE_RESOLVE_CALL) == [
            "resolve_session_id("
        ]

    def test_canonical_helper_exists_with_the_documented_keyword(self) -> None:
        """The doc instructs a real API — verify the surface, do not assume it."""
        import inspect

        sys.path.insert(0, str(LIB_DIR))
        import pipeline_completion_state as pcs

        sig = inspect.signature(pcs.resolve_session_id)
        assert "sentinel_path" in sig.parameters
        assert sig.parameters["sentinel_path"].kind is inspect.Parameter.KEYWORD_ONLY
        assert sig.parameters["sentinel_path"].default is None


class TestNonAtomicSentinelWrite:
    """Truncation-on-open is file-shape-independent, so this parametrizes."""

    @pytest.mark.parametrize("doc", ALL_COORDINATORS, ids=COORDINATOR_IDS)
    def test_no_non_atomic_sentinel_write(self, doc: Path) -> None:
        count = non_atomic_sentinel_writes(doc.read_text())
        assert count == 0, (
            f"{doc.name}: {count} non-atomic sentinel write(s). open(path,'w') "
            "truncates at OPEN time — a kill between the open and the "
            "json.dump leaves a 0-byte sentinel with the prior content already "
            "gone (#1384). Use atomic_write_json(Path(...), state)."
        )

    def test_both_synthetic_shapes_are_refused(self) -> None:
        """REFUSE arms, two DIFFERENT shapes."""
        assert non_atomic_sentinel_writes(FIXTURE_OPEN_W_WRITE) == 1
        assert non_atomic_sentinel_writes(FIXTURE_WRITE_TEXT_WRITE) == 1

    def test_variable_indirected_write_is_refused(self) -> None:
        """REFUSE arm for the shape the ORIGINAL pattern could not see.

        The pre-widening regex matched an inline ``open(os.environ.get(...),
        'w')`` plus the two hardcoded names ``sentinel`` and ``state_path``.
        Parking the resolved path in a local named ``p`` evaded all three
        while being the identical truncate-at-open bug — the defect class this
        module exists to close, applied to this module's own guard.

        Captured RED before the widening: this assertion read ``0 == 1``.
        """
        assert non_atomic_sentinel_writes(FIXTURE_VARIABLE_INDIRECTED_WRITE) == 1

    def test_variable_indirected_write_text_is_refused(self) -> None:
        """The same evasion through ``write_text`` on an unenumerated name.

        Proves the widening removed the name ENUMERATION rather than growing
        it: ``psf`` is in no list anywhere.
        """
        assert non_atomic_sentinel_writes(FIXTURE_INDIRECTED_WRITE_TEXT) == 1

    def test_legitimate_non_sentinel_write_is_permitted(self) -> None:
        """PERMIT arm — the over-capture control for the widening.

        A guard that refuses every ``open(<var>, 'w')`` would refuse
        implement.md's live ``log_file``/``ack_file`` writes and be deleted
        within a week. The scoping is DATAFLOW, not name shape: only a name
        BOUND to ``PIPELINE_STATE_FILE`` or ``get_legacy_sentinel_path()`` in
        the same body is refused.
        """
        assert non_atomic_sentinel_writes(FIXTURE_LEGITIMATE_NON_SENTINEL_WRITE) == 0


class TestResumeZeroSubjectPins:
    """implement-resume.md is a ZERO-SUBJECT member, pinned as such.

    Every universal arm above passes on resume against a subject of size zero.
    They would be green against a completely broken guard. They are NOT "the
    discriminating GREEN control" — calling them that is the same false claim
    of completeness this module exists to remove. So the zeros are pinned as
    MEASURED numbers: the moment resume gains a state block they go RED and
    force a decision at exactly the point the next recurrence would otherwise
    be born.
    """

    def test_executable_fence_subject_size_is_pinned(self) -> None:
        """The subject-size pin covering the three fence-scoped resume arms.

        (``test_zero_handrolled_resolvers[resume]``,
        ``test_every_call_passes_sentinel_path[resume]``,
        ``test_no_non_atomic_sentinel_write[resume]`` all read
        ``executable_text(resume)``.)

        MEASURED: 3 bash fences at implement-resume.md:85,110,119; zero
        indented, zero python. A MEASURED number, not a boolean non-empty
        probe — a non-empty probe passes in exactly the situation it exists to
        catch, because resume's executable text IS non-empty while all its
        arms are simultaneously zero-subject.
        """
        assert len(executable_fences(RESUME_MD.read_text())) == 3

    def test_state_file_reads_are_zero(self) -> None:
        """MEASURED (0,0,0).

        HONEST CAVEAT — this pin is weaker than it looks. ``_PSF_ANY`` matches
        only the PYTHON ``os.environ.get('PIPELINE_STATE_FILE'…)`` form. A
        future author implementing resume's own instruction at
        implement-resume.md:65 ("Restore ``PIPELINE_STATE_FILE`` env var…") as
        a SHELL ``export`` leaves this pin GREEN. :65 is exactly the text such
        an author would be implementing.
        """
        assert state_file_reads(RESUME_MD.read_text()) == (0, 0, 0)

    def test_zero_resolve_session_id_calls_in_executable_text(self) -> None:
        """The companion pin, and this one IS well-aimed.

        implement-resume.md:64 already instructs
        ``get_completed_agents(session_id, run_id=run_id)`` in prose; the
        natural implementation resolves a session id, which fires this.
        """
        assert executable_text(RESUME_MD.read_text()).count("resolve_session_id(") == 0

    def test_canonical_per_run_state_path_is_not_the_guarded_literal(self) -> None:
        """resume's /tmp references are CORRECT and must not be 'fixed'.

        ``/tmp/pipeline_state_<run_id>.json`` is the canonical PER-RUN path
        from ``pipeline_state.get_state_path`` — a measurably DIFFERENT file
        from ``get_legacy_sentinel_path()``'s
        ``<repo>/.claude/local/implement_pipeline_state.json``. A blanket
        /tmp-literal sweep would break resume.

        THE MODULE'S "PIN AN EXACT NUMBER, NEVER ``>= 1``" RULE IS WAIVED
        HERE, deliberately and only here. That rule exists to stop an
        EXTRACTOR silently matching zero and reporting a clean doc. There is
        no extractor on this line — it is a raw ``str.count`` on whole-file
        text, which has nothing to drift. What the exact ``== 3`` DID pin was
        a count of PROSE occurrences: MEASURED, all three sit at
        implement-resume.md:33, :54 and :65 and NONE is inside a fence::

            grep -n '/tmp/pipeline_state_<run_id>.json' \\
                plugins/autonomous-dev/commands/implement-resume.md

        So rewording resume's documentation turned this regression test red
        with zero behavioural change — a pin on wording, wearing the costume
        of a contract. ``>= 1`` keeps the load-bearing property (the canonical
        per-run path is still NAMED, so a future sweep sees it is deliberate)
        and drops the churn.

        The discriminating assertion is the second one, and it is unchanged.
        """
        text = RESUME_MD.read_text()
        assert text.count("/tmp/pipeline_state_<run_id>.json") >= 1, (
            "resume must still NAME the canonical per-run path, so a future "
            "/tmp-literal sweep can tell it apart from the guarded legacy "
            "sentinel literal."
        )
        assert "/tmp/implement_pipeline_state.json" not in text


# ---------------------------------------------------------------------------
# 4. FIX 1 — the STEP 0 sentinel write is atomic (behavioural, both arms)
# ---------------------------------------------------------------------------

STEP0_ANCHOR = "state = sign_state(state, sid)"
KNOWN_GOOD = {"session_id": "prior-owner", "run_id": "prior", "mode": "full"}


@pytest.fixture
def step0_repo(tmp_path: Path):
    """A synthetic repo whose ``.claude/lib`` is the REAL lib directory.

    A real repo cannot be given a read-only ``.claude/local/`` — hence the
    synthetic tree. Nothing about the write path is stubbed: the block imports
    the genuine ``pipeline_state`` and ``pipeline_completion_state``.
    """
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "lib").symlink_to(LIB_DIR, target_is_directory=True)
    # NOT ``.claude/local``. Measured: the block's
    # ``os.environ.get('PIPELINE_STATE_FILE', str(get_legacy_sentinel_path()))``
    # evaluates the default EAGERLY, and get_legacy_sentinel_path() chmods
    # <repo>/.claude/local back to 0o700 as a side effect — which silently
    # undid the read-only refuse arm and made it pass for BOTH implementations.
    # A sibling directory keeps the permission control discriminating.
    local = repo / ".claude" / "ro_state"
    local.mkdir()
    sentinel = local / "implement_pipeline_state.json"
    sentinel.write_text(json.dumps(KNOWN_GOOD))

    run_id = "t" + uuid.uuid4().hex[:12]
    session_id = "sess-" + uuid.uuid4().hex[:12]
    yield repo, local, sentinel, run_id, session_id

    # Consecutive-run isolation: record_run_start writes real /tmp state.
    digest = hashlib.sha256(session_id.encode()).hexdigest()[:8]
    for pattern in (
        f"/tmp/pipeline_agent_completions_{run_id}*",
        f"/tmp/pipeline_agent_completions_{digest}*",
    ):
        for stale in glob.glob(pattern):
            try:
                os.unlink(stale)
            except OSError:
                pass
    try:
        local.chmod(0o700)
    except OSError:
        pass


def _run_coordinator_block(
    doc: Path,
    anchor: str,
    repo: Path,
    *,
    sentinel: Path | None = None,
    run_id: str,
    session_id: str,
):
    """Materialise and execute the ``python3 -c`` block of ``doc`` containing
    ``anchor``, in a subprocess rooted at ``repo``.

    ``sentinel=None`` means the child MUST NOT see ``PIPELINE_STATE_FILE`` at
    all. The body builds ``env`` from ``dict(os.environ)``, so merely not
    SETTING the variable would INHERIT it — and if the session that launched
    pytest has it set, the arm would write to the LIVE sentinel and its own
    name would be false. Hence the explicit ``pop``.

    The three ``.replace()`` substitutions are unconditional. Verified safe:
    implement-fix.md's state-init block carries none of those placeholders, so
    all three are no-ops on that path — no branching needed.
    """
    block = extract_python_c_block(doc.read_text(), anchor)
    src = (
        block.replace("$(date +%Y-%m-%dT%H:%M:%S)", "2026-09-05T00:00:00")
        .replace("$RUN_ID", run_id)
        .replace("'MODE'", "'full'")
    )
    script = repo / "coordinator_block.py"
    script.write_text(src)
    env = dict(os.environ)
    if sentinel is None:
        env.pop("PIPELINE_STATE_FILE", None)
    else:
        env["PIPELINE_STATE_FILE"] = str(sentinel)
    env["CLAUDE_SESSION_ID"] = session_id
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _run_step0(repo: Path, sentinel: Path, run_id: str, session_id: str):
    """Materialise and execute implement.md's STEP 0 sentinel block."""
    return _run_coordinator_block(
        IMPLEMENT_MD,
        STEP0_ANCHOR,
        repo,
        sentinel=sentinel,
        run_id=run_id,
        session_id=session_id,
    )


def test_step0_block_is_extractable_and_uses_atomic_write() -> None:
    """Guards the extractor for the two behavioural tests below."""
    block = extract_python_c_block(IMPLEMENT_MD.read_text(), STEP0_ANCHOR)
    assert "atomic_write_json(" in block
    assert non_atomic_sentinel_writes(block) == 0
    assert "```" not in block


def test_step0_write_permit_arm(step0_repo) -> None:
    """PERMIT arm: a writable directory produces a valid signed sentinel."""
    repo, _local, sentinel, run_id, session_id = step0_repo
    proc = _run_step0(repo, sentinel, run_id, session_id)
    assert proc.returncode == 0, proc.stderr

    written = json.loads(sentinel.read_text())
    assert written["session_id"] == session_id
    assert written["run_id"] == run_id
    assert written["mode"] == "full"
    assert written["explicitly_invoked"] is True
    # #1384: a genuine STEP-0 sentinel carries run_id/mode/explicitly_invoked,
    # so _is_pipeline_active() classifies it ACTIVE.
    assert any(written.get(k) for k in ("run_id", "mode", "explicitly_invoked"))
    assert "hmac" in written or "signature" in written or "nonce" in written


def test_step0_write_leaves_no_orphan_tmp(step0_repo) -> None:
    """atomic_write_json unlinks its temp file on both paths."""
    repo, local, sentinel, run_id, session_id = step0_repo
    proc = _run_step0(repo, sentinel, run_id, session_id)
    assert proc.returncode == 0, proc.stderr
    leftovers = [p.name for p in local.iterdir() if p.name != sentinel.name]
    assert leftovers == [], f"orphaned temp files: {leftovers}"


def test_step0_write_is_atomic_dir_readonly(step0_repo) -> None:
    """REFUSE arm: a non-writable PARENT directory must leave the prior
    sentinel byte-identical, never 0 bytes.

    Measured to discriminate: ``open(path, 'w')`` succeeds and truncates
    (the FILE is still writable) while ``mkstemp(dir=d)`` raises
    ``PermissionError``.
    """
    if _IS_ROOT:
        pytest.skip(_ROOT_SKIP)

    repo, local, sentinel, run_id, session_id = step0_repo
    before = sentinel.read_bytes()
    assert before, "fixture must seed known-good content"

    local.chmod(0o500)  # r-x: file stays writable, directory does not accept new entries
    try:
        proc = _run_step0(repo, sentinel, run_id, session_id)
    finally:
        local.chmod(0o700)

    assert proc.returncode != 0, (
        "a pipeline that cannot write its own sentinel MUST NOT proceed silently"
    )
    assert "PermissionError" in proc.stderr, proc.stderr
    after = sentinel.read_bytes()
    assert after == before, "prior sentinel content was destroyed"
    assert after != b"", "sentinel was truncated to 0 bytes"


# ---------------------------------------------------------------------------
# 4b. The ONE fix-mode behavioural pair (1g)
#
# Acceptance criterion 2 is otherwise purely textual — nothing would prove
# implement-fix.md's state-init block EXECUTES, and wiring is precisely what
# broke. This is deliberately a sibling PAIR, not a blanket parametrize over
# ALL_COORDINATORS: STEP0_ANCHOR is unique to implement.md and fix mode's
# block has a different shape and no signing.
# ---------------------------------------------------------------------------

FIX_STEP0_ANCHOR = "'mode': 'fix'"


@pytest.fixture
def fix_state_repo(tmp_path: Path):
    """A synthetic repo with NO ``.claude/local/`` — the block must create it.

    The ``.claude/lib`` symlink is REQUIRED and is not decoration: the
    bootstrap the block carries walks
    ``('.claude/lib', 'plugins/autonomous-dev/lib', '~/.claude/lib')``, and
    ``~/.claude/lib/pipeline_state.py`` EXISTS on a deployed machine. Omit the
    symlink and this arm silently proves the DEPLOYED library rather than this
    repo's.
    """
    repo = tmp_path / "fixrepo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "lib").symlink_to(LIB_DIR, target_is_directory=True)

    # This fixture is the ONE that lets the block resolve its own root: the
    # permit arm passes ``sentinel=None`` so ``get_legacy_sentinel_path()``
    # calls ``find_project_root()``, which searches for ``.git`` ALL THE WAY
    # UP before it will settle for the nearest ``.claude``
    # (path_utils.find_project_root, "Prioritizes .git over .claude").
    #
    # So if ``TMPDIR`` points inside a real checkout, the child writes its
    # sentinel into THAT repo's ``.claude/local/`` and the arm's own name
    # becomes false. Assert the precondition rather than assume it — resolved,
    # because macOS ``tmp_path`` sits under a symlinked ``/var``.
    resolved = repo.resolve()
    enclosing_git = [p for p in resolved.parents if (p / ".git").exists()]
    assert not enclosing_git, (
        f"tmp_path is inside a git checkout ({enclosing_git[0] if enclosing_git else ''}); "
        "find_project_root() would resolve the child's repo root to it and the "
        "sentinel would be written into a REAL repository. Point TMPDIR "
        "outside any checkout."
    )

    run_id = "t" + uuid.uuid4().hex[:12]
    session_id = "sess-" + uuid.uuid4().hex[:12]
    yield repo, run_id, session_id

    digest = hashlib.sha256(session_id.encode()).hexdigest()[:8]
    for pattern in (
        f"/tmp/pipeline_agent_completions_{run_id}*",
        f"/tmp/pipeline_agent_completions_{digest}*",
    ):
        for stale in glob.glob(pattern):
            try:
                os.unlink(stale)
            except OSError:
                pass


def test_fix_state_block_is_extractable_and_uses_atomic_write() -> None:
    """Guards the extractor for the behavioural pair below."""
    text = FIX_MD.read_text()
    assert text.count(FIX_STEP0_ANCHOR) == 1, (
        "the fix-mode state-init anchor must be unique; found "
        f"{text.count(FIX_STEP0_ANCHOR)}"
    )
    block = extract_python_c_block(text, FIX_STEP0_ANCHOR)
    assert "atomic_write_json(" in block
    assert non_atomic_sentinel_writes(block) == 0
    assert "```" not in block


def test_fix_state_write_permit_arm(fix_state_repo) -> None:
    """PERMIT arm, ``PIPELINE_STATE_FILE`` UNSET (popped, not merely unset).

    This is the arm that pins the load-bearing precondition. ``atomic_write_json``
    requires the parent directory to EXIST and raises ``OSError`` from
    ``mkstemp`` if not. implement.md satisfies that by pairing
    ``export PIPELINE_STATE_FILE`` with ``mkdir -p "$(dirname …)"``.
    implement-fix.md has NEITHER — its precondition rests entirely on
    ``get_legacy_sentinel_path()``'s best-effort mkdir being evaluated EAGERLY
    as the ``.get()`` default. That works, but it is load-bearing,
    cwd-dependent and was undocumented. This asserts it.

    Discriminating: the pre-fix block resolved to ``/tmp/implement_pipeline_state.json``,
    so nothing appeared under the repo at all.
    """
    repo, run_id, session_id = fix_state_repo
    assert not (repo / ".claude" / "local").exists(), "fixture must start with no local/"

    proc = _run_coordinator_block(
        FIX_MD, FIX_STEP0_ANCHOR, repo, sentinel=None, run_id=run_id, session_id=session_id
    )
    assert proc.returncode == 0, proc.stderr

    written_path = repo / ".claude" / "local" / "implement_pipeline_state.json"
    assert written_path.exists(), (
        "the eager get_legacy_sentinel_path() default did not create "
        f"<repo>/.claude/local/. stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    written = json.loads(written_path.read_text())
    assert written["mode"] == "fix"
    assert written["explicitly_invoked"] is True


def test_fix_state_write_is_atomic_dir_readonly(fix_state_repo) -> None:
    """REFUSE arm: a read-only SIBLING parent directory.

    A sibling (``.claude/ro_state``), not ``.claude/local``, for the reason
    documented on ``step0_repo``: ``get_legacy_sentinel_path()`` chmods
    ``.claude/local`` back to 0o700 as a side effect and silently
    un-discriminates the control.
    """
    if _IS_ROOT:
        pytest.skip(_ROOT_SKIP)

    repo, run_id, session_id = fix_state_repo
    local = repo / ".claude" / "ro_state"
    local.mkdir()
    sentinel = local / "implement_pipeline_state.json"
    sentinel.write_text(json.dumps(KNOWN_GOOD))
    before = sentinel.read_bytes()
    assert before, "fixture must seed known-good content"

    local.chmod(0o500)
    try:
        proc = _run_coordinator_block(
            FIX_MD,
            FIX_STEP0_ANCHOR,
            repo,
            sentinel=sentinel,
            run_id=run_id,
            session_id=session_id,
        )
    finally:
        local.chmod(0o700)

    assert proc.returncode != 0, (
        "a pipeline that cannot write its own sentinel MUST NOT proceed silently"
    )
    assert "PermissionError" in proc.stderr, proc.stderr
    after = sentinel.read_bytes()
    assert after == before, "prior sentinel content was destroyed"
    assert after != b"", "sentinel was truncated to 0 bytes"


def test_write_text_shape_is_also_rejected() -> None:
    """DIFFERENT-SHAPE control.

    The observed bug was ``open(..., 'w')``. This control is ``write_text``
    (#1512's mechanism) — a guard that only recognised the reproducer's shape
    would pass the live doc and this fixture alike.
    """
    assert non_atomic_sentinel_writes(FIXTURE_WRITE_TEXT_WRITE) == 1
    assert non_atomic_sentinel_writes(FIXTURE_OPEN_W_WRITE) == 1
    assert non_atomic_sentinel_writes(IMPLEMENT_MD.read_text()) == 0


def test_heartbeat_recovery_write_is_atomic() -> None:
    """The code that REPAIRS sentinels must not be able to corrupt one."""
    src = (LIB_DIR / "pipeline_completion_state.py").read_text()
    assert "sentinel.write_text(" not in src
    assert "atomic_write_json(sentinel, recovered_sentinel, indent=2)" in src


def test_unreadable_sentinel_is_distinguishable_from_absent(tmp_path) -> None:
    """A sentinel that EXISTS but does not parse names itself in the log;
    a merely-absent one stays silent."""
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_bytes(b"")  # the observed 0-byte shape
    absent = tmp_path / "absent.json"

    def _probe(path: Path) -> str:
        code = (
            f"import sys; sys.path.insert(0, {str(LIB_DIR)!r})\n"
            "from pipeline_completion_state import resolve_session_id\n"
            f"resolve_session_id(sentinel_path={str(path)!r})\n"
        )
        env = dict(os.environ)
        env.pop("CLAUDE_SESSION_ID", None)
        return subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True,
            env=env, cwd=str(tmp_path), timeout=60,
        ).stderr

    corrupt_err = _probe(corrupt)
    absent_err = _probe(absent)
    assert "[SENTINEL-UNREADABLE]" in corrupt_err, corrupt_err
    assert str(corrupt) in corrupt_err
    assert "[SENTINEL-UNREADABLE]" not in absent_err, absent_err


# ---------------------------------------------------------------------------
# 5. FIX 4 — filing routes through the issue-creator agent
# ---------------------------------------------------------------------------


class TestGhIssueCreateDocConformance:
    """Secondary evidence. The PROOF is the runtime pair below."""

    def test_zero_gh_issue_create_in_any_bash_fence(self) -> None:
        assert gh_issue_create_in_bash_fences(IMPLEMENT_MD.read_text()) == 0

    def test_synthetic_bash_fence_occurrence_is_refused(self) -> None:
        """REFUSE arm for this very check."""
        assert gh_issue_create_in_bash_fences(FIXTURE_TWO_GH_IN_BASH) == 2

    def test_step8_pre_existing_failure_path_names_issue_creator(self) -> None:
        text = IMPLEMENT_MD.read_text()
        line = next(
            ln for ln in text.splitlines() if "pre-existing-failure" in ln
        )
        assert "issue-creator" in line, line
        assert "gh issue create" not in line

    def test_dedup_query_and_advisory_contract_survive(self) -> None:
        text = IMPLEMENT_MD.read_text()
        assert (
            "gh issue list --label security --label auto-improvement --state open --search"
            in text
        )
        assert "[ADVISORY-DEDUP-FAILED]" in text
        assert "[ADVISORY-FILE-FAILED]" in text
        assert "[ADVISORY-MALFORMED]" in text

    def test_all_three_filing_sites_dispatch_issue_creator(self) -> None:
        text = IMPLEMENT_MD.read_text()
        assert text.count('subagent_type="issue-creator"') == 3


def _gate_verdict(command: str, *, agent: str | None, tmp_path: Path) -> str:
    """Call the REAL hook gate in a fresh process with controlled inputs.

    Nothing is mocked: the sentinel and command-context paths are pointed at
    files that do not exist, so ``_is_pipeline_active()`` and
    ``_is_issue_command_active()`` return False through their own logic.
    """
    env = dict(os.environ)
    env["PIPELINE_STATE_FILE"] = str(tmp_path / "no_such_sentinel.json")
    env["GH_ISSUE_CMD_CONTEXT_PATH"] = str(tmp_path / "no_such_context.json")
    env.pop("CLAUDE_AGENT_NAME", None)
    if agent is not None:
        env["CLAUDE_AGENT_NAME"] = agent
    code = (
        f"import sys; sys.path[:0] = [{str(HOOK_DIR)!r}, {str(LIB_DIR)!r}]\n"
        "import unified_pre_tool as u\n"
        "assert u._is_pipeline_active() is False, 'precondition: pipeline must be INACTIVE'\n"
        "import json\n"
        "cmd = json.loads(sys.stdin.read())['command']\n"
        "r = u._detect_gh_issue_create(cmd)\n"
        "print('ALLOW' if r is None else 'DENY')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        input=json.dumps({"command": command}),
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


GH_CMD = 'gh issue create --title "[Security advisory] x" --body "y" --label security'
GH_SUBPROCESS_CMD = (
    "python3 -c \"import subprocess; "
    "subprocess.run(['gh','issue','create','--title','x','--body','y'])\""
)


def test_issue_creator_dispatch_is_allowed_with_pipeline_inactive(tmp_path) -> None:
    """PERMIT arm — the whole point of routing filing through the agent.

    ``_is_pipeline_active()`` is False (asserted as a precondition inside the
    subprocess), which is exactly the state a recovered sentinel produces for
    the rest of a run (#1384). The agent-identity allow-through still permits.
    """
    assert _gate_verdict(GH_CMD, agent="issue-creator", tmp_path=tmp_path) == "ALLOW"


def test_direct_coordinator_call_is_denied_with_pipeline_inactive(tmp_path) -> None:
    """REFUSE arm — same command, no agent context."""
    assert _gate_verdict(GH_CMD, agent=None, tmp_path=tmp_path) == "DENY"


def test_non_authorized_agent_is_denied(tmp_path) -> None:
    """Negative control on the identity: not just any agent gets through."""
    assert _gate_verdict(GH_CMD, agent="reviewer", tmp_path=tmp_path) == "DENY"


def test_subprocess_wrapped_form_is_also_denied(tmp_path) -> None:
    """DIFFERENT SHAPE — the bypass wrapper, not the bare command."""
    assert _gate_verdict(GH_SUBPROCESS_CMD, agent=None, tmp_path=tmp_path) == "DENY"


def test_unrelated_gh_command_is_not_gated(tmp_path) -> None:
    """Negative control on the DETECTOR: it does not flag everything."""
    assert _gate_verdict("gh issue list --state open", agent=None, tmp_path=tmp_path) == "ALLOW"


def test_issue_creator_is_the_sole_authorized_agent() -> None:
    """The doc instructs a mechanism that actually exists."""
    sys.path.insert(0, str(HOOK_DIR))
    sys.path.insert(0, str(LIB_DIR))
    import unified_pre_tool as upt

    assert upt.GH_ISSUE_AGENTS == {"issue-creator"}
    assert (REPO_ROOT / "plugins" / "autonomous-dev" / "agents" / "issue-creator.md").exists()
    manifest = json.loads(
        (REPO_ROOT / "plugins" / "autonomous-dev" / "install_manifest.json").read_text()
    )
    agent_files = manifest["components"]["agents"]["files"]
    assert any(f.endswith("/issue-creator.md") for f in agent_files), agent_files
