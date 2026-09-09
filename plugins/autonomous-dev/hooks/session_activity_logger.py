#!/usr/bin/env python3
"""
Session Activity Logger - Structured tool call logging for continuous improvement.

Logs every tool call as structured JSONL for post-session analysis by the
continuous-improvement-analyst agent.

Hooks: PostToolUse (after every tool call), Stop (after assistant response)

Captures:
    - Tool name and input summary (NOT full content)
    - Output status (success/error)
    - Active agent context (pipeline step)
    - Assistant text output (truncated summary)
    - Timestamp and session ID

Log location: .claude/logs/activity/{date}.jsonl
Logs are gitignored (local-only).

Environment Variables:
    ACTIVITY_LOGGING=true/false/debug (default: true)
        true  = compact summaries (file paths, content_length, truncated commands)
        debug = full raw stdin (complete tool_input + tool_output from Claude Code)
        false = disabled
    CLAUDE_SESSION_ID - Session identifier (provided by Claude Code)

Exit codes:
    0: Always (non-blocking hook)
"""

# Issue #953: Hook safety — wrap main() with safe_main so hook crashes never
# block Claude Code. The wrap is purely an outer safety net; success-path
# return codes are preserved (int return → exit code, sys.exit → propagated).
import sys as _sys_953  # alias to avoid colliding with hook-local sys imports
from pathlib import Path as _Path_953

_hook_dir_953 = _Path_953(__file__).resolve().parent
for _candidate_lib_953 in (
    _hook_dir_953.parent / "lib",                    # plugins/autonomous-dev/lib (dev)
    _hook_dir_953.parent.parent / "lib",             # ~/.claude/lib (installed)
    _Path_953.home() / ".claude" / "plugins" / "autonomous-dev" / "lib",  # marketplace
):
    if _candidate_lib_953.exists() and str(_candidate_lib_953) not in _sys_953.path:
        _sys_953.path.insert(0, str(_candidate_lib_953))

try:
    from hook_safety import safe_main as _safe_main_953
except ImportError:
    # Fallback: no-op wrapper so hooks still load if hook_safety is missing.
    def _safe_main_953(_fn):
        _result = _fn()
        if isinstance(_result, int):
            _sys_953.exit(_result)
        _sys_953.exit(0)


import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Issue #1726: canonical activity-log resolution lives in lib/path_utils.py.
# The lib bootstrap above already put lib/ on sys.path. If it is unavailable we
# fail loudly at call time rather than silently logging into the current
# directory — a cwd fallback is the defect this import replaces.
try:
    from path_utils import LogDirResolutionError, resolve_activity_log_dir
except ImportError:  # pragma: no cover - exercised only on a broken install
    resolve_activity_log_dir = None  # type: ignore[assignment]

    class LogDirResolutionError(RuntimeError):  # type: ignore[no-redef]
        """Fallback when lib/path_utils.py is not importable."""

# In-process cache for session date (avoids repeated file reads within same invocation)
_SESSION_DATE_CACHE: dict = {}

# Issue #1461: Phantom-then-real dedup for Task/Agent PostToolUse writes.
# Mirrors the guard at plugins/autonomous-dev/hooks/unified_session_tracker.py:1403-1453
# (which protects the SubagentStop code path). Claude Code sometimes fires a
# phantom Task PostToolUse entry ~31-32s after the Agent-tool start with low
# word count and a transcript_path that never exists on disk, followed by the
# real completion later. Both used to be written to .claude/logs/activity/*.jsonl,
# producing false [GHOST] findings in pipeline_intent_validator.
# Keys: (session_id, subagent_type) -> timestamp of first observed entry.
_PHANTOM_DEDUP_CACHE: dict[tuple[str, str], float] = {}
PHANTOM_DEDUP_WINDOW_SECONDS = 300  # 5 minutes; matches unified_session_tracker.py
PHANTOM_MIN_WORD_COUNT = 10  # Below this + missing transcript => classify phantom

# ============================================================================
# Subagent Invocation Cache helpers (Issue #1087)
# ============================================================================
#
# Claude Code's SubagentStop hook payload sometimes omits the agent_type
# and always reports duration_ms=0. We work around this by caching
# subagent invocations at PreToolUse time and popping them at
# SubagentStop. The cache lives in plugins/autonomous-dev/lib/
# subagent_invocation_cache.py so both this hook (PreToolUse writer) and
# unified_session_tracker.py (SubagentStop reader) can share it.

try:
    from subagent_invocation_cache import cache_invocation as _sic_cache_invocation
