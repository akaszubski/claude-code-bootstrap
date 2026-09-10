---
covers:
  - plugins/autonomous-dev/hooks/
  - plugins/autonomous-dev/lib/hook_exit_codes.py
  - scripts/hooks/
---

# Automation Hooks Reference

**Last Updated**: 2026-09-06 (`PreToolUseWrite-protect-sensitive.sh` — MCP write-target extraction fixed, arm 5 — Issue #1588)
**Location**: `plugins/autonomous-dev/hooks/`

See [CLAUDE.md](../CLAUDE.md) for current counts. See [HOOK-REGISTRY.md](HOOK-REGISTRY.md) for environment variables and activation status.

---

## Overview

Hooks provide automated quality enforcement, validation, and workflow automation. They use standard `python3` shebangs and are designed to degrade gracefully — a hook crash never blocks Claude Code (see [Safe Failure Behavior](#safe-failure-behavior) below).

**Architecture**: Unified dispatcher pattern — consolidated hooks replace individual ones for reduced collision and easier maintenance.

---

## Exit Code Semantics

| Code | Constant | Meaning | Workflow Effect |
|------|----------|---------|-----------------|
| **0** | EXIT_SUCCESS | Passed | Continue normally |
| **1** | EXIT_WARNING | Non-critical issue | Continue with warning |
| **2** | EXIT_BLOCK | Critical issue | Block operation (PreCommit/PreSubagent only) |

**Lifecycle constraints**: PreToolUse, SubagentStop, Stop, and TaskCompleted hooks must always exit 0. Only PreCommit and PreSubagent hooks can block.

**Library**: `plugins/autonomous-dev/lib/hook_exit_codes.py` — see [LIBRARIES.md](LIBRARIES.md) for API.

---

## Active Hooks by Lifecycle

### UserPromptSubmit

| Hook | Purpose | Key Env Vars |
|------|---------|--------------|
| **unified_prompt_validator.py** | Compaction recovery re-injection (batch and pipeline state) + workflow bypass detection + quality nudges. On each prompt, checks for `.claude/compaction_recovery.json` and if present re-injects saved batch/pipeline context to stderr, then deletes the marker. Pipeline recovery validates staleness and cwd before injecting. **Plan-mode-exit enforcement was moved to PreToolUse (`unified_pre_tool.py`) per Issue #926** — UserPromptSubmit cannot observe in-turn model tool calls (e.g., `gh issue create`, `Task(implementer)`), so the gate was structurally in the wrong place. The marker file format and writer (`plan_mode_exit_detector.py`) are unchanged. **Semantic intent classifier (Phase 1, shadow mode)**: when `INTENT_CLASSIFIER_ENABLED=true`, lazily loads `lib/intent_classifier.py` and annotates each prompt's classification (13 intent classes — `security_critical`, `implement`, `refactor`, `test`, `doc`, `config`, `typo`, `status_query`, `conversation`, `exploration`, `triage`, `remote_ops`, `scratch` — plus AMBIGUOUS sentinel) to the activity log. Default is `false` — when unset/false, output is byte-identical to the pre-classifier version (verified by golden-snapshot test). Phase 1 is telemetry-only; no routing or blocking behavior changes. **Phase D (Issue #998)**: when `INTENT_CLASSIFIER_ENABLED=true`, also calls `lib/session_mode.write_session_mode()` to write a per-session artifact at `/tmp/session_mode_<sha256(session_id)[:8]>.json`; fail-open (write failures swallowed). **Phase E (Issue #999)**: `INTENT_CLASSIFIER_ENFORCE=true` activates downstream enforcement in `unified_pre_tool.py` (5 wrap sites), `plan_gate.py`, and `plan_mode_exit_detector.py` — this hook remains the UserPromptSubmit writer; enforcement is in PreToolUse hooks. | ENFORCE_WORKFLOW, QUALITY_NUDGE_ENABLED, INTENT_CLASSIFIER_ENABLED, INTENT_CLASSIFIER_ENFORCE |
| **session_activity_logger.py** | Captures user prompt preview + length into session JSONL log. Pins session start date. Non-blocking. | ACTIVITY_LOGGING |

### PreToolUse

| Hook | Purpose | Key Env Vars |
|------|---------|--------------|
| **enforce_tier_distribution.py** | Warns when test tier distribution drifts from the target T3:T2:T1:T0 = 5:2:2:1 ratio. **Transport-independent since Issue #1503**: the tool test is `tool_intent.is_write()` (matcher: `Write\|Edit\|MultiEdit\|NotebookEdit\|mcp__.*`), not a hard-coded `("Write", "Edit")` tuple. Lazy-imports `TestLifecycleManager` from `test_lifecycle_manager.py` to compute current tier counts and emits a warning via stderr when actual distribution deviates > 50% from target. Non-blocking (always exits 0) — part of the test pyramid health monitoring delivered in Issue #908. (Issues #908, #1503) | — |
| **PreToolUseWrite-protect-sensitive.sh** | Guards sensitive-file writes on `PreToolUse`, matcher `Write\|Edit\|MultiEdit\|NotebookEdit\|mcp__.*`, timeout 5. **Was dead on arrival (Issue #1587)**: bound to no lifecycle event in any settings surface despite shipping via `install_manifest.json`, read the nonexistent `.parameters.file_path` instead of the real `tool_input.file_path`, and emitted a bare top-level `permissionDecision` that Claude Code does not honor as either `hookSpecificOutput.permissionDecision` or the legacy `{"decision": "block"}` envelope — three independent reasons its 0 rows in `hook-blocks.jsonl` were unreadable rather than clean. All three are fixed: registered on `PreToolUse` in every settings template plus `global_settings_template.json`, reads `tool_input.file_path`, and emits the `hookSpecificOutput` envelope on both allow and refusal paths. **Policy split (Issue #1588)**: the single deny list is now two decision classes routed through one `matches_pattern()` helper — **deny** (`credentials`, `secrets`, `private.*key`, `.pem`, `.key`, `.git/`) refuses outright; **ask** (`.env`, `.env.*`, `PROJECT.md`) stops the agent and prompts the human, since a blanket deny cannot express "let the human decide." Matching is case-insensitive (`grep -qiE`) because the deploy target (macOS/APFS) is case-insensitive by default — case-sensitive matching let `SECRETS.yaml` bypass a deny on `secrets.yaml`, the same file under a different spelling; the unanchored `credentials`/`secrets`/`private.*key` substrings now also catch CamelCase names such as `AwsCredentialsProvider.java`. Both `deny` and `ask` decisions record to `.claude/logs/hook-blocks.jsonl` with `decision_shape="dict"`; the actual class is in `metadata.decision` — a reader counting blocks must split on that field or it over-counts hard refusals. **Arm 5 (Issue #1588, MCP coverage was broken)**: the matcher includes `mcp__.*` and fires for MCP editors, but the hook decided using only `.tool_input.file_path` — a key MCP editors never send (`mcp__serena__replace_symbol_body`/`replace_content` carry their target under `relative_path`). Measured: `Write`+`file_path=credentials.json` denied while the identical path via `mcp__serena__replace_symbol_body`+`relative_path` allowed, and a key control (same MCP tool name, `file_path` key) still denied, proving the KEY was the fault, not the tool name. Fixed by delegating to `lib/tool_intent.py`'s `write_targets()` (the same tool-name → path-key registry the Issue #1435 protected-infrastructure hard floor already uses) rather than enumerating more keys; its output is UNIONED with, not substituted for, the original `jq` extraction, so a host with `python3` absent or `tool_intent` unimportable still keeps full built-in-tool coverage and loses only the added MCP reach. `match_any_target()` now runs `matches_pattern()` across every extracted target so a match on any one target triggers the same deny/ask paths. Known gap, deliberately not covered: `id_rsa`, `id_ed25519`, `.netrc`, `kubeconfig`, `terraform.tfstate`, `.npmrc`, `service-account.json` (`~/.ssh/**` is independently covered by the `Edit(~/.ssh/**)` settings deny rule). | — | Issues #1587, #1588 |
| **unified_pre_tool.py** | Native tool fast path + 4-layer permission validation (sandbox → MCP security → agent auth → batch approval) + pipeline ordering gate (deny messages now include session_id in format `(session_id: <id>)` for diagnosability — Issue #1196) + hook extensions. 84% reduction in permission prompts. Blocks git bypass flags (--no-verify, --force push, reset --hard, clean -f). Blocks a direct write via **any write-classified tool** (Write, Edit, MultiEdit, NotebookEdit, or an MCP editor such as `mcp__serena__replace_symbol_body` — classification is `tool_intent.is_write()`, Issue #1503) to infrastructure files (`agents/*.md`, `commands/*.md`, `hooks/*.py`, `lib/*.py`, `skills/*/SKILL.md`) and per-file protected entries (`config/install_manifest.json` — Issue #980) outside `/implement` pipeline — scoped to autonomous-dev repos only. The hard floor runs **upstream of** the native-tool fast path (relocated in Issue #1503), so a tool that terminates in the fast path's unconditional allow can no longer escape it. Also inspects Bash command bodies for shell file-write patterns (sed -i, cp/mv, redirects, tee, python3 -c writes, cat heredoc `cat > file << EOF`, `dd of=FILE`, `Path.write_text/write_bytes` in python3 -c, python3 heredoc with open()/Path.write_text inside) to the same protected paths, closing the bypass gap where wrapping a write in Bash would evade the gate (Issue #558). Python snippet analysis (python3 -c and heredoc bodies) is backed by `python_write_detector.py` (Issue #589) using AST-based extraction with regex fallback; handles aliased `Path` imports, `shutil.copy/move` destination arguments, and `eval()`/`exec()` with dynamic arguments. Deny cache at `/tmp/.claude_deny_cache.jsonl` tracks repeated bypass attempts within a 60-second window and escalates the block message on second attempt (Issue #558). Detects inline env var spoofing in Bash commands (e.g. `VAR=value cmd` or `export VAR=value`) for protected pipeline variables. Individual variables protected by exact match (7, grown from 5): PIPELINE_STATE_FILE, ENFORCEMENT_LEVEL, AUTONOMOUS_DEV_COMMAND, INTENT_CLASSIFIER_ENFORCE (Issue #1134), ALIGNMENT_USER_APPROVED (Issue #1467 — gates the `escalate` -> `user_approved` upgrade in the alignment gate; inline-spoofing it, e.g. `ALIGNMENT_USER_APPROVED=1 python3 -c ...`, would otherwise fake a human approval), **SCRATCHPAD** and **PLAN_CRITIC_VERDICT_PATH** (both added in the same change: `SCRATCHPAD` gates the `_is_scratch_path()` write-gate exemption — `SCRATCHPAD=/ <cmd>` previously reduced the prefix test to `startswith("/")`, exempting every absolute path from the gate, so it is now both protected against inline spoofing AND `_is_scratch_path` itself rejects degenerate roots (`/`, `//`, `""`, `.`, `..`, `~`, or any relative value) regardless of the env var's protection; `PLAN_CRITIC_VERDICT_PATH` gates the plan-critic REVISE refusal — pointing it at `/dev/null` would silently disable that gate). Note: CLAUDE_AGENT_NAME and CLAUDE_AGENT_ROLE are protected by the `CLAUDE_` prefix rule below, not by the individual-match set. CLAUDE_SESSION_ID was previously in this group but is now excluded — see exception note below. Additionally, any variable whose name starts with the `CLAUDE_` prefix is blocked by prefix-based protection (Issue #606, `PROTECTED_ENV_PREFIXES`), preventing new CLAUDE_* variables from being spoofed without requiring explicit listing. Heredoc content is stripped from the command before pattern matching so that documentation strings containing protected env-var names (e.g. writing a Markdown file that mentions `PIPELINE_STATE_FILE`) do not produce false-positive blocks (Issue #1032). A session-scoped escalation tracker (`_track_spoofing_escalation()`) persists attempt counts to `~/.claude/logs/spoofing_attempts.json` across hook invocations; repeated spoofing attempts within the same session produce an escalated block message — blocks attempts to forge agent identity or downgrade enforcement level. Blocks Write/Edit to `settings.json` and `settings.local.json` during active `/implement` pipeline sessions — with three bypass conditions: (1) paths under any `templates/` directory component are skipped because those are template source files, not runtime settings (`_is_settings_template_path`, Issue #1001); (2) paths under `plugins/autonomous-dev/` are skipped when self-maintenance mode is active (cwd inside the canonical autonomous-dev source tree), because the maintainer is the runtime settings author and the consumer-side guard does not apply (Issue #1111); (3) Bash write targets under `/tmp/`, `/var/folders/`, or `/private/tmp/` are skipped because tempfile-directory paths are physically incapable of affecting real Claude settings — these are pytest fixtures and `tempfile.mkdtemp()` paths (`_TEMP_PREFIXES` carve-out in `_detect_settings_json_write`, Issue #958). Also blocks Bash `python3 -c` / `python -c` commands that contain both a settings file reference (`settings.json` or `settings.local.json`) AND a Python write pattern (`open(`, `json.dump(`, `.write(`, `.write_text(`, `shutil.`, `os.rename(`, `os.replace(`), closing the bypass where variable indirection (`p = 'settings.json'; json.dump(d, open(p,'w'))`) would evade the file-tool gate (Issue #768). Verifies HMAC integrity of pipeline state files to detect tampering. (Issue #557) Alignment gate: when `/implement` is active, blocks coordinator Write/Edit/Bash to code files until STEP 2 (PROJECT.md alignment) has completed — `alignment_passed: true` must be set in the pipeline state before any code changes are permitted; fails closed on HMAC failure or missing state. `alignment_passed` field included in the HMAC message to prevent tampering. (Issue #585) **Alignment-verdict extension (Issue #1467)**: STEP 2 is no longer coordinator self-attestation — `alignment_passed` is set solely by `alignment_classifier.record_alignment_verdict()` after a two-stage gate (deterministic Stage 0 pre-check, then an `alignment-classifier` Haiku agent dispatch with a citation verified against PROJECT.md). The co-signed `alignment_verdict` field (lowercase enum: `auto_pass`, `escalate`, `user_approved`, `block`) is now also included in the HMAC message. `_has_alignment_passed()` treats a present-but-disallowed verdict (anything outside `alignment_classifier.ALLOWED_VERDICTS = {auto_pass, user_approved}`) as failing even when `alignment_passed` is somehow `True`; when `alignment_classifier.py` is not importable next to the hook, or the `alignment_verdict` field is absent (legacy/pre-#1467 state), the hook degrades to the pre-#1467 boolean-only check for consumer-repo backward compatibility. A NEW check at the pipeline-agent-authorization site denies Write/Edit for `implementer`/`test-master`/`doc-master` (not just the coordinator) when an explicit ESCALATE/BLOCK verdict is present, with a block message directing the user to resolve the scope/architecture delta, update PROJECT.md, or narrow the change. Blocks direct `gh issue create` in Bash outside the `/implement` pipeline, authorized issue-creation agents (`continuous-improvement-analyst`, `issue-creator`), or commands that write a command context file at `/tmp/autonomous_dev_cmd_context.json` (Issue #599, #630). Realign CLI enforcement (Issue #754): in projects detected as realign repos (contain `src/realign/` or `pyproject.toml` with "realign" string), blocks Bash commands that directly invoke `python -m mlx_lm.lora`, `python -m mlx_lm.generate`, `python -m mlx_lm.fuse`, or `python -m mlx.launch`; grep/search/cat references to mlx_lm are allowed. Block message directs the user to use `realign train` or `realign generate` instead. Fails open on project-detection errors. Agent completeness gate (Issues #802, #853): blocks `git commit` when required pipeline agents have not all completed. In batch mode (detected by `.worktrees/batch-` in cwd), iterates ALL issues in the state file and calls `verify_pipeline_agent_completions()` per issue, respecting each issue's `research_skipped` flag; produces a per-issue failure list (`#N: missing agent1, agent2`). In non-batch mode, calls `_check_pipeline_agent_completions()` for the single active issue. Both paths read state via `pipeline_completion_state.py`; bypass (in order of reliability): (1) `touch /tmp/skip_agent_completeness_gate` as a SEPARATE command first, then retry — file-based one-shot, works mid-session, file consumed on first check; (2) `export SKIP_AGENT_COMPLETENESS_GATE=1` BEFORE launching claude (env vars don't propagate mid-session — the hook runs in a separate process; Issue #779); (3) inline command prefix `SKIP_AGENT_COMPLETENESS_GATE=1 git commit ...` — the hook parses the Bash command string for the env var prefix, so prefixing the commit command directly also works; `skip_agent_completeness_gate=true` accepted case-insensitively; Issue #802); (4) **automatic short-circuit for message-only `git commit --amend`** (Issue #1382): `_is_message_only_amend()` runs `git diff-index --quiet --cached HEAD --` and only returns True when the staged tree is byte-identical to HEAD (e.g. `--amend --no-edit` or a pure reword) — a content-changing amend still returns False and stays gated. This is not an operator-invoked bypass; it fires automatically and is logged with reason `bypass: message-only git commit --amend (tree unchanged, #1382)`; fails open (treated as False, i.e. still gated) on any subprocess/parse error. **Read-side session-id fallback** (Issue #1228): if the payload `session_id` yields ZERO completion records (not passed, nothing completed, agents missing) — e.g. a `git commit` Bash subprocess dropped `CLAUDE_SESSION_ID` and fell back to a boot-time `"unknown"` sentinel while the real completions were recorded under a resolvable id — `_check_pipeline_agent_completions()` calls `resolve_session_id()` and re-evaluates under the resolved id, adopting that result only if it is strictly better-informed (more completed agents) or fully passes; the block message lists all evaluated session id(s) for diagnosability. SCOPE-LOCK: fires only on zero payload-sid records — a genuinely partial primary session (some agents completed, some missing) is never masked. Fails open (skips the fallback) if `resolve_session_id` is unavailable. Fails open on state errors. Batch CIA completion gate (Issue #712): blocks `git commit` in batch worktrees when any batch issue is missing `continuous-improvement-analyst` completion; delegates to `verify_batch_cia_completions()` in `pipeline_completion_state.py`; bypass via `SKIP_BATCH_CIA_GATE=1`; fails open on state errors. Batch doc-master completion gate (Issues #786, #837): blocks `git commit` in batch worktrees when any batch issue is missing `doc-master` completion OR when doc-master ran but produced no valid verdict (MISSING/SHALLOW); delegates to `verify_batch_doc_master_completions()` in `pipeline_completion_state.py`; block message differentiates "doc-master never ran" from "ran but produced no valid verdict" to aid diagnosis; bypass via `SKIP_BATCH_DOC_MASTER_GATE=1`; fails open on state errors. pytest-gate ordering enforcement (Issue #838): `pytest-gate` is treated as a virtual agent prerequisite — reviewer, security-auditor, and doc-master are blocked until `pytest-gate` is recorded as completed; `reviewer → security-auditor` ordering is now always enforced (no longer relaxed in parallel mode); bypass via `SKIP_PYTEST_GATE=1` (injects `"pytest-gate"` into the completed set before the ordering check runs); fails open on state errors. **Drain-pending commit gate** (`_check_drain_pending_commit_gate`): fires BEFORE the native-tool fast path for ALL Bash `git commit` invocations when `.claude/local/drain_pending.json` is present (written by `/drain-queue` STEP 3.6 after cluster selection). Blocks any commit whose message does not include `Closes #N` or `Fixes #N` for at least one cluster issue number from the marker. Helper `_extract_commit_message_payload` handles `-m`/`--message`/`-F`/`--file` argv forms and heredoc bodies (via `extract_heredoc_body_for_redirect()` from `edit_tier_classifier.py`); uninspectable payloads (editor mode, `-F -`, `<(proc-sub)`, missing file, unresolved `$`/backtick in heredoc body) fail CLOSED with explicit reasons. The gate NEVER consults marker TTL — long `/implement` runs (2h+ observed) remain covered; TTL is used only by SessionStart cleanup. Marker is cleared by `/drain-queue` STEP 12.5 after post-push `state=CLOSED` verification succeeds. Fails open on `DrainPendingMarker.read()` errors so that import or parse failures do not block legitimate commits. (drain-queue durability plan, round-2 PROCEED) **Phase E (Issue #999)**: when `INTENT_CLASSIFIER_ENFORCE=true`, non-floor checks in 5 sites are wrapped by `_phase_e_skip()` helper, which calls `enforcement_decision.should_skip_enforcement()`. If the session-mode artifact indicates a low-risk intent class (`doc`, `config`, `typo`, `status_query`, `conversation`, `exploration`, `triage`, `remote_ops`, `scratch`), the check is bypassed and a `mode_skip` telemetry row is emitted to `.claude/logs/hook-blocks.jsonl`. Hard-floor hooks (Phase C registry) always fire. Fail-safe: any missing artifact, stale TTL, fail-open classifier, or security-keyword session keeps enforcement hot. **Phase 2 SWE router (Issue #1263 Phase A)**: `_maybe_invoke_swe_router(tool_name, tool_input, session_id)` is called at the Write/Edit interception site. When feature flag `swe_router` is explicitly enabled in `.claude/feature_flags.json`, invokes `semantic_gate.route()` instead of the Phase 1 shadow judge (`semantic_gate.judge()`). Prerequisites: `is_write_to_code_file()` filter must pass (Write/Edit/MultiEdit targeting a code-file extension), and the fire-once-per-turn token from `session_mode.get_user_msg_token()` must differ from the cached token in `_LAST_ROUTE_TOKEN_BY_SESSION` (module-level dict). When `swe_router` is off and `semantic_gate` is on, the Phase 1 shadow judge runs instead (backward compatible). Phase A is log-only — the router NEVER blocks; verdict and `route_target` are logged to `.claude/logs/route/<date>.jsonl`. | SANDBOX_ENABLED, MCP_AUTO_APPROVE, HOOK_EXTENSIONS_ENABLED, PRE_TOOL_PIPELINE_ORDERING, SKIP_PYTEST_GATE, INTENT_CLASSIFIER_ENFORCE, HOOK_TELEMETRY_VERBOSE
| **validate_paid_dependency.py** | PROJECT.md alignment gate on `PreToolUse` for the write tools (`Write|Edit|MultiEdit|NotebookEdit|mcp__.*`). REFUSES with `permissionDecision: "deny"` when a write introduces a paid-API client into **production** Python — enforcing `.claude/PROJECT.md:59` "Paid features — 100% free, MIT licence" and INV-8. Detects by **shape**, not a vendor list: any callable handed a credential-shaped keyword (`api_key`, `api_token`, `access_token`, `secret_key`, `subscription_key`, …), with `def`/`async def` signatures blanked first so parameter defaults are not misread as constructions. Permits test files, docs, and signature defaults containing the same strings. Fails **CLOSED** when `tool_intent` cannot be imported — the classifier's absence means the write is unverified, not permitted. Replaces the inert `validate_project_alignment.py`, which declared `"type": "utility"`, emitted no `deny`, was bound in no settings surface, and refused 0 of 11,872. | SKIP_PAID_DEPENDENCY_CHECK | Issue #1639 |

**Exception**: `CLAUDE_SESSION_ID` is in `PROTECTED_ENV_PREFIX_EXCEPTIONS` as it is non-privileged framework correlation metadata; downstream sanitization via `_SAFE_SESSION_ID_RE` (Issue #1024) handles spoofing-induced log-attribution risk. Revoke this exception if `CLAUDE_SESSION_ID` ever gains auth scope (Issue #1137). Session-id reads at all 8 sites that previously duplicated the "read env var → sanitize → fall back to module-level `_session_id`" pattern are now centralized in `_resolve_session_id_safe(input_session_id)` (Issue #1171), which reads `CLAUDE_SESSION_ID`, sanitizes via `_sanitize_session_id()`, and returns `None` for empty or `"unknown"` values — callers use `... or "unknown"` at the call site to preserve prior behavior.

**Hook Output Format and Visibility Semantics** (Issue #660):

The PreToolUse hook outputs a JSON object with two distinct channels that have different visibility:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask",
    "permissionDecisionReason": "Model-visible reason; used for REQUIRED NEXT ACTION carrots"
  },
  "systemMessage": "User-visible message injected into conversation (optional)"
}
```

- **`permissionDecisionReason`** (model-visible on deny): Read by the model when a tool call is blocked. Block messages include a `REQUIRED NEXT ACTION:` carrot directive telling the model exactly what to do next (e.g., "Run /implement", "Use /create-issue", "Wait for prerequisite agents"). This is the primary enforcement mechanism — the carrot is a model-readable instruction, not a user-facing message.
- **`systemMessage`** (user-visible): Injected into the conversation context as a system-level message visible to the human user. Used for escalated or user-facing notifications. `systemMessage` is omitted when not needed; its presence is optional.

This distinction is fundamental: nudges in `systemMessage` are user-readable but the model cannot act on them. Enforcement directives in `permissionDecisionReason` are model-readable and drive corrective behavior. See MEMORY.md entry "Critical Behavioral Issue" for why this distinction matters.

**unified_pre_tool.py Native Tool Fast Path** (v4.1.0+):
- Native Claude Code tools (Read, Write, Edit, Bash, Task, etc.) skip the 4-layer MCP validation
- Governed by settings.json permissions instead
- Eliminates unwanted permission prompts for standard tools
- **Exception — Agent/Task tools**: Pipeline ordering gate and prompt integrity gate run before extensions for Agent/Task tool calls (Issues #625, #629, #632, #695, #716). Prompt integrity minimum word count fires regardless of pipeline state; baseline shrinkage check only during active pipeline.
- Hook extensions still run for all native tools (extensions can block any tool)

**Project Detection Guard** (Issue #662 — non-native MCP tools only):
- Runs immediately after the native tool fast path, before the 4-layer enforcement stack
- Calls `repo_detector.is_autonomous_dev_repo()` on the current working directory
- Returns `True` only when the autonomous-dev source repo is detected via `plugins/autonomous-dev/.claude-plugin/marketplace.json`. Phase 1 (Issue #1142+) removed the `.claude/.enforce` opt-in path; the `matched_via` audit field is now `"plugin_marker"` | `"none"`.
- Unmanaged projects (no plugin marker): returns immediate allow, skipping all enforcement layers
- Fail-closed: when `repo_detector` is unavailable at load time, `_is_adev_project()` returns `True` so enforcement continues rather than being silently skipped
- Has no effect in autonomous-dev repos — all enforcement layers run normally. Consumer-repo Write/Edit gating is now handled by the default-on production-code gate below (subject to `.claude/.bypass` opt-out).

**unified_pre_tool.py 6-Layer Architecture** (for MCP/external tools in autonomous-dev repos):
- **Layer 0 (Sandbox)**: Command classification (SAFE/BLOCKED/NEEDS_APPROVAL)
- **Layer 1 (MCP Security)**: Path traversal (CWE-22), injection (CWE-78), SSRF (CWE-918)
- **Layer 2 (Agent Auth)**: Pipeline agent detection, authorized agent verification
- **Layer 3 (Batch Approver)**: User consent caching, audit logging (merged into unified_pre_tool.py per Issue #348)
- **Layer 4 (Extensions)**: Project/user-specific checks from `.claude/hooks/extensions/*.py` and `~/.claude/hooks/extensions/*.py` — survives `/sync` and `/install` (see Extension Points section)
- **Layer 5 (Infrastructure Protection)**: Write/Edit to `agents/*.md`, `commands/*.md`, `hooks/*.py`, `lib/*.py`, `skills/*/SKILL.md` are blocked outside the `/implement` pipeline (see Infrastructure Protection section)
- **Layer 6 (Prompt Quality)**: Write/Edit to `agents/*.md` or `commands/*.md` during active pipeline sessions are checked against `prompt_quality_rules.py` anti-patterns; blocks banned persona openers, casual register phrases, and oversized constraint sections (Issue #842)

**Pipeline Ordering Gate** (Issues #625, #629, #632, #686 — native Agent/Task tools only):
- Enforces agent invocation order during active pipeline sessions
- Records agent launch in `pipeline_completion_state.py` before checking prerequisites (Issue #686)
- Reads completion and launch state from `pipeline_completion_state.py` (completions written by `unified_session_tracker.py`)
- Delegates ordering logic to `agent_ordering_gate.py` (pure logic, no I/O)
- Blocks out-of-order agent calls (e.g., implementer before planner/test-master)
- Supports sequential mode (default) and parallel mode (`set_validation_mode()`)
- In parallel mode, distinguishes "running concurrently" (launched, not yet complete — allowed with warning) from "skipped entirely" (never launched — blocked)
- Controlled by env var `PRE_TOOL_PIPELINE_ORDERING` (default: `true`)
- Fails open — ordering check errors never block workflow

**Prompt Integrity Gate** (Issues #695, #716, #723, #789, #791, #794 — native Agent/Task tools only):
- Blocks invocations of compression-critical agents (security-auditor, reviewer, doc-master, implementer, planner) when their prompt falls below the minimum word count
- Minimum word count enforcement fires **regardless of pipeline state** (Issue #716 fix) — this gate is always active for critical agents, not just during `/implement` batches
- Baseline shrinkage check (detecting >= 20% compression vs first-issue baseline — Issue #812 tightened from > 25%) fires **whenever a baseline exists** (Issue #723 — no pipeline-active gate); when no baseline exists, the hook seeds one from the **observed word count** of the current prompt at `issue_number=0` (Issue #759 fix — template-based seeding produced ~1700-word baselines that blocked legitimate ~200-400-word task-specific prompts even with a 0.70 slack factor); template-based seeding via `seed_baselines_from_templates()` is reserved for batch-mode pre-seeding at batch start with appropriate slack
- Uses `validate_prompt_integrity()` which imports `COMPRESSION_CRITICAL_AGENTS` and `MIN_CRITICAL_AGENT_PROMPT_WORDS` from `prompt_integrity.py` (minimum: 80 words)
- Shrinkage check calls `validate_prompt_word_count` with `max_shrinkage=0.20` (20% — Issue #812 tightened from 25%; library default is 15%)
- **Reinvocation context detection** (Issues #789, #791): `_detect_invocation_context()` checks the `PIPELINE_INVOCATION_CONTEXT` env var first, then scans prompt text for markers (`"remediation mode"`, `"re-review"`, `"doc-update-retry"`, `"reduced context"`). When a known reinvocation context (`REINVOCATION_CONTEXTS = {"remediation", "re-review", "doc-update-retry", "research-skip", "fix", "light"}`) is detected, the shrinkage threshold is relaxed — doubled (20% → 40%) for most contexts, 3.0x (→ 60%) for `"fix"` mode (Issue #1358), 2.5x (→ 50%) for `"light"` mode (Issue #1359) — to accommodate naturally shorter re-invocation prompts; the effective threshold is noted in the block message. Passed as `invocation_context` to `validate_prompt_word_count`.
- **Cumulative drift check** (Issue #794): After each check passes, `record_batch_observation(agent_type, issue_number, word_count)` records the observation to `prompt_batch_observations.json`. `get_cumulative_shrinkage(agent_type)` then computes total drift from the first to latest observation; if drift is `>= MAX_CUMULATIVE_SHRINKAGE` (30% — Issue #870 calibrated from 15% to reduce false positives on normal inter-issue variance; operator is `>=`), the invocation is blocked with a REQUIRED NEXT ACTION directive — this catches progressive 3–5% per-iteration compression that individually passes the 20% per-issue threshold.
- `clear_prompt_baselines()` now also calls `clear_batch_observations()` at batch start so cumulative drift state resets alongside baselines
- Block message directs the coordinator to reconstruct the prompt with full context and use `get_agent_prompt_template()` to reload the agent base prompt from disk
- **Fail-open/fail-closed split (Issue #1471)**: both the baseline-shrinkage check and the cumulative-drift check independently distinguish `ImportError` (the `prompt_integrity` module is unavailable) and `IOError`/`OSError`/`json.JSONDecodeError` (baseline/observation file I/O problems) — these stay **fail-open** by design, logged as a warning, and never block the agent — from any *other* exception, which is a **gate-internal bug** and now fails **CLOSED**: it is logged at ERROR with a traceback and the tool call is denied with a `/create-issue` directive. Previously a single blanket `except Exception: pass` around both checks silently waved every agent through on ANY internal error, including a since-fixed `AttributeError` from a dataclass field rename that had made the gate a no-op in production.

**Plan-Exit Gate** (Issue #926 — Layer for native + MCP tools, marker-driven state machine):
- Moved from UserPromptSubmit (`unified_prompt_validator.py`) to PreToolUse here because in-turn model tool calls (e.g., `gh issue create`, `Task(implementer)`) bypass UserPromptSubmit. Marker writer (`plan_mode_exit_detector.py`) and stage advancer (`unified_session_tracker.py`) are unchanged
- Reads `.claude/plan_mode_exit.json` marker on every PreToolUse event; marker auto-deletes when older than 30 minutes; corrupted/timestamp-missing markers also auto-delete
- **stage=plan_exited**: Read/Glob/Grep pass through; `Task(plan-critic)` passes through; Bash on read-only allowlist (`ls`, `cat`, `head`, `tail`, `wc`, `pwd`, `which`, `echo`, `grep`, `rg`, `tree`, `stat`, `file`, `date`, `whoami`, `id`, `uname`; `git status|log|diff|show|branch|blame|ls-files|rev-parse|remote`; `gh issue|pr|repo view|list`, `gh auth status`) passes through. **Issue #1503**: the deny-candidate set is sourced from `tool_intent`'s write registries (`_ti_write_tool_names()` = native `WRITE_TOOLS` + `MCP_WRITE_TOOLS`) instead of a literal `("Write", "Edit", "NotebookEdit")` tuple — this closed a gap where the literal tuple omitted `MultiEdit`. Any registered write tool (Write/Edit/MultiEdit/NotebookEdit/MCP writers), Task with any other subagent, and Bash off-allowlist or with injection metacharacters (`;`, `&`, `|`, `` ` ``, `$`, `<`, `>`, `&&`, `||`, `$(`, `<(`, `<<<`, `<<`, `\n`, `\r`) are denied. MCP tools deny unless on the explicit read-only allowlist — now `tool_intent.MCP_READ_TOOLS` (Playwright snapshot/screenshot/console/network, HuggingFace search/fetch, Gmail list/get, Calendar list/get, Drive list/search/read/metadata, plus the serena LSP read surface: `find_symbol`, `find_referencing_symbols`, `get_symbols_overview`, `read_file`, `list_dir`, etc. — added because the previous module-local `_PLAN_EXIT_MCP_READONLY` frozenset, now deleted, over-blocked serena reads at this stage)
- **stage=critique_done**: `Bash(gh issue create ...)` and `Task(implementer|issue-creator|continuous-improvement-analyst)` are allowed and consume the marker (one-shot); other tools fall through to later validators
- **Race mitigation**: on tentative deny, sleeps 10ms and re-reads the marker; if stage advanced (writer hook fired during the call), allows the tool
- Fails open: any exception during marker read or comparison is treated as no enforcement (never blocks on hook errors)
- Allowlist is explicit (`frozenset`-based), not regex/heuristic — AC #21 prevents false positives like `mcp__foo__find_and_replace` slipping through

**Infrastructure Protection** (scoped to autonomous-dev repos):
- Write/Edit to `agents/*.md`, `commands/*.md`, `hooks/*.py`, `lib/*.py`, `skills/*/SKILL.md` are blocked outside the `/implement` pipeline
- Per-file protection (`PROTECTED_INFRA_FILES`, Issue #980): `plugins/autonomous-dev/config/install_manifest.json` (deployment manifest) is also protected; direct Edit/Write outside the pipeline is blocked. Matched via `endswith` to prevent partial-basename false positives.
- Scoped to autonomous-dev repos (detected via `_is_autonomous_dev_repo()`) — does not affect user projects
- User-facing docs (`README.md`, `CHANGELOG.md`, `docs/*.md`) and most config files (`.json`/`.yaml`) are unaffected; deployment manifests (`install_manifest.json`), policy files, and settings templates are protected
- **Non-bypassable hard floor (Issue #1435)**: `_is_protected_infrastructure` is a registered hard-floor function (`config/hard_floor_hooks.json`). Unlike most other gates, the universal `.claude/.bypass` / `AUTONOMOUS_DEV_BYPASS=1` bypass does NOT waive this check — the bypass block in `unified_pre_tool.py::main()` explicitly falls through to the protected-infra deny gate (including the Issue #1296 coordinator-dispatch-sentinel sub-check) whenever the target path is protected infrastructure and `is_hard_floor()` returns true. `/implement` remains the sole sanctioned path for these edits, with no operator override.

**Production-Code Write/Edit Gate — Default-On, Tier-Aware** (Issue #1142 + Phase 1 polarity flip — `_check_write_pipeline_required`):
- Phase 1 (Issue #1142+) flipped the polarity from opt-IN via `.claude/.enforce` to default-ON subject to `.claude/.bypass` opt-out. The previous `.enforce` marker has been removed.
- Fires when (a) no `/implement` pipeline is active, (b) the file has a production-code extension (`CODE_EXTENSIONS` — `.py`, `.ts`, `.js`, `.go`, `.rs`, `.java`, `.rb`, `.sh`, etc.), and (c) the edit classifies as `fix`, `light`, or `full` via `classify_edit_tier()` (Python AST diff for `.py`; line-count fallback returning `light` as safe default for other languages)
- Tier mapping: `fix` (<20 lines, no AST signal) → `/implement --fix`; `light` (new function / control-flow / 20-99 lines) → `/implement --light`; `full` (new class OR ≥100 lines) → `/implement`. AST edge cases (comment-only, formatting-only, import reordering, type-hint-only, docstring-only) all classify as `fix`.
- Test files (`/tests/`, `/test/`, `test_*.py`, `*_test.py`) are excluded — Tier 0f pass-through
- **Scratch/worktree scoping** (Issue #1408 — Tier 0g/0h, `_is_scratch_path` / `_is_gated_repo_source`): scratch/ephemeral paths (`/tmp/`, `/private/tmp/`, `/var/tmp/`, `/var/folders/`, `~/tmp/`, `~/.cache/`, `$SCRATCHPAD`, per-session `/private/tmp/claude-*/` roots, `.claude/tmp/`) return `tier0_scratch_path` (never gated); paths outside a git worktree or matched by `.gitignore` (checked per-invocation via `git -C <dir> rev-parse --is-inside-work-tree` / `check-ignore`, 1.0s timeout, fail-open to `_is_autonomous_dev_repo` on git error) return `tier0_out_of_tree`. Both checks run before tier classification and apply to both the Write/Edit gate and the Bash-to-code-file gate below. **Security fix**: `_is_scratch_path` previously computed `expanded.startswith(scratchpad.rstrip("/") + "/")` with no floor on the resulting prefix — `SCRATCHPAD=/` (or any all-slash value) reduced that to `startswith("/")`, true for every absolute path, so the exemption covered the entire filesystem for all four `_is_scratch_path` call sites (three pre-existing, plus `_is_code_file_target`, wired in the same fix so scratch writes stop being misclassified as gated code targets). `_is_scratch_path` now rejects degenerate/relative roots (`/`, `//`, `""`, `.`, `..`, `~`) and `SCRATCHPAD` was added to `PROTECTED_ENV_VARS` to block inline/export/env-prefixed spoofing of the variable itself.
- Block message format: `BLOCKED: Write/Edit to code file '<name>' requires the /implement pipeline. File: <path>. Tier: <tier>. REQUIRED NEXT ACTION: Run /implement [--fix|--light] "<description>". Per-repo opt-out: touch .claude/.bypass && git commit.`
- One-shot operator bypass: `touch /tmp/skip_write_pipeline_gate` (consumed on the first *refusal* it buys passage past — mirrors `/tmp/skip_agent_completeness_gate` pattern). Issue #1638: consumption is deferred to the point of refusal and there is exactly one consumer, `_consume_write_gate_bypass`. Previously the sentinel was checked eagerly at the top of both the Write/Edit gate and the Bash gate, so any tool call reaching either — a bare `ls`, a Write to `README.md` or to a test file — silently spent the token and the operator was then refused anyway. The advisory-only Bash-to-code-file gate below never refuses, so it does **not** consume the sentinel. Issue #1408: the consumed-bypass log entry now captures a `reason` string — read from the sentinel file's own contents (e.g. `echo "why" > /tmp/skip_write_pipeline_gate`), falling back to `$WRITE_GATE_BYPASS_REASON`, else `"unspecified"` — so one-shot escapes stay auditable without adding a session-wide off switch. **Issue #1641 — #1638 alone was not sufficient**: `unified_pre_tool.py` is registered for `PreToolUse` with matcher `*` on BOTH the project `.claude/settings.json` and the user's `~/.claude/settings.json`, and Claude Code merges registrations across surfaces and runs every match concurrently — so a single Write can spawn two (or more) concurrent copies of this hook for one tool call. #1638's consumption was idempotent per process, not per logical tool call, so one copy could consume the sentinel and allow while a sibling copy, finding the sentinel already gone, denied — and Claude Code takes the deny. `_consume_write_gate_bypass` now takes a keyword-only `call_key` (from `_write_gate_bypass_call_key`, a hash of the tool payload shared byte-for-byte by every sibling); the winner of an atomic `os.link()`-based claim (`_claim_write_gate_bypass_receipt`) spends and logs the token once, and concurrent siblings honour that receipt (`_read_write_gate_bypass_receipt`, discriminated from a later unrelated tool call via `_HOOK_PROCESS_START_TIME`) without re-consuming the sentinel. **Correction**: siblings do still each log — a deferring sibling calls `_log_write_gate_bypass_deferred(file_path, call_key)`, a distinct `write_gate_operator_bypass_deferred` event separate from the winner's single `write_gate_operator_bypass_consumed` record. An earlier version of this paragraph said siblings honour the receipt "without re-consuming or re-logging" at all — that was true only briefly: the first cut of the #1641 fix granted the bypass on those paths but logged nothing, an omission found and closed in the same change that added this correction. A bypassed write with N concurrent hook copies now produces exactly one `..._consumed` record plus (N-1) `..._deferred` records in `.claude/logs/activity/*.jsonl`, not a single record. This duplicate-invocation topology is general — it is not specific to the bypass sentinel — so any other hook logic with a non-idempotent per-process side effect is exposed to the same class of bug until it adopts the same per-logical-call coordination.
- Durable per-repo opt-out: `touch .claude/.bypass && git commit` (universal `.claude/.bypass` opt-out at line ~4532 short-circuits ALL hooks, including this gate)
- **Bash-to-code-file detection — advisory, not blocking (Issue #1408 Hybrid model)**: `cat > X.py`, `cat >> X.py`, `sed -i ... X.py`, `tee X.py`, `tee -a X.py`, heredocs into code files (`<< 'EOF' > X.py`), `python -c "open('X.py','w')..."`, `python3 -c` with `open()` or `Path.write_text`, base64-decoded heredocs (`echo "<b64>" | base64 -d > X.py`), and `awk '...' > X.py` are DETECTED but no longer hard-block general production-code bash writes — general bash-write detection is unsound (many forms, e.g. `git checkout`, `dd`, `base64 | tee`, bypass the pattern set), so a hard gate here gave a false sense of security while taxing legitimate one-off scripting. The command falls through with a `[hook advisory]` line on stderr recommending the matching `/implement` variant; the event is logged as `bash_code_file_gate_advisory:<tier>` (allow, not deny — the deny cache is intentionally NOT poisoned). The HARD gates remain: Edit/Write (`_check_write_pipeline_required`), protected-infrastructure Bash writes (`_check_bash_infra_writes`, including `git checkout`/`git apply`), and the Issue #803 cross-tool workaround check. `git apply` and `patch < diff` are excluded as user-driven patch tooling.
- **Heredoc-aware Bash detection** (Phase 2, Issues #1153/#1154): heredoc bodies are stripped from the command BEFORE the code-file detection patterns run, so a `gh issue create --body-file <<HEREDOC ... cat > /tmp/x.py ... HEREDOC` payload — whose body happens to contain a `cat > X.py` example — does NOT fire a false-positive block. The strip is sourced from the shared `plugins/autonomous-dev/lib/heredoc_utils.py` (extracted from `unified_pre_tool._strip_heredoc_content`; same shared utility now backs the heredoc-strip in the state-file deletion guards at lines 3705 and 3802, replacing two inline regex duplicates). The regex also tolerates leading tabs before the closing delimiter so the POSIX `<<-` indented-heredoc form is correctly stripped. Pattern 4 (`<<EOF > X.py`) deliberately scans the unstripped command since the redirect is on the heredoc OPENER line. Chained-statement variable assignments such as `OUT=foo.py; cat > "$OUT"` (and the newline-separator variant) are resolved by `_resolve_chained_assignments()` so the downstream regexes see the literal target path — in-scope LHS forms are `"$NAME"`, `${NAME}`, `$NAME`; out-of-scope and acknowledged as residual evasion paths: command substitution `$(...)`, backticks, default-value `${VAR:-default}`, array expansion, concatenation.
- **Sliding-window cumulative escalation** (Phase 2, Issue #1146): closes the multi-Edit splitting gap (a model can split one large edit into N small ones, each of which classifies as Tier-1 `fix` and blocks individually, but cumulative effect crosses the Tier-2 line threshold). Per-`(session_id, file_path)` ring buffer in `pipeline_completion_state.py` records lines-added on each Tier-1 (`fix`) classification (soft FIFO cap = 10, 60-second window). When cumulative lines-added across the window crosses `TIER_LIGHT_LINE_THRESHOLD` (20), the returned tier label is escalated from `fix` to `light` and the directive carries a `cumulative_sliding_window` marker; the ring buffer is then dropped so a single threshold trigger does not keep firing. Backwards compatible: callers that omit `session_id` skip the check entirely. Ring-buffer mutators (`record_tier1_allow`, `clear_tier1_ring_buffer`) run under `_locked_rmw` (Issue #1170) — an external sibling lockfile at `/tmp/pipeline_agent_completions_{key}.lock` serializes the full read-modify-write so two concurrent hook processes cannot silently drop each other's entries. State files are chmod'd to 0o600 on every write (Issue #1169) to prevent exposure on multi-user systems (CWE-732).
- Fails closed on classifier errors (returns `("full", "classifier_error")`) so the most conservative tier directs the model to the full pipeline.

**Agent Completeness Gate — Bypass mechanisms** (Issue #1040 — documentation of pre-existing bypasses in the gate at Issues #802, #853):

The agent-completeness gate blocks `git commit` when required pipeline agents (`reviewer`, `security-auditor`, `doc-master`, `continuous-improvement-analyst`) have not all completed. Three operator-visible bypass mechanisms exist, in order of reliability. The bypass should be reserved for emergencies (hotfixes outside the normal pipeline flow, CI workflow tweaks, README-only changes); for legitimate skips the preferred path is `record_agent_completion()` for the absent agents, which satisfies the gate the right way.

1. **File marker** — `touch /tmp/skip_agent_completeness_gate` as a SEPARATE Bash command first, then retry the commit. The file is a one-shot — the hook consumes it on the first gate check. Works mid-session because the hook walks the filesystem rather than the process environment. **IMPORTANT — chaining with `&&` WILL NOT WORK**: `touch /tmp/skip_agent_completeness_gate && git commit -m "..."` causes the hook's pre-tool phase to run before `touch` executes, so the bypass file is absent when the gate checks. You MUST run `touch` in one Bash call and `git commit` in a separate, subsequent Bash call. (Issue #1212)
2. **Inline command-string env var** — `SKIP_AGENT_COMPLETENESS_GATE=1 git commit ...` prefixes the env var at command position. The hook parses the Bash command string for the prefix (case-insensitive; `skip_agent_completeness_gate=true` is also accepted). Works mid-session because the entire bypass lives in the command string itself.
3. **Process env var (set before claude launch)** — `export SKIP_AGENT_COMPLETENESS_GATE=1` BEFORE launching `claude`. Does NOT propagate mid-session because the hook runs in a separate process from the claude subagent that called `git commit` (Issue #779). This form is the least reliable in practice — prefer (1) or (2) for in-session emergencies.

**Audit trail** — every bypass is logged. `unified_pre_tool.py` writes a row to `.claude/logs/activity/<date>.jsonl` with `decision=allow` and a specific `bypass: ...` reason string (one of `bypass: /tmp/skip_agent_completeness_gate marker present`, `bypass: SKIP_AGENT_COMPLETENESS_GATE inline in command string`, `bypass: SKIP_AGENT_COMPLETENESS_GATE set in process environment`). Auditors can distinguish legitimate skips from gaming by scanning the daily activity log for these reason strings. The CLAUDE_BYPASS_REASON env-var requirement (operator-supplied free-text reason) is a separate hook change deferred to a future issue; for now the form of bypass IS the audit signal.

**Scope** — only the agent-completeness gate at `git commit` time. Does not affect: the pipeline ordering gate, the prompt-integrity gate, the infrastructure-protection gate, the production-code Write/Edit gate, or any PostToolUse hook. For broader emergency bypass see the universal `.claude/.bypass` marker.

**Prompt Quality Gate** (Issue #842 — Layer 6, Write/Edit to agents/*.md and commands/*.md only):
- Blocks writes to `agents/*.md` or `commands/*.md` when the resulting content contains prompt anti-patterns detected by `prompt_quality_rules.py`
- Only enforced during active pipeline sessions (`_is_pipeline_active()` must return true); fails open on all errors
- Content check for Write tool: uses `tool_input["content"]` directly; all anti-patterns are checked against the full new content (full-file semantics — everything is "new")
- Content check for Edit tool: reads the existing file from disk, applies the replacement in memory, then runs diff-aware anti-pattern checks on the post-edit content (Issue #1038 — see below); if the file cannot be read, the check is skipped (fail-open)
- **Diff-aware Edit checks** (Issue #1038): For Edit operations, persona and casual-register checks subtract pre-existing violations so that edits which do NOT introduce new anti-patterns in the touched section are not blocked by pre-existing prose in untouched sections. Constraint-density check uses `check_constraint_density_diff(old_content, new_content)` from `prompt_quality_rules.py`, which only flags sections that are (a) new AND oversized, or (b) had their bullet count increased into over-threshold territory. Sections pre-existing at or above threshold that the edit does not worsen are exempt.
- Anti-patterns checked: (1) banned persona openers (`You are an expert/senior/world-class/renowned/leading/top`) — legitimate role assignments like `You are the **agent** agent` are allowed; (2) casual register phrases (`check for`, `look for`, `make sure`, `try to`, `you should`, `feel free`) that weaken enforcement; (3) oversized constraint sections exceeding 8 bullet items per `##`-level section — `##` sections whose headers contain `FORBIDDEN`, `HARD GATE`, `HARD-GATE`, `REQUIRED`, or `MUST NOT` (case-insensitive) are exempt from this count, as these are load-bearing enforcement lists rather than prose (Issue #1119)
- Block message lists the first three violations (plus count of remaining), and includes a `REQUIRED NEXT ACTION` directive to use formal directive language (`MUST`, `REQUIRED`, `FORBIDDEN`) and keep constraint sections under the threshold
- Rule library (`prompt_quality_rules.py`) is loaded via `importlib.util.spec_from_file_location` at check time; if the module file is missing or import fails, the gate is skipped (fail-open)
- Runs as Layer 6 in the Write/Edit enforcement stack, after Infrastructure Protection (Layer 5) and the Agent Denial Fallback Guard

**Agent Denial Fallback Guard** (Issue #750):
- When the Prompt Integrity Gate denies an Agent/Task invocation due to prompt shrinkage, the orchestrator may fall back to direct Write/Edit calls to the same protected infrastructure files
- `_record_agent_denial(agent_type)` writes a session-scoped JSON state file at `AGENT_DENY_STATE_DIR` (`/tmp/adev-agent-deny-{session_id}.json`) immediately after any prompt-integrity denial
- `_check_agent_denial()` is called at the top of every Write/Edit check; if a denial record exists within `AGENT_DENY_TTL` (300 seconds) for the same session, the Write/Edit to a protected infrastructure path is blocked
- Block message includes a `REQUIRED NEXT ACTION` directive telling the orchestrator to reload the agent prompt template via `get_agent_prompt_template()` and retry the Agent call with a full-length prompt
- Non-infrastructure paths (docs, config, test files) are unaffected — the guard only activates for the same `_is_protected_infrastructure()` paths that the base infrastructure gate covers
- Fails open on all state file errors (`_record_agent_denial` swallows exceptions; `_check_agent_denial` returns `None` on any error) to avoid blocking legitimate work
- **Auto-cleanup of stale deny files** (Issue #1051): `_check_agent_denial` now deletes deny files that belong to a different session (session-id mismatch) or whose timestamp exceeds `AGENT_DENY_TTL`, using a fail-open `os.unlink` (OSError is swallowed). This prevents stale `/tmp/adev-agent-deny-*.json` files from accumulating across pipeline runs and requiring manual `rm` to unblock agents. Only deny files that are actively enforced (same session, within TTL) are preserved.

**Cross-Tool Write-to-Bash Workaround Detection** (Issue #803):
- When a Write/Edit to a protected infrastructure file is denied, `_update_deny_cache(file_path)` is now called at both denial sites — the main infrastructure protection block and the Issue #750 agent-denial-workaround block — so the denied path is recorded in the deny cache at `/tmp/.claude_deny_cache.jsonl`
- Subsequent Bash commands that attempt to write the same file (via heredoc, redirect, `tee`, `echo`, or Python `-c` write patterns) within the 60-second deny window are detected by extracting write targets with `_extract_bash_file_writes()` and checking each against `_check_deny_cache()`
- A match within the 60-second window is blocked with a "cross-tool workaround detected" message including a `REQUIRED NEXT ACTION` directive
- `_check_deny_cache(file_path)` now also falls back to basename matching (`Path.name`) when the full path does not match, handling cross-format path references (absolute vs relative)
- Closes the bypass pattern where an agent switches from Write/Edit to a Bash heredoc after an infrastructure protection denial

**Pipeline State File Deletion Guard** (Issue #804):
- Detects `rm`, `unlink`, `truncate`, redirect-to-empty (`> file`), `python os.remove`/`os.unlink`/`Path.unlink` targeting pipeline state files during active pipeline runs
- Protected state file patterns: `<repo>/.claude/local/implement_pipeline_state.json` and `/tmp/implement_pipeline_state.json` (both covered via `LEGACY_SENTINEL_LITERALS` since Issue #1206), `/tmp/.claude_deny_cache.jsonl`, `/tmp/pipeline_completion_state_*.json`, `/tmp/pipeline_secrets/*`
- `_check_bash_state_deletion(command)` is the detection function; `_is_state_file(path)` is the helper that matches a path against the protected patterns
- Before scanning, the function strips heredoc bodies (`<<'EOF'...EOF`, `<<EOF...EOF`, `<<"EOF"...EOF`, `<<-EOF...EOF`) and `--body`/`--message` quoted argument values from the command string to prevent false positives when prose text in commit messages or issue descriptions happens to mention state file paths (Issue #866)
- Deleting state files during an active pipeline would bypass enforcement by clearing the ordering gate state, deny cache, or pipeline secrets — this guard closes that vector
- Fails open: only fires when the pipeline is active (state file present); passes when no pipeline is running
- Escape hatch: `PIPELINE_CLEANUP_PHASE=1` (or `true`) allows state file deletion — used by STEP 15 / STEP B4 coordinator-authorized cleanup after batch completion (Issue #865)

**Spec Test Deletion Scope Guard** (Issue #790):
- Blocks deletion of `tests/spec_validation/test_spec_issue{N}_*.py` files that belong to a different issue than the current pipeline run
- Detection covers: `Write` tool with empty/whitespace content (truncation vector), `rm`, `unlink`, `truncate`, redirect-to-empty (`> file`), `python os.remove`/`os.unlink`/`Path.unlink`, and `mv` to a non-`tests/archived/` destination
- `_check_spec_test_deletion_scope(file_path)` extracts the issue number from the filename, reads `_get_current_issue_number()`, and blocks when the two differ
- `_extract_bash_spec_test_targets(command)` parses Bash command strings to find spec test paths targeted by deletion or move operations
- Escape hatch: `SKIP_SPEC_DELETION_GUARD=1` bypasses the guard for intentional cross-issue cleanup
- Fail-open: when no pipeline context exists (`current_issue == 0`), the guard passes; detection errors never block
- Required next action on block: `mv {file_path} tests/archived/` — spec tests from other issues must be archived, not deleted

**GitHub Issue Creation Gate** (Issue #599, hardened Issues #1203, #1215):
- Direct `gh issue create` in Bash is blocked outside approved contexts to enforce the `/create-issue` pipeline (research, duplicate detection, proper formatting)
- **Argv-position-aware match (Issue #1215)**: the direct-match path (`_detect_gh_issue_create`) uses `shlex.split` to tokenize the command into statements and argv tokens, then requires that `gh` is the leading verb (argv[0] after any leading env-var assignments) AND the next two tokens are `issue` and `create` (case-insensitive). Pre-#1215 the match was a raw substring scan on the quote-stripped command, which produced false positives whenever the substring appeared in prose inside a `git commit -m "..."` body that escaped the simple quote stripper (shell-escaped quotes, ANSI-C `$'...'` quoting, or unquoted prose between argv tokens). The #1203 and #1204 commits themselves were blocked by this and required `git commit -F /tmp/file` workarounds plus body-rewriting with neutral phrasing. The fix mirrors the shlex-aware treatment that #1203 added to the bypass detector. Body/message argument VALUES (`-m`/`--message`/`-F`/`--file` for git; `--body`/`--title`/`--body-file` for gh) are stripped via the hoisted `_strip_body_arg_values` helper before tokenization so substring matches inside argument values cannot fire. Statement boundaries (`;`, `&&`, `||`, `|`, `&`, newline) outside quoted regions are respected, so multi-statement forms like `cat <<EOF ... EOF; gh issue create ...` (where the gh call is the leading verb of a later statement) are still caught. On `shlex.ValueError` for the whole command (unterminated quotes), the path falls back to the raw-regex scan on the quote-stripped command so true bypass forms with garbled syntax remain blocked (fail-closed).
- Allow-through 1: an active `/implement` pipeline is present (`<repo>/.claude/local/implement_pipeline_state.json`, resolved by `get_legacy_sentinel_path()` — was `/tmp/implement_pipeline_state.json` before Issue #1206)
- Allow-through 2: the current agent is `continuous-improvement-analyst` or `issue-creator` (authorized for direct issue creation)
- Allow-through 3 (Issue #630, #647, #663): a command context file exists at `GH_ISSUE_COMMAND_CONTEXT_PATH` (`/tmp/autonomous_dev_cmd_context.json`) with a `command` field set to one of `create-issue`, `plan-to-issues`, `improve`, `refactor`, `retrospective`, or `plan` — the hook auto-writes this file in the `NATIVE_TOOLS` fast path when it detects a `Skill` tool invocation for one of these commands (before any downstream Bash `gh issue create` check fires); uses file mtime for age check (harder to spoof than an embedded JSON timestamp). **Prior-call ordering contract (#1203)**: the context file MUST be written in a separate Bash tool call prior to any `gh issue create` call — bundling write and create into one Bash invocation leaves the context absent at hook-evaluation time and blocks. Note: the prior marker-file allow-through (Allow-through 3 in pre-#1203 versions) was removed in #1203 because it was dead code — nothing writes the marker file anymore (writes are blocked by the Marker File Creation Guard since #627)
- Allow-through 4 (Issue #1383): `gh issue create --repo <owner>/<repo>` (or `-R <owner>/<repo>`) targets a repo owned by a DIFFERENT owner than the current repo's `origin` remote — a legitimate upstream-filing action the `/create-issue` pipeline does not cover. `_gh_issue_create_target_is_cross_owner()` parses the `--repo`/`-R` flag (last occurrence wins on duplicates, `--repo=` / `-R=` forms supported) and resolves the current owner via `git remote get-url origin` + `dependabot_tracker.parse_owner_repo()`; the owner comparison is case-insensitive. Fails CLOSED (stays blocked) on any ambiguity — missing `--repo`/`-R`, a bare owner-less target, an unresolvable current owner, or a same-owner target all keep the gate active; only a confidently-parsed, confirmed cross-owner target is allowed through.
- Block message directs the user to `/create-issue` or `/create-issue --quick`; also includes a FORBIDDEN clause explicitly prohibiting suggestions to run `! gh issue create` or any other bypass method (the `!` prefix runs commands outside the hook system)
- Fails open on any detection error to avoid blocking legitimate work

**Daily Aggregate Direct-Filing Guard** (Issues #1369, #1374 — called after the GitHub Issue Creation Gate when `_is_issue_command_active()` returns False):
- `_detect_daily_aggregate_direct_filing(command_str)` blocks direct `gh issue create` calls whose `--title` begins with a guarded prefix unless the `triage-aggregate` command context marker is active
- **Guarded prefixes** (exact `startswith` match on extracted title value):
  - `"Auto-triage findings —"` (em-dash) — auto-triage daily aggregate
  - `"[CRITICAL] AI triage —"` (em-dash) — critical-severity triage aggregate
  - `"[drain-stuck] watchdog"` (Issue #1374) — drain-watchdog stuck-detector aggregate; matches both legacy colon-format `"[drain-stuck] watchdog: <reason>"` and new date-suffix format `"[drain-stuck] watchdog YYYY-MM-DD"`
- **Sanctioned path**: call `plugins/autonomous-dev/lib/daily_aggregate_manager.py::open_or_supersede_daily_aggregate(repo, label, title_prefix, body, today_utc)` instead — same-UTC-day fires edit the existing aggregate in-place; prior-day open aggregates are superseded with a `Superseded by #<new>` comment before a new one is created
- **Title extraction**: three scan forms — CLI-arg `--title "val"`, escaped-quotes `--title \"val\"`, and list-literal `'--title', 'val'`
- Fails open on detection errors; never blocks when the active command marker is `triage-aggregate`

**Marker File Creation Guard** (Issue #627):
- Blocks direct creation of the marker file `autonomous_dev_gh_issue_allowed.marker` outside approved contexts, closing the bypass where manually writing the marker file would short-circuit the gh issue create gate
- Uses deny-by-default logic: if the substring `autonomous_dev_gh_issue_allowed` appears anywhere in the command, the command is blocked unless the operation is provably read-only or a delete — this prevents bypass via novel write methods (e.g. `python3 -c "..."`, `dd`, `install`, `os.open`) that a fixed allowlist would miss
- Allowed (not blocked): read-only verbs (`cat`, `ls`, `stat`, `test`, `head`, `tail`, `wc`, `file`, `readlink`, `[`), delete (`rm`), reference-only mentions (`grep`; `echo`/`printf` without a redirect targeting the marker file)
- Allow-through 1: active `/implement` pipeline (the pipeline legitimately writes the marker when authorizing issue creation)
- Allow-through 2: agent name in `GH_ISSUE_AGENTS` (`continuous-improvement-analyst`, `issue-creator`)
- Allow-through 3: issue-creating command is active (`_is_issue_command_active()`) — commands such as `/create-issue`, `/plan-to-issues`, `/improve`, `/refactor`, `/retrospective`, `/plan`
- No marker-file allow-through (circular — the guard protects the marker itself)
- Fails open on any detection error to avoid blocking legitimate work

See [SANDBOXING.md](SANDBOXING.md) for complete security architecture.

**plan_gate.py** (Issue #814, #1503 — PreToolUse, matcher `Write|Edit|MultiEdit|NotebookEdit|mcp__.*`):
- Blocks complex write operations when no valid plan exists in `.claude/plans/`
- **Transport-independent since Issue #1503**: the tool test is `tool_intent.is_write()`, not a hard-coded `("Write", "Edit")` tuple, so `MultiEdit`, `NotebookEdit`, and MCP editors (`mcp__serena__*`) are gated identically
- Simple edits (fewer than 100 lines of changed content, measured via `tool_intent.changed_content()` for every transport) are exempt — only non-trivial changes require a plan
- Documentation files (`.md`, `.rst`, `.txt`, docs/ directory) are always exempt
- Validates plan structure: requires `## WHY + SCOPE`, `## Existing Solutions`, and `## Minimal Path` sections
- Plans older than 72 hours trigger a warning (stderr only, non-blocking) — expired plans do not block work
- Escape hatch: `SKIP_PLAN_CHECK=1` bypasses all checks
- Fails open: any exception or invalid input results in allow
- Block message includes `REQUIRED NEXT ACTION` directive pointing to `/plan`

**enforce_file_organization.py** (Issue #1034, #1503 — PreToolUse, matcher `Write|Edit|MultiEdit|NotebookEdit|mcp__.*`):
- Blocks write operations that would create files at the repo root outside an allow-list (e.g. `README.md`, `pyproject.toml`, `CLAUDE.md`)
- **Transport-independent since Issue #1503**: the tool test is `tool_intent.is_write()` (not a hard-coded `("Write", "Edit")` tuple); write target resolved via `tool_intent.write_targets()`, which also resolves MCP path keys (`relative_path`, `path`)
- Allow-list sources: built-in defaults (consolidated standard root files), plus `plugins/autonomous-dev/templates/project-structure.json` under `["structure"]["Root directory"]["allowed_files"]` (falls back to `.claude/templates/project-structure.json` for installed-only repos)
- Hardcoded extension allow-list at root: `.json`, `.yaml`, `.yml`, `.toml`, `.cfg`, `.ini`, `.lock` (config files always pass)
- Hidden files (basename starts with `.`) always pass
- Files in any subdirectory always pass — the gate is repo-root-only
- Block message includes a suggested folder when the extension maps to a standard directory: `.py`/`.sh` → `scripts/`, `.md` → `docs/`, `.log`/`.jsonl` → `logs/`, `test_*.py`/`*_test.py` → `tests/unit/`
- Block message format: `File placement violation: <basename> cannot be created in repo root. Suggested location: <folder>/<basename>. REQUIRED NEXT ACTION: Re-issue Write with file_path=<folder>/<basename>.`
- Escape hatch: universal `AUTONOMOUS_DEV_BYPASS=1` env var or `.claude/.bypass` file (Issue #969)
- Stdlib-only, standalone (not wired into `unified_pre_tool.py`); fails open on every error path
- Repo root resolved via `git rev-parse --show-toplevel` — non-git contexts skip enforcement
- Replaces the GenAI-based `archived/enforce_file_organization.py`; deterministic heuristics only, no `--fix` mode

### PreCommit

| Hook | Purpose | Key Env Vars |
|------|---------|--------------|
| **auto_format.py** | Code formatting (black + isort, prettier) | AUTO_FORMAT |
| **auto_test.py** | Run related test files | AUTO_TEST |
| **security_scan.py** | Secrets detection, vulnerability scanning | SECURITY_SCAN |
| **enforce_tdd.py** | TDD workflow enforcement (tests before code) | ENFORCE_TDD |
| **enforce_prunable_threshold.py** | Blocks commits when prunable test count exceeds `PRUNABLE_THRESHOLD` (100). Uses `TestPruningAnalyzer` for local-only AST scanning (no network calls). Imports threshold from `test_lifecycle_manager`. Graceful degradation on errors (exit 0). Supports `SKIP_PRUNABLE_GATE=1` env var. Strict-mode only. (Issue #863) | SKIP_PRUNABLE_GATE |
| **enforce_regression_test.py** | Blocks `fix:`, `bugfix:`, and `hotfix:` commits when no test files are staged. Uses `bugfix_detector.is_bugfix_commit()` to detect prefixes. Fails open when `bugfix_detector` library is unavailable. Follows stick+carrot pattern: block message includes `REQUIRED NEXT ACTION` directing the committer to add a failing-then-passing regression test. Exception: pass `--no-verify` and document the covering test in the commit body when an existing test already covers the regression. (Issue #737) | — |
| **enforce_orchestrator.py** | PROJECT.md alignment validation | — |
| **validate_project_alignment.py** | PROJECT.md forbidden sections detection | VALIDATE_PROJECT_ALIGNMENT |
| **validate_command_file_ops.py** | Commands execute Python libs, not just describe them | — |
| **validate_session_quality.py** | Session log completeness | — |
| **auto_fix_docs.py** | Documentation consistency auto-fixes | AUTO_FIX_DOCS |
| **validate_claude_md_size.py** | Context-file guard on `PostToolUse` for the write tools. WARNS when a context file drifts past target — CLAUDE.md > 200 lines (Anthropic best practice), `~/.claude/CLAUDE.md` > 200 lines (loads in every repo), `.claude/PROJECT.md` > 150 lines (content-allocation target), `~/.claude/projects/<slug>/memory/MEMORY.md` > 200 lines (Anthropic auto-load threshold). REFUSES with `{"decision": "block"}` past a 1.5x hard ceiling, and refuses a local CLAUDE.md section that restates a rule already in the global CLAUDE.md. For the two repo-tracked files (`CLAUDE.md`, `.claude/PROJECT.md`) the effective block limit is a per-repo ratchet, `max(hard ceiling, the file's line count at git HEAD)`: a repo that inherited an oversized file is refused only when the file grows past its own committed size, not on every edit; when the mark is in force, warn and block both move to it. Worktrees, submodules, and context files committed as symlinks get no ratchet. Acts only when the write targeted one of the four tracked files; each check runs independently and missing files are skipped silently. | Issues #1639, #1648 |

### SubagentStop

| Hook | Purpose | Key Env Vars |
|------|---------|--------------|
| **unified_session_tracker.py** | Session logging, pipeline tracking, progress updates. Reads stdin JSON from Claude Code, computes duration_ms, validates agent_transcript_path, writes JSONL for pipeline_intent_validator ghost detection. Status determination uses `CLAUDE_AGENT_STATUS` env var as authoritative signal when present; falls back to `_determine_success()` text scan only when the env var is absent (Issue #541). Session isolation: when `CLAUDE_SESSION_ID` is set, both `SessionTracker` file selection and `check_pipeline_complete()` filter to the matching session, preventing cross-session contamination when multiple batches run on the same day (Issue #594). Each JSONL entry now includes a `plugin_version` field (e.g. `"3.50.0 (abc1234)"`) populated via `version_reader.get_plugin_version()` for diagnostics and issue triage (Issue #630). **Word count aggregation** (Issue #872/#907): `result_word_count` in JSONL entries is computed by `_count_words_in_transcript()`, which iterates all assistant turns in the JSONL transcript file and sums word counts across both str-content (legacy) and list-of-blocks (modern) content shapes; falls back to splitting the single last-message `agent_output` string when no transcript path is available. This captures multi-turn subagent output rather than only the final turn. **Transcript flush settling** (Issue #1179): SubagentStop fires while Claude Code may still be asynchronously writing the JSONL transcript. If the first read of the transcript returns fewer than `_TRANSCRIPT_FLUSH_THRESHOLD_WORDS` (10) words, `_count_words_in_transcript()` calls `_wait_for_transcript_flush()` to poll the file size until stable (up to 2 seconds, checking every 100ms, requiring 3 consecutive equal-size samples), then re-reads. Adds ~0ms when the file is already flushed, ~300ms in the race case. Fails open (returns whatever is on disk) when the file is missing or an `OSError` occurs. **SubagentStop cross-hook correlation** (Issue #1087): at SubagentStop time, calls `subagent_invocation_cache.pop_invocation(session_id, preferred_subagent_type=agent_type_from_stdin)` to recover the cached `subagent_type` and `start_time` that were written by `session_activity_logger.py` at PreToolUse. If the cache hit provides a non-empty `subagent_type` and a valid `start_time`, `duration_ms` is computed as `(time.time() - start_time) * 1000`. Falls back to `_compute_duration_ms()` (agent_tracker method) when the cache is empty or stale. This fixes the root cause of `subagent_type=""` and `duration_ms=0` in SubagentStop JSONL entries, which broke ghost detection, agent completeness gates, and timing analysis. Then calls `record_agent_completion()` from `pipeline_completion_state.py` with the resolved `agent_type`. **SubagentStop dedup guard** (Issue #1176): SubagentStop fires twice per agent due to dual hook registration in some settings templates (both `~/.claude/settings.json` and `.claude/settings.json` register the hook). The duplicate firing pollutes JSONL logs, double-counts durations, and triggers downstream consumers (ghost-agent detection, pipeline completion state, plan-critic stage advance) twice. The guard atomically claims a file-backed marker in `/tmp` keyed by `sha256(agent_transcript_path)[:16]` (falling back to `sha256(session_id:agent_name)[:16]` when the transcript path is empty). The claim uses `os.open(O_CREAT|O_EXCL)` — only one caller can succeed; the duplicate sees `FileExistsError` and returns `False`. On duplicate, the hook writes a JSONL entry with `subagent_type=f"__dedup_skip__:{agent_name}"` (debug-only, zero duration/word-count) and exits 0. Markers expire after a TTL of 300 seconds; stale markers are swept by a background cleanup gated to at most once per 60 seconds. Fails OPEN (allows through) on unexpected errors to prevent legitimate firings from being silently dropped. Root-cause fix delivered by Issue #1183: `templates/settings.local.json` now carries an empty `hooks: {}` block, so hooks live exclusively in `settings.json` (written by `sync_settings_hooks.py`). A deploy-time audit gate (`strip_duplicate_hooks.py --audit`) is wired into `scripts/deploy-all.sh` `validate_local()` as check #12 and hard-fails on any future duplicate registration. **Staged Plan-Exit Pipeline**: when `agent_name == "plan-critic"`, calls `_advance_plan_mode_stage()` to attempt advancing the `.claude/plan_mode_exit.json` marker from `plan_exited` to `critique_done`, unlocking `/implement` and related commands in `unified_pre_tool.py` (Issue #926 — enforcement moved from `unified_prompt_validator.py` to `unified_pre_tool.py` PreToolUse). **PROCEED verdict gate** (Issue #927, #1264): `_advance_plan_mode_stage()` now requires `.claude/plan_critic_verdict.json` to exist with `"verdict": "PROCEED"`, a timestamp at least as recent as the plan-mode-exit marker, AND required fields `reasoning` and `axis_scores` present before advancing the stage. REVISE and BLOCKED verdicts leave the gate closed; the verdict file is retained so the plan-critic can re-run. When a PROCEED verdict is accepted, the verdict file is consumed (deleted) to prevent replay. The verdict file is written by the plan-critic agent at the end of every critique round. When the stage successfully advances from `plan_exited` to `critique_done`, the hook emits a `systemMessage` suggesting next steps: `"/plan-to-issues --quick` to create GitHub issues from this plan"` and `"/implement` to begin implementation directly"`. This is an informational nudge only — non-blocking. **Sentinel heartbeat check** (Issue #989): immediately after `record_agent_completion()` succeeds, calls `ensure_sentinel_heartbeat(session_id)` from `pipeline_completion_state.py`. If the `<repo>/.claude/local/implement_pipeline_state.json` sentinel (resolved by `get_legacy_sentinel_path()`; was `/tmp/implement_pipeline_state.json` before Issue #1206) is missing or its `session_id` field does not match the current session (e.g., because `clear_stale_state()` in `hook_recovery.py` deleted it when a subprocess ran under a different `CLAUDE_SESSION_ID`), a minimal sentinel `{"session_id": ..., "recovered": True, "recovered_at": "<iso>"}` is recreated and `[SENTINEL-HEARTBEAT-MISSING] state_path=... recovering_for_session=...` is emitted to stderr. The function never raises — all error paths are fail-open so that a failed heartbeat never blocks agent completions. (Issue #879, #1087, #1176, #989) **Background agents never fire this hook** (Issue #906/#882, Anthropic #25147 — won't-fix platform limitation): agents launched with `run_in_background=true` never trigger `SubagentStop`; their completion is recorded coordinator-side via a direct `record_agent_completion()` call in `commands/implement.md`, not by this hook. **Transcript-based agent-type recovery** (Issue #1396): when both the payload and the #1087 PreToolUse cache omit `agent_type`, `_resolve_agent_type_from_transcript()` best-effort-scans the first ~20 JSONL lines of the subagent transcript for an identity field (`agent_type`/`subagent_type`/`agentType`, top-level or nested under `session_meta`/`meta`/`summary`); returns `""` on any parse failure since the transcript schema is undocumented (Anthropic #27423/#27755). **Heartbeat drop** (Issue #1396): internal/tool-level SubagentStop firings with no usable identity (empty `agent_type` AND `duration_ms == 0` AND no #1087 cache hit AND no transcript-resolved identity) are dropped (`return 0`, never recorded) rather than logged as ghost/ambiguous agents — this eliminates roughly 95 of ~113 noise SubagentStop events observed per run; the drop check runs after `duration_ms` is computed and before the #1414 phantom-dedup block so it never perturbs `_PHANTOM_DEDUP_CACHE`. **Unattributable-firing guard** (Issue #1436): a firing can survive the #1396 heartbeat drop (e.g. non-zero `duration_ms` or substantive output) while still carrying no real identity — `agent_name` empty, whitespace-only, or the literal `"unknown"`. `_is_unattributable(agent_name)` checks for this class BEFORE the #1414 `phantom_key` is ever computed, closing the gap where keying on `(session_id, "")` could collapse two distinct empty-identity firings into one (suppressing a genuine completion) or let an unattributable firing pollute the agent-completeness gate. On a match, the hook writes a `subagent_type=f"__unattributable__:{agent_name or ''}"` JSONL audit entry (mirroring the `__dedup_skip__` convention) and never inserts the event into `_PHANTOM_DEDUP_CACHE`; it still calls `record_agent_completion()` for #1396 backward-compatibility, but `_is_gate_countable_agent()` in `pipeline_completion_state.py` makes that call a no-op (Layer-1 guard — the completion is never persisted or gate-counted). **Agent-dispatch sentinel clear relocated + compare-and-delete** (Issue #1484): the `agent_dispatch_sentinel.clear()` call (Issue #1296) was moved from before to after the `subagent_invocation_cache.pop_invocation()` call so the recovered `generation` token is available; it is passed as `clear(expected_generation=...)`, which no-ops instead of unlinking when a *different* dispatch's token is found in the sentinel payload (closing the #1467 ABA race). `session_id` resolution is now env-first (`CLAUDE_SESSION_ID` before the payload `session_id` field) to symmetrically match the writer in `session_activity_logger.py`, so the cache-key lookup reliably hits. **Phantom-`SubagentStop` classification** (Issue #1512): before the #1087 cache pop (and therefore before any #1484 generation-token compare-and-delete can run), `_is_phantom_subagent_stop(agent_transcript_path_raw)` classifies the firing. A `SubagentStop` whose `agent_transcript_path` names a file that does not exist on disk — even after a short `PHANTOM_TRANSCRIPT_GRACE_SECONDS` (0.5s, polled every `PHANTOM_TRANSCRIPT_POLL_SECONDS` = 0.05s to absorb a hypothetical async-flush race) — is a phantom: measured over 102 typed stops, this split 50 phantoms from 52 real completions with zero overlap. Before this fix, the phantom always won the #1087 cache and collected the live dispatch's generation token, then used it to satisfy `agent_dispatch_sentinel.clear(expected_generation=...)`, disarming a sentinel whose dispatch was still running. An **empty** transcript path, or one that resolves **outside `~/.claude`**, is deliberately classified as UNKNOWN rather than phantom (over-broadening is the worse failure — it would re-break the #1387/#1412 false-negative class and misclassify genuine stops). On a phantom classification, the hook skips BOTH the invocation-cache pop and the `agent_dispatch_sentinel.clear()` call, and — for typed (non-`_is_unattributable`) phantoms only — writes a `subagent_type=f"__phantom_stop__:{agent_name}"` JSONL audit entry (zero duration/word-count, mirroring the `__dedup_skip__`/`__unattributable__` convention so it stays inert for `agent_output_health.py` and the completeness gate); `record_agent_completion()` is NOT called for a phantom. Diagnostic: `scripts/measure_phantom_subagent_stops.py` re-runs the phantom/real classification against `.claude/logs/activity/*.jsonl` to confirm the hit/miss inversion post-deployment (see [SCRIPTS.md](SCRIPTS.md)). | TRACK_SESSIONS, TRACK_PIPELINE, CLAUDE_AGENT_STATUS, CLAUDE_SESSION_ID |

#### Not a hook: the mutation-witness harness (Issue #1660)

`scripts/mutation_witness_gate.py` and `scripts/mutation_witness.py` are written
to the `SubagentStop` contract but are **not hooks**. They are in `scripts/`
beside their sibling harness `scripts/integration_ceiling.py`; there is no
`.hook.json` sidecar, no entry in either `install_manifest.json`, and no
registration in any settings surface. An earlier revision placed the driver in
`hooks/` and the library in `lib/`; two shipped ratchets measured both as
defects (`test_no_new_unreachable_refusers`, `test_no_new_unreached_library_modules`)
and were right — a file that can refuse while nothing invokes it, and a module
whose only importer is itself pinned unreached, are exactly the states those
instruments exist to surface.

The mechanism works and is proven refusing AND permitting under test. **Issue
#1660's enforcement loop is OPEN, not closed**: nothing in this repo writes a
mutation claim, so a blocking `SubagentStop` gate could only produce false
refusals. Landing a producer means editing `agents/test-master.md` and the
coordinator wiring — a separate change with its own review. The unwired state is
locked by `TestDeliberatelyNotShipped` and `TestHonestlyUnwired`, which go red
the day a producer or a registration lands. Registration instructions are in the
driver's module docstring.

#### Not a hook: the append-writer ratchet (Issue #1718)

`tests/unit/lib/test_append_writer_ratchet.py` is a shrink-only ratchet pinning
the count of modules under `plugins/autonomous-dev/{lib,hooks}` that open a log
file in append mode — not itself a hook, and not shipped in
`install_manifest.json`. It is enforced as a step in the `smoke` job of
`.github/workflows/ci.yml`, not on any lifecycle event: `tests/unit/` currently
carries standing failures (#1719) that would make a refusal placed there
unobservable, while `summary` gates merge on the smoke job's result
independently. The pinned count and the AST detector that produces it are
defined in the test module itself, not restated here — see the module docstring
for the current figure and the sixth-in-a-family ceiling/high-water-mark design
it shares with `test_vacuous_test_ratchet.py`, `test_anthropic_client_ratchet.py`,
`test_hook_reachability_ratchet.py`, `test_refusal_sink_ratchet.py`, and
`test_context_file_guard_ratchet.py`.

### PostToolUse

| Hook | Purpose | Key Env Vars |
|------|---------|--------------|
| **plan_mode_exit_detector.py** | Detects `ExitPlanMode` tool calls and writes a marker at `.claude/plan_mode_exit.json`. Implements the **Staged Plan-Exit Pipeline**: stage advances from `plan_exited` → `critique_done` when the plan-critic SubagentStop fires (via `unified_session_tracker.py`). **AC#3 fast-path (Issue #937/#970, #1264 — substantive validation)**: before writing the marker, reads `.claude/plan_critic_verdict.json`; if plan-critic already produced a PROCEED verdict with required fields `reasoning` and `axis_scores` before ExitPlanMode fired, the marker is born with `stage: "critique_done"` (not `"plan_exited"`), the verdict file is consumed, and the systemMessage informs the model that the pipeline is ready. Without a PROCEED verdict the marker is born with `stage: "plan_exited"` as before. **`unified_pre_tool.py` enforces the two-stage pipeline at PreToolUse** (Issue #926 — moved from `unified_prompt_validator.py`): in `plan_exited` state Write/Edit/non-allowlisted Bash/non-readonly-MCP are denied until plan-critic runs; in `critique_done` state `Bash(gh issue create ...)` and `Task(implementer|issue-creator|continuous-improvement-analyst)` are allowed and consume the marker. Emits a `systemMessage` on ExitPlanMode instructing the model to invoke plan-critic before proceeding (or, on the fast-path, that the pipeline is ready). Auto-expires after 30 minutes. **Scope (Issue #1361 — default-ON polarity flip)**: enforcement fires in every repo by default (previously scoped to autonomous-dev repos only via `AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT`, #938 through #1361). Three plan-review-specific escape hatches bypass this gate only, leaving all other hooks in effect: (1) `/implement --skip-review` — one-shot, plan-only; (2) `AUTONOMOUS_DEV_SKIP_PLAN_REVIEW=1` env var — persistent across sessions; (3) `touch .claude/SKIP_PLAN_REVIEW` sentinel file — local, gitignored. For a whole-stack opt-out use the universal `.claude/.bypass` or `AUTONOMOUS_DEV_BYPASS=1` (Issue #969). **`AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT` is deprecated** (#1361): enforcement is now the default; setting the var emits a stderr deprecation notice via `hook_bypass.warn_global_enforcement_deprecated_once()` but is otherwise a no-op. Always exits 0. | AUTONOMOUS_DEV_SKIP_PLAN_REVIEW (deprecated: AUTONOMOUS_DEV_GLOBAL_ENFORCEMENT) |
| **session_activity_logger.py** | Structured JSONL activity logging for continuous improvement analysis. Handles PostToolUse (tool calls), UserPromptSubmit (user prompts), and **PreToolUse for Task/Agent tools** (Issue #1087 — subagent invocation caching). Sets `"hook": "PostToolUse"` correctly for tool-call entries. Falls back to parsing hook stdin JSON for `session_id` when `CLAUDE_SESSION_ID` env var is absent (common in PostToolUse lifecycle). Session date pinned on first activity to prevent midnight log splits. For Agent/Task tool outputs, extracts `total_tokens`, `tool_uses`, and `agent_duration_ms` from `<usage>` blocks in the result text (Issue #704) — consumed by `pipeline_timing_analyzer.py` for token efficiency analysis. **result_word_count** (Issue #925): `_add_result_word_count()` writes the word count of the agent result into each PostToolUse JSONL entry. Reads `tool_output["content"]` (modern Anthropic Task `toolUseResult` schema — list-of-text-blocks) and delegates to `count_words_in_content()` from `lib/word_count_helpers.py`, which handles both str-content (legacy) and list-of-blocks (modern) shapes. Falls back to splitting `tool_output["output"]` as a flat string when `content` is absent or the word count is 0. Prior to Issue #925, this function read only the flat-string `output` key, logging `result_word_count: 0` for all implementer events (the root cause of 5 false-positive compression closures). Worktree-aware log directory resolution (Issue #755): when the hook's CWD is inside a `.worktrees/` directory, `_find_log_dir()` runs `git rev-parse --git-common-dir` to locate the parent repo's `.claude/logs/activity/` directory, so downstream agent events written from a worktree land in the same log file as main-session events; falls through to normal walk-up resolution on any git error or when the parent `.claude/` directory does not exist. Batch issue attribution (Issue #808): when a BATCH CONTEXT block is detected in an Agent/Task prompt, `batch_issue_number` is extracted by first trying the structured `Issue Number: N` field added to the BATCH CONTEXT template, then falling back to the inline `Issue #N` pattern for backward compatibility; this prevents mis-attribution when free-text issue references appear elsewhere in the prompt. **PreToolUse subagent invocation caching** (Issue #1087): when `hook_event == "PreToolUse"` and the tool is `Task` or `Agent`, calls `subagent_invocation_cache.cache_invocation(session_id, subagent_type, start_time=time.time(), generation=...)` to write an entry to the per-session FIFO queue at `/tmp/subagent_invocations_{sha8}.json`. This entry is consumed by `unified_session_tracker.py` at SubagentStop time to recover the correct `subagent_type` and compute reliable `duration_ms`. **Generation-token minting** (Issue #1484): a `uuid.uuid4().hex` generation token is minted once per PreToolUse dispatch and passed both to `cache_invocation(..., generation=...)` and to `agent_dispatch_sentinel.write(..., generation=...)`, so `SubagentStop` can later recover the same token and pass it to `agent_dispatch_sentinel.clear(expected_generation=...)` for a compare-and-delete that prevents one dispatch's completion from disarming a sibling dispatch's still-active sentinel (the #1467 ABA race). Sentinel `write()`/`refresh()` failures now emit a non-blocking `[agent_dispatch_sentinel] WARNING: ...` line to stderr instead of a silent `except Exception: pass`. Always exits 0 on PreToolUse — no log entry is written from this hook for PreToolUse events (PostToolUse logging path is unchanged). Non-blocking. | ACTIVITY_LOGGING |

### PreCompact

| Hook | Purpose | Key Env Vars |
|------|---------|--------------|
| **pre_compact_batch_saver.sh** | Saves in-progress batch and/or pipeline state to `.claude/compaction_recovery.json` before context compaction. Captures batch_id, current_index, feature list, and RALPH checkpoint data when a batch is active. Also captures `/implement` pipeline state (run_id, feature, current step, steps completed/remaining, modified files) from the sentinel resolved by `lib/_sentinel.sh::_default_sentinel()` — `<repo>/.claude/local/implement_pipeline_state.json` (was `/tmp/implement_pipeline_state.json` before Issue #1206) — when a pipeline run is active. No-ops when neither batch nor pipeline is active. Always exits 0. | CHECKPOINT_DIR, PIPELINE_STATE_FILE, PIPELINE_STATE_DIR |

### PostCompact

| Hook | Purpose | Key Env Vars |
|------|---------|--------------|
| **post_compact_enricher.sh** | Enriches the compaction recovery marker with the compact_summary from stdin JSON after compaction completes. No-ops if no recovery marker present. Always exits 0. | — |

**Compaction recovery flow**: PreCompact saves state (batch and/or pipeline) → PostCompact adds summary → UserPromptSubmit (`unified_prompt_validator.py`) detects marker on next prompt, re-injects batch and/or pipeline context into model output, and deletes marker. Pipeline recovery validates staleness (discarded if >900 seconds old) and cwd match before injecting. This ensures both batch pipelines and single `/implement` pipeline runs resume correctly after `/clear` or auto-compact without requiring manual state reconstruction.

### TaskCompleted

| Hook | Purpose | Key Env Vars |
|------|---------|--------------|
| **task_completed_handler.py** | Logs task completion events (task_id, subject, description, teammate, team) to the daily activity JSONL at `.claude/logs/activity/{date}.jsonl`. Preparation handler: TaskCompleted does not currently fire in the Agent-tool pipeline but is registered so infrastructure is ready. Always exits 0. | — |

### Stop

| Hook | Purpose | Key Env Vars |
|------|---------|--------------|
| **stop_quality_gate.py** | End-of-turn quality checks (pytest, ruff, mypy). Auto-detects tools, parallel execution, 60s timeout. Always non-blocking. | ENFORCE_QUALITY_GATE |
| **conversation_archiver.py** | Archives complete Claude Code conversation transcripts to `~/.claude/archive/` on every Stop event for long-term pattern analysis. Writes session metadata to both `~/.claude/archive/index.jsonl` (JSONL, jq/grep compatible) and `~/.claude/archive/sessions.db` (SQLite, queryable via Python sqlite3 or DuckDB). Pure Python stdlib, non-blocking, always exits 0. Enabled via `CONVERSATION_ARCHIVE=true` env var. (Issue #773) | CONVERSATION_ARCHIVE |

### Utility (not lifecycle-triggered)

| Hook | Purpose |
|------|---------|
| **cloud_drain_telemetry.py** | Cloud-drain telemetry controller (Issue #1437). Decides whether a cloud-drain fire emits a `FIRE_START`/`FIRE_END` telemetry commit or only JSONL logging. `should_emit_telemetry_commit(exit_reason)` returns `False` for `no_drainable_cluster` (no real work — ~96% of fires) and `True` for genuine events, suppressing the commit churn that previously landed on every no-op fire. Not registered on any Claude Code lifecycle event, and — as of Issue #1437's follow-up audit — **not currently invoked by anything**: a repo-wide search for `cloud_drain_telemetry`, `should_emit_telemetry_commit`, and `create_telemetry_commit` finds no call site outside the module and its own unit test. It ships via `install_manifest.json` and is absent from both settings templates, hence `type: "utility"` in its sidecar. The functions are CLI-invocable (`--fire-type`/`--exit-reason`) and ready for a caller; wiring them into the drain workflows is outstanding. Pure Python stdlib, non-blocking. |
| **genai_prompts.py** | Prompt templates for GenAI-enhanced hooks |
| **genai_utils.py** | Anthropic SDK wrapper with graceful fallback. `GenAIAnalyzer._initialize_client()` now delegates client construction to `lib/genai_credentials.get_anthropic_client()` (Issue #1593) instead of calling `Anthropic()` directly — a bare `Anthropic()` does not raise when no credential is present, so `self.client` was always truthy and the `if not self.client` guard in `analyze()` could never fire; the resulting request-time `TypeError` was swallowed by a blanket `except Exception` and looked identical to a model declining to answer. Credential resolution order: `ANTHROPIC_API_KEY`, then `ANTHROPIC_AUTH_TOKEN`, then no client (`self.client = None`, existing non-LLM fallback path preserved — INV-8). Also exports `_wrap_user_input(text) -> str` — wraps user-controlled text in `<user_input>…</user_input>` XML delimiters with `html.escape(quote=False)` to prevent prompt-injection (Issue #960 Phase 2). Phase 3 (Issue #1007) adds `_safe_wrap(text) -> str` — never-raises convenience wrapper around `_wrap_user_input`; adopted by 8 `GenAIAnalyzer` callers (10 sites) for cross-codebase prompt-injection defense. Issue #1467 adds `INJECTION_MARKERS` (tuple of phrase markers, e.g. "ignore previous instructions", "auto-pass", "this is pre-approved") and `detect_injection(text) -> list` — case-insensitive substring scan returning the matched markers (empty list = clean); this is the single canonical marker surface reused by `alignment_classifier.py`'s Stage 0 pre-check so the injection-defense list has exactly one home. |
| **setup.py** | Interactive setup wizard for plugin configuration |

---

## Standard Git Hooks

### pre-commit (`scripts/hooks/pre-commit`)

Repository structure validation, command validation, manifest sync, lib import checks, hook documentation checks, and documentation tests.

**Manifest completeness check now wired in (Issue #1747, 2026-09-04)**: after the manifest-sync/stage step, the hook runs `python3 scripts/validate_manifest.py` against the POST-SYNC manifest and blocks the commit on non-zero exit. `validate_manifest.py` existed before this change but had no caller anywhere in the repo — a gate nobody invokes, the exact defect class it exists to catch. Its `critical` hooks list also dropped the stale `pre_tool_use.py` entry (archived, no longer shipped); only `unified_pre_tool.py` and `unified_prompt_validator.py` remain required. **Hardened further, same pass**: this guard originally read `if [ -f "scripts/validate_manifest.py" ]; then ... fi` with no `else`, so deleting the validator silently passed the gate — the exact fail-open shape #1747 exists to remove. It now falls through to `elif [ -f "plugins/autonomous-dev/config/install_manifest.json" ]; then` (`scripts/hooks/pre-commit:256`) and refuses the commit when a manifest is present but its validator is missing, rather than treating a missing script as nothing-to-check. **This is not repo-wide**: two earlier `if [ -f ... ]`-guarded checks in the same hook — command validation and the archived `validate_install_manifest.py` sync step — still fall open silently when their scripts are absent; making them fail-closed too is filed as a follow-up, not done in this change.

**Manifest schema gained an `exclude` key (Issue #1747)**: `install_manifest.json` generation is now recursive per component (previously non-recursive globbing under-counted `lib/` by 25 files and `skills/` by 29), and each component object may carry an `"exclude"` array of path prefixes to filter out of that recursive scan — currently only `skills: ["archived/"]`; every other component's `exclude` is `[]`. `plugins/autonomous-dev/scripts/install.py` was also fixed to preserve subdirectory structure when mapping a manifest entry to its install destination (previously flattened every path to its basename via `Path(github_path).name`, which silently collapsed 29 distinct `SKILL.md` files onto one destination) and now raises `ValueError` via `validate_manifest_file_path()` on a `components.<name>.files[]` entry containing `..`, `/./`, an encoded traversal marker, or an absolute/home-relative path (path-traversal refusal, matching the uninstaller's existing check).

**A second, more severe manifest-trust gap, found by security audit of the fix above and closed in the same change (CWE-22)**: the file-path check only ever covered `github_path` — the per-file entry — and never the component-level `target` field. `Path(target) / relative_structure` DISCARDS the left operand when the right side is absolute, so a manifest with an absolute `target` produced an absolute install destination, and `download_to_temp` wrote to that destination during staging — before `FileManager.validate_path`, the only pre-existing containment gate, ever ran. A working proof-of-concept wrote a payload outside the staging directory; because the manifest is fetched over the network at install time with no signature or hash check, this was reachable by a compromised or MITM'd manifest, not only a hand-edited local one. Fixed with two new names in `plugins/autonomous-dev/scripts/install.py`: `validate_manifest_target(component, target)` refuses an empty, NUL-containing, backslash-containing, `..`/`/./`-traversing, `./`-prefixed, `~`-prefixed, absolute, or otherwise non-`.claude/`-normalizing `target` — checked against the RAW string, not `Path(...).parts`, because pathlib silently drops `.` segments (`Path(".claude/./x").parts == ('.claude', 'x')`) and a parts-based check can never see one; and `assert_contained(root, candidate, *, what)`, called in `download_to_temp` immediately before `mkdir`, which resolves both root and candidate and checks containment via `relative_to` (follows symlinks, not a string-prefix compare) as defense in depth for the actual write site. `ENCODED_TRAVERSAL_MARKERS` (`%2e`, `%2f`, `%5c`, `%252e`, `%252f`) is refused on both `target` and `github_path`, though nothing today URL-decodes either before use. `tests/regression/test_issue_1747_manifest_completeness.py` grew again for this arm, 12 → 15 `def test_` functions (31 collected via `pytest --collect-only`).

**The `.claude/` staging gate allowlists exactly three (path, git object mode) PAIRS, matched EXACTLY (whole-line):** `.claude/PROJECT.md 120000` (symlink), `.claude/settings.json 100644` (regular file), and `.claude/logs/cloud-runs.jsonl 100644` (regular file). Selection and subtraction are done by the shell function `claude_gate_scan` (`scripts/hooks/pre-commit:119-167`), reading `git diff --cached --raw -z` on stdin: it walks the NUL-delimited record stream itself and subtracts with an exact whole-line `case` over `<path> <mode>`. Until 2026-09-04 this was a one-line `git diff --cached --raw | awk -F'\t' '…' | grep "^\\.claude/" | grep -vxF -e … || true` pipeline, which fell open three separate ways. Until 2026-09-03 the subtraction was `grep -v "^\.claude/PROJECT.md"`, a prefix match with no end anchor, so `.claude/PROJECT.md.bak` was silently permitted and an entry for `.claude/settings.json` written the same way would have permitted `.claude/settings.json.bak-20260903-081206` too. **GAP 1 (`-z`)** — without `-z`, git applies `core.quotePath`, which is ON by default: any path holding a non-ASCII byte, a backslash, a double quote or a control character is C-quoted, so `.claude/café-évil.json` arrived as `"\.claude/caf\303\251-…"` and no longer matched the `^\.claude/` selector. It left the gate's DOMAIN rather than its allowlist — the gate never saw it, so it had nothing to refuse, and the commit went through with rc=0. `-z` emits raw undecoded bytes and never quotes. **GAP 2 (case-folded selector)** — the selector was byte-exact while APFS folds case, so `.Claude/settings.json` was never selected. The selector now folds (`.[Cc][Ll][Aa][Uu][Dd][Ee]/*`), which WIDENS the domain; the allowlist stays byte-exact, so `.claude/SETTINGS.JSON` is now selected and then REFUSED. Folding the allowlist too would reopen the hole from the other side. **GAP 3 (fail-closed rc)** — the pipeline ended in `|| true` with no `pipefail`, so a git failure (corrupt index, killed process) produced an empty capture indistinguishable from "nothing staged" and the gate PERMITTED. The scan now returns `3` on any stream it cannot account for, the status is captured with `set -o pipefail` plus an if/else, and any non-zero status refuses. The selector deliberately stays a prefix match (case-folded): it is the selector for the gate's domain, not the allowlist. Two of the three entries have `!` negations at `.gitignore:147-148` excepting them from the `.claude/*` blanket at `:146`, and the guard must agree with those — a disagreement is what made `.claude/settings.json` untrackable despite being un-ignored. The third, `.claude/logs/cloud-runs.jsonl`, has no `!` negation anywhere in `.gitignore` and needs none: it is already tracked, and gitignore rules do not apply to files git already tracks. The mode is part of the key because `git diff --cached --name-only` emits only the LINK PATH for a symlink: until 2026-09-03 the gate keyed on the path alone, so `ln -s /etc/hosts .claude/settings.json && git add -f …` exact-matched the allowlist and committed clean — a symlink to anywhere on the filesystem, landing under a name Claude Code loads as live configuration and CI parses as JSON. The gate therefore reads `git diff --cached --raw -z` and pairs each path with the NEW mode in its second metadata field. Rename/copy records carry TWO paths and no disambiguating NUL before the first, so the scan consumes the second path BEFORE any `continue` — skipping it would desync the stream and silently drop the next staged path — and judges a rename on its DESTINATION. A blanket symlink refusal would be wrong: `.claude/PROJECT.md` is itself a symlink by design (to the root `PROJECT.md`, the alignment source of truth) and is the allowlist's own first entry, so each path is pinned to the one mode it is legitimately tracked at. Deletions (new mode `000000`) are dropped before the allowlist: a deletion stages no object, and removing a `.claude/` path from tracking is the remedy this gate asks for. Proven refusing *and* permitting by `TestClaudeAllowlistIsExactMatch` in `tests/regression/test_precommit_fail_open_guard.py`, which stages each path with `git add -f` — as a regular file and as a symlink — and runs the real hook through a real commit. GAP 1 and GAP 2 have end-to-end refuse arms there (`test_refuse_arm_non_ascii_claude_path_blocked`, `test_refuse_arm_case_variant_of_allowlisted_name_blocked`; the GAP 2 arm builds its own repo, because where `.claude/` already exists on disk git normalises the mixed-case spelling away). GAP 3 and the rename bookkeeping are watched at function level by `TestGateScanStreamHandling`, which slices `claude_gate_scan` out of the live hook and feeds it crafted `--raw -z` streams — git cannot be made to emit a malformed one.

**The documentation-test gate refuses as of 2026-08-30; before that it did not.** From `0b00185f` (2025-11-11) the check ran `pytest ... || true` and then read `$?`, which is the exit status of `true` and therefore always `0` — the `exit` below it was unreachable dead code for 9.5 months. It now captures with `if/else` and blocks the commit on failure. Proven refusing *and* permitting by `tests/regression/test_precommit_fail_open_guard.py`, which runs the hook through a real `git commit` in a sandbox repo and asserts on both the return code and whether a commit object exists.

Not shipped to consumers: this hook is not in `install_manifest.json` and has no installer. It applies to this repository and any clone where you create the symlink below by hand.

```bash
# Install
ln -sf ../../scripts/hooks/pre-commit .git/hooks/pre-commit
```

### pre-push (`scripts/hooks/pre-push`)

Fast test suite only (excludes `@pytest.mark.slow`, `@pytest.mark.genai`, `@pytest.mark.integration`). 30s vs 2-5 min full suite.

```bash
# Install
ln -sf ../../scripts/hooks/pre-push .git/hooks/pre-push
```

---

## Universal Hook Bypass (Issue #969)

Almost every hook honors a universal bypass that can be set from outside Claude Code, so a deadlocked harness cannot prevent recovery.

**Exception (Issue #1435 — hard floor)**: Write/Edit to protected
infrastructure (`agents/*.md`, `commands/*.md`, `hooks/*.py`, `lib/*.py`,
`skills/*/SKILL.md`) inside an autonomous-dev repo is **not** waived by this
bypass. `_is_protected_infrastructure` is a registered hard-floor function
(`config/hard_floor_hooks.json`); `unified_pre_tool.py`'s bypass block
detects protected-infra Write/Edit targets before granting the bypass allow
and instead falls through to the normal deny gate, fail-closed on any error
in that check. `/implement` remains the only sanctioned path for such edits.

**Two equivalent signals — either one is sufficient:**

| Signal | Scope | How to set |
|--------|-------|-----------|
| `AUTONOMOUS_DEV_BYPASS=1` (env var) | Process-scoped | `AUTONOMOUS_DEV_BYPASS=1 git commit -m "..."` or `export AUTONOMOUS_DEV_BYPASS=1` |
| `.claude/.bypass` (file flag) | Project-scoped | `touch .claude/.bypass` from the repo root |

When either signal is active, every hook falls through to `allow` and appends one JSONL line to `.claude/logs/hook-bypass.jsonl` for later audit — EXCEPT the protected-infrastructure Write/Edit hard floor described above (Issue #1435), which remains enforced regardless of the bypass. Telemetry failures never block the bypass itself.

**Truthy env var values**: any non-empty string NOT in `{"0", "false", "no", "off"}` (case-insensitive). Explicitly falsy values do NOT trigger bypass.

**File flag walk**: `.claude/.bypass` is detected in the current directory or any ancestor up to 30 levels; symlinks are not followed.

**Implementation**: `plugins/autonomous-dev/lib/hook_bypass.py` — `is_bypassed(start_dir=None)` and `log_bypass_used(hook_name, tool_name, reason)`. Import pattern in hooks:

```python
from hook_bypass import is_bypassed, log_bypass_used

def main():
    if is_bypassed():
        log_bypass_used(hook_name=__file__, tool_name=tool_name)
        sys.exit(0)
    # ... normal enforcement ...
```

See [TROUBLESHOOTING.md](../plugins/autonomous-dev/docs/TROUBLESHOOTING.md#universal-escape-unstick-any-blocked-hook-issue-969) for operator usage.

**Staleness warning for a forgotten `.claude/.bypass` (Issue #1434)**: `SessionStart-batch-recovery.sh` now runs `hook_bypass.check_bypass_staleness()` on every session start (the hook's `SessionStart` matcher was broadened from `compact`-only to `*` to make this possible). If a `.claude/.bypass` file exists, is **not** git-tracked (uncommitted), and is older than `AUTONOMOUS_DEV_BYPASS_STALE_HOURS` (default `24`), a non-blocking `WARNING:` line is printed naming the file, its age, and remediation (`rm` it, or `git add -f && git commit` to make it a durable, silent opt-out). Env-var bypass (`AUTONOMOUS_DEV_BYPASS=1`) never warns — it is process-scoped and expires with the shell. A **committed** `.claude/.bypass` never warns either, since that is the supported durable per-repo opt-out described above. `is_bypassed()` itself is unaffected — this is a separate reaper-style check consulted only at `SessionStart`, never on the hot path.

---

## Hook Time Budgets

Every hook timeout in this repo comes from ONE file:
`plugins/autonomous-dev/config/hook_time_budgets.json` (Issue #1704). Nothing
else may declare one -- not a sidecar, not a settings surface, not a module
constant.

**Why it exists.** The value `5` used to be declared independently in the 7
registration surfaces, in `genai_prompts.DEFAULT_TIMEOUT`, in
`intent_classifier_config.json` and in `semantic_gate.TIMEOUT_S`, seeded by a
hard-coded `reg.get("timeout", 5)` default in `scripts/generate_hook_config.py`.
Nobody had measured it against the work it governs. MEASURED over
`~/.claude/logs/hook_timings_*.jsonl` for `ts >= 2026-08-21` (89,442 rows):
`unified_pre_tool.py` ran to a p99 of 2,223.4ms and a max of 13,139.7ms across
34,973 invocations, and **23 of those exceeded the 5s budget** -- each one
discarding all ~51 checks with no record in either log.

**Budgets are sized from measurement per class**, never by feel:

| class | example | measurement | budget |
|---|---|---|---|
| `fast_local` | `plan_gate`, `validate_paid_dependency` | p50 5.4-9.0ms | 3-5s |
| `composite_gate` | `unified_pre_tool` | p99 2,223.4ms, max 13,139.7ms | 20s |
| `session_lifecycle` | `stop_quality_gate` | max 28,038.1ms | 60s |
| `llm_host` | `unified_prompt_validator` | `claude -p` median 12,766ms | 50s |

**60 is a hard ceiling** declared once, in
`hook-metadata.schema.json` (`timeout.maximum`), and read by
`hook_budgets.schema_max_seconds()`. Whether the runtime honours a larger value
is UNTESTED and moot while the schema refuses it.

**The nesting constraint.** A library's own subprocess/API timeout and its host
hook's budget are DIFFERENT knobs. The library's MUST be strictly less, or the
runtime discards the hook at the same instant the library gives up and a
library timeout becomes indistinguishable from a hook crash. Declared under
`libraries` with an explicit `host_hooks` list and enforced by
`hook_budgets.check_nesting()`.

**A timeout-skip is countable.** `HookTimer` calls
`maybe_record_budget_overrun()`, which routes one row to the existing refusal
sink under `decision_shape="budget_overrun"`. One query finds them all:

```bash
grep hook_budget_overrun .claude/logs/hook-blocks.jsonl
```

The shape is deliberately outside `BLOCK_SHAPES`, so `is_refusal_row()` never
counts an overrun as a refusal -- enforcement *skipped* is the opposite of a
refusal. `HOOK_BUDGET_OVERRUN_DISABLED=1` is the rollback switch and leaves the
timing row intact.

### Changing a budget

```bash
# 1. Edit plugins/autonomous-dev/config/hook_time_budgets.json
# 2. Propagate to every settings surface (discovered BY CONTENT, not by a
#    settings*.json glob -- which misses global_settings_template.json):
python3 scripts/generate_hook_config.py --sync-timeouts -v
# 3. Verify no surface drifted:
python3 scripts/generate_hook_config.py --check-timeouts
# 4. Deploy. --global-settings is REQUIRED, not optional:
bash scripts/deploy-all.sh --global-settings
```

**Step 4 needs `--global-settings`, and a bare `deploy-all.sh` is actively
harmful here.** `deploy-all.sh:110` sets `DO_GLOBAL_SETTINGS=false`; the flag is
opt-in at `:129`. Without it, deploy ships `lib/hook_budgets.py`,
`intent_classifier_config.json` (40s) and `genai_prompts.DEFAULT_TIMEOUT` (15s)
into `~/.claude/` while `~/.claude/settings.json` stays at **5** — producing
`15 > 5` and `40 > 5`, the exact nesting violation this whole section exists to
remove. **The libraries and the settings land together or not at all.**

`check_nesting()` cannot see that state: it reads the canonical config's
`hooks` section, not the installed settings. `check_installed_settings_skew()`
is the check that can, and `--check-timeouts` runs it:

```bash
python3 scripts/generate_hook_config.py --check-timeouts        # exit 1 on skew
# SKEW between the canonical config and the INSTALLED settings (4):
#   ~/.claude/settings.json: unified_pre_tool declares 20s but the INSTALLED
#   registration enforces 5s. A run between 5s and 20s is discarded by the
#   runtime and records NO overrun row.
#   Run `bash scripts/deploy-all.sh --global-settings`, or pass --allow-skew
#   to acknowledge a known pre-deploy window.

python3 scripts/generate_hook_config.py --check-timeouts --allow-skew   # exit 0
#   ACKNOWLEDGED via --allow-skew (pre-deploy window).
```

**Skew exits 1.** It was originally a print statement that returned 0 — nothing
could gate on it, which made the "make skips countable" work unenforceable
where it mattered most. `--allow-skew` is the narrow, explicit acknowledgement
for the pre-deploy window; it does NOT mask drift or unbudgeted registrations,
which keep failing. Without that flag a permanently-red check would train
everyone to ignore the whole class — the cry-wolf failure this repo treats as a
first-class defect.

That last sentence is the reason skew is a correctness bug and not just
untidiness: `maybe_record_budget_overrun` compares against the **declared**
budget, so under skew a real skip produces no row. A guard that validates the
declaration and calls it enforcement is the defect, not the fix. Every overrun
row therefore carries `metadata.budget_source` naming the file its threshold
came from.

---

## Safe Failure Behavior

All 27 hooks wrap their `main()` function with `safe_main()` from `plugins/autonomous-dev/lib/hook_safety.py` (Issue #953). `cloud_drain_telemetry.py` was the last holdout — it invoked `main()` directly with no safety net — and gained the standard wrapper in Issue #1471, closing the gap.

**Hook Recovery Telemetry** (Issue #970): When a hook denies a tool call, it can emit a structured JSONL row to `.claude/logs/hook-recovery.jsonl` via `log_block_with_recovery()` from `plugins/autonomous-dev/lib/hook_recovery.py`. This gives users an actionable recovery hint rather than a silent block. Telemetry NEVER raises — `OSError` falls back to a `[hook-recovery]` stderr line and the block decision is preserved. Set `HOOK_RECOVERY_DISABLED=1` to disable both log writes and stale-state cleanup as a rollback valve. See [HOOK-REGISTRY.md](HOOK-REGISTRY.md) for the env var reference. This provides two guarantees:

**1. Hook crashes never block Claude Code.**
If an unhandled exception propagates out of a hook (missing import, runtime bug, etc.), `safe_main()` catches it, prints a `[hook warning] <hook_name>: <ExceptionType>: <message>` line to stderr, and exits with code 0. Claude Code continues normally. Operators can detect failures by scanning stderr for the `[hook warning]` prefix.

**2. `command_registered()` prevents deny-deadlocks.**
Hooks that issue a `deny` decision directing the user to run a slash command (e.g., `/create-issue`) MUST first call `command_registered("create-issue")` from `hook_safety.py`. If the command is not installed, the deny is downgraded to a warning so the user is not stuck between a blocking hook and a missing command. The lookup fails CLOSED (returns `True`) on any error so the existing security barrier remains active.

**Shebang**: All hooks use `#!/usr/bin/env python3` (not `uv`). A pinned `uv` interpreter was itself a deadlock risk — if `uv` was absent from PATH, the hook never reached the `safe_main` safety net. Standard `python3` resolves via PATH without an external tool dependency.

```python
#!/usr/bin/env python3

if __name__ == "__main__":
    from hook_safety import safe_main
    safe_main(main)
```

See `plugins/autonomous-dev/lib/hook_safety.py` for full API documentation.

**The sanctioned way to refuse (Issue #1588)**: before #1588, refusing a tool call had four different emitter functions across three vocabularies (`deny`/`ask`/`block`) and two recording paths — one hook (`enforce_file_organization.py`) could issue a valid `deny` decision and record zero rows in `.claude/logs/hook-blocks.jsonl`, indistinguishable from a hook that never fired. A new hook (or a hook migrating off a hand-rolled `print(json.dumps(...))` refusal) should have `main()` **return** a `hook_safety.HookDecision` instead of printing:

```python
from hook_safety import HookDecision, safe_main

def main():
    ...
    if disallowed:
        return HookDecision.deny(
            hook_name="my_hook.py",
            reason="... REQUIRED NEXT ACTION: ...",
        )
    return 0

if __name__ == "__main__":
    safe_main(main)
```

`safe_main` owns the output channel for a returned `HookDecision`: it writes the protocol-correct stdout payload and records the refusal via the existing `hook_telemetry.deny_and_record`/`log_block_event` sinks in one indivisible act, so a hook that never touches stdout cannot refuse without a matching telemetry row. This is purely additive — hooks that already `print()` and `return`/`sys.exit()` an int are unaffected. `tests/unit/hooks/test_refusal_sink_ratchet.py` is the enforcement ratchet: it enumerates every hook on disk, classifies its refusal shape by six instruments (dict-literal, emitter-call, `sys.exit(2)`, `return 2`, `@block_event_decorator`, and the `HookDecision` return form), and fails the build if a hook refuses outside `deny_and_record`/`block_event_decorator`/`HookDecision` — with a small, ceiling-capped, name-pinned exemption list (`PINNED_OUT_OF_SINK`) for the handful of commit-gate hooks whose refusal channel genuinely is process exit status.

---

## Archived Hooks

61 hooks have been archived into `plugins/autonomous-dev/hooks/archived/`. These were consolidated into the unified hooks listed above.

See `plugins/autonomous-dev/hooks/archived/README.md` for:
- Complete list of archived hooks
- Migration guides (which unified hook replaced each)
- Historical rationale

---

## Agent Hooks (Experimental)

> **Status**: Proof-of-concept. Advisory only, never enforcement. See [ADR-001-agent-hooks.md](ADR-001-agent-hooks.md) for full rationale.

### type:agent vs type:command

| Property | type:command | type:agent |
|----------|-------------|------------|
| **Format** | Python script (.py) | Markdown prompt (.md) |
| **Execution** | Deterministic Python | LLM subagent (non-deterministic) |
| **Tools available** | Full system access | Read, Grep, Glob only |
| **Limits** | None | 50 tool turns, 60s timeout |
| **Use case** | Enforcement, blocking | Advisory, semantic analysis |

### Key Constraint: Advisory Only

Agent hooks **always** return `{"decision": "approve"}`. They provide informational output (e.g., "these files are missing tests") but never block operations. This is a deliberate design choice:

- LLM non-determinism makes blocking unreliable
- "Hard blocking > nudges" philosophy requires deterministic enforcement
- Advisory output adds value without disrupting workflow

### Available Agent Hooks

| Hook | Event | Purpose |
|------|-------|---------|
| **Stop-verify-test-coverage.md** | Stop | Advisory check: do modified source files have test files? |

### How to Enable (Opt-in)

Agent hooks are **not enabled by default**. To enable, add to `.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "type": "agent",
        "prompt": "plugins/autonomous-dev/hooks/Stop-verify-test-coverage.md",
        "description": "Advisory: check test coverage for modified files"
      }
    ]
  }
}
```

To disable, remove the entry. No environment variable controls activation — presence in settings.json is sufficient.

**Warning**: Agent hooks consume tokens on every invocation. Enable only when the advisory output is valuable for your workflow.

---

## Extension Points

Hook extensions allow project-specific or user-specific tool call validation without modifying the core hook files. Extensions survive `/sync` and `/install` updates.

### Extension API Contract

Each extension is a Python file (`.py`) that implements a `check` function:

```python
def check(tool_name: str, tool_input: dict) -> tuple[str, str]:
    """Validate a tool call.

    Args:
        tool_name: Name of the tool (e.g., "Bash", "Edit", "Write").
        tool_input: Tool input parameters dict.

    Returns:
        ("allow", "") to permit the tool call.
        ("deny", "reason") to block it.
    """
    # Example: block raw mlx commands
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        if "mlx" in cmd and "realign" not in cmd:
            return ("deny", "Use 'realign train' CLI instead of raw mlx commands")
    return ("allow", "")
```

### Extension Directories

Extensions are discovered from two locations (deduplicated by filename, first occurrence wins):

1. **Global**: `~/.claude/hooks/extensions/*.py` — applies to all projects
2. **Project-level**: `.claude/hooks/extensions/*.py` — project-specific rules

Extensions are loaded in **alphabetical order** within each directory. The first `("deny", reason)` return short-circuits — remaining extensions are not called.

### How Extensions Survive Updates

The `extensions/` directory is **never overwritten** by `/sync`, `/install`, or `deploy-all.sh`. All operations explicitly create or preserve the directory:

- `install.sh`: `mkdir -p ~/.claude/hooks/extensions`
- `sync_dispatcher.py`: `(hooks_dst / "extensions").mkdir(exist_ok=True)`
- `scripts/deploy-all.sh`: rsync uses `--exclude=extensions/` to prevent deletion during `--delete` syncs (Issue #560)

### Environment Variable

| Variable | Default | Effect |
|----------|---------|--------|
| `HOOK_EXTENSIONS_ENABLED` | `true` | Set to `false` to skip all extensions |

### Example Extension

**File**: `~/.claude/hooks/extensions/block_raw_mlx.py`

```python
"""Block raw mlx-lm commands — use realign train CLI instead."""

def check(tool_name: str, tool_input: dict) -> tuple[str, str]:
    if tool_name != "Bash":
        return ("allow", "")
    cmd = tool_input.get("command", "")
    if "mlx_lm" in cmd or "mlx-lm" in cmd:
        if "realign" not in cmd:
            return ("deny", "Use 'realign train' instead of raw mlx-lm commands")
    return ("allow", "")
```

### Security Notes

- **Symlinks are skipped**: Extension files that are symlinks are silently ignored to prevent symlink-based attacks.
- **Per-extension isolation**: Each extension runs in its own try/except block. A crashing extension never affects other extensions or the main hook.
- **No arbitrary code injection**: Extensions are only loaded from the two known directories listed above.

---

## See Also

- [ADR-001-agent-hooks.md](ADR-001-agent-hooks.md) — Architecture Decision Record for agent hooks
- [HOOK-REGISTRY.md](HOOK-REGISTRY.md) — Environment variables, activation status
- [SANDBOXING.md](SANDBOXING.md) — 4-layer security architecture
- [GIT-AUTOMATION.md](GIT-AUTOMATION.md) — Git automation workflow
- [hooks/archived/README.md](/plugins/autonomous-dev/hooks/archived/) — Archived hooks reference
