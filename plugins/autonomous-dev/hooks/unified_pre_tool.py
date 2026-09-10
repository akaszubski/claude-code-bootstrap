#!/usr/bin/env python3
"""
Unified PreToolUse Hook - Consolidated Permission & Security Validation

This hook consolidates five PreToolUse validators into a single dispatcher:
0. Sandbox Enforcer (sandbox_enforcer.py) - Command classification & sandboxing (Issue #171)
1. MCP Security Validator (pre_tool_use.py) - Path traversal, injection, SSRF protection
2. Agent Authorization (enforce_implementation_workflow.py) - Pipeline agent detection
3. Batch Permission Approver (batch_permission_approver.py) - Permission batching
5. Prompt Integrity (Issue #695) - Minimum word count for critical agents
6. Prompt Quality (Issue #842) - Anti-pattern detection for agent/command .md files

Native Tool Fast Path:
- Native Claude Code tools (Read, Write, Edit, Bash, Task, etc.) bypass all 4 validation layers
- These tools are governed by settings.json permissions, not by this hook
- This avoids unwanted permission prompts for built-in tools
- See NATIVE_TOOLS set below for complete list

Decision Logic:
- If tool is native → skip all layers, return "allow" (settings.json governs)
- If project is not autonomous-dev → skip enforcement layers, return "allow"
- If ANY validator returns "deny" → output "deny" (block operation)
- If ALL validators return "allow" → output "allow" (approve operation)
- Otherwise → output "ask" (prompt user)

Layer Execution Order (short-circuit on deny):
0. Layer 0 (Sandbox): Command classification (SAFE → auto-approve, BLOCKED → deny, NEEDS_APPROVAL → continue)
1. Layer 1 (MCP Security): Path traversal, injection, SSRF checks
2. Layer 2 (Agent Auth): Pipeline agent detection
3. Layer 3 (Batch Permission): Permission batching
5. Layer 5 (Prompt Integrity): Minimum word count for critical agents (Issue #695)
6. Layer 6 (Prompt Quality): Anti-pattern detection for agent/command .md writes (Issue #842)

Environment Variables:
- SANDBOX_ENABLED: Enable/disable sandbox layer (default: false for opt-in)
- SANDBOX_PROFILE: Sandbox profile (default: development)
- PRE_TOOL_MCP_SECURITY: Enable/disable MCP security (default: true)
- PRE_TOOL_AGENT_AUTH: Enable/disable agent authorization (default: true)
- PRE_TOOL_BATCH_PERMISSION: Enable/disable batch permission (default: false)
- MCP_AUTO_APPROVE: Enable/disable auto-approval (default: false)
- PRE_TOOL_PIPELINE_ORDERING: Enable/disable pipeline ordering gate (default: true)

Input (stdin):
{
  "tool_name": "Bash",
  "tool_input": {"command": "pytest tests/"}
}

Output (stdout):
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask",
    "permissionDecisionReason": "Combined validator reasons"
  }
}

Exit code: 0 (always - let Claude Code process the decision)

Date: 2026-01-02
Issue: GitHub #171 (Sandboxing for reduced permission prompts)
Agent: implementer
"""

import importlib.util
import json
import re
import shlex
import subprocess
import sys
import time
import os
from pathlib import Path
from typing import Any, Dict, Tuple, List, Optional

# Module-level session_id extracted from hook stdin (set in main()).
# Logging functions fall back to this when CLAUDE_SESSION_ID env var is absent.
_session_id: str = "unknown"

# Defensive import of python_write_detector (Issue #589).
# Falls back to None so inline regex continues to work if import fails.
_python_write_detector = None
try:
    _hook_path = Path(__file__).resolve().parent
    _lib_candidates = [
        _hook_path.parent / "lib",           # plugins/autonomous-dev/lib
        _hook_path.parents[2] / "lib",        # fallback
    ]
    for _lib_dir in _lib_candidates:
        _detector_path = _lib_dir / "python_write_detector.py"
        if _detector_path.exists():
            import importlib.util as _ilu
            _spec = _ilu.spec_from_file_location("python_write_detector", str(_detector_path))
            if _spec and _spec.loader:
                _python_write_detector = importlib.util.module_from_spec(_spec)
                _spec.loader.exec_module(_python_write_detector)
            break
except Exception:
    _python_write_detector = None  # Fallback: inline regex in _extract_bash_file_writes

# Defensive import of tool_intent (Issue #971) — shell+tool classifier that
# delegates python -c parsing to python_write_detector. _extract_bash_file_writes
# is now a thin shim around tool_intent.write_targets when available.
# Falls back to legacy regex via _extract_bash_file_writes_legacy on import failure.
_tool_intent = None
try:
    _hook_path_ti = Path(__file__).resolve().parent
    _lib_candidates_ti = [
        _hook_path_ti.parent / "lib",           # plugins/autonomous-dev/lib
        _hook_path_ti.parents[2] / "lib",        # fallback
    ]
    for _lib_dir_ti in _lib_candidates_ti:
        _ti_path = _lib_dir_ti / "tool_intent.py"
        if _ti_path.exists():
            import importlib.util as _ilu_ti
            _spec_ti = _ilu_ti.spec_from_file_location("tool_intent", str(_ti_path))
            if _spec_ti and _spec_ti.loader:
                _tool_intent = importlib.util.module_from_spec(_spec_ti)
                _spec_ti.loader.exec_module(_tool_intent)
            break
except Exception:
    _tool_intent = None  # Fallback: _extract_bash_file_writes_legacy retains old behavior

# Issue #1503: transport-independent write classification for every gate in
# this module. _tool_intent is loaded via spec_from_file_location above, so
# attribute probing (hasattr) is the only available capability detection —
# a stale install may expose classify/write_targets but not is_write.
#
# The fallback must NOT fail closed to "deny" — denying on a missing library
# would block Read, which is catastrophic.
#
# Issue #1682: that reasoning is correct, but the fallback USED to be nothing
# but this four-tuple, which enumerates NATIVE transports only. So with
# tool_intent unavailable, every MCP write transport classified as a non-write
# and walked through the #1435 hard floor. Measured against a lib tree with
# tool_intent.py absent: Write/Edit denied, mcp__serena__replace_symbol_body
# and mcp__serena__rename_symbol both ALLOWED on plugins/.../hooks/. is_write
# was made transport-independent by #1503; its fallback was not.
#
# Refusing to deny READS does not require classifying MCP WRITES as
# non-writes — those are separable, and the shape rule below separates them.
# The tuple stays as the fast path for MultiEdit, whose content lives under
# edits[].new_string and so has no top-level content key to shape-match.
_FALLBACK_WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")

# Minimal copy of tool_intent's SHAPE RULE (its PATH_KEYS x CONTENT_KEYS
# conjunction), deliberately NOT a copy of its MCP_WRITE_TOOLS list: an
# allowlist only refuses the writers someone already noticed, which moves the
# hole to the next unenumerated MCP editor instead of closing it.
_FALLBACK_PATH_KEYS = ("file_path", "notebook_path", "relative_path", "path")
_FALLBACK_CONTENT_KEYS = ("content", "new_string", "body", "repl", "new_source")


def _ti_has_key(tool_input, keys):
    """True when a non-empty string lives under any of ``keys``."""
    if not isinstance(tool_input, dict):
        return False
    for key in keys:
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return True
    return False


def _ti_fallback_is_write(tool_name, tool_input):
    """Classify a write WITHOUT tool_intent, by shape rather than by name.

    A tool carrying BOTH a filesystem path AND content is writing that content
    somewhere, whatever its name or transport. The conjunction is what keeps
    reads permitted: Read/Grep carry a path but no content, and
    mcp__serena__find_symbol carries ``relative_path`` but no content
    argument, so both stay allowed.
    """
    if tool_name in _FALLBACK_WRITE_TOOLS:
        return True
    if not _ti_has_key(tool_input, _FALLBACK_PATH_KEYS):
        return False
    return _ti_has_key(tool_input, _FALLBACK_CONTENT_KEYS)


def _ti_is_write(tool_name, tool_input):
    """Transport-independent write test with a stale-install fallback (#1503).

    Degrades in capability order (#1682): ``is_write`` -> ``classify`` ->
    shape. The ``classify`` rung matters because the two failure modes differ
    — a stale install that lost ``is_write`` still carries the authoritative
    MCP_WRITE_TOOLS registry, which catches the content-less writers
    (rename_symbol, delete_lines) that no shape test can see. Every rung is
    transport-independent; none enumerates MCP tool names.
    """
    if _tool_intent is not None:
        if hasattr(_tool_intent, "is_write"):
            try:
                return _tool_intent.is_write(tool_name, tool_input)
            except Exception:
                pass
        if hasattr(_tool_intent, "classify"):
            try:
                return _tool_intent.classify(tool_name, tool_input) == "WRITE"
            except Exception:
                pass
    return _ti_fallback_is_write(tool_name, tool_input)


def _ti_write_targets(tool_name, tool_input):
    """Resolve a tool call's write target paths, with a stale-install fallback."""
    if _tool_intent is not None and hasattr(_tool_intent, "write_targets"):
        try:
            targets = _tool_intent.write_targets(tool_name, tool_input)
            if targets:
                return list(targets)
        except Exception:
            pass
    if not isinstance(tool_input, dict):
        return []
    for _key in ("file_path", "notebook_path", "relative_path", "path"):
        _value = tool_input.get(_key)
        if isinstance(_value, str) and _value:
            return [_value]
    return []


def _ti_first_write_target(tool_name, tool_input):
    """Return the first write target path, or "" when there is none."""
    targets = _ti_write_targets(tool_name, tool_input)
    return targets[0] if targets else ""


def _ti_write_tool_names():
    """Every registered write tool name (native + MCP), with a stale fallback."""
    names = set(_FALLBACK_WRITE_TOOLS)
    if _tool_intent is not None:
        for _attr in ("WRITE_TOOLS", "MCP_WRITE_TOOLS"):
            try:
                names |= set(getattr(_tool_intent, _attr, ()) or ())
            except Exception:
                pass
    return frozenset(names)


# Stale-install fallback for _ti_mcp_read_tools. Issue #1503 deleted the
# module-local _PLAN_EXIT_MCP_READONLY frozenset in favour of the canonical
# tool_intent.MCP_READ_TOOLS registry (which is a strict superset — it also
# knows the serena read surface, which this list over-blocked at the
# plan_exited stage). This copy exists ONLY so an old installed tool_intent.py
# without MCP_READ_TOOLS does not regress plan-exit behaviour.
_PLAN_EXIT_MCP_READONLY_FALLBACK: "frozenset[str]" = frozenset({
    "mcp__playwright__browser_snapshot",
    "mcp__playwright__browser_take_screenshot",
    "mcp__playwright__browser_console_messages",
    "mcp__playwright__browser_network_requests",
    "mcp__claude_ai_Hugging_Face__hf_doc_search",
    "mcp__claude_ai_Hugging_Face__hf_doc_fetch",
    "mcp__claude_ai_Hugging_Face__hub_repo_search",
    "mcp__claude_ai_Hugging_Face__paper_search",
    "mcp__claude_ai_Hugging_Face__space_search",
    "mcp__claude_ai_Hugging_Face__hf_whoami",
    "mcp__claude_ai_Hugging_Face__hf_hub_query",
    "mcp__claude_ai_Hugging_Face__hub_repo_details",
    "mcp__claude_ai_Gmail__list_drafts",
    "mcp__claude_ai_Gmail__list_labels",
    "mcp__claude_ai_Gmail__get_thread",
    "mcp__claude_ai_Gmail__search_threads",
    "mcp__claude_ai_Google_Calendar__list_calendars",
    "mcp__claude_ai_Google_Calendar__list_events",
    "mcp__claude_ai_Google_Calendar__get_event",
    "mcp__claude_ai_Google_Drive__list_recent_files",
    "mcp__claude_ai_Google_Drive__search_files",
    "mcp__claude_ai_Google_Drive__read_file_content",
    "mcp__claude_ai_Google_Drive__get_file_metadata",
    "mcp__claude_ai_Google_Drive__get_file_permissions",
})


def _ti_mcp_read_tools():
    """The canonical read-only MCP allowlist, with a stale-install fallback."""
    if _tool_intent is not None:
        try:
            registry = getattr(_tool_intent, "MCP_READ_TOOLS", None)
            if registry:
                return frozenset(registry)
        except Exception:
            pass
    return _PLAN_EXIT_MCP_READONLY_FALLBACK

# Defensive import of hook_recovery (Issue #970).
# Telemetry-only. If unavailable, log_block_with_recovery becomes a no-op so
# the hook gate continues to function unchanged.
try:
    _hook_path_hr = Path(__file__).resolve().parent
    _lib_candidates_hr = [
        _hook_path_hr.parent / "lib",           # plugins/autonomous-dev/lib
        _hook_path_hr.parents[2] / "lib",        # fallback
        Path.home() / ".claude" / "lib",        # user-global install
    ]
    _hr_loaded = False
    for _lib_dir_hr in _lib_candidates_hr:
        _hr_path = _lib_dir_hr / "hook_recovery.py"
        if _hr_path.exists():
            import importlib.util as _ilu_hr
            _spec_hr = _ilu_hr.spec_from_file_location("hook_recovery", str(_hr_path))
            if _spec_hr and _spec_hr.loader:
                _hook_recovery_mod = importlib.util.module_from_spec(_spec_hr)
                _spec_hr.loader.exec_module(_hook_recovery_mod)
                log_block_with_recovery = _hook_recovery_mod.log_block_with_recovery
                is_recovery_disabled = _hook_recovery_mod.is_recovery_disabled
                _hr_loaded = True
            break
    if not _hr_loaded:
        raise ImportError("hook_recovery.py not found in any candidate location")
except Exception:
    def log_block_with_recovery(**kwargs):  # type: ignore[no-redef]
        return None

    def is_recovery_disabled() -> bool:  # type: ignore[no-redef]
        return False

# Defensive import of hook_telemetry (Issue #972, #942-D capstone).
# Provides a decorator that emits a structured JSONL row on every "deny"
# decision flowing through ``output_decision``. Falls back to a no-op
# decorator if the library is unavailable so the hook continues to
# function unchanged.
try:
    _hook_path_ht = Path(__file__).resolve().parent
    _lib_candidates_ht = [
        _hook_path_ht.parent / "lib",           # plugins/autonomous-dev/lib
        _hook_path_ht.parents[2] / "lib",        # fallback
        Path.home() / ".claude" / "lib",        # user-global install
    ]
    _ht_loaded = False
    for _lib_dir_ht in _lib_candidates_ht:
        _ht_path = _lib_dir_ht / "hook_telemetry.py"
        if _ht_path.exists():
            import importlib.util as _ilu_ht
            _spec_ht = _ilu_ht.spec_from_file_location("hook_telemetry", str(_ht_path))
            if _spec_ht and _spec_ht.loader:
                _hook_telemetry_mod = importlib.util.module_from_spec(_spec_ht)
                _spec_ht.loader.exec_module(_hook_telemetry_mod)
                block_event_decorator = _hook_telemetry_mod.block_event_decorator
                log_block_event = _hook_telemetry_mod.log_block_event
                _ht_loaded = True
            break
    if not _ht_loaded:
        raise ImportError("hook_telemetry.py not found in any candidate location")
except Exception:
    def block_event_decorator(hook_name):  # type: ignore[no-redef]
        def _decorator(fn):
            return fn
        return _decorator

    def log_block_event(**kwargs):  # type: ignore[no-redef]
        return None

# Module-level agent_type extracted from hook stdin JSON (set in main()).
# Used by _get_active_agent_name() as primary identity source (Issue #591).
_agent_type: str = ""

# Issue #1263: In-process fire-once-per-turn token cache for the SWE router.
# Keyed by session_id; value is the user-message token most recently observed
# for that session. Process restart resets this — acceptable for log-only
# Phase A (over-logging on hook restart, not under-logging). Phase B should
# persist this to /tmp/router_last_token_<sid>.json for restart-safety.
_LAST_ROUTE_TOKEN_BY_SESSION: Dict[str, str] = {}


def _maybe_invoke_swe_router(tool_name: str, tool_input: Dict[str, Any],
                             session_id: str) -> None:
    """Issue #1263: Phase 2 SWE router dispatcher (log-only).

    Extracted from ``main()`` so it can be exercised directly in unit
    tests. Mirrors the inline block at the PreToolUse entry; NEVER blocks
    the hook, NEVER raises.

    Decision tree:
        1. Only Write/Edit/MultiEdit on code files (see
           ``semantic_gate.is_write_to_code_file``).
        2. Feature flag ``swe_router`` MUST be explicitly enabled.
        3. ``get_user_msg_token(session_id)`` returns a token; if None we
           skip (cannot dedupe safely).
        4. Fire-once-per-turn: only invoke router when the token differs
           from the last-observed token for this session.

    Args:
        tool_name: Tool name from the hook payload.
        tool_input: Tool input dict from the hook payload.
        session_id: Resolved session id (already sanitized by caller).
    """
    if tool_name not in ("Edit", "Write", "MultiEdit"):
        return
    try:
        from feature_flags import is_feature_explicitly_enabled
        if is_feature_explicitly_enabled("swe_router"):
            from semantic_gate import (
                route as _sem_route,
                is_write_to_code_file as _is_write_to_code_file,
            )
            from session_mode import get_user_msg_token as _get_token
            if not _is_write_to_code_file(tool_name, tool_input):
                return
            token = _get_token(session_id)
            if token is None:
                return
            session_key = session_id or ""
            last_token = _LAST_ROUTE_TOKEN_BY_SESSION.get(session_key)
            if token == last_token:
                return
            _LAST_ROUTE_TOKEN_BY_SESSION[session_key] = token
            _sem_route(
                file_path=tool_input.get("file_path", ""),
                old_string=tool_input.get("old_string", "") if tool_name == "Edit" else "",
                new_string=tool_input.get("new_string", tool_input.get("content", "")),
                tool_name=tool_name,
                session_id=session_id,
            )
        elif is_feature_explicitly_enabled("semantic_gate"):
            # Phase 1 fallback (existing shadow judge).
            from semantic_gate import judge as _sem_judge
            _sem_judge(
                file_path=tool_input.get("file_path", ""),
                old_string=tool_input.get("old_string", "") if tool_name == "Edit" else "",
                new_string=tool_input.get("new_string", tool_input.get("content", "")),
                tool_name=tool_name,
                tier_signal="unknown",
                session_id=session_id,
            )
    except Exception:
        # Phase A MUST NEVER affect hook behavior.
        return

# Defensive import of repo_detector (Issue #662).
# Uses importlib.util.spec_from_file_location to load the module relative to
# __file__ so the import resolves correctly regardless of sys.path at load time.
# Fail-closed: if the detector is unavailable, _is_adev_project_fn is None and
# _is_adev_project() returns True — enforcement is never silently skipped.
_is_adev_project_fn = None
try:
    _hook_dir = Path(__file__).resolve().parent
    _repo_detector_candidates = [
        _hook_dir.parent / "lib" / "repo_detector.py",           # plugins/autonomous-dev/lib
        _hook_dir.parents[2] / "lib" / "repo_detector.py",        # fallback
    ]
    for _rd_path in _repo_detector_candidates:
        if _rd_path.exists():
            import importlib.util as _rd_ilu
            _rd_spec = _rd_ilu.spec_from_file_location("repo_detector", str(_rd_path))
            if _rd_spec and _rd_spec.loader:
                _rd_mod = importlib.util.module_from_spec(_rd_spec)
                _rd_spec.loader.exec_module(_rd_mod)
                _is_adev_project_fn = _rd_mod.is_autonomous_dev_repo
            break
except Exception:
    _is_adev_project_fn = None  # Fallback: fail closed (always enforce)

_REPO_DETECTOR_AVAILABLE = _is_adev_project_fn is not None

# Issue #1178: Prompt-integrity recovery telemetry — paired block + recovery
# events written to hook-blocks.jsonl via log_block_event. The classifier is
# inlined at the emission site (no helper); this constant only encodes the
# substring -> category mapping in priority order.
_PI_CATEGORY_MAP = (
    ("shrank", "shrinkage_pct_over_threshold"),
    ("slot", "slot_missing"),
    ("below baseline", "word_count_below_baseline"),
)
_PI_BLOCK_EVENT_TYPE = "prompt_integrity_block"
_PI_RECOVERY_EVENT_TYPE = "prompt_integrity_recovery"


# Phase 1 (Issue #1142): defensive import of edit_tier_classifier for the
# default-on Write/Edit gate. Replaces the old `.enforce` opt-in marker check
# and the line-count-only "significant additions" heuristic.
_classify_edit_tier_fn = None
_detect_bash_code_file_write_fn = None
# Phase 2 remediation (Issue #1154): helpers for upgrading the tier of a
# Bash fresh-file write by feeding the heredoc body through the AST
# classifier. Defensively bound — if absent (older lib/), the hook falls
# back to the previous line-count behavior.
_extract_heredoc_body_fn = None
_is_fresh_file_write_pattern_fn = None
try:
    _etc_path = Path(__file__).resolve().parent.parent / "lib" / "edit_tier_classifier.py"
    if _etc_path.exists():
        import importlib.util as _etc_ilu
        _etc_spec = _etc_ilu.spec_from_file_location("edit_tier_classifier", str(_etc_path))
        if _etc_spec and _etc_spec.loader:
            _etc_mod = importlib.util.module_from_spec(_etc_spec)
            _etc_spec.loader.exec_module(_etc_mod)
            _classify_edit_tier_fn = _etc_mod.classify_edit_tier
            _detect_bash_code_file_write_fn = _etc_mod.detect_bash_code_file_write
            _extract_heredoc_body_fn = getattr(
                _etc_mod, "extract_heredoc_body_for_redirect", None
            )
            _is_fresh_file_write_pattern_fn = getattr(
                _etc_mod, "is_fresh_file_write_pattern", None
            )
except Exception:
    # Fail-closed: if classifier is unavailable, the gate degrades to a
    # conservative "always full" decision via the local helper below.
    _classify_edit_tier_fn = None
    _detect_bash_code_file_write_fn = None
    _extract_heredoc_body_fn = None
    _is_fresh_file_write_pattern_fn = None


# Phase 2 (Issue #1153): defensive import of the shared heredoc-strip
# utility. Mirrors the pattern above. The shared module is used here at
# three call sites (formerly the private `_strip_heredoc_content` at the
# two sites that called it + the inline-duplicated regex inside the
# state-file deletion check). When the shared module fails to load we
# fall back to a no-op strip — preserving existing behavior with one
# minor false-positive risk that was already there before this refactor.
_strip_heredoc_fn = None
try:
    _heredoc_path = (
        Path(__file__).resolve().parent.parent / "lib" / "heredoc_utils.py"
    )
    if _heredoc_path.exists():
        import importlib.util as _heredoc_ilu
        _heredoc_spec = _heredoc_ilu.spec_from_file_location(
            "heredoc_utils", str(_heredoc_path)
        )
        if _heredoc_spec and _heredoc_spec.loader:
            _heredoc_mod = importlib.util.module_from_spec(_heredoc_spec)
            _heredoc_spec.loader.exec_module(_heredoc_mod)
            _strip_heredoc_fn = _heredoc_mod.strip_heredoc_content
except Exception:
    _strip_heredoc_fn = None


def _is_adev_project() -> bool:
    """Return True if the current working directory is an autonomous-dev repo.

    Wraps the dynamically-loaded repo_detector.is_autonomous_dev_repo.
    Falls back to True (fail-closed) when the module could not be loaded,
    so enforcement is never silently skipped on import failure.
    """
    if _is_adev_project_fn is None:
        return True
    return _is_adev_project_fn()


def _safe_classify_edit_tier(file_path: str, old_string: str, new_string: str) -> tuple:
    """Defensive wrapper around classify_edit_tier.

    Returns (tier, reason). On classifier unavailability or exception,
    fails CLOSED with ("full", "classifier_unavailable") so the gate
    routes the model to the full /implement pipeline (most conservative).
    """
    if _classify_edit_tier_fn is None:
        return ("full", "classifier_unavailable")
    try:
        return _classify_edit_tier_fn(file_path, old_string, new_string)
    except Exception:
        return ("full", "classifier_error")


# Phase 2 (Issue #1146): sliding-window helpers.
#
# Tier-2 threshold mirrored locally so the hook does not need to import the
# constant from the classifier module — easier wiring under the defensive-
# import scheme above. Kept in sync with
# ``edit_tier_classifier.py:TIER_LIGHT_LINE_THRESHOLD``.
_TIER_LIGHT_LINE_THRESHOLD_LOCAL = 20

# Defensive dynamic-load of the sliding-window ring-buffer API from
# ``pipeline_completion_state``. Module is already loaded elsewhere in this
# file, but we cannot guarantee the import has happened by the time the
# helpers are called. We resolve lazily on first call to dodge import-order
# issues with the existing late-import pattern in this file.
def _count_added_lines_for_sliding_window(old_string: str, new_string: str) -> int:
    """Compute lines-added for the sliding-window record.

    Mirrors the classifier's ``_count_added_lines`` but kept local to the
    hook so the sliding-window mechanism is self-contained — the classifier
    must remain a pure module with no state.
    """
    old_lines = len(old_string.splitlines()) if old_string else 0
    new_lines = len(new_string.splitlines()) if new_string else 0
    return max(0, new_lines - old_lines)


# #1166: module-level cache so we resolve the ring-buffer API exactly
# once per process. Previously every Write/Edit/Bash classification ran
# the full importlib lookup, which was measurable in tight gate loops.
# Module is shared with the cache helpers below — module-private by
# convention, not enforcement.
_PCS_MODULE_CACHE = None  # type: ignore[var-annotated]
_PCS_API_CACHE: Tuple = (None, None, None)
_PCS_RESOLVED = False


def _load_tier1_ring_buffer_api():
    """Lazy resolve the ring-buffer API from ``pipeline_completion_state``.

    Returns a 3-tuple ``(record, get, clear)`` of callables, or ``(None,
    None, None)`` when the module is not importable. Callers MUST treat
    a ``None`` triple as "skip the sliding-window check" — failures here
    never worsen the gate behavior.

    The triple is cached at module level after the first successful OR
    failed resolution (#1166). Subsequent calls return the cached value
    without re-importing. The failure path also sets the sentinel so we
    do not pay the importlib cost every gate invocation when the module
    is genuinely unavailable.
    """
    global _PCS_MODULE_CACHE, _PCS_API_CACHE, _PCS_RESOLVED
    if _PCS_RESOLVED:
        return _PCS_API_CACHE
    try:
        import pipeline_completion_state as _pcs  # type: ignore[import-not-found]
        _PCS_MODULE_CACHE = _pcs
        _PCS_API_CACHE = (
            getattr(_pcs, "record_tier1_allow", None),
            getattr(_pcs, "get_recent_tier1_allows", None),
            getattr(_pcs, "clear_tier1_ring_buffer", None),
        )
    except Exception:
        _PCS_API_CACHE = (None, None, None)
    finally:
        # Set even on the failure path so subsequent calls skip the
        # import attempt — the gate must not re-pay importlib cost on
        # every classification when the module is missing.
        _PCS_RESOLVED = True
    return _PCS_API_CACHE


def _record_tier1_allow(session_id: str, file_path: str, lines_added: int) -> None:
    """Record a Tier-1 (fix-tier) classifier decision into the ring buffer."""
    rec, _, _ = _load_tier1_ring_buffer_api()
    if rec is None:
        return
    try:
        rec(session_id, file_path, lines_added)
    except Exception:
        pass


def _get_recent_tier1_allows(
    session_id: str, file_path: str, *, window_seconds: int = 60
) -> list:
    """Return the recent Tier-1 ring-buffer entries for ``(session_id, file_path)``."""
    _, get, _ = _load_tier1_ring_buffer_api()
    if get is None:
        return []
    try:
        return get(session_id, file_path, window_seconds=window_seconds)
    except Exception:
        return []


def _clear_tier1_ring_buffer(session_id: str, file_path: str) -> None:
    """Drop the ring buffer for ``(session_id, file_path)`` after escalation."""
    _, _, clr = _load_tier1_ring_buffer_api()
    if clr is None:
        return
    try:
        clr(session_id, file_path)
    except Exception:
        pass


def is_running_under_uv() -> bool:
    """Detect if script is running under UV."""
    return "UV_PROJECT_ENVIRONMENT" in os.environ

def find_lib_directory(hook_path: Path) -> Path | None:
    """
    Find lib directory dynamically (Issue #113).

    Checks multiple locations in order:
    1. Development: plugins/autonomous-dev/lib (relative to hook)
    2. Local install: ~/.claude/lib
    3. Marketplace: ~/.claude/plugins/autonomous-dev/lib

    Args:
        hook_path: Path to this hook script

    Returns:
        Path to lib directory if found, None otherwise (graceful failure)
    """
    # Try development location first
    dev_lib = hook_path.parent.parent / "lib"
    if dev_lib.exists() and dev_lib.is_dir():
        return dev_lib

    # Try local install
    home = Path.home()
    local_lib = home / ".claude" / "lib"
    if local_lib.exists() and local_lib.is_dir():
        return local_lib

    # Try marketplace location
    marketplace_lib = home / ".claude" / "plugins" / "autonomous-dev" / "lib"
    if marketplace_lib.exists() and marketplace_lib.is_dir():
        return marketplace_lib

    return None


# Add lib directory to path dynamically
LIB_DIR = find_lib_directory(Path(__file__))
if LIB_DIR:
    if not is_running_under_uv():
        sys.path.insert(0, str(LIB_DIR))

# Issue #953: Hook safety helpers — graceful failure on missing deps and
# slash-command precondition checks. Wrapped in try/except so the hook still
# loads (with no-op fallbacks) if hook_safety is unavailable.
try:
    from hook_safety import command_registered as _hook_command_registered
    from hook_safety import safe_main as _hook_safe_main
except ImportError:
    def _hook_command_registered(_name: str) -> bool:  # fail-CLOSED stub
        return True

    def _hook_safe_main(fn):  # no-op stub: preserves int return semantics
        result = fn()
        if isinstance(result, int):
            sys.exit(result)
        sys.exit(0)


# Issue #1206: per-repo sentinel path. Import from lib.pipeline_state so the
# hook subprocess resolves the same sentinel path the coordinator session uses
# (subject to CWD inheritance — see tests/integration/test_hook_pwd_inheritance.py).
try:
    from pipeline_state import get_legacy_sentinel_path  # type: ignore
except ImportError:
    def get_legacy_sentinel_path(repo_root=None):  # type: ignore
        # Fallback: behave like the pre-#1206 hardcoded path so hooks still
        # function in degraded environments where lib/ is not on sys.path.
        return Path("/tmp/implement_pipeline_state.json")


# Issue #1206: state-file write-protection tuple. Both the legacy machine-global
# literal AND the new per-repo path must be protected:
# - The legacy literal (``/tmp/implement_pipeline_state.json``) is retained so
#   that orphaned sentinel files from pre-#1206 sessions still receive
#   write-protection during the transition window.
# - The new per-repo path is added so the current sentinel is protected at its
#   actual location.
LEGACY_SENTINEL_LITERALS: tuple = (
    "/tmp/implement_pipeline_state.json",  # legacy orphan: pre-#1206 sessions
    str(get_legacy_sentinel_path()),        # new per-repo: current sentinel
)


def load_env():
    """Load .env file from project root if it exists."""
    env_file = Path(os.getcwd()) / ".env"
    if env_file.exists():
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key not in os.environ:
                            os.environ[key] = value
        except Exception:
            pass  # Silently skip


# Agents authorized for code changes (pipeline agents)
# Issue #147: Consolidated to only active agents that write code/tests/docs
PIPELINE_AGENTS = [
    'implementer',
    'test-master',
    'doc-master',
]

# Agents authorized to create GitHub issues directly (Issue #599)
GH_ISSUE_AGENTS = {'issue-creator'}

# Marker file path for allowing gh issue create from commands (Issue #599)
GH_ISSUE_MARKER_PATH = "/tmp/autonomous_dev_gh_issue_allowed.marker"

# Command context file for issue-creating commands (Issue #630).
# Issue #1203: support env-var override (GH_ISSUE_CMD_CONTEXT_PATH) so subprocess
# runtime tests can isolate the path without writing the real /tmp file. Mirrors
# the PIPELINE_STATE_FILE precedent (see line ~1758).
GH_ISSUE_COMMAND_CONTEXT_PATH = os.getenv(
    "GH_ISSUE_CMD_CONTEXT_PATH",
    "/tmp/autonomous_dev_cmd_context.json",
)

# Plan-critic REVISE gate artifact path (Issue #1417).
#
# Sourced from lib/plan_critic_verdict.DEFAULT_VERDICT_PATH — the module that
# WRITES the file — so the reader and the writer cannot drift. The module-level
# guarded-import idiom mirrors get_legacy_sentinel_path above: an ImportError in
# a degraded environment falls back to the same literal, it does NOT fail the
# gate open from inside the gate's own try block.
#
# The env override exists so subprocess/runtime tests can isolate the path.
# PLAN_CRITIC_VERDICT_PATH is in PROTECTED_ENV_VARS below: unlike
# GH_ISSUE_CMD_CONTEXT_PATH (which gates an ALLOW-through), this path gates a
# REFUSAL, so an unprotected override would let
# `PLAN_CRITIC_VERDICT_PATH=/dev/null <cmd>` disable the REVISE gate outright.
try:
    from plan_critic_verdict import DEFAULT_VERDICT_PATH as _PC_DEFAULT  # type: ignore
except ImportError:
    _PC_DEFAULT = Path(".claude/plan_critic_verdict.json")
PLAN_CRITIC_VERDICT_PATH = os.getenv("PLAN_CRITIC_VERDICT_PATH", str(_PC_DEFAULT))

# Commands that are authorized to create GitHub issues (Issue #630).
# Issue #1203: 'plan' added — plan.md STEP 6 files issues by design per its own
# HARD GATE (>=2 independent work items). Whitelisting here is the minimal fix
# vs rerouting plan.md to use a different mechanism.
GH_ISSUE_COMMANDS = {'create-issue', 'plan-to-issues', 'improve', 'refactor', 'retrospective', 'plan', 'triage-aggregate'}

# Environment variables protected from inline spoofing in Bash commands (Issue #557)
# Non-prefix vars that don't start with CLAUDE_ are listed individually
# Issue #1467: ALIGNMENT_USER_APPROVED gates the ESCALATE -> USER_APPROVED
# upgrade in the alignment gate. Inline-spoofing it (ALIGNMENT_USER_APPROVED=1
# python3 -c ...) would fake a human approval, so it is protected like the other
# gate-controlling variables.
# PLAN_CRITIC_VERDICT_PATH gates the REVISE refusal — pointing it at /dev/null
# would disable that gate, so it is protected in the same change that
# introduced it.
# SCRATCHPAD is consulted by _is_scratch_path, which grants a write-gate
# EXEMPTION. An inline `SCRATCHPAD=... <cmd>` would let a caller nominate any
# subtree as scratch and skip the pipeline gate on it.
PROTECTED_ENV_VARS = {
    'PIPELINE_STATE_FILE', 'ENFORCEMENT_LEVEL', 'AUTONOMOUS_DEV_COMMAND',
    'INTENT_CLASSIFIER_ENFORCE', 'ALIGNMENT_USER_APPROVED',
    'PLAN_CRITIC_VERDICT_PATH', 'SCRATCHPAD',
}

# Prefix-based protection: any env var starting with these prefixes is protected (Issue #606)
PROTECTED_ENV_PREFIXES: "tuple[str, ...]" = ('CLAUDE_',)

# Issue #1137: CLAUDE_SESSION_ID is non-privileged framework correlation metadata
# (Claude Code-generated UUID, NOT an authentication token). Legitimate tooling
# (baseline failure capture, activity-log scoping, nested subshell propagation per
# Issue #904) needs to export it. The compensating control against log-attribution
# spoofing is _SAFE_SESSION_ID_RE sanitization in unified_prompt_validator.py
# (around lines 554-558, Issue #1024).
# REVOCATION CONDITION: remove from this exceptions set if CLAUDE_SESSION_ID
# ever gains authentication, authorization, or other privilege-bearing semantics.
PROTECTED_ENV_PREFIX_EXCEPTIONS: "frozenset[str]" = frozenset({"CLAUDE_SESSION_ID"})

# Code file extensions subject to workflow enforcement
CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs',
    '.c', '.cpp', '.h', '.hpp', '.cs', '.rb', '.php', '.swift',
    '.kt', '.scala', '.sh', '.bash', '.zsh', '.vue', '.svelte',
}

# Ephemeral / scratch absolute prefixes exempt from the write-pipeline gate
# (Issue #1408). Promoted from a function-local list in
# ``_check_write_pipeline_required`` to a module-level constant so the
# Bash-code gate and #803 cross-tool check share ONE definition (the repo
# previously carried three inconsistent temp lists). Files at these locations
# are never committed and never user-facing, so pipeline review adds no value.
# Restricted to ABSOLUTE prefixes so ``/tmp/foo.sh`` is exempt but a project
# dir literally named ``tmp`` is NOT. ``$SCRATCHPAD`` is handled dynamically in
# ``_is_scratch_path`` (env is read per-call, not frozen at import).
EPHEMERAL_PREFIXES: "tuple[str, ...]" = (
    "/tmp/",
    "/private/tmp/",      # macOS canonicalises /tmp -> /private/tmp
    "/var/tmp/",
    "/var/folders/",      # macOS pytest tmp_path / mkdtemp default
    str(Path.home() / "tmp") + "/",
    str(Path.home() / ".cache") + "/",
)


def _is_scratch_path(path: str) -> bool:
    """Return True when ``path`` is an ephemeral/scratch location (Issue #1408).

    A scratch path is never committed and never user-facing, so the
    ``/implement`` write-pipeline gate must not fire on it. Recognises:

    * any :data:`EPHEMERAL_PREFIXES` absolute prefix,
    * the ``$SCRATCHPAD`` subtree (when the env var is set),
    * per-session scratchpad roots ``/private/tmp/claude-*/`` (and the
      ``/tmp/claude-*/`` uncanonicalised form),
    * any ``.claude/tmp/`` segment (project-local scratch).

    Pure helper: reads env only, uses ``.expanduser()`` (NOT ``.resolve()`` —
    resolving would chase symlinks and could surprise on macOS ``/tmp`` ->
    ``/private/tmp``). Never raises — any error returns False (fail-safe: an
    unclassifiable path is treated as NON-scratch, i.e. still gated).

    Args:
        path: The candidate file path (absolute or relative).

    Returns:
        True if the path is an ephemeral/scratch location.
    """
    if not path:
        return False
    try:
        p = path.strip().strip("'\"")
        if not p:
            return False
        try:
            expanded = str(Path(p).expanduser())
        except Exception:
            expanded = p

        if any(expanded.startswith(prefix) for prefix in EPHEMERAL_PREFIXES):
            return True

        # Home-relative scratch (~/tmp, ~/.cache) recomputed per-call so it
        # tracks the live $HOME even when a test monkeypatches Path.home — the
        # module-level EPHEMERAL_PREFIXES froze Path.home() at import time.
        try:
            home = Path.home()
            for sub in ("tmp", ".cache"):
                if expanded.startswith(str(home / sub) + "/"):
                    return True
        except Exception:
            pass

        scratchpad = os.environ.get("SCRATCHPAD", "")
        # Degenerate roots are REJECTED. ``SCRATCHPAD=/`` (or any all-slash
        # value) reduces the prefix test to ``startswith("/")``, which is true
        # for EVERY absolute path — including this hook and /etc/passwd — and
        # so would exempt the entire filesystem from every _is_scratch_path
        # caller. Measured both arms: unset -> no path matches;
        # ``SCRATCHPAD=/`` -> every absolute path matched.
        scratchpad_root = scratchpad.rstrip("/")
        if scratchpad_root and expanded.startswith(scratchpad_root + "/"):
            return True

        # Per-session scratchpad roots: /private/tmp/claude-*/ and /tmp/claude-*/
        for seg in ("/private/tmp/claude-", "/tmp/claude-"):
            if expanded.startswith(seg):
                return True

        # Project-local scratch directory.
        if "/.claude/tmp/" in expanded or expanded.startswith(".claude/tmp/"):
            return True
    except Exception:
        return False

    return False


def _is_gated_repo_source(path: str) -> bool:
    """Return True when ``path`` is in-worktree, non-ignored repo source (Issue #1408).

    Git-worktree-aware scoping for the write-pipeline gate. A path is "gated
    repo source" (i.e. the Edit/Write pipeline gate SHOULD apply) only when it
    is a real, tracked-or-trackable source file inside a git worktree:

    1. scratch paths are checked FIRST and are never gated (returns False),
    2. paths outside any git worktree are not gated (returns False),
    3. gitignored paths are not gated (returns False),
    4. everything else in-worktree (including new-untracked source) STAYS gated
       (returns True).

    Runs ``git`` per-invocation FROM THE TARGET FILE'S DIRECTORY so submodules
    and linked worktrees resolve to the correct repo (a single top-level
    ``git -C repo_root`` would misclassify submodule files). Every subprocess is
    timeout-bounded (1.0s) and wrapped.

    FAIL-OPEN: any subprocess error / TimeoutExpired / FileNotFoundError (git
    missing) falls back to :func:`_is_autonomous_dev_repo`. This function NEVER
    raises — a raised exception inside PreToolUse breaks ALL tool use.

    Args:
        path: The candidate file path.

    Returns:
        True if the path is in-worktree, non-ignored repo source.
    """
    try:
        if not path:
            return False

        # (1) scratch checked first — scratch is never gated.
        if _is_scratch_path(path):
            return False

        try:
            target = Path(path).expanduser()
            work_dir = str(target.parent if target.parent != Path("") else Path.cwd())
        except Exception:
            return _is_autonomous_dev_repo(path)

        import subprocess as _sp

        # (2) inside a git worktree?
        try:
            _r = _sp.run(
                ["git", "-C", work_dir, "rev-parse", "--is-inside-work-tree"],
                capture_output=True, text=True, timeout=1.0,
            )
        except (OSError, ValueError, _sp.SubprocessError):
            # git unavailable / timeout — fail open to the pre-#1408 scoping.
            return _is_autonomous_dev_repo(path)
        if _r.returncode != 0 or _r.stdout.strip() != "true":
            return False  # outside a worktree — not gated repo source.

        # (3) gitignored? check-ignore exit 0 == ignored.
        try:
            _ig = _sp.run(
                ["git", "-C", work_dir, "check-ignore", "-q", str(target)],
                capture_output=True, text=True, timeout=1.0,
            )
        except (OSError, ValueError, _sp.SubprocessError):
            return _is_autonomous_dev_repo(path)
        if _ig.returncode == 0:
            return False  # gitignored — not gated.

        # (4) in-worktree, non-ignored (incl. new-untracked source) — STAYS gated.
        return True
    except Exception:
        # Absolute belt-and-braces: never raise out of PreToolUse.
        try:
            return _is_autonomous_dev_repo(path)
        except Exception:
            return False

# Language-specific pattern groups for code significance detection
PATTERN_GROUPS = {
    'python': {
        'extensions': {'.py'},
        'patterns': [
            (r'\bdef\s+\w+\s*\(', 'Python function'),
            (r'\basync\s+def\s+\w+\s*\(', 'Python async function'),
            (r'\bclass\s+\w+', 'Python class'),
        ]
    },
    'javascript': {
        'extensions': {'.js', '.ts', '.jsx', '.tsx', '.vue', '.svelte'},
        'patterns': [
            (r'\bfunction\s+\w+\s*\(', 'JavaScript function'),
            (r'\basync\s+function\s+\w+\s*\(', 'JavaScript async function'),
            (r'\bconst\s+\w+\s*=\s*(?:async\s*)?\(.*?\)\s*=>', 'Arrow function'),
            (r'\bexport\s+(?:default\s+)?(?:function|class|const)', 'JS export'),
            (r'\bclass\s+\w+', 'JavaScript class'),
        ]
    },
    'shell': {
        'extensions': {'.sh', '.bash', '.zsh'},
        'patterns': [
            (r'\bfunction\s+\w+', 'Shell function'),
        ]
    },
    'go': {
        'extensions': {'.go'},
        'patterns': [
            (r'\bfunc\s+(?:\(\w+\s+\*?\w+\)\s+)?\w+\s*\(', 'Go function'),
        ]
    },
    'rust': {
        'extensions': {'.rs'},
        'patterns': [
            (r'\bfn\s+\w+\s*[<(]', 'Rust function'),
            (r'\bimpl\s+', 'Rust impl block'),
        ]
    },
    'universal': {
        'extensions': None,  # None means applies to ALL code extensions
        'patterns': [
            (r'\btry:\s*\n\s+(?:from|import)\s+', 'Conditional import (try/except)'),
            (r'\bif\s+\w+.*:\s*\n(?:\s+.*\n){3,}else:', 'Multi-branch conditional'),
        ]
    }
}

SIGNIFICANT_LINE_THRESHOLD = 5

# Git subcommands where -n means --no-verify (not a count flag)
_GIT_VERIFY_SUBCOMMANDS = {"push", "commit", "merge"}

# Git subcommands where -f means --force (not something else)
_GIT_FORCE_PUSH_SUBCOMMANDS = {"push"}

# Git global flags that consume the next token as their value (Issue #1470).
# When these precede the subcommand (e.g. "git -c foo=bar push --force"), the
# naive "first non-dash token" scan would misidentify the value as the
# subcommand and silently skip force/verify detection.
_GIT_VALUE_FLAGS = {"-c", "-C", "--git-dir", "--work-tree", "--namespace"}


def _detect_git_bypass(command: str) -> Tuple[bool, str]:
    """Detect git bypass patterns in a command string.

    Checks for --no-verify, --force on push, git reset --hard,
    git clean -f/-fd, and the -n shorthand on push/commit/merge.

    Handles pipes by only parsing the segment before the first pipe.

    Args:
        command: The shell command string to analyze.

    Returns:
        Tuple of (is_bypass, reason). If is_bypass is True, the command
        should be blocked.
    """
    # Only parse the first command in a pipeline
    pipe_idx = command.find("|")
    if pipe_idx >= 0:
        command = command[:pipe_idx]

    command = command.strip()
    if not command:
        return (False, "")

    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()

    if not tokens:
        return (False, "")

    # Find the git command and subcommand
    git_idx = None
    for i, token in enumerate(tokens):
        if token == "git" or token.endswith("/git"):
            git_idx = i
            break

    if git_idx is None:
        return (False, "")

    # Extract subcommand (first non-flag token after "git"), skipping over
    # value-taking global flags like "-c foo=bar" or "-C /path" so their value
    # tokens are not misidentified as the subcommand (Issue #1470).
    subcommand = ""
    tokens_after_git = tokens[git_idx + 1:]
    i = 0
    while i < len(tokens_after_git):
        token = tokens_after_git[i]
        if token in _GIT_VALUE_FLAGS:
            # Skip the flag and its value token (if present).
            i += 2
            continue
        if token.startswith("--") and "=" in token:
            # Combined form like "--git-dir=/path" — single token, no separate value.
            i += 1
            continue
        if not token.startswith("-"):
            subcommand = token
            break
        i += 1

    remaining_tokens = tokens[git_idx + 1:]

    # Check --no-verify on any git command
    if "--no-verify" in remaining_tokens:
        return (True, f"git {subcommand} --no-verify bypasses pre-commit/pre-push hooks")

    # Check -n shorthand ONLY on push/commit/merge (not log/diff where it means count)
    if subcommand in _GIT_VERIFY_SUBCOMMANDS:
        for token in remaining_tokens:
            # Match -n as standalone flag or combined flags like -fn
            if token == "-n":
                return (True, f"git {subcommand} -n bypasses verification hooks")
            # Check combined short flags (e.g., -fn, -an) but not subcommand itself
            if token.startswith("-") and not token.startswith("--") and "n" in token and token != subcommand:
                return (True, f"git {subcommand} {token} contains -n (bypasses verification hooks)")

    # Check --force / -f ONLY on push
    if subcommand in _GIT_FORCE_PUSH_SUBCOMMANDS:
        if "--force" in remaining_tokens or "--force-with-lease" in remaining_tokens:
            return (True, f"git push --force can overwrite remote history")
        for token in remaining_tokens:
            if token == "-f":
                return (True, "git push -f can overwrite remote history")

    # Check git reset --hard
    if subcommand == "reset" and "--hard" in remaining_tokens:
        return (True, "git reset --hard discards all uncommitted changes")

    # Check git clean -f or git clean -fd
    if subcommand == "clean":
        for token in remaining_tokens:
            if token.startswith("-") and not token.startswith("--") and "f" in token:
                return (True, "git clean -f permanently deletes untracked files")
        if "--force" in remaining_tokens:
            return (True, "git clean --force permanently deletes untracked files")

    return (False, "")


def validate_sandbox_layer(tool_name: str, tool_input: Dict) -> Tuple[str, str]:
    """
    Validate sandbox layer (Layer 0) - command classification and sandboxing.

    Args:
        tool_name: Name of the tool being called
        tool_input: Tool input parameters

    Returns:
        Tuple of (decision, reason)
        - decision: "allow", "deny", or "ask"
        - reason: Human-readable reason for decision
    """
    # Check if sandbox is enabled
    enabled = os.getenv("SANDBOX_ENABLED", "false").lower() == "true"
    if not enabled:
        return ("allow", "Sandbox layer disabled - pass through")

    # Only validate Bash commands
    if tool_name != "Bash":
        return ("allow", "Sandbox layer only validates Bash commands - pass through")

    # Extract command from tool_input
    command = tool_input.get("command", "")
    if not command:
        return ("allow", "No command to validate - pass through")

    try:
        # Try to import sandbox enforcer
        try:
            from sandbox_enforcer import SandboxEnforcer, CommandClassification

            # Create enforcer
            enforcer = SandboxEnforcer(policy_path=None, profile=None)

            # Classify command
            result = enforcer.is_command_safe(command)

            if result.classification == CommandClassification.SAFE:
                # Safe command - auto-approve
                return ("allow", "Sandbox: SAFE command auto-approved")
            elif result.classification == CommandClassification.BLOCKED:
                # Blocked command - deny
                return ("deny", f"Sandbox: BLOCKED - {result.reason}")
            else:  # NEEDS_APPROVAL
                # Unknown command - continue to next layer
                return ("ask", "Sandbox: NEEDS_APPROVAL - unknown command")

        except ImportError:
            # Sandbox enforcer not available - continue to next layer
            return ("ask", "Sandbox enforcer unavailable")

    except Exception as e:
        # Error in validation - continue to next layer (don't block on errors)
        return ("ask", f"Sandbox error: {e}")


NATIVE_TOOLS = {
    "Read", "Write", "Edit", "Glob", "Grep", "Bash",
    "Task", "TaskOutput", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet", "TaskStop",
    "AskUserQuestion", "Skill", "SlashCommand", "BashOutput", "NotebookEdit",
    "TodoWrite", "EnterPlanMode", "ExitPlanMode", "AgentOutputTool", "KillShell",
    "LSP", "WebFetch", "WebSearch",
    "Agent", "EnterWorktree", "ExitWorktree", "ToolSearch",
    "CronCreate", "CronDelete", "CronList",
}

# Tool names that represent subagent invocations (Agent tool; legacy: Task)
AGENT_TOOL_NAMES = {"Agent", "Task"}

# Infrastructure file segments protected from direct edits (Issue #483)
# Maps directory path segments to allowed file extensions within that segment.
PROTECTED_INFRA_SEGMENTS = {
    '/agents/': {'.md'},
    '/commands/': {'.md'},
    '/hooks/': {'.py'},
    '/lib/': {'.py'},
    '/skills/': {'.md'},
}

# Per-file protected entries (Issue #980) — relative paths from autonomous-dev
# repo root. Matched via endswith against normalized absolute paths.
PROTECTED_INFRA_FILES = {
    "plugins/autonomous-dev/config/install_manifest.json",
}

# ============================================================================
# Plan-Exit Enforcement (Issue #926)
#
# Moved from UserPromptSubmit (unified_prompt_validator.py) to PreToolUse here
# because UserPromptSubmit does not fire for in-turn tool calls by the model
# (gh issue create, Task(implementer), etc.). Enforcement at PreToolUse
# observes every tool call and cannot be bypassed by the model executing the
# plan in-turn without a user prompt.
#
# Marker writer (plan_mode_exit_detector.py) and stage advancer
# (unified_session_tracker.py) are unchanged — only the *enforcement* event
# boundary moved.
# ============================================================================

_PLAN_EXIT_MARKER_PATH = ".claude/plan_mode_exit.json"
_PLAN_EXIT_STALE_MINUTES = 30

# Bash allowlists for plan_exited stage — read-only inspection only.
# Command tokenization: `command.split()` + exact match against these sets.
# Any command with injection metacharacters is rejected before tokenization.
_PLAN_EXIT_BASH_ALLOWLIST_1TOKEN: "frozenset[str]" = frozenset({
    "ls", "cat", "head", "tail", "wc", "pwd", "which", "echo",
    "grep", "rg", "tree", "stat", "file", "date", "whoami", "id", "uname",
})

_PLAN_EXIT_BASH_ALLOWLIST_2TOKEN: "frozenset[tuple]" = frozenset({
    ("git", "status"),
    ("git", "log"),
    ("git", "diff"),
    ("git", "show"),
    ("git", "branch"),
    ("git", "blame"),
    ("git", "ls-files"),
    ("git", "rev-parse"),
    ("git", "remote"),
})

_PLAN_EXIT_BASH_ALLOWLIST_3TOKEN: "frozenset[tuple]" = frozenset({
    ("gh", "issue", "view"),
    ("gh", "issue", "list"),
    ("gh", "pr", "view"),
    ("gh", "pr", "list"),
    ("gh", "repo", "view"),
    ("gh", "auth", "status"),
})

# Injection metacharacter tokens. Checked as raw substrings — NOT via shlex.
# shlex would silently accept ';' inside single/double-quoted strings, which
# defeats the purpose of blocking injection. Longer tokens listed first for
# clarity; all matches are equivalent (any match → reject).
#
# A03 BLOCKING fix: '\n' and '\r' are bash command separators (identical to
# ';'). Without these, str.split() at line ~3601 silently splits multi-line
# payloads on whitespace, causing the first token to match the 1-token
# allowlist while subsequent commands execute. Example bypass (now blocked):
# 'ls\nrm -rf .claude/plan_mode_exit.json'.
_PLAN_EXIT_INJECTION_TOKENS: "tuple[str, ...]" = (
    "&&", "||", "$(", "<(", "<<<", "<<",
    ";", "&", "|", "`", "$", "<", ">",
    "\n", "\r",  # newline and carriage-return are bash command separators
)

# Subagents that consume the critique_done marker (allowed terminal actions).
_PLAN_EXIT_CONSUMER_AGENTS: "frozenset[str]" = frozenset({
    "issue-creator",
    "continuous-improvement-analyst",
    "implementer",
})

# MCP tools allowed at plan_exited stage — explicit allowlist (AC #21).
#
# Issue #1503: the literal frozenset that used to live here was DELETED. It is
# Issue #1503 residual: MCP tools that ACT without carrying a write shape.
#
# The plan-exit gate denies what acts, not what is un-enumerated. Most acting
# tools are caught by tool_intent.is_write(), which classifies by registry and
# by path+content shape. These are not: they have side effects with no path and
# no content argument, so no shape test can reach them.
#
# browser_evaluate executes arbitrary JavaScript in a live browser and was
# AC #19 of the original #1503 work -- it must never be treated as read-only.
_MCP_SIDE_EFFECT_TOOLS: "frozenset[str]" = frozenset({
    "mcp__playwright__browser_evaluate",
    "mcp__playwright__browser_click",
    "mcp__playwright__browser_type",
    "mcp__playwright__browser_navigate",
    "mcp__playwright__browser_file_upload",
    "mcp__claude_ai_Gmail__send_message",
    "mcp__claude_ai_Gmail__trash_message",
    "mcp__ms365__send-mail",
    "mcp__home-assistant__ha_call_service",
    "mcp__home-assistant__ha_bulk_control",
    "mcp__home-assistant__ha_restart",
    "mcp__unifi-network__unifi_execute",
})

# now sourced from tool_intent.MCP_READ_TOOLS via _ti_mcp_read_tools(), the
# single canonical registry. The old copy was a strict subset — it did not
# know serena's read surface, so it OVER-BLOCKED find_symbol /
# get_symbols_overview / find_referencing_symbols at the plan_exited stage.
# The design constraint it carried ("structural regex heuristics are forbidden
# because they produce false-negatives — 'find_and_replace' contains 'find'
# but is a write") is preserved verbatim in tool_intent.py alongside the
# registries. AC #19 (mcp__playwright__browser_evaluate must NOT be treated as
# read-only) is enforced there and asserted by tests/unit/lib/test_tool_intent.py.

# Canonical deny reason (AC #5) — same string for all plan-exit denies.
# Issue #938: surfaces all three escape hatches in the canonical reason.
_PLAN_EXIT_DENY_REASON = (
    "Run plan-critic, /implement --skip-review, or set AUTONOMOUS_DEV_SKIP_PLAN_REVIEW=1"
)


def _detect_invocation_context(prompt: str) -> "Optional[str]":
    """Detect reinvocation context from prompt text or environment.

    Checks for known markers that indicate a secondary agent invocation
    (remediation, re-review, doc-update-retry) where prompts are naturally
    shorter and should use relaxed shrinkage thresholds.

    Args:
        prompt: The prompt text to scan for markers.

    Returns:
        Context string if detected, None otherwise.
    """
    # 1. Explicit env var takes precedence (coordinator can set this)
    env_ctx = os.getenv("PIPELINE_INVOCATION_CONTEXT", "").strip().lower()
    if env_ctx:
        return env_ctx

    # 2. Scan prompt for known markers (case-insensitive)
    prompt_lower = prompt.lower()

    if "remediation mode" in prompt_lower:
        return "remediation"
    if "re-review" in prompt_lower or "re_review" in prompt_lower:
        return "re-review"
    if "doc-update-retry" in prompt_lower or "reduced context" in prompt_lower or "retry with reduced" in prompt_lower:
        return "doc-update-retry"

    return None


def _prompt_integrity_is_absent() -> bool:
    """Report whether ``prompt_integrity`` is genuinely not installed.

    "Absent by design" means there is no ``prompt_integrity.py`` on disk for
    this hook to load: either no autonomous-dev ``lib/`` directory was resolved
    at all, or the resolved lib exists without the module. That is a filesystem
    fact, so a broken import cannot fake it.

    A module file that *exists* but fails to import is NOT absent — it is
    broken or partial, and the caller must fail closed (Issue #1471, where a
    swallowed ``AttributeError`` after a field rename waved every
    compression-critical agent invocation through, undetected in production).

    Returns:
        True when the module is genuinely not installed (safe to skip the
        check), False when it is on disk (so an import failure means the gate
        is broken, not inapplicable).
    """
    try:
        if LIB_DIR is None:
            return True
        return not (Path(LIB_DIR) / "prompt_integrity.py").exists()
    except OSError:
        # Cannot even stat the path — we do not know, so report "present" and
        # let the caller fail closed rather than wave the dispatch through.
        return False


def validate_prompt_integrity(tool_name: str, tool_input: Dict) -> Tuple[str, str]:
    """Validate agent prompt word count during active pipeline (Issue #695).

    Layer 5: Blocks agent invocations where the prompt is below the minimum
    word count for critical agents. This is deterministic enforcement — the
    coordinator cannot bypass it by ignoring prompt-level instructions.

    Args:
        tool_name: Tool being invoked.
        tool_input: Tool input parameters.

    Returns:
        Tuple of (decision, reason).
    """
    # Only check Agent/Task tool calls
    if tool_name not in AGENT_TOOL_NAMES:
        return ("allow", "Not an agent invocation")

    # Extract agent type first — needed for minimum word count check
    agent_type = tool_input.get("subagent_type", "").strip().lower()
    if not agent_type:
        return ("allow", "Could not determine agent type")

    # Only check critical agents
    try:
        from prompt_integrity import COMPRESSION_CRITICAL_AGENTS, MIN_CRITICAL_AGENT_PROMPT_WORDS
    except ImportError as exc:
        # This handler used to conflate two different states and encode both as
        # "verified, pass" (INV-7 breach):
        #   1. prompt_integrity is genuinely not installed — nothing to enforce.
        #   2. prompt_integrity IS on disk but did not import (broken, partial,
        #      renamed symbol) — the gate cannot evaluate.
        # Only state 1 is safe to allow. State 2 is the Issue #1471 shape: a
        # swallowed error after a field rename waved every compression-critical
        # agent invocation through, undetected in production.
        if _prompt_integrity_is_absent():
            return ("allow", "prompt_integrity module not available - skipping check")

        import logging as _abs_logging

        _abs_logger = _abs_logging.getLogger("unified_pre_tool.prompt_integrity")
        _abs_logger.error(
            "prompt_integrity is on disk but failed to import — FAIL-CLOSED: %s",
            exc,
            exc_info=True,
        )
        module_path = (
            str(Path(LIB_DIR) / "prompt_integrity.py") if LIB_DIR else "lib/prompt_integrity.py"
        )
        return (
            "deny",
            f"BLOCKED: prompt-integrity gate cannot evaluate agent '{agent_type}'. "
            f"prompt_integrity is installed at {module_path} but failed to import "
            f"({type(exc).__name__}: {exc}). A gate that cannot verify must not "
            f"report 'verified' (Issue #1471). "
            f"REQUIRED NEXT ACTION: repair the module — run "
            f"`python3 -c 'import prompt_integrity'` with that lib directory on "
            f"sys.path to see the real error, then report it via /create-issue. "
            f"Do not retry blind. "
            f"Emergency override: `touch .claude/.bypass` (or AUTONOMOUS_DEV_BYPASS=1) "
            f"disables all hooks for this repo.",
        )

    if agent_type not in COMPRESSION_CRITICAL_AGENTS:
        return ("allow", f"Agent '{agent_type}' is not compression-critical")

    # Extract prompt and check word count — enforced regardless of pipeline state (Issue #716)
    prompt = tool_input.get("prompt", "")
    word_count = len(prompt.split())

    if word_count < MIN_CRITICAL_AGENT_PROMPT_WORDS:
        return (
            "deny",
            f"BLOCKED: Prompt for critical agent '{agent_type}' has only {word_count} words "
            f"(minimum: {MIN_CRITICAL_AGENT_PROMPT_WORDS}). "
            f"Reconstruct the prompt with full context — include the complete implementer "
            f"output, list of changed files, and test results. "
            f"Use get_agent_prompt_template('{agent_type}') to reload the agent's base prompt from disk."
        )

    # Baseline shrinkage check — runs whenever a baseline exists (no pipeline-active gate).
    # Falls open (returns allow) when no baseline is recorded yet. Issue #723.
    # max_shrinkage is 0.20 (20%) — tightened from 0.25 in Issue #812 to catch
    # progressive compression in batch runs. Still above the library default of 15%
    # to give headroom for legitimate prompt variation at the hook level.
    #
    # Issue #764: Use PIPELINE_ISSUE_NUMBER for per-issue baseline isolation.
    # In batch mode, each issue gets its own baseline so cross-issue context
    # pressure doesn't trigger false-positive shrinkage blocks.
    import logging as _pi_logging
    _pi_logger = _pi_logging.getLogger("unified_pre_tool.prompt_integrity")
    try:
        from prompt_integrity import (
            get_prompt_baseline,
            record_prompt_baseline,
            validate_prompt_word_count,
        )
    except ImportError as exc:
        _pi_logger.warning(
            "prompt_integrity unavailable — baseline gate skipped (fail-open): %s", exc
        )
    else:
        try:
            # Per-issue isolation (Issue #764): use current issue number for
            # baseline lookup and seeding. When not in batch mode (no issue context),
            # issue_number=None preserves backward-compatible behavior (lowest issue).
            # Issue #779: Use file-based fallback when env var is missing.
            current_issue_num_raw = _get_current_issue_number()
            current_issue_num = current_issue_num_raw if current_issue_num_raw > 0 else None
            current_issue_str = str(current_issue_num) if current_issue_num else None

            baseline_word_count = get_prompt_baseline(
                agent_type, issue_number=current_issue_num
            )

            # Detect reinvocation context for relaxed thresholds (Issue #789, #791)
            invocation_ctx = _detect_invocation_context(prompt)
            # Issue #1358: Get pipeline mode to pass to prompt integrity functions
            pipeline_mode = _get_pipeline_mode_from_state()


            if baseline_word_count is not None:
                result = validate_prompt_word_count(
                    agent_type, prompt, baseline_word_count,
                    max_shrinkage=0.20, invocation_context=invocation_ctx,
                    pipeline_mode=pipeline_mode,  # Issue #1358
                )
                if not result.passed:
                    issue_ctx = f" (issue #{current_issue_str})" if current_issue_str else ""
                    return (
                        "deny",
                        f"BLOCKED: Prompt for '{agent_type}'{issue_ctx} shrank {result.shrinkage_pct:.1f}% "
                        f"from baseline ({baseline_word_count} words → {word_count} words, "
                        f"threshold: 20%). "
                        f"The agent prompt is being compressed across invocations. "
                        f"REQUIRED NEXT ACTION: Use get_agent_prompt_template('{agent_type}') "
                        f"to reload the full agent prompt from disk and reconstruct with complete context.",
                    )
            else:
                # No baseline yet — seed from OBSERVED word count (Issue #759, #810).
                # Template files (~2500 words) are far larger than task-specific
                # prompts (~200-600 words) because templates contain the full agent
                # definition while the coordinator sends focused task context.
                # Template-based seeding (even at 0.70 slack) produced baselines of
                # ~1700 words, causing 25-50% false positive block rate in batch mode.
                # The observed word count is the correct baseline for cross-issue
                # shrinkage detection. seed_baselines_from_templates() is deprecated.
                #
                # Issue #764: Use current issue number instead of hardcoded 0.
                seed_issue = int(current_issue_str) if current_issue_str else 0
                record_prompt_baseline(
                    agent_type, issue_number=seed_issue, word_count=word_count,
                    pipeline_mode=pipeline_mode,  # Issue #1358
                )
                _pi_logger.debug(
                    "Seeded baseline from observation: %s issue #%d = %d words",
                    agent_type, seed_issue, word_count,
                )
                # Also record as batch observation for cumulative drift tracking (Issue #794)
                from prompt_integrity import record_batch_observation as _record_obs
                _record_obs(agent_type, seed_issue, word_count)
        except (IOError, OSError, json.JSONDecodeError) as exc:
            # Baseline-file I/O problems must not block agents (documented fail-open)
            _pi_logger.warning("Prompt-integrity baseline I/O error — fail-open: %s", exc)
        except Exception as exc:
            _pi_logger.error(
                "Prompt-integrity gate-internal error — FAIL-CLOSED: %s", exc, exc_info=True
            )
            return (
                "deny",
                f"BLOCKED: prompt-integrity gate failed internally "
                f"({type(exc).__name__}: {exc}). REQUIRED NEXT ACTION: report this as "
                f"an autonomous-dev bug via /create-issue; do not retry blind.",
            )

    # Cumulative drift check (Issue #794) — same fail-open/fail-closed split (Issue #1471)
    try:
        from prompt_integrity import (
            record_batch_observation,
            get_cumulative_shrinkage,
            MAX_CUMULATIVE_SHRINKAGE,
        )
    except ImportError as exc:
        _pi_logger.warning(
            "prompt_integrity unavailable — cumulative check skipped (fail-open): %s", exc
        )
    else:
        try:
            issue_for_obs = _get_current_issue_number()
            record_batch_observation(agent_type, issue_for_obs, word_count)
            cumulative = get_cumulative_shrinkage(agent_type)
            if cumulative is not None and cumulative >= MAX_CUMULATIVE_SHRINKAGE * 100:
                return (
                    "deny",
                    f"BLOCKED: Cumulative prompt drift for '{agent_type}' is {cumulative:.1f}% "
                    f"across this batch (threshold: {MAX_CUMULATIVE_SHRINKAGE:.0%}). "
                    f"Individual issues pass but the overall trend shows progressive compression. "
                    f"REQUIRED NEXT ACTION: Use get_agent_prompt_template('{agent_type}') "
                    f"to reload the full agent prompt from disk and reconstruct with complete context.",
                )
        except (IOError, OSError, json.JSONDecodeError) as exc:
            _pi_logger.warning("Cumulative-drift I/O error — fail-open: %s", exc)
        except Exception as exc:
            _pi_logger.error(
                "Cumulative-drift gate-internal error — FAIL-CLOSED: %s", exc, exc_info=True
            )
            return (
                "deny",
                f"BLOCKED: prompt-integrity cumulative gate failed internally "
                f"({type(exc).__name__}: {exc}). REQUIRED NEXT ACTION: report this as "
                f"an autonomous-dev bug via /create-issue; do not retry blind.",
            )

    return ("allow", f"Prompt integrity OK: {agent_type} has {word_count} words (>= {MIN_CRITICAL_AGENT_PROMPT_WORDS})")


def validate_pipeline_ordering(tool_name: str, tool_input: Dict) -> Tuple[str, str]:
    """
    Layer 4: Pipeline ordering gate — enforce agent invocation order.

    Checks that Agent tool calls during an active pipeline respect the
    SEQUENTIAL_REQUIRED ordering from pipeline_intent_validator.py.
    Fail-open: any error in the check defaults to allow.

    Issues: #625, #629, #632

    Args:
        tool_name: Name of the tool being called.
        tool_input: Tool input parameters.

    Returns:
        Tuple of (decision, reason).
    """
    try:
        # Env var kill switch
        if os.getenv("PRE_TOOL_PIPELINE_ORDERING", "true").lower() != "true":
            return ("allow", "Pipeline ordering disabled via env var")

        # Only check Agent/Task tool calls
        if tool_name not in AGENT_TOOL_NAMES:
            return ("allow", f"Tool '{tool_name}' is not an agent invocation")

        # Only check during active pipeline
        if not _is_pipeline_active():
            return ("allow", "No active pipeline - ordering check skipped")

        # Extract agent type — prefer explicit subagent_type over text extraction
        # (text extraction can match wrong agent when prompt contains other agent names)
        target_agent = tool_input.get("subagent_type", "").strip().lower()
        if not target_agent:
            task_desc = tool_input.get("task_description", "") or tool_input.get("prompt", "")
            target_agent = _extract_subagent_type(task_desc)
        if not target_agent:
            return ("allow", "Could not determine target agent - allowing")

        # Import completion state and ordering gate
        from pipeline_completion_state import (
            get_completed_agents,
            get_launched_agents,
            get_validation_mode,
            record_agent_launch,
        )
        from agent_ordering_gate import check_ordering_with_session_fallback

        session_id = _session_id or os.getenv("CLAUDE_SESSION_ID", "unknown")
        issue_number = _get_current_issue_number()

        # Issue #686: Record agent launch BEFORE checking prerequisites.
        # This tracks that PreToolUse fired for this agent, enabling the
        # parallel-mode defense-in-depth guard to distinguish "running
        # concurrently" from "skipped entirely".
        record_agent_launch(session_id, target_agent, issue_number=issue_number)

        completed = get_completed_agents(session_id, issue_number=issue_number)
        launched = get_launched_agents(session_id, issue_number=issue_number)
        mode = get_validation_mode(session_id)

        # SKIP_PYTEST_GATE escape hatch (Issue #838)
        skip_pytest = os.environ.get("SKIP_PYTEST_GATE", "").strip().lower()
        if skip_pytest in ("1", "true", "yes"):
            completed.add("pytest-gate")

        # Issue #697: Read pipeline_mode from state file to filter prerequisites.
        # In --fix mode, planner is not part of the pipeline, so the
        # planner->implementer prerequisite must be skipped.
        pipeline_mode = _get_pipeline_mode_from_state()

        gate = check_ordering_with_session_fallback(
            target_agent,
            session_id,
            issue_number=issue_number,
            validation_mode=mode,
            pipeline_mode=pipeline_mode,
        )
        if not gate.passed:
            # Issue #1227: Set redispatch flag when ordering gate denies
            try:
                from prompt_integrity import set_redispatch_flag
                set_redispatch_flag(target_agent)
            except Exception:
                pass  # Never fail the hook for flag setting
            return ("deny", f"{gate.reason} (session_id: {session_id})")

        # Issue #669: Log parallel mode warnings for observability
        if gate.warning:
            import logging

            logger = logging.getLogger("unified_pre_tool.ordering")
            logger.warning("%s", gate.warning)

        return ("allow", f"Ordering OK: {target_agent} prerequisites met")

    except Exception as e:
        # Fail-open: ordering check errors must not block workflow.
        # Issue #669: Log a warning when failing open for security-critical ordering pairs,
        # since a crash in the ordering check could silently allow security-auditor
        # before reviewer completes.
        import logging

        logger = logging.getLogger("unified_pre_tool.ordering")
        logger.warning(
            "Pipeline ordering check failed open for tool='%s': %s. "
            "If this involves security-auditor, the ordering guarantee is NOT enforced. "
            "Issue #669.",
            tool_name,
            e,
        )
        return ("allow", f"Pipeline ordering check error (fail-open): {e}")


def _extract_subagent_type(task_description: str) -> str:
    """Extract agent type name from a task description string.

    Looks for patterns like:
    - "Run the implementer agent"
    - "researcher-local"
    - "You are the security-auditor"

    Args:
        task_description: The task description or prompt text.

    Returns:
        Lowercase agent type, or empty string if not found.
    """
    import re

    text = task_description.lower()

    # Known agent types to look for
    known_agents = [
        "researcher-local", "researcher", "planner", "test-master",
        "implementer", "reviewer", "security-auditor", "doc-master",
        "continuous-improvement-analyst",
    ]

    # Check for exact agent name mentions (longest first to match "researcher-local" before "researcher")
    for agent in sorted(known_agents, key=len, reverse=True):
        if agent in text:
            return agent

    return ""


def validate_mcp_security(tool_name: str, tool_input: Dict) -> Tuple[str, str]:
    """
    Validate MCP security (path traversal, injection, SSRF).

    Args:
        tool_name: Name of the tool being called
        tool_input: Tool input parameters

    Returns:
        Tuple of (decision, reason)
        - decision: "allow", "deny", or "ask"
        - reason: Human-readable reason for decision
    """
    # Native Claude Code tools skip MCP security (not MCP tools)
    if tool_name in NATIVE_TOOLS:
        return ("allow", f"Native tool '{tool_name}' - MCP security not applicable")

    # Check if MCP security is enabled
    enabled = os.getenv("PRE_TOOL_MCP_SECURITY", "true").lower() == "true"
    if not enabled:
        return ("allow", "MCP security disabled")

    try:
        # Try to import MCP security validator
        try:
            from mcp_security_validator import validate_mcp_operation

            # Validate the operation
            is_safe, reason = validate_mcp_operation(tool_name, tool_input)

            if not is_safe:
                # Security risk detected
                return ("deny", f"MCP Security: {reason}")
            else:
                return ("allow", f"MCP Security: {reason}")

        except ImportError:
            # MCP security validator not available — default to allow.
            # Previously this fell through to auto_approval_engine which used
            # an allow-list (auto_approve_policy.json). That caused recurring
            # "Not whitelisted" regressions every time Claude Code added new
            # tools. Default-allow with deny-only-on-security is simpler and
            # eliminates that entire class of regressions (Issue #401).
            return ("allow", "MCP security validator unavailable — default allow")

    except Exception as e:
        # The validator was PRESENT and its execution CRASHED. That is a
        # different state from the ImportError branch above, and Issue #401's
        # rationale does not cover it: #401 argues for "we deliberately chose
        # not to check", this is "we tried to check and do not know the answer".
        # Encoding the second as allow is an INV-7 breach — the operation is
        # unverified, not verified-safe.
        import logging as _mcp_logging

        _mcp_logging.getLogger("unified_pre_tool.mcp_security").error(
            "MCP security validator crashed while validating '%s' — FAIL-CLOSED: %s",
            tool_name,
            e,
            exc_info=True,
        )
        return (
            "deny",
            f"BLOCKED: MCP security validation crashed for '{tool_name}' "
            f"({type(e).__name__}: {e}). The validator was present but could not "
            f"complete, so this operation is unverified — not verified safe. "
            f"REQUIRED NEXT ACTION: report this as an autonomous-dev bug via "
            f"/create-issue, quoting the error above. Do not retry blind. "
            f"Emergency override: set PRE_TOOL_MCP_SECURITY=false to disable this "
            f"layer, or `touch .claude/.bypass` (AUTONOMOUS_DEV_BYPASS=1) to "
            f"disable all hooks for this repo.",
        )


def _is_exempt_path(file_path: str) -> bool:
    """Check if file is exempt from workflow enforcement (tests, docs, configs)."""
    if not file_path:
        return False
    path = Path(file_path)
    path_str = str(path).lower()
    # Test files
    if ('test_' in path_str or '_test.' in path_str or '.test.' in path_str
            or path_str.startswith('tests/') or path_str.startswith('test/')):
        return True
    # Docs, configs, hooks, scripts, lib, agents, commands
    if path.suffix.lower() in {'.md', '.txt', '.rst', '.json', '.yaml', '.yml', '.toml', '.env', '.ini', '.cfg'}:
        return True
    if any(s in path_str for s in ['.claude/hooks/', 'hooks/', '/lib/', 'lib/', '.claude/agents/',
                                    '.claude/commands/', '.claude/skills/', 'scripts/']):
        return True
    return False


def _is_autonomous_dev_repo(file_path: str) -> bool:
    """Check if file is inside a repo where autonomous-dev is installed.

    Walks up from file_path looking for .claude/commands/implement.md,
    which only exists in repos with the autonomous-dev plugin installed.

    Args:
        file_path: Absolute path to check

    Returns:
        True if file is inside an autonomous-dev-managed repo
    """
    try:
        current = Path(file_path).resolve().parent
    except (OSError, ValueError):
        return False
    # Don't let the walk-up reach the user's home directory: the global
    # autonomous-dev install at ~/.claude/commands/implement.md is meant for
    # the user's tooling, not to mark every project under ~ as autonomous-dev.
    try:
        home = Path.home().resolve()
    except (OSError, ValueError):
        home = None
    # Walk up at most 10 levels to find repo root
    for _ in range(10):
        if home is not None and current == home:
            break
        marker = current / ".claude" / "commands" / "implement.md"
        if marker.exists():
            return True
        parent = current.parent
        if parent == current:
            break
        current = parent
    return False


def _is_protected_infrastructure(file_path: str) -> bool:
    """Check if file is a protected infrastructure file (agents, commands, hooks, lib, skills).

    Protected files require the /implement pipeline for edits.
    Only applies to repos where autonomous-dev is installed — other repos are unaffected.

    Args:
        file_path: Path to the file being edited

    Returns:
        True if the file is in a protected directory with matching extension
    """
    if not file_path:
        return False
    # Resolve symlinks and normalize to absolute path for security (A01)
    try:
        resolved = str(Path(file_path).resolve())
    except (OSError, ValueError):
        resolved = file_path
    # Only protect infrastructure in autonomous-dev repos (not all repos globally)
    if not _is_autonomous_dev_repo(resolved):
        return False
    # Normalize separators to forward slashes for consistent matching
    normalized = resolved.replace("\\", "/")
    # Extensions directory is user-owned — never protected
    if "/extensions/" in normalized:
        return False
    # Test files are never protected — even if they live under hooks/ or lib/
    if "/tests/" in normalized or "/test/" in normalized:
        return False
    path_basename = Path(file_path).name
    if path_basename.startswith("test_") or path_basename.endswith("_test.py"):
        return False
    # Per-file protection (Issue #980): explicit file allowlist with strict
    # suffix matching — prevents partial-basename false positives.
    for protected_file in PROTECTED_INFRA_FILES:
        # Match both absolute paths ending with the suffix AND a bare relative path.
        # endswith with leading "/" prevents partial-basename false positives
        # (e.g., "foo_install_manifest.json" must not match).
        if normalized.endswith("/" + protected_file) or normalized == protected_file:
            return True
    # Ensure leading slash or check for bare directory name at start
    for segment, extensions in PROTECTED_INFRA_SEGMENTS.items():
        # segment is like '/agents/' — check both embedded and path-start forms
        bare = segment.lstrip("/")  # 'agents/'
        if segment in normalized or normalized.startswith(bare):
            ext = Path(file_path).suffix.lower()
            if ext in extensions:
                return True
    return False


def _enforce_protected_infrastructure(tool_name: str, tool_input: dict) -> None:
    """Protected-infrastructure hard floor — INV-4 (Issues #483, #1296, #1435).

    Blocks writes to agents/, commands/, hooks/, lib/, skills/ unless the
    /implement pipeline is active AND the implementer agent is the actor.
    Denies via ``output_decision`` + ``sys.exit(0)``; returns None when the
    call is permitted.

    Issue #1503 relocated this block OUT of the native-tool fast path. It
    previously lived inside ``if tool_name in NATIVE_TOOLS:`` and tested
    ``tool_name in ("Write", "Edit")``, which meant:
      - NotebookEdit entered the fast path, failed the tuple test, and fell
        through to the terminal "Native tool — hook bypass" allow;
      - MultiEdit is not in NATIVE_TOOLS at all, so it skipped the fast path
        (and therefore this gate) entirely;
      - every MCP editor did the same.
    Running upstream of the fast path makes the hard floor reachable for every
    write transport. Threat model: accidental direct edits, not a malicious
    local attacker. CLAUDE_AGENT_NAME is set by Claude Code; env var trust is
    by design. Fail-closed: if the check itself errors, block the write
    (A04 remediation).

    DOCUMENTED BEHAVIOUR CHANGE (#1503): ``_check_plan_exit_native`` used to
    run BEFORE this block, so when both would fire the plan-exit message won.
    After the relocation the infrastructure message wins. deny stays deny —
    only the visible reason changes.

    Args:
        tool_name: The tool name from the PreToolUse payload.
        tool_input: The tool input dict from the PreToolUse payload.

    Returns:
        None. Exits the process with a deny decision when the write is denied.
    """
    # Bash is deliberately OUT of scope for this block (Issue #1503).
    # Pre-#1503 the guard was ``tool_name in ("Write", "Edit")``, which is
    # False for Bash, so this hard floor never evaluated Bash commands.
    # Bash has its own dedicated coverage in ``_check_bash_infra_writes``
    # with intentionally different semantics — an active-pipeline implementer
    # may use ``sed -i``/``tee`` on protected paths. Routing Bash through
    # here as well silently tightened that and broke
    # test_bash_write_to_protected_path_allowed_when_pipeline_active.
    # #1503 widened this gate to reach MultiEdit, NotebookEdit and MCP
    # editors — transports that previously escaped it — NOT to change Bash.
    if tool_name == "Bash":
        return
    if not _ti_is_write(tool_name, tool_input):
        return
    file_path = _ti_first_write_target(tool_name, tool_input)
    try:
        is_protected = _is_protected_infrastructure(file_path)
        pipeline_active = _is_pipeline_active() if is_protected else False
    except Exception:
        # Fail closed — if protection check errors, treat as protected
        is_protected = True
        pipeline_active = False
    if not is_protected:
        return

    # Issue #1296: pipeline-active is NOT a blanket permit. The implementer agent
    # must be the actor — coordinator direct-edits to protected paths during an
    # active pipeline are also blocked.
    if pipeline_active:
        try:
            from agent_dispatch_sentinel import is_active as _ads_is_active
            from agent_dispatch_sentinel import reap_if_stale as _ads_reap_if_stale
            # Issue #1512: is_active() is now a pure predicate. Reap explicitly
            # first so this gate's observable outcome is unchanged — a stale
            # sentinel is unlinked, then read as absent, then denied.
            try:
                _ads_reap_if_stale()
            except Exception:
                pass  # Reaping is opportunistic; the gate decision does not depend on it
            if not _ads_is_active():
                file_name = Path(file_path).name if file_path else "unknown"
                block_reason = (
                    f"BLOCKED: Coordinator cannot directly edit protected path '{file_name}' "
                    f"mid-pipeline. Re-dispatch the implementer agent with this "
                    f"change as a remediation cycle. (Issue #1296) "
                    f"REQUIRED NEXT ACTION: Use the Task tool to invoke the implementer "
                    f"agent to make this change. Do NOT edit infrastructure files directly."
                )
                _log_deviation(file_name, tool_name, "coordinator_bypass_block")
                _log_pretool_activity(tool_name, tool_input, "deny", block_reason)
                output_decision(
                    "deny", block_reason,
                    system_message=(
                        f"Coordinator cannot directly edit protected path '{file_path}' "
                        f"mid-pipeline. Re-dispatch the implementer agent. (Issue #1296)"
                    )
                )
                sys.exit(0)
        except ImportError:
            # Issue #1296: Fail CLOSED when sentinel library missing for security-critical check
            file_name = Path(file_path).name if file_path else "unknown"
            block_reason = (
                f"BLOCKED: Sentinel library missing — security-critical component unavailable, "
                f"refusing to allow protected-path edit to '{file_name}'. "
                f"The agent_dispatch_sentinel module is required for coordinator bypass detection."
            )
            _log_deviation(file_name, tool_name, "sentinel_import_error_block")
            _log_pretool_activity(tool_name, tool_input, "deny", block_reason)
            output_decision(
                "deny", block_reason,
                system_message=(
                    f"Sentinel library missing — cannot verify agent dispatch status. "
                    f"Blocking protected-path edit for security. (Issue #1296)"
                )
            )
            sys.exit(0)
        # implementer-dispatched edit: permit as before (fall through to WPG/other checks)
        return

    file_name = Path(file_path).name if file_path else "unknown"
    block_reason = (
        f"BLOCKED: Direct edit to '{file_name}' denied. "
        f"Infrastructure files (agents/, commands/, hooks/, lib/, skills/) "
        f"require the /implement pipeline. Run: /implement \"description\" "
        f"REQUIRED NEXT ACTION: Run /implement with a description of your "
        f"change. Delegate the edit to the implementer agent. "
        f"Do NOT write infrastructure files directly."
    )
    _log_deviation(file_name, tool_name, "infrastructure_protection_block")
    _log_pretool_activity(tool_name, tool_input, "deny", block_reason)
    output_decision(
        "deny", block_reason,
        system_message=(
            f"BLOCKED: Direct edit to '{file_name}' denied. "
            f"Use /implement to modify infrastructure files."
        ),
    )
    # Issue #803: Record denial for cross-tool workaround detection.
    # If the agent retries via Bash heredoc, the deny cache catches it.
    try:
        _update_deny_cache(file_path)
    except Exception:
        pass  # Never fail the hook for cache writes
    sys.exit(0)


def _get_active_agent_name() -> str:
    """Get the active agent name from available sources (Issue #591).

    Priority order:
    1. agent_type from hook stdin JSON (available inside subagents)
    2. CLAUDE_AGENT_NAME env var (set by Claude Code in some contexts)

    Returns:
        Lowercase agent name, or empty string if not in an agent context.
    """
    if _agent_type:
        return _agent_type.strip().lower()
    env_name = os.getenv("CLAUDE_AGENT_NAME", "").strip().lower()
    return env_name


def _is_stale_session(state: dict, state_path: "Path") -> bool:
    """Check if pipeline state belongs to a different (stale) session (Issue #592).

    Compares session_id in state file against current session's _session_id.
    If different and both are non-empty/non-unknown, state is stale -- remove file.

    Args:
        state: Parsed pipeline state dict.
        state_path: Path to the state file (for removal).

    Returns:
        True if state is stale (file removed), False if current or indeterminate.

    Note: When either session_id is "unknown" or empty (e.g., first hook
    invocation before stdin parsing), this returns False (indeterminate).
    This is an accepted gap — callers fall back to safe defaults (0 for
    issue_number, "full" for mode), and the 30-min mtime TTL in
    _is_pipeline_active() provides a secondary staleness guard.
    """
    stored_sid = state.get("session_id", "")
    # #1171: sanitize untrusted env-var input before equality compare.
    current_sid = _resolve_session_id_safe(_session_id) or "unknown"

    if not stored_sid or stored_sid == "unknown" or not current_sid or current_sid == "unknown":
        return False  # Cannot determine, fall through to TTL/HMAC

    if stored_sid != current_sid:
        try:
            state_path.unlink(missing_ok=True)
        except OSError:
            pass
        return True

    return False


def _is_issue_command_active() -> bool:
    """Check if an issue-creating command is currently active (Issue #630).

    Reads the command context JSON file written by /create-issue, /plan-to-issues,
    /improve, /refactor, and /retrospective before they create issues.

    Fail-closed: returns False on any error (missing file, bad JSON, stale timestamp,
    unknown command).

    Returns:
        True if a recognized issue command wrote the context file within the last hour.
    """
    try:
        import json as _json
        import time as _time

        context_path = Path(GH_ISSUE_COMMAND_CONTEXT_PATH)
        if not context_path.exists():
            return False

        with open(context_path) as f:
            data = _json.load(f)

        command = data.get("command")
        if command not in GH_ISSUE_COMMANDS:
            return False

        # Use file modification time for age check (harder to spoof than JSON timestamp)
        age = _time.time() - context_path.stat().st_mtime
        if age > 3600:
            return False

        return True
    except Exception:
        return False  # Fail-closed on any error


def _get_current_issue_number() -> int:
    """Get the current pipeline issue number with file-based fallback.

    Issue #779: Env vars set via ``export`` in one Bash tool call do NOT
    persist to subsequent Bash calls because each invocation gets a fresh
    shell.  The hook process inherits env from the Claude Code parent
    process, not from a previous Bash session.

    Resolution order:
        1. ``PIPELINE_ISSUE_NUMBER`` env var (set by Claude Code process)
        2. ``issue_number`` field in the pipeline state file
           (``<repo>/.claude/local/implement_pipeline_state.json`` since
           Issue #1206; was ``/tmp/implement_pipeline_state.json``)
        3. Issue number extracted from ``run_id`` field in the pipeline state
           file (Issue #869: batch mode run_ids follow pattern
           ``issue-{N}-YYYYMMDD-HHMMSS``)
        4. ``0`` as a safe default (no issue context)

    Returns:
        The current issue number, or 0 if unavailable.
    """
    # 1. Env var takes precedence when available
    env_val = os.getenv("PIPELINE_ISSUE_NUMBER")
    if env_val and env_val != "0":
        try:
            return int(env_val)
        except (ValueError, TypeError):
            pass

    # 2. Fall back to pipeline state file
    pipeline_state_file = os.getenv(
        "PIPELINE_STATE_FILE", str(get_legacy_sentinel_path())
    )
    try:
        state_path = Path(pipeline_state_file)
        if state_path.exists():
            import json as _json

            with open(state_path) as f:
                state = _json.load(f)
            # Session staleness check (Issue #862)
            if _is_stale_session(state, state_path):
                return 0  # Stale session — safe default
            issue_num = state.get("issue_number", 0)
            if isinstance(issue_num, int) and issue_num > 0:
                return issue_num
            # Also handle string values
            if isinstance(issue_num, str) and issue_num.isdigit():
                return int(issue_num)

            # Issue #869: Fallback — extract issue number from run_id field.
            # Batch mode run_ids follow pattern: issue-{N}-YYYYMMDD-HHMMSS
            run_id = state.get("run_id", "")
            if isinstance(run_id, str) and run_id.startswith("issue-"):
                import re as _re

                match = _re.match(r"issue-(\d+)-", run_id)
                if match:
                    return int(match.group(1))
    except Exception:
        pass  # Fail open — return 0

    # 3. Default
    return 0


def _get_pipeline_mode_from_state() -> str:
    """Read pipeline mode from the state file.

    Returns the mode field from the pipeline state file (e.g., "full", "fix", "light").
    Falls back to "full" if the state file is missing, unreadable, or lacks a mode field.

    Issue #697: Needed to filter ordering prerequisites by pipeline mode.
    In --fix mode, planner is not part of the pipeline.
    Issue #849: PIPELINE_MODE env-var takes precedence at all call-sites.
    Issue #1173: mtime-TTL fallback closes the indeterminate-session gap where
    stale fix-mode state would leak into a fresh --light run.
    Issue #1027 refinement: the #1173 mtime-TTL->"full" fallback is scoped to
    INDETERMINATE sessions only. A CONFIRMED same-session run (stored
    session_id == current session_id, both known/non-"unknown") honors
    state.get("mode") regardless of mtime age — a long-running --light run must
    not be misclassified as "full" merely because 30 min elapsed since the last
    state write. The mismatched-known-session leak is already handled earlier by
    _is_stale_session() (which unlinks the foreign file); indeterminate sessions
    remain TTL-guarded, so no cross-session leakage is reintroduced.

    Returns:
        Pipeline mode string, defaulting to "full".
    """
    # Issue #849/#1173: env-var takes precedence (eliminates call-site asymmetry
    # where line 1108 honors PIPELINE_MODE but other call-sites went through this
    # function and silently ignored it).
    env_mode = os.getenv("PIPELINE_MODE", "").strip()
    if env_mode:
        return env_mode

    pipeline_state_file = os.getenv("PIPELINE_STATE_FILE", str(get_legacy_sentinel_path()))
    try:
        state_path = Path(pipeline_state_file)
        if state_path.exists():
            import json as _json

            with open(state_path) as f:
                state = _json.load(f)
            # Session staleness check (Issue #862)
            if _is_stale_session(state, state_path):
                return "full"  # Stale session — safe default
            # Issue #1173: mtime-TTL fallback. When session_id is indeterminate
            # (e.g. 'unknown'), _is_stale_session() returns False and stale mode
            # would otherwise leak. Treat state older than the TTL as expired.
            # Issue #1027: scope the TTL fallback to INDETERMINATE sessions only.
            # A confirmed same-session run (stored == current, both known) honors
            # the stored mode regardless of mtime age, so a long-running --light
            # run is not misclassified as "full" after 30 min of inactivity.
            stored_sid = state.get("session_id", "")
            current_sid = _resolve_session_id_safe(_session_id) or "unknown"
            same_session_confirmed = (
                bool(stored_sid)
                and stored_sid != "unknown"
                and bool(current_sid)
                and current_sid != "unknown"
                and stored_sid == current_sid
            )
            if not same_session_confirmed:
                import time as _time
                mtime = state_path.stat().st_mtime
                if _time.time() - mtime >= _PIPELINE_STATE_TTL_SECONDS:
                    return "full"
            return state.get("mode", "full")
    except Exception:
        pass
    return "full"


_SELF_MAINT_CACHE: "dict[str, bool]" = {}


def _is_self_maintenance_mode() -> bool:
    """Detect if we are operating inside the canonical autonomous-dev source.

    Returns True iff a parent of the current working directory (up to 30
    levels) contains ``plugins/autonomous-dev/.claude-plugin/marketplace.json``
    — the canonical-source marker. This identifies the autonomous-dev repo
    itself (where maintainers edit the framework) versus any consumer repo
    where the plugin is installed via ``.claude/``.

    Used to relax gates whose enforcement intent is "consumer protections"
    rather than "framework correctness". The test gate, security audit,
    doc-master verdict, and prompt-integrity baselines remain enforced —
    they are dogfooding requirements. Only the gates that exist to keep
    consumer-repo maintainers from accidentally editing installed framework
    files relax here, because in autonomous-dev itself those files ARE the
    work product.

    Result is cached per-cwd within this process (the cwd rarely changes
    mid-hook-invocation and the walk is cheap, but the cache keeps it from
    showing up in flamegraphs).

    Returns:
        True if cwd is inside the canonical autonomous-dev source tree.
    """
    try:
        key = str(Path.cwd().resolve())
    except (OSError, RuntimeError):
        return False
    cached = _SELF_MAINT_CACHE.get(key)
    if cached is not None:
        return cached

    marker = Path("plugins") / "autonomous-dev" / ".claude-plugin" / "marketplace.json"
    try:
        current = Path(key)
        for _ in range(30):
            if (current / marker).exists():
                _SELF_MAINT_CACHE[key] = True
                return True
            parent = current.parent
            if parent == current:
                break
            current = parent
    except (OSError, RuntimeError):
        pass

    _SELF_MAINT_CACHE[key] = False
    return False


def _is_settings_template_path(file_path: str) -> bool:
    """Return True iff file_path is a plugin-source settings template path.

    Used to short-circuit the Issue #557 settings guard for template files under
    plugins/*/templates/ — these are work products (template source), not the
    runtime settings files the guard is designed to protect. Issue #1001.

    Tightened after security-auditor MEDIUM (A01 Broken Access Control):
    the helper previously matched any path with a ``templates`` component,
    which would also bypass the guard for runtime paths like
    ``.claude/templates/settings.local.json``. The check now requires
    ``"plugins"`` to appear as a path component BEFORE ``"templates"`` in
    the resolved parts tuple, scoping the bypass to genuine plugin
    template-source paths only.

    Args:
        file_path: The path string from tool_input["file_path"].

    Returns:
        True if the resolved path has a ``templates`` component preceded
        somewhere by a ``plugins`` component. False on empty input,
        resolution error, missing ``templates`` component, or
        ``templates`` not preceded by ``plugins``.
    """
    if not file_path:
        return False
    try:
        parts = Path(file_path).resolve().parts
        if "templates" not in parts:
            return False
        templates_idx = parts.index("templates")
        return "plugins" in parts[:templates_idx]
    except (OSError, RuntimeError, ValueError):
        return False


def _is_plugin_source_path(file_path: str) -> bool:
    """Return True iff file_path resolves under a real autonomous-dev source tree.

    Used by the Issue #557 settings-write guard self-maintenance branch
    (Issue #1111) to detect writes that target the canonical
    autonomous-dev plugin source tree. The previous substring check
    (``"plugins/autonomous-dev/" in str(file_path)``) would also match
    unrelated paths like ``/tmp/plugins/autonomous-dev/...`` (security-
    auditor LOW, A01).

    The tightened check has TWO requirements (both must hold):

    1. ``"plugins"`` and ``"autonomous-dev"`` appear as ADJACENT
       components (in that order) in the resolved path parts.
    2. An ancestor of that ``plugins/autonomous-dev/`` directory contains
       the canonical marker
       ``plugins/autonomous-dev/.claude-plugin/marketplace.json`` — i.e.
       the path actually lives inside a real autonomous-dev source tree,
       not a look-alike directory layout under ``/tmp`` or similar.

    Args:
        file_path: The path string from tool_input["file_path"].

    Returns:
        True iff both conditions above hold. False on empty input,
        resolution error, missing adjacency, or no canonical marker.
    """
    if not file_path:
        return False
    try:
        parts = Path(file_path).resolve().parts
        adj_idx: int | None = None
        for i, p in enumerate(parts):
            if p == "plugins" and i + 1 < len(parts) and parts[i + 1] == "autonomous-dev":
                adj_idx = i
                break
        if adj_idx is None:
            return False
        # Verify a real autonomous-dev source tree by checking for the
        # canonical marker file at the ancestor that owns the
        # plugins/autonomous-dev/ directory.
        repo_root = Path(*parts[:adj_idx]) if adj_idx > 0 else Path(parts[0])
        marker = repo_root / "plugins" / "autonomous-dev" / ".claude-plugin" / "marketplace.json"
        return marker.exists()
    except (OSError, RuntimeError):
        return False


def _targets_nested_claude_dir(file_path: str) -> bool:
    """True iff ``file_path`` sits in a ``.claude/`` nested under plugin source.

    Issue #1726: two stray ``.claude/`` trees accumulated inside
    ``plugins/autonomous-dev/`` — a directory that ships to consumer repos via
    ``install_manifest.json`` and is not covered by the root ``.gitignore``.
    They were self-perpetuating: any cwd walk-up from a deeper directory found
    the stray first, forever.

    The refused class is "a ``.claude`` path component appearing BELOW a real
    ``plugins/autonomous-dev/`` source tree" — not one named subdirectory.
    Three conditions must all hold, so the legitimate cases stay permitted:

    * ``plugins`` and ``autonomous-dev`` are adjacent components, and
    * some later component is exactly ``.claude`` — which is why the
      marketplace install layout ``~/.claude/plugins/autonomous-dev/...``
      (``.claude`` BEFORE the plugin dir) and the shipped ``.claude-plugin/``
      directory are both permitted, and
    * the tree carries the canonical
      ``plugins/autonomous-dev/.claude-plugin/marketplace.json`` marker, so a
      look-alike layout under ``/tmp`` is not gated.

    Args:
        file_path: The candidate write target.

    Returns:
        True when the write belongs to the refused class.
    """
    if not file_path:
        return False
    try:
        parts = Path(file_path).resolve().parts
        adj_idx: int | None = None
        for i, part in enumerate(parts):
            if part == "plugins" and i + 1 < len(parts) and parts[i + 1] == "autonomous-dev":
                adj_idx = i
                break
        if adj_idx is None:
            return False
        if ".claude" not in parts[adj_idx + 2:]:
            return False
        repo_root = Path(*parts[:adj_idx]) if adj_idx > 0 else Path(parts[0])
        marker = repo_root / "plugins" / "autonomous-dev" / ".claude-plugin" / "marketplace.json"
        return marker.exists()
    except (OSError, RuntimeError, ValueError):
        return False


def _enforce_no_nested_claude_dir(tool_name: str, tool_input: dict) -> None:
    """Refuse writes that create a ``.claude/`` tree inside plugin source (#1726).

    Companion to the Issue #1726 resolver fix: the three hooks no longer WRITE
    stray activity logs there, and this refuses anything else from CREATING the
    directory again. Runs for every write transport via ``_ti_is_write`` /
    ``_ti_write_targets``, so MultiEdit, NotebookEdit and MCP editors are
    covered, not just Write/Edit.

    Bash is deliberately out of scope. Measured: ``tool_intent.write_targets``
    reports the SOURCE of a deletion as a write target
    (``rm -rf plugins/autonomous-dev/commands/.claude`` ->
    ``['plugins/autonomous-dev/commands/.claude']``), so gating Bash here would
    block the authorised removal of the two stray trees that already exist.

    Args:
        tool_name: The tool name from the PreToolUse payload.
        tool_input: The tool input dict from the PreToolUse payload.

    Returns:
        None. Exits the process with a deny decision when the write is refused.
    """
    if tool_name == "Bash":
        return
    try:
        if not _ti_is_write(tool_name, tool_input):
            return
        offending = next(
            (t for t in _ti_write_targets(tool_name, tool_input)
             if _targets_nested_claude_dir(t)),
            None,
        )
    except Exception:
        return  # Never fail the hook for this check — it is additive, not a floor
    if offending is None:
        return

    block_reason = (
        f"BLOCKED: '{offending}' would create a .claude/ directory inside "
        f"plugins/autonomous-dev/ — shipped plugin source that is NOT covered "
        f"by the root .gitignore, so the tree gets distributed to consumer "
        f"repos and committed by one 'git add -A'. Stray .claude/ trees are "
        f"self-perpetuating and split the session record. (Issue #1726) "
        f"REQUIRED NEXT ACTION: Write to the repo-root .claude/ instead, or "
        f"choose a path outside plugins/autonomous-dev/."
    )
    _log_deviation(Path(offending).name, tool_name, "nested_claude_dir_block")
    _log_pretool_activity(tool_name, tool_input, "deny", block_reason)
    output_decision(
        "deny", block_reason,
        system_message=(
            f"BLOCKED: refusing to create a .claude/ directory inside "
            f"plugins/autonomous-dev/ ('{offending}'). Use the repo-root "
            f".claude/ instead. (Issue #1726)"
        ),
    )
    sys.exit(0)


def _is_batch_context(cwd: str) -> bool:
    """Return True when the current invocation is part of a batch.

    Issue #1133: Batch context can be signaled two ways:

    1. **Worktree mode** (the original): the current working directory is
       inside a ``.worktrees/batch-*`` directory. This is the default for
       ``/implement --batch`` and ``/implement --issues`` in repos where
       ``.claude/*`` is NOT gitignored.
    2. **In-place mode** (no-worktree, Issue #1133): the environment
       variable ``BATCH_NO_WORKTREE`` is set to ``1`` / ``true`` / ``yes``.
       This mirrors the ``BATCH_AUTO_APPROVE`` precedent (Issue #323) for
       repos like autonomous-dev where ``.claude/`` is gitignored.

    Centralizing the check ensures all three batch-context gates (CIA
    completion, doc-master completion, agent completeness) fire
    consistently regardless of which batch mode is active.

    Args:
        cwd: Current working directory string.

    Returns:
        True if either signal indicates batch context.
    """
    if ".worktrees/batch-" in cwd:
        return True
    return os.environ.get("BATCH_NO_WORKTREE", "").strip().lower() in ("1", "true", "yes")


# Issue #1173 — 30-min TTL for pipeline state staleness. Used by
# _is_pipeline_active() (mtime liveness check) and _get_pipeline_mode_from_state()
# (mtime-based fallback when session-id is indeterminate).
_PIPELINE_STATE_TTL_SECONDS = 1800


def _is_pipeline_active() -> bool:
    """Check if the /implement pipeline is currently active.

    Checks two sources:
    1. CLAUDE_AGENT_NAME env var against known pipeline agents (touches state file mtime)
    2. Pipeline state file (valid if mtime < 30 min old; Issue #636)

    Returns:
        True if pipeline is active
    """
    # Check agent name (Issue #591: prefer stdin agent_type over env var)
    agent_name = _get_active_agent_name()
    if agent_name in PIPELINE_AGENTS:
        # Issue #941: refresh mtime ONLY when this session OWNS the state file.
        # Previously this was unconditional (Issue #636) which let concurrent
        # sessions inadvertently keep a foreign session's stale state alive.
        # Preserves #636: the owning session keeps its own mtime fresh.
        # Fixes #941: a parallel pipeline run does not refresh another
        # session's sentinel.
        pipeline_state_file = os.getenv(
            "PIPELINE_STATE_FILE", str(get_legacy_sentinel_path())
        )
        try:
            current_sid = os.environ.get("CLAUDE_SESSION_ID", "")
            should_touch = True  # default: preserve #636 if we cannot read state
            state_path = Path(pipeline_state_file)
            if state_path.exists():
                try:
                    import json as _json_touch
                    with open(state_path) as _fh_touch:
                        _state_for_touch = _json_touch.load(_fh_touch)
                    state_sid = _state_for_touch.get("session_id", "") if isinstance(_state_for_touch, dict) else ""
                    if state_sid and current_sid and state_sid != current_sid:
                        should_touch = False  # foreign-owned: do not refresh
                except (OSError, ValueError, json.JSONDecodeError):
                    pass  # Unreadable/corrupt: fall back to touch (preserves #636)
            if should_touch:
                Path(pipeline_state_file).touch()
        except OSError:
            pass
        return True

    # Check pipeline state file
    pipeline_state_file = os.getenv("PIPELINE_STATE_FILE", str(get_legacy_sentinel_path()))
    try:
        state_path = Path(pipeline_state_file)
        if state_path.exists():
            import json as _json
            from datetime import datetime as _datetime
            with open(state_path) as f:
                state = _json.load(f)

            # Session staleness check (Issue #592)
            if _is_stale_session(state, state_path):
                return False

            # HMAC integrity check (Issue #557)
            if state.get("hmac") is not None:
                try:
                    from pipeline_state import verify_state_hmac
                    # #1171: sanitize untrusted env-var before HMAC verify.
                    sid = _resolve_session_id_safe(_session_id) or "unknown"
                    if not verify_state_hmac(state, sid):
                        _log_deviation("pipeline_state", "hmac_check", "pipeline_state_hmac_invalid")
                        return False  # Fail closed: tampered state = not active
                except ImportError:
                    return False  # Fail closed: HMAC present but verify library unavailable

            # Issue #1384: a bare recovery heartbeat is NOT a live pipeline.
            # pipeline_completion_state.py writes {"session_id","recovered","recovered_at"}
            # on restart -- no run_id/mode/explicitly_invoked and no hmac (skips the
            # integrity branch above) so it would otherwise sail through the mtime-TTL
            # return True for 30 min. A genuine STEP-0 sentinel always carries at least one
            # of run_id/mode/explicitly_invoked, so the any(...) guard keeps real active
            # pipelines classified active (unchanged).
            if state.get("recovered") and not any(
                state.get(k) for k in ("run_id", "mode", "explicitly_invoked")
            ):
                return False

            # Use file mtime for staleness (Issue #636).
            # Pipeline agents touch this file on each hook call (see above),
            # keeping mtime fresh during legitimate runs. A failed/abandoned
            # pipeline stops invoking agents, so mtime stalls and expires.
            # 30 min TTL covers long implementer runs with margin.
            import time as _time
            mtime = state_path.stat().st_mtime
            age_seconds = _time.time() - mtime
            if age_seconds < _PIPELINE_STATE_TTL_SECONDS:  # 30 minutes since last agent activity
                return True
    except Exception:
        pass

    return False


def _is_explicit_implement_active() -> bool:
    """Check if /implement was explicitly invoked by the user (Issue #528).

    Reads the pipeline state file and checks for the 'explicitly_invoked' flag.
    This distinguishes user-invoked /implement from other pipeline activity,
    enabling hard blocking of coordinator code writes during explicit sessions.

    Returns:
        True if /implement was explicitly invoked and session is within TTL
    """
    pipeline_state_file = os.getenv(
        "PIPELINE_STATE_FILE", str(get_legacy_sentinel_path())
    )
    try:
        state_path = Path(pipeline_state_file)
        if not state_path.exists():
            return False
        import json as _json
        from datetime import datetime as _datetime

        with open(state_path) as f:
            state = _json.load(f)

        # Session staleness check (Issue #592)
        if _is_stale_session(state, state_path):
            return False

        # HMAC integrity check (Issue #557)
        if state.get("hmac") is not None:
            try:
                from pipeline_state import verify_state_hmac
                # #1171: sanitize untrusted env-var before HMAC verify.
                sid = _resolve_session_id_safe(_session_id) or "unknown"
                if not verify_state_hmac(state, sid):
                    _log_deviation("pipeline_state", "hmac_check", "explicit_implement_hmac_invalid")
                    return False  # Fail closed: tampered state = not active
            except ImportError:
                return False  # Fail closed: HMAC present but verify library unavailable

        # Must have explicitly_invoked flag set to true
        if not state.get("explicitly_invoked", False):
            return False
        # Check session TTL (2 hours)
        session_start = state.get("session_start", "")
        if not session_start:
            return False
        start_time = _datetime.fromisoformat(session_start)
        elapsed = (_datetime.now() - start_time).total_seconds()
        if elapsed >= 7200:  # 2 hours TTL
            return False
        return True
    except (json.JSONDecodeError, ValueError, KeyError, OSError, TypeError):
        return False


def _alignment_strict_available() -> bool:
    """True when alignment_classifier (Issue #1467) is importable next to this hook."""
    try:
        import alignment_classifier  # noqa: F401
        return True
    except Exception:
        # Record WHY strict enforcement degraded — could be a legitimate
        # consumer install (library absent) or a broken deploy (library
        # present but raising on import). Never let the logging call itself
        # break the fail-open path.
        try:
            _log_deviation("alignment_classifier_import", "hook", "alignment_strict_unavailable")
        except Exception:
            pass
        return False


def _allowed_alignment_verdicts() -> frozenset:
    """Verdicts that count as "alignment passed" (Issue #1467).

    Sourced from ``alignment_classifier.ALLOWED_VERDICTS`` so the hook and the
    library cannot drift. The literal fallback keeps consumer installs that ship
    the hook without the classifier library working.

    Returns:
        Frozenset of allowed verdict strings ("auto_pass", "user_approved").
    """
    try:
        from alignment_classifier import ALLOWED_VERDICTS
        return frozenset(ALLOWED_VERDICTS)
    except Exception:
        # Same rationale as _alignment_strict_available(): record why the
        # literal fallback was used so an operator can distinguish "library
        # legitimately absent" from "library present but broken."
        try:
            _log_deviation("alignment_classifier_import", "hook", "allowed_verdicts_fallback")
        except Exception:
            pass
        return frozenset({"auto_pass", "user_approved"})


def _load_pipeline_state_verified() -> Optional[dict]:
    """Load the pipeline state, returning it only when fresh and HMAC-valid.

    Shared loader for the alignment gates (Issues #585, #592, #1171, #1467).
    On any error (file missing, JSON invalid, stale session, HMAC failure) this
    returns None so callers can fail closed.

    Returns:
        The verified pipeline state dict, or None when it cannot be trusted.
    """
    pipeline_state_file = os.getenv(
        "PIPELINE_STATE_FILE", str(get_legacy_sentinel_path())
    )
    try:
        state_path = Path(pipeline_state_file)
        if not state_path.exists():
            return None
        import json as _json

        with open(state_path) as f:
            state = _json.load(f)

        # Session staleness check (Issue #592)
        if _is_stale_session(state, state_path):
            return None

        # HMAC integrity check — fail closed on any verification failure
        if state.get("hmac") is not None:
            try:
                from pipeline_state import verify_state_hmac
                # #1171: sanitize untrusted env-var before HMAC verify.
                sid = _resolve_session_id_safe(_session_id) or "unknown"
                if not verify_state_hmac(state, sid):
                    _log_deviation(
                        "pipeline_state", "hmac_check", "alignment_gate_hmac_invalid"
                    )
                    return None
            except ImportError:
                return None  # Fail closed: HMAC present but verify library unavailable

        return state
    except (Exception,):
        return None  # Fail closed on any error


def _explicit_alignment_verdict_block() -> Optional[str]:
    """Return the verdict when verified state carries a present-but-disallowed one.

    Returns:
        The offending verdict string, or None when there is nothing to block on
        (no state, no verdict field, allowed verdict, or strict mode unavailable).
    """
    state = _load_pipeline_state_verified()
    if not state:
        return None
    verdict = state.get("alignment_verdict")
    if verdict is None or not _alignment_strict_available():
        return None
    return None if verdict in _allowed_alignment_verdicts() else verdict


def _has_alignment_passed() -> bool:
    """Check if STEP 2 alignment has passed in the pipeline state (Issue #585).

    Reads the pipeline state file and verifies that alignment_passed is True.
    HMAC integrity is verified to prevent tampering. On any error (file missing,
    JSON invalid, HMAC fails), returns False (fail closed).

    Issue #1467 extends the boolean with a co-signed ``alignment_verdict``. When
    the field is present AND the classifier library ships alongside this hook,
    the verdict must be in ALLOWED_VERDICTS. Legacy states (field absent) and
    consumer installs without the library keep the pre-#1467 boolean behavior.

    Returns:
        True if alignment has passed and HMAC is valid
    """
    state = _load_pipeline_state_verified()
    if state is None:
        return False

    if state.get("alignment_passed", False) is not True:
        return False

    verdict = state.get("alignment_verdict")
    if verdict is None:
        return True  # Legacy / pre-#1467 state: boolean is the whole contract
    if not _alignment_strict_available():
        return True  # Graceful degradation: no library, no verdict enforcement
    if verdict in _allowed_alignment_verdicts():
        return True

    _log_deviation("pipeline_state", "alignment_verdict", "alignment_verdict_disallowed")
    return False


# Non-code file extensions exempt from explicit /implement coordinator blocking
_NON_CODE_EXTENSIONS = {
    ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini",
    ".md", ".txt", ".rst", ".csv", ".env",
}


def _is_code_file_target(tool_name: str, tool_input: Dict) -> bool:
    """Check if the tool operation targets a code file (Issue #528).

    Protected infrastructure files (agents/*.md, commands/*.md, skills/*.md)
    are treated as code targets regardless of their .md extension (Issue #623).
    The extension-based exemption only applies to regular docs and config files.

    Args:
        tool_name: Name of the tool (Write, Edit, Bash)
        tool_input: Tool input parameters

    Returns:
        True if the tool targets a code file or protected infrastructure file
    """
    # Issue #1503: transport-independent. MultiEdit/NotebookEdit/MCP editors
    # target code files exactly as Write and Edit do.
    if tool_name != "Bash" and _ti_is_write(tool_name, tool_input):
        file_path = _ti_first_write_target(tool_name, tool_input)
        if not file_path:
            return False
        # Issue #1408: scratch checked FIRST — a scratch path is never a gated
        # code target. Mirrors _is_gated_repo_source's ordering exactly.
        if _is_scratch_path(file_path):
            return False
        # Issue #623: Protected infrastructure files (agents/*.md, commands/*.md,
        # skills/*.md) must be treated as code targets regardless of extension.
        if _is_protected_infrastructure(file_path):
            return True
        suffix = Path(file_path).suffix.lower()
        # Exempt non-code files (README.md, docs/*.md, config files, etc.)
        if suffix in _NON_CODE_EXTENSIONS:
            return False
        # Check against known code extensions
        return suffix in CODE_EXTENSIONS
    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        if not command:
            return False
        target_files = _extract_bash_file_writes(command)
        for fp in target_files:
            # Issue #1408: scratch checked FIRST — a scratch redirect target is
            # never a gated code target. Same ordering as the Write/Edit branch.
            if _is_scratch_path(fp):
                continue
            # Issue #623: Infrastructure .md files in Bash redirects are code targets
            if _is_protected_infrastructure(fp):
                return True
            suffix = Path(fp).suffix.lower()
            if suffix in _NON_CODE_EXTENSIONS:
                continue
            if suffix in CODE_EXTENSIONS:
                return True
        return False
    return False


def _has_significant_additions(old_string: str, new_string: str, file_path: str = "") -> tuple:
    """Check if the edit adds significant code (new functions, classes, >5 lines)."""
    import re
    old_string = old_string or ""
    new_string = new_string or ""

    file_ext = Path(file_path).suffix.lower() if file_path else ""

    # Collect applicable patterns
    applicable_patterns = []
    for group_name, group_data in PATTERN_GROUPS.items():
        extensions = group_data['extensions']
        if extensions is None:  # universal
            applicable_patterns.extend(group_data['patterns'])
        elif not file_ext:  # no file path = backward compat, use all
            applicable_patterns.extend(group_data['patterns'])
        elif file_ext in extensions:
            applicable_patterns.extend(group_data['patterns'])

    for pattern, desc in applicable_patterns:
        old_matches = len(re.findall(pattern, old_string, re.MULTILINE))
        new_matches = len(re.findall(pattern, new_string, re.MULTILINE))
        if new_matches > old_matches:
            match = re.search(pattern, new_string)
            if match:
                return True, f"New {desc} detected", match.group(0)[:60]

    old_lines = len(old_string.strip().split('\n')) if old_string.strip() else 0
    new_lines = len(new_string.strip().split('\n')) if new_string.strip() else 0
    added = max(0, new_lines - old_lines)
    if added >= SIGNIFICANT_LINE_THRESHOLD:
        return True, "Significant code change detected", f"+{added} lines"
    return False, "", ""


#: The one-shot operator bypass sentinel for the write-pipeline gate.
#: Declared once so the (single) consumption site and every message that
#: advertises it cannot drift apart.
WRITE_GATE_BYPASS_SENTINEL = Path("/tmp/skip_write_pipeline_gate")

#: Wall-clock time at which THIS hook process began. Module import is the first
#: thing a hook process does, so this is a faithful proxy for process start.
#:
#: It is the discriminator that tells a CONCURRENT sibling invocation of the
#: same tool call apart from a LATER, separate tool call (Issue #1641). Claude
#: Code merges hook registrations across settings surfaces and runs every match
#: in parallel, so one PreToolUse event can spawn N copies of this hook. Sibling
#: invocations all start BEFORE any of them consumes the token, so comparing
#: start time to the receipt's mtime admits them; a tool call issued after the
#: previous call's hooks returned starts after the mtime, so it is refused.
#:
#: What that is NOT: a proof that no later call can ever be admitted. The
#: comparison is only ever reached for a receipt under the SAME ``call_key``,
#: which requires byte-identical ``(tool_name, file_path, old_string,
#: new_string)``. A separate, later call that replays an identical payload — an
#: agent-side retry of the very same Write after a timeout, say — and whose
#: hook process happens to start before the winning sibling's receipt mtime
#: would be admitted as a sibling. The window is bounded by one hook's runtime
#: (~1.7 s) and requires a full content collision, which is why this is judged
#: an acceptable residual rather than a hole; it is a narrow precondition, not
#: an impossibility. There is deliberately no arbitrary time window on top.
_HOOK_PROCESS_START_TIME: float = time.time()

#: Upper bound on how long a consumption receipt is honoured. Receipts only
#: ever need to outlive the slowest sibling in the same PreToolUse fan-out
#: (the hook's own configured timeout is 20 s), so this is garbage-collection
#: hygiene rather than the security boundary — the boundary is the process
#: start-time comparison above, which no amount of elapsed time can satisfy
#: for a later tool call.
WRITE_GATE_BYPASS_RECEIPT_TTL_SECONDS = 60.0


def _write_gate_bypass_call_key(
    tool_name: str, file_path: str, old_string: str, new_string: str
) -> str:
    """Derive a stable identity for one logical Write/Edit tool call.

    Every sibling invocation spawned for the same PreToolUse event receives a
    byte-identical ``tool_input``, so hashing it yields the same key in each
    copy of the hook without needing an event id the payload does not carry.

    Args:
        tool_name: The tool name ("Write" or "Edit").
        file_path: The target file path.
        old_string: The pre-edit content (empty for a new-file Write).
        new_string: The post-edit content.

    Returns:
        A 32-character hex digest identifying this logical tool call.
    """
    import hashlib

    digest = hashlib.sha256()
    for part in (tool_name, file_path, old_string, new_string):
        digest.update(str(part).encode("utf-8", "replace"))
        digest.update(b"\x00")
    return digest.hexdigest()[:32]


def _write_gate_bypass_receipt_path(call_key: str) -> Path:
    """Path of the consumption receipt for ``call_key``.

    Derived from :data:`WRITE_GATE_BYPASS_SENTINEL` (never re-constructed from
    a literal) and namespaced by uid so receipts cannot collide between users
    on a shared ``/tmp``.

    Args:
        call_key: Digest from :func:`_write_gate_bypass_call_key`.

    Returns:
        The receipt file path.
    """
    try:
        uid = os.getuid()  # type: ignore[attr-defined]
    except AttributeError:  # pragma: no cover - non-POSIX
        uid = 0
    return WRITE_GATE_BYPASS_SENTINEL.with_name(
        f".{WRITE_GATE_BYPASS_SENTINEL.name}.receipt.{uid}.{call_key}"
    )


def _read_write_gate_bypass_receipt(call_key: str) -> bool:
    """Is there a receipt proving a CONCURRENT sibling already spent the token?

    Four conditions must all hold. Any one of them failing means this is not a
    sibling of the current tool call, and the receipt grants nothing:

    1. The receipt exists, is owned by us, and parses.
    2. It was written by a DIFFERENT process — a receipt never grants its own
       author a second shot, which is what keeps the token one-shot for
       repeated in-process calls.
    3. This process started BEFORE the receipt was written. A sibling of the
       same fan-out passes this; a later tool call issued after the previous
       call's hooks returned fails it. See
       :data:`_HOOK_PROCESS_START_TIME` for the residual this does NOT cover.
    4. The receipt is within :data:`WRITE_GATE_BYPASS_RECEIPT_TTL_SECONDS`.

    Args:
        call_key: Digest from :func:`_write_gate_bypass_call_key`.

    Returns:
        True when the current invocation may honour the sibling's consumption.
    """
    receipt = _write_gate_bypass_receipt_path(call_key)
    try:
        stat_result = receipt.stat()
    except OSError:
        return False

    age = time.time() - stat_result.st_mtime
    if age > WRITE_GATE_BYPASS_RECEIPT_TTL_SECONDS or age < -WRITE_GATE_BYPASS_RECEIPT_TTL_SECONDS:
        try:
            receipt.unlink()  # stale garbage; never a valid grant
        except OSError:
            pass
        return False

    try:
        if hasattr(os, "getuid") and stat_result.st_uid != os.getuid():
            return False  # planted by someone else -> not auditable, not honoured
    except OSError:
        return False

    try:
        record = json.loads(receipt.read_text())
    except (OSError, ValueError):
        return False
    if not isinstance(record, dict) or record.get("pid") == os.getpid():
        return False

    return _HOOK_PROCESS_START_TIME < stat_result.st_mtime


def _claim_write_gate_bypass_receipt(call_key: str, file_path: str) -> str:
    """Atomically claim the right to spend the one-shot token for this call.

    Exactly one invocation in a fan-out can win, which is what keeps
    consumption logged exactly once no matter how many copies of the hook
    Claude Code launches.

    The receipt is published by writing a private temp file and then
    ``os.link``-ing it into place. ``link`` fails with ``FileExistsError`` when
    the target exists, so it is the mutual exclusion; and because the content is
    already complete before the name appears, a sibling can never observe a
    half-written receipt. (``O_CREAT | O_EXCL`` is atomic for the NAME only —
    the write that follows is not, which leaves exactly that window open.)

    The staging file itself is opened ``O_CREAT | O_EXCL``: its path is
    derivable, so it must be CREATED by this process, never adopted from
    whatever already occupies the name.

    Args:
        call_key: Digest from :func:`_write_gate_bypass_call_key`.
        file_path: Target file, recorded in the receipt for forensics.

    Returns:
        ``"won"`` - this invocation holds the claim and MUST log and unlink.
        ``"deferred"`` - a concurrent sibling holds it; grant without logging.
        ``"unavailable"`` - no receipt could be published; the caller proceeds
        as the sole consumer (fail-open: a receipt is coordination, not a gate).
    """
    receipt = _write_gate_bypass_receipt_path(call_key)
    staging = receipt.with_name(f"{receipt.name}.staging.{os.getpid()}")
    payload = json.dumps(
        {
            "pid": os.getpid(),
            "consumed_at": time.time(),
            "process_start": _HOOK_PROCESS_START_TIME,
            "file_path": file_path,
        },
        separators=(",", ":"),
    )
    # O_EXCL, not O_TRUNC: the staging path is DERIVABLE (receipt name +
    # ".staging." + pid), so anything already sitting there was put there by
    # someone else. Without O_EXCL this open follows a planted symlink and
    # truncates its target with the hook's own privileges. With it, an occupied
    # name simply fails to create and the claim reports "unavailable" — the
    # pre-existing failure semantics, unchanged. Note that "unavailable" only
    # ever grants a bypass when the real sentinel was already confirmed
    # present, so this is not a fail-open on the decision.
    try:
        fd = os.open(str(staging), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except OSError:
        # We did not create it, so we do not write it and we do not remove it.
        # Unlinking here would delete an operator's file (or a symlink whose
        # removal masks the attempt) on behalf of whoever planted it.
        return "unavailable"

    try:
        try:
            with os.fdopen(fd, "w") as handle:
                handle.write(payload)
        except OSError:
            return "unavailable"

        for _attempt in (0, 1):
            try:
                os.link(str(staging), str(receipt))
                return "won"
            except FileExistsError:
                # Re-read on EVERY collision, never only the first. Two racers
                # can both find the same STALE receipt, both sweep it, and one
                # of them then win the re-link — so the second attempt can
                # collide with a receipt that is now a legitimate sibling's.
                # Checking only the first attempt would unlink that live receipt
                # and return "unavailable", and this copy would go on to log a
                # second consumption for a single token, breaking the
                # log-exactly-once invariant this whole mechanism exists for.
                if _read_write_gate_bypass_receipt(call_key):
                    return "deferred"
                # A receipt that fails the sibling test while the sentinel is
                # still on disk is left over from an EARLIER consumption. Clear
                # it and retry once, so a stale file cannot hand out a free
                # bypass — nor block the fan-out that follows it.
                try:
                    receipt.unlink()
                except FileNotFoundError:
                    pass  # already swept by the staleness check — retry anyway
                except OSError:
                    return "unavailable"
                continue
            except OSError:
                return "unavailable"
        return "unavailable"
    finally:
        try:
            staging.unlink()
        except OSError:
            pass


def _consume_write_gate_bypass(file_path: str = "", *, call_key: str = "") -> bool:
    """Consume the one-shot operator bypass sentinel, if it is present.

    This is the SINGLE sanctioned consumption point for
    :data:`WRITE_GATE_BYPASS_SENTINEL`. It MUST only be called once a gate has
    already established that it would otherwise REFUSE the current tool call.

    Rationale (the defect this shape removes): the sentinel used to be checked
    eagerly, at the top of both :func:`_check_write_pipeline_required` and
    :func:`_check_bash_code_file_pipeline_required`, *before* either gate had
    determined that it applied at all. Consequently any tool call that reached
    a gate burned the operator's one-shot token even though nothing was ever
    going to be refused — a bare ``ls`` reaching the Bash gate, or a Write to
    ``README.md`` reaching the Write/Edit gate, silently spent it. The operator
    then followed the gate's own printed instructions, found the token already
    gone, and was refused anyway. Deferring consumption to the point of refusal
    removes that whole class: the token can now only ever be spent to buy
    passage past an actual refusal.

    A one-shot token must not be consumable by more than one gate, so the
    advisory-only Bash path (downgraded to non-blocking in Issue #1408) does
    NOT consume it — there is nothing there to bypass. The Write/Edit gate is
    the sole consumer.

    Issue #1641 — the second half of the defect, which the fix above did not
    reach. ONE PreToolUse event does not mean ONE invocation of this hook.
    Claude Code merges hook registrations across settings surfaces, and
    ``unified_pre_tool.py`` is registered with matcher ``*`` in BOTH the
    project ``.claude/settings.json`` and the user's ``~/.claude/settings.json``
    — so a single Write spawned two concurrent copies. The production activity
    log shows it plainly: at ``23:00:28.181`` copy A logged
    ``write_pipeline_gate: operator_bypass`` and allowed; at ``23:00:28.548``
    copy B, 367 ms behind and now looking at a ``/tmp`` with no sentinel in it,
    logged ``BLOCKED ... Tier: full``. Claude Code takes the deny. The operator
    watched the token vanish and the write refused anyway.

    Consumption is therefore made idempotent PER LOGICAL TOOL CALL rather than
    per process: the winner of an atomic claim spends and logs the token, and
    every concurrent sibling of the SAME call honours its receipt. See
    :func:`_read_write_gate_bypass_receipt` for why this cannot extend the
    one-shot to a later tool call.

    Args:
        file_path: The target file being written/edited, recorded in the audit
            log. Empty string when no specific path applies.
        call_key: Identity of the logical tool call, from
            :func:`_write_gate_bypass_call_key`. Empty string disables sibling
            coordination and restores strict per-process consumption — correct
            for any caller that cannot identify its tool call.

    Returns:
        True when the bypass applies to this call (the caller MUST then allow
        the operation); False otherwise.

    Note:
        CONSUMPTION is logged exactly once via
        :func:`_log_write_gate_bypass_consumed` (Issue #1356), which records
        the scoped-escape reason and the sentinel's age. Siblings that defer to
        a receipt consume nothing, so they never emit that event — but they do
        GRANT the write, so they emit :func:`_log_write_gate_bypass_deferred`
        instead. The two events are distinct on purpose: one token still
        produces exactly one ``..._consumed`` record no matter how wide the
        fan-out, while no path can grant a bypass and leave no trace at all.
        Removal of the sentinel fails OPEN: a filesystem error unlinking it
        must not crash the hook, and the bypass still counts as consumed.
    """
    skip_file = WRITE_GATE_BYPASS_SENTINEL

    # A concurrent sibling invocation of this same tool call may already have
    # spent the token. Honour its receipt so every copy of the hook returns the
    # same verdict for one PreToolUse event (Issue #1641).
    if call_key and _read_write_gate_bypass_receipt(call_key):
        _log_write_gate_bypass_deferred(file_path, call_key)
        return True

    try:
        sentinel_present = skip_file.exists()
    except OSError:
        sentinel_present = False  # cannot tell -> no bypass we cannot audit

    if not sentinel_present:
        # Re-read the receipt before refusing. A sibling may have published its
        # receipt and unlinked the sentinel in the interval between our two
        # reads — that interleaving is the whole bug, and checking only once
        # leaves a window in which this copy refuses a write already paid for.
        # The claim always publishes BEFORE unlinking, so an absent sentinel
        # caused by a sibling always has a receipt standing behind it.
        if call_key and _read_write_gate_bypass_receipt(call_key):
            _log_write_gate_bypass_deferred(file_path, call_key)
            return True
        return False

    if call_key:
        # Claim BEFORE logging and BEFORE unlinking: the receipt must be on disk
        # for the whole window in which the sentinel is gone, or a sibling would
        # find neither and refuse.
        if _claim_write_gate_bypass_receipt(call_key, file_path) == "deferred":
            _log_write_gate_bypass_deferred(file_path, call_key)
            return True

    # Log BEFORE unlinking: the logger reads the sentinel's own contents as the
    # scoped-escape reason (Issue #1408), so it must still be on disk.
    _log_write_gate_bypass_consumed(file_path, skip_file)
    try:
        skip_file.unlink()
    except OSError:
        pass  # fail-open on unlink — bypass still consumed
    return True


def _check_write_pipeline_required(
    tool_name: str,
    file_path: str,
    old_string: str,
    new_string: str,
    *,
    session_id: "Optional[str]" = None,
) -> "tuple[bool, str, str]":
    """Decide if a Write/Edit on production code requires the /implement pipeline.

    Args:
        tool_name: The tool name ("Write" or "Edit").
        file_path: The target file path.
        old_string: The pre-edit content (empty string for new-file Write).
        new_string: The post-edit content.
        session_id: Optional pipeline session id used by the Phase 2
            sliding-window check. When provided, ``fix`` tier blocks are
            recorded into the per-session ring buffer; when the rolling
            cumulative-lines-added across the last 60 s window for the
            same ``(session_id, file_path)`` crosses
            ``TIER_LIGHT_LINE_THRESHOLD`` the returned tier label is
            escalated from ``fix`` to ``light`` with reason marker
            ``cumulative_sliding_window``. When ``None`` the sliding
            window is skipped — preserving the Phase 1 contract for
            callers that have not been updated yet (#1146).

    Returns:
        (block, tier_label, directive)
        - block: True means caller MUST emit a deny decision.
        - tier_label: one of "pipeline_active", "operator_bypass", "no_path",
          "tier0_non_code", "tier0_test_file", "tier0_scratch_path",
          "tier0_out_of_tree", "fix", "light", "full", "wpg_check_error".
          "tier0_scratch_path" = ephemeral/scratch location (Issue #1408).
          "tier0_out_of_tree" = outside a git worktree or gitignored (#1408).
        - directive: human-readable REQUIRED NEXT ACTION (empty when block False).

    Phase 1 (Issue #1142+): default-on. The previous opt-IN check via
    `.claude/.enforce` was removed; per-repo opt-OUT is now via the existing
    `.claude/.bypass` marker (already short-circuited at line ~4532). The old
    line-count heuristic is replaced by `classify_edit_tier()` which returns
    one of three tiers — `fix` / `light` / `full` — each mapped to the
    matching `/implement` variant in the directive.

    Phase 2 (Issue #1146): sliding-window escalation for emergent bypass via
    tool-call granularity mismatch. See ``session_id`` arg above.
    """
    # Tier 0b: pipeline already active — already in-flow, allow
    try:
        if _is_pipeline_active():
            return (False, "pipeline_active", "")
    except Exception:
        pass  # fall through; if we cannot tell, continue with other checks

    # NOTE: the one-shot operator bypass is NOT checked here. It used to be
    # (as "Tier 0c"), which meant every Write/Edit that reached this function
    # consumed it — including writes to docs, tests, scratch paths and
    # out-of-tree files that Tier 0d–0h below allow unconditionally. The token
    # is now consumed only at the point of actual refusal, after Tier 0h. See
    # _consume_write_gate_bypass.

    # Tier 0d: no path provided
    if not file_path:
        return (False, "no_path", "")

    # Tier 0e: non-code extension — not applicable
    suffix = Path(file_path).suffix.lower()
    if suffix not in CODE_EXTENSIONS:
        return (False, "tier0_non_code", "")

    # Tier 0f: test file — excluded (reuse pattern from _is_protected_infrastructure)
    fp_lower = file_path.lower()
    if "/tests/" in fp_lower or "/test/" in fp_lower:
        return (False, "tier0_test_file", "")
    basename = Path(file_path).name
    if basename.startswith("test_") or basename.endswith("_test.py"):
        return (False, "tier0_test_file", "")

    # Tier 0g: ephemeral / scratch paths — excluded. Files at these
    # absolute locations are never committed (covered by .gitignore +
    # repo discipline) and never user-facing, so the /implement pipeline
    # review adds no value but charges a UX tax every time the agent
    # needs a one-off helper script or scratch file. Restricted to
    # ABSOLUTE prefixes so a literal ``/tmp/foo.sh`` is exempt but
    # ``./tmp/foo.sh`` inside a project named ``tmp`` is NOT.
    #
    # NOTE: this is orthogonal to the security guard in
    # :func:`_is_plugin_source_path` (which prevents an attacker
    # placing a look-alike ``/tmp/plugins/autonomous-dev/...`` tree to
    # be trusted as a plugin source). Pipeline gating is about review
    # discipline, not trust elevation; the two concerns don't overlap.
    # Uses the module-level EPHEMERAL_PREFIXES + $SCRATCHPAD/.claude/tmp/
    # awareness via _is_scratch_path (Issue #1408).
    if _is_scratch_path(file_path):
        return (False, "tier0_scratch_path", "")

    # Tier 0h: git-worktree-aware scoping (Issue #1408). Only in-worktree,
    # non-ignored repo source stays gated. Out-of-tree files and gitignored
    # paths are not gated (the pipeline review adds no value for files that are
    # never committed). Fails open to _is_autonomous_dev_repo scoping on any
    # git error — never raises.
    if not _is_gated_repo_source(file_path):
        return (False, "tier0_out_of_tree", "")

    # Tier 0i: one-shot operator bypass (mirrors the
    # /tmp/skip_agent_completeness_gate pattern). Deliberately placed HERE and
    # not at the top: every Tier 0 exit above returns block=False, so this is
    # the first point at which refusal is certain — whatever tier the
    # classifier below assigns, the function returns block=True. Consuming the
    # token only when a refusal is actually being bought means an unrelated
    # doc/test/scratch write can no longer silently spend it.
    #
    # It also precedes the sliding-window bookkeeping so a bypassed edit does
    # not pollute the per-(session, file) ring buffer.
    #
    # The call key (Issue #1641) makes the consumption idempotent across the
    # several concurrent copies of this hook that one PreToolUse event spawns
    # when the hook is registered on more than one settings surface. It is
    # derived from the tool payload alone — deliberately NOT from session_id,
    # which is not guaranteed identical between copies.
    if _consume_write_gate_bypass(
        file_path,
        call_key=_write_gate_bypass_call_key(
            tool_name, file_path, old_string or "", new_string or ""
        ),
    ):
        return (False, "operator_bypass", "")

    # Tier classification via AST-based classifier (Phase 1, #1142+).
    tier, reason = _safe_classify_edit_tier(file_path, old_string or "", new_string or "")

    # Phase 2 (Issue #1146): sliding-window cumulative escalation.
    # When the classifier returns ``fix`` (Tier-1) AND a session_id is
    # available, query the per-(session, file) ring buffer. If the rolling
    # sum of lines-added in the last 60 s plus this edit's added lines
    # crosses the Tier-2 threshold (20), ESCALATE the returned tier label
    # from ``fix`` to ``light`` and tag the reason. The ring buffer is
    # then dropped so a single threshold trigger does not keep firing on
    # subsequent edits.
    #
    # On allow paths (``fix`` not escalated): record this edit's added
    # lines so the NEXT call sees the cumulative.
    escalated_by_sliding_window = False
    if tier == "fix" and session_id:
        try:
            new_lines = _count_added_lines_for_sliding_window(old_string or "", new_string or "")
            existing = _get_recent_tier1_allows(session_id, file_path, window_seconds=60)
            existing_sum = sum(int(e.get("lines", 0)) for e in existing)
            if existing_sum + new_lines >= _TIER_LIGHT_LINE_THRESHOLD_LOCAL:
                tier = "light"
                reason = (
                    f"cumulative_sliding_window: existing_sum={existing_sum} "
                    f"new={new_lines} >= threshold={_TIER_LIGHT_LINE_THRESHOLD_LOCAL}"
                )
                escalated_by_sliding_window = True
                # Reset so the deny does not keep firing on subsequent edits.
                _clear_tier1_ring_buffer(session_id, file_path)
            else:
                _record_tier1_allow(session_id, file_path, new_lines)
        except Exception:
            # Sliding-window check failures must NEVER worsen the gate.
            pass

    # Map tier -> /implement variant (the 3-door menu).
    file_name = Path(file_path).name
    if tier == "fix":
        flag = "--fix "
    elif tier == "light":
        flag = "--light "
    else:
        # full (or unknown fallback) -> bare /implement
        tier = "full" if tier not in ("fix", "light", "full") else tier
        flag = ""
    directive = (
        f"Run /implement {flag}\"<brief description of change to {file_name}>\". "
        f"Operator one-shot bypass: touch {WRITE_GATE_BYPASS_SENTINEL}."
    )
    if escalated_by_sliding_window:
        directive = (
            f"cumulative_sliding_window: {reason}. " + directive
        )
    return (True, tier, directive)


def _check_bash_code_file_pipeline_required(
    command: str,
    *,
    session_id: "Optional[str]" = None,
) -> "tuple[bool, str, str, str]":
    """Decide if a Bash command writing to a code file requires /implement.

    Mirrors `_check_write_pipeline_required` for the Bash tool path. Detects
    cat >, sed -i, tee, heredocs, python -c open(), awk redirects, etc.,
    targeting code files (CODE_EXTENSIONS).

    Args:
        command: The raw Bash command string.
        session_id: Optional pipeline session id used by the Phase 2
            sliding-window check. When provided and the detected tier is
            ``fix``-equivalent (the classifier's safe default for empty
            old/new is ``light``, so this rarely fires through this path —
            see ``_check_write_pipeline_required`` for the primary site).

    Returns:
        (block, tier_label, directive, target_path)
        - target_path: the detected code-file path (empty when no match).
        Block is False when the command does not target a code file, the
        command is excluded user-patch tooling (`git apply`, `patch < diff`),
        or the pipeline is already active / operator bypass is set.

    Phase 1 (Issue #1142+).
    Phase 2 (Issue #1146): ``session_id`` arg for sliding-window symmetry.
    """
    if not command:
        return (False, "no_command", "", "")

    # Pipeline active — allow (the model is in-flow).
    try:
        if _is_pipeline_active():
            return (False, "pipeline_active", "", "")
    except Exception:
        pass

    # NOTE: this path does NOT consume the one-shot operator bypass sentinel.
    # It used to, unconditionally and before the detector below had even run,
    # so ANY Bash command whatsoever — `ls`, `git status` — spent the
    # operator's token. Since Issue #1408 this gate is ADVISORY: it never
    # refuses, so there is nothing here for a bypass to buy. The Write/Edit
    # gate is the sole consumer (see _consume_write_gate_bypass), which is what
    # keeps a single token from being spendable by two gates.

    # Detect the code-file write target.
    if _detect_bash_code_file_write_fn is None:
        return (False, "detector_unavailable", "", "")
    try:
        target, pattern = _detect_bash_code_file_write_fn(command)
    except Exception:
        return (False, "detector_error", "", "")

    if not target:
        return (False, "no_code_target", "", "")

    # Test files: pass.
    target_lower = target.lower()
    if "/tests/" in target_lower or "/test/" in target_lower:
        return (False, "tier0_test_file", "", target)
    basename = Path(target).name
    if basename.startswith("test_") or basename.endswith("_test.py"):
        return (False, "tier0_test_file", "", target)

    # Scratch / out-of-tree scoping (Issue #1408) — mirror the Write/Edit gate
    # so this (now advisory) path does not fire on scratch or out-of-tree
    # targets. Scratch first (never gated), then git-worktree scoping.
    if _is_scratch_path(target):
        return (False, "tier0_scratch_path", "", target)
    if not _is_gated_repo_source(target):
        return (False, "tier0_out_of_tree", "", target)

    # Classify — for in-place edits like sed -i we cannot see the patch,
    # so we pass empty old/new and let the classifier return its safe
    # default (`light` for non-Python, classifier behavior for .py).
    #
    # Phase 2 remediation (Issue #1154): for fresh-file write patterns
    # (cat redirect, heredoc redirect, etc.) we additionally try to extract
    # the heredoc body and run the AST classifier against it. The body IS
    # the new file's content, so a `class X: pass` body correctly upgrades
    # to ``tier=full`` (new class) — matching the spec for the chained
    # heredoc form `OUT=foo.py; cat > "$OUT" << EOF\nclass X: pass\nEOF`.
    #
    # Constraints honored:
    # - The detector (``detect_bash_code_file_write``) already strips heredoc
    #   bodies before scanning patterns 1/2/3/6/7/8 (Issue #1153), so this
    #   re-classify ONLY fires AFTER a code-file target has been detected
    #   from the SHELL syntax (not the body). AC2 is preserved: a
    #   `gh issue create --body-file - <<HD ... HD` payload returns
    #   ``target=""`` from the detector and never reaches this branch.
    # - On any extraction or classification error we silently fall back to
    #   the original (empty-old, empty-new) tier — same as pre-remediation.
    tier, _reason = _safe_classify_edit_tier(target, "", "")
    body_classified = False
    if (
        _extract_heredoc_body_fn is not None
        and _is_fresh_file_write_pattern_fn is not None
        and _is_fresh_file_write_pattern_fn(pattern)
    ):
        try:
            body = _extract_heredoc_body_fn(command)
        except Exception:
            body = ""
        if body:
            body_tier, _body_reason = _safe_classify_edit_tier(target, "", body)
            # Only ELEVATE the tier — never weaken. fix < light < full.
            _ranks = {"fix": 0, "light": 1, "full": 2}
            if _ranks.get(body_tier, 0) > _ranks.get(tier, 0):
                tier = body_tier
                body_classified = True
    # For Bash patterns we conservatively floor at `light` — a one-shot
    # `sed -i X.py` or `cat > X.py` is not a "fix-tier" edit. Body-classified
    # decisions are already >= light (we only elevate), so this floor is a
    # no-op for them; the explicit check keeps the invariant readable.
    if tier == "fix":
        tier = "light"
    # body_classified is captured for future telemetry / debug-log integration
    # (Phase 3 — Issue #1155). Not yet wired into the directive text.
    _ = body_classified

    if tier == "light":
        flag = "--light "
    elif tier == "full":
        flag = ""
    else:
        flag = "--light "
        tier = "light"
    directive = (
        f"Run /implement {flag}\"<brief description of change to {basename}>\" "
        f"instead of Bash-writing to code files (pattern: {pattern}). "
        f"This path is advisory and does not block, so it needs no bypass; the "
        f"one-shot {WRITE_GATE_BYPASS_SENTINEL} sentinel applies to the "
        f"Write/Edit gate only and is NOT consumed here."
    )
    return (True, tier, directive, target)


def _strip_quoted_segments(command: str) -> str:
    """Remove single- and double-quoted segments from a command string (Issue #590).

    This prevents false-positive env-var spoofing detection when a protected
    variable name appears inside a quoted argument (e.g., a --body flag to gh).

    Single-quoted strings in bash have no escape sequences, so the pattern is
    simple: everything between the first ``'`` and the next ``'``.

    Double-quoted strings support backslash escaping, so ``\\"`` inside a
    double-quoted segment does NOT end the string.

    On any regex error the original command is returned unchanged (fail-open for
    the stripping step, but the caller still applies the detection patterns to
    the original on error).

    Args:
        command: The raw Bash command string.

    Returns:
        Command with quoted segments replaced by empty strings.
    """
    import re

    try:
        # Remove single-quoted segments first (no escape sequences in single quotes)
        result = re.sub(r"'[^']*'", "", command)
        # Remove double-quoted segments (backslash can escape a quote inside)
        result = re.sub(r'"(?:[^"\\]|\\.)*"', "", result)
        return result
    except re.error:
        return command


def _strip_heredoc_content(command: str) -> str:
    """Remove heredoc content from a command string.

    Thin wrapper around the shared ``heredoc_utils.strip_heredoc_content``
    helper. Kept under the original private name so existing internal call
    sites (``_detect_env_spoofing`` and ``_detect_gh_issue_create``) do not
    need to be touched as part of the Phase 2 extraction.

    Args:
        command: The raw Bash command string.

    Returns:
        Command with heredoc body content replaced by empty strings. Falls
        back to the input unchanged when the shared module failed to load
        (no-op strip) to preserve the existing scan behavior.

    Issue: #1153
    """
    if _strip_heredoc_fn is None:
        return command
    try:
        return _strip_heredoc_fn(command)
    except Exception:
        return command


def _is_protected_env_var(var_name: str) -> bool:
    """Check if a variable name is protected by individual listing or prefix matching.

    Args:
        var_name: The environment variable name to check.

    Returns:
        True if the variable is protected and should not be set inline.
    """
    # Check individual protected vars first
    if var_name in PROTECTED_ENV_VARS:
        return True

    # Check prefix-based protection (Issue #606)
    if var_name in PROTECTED_ENV_PREFIX_EXCEPTIONS:
        return False
    for prefix in PROTECTED_ENV_PREFIXES:
        if var_name.startswith(prefix):
            return True

    return False


def _detect_env_spoofing(command: str) -> "Optional[str]":
    """Detect inline environment variable spoofing in Bash commands (Issue #557, #606).

    Checks for patterns like:
    - CLAUDE_AGENT_NAME=implementer python3 ...
    - export CLAUDE_AGENT_NAME=implementer
    - env CLAUDE_AGENT_NAME=implementer ...
    - CLAUDE_ANY_NEW_VAR=value cmd (prefix-based, Issue #606)

    Checks variables in PROTECTED_ENV_VARS (individual) and any variable
    matching PROTECTED_ENV_PREFIXES. Legitimate env usage
    (e.g., PATH=foo, HOME=/tmp) is not blocked.

    Args:
        command: The Bash command string to inspect.

    Returns:
        Block reason string if spoofing detected, None if clean.
    """
    import re

    # Issue #1032: Strip heredoc content before quoted segments so that
    # protected env-var names appearing inside heredoc bodies (e.g. when
    # writing a Markdown file that documents PIPELINE_STATE_FILE) do not
    # produce false-positive blocks. Mirrors the pattern used by
    # _detect_gh_issue_create at lines 2172-2173.
    stripped = _strip_heredoc_content(command)
    stripped = _strip_quoted_segments(stripped)

    # --- Pass 1: Check individual PROTECTED_ENV_VARS (exact match) ---
    for var in PROTECTED_ENV_VARS:
        # Pattern 1: VAR=value command (inline prefix)
        pattern1 = (
            r'(?:^|[;&|]\s*)' + re.escape(var)
            + r"""=['""]?[^\s'"";|&]*['""]?\s+\S"""
        )
        if re.search(pattern1, stripped):
            return (
                f"BLOCKED: Inline env var spoofing detected — '{var}' cannot be "
                f"set inline in Bash commands. Protected environment variables "
                f"are managed by the pipeline. (Issue #557) "
                f"REQUIRED NEXT ACTION: Remove the environment variable override "
                f"from your command. Do NOT attempt to set protected variables "
                f"via alternative methods."
            )

        # Pattern 2: export VAR=value
        pattern2 = r'\bexport\s+' + re.escape(var) + r'\s*='
        if re.search(pattern2, stripped):
            return (
                f"BLOCKED: Export of protected env var '{var}' detected. "
                f"Protected environment variables cannot be overridden via "
                f"Bash export. (Issue #557) "
                f"REQUIRED NEXT ACTION: Remove the environment variable override "
                f"from your command. Do NOT attempt to set protected variables "
                f"via alternative methods."
            )

        # Pattern 3: env [-flags] [--] VAR=value command
        pattern3 = r'\benv\s+(?:(?:-[a-zA-Z]+\s+(?:\S+\s+)?|--\s+)*)(?:[^\s=]+=\S+\s+)*' + re.escape(var) + r'\s*='
        if re.search(pattern3, stripped):
            return (
                f"BLOCKED: Env command spoofing detected — '{var}' cannot be "
                f"set via the env command. Protected environment variables "
                f"are managed by the pipeline. (Issue #557) "
                f"REQUIRED NEXT ACTION: Remove the environment variable override "
                f"from your command. Do NOT attempt to set protected variables "
                f"via alternative methods."
            )

    # --- Pass 2: Prefix-based detection (Issue #606) ---
    # Find all VAR=value assignments in the stripped command
    # Pattern: word characters (var name) followed by = at assignment positions
    # Inline: VAR=value cmd  (start of command or after ; & |)
    inline_vars = re.findall(r'(?:^|[;&|]\s*)([A-Z_][A-Z0-9_]*)=', stripped, re.MULTILINE)
    # Export: export VAR=value
    export_vars = re.findall(r'\bexport\s+([A-Z_][A-Z0-9_]*)\s*=', stripped, re.MULTILINE)
    # Env command: env [-flags...] [--] VAR=value
    # Handles: env VAR=val, env -i VAR=val, env -u NAME VAR=val, env -- VAR=val
    env_cmd_vars = re.findall(
        r'\benv\s+(?:(?:-[a-zA-Z]+\s+(?:\S+\s+)?|--\s+)*)(?:[^\s=]+=\S+\s+)*([A-Z_][A-Z0-9_]*)=',
        stripped,
        re.MULTILINE,
    )

    all_assigned_vars = set(inline_vars + export_vars + env_cmd_vars)
    for var in all_assigned_vars:
        # Skip vars already checked in Pass 1
        if var in PROTECTED_ENV_VARS:
            continue
        if _is_protected_env_var(var):
            # Determine which pattern matched to give a specific message
            inline_pat = (
                r'(?:^|[;&|]\s*)' + re.escape(var)
                + r"""=['""]?[^\s'"";|&]*['""]?\s+\S"""
            )
            export_pat = r'\bexport\s+' + re.escape(var) + r'\s*='
            env_pat = r'\benv\s+(?:(?:-[a-zA-Z]+\s+(?:\S+\s+)?|--\s+)*)(?:[^\s=]+=\S+\s+)*' + re.escape(var) + r'\s*='

            if re.search(export_pat, stripped):
                return (
                    f"BLOCKED: Export of protected env var '{var}' detected. "
                    f"Variables matching protected prefix cannot be overridden "
                    f"via Bash export. (Issue #606) "
                    f"REQUIRED NEXT ACTION: Remove the environment variable override "
                    f"from your command. Do NOT attempt to set protected variables "
                    f"via alternative methods."
                )
            if re.search(env_pat, stripped):
                return (
                    f"BLOCKED: Env command spoofing detected — '{var}' cannot be "
                    f"set via the env command. Variables matching protected prefix "
                    f"are managed by the pipeline. (Issue #606) "
                    f"REQUIRED NEXT ACTION: Remove the environment variable override "
                    f"from your command. Do NOT attempt to set protected variables "
                    f"via alternative methods."
                )
            if re.search(inline_pat, stripped):
                return (
                    f"BLOCKED: Inline env var spoofing detected — '{var}' cannot be "
                    f"set inline in Bash commands. Variables matching protected prefix "
                    f"are managed by the pipeline. (Issue #606) "
                    f"REQUIRED NEXT ACTION: Remove the environment variable override "
                    f"from your command. Do NOT attempt to set protected variables "
                    f"via alternative methods."
                )
            # Fallback: var was found in assignment but specific pattern didn't re-match
            # (shouldn't happen, but fail safe)
            return (
                f"BLOCKED: Protected env var '{var}' assignment detected. "
                f"Variables matching protected prefix cannot be set in "
                f"Bash commands. (Issue #606) "
                f"REQUIRED NEXT ACTION: Remove the environment variable override "
                f"from your command. Do NOT attempt to set protected variables "
                f"via alternative methods."
            )

    # Pattern 4: bash -c / sh -c subshell containing protected var assignments
    # Catches: bash -c 'CLAUDE_AGENT_NAME=x python3 ...'
    #          sh -c "export PIPELINE_STATE_FILE=/tmp/fake.json; ..."
    for subshell_match in re.finditer(r'(?:ba)?sh\s+-c\s+([\x27"])(.*?)\1', command, re.DOTALL):
        inner_cmd = subshell_match.group(2)
        # Recursively check the inner command for env spoofing
        inner_result = _detect_env_spoofing(inner_cmd)
        if inner_result:
            return (
                f"BLOCKED: Subshell env spoofing detected — protected environment "
                f"variable assignment found inside bash -c / sh -c subshell. "
                f"Inner violation: {inner_result} "
                f"REQUIRED NEXT ACTION: Remove the environment variable override "
                f"from your command. Do NOT attempt to set protected variables "
                f"via alternative methods."
            )

    return None


def _track_spoofing_escalation(
    session_id: str,
    *,
    tracker_path: "Optional[str]" = None,
) -> bool:
    """Track spoofing attempts per session and detect escalation (Issue #606).

    Uses a file-based tracker to persist attempt counts across hook invocations
    (each hook invocation is a separate process). Returns True when 2+ attempts
    have occurred in the same session, indicating escalation.

    Args:
        session_id: The current session identifier.
        tracker_path: Optional override for the tracker file path (for testing).

    Returns:
        True if this is the 2nd or later attempt in the same session (escalation).
    """
    import json
    import tempfile
    from datetime import datetime

    if tracker_path is None:
        log_dir = Path(os.environ.get("HOME", "/tmp")) / ".claude" / "logs"
        tracker_file = log_dir / "spoofing_attempts.json"
    else:
        tracker_file = Path(tracker_path)

    try:
        tracker_file.parent.mkdir(parents=True, exist_ok=True)

        # Read existing tracker data
        data: "dict[str, list[str]]" = {}
        if tracker_file.exists():
            try:
                data = json.loads(tracker_file.read_text())
            except (json.JSONDecodeError, OSError):
                data = {}

        # Record this attempt
        if session_id not in data:
            data[session_id] = []
        data[session_id].append(datetime.now().isoformat())

        is_escalation = len(data[session_id]) >= 2

        # Atomic write: write to tmp file, then rename
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=str(tracker_file.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w") as f:
                json.dump(data, f)
            os.replace(tmp_path, str(tracker_file))
        except OSError:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            # Still return the escalation result based on in-memory data
            pass

        return is_escalation
    except Exception:
        # Never block on tracker failure — fail open for tracking,
        # the spoofing block itself is already applied
        return False


# ---------------------------------------------------------------------------
# Module-level body/message flag helpers (hoisted from
# _contains_gh_issue_create_bypass per Issue #1215 so both the bypass detector
# AND the direct detector can use them).
#
# BODY_FLAGS lists argument flags whose VALUES carry user-authored prose
# (commit messages, issue/PR bodies, titles). False positives lived in these
# values pre-#1203:
#   - --body / --title / --body-file are gh's body-content flags
#   - -m / --message / -F / --file are git commit's message flags
# A single combined set is harmless: stripping a flag the current tool does
# not recognize is a no-op (the loop just skips the next token), and the
# union covers every body/message false-positive surface.
# ---------------------------------------------------------------------------

GH_ISSUE_BODY_FLAGS: "tuple[str, ...]" = (
    # gh issue / pr family
    "--body",
    "--title",
    "--body-file",
    # gh issue close / comment family (Issue #1216)
    "-c",
    "--comment",
    # git commit family (Issue #1215)
    "-m",
    "--message",
    "-F",
    "--file",
)


def _strip_body_arg_values(cmd: str) -> "tuple[str, list[str]]":
    """Strip body/title/message argument VALUES from a tokenized command.

    Tokenize via shlex.split(posix=True). Drop VALUE tokens that immediately
    follow a body flag (separate-value form), and drop ``--flag=VALUE`` /
    ``--body=VALUE`` attached-value tokens entirely. Rejoin remaining tokens
    with single spaces. The resulting string preserves command structure
    (the leading verb, the flags, the rest of argv) but no longer contains
    the body's prose content where false-positive substring matches would
    live.

    The flag set is the union of gh-family flags
    (``--body``/``--title``/``--body-file``) and git-commit-family flags
    (``-m``/``--message``/``-F``/``--file``). Applying a foreign-flag strip
    is harmless because shlex tokenization only treats a token as a flag
    when it appears in flag position; unrecognized flags simply pass
    through as normal tokens.

    Args:
        cmd: The raw Bash command string (will be tokenized).

    Returns:
        Tuple ``(stripped_command, dropped_values)`` where dropped_values
        are the raw VALUE tokens that were removed. Callers may inspect
        dropped_values for embedded bypass patterns (Tier-B scan in
        ``_contains_gh_issue_create_bypass``).

    Raises:
        ValueError: When shlex.split fails (malformed shell, unterminated
            quotes). Callers must catch and fall back to raw-regex behavior
            to preserve fail-closed blocking on garbled input.
    """
    toks = shlex.split(cmd, posix=True)  # may raise ValueError; let caller catch
    out: list[str] = []
    dropped: list[str] = []
    i = 0
    while i < len(toks):
        t = toks[i]
        if t in GH_ISSUE_BODY_FLAGS:
            # drop flag AND its value; capture the value for embedded-bypass scan
            if i + 1 < len(toks):
                dropped.append(toks[i + 1])
            i += 2
            continue
        attached_flag = next(
            (flag for flag in GH_ISSUE_BODY_FLAGS if t.startswith(flag + "=")),
            None,
        )
        if attached_flag is not None:
            # drop --body=VALUE / --message=VALUE attached form;
            # capture VALUE portion (everything after the '=') for the scan
            dropped.append(t[len(attached_flag) + 1:])
            i += 1
            continue
        out.append(t)
        i += 1
    return " ".join(out), dropped


# Drain-pending commit-gate (Issue: drain-queue durability plan, round-2 PROCEED).
# Recognized commit-message flag set, mirrored from git-commit semantics.
_GIT_COMMIT_MESSAGE_FLAGS: "frozenset[str]" = frozenset({
    "-m", "--message", "-F", "--file",
})


def _extract_commit_message_payload(command: str) -> Optional[str]:
    """Extract the literal commit-message payload from a ``git commit`` invocation.

    Drain-pending gate companion to ``_strip_body_arg_values`` — instead of
    stripping the body, this returns it so the gate can scan for
    ``Closes #N`` / ``Fixes #N`` references.

    Returns ``None`` when the payload is uninspectable (the gate then
    fails CLOSED with an explicit reason):

    * No ``-m`` / ``--message`` / ``-F`` / ``--file`` flag → editor mode.
    * ``-F -`` (stdin) — payload not in argv.
    * ``-F <(…)`` (process substitution) — pseudo-device path.
    * ``-F /path/that/does/not/exist`` — unreadable.
    * Heredoc body containing unresolved ``$`` / backtick — shell expansion
      defeats the literal-scan invariant.
    * Heredoc with no ``-m``/``-F`` — payload is bash-expanded into argv
      AFTER shell parsing; the hook only sees the pre-expansion raw command,
      so falling back to the heredoc body is the safe extraction.

    Args:
        command: The raw Bash command string.

    Returns:
        The literal payload string (one or more messages concatenated by
        ``\\n``), or ``None`` when the payload cannot be inspected.
    """
    if not command:
        return None

    # Heredoc form (``git commit -m "$(cat <<'EOF' ... EOF)"`` or
    # ``git commit -F - <<EOF ... EOF``). The hook receives the raw command
    # string, NOT shell-expanded argv. Extract the heredoc body via the
    # existing helper and validate for unresolved expansion.
    if "<<" in command:
        try:
            # Defensive import — edit_tier_classifier is in lib/ alongside
            # this hook's sibling lib dir.
            from edit_tier_classifier import (  # type: ignore
                extract_heredoc_body_for_redirect,
            )
        except Exception:
            return None
        body = extract_heredoc_body_for_redirect(command)
        if body:
            # Reject bodies with unresolved shell expansion — we cannot
            # safely scan for Closes #N when ``$VAR`` / `` `cmd` `` could
            # inject arbitrary text at exec time.
            if "$" in body or "`" in body:
                return None
            return body

    try:
        toks = shlex.split(command, posix=True)
    except ValueError:
        return None

    # Locate the ``git commit`` verb.
    git_idx: Optional[int] = None
    for i, token in enumerate(toks):
        if token == "git" or token.endswith("/git"):
            # Look ahead for the ``commit`` subcommand (allowing for flags
            # like ``git -C /repo commit``).
            for j in range(i + 1, len(toks)):
                if toks[j] == "commit":
                    git_idx = j
                    break
                if not toks[j].startswith("-"):
                    break
        if git_idx is not None:
            break
    if git_idx is None:
        return None

    remaining = toks[git_idx + 1:]
    messages: List[str] = []

    i = 0
    while i < len(remaining):
        t = remaining[i]

        # ``-m "msg"`` / ``--message "msg"``
        if t in ("-m", "--message"):
            if i + 1 >= len(remaining):
                # Trailing flag with no value — uninspectable.
                return None
            messages.append(remaining[i + 1])
            i += 2
            continue

        # ``--message=msg``
        if t.startswith("--message="):
            messages.append(t[len("--message="):])
            i += 1
            continue
        if t.startswith("-m="):
            # git accepts ``-m=msg`` rarely; tolerate for robustness.
            messages.append(t[len("-m="):])
            i += 1
            continue

        # ``-F path`` / ``--file path`` / ``--file=path`` / ``-F=path``
        flag_path: Optional[str] = None
        if t in ("-F", "--file") and i + 1 < len(remaining):
            flag_path = remaining[i + 1]
            i += 2
        elif t.startswith("--file="):
            flag_path = t[len("--file="):]
            i += 1
        elif t.startswith("-F="):
            flag_path = t[len("-F="):]
            i += 1
        else:
            i += 1
            continue

        if flag_path is None:
            continue
        # stdin or process-substitution → uninspectable.
        if flag_path == "-":
            return None
        if flag_path.startswith("<(") or flag_path.startswith(">(") or "<(" in flag_path:
            return None
        # File must exist and be readable.
        try:
            from pathlib import Path as _Path
            p = _Path(flag_path)
            if not p.exists() or not p.is_file():
                return None
            file_text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        # Reject embedded unresolved shell expansion in the file payload.
        if "$" in file_text or "`" in file_text:
            return None
        messages.append(file_text)

    if not messages:
        # No -m/-F → editor mode → uninspectable.
        return None

    return "\n".join(messages)


# Drain-pending commit gate (drain-queue durability plan).
# Compiled at module load — pattern matches ``Closes #1234`` / ``Fixes #1234``
# in any case (GitHub-recognized keywords).
_DRAIN_CLOSES_RE = re.compile(r"(?:Closes|Fixes)\s+#(\d+)", re.IGNORECASE)
_DRAIN_GIT_COMMIT_RE = re.compile(r"\bgit\s+commit\b")


def _is_message_only_amend(command: str) -> bool:
    """Return True iff command is a ``git commit --amend`` whose staged tree == HEAD.

    A message-only amend (e.g. ``git commit --amend --no-edit`` or an amend that
    only rewords the commit message) changes NO tracked content — the staged tree
    is identical to HEAD. Such an amend does not warrant re-firing the agent
    completeness gate (Issue #1382): the pipeline agents already validated the
    content on the original commit, and rewording the message is a no-op for the
    purposes of that gate.

    Fail-open (returns False) on any error, malformed command, missing HEAD
    (initial commit), or non-amend command. Only returns True on a confident
    no-op/message-only amend, so the caller keeps enforcing in every ambiguous
    case. A content-changing amend (staged tree differs from HEAD) returns False
    and remains gated.

    Args:
        command: The raw Bash command string to inspect.

    Returns:
        True only when the command is a confirmed message-only ``git commit
        --amend`` whose staged tree equals HEAD; False otherwise.
    """
    try:
        try:
            tokens = shlex.split(command, posix=True)
        except ValueError:
            return False
        if "--amend" not in tokens:
            return False
        head = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            capture_output=True,
            timeout=5,
        )
        if head.returncode != 0:
            return False  # no HEAD -> initial commit, not an amend
        diff = subprocess.run(
            ["git", "diff-index", "--quiet", "--cached", "HEAD", "--"],
            capture_output=True,
            timeout=5,
        )
        return diff.returncode == 0  # exit 0 = staged tree == HEAD = message-only
    except Exception:
        return False


def _check_drain_pending_commit_gate(
    tool_input: Dict[str, Any],
) -> Optional[Tuple[str, str]]:
    """Return ``(decision, reason)`` when a ``git commit`` must be blocked.

    Fires when ``.claude/local/drain_pending.json`` exists with a non-empty
    ``issues`` list AND the inspected Bash command matches ``git commit``.

    Behavior matrix:

    * No marker file (or marker has empty ``issues``)  → ``None`` (no enforcement).
    * Marker present + non-``git commit`` Bash         → ``None`` (gate scope).
    * Marker present + ``git commit -m "Closes #N"``
      where N ∈ marker.issues                          → ``None`` (allow).
    * Marker present + ``git commit -m "freelance"``   → ``("deny", reason)``.
    * Marker present + uninspectable payload (editor,
      stdin, proc-sub, missing file, shell expansion) → ``("deny", reason)``.

    The gate NEVER consults marker TTL — long ``/implement`` runs remain
    covered. TTL is for SessionStart cleanup only.

    Args:
        tool_input: The Bash tool's input dict (expects ``command`` key).

    Returns:
        ``None`` when the gate does not apply (allow proceeds to other
        layers). ``("deny", reason)`` when the gate fires.
    """
    command = tool_input.get("command", "")
    if not command or not _DRAIN_GIT_COMMIT_RE.search(command):
        return None

    # Defensive import — never crash the entire hook stack because the
    # marker library is unavailable (e.g. mid-deploy).
    try:
        # Add lib dir to sys.path so the import works regardless of how
        # the hook was invoked (direct, via importlib, etc.).
        _lib_dir = Path(__file__).resolve().parent.parent / "lib"
        if str(_lib_dir) not in sys.path:
            sys.path.insert(0, str(_lib_dir))
        from drain_pending import DrainPendingMarker  # type: ignore
    except Exception:
        return None

    try:
        marker = DrainPendingMarker.read()
    except Exception:
        # Read errors fail-OPEN — never block a commit because the marker
        # is unreadable. (read() already tolerates malformed JSON.)
        return None

    if marker is None or not marker.issues:
        return None

    # Marker present → enforce.
    payload = _extract_commit_message_payload(command)
    if payload is None:
        reason = (
            f"drain marker active (issues={list(marker.issues)}) — commit "
            f"payload uninspectable (no -m/-F, stdin, process substitution, "
            f"missing file, or unresolved shell expansion). "
            f"Use 'git commit -m \"... Closes #{marker.issues[0]}\"' with a "
            f"literal message that closes a cluster issue."
        )
        return ("deny", reason)

    refs = {int(m.group(1)) for m in _DRAIN_CLOSES_RE.finditer(payload)}
    if not (refs & set(marker.issues)):
        got = sorted(refs) if refs else "none"
        reason = (
            f"drain marker active (issues={list(marker.issues)}) — commit "
            f"message must include 'Closes #N' (or 'Fixes #N') for at least "
            f"one cluster issue. Got refs: {got}. "
            f"Add 'Closes #{marker.issues[0]}' to the commit body."
        )
        return ("deny", reason)

    return None


# Shell wrappers whose -c argument carries a sub-command. When the leading
# verb (argv[0]) is one of these AND argv[1] == "-c", the substring scan
# inside argv[2] is handled by _contains_gh_issue_create_bypass — do not
# double-flag from _detect_gh_issue_create's direct-match argv check.
#
# Issue #1619: this set is NOT the place to add `env`, `nice`, `timeout`,
# `command`, `stdbuf`, `nohup`, `xargs`, `setsid`, `taskset`, `doas` or
# `sudo`. Those are command *runners*, and enumerating runners is an
# allowlist against an open set — the next one ships tomorrow. See
# _COMMAND_ARG_CONSUMERS below for the polarity the gate uses instead.
_SHELL_WRAPPERS: "frozenset[str]" = frozenset({
    "sh", "bash", "zsh", "dash", "ksh",
    "/bin/sh", "/bin/bash", "/bin/zsh", "/bin/dash", "/bin/ksh",
    "/usr/bin/sh", "/usr/bin/bash", "/usr/bin/zsh",
    "/usr/local/bin/sh", "/usr/local/bin/bash", "/usr/local/bin/zsh",
})


# Verbs that consume bare positional words as DATA rather than executing them
# (Issue #1619).
#
# THE POLARITY IS THE POINT. The gate no longer asks "is the leading token a
# known wrapper?" — that question has an open, attacker-controlled answer set,
# and `stash@{0}` holds a prior enumeration attempt for a sibling gate marked
# FAIL-Critical with 65 bypasses remaining. It asks the inverse: "having found
# the token triple `gh issue create` past the leading token, is the leading
# token one that provably treats bare words as data?"
#
# An omission from THIS set produces a false REFUSAL — loud, attributable, and
# fixable by adding the verb. An omission from a wrapper deny-list produces a
# silent PERMIT. Only the first failure mode is acceptable in a guard, so the
# only enumeration left in this gate sits on the permit side.
#
# Membership rule: a verb belongs here only if its bare positional arguments
# are patterns, paths, or prose — never a command it will execute. `xargs`,
# `find` (`-exec`), `ssh`, `sudo`, `watch`, `parallel`, `make` and `docker` all
# DO execute their arguments and are deliberately absent.
#
# The safety property — "an omission over-blocks loudly" — holds ONLY while
# every member genuinely satisfies the membership rule. A single over-broad
# member converts this permit set back into a deny list with extra steps, and
# does so invisibly. `git` is the one member that needs a qualifier; see
# `_GIT_SUBCOMMANDS_THAT_EXECUTE_ARGUMENTS` and `_verb_consumes_bare_args`.
# Membership here is NECESSARY but not SUFFICIENT: always ask through
# `_verb_consumes_bare_args`, never by testing this set directly.
_COMMAND_ARG_CONSUMERS: "frozenset[str]" = frozenset({
    # Text emitters and matchers — args are strings/patterns/paths.
    "echo", "printf", "grep", "egrep", "fgrep", "rg", "ag", "ack",
    "sed", "awk", "jq", "tr", "cut", "sort", "uniq", "wc", "diff",
    # File/path handlers — args are paths.
    "cat", "head", "tail", "less", "more", "ls", "rm", "cp", "mv",
    "touch", "stat", "file", "readlink", "mkdir", "basename", "dirname",
    # Version control — bare positionals are USUALLY subcommands, refs, paths
    # and (unquoted) commit prose. Locks the Issue #1215 false positive:
    # `git commit -m fix gh issue create gate` survives _strip_body_arg_values
    # as three bare tokens.
    #
    # CONDITIONAL. A previous revision of this comment claimed `git` cannot
    # execute a bare positional. That is FALSE, and the false claim is how the
    # over-broad entry survived a review: `git bisect run <cmd> [args…]`,
    # `git submodule foreach <cmd> [args…]`, `git rebase --exec <cmd>` and
    # `git difftool -x <cmd>` all execute a bare positional, and three of the
    # four were measured PERMITTING `gh issue create` before this qualifier
    # existed. Consult `_verb_consumes_bare_args`, which excludes those
    # subcommands, rather than this set alone.
    "git",
})


# Subcommands that make `git` a command RUNNER rather than an arg consumer
# (Issue #1619 remediation).
#
# NOTE THE POLARITY DELIBERATELY: this inner set IS a deny list, and that is
# not a relapse into wrapper enumeration. It is scoped to ONE verb whose
# subcommand vocabulary is closed, documented and versioned by an upstream
# project — not to the open, attacker-controlled set of shell wrappers that
# `_COMMAND_ARG_CONSUMERS` exists to avoid enumerating. Do NOT "fix" this into
# a permit list of safe git subcommands: git ships ~150 of them, that list is
# the open set, and inverting the polarity here would put the loud failure on
# the wrong side.
_GIT_SUBCOMMANDS_THAT_EXECUTE_ARGUMENTS: "frozenset[str]" = frozenset({
    "bisect",        # git bisect run <cmd> [args…]
    "submodule",     # git submodule foreach <cmd> [args…]
    "filter-branch",  # --tree-filter / --index-filter / --msg-filter <cmd>
    "difftool",      # git difftool -x <cmd>
    "mergetool",     # git mergetool --tool=<cmd> / configured cmd
    "rebase",        # git rebase --exec <cmd>
})


def _verb_consumes_bare_args(argv: "list[str]", idx: "int") -> bool:
    """Does ``argv[idx]`` treat its bare positional words as DATA, not commands?

    The single sanctioned way to ask the permit-side question. Membership in
    :data:`_COMMAND_ARG_CONSUMERS` is necessary but not sufficient — ``git`` is
    a consumer for ``commit``/``log``/``grep`` but a command RUNNER for
    ``bisect run``/``submodule foreach``/``rebase --exec``/``difftool -x``.

    For ``git`` the runner subcommand is searched across the ENTIRE remainder
    of ``argv``, never at the fixed offset ``argv[idx + 1]``: git's global
    options (``-C``, ``--no-pager``, ``--git-dir=``, ``-c k=v``) sit between
    the verb and its subcommand, and a fixed-offset read permits every runner
    form that carries one. See the inline note at the ``git`` branch for the
    measured over-block cost of scanning wide.

    Args:
        argv: Tokenized statement (body-argument values already stripped).
        idx: Index of the verb token to classify.

    Returns:
        True when the verb provably consumes bare words as data, so reaching
        ``gh issue create`` through it is prose rather than execution.
    """
    if idx >= len(argv):
        return False
    verb = _token_basename(argv[idx])
    if verb not in _COMMAND_ARG_CONSUMERS:
        return False
    if verb == "git":
        # Scan the WHOLE remainder, not `argv[idx + 1]`. Reading the subcommand
        # at a fixed offset assumes it sits immediately after `git`, and git's
        # global options sit BETWEEN the two: `-C <path>`, `--no-pager`,
        # `--git-dir=`, `--work-tree=`, `-c k=v`. With one present,
        # `argv[idx + 1]` is the option, the membership test misses, and
        # `git -C . bisect run gh issue create` PERMITS. All four of
        # `-C` / `--no-pager` / `--git-dir=` / `difftool -x` were measured
        # reopened by exactly this. A global option before the subcommand is
        # the normal shape here, not an exotic one: 2,693 of 19,795 bare-`git`
        # commands in 167,963 logged commands — 14% — have one.
        #
        # (`git -c k=v bisect run …` denied even at the fixed offset, but only
        # incidentally: `_strip_body_arg_values` ate `-c`'s value and left
        # `bisect` back at `argv[idx + 1]`. Luck, not logic. Do not read that
        # as evidence the offset works.)
        #
        # The alternative — walk the prefix, skip `-`-prefixed tokens, and also
        # skip the VALUE of the non-`=` value-taking globals — is more precise
        # but needs a second enumeration (`-C`, `-c`, `--git-dir`, `--work-tree`,
        # `--namespace`, `--exec-path`, `--super-prefix`, `--config-env`), and
        # that value-skip is load-bearing: omit it and `-C`'s path argument
        # becomes the apparent subcommand and this permits again. A second open
        # set is the failure mode Issue #1619 exists to remove, so the whole
        # remainder is scanned instead. The cost is bounded and measured: the
        # only statements that reach here already contain the `gh issue create`
        # triple, and across 167,963 logged commands the tokens below appear in
        # such a statement 28 times — every one a genuine
        # `git bisect run` / `submodule foreach` / `difftool -x` invocation of
        # `gh issue create`, i.e. ZERO legitimate commands over-blocked. The
        # residual cost is unquoted commit prose that names a runner
        # subcommand (`git commit -m fix rebase gh issue create flow`), which
        # over-blocks LOUDLY — the direction this gate deliberately prefers.
        if any(
            _token_basename(token) in _GIT_SUBCOMMANDS_THAT_EXECUTE_ARGUMENTS
            for token in argv[idx + 1:]
        ):
            return False
    return True


# Verbs whose ARGUMENT STRING is command text the shell will execute, so the
# effective verb cannot be resolved by tokenization (Issue #1619). Scanned as a
# substring rather than as a token triple, and scoped to arguments that
# actually contain the gh-issue-create pattern so that `eval "$(ssh-agent -s)"`
# and friends are not swept up — a permanently-red check trains everyone to
# ignore the whole class.
_INDIRECT_COMMAND_EXECUTORS: "frozenset[str]" = frozenset({
    "eval", "source", ".",
})


_STATEMENT_SEPARATORS: "frozenset[str]" = frozenset({"|", ";", "&&", "||", "&", "\n"})


def _split_statements(command: str) -> "list[str]":
    """Split a Bash command string into top-level statement strings.

    Walks the source command character-by-character respecting single and
    double quotes (so a separator inside a quoted body is NOT a split point).
    Recognized top-level separators: ``;``, ``&&``, ``||``, ``|``, ``&``,
    and newline. The resulting statement strings preserve their interior
    structure (quoting, flags, values) for the caller to feed to shlex.

    Args:
        command: The raw Bash command string.

    Returns:
        List of statement substrings with surrounding whitespace stripped.
        Empty statements are dropped.
    """
    out: "list[str]" = []
    buf: "list[str]" = []
    i = 0
    n = len(command)
    in_single = False
    in_double = False
    while i < n:
        c = command[i]
        # Quote handling: single quotes are literal (no escapes); double
        # quotes honor backslash escapes for the closing quote.
        if c == "'" and not in_double:
            in_single = not in_single
            buf.append(c)
            i += 1
            continue
        if c == '"' and not in_single:
            in_double = not in_double
            buf.append(c)
            i += 1
            continue
        if in_single or in_double:
            # Inside a quoted region, preserve everything verbatim
            # (including backslash-escapes inside double quotes).
            if c == "\\" and in_double and i + 1 < n:
                buf.append(c)
                buf.append(command[i + 1])
                i += 2
                continue
            buf.append(c)
            i += 1
            continue
        # Two-character separators take precedence over single-char ones.
        if i + 1 < n and command[i:i + 2] in ("&&", "||"):
            stmt = "".join(buf).strip()
            if stmt:
                out.append(stmt)
            buf = []
            i += 2
            continue
        if c in (";", "|", "&", "\n"):
            stmt = "".join(buf).strip()
            if stmt:
                out.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


def _strip_shell_comment(statement: str) -> str:
    """Truncate a raw statement at its first UNQUOTED word-initial ``#``.

    This must run on RAW statement text, before any tokenization. A previous
    revision ran the equivalent predicate on post-``shlex`` tokens and
    justified it with the claim that a quoted ``"# foo"`` "arrives as a token
    containing whitespace". That claim is FALSE for quoted markers that
    contain no whitespace, and the false claim is how the defect survived
    review: ``shlex.split("xargs -I '#' gh issue create", posix=True)`` yields
    ``['xargs', '-I', '#', 'gh', 'issue', 'create']``, the bare ``#`` read as a
    comment, the statement truncated to ``['xargs', '-I']``, and the
    invocation behind it was PERMITTED. Bash does not treat a quoted ``'#'``
    as a comment, so ``xargs -I '#' gh issue create`` really executes — and
    ``xargs`` is deliberately absent from :data:`_COMMAND_ARG_CONSUMERS`
    precisely so it would refuse.

    Scanning the raw text is what the shell itself does: a ``#`` begins a
    comment only when it is unquoted, unescaped, and starts a word (preceded
    by start-of-string or whitespace).

    Args:
        statement: A raw statement string from :func:`_split_statements`.

    Returns:
        ``statement`` truncated at the comment marker, or unchanged when it
        contains no comment. Never raises.
    """
    quote: "Optional[str]" = None
    i = 0
    n = len(statement)
    while i < n:
        ch = statement[i]
        if quote is None:
            if ch == "\\":
                # Escaped next character — `\#` is a literal hash, not a marker.
                i += 2
                continue
            if ch in ("'", '"'):
                quote = ch
                i += 1
                continue
            # `" \t\n"`, NOT `.isspace()`. Python's `str.isspace()` is
            # Unicode-aware; bash's default IFS is space, tab and newline only.
            # For U+00A0 (NBSP), U+2007, U+2028, U+000B (VT) and U+000C (FF),
            # `.isspace()` is True, so this scanner believed `#` started a word
            # and truncated the statement — while BASH saw the `#` mid-word,
            # treated it as a literal, and executed the rest of the line.
            #
            # Measured end to end with a stub `gh` on PATH (bash side and gate
            # side measured independently, with a positive control that has no
            # `#` at all and a negative control using a plain space):
            #     env -u FOO<NBSP># gh issue create --title pwned
            #         -> bash ran gh = True, gate = ALLOW  *** silent permit ***
            # and the same for U+2007, U+2028, VT and FF. One pasted character,
            # using only permitted commands.
            #
            # This is the `xargs -I '#'` class the scanner exists to close,
            # reached through a different mechanism — and it existed BECAUSE of
            # the scanner: without any comment stripping,
            # `env -u <NBSP># gh issue create` denies.
            if ch == "#" and (i == 0 or statement[i - 1] in " \t\n"):
                return statement[:i]
            i += 1
            continue
        # Inside quotes. Backslash escapes only inside double quotes; within
        # single quotes bash treats a backslash literally.
        if quote == '"' and ch == "\\":
            i += 2
            continue
        if ch == quote:
            quote = None
        i += 1
    return statement


def _token_basename(token: str) -> str:
    """Return the lower-cased basename of a shell token (Issue #1619).

    ``/usr/bin/gh`` and ``./gh`` name the same executable as ``gh``. The prior
    argv check compared ``verb.lower() == "gh"``, which an absolute path
    defeated in the same one-word way ``env`` did.

    Args:
        token: A single shlex-produced argv token.

    Returns:
        The token's basename, lower-cased. ``"gh"`` for ``"/usr/bin/GH"``.
    """
    return token.rsplit("/", 1)[-1].lower()


def _find_gh_issue_create_triple(argv: "list[str]", start: int) -> "Optional[int]":
    """Locate the argv index where the ``gh issue create`` token triple begins.

    Args:
        argv: Tokenized statement (body-argument values already stripped).
        start: Index to begin scanning from (past leading ``VAR=value``).

    Returns:
        Index of the ``gh`` token when ``gh``/``issue``/``create`` appear as
        three consecutive tokens at or after ``start``, else None.
    """
    for pos in range(start, max(start, len(argv) - 2)):
        if (
            _token_basename(argv[pos]) == "gh"
            and argv[pos + 1].lower() == "issue"
            and argv[pos + 2].lower() == "create"
        ):
            return pos
    return None


def _unresolvable_verb_reaches_gh_issue_create(
    argv: "list[str]", start: int
) -> bool:
    """Fail-closed check for statements whose effective verb cannot be resolved.

    Two shapes are covered, both of which fell through to *allow* before
    Issue #1619:

    1. **Indirect execution** — ``eval "gh issue create ..."``. The command
       text lives inside a single argument token, so no bare token triple
       exists to find. Any argument of an
       :data:`_INDIRECT_COMMAND_EXECUTORS` verb whose text contains the
       gh-issue-create pattern is refused.
    2. **Computed verb** — ``$CMD issue create ...`` / ``${GH_BIN} issue
       create ...``. The verb is a parameter expansion the hook cannot
       resolve, but the ``issue create`` operands are still visible.

    Both are deliberately scoped to statements that actually reference
    gh-issue-create. A blanket "any ``eval`` is refused" rule would make this
    gate permanently red for ``eval "$(ssh-agent -s)"`` and train everyone to
    ignore it.

    Both shapes are scoped to the VERB POSITION via
    :func:`_verb_consumes_bare_args`. Unscoped, shape 2 refused ordinary prose
    the moment it contained a variable — measured: ``grep $PAT issue create
    docs/``, ``git commit -m fix $BRANCH issue create flow``,
    ``cat notes-$USER issue create`` and ``echo `date` issue create`` were all
    REFUSED. The second is the Issue #1215 commit-prose false positive
    returning, which is the very case ``git`` was put on the permit side to
    protect. That is the cry-wolf direction and it is not acceptable here.

    Note (honest limit): a command whose text is genuinely invisible to the
    hook — base64-decoded and piped to a shell, or read from a file — is not
    covered here and cannot be. ``docs/audits/unified-pre-tool-51-check-audit.md``
    already records that inferring intent from a shell string cannot be made
    complete; this closes the resolvable-but-indirect cases only.

    Args:
        argv: Tokenized statement (body-argument values already stripped).
        start: Index to begin scanning from (past leading ``VAR=value``).

    Returns:
        True when the statement reaches ``gh issue create`` through a verb the
        hook cannot resolve.
    """
    import re

    # The leading verb provably consumes bare words as data, so neither an
    # `eval` token nor a `$VAR` token further along is in verb position —
    # both are operands. `echo eval gh issue create` is prose.
    if _verb_consumes_bare_args(argv, start):
        return False

    pattern = re.compile(r"\bgh\s+issue\s+create\b", re.IGNORECASE)

    # Shape 1: an indirect executor anywhere in the prefix, with command text
    # in a later argument.
    for pos in range(start, len(argv)):
        if _token_basename(argv[pos]) in _INDIRECT_COMMAND_EXECUTORS:
            if any(pattern.search(arg) for arg in argv[pos + 1:]):
                return True

    # Shape 2: a parameter-expanded verb immediately followed by the
    # ``issue create`` operands. The computed token must BE the effective verb:
    # either the first token, or reached only through runner prefixes
    # (`env nice $CMD issue create`). If ANY token in front of it consumes bare
    # words as data, the `$VAR` is that verb's operand and this is prose.
    for pos in range(start, max(start, len(argv) - 2)):
        token = argv[pos]
        if not ("$" in token or "`" in token):
            continue
        if not (argv[pos + 1].lower() == "issue" and argv[pos + 2].lower() == "create"):
            continue
        if any(_verb_consumes_bare_args(argv, i) for i in range(start, pos)):
            continue
        return True

    return False


def _gh_issue_create_at_command_position(
    command: str, *, heredoc_stripped: "Optional[str]" = None
) -> bool:
    """Effective-verb check: does this command actually invoke ``gh issue create``?

    Per Issue #1215, a raw substring scan of the Bash command falsely matched
    the gh-issue-create command name when it appeared in prose inside a
    ``git commit -m "..."`` body. This helper mirrors the shlex-aware
    treatment that ``_contains_gh_issue_create_bypass`` uses for backtick/$()
    detection and applies it to the direct ``gh issue create`` match path.

    Detection rules:
    1. Split the raw command into top-level statements on Bash statement
       separators (``;``, ``&&``, ``||``, ``|``, ``&``, newline) that live
       OUTSIDE quoted regions. This catches multi-statement forms like
       ``cat <<EOF ... EOF; gh issue create ...`` where the gh call is the
       leading verb of a later statement.
    2. Truncate each statement at its first unquoted word-initial ``#`` via
       :func:`_strip_shell_comment` (Issue #1619). This runs on RAW statement
       text, BEFORE any tokenization, and the ordering is load-bearing in both
       directions:

       - it must run at all, because once the gate stopped trusting argv[0]
         the prose in ``# ...can the coordinator call gh issue create`` read
         as an invocation (15 such comment lines measured in this repo's own
         activity log);
       - it must run before tokenization, because
         :func:`_strip_body_arg_values` rejoins shlex tokens with spaces and
         so destroys the quoting that separates a comment marker from a
         quoted ``'#'`` literal. A post-tokenization predicate PERMITTED
         ``xargs -I '#' gh issue create``. See :func:`_strip_shell_comment`.

       A statement that is empty after truncation is skipped.
    3. Strip body/message argument VALUES via ``_strip_body_arg_values`` so
       prose inside ``-m``/``--body``/``-F`` cannot match.
    4. Tokenize via shlex.split(posix=True). Skip leading env-var assignments
       like ``FOO=bar``.
    5. If the verb is a shell wrapper (``sh``, ``bash``, ``/bin/sh``...) with
       ``-c`` followed by a sub-command, leave detection to the bypass
       detector — skip this statement here. (The bypass detector already
       catches this pattern with shlex-stripping.)
    6. Resolve the EFFECTIVE VERB rather than trusting argv[0] (Issue #1619).
       Locate the ``gh``/``issue``/``create`` token triple anywhere in the
       statement, basename-aware so ``/usr/bin/gh`` counts:

       - triple at the first non-assignment token → direct invocation, True
         (the pre-#1619 behaviour, unchanged);
       - triple reached THROUGH a leading token → True, **unless**
         :func:`_verb_consumes_bare_args` says that token provably treats its
         bare positional words as DATA, or the statement is heredoc body
         prose. This is what refuses ``env``/``nice``/``timeout``/``xargs``/
         ``doas`` and every future runner without naming any of them;
       - no triple → :func:`_unresolvable_verb_reaches_gh_issue_create` gives
         the fail-closed answer for ``eval "gh issue create ..."`` and
         ``$CMD issue create ...``, which previously fell through to allow.

       Ask the permit-side question ONLY through
       :func:`_verb_consumes_bare_args`. That function is the single
       sanctioned reader of :data:`_COMMAND_ARG_CONSUMERS`; do not add a
       second one and do not test that set directly here. Membership is
       NECESSARY but not SUFFICIENT — ``git`` is in the set (it consumes bare
       words for ``commit``/``log``/``grep``) yet is a command RUNNER for
       ``bisect run``/``submodule foreach``/``rebase --exec``/``difftool -x``,
       three of which were measured PERMITTING ``gh issue create`` while a
       raw set test was the gate. ``_verb_consumes_bare_args`` is where that
       qualifier lives, so a direct set test silently reopens those holes.

       Every enumeration in this path is on the PERMIT side, so an omission
       over-blocks loudly instead of silently permitting.

    Args:
        command: The raw Bash command string.
        heredoc_stripped: Optional precomputed ``_strip_heredoc_content(command)``
            for the SAME ``command``, supplied by a caller that already
            needed it, so the heredoc strip runs once per gate pass instead
            of twice (Issue #1620 — see the call site below; the strip is no
            longer exponential, but the single-pass contract is pinned).
            When None it is computed here. Passing a value derived from any
            other string is a defect: the heredoc carve-out compares the
            resulting statements against those of ``command``, so a
            mismatched value silently changes which statements count as
            executable.

    Returns:
        True if ``gh issue create`` is reached as the effective verb in at
        least one executable statement, False otherwise. Raises no
        exceptions — on shlex.ValueError for a given statement, that
        statement is skipped (caller's raw-regex fallback preserves
        fail-closed blocking for the whole-command malformed case).
    """
    statements = _split_statements(command)

    # Issue #1619: statements that survive heredoc stripping are real command
    # text; statements that vanish were heredoc BODY lines (data written to a
    # file, never executed). Only the effective-verb scan consults this — the
    # pre-existing argv[0] path is left byte-for-byte on the raw statements so
    # this change cannot weaken anything that already blocked.
    #
    # ISSUE #1620 — FIXED IN lib/heredoc_utils.py. HISTORY KEPT DELIBERATELY.
    # _strip_heredoc_content used to wrap heredoc_utils._HEREDOC_PATTERN, whose
    # `(.*?\n)*?` nested a quantifier inside a lazy repeat and backtracked
    # exponentially when the closing delimiter was never found. Measured on
    # `cat <<EOF > f.txt` + N body lines with NO terminator, end-to-end through
    # the real hook subprocess:
    #     n=18 0.94s | n=19 1.75s | n=20 3.38s | n=21 (147 chars) 6.65s
    # against 0.086s for the same-size TERMINATED heredoc and 0.083s for
    # `echo hello`. Roughly 2x per added line.
    #
    # The PreToolUse budget for this hook is 5 SECONDS (`.claude/settings.json`),
    # and CLAUDE CODE PROCEEDS PAST A TIMED-OUT HOOK. That is now MEASURED, not
    # asserted: in a sandbox, both arms, two runs each, an instant-deny hook
    # BLOCKED while the identical deny behind `sleep 8` PROCEEDED. The
    # production timing corpus holds 16 historical over-budget events for this
    # hook across five days (max 12.719s), predating any probing. So a
    # ~150-character command skipped EVERY gate in this file at once —
    # including the #1435 protected-infrastructure hard floor — not merely this
    # one. It was a live bypass, not a theoretical one.
    #
    # #1620 replaced the regex with a linear line scanner that emulates it
    # byte-for-byte (including the `(\w+)` prefix backtracking — see that
    # module's docstring; a `{0,N}` bound in the style of #1194/#1220/#1221/
    # #1222 would NOT work here and would silently stop stripping long
    # heredocs). Re-measured through this same harness: n=21 0.065s, and 0
    # verdict disagreements across all 7 call sites x 22 commands.
    #
    # The `heredoc_stripped` parameter predates the fix: Issue #1619 added a
    # second call on this path (6 static call sites at HEAD, 7 after; 1 runtime
    # execution per command through _detect_gh_issue_create at HEAD, 2 after),
    # and at n=23 that doubling took 3.19s to 6.43s — over budget. The fold back
    # to one call is no longer load-bearing for ReDoS, but it is still the
    # single-pass contract this gate is written against, and
    # tests/regression/test_issue_1619_gh_issue_create_wrapper_bypass.py pins it
    # as a property. Passing a value derived from any OTHER string is still a
    # defect (see the Args note above).
    stripped_for_heredoc = (
        _strip_heredoc_content(command) if heredoc_stripped is None else heredoc_stripped
    )
    try:
        executable_statements = set(_split_statements(stripped_for_heredoc))
    except (ValueError, re.error):
        # _split_statements is regex-driven, and _strip_heredoc_content fails
        # open by contract (#1620); neither a re.error nor a value error may
        # silently disable the heredoc carve-out.
        import logging

        logging.debug(
            "gh-issue-create gate: heredoc strip failed; treating every "
            "statement as executable",
            exc_info=True,
        )
        executable_statements = set(statements)

    for stmt in statements:
        # Bash comments (Issue #1619). A word beginning with '#' starts a
        # comment that runs to end of line, so once the gate stopped trusting
        # argv[0] the prose in `# ...can the coordinator call gh issue create
        # inside the pipeline` read as an invocation. Measured against 1,282
        # decision-relevant commands from this repo's own activity log: 15 such
        # comment lines would have been refused. A permanently-red check trains
        # everyone to ignore the whole class, so truncate at the comment marker
        # — which is exactly what the shell itself does.
        #
        # This MUST run on the raw statement text, before tokenization:
        # _strip_body_arg_values rejoins shlex tokens with spaces and so
        # destroys the quoting that distinguishes a comment marker from a
        # quoted `'#'` literal. See _strip_shell_comment for the measured
        # bypass that a post-tokenization predicate permitted.
        stmt_code = _strip_shell_comment(stmt)
        if not stmt_code.strip():
            continue
        try:
            stripped_cmd, _dropped = _strip_body_arg_values(stmt_code)
        except ValueError:
            # Malformed statement — skip; whole-command fallback handles it.
            continue
        try:
            seg = shlex.split(stripped_cmd, posix=True)
        except ValueError:
            continue
        if not seg:
            continue

        # Skip leading env-var assignments (FOO=bar gh issue create ...).
        idx = 0
        while idx < len(seg) and "=" in seg[idx] and not seg[idx].startswith("-"):
            idx += 1
        if idx >= len(seg):
            continue
        verb = seg[idx]

        # Shell-wrapper case (sh -c "gh issue create ..."): handled by the
        # bypass detector — do NOT double-flag here.
        if verb in _SHELL_WRAPPERS:
            continue

        # --- Effective-verb resolution (Issue #1619) ---------------------
        # Locate the `gh issue create` token triple anywhere in the statement
        # rather than trusting argv[0]. Basename-aware, so `/usr/bin/gh`
        # counts too.
        pos = _find_gh_issue_create_triple(seg, idx)

        if pos == idx:
            # Direct invocation — the pre-existing case, unchanged.
            return True

        if pos is not None:
            # `gh issue create` is reached THROUGH a leading token. That token
            # is either a command runner (env/nice/timeout/xargs/sudo/ssh/an
            # invented one) or a verb that consumes bare words as data.
            # Unknown resolves to REFUSE — the whole point of Issue #1619 is
            # that the unknown case must not be a silent permit.
            #
            # Ask through _verb_consumes_bare_args, never by testing
            # _COMMAND_ARG_CONSUMERS directly: `git` is on the permit side for
            # `commit`/`log`/`grep` but is a command RUNNER for
            # `bisect run`/`submodule foreach`/`rebase --exec`/`difftool -x`.
            if _verb_consumes_bare_args(seg, idx):
                continue
            if stmt not in executable_statements:
                # Heredoc body prose, not a command. Data, not execution.
                continue
            return True

        # No token triple: the verb may be unresolvable (eval / $CMD).
        if stmt in executable_statements and _unresolvable_verb_reaches_gh_issue_create(
            seg, idx
        ):
            return True

    return False


def _contains_gh_issue_create_bypass(command: str) -> bool:
    """Detect subprocess-wrapped 'gh issue create' bypass patterns (Issue #618).

    Checks the RAW (unstripped) command string for patterns where 'gh issue create'
    is invoked indirectly via subprocess wrappers, shell wrappers, or backtick
    substitution. These bypasses escape the normal stripped-string detection
    because the 'gh issue create' text lives inside a quoted string argument.

    Patterns detected:
    - python3 -c "... subprocess.run(['gh', 'issue', 'create'] ...)"
    - python -c "... subprocess.call(['gh', 'issue', 'create'] ...)"
    - python3 -c "... subprocess.Popen(['gh', 'issue', 'create'] ...)"
    - python3 -c "... os.system('gh issue create ...')"
    - sh -c "gh issue create ..."
    - bash -c "gh issue create ..."
    - `gh issue create ...` (backtick substitution)
    - $(gh issue create ...) (command substitution)

    Args:
        command: The raw (unstripped) Bash command string.

    Returns:
        True if a bypass pattern is detected, False otherwise.
    """
    import re

    try:
        # Pattern 1: Python subprocess wrappers — subprocess.run/call/Popen/check_output
        # with 'gh' and 'issue' and 'create' appearing as list elements or in a string.
        # We look for the subprocess family of calls followed by gh issue create nearby.
        # Issue #1629 tracks this pattern's separate cubic scanning behaviour on
        # large inputs (three unbounded `[^)]*` runs). NOT #1620 and NOT fixed
        # here — different regex, different class, deliberately out of scope.
        subprocess_pattern = (
            r'subprocess\s*\.\s*(?:run|call|Popen|check_output|check_call)'
            r'[^)]*\bgh\b[^)]*\bissue\b[^)]*\bcreate\b'
        )
        if re.search(subprocess_pattern, command, re.IGNORECASE | re.DOTALL):
            return True

        # Pattern 2: os.system('gh issue create ...') or os.system("gh issue create ...")
        os_system_pattern = r'os\s*\.\s*system\s*\([^)]*\bgh\s+issue\s+create\b'
        if re.search(os_system_pattern, command, re.IGNORECASE | re.DOTALL):
            return True

        # Pattern 3: sh -c "gh issue create ..." or bash -c "gh issue create ..."
        # Also covers: /bin/sh -c, /bin/bash -c, /usr/bin/env sh -c, etc.
        shell_wrapper_pattern = (
            r'(?:^|[|;&\s])(?:/\S+/)?(?:sh|bash|zsh|dash)\s+-c\s+'
            r'["\'](?:[^"\'\\]|\\.)*\bgh\s+issue\s+create\b'
        )
        if re.search(shell_wrapper_pattern, command, re.IGNORECASE | re.DOTALL):
            return True

        # Patterns 4 and 5: backtick / $() command substitution at command position.
        # Issue #1203: previously these were RAW regex scans, which produced
        # false positives when the user passed a backtick-quoted body to
        # `gh issue comment` (live-confirmed). Make argv-aware: tokenize via
        # shlex.split, strip the VALUE token that follows --body/--title/
        # --body-file (and the --body=VALUE attached-value form), rejoin, then
        # apply the original regex on the reconstructed string. The reconstructed
        # form still contains the bypass when it lives at command position (e.g.
        # `RESULT=\`gh issue create...\``) but no longer contains backtick/$()
        # substrings that were merely body-argument content.
        # Mirrors _detect_git_bypass shlex precedent (~line 624). `sh -c
        # "gh issue create..."` and subprocess wrappers are caught by Patterns
        # 1-3 above and remain blocked unchanged. On shlex ValueError
        # (malformed shell), fall back to the original raw-regex behavior so
        # we never weaken blocking on garbled inputs.
        # Argv-aware body-value stripping is handled by the module-level
        # _strip_body_arg_values helper (hoisted in Issue #1215 so both this
        # bypass detector AND _detect_gh_issue_create can share it). The flag
        # set GH_ISSUE_BODY_FLAGS combines gh's --body/--title/--body-file
        # with git commit's -m/--message/-F/--file to cover the union of
        # false-positive surfaces.
        try:
            stripped_for_subst, dropped_values = _strip_body_arg_values(command)
        except ValueError:
            # Malformed shell — fall back to the original raw-regex behavior
            # so we never weaken blocking on garbled inputs.
            backtick_pattern = r'`\s*gh\s+issue\s+create\b'
            if re.search(backtick_pattern, command, re.IGNORECASE | re.DOTALL):
                return True
            dollar_subst_pattern = r'\$\(\s*gh\s+issue\s+create\b'
            if re.search(dollar_subst_pattern, command, re.IGNORECASE | re.DOTALL):
                return True
            return False

        # Patterns 4 & 5 (Tier A — command-position substitution).
        # After body-value stripping, any remaining backtick/$() substitution is
        # at command position (e.g. RESULT=`gh issue create...` or
        # FOO=$(gh issue create...)). These ALWAYS execute at shell runtime
        # and must be blocked.
        # Pattern 4: Backtick command substitution: `gh issue create ...`
        backtick_cmd_pos = r'`\s*gh\s+issue\s+create\b'
        if re.search(backtick_cmd_pos, stripped_for_subst, re.IGNORECASE | re.DOTALL):
            return True

        # Pattern 5: $(...) command substitution with gh issue create as the
        # direct command, e.g. $(gh issue create --title "test").
        # NOT matched: $(cat <<'EOF'\ngh issue create\nEOF\n) — heredoc body.
        dollar_subst_cmd_pos = r'\$\(\s*gh\s+issue\s+create\b'
        if re.search(dollar_subst_cmd_pos, stripped_for_subst, re.IGNORECASE | re.DOTALL):
            return True

        # Pattern 6 (Tier B — FINDING-1 fix, Issue #1203 remediation cycle 1).
        # Substitution inside body-flag VALUES. In POSIX shell, both $() and
        # backticks INSIDE DOUBLE QUOTES execute (and create the issue). Inside
        # single quotes they do NOT execute (single quotes are literal).
        # shlex.split(posix=True) discards quote-type info, so we cannot tell
        # which quoting style produced each dropped value. Per the FINDING-1
        # guidance, we fail closed: any dropped value containing a backtick or
        # $() substitution with `gh issue create` AT COMMAND POSITION inside
        # the substitution is blocked. Match the same precision as the
        # Tier-A command-position scan (`\s*gh\s+issue\s+create` at the start
        # of the substitution opener) so that:
        #   - `--body "$(gh issue create -t x)"`     → BLOCKED (real bypass)
        #   - `--body "$(echo x)"`                    → ALLOWED (benign)
        #   - `--body "see \`some helper\`"`           → ALLOWED (no create pattern)
        #   - `git commit -m "$(cat <<EOF ... EOF)"` → ALLOWED (cat is command;
        #       gh issue create inside heredoc body is just text)
        # Tradeoff: a single-quoted body containing literal
        # `` `gh issue create` `` as code-formatted prose will be blocked even
        # though shell would not execute it. The fail-closed posture is the
        # safer choice — the live-confirmed false positive (prose backticks
        # or $() WITHOUT the create pattern at command position in the
        # substitution) is still allowed.
        value_backtick_cmd_pos = r'`\s*gh\s+issue\s+create\b'
        value_dollar_cmd_pos = r'\$\(\s*gh\s+issue\s+create\b'
        for val in dropped_values:
            if re.search(value_backtick_cmd_pos, val, re.IGNORECASE | re.DOTALL):
                return True
            if re.search(value_dollar_cmd_pos, val, re.IGNORECASE | re.DOTALL):
                return True

        return False
    except re.error:
        return False  # Fail-open on regex error


def _detect_gh_issue_marker_creation(command: str) -> "Optional[str]":
    """Detect Bash commands that directly create the gh issue marker file (Issue #627).

    The marker file ``autonomous_dev_gh_issue_allowed.marker`` is written by the
    approved /create-issue pipeline to signal that a ``gh issue create`` call is
    authorized.  Allowing arbitrary code to create the file directly would
    short-circuit the entire bypass-prevention mechanism.

    Uses deny-by-default logic: if the marker name appears in the command and
    the operation is NOT provably read-only/delete, it is blocked.  This
    prevents bypass via novel write methods (e.g. ``python3 -c "json.dump(...)"``,
    ``dd``, ``install``, ``os.open``).

    Read-only and delete operations (``cat``, ``ls``, ``rm``, ``stat``, ``test``,
    ``head``, ``tail``, ``wc``, ``file``, ``readlink``, ``[``) are intentionally
    NOT blocked, nor are commands that merely *mention* the marker name in
    output text (``grep``, ``echo``/``printf`` without redirect to the marker).

    Allow-through conditions (same guards as ``_detect_gh_issue_create``):
    1. ``_is_pipeline_active()`` — the pipeline itself writes the marker legitimately.
    2. Agent name in ``GH_ISSUE_AGENTS`` — authorised agents may also write it.
    3. ``_is_issue_command_active()`` — issue-creating command is active.
    Note: there is deliberately NO marker-file allow-through here (circular).

    Args:
        command: The raw Bash command string to inspect.

    Returns:
        Block reason string if marker creation detected and not allowed,
        None if the command is clean or allowed.
    """
    try:
        marker_anchor = "autonomous_dev_gh_issue_allowed"

        # Fast path: marker name not mentioned at all → nothing to check
        if marker_anchor not in command.lower():
            return None

        # --- Identify the command segment that references the marker ---
        # For piped commands, only inspect the segment containing the marker.
        cmd_lower = command.lower()
        segments = command.split("|")
        relevant_segment = command  # default: whole command
        for seg in segments:
            if marker_anchor in seg.lower():
                relevant_segment = seg.strip()
                break

        seg_lower = relevant_segment.lower()
        seg_stripped = relevant_segment.strip()

        # --- Read-only / delete verbs: first token of the relevant segment ---
        # Extract the first token (the command verb) from the segment.
        # Handle leading env vars (FOO=bar cmd ...) and sudo.
        tokens = seg_stripped.split()
        verb = ""
        for tok in tokens:
            # Skip env-var assignments (VAR=value)
            if "=" in tok and not tok.startswith("-"):
                continue
            # Skip sudo
            if tok == "sudo":
                continue
            verb = tok.lower()
            break

        readonly_verbs = {
            "cat", "ls", "stat", "test", "head", "tail", "wc", "file",
            "rm", "readlink", "[",
        }
        if verb in readonly_verbs:
            return None

        # --- Reference-only mentions (grep, echo/printf without redirect to marker) ---
        if verb == "grep":
            return None

        # echo/printf: allowed UNLESS a redirect targets the marker file
        if verb in ("echo", "printf"):
            # Check if there is a redirect (> or >>) followed by the marker name
            # in the same segment
            import re
            if re.search(
                r">\s*\S*" + re.escape(marker_anchor), seg_lower
            ):
                pass  # Fall through to blocking
            else:
                return None

        # --- Allow-through conditions (unchanged) ---

        # Allow-through 1: Pipeline is active (writes the marker legitimately)
        if _is_pipeline_active():
            return None

        # Allow-through 2: Agent is authorised for issue creation
        agent_name = _get_active_agent_name()
        if agent_name in GH_ISSUE_AGENTS:
            return None

        # Allow-through 3: Issue-creating command is active (Issue #630)
        if _is_issue_command_active():
            return None

        return (
            "BLOCKED: Cannot create gh issue marker file directly.\n"
            "REQUIRED NEXT ACTION: Use /create-issue or /create-issue --quick "
            "to create issues through the approved pipeline. "
            "Do NOT create the marker file directly."
        )
    except Exception:
        return None  # Fail-open on any error





def _detect_architectural_decision_without_plan_critic(
    tool_name: str, tool_input: dict
) -> "Optional[str]":
    """Detect architectural-decision creation without plan-critic approval.
    
    Blocks:
    1. Write tool creating new docs/architecture/adr-NNN-*.md files
    2. Bash gh issue create with architectural keywords
    
    Unless record_plan_critic_passed() was called earlier in session.
    
    Issue #1330.
    """
    import os
    import re
    from pathlib import Path
    
    # Get session ID
    session_id = os.environ.get("CLAUDE_SESSION_ID") or \
                 os.environ.get("AUTONOMOUS_DEV_SESSION_ID") or \
                 "unknown"
    
    # Check Write tool for new ADR creation
    if tool_name == "Write":
        file_path = tool_input.get("file_path", "")
        # Match docs/architecture/adr-NNN-*.md pattern
        if re.match(r".*docs/architecture/adr-\d+-.*\.md$", file_path):
            # Check if file already exists (allow edits to existing)
            if not Path(file_path).exists():
                # This is a NEW ADR creation - check gate
                pass  # Fall through to gate check
            else:
                # Existing file - allow edits
                return None
        else:
            # Not an ADR file
            return None
    
    # Check Bash tool for gh issue create with architectural keywords
    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        
        # Check if this is gh issue create
        if "gh issue create" not in command:
            return None
        
        # Extract body content
        body = ""
        
        # Check for --body argument
        body_match = re.search(r"""--body\s+["']([^"']*)["']""", command)
        if body_match:
            body = body_match.group(1)
        else:
            # Check for --body-file
            body_file_match = re.search(r'--body-file\s+(\S+)', command)
            if body_file_match:
                body_file = body_file_match.group(1)
                try:
                    with open(body_file, 'r') as f:
                        body = f.read()
                except (IOError, OSError):
                    pass
        
        # Check for architectural keywords in body
        architectural_keywords = [
            "architectural-debt",  # label
            "Status: Proposed",
            "architectural review",
            r"ADR-\d{3,4}",  # regex pattern
            "## Open Questions",
            "## Implementation Phases"
        ]
        
        found_keyword = False
        for keyword in architectural_keywords:
            if keyword.startswith(r"ADR-"):
                # Regex pattern
                if re.search(keyword, body):
                    found_keyword = True
                    break
            else:
                # Direct string match
                if keyword in body:
                    found_keyword = True
                    break
        
        if not found_keyword:
            return None
        
        # Found architectural keyword - fall through to gate check
    
    else:
        # Not Write or Bash tool
        return None
    
    # Check bypass file
    bypass_file = Path("/tmp/skip_plan_critic_gate")
    if bypass_file.exists():
        try:
            bypass_file.unlink()
        except OSError:
            pass
        
        # Log bypass usage to activity log
        try:
            from pathlib import Path
            import sys
            import json
            from datetime import datetime
            
            # Add lib to path
            lib_path = Path(__file__).parent.parent / "lib"
            if lib_path.exists():
                sys.path.insert(0, str(lib_path))
            
            from activity_log import log_activity
            
            log_activity(
                tool_name=tool_name,
                event="plan_critic_gate_bypass",
                details={
                    "bypass": "plan_critic_gate one-shot file",
                    "session_id": session_id
                }
            )
        except ImportError:
            pass  # Activity logging is optional
        
        return None  # Allow with bypass
    
    # Check if plan-critic passed in this session
    try:
        from pathlib import Path
        import sys
        
        # Add lib to path
        lib_path = Path(__file__).parent.parent / "lib"
        if lib_path.exists():
            sys.path.insert(0, str(lib_path))
        
        from pipeline_completion_state import get_plan_critic_passed
        
        if get_plan_critic_passed(session_id):
            return None  # Allow - plan-critic has passed
    except ImportError:
        # If we can't import, fail open
        return None
    
    # Block - plan-critic has not passed
    return (
        "BLOCKED: Architectural-decision creation detected. plan-critic has not run in this session.\n"
        "REQUIRED NEXT ACTION: Invoke /plan with the architectural-decision description, complete the 3+ round plan-critic loop, then proceed to file the issue / write the ADR.\n"
        "Bypass (emergency): touch /tmp/skip_plan_critic_gate (one-shot, logged to activity log)."
    )




def _get_active_issue_command() -> "Optional[str]":
    """Get the currently active issue command from context file.
    
    Returns:
        The command string if valid and recent, else None.
    """
    try:
        import json as _json
        from pathlib import Path
        
        context_path = Path(GH_ISSUE_COMMAND_CONTEXT_PATH)
        if not context_path.exists():
            return None
        
        with open(context_path) as f:
            data = _json.load(f)
        
        command = data.get("command")
        if command not in GH_ISSUE_COMMANDS:
            return None
        
        # Use file modification time for age check (same as _is_issue_command_active)
        import time as _time
        age = _time.time() - context_path.stat().st_mtime
        if age > 3600:
            return None
        
        return command
    except Exception:
        return None


def _detect_daily_aggregate_direct_filing(command_str: str) -> "Optional[str]":
    """Detect direct `gh issue create --title "<prefix> ..."` for guarded prefixes.

    Returns block reason if a guarded title is being filed without marker,
    else None. Called AFTER _is_issue_command_active() returns False so
    /improve, /plan marker paths retain precedence.

    Two-scan title extraction:
      Scan 1 CLI-arg form: --title <val> or --title="val" or --title='val'
      Scan 2 list-literal: '--title', 'val' (subprocess list form)

    Guarded prefixes (exact startswith):
      - "Auto-triage findings —" (em-dash)
      - "[CRITICAL] AI triage —" (em-dash)
      - "[drain-stuck] watchdog" (Issue #1374 — covers both the legacy
        "[drain-stuck] watchdog: <reason>" and the new
        "[drain-stuck] watchdog <YYYY-MM-DD>" title formats)

    Only allow when active marker command == 'triage-aggregate'.
    """
    import re

    GUARDED = (
        "Auto-triage findings —",
        "[CRITICAL] AI triage —",
        "[drain-stuck] watchdog",  # Issue #1374 — matches both "[drain-stuck] watchdog: $REASON" and "[drain-stuck] watchdog 2026-07-09" via startswith
    )
    titles = []
    
    # Scan 1: CLI form - handles regular quotes
    # Match: --title "value" or --title='value' or --title="value"
    for m in re.finditer(r"--title\s*[=\s]\s*(['\"])([^'\"]*?)\1", command_str):
        titles.append(m.group(2))
    
    # Scan 2: Escaped quotes form (e.g., within os.system)  
    # Match: --title \"value\"
    for m in re.finditer(r'--title\s+\\"([^"]*?)\\"', command_str):
        titles.append(m.group(1))
    
    # Scan 3: list-literal form
    # Match: '--title', 'value'
    for m in re.finditer(r"['\"]\s*--title\s*['\"]\s*,\s*['\"](.*?)['\"]", command_str):
        titles.append(m.group(1))
    
    for title in titles:
        for prefix in GUARDED:
            if title.startswith(prefix):
                # Check if triage-aggregate marker is the active one
                active = _get_active_issue_command()
                if active != 'triage-aggregate':
                    return (
                        f"Direct filing of guarded title '{title[:60]}...' blocked. "
                        f"Use plugins/autonomous-dev/lib/daily_aggregate_manager.py::"
                        f"open_or_supersede_daily_aggregate() instead."
                    )
    return None


def _resolve_current_repo_owner() -> "Optional[str]":
    """Return the current repo's owner via ``git remote get-url origin``.

    Reuses ``parse_owner_repo()`` from the dependabot_tracker library to parse
    both SSH and HTTPS remote URL forms. Fail-open: returns None on any error
    (subprocess failure, non-GitHub remote, missing origin, import failure).
    A None result routes the caller to fail-closed (keep blocking) because the
    owner comparison cannot be made. (Issue #1383)

    Returns:
        The owner segment of the origin remote (e.g. ``"anthropics"``), or None
        when it cannot be determined.
    """
    try:
        _lib_dir = Path(__file__).resolve().parent.parent / "lib"
        if str(_lib_dir) not in sys.path:
            sys.path.insert(0, str(_lib_dir))
        from dependabot_tracker import parse_owner_repo  # type: ignore

        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        parsed = parse_owner_repo(result.stdout.strip())
        return parsed[0] if parsed else None
    except Exception:
        return None


def _gh_issue_create_target_is_cross_owner(command: str) -> bool:
    """Return True iff ``gh issue create`` targets a DIFFERENT owner's repo.

    A cross-owner ``gh issue create --repo <other-org>/<repo>`` is a legitimate
    upstream-filing action that the /create-issue pipeline does not cover, so it
    should be allowed through the gate. A same-owner (or ambiguous) target must
    keep routing to /create-issue.

    Fail-CLOSED (returns False -> keep blocking) on any ambiguity: malformed
    shell, no ``--repo``/``-R`` flag, a bare (owner-less) target, an
    unresolvable current owner, or any exception.

    Security notes (allow-decision derived from an untrusted command string):
        * shlex tokenization mirrors gh/Cobra argv semantics.
        * When ``--repo``/``-R`` appears multiple times, the LAST occurrence
          wins (gh/Cobra flag semantics).
        * Owner comparison is case-insensitive on the OWNER segment only.
        * ``GH_REPO`` env indirection is intentionally out of scope — only the
          command string is inspected.

    Args:
        command: The raw Bash command string to inspect.

    Returns:
        True only when a target owner is confidently parsed AND differs from the
        resolved current-repo owner; False in every ambiguous or same-owner
        case. (Issue #1383)
    """
    try:
        try:
            tokens = shlex.split(command, posix=True)
        except ValueError:
            return False
        target = None
        i = 0
        while i < len(tokens):
            t = tokens[i]
            if t in ("--repo", "-R"):
                if i + 1 < len(tokens):
                    target = tokens[i + 1]
                    i += 2
                    continue
                return False
            elif t.startswith("--repo=") or t.startswith("-R="):
                target = t.split("=", 1)[1]
            i += 1
        if not target or "/" not in target:
            return False
        target_owner = target.split("/", 1)[0].strip().lower()
        if not target_owner:
            return False
        current_owner = _resolve_current_repo_owner()
        if not current_owner:
            return False
        return target_owner != current_owner.strip().lower()
    except Exception:
        return False


def _detect_gh_issue_create(command: str) -> "Optional[str]":
    """Detect direct 'gh issue create' usage outside approved contexts (Issue #599).

    Blocks direct GitHub issue creation via the gh CLI to enforce the
    /create-issue pipeline which includes research, duplicate detection,
    and proper formatting.

    Also detects subprocess-bypass patterns (Issue #618) where 'gh issue create'
    is wrapped inside python3 -c subprocess calls, sh/bash -c, or backtick
    substitutions to evade the normal stripped-string detection.

    Args:
        command: The raw Bash command string to inspect.

    Returns:
        Block reason string if gh issue create detected and not allowed,
        None if the command is clean or allowed.
    """
    import re

    try:
        # Strip quoted segments and heredoc content to avoid false positives
        # when 'gh issue create' appears inside commit messages, echo strings, etc.
        #
        # Issue #1620: keep the heredoc-stripped text in its own name and hand
        # it to _gh_issue_create_at_command_position below. That helper needs
        # the identical value, and _strip_heredoc_content is an exponentially
        # backtracking regex (measured 6.5s on a 175-char unterminated heredoc,
        # against a 5s hook budget) — computing it twice doubled the wall-clock
        # cost of the worst case for no benefit.
        heredoc_stripped = _strip_heredoc_content(command)
        stripped = _strip_quoted_segments(heredoc_stripped)

        # Check 1: Direct 'gh issue create' in the stripped command.
        #
        # Issue #1215: the raw substring scan produced a false positive when
        # the substring appeared in prose inside a git-commit body that
        # escaped the simple quote stripper (e.g., shell-escaped quotes,
        # ANSI-C $'...' quoting, or unquoted prose between -m and the next
        # argument). The fix is argv-position-aware: require that
        # ``gh issue create`` lives at argv[0] of some pipeline segment, NOT
        # merely as a substring of the rendered command. The shlex-aware
        # helper mirrors the bypass detector's #1203 treatment.
        #
        # Fail-closed: on malformed shell (shlex ValueError), the helper
        # returns False AND we then check the raw-regex fallback against the
        # quote-stripped command. This preserves blocking on garbled input
        # where a true bypass form like
        # ``RESULT=`gh issue create --title 'unterminated`` would still trip
        # the regex scan even though shlex cannot parse it. The bypass
        # detector independently scans the raw command for the same family
        # of forms.
        argv_match = _gh_issue_create_at_command_position(
            command, heredoc_stripped=heredoc_stripped
        )

        # Raw-regex fallback ONLY when the shlex-aware path could not parse.
        # We detect the unparseable case by attempting the same shlex call
        # and catching ValueError. When shlex parses cleanly but argv_match
        # is False, the substring is genuinely NOT at command position and
        # the direct-match path stays False (true argv-blind false positive
        # avoided).
        try:
            shlex.split(command, posix=True)
            shlex_parsed = True
        except ValueError:
            shlex_parsed = False

        if shlex_parsed:
            direct_match = argv_match
        else:
            # Malformed shell — fall back to the original raw-regex behavior
            # on the quote-stripped command so true bypass forms with garbled
            # syntax still trip the gate.
            direct_match = bool(
                re.search(r'\bgh\s+issue\s+create\b', stripped, re.IGNORECASE)
            )

        # Check 2: Subprocess bypass patterns in the RAW command (Issue #618).
        # These wrappers embed 'gh issue create' inside quoted strings, which
        # stripping would normally remove — so we scan the original command.
        bypass_match = _contains_gh_issue_create_bypass(command)

        if not direct_match and not bypass_match:
            return None

        # Allow-through 1: Pipeline is active (implementer/test-master/doc-master)
        if _is_pipeline_active():
            return None

        # Allow-through 2: Agent is authorized for issue creation
        agent_name = _get_active_agent_name()
        if agent_name in GH_ISSUE_AGENTS:
            return None

        # Allow-through 3: Issue-creating command is active (Issue #630).
        # Prior-call ordering contract (Issue #1203): the command context file
        # MUST be written in a PRIOR Bash tool call (separate from the gh issue
        # create call), because PreToolUse evaluates each Bash invocation BEFORE
        # it runs — bundling "write context && gh issue create" into one Bash
        # call leaves the context absent at hook-evaluation time and blocks.
        # See #1203 plan and the six issue-creating command markdowns.
        # Out-of-scope caveat: cross-session /tmp context leak between concurrent
        # sessions is tracked separately as Issue #1206.
        # NOTE: a prior marker-file READ allow-through (writing
        # GH_ISSUE_MARKER_PATH would grant a 1h pass) was removed in #1203
        # because nothing writes the marker anymore (the WRITE has been blocked
        # by _detect_gh_issue_marker_creation since #627) — that allow-through
        # was dead code. The WRITE blocker is kept as defense-in-depth.
        if _is_issue_command_active():
            return None

        # Allow-through 4: cross-owner upstream filing (Issue #1383).
        # `gh issue create --repo <other-org>/<repo>` targets a repo owned by a
        # DIFFERENT owner than the current repo — a legitimate upstream-filing
        # action that /create-issue does not cover. Same-owner / missing / bare /
        # unresolvable targets all fail-closed (False) and keep blocking.
        if _gh_issue_create_target_is_cross_owner(command):
            return None

        return (
            "BLOCKED: Cannot create GitHub issues with 'gh issue create' directly.\n"
            "REQUIRED NEXT ACTION: Use /create-issue or /create-issue --quick instead.\n\n"
            "/create-issue includes research, duplicate detection, and ensures "
            "proper formatting.\n\n"
            "FORBIDDEN: Do NOT suggest the user run 'gh issue create' manually, "
            "including via '! gh issue create' or any other bypass method. "
            "The '!' prefix runs commands outside the hook system and defeats "
            "enforcement. The ONLY acceptable path is /create-issue."
        )
    except Exception:
        return None  # Fail-open on any error


def _check_batch_cia_completions(session_id: str) -> "Optional[str]":
    """Check if all batch issues have CIA completion.

    Loads verify_batch_cia_completions from pipeline_completion_state and
    returns a block reason string if any issues are missing CIA, or None
    if all passed (or on any error — fail-open).

    Args:
        session_id: The pipeline session identifier.

    Returns:
        Block reason string if CIA missing for any issue, None otherwise.

    Issues: #712
    """
    try:
        hook_dir = Path(__file__).resolve().parent
        lib_candidates = [
            hook_dir.parent / "lib" / "pipeline_completion_state.py",
            hook_dir.parents[2] / "lib" / "pipeline_completion_state.py",
        ]
        mod = None
        for lib_path in lib_candidates:
            if lib_path.exists():
                spec = importlib.util.spec_from_file_location(
                    "pipeline_completion_state", str(lib_path)
                )
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                break

        if mod is None or not hasattr(mod, "verify_batch_cia_completions"):
            return None  # Fail-open

        all_passed, with_cia, missing_cia = mod.verify_batch_cia_completions(session_id)
        if all_passed:
            return None

        missing_str = ", ".join(f"#{n}" for n in missing_cia)
        return (
            f"BLOCKED: Batch CIA gate — issues missing continuous-improvement-analyst: "
            f"{missing_str}. All batch issues MUST have CIA completion before git commit. "
            f"REQUIRED NEXT ACTION: Run the continuous-improvement-analyst agent for "
            f"the missing issues before committing. "
            f"Set SKIP_BATCH_CIA_GATE=1 to bypass. (Issue #712)"
        )
    except Exception:
        return None  # Fail-open


def _check_batch_doc_master_completions(session_id: str) -> "Optional[str]":
    """Check if all batch issues have doc-master completion.

    Loads verify_batch_doc_master_completions from pipeline_completion_state and
    returns a block reason string if any issues are missing doc-master, or None
    if all passed (or on any error — fail-open).

    Args:
        session_id: The pipeline session identifier.

    Returns:
        Block reason string if doc-master missing for any issue, None otherwise.

    Issues: #786
    """
    try:
        hook_dir = Path(__file__).resolve().parent
        lib_candidates = [
            hook_dir.parent / "lib" / "pipeline_completion_state.py",
            hook_dir.parents[2] / "lib" / "pipeline_completion_state.py",
        ]
        mod = None
        for lib_path in lib_candidates:
            if lib_path.exists():
                spec = importlib.util.spec_from_file_location(
                    "pipeline_completion_state", str(lib_path)
                )
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                break

        if mod is None or not hasattr(mod, "verify_batch_doc_master_completions"):
            return None  # Fail-open

        all_passed, with_doc_master, missing_doc_master = mod.verify_batch_doc_master_completions(session_id)
        if all_passed:
            return None

        # Differentiate "never ran" vs "ran but no valid verdict" (Issue #837).
        # Read the raw state to inspect verdict fields for each missing issue.
        never_ran: list[int] = []
        no_verdict: list[int] = []
        try:
            if hasattr(mod, "_read_state"):
                raw_state = mod._read_state(session_id)
                completions = raw_state.get("completions", {}) if raw_state else {}
                for issue_num in missing_doc_master:
                    issue_data = completions.get(str(issue_num), {})
                    if isinstance(issue_data, dict) and issue_data.get("doc-master"):
                        no_verdict.append(issue_num)
                    else:
                        never_ran.append(issue_num)
            else:
                never_ran = list(missing_doc_master)
        except Exception:
            never_ran = list(missing_doc_master)

        parts: list[str] = []
        if never_ran:
            never_ran_str = ", ".join(f"#{n}" for n in never_ran)
            parts.append(f"doc-master never ran: {never_ran_str}")
        if no_verdict:
            no_verdict_str = ", ".join(f"#{n}" for n in no_verdict)
            parts.append(f"doc-master ran but produced no valid verdict: {no_verdict_str}")

        detail = "; ".join(parts) if parts else ", ".join(f"#{n}" for n in missing_doc_master)
        return (
            f"BLOCKED: Batch doc-master gate — {detail}. "
            f"All batch issues MUST have doc-master completion with a valid verdict before git commit. "
            f"REQUIRED NEXT ACTION: Run the doc-master agent for "
            f"the missing issues before committing. "
            f"Set SKIP_BATCH_DOC_MASTER_GATE=1 to bypass. (Issue #786, #837)"
        )
    except Exception:
        return None  # Fail-open


def _check_pipeline_agent_completions(session_id: str) -> "Optional[str]":
    """Check if all required pipeline agents have completed before git commit.

    Loads verify_pipeline_agent_completions from pipeline_completion_state and
    returns a block reason string if any required agents are missing, or None
    if all passed (or on any error -- fail-open).

    Args:
        session_id: The pipeline session identifier.

    Returns:
        Block reason string if agents missing, None otherwise.

    Issues: #802
    """
    try:
        hook_dir = Path(__file__).resolve().parent
        lib_candidates = [
            hook_dir.parent / "lib" / "pipeline_completion_state.py",
            hook_dir.parents[2] / "lib" / "pipeline_completion_state.py",
        ]
        mod = None
        for lib_path in lib_candidates:
            if lib_path.exists():
                spec = importlib.util.spec_from_file_location(
                    "pipeline_completion_state", str(lib_path)
                )
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                break

        if mod is None or not hasattr(mod, "verify_pipeline_agent_completions"):
            return None  # Fail-open

        # Determine pipeline mode. #1177: env-var handled internally by
        # _get_pipeline_mode_from_state() since #1173 — the previous
        # outer `os.environ.get("PIPELINE_MODE") or ...` short-circuit
        # was dead code (the helper already reads the same env var at
        # its first line).
        pipeline_mode = _get_pipeline_mode_from_state()
        issue_number = 0
        try:
            # NOTE(#1177-followup): env-var read here may also be dead; audit deferred.
            issue_number = int(os.environ.get("PIPELINE_ISSUE_NUMBER", "0"))
        except (ValueError, TypeError):
            pass

        passed, completed, missing = mod.verify_pipeline_agent_completions(
            session_id, pipeline_mode, issue_number=issue_number
        )
        if passed:
            return None

        # Issue #1228: read-side session-id fallback. When the payload session_id
        # yielded ZERO completion records (not passed AND no completed AND some
        # missing), the gate may be evaluating the WRONG session id -- e.g. the
        # Bash git-commit subprocess dropped CLAUDE_SESSION_ID and fell back to a
        # boot-time "unknown" sentinel while the real agent completions were
        # recorded under a resolvable id. SCOPE-LOCK: this fallback fires ONLY on
        # zero payload-sid records. A PARTIAL primary session (some completed,
        # some missing) still blocks -- we never mask a genuinely incomplete
        # pipeline. Fail-open (skip fallback) if no resolver is available.
        #
        # #1228 concurrent-session hardening: resolve via SESSION-AFFINE sources
        # only (env var + fresh STEP-0 sentinel), NEVER the repo-wide
        # activity-log scan. The broad scan returns "today's most-recent real
        # session id" with no cwd/PID/temporal scoping, so a DIFFERENT concurrent
        # session (a documented regular occurrence in this repo) could have its
        # completions satisfy THIS session's commit gate. resolve_session_id_affine
        # returns None when no affine source yields a real id, so the gate FAILS
        # SAFE (still blocks) instead of trusting a cross-session guess. The
        # legitimate CLAUDE_SESSION_ID-dropped-in-subshell recovery is preserved
        # because the coordinator writes the real session id to the sentinel at
        # STEP 0. Prefer the affine resolver; fall back to the legacy resolver
        # only if the affine one is absent (older lib versions).
        evaluated_sids = [session_id]
        if (
            (not passed)
            and (not completed)
            and missing
            and (
                hasattr(mod, "resolve_session_id_affine")
                or hasattr(mod, "resolve_session_id")
            )
        ):
            if hasattr(mod, "resolve_session_id_affine"):
                resolved = mod.resolve_session_id_affine()
            else:
                resolved = mod.resolve_session_id()
            if resolved and resolved != "unknown" and resolved != session_id:
                evaluated_sids.append(resolved)
                r_passed, r_completed, r_missing = mod.verify_pipeline_agent_completions(
                    resolved, pipeline_mode, issue_number=issue_number
                )
                if r_passed:
                    return None
                # Prefer the better-informed result (more completed agents).
                if len(r_completed) > len(completed):
                    completed, missing = r_completed, r_missing

        missing_str = ", ".join(sorted(missing))
        completed_str = ", ".join(sorted(completed)) if completed else "(none)"
        evaluated_str = ", ".join(evaluated_sids)
        return (
            f"BLOCKED: Agent completeness gate -- missing required agents: "
            f"{missing_str}. Completed: {completed_str}. "
            f"Evaluated session id(s): {evaluated_str}. "
            f"All required pipeline agents MUST complete before git commit. "
            f"REQUIRED NEXT ACTION: Run the missing agents before committing. "
            f"BYPASS (in order of reliability): "
            f"(1) `touch /tmp/skip_agent_completeness_gate` as a SEPARATE command first, "
            f"then retry the commit — file-based, works mid-session "
            f"(chaining with && WILL NOT WORK — the hook intercepts compound commands before touch executes); "
            f"(2) export SKIP_AGENT_COMPLETENESS_GATE=1 BEFORE launching claude "
            f"(env vars don't propagate mid-session — Issue #779). (Issue #802)"
        )
    except Exception:
        return None  # Fail-open


def _detect_settings_json_write(command: str) -> "Optional[str]":
    """Detect Bash commands that write to settings.json or settings.local.json.

    Only blocks during active pipeline. Called separately after pipeline check.

    Issue #971: Primary detection routes through ``_extract_bash_file_writes``
    (which delegates to ``tool_intent.write_targets``) for AST-accurate
    classification. The legacy regex duplicate that flagged ``open()`` calls
    (and produced false positives on ``json.load(open(...))``) is removed.

    A narrow defense-in-depth check is retained for the variable-indirection
    case (``p='settings.json'; json.dump(d, open(p, 'w'))``) where the AST
    detector cannot statically resolve the path. This check requires BOTH a
    settings reference AND a true python write keyword (``json.dump``,
    ``.write_text``, ``.write_bytes``, ``shutil.``, ``os.rename``,
    ``os.replace``), or a non-trivial ``.write(`` call. We deliberately do
    NOT match ``open\\s*\\(`` alone — that was the source of the
    ``json.load(open(...))`` false positive in the legacy code (Issue #971).

    Args:
        command: The Bash command string to inspect.

    Returns:
        Block reason string if settings write detected, None if clean.
    """
    import re

    settings_patterns = [
        r'settings\.json',
        r'settings\.local\.json',
    ]
    # Check ALL write targets — the shim covers redirects, tee, cp/mv,
    # sed -i, dd, tools like rm/touch/chmod, AND python -c snippets via
    # python_write_detector AST analysis. (Issue #557, #768, #971)
    write_targets = _extract_bash_file_writes(command)
    # Issue #958: Allow writes to tempfile directories — these paths cannot
    # affect real settings files under ~/.claude/ or any project root.
    _TEMP_PREFIXES = ("/tmp/", "/var/folders/", "/private/tmp/")
    for target in write_targets:
        if any(target.startswith(prefix) for prefix in _TEMP_PREFIXES):
            continue  # Safe: tempfile directory, not a real settings location
        for pat in settings_patterns:
            if re.search(pat, target):
                if re.search(r'\bsed\s+.*-i', command):
                    return (
                        f"BLOCKED: In-place edit of settings file during active pipeline. "
                        f"Settings files are protected during /implement sessions. (Issue #557) "
                        f"REQUIRED NEXT ACTION: Complete the current /implement pipeline first, "
                        f"then modify settings. Do NOT write settings during an active pipeline."
                    )
                if re.search(r'\bpython3?\s+-c\b', command) or re.search(r'\bpython3?\s+.*?<<', command):
                    return (
                        f"BLOCKED: Python -c command writes to settings file during active pipeline. "
                        f"Settings files are protected during /implement sessions. (Issue #768) "
                        f"REQUIRED NEXT ACTION: Complete the current /implement pipeline first, "
                        f"then modify settings. Do NOT write settings during an active pipeline."
                    )
                return (
                    f"BLOCKED: Bash write to '{target}' during active pipeline. "
                    f"Settings files are protected during /implement sessions. (Issue #557) "
                    f"REQUIRED NEXT ACTION: Complete the current /implement pipeline first, "
                    f"then modify settings. Do NOT write settings during an active pipeline."
                )

    # Defense-in-depth: variable-indirection case for python -c snippets
    # (Issue #768). The AST detector cannot resolve ``p`` in:
    #   python3 -c "p='settings.json'; json.dump({}, open(p,'w'))"
    # so we fall back to a narrow regex check that requires BOTH a settings
    # reference AND a true write keyword. We deliberately do NOT match
    # ``open\s*\(`` alone — that was the false-positive trigger removed in
    # Issue #971 (it flagged read-only ``json.load(open(...))``).
    #
    # Issue #958: Skip the defense-in-depth block entirely when ALL resolved
    # write targets that reference settings patterns are in temp directories.
    # This prevents false-positives on python -c snippets that write to
    # /private/tmp/, /tmp/, or /var/folders/ (e.g. pytest fixtures).
    _all_settings_writes_are_temp = (
        len(write_targets) > 0
        and all(
            any(target.startswith(prefix) for prefix in _TEMP_PREFIXES)
            for target in write_targets
            if any(re.search(pat, target) for pat in settings_patterns)
        )
        and any(
            any(re.search(pat, target) for pat in settings_patterns)
            for target in write_targets
        )
    )
    if _all_settings_writes_are_temp:
        return None
    py_c_patterns = [
        r'python3?\s+-c\s+"([^"]+)"',
        r"python3?\s+-c\s+'([^']+)'",
    ]
    # Narrow write-keyword patterns: each one is a *true* write operation,
    # not an ambiguous expression. open(...) is excluded by design.
    python_write_keywords = [
        r'\bjson\.dump\s*\(',
        r'\.write_text\s*\(',
        r'\.write_bytes\s*\(',
        r'\bshutil\.(copy|copy2|move|copyfile)\s*\(',
        r'\bos\.rename\s*\(',
        r'\bos\.replace\s*\(',
        # Match .write( only when it follows a variable obtained from open()
        # in WRITE mode — heuristic: the snippet contains both an open(...,
        # 'w'/'a'/'wb'/'ab') call AND a .write( call somewhere.
    ]
    for py_c_pat in py_c_patterns:
        for match in re.finditer(py_c_pat, command):
            snippet = match.group(1)
            if not any(re.search(p, snippet) for p in settings_patterns):
                continue
            if any(re.search(wp, snippet) for wp in python_write_keywords):
                return (
                    f"BLOCKED: Python -c command writes to settings file during active pipeline. "
                    f"Settings files are protected during /implement sessions. (Issue #768) "
                    f"REQUIRED NEXT ACTION: Complete the current /implement pipeline first, "
                    f"then modify settings. Do NOT write settings during an active pipeline."
                )
            # ``f = open(p, 'w'); f.write(x)`` pattern: open() in write mode
            # AND a separate .write() call. We DO NOT trigger on .write()
            # alone because that's also how strings/streams are constructed.
            if re.search(r"open\s*\([^)]*,\s*['\"][wa]", snippet) and re.search(r"\.write\s*\(", snippet):
                return (
                    f"BLOCKED: Python -c command writes to settings file during active pipeline. "
                    f"Settings files are protected during /implement sessions. (Issue #768) "
                    f"REQUIRED NEXT ACTION: Complete the current /implement pipeline first, "
                    f"then modify settings. Do NOT write settings during an active pipeline."
                )

    return None


def _detect_realign_bypass(tool_name: str, tool_input: Dict) -> Tuple[str, str]:
    """Detect attempts to run raw mlx_lm scripts bypassing realign CLI (Issue #754).

    RULE #1: Never run raw mlx.launch, mlx_lm.lora, or standalone scripts.
    Users must use the realign CLI wrapper instead.

    Only active when the current project contains realign markers.

    Args:
        tool_name: The Claude Code tool being invoked.
        tool_input: The tool input dictionary (command key for Bash).

    Returns:
        Tuple of (decision, reason) where decision is "deny" or "allow".
    """
    # Only inspect Bash tool calls
    if tool_name != "Bash":
        return ("allow", "")

    command = tool_input.get("command", "")
    if not command:
        return ("allow", "")

    # Patterns that indicate direct mlx_lm/mlx.launch execution (not grep/search)
    import re

    # Only match execution patterns, not grep/search/cat/echo references
    # Look for python -m mlx_lm.X or python -m mlx.launch
    bypass_patterns = [
        r"python[23]?\s+(?:-\w\s+)*-m\s+mlx_lm\.lora\b",
        r"python[23]?\s+(?:-\w\s+)*-m\s+mlx_lm\.fuse\b",
        r"python[23]?\s+(?:-\w\s+)*-m\s+mlx_lm\.generate\b",
        r"python[23]?\s+(?:-\w\s+)*-m\s+mlx_lm\b",
        r"python[23]?\s+(?:-\w\s+)*-m\s+mlx\.launch\b",
    ]

    # Exclude search/inspection commands that reference mlx_lm without executing it
    search_prefixes = (
        "grep ", "rg ", "ag ", "ack ", "find ", "cat ", "less ", "head ",
        "tail ", "echo ", "printf ", "man ", "gh ",
    )
    stripped = command.lstrip()
    if any(stripped.startswith(prefix) for prefix in search_prefixes):
        return ("allow", "")

    for pattern in bypass_patterns:
        if re.search(pattern, command):
            reason = (
                "BLOCKED: Direct use of mlx_lm/mlx.launch is not allowed. "
                "The realign CLI wraps mlx_lm with correct configuration, logging, "
                "and checkpoint management. "
                "REQUIRED NEXT ACTION: Use 'realign train' instead of 'python -m mlx_lm.lora', "
                "or 'realign generate' instead of 'python -m mlx_lm.generate'. "
                "See 'realign --help' for available commands. "
                "Do NOT run raw mlx_lm commands directly. (Issue #754)"
            )
            return ("deny", reason)

    return ("allow", "")


def _extract_bash_file_writes(command: str) -> list:
    """Extract file paths being written to by Bash command.

    Issue #971: This is now a thin compatibility shim that delegates to
    ``tool_intent.write_targets`` when the tool_intent module is loaded.
    Falls back to the legacy regex-based implementation if the new
    classifier is unavailable.

    The shim preserves the public signature (``command: str -> list``) so
    all 5 existing callers continue to work unchanged. SUSPICIOUS_EXEC_SENTINEL
    handling is preserved — when present, it is excluded from the returned
    list (callers that need the sentinel use the dedicated path in
    ``_check_bash_infra_writes`` which calls ``tool_intent`` directly).
    """
    if _tool_intent is None:
        return _extract_bash_file_writes_legacy(command)
    try:
        targets = _tool_intent.write_targets("Bash", {"command": command})
    except Exception:
        return _extract_bash_file_writes_legacy(command)
    # Strip the SUSPICIOUS_EXEC_SENTINEL — historical callers of this
    # function never saw it, only _check_bash_infra_writes did.
    if _python_write_detector is not None:
        sentinel = getattr(_python_write_detector, "SUSPICIOUS_EXEC_SENTINEL", None)
        if sentinel is not None:
            targets = [t for t in targets if t != sentinel]
    return targets


def _extract_bash_file_writes_legacy(command: str) -> list:
    """Legacy regex-based implementation (preserved for fallback).

    Used only when the ``tool_intent`` module fails to load. Returns the
    same shape (``list`` of file path strings) as the shim.
    """
    import re
    file_paths = []

    # Redirection (>, >>) — skip stderr redirects (2>, 2>>)
    redirect_pattern = r'(?<![0-9])[>]{1,2}\s+([^\s;&|]+)'
    for match in re.finditer(redirect_pattern, command):
        fp = match.group(1).strip()
        if fp not in {'/dev/null', '/dev/stderr', '/dev/stdout', '&1', '&2'}:
            file_paths.append(fp)

    # tee command
    tee_pattern = r'\btee\s+(?:-a\s+)?([^\s;&|]+)'
    for match in re.finditer(tee_pattern, command):
        file_paths.append(match.group(1).strip())

    # Heredoc redirect (heredoc >> file)
    heredoc_pattern = r'<<\s*[\'"]?\w+[\'"]?\s*[>]{1,2}\s+([^\s;&|]+)'
    for match in re.finditer(heredoc_pattern, command):
        file_paths.append(match.group(1).strip())

    # cat redirect before heredoc: cat > file << 'EOF' (Issue #558)
    cat_heredoc_pattern = r'\bcat\s+[>]{1,2}\s+([^\s;&|]+)\s+<<'
    for match in re.finditer(cat_heredoc_pattern, command):
        fp = match.group(1).strip()
        if fp not in {'/dev/null', '/dev/stderr', '/dev/stdout', '&1', '&2'}:
            file_paths.append(fp)

    # dd of=FILE (Issue #558)
    dd_pattern = r'\bdd\s+.*?\bof=([^\s;&|]+)'
    for match in re.finditer(dd_pattern, command):
        file_paths.append(match.group(1).strip())

    # sed -i (in-place edit) — Issue #589
    sed_pattern = r'\bsed\s+(?:-[^i]*)?-i[^\s]*\s+(?:[\'"][^\'"]*[\'"]\s+)?([^\s;&|]+)'
    for match in re.finditer(sed_pattern, command):
        file_paths.append(match.group(1).strip())

    # cp / mv destination (last argument) — Issue #589
    cp_mv_pattern = r'\b(?:cp|mv)\s+(?:-[^\s]+\s+)*(?:[^\s]+\s+)+([^\s;&|]+)'
    for match in re.finditer(cp_mv_pattern, command):
        file_paths.append(match.group(1).strip())

    # python3 -c with file writes — Issue #589 (enhanced with python_write_detector)
    py_c_patterns = [
        r'python3?\s+-c\s+"([^"]+)"',   # double-quoted
        r"python3?\s+-c\s+'([^']+)'",    # single-quoted
    ]
    py_c_snippets = []
    for py_c_pattern in py_c_patterns:
        for match in re.finditer(py_c_pattern, command):
            py_c_snippets.append(match.group(1))

    # python3 heredoc with file writes — Issue #589
    py_heredoc_pattern = r'python3?\s+.*?<<\s*[\'"]?(\w+)[\'"]?'
    for match in re.finditer(py_heredoc_pattern, command):
        marker = match.group(1)
        heredoc_start = match.end()
        remaining = command[heredoc_start:]
        _end_match = re.search(r'(?:^|\n)' + re.escape(marker) + r'(?:\n|$)', remaining)
        end_idx = _end_match.start() if _end_match else -1
        heredoc_body = remaining[:end_idx] if end_idx >= 0 else remaining
        py_c_snippets.append(heredoc_body)

    # Use python_write_detector if available, else fall back to inline regex
    for snippet in py_c_snippets:
        if _python_write_detector is not None:
            targets = _python_write_detector.extract_write_targets(snippet)
            for t in targets:
                if t != _python_write_detector.SUSPICIOUS_EXEC_SENTINEL:
                    file_paths.append(t)
        else:
            # Inline regex fallback (original patterns)
            open_pattern = r'open\s*\(\s*[\'"]([^\'"]+)[\'"]\s*,\s*[\'"][wa]'
            for open_match in re.finditer(open_pattern, snippet):
                file_paths.append(open_match.group(1))
            path_write_pattern = r"Path\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\.write_(?:text|bytes)"
            for path_match in re.finditer(path_write_pattern, snippet):
                file_paths.append(path_match.group(1))
            # shutil fallback — Issue #589
            shutil_pattern = r'(?:\w+)\.(?:copy|copy2|move|copyfile)\s*\(\s*[\'"][^\'"]*[\'"]\s*,\s*[\'"]([^\'"]+)[\'"]\s*\)'
            for shutil_match in re.finditer(shutil_pattern, snippet):
                file_paths.append(shutil_match.group(1))
            # os.rename/os.replace fallback — Issue #698 (destination is 2nd arg)
            os_rename_pattern = r'(?:\w+)\.(?:rename|replace)\s*\(\s*[\'"][^\'"]*[\'"]\s*,\s*[\'"]([^\'"]+)[\'"]'
            for os_rename_match in re.finditer(os_rename_pattern, snippet):
                file_paths.append(os_rename_match.group(1))
            # Path(...).rename/Path(...).replace fallback — Issue #698 (destination is 1st arg)
            path_rename_pattern = r'(?:\w+)\s*\(\s*[\'"][^\'"]+[\'"]\s*\)\.(?:rename|replace)\s*\(\s*[\'"]([^\'"]+)[\'"]'
            for path_rename_match in re.finditer(path_rename_pattern, snippet):
                file_paths.append(path_rename_match.group(1))

    return file_paths


def _resolved_logs_dir() -> "Path | None":
    """Return ``<project_root>/.claude/logs``, or None when unresolvable.

    Issue #1726: both loggers below derived their log path from the process's
    current directory (``os.getcwd()``), so PreToolUse records and deviation
    records landed in whatever directory the hook happened to run in — including
    ``plugins/autonomous-dev/commands/.claude/logs/`` inside shipped plugin
    source. Resolution now goes through the canonical resolver, and an
    unresolvable root skips the write with a stderr warning instead of creating
    a stray tree.

    Returns:
        The project's ``.claude/logs`` directory, or None if it cannot be tied
        to a project root.
    """
    try:
        from path_utils import resolve_activity_log_dir
        # resolve_activity_log_dir() returns <root>/.claude/logs/activity
        return resolve_activity_log_dir().parent
    except Exception as exc:
        try:
            sys.stderr.write(
                f"[unified_pre_tool] logging skipped, no project root: {exc} "
                f"(Issue #1726)\n"
            )
        except Exception:
            pass
        return None


def _log_deviation(file_name: str, tool_name: str, reason: str) -> None:
    """Append deviation to .claude/logs/deviations.jsonl for analytics."""
    try:
        import json as _json
        from datetime import datetime as _dt
        log_dir = _resolved_logs_dir()
        if log_dir is None:
            return
        log_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": _dt.now().isoformat(),
            "file": file_name,
            "tool": tool_name,
            "reason": reason,
            # #1171: sanitize untrusted env-var before writing to JSON log.
            "session_id": _resolve_session_id_safe(_session_id) or "unknown",
        }
        with open(log_dir / "deviations.jsonl", "a") as f:
            f.write(_json.dumps(entry) + "\n")
    except Exception:
        pass  # Never fail the hook for logging


def check_plan_critic_revise_gate(tool_name: str, tool_input: Dict) -> Tuple[str, str]:
    """
    Check plan-critic REVISE re-invocation gate (Issue #1417).
    
    Blocks implementer dispatch when plan_critic_verdict.json contains verdict=REVISE
    and no second planner completion exists since the verdict timestamp.
    
    Args:
        tool_name: Name of the tool being called
        tool_input: Tool input parameters
    
    Returns:
        Tuple of (decision, reason)
    """
    # Only check Agent/Task tool calls
    if tool_name not in AGENT_TOOL_NAMES:
        return ("allow", "Not an agent invocation")
    
    # Only check implementer dispatch
    target_agent = tool_input.get("subagent_type", "").strip().lower()
    if target_agent != "implementer":
        return ("allow", "Not implementer dispatch")
    
    # Check for plan_critic_verdict.json
    try:
        verdict_file = Path(PLAN_CRITIC_VERDICT_PATH)
        if not verdict_file.exists():
            return ("allow", "No plan-critic verdict file")
        
        with open(verdict_file, "r") as f:
            verdict_data = json.loads(f.read())
        
        verdict = verdict_data.get("verdict", "").upper()
        if verdict != "REVISE":
            return ("allow", f"Plan-critic verdict is {verdict}, not REVISE")
        
        # Get the verdict timestamp
        verdict_timestamp = verdict_data.get("timestamp")
        if not verdict_timestamp:
            return ("allow", "No timestamp in verdict file")
        
        # Parse timestamp to epoch
        from datetime import datetime
        try:
            # Try ISO format first
            if "T" in verdict_timestamp:
                verdict_dt = datetime.fromisoformat(verdict_timestamp.replace("Z", "+00:00"))
            else:
                # Fallback to other formats
                verdict_dt = datetime.strptime(verdict_timestamp, "%Y-%m-%d %H:%M:%S")
            verdict_epoch = verdict_dt.timestamp()
        except Exception:
            return ("allow", "Could not parse verdict timestamp")
        
        # Check if planner was re-invoked after the verdict
        from pipeline_completion_state import get_planner_completion_count
        
        session_id = _session_id or os.getenv("CLAUDE_SESSION_ID", "unknown")
        planner_count = get_planner_completion_count(session_id, verdict_epoch)
        
        if planner_count > 0:
            return ("allow", f"Planner re-invoked {planner_count} time(s) after REVISE verdict")
        
        # Block: REVISE verdict without planner re-invocation
        return (
            "deny",
            "BLOCKED: plan-critic returned REVISE verdict but planner was not re-invoked. "
            "The coordinator must pass the plan-critic feedback to the planner and re-invoke "
            "it before dispatching the implementer. See implement.md STEP 5.5b."
        )
        
    except Exception as e:
        # Fail open on any errors
        return ("allow", f"Error checking plan-critic gate: {str(e)}")



def validate_agent_authorization(tool_name: str, tool_input: Dict) -> Tuple[str, str]:
    """
    Validate agent authorization for code changes.

    Enforces /implement workflow for significant code changes.
    Enforcement level controlled by ENFORCEMENT_LEVEL env var:
    - off: always allow
    - warn: allow + log warning (default for backward compat)
    - suggest: ask (user-visible prompt) + include /implement suggestion in reason
    - block: deny significant changes outside pipeline

    Args:
        tool_name: Name of the tool being called
        tool_input: Tool input parameters

    Returns:
        Tuple of (decision, reason)
    """
    # Check if agent authorization is enabled
    enabled = os.getenv("PRE_TOOL_AGENT_AUTH", "true").lower() == "true"
    if not enabled:
        return ("allow", "Agent authorization disabled")

    # Check if pipeline is active (agent name or state file)
    if _is_pipeline_active():
        agent_name = _get_active_agent_name()
        # Issue #1467: an EXPLICIT escalated/blocked alignment verdict stops
        # pipeline agents too. Only the new STEP 2 path can produce a
        # present-but-disallowed verdict, so legacy/batch states (field absent)
        # are untouched. Do NOT "fix" this into a blanket reorder — batch
        # per-issue states lack explicitly_invoked and would all false-block.
        if agent_name in PIPELINE_AGENTS and tool_name in ("Write", "Edit"):
            _bad = _explicit_alignment_verdict_block()
            if _bad:
                _log_deviation(tool_input.get("file_path", "unknown"),
                               tool_name, "alignment_verdict_escalated")
                return ("deny", (
                    "ALIGNMENT GATE (Issue #1467): STEP 2 produced verdict "
                    f"'{_bad}'. Work is blocked until the scope/architecture "
                    "delta is resolved — answer the alignment question, update "
                    "PROJECT.md, or narrow the change."))
        if agent_name in PIPELINE_AGENTS:
            return ("allow", f"Pipeline agent '{agent_name}' authorized")
        impl_active = _is_explicit_implement_active()
        # Issue #585: Block ALL code writes before alignment passes
        if impl_active and tool_name in ("Write", "Edit", "Bash"):
            if not _has_alignment_passed():
                if _is_code_file_target(tool_name, tool_input):
                    _log_deviation(
                        tool_input.get("file_path", "unknown") if tool_name != "Bash"
                        else "bash_command",
                        tool_name,
                        "alignment_gate_not_passed",
                    )
                    return ("deny", (
                        "ALIGNMENT GATE: /implement is active but STEP 2 (PROJECT.md alignment) "
                        "has not passed yet. The coordinator must complete alignment validation "
                        "before any code changes are allowed. Complete STEP 2 first."
                    ))
        # Issue #528: If /implement was explicitly invoked, block coordinator code writes
        if impl_active and tool_name in ("Write", "Edit", "Bash"):
            # NOTE(#1177-followup): env-var read here may also be dead; audit deferred.
            level = os.getenv("ENFORCEMENT_LEVEL", "block").strip().lower()
            if level != "off" and _is_code_file_target(tool_name, tool_input):
                block_reason = (
                    "WORKFLOW ENFORCEMENT: /implement is active — code changes must be "
                    "made by pipeline agents (implementer, test-master, doc-master), "
                    "not the coordinator. Delegate this work to the appropriate agent."
                )
                _log_deviation(
                    tool_input.get("file_path", "unknown") if tool_name != "Bash"
                    else "bash_command",
                    tool_name,
                    "explicit_implement_coordinator_block",
                )
                return ("deny", block_reason)
        return ("allow", "Active /implement pipeline detected via state file")

    # Only check Edit, Write, and Bash tools
    if tool_name not in ("Edit", "Write", "Bash"):
        return ("allow", f"Tool '{tool_name}' not subject to workflow enforcement")

    # Get enforcement level (default: suggest - nudge toward /implement)
    level = os.getenv("ENFORCEMENT_LEVEL", "suggest").strip().lower()
    if level == "off":
        return ("allow", "Workflow enforcement disabled (level: off)")

    # Get file path and check exemptions
    file_path = tool_input.get("file_path", "")
    if _is_exempt_path(file_path):
        return ("allow", f"File exempt from workflow enforcement: {Path(file_path).name}")
    if file_path and Path(file_path).suffix.lower() not in CODE_EXTENSIONS:
        return ("allow", "Non-code file, no enforcement needed")

    # Analyze the change for significance
    if tool_name == "Edit":
        old_string = tool_input.get("old_string", "")
        new_string = tool_input.get("new_string", "")
        is_significant, reason, details = _has_significant_additions(old_string, new_string, file_path)
    elif tool_name == "Write":
        content = tool_input.get("content", "")
        is_significant, reason, details = _has_significant_additions("", content, file_path)
    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        if not command:
            return ("allow", "No command to check")
        # Git bypass detection (Issue #406)
        if "git" in command:
            is_bypass, bypass_reason = _detect_git_bypass(command)
            if is_bypass:
                return ("deny", f"GIT BYPASS BLOCKED: {bypass_reason}")
        target_files = _extract_bash_file_writes(command)
        if not target_files:
            return ("allow", "No file writes detected in Bash command")
        # Check each target file for code file enforcement
        for fp in target_files:
            if _is_exempt_path(fp):
                continue
            if Path(fp).suffix.lower() not in CODE_EXTENSIONS:
                continue
            # Code file write detected via Bash
            file_name = Path(fp).name
            tip = "Tip: /implement handles testing, review, and docs automatically."
            if level == "warn":
                import sys as _sys
                _sys.stderr.write(f"WARNING: Bash file write to code file: {file_name}\n")
                _sys.stderr.flush()
                _log_deviation(file_name, tool_name, "Bash file write to code file")
                return ("allow", f"Bash file write detected ({file_name}), allowed at WARN level")
            elif level == "suggest":
                _log_deviation(file_name, tool_name, "Bash file write to code file")
                return ("ask", f"Bash file write to code file {file_name}. {tip}")
            elif level == "block":
                return ("deny", f"WORKFLOW ENFORCEMENT: Bash file write to code file {file_name}. "
                        f"Significant code changes require /implement workflow. {tip}")
        return ("allow", "Bash command writes only to non-code/exempt files")
    else:
        return ("allow", f"Tool '{tool_name}' allowed")

    if not is_significant:
        return ("allow", "Minor edit, no significant code additions detected")

    file_name = Path(file_path).name if file_path else "unknown"
    tip = "Tip: /implement handles testing, review, and docs automatically."

    if level == "warn":
        import sys as _sys
        _sys.stderr.write(f"WARNING: {reason} in {file_name}\n")
        _sys.stderr.flush()
        _log_deviation(file_name, tool_name, reason)
        return ("allow", f"{reason} in {file_name}, allowed at WARN level")

    elif level == "suggest":
        _log_deviation(file_name, tool_name, reason)
        return ("ask", f"{reason} in {file_name}. "
                f"Use /implement for this change:\n"
                f"- /implement \"description\"\n"
                f"- /implement --quick \"description\" (skip full pipeline)\n"
                f"- /implement #<issue-number>")

    elif level == "block":
        return ("deny", f"WORKFLOW ENFORCEMENT: {reason} in {file_name}. "
                f"Significant code changes require /implement workflow. "
                f"STOP coding directly and run: /implement --quick \"description\"\n"
                f"Use /implement for this change:\n"
                f"- /implement \"description\"\n"
                f"- /implement --quick \"description\" (skip full pipeline)\n"
                f"- /implement #<issue-number>")

    return ("allow", f"Tool '{tool_name}' allowed")


def validate_batch_permission(tool_name: str, tool_input: Dict) -> Tuple[str, str]:
    """
    Validate batch permission for auto-approval.

    Args:
        tool_name: Name of the tool being called
        tool_input: Tool input parameters

    Returns:
        Tuple of (decision, reason)
        - decision: "allow", "deny", or "ask"
        - reason: Human-readable reason for decision
    """
    # Check if batch permission is enabled
    enabled = os.getenv("PRE_TOOL_BATCH_PERMISSION", "false").lower() == "true"
    if not enabled:
        return ("allow", "Batch permission disabled")

    try:
        # Try to import permission classifier
        try:
            from permission_classifier import PermissionClassifier, PermissionLevel

            # Classify operation
            classifier = PermissionClassifier()
            level = classifier.classify(tool_name, tool_input)

            if level == PermissionLevel.SAFE:
                return ("allow", f"Batch permission: SAFE operation auto-approved")
            elif level == PermissionLevel.BOUNDARY:
                return ("allow", f"Batch permission: BOUNDARY operation allowed")
            else:  # PermissionLevel.SENSITIVE
                return ("ask", f"Batch permission: SENSITIVE operation requires user approval")

        except ImportError:
            # Permission classifier not available - allow (don't block)
            return ("allow", "Batch permission classifier unavailable")

    except Exception as e:
        # Error in validation - allow (don't block on errors)
        return ("allow", f"Batch permission error: {e}")


def combine_decisions(validators_results: List[Tuple[str, str, str]]) -> Tuple[str, str]:
    """
    Combine multiple validator decisions into single decision.

    Decision Logic:
    - If ANY validator returns "deny" → "deny" (block operation)
    - If ALL validators return "allow" → "allow" (approve operation)
    - Otherwise → "ask" (prompt user)

    Args:
        validators_results: List of (validator_name, decision, reason) tuples

    Returns:
        Tuple of (final_decision, combined_reason)
    """
    decisions = []
    reasons = []

    for validator_name, decision, reason in validators_results:
        decisions.append(decision)
        reasons.append(f"[{validator_name}] {reason}")

    # If ANY deny → deny
    if "deny" in decisions:
        deny_reasons = [r for v, d, r in validators_results if d == "deny"]
        return ("deny", "; ".join(deny_reasons))

    # If ALL allow → allow
    if all(d == "allow" for d in decisions):
        return ("allow", "; ".join(reasons))

    # Otherwise → ask
    ask_reasons = [r for v, d, r in validators_results if d == "ask"]
    if ask_reasons:
        return ("ask", "; ".join(ask_reasons))
    else:
        return ("ask", "; ".join(reasons))


def _log_write_gate_bypass_consumed(file_path: str, skip_file: Path) -> None:
    """Log consumption of write-gate operator bypass sentinel (Issue #1356).
    
    Args:
        file_path: The target file being written/edited (empty string for Bash context).
        skip_file: Path to the sentinel file.
    """
    try:
        import json as _json
        import time
        from datetime import datetime as _dt, timezone as _tz
        
        # Get the agent identity
        agent_name = _get_active_agent_name()
        if not agent_name:
            agent_name = "main"  # Default to main if no agent context
        
        # Calculate sentinel age
        sentinel_age_seconds = -1.0
        try:
            sentinel_mtime = skip_file.stat().st_mtime
            sentinel_age_seconds = time.time() - sentinel_mtime
        except Exception:
            pass

        # Scoped-escape reason (Issue #1408): prefer the sentinel file's own
        # contents (operator can `echo "why" > /tmp/skip_write_pipeline_gate`),
        # then the $WRITE_GATE_BYPASS_REASON env var, else "unspecified". This
        # makes each one-shot bypass auditable WITHOUT introducing any
        # session-wide off switch (.claude/.bypass remains the blanket
        # kill-switch). Logged unconditionally; the bypass stays one-shot.
        reason = ""
        try:
            reason = skip_file.read_text(errors="replace").strip()[:500]
        except Exception:
            reason = ""
        if not reason:
            reason = os.environ.get("WRITE_GATE_BYPASS_REASON", "").strip()[:500]
        if not reason:
            reason = "unspecified"

        # Prepare log entry (Issue #1726: root-anchored, never cwd-anchored —
        # a bypass-consumption record hidden in a stray tree is an unauditable
        # bypass).
        _logs_dir = _resolved_logs_dir()
        if _logs_dir is None:
            return
        log_dir = _logs_dir / "activity"
        log_dir.mkdir(parents=True, exist_ok=True)
        date_str = _dt.now().strftime("%Y-%m-%d")

        entry = {
            "timestamp": _dt.now(_tz.utc).isoformat(),
            "event": "write_gate_operator_bypass_consumed",
            "agent": agent_name,
            "file_path": file_path or "(bash context)",
            "reason": reason,
            "sentinel_age_seconds": round(sentinel_age_seconds, 2) if sentinel_age_seconds >= 0 else -1,
            "session_id": _resolve_session_id_safe(_session_id) or "unknown",
        }
        
        # Write to activity log
        with open(log_dir / f"{date_str}.jsonl", "a") as f:
            f.write(_json.dumps(entry, separators=(",", ":")) + "\n")
    except Exception:
        pass  # Fail silently to not disrupt the bypass flow


def _log_write_gate_bypass_deferred(file_path: str, call_key: str) -> None:
    """Log a write-gate bypass GRANTED by deferring to a sibling's receipt.

    Companion to :func:`_log_write_gate_bypass_consumed`, deliberately under a
    DISTINCT event name. Issue #1641 made consumption idempotent per logical
    tool call: one copy of the fan-out spends the token and logs
    ``write_gate_operator_bypass_consumed``, and every other copy grants the
    same write by honouring that copy's receipt. Those deferred grants were
    recorded nowhere — three paths in :func:`_consume_write_gate_bypass`
    returned True without reaching any logger — so a permitted write left no
    trace, which is the one thing this project's controls exist to prevent.

    Folding deferrals into the consumed event instead would have been wrong: a
    single token must still produce exactly one ``..._consumed`` record however
    many copies Claude Code launches.

    Args:
        file_path: The target file being written/edited. Empty string when no
            specific path applies.
        call_key: Digest identifying the logical tool call, from
            :func:`_write_gate_bypass_call_key`. Recorded so a deferral can be
            tied back to the consumption it honoured.
    """
    try:
        import json as _json
        from datetime import datetime as _dt, timezone as _tz

        agent_name = _get_active_agent_name() or "main"

        # Identify the copy whose consumption we are honouring. Both fields are
        # best-effort: the winner may sweep its own receipt between our grant
        # and this write. A grant with an unknown winner is still recorded —
        # an incomplete record beats a missing one.
        winner_pid = -1
        receipt_age_seconds = -1.0
        try:
            receipt = _write_gate_bypass_receipt_path(call_key)
            receipt_age_seconds = time.time() - receipt.stat().st_mtime
            record = _json.loads(receipt.read_text())
            if isinstance(record, dict) and isinstance(record.get("pid"), int):
                winner_pid = int(record["pid"])
        except Exception:
            pass

        # Issue #1726: root-anchored, never cwd-anchored.
        _logs_dir = _resolved_logs_dir()
        if _logs_dir is None:
            return
        log_dir = _logs_dir / "activity"
        log_dir.mkdir(parents=True, exist_ok=True)
        date_str = _dt.now().strftime("%Y-%m-%d")

        entry = {
            "timestamp": _dt.now(_tz.utc).isoformat(),
            "event": "write_gate_operator_bypass_deferred",
            "agent": agent_name,
            "file_path": file_path or "(bash context)",
            "call_key": call_key,
            "winner_pid": winner_pid,
            "pid": os.getpid(),
            "receipt_age_seconds": (
                round(receipt_age_seconds, 2) if receipt_age_seconds >= 0 else -1
            ),
            "session_id": _resolve_session_id_safe(_session_id) or "unknown",
        }

        with open(log_dir / f"{date_str}.jsonl", "a") as f:
            f.write(_json.dumps(entry, separators=(",", ":")) + "\n")
    except Exception:
        pass  # Fail silently — auditing must never disrupt the grant it records


def _log_pretool_activity(tool_name: str, tool_input: Dict, decision: str, reason: str) -> None:
    """Log PreToolUse decision to shared activity log."""
    try:
        import json as _json
        from datetime import datetime as _dt, timezone as _tz
        _logs_dir = _resolved_logs_dir()
        if _logs_dir is None:
            return
        log_dir = _logs_dir / "activity"
        log_dir.mkdir(parents=True, exist_ok=True)
        date_str = _dt.now().strftime("%Y-%m-%d")

        # Build a compact summary of what's being done
        summary = {"tool": tool_name}
        if tool_name in ("Edit", "Write"):
            summary["file"] = tool_input.get("file_path", "")
        elif tool_name == "Bash":
            cmd = tool_input.get("command", "")
            summary["command"] = cmd[:200] if len(cmd) > 200 else cmd
        elif tool_name in ("Task", "Agent"):
            summary["subagent"] = tool_input.get("subagent_type", "")
            summary["description"] = tool_input.get("description", "")
        elif tool_name == "Skill":
            summary["skill"] = tool_input.get("skill", "")

        entry = {
            "timestamp": _dt.now(_tz.utc).isoformat(),
            "hook": "PreToolUse",
            "decision": decision,
            "reason": reason[:300],
            # #1171: sanitize untrusted env-var before writing to JSON log.
            "session_id": _resolve_session_id_safe(_session_id) or "unknown",
            "agent": _get_active_agent_name() or "main",
            **summary,
        }
        with open(log_dir / f"{date_str}.jsonl", "a") as f:
            f.write(_json.dumps(entry, separators=(",", ":")) + "\n")
    except Exception:
        pass


@block_event_decorator("unified_pre_tool.py")
def output_decision(decision: str, reason: str, *, system_message: str = ""):
    """Output the hook decision in required format.

    Args:
        decision: Permission decision ("allow", "deny", or "ask")
        reason: Human-readable reason for the decision
        system_message: Optional message injected into model context (visible to user)

    Telemetry (Issue #972): when ``decision == "deny"``, the
    ``block_event_decorator`` appends one structured JSONL row to
    ``.claude/logs/hook-blocks.jsonl`` so the per-hook block count and
    deny-reason text can be reconstructed without grepping session
    transcripts. The decorator is idempotent and never raises.
    """
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason
        }
    }
    if system_message:
        output["systemMessage"] = system_message
    print(json.dumps(output))


DENY_CACHE_PATH = "/tmp/.claude_deny_cache.jsonl"

# Agent denial state for blocking coordinator workaround edits (Issue #750)
AGENT_DENY_STATE_DIR = "/tmp"
AGENT_DENY_TTL = 300  # seconds


def _sanitize_session_id(raw: str) -> str:
    """Sanitize session_id for safe use in filesystem paths.

    Defense-in-depth layers:
    1. Strip null bytes (prevents C-layer truncation bypass)
    2. Unicode NFKC normalization (prevents lookalike characters to ASCII equivalents)
    3. Allowlist regex: replace non-[a-zA-Z0-9_-] with underscore (OWASP recommended)
    4. Cap length at 128 characters (prevents PATH_MAX exhaustion)

    Args:
        raw: The raw session_id string from hook input_data dictionary.

    Returns:
        A filesystem-safe session_id string containing only [a-zA-Z0-9_-].
        Returns 'unknown' if input is empty or None after sanitization.
    """
    import re as _re
    import unicodedata
    if not isinstance(raw, str):
        raw = str(raw) if raw is not None else "unknown"
    # Layer 1: Strip null bytes — must be first before any regex processing
    raw = raw.replace('\x00', '')
    # Layer 2: Unicode NFKC normalization — collapse lookalike characters to ASCII equivalents
    raw = unicodedata.normalize('NFKC', raw)
    # Layer 3: Allowlist regex — only permit alphanumeric, underscore, hyphen characters
    sanitized = _re.sub(r'[^a-zA-Z0-9_-]', '_', raw)
    # Layer 4: Length cap — prevent PATH_MAX exhaustion on macOS (1024) and Linux (4096)
    sanitized = sanitized[:128]
    return sanitized if sanitized else 'unknown'


def _resolve_session_id_safe(input_session_id: Optional[str]) -> Optional[str]:
    """Resolve and sanitize the active session id.

    Centralizes the "read CLAUDE_SESSION_ID env var, fall back to the
    already-sanitized module-level ``_session_id``, then sanitize the
    result" pattern that was previously duplicated at 8 sites. The env
    var is untrusted process input — without sanitizing here, the raw
    value would flow into filesystem paths and HMAC computations.

    Args:
        input_session_id: Fallback session id when the env var is unset
            (typically ``_session_id`` from the hook's per-invocation
            scope, which is itself already sanitized at line 4856).

    Returns:
        A sanitized session id string, OR ``None`` if the resolved value
        is empty or the literal ``"unknown"`` after sanitization. Callers
        that need ``"unknown"`` semantics use ``... or "unknown"`` at the
        call site to preserve prior behavior.

    Issues: #1171
    """
    env_raw = os.getenv("CLAUDE_SESSION_ID") or input_session_id or ""
    sanitized = _sanitize_session_id(env_raw)
    return sanitized if sanitized and sanitized != "unknown" else None


def _update_deny_cache(file_path: str) -> None:
    """Record a denied file path in the deny cache for escalation tracking.

    Appends a JSON line with the path and current timestamp.
    Prunes stale entries (>300s) on every 10th write, capped at 500 lines.
    Failures are silently ignored — deny cache must never block legitimate commands.

    Args:
        file_path: The file path that was denied.
    """
    import json as _json
    import time as _time
    _PRUNE_MAX_AGE = 300  # seconds
    _PRUNE_MAX_LINES = 500
    try:
        with open(DENY_CACHE_PATH, "a") as f:
            entry = {"path": file_path, "timestamp": _time.time()}
            f.write(_json.dumps(entry) + "\n")
        # Prune on every 10th write (check line count to decide)
        cache_p = Path(DENY_CACHE_PATH)
        if cache_p.exists():
            all_lines = cache_p.read_text().splitlines()
            if len(all_lines) % 10 == 0 or len(all_lines) > _PRUNE_MAX_LINES:
                now = _time.time()
                cutoff = now - _PRUNE_MAX_AGE
                kept = []
                for raw_line in all_lines:
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    try:
                        parsed = json.loads(raw_line)
                        if parsed.get("timestamp", 0) >= cutoff:
                            kept.append(raw_line)
                    except (ValueError, KeyError):
                        continue
                # Cap at max lines (keep most recent)
                if len(kept) > _PRUNE_MAX_LINES:
                    kept = kept[-_PRUNE_MAX_LINES:]
                cache_p.write_text("\n".join(kept) + "\n" if kept else "")
    except Exception:
        pass  # Never fail the hook for cache writes


def _check_deny_cache(file_path: str, *, window_seconds: int = 60) -> bool:
    """Check if a file path was denied within the recent time window.

    Used to detect repeated bypass attempts and escalate messaging.
    Failures return False — deny cache must never block legitimate commands.

    Args:
        file_path: The file path to check.
        window_seconds: How far back to look in seconds (default: 60).

    Returns:
        True if the path was denied within the window, False otherwise.
    """
    import json as _json
    import time as _time
    try:
        cache_path = Path(DENY_CACHE_PATH)
        if not cache_path.exists():
            return False
        now = _time.time()
        cutoff = now - window_seconds
        with open(cache_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("timestamp", 0) < cutoff:
                        continue
                    cached_path = entry.get("path", "")
                    # Exact match
                    if cached_path == file_path:
                        return True
                    # Basename fallback for cross-tool detection (Issue #803):
                    # Write may deny "/Users/.../agents/foo.md" while Bash uses
                    # "agents/foo.md" — match on basename as fallback.
                    if cached_path and file_path:
                        try:
                            if Path(cached_path).name == Path(file_path).name:
                                return True
                        except Exception:
                            pass
                except (ValueError, KeyError):
                    continue
    except Exception:
        pass  # Never fail the hook for cache reads
    return False


def _record_agent_denial(
    agent_type: str,
    *,
    block_event_id: "Optional[str]" = None,
    block_timestamp_iso: "Optional[str]" = None,
) -> None:
    """Record that an agent invocation was denied by prompt integrity (Issue #750).

    Writes a JSON file keyed by session_id so subsequent Write/Edit calls
    can detect the workaround pattern and block substantive edits to
    protected infrastructure.

    Atomic write: writes to a .tmp file first, then os.replace.
    Fail-open: exceptions are silently ignored.

    Args:
        agent_type: The agent type that was denied (e.g. 'implementer').
        block_event_id: Optional uuid4 identifier paired with the
            ``prompt_integrity_block`` telemetry row (Issue #1178). When set,
            the recovery emission joins back to the original block via this id.
        block_timestamp_iso: Optional ISO-8601 UTC timestamp captured at
            block emission time (Issue #1178). When set, the recovery
            emission computes block->recovery latency from this anchor.
    """
    import json as _json
    import tempfile as _tempfile
    import time as _time
    try:
        state = {
            "agent_type": agent_type,
            "timestamp": _time.time(),
            "session_id": _session_id,
        }
        # Issue #1178: telemetry fields are additive. _check_agent_denial only
        # reads agent_type/session_id/timestamp; the new helpers below read
        # the full dict. Unknown-key safety is verified by regression test.
        if block_event_id is not None:
            state["block_event_id"] = block_event_id
        if block_timestamp_iso is not None:
            state["block_timestamp_iso"] = block_timestamp_iso
        state_path = os.path.join(AGENT_DENY_STATE_DIR, f"adev-agent-deny-{_session_id}.json")
        # Path confinement: verify resolved path stays within AGENT_DENY_STATE_DIR
        resolved = os.path.realpath(state_path)
        base = os.path.realpath(AGENT_DENY_STATE_DIR)
        if not resolved.startswith(base + os.sep) and resolved != base:
            return  # Path escapes base directory — fail-open, silently refuse to write
        # Atomic creation via O_CREAT|O_EXCL prevents symlink attacks (replaces predictable .tmp)
        tmp_fd, tmp_path = _tempfile.mkstemp(dir=AGENT_DENY_STATE_DIR, suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w") as f:
                _json.dump(state, f)
            os.replace(tmp_path, state_path)
        except OSError:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except Exception:
        pass  # Fail-open: never block on state file errors


def _check_agent_denial(*, window_seconds: int = AGENT_DENY_TTL) -> "Optional[str]":
    """Check whether an agent invocation was recently denied (Issue #750).

    Returns the agent_type if a denial record exists within the time window
    and the session_id matches, otherwise None. Fail-open on all errors.

    Args:
        window_seconds: How far back to look for denials (default: AGENT_DENY_TTL).

    Returns:
        The denied agent_type string, or None if no recent denial.
    """
    import json as _json
    import time as _time
    try:
        state_path = os.path.join(AGENT_DENY_STATE_DIR, f"adev-agent-deny-{_session_id}.json")
        # Path confinement: verify resolved path stays within AGENT_DENY_STATE_DIR
        resolved = os.path.realpath(state_path)
        base = os.path.realpath(AGENT_DENY_STATE_DIR)
        if not resolved.startswith(base + os.sep) and resolved != base:
            return None  # Path escapes base directory — fail-open, refuse to read
        if not os.path.exists(state_path):
            return None
        with open(state_path) as f:
            state = _json.load(f)
        if state.get("session_id") != _session_id:
            # Issue #1051: deny file from a different session is orphaned — clean it up
            try:
                os.unlink(state_path)
            except OSError:
                pass  # fail-open — cleanup failure must not block agents
            return None
        if _time.time() - state.get("timestamp", 0) > window_seconds:
            # Issue #1051: stale deny file beyond TTL — clean it up so subsequent
            # agent invocations are not blocked by manual `rm` requirements
            try:
                os.unlink(state_path)
            except OSError:
                pass  # fail-open — cleanup failure must not block agents
            return None
        return state.get("agent_type", "")
    except Exception:
        return None  # Fail-open


def _read_agent_denial_record() -> "Optional[Dict[str, Any]]":
    """Read the full agent-denial state dict for the current session (Issue #1178).

    Mirrors ``_check_agent_denial`` for path resolution and session-id
    matching, but returns the full state dict (including #1178 telemetry
    fields ``block_event_id`` and ``block_timestamp_iso``) instead of just
    the agent_type. Used by the recovery emission path to compute
    block->recovery latency.

    Fail-open: returns None on missing file, parse error, session mismatch,
    or path-confinement violation.

    Returns:
        The full state dict, or None on any error / no record.
    """
    import json as _json
    try:
        state_path = os.path.join(
            AGENT_DENY_STATE_DIR, f"adev-agent-deny-{_session_id}.json"
        )
        resolved = os.path.realpath(state_path)
        base = os.path.realpath(AGENT_DENY_STATE_DIR)
        if not resolved.startswith(base + os.sep) and resolved != base:
            return None
        if not os.path.exists(state_path):
            return None
        with open(state_path) as f:
            state = _json.load(f)
        if not isinstance(state, dict):
            return None
        if state.get("session_id") != _session_id:
            return None
        return state
    except Exception:
        return None


def _consume_agent_denial_record() -> None:
    """Delete the agent-denial state file after a successful recovery (Issue #1178).

    Enforces the single-emit invariant: once a ``prompt_integrity_recovery``
    event has been written for a given block, the denial state must be
    cleared so subsequent allow-path invocations do not re-emit.

    Fail-open: silently ignores OSError (e.g. file already removed).
    """
    try:
        state_path = os.path.join(
            AGENT_DENY_STATE_DIR, f"adev-agent-deny-{_session_id}.json"
        )
        resolved = os.path.realpath(state_path)
        base = os.path.realpath(AGENT_DENY_STATE_DIR)
        if not resolved.startswith(base + os.sep) and resolved != base:
            return
        if os.path.exists(state_path):
            os.unlink(state_path)
    except Exception:
        pass


# Issue #1178: regex for extracting the three numerics from a typical
# prompt-integrity deny reason, e.g.
#   "Prompt for 'researcher-local' shrank 27.6% from baseline (399 words -> 289 words)"
# Capture groups: (1) shrinkage percent, (2) baseline words, (3) current words.
# The arrow byte may be ASCII "->", a literal unicode "->", or a UTF-8 right-arrow.
_PI_NUMERICS_RE = re.compile(
    r"shrank\s+([0-9]+(?:\.[0-9]+)?)\s*%[^()]*\(\s*([0-9]+)\s*words\s*[^0-9]+\s*([0-9]+)\s*words",
    re.IGNORECASE,
)


def _parse_pi_numerics(
    reason: str,
) -> "Tuple[Optional[float], Optional[int], Optional[int]]":
    """Extract (shrinkage_pct, baseline_words, current_words) from a PI reason (Issue #1178).

    Fail-open: returns ``(None, None, None)`` on any parse failure. Never raises.

    Args:
        reason: The deny reason string emitted by ``validate_prompt_integrity``.

    Returns:
        Tuple of (shrinkage_pct: float|None, baseline_words: int|None,
        current_words: int|None). Any element that could not be parsed is None.
    """
    try:
        if not isinstance(reason, str):
            return (None, None, None)
        m = _PI_NUMERICS_RE.search(reason)
        if m is None:
            return (None, None, None)
        try:
            pct = float(m.group(1))
        except (TypeError, ValueError):
            pct = None
        try:
            baseline = int(m.group(2))
        except (TypeError, ValueError):
            baseline = None
        try:
            current = int(m.group(3))
        except (TypeError, ValueError):
            current = None
        return (pct, baseline, current)
    except Exception:
        return (None, None, None)


def _emit_prompt_integrity_event(
    event_type: str,
    *,
    agent_type: str,
    block_event_id: str,
    **kwargs: "Any",
) -> None:
    """Emit prompt-integrity telemetry row to hook-blocks.jsonl (Issue #1178).

    Thin wrapper around ``log_block_event`` with privacy gating: the
    ``block_reason_detail`` field is stripped unless the
    ``HOOK_TELEMETRY_VERBOSE=1`` env var is set. Never raises — telemetry
    must never break the underlying hook decision path.

    Args:
        event_type: One of ``_PI_BLOCK_EVENT_TYPE`` or
            ``_PI_RECOVERY_EVENT_TYPE``.
        agent_type: The agent type involved (e.g. ``"researcher-local"``).
        block_event_id: uuid4 string joining the block and recovery rows.
        **kwargs: Additional fields to include in the metadata payload.
    """
    try:
        metadata = {
            "event_type": event_type,
            "block_event_id": block_event_id,
            "agent_type": agent_type,
            "session_id": _session_id,
        }
        metadata.update(kwargs)
        if os.environ.get("HOOK_TELEMETRY_VERBOSE") != "1":
            metadata.pop("block_reason_detail", None)
        log_block_event(
            hook_name="unified_pre_tool.py",
            decision_shape="dict",
            reason=f"{event_type}:{agent_type}",
            metadata=metadata,
        )
    except Exception:
        # Telemetry must never break the hook decision path.
        pass


def _check_bash_state_deletion(command: str) -> "Optional[Tuple[str, str]]":
    """Check if a Bash command deletes or truncates pipeline state files.

    Detects rm, unlink, truncate, redirect-to-empty, and python os.remove/os.unlink/Path.unlink
    targeting pipeline state files. Pure function: caller decides whether to block based on
    pipeline-active status.

    Args:
        command: The Bash command string to inspect.

    Returns:
        None if no state file is targeted, or a tuple of (file_path, reason) if detected.
    """
    import re

    # Protected state file patterns
    # Issue #1206: include both the legacy /tmp literal (orphan protection for
    # pre-#1206 sessions) and the new per-repo path via LEGACY_SENTINEL_LITERALS.
    _STATE_FILE_PATTERNS = [
        *LEGACY_SENTINEL_LITERALS,
        "/tmp/.claude_deny_cache.jsonl",
    ]
    _STATE_FILE_GLOB_PREFIXES = [
        "/tmp/pipeline_completion_state_",
        "/tmp/pipeline_secrets/",
    ]

    # Also protect whatever PIPELINE_STATE_FILE env var points to
    _env_state = os.environ.get("PIPELINE_STATE_FILE", "")
    if _env_state:
        _STATE_FILE_PATTERNS.append(_env_state)

    def _is_state_file(path: str) -> bool:
        """Check if a path matches a protected state file."""
        path = path.strip().strip("'\"")
        if not path:
            return False
        for pattern in _STATE_FILE_PATTERNS:
            if path == pattern or path.endswith("/" + Path(pattern).name):
                return True
        for prefix in _STATE_FILE_GLOB_PREFIXES:
            if path.startswith(prefix):
                return True
        # Also check for $PIPELINE_STATE_FILE variable reference
        if "$PIPELINE_STATE_FILE" in path or "${PIPELINE_STATE_FILE}" in path:
            return True
        return False

    # Strip heredoc bodies and --body/--message quoted args so that text content
    # (e.g. issue descriptions mentioning deletion commands) is not scanned.
    # Issue #866: false positive when gh issue create heredoc body mentions rm.
    # Issue #1153 (Phase 2): inline regex unified with shared heredoc_utils.

    # Strip heredoc bodies: <<'EOF'...EOF, <<EOF...EOF, <<"EOF"...EOF, <<-EOF...EOF
    command = _strip_heredoc_content(command)

    # Strip --body '...' / --body "..." / --body "$(cat ...)" argument values
    _body_pat = r"""--body\s+(?:'[^']*'|"[^"]*"|\$\([^)]*\))"""
    command = re.sub(_body_pat, '--body ""', command)

    # Strip --message / -m quoted argument values
    _msg_pat = r"""(?:--message|-m)\s+(?:'[^']*'|"[^"]*")"""
    command = re.sub(_msg_pat, '-m ""', command)

    try:
        # 1. rm [-flags] <path>
        rm_pattern = r'\brm\s+(?:-[^\s]+\s+)*([^\s;&|]+)'
        for match in re.finditer(rm_pattern, command):
            target = match.group(1).strip().strip("'\"")
            if _is_state_file(target):
                return (target, "Pipeline state file deletion blocked during active pipeline (Issue #803)")

        # 2. unlink <path>
        unlink_pattern = r'\bunlink\s+([^\s;&|]+)'
        for match in re.finditer(unlink_pattern, command):
            target = match.group(1).strip().strip("'\"")
            if _is_state_file(target):
                return (target, "Pipeline state file deletion blocked during active pipeline (Issue #803)")

        # 3. truncate [-flags [value]] <path>
        # Handle: truncate -s 0 /path, truncate --size=0 /path, truncate /path
        truncate_pattern = r'\btruncate\s+(?:(?:-\w+\s+\S+\s+)|(?:--\w+=\S+\s+))*([^\s;&|]+)'
        for match in re.finditer(truncate_pattern, command):
            target = match.group(1).strip().strip("'\"")
            if _is_state_file(target):
                return (target, "Pipeline state file deletion blocked during active pipeline (Issue #803)")

        # 4. Redirect-to-empty: > /path/to/state/file (with nothing before >)
        empty_redirect_pattern = r'(?:^|;|&&|\|\|)\s*>\s*([^\s;&|]+)'
        for match in re.finditer(empty_redirect_pattern, command):
            target = match.group(1).strip().strip("'\"")
            if _is_state_file(target):
                return (target, "Pipeline state file deletion blocked during active pipeline (Issue #803)")

        # 5. python3 -c with os.remove/os.unlink/Path.unlink
        py_delete_patterns = [
            r'os\.remove\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
            r'os\.unlink\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
            r'Path\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)\.unlink',
        ]
        for py_pat in py_delete_patterns:
            for match in re.finditer(py_pat, command, re.IGNORECASE):
                target = match.group(1).strip()
                if _is_state_file(target):
                    return (target, "Pipeline state file deletion blocked during active pipeline (Issue #803)")

    except Exception:
        pass  # Fail-open: never block legitimate commands on detection errors

    return None


def _check_rm_rf_unresolved_vars(command: str) -> "Optional[Tuple[str, str]]":
    """Detect `rm -rf` (or `rm -f`/`rm -Rf` etc.) with unquoted variable expansion.

    Catastrophic-prevention guard (Issue #1008). When a variable used as the
    deletion target is unset or empty, `rm -rf $VAR/subpath` expands to
    `rm -rf /subpath` — which can erase critical filesystem paths. Quoting the
    variable (`"$VAR"`) makes the empty case safe (`rm -rf ""` is a harmless
    no-op), so the rule is: flag UNQUOTED variable expansions only.

    Detection scope:
        - `rm -rf $VAR` / `rm -rf ${VAR}` — unquoted variable
        - `rm -rf $VAR/anything` — unquoted variable with suffix
        - `rm -f $VAR` — single-file `rm -f` with unquoted var is also dangerous
        - `rm -Rf $VAR`, `rm -fr $VAR`, etc. — any combo of [rRfF] flags

    Safe (NOT flagged):
        - `rm -rf "$VAR"` / `rm -rf "${VAR}"` — quoted variable
        - `rm -rf /tmp/foo` — literal path
        - `ls -la` — not an `rm` command
        - heredoc bodies and `--body "..."` quoted args (stripped before scanning)

    Args:
        command: The Bash command string to inspect.

    Returns:
        ``None`` if the command is safe, or a tuple of ``(decision, reason)``
        where ``decision == "deny"`` and ``reason`` carries the user-facing
        message. The tuple shape matches the deny-pipeline contract used by
        the caller in ``main()``.
    """
    import re

    try:
        # Strip heredoc bodies and --body/--message quoted args so user-supplied
        # text content (issue descriptions, PR bodies, etc.) doesn't trigger a
        # false positive. Mirrors the sanitization in _check_bash_state_deletion.
        # Issue #1153 (Phase 2): inline regex unified with shared heredoc_utils.
        scrubbed = _strip_heredoc_content(command)

        _body_pat = r"""--body\s+(?:'[^']*'|"[^"]*"|\$\([^)]*\))"""
        scrubbed = re.sub(_body_pat, '--body ""', scrubbed)

        _msg_pat = r"""(?:--message|-m)\s+(?:'[^']*'|"[^"]*")"""
        scrubbed = re.sub(_msg_pat, '-m ""', scrubbed)

        # Core detection: `rm` + one or more flag tokens (each containing at
        # least one of r/R/f/F) + a bareword variable expansion.
        #
        # The negative lookahead `(?!["\'])` is the safety hinge: if the next
        # character is a quote, the variable is being expanded safely and we
        # do NOT flag.
        rm_rf_var_pattern = (
            r"\brm\s+(?:-[a-zA-Z]*[rRfF][a-zA-Z]*\s+)+"
            r"(?![\"'])"
            r"(\$\{?[A-Za-z_][A-Za-z0-9_]*\}?)"
        )
        match = re.search(rm_rf_var_pattern, scrubbed)
        if match is not None:
            var_expr = match.group(1)
            reason = (
                f"BLOCKED: rm -rf with unquoted variable expansion detected: "
                f"{var_expr}. If the variable is unset or empty, the command "
                f"expands to a catastrophic deletion (e.g. `rm -rf /subpath` "
                f"or `rm -rf /`). Quote the variable to make the empty case "
                f"a safe no-op: rm -rf \"{var_expr}\". "
                f"REQUIRED NEXT ACTION: Re-issue the command with the "
                f"variable double-quoted."
            )
            return ("deny", reason)
    except Exception:
        pass  # Fail-open: never block legitimate commands on detection errors

    return None

def _check_worktree_path_boundary(
    tool_name: str,
    tool_input: Dict[str, Any],
) -> "Optional[Tuple[str, str]]":
    """Check if Write/Edit target path escapes worktree boundary.

    Issue #1390: doc-master writes to main repo path instead of batch worktree.
    When operating in a worktree (.worktrees/batch-*), Write/Edit must target
    paths within that worktree, not escape to the main repo.

    Returns:
        None if allowed (non-worktree mode or target inside worktree)
        (file_path, reason) if denied (worktree escape detected)
    """
    # Only check Write/Edit tools
    if tool_name not in ("Write", "Edit"):
        return None
    
    # Only active in worktree mode
    cwd = os.getcwd()
    if ".worktrees/batch-" not in cwd:
        return None
    
    # Get target file path
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return None
    
    try:
        # Resolve to absolute paths for comparison
        target_path = Path(file_path).resolve()
        worktree_root = Path(cwd).resolve()
        
        # Find the actual worktree root (go up to .worktrees/batch-* level)
        current = worktree_root
        while current != current.parent:
            if current.name.startswith("batch-") and current.parent.name == ".worktrees":
                worktree_root = current
                break
            current = current.parent
        
        # Check if target is within worktree boundary
        try:
            target_path.relative_to(worktree_root)
            # Target is inside worktree - allow
            return None
        except ValueError:
            # Target is outside worktree - deny
            violation_path = str(target_path)
            reason = (
                f"WORKTREE BOUNDARY VIOLATION: Cannot write to '{violation_path}' "
                f"from worktree '{worktree_root}'. Write/Edit operations in batch "
                f"worktrees must target paths within the worktree. "
                f"(Issue #1390)"
            )
            return (violation_path, reason)
    except Exception:
        # Fail open on errors
        return None



def _check_spec_test_deletion_scope(file_path: str) -> "Optional[Tuple[str, str]]":
    """Check if a spec validation test deletion is outside the current batch scope.

    Spec validation tests (tests/spec_validation/test_spec_issue{N}_*.py) are
    scoped to the issue that created them. Deleting a spec test from a different
    issue is blocked unless the escape hatch env var is set.

    Args:
        file_path: Path to the file being deleted or overwritten.

    Returns:
        None if the operation is allowed, or (file_path, block_reason) if blocked.
    """
    import re

    try:
        # Escape hatch
        skip_guard = os.getenv("SKIP_SPEC_DELETION_GUARD", "").lower()
        if skip_guard in ("1", "true", "yes"):
            return None

        # Normalize path to handle traversal
        resolved = Path(file_path).resolve()
        name = resolved.name

        # Only guard files in tests/spec_validation/
        resolved_str = str(resolved)
        if "tests/spec_validation/" not in resolved_str and "tests/spec_validation\\" not in resolved_str:
            return None

        # Extract issue number from filename pattern: test_spec_issue{N}_*.py
        match = re.match(r'test_spec_issue(\d+)_', name)
        if not match:
            return None  # Not an issue-scoped spec test (e.g. test_spec_tautological_assertions.py)

        spec_issue = int(match.group(1))

        # Get current pipeline issue
        current_issue = _get_current_issue_number()

        # Fail open when no pipeline context
        if current_issue == 0:
            return None

        # Allow if same issue
        if spec_issue == current_issue:
            return None

        # Block: different issue
        block_reason = (
            f"BLOCKED: Deletion of spec test '{name}' denied (Issue #790). "
            f"This test belongs to issue #{spec_issue} but current pipeline is issue #{current_issue}. "
            f"Spec validation tests are scoped to their originating issue. "
            f"REQUIRED NEXT ACTION: If this test is truly obsolete, move it to tests/archived/ "
            f"instead of deleting it. Run: mv {file_path} tests/archived/"
        )
        return (file_path, block_reason)

    except Exception:
        pass  # Fail-open: never block legitimate commands on detection errors

    return None


def _extract_bash_spec_test_targets(command: str) -> "list[str]":
    """Extract spec validation test file paths targeted by a Bash command.

    Detects rm, unlink, truncate, redirect-to-empty, Python os.remove/Path.unlink,
    and mv commands that move spec tests outside tests/archived/.

    Args:
        command: The Bash command string to inspect.

    Returns:
        List of file paths targeting spec validation tests.
    """
    import re

    targets = []

    try:
        # Helper to check if a path looks like a spec test
        def _is_spec_test_path(path: str) -> bool:
            path = path.strip().strip("'\"")
            return bool(
                ("spec_validation" in path or "test_spec_issue" in path)
                and re.search(r'test_spec_issue\d+_', path)
            )

        # 1. rm [-flags] <paths>
        rm_pattern = r'\brm\s+(?:-[^\s]+\s+)*([^\s;&|]+(?:\s+[^\s;&|]+)*)'
        for match in re.finditer(rm_pattern, command):
            for token in match.group(1).split():
                token = token.strip("'\"")
                if _is_spec_test_path(token):
                    targets.append(token)

        # 2. unlink <path>
        unlink_pattern = r'\bunlink\s+([^\s;&|]+)'
        for match in re.finditer(unlink_pattern, command):
            target = match.group(1).strip("'\"")
            if _is_spec_test_path(target):
                targets.append(target)

        # 3. truncate [-flags [value]] <path>
        truncate_pattern = r'\btruncate\s+(?:(?:-\w+\s+\S+\s+)|(?:--\w+=\S+\s+))*([^\s;&|]+)'
        for match in re.finditer(truncate_pattern, command):
            target = match.group(1).strip("'\"")
            if _is_spec_test_path(target):
                targets.append(target)

        # 4. Redirect-to-empty: > /path/to/file
        empty_redirect_pattern = r'(?:^|;|&&|\|\|)\s*>\s*([^\s;&|]+)'
        for match in re.finditer(empty_redirect_pattern, command):
            target = match.group(1).strip("'\"")
            if _is_spec_test_path(target):
                targets.append(target)

        # 5. Python os.remove / os.unlink / Path.unlink
        py_delete_patterns = [
            r'os\.remove\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
            r'os\.unlink\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
            r'Path\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)\.unlink',
        ]
        for py_pat in py_delete_patterns:
            for match in re.finditer(py_pat, command, re.IGNORECASE):
                target = match.group(1).strip()
                if _is_spec_test_path(target):
                    targets.append(target)

        # 6. mv to NON-archived location (mv to tests/archived/ is allowed)
        mv_pattern = r'\bmv\s+(?:-[^\s]+\s+)*([^\s;&|]+)\s+([^\s;&|]+)'
        for match in re.finditer(mv_pattern, command):
            source = match.group(1).strip("'\"")
            dest = match.group(2).strip("'\"")
            if _is_spec_test_path(source):
                # Allow mv to tests/archived/
                if "tests/archived" in dest:
                    continue
                targets.append(source)

    except Exception:
        pass  # Fail-open

    return targets


def _extract_git_checkout_targets(command: str) -> "list":
    """Extract file paths a ``git checkout``/``git restore`` would overwrite (Issue #1408).

    ``git checkout [<ref>] [--] <paths>...`` and ``git restore [--source=<ref>]
    [--] <paths>...`` overwrite working-tree files from a ref — a write path
    that the existing infra gate (cp/mv/redirect/tee/dd/python3) does NOT
    detect. This pure parser returns the candidate destination paths so the
    caller can re-check them against protected infrastructure.

    Conservative: false negatives are acceptable (a missed exotic form),
    false positives are not (we only harvest tokens after an explicit
    ``checkout``/``restore`` subcommand). Only regex/tokenisation — no fs or
    subprocess. Never raises.

    Args:
        command: The raw Bash command string.

    Returns:
        List of candidate file-path tokens (may be empty).
    """
    import re

    if not command:
        return []
    try:
        targets: "list" = []
        # Match `git ... checkout` or `git ... restore` (allow -C <dir> etc.
        # between `git` and the subcommand).
        for m in re.finditer(r"\bgit\b[^\n;&|]*?\b(checkout|restore)\b([^\n;&|]*)", command):
            tail = m.group(2)
            tokens = tail.split()
            paths: "list" = []
            seen_dd = False
            for tok in tokens:
                if tok == "--":
                    seen_dd = True
                    paths = []  # everything after `--` is authoritative paths
                    continue
                if tok.startswith("-"):
                    # flag (e.g. -b, --source=, -f, --) — skip; --source=<ref>
                    # names a ref, not a path.
                    continue
                paths.append(tok)
            # Heuristic when no `--` seen: git checkout <ref> -- is the safe form,
            # but `git checkout main -- a b` handled above. Without `--`, the
            # first token MAY be a ref (`git checkout main`) OR a path
            # (`git restore x`). We conservatively include ALL non-flag tokens:
            # over-inclusion only means an extra _is_protected_infrastructure
            # check that returns False for a ref like "main".
            for tok in paths:
                cleaned = tok.strip().strip("'\"")
                if cleaned:
                    targets.append(cleaned)
            _ = seen_dd
        return targets
    except Exception:
        return []


def _check_bash_infra_writes(command: str) -> "Optional[Tuple[str, str]]":
    """Check if a Bash command writes to protected infrastructure paths.

    Conservative detection: false negatives OK, false positives NOT OK.
    Returns None if allowed, or (file_name, block_reason) if blocked.

    Detects: sed -i, cp/mv to protected paths, shell redirects (>, >>),
    tee to protected paths, python3 -c with open(..., 'w'),
    cat heredoc (cat > file << EOF), dd of=FILE,
    Path.write_text/write_bytes in python3 -c,
    python3 heredoc with open()/Path.write_text inside (Issue #558).

    Args:
        command: The Bash command string to inspect.

    Returns:
        None if the command is allowed, or a tuple of (file_name, reason)
        if it should be blocked.
    """
    import re

    # If pipeline is active, allow everything (same as Write/Edit behavior)
    try:
        if _is_pipeline_active():
            return None
    except Exception:
        pass  # If check fails, continue with inspection

    # Collect candidate target file paths from various write patterns
    target_paths = []  # type: list

    # 1. sed -i (in-place edit)
    sed_pattern = r'\bsed\s+(?:-[^i]*)?-i[^\s]*\s+(?:[\'"][^\'"]*[\'\"]\s+)?([^\s;&|]+)'
    for match in re.finditer(sed_pattern, command):
        target_paths.append(match.group(1))

    # 2. cp / mv destination (last argument)
    # Match: cp [flags] source dest  OR  cp [flags] source1 source2 dest/
    cp_mv_pattern = r'\b(?:cp|mv)\s+(?:-[^\s]+\s+)*(?:[^\s]+\s+)+([^\s;&|]+)'
    for match in re.finditer(cp_mv_pattern, command):
        target_paths.append(match.group(1))

    # 3. Shell redirects (>, >>) — reuse existing helper
    redirect_targets = _extract_bash_file_writes(command)
    target_paths.extend(redirect_targets)

    # 4. python3 -c with file writes — Issue #589 (enhanced with python_write_detector)
    py_c_patterns = [
        r'python3?\s+-c\s+"([^"]+)"',   # double-quoted: python3 -c "..."
        r"python3?\s+-c\s+'([^']+)'",   # single-quoted: python3 -c '...'
    ]
    py_c_snippets = []
    for py_c_pattern in py_c_patterns:
        for match in re.finditer(py_c_pattern, command):
            py_c_snippets.append(match.group(1))

    # 5. python3 heredoc — python3 << 'EOF' with file writes inside (Issue #558, #589)
    py_heredoc_pattern = r'python3?\s+.*?<<\s*[\'"]?(\w+)[\'"]?'
    for match in re.finditer(py_heredoc_pattern, command):
        marker = match.group(1)
        heredoc_start = match.end()
        remaining = command[heredoc_start:]
        import re as _re
        _end_match = _re.search(r'(?:^|\n)' + _re.escape(marker) + r'(?:\n|$)', remaining)
        end_idx = _end_match.start() if _end_match else -1
        heredoc_body = remaining[:end_idx] if end_idx >= 0 else remaining
        py_c_snippets.append(heredoc_body)

    # Use python_write_detector if available, else fall back to inline regex
    for snippet in py_c_snippets:
        if _python_write_detector is not None:
            targets = _python_write_detector.extract_write_targets(snippet)
            for t in targets:
                if t == _python_write_detector.SUSPICIOUS_EXEC_SENTINEL:
                    # Directly block if command references protected path segments
                    for seg in ["agents/", "hooks/", "lib/", "skills/", "commands/"]:
                        if seg in command:
                            return (
                                f"__suspicious_exec__ ({seg})",
                                f"BLOCKED: Bash command contains exec/eval with dynamic arguments "
                                f"that reference protected path '{seg}'. This pattern may be "
                                f"attempting to bypass write enforcement. "
                                f"Infrastructure files require the /implement pipeline. "
                                f"Run: /implement \"description\" "
                                f"REQUIRED NEXT ACTION: Delegate file modifications to the "
                                f"implementer agent via the Agent tool. Do NOT use Bash to "
                                f"write to infrastructure files."
                            )
                else:
                    target_paths.append(t)
        else:
            # Inline regex fallback (original patterns)
            open_pattern = r'open\s*\(\s*[\'"]([^\'"]+)[\'"]\s*,\s*[\'"][wa]'
            for open_match in re.finditer(open_pattern, snippet):
                target_paths.append(open_match.group(1))
            path_write_pattern = r"Path\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\.write_(?:text|bytes)"
            for path_match in re.finditer(path_write_pattern, snippet):
                target_paths.append(path_match.group(1))
            # shutil fallback — Issue #589
            shutil_pattern = r'(?:\w+)\.(?:copy|copy2|move|copyfile)\s*\(\s*[\'"][^\'"]*[\'"]\s*,\s*[\'"]([^\'"]+)[\'"]\s*\)'
            for shutil_match in re.finditer(shutil_pattern, snippet):
                target_paths.append(shutil_match.group(1))
            # os.rename/os.replace fallback — Issue #698 (destination is 2nd arg)
            os_rename_pattern = r'(?:\w+)\.(?:rename|replace)\s*\(\s*[\'"][^\'"]*[\'"]\s*,\s*[\'"]([^\'"]+)[\'"]'
            for os_rename_match in re.finditer(os_rename_pattern, snippet):
                target_paths.append(os_rename_match.group(1))
            # Path(...).rename/Path(...).replace fallback — Issue #698 (destination is 1st arg)
            path_rename_pattern = r'(?:\w+)\s*\(\s*[\'"][^\'"]+[\'"]\s*\)\.(?:rename|replace)\s*\(\s*[\'"]([^\'"]+)[\'"]'
            for path_rename_match in re.finditer(path_rename_pattern, snippet):
                target_paths.append(path_rename_match.group(1))

    # 6. git checkout / git restore targets (Issue #1408) — these overwrite
    # working-tree files from a ref and are NOT covered by cp/mv/redirect/tee.
    try:
        target_paths.extend(_extract_git_checkout_targets(command))
    except Exception:
        pass  # fail-open: never block on extraction errors

    # 7. git apply / patch to protected infra (Issue #1408, narrowed by #1488).
    # The diff body is unparseable here (it may arrive via stdin/heredoc/file),
    # so we mirror the conservative ``__suspicious_exec__`` style. To avoid
    # false positives (Issue #1488) where the tokens co-occur inside heredoc
    # bodies, grep pattern arguments, or other quoted DATA (not shell command
    # structure), we (a) strip heredoc bodies and quoted segments before
    # scanning, and (b) require the ``git apply`` / ``patch`` invocation to
    # appear at a command-start position (start-of-string or immediately after
    # ``;`` ``&&`` ``||`` ``|`` ``(`` ``$(`` `` ` ``, allowing whitespace).
    # False negatives (segment hidden in a separate diff file) remain
    # acceptable; false positives on unrelated Bash commands are prevented.
    try:
        scan_text = _strip_heredoc_content(command)
        scan_text = _strip_quoted_segments(scan_text)
        # Command-start position: start of string OR after a shell separator/opener,
        # optionally followed by whitespace. Matches "patch " and "git apply " when
        # they are being invoked, not when they appear as substrings inside argv.
        invocation_pat = r"(?:^|[;&|(`]|\$\()\s*(?:git\s+apply|patch)\b"
        if re.search(invocation_pat, scan_text):
            for seg in ("agents/", "hooks/", "lib/", "skills/", "commands/"):
                if seg in scan_text:
                    return (
                        f"__patch_apply__ ({seg})",
                        f"BLOCKED: Bash command uses git apply/patch referencing protected "
                        f"path '{seg}'. Patch tooling can overwrite infrastructure files, "
                        f"which require the /implement pipeline. Run: /implement \"description\" "
                        f"REQUIRED NEXT ACTION: Delegate file modifications to the "
                        f"implementer agent via the Agent tool. Do NOT use git apply/patch to "
                        f"write to infrastructure files."
                    )
    except Exception:
        pass  # fail-open

    # Check each target path against protected infrastructure
    for fp in target_paths:
        fp = fp.strip().strip("'\"")
        if not fp:
            continue
        try:
            if _is_protected_infrastructure(fp):
                file_name = Path(fp).name
                # Check deny cache for escalation (Issue #558)
                repeated = _check_deny_cache(fp)
                if repeated:
                    block_reason = (
                        f"BLOCKED (repeated attempt): Bash command writes to protected "
                        f"file '{file_name}'. This path was already denied recently. "
                        f"Infrastructure files (agents/, commands/, hooks/, lib/, skills/) "
                        f"require the /implement pipeline. Run: /implement \"description\" "
                        f"REQUIRED NEXT ACTION: Delegate file modifications to the "
                        f"implementer agent via the Agent tool. Do NOT use Bash to "
                        f"write to infrastructure files."
                    )
                else:
                    block_reason = (
                        f"BLOCKED: Bash command writes to protected file '{file_name}'. "
                        f"Infrastructure files (agents/, commands/, hooks/, lib/, skills/) "
                        f"require the /implement pipeline. Run: /implement \"description\" "
                        f"REQUIRED NEXT ACTION: Delegate file modifications to the "
                        f"implementer agent via the Agent tool. Do NOT use Bash to "
                        f"write to infrastructure files."
                    )
                _update_deny_cache(fp)
                return (file_name, block_reason)
        except Exception:
            continue  # Skip paths that can't be resolved

    return None


def _run_extensions(tool_name: str, tool_input: Dict) -> Tuple[str, str]:
    """Run hook extension scripts that can block tool calls.

    Discovers *.py files in extensions/ directories (both alongside this hook
    and in the project's .claude/hooks/extensions/), loads each, and calls
    its ``check(tool_name, tool_input)`` function.

    Extensions survive /sync and /install — they are user-owned files in a
    directory that is never overwritten.

    Args:
        tool_name: Name of the tool being called.
        tool_input: Tool input parameters.

    Returns:
        Tuple of (decision, reason). ``("deny", reason)`` if any extension
        blocks; ``("allow", "")`` otherwise.
    """
    # Check kill-switch env var
    if os.getenv("HOOK_EXTENSIONS_ENABLED", "true").lower() == "false":
        return ("allow", "")

    # Discover extension directories
    ext_dirs: list[Path] = []

    # 1. Directory alongside this hook file (global ~/.claude/hooks/extensions/)
    hook_ext_dir = Path(__file__).parent / "extensions"
    ext_dirs.append(hook_ext_dir)

    # 2. Project-level .claude/hooks/extensions/
    project_ext_dir = Path.cwd() / ".claude" / "hooks" / "extensions"
    ext_dirs.append(project_ext_dir)

    # Collect extension files, deduplicated by filename (first occurrence wins)
    seen_names: set[str] = set()
    extension_files: list[Path] = []

    for ext_dir in ext_dirs:
        if not ext_dir.is_dir():
            continue
        try:
            py_files = sorted(ext_dir.glob("*.py"))
        except OSError:
            continue
        for py_file in py_files:
            # Skip symlinks (security)
            if py_file.is_symlink():
                continue
            if py_file.name in seen_names:
                continue
            seen_names.add(py_file.name)
            extension_files.append(py_file)

    # Execute each extension
    for ext_file in extension_files:
        try:
            module_name = f"_hook_ext_{ext_file.stem}"
            spec = importlib.util.spec_from_file_location(module_name, str(ext_file))
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            check_fn = getattr(module, "check", None)
            if check_fn is None:
                continue

            result = check_fn(tool_name, tool_input)

            # Validate return type
            if not isinstance(result, (tuple, list)) or len(result) != 2:
                continue

            decision, reason = result
            if decision == "deny":
                return ("deny", f"[ext:{ext_file.name}] {reason}")

        except Exception:
            # Per-extension isolation — never crash the hook
            continue

    return ("allow", "")


def _maybe_write_issue_context(tool_input: Dict) -> None:
    """Write issue command context file when Skill invokes an issue-creating command.

    Called from the NATIVE_TOOLS fast path when tool_name == "Skill".
    Writes the context JSON that _is_issue_command_active() checks, enabling
    downstream gh issue create Bash commands to pass through the hook.

    Fails open (silently) — a write failure should not block the Skill invocation.

    Args:
        tool_input: The tool_input dict from the hook, containing "skill" and/or "args".
    """
    skill_name = (
        tool_input.get("skill", "")
        or (tool_input.get("args", "").split()[0] if tool_input.get("args") else "")
    )
    # Normalize: strip leading slash if present
    skill_name = skill_name.lstrip("/")
    if skill_name in GH_ISSUE_COMMANDS:
        try:
            import json as _json
            from datetime import datetime, timezone

            with open(GH_ISSUE_COMMAND_CONTEXT_PATH, "w") as f:
                _json.dump(
                    {
                        "command": skill_name,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    f,
                )
        except Exception:
            pass  # Fail open - don't block Skill invocation on context write failure


# ============================================================================
# Plan-Exit Gate Helpers (Issue #926)
# ============================================================================


def _log_plan_exit_marker_corruption(disposition: str, detail: str) -> None:
    """Record an unreadable plan-exit marker to the canonical refusal sink.

    Issue #1684: corruption used to be handled silently (delete + pass
    through), so a guard that stopped enforcing left no trace. Routed
    through ``log_block_event`` — the same sink every other refusal in this
    hook uses (Issue #1588) — so the event is attributable.

    Never raises: telemetry must not break a hook decision.

    Only ``fail_closed`` actually refuses, so only it is logged with a
    refusal shape; the two permitting dispositions use ``allow`` so they
    are not counted as blocks by ``is_refusal_shape``.

    Args:
        disposition: What the gate did — ``fail_closed``, ``stale_by_mtime``
            or ``stat_failed``.
        detail: Short description of the parse failure.
    """
    try:
        log_block_event(
            hook_name="unified_pre_tool.py",
            decision_shape="dict" if disposition == "fail_closed" else "allow",
            reason=f"plan_exit_marker_corrupt:{disposition}",
            metadata={
                "gate": "plan-exit-gate",
                "marker": _PLAN_EXIT_MARKER_PATH,
                "disposition": disposition,
                "parse_error": str(detail)[:200],
                "issue": "1684",
            },
        )
    except Exception:
        pass


def _read_plan_exit_marker() -> "Optional[dict]":
    """Read the plan-mode-exit marker.

    Returns a dict with normalized 'stage' field, or None if no enforcement
    should occur. Handles staleness (>30 min auto-deletes and returns None),
    corruption (fails CLOSED to 'plan_exited' while the file's mtime is
    fresh — Issue #1684), and missing 'stage' (back-compat: treated as
    'critique_done'). Unknown stage values are treated as 'plan_exited'
    (fail-safe).

    Returns:
        dict with at least 'stage' key (always one of 'plan_exited' or
        'critique_done'), or None if no marker exists or marker was cleared.
    """
    try:
        marker_path = Path(os.getcwd()) / _PLAN_EXIT_MARKER_PATH
        if not marker_path.exists():
            return None

        try:
            from datetime import datetime as _datetime, timezone as _timezone
            raw_data = json.loads(marker_path.read_text())
            marker_ts = _datetime.fromisoformat(raw_data.get("timestamp", ""))
            age_minutes = (_datetime.now(_timezone.utc) - marker_ts).total_seconds() / 60.0
            if age_minutes > _PLAN_EXIT_STALE_MINUTES:
                marker_path.unlink(missing_ok=True)
                return None
        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as parse_exc:
            # Issue #1684: an unreadable marker is a verification FAILURE,
            # not an absence. INV-7 — "cannot verify the stage" means "not
            # passed", matching the unknown-stage branch below. The
            # timestamp is unreadable, so the staleness clock falls back to
            # the file's mtime; that bounds the fail-closed window at
            # _PLAN_EXIT_STALE_MINUTES instead of restricting the session
            # until someone manually deletes the file.
            import time as _time

            try:
                mtime_age_minutes = (
                    _time.time() - marker_path.stat().st_mtime
                ) / 60.0
            except OSError as stat_exc:
                # No clock at all — preserve the pre-#1684 escape rather
                # than livelock the session, but say so out loud.
                _log_plan_exit_marker_corruption(
                    "stat_failed", f"{parse_exc}; stat: {stat_exc}"
                )
                try:
                    marker_path.unlink(missing_ok=True)
                except OSError:
                    pass
                return None

            if mtime_age_minutes > _PLAN_EXIT_STALE_MINUTES:
                # An abandoned corrupt marker still self-clears.
                _log_plan_exit_marker_corruption("stale_by_mtime", str(parse_exc))
                try:
                    marker_path.unlink(missing_ok=True)
                except OSError:
                    pass
                return None

            # Fresh but unreadable — fail closed. Do NOT unlink: the file is
            # the only evidence the corruption occurred.
            _log_plan_exit_marker_corruption("fail_closed", str(parse_exc))
            return {"stage": "plan_exited"}

        # Normalize stage field
        raw_stage = raw_data.get("stage")
        if raw_stage is None:
            # Back-compat: old markers without stage field
            raw_data["stage"] = "critique_done"
        elif raw_stage in ("plan_exited", "critique_done"):
            raw_data["stage"] = raw_stage
        else:
            # Unknown stage — fail-safe to plan_exited
            raw_data["stage"] = "plan_exited"

        return raw_data
    except Exception:
        # Never raise from a hook — fail open (no enforcement)
        return None


def _delete_plan_exit_marker() -> None:
    """Best-effort deletion of the plan-exit marker. Never raises."""
    try:
        marker_path = Path(os.getcwd()) / _PLAN_EXIT_MARKER_PATH
        marker_path.unlink(missing_ok=True)
    except Exception:
        pass


def _bash_command_on_allowlist(command: str) -> bool:
    """Check whether a Bash command is on the plan-exit read-only allowlist.

    Returns True iff the command:
      1. Contains zero injection metacharacters (raw substring check), AND
      2. Tokenizes via .split() to match a 1-, 2-, or 3-token allowlist entry.

    NOTE: raw substring rejection (not shlex) is intentional. shlex would
    silently accept ';' inside quoted strings, which defeats injection
    blocking.

    Args:
        command: Raw Bash command string.

    Returns:
        True if allowed (read-only, no injection), False otherwise.
    """
    if not command or not isinstance(command, str):
        return False

    # Reject injection metacharacters (raw substring check)
    for token in _PLAN_EXIT_INJECTION_TOKENS:
        if token in command:
            return False

    parts = command.split()
    if not parts:
        return False

    if len(parts) == 1:
        return parts[0] in _PLAN_EXIT_BASH_ALLOWLIST_1TOKEN

    # Check 3-token allowlist first (more specific)
    if len(parts) >= 3:
        three = (parts[0], parts[1], parts[2])
        if three in _PLAN_EXIT_BASH_ALLOWLIST_3TOKEN:
            return True

    # Check 2-token allowlist
    two = (parts[0], parts[1])
    if two in _PLAN_EXIT_BASH_ALLOWLIST_2TOKEN:
        return True

    # Check 1-token (e.g., "ls -la" — first token is "ls", 1-token allowlist)
    if parts[0] in _PLAN_EXIT_BASH_ALLOWLIST_1TOKEN:
        return True

    return False


def _check_plan_exit_native(tool_name: str, tool_input: Dict) -> "Optional[Tuple[str, str, str]]":
    """Plan-exit gate for native Claude Code tools (Issue #926).

    State matrix:
      stage=plan_exited:
        Read/Glob/Grep                           -> None (allow, fall through)
        Task(plan-critic)                        -> None
        Bash on allowlist (no injection)         -> None
        Write/Edit/NotebookEdit                  -> deny
        Task(other subagent)                     -> deny
        Bash off allowlist OR with injection     -> deny
      stage=critique_done:
        Bash(gh issue create ...)                -> allow + delete marker
        Task(implementer|issue-creator|          -> allow + delete marker
            continuous-improvement-analyst)
        anything else                            -> None (fall through)

    Race mitigation: on tentative deny, sleep 10ms and re-read the marker; if
    the stage advanced (writer hook fired during call), allow the tool.

    Args:
        tool_name: Tool being invoked.
        tool_input: Tool input parameters.

    Returns:
        (decision, reason, system_message) if gate fires, or None to fall
        through to later validators/default-allow.
    """
    import time as _time

    # Issue #1361: Polarity flipped from #938. Only two bypasses remain here:
    #   1. AUTONOMOUS_DEV_SKIP_PLAN_REVIEW env var (plan-review escape hatch)
    #   2. .claude/SKIP_PLAN_REVIEW sentinel file (plan-review escape hatch)
    # The scope check (AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT or _is_adev_project())
    # is deleted — enforcement is now default-ON in every repo.
    # Universal bypass (Issue #969, .claude/.bypass / AUTONOMOUS_DEV_BYPASS)
    # short-circuits BEFORE this function via hook_bypass.is_bypassed() in the
    # hook preamble.
    if (os.environ.get("AUTONOMOUS_DEV_SKIP_PLAN_REVIEW", "").strip().lower()
            in ("1", "true", "yes", "on")):
        return None
    if (Path(os.getcwd()) / ".claude" / "SKIP_PLAN_REVIEW").exists():
        return None

    # Emit deprecation notice when GLOBAL_ENFORCEMENT is observed (Issue #1361).
    try:
        from hook_bypass import warn_global_enforcement_deprecated_once
        warn_global_enforcement_deprecated_once()
    except ImportError:
        pass

    marker = _read_plan_exit_marker()
    if marker is None:
        return None

    stage = marker.get("stage", "plan_exited")

    if stage == "critique_done":
        # Marker is primed for consumption. Only specific terminal actions
        # consume it; anything else passes through (fall to later gates).
        if tool_name == "Bash":
            command = tool_input.get("command", "") or ""
            # Detect `gh issue create` — canonical consuming command.
            # Tolerate leading whitespace and common flag positions.
            stripped = command.strip()
            if stripped.startswith("gh issue create") or stripped.startswith("gh  issue  create"):
                _delete_plan_exit_marker()
                return None  # Allow — fall through to later validators
            # Any other Bash at critique_done — fall through (normal enforcement)
            return None

        if tool_name in AGENT_TOOL_NAMES:
            subagent = (tool_input.get("subagent_type", "") or "").strip().lower()
            if subagent in _PLAN_EXIT_CONSUMER_AGENTS:
                _delete_plan_exit_marker()
                return None  # Allow — fall through to later validators
            # Other subagents at critique_done — fall through
            return None

        # Any other tool at critique_done — fall through
        return None

    # stage == "plan_exited"
    # --- Allow list (fall through, no deny) ---
    if tool_name in ("Read", "Glob", "Grep"):
        return None

    if tool_name in AGENT_TOOL_NAMES:
        subagent = (tool_input.get("subagent_type", "") or "").strip().lower()
        if subagent == "plan-critic":
            return None
        # Any other subagent is a deny candidate — apply race mitigation below

    if tool_name == "Bash":
        command = tool_input.get("command", "") or ""
        if _bash_command_on_allowlist(command):
            return None
        # Off-allowlist or has injection — deny candidate

    # --- Deny candidates ---
    # Race mitigation: 10ms re-read; if stage advanced, allow.
    # Belt-and-suspenders: catches any newly added NATIVE_TOOLS that aren't
    # explicitly handled above.
    # Issue #1503: was the literal ("Write", "Edit", "NotebookEdit") tuple,
    # which omitted MultiEdit. Sourced from the canonical registries so a new
    # write transport is covered by registering it once, in tool_intent.
    deny_tools = _ti_write_tool_names()
    is_deny_candidate = (
        tool_name in deny_tools
        or (tool_name in AGENT_TOOL_NAMES and (tool_input.get("subagent_type", "") or "").strip().lower() != "plan-critic")
        or (tool_name == "Bash")
    )

    if not is_deny_candidate:
        # Any other unclassified tool — fall through (allow)
        return None

    # Re-read marker after 10ms to catch writer-hook advance
    try:
        _time.sleep(0.01)
    except Exception:
        pass
    refreshed = _read_plan_exit_marker()
    if refreshed is None:
        # Marker cleared during window — allow
        return None
    if refreshed.get("stage") == "critique_done":
        # Stage advanced — allow (fall through to consume-on-intent logic)
        return None

    # Build a systemMessage with clear guidance (visible to user).
    system_msg = (
        "PLAN MODE EXIT DETECTED — Plan critique required\n"
        "You just exited plan mode. Before proceeding, you MUST run the "
        "plan-critic agent on your plan. After plan-critic completes with "
        "PROCEED verdict, /implement, /create-issue, and /plan-to-issues "
        "will consume the marker and run normally.\n"
        "Escape hatches (any one):\n"
        "  - /implement --skip-review                       (one-shot)\n"
        "  - export AUTONOMOUS_DEV_SKIP_PLAN_REVIEW=1       (cross-session, recommended)\n"
        "  - touch .claude/SKIP_PLAN_REVIEW                 (local, gitignored)"
    )
    return ("deny", _PLAN_EXIT_DENY_REASON, system_msg)


def _check_plan_exit_mcp(
    tool_name: str, tool_input: "Optional[Dict]" = None
) -> "Optional[Tuple[str, str]]":
    """Plan-exit gate for MCP (non-native) tools (Issue #926).

    State matrix:
      stage=plan_exited: deny what ACTS -- tools classified as writes by
        tool_intent.is_write(), plus _MCP_SIDE_EFFECT_TOOLS for tools that act
        without carrying a write shape. Everything else is allowed (Issue
        #1503 residual: the previous rule denied anything absent from an
        enumerated read allowlist, which blocked read-only tools from any
        unlisted server, including the mandated search path).

    ``tool_input`` defaults to None so the existing call site at ~8559 keeps
    working unchanged; registered writers classify by NAME and are caught even
    without a payload, and only the unregistered path+content fallback needs
    the real input.
      stage=critique_done: None (fall through — marker consumed by native gate).

    Same 10ms race mitigation as the native gate.

    Args:
        tool_name: MCP tool name (e.g., "mcp__ms365__send-mail").

    Returns:
        (decision, reason) if gate fires, or None to fall through.
    """
    import time as _time

    # Issue #1361: Polarity flipped from #938. Only the two plan-review escape
    # hatches short-circuit here now — the AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT
    # /_is_adev_project() scope check is deleted (default-ON enforcement).
    # Universal bypass is handled by hook_bypass.is_bypassed() in the preamble.
    if (os.environ.get("AUTONOMOUS_DEV_SKIP_PLAN_REVIEW", "").strip().lower()
            in ("1", "true", "yes", "on")):
        return None
    if (Path(os.getcwd()) / ".claude" / "SKIP_PLAN_REVIEW").exists():
        return None

    # Emit deprecation notice when GLOBAL_ENFORCEMENT is observed (Issue #1361).
    try:
        from hook_bypass import warn_global_enforcement_deprecated_once
        warn_global_enforcement_deprecated_once()
    except ImportError:
        pass

    marker = _read_plan_exit_marker()
    if marker is None:
        return None

    stage = marker.get("stage", "plan_exited")
    if stage == "critique_done":
        # MCP tools don't consume the marker; native gate handles consumption.
        return None

    # stage == "plan_exited"
    # Issue #1503 residual: deny what ACTS, not what is un-enumerated.
    #
    # Previously this allowed ONLY tools present in MCP_READ_TOOLS, so a
    # read-only tool from any unlisted server was denied at this stage --
    # including mcp__searxng__search, the mandated search path. That is the
    # same enumerate-by-name defect #1503 fixed on the write side.
    #
    # tool_input may be absent on older call paths; registered writers are
    # classified by NAME so they are still caught with an empty dict, and only
    # the unregistered path+content fallback needs the real payload.
    _pe_input = tool_input if isinstance(tool_input, dict) else {}
    try:
        _pe_acts = (
            _ti_is_write(tool_name, _pe_input)
            or tool_name in _MCP_SIDE_EFFECT_TOOLS
        )
    except Exception:
        _pe_acts = True  # fail closed: unclassifiable at a gate means deny
    if not _pe_acts:
        return None

    # Deny candidate — race mitigation
    try:
        _time.sleep(0.01)
    except Exception:
        pass
    refreshed = _read_plan_exit_marker()
    if refreshed is None:
        return None
    if refreshed.get("stage") == "critique_done":
        return None

    return ("deny", _PLAN_EXIT_DENY_REASON)


def _phase_e_skip(
    function_name: str,
    input_data: "Optional[Dict]" = None,
    session_id: "Optional[str]" = None,
) -> "Optional[Tuple[bool, str]]":
    """Phase E gate (Issue #999) — should the named check be skipped?

    Wraps the pure policy in :mod:`enforcement_decision` with the local
    telemetry surface and a session_id resolution that prefers the caller's
    explicit value, then falls back to ``input_data`` via :mod:`hook_stdin`.

    Returns:
        ``None`` on import failure (transitional deploy / cross-cwd /
        partial uninstall) — caller MUST treat None as "fall through to
        existing logic".
        ``(skip, reason)`` otherwise. ``skip == True`` means the named
        check SHOULD be bypassed; ``skip == False`` means run it as today.
        On skip, this helper emits a single ``mode_skip`` telemetry row.
        The enforce path is silent — preserves the pre-Phase-E baseline.

    NEVER raises — every exception path returns either None (import error)
    or ``(False, "exception_safety")`` (runtime error → fail-safe enforce).
    """
    try:
        from enforcement_decision import should_skip_enforcement
        from hook_telemetry import log_block_event

        sid = session_id
        if sid is None and input_data is not None:
            try:
                from hook_stdin import extract_session_id
                sid = extract_session_id(input_data)
            except ImportError:
                pass

        skip, reason = should_skip_enforcement(
            hook_name="unified_pre_tool.py",
            function_name=function_name,
            session_id=sid,
        )
        if skip:
            log_block_event(
                hook_name="unified_pre_tool.py",
                decision_shape="mode_skip",
                reason=reason,
                metadata={"function": function_name},
                session_id=sid,
            )
        return (skip, reason)
    except ImportError:
        # Phase E libs not yet deployed in this environment — fall through.
        return None
    except Exception:
        # Fail-safe: any unexpected exception → enforce. The hook decision
        # path is load-bearing; we never want to skip a gate because we hit
        # a weird exception inside the policy layer.
        return (False, "exception_safety")


def main():
    """Main entry point - dispatch to all validators and combine decisions."""
    try:
        # Load environment variables
        load_env()

        # Read input from stdin
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            # Invalid JSON - ask user (don't block on invalid input)
            output_decision("ask", f"Invalid input JSON: {e}")
            sys.exit(0)

        # Extract session_id from hook stdin for logging functions (Issue #504).
        # The env var CLAUDE_SESSION_ID is absent in most hook contexts, so we
        # store the stdin value at module level as a fallback.
        global _session_id, _agent_type
        _session_id = _sanitize_session_id(input_data.get("session_id", "unknown"))

        # Extract agent_type from hook stdin JSON (Issue #591).
        # When fired inside a subagent, Claude Code populates agent_type in the
        # hook payload even though CLAUDE_AGENT_NAME may be absent from the
        # subprocess environment.  _get_active_agent_name() uses this as primary
        # identity source.
        _agent_type = input_data.get("agent_type", "")

        # Extract tool information
        tool_name = input_data.get("tool_name", "")
        tool_input = input_data.get("tool_input", {})


        # =================================================================
        # ISSUE #1357: Warn when main invokes general-purpose outside pipeline
        # =================================================================
        if tool_name in AGENT_TOOL_NAMES:
            subagent_type = tool_input.get("subagent_type", "")
            if subagent_type == "general-purpose":
                agent_name = _get_active_agent_name()
                # Treat empty string or None as "main" for this check
                if not agent_name or agent_name == "main":
                    if not _is_pipeline_active():
                        # Emit warning to stderr
                        sys.stderr.write("[WARN] general-purpose launched outside pipeline; use /implement to route through researcher-local → researcher.\n")
                        
                        # Log to activity log
                        try:
                            from activity_log import log_activity
                            log_activity(
                                tool_name=tool_name,
                                event="general_purpose_outside_pipeline",
                                details={
                                    "level": "warn",
                                    "hook": "unified_pre_tool",
                                    "subagent": "general-purpose",
                                    "agent": "main",
                                    "session_id": _session_id
                                }
                            )
                        except ImportError:
                            pass  # Activity logging is optional
        # =================================================================
        # PHASE 1 SEMANTIC GATE (shadow, Issue #960).
        # Phase 1 semantic gate runs BEFORE the universal bypass so shadow
        # telemetry is captured even when .claude/.bypass is set. Bypass
        # still wins the decision; the judge only logs.
        # Default OFF via feature flag (.claude/feature_flags.json). The
        # flag uses OPT-IN semantics — fresh repos with no config file (or
        # a config file lacking the ``semantic_gate`` key) MUST NOT invoke
        # the judge. Use ``is_feature_explicitly_enabled`` for this (not
        # ``is_feature_enabled``, which is opt-out and defaults True).
        # When enabled, the judge writes one JSONL audit line per Write/
        # Edit attempt to .claude/logs/judge/<date>.jsonl. The verdict is
        # NEVER enforced in Phase 1. Wrapped in try/except so any judge
        # failure cannot affect the hook decision.
        # =================================================================
        # Issue #1263: Phase 2 SWE router dispatcher (log-only).
        # Falls back to Phase 1 shadow judge when only ``semantic_gate`` is
        # enabled. NEVER blocks — wrapped in the helper's outer try/except.
        _maybe_invoke_swe_router(tool_name, tool_input, _session_id)

        # =================================================================
        # UNIVERSAL BYPASS (Issue #969): AUTONOMOUS_DEV_BYPASS=1 OR
        # .claude/.bypass file in cwd-or-ancestor falls through to allow.
        # Checked BEFORE any other validation so a deadlocked harness can
        # always be unstuck by setting either signal from outside.
        # =================================================================
        try:
            from hook_bypass import is_bypassed, log_bypass_used, check_and_log_window_close
            if is_bypassed():
                # Issue #1197: Extract command head for Bash tools
                command_head = ""
                if tool_name == "Bash":
                    command_head = (tool_input.get("command") or "")[:200]
                
                log_bypass_used(
                    hook_name=Path(__file__).name,
                    tool_name=tool_name,
                    command_head=command_head,
                )
                
                # Issue #1195: In self-maintenance mode, still enforce agent-completeness gate
                # for git commits even when bypass is active
                _skip_bypass_exit = False
                if _is_self_maintenance_mode() and tool_name == "Bash":
                    command = tool_input.get("command", "")
                    if "git commit" in command or ("git -c" in command and "commit" in command):
                        _skip_bypass_exit = True

                # Issue #1435: Hard-floor infrastructure protection must survive the
                # universal bypass. _is_protected_infrastructure is a hard-floor function
                # (config/hard_floor_hooks.json); bypass must NOT allow protected-infra
                # writes. Fall through to the protected-infrastructure hard floor
                # (_enforce_protected_infrastructure, invoked just before the native-tool
                # fast path) so it can evaluate and deny.
                #
                # Issue #1503: the test is _ti_is_write, not the ("Write", "Edit")
                # tuple this replaced. Measured before the fix: native Write/Edit
                # correctly denied under bypass while MultiEdit, NotebookEdit and the
                # three serena editors all walked straight through — INV-4 was
                # bypassable with zero MCP servers installed (NotebookEdit ships with
                # Claude Code).
                if not _skip_bypass_exit and _ti_is_write(tool_name, tool_input):
                    try:
                        from hard_floor import is_hard_floor
                        file_path = _ti_first_write_target(tool_name, tool_input)
                        if _is_protected_infrastructure(file_path) and is_hard_floor(
                            "unified_pre_tool.py", "_is_protected_infrastructure"
                        ):
                            _skip_bypass_exit = True
                    except Exception:
                        # Fail CLOSED: if the hard-floor/protection check errors on a
                        # write under bypass, do NOT grant the bypass allow — fall
                        # through so the deny gate can evaluate.
                        _skip_bypass_exit = True

                if not _skip_bypass_exit:
                    output_decision("allow", "Universal bypass active (#969)")
                    sys.exit(0)
            else:
                # Issue #1197: Check for window close transitions
                check_and_log_window_close()
        except ImportError:
            pass  # bypass library unavailable - continue with normal hook logic

        if not tool_name:
            # No tool name - ask user
            output_decision("ask", "No tool name provided")
            sys.exit(0)

        # =================================================================
        # DRAIN-PENDING COMMIT GATE (drain-queue durability plan, round-2).
        #
        # When ``/drain-queue`` STEP 3.6 has written ``.claude/local/
        # drain_pending.json`` for an active cluster commitment, EVERY
        # ``git commit`` invocation MUST reference at least one cluster issue
        # via ``Closes #N`` / ``Fixes #N``. Otherwise the commit "freelanced"
        # — exactly the failure mode observed on 2026-06-15T18:06Z that
        # produced commit 8b3b582 without any ``Closes #N`` reference.
        #
        # This check runs BEFORE the native-tool fast path so it fires for
        # ALL Bash ``git commit`` invocations, not just enforcement-eligible
        # ones. The marker presence is the only gate trigger; the hook
        # NEVER consults TTL (long /implement runs of 2h+ MUST remain
        # covered — TTL cleanup is SessionStart-only).
        # =================================================================
        if tool_name == "Bash":
            _drain_gate = _check_drain_pending_commit_gate(tool_input)
            if _drain_gate is not None:
                _decision, _reason = _drain_gate
                output_decision(_decision, _reason)
                sys.exit(0)

        # =================================================================
        # PROTECTED-INFRASTRUCTURE HARD FLOOR (INV-4).
        #
        # Issue #1503: runs BEFORE the native-tool fast path so it is reachable
        # for EVERY write transport, not just the two that happened to be
        # spelled out in a tuple. The fast path below terminates in an
        # unconditional allow, so anything gated inside it is only as broad as
        # its own tool-name test — that is exactly how NotebookEdit (ships with
        # Claude Code, zero MCP servers required) walked through the hard floor.
        #
        # The fast-path entry itself is deliberately NOT widened: routing MCP
        # writers into it would skip validate_mcp_security, trading one hole
        # for another.
        # =================================================================
        _enforce_protected_infrastructure(tool_name, tool_input)

        # =================================================================
        # NESTED .claude/ REFUSAL (Issue #1726).
        #
        # Placed beside the hard floor and BEFORE the native-tool fast path for
        # the same reason: the fast path terminates in an unconditional allow,
        # so anything gated inside it only covers the tool names spelled out
        # there. Companion to the resolver fix that stopped the three hooks
        # from writing their own stray trees.
        # =================================================================
        _enforce_no_nested_claude_dir(tool_name, tool_input)

        # =================================================================
        # FAST PATH: Native tools skip ALL hook layers.
        # Hooks run BEFORE settings.json — returning "ask" here overrides
        # settings.json "allow" rules. Native tools are governed by
        # settings.json, not by this hook.
        # =================================================================
        if tool_name in NATIVE_TOOLS:
            # Auto-write context file when Skill invokes issue-creating commands
            # (Issue #647, #663). This MUST happen before any Bash gh-issue-create
            # check, because the Skill tool fires first and sets up the context
            # that _is_issue_command_active() reads.
            if tool_name == "Skill":
                _maybe_write_issue_context(tool_input)

            # Plan-Exit Gate (Issue #926): enforce plan-critic workflow on
            # every tool call. Moved from UserPromptSubmit because in-turn
            # model tool calls bypass UserPromptSubmit. Marker writer and
            # stage advancer unchanged — only enforcement event moved.
            #
            # Phase E (Issue #999): wrap with session-mode gate so low-risk
            # session classes skip the plan-exit nudge. Hard-floor checks
            # are NOT wrapped.
            _phase_e = _phase_e_skip(
                "_check_plan_exit_native",
                input_data=input_data,
                session_id=_session_id,
            )
            if _phase_e is None or not _phase_e[0]:
                plan_exit_decision = _check_plan_exit_native(tool_name, tool_input)
                if plan_exit_decision is not None:
                    decision, reason, system_message = plan_exit_decision
                    _log_pretool_activity(tool_name, tool_input, decision, reason)
                    output_decision(decision, reason, system_message=system_message)
                    sys.exit(0)

            # Infrastructure protection (Issue #483) now runs UPSTREAM of this
            # fast path, in _enforce_protected_infrastructure(). Issue #1503
            # moved it: NotebookEdit reached this point, failed the old
            # ("Write", "Edit") tuple test, and fell through to the terminal
            # "Native tool — hook bypass" allow, while MultiEdit and the MCP
            # editors never entered the fast path at all. The remaining
            # sub-gates below are still native-Write/Edit-shaped.
            if tool_name in ("Write", "Edit"):
                file_path = tool_input.get("file_path", "")

                # Issue #1330: Block architectural decision creation without plan-critic
                arch_block = _detect_architectural_decision_without_plan_critic(tool_name, tool_input)
                if arch_block:
                    _log_pretool_activity(tool_name, tool_input, "deny", arch_block)
                    output_decision(
                        "deny", arch_block,
                        system_message=arch_block,
                    )
                    sys.exit(0)

                # Issue #1142+ (Phase 1 polarity flip): Default-on production-code
                # Write/Edit gate. Replaces the previous opt-IN check via
                # `.claude/.enforce`. Per-repo opt-out is now via the existing
                # `.claude/.bypass` marker (already short-circuited at line ~4532).
                # The gate runs unless the pipeline is active, a one-shot operator
                # bypass is set, the file is non-code or a test, or the edit
                # classifies as no-change. Tier is one of "fix" / "light" / "full"
                # and is mapped to the matching /implement variant in the directive.
                try:
                    # Phase 2 (Issue #1146): pass session_id so the
                    # sliding-window can scope its ring buffer per session.
                    # #1171: sanitize untrusted env-var before use.
                    _wpg_session_id = _resolve_session_id_safe(_session_id)
                    _wpg_block, _wpg_tier, _wpg_directive = _check_write_pipeline_required(
                        tool_name,
                        file_path,
                        tool_input.get("old_string", ""),
                        tool_input.get("new_string", tool_input.get("content", "")),
                        session_id=_wpg_session_id,
                    )
                except Exception:
                    # Fail-closed on any unexpected exception
                    _wpg_block, _wpg_tier, _wpg_directive = (
                        True,
                        "wpg_check_error",
                        "Run /implement to make changes. Production-code gate detection errored; defaulting to enforce.",
                    )

                if _wpg_block:
                    _wpg_file_name = Path(file_path).name if file_path else "unknown"
                    _wpg_block_reason = (
                        f"BLOCKED: Write/Edit to code file '{_wpg_file_name}' requires the /implement pipeline. "
                        f"File: {file_path} "
                        f"Tier: {_wpg_tier}. "
                        f"REQUIRED NEXT ACTION: {_wpg_directive} "
                        f"Per-repo opt-out: touch .claude/.bypass && git commit."
                    )
                    _log_deviation(_wpg_file_name, tool_name, f"write_pipeline_gate_block:{_wpg_tier}")
                    _log_pretool_activity(tool_name, tool_input, "deny", _wpg_block_reason)
                    output_decision(
                        "deny", _wpg_block_reason,
                        system_message=(
                            f"BLOCKED: Write/Edit to '{_wpg_file_name}' denied (tier: {_wpg_tier}). "
                            f"Run /implement to make changes. "
                            f"Per-repo opt-out: touch .claude/.bypass && git commit."
                        ),
                    )
                    try:
                        _update_deny_cache(file_path)  # telemetry — does NOT prevent multi-Edit bypass
                    except Exception:
                        pass
                    sys.exit(0)
                elif _wpg_tier in ("operator_bypass", "pipeline_active"):
                    # Telemetry: log fast-path allows so we can detect over-bypass.
                    try:
                        _log_pretool_activity(tool_name, tool_input, "allow",
                                              f"write_pipeline_gate: {_wpg_tier}")
                    except Exception:
                        pass

                # Issue #1390: Block Write/Edit that escape worktree boundary
                worktree_violation = _check_worktree_path_boundary(tool_name, tool_input)
                if worktree_violation is not None:
                    violation_path, block_reason = worktree_violation
                    _log_deviation(violation_path, tool_name, "worktree_path_boundary_violation")
                    _log_pretool_activity(tool_name, tool_input, "deny", block_reason)
                    output_decision(
                        "deny", block_reason,
                        system_message=block_reason,
                    )
                    sys.exit(0)

                # Issue #557: Block settings.json writes during active pipeline
                if file_path:
                    fname = Path(file_path).name
                    if fname in ("settings.json", "settings.local.json"):
                        # Issue #1001: template paths are work products
                        # (plugins/*/templates/...) — bypass the guard.
                        if _is_settings_template_path(file_path):
                            pass
                        # Issue #1111: self-maintenance on plugin source — when
                        # we are inside the canonical autonomous-dev tree AND
                        # touching plugins/autonomous-dev/ paths, the maintainer
                        # IS the runtime settings author and the consumer-side
                        # guard does not apply. Tightened (security-auditor LOW,
                        # A01) from a substring check to a component-adjacency
                        # check via _is_plugin_source_path to avoid matching
                        # unrelated paths like /tmp/plugins/autonomous-dev/...
                        elif (
                            _is_self_maintenance_mode()
                            and _is_plugin_source_path(file_path)
                        ):
                            pass
                        else:
                            try:
                                if _is_pipeline_active():
                                    block_reason = (
                                        f"BLOCKED: Write to '{fname}' denied during active pipeline. "
                                        f"Settings files are protected during /implement sessions. "
                                        f"(Issue #557) "
                                        f"REQUIRED NEXT ACTION: Complete the current /implement "
                                        f"pipeline first, then modify settings. "
                                        f"Do NOT write settings during an active pipeline."
                                    )
                                    _log_deviation(fname, tool_name, "settings_json_write_block")
                                    _log_pretool_activity(tool_name, tool_input, "deny", block_reason)
                                    output_decision(
                                        "deny", block_reason,
                                        system_message=(
                                            f"BLOCKED: Write to '{fname}' denied during pipeline. "
                                            f"Complete /implement first."
                                        ),
                                    )
                                    sys.exit(0)
                            except Exception:
                                pass  # Don't block on check failure

                # Issue #790: Block deletion of spec validation tests outside current batch scope.
                # Detect Write with empty/whitespace content as a deletion vector.
                if file_path and tool_name == "Write":
                    try:
                        content = tool_input.get("content", "")
                        if isinstance(content, str) and content.strip() == "":
                            spec_block = _check_spec_test_deletion_scope(file_path)
                            if spec_block is not None:
                                _log_deviation(spec_block[0], tool_name, "spec_test_deletion_scope_block")
                                _log_pretool_activity(tool_name, tool_input, "deny", spec_block[1])
                                output_decision(
                                    "deny", spec_block[1],
                                    system_message=(
                                        f"BLOCKED: Spec test deletion outside batch scope. "
                                        f"Move to tests/archived/ instead."
                                    ),
                                )
                                sys.exit(0)
                    except Exception:
                        pass  # Fail-open: never block on detection errors

                # Layer 6: Prompt quality gate (Issue #842)
                # Block writes to agents/ or commands/ .md files that introduce
                # prompt anti-patterns (banned personas, casual register, oversized sections).
                # Only enforced during active pipeline — fail-open on errors.
                try:
                    if _is_pipeline_active() and file_path:
                        _pq_path = Path(file_path)
                        _pq_is_agent_or_command = (
                            _pq_path.suffix == ".md"
                            and ("/agents/" in file_path or "/commands/" in file_path)
                        )
                        if _pq_is_agent_or_command:
                            _pq_content = ""
                            _pq_existing = ""  # Pre-edit content (empty for Write)
                            _pq_is_edit = False
                            if tool_name == "Write":
                                _pq_content = tool_input.get("content", "")
                            elif tool_name == "Edit":
                                _pq_is_edit = True
                                # Read existing file, apply replacement in memory
                                try:
                                    _pq_existing = Path(file_path).read_text(encoding="utf-8")
                                    _pq_old = tool_input.get("old_string", "")
                                    _pq_new = tool_input.get("new_string", "")
                                    if _pq_old and _pq_old in _pq_existing:
                                        _pq_content = _pq_existing.replace(_pq_old, _pq_new, 1)
                                    else:
                                        _pq_content = _pq_existing  # Can't apply edit, check existing
                                except (OSError, UnicodeDecodeError):
                                    _pq_content = ""  # Can't read file, skip check
                                    _pq_existing = ""

                            if _pq_content:
                                # Defensive import of prompt_quality_rules
                                _pq_violations = None
                                try:
                                    _pq_lib_dir = Path(__file__).resolve().parent.parent / "lib"
                                    _pq_mod_path = _pq_lib_dir / "prompt_quality_rules.py"
                                    if _pq_mod_path.exists():
                                        _pq_spec = importlib.util.spec_from_file_location(
                                            "prompt_quality_rules", str(_pq_mod_path)
                                        )
                                        if _pq_spec and _pq_spec.loader:
                                            _pq_mod = importlib.util.module_from_spec(_pq_spec)
                                            _pq_spec.loader.exec_module(_pq_mod)
                                            # Commands are coordinator prompts with extensive
                                            # step-by-step instructions — use a higher density
                                            # threshold than agent prompts (Issue #845 remediation)
                                            _pq_density_threshold = (
                                                150
                                                if "/commands/" in file_path
                                                else _pq_mod.CONSTRAINT_DENSITY_THRESHOLD
                                            )
                                            # Issue #1038: Make Edit checks diff-aware so
                                            # pre-existing oversized sections / pre-existing
                                            # persona/casual phrases do not block edits that
                                            # don't touch them.  Write (full overwrite) uses
                                            # the standard check — everything is "new".
                                            if _pq_is_edit and _pq_existing:
                                                _pre_persona = set(
                                                    _pq_mod.check_persona(_pq_existing)
                                                )
                                                _pre_casual = set(
                                                    _pq_mod.check_casual_register(_pq_existing)
                                                )
                                                _new_persona = [
                                                    v
                                                    for v in _pq_mod.check_persona(_pq_content)
                                                    if v not in _pre_persona
                                                ]
                                                _new_casual = [
                                                    v
                                                    for v in _pq_mod.check_casual_register(
                                                        _pq_content
                                                    )
                                                    if v not in _pre_casual
                                                ]
                                                _new_density = (
                                                    _pq_mod.check_constraint_density_diff(
                                                        _pq_existing,
                                                        _pq_content,
                                                        threshold=_pq_density_threshold,
                                                    )
                                                )
                                                _pq_violations = (
                                                    _new_persona + _new_casual + _new_density
                                                )
                                            else:
                                                _pq_violations = (
                                                    _pq_mod.check_persona(_pq_content)
                                                    + _pq_mod.check_casual_register(_pq_content)
                                                    + _pq_mod.check_constraint_density(
                                                        _pq_content,
                                                        threshold=_pq_density_threshold,
                                                    )
                                                )
                                except Exception:
                                    _pq_violations = None  # Fail-open on import errors

                                if _pq_violations:
                                    _pq_fname = _pq_path.name
                                    _pq_summary = "; ".join(_pq_violations[:3])
                                    if len(_pq_violations) > 3:
                                        _pq_summary += f" ... and {len(_pq_violations) - 3} more"
                                    _pq_block_reason = (
                                        f"BLOCKED: Prompt quality violation in '{_pq_fname}' "
                                        f"(Issue #842). {_pq_summary} "
                                        f"REQUIRED NEXT ACTION: Fix the violations and retry. "
                                        f"Avoid banned persona openers ('You are an expert'), "
                                        f"casual register ('make sure', 'try to'), and "
                                        f"oversized constraint sections (>8 bullets). "
                                        f"Use formal directives (MUST, REQUIRED, FORBIDDEN)."
                                    )
                                    _log_pretool_activity(tool_name, tool_input, "deny", _pq_block_reason)
                                    output_decision(
                                        "deny", _pq_block_reason,
                                        system_message=(
                                            f"PROMPT QUALITY: '{_pq_fname}' has anti-pattern violations. "
                                            f"Fix and retry."
                                        ),
                                    )
                                    sys.exit(0)
                except Exception:
                    pass  # Fail-open: never block on prompt quality check errors

            # Bash command inspection: detect writes to protected paths (#502)
            if tool_name == "Bash":
                command = tool_input.get("command", "")
                if command:
                    # Phase 1 (Issue #1142+): Bash-to-code-file gate.
                    # Mirror the default-on Write/Edit gate above for Bash
                    # commands that write to code files (cat>, sed -i, tee,
                    # heredocs, python -c open(), awk redirect, base64 -d).
                    # User-driven patch tooling (`git apply`, `patch < diff`)
                    # is excluded by the detector. The gate respects the
                    # universal `.claude/.bypass` (checked at line ~4532
                    # earlier) and the one-shot operator bypass.
                    try:
                        # Phase 2 (Issue #1146): pass session_id for symmetry.
                        # #1171: sanitize untrusted env-var before use.
                        _b2b_session_id = _resolve_session_id_safe(_session_id)
                        (
                            _b2b_block,
                            _b2b_tier,
                            _b2b_directive,
                            _b2b_target,
                        ) = _check_bash_code_file_pipeline_required(
                            command, session_id=_b2b_session_id
                        )
                    except Exception:
                        _b2b_block = False
                        _b2b_tier = "wpg_check_error"
                        _b2b_directive = ""
                        _b2b_target = ""
                    if _b2b_block:
                        # Issue #1408 (user-approved Hybrid): DOWNGRADED from a
                        # hard decision:block to a NON-BLOCKING advisory. General
                        # bash write-detection is UNSOUND — `git checkout`,
                        # `python3 -c`, `dd`, `base64 | tee` and other forms
                        # bypass the pattern set, so a hard gate here provides a
                        # false sense of security while taxing legitimate one-off
                        # scripting. The HARD gates remain: Edit/Write
                        # (_check_write_pipeline_required), protected-infra Bash
                        # (_check_bash_infra_writes, incl. git checkout/apply),
                        # and the #803 cross-tool check below. This path is now
                        # best-effort DETECTIVE, not preventive.
                        #
                        # IMPORTANT: do NOT call _update_deny_cache here — nothing
                        # was denied, so poisoning the deny cache would make the
                        # #803 cross-tool check fire spuriously on later commands.
                        _b2b_basename = Path(_b2b_target).name if _b2b_target else "unknown"
                        _b2b_advisory = (
                            f"ADVISORY (Issue #1408): Bash command writes to code file "
                            f"'{_b2b_basename}' ({_b2b_target}, tier: {_b2b_tier}). "
                            f"This is no longer blocked, but for reviewable changes prefer: "
                            f"{_b2b_directive} "
                            f"Edit/Write to this file and protected-infrastructure writes "
                            f"remain hard-gated."
                        )
                        _log_deviation(
                            _b2b_basename, tool_name, f"bash_code_file_gate_advisory:{_b2b_tier}"
                        )
                        _log_pretool_activity(tool_name, tool_input, "allow", _b2b_advisory)
                        # Emit a user-visible advisory to stderr (same fall-through
                        # pattern as the #953 downgrade sites) but FALL THROUGH (no
                        # deny, no sys.exit) so the command proceeds.
                        try:
                            print(f"[hook advisory] {_b2b_advisory}", file=sys.stderr)
                        except Exception:
                            pass

                    # Issue #803: Cross-tool workaround detection.
                    # If a Write/Edit was recently denied, check if this Bash command
                    # targets the same path via heredoc, redirect, etc.
                    # Only check when pipeline is NOT active — during active pipeline,
                    # writes are legitimately allowed, so no workaround detection needed.
                    try:
                        _pipeline_active_803 = _is_pipeline_active()
                    except Exception:
                        _pipeline_active_803 = False
                    if not _pipeline_active_803:
                        try:
                            # #803 STAYS HARD. write_targets already covers
                            # cp/mv (via tool_intent.write_targets) + redirects/
                            # tee/dd/python. Issue #1408: additionally union
                            # git checkout/restore targets so a denied-Edit ->
                            # `git checkout -- same/path` workaround is still
                            # blocked (git checkout is otherwise undetected).
                            _write_targets_803 = list(_extract_bash_file_writes(command))
                            try:
                                _write_targets_803.extend(
                                    _extract_git_checkout_targets(command)
                                )
                            except Exception:
                                pass  # fail-open: never block on extraction errors
                            for _wt in _write_targets_803:
                                _wt_clean = _wt.strip().strip("'\"")
                                if not _wt_clean:
                                    continue
                                # Check full path match AND basename fallback
                                _wt_matched = _check_deny_cache(_wt_clean)
                                if not _wt_matched:
                                    # Basename fallback: Write may use absolute path,
                                    # Bash may use relative path or vice versa
                                    _wt_basename = Path(_wt_clean).name
                                    _wt_matched = _check_deny_cache(_wt_basename)
                                if _wt_matched:
                                    _xt_reason = (
                                        f"BLOCKED: Cross-tool workaround detected (Issue #803). "
                                        f"Write/Edit to '{_wt_clean}' was denied, and this Bash command "
                                        f"targets the same file. Infrastructure files require the "
                                        f"/implement pipeline. "
                                        f"REQUIRED NEXT ACTION: Run /implement to modify this file. "
                                        f"Do NOT use Bash heredoc/redirect as a workaround for denied writes."
                                    )
                                    _log_deviation(_wt_clean, tool_name, "cross_tool_workaround_block")
                                    _log_pretool_activity(tool_name, tool_input, "deny", _xt_reason)
                                    output_decision(
                                        "deny", _xt_reason,
                                        system_message="BLOCKED: Cross-tool workaround. Use /implement.",
                                    )
                                    sys.exit(0)
                        except Exception:
                            pass  # Fail-open: never block on detection errors

                    # Issue #1008: rm -rf with unresolved (unquoted) variable
                    # expansion. ALWAYS fires (hard-floor) regardless of pipeline
                    # status — `rm -rf $UNSET_VAR/path` expanding to `rm -rf /path`
                    # is catastrophic in any session mode. Fires BEFORE the
                    # state-deletion guard because it is a stronger gate.
                    try:
                        _rm_rf_var = _check_rm_rf_unresolved_vars(command)
                        if _rm_rf_var is not None:
                            _rrv_decision, _rrv_reason = _rm_rf_var
                            _log_deviation(
                                "rm_rf_unresolved_var", tool_name,
                                "rm_rf_unresolved_var_block",
                            )
                            _log_pretool_activity(tool_name, tool_input, "deny", _rrv_reason)
                            output_decision(
                                _rrv_decision, _rrv_reason,
                                system_message=(
                                    "BLOCKED: rm -rf with unquoted variable. "
                                    "Quote the variable to avoid catastrophic deletion."
                                ),
                            )
                            sys.exit(0)
                    except SystemExit:
                        raise
                    except Exception:
                        pass  # Fail-open: never block on detection errors

                    # Issue #803: Pipeline state file deletion guard.
                    # Block rm/unlink/truncate of pipeline state files during active pipeline.
                    # Issue #865: Allow cleanup when PIPELINE_CLEANUP_PHASE is set
                    # (STEP 15 / STEP B4 cleanup authorized by coordinator)
                    # Issue #1083: Allow cleanup in self-maintenance mode (autonomous-dev
                    # source repo). Mid-session env-var bypasses don't propagate to hook
                    # subprocesses (Issue #779), so maintainers working on the framework
                    # itself were deadlocked when a /implement session left stuck state.
                    try:
                        _cleanup_phase = os.getenv("PIPELINE_CLEANUP_PHASE", "").lower()
                        _state_del = _check_bash_state_deletion(command)
                        _self_maint = _is_self_maintenance_mode()
                        if (
                            _state_del is not None
                            and _cleanup_phase not in ("1", "true")
                            and not _self_maint
                            and _is_pipeline_active()
                        ):
                            _sd_reason = (
                                f"BLOCKED: {_state_del[1]} "
                                f"File: {_state_del[0]}. "
                                f"REQUIRED NEXT ACTION: Do NOT delete pipeline state files "
                                f"during an active /implement session. "
                                f"BYPASS (in order of reliability): "
                                f"(1) `touch .claude/.bypass` then retry — file-based, "
                                f"works mid-session; (2) export PIPELINE_CLEANUP_PHASE=1 "
                                f"BEFORE launching claude (env vars don't propagate "
                                f"mid-session — Issue #779)."
                            )
                            _log_deviation(_state_del[0], tool_name, "state_file_deletion_block")
                            _log_pretool_activity(tool_name, tool_input, "deny", _sd_reason)
                            output_decision(
                                "deny", _sd_reason,
                                system_message="BLOCKED: Pipeline state file deletion during active pipeline.",
                            )
                            sys.exit(0)
                        elif _state_del is not None and _self_maint and _is_pipeline_active():
                            # Log the relaxation for the audit trail (Issue #1083).
                            _log_pretool_activity(
                                tool_name, tool_input, "allow",
                                "self-maintenance: state cleanup permitted (autonomous-dev source repo)"
                            )
                    except Exception:
                        pass  # Fail-open: never block on detection errors

                    # Issue #790: Spec test deletion scope guard.
                    # Block rm/unlink/mv of spec validation tests from other issues.
                    try:
                        _spec_targets = _extract_bash_spec_test_targets(command)
                        for _spec_path in _spec_targets:
                            _spec_block = _check_spec_test_deletion_scope(_spec_path)
                            if _spec_block is not None:
                                _log_deviation(_spec_block[0], tool_name, "spec_test_deletion_scope_block")
                                _log_pretool_activity(tool_name, tool_input, "deny", _spec_block[1])
                                output_decision(
                                    "deny", _spec_block[1],
                                    system_message="BLOCKED: Spec test deletion outside batch scope. Move to tests/archived/ instead.",
                                )
                                sys.exit(0)
                    except Exception:
                        pass  # Fail-open: never block on detection errors

                    bash_block = _check_bash_infra_writes(command)
                    if bash_block is not None:
                        _log_deviation(bash_block[0], tool_name, "bash_infrastructure_protection_block")
                        _log_pretool_activity(tool_name, tool_input, "deny", bash_block[1])
                        output_decision(
                            "deny", bash_block[1],
                            system_message="BLOCKED: Bash write to infrastructure file. Delegate to implementer agent.",
                        )
                        sys.exit(0)

                    # Issue #557, #606: Detect inline env var spoofing
                    spoof_reason = _detect_env_spoofing(command)
                    if spoof_reason is not None:
                        # Issue #606: Track escalation across attempts in same session
                        # Skip escalation tracking when session_id is unknown to
                        # prevent false escalation from unrelated invocations
                        session_id = os.environ.get("CLAUDE_SESSION_ID", "unknown")
                        is_escalation = (
                            _track_spoofing_escalation(session_id)
                            if session_id != "unknown"
                            else False
                        )
                        if is_escalation:
                            spoof_reason += " [CIRCUMVENTION-ESCALATION]"
                        _log_deviation("env_spoofing", tool_name, "env_var_spoofing_block")
                        _log_pretool_activity(tool_name, tool_input, "deny", spoof_reason)
                        # Issue #970: recovery telemetry for env-var spoofing block.
                        log_block_with_recovery(
                            hook_name="unified_pre_tool.py",
                            tool_name=tool_name,
                            block_reason=spoof_reason,
                            recovery_hint=(
                                "Remove the protected env-var override from your command. "
                                "Set the variable in your shell profile if persistence is "
                                "needed. To bypass enforcement: AUTONOMOUS_DEV_BYPASS=1."
                            ),
                        )
                        output_decision(
                            "deny", spoof_reason,
                            system_message="BLOCKED: Protected environment variable cannot be overridden.",
                        )
                        sys.exit(0)

                    # Issue #627: Block direct creation of gh issue marker file
                    marker_block = _detect_gh_issue_marker_creation(command)
                    if marker_block:
                        # Issue #953: Downgrade deny → warning when /create-issue
                        # is not registered. Otherwise the user is wedged.
                        if not _hook_command_registered("create-issue"):
                            print(
                                f"[hook warning] Would block ({marker_block}) but "
                                f"/create-issue is not registered; allowing direct call. "
                                f"Re-register: /plugin install autonomous-dev@autonomous-dev",
                                file=sys.stderr,
                            )
                            # Fall through — do not deny.
                        else:
                            _log_deviation("gh_issue_marker", tool_name, "gh_issue_marker_creation_blocked")
                            _log_pretool_activity(tool_name, tool_input, "deny", marker_block)
                            output_decision(
                                "deny", marker_block,
                                system_message="BLOCKED: Use /create-issue to create GitHub issues.",
                            )
                            sys.exit(0)

                    # Issue #599: Block direct gh issue create outside approved contexts
                    gh_block = _detect_gh_issue_create(command)
                    if gh_block:
                        # Issue #953: Downgrade deny → warning when /create-issue
                        # is not registered. Otherwise the user is wedged.
                        if not _hook_command_registered("create-issue"):
                            print(
                                f"[hook warning] Would block ({gh_block}) but "
                                f"/create-issue is not registered; allowing direct call. "
                                f"Re-register: /plugin install autonomous-dev@autonomous-dev",
                                file=sys.stderr,
                            )
                            # Fall through — do not deny.
                        else:
                            _log_deviation("gh_issue_create", tool_name, "gh_issue_create_blocked")
                            _log_pretool_activity(tool_name, tool_input, "deny", gh_block)
                            output_decision(
                                "deny", gh_block,
                                system_message="BLOCKED: Use /create-issue or /create-issue --quick.",
                            )
                            sys.exit(0)

                    # Issue #1369: Block direct filing of guarded aggregate titles
                    aggregate_block = _detect_daily_aggregate_direct_filing(command)
                    if aggregate_block:
                        _log_deviation("daily_aggregate_direct", tool_name, "daily_aggregate_blocked")
                        _log_pretool_activity(tool_name, tool_input, "deny", aggregate_block)
                        output_decision(
                            "deny", aggregate_block,
                            system_message="BLOCKED: Use daily_aggregate_manager for aggregate issues.",
                        )
                        sys.exit(0)

                    # Issue #1330: Block architectural decision creation without plan-critic
                    arch_block = _detect_architectural_decision_without_plan_critic("Bash", tool_input)
                    if arch_block:
                        _log_pretool_activity(tool_name, tool_input, "deny", arch_block)
                        output_decision(
                            "deny", arch_block,
                            system_message=arch_block,
                        )
                        sys.exit(0)

                    # Issue #557: Block settings.json writes during active pipeline
                    try:
                        if _is_pipeline_active():
                            settings_block = _detect_settings_json_write(command)
                            if settings_block is not None:
                                _log_deviation("settings.json", tool_name, "settings_json_write_block")
                                _log_pretool_activity(tool_name, tool_input, "deny", settings_block)
                                output_decision(
                                    "deny", settings_block,
                                    system_message="BLOCKED: Settings write during pipeline. Complete /implement first.",
                                )
                                sys.exit(0)
                    except Exception:
                        pass  # Don't block on check failure

                    # Issue #1139: Warn when git stash is used mid-pipeline without
                    # a recorded baseline_cmd.  Advisory only — NEVER blocks.
                    try:
                        _gs_cmd = command.lstrip()
                        # Strip leading VAR=val env prefixes (e.g. "FOO=bar git stash ...")
                        while _gs_cmd and "=" in _gs_cmd.split(" ", 1)[0] and "/" not in _gs_cmd.split(" ", 1)[0]:
                            _gs_cmd = _gs_cmd.split(" ", 1)[1] if " " in _gs_cmd else ""
                        if _gs_cmd.startswith("git stash"):
                            _gs_state_path = os.environ.get(
                                "PIPELINE_STATE_FILE",
                                str(get_legacy_sentinel_path()),
                            )
                            if Path(_gs_state_path).exists():
                                _bg_lib_dir = Path(__file__).resolve().parent.parent / "lib"
                                _bg_spec = importlib.util.spec_from_file_location(
                                    "baseline_guardrail",
                                    str(_bg_lib_dir / "baseline_guardrail.py"),
                                )
                                if _bg_spec and _bg_spec.loader:
                                    _bg_mod = importlib.util.module_from_spec(_bg_spec)
                                    _bg_spec.loader.exec_module(_bg_mod)
                                    _bg_mod.warn_if_baseline_missing(_gs_state_path)
                    except Exception:
                        pass  # Never block the hook on guardrail errors

                    # Issue #712: Batch CIA completion gate
                    # Block git commit in batch worktrees when issues are missing CIA
                    # Phase E (Issue #999): session-mode wrap — low-risk
                    # classes skip this commit gate.
                    if "git commit" in command or "git -c" in command and "commit" in command:
                        _phase_e_cia = _phase_e_skip(
                            "_check_batch_cia_completions",
                            input_data=input_data,
                            session_id=_session_id,
                        )
                        if _phase_e_cia is None or not _phase_e_cia[0]:
                            try:
                                cwd = os.getcwd()
                                if _is_batch_context(cwd):
                                    if os.environ.get("SKIP_BATCH_CIA_GATE", "").strip().lower() not in ("1", "true", "yes"):
                                        _batch_cia_session_id = _resolve_session_id_safe(_session_id) or _session_id
                                        _batch_cia_result = _check_batch_cia_completions(_batch_cia_session_id)
                                        if _batch_cia_result is not None:
                                            _log_pretool_activity(tool_name, tool_input, "deny", _batch_cia_result)
                                            output_decision(
                                                "deny", _batch_cia_result,
                                                system_message=(
                                                    "BLOCKED: Batch CIA gate — some issues are missing "
                                                    "continuous-improvement-analyst completion. "
                                                    "Run CIA for all issues before committing."
                                                ),
                                            )
                                            sys.exit(0)
                            except Exception:
                                pass  # Fail-open: don't block on errors

                    # Issue #786: Batch doc-master completion gate
                    # Block git commit in batch worktrees when issues are missing doc-master
                    # Phase E (Issue #999): session-mode wrap.
                    if "git commit" in command or "git -c" in command and "commit" in command:
                        _phase_e_dm = _phase_e_skip(
                            "_check_batch_doc_master_completions",
                            input_data=input_data,
                            session_id=_session_id,
                        )
                        if _phase_e_dm is None or not _phase_e_dm[0]:
                            try:
                                cwd = os.getcwd()
                                if _is_batch_context(cwd):
                                    if os.environ.get("SKIP_BATCH_DOC_MASTER_GATE", "").strip().lower() not in ("1", "true", "yes"):
                                        _batch_dm_session_id = _resolve_session_id_safe(_session_id) or _session_id
                                        _batch_dm_result = _check_batch_doc_master_completions(_batch_dm_session_id)
                                        if _batch_dm_result is not None:
                                            _log_pretool_activity(tool_name, tool_input, "deny", _batch_dm_result)
                                            output_decision(
                                                "deny", _batch_dm_result,
                                                system_message=(
                                                    "BLOCKED: Batch doc-master gate — some issues are missing "
                                                    "doc-master completion. "
                                                    "Run doc-master for all issues before committing."
                                                ),
                                            )
                                            sys.exit(0)
                            except Exception:
                                pass  # Fail-open: don't block on errors

                    # Issue #802: Pipeline agent completeness gate
                    # Block git commit when required pipeline agents haven't completed
                    # Issue #853: In batch mode, check ALL issues rather than a single issue
                    # Phase E (Issue #999): session-mode wrap.
                    _phase_e_pa = _phase_e_skip(
                        "_check_pipeline_agent_completions",
                        input_data=input_data,
                        session_id=_session_id,
                    )
                    if ("git commit" in command or "git -c" in command and "commit" in command) and (
                        _phase_e_pa is None or not _phase_e_pa[0]
                    ):
                        try:
                            if _is_pipeline_active():
                                # Issue #1382: a message-only `git commit --amend`
                                # (staged tree == HEAD) changes no tracked content,
                                # so the agent-completeness gate must NOT re-fire.
                                # Computed BEFORE the batch/non-batch split so both
                                # paths honor it via the shared skip guard below. A
                                # content-changing amend (diff exit 1) returns False
                                # here and stays gated.
                                _skip_gate_via_amend = _is_message_only_amend(command)
                                if _skip_gate_via_amend:
                                    _log_pretool_activity(
                                        tool_name,
                                        tool_input,
                                        "allow",
                                        "bypass: message-only git commit --amend (tree unchanged, #1382)",
                                    )
                                # Issue #802: env var bypass + file-based bypass
                                # Env var works when set in harness; file works from Bash:
                                #   touch /tmp/skip_agent_completeness_gate
                                _skip_gate_file = Path("/tmp/skip_agent_completeness_gate")
                                _skip_gate_via_file = False
                                try:
                                    if _skip_gate_file.exists():
                                        try:
                                            _skip_gate_file.unlink()
                                        except OSError:
                                            pass  # Fail-open
                                        _skip_gate_via_file = True
                                except OSError:
                                    pass
                                # Issue #802 fix: Also check for inline env var in the command string
                                # Models naturally write "SKIP_AGENT_COMPLETENESS_GATE=1 git commit ..."
                                # but inline vars only affect the child process, not this hook's os.environ
                                # Security fix: Only match at START of command (not in commit messages)
                                _skip_gate_via_command = bool(re.match(r'(?i)SKIP_AGENT_COMPLETENESS_GATE=[1]', command.strip())) or bool(re.match(r'(?i)skip_agent_completeness_gate=true', command.strip()))
                                # Log bypass activations for audit trail
                                # NOTE(#1177-followup): env-var read here may also be dead; audit deferred.
                                _skip_gate_via_env = os.environ.get("SKIP_AGENT_COMPLETENESS_GATE", "").strip().lower() in ("1", "true", "yes")
                                if _skip_gate_via_file:
                                    _log_pretool_activity(tool_name, tool_input, "allow", "bypass: file-based gate skip consumed")
                                if _skip_gate_via_command:
                                    _log_pretool_activity(tool_name, tool_input, "allow", "bypass: inline env var in command string")
                                if _skip_gate_via_env:
                                    _log_pretool_activity(tool_name, tool_input, "allow", "bypass: SKIP_AGENT_COMPLETENESS_GATE set in process environment")
                                if not _skip_gate_via_env and not _skip_gate_via_file and not _skip_gate_via_command and not _skip_gate_via_amend:
                                    _agent_gate_session_id = _resolve_session_id_safe(_session_id) or _session_id
                                    cwd = os.getcwd()
                                    if _is_batch_context(cwd):
                                        # Batch mode: check all issues in the state file
                                        try:
                                            hook_dir = Path(__file__).resolve().parent
                                            lib_candidates = [
                                                hook_dir.parent / "lib" / "pipeline_completion_state.py",
                                                hook_dir.parents[2] / "lib" / "pipeline_completion_state.py",
                                            ]
                                            _batch_agent_mod = None
                                            for lib_path in lib_candidates:
                                                if lib_path.exists():
                                                    spec = importlib.util.spec_from_file_location(
                                                        "pipeline_completion_state", str(lib_path)
                                                    )
                                                    if spec and spec.loader:
                                                        _batch_agent_mod = importlib.util.module_from_spec(spec)
                                                        spec.loader.exec_module(_batch_agent_mod)
                                                    break

                                            if _batch_agent_mod is not None and hasattr(_batch_agent_mod, "_read_state") and hasattr(_batch_agent_mod, "verify_pipeline_agent_completions"):
                                                _batch_agent_state = _batch_agent_mod._read_state(_agent_gate_session_id)
                                                _batch_agent_completions = _batch_agent_state.get("completions", {}) if _batch_agent_state else {}
                                                # #1177: env-var handled internally by
                                                # _get_pipeline_mode_from_state() since #1173 — outer
                                                # `os.environ.get("PIPELINE_MODE") or ...` was dead.
                                                _batch_agent_pipeline_mode = _get_pipeline_mode_from_state()
                                                _batch_agent_failures: list = []
                                                for _batch_agent_key in _batch_agent_completions:
                                                    if _batch_agent_key == "0":
                                                        continue  # skip non-batch issue 0
                                                    try:
                                                        _batch_agent_issue_num = int(_batch_agent_key)
                                                    except (ValueError, TypeError):
                                                        continue
                                                    _batch_agent_passed, _batch_agent_completed, _batch_agent_missing = _batch_agent_mod.verify_pipeline_agent_completions(
                                                        _agent_gate_session_id, _batch_agent_pipeline_mode, issue_number=_batch_agent_issue_num
                                                    )
                                                    if not _batch_agent_passed:
                                                        _batch_agent_failures.append(
                                                            f"#{_batch_agent_issue_num}: missing {', '.join(sorted(_batch_agent_missing))}"
                                                        )

                                                if _batch_agent_failures:
                                                    _batch_agent_result = (
                                                        f"BLOCKED: Batch agent completeness gate -- the following issues are missing "
                                                        f"required pipeline agents: {'; '.join(_batch_agent_failures)}. "
                                                        f"All required pipeline agents MUST complete for every issue before git commit. "
                                                        f"REQUIRED NEXT ACTION: Run the missing agents for the listed issues before committing. "
                                                        f"BYPASS (in order of reliability): "
                                                        f"(1) `touch /tmp/skip_agent_completeness_gate` as a SEPARATE command first, "
                                                        f"then retry the commit — file-based, works mid-session "
                                                        f"(chaining with && WILL NOT WORK — the hook intercepts compound commands before touch executes); "
                                                        f"(2) export SKIP_AGENT_COMPLETENESS_GATE=1 BEFORE launching claude "
                                                        f"(env vars don't propagate mid-session — Issue #779). (Issue #853)"
                                                    )
                                                    _log_pretool_activity(tool_name, tool_input, "deny", _batch_agent_result)
                                                    output_decision(
                                                        "deny", _batch_agent_result,
                                                        system_message=(
                                                            "BLOCKED: Batch agent completeness gate -- required pipeline "
                                                            "agents have not completed for all batch issues. Run all required "
                                                            "agents before committing."
                                                        ),
                                                    )
                                                    sys.exit(0)
                                        except Exception:
                                            pass  # Fail-open: don't block on errors
                                    else:
                                        # Non-batch mode: single-issue check (existing behavior)
                                        _agent_gate_result = _check_pipeline_agent_completions(_agent_gate_session_id)
                                        if _agent_gate_result is not None:
                                            _log_pretool_activity(tool_name, tool_input, "deny", _agent_gate_result)
                                            output_decision(
                                                "deny", _agent_gate_result,
                                                system_message=(
                                                    "BLOCKED: Agent completeness gate -- required pipeline "
                                                    "agents have not completed. Run all required agents "
                                                    "before committing."
                                                ),
                                            )
                                            sys.exit(0)
                        except Exception:
                            pass  # Fail-open: don't block on errors

                    # Issue #754: Detect raw mlx_lm bypass in realign projects
                    try:
                        cwd = os.getcwd()
                        is_realign = (
                            Path(cwd, "src", "realign").is_dir()
                            or (Path(cwd, "pyproject.toml").exists()
                                and "realign" in Path(cwd, "pyproject.toml").read_text(errors="ignore"))
                        )
                        if is_realign:
                            rb_decision, rb_reason = _detect_realign_bypass(tool_name, tool_input)
                            if rb_decision == "deny":
                                _log_pretool_activity(tool_name, tool_input, "deny", rb_reason)
                                output_decision(
                                    "deny", rb_reason,
                                    system_message="BLOCKED: Use 'realign train' or 'realign generate' instead of raw mlx_lm.",
                                )
                                sys.exit(0)
                    except Exception:
                        pass  # Fail-open: don't block on project detection errors

            # Issue #528: Block coordinator code writes when /implement explicitly active
            # This is CRITICAL for external repo coverage — native tools bypass all
            # validation layers, so this check must be in the fast path.
            if tool_name in ("Write", "Edit", "Bash"):
                agent_name = _get_active_agent_name()
                impl_active = _is_explicit_implement_active()
                if (agent_name not in PIPELINE_AGENTS
                        and impl_active
                        and os.getenv("ENFORCEMENT_LEVEL", "block").strip().lower() != "off"):
                    if _is_code_file_target(tool_name, tool_input):
                        block_reason = (
                            "WORKFLOW ENFORCEMENT: /implement is active — code changes must be "
                            "made by pipeline agents (implementer, test-master, doc-master), "
                            "not the coordinator. Delegate this work to the appropriate agent. "
                            "REQUIRED NEXT ACTION: Invoke the appropriate agent (implementer, "
                            "test-master, or doc-master) via the Agent tool. "
                            "Do NOT write code directly."
                        )
                        _log_deviation(
                            tool_input.get("file_path", "bash_command")
                            if tool_name != "Bash" else "bash_command",
                            tool_name,
                            "explicit_implement_coordinator_block_native",
                        )
                        _log_pretool_activity(tool_name, tool_input, "deny", block_reason)
                        # Issue #970: recovery telemetry for #528 workflow enforcement.
                        log_block_with_recovery(
                            hook_name="unified_pre_tool.py",
                            tool_name=tool_name,
                            block_reason=block_reason,
                            recovery_hint=(
                                "Delegate the change to a pipeline agent (implementer, "
                                "test-master, doc-master) via the Task tool. To bypass for "
                                "an emergency direct-edit: set ENFORCEMENT_LEVEL=off or "
                                "AUTONOMOUS_DEV_BYPASS=1."
                            ),
                        )
                        output_decision(
                            "deny", block_reason,
                            system_message="WORKFLOW ENFORCEMENT: Delegate code changes to pipeline agents.",
                        )
                        sys.exit(0)

            # Issue #750: Block coordinator workaround edits after agent prompt-shrinkage denial
            # When validate_prompt_integrity denies an Agent call, the coordinator may
            # fall back to direct Write/Edit to protected infrastructure files.
            if tool_name in ("Write", "Edit"):
                _denied_agent = _check_agent_denial()
                if _denied_agent:
                    _deny750_path = tool_input.get("file_path", "")
                    if _is_protected_infrastructure(_deny750_path):
                        _deny750_is_substantive = False
                        if tool_name == "Edit":
                            _d750_old = tool_input.get("old_string", "")
                            _d750_new = tool_input.get("new_string", "")
                            _d750_sig, _, _ = _has_significant_additions(_d750_old, _d750_new, _deny750_path)
                            _deny750_is_substantive = _d750_sig
                        else:  # Write
                            _d750_content = tool_input.get("content", "")
                            _deny750_is_substantive = len(_d750_content.splitlines()) >= SIGNIFICANT_LINE_THRESHOLD
                        if _deny750_is_substantive:
                            _deny750_reason = (
                                f"BLOCKED: Agent '{_denied_agent}' was recently denied by prompt integrity. "
                                f"Direct edits to protected infrastructure ({_deny750_path}) are not allowed "
                                f"as a workaround. "
                                f"REQUIRED NEXT ACTION: Use get_agent_prompt_template('{_denied_agent}') "
                                f"to reload the full agent prompt from disk and retry the agent invocation. "
                                f"Do NOT attempt direct edits as a workaround."
                            )
                            _log_pretool_activity(tool_name, tool_input, "deny", _deny750_reason)
                            output_decision(
                                "deny", _deny750_reason,
                                system_message=(
                                    f"AGENT DENIAL WORKAROUND BLOCKED: Reload agent prompt and retry. "
                                    f"Do not edit infrastructure files directly."
                                ),
                            )
                            # Issue #803: Record denial for cross-tool workaround detection.
                            try:
                                _update_deny_cache(_deny750_path)
                            except Exception:
                                pass  # Never fail the hook for cache writes
                            sys.exit(0)


            # Layer 3.5: Plan-critic REVISE gate (Issue #1417)
            # Blocks implementer dispatch when plan-critic returned REVISE but planner not re-invoked
            if tool_name in AGENT_TOOL_NAMES:
                revise_decision, revise_reason = check_plan_critic_revise_gate(tool_name, tool_input)
                if revise_decision == "deny":
                    _log_pretool_activity(tool_name, tool_input, "deny", revise_reason)
                    output_decision(
                        "deny", revise_reason,
                        system_message="PLAN-CRITIC REVISE: Planner must be re-invoked first.",
                    )
                    sys.exit(0)
            # Layer 4: Pipeline ordering gate (Issues #625, #629, #632)
            # Only applies to Agent/Task tool calls during active pipeline.
            if tool_name in AGENT_TOOL_NAMES:
                ord_decision, ord_reason = validate_pipeline_ordering(tool_name, tool_input)
                if ord_decision == "deny":
                    # Issue #1227: Set redispatch flag when ordering gate denies
                    try:
                        from prompt_integrity import set_redispatch_flag
                        target_agent = tool_input.get('subagent_type', '').strip().lower()
                        if target_agent:
                            set_redispatch_flag(target_agent)
                    except Exception:
                        pass  # Never fail the hook for flag setting
                    _log_pretool_activity(tool_name, tool_input, "deny", ord_reason)
                    output_decision(
                        "deny", ord_reason,
                        system_message="ORDERING: Wait for prerequisite agents to complete.",
                    )
                    sys.exit(0)
            # Layer 5: Prompt integrity gate (Issue #695)
            # Blocks critical agents with sub-minimum prompts during pipeline.
            if tool_name in AGENT_TOOL_NAMES:
                pi_decision, pi_reason = validate_prompt_integrity(tool_name, tool_input)
                if pi_decision == "deny":
                    # Issue #1178: paired block + recovery telemetry. Generate a
                    # uuid4 block_event_id and capture a UTC anchor timestamp;
                    # the recovery path joins back via the same id and computes
                    # latency from this anchor.
                    import uuid as _uuid
                    from datetime import datetime as _dt, timezone as _tz
                    _pi_agent_type = tool_input.get("subagent_type", "")
                    _block_event_id = str(_uuid.uuid4())
                    _block_ts_iso = _dt.now(_tz.utc).isoformat()
                    _pi_reason_lower = pi_reason.lower() if isinstance(pi_reason, str) else ""
                    _category = next(
                        (cat for substr, cat in _PI_CATEGORY_MAP if substr in _pi_reason_lower),
                        "other",
                    )
                    _shrink_pct, _baseline_w, _current_w = _parse_pi_numerics(pi_reason)
                    _emit_prompt_integrity_event(
                        _PI_BLOCK_EVENT_TYPE,
                        agent_type=_pi_agent_type,
                        block_event_id=_block_event_id,
                        timestamp=_block_ts_iso,
                        block_reason_category=_category,
                        shrinkage_pct=_shrink_pct,
                        baseline_words=_baseline_w,
                        current_words=_current_w,
                        retry_count=0,
                        block_reason_detail=pi_reason,
                    )
                    # Issue #750: Record denial so subsequent Write/Edit workarounds are blocked.
                    # Issue #1178: persist block_event_id + ISO anchor for the recovery emission.
                    _record_agent_denial(
                        _pi_agent_type,
                        block_event_id=_block_event_id,
                        block_timestamp_iso=_block_ts_iso,
                    )
                    _log_pretool_activity(tool_name, tool_input, "deny", pi_reason)
                    output_decision(
                        "deny", pi_reason,
                        system_message=(
                            "PROMPT INTEGRITY: Your prompt for this agent is too short. "
                            "Include the full implementer output, changed files list, and test results. "
                            "Re-read the agent source from disk if needed."
                        ),
                    )
                    sys.exit(0)

            # Layer 5 (continued): Prompt-integrity recovery emission (Issue #1178).
            # If we reach this point with an Agent dispatch, pi_decision != "deny"
            # (the deny branch sys.exit'd above). If a denial record exists for the
            # same agent_type in this session, this dispatch IS the recovery — emit
            # the paired recovery row and consume the state file to enforce the
            # single-emit invariant.
            if tool_name in AGENT_TOOL_NAMES:
                _denial_record = _read_agent_denial_record()
                if _denial_record and _denial_record.get("agent_type") == tool_input.get(
                    "subagent_type", ""
                ):
                    from datetime import datetime as _dt, timezone as _tz
                    _block_ts_iso = _denial_record.get("block_timestamp_iso")
                    _block_event_id = _denial_record.get("block_event_id")
                    if _block_ts_iso and _block_event_id:
                        _now = _dt.now(_tz.utc)
                        try:
                            _block_dt = _dt.fromisoformat(_block_ts_iso)
                            _latency_ms = int((_now - _block_dt).total_seconds() * 1000)
                        except Exception:
                            _latency_ms = None
                        _emit_prompt_integrity_event(
                            _PI_RECOVERY_EVENT_TYPE,
                            agent_type=_denial_record.get("agent_type", ""),
                            block_event_id=_block_event_id,
                            timestamp=_now.isoformat(),
                            recovery_strategy="template_reload+reconstruct",
                            retry_count=1,
                            latency_ms_from_block_to_recovery=_latency_ms,
                        )
                        _consume_agent_denial_record()  # single-emit invariant

            # Run extensions even for native tools
            ext_decision, ext_reason = _run_extensions(tool_name, tool_input)
            if ext_decision == "deny":
                _log_pretool_activity(tool_name, tool_input, "deny", ext_reason)
                # Issue #970: emit recovery hint for blocks raised by extensions.
                log_block_with_recovery(
                    hook_name="unified_pre_tool.py",
                    tool_name=tool_name,
                    block_reason=ext_reason,
                    recovery_hint=(
                        "Review the extension that raised this deny. To temporarily disable "
                        "all hooks: set AUTONOMOUS_DEV_BYPASS=1 or `touch .claude/.bypass`. "
                        "See docs/TROUBLESHOOTING.md (#970)."
                    ),
                )
                output_decision("deny", ext_reason, system_message=ext_reason)
                sys.exit(0)

            # Issue #1503: the protected-infrastructure hard floor (INV-4) now
            # runs UPSTREAM of this fast path, so protected-infra writes are
            # already denied before reaching this terminal allow.
            reason = f"Native tool '{tool_name}' - hook bypass (settings.json governs)"
            _log_pretool_activity(tool_name, tool_input, "allow", reason)
            output_decision("allow", reason)
            sys.exit(0)

        # =================================================================
        # PROJECT GUARD: Non-autonomous-dev projects skip enforcement.
        # Only non-native (MCP) tools reach this point. For projects
        # without autonomous-dev, these don't need pipeline enforcement.
        # Fail-closed: if repo_detector is unavailable, _is_adev_project()
        # returns True so enforcement continues rather than being silently
        # skipped. (Issue #662)
        # =================================================================
        if not _is_adev_project():
            reason = "Non-autonomous-dev project - enforcement skipped"
            _log_pretool_activity(tool_name, tool_input, "allow", reason)
            output_decision("allow", reason)
            sys.exit(0)

        # Plan-Exit Gate for MCP tools (Issue #926, Issue #1503): enforce
        # plan-critic workflow on non-native tool calls (MCP servers). Deny when
        # the call is classified as a WRITE — either by tool name or by argument
        # shape, so editing tools from MCP servers nobody has enumerated are
        # still caught. Also deny tools in the explicit side-effect set, which
        # act without carrying a write shape (mcp__playwright__browser_evaluate
        # executes arbitrary JS with no path or content argument, so no shape
        # test can catch it). Everything else is allowed, including
        # un-enumerated read-only tools such as mcp__searxng__search. Passing
        # tool_input is required: it drives the argument-shape half of the
        # classifier.
        # Phase E (Issue #999): session-mode wrap. Hard-floor checks are
        # NOT wrapped; this is a non-hard-floor gate.
        _phase_e_mcp = _phase_e_skip(
            "_check_plan_exit_mcp",
            input_data=input_data,
            session_id=_session_id,
        )
        if _phase_e_mcp is None or not _phase_e_mcp[0]:
            plan_exit_mcp_decision = _check_plan_exit_mcp(tool_name, tool_input)
            if plan_exit_mcp_decision is not None:
                decision, reason = plan_exit_mcp_decision
                _log_pretool_activity(tool_name, tool_input, decision, reason)
                output_decision(decision, reason)
                sys.exit(0)

        # Run all validators in sequence (Layer 0 → Layer 1 → Layer 2 → Layer 3)
        validators_results = []

        # 0. Sandbox Layer (Layer 0) - Command classification & sandboxing
        decision, reason = validate_sandbox_layer(tool_name, tool_input)
        validators_results.append(("Sandbox", decision, reason))

        # 1. MCP Security Validator (Layer 1)
        decision, reason = validate_mcp_security(tool_name, tool_input)
        validators_results.append(("MCP Security", decision, reason))

        # 2. Agent Authorization (Layer 2)
        decision, reason = validate_agent_authorization(tool_name, tool_input)
        validators_results.append(("Agent Auth", decision, reason))

        # 3. Batch Permission Approver (Layer 3)
        decision, reason = validate_batch_permission(tool_name, tool_input)
        validators_results.append(("Batch Permission", decision, reason))

        # Layer 4: Hook extensions
        ext_decision, ext_reason = _run_extensions(tool_name, tool_input)
        if ext_decision == "deny":
            validators_results.append(("Extensions", "deny", ext_reason))

        # Combine all decisions
        final_decision, combined_reason = combine_decisions(validators_results)

        # Log the enforcement decision
        _log_pretool_activity(tool_name, tool_input, final_decision, combined_reason)

        # Output final decision
        output_decision(final_decision, combined_reason)

    except Exception as e:
        # Error in hook - ask user (don't block on hook errors)
        output_decision("ask", f"Hook error: {e}")

    # Always exit 0 - let Claude Code process the decision
    sys.exit(0)



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

_HOOK_TIMER_NAME = Path(__file__).name


def _timed_main():
    with HookTimer(_HOOK_TIMER_NAME):
        return main()

if __name__ == "__main__":
    _hook_safe_main(_timed_main)