except ImportError:
    # Fallback: silently disable the cache so this hook still loads if
    # the lib is missing. SubagentStop instrumentation degrades to the
    # pre-#1087 behavior (empty subagent_type, duration_ms=0) — no crash.
    def _sic_cache_invocation(*_args, **_kwargs):
        return False


def _classify_task_agent_phantom(
    subagent_type: str,
    session_id: str,
    result_word_count: int,
    agent_transcript_path: str,
) -> tuple[str, dict]:
    """Issue #1461: Classify a Task/Agent PostToolUse entry against the
    phantom-then-real dedup gate.

    Two tiers, mirroring unified_session_tracker.py:1403-1453 semantics:

    * Tier 1 (transcript-existence): a low-word-count entry (< PHANTOM_MIN_WORD_COUNT)
      whose ``agent_transcript_path`` is set but does NOT exist on disk is
      classified ``phantom``. Real completions either have substantive output
      or a transcript that actually exists.
    * Tier 2 (phantom-then-real cache): keyed on ``(session_id, subagent_type)``,
      remembers the first observed timestamp. A second observation of the same
      key inside ``PHANTOM_DEDUP_WINDOW_SECONDS`` returns ``dedup_skip``.

    Fails OPEN: on missing/empty inputs or unexpected errors, returns
    ``("write", {})`` so a legit entry is never silently dropped.

    Returns:
        Tuple ``(verdict, extra_fields)``:
          * ``verdict="write"``: caller writes the normal PostToolUse entry.
          * ``verdict="phantom_skip"``: caller writes an audit-only entry
            ``__phantom_skip__:<agent>`` (or skips entirely).
          * ``verdict="dedup_skip"``: caller writes an audit-only entry
            ``__phantom_dedup_skip__:<agent>``.
        ``extra_fields`` carries diagnostic metadata for the audit entry.
    """
    try:
        agent = (subagent_type or "").strip()
        # Empty subagent_type => cannot dedup by identity; write and move on.
        if not agent:
            return ("write", {})

        # Tier 1: transcript-existence guard.
        transcript_missing = False
        if agent_transcript_path:
            try:
                transcript_missing = not Path(agent_transcript_path).exists()
            except Exception:
                transcript_missing = False  # fail open
        if (
            result_word_count < PHANTOM_MIN_WORD_COUNT
            and agent_transcript_path
            and transcript_missing
        ):
            return (
                "phantom_skip",
                {
                    "phantom_reason": "transcript_missing_low_words",
                    "phantom_word_count": result_word_count,
                    "phantom_transcript": agent_transcript_path,
                },
            )

        # Tier 2: phantom-then-real cache.
        key = (session_id or "unknown", agent)
        now = time.time()

        # Opportunistic cleanup (prevents unbounded growth).
        expired = [
            k for k, t in _PHANTOM_DEDUP_CACHE.items()
            if now - t > PHANTOM_DEDUP_WINDOW_SECONDS * 2
        ]
        for k in expired:
            del _PHANTOM_DEDUP_CACHE[k]

        if key in _PHANTOM_DEDUP_CACHE:
            last = _PHANTOM_DEDUP_CACHE[key]
            if now - last < PHANTOM_DEDUP_WINDOW_SECONDS:
                # Duplicate within window — refresh window and signal skip.
                _PHANTOM_DEDUP_CACHE[key] = now
                return (
                    "dedup_skip",
                    {
                        "phantom_reason": "duplicate_within_window",
                        "phantom_prev_ts": last,
                        "phantom_delta_s": round(now - last, 3),
                    },
                )
            # Outside window — treat as new invocation.
            _PHANTOM_DEDUP_CACHE[key] = now
            return ("write", {})

        # First observation for this key.
        _PHANTOM_DEDUP_CACHE[key] = now
        return ("write", {})
    except Exception:
        # Fail open on any error.
        return ("write", {})


