"""Subprocess-level regression tests for PreToolUseWrite-protect-sensitive.sh.

Issue #1587: this shell hook produced a valid deny payload on two paths and
recorded nothing, so every refusal it made was invisible in
``.claude/logs/hook-blocks.jsonl``. Zero rows meant *unmeasured*, not *never
fired*.

Issue #1588 (this pass): the guard was dead THREE independent ways and
permitted every write it claimed to block.

1. **Not registered.** No settings surface bound it to any lifecycle event, so
   it had never run in production despite shipping to every consumer repo via
   ``install_manifest.json``.
2. **Wrong payload key.** It read ``.parameters.file_path``; Claude Code sends
   ``.tool_input.file_path``. Against a real payload the variable was empty,
   every pattern missed, and the hook fell through to allow.
3. **Wrong envelope.** It emitted a bare top-level ``permissionDecision``,
   which Claude Code honours neither as ``hookSpecificOutput.
   permissionDecision`` nor as the legacy top-level ``{"decision": "block"}``.

Arms 2 and 3 were found under #1587, proved with both arms, and deliberately
pinned as characterization tests rather than fixed, because fixing them is a
POLICY change: it flips this hook from refusing nothing to enforcing a broad
pattern list. That policy change was confirmed by the repository owner and is
implemented here — see ``TestIssue1588PolicyChangeIsIntentional``, which pins
the NEW behaviour just as loudly as the old tests pinned the old.

The policy is no longer a single list. It splits:

* **DENY** — ``credentials``, ``secrets``, ``private.*key``, ``.pem``,
  ``.key``, ``.git/``. An agent has no business writing these.
* **ASK** — ``.env``, ``.env.*``, ``PROJECT.md``. A human legitimately edits
  these; the PROJECT.md rule's own reason text says "edit PROJECT.md
  manually". Stop the agent, let the human decide. A blanket deny cannot
  express that.

These tests drive the real hook as a subprocess, the way Claude Code would.
Assertions on the file's TEXT or its COMMENTS are worthless here: this hook
already shipped once with a correct-looking suite and a comment accurately
documenting arm 3. Every behavioural test below feeds a payload to the actual
script and asserts on its actual stdout, through the nested envelope key.

They are structured around the evidence rules #1587 establishes:

* the guard is watched REFUSING **and** PERMITTING, on **every** rule class
  (deny patterns, ask patterns, allow) — not just the one that prompted it;
* every probe has a positive and a negative control, so an empty result is
  distinguishable from a broken instrument;
* telemetry failure is exercised four ways, and each must degrade to
  "refused but unrecorded", never to "allowed".

The telemetry log is anchored at the temp repo root, so no test row can reach
the real ``.claude/logs/hook-blocks.jsonl``. ``CLAUDE_PROJECT_DIR`` is popped
from the inherited environment for exactly that reason: Claude Code sets it,
and inheriting it would redirect every test row into the live log.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "autonomous-dev"
HOOK_PATH = PLUGIN_ROOT / "hooks" / "PreToolUseWrite-protect-sensitive.sh"
LIB_DIR = PLUGIN_ROOT / "lib"
PERF_REPORT_PATH = REPO_ROOT / "scripts" / "hook_perf_report.py"

HOOK_NAME = "PreToolUseWrite-protect-sensitive.sh"
BLOCK_LOG_RELATIVE = Path(".claude") / "logs" / "hook-blocks.jsonl"

# The reference registration this hook's own registration is modelled on. Read
# dynamically from the surfaces rather than hardcoded, so the registration test
# below cross-validates two real files instead of a stale third copy.
REFERENCE_HOOK = "unified_pre_tool.py"

#: Tracked settings surfaces. Same two globs the #1612 reachability ratchet
#: walks; the untracked ``.claude/settings*.json`` files are machine-local and
#: would make this test green here and red in CI for the same commit.
SETTINGS_SURFACE_GLOBS = (
    "templates/settings*.json",
    "config/global_settings_template.json",
)

# Utilities the hook (and the subprocess launcher) need on PATH, minus
# python3. Used to build a curated PATH that proves the no-python3
# degradation path.
_HOOK_PATH_UTILITIES = ("bash", "cat", "jq", "grep", "dirname", "git", "env")

# Resolved once so PATH overrides in tests cannot hide the launcher itself.
BASH = shutil.which("bash") or "/bin/bash"

#: One shell comment, stripped before counting emitters. Prose that names a
#: decision must not be counted as a surface that emits one — that is the
#: comment-blindness failure the #1588 ratchet already has on record.
_SHELL_COMMENT = re.compile(r"(?<!\\)#.*$")

#: A surface that emits a REFUSING decision: ``permissionDecision`` paired with
#: a literal refusal value, with the shell variable the fused emitter
#: interpolates, or with a ``printf``/``jq`` substitution placeholder.
#:
#: The parameterised emitter is the whole point of the fix — a counter that
#: only knew the literal ``"deny"`` would read 0 against the new code and pass
#: for the wrong reason. The ``%s`` and ``$decision`` arms were added when the
#: emitter stopped being a heredoc: the payload is now rendered by ``printf``
#: with a ``jq``-escaped reason, so the decision reaches the wire as ``"%s"``.
#: Adding those arms makes the counter STRICTER, not laxer — a second printf
#: or jq emitter is now counted where before it would have been invisible.
_REFUSAL_EMITTER = re.compile(
    r'"permissionDecision"\s*:\s*'
    r'(?:"(?:deny|ask|%s|\$\{?decision\}?)"|\$\{?decision\}?\b)'
)


def _load_block_shapes() -> frozenset:
    """Read BLOCK_SHAPES from the real report script.

    Cross-validation, not a hardcoded copy: if the report's notion of which
    decision shapes count as blocks drifts, these tests move with it rather
    than assert against a stale third copy.
    """
    spec = importlib.util.spec_from_file_location(
        "_hook_perf_report_for_protect_sensitive_test", PERF_REPORT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BLOCK_SHAPES


def _read_block_rows(root: Path) -> list:
    """Return parsed telemetry rows under ``root``, or [] when absent."""
    log_path = root / BLOCK_LOG_RELATIVE
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _decision(result: subprocess.CompletedProcess) -> str:
    """Extract the decision from the hookSpecificOutput envelope.

    Issue #1588 arm 3: this hook used to emit a BARE top-level
    ``permissionDecision``, which Claude Code honours neither as
    ``hookSpecificOutput.permissionDecision`` (``unified_pre_tool.py:6302``)
    nor as the legacy top-level ``{"decision": "block"}`` (``:6273``), so every
    refusal it made was ignored and the write proceeded. It now emits the same
    envelope ``unified_pre_tool.py`` emits, and this reader asserts through
    that envelope on purpose: a reader that fell back to the top level would
    pass against the broken shape and prove nothing.

    Returns:
        The ``permissionDecision`` value, or ``"no output"`` when stdout is
        empty, or ``"no envelope"`` when the payload carries no
        ``hookSpecificOutput``.
    """
    if not result.stdout.strip():
        return "no output"
    emitted = json.loads(result.stdout)
    hook_specific = emitted.get("hookSpecificOutput")
    if not isinstance(hook_specific, dict):
        return "no envelope"
    return hook_specific.get("permissionDecision", "no decision")


def _init_repo(repo_dir: Path) -> Path:
    """Initialize ``repo_dir`` as a git repo and return its resolved path."""
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "--quiet", str(repo_dir)],
        check=True,
        capture_output=True,
    )
    return repo_dir.resolve()


def _run_hook(
    payload: dict | str,
    *,
    cwd: Path,
    env: dict | None = None,
) -> subprocess.CompletedProcess:
    """Invoke the hook as a subprocess with ``payload`` on stdin."""
    full_env = os.environ.copy()
    # Claude Code sets CLAUDE_PROJECT_DIR. Inheriting it would anchor every
    # test row at the REAL repo log. Pop it; tests that need it set it back.
    full_env.pop("CLAUDE_PROJECT_DIR", None)
    # Telemetry assertions require the recorder enabled.
    full_env.pop("HOOK_TELEMETRY_DISABLED", None)
    full_env.pop("HOOK_RECOVERY_DISABLED", None)
    if env:
        full_env.update(env)
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [BASH, str(HOOK_PATH)],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=full_env,
        timeout=30,
    )


def _write_payload(file_path: str, **extra) -> dict:
    """Build a payload in the shape Claude Code ACTUALLY sends.

    Issue #1588 arm 2: the hook used to read ``.parameters.file_path``, a key
    that appears in no real PreToolUse payload. Against a live write the
    variable was empty, every pattern grep missed, and the hook fell through
    to allow — a guard that could not refuse anything. It now reads
    ``.tool_input.file_path``, and this builder emits that shape so no test
    below can pass against a hook that reads the wrong field.

    Args:
        file_path: Value for ``tool_input.file_path``.
        **extra: Top-level payload fields (``tool_name``, ``session_id``).

    Returns:
        A PreToolUse payload dict.
    """
    payload: dict = {"tool_input": {"file_path": file_path}}
    payload.update(extra)
    return payload


def _count_refusal_emitters(text: str) -> int:
    """Count surfaces in a shell source that emit a REFUSING decision.

    Comments are stripped first: the hook's own prose names the envelope while
    describing it, and counting prose as a surface is the comment-blindness
    error one level down.

    Args:
        text: Shell source.

    Returns:
        Number of refusing-decision emission sites.
    """
    stripped = "\n".join(_SHELL_COMMENT.sub("", ln) for ln in text.splitlines())
    return len(_REFUSAL_EMITTER.findall(stripped))


#: A ``grep`` invocation and every short-flag cluster that follows it, up to
#: the first non-flag word (the pattern). Flags are parsed rather than searched
#: for, so a pattern containing the letter ``i`` cannot masquerade as ``-i``.
_GREP_INVOCATION = re.compile(r"\bgrep\b((?:\s+-[A-Za-z]+)*)")


def _greps_by_case(text: str) -> "dict[str, int]":
    """Count grep match sites in a shell source, split by case sensitivity.

    Comments are stripped first: the hook's header necessarily quotes the old
    case-sensitive invocation while explaining why it is gone, and counting
    prose as a match site is the comment-blindness error one level down.

    Args:
        text: Shell source.

    Returns:
        ``{"insensitive": n, "sensitive": n}`` — greps whose flag cluster
        carries ``i``, and those that do not.
    """
    stripped = "\n".join(_SHELL_COMMENT.sub("", ln) for ln in text.splitlines())
    counts = {"insensitive": 0, "sensitive": 0}
    for flag_text in _GREP_INVOCATION.findall(stripped):
        flags = set(flag_text.replace("-", " ").split())
        flags = {ch for token in flags for ch in token}
        counts["insensitive" if "i" in flags else "sensitive"] += 1
    return counts


def _settings_surfaces() -> "list[Path]":
    """Enumerate the tracked settings surfaces that can carry a registration."""
    found: "set[Path]" = set()
    for pattern in SETTINGS_SURFACE_GLOBS:
        for path in PLUGIN_ROOT.glob(pattern):
            if path.is_file():
                found.add(path)
    return sorted(found)


def _hooks_registered_under(surface: Path, event: str) -> "set[str]":
    """Return the hook script basenames registered under ``event``.

    Args:
        surface: A settings JSON file.
        event: Lifecycle event key (e.g. ``"PreToolUse"``).

    Returns:
        Set of script filenames appearing in that event's command strings.
    """
    try:
        data = json.loads(surface.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return set()
    names: "set[str]" = set()
    for group in hooks.get(event, []) or []:
        for entry in (group or {}).get("hooks", []) or []:
            command = entry.get("command", "")
            names.update(re.findall(r"[\w.\-]+\.(?:py|sh)", command))
    return names


class TestIssue1588HookIsRegistered:
    """ARM 1. The hook was bound to no lifecycle event and had never run."""

    def test_regression_issue_1588_registered_on_pretooluse_everywhere(self) -> None:
        """Every surface registering the reference hook must register this one.

        LIMITATION, stated rather than overclaimed: this asserts on CONFIG,
        not on behaviour. It proves the hook appears under a ``PreToolUse``
        key in the tracked settings surfaces. It does NOT prove Claude Code
        loads any of those surfaces, that the installed copy under
        ``.claude/hooks/`` matches, or that the hook actually executes on a
        write. Those are outside what a repository test can observe. The
        behavioural arm is every other test in this file, which drives the
        script directly with a real payload.

        The reference set is DERIVED (surfaces that register
        ``unified_pre_tool.py`` on ``PreToolUse``) rather than hardcoded, so a
        new template inherits the requirement instead of silently escaping it.
        """
        surfaces = _settings_surfaces()
        reference = [
            s
            for s in surfaces
            if REFERENCE_HOOK in _hooks_registered_under(s, "PreToolUse")
        ]
        # Premise: an empty reference set would make the loop below vacuous.
        assert len(reference) >= 5, (
            f"expected the reference hook {REFERENCE_HOOK} on PreToolUse in at "
            f"least 5 tracked surfaces, found {[p.name for p in reference]} "
            f"among {[p.name for p in surfaces]}. The instrument is broken, "
            f"not the repo."
        )
        missing = [
            s.name
            for s in reference
            if HOOK_NAME not in _hooks_registered_under(s, "PreToolUse")
        ]
        assert not missing, (
            f"{HOOK_NAME} is not registered on PreToolUse in {missing}. It "
            f"ships to every consumer repo via install_manifest.json, so an "
            f"unregistered hook is a guard that deploys everywhere and runs "
            f"nowhere (#1588 arm 1)."
        )

    def test_regression_issue_1588_registration_probe_discriminates(
        self, tmp_path: Path
    ) -> None:
        """NEGATIVE CONTROL for the probe above.

        A surface reader that returned every filename it saw, regardless of
        event, would pass the test above against a hook registered on
        ``Stop``. This feeds the reader a synthetic surface with the hook
        under the WRONG event and requires PreToolUse to come back empty.
        """
        payload = {
            "hooks": {
                "Stop": [
                    {
                        "matcher": "*",
                        "hooks": [{"command": f"bash /x/{HOOK_NAME}"}],
                    }
                ]
            }
        }
        probe = tmp_path / "settings.probe.json"
        probe.write_text(json.dumps(payload), encoding="utf-8")

        assert _hooks_registered_under(probe, "Stop") == {HOOK_NAME}, (
            "positive control: the reader must find the hook under the "
            "event it IS registered on"
        )
        assert _hooks_registered_under(probe, "PreToolUse") == set(), (
            "negative control: the reader reported a PreToolUse registration "
            "for a hook registered only on Stop, so it is not event-aware "
            "and the arm-1 test proves nothing"
        )


class TestIssue1587RefusalIsRecorded:
    """The refusal and its telemetry row must be one indivisible act."""

    def test_regression_issue_1587_sensitive_file_deny_writes_block_row(
        self, tmp_path: Path
    ) -> None:
        """A refused write to a sensitive file MUST emit one countable row."""
        repo = _init_repo(tmp_path / "repo")
        assert _read_block_rows(repo) == [], "temp repo must start with no rows"

        result = _run_hook(
            _write_payload(
                "app/credentials.json", tool_name="Write", session_id="sess-1587"
            ),
            cwd=repo,
        )

        assert result.returncode == 0, f"hook exited {result.returncode}: {result.stderr}"
        assert _decision(result) == "deny", f"stdout={result.stdout!r}"

        rows = _read_block_rows(repo)
        assert len(rows) == 1, f"expected exactly 1 telemetry row, got {len(rows)}"
        row = rows[0]
        assert row["hook_name"] == HOOK_NAME
        assert row["decision_shape"] in _load_block_shapes(), (
            f"decision_shape={row['decision_shape']!r} is not in BLOCK_SHAPES, "
            "so hook_perf_report.py would not count this refusal as a block"
        )
        assert "Cannot write to sensitive file" in row["reason"]
        assert "app/credentials.json" in row["reason"]
        assert row["metadata"]["rule"] == "sensitive_file_pattern"
        assert row["metadata"]["decision"] == "deny", (
            "the row must record WHICH decision was emitted so triage can "
            "tell an ask from a deny (#1588)"
        )
        assert row["metadata"]["tool_name"] == "Write"
        assert row["metadata"]["file_path"] == "app/credentials.json"
        assert row["metadata"]["envelope"] == "hookSpecificOutput.permissionDecision"
        assert row["session_id"] == "sess-1587"

    def test_regression_issue_1588_project_md_ask_writes_block_row(
        self, tmp_path: Path
    ) -> None:
        """The SECOND rule class must record too — and it is now ``ask``.

        Authored to a different shape than the reproducer on purpose: a guard
        proven only against the path that prompted it is scoped to that
        instance. The covered class is "every non-allow decision this hook can
        produce", and after #1588 that is two: ``deny`` and ``ask``.

        An ``ask`` is a refusal to proceed silently, so it belongs in
        ``hook-blocks.jsonl`` exactly as a deny does. It is recorded with
        ``decision_shape: "dict"`` — the shape of the printed JSON envelope —
        which IS a member of ``BLOCK_SHAPES``, so ``hook_perf_report.py``
        counts it as a block. The ACTUAL decision rides in
        ``metadata.decision`` so triage can separate the two classes.
        """
        repo = _init_repo(tmp_path / "repo")

        result = _run_hook(
            _write_payload(".claude/PROJECT.md", tool_name="Edit"),
            cwd=repo,
        )

        assert _decision(result) == "ask", f"stdout={result.stdout!r}"
        rows = _read_block_rows(repo)
        assert len(rows) == 1, f"expected exactly 1 telemetry row, got {len(rows)}"
        assert rows[0]["hook_name"] == HOOK_NAME
        assert rows[0]["metadata"]["rule"] == "project_md_protected"
        assert rows[0]["metadata"]["decision"] == "ask"
        assert rows[0]["decision_shape"] in _load_block_shapes(), (
            "an ask row must still be counted as a block by "
            "hook_perf_report.py — an unrecorded ask is an invisible refusal"
        )
        assert "PROJECT.md is protected" in rows[0]["reason"]

    def test_regression_issue_1588_env_ask_writes_block_row(
        self, tmp_path: Path
    ) -> None:
        """The ask-class PATTERN rule records too, not just PROJECT.md.

        ``.env`` moved from deny to ask under #1588. Both ask rules are
        exercised because they are separate branches in the hook, and a guard
        proven on one branch is scoped to that branch.
        """
        repo = _init_repo(tmp_path / "repo")

        result = _run_hook(
            _write_payload(".env", tool_name="Write", session_id="sess-1588"),
            cwd=repo,
        )

        assert _decision(result) == "ask", f"stdout={result.stdout!r}"
        rows = _read_block_rows(repo)
        assert len(rows) == 1, f"expected exactly 1 telemetry row, got {len(rows)}"
        assert rows[0]["metadata"]["rule"] == "human_editable_pattern"
        assert rows[0]["metadata"]["decision"] == "ask"
        assert rows[0]["session_id"] == "sess-1588"

    def test_regression_issue_1587_allow_writes_no_row(self, tmp_path: Path) -> None:
        """The PERMITTING arm: a permitted write must record nothing.

        This is the negative control for every count above. A recorder that
        also fired on allows would corrupt every number derived from the
        block log, and the refusing tests alone cannot detect that.
        """
        repo = _init_repo(tmp_path / "repo")

        result = _run_hook(
            _write_payload("src/app.py", tool_name="Write"),
            cwd=repo,
        )

        assert result.returncode == 0, f"hook exited {result.returncode}"
        assert _decision(result) == "allow", f"stdout={result.stdout!r}"
        assert _read_block_rows(repo) == [], "allow path must not write a row"

    def test_regression_issue_1587_row_anchored_at_repo_root_not_cwd(
        self, tmp_path: Path
    ) -> None:
        """A refusal issued from a subdirectory must record at the repo root.

        Without an explicit anchor the row lands in
        ``<subdir>/.claude/logs/``, invisible to every report that reads the
        repo's log. Same latent bug the reference fix (b984ad8c) corrected.
        """
        repo = _init_repo(tmp_path / "repo")
        subdir = repo / "deep" / "nested"
        subdir.mkdir(parents=True)

        result = _run_hook(_write_payload("config/secrets.yml"), cwd=subdir)

        assert _decision(result) == "deny", f"stdout={result.stdout!r}"
        assert len(_read_block_rows(repo)) == 1, "row must land at the repo root"
        assert _read_block_rows(subdir) == [], (
            "row must NOT land in the invoking subdirectory"
        )

    def test_regression_issue_1587_explicit_project_dir_anchors_log(
        self, tmp_path: Path
    ) -> None:
        """CLAUDE_PROJECT_DIR takes precedence over git rev-parse.

        Positive control for the injection point the other tests rely on:
        proves the anchor is genuinely honoured rather than coincidentally
        matching cwd.
        """
        repo = _init_repo(tmp_path / "repo")
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()

        result = _run_hook(
            _write_payload("deploy/server.pem"),
            cwd=repo,
            env={"CLAUDE_PROJECT_DIR": str(elsewhere)},
        )

        assert _decision(result) == "deny"
        assert len(_read_block_rows(elsewhere)) == 1, "row must follow the anchor"
        assert _read_block_rows(repo) == [], "row must not land at the git root"


class TestIssue1587TelemetryNeverOutranksEnforcement:
    """Four ways recording can fail. All four must still refuse."""

    def test_regression_issue_1587_unwritable_log_still_denies(
        self, tmp_path: Path
    ) -> None:
        """An unwritable telemetry log must not convert a block into an allow.

        ``.claude`` is created as a regular FILE so ``mkdir(parents=True)``
        inside the recorder raises NotADirectoryError. uid-independent,
        unlike chmod, which root ignores.
        """
        repo = _init_repo(tmp_path / "repo")
        (repo / ".claude").write_text("not a directory\n", encoding="utf-8")

        result = _run_hook(_write_payload("app/credentials.json"), cwd=repo)

        assert _decision(result) == "deny", (
            "telemetry failure must degrade to 'refused, unrecorded', never to "
            f"'allow'. stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert result.returncode == 0, f"hook exited {result.returncode}"
        # Positive control: the recorder really did fail. Without this the
        # test would pass just as happily against a recorder that succeeded.
        assert "[hook-telemetry]" in result.stderr, (
            f"expected the recorder's stderr fallback; stderr={result.stderr!r}"
        )

    def test_regression_issue_1587_raising_recorder_still_denies(
        self, tmp_path: Path
    ) -> None:
        """A recorder that RAISES must not break the refusal.

        A ``sitecustomize`` shim patches ``log_block_event`` at interpreter
        startup, before the hook's python3 subprocess imports it — a real
        subprocess proof rather than an in-process mock.
        """
        repo = _init_repo(tmp_path / "repo")
        shim_dir = tmp_path / "shim"
        shim_dir.mkdir()
        (shim_dir / "sitecustomize.py").write_text(
            "import sys, os\n"
            "sys.path.insert(0, os.environ['AD_LIB'])\n"
            "import hook_telemetry\n"
            "def _boom(**kwargs):\n"
            "    raise RuntimeError('recorder exploded (injected)')\n"
            "hook_telemetry.log_block_event = _boom\n"
            "sys.stderr.write('RECORDER_PATCHED\\n')\n",
            encoding="utf-8",
        )

        result = _run_hook(
            _write_payload("app/credentials.json"),
            cwd=repo,
            env={"AD_LIB": str(LIB_DIR), "PYTHONPATH": str(shim_dir)},
        )

        # Positive control: a probe whose instrument did not engage proves
        # nothing. Confirm the patch landed before trusting the deny.
        assert "RECORDER_PATCHED" in result.stderr, (
            f"sitecustomize shim did not run; stderr={result.stderr!r}"
        )
        assert _decision(result) == "deny", (
            f"raising recorder broke enforcement; stdout={result.stdout!r}"
        )
        assert result.returncode == 0, f"hook exited {result.returncode}"
        assert _read_block_rows(repo) == [], "raising recorder cannot have logged"

    def test_regression_issue_1587_telemetry_disabled_still_denies(
        self, tmp_path: Path
    ) -> None:
        """The HOOK_TELEMETRY_DISABLED rollback switch must not disable the guard."""
        repo = _init_repo(tmp_path / "repo")

        result = _run_hook(
            _write_payload("app/credentials.json"),
            cwd=repo,
            env={"HOOK_TELEMETRY_DISABLED": "1"},
        )

        assert _decision(result) == "deny", f"stdout={result.stdout!r}"
        assert _read_block_rows(repo) == [], "disabled telemetry must write no row"

    def test_regression_issue_1588_telemetry_disabled_still_asks(
        self, tmp_path: Path
    ) -> None:
        """The ask arm degrades the same way the deny arm does.

        The fused emitter is one surface, so this cannot diverge — which is
        precisely the property worth an assertion rather than an assumption.
        """
        repo = _init_repo(tmp_path / "repo")

        result = _run_hook(
            _write_payload(".env.production"),
            cwd=repo,
            env={"HOOK_TELEMETRY_DISABLED": "1"},
        )

        assert _decision(result) == "ask", f"stdout={result.stdout!r}"
        assert _read_block_rows(repo) == [], "disabled telemetry must write no row"

    def test_regression_issue_1587_missing_python3_still_denies(
        self, tmp_path: Path
    ) -> None:
        """With no python3 on PATH the hook must still refuse.

        PATH is rebuilt from symlinks to only the utilities the hook needs,
        deliberately excluding python3, so the ``command -v`` degradation
        branch is genuinely exercised rather than assumed.
        """
        repo = _init_repo(tmp_path / "repo")
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        for util in _HOOK_PATH_UTILITIES:
            real = shutil.which(util)
            if real:
                (bin_dir / util).symlink_to(real)

        curated_path = str(bin_dir)
        # Negative control on the instrument: the curated PATH must genuinely
        # hide python3, otherwise this test proves nothing.
        assert shutil.which("python3", path=curated_path) is None, (
            "curated PATH still exposes python3; the probe would be vacuous"
        )

        result = _run_hook(
            _write_payload("app/credentials.json"),
            cwd=repo,
            env={"PATH": curated_path},
        )

        assert _decision(result) == "deny", (
            f"missing python3 broke enforcement; stdout={result.stdout!r} "
            f"stderr={result.stderr!r}"
        )
        assert result.returncode == 0, f"hook exited {result.returncode}"
        assert "python3 unavailable" in result.stderr, (
            f"expected the degradation notice; stderr={result.stderr!r}"
        )
        assert _read_block_rows(repo) == []


class TestIssue1587SingleRefusalSurface:
    """The mechanism, not the patch: only one place may emit a refusal."""

    def test_regression_issue_1587_hook_has_exactly_one_deny_emitter(self) -> None:
        """Adding a third refusal path with its own heredoc must fail here.

        The defect being fixed is not "two heredocs lacked a log call" — it
        is that emitting a refusal and recording it were separable at all.
        This guard fails the moment that surface is reintroduced.

        #1588 parameterised the emitter over the decision, so the literal
        ``"permissionDecision": "deny"`` no longer appears in the source. A
        counter still looking for that literal would read 0 and pass for the
        wrong reason; ``_REFUSAL_EMITTER`` matches the interpolated form too.
        """
        source = HOOK_PATH.read_text(encoding="utf-8")
        found = _count_refusal_emitters(source)
        assert found == 1, (
            "the hook must have exactly ONE refusing-decision emitter "
            f"(deny_and_record, covering both deny and ask); found {found}"
        )
        assert "deny_and_record()" in source, "the fused emitter must exist"

    def test_regression_issue_1587_deny_emitter_counter_can_fail(self) -> None:
        """Positive control for the counter above.

        A guard observed only passing is indistinguishable from a guard that
        cannot fail. This feeds the counter a source with the separable
        surface restored — in the NEW envelope shape, so the control tracks
        the code that actually ships — and requires it to report 2. A third
        arm covers the ask variant, which a deny-only counter would miss.
        """
        separable = (
            "if grep -q secret; then\n"
            "  cat <<EOF\n"
            '{"hookSpecificOutput": {"hookEventName": "PreToolUse",\n'
            '  "permissionDecision": "deny", "permissionDecisionReason": "a"}}\n'
            "EOF\nfi\n"
            "if grep -q key; then\n"
            "  cat <<EOF\n"
            '{"hookSpecificOutput": {"hookEventName": "PreToolUse",\n'
            '  "permissionDecision": "deny", "permissionDecisionReason": "b"}}\n'
            "EOF\nfi\n"
        )
        assert _count_refusal_emitters(separable) == 2

        ask_variant = separable.replace('"deny"', '"ask"')
        assert _count_refusal_emitters(ask_variant) == 2, (
            "an ask emitter is a refusing surface too; a deny-only counter "
            "would let a second ask heredoc in unnoticed"
        )

        allow_only = (
            'echo \'{"hookSpecificOutput": {"hookEventName": "PreToolUse", '
            '"permissionDecision": "allow"}}\'\n'
        )
        assert _count_refusal_emitters(allow_only) == 0

        commented = '# emits "permissionDecision": "deny" on this path\n'
        assert _count_refusal_emitters(commented) == 0, (
            "prose describing a refusal is not a surface that emits one"
        )

        # THE SHAPE THAT ACTUALLY SHIPS. The emitter is no longer a heredoc:
        # the payload is rendered by printf with a jq-escaped reason, so the
        # decision reaches the source text as the placeholder "%s". A counter
        # that only knew the heredoc shapes above would read 0 against the
        # shipped file and pass for the wrong reason — which is the same
        # "counter blind to the code it counts" defect this control exists
        # for. Two printf emitters must read 2.
        printf_shape = (
            "emit_one() {\n"
            "  printf '{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\","
            '"permissionDecision":"%s","permissionDecisionReason":%s}}\\n\' '
            '"$decision" "$reason_json"\n'
            "}\n"
        )
        assert _count_refusal_emitters(printf_shape) == 1, (
            "the counter is blind to the printf emitter shape that ships"
        )
        assert _count_refusal_emitters(printf_shape * 2) == 2

        # The jq --arg shape, for the same reason: if the emitter is ever
        # rewritten as `jq -n --arg decision`, the counter must still see it.
        jq_shape = (
            "jq -n --arg decision \"$decision\" '{\"hookSpecificOutput\": "
            '{"hookEventName": "PreToolUse", "permissionDecision": $decision}}\'\n'
        )
        assert _count_refusal_emitters(jq_shape) == 1, (
            "the counter is blind to the jq --arg emitter shape"
        )

        # NEGATIVE CONTROL for the widened alternation: a printf that emits an
        # ALLOW is not a refusing surface, and the "%s" arm must not have made
        # every printf payload look like one.
        printf_allow = (
            "printf '{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\","
            '"permissionDecision":"allow","permissionDecisionReason":%s}}\\n\' '
            '"$reason_json"\n'
        )
        assert _count_refusal_emitters(printf_allow) == 0, (
            "an allow-emitting printf was counted as a refusing surface"
        )


class TestIssue1588PolicyChangeIsIntentional:
    """The two #1587 characterization tests, INVERTED.

    These two tests used to pin arms 2 and 3 as BROKEN, each carrying a
    comment saying: if this now denies, the defect was fixed — that is a
    POLICY change, confirm it was intended, then update this test. The
    tripwires fired. The repository owner confirmed the policy change under
    #1588, and they are inverted here to pin the NEW behaviour.

    They are just as loud in the new direction. This hook now refuses live
    writes in every consumer repo that installs the plugin. If either
    assertion below starts failing, the guard has gone dark AGAIN — back to
    the state where it ships everywhere, runs on every write, and permits
    all of them. Do not "fix" the test. Confirm the policy reversal was
    intended, and if it was not, restore the hook.
    """

    def test_regression_issue_1588_real_payload_shape_reaches_the_refusal(
        self, tmp_path: Path
    ) -> None:
        """Claude Code sends ``tool_input.file_path``; the hook now reads it.

        Before #1588 the hook read ``parameters.file_path``, so every deny
        path was unreachable in production and this test asserted ``allow``.
        Deliberately hand-built rather than routed through ``_write_payload``:
        the builder and the hook must be able to disagree, or this test only
        proves the builder is self-consistent.
        """
        repo = _init_repo(tmp_path / "repo")

        result = _run_hook(
            {
                "tool_name": "Write",
                "tool_input": {"file_path": "config/secrets.yaml"},
                "session_id": "real-shape",
            },
            cwd=repo,
        )

        assert _decision(result) == "deny", (
            "the hook is reading the wrong input field again, so it permits "
            "every write it claims to block (#1588 arm 2). The real Claude "
            "Code key is tool_input.file_path; .parameters.file_path appears "
            "in no live payload. Confirm any reversal was intended before "
            f"touching this test. stdout={result.stdout!r}"
        )
        rows = _read_block_rows(repo)
        assert len(rows) == 1, "a live refusal must still be recorded"
        assert rows[0]["session_id"] == "real-shape"

    def test_regression_issue_1588_envelope_is_hook_specific_output(
        self, tmp_path: Path
    ) -> None:
        """The hook emits ``hookSpecificOutput.permissionDecision``.

        Before #1588 it emitted a BARE top-level ``permissionDecision``, which
        Claude Code honours neither as the documented envelope
        (``unified_pre_tool.py:6302``) nor as the legacy top-level
        ``{"decision": "block"}`` (``:6273``) — so the refusal was ignored and
        the write proceeded regardless.

        Asserted against the EMITTED payload, not the source text: source text
        matches comments too, and the comments necessarily name both envelopes
        while explaining the fix.
        """
        repo = _init_repo(tmp_path / "repo")
        result = _run_hook(_write_payload("keys/private_key.txt"), cwd=repo)

        emitted = json.loads(result.stdout)
        assert "hookSpecificOutput" in emitted, (
            "the documented envelope is gone, so Claude Code would read this "
            "payload as carrying no decision at all and every refusal this "
            "hook makes becomes invisible again (#1588 arm 3). Confirm any "
            f"reversal was intended before touching this test. {emitted!r}"
        )
        envelope = emitted["hookSpecificOutput"]
        assert envelope["hookEventName"] == "PreToolUse"
        assert envelope["permissionDecision"] == "deny"
        assert "Cannot write to sensitive file" in envelope["permissionDecisionReason"]
        # The bare top-level field is what Claude Code ignores. Its ABSENCE is
        # the fix; leaving it beside the envelope would re-document the
        # divergence as if it were still real.
        assert "permissionDecision" not in emitted, (
            "the ignored top-level field is back alongside the envelope"
        )

    def test_regression_issue_1588_allow_uses_the_same_envelope(
        self, tmp_path: Path
    ) -> None:
        """The allow payload must not diverge from the refusal payload.

        Arm 3 was two divergent shapes in one file. Fixing only the refusing
        one would leave the same class of defect on the permitting path.
        """
        repo = _init_repo(tmp_path / "repo")
        result = _run_hook(_write_payload("README.md"), cwd=repo)

        emitted = json.loads(result.stdout)
        assert set(emitted) == {"hookSpecificOutput"}, (
            f"allow payload carries unexpected top-level keys: {sorted(emitted)}"
        )
        assert emitted["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        assert emitted["hookSpecificOutput"]["permissionDecision"] == "allow"


# ---------------------------------------------------------------------------
# The policy, one case per pattern class, all three arms.
#
# Every case is fed a REAL-shaped payload and asserted through the nested
# envelope key. A test that grepped stdout for the substring "deny" would pass
# against the pre-#1588 top-level envelope, and would therefore not be a test.
# ---------------------------------------------------------------------------

#: One representative per DENY pattern. An agent has no business writing these.
_DENY_CASES = [
    ("app/credentials.json", "credentials"),
    ("config/secrets.yaml", "secrets"),
    ("keys/private_key.txt", "private.*key"),
    ("certs/server.pem", r"\.pem$"),
    ("certs/server.key", r"\.key$"),
    (".git/config", r"\.git/"),
]

#: One representative per ASK pattern. A human legitimately edits these.
_ASK_CASES = [
    (".env", r"\.env$"),
    (".env.production", r"\.env\..*"),
    (".claude/PROJECT.md", r"PROJECT\.md$"),
]

#: The permitting arm. ``docs/environment.md`` is the negative control that
#: proves "environment" does not trip the ``.env`` pattern.
_ALLOW_CASES = ["README.md", "src/app.py", "docs/environment.md"]


@pytest.mark.parametrize("file_path,pattern", _DENY_CASES)
def test_regression_issue_1588_deny_class_refuses(
    file_path: str, pattern: str, tmp_path: Path
) -> None:
    """Every DENY pattern must refuse outright, through the real envelope."""
    repo = _init_repo(tmp_path / "repo")
    result = _run_hook(_write_payload(file_path, tool_name="Write"), cwd=repo)
    assert _decision(result) == "deny", (
        f"{file_path} (pattern {pattern}) expected deny, got {result.stdout!r}"
    )
    rows = _read_block_rows(repo)
    assert len(rows) == 1 and rows[0]["metadata"]["decision"] == "deny", (
        f"{file_path}: refusal was not recorded as a deny; rows={rows!r}"
    )


@pytest.mark.parametrize("file_path,pattern", _ASK_CASES)
def test_regression_issue_1588_ask_class_prompts(
    file_path: str, pattern: str, tmp_path: Path
) -> None:
    """Every ASK pattern must prompt, not refuse.

    ``.env`` and ``PROJECT.md`` MOVED from deny to ask under #1588: editing
    them is routine human work, and the PROJECT.md rule's own reason text
    already said "edit PROJECT.md manually". A blanket deny cannot express
    "stop the agent, let the human decide".
    """
    repo = _init_repo(tmp_path / "repo")
    result = _run_hook(_write_payload(file_path, tool_name="Edit"), cwd=repo)
    assert _decision(result) == "ask", (
        f"{file_path} (pattern {pattern}) expected ask, got {result.stdout!r}"
    )
    rows = _read_block_rows(repo)
    assert len(rows) == 1 and rows[0]["metadata"]["decision"] == "ask", (
        f"{file_path}: the ask was not recorded; an ask is a refusal to "
        f"proceed silently and belongs in the block log. rows={rows!r}"
    )


@pytest.mark.parametrize("file_path", _ALLOW_CASES)
def test_regression_issue_1588_ordinary_files_are_permitted(
    file_path: str, tmp_path: Path
) -> None:
    """THE PERMITTING ARM. A guard that refuses everything is not a guard.

    ``docs/environment.md`` is the load-bearing case: it contains the letters
    "environment" but must not trip the ``.env`` pattern.
    """
    repo = _init_repo(tmp_path / "repo")
    result = _run_hook(_write_payload(file_path, tool_name="Write"), cwd=repo)
    assert _decision(result) == "allow", (
        f"{file_path}: expected allow, got {result.stdout!r}"
    )
    assert _read_block_rows(repo) == [], f"{file_path}: allow must record nothing"


# ---------------------------------------------------------------------------
# Case-insensitivity (#1588 remediation).
#
# Every pattern class fell through on an uppercase spelling: the guard denied
# ``x/secrets.yaml`` and permitted ``x/SECRETS.yaml``. On the deployment target
# (macOS/APFS, case-insensitive by default) those two spellings NAME THE SAME
# FILE, so the guard refused a write and then permitted the identical write one
# shift key later.
#
# This is the same defect class as arms 1-3: the check's subject was a
# lowercase string rather than the thing being protected. The fix removes the
# category (case-insensitive matching at the single match site) rather than
# enumerating uppercase variants — an alternation like ``SECRETS|Secrets`` is
# the same defect with more spellings, and would fall through on ``SeCrEtS``.
#
# Each case below feeds the SAME logical path in two spellings and requires the
# SAME decision from both. The lowercase half passed before the fix; the
# uppercase half is the red.
# ---------------------------------------------------------------------------

#: (lowercase spelling, other-case spelling, required decision, pattern).
#: PROJECT.md is inverted on purpose — its canonical spelling is the uppercase
#: one, so its variant tests the lowercase direction. Case-insensitivity is not
#: "tolerate shouting"; it is "case is not part of the identity of a path".
_CASE_VARIANT_CASES = [
    ("app/credentials.json", "app/CREDENTIALS.json", "deny", "credentials"),
    ("config/secrets.yaml", "config/SECRETS.yaml", "deny", "secrets"),
    ("keys/private_key.txt", "keys/PRIVATE_KEY.txt", "deny", "private.*key"),
    ("certs/server.pem", "certs/server.PEM", "deny", r"\.pem$"),
    ("certs/server.key", "certs/server.KEY", "deny", r"\.key$"),
    (".git/config", ".GIT/config", "deny", r"\.git/"),
    (".env", ".ENV", "ask", r"\.env$"),
    (".env.production", ".ENV.PRODUCTION", "ask", r"\.env\..*"),
    (".claude/PROJECT.md", ".claude/project.md", "ask", r"PROJECT\.md$"),
]

#: The permitting arm of the same widening. A case-insensitive fix applied too
#: broadly would start refusing these; ``docs/ENVIRONMENT.md`` is the standing
#: ``.env`` negative control in its uppercase spelling, which is exactly where
#: an over-eager widening would first show.
_ALLOW_CASE_VARIANTS = [
    ("docs/environment.md", "docs/ENVIRONMENT.md"),
    ("README.md", "readme.md"),
    ("src/app.py", "src/APP.PY"),
]


@pytest.mark.parametrize(
    "lower_path,variant_path,expected,pattern", _CASE_VARIANT_CASES
)
def test_regression_issue_1588_case_variants_get_the_same_decision(
    lower_path: str, variant_path: str, expected: str, pattern: str, tmp_path: Path
) -> None:
    """Two spellings of one path must produce one decision.

    Both halves are asserted in the same test so the pair cannot drift apart:
    a fix that made ``deny`` case-insensitive while leaving ``ask`` case
    sensitive would reintroduce the split in a new place, and this
    parametrization covers every class on both sides of that line.
    """
    repo_lower = _init_repo(tmp_path / "lower")
    repo_variant = _init_repo(tmp_path / "variant")

    lower_result = _run_hook(_write_payload(lower_path, tool_name="Write"), cwd=repo_lower)
    variant_result = _run_hook(
        _write_payload(variant_path, tool_name="Write"), cwd=repo_variant
    )

    # Positive control: the spelling that always worked must still work. If
    # this half fails the fix broke the guard rather than widening it.
    assert _decision(lower_result) == expected, (
        f"{lower_path} (pattern {pattern}) expected {expected}, "
        f"got {lower_result.stdout!r}"
    )
    assert _decision(variant_result) == expected, (
        f"{variant_path} is the same file as {lower_path} on a case-insensitive "
        f"filesystem, so it must get the same decision ({expected}). Pattern "
        f"{pattern} is matching case-sensitively, which makes this guard "
        f"bypassable by pressing shift. Got {variant_result.stdout!r}"
    )
    # The refusal must be RECORDED in both spellings too. A guard that refuses
    # the variant but logs nothing is invisible to triage for half its traffic.
    for label, repo in ((lower_path, repo_lower), (variant_path, repo_variant)):
        rows = _read_block_rows(repo)
        assert len(rows) == 1 and rows[0]["metadata"]["decision"] == expected, (
            f"{label}: refusal not recorded as {expected}; rows={rows!r}"
        )


@pytest.mark.parametrize("lower_path,variant_path", _ALLOW_CASE_VARIANTS)
def test_regression_issue_1588_case_widening_does_not_over_refuse(
    lower_path: str, variant_path: str, tmp_path: Path
) -> None:
    """THE PERMITTING ARM of the case-insensitive widening.

    ``docs/environment.md`` is the standing negative control proving the
    substring "environment" does not trip the ``.env`` pattern. A careless
    case-insensitive widening could break it, and it would break in the
    UPPERCASE spelling first — which nothing tested before this. If either
    half starts refusing, the fix is too broad; report that rather than
    relaxing the control.
    """
    repo_lower = _init_repo(tmp_path / "lower")
    repo_variant = _init_repo(tmp_path / "variant")

    for label, path, repo in (
        (lower_path, lower_path, repo_lower),
        (variant_path, variant_path, repo_variant),
    ):
        result = _run_hook(_write_payload(path, tool_name="Write"), cwd=repo)
        assert _decision(result) == "allow", (
            f"{label}: expected allow, got {result.stdout!r}. A case-insensitive "
            f"match must not widen WHAT is protected, only how it is spelled."
        )
        assert _read_block_rows(repo) == [], f"{label}: allow must record nothing"


class TestIssue1588CaseInsensitivityRationale:
    """WHY the matching is case-insensitive — pinned so it is not simplified out.

    The deployment target for this plugin is macOS with APFS, which is
    **case-insensitive by default**. ``secrets.yaml`` and ``SECRETS.yaml`` are
    not two files that happen to look alike; they are one file with two
    spellings. A case-sensitive guard therefore refuses a write and permits the
    byte-identical write to the byte-identical file, which is strictly worse
    than no guard: it produces confidence it has not earned.

    A future reader looking at ``grep -qiE`` may be tempted to drop the ``i``
    on the grounds that "the patterns are all lowercase anyway". That is the
    reasoning this class exists to refuse.
    """

    def test_regression_issue_1588_same_file_two_spellings_one_decision(
        self, tmp_path: Path
    ) -> None:
        """Probe the filesystem, then require the guard to hold either way.

        The probe is recorded rather than asserted: CI runs on Linux/ext4,
        which IS case-sensitive, and the guard must be case-insensitive on
        BOTH — the artifact ships to macOS regardless of where it is tested.
        Making the assertion conditional on the probe would make this test
        vacuous on exactly the platform whose result matters least.
        """
        probe_dir = tmp_path / "fsprobe"
        probe_dir.mkdir()
        (probe_dir / "secrets.yaml").write_text("x\n", encoding="utf-8")
        fs_is_case_insensitive = (probe_dir / "SECRETS.yaml").exists()

        repo = _init_repo(tmp_path / "repo")
        result = _run_hook(_write_payload("config/SECRETS.yaml"), cwd=repo)

        assert _decision(result) == "deny", (
            "config/SECRETS.yaml was permitted. This filesystem reports "
            f"case-insensitive={fs_is_case_insensitive}; on the macOS/APFS "
            "deployment target that value is True, meaning SECRETS.yaml and "
            "secrets.yaml are THE SAME FILE. A case-sensitive guard there "
            "refuses one spelling and permits the other spelling of the file "
            f"it just refused. stdout={result.stdout!r}"
        )

    def test_regression_issue_1588_case_insensitivity_is_at_every_match_site(
        self,
    ) -> None:
        """No decision class may match case-sensitively.

        A source-text check, and deliberately a narrow one: the behavioural
        proof is the parametrized pairs above, which drive the real script.
        This adds the one thing behaviour cannot show — that a FUTURE pattern
        class cannot be added with a case-sensitive matcher beside the
        case-insensitive one. It counts match sites, so it fails both when the
        site loses its ``i`` and when a second, unguarded matcher appears.
        """
        source = HOOK_PATH.read_text(encoding="utf-8")

        assert _greps_by_case(source) == {"insensitive": 1, "sensitive": 0}, (
            "the hook must have exactly ONE pattern-match site, and it must be "
            "case-insensitive. Found "
            f"{_greps_by_case(source)}. A case-SENSITIVE grep deciding "
            "anything here is bypassable by pressing shift; a SECOND match "
            "site is a place to fix deny and forget ask."
        )

    def test_regression_issue_1588_match_site_counter_can_fail(self) -> None:
        """POSITIVE CONTROL for the counter above.

        A guard observed only passing is indistinguishable from a guard that
        cannot fail. An earlier draft of this counter used a ``(?!.*i)``
        lookahead over the whole line, so it silently failed to flag
        ``grep -qE "private.*key"`` — the letter ``i`` in the PATTERN satisfied
        the lookahead. That instrument would have reported the fixed hook and
        the broken hook identically. These arms exist so it cannot happen
        twice: the flag cluster is parsed, not pattern-matched.
        """
        # The exact shape the bug had, including an ``i`` in the pattern that
        # defeated the lookahead version of this check.
        broken = 'if echo "$F" | grep -qE "private.*key"; then\n  refuse\nfi\n'
        assert _greps_by_case(broken) == {"insensitive": 0, "sensitive": 1}, (
            "the counter did not flag a case-sensitive grep whose PATTERN "
            "contains the letter i — this is the lookahead defect, restored"
        )

        fixed = 'grep -qiE "$DENY" <<<"$F"\n'
        assert _greps_by_case(fixed) == {"insensitive": 1, "sensitive": 0}

        # Flag order and separate flags must not fool it.
        assert _greps_by_case('grep -i -q -E "$P" <<<"$F"\n') == {
            "insensitive": 1,
            "sensitive": 0,
        }
        assert _greps_by_case('grep -Eq "$P" <<<"$F"\n') == {
            "insensitive": 0,
            "sensitive": 1,
        }

        # Two sites, one of each: the split this hook must never reacquire.
        split = fixed + broken
        assert _greps_by_case(split) == {"insensitive": 1, "sensitive": 1}

        # NEGATIVE CONTROL: prose naming a grep is not a grep. Without this the
        # counter would read the header's own explanation as a match site.
        commented = '# was: echo "$F" | grep -qE "$DENY_PATTERNS"\n'
        assert _greps_by_case(commented) == {"insensitive": 0, "sensitive": 0}, (
            "a comment describing a match site was counted as one"
        )


# ---------------------------------------------------------------------------
# Issue #1588 remediation cycle 2 — THE FAIL-OPEN CLASS.
#
# One class, two instances. ANY path on which this hook fails to emit a VALID
# decision payload results in the write being PERMITTED, because Claude Code
# parses no decision from unparseable or absent stdout and falls through.
#
#   INSTANCE 1 — untrusted path content broke the JSON. The reason string is
#     built from ``FILE_PATH``, which is attacker-influenced, and was
#     interpolated RAW into a heredoc. A path carrying a double quote, a
#     backslash, a newline or a control character produced malformed stdout.
#     Worse than a silent miss: the telemetry row was still written, so the
#     block log claimed a refusal that never happened. A guard that lies in
#     your favour manufactures the very evidence you would use to catch it.
#
#   INSTANCE 2 — the hook emitted NOTHING. Under ``set -euo pipefail`` a
#     malformed stdin payload killed the script at the ``jq`` parse, before
#     any payload reached stdout.
#
# Both are the same defect: enforcement that depends on a fragile emission
# path, with silence as the failure mode. The tests below drive the real
# script and require ``json.loads`` to succeed AND the nested decision to be
# correct. A test that merely grepped stdout for "deny" would pass against the
# malformed payload — which is exactly the state being fixed — so it would not
# be a test.
# ---------------------------------------------------------------------------

#: Path fragments that are hostile to raw JSON interpolation. One per escape
#: class JSON defines, rather than an enumeration of "bad characters": a fix
#: that special-cased the quote and forgot the backslash would still be the
#: defect, and a fix that escaped both but not U+0001 would still be the
#: defect. ``jq`` handles the whole class, which is why the fix delegates to
#: it rather than substituting characters.
_HOSTILE_FRAGMENTS = [
    ("double_quote", '"'),
    ("backslash", "\\"),
    ("newline", "\n"),
    ("control_char", "\x01"),
]


@pytest.mark.parametrize("label,fragment", _HOSTILE_FRAGMENTS)
def test_regression_issue_1588_hostile_path_still_denies_with_valid_json(
    label: str, fragment: str, tmp_path: Path
) -> None:
    """A DENY-class path carrying a JSON metacharacter must still refuse.

    The assertion is deliberately two-part. ``json.loads`` must succeed —
    that is the enforcement, because Claude Code reads no decision from a
    payload it cannot parse — AND the nested decision must be ``deny``. Only
    the second half would pass against a payload that happened to contain the
    substring ``deny`` inside broken JSON.

    The telemetry assertion is the PHANTOM-DENY check: before the fix the row
    was written while stdout was malformed, so the block log recorded a
    refusal that the harness never enforced. Row and payload must now agree.
    """
    repo = _init_repo(tmp_path / "repo")
    file_path = f"config/secrets{fragment}weird.yaml"

    result = _run_hook(_write_payload(file_path, tool_name="Write"), cwd=repo)

    assert result.stdout.strip(), (
        f"[{label}] the hook emitted NOTHING, so no decision reaches Claude "
        f"Code and the write proceeds. stderr={result.stderr!r}"
    )
    try:
        emitted = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"[{label}] stdout is not valid JSON, so Claude Code parses no "
            f"decision and the write PROCEEDS. An attacker-influenced path "
            f"must not be able to break the payload. {exc}\n"
            f"stdout={result.stdout!r}"
        ) from exc

    assert emitted["hookSpecificOutput"]["permissionDecision"] == "deny", (
        f"[{label}] expected deny, got {emitted!r}"
    )

    rows = _read_block_rows(repo)
    assert len(rows) == 1 and rows[0]["metadata"]["decision"] == "deny", (
        f"[{label}] the refusal was not recorded; rows={rows!r}"
    )


@pytest.mark.parametrize("label,fragment", _HOSTILE_FRAGMENTS)
def test_regression_issue_1588_hostile_path_still_asks_with_valid_json(
    label: str, fragment: str, tmp_path: Path
) -> None:
    """The ASK class breaks identically, so it is proved identically.

    Fixing deny and leaving ask is the "fix the instance, not the class"
    failure this hook has already committed once (arm 4 denied
    ``secrets.yaml`` and allowed ``SECRETS.yaml``). Both classes route
    through the same single emitter, so this must hold by construction — which
    is precisely why it is worth an assertion rather than an assumption.
    """
    repo = _init_repo(tmp_path / "repo")
    file_path = f".env.prod{fragment}uction"

    result = _run_hook(_write_payload(file_path, tool_name="Edit"), cwd=repo)

    assert result.stdout.strip(), (
        f"[{label}] the hook emitted NOTHING; the write proceeds. "
        f"stderr={result.stderr!r}"
    )
    try:
        emitted = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"[{label}] stdout is not valid JSON on the ask path either, so "
            f"the human is never prompted and the write PROCEEDS. {exc}\n"
            f"stdout={result.stdout!r}"
        ) from exc

    assert emitted["hookSpecificOutput"]["permissionDecision"] == "ask", (
        f"[{label}] expected ask, got {emitted!r}"
    )

    rows = _read_block_rows(repo)
    assert len(rows) == 1 and rows[0]["metadata"]["decision"] == "ask", (
        f"[{label}] the ask was not recorded; rows={rows!r}"
    )


@pytest.mark.parametrize("label,fragment", _HOSTILE_FRAGMENTS)
def test_regression_issue_1588_hostile_path_round_trips_into_the_reason(
    label: str, fragment: str, tmp_path: Path
) -> None:
    """Escaping must PRESERVE the path, not sanitise it away.

    A "fix" that stripped hostile characters from the reason would make the
    payload parse while destroying the one piece of information the human
    needs to judge the write. The reason must contain the path byte for byte
    after JSON decoding.
    """
    repo = _init_repo(tmp_path / "repo")
    file_path = f"config/secrets{fragment}weird.yaml"

    result = _run_hook(_write_payload(file_path, tool_name="Write"), cwd=repo)

    emitted = json.loads(result.stdout)
    reason = emitted["hookSpecificOutput"]["permissionDecisionReason"]
    assert file_path in reason, (
        f"[{label}] the path did not survive escaping intact. A reason that "
        f"drops the character that made the path suspicious is not a usable "
        f"prompt. reason={reason!r}"
    )


@pytest.mark.parametrize("label,fragment", _HOSTILE_FRAGMENTS)
def test_regression_issue_1588_hostile_path_permitting_arm(
    label: str, fragment: str, tmp_path: Path
) -> None:
    """THE PERMITTING ARM — deliberately NOT a red-before case.

    Stated plainly rather than counted as evidence: this case PASSES against
    the pre-fix code, because the allow payload was a heredoc with nothing
    interpolated into it and so could not be broken. It is kept as the
    negative control for the fix, not as proof of the bug: a change that
    routed the allow payload through the same renderer could break it, and an
    over-eager "reject anything with a weird character" fix would turn these
    ordinary files into refusals. Both would show here.
    """
    repo = _init_repo(tmp_path / "repo")
    file_path = f"docs/note{fragment}book.md"

    result = _run_hook(_write_payload(file_path, tool_name="Write"), cwd=repo)

    emitted = json.loads(result.stdout)
    assert emitted["hookSpecificOutput"]["permissionDecision"] == "allow", (
        f"[{label}] an ordinary file with an odd character must still be "
        f"permitted; a guard that refuses everything is not a guard. "
        f"{emitted!r}"
    )
    assert _read_block_rows(repo) == [], f"[{label}] allow must record nothing"


class TestIssue1588UndeterminedDecisionFailsClosed:
    """INSTANCE 2. The hook could exit having emitted no payload at all.

    Under ``set -euo pipefail`` a stdin payload ``jq`` cannot parse killed the
    script at the parse, before any payload reached stdout. No payload means
    no decision means the write proceeds.

    Neither trigger is agent-reachable — an agent cannot make Claude Code send
    non-JSON on hook stdin — so this is not an exploit path, and it is fixed
    anyway. The bar this work is held to is that a guard must be PROVEN to
    refuse; a known route to silent permission fails that bar whether or not
    an adversary can walk it.

    The chosen undetermined-case decision is ``ask``, not ``deny``. See the
    ``UNDETERMINED_DECISION`` rationale in the hook header: a hard deny on
    every payload the hook cannot parse would wedge the session outright if
    the harness ever changed its payload shape, whereas ``ask`` surfaces the
    anomaly to the human and lets them proceed. Refusing to act silently is
    the property that matters; refusing to act at all is a cost with no
    matching benefit.
    """

    def test_regression_issue_1588_malformed_stdin_emits_a_valid_ask(
        self, tmp_path: Path
    ) -> None:
        """Non-JSON on stdin must produce a valid payload, not silence."""
        repo = _init_repo(tmp_path / "repo")

        result = _run_hook("this is not json at all {{{", cwd=repo)

        assert result.stdout.strip(), (
            "the hook emitted NOTHING on a malformed payload. No stdout means "
            "no decision, which means the write PROCEEDS. "
            f"rc={result.returncode} stderr={result.stderr!r}"
        )
        emitted = json.loads(result.stdout)
        assert emitted["hookSpecificOutput"]["permissionDecision"] == "ask", (
            "an undetermined decision must surface to the human as an ask, "
            f"not fall through. {emitted!r}"
        )
        assert emitted["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        assert result.returncode == 0, (
            f"the hook must exit cleanly after emitting; rc={result.returncode}"
        )

    def test_regression_issue_1588_malformed_stdin_is_recorded(
        self, tmp_path: Path
    ) -> None:
        """The undetermined case is a refusal to proceed silently, so it logs.

        It routes through the SAME single emitter as every other refusal, so
        it cannot refuse without recording. The distinct ``rule`` is what lets
        triage tell "the harness sent me something I could not read" apart
        from "an agent tried to write a secret".
        """
        repo = _init_repo(tmp_path / "repo")

        _run_hook("not json", cwd=repo)

        rows = _read_block_rows(repo)
        assert len(rows) == 1, f"the undetermined ask was not recorded; {rows!r}"
        assert rows[0]["metadata"]["decision"] == "ask"
        assert rows[0]["metadata"]["rule"] == "undetermined_payload", (
            "triage cannot separate a parse failure from a policy refusal "
            f"without a distinct rule; got {rows[0]['metadata']!r}"
        )

    def test_regression_issue_1588_undetermined_fallback_does_not_fire_normally(
        self, tmp_path: Path
    ) -> None:
        """NEGATIVE CONTROL. The fallback must not hijack well-formed traffic.

        A fallback that fired on every invocation would make every test above
        pass while the policy itself was dead. Three arms — allow, deny, ask —
        because a fallback that fired only on the allow path would be visible
        nowhere else.
        """
        for path, expected, rule in (
            ("README.md", "allow", None),
            ("config/secrets.yaml", "deny", "sensitive_file_pattern"),
            (".env", "ask", "human_editable_pattern"),
        ):
            repo = _init_repo(tmp_path / f"repo-{expected}")
            result = _run_hook(_write_payload(path, tool_name="Write"), cwd=repo)
            assert _decision(result) == expected, (
                f"{path}: expected {expected}, got {result.stdout!r}"
            )
            rows = _read_block_rows(repo)
            if rule is None:
                assert rows == [], f"{path}: allow must record nothing; {rows!r}"
            else:
                assert len(rows) == 1 and rows[0]["metadata"]["rule"] == rule, (
                    f"{path}: the undetermined fallback appears to have "
                    f"hijacked a real policy decision; rows={rows!r}"
                )

    def test_regression_issue_1588_missing_jq_emits_a_valid_ask(
        self, tmp_path: Path
    ) -> None:
        """The emitter's own hard dependency must not be a fail-open route.

        ``jq`` parses the input payload, so without it the hook cannot read
        ``file_path`` at all and dies at the first command. That is the same
        class as a malformed payload, and it is the one case a fallback built
        ON jq could not cover — which is why the emitter renders its envelope
        with ``printf`` and uses ``jq`` only to escape the reason, falling
        back to a constant reason when ``jq`` is unreachable.

        PATH is rebuilt from symlinks to the utilities the hook needs, minus
        jq, so the branch is genuinely exercised rather than assumed.
        """
        repo = _init_repo(tmp_path / "repo")
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        for util in _HOOK_PATH_UTILITIES:
            if util == "jq":
                continue
            real = shutil.which(util)
            if real:
                (bin_dir / util).symlink_to(real)
        real_python = shutil.which("python3")
        if real_python:
            (bin_dir / "python3").symlink_to(real_python)

        curated_path = str(bin_dir)
        # Negative control on the instrument: the curated PATH must genuinely
        # hide jq, otherwise this probe is vacuous.
        assert shutil.which("jq", path=curated_path) is None, (
            "curated PATH still exposes jq; the probe would prove nothing"
        )
        # Positive control on the instrument: it must NOT have hidden bash,
        # or the failure would be the launcher rather than the hook.
        assert shutil.which("bash", path=curated_path) is not None

        result = _run_hook(
            _write_payload("config/secrets.yaml", tool_name="Write"),
            cwd=repo,
            env={"PATH": curated_path},
        )

        assert result.stdout.strip(), (
            "with jq absent the hook emitted NOTHING, so the write proceeds. "
            f"rc={result.returncode} stderr={result.stderr!r}"
        )
        emitted = json.loads(result.stdout)
        assert emitted["hookSpecificOutput"]["permissionDecision"] == "ask", (
            f"expected the undetermined ask with jq absent; {emitted!r}"
        )


# ---------------------------------------------------------------------------
# Issue #1588 remediation cycle 3 — THE TRAP INSTALLED TOO LATE.
#
# Cycle 2 closed the fail-open class with an EXIT trap and wrote, in capitals,
# THE HOOK CANNOT EXIT WITHOUT EMITTING A PAYLOAD. The trap was installed 237
# lines after ``set -euo pipefail``. Everything in that window ran unguarded,
# and one line in it —
#
#     SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
#
# — spawns three external commands and dies under ``set -e`` when any is
# unreachable, with empty stdout and no trap yet installed to notice. Empty
# stdout is the fail-open: Claude Code parses no decision and the write
# proceeds. Same class as arms 1-4 and instances 1-2, discovered inside the
# comment that claimed the class was closed.
#
# Not attacker-reachable — it needs host-level PATH or coreutils damage, not
# anything an agent can put in ``file_path``. Fixed anyway, on the same bar the
# rest of this file is held to: a known route to silent permission is a guard
# that has not been proven to refuse.
#
# The fix is NOT "move the trap to line 1". Bash executes a script as it reads
# it; it does not parse the file first. A trap naming a function defined
# further down fires as ``command not found`` and emits exactly the silence it
# was installed to prevent — measured, not assumed:
#
#     $ printf 'set -euo pipefail\\ntrap f EXIT\\nX="$(nope)"\\nf() { echo E; }\\n' \\
#         | bash
#     bash: line 3: nope: command not found
#     bash: line 1: f: command not found          <-- the trap itself died
#
# So the trap goes immediately after the last function definition, the region
# above it is reduced to constructs that cannot fail (literal assignments and
# function definitions), and the one fallible command MOVED BELOW the trap.
#
# Two kinds of test below, because one without the other is the defect again:
#
#   * BEHAVIOURAL — break the early region for real and require a valid ask.
#     Red before the fix (empty stdout, rc 1), green after.
#   * STRUCTURAL — read the source and refuse ANY fallible construct above the
#     trap. Removes the category rather than pinning the one member that was
#     there, and pins the header's claim against the code so a future edit
#     cannot re-broaden the prose past what the code delivers. That specific
#     divergence — a comment more confident than the code — is how arms 2 and
#     3 survived for months in this same file.
# ---------------------------------------------------------------------------

#: A ``dirname`` that fails, and a ``dirname`` that is simply gone. Two
#: different shapes of the same host damage: the first proves a non-zero exit
#: from the early region is caught, the second proves an absent binary is.
#: Both were confirmed to break the assignment before being used as probes.
_BROKEN_DIRNAME_MODES = ("exits_nonzero", "absent")


def _curated_bin(tmp_path: Path, *, dirname_mode: str) -> Path:
    """Build a PATH directory holding the hook's utilities, with a chosen dirname.

    Args:
        tmp_path: Test-scoped temp directory.
        dirname_mode: ``"working"`` symlinks the real ``dirname``;
            ``"exits_nonzero"`` installs one that exits 1; ``"absent"``
            installs none.

    Returns:
        The directory to use as ``PATH``.
    """
    bin_dir = tmp_path / f"bin-{dirname_mode}"
    bin_dir.mkdir()
    for util in _HOOK_PATH_UTILITIES:
        if util == "dirname":
            continue
        real = shutil.which(util)
        if real:
            (bin_dir / util).symlink_to(real)
    real_python = shutil.which("python3")
    if real_python:
        (bin_dir / "python3").symlink_to(real_python)

    if dirname_mode == "working":
        real_dirname = shutil.which("dirname")
        assert real_dirname, "no dirname on this host; the control cannot run"
        (bin_dir / "dirname").symlink_to(real_dirname)
    elif dirname_mode == "exits_nonzero":
        shim = bin_dir / "dirname"
        shim.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        shim.chmod(0o755)
    elif dirname_mode != "absent":
        raise ValueError(f"unknown dirname_mode: {dirname_mode!r}")
    return bin_dir


class TestIssue1588TrapCoversTheEarlyRegion:
    """The 237 lines that ran before the trap existed are now covered.

    The failure is forced in the SCRIPT_DIR resolution, which is the first
    command the hook runs and sits 236 lines above where the trap used to be
    installed. A test that reached only the stdin parse would be re-testing
    cycle 2's fix and would pass against the unfixed code.
    """

    @pytest.mark.parametrize("dirname_mode", _BROKEN_DIRNAME_MODES)
    def test_regression_issue_1588_early_region_failure_emits_a_valid_ask(
        self, dirname_mode: str, tmp_path: Path
    ) -> None:
        """A death in the earliest command must still produce a decision.

        RED BEFORE: the trap was installed 236 lines below the failing
        command, so the script exited rc 1 with empty stdout and Claude Code
        read no decision at all.
        """
        repo = _init_repo(tmp_path / f"repo-{dirname_mode}")
        bin_dir = _curated_bin(tmp_path, dirname_mode=dirname_mode)

        result = _run_hook(
            _write_payload("config/secrets.yaml", tool_name="Write"),
            cwd=repo,
            env={"PATH": str(bin_dir)},
        )

        assert result.stdout.strip(), (
            f"[{dirname_mode}] the hook emitted NOTHING after failing in the "
            f"pre-trap region. No stdout means no decision, which means the "
            f"write PROCEEDS. rc={result.returncode} stderr={result.stderr!r}"
        )
        emitted = json.loads(result.stdout)
        assert emitted["hookSpecificOutput"]["permissionDecision"] == "ask", (
            f"[{dirname_mode}] expected the undetermined ask; {emitted!r}"
        )
        assert emitted["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
        assert result.returncode == 0, (
            f"[{dirname_mode}] the hook must exit cleanly after emitting; "
            f"rc={result.returncode} stderr={result.stderr!r}"
        )

    @pytest.mark.parametrize("dirname_mode", _BROKEN_DIRNAME_MODES)
    def test_regression_issue_1588_early_region_failure_is_unrecorded_not_unenforced(
        self, dirname_mode: str, tmp_path: Path
    ) -> None:
        """Telemetry may degrade here; enforcement may not.

        LIB_DIR is resolved from SCRIPT_DIR, so a failure in that resolution
        leaves the recorder unable to import ``hook_telemetry``. The hook's
        standing ordering applies: a refusal degrades to *unrecorded*, never
        to *allowed*. Both outcomes are accepted here because a host that
        still exposes the library on ``PYTHONPATH`` would legitimately record
        the row; what is NOT accepted is a row claiming a decision the
        payload did not carry — the phantom-deny shape from instance 1.
        """
        repo = _init_repo(tmp_path / f"repo-{dirname_mode}")
        bin_dir = _curated_bin(tmp_path, dirname_mode=dirname_mode)

        result = _run_hook(
            _write_payload("config/secrets.yaml", tool_name="Write"),
            cwd=repo,
            env={"PATH": str(bin_dir)},
        )
        emitted_decision = json.loads(result.stdout)["hookSpecificOutput"][
            "permissionDecision"
        ]

        rows = _read_block_rows(repo)
        if rows:
            assert len(rows) == 1, f"[{dirname_mode}] unexpected rows: {rows!r}"
            assert rows[0]["metadata"]["decision"] == emitted_decision, (
                f"[{dirname_mode}] the block log records a decision the "
                f"payload never carried — the phantom-deny shape. "
                f"rows={rows!r} emitted={emitted_decision!r}"
            )
            assert rows[0]["metadata"]["rule"] == "undetermined_payload"
        else:
            assert "refusal unrecorded" in result.stderr, (
                f"[{dirname_mode}] the refusal was neither recorded nor "
                f"reported as unrecorded; a silent telemetry loss is how "
                f"#1587 started. stderr={result.stderr!r}"
            )

    def test_regression_issue_1588_curated_path_probe_has_a_negative_control(
        self, tmp_path: Path
    ) -> None:
        """NEGATIVE CONTROL ON THE INSTRUMENT.

        The same curated PATH, with a WORKING ``dirname``, must produce
        ordinary policy decisions on all three classes. Without this arm the
        ask above is indistinguishable from "the curated PATH broke the hook
        outright", which would make the probe vacuous — the failure mode that
        turned four silent allows into a false negative in this same file.
        """
        bin_dir = _curated_bin(tmp_path, dirname_mode="working")

        for path, expected in (
            ("README.md", "allow"),
            ("config/secrets.yaml", "deny"),
            (".env", "ask"),
        ):
            repo = _init_repo(tmp_path / f"control-{expected}")
            result = _run_hook(
                _write_payload(path, tool_name="Write"),
                cwd=repo,
                env={"PATH": str(bin_dir)},
            )
            assert _decision(result) == expected, (
                f"{path}: the curated PATH itself changed the decision "
                f"(expected {expected}); the broken-dirname probe would be "
                f"proving nothing. stdout={result.stdout!r} "
                f"stderr={result.stderr!r}"
            )

    def test_regression_issue_1588_broken_dirname_actually_breaks_the_assignment(
        self, tmp_path: Path
    ) -> None:
        """POSITIVE CONTROL ON THE INSTRUMENT.

        The probe is only meaningful if a broken ``dirname`` genuinely kills
        the SCRIPT_DIR assignment under ``set -e``. Asserted against a
        standalone script carrying the hook's exact resolution line and NO
        trap, so a green result upstream cannot be explained by "the
        assignment quietly succeeded".
        """
        probe = tmp_path / "probe.sh"
        probe.write_text(
            'set -euo pipefail\n'
            'SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"\n'
            'printf "SURVIVED\\n"\n',
            encoding="utf-8",
        )

        for mode, should_survive in (
            ("working", True),
            ("exits_nonzero", False),
            ("absent", False),
        ):
            bin_dir = _curated_bin(tmp_path, dirname_mode=mode)
            env = os.environ.copy()
            env["PATH"] = str(bin_dir)
            result = subprocess.run(
                [BASH, str(probe)],
                capture_output=True,
                text=True,
                env=env,
                timeout=30,
            )
            survived = "SURVIVED" in result.stdout
            assert survived is should_survive, (
                f"[{mode}] expected survived={should_survive}, got "
                f"{survived}. The probe mechanism does not do what the "
                f"tests above assume. stdout={result.stdout!r} "
                f"stderr={result.stderr!r}"
            )


# --- Structural half: the source cannot drift back, and neither can the prose.

#: The two anchors that bound the pre-trap region. Matched whole-line so a
#: mention inside a comment cannot be mistaken for the real thing.
_SET_STRICT_ANCHOR = re.compile(r"^set -euo pipefail\s*$")
_TRAP_ANCHOR = re.compile(r"^trap _emit_undetermined_on_exit EXIT\s*$")

#: A shell function definition opening at column 0, and its closing brace.
_FUNC_OPEN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\(\)\s*\{\s*$")
_FUNC_CLOSE = re.compile(r"^\}\s*$")

#: An assignment whose value is a single literal — a single-quoted string, a
#: double-quoted string, a ``$'...'`` string, or a bare word. Nothing here can
#: fail at runtime. Anything that does NOT match this shape is a command (or an
#: assignment carrying one), and a command can fail.
_LITERAL_ASSIGNMENT = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*="
    r"(?:'[^']*'|\"[^\"]*\"|\$'[^']*'|[A-Za-z0-9_./:@=-]*)\s*$"
)

#: Substitution constructs that execute something, or abort under ``set -u``.
#: Live inside double quotes as well as bare, which is why they are checked on
#: the raw line rather than after any quote stripping.
_EXECUTES_SOMETHING = ("$(", "`", ":?")


def _fallible_lines_before_trap(text: str) -> "list[tuple[int, str]]":
    """Return pre-trap lines that can fail at runtime.

    Walks from ``set -euo pipefail`` to the ``trap`` install, skipping blanks,
    comments and function bodies (a definition cannot fail; only calling it
    can, and calls happen below the trap). Every remaining line must be a
    literal assignment carrying no substitution.

    Args:
        text: Shell source of the hook.

    Returns:
        ``[(1-based line number, line)]`` for each fallible line. Empty means
        the pre-trap region cannot fail.

    Raises:
        AssertionError: If either anchor is missing or appears more than once,
            which would make an empty result meaningless.
    """
    lines = text.splitlines()
    starts = [i for i, ln in enumerate(lines) if _SET_STRICT_ANCHOR.match(ln)]
    traps = [i for i, ln in enumerate(lines) if _TRAP_ANCHOR.match(ln)]
    assert len(starts) == 1, (
        f"expected exactly 1 `set -euo pipefail` anchor, found {len(starts)}; "
        f"a zero-match or multi-match anchor makes this check vacuous"
    )
    assert len(traps) == 1, (
        f"expected exactly 1 trap-install anchor, found {len(traps)}; "
        f"a zero-match or multi-match anchor makes this check vacuous"
    )
    assert starts[0] < traps[0], "the trap is installed above `set -euo pipefail`"

    fallible: "list[tuple[int, str]]" = []
    in_function = False
    for offset in range(starts[0] + 1, traps[0]):
        raw = lines[offset]
        stripped = raw.strip()
        if in_function:
            if _FUNC_CLOSE.match(raw):
                in_function = False
            continue
        if not stripped or stripped.startswith("#"):
            continue
        if _FUNC_OPEN.match(raw):
            in_function = True
            continue
        if not _LITERAL_ASSIGNMENT.match(raw) or any(
            token in raw for token in _EXECUTES_SOMETHING
        ):
            fallible.append((offset + 1, raw))
    return fallible


#: The unconditional claim, and the qualifiers that bound it. The claim may
#: appear only alongside a qualifier — see the class docstring below.
_PAYLOAD_CLAIM = "CANNOT EXIT WITHOUT EMITTING A PAYLOAD"
_CLAIM_QUALIFIERS = (
    "FROM THE INSTALLATION OF THE EXIT TRAP ONWARD",
    "NOTHING THAT RUNS BEFORE",
)


def _unbounded_payload_claims(text: str) -> "list[str]":
    """Return occurrences of the payload guarantee that carry no boundary.

    Args:
        text: Shell source (or any text) to inspect.

    Returns:
        A context window per unqualified occurrence. Empty means every
        statement of the guarantee names its scope.
    """
    unbounded: "list[str]" = []
    for match in re.finditer(re.escape(_PAYLOAD_CLAIM), text):
        window = text[max(0, match.start() - 400) : match.end() + 400]
        if not any(qualifier in window for qualifier in _CLAIM_QUALIFIERS):
            unbounded.append(window)
    return unbounded


class TestIssue1588TrapCoversEveryFallibleCommand:
    """The header's guarantee and the code's behaviour, pinned to each other.

    Named in the hook header on purpose: the prose points at this class, and
    this class reads the prose. Either half drifting fails the other.

    The structural check removes a CATEGORY — "a command that can fail runs
    before the trap" — rather than pinning the SCRIPT_DIR line that happened
    to be the member. A check that named SCRIPT_DIR would go green the moment
    someone added a different early command, which is the guard-scoped-to-the-
    instance failure this file has already committed once (arm 4 denied
    ``secrets.yaml`` and allowed ``SECRETS.yaml``).
    """

    def test_regression_issue_1588_no_fallible_command_runs_before_the_trap(
        self,
    ) -> None:
        """Everything above the trap must be literal or a function definition."""
        fallible = _fallible_lines_before_trap(
            HOOK_PATH.read_text(encoding="utf-8")
        )
        assert fallible == [], (
            "these lines run BEFORE the exit trap is installed and can fail "
            "under `set -euo pipefail`, exiting with empty stdout — which "
            "Claude Code reads as consent. Move them below the trap, or make "
            "them unfallible:\n"
            + "\n".join(f"  line {num}: {line}" for num, line in fallible)
        )

    def test_regression_issue_1588_fallible_line_detector_has_a_positive_control(
        self,
    ) -> None:
        """POSITIVE CONTROL. The detector must flag what it claims to flag.

        Three shapes, because a detector that caught only command
        substitution would pass a bare command and a pipeline. An empty
        result from this detector is only evidence if it can produce a
        non-empty one.
        """
        for label, injected in (
            ("command_substitution", 'X="$(dirname -- "$0")"'),
            ("bare_command", "mkdir -p /tmp/whatever"),
            ("pipeline", "COUNT=$(ls | wc -l)"),
        ):
            source = (
                "set -euo pipefail\n"
                'SAFE="literal"\n'
                f"{injected}\n"
                "_emit_undetermined_on_exit() {\n"
                "  echo inside\n"
                "}\n"
                "trap _emit_undetermined_on_exit EXIT\n"
            )
            found = _fallible_lines_before_trap(source)
            assert [line for _, line in found] == [injected], (
                f"[{label}] the detector missed a fallible pre-trap line, so "
                f"its empty result on the real hook proves nothing. "
                f"found={found!r}"
            )

    def test_regression_issue_1588_fallible_line_detector_has_a_negative_control(
        self,
    ) -> None:
        """NEGATIVE CONTROL. The detector must not flag safe constructs.

        Includes the exact literal shapes the hook uses — a pattern string
        full of regex metacharacters, a ``$'...'`` newline, an empty string —
        because a detector that flagged those would force the fix to be
        undone to get green.
        """
        source = (
            "set -euo pipefail\n"
            'HOOK_NAME="a-hook.sh"\n'
            'LIB_DIR=""\n'
            "NL=$'\\n'\n"
            "DECISION_EMITTED=0\n"
            'DENY_PATTERNS="credentials|secrets|private.*key|\\.pem$|\\.git/"\n'
            "UNRENDERABLE_REASON_JSON='\"could not render\"'\n"
            "# a comment mentioning $(dirname) must not count\n"
            "helper() {\n"
            '  local x="$(date)"\n'
            "  printf '%s' \"$x\"\n"
            "}\n"
            "_emit_undetermined_on_exit() {\n"
            "  echo inside\n"
            "}\n"
            "trap _emit_undetermined_on_exit EXIT\n"
        )
        assert _fallible_lines_before_trap(source) == [], (
            "the detector flagged a construct that cannot fail; it would "
            "force the fix to be reverted to reach green"
        )

    def test_regression_issue_1588_header_claim_states_its_boundary(self) -> None:
        """The prose may not out-claim the code.

        The header carried ``THE HOOK CANNOT EXIT WITHOUT EMITTING A PAYLOAD``
        in capitals while 237 lines ran ahead of the trap. In this file that
        is not a cosmetic problem: a comment describing a known defect more
        confidently than the code delivers is exactly what let arms 2 and 3
        survive for months.
        """
        text = HOOK_PATH.read_text(encoding="utf-8")
        assert _PAYLOAD_CLAIM in text, (
            "the guarantee disappeared from the header entirely; it is the "
            "property this hook's whole cycle-2 design exists to provide"
        )
        unbounded = _unbounded_payload_claims(text)
        assert unbounded == [], (
            "the header states the no-silence guarantee without naming where "
            "it starts. It starts at the trap install; say so.\n"
            + "\n---\n".join(unbounded)
        )

    def test_regression_issue_1588_claim_checker_has_both_controls(self) -> None:
        """The claim checker must be able to both flag and pass."""
        unbounded_text = f"# So the property is: THE HOOK {_PAYLOAD_CLAIM}."
        assert _unbounded_payload_claims(unbounded_text), (
            "POSITIVE CONTROL FAILED: the checker passed an unqualified "
            "claim, so its empty result on the real header means nothing"
        )
        bounded_text = (
            f"# FROM THE INSTALLATION OF THE EXIT TRAP ONWARD, THE HOOK "
            f"{_PAYLOAD_CLAIM}."
        )
        assert _unbounded_payload_claims(bounded_text) == [], (
            "NEGATIVE CONTROL FAILED: the checker flags a properly bounded "
            "claim, so it cannot be satisfied by any honest wording"
        )


# ---------------------------------------------------------------------------
# Issue #1588 arm 5 — ARM 2 REPEATING, FOR A DIFFERENT TRANSPORT.
#
# The hook is bound with matcher ``Write|Edit|MultiEdit|NotebookEdit|mcp__.*``
# on every settings surface that registers it, so it FIRES for MCP editing
# tools. It then read ONE key, ``.tool_input.file_path`` — and MCP editors
# never send that key. Measured against the live script before the fix:
#
#   Write                              + file_path=.../credentials.json  deny
#   mcp__serena__replace_symbol_body   + relative_path=.../credentials   ALLOW
#   mcp__serena__replace_content       + relative_path=.../server.pem    ALLOW
#   mcp__serena__insert_after_symbol   + relative_path=.../secrets.yaml  ALLOW
#   mcp__serena__replace_symbol_body   + file_path=.../credentials.json  deny
#
# The last row is the conclusive control: the tool NAME was never the problem,
# the KEY was. ``// empty`` left the variable empty, every pattern missed, and
# the hook fell through to allow — the identical mechanism as arm 2, which read
# ``.parameters.file_path``, "a key that appears in no real Claude Code
# PreToolUse payload". Arm 2 was fixed for the built-in transports and stopped
# there.
#
# THE FIX DELEGATES. ``lib/tool_intent.py``'s ``write_targets()`` already owns
# the tool-name -> path-key mapping for every transport in the repo. Adding
# ``relative_path`` to the jq expression would be arm 4's defect in new
# clothes: a list that still falls through on the next server that names its
# argument ``path`` or ``target_file``.
#
# IT IS A UNION, NOT A REPLACEMENT. The jq ``file_path`` extraction is
# untouched and always contributes target 0, so the classifier being absent
# costs MCP coverage and never built-in coverage. The tests below prove that
# degradation on both arms rather than asserting it.
# ---------------------------------------------------------------------------

TOOL_INTENT_PATH = LIB_DIR / "tool_intent.py"


def _load_tool_intent():
    """Import the real classifier this hook now delegates to.

    Loaded from disk rather than restated, so the key-enumeration check below
    cross-validates two real sources instead of asserting against a stale
    third copy of ``PATH_KEYS``.
    """
    spec = importlib.util.spec_from_file_location(
        "_tool_intent_for_protect_sensitive_test", TOOL_INTENT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mcp_payload(tool_name: str, relative_path: str, **extra) -> dict:
    """Build a payload in the shape an MCP editor ACTUALLY sends.

    Verified against the live serena tool schemas: ``replace_symbol_body``
    requires ``name_path``/``relative_path``/``body``; ``replace_content``
    requires ``relative_path``/``needle``/``repl``/``mode``. Neither carries
    ``file_path`` — which is the whole of arm 5.

    The extra required arguments are included rather than trimmed to the one
    key under test: a payload the real tool would never send is a synthetic
    input, and this file's own history is a lesson in what synthetic inputs
    fail to catch.

    Args:
        relative_path: Value for ``tool_input.relative_path``.
        tool_name: A member of ``tool_intent.MCP_WRITE_TOOLS``.
        **extra: Additional ``tool_input`` members.

    Returns:
        A PreToolUse payload dict.
    """
    tool_input: dict = {"relative_path": relative_path}
    tool_input.update(extra)
    return {"tool_name": tool_name, "tool_input": tool_input}


def _non_comment_source(text: str) -> str:
    """Strip shell comments so prose is not read as code.

    The hook's header necessarily NAMES ``relative_path`` while explaining why
    the code must not enumerate it. Counting that explanation as an
    enumeration is the comment-blindness error one level down — the same one
    ``_greps_by_case`` and ``_count_refusal_emitters`` already guard against.
    """
    return "\n".join(_SHELL_COMMENT.sub("", ln) for ln in text.splitlines())


def _jq_extracted_tool_input_keys(text: str) -> "set[str]":
    """Return every ``.tool_input.<key>`` a jq expression reads in real code.

    Args:
        text: Shell source.

    Returns:
        The set of key names. ``{"file_path"}`` is the only acceptable value
        for this hook: one key, the built-in one, with every other transport
        resolved by the classifier instead.
    """
    return set(
        re.findall(r"\.tool_input\.([A-Za-z_][A-Za-z0-9_]*)", _non_comment_source(text))
    )


def _enumerated_transport_keys(text: str, path_keys: "tuple[str, ...]") -> "set[str]":
    """Return transport-specific path keys named in real code.

    ``file_path`` is excluded: it is the built-in key the union deliberately
    keeps reading directly. Every OTHER member of ``tool_intent.PATH_KEYS``
    appearing outside a comment means this file has started enumerating keys
    again instead of delegating.

    BOUNDARY, stated rather than overclaimed: only multi-word keys are
    checked. The bare key ``path`` is excluded because it is a substring of
    too many legitimate shell tokens (``PYTHONPATH``, ``pathlib``) to
    discriminate on, so a fix that enumerated ``path`` alone would slip past
    this instrument. The behavioural arms above are what actually prove the
    delegation; this removes the category a source read can see.

    Args:
        text: Shell source.
        path_keys: ``tool_intent.PATH_KEYS``, read from the real module.

    Returns:
        The set of offending key names. Empty means nothing is enumerated.
    """
    source = _non_comment_source(text)
    checked = [k for k in path_keys if k != "file_path" and "_" in k]
    return {
        key
        for key in checked
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(key)}(?![A-Za-z0-9_])", source)
    }


#: The REFUSING arm. Three different serena writers, three different DENY
#: classes, all carrying their target under ``relative_path``. Every one of
#: these was measured ALLOW before the fix.
_ARM5_MCP_DENY_CASES = [
    (
        "mcp__serena__replace_symbol_body",
        "app/credentials.json",
        {"name_path": "Config/load", "body": "def load(self): ..."},
    ),
    (
        "mcp__serena__replace_content",
        "certs/server.pem",
        {"needle": "BEGIN", "repl": "END", "mode": "literal"},
    ),
    (
        "mcp__serena__insert_after_symbol",
        "config/secrets.yaml",
        {"name_path": "root", "body": "token: abc"},
    ),
]

#: The PERMITTING arm. The same transport, the same key, ordinary paths. A
#: guard that refused every MCP write would pass every test above and be
#: useless — and ``docs/ENVIRONMENT.md`` carries the standing case-insensitive
#: ``.env`` negative control across to the new transport, where nothing tested
#: it before.
_ARM5_MCP_ALLOW_CASES = [
    (
        "mcp__serena__replace_symbol_body",
        "src/hello.py",
        {"name_path": "greet", "body": "def greet(): ..."},
    ),
    (
        "mcp__serena__replace_content",
        "docs/ENVIRONMENT.md",
        {"needle": "a", "repl": "b", "mode": "literal"},
    ),
]

#: MUST-NOT-REGRESS. The built-in transport, across every decision class and
#: both arms of the arm-4 case fix. The union exists so this table cannot move.
_ARM5_BUILTIN_CASES = [
    ("Write", "app/credentials.json", "deny"),
    ("Write", ".env", "ask"),
    ("Write", "src/hello.py", "allow"),
    ("Write", "config/SECRETS.yaml", "deny"),
    ("Write", "certs/a.PEM", "deny"),
]


@pytest.mark.parametrize("tool_name,relative_path,extra", _ARM5_MCP_DENY_CASES)
def test_regression_issue_1588_arm5_mcp_writers_are_refused(
    tool_name: str, relative_path: str, extra: dict, tmp_path: Path
) -> None:
    """THE REFUSING ARM. Every MCP write to a protected path was permitted.

    RED BEFORE: the hook read only ``.tool_input.file_path``, MCP editors send
    ``relative_path``, so ``FILE_PATH`` was empty, every pattern missed and the
    hook emitted ``allow``. GREEN AFTER: the classifier resolves the target and
    the same DENY patterns refuse it.

    The refusal must also be RECORDED. A guard that refuses a whole transport
    and logs nothing is invisible to triage for exactly the traffic that
    prompted the fix.
    """
    repo = _init_repo(tmp_path / "repo")
    result = _run_hook(_mcp_payload(tool_name, relative_path, **extra), cwd=repo)

    assert _decision(result) == "deny", (
        f"{tool_name} writing {relative_path} was PERMITTED. This hook's "
        f"matcher includes mcp__.*, so it fires for this call and claims to "
        f"check it. It carries its target under relative_path, not file_path "
        f"(#1588 arm 5). stdout={result.stdout!r}"
    )
    rows = _read_block_rows(repo)
    assert len(rows) == 1 and rows[0]["metadata"]["decision"] == "deny", (
        f"{tool_name}/{relative_path}: refusal not recorded; rows={rows!r}"
    )
    assert rows[0]["metadata"]["file_path"] == relative_path, (
        "the telemetry row must name the MCP target, not the empty file_path "
        f"the old extraction produced; rows={rows!r}"
    )


@pytest.mark.parametrize("tool_name,relative_path,extra", _ARM5_MCP_ALLOW_CASES)
def test_regression_issue_1588_arm5_mcp_permitting_arm(
    tool_name: str, relative_path: str, extra: dict, tmp_path: Path
) -> None:
    """THE PERMITTING ARM. Widening WHICH paths are seen must not widen WHICH are protected.

    A fix that classified every ``mcp__*`` call as a refusal would satisfy the
    refusing arm above and break every LSP edit in the repo. ``docs/
    ENVIRONMENT.md`` is the load-bearing case: it contains the letters
    "environment" and must not trip the ``.env`` pattern on this transport any
    more than it does on the built-in one.
    """
    repo = _init_repo(tmp_path / "repo")
    result = _run_hook(_mcp_payload(tool_name, relative_path, **extra), cwd=repo)

    assert _decision(result) == "allow", (
        f"{tool_name} writing the ordinary path {relative_path} was refused. "
        f"The arm-5 fix must widen WHICH PATHS ARE SEEN, never WHAT IS "
        f"PROTECTED. stdout={result.stdout!r}"
    )
    assert _read_block_rows(repo) == [], f"{relative_path}: allow must record nothing"


@pytest.mark.parametrize("tool_name,file_path,expected", _ARM5_BUILTIN_CASES)
def test_regression_issue_1588_arm5_builtin_transports_did_not_regress(
    tool_name: str, file_path: str, expected: str, tmp_path: Path
) -> None:
    """MUST NOT REGRESS. The built-in transport keeps every decision it had.

    The fix is a UNION — the jq ``file_path`` extraction is untouched and
    always contributes target 0 — precisely so this table cannot move. A fix
    that replaced the extraction instead of adding to it would put every row
    here at the mercy of an importable classifier.
    """
    repo = _init_repo(tmp_path / "repo")
    result = _run_hook(_write_payload(file_path, tool_name=tool_name), cwd=repo)

    assert _decision(result) == expected, (
        f"{tool_name} {file_path}: expected {expected}, got {result.stdout!r}. "
        f"The arm-5 fix changed built-in behaviour, which it must not."
    )


class TestIssue1588Arm5TheKeyNotTheName:
    """The discriminating control: the tool NAME was never the problem."""

    def test_regression_issue_1588_arm5_mcp_name_with_file_path_still_denies(
        self, tmp_path: Path
    ) -> None:
        """KEY CONTROL, measured before the fix and still required after.

        Feeding an MCP tool NAME together with a ``file_path`` key denied even
        on the broken hook. That is what proves the defect was the KEY and not
        a tool-name allowlist — and it is why a fix that special-cased
        ``mcp__*`` tool names would have been aimed at the wrong thing.

        It must keep denying after the fix, because the union still reads
        ``file_path`` for every tool. A fix that made the classifier
        AUTHORITATIVE would have flipped this to allow: ``write_targets``
        resolves ``relative_path`` first for a registered MCP writer, and a
        replacement extraction would have discarded the ``file_path`` the
        payload actually carried.
        """
        repo = _init_repo(tmp_path / "repo")
        payload = {
            "tool_name": "mcp__serena__replace_symbol_body",
            "tool_input": {
                "file_path": "app/credentials.json",
                "name_path": "Config/load",
                "body": "...",
            },
        }
        result = _run_hook(payload, cwd=repo)

        assert _decision(result) == "deny", (
            "an MCP tool name carrying a file_path key must still refuse; the "
            "union reads file_path for EVERY tool. If this went allow the fix "
            f"replaced the extraction instead of adding to it. {result.stdout!r}"
        )

    def test_regression_issue_1588_arm5_reason_names_the_mcp_target(
        self, tmp_path: Path
    ) -> None:
        """The model-visible reason must name the path that tripped the rule.

        Not cosmetic. ``permissionDecisionReason`` is the only channel the
        model reads, and the old extraction left ``FILE_PATH`` empty — so a
        refusal built on it would have said "Cannot write to sensitive file: "
        with nothing after the colon, telling the model nothing it could act
        on.
        """
        repo = _init_repo(tmp_path / "repo")
        result = _run_hook(
            _mcp_payload(
                "mcp__serena__replace_content",
                "certs/server.pem",
                needle="a",
                repl="b",
                mode="literal",
            ),
            cwd=repo,
        )
        reason = json.loads(result.stdout)["hookSpecificOutput"][
            "permissionDecisionReason"
        ]
        assert "certs/server.pem" in reason, (
            "the refusal did not name the path it refused; the reason is the "
            f"only thing the model sees. reason={reason!r}"
        )

    def test_regression_issue_1588_arm5_read_transport_is_still_seen(
        self, tmp_path: Path
    ) -> None:
        """A deliberate NON-change, pinned because it looks like one.

        MEASURED DISAGREEMENT WITH THE ARM-5 BRIEF, recorded rather than
        silently resolved: the brief listed ``Read`` + a protected
        ``file_path`` as a permitting arm that must "STAY allow". It was never
        allow. Measured on the unfixed hook, it was ``deny`` — the extraction
        read ``file_path`` for every tool name, ``Read`` included.

        It still denies, and that is the correct outcome for this change:

        * the union can only ADD a refusal, never remove one, which is the
          property that makes the built-in table above immovable;
        * making it allow would mean the guard SEES FEWER paths inside a
          change whose entire purpose is making it see more;
        * it is unreachable in production anyway — ``Read`` is not in this
          hook's matcher, so Claude Code never routes it here.

        Over-refusal on an unreachable transport is a cost worth naming and
        not worth paying down inside a fail-open fix.
        """
        repo = _init_repo(tmp_path / "repo")
        result = _run_hook(
            _write_payload("app/credentials.json", tool_name="Read"), cwd=repo
        )
        assert _decision(result) == "deny", (
            "Read + a protected file_path changed decision. The arm-5 union "
            "must not remove any refusal the hook already made. "
            f"stdout={result.stdout!r}"
        )


class TestIssue1588Arm5EveryTargetIsChecked:
    """``write_targets`` returns a LIST, and the decision covers all of it.

    A decision made from ``TARGETS[0]`` would be a guard scoped to the first
    element — the same shape as a guard scoped to the instance that prompted
    it, which this file has already committed once (arm 4 refused
    ``secrets.yaml`` and permitted ``SECRETS.yaml``).

    Deliberately authored to a DIFFERENT SHAPE than the reproducer. The bug
    was an MCP editor with one ``relative_path``; these arms are a ``Bash``
    command with two write targets, which is the only input in this repo that
    exercises the multi-target path at all. A refusing case built from another
    single-target MCP payload would prove nothing about the loop.
    """

    def test_regression_issue_1588_arm5_a_later_target_still_refuses(
        self, tmp_path: Path
    ) -> None:
        """The SECOND target trips the rule, and the reason names IT."""
        repo = _init_repo(tmp_path / "repo")
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "touch notes.txt; touch config/secrets.yaml"},
        }
        result = _run_hook(payload, cwd=repo)

        assert _decision(result) == "deny", (
            "a benign FIRST target masked a protected SECOND one, so the "
            "decision is scoped to TARGETS[0] rather than to every target. "
            f"stdout={result.stdout!r}"
        )
        reason = json.loads(result.stdout)["hookSpecificOutput"][
            "permissionDecisionReason"
        ]
        assert "config/secrets.yaml" in reason and "notes.txt" not in reason, (
            "the refusal must name the OFFENDING target, not whichever one "
            f"happened to be first. reason={reason!r}"
        )

    def test_regression_issue_1588_arm5_all_benign_targets_permit(
        self, tmp_path: Path
    ) -> None:
        """NEGATIVE CONTROL of a DIFFERENT SHAPE to the arm above.

        Same transport, same multi-target structure, no protected path. If
        this refused, the arm above would be passing because the loop refuses
        everything it walks — indistinguishable from a guard that cannot
        permit.
        """
        repo = _init_repo(tmp_path / "repo")
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "touch notes.txt; touch other.txt"},
        }
        result = _run_hook(payload, cwd=repo)

        assert _decision(result) == "allow", (
            "two ordinary write targets were refused; the multi-target loop "
            f"refuses everything it sees. stdout={result.stdout!r}"
        )
        assert _read_block_rows(repo) == [], "allow must record nothing"


class TestIssue1588Arm5DegradesToBuiltinNeverToAllow:
    """The classifier is an ADDITION. Losing it must cost only MCP coverage.

    The delegation spawns ``python3`` and imports ``tool_intent``. Both can be
    absent on a damaged host. The union exists so that when they are, the jq
    ``file_path`` extraction still stands and every built-in refusal survives
    — the same enforcement-over-telemetry ordering used everywhere else in
    this file, applied to classification.

    ``tool_intent`` is made unimportable by placing a module of that name in
    the hook's working directory, which is ``sys.path[0]`` for ``python3 -c``.
    That shadows the real module for the classifier call and leaves
    ``hook_telemetry`` untouched, so the degraded refusal is still recorded.
    """

    @staticmethod
    def _poison(repo: Path) -> None:
        """Shadow ``tool_intent`` with a module that raises on import."""
        (repo / "tool_intent.py").write_text(
            'raise ImportError("simulated: tool_intent unimportable")\n',
            encoding="utf-8",
        )

    def test_regression_issue_1588_arm5_unimportable_classifier_keeps_builtin_coverage(
        self, tmp_path: Path
    ) -> None:
        """THE CONSTRAINT. Built-in coverage must never depend on the classifier."""
        repo = _init_repo(tmp_path / "repo")
        self._poison(repo)

        result = _run_hook(
            _write_payload("app/credentials.json", tool_name="Write"), cwd=repo
        )
        assert _decision(result) == "deny", (
            "with tool_intent unimportable the hook stopped refusing a "
            "built-in write to credentials.json. The classifier was made "
            "load-bearing for the transport it was never needed for, which "
            f"turns a missing interpreter into a fail-open. {result.stdout!r}"
        )
        rows = _read_block_rows(repo)
        assert len(rows) == 1 and rows[0]["metadata"]["decision"] == "deny", (
            f"the degraded refusal was not recorded; rows={rows!r}"
        )

    def test_regression_issue_1588_arm5_degradation_probe_has_both_controls(
        self, tmp_path: Path
    ) -> None:
        """The probe must be shown to DO something, and to be what did it.

        POSITIVE CONTROL: with the shadow in place, an MCP write to a
        protected path goes back to ``allow`` — the pre-fix behaviour. That is
        the acceptable half of the degradation, and observing it is what
        proves the shadow actually reached the classifier rather than the
        payload being mishandled somewhere else.

        NEGATIVE CONTROL: the identical payload in an identical repo WITHOUT
        the shadow refuses. Without this half, a green positive control would
        be indistinguishable from a fix that never worked.
        """
        payload = _mcp_payload(
            "mcp__serena__replace_symbol_body",
            "app/credentials.json",
            name_path="Config/load",
            body="...",
        )

        poisoned = _init_repo(tmp_path / "poisoned")
        self._poison(poisoned)
        degraded = _decision(_run_hook(payload, cwd=poisoned))

        clean = _init_repo(tmp_path / "clean")
        enforced = _decision(_run_hook(payload, cwd=clean))

        assert enforced == "deny", (
            "NEGATIVE CONTROL FAILED: the same MCP payload does not refuse "
            "even with the classifier available, so the positive control "
            f"below proves nothing about the shadow. got {enforced!r}"
        )
        assert degraded == "allow", (
            "POSITIVE CONTROL FAILED: the shadow module did not make "
            "tool_intent unimportable, so this whole class is measuring "
            f"nothing. got {degraded!r}"
        )


class TestIssue1588Arm5DelegatesRatherThanEnumerates:
    """The fix must not become a list of key names.

    Adding ``relative_path`` to the jq expression would pass every behavioural
    arm above and still fall through on the next MCP server that names its
    argument ``path`` or ``target_file``. That is arm 4's defect exactly — "an
    alternation like ``SECRETS|Secrets|secrets`` is the same defect with more
    spellings" — one abstraction level up.

    Behaviour cannot show this: a hook that enumerated three keys and a hook
    that delegates are indistinguishable on every payload anyone has thought
    to write. Reading the source is the only instrument that can, so it is
    used here, with controls.
    """

    def test_regression_issue_1588_arm5_no_transport_key_is_enumerated(self) -> None:
        """No path key but the built-in one may appear in real code."""
        tool_intent = _load_tool_intent()
        # Premise: an empty key list would make this check vacuous.
        assert len(tool_intent.PATH_KEYS) >= 2, (
            f"tool_intent.PATH_KEYS is {tool_intent.PATH_KEYS!r}; with fewer "
            f"than two keys this check has nothing to look for"
        )
        source = HOOK_PATH.read_text(encoding="utf-8")

        assert _jq_extracted_tool_input_keys(source) == {"file_path"}, (
            "the hook reads more than one tool_input key with jq. Every "
            "transport-specific key belongs in tool_intent.PATH_KEYS, where "
            "one registration covers every enforcement site, not in a jq "
            f"expression here. found={_jq_extracted_tool_input_keys(source)}"
        )
        enumerated = _enumerated_transport_keys(source, tool_intent.PATH_KEYS)
        assert enumerated == set(), (
            f"the hook names transport-specific path keys {sorted(enumerated)} "
            f"in real code. That is arm 4 one level up: the list still falls "
            f"through on the next server that calls its argument something "
            f"else. Register the tool in tool_intent instead."
        )

    def test_regression_issue_1588_arm5_enumeration_detector_has_both_controls(
        self,
    ) -> None:
        """POSITIVE and NEGATIVE controls for both source readers above."""
        path_keys = ("file_path", "notebook_path", "relative_path", "path")

        # POSITIVE: the exact wrong fix this class exists to refuse.
        wrong_fix = (
            "FILE_PATH=$(echo \"$TOOL_USE\" | jq -r "
            "'.tool_input.file_path // .tool_input.relative_path // empty')\n"
        )
        assert _jq_extracted_tool_input_keys(wrong_fix) == {
            "file_path",
            "relative_path",
        }, "the jq reader missed a second extracted key"
        assert _enumerated_transport_keys(wrong_fix, path_keys) == {
            "relative_path"
        }, "the key reader missed an enumerated transport key"

        # NEGATIVE: prose naming the key is not code naming it. Without this
        # the hook's own header — which must explain relative_path to justify
        # NOT enumerating it — would fail its own check.
        prose = "# MCP editors carry their target under relative_path, not file_path\n"
        assert _enumerated_transport_keys(prose, path_keys) == set(), (
            "a comment explaining relative_path was counted as code"
        )
        assert _jq_extracted_tool_input_keys(prose) == set()

        # NEGATIVE: a substring must not masquerade as the key.
        lookalike = 'PYTHONPATH="$LIB_DIR" python3 -c "import pathlib"\n'
        assert _enumerated_transport_keys(lookalike, path_keys) == set(), (
            "a token merely CONTAINING a key name was flagged"
        )

    def test_regression_issue_1588_arm5_classifier_is_actually_consulted(self) -> None:
        """Q1: is the delegation CONNECTED, by a route a machine can check?

        The behavioural arms are the real proof. This adds the one thing they
        cannot: that the route runs through ``tool_intent.write_targets`` —
        the module the rest of the repo's enforcement sites already share —
        rather than through a second private mapping that happens to give the
        same answers today and drifts tomorrow.
        """
        source = _non_comment_source(HOOK_PATH.read_text(encoding="utf-8"))
        assert "import tool_intent" in source, (
            "the hook does not import the classifier in real code; if the "
            "MCP arms are green, something else is resolving those paths"
        )
        assert "tool_intent.write_targets(" in source, (
            "the hook imports tool_intent but does not call write_targets(); "
            "the canonical answer to 'what would this write?' is that "
            "function, not a reimplementation beside it"
        )
        assert TOOL_INTENT_PATH.exists(), (
            f"{TOOL_INTENT_PATH} is missing, so the import above resolves to "
            f"nothing and the hook silently degrades to built-ins only"
        )