def main():
    """Log tool call activity to structured JSONL."""
    # Opt-out check: false=off, true=summary, debug=full raw stdin
    log_level = os.environ.get("ACTIVITY_LOGGING", "true").lower()
    if log_level == "false":
        sys.exit(0)

    try:
        _start = time.monotonic()
        # Read hook input from stdin
        raw = sys.stdin.read().strip()
        if not raw:
            sys.exit(0)

        try:
            hook_input = json.loads(raw)
        except json.JSONDecodeError:
            sys.exit(0)

        # Detect hook type from input fields
        hook_event = hook_input.get("hook_event_name", "")

        if hook_event == "Stop":
            # Stop hook: capture assistant text output
            message = hook_input.get("last_assistant_message", "")
            if not message:
                sys.exit(0)
            if log_level == "debug":
                session_id = os.environ.get("CLAUDE_SESSION_ID") or hook_input.get("session_id") or "unknown"
                if session_id == "unknown":
                    sys.stderr.write(f"[session_activity_logger] WARNING: session_id resolved to 'unknown' for hook={hook_event}\n")
                entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "hook": "Stop",
                    "message": message[:10000],
                    "message_length": len(message),
                    "session_id": session_id,
                    "agent": os.environ.get("CLAUDE_AGENT_NAME", "main"),
                    "stop_hook_active": hook_input.get("stop_hook_active", False),
                    "debug": True,
                }
            else:
                session_id = os.environ.get("CLAUDE_SESSION_ID") or hook_input.get("session_id") or "unknown"
                if session_id == "unknown":
                    sys.stderr.write(f"[session_activity_logger] WARNING: session_id resolved to 'unknown' for hook={hook_event}\n")
                entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "hook": "Stop",
                    "message_preview": message[:1000],
                    "message_length": len(message),
                    "session_id": session_id,
                    "agent": os.environ.get("CLAUDE_AGENT_NAME", "main"),
                    "stop_hook_active": hook_input.get("stop_hook_active", False),
                }

            log_dir = _find_log_dir()
            log_dir.mkdir(parents=True, exist_ok=True)
            session_id = os.environ.get("CLAUDE_SESSION_ID") or hook_input.get("session_id") or "unknown"
            date_str = _get_session_date(session_id)
            log_file = log_dir / f"{date_str}.jsonl"
            with open(log_file, "a") as f:
                f.write(json.dumps(entry, separators=(",", ":")) + "\n")
            sys.exit(0)

        # UserPromptSubmit: capture user prompt activity
        if hook_event == "UserPromptSubmit":
            user_prompt = hook_input.get("user_prompt", "")
            if not user_prompt:
                sys.exit(0)

            session_id = os.environ.get("CLAUDE_SESSION_ID") or hook_input.get("session_id") or "unknown"
            if session_id == "unknown":
                sys.stderr.write(f"[session_activity_logger] WARNING: session_id resolved to 'unknown' for hook={hook_event}\n")
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "hook": "UserPromptSubmit",
                "prompt_preview": user_prompt[:500],
                "prompt_length": len(user_prompt),
                "session_id": session_id,
                "agent": os.environ.get("CLAUDE_AGENT_NAME", "main"),
            }

            log_dir = _find_log_dir()
            log_dir.mkdir(parents=True, exist_ok=True)
            date_str = _get_session_date(session_id)
            log_file = log_dir / f"{date_str}.jsonl"
            with open(log_file, "a") as f:
                f.write(json.dumps(entry, separators=(",", ":")) + "\n")
            sys.exit(0)

        # PreToolUse: cache subagent invocation data for SubagentStop correlation (Issue #1087).
        # Only Task/Agent invocations get cached — every other tool call is ignored at this branch
        # so we don't double-log PostToolUse later in main().
        if hook_event == "PreToolUse":
            pre_tool_name = hook_input.get("tool_name", "")
            if pre_tool_name in ("Task", "Agent"):
                pre_tool_input = hook_input.get("tool_input", {}) or {}
                pre_session_id = (
                    os.environ.get("CLAUDE_SESSION_ID")
                    or hook_input.get("session_id", "unknown")
                )
                pre_subagent_type = (pre_tool_input.get("subagent_type", "") or "").strip()
                # Issue #1484: mint one per-dispatch generation token shared by the
                # invocation cache entry and the sentinel payload. SubagentStop
                # recovers it from the cache and passes it to clear() for a
                # compare-and-delete that avoids the #1467 ABA disarm race.
                generation = uuid.uuid4().hex
                if pre_subagent_type:
                    _sic_cache_invocation(
                        pre_session_id,
                        pre_subagent_type,
                        start_time=time.time(),
                        description=pre_tool_input.get("description", ""),
                        generation=generation,
                    )
                # Issue #1296: write agent-dispatch sentinel so unified_pre_tool can distinguish
                # coordinator-direct edits from implementer-dispatched edits to protected paths.
                try:
                    from agent_dispatch_sentinel import write as _ads_write
                    _ads_write(
                        agent_name=pre_subagent_type if pre_subagent_type else "unknown",
                        generation=generation,
                    )
                except Exception as e:
                    # Issue #1484 (Fix 4): loud, non-blocking warning instead of silent pass.
                    sys.stderr.write(
                        f"[agent_dispatch_sentinel] WARNING: write failed: {e}\n"
                    )
            # Always exit on PreToolUse — we don't write a log entry from this hook
            # (unified_pre_tool.py owns PreToolUse activity logging).
            sys.exit(0)

        # PostToolUse: capture tool call activity
        tool_name = hook_input.get("tool_name", "unknown")
        tool_input = hook_input.get("tool_input", {})
        tool_output = hook_input.get("tool_output", {})

        # Issue #1448: slide the agent-dispatch sentinel TTL forward. Every tool use
        # while a dispatched agent is in flight is evidence the agent is still alive,
        # so the sentinel written at dispatch time (PreToolUse, above) stays valid for
        # the whole dispatch instead of expiring mid-run and blocking the implementer's
        # later protected-path edits (Issue #1296 gate in unified_pre_tool.py).
        # refresh() is a no-op when no sentinel exists (outside a dispatch window) and
        # when the sentinel is already stale, so it can never arm the gate on its own.
        # Note: with ACTIVITY_LOGGING=false this hook exits early and the gate falls
        # back to the fixed DEFAULT_TTL_SECONDS crash backstop.
        try:
            from agent_dispatch_sentinel import refresh as _ads_refresh
            _ads_refresh()
        except Exception as e:
            # Issue #1484 (Fix 4): loud, non-blocking warning instead of silent pass.
            sys.stderr.write(
                f"[agent_dispatch_sentinel] WARNING: refresh failed: {e}\n"
            )

        # Session ID: prefer env var, fall back to hook stdin JSON
        session_id = os.environ.get("CLAUDE_SESSION_ID") or hook_input.get("session_id") or "unknown"
        if session_id == "unknown":
            sys.stderr.write(f"[session_activity_logger] WARNING: session_id resolved to 'unknown' for hook={hook_event}\n")

        if log_level == "debug":
            # Debug mode: log full raw stdin (tool_input + tool_output)
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "hook": "PostToolUse",
                "tool": tool_name,
                "tool_input": tool_input,
                "tool_output": tool_output if isinstance(tool_output, dict) else {"raw": str(tool_output)[:5000]},
                "session_id": session_id,
                "agent": os.environ.get("CLAUDE_AGENT_NAME", "main"),
                "duration_ms": round((time.monotonic() - _start) * 1000),
                "debug": True,
            }
        else:
            # Normal mode: compact summaries only
            input_summary = _summarize_input(tool_name, tool_input)
            output_summary = _summarize_output(tool_output)
            output_summary = _add_result_word_count(tool_name, tool_output, output_summary)
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "hook": "PostToolUse",
                "tool": tool_name,
                "input_summary": input_summary,
                "output_summary": output_summary,
                "session_id": session_id,
                "agent": os.environ.get("CLAUDE_AGENT_NAME", "main"),
                "duration_ms": round((time.monotonic() - _start) * 1000),
                "success": output_summary.get("success", True),
            }
            # Enhanced Agent event tracking (Issue #526)
            # Agent events are critical for pipeline completeness validation
            # Log them with elevated priority to ensure they're captured
            if tool_name in ("Task", "Agent"):
                entry["priority"] = "high"
                entry["agent_event"] = True

            # Issue #1430: Cluster mode (BATCH_NO_WORKTREE=1) sub-issue visibility.
            # When the coordinator runs a cluster in-place on master (no worktree),
            # sub-issue Agent completions are otherwise indistinguishable from
            # top-level activity in the session log, making CIA post-session
            # analysis unable to attribute completions to specific issues.
            # Tag every entry with the batch context so downstream analyzers can
            # filter/group by cluster and current sub-issue.
            _bnw = os.environ.get("BATCH_NO_WORKTREE", "").strip().lower()
            if _bnw in ("1", "true", "yes"):
                entry["batch_no_worktree"] = True
                _cur_issue = _resolve_current_batch_issue()
                if _cur_issue:
                    entry["batch_issue_number"] = _cur_issue

        # Write to log file
        log_dir = _find_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)

        date_str = _get_session_date(session_id)
        log_file = log_dir / f"{date_str}.jsonl"

        # Issue #1461: phantom-then-real dedup for Task/Agent PostToolUse writes.
        # Runs BEFORE the write so phantom entries never land in the JSONL log
        # that pipeline_intent_validator + CIA consume. Only applies to Task/Agent;
        # every other tool call takes the fast path unchanged.
        if tool_name in ("Task", "Agent") and log_level != "debug":
            try:
                _out_summary = entry.get("output_summary") or {}
                _in_summary = entry.get("input_summary") or {}
                _subagent = _in_summary.get("subagent_type", "") or ""
                _rwc = int(_out_summary.get("result_word_count", 0) or 0)
                # transcript_path lives on the raw tool_output payload, not the
                # summary. Fall back to output_summary in case future refactors
                # promote it there.
                _tpath = ""
                if isinstance(tool_output, dict):
                    _tpath = (
                        tool_output.get("agent_transcript_path")
                        or tool_output.get("transcript_path")
                        or ""
                    )
                if not _tpath:
                    _tpath = _out_summary.get("agent_transcript_path", "") or ""
                _verdict, _extra = _classify_task_agent_phantom(
                    subagent_type=_subagent,
                    session_id=session_id,
                    result_word_count=_rwc,
                    agent_transcript_path=_tpath,
                )
            except Exception:
                _verdict, _extra = "write", {}

            if _verdict != "write":
                # Convert to audit-only entry.
                _audit_prefix = (
                    "__phantom_skip__" if _verdict == "phantom_skip"
                    else "__phantom_dedup_skip__"
                )
                _audit_entry = {
                    "timestamp": entry.get("timestamp"),
                    "hook": "PostToolUse",
                    "tool": tool_name,
                    "session_id": session_id,
                    "agent": entry.get("agent", "main"),
                    "phantom_verdict": _verdict,
                    "subagent_type_flag": f"{_audit_prefix}:{_subagent or 'unknown'}",
                    **_extra,
                }
                try:
                    with open(log_file, "a") as f:
                        f.write(json.dumps(_audit_entry, separators=(",", ":")) + "\n")
                except Exception:
                    pass  # non-blocking
                # Skip the normal write + downstream heartbeat/budget checks
                # (this entry was phantom noise, not a real agent completion).
                sys.exit(0)

        with open(log_file, "a") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")

        # Heartbeat check for batch session monitoring (Issue #526)
        _check_and_log_heartbeat(session_id, log_dir, date_str)

        # Budget check for Agent/Task completions (Issue #705 — non-blocking soft gate)
        if tool_name in ("Task", "Agent") and log_level != "debug":
            try:
                agent_duration_ms = output_summary.get("agent_duration_ms")
                agent_type = input_summary.get("subagent_type")
                if agent_type and agent_duration_ms and agent_duration_ms > 0:
                    _check_and_log_budget(
                        agent_type=agent_type,
                        duration_ms=agent_duration_ms,
                        session_id=session_id,
                        log_file=log_file,
                    )
            except Exception:
                # Non-blocking: budget check errors must never crash the hook
                pass

    except Exception:
        # Non-blocking: never crash Claude Code
        pass

    sys.exit(0)


def _extract_file_paths(text: str) -> list[str]:
    """Extract file paths with specific extensions from text.
    
    Returns deduplicated list of paths in order of first appearance.
    Caps path length at 512 chars to prevent ReDoS.
    """
    if not isinstance(text, str) or not text:
        return []
    
    # Conservative regex with bounded repetition to prevent ReDoS
    # Matches path-like tokens ending in target extensions
    pattern = r'(?<![\w./-])([\w./-]{1,512}\.(?:py|md|json|yaml|yml|sh))(?![\w./-])'
    matches = re.findall(pattern, text)
    
    # Deduplicate while preserving order
    return list(dict.fromkeys(matches))


def _summarize_input(tool_name: str, tool_input: dict) -> dict:
    """Create a compact summary of tool input (no full content)."""
    summary = {}

    if tool_name in ("Write", "Edit"):
        summary["file_path"] = tool_input.get("file_path", "")
        content = tool_input.get("content", tool_input.get("new_string", ""))
        summary["content_length"] = len(content) if isinstance(content, str) else 0
    elif tool_name == "Read":
        summary["file_path"] = tool_input.get("file_path", "")
    elif tool_name == "Bash":
        cmd = tool_input.get("command", "")
        # Truncate long commands
        summary["command"] = cmd[:200] if len(cmd) > 200 else cmd
        # Detect pipeline terminal actions
        if "git push" in cmd:
            summary["pipeline_action"] = "git_push"
        elif "gh issue close" in cmd:
            summary["pipeline_action"] = "issue_close"
        elif "git commit" in cmd:
            summary["pipeline_action"] = "git_commit"
        elif "pytest" in cmd:
            summary["pipeline_action"] = "test_run"
        elif "implement_pipeline_state" in cmd:
            summary["pipeline_action"] = "pipeline_state"
    elif tool_name in ("Glob", "Grep"):
        summary["pattern"] = tool_input.get("pattern", "")
        summary["path"] = tool_input.get("path", "")
    elif tool_name in ("Task", "Agent"):
        summary["description"] = tool_input.get("description", "")
        summary["subagent_type"] = tool_input.get("subagent_type", "")
        # Track agent invocations for pipeline completeness
        summary["pipeline_action"] = "agent_invocation"
        # Issue #906 / #882: detect background agent launch so the validator can
        # skip step_ordering checks for asynchronous agents (e.g., doc-master).
        # Only add the field when true; omitting it keeps legacy log format clean
        # and the parser defaults to False for backward compatibility.
        if tool_input.get("run_in_background"):
            summary["is_background"] = True
        # Word count for intent validation (Issue #367)
        prompt_text = tool_input.get("prompt", "")
        summary["prompt_word_count"] = len(prompt_text.split()) if isinstance(prompt_text, str) else 0
        
        # Issue #1280: Extract file paths for security-auditor and doc-master
        if summary["subagent_type"] in ("security-auditor", "doc-master"):
            paths = _extract_file_paths(prompt_text)
            summary["prompt_file_count"] = len(paths)
            summary["prompt_file_paths"] = paths
        
        # Batch context detection (Issue #526)
        if isinstance(prompt_text, str) and "BATCH CONTEXT" in prompt_text:
            summary["batch_mode"] = True
            # Prefer structured field from BATCH CONTEXT block (Issue #808),
            # fall back to inline Issue #N for backward compatibility
            issue_match = re.search(r'Issue Number:\s*(\d+)', prompt_text)
            if not issue_match:
                issue_match = re.search(r'Issue #(\d+)', prompt_text)
            if issue_match:
                summary["batch_issue_number"] = int(issue_match.group(1))
    elif tool_name == "Skill":
        summary["skill"] = tool_input.get("skill", "")
        args = tool_input.get("args", "")
        summary["args"] = str(args)[:200] if args else ""
        summary["pipeline_action"] = "skill_load"
    else:
        # Generic: include keys but not values
        summary["keys"] = list(tool_input.keys())[:5]

    return summary


def _summarize_output(tool_output: dict) -> dict:
    """Create a compact summary of tool output including errors."""
    if isinstance(tool_output, str):
        # Check if it looks like an error
        is_error = any(w in tool_output.lower() for w in ["error", "traceback", "failed", "exception"])
        summary = {"length": len(tool_output), "success": not is_error}
        if is_error:
            summary["error_preview"] = tool_output[:500]
        return summary

    if isinstance(tool_output, dict):
        has_error = tool_output.get("error", False)
        summary = {
            "success": not has_error,
            "has_output": bool(tool_output.get("output", "")),
        }
        if has_error:
            # Capture error details
            err = tool_output.get("error", "")
            if isinstance(err, str):
                summary["error_preview"] = err[:500]
            output_text = tool_output.get("output", "")
            if isinstance(output_text, str) and output_text:
                summary["output_preview"] = output_text[:500]
        return summary

    return {"success": True}


def _extract_usage_from_result(tool_output: str) -> dict:
    """Extract token usage data from Agent tool result text.

    Parses the ``<usage>`` block returned by the Agent tool, e.g.::

        <usage>total_tokens: 27169
        tool_uses: 2
        duration_ms: 18677</usage>

    Args:
        tool_output: Raw output text from the Agent/Task tool.

    Returns:
        Dict with ``total_tokens``, ``tool_uses``, and ``duration_ms`` keys
        (int values) for any fields found, or empty dict if no usage block.
    """
    if not tool_output or not isinstance(tool_output, str):
        return {}

    match = re.search(r"<usage>(.*?)</usage>", tool_output, re.DOTALL)
    if not match:
        return {}

    usage_text = match.group(1)
    result: dict = {}

    for key in ("total_tokens", "tool_uses", "duration_ms"):
        field_match = re.search(rf"{key}:\s*(\d+)", usage_text)
        if field_match:
            result[key] = int(field_match.group(1))

    return result


def _add_result_word_count(tool_name: str, tool_output: dict, summary: dict) -> dict:
    """Add result_word_count and token usage for Task/Agent tool outputs (Issue #367, #704, #925)."""
    if tool_name in ("Task", "Agent"):
        # Lazy import shared helper (Issue #925)
        import sys as _sys_wch
        _lib_dir_wch = str(Path(__file__).parent.parent / "lib")
        if _lib_dir_wch not in _sys_wch.path:
            _sys_wch.path.insert(0, _lib_dir_wch)
        from word_count_helpers import count_words_in_content

        # Modern Anthropic schema: toolUseResult uses "content" as list-of-text-blocks (Issue #925)
        content = tool_output.get("content") if isinstance(tool_output, dict) else None
        word_count = count_words_in_content(content)

        # Fall back to legacy flat "output" string if content is absent or yields 0 words
        output_text = ""
        if content is None or word_count == 0:
            if isinstance(tool_output, dict):
                output_text = str(tool_output.get("output", ""))
            elif isinstance(tool_output, str):
                output_text = tool_output
            word_count = len(output_text.split()) if output_text else 0

        summary["result_word_count"] = word_count

        # Build output_text for usage extraction (Issue #704)
        # Prefer the flat-string path; if content is a list-of-blocks, concatenate text blocks.
        if not output_text and isinstance(content, list):
            output_text = "\n".join(
                b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"
            )

        # Extract token usage from <usage> block (Issue #704)
        usage = _extract_usage_from_result(output_text)
        summary["total_tokens"] = usage.get("total_tokens", 0)
        summary["tool_uses"] = usage.get("tool_uses", 0)
        summary["agent_duration_ms"] = usage.get("duration_ms", 0)
    return summary


def _get_session_date(session_id: str) -> str:
    """Get the pinned date for a session, preventing cross-midnight mislabeling.

    Each session gets a date pinned on first activity. If the session spans
    midnight, all entries still use the original date so they land in the
    same log file.

    Uses a small file for persistence across subprocess invocations, with
    an in-process cache to avoid repeated file reads.

    Args:
        session_id: The Claude session identifier.

    Returns:
        Date string in YYYY-MM-DD format.
    """
    # Check in-process cache first
    if session_id in _SESSION_DATE_CACHE:
        return _SESSION_DATE_CACHE[session_id]

    # Check for session date file
    log_dir = _find_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    date_file = log_dir / f".session_date_{session_id}"

    try:
        if date_file.exists():
            stored_date = date_file.read_text().strip()
            # Validate freshness: if file is older than 24 hours, start fresh
            file_age_seconds = time.time() - date_file.stat().st_mtime
            if file_age_seconds < 86400 and stored_date:
                _SESSION_DATE_CACHE[session_id] = stored_date
                return stored_date
    except Exception:
        pass

    # Fall back to current date and persist it
    date_str = datetime.now().strftime("%Y-%m-%d")
    try:
        date_file.write_text(date_str)
    except Exception:
        pass
    _SESSION_DATE_CACHE[session_id] = date_str
    return date_str


def _resolve_current_batch_issue() -> int | None:
    """Return the currently-processing issue number in BATCH_NO_WORKTREE mode.

    Issue #1430: In cluster mode (`BATCH_NO_WORKTREE=1`) the orchestrator
    persists batch state at ``<cwd>/.claude/batch_state.json`` with a
    ``current_index`` cursor into ``issues[]``. Reading that lets us
    attribute in-flight sub-issue activity in the session log so CIA
    post-session analysis can group by issue.

    Fallbacks (env-first for cheap resolution):
    1. ``CURRENT_BATCH_ISSUE`` env var (set by coordinator per iteration).
    2. ``<cwd>/.claude/batch_state.json`` — ``issues[current_index]``.

    Returns None on any failure (missing state, invalid JSON, index out
    of range). Non-blocking: never raises.
    """
    try:
        env_val = os.environ.get("CURRENT_BATCH_ISSUE", "").strip()
        if env_val.isdigit():
            return int(env_val)
    except Exception:
        pass
    try:
        state_path = Path.cwd() / ".claude" / "batch_state.json"
        if not state_path.exists():
            return None
        data = json.loads(state_path.read_text())
        issues = data.get("issues") or []
        idx = int(data.get("current_index", 0))
        if 0 <= idx < len(issues):
            candidate = issues[idx]
            if isinstance(candidate, int):
                return candidate
            if isinstance(candidate, str) and candidate.isdigit():
                return int(candidate)
    except Exception:
        return None
    return None


def _find_log_dir() -> Path:
    """Find the project's .claude/logs/activity directory.

    Delegates to :func:`path_utils.resolve_activity_log_dir` — worktree parent
    (Issue #755) -> ``CLAUDE_PROJECT_DIR`` -> project root -> loud failure.

    Issue #1726: this function used to walk up from ``Path.cwd()`` to the first
    ``.claude/`` and fall back to ``cwd/.claude/logs/activity``. A stray
    ``.claude/`` below the repo root (two of them existed inside shipped plugin
    source) therefore captured every hook invoked from a deeper directory,
    permanently, and post-session analysis read a partial record for months.

    Returns:
        Absolute path to the activity-log directory (not created here).

    Raises:
        LogDirResolutionError: If no project root can be resolved.
    """
    if resolve_activity_log_dir is None:
        raise LogDirResolutionError(
            "lib/path_utils.py is not importable, so the activity-log directory "
            "cannot be tied to a project root.\n"
            "Expected: plugins/autonomous-dev/lib/ on sys.path\n"
            "Refusing to fall back to the current directory (Issue #1726)"
        )
    # Normalise through the module-level Path so tests that patch
    # ``session_activity_logger.Path`` still hand a real path to the resolver.
    return resolve_activity_log_dir(start_path=Path(str(Path.cwd())))


def _check_and_log_budget(
    agent_type: str,
    duration_ms: int | float,
    session_id: str,
    log_file: Path,
) -> None:
    """Check agent duration against time budget and log a BudgetWarning entry if needed.

    This is a soft gate — never blocks. Writes an additional JSONL entry tagged
    "BudgetWarning" when an agent uses >= warning_pct of its budget or exceeds it.

    Args:
        agent_type: The pipeline agent type (e.g. "implementer").
        duration_ms: Agent wall-clock duration in milliseconds.
        session_id: Current Claude session identifier.
        log_file: Path to the active JSONL log file for writing.
    """
    try:
        # Lazy import so that the hook still works even if the library is unavailable
        import sys as _sys
        _lib_dir = str(Path(__file__).parent.parent / "lib")
        if _lib_dir not in _sys.path:
            _sys.path.insert(0, _lib_dir)
        from pipeline_timing_analyzer import check_budget_violation, format_budget_warning

        duration_seconds = duration_ms / 1000.0
        violation = check_budget_violation(agent_type, duration_seconds)
        if violation is None:
            return

        warning_text = format_budget_warning(violation)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hook": "BudgetWarning",
            "agent_type": agent_type,
            "level": violation["level"],
            "duration_seconds": violation["duration"],
            "budget_seconds": violation["budget"],
            "pct_used": round(violation["pct_used"], 3),
            "session_id": session_id,
            "message": warning_text,
        }
        with open(log_file, "a") as _f:
            _f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except Exception:
        pass  # Non-blocking: never crash the hook


def _check_and_log_heartbeat(session_id: str, log_dir: Path, date_str: str):
    """Write a heartbeat entry if >5 minutes since last log for this session.

    Helps detect when the logger stops receiving events in batch mode (Issue #526).

    Args:
        session_id: The Claude session identifier.
        log_dir: Directory where log files are written.
        date_str: Date string for the log file name (YYYY-MM-DD).
    """
    try:
        heartbeat_file = log_dir / f".heartbeat_{session_id}"
        now = time.time()

        if heartbeat_file.exists():
            last_beat = float(heartbeat_file.read_text().strip())
            if now - last_beat < 300:  # 5 minutes
                return

        # Write heartbeat
        heartbeat_file.write_text(str(now))

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hook": "Heartbeat",
            "session_id": session_id,
            "agent": os.environ.get("CLAUDE_AGENT_NAME", "main"),
            "message": "Logger heartbeat - still receiving events",
        }
        log_file = log_dir / f"{date_str}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(entry, separators=(",", ":")) + "\n")
    except Exception:
        pass  # Non-blocking



# Issue #1012 (W0): Per-hook timing telemetry. Best-effort, never raises.
# Records duration + decision_shape to ~/.claude/logs/hook_timings_YYYY-MM-DD.jsonl.
try:
    from hook_timing import HookTimer  # type: ignore[import-not-found]
except ImportError:
    # Fallback: no-op stub so hooks keep working if hook_timing is missing.
    class HookTimer:  # type: ignore[no-redef]
        def __init__(self, *_, **__): pass
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def set_decision_shape(self, _): pass

_HOOK_TIMER_NAME = _Path_953(__file__).name


def _timed_main():  # type: ignore[no-redef]
    with HookTimer(_HOOK_TIMER_NAME):
        return main()

if __name__ == "__main__":
    _safe_main_953(_timed_main)
