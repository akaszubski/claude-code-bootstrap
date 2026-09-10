---
covers:
  - plugins/autonomous-dev/lib/
---

# Shared Libraries Reference

**Last Updated**: 2026-09-04 (bugfix_detector.py: `CANONICAL_TEST_COUNT_DIRS` and `evaluate_regression_test_gate()` added, closing the STEP 1/STEP 8 scope mismatch that left the regression-test HARD GATE unable to refuse, plus two remediation cycles adding the caller-side `ERROR` verdict, the `BASELINE-SCOPE-RECORD` marker block, and exception-truncation hardening — see entry #87 below)
**Purpose**: Comprehensive API documentation for autonomous-dev shared libraries

This document provides detailed API documentation for shared libraries in `plugins/autonomous-dev/lib/` and `plugins/autonomous-dev/scripts/`. For high-level overview, see [CLAUDE.md](../CLAUDE.md) Architecture section.

## Overview

The autonomous-dev plugin includes shared libraries organized into the following categories:

### Core Libraries (96)

1. **security_utils.py** - Security validation and audit logging
2. **project_md_updater.py** - Atomic PROJECT.md updates with merge conflict detection
3. **version_detector.py** - Semantic version comparison for marketplace sync
4. **orphan_file_cleaner.py** - Orphaned file detection and cleanup
5. **sync_dispatcher.py** - Intelligent sync orchestration (marketplace/env/plugin-dev)
6. **validate_marketplace_version.py** - CLI script for version validation
7. **plugin_updater.py** - Interactive plugin update with backup/rollback
8. **update_plugin.py** - CLI interface for plugin updates
9. **hook_activator.py** - Automatic hook activation during updates
10. **auto_implement_git_integration.py** - Automatic git operations (commit/push/PR)
11. **abstract_state_manager.py** - StateManager ABC for standardized state management (NEW v1.0.0, Issue #220)
12. **session_state_manager.py** - Session state persistence in .claude/local/SESSION_STATE.json with context tracking (NEW v1.0.0, Issue #247)
13. **batch_state_manager.py** - State persistence for /implement --batch with automatic context management (v3.23.0, Issue #218: deprecated context clearing functions removed v3.46.0, Issue #221: now inherits from StateManager ABC)
14. **github_issue_fetcher.py** - GitHub issue fetching via gh CLI (v3.24.0)
15. **github_issue_closer.py** - Auto-close GitHub issues after /implement (v3.22.0, Issue #91)
16. **path_utils.py** - Dynamic PROJECT_ROOT detection and path resolution (v3.28.0, Issue #79)
17. **validation.py** - Tracking infrastructure security validation (v3.28.0, Issue #79)
18. **failure_classifier.py** - Error classification (transient vs permanent) for /implement --batch (v3.33.0, Issue #89)
19. **batch_retry_manager.py** - REMOVED (never executed; see section 22)
20. **batch_retry_consent.py** - REMOVED (never executed; see section 23)
21. **quality_persistence_enforcer.py** - Completion gate enforcement and honest summary for /implement --batch (v1.0.0, Issue #254)
22. **session_tracker.py** - Session logging for agent actions with portable path detection (v3.28.0+, Issue #79)
23. **settings_merger.py** - Merge settings.local.json with template configuration (v3.39.0, Issue #98)
24. **settings_generator.py** - Generate settings.local.json with specific command patterns (NO wildcards) (v3.43.0+, Issue #115)
25. **feature_dependency_analyzer.py** - Smart dependency ordering for /implement --batch (v1.0.0, Issue #157)
26. **acceptance_criteria_parser.py** - Parse acceptance criteria from GitHub issues for UAT generation (v3.45.0+, Issue #161)
27. **test_tier_organizer.py** - Classify and organize tests into unit/integration/uat tiers (v3.45.0+, Issue #161)
28. **test_validator.py** - Execute tests and validate TDD workflow with quality gates (v3.45.0+, Issue #161)
29. **tech_debt_detector.py** - Proactive code quality issue detection (large files, circular imports, dead code, complexity) (v1.0.0, Issue #162)
30. **scope_detector.py** - Scope analysis and complexity detection for issue decomposition (v1.0.0)
31. **completion_verifier.py** - Pipeline verification with loop-back retry and circuit breaker (v1.0.0)
32. **hook_exit_codes.py** - Standardized exit code constants and lifecycle constraints for all hooks (v4.0.0+)
33a. **hook_safety.py** - Hook graceful-failure safety net: `safe_main()` wraps hook `main()` so any unhandled exception exits with code 0 + stderr warning instead of blocking Claude Code; `command_registered()` checks whether a slash command is installed before issuing a deny decision that references it (fail-CLOSED: returns True on lookup error to preserve security barrier); path-traversal guard (Issue #954, M-01) rejects any command name containing `/`, `\`, or `..` at the `command_registered()` chokepoint and inside `_check_command_dir()` before any filesystem access, with a `Path.resolve()` backstop to catch symlink-based escapes. **The sanctioned refusal sink (Issue #1588)**: before this, a hook could construct a valid deny payload and print it without ever calling a telemetry recorder — refusing and recording were two separate, forgettable acts across four emitter functions and three vocabularies (`deny`/`ask`/`block`) in the harness. `HookDecision` (frozen dataclass; `.deny()` classmethod for the common `PreToolUse` case; validates its `decision`/`protocol` pairing at construction) is now returned from a hook's `main()` instead of being printed, handing stdout ownership to `safe_main`. `safe_main` detects a returned `HookDecision` and calls `emit_decision()`, which (a) for a `PreToolUse`/`deny` decision delegates to `hook_telemetry.deny_and_record` so the payload and the telemetry row come from one call, (b) for `ask` or a `UserPromptSubmit` refusal calls `hook_telemetry.log_block_event` directly, (c) verifies the sink's returned payload still carries the decided `permissionDecision` before trusting it (`_payload_carries_decision` — an envelope that lost the field reads as an allow even though a block row was already written), (d) serialises via `_render`'s three-tier coercion so a non-`str` `reason` degrades the *message*, never the *decision*, and (e) returns `False` (rather than raising) when stdout itself is unwritable, which `safe_main` uses to raise the implied exit-0 to exit-1 so a refusal is never silently converted into a permission. Purely additive: hooks that `print()` and `return`/`sys.exit()` an int are unaffected. `tests/unit/hooks/test_refusal_sink_ratchet.py` is the accompanying ratchet — it AST-scans every hook file, classifies refusal shape by six named instruments, and fails the build on any refusal outside `deny_and_record`/`block_event_decorator`/`HookDecision`, with a small ceiling-capped exemption list (`PINNED_OUT_OF_SINK`, `PINNED_CEILING = 6`) for commit-gate hooks whose refusal channel genuinely is process exit status. `enforce_file_organization.py` is the first hook migrated onto this path. (v1.0.0, Issue #953; v1.1.0, Issue #954; v1.2.0, Issue #1588)
33. **worktree_manager.py** - Git worktree isolation for safe feature development (v1.0.0, Issue #178)
34. **complexity_assessor.py** - Automatic complexity assessment for pipeline scaling (v1.0.0, Issue #181)
35. **pause_controller.py** - File-based pause controls and human input handling for workflows (v1.0.0, Issue #182)
36. **worktree_command.py** - Interactive CLI for git worktree management (list, status, review, merge, discard) (v1.0.0, Issue #180)
37. **sandbox_enforcer.py** - Command classification and sandboxing for permission reduction (v1.0.0, Issue #171)
38. **status_tracker.py** - Test status tracking for pre-commit gate enforcement (v3.48.0+, Issue #174)
39. **headless_mode.py** - CI/CD integration support for headless/non-interactive environments (v1.0.0, Issue #176)
40. **qa_self_healer.py** - Orchestrate automatic test healing with fix iterations (v1.0.0, Issue #184)
41. **failure_analyzer.py** - Parse pytest output to extract failure details (v1.0.0, Issue #184)
42. **code_patcher.py** - Atomic file patching with backup and rollback (v1.0.0, Issue #184)
43. **stuck_detector.py** - Detect infinite healing loops from repeated identical errors (v1.0.0, Issue #184)
44. **ralph_loop_manager.py** - Retry loop orchestration with circuit breaker and validation strategies (v1.0.0, Issue #189)
45. **success_criteria_validator.py** - Validation strategies for agent task completion (v1.0.0, Issue #189)
46. **feature_flags.py** - Optional feature configuration with graceful degradation (v1.0.0, Issue #193). `is_feature_enabled(feature_name)` uses opt-out semantics — returns True when the config file is missing or the feature key is absent (safe default ON). `is_feature_explicitly_enabled(feature_name)` uses opt-in semantics — returns True ONLY when `.claude/feature_flags.json` exists AND contains `{feature_name: {"enabled": true}}` explicitly; any other state (missing file, missing key, malformed config, enabled=false, any load error) returns False (safe default OFF). Use `is_feature_explicitly_enabled` for features that must be off by default in fresh repos (e.g., `semantic_gate`).
47. **worktree_conflict_integration.py** - Conflict resolver integration into worktree workflow (v1.0.0, Issue #193)
48. **comprehensive_doc_validator.py** - Cross-reference validation between documentation files (708 lines, v1.0.0, Issue #198)
49. **test_runner.py** - Autonomous test execution with structured TestResult (v1.0.0, Issue #200)
50. **code_path_analyzer.py** - Discover code paths matching patterns for debug-first enforcement (v1.0.0, Issue #200)
51. **doc_update_risk_classifier.py** - Risk classification for documentation updates (auto-apply vs approval) (v1.0.0, Issue #204)
52. **doc_master_auto_apply.py** - Auto-apply LOW_RISK documentation updates with user approval for HIGH_RISK changes (v1.0.0, Issue #204)
53. **auto_implement_pipeline.py** - Pipeline integration for project-progress-tracker invocation after doc-master (v1.0.0, Issue #204)
54. **alignment_gate.py** - Strict PROJECT.md alignment validation with score-based gating (7+ threshold) (v1.0.0, Issue #251)
55. **workflow_violation_logger.py** - Audit logging for workflow violations with JSON Lines format, CWE-117 prevention, log rotation, thread safety (v1.0.0, Issue #250)
56. **training_metrics.py** - Tulu3 multi-dimensional scoring and DPO preference generation for LLM training quality assessment (v1.0.0, Issue #279)
57. **coverage_baseline.py** - Coverage baseline storage and regression detection for test quality gates (v1.0.0, Issue #332). `check_test_count_regression(current_test_count, *, tolerance_pct=10.0, tolerance_abs=20)` blocks when test count drops by more than `min(tolerance_pct%, tolerance_abs)` from baseline, detecting test-deletion gaming where behavioral tests are replaced with fewer structural checks (Issue #711). `check_skip_regression(current_skipped)` blocks when skip count increases. `check_coverage_regression(current_coverage, tolerance=0.5)` blocks when coverage drops below baseline minus tolerance. `save_baseline(coverage_pct, skip_count, total_tests)` persists all three values atomically to `.claude/local/coverage_baseline.json`.
58. **batch_git_finalize.py** - Batch git finalization with auto-commit, merge, and worktree cleanup (v1.0.0, Issues #333-334)
59. **pipeline_intent_validator.py** - Intent-level pipeline validation via JSONL session logs for coordinator-level violations. Detects step ordering, hard gate bypasses, context dropping, parallelization violations, progressive prompt compression across batch issues (Issue #367, compression detection Issue #544; `detect_progressive_compression` and `MAX_PROMPT_SHRINKAGE_RATIO` deprecated #925 — no longer consulted by `validate_pipeline_intent`), doc-master verdict timeouts/failures (Issue #543), batch issues missing continuous-improvement-analyst invocations (Issue #559), and single (non-batch) pipeline runs missing continuous-improvement-analyst invocations (Issue #667). `STEP_ORDER` now includes `continuous-improvement-analyst: 7.0` (CIA is always the last step), and `SEQUENTIAL_REQUIRED` gains three CIA prerequisite pairs: `(implementer, CIA)`, `(reviewer, CIA)`, `(doc-master, CIA)` — enforcing that CIA runs only after all validation/implementation agents complete; `security-auditor → CIA` intentionally absent (conditional agent) (Issue #957). `STEP_ORDER` also includes `spec-validator: 5.7` (between pytest-gate at 5.5 and reviewer at 6.0), and `SEQUENTIAL_REQUIRED` gains three spec-validator ordering pairs: `(implementer, spec-validator)`, `(pytest-gate, spec-validator)`, `(spec-validator, reviewer)` — enforcing that spec-validator runs at STEP 8.5 after tests pass and before human-judgment review (Issue #1158, closes audit D4). `Finding` dataclass includes `recommended_action: Optional[str]` field for remediation guidance. `detect_progressive_compression()` accepts optional `agents_dir` parameter and populates `recommended_action` with prompt reload instructions. `get_minimum_prompt_content(agent_type, agents_dir)` reads baseline prompt content from agent `.md` files with `VALID_AGENT_TYPES` whitelist path validation (Issue #561). `detect_doc_verdict_missing()` uses `_correlate_invocation_completion()` to pair PostToolUse invocation events with SubagentStop completion events by subagent type and temporal proximity, enabling accurate verdict detection from completion word counts rather than invocation placeholders; `MIN_DOC_VERDICT_WORDS = 30` constant sets minimum output threshold (Issue #562). When correlation fails to produce a completion match (`comp is None`), a fallback scan checks whether any doc-master completion event in the full event list has `success=True` and `result_word_count >= MIN_DOC_VERDICT_WORDS`; if such an event exists the invocation is skipped as a false positive, preventing spurious `doc_verdict_missing` findings when session grouping, timestamp parsing, or time-window boundary conditions cause correlation to fail (Issue #650). `PipelineEvent` dataclass includes `session_id: str`, `total_tokens: int`, and `tool_uses: int` fields populated from JSONL log entries (token fields sourced from `session_activity_logger.py` Agent result extraction, Issue #704). `validate_pipeline_intent()` is now session-scoped: when no `session_id` filter is provided, events are grouped by their `session_id` field and each session's events are checked independently, preventing false CRITICAL `step_ordering` findings from cross-session event comparisons in a shared daily log file; legacy events with an empty `session_id` are grouped together as a fallback virtual session (Issue #587). `parse_session_logs()` accepts an optional `additional_log_paths` parameter to merge events from multiple JSONL files; duplicates are removed by `(timestamp, tool, session_id)` key before sorting. `validate_pipeline_intent()` automatically detects worktree context via `path_utils.get_main_repo_activity_log_dir()` and passes the corresponding main-repo log file as `additional_log_paths`, preventing false INCOMPLETE findings when logs are split across the worktree and its parent repository (Issue #593). `detect_doc_verdict_shallow(events)` detects doc-master completions that pass the `MIN_DOC_VERDICT_WORDS` threshold (so they evade `detect_doc_verdict_missing`) but fall below `MIN_DOC_SWEEP_WORDS = 100`; these indicate the agent likely only updated CHANGELOG without performing a semantic drift sweep. Emits `Finding` with `finding_type="doc_verdict_shallow"` and `severity="WARNING"`. Applies the same `_correlate_invocation_completion()` pairing strategy as `detect_doc_verdict_missing`, with an equivalent fallback scan when correlation produces no match. Integrated into `validate_pipeline_intent()` (Issue #672). `detect_cia_skip(events)` detects missing `continuous-improvement-analyst` in non-batch (single) pipeline runs; complements `detect_batch_cia_skip()` which handles batch runs. Skips sessions that have no completed pipeline agents (not a real pipeline run) or that look like batch runs (any event has `batch_issue_number > 0`). Emits `Finding` with `finding_type="cia_skip"`, `severity="WARNING"`, `pattern_id="single_pipeline_cia_skip"`. Integrated into `validate_pipeline_intent()` (Issue #667). `validate_step_ordering(events)` now groups agent events by `batch_issue_number` when batch events are present: ordering is checked independently within each issue group, preventing false CRITICAL findings in mixed-mode batches where `--fix` issues (implementer-only, no planner/researcher) run alongside full-pipeline issues (Issue #680). The internal helper `_validate_step_ordering_for_group(agent_events, all_events)` performs the per-group ordering check and is also called directly in non-batch mode. `detect_context_dropping(events)` now detects whether a session contains batch events and, when it does, skips consecutive-pair comparisons where `prev.batch_issue_number != curr.batch_issue_number`; this prevents false positives caused by treating the final agent result of issue N as the expected context for the first agent of issue N+1 (Issue #681). `_validate_step_ordering_for_group` now filters out `--fix` implementer events before the planner→implementer timestamp comparison instead of skipping the entire check when all implementers are `--fix`; this allows the check to still fire for any non-fix implementer that genuinely precedes the planner, while correctly ignoring fix-mode implementers that run without a planner by design. In a mixed-mode batch where one issue is `--fix` (implementer only, no planner) and another is full-pipeline (implementer after planner), the fix-mode implementer's early timestamp no longer causes a false CRITICAL `step_ordering` finding (Issue #760). 3 regression tests in `tests/regression/test_issue_760_mixed_mode_ordering.py` cover: mixed-mode no false positive, non-fix implementer genuinely before planner is still detected, and all-fix-mode skip behavior preserved. `_validate_step_ordering_for_group` updated in Issue #801 to use group-level mode detection via `PLANNER_EXEMPT_MODES = {"--fix", "fix"}` constant: collects the set of `pipeline_mode` values across all events in the group, and if any intersect with `PLANNER_EXEMPT_MODES`, removes the `("planner", "implementer")` pair from enforcement entirely. Empty or unknown `pipeline_mode` defaults to full enforcement as a fail-safe. This replaces the prior per-event filtering approach with a cleaner group-scoped check. `PipelineEvent.pipeline_mode` field (str) is now populated from the `pipeline_mode` key in JSONL `input_summary` entries. `SECURITY_SENSITIVE_PATTERNS` constant (tuple of path substrings) expanded from 5 to 29 patterns covering four domain groups — **Infrastructure** (`hooks/`, `lib/auto_approval_engine`, `lib/tool_validator`, `config/auto_approve_policy`, `lib/security`), **Auth/access control** (`auth`, `crypto`, `permission`, `session`, `token`, `secret`, `credential`, `password`, `oauth`, `sso`, `jwt`, `rbac`), **Financial** (`trading`, `payment`, `billing`, `financial`, `transaction`, `wallet`), **Schema/environment** (`migration`, `alembic`, `.env`) — broad substring matching is intentional; false positives (extra security review) are cheaper than false negatives (missed security regression). `detect_missing_security_review(log_path, events, *, session_id)` scans JSONL for Write/Edit tool entries targeting `SECURITY_SENSITIVE_PATTERNS`; if any match is found and no `security-auditor` event exists in the session events, a WARNING finding with `finding_type="missing_security_review"` is emitted. Test files are excluded from triggering the warning: paths starting with `tests/` (relative) OR containing `/tests/` as a substring (absolute paths recorded by the JSONL activity logger, e.g. `<home>/.../tests/unit/hooks/test_x.py`). The bare `startswith("tests/")` check previously missed absolute paths, producing false-positive `missing_security_review` warnings whenever test files touching hook-related paths were edited (Issue #1088 F2). Integrated into `validate_pipeline_intent()` (Issues #788, #798, consolidated as #801, expanded as #845). 2 regression tests for the absolute-path fix added to `TestMissingSecurityReview` in `tests/unit/lib/test_pipeline_intent_validator.py` (Issue #1088).
60. **pipeline_state.py** - Pipeline state tracker with gate enforcement (stdlib only, zero dependencies) (Issue #402). HMAC integrity protection added in Issue #557: `_compute_state_hmac(state, session_id)` computes HMAC-SHA256 over critical state fields (session_start, mode, run_id, explicitly_invoked, nonce) keyed by session_id+nonce; `verify_state_hmac(state, session_id)` verifies the stored HMAC — backward compatible (returns True when no hmac field present), returns False when nonce is missing with hmac present (tampering indicator). Stale fail-open added in Issue #753: when HMAC cannot be verified and the state's `session_start` timestamp is older than 1 hour, `verify_state_hmac` returns True (treating the state as expired rather than tampered) — prevents repeated HMAC failures in batch/worktree workflows where the per-run secret file is cleaned up after `/clear`. Module-level constant `LEGACY_SENTINEL_PATH: Path = Path("/tmp/implement_pipeline_state.json")` was extracted in Issue #761 and **removed in Issue #1206** — replaced by `LEGACY_SENTINEL_FILENAME: str = "implement_pipeline_state.json"` (the bare filename) and the public function `get_legacy_sentinel_path(repo_root=None) -> Path`, which resolves to `<repo>/.claude/local/implement_pipeline_state.json` by walking up from CWD for a `.git` or `.claude` marker. The `atomic_write_json(path, data, ...)` public function (renamed from private `_atomic_write_json` in Issue #1320; `_atomic_write_json` remains as a backward-compat alias) consolidates the temp-file + `os.replace` + `0o600` mode pattern used in two former inline mkstemp writers. The HMAC stale-detection proxy (mtime of the sentinel file) is preserved and now targets the per-repo path. The `test_legacy_sentinel_path_constant_exists` regression test was updated to verify the new `LEGACY_SENTINEL_FILENAME` constant rather than the removed `LEGACY_SENTINEL_PATH`. Consumed by `unified_pre_tool.py` to reject forged pipeline state files. (Issue #1206) Five new public helpers added in Issue #1047 for STEP 0 run isolation: `generate_run_id()` returns a 16-char lowercase hex string via `secrets.token_hex(8)`; `get_lockfile_path(run_id)` returns `Path("/tmp/pipeline_<run_id>.lock")`; `acquire_run_lock(run_id)` opens that file and calls `fcntl.flock(LOCK_EX | LOCK_NB)` — returns the fd on success or `None` when the lock is already held (concurrent pipeline guard); `release_run_lock(fd)` unlocks and closes the fd; `classify_resume_id(arg)` returns one of `"batch"` (`batch-*` prefix), `"run_id"` (16-char hex), `"run_id_legacy"` (`YYYYMMDD-HHMMSS` back-compat), or `"unknown"` for any other format — used by the coordinator's `--resume` dispatch in STEP 0. Two new public helpers added in Issue #1069 for PIPELINE_BASE_COMMIT anchoring: `set_pipeline_base_commit(base_commit, *, state_path=None) -> bool` — writes the git SHA captured via `git rev-parse HEAD` at pipeline start into the `base_commit` key of the legacy sentinel state file (PIPELINE_STATE_FILE); returns `True` on success, `False` if the state file does not exist or could not be read/written; empty string is permitted (disables anchoring); `get_pipeline_base_commit(*, state_path=None) -> Optional[str]` — reads the stored SHA back; returns `None` when the key is absent, empty, or whitespace-only (callers SHOULD fall back to plain `HEAD` diff). These helpers are called at STEP 0 / STEP F1 to persist the base commit and at STEP 8.5 / STEP F3.5 / STEP F4 to recover it, ensuring `git diff --name-only` reflects only files changed by the current pipeline run rather than pre-existing working-tree state. 12 new tests in `tests/unit/lib/test_pipeline_state_base_commit.py`. (Issue #1069) Three new public symbols added in Issue #990 for pytest baseline scope recording: module-level constant `CANONICAL_BASELINE_CMD: List[str] = ["pytest", "tests/unit", "tests/integration", "-q", "--tb=no"]` — the canonical baseline pytest invocation (stored as a list for shell-injection safety; join with `" ".join(CANONICAL_BASELINE_CMD)` when a string form is needed); `record_baseline_scope(state_path, baseline_cmd, baseline_count) -> bool` — reads the existing pipeline sentinel JSON, merges `baseline_cmd` (list) and `baseline_count` (int) under those exact key names, and writes back atomically via temp-file + `os.replace`; returns `True` on success, `False` on any IO/JSON error, NEVER raises; called by the coordinator in STEP 1 immediately after capturing `BASELINE_TEST_COUNT`; `get_baseline_scope(state_path) -> dict|None` — returns `{"baseline_cmd": [...], "baseline_count": N}` when both fields are present and well-formed (non-empty list of strings, integer count), otherwise returns `None`; NEVER raises; consumed by the implementer agent at STEP 8 to enforce that pytest is run with the exact recorded scope rather than a broader self-chosen directory set. 19 unit tests in `tests/unit/lib/test_pipeline_state_baseline_scope.py` (untracked — to be staged). **Known limitation (flagged by the security-auditor pass on the Issue #990 follow-up, Medium):** `baseline_cmd`/`baseline_count` sit outside the HMAC-covered field set above (`session_start`, `mode`, `run_id`, `explicitly_invoked`, `nonce`) — `_compute_state_hmac` does not sign them — yet the STEP 8 regression gate's `UNMEASURED` fallback now reads `get_baseline_scope()` as its dominant path whenever the exported shell variable is absent, meaning the value the gate trusts most is the one value in the sentinel an attacker with file write access could tamper with undetected. No exploit is claimed; recorded here as a limitation to revisit if the scope fields become a higher-value target. (Issue #990) Two new public helpers added in Issue #1271 for remediation-aware doc-drift: `set_remediation_flag(run_id) -> bool` — sets `remediation_occurred` flag to True in the pipeline state when STEP 11 remediation is triggered (implementer re-invoked in REMEDIATION MODE); `get_remediation_flag(run_id) -> bool` — reads the flag back at STEP 12 to determine whether doc-master needs re-invocation due to file/test changes during remediation. The `PipelineState` dataclass gains `remediation_occurred: bool = False` field (backward-compatible default). Called by the coordinator at STEP 11 when remediation triggers and at STEP 12 for conditional doc-master re-invocation.
61. **step5_quality_gate.py** - STEP 5 quality gate: runs tests with smart routing or full suite, checks coverage regression, enforces skip baseline, enforces test count baseline (blocks if test count drops significantly from baseline, detecting test-deletion gaming — Issue #711), reports Diamond Model tier distribution via `tier_registry.get_tier_distribution()`, and reports acceptance criteria coverage (N/M criteria covered) via `acceptance_criteria_tracker`. When total acceptance criteria > 0 but covered == 0, a WARNING is appended to the summary (never blocks). Gate passes only when all four checks pass: `test_result.passed`, `coverage_result.passed`, `skip_passed`, and `test_count_passed`. `run_quality_gate()` result dict includes a `test_count_regression` key, `{passed, message}`. All four are COUNTERS — `assert True` satisfies every one of them. An Issue #1660 revision composed a fifth, non-counter check (`mutation_witness.check_mutation_witnesses()`) here; it was removed, because this module is itself pinned in `PINNED_UNREACHED_LIBRARY` — named repeatedly in `implement.md` and `implementer.md` as the gate that "blocks", and invoked by neither — so the composition wired a harness into a host nothing calls and produced the appearance of enforcement rather than enforcement (INV-1). The mutation harness now lives unwired at `scripts/mutation_witness.py` with its driver `scripts/mutation_witness_gate.py`; see `docs/HOOKS.md`. (Issue #508; tier reporting Issue #677; acceptance coverage Issue #676; test count regression Issue #711; mutation witness Issue #1660)
62. **test_routing.py** - Smart test routing: classifies changed files into categories and computes minimal pytest marker expression to skip irrelevant test tiers; `--full-tests` override runs complete suite (Issue #508). `get_changed_files(cwd)` gathers staged + unstaged changes (`git diff --name-only HEAD`) and untracked files (`git ls-files --others`); when both return empty (e.g. all changes committed and coordinator cwd differs from the worktree), falls back to `git diff --name-only HEAD~1` to surface the most-recent commit — prevents spurious `full_suite: True` returns in batch/--no-worktree mode (Issue #1136).
63. **refactor_analyzer.py** - `RefactorAnalyzer` class: deep analysis of test shape (Quality Diamond), test waste, doc redundancy, dead code, and unused libraries; composes `SweepAnalyzer` for quick-sweep mode; `ConfidenceLevel` enum for findings; word-boundary regex to reduce false positives (Issue #513). Updated dispatcher (Issue #1098): `full_analysis(["docs"])` now calls `analyze_doc_drift()` (periodic narrative-doc drift sweep via `doc_drift_detector.py`); the prior SequenceMatcher redundancy behavior is preserved as `analyze_docs()` and reachable via `full_analysis(["docs_redundancy"])`
64. **genai_refactor_analyzer.py** - `GenAIRefactorAnalyzer`: hybrid static-candidate + LLM-semantic analysis wrapper around `RefactorAnalyzer`; three-pass analysis (doc-code drift via `covers:` frontmatter, hollow test detection, dead code verification with dynamic dispatch context); Haiku for first-pass classification, Sonnet escalation for HIGH findings; SHA-256 content hash caching; Anthropic Batch API support for 50% cost reduction (Issue #515). Issue #1593: `_submit_batch`/`_poll_batch` now call `genai_credentials.get_anthropic_client()` instead of constructing `Anthropic()` directly, so a missing credential is a clean skip (logged, returns `None`) rather than a bare construction whose failure was previously deferred to request time and swallowed by the surrounding `except Exception`.

64b. **genai_credentials.py** - The sole sanctioned construction site for `anthropic.Anthropic` in this repository (Issue #1593). `get_anthropic_client(*, purpose="") -> Optional[Anthropic]` never raises: a missing SDK, a missing credential, or a credential the SDK silently declines all resolve to `None`, so callers need exactly one guard (`if client is None`) instead of a blanket `except Exception`. Two-layer check: **Layer 1** (authoritative) — an env pre-check resolves `ANTHROPIC_API_KEY` first, then `ANTHROPIC_AUTH_TOKEN`; if neither holds a non-blank value, returns `None` *without constructing a client at all* (the property Issue #1593 is about — `Anthropic()` with no credential does not raise, it returns a truthy client whose `api_key` is `None`, deferring the `TypeError` to request time). **Layer 2** (defence in depth) — a post-construction `auth_headers` probe catches a credential the SDK silently declined to adopt; it is an over-approximation of the SDK's internal `_validate_headers`, not a replacement for it. Deliberately does NOT use the macOS keychain `accessToken` (expires hourly) or a Claude Code OAuth `auth_token` (API rejects it without an unsupported beta header). Consumed by `hooks/genai_utils.py::GenAIAnalyzer._initialize_client` and by `genai_refactor_analyzer.py`'s two Batch API construction sites. Three other direct-construction sites (`genai_validate.py`, `alignment_gate.py`, `genai_manifest_validator.py`) remain deliberately unmigrated — each has a structurally different error contract — and are pinned with justification in the ratchet test below. Enforcement: `tests/unit/lib/test_anthropic_client_ratchet.py` AST-scans `hooks/`, `lib/`, and `scripts/` for any `Anthropic(...)` construction outside `genai_credentials.py`; a fixed `PINNED_OUT_OF_SINK` frozenset (6 entries, asserted by exact membership) names every remaining out-of-sink site, and `PINNED_CEILING` asserts equality with that set's size so the exemption list can only change via a deliberate two-line diff — adding an entry is not an acceptable resolution for a new failure. Part 1 of #1593; Part 2 (transport-layer work, `claude -p` subprocess path) is explicitly out of scope for this module. (v1.0.0, Issue #1593)
65. **reviewer_benchmark.py** - Harness effectiveness benchmark for the reviewer agent: loads labeled diff datasets with ground-truth verdicts, constructs reviewer prompts, parses APPROVE/REQUEST_CHANGES/BLOCKING verdicts, computes balanced accuracy/FPR/FNR/consistency scoring with per-difficulty and per-defect-category breakdowns, and persists reports via `skill_evaluator.BenchmarkStore`. CLI runner at `scripts/run_reviewer_benchmark.py`. Dataset expanded to 146 samples with 91-category taxonomy at `tests/benchmarks/reviewer/`. Mining scripts: `scripts/mine_git_samples.py`, `scripts/mine_session_logs.py` (Issue #567, #573)
66. **benchmark_history.py** - Append-only JSONL storage for timestamped benchmark results. `BenchmarkHistory(path)` stores one JSON object per line with timestamp, prompt hash, model, balanced accuracy, FPR, FNR, per-defect-category, per-difficulty, and confusion matrix fields. Methods: `append(report, *, prompt_hash, model, metadata)`, `load_all()` (corrupt lines silently skipped), `load_latest(n)`, `trend(metric, last_n)`. Module-level `compute_prompt_hash(prompt_text)` returns hex-encoded SHA256 of reviewer prompt for change tracking. Used by `scripts/improve_reviewer.py` to track improvement loop history. (Issue #578)
67. **reviewer_weakness_analyzer.py** - Analyzes benchmark scoring reports to identify weak defect categories and generate improvement instructions for the reviewer agent. `analyze_weaknesses(report, *, samples, taxonomy, threshold, min_samples)` returns a `WeaknessReport` with `WeaknessItem` entries sorted by priority (accuracy deficit × failure-mode weight × sample count). Failure-mode weights: `silent-failure` 1.5×, `concurrency` 1.4×, `cross-path-parity` 1.3×, `security` 1.2×. `generate_improvement_instructions(weaknesses, *, max_instructions)` produces up to N markdown instructions targeting the top weaknesses. Used by `scripts/improve_reviewer.py`. (Issue #578)
68. **runtime_data_aggregator.py** - Collect, normalize, rank, and persist improvement signals from 5 sources: session activity logs (tool failures, hook errors, agent crashes), benchmark history (per-category accuracy deficits), CI/session logs (known bypass pattern matches), GitHub issues (auto-improvement labeled issues), and CIA findings from `.claude/logs/findings/YYYY-MM.jsonl` (Issue #1200). `aggregate(project_root, *, window_days, top_n, repo)` collects all signals, computes priority using `SEVERITY_WEIGHTS` × severity × log(1+frequency), sorts descending, caps at top_n, persists to `.claude/logs/aggregated_reports.jsonl`, and returns `AggregatedReport`. `collect_cia_findings(findings_dir, window_days=90)` aggregates CIA findings across sessions, grouping by `root_cause_tag` then title-token cluster (Jaccard via `issue_triage_analyzer.cluster_within_tag`); severity contract: `CIA_FINDING_SEVERITY_MAP = {"info": 0.33, "warning": 0.66, "error": 1.0}`. `fetch_issues_with_label(repo, label, limit, state, closed_within_days)` fetches raw GitHub issues via `gh` CLI with open/closed/all state support (Issue #1201); when `state != "open"` the `--json` field list adds `closedAt` and a post-filter drops issues closed before `now - closed_within_days`; `fetch_open_issues_with_label` is now a backward-compatible alias delegating to `state="open"`. Security: CWE-532 secret scrubbing, CWE-400 line cap (MAX_LINES=100,000), CWE-78 subprocess argument lists, CWE-22 path validation. (Issue #579; CIA collector Issue #1200; fetch generalization Issue #1201)

68a. **macro_promotion.py** - Pure-logic C3 promotion layer for `/improve --auto-file` (Issue #1201). Stdlib-only; no `gh` calls, no filesystem writes. Consumes `AggregatedSignal` output from `runtime_data_aggregator.collect_cia_findings`. Promotion gate: volume+breadth (`frequency >= PROMOTION_FREQUENCY_MIN=3` AND `distinct_sessions >= PROMOTION_DISTINCT_SESSIONS_MIN=2`) with an error fast-path (`max_severity_label == "error"` AND `frequency >= PROMOTION_ERROR_FREQUENCY_MIN=2`) — string-label equality on severity, never the float. `decide_promotions(signals, open_issues)` returns one `PromotionDecision` per signal with `route` in `{"create", "append", "hold"}`. `classify_route(signal, open_issues)` applies tag-equality filter first then `issue_triage_analyzer.cluster_within_tag` to prevent over-clustering across unrelated tags; appends to the lowest-numbered matching open issue. `detect_recurrence_after_close(signals, closed_issues)` runs over ALL signals (not just promoted) and returns `(tag, closed_issue_number)` pairs where a fix was applied but the symptom recurred — rendered as loud `FIX DIDN'T STICK:` lines in the digest. `build_digest` + `format_digest` produce a 5-section anti-habituation direction-guard digest (ACTIONS TAKEN / Recurrence-after-close / Match-rate / Findings-per-session / Error-without-other-channel); all 5 sections always render (empty or populated) to prevent signal habituation. Match-rate ALARM gates on BOTH `< MATCH_RATE_ALARM_THRESHOLD=50%` AND `open_count > OPEN_AUTO_IMPROVEMENT_COUNT_FOR_ALARM=20` (avoids false alarms in young repos). Findings-per-session ALARM fires on zero findings against positive observed sessions (CIA emission failure). Tunable threshold constants documented with re-evaluation gate: revisit after first 2 user-reviewed digests. 9 regression tests in `tests/regression/test_macro_promotion.py`. (v1.0.0, Issue #1201)
69. **runtime_verification_classifier.py** - Classifies changed files into runtime verification categories (frontend, API, CLI) so the reviewer can perform targeted runtime checks after static code review. `classify_runtime_targets(file_paths)` returns a `RuntimeVerificationPlan` with `has_targets` flag and typed target lists (`FrontendTarget`, `ApiTarget`, `CliTarget`). Frontend detection matches `.html`, `.tsx`, `.jsx`, `.vue`, `.svelte` extensions with per-framework suggested checks. API detection matches `routes/`, `api/`, `endpoints/`, `views/` path patterns and common server filenames, guessing framework (fastapi, flask, express) from path. CLI detection matches scripts and named CLI tools. All detection excludes test files. (v1.0.0, Issue #564)
70. **retrospective_analyzer.py** - Session log analysis and drift detection for the `/retrospective` command. Reads JSONL activity logs from `.claude/logs/activity/`, groups events by session, and runs three drift detectors: `detect_repeated_corrections(summaries, *, min_threshold)` flags correction patterns (revert, wrong, stop, etc.) recurring across multiple sessions; `detect_config_drift(project_root, *, baseline_commits)` uses `git diff HEAD~N` to surface large changes to `PROJECT.md` and `CLAUDE.md`; `detect_memory_rot(memory_dir, summaries, *, decay_days)` flags date-stamped memory sections older than `decay_days` with no recent corroboration. `load_session_summaries(logs_dir, *, max_sessions)` returns `SessionSummary` dataclasses. `format_as_unified_diff(edit)` renders `ProposedEdit` objects as unified diffs. Resource limits: `MAX_SESSIONS=50`, `MAX_EVENTS_PER_SESSION=200`, `MAX_LOG_FILES=100`. Security: CWE-22 path validation, CWE-400 resource caps, CWE-116 untrusted log content. (v1.0.0, Issue #598)
71. **batch_mode_detector.py** - Per-issue pipeline mode detection for `/implement --batch --issues`. Analyzes issue title, body, and labels to automatically select the appropriate pipeline variant (full/fix/light) for each issue. `PipelineMode` enum: `FULL`, `FIX`, `LIGHT`. `ModeDetection` dataclass: `mode`, `confidence` (0.0–1.0), `signals` (list of matched signal descriptions), `source` ("label"/"title"/"body"/"default"). `detect_issue_mode(title, body, labels)` applies priority: (1) label override — "bug" → FIX, "documentation" → LIGHT at confidence 1.0; (2) signal matching — `FIX_SIGNALS` / `LIGHT_SIGNALS` with title worth 2 pts, body worth 1 pt; (3) tie-break: fix wins over light; (4) default: FULL. `detect_batch_modes(issues)` accepts a list of dicts with "title", "body", "labels" keys (labels as list of strings or GitHub API dicts). `format_mode_summary_table(issue_numbers, titles, modes)` returns a formatted text table for display. (v1.0.0, Issue #600)
72. **doc_verdict_validator.py** - Validates that doc-master output contains a properly formatted `DOC-DRIFT-VERDICT` line. `validate_doc_verdict(doc_master_output)` returns a `DocVerdictResult` dataclass with: `found` (bool), `verdict` ("PASS"/"FAIL"/""), `finding_count` (int, -1 if unparseable, 0 for PASS, N for FAIL(N)), `raw_line` (the matched verdict line), `position_warning` (non-empty if verdict is not the final non-empty line), `word_count` (int, total words in the output), and `is_shallow` (bool, True when word_count < `MIN_DOC_VERDICT_WORDS`). `MIN_DOC_VERDICT_WORDS = 100` module-level constant: responses below this threshold indicate the `covers:` scan or semantic comparison was skipped (Issue #758). Strips ANSI escape codes before matching. When multiple verdict lines appear, uses the last one. `FAIL(0)` is treated as PASS. Used by the coordinator to detect missing verdicts and shallow (sub-100-word) responses before the pipeline completes. (v1.0.0, Issues #602, #758)
73a. **plan_freshness.py** - Plan freshness re-verification helpers for STEP 4.8 of `commands/implement.md` (Issue #1175, T2 fix complementary to the prompt-integrity T1 fix in Issue #1172). Two pure functions with minimal side effects: `extract_referenced_paths(plan_content)` parses a plan markdown blob using the STEP 5.5c file-path regex (`[\\w/.-]{1,512}\\.(py|md|json|yaml|sh|ts|js)`) and returns a deduplicated, sorted list of path strings truncated to MAX_PATHS=500 entries (Issue #1223); returns `[]` for empty/None input. The `{1,512}` upper bound on the character-class run is a ReDoS-defensive cap — adversarial 100 KB+ pads of `[\\w/.-]` chars no longer produce superlinear scanning time; legitimate paths (well under 512 chars) match identically (Issue #1194).
**O(n) path-check overhead guard** (Issue #1223): Results are capped at 500 paths to prevent unbounded memory consumption on pathological inputs; when truncation occurs, a debug-level log message reports the omission count. `verify_paths_exist(paths, repo_root)` accepts the output of `extract_referenced_paths` and a `Path` repo root, resolves relative paths under `repo_root`, and returns a sorted list of path strings whose resolved location does not exist on disk — empty list means all referenced paths were found. Security: applies canonicalize-then-contain via `Path.resolve()` + `relative_to()` — paths that escape `repo_root` via traversal (e.g., `../../etc/passwd`) or that fail to resolve are treated as missing; the helper never probes the filesystem outside `repo_root` (Issue #1193, CWE-22). Absolute paths in `paths` are also subject to the containment check. The regex mirrors STEP 5.5c structural validation in `commands/implement.md`; both must be kept in sync. Invoked by the coordinator when `PRE_VALIDATED_PLAN_PATH` is set AND the plan file's mtime age exceeds 86400 seconds (24 hours); on missing paths the coordinator re-invokes the planner exactly once via `construct_revision_prompt()` from `prompt_integrity.py`, matching STEP 5.5b single-revision semantics. Pure stdlib (`re`, `pathlib`) plus standard `logging` for debug output. 14 unit tests in `tests/unit/commands/test_pre_validated_plan_detection.py`; 6 path-traversal regression tests in `tests/unit/lib/test_plan_freshness_path_traversal.py` (Issues #1193, #1219); 3 ReDoS-bound regression tests in `tests/unit/lib/test_plan_freshness_regex_bound.py` (Issue #1194); 1 MAX_PATHS regression test in `tests/unit/lib/test_plan_freshness_max_paths.py` (Issue #1223). (v1.0.0, Issue #1175; v1.1.0, Issue #1193; v1.2.0, Issue #1194; v1.3.0, Issue #1223)
73. **prompt_integrity.py** - Real-time prevention of progressive prompt compression in batch processing. `validate_prompt_word_count(agent_type, prompt, baseline_word_count, *, max_shrinkage=0.15, invocation_context=None)` checks: (1) prompt must not be empty; (2) critical agents must have at least 80 words; (3) shrinkage vs baseline must be ≤ max_shrinkage (default 15%); when `invocation_context` is a member of `REINVOCATION_CONTEXTS`, the effective threshold is doubled (e.g. 15% → 30%) to accommodate naturally shorter re-invocation prompts. Returns `PromptIntegrityResult` with `passed`, `reason`, `shrinkage_pct`, and `should_reload` fields. `record_prompt_baseline(agent_type, issue_number, word_count)` persists word counts to `.claude/logs/prompt_baselines.json`. `get_prompt_baseline(agent_type)` retrieves the word count from the lowest-numbered (first) issue. `get_agent_prompt_template(agent_type)` reads the agent's `.md` source file for prompt reconstruction; path resolution: checks `{root}/plugins/autonomous-dev/agents/` first, and if that directory does not exist (consumer installs such as spektiv where templates live under `.claude/agents/`), falls back to `{root}/.claude/agents/` — primary path takes precedence when both exist (Issue #1118). `clear_prompt_baselines()` resets both baselines and batch observations at batch start (Issue #794 — also calls `clear_batch_observations()` internally). `compute_template_baselines(agents_dir=None)` reads each critical agent's `.md` template file and returns `{agent_type: word_count}` for all found templates — agents with missing files are skipped with a warning. `seed_baselines_from_templates(agents_dir=None, state_dir=None)` is deprecated and a no-op (Issue #810). Previously it seeded baselines from template word counts at 0.70× to act as a ground-truth floor (Issue #748), but template files (~2500 words) are far larger than coordinator-constructed task-specific prompts (~200-600 words), causing a systematic 25-50% false positive block rate. The correct approach is first-observation seeding: call `clear_prompt_baselines()` at batch start and baselines are established automatically from the first observed prompt for each agent per issue. The function logs a deprecation warning and returns an empty dict; the signature is preserved for backward compatibility. **Cumulative drift tracking** (Issue #794): `record_batch_observation(agent_type, issue_number, word_count)` appends an observation to `.claude/logs/prompt_batch_observations.json`; `get_cumulative_shrinkage(agent_type)` returns the percentage drift from the first to the latest observation (None if fewer than 2 observations, or if fewer than 2 distinct issue numbers appear across observations — single-issue remediation loops are excluded to prevent false positives, Issue #934; observations missing an issue identifier are discarded from the distinct-issue count rather than counted as a pseudo-issue); `clear_batch_observations(state_dir=None)` deletes the observations file. `MAX_CUMULATIVE_SHRINKAGE = 0.30` (30%) is the batch-level drift threshold used by the hook (Issue #870 calibrated from 15% — the original Issue #812 value — to reduce false positives on normal inter-issue variance). `REINVOCATION_CONTEXTS = {"remediation", "re-review", "doc-update-retry", "research-skip", "fix", "light"}` — contexts where prompts are naturally shorter and shrinkage thresholds are relaxed: doubled for most (Issue #789/#791), 3.0x for `"fix"` mode (Issue #1358), 2.5x for `"light"` mode (Issue #1359), and `"research-skip"` (Issue #1002) covers downstream agents that legitimately skip the research-output payload when STEP 3.5 detects a fully-specified change. `COMPRESSION_CRITICAL_AGENTS = {"security-auditor", "reviewer", "researcher-local", "researcher", "implementer", "planner", "doc-master"}` — mirrors the same set in `pipeline_intent_validator.py`. **Post-reload validation** (Issue #844): `validate_and_reload(prompt, agent_type, baseline_word_count, *, max_shrinkage=0.15, max_reload_attempts=2, agents_dir=None, invocation_context=None)` validates a prompt and, if it fails, reads the agent template from disk and re-validates — bounding the number of reload attempts via `max_reload_attempts` (default: 2). Fixes the gap where reloaded templates were used without re-validation. Returns `ValidateAndReloadResult` with `prompt` (best available), `validation` (`PromptIntegrityResult`), `reload_count` (int), and `reload_succeeded` (bool). **Content slot checking** (Issue #844): `validate_prompt_slots(agent_type, prompt)` checks that a prompt contains required content section markers for critical agents; agents not in `REQUIRED_PROMPT_SLOTS` always pass. `REQUIRED_PROMPT_SLOTS` maps `"security-auditor"` and `"reviewer"` each to three required slots: `("implementer output", "implementer")`, `("changed files", "changed file")`, `("test results", "test")`. Returns `PromptSlotResult` with `agent_type`, `present_slots`, `missing_slots`, and `passed` fields. Enables coordinators to detect and fill missing sections before agent invocation rather than discovering the omission after a failed block. **Revision prompt builder** (Issue #1116): `construct_revision_prompt(agent_type, baseline_context, feedback)` combines the full original baseline context with a feedback suffix so the resulting prompt's word count is always `>= len(baseline_context.split())`, defeating the prompt-integrity shrinkage detector on plan-critic REVISE and reviewer/security-auditor BLOCKING re-invocations. The coordinator previously passed only the new feedback to a second invocation, causing every revision to be blocked for compression. The returned string is `"{baseline_context}\n\n## REVISION FEEDBACK\n{feedback}"`. Mandatory use is declared in `commands/implement.md` COORDINATOR FORBIDDEN LIST, STEP 5.5b, and STEP 11. **Redispatch awareness** (Issue #1227): `set_redispatch_flag(agent_type)` and `consume_redispatch_flag(agent_type)` manage per-agent flags in PipelineState.redispatch_agents dict to signal legitimate re-invocations after ordering-gate denials; `is_canonical_template_match(agent_type, content, *, tolerance=0.10)` checks if a prompt closely matches the agent's canonical template (≥90% word overlap by default). `validate_prompt_word_count()` now short-circuits on redispatch flag or canonical-template match to avoid false-positive compression blocks. (v1.0.0, Issues #601, #603, #696, #748, #789, #791, #794, #844, #934, #1116, #1227)
223. **agent_dispatch_sentinel.py** - Tracks whether an Agent/Task tool dispatch is currently in flight, so `unified_pre_tool.py`'s protected-infrastructure hard floor (Issue #1296) can distinguish a coordinator's direct Write/Edit from an edit made by a dispatched implementer agent mid-`/implement`. `write(agent_name, repo_root=None, generation=None)` writes a sentinel JSON file (`{agent, pid, timestamp, armed_at, generation}`) to `<repo>/.claude/local/active_agent_dispatch.json` (per-repo isolation, Issue #1206 pattern) when an Agent/Task dispatch starts; `generation` (Issue #1484) is a per-dispatch token minted by `session_activity_logger.py` (`uuid.uuid4().hex`) and shared with the same dispatch's `subagent_invocation_cache` entry. `clear(repo_root=None, expected_generation=None, force=False)` (Issue #1484 — compare-and-delete redesign; **Issue #1512 — anonymous-clear refusal**) removes the sentinel: with `expected_generation=None` and `force=False` (the default), `clear()` now **refuses unconditionally** and returns without unlinking, writing a `[agent_dispatch_sentinel] WARNING: unidentified SubagentStop (no generation token) — refusing to clear` line to stderr. This replaces the prior "accepted backcompat gap" (the old unconditional `unlink()` on an anonymous clear), which measurement showed was not a rare edge case but the dominant failure path: a phantom `SubagentStop` naming an `agent_transcript_path` that was never written to disk would win the #1087 invocation cache (recovering the live dispatch's #1484 generation token) and use that token to satisfy `clear()`'s compare-and-delete, disarming a sentinel for a dispatch that was still running — observed to fire within about a minute of an ordinary dispatch. `force=True` bypasses the refusal and unconditionally unlinks; it is reserved for deliberate operator recovery of a stuck sentinel and must never be set by production callers (a phantom stop passing `force=True` would reintroduce the #1512 defect exactly). `DEFAULT_TTL_SECONDS` remains the sole backstop for genuinely abandoned sentinels, so refusing anonymous clears cannot leak one permanently. With `expected_generation` given, `clear()` reads the sentinel payload first and no-ops (does NOT unlink) when the payload's `generation` is present and does not match — i.e. a *different*, still in-flight dispatch owns the sentinel. This is the fix for the #1467 ABA race, where an overlapping sibling dispatch's `SubagentStop` could disarm another dispatch's still-active sentinel. Never raises. `is_active(ttl_seconds=DEFAULT_TTL_SECONDS, repo_root=None, max_lifetime_seconds=MAX_LIFETIME_SECONDS) -> bool` returns `True` only if the sentinel exists AND its `timestamp` is within `ttl_seconds` AND its lifetime since `armed_at` is within `max_lifetime_seconds`. **Issue #1512: `is_active()` is now a pure predicate — it never mutates the sentinel.** It previously unlinked a stale sentinel as a side effect of being read, which meant any diagnostic that merely inspected the gate destroyed the evidence it was measuring. That reaping now lives in the separate `reap_if_stale(ttl_seconds=DEFAULT_TTL_SECONDS, repo_root=None, max_lifetime_seconds=MAX_LIFETIME_SECONDS) -> bool` function, which unlinks the sentinel if and only if it is stale or past its lifetime ceiling and returns whether it did so; `unified_pre_tool.py`'s protected-path gate calls `reap_if_stale()` immediately before `is_active()` so that call site's observable behavior is unchanged. Malformed sentinel (missing/non-numeric `timestamp`, unreadable JSON) is treated as inactive rather than raising by both functions; a genuinely *corrupt* (JSON-undecodable) sentinel additionally emits a `[agent_dispatch_sentinel] WARNING` to stderr from `is_active()` and is deliberately left on disk (NOT reaped) by `reap_if_stale()`, since corruption has no ordinary cause now that writes are atomic and the file is kept as evidence for the operator. `DEFAULT_TTL_SECONDS = 600` (Issue #1447/#1471 — raised from the original 30s, which was shorter than real implementer dispatch latency: system-prompt/skill loading + one Read + streaming a multi-line Edit call reliably exceeded 30s, structurally denying every large protected-path edit even for legitimate agent-dispatched writes; `SubagentStop` still clears the sentinel on normal completion, so the 600s TTL only matters as a crash/forgotten-clear backstop). `refresh(ttl_seconds=DEFAULT_TTL_SECONDS, repo_root=None) -> bool` (Issue #1448) slides an existing sentinel's `timestamp` forward to now and returns `True`, making the TTL a *sliding* window: `session_activity_logger.py`'s `PostToolUse` branch calls it on every tool use, so a dispatched implementer doing reads, test runs and multi-file edits over many minutes stays continuously active instead of expiring mid-dispatch (the recurrence reported in #1448/#1475, where the implementer had to manually rewrite the sentinel before each edit — a BYPASS-tagged workaround). Sliding-TTL protection depends on that `PostToolUse` branch running: when `ACTIVITY_LOGGING=false`, `session_activity_logger.py` exits early before the `refresh()` call, so the #1296 gate silently degrades to the fixed `DEFAULT_TTL_SECONDS` (600s) window for that session — operators disabling activity logging in batch/CI runs lose sliding-TTL protection. `refresh()` is deliberately conservative and returns `False` without writing when the sentinel file is absent (it must never create one, or the coordinator could arm the gate with no real dispatch), when the sentinel is already past `ttl_seconds` (never resurrects a dead dispatch), or when the payload is malformed/non-dict; the existing `agent` and `pid` fields are preserved and only `timestamp` moves. With `refresh()` wired in, `DEFAULT_TTL_SECONDS` is only the *idle*/crash backstop — how long the sentinel survives with no tool activity at all. **Path resolution (Issue #1484)**: `_path(repo_root=None)` — the default (no-arg) branch, which ALL production callers must use, resolves the repo root via `path_utils.find_project_root()` (walks up for `.git`/`.claude` markers; never shells out to `git rev-parse --git-common-dir`, which is banned by `hook_path_validator.py`) rather than `Path.cwd()`, so the writer (`PreToolUse`), reader (`unified_pre_tool.py`), and clearer (`SubagentStop`) — three separate hook subprocesses — converge on one normalized sentinel path even when invoked from a subdirectory or a git worktree. The explicit `repo_root=` branch stays literal/unresolved and is test-only. Pure Python stdlib (`json`, `os`, `time`, `uuid`, `pathlib`), zero external dependencies. Tests: `tests/unit/lib/test_agent_dispatch_sentinel.py`, `tests/regression/test_issue_1448_sentinel_sliding_ttl.py`, `tests/regression/test_issue_1479_1480_sentinel_hardening.py`, `tests/regression/test_issue_1484_generation_token.py`, `tests/regression/test_issue_1484_path_convergence.py`, `tests/regression/test_issue_1512_atomic_sentinel_write.py`, `tests/integration/test_issue_1484_worktree_convergence.py`, `tests/hooks/test_issue_1484_fix4_stderr_warnings.py`. (v1.0.0, Issue #1296; v1.1.0 TTL 30s→600s, Issue #1447/#1471; v1.2.0 sliding TTL via `refresh()`, Issue #1448/#1475; v1.3.0 generation-token compare-and-delete + `find_project_root` path convergence, Issue #1484; v1.4.0 anonymous-clear refusal (`clear()` no longer unconditionally unlinks without a generation token, `force=True` added as the operator-recovery escape) + atomic same-directory writes via `os.replace()` + `is_active()`/`reap_if_stale()` split — pure-predicate read vs. explicit reap, Issue #1512)

74. **pipeline_timing_analyzer.py** - Automatic pipeline timing analysis for the continuous-improvement-analyst (check #11, Issue #621). Detects four finding types: `GHOST` (duration <10s, words <50), `WASTEFUL` (low words/sec over 60s), `SLOW` (exceeds static or adaptive p95×1.5 threshold), and `TOKEN_EFFICIENCY` (tokens-per-word ratio >500 — added Issue #704). `AgentTiming` dataclass includes `total_tokens` and `tool_uses` fields (populated from Agent result `<usage>` blocks via `session_activity_logger.py`). `format_timing_report(timings, findings, *, recoveries=None, blocked_without_recovery=0)` conditionally adds `Tokens` and `Tok/Word` columns to the timing table when any invocation has token data; the optional `recoveries` kwarg (Issue #1178) accepts a list of `PromptIntegrityRecovery` dataclasses and, when non-empty, appends a "Prompt-Integrity Recovery Overhead" section reporting total recoveries, cumulative and mean latency, unmatched block count, and a per-agent breakdown — default `None` preserves backward compatibility with all existing callers. Adaptive thresholds computed from rolling history via `load_timing_history()` / `save_timing_entry(timings, history_path)`. `check_consecutive_violations(agent_type, history_path, threshold)` counts consecutive recent runs exceeding a threshold — used as a circuit breaker before filing GitHub issues. Per-agent time budget functions added in Issue #705: `load_time_budgets(config_path)` loads `pipeline_time_budgets.json` (falls back to `STATIC_THRESHOLDS` when file missing); `check_budget_violation(agent_type, duration_seconds, budgets)` returns `None` if within budget or a dict with `level` ("warning"/"exceeded"), `duration`, `budget`, and `pct_used`; `format_budget_warning(violation)` formats a human-readable stick+carrot message with `REQUIRED NEXT ACTION` directive. Budget config at `plugins/autonomous-dev/config/pipeline_time_budgets.json`. **Prompt-integrity recovery analysis** (Issue #1178): `PromptIntegrityRecovery` dataclass captures a paired block+recovery event joined by `block_event_id` — fields: `block_event_id`, `agent_type`, `block_timestamp_iso`, `recovery_timestamp_iso`, `latency_ms`, `block_reason_category`. `load_prompt_integrity_events(log_path)` reads `.claude/logs/hook-blocks.jsonl` and returns rows whose `metadata.event_type` starts with `"prompt_integrity_"` (missing file returns `[]`; malformed lines silently skipped). **Issue #1611 narrowed this asymmetrically**: `prompt_integrity_block` rows must additionally be refusal-shaped per `hook_telemetry.is_refusal_row` (a "block" row carrying `mode_skip` is enforcement being *skipped*, not a block), while `prompt_integrity_recovery` rows are admitted regardless of shape because they record a subsequent ALLOW and `extract_prompt_integrity_recoveries()` cannot join a pair whose second half was filtered away. The classifier is imported with a `try/except ImportError` stale-install guard — this module is deployed to `.claude/lib/` and does not move in lockstep with its sibling — and the fallback is `None` (filter not applied, i.e. pre-#1611 behaviour) rather than a local rule copy, since a second definition inside a reader is the defect the issue removes. `extract_prompt_integrity_recoveries(events)` performs O(1) pairing of block+recovery rows by `block_event_id` and returns `(paired_recoveries, blocked_without_recovery)` — recovery rows without a matching block are ignored; unmatched blocks contribute to the second return value. **User-pause subtraction** (Issue #986): Module-level constants `MAX_ACTIVE_AGENT_SECONDS=3600.0` and `MIN_PAUSE_GAP_SECONDS=300.0` define the detection window. When `extract_agent_timings()` measures a raw timestamp gap exceeding `MAX_ACTIVE_AGENT_SECONDS`, it calls the private helper `_subtract_user_pauses(events, inv_event, comp_event, raw_gap)` which scans session events inside that window for contiguous idle spans >= `MIN_PAUSE_GAP_SECONDS` (5 min — longer than any Sonnet thinking pause) and subtracts the largest such span from the gap, producing a corrected `active_gap`. The `AgentTiming` dataclass, the `extract_agent_timings` public signature, and the `timing_history.jsonl` schema are all unchanged.
75. **version_reader.py** - Lightweight plugin version + git SHA stamping for session logs and auto-filed issues (Issue #630).
76. **test_pruning_analyzer.py** - AST-based test hygiene analyzer for `/sweep --tests`. Detects 5 categories of pruning candidates: dead imports, archived references, zero-assertion tests, duplicate coverage, and stale regression references. Default output is informational. `prune_tests(dry_run=True)` can delete fully-flagged files with safety guards (security exclusion, tier protection, whole-file-only). Returns `PruneResult` dataclass. (v1.0.0, Issue #674; pruning: Issue #736)
76. **test_pruning_analyzer.py** - AST-based test hygiene analyzer for `/sweep --tests`. Detects 5 categories of pruning candidates: dead imports, archived references, zero-assertion tests, duplicate coverage, and stale regression references. Default output is informational. `prune_tests(dry_run=True)` can delete fully-flagged files with safety guards (security exclusion, tier protection, whole-file-only). Returns `PruneResult` dataclass. (v1.0.0, Issue #674; pruning: Issue #736)
76b. **selector_stall_detector.py** - Backward-looking stall detector for the drain-watchdog (Issue #1303). Consumes a sequence of `(timestamp_iso, cluster_str)` FIRE_END telemetry tuples and reports whether the cloud-drain selector returned empty for K consecutive fires within a lookback window. Pure Python; no I/O; no subprocess. `detect_stall(fires, *, now_utc=None, k=K, window_hours=WINDOW_HOURS) -> SelectorStallResult` counts consecutive empty fires (where `cluster_str` is `""` or `"none"`, case-insensitive) from the newest end, stopping at the first non-empty fire or a fire outside the window. Module constants: `K=4` (consecutive-empty threshold) and `WINDOW_HOURS=6` (lookback window) are hardcoded per AC1 / Issue #1303 Finding 5 — edit module and add regression test to tune. `SelectorStallResult` frozen dataclass: `stalled: bool`, `consecutive_empty: int`, `window_hours_examined: int`, `reason: str`. Malformed ISO timestamps are skipped without resetting the streak (intentional trust assumption, Issue #1314 LOW-2 — documented in docstring with regression test `test_malformed_timestamp_row_is_skipped_without_resetting_streak`). Known limitation (AC4 relaxed, v1): does NOT inspect cluster severities to suppress false positives when all remaining clusters are `severity=high`. Used by `.github/workflows/drain-watchdog.yml` "Detect selector stall" step to file `[selector-stall]` issues with `selector-stall,high-priority` labels. 8 unit tests in `tests/unit/lib/test_selector_stall_detector.py` (8th added for #1314 FINDING-3: `test_malformed_timestamp_row_is_skipped_without_resetting_streak`). (v1.0.0, Issue #1303; hardening Issue #1314)

76a. **cluster_selector.py** - Cluster selection logic for `/drain-queue` command with tracker-shaped issue detection, leaf preference, and cross-machine in-progress check (Issues #1284, #1335). `select_next_cluster(clusters)` filters out multi-phase root-cause tracker issues, prefers their lowest-numbered open leaf children, and now also skips clusters whose issues are actively claimed by a different actor via `issue_claim.is_claimed()`. Tracker detection criteria (ANY match triggers): (1) Title starts with `[TRACKER]` (case-insensitive); (2) Labels contain both "root-cause" AND "enhancement"; (3) Body contains ≥2 phase headings (`^### Phase [A-Z]`) AND ≥2 issue references (`#\d+`). When a tracker with open leaf issues is encountered, returns a synthetic single-issue cluster pointing to the lowest-numbered open leaf with `{"root_cause_tag": original_tag, "issue_numbers": [leaf_n]}`. Returns `None` if no drainable cluster exists. **Note**: `select_next_cluster` makes `gh` CLI calls via `_is_cluster_closed` and `_is_cluster_in_progress` — it is NOT a pure function. (v1.0.0, Issue #1284; cross-machine mutex v1.1.0, Issue #1335)

76c. **issue_claim.py** - Cross-machine GH Issue claim mutex preventing `/implement --issues` and `/drain-queue → /implement --issues` from racing on the same cluster (Issue #1335). The claim signal is a GH Issue label `in-progress` PLUS a marker comment `🤖 Implementing #N now [host=…, pid=…, ts=…]` — both visible across machines via `gh`. Three public functions: `is_claimed(issue_number, *, actor, max_age_hours, now)` checks whether an issue has a fresh active claim from a DIFFERENT actor (self-claims are transparent; stale claims >4h are ignored inline with no separate reaper); `claim_issue(issue_number, actor)` posts the claim comment first then adds the `in-progress` label (both must succeed — returns `bool`); `release_issue(issue_number, actor, *, reason)` removes the label then posts a release comment (best-effort — callers must not fail the pipeline on `False` return). Internal constants: `CLAIM_LABEL = "in-progress"`, `CLAIM_MAX_AGE_HOURS = 4`, `GH_TIMEOUT_SECONDS = 10`. All `gh` calls are best-effort — any `gh` failure degrades to "not claimed" so the pipeline never deadlocks on transient network issues. Actor string format: `host:pid:run_id` from `_actor_string(run_id)`. Claim release called by `implement-batch.md` STEP B3 (terminal failure) and STEP B4 (success). Consumed by `cluster_selector._is_cluster_in_progress` for drain-queue selection. 23 regression tests in `tests/regression/test_issue_claim_interlock.py`. (v1.0.0, Issue #1335)
78. **acceptance_criteria_tracker.py** - Tracks which acceptance criteria from STEP 6 have corresponding tests, computing N/M coverage ratios surfaced in the STEP 8 quality gate report. `save_criteria_registry(criteria, artifact_dir)` writes a JSON registry mapping each criterion to its scenario_name and test_file. `load_criteria_registry(artifact_dir)` reads the registry (returns empty list if missing or corrupt). `compute_criteria_coverage(registry, tests_dir)` scans all test files under tests_dir and returns a `CriteriaCoverageResult` dataclass with `total`, `covered`, `uncovered_criteria`, `coverage_ratio`, and `has_warning` (True when total > 0 but covered == 0). Consumed by `step5_quality_gate.run_quality_gate()`. Coverage is advisory only — never blocks the pipeline. (v1.0.0, Issue #676)

79. **test_lifecycle_manager.py** - Orchestrates existing test analyzers (TestIssueTracer, TestPruningAnalyzer, tier_registry, coverage_baseline) into a unified `TestHealthReport`. Each analyzer runs in an isolated error boundary so a single failure produces a partial report rather than a crash. `TestLifecycleManager(project_root).analyze()` returns a `TestHealthReport` with `tracing`, `pruning`, `tier_distribution`, `coverage_baseline`, `summary` (aggregated `TestHealthSummary`), `scan_duration_ms`, and `errors` fields. `format_dashboard(report)` renders a markdown health dashboard with Gate Status lines showing PASS/FAIL against `PRUNABLE_THRESHOLD` (default 100) comparing deletable file count (not raw findings) and tier balance warnings. `check_prunable_threshold(report, threshold=None)` returns `(passed: bool, message: str)` for CI gate integration, comparing deletable file count against the threshold. `check_tier_distribution(tier_distribution)` returns `(passed: bool, message: str)` checking pyramid balance against 5:2:2:1 target ratio, warning when upper tiers (T0+T1+T2) < 25% of total. `check_issue_tracing(project_root, issue_number)` is a pipeline convenience wrapper that returns a warning string when an issue has no test references. Used by `/improve` STEP 2.7 and by `continuous-improvement-analyst` check #12. (v1.0.0, Issue #673; gate: Issue #736; tier distribution: Issue #908; deletable count: Issue #1317)

80. **skill_change_detector.py** - Detect which skills were modified in a changeset and check evaluation readiness. `detect_skill_changes(file_paths)` extracts skill names from paths matching `skills/*/SKILL.md`. `get_eval_status(skill_name, *, repo_root)` checks for eval prompts (`tests/genai/skills/eval_prompts/{name}.json`) and baseline data (`tests/genai/skills/baselines/effectiveness.json`), returning `{skill_name, has_eval_prompts, baseline, evaluable}`. `format_skill_eval_report(results)` formats per-skill results with PASS/WARNING/BLOCK verdicts (delta < -0.10 triggers BLOCK). `get_weak_skills(baselines_path, *, min_delta, min_pass_rate, stale_days)` identifies skills with weak delta, low pass rate, or stale baselines — used by `/improve` STEP 2.5 to surface skill health. Used by STEP 11.5 (Skill Effectiveness Gate) in `/implement` and by `/improve`. (v1.0.0, Issue #643)

81. **covers_index.py** - Pre-computed source-path to doc-file mapping for doc-master optimization.
88. **dependabot_tracker.py** - Dependabot security issue tracker — queries GitHub Dependabot API for open vulnerability alerts, creates deduplicated tracking issues for critical/high severity alerts individually and weekly batch issues for medium severity. Non-blocking STEP 13 integration. (v1.0.0, Issue #767) `build_covers_index(docs_dir)` scans all `*.md` files for `covers:` YAML frontmatter and returns a dict mapping each source path (or pattern) to the sorted list of doc files that cover it. `get_affected_docs(changed_files, index)` matches changed paths against index keys using exact match, prefix match (keys ending in `/`), and glob match (keys containing `*`), returning a deduplicated sorted list of affected doc paths. `save_covers_index(index, output_path)` writes the index as formatted JSON with `_generated` and `_doc_count` metadata keys. `load_covers_index(index_path)` reads the JSON and strips metadata keys. Eliminates doc-master's per-invocation 23-file scan; the index is pre-built by `scripts/build_covers_index.py` and stored at `docs/covers_index.json`. (v1.0.0, Issue #713)

89. **agent_output_health.py** - Ghost and absent agent output detection library for post-hoc pipeline health assessment (Issues #793, #792, #1266, #1436). `_get_agent_completions(events)` (shared private helper) filters to `agent_completion` events only and excludes any event whose `subagent_type` starts with the internal double-underscore sentinel prefix `__` — originally scoped to `__dedup_skip__:*` markers written by the SubagentStop dedup guard (Issue #1176), broadened by Issue #1436 to cover ALL `__`-prefixed internal hook markers (`__dedup_skip__`, `__phantom_dedup_skip__`, `__unattributable__`) since no legitimate agent name in `FULL_PIPELINE_AGENTS` begins with `__`. Both `check_agent_output_health` and `detect_zero_word_completions` call this helper, so neither produces false-positive ghost or `zero_word_agent_output` findings for any internal sentinel-marker event.

91. **fix_forward.py** - Opportunistic fix-forward classification for pre-existing test failures (Issue #860). `parse_failing_tests(pytest_output)` parses raw pytest output and returns a `set[str]` of failing test IDs (e.g., `"tests/unit/test_foo.py::test_bar"`), matching BOTH the verbose per-test shape (`id FAILED`) AND the short-summary shape (`FAILED id - reason`) that pytest's default `-r fE` reporter emits at any verbosity — the short-summary pattern was added in Issue #1533 because the pipeline's own `-q` baseline invocation nets verbosity 0 and previously produced zero parsed IDs even when pytest reported real failures. The short-summary pattern splits the ID from the failure reason as "non-space run plus an optional bracketed parametrize block", not on the first ` - `, so a parametrize value containing that same separator (`test_bar[a - b] - AssertionError`) is not truncated to `test_bar[a`. `classify_failures(baseline, current, known_flaky_tests=None)` compares a pre-implementation baseline set against the post-implementation current set and returns a dict with three keys: `"fixed"` (was failing, now passes), `"pre_existing_remaining"` (still failing, in both sets), and `"new_failures"` (newly introduced, only in current, excluding any IDs in `known_flaky_tests` when provided — Issue #983). The optional `known_flaky_tests` kwarg accepts a `set[str] | None`; default `None` preserves existing behavior (no exclusions). Pass the result of `flaky_tests.load_known_flaky_tests()` here to prevent known-intermittent tests from blocking the pipeline. `format_issue_body(test_id, context="")` formats a Markdown GitHub issue body suitable for `gh issue create --body` for auto-filing pre-existing failures with label `pre-existing-failure`. **Capture-failure detection (Issue #1533)**: encodes the invariant that a capture which executed zero tests is a measurement failure, never a baseline. `detect_capture_failure(pytest_output, returncode=None)` returns an optional `CaptureFailure` NamedTuple (`sentinel`, `reason`) by checking three independent signals — a pytest exit code in `{2, 3, 4, 5}` (interrupted/internal-error/usage-error/no-tests-collected), an abort BANNER on its own line (`!!! Interrupted: ... !!!`, a bang/equals-decorated `error(s) during collection` banner, a line-initial `INTERNALERROR>`, or the `no tests ran in ...` summary line — matched per line, case-sensitively, and skipping lines that report a failing test, so a marker word appearing inside a test ID, class name, or assertion message can never be read as a banner; a blob-wide substring search collided with the real in-repo `TestGateInternalErrorsFailClosed` class), or zero tests processed per the summary line (including the case where `parse_failing_tests` finds no IDs despite pytest reporting a nonzero failure count) — and `None` when the measurement is trustworthy, including a real measured zero. `count_executed_tests(pytest_output)` and `count_reported_failures(pytest_output)` sum the passed/failed/skipped/xfailed/xpassed and failed-only counts respectively off the LAST pytest summary line, returning `None` when no summary line is present. `is_capture_failure_sentinel(baseline_contents)` returns `True` when baseline file contents start with either `TIMEOUT_SENTINEL` (`__TIMEOUT__`, Issue #1094) or `COLLECTION_ERROR_SENTINEL` (`__COLLECTION_ERROR__`, Issue #1533) — both are exported as module constants alongside `CAPTURE_FAILURE_SENTINELS`, the tuple of both. Used by pipeline STEP 1 (baseline capture) and STEP 8 (classification and auto-filing) in `implement.md`, and by the implementer agent for handling pre-existing failures opportunistically. Pure Python, zero external dependencies. 13 unit tests in `tests/unit/test_fix_forward_classification.py`, 18 unit tests in `tests/unit/lib/test_fix_forward_capture_failure.py`, 31 spec tests in `tests/spec_validation/test_spec_issue860_fix_forward.py`, and 38 regression tests in `tests/regression/test_issue_1533_baseline_collection_error.py`. (v1.0.0, Issue #860; v1.1.0, Issue #983 — known_flaky_tests kwarg; v1.2.0, Issue #1533 — capture-failure detection + short-summary parsing)

95. **flaky_tests.py** - Known-flaky test allowlist helper for the fix-forward classifier (Issue #983). Companion to `fix_forward.py`. `load_known_flaky_tests(project_root)` reads `<project_root>/.claude/local/known_flaky_tests.json` — a flat JSON array of fully-qualified test ID strings — and returns a `set[str]`. Fail-open: returns empty set on missing file, malformed JSON, or non-list root (never raises). `mark_test_flaky(test_id, reason, project_root)` appends a test ID to the allowlist atomically (temp file + `os.replace`). Idempotent — does nothing if `test_id` is already present. Fail-open: silently no-ops on write errors. Directory created with `0o700`, file written with `0o600` permissions. Pass the result of `load_known_flaky_tests()` as the `known_flaky_tests` kwarg to `classify_failures()` to prevent known-intermittent test IDs from appearing in the `new_failures` bucket. Pure Python stdlib, zero external dependencies. (v1.0.0, Issue #983)

93. **hook_path_validator.py** - Validates every hook command path declared in `~/.claude/settings.json` (global) and `.claude/settings.local.json` (local) settings files (Issue #950). Walks all `hooks.<event>[].hooks[].command` entries and emits findings for five issue categories: `missing` (script file does not exist), `non_executable` (`.sh`/`.bash`/`.zsh` script lacks execute bit), `duplicate` (same canonical hook path registered in both global and local scopes — causes double-firing), `unresolved_env` (command references an env var not defined in the current environment), and `path_style` (command contains a disallowed path substring per the `DISALLOWED_PATH_SUBSTRINGS` registry — currently `~/.claude/` and `--git-common-dir`, both flagged at `error` severity; Issue #996 Phase B). **Canonical hook-path form updated (Issue #1036)**: the required pattern is now `${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}/.claude/hooks/<NAME>` — `CLAUDE_PROJECT_DIR` is the Claude-Code-set launch project root (git-independent, so it survives submodule checkouts where `git rev-parse --show-toplevel` would incorrectly resolve to the submodule root), with the `$(git rev-parse --show-toplevel)` fallback covering older CLIs that do not set the variable. `expand_path()` collapses the whole `${CLAUDE_PROJECT_DIR:-<default>}` expression to `project_root` via `_CLAUDE_PROJECT_DIR_DEFAULT_RE` before falling back to bare-`$CLAUDE_PROJECT_DIR`/`$CLAUDE_PLUGIN_ROOT` substitution, so the older bare `$(git rev-parse --show-toplevel)` form (still accepted, no longer the canonical hint) is not double-processed. The `_validate_path_style()` pass only inspects script-shaped tokens and fires even when the script does not yet exist on disk, so policy violations surface in clean checkouts. Findings reuse the `ValidationIssue` shape from `sync_validator.py` so downstream tooling (`/health-check`, `/sync`, GitHub Actions reports) can render a single unified shape. CLI: `python -m hook_path_validator --global-settings ~/.claude/settings.json --local-settings .claude/settings.local.json --project-root .`; exit code 1 when any error-severity issue is detected (or any warning under `--strict`), 0 otherwise. Tests across `tests/unit/lib/test_hook_path_validator.py`, `tests/integration/test_health_check_hook_validation.py`, `tests/spec_validation/test_spec_issue950_health_check_hook_validation.py`, and `tests/regression/regression/test_issue_1036_submodule_hook_paths.py` (submodule-safe canonical form). (v1.0.0, Issue #950; path_style pass: Issue #996; submodule-safe canonical form: Issue #1036)

92. **word_count_helpers.py** - Shared word-count helper for Claude Code message-content payloads (Issue #925). `count_words_in_content(content)` handles three input shapes: `str` (splits on whitespace), `list` of `{"type": "text", "text": ...}` blocks (sums words across all text blocks), and `None` (returns 0). Returns 0 for any unrecognised shape and never raises. Used by `hooks/session_activity_logger.py` (`_add_result_word_count`) and `hooks/unified_session_tracker.py` (`_count_words_in_transcript`) to handle both the legacy flat-string `tool_output["output"]` schema and the modern Anthropic Task `toolUseResult` list-of-blocks schema. Created to fix the root cause of 5 prior false-positive compression closures (#757, #723, #867, #805, #923): `_add_result_word_count` was reading only the flat-string key and logging `result_word_count: 0` for all implementer events. Pure Python, zero external dependencies. (v1.0.0, Issue #925)

90. **plan_validator.py** - Plan file validator for the planning workflow system (Issue #814). `find_latest_plan(plans_dir)` searches a directory for `.md` plan files and returns the most recently modified one (by mtime), or `None` if the directory is empty or missing. `validate_plan(plan_path)` reads the plan file and checks for three required sections: `## WHY + SCOPE`, `## Existing Solutions`, and `## Minimal Path` (matched case-insensitively via regex; section-level depth is flexible). Returns a `PlanValidationResult` dataclass with `valid` (bool), `missing_sections` (list), `plan_path` (Path), `age_hours` (float), and `expired` (bool; True when age exceeds `PLAN_EXPIRY_HOURS=72`). Expired plans trigger a warning only — they do not cause a validation failure. Used by `plan_gate.py` hook to enforce plan-before-write workflow. `AgentHealthVerdict` dataclass captures `agent_type`, `word_count`, `duration_ms`, `status` (one of `"healthy"`, `"ghost"`, `"zero_output"`, `"shallow"`), and `timestamp` for a single agent completion event. `detect_zero_word_completions(events)` scans `agent_completion` events and returns a `CRITICAL`-severity `Finding` with `pattern_id="zero_word_agent_output"` for every completion where `result_word_count == 0` — regardless of duration — since zero-word output is an unambiguous failure. Integrated into `pipeline_intent_validator._run_checks_on_events()` via lazy import to avoid circular dependency. `check_agent_output_health(events)` evaluates each `agent_completion` event against per-agent minimum word thresholds (`AGENT_MIN_WORD_THRESHOLDS`: security-auditor/reviewer/implementer/planner=50, doc-master/researcher/researcher-local=30; `DEFAULT_MIN_WORDS=10` for others) and classifies completions as `ghost` (0 words and duration < `GHOST_MAX_DURATION_MS=5000`ms), `zero_output` (0 words, duration >= 5s), `shallow` (below threshold), or `healthy`. `generate_batch_health_summary(events)` aggregates per-agent statistics from all completion events: `invocation_count`, `ghost_count`, `zero_word_count`, `avg_word_count`, `total_word_count` — suitable for post-batch reporting. (v1.0.0, Issue #800)

82. **pipeline_efficiency_analyzer.py** - Cross-run pipeline efficiency analysis for the continuous-improvement-analyst (check #14, Issue #714). Analyzes historical timing data from `timing_history.jsonl` to surface agent optimization opportunities. Three analysis functions: `detect_model_tier_recommendations(agent_entries, agent_type)` flags agents with stable quality (CV < 0.3) and efficient token usage (median tokens/word < 100) as downgrade candidates, and warns on prompt bloat (tokens/word > 500); `detect_token_trends(agent_entries, agent_type)` uses simple linear regression to detect rising token usage over sequential runs (flagged when slope > 0 and R² > 0.5); `compute_iqr_outliers(values)` returns values outside the standard IQR fences (Q1 − 1.5×IQR, Q3 + 1.5×IQR). Main entry point: `analyze_efficiency(observations, *, min_observations=5)` groups by agent_type, runs all three analyses, and returns a list of `EfficiencyFinding` dataclasses capped at 5 per report (circuit breaker). `format_efficiency_report(findings)` renders a Markdown summary. Consumes data from `load_full_timing_history()` in `pipeline_timing_analyzer.py`. Advisory only — never blocks the pipeline. (v1.0.0, Issue #714)

83. **secret_patterns.py** - Shared credential detection patterns — single source of truth for `hooks/security_scan.py` and `lib/active_security_scanner.py`. Exports `SECRET_PATTERNS` (list of `(regex_str, description)` tuples for API keys, AWS keys, generic secrets, database URLs, and private keys), `COMPILED_SECRET_PATTERNS` (pre-compiled versions for efficient reuse), `OWASP_CODE_PATTERNS` (list of `(regex_str, owasp_category, remediation)` tuples covering A03 command/code/SQL injection, A05 debug=True misconfiguration, A10 SSRF dynamic URL construction), `COMPILED_OWASP_PATTERNS`, and `DEPENDENCY_ADVISORIES` (dict of package → CVE advisory list for django, flask, requests, urllib3, cryptography, pillow, jinja2, pyyaml). (v1.0.0, Issue #710)

84. **active_security_scanner.py** - Active security scanning with three modes: dependency audit, credential history scan, and OWASP pattern scan. `dependency_audit(project_root)` parses `requirements.txt` and `pyproject.toml`, checks versions against `DEPENDENCY_ADVISORIES`, and runs `pip-audit` when available. `credential_history_scan(project_root, *, max_commits=1000)` scans `git log --all -p` diff lines against `COMPILED_SECRET_PATTERNS`, returning `CRITICAL` findings for any leaked credentials. `owasp_pattern_scan(file_paths)` checks Python source files against `COMPILED_OWASP_PATTERNS`, skipping test files and comments to reduce false positives. `full_scan(project_root, changed_files=None)` orchestrates all three scans and returns an `ActiveScanReport` dataclass with `findings` (sorted by `Severity` enum: CRITICAL→HIGH→MEDIUM→LOW), `scan_duration`, and `scans_completed`. `format_report(report)` renders Markdown with severity summary table, findings table, and remediation actions. Used by the `security-auditor` agent at STEP 0 before passive OWASP checklist review. (v1.0.0, Issue #710)

85. **context_budget_monitor.py** - Inline truncation warnings and context budget threshold tracking (pure Python, no external dependencies). `truncate_output(text, *, max_chars=12000, tail_chars=500)` returns text unchanged if within limit; when the text exceeds `max_chars` it inserts an inline `[TRUNCATED: N chars removed. Showing first K + last T chars]` marker so downstream agents know content was cut — the head-only path activates when `tail_chars >= max_chars`. `check_context_budget(current_tokens, max_tokens, *, warn_threshold=0.80, critical_threshold=0.95)` returns `None` below the warn threshold, an advisory `[CONTEXT NOTE: X% of token budget used. Prioritize completing current task over exploration.]` string between warn and critical thresholds, and a blocking `[CONTEXT WARNING: X% of token budget used (N/M). Complete current step only.]` string at or above the critical threshold; `max_tokens <= 0` always returns a critical warning. `estimate_tokens(text)` approximates token count via `word_count * 1.3` (model-agnostic rough estimate). Constants: `DEFAULT_MAX_OUTPUT_CHARS = 12000`, `DEFAULT_TAIL_CHARS = 500`, `WARN_THRESHOLD = 0.80`, `CRITICAL_THRESHOLD = 0.95`. Integrated into `implement.md` STEP 10b VERBATIM PASSING: coordinators MUST include the `[TRUNCATED: N chars removed]` marker at truncation points when passing file diffs to downstream agents. (v1.0.0, Issue #729)

87. **bugfix_detector.py** - Shared detection library for identifying bug-fix commits and features (pure Python, no external dependencies, Issue #737). Five public functions plus one shared constant: `is_bugfix_feature(description, labels=None)` checks feature descriptions and optional GitHub issue labels against keyword patterns (`fix`, `bug`, `broken`, `regression`, `crash`, `dedup`, `duplicate`) and label set (`bug`, `fix`, `bugfix`, `regression`, `hotfix`) — used by the implement.md HARD GATE at STEP 8. `is_bugfix_commit(message)` checks whether a git commit message starts with a `fix:`, `bugfix:`, or `hotfix:` prefix (supports conventional commit scopes, e.g., `fix(auth):`) — used by `enforce_regression_test.py` pre-commit hook. `get_test_count(project_root)` scans all `.py` files under `project_root/tests/` for `def test_*` functions and returns the total count — full-tree scan; still used for AC-mandated minimum-test-count checks (Issues #988/#1117), a separate concern from the regression gate below. `get_test_count_for_dirs(dirs, project_root=None)` mirrors `get_test_count()` but restricts the scan to the specified relative subdirectories, silently skipping non-existent dirs. `CANONICAL_TEST_COUNT_DIRS = ["tests/unit", "tests/integration", "tests/regression"]` (Issue #990 follow-up) is the single shared scope constant now consumed by BOTH the implement.md STEP 1 `BASELINE_TEST_COUNT` capture and the STEP 8 after-count — previously STEP 1 counted only `tests/unit` + `tests/integration` while STEP 8 rglobbed the whole `tests/` tree via `get_test_count()`, so the after-count always exceeded the baseline and the gate never blocked; the shared constant closes that scope mismatch and also makes a correctly-placed `tests/regression/` test visible to the baseline. `evaluate_regression_test_gate(baseline_count, current_count, project_root=None, dirs=None)` replaces the old two-state `current > baseline` comparison with a tri-state verdict — `("BLOCK"|"PASS"|"UNMEASURED", reason)` — returning `UNMEASURED` when `baseline_count is None` (e.g., the shell variable did not survive into a fresh coordinator process — STEP 1 now `export`s `BASELINE_TEST_COUNT` to close that gap) or when none of `CANONICAL_TEST_COUNT_DIRS` exists under `project_root` (a consumer repo with a non-canonical test layout, e.g. `test/` or `spec/`), keying on directory presence rather than a zero count so a canonical-layout repo with zero tests still `BLOCK`s. **A fourth verdict, `ERROR`, exists only in the caller's vocabulary — it is never returned by this function**, because the failure it names (a stale deployed `bugfix_detector.py` missing these symbols) prevents the module from importing in the first place, so no code inside the function can catch it. Both `implement.md` call sites (`# BEGIN/END BASELINE-TEST-COUNT`, lines 614/648, and `# BEGIN/END REGRESSION-TEST-COUNT-GATE`, lines 1514/1572) wrap their body in `try/except BaseException` so exactly one verdict line prints on every path, crashes included — `ERROR` fails CLOSED (blocks, `REQUIRED NEXT ACTION: bash scripts/deploy-all.sh`), the opposite of `UNMEASURED`, which still fails open by design. A third marker pair, `# BEGIN/END BASELINE-SCOPE-RECORD` (lines 650/682), extracts the STEP 1 scope-record block that used to write a fabricated `baseline_count=0` sentinel via unexported-variable coercion; it now reads `BASELINE_TEST_COUNT` from `os.environ` (not string-interpolated into embedded Python source) and skips the write entirely when the variable is unset, so an unmeasured baseline reads back as `None` (verdict `UNMEASURED`) rather than a false `PASS`. Both `try/except` blocks additionally truncate the caught exception to its first line (`str(_exc).splitlines()[0]`) before interpolating it into the printed verdict, closing a verdict-spoofing path where a multi-line exception message could forge a second, fake `REGRESSION_GATE:`/`BASELINE_TEST_COUNT:` line after the real one.
86. **blocking_signal_classifier.py** - Three-tier blocking signal classification for implementer adaptive replanning (pure Python, no external dependencies). `classify_blocking_signal(error_output)` inspects raw tool output and returns a `BlockingSignal` dataclass with `signal_type` (`BlockingSignalType.RECOVERABLE`, `STRUCTURAL`, or `NOT_BLOCKING`), `error_name`, `error_detail`, and `suggested_action`. Recoverable signals (ModuleNotFoundError, FileNotFoundError, ImportError, AttributeError, command not found / exit code 127) trigger mini-replan cycles; structural signals (SyntaxError, IndentationError, TabError) indicate the code must be fixed before retrying. `sanitize_error_for_directive(error_output)` truncates to `MAX_DIRECTIVE_ERROR_LENGTH=500` chars and removes newlines, delegating to `failure_classifier.sanitize_error_message` when available. `format_mini_replan_directive(signal, *, cycle)` produces a structured `[MINI-REPLAN cycle N/2]` directive for injection into the implementer prompt, including the error name, detail, suggested action, FORBIDDEN retry clause, and a final-cycle escalation warning when `cycle >= MAX_MINI_REPLAN_CYCLES=2`. Used by the implementer agent HARD GATE (Issue #730). (v1.0.0, Issue #730)

95. **tool_intent.py** - Shell command and tool-call intent classifier (Issue #971; widened to TRANSPORT-INDEPENDENT write classification by Issue #1503; gained a fourth registry for agent `optional_mcp:` declarability by Issue #1546). Replaces ad-hoc substring matching against command strings with a principled classifier that decides whether a tool call is a READ, WRITE, or EXEC operation and extracts the file paths it would write to. Handles native Claude Code tools by tool-name dispatch (`READ_TOOLS`, `WRITE_TOOLS`), MCP tools by registry dispatch (`MCP_READ_TOOLS`, `MCP_WRITE_TOOLS` — Issue #1503), Bash commands via `shlex.split` (env-var prefixes, redirections, pipes, sequential operators, `bash -c`/`sh -c` recursion), and `python -c` snippets via the AST-based `python_write_detector` library. Public API: `classify(tool_name, tool_input) -> Literal["READ","WRITE","EXEC"]` — returns the dominant intent, resolving native/MCP registries FIRST with a fail-closed path+content shape fallback (`_looks_like_write`) for unregistered tools only; `write_targets(tool_name, tool_input) -> List[str]` — returns file paths that would be written, resolving MCP path keys (`relative_path`, `path`) in addition to `file_path`; `is_write(tool_name, tool_input) -> bool` (Issue #1503) — the canonical transport-independent replacement for hard-coded `tool_name in ("Write", "Edit")` tests; `changed_content(tool_name, tool_input) -> str` (Issue #1503) — returns the content a call would write (concatenates `MultiEdit` edits, else first non-empty `CONTENT_KEYS` value), used by complexity gates so exemptions are about the CHANGE, not the TRANSPORT; `may_be_declared_optional(tool_name) -> bool` (Issue #1546) — the canonical predicate for "may an agent name this MCP tool under `optional_mcp:` frontmatter?", returning True for membership in the UNION of `MCP_READ_TOOLS` and the new `MCP_OPTIONAL_DECLARABLE_TOOLS` registry, False (fail-closed) for everything else including unclassified tokens and wildcards; `has_suspicious_exec(command) -> bool` — checks for suspicious exec patterns using `python_write_detector.SUSPICIOUS_EXEC_SENTINEL`. Design: conservative (false negatives acceptable; false positives are not), defensive (never raises — every error returns a safe default), composable (pure functions of inputs). `MCP_READ_TOOLS` is a strict superset of the legacy `_PLAN_EXIT_MCP_READONLY` frozenset formerly in `unified_pre_tool.py` (now deleted), adding the serena LSP read surface (`find_symbol`, `get_symbols_overview`, `find_referencing_symbols`, etc.); `mcp__playwright__browser_evaluate` is deliberately excluded (executes arbitrary JS, not read-only). `MCP_OPTIONAL_DECLARABLE_TOOLS` (Issue #1546) is a THIRD, deliberately disjoint MCP registry — 6 entries (5 Appium tools plus `mcp__playwright__browser_navigate`) whose effect is bounded and enumerable but which are not observation-only, so they may be *declared* under an agent's `optional_mcp:` key without being *granted* under `tools:`. It answers "may an agent be told to attempt this?" and is NOT the same set as `MCP_KNOWN_EXEC_TOOLS` in `scripts/audit_tool_intent_coverage.py` (a fourth, separately-maintained registry that answers "has anyone classified this tool name observed in the activity logs?" for CI coverage purposes) — the two sets are intentionally unmerged and their only member in common is `mcp__playwright__browser_navigate`. Consumed by `unified_pre_tool.py` (settings-write protection gate, protected-infrastructure hard floor, plan-exit deny-candidate gate — all via `is_write()`), `plan_gate.py`, `enforce_file_organization.py`, and `enforce_tier_distribution.py` (all three switched from literal `("Write", "Edit")` tuples to `is_write()`/`write_targets()`), `tests/unit/lib/test_agent_registry_consistency.py::TestAgentMcpToolDeclarations` (INV-5, via `may_be_declared_optional()`), and by `scripts/audit_tool_intent_coverage.py` (CI gate for tool-name coverage). Fixes the false-positive where `python3 -c "json.load(open('settings.json'))"` was incorrectly blocked by the settings-write gate because the command string contained the word "settings". Constants: `READ_TOOLS`, `WRITE_TOOLS`, `MCP_READ_TOOLS`, `MCP_WRITE_TOOLS`, `MCP_OPTIONAL_DECLARABLE_TOOLS`, `PATH_KEYS`, `CONTENT_KEYS`, `BASH_READ_BINS`, `BASH_WRITE_BINS`. Every call site keeps a stale-install fallback (the literal four-tuple `("Write", "Edit", "MultiEdit", "NotebookEdit")` — strictly stronger than the two-tuple it replaces, never weaker) for when an older `tool_intent.py` lacks `is_write`. Pure Python, defensive import of `python_write_detector` with no-op fallback when unavailable. (v1.0.0, Issue #971; v1.1.0, Issue #1503; v1.2.0, Issue #1546)

220. **edit_tier_classifier.py** - AST-based edit tier classifier for the default-on Write/Edit gate (Issue #1142+, Phase 1 + Phase 2 robustness Issues #1153/#1154). `classify_edit_tier(file_path, old_string, new_string) -> (tier, reason)` classifies a Write or Edit operation into one of three enforcement tiers: `"fix"` (small, low-risk — <20 added lines AND no AST structural change), `"light"` (new function, control-flow addition, signature change, or 20–99 added lines), `"full"` (new class OR ≥100 added lines). For Python files, classification is AST-based: both old and new content are parsed, and structural features (class names, function names, control-flow node counts, function signatures) are compared; the canonical-dump path detects comment-only, formatting-only, import-reordering, type-hint-only, and docstring-only edits and classifies them all as `fix`. For non-Python code files, a line-count fallback is used with `"light"` as the safe default (so a 1-line `.ts` edit never falsely upgrades to `full`). AST parse failures degrade to the line-count rule. `detect_bash_code_file_write(command) -> (target_path, pattern_name)` detects Bash commands that write to code-file extensions: `tee`/`tee -a`, `sed -i`, `cat > X`, `cat >> X`, heredocs (`<< 'EOF' > X.py`), `python -c "open(X, 'w')"`, `Path('X.py').write_text()`, base64-decoded heredocs, and `awk '...' > X.py`. Returns `("", "")` for patch tooling (`git apply`, `patch < diff`) and when no code-file write is detected. **Phase 2 additions** (Issue #1153): `detect_bash_code_file_write` now applies a `strip_heredoc_content` pre-pass (from `heredoc_utils.py`) before running Patterns 1/2/3/6/7/8, eliminating false-positive blocks when a heredoc body happens to contain a `cat > X.py` example; Pattern 4 (`<<EOF > X.py`) deliberately scans the unstripped command (the redirect is on the OPENER line). **Phase 2 additions** (Issue #1154): new `_resolve_chained_assignments(command) -> str` helper resolves `OUT=foo.py; cat > "$OUT"` (and the newline-separator variant) so downstream regexes see the literal target path; in-scope LHS forms: `"$NAME"`, `${NAME}`, `$NAME`; out-of-scope (acknowledged residual): `$(...)`, backticks, `${VAR:-default}`, arrays. New exports: `extract_heredoc_body_for_redirect(command) -> str`, `is_fresh_file_write_pattern(pattern_name) -> bool`, `_HEREDOC_BODY_RE`, `_FRESH_FILE_WRITE_PATTERNS`. Constants: `TIER_FULL_LINE_THRESHOLD=100`, `TIER_LIGHT_LINE_THRESHOLD=20`. Pure stdlib (`ast`, `re`, `pathlib`). Consumed by `unified_pre_tool.py`'s `_check_write_pipeline_required` gate and `_check_bash_write_pipeline_required`. **Issue #1408**: `_is_temp_path(path)` (used by the bash-code-file gate to skip scratch targets) now also recognises `/private/tmp/` and `/var/folders/` (macOS canonicalisation and pytest/mkdtemp defaults) and `$SCRATCHPAD`, closing the gap where the pre-#1408 list omitted these even though the Edit/Write gate's own `EPHEMERAL_PREFIXES` already covered them — the two lists had drifted apart. Never raises (wrapped in try/except). 38 unit tests in `tests/unit/hooks/test_unified_b2_activation.py`; 17 Phase 2 tests in `tests/unit/hooks/test_classifier_robustness.py`. (v1.0.0, Issue #1142; v1.1.0, Issues #1153/#1154; v1.2.0, Issue #1408)

221. **heredoc_utils.py** - Shared heredoc-stripping utility extracted from `unified_pre_tool._strip_heredoc_content` (Issue #1153). Prevents false-positive code-file-write blocks when a Bash command's heredoc body happens to contain a `cat > X.py` example. `strip_heredoc_content(command: str) -> str` removes all heredoc bodies (everything between the opening `<<['-]DELIM` line and the closing `DELIM` line) from a Bash command string. Handles: standard `<<EOF...EOF`, `<<-` POSIX indented form (closing delimiter may be tab-indented), single-quoted `<<'EOF'`, and double-quoted `<<"EOF"` delimiter forms. An unterminated heredoc is returned unchanged (no EOF fallback, no partial strip). **Issue #1620**: the original implementation matched the whole heredoc body with a single compiled regex (`_HEREDOC_PATTERN`, `r"<<-?\s*['\"]?(\w+)['\"]?.*?\n(.*?\n)*?[ \t]*\1\b"`); nesting a quantifier inside a lazy repeat made it exponential in body-line count on an unterminated heredoc (measured 6.65s end-to-end for a 147-character command against the 5s PreToolUse hook budget — a live gate-bypass, not merely latency). `_HEREDOC_PATTERN` has been deleted; there is no longer a single body-matching regex. It is replaced by a two-phase O(n) line scanner — `_build_line_index()` (indexes every line by its closing-delimiter token) and `_scan_openers()` (finds each heredoc opener and its matching close via that index) — that reproduces the deleted regex byte-for-byte, verified against 50,000+ seeded differential inputs with zero mismatches (`tests/unit/lib/test_heredoc_utils_scanner_equivalence.py`, `tests/integration/test_heredoc_redos_hook_end_to_end.py`). The public signature and fail-open-on-error contract (returns the input unchanged if the scanner raises) are unchanged. Pure stdlib (`re`, `bisect`). Shared by `unified_pre_tool.py` (Bash code-file detection AND two state-file deletion guards, replacing three inline regex duplicates) and `edit_tier_classifier.detect_bash_code_file_write`. Zero external dependencies. (v1.0.0, Issue #1153; v1.1.0, Issue #1620)

222. **cia_finding_store.py** - Atomic, fail-open append of structured CIA findings to monthly JSONL files (Issue #1200). `append_finding(record, *, findings_dir, now=None) -> bool` writes one finding record to `.claude/logs/findings/YYYY-MM.jsonl` (0600 perms, 0700 parent dir). Required record fields: `severity` (info|warning|error — normalized to "info" if invalid), `root_cause_tag`, `title` (≤200 chars, secret-scrubbed), `evidence` (≤2000 chars, secret-scrubbed), `file_refs`, `session_id`, `ts` (ISO-8601; defaults to UTC now). Extra fields passed through verbatim (e.g. `target_repo`). Security: CWE-117 CR/LF/TAB stripped from all string fields; CWE-532 secret scrubbing via `runtime_data_aggregator.scrub_secrets`; CWE-59 symlinked monthly files refused; CWE-22 explicit `..` traversal check; atomic writes via `fcntl.flock(LOCK_EX)` (degrades gracefully on NFS/Windows). Returns `True` on success, `False` on any failure (fails open — finding still surfaces in CIA report via stderr breadcrumb). `ValueError` raised only for non-absolute `findings_dir` (programmer error). Consumed exclusively by `continuous-improvement-analyst` agent. 14 unit tests in `tests/unit/lib/test_cia_finding_store.py`. (v1.0.0, Issue #1200)

94. **hook_bypass.py** - Universal hook bypass mechanism (Issue #969). Single source of truth for the two bypass signals that every hook honors, with one carve-out: `unified_pre_tool.py`'s protected-infrastructure Write/Edit hard floor (`_is_protected_infrastructure`, registered in `hard_floor_hooks.json`) does NOT honor this bypass (Issue #1435) — the caller checks `is_hard_floor()` before granting the bypass allow, falling through to the deny gate instead. `is_bypassed(start_dir=None)` returns `True` when either `AUTONOMOUS_DEV_BYPASS` env var is set to a truthy value OR a `.claude/.bypass` file exists in `start_dir` (or cwd if None) or any ancestor directory. `log_bypass_used(hook_name, tool_name, reason)` appends one JSONL event to `.claude/logs/hook-bypass.jsonl`; auto-creates parent directories; falls back to stderr on any `OSError`; never raises (bypass telemetry must not block the bypass itself). `_env_var_active()` — truthy: any non-empty string not in `{"", "0", "false", "no", "off"}` (case-insensitive). `_flag_file_in_chain(start_dir)` — walks parent chain up to `WALK_DEPTH_LIMIT=30`, does not follow symlinks. `ENV_VAR_NAME = "AUTONOMOUS_DEV_BYPASS"`. `BYPASS_FILE_RELATIVE = Path(".claude") / ".bypass"`. `LOG_FILE_RELATIVE = Path(".claude") / "logs" / "hook-bypass.jsonl"`. Pure Python stdlib, zero external dependencies. Companion tests: `tests/unit/lib/test_hook_bypass.py`, `tests/regression/test_universal_hook_bypass.py`. (v1.0.0, Issue #969)

    **Staleness reaper (Issue #1434)**: `check_bypass_staleness(start_dir=None) -> Optional[str]` is a SessionStart-only helper (called from `SessionStart-batch-recovery.sh`, never from the `is_bypassed()` hot path) that returns a WARNING string when a `.claude/.bypass` file is BOTH uncommitted (not git-tracked, checked via `_is_git_tracked()` running `git ls-files --error-unmatch`, fail-safe `False` on any error/timeout/missing git) AND older than `STALE_HOURS_DEFAULT = 24` hours, overridable via the `AUTONOMOUS_DEV_BYPASS_STALE_HOURS` env var (read at call time by `_stale_hours_threshold()`; unparseable/blank/non-positive values fall back to the default, never raises). Returns `None` when the env-var bypass is active, no `.bypass` file is found, the file is git-tracked, or the file is younger than the threshold. The entire function body is wrapped in a broad exception guard — staleness telemetry must never break session start.

96. **hook_telemetry.py** - Unified hook block telemetry (Issue #972, #942-D capstone). Single canonical surface for recording every "deny" decision a hook makes, across all three deny shapes used in the harness: `("deny", reason)` tuple (used by `unified_pre_tool.py` via `output_decision`), `{"decision": "block", ...}` dict (used by `unified_prompt_validator.py`), and `sys.exit(2)` (used by `enforce_orchestrator.py`). **Phase E extension (Issue #999)**: adds a fourth valid `decision_shape` value, `"mode_skip"`, emitted when `_phase_e_skip()` returns `(True, reason)` — records the skip event (not a block) so telemetry consumers can observe enforcement relaxations without confusing them with deny events. `"mode_skip"` is intentionally NOT paired with `"mode_enforce"` (enforce path emits nothing — existing block shapes cover those). `VALID_DECISION_SHAPES` frozenset updated to include `"mode_skip"`. Public API: `log_block_event(hook_name, decision_shape, reason, metadata=None)` — appends one JSONL row to `.claude/logs/hook-blocks.jsonl` with stable **8-field** schema `{ts, hook_name, decision_shape, refused, reason, metadata, session_id, cwd}` (`refused` added in Issue #1611 — a structural boolean derived from the shape, so a reader that ignores it makes a *visible* choice rather than an invisible omission); concurrent-write safety guaranteed via `fcntl.flock(LOCK_EX)` on POSIX (Issue #992 — `MAX_REASON_LENGTH=8000` exceeded POSIX `PIPE_BUF` atomic-append limits causing torn JSONL lines under concurrent hook invocations; flock adds ~1ms per write); on non-POSIX platforms where `fcntl` is absent (Windows) falls back to bare append; OSError from flock on NFS/unsupported FS is silently swallowed (telemetry must never break the hook decision path); falls back to stderr on write `OSError`; NEVER raises; `is_telemetry_disabled()` — reads `HOOK_TELEMETRY_DISABLED` env var (also honors `HOOK_RECOVERY_DISABLED` as a deprecated alias, emitting a one-time `DeprecationWarning`); `block_event_decorator(hook_name, *, decision_shape="tuple", refusal_values=None, metadata=None)` — factory that wraps an `output_decision` callable to instrument all deny sites through one decorator. All three keyword arguments were added in Issue #1611 and all three default to the pre-#1611 behaviour, so no existing caller moves: `decision_shape` labels the recorded row (`"dict"` for an emitter that PRINTS a JSON envelope); `refusal_values` is the set of decision values this emitter treats as a refusal (defaults to `DEFAULT_REFUSAL_DECISION_VALUES` = `{"deny"}`; **must be a set, not a bare string** — a string makes `decision in values` a substring test, and passing one raises `TypeError`); `metadata` is constant structured metadata stamped on every recorded row, used by `plan_gate.py` to record that the value it emits is the out-of-enum `"block"` with `honoured: "unverified"` pending Issue #1589. Idempotent — double-wrapping is a no-op, but a re-decoration requesting a **different** configuration now emits a stderr `DISCARDED` warning instead of being swallowed silently. **Refusal vocabulary exports (Issue #1611)**, defined here beside the only writer and imported by every reader (`scripts/hook_perf_report.py`, `scripts/hook_block_summary.py`, `lib/pipeline_timing_analyzer.py`), none of which keeps a local copy: `BLOCK_SHAPES` (frozenset of genuine refusal shapes — `tuple`, `dict`, `exit2`, `legacy_recovery`), `NON_REFUSAL_SHAPES` (documentation-only), `REFUSED_FIELD`, `DEFAULT_REFUSAL_DECISION_VALUES`, `NON_REFUSAL_EVENT_TYPES` (event types written *through* the recorder on an ALLOW path — currently `prompt_integrity_recovery`), `is_refusal_shape(shape)`, `row_event_type(row)`, `is_non_refusal_event_type(row)`, and `is_refusal_row(row)` — the single authority, testing event type first (a recovery row is an allow whatever its shape or boolean says), then the explicit boolean, then the shape; `can_user_recover(hook_name, block_reason)` — checks the exemption registry at `plugins/autonomous-dev/config/hook_recovery_exemptions.json` (malformed JSON treated as "no exemptions"). Rollback: `HOOK_TELEMETRY_DISABLED=1` disables writes without redeployment. Consumed by `unified_pre_tool.py` (via `@block_event_decorator`), `unified_prompt_validator.py`, and `enforce_orchestrator.py` (via explicit `log_block_event` calls). 28 unit tests in `tests/unit/lib/test_hook_telemetry.py`; 3 concurrent-write regression tests in `tests/regression/test_issue_992_pipe_buf_concurrency.py`. (v1.0.0, Issue #972; v1.1.0 Issue #999 — mode_skip shape; v1.2.0 Issue #992 — fcntl.flock concurrent-write safety)

96b. **hook_budgets.py** - Canonical hook time budgets (Issue #1704). ONE home for two numbers that were previously declared independently in at least four places: the execution budget the Claude Code runtime applies to a hook, and the subprocess/API timeout of a library that hook hosts. Backed by `plugins/autonomous-dev/config/hook_time_budgets.json`. **Why a sibling file rather than an extension of `config/pipeline_time_budgets.json`**: `pipeline_timing_analyzer.load_time_budgets()` unconditionally merges `STATIC_THRESHOLDS` (the eight pipeline-agent names) into every result, so a hook key added there returns accompanied by eight agent budgets and a settings generator iterating it would try to register `researcher` as a hook; the merge is neither optional nor parameterised. The field names (`budget_seconds` / `warning_pct`) and the `_`-prefixed comment convention are lifted verbatim, so this is the same mechanism applied to a second namespace, not a fourth pattern. **The 60s ceiling is NOT re-declared here** — `schema_max_seconds()` reads it from `hook-metadata.schema.json`, the file that actually refuses a larger value. Public API: `load_budget_config(config_path=None)` (never raises; degrades to a fail-safe default with empty hooks/libraries); `get_hook_budget(hook_name, config=None)` (accepts `foo` or `foo.py`; unknown hooks get the default, never zero); `has_hook_budget(...)` — distinguishes "budgeted at the default" from "not budgeted at all", which is what keeps unregistered processes that merely borrow `HookTimer` (notably `scripts/mutation_witness_gate.py`, registered nowhere, which contributed 56 spurious over-5s rows to the production timing sink — tracked separately as #1645) out of the overrun accounting; `get_library_timeout(key)` (raises `BudgetConfigError` — unlike hook budgets there is deliberately NO safe default, since silently substituting one re-creates the untracked constant); `library_timeout_or(key, fallback)` (the import-time-safe variant used by the three library constants); `OVERRUN_FLOOR_SECONDS` — the smallest budget for which an overrun can still be RECORDED; `check_ceiling()` refuses anything below it, because `hook_timing` short-circuits under that duration and such a hook would overrun forever while passing every check. This module is the authority and `hook_timing.MIN_BUDGET_SECONDS` is its performance mirror, locked by test. `check_ceiling()`, `check_nesting()`, `check_measured_headroom(margin=3.0)` — each paired with an anti-vacuity companion (`budgeted_hook_count()`, `measured_hook_count()`) and each REPORTING A VIOLATION rather than `[]` when the config loaded empty, so a pass over zero is impossible; `check_declared_hosts_match_derived()` — refuses a `host_hooks` list that omits a registered hook whose IMPORT GRAPH reaches the library, via `registered_hook_names()` / `reaches_module()` / `derive_host_hooks()`. The walk sees static imports, RELATIVE imports (`from . import x`, previously filtered out by `node.level == 0`) and DYNAMIC loads (string arguments to `spec_from_file_location` / `import_module`) — the last is essential because `importlib` is this repo's primary hook→lib loader and `unified_pre_tool.py` alone reaches 28 local modules that way. Verified in both directions: prose mentions of a module in a docstring, comment or string literal are NOT counted as edges (the #1698 shape). The one declared remaining blind spot is a module name COMPUTED at runtime, which under-credits rather than over-credits — the safe direction, since an omitted host is refused and an extra declared host is permitted; the hand-written list was already wrong (`auto_fix_docs` reaches `genai_prompts` through `genai_utils` and is registered at `PreCommit`, so a 15s library sat under an unbounded host the nesting guard never examined); `check_installed_settings_skew()` — compares canonical budgets against the INSTALLED `~/.claude/settings.json` and project `.claude/settings.json`, NOT the in-repo templates. It refuses THREE vacuity shapes as well as real skew: zero installed files (the consumer-repo case — a checker for undeployed state must not clear a machine with nothing deployed), a file that parses but registers zero hooks, and a MALFORMED file (previously the worst: `read_installed_timeouts` swallowed `JSONDecodeError` and returned `{}`, so a corrupt `~/.claude/settings.json` — a file that still governs execution — read as clean; it now returns `(timeouts, error)` so the caller can tell 'no hooks' from 'unparseable'). `inspected_settings_count()` is its anti-vacuity companion. Project-tier discovery uses `find_project_root()`, which walks UP and prefers `.git` over `.claude` — anchoring on `Path.cwd()` dropped the project tier when run from a subdirectory (#1697 class), and an unordered marker walk anchors on `plugins/autonomous-dev/.claude/`, a log artifact in this very repo. Surfaced through `--check-timeouts`, which **exits 1** on skew; `--allow-skew` is the narrow acknowledgement for a known pre-deploy window and does not mask drift or unbudgeted entries. This is the half that makes countability honest: `maybe_record_budget_overrun` compares a duration against the DECLARED budget, so if the installed settings enforce something smaller the runtime discards the decision at the smaller value while the recorder stays silent — under-reporting 100% of real skips. Every overrun row therefore carries `metadata.budget_source`. `min_declared_budget_seconds()` — the floor `hook_timing.MIN_BUDGET_NS` short-circuits on before paying a 3.28ms import+read on every hook exit (MEASURED, n=15 fresh processes; +51% on `unified_pre_tool`'s 6.4ms p50, reduced to 0.0005ms — 6,052x); a cross-validation test locks the literal to this function. `record_budget_overrun(...)`. **The nesting constraint**: a library's timeout must be STRICTLY less than every host hook's budget — at equality the runtime discards the hook at the same instant the library gives up, so the library can never report its own timeout. That equality was live: `intent_classifier_config.json` carried `timeout_seconds: 5` under a host registered at `"timeout": 5`. **Countable skips**: `record_budget_overrun` routes to the existing refusal sink `hook_telemetry.log_block_event` under `decision_shape="budget_overrun"` and `metadata.event_type="hook_budget_overrun"` — NOT a second sink, and NOT in `BLOCK_SHAPES`, so `is_refusal_row()` excludes it from refusal counts while `hook_block_summary.py`'s `by_decision_shape` keeps it visible. The record is possible at all because the runtime abandons the *wait*, not the *process*: the timing log holds COMPLETED rows at 13,139.7ms for a hook budgeted at 5s. 25 unit tests in `tests/unit/lib/test_hook_budgets.py`, 82 guard tests in `tests/regression/regression/test_issue_1704_hook_time_budgets.py` (counts MEASURED via `pytest --collect-only`, which is authoritative — a `^\s*def\s+test_` grep reports 22 for the unit file because one parametrized def expands to four collected cases). Every guard is exercised REFUSING and PERMITTING; the seven remediation classes were each confirmed RED against the pre-remediation source before their fix. (v1.0.0, Issue #1704; v1.1.0 remediation — write-path refusal, installed-settings skew, derived host_hooks, anti-vacuity companions, fast-path floor; v1.2.0 remediation 2 — skew is a GATE not a print, skew-check vacuity shapes, cwd-independent project root, importlib/relative-import edges, overrun-floor enforced in check_ceiling)

97. **hard_floor.py** - Hard-floor hook registry — explicit read-only list of hooks (and specific functions within hooks) that MUST always fire regardless of session mode (Issue #997, Phase C). Acts as a declaration layer that session-mode logic will query in Phase D before considering any disable/skip path. Dual-source with safe fallback: authoritative source is `plugins/autonomous-dev/config/hard_floor_hooks.json`; if the file is missing, malformed, or unreadable the module falls back to in-module constants (`_FALLBACK_HARD_FLOOR_HOOKS`, `_FALLBACK_OBSERVABILITY_HOOKS`) — fallback returns `True` ONLY for entries explicitly listed in the constant (never over-blocks arbitrary hooks). No caching: every call re-reads the JSON (file is ~1 KB, hook invocation rate is low double digits/second at most). Hard-floor hooks (catastrophe prevention): `security_scan.py` (file-level; secrets in commits), `unified_pre_tool.py::_check_bash_state_deletion` (rm/truncate of pipeline state), `unified_pre_tool.py::_detect_settings_json_write` (writes to settings.json), `unified_pre_tool.py::_is_protected_infrastructure` (writes to hooks/lib/agents/commands), `unified_pre_tool.py::_detect_git_bypass` (Detects git bypass attempts: force-push, --no-verify, git reset --hard, git clean -f). Always-run observability (non-enforcement, logging only): `session_activity_logger.py`, `conversation_archiver.py`, `unified_session_tracker.py`. Public API: `is_hard_floor(hook_name, function_name=None) -> bool` — returns True if the (hook, function) pair is hard-floor; `get_observability_hooks() -> list[str]` — returns a fresh list of always-run observability hook filenames. Matching rules: file-level entry (no `function` key) matches only when `function_name is None`; function-level entry matches when `function_name` equals the entry's function. Phase D will wire session-mode logic to call `is_hard_floor` before any disable/skip path. 6 test functions (16 parametrized cases) in `tests/unit/lib/test_hard_floor.py`. (v1.0.0, Issue #997)

98. **hook_timing.py** - Per-hook invocation timing telemetry (Issue #1012, W0 observability). Sibling of `hook_telemetry.py` — writes to a separate daily-rotated file (`~/.claude/logs/hook_timings_YYYY-MM-DD.jsonl`) so deny-decision telemetry and per-invocation timing can evolve independently. Each `HookTimer` context manager call emits one JSONL row with stable schema `{ts, hook, dur_ns, decision_shape, schema_version}`. All 24 active hooks wrap their `__main__` block with `HookTimer`. Durations use `time.perf_counter_ns` (monotonic, sub-millisecond precision — PEP 564). Design constraints mirror `hook_telemetry.py`: telemetry MUST NEVER raise; read-only filesystem fallback writes to stderr; zero-latency impact on the hook decision path. Public API: `HookTimer(hook_name, *, decision_shape="unknown", log_dir_override=None)` — context manager; `emit_timing_event(*, hook_name, dur_ns, decision_shape="unknown", log_dir_override=None)` — standalone emitter; `is_timing_disabled() -> bool` — reads `HOOK_TIMING_DISABLED` env var (truthy: non-empty string not in `{"0","false","no","off"}`). Security hardening (Issue #1056): `MAX_HOOK_NAME_LENGTH=128` constant caps the `hook_name` field before it reaches the JSONL log, preventing adversarial or malformed names from producing oversized rows that break downstream parsers; `LOG_FILE_MODE=0o600` constant sets owner-only permissions on the timing log file at creation time (via `os.open` opener) and is re-applied via `os.chmod` as a backstop for pre-existing files — prevents exposure of timing data on multi-user systems (CWE-732); `_sanitize_os_error(exc)` helper rewrites absolute paths in `OSError` messages to basenames before writing to stderr, preventing internal directory-tree leakage; `_ABS_PATH_PATTERN` compiled regex handles quoted and unquoted POSIX paths including those with spaces. Env vars: `HOOK_TIMING_DISABLED` (rollback switch), `HOOK_TIMING_DIR` (redirect log directory — used by tests and `scripts/capture_baseline.py`). Log path resolution order: `log_dir_override` argument → `HOOK_TIMING_DIR` env var → `~/.claude/logs/` (production default). `SCHEMA_VERSION=1` stamped on every row for forward-compatible reader upgrades. Pure Python stdlib, zero external dependencies. Companion libraries: `scripts/hook_perf_report.py` (p50/p95/p99 reporting from timing JSONL), `scripts/capture_baseline.py` (baseline driver writing to `baselines/`). 27 unit tests in `tests/unit/lib/test_hook_timing.py`, 17 unit tests in `tests/unit/scripts/test_hook_perf_report.py`, 6 integration tests in `tests/integration/test_hook_timing_wraps_all_hooks.py`, 6 integration tests in `tests/integration/test_baseline_artifact_present.py`, 4 regression tests in `tests/regression/test_w0_telemetry_doc_present.py`, 16 regression tests in `tests/regression/test_issue_1056_hook_timing_hardening.py`, 2 perf tests in `tests/perf/test_telemetry_overhead.py` (78 total). (v1.0.0, Issue #1012; v1.1.0, Issue #1056 — security hardening)

101. **validator_diversity.py** - Validator Diversity Score — measures complementarity between reviewer and security-auditor findings using Jaccard similarity (Issue #991). `score(reviewer_text, security_text)` computes `diversity = 1 − jaccard` over normalized finding tuples `(severity, category, file, line)`. `score_from_paths(reviewer_path, security_path)` reads artifact files and returns `files_present=False` when either file is missing or empty, so the CIA can omit the report subsection entirely. `parse_reviewer_findings(text)` parses `### FINDING-N` blocks with `**Severity**`, `**Category**`, `**File**` fields. `parse_security_auditor_findings(text)` parses OWASP `## A01: ...` section blocks. Severity normalization: `critical`/`high` → `blocking`, `medium`/`warning` → `warning`, `low`/`info` → `info`. OWASP category normalization: any `A0x:` prefix maps to `"security"`. Classifications: `"diverse"` (j ≤ 0.5, total ≥ 6), `"overlapping"` (0.5 < j ≤ 0.8, total ≥ 6), `"rubber-stamp"` (j > 0.8, total ≥ 6 — emits `[VALIDATOR-OVERLAP]` alert), `"tiny-sample"` (total < 6, both non-empty), `"complementary"` (total < 6, one validator empty), `"blind-spot"` (both empty — emits `[VALIDATOR-BLIND-SPOT]` alert). When both validators are empty, `diversity` is pinned to `0.0` to signal "no signal". CLI: `PYTHONPATH="plugins/autonomous-dev/lib" python3 -m validator_diversity --reviewer PATH --security PATH [--json]`. Info severity only — never blocks the pipeline. Artifacts written to `.claude/logs/activity/validators/{run_id}/` by `implement.md` STEP 10/10b/11 and `implement-batch.md` STEP B3. Pure Python stdlib, zero external dependencies. (v1.0.0, Issue #991)

100. **doc_drift_detector.py** - Periodic-aggregation pass for narrative-doc drift (Issue #1098, sub-issue #1 of umbrella #1075). Sweeps every doc with `covers:` YAML frontmatter against actual code/component state to detect count drift and enumeration drift across the whole repo. `detect_doc_drift(project_root)` is the main entry point — returns a list of `DocDriftFinding` dataclasses. `DocDriftFinding` fields: `doc_path` (repo-relative POSIX string, never absolute), `drift_type` (`"count_mismatch"` or `"enumeration_drift"`), `description` (human-readable, e.g., "Library count: docs say 216, actual 219"), `severity` (`"low"` | `"medium"` | `"high"`), `auto_fixable` (bool), `line_number` (1-indexed or None). Two primitive detectors: `count_mismatch` scans lines for patterns like "N libraries" / "N hooks" / "N agents" / "N commands" / "N skills" and compares against filesystem counts (strategy: `"py"` for libraries/hooks, `"md"` for agents/commands, `"dirs"` for skills); `enumeration_drift` scans numbered/bulleted list items under recognized section headers and checks whether each item's basename matches an existing file. Reuses `covers_index.build_covers_index()` for doc discovery. First concrete instance of the periodic-aggregation pattern. Invoked by `/refactor --docs`. Pure Python stdlib, zero external dependencies. (v1.0.0, Issue #1098)

99. **subagent_invocation_cache.py** - Cross-hook FIFO correlation cache for SubagentStop instrumentation (Issue #1087). Fixes empty `subagent_type` and `duration_ms=0` in SubagentStop log entries by capturing invocation data at PreToolUse time and recovering it at SubagentStop time. `cache_path(session_id) -> Path` — computes `/tmp/subagent_invocations_{sha8}.json` using `sha256(session_id)[:8]` to avoid path injection. `cache_invocation(session_id, subagent_type, *, start_time=None, description="", generation="") -> bool` — appends a queue entry (subagent_type, start_time, description truncated to 200 chars, generation) to the per-session JSON queue under `fcntl.LOCK_EX`; rejects empty subagent_type; returns False on any failure; never raises. `generation` (Issue #1484) stores the per-dispatch token minted by `session_activity_logger.py` so `pop_invocation()` can hand it back to the `SubagentStop` caller, which passes it to `agent_dispatch_sentinel.clear(expected_generation=...)` for the compare-and-delete that prevents one dispatch's completion from disarming a sibling dispatch's still-active sentinel. `pop_invocation(session_id, *, preferred_subagent_type="") -> Optional[dict]` — pops the next entry via FIFO with optional preferred-type preference: if `preferred_subagent_type` is set, the oldest matching entry is selected; otherwise pure FIFO; the returned dict includes the stored `generation` field; returns `None` when queue is missing, empty, stale (mtime older than `TTL_SECONDS=3600`), or unreadable; never raises. `peek_queue(session_id) -> list` — read-only snapshot of the current queue; never raises. Called by `session_activity_logger.py` (PreToolUse writer) and `unified_session_tracker.py` (SubagentStop reader). Pure Python stdlib. 15 new tests in `tests/unit/hooks/test_session_activity_logger.py`; generation-field coverage in `tests/regression/test_issue_1484_generation_token.py`. (v1.0.0, Issue #1087; v1.1.0 adds `generation` field, Issue #1484)

88b. **baseline_guardrail.py** - Advisory guardrail that detects sentinel-without-baseline-cmd state and emits a structured warning to stderr (Issue #1139). Single public function: `warn_if_baseline_missing(state_path: str) -> bool` — checks whether the pipeline sentinel at `state_path` exists but lacks a `baseline_cmd` field (indicating the coordinator started a pipeline run but STEP 1 baseline capture did not call `record_baseline_scope`). When the condition is detected, writes `[BASELINE-MISSING-WARNING] {state_path} exists but no baseline_cmd recorded. The coordinator MUST NOT use git stash as a baseline-comparison workaround — re-run STEP 1 baseline capture.` to stderr and returns `True`; returns `False` when the sentinel is absent (pipeline inactive) or when `baseline_cmd` is already recorded. NEVER raises — all error paths are swallowed and return `False` (advisory only). Imports `get_baseline_scope` from `pipeline_state.py`. Used by the coordinator to surface the root cause when the `git_stash_mid_pipeline` bypass pattern is detected. Pure stdlib. (v1.0.0, Issue #1139)

102. **drain_queue_state.py** - State primitives for the `/drain-queue` autonomous queue drainer. Four state classes stored under `<repo_root>/.claude/local/`: `DrainBudget` (daily drain-count + wall-clock cap, fail-CLOSED on corrupt JSON per OWASP LLM06 — returns an EXHAUSTED budget so a tampered file cannot bypass the cap), `CircuitBreaker` (consecutive + rolling-window failure tracking, fail-OPEN: corrupt file → CLOSED state), `PauseFlag` (operator/system pause sentinel with deadline body; fail-OPEN on malformed body; fail-CLOSED on path-validation failure — `is_active()` returns `(True, "path_validation_failed")` when CWE-22 traversal or CWE-59 symlink is detected on the flag path so a symlink attack cannot silently disable the pause), `DrainHistory` (append-only JSONL outcome log under `drain_log.jsonl`; tolerates malformed lines on read; write failure propagates `OSError`; supports optional `revert_status` and `revert_sha` fields for Phase C auto-revert tracking per Issue #1292; includes `latest_pending_reverts()` classmethod to query records with `outcome=success` and `revert_status=pending`). Five pure-function gates: `severity_gate(cluster_severity)` blocks when severity not in `AUTO_DRAINABLE_SEVERITY` (ADR-002 Phase D partial: blocks only `high` now — `low`/`info`/`medium` all pass; `confidence_gate` is the real autonomy decision per PROJECT.md Layer 4); `tag_gate(cluster_labels)` blocks when labels intersect `HUMAN_GATE_TAGS`; `size_gate(cluster_size)` blocks when size exceeds `MAX_CLUSTER_SIZE_AUTO_DRAINABLE`; `skip_gate(cluster_labels)` returns skip (try next) for `SKIP_LABELS` ({blocked, waiting}); `evaluate_cluster_gates(severity, size, labels)` runs severity → tag → size short-circuit and returns `(verdict, reason)` where verdict is `"pass"` or `"stop"`. Eight module constants pin all thresholds (single source of truth, asserted by tests to prevent drift): `MAX_DRAINS_PER_DAY=10`, `MAX_WALL_SECONDS_PER_DAY=14400` (4h), `CONSECUTIVE_FAIL_PAUSE_HOURS=4`, `DAILY_FAIL_THRESHOLD=3`, `LONG_PAUSE_HOURS=24`, `MAX_CLUSTER_SIZE_AUTO_DRAINABLE=5`, `HUMAN_GATE_TAGS=frozenset({security, security-advisory, bypass, auth, breaking-change, needs-design, human-only, major})`, `AUTO_DRAINABLE_SEVERITY=frozenset({low, info, medium})` (ADR-002 Phase D partial — full gate retirement deferred), plus `SKIP_LABELS=frozenset({blocked, waiting})`. Atomic writes delegate to `pipeline_state.atomic_write_json` (formerly `_atomic_write_json`, now public; alias preserved for backward compatibility — Issue #1320). All flag-path operations route through `pause_controller.validate_pause_path` to apply CWE-22 and CWE-59 guards. Tests: 23 unit (budget) + 32 unit (gates — includes 3 new in ADR-002 Phase D for medium-pass + high-blocks + evaluate-with-medium-and-low-confidence-blocks-by-confidence interaction) + 21 regression (circuit breaker + pause flag) + 4 unit (revert fields) = 80 tests. (v1.0.0; v1.1.0 ADR-002 Phase D partial)

103. **drain_runner.py** - Subprocess wrapper layer for the `/drain-queue` runner. One dataclass `DrainResult` (`success: bool`, `exit_code: int`, `wall_seconds: float`, `stdout: str`, `stderr: str`, `cluster_id: str`). Ten public functions, each with explicit `cwd=` and `env=` kwargs per Issue #1064 (subprocess context-bleed prevention): `check_clean_worktree(repo_root, env)` returns True when `git status --porcelain` is empty; `default_branch(repo_root, env)` resolves the default branch via `git remote show origin` → `git symbolic-ref refs/remotes/origin/HEAD` → `"master"` fallback (no hardcoded branch); `hydrate_issue_labels(issue_numbers, repo_root, env)` calls `gh issue view --json labels` per issue and returns a unioned `frozenset[str]` (v1 workaround for `TriageFinding` having no labels field — v2 will hydrate at triage time); `fetch_remote(repo_root, env)` runs `git fetch origin`; `remote_diverged(repo_root, env)` checks `git rev-list HEAD..@{upstream}` for non-zero ahead count; `push_to_default_branch(repo_root, env, branch)` runs `git push origin <branch>`; `relevant_files_changed(repo_root, env)` checks `git diff --name-only HEAD~1` against deploy-relevant path prefixes; `invoke_deploy_all(repo_root, env)` runs `bash scripts/deploy-all.sh`; `append_stop_notification(reason, drain_log_dir)` appends one JSONL row to `<drain_log_dir>/notifications.jsonl` for headless `/loop`/`/schedule` contexts where `PushNotification` is unreachable; `run_drain(...)` is the top-level orchestrator that invokes `/implement --issues <num>` as a subprocess with `cwd=<repo_root>` and `env=` containing `BATCH_NO_WORKTREE=1` when `_is_autonomous_dev_repo(repo_root)` detects the canonical autonomous-dev marketplace marker. STEP 1 uses `get_legacy_sentinel_path()` (Issue #1206 per-repo sentinel) rather than the obsolete `/tmp/implement_pipeline_state.json` literal. All subprocess invocations use list-arg form (`shell=False`) with explicit `timeout=` and capture stdout/stderr for `DrainResult`. Tests: 25 regression covering subprocess `cwd=` / `env=` / `timeout=` kwargs (`tests/regression/test_drain_queue_runner_subprocess_kwargs.py`). (v1.0.0)

104. **drain_pending.py** - Drain-pending marker file primitive for the `/drain-queue` durability gate (round-2 PROCEED plan). One dataclass `DrainPendingMarker` with fields `issues: list[int]`, `cluster_tag: str`, `started_at: str` (ISO-8601 UTC), `session_id: str` (defaults to `$CLAUDE_SESSION_ID` or `"unknown"`). Four classmethods: `write(*, issues, cluster_tag, session_id=None, repo_root=None)` atomically writes to `<repo>/.claude/local/drain_pending.json` via `pipeline_state.atomic_write_json` (mode 0o600; formerly `_atomic_write_json`, now public — Issue #1320) — rejects empty issues with `ValueError`; `read(repo_root=None) -> Optional[DrainPendingMarker]` tolerates missing file, malformed JSON, non-dict root, and non-list `issues` (all return `None` so the gate fails OPEN on parse errors); `clear(repo_root=None) -> bool` idempotent — returns True iff a file was unlinked; `is_stale(*, now=None) -> bool` returns True when the marker is older than `STALE_MINUTES=240` (4h) OR when `started_at` is empty / unparseable. **The companion commit gate at `unified_pre_tool.py::_check_drain_pending_commit_gate` MUST NOT consult `is_stale()`** — long `/implement` runs (2h+ observed) require uninterrupted enforcement; TTL is for SessionStart cleanup only. Path resolution delegates to `pipeline_state.get_legacy_sentinel_path()` for per-repo isolation (Issue #1206 policy). Tests: 16 unit (`tests/unit/lib/test_drain_pending_marker.py`) — write/read round-trip preserves all fields including session_id, atomic-write survives mid-rename failure (no half-written file, no stray temp files), env-var session_id fallback, malformed JSON returns None, non-list issues returns None, is_stale() True for malformed/empty timestamps, is_stale() False before threshold and True after. Companion regression tests in `tests/regression/test_drain_commit_gate.py` (28) and `tests/regression/test_drain_queue_verifies_state_closed.py` (7). (v1.0.0)

88c. **semantic_gate.py** - Phase-1 shadow judge + Phase-2 SWE intent router (log-only). Two independent public entry points coexist: **Phase 1** `judge(*, file_path, old_string, new_string, tool_name, tier_signal, session_id=None) -> JudgeResult` — shadow-judges the existing rule-based tier decision and writes one JSONL row to `.claude/logs/judge/<date>.jsonl`. **Phase 2** `route(*, file_path, old_string, new_string, tool_name, session_id=None) -> RouterResult` — per-task SWE intent router that classifies whether a code edit is feature/SDLC work (`"agree"` → suggests `/implement`) or not (`"disagree"` / `"abstain"`); audit rows written to `.claude/logs/route/<date>.jsonl` (separate log from judge). `is_write_to_code_file(tool_name, tool_input) -> bool` is a gate filter that returns True only for Write/Edit/MultiEdit targeting extensions in `_ROUTER_CODE_EXTENSIONS` (`.py .sh .js .ts .tsx .jsx .md .json .yaml .yml .toml`). Both phases share the same Haiku model and fail-open semantics: any failure returns an `abstain` result and NEVER raises. **Phase 1 feature flag**: `semantic_gate` key in `.claude/feature_flags.json`. **Phase 2 feature flag**: `swe_router` key (default OFF, opt-in via `is_feature_explicitly_enabled`); when `swe_router` is enabled in `unified_pre_tool.py`, it invokes `route()` instead of `judge()`; the legacy Phase 1 judge remains available as fallback when only `semantic_gate` is enabled. `RouterResult` frozen dataclass fields: `verdict`, `route_target` (one of `"/implement"` or `"none"` — deterministic mapping from verdict), `reasoning` (≤200 chars), `latency_ms`, `cache_hit` (always False in Phase A), `fail_open`. `JudgeResult` frozen dataclass fields: `verdict` (one of `"agree"` / `"disagree"` / `"abstain"`), `confidence` (float 0.0–1.0), `reasoning`, `fail_open`, `latency_ms`, `cache_hit`. `ROUTER_PROMPT_VERSION = "v2"` constant; `PROMPT_VERSION = "v1"` for judge. Session-bounded SHA-256 cache (no TTL) applies to Phase 1 only — Phase A router does not cache. Test overrides: `LOG_DIR_OVERRIDE` module-level attribute routes both judge and route audit writes to `tmp_path`; `_reset_cache_for_testing()` and `_reset_analyzer_for_testing()` clear module-level state. (v1.0.0 Phase 1 shadow mode; v1.1.0 Issue #1263 Phase A — per-task SWE router)

88. **intent_classifier.py** - Semantic intent classifier for user prompts (Phase 1, shadow mode). `IntentClassifier.classify(prompt)` applies a two-stage pipeline: (1) compiled regex of 38 security-keyword stems runs FIRST — any match short-circuits to `IntentClass.SECURITY_CRITICAL` without calling the LLM, defending against OWASP LLM01:2025 prompt injection; (2) if the regex misses, Claude Haiku 4.5 (`claude-haiku-4-5-20251001`, pinned) is called via `genai_utils.GenAIAnalyzer` with a strict JSON-only prompt. Returns `IntentResult` (frozen dataclass): `intent` (one of 9 `IntentClass` values — security_critical, implement, refactor, test, doc, config, typo, status_query, conversation — or `AMBIGUOUS` fail-open sentinel), `confidence`, `regex_hit`, `llm_used`, `fail_open`, `requires_security_audit`, `prompt_length`, `predicted_file_count`, `reasoning`. Any failure path (timeout, SDK unavailable, malformed JSON, intent outside enum, confidence < threshold, NaN/inf confidence, empty/None prompt) returns `IntentResult(intent=AMBIGUOUS, fail_open=True, requires_security_audit=True)`. `IntentClassifier.from_config(path=None)` loads `plugins/autonomous-dev/config/intent_classifier_config.json` (tunable: `model`, `max_tokens`, `timeout_seconds`, `confidence_threshold` default 0.85, `max_prompt_chars`, `security_keywords`, `telemetry.enabled`). Every call appends one 9-field JSONL line to `.claude/logs/activity/{YYYY-MM-DD}.jsonl` (telemetry failures never raise). Consumed by `unified_prompt_validator.py` when `INTENT_CLASSIFIER_ENABLED=true`; default OFF — hook output byte-identical when disabled. Coexists with `genai_prompts.py::INTENT_CLASSIFICATION_PROMPT` (different 5-class scheme, different consumer). 68 test functions in `tests/unit/lib/test_intent_classifier.py` (includes 8 `TestPromptInjectionResistance` tests added in Phase 2, Issue #960). Phase 2 hardening: user input wrapped in `<user_input>` XML delimiters via `genai_utils._wrap_user_input()` before LLM call; module-load `RuntimeError` guard validates template integrity at import time (`python -O` safe). Phase 3 (Issue #1007): `_safe_wrap` helper added to `genai_utils.py` and adopted by 8 additional `GenAIAnalyzer` callers (10 sites) for cross-codebase prompt-injection defense. (v1.0.0, Phase 1/Phase 2/Phase 3)

### Tracking Libraries (2) - NEW in v3.28.0

22. **agent_tracker.py** (see section 24)
23. **session_tracker.py** (see section 25)

### Installation Libraries (4) - NEW in v3.29.0

25. **file_discovery.py** - Comprehensive file discovery with exclusion patterns (Issue #80)
26. **copy_system.py** - Structure-preserving file copying with permission handling (Issue #80)
27. **installation_validator.py** - Coverage validation and missing file detection (Issue #80)
28. **install_orchestrator.py** - Coordinates complete installation workflows (Issue #80)

### Brownfield Retrofit Libraries (6)

31. **brownfield_retrofit.py** - Phase 0: Project analysis and tech stack detection
32. **codebase_analyzer.py** - Phase 1: Deep codebase analysis (multi-language)
33. **alignment_assessor.py** - Phase 2: Gap assessment and 12-Factor compliance
34. **migration_planner.py** - Phase 3: Migration plan with dependency tracking
35. **retrofit_executor.py** - Phase 4: Step-by-step execution with rollback
36. **retrofit_verifier.py** - Phase 5: Verification and readiness assessment

### MCP Security Libraries (2) - NEW in v3.37.0

39. **mcp_permission_validator.py** - REMOVED (never executed; see section 35)
40. **mcp_profile_manager.py** - Pre-configured security profiles for MCP (development, testing, production) (Issue #95)

### Script Utilities (2) - NEW in v3.42.0, ENHANCED in v3.44.0

42. **genai_install_wrapper.py** - CLI wrapper for setup-wizard Phase 0 GenAI-first installation with JSON output (Issue #109)
43. **migrate_hook_paths.py** - Migrate PreToolUse hook paths from hardcoded to portable ~/.claude/hooks/pre_tool_use.py (Issue #113)

## 70. qa_self_healer.py (16360 bytes, v1.0.0 - Issue #184)

**Purpose**: Orchestrate automatic test healing with fix iterations to resolve test failures without manual intervention.

**Problem**: When tests fail during development, engineers must manually analyze error messages, implement fixes, and re-run tests. This is repetitive and error-prone for simple issues (missing colons, typos, incorrect imports).

**Solution**: Self-healing QA orchestrator that automatically detects failures, analyzes errors, generates fixes, applies patches, and retries until all tests pass or max iterations/stuck detection reached.

**Location**: `plugins/autonomous-dev/lib/qa_self_healer.py`

**Key Features**:
- Iterative healing loop (max 10 iterations by default)
- Multi-failure handling (fix all failures in each iteration)
- Stuck detection (3 identical errors triggers circuit breaker)
- Environment variable controls (SELF_HEAL_ENABLED, SELF_HEAL_MAX_ITERATIONS)
- Audit logging for all healing attempts
- Atomic rollback on patch failure

### Classes

#### `SelfHealingResult`
Result object from healing operation with full history and outcome.

**Attributes**:
- `success: bool` - True if all tests pass after healing
- `iterations: int` - Number of healing iterations performed
- `attempts: List[HealingAttempt]` - Detailed history of each attempt
- `final_test_output: str` - Final pytest output
- `stuck_detected: bool` - True if stuck detector triggered
- `max_iterations_reached: bool` - True if hit iteration limit
- `error_message: str` - Error details if healing failed

#### `HealingAttempt`
Single healing attempt in the loop.

**Attributes**:
- `iteration: int` - Attempt number (1-indexed)
- `failures: List[FailureAnalysis]` - Errors found in test output
- `fixes_generated: int` - Number of fixes attempted
- `fixes_applied: int` - Number of fixes successfully applied
- `timestamp: str` - When attempt occurred

#### `QASelfHealer`
Main orchestrator for self-healing workflow.

**Constructor**:
```python
QASelfHealer(
    test_dir: Optional[Path] = None,
    max_iterations: int = 10,
    enabled: bool = True,
    stuck_threshold: int = 3
)
```

**Parameters**:
- `test_dir` - Test directory (default: current directory)
- `max_iterations` - Max healing iterations (default: 10, overridable via SELF_HEAL_MAX_ITERATIONS env var)
- `enabled` - Enable self-healing (default: True, overridable via SELF_HEAL_ENABLED env var)
- `stuck_threshold` - Stuck detection threshold (default: 3 consecutive identical errors)

### Methods

#### `heal_test_failures(test_command)`

Run self-healing loop to fix all test failures.

**Parameters**:
- `test_command: Optional[List[str]]` - Test command to execute (default: ["pytest"])

**Returns**: `SelfHealingResult` with outcome and full history

**Logic**:
```
Loop (max iterations):
  1. Run tests
  2. If all pass → return SUCCESS
  3. Parse failures from output
  4. Check stuck detector (3 identical errors → STOP)
  5. Generate fixes for all failures
  6. Apply fixes atomically
  7. Record attempt
  8. Repeat
```

### Functions

#### `heal_test_failures(test_command, max_iterations, enabled)`

Convenience function for one-shot healing.

**Parameters**:
- `test_command: Optional[List[str]]` - Test command (default: ["pytest"])
- `max_iterations: int` - Max iterations (default: 10)
- `enabled: bool` - Enable healing (default: True)

**Returns**: `SelfHealingResult`

**Usage**:
```python
from qa_self_healer import heal_test_failures

result = heal_test_failures(["pytest", "tests/"])
if result.success:
    print(f"All tests passing after {result.iterations} iterations!")
elif result.stuck_detected:
    print("Stuck - same error repeating, needs manual fix")
```

#### `run_tests_with_healing(test_command, max_iterations)`

High-level entry point for test execution with automatic healing.

**Parameters**:
- `test_command: Optional[List[str]]` - Test command
- `max_iterations: int` - Max healing iterations

**Returns**: `SelfHealingResult`

### Design Patterns

- **Iterative Healing**: Loop until success, stuck, or max iterations
- **Multi-failure Handling**: Process all failures in each iteration (faster convergence)
- **Circuit Breaker**: Stuck detector prevents infinite loops
- **Atomic Operations**: Patches applied atomically, rollback on failure
- **Audit Trail**: All attempts logged for debugging

### Integration Points

**test-master Agent**: Uses `heal_test_failures()` to automatically fix failing tests after TDD red phase

**Other Libraries**:
- `failure_analyzer.py` - Parse pytest output
- `code_patcher.py` - Apply atomic fixes
- `stuck_detector.py` - Detect infinite loops

### Security

- No arbitrary code execution (only applies pre-generated fixes)
- Path validation via `code_patcher.py` (CWE-22, CWE-59 prevention)
- Atomic writes prevent partial updates
- Backup creation for rollback

### Performance

- Iteration 1: 2-5 seconds (test run + analysis + fix)
- Subsequent iterations: 1-3 seconds each
- Typical convergence: 2-4 iterations for simple fixes
- Max iterations: 10 (configurable)
- Timeout: None (relies on underlying test runner)

### Test Coverage

- Successful healing (syntax errors, typos, missing imports)
- Stuck detection (circuit breaker)
- Max iterations reached
- Atomic rollback on patch failure
- Environment variable control

### Version History

- v1.0.0 (2026-01-02) - Initial release with iterative healing loop (Issue #184)

### Backward Compatibility

N/A (new library - Issue #184)

---

## 71. failure_analyzer.py (13606 bytes, v1.0.0 - Issue #184)

**Purpose**: Parse pytest output to extract structured failure information for automated fix generation.

**Problem**: Test failure messages contain mixed stdout/stderr with variable formats. Manual parsing is error-prone. Need structured data (error type, file, line, message) to generate fixes.

**Solution**: Parse pytest output with multi-error type detection and extract file path, line number, error type, and stack trace.

**Location**: `plugins/autonomous-dev/lib/failure_analyzer.py`

**Key Features**:
- Multi-error type detection (syntax, import, assertion, type, runtime)
- File path and line number extraction
- Stack trace extraction for debugging
- Test name extraction from pytest format
- Graceful handling of malformed/empty output

### Classes

#### `FailureAnalysis`
Structured representation of a single test failure.

**Attributes**:
- `test_name: str` - Test function/class name
- `file_path: str` - File containing the error
- `line_number: int` - Line number of error
- `error_type: str` - Classification: syntax, import, assertion, type, runtime
- `error_message: str` - Human-readable error message
- `stack_trace: str` - Full stack trace for debugging

#### `FailureAnalyzer`
Parser for pytest output.

**Constructor**:
```python
FailureAnalyzer()
```

No parameters required.

### Methods

#### `parse_pytest_output(output)`

Parse raw pytest output to extract all failures.

**Parameters**:
- `output: str` - Raw pytest stdout/stderr

**Returns**: `List[FailureAnalysis]` (empty list if no failures or malformed output)

**Error Types**:
- `syntax` - SyntaxError, IndentationError, invalid syntax
- `import` - ImportError, ModuleNotFoundError
- `assertion` - AssertionError, assertion failed
- `type` - TypeError, AttributeError, NameError
- `runtime` - ZeroDivisionError, KeyError, IndexError, ValueError, etc.

**Graceful Degradation**:
- Malformed output returns empty list (no crashes)
- Missing fields populated with defaults
- Graceful handling of variable pytest output formats

### Functions

#### `parse_pytest_output(output)`

Convenience function for one-shot parsing.

**Parameters**:
- `output: str` - Raw pytest output

**Returns**: `List[FailureAnalysis]`

**Usage**:
```python
from failure_analyzer import parse_pytest_output

output = subprocess.check_output(["pytest", "tests/"], text=True)
failures = parse_pytest_output(output)

for failure in failures:
    print(f"{failure.error_type}: {failure.file_path}:{failure.line_number}")
    print(f"  {failure.error_message}")
```

#### `extract_error_details(output)`

Extract detailed error information (alias for parse_pytest_output).

**Parameters**:
- `output: str` - Raw pytest output

**Returns**: `List[FailureAnalysis]`

### Design Patterns

- **Graceful Degradation**: Malformed output doesn't crash
- **Progressive Disclosure**: Only extract needed fields
- **Bounded Output**: No memory exhaustion on large outputs
- **Regex-based Parsing**: No code execution risk

### Integration Points

**qa_self_healer.py**: Uses to parse test failures for fix generation

**test-master Agent**: May use for detailed error analysis

**Other Libraries**:
- No dependencies on other libraries

### Security

- No arbitrary code execution
- Safe regex parsing (no ReDoS vulnerabilities)
- Bounded output (prevents memory exhaustion)
- Sanitized error messages (no injection risk)

### Performance

- Small output (<1KB): <10ms
- Large output (100KB+): <100ms
- Linear time complexity relative to output size
- Memory usage bounded by output size

### Test Coverage

- Multi-error type detection (syntax, import, assertion, type, runtime)
- File path and line number extraction
- Stack trace extraction
- Test name extraction
- Malformed output handling
- Edge cases: Empty output, no failures, large files

### Version History

- v1.0.0 (2026-01-02) - Initial release with multi-error type detection (Issue #184)

### Backward Compatibility

N/A (new library - Issue #184)

---

## 72. code_patcher.py (11241 bytes, v1.0.0 - Issue #184)

**Purpose**: Safely apply code fixes with atomic writes, backup creation, and rollback support.

**Problem**: Applying code patches requires careful handling to prevent corruption. Need atomic writes, backup creation, and rollback on failure.

**Solution**: Atomic file patching with backup directory, temporary file writes, and rollback support. Validates paths for security (CWE-22, CWE-59).

**Location**: `plugins/autonomous-dev/lib/code_patcher.py`

**Key Features**:
- Atomic write pattern (temp file -> rename)
- Automatic backup creation before patching
- Rollback support for failed patches
- File permissions preservation
- Security validation (CWE-22, CWE-59)

### Classes

#### `ProposedFix`
Proposed code fix with metadata.

**Attributes**:
- `file_path: str` - File to patch (relative or absolute)
- `original_code: str` - Original code snippet
- `fixed_code: str` - Replacement code
- `strategy: str` - Fix strategy (e.g., "add_colon", "fix_import")
- `confidence: float` - Confidence score (0.0-1.0)

#### `CodePatcher`
Main patcher for atomic file updates.

**Constructor**:
```python
CodePatcher(backup_dir: Optional[Path] = None)
```

**Parameters**:
- `backup_dir` - Directory for backups (default: system temp directory)

### Methods

#### `apply_patch(fix)`

Apply code fix with atomic write and backup.

**Parameters**:
- `fix: ProposedFix` - Fix details

**Returns**: `bool` - True if patch applied successfully

**Process**:
1. Validate patch path (CWE-22, CWE-59)
2. Create backup of original file
3. Apply fix via atomic write (temp + rename)
4. Verify patch applied
5. Return success status

**Error Handling**:
- Path traversal attempts rejected
- Symlink attacks prevented
- Atomic writes ensure no corruption
- Backup preserved on failure

#### `rollback_last_patch()`

Rollback the most recent patch from backup.

**Returns**: `bool` - True if rollback successful

#### `cleanup_backups()`

Remove all backups after successful healing.

**Returns**: `bool` - True if cleanup successful

### Functions

#### `validate_patch_path(file_path)`

Validate file path for security issues.

**Parameters**:
- `file_path: Path` - File path to validate

**Raises**: `ValueError` if path is invalid (path traversal, symlink, etc.)

**Prevents**:
- CWE-22 (path traversal via ..)
- CWE-59 (symlink attacks)
- Absolute paths outside project

#### `apply_patch(fix, backup_dir)`

Convenience function for one-shot patching.

**Parameters**:
- `fix: ProposedFix` - Fix details
- `backup_dir: Optional[Path]` - Backup directory

**Returns**: `bool` - True if patch applied

**Usage**:
```python
from code_patcher import apply_patch, ProposedFix

fix = ProposedFix(
    file_path="test.py",
    original_code="def foo()",
    fixed_code="def foo():",
    strategy="add_colon",
    confidence=0.95
)

if apply_patch(fix):
    print("Patch applied successfully")
else:
    print("Patch failed")
```

#### `create_backup(file_path, backup_dir)`

Create backup of file.

**Parameters**:
- `file_path: Path` - File to backup
- `backup_dir: Optional[Path]` - Backup directory

**Returns**: `Path` - Backup file path

#### `rollback_patch(file_path, backup_dir)`

Rollback file from backup.

**Parameters**:
- `file_path: Path` - File to restore
- `backup_dir: Optional[Path]` - Backup directory

**Returns**: `bool` - True if rollback successful

#### `cleanup_backups(backup_dir)`

Remove all backups.

**Parameters**:
- `backup_dir: Optional[Path]` - Backup directory to clean

**Returns**: `bool` - True if cleanup successful

### Design Patterns

- **Atomic Writes**: Temporary file + rename prevents partial updates
- **Backup First**: Create backup before any modifications
- **Rollback Support**: Quick recovery from failed patches
- **Path Validation**: Security-first approach

### Integration Points

**qa_self_healer.py**: Uses to apply atomic fixes to test files

**Other Libraries**:
- `security_utils.py` - May use for additional path validation

### Security

- CWE-22: Path traversal prevention (reject .., absolute paths)
- CWE-59: Symlink attack prevention (reject symlinks)
- Atomic writes prevent partial updates
- Backup directory isolation
- File permissions preservation

### Performance

- Backup creation: 1-10ms
- Atomic write: 2-20ms
- Rollback: 1-10ms
- Cleanup: 5-50ms
- Scales with file size (large files take longer)

### Test Coverage

- Successful patch application
- Atomic write verification
- Backup creation and rollback
- Path validation (traversal, symlinks)
- File permissions preservation
- Error handling and recovery

### Version History

- v1.0.0 (2026-01-02) - Initial release with atomic writes and backup/rollback (Issue #184)

### Backward Compatibility

N/A (new library - Issue #184)

---

## 73. stuck_detector.py (5453 bytes, v1.0.0 - Issue #184)

**Purpose**: Detect infinite healing loops from repeated identical errors to prevent wasted iterations.

**Problem**: Self-healing loop can get stuck if the same error repeats (e.g., fix doesn't address root cause). Need to detect this and stop to avoid infinite iterations.

**Solution**: Track error signatures and trigger circuit breaker when same error appears N consecutive times (default: 3).

**Location**: `plugins/autonomous-dev/lib/stuck_detector.py`

**Key Features**:
- Error signature computation (normalized for comparison)
- Consecutive error tracking
- Configurable stuck threshold (default: 3)
- Reset on successful test run
- Thread-safe operation

### Constants

- `DEFAULT_STUCK_THRESHOLD` - Default threshold for stuck detection (3)

### Classes

#### `StuckDetector`
Detector for infinite healing loops.

**Constructor**:
```python
StuckDetector(threshold: int = 3)
```

**Parameters**:
- `threshold: int` - Consecutive identical errors before stuck (default: 3)

### Methods

#### `record_error(error_signature)`

Record an error signature for stuck detection.

**Parameters**:
- `error_signature: str` - Normalized error signature (file + line + error type)

**Thread-safe**: Uses internal lock

#### `is_stuck()`

Check if stuck detector triggered.

**Returns**: `bool` - True if threshold reached (3+ consecutive identical errors)

#### `reset()`

Reset stuck detector after successful iteration.

**Parameters**: None

#### `compute_error_signature(failures)`

Compute normalized error signature from failures.

**Parameters**:
- `failures: List[FailureAnalysis]` - Parsed test failures

**Returns**: `str` - Normalized signature for comparison

### Functions

#### `is_stuck()`

Check global stuck status (singleton).

**Returns**: `bool` - True if stuck

#### `reset_stuck_detection()`

Reset global stuck detector (singleton).

**Parameters**: None

### Stuck Detection Logic

1. Compute error signature (file + line + error type)
2. Compare with previous errors
3. If same signature appears N times consecutively -> STUCK
4. Otherwise -> continue healing
5. On test success -> reset detector

### Design Patterns

- **Singleton Pattern**: Global stuck detector instance
- **Signature Normalization**: Ignore message text, focus on error location/type
- **Bounded Memory**: Only store recent error history
- **Thread-safe**: Uses locks for concurrent access

### Integration Points

**qa_self_healer.py**: Uses to check for stuck loops before continuing iterations

**Other Libraries**:
- Works with `failure_analyzer.py` for error signatures

### Security

- No code execution
- Bounded memory (only stores recent signatures)
- Thread-safe with locks
- No credential exposure

### Performance

- record_error(): <0.1ms
- is_stuck(): <0.1ms
- reset(): <0.1ms
- compute_error_signature(): <1ms
- Memory usage: O(n) where n = max_history

### Test Coverage

- Error signature computation
- Consecutive error tracking
- Circuit breaker threshold
- Reset on success
- Thread safety
- Edge cases: Empty signature, rapid errors

### Version History

- v1.0.0 (2026-01-02) - Initial release with circuit breaker threshold (Issue #184)

### Backward Compatibility

N/A (new library - Issue #184)

---

## Design Patterns

- **Progressive Enhancement**: String → path → whitelist validation for graceful error recovery
- **Non-blocking Enhancement**: Enhancements don't block core operations
- **Two-tier Design**: Core logic + CLI interface for reusability and testing
- **Security First**: All file operations validated via security_utils.py

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Main project documentation
- [MCP-SECURITY.md](MCP-SECURITY.md) - MCP security configuration and API reference
- [PERFORMANCE.md](PERFORMANCE.md) - Performance optimization tracking
- [GIT-AUTOMATION.md](GIT-AUTOMATION.md) - Git automation workflow
- [SECURITY.md](SECURITY.md) - Security hardening guide

---

# Library Reference

## 1. security_utils.py (628 lines, v3.4.3+)

**Purpose**: Centralized security validation and audit logging

### Functions

#### `validate_path(path, operation)`
- **Purpose**: 4-layer whitelist defense against path traversal attacks
- **Parameters**:
  - `path` (str|Path): Path to validate
  - `operation` (str): Operation type (e.g., "read", "write")
- **Returns**: `Path` object (validated and resolved)
- **Raises**: `SecurityError` if path violates security rules
- **Security Coverage**: CWE-22 (path traversal), CWE-59 (symlink resolution)
- **Validation Layers**:
  1. String checks (no "..", no absolute system paths)
  2. Symlink detection (blocks symlink attacks)
  3. Path resolution (resolves to canonical path)
  4. Whitelist validation (must be within allowed directories)

#### `validate_pytest_path(path)`
- **Purpose**: Special path validation for pytest execution
- **Parameters**: `path` (str|Path): Path to validate
- **Returns**: `Path` object (validated)
- **Features**: Auto-detects pytest environment, allows system temp while blocking system directories

#### `validate_input_length(input_str, max_length, field_name)`
- **Purpose**: Input length validation to prevent DoS attacks
- **Parameters**:
  - `input_str` (str): Input string to validate
  - `max_length` (int): Maximum allowed length
  - `field_name` (str): Field name for error messages
- **Raises**: `ValueError` if input exceeds max_length

#### `validate_agent_name(agent_name)`
- **Purpose**: Validate agent name format (alphanumeric, dash, underscore only)
- **Parameters**: `agent_name` (str): Agent name to validate
- **Raises**: `ValueError` if format is invalid

#### `validate_github_issue(issue_number)`
- **Purpose**: Validate GitHub issue number format
- **Parameters**: `issue_number` (int|str): Issue number to validate
- **Raises**: `ValueError` if format is invalid

#### `audit_log(event_type, details, level)`
- **Purpose**: Thread-safe JSON logging to security audit log
- **Parameters**:
  - `event_type` (str): Event type (e.g., "path_validation", "marketplace_sync")
  - `details` (dict): Event details
  - `level` (str): Log level ("INFO", "WARNING", "ERROR")
- **Features**: 10MB rotation, 5 backups, thread-safe

### Test Coverage
- 638 unit tests (98.3% coverage)

### Used By
- agent_tracker.py
- project_md_updater.py
- version_detector.py
- orphan_file_cleaner.py
- All security-critical operations

### Documentation
See `docs/SECURITY.md` for comprehensive security guide

---

## 2. project_md_updater.py (247 lines, v3.4.0+)

**Purpose**: Atomic PROJECT.md updates with security validation

### Functions

#### `update_goal_progress()` - Update goal progress atomically

**Signature**: `update_goal_progress(project_root, goal_title, progress_percent, notes)`

- **Purpose**: Update goal progress in PROJECT.md atomically
- **Parameters**:
  - `project_root` (str|Path): Project root directory
  - `goal_title` (str): Goal title to update
  - `progress_percent` (int): Progress percentage (0-100)
  - `notes` (str): Optional progress notes
- **Returns**: `bool` (True if update succeeded)
- **Features**: Atomic writes, merge conflict detection, backup before update

### Internal Methods

#### `_atomic_write(file_path, content)`
- **Purpose**: Write file atomically using temp file + rename pattern
- **Security**: Uses mkstemp() for temp file creation, atomic rename

#### `_validate_update(project_root, goal_title, progress_percent)`
- **Purpose**: Validate update parameters
- **Raises**: `ValueError` if parameters are invalid

#### `_backup_before_update(file_path)`
- **Purpose**: Create backup before modifying PROJECT.md
- **Returns**: `Path` to backup file

#### `_detect_merge_conflicts(file_path)`
- **Purpose**: Detect if PROJECT.md has merge conflicts
- **Returns**: `bool` (True if conflicts detected)
- **Features**: Prevents data loss if PROJECT.md changed during update

### Test Coverage
- 24 unit tests (95.8% coverage)

### Used By
- auto_update_project_progress.py hook (SubagentStop)

---

## 3. version_detector.py (531 lines, v3.7.1+)

**Purpose**: Semantic version detection and comparison

### Classes

#### `Version`
- **Purpose**: Semantic version object with comparison operators
- **Attributes**:
  - `major` (int): Major version
  - `minor` (int): Minor version
  - `patch` (int): Patch version
  - `prerelease` (str|None): Pre-release identifier
- **Methods**:
  - `__eq__`, `__lt__`, `__le__`, `__gt__`, `__ge__`: Comparison operators
  - `__str__`: String representation (e.g., "3.7.1" or "3.7.1-beta")

#### `VersionComparison`
- **Purpose**: Result dataclass for version comparison
- **Attributes**:
  - `marketplace_version` (Version): Marketplace plugin version
  - `project_version` (Version): Local project plugin version
  - `is_upgrade` (bool): True if marketplace version is newer
  - `is_downgrade` (bool): True if marketplace version is older
  - `is_same` (bool): True if versions match
  - `message` (str): Human-readable comparison message

### Functions

#### `VersionDetector.detect_version_mismatch(marketplace_path, project_root)`
- **Purpose**: Compare marketplace plugin version vs local project version
- **Parameters**:
  - `marketplace_path` (str|Path): Path to marketplace plugin directory
  - `project_root` (str|Path): Project root directory
- **Returns**: `VersionComparison` object
- **Features**: Handles pre-release versions, semantic version comparison

#### `detect_version_mismatch(marketplace_path, project_root)` (convenience)
- **Purpose**: High-level API for version detection
- **Returns**: `VersionComparison` object

### Security
- Path validation via security_utils
- Audit logging (CWE-22, CWE-59 protection)

### Error Handling
- Clear error messages with context and expected format

### Pre-release Support
- Correctly handles `MAJOR.MINOR.PATCH` and `MAJOR.MINOR.PATCH-PRERELEASE` patterns

### Test Coverage
- 20 unit tests (version parsing, comparison, edge cases)

### Used By
- sync_dispatcher.py for marketplace version detection

### Related
- GitHub Issue #50

---

## 4. orphan_file_cleaner.py (778 lines, v3.7.1+ → v3.29.1)

**Purpose**: Orphaned file detection and cleanup + duplicate library prevention

**New in v3.29.1 (Issue #81)**: Duplicate library detection and pre-install cleanup to prevent `.claude/lib/` import conflicts

### Classes

#### `OrphanFile`
- **Purpose**: Representation of an orphaned file
- **Attributes**:
  - `path` (Path): Full path to orphaned file
  - `category` (str): File category ("command", "hook", "agent")
  - `is_orphan` (bool): Whether file is confirmed orphan (always True)
  - `reason` (str): Human-readable reason why file is orphaned

#### `CleanupResult`
- **Purpose**: Result dataclass for cleanup operation
- **Attributes**:
  - `orphans_detected` (int): Number of orphans detected
  - `orphans_deleted` (int): Number of orphans deleted
  - `dry_run` (bool): Whether this was a dry-run (no deletions)
  - `errors` (int): Number of errors encountered
  - `orphans` (List[OrphanFile]): List of detected orphan files
  - `success` (bool): Whether cleanup succeeded
  - `error_message` (str): Optional error message for failed operations
  - `files_removed` (int): Alias for orphans_deleted (for pre-install cleanup compatibility)
- **Properties**:
  - `summary` (str): Auto-generated human-readable summary of cleanup result

### Functions

#### `detect_orphans()` - Detect orphaned files

**Signature**: `detect_orphans(project_root, plugin_name="autonomous-dev")`

- **Purpose**: Detect orphaned files in commands/hooks/agents directories
- **Parameters**:
  - `project_root` (str|Path): Project root directory
  - `plugin_name` (str): Plugin name (default: "autonomous-dev")
- **Returns**: `List[OrphanFile]`
- **Features**: Detects files not registered in plugin.json

#### `cleanup_orphans(project_root, dry_run, confirm, plugin_name)`
- **Purpose**: Clean up orphaned files with mode control
- **Parameters**:
  - `project_root` (str|Path): Project root directory
  - `dry_run` (bool): If True, report only (don't delete), default: True
  - `confirm` (bool): If True, ask user before each deletion, default: False
  - `plugin_name` (str): Plugin name (default: "autonomous-dev")
- **Returns**: `CleanupResult`
- **Modes**:
  - `dry_run=True`: Report orphans without deleting
  - `confirm=True`: Ask user to confirm each deletion
  - `dry_run=False, confirm=False`: Auto mode - delete all orphans without prompts

#### `OrphanFileCleaner.find_duplicate_libs()` - NEW in v3.29.1

**Signature**: `find_duplicate_libs() -> List[Path]`

- **Purpose**: Detect Python files in `.claude/lib/` directory (duplicate library location)
- **Details**:
  - Identifies duplicate libraries in legacy `.claude/lib/` location
  - These files conflict with canonical location: `plugins/autonomous-dev/lib/`
  - Prevents import conflicts (CWE-627) when installing/updating plugin
- **Returns**: List of Path objects for duplicate library files found
  - Excludes `__init__.py` and `__pycache__` directories
  - Includes files in nested subdirectories
  - Returns empty list if `.claude/lib/` doesn't exist
- **Security**: All paths validated via `security_utils.validate_path()`
- **Example**:
  ```python
  cleaner = OrphanFileCleaner(project_root)
  duplicates = cleaner.find_duplicate_libs()
  print(f"Found {len(duplicates)} duplicate libraries")
  ```

#### `OrphanFileCleaner.pre_install_cleanup()` - NEW in v3.29.1

**Signature**: `pre_install_cleanup() -> CleanupResult`

- **Purpose**: Remove `.claude/lib/` directory before installation to prevent duplicates
- **Details**:
  - Performs pre-installation cleanup by removing legacy `.claude/lib/` directory
  - Prevents import conflicts when installing or updating plugin
  - Idempotent: Safe to call even if `.claude/lib/` doesn't exist
- **Returns**: `CleanupResult` with:
  - `success` (bool): Whether cleanup succeeded
  - `files_removed` (int): Count of duplicate files removed
  - `error_message` (str): Error description if cleanup failed
- **Behavior**:
  - Returns success immediately if `.claude/lib/` doesn't exist (idempotent)
  - Handles symlinks safely: removes symlink itself, preserves target (CWE-59)
  - Logs all operations to audit trail with timestamp and file count
  - Gracefully handles permission errors with clear error messages
  - Validates all paths before removal (CWE-22 prevention)
- **Integration**: Called by:
  - `install_orchestrator.py` (fresh install and upgrade)
  - `plugin_updater.py` (plugin update workflow)
- **Example**:
  ```python
  cleaner = OrphanFileCleaner(project_root)
  result = cleaner.pre_install_cleanup()
  if result.success:
      print(f"Removed {result.files_removed} duplicate files")
  else:
      print(f"Error: {result.error_message}")
  ```

### Security
- Path validation via security_utils.validate_path()
  - Prevents path traversal attacks (CWE-22)
  - Blocks symlink-based attacks (CWE-59)
  - Rejects path traversal patterns (.., absolute system paths)
- Audit logging:
  - Global security audit log (security_utils.audit_log)
  - Project-specific audit log: `logs/orphan_cleanup_audit.log` (JSON format)
  - All file operations logged with timestamp, user, operation type

### Error Handling
- Graceful per-file failures (one orphan failure doesn't block others)
- Permission errors reported clearly without aborting cleanup
- Symlinks handled specially to prevent CWE-59 attacks

### Test Coverage
- 62 unit tests (v3.29.1 additions):
  - Detection: 6 tests (empty dir, missing dir, nested files, etc.)
  - Cleanup: 6 tests (idempotent, symlinks, readonly files, etc.)
  - Integration: 10+ tests (install_orchestrator, plugin_updater)
  - Edge cases: 8 tests (large directories, permission errors, etc.)
- Original 22 tests for orphan detection/cleanup maintained
- Total coverage: 62+ tests

### Used By
- sync_dispatcher.py for marketplace sync cleanup
- install_orchestrator.py for fresh install and upgrade (pre_install_cleanup)
- plugin_updater.py for plugin update workflow (pre_install_cleanup)
- installation_validator.py for validation warnings (find_duplicate_libs)

### Related
- GitHub Issue #50 (Fix Marketplace Update UX)
- GitHub Issue #81 (Prevent .claude/lib/ Duplicate Library Imports) - NEW

---

## 5. sync_dispatcher package (Issue #164 - Refactored from 2,074 LOC monolithic file into 4 focused modules)

**Purpose**: Intelligent sync orchestration with version detection and cleanup (Issue #97: Fixed sync directory silent failures)

**Package Structure**: Refactored from monolithic sync_dispatcher.py (2,074 LOC) into focused package with 4 modules (Issue #164):
- models.py (158 lines): Data structures (SyncResult, SyncDispatcherError, SyncError)
- modes.py (749 lines): Mode-specific dispatch functions (marketplace, env, plugin-dev, github)
- dispatcher.py (1,017 lines): Main SyncDispatcher class with orchestration logic and _sync_directory() method
- cli.py (262 lines): CLI interface and convenience functions (dispatch_sync, main)

**Backward Compatibility**: All existing imports continue working via re-export shim (sync_dispatcher.py)

**Import Patterns**:
- Old (still works): `from sync_dispatcher import SyncResult, SyncDispatcher, dispatch_sync`
- New (preferred): `from sync_dispatcher.models import SyncResult` or `from sync_dispatcher.dispatcher import SyncDispatcher`

### Classes

#### `SyncMode` (enum)
- `MARKETPLACE`: Sync from marketplace
- `ENV`: Sync development environment
- `PLUGIN_DEV`: Plugin development sync

#### `SyncResult`
- **Purpose**: Result dataclass for sync operation
- **Attributes**:
  - `success` (bool): Whether sync succeeded
  - `mode` (SyncMode): Which sync mode executed
  - `message` (str): Human-readable result
  - `details` (dict): Additional details (files updated, conflicts, etc.)
  - `version_comparison` (VersionComparison|None): Version comparison (marketplace mode only)
  - `orphan_cleanup` (CleanupResult|None): Cleanup result (marketplace mode only)
- **Properties**:
  - `summary` (str): Auto-generated comprehensive summary including version and cleanup info

### Functions

#### `SyncDispatcher._sync_directory(src, dst, pattern, description)` (v3.37.1+)
- **Purpose**: Sync directory with per-file operations (fixes Issue #97 shutil.copytree bug)
- **Parameters**:
  - `src` (Path): Source directory path
  - `dst` (Path): Destination directory path
  - `pattern` (str): File pattern to match (e.g., "*.md", "*.py", default "*")
  - `description` (str): Human-readable description for logging
- **Returns**: `int` - Number of files successfully copied
- **Raises**: `ValueError` if source doesn't exist or path validation fails
- **Features**:
  - Replaces buggy `shutil.copytree(dirs_exist_ok=True)` which silently fails to copy new files
  - Uses `FileDiscovery` to enumerate all matching files
  - Per-file copy operations with `copy2()` to preserve metadata
  - Preserves directory structure via `relative_to()` and mkdir parents
  - Security: Validates paths to prevent CWE-22 (path traversal) and CWE-59 (symlink attacks)
  - Continues on individual file errors (doesn't fail entire sync)
  - Audit logging per operation for debugging

#### `SyncDispatcher.sync(mode, project_root, cleanup_orphans)`
- **Purpose**: Main entry point for sync operations
- **Parameters**:
  - `mode` (SyncMode): Sync mode
  - `project_root` (str|Path): Project root directory
  - `cleanup_orphans` (bool): Whether to clean up orphaned files (marketplace mode only)
- **Returns**: `SyncResult`

#### `sync_marketplace(project_root, cleanup_orphans)` (convenience)
- **Purpose**: High-level API for marketplace sync with enhancements
- **Parameters**:
  - `project_root` (str|Path): Project root directory
  - `cleanup_orphans` (bool): Whether to clean up orphaned files
- **Returns**: `SyncResult`
- **Features**:
  - Version detection: Runs detect_version_mismatch() for marketplace vs. project comparison
  - Orphan cleanup: Conditional (cleanup_orphans parameter), with dry-run support
  - Error handling: Non-blocking - enhancements don't block core sync
  - Messaging: Shows upgrade/downgrade/up-to-date status and cleanup results

#### main() (CLI wrapper - NEW Issue #127, v3.7.1+)
- **Purpose**: Command-line interface wrapper for sync_dispatcher package
- **Returns**: int - Exit code (0 success, 1 failure, 2 invalid args)
- **CLI Arguments**:
  - --github: Fetch latest files from GitHub (default if no flags)
  - --env: Sync environment (delegates to sync-validator agent)
  - --marketplace: Copy files from installed plugin
  - --plugin-dev: Sync plugin development files
  - --all: Execute all sync modes in sequence
- **Mutually Exclusive**: Only one mode flag allowed per invocation
- **Features**:
  - Auto-detection of sync mode based on CLI flags
  - Sensible default: GITHUB mode when no flags specified
  - Argument validation via argparse (returns exit code 2 for invalid args)
  - Helpful error messages and usage examples
  - Graceful handling of KeyboardInterrupt (user cancellation)
  - Exit code 0 for --help flag (standard argparse behavior)
- **Implementation**: Embedded in cli.py module
- **Used By**: /sync command (delegates to main() via subprocess)

### Security
- All paths validated via security_utils
- Audit logging to security audit (marketplace_sync events)

### Test Coverage
- Comprehensive testing of all sync modes
- Backward compatibility tests verify re-export shim

### Used By
- /sync command
- sync_marketplace() high-level API
- plugin_updater.py (import utilities)

### Related
- GitHub Issues #47, #50, #51, #164 (refactoring)
- Issue #97 (Fixed sync directory silent failures)
- Issue #127 (CLI wrapper added)

---

## 6. validate_marketplace_version.py (371 lines, v3.7.2+)

**Purpose**: CLI script for /health-check marketplace integration

### Functions

#### `validate_marketplace_version(project_root, verbose, json_output)`
- **Purpose**: Main entry point for version validation
- **Parameters**:
  - `project_root` (str|Path): Project root directory
  - `verbose` (bool): Verbose output
  - `json_output` (bool): Machine-readable JSON output
- **Returns**: `VersionComparison` object

#### `_parse_version(version_str)`
- **Purpose**: Parse semantic version string
- **Parameters**: `version_str` (str): Version string (e.g., "3.7.1")
- **Returns**: `Version` object

#### `_format_output(version_comparison, json_output)`
- **Purpose**: Format output for CLI display
- **Parameters**:
  - `version_comparison` (VersionComparison): Version comparison result
  - `json_output` (bool): Whether to output JSON
- **Returns**: `str` (formatted output)

### CLI Arguments
- `--project-root`: Project root path (required)
- `--verbose`: Verbose output
- `--json`: Machine-readable JSON output format

### Output Formats
- **Human-readable**: "Project v3.7.0 vs Marketplace v3.7.1 - Update available"
- **JSON**: Structured result with version comparison data

### Security
- Path validation via security_utils.validate_path()
- Audit logging to security audit

### Error Handling
- Non-blocking errors (marketplace not found is not fatal)
- Exit code 1 on errors

### Integration
- Called by health_check.py `_validate_marketplace_version()` method

### Test Coverage
- 7 unit tests (version comparison, output formatting, error cases)

### Used By
- health-check command (CLI invocation)
- /health-check validation

### Related
- GitHub Issue #50 Phase 1 (marketplace version validation integration into /health-check)

---

## 7. plugin_updater.py (868 lines, v3.8.2+)

**Purpose**: Interactive plugin update with version detection, backup, rollback, and security hardening

### Classes

#### `UpdateError` (base exception)
- Base class for all update-related errors

#### `BackupError` (UpdateError)
- Raised when backup operations fail

#### `VerificationError` (UpdateError)
- Raised when verification fails

#### `UpdateResult`
- **Purpose**: Result dataclass for update operation
- **Attributes**:
  - `success` (bool): Whether update succeeded
  - `updated` (bool): Whether plugin was actually updated
  - `message` (str): Human-readable result
  - `old_version` (str|None): Previous plugin version
  - `new_version` (str|None): New plugin version
  - `backup_path` (str|None): Path to backup (if created)
  - `rollback_performed` (bool): Whether rollback was performed
  - `hooks_activated` (bool): Whether hooks were activated
  - `hooks_added` (List[str]): List of hooks added
  - `details` (dict): Additional details

### Key Methods

#### `PluginUpdater.check_for_updates(project_root, plugin_name)`
- **Purpose**: Check for available updates without performing update
- **Parameters**:
  - `project_root` (str|Path): Project root directory
  - `plugin_name` (str): Plugin name (default: "autonomous-dev")
- **Returns**: `VersionComparison` object

#### `PluginUpdater.update(project_root, plugin_name, interactive, auto_backup)`
- **Purpose**: Perform interactive or non-interactive update
- **Parameters**:
  - `project_root` (str|Path): Project root directory
  - `plugin_name` (str): Plugin name
  - `interactive` (bool): Whether to prompt for confirmation
  - `auto_backup` (bool): Whether to create backup before update
- **Returns**: `UpdateResult`
- **Features**:
  - Interactive confirmation prompts (customizable)
  - Automatic backup before update (timestamped, in /tmp, 0o700 permissions)
  - Automatic rollback on any failure (sync, verification, unexpected errors)
  - Verification: checks version matches expected, validates critical files exist
  - Cleanup: removes backup after successful update
  - Hook activation: Auto-activates hooks from new version (first install only)

#### `_create_backup(project_root, plugin_name)`
- **Purpose**: Create timestamped backup
- **Security**: 0o700 permissions, symlink detection
- **Returns**: `Path` to backup directory

#### `_rollback(backup_path, project_root, plugin_name)`
- **Purpose**: Restore from backup on failure
- **Security**: Path validation, symlink blocking

#### `_cleanup_backup(backup_path)`
- **Purpose**: Remove backup after successful update

#### `_verify_update(project_root, plugin_name, expected_version)`
- **Purpose**: Verify update succeeded
- **Features**: Version validation, critical file validation

#### `_activate_hooks(project_root, plugin_name)`
- **Purpose**: Activate hooks from new plugin version
- **Integration**: Calls hook_activator.py


#### _sync_lib_files (NEW - Issue #123)
- **Purpose**: Sync lib files from plugin to ~/.claude/lib/ (non-blocking)
- **Workflow**:
  1. Read installation_manifest.json to verify lib directory should be synced
  2. Create ~/.claude/lib/ if doesn't exist
  3. Copy each top-level .py file from plugin/lib/ (excluding `__init__.py`)
  4. Discover package directories (subdirectories containing `__init__.py`) and copy all .py files recursively — enables packages like `sync_dispatcher/` to deploy correctly
  5. Validate all paths for security (CWE-22, CWE-59)
  6. Audit log all operations
  7. Handle errors gracefully (non-blocking)
- **Returns**: Number of lib files successfully synced (0 on complete failure)
- **Security**:
  - Target path validation: Ensures ~/.claude/lib is within user home
  - Source path validation: Prevents CWE-22 (path traversal)
  - Symlink rejection: Prevents CWE-59 (symlink attacks)
  - Manifest validation: Ensures lib files explicitly listed
  - Audit logging for all operations
- **Non-Blocking**: Lib sync failures don't block plugin update
- **Features**:
  - Graceful degradation: Missing manifest or source files handled cleanly
  - Returns lib_files_synced count in UpdateResult.details
  - Skips __init__.py (not needed in global lib)

#### _validate_and_fix_permissions (NEW - Issue #123)
- **Purpose**: Validate and fix settings.local.json permissions (non-blocking)
- **Workflow**:
  1. Check if settings.local.json exists (skip if not)
  2. Load and validate permissions
  3. If issues found:
     - Backup existing file with timestamp
     - Generate template with correct patterns
     - Fix using fix_permission_patterns()
     - Write fixed settings atomically
  4. Return result with action taken
- **Returns**: PermissionFixResult with action, issues found, and fixes applied
- **Actions**:
  - validated: No issues found, settings already correct
  - fixed: Issues found and fixed
  - regenerated: Corrupted JSON regenerated from template
  - skipped: No settings.local.json found
  - failed: Validation or fix failed
- **Backup Strategy**:
  - Timestamped filename: settings.local.json.backup-YYYYMMDD-HHMMSS-NNNNNN
  - Location: .claude/backups/
  - Permissions: Inherits from original file
- **Non-Blocking**: Permission fix failures don't block plugin operations
- **Security**:
  - Atomic writes: Uses tempfile plus rename
  - Path validation: CWE-22 and CWE-59 prevention
  - Backup creation: Before any modifications
  - Audit logging: All operations logged with context

#### PermissionFixResult (NEW - Issue #123)
- **Purpose**: Dataclass tracking permission validation/fix results
- **Attributes**:
  - success (bool): Whether validation/fix succeeded
  - action (str): Action taken (validated, fixed, regenerated, skipped, failed)
  - issues_found (int): Count of detected permission issues
  - fixes_applied (List[str]): List of fixes that were applied
  - backup_path (Path or None): Path to backup file (if created)
  - message (str): Human-readable result message
### Security (GitHub Issue #52 - 5 CWE vulnerabilities addressed)
- **CWE-22 (Path Traversal)**: Marketplace path validation, rollback path validation, user home directory check
- **CWE-78 (Command Injection)**: Plugin name length + format validation (alphanumeric, dash, underscore only)
- **CWE-59 (Symlink Following/TOCTOU)**: Backup path re-validation after creation, symlink detection
- **CWE-117 (Log Injection)**: Audit log input sanitization, audit log signature standardized
- **CWE-732 (Permissions)**: Backup directory permissions 0o700 (user-only)
- All validations use security_utils module for consistency
- Audit logging for all security operations to security_audit.log

### Test Coverage
- 53 unit tests (39 existing + 14 new security tests, 46 passing, 7 design issues to fix)

### Used By
- update_plugin.py CLI script
- /update-plugin command

### Related
- GitHub Issue #50 Phase 2 (interactive plugin update)
- GitHub Issue #52 (security hardening)

---

## 8. update_plugin.py (380 lines, v3.8.0+)

**Purpose**: CLI script for interactive plugin updates

### Functions

#### `parse_args()`
- **Purpose**: Parse command-line arguments
- **Returns**: `argparse.Namespace`

#### `main()`
- **Purpose**: Main entry point
- **Returns**: Exit code (0=success, 1=error, 2=no update needed)

#### `_format_version_output(version_comparison)`
- **Purpose**: Format version comparison for display
- **Returns**: `str` (formatted output)

#### `_prompt_for_confirmation(message)`
- **Purpose**: Interactive confirmation prompt
- **Returns**: `bool` (True if user confirmed)

### CLI Arguments
- `--check-only`: Check for updates without performing update (dry-run)
- `--yes`, `-y`: Skip confirmation prompts (non-interactive mode)
- `--auto-backup`: Create backup before update (default: enabled)
- `--no-backup`: Skip backup creation (advanced users only)
- `--verbose`, `-v`: Enable verbose logging
- `--json`: Output JSON for scripting (machine-readable)
- `--project-root`: Path to project root (default: current directory)
- `--plugin-name`: Name of plugin to update (default: autonomous-dev)

### Exit Codes
- `0`: Success (update performed or already up-to-date)
- `1`: Error (update failed)
- `2`: No update needed (when --check-only)

### Output Modes
- **Human-readable**: Rich ASCII tables with status indicators and progress
- **JSON**: Machine-readable structured output for scripting
- **Verbose**: Detailed logging of all operations (backups, verifications, rollbacks)

### Integration
- Invokes PluginUpdater from plugin_updater.py

### Security
- Path validation via security_utils
- Audit logging

### Error Handling
- Clear error messages with context and guidance

### Test Coverage
- Comprehensive unit tests (argument parsing, output formatting, interactive flow)

### Used By
- /update-plugin command (bash invocation)

### Related
- GitHub Issue #50 Phase 2 (interactive plugin update command)

---

## 9. hook_activator.py (938 lines, v3.8.1+, format migration v3.44.0+)

**Purpose**: Automatic hook activation during plugin updates with Claude Code 2.0 format migration (Issue #112)

### Classes

#### `ActivationError` (base exception)
- Base class for activation-related errors

#### `SettingsValidationError` (ActivationError)
- Raised when settings validation fails

#### `ActivationResult`
- **Purpose**: Result dataclass for activation operation
- **Attributes**:
  - `activated` (bool): Whether hooks were activated
  - `first_install` (bool): Whether this was first install
  - `message` (str): Human-readable result
  - `hooks_added` (List[str]): List of hooks added
  - `settings_path` (str): Path to settings.json
  - `details` (dict): Additional details

### Key Methods

#### `HookActivator.activate_hooks(project_root, plugin_name)`
- **Purpose**: Activate hooks from new plugin version with automatic format migration
- **Parameters**:
  - `project_root` (str|Path): Project root directory
  - `plugin_name` (str): Plugin name
- **Returns**: `ActivationResult`
- **Features**:
  - First install detection: Checks for existing settings.json file
  - Automatic hook activation: Activates hooks from plugin.json on first install
  - Smart merging: Preserves existing customizations when updating
  - Format migration: Detects legacy format and auto-migrates to Claude Code 2.0 (Issue #112)
  - Atomic writes: Prevents corruption via tempfile + rename pattern
  - Validation: Structure validation (required fields, hook format)
  - Error recovery: Graceful handling of malformed JSON, permissions issues

#### `detect_first_install(project_root)`
- **Purpose**: Check if settings.json exists (first install vs update detection)
- **Returns**: `bool`

#### `_read_settings(settings_path)`
- **Purpose**: Read and parse existing settings.json
- **Returns**: `dict`
- **Error Handling**: Graceful handling of malformed JSON

#### `_merge_hooks(existing_hooks, new_hooks)`
- **Purpose**: Merge new hooks with existing settings
- **Features**: Preserves existing customizations

#### `_validate_settings(settings)`
- **Purpose**: Validate settings structure and content
- **Raises**: `SettingsValidationError` if validation fails

#### `_ensure_claude_dir(claude_dir)`
- **Purpose**: Create .claude directory if missing
- **Security**: Correct permissions

#### `_atomic_write(settings_path, settings)`
- **Purpose**: Write settings.json atomically
- **Pattern**: Tempfile + rename

#### `validate_hook_format(settings_data)` (NEW - Issue #112)
- **Purpose**: Detect legacy vs Claude Code 2.0 hook format
- **Parameters**:
  - `settings_data` (Dict): Settings dictionary to validate
- **Returns**: `Dict` with `is_legacy` (bool) and `reason` (str)
- **Detection Criteria**:
  - Legacy indicators: Missing `timeout` fields, flat command strings, missing nested `hooks` arrays
  - Modern CC2: All hooks have `timeout`, nested dicts with matchers containing `hooks` arrays
- **Raises**: `SettingsValidationError` if structure is malformed
- **Example**:
  ```python
  result = validate_hook_format(settings)
  if result['is_legacy']:
      print(f"Legacy format: {result['reason']}")
  ```

#### `migrate_hook_format_cc2(settings_data)` (NEW - Issue #112)
- **Purpose**: Auto-migrate legacy hook format to Claude Code 2.0 format
- **Parameters**:
  - `settings_data` (Dict): Settings to migrate (can be legacy or modern)
- **Returns**: `Dict` with migrated settings (deep copy, original unchanged)
- **Transformations**:
  - Adds `timeout: 5` to all hooks missing it
  - Converts flat string commands to nested dict structure
  - Wraps commands in nested `hooks` array if missing
  - Adds `matcher: '*'` if missing
  - Preserves user customizations (custom timeouts, matchers)
- **Idempotent**: Running multiple times produces same result
- **Example**:
  ```python
  legacy = {"hooks": {"PrePush": ["auto_test.py"]}}
  modern = migrate_hook_format_cc2(legacy)
  # Result: modern['hooks']['PrePush'][0]['hooks'][0]['timeout'] == 5
  ```

#### migrate_hooks_to_object_format(settings_path) (NEW - Issue #135)
- **Purpose**: Auto-migrate hooks from array format to object format during /sync --marketplace (Claude Code v2.0.69+ compatibility)
- **Parameters**:
  - settings_path (Path): Path to settings.json (typically user home/.claude/settings.json)
- **Returns**: Dict with keys:
  - migrated (bool): True if migration was performed
  - backup_path (Optional[Path]): Path to timestamped backup if migrated
  - format (str): Detected format - array (needs migration), object (already modern), invalid, or missing
  - error (Optional[str]): Error message if migration failed
- **Format Detection**:
  - **Array format** (pre-v2.0.69): Array of hook objects with event and command fields
  - **Object format** (v2.0.69+): Object keyed by event name with nested matcher and hooks arrays
- **Migration Steps**:
  1. Check if file exists (returns format: missing if not)
  2. Read and parse JSON (graceful error handling for corrupted files)
  3. Detect format (array vs object)
  4. If array format: Create timestamped backup, transform array to object structure, write atomically (tempfile + rename), return success with backup path
  5. If migration fails: Rollback from backup (no partial migrations)
- **Security** (CWE-22, CWE-362, CWE-404 prevention):
  - Path validation (settings must be in user home/.claude/)
  - Atomic writes prevent corruption
  - Backup creation before modifications
  - No secrets exposed in logs
  - Full rollback on error
- **Integration**: Called automatically during /sync --marketplace after settings merge
- **Non-blocking**: Migration failures do not stop sync (graceful degradation)

### Security
- Path validation via security_utils
- Audit logging to logs/security_audit.log
- Secure permissions (0o600)
- Backup creation before format migration

### Error Handling
- Non-blocking (activation failures do not block plugin update)
- Graceful degradation if migration fails (existing settings preserved)

### Format Migration (Issue #112 and Issue #135)
- **Issue #112**: Automatic migration during activate_hooks() if legacy format detected
- **Issue #135**: Automatic migration during /sync --marketplace for user settings
- **Transparent**: Backup created before any changes
- **Idempotent**: Safe to run multiple times
- **Backwards Compatible**: Legacy settings continue to work unchanged

### Test Coverage
- 41 unit tests (first install, updates, merge logic, error cases, malformed JSON)
- 28 migration tests (format detection, legacy-to-CC2 conversion, backup creation)
- 12 tests for Issue #135 migration (array-to-object format, backup creation, rollback)

### Used By
- plugin_updater.py for /update-plugin command
- activate_hooks() for automatic format migration during install/update
- sync_dispatcher.py for /sync --marketplace command (Issue #135)

### Related
- GitHub Issue #112 (Hook Format Migration to Claude Code 2.0)
- GitHub Issue #135 (Auto-migrate settings.json hooks format during /sync)

---

## 11. auto_implement_git_integration.py (2,220 lines as of Issue #1555 — verify against the filesystem rather than trusting this count, it drifts; v3.9.0+)

**Purpose**: Automatic git operations orchestration

### Key Functions

#### `execute_step8_git_operations(workflow_id, request, branch, push, create_pr, base_branch)`
- **Purpose**: Main entry point orchestrating complete workflow (commit, push, PR creation)
- **Parameters**:
  - `workflow_id` (str): Workflow identifier
  - `request` (str): Feature request description
  - `branch` (str): Branch name
  - `push` (bool): Whether to push to remote
  - `create_pr` (bool): Whether to create PR
  - `base_branch` (str): Base branch for PR
- **Returns**: `ExecutionResult`

#### `check_consent_via_env()`
- **Purpose**: Parse consent from environment variables
- **Returns**: `dict` with `AUTO_GIT_ENABLED`, `AUTO_GIT_PUSH`, `AUTO_GIT_PR` values

#### `invoke_commit_message_agent(workflow_id, request, staged_files=None)`
- **Purpose**: Produce the commit message for a workflow. Despite the name, no subagent is dispatched — generates in-process via `generate_commit_message()` (Issue #1555; the `commit-message-generator` agent this used to call exists only under `agents/archived/` and was never a working call path, since `AgentInvoker.invoke()` returns a Task-tool dispatch descriptor, not an executed result). The function name and `{'success','output','error'}` return contract are preserved for backward compatibility — callers and ~15 test sites depend on them.
- **Returns**: `dict` with `success`, `output` (commit message), `error`

#### `invoke_pr_description_agent(workflow_id, branch)`
- **Purpose**: Produce the PR description for a workflow. Same in-process substitution as `invoke_commit_message_agent()` — no subagent dispatch (Issue #1555).
- **Returns**: `dict` with `success`, `output` (PR description), `error`

#### `generate_commit_message(request, changed_files=None, manifest=None)`
- **Purpose**: New in Issue #1555. Deterministically builds a conventional-commit message from the feature request, changed files, and an optional workflow manifest (manifest is enrichment context, not a prerequisite)
- **Returns**: `str` (commit message)

#### `generate_pr_description(request, branch, *, commit_subjects=None, changed_files=None)`
- **Purpose**: New in Issue #1555. Deterministically builds a PR description (summary, test plan, related issues) from the feature request, branch name, recent commit subjects, and changed files — note this does NOT take a `manifest` argument (unlike `generate_commit_message()`); `invoke_pr_description_agent()` reads the manifest itself and folds `manifest['request']` in as the `request` argument before calling this function
- **Returns**: `str` (PR description)

#### `infer_commit_type(request)`, `infer_scope(changed_files)`, `build_commit_subject(request, commit_type, scope=None)`
- **Purpose**: New in Issue #1555. Helpers backing `generate_commit_message()` — classify the conventional-commit `type`, infer a `scope` from changed file paths, and format the `type(scope): description` subject line
- **Returns**: `str` each

#### `create_commit_with_agent_message(workflow_id, request, branch, push=False, issue_number=None, stage_all=True)`
- **Purpose**: Generate the commit message (in-process), validate it, append `Closes #N` if `issue_number` is provided, and execute the commit via `git_operations.auto_commit_and_push()`. A clean working tree (nothing to commit) is now a hard failure (`success=False` with an actionable error) rather than the pre-Issue #1555 silent `success=True, commit_sha=''` no-op.
- **`stage_all` (Issue #1564)**: forwarded verbatim to `auto_commit_and_push()`. `True` (default, and what every caller including `/implement` STEP 12.7 uses) stages the whole working tree — untracked files included — before committing. `False` commits the caller's existing index verbatim and adds nothing to it, so unstaged and untracked files stay out of the commit.
  - **Precondition for `False`**: the caller must have staged its files first. With an empty index no commit is created and this returns `success=False` with the "No commit created" error plus manual fallback instructions. `/implement` does not yet satisfy this — it has no staging step, and STEP 1 hard-blocks on a non-empty index — so STEP 12.7 keeps the default. See [GIT-AUTOMATION.md § Staging scope](GIT-AUTOMATION.md#staging-scope-issue-1564).
- **Returns**: `dict` with `success`, `commit_sha`, `pushed`, `files_committed` (int; number of files in the resulting commit, `0` on every failure path — Issue #1564), `commit_message_generated`, `agent_succeeded`, `git_succeeded`, `error`, `manual_instructions`

#### `push_and_create_pr(branch, pr_description, base_branch)`
- **Purpose**: Push to remote and optionally create PR via gh CLI
- **Returns**: `dict` with PR URL

### Private Helpers (Issue #1555)

#### `_load_workflow_manifest(workflow_id)`
- **Purpose**: Loads the workflow manifest via `ArtifactManager.artifact_exists()` + `read_artifact(workflow_id, 'manifest', validate=False)` if present. Returns `None` when no manifest was written — the manifest is optional context, not a required precondition, so a workflow that never wrote v2.0 artifacts is still committable. (Fixes the prior `TypeError` from calling `ArtifactManager.read_artifact()` with only 1 of its 2 required positional args.)
- **Returns**: `Optional[Dict[str, Any]]`

#### `_collect_changed_files(limit=200)`
- **Purpose**: Collects the list of changed files from git status for use as generation context
- **Returns**: `List[str]`

#### `_recent_commit_subjects(limit=10)`
- **Purpose**: Reads recent commit subject lines to inform type/scope inference
- **Returns**: `List[str]`

### Validation Functions

#### `validate_agent_output(agent_output)`
- **Purpose**: Verify the generated commit message / PR description is usable
- **Checks**: success key, message length, format

#### `validate_git_state()`
- **Purpose**: Check repository state
- **Checks**: not detached, no merge conflicts, clean working directory

#### `validate_branch_name(branch_name)`
- **Purpose**: Ensure branch name follows conventions

#### `validate_commit_message(message)`
- **Purpose**: Validate commit message format (conventional commits)

### Prerequisite Checks

#### `check_git_credentials()`, `check_git_available()`, `check_gh_available()`
- **Purpose**: Validate prerequisites before operations

### Fallback Functions

#### `build_manual_git_instructions(commit_message)`, `build_fallback_pr_command(pr_description, branch, base_branch)`
- **Purpose**: Generate fallback instructions if automation fails

### ExecutionResult

**Attributes**:
- `success` (bool): Whether operation succeeded
- `commit_sha` (str|None): Commit SHA (if created)
- `pushed` (bool): Whether pushed to remote
- `pr_created` (bool): Whether PR was created
- `pr_url` (str|None): PR URL (if created)
- `error` (str|None): Error message (if failed)
- `details` (dict): Additional details
- `manual_instructions` (str|None): Fallback instructions

### Features
- Consent-based automation via environment variables (defaults: all disabled for safety)
- In-process, deterministic commit and PR message generation — no subagent dispatch (Issue #1555)
- Graceful degradation with manual fallback instructions (non-blocking)
- Prerequisite validation before operations
- Subprocess safety (command injection prevention)
- Comprehensive error handling with actionable messages

### Security
- Uses security_utils.validate_path() for all paths
- Audit logs to security_audit.log
- Safe subprocess calls

### Integration
- Invoked by auto_git_workflow.py hook (SubagentStop lifecycle) after quality-validator completes

### Error Handling
- Non-blocking - git operation failures don't affect feature completion (graceful degradation)

### Used By
- auto_git_workflow.py hook
- /implement Step 8 (automatic git operations)

### Related
- GitHub Issue #58 (automatic git operations integration)

---

## 12. github_issue_closer.py (583 lines, v3.22.0+, Issue #91)

**Purpose**: Auto-close GitHub issues after successful `/implement` workflow

### Functions

#### `extract_issue_number(command_args)`
- **Purpose**: Extract GitHub issue number from feature request
- **Parameters**: `command_args` (str): Feature request text
- **Returns**: `int | None` - Issue number (1-999999) or None if not found
- **Features**: Flexible pattern matching
  - Patterns: `"issue #8"`, `"#8"`, `"Issue 8"` (case-insensitive)
  - Extracts first occurrence if multiple mentions
  - Validates issue number is positive integer (1-999999)
- **Security**: CWE-20 (input validation), range checking
- **Examples**:
  ```python
  extract_issue_number("implement issue #8")  # Returns: 8
  extract_issue_number("Add feature for #42")  # Returns: 42
  extract_issue_number("Issue 91 implementation")  # Returns: 91
  ```

#### `prompt_user_consent(issue_number)`
- **Purpose**: Interactive consent prompt before closing issue
- **Parameters**: `issue_number` (int): GitHub issue number
- **Returns**: `bool` - True if user consents, False if declines
- **Features**:
  - Displays issue title (via `gh issue view`)
  - Prompt: `"Close issue #8 (issue title)? [yes/no]:`
  - Accepts: "yes", "y" (True), "no", "n" (False)
  - Ctrl+C propagates KeyboardInterrupt (cancels workflow)
- **Error Handling**: Network errors fall back to generic prompt
- **Non-blocking**: Graceful degradation if gh CLI unavailable

#### `validate_issue_state(issue_number)`
- **Purpose**: Verify issue exists and is open via gh CLI
- **Parameters**: `issue_number` (int): GitHub issue number
- **Raises**: `IssueNotFoundError` if issue doesn't exist or is closed
- **Features**:
  - Calls `gh issue view <number>`
  - Checks issue state (open/closed)
  - Validates user has permission to close
- **Security**: CWE-20 (validates issue number)
- **Idempotent**: Already closed issues skip gracefully

#### `generate_close_summary(issue_number, metadata)`
- **Purpose**: Generate markdown summary for issue close comment
- **Parameters**:
  - `issue_number` (int): GitHub issue number
  - `metadata` (dict): Workflow metadata
    - `pr_url` (str): Pull request URL
    - `commit_hash` (str): Commit hash
    - `files_changed` (list): Changed file names
    - `agents_passed` (list): Agent names (researcher, planner, etc.)
- **Returns**: `str` - Markdown summary
- **Features**: Professional formatting with workflow metadata
- **Security**: CWE-117 (sanitizes newlines/control chars from file names)

#### `close_github_issue(issue_number, summary)`
- **Purpose**: Close GitHub issue via gh CLI with summary
- **Parameters**:
  - `issue_number` (int): GitHub issue number
  - `summary` (str): Markdown summary for close comment
- **Returns**: `dict` - Result with success/failure info
- **Security**:
  - CWE-20: Validates issue number (1-999999)
  - CWE-78: Subprocess list args (shell=False)
  - CWE-117: Sanitizes summary text
  - Audit logs all gh CLI operations
- **Error Handling**: Returns error dict (non-blocking)

### Exceptions

#### `GitHubAPIError`
- Base exception for GitHub API errors
- Contains: error message, original exception, traceback

#### `IssueNotFoundError`
- Raised when issue doesn't exist or is closed
- Subclass of GitHubAPIError

#### `IssueAlreadyClosedError`
- Raised when issue is already closed (can be ignored - idempotent)
- Subclass of GitHubAPIError

### Integration

- Invoked by auto_git_workflow.py hook (SubagentStop) after git push
- STEP 8 of /implement workflow: Auto-close GitHub issue
- Non-blocking feature (feature success independent of issue close)

### Security Features

- **CWE-20** (Input Validation): Issue number range checking (1-999999)
- **CWE-78** (Command Injection): Subprocess list args (shell=False)
- **CWE-117** (Log Injection): Sanitizes newlines/control chars
- **Audit Logging**: All gh CLI operations logged to security_audit.log

### Error Handling

All errors gracefully degrade:
- Issue not found: Skip with warning (feature still successful)
- Issue already closed: Skip gracefully (idempotent)
- gh CLI unavailable: Skip with manual instructions (non-blocking)
- Network error: Skip with retry instructions (feature still successful)
- User declines consent: Skip (user control)

### Used By
- auto_git_workflow.py hook
- /implement Step 8 (auto-close GitHub issue)

### Related
- GitHub Issue #91 (Auto-close GitHub issues after /implement)
- github_issue_fetcher.py (Issue fetching via gh CLI)

---

## 21-26. Brownfield Retrofit Libraries (v3.11.0+)

**Purpose**: 5-phase brownfield project retrofit system for existing project adoption

### 21. brownfield_retrofit.py (470 lines) - Phase 0 Analysis

#### Classes
- `BrownfieldProject`: Project descriptor
- `BrownfieldAnalysis`: Analysis result
- `RetrofitPhase`: Phase enum
- `BrownfieldRetrofitter`: Main coordinator

#### Key Functions
- `analyze_brownfield_project(project_root)`: Main entry point for Phase 0 analysis
- `detect_project_root()`: Auto-detect project root from current directory
- `validate_project_structure()`: Verify valid project directory
- `_detect_tech_stack()`: Identify language, framework, package manager
- `_check_existing_structure()`: Check for PROJECT.md, CLAUDE.md, .claude directory
- `build_retrofit_plan()`: Generate high-level retrofit plan

#### Features
- Tech stack auto-detection (Python, JavaScript, Go, Java, Rust, etc.)
- Existing structure analysis (identifies missing or incomplete files)
- Project root validation (verifies directory structure)
- Plan generation with all 5 phases outlined

#### Used By
- align_project_retrofit.py script
- /align-project-retrofit command PHASE 0

### 22. codebase_analyzer.py (870 lines) - Phase 1 Deep Analysis

#### Key Functions
- `analyze_codebase(project_root, tech_stack_hint)`: Comprehensive codebase analysis
- `_scan_directory_structure()`: Recursively analyze directory organization
- `_detect_language_and_framework()`: Language and framework detection
- `_analyze_dependencies()`: Parse requirements.txt, package.json, go.mod, Cargo.toml, etc.
- `_find_test_files()`: Locate and categorize test files
- `_detect_code_organization()`: Analyze module organization and naming conventions
- `_scan_documentation()`: Find README, docs, docstrings coverage
- `_identify_configuration_files()`: Locate config files (.env, .yaml, .json, etc.)

#### Features
- Multi-language support (Python, JavaScript, Go, Java, Rust, C++, etc.)
- Framework detection (Django, FastAPI, Express, Spring, etc.)
- Dependency analysis (dev vs production, versions)
- Test file detection and categorization (unit, integration, e2e)
- Code organization assessment (modular, monolithic, microservices)
- Documentation coverage analysis
- Configuration file inventory

### 23. alignment_assessor.py (666 lines) - Phase 2 Gap Assessment

#### Key Functions
- `assess_alignment(codebase_analysis, project_root)`: Assessment of alignment gaps
- `_calculate_compliance_score()`: Calculate 12-Factor App compliance (0-100 scale)
- `_check_project_structure()`: Verify PROJECT.md, CLAUDE.md presence
- `_check_documentation_quality()`: Assess README, API docs, architecture docs
- `_check_test_coverage()`: Estimate test coverage from test file locations
- `_detect_alignment_gaps()`: Identify missing autonomous-dev standards
- `_prioritize_gaps()`: Sort gaps by criticality and effort
- `_generate_project_md_draft()`: Create initial PROJECT.md structure

#### Features
- 12-Factor App compliance assessment (codebase, dependencies, config, etc.)
- Alignment gap detection (missing files, incomplete structure)
- Gap prioritization (critical, high, medium, low)
- PROJECT.md draft generation (ready to customize)
- Readiness assessment (ready, needs_work, not_ready)
- Estimated retrofit effort (XS, S, M, L, XL)

### 24. migration_planner.py (578 lines) - Phase 3 Plan Generation

#### Key Functions
- `generate_migration_plan(alignment_assessment, project_root, tech_stack)`: Generate migration plan
- `_break_down_gaps_into_steps()`: Convert gaps into actionable steps
- `_estimate_effort()`: Estimate effort for each step (XS-XL scale)
- `_assess_impact()`: Assess impact level (LOW, MEDIUM, HIGH)
- `_detect_step_dependencies()`: Identify prerequisite steps
- `_create_critical_path()`: Order steps by dependencies
- `_generate_verification_criteria()`: Define success criteria for each step
- `_estimate_total_effort()`: Sum effort for complete plan

#### Features
- Gap-to-step conversion with clear instructions
- Multi-factor effort estimation (complexity, scope, skill level)
- Dependency tracking (prerequisites, blocking relationships)
- Critical path analysis (minimum viable retrofit path)
- Verification criteria (how to confirm step success)
- Step grouping by phase (setup, structure, tests, docs, integration)
- Rollback considerations for each step

### 25. retrofit_executor.py (725 lines) - Phase 4 Execution

#### Key Functions
- `execute_migration(migration_plan, mode, project_root)`: Execute migration plan
- `_create_backup()`: Create timestamped backup (0o700 permissions, symlink detection)
- `_execute_step()`: Execute single step (create files, update configs, etc.)
- `_apply_template()`: Apply .claude template to project
- `_create_project_md()`: Create PROJECT.md with customization
- `_create_claude_md()`: Create CLAUDE.md tailored to project
- `_setup_test_framework()`: Configure test framework
- `_setup_git_hooks()`: Install project hooks
- `_rollback_all_changes()`: Restore from backup on failure
- `_validate_step_result()`: Verify step succeeded

#### Features
- Execution mode support: DRY_RUN (show only), STEP_BY_STEP (confirm each), AUTO (all)
- Automatic backup before changes (timestamped, 0o700 permissions)
- Rollback on any failure (atomic: all succeed or all rollback)
- Step-by-step confirmation prompts (customizable)
- Template application (PROJECT.md, CLAUDE.md, .claude directory)
- Test framework setup (auto-detect and configure)
- Hook installation and activation
- Detailed progress reporting

#### Security
- Path validation via security_utils
- Audit logging
- Symlink detection
- 0o700 permissions
- CWE-22/59/732 hardening

### 26. retrofit_verifier.py (689 lines) - Phase 5 Verification

#### Key Functions
- `verify_retrofit_complete(execution_result, project_root, original_analysis)`: Verify retrofit
- `_verify_files_created()`: Verify all required files exist and are valid
- `_verify_file_structure()`: Check .claude directory structure and permissions
- `_verify_configuration()`: Validate PROJECT.md and CLAUDE.md content
- `_verify_test_setup()`: Confirm test framework is operational
- `_verify_hooks_installed()`: Check hook activation status
- `_verify_auto_implement_readiness()`: Verify /implement compatibility
- `_run_smoke_tests()`: Execute basic validation tests
- `_assess_final_readiness()`: Determine readiness for /implement

#### Features
- File existence and integrity verification
- Configuration validation (PROJECT.md structure, CLAUDE.md alignment)
- Test framework operational check
- Hook installation verification
- /implement compatibility check
- Smoke test execution (optional)
- Readiness assessment (ready, needs_minor_fixes, needs_major_fixes)
- Remediation recommendations for failures

### All Brownfield Libraries Share
- Security: Path validation via security_utils, audit logging to security_audit.log
- Integration: Called by /align-project-retrofit command (respective phases)
- Related: GitHub Issue #59 (brownfield project retrofit)



---

## 12. abstract_state_manager.py (428 lines, NEW v1.0.0, Issue #220)

**Purpose**: Abstract Base Class (ABC) for standardized state management across all state managers.

**Problem**: Multiple state managers (batch_state_manager, session_tracker state management) had duplicate implementations of:
- Path validation and security checks (CWE-22 path traversal, CWE-59 symlinks)
- Atomic file writes with temp file + rename
- File locking for thread safety
- Audit logging for security events

**Solution**: StateManager ABC defines the contract for state management with concrete helper methods for security and atomicity.

**Note (Issue #221)**: BatchStateManager now inherits from StateManager[BatchState] to implement standardized state management interface while maintaining backward compatibility.

### Abstract Methods (must be implemented by subclasses)

#### `load_state() -> T`
- **Purpose**: Load state from persistent storage
- **Returns**: State object of type T
- **Raises**: StateError if load fails

#### `save_state(state: T) -> None`
- **Purpose**: Save state to persistent storage
- **Parameters**: `state` - State object to save
- **Raises**: StateError if save fails

#### `cleanup_state() -> None`
- **Purpose**: Clean up state (remove files, etc.)
- **Raises**: StateError if cleanup fails

### Concrete Helper Methods

#### `exists() -> bool`
- **Purpose**: Check if state file exists
- **Returns**: True if state file exists, False otherwise

#### `__repr__() -> str`
- **Purpose**: Return developer-friendly string representation
- **Returns**: String in format `ClassName(state_file=/path)` if state_file exists, otherwise `ClassName()`
- **Example**: `BatchStateManager(state_file=/tmp/batch_state.json)`

#### `_validate_state_path(path: Path) -> Path`
- **Purpose**: Validate state file path for security
- **Security**:
  - CWE-22 (Path Traversal): Prevents `../` sequences
  - CWE-59 (Symlink Following): Detects and rejects symlinks
- **Parameters**: `path` - Path to validate
- **Returns**: Resolved, validated path
- **Raises**: ValueError if path is invalid

#### `_atomic_write(path: Path, content: str, mode: int = 0o600) -> None`
- **Purpose**: Write file atomically with permissions
- **Security**:
  - CWE-367 (Race Condition): Temp file + atomic rename
  - CWE-732 (File Permissions): Sets file to read-only (0o600)
- **Parameters**:
  - `path` - File to write
  - `content` - Content to write
  - `mode` - File permissions (default: 0o600)
- **Raises**: IOError if write fails

#### `_get_file_lock(path: Path) -> threading.RLock`
- **Purpose**: Get reentrant lock for thread-safe file access
- **Parameters**: `path` - File path
- **Returns**: Reentrant lock for the file
- **Thread Safety**: Multiple threads can acquire the same lock

#### `_audit_operation(operation: str, status: str, details: Dict[str, Any]) -> None`
- **Purpose**: Log security-relevant operations
- **Parameters**:
  - `operation` - Operation type (e.g., "state_save")
  - `status` - Result status ("success", "failure", "warning")
  - `details` - Context details for audit log

### Usage Pattern

```python
from abc import ABC, TypeVar
from pathlib import Path
from abstract_state_manager import StateManager

T = TypeVar('T')  # Generic state type

class MyState:
    """Your state data class."""
    def to_dict(self) -> dict:
        ...

class MyStateManager(StateManager[MyState]):
    """Custom state manager inheriting from StateManager ABC."""

    def __init__(self, state_file: Path = None):
        self.state_file = state_file or Path(".my_state.json")
        # Validate path using inherited helper
        self.state_file = self._validate_state_path(self.state_file)

    def load_state(self) -> MyState:
        """Load state from file."""
        # Use inherited helpers as needed
        if not self.exists():
            raise StateError("State file not found")
        # ... load logic ...
        return MyState(...)

    def save_state(self, state: MyState) -> None:
        """Save state to file using atomic write."""
        content = json.dumps(state.to_dict())
        # Use inherited _atomic_write for security
        self._atomic_write(self.state_file, content)
        # Log the operation
        self._audit_operation("state_save", "success", {...})

    def cleanup_state(self) -> None:
        """Clean up state file."""
        if self.exists():
            self.state_file.unlink()
```

### Security Features

1. **CWE-22 (Path Traversal Prevention)**:
   - Validates paths don't contain `../` sequences
   - Resolves symlinks and detects traversal

2. **CWE-59 (Symlink Following Prevention)**:
   - Detects and rejects symlinks
   - Prevents TOCTOU (Time-of-check-time-of-use) races

3. **CWE-367 (Atomic Write)**:
   - Writes to temp file first
   - Atomically renames to final location
   - Prevents partial/corrupted state files

4. **CWE-732 (File Permissions)**:
   - Sets files to 0o600 (user read/write only)
   - Prevents unauthorized access

### Design Notes

- **Generic type**: StateManager[T] supports any state data class
- **Delegation pattern**: Subclasses implement abstract methods, use helpers for security
- **Backward compatibility**: Existing managers can inherit without refactoring
- **Phase-based migration**: Issue #220 (ABC foundation), Issue #221 (BatchStateManager), further phases for other managers

### Related

- Issue #220: Create StateManager ABC
- Issue #221: Migrate BatchStateManager to inherit from StateManager ABC
- GitHub: `plugins/autonomous-dev/lib/abstract_state_manager.py`

---

## 13. batch_state_manager.py (692 lines, v3.23.0+, enhanced v3.24.0, Issue #218: v3.46.0)

**Purpose**: State persistence for /implement --batch command with automatic context management via Claude Code

**Note (Issue #218 - v3.46.0)**: Deprecated context clearing functions removed:
- `should_clear_context()` - Removed (Claude Code v2.0+ manages context automatically with 200K budget)
- `pause_batch_for_clear()` - Removed (no longer needed without manual clearing)
- `get_clear_notification_message()` - Removed (no longer needed without manual clearing)
- `@deprecated` decorator - Removed (no longer needed)
- `CONTEXT_THRESHOLD` constant - Removed (Claude Code handles context automatically)

### Data Classes

#### `BatchState`
Batch processing state with persistent storage.

**Attributes**:
- `batch_id` (str): Unique batch identifier (format: "batch-YYYYMMDD-HHMMSS")
- `features_file` (str): Path to features file (empty for --issues batches)
- `total_features` (int): Total number of features in batch
- `features` (List[str]): List of feature descriptions
- `current_index` (int): Index of current feature being processed
- `completed_features` (List[int]): List of completed feature indices
- `failed_features` (List[Dict]): List of failed feature records
- `context_token_estimate` (int): Estimated context token count
- `auto_clear_count` (int): Number of auto-clear events
- `auto_clear_events` (List[Dict]): List of auto-clear event records
- `created_at` (str): ISO 8601 timestamp of batch creation
- `updated_at` (str): ISO 8601 timestamp of last update
- `status` (str): Batch status ("in_progress", "completed", "failed")
- `issue_numbers` (Optional[List[int]]): GitHub issue numbers for --issues flag (v3.24.0)
- `source_type` (str): Source type ("file" or "issues") (v3.24.0)
- `feature_modes` (Dict[int, str]): Maps feature index to detected pipeline mode ("full", "fix", "light") (v1.0.0, Issue #600)
- `state_file` (str): Path to state file

### Functions

#### `create_batch_state(features, state_file, features_file="", issue_numbers=None, source_type="file")`
- **Purpose**: Create new batch state with atomic write
- **Parameters**:
  - `features` (List[str]): List of feature descriptions
  - `state_file` (Path): Path to state file
  - `features_file` (str): Original features file path (optional)
  - `issue_numbers` (Optional[List[int]]): GitHub issue numbers (v3.24.0)
  - `source_type` (str): "file" or "issues" (v3.24.0)
- **Returns**: BatchState object
- **Security**: CWE-22 (path validation), CWE-732 (file permissions 0o600)

**Example**:
```python
from batch_state_manager import create_batch_state
from path_utils import get_batch_state_file

# File-based batch
state = create_batch_state(
    features=["Add login", "Add logout"],
    state_file=get_batch_state_file(),
    features_file="features.txt"
)

# GitHub issues batch (v3.24.0)
state = create_batch_state(
    features=["Issue #72: Add logging", "Issue #73: Fix bug"],
    state_file=get_batch_state_file(),
    issue_numbers=[72, 73],
    source_type="issues"
)
```

#### `save_batch_state(state)`
- **Purpose**: Save batch state with atomic write
- **Parameters**: `state` (BatchState): State to save
- **Returns**: None
- **Security**: Atomic write (temp file + rename), file permissions 0o600

#### `load_batch_state(state_file)`
- **Purpose**: Load batch state from file
- **Parameters**: `state_file` (Path): Path to state file
- **Returns**: BatchState object
- **Raises**: `StateError` (BatchStateError is now an alias, Issue #225) if file not found or corrupted
- **Backward Compatibility**: Old state files load with defaults (issue_numbers=None, source_type="file")

#### `update_batch_progress(state, feature_index, status="completed", error=None)`
- **Purpose**: Update batch progress after feature completion
- **Parameters**:
  - `state` (BatchState): Current state
  - `feature_index` (int): Index of completed feature
  - `status` (str): "completed" or "failed"
  - `error` (Optional[str]): Error message if failed
- **Returns**: Updated BatchState object

#### `record_auto_clear_event(state, tokens_before)`
- **Purpose**: Record auto-clear event in state
- **Parameters**:
  - `state` (BatchState): Current state
  - `tokens_before` (int): Token count before clearing
- **Returns**: Updated BatchState object

#### `should_auto_clear(state, checkpoint_callback=None)` **[DEPRECATED]**
- **Status**: DEPRECATED (Issue #277) - Not used in production
- **Purpose**: Check if context should be auto-cleared (legacy function)
- **Parameters**:
  - `state` (BatchState): Current state
  - `checkpoint_callback` (callable, optional): Callback to invoke before clearing (Issue #276)
- **Returns**: bool (True if context token estimate exceeds 185K threshold)
- **Deprecation Note**: This function is not used in production. Claude Code handles auto-compact automatically. The batch system now relies on:
  - Checkpoint after every feature (Issue #276)
  - Claude's automatic compaction (whenever it decides)
  - SessionStart hook auto-resume (Issue #277)
- **Kept For**: Backward compatibility with existing tests only

#### `get_next_pending_feature(state)`
- **Purpose**: Get next feature to process
- **Parameters**: `state` (BatchState): Current state
- **Returns**: Optional[Tuple[int, str]] (index, feature description) or None if complete

#### `cleanup_batch_state(state_file)`
- **Purpose**: Delete state file after successful batch completion
- **Parameters**: `state_file` (Path): Path to state file
- **Returns**: None

#### `mark_feature_skipped(state_file, feature_index, reason, category="quality_gate")` (NEW v3.48.0, Issue #256)
- **Purpose**: Mark a feature as permanently skipped (excluded from batch processing and retries)
- **Parameters**:
  - `state_file` (Path): Path to batch state file
  - `feature_index` (int): Index of feature to skip
  - `reason` (str): Reason for skipping (user-visible message)
  - `category` (str): Skip category - "quality_gate" (default), "manual", or "dependency"
- **Returns**: None
- **Raises**: `BatchStateError` if feature_index invalid, `ValueError` if feature_index out of range
- **Thread-safe**: Uses file locking consistent with mark_feature_status()
- **Use Cases**:
  - Quality gate failures: Skip feature after exhausting max retries
  - Security audit failures: Skip feature that failed security checks
  - Manual exclusions: Skip features explicitly excluded by user
  - Dependency issues: Skip features with unsolvable dependency chains
- **Example**:
```python
from batch_state_manager import mark_feature_skipped
from path_utils import get_batch_state_file

# Skip feature due to quality gate failure
mark_feature_skipped(
    get_batch_state_file(),
    feature_index=2,
    reason="Failed security audit - CWE-79 vulnerability detected",
    category="quality_gate"
)

# Skip feature due to manual request
mark_feature_skipped(
    get_batch_state_file(),
    feature_index=5,
    reason="User requested skip - deferring to next batch",
    category="manual"
)
```

### Security Features

1. **CWE-22 (Path Traversal Prevention)**: All paths validated via security_utils.validate_path()
2. **CWE-59 (Symlink Resolution)**: Symlink detection before file operations
3. **CWE-117 (Log Injection Prevention)**: Sanitize all log messages
4. **CWE-732 (File Permissions)**: State files created with 0o600 permissions
5. **Thread Safety**: Reentrant file locks for concurrent access protection
6. **Atomic Writes**: Temp file + rename pattern prevents corrupted state

### Integration

- **Command**: `/implement --batch` (file-based and --issues flag)
- **State File**: `.claude/batch_state.json` (persistent across crashes)
- **Related**: GitHub Issues #76 (state management), #77 (--issues flag)

### Enhanced Fields (v3.24.0)

```python
@dataclass
class BatchState:
    # ... existing fields ...
    issue_numbers: Optional[List[int]] = None  # NEW: GitHub issue numbers
    source_type: str = "file"  # NEW: "file" or "issues"
```

**Backward Compatibility**: Old state files (v3.23.0) load with default values:
- `issue_numbers = None`
- `source_type = "file"`

### Object-Oriented Interface (NEW Issue #221)

#### `BatchStateManager` class (inherits from StateManager[BatchState])

Object-oriented wrapper for batch state functions that inherits from StateManager ABC.

**Constructors**:
- `__init__(state_file: Optional[Path] = None)` - Initialize with optional custom state file path

**Methods** (implementing StateManager ABC):
- `load_state() -> BatchState` - Load batch state from file
- `save_state(state: BatchState) -> None` - Save batch state to file (uses inherited _atomic_write())
- `cleanup_state() -> None` - Clean up state file

**Methods** (batch-specific operations):
- `create_batch_state(features, batch_id=None, issue_numbers=None) -> BatchState` - Create new batch state
- `create_batch(features, features_file=None, batch_id=None, issue_numbers=None) -> BatchState` - Alias for create_batch_state
- `load_batch_state() -> BatchState` - Load batch state (delegates to load_state)
- `save_batch_state(state) -> None` - Save batch state (delegates to save_state)
- `update_batch_progress(feature_index, status, tokens_consumed=0) -> None` - Update batch progress
- `record_auto_clear_event(feature_index, tokens_before) -> None` - Record auto-clear event
- `should_auto_clear(checkpoint_callback=None) -> bool` - **[DEPRECATED]** Check if auto-clear threshold exceeded (not used in production)
- `get_next_pending_feature() -> Optional[str]` - Get next unprocessed feature
- `cleanup_batch_state() -> None` - Cleanup batch (delegates to cleanup_state)

**Example**:
```python
from batch_state_manager import BatchStateManager

# Create manager
manager = BatchStateManager()

# Create new batch
state = manager.create_batch_state(
    features=["Add login", "Add logout"],
    issue_numbers=[72, 73],
)

# Save state
manager.save_batch_state(state)

# Load state
loaded_state = manager.load_batch_state()

# Update progress
manager.update_batch_progress(0, "completed", tokens_consumed=50000)

# Get next feature to process
next_feature = manager.get_next_pending_feature()

# Note: should_auto_clear() is deprecated (Issue #277)
# Claude handles auto-compact automatically - no manual checking needed

# Cleanup when done
manager.cleanup_batch_state()
```

**Inheritance Pattern**:
BatchStateManager now inherits from StateManager[BatchState] ABC (Issue #221), implementing abstract methods via delegation:
- `load_state()` delegates to `load_batch_state()`
- `save_state()` delegates to `save_batch_state()`
- `cleanup_state()` delegates to `cleanup_batch_state()`

This maintains full backward compatibility while providing standardized state management interface with built-in security helpers from StateManager ABC.

---

## 14. github_issue_fetcher.py (462 lines, v3.24.0+)

**Purpose**: Fetch GitHub issue titles via gh CLI for /implement --batch --issues flag

### Functions

#### `validate_issue_numbers(issue_numbers)`
- **Purpose**: Validate issue numbers before subprocess calls
- **Parameters**: `issue_numbers` (List[int]): List of issue numbers to validate
- **Returns**: None (raises on validation failure)
- **Raises**: `ValueError` if validation fails
- **Security**: CWE-20 (Input Validation)
- **Validations**:
  1. All numbers are positive integers
  2. No duplicates
  3. Maximum 100 issues per batch (prevent resource exhaustion)

**Example**:
```python
from github_issue_fetcher import validate_issue_numbers

# Valid
validate_issue_numbers([72, 73, 74])  # OK

# Invalid
validate_issue_numbers([-5])  # ValueError: negative number
validate_issue_numbers([72, 72])  # ValueError: duplicates
validate_issue_numbers(range(150))  # ValueError: too many
```

#### `fetch_issue_title(issue_number, timeout=10)`
- **Purpose**: Fetch single issue title via gh CLI
- **Parameters**:
  - `issue_number` (int): GitHub issue number
  - `timeout` (int): Subprocess timeout in seconds (default: 10)
- **Returns**: str (issue title)
- **Raises**: 
  - `IssueNotFoundError` if issue doesn't exist
  - `GitHubAPIError` for other gh CLI errors
- **Security**: CWE-78 (Command Injection Prevention)
- **Implementation**: subprocess.run with list args, shell=False

**Example**:
```python
from github_issue_fetcher import fetch_issue_title

title = fetch_issue_title(72)
# Returns: "Add logging feature"
```

#### `fetch_issue_titles(issue_numbers, skip_missing=True)`
- **Purpose**: Batch fetch multiple issue titles
- **Parameters**:
  - `issue_numbers` (List[int]): List of issue numbers
  - `skip_missing` (bool): If True, skip missing issues; if False, raise error (default: True)
- **Returns**: Dict[int, str] (mapping of issue number to title)
- **Raises**: `GitHubAPIError` if skip_missing=False and issue not found
- **Graceful Degradation**: Skips missing issues by default, continues with available issues

**Example**:
```python
from github_issue_fetcher import fetch_issue_titles

titles = fetch_issue_titles([72, 73, 999])
# Returns: {72: "Add logging", 73: "Fix bug"}
# (999 skipped because it doesn't exist)
```

#### `format_feature_description(issue_number, title)`
- **Purpose**: Format issue as feature description for /implement --batch
- **Parameters**:
  - `issue_number` (int): GitHub issue number
  - `title` (str): Issue title from GitHub
- **Returns**: str (formatted feature description)

**Example**:
```python
from github_issue_fetcher import format_feature_description

feature = format_feature_description(72, "Add logging feature")
# Returns: "Issue #72: Add logging feature"
```

#### `fetch_issue_details(issue_number)` (v1.0.0, Issue #600)
- **Purpose**: Fetch issue title, body, and labels via gh CLI for per-issue mode detection
- **Parameters**: `issue_number` (int): GitHub issue number
- **Returns**: `Optional[Dict]` with "title", "body", "labels" keys if found; `None` if not found. Labels are list of dicts with "name" key (GitHub API format).
- **Raises**:
  - `FileNotFoundError` if gh CLI is not installed
  - `TimeoutExpired` if gh CLI hangs (>10 seconds)
  - `OSError` for network or system errors
- **Security**: CWE-78 (same command injection prevention as `fetch_issue_title`)

**Example**:
```python
from github_issue_fetcher import fetch_issue_details

details = fetch_issue_details(72)
# Returns: {"title": "Fix auth bug", "body": "Steps to reproduce...", "labels": [{"name": "bug"}]}
```

#### `fetch_issues_details(issue_numbers)` (v1.0.0, Issue #600)
- **Purpose**: Batch fetch issue details (title, body, labels) for multiple issues
- **Parameters**: `issue_numbers` (List[int]): List of GitHub issue numbers
- **Returns**: `Dict[int, Dict]` mapping issue number to details dict. Only includes successfully fetched issues.
- **Raises**:
  - `ValueError` if ALL issues fail to fetch
  - `FileNotFoundError` if gh CLI is not installed
  - `TimeoutExpired` if gh CLI hangs

**Example**:
```python
from github_issue_fetcher import fetch_issues_details

all_details = fetch_issues_details([72, 73, 74])
# Returns: {72: {"title": "...", "body": "...", "labels": [...]}, ...}
```

### Security Features

1. **CWE-20 (Input Validation)**:
   - Positive integers only
   - Maximum 100 issues per batch
   - No duplicates

2. **CWE-78 (Command Injection Prevention)**:
   - subprocess.run with list args (not string)
   - shell=False
   - No user input in command string

3. **CWE-117 (Log Injection Prevention)**:
   - Sanitize newlines and control characters in log messages
   - Truncate titles to 200 characters

4. **Audit Logging**:
   - All gh CLI operations logged to security_audit.log
   - Includes: issue numbers, operation type, success/failure

### Integration

- **Command**: `/implement --batch --issues 72 73 74`
- **State Manager**: Enhanced batch_state_manager.py with issue_numbers and source_type fields
- **Requirements**: gh CLI v2.0+, authenticated (gh auth login)
- **Related**: GitHub Issue #77 (Add --issues flag to /implement --batch)

### Usage Workflow

```python
from github_issue_fetcher import (
    validate_issue_numbers,
    fetch_issue_titles,
    format_feature_description,
)
from batch_state_manager import create_batch_state

# 1. Parse issue numbers from command args
issue_numbers = [72, 73, 74]

# 2. Validate
validate_issue_numbers(issue_numbers)

# 3. Fetch titles
issue_titles = fetch_issue_titles(issue_numbers)
# Returns: {72: "Add logging", 73: "Fix bug", 74: "Update docs"}

# 4. Format as features
features = [
    format_feature_description(num, title)
    for num, title in issue_titles.items()
]
# Returns: [
#   "Issue #72: Add logging",
#   "Issue #73: Fix bug",
#   "Issue #74: Update docs"
# ]

# 5. Create batch state
from path_utils import get_batch_state_file

state = create_batch_state(
    features=features,
    state_file=get_batch_state_file(),
    issue_numbers=issue_numbers,
    source_type="issues"
)
```

### Error Handling

```python
from github_issue_fetcher import (
    fetch_issue_titles,
    GitHubAPIError,
    IssueNotFoundError,
)

try:
    titles = fetch_issue_titles([72, 73, 74])
except IssueNotFoundError as e:
    # Issue doesn't exist (only raised if skip_missing=False)
    print(f"Issue not found: {e}")
except GitHubAPIError as e:
    # Other GitHub API errors (gh CLI not found, not authenticated, etc.)
    print(f"GitHub API error: {e}")
```

### Related Skills

- See `api-integration-patterns` skill for the error taxonomy, retry and
  rate-limit conventions this module follows when calling the GitHub API.
  `github_issue_closer.py` (section 12) follows the same conventions.

---

## 15. path_utils.py (350+ lines, v3.28.0+ / v3.41.0+ / v3.45.0+)

**Purpose**: Dynamic PROJECT_ROOT detection, path resolution, policy file location, and worktree batch state isolation for tracking infrastructure and tool configuration

**Issues**: GitHub #79 (hardcoded paths), GitHub #226 (worktree isolation)

### Key Features

- **Dynamic PROJECT_ROOT Detection**: Searches upward from current directory for `.git/` or `.claude/` markers
- **Worktree Batch State Isolation** (v3.45.0): Automatically isolates batch state per git worktree for concurrent batch processing
- **Caching**: Module-level cache prevents repeated filesystem searches
- **Flexible Creation**: Creates directories (docs/sessions, .claude) as needed with safe permissions (0o755)
- **Backward Compatible**: Existing usage patterns still work, uses get_project_root() internally
- **Security Validation**: Rejects symlinks and invalid JSON in policy files (CWE-59)

### Public API

#### `find_project_root(marker_files=None, start_path=None)`
- **Purpose**: Search upward for project root directory
- **Parameters**:
  - `marker_files` (list): Files/directories to search for. Defaults to `[".git", ".claude"]` (priority order)
  - `start_path` (Path): Starting directory for search. Defaults to current working directory
- **Returns**: `Path` - Project root directory
- **Raises**: `FileNotFoundError` - If no marker found up to filesystem root
- **Priority Strategy**: Searches all the way up for `.git` before considering `.claude` (ensures nested `.claude` dirs work correctly)

#### `get_project_root(use_cache=True)`
- **Purpose**: Get cached project root (detects and caches if first call)
- **Parameters**: `use_cache` (bool): Use cached value or force re-detection (default: True)
- **Returns**: `Path` - Project root directory
- **Thread Safety**: Not thread-safe (uses module-level cache); wrap with threading.Lock for multi-threading
- **Best For**: Performance-critical code that calls repeatedly

#### `get_session_dir(create=True, use_cache=True)`
- **Purpose**: Get session directory path (`PROJECT_ROOT/docs/sessions`)
- **Parameters**:
  - `create` (bool): Create directory if missing (default: True)
  - `use_cache` (bool): Use cached project root (default: True)
- **Returns**: `Path` - Session directory
- **Creates**: Parent directories with safe permissions (0o755 = rwxr-xr-x)
- **Used By**: session_tracker.py, agent_tracker.py

#### `get_batch_state_file()` (Enhanced v3.45.0 - Issue #226)
- **Purpose**: Get batch state file path with automatic worktree isolation support
- **Behavior**:
  - **Worktrees**: Returns `WORKTREE_DIR/.claude/batch_state.json` (isolated per worktree)
  - **Main Repository**: Returns `PROJECT_ROOT/.claude/batch_state.json` (backward compatible)
- **Detection**: Automatically calls `is_worktree()` to detect current directory
- **Returns**: `Path` - Batch state file path (note: file itself not created)
- **Creates**: Parent directory (`.claude/`) if missing, with safe permissions (0o755)
- **Fallback**: If worktree detection fails, falls back to main repo behavior
- **Used By**: batch_state_manager.py
- **Security**: Graceful fallback on detection errors, CWE-22 (path traversal), CWE-59 (symlinks) protection

#### `get_policy_file(use_cache=True)` (NEW in v3.41.0)
- **Purpose**: Get policy file path via cascading lookup with fallback
- **Parameters**: `use_cache` (bool): Use cached value or force re-detection (default: True). Set to False in tests that change working directory.
- **Returns**: `Path` - Policy file (validated and readable)
- **Cascading Lookup Order**:
  1. `.claude/config/auto_approve_policy.json` (project-local) - enables per-project customization
  2. `plugins/autonomous-dev/config/auto_approve_policy.json` (plugin default) - stable fallback
  3. Minimal fallback path (may not exist) - graceful degradation
- **Security Validations**:
  - Rejects symlinks (CWE-59)
  - Prevents path traversal (CWE-22)
  - Validates JSON format
  - Handles permission errors gracefully
- **Thread Safety**: Not thread-safe (uses module-level cache); wrap with threading.Lock for multi-threading
- **Used By**: tool_validator.py
- **Use Cases**:
  - Customize policy per project (place policy in `.claude/config/auto_approve_policy.json`)
  - Inherit plugin defaults (omit custom policy)
  - Test with different policies (call with `use_cache=False`)

#### `is_worktree()` (NEW in v3.45.0 - Issue #226)
- **Purpose**: Check if current directory is a git worktree (lazy-loaded wrapper)
- **Returns**: `bool` - True if in worktree, False otherwise
- **Lazy Import**: Imports git_operations.is_worktree() on first call to avoid circular dependencies
- **Fallback**: Returns False if import fails or detection raises exception
- **Used By**: get_batch_state_file(), get_main_repo_activity_log_dir()
- **Caching**: Module-level function cache for performance
- **Testing**: Can be mocked by patching `path_utils.is_worktree`

#### `get_main_repo_activity_log_dir()` (NEW - Issue #593)
- **Purpose**: Get the activity log directory of the main (parent) repository when running inside a git worktree
- **Returns**: `Optional[Path]` - Path to `<parent_repo>/.claude/logs/activity/` if in a worktree and the directory exists; `None` otherwise
- **Behavior**: Returns `None` immediately when not in a worktree; resolves parent repo path via `git_operations.get_worktree_parent()`
- **Used By**: `pipeline_intent_validator.validate_pipeline_intent()` to merge main repo logs and prevent false INCOMPLETE findings in worktree context
- **Fallback**: Returns `None` if worktree detection fails, parent resolution fails, or the activity directory does not exist

#### `reset_project_root_cache()`
- **Purpose**: Reset cached project root (testing only)
- **Warning**: Only use in test teardown; production code should maintain cache for process lifetime

#### `reset_worktree_cache()` (NEW in v3.45.0 - Issue #226)
- **Purpose**: Reset cached is_worktree function (testing only)
- **Warning**: Only use in test teardown; production code should maintain cache for process lifetime

### Test Coverage

- **Total**: 45+ tests in `tests/unit/test_tracking_path_resolution.py` + 15 tests in `tests/unit/lib/test_policy_path_resolution.py` + 15 tests in `tests/unit/lib/test_path_utils_worktree.py` + 9 integration tests in `tests/integration/test_worktree_batch_isolation.py` (NEW v3.45.0) + 9 tests in `tests/unit/lib/test_worktree_log_resolution.py` (Issue #593)
- **Areas**:
  - PROJECT_ROOT detection from various directories
  - Marker file priority (`.git` over `.claude`)
  - Nested `.claude/` handling in git repositories
  - Directory creation with safe permissions
  - Cache behavior and reset
  - Policy file cascading lookup (NEW v3.41.0)
  - Policy file security validation (NEW v3.41.0)
  - Symlink detection in policy files (NEW v3.41.0)
  - Worktree batch state path isolation (NEW v3.45.0 - Issue #226)
  - Concurrent worktree batch operations (NEW v3.45.0)
  - Worktree detection fallback behavior (NEW v3.45.0)
  - Real git worktree integration (NEW v3.45.0)

### Worktree Safety Pattern (NEW in Issues #313-316)

**Critical for Batch Processing**: All libraries must use `get_project_root()` for absolute path resolution to work correctly in worktree-based batch processing.

```python
from path_utils import get_project_root

# BROKEN (Issue #313 - hardcoded relative path)
plugins_dir = "plugins/autonomous-dev"  # Fails in worktrees
config_file = ".claude/settings.json"   # Fails in worktrees

# FIXED (Issue #313 - absolute path via get_project_root())
plugins_dir = get_project_root() / "plugins/autonomous-dev"  # Works in worktrees
config_file = get_project_root() / ".claude/settings.json"   # Works in worktrees
```

**Files Using This Pattern** (Issue #313):
- brownfield_retrofit.py: Dynamic get_project_root() for plugins/ references
- orphan_file_cleaner.py: get_project_root() for plugins directory
- settings_generator.py: get_project_root() for plugins directory
- test_session_state_manager.py: get_project_root() for .claude/ directory
- test_agent_tracker.py: get_project_root() for docs/sessions directory

**Security**: Fixes CWE-22 (Path Traversal) by validating all paths relative to dynamically detected project root.

### Usage Examples

```python
from plugins.autonomous_dev.lib.path_utils import (
    get_project_root,
    get_session_dir,
    get_batch_state_file,
    get_policy_file
)

# Get project root (cached after first call)
root = get_project_root()
print(root)  # /path/to/autonomous-dev

# Get session directory (creates if missing)
session_dir = get_session_dir()
session_file = session_dir / "20251117-session.md"

# Get batch state file path (with worktree isolation - v3.45.0)
state_file = get_batch_state_file()
# Main repo: Returns /project/.claude/batch_state.json
# In worktree: Returns /project/worktree-dir/.claude/batch_state.json

# Check if in worktree (v3.45.0)
from plugins.autonomous_dev.lib.path_utils import is_worktree
if is_worktree():
    print("Running in git worktree - batch state isolated")
else:
    print("Running in main repository")

# Get policy file with cascading lookup
policy_file = get_policy_file()
# 1. Tries: .claude/config/auto_approve_policy.json (project-local)
# 2. Falls back to: plugins/autonomous-dev/config/auto_approve_policy.json (plugin default)
# 3. Returns minimal fallback if both missing

# Force re-detection (for tests that change cwd)
from tests.conftest import isolated_project
root = get_project_root(use_cache=False)
policy_file = get_policy_file(use_cache=False)

# Worktree example (v3.45.0)
# In main repo
state_file = get_batch_state_file()  # .claude/batch_state.json

# In worktree
state_file = get_batch_state_file()  # worktree-dir/.claude/batch_state.json (isolated)
```

### Security

- **No Path Traversal**: Only searches upward, never downward
- **Safe Permissions**: Creates directories with 0o755 (rwxr-xr-x)
- **Validation**: Validates marker files exist before returning
- **Symlink Handling**: Resolves symlinks to canonical paths
- **Policy File Security** (v3.41.0):
  - Rejects symlinks in policy file locations (CWE-59)
  - Validates JSON format before use (prevents malformed policy)
  - Handles permission denied errors gracefully
  - Prefers project-local customization for per-project policies

### Migration from Hardcoded Paths

**Before** (Issue #79 - fails from subdirectories):
```python
# Hardcoded path in session_tracker.py line 25
session_dir = Path("docs/sessions")  # Fails if cwd != project root
```

**After** (v3.28.0+):
```python
from path_utils import get_session_dir
session_dir = get_session_dir()  # Works from any subdirectory
```

### Policy File Customization (NEW in v3.41.0)

Per-project policy customization enables different auto-approval policies for different projects:

**Project-Local Policy** (takes priority):
```bash
# Create custom policy in your project
mkdir -p .claude/config/
cp plugins/autonomous-dev/config/auto_approve_policy.json .claude/config/auto_approve_policy.json
# Edit .claude/config/auto_approve_policy.json for project-specific rules
```

**Automatic Fallback**:
```python
# Code automatically uses:
# 1. .claude/config/auto_approve_policy.json (if it exists and is valid)
# 2. plugins/autonomous-dev/config/auto_approve_policy.json (plugin default)
policy_file = get_policy_file()  # No configuration needed!
```

### Related Documentation

- See `library-design-patterns` skill for design principles
- See Issue #79 for hardcoded path fixes and security implications
- See Issue #100 for policy file portability and cascading lookup design
- See `docs/TOOL-AUTO-APPROVAL.md` section "Policy File Location" for user guide

---

## 16. validation.py (286 lines, v3.28.0+)

**Purpose**: Tracking infrastructure security validation (input sanitization and path traversal prevention)

**Issue**: GitHub #79 - Fixes security gaps in tracking modules (path traversal, control character injection)

### Key Features

- **Path Traversal Prevention**: Rejects paths with `..` sequences, validates within allowed directories
- **Symlink Attack Prevention**: Rejects symlinks that could bypass path restrictions
- **Input Validation**: Agent names, messages with length limits and character validation
- **Control Character Filtering**: Prevents log injection attacks
- **Clear Error Messages**: Helpful guidance for developers using these APIs

### Public API

#### `validate_session_path(path, purpose="session tracking")`
- **Purpose**: Validate session path to prevent path traversal attacks
- **Parameters**:
  - `path` (str|Path): Path to validate
  - `purpose` (str): Description for error messages
- **Returns**: `Path` - Validated and resolved path
- **Raises**: `ValueError` - If path contains traversal sequences, is outside allowed dirs, or is symlink
- **Allowed Directories**:
  - `PROJECT_ROOT/docs/sessions/` (session files)
  - `PROJECT_ROOT/.claude/` (state files)
- **Security Coverage**: CWE-22 (path traversal), CWE-59 (symlink resolution)

#### `validate_agent_name(name, purpose="agent tracking")`
- **Purpose**: Validate agent name (alphanumeric, hyphen, underscore only)
- **Parameters**:
  - `name` (str): Agent name to validate
  - `purpose` (str): Description for error messages
- **Returns**: `str` - Validated agent name (whitespace stripped)
- **Raises**: `ValueError` - If name is empty, too long (>255 chars), or contains invalid characters
- **Allowed Characters**: Letters (a-z, A-Z), numbers (0-9), hyphen (-), underscore (_)
- **Security Coverage**: Input injection prevention

#### `validate_message(message, purpose="message logging")`
- **Purpose**: Validate message (length limits, no control characters)
- **Parameters**:
  - `message` (str): Message to validate
  - `purpose` (str): Description for error messages
- **Returns**: `str` - Validated message (stripped of leading/trailing whitespace)
- **Raises**: `ValueError` - If message exceeds 10KB or contains control characters
- **Allowed Characters**: Printable ASCII, tabs, newlines, carriage returns
- **Blocked Characters**: Control characters (ASCII 0-31 except tab/newline/CR)
- **Security Coverage**: Log injection prevention, DoS prevention (input limits)

### Constants

- `MAX_MESSAGE_LENGTH = 10000` - Maximum message length (10KB)
- `MAX_AGENT_NAME_LENGTH = 255` - Maximum agent name length

### Test Coverage

- **Total**: 35+ tests in `tests/unit/test_tracking_security.py`
- **Areas**:
  - Path traversal attack detection (various `.` and `..` patterns)
  - Symlink attack detection
  - Path outside allowed directories
  - Agent name validation (empty, too long, invalid characters)
  - Message validation (too long, control characters)
  - Helpful error messages

### Usage Examples

```python
from plugins.autonomous_dev.lib.validation import (
    validate_session_path,
    validate_agent_name,
    validate_message
)

# Validate session path
try:
    safe_path = validate_session_path("/project/docs/sessions/file.json")
except ValueError as e:
    print(f"Invalid path: {e}")

# Validate agent name
try:
    name = validate_agent_name("researcher-v2")
    print(f"Valid name: {name}")
except ValueError as e:
    print(f"Invalid name: {e}")

# Validate message
try:
    msg = validate_message("Research complete - 5 patterns found")
    print(f"Valid message: {msg}")
except ValueError as e:
    print(f"Invalid message: {e}")

# Security: These raise ValueError
validate_session_path("../../etc/passwd")  # Path traversal
validate_session_path("/etc/passwd")  # Outside allowed dirs
validate_agent_name("../../etc/passwd")  # Invalid chars
validate_agent_name("")  # Empty
validate_message("x" * 20000)  # Too long
validate_message("msg\x00with\x01control")  # Control chars
```

### Security Principles

- **Whitelist Validation**: Only allow specific characters and paths
- **Fail Closed**: Reject unknown inputs (not permissive)
- **Clear Errors**: Error messages guide developers to correct usage
- **Defense in Depth**: Multiple validation layers prevent bypasses
- **No Eval/Exec**: Pure validation, no code execution

### Used By

- `session_tracker.py` - Session file path and agent name validation
- `batch_state_manager.py` - Batch state file path validation
- `agent_tracker.py` - Agent name validation for session tracking

### Related Documentation

- See `security-patterns` skill for validation principles
- See `library-design-patterns` skill for input validation design
- See Issue #79 for security implications and threat model

---

## 17. file_discovery.py (354 lines, v3.29.0+)

**Purpose**: Comprehensive file discovery with intelligent exclusion patterns for 100% coverage

### Classes

#### `DiscoveryResult`
- **Purpose**: Result dataclass for file discovery operation
- **Attributes**:
  - `files` (List[Path]): List of discovered files (absolute paths)
  - `count` (int): Total number of files discovered
  - `excluded_count` (int): Number of files excluded
  - `directories` (List[Path]): List of discovered directories

### Key Methods

#### `FileDiscovery.discover_all_files()`
- **Purpose**: Recursively discover all files in plugin directory
- **Returns**: `DiscoveryResult`
- **Features**:
  - Recursive directory traversal (finds all 201+ files)
  - Intelligent exclusion patterns (cache, build artifacts, hidden files)
  - Nested skill structure support (skills/[name].skill/docs/...)
  - Performance optimized (patterns compiled, single pass)

#### `FileDiscovery.discover_by_type(file_type)`
- **Purpose**: Discover files matching specific type
- **Parameters**: `file_type` (str): File type (e.g., "py", "md", "json")
- **Returns**: `DiscoveryResult`

#### `FileDiscovery.generate_manifest()`
- **Purpose**: Generate installation manifest from discovered files
- **Returns**: `dict` (manifest structure)
- **Features**: Categorizes files (agents, commands, hooks, skills, lib, scripts, config, templates)

#### `FileDiscovery.validate_against_manifest(manifest)`
- **Purpose**: Compare discovered files vs manifest
- **Returns**: `dict` with missing/extra files
- **Features**: Detects file coverage gaps

### Exclusion Patterns

**Built-in patterns** (configurable, with two-tier matching strategy):

**Exact Patterns** (EXCLUDE_PATTERNS set):
- Cache: `__pycache__`, `.pytest_cache`, `.eggs`, `*.egg-info`, `*.egg`
- Build artifacts: `*.pyc`, `*.pyo`, `*.pyd`, `build`, `dist`
- Version control: `.git`, `.gitignore`, `.gitattributes`
- IDE: `.vscode`, `.idea`
- Temp/backup: `*.tmp`, `*.bak`, `*.log`, `*~`, `*.swp`, `*.swo`
- System: `.DS_Store`

**Partial Patterns** (EXCLUDE_DIR_PATTERNS list - enhanced in v3.29.0+):
- Directory name pattern matching: `.egg-info`, `__pycache__`, `.pytest_cache`, `.git`, `.eggs`, `build`, `dist`
- Detects patterns within directory names (e.g., `foo-1.0.0.egg-info` matches `.egg-info` pattern)
- Prevents false negatives from naming variations

### Security
- Path validation via security_utils
- Symlink detection and handling
- Safe recursive traversal (prevents infinite loops)

### Test Coverage
- 60+ unit tests (discovery, exclusions, nested structures, edge cases)
- Integration tests with actual plugin directory

### Used By
- install_orchestrator.py for installation planning
- copy_system.py for determining what to copy

### Related
- GitHub Issue #80 (Bootstrap overhaul - 100% file coverage)

---

## 18. copy_system.py (274 lines, v3.29.0+)

**Purpose**: Structure-preserving file copying with permission handling

### Classes

#### `CopyError`
- **Purpose**: Exception raised during copy operations

#### `CopyResult`
- **Purpose**: Result dataclass for copy operation
- **Attributes**:
  - `success` (bool): Whether copy succeeded
  - `copied_count` (int): Number of files successfully copied
  - `failed_count` (int): Number of files that failed
  - `message` (str): Human-readable result
  - `failed_files` (List[dict]): Details of failed copies

### Key Methods

#### `CopySystem.copy_all()`
- **Purpose**: Copy all discovered files with structure preservation
- **Returns**: `CopyResult`
- **Features**:
  - Directory structure preservation (lib/foo.py → .claude/lib/foo.py)
  - Executable permissions for scripts (scripts/*.py get +x)
  - Timestamp preservation
  - Progress reporting with callbacks
  - Error handling with optional continuation

#### `CopySystem.copy_file(source, destination)`
- **Purpose**: Copy single file with validation
- **Parameters**:
  - `source` (Path): Source file
  - `destination` (Path): Destination file
- **Returns**: `bool`
- **Features**: Creates parent directories, validates permissions

#### `CopySystem.set_executable_permission(file_path)`
- **Purpose**: Set executable bit for scripts
- **Parameters**: `file_path` (Path): File to make executable
- **Security**: Only applies to allowed patterns (scripts/*.py, hooks/*.py)

#### `CopySystem.rollback(backup_dir, dest_dir)` - ENHANCED in v3.29.0+
- **Purpose**: Restore installation from backup on failure (with early validation)
- **Parameters**:
  - `backup_dir` (Path): Path to backup directory
  - `dest_dir` (Path): Destination directory to restore to
- **Returns**: `bool` (True if rollback succeeded, False otherwise)
- **Features**:
  - Early validation: Checks backup exists before removing destination
  - Safe removal: Only removes destination if backup is available
  - Atomic restore: Copies entire backup directory structure
  - Security: Path validation, symlink protection
- **Enhancement (v3.29.0+)**: Added early backup existence check before removing destination
  - Prevents accidental deletion if backup is missing
  - More robust error handling and recovery

### Progress Callback

#### `CopySystem.copy_all(progress_callback=callback)`
- **Signature**: `callback(current: int, total: int, file_path: Path)`
- **Purpose**: Real-time progress reporting during copy
- **Example**: Display progress bar, log operations

### Security
- Path validation via security_utils
- Destination path must be within allowed directories
- Permission preservation (respects umask)
- Rollback support (can recover from partial copies)

### Error Handling
- Per-file error handling (one failure doesn't block others)
- Optional strict mode (fail on first error)
- Detailed error information (source, destination, reason)

### Test Coverage
- 45+ unit tests (file copying, permissions, nested dirs, rollback, error cases)
- Integration tests with real filesystem

### Used By
- install_orchestrator.py for file installation

### Related
- GitHub Issue #80 (Bootstrap overhaul - structure-preserving copy)

---

## 19. installation_validator.py (632 lines, v3.29.0+ → v3.29.1)

**Purpose**: Ensures complete file coverage and detects installation issues + duplicate library validation

**Enhanced in v3.29.1 (Issue #81)**: Added duplicate library detection and cleanup recommendations

### Classes

#### `ValidationError`
- **Purpose**: Exception raised when validation encounters critical error

#### `ValidationResult`
- **Purpose**: Result dataclass for validation operation
- **Attributes**:
  - `status` (str): "complete" if 100% coverage, "incomplete" otherwise
  - `coverage` (float): File coverage percentage (0-100)
  - `total_expected` (int): Total files expected from source
  - `total_found` (int): Total files found in destination
  - `missing_files` (int): Count of missing files
  - `extra_files` (int): Count of extra files
  - `missing_file_list` (List[str]): Paths of missing files
  - `extra_file_list` (List[str]): Paths of extra files
  - `structure_valid` (bool): Whether directory structure is valid
  - `errors` (List[str]): List of error messages
  - `sizes_match` (bool|None): Whether file sizes match manifest (if applicable)
  - `size_errors` (List[str]|None): Files with size mismatches (if applicable)
  - `missing_by_category` (Dict[str, int]|None): Missing files categorized by directory (NEW in v3.29.0+)
  - `critical_missing` (List[str]|None): List of critical missing files (NEW in v3.29.0+)

### Key Methods

#### `InstallationValidator.validate(threshold=100.0)`
- **Purpose**: Validate complete installation
- **Parameters**:
  - `threshold` (float, optional): Coverage threshold percentage (default: 100.0, can be 99.5 for flexible validation)
- **Returns**: `ValidationResult`
- **Features**:
  - File coverage calculation (actual/expected * 100)
  - Missing file detection (source files not in destination)
  - Extra file detection (unexpected files in destination)
  - Directory structure validation
  - File categorization by directory (NEW in v3.29.0+)
  - Critical file identification (NEW in v3.29.0+)
  - File size validation (NEW in v3.29.0+)
  - Threshold-based status determination (flexible pass/fail criteria)
  - Detailed reporting

#### `InstallationValidator.validate_sizes()` - NEW in v3.29.1
- **Purpose**: Validate file sizes against manifest
- **Parameters**: None (uses internal manifest)
- **Returns**: `Dict` with `sizes_match` (bool) and `size_errors` (List[str])
- **Raises**: `ValidationError` if no manifest provided
- **Features**: Detects corrupted downloads or partial installs

#### `InstallationValidator.categorize_missing_files(missing_file_list)` - NEW in v3.29.0+

**Signature**: `categorize_missing_files(missing_file_list: List[str]) -> Dict[str, int]`

- **Purpose**: Categorize missing files by directory for detailed reporting
- **Parameters**: `missing_file_list` (List[str]): List of missing file paths
- **Returns**: `Dict[str, int]` mapping directory to count
  - Example: `{"scripts": 2, "lib": 5, "agents": 1}`
- **Features**:
  - Groups missing files by first directory component
  - Provides summary for quick problem diagnosis
  - Used in `validate()` method to populate `missing_by_category`

#### `InstallationValidator.identify_critical_files(missing_file_list)` - NEW in v3.29.0+

**Signature**: `identify_critical_files(missing_file_list: List[str]) -> List[str]`

- **Purpose**: Identify critical missing files that must be installed
- **Parameters**: `missing_file_list` (List[str]): List of missing file paths
- **Returns**: `List[str]` of critical missing files
- **Critical Patterns**:
  - `scripts/setup.py`
  - `lib/security_utils.py`
  - `lib/install_orchestrator.py`
  - `lib/file_discovery.py`
  - `lib/copy_system.py`
  - `lib/installation_validator.py`
- **Features**:
  - Identifies essential files for plugin operation
  - Used in `validate()` method to populate `critical_missing`
  - Helps prioritize missing file recovery

#### `InstallationValidator.validate_no_duplicate_libs()` - NEW in v3.29.1

**Signature**: `validate_no_duplicate_libs() -> List[str]`

- **Purpose**: Validate that no duplicate libraries exist in `.claude/lib/`
- **Details**:
  - Checks for Python files in `.claude/lib/` that conflict with canonical location
  - Uses `OrphanFileCleaner.find_duplicate_libs()` for detection
  - Returns warning messages with cleanup instructions if duplicates found
- **Returns**: `List[str]` of warning messages
  - Empty list if no duplicates found
  - Warnings include file count and cleanup instructions if duplicates detected
- **Behavior**:
  - Returns empty list if `.claude/lib/` doesn't exist
  - Returns empty list if `.claude/lib/` is empty
  - Provides clear remediation steps in warning messages
  - Audit logs detection results
- **Example**:
  ```python
  validator = InstallationValidator(source_dir, dest_dir)
  warnings = validator.validate_no_duplicate_libs()
  if warnings:
      for warning in warnings:
          print(f"WARNING: {warning}")
  ```

#### `InstallationValidator.from_manifest(manifest_path, dest_dir)` (classmethod)
- **Purpose**: Validate using installation manifest
- **Parameters**:
  - `manifest_path` (Path): Path to installation_manifest.json
  - `dest_dir` (Path): Installation destination directory
- **Returns**: `InstallationValidator` instance

#### `InstallationValidator.from_manifest_dict(manifest, dest_dir)` (classmethod)
- **Purpose**: Create validator from manifest dictionary
- **Parameters**:
  - `manifest` (Dict): Manifest dictionary
  - `dest_dir` (Path): Installation destination directory
- **Returns**: `InstallationValidator` instance
- **New in v3.29.1**: For testing and programmatic use

#### `InstallationValidator.generate_report(result)`
- **Purpose**: Generate human-readable validation report
- **Parameters**: `result` (ValidationResult): Validation result to format
- **Returns**: `str` (formatted report with symbols and sections)
- **Features**:
  - Coverage percentage with status symbols
  - Missing and extra files listing (first 10 shown)
  - Directory structure validation status
  - File size validation status (if applicable)
  - Detailed error messages

#### `InstallationValidator.calculate_coverage(expected, actual)`
- **Purpose**: Calculate coverage percentage
- **Parameters**:
  - `expected` (int): Number of expected files
  - `actual` (int): Number of actual files
- **Returns**: `float` Coverage percentage (0-100, rounded to 2 decimal places)

#### `InstallationValidator.find_missing_files(expected_files, actual_files)`
- **Purpose**: Find files that are expected but not present
- **Parameters**:
  - `expected_files` (List[Path]): Expected file paths
  - `actual_files` (List[Path]): Actual file paths
- **Returns**: `List[str]` of missing file paths (sorted)

### Coverage Requirements

**100% Coverage Baseline**:
- All 201+ files in plugin directory expected
- Current baseline: 76% coverage (152/201 files)
- Goal: 95%+ coverage (190+ files)

### Validation Levels

1. **Critical**: Directory structure issues (lib/ missing, etc.) OR duplicate libraries found
2. **High**: Key files missing (agents/*.md, commands/*.md)
3. **Medium**: Optional enhancements missing (some lib files)
4. **Low**: Metadata files missing (*.log, session files)

### Security
- Path validation via security_utils.validate_path()
  - Prevents path traversal attacks (CWE-22)
  - Blocks symlink-based attacks (CWE-59)
- File size limits on reading
- Safe manifest parsing (JSON schema validation)
- Duplicate library detection prevents import conflicts (CWE-627)

### Test Coverage
- 60+ unit tests (v3.29.1 additions):
  - Basic validation: 10 tests
  - Duplicate detection: 6 tests (empty, missing, warnings, counts)
  - Cleanup instructions: 3 tests
  - Edge cases: 5+ tests
- Original 40+ tests for coverage/manifest validation maintained
- Total coverage: 60+ tests

### Used By
- install_orchestrator.py for post-installation verification
- plugin_updater.py for pre-update duplicate validation
- /health-check command for installation integrity validation
- orphan_file_cleaner.py for duplicate library warnings

### Related
- GitHub Issue #80 (Bootstrap overhaul - coverage validation)
- GitHub Issue #81 (Prevent .claude/lib/ Duplicate Library Imports) - NEW

---

## 20. install_orchestrator.py (602 lines, v3.29.0+)

**Purpose**: Coordinates complete installation workflow (fresh install, upgrade, rollback)

### Classes

#### `InstallationType` (enum)
- `FRESH`: New installation
- `UPGRADE`: Update existing installation
- `REPAIR`: Fix broken installation

#### `InstallationResult`
- **Purpose**: Result dataclass for installation operation
- **Attributes**:
  - `success` (bool): Whether installation succeeded
  - `installation_type` (InstallationType): Type of installation performed
  - `message` (str): Human-readable result
  - `files_installed` (int): Number of files installed
  - `coverage_percent` (float): File coverage percentage
  - `backup_path` (Path|None): Path to backup (if created during upgrade)
  - `rollback_performed` (bool): Whether rollback was executed
  - `validation_result` (ValidationResult): Post-installation validation

### Key Methods

#### `InstallOrchestrator.fresh_install()`
- **Purpose**: Perform fresh installation
- **Returns**: `InstallationResult`
- **Features**:
  - Discovers all files
  - Creates installation marker
  - Validates coverage (expects 95%+)
  - No backup needed (new installation)

#### `InstallOrchestrator.upgrade_install()`
- **Purpose**: Upgrade existing installation
- **Returns**: `InstallationResult`
- **Features**:
  - Automatic backup before upgrade
  - Preserves user settings and customizations
  - Validates coverage after upgrade
  - Rollback on validation failure

#### `InstallOrchestrator.repair_install()`
- **Purpose**: Repair broken installation
- **Returns**: `InstallationResult`
- **Features**:
  - Detects missing files
  - Recopies missing files
  - Preserves existing correct files
  - Full validation after repair

#### `InstallOrchestrator.auto_detect(project_dir)` (classmethod)
- **Purpose**: Auto-detect installation type and execute
- **Parameters**: `project_dir` (Path): Project directory
- **Returns**: `InstallationResult`
- **Logic**:
  - No .claude/: FRESH installation
  - Has .claude/ + recent marker: UPGRADE
  - Has .claude/ + old/missing files: REPAIR

#### `InstallOrchestrator.rollback(backup_dir)`
- **Purpose**: Restore from backup on failure
- **Parameters**: `backup_dir` (Path): Path to backup directory
- **Security**: Path validation, symlink blocking

### Manifest System

**Installation Manifest** (`config/installation_manifest.json`):
- Lists all required directories
- Defines exclusion patterns
- Specifies executable patterns
- Marks files to preserve on upgrade

### Installation Marker

**Purpose**: Track installation state and coverage

**Location**: `.claude/.install_marker.json`

**Content**:
```json
{
  "version": "3.29.0",
  "installed_at": "2025-11-17T10:30:00Z",
  "installation_type": "fresh",
  "coverage_percent": 98.5,
  "files_installed": 201,
  "marker_version": 1
}
```

### Workflow Integration

**Fresh Install**:
1. Pre-install cleanup (remove duplicate .claude/lib/ libraries)
2. Discover all files
3. Copy with structure preservation
4. Validate coverage (expect 95%+)
5. Create installation marker
6. Activate hooks (optional)

**Upgrade Install**:
1. Pre-install cleanup (remove duplicate .claude/lib/ libraries)
2. Create timestamped backup
3. Discover files
4. Copy files (preserving user customizations if possible)
5. Set permissions
6. Update marker file
7. Validate
8. On failure: rollback

**Repair Install**:
1. Detect missing files (compare against manifest)
2. Copy missing files only
3. Validate coverage
4. Update installation marker

### Security
- All paths validated via security_utils
- Backup directory permissions 0o700 (user-only)
- Atomic marker file writes (tempfile + rename)
- Audit logging to security audit

### Test Coverage
- 60+ unit tests (fresh install, upgrade, repair, rollback scenarios)
- Integration tests with complete workflows

### Used By
- `install.sh` bootstrap script
- `/setup` command
- `/health-check` command (validation)

### Related
- GitHub Issue #80 (Bootstrap overhaul - orchestrated installation)

---

## 21. failure_classifier.py (343 lines, v3.33.0+)

**Purpose**: Classify /implement failures as transient vs permanent for intelligent retry logic.

### Overview

Analyzes error messages to determine if a failed feature attempt should be retried (transient errors like network issues) or marked failed (permanent errors like syntax errors). Was used by the removed batch_retry_manager.py to make retry decisions; it has no caller today.

### Enums

#### `FailureType`
- `TRANSIENT` - Retriable error (network, timeout, rate limit)
- `PERMANENT` - Non-retriable error (syntax, import, type errors)

### Functions

#### `classify_failure(error_message)`
- **Purpose**: Classify error message as transient or permanent
- **Parameters**: `error_message` (str|None): Raw error message
- **Returns**: `FailureType.TRANSIENT` or `FailureType.PERMANENT`
- **Logic**:
  1. Check transient patterns (network, timeout, rate limit)
  2. Check permanent patterns (syntax, import, type errors)
  3. Default to PERMANENT for safety (unknown errors not retried)
- **Examples**:
  ```python
  classify_failure("ConnectionError: Failed to connect")  # TRANSIENT
  classify_failure("SyntaxError: invalid syntax")  # PERMANENT
  classify_failure("WeirdUnknownError")  # PERMANENT (safe default)
  ```

#### `is_transient_error(error_message)`
- **Purpose**: Check if error indicates transient failure
- **Parameters**: `error_message` (str|None): Error message
- **Returns**: `True` if transient, `False` otherwise
- **Patterns Detected**:
  - ConnectionError, NetworkError
  - TimeoutError
  - RateLimitError, HTTP 429/503
  - HTTP 502/504 (Bad Gateway, Gateway Timeout)
  - TemporaryFailure, Service Unavailable

#### `is_permanent_error(error_message)`
- **Purpose**: Check if error indicates permanent failure
- **Parameters**: `error_message` (str|None): Error message
- **Returns**: `True` if permanent, `False` otherwise
- **Patterns Detected**:
  - SyntaxError, IndentationError
  - ImportError, ModuleNotFoundError
  - TypeError, AttributeError, NameError
  - ValueError, KeyError, IndexError
  - AssertionError, ZeroDivisionError

#### `sanitize_error_message(error_message)`
- **Purpose**: Sanitize error message for safe logging (CWE-117 prevention)
- **Parameters**: `error_message` (str|None): Raw error message
- **Returns**: `str` (sanitized message)
- **Security**:
  - Removes newlines (prevent log injection)
  - Removes carriage returns (prevent log injection)
  - Truncates to 1000 chars (prevent resource exhaustion)
- **Examples**:
  ```python
  sanitize_error_message("Error\nFAKE LOG: Admin")  # "Error FAKE LOG: Admin"
  sanitize_error_message("E" * 10000)  # "EEEE...[truncated]"
  ```

#### `extract_error_context(error_message, feature_name)`
- **Purpose**: Extract rich error context for debugging
- **Parameters**:
  - `error_message` (str|None): Raw error message
  - `feature_name` (str): Name of feature being processed
- **Returns**: `Dict` with error context
- **Context Fields**:
  - `error_type` (str): Type extracted from message
  - `error_message` (str): Sanitized message
  - `feature_name` (str): Original feature name
  - `timestamp` (str): ISO 8601 timestamp
  - `failure_type` (str): "transient" or "permanent"
- **Examples**:
  ```python
  context = extract_error_context("SyntaxError: invalid", "Add auth")
  # {
  #   "error_type": "SyntaxError",
  #   "error_message": "SyntaxError: invalid",
  #   "feature_name": "Add auth",
  #   "timestamp": "2025-11-19T10:00:00Z",
  #   "failure_type": "permanent"
  # }
  ```

### Security
- **CWE-117**: Log injection prevention via newline/carriage return removal
- **Resource Exhaustion**: Max 1000-char error messages prevent DOS
- **Safe Defaults**: Unknown errors → permanent (don't retry)

### Constants

- `TRANSIENT_ERROR_PATTERNS`: List of 15+ regex patterns for transient errors
- `PERMANENT_ERROR_PATTERNS`: List of 15+ regex patterns for permanent errors
- `MAX_ERROR_MESSAGE_LENGTH`: 1000 chars (truncate longer messages)

### Test Coverage
- 25+ unit tests covering classification, sanitization, context extraction
- Edge cases: None, empty, unknown error types, long messages

### Used By
- /implement --batch command for retry logic

### Related
- GitHub Issue #89 (Automatic Failure Recovery for /implement --batch)
- error-handling-patterns skill for exception hierarchy

---

## 22. batch_retry_manager.py — REMOVED

Deleted with the never-executed approval subsystem. The module was built,
tested, shipped to five consumer repositories, and never once executed: the
reachability ratchet measured it UNREACHED, and a scan of 541,492 activity-log
lines resolved every mention of it to a file-read operation rather than a call.

The section number is retained so the numbering of every later entry, and the
anchors that link to them, stay valid.

**What enforces this area now**: Claude Code's native permission rules
(4 allow, 61 deny in `.claude/settings.json`) and
`plugins/autonomous-dev/hooks/unified_pre_tool.py`, which recorded 167 refusals
in the two days before this deletion.

---

## 23. batch_retry_consent.py — REMOVED

Deleted with the never-executed approval subsystem. The module was built,
tested, shipped to five consumer repositories, and never once executed: the
reachability ratchet measured it UNREACHED, and a scan of 541,492 activity-log
lines resolved every mention of it to a file-read operation rather than a call.

The section number is retained so the numbering of every later entry, and the
anchors that link to them, stay valid.

**What enforces this area now**: Claude Code's native permission rules
(4 allow, 61 deny in `.claude/settings.json`) and
`plugins/autonomous-dev/hooks/unified_pre_tool.py`, which recorded 167 refusals
in the two days before this deletion.

---

## 24. quality_persistence_enforcer.py (450+ lines, v1.0.0, Issue #254)

**Purpose**: Central enforcement engine for quality gates in batch workflows ensuring features pass all quality requirements before completion.

### Overview

Quality persistence enforcer prevents batches from giving up too easily or faking success when tests fail. System enforces:
- **100% test pass requirement** (not 80%, not "most" - ALL tests must pass)
- **Coverage threshold** (80%+ code coverage)
- **Retry limits** (max 3 attempts per feature)
- **Honest summaries** (shows actual completion status, not inflated numbers)
- **Quality metrics tracking** (test pass rate, coverage percentage)

### Quality Gate Rules

Features are only marked as completed when they truly pass ALL quality gates:

1. **All tests must pass** - 100% test pass rate (exit code 0 from test runner)
2. **Coverage threshold met** - 80%+ code coverage
3. **No infinite retry loops** - Max 3 retry attempts per feature
4. **Clear failure tracking** - Failed features tracked separately from completed

### Data Classes

#### `EnforcementResult`
- **Purpose**: Result of completion gate enforcement check
- **Attributes**:
  - `passed` (bool): Whether the quality gate passed
  - `reason` (str): Human-readable reason (e.g., "Tests failed", "Coverage below threshold")
  - `test_failures` (int): Number of test failures
  - `coverage` (float): Test coverage percentage
  - `attempt_number` (int): Current retry attempt (1-3)
- **Methods**:
  - `to_dict()`: Convert to JSON-serializable dict

#### `RetryStrategy`
- **Purpose**: Escalation strategy for retry attempts
- **Attributes**:
  - `approach` (str): Strategy identifier (e.g., "fix_tests_first")
  - `description` (str): Human-readable description
  - `attempt_number` (int): Retry attempt number (1-3)

#### `CompletionSummary`
- **Purpose**: Honest summary of batch completion status
- **Attributes**:
  - `total_features` (int): Total features in batch
  - `completed_count` (int): Features that passed all quality gates
  - `failed_count` (int): Features that failed and exhausted retries
  - `skipped_count` (int): Features intentionally skipped
  - `completed_features` (List[str]): Feature descriptions that passed
  - `failed_features` (List[str]): Feature descriptions that failed
  - `skipped_features` (List[str]): Feature descriptions that were skipped
  - `average_coverage` (float): Average coverage across all features
- **Methods**:
  - `completion_rate()`: Percentage of features completed
  - `to_dict()`: Convert to JSON-serializable dict

### Main Functions

#### `enforce_completion_gate(feature_index, test_results)`
- **Purpose**: Check if feature passes all quality gates
- **Parameters**:
  - `feature_index` (int): Index of feature in batch
  - `test_results` (Dict): Results from test runner with `total`, `passed`, `failed`, `coverage`
- **Returns**: `EnforcementResult` with pass/fail decision
- **Logic**:
  1. Check if all tests passed (test_results['failed'] == 0)
  2. Check if coverage meets threshold (test_results['coverage'] >= 80%)
  3. Return result with reason if any check fails
- **Example**:
  ```python
  test_results = {"total": 10, "passed": 10, "failed": 0, "coverage": 85.0}
  result = enforce_completion_gate(0, test_results)
  if result.passed:
      print("Feature passed quality gate!")
  else:
      print(f"Gate failed: {result.reason}")
  ```

#### `retry_with_different_approach(feature_index, attempt_number, failure_reason)`
- **Purpose**: Select escalation strategy for retry attempts
- **Parameters**:
  - `feature_index` (int): Index of feature
  - `attempt_number` (int): Which retry (1, 2, or 3)
  - `failure_reason` (str): Why the feature failed
- **Returns**: `RetryStrategy` with next approach, or None if max attempts reached
- **Strategy Progression**:
  - **Attempt 1** (first retry): Basic retry - "Try again with same approach"
  - **Attempt 2** (second retry): Fix tests first - "Focus on making tests pass"
  - **Attempt 3** (third retry): Different implementation - "Try alternative approach"
  - **Beyond 3**: None (stop retrying)

#### `generate_honest_summary(batch_state)`
- **Purpose**: Generate accurate summary of batch completion status
- **Parameters**:
  - `batch_state` (BatchState): State object with feature results
- **Returns**: `CompletionSummary` with accurate counts
- **Behavior**:
  - Counts completed features (passed all quality gates)
  - Counts failed features (exhausted retries without passing)
  - Counts skipped features (intentionally not implemented)
  - Calculates average coverage across all features
  - Never inflates numbers or hides failures
- **Example**:
  ```python
  summary = generate_honest_summary(batch_state)
  print(f"Completed: {summary.completed_count}/{summary.total_features}")
  print(f"Failed: {summary.failed_count}")
  print(f"Skipped: {summary.skipped_count}")
  ```

#### `should_close_issue(batch_state, feature_index)`
- **Purpose**: Decide if GitHub issue should be auto-closed
- **Parameters**:
  - `batch_state` (BatchState): Batch state with feature results
  - `feature_index` (int): Index of feature in batch
- **Returns**: `True` only if feature passed all quality gates (ready for closure)
- **Decision Logic**:
  - Feature completed (passed quality gate) → True (close issue)
  - Feature failed (exhausted retries) → False (keep open with 'blocked' label)
  - Feature skipped (not implemented) → False (keep open with 'blocked' label)

### Constants

- `MAX_RETRY_ATTEMPTS = 3`: Maximum retries per feature
- `COVERAGE_THRESHOLD = 80.0`: Minimum code coverage percentage

### Security

- **No Faking**: System never marks features as complete when tests failed
- **Audit Logging**: All enforcement decisions logged with timestamps
- **Path Validation**: batch_state path validated (CWE-22 prevention)
- **Input Sanitization**: Error messages sanitized for log injection (CWE-117)

### Test Coverage

- 35+ unit tests covering:
  - Completion gate enforcement (all test outcomes)
  - Coverage threshold validation
  - Retry strategy selection (all 3 attempts)
  - Honest summary generation
  - Issue close decision logic
  - Edge cases (0 tests, 100% coverage, max retries)

### Used By

- `/implement --batch` command for quality gate checks
- `batch_issue_closer.py` for issue close decisions
- `batch_state_manager.py` for quality metrics tracking

### Related

- GitHub Issue #254 (Quality Persistence: System gives up too easily)
- error-handling-patterns skill for exception hierarchy
- state-management-patterns skill for state persistence patterns

---

## 25. agent_tracker package (1,755 lines, v3.44.0+, Issue #165)

**Purpose**: Portable tracking infrastructure for agent execution with dynamic project root detection

**Problem Solved (Issue #79)**: Original `scripts/agent_tracker.py` had hardcoded paths that failed when:
- Running from user projects (no `scripts/` directory)
- Running from project subdirectories (couldn't find project root)
- Commands invoked from installation path vs development path

**Solution (Issue #165 Refactoring)**: Monolithic library file (1,185 lines) split into focused package with 8 modules for maintainability:

**Package Structure** (`plugins/autonomous-dev/lib/agent_tracker/`):
- `__init__.py` (72 lines): Re-exports for backward compatibility
- `models.py` (64 lines): Data structures (AGENT_METADATA, EXPECTED_AGENTS)
- `state.py` (408 lines): Session state management and agent lifecycle
- `tracker.py` (478 lines): Main AgentTracker class with delegation pattern
- `metrics.py` (116 lines): Progress calculation and time estimation
- `verification.py` (311 lines): Parallel execution verification
- `display.py` (200 lines): Status display and visualization
- `cli.py` (98 lines): Command-line interface

**Backward Compatibility**: All imports continue to work via re-exports:
- Old: `from agent_tracker import AgentTracker` ✅ still works
- New: `from agent_tracker.tracker import AgentTracker` (preferred)
- Path utilities also re-exported for legacy code

**Benefits**:
- Dynamic project root detection via path_utils
- Portable path resolution (no hardcoded paths)
- Atomic file writes for data consistency
- Comprehensive error handling with context
- Clearer module responsibilities (each <500 lines)
- Easier testing and maintenance
- Better IDE support and code navigation

### Classes

#### `AgentTracker`
- **Purpose**: Track agent execution with structured logging
- **Location**: `tracker.py` (delegates to state manager)
- **Initialization**: `AgentTracker(session_file=None)`
  - `session_file` (Optional[str]): Path to session file for testing
  - If None: Creates/finds session file automatically using path_utils
  - Raises `ValueError` if session_file path is outside project (path traversal prevention)
- **Features**:
  - Auto-detects project root from any subdirectory
  - Creates `docs/sessions/` directory if missing
  - Finds or creates JSON session files with timestamp naming: `YYYYMMDD-HHMMSS-pipeline.json`
  - Session isolation via `CLAUDE_SESSION_ID`: when the env var is set, file selection filters to pipeline.json files whose stored `claude_session_id` field matches the current session, preventing cross-session pollution when multiple batches run on the same day (Issue #594). Falls back to latest file when env var is absent.
  - Schema compatibility via `setdefault("agents", [])` at all three session-file loading sites (Issue #576): session files that use the new pipeline schema and omit the `agents` key no longer raise `KeyError` on load.
  - Atomic writes using tempfile + rename pattern (Issue #45 security)
  - Path validation via shared security_utils module

### Public Methods

#### Agent Lifecycle Methods

#### `start_agent(agent_name, message)`
- **Purpose**: Log agent start time
- **Parameters**:
  - `agent_name` (str): Agent name (validated via security_utils)
  - `message` (str): Start message (max 10KB)
- **Records**:
  - Start timestamp (ISO format)
  - Agent name and status ("started")
  - Initial message
- **Security**: Input validation prevents injection attacks

#### `complete_agent(agent_name, message, tools=None, tools_used=None, github_issue=None)`
- **Purpose**: Log agent completion with optional metrics
- **Parameters**:
  - `agent_name` (str): Agent name
  - `message` (str): Completion message
  - `tools` (Optional[List[str]]): Tools declared to use (metadata)
  - `tools_used` (Optional[List[str]]): Tools actually used (audit trail)
  - `github_issue` (Optional[int]): Linked GitHub issue number
- **Records**:
  - Completion timestamp (ISO format)
  - Duration in seconds (auto-calculated from start)
  - Message and tool usage
  - Links to GitHub issue if provided
- **Returns**: Boolean indicating success
- **Error Handling**: Logs errors without raising (non-blocking)
- **Idempotency (Issue #57, #541)**: If agent is already in a terminal state ("completed" or "failed"), the call is a no-op. This prevents duplicate status entries when both an explicit `complete_agent()` call and the SubagentStop hook fire for the same agent.

#### `fail_agent(agent_name, message)`
- **Purpose**: Log agent failure
- **Parameters**:
  - `agent_name` (str): Agent name
  - `message` (str): Failure message
- **Records**:
  - Failure timestamp
  - Error message with context
  - Status set to "failed"
- **Security**: Error messages sanitized to prevent log injection
- **Idempotency (Issue #541)**: If agent is already in a terminal state ("completed" or "failed"), the call is a no-op. This prevents a late `fail_agent()` call (e.g. from a text-scan fallback in `unified_session_tracker.py`) from overwriting a correctly completed agent.

#### Pipeline Status Methods

#### `set_github_issue(issue_number)`
- **Purpose**: Link session to GitHub issue number
- **Parameters**: `issue_number` (int): GitHub issue (1-999999)
- **Uses**: GitHub Issue metadata in STEP 5 checkpoints

#### `show_status()`
- **Purpose**: Display current pipeline status with colors and emojis
- **Output**:
  - Session ID and start time
  - List of agents (started/completed/failed/pending)
  - Progress percentage (agents completed / total expected)
  - Tree view of execution flow
  - Duration metrics (actual, average, estimated remaining)
- **Color Coding**: Uses ANSI colors for status visualization

#### Progress Tracking Methods

#### `get_expected_agents() -> List[str]`
- **Purpose**: Return list of expected agents for workflow
- **Returns**: List of agent names (hardcoded per workflow type)
- **Used By**: Progress calculations, pipeline verification
- **Location**: Delegates to `metrics.py`

#### `calculate_progress() -> int`
- **Purpose**: Calculate workflow completion percentage
- **Returns**: Integer 0-100
- **Calculation**: `(agents_completed / agents_expected) * 100`
- **Location**: Delegates to `metrics.py`

#### `get_average_agent_duration() -> Optional[int]`
- **Purpose**: Calculate average duration of completed agents
- **Returns**: Seconds (or None if no agents completed)
- **Uses**: Estimation of remaining time
- **Location**: Delegates to `metrics.py`

#### `estimate_remaining_time() -> Optional[int]`
- **Purpose**: Estimate time until workflow completion
- **Returns**: Seconds (or None if insufficient data)
- **Calculation**: `(pending_agents * average_duration) + safety_buffer`
- **Location**: Delegates to `metrics.py`

#### `get_pending_agents() -> List[str]`
- **Purpose**: List agents not yet started
- **Returns**: List of agent names
- **Uses**: Progress tracking and timeout calculations
- **Location**: Delegates to `state.py`

#### `get_running_agent() -> Optional[str]`
- **Purpose**: Get currently running agent
- **Returns**: Agent name (or None if none running)
- **Uses**: Checkpoint verification, deadlock detection
- **Location**: Delegates to `state.py`

#### Verification Methods

#### `verify_parallel_exploration() -> bool`
- **Purpose**: Verify parallel exploration checkpoint (STEP 1)
- **Checks**:
  - researcher agent completed
  - planner agent completed
  - Execution time ≤ 10 minutes (typical: 5-8 minutes)
- **Returns**: True if verification passed
- **Output**: Displays efficiency metrics and time saved
- **Used By**: auto-implement.md CHECKPOINT 1 (line 109)
- **Graceful Degradation**: Returns False if AgentTracker unavailable (non-blocking)
- **Location**: Delegates to `verification.py`

#### `verify_parallel_validation() -> bool`
- **Purpose**: Verify parallel validation checkpoint (STEP 4.1)
- **Checks**:
  - reviewer agent completed
  - security-auditor agent completed
  - doc-master agent completed
  - Execution time ≤ 5 minutes (typical: 2-3 minutes)
- **Returns**: True if verification passed
- **Output**: Displays efficiency metrics
- **Used By**: auto-implement.md CHECKPOINT 4.1 (line 390)
- **Graceful Degradation**: Returns False if unavailable (non-blocking)
- **Location**: Delegates to `verification.py`

#### `get_parallel_validation_metrics() -> Dict[str, Any]`
- **Purpose**: Extract metrics from parallel validation execution
- **Returns**: Dictionary with:
  - `reviewer_duration`: seconds
  - `security_auditor_duration`: seconds
  - `doc_master_duration`: seconds
  - `parallel_time`: max of above (actual duration)
  - `sequential_time`: sum of above (if run sequentially)
  - `time_saved`: sequential - parallel
  - `efficiency_percent`: (time_saved / sequential) * 100
- **Uses**: Checkpoint display and performance analysis
- **Location**: Delegates to `verification.py`

#### `is_pipeline_complete() -> bool`
- **Purpose**: Check if all expected agents completed
- **Returns**: True if all agents in "completed" or "failed" state
- **Uses**: Workflow completion detection
- **Location**: Delegates to `state.py`

#### `is_agent_tracked(agent_name) -> bool`
- **Purpose**: Check if agent has been logged
- **Parameters**: `agent_name` (str): Agent to check
- **Returns**: True if agent found in session
- **Location**: Delegates to `state.py`

#### Environment Tracking

#### `auto_track_from_environment(message=None) -> bool`
- **Purpose**: Auto-detect running agent from environment variable
- **Parameters**: `message` (Optional[str]): Optional override message
- **Reads**: `CLAUDE_AGENT_NAME` environment variable (set by Task tool and Claude Code)
- **Returns**:
  - `True` if agent was newly tracked (created start entry)
  - `False` if agent already tracked (idempotent - no duplicate)
  - `False` if environment variable not set (graceful degradation)
- **Security**: Validates agent name format before logging
- **Used By**:
  - SubagentStop hook (log_agent_completion.py) - Issue #104
  - Explicit checkpoint tracking in auto-implement.md
- **Task Tool Integration (Issue #104)**:
  - Task tool sets `CLAUDE_AGENT_NAME` when invoking agents
  - SubagentStop hook calls this method before `complete_agent()`
  - Ensures parallel Task tool agents (reviewer, security-auditor, doc-master) are tracked
  - Prevents incomplete entries (completion without start)
  - Idempotent design prevents duplicates when combined with explicit tracking
- **Location**: Delegates to `state.py`

### Formatting & Display Methods

#### `get_agent_emoji(status) -> str`
- **Purpose**: Get emoji for agent status
- **Status Mappings**:
  - "started" → "▶️"
  - "completed" → "✅"
  - "failed" → "❌"
  - "pending" → "⏳"
- **Location**: `display.py`

#### `get_agent_color(status) -> str`
- **Purpose**: Get ANSI color code for status
- **Colors**: Green (completed), Red (failed), Yellow (started), Gray (pending)
- **Location**: `display.py`

#### `get_display_metadata() -> Dict[str, Any]`
- **Purpose**: Get formatted metadata for display
- **Returns**: Dictionary with:
  - `session_id`: Unique session identifier
  - `started`: Human-readable start time
  - `duration`: Total elapsed time
  - `progress`: Completion percentage
  - `agents_summary`: Count by status
- **Location**: `display.py`

#### `get_tree_view_data() -> Dict[str, Any]`
- **Purpose**: Get tree structure for ASCII tree display
- **Returns**: Hierarchical dictionary representing workflow execution
- **Location**: `display.py`

### Session Data Format

JSON session files stored in `docs/sessions/YYYYMMDD-HHMMSS-pipeline.json`:

```json
{
  "session_id": "20251119-143022",
  "claude_session_id": "abc123",
  "started": "2025-11-19T14:30:22.123456",
  "github_issue": 79,
  "agents": [
    {
      "agent": "researcher",
      "status": "completed",
      "started_at": "2025-11-19T14:30:25",
      "completed_at": "2025-11-19T14:35:10",
      "duration_seconds": 285,
      "message": "Found 3 JWT patterns",
      "tools_used": ["mcp__searxng__search", "Grep", "Read"]
    }
  ]
}
```

### Security Features

#### Path Traversal Prevention (CWE-22)
- All paths validated to stay within project root
- Rejects `..` sequences in path strings
- Uses shared `validate_path()` from security_utils
- Audit logging of all validation attempts

#### Symlink Attack Prevention (CWE-59)
- Rejects symlinks that could bypass restrictions
- Path normalization prevents escape attempts
- Atomic file writes prevent partial reads

#### Input Validation
- Agent names: 1-255 chars, alphanumeric + hyphen/underscore only
- Messages: Max 10KB to prevent log bloat
- GitHub issue: Positive integers 1-999999 only
- Control character filtering prevents log injection (CWE-117)

#### Atomic File Writes (Issue #45)
- Uses tempfile + rename pattern for consistency
- Process crash during write: Original file unchanged
- Prevents readers from seeing corrupted/partial JSON
- On POSIX: Rename is guaranteed atomic by OS

### Class Methods

#### `AgentTracker.save_agent_checkpoint()` (Issue #79, v3.36.0+)

**Signature**:
```python
@classmethod
def save_agent_checkpoint(
    cls,
    agent_name: str,
    message: str,
    github_issue: Optional[int] = None,
    tools_used: Optional[List[str]] = None
) -> bool
```

**Purpose**: Convenience class method for agents to save checkpoints without creating AgentTracker instances. Solves the dogfooding bug (Issue #79) where hardcoded paths caused `/implement` to stall for 7+ hours.

**Parameters**:
- `agent_name` (str): Agent name (e.g., 'researcher', 'planner'). Must be alphanumeric + hyphen/underscore.
- `message` (str): Brief completion summary. Maximum 10KB.
- `github_issue` (Optional[int]): GitHub issue number being worked on. Range: 1-999999.
- `tools_used` (Optional[List[str]]): List of tools used during execution. Stored in session file for audit trail.

**Returns**: `bool`
- `True` if checkpoint saved successfully
- `False` if skipped due to graceful degradation (user project, import error, filesystem error)

**Behavior**:
- Uses portable path detection (works from any directory)
- Creates AgentTracker internally (caller doesn't manage instance)
- Validates all inputs before saving
- Gracefully degrades in user projects (prints info message, returns False)
- Never raises exceptions (non-blocking design)

**Examples**:

```python
# Basic usage (works from any directory)
from agent_tracker import AgentTracker

success = AgentTracker.save_agent_checkpoint(
    'researcher',
    'Found 3 JWT patterns in codebase'
)
if success:
    print("✅ Checkpoint saved")
else:
    print("ℹ️ Skipped (user project)")

# With all parameters
success = AgentTracker.save_agent_checkpoint(
    agent_name='planner',
    message='Architecture designed - see docs/design/auth.md',
    github_issue=79,
    tools_used=['FileSearch', 'Read', 'Write']
)

# In agent code (automatic error handling)
AgentTracker.save_agent_checkpoint(
    agent_name='implementer',
    message='Implementation complete - 450 lines of code',
    tools_used=['Read', 'Write', 'Execute']
)
# Even if this fails, agent continues working
```

**Security**:
- Input validation: agent_name, message, github_issue all validated
- Path validation: All paths checked against project root (CWE-22)
- No subprocess calls: Uses library imports (prevents CWE-78)
- Message length limit: Prevents log bloat attacks
- Graceful degradation: No sensitive error leakage

**Graceful Degradation**:
When running in environments without tracking infrastructure:
- User projects (no `plugins/` directory) -> skips, returns False
- Import errors (missing dependencies) -> skips, returns False
- Filesystem errors (permission denied) -> skips, returns False
- Unexpected errors -> logs warning, returns False

This allows agents to be portable across development and user environments.

**Design Pattern**: Progressive Enhancement - feature works with or without supporting infrastructure

**Related**: GitHub Issue #79 (Dogfooding bug fix), Issue #82 (Optional checkpoint verification)

### Module Architecture (Issue #165)

**Purpose of Refactoring**: Split monolithic 1,185-line file into focused modules for:
- Easier testing (unit test each responsibility separately)
- Better maintainability (changes isolated to relevant modules)
- Clearer code organization (each module has single responsibility)
- Performance monitoring (metrics in dedicated module)
- Display logic separation (display.py handles all formatting)

**Delegation Pattern**:
- `tracker.py` (441 lines): AgentTracker class coordinates via delegation
- Methods call specialized manager classes from other modules
- Reduces complexity: Main class focuses on public API, not implementation details
- Example: `calculate_progress()` delegates to `metrics.calculate_progress()`

**State Management** (state.py - 408 lines):
- `StateManager` class handles session file I/O
- Tracks agent start/completion times
- Manages JSON serialization and atomic writes
- Enforces security constraints (path validation)

**Metrics Calculation** (metrics.py - 116 lines):
- `MetricsCalculator` class handles all time-based calculations
- Progress percentage, average duration, remaining time estimates
- No I/O operations (pure calculation)
- Easy to unit test

**Verification Logic** (verification.py - 311 lines):
- `ParallelVerifier` class handles parallel execution checks
- Validates checkpoint requirements (agents completed, time thresholds)
- Extracts and formats metrics for display
- Used by CHECKPOINT 1 and CHECKPOINT 4.1

**Display Formatting** (display.py - 200 lines):
- `DisplayFormatter` class handles all output formatting
- ANSI colors, emoji status indicators, tree view generation
- Separated from logic (can swap formatters for testing)
- Enables future HTML/JSON output formats

**Data Models** (models.py - 64 lines):
- Constants: `AGENT_METADATA`, `EXPECTED_AGENTS` per workflow
- Enum for agent status values
- Type hints for consistency

**CLI Wrapper** (cli.py - 98 lines):
- Command-line interface delegating to AgentTracker
- Commands: start, complete, fail, status, set-github-issue
- Argument parsing and error handling

### CLI Wrapper

**File**: `plugins/autonomous-dev/scripts/agent_tracker.py`
- **Purpose**: CLI interface for library functionality
- **Design**: Delegates to `plugins/autonomous-dev/lib/agent_tracker/` package
- **Commands**:
  - `start <agent_name> <message>`: Start agent tracking
  - `complete <agent_name> <message> [--tools tool1,tool2]`: Complete agent
  - `fail <agent_name> <message>`: Log failure
  - `status`: Display current status
- **Backward Compatibility**: Installed plugin uses lib version directly

### Deprecation (Issue #79)

**Deprecated**: `scripts/agent_tracker.py` (original location)
- **Reason**: Hardcoded paths fail in user projects and subdirectories
- **Migration**:
  - For CLI: Use `plugins/autonomous-dev/scripts/agent_tracker.py` (installed plugin)
  - For imports: Use `from plugins.autonomous_dev.lib.agent_tracker import AgentTracker`
  - Existing code continues to work (delegates to library implementation)
  - Will be removed in v4.0.0

### Usage Examples

#### Basic Usage (Standard Mode)
```python
from agent_tracker import AgentTracker

# Create tracker (auto-detects project root)
tracker = AgentTracker()

# Log agent start
tracker.start_agent("researcher", "Researching JWT patterns")

# Log agent completion
tracker.complete_agent("researcher", "Found 3 patterns",
                       tools_used=["mcp__searxng__search", "Grep", "Read"],
                       github_issue=79)

# Display status
tracker.show_status()
```

#### Testing with Explicit Session File
```python
from pathlib import Path
tracker = AgentTracker(session_file="/tmp/test-session.json")
tracker.start_agent("test-agent", "Testing")
```

#### Checkpoint Verification (auto-implement.md)
```python
tracker = AgentTracker()

# Verify parallel exploration (STEP 1)
if tracker.verify_parallel_exploration():
    print("✅ PARALLEL EXPLORATION: SUCCESS")
    metrics = tracker.get_parallel_validation_metrics()
    print(f"Time saved: {metrics['time_saved']}s ({metrics['efficiency_percent']}%)")
else:
    print("⚠️ Parallel exploration verification failed")
    # Workflow continues regardless (graceful degradation)
```

### Error Handling

All exceptions include context and guidance:
```python
try:
    tracker = AgentTracker(session_file="../../etc/passwd")
except ValueError as e:
    # Error includes: what went wrong, why, and what's expected
    # Example: "Path traversal attempt detected: /etc/passwd"
    print(e)
```

### Test Coverage
- 66+ unit tests (85.7% coverage) in `tests/unit/lib/test_agent_tracker_issue79.py`
- Integration tests for checkpoint verification
- Path resolution from nested subdirectories
- Atomic write pattern verification
- Security validation (path traversal, symlinks, input bounds)

### Used By
- `/implement` command checkpoints (parallel exploration, parallel validation)
- `/implement --batch` for pipeline tracking
- Dogfooding infrastructure in autonomous-dev repo
- Optional checkpoint verification (graceful degradation in user projects)

### Related
- GitHub Issue #79 (Dogfooding bug - tracking infrastructure hardcoded paths)
- GitHub Issue #82 (Optional checkpoint verification with graceful degradation)
- GitHub Issue #45 (Atomic write pattern and security hardening)
- GitHub Issue #165 (Package refactoring - monolithic to modular)
- path_utils.py (Dynamic project root detection)
- security_utils.py (Path validation and input bounds checking)

### Design Patterns
- **Two-tier Design**: Library (core logic) + CLI wrapper (interface)
- **Delegation Pattern**: AgentTracker delegates to specialized manager classes
- **Progressive Enhancement**: Features gracefully degrade if infrastructure unavailable
- **Atomic Writes**: Tempfile + rename for consistency
- **Path Portability**: Uses path_utils instead of hardcoded paths
- **Modular Responsibility**: Each module handles single concern (~100-400 lines)

- Comprehensive docstrings with design patterns

### Classes

#### `SessionTracker`
- **Purpose**: Log agent actions to session file instead of keeping in context
- **Base Class**: Inherits from `StateManager[str]` (Issue #224)
  - Generic type is `str` for markdown content
  - Implements abstract methods: `load_state()`, `save_state()`, `cleanup_state()`
  - Uses inherited helpers: `_validate_state_path()`, `_atomic_write()`, `_get_file_lock()`, `_audit_operation()`
- **Initialization**: `SessionTracker(session_file=None, use_cache=True)`
  - `session_file` (Optional[str]): Path to session file for testing
  - `use_cache` (bool): If True, use cached project root (default: True)
  - If None: Creates/finds session file automatically using path_utils
  - Raises `StateError` if session_file path is invalid or outside project
- **Features**:
  - Auto-detects project root from any subdirectory
  - Creates `docs/sessions/` directory if missing
  - Finds or creates session files with timestamp naming: `YYYYMMDD-HHMMSS-session.md`
  - Path validation via shared validation module
  - Directory permission checking (warns on world-writable)
  - Thread-safe file operations with atomic writes

### Public Methods

#### `log(agent_name, message) -> None`
- **Purpose**: Log agent action to session file
- **Parameters**:
  - `agent_name` (str): Agent identifier (e.g., "researcher", "implementer")
  - `message` (str): Action message (e.g., "Research complete - docs/research/auth.md")
- **Output**:
  - Appends to session file with timestamp
  - Prints confirmation to console
- **Format**: `**HH:MM:SS - agent_name**: message`
- **Example Output**:
  ```
  **14:30:22 - researcher**: Research complete - docs/research/auth.md
  ```

#### `load_state() -> str` (StateManager ABC)
- **Purpose**: Load session markdown content from file
- **Returns**: str - Markdown content of session file
- **Raises**: `StateError` if session file not found or load fails
- **Features**:
  - Thread-safe with inherited file locking
  - Validates file path via `_validate_state_path()`
- **Example**:
  ```python
  tracker = SessionTracker()
  content = tracker.load_state()
  print(content)  # Full markdown session content
  ```

#### `save_state(state: str) -> None` (StateManager ABC)
- **Purpose**: Save session markdown content to file with atomic writes
- **Parameters**: `state` (str) - Markdown content to save
- **Raises**: `StateError` if save fails
- **Features**:
  - Uses inherited atomic write pattern (temp file + rename)
  - Thread-safe with file locking
  - Path validation to prevent CWE-22 (path traversal)
  - Sets restrictive permissions (0o600)
- **Example**:
  ```python
  tracker = SessionTracker()
  content = "# Session Log\n\n**12:00:00 - researcher**: Test\n"
  tracker.save_state(content)
  ```

#### `cleanup_state() -> None` (StateManager ABC)
- **Purpose**: Remove session file from disk
- **Raises**: `StateError` if cleanup fails
- **Features**:
  - Thread-safe with file locking
  - Only removes file if it exists
- **Example**:
  ```python
  tracker = SessionTracker()
  tracker.cleanup_state()
  assert not tracker.session_file.exists()
  ```

### Helper Functions

#### `get_default_session_file() -> Path`
- **Purpose**: Get default session file path with timestamp
- **Returns**: Path object for new session file
- **Format**: `<session_dir>/session-YYYY-MM-DD-HHMMSS.md`
- **Uses**: path_utils.get_session_dir() for portable resolution
- **Example**:
  ```python
  path = get_default_session_file()
  print(path.name)  # session-2025-11-19-143022.md
  ```

### File Format

Session files stored in `docs/sessions/YYYYMMDD-HHMMSS-session.md`:

```markdown
# Session 20251119-143022

**Started**: 2025-11-19 14:30:22

---

**14:30:25 - researcher**: Research complete - docs/research/jwt-patterns.md

**14:35:10 - planner**: Plan complete - docs/design/auth-architecture.md

**14:45:30 - test-master**: Tests written - 12 test cases

**15:02:15 - implementer**: Implementation complete - src/auth/jwt_handler.py
```

### Security Features

#### Path Validation (CWE-22)
- All paths validated via validation module
- Rejects paths outside project directory
- Uses path_utils for consistent resolution
- Audit logging on validation errors

#### Permission Checking (CWE-732)
- Warns if session directory is world-writable
- Checks ownership on POSIX systems
- Gracefully handles Windows (different permission model)

#### Input Validation
- Agent names must match `/^[a-zA-Z0-9_-]+$/` (via validation module)
- Messages limited to reasonable length
- Control characters filtered to prevent log injection

### CLI Wrapper

**File**: `plugins/autonomous-dev/scripts/session_tracker.py`
- **Purpose**: CLI interface for library functionality
- **Design**: Delegates to `plugins/autonomous-dev/lib/session_tracker.py`
- **Usage**: `python plugins/autonomous-dev/scripts/session_tracker.py <agent_name> <message>`
- **Example**: `python plugins/autonomous-dev/scripts/session_tracker.py researcher "Found 3 JWT patterns"`

### Deprecation (Issue #79)

**Deprecated**: `scripts/session_tracker.py` (original location)
- **Reason**: Hardcoded paths fail in user projects and subdirectories
- **Migration**:
  - For CLI: Use `plugins/autonomous-dev/scripts/session_tracker.py` (installed plugin)
  - For imports: Use `from plugins.autonomous-dev.lib.session_tracker import SessionTracker`
  - Existing code continues to work (delegates to library implementation)
  - Will be removed in v4.0.0

### Usage Examples

#### Basic Session Logging
```python
from plugins.autonomous_dev.lib.session_tracker import SessionTracker

# Create tracker (auto-detects project root)
tracker = SessionTracker()

# Log agent actions
tracker.log("researcher", "Found 3 JWT patterns in codebase")
tracker.log("planner", "Architecture designed - see docs/design/auth.md")
tracker.log("test-master", "12 test cases written")
tracker.log("implementer", "Implementation complete - 450 lines of code")
```

#### Testing with Explicit Session File
```python
from pathlib import Path
tracker = SessionTracker(session_file="/tmp/test-session.md")
tracker.log("test-agent", "Testing portable path detection")
```

#### From auto-implement Checkpoints
```bash
# Log from bash (CHECKPOINT 1)
python plugins/autonomous-dev/scripts/session_tracker.py auto-implement "Parallel exploration completed"

# Log from bash (CHECKPOINT 4.1)
python plugins/autonomous-dev/scripts/session_tracker.py auto-implement "Parallel validation completed"
```

### Error Handling

StateError exceptions include context and guidance:
```python
try:
    tracker = SessionTracker(session_file="../../etc/passwd")
except StateError as e:
    # Error includes: what went wrong, why, and what's expected
    # Example: "Path traversal attempt detected: /etc/passwd"
    print(e)

try:
    content = tracker.load_state()
except StateError as e:
    # Handles: file not found, read errors, path validation failures
    print(e)
```

Backward Compatibility:
- Exceptions raised during `__init__` (path validation) may raise exceptions inherited from StateError
- StateError is a subclass of AutonomousDevError for consistent error handling

### Test Coverage
- 30+ unit tests in `tests/unit/lib/test_session_tracker.py`
- Path resolution from nested subdirectories
- Session file creation and appending
- Directory permission checking
- Input validation (agent names, messages)
- Security validation (path traversal, symlinks)

### Used By
- `/implement` command checkpoints (progress tracking)
- `/implement --batch` for feature logging
- Dogfooding infrastructure (session logs in docs/sessions/)
- CI/CD pipelines for audit trails
- Optional checkpoint logging (graceful degradation in user projects)

### Related
- GitHub Issue #79 (Tracking infrastructure hardcoded paths)
- GitHub Issue #82 (Optional checkpoint verification with graceful degradation)
- GitHub Issue #85 (Portable checkpoint implementation)
- GitHub Issue #45 (Atomic write pattern and security hardening)
- path_utils.py (Dynamic project root detection)
- validation.py (Path and input validation)
- agent_tracker.py (Agent execution tracking)

### Design Patterns
- **Two-tier Design**: Library (core logic) + CLI wrapper (interface)
- **Progressive Enhancement**: Features gracefully degrade if unavailable
- **Portable Paths**: Uses path_utils instead of hardcoded paths
- **Non-blocking**: Logging failures don't break workflows
- **StateManager ABC Integration** (Issue #224): Standardized state management
  - Inherits from StateManager[str] for type-safe state operations
  - Delegates file operations to inherited helpers for DRY principle
  - Consistent error handling via StateError exception hierarchy
  - Phase 5 of StateManager migration (after BatchStateManager, UserStateManager, CheckpointManager)

### StateManager ABC Methods

See [abstract_state_manager.py](../plugins/autonomous-dev/lib/abstract_state_manager.py) for implementation details.

**Inherited Helper Methods**:
- `exists() -> bool`: Check if state file exists
- `_validate_state_path(path: Path) -> Path`: Validate path against traversal attacks (CWE-22)
- `_atomic_write(path: Path, content: str, mode: int = 0o600) -> None`: Write with atomicity guarantees
- `_get_file_lock(path: Path) -> threading.RLock`: Get thread-safe lock for file operations
- `_audit_operation(operation: str, details: Dict) -> None`: Log security-relevant operations

---

## Design Pattern

**Progressive Enhancement**: Libraries use string → path → whitelist validation pattern, allowing graceful error recovery

**Non-blocking Enhancements**: Version detection, orphan cleanup, hook activation, parity validation, git automation, issue automation, and brownfield retrofit don't block core operations

**Two-tier Design**:
- Core logic libraries (plugin_updater.py, auto_implement_git_integration.py, brownfield_retrofit.py + 5 phase libraries)
- CLI interface scripts (update_plugin.py, auto_git_workflow.py, align_project_retrofit.py)
- Enables reuse and testing
- Note: /create-issue uses direct gh CLI (no wrapper library)

**Optional Features**: Feature automation and other enhancements are controlled by flags/hooks

## 35. mcp_permission_validator.py — REMOVED

Deleted with the never-executed approval subsystem. The module was built,
tested, shipped to five consumer repositories, and never once executed: the
reachability ratchet measured it UNREACHED, and a scan of 541,492 activity-log
lines resolved every mention of it to a file-read operation rather than a call.

The section number is retained so the numbering of every later entry, and the
anchors that link to them, stay valid.

**What enforces this area now**: Claude Code's native permission rules
(4 allow, 61 deny in `.claude/settings.json`) and
`plugins/autonomous-dev/hooks/unified_pre_tool.py`, which recorded 167 refusals
in the two days before this deletion.

---

## 36. mcp_profile_manager.py (533 lines, v3.37.0)

**Purpose**: Pre-configured security profiles for MCP server operations

**Issue**: #95 (MCP Server Security)

### Enums

#### `ProfileType`

Pre-configured security profiles.

**Values**:
- `DEVELOPMENT` - Most permissive (local development)
- `TESTING` - Moderate restrictions (CI/CD, test environments)
- `PRODUCTION` - Strictest (production automation)

**Methods**:
- `from_string(value: str) -> ProfileType` - Parse string to enum

### Dataclasses

#### `SecurityProfile`

Security profile configuration.

**Attributes**:
- `version: str` - Profile schema version
- `profile: str` - Profile name (development, testing, production)
- `filesystem: Dict[str, List[str]]` - Read/write allowlists
- `shell: Dict[str, Any]` - Command allowlists
- `network: Dict[str, List[str]]` - Domain/IP allowlists
- `environment: Dict[str, List[str]]` - Variable allowlists

**Methods**:
- `from_dict(data: Dict[str, Any]) -> SecurityProfile` - Deserialize from dictionary
- `to_dict() -> Dict[str, Any]` - Serialize to dictionary
- `validate() -> ValidationResult` - Validate profile structure

### Classes

#### `MCPProfileManager`

Manage and generate security profiles.

**Constructor**:
```python
manager = MCPProfileManager()
```

**Methods**:

##### `create_profile(profile_type: ProfileType) -> Dict[str, Any]`
- Generate pre-configured profile
- **Example**:
  ```python
  profile = manager.create_profile(ProfileType.DEVELOPMENT)
  ```

##### `save_profile(profile: Dict[str, Any], output_path: str) -> None`
- Write profile to JSON file
- **Example**:
  ```python
  manager.save_profile(profile, ".mcp/security_policy.json")
  ```

##### `load_profile(input_path: str) -> Dict[str, Any]`
- Read profile from JSON file
- Validates structure on load
- **Example**:
  ```python
  profile = manager.load_profile(".mcp/security_policy.json")
  ```

### Profile Generation Functions

Standalone functions for generating profiles:

```python
from autonomous_dev.lib.mcp_profile_manager import (
    generate_development_profile,
    generate_testing_profile,
    generate_production_profile
)

dev = generate_development_profile()
test = generate_testing_profile()
prod = generate_production_profile()
```

#### `generate_development_profile() -> Dict[str, Any]`

Most permissive profile for local development.

**Permissions**:
- Read: src/**, tests/**, docs/**, *.md, *.json, config files
- Write: src/**, tests/**, docs/**
- Shell: pytest, git, python, python3, pip, npm, make
- Network: All domains (except localhost/private)
- Environment: Safe variables only (PATH, HOME, USER, SHELL, LANG, PWD, TERM)
- Blocks: .env, .git, .ssh, keys, tokens, secrets

#### `generate_testing_profile() -> Dict[str, Any]`

Moderate restrictions for CI/CD and test environments.

**Permissions**:
- Read: src/**, tests/**, config (no docs)
- Write: tests/** only (read-only source)
- Shell: pytest only
- Network: Specific test APIs only
- Environment: Test variables only

#### `generate_production_profile() -> Dict[str, Any]`

Strictest profile for production automation.

**Permissions**:
- Read: Specific paths only (no source)
- Write: logs/**, data/** only
- Shell: Safe read-only commands only
- Network: Specific production APIs only
- Environment: Production config only (no secrets)

### Profile Customization

#### `customize_profile(profile: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]`

Customize profile with override values.

**Example**:
```python
from autonomous_dev.lib.mcp_profile_manager import customize_profile

custom = customize_profile(profile, {
    "filesystem": {
        "read": ["src/**", "config/**"]
    },
    "shell": {
        "allowed_commands": ["pytest", "git", "poetry"]
    }
})
```

**Behavior**:
- Deep merge with profile dict
- Override values replace profile values
- New keys added to profile

### Validation

#### `validate_profile_schema(profile: Dict[str, Any]) -> ValidationResult`

Validate profile structure.

**Checks**:
- Required fields present
- Correct types
- Policy structure matches schema

**Returns**: ValidationResult with approval/denial

### Export

#### `export_profile(profile: Dict[str, Any], output_format: str = "json") -> str`

Export profile to string format.

**Formats**:
- json - JSON string
- yaml - YAML string (if PyYAML available)

### Used By

- `unified_pre_tool.py` hook - Load profiles on startup (Layer 2: MCP Security Validator)
- Setup and initialization scripts

### Related

- GitHub Issue #95 (MCP Server Security)
- [MCP-SECURITY.md](MCP-SECURITY.md) - Comprehensive security guide
- `plugins/autonomous-dev/hooks/unified_pre_tool.py` - Unified hook implementation (Layer 2)
- `plugins/autonomous-dev/hooks/archived/README.md` - Archived hook documentation (Issue #211)
- `.mcp/security_policy.json` - Policy configuration file

---

**For usage examples and integration patterns**: See CLAUDE.md Architecture section and individual command documentation

## 38. auto_approval_engine.py — REMOVED

Deleted with the never-executed approval subsystem. The module was built,
tested, shipped to five consumer repositories, and never once executed: the
reachability ratchet measured it UNREACHED, and a scan of 541,492 activity-log
lines resolved every mention of it to a file-read operation rather than a call.

The section number is retained so the numbering of every later entry, and the
anchors that link to them, stay valid.

**What enforces this area now**: Claude Code's native permission rules
(4 allow, 61 deny in `.claude/settings.json`) and
`plugins/autonomous-dev/hooks/unified_pre_tool.py`, which recorded 167 refusals
in the two days before this deletion.

---

## 39. tool_validator.py (900 lines, v3.40.0)

**Purpose**: Tool call validation with whitelist/blacklist, injection detection, path containment validation, and parameter analysis

**Issue**: #73 (MCP Auto-Approval), #98 (PreToolUse Consolidation)

**New in v3.40.0**: Path extraction and containment validation for destructive shell commands (rm, mv, cp, chmod, chown) - prevents CWE-22 (path traversal) and CWE-59 (symlink attacks) when files are modified.

### Classes

#### `ToolValidator`

Validates MCP tool calls against security policies with path-aware containment validation for destructive commands.

**Methods**:

##### `validate_tool(tool_name: str, params: Dict[str, Any]) -> ValidationResult`

Comprehensive validation of tool calls.

**Parameters**:
- `tool_name` (str): Tool name to validate
- `params` (Dict[str, Any]): Tool parameters

**Returns**: `ValidationResult` dataclass with:
- `valid` (bool): Overall validation result
- `violations` (List[str]): Security violations found
- `severity` (str): "critical", "high", "medium", "low", "none"
- `recommendations` (List[str]): How to fix violations

**Validation Checks**:
1. **Whitelist Check** - Tool must be in approved list
2. **Blacklist Check** - Tool must not be explicitly denied
3. **Path Traversal** - Detect `..`, `/etc/passwd`, symlink attacks
4. **Injection Patterns** - Detect shell metacharacters, command chaining
5. **Path Containment** (NEW v3.40.0) - Validate extracted paths are within project boundaries
6. **Sensitive Files** - Block access to `.env`, `.ssh`, secrets
7. **SSRF Detection** - Detect localhost, private IPs, metadata services
8. **Parameter Size** - Reject suspiciously large parameters

**Example**:
```python
from tool_validator import ToolValidator, ValidationResult

validator = ToolValidator()

# Valid tool call
result = validator.validate_tool("Read", {"file_path": "src/main.py"})
assert result.valid == True
assert result.severity == "none"

# Invalid - path traversal
result = validator.validate_tool(
    "Read",
    {"file_path": "../../.env"}
)
assert result.valid == False
assert result.severity == "critical"
assert any("path traversal" in v for v in result.violations)

# Valid - rm within project boundaries
result = validator.validate_bash_command("rm src/temp.py")
assert result.approved == True

# Invalid - rm outside project
result = validator.validate_bash_command("rm ../../../etc/passwd")
assert result.approved == False
assert "path traversal" in result.reason
```

##### `_extract_paths_from_command(command: str) -> List[str]` (NEW v3.40.0)

Extract file paths from destructive shell commands for containment validation.

**Purpose**: Identifies files that will be modified by rm/mv/cp/chmod/chown commands so they can be validated against project boundaries.

**Supported Commands**:
- `rm` - Remove files/directories
- `mv` - Move files/directories
- `cp` - Copy files/directories
- `chmod` - Change file permissions
- `chown` - Change file ownership

**Parameters**:
- `command` (str): Shell command string to parse

**Returns**: List of file paths extracted from command, or empty list if:
- Command is non-destructive (ls, cat, etc.)
- Command contains wildcards (asterisk or question mark) - cannot validate at static analysis time
- Command is empty or malformed (unclosed quotes)

**Behavior**:
- Uses shlex.split() for proper quote/escape handling
- Filters out flags (arguments starting with dash)
- Skips mode/ownership arguments for chmod/chown
- Gracefully handles malformed commands (returns empty list)

**Security Notes**:
- Wildcard commands return empty list (conservative approach - cannot validate)
- Symlinks are resolved and validated separately by _validate_path_containment()
- Only destructive commands checked (non-destructive commands skip validation)

**Example**:
```python
validator = ToolValidator()

# Extract paths from rm command
paths = validator._extract_paths_from_command("rm file.txt")
# Returns: ["file.txt"]

# Extract multiple paths from mv
paths = validator._extract_paths_from_command("mv src.txt dst.txt")
# Returns: ["src.txt", "dst.txt"]

# Wildcards skip validation (conservative)
paths = validator._extract_paths_from_command("rm *.txt")
# Returns: []  # Cannot validate wildcard expansion

# Non-destructive commands skip validation
paths = validator._extract_paths_from_command("ls file.txt")
# Returns: []  # No containment validation needed
```

##### `_validate_path_containment(paths: List[str], project_root: Path) -> Tuple[bool, Optional[str]]` (NEW v3.40.0)

Validate that all paths are contained within project boundaries.

**Purpose**: Prevents CWE-22 (path traversal) and CWE-59 (symlink attacks) by ensuring destructive operations only affect files within the project.

**Validation Checks**:
- **Path Traversal** - Reject traversal style escapes like ../../../etc/passwd
- **Absolute Paths** - Reject /etc/passwd outside project
- **Symlinks** - Reject symlinks pointing outside project
- **Home Directory** - Reject ~/ expansion (except whitelisted ~/.claude/)
- **Invalid Characters** - Reject paths with null bytes or newlines

**Parameters**:
- `paths` (List[str]): File paths to validate
- `project_root` (Path): Project root directory (containment boundary)

**Returns**: Tuple of:
- (True, None) - All paths valid and contained
- (False, error_message) - First invalid path with description

**Special Cases**:
- **Empty list**: Always valid (no paths to validate)
- **~/.claude/**: Whitelisted for Claude Code system files
- **Other ~/ paths**: Rejected (outside project boundaries)

**Security Features**:
- Checks for null bytes and newlines - injection risk
- Expands tilde to absolute path before validation
- Resolves symlinks and validates target location
- Uses is_relative_to() for containment check (Python 3.9+) with fallback for 3.8
- Distinguishes between path traversal vs absolute path violations in error messages

**Example**:
```python
validator = ToolValidator()
project_root = Path("/tmp/project")  # Example project root

# Valid - relative path within project
is_valid, error = validator._validate_path_containment(
    ["src/main.py"],
    project_root
)
assert is_valid == True
assert error is None

# Invalid - path traversal attempt
is_valid, error = validator._validate_path_containment(
    ["../../../etc/passwd"],
    project_root
)
assert is_valid == False
assert "path traversal" in error

# Invalid - absolute path outside project
is_valid, error = validator._validate_path_containment(
    ["/etc/passwd"],
    project_root
)
assert is_valid == False
assert "absolute path" in error and "outside" in error

# Invalid - symlink to outside
is_valid, error = validator._validate_path_containment(
    ["link_to_etc"],
    project_root
)
assert is_valid == False
assert "symlink" in error

# Whitelisted - .claude directory
is_valid, error = validator._validate_path_containment(
    ["~/.claude/config.json"],
    project_root
)
assert is_valid == True

# Invalid - other home directory paths
is_valid, error = validator._validate_path_containment(
    ["~/.ssh/id_rsa"],
    project_root
)
assert is_valid == False
assert "home directory" in error
```

### Integration with validate_bash_command()

When validate_bash_command() processes a command:
1. Checks command against blacklist
2. NEW v3.40.0: Extracts paths from destructive commands
3. NEW v3.40.0: Validates paths are contained within project boundaries
4. Checks for command injection patterns
5. Checks against whitelist
6. Denies by default (conservative approach)

This ensures commands like rm ../../../etc/passwd are blocked before execution, even if they pass other validation layers.

### Related

- GitHub Issue #73 (MCP Auto-Approval)
- GitHub Issue #98 (PreToolUse Consolidation)
- docs/TOOL-AUTO-APPROVAL.md - Security validation documentation
- CWE-22: Improper Limitation of a Pathname to a Restricted Directory
- CWE-59: Improper Link Resolution Before File Access

---

## 40. unified_pre_tool_use.py (467 lines, v3.38.0)

**Purpose**: Library-based PreToolUse hook implementation combining auto-approval and security validation

**Issue**: #95 (MCP Security), #98 (PreToolUse Consolidation)

### Main Class

#### `UnifiedPreToolUseHook`

Main hook handler that coordinates auto-approval and security validation.

**Methods**:

##### `on_pre_tool_use(tool_call: Dict[str, Any]) -> Dict[str, Any]`

Claude Code PreToolUse lifecycle hook handler.

**Parameters**:
- `tool_call` (Dict[str, Any]): Tool call with `tool_name` and `tool_input`

**Returns**: Hook response dict with:
- `hookSpecificOutput`: Dict containing:
  - `hookEventName`: "PreToolUse"
  - `permissionDecision`: "allow" or "deny"
  - `permissionDecisionReason`: Explanation

**Workflow**:
1. Parse tool call from JSON input
2. Run auto-approval engine
3. If not auto-approved, run security validation
4. Log decision to audit trail
5. Return decision to Claude Code

**Example**:
```python
from unified_pre_tool_use import UnifiedPreToolUseHook

hook = UnifiedPreToolUseHook()

# Tool call
tool_call = {
    "tool_name": "Bash",
    "tool_input": {"command": "pytest tests/"}
}

# Get decision
response = hook.on_pre_tool_use(tool_call)
assert response["hookSpecificOutput"]["permissionDecision"] == "allow"
```

### Integration

This library is used by both:
1. `plugins/autonomous-dev/hooks/pre_tool_use.py` - Standalone shell script wrapper
2. Direct Python imports in custom hooks

### Related

- GitHub Issue #95 (MCP Server Security)
- GitHub Issue #98 (PreToolUse Consolidation)
- `tool_validator.py` - Security validation
- `plugins/autonomous-dev/hooks/pre_tool_use.py` - Standalone wrapper
- `docs/TOOL-AUTO-APPROVAL.md` - Usage guide
---

## 41. settings_merger.py (v3.39.0, extended Issue #944)

**Purpose**: Merge template settings.local.json with user settings while preserving customizations

**Issue**: #98 (Settings Merge on Marketplace Sync)

### Main Class

#### `SettingsMerger`

Handles merging template settings with user settings during marketplace sync operations.

**Constructor**:
```python
def __init__(self, project_root: str)
```

**Parameters**:
- `project_root` (str): Project root directory for path validation

**Methods**:

##### `merge_settings(template_path: Path, user_path: Path, write_result: bool = True) -> MergeResult`

Merge template settings with user settings, preserving customizations.

**Parameters**:
- `template_path` (Path): Path to template settings.local.json
- `user_path` (Path): Path to user settings.local.json
- `write_result` (bool): Whether to write merged settings (False for dry-run)

**Returns**: `MergeResult` dataclass with:
- `success` (bool): Whether merge succeeded
- `message` (str): Human-readable result message
- `settings_path` (Optional[str]): Path to merged settings file
- `hooks_added` (int): Number of hooks added from template
- `hooks_preserved` (int): Number of existing hooks preserved
- `details` (Dict[str, Any]): Additional context (errors, warnings)

**Workflow**:
1. Validate both paths (security: CWE-22, CWE-59)
2. Read template and user settings files
3. Deep merge dictionaries (nested objects preserved)
4. Merge hooks by lifecycle event (avoid duplicates)
5. Atomic write to user path (secure permissions 0o600)
6. Audit log the operation

**Example**:
```python
from autonomous_dev.lib.settings_merger import SettingsMerger

merger = SettingsMerger(project_root="/path/to/project")

# Merge template with user settings
result = merger.merge_settings(
    template_path=Path("templates/settings.local.json"),
    user_path=Path(".claude/settings.local.json"),
    write_result=True
)

if result.success:
    print(f"Merged {result.hooks_added} new hooks")
    print(f"Preserved {result.hooks_preserved} existing hooks")
else:
    print(f"Merge failed: {result.message}")
```

### Data Classes

#### `MergeResult`

Result of settings merge operation.

**Attributes**:
- `success` (bool): Whether merge succeeded
- `message` (str): Human-readable result message
- `settings_path` (Optional[str]): Path to merged settings file (None if merge failed)
- `hooks_added` (int): Number of hooks added from template
- `hooks_preserved` (int): Number of existing hooks preserved
- `details` (Dict[str, Any]): Additional result details (errors, warnings)

### Security Features

**Path Validation**:
- Validates both template and user paths against project root
- Blocks path traversal attacks (CWE-22)
- Rejects symlinks and suspicious paths (CWE-59)
- Uses `security_utils.validate_path()` for comprehensive validation

**Atomic Writes**:
- Creates temp file in same directory as target
- Sets secure permissions (0o600 - user read/write only)
- Atomic rename to target path (POSIX-safe)
- Cleans up temp files on error

**Audit Logging**:
- All operations logged via `security_utils.audit_log()`
- Tracks merge success/failure with context
- Records path validation decisions
- Enables security audits and compliance

**Deep Merge Logic**:
- Nested dictionaries merged recursively (preserves structure)
- Lists replaced, not merged (prevents duplicate items)
- Special handling for hooks: merge by lifecycle event
- User customizations always preserved

### Module-Level Constants (Issue #944)

#### `CANONICAL_GLOBAL_HOOKS`

```python
CANONICAL_GLOBAL_HOOKS: Tuple[str, ...]
```

Tuple of 7 canonical hook command strings that MUST NOT appear in per-repo `settings.json` templates because they are already registered in `~/.claude/settings.json` by `configure_global_settings.py`. Used by `strip_global_duplicates()` as the default canonical set. Variants with extra arguments (custom env vars, `&& echo` suffixes) are not considered canonical and are preserved.

### Module-Level Functions (Issue #944)

#### `extract_hook_refs(settings: Dict[str, Any]) -> set`

Extract all hook file references (Python basenames) from a settings dict. Walks the `settings["hooks"]` tree and collects every `.py` hook filename referenced in a command string.

**Parameters**:
- `settings` (Dict): Parsed settings.json content.

**Returns**: Set of hook filenames (basename only, with `.py` extension), e.g. `{"unified_prompt_validator.py", "plan_gate.py"}`.

#### `strip_global_duplicates(settings, *, canonical=None, source_label="") -> Tuple[Dict, List[ValidationIssue]]`

Remove canonical global-hook entries from a per-repo settings dict. Returns a filtered copy of the settings and a list of `ValidationIssue` findings (severity `"info"`, category `"hook-dedup"`) for each removed entry.

**Parameters**:
- `settings` (Dict): Parsed settings dict to filter.
- `canonical` (Iterable[str] | None): Set of canonical command strings to strip. Defaults to `CANONICAL_GLOBAL_HOOKS` when `None`.
- `source_label` (str): Label used in `ValidationIssue.file_path` for audit context.

**Returns**: Tuple of `(filtered_settings_dict, list_of_ValidationIssue)`. The original dict is not mutated. Matcher groups whose entire `hooks` array is stripped are removed; lifecycle events left empty are omitted from `filtered_settings["hooks"]`.

**Idempotent**: Running on already-stripped settings returns the same dict with an empty findings list.

### Integration with sync_dispatcher.py

Used by `SyncDispatcher.sync_marketplace()` to automatically merge PreToolUse hooks:

**Workflow**:
1. Marketplace sync starts
2. Locate plugin's template settings.local.json
3. Create SettingsMerger instance
4. Call `merge_settings()` with template and user paths
5. Record merge result in `SyncResult.settings_merged`
6. Continue sync (non-blocking if merge fails)

**Example**:
```python
from autonomous_dev.lib.sync_dispatcher import SyncDispatcher

dispatcher = SyncDispatcher(project_root="/path/to/project")
result = dispatcher.sync_marketplace(installed_plugins_path)

if result.settings_merged and result.settings_merged.success:
    print(f"Settings synced: {result.settings_merged.hooks_added} hooks added")
```

### Error Handling

All errors are graceful and non-blocking:

**Template Errors**:
- Template path validation fails: Return MergeResult with `success=False`
- Template file not found: Return MergeResult with `success=False`
- Template JSON invalid: Return MergeResult with `success=False`

**User Settings Errors**:
- User path validation fails: Return MergeResult with `success=False`
- User settings JSON invalid: Return MergeResult with `success=False`
- User settings file missing: Create new file from template (success=True)

**Write Errors**:
- Cannot create parent directories: Return MergeResult with `success=False`
- File write fails: Return MergeResult with `success=False` (temp file cleaned up)
- Permission denied: Return MergeResult with `success=False`

**Note**: Marketplace sync continues even if settings merge fails (non-blocking design)

### Testing

**Test Coverage**: 25 tests (15 core + 4 edge cases + 3 security + 3 integration)
- Core functionality tests for merge operations
- Edge case handling (missing files, invalid JSON, path errors)
- Security tests (path traversal, symlink attacks, validation)
- Integration tests with sync_dispatcher

### Related

- GitHub Issue #98 (Settings Merge on Marketplace Sync)
- `sync_dispatcher.py` - Uses SettingsMerger in sync_marketplace() method
- `security_utils.py` - Provides path validation and audit logging
- `docs/TOOL-AUTO-APPROVAL.md` - PreToolUse hook configuration reference
- `plugins/autonomous-dev/templates/settings.local.json` - Default template

---

## 42. staging_manager.py (340 lines, v3.41.0+)

**Purpose**: Manage staging directory for GenAI-first installation system

**Issue**: #106 (GenAI-first installation system)

### Overview

The staging manager handles staged plugin files during the GenAI-first installation workflow. It validates staging directories, lists files with metadata, detects conflicts with target installations, and manages cleanup operations.

**Key Features**:
- Staging directory validation and initialization
- File listing with SHA256 hashes and metadata
- Conflict detection (file exists in both locations with different content)
- Security validation (path traversal prevention, symlink detection)
- Selective and full cleanup operations

### Main Class

#### `StagingManager`

Manages a staging directory for plugin files.

**Constructor**:
```python
def __init__(self, staging_dir: Path | str)
```

**Parameters**:
- `staging_dir` (Path | str): Path to staging directory (created if doesn't exist)

**Raises**:
- `ValueError`: If path is a file (not a directory)

**Methods**:

##### `list_files() -> List[Dict[str, Any]]`

List all files in staging directory with metadata.

**Returns**: List of dicts with keys:
- `path` (str): Relative path from staging directory (normalized)
- `size` (int): File size in bytes
- `hash` (str): SHA256 hex digest

##### `get_file_hash(relative_path: str) -> Optional[str]`

Get SHA256 hash of a specific file.

**Parameters**:
- `relative_path` (str): Relative path from staging directory

**Returns**: SHA256 hex digest or None if file not found

**Raises**:
- `ValueError`: If path contains traversal or symlinks

##### `detect_conflicts(target_dir: Path | str) -> List[Dict[str, Any]]`

Detect conflicts between staged files and target directory.

A conflict occurs when:
- File exists in both locations
- File content differs (different hashes)

**Parameters**:
- `target_dir` (Path | str): Target directory to compare against

**Returns**: List of conflict dicts with file, reason, staging_hash, target_hash

##### `cleanup() -> None`

Remove all files and directories from staging directory.

##### `cleanup_files(file_paths: List[str]) -> None`

Remove specific files from staging directory.

**Parameters**:
- `file_paths` (List[str]): Relative paths to remove

##### `is_secure() -> bool`

Check if staging directory has secure permissions.

**Returns**: True if readable and writable

##### `validate_path(relative_path: str) -> None`

Validate path for security issues.

**Raises**:
- `ValueError`: If path contains traversal (..), is absolute, or is a symlink

### Security Features

**Path Traversal Prevention**:
- Blocks paths containing `..`
- Rejects absolute paths
- Validates paths are within staging directory (CWE-22)

**Symlink Detection**:
- Prevents symlink-based attacks (CWE-59)
- Validates resolved path is within staging directory

**File Hashing**:
- SHA256 for content comparison
- Enables conflict detection without loading full file contents

### Testing

**Test Coverage**: 18 tests
- Directory initialization and validation
- File listing with correct metadata
- Conflict detection (same content, different content, missing files)
- Path traversal prevention (.. attempts, absolute paths)
- Symlink detection and rejection
- Cleanup operations (full and selective)
- Security permission checks

### Related

- GitHub Issue #106 (GenAI-first installation system)
- `protected_file_detector.py` - Identifies files to preserve during installation
- `installation_analyzer.py` - Analyzes installation type and strategy
- `install_audit.py` - Audit logging for installation operations
- `copy_system.py` - Performs actual file copying to target

---

---

## 47. settings_generator.py (749 lines, v3.43.0+)

**Purpose**: Generate settings.local.json with specific command patterns and comprehensive deny list

**Issue**: #115 (Settings Generator - NO wildcards, specific patterns only)

### Overview

The settings generator creates `.claude/settings.local.json` with security-first design:
- **Specific command patterns only** - NO wildcards like `Bash(*)`
- **Comprehensive deny list** - Blocks dangerous operations (rm -rf, sudo, eval, etc.)
- **Command auto-discovery** - Scans `plugins/autonomous-dev/commands/*.md`
- **User customization preservation** - Merges with existing settings during upgrades
- **Atomic writes** - Secure permissions (0o600)

**Key Features**:
- Generates specific patterns: `Bash(git:*)`, `Bash(pytest:*)`, `Bash(python:*)`
- Auto-discovers slash commands from plugin directory
- Preserves user customizations during marketplace sync
- Secure file operations with path validation
- Comprehensive audit logging

### Main Class

#### `SettingsGenerator`

Generates settings.local.json with command-specific patterns and security controls.

**Constructor**:
```python
def __init__(self, plugin_dir: Path)
```

**Parameters**:
- `plugin_dir` (Path): Path to plugin directory (plugins/autonomous-dev)

**Raises**:
- `SettingsGeneratorError`: If plugin_dir or commands/ directory not found

**Attributes**:
- `plugin_dir` (Path): Plugin root directory
- `commands_dir` (Path): Commands directory (plugin_dir/commands)
- `discovered_commands` (List[str]): Auto-discovered command names
- `_validated` (bool): Whether initialization succeeded

**Methods**:

##### `discover_commands() -> List[str]`

Discover slash commands from `plugins/autonomous-dev/commands/*.md` files.

**Returns**: List of command names (without leading slash)

**Example**:
```python
generator = SettingsGenerator(Path("plugins/autonomous-dev"))
commands = generator.discover_commands()
# Returns: ['auto-implement', 'batch-implement', 'align-project', ...]
```

**Validation**:
- Command names must match pattern: `^[a-z][a-z0-9-]*$`
- Invalid names logged and skipped
- Prevents command injection attacks

##### `build_command_patterns() -> List[str]`

Build allow patterns from discovered commands and safe operations.

**Returns**: List of allow patterns

**Includes**:
- **File operations**: `Read(**)`, `Edit(**)`, `Grep(**)` — plus the bare tool names `Read`/`Write`/`Edit`/`Glob`/`Grep`. No path-scoped `Write(**)` or `Glob(**)` is emitted: Claude Code never consults those (Issue #1409, see note under `build_deny_list()`).
- **Safe Bash patterns**: `Bash(git:*)`, `Bash(python:*)`, `Bash(pytest:*)`, `Bash(pip:*)`
- **Discovered commands**: `Task(researcher)`, `Task(planner)`, etc.
- **Standalone tools**: `Task`, `WebFetch`, `WebSearch`, `mcp__searxng__search`, `mcp__searxng__fetch`, `TodoWrite`, `NotebookEdit` (searxng entries added so a template-level searxng permission is not undone by this GENERATED list — the 8th of the 8 settings surfaces)

**Example Output**:
```python
[
    "Read(**)",
    "Edit(**)",
    "Bash(git:*)",
    "Bash(pytest:*)",
    "Task(researcher)",
    "Task(planner)",
    ...
]
```

##### `build_deny_list() -> List[str]` (static method)

Build comprehensive deny list of dangerous operations.

**Returns**: List of deny patterns

**Blocks**:
- **Destructive operations**: `Bash(rm:-rf*)`, `Bash(shred:*)`, `Bash(dd:*)`
- **Privilege escalation**: `Bash(sudo:*)`, `Bash(chmod:*)`, `Bash(chown:*)`
- **Code execution**: `Bash(eval:*)`, `Bash(exec:*)`, `Bash(*|*sh*)`
- **Network tools**: `Bash(nc:*)`, `Bash(*curl *|*sh*)`
- **Dangerous git**: `Bash(*git *--force*)`, `Bash(*git *reset*--hard*)`
- **Package publishing**: `Bash(npm:publish*)`, `Bash(pip:upload*)`
- **Sensitive files**: `Read(./.env)`, `Read(~/.ssh/**)`, `Edit(//etc/**)`

**Note** (Issue #1409): `DEFAULT_DENY_LIST` path-scoped file rules use `Edit(<path>)`, not `Write(<path>)` — Claude Code's file-permission matcher only honors `Edit(path)` rules for the file-editing tools (Write/Edit/NotebookEdit); `Write(path)` rules are silently ignored (a no-op deny). Absolute system paths (`/etc/**`, `/System/**`, `/usr/**`, `/root/**`) use a doubled leading slash (`//etc/**`) so the pattern anchors to the filesystem root rather than matching relative to the working directory. `Read(...)` rules and bare tool allows (`"Write"`, `"Edit"`) are unaffected. Issue #1486 briefly reversed this — it re-added a `Write(<path>)` companion for every `Edit(<path>)` rule on the premise that Edit and Write are distinct path grants — and that reversal has itself now been reversed against the primary source (Claude Code permissions docs), restoring the #1409 behaviour; the `add_write_companions()` helper it introduced is deleted.

**Example**:
```python
deny_list = SettingsGenerator.build_deny_list()
# Static method - no instance needed
```

##### `generate_settings(merge_with: Optional[Dict] = None) -> Dict`

Generate complete settings dictionary with patterns and metadata.

**Parameters**:
- `merge_with` (Optional[Dict]): Existing settings to merge with (preserves user customizations)

**Returns**: Settings dictionary ready for JSON serialization

**Structure**:
```python
{
    "permissions": {
        "allow": [...],
        "deny": [...]
    },
    "hooks": {...},  # Preserved from merge_with
    "generated_by": "autonomous-dev",
    "version": "1.0.0",
    "timestamp": "2025-12-12T10:30:00Z"
}
```

##### `write_settings(output_path: Path, merge_existing: bool = False, backup: bool = False) -> GeneratorResult`

Write settings.local.json to disk with optional merge and backup.

**Parameters**:
- `output_path` (Path): Path to write settings.local.json
- `merge_existing` (bool): Whether to merge with existing settings (preserves customizations)
- `backup` (bool): Whether to backup existing file before overwrite

**Returns**: `GeneratorResult` dataclass

**Workflow**:
1. Validate output path (security checks)
2. Create .claude/ directory if missing (with secure permissions)
3. Backup existing file if requested
4. Read and merge with existing settings if requested
5. Generate new settings dictionary
6. Atomic write with secure permissions (0o600)
7. Audit log the operation

**Example**:
```python
from pathlib import Path
from autonomous_dev.lib.settings_generator import SettingsGenerator

generator = SettingsGenerator(Path("plugins/autonomous-dev"))

# Fresh install
result = generator.write_settings(
    output_path=Path(".claude/settings.local.json")
)

# Upgrade with merge and backup
result = generator.write_settings(
    output_path=Path(".claude/settings.local.json"),
    merge_existing=True,
    backup=True
)

if result.success:
    print(f"Settings written: {result.patterns_added} patterns")
    print(f"Preserved: {result.patterns_preserved} user patterns")
```


##### `validate_permission_patterns(settings: Dict) -> ValidationResult` (v3.44.0+, Issue #114)

Validate permission patterns in settings for dangerous wildcards and missing deny list.

**Parameters**:
- `settings` (Dict): Settings dictionary to validate

**Returns**: `ValidationResult` dataclass with detected issues

**Detects**:
- **Bash(*) wildcard** → severity "error" (too permissive, approves all Bash commands)
- **Bash(:*) wildcard** → severity "warning" (rare edge case, usually unintended)
- **Missing deny list** → severity "error" (no protection against dangerous commands)
- **Empty deny list** → severity "error" (no protection against dangerous commands)

**Example**:
```python
from settings_generator import validate_permission_patterns

# Settings with dangerous patterns
settings = {
    "permissions": {
        "allow": ["Bash(*)", "Read(**)"],
        "deny": []
    }
}

result = validate_permission_patterns(settings)
if not result.valid:
    for issue in result.issues:
        print(f"{issue.severity.upper()}: {issue.description}")
        # ERROR: Dangerous wildcard pattern detected: Bash(*)
        # ERROR: Deny list is empty - no protection against dangerous commands

# Clean settings
good_settings = {
    "permissions": {
        "allow": ["Bash(git:*)", "Read(**)"],
        "deny": ["Bash(rm:-rf*)", "Bash(sudo:*)"]
    }
}

result = validate_permission_patterns(good_settings)
print(result.valid)  # True
```

**Related**: GitHub Issue #114 (Permission validation during updates)

##### `fix_permission_patterns(user_settings: Dict, template_settings: Optional[Dict] = None) -> Dict` (v3.44.0+, Issue #114)

Fix permission patterns while preserving user customizations.

**Parameters**:
- `user_settings` (Dict): User's existing settings to fix
- `template_settings` (Optional[Dict]): Template settings (unused, for compatibility)

**Returns**: Fixed settings dictionary

**Raises**:
- `ValueError`: If user_settings is None or not a dictionary

**Process**:
1. Preserve user hooks (don't touch)
2. Preserve valid custom allow patterns (non-wildcard patterns)
3. Replace wildcards with specific patterns (Bash(*) → Bash(git:*), Bash(pytest:*), etc.)
4. Add comprehensive deny list if missing
5. Validate result

**Example**:
```python
from settings_generator import fix_permission_patterns

# User settings with dangerous wildcards
user_settings = {
    "permissions": {
        "allow": ["Bash(*)", "MyCustomPattern"],  # Has wildcard + custom
        "deny": []
    },
    "hooks": {
        "my_custom_hook": "path/to/hook.py"
    }
}

# Fix patterns
fixed = fix_permission_patterns(user_settings)

# Result preserves customizations:
# - "MyCustomPattern" kept (valid custom pattern)
# - "Bash(*)" replaced with specific patterns
# - Deny list added
# - Hooks preserved
print(fixed["permissions"]["allow"])
# ['MyCustomPattern', 'Bash(git:*)', 'Bash(pytest:*)', 'Read(**)', ...]

print(fixed["hooks"])
# {'my_custom_hook': 'path/to/hook.py'}  # Preserved!
```

**Preservation Logic**:
- **Hooks**: Always preserved (user customization)
- **Valid patterns**: Preserved if not Bash(*) or Bash(:*)
- **Wildcards**: Replaced with safe specific patterns
- **Deny list**: Added if missing (50+ dangerous patterns)

**Related**: GitHub Issue #114 (Permission fixing during updates)

##### `merge_global_settings(global_path: Path, template_path: Path, fix_wildcards: bool = True, create_backup: bool = True) -> Dict[str, Any]` (v3.46.0+, Issue #117)

Merge global settings preserving user customizations while fixing broken patterns.

**Purpose**: Merge template settings with existing user settings, fixing broken Bash(:*) patterns while preserving user hooks and custom patterns. Used during plugin installation/update to safely merge new patterns.

**Parameters**:
- `global_path` (Path): Path to global settings file (~/.claude/settings.json)
- `template_path` (Path): Path to template file (plugins/autonomous-dev/config/global_settings_template.json)
- `fix_wildcards` (bool): Whether to fix broken wildcard patterns (default: True)
- `create_backup` (bool): Whether to create backup before modification (default: True)

**Returns**: Merged settings dictionary ready for use

**Raises**:
- `SettingsGeneratorError`: If template not found, template invalid JSON, or write fails

**Process**:
1. Validate template exists and is valid JSON
2. Read existing user settings from global_path (if exists)
3. Detect broken patterns in user settings (Bash(:*))
4. Fix broken patterns: Bash(:*) to [Bash(git:*), Bash(python:*), ...]
5. Deep merge: template patterns + user patterns (union)
6. Preserve user hooks completely (never modified)
7. Backup existing file before writing (if create_backup=True)
8. Write merged settings atomically with secure permissions
9. Audit log all operations

**Merge Strategy**:
- **Template**: Source of truth for safe patterns
- **User settings**: Provides customizations and valid patterns
- **Merge result**: Union of all patterns (template + user)
- **User hooks**: Always preserved unchanged
- **Wildcard fix**: Broken patterns replaced, valid patterns kept

**Example**:
```python
from pathlib import Path
from autonomous_dev.lib.settings_generator import SettingsGenerator

generator = SettingsGenerator(Path("plugins/autonomous-dev"))

# Merge global settings with user customizations
merged_settings = generator.merge_global_settings(
    global_path=Path.home() / ".claude" / "settings.json",
    template_path=Path("plugins/autonomous-dev/config/global_settings_template.json"),
    fix_wildcards=True,
    create_backup=True
)

print(f"Merged settings: {merged_settings}")
print(f"Patterns available: {len(merged_settings.get('allowedTools', {}).get('Bash', {}).get('allow_patterns', []))} allows")
```

**Backup Behavior**:
- Creates ~/.claude/settings.json.backup before modifying existing file
- Only creates backup if file exists and will be modified
- Old backup automatically replaced (one backup per merge)
- Corrupted files backed up as .json.corrupted with automatic regeneration

**Error Recovery**:
- **Missing template**: Raises SettingsGeneratorError with helpful message
- **Invalid template JSON**: Raises SettingsGeneratorError with JSON error details
- **Permission denied**: Raises PermissionError (allows testing/handling in caller)
- **Write failure**: Cleans up temp file and raises SettingsGeneratorError
- **Corrupted user file**: Creates .json.corrupted backup and starts fresh

**Security**:
- Atomic writes: Tempfile in same directory + atomic rename prevents corruption
- Secure permissions: 0o600 (user read/write only)
- Path validation: All paths validated against CWE-22 (path traversal), CWE-59 (symlinks)
- Audit logging: All operations logged with context

**Related**: GitHub Issue #117 (Global Settings Configuration - Merge Broken Patterns)

### Data Classes (Issue #114)

#### `PermissionIssue` (v3.44.0+)

Details about a detected permission issue.

**Attributes**:
- `issue_type` (str): Type of issue (wildcard_pattern, missing_deny_list, empty_deny_list, outdated_pattern)
- `description` (str): Human-readable description of the issue
- `pattern` (str): Pattern affected by this issue (empty string if N/A)
- `severity` (str): Severity level ("warning" or "error")

**Example**:
```python
issue = PermissionIssue(
    issue_type="wildcard_pattern",
    description="Dangerous wildcard pattern detected: Bash(*)",
    pattern="Bash(*)",
    severity="error"
)
```

#### `ValidationResult` (v3.44.0+)

Result of permission validation.

**Attributes**:
- `valid` (bool): Whether validation passed (True if no issues)
- `issues` (List[PermissionIssue]): List of detected issues
- `needs_fix` (bool): Whether fixes should be applied

**Example**:
```python
from settings_generator import validate_permission_patterns

settings = {"permissions": {"allow": ["Bash(*)"], "deny": []}}
result = validate_permission_patterns(settings)

if not result.valid:
    print(f"Found {len(result.issues)} issues:")
    for issue in result.issues:
        print(f"  - [{issue.severity}] {issue.description}")
    if result.needs_fix:
        print("Automatic fix available via fix_permission_patterns()")
```


### Data Classes

#### `GeneratorResult`

Result of settings generation operation.

**Attributes**:
- `success` (bool): Whether generation succeeded
- `message` (str): Human-readable result message
- `settings_path` (Optional[str]): Path to generated settings file (None if failed)
- `patterns_added` (int): Number of new patterns added
- `patterns_preserved` (int): Number of user patterns preserved (upgrade only)
- `denies_added` (int): Number of deny patterns added
- `details` (Dict[str, Any]): Additional result details

### Security Features

**NO Wildcards**:
- Never uses `Bash(*)` (too permissive)
- Always uses specific patterns: `Bash(git:*)`, `Bash(pytest:*)`
- Prevents accidental approval of dangerous commands

**Comprehensive Deny List**:
- 50+ deny patterns blocking dangerous operations
- Covers CWE-78 (command injection), privilege escalation, data destruction
- Blocks piping to shell: `Bash(*|*sh*)`, `Bash(*|*bash*)`
- Prevents command substitution patterns

**Path Validation**:
- Validates output path against project root (CWE-22)
- Rejects symlinks and suspicious paths (CWE-59)
- Uses `security_utils.validate_path()` for comprehensive validation

**Atomic Writes**:
- Creates temp file in same directory as target
- Sets secure permissions (0o600 - user read/write only)
- Atomic rename to target path (POSIX-safe)
- Cleans up temp files on error

**Audit Logging**:
- All operations logged via `security_utils.audit_log()`
- Tracks generation success/failure with context
- Records merge operations and pattern counts
- Enables security audits and compliance

### Integration

**Used By**:
- `/setup` command - Fresh installation
- `/sync` command - Marketplace sync with merge
- Installation system - Auto-generates during plugin install

**Workflow in Installation**:
1. Plugin installed to `~/.config/claude/installed_plugins/`
2. SettingsGenerator discovers commands from plugin
3. Generates settings.local.json with specific patterns
4. Merges with existing user settings (preserves customizations)
5. Writes to `.claude/settings.local.json` with secure permissions

### Testing

**Test Coverage**: 85 tests (56 unit + 29 integration)

**Unit Tests** (`tests/unit/lib/test_settings_generator.py`):
- Command discovery and validation (12 tests)
- Pattern building (allow and deny lists) (8 tests)
- Settings generation and merge logic (15 tests)
- Path validation and security (10 tests)
- Error handling and edge cases (11 tests)

**Integration Tests** (`tests/integration/test_install_settings_generation.py`):
- End-to-end settings generation (8 tests)
- Merge with existing settings (7 tests)
- Backup and rollback scenarios (6 tests)
- Permission and security validation (8 tests)

### Related

- GitHub Issue #115 (Settings Generator - NO wildcards)
- `settings_merger.py` - Merges template settings during marketplace sync
- `security_utils.py` - Provides path validation and audit logging
- `docs/TOOL-AUTO-APPROVAL.md` - Tool approval configuration reference
- `plugins/autonomous-dev/templates/settings.default.json` - Default template with safe patterns


## 43. protected_file_detector.py (316 lines, v3.41.0+)

**Purpose**: Detect user artifacts and protected files during installation

**Issue**: #106 (GenAI-first installation system)

### Overview

The protected file detector identifies files that should NOT be overwritten during installation. This includes:
- User configuration files (.env, PROJECT.md)
- State files (batch state, session state)
- Custom hooks created by users
- Modified plugin files (detected by hash comparison)

**Key Features**:
- Always-protected file list (hardcoded critical files)
- Custom hook detection (glob patterns)
- Plugin default comparison (hash-based)
- Flexible glob pattern matching
- File categorization (config, state, custom_hook, modified_plugin)

### Class

#### `ProtectedFileDetector`

Detects files that should be protected during installation.

**Constructor**:
```python
def __init__(
    self,
    additional_patterns: Optional[List[str]] = None,
    plugin_defaults: Optional[Dict[str, str]] = None
)
```

**Parameters**:
- `additional_patterns` (Optional[List[str]]): Extra glob patterns to protect
- `plugin_defaults` (Optional[Dict[str, str]]): Dict mapping file paths to their default SHA256 hashes

**Attributes**:
- `ALWAYS_PROTECTED` (List[str]): Always-protected files
- `PROTECTED_PATTERNS` (List[str]): Default glob patterns

### Methods

##### `detect_protected_files(project_dir: Path | str) -> List[Dict[str, Any]]`

Identify all protected files in a project directory.

**Parameters**:
- `project_dir` (Path | str): Path to project directory

**Returns**: List of protected file dicts with file, category, protection_reason, hash

##### `get_protected_patterns() -> List[str]`

Get all protected glob patterns (built-in + custom).

**Returns**: List of glob patterns

##### `has_plugin_default(file_path: str) -> bool`

Check if plugin has a default for this file.

**Parameters**:
- `file_path` (str): File path to check

**Returns**: True if file has a default hash in plugin_defaults

##### `matches_pattern(file_path: str) -> bool`

Check if file path matches any protected pattern.

**Parameters**:
- `file_path` (str): File path to check

**Returns**: True if matches any protected pattern

##### `matches_plugin_default(file_path: Path, relative_path: str) -> bool`

Check if file matches plugin default (unmodified).

**Parameters**:
- `file_path` (Path): Full path to file
- `relative_path` (str): Relative path from project root

**Returns**: True if file content matches default hash

##### `calculate_hash(file_path: Path) -> str`

Calculate SHA256 hash of a file.

**Parameters**:
- `file_path` (Path): Path to file

**Returns**: SHA256 hex digest

### File Categories

**Config Files**: `.env`, `*.env`, `.claude/PROJECT.md` - Never overwritten

**State Files**: `.claude/batch_state.json`, `.claude/session_state.json` - Preserves workflow state

**Custom Hooks**: Files matching `.claude/hooks/custom_*.py` pattern - Never removed

**Modified Plugin Files**: Plugin files with different hashes - Protected to preserve customizations

### Security Features

**Hash-Based Comparison**:
- Compares file content, not timestamps
- Detects modified plugin files even if timestamps change
- Enables reliable conflict detection across machines

**Pattern Matching**:
- fnmatch-style glob patterns
- Flexible protection rules
- Supports wildcards (*, ?, [...])

### Testing

**Test Coverage**: 22 tests

### Related

- GitHub Issue #106 (GenAI-first installation system)
- `staging_manager.py` - Manages staged files
- `installation_analyzer.py` - Analyzes protection impact
- `install_audit.py` - Logs protected file decisions
- `copy_system.py` - Uses protection info for safe copying

---

## 44. installation_analyzer.py (374 lines, v3.41.0+)

**Purpose**: Analyze installation type and recommend installation strategy

**Issue**: #106 (GenAI-first installation system)

### Overview

The installation analyzer examines project state and plugin staging to determine the installation type (fresh, brownfield, or upgrade) and recommend an appropriate installation strategy with risk assessment.

**Key Features**:
- Installation type detection (fresh/brownfield/upgrade)
- Comprehensive conflict analysis
- Risk assessment (low/medium/high)
- Strategy recommendation with action items
- Detailed analysis reports

### Enumerations

#### `InstallationType`

Installation type enumeration.

**Values**:
- `FRESH = "fresh"` - New project with no existing plugin
- `BROWNFIELD = "brownfield"` - Existing project with plugin artifacts
- `UPGRADE = "upgrade"` - Existing plugin being updated

### Main Class

#### `InstallationAnalyzer`

Analyzes installation scenarios and recommends strategies.

**Constructor**:
```python
def __init__(self, project_dir: Path | str)
```

**Parameters**:
- `project_dir` (Path | str): Path to project directory

**Raises**:
- `ValueError`: If project directory doesn't exist

### Methods

##### `detect_installation_type() -> InstallationType`

Determine installation type based on project state.

**Returns**: InstallationType enum value

##### `generate_conflict_report(staging_dir: Path | str) -> Dict[str, Any]`

Generate detailed conflict analysis report.

**Parameters**:
- `staging_dir` (Path | str): Staging directory with new files

**Returns**: Report dict with total_conflicts, conflicts, protected_files, risk_level

##### `recommend_strategy() -> Dict[str, Any]`

Recommend installation strategy based on project state.

**Returns**: Strategy dict with type, strategy, action_items, warnings, approval_required

##### `assess_risk() -> Dict[str, Any]`

Assess installation risk level.

**Returns**: Risk assessment dict with level, factors, conflicts_count, protected_files_count, recommendation

**Risk Levels**:
- `low` - No conflicts, protected files intact
- `medium` - Some conflicts with protected files
- `high` - Many conflicts, potential data loss

##### `generate_analysis_report(staging_dir: Path | str) -> Dict[str, Any]`

Generate comprehensive analysis report combining all analysis.

**Parameters**:
- `staging_dir` (Path | str): Staging directory

**Returns**: Complete analysis report dict

### Integration with GenAI-First Installation

This analyzer is used by the GenAI-first installation system to:

1. **Pre-Analysis Phase**: Analyze project before staging files
2. **Strategy Recommendation**: Recommend installation approach
3. **Risk Assessment**: Identify potential issues
4. **Conflict Resolution**: Guide conflict resolution strategy
5. **Approval Decision**: Determine if human approval required

### Testing

**Test Coverage**: 24 tests

### Related

- GitHub Issue #106 (GenAI-first installation system)
- `staging_manager.py` - Provides conflict detection
- `protected_file_detector.py` - Identifies protected files
- `install_audit.py` - Logs analysis results
- `copy_system.py` - Executes recommended strategy

---

## 45. install_audit.py (493 lines, v3.41.0+)

**Purpose**: Audit logging for GenAI-first installation system

**Issue**: #106 (GenAI-first installation system)

### Overview

The install audit module provides append-only audit logging for installation operations. It tracks installation attempts, protected files, conflicts, resolutions, and outcomes using JSONL format (one JSON object per line). This enables crash recovery, audit trails, and installation reports.

**Key Features**:
- JSONL format (append-only, crash-resistant)
- Unique installation IDs for tracking
- Protected file recording with categorization
- Conflict tracking and resolution logging
- Report generation from audit trail
- Multiple query methods (by ID, by status)

### Data Classes

#### `AuditEntry`

Represents a single audit log entry.

**Constructor**:
```python
def __init__(
    self,
    event: str,
    install_id: str,
    timestamp: Optional[str] = None,
    **kwargs
)
```

**Parameters**:
- `event` (str): Event type
- `install_id` (str): Unique installation ID
- `timestamp` (Optional[str]): ISO 8601 timestamp (auto-generated if None)
- `**kwargs`: Additional event-specific fields

**Methods**:

##### `to_dict() -> Dict[str, Any]`

Convert entry to dictionary for JSON serialization.

**Returns**: Dict with event, install_id, timestamp, and all kwargs

### Main Class

#### `InstallAudit`

Manages audit logging for installations.

**Constructor**:
```python
def __init__(self, audit_file: Path | str)
```

**Parameters**:
- `audit_file` (Path | str): Path to JSONL audit log file

### Methods

##### `start_installation(install_type: str) -> str`

Start a new installation session and generate unique ID.

**Parameters**:
- `install_type` (str): Type of installation ("fresh", "brownfield", "upgrade")

**Returns**: Unique installation ID (UUID format)

##### `log_success(install_id: str, files_copied: int, **kwargs) -> None`

Log successful installation completion.

**Parameters**:
- `install_id` (str): Installation ID
- `files_copied` (int): Number of files copied
- `**kwargs`: Additional context (duration, etc.)

##### `log_failure(install_id: str, error: str, **kwargs) -> None`

Log installation failure.

**Parameters**:
- `install_id` (str): Installation ID
- `error` (str): Error message
- `**kwargs`: Additional context

##### `record_protected_file(install_id: str, file_path: str, category: str) -> None`

Record a protected file that won't be overwritten.

**Parameters**:
- `install_id` (str): Installation ID
- `file_path` (str): Relative path to protected file
- `category` (str): Protection category

##### `record_conflict(install_id: str, file_path: str, conflict_type: str, **kwargs) -> None`

Record a file conflict during installation.

**Parameters**:
- `install_id` (str): Installation ID
- `file_path` (str): Path to conflicting file
- `conflict_type` (str): Type of conflict
- `**kwargs`: Additional context (hashes, sizes, etc.)

##### `record_conflict_resolution(install_id: str, file_path: str, resolution: str, **kwargs) -> None`

Record how a conflict was resolved.

**Parameters**:
- `install_id` (str): Installation ID
- `file_path` (str): Path to file
- `resolution` (str): Resolution action (skip, overwrite, merge, manual_review)
- `**kwargs`: Additional context

##### `generate_report(install_id: str) -> Dict[str, Any]`

Generate a report for a specific installation.

**Parameters**:
- `install_id` (str): Installation ID

**Returns**: Report dict with install_id, status, duration, protected_files, conflicts, files_copied, summary

##### `export_report(install_id: str, report_file: Path | str) -> None`

Export a report to JSON file.

**Parameters**:
- `install_id` (str): Installation ID
- `report_file` (Path | str): Path to write report JSON

##### `get_all_installations() -> List[Dict[str, Any]]`

Get all installation records from audit log.

**Returns**: List of installation dicts with status, timestamp, type

##### `get_installations_by_status(status: str) -> List[Dict[str, Any]]`

Get installations filtered by status.

**Parameters**:
- `status` (str): "success" or "failure"

**Returns**: List of matching installations

### JSONL Format

The audit log is JSONL (JSON Lines) format - one JSON object per line.

### Security Features

**Path Validation**:
- Validates all file paths to prevent injection
- Blocks paths with suspicious patterns

**Append-Only Design**:
- All entries appended (never modified)
- Supports recovery from crashes
- Enables forensic analysis

**Timestamp Tracking**:
- All entries timestamped (ISO 8601)
- Tracks operation order and duration
- Enables performance analysis

### Testing

**Test Coverage**: 26 tests

### Related

- GitHub Issue #106 (GenAI-first installation system)
- `staging_manager.py` - Triggers conflict logging
- `protected_file_detector.py` - Categorizes protected files
- `installation_analyzer.py` - Analyzes installation strategy
- `copy_system.py` - Executes operations that are logged

## 46. genai_install_wrapper.py (596 lines, v3.42.0+)

**Purpose**: CLI wrapper for setup-wizard Phase 0 GenAI-first installation with JSON output for agent consumption

**Type**: Script utility

**Location**: `plugins/autonomous-dev/scripts/genai_install_wrapper.py`

**Issue**: GitHub Issue #109 (Setup-wizard GenAI integration)

### Overview

Provides CLI interface for setup-wizard Phase 0 (GenAI installation), wrapping core installation libraries with JSON output for intelligent agent decision-making. Enables setup-wizard to use pre-downloaded plugin files with automated conflict resolution and protected file preservation.

### Features

**5 CLI Commands**:
- `check-staging` - Validate staging directory exists
- `analyze` - Analyze installation type (fresh/brownfield/upgrade)
- `execute` - Perform installation with protected file handling
- `cleanup` - Remove staging directory (idempotent)
- `summary` - Generate installation summary report

**Design**:
- JSON output for agent parsing
- Non-blocking error handling (graceful degradation to Phase 1)
- Atomic and idempotent commands (safe to retry)
- Full audit trail via InstallAudit

### Exports

#### Main Functions

##### `check_staging(staging_path: str) -> Dict[str, Any]`

Validate staging directory exists and contains critical directories.

**Parameters**:
- `staging_path` (str): Path to staging directory

**Returns**:
```json
{
  "status": "valid|missing|invalid",
  "staging_path": "...",
  "fallback_needed": bool,
  "missing_dirs": ["..."],
  "message": "..."
}
```

**Purpose**: Detect if Phase 0 can proceed; if missing, skip to Phase 1

##### `analyze_installation_type(project_path: str) -> Dict[str, Any]`

Analyze project state to determine installation type and protected files.

**Parameters**:
- `project_path` (str): Path to project directory

**Returns**:
```json
{
  "type": "fresh|brownfield|upgrade",
  "has_project_md": bool,
  "has_claude_dir": bool,
  "existing_files": ["..."],
  "protected_files": ["..."]
}
```

**Purpose**: Display to user before installation; inform about protected files

**Installation Types**:
- **fresh**: No `.claude/` directory (new installation)
- **brownfield**: Has PROJECT.md or user artifacts (preserve user files)
- **upgrade**: Has existing plugin files (create backups)

##### `execute_installation(staging_path: str, project_path: str, install_type: str) -> Dict[str, Any]`

Execute installation from staging to project with protected file handling.

**Parameters**:
- `staging_path` (str): Path to staging directory
- `project_path` (str): Path to target project directory
- `install_type` (str): "fresh", "brownfield", or "upgrade"

**Returns**:
```json
{
  "status": "success|error",
  "files_copied": int,
  "skipped_files": ["..."],
  "backups_created": ["..."],
  "error": "..."
}
```

**Purpose**: Perform actual installation from staging to project

**Behavior**:
- Validates install_type parameter
- Validates staging directory exists
- Creates project directory if needed
- Detects protected files (ALWAYS_PROTECTED list + user artifacts)
- Logs protected files in audit trail
- Uses CopySystem with appropriate conflict strategy
- Records installation in audit log

**Conflict Strategies**:
- **brownfield/fresh**: `skip` - Do not overwrite protected files
- **upgrade**: `backup` - Create backups before overwriting

**Error Handling**:
- Returns status: "error" if install_type invalid
- Returns status: "error" if staging does not exist
- Returns status: "error" if copy operation fails
- All errors recorded in audit trail

##### `cleanup_staging(staging_path: str) -> Dict[str, Any]`

Remove staging directory (idempotent - safe to call multiple times).

**Parameters**:
- `staging_path` (str): Path to staging directory

**Returns**:
```json
{
  "status": "success|error",
  "message": "..."
}
```

**Purpose**: Clean up after installation completes

**Idempotent**: Returns success if staging already removed

##### `generate_summary(install_type: str, install_result: Dict[str, Any] | str, project_path: str) -> Dict[str, Any]`

Generate installation summary report with next steps.

**Parameters**:
- `install_type` (str): "fresh", "brownfield", or "upgrade"
- `install_result` (Dict | str): Result from execute_installation (or path to JSON file)
- `project_path` (str): Path to project directory

**Returns**:
```json
{
  "status": "success",
  "summary": {
    "install_type": "...",
    "files_copied": int,
    "skipped_files": int,
    "backups_created": int
  },
  "next_steps": ["..."]
}
```

**Purpose**: Display results to user with recommended next steps

**Next Steps by Type**:
- **fresh**: Configure PROJECT.md, environment variables, test with /status
- **brownfield**: Review protected files, run /align-project, test
- **upgrade**: Review backups, test with /status, run /health-check

##### `main() -> int`

CLI entry point.

**Exit Codes**:
- 0: Success
- 1: Error (missing arguments or command failure)

### Setup-Wizard Phase 0 Workflow

Orchestrates 6-step installation process:

1. **Phase 0.1**: Check for staging directory
   - Call: `check_staging(staging_path)`
   - If fallback_needed: Skip to Phase 1

2. **Phase 0.2**: Analyze installation type
   - Call: `analyze_installation_type(project_path)`
   - Display analysis to user (type, protected files)

3. **Phase 0.3**: Execute installation
   - Call: `execute_installation(staging_path, project_path, type)`
   - Display progress (files copied, skipped, backups)

4. **Phase 0.4**: Validate critical directories exist
   - Verify: plugins/autonomous-dev/commands/
   - Verify: plugins/autonomous-dev/agents/
   - Verify: plugins/autonomous-dev/hooks/
   - Verify: plugins/autonomous-dev/lib/
   - Verify: plugins/autonomous-dev/skills/
   - Verify: .claude/

5. **Phase 0.5**: Generate summary
   - Call: `generate_summary(type, result, project_path)`
   - Display summary and next steps

6. **Phase 0.6**: Cleanup staging
   - Call: `cleanup_staging(staging_path)`
   - Remove staging directory

**Error Recovery**: Any step failure falls back to Phase 1 (manual setup) without data loss

### Integration Points

**Uses**:
- `staging_manager.py`: Check directory validity, list files
- `installation_analyzer.py`: Analyze installation type
- `protected_file_detector.py`: Identify protected files
- `copy_system.py`: Execute file copying with protection
- `install_audit.py`: Record all operations in audit trail

**Called By**:
- `setup-wizard.md` (Phase 0 workflow)

### Security Features

**Path Traversal Prevention (CWE-22)**:
- Validates all paths before operations
- Rejects paths with `../` sequences
- Uses `Path.resolve()` for absolute path validation

**Symlink Attack Prevention (CWE-59)**:
- Detects symlinks via `is_symlink()`
- Validates resolved targets are within project

**Protected File Detection**:
- ALWAYS_PROTECTED list: .env, .claude/PROJECT.md, .claude/batch_state.json, etc.
- Custom detection for user hooks via glob patterns
- Hash-based detection for modified plugin files

**Audit Logging**:
- All operations logged in `.claude/install_audit.jsonl`
- Enables forensic analysis and debugging
- Supports recovery from crashes

### Error Handling

**Graceful Degradation**:
- CLI failures do not interrupt setup wizard
- Phase 0 failures fall back to Phase 1 (manual setup)
- Non-blocking: Errors return status field for agent decision-making

**JSON Error Format**:
```json
{
  "status": "error",
  "error": "Error message",
  "command": "command_name"
}
```

### Usage Examples

**Check Staging**:
```bash
python genai_install_wrapper.py check-staging "$HOME/.autonomous-dev-staging"
```

**Analyze Project**:
```bash
python genai_install_wrapper.py analyze "$(pwd)"
```

**Execute Installation**:
```bash
python genai_install_wrapper.py execute \
  "$HOME/.autonomous-dev-staging" \
  "$(pwd)" \
  "fresh"
```

**Generate Summary**:
```bash
python genai_install_wrapper.py summary \
  "fresh" \
  "/tmp/install_result.json" \
  "$(pwd)"
```

**Cleanup**:
```bash
python genai_install_wrapper.py cleanup "$HOME/.autonomous-dev-staging"
```

### Design Patterns

**Non-Blocking CLI**:
- All commands return JSON
- Failures are graceful (do not crash wrapper)
- Agent can decide next action based on status field

**Atomic Commands**:
- Each command is independent
- Can be retried safely
- Idempotent operations (cleanup can run multiple times)

**Integration Layer**:
- Wraps core installation libraries
- Orchestrates workflow steps
- Provides human-friendly output templates

### Testing

**Test Coverage**: Comprehensive integration tests

**Scenarios**:
- Phase 0 complete workflow (all 6 steps)
- Missing staging directory (fallback to Phase 1)
- Invalid installation types (error handling)
- Protected file preservation (brownfield/upgrade)
- Backup creation for upgrades
- Error recovery and audit trail

### Related

- GitHub Issue #109 (Setup-wizard GenAI integration)
- `setup-wizard.md` - Phase 0 workflow documentation
- `staging_manager.py` - Directory validation and file listing
- `installation_analyzer.py` - Installation type detection
- `protected_file_detector.py` - Protected file identification
- `copy_system.py` - File copying with protection
- `install_audit.py` - Audit logging and reporting

---

## 49. configure_global_settings.py (CLI Wrapper, v3.46.0+, Issue #116)

**Purpose**: Configure fresh installs and upgrades with ~/.claude/settings.json permission patterns

**Called By**: `install.sh` during bootstrap Phase 1 (fresh install, updates, upgrades)

**Status**: Production (integrated into install.sh bootstrap workflow)

### Overview

CLI wrapper for `SettingsGenerator.merge_global_settings()`. Creates or updates `~/.claude/settings.json` with correct permission patterns for Claude Code 2.0. Handles both fresh installs (create from template) and upgrades (preserve user customizations while fixing broken patterns).

### Key Features

1. **Fresh Install**: Creates `~/.claude/settings.json` from template on first install
2. **Upgrade Path**: Preserves user customizations while fixing broken `Bash(:*)` patterns
3. **Non-Blocking**: Always exits 0 for graceful degradation (installation continues even on errors)
4. **Backup Safety**: Creates timestamped backup before modifying existing files
5. **JSON Output**: Returns structured status JSON for `install.sh` consumption
6. **Atomic Writes**: Uses tempfile + rename for safe file operations
7. **Directory Creation**: Creates `~/.claude/` if missing with secure permissions

### Command-Line Interface

**Basic Usage**:
```bash
# Fresh install (no existing settings)
python3 configure_global_settings.py --template /path/to/template.json

# Upgrade (existing settings, preserve customizations)
python3 configure_global_settings.py --template /path/to/template.json --home ~/.claude
```

**Arguments**:
- `--template PATH`: Path to settings template file (required)
  - Typically: `plugins/autonomous-dev/config/global_settings_template.json`
  - Must be valid JSON with `permissions` object
- `--home PATH`: Path to home directory (optional, default: `~/.claude`)
  - Rarely used, for testing with different directories

### Output Format

**Success Response**:
```json
{
  "success": true,
  "created": true,
  "message": "Created ~/.claude/settings.json from template",
  "path": "~/.claude/settings.json",
  "permissions": 384,
  "patterns_added": 45,
  "timestamp": "2025-12-13T15:30:45.123456"
}
```

**Upgrade Response** (preserving customizations):
```json
{
  "success": true,
  "created": false,
  "message": "Updated ~/.claude/settings.json (preserved customizations)",
  "path": "~/.claude/settings.json",
  "backup_path": "~/.claude/settings.json.backup.20251213_153045",
  "patterns_fixed": 2,
  "patterns_preserved": 5,
  "timestamp": "2025-12-13T15:30:45.123456"
}
```

**Error Response** (non-blocking):
```json
{
  "success": false,
  "created": false,
  "message": "Template file not found: /path/to/template.json",
  "path": null,
  "timestamp": "2025-12-13T15:30:45.123456"
}
```

**Exit Code**: Always 0 (non-blocking - installation continues)

### Integration with install.sh

Called from `install.sh` after downloading plugin files to configure global settings.

**Related Files**:
- `plugins/autonomous-dev/config/global_settings_template.json` - Template source
- `plugins/autonomous-dev/lib/settings_generator.py` - Python API
- `plugins/autonomous-dev/lib/validation.py` - Path validation
- `tests/unit/scripts/test_configure_global_settings.py` - Unit tests
- `tests/integration/test_install_settings_configuration.py` - Integration tests

### Configuration Processing

**Fresh Install Workflow**:
1. Check if template exists and is valid JSON
2. Create `~/.claude/` directory if missing (permissions: 0o700)
3. Merge template with empty user settings
4. Write merged settings to `~/.claude/settings.json` (permissions: 0o600)
5. Return JSON with `created: true`

**Upgrade Workflow**:
1. Check if template exists and is valid JSON
2. Read existing `~/.claude/settings.json`
3. Detect broken patterns (e.g., `Bash(:*)`)
4. Fix broken patterns: Replace `Bash(:*)` with safe specific patterns
5. Deep merge: template patterns + user patterns (union)
6. Preserve user hooks completely (never modified)
7. Create backup: `settings.json.backup.YYYYMMDD_HHMMSS`
8. Write merged settings atomically
9. Return JSON with `created: false`, backup path, and fix count

### Security

**Input Validation**:
- Path validation (CWE-22, CWE-59): Prevent path traversal, symlink attacks
- Template validation: Must be valid JSON
- Home directory validation: Must be under home directory

**Output Safety**:
- Atomic writes: Tempfile + rename pattern
- Secure permissions: 0o600 for settings (user-only access)
- No credential exposure in JSON output

**Backup Safety**:
- Timestamped filenames: `settings.json.backup.YYYYMMDD_HHMMSS`
- Only created if file will be modified
- Secure permissions: 0o600 (user-only access)
- Old backups automatically replaced (one backup per session)

### Error Handling

All errors are non-blocking (exit 0) for graceful degradation:

| Error | Message | Behavior |
|-------|---------|----------|
| Template not found | "Template file not found: ..." | Returns error JSON, continues installation |
| Invalid template JSON | "Template is invalid JSON: ..." | Returns error JSON, continues installation |
| Permission denied (read) | "Cannot read template: ..." | Returns error JSON, continues installation |
| Permission denied (write) | "Cannot write settings: ..." | Returns error JSON, continues installation |
| Corrupted settings.json | "Settings file corrupted: ..." | Backs up corrupted file, creates fresh copy |
| Path traversal attempt | "Invalid path: ..." | Rejected, continues installation |

Installation Impact: Non-blocking errors allow installation to continue. Manual configuration may be needed if settings.json not created.

### Testing

**Test Coverage**: 19 tests across 2 files

**Unit Tests** (11 tests):
- Fresh install creates settings from template
- Existing settings preserved during upgrade
- Broken Bash(:*) patterns fixed
- Missing template handled gracefully
- Directory creation with proper permissions
- JSON output format validation
- Exit code always 0 (non-blocking)
- Integration with SettingsGenerator
- Backup creation before modification
- Permission error handling
- Settings generator integration

**Integration Tests** (8 tests):
- Settings have correct Claude Code 2.0 format
- All 45+ required patterns present
- Deny list comprehensive
- PreToolUse hook configured
- Fresh install end-to-end
- Upgrade preserves customizations
- install.sh integration
- Idempotency (no duplication on repeated runs)

Coverage Target: 95%+ for CLI script

### Related Components

**Calls**:
- `SettingsGenerator.merge_global_settings()` - Core merge and fix logic

**Called By**:
- `install.sh` - Bootstrap Phase 1 (fresh install, updates, upgrades)

**Related Issues**:
- GitHub Issue #116 - Fresh install permission configuration (implementation)
- GitHub Issue #117 - Global settings configuration (related feature)
- GitHub Issue #114 - Permission fixing during updates (broken pattern detection)

### See Also

- **BOOTSTRAP_PARADOX_SOLUTION.md** - Why global infrastructure needed
- **VERIFICATION-ISSUE-116.md** - Documentation verification report
- **SettingsGenerator** - Python API for settings merge and fix logic

---

## 43. skill_loader.py (320 lines, v3.43.0+, Issue #140)

**Purpose**: Load and inject skill content into subagent prompts spawned via Task tool.

**Location**: `plugins/autonomous-dev/lib/skill_loader.py`

**Problem Solved**: Subagents spawned via Task tool do not inherit skills from the main conversation. Skills must be explicitly injected into Task prompts.

### Quick Start

```bash
# Load skills for an agent
python3 plugins/autonomous-dev/lib/skill_loader.py implementer

# List available skills
python3 plugins/autonomous-dev/lib/skill_loader.py --list

# Show agent-skill mapping
python3 plugins/autonomous-dev/lib/skill_loader.py --map
```

### Core Functions

#### `load_skills_for_agent(agent_name: str) -> Dict[str, str]`

Load all relevant skills for an agent.

**Parameters**:
- `agent_name` (str): Name of the agent (e.g., "implementer")

**Returns**: Dict mapping skill names to their content

#### `format_skills_for_prompt(skills: Dict[str, str], max_total_lines: int = 1500) -> str`

Format loaded skills as XML tags for prompt injection.

**Parameters**:
- `skills` (Dict[str, str]): Dict mapping skill names to content
- `max_total_lines` (int): Maximum total lines across all skills (default 1500)

**Returns**: Formatted string with skills in XML tags

#### `get_skill_injection_for_agent(agent_name: str) -> str`

Convenience function to get formatted skill injection for an agent.

**Parameters**:
- `agent_name` (str): Name of the agent

**Returns**: Formatted skill content ready for prompt injection

### Agent-Skill Mapping

| Agent | Skills |
|-------|--------|
| test-master | testing-guide, python-standards |
| implementer | python-standards, testing-guide, error-handling-patterns |
| reviewer | code-review, python-standards |
| security-auditor | security-patterns, error-handling-patterns |
| doc-master | documentation-guide, git-workflow |
| planner | architecture-patterns, project-management |

### Security Features

- **Trusted Directory Only**: Skills loaded from `plugins/autonomous-dev/skills/` only
- **No Path Traversal**: Rejects skill names with `/`, `\`, or `..`
- **Text Injection Only**: Skill content is not executed, only injected as text
- **Audit Logging**: Missing skills logged to stderr for debugging

### Integration with auto-implement.md

The `/implement` command uses skill_loader.py before each Task call:

```markdown
**SKILL INJECTION** (Issue #140): Before calling Task, load skills:
\`\`\`bash
python3 plugins/autonomous-dev/lib/skill_loader.py test-master
\`\`\`
Prepend the output to the prompt below.
```

### Related Components

**Imports**:
- `path_utils.get_project_root()` - Project root detection

**Used By**:
- `auto-implement.md` - Skill injection before Task calls

**Related Issues**:
- GitHub Issue #140 - Skills not available to subagents
- GitHub Issue #35 - Agents should actively use skills
- GitHub Issue #110 - Skills refactoring to under 500 lines

---

## 33. feature_dependency_analyzer.py (509 lines, v1.0.0 - Issue #157)

**Purpose**: Analyze feature descriptions for dependencies and optimize batch execution order using topological sort

**Location**: plugins/autonomous-dev/lib/feature_dependency_analyzer.py

**Dependencies**: validation.py (optional, graceful degradation)

### Classes

#### FeatureDependencyError

Base exception for feature dependency operations.

#### CircularDependencyError

Raised when circular dependencies are detected in the dependency graph.

#### TimeoutError

Raised when analysis exceeds 5-second timeout.

### Functions

#### detect_keywords(feature_text: str) -> Set[str]

Extract dependency keywords from feature text.

**Parameters**:
- feature_text (str): Feature description text

**Returns**: Set of detected keywords (lowercase)

**Detects**:
- Dependency keywords: requires, depends, after, before, uses, needs
- File references: .py, .md, .json, .yaml, .yml, .sh, .ts, .js, .tsx, .jsx

**Example**:
```python
keywords = detect_keywords("Add tests for auth (requires auth implementation)")
# Returns: {"requires", "tests", "auth"}
```

#### build_dependency_graph(features: List[str], keywords: Dict[int, Set[str]]) -> Dict[int, List[int]]

Build directed dependency graph from feature keywords.

**Parameters**:
- features (List[str]): List of feature descriptions
- keywords (Dict[int, Set[str]]): Keywords detected per feature (from detect_keywords)

**Returns**: Dependency graph where deps[i] = [j, k] means features i depends on j and k

**Algorithm**: Analyzes feature names for references to other features using keyword matching and file similarity.

#### analyze_dependencies(features: List[str]) -> Dict[int, List[int]]

Main entry point: analyze features for dependencies.

**Parameters**:
- features (List[str]): List of feature descriptions

**Returns**: Dependency graph (Dict[int, List[int]])

**Execution**:
1. Validates input (max 1000 features, sanitizes text)
2. Detects keywords for each feature
3. Builds dependency graph
4. Detects circular dependencies
5. Returns graph with timeout protection (5 seconds)

**Graceful Degradation**: Returns empty dict (no dependencies) if analysis fails

#### topological_sort(features: List[str], deps: Dict[int, List[int]]) -> List[int]

Order features using topological sort (Kahn's algorithm).

**Parameters**:
- features (List[str]): Feature descriptions
- deps (Dict[int, List[int]]): Dependency graph from analyze_dependencies()

**Returns**: Feature indices in dependency order

**Algorithm**: Kahn's algorithm for topological sort
- Time complexity: O(V + E) where V = features, E = dependencies
- Circular dependencies raise CircularDependencyError

**Example**:
```python
features = ["Add auth", "Add tests for auth"]
deps = analyze_dependencies(features)
order = topological_sort(features, deps)
# Returns: [0, 1] (implement auth before testing)
```

#### visualize_graph(features: List[str], deps: Dict[int, List[int]]) -> str

Generate ASCII visualization of dependency graph.

**Parameters**:
- features (List[str]): Feature descriptions
- deps (Dict[int, List[int]]): Dependency graph

**Returns**: Formatted ASCII string showing graph relationships

**Example Output**:
```
Feature Dependency Graph
========================

Feature 0: Add auth
  └─> [depends on] (no dependencies)

Feature 1: Add tests for auth
  └─> [depends on] Feature 0: Add auth

Feature 2: Add password reset
  └─> [depends on] Feature 0: Add auth
```

#### detect_circular_dependencies(deps: Dict[int, List[int]]) -> List[List[int]]

Detect circular dependency cycles in graph.

**Parameters**:
- deps (Dict[int, List[int]]): Dependency graph

**Returns**: List of cycles (each cycle is list of feature indices)

**Returns empty list if no cycles detected**

#### get_execution_order_stats(features: List[str], deps: Dict[int, List[int]], order: List[int]) -> Dict[str, Any]

Generate statistics about execution order.

**Parameters**:
- features (List[str]): Feature descriptions
- deps (Dict[int, List[int]]): Dependency graph
- order (List[int]): Topologically sorted order

**Returns**: Dictionary with statistics:
```python
{
    "total_dependencies": 3,      # Total edges in graph
    "independent_features": 1,    # Features with no dependencies
    "dependent_features": 2,      # Features with dependencies
    "max_depth": 2,              # Longest dependency chain
    "total_features": 3,
}
```

### Security

**Input Validation** (CWE-22, CWE-78):
- Text sanitization via validation.sanitize_text_input() (max 10,000 chars per feature)
- No shell execution
- Path traversal protection via safe regex matching
- Command injection prevention - only text analysis

**Resource Limits**:
- MAX_FEATURES: 1000 (prevents unbounded processing)
- TIMEOUT_SECONDS: 5 (prevents infinite loops in circular detection)
- Memory: O(V + E) for graph storage (linear in feature count)

### Performance Characteristics

- **Analysis Time**: <100ms for typical batches (50 features)
- **Memory**: O(V + E) where V = features, E = dependencies
- **Topological Sort**: O(V + E) via Kahn's algorithm
- **Circular Detection**: O(V + E) via DFS
- **Graph Visualization**: O(V + E) for ASCII rendering

### Error Handling

**Graceful Degradation**:
- If analysis fails: Returns empty dict (no dependencies detected)
- If topological sort fails: CircularDependencyError raised
- If timeout exceeded: TimeoutError raised
- If validation fails: Returns fallback (original order)

### Test Coverage

**Test File**: tests/unit/lib/test_feature_dependency_analyzer.py

**Coverage Areas**:
- Keyword detection (requires, depends, after, before, uses, needs)
- File reference detection (.py, .md, .json, etc.)
- Dependency graph construction
- Topological sort correctness
- Circular dependency detection
- ASCII visualization formatting
- Timeout protection
- Memory limits for large batches
- Security validations (CWE-22, CWE-78)
- Graceful degradation with invalid inputs

**Target**: 90%+ coverage

### Used By

- /implement --batch command (STEP 1.5 - Analyze Dependencies)
- batch_state_manager.py - Stores optimized order and dependency info
- Batch processing workflow for reordering features

### Related Issues

- GitHub Issue #157 - Smart dependency ordering for /implement --batch
- GitHub Issue #88 - Batch processing support
- GitHub Issue #89 - Automatic retry for batch features
- GitHub Issue #93 - Git automation for batch mode

### Related Components

**Dependencies**:
- validation.py - Input sanitization (optional, graceful degradation)

**Used By**:
- batch_state_manager.py - Stores dependency metadata
- /implement --batch command - STEP 1.5 dependency analysis

### Example Workflow

```python
from plugins.autonomous_dev.lib.feature_dependency_analyzer import (
    analyze_dependencies,
    topological_sort,
    visualize_graph,
    get_execution_order_stats
)

# Features to process
features = [
    "Add JWT authentication module",
    "Add tests for JWT validation",
    "Add password reset endpoint (requires auth)"
]

# Analyze dependencies
deps = analyze_dependencies(features)

# Get optimized order
order = topological_sort(features, deps)

# Get statistics
stats = get_execution_order_stats(features, deps, order)

# Visualize for user
graph = visualize_graph(features, deps)

print(f"Dependencies detected: {stats['total_dependencies']}")
print(f"Independent features: {stats['independent_features']}")
print(graph)

# Use optimized order in batch processing
for idx in order:
    process_feature(features[idx])
```

### Integration with /implement --batch

STEP 1.5 in /implement --batch command now calls this analyzer:

```python
# Import analyzer
from plugins.autonomous_dev.lib.feature_dependency_analyzer import (
    analyze_dependencies,
    topological_sort,
    visualize_graph,
    get_execution_order_stats
)

# Analyze and optimize order
try:
    deps = analyze_dependencies(features)
    feature_order = topological_sort(features, deps)
    stats = get_execution_order_stats(features, deps, feature_order)
    graph = visualize_graph(features, deps)

    # Store in batch state
    state.feature_dependencies = deps
    state.feature_order = feature_order
    state.analysis_metadata = {"stats": stats}

    # Show user
    print(f"Dependencies detected: {stats['total_dependencies']}")
    print(graph)
except Exception as e:
    # Graceful degradation
    print(f"Dependency analysis failed: {e}")
    feature_order = list(range(len(features)))
    state.feature_order = feature_order
```

---

## 51. genai_manifest_validator.py (474 lines, v3.44.0+ - Issue #160)

**Purpose**: GenAI-powered manifest alignment validation using Claude Sonnet 4.5 with structured output.

**Module**: plugins/autonomous-dev/lib/genai_manifest_validator.py

**Problem Solved**:
- Manual CLAUDE.md updates may create drift between documented component counts and actual manifest
- Regex-only validation misses semantic inconsistencies and version conflicts
- Need LLM reasoning to catch complex alignment issues

**Solution**:
- Uses Claude Sonnet 4.5 with structured JSON output for manifest validation
- Validates manifest (plugin.json) against documentation (CLAUDE.md)
- Detects count mismatches, version drift, missing components, inconsistent configurations
- Returns None when API key absent (enables fallback to regex validator)
- Supports both Anthropic and OpenRouter API keys for flexibility

### Core Classes

#### ManifestIssue
Represents a single manifest alignment issue with severity level.

#### IssueLevel
Enum for validation issue severity levels with ERROR, WARNING, and INFO levels.

#### ManifestValidationResult
Complete validation result with component breakdown, counts, versions, and timestamp.

#### GenAIManifestValidator
Main validator class using Claude Sonnet 4.5 with structured output.

### API Reference

#### GenAIManifestValidator.validate()

Main validation entry point.

**Returns**: Optional[ManifestValidationResult]
- ManifestValidationResult on successful validation
- None if API key missing (graceful fallback)

**Raises**:
- json.JSONDecodeError - If plugin.json is malformed
- FileNotFoundError - If plugin.json or CLAUDE.md not found
- Exception - If API call fails (will be caught and logged)

**Security**:
- Path validation via security_utils (CWE-22, CWE-59)
- Token budget enforcement (max 8K tokens)
- API key never logged
- Input sanitization

### Validation Checks

GenAI validator checks for:
1. Count Mismatches: Documented vs actual component counts
2. Version Drift: Documented versions vs manifest versions
3. Missing Components: Components in manifest but not documented
4. Undocumented Components: Components documented but not in manifest
5. Configuration Inconsistencies: Settings conflicts between manifest and docs
6. Dependency Issues: Component dependencies that cannot be satisfied

### LLM Reasoning

Uses Claude Sonnet 4.5 for semantic validation:
- Understands natural language descriptions in CLAUDE.md
- Detects logical inconsistencies (e.g., documented 8 agents but manifest shows 7)
- Catches version mismatches across multiple files
- Identifies scope creep (features documented but not implemented)
- Validates architectural claims against actual implementation

### API Support

**Primary API**: Anthropic (ANTHROPIC_API_KEY)

**Fallback API**: OpenRouter (OPENROUTER_API_KEY)

### Security

**Input Validation** (CWE-22, CWE-59):
- Path validation via security_utils.validate_path()
- Only allows project root and system temp directories
- Symlink resolution and normalization

**Token Budget**:
- MAX_TOKENS = 8000
- Enforced in prompt construction
- Prevents runaway API costs

**API Key Handling**:
- Keys read from environment only
- Never logged or exposed in output
- Graceful degradation if missing

**Data Handling**:
- No sensitive data in audit logs
- Results include only validation metadata
- No raw file contents in output

### Performance Characteristics

- API Latency: 5-15 seconds (Anthropic/OpenRouter)
- Local Processing: less than 100ms
- Total Time: 5-15 seconds per validation
- Token Usage: 2-4K tokens typical (within 8K budget)
- Memory: less than 50MB

### Error Handling

**Graceful Degradation**:
- API key missing: Returns None (signals fallback)
- API call fails: Logs error, returns None
- Invalid JSON: Raises JSONDecodeError (should be caught by hybrid validator)
- File not found: Returns None (signals regex fallback)
- Token budget exceeded: Truncates input gracefully

### Test Coverage

**Test File**: tests/unit/lib/test_genai_manifest_validator.py

**Coverage Areas**:
- API key detection (Anthropic, OpenRouter, missing)
- Manifest loading and validation
- CLAUDE.md parsing
- Count mismatch detection
- Version drift detection
- Missing component detection
- Prompt construction with token budget
- LLM response parsing
- Error handling (missing files, invalid JSON)
- Security validations (path traversal, injection)
- Graceful degradation

**Target**: 85 percent coverage

### Used By

- hybrid_validator.py - Primary GenAI validator (tries first, falls back if no API key)
- /health-check command - Optional GenAI validation if API key available
- CI/CD validation - For GenAI-powered alignment checks

### Related Issues

- GitHub Issue #160 - GenAI manifest alignment validation
- GitHub Issue #148 - Claude Code 2.0 compliance
- GitHub Issue #146 - Tool least privilege enforcement

### Related Components

**Dependencies**:
- security_utils.py - Path validation and audit logging
- anthropic package (optional) - Anthropic API
- openai package (optional) - OpenRouter API via OpenAI client

**Used By**:
- hybrid_validator.py - Orchestrator that wraps this validator

### Fallback Mechanism

GenAI validator is designed to fail gracefully. When API key is missing, it returns None which signals the hybrid validator to fall back to regex validation. This enables LLM-powered validation in environments with API keys while maintaining regex-based validation for users without them.

---

## 52. hybrid_validator.py (378 lines, v3.44.0+ - Issue #160)

**Purpose**: Orchestrates GenAI and regex manifest validation with automatic fallback.

**Module**: plugins/autonomous-dev/lib/hybrid_validator.py

**Problem Solved**:
- Users with API keys get LLM-powered validation (better accuracy)
- Users without API keys get regex validation (still catches issues)
- Need unified API for both approaches

**Solution**:
- Three validation modes: AUTO (default), GENAI_ONLY, REGEX_ONLY
- AUTO mode tries GenAI first, falls back to regex if API key missing
- Returns consistent HybridValidationReport format
- Used by /health-check and CI/CD validation pipelines

### Core Classes

#### ValidationMode
Enum for validation execution modes with AUTO, GENAI_ONLY, and REGEX_ONLY values.

#### HybridValidationReport
Extended validation report with hybrid metadata tracking which validator was used.

#### HybridManifestValidator
Main validator orchestrator with mode-specific behavior.

### API Reference

#### HybridManifestValidator.__init__()

Initialize validator with mode selection.

**Parameters**:
- repo_root (Path): Repository root directory
- mode (ValidationMode): Validation mode (default: AUTO)

**Raises**:
- ValueError - If repo_root invalid or outside allowed locations

#### HybridManifestValidator.validate()

Main validation entry point with mode-specific behavior.

**Returns**: HybridValidationReport
- Always returns a report (never None)
- validator_used field indicates which backend was used

**Raises**:
- RuntimeError - Only in GENAI_ONLY mode if no API key
- FileNotFoundError - If required files missing

### Validation Modes

#### AUTO Mode (Default)

Strategy: LLM first, regex fallback

1. Try GenAI: Attempt validation with Claude Sonnet 4.5
2. Success Path: Return GenAI result (validator_used="genai")
3. Fallback Path: If API key missing, use regex validation
4. Final Result: Always returns HybridValidationReport

Best For: Production environments where API key may be available

#### GENAI_ONLY Mode

Strategy: Strict LLM validation

1. Check API Key: Verify ANTHROPIC_API_KEY or OPENROUTER_API_KEY
2. Fail if Missing: Raise RuntimeError
3. Validate: Use Claude Sonnet 4.5 validation

Best For: CI/CD pipelines that require LLM-powered validation

#### REGEX_ONLY Mode

Strategy: Pattern-based validation

1. Use Regex: Validate with pattern matching (no API call)
2. Return Result: Always succeeds (validator_used="regex")

Best For: Quick validation without API latency, offline environments

### Validation Report

All modes return HybridValidationReport with:
- validator_used: "genai" or "regex"
- version_issues: Version mismatches
- count_issues: Count discrepancies
- cross_reference_issues: Missing references
- error_count: Number of errors
- warning_count: Number of warnings
- info_count: Number of info messages
- is_valid: True if error_count equals zero

### Security

**Input Validation** (CWE-22, CWE-59):
- Path validation via security_utils.validate_path()
- Repository root must be within project boundaries
- No path traversal allowed

**API Key Handling**:
- Keys read from environment only
- Never exposed in output or logs
- Missing key triggers graceful fallback (AUTO mode)

**Data Flow**:
- GenAI validator: Processes manifest and docs, returns issues
- Regex validator: Pattern matching only, no LLM calls
- Report: Contains only validation metadata, no sensitive data

### Performance Characteristics

**AUTO Mode**:
- With API Key: 5-15 seconds (GenAI latency)
- Without API Key: less than 1 second (regex fallback)
- Typical: 1-3 seconds (regex)

**GENAI_ONLY Mode**:
- With API Key: 5-15 seconds
- Without API Key: RuntimeError (fails immediately)

**REGEX_ONLY Mode**:
- Always: less than 1 second
- Memory: less than 10MB

### Error Handling

**Graceful Degradation**:
- AUTO mode: Missing API key -> Falls back to regex
- GENAI_ONLY mode: Missing API key -> Raises RuntimeError
- REGEX_ONLY mode: Always succeeds (worst case: minimal validation)
- Invalid paths: Raises ValueError early (before validation)
- Missing files: Returns report with errors (no exception)

### Test Coverage

**Test File**: tests/unit/lib/test_hybrid_validator.py

**Coverage Areas**:
- Mode selection (AUTO, GENAI_ONLY, REGEX_ONLY)
- API key detection and fallback
- GenAI validation integration
- Regex validation fallback
- Report generation and formatting
- Error handling (missing files, invalid paths)
- Graceful degradation
- Security validations (path traversal)

**Target**: 85 percent coverage

### Used By

- /health-check command - Manifest alignment validation
- CI/CD validation pipelines - Automated alignment checks
- genai_manifest_validator.py - Wrapped by this orchestrator

### Related Issues

- GitHub Issue #160 - GenAI manifest alignment validation
- GitHub Issue #148 - Claude Code 2.0 compliance
- GitHub Issue #50 - /health-check command

### Related Components

**Dependencies**:
- genai_manifest_validator.py - LLM-powered validation
- security_utils.py - Path validation

**Used By**:
- /health-check command
- CI/CD validation scripts

---
## 53. acceptance_criteria_parser.py (269 lines, v3.45.0+ - Issue #161)

**Purpose**: Parse and format acceptance criteria from GitHub issues for UAT test generation.

**Module**: plugins/autonomous-dev/lib/acceptance_criteria_parser.py

**Problem Solved**:
- Test-master needs to extract acceptance criteria from GitHub issues
- Manual parsing is error-prone and time-consuming
- Need standardized format for UAT test generation with Gherkin-style scenarios

**Solution**:
- Fetch issue body via gh CLI with security validation
- Parse categorized acceptance criteria (### headers)
- Format criteria as Gherkin-style test scenarios
- Handle malformed/missing criteria gracefully

### Functions

#### fetch_issue_body(issue_number: int) -> str

Fetch GitHub issue body via gh CLI.

**Parameters**:
- issue_number (int): GitHub issue number (must be positive)

**Returns**: Issue body as string

**Raises**:
- ValueError: If issue not found (404)
- RuntimeError: If gh CLI not installed or network error

**Security**:
- Uses subprocess.run with list args (no shell=True)
- Validates issue_number is positive integer
- No credential exposure in logs

#### parse_acceptance_criteria(issue_body: str) -> Dict[str, List[str]]

Parse GitHub issue body into categorized acceptance criteria.

**Parameters**:
- issue_body (str): Raw GitHub issue body

**Returns**: Dictionary with category names as keys and lists of criteria as values

#### format_for_uat(criteria: Dict[str, List[str]]) -> List[Dict[str, str]]

Format acceptance criteria as Gherkin-style UAT scenarios.

**Parameters**:
- criteria (Dict): Parsed acceptance criteria

**Returns**: List of UAT scenario dictionaries with "scenario" and "description" keys

### Test Coverage

**Test File**: tests/unit/lib/test_acceptance_criteria_parser.py (530 lines, 16 tests)

**Coverage Areas**:
- Fetch issue body (gh CLI integration, error handling)
- Parse acceptance criteria (categorization, formatting)
- Format for UAT (Gherkin-style scenarios)
- Error handling (missing issues, network errors, malformed criteria)
- Security (subprocess list args, input validation)

**Target**: 90 percent coverage

### Used By

- test-master agent - UAT test generation during TDD phase
- /implement command - Acceptance criteria parsing in test phase

### Related Issues

- GitHub Issue #161 - Enhanced test-master for 3-tier test coverage

### Related Components

**Dependencies**:
- gh CLI (external) - GitHub issue fetching
- subprocess module (stdlib) - Command execution

**Used By**:
- test_tier_organizer.py - Test tier classification
- test_validator.py - Test validation after organization

---

## 54. test_tier_organizer.py (399 lines, v3.45.0+ - Issue #161)

**Purpose**: Classify and organize tests into unit/integration/uat tiers with pyramid validation.

**Module**: plugins/autonomous-dev/lib/test_tier_organizer.py

**Problem Solved**:
- Tests generated by test-master need intelligent tier classification
- Manual test organization is error-prone
- Need to enforce test pyramid (70% unit, 20% integration, 10% UAT)

**Solution**:
- Content-based tier classification (imports, decorators, patterns)
- Filename-based tier hints
- Tier directory structure creation (tests/{unit,integration,uat}/)
- Test pyramid validation with statistics

### Functions

#### determine_tier(test_content: str) -> str

Determine test tier from test file content analysis.

**Parameters**:
- test_content (str): Test file content as string

**Returns**: "unit", "integration", or "uat"

**Classification Logic**:
- UAT: pytest-bdd imports, Gherkin decorators (@scenario, @given, @when, @then), explicit "test_uat_" naming
- Integration: Multiple imports, subprocess, file I/O, "integration" in function names, tmp_path/tmpdir fixtures
- Unit: Default (single function, mocking, isolated)

#### determine_tier_from_filename(filename: str) -> str

Hint for test tier from filename patterns.

**Parameters**:
- filename (str): Test filename

**Returns**: "unit", "integration", or "uat" (or None for no hint)

#### create_tier_directories(base_path: Path, subdirs: List[str] = None) -> None

Create tier directory structure.

**Parameters**:
- base_path (Path): Repository root
- subdirs (List[str]): Optional subdirectories

**Creates**: tests/unit/, tests/integration/, tests/uat/

#### organize_tests_by_tier(test_files: List[Path], base_path: Path = None) -> Dict[str, List[Path]]

Move tests to tier directories with collision handling.

**Parameters**:
- test_files (List[Path]): List of test file paths
- base_path (Path): Repository root (auto-detected if None)

**Returns**: Dictionary mapping tier names to file paths

#### get_tier_statistics(tests_path: Path) -> Dict[str, int]

Count tests in each tier directory.

**Parameters**:
- tests_path (Path): Path to tests directory

**Returns**: Dictionary with unit/integration/uat/total counts

#### validate_test_pyramid(tests_path: Path) -> Tuple[bool, List[str]]

Validate test pyramid ratios (70% unit, 20% integration, 10% UAT).

**Parameters**:
- tests_path (Path): Path to tests directory

**Returns**: Tuple of (is_valid, warning_messages)

### Test Coverage

**Test File**: tests/unit/lib/test_test_tier_organizer.py (490 lines, 31 tests)

**Coverage Areas**:
- Tier determination (content and filename analysis)
- Directory structure creation
- Test file organization (with collision handling)
- Tier statistics and counting
- Test pyramid validation
- Error handling (missing directories, invalid paths)

**Target**: 90 percent coverage

### Used By

- test-master agent - Organizing generated tests after creation
- /implement command - Test organization in pipeline

### Related Issues

- GitHub Issue #161 - Enhanced test-master for 3-tier test coverage

### Related Components

**Dependencies**:
- pathlib - Path handling
- test_validator.py - Test validation after organization

**Used By**:
- test_validator.py - Validation gate before commit

---

## 55. test_validator.py (388 lines, v3.45.0+ - Issue #161)

**Purpose**: Execute tests, validate TDD workflow, and enforce quality gates.

**Module**: plugins/autonomous-dev/lib/test_validator.py

**Problem Solved**:
- Need to validate TDD red phase (tests must fail before implementation)
- Need to run validation gate (all tests must pass before commit)
- Need to detect syntax errors vs runtime errors
- Need to enforce coverage thresholds

**Solution**:
- Run pytest with minimal verbosity (--tb=line -q per Issue #90)
- Parse test output for pass/fail/error counts
- Enforce TDD red phase validation
- Detect and report syntax errors separately
- Validate coverage thresholds

### Functions

#### run_tests(test_path: Path, timeout: int = 300, pytest_args: List[str] = None) -> Dict[str, Any]

Execute pytest and return results.

**Parameters**:
- test_path (Path): Path to test directory or file
- timeout (int): Timeout in seconds (default 5 minutes)
- pytest_args (List[str]): Optional custom pytest arguments

**Returns**: Dictionary with results including success, passed, failed, errors, skipped, total, stdout, stderr, no_tests_collected

**Raises**:
- TimeoutError: If tests exceed timeout
- RuntimeError: If pytest not installed

**Minimal Verbosity** (Issue #90):
- Uses --tb=line -q to prevent pipe deadlock
- Reduces output from 2,300 lines to 50 lines
- Better for subprocess communication

#### parse_pytest_output(output: str) -> Dict[str, int]

Parse pytest output for test counts.

**Parameters**:
- output (str): pytest stdout

**Returns**: Dictionary with "passed", "failed", "errors", "skipped" counts

#### validate_red_phase(test_result: Dict[str, Any]) -> None

Enforce TDD red phase (tests must fail before implementation).

**Parameters**:
- test_result (Dict): Result from run_tests()

**Raises**:
- AssertionError: If tests pass prematurely (red phase not satisfied)

**Purpose**:
- Called before implementation starts
- Ensures test file is valid (has tests, no syntax errors)
- Ensures tests actually fail before code written

#### detect_syntax_errors(pytest_output: str) -> Tuple[bool, List[str]]

Detect and extract syntax errors from pytest output.

**Parameters**:
- pytest_output (str): pytest stderr or combined output

**Returns**: Tuple of (has_errors, error_messages)

**Error Types**:
- SyntaxError
- ImportError
- IndentationError
- NameError

#### validate_test_syntax(test_result: Dict[str, Any]) -> None

Validate test file syntax and raise if errors detected.

**Parameters**:
- test_result (Dict): Result from run_tests()

**Raises**:
- RuntimeError: If syntax errors detected

**Used By**:
- TDD red phase to verify test file is syntactically valid

#### run_validation_gate(test_path: Path, timeout: int = 300) -> Dict[str, Any]

Run complete validation gate (all tests must pass).

**Parameters**:
- test_path (Path): Path to test directory or file
- timeout (int): Timeout in seconds

**Returns**: Dictionary with gate_passed, tests_passed, syntax_valid, coverage_valid, error_count, passed, failed, message

**Pre-commit Checks**:
- All tests must pass
- No syntax errors
- Coverage threshold met (if configured)
- No test collection errors

#### validate_coverage(coverage_output: str, threshold: float = 80.0) -> None

Validate code coverage threshold.

**Parameters**:
- coverage_output (str): Coverage output from pytest --cov
- threshold (float): Minimum coverage percentage (default 80%)

**Raises**:
- AssertionError: If coverage below threshold

### Test Coverage

**Test File**: tests/unit/lib/test_test_validator.py (668 lines, 33 tests)

**Coverage Areas**:
- Test execution (pytest integration, timeout handling)
- Output parsing (pass/fail/error counts)
- TDD red phase validation
- Syntax error detection
- Validation gate (pre-commit checks)
- Coverage threshold validation
- Error handling (pytest not found, timeout, syntax errors)

**Target**: 90 percent coverage

### Used By

- test-master agent - TDD validation during /implement
- /implement command - Pre-commit quality gate

### Related Issues

- GitHub Issue #161 - Enhanced test-master for 3-tier test coverage
- GitHub Issue #90 - Minimal pytest verbosity (--tb=line -q)

### Related Components

**Dependencies**:
- pytest (external) - Test execution
- pytest-cov (optional) - Coverage measurement
- subprocess module (stdlib) - Command execution

**Used By**:
- test_tier_organizer.py - After test organization
- acceptance_criteria_parser.py - Works with parsed criteria


---

## 56. tech_debt_detector.py (759 lines, v1.0.0 - Issue #162)

**Purpose**: Proactive code quality issue detection with severity classification.

**Module**: plugins/autonomous-dev/lib/tech_debt_detector.py

**Problem Solved**:
- Reviewers need structured detection of common code quality issues
- Manual inspection of large files, circular imports, dead code is error-prone
- Need severity levels to distinguish blocking issues from warnings
- Need integration point for reviewer checklist

**Solution**:
- 7 detection methods for different tech debt patterns
- Severity enum (CRITICAL, HIGH, MEDIUM, LOW)
- Dataclass-based issue representation for structured results
- Convenience function for one-shot project scanning
- Path traversal prevention for security

### Classes

#### Severity

Enumeration for tech debt issue severity levels.

**Values**:
- CRITICAL (4) - Blocks workflow (exit code 1 in hooks)
- HIGH (3) - Warning only (exit code 0, show message)
- MEDIUM (2) - Informational (tracked but not blocking)
- LOW (1) - Minor issues (low priority)

#### TechDebtIssue

Dataclass representing a single tech debt issue.

**Attributes**:
- category (str): Type of issue (e.g., "large_file", "circular_import")
- severity (Severity): Severity level
- file_path (str): Path to affected file
- metric_value (int): Measured value (e.g., LOC count, complexity score)
- threshold (int): Threshold that was exceeded
- message (str): Human-readable description
- recommendation (str): Suggested fix

#### TechDebtReport

Dataclass aggregating all detected issues.

**Attributes**:
- issues (List[TechDebtIssue]): All detected issues
- counts (Dict[Severity, int]): Count by severity level
- blocked (bool): True if CRITICAL issues found

### Detection Methods

#### detect_large_files() -> List[TechDebtIssue]

Identify files exceeding size thresholds.

**Thresholds**:
- 1500+ LOC: CRITICAL
- 1000-1499 LOC: HIGH

**Returns**: List of issues for oversized files

**Use Case**: Large files indicate monolithic design, harder to test and maintain

#### detect_circular_imports() -> List[TechDebtIssue]

Detect import cycles via AST analysis (Python files only).

**Algorithm**: Build import graph, detect cycles using DFS

**Returns**: List of issues for circular dependencies

**Use Case**: Circular imports cause initialization issues, indicate tight coupling

#### detect_red_test_accumulation() -> List[TechDebtIssue]

Count RED test markers (failing tests) in codebase.

**Markers**: Lines containing "RED" or "@skip" or "@xfail"

**Thresholds**:
- 20+ RED markers: CRITICAL
- 10-19 RED markers: HIGH

**Returns**: List of issues for accumulated failed tests

**Use Case**: Accumulating RED tests indicate feature rot, incomplete implementation

#### detect_config_proliferation() -> List[TechDebtIssue]

Identify scattered configuration files.

**Patterns**: .env, .config.json, config.yaml, settings.ini, etc.

**Thresholds**:
- 10+ config files: CRITICAL
- 5-9 config files: HIGH

**Returns**: List of issues for config sprawl

**Use Case**: Config proliferation makes setup complex, increases errors

#### detect_duplicate_directories() -> List[TechDebtIssue]

Find directories with similar names suggesting duplication.

**Patterns**: utils, util, helpers, helper; config, configs, configuration, etc.

**Returns**: List of issues for naming inconsistencies

**Use Case**: Duplicate directories indicate unclear organization

#### detect_dead_code() -> List[TechDebtIssue]

Identify unused imports and function definitions.

**Methods**:
- Unused imports: Import statements with no references
- Unused functions: Function definitions with no calls (conservative approach)

**Returns**: List of issues for dead code

**Use Case**: Dead code accumulates, adds noise, increases maintenance burden

#### calculate_complexity() -> List[TechDebtIssue]

Measure McCabe cyclomatic complexity using radon library (optional dependency).

**Thresholds** (per function):
- 15+ complexity: CRITICAL
- 10-14 complexity: HIGH

**Returns**: List of issues for overly complex functions

**Use Case**: High complexity indicates functions doing too much, harder to test

### Methods

#### __init__(project_root: Path)

Initialize detector with project root path.

**Parameters**:
- project_root (Path): Root directory to analyze

**Validation**: Path must exist and be readable

#### analyze() -> TechDebtReport

Run all detection methods and aggregate results.

**Returns**: Aggregated report with all issues and statistics

**Execution Order**:
1. Large files detection
2. Circular imports detection
3. Red test accumulation
4. Config proliferation
5. Duplicate directories
6. Dead code detection
7. Complexity analysis

### Module Functions

#### scan_project(project_root: Path) -> TechDebtReport

Convenience function for one-shot project scanning.

**Parameters**:
- project_root (Path): Root directory to analyze

**Returns**: Complete tech debt report

**Usage Example**:

```
from tech_debt_detector import scan_project

report = scan_project(Path("/path/to/project"))
if report.blocked:
    print("CRITICAL issues found!")
    for issue in report.issues:
        if issue.severity == Severity.CRITICAL:
            print(f"  {issue.message}")
```

### Integration Points

- reviewer agent - Integrated into code review checklist (CHECKPOINT 4.2 in /implement)
- /health-check command - Optional tech debt analysis
- CI/CD pipelines - Pre-commit quality gate

### Security Features

- Path traversal prevention (CWE-22) via security_utils validation
- Symlink resolution for safe path handling (CWE-59)
- Conservative detection logic to minimize false positives
- No arbitrary code execution (AST parsing only, no eval)

### Performance Characteristics

- Large files: O(n) where n = files scanned
- Circular imports: O(V + E) where V = modules, E = imports
- Config proliferation: O(n) glob pattern matching
- Dead code: O(n*m) where m = lines per file
- Complexity: Depends on radon library (typically less than 100ms per file)
- Typical project (1000 files): 2-5 seconds total

### Test Coverage

**Test File**: tests/unit/lib/test_tech_debt_detector.py

**Coverage Areas**:
- Severity enumeration and values
- Issue dataclass creation and validation
- Large files detection with thresholds
- Circular import detection via AST
- RED test accumulation and counting
- Config proliferation detection
- Duplicate directory detection
- Dead code detection (imports and functions)
- Complexity calculation with radon
- Report aggregation and statistics
- Security (path validation, traversal prevention)
- Error handling (missing files, invalid paths, unreadable directories)

**Target**: 90 percent coverage

### Used By

- reviewer agent - Code quality analysis during /implement
- /health-check command - Optional tech debt scanning
- CI/CD integration - Pre-commit quality gates

### Related Issues

- GitHub Issue #162 - Tech Debt Detection System
- GitHub Issue #141 - Workflow discipline (guides usage of detector)

### Related Components

**Dependencies**:
- pathlib - Path handling
- ast - Python import graph analysis
- radon (optional) - McCabe complexity calculation
- security_utils.py - Path validation (CWE-22, CWE-59 prevention)

**Used By**:
- reviewer.md agent - Code review checklist integration
- health_check.py hook - Optional tech debt analysis


## 57. scope_detector.py (584 lines, v1.0.0)

**Purpose**: Scope analysis and complexity detection for issue decomposition

**Module**: plugins/autonomous-dev/lib/scope_detector.py

**Exports**:
- EffortSize (enum): T-shirt sizing for effort estimation (XS/S/M/L/XL)
- ComplexityAnalysis (dataclass): Results of complexity analysis
- analyze_complexity() - Main analysis function
- estimate_atomic_count() - Estimate number of sub-issues
- generate_decomposition_prompt() - Generate decomposition prompt
- load_config() - Load configuration with fallback

### Key Data Structures

#### EffortSize (Enum)

T-shirt sizing for effort estimation:
- XS: Less than 1 hour
- S: 1-4 hours
- M: 4-8 hours
- L: 1-2 days
- XL: More than 2 days

#### ComplexityAnalysis (Dataclass)

Results of complexity analysis with attributes:
- effort: Estimated effort size (EffortSize enum)
- indicators: Dictionary of detected indicators (keywords, anti-patterns)
- needs_decomposition: Whether request should be broken into sub-issues
- confidence: Confidence score for analysis (0.0-1.0)

### Main Functions

#### analyze_complexity(request, config=None) - Main analysis

Signature: analyze_complexity(request: str, config: Optional[Dict] = None) -> ComplexityAnalysis

- Purpose: Analyze complexity of a feature request
- Parameters:
  - request (str): Feature request text to analyze
  - config (dict|None): Optional configuration (uses defaults if None)
- Returns: ComplexityAnalysis with effort, indicators, decomposition flag, confidence
- Features:
  - Keyword detection: Identifies high/medium complexity indicators
  - Anti-pattern detection: Finds conjunctions, multiple file types, vague terms
  - Effort estimation: Maps indicators to t-shirt sizes
  - Confidence calculation: Scores analysis reliability (0.0-1.0)
  - Decomposition determination: Flags if request needs breaking into sub-issues
- Algorithm:
  1. Detect keywords (complexity_high, complexity_medium, vague, domain, breadth)
  2. Detect anti-patterns (conjunctions, file types, vague keywords)
  3. Estimate effort size based on indicators
  4. Calculate confidence score
  5. Determine if decomposition needed (effort >= threshold OR excessive conjunctions)
- Edge Cases:
  - Empty/None/whitespace input: Returns M effort with low confidence
  - Very long input (>10K chars): Truncated with warning
  - Invalid threshold: Defaults to M

#### estimate_atomic_count(request, complexity, config=None) - Sub-issue count

Signature: estimate_atomic_count(request: str, complexity: ComplexityAnalysis, config: Optional[Dict] = None) -> int

- Purpose: Estimate number of atomic sub-issues needed
- Parameters:
  - request (str): Original feature request
  - complexity (ComplexityAnalysis): Result from analyze_complexity()
  - config (dict|None): Optional configuration
- Returns: int - Number of sub-issues (1-5 default)
- Mapping:
  - XS/S effort: 1 (no decomposition needed)
  - M effort: 3 sub-issues
  - L effort: 4 sub-issues
  - XL effort: 5 sub-issues

#### generate_decomposition_prompt(request, count) - Decomposition prompt

Signature: generate_decomposition_prompt(request: str, count: int) -> str

- Purpose: Generate prompt for decomposing request into atomic sub-issues
- Parameters:
  - request (str): Original feature request
  - count (int): Target number of sub-issues
- Returns: str - Formatted prompt with decomposition instructions
- Features:
  - Preserves original request context
  - Specifies size constraints (1-4 hours per sub-issue)
  - Minimizes inter-issue dependencies
  - Includes testability requirement

#### load_config(config_path=None) - Configuration loading

Signature: load_config(config_path: Optional[Path] = None) -> Dict[str, Any]

- Purpose: Load configuration from file with fallback to defaults
- Parameters: config_path (Path|None): Path to JSON config file
- Returns: Configuration dictionary with all required fields
- Features:
  - Fallback to DEFAULT_CONFIG if file not found
  - Deep merging of keyword_sets and anti_patterns with defaults
  - Graceful error handling (logs errors, uses defaults)

### Configuration

Default Configuration:
- decomposition_threshold: "M" - Minimum effort to trigger decomposition
- max_atomic_issues: 5 - Maximum number of sub-issues
- keyword_sets: Categorized keywords for detection
  - complexity_high: refactor, redesign, migrate, overhaul, rewrite, architect
  - complexity_medium: add, implement, create, build, integrate
  - vague_indicators: improve, enhance, optimize, better, faster, cleaner
  - domain_terms: authentication, oauth, saml, ldap, jwt, api, database, security
  - breadth_indicators: complete, entire, full, comprehensive, system, platform
- anti_patterns:
  - conjunction_limit: 3 - Max "and" conjunctions before flagging
  - file_type_limit: 3 - Max file types before flagging breadth

### Detection Functions

#### detect_keywords(text, keyword_sets)

- Purpose: Detect and count keyword occurrences
- Returns: dict - Mapping of category to match count
- Features: Case-insensitive matching, word boundaries, domain term partial matches

#### detect_anti_patterns(text, anti_patterns)

- Purpose: Detect anti-patterns in feature requests
- Returns: dict with conjunction_count, file_types, vague_keywords
- Features: Identifies scope creep, breadth complexity, unclear requirements

### Performance

- Time Complexity: O(n) where n = request length
- Typical: <10ms for average request (100-500 chars)
- Worst case: <100ms for 10K+ char requests

### Test Coverage

Test File: tests/unit/lib/test_scope_detector.py

Coverage: 49 test cases covering:
- Keyword detection (case insensitivity, word boundaries, partial matches)
- Anti-pattern detection (conjunctions, file types, vague keywords)
- Effort estimation (all effort sizes, edge cases, complexity boosters)
- Confidence calculation (high/low confidence cases)
- Main analysis function (complex features, simple features)
- Atomic count estimation (all effort sizes, respecting limits)
- Decomposition prompt generation (prompt structure, clarity)
- Configuration loading (defaults, file loading, error handling)
- Security (input validation, graceful degradation)

Target: 90+ percent coverage

### Used By

- issue-creator agent - Scope detection and decomposition
- Feature request analysis workflows
- Issue decomposition planning

### Related Components

Dependencies:
- pathlib - Path handling
- json - Configuration loading
- re - Regular expression matching
- logging - Debug logging
- dataclasses - Data structures
- enum - Effort size enumeration

---

## 58. completion_verifier.py (415 lines, v1.0.0)

**Purpose**: Pipeline completion verification with intelligent retry and circuit breaker

**Problem**: Pipeline agents may fail to complete, but users have no way to detect and retry incomplete work

**Solution**: Comprehensive completion verification system with exponential backoff and state persistence

### Data Structures

#### VerificationResult

Immutable verification outcome.

**Attributes**:
- `complete` (bool): True if all 8 agents completed
- `agents_found` (List[str]): Names of agents found in session
- `missing_agents` (List[str]): Names of agents not found (empty if complete)
- `verification_time_ms` (float): Time taken to verify (milliseconds)

**Features**:
- Immutable (frozen dataclass)
- Preserves agent order from EXPECTED_AGENTS constant
- Always includes verification timing for performance monitoring

#### LoopBackState

Mutable retry state with persistence.

**Attributes**:
- `session_id` (str): Session identifier for correlation
- `attempt_count` (int): Current retry attempt number (0 = initial check)
- `max_attempts` (int): Maximum allowed attempts (default: 5)
- `consecutive_failures` (int): Count of consecutive failures (0 = success, increments on failure)
- `circuit_breaker_open` (bool): True if circuit breaker triggered (after 3 consecutive failures)
- `last_attempt_timestamp` (Optional[str]): ISO 8601 timestamp of last attempt
- `missing_agents` (List[str]): Agents not found in last verification

**Features**:
- Serializable to JSON (for state persistence)
- Tracks attempt history for audit logging
- Circuit breaker integration (prevents infinite retries)
- Supports graceful degradation with fallback defaults

### Functions

#### verify_pipeline_completion(session_id, session_data=None, state_dir=None)

Verify that all 8 expected agents completed.

**Signature**:
```python
def verify_pipeline_completion(
    session_id: str,
    session_data: Optional[Dict] = None,
    state_dir: Optional[Path] = None
) -> VerificationResult
```

**Parameters**:
- `session_id` (str): Session identifier
- `session_data` (Optional[Dict]): Pre-loaded session data for testing (bypasses file read)
- `state_dir` (Optional[Path]): State directory (defaults to `./.claude`)

**Returns**: `VerificationResult` with completion status and missing agents

**Expected Agents** (in order):
1. researcher-local
2. researcher-web
3. planner
4. test-master
5. implementer
6. reviewer
7. security-auditor
8. doc-master

**Features**:
- Loads session file from `.claude/sessions/{session_id}.json`
- Extracts agent names from session data
- Compares against EXPECTED_AGENTS constant
- Preserves agent order in results
- Graceful degradation on file not found (returns incomplete)
- Handles JSON parse errors gracefully

**Security**:
- Path validation for state_dir (CWE-22 prevention)
- No execution of code in session data
- Read-only access to session files

**Performance**:
- Typical: <10ms for average session file (500-1000 bytes)
- Worst case: <50ms for large session files (10K+ bytes)

#### should_retry(state: LoopBackState) -> bool

Check if retry should proceed (under max attempts and circuit breaker not triggered).

**Parameters**:
- `state` (LoopBackState): Current loop-back state

**Returns**: True if retry allowed, False otherwise

**Logic**:
1. Check circuit breaker first (if 3+ consecutive failures, return False)
2. Check if circuit breaker open flag set (return False)
3. Check if attempt_count >= max_attempts (return False)
4. Otherwise return True

**Features**:
- Prevents infinite retry loops via circuit breaker
- Prevents resource exhaustion via max attempt limit
- Checks circuit breaker before max attempts check (fail-fast)

#### get_next_retry_delay(attempt: int) -> float

Calculate exponential backoff delay for next retry.

**Parameters**:
- `attempt` (int): Current attempt number (0-based)

**Returns**: Delay in milliseconds as float

**Backoff Schedule**:
- Attempt 0: 100ms (BASE_RETRY_DELAY_MS)
- Attempt 1: 200ms (100 * 2^1)
- Attempt 2: 400ms (100 * 2^2)
- Attempt 3: 800ms (100 * 2^3)
- Attempt 4: 1600ms (100 * 2^4)
- Max: 5000ms (BACKOFF_MAX_MS, capped)

**Formula**:
```
delay = BASE_RETRY_DELAY_MS * (BACKOFF_MULTIPLIER ^ attempt)
delay = min(delay, BACKOFF_MAX_MS)
```

**Features**:
- Exponential backoff prevents server overload on transient failures
- Capped at 5000ms to prevent excessive delays
- Graceful degradation if attempt < 0 (returns BASE_RETRY_DELAY_MS)

#### load_loop_back_state(state_file: Path) -> Optional[LoopBackState]

Load retry state from JSON file.

**Parameters**:
- `state_file` (Path): Path to loop-back state JSON file

**Returns**: `LoopBackState` if file exists and valid, None otherwise

**Features**:
- Handles file not found gracefully (returns None)
- Handles JSON parse errors gracefully (logs error, returns None)
- Deserializes LoopBackState from JSON
- Validates required fields present

**Security**:
- Path validation for state_file
- No code execution from loaded state

#### save_loop_back_state(state: LoopBackState, state_file: Path) -> bool

Save retry state to JSON file.

**Parameters**:
- `state` (LoopBackState): State to save
- `state_file` (Path): Path to write state file

**Returns**: True if save succeeded, False otherwise

**Features**:
- Atomic write via tempfile + rename pattern
- Creates parent directories if needed
- Handles permission errors gracefully
- Updates timestamp on save

**Security**:
- Atomic write prevents corruption on interruption
- No sensitive data in state file (session IDs only)

#### clear_loop_back_state(state_file: Path) -> bool

Delete retry state file after successful completion.

**Parameters**:
- `state_file` (Path): Path to state file to delete

**Returns**: True if deleted or doesn't exist, False if error

**Features**:
- Idempotent (returns True if file doesn't exist)
- Handles permission errors gracefully
- Logs all operations for audit trail

#### create_loop_back_checkpoint(session_id: str, missing_agents: List[str], state_dir: Path) -> bool

Create a loop-back checkpoint for incomplete work.

**Parameters**:
- `session_id` (str): Session identifier
- `missing_agents` (List[str]): List of agent names not found
- `state_dir` (Path): Directory to save state

**Returns**: True if checkpoint created, False otherwise

**Features**:
- Creates LoopBackState with initial values
- Sets attempt_count = 0 (fresh retry attempt)
- Initializes consecutive_failures = 0
- Records timestamp of checkpoint creation
- Saves state atomically

### CompletionVerifier Class

Main verification engine with session file handling.

#### __init__(session_id: str, state_dir: Optional[Path] = None)

Initialize verifier for a session.

**Parameters**:
- `session_id` (str): Session identifier
- `state_dir` (Optional[Path]): State directory (defaults to `./.claude`)

**Features**:
- Stores session_id for later verification
- Resolves state_dir with fallback to `./.claude`
- Prepares state file path (`.claude/loop_back/{session_id}.json`)

#### verify() -> VerificationResult

Run verification check on the session.

**Returns**: `VerificationResult` with completion status

**Features**:
- Calls `verify_pipeline_completion()` with stored session_id
- Returns result for caller to handle retry logic
- Non-blocking (always returns a result)

#### get_retry_state() -> Optional[LoopBackState]

Load current retry state if exists.

**Returns**: `LoopBackState` if state file exists, None otherwise

**Features**:
- Loads from persistent state file
- Returns None if first check or state cleared

#### update_retry_state(state: LoopBackState) -> None

Update retry state with current attempt.

**Parameters**:
- `state` (LoopBackState): State to persist

**Features**:
- Increments attempt_count
- Updates timestamp
- Saves to disk atomically

#### clear_state_on_success() -> bool

Delete state file after successful completion.

**Returns**: True if cleared or doesn't exist, False if error

**Features**:
- Idempotent (safe to call multiple times)
- Graceful degradation on permission errors

#### get_state() -> Optional[LoopBackState]

Alias for `get_retry_state()` for consistency with other APIs.

**Returns**: `LoopBackState` if exists, None otherwise

### Configuration Constants

```python
# Expected agents in pipeline order (8 total)
EXPECTED_AGENTS = [
    "researcher-local",
    "researcher-web",
    "planner",
    "test-master",
    "implementer",
    "reviewer",
    "security-auditor",
    "doc-master"
]

# Retry configuration
MAX_RETRY_ATTEMPTS = 5
CIRCUIT_BREAKER_THRESHOLD = 3
BASE_RETRY_DELAY_MS = 100
BACKOFF_BASE_MS = 100
BACKOFF_MULTIPLIER = 2
BACKOFF_MAX_MS = 5000
```

### Usage Example

Basic verification with retry logic:

```python
from pathlib import Path
from completion_verifier import CompletionVerifier, should_retry
import time

# Initialize verifier
verifier = CompletionVerifier(session_id="session_123")

# Check if complete
result = verifier.verify()
if result.complete:
    print(f"Pipeline complete: {len(result.agents_found)} agents")
    verifier.clear_state_on_success()
else:
    print(f"Missing agents: {result.missing_agents}")

    # Load or create retry state
    state = verifier.get_retry_state()
    if state is None:
        # First check - create new state
        from completion_verifier import create_loop_back_checkpoint
        create_loop_back_checkpoint("session_123", result.missing_agents, Path(".claude"))
        state = verifier.get_retry_state()

    # Check if should retry
    if should_retry(state):
        # Wait with exponential backoff
        from completion_verifier import get_next_retry_delay
        delay_ms = get_next_retry_delay(state.attempt_count)
        time.sleep(delay_ms / 1000)

        # Update attempt counter
        state.attempt_count += 1
        state.last_attempt_timestamp = datetime.now().isoformat()
        verifier.update_retry_state(state)

        # Retry verification (would be called again by hook)
        print(f"Retrying verification (attempt {state.attempt_count}/{state.max_attempts})")
    else:
        print(f"Max retries exceeded or circuit breaker open")
        # Handle permanent failure
```

### Security Considerations

**Path Traversal (CWE-22)**:
- All file operations validated via `security_utils.validate_path()`
- State files isolated to `.claude/loop_back/` directory
- Session IDs must match `^[a-zA-Z0-9_-]+$` pattern

**Denial of Service**:
- Circuit breaker prevents infinite retry loops
- Max attempt limit prevents resource exhaustion
- Exponential backoff prevents server overload

**Data Integrity**:
- Atomic writes via tempfile + rename prevent corruption
- State files contain only non-sensitive metadata

### Test Coverage

Test Files:
- `tests/unit/lib/test_completion_verifier.py` (26 tests)
- `tests/unit/hooks/test_verify_completion_hook.py` (25 tests)

Coverage: 51 test cases covering:
- Verification logic (all 8 agents, missing agents)
- Circuit breaker (opening/closing, state persistence)
- Exponential backoff (all retry attempts, max delay capping)
- State persistence (load/save, file handling)
- Error handling (invalid session, file not found, JSON errors)
- Edge cases (empty session, duplicate agents, agent ordering)
- Integration with hook lifecycle

Target: 90+% coverage

### Used By

- verify_completion.py - SubagentStop hook for pipeline completion
- /implement pipeline - Verifies all agents completed
- Batch processing - Validates pipeline completion per feature

### Related Components

Dependencies:
- pathlib - Path handling
- json - State serialization
- time - Performance timing
- logging - Audit logging
- datetime - Timestamp recording
- dataclasses - Data structures

See Also:
- `plugins/autonomous-dev/hooks/verify_completion.py` - Hook integration
- `docs/HOOKS.md` - Hook documentation
- GitHub Issue #170 - Feature tracking

---


## 59. hook_exit_codes.py (139 lines, v4.0.0+)

**Purpose**: Standardized exit code constants and lifecycle constraints for all hooks

**Location**: `plugins/autonomous-dev/lib/hook_exit_codes.py`

### Overview

Defines symbolic constants for hook exit codes and lifecycle constraints that determine which exit codes are valid for different hook types. Prevents hardcoded exit codes scattered throughout hook implementations.

### Constants

#### Exit Code Constants

```python
EXIT_SUCCESS = 0  # Operation succeeded, continue workflow normally
EXIT_WARNING = 1  # Non-critical issue detected, continue workflow with warning
EXIT_BLOCK = 2    # Critical issue detected, block workflow (if lifecycle supports it)
```

### Lifecycle Constraints

Defines allowed exit codes for each hook lifecycle:

```python
LIFECYCLE_CONSTRAINTS = {
    "PreToolUse": {
        "allowed_exits": [EXIT_SUCCESS],
        "can_block": False,
        "description": "PreToolUse hooks run AFTER user approved tool execution..."
    },
    "SubagentStop": {
        "allowed_exits": [EXIT_SUCCESS],
        "can_block": False,
        "description": "SubagentStop hooks run AFTER agent completes..."
    },
    "PreSubagent": {
        "allowed_exits": [EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK],
        "can_block": True,
        "description": "PreSubagent hooks run BEFORE agent spawn..."
    },
}
```

### Functions

#### `can_lifecycle_block(lifecycle: str) -> bool`

**Purpose**: Check if a lifecycle can block workflow

**Parameters**:
- `lifecycle` (str): Hook lifecycle name (PreToolUse, SubagentStop, PreSubagent, etc.)

**Returns**: `bool` - True if lifecycle can exit with EXIT_BLOCK (2)

**Raises**: `KeyError` if lifecycle not defined

**Examples**:
```python
>>> can_lifecycle_block("PreToolUse")
False

>>> can_lifecycle_block("PreSubagent")
True
```

#### `is_exit_allowed(lifecycle: str, exit_code: int) -> bool`

**Purpose**: Check if an exit code is allowed for a given lifecycle

**Parameters**:
- `lifecycle` (str): Hook lifecycle name
- `exit_code` (int): Exit code to check (0, 1, or 2)

**Returns**: `bool` - True if exit code is allowed for lifecycle

**Raises**: `KeyError` if lifecycle not defined

**Examples**:
```python
>>> is_exit_allowed("PreToolUse", EXIT_BLOCK)
False

>>> is_exit_allowed("PreSubagent", EXIT_BLOCK)
True

>>> is_exit_allowed("SubagentStop", EXIT_SUCCESS)
True
```

#### `get_lifecycle_description(lifecycle: str) -> str`

**Purpose**: Get description of lifecycle constraints

**Parameters**:
- `lifecycle` (str): Hook lifecycle name

**Returns**: `str` - Description explaining lifecycle constraints and valid exit codes

**Raises**: `KeyError` if lifecycle not defined

**Examples**:
```python
>>> desc = get_lifecycle_description("PreToolUse")
>>> print(desc)
PreToolUse hooks run before tool execution. They MUST always exit 0...
```

### Lifecycle Breakdown

#### PreToolUse
- **When**: Runs before tool execution
- **Allowed exits**: EXIT_SUCCESS (0) only
- **Can block**: No
- **Why**: User already approved tool, cannot retroactively prevent execution
- **Use**: Logging, permission checks, security validation (all non-blocking)

#### SubagentStop
- **When**: Runs after agent completes
- **Allowed exits**: EXIT_SUCCESS (0) only
- **Can block**: No
- **Why**: Agent work already done, cannot block after completion
- **Use**: Post-processing (git commits), logging, completion verification

#### PreSubagent
- **When**: Runs before agent spawns
- **Allowed exits**: EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK
- **Can block**: Yes
- **Why**: Agent hasn't run yet, can prevent invalid work from starting
- **Use**: Quality gates, validation before expensive operations

#### PreCommit
- **When**: Runs before commit
- **Allowed exits**: EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK
- **Can block**: Yes
- **Why**: Commit hasn't happened yet, can enforce requirements
- **Use**: Code quality validation, test coverage checks, lint rules

#### PostCommit
- **When**: Runs after commit
- **Allowed exits**: EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK
- **Can block**: Yes (won't affect already-committed changes)
- **Use**: Notifications, statistics updates

#### UserPromptSubmit
- **When**: Runs when user submits prompt
- **Allowed exits**: EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK
- **Can block**: Yes
- **Why**: Submission not yet processed, can prevent invalid submissions
- **Use**: Input validation, alignment checks

### Usage Examples

**Basic Success Pattern**:
```python
from hook_exit_codes import EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK
import sys

if validation_passes:
    sys.exit(EXIT_SUCCESS)  # Exit 0 - Workflow continues
```

**Lifecycle-Aware Exit Code**:
```python
from hook_exit_codes import (
    EXIT_SUCCESS, EXIT_WARNING, EXIT_BLOCK,
    can_lifecycle_block, get_lifecycle_description
)
import os
import sys

lifecycle = os.environ.get("HOOK_LIFECYCLE", "PreCommit")

if critical_issue_detected:
    if can_lifecycle_block(lifecycle):
        sys.exit(EXIT_BLOCK)  # Exit 2 - Block workflow
    else:
        # This lifecycle cannot block - use warning instead
        print(f"WARNING: {get_lifecycle_description(lifecycle)}")
        sys.exit(EXIT_WARNING)  # Exit 1 - Continue with warning
else:
    sys.exit(EXIT_SUCCESS)
```

**Validation Check Pattern**:
```python
from hook_exit_codes import is_exit_allowed, LIFECYCLE_CONSTRAINTS
import sys

lifecycle = "PreToolUse"
proposed_exit = 2  # EXIT_BLOCK

if not is_exit_allowed(lifecycle, proposed_exit):
    print(f"ERROR: {lifecycle} cannot exit {proposed_exit}")
    print(f"Allowed exits: {LIFECYCLE_CONSTRAINTS[lifecycle]['allowed_exits']}")
    sys.exit(1)
```

### Design Benefits

1. **Semantic Clarity**: `EXIT_BLOCK` clearer than hardcoded `sys.exit(2)`
2. **Self-Documenting**: Constant names explain intent
3. **Prevents Inversion Bugs**: Harder to accidentally swap exit codes
4. **Centralized Definition**: Single source of truth (not scattered across hooks)
5. **Type Safety**: Import errors caught at startup, not runtime
6. **Lifecycle Validation**: Prevents invalid exit codes for hook type
7. **Discoverability**: Easy to view all constraints via LIFECYCLE_CONSTRAINTS dict

### Constraints

**Important Restrictions**:
- PreToolUse hooks: Must always exit 0 (cannot block)
- SubagentStop hooks: Must always exit 0 (cannot block)
- All other hooks: Can exit 0, 1, or 2

**Why**: PreToolUse and SubagentStop run at moments when blocking is impossible (tool already approved, agent already complete).

### Test Coverage

Test File: `tests/unit/lib/test_hook_exit_codes.py` (23 tests)

Coverage includes:
- **Constants**: Exit code values (0, 1, 2), distinctness, type validation, range validation
- **Lifecycle constraints**: All 3 lifecycles exist, constraints complete, required keys present
- **Allowed exits**: Each lifecycle has proper allowed exits list
- **Can block**: Correctly identifies which lifecycles support blocking
- **Documentation**: Module and constraint descriptions exist
- **Helper functions**: All 3 helper functions work correctly
- **Error cases**: Invalid lifecycles raise KeyError, invalid exits detected
- **Usage patterns**: Common patterns (success, warning, block, lifecycle checks) work

Target: 100% coverage of exit code semantics

### Used By

Hooks throughout autonomous-dev:
- All PreCommit hooks
- All PreSubagent hooks
- All PostCommit hooks
- All UserPromptSubmit hooks

Examples:
- `unified_code_quality.py` - PreCommit, can block on test failures
- `verify_completion.py` - SubagentStop, must exit 0
- `auto_tdd_enforcer.py` - PreSubagent, can block on missing tests

### Related

**Documentation**:
- [HOOKS.md - Exit Code Semantics section](HOOKS.md#exit-code-semantics)
- [LIBRARIES.md - Lifecycle Constraints](LIBRARIES.md#lifecycle-constraints)

**Implementation**:
- `plugins/autonomous-dev/lib/hook_exit_codes.py` (139 lines)
- `tests/unit/lib/test_hook_exit_codes.py` (23 tests)

**GitHub**: Feature tracking (Issue TBD)


---

## 60. status_tracker.py (363 lines, v1.0.0 - Issue #174)

**Purpose**: Manages test execution status for pre-commit gate hook (block-at-submit validation).

**Problem**: Need reliable test status tracking across different processes so pre-commit hook can check if tests passed before allowing commit.

**Solution**: Provides JSON-based status persistence with cross-process communication between test runners and pre-commit gate hook.

### API

#### `get_status_file_path() -> Path`

**Purpose**: Get path to test status JSON file

**Returns**: Path object pointing to test-status.json in temp directory

**Location**: /tmp/.autonomous-dev/test-status.json (Linux/macOS) or system temp (Windows)

**Security**:
- Returns absolute path (prevents relative path attacks)
- No user input in path construction
- Path is deterministic and not user-controllable

**Examples**:
```python
from status_tracker import get_status_file_path
path = get_status_file_path()
assert path.is_absolute()
assert ".autonomous-dev" in str(path)
```

#### `write_status(passed: bool, timestamp: Optional[str] = None) -> None`

**Purpose**: Write test execution status to JSON file

**Parameters**:
- `passed` (bool): True if tests passed, False if failed
- `timestamp` (str, optional): ISO 8601 timestamp (defaults to current time)

**Raises**:
- `ValueError`: If timestamp format is invalid
- `OSError`: If file cannot be written (permissions, disk full, etc.)

**Security**:
- Atomic writes: Write to temp file, then rename
- Secure permissions: 0600 (user-only read/write)
- Path validation: Prevents traversal and symlink attacks (CWE-22, CWE-59)
- Input validation: Validates timestamp format

**Status File Format**:
```json
{
  "passed": true,
  "timestamp": "2026-01-01T12:00:00Z",
  "last_run": "2026-01-01T12:00:00.123456Z"
}
```

**Usage Examples**:
```python
from status_tracker import write_status

# After successful test run (auto-timestamp)
write_status(passed=True)

# After failed test run (auto-timestamp)
write_status(passed=False)

# With explicit timestamp
write_status(passed=True, timestamp="2026-01-01T12:00:00Z")
```

#### `read_status() -> Dict[str, Any]`

**Purpose**: Read test execution status from JSON file

**Returns**: Dictionary with keys:
- `passed` (bool): True if tests passed, False otherwise
- `timestamp` (str | None): ISO 8601 timestamp of test run
- `last_run` (str | None): ISO 8601 timestamp of status update

**Graceful Degradation**:
- Missing file: Returns safe default (passed=False)
- Corrupted JSON: Returns safe default (passed=False)
- Missing fields: Adds default values
- Invalid types: Returns safe default (passed=False)
- Permission errors: Returns safe default (passed=False)
- Symlinks detected: Returns safe default (passed=False)

**Security**:
- Validates path before reading (prevents traversal - CWE-22)
- Checks for symlinks (prevents attack - CWE-59)
- Handles permission errors gracefully
- Never exposes sensitive data from corrupted files

**Usage Examples**:
```python
from status_tracker import read_status

status = read_status()
if status["passed"]:
    print("Tests passed!")
else:
    print("Tests failed or not run")

# Check timestamp
if status["timestamp"]:
    print(f"Last run: {status['timestamp']}")
```

### Integration

**With pre_commit_gate hook**:
```python
# pre_commit_gate.py reads status to decide whether to block
from status_tracker import read_status

status = read_status()
if status["passed"]:
    sys.exit(EXIT_SUCCESS)  # Allow commit
else:
    sys.exit(EXIT_BLOCK)    # Block commit
```

**With test-master agent in /implement**:
```python
# test-master writes status after running tests
from status_tracker import write_status

# After all tests pass
write_status(passed=True)

# Or if tests fail
write_status(passed=False)
```

### Configuration

**Environment Variables**: None (file path is deterministic)

**Status File Permissions**: 0600 (user-only read/write)

**ISO 8601 Timestamps**: All timestamps use UTC timezone for cross-platform compatibility

### Error Handling

**Atomic Write Strategy**:
- Write to temporary file first
- Rename temp file to target atomically (prevents corruption)
- Clean up temp file on error
- Raises OSError with context if write fails

**Safe Defaults on Read Errors**:
- Any read error returns {"passed": False, ...} (fail-safe)
- Prevents false positives (incorrect "tests passed" claims)
- Never blocks on missing/corrupted status
- Clear error messages in logs for debugging

### Examples

**Basic workflow**:
```python
# 1. Test runner writes status after execution
from status_tracker import write_status
import subprocess

result = subprocess.run(["pytest"], capture_output=True)
if result.returncode == 0:
    write_status(passed=True)
else:
    write_status(passed=False)

# 2. Pre-commit hook reads status
from status_tracker import read_status

status = read_status()
if status["passed"]:
    # Allow commit
    sys.exit(0)
else:
    # Block commit
    sys.exit(2)
```

**With /implement pipeline**:
```python
# test-master agent runs tests and writes status
write_status(passed=all_tests_pass)

# When user commits, pre_commit_gate checks status
# Status is already written by test-master
# Gate blocks or allows based on status
```

### Test Coverage

Test File: tests/unit/lib/status_tracker.py

Coverage includes:
- **Get path**: Path is absolute, contains expected directory
- **Write status**: File created, permissions set, JSON valid
- **Read status**: Returns correct structure, handles missing file
- **Atomic writes**: Temp file cleanup on error
- **Security**: Symlink detection, path validation, permission checks
- **Graceful degradation**: Corrupted JSON handled, missing fields defaulted
- **Timestamp validation**: Valid ISO 8601 accepted, invalid rejected
- **Cross-process**: Multiple writes/reads work correctly

Target: 95% coverage of core functionality

### Used By

- `pre_commit_gate.py` hook - Reads status to determine commit permission
- `test-master` agent in `/implement` - Writes status after test execution
- Manual pytest runs - Users can write status via CLI

### Related

**Documentation**:
- [HOOKS.md - PreCommit hooks](HOOKS.md#precommit)
- [TESTING-STRATEGY.md - TDD workflow](TESTING-STRATEGY.md)

**Implementation**:
- `plugins/autonomous-dev/lib/status_tracker.py` (363 lines)
- `plugins/autonomous-dev/hooks/pre_commit_gate.py` (299 lines)
- `tests/unit/lib/status_tracker.py`

**GitHub**: Issue #174 - Block-at-submit hook with test status tracking


## 61. worktree_manager.py (684 lines, v1.0.0 - Issue #178)

**Purpose**: Safe git worktree isolation for parallel feature development

**Problem**: Developers need to work on multiple features in parallel without affecting the main branch. Standard branching requires switching contexts repeatedly.

**Solution**: Comprehensive git worktree management system with automatic isolation, collision detection, and safe merge operations.

### Features

- **Create worktrees**: Spawn isolated working directories for each feature
- **List worktrees**: Display all active worktrees with metadata (status, branch, commit, creation time)
- **Delete worktrees**: Remove worktrees with optional force flag for uncommitted changes
- **Merge worktrees**: Merge worktree branches back to target branch with conflict detection
- **Prune stale**: Automatically clean up orphaned/old worktrees (configurable age threshold)
- **Path queries**: Get worktree path by feature name
- **Security**: Path traversal prevention (CWE-22), command injection prevention (CWE-78), symlink resolution (CWE-59)
- **Graceful degradation**: Failures don't crash, return error tuples for safe handling
- **Atomic operations**: Collision detection with timestamp suffix for duplicate names
- **Parallel development**: Work on 5+ features simultaneously without branch switching

### Main Components

#### Data Classes

**WorktreeInfo**: Metadata about a worktree

- name: str - Feature name
- path: Path - Absolute path to worktree
- branch: Optional[str] - Branch name (None if detached)
- commit: str - Short commit SHA
- status: str - 'active', 'stale', or 'detached'
- created_at: datetime - Creation timestamp

**MergeResult**: Result of merge operation

- success: bool - Whether merge completed
- conflicts: List[str] - Files with conflicts
- merged_files: List[str] - Successfully merged files
- error_message: str - Error details if failed

#### Main Functions

#### create_worktree(feature_name, base_branch='master') -> Tuple[bool, Union[Path, str]]

- **Purpose**: Create isolated worktree for feature development
- **Parameters**:
  - feature_name (str): Feature name (alphanumeric, hyphens, underscores, dots only)
  - base_branch (str): Base branch to branch from (default: 'master')
- **Returns**: Tuple of (success, result) where result is Path on success or error_message on failure
- **Security**: Validates feature name (CWE-22, CWE-78), uses subprocess list args (no shell), resolves symlinks
- **Collision Handling**: If feature name exists, appends timestamp (YYYYMMDD-HHMMSS)
- **Errors Handled**:
  - Empty/invalid feature name
  - Path traversal attempts
  - Branch already checked out
  - Invalid/missing base branch
  - No disk space
  - Timeout (30s)

#### list_worktrees() -> List[WorktreeInfo]

- **Purpose**: List all git worktrees with metadata
- **Parameters**: None
- **Returns**: List of WorktreeInfo objects (empty list on error)
- **Status Detection**:
  - active: Worktree exists and on a branch
  - stale: Worktree directory doesn't exist
  - detached: Worktree in detached HEAD state
- **Performance**: Uses git porcelain format for efficient parsing

#### delete_worktree(feature_name, force=False) -> Tuple[bool, str]

- **Purpose**: Delete a worktree
- **Parameters**:
  - feature_name (str): Feature name of worktree to delete
  - force (bool): Force deletion even with uncommitted changes (default: False)
- **Returns**: Tuple of (success, message)
- **Validation**: Checks feature name format before deletion
- **Errors Handled**:
  - Worktree not found
  - Uncommitted changes (unless force=True)
  - Permission denied

#### merge_worktree(feature_name, target_branch='master') -> MergeResult

- **Purpose**: Merge worktree branch back to target branch
- **Parameters**:
  - feature_name (str): Feature name to merge
  - target_branch (str): Target branch for merge (default: 'master')
- **Returns**: MergeResult with success/conflicts/merged_files/error_message
- **Merge Flow**:
  1. Validate feature name
  2. Checkout target branch
  3. Merge feature branch
  4. Get list of merged files (if successful)
  5. Detect conflicts (if merge failed)
- **Conflict Detection**: Uses multiple strategies
  - git diff --name-only --diff-filter=U (unmerged)
  - git status --porcelain with status codes (UU, AA, DD, AU, UA, DU, UD)
- **Errors Handled**:
  - Invalid feature name
  - Target branch not found
  - Detached HEAD state
  - Merge conflicts
  - Timeout (30s)

#### prune_stale_worktrees(max_age_days=7) -> int

- **Purpose**: Remove stale/orphaned worktrees
- **Parameters**:
  - max_age_days (int): Maximum age threshold in days (default: 7)
- **Returns**: Number of worktrees pruned
- **Pruning Criteria**:
  - Worktree directory doesn't exist (orphaned)
  - Worktree older than max_age_days (uses directory mtime)
  - Only prunes managed worktrees (containing 'worktrees' in path)
  - Skips main repository

#### get_worktree_path(feature_name) -> Optional[Path]

- **Purpose**: Get path to a worktree by feature name
- **Parameters**: feature_name (str): Feature name
- **Returns**: Path to worktree or None if not found

### Internal Functions

#### _validate_feature_name(name) -> Tuple[bool, str]

- **Purpose**: Security validation for feature names
- **Checks**:
  - Non-empty string
  - No path traversal (.., /)
  - No shell injection (;, &, |, parentheses)
  - Only alphanumeric, hyphens, underscores, dots
- **Returns**: Tuple of (is_valid, error_message)

#### _get_worktree_base_dir() -> Path

- **Purpose**: Get base directory for worktrees (.worktrees/ in cwd)
- **Returns**: Path to .worktrees directory
- **Note**: Uses current working directory, no git calls needed

### Configuration

**Environment Variables**: None (configuration is function parameters)

**Default Worktree Location**: .worktrees/<feature-name>/ in current directory

**Naming Conventions**:
- Feature names: alphanumeric, hyphens, underscores, dots only
- Directory structure: <repo>/.worktrees/<feature-name>/
- Collision handling: <feature-name>-YYYYMMDD-HHMMSS if name exists

### Security Analysis

**Threat Model**:
1. **Path Traversal (CWE-22)**: Blocked by feature name validation (no .., /)
2. **Command Injection (CWE-78)**: Blocked by subprocess list args (no shell=True), feature name validation
3. **Symlink Attacks (CWE-59)**: Blocked by Path.resolve() during worktree path generation

**Validation Layers**:
1. Feature name validation (regex check)
2. subprocess list args (no shell interpolation)
3. Path resolution (symlink detection via resolve())
4. Error messages (no stderr leakage)

### Error Handling Strategy

**All functions return safe tuples/objects**:
- create_worktree(): (bool, Union[Path, str]) - easy error checking
- delete_worktree(): (bool, str) - message for logging
- merge_worktree(): MergeResult dataclass - structured conflict info
- list_worktrees(): List[WorktreeInfo] - empty list on error
- prune_stale_worktrees(): int - 0 on error
- get_worktree_path(): Optional[Path] - None if not found

**Exceptions**: Only raises on programming errors, not operational failures

### Performance

- **Create worktree**: ~1-2 seconds (git worktree add + symlink resolution)
- **List worktrees**: ~50-100ms (porcelain parsing)
- **Merge worktree**: ~0.5-5 seconds (depends on file count)
- **Prune stale**: ~100-500ms (depends on number of worktrees)
- **Get path**: ~5-10ms (list + lookup)

### Test Coverage

**Unit Tests** (40 tests in tests/unit/test_worktree_manager.py):
- Feature name validation (empty, path traversal, injection, invalid chars)
- Worktree creation (success, collision handling, branch errors)
- Worktree listing (parsing, status detection, metadata)
- Worktree deletion (success, force flag, not found)
- Merge operations (success, conflicts, checkout errors)
- Prune operations (stale detection, orphaned cleanup)
- Path queries (found, not found, empty list)
- Mock git commands for offline testing

**Integration Tests** (18 tests in tests/integration/test_worktree_integration.py):
- Real git repository setup/teardown
- Actual worktree creation and listing
- Branch checkout and merge workflows
- Conflict detection and handling
- File operations during merge
- Cleanup after each test

**Coverage Target**: 95% of code paths, 100% of security-critical paths

### Files Added

- plugins/autonomous-dev/lib/worktree_manager.py (684 lines)
- tests/unit/test_worktree_manager.py (927 lines, 40 tests)
- tests/integration/test_worktree_integration.py (702 lines, 18 tests)
- .gitignore updated (added .worktrees/)

### Documentation

- docs/LIBRARIES.md Section 61 (this section)
- Comprehensive docstrings with examples
- Type hints on all functions

### Integration Points

**Used By**:
- /implement command (future feature branch isolation)
- Parallel feature development workflows
- Batch feature processing (potential future use)

**Related**:
- git_operations.py Section 16 - Helper functions (is_worktree, get_worktree_parent)

### GitHub

- Issue #178 - Git worktree isolation feature
- Related: Issue #177 (Stop hook quality gates), #175 (Agent audit), #174 (Test passage enforcement)

### Related Documentation

- docs/GIT-AUTOMATION.md - Git automation workflows
- docs/SECURITY.md - Security hardening guide
- git_operations.py Section 16 - Worktree helper functions

---

## 62. memory_layer.py (766 lines, v1.0.0 - Issue #179)

**Purpose**: Cross-session memory layer for context continuity - persistent memory storage across /implement sessions enabling agents to remember architectural decisions, blockers, patterns, and context without re-research.

**Location**: `plugins/autonomous-dev/lib/memory_layer.py`

### Problem Statement

Issue #179 identified that context resets between /implement sessions force expensive re-research:
- No persistent memory between sessions
- Architectural decisions must be rediscovered
- Blocker knowledge is lost
- Pattern findings don't carry over

### Solution

A JSON-based memory layer stored in `.claude/memory.json` with:
- **Memory types**: feature, decision, blocker, pattern, context
- **Utility scoring**: Recency decay + access frequency ranking
- **PII sanitization**: API keys, passwords, emails, JWT tokens redacted
- **Atomic writes**: Temp file + rename pattern prevents corruption
- **Thread-safe operations**: File locking for concurrent access
- **Graceful degradation**: Storage errors don't crash workflow

### Key Functions

```python
from memory_layer import MemoryLayer, sanitize_pii, calculate_utility_score

# Initialize layer
layer = MemoryLayer()  # Uses .claude/memory.json
layer = MemoryLayer(memory_file=Path("/custom/path.json"))

# Store a memory
memory_id = layer.remember(
    memory_type="decision",
    content={"title": "Database Choice", "summary": "Chose PostgreSQL for ACID compliance"},
    metadata={"tags": ["database", "architecture"]}
)

# Retrieve memories
all_memories = layer.recall()  # All memories, sorted by utility score
decisions = layer.recall(memory_type="decision")  # Filter by type
tagged = layer.recall(filters={"tags": ["database"]})  # Filter by tags
recent = layer.recall(filters={"after": "2026-01-01T00:00:00Z"})  # Date filter

# Forget memories
count = layer.forget(memory_id="mem_123")  # By ID
count = layer.forget(filters={"tags": ["deprecated"]})  # By filter

# Prune old/low-utility memories
removed = layer.prune(max_entries=1000, max_age_days=90)

# Get statistics
summary = layer.get_summary()  # Returns dict with counts, scores, etc.

# PII sanitization (automatic in remember, available standalone)
safe_text = sanitize_pii("API key: sk-1234abcd for user@example.com")
# Returns: "API key: [REDACTED_API_KEY] for [REDACTED_EMAIL]"

# Utility scoring
score = calculate_utility_score(created_at=datetime.now(), access_count=5)
```

### Memory Structure

```json
{
    "version": "1.0.0",
    "memories": [
        {
            "id": "mem_20260102_153042_abc123",
            "type": "decision",
            "content": {
                "title": "Database Choice",
                "summary": "Chose PostgreSQL for ACID compliance"
            },
            "metadata": {
                "created_at": "2026-01-02T15:30:42Z",
                "updated_at": "2026-01-02T15:30:42Z",
                "access_count": 3,
                "tags": ["database", "architecture"],
                "utility_score": 0.85
            }
        }
    ]
}
```

### Security Features

- **CWE-22 Prevention**: Path traversal validation via validate_path()
- **CWE-59 Prevention**: Symlink detection and rejection
- **CWE-359 Prevention**: PII sanitization (API keys, passwords, emails, JWTs)
- **Atomic writes**: Prevents corruption from interrupted writes
- **File locking**: Thread-safe concurrent access
- **Audit logging**: All operations logged (with safe wrapper for test env)

### Utility Scoring Algorithm

```python
utility_score = recency_score * (1 - weight) + frequency_score * weight

# Recency: Exponential decay with 30-day half-life
recency_score = 2 ** (-age_days / 30)

# Frequency: Normalized by max access count (20)
frequency_score = min(1.0, access_count / 20)

# Weight: 0.3 (30% frequency, 70% recency)
```

### Test Coverage

**Unit Tests** (47 tests in tests/unit/lib/test_memory_layer.py):
- Initialization with default and custom paths
- Remember operations (storage, ID generation, PII sanitization)
- Recall operations (filtering, sorting, access tracking)
- Forget operations (by ID, by filter)
- Prune operations (age limit, entry limit)
- PII sanitization (API keys, passwords, emails, JWTs)
- Utility scoring (recency decay, access frequency)
- Security validation (path traversal, symlinks)
- Concurrent access safety

**Integration Tests** (16 tests in tests/integration/test_memory_integration.py):
- Cross-session persistence
- Auto-implement pipeline integration
- Multi-agent memory sharing
- Batch processing cleanup
- Memory migration and versioning

**Coverage Target**: 95% of code paths, 100% of security-critical paths

### Files Added

- plugins/autonomous-dev/lib/memory_layer.py (766 lines)
- tests/unit/lib/test_memory_layer.py (63 tests, ~1000 lines)
- tests/integration/test_memory_integration.py (16 tests, ~600 lines)

### Integration Points

**Used By**:
- /implement command (agent memory persistence)
- Planner agent (recall previous decisions)
- Researcher agent (cache pattern findings)
- Implementer agent (recall blockers)

**Dependencies**:
- security_utils.py - validate_path(), audit_log()
- path_utils.py - get_project_root()

### GitHub

- Issue #179 - Cross-session memory layer for context continuity
- Related: Issue #178 (Git worktree isolation), #180 (Review/merge/discard)

### Related Documentation

- docs/SECURITY.md - Security hardening guide
- docs/LIBRARIES.md Section 6 (security_utils.py) - Path validation
- docs/LIBRARIES.md Section 15 (path_utils.py) - Project root detection
## 63. complexity_assessor.py (441 lines, v1.0.0 - Issue #181)

**Purpose**: Automatic complexity assessment for pipeline scaling

**Key Concepts**:
- Keyword-based heuristics for fast complexity classification
- Confidence scoring to indicate assessment certainty
- Agent count and time recommendations based on complexity
- Security-first approach: COMPLEX keywords override SIMPLE keywords

### Classes

#### `ComplexityLevel` (Enum)

**Values**:
- `SIMPLE` - Simple changes (typos, docs, formatting) - 3 agents, ~8 min
- `STANDARD` - Standard features (bug fixes, small features) - 6 agents, ~15 min
- `COMPLEX` - Complex features (auth, security, APIs) - 8 agents, ~25 min

#### `ComplexityAssessment` (NamedTuple)

**Attributes**:
- `level` (ComplexityLevel): Assessed complexity level (SIMPLE/STANDARD/COMPLEX)
- `confidence` (float): Confidence score for assessment (0.0-1.0)
- `reasoning` (str): Human-readable explanation of classification
- `agent_count` (int): Recommended number of agents (3/6/8)
- `estimated_time` (int): Estimated time in minutes (8/15/25)

#### `ComplexityAssessor` (Class)

**Design**:
- Stateless: No instance variables, all methods can be class methods
- Keyword-based: Fast heuristics for common patterns
- Conservative: Defaults to STANDARD when uncertain
- Security-first: COMPLEX keywords override SIMPLE keywords

**Keyword Sets**:
- SIMPLE_KEYWORDS: typo, spelling, docs, documentation, readme, rename, format, formatting, comment, whitespace, indentation, style, lint, pep8, black
- COMPLEX_KEYWORDS: auth, authentication, authorization, security, encrypt, encryption, jwt, oauth, oauth2, saml, ldap, password, credential, token, api, webhook, database, migration, schema

### Methods

#### `assess(feature_description, github_issue=None)` - Main entry point

**Signature**: `@classmethod assess(feature_description: str, github_issue: Optional[Dict] = None) -> ComplexityAssessment`

**Purpose**: Assess complexity of a feature request

**Parameters**:
- `feature_description` (str): Feature request text to analyze
- `github_issue` (Optional[Dict]): GitHub issue dict with 'title' and 'body' keys (optional)

**Returns**: ComplexityAssessment with level, confidence, reasoning, agent_count, time

**Edge Cases**:
- Handles None input (defaults to STANDARD with 0.4 confidence)
- Handles empty/whitespace input (defaults to STANDARD with 0.4 confidence)
- Truncates input >10000 chars with warning
- Combines feature description with GitHub issue (body weighted higher)

**Example**:
```python
assessor = ComplexityAssessor()
result = assessor.assess("Fix typo in README")
print(f"Level: {result.level}, Agents: {result.agent_count}")
# Output: Level: ComplexityLevel.SIMPLE, Agents: 3
```

#### `_analyze_keywords(text)` - Keyword-based classification

**Signature**: `@classmethod _analyze_keywords(text: str) -> Dict[str, Any]`

**Purpose**: Analyze text for SIMPLE and COMPLEX keyword indicators

**Parameters**: `text` (str): Text to analyze

**Returns**: Dict with 'simple_count', 'complex_count', 'simple_keywords', 'complex_keywords'

**Algorithm**:
- Case-insensitive substring matching for each keyword set
- Returns counts and matched keyword lists
- Fast O(n) algorithm where n = text length

#### `_analyze_scope(text)` - Scope detection analysis

**Signature**: `@classmethod _analyze_scope(text: str) -> Dict[str, Any]`

**Purpose**: Analyze text for scope indicators (file counts, conjunctions)

**Parameters**: `text` (str): Text to analyze

**Returns**: Dict with 'conjunction_count', 'file_type_count', 'word_count', 'alphabetic_count'

**Algorithm**:
- Count conjunctions: and, or, also, plus, additionally (regex-based)
- Count unique file types: .py, .js, .md, etc. (regex-based)
- Calculate word count and alphabetic word count
- Used as secondary indicator for scope breadth

#### `_analyze_security(text)` - Security indicator detection

**Signature**: `@classmethod _analyze_security(text: str) -> Dict[str, Any]`

**Purpose**: Analyze text for security-related indicators

**Parameters**: `text` (str): Text to analyze

**Returns**: Dict with 'has_security_keywords' and 'security_keyword_list'

**Security Keywords**: auth, authentication, authorization, security, encrypt, encryption, jwt, oauth, oauth2, saml, password, credential, token

#### `_determine_level(indicators)` - Complexity level determination

**Signature**: `@classmethod _determine_level(indicators: Dict) -> ComplexityLevel`

**Purpose**: Determine complexity level from indicators

**Priority**:
1. COMPLEX keywords override SIMPLE keywords (security-first approach)
2. SIMPLE keywords with no conflicts
3. STANDARD as default fallback

**Algorithm**:
- If complex_count > 0: return COMPLEX
- Else if simple_count > 0: return SIMPLE
- Else: return STANDARD

#### `_calculate_confidence(indicators)` - Confidence scoring

**Signature**: `@classmethod _calculate_confidence(indicators: Dict) -> float`

**Purpose**: Calculate confidence score (0.0-1.0) for assessment

**Confidence Factors**:
- Single keyword match: 0.85 base
- Multiple keyword matches: +0.05 per additional (max +0.10)
- Conflicting signals: -0.30 penalty
- No keywords but detailed: 0.6 (reasonable default to STANDARD)
- No keywords and vague/garbage: 0.4-0.5 (very ambiguous)

**Algorithm**:
```
If no keywords detected:
  If alphabetic_count == 0: confidence = 0.4 (garbage input)
  Elif word_count < 5: confidence = 0.5 (very ambiguous)
  Else: confidence = 0.6 (detailed request)
Else:
  confidence = 0.85 (base for any keyword match)
  If total_keywords >= 2: confidence += 0.05
  If total_keywords >= 3: confidence += 0.05
  If simple_count > 0 AND complex_count > 0: confidence -= 0.30
  Clamp confidence to [0.0, 1.0]
```

#### `_generate_reasoning(level, indicators, confidence)` - Reasoning generation

**Signature**: `@classmethod _generate_reasoning(level, indicators, confidence) -> str`

**Purpose**: Generate human-readable reasoning for assessment

**Output Format**: "Classified as LEVEL - [keyword details] - confidence level - [conflicts]"

**Example**: "Classified as COMPLEX - detected COMPLEX keywords: auth, encryption, jwt - high confidence - (conflicting signals detected, COMPLEX takes priority)"

### Test Coverage

**Unit Tests** (52 tests in tests/unit/lib/test_complexity_assessor.py):
- Simple typo/documentation classification
- Standard feature/bug fix classification
- Complex authentication/security/API classification
- Conflicting signal handling (SIMPLE + COMPLEX)
- Edge cases (empty input, None, whitespace-only)
- GitHub issue integration (title + body weighting)
- Confidence scoring accuracy
- Agent count and time mapping
- Low confidence scenarios
- Very long input truncation

**Coverage Target**: 95% of code paths, 100% of public API paths

### Files Added

- plugins/autonomous-dev/lib/complexity_assessor.py (441 lines)
- plugins/autonomous-dev/scripts/complexity_assessor.py (CLI wrapper, ~180 lines)
- tests/unit/lib/test_complexity_assessor.py (52 tests, ~500 lines)

### CLI Usage

```bash
# Simple text input
python complexity_assessor.py "Fix typo in README"

# From stdin
echo "Add OAuth2 support" | python complexity_assessor.py --stdin

# From GitHub issue
python complexity_assessor.py --issue 181

# JSON output
python complexity_assessor.py "Add JWT authentication" --json

# Verbose output
python complexity_assessor.py "Implement OAuth2" --verbose
```

### Integration Points

**Used By**:
- /implement command (determine pipeline scaling)
- planner agent (estimate time and agent requirements)
- /create-issue command (estimate scope in issue creation)

**Dependencies**:
- None (standard library only: enum, typing, re, logging)

### Security Features

- Input validation for all user-provided text
- Graceful degradation for invalid inputs
- Max 10000 chars truncation with warning
- No external dependencies on network resources
- Thread-safe logging

### Performance

- Time complexity: O(n) where n = text length
- Space complexity: O(m) where m = number of keywords found
- Typical execution: < 5ms for standard feature descriptions

### GitHub

- Issue #181 - Automatic complexity assessment for pipeline scaling
- Related: Issue #180 (Smart pipeline scaling based on complexity)

### Related Documentation

- docs/PERFORMANCE.md - Pipeline performance metrics
- docs/LIBRARIES.md Section 1 (security_utils.py) - Input validation patterns

---

## 64. pause_controller.py (403 lines, v1.0.0 - Issue #182)

**Purpose**: File-based pause controls and human input handling for autonomous workflows

**Problem**: Long-running autonomous workflows need to pause at checkpoints to accept human feedback, approvals, or instructions without losing state.

**Solution**: Comprehensive pause/resume system with file-based signaling, checkpoint persistence, and secure file operations.

### Key Files

- `.claude/PAUSE` - Touch file to signal pause request
- `.claude/HUMAN_INPUT.md` - Optional file with human instructions/feedback
- `.claude/pause_checkpoint.json` - Checkpoint state for resume

### Functions

#### `check_pause_requested()` -> bool

**Purpose**: Check if pause is requested via .claude/PAUSE file

**Returns**: True if PAUSE file exists and is valid, False otherwise

**Security**:
- Rejects symlinks (CWE-59)
- Returns False if .claude dir doesn't exist
- Path traversal prevention

#### `read_human_input()` -> Optional[str]

**Purpose**: Read content from .claude/HUMAN_INPUT.md file

**Returns**: File content as string, or None if file doesn't exist

**Security**:
- Rejects symlinks (CWE-59)
- 1MB file size limit (DoS prevention)
- Handles unicode properly
- Returns None on permission errors
- Path traversal prevention

**Features**:
- Graceful handling of missing files
- Automatic encoding detection
- Safe error recovery

#### `clear_pause_state()` -> None

**Purpose**: Remove PAUSE and HUMAN_INPUT.md files to resume workflow

**Behavior**:
- Idempotent (no error if files don't exist)
- Preserves checkpoint file (separate lifecycle)
- Removes both signal files

**Security**:
- Validates paths before deletion
- Only removes PAUSE and HUMAN_INPUT.md
- Never follows symlinks

#### `save_checkpoint(agent_name, state)` -> None

**Purpose**: Save checkpoint state to .claude/pause_checkpoint.json for resume

**Parameters**:
- `agent_name` (str): Name of agent saving checkpoint
- `state` (Dict[str, Any]): State dictionary to save

**Security**:
- Atomic write (write to temp file, then rename)
- Input validation for agent_name
- Path validation before write
- Atomic rename prevents partial writes

**Checkpoint Structure**:
```json
{
  "agent": "agent_name",
  "timestamp": "2026-01-02T12:34:56.123456+00:00",
  "step": 3,
  "data": "..."
}
```

#### `load_checkpoint()` -> Optional[Dict[str, Any]]

**Purpose**: Load checkpoint from .claude/pause_checkpoint.json

**Returns**: Checkpoint data as dictionary, or None if:
- File doesn't exist
- JSON is invalid
- File is empty
- Permission denied

**Security**:
- Validates path before reading
- Handles corrupted JSON gracefully
- Rejects invalid file formats
- Returns None for errors (graceful degradation)

#### `validate_pause_path(path)` -> bool

**Purpose**: Validate path for pause-related file operations

**Parameters**: `path` (str): Path to validate

**Returns**: True if path is valid and safe, False otherwise

**Security Validations**:
- CWE-22: Reject path traversal attempts (..)
- CWE-59: Reject symlinks
- Ensure path is within .claude/ directory
- Block null bytes (CWE-158)

### Workflow Integration

**Typical Workflow**:
1. User creates `.claude/PAUSE` file to pause at next checkpoint
2. Optionally: User writes `.claude/HUMAN_INPUT.md` with instructions
3. Workflow checks `check_pause_requested()` at checkpoints
4. If paused: saves state with `save_checkpoint()`
5. Workflow reads instructions with `read_human_input()`
6. User provides feedback/approval
7. User removes `.claude/PAUSE` to signal resume
8. Workflow loads state with `load_checkpoint()` and continues

### Security Features

- **Path Traversal Prevention (CWE-22)**: Strict validation that all paths are within `.claude/` directory
- **Symlink Attack Prevention (CWE-59)**: All file checks detect and reject symlinks
- **Null Byte Injection (CWE-158)**: Blocks null bytes in paths
- **DoS Prevention**: 1MB file size limit on human input
- **Atomic Operations**: Checkpoint writes use temp file + rename for atomicity
- **Graceful Degradation**: All errors return safe defaults (None/False) instead of exceptions

### Test Coverage

- 44 unit tests for all functions
- 24 integration tests for workflow scenarios
- Security tests for path traversal, symlinks, null bytes
- Edge case tests for missing files, permissions, corrupted JSON

### Related

- GitHub Issue #182 - Pause controls with PAUSE file and HUMAN_INPUT.md
- state-management-patterns skill - Checkpoint patterns
- security_utils.py (Section 1) - Common path validation approach

### Documentation

- **API**: This section (LIBRARIES.md Section 64)
- **Workflow**: See HUMAN_INPUT.md for user-facing pause workflow
- **Source**: plugins/autonomous-dev/lib/pause_controller.py (403 lines)


## 65. worktree_command.py (506 lines, v1.0.0 - Issue #180)

**Purpose**: Interactive CLI interface for git worktree management

**Problem**: After features are developed in isolated worktrees, users need a way to review changes, merge to target branch, or discard work safely - all from the command line

**Solution**: Complete CLI with 5 modes (list, status, review, merge, discard) providing full worktree lifecycle management

### Key Features

- **Multi-mode interface**: List, status, review, merge, discard modes
- **Safe operations**: Destructive operations require explicit user approval
- **Formatted output**: Status indicators (clean, dirty, active, stale, detached)
- **Interactive review**: Shows diff and prompts for merge approval
- **Exit codes**: Standard codes (0=success, 1=warning, 2=user reject)

### Modes

#### List Mode (`--list` - DEFAULT)

Shows all active worktrees with status indicators.

**Usage**:
```bash
/worktree                # Default list mode
/worktree --list         # Explicit list mode
```

**Output**:
```
Feature              Branch                         Status
------------------------------------------------------------
feature-auth         feature/feature-auth           clean
feature-logging      feature/feature-logging        dirty
```

**Status Indicators**:
- `clean` - No uncommitted changes
- `dirty` - Has uncommitted changes
- `active` - Currently checked out
- `stale` - Directory missing (orphaned)
- `detached` - Detached HEAD state

#### Status Mode (`--status FEATURE`)

Detailed information for a specific worktree.

**Usage**:
```bash
/worktree --status feature-auth
```

**Output**:
```
Worktree Status: feature-auth
Path:            /project/.worktrees/feature-auth
Branch:          feature/feature-auth
Status:          dirty
Target Branch:   master
Commits Ahead:   5
Commits Behind:  2

Uncommitted Changes (3 files):
  - auth/models.py
  - auth/tests.py
  - README.md
```

**Fields**:
- Path: Full path to worktree directory
- Branch: Current branch name
- Status: clean/dirty/active/stale/detached
- Target Branch: Where commits will be merged
- Commits Ahead/Behind: Against target branch
- Uncommitted Changes: List of modified files

#### Review Mode (`--review FEATURE`)

Interactive diff review with approve/reject workflow.

**Usage**:
```bash
/worktree --review feature-auth
```

**Workflow**:
1. Shows full git diff against target branch
2. Prompts: "Approve or reject changes? [approve/reject]:"
3. If approve: Automatically merges to target branch
4. If reject: Exits without merging

**Output**:
```
Diff for worktree: feature-auth
============================================================
diff --git a/auth/models.py b/auth/models.py
[... full diff output ...]
============================================================

Approve or reject changes? [approve/reject]: approve

Successfully merged 12 files
```

#### Merge Mode (`--merge FEATURE`)

Directly merge worktree to target branch without review.

**Usage**:
```bash
/worktree --merge feature-auth
```

**Behavior**:
- Merges worktree branch to target branch
- Handles merge conflicts (reports and exits with code 1)
- Non-interactive (no approval prompt)

#### Discard Mode (`--discard FEATURE`)

Delete worktree with confirmation.

**Usage**:
```bash
/worktree --discard feature-auth
```

**Behavior**:
- Prompts for confirmation: "Delete worktree feature-auth? [y/N]:"
- If yes: Deletes worktree directory and git worktree entry
- If no: Exits without deleting
- Prevents accidental deletion of uncommitted work

### Implementation Details

**Design Pattern**: Wrapper CLI around worktree_manager.py library

**Architecture**:
- Parse arguments using argparse
- Delegate operations to worktree_manager.py functions
- Handle user interactions (prompts, confirmation)
- Format and display results
- Return appropriate exit codes

**User Prompts**:
- Review mode: Shows diff, prompts approve/reject
- Discard mode: Prompts for confirmation
- Review/merge prompts use Task tool for interactive input

**Error Handling**:
- Clear error messages for failed operations
- Non-blocking graceful degradation (non-git directories)
- Exit codes signal success/warning/user rejection

**Integration**:
- Designed to work with /implement worktree output
- Part of feature review and merge workflow
- Can be used standalone for worktree management

### API Functions

#### `main(args: List[str]) -> int`

**Purpose**: Main entry point for CLI

**Parameters**:
- `args` (List[str]): Command-line arguments (excluding program name)

**Returns**: Exit code (0=success, 1=warning, 2=user reject)

**Modes Dispatched**:
- Empty or `--list` -> list_mode()
- `--status NAME` -> status_mode(NAME)
- `--review NAME` -> review_mode(NAME)
- `--merge NAME` -> merge_mode(NAME)
- `--discard NAME` -> discard_mode(NAME)

#### `list_mode() -> int`

Lists all active worktrees with formatted output.

**Returns**: 0 (always succeeds, even if no worktrees)

#### `status_mode(feature: str) -> int`

Shows detailed status for a worktree.

**Parameters**: `feature` (str): Worktree/feature name

**Returns**: 0=success, 1=worktree not found

#### `review_mode(feature: str) -> int`

Interactive diff review and merge.

**Parameters**: `feature` (str): Worktree/feature name

**Returns**: 0=merged, 1=merge failed, 2=user rejected

#### `merge_mode(feature: str) -> int`

Direct merge without review.

**Parameters**: `feature` (str): Worktree/feature name

**Returns**: 0=success, 1=merge failed

#### `discard_mode(feature: str) -> int`

Delete worktree with confirmation.

**Parameters**: `feature` (str): Worktree/feature name

**Returns**: 0=deleted, 1=error, 2=user cancelled

### Data Structures

#### `ParsedArgs` (dataclass)

Parsed command-line arguments.

**Fields**:
- `mode` (str): Operation mode (list, status, review, merge, discard)
- `feature` (Optional[str]): Feature name (None for list mode)

### Security

**Path Validation**:
- Validates worktree paths (CWE-22 path traversal prevention)
- Prevents directory traversal via feature names
- Rejects symlinks and suspicious paths

**Command Injection Prevention** (CWE-78):
- Feature names sanitized before shell commands
- Uses subprocess with list arguments (not shell=True)
- No user input passed directly to shell

**No File Writes**:
- Only reads git state and worktree metadata
- All modifications delegated to worktree_manager.py
- No file creation in user directories

### Test Coverage

**40 unit tests** covering:
- All 5 modes (list, status, review, merge, discard)
- Argument parsing (valid/invalid args)
- Output formatting
- User prompt handling
- Error conditions (missing worktrees, permission errors)
- Edge cases (empty list, special characters in names)

**Files**:
- tests/unit/test_worktree_command.py (40 tests)

### Performance

- List: 50-100ms (git worktree list)
- Status: 100-500ms (git log, git status for one worktree)
- Review: 0.5-5s (git diff, merge operations)
- Merge: 0.5-5s (git merge operation)
- Discard: 1-2s (worktree cleanup)

### Related

- GitHub Issue #180 - /worktree command for git worktree management
- worktree_manager.py (Section 61) - Core library for operations
- git-operations skill - Git integration patterns
- cli-design-patterns skill - CLI argument handling patterns

### Documentation

- **API**: This section (LIBRARIES.md Section 65)
- **Command**: plugins/autonomous-dev/commands/worktree.md (590 lines)
  - Quick start examples
  - Use case descriptions
  - Detailed mode reference
- **Source**: plugins/autonomous-dev/lib/worktree_command.py (506 lines)

## 66. sandbox_enforcer.py (625 lines, v1.0.0 - Issue #171)

**Purpose**: Command classification and OS-specific sandboxing to reduce permission prompts by 84%

**Location**: `plugins/autonomous-dev/lib/sandbox_enforcer.py`

**Version**: 1.0.0 (2026-01-02, Issue #171 - Sandboxing for reduced permission prompts)

### Overview

SandboxEnforcer provides command classification (SAFE/BLOCKED/NEEDS_APPROVAL) and OS-specific sandboxing to eliminate repetitive permission prompts for safe operations.

**Problem It Solves**:
- Users approve 50+ permission prompts per /implement workflow
- 80%+ are for safe read-only commands (cat, ls, grep, git status)
- Each prompt breaks focus and adds 10-20 seconds overhead
- SandboxEnforcer reduces prompts from 50+ to roughly 8-10 (84% reduction)

**Solution**:
- Whitelist-first approach: Safe commands auto-approve without prompts
- Blocked patterns: Dangerous commands denied with audit logging
- OS-specific sandboxing: bwrap (Linux), sandbox-exec (macOS), none (Windows)
- Circuit breaker: Disables after threshold blocks (safety mechanism)

### Architecture

**4-Layer Integration**:
1. **Layer 0 (Sandbox)**: SAFE to auto-approve, BLOCKED to deny, NEEDS_APPROVAL to continue
2. **Layer 1 (MCP Security)**: Path traversal, injection, SSRF validation
3. **Layer 2 (Agent Auth)**: Pipeline agent detection
4. **Layer 3 (Batch Permission)**: Permission batching

**Integrated into**: `unified_pre_tool.py` hook (PreToolUse lifecycle)

**Environment Variables**:
- `SANDBOX_ENABLED` (bool, default: false) - Enable/disable sandbox layer
- `SANDBOX_PROFILE` (str, default: development) - Security profile (development/testing/production)

### Classes

#### `CommandClassification` (Enum)

Command classification results:

```
class CommandClassification(Enum):
    SAFE = "safe"
    BLOCKED = "blocked"
    NEEDS_APPROVAL = "needs_approval"
```

#### `SandboxBinary` (Enum)

OS-specific sandbox binaries:

```
class SandboxBinary(Enum):
    BWRAP = "bwrap"
    SANDBOX_EXEC = "sandbox-exec"
    NONE = "none"
```

#### `CommandResult` (Dataclass)

Result of command classification:

```
@dataclass
class CommandResult:
    classification: CommandClassification
    reason: Optional[str] = None
    can_sandbox: bool = False
```

#### `SandboxEnforcer` (Main Class)

Command classifier and sandbox manager.

**Constructor**:
```
SandboxEnforcer(policy_path: Optional[str|Path] = None, profile: str = "development")
```

**Parameters**:
- `policy_path` (optional): Custom policy file (defaults to plugin policy.json)
- `profile` (str): Security profile - "development" (permissive), "testing" (moderate), "production" (strict)

**Key Methods**:

##### `is_command_safe(command: str) -> CommandResult`
Classify a command and determine permission decision.

**Parameters**: `command` (str) - Full command string

**Returns**: `CommandResult` with classification and reason

**Logic**:
1. Check circuit breaker (return BLOCKED if tripped)
2. Check if command is in safe_commands list (return SAFE)
3. Check for blocked patterns (return BLOCKED)
4. Check for shell injection patterns (return BLOCKED)
5. Check for path traversal (return BLOCKED)
6. Check for blocked file paths (return BLOCKED)
7. Return NEEDS_APPROVAL (continue to Layer 1)

**Example**:
```
enforcer = SandboxEnforcer()

result = enforcer.is_command_safe("cat README.md")
assert result.classification == CommandClassification.SAFE

result = enforcer.is_command_safe("rm command")
assert result.classification == CommandClassification.BLOCKED
```

##### `get_sandbox_binary() -> SandboxBinary`
Detect OS-specific sandbox binary availability.

**Returns**: SandboxBinary enum (BWRAP, SANDBOX_EXEC, or NONE)

**Behavior**:
- Linux: Check for `bwrap` (bubblewrap)
- macOS: Check for `sandbox-exec`
- Windows: Return NONE
- Fallback: Return NONE if binary not found

##### `build_sandbox_args(command: str) -> List[str]`
Build OS-specific sandbox arguments for command wrapping.

**Parameters**: `command` (str) - Original command

**Returns**: List[str] - Sandbox wrapper plus original command

**OS-Specific Behavior**:

Linux (bwrap): Wraps with tmpfs isolation and bind mounts

macOS (sandbox-exec): Wraps with operation deny policy

Windows (none): Returns original command as-is (no sandboxing)

### Validation Methods

#### `validate_policy(policy: Dict[str, Any]) -> bool`
Validate policy JSON schema.

**Checks**:
- Version field present
- Profiles dict present
- Each profile has required sections
- Security settings valid

**Raises**: `PolicyValidationError` if validation fails

### Security Features

**Shell Injection Detection** (CWE-78):
- Detects dangerous shell metacharacters
- Blocks commands with unsafe patterns
- Prevents command chaining and execution tricks

**Path Traversal Protection** (CWE-22):
- Detects pattern matching in commands
- Blocks access to sensitive files: .env, .ssh, credential files
- Validates all file paths in commands

**Circuit Breaker** (DoS Prevention):
- Trips after threshold blocks (configurable per profile)
- Automatically disables sandbox after repeated violations
- Prevents brute-force attempts to bypass sandbox

**Audit Logging**:
- Logs all decisions to security audit log
- Records command, classification, reason
- Thread-safe logging with file rotation

### Policy Profiles

**Profile: Development** (Most Permissive)

Safe commands: cat, echo, grep, ls, pwd, which, git status, git diff, pytest

Blocked patterns: rm command, sudo, git push variants, eval, wget patterns, curl patterns

Blocked paths: .env, .ssh/, credentials.json, key files, /etc/shadow

Circuit breaker: 10 blocks before tripping

**Profile: Testing** (Moderate)

Stricter than development with fewer safe commands and 5-block circuit breaker

**Profile: Production** (Strictest)

Minimal auto-approvals with 3-block circuit breaker

### Configuration

**Policy File Location**: `plugins/autonomous-dev/config/sandbox_policy.json`

**Custom Policy** (Project-Local Override):
Create `.claude/config/sandbox_policy.json` with custom profiles

### Integration with unified_pre_tool.py

**Layer 0 Decision Logic**:

Tool call received -> Extract command -> Classify with SandboxEnforcer -> Return decision

### Examples

**Example 1: Safe Read-Only Command**
```
result = enforcer.is_command_safe("grep pattern src/")
Classification: SAFE (grep is in safe_commands list)
Action: Auto-approve, skip permission prompt
```

**Example 2: Blocked Dangerous Pattern**
```
result = enforcer.is_command_safe("rm command /home/user")
Classification: BLOCKED (matches blocked pattern)
Action: Deny with audit log
```

**Example 3: Unknown Command**
```
result = enforcer.is_command_safe("custom-linter options")
Classification: NEEDS_APPROVAL (not in safe list, no blocked patterns)
Action: Continue to Layer 1 (MCP Security validation)
```

**Example 4: Sandboxing on Linux**
```
binary = enforcer.get_sandbox_binary()
if binary == SandboxBinary.BWRAP:
    sandbox_args = enforcer.build_sandbox_args("cat file.txt")
    # Execute with subprocess
```

### Test Coverage

**50+ unit tests** covering:
- Command classification (SAFE/BLOCKED/NEEDS_APPROVAL)
- Safe command patterns
- Blocked patterns
- Injection detection
- Path traversal detection
- Blocked file patterns
- Sandbox binary detection
- Policy loading and validation
- Circuit breaker logic
- Cross-platform behavior
- Edge cases

**Files**:
- tests/unit/lib/test_sandbox_enforcer.py (50+ tests)

### Performance

- Command classification: less than 1ms (pattern matching)
- Sandbox binary detection: 5-50ms (first run, cached after)
- Policy loading: 10-20ms (per process startup)
- Circuit breaker check: less than 1ms (in-memory state)

**Optimization Notes**:
- Compiled regex patterns for performance
- Cached binary detection
- No filesystem I/O during classification

### Security Considerations

**What It Protects**:
- Command injection via shell metacharacters
- Path traversal attacks
- Sensitive data exposure via blocked file patterns
- DoS via brute-force bypass attempts

**What It Doesn't Protect**:
- Vulnerabilities in whitelisted commands
- Logic bugs in policy rules
- Malicious code execution
- Privilege escalation beyond blocked patterns

### Related

- GitHub Issue #171 - Sandboxing for reduced permission prompts
- unified_pre_tool.py (HOOKS.md) - Hook integration (Layer 0)
- MCP-SECURITY.md - Overall security architecture
- sandbox_policy.json - Policy configuration file

### Documentation

- **API**: This section (LIBRARIES.md Section 66)
- **User Guide**: docs/SANDBOXING.md (comprehensive user documentation)
- **Hook Integration**: docs/HOOKS.md (unified_pre_tool.py Layer 0)
- **Source**: plugins/autonomous-dev/lib/sandbox_enforcer.py (625 lines)
- **Config**: plugins/autonomous-dev/config/sandbox_policy.json
- **Tests**: tests/unit/lib/test_sandbox_enforcer.py


## 67. status_tracker.py (335 lines, v3.48.0+ - Issue #174)

**Purpose**: Test status tracking for pre-commit gate hook enforcement

**Module**: plugins/autonomous-dev/lib/status_tracker.py

**Problem**: Pre-commit hooks need to know if tests passed before allowing commits. A simple, reliable mechanism is needed for test runners to communicate test status to the commit hook.

**Solution**: Atomic file-based test status tracking with secure permissions and graceful degradation.

**Key Features**:
- **Atomic writes**: Write to temp file, then rename (prevents corruption if process crashes)
- **Secure storage**: /tmp/.autonomous-dev/test-status.json with 0600 file permissions and 0700 directory permissions
- **Graceful degradation**: All I/O errors return safe defaults (assume tests failed)
- **Safe defaults**: read_status() returns {"passed": False} if file missing/corrupted
- **Temporary storage**: Ephemeral in /tmp (cleared on system reboot)
- **Comprehensive validation**: JSON structure validation, type checking, timestamp validation

**API Reference**:

```python
from status_tracker import write_status, read_status, clear_status, get_status_file_path

# After test run completes
write_status(passed=True, details={"total": 100, "failed": 0})
# Returns: bool (True if write succeeded, False if failed)

# In pre-commit hook
status = read_status()
# Returns: Dict with at least {"passed": bool, "timestamp": str or None}
# Safe default on any error: {"passed": False, "timestamp": None}

if status.get("passed"):
    # Allow commit
    pass
else:
    # Block commit
    pass

# Clear status (optional)
clear_status()  # Returns: bool

# Get status file path
path = get_status_file_path()
# Returns: Path object (PosixPath on Unix, WindowsPath on Windows)
```

**Security Features**:
- **CWE-22 Prevention**: Hardcoded /tmp path (no user input, no traversal risk)
- **Atomic operations**: Rename is atomic at filesystem level (prevents race conditions)
- **Restricted permissions**: 0600 on files, 0700 on directory (owner read/write only)
- **Safe defaults**: Any I/O error returns safe "tests failed" default
- **JSON validation**: Validates parsed JSON structure before returning

**Main Functions**:

1. **write_status(passed, details=None) -> bool**
   - Write test status to /tmp/.autonomous-dev/test-status.json
   - Args: passed (bool), details (optional dict with additional data)
   - Returns: True if write succeeded, False if failed
   - Creates directory with 0700 permissions if missing
   - Sets file permissions to 0600 after write
   - Graceful degradation: Returns False on any error (doesn't raise)

2. **read_status() -> Dict[str, Any]**
   - Read test status from file
   - Returns: Dictionary with at least {"passed": bool, "timestamp": str or None}
   - Safe default: {"passed": False, "timestamp": None} on any error
   - Validates JSON structure and field types before returning
   - Graceful degradation: Returns safe default on missing file, parse errors, etc.

3. **clear_status() -> bool**
   - Delete the status file
   - Returns: True if deleted or didn't exist, False if deletion failed
   - Graceful degradation: Returns False on permission errors

4. **get_status_file_path() -> Path**
   - Get path to status file
   - Returns: pathlib.Path object
   - No I/O operations (just returns constant path)

5. **_ensure_status_dir() -> bool** (internal)
   - Ensure /tmp/.autonomous-dev/ exists with 0700 permissions
   - Returns: True if directory exists/was created, False if failed
   - Validates and fixes permissions if directory already existed

**Design Patterns**:
- **Graceful degradation**: All functions return safe defaults on errors, never raise
- **Atomic writes**: Uses temp file + rename pattern for data integrity
- **Safe defaults**: Assume tests failed if anything goes wrong
- **No user input**: Hardcoded paths prevent all traversal attacks

**Error Handling**:
- OSError, PermissionError: Caught and return False (graceful degradation)
- IOError, json.JSONDecodeError: Caught and return safe defaults
- Missing file: Treated as {"passed": False} (safe default)
- Corrupted JSON: Treated as {"passed": False} (safe default)
- Invalid field types: Cleaned up and returned with safe values

**Performance**:
- write_status(): ~2-5ms (file I/O)
- read_status(): ~1-3ms (file I/O + JSON parsing)
- clear_status(): ~1-2ms (file deletion)
- get_status_file_path(): <0.1ms (no I/O)

**Usage Examples**:

```python
# Test runner integration
import subprocess
from status_tracker import write_status

result = subprocess.run(['pytest', 'tests/'], capture_output=True)
write_status(
    passed=(result.returncode == 0),
    details={
        "total": 100,
        "failed": 0 if result.returncode == 0 else 5,
        "duration": 12.3
    }
)

# Pre-commit hook integration
from status_tracker import read_status

status = read_status()
if not status.get("passed"):
    print("Tests failed - commit blocked")
    print(f"Details: {status}")
    exit(1)  # Block commit
```

**Integration**:
- Used by: pre_commit_gate.py hook (blocks commits if tests failed)
- Called by: Test runners after test execution (write status)
- Non-blocking: Library itself has no side effects, hook decides action

**Security Audit**:
- Path validation: Hardcoded path only, no user input
- File permissions: 0600 (owner RW), 0700 (directory owner RWX)
- No symlink following: Verified no symlink traversal
- No subprocess calls: Pure Python file I/O
- No network access: File-local only
- No credential exposure: No passwords or tokens in status file

**Test Coverage**:
- Write operations: File creation, permission setting, temp file cleanup
- Read operations: Missing file, corrupted JSON, invalid field types
- Edge cases: Race conditions (atomic rename), permission errors, disk full
- Security: Path traversal attempts, symlink attacks, permission escalation
- Integration: Hook usage patterns, test runner integration

**Related Documentation**:
- docs/LIBRARIES.md - This section (67)
- docs/HOOKS.md - pre_commit_gate section (uses status_tracker)
- plugins/autonomous-dev/hooks/pre_commit_gate.py - Hook implementation
- Issue #174 - Block-at-submit hook for test passage enforcement

**Testing**:
```bash
# Self-test (included in module)
python plugins/autonomous-dev/lib/status_tracker.py

# Integrated tests
pytest tests/unit/lib/test_status_tracker.py
```

**Backward Compatibility**: N/A (new library)

**Version History**:
- v1.0.0 (2026-01-02) - Initial release with atomic writes, secure permissions, graceful degradation


---

## 68. headless_mode.py (263 lines, v1.0.0 - Issue #176)

**Purpose**: CI/CD integration support for headless/non-interactive environments

**GitHub Issue**: #176 - Headless mode for CI/CD integration

### Functions

#### `detect_headless_flag() -> bool`
- **Purpose**: Detect if --headless flag is present in sys.argv
- **Parameters**: None
- **Returns**: bool - True if --headless flag is present (case-sensitive, exact match)
- **Features**:
  - Case-sensitive matching (--Headless returns False)
  - Exact match only (--headless-verbose would not match)
  - No argument parsing required (simple membership check)

#### `detect_ci_environment() -> bool`
- **Purpose**: Detect if running in a CI/CD environment
- **Parameters**: None
- **Returns**: bool - True if any CI environment variable is detected
- **Features**:
  - Checks common CI environment variables (case-insensitive values):
    - CI=true, CI=1
    - GITHUB_ACTIONS=true, GITHUB_ACTIONS=1
    - GITLAB_CI=true, GITLAB_CI=1
    - CIRCLECI=true, CIRCLECI=1
    - TRAVIS=true, TRAVIS=1
  - JENKINS_HOME: Any non-empty value (typically /var/jenkins_home)
- **Supported CI Systems**:
  - GitHub Actions
  - GitLab CI/CD
  - CircleCI
  - Travis CI
  - Jenkins
  - Any CI that sets CI=true standard

#### `is_headless_mode() -> bool`
- **Purpose**: Determine if running in headless mode (combined detection)
- **Parameters**: None
- **Returns**: bool - True if headless mode is active
- **Detection Logic** (in priority order):
  1. Explicit --headless flag present -> Return True
  2. CI environment AND not TTY -> Return True
  3. Not TTY (stdin not a terminal) -> Return True
  4. Otherwise -> Return False
- **Features**:
  - TTY detection via sys.stdin.isatty()
  - Combines flag-based and environment-based detection
  - Detects CI environments without explicit flag
  - Detects piped input (not TTY)

#### `should_skip_prompts() -> bool`
- **Purpose**: Determine if interactive prompts should be skipped
- **Parameters**: None
- **Returns**: bool - True if prompts should be skipped (alias for is_headless_mode())
- **Usage**: Call this in interactive workflows to decide whether to prompt

#### `format_json_output(status, data, error) -> str`
- **Purpose**: Format output as JSON for machine parsing
- **Parameters**:
  - status (str): Status string ("success" or "error")
  - data (Optional[Dict[str, Any]]): Optional data dictionary to include
  - error (Optional[str]): Optional error message (only for error status)
- **Returns**: str - JSON-formatted string with no trailing newline
- **Output Format**:
  - Success: {"status": "success", ... additional data fields ...}
  - Error: {"status": "error", "error": "error message"}
- **Features**:
  - Merges data fields directly into output dict (flattens structure)
  - Includes error message when present
  - Compact JSON output (no pretty-printing)
  - Machine-readable for CI/CD pipelines

#### `get_exit_code(status, error_type) -> int`
- **Purpose**: Map status/error_type to exit code for CI/CD pipelines
- **Parameters**:
  - status (str): Status string ("success" or "error")
  - error_type (Optional[str]): Optional error type for specific exit codes
- **Returns**: int - Exit code (0-5)
- **Exit Code Mapping**:
  - 0: success (status == "success")
  - 1: generic error (status == "error", no error_type or unknown type)
  - 2: alignment_failed (error_type == "alignment_failed")
  - 3: tests_failed (error_type == "tests_failed")
  - 4: security_failed (error_type == "security_failed")
  - 5: timeout (error_type == "timeout")
- **Features**:
  - Semantic exit codes for CI/CD integration
  - Graceful fallback to 1 for unknown error types
  - Type-safe mapping (uses dict.get with default)

#### `configure_auto_git_for_headless() -> Dict[str, str]`
- **Purpose**: Configure AUTO_GIT environment variables for headless mode
- **Parameters**: None
- **Returns**: dict - Dictionary of configured values with keys: AUTO_GIT_ENABLED, AUTO_GIT_PUSH, AUTO_GIT_PR
- **Features**:
  - Sets environment variables if not already set (respects existing configuration)
  - AUTO_GIT_ENABLED: "true" (enables git automation)
  - AUTO_GIT_PUSH: "true" (automatically pushes commits)
  - AUTO_GIT_PR: "false" (no auto-PR in CI, requires manual review)
  - Non-destructive: Does NOT override existing values
  - Returns dict of actual values (configured or existing)

### Design Patterns

- **Progressive Detection**: Flag -> CI environment -> TTY checks (most to least specific)
- **Non-blocking Enhancement**: Headless mode detection never fails, always returns safe defaults
- **Environment-aware**: Respects existing configuration, doesn't override user choices
- **Machine-friendly Output**: JSON format for CI/CD integration, standardized exit codes

### Security Considerations

- No external dependencies (uses only stdlib: os, sys, json)
- No file I/O operations (stateless detection)
- No subprocess calls (pure Python detection)
- No credential exposure (no environment variable logging)
- Case-insensitive CI environment detection (handles variations)
- Exit codes match POSIX conventions (0 = success, 1+ = error variants)

### Error Handling

- All functions return safe defaults (bool or dict) on any error
- No exceptions raised (graceful degradation)
- Missing environment variables treated as False
- Invalid status/error_type strings handled safely (default to generic error code 1)

### Performance

- detect_headless_flag(): less than 0.1ms (list membership check)
- detect_ci_environment(): less than 0.5ms (environment variable lookups)
- is_headless_mode(): less than 1ms (combined detection with TTY check)
- should_skip_prompts(): less than 1ms (calls is_headless_mode())
- format_json_output(): less than 1ms (JSON serialization)
- get_exit_code(): less than 0.1ms (dict lookup)
- configure_auto_git_for_headless(): less than 1ms (environment variable writes)

### Integration Patterns

**Pattern 1: Skip Interactive Prompts in Headless**
```python
from headless_mode import should_skip_prompts

if should_skip_prompts():
    response = "yes"
else:
    response = input("Continue? (yes/no): ")
```

**Pattern 2: JSON Output for CI/CD**
```python
from headless_mode import is_headless_mode, format_json_output

try:
    result = perform_workflow()
    output = format_json_output("success", {"feature": result})
except Exception as e:
    output = format_json_output("error", error=str(e))

if is_headless_mode():
    print(output)
else:
    print("Workflow completed successfully")
```

**Pattern 3: Exit Codes for CI/CD Integration**
```python
from headless_mode import get_exit_code, format_json_output

try:
    result = run_tests()
    if result.passed:
        output = format_json_output("success", {"tests": result.count})
        exit(get_exit_code("success"))
    else:
        output = format_json_output("error", error="Tests failed")
        exit(get_exit_code("error", "tests_failed"))
except TimeoutError:
    output = format_json_output("error", error="Timeout")
    exit(get_exit_code("error", "timeout"))
```

**Pattern 4: Auto-configure Git for Headless**
```python
from headless_mode import is_headless_mode, configure_auto_git_for_headless

if is_headless_mode():
    config = configure_auto_git_for_headless()
```

### Related Libraries

- auto_implement_git_integration.py - Uses AUTO_GIT env vars configured by headless_mode
- status_tracker.py - Provides test status for exit code determination
- hook_exit_codes.py - Standardized exit code constants

### Used By

- /implement command (respects headless mode, skips prompts)
- /implement --batch command (uses headless detection for mode selection)
- GitHub Actions and other CI/CD systems
- Docker containers (non-TTY environments)
- Headless servers and API backends

### Test Coverage

- Environment detection tests (CI vars, TTY checks, flag parsing)
- Exit code mapping tests (all status/error_type combinations)
- JSON output formatting tests (success, error, merged data)
- Integration tests (headless workflows with auto-git configuration)
- Edge cases: Missing env vars, invalid JSON data, type mismatches

### Version History

- v1.0.0 (2026-01-02) - Initial release with CI/CD detection, JSON output, exit codes, and auto-git configuration

### Backward Compatibility

N/A (new library - Issue #176)

---

## 69. conflict_resolver.py (1016 lines, v1.0.0 - Issue #183)

**AI-powered merge conflict resolution with three-tier escalation strategy**

### Purpose

Resolve git merge conflicts intelligently using Claude API. Handles conflicts from simple (whitespace) to complex (multi-conflict semantic issues) with automatic tier escalation.

### Problem

Merge conflicts interrupt development workflows. Manual resolution requires understanding code context, intent, and impact. Simple conflicts are tedious to resolve manually. Complex conflicts need semantic understanding.

### Solution

Three-tier escalation strategy balances automation with accuracy:

1. **Tier 1 (Auto-Merge)**: Trivial conflicts resolved without AI
   - Whitespace-only differences
   - Identical changes on both sides
   - Instant resolution, zero API cost

2. **Tier 2 (Conflict-Only)**: AI analyzes only conflict blocks
   - Focuses on semantic understanding of changes
   - Faster than full-file analysis
   - Suitable for most real conflicts

3. **Tier 3 (Full-File)**: Comprehensive context analysis
   - Reads entire file for maximum context
   - Handles complex multi-conflict scenarios
   - Chunks large files to respect API limits (100KB per chunk)

### Key Classes

**ConflictBlock**
- Represents a single merge conflict
- Tracks: file_path, start_line, end_line, their_changes, our_changes, base_version
- Extracts conflict range for targeted analysis

**ResolutionSuggestion**
- Recommended resolution with metadata
- Fields: file_path, start_line, end_line, resolved_content, confidence (0.0-1.0), reasoning, tier_used
- Applied atomically to file with backup

**ConflictResolutionResult**
- Final result of resolution attempt
- Fields: success (bool), resolution (optional ResolutionSuggestion), error_message, conflict_count, resolved_count

### Key Functions

**parse_conflict_markers(file_path)**
- Parses git conflict markers (<<<<<<<, =======, >>>>>>>)
- Returns: List[ConflictBlock] with all conflicts found
- Validates file path (CWE-22, CWE-59 prevention)

**resolve_tier1_auto_merge(conflict: ConflictBlock)**
- Detects and resolves trivial conflicts
- Whitespace normalization
- Identical side detection
- Returns: Optional[ResolutionSuggestion] (None if needs escalation)

**resolve_tier2_conflict_only(conflict: ConflictBlock, api_key: str)**
- AI analysis of conflict block only
- Prompt: 200-300 tokens (conflict + reasoning request)
- Returns: ResolutionSuggestion with confidence scoring
- Suitable for 90% of conflicts

**resolve_tier3_full_file(file_path: str, conflicts: List[ConflictBlock], api_key: str)**
- AI analysis with entire file context
- Chunks large files (>100KB)
- Processes chunks sequentially with context preservation
- Returns: ConflictResolutionResult with all resolutions

**apply_resolution(file_path: str, resolution: ResolutionSuggestion)**
- Applies resolution to file
- Atomic operations: backup -> update -> verify
- Returns: bool (success/failure)
- Verifies conflict markers removed

**resolve_conflicts(file_path: str, api_key: str)**
- Main entry point with automatic tier escalation
- Implements escalation logic: Tier 1 -> Tier 2 -> Tier 3
- Returns: ConflictResolutionResult
- Handles all errors gracefully

### Three-Tier Strategy

**Why Escalation?**
- Tier 1 (instant) handles common cases
- Tier 2 (fast) handles most conflicts without full context
- Tier 3 (comprehensive) available for complex scenarios
- Reduces API cost while maintaining quality

**When to Use Each Tier**

| Scenario | Tier | Reason |
|----------|------|--------|
| Whitespace only | 1 | Instant, no AI needed |
| Identical changes | 1 | Deterministic resolution |
| Simple semantic conflict | 2 | Context from conflict block sufficient |
| Multiple conflicts | 2 | Tier 2 handles multiple blocks |
| Cross-cutting changes | 3 | Needs full file context |
| Complex refactoring | 3 | Semantic understanding requires file knowledge |

**Tier 2 vs Tier 3 Performance**
- Tier 2: ~3-5 seconds per conflict (200 tokens)
- Tier 3: ~5-10 seconds per file (500-1000 tokens depending on file size)
- Cost: Tier 2 ~100x cheaper than Tier 3

### Security Features

**Path Validation (CWE-22, CWE-59)**
- validate_path() checks for path traversal
- Symlink detection and rejection
- Absolute path normalization
- User project scope validation

**Log Injection Sanitization (CWE-117)**
- Sanitize conflict markers before logging
- Remove control characters and newlines
- Never log API keys or sensitive data

**API Key Protection**
- Never logged or printed
- Passed only to anthropic.Anthropic client
- Removed from error messages
- Used via environment variable (ANTHROPIC_API_KEY)

**Atomic File Operations**
- Backup created before modification
- Changes written to temporary file
- Atomic rename on success
- Rollback on failure

### Usage Example

```python
from conflict_resolver import resolve_conflicts, parse_conflict_markers

# Method 1: Automatic escalation (recommended)
result = resolve_conflicts("path/to/file.py", api_key="sk-ant-...")

if result.success:
    print(f"Resolved {result.resolved_count}/{result.conflict_count} conflicts")
    print(f"Confidence: {result.resolution.confidence:.0%}")
    print(f"Reasoning: {result.resolution.reasoning}")
else:
    print(f"Error: {result.error_message}")
    print("Manual resolution required")

# Method 2: Manual tier control
conflicts = parse_conflict_markers("file.py")

for conflict in conflicts:
    # Try Tier 1
    suggestion = resolve_tier1_auto_merge(conflict)

    if suggestion is None:
        # Escalate to Tier 2
        suggestion = resolve_tier2_conflict_only(conflict, api_key)

    if suggestion and suggestion.confidence >= 0.7:
        apply_resolution("file.py", suggestion)
    else:
        print(f"Manual resolution needed: Line {conflict.start_line}")

# Method 3: Full-file context
conflicts = parse_conflict_markers("file.py")
result = resolve_tier3_full_file("file.py", conflicts, api_key)

if result.success:
    print(f"Resolved all {result.resolved_count} conflicts")
```

### Integration with /worktree Command

The `--ai-merge` flag integrates conflict_resolver with worktree merge workflow:

```bash
# Merge worktree with AI conflict resolution
/worktree --merge my-feature --ai-merge

# Without AI (manual resolution)
/worktree --merge my-feature
```

**Requirements**:
- ANTHROPIC_API_KEY environment variable set
- Merge conflict(s) present
- User approves AI resolution (interactive prompt)

### Error Handling

- Returns ConflictResolutionResult.success = False on any error
- ConflictResolutionResult.error_message contains details
- Graceful degradation: Missing API key, rate limiting, network errors handled
- Backup preserved on failure for manual recovery

### Performance

- Tier 1: <100ms per conflict (no API)
- Tier 2: 3-5 seconds per conflict (one API call)
- Tier 3: 5-10 seconds per file (handles chunking)
- File I/O: ~10-50ms depending on file size
- Parallel: Can resolve multiple conflicts in single API call

### Design Patterns

- **Tier Escalation**: Start simple, escalate only when needed (cost optimization)
- **Atomic Operations**: Backup-modify-verify prevents corruption
- **Graceful Degradation**: Missing API key doesn't crash, just fails with explanation
- **Progressive Disclosure**: API key only requested when needed (Tier 2+)

See library-design-patterns skill for standardized design patterns.

### Integration Points

**Command**: `/worktree --merge <feature> --ai-merge`
- Integrates conflict resolution into merge workflow
- Requires user consent before AI resolution
- Fallback to manual resolution if AI fails

**Other Libraries**: None currently (self-contained)

### Used By

- worktree_command.py - Integrates via --ai-merge flag
- merge_worktree() function in worktree_manager.py
- Future: Other merge workflows

### Test Coverage

- Tier 1 resolution: Whitespace, identical changes
- Tier 2 resolution: Single and multiple conflicts
- Tier 3 resolution: Full-file context, chunking
- Error cases: Missing file, invalid path, API errors
- Security: Path traversal, symlink detection, log injection
- Edge cases: Empty conflicts, very large files (>1MB), missing API key

### Version History

- v1.0.0 (2026-01-02) - Initial release with three-tier escalation (Issue #183)

### Backward Compatibility

N/A (new library - Issue #183)

## 74. agent_pool.py (495 lines, v1.0.0 - Issue #185)

**Scalable parallel agent pool with priority queue and token-aware rate limiting**

### Purpose

Execute multiple agents concurrently with intelligent task scheduling, priority queue management, token budget enforcement, and work-stealing load balancing. Enables scaling from 3 to 12 agents while preventing resource exhaustion.

### Problem

Sequential agent execution is slow. Parallel execution without coordination causes token budget exhaustion and resource contention. No mechanism to prioritize critical tasks (security, tests) over optional work.

### Solution

Scalable agent pool that manages concurrent execution with four key features:

1. **Priority Queue**: Tasks executed by priority (P1_SECURITY greater than P2_TESTS greater than P3_DOCS greater than P4_OPTIONAL)
2. **Token Tracking**: Sliding window budget enforcement prevents token exhaustion
3. **Work Stealing**: Agents pull tasks from queue based on availability (load balancing)
4. **Graceful Failures**: Timeouts and partial results handled cleanly

### Key Classes

**PriorityLevel (Enum)**
- P1_SECURITY: Highest priority (security-critical tasks)
- P2_TESTS: High priority (test generation)
- P3_DOCS: Medium priority (documentation)
- P4_OPTIONAL: Low priority (optional enhancements)

**TaskHandle**
- Represents submitted task
- Fields: task_id, agent_type, priority, submitted_at
- Returned from submit_task() for result tracking

**AgentResult**
- Result from completed task
- Fields: task_id, success, output, tokens_used, duration
- Contains agent output and execution metrics

**PoolStatus**
- Current pool execution state
- Fields: active_tasks, queued_tasks, completed_tasks, token_usage
- Used for monitoring and debugging

**AgentPool**
- Main pool coordinator
- Manages worker threads, task queue, token tracking, result storage
- Thread-safe with internal locking mechanisms

### Key Functions

**AgentPool.__init__(config: PoolConfig)**
- Initialize pool with configuration
- Starts worker threads
- Sets up token tracking
- Raises ValueError if config invalid

**AgentPool.submit_task(agent_type, prompt, priority, estimated_tokens)**
- Submit task to pool for execution
- Args: agent_type (string), prompt (string, less than 10,000 chars), priority (PriorityLevel), estimated_tokens (optional, default 5000)
- Returns: TaskHandle for tracking
- Raises: ValueError (invalid input), RuntimeError (token budget exhausted)
- CWE-22: Validates agent_type pattern prevents path traversal
- CWE-770: Enforces prompt size limit prevents resource exhaustion

**AgentPool.await_all(handles, timeout)**
- Wait for all submitted tasks to complete
- Args: handles (List[TaskHandle]), timeout (optional, seconds)
- Returns: List[AgentResult] (in same order as input handles)
- Raises: TimeoutError if timeout exceeded
- Blocks until all results available or timeout

**AgentPool.get_pool_status()**
- Get current pool execution state
- Returns: PoolStatus with active/queued/completed task counts and token usage
- Non-blocking, real-time status

**AgentPool.shutdown()**
- Gracefully shutdown pool
- Waits for active tasks to complete (5-second timeout per worker)
- Stops accepting new submissions
- Cleans up worker threads

### Design Patterns

- **Priority Queue**: Queue.PriorityQueue with (priority, submission_time, task_id, task_data) tuple ordering
- **Sliding Window**: TokenTracker manages token budget with time-based expiration
- **Work Stealing**: Worker threads pull tasks based on availability (natural load balancing)
- **Thread Safety**: Lock-protected access to shared state (results, status)
- **Graceful Failures**: Timeouts return partial results, exceptions captured per task

### Security Features

**Path Validation (CWE-22)**
- agent_type validated against regex pattern matching ^[a-z0-9_-]+$
- Prevents path traversal via agent type field
- Explicit error message on invalid input

**Resource Limit (CWE-400)**
- Hard cap at 12 concurrent agents (max_agents parameter)
- Token budget enforcement via sliding window
- Reject submissions exceeding budget
- Default 150,000 token budget

**Resource Limit (CWE-770)**
- Prompt size limited to 10,000 characters
- Prevents excessive memory/API usage
- Validated on submission

**Thread Safety**
- Results locked with threading.Lock
- Status locked with threading.Lock
- Supports concurrent agent execution

### Usage Example

```
from agent_pool import AgentPool, PriorityLevel
from pool_config import PoolConfig

# Create pool with 6 agents and 150K token budget
config = PoolConfig(max_agents=6, token_budget=150000)
pool = AgentPool(config=config)

# Submit high-priority security task
security_handle = pool.submit_task(
    agent_type="security-auditor",
    prompt="Audit new authentication module for vulnerabilities",
    priority=PriorityLevel.P1_SECURITY,
    estimated_tokens=8000
)

# Submit medium-priority doc task
doc_handle = pool.submit_task(
    agent_type="doc-master",
    prompt="Update API documentation for new endpoint",
    priority=PriorityLevel.P3_DOCS,
    estimated_tokens=5000
)

# Wait for all tasks to complete
results = pool.await_all([security_handle, doc_handle], timeout=60.0)

# Process results
for result in results:
    if result.success:
        print(f"Task {result.task_id} completed in {result.duration:.1f}s ({result.tokens_used} tokens)")
        print(f"Output: {result.output}")
    else:
        print(f"Task {result.task_id} failed")

# Get pool status
status = pool.get_pool_status()
print(f"Active: {status.active_tasks}, Queued: {status.queued_tasks}, Complete: {status.completed_tasks}")

# Shutdown
pool.shutdown()
```

### Integration Points

**Commands**:
- `/implement` - May use for parallel validation phase (reviewer + security-auditor + doc-master)
- `/implement --batch` - May use for per-feature parallel agents

**Agents**:
- All agents can be submitted to pool (researcher, planner, implementer, test-master, reviewer, security-auditor, doc-master, etc.)
- Agent type must match valid agent names

**Libraries**:
- PoolConfig (configuration management) - Required
- TokenTracker (token budget enforcement) - Required
- Task (Claude Code Task tool) - External dependency for execution

### Performance

- Task submission: less than 1ms (queue insertion)
- Await all: Depends on task duration (typically 2-30 minutes per task)
- Pool startup: approximately 10ms (thread creation)
- Pool shutdown: 5-25 seconds (worker join timeout)
- Memory overhead: approximately 1KB per task in queue

### Test Coverage

- Task submission and validation (agent type, prompt size, token budget)
- Priority queue ordering (P1 greater than P2 greater than P3 greater than P4)
- Token budget enforcement (reject over-budget submissions)
- Concurrent task execution (worker threads)
- Result collection and ordering
- Pool status tracking
- Graceful shutdown
- Security: Path traversal prevention, resource limits
- Error handling: Timeout, invalid config, budget exceeded

### Version History

- v1.0.0 (2026-01-02) - Initial release with priority queue and token tracking (Issue #185)

### Backward Compatibility

N/A (new library - Issue #185)

## 75. pool_config.py (196 lines, v1.0.0 - Issue #185)

**Agent pool configuration with validation and loading**

### Purpose

Manage agent pool configuration with support for defaults, environment variables, and PROJECT.md loading. Provides validated configuration for AgentPool initialization.

### Problem

Agent pool needs configurable max concurrency and token budget. Configuration should support multiple sources (defaults, env vars, PROJECT.md) with validation and graceful degradation.

### Solution

PoolConfig dataclass with multi-source loading and validation:
- Constructor arguments (highest priority)
- Environment variables (AGENT_POOL_*)
- PROJECT.md file (Agent Pool Configuration section)
- Built-in defaults (fallback)

### Key Classes

**PoolConfig**
- Dataclass holding pool configuration
- Fields: max_agents (3-12), token_budget (positive), priority_enabled (bool), token_window_seconds (positive)
- Validates on instantiation via __post_init__
- Provides class methods for loading from multiple sources

### Key Functions

**PoolConfig.__init__(max_agents, token_budget, priority_enabled, token_window_seconds)**
- Initialize configuration with defaults or custom values
- Validates all parameters in __post_init__
- Raises ValueError if validation fails

**PoolConfig._validate()**
- Validate configuration values
- Checks: max_agents (3-12 range), token_budget (greater than 0), token_window_seconds (greater than 0)
- Raises ValueError with descriptive message on failure

**PoolConfig.load_from_env()**
- Load configuration from environment variables
- Variables: AGENT_POOL_MAX_AGENTS, AGENT_POOL_TOKEN_BUDGET, AGENT_POOL_PRIORITY_ENABLED, AGENT_POOL_TOKEN_WINDOW_SECONDS
- Uses constructor defaults as fallback
- Returns: PoolConfig instance
- Raises ValueError if validation fails

**PoolConfig.load_from_project(project_root)**
- Load configuration from PROJECT.md file
- Searches for Agent Pool Configuration JSON block
- Format: max_agents, token_budget, priority_enabled, token_window_seconds
- Falls back to defaults if not found
- Returns: PoolConfig instance
- Graceful degradation on parse errors

### Configuration Sources Priority

1. Constructor arguments (highest - explicit values)
2. Environment variables (AGENT_POOL_* override defaults)
3. PROJECT.md (Agent Pool Configuration section)
4. Built-in defaults (fallback - max_agents=6, token_budget=150000, priority_enabled=true, token_window_seconds=60)

### Environment Variables

| Variable | Description | Valid Range | Default |
|----------|-------------|-------------|---------|
| AGENT_POOL_MAX_AGENTS | Max concurrent agents | 3-12 | 6 |
| AGENT_POOL_TOKEN_BUDGET | Token budget for window | Positive | 150000 |
| AGENT_POOL_PRIORITY_ENABLED | Enable priority queue | true/false | true |
| AGENT_POOL_TOKEN_WINDOW_SECONDS | Sliding window duration | Positive | 60 |

### Security Features

**Input Validation**
- Type checking (int, bool)
- Range validation (max_agents: 3-12)
- Positive value checking (token_budget, token_window_seconds)
- Descriptive error messages

**Graceful Degradation**
- Invalid PROJECT.md doesn't crash, falls back to env/defaults
- Missing env vars use defaults
- Parse errors logged and ignored

**No External Dependencies**
- Pure Python dataclass
- No network calls
- No subprocess execution

### Usage Example

```
from pool_config import PoolConfig
from pathlib import Path

# Use defaults
config = PoolConfig()
print(f"Default: {config.max_agents} agents, {config.token_budget} token budget")

# Load from environment
config = PoolConfig.load_from_env()

# Load from PROJECT.md with fallback
config = PoolConfig.load_from_project(Path(".claude/PROJECT.md"))

# Custom values
config = PoolConfig(max_agents=8, token_budget=200000)

# Pass to AgentPool
from agent_pool import AgentPool
pool = AgentPool(config=config)
```

### Integration Points

**AgentPool**: Required configuration parameter
**Commands**: `/implement`, `/implement --batch` may read config

### Performance

- Load from env: less than 1ms (os.getenv + int conversion)
- Load from PROJECT.md: 5-10ms (file I/O + JSON parsing)
- Validation: less than 1ms (range checks)
- Total overhead: Negligible compared to agent execution

### Test Coverage

- Default construction and validation
- Environment variable loading and override
- PROJECT.md loading and parsing
- Validation: Range checks, positive values, type checking
- Graceful degradation: Missing/invalid sources
- Error messages and exception types

### Version History

- v1.0.0 (2026-01-02) - Initial release with multi-source loading (Issue #185)

### Backward Compatibility

N/A (new library - Issue #185)

## 76. token_tracker.py (177 lines, v1.0.0 - Issue #185)

**Token-aware rate limiting with sliding window**

### Purpose

Track token usage across multiple agents with sliding time window to enforce budget limits and prevent token exhaustion during parallel execution.

### Problem

Parallel agent execution can quickly exhaust token budget without rate limiting. Need mechanism to track total usage, allow budget enforcement, and prevent over-submission.

### Solution

Token tracker with sliding window approach:
- Records usage per agent with timestamp
- Expires old records automatically based on time window
- Enforces budget by rejecting submissions exceeding remaining budget
- Provides usage breakdown by agent for monitoring

### Key Classes

**UsageRecord**
- Represents single token usage event
- Fields: agent_id, tokens, timestamp
- Used internally for sliding window tracking

**TokenTracker**
- Main tracking class
- Manages budget enforcement and usage tracking
- Thread-safe for concurrent agent access

### Key Functions

**TokenTracker.__init__(budget, window_seconds)**
- Initialize tracker with budget and window
- Args: budget (positive int), window_seconds (positive int, default 60)
- Raises ValueError if budget or window_seconds non-positive
- Sets up empty usage records list

**TokenTracker.record_usage(agent_id, tokens)**
- Record token usage for an agent
- Args: agent_id (string), tokens (int)
- Creates UsageRecord with current timestamp
- Appends to usage_records list
- Logs debug message

**TokenTracker.can_submit(estimated_tokens)**
- Check if submission would exceed budget
- Args: estimated_tokens (int)
- Returns: bool (True if within budget, False otherwise)
- Cleans up expired records before checking
- Non-blocking check

**TokenTracker.get_remaining_budget()**
- Get remaining token budget in current window
- Returns: int (remaining budget, greater than or equal to 0)
- Cleans up expired records first
- Calculates total usage in window and subtracts from budget

**TokenTracker._cleanup_expired_records()**
- Remove records outside sliding window
- Private method called before budget checks
- Removes records with timestamp greater than window_seconds ago
- Uses datetime.now() for current time

**TokenTracker.get_usage_by_agent()**
- Get per-agent token usage breakdown
- Returns: Dict[str, int] (agent_id to total tokens)
- Cleans up expired records first
- Useful for monitoring and debugging

### Sliding Window Design

**How it works**:
1. Each token usage recorded with timestamp
2. Before budget check, expired records removed (older than window_seconds)
3. Remaining records summed for total usage
4. Remaining budget = budget - total_usage
5. Submission allowed if remaining greater than or equal to estimated_tokens

**Why it works**:
- Allows temporary spikes within window
- Automatic expiration prevents permanent budget exhaustion
- Window defaults to 60 seconds (configurable)
- Per-agent tracking enables usage monitoring

**Example**:
Budget: 150,000 tokens, Window: 60 seconds

At T=0:
  - Agent A uses 50,000 tokens
  - Remaining: 100,000

At T=30:
  - Agent B uses 70,000 tokens
  - Total usage: 120,000
  - Remaining: 30,000

At T=65:
  - Agent A's usage expired (recorded at T=0, now greater than 60s old)
  - Remaining usage: 70,000 (only Agent B)
  - Remaining budget: 80,000

### Security Features

**Budget Enforcement (CWE-400)**
- Hard budget limits prevent token exhaustion
- Reject submissions exceeding available budget
- Per-agent tracking prevents single agent hogging budget

**No External Dependencies**
- Pure Python implementation
- No network calls
- No subprocess execution
- No file I/O

**Thread-Safe**
- Uses datetime for consistent timestamps
- Stateless operations (no race conditions on list operations in CPython)
- Safe for concurrent agent access

### Usage Example

```
from token_tracker import TokenTracker

# Create tracker: 150K token budget, 60-second window
tracker = TokenTracker(budget=150000, window_seconds=60)

# Check if can submit task
if tracker.can_submit(estimated_tokens=10000):
    # Submit task...
    # After execution, record actual usage
    tracker.record_usage(agent_id="researcher", tokens=8500)
else:
    print("Token budget exhausted, cannot submit new tasks")

# Check remaining budget
remaining = tracker.get_remaining_budget()
print(f"Remaining budget: {remaining} tokens")

# Monitor per-agent usage
usage_by_agent = tracker.get_usage_by_agent()
for agent_id, tokens in usage_by_agent.items():
    print(f"Agent {agent_id}: {tokens} tokens")

# Usage expires automatically after window
# At T=65 seconds, records from T=0 automatically removed
```

### Integration Points

**AgentPool**: Required for token budget enforcement
**PoolConfig**: Provides window_seconds configuration

### Performance

- Record usage: less than 1ms (append to list)
- Get remaining budget: 1-5ms (cleanup + summation, depends on record count)
- Can submit check: 1-5ms (cleanup + comparison)
- Cleanup: O(n) where n equals records in window (typically 1-20 records)

### Test Coverage

- Tracker initialization with valid/invalid budgets
- Recording usage and timestamp tracking
- Can_submit budget checking and remaining calculation
- Usage expiration and cleanup (time-based)
- Per-agent usage breakdown
- Thread safety with concurrent operations
- Edge cases: Empty records, zero budget, very large usage

### Version History

- v1.0.0 (2026-01-02) - Initial release with sliding window (Issue #185)

### Backward Compatibility

N/A (new library - Issue #185)


## 77. ideation_engine.py (431 lines, v1.0.0 - Issue #186)

### Purpose

Orchestrates automated discovery of improvement opportunities across code quality, security, performance, accessibility, and technical debt through multi-category analysis.

### Problem

Manual code review is time-consuming and misses systemic issues. Development teams need automated suggestions for improvements without running separate tools for each category (security scanners, linters, complexity checkers, etc.). Single-category tools miss cross-cutting improvements.

### Solution

Unified analysis framework that runs specialized analyzers (ideators) for five improvement categories, aggregates findings with metadata (severity, confidence, effort, impact), and generates prioritized recommendations and GitHub issue descriptions.

### Key Classes

**IdeationCategory** (Enum)
- SECURITY: Security vulnerabilities and weaknesses
- PERFORMANCE: Performance bottlenecks and inefficiencies
- QUALITY: Code quality issues (tests, duplication, complexity)
- ACCESSIBILITY: User experience and accessibility issues
- TECH_DEBT: Technical debt accumulation

**IdeationSeverity** (Enum)
- CRITICAL: Requires immediate attention
- HIGH: High-priority, address soon
- MEDIUM: Medium-priority for planning
- LOW: Low-priority nice-to-have improvements
- INFO: Informational findings

**IdeationResult** (Dataclass)
- category: IdeationCategory
- severity: IdeationSeverity
- location: str (file:line format)
- title: str (short finding title)
- description: str (detailed issue description)
- suggested_fix: str (recommended fix)
- confidence: float (0.0-1.0)
- impact: str (impact assessment)
- effort: str (effort estimate)
- references: List[str] (CWE, OWASP, etc.)

**IdeationReport** (Dataclass)
- timestamp: str (ISO format)
- categories_analyzed: List[IdeationCategory]
- total_findings: int
- findings_by_severity: Dict[IdeationSeverity, int]
- results: List[IdeationResult]
- analysis_duration: float (seconds)
- Methods:
  - to_markdown() - Generate markdown report
  - filter_by_severity(min_severity) - Filter by severity level

**IdeationEngine** (Main Orchestrator)
- __init__(project_root: Path) - Initialize with project root
- run_ideation(categories: List[IdeationCategory]) - Run analysis for specified categories
- prioritize_results(results: List[IdeationResult]) - Sort by severity and confidence
- generate_issues(results, min_severity) - Create GitHub issue descriptions
- filter_by_minimum_severity(results, min_severity) - Filter by severity threshold

### Key Functions

**IdeationEngine.run_ideation()**
- Coordinates all ideators for requested categories
- Returns IdeationReport with findings aggregated
- Measures analysis duration
- Calculates statistics by severity

**IdeationEngine.prioritize_results()**
- Sorts by severity (CRITICAL > HIGH > MEDIUM > LOW > INFO)
- Secondary sort by confidence score
- Returns highest-priority findings first

**IdeationEngine.generate_issues()**
- Creates GitHub issue descriptions from results
- Filters by minimum severity
- Formats as markdown with metadata

**IdeationReport.filter_by_severity()**
- Returns results at or above specified severity
- Enables severity-based filtering

### Security Features

**Path Traversal Prevention (CWE-22)**
- All paths converted to Path objects
- Relative paths generated using relative_to()
- No string concatenation for paths

**Input Validation**
- Confidence scores validated (0.0-1.0)
- Project root validated as directory
- Category/severity enums restrict values

**Safe File Handling**
- pathlib.Path for all file operations
- read_text() with encoding specified
- Exception handling for file access errors

**No Arbitrary Code Execution**
- Pattern matching only (no eval, exec, import)
- Read-only analysis
- No subprocess calls

### Integration Points

**Ideators Package**: Five specialized analyzers
**IdeationReportGenerator**: Markdown report generation
**Command Integration**: /ideate command can use this engine
**Agent Integration**: planner agent can use for feature discovery

### Performance

- Analysis duration: 2-10 seconds (depends on project size)
- Report generation: less than 500ms

### Test Coverage

- IdeationCategory and IdeationSeverity enums
- IdeationResult dataclass with confidence validation
- IdeationReport creation and aggregation
- Result prioritization and filtering
- Issue generation and formatting
- Edge cases: empty results, single results, duplicate severities

### Version History

- v1.0.0 (2026-01-02) - Initial release with five ideators (Issue #186)

### Backward Compatibility

N/A (new library - Issue #186)

## 78. ideation_report_generator.py (231 lines, v1.0.0 - Issue #186)

### Purpose

Generates formatted markdown reports from ideation analysis results with multiple output formats and filtering options.

### Problem

Raw IdeationReport requires custom formatting for different use cases. Users need multiple report types (full, summary, category-specific, critical-only) with flexible filtering.

### Solution

Dedicated report generator providing multiple report generation methods with flexible filtering and formatting options.

### Key Classes

**IdeationReportGenerator**
- generate(report) - Main entry point
- generate_markdown_report(report, filters) - Full report with optional filtering
- generate_summary_report(report) - Summary only (no detailed findings)
- generate_findings_by_category(report, category) - Category-specific report
- generate_critical_findings_report(report) - Critical issues only

### Key Functions

**generate()**
- Main entry point, delegates to generate_markdown_report()

**generate_markdown_report()**
- Applies optional filtering by min_severity
- Returns formatted markdown string
- Uses IdeationReport.to_markdown() for consistency

**generate_summary_report()**
- Header with timestamp and duration
- Total findings count
- Breakdown by severity and category
- No detailed findings

**generate_findings_by_category()**
- Filters results to single category
- Returns full report for that category

**generate_critical_findings_report()**
- Filters to CRITICAL severity only
- Concise format for urgent action items

### Security Features

**No External Dependencies**
- Pure Python (only stdlib and ideation_engine)
- No network calls
- No subprocess execution

**Safe Report Generation**
- No eval, exec, or arbitrary code execution
- String formatting only

**Input Validation**
- Report and category enum validation
- No string injection vectors

### Integration Points

**IdeationEngine**: Provides IdeationReport objects
**Commands**: /ideate command uses this generator
**Agents**: planner agent can use summary reports

### Performance

- Report generation: less than 500ms
- Summary generation: less than 100ms

### Test Coverage

- Report generation with filtering options
- Summary/category/critical report generation
- Severity filtering (all combinations)
- Edge cases: empty results, mixed severities

### Version History

- v1.0.0 (2026-01-02) - Initial release (Issue #186)

### Backward Compatibility

N/A (new library - Issue #186)

## 79-83. ideators/ package (5 specialized analyzers - Issue #186)

### Purpose

Five specialized Python modules detecting improvement opportunities in specific categories:
- security_ideator.py: Security vulnerabilities
- performance_ideator.py: Performance bottlenecks
- quality_ideator.py: Code quality issues
- accessibility_ideator.py: Accessibility and UX issues
- tech_debt_ideator.py: Technical debt patterns

### 79. security_ideator.py (252 lines)

Detects security vulnerabilities:
- SQL injection (string concatenation in queries)
- XSS vulnerabilities (unescaped HTML output)
- Command injection (shell command construction)
- Path traversal vulnerabilities
- Insecure cryptography usage

Reports: CRITICAL (SQL/command injection), HIGH (XSS, path traversal), MEDIUM (weak crypto)

### 80. performance_ideator.py (198 lines)

Detects performance issues:
- N+1 query problems (ORM queries in loops)
- Inefficient algorithms (nested loops, O(n^2))
- Missing database indexes
- Unoptimized file I/O (repeated reads)
- Memory leaks (unbounded lists)

Reports: HIGH (N+1 queries), MEDIUM (inefficient algorithms), LOW (memory patterns)

### 81. quality_ideator.py (304 lines)

Detects code quality issues:
- Missing test coverage (no test_*.py files)
- Code duplication (similar functions)
- High cyclomatic complexity (deep nesting)
- Missing docstrings
- Long functions/methods

Reports: MEDIUM (missing tests, duplication, complexity), LOW (docstrings, length)

### 82. accessibility_ideator.py (184 lines)

Detects accessibility issues:
- Missing help text (functions without docstrings)
- Poor error messages (generic exceptions)
- Missing validation error messages
- Inaccessible UI patterns
- Missing internationalization

Reports: LOW (accessibility concerns), INFO (best practices)

### 83. tech_debt_ideator.py (225 lines)

Detects technical debt patterns:
- Deprecated API usage
- Outdated dependency versions
- Known vulnerability patterns
- Code style violations
- Inefficient imports

Reports: MEDIUM (deprecated APIs), LOW (style, imports)

### Common Integration Pattern

All ideators follow a standard pattern with __init__ and analyze() methods returning List[IdeationResult].

### Performance Baselines

- Security analysis: 1-2 seconds
- Performance analysis: 1-2 seconds
- Quality analysis: 2-3 seconds (file iteration)
- Accessibility analysis: 1-2 seconds
- Tech debt analysis: 1-3 seconds
- Total: 6-12 seconds for all categories

### Files Added

- plugins/autonomous-dev/lib/ideation_engine.py (431 lines)
- plugins/autonomous-dev/lib/ideation_report_generator.py (231 lines)
- plugins/autonomous-dev/lib/ideators/__init__.py (28 lines)
- plugins/autonomous-dev/lib/ideators/security_ideator.py (252 lines)
- plugins/autonomous-dev/lib/ideators/performance_ideator.py (198 lines)
- plugins/autonomous-dev/lib/ideators/quality_ideator.py (304 lines)
- plugins/autonomous-dev/lib/ideators/accessibility_ideator.py (184 lines)
- plugins/autonomous-dev/lib/ideators/tech_debt_ideator.py (225 lines)
- tests/unit/lib/test_ideation_engine.py (comprehensive tests)

### Version History

- v1.0.0 (2026-01-02) - Initial release with five ideators (Issue #186)

### Backward Compatibility

N/A (new libraries - Issue #186)


## 84. parallel_validation.py (753 lines, v1.0.0 - Issue #188)

### Purpose

Migrates /implement STEP 4.1 parallel validation from prompt engineering to reusable agent_pool library integration. Provides unified parallel validation execution for security-auditor, reviewer, and doc-master agents with security-first priority mode, automatic retry logic, and result aggregation.

### Problem

Previously, /implement Step 4.1 parallel validation relied on prompt engineering and manual coordination within the conversation. This approach:
- Tight coupling between /implement and validation logic
- No reusability for other workflows needing parallel validation
- Manual retry logic and error handling
- Difficult to test in isolation
- Hard to optimize performance independently

### Solution

Dedicated parallel_validation library that:
- Encapsulates validation orchestration in reusable functions
- Integrates with AgentPool library for scalable parallel execution
- Provides security-first priority mode (security blocks on failure)
- Automatic retry with exponential backoff (transient vs permanent error classification)
- Result aggregation and parsing from agent outputs
- Comprehensive error handling and validation

### Key Classes

**ValidationResults** (dataclass)
- security_passed: bool - Security audit pass/fail status
- review_passed: bool - Code review pass/fail status
- docs_updated: bool - Documentation update status
- failed_agents: List[str] - List of agent types that failed
- execution_time_seconds: float - Total execution time
- security_output: str - Raw security agent output
- review_output: str - Raw reviewer output
- docs_output: str - Raw doc-master output

### Key Functions

**execute_parallel_validation()**
- Main entry point for parallel validation
- Args: feature_description, project_root, priority_mode, changed_files, max_retries
- Returns: ValidationResults
- Raises: ValueError (invalid input), SecurityValidationError (security failure in priority mode), ValidationTimeoutError (all agents timeout)
- Behavior: Coordinates agent pool execution and result aggregation

**_execute_security_first()**
- Security-first priority mode execution
- Phase 1: Runs security agent first (blocking)
- Phase 2: If security passes, runs reviewer + doc-master in parallel
- Raises: SecurityValidationError if security audit fails
- Rationale: Security failures should block feature implementation immediately

**_aggregate_results()**
- Parses agent outputs and aggregates into ValidationResults
- Looks for "PASS"/"FAIL" in security-auditor output
- Looks for "APPROVE"/"REQUEST_CHANGES" in reviewer output
- Looks for "UPDATED" in doc-master output
- Handles missing results with appropriate defaults
- Returns: ValidationResults with aggregated status

**retry_with_backoff()**
- Executes agent task with automatic retry on transient errors
- Exponential backoff: 2^n seconds (2s, 4s, 8s, ...)
- Transient errors (timeout, connection) - automatically retried
- Permanent errors (syntax, import, type) - fail fast
- Args: pool, agent_type, prompt, max_retries, priority
- Returns: AgentResult from successful execution
- Raises: Exception on permanent error or max retries exceeded

**is_transient_error()**
- Classify error as transient (should retry)
- Returns: True for TimeoutError, ConnectionError, HTTP 5xx patterns
- Returns: False for permanent errors

**is_permanent_error()**
- Classify error as permanent (fail fast)
- Returns: True for SyntaxError, ImportError, ValueError, PermissionError, TypeError, KeyError, AttributeError
- Returns: False for transient errors

### Key Features

**Parallel Validation Modes**:
- All parallel mode (default): All three agents run simultaneously
- Security-first mode: Security runs first, blocks on failure, then parallel validation

**Automatic Retry**:
- Transient error detection (timeout, network, HTTP 5xx)
- Permanent error detection (syntax, import, type)
- Exponential backoff (2^n seconds)
- Circuit breaker: max_retries limit (default 3)

**Result Aggregation**:
- Parse agent outputs from free-form text
- Track execution time from AgentResult.duration
- Aggregate failures with detailed error messages
- Handle missing agents with appropriate fallbacks

**Security-First Priority**:
- Security agent runs first
- If security fails, raises SecurityValidationError immediately
- Blocks reviewer and doc-master from executing
- Prevents unsafe code from being approved

**Input Validation**:
- Feature description validation (non-empty)
- Project root path validation (Path object, exists)
- File path validation (format check)

### Security Features

**CWE-22 (Path Traversal Prevention)**:
- project_root must be Path object
- project_root.exists() validated
- Only relative paths in changed_files (no absolute paths)

**Input Validation**:
- Feature description non-empty check
- Path object type validation
- File path format validation

**Error Classification**:
- Transient vs permanent error detection
- Prevents retry loops on permanent errors
- Protects against infinite backoff

### Integration Points

**AgentPool Library** (Issue #185)
- Uses AgentPool.submit_task() for agent execution
- Uses AgentPool.await_all() for result retrieval
- Respects PriorityLevel (P1_SECURITY, P2_TESTS, P3_DOCS)
- Gracefully handles pool initialization

**auto-implement Command**
- Called from /implement Step 4.1 (parallel validation phase)
- Replaces prompt engineering with library call
- Passes feature description, project root, changed files

**PoolConfig Library** (Issue #185)
- Uses PoolConfig.load_from_env() for configuration
- Supports environment-based pool settings

### Performance

**Baseline** (3 agents parallel):
- Execution time: 2-5 minutes (depends on agent response time)
- Security audit: 60-90 seconds
- Code review: 45-60 seconds
- Documentation: 45-60 seconds
- Total (parallel): approximately 90 seconds (wall clock, not sequential sum)

**Retry Performance Impact**:
- Transient error retry: +2s per retry (exponential backoff)
- Permanent error: immediate fail (no backoff)
- Typical: 1 retry needed in 5 percent of cases

### Test Coverage

- ValidationResults dataclass creation and serialization
- execute_parallel_validation() with valid/invalid inputs
- _execute_security_first() security blocking behavior
- _aggregate_results() with various agent outputs
- retry_with_backoff() transient and permanent error handling
- is_transient_error() classification accuracy
- is_permanent_error() classification accuracy
- Missing agent result handling
- Timeout and exception propagation
- Integration with mocked AgentPool

**Test Files**:
- tests/unit/lib/test_parallel_validation_library.py (943 lines - comprehensive unit tests)
- tests/integration/test_parallel_validation.py (integration tests with real agent pool)

### Files Added

- plugins/autonomous-dev/lib/parallel_validation.py (753 lines)
- tests/unit/lib/test_parallel_validation_library.py (943 lines)
- tests/integration/test_parallel_validation.py (updated)

### Files Modified

- plugins/autonomous-dev/config/install_manifest.json (added parallel_validation.py to library manifest)

### API Usage Example

```python
from pathlib import Path
from parallel_validation import execute_parallel_validation, SecurityValidationError

# Execute parallel validation with security-first mode
results = execute_parallel_validation(
    feature_description="Add JWT authentication to login endpoint",
    project_root=Path("/path/to/project"),
    priority_mode=True,  # Security blocks on failure
    changed_files=["src/auth/jwt.py", "tests/test_jwt.py"]
)

# Check results
if not results.security_passed:
    raise SecurityValidationError(f"Security failed: {results.security_output}")

print(f"Validation complete:")
print(f"  Security: PASS" if results.security_passed else "  Security: FAIL")
print(f"  Review: PASS" if results.review_passed else "  Review: FAIL")
print(f"  Docs: UPDATED" if results.docs_updated else "  Docs: NOT UPDATED")
print(f"  Duration: {results.execution_time_seconds:.1f}s")

if results.failed_agents:
    print(f"Failed agents: {', '.join(results.failed_agents)}")
```

### Command-Line Usage

```bash
# Execute parallel validation with CLI
python -m autonomous_dev.lib.parallel_validation \
  --feature "Add JWT authentication" \
  --project-root /path/to/project \
  --priority-mode \
  --changed-files src/auth/jwt.py tests/test_jwt.py \
  --output-format json
```

### Dependencies

- **AgentPool** (plugins/autonomous-dev/lib/agent_pool.py) - Agent orchestration
- **PoolConfig** (plugins/autonomous-dev/lib/pool_config.py) - Configuration management
- Standard library: logging, time, dataclasses, pathlib, typing, argparse, json, sys

### Version History

- v1.0.0 (2026-01-02) - Initial release, migrate from /implement prompt engineering (Issue #188)

### Backward Compatibility


## 85. ralph_loop_manager.py (305 lines, v1.0.0 - Issue #189)

**Purpose**: Orchestrate self-correcting agent execution with retry loops, circuit breaker pattern, and token usage tracking.

**Problem**: Agents sometimes complete tasks incompletely or fail silently. Manual retry coordination is error-prone, and cost overruns from infinite loops are possible.

**Solution**: Ralph Loop Manager that tracks iterations, enforces circuit breaker on consecutive failures, limits token usage, and determines when to allow retry vs. blocking further attempts.

**Location**: `plugins/autonomous-dev/lib/ralph_loop_manager.py`

**Key Features**:
- Iteration tracking (max 5 iterations per session)
- Circuit breaker pattern (3 consecutive failures blocks retry)
- Token usage tracking (prevents cost overruns)
- Thread-safe state operations with atomic writes
- Graceful degradation for corrupted state files

**Constants**:
- `MAX_ITERATIONS = 5` - Maximum retry attempts per session
- `CIRCUIT_BREAKER_THRESHOLD = 3` - Consecutive failures to trigger circuit breaker
- `DEFAULT_TOKEN_LIMIT = 50000` - Token limit for entire loop

**Key Classes**:
- `RalphLoopState` (dataclass) - Tracks session state (current iteration, tokens used, consecutive failures, circuit breaker status, retry_history)
  - **retry_history** (NEW v3.48.0): List of retry attempt records with timestamp, iteration, tokens, status
- `RalphLoopManager` - Main orchestrator with methods:
  - `record_attempt(tokens_used)` - Record token consumption for attempt
  - `should_retry()` - Check if retry allowed (respects max iterations, circuit breaker, token limit)
  - `record_success()` - Record successful completion
  - `record_failure(error_msg)` - Record failure and check circuit breaker
  - `get_state()` - Get current state for inspection
  - `reset_state()` - Reset for new session

**Retry Decision Logic**:
1. Check max iterations (5 iterations -> block)
2. Check circuit breaker (3 consecutive failures -> block)
3. Check token limit (exceeded -> block)
4. If all checks pass -> allow retry

**Security Features**:
- Atomic state file writes (temp + rename to prevent corruption)
- Thread-safe operations with locks
- Path validation to prevent directory traversal
- Graceful degradation for corrupted state files (logs warning, continues)
- No code execution from user input

**API Highlights**:
```python
from ralph_loop_manager import RalphLoopManager, MAX_ITERATIONS, CIRCUIT_BREAKER_THRESHOLD

# Create manager for session
manager = RalphLoopManager("session-123", token_limit=50000)

# Record attempt with tokens
manager.record_attempt(tokens_used=5000)

# Check if should retry
if manager.should_retry():
    # Retry execution
    try:
        # Run agent task
        pass
    except Exception as e:
        manager.record_failure(str(e))
else:
    # Stop (max iterations, circuit breaker, or token limit)
    print("Retry blocked: " + manager.get_state().stop_reason)

# Record success
manager.record_success()
```

**State Persistence**:
- State stored in `~/.autonomous-dev/ralph_loop_sessions/[session-id].json`
- Portable path detection works from any directory
- Atomic writes prevent corruption on crash

**Test Coverage**:
- RalphLoopState creation and serialization
- RalphLoopManager initialization and state management
- should_retry() with various state conditions
- record_attempt() token tracking
- record_failure() circuit breaker triggering
- Thread safety with concurrent operations
- State file corruption handling

**Version History**:
- v1.0.0 (2026-01-02) - Initial release for self-correcting agent execution (Issue #189)

**Dependencies**:
- Standard library: json, threading, tempfile, pathlib, dataclasses, datetime

**Files Added**:
- plugins/autonomous-dev/lib/ralph_loop_manager.py (305 lines)
- tests/unit/lib/test_ralph_loop_manager.py (test suite)

---

## 86. success_criteria_validator.py (432 lines, v1.0.0 - Issue #189)

**Purpose**: Provide multiple validation strategies to determine if agent task completed successfully.

**Problem**: Different tasks need different validation approaches. Some need test verification (pytest), others need file existence checks, and still others need output parsing. Each agent implements validation differently, leading to inconsistency and bugs.

**Solution**: Unified validator library supporting five validation strategies with security hardening, timeout enforcement, and clear success/failure messages.

**Location**: `plugins/autonomous-dev/lib/success_criteria_validator.py`

**Key Features**:
- Multiple validation strategies (pytest, safe_word, file_existence, regex, json)
- Security validations (path traversal, ReDoS, command injection)
- Timeout enforcement for long-running operations
- Thread-safe operation
- Clear success/failure messages with context

**Validation Strategies**:

1. **Pytest Strategy**
   - Runs pytest and checks pass/fail
   - Timeout: 60 seconds by default (v3.48.0, increased from 30s)
   - Configurable via PYTEST_TIMEOUT environment variable (e.g., PYTEST_TIMEOUT=120)
   - Returns test output and status
   - Use case: Unit/integration test verification

2. **Safe Word Strategy**
   - Searches for completion marker in agent output
   - Case-insensitive matching
   - Returns match position and context
   - Use case: Agent output verification (e.g., "TASK_COMPLETE")

3. **File Existence Strategy**
   - Verifies all expected files exist
   - Checks file paths, rejects symlinks (CWE-59)
   - Returns list of missing files
   - Use case: Output file verification

4. **Regex Strategy**
   - Extracts data via regex pattern
   - ReDoS prevention (1 second timeout)
   - Validates extracted value against expected
   - Use case: Structured output validation

5. **JSON Strategy**
   - Extracts data via JSONPath expression
   - Validates extracted value against expected
   - Provides detailed error context
   - Use case: JSON response validation

**Constants**:
- `DEFAULT_PYTEST_TIMEOUT = 60` - Timeout for pytest runs (v3.48.0: increased from 30s for slower test suites)
- `REGEX_TIMEOUT = 1` - Timeout for regex operations (prevent ReDoS)

**Environment Variables** (NEW v3.48.0, Issue #256):
- `PYTEST_TIMEOUT` - Override DEFAULT_PYTEST_TIMEOUT per test run (e.g., PYTEST_TIMEOUT=120)
- Checked only when timeout not explicitly provided to validate_pytest()
- Allows per-environment tuning (local dev, CI/CD, slow hardware)

**Key Functions**:
```python
# Pytest validation
success, message = validate_pytest("tests/test_feature.py", timeout=10)

# Safe word validation
success, message = validate_safe_word(agent_output, safe_word="SAFE_WORD_COMPLETE")

# File existence validation
success, message = validate_file_existence(["output.txt", "data.json"])

# Output parsing validation
success, message = validate_output_parsing(
    agent_output,
    strategy="regex",
    pattern=r"Result: (\d+)",
    expected="42"
)
```

**Security Features**:
- Path traversal prevention (CWE-22): Validates paths exist and are files/directories
- Symlink rejection (CWE-59): Rejects symlinks to prevent TOCTOU attacks
- Command injection prevention (CWE-78): Uses subprocess.run with list arguments (no shell=True)
- ReDoS prevention: Regex operations timeout after 1 second
- Input validation: Validates patterns, paths, JSONPath expressions
- No code execution from user input

**Validation Result**:
```python
class ValidationResult:
    # Result of validation attempt.
    success: bool          # True if validation passed
    message: str           # Human-readable result message
    strategy: str          # Which strategy was used
    details: Dict          # Additional context (matches, file list, etc.)
    duration_seconds: float # How long validation took
```

**API Highlights**:
```python
from success_criteria_validator import validate_success, validate_pytest

# Generic validator (auto-selects strategy based on criteria type)
result = validate_success(
    criteria={
        "strategy": "pytest",
        "test_file": "tests/test_auth.py"
    }
)

# Specific validator
result = validate_pytest("tests/test_auth.py", timeout=30)

# Check result
if result.success:
    print(f"PASS: {result.message}")
else:
    print(f"FAIL: {result.message}")
    print(f"Details: {result.details}")
```

**Test Coverage**:
- validate_pytest() with passing/failing tests
- validate_safe_word() with various outputs
- validate_file_existence() with existing/missing files
- validate_output_parsing() with regex/json strategies
- Security: Path traversal rejection, symlink detection, injection prevention
- Timeout enforcement for long operations
- Edge cases: Empty patterns, missing files, malformed JSON
- Performance: Validation speed benchmarks

**Version History**:
- v1.0.0 (2026-01-02) - Initial release with five validation strategies (Issue #189)

**Dependencies**:
- Standard library: json, subprocess, re, pathlib, typing, signal, os

**Files Added**:
- plugins/autonomous-dev/lib/success_criteria_validator.py (432 lines)
- tests/unit/lib/test_success_criteria_validator.py (test suite)

---
100 percent compatible - new library, no API changes to existing code. Replaces internal /implement Step 4.1 orchestration without affecting external interfaces.


---

## 87. agent_feedback.py (946 lines, v1.0.0 - Issue #191)

**Purpose**: Machine learning feedback loop for intelligent agent routing optimization based on historical performance metrics.

**Problem**: Agent selection is static. Planner assigns agents without data about their performance on similar tasks. This leads to suboptimal routing and missed optimization opportunities.

**Solution**: Feedback loop system that:
1. Records agent performance after each feature (duration, success, feature type, complexity)
2. Queries historical data to recommend optimal agents for new features
3. Maintains aggregated statistics by agent/feature-type/complexity combination
4. Provides fallback agent suggestions when primary recommendation has low confidence
5. Automatically prunes old data (90-day retention) with monthly aggregation

**Key Features**:

1. **Feature Type Classification**: 7 categories (security, api, ui, refactor, docs, tests, general)
   - Keyword-based classification (e.g., "auth", "oauth" → security)
   - Fallback to "general" for unmatched features
   - Configurable keyword patterns per category

2. **Confidence Scoring**: Statistical confidence metric
   - Formula: confidence = success_rate * sqrt(min(executions, 50) / 50)
   - Low confidence (less than 10 executions): 0.0-0.5
   - Medium confidence (30 executions): 0.77 with 100% success
   - High confidence plateau (50+ executions): success_rate as limiting factor
   - Ensures recommendations backed by sufficient data

3. **Smart Routing**: Query optimal agents per feature
   - Top N recommendations (sorted by confidence)
   - Fallback agents for redundancy
   - Reasoning explanation for each recommendation
   - Success rates and execution counts included

4. **Data Aggregation**: Monthly aggregation of old feedback
   - Preserves daily feedback for recent data (90-day window)
   - Aggregates older data by month for retention
   - Automatically runs during cleanup operations
   - Maintains queryability across all time ranges

5. **Atomic Writes**: Crash-proof state persistence
   - Tempfile + atomic rename (prevents corruption on crash)
   - Lock-based coordination for concurrent access
   - Graceful error handling for corrupted state files
   - Audit logging for all state changes

6. **Security Hardening**:
   - CWE-22 (path traversal): Path validation and exists() checks
   - Input validation: agent_name, complexity, duration, feature types
   - Sanitization: Feature descriptions and metadata
   - No code execution from user input
   - Audit trail logging for all operations

**Dataclasses**:

Single feedback entry (AgentFeedback):
- agent_name: Name of executing agent
- feature_type: Type of feature (security, api, ui, refactor, docs, tests, general)
- complexity: Feature complexity (SIMPLE, STANDARD, COMPLEX)
- duration: Execution time in minutes
- success: Whether agent completed successfully
- timestamp: ISO 8601 timestamp (auto-added)
- metadata: Additional context (owasp_checks, coverage, etc.)

Aggregated statistics (FeedbackStats):
- success_rate: Percentage of successful executions (0.0-1.0)
- avg_duration: Average execution time in minutes
- executions: Total execution count
- last_execution: ISO 8601 timestamp of most recent execution
- confidence: Confidence score (0.0-1.0) based on data volume

Recommendation with fallbacks (RoutingRecommendation):
- agent_name: Primary recommended agent
- confidence: Confidence score (0.0-1.0)
- reasoning: Explanation of recommendation
- fallback_agents: Backup agents if primary unavailable
- stats: Performance metrics for this agent

**State File Structure** (.claude/agent_feedback.json):

JSON structure with version, feedback array, and aggregated monthly statistics:
- version: "1.0"
- feedback: Array of AgentFeedback entries with agent_name, feature_type, complexity, duration, success, timestamp, metadata
- aggregated: Nested object by month/agent/feature_type/complexity with total_executions, success_count, total_duration

**Public API**:

Key functions:
- record_feedback(agent_name, feature_type, complexity, duration, success, metadata=None) - Record agent performance after task completion
- query_recommendations(feature_type, complexity, top_n=3) - Get recommended agents for a feature
- get_agent_stats(agent_name) - Get statistics for specific agent
- classify_feature_type(description) - Classify feature type from description
- cleanup_old_data() - Prune expired data and aggregate old feedback

Usage:
- Record performance after agent completes
- Query recommendations when planning next features
- Classify features automatically from descriptions
- Run periodic cleanup for maintenance

**Usage Example** (Integration in /implement):

After security-auditor completes:
1. Record the execution with agent_name, feature_type, complexity, duration, success flag
2. For future features, planner queries recommendations for security/STANDARD
3. Suggests agents to use based on historical performance

**Constants**:

- DATA_RETENTION_DAYS = 90: Keep daily feedback for 90 days
- CONFIDENCE_SCALE_FACTOR = 50: Executions needed to reach high confidence
- DEFAULT_TOP_N = 3: Default number of recommendations to return
- FEEDBACK_FILE = ".claude/agent_feedback.json"

**Integration Points**:

1. Planner Agent: Query recommendations when assigning agents
2. Agent Exit: Record feedback after agent completion (SubagentStop hook)
3. Maintenance: Periodic cleanup via /health-check command
4. Reporting: Session reports include feedback statistics

**Test Coverage** (73 tests total):

Unit Tests (55 tests):
- Dataclass validation and serialization
- Feature type classification (7 categories, precedence rules)
- record_feedback() with validation, atomicity, timestamp handling
- query_recommendations() with confidence sorting, fallback logic
- get_agent_stats() with filtered results and edge cases
- classify_feature_type() with keyword matching and fallback
- aggregate_feedback() with month bucketing and data preservation
- cleanup_old_data() with expiration and aggregation
- Error handling: Invalid inputs, corrupted state files, missing data
- Atomic writes and crash recovery
- Concurrent access and lock management

Integration Tests (18 tests):
- End-to-end feedback workflow (record to query to recommend)
- Data persistence across restarts
- Feature type classification in real scenarios
- Confidence score accuracy across data volumes
- Aggregation correctness (90-day retention, month bucketing)
- Concurrent record_feedback calls
- Cleanup effectiveness (pruning + aggregation)
- Performance benchmarks (query speed, data size management)
- Fallback routing when primary recommendation unavailable

**Version History**:
- v1.0.0 (2026-01-02) - Initial release with intelligent agent routing (Issue #191)

**Dependencies**:
- Standard library: json, pathlib, typing, datetime, threading, tempfile, os
- Internal: path_utils, validation, audit_logging

**Files Added**:
- plugins/autonomous-dev/lib/agent_feedback.py (946 lines)
- tests/unit/lib/test_agent_feedback.py (1,241 lines, 55 tests)
- tests/integration/test_agent_feedback_integration.py (617 lines, 18 tests)

**Files Modified**:
- plugins/autonomous-dev/config/install_manifest.json - Added agent_feedback.py to lib section

---
100 percent compatible - new library for feedback-driven agent routing without affecting existing workflows. Optional integration point for planner optimization.

---

## 88. memory_relevance.py (287 lines, v1.0.0 - Issue #192)

Purpose: TF-IDF-based relevance scoring for cross-session memories enabling intelligent retrieval of contextually relevant memories from previous sessions.

Problem: Memory injection needs intelligent filtering to avoid context bloat. Too many irrelevant memories waste tokens; too few memories reduce context continuity. No built-in relevance scoring.

Solution: TF-IDF (Term Frequency-Inverse Document Frequency) scoring system that:
1. Extracts keywords from query using stopword removal
2. Calculates relevance scores between query and memory content
3. Applies recency boost to favor recent memories
4. Filters low-relevance memories using threshold (configurable)
5. Returns ranked memories sorted by relevance score (highest first)

Key Features:

1. Keyword Extraction:
   - Extracts keywords from text using simple TF-IDF tokenization
   - Removes stopwords (common words like the, and, to)
   - Case-insensitive matching
   - Returns sorted list of unique keywords

2. Relevance Scoring:
   - TF-IDF formula: overlap_ratio * recency_boost
   - overlap_ratio: Count of matching keywords / total keywords in query
   - Recency boost: 1.0 + (days_old / 30) up to 1.3 max bonus
   - Range: 0.0 (no match) to 1.3 (perfect match + recent)
   - Timestamp-aware (expects ISO 8601 format)

3. Memory Ranking:
   - Sorts memories by relevance score (descending)
   - Filters memories below threshold (default 0.3)
   - Preserves original memory structure with added relevance_score
   - Returns empty list if no matches meet threshold

4. Threshold Filtering:
   - Default threshold: 0.3 (allows partial matches)
   - Configurable per call via threshold parameter
   - High thresholds (0.7+) only include high-relevance memories
   - Low thresholds (0.1) include most memories

Public API:

Key functions:
- extract_keywords(text: str) - Extract keywords from text
- calculate_relevance(query: str, memory_text: str, timestamp: str) - Calculate relevance score between query and memory
- rank_memories(query: str, memories: List, threshold: float) - Rank and filter memories by relevance

Constants:

- STOPWORDS - Set of common English stopwords
- RECENCY_BOOST_MAX = 1.3 - Maximum boost for recent memories
- RECENCY_BOOST_SCALE = 30 - Days to reach max boost
- DEFAULT_THRESHOLD = 0.3 - Minimum relevance score

Integration Points:

1. Memory Injection: Used by auto_inject_memory.py to filter relevant memories
2. Formatting: Ranked memories passed to memory_formatter.py for token-aware formatting
3. SessionStart Hook: Called during memory injection at session start

Test Coverage (32 tests):

Unit Tests:
- extract_keywords() with various text inputs, stopword filtering
- calculate_relevance() with exact/partial/no matches, timestamp variations
- rank_memories() with threshold filtering, sorting, edge cases
- Recency boost calculation and max limits
- Empty/None input handling
- Performance benchmarks for keyword extraction

Version History:
- v1.0.0 (2026-01-02) - Initial release with TF-IDF relevance scoring (Issue #192)

Dependencies:
- Standard library: datetime, typing

Files Added:
- plugins/autonomous-dev/lib/memory_relevance.py (287 lines)
- tests/unit/lib/test_memory_relevance.py (test suite)

---
100 percent compatible - new library for intelligent memory filtering without affecting existing code.

---

## 89. memory_formatter.py (261 lines, v1.0.0 - Issue #192)

Purpose: Token-aware formatting for memories with budget constraints enabling cost-effective memory injection while preventing context bloat.

Problem: Memory injection must respect token budget to prevent context bloat. No built-in token counting or budget-aware formatting. Memories must be formatted for readability with markdown structure.

Solution: Formatting system that:
1. Counts tokens using character-based estimation (accurate within 10%)
2. Formats individual memories with metadata and structure
3. Formats memory blocks with budget awareness
4. Truncates memories when budget exceeded (prioritizes high-relevance)
5. Adds markdown headers and structure for readability

Key Features:

1. Token Counting:
   - Character-based estimation: tokens approx equals character_count / 4
   - Fast estimation (no external models needed)
   - Accurate within 5-10% for typical text
   - Handles edge cases (empty strings, unicode)

2. Memory Block Formatting:
   - Markdown format with metadata header
   - Relevance score displayed prominently
   - Timestamp for temporal context
   - Content with proper line breaks
   - Example: Relevance: 0.85 | 2026-01-02 with content

3. Budget-Aware Formatting:
   - Respects max_tokens constraint
   - Prioritizes high-relevance memories when budget constrained
   - Graceful truncation (shows ... if truncated)
   - Returns formatted markdown block with headers

4. Token Budgeting:
   - Default budget: 500 tokens
   - Configurable per call
   - Includes header/footer tokens in budget calculation
   - Reports actual tokens used

Public API:

Key functions:
- count_tokens(text: str) - Estimate tokens in text
- format_memory_block(memory: Dict) - Format single memory for display
- format_memories_with_budget(memories: List, max_tokens: int) - Format all memories within token budget

Constants:

- TOKENS_PER_CHAR = 4 - Assumed characters per token
- HEADER_TOKENS = 20 - Overhead for markdown headers
- DEFAULT_MAX_TOKENS = 500 - Default budget
- TRUNCATION_MARKER = ... - Indicator of truncated content

Integration Points:

1. Memory Injection: Used by auto_inject_memory.py to format memories
2. Relevance Scoring: Takes output from memory_relevance.py (ranked memories)
3. SessionStart Hook: Formats memories before prompt injection

Test Coverage (28 tests):

Unit Tests:
- count_tokens() with various text lengths, unicode, special chars
- format_memory_block() with all metadata fields, missing fields
- format_memories_with_budget() with budget limits, priority sorting
- Truncation behavior at budget limits
- Edge cases: Empty memories, zero budget, single memory
- Performance benchmarks for formatting speed

Version History:
- v1.0.0 (2026-01-02) - Initial release with token-aware formatting (Issue #192)

Dependencies:
- Standard library: typing

Files Added:
- plugins/autonomous-dev/lib/memory_formatter.py (261 lines)
- tests/unit/lib/test_memory_formatter.py (test suite)

---
100 percent compatible - new library for efficient memory formatting without affecting existing code.

---

## 90. auto_inject_memory.py (9,089 lines, v1.0.0 - Issue #192)

Purpose: Auto-inject relevant memories at SessionStart enabling cross-session context continuity for architectural decisions, blockers, and patterns.

Problem: Agents have no memory between sessions. Architectural decisions, blockers, and patterns must be re-explained. Manual context recovery is slow and error-prone. SessionStart lacks mechanism to inject persistent context.

Solution: SessionStart hook that:
1. Loads memories from .claude/memories/session_memories.json
2. Ranks memories by relevance to current task (TF-IDF)
3. Formats memories within token budget (default: 500)
4. Injects formatted memories into initial prompt as markdown context
5. Environment variable control (MEMORY_INJECTION_ENABLED, default false)

Key Features:

1. Memory Loading:
   - Loads from .claude/memories/session_memories.json
   - Graceful degradation if file missing (logs info, continues)
   - Validates JSON structure before processing
   - Handles corrupted memory files safely

2. Relevance Ranking:
   - Uses TF-IDF scoring to rank memories by relevance
   - Recency boost favors recent memories (1-30 days)
   - Threshold filtering (default: 0.7) removes low-relevance memories
   - Configurable via MEMORY_RELEVANCE_THRESHOLD env var

3. Token Budget Enforcement:
   - Default budget: 500 tokens
   - Configurable via MEMORY_INJECTION_TOKEN_BUDGET env var
   - Prioritizes high-relevance memories when budget constrained
   - Graceful truncation if over budget

4. Prompt Injection:
   - Injects formatted memories into prompt as markdown block
   - Placed at top of prompt for visibility
   - Includes Relevant Context from Previous Sessions header
   - Clean markdown formatting with relevance scores

5. Environment Variable Control:
   - MEMORY_INJECTION_ENABLED (default: false) - Enable/disable injection
   - MEMORY_INJECTION_TOKEN_BUDGET (default: 500) - Max tokens for memories
   - MEMORY_RELEVANCE_THRESHOLD (default: 0.7) - Min relevance score

Public API:

Key functions:
- inject_memories_into_prompt(original_prompt: str, project_root: Path, max_tokens: int) - Inject memories into prompt
- should_inject_memories() - Check if injection enabled
- load_relevant_memories(query: str, project_root: Path, threshold: float) - Load and rank relevant memories

Integration Points:

1. SessionStart Hook: Triggered automatically when new session/conversation starts
2. Memory Layer: Reads memories from memory_layer.py storage
3. Relevance Scoring: Uses memory_relevance.py for ranking
4. Formatting: Uses memory_formatter.py for token-aware formatting
5. Prompt Modification: Modifies initial prompt before agent sees it

Configuration:

Environment variables (set in .env or shell):
- MEMORY_INJECTION_ENABLED=true - Enable memory injection (default: false)
- MEMORY_INJECTION_TOKEN_BUDGET=1000 - Max tokens (default: 500)
- MEMORY_RELEVANCE_THRESHOLD=0.5 - Min score (default: 0.7)

Test Coverage (36 tests):

Unit Tests:
- inject_memories_into_prompt() with various scenarios
- should_inject_memories() with env var states
- load_relevant_memories() with query matching
- Prompt injection formatting
- Memory file loading and validation
- Edge cases: Missing files, corrupted JSON, empty memories
- Performance benchmarks for injection speed

Version History:
- v1.0.0 (2026-01-02) - Initial release with SessionStart memory injection (Issue #192)

Dependencies:
- memory_layer.py - Memory persistence
- memory_relevance.py - Relevance scoring
- memory_formatter.py - Token-aware formatting
- path_utils.py - Path detection
- validation.py - Input validation

Files Added:
- plugins/autonomous-dev/lib/auto_inject_memory.py (9,089 lines)
- tests/unit/lib/test_auto_inject_memory.py (test suite)
- tests/integration/test_auto_inject_memory_integration.py (test suite)

---
100 percent compatible - new SessionStart hook for optional memory injection without affecting existing workflows.


---

## 91. feature_flags.py (230 lines, v1.0.0 - Issue #193)

**Purpose**: Configuration management for optional features with graceful degradation enabling selective feature control without code changes.

**Problem**: Features like conflict_resolver and auto_git_workflow should be configurable. Users need ability to opt-out of features without modifying code. Configuration should have sensible defaults and graceful failure modes.

**Solution**: Feature flag system that:
1. Loads configuration from .claude/feature_flags.json (optional)
2. Defaults all features to ENABLED (opt-out model)
3. Provides graceful degradation for missing/invalid configs
4. Prevents path traversal attacks via validate_path()
5. Has built-in defaults for all known features

**Key Features**:

1. Feature Flag Loading:
   - Loads from .claude/feature_flags.json
   - Opt-out model (all features enabled by default)
   - Missing file returns empty dict (all features enabled)
   - Invalid JSON returns empty dict (graceful degradation)

2. Default Behaviors:
   - conflict_resolver: enabled=true, confidence_threshold=0.8, security_requires_manual=true
   - auto_git_workflow: enabled=true, auto_push=false, auto_pr=false

3. Security:
   - Path validation via validate_path() (CWE-22)
   - No arbitrary code execution
   - JSON parsing with error handling
   - Graceful fallback on errors

4. Configuration File Format:
   - Location: .claude/feature_flags.json
   - Format: JSON with feature names as keys
   - Structure: {"feature_name": {"enabled": true, "key": "value"}}

**Public API**:

Key functions:
- is_feature_enabled(feature_name: str) -> bool - Check if feature is enabled
- get_feature_config(feature_name: str) -> Dict - Get complete feature configuration
- get_default_flags() -> Dict - Get all default flags
- _load_feature_flags() -> Dict - Load flags from configuration file (internal)
- _get_feature_flags_path() -> Optional[Path] - Get path to flags file (internal)
- _find_project_root() -> Optional[Path] - Find project root (internal)

**Configuration**:

Feature Flags File (.claude/feature_flags.json):
```json
{
  "conflict_resolver": {
    "enabled": true,
    "confidence_threshold": 0.8,
    "security_requires_manual": true
  },
  "auto_git_workflow": {
    "enabled": true,
    "auto_push": false,
    "auto_pr": false
  }
}
```

Default Behavior:
- Missing file = all features enabled
- Missing feature = enabled
- Invalid JSON = all features enabled
- Read errors = all features enabled

**Integration Points**:

1. Conflict Resolver: worktree_conflict_integration.py checks conflict_resolver flag
2. Git Automation: auto_git_workflow hook checks auto_git_workflow flag
3. Worktree Manager: merge_worktree() honors conflict_resolver configuration
4. Feature Control: Any system can check is_feature_enabled() before executing

**Test Coverage**:

Unit Tests:
- is_feature_enabled() with file present/missing/corrupted
- get_feature_config() with various configurations
- Default flag loading
- Path validation (CWE-22 prevention)
- Graceful degradation for missing/invalid files
- Edge cases: Empty flags, wrong JSON structure

**Version History**:
- v1.0.0 (2026-01-02) - Initial release for conflict resolver integration (Issue #193)

**Dependencies**:
- security_utils.py - Path validation
- Standard library: json, pathlib, typing

**Files Added**:
- plugins/autonomous-dev/lib/feature_flags.py (230 lines)
- tests/unit/lib/test_feature_flags.py (test suite)

---
100 percent compatible - new optional configuration system without affecting existing features.

---

## 92. worktree_conflict_integration.py (387 lines, v1.0.0 - Issue #193)

**Purpose**: Glue layer integrating AI-powered conflict resolution into worktree workflow with security detection and confidence thresholds enabling automatic merge conflict handling.

**Problem**: /worktree --merge conflicts are 100% manual. Users must edit files, understand conflict markers, resolve manually. This blocks automated workflows and requires human intervention. No way to automatically suggest resolutions or enforce security reviews.

**Solution**: Integration system that:
1. Detects merge conflicts from git output
2. Triggers AI resolution via conflict_resolver.py
3. Enforces confidence thresholds (0.8 default)
4. Requires manual review for security files
5. Provides three-tier escalation strategy
6. Integrates with worktree_manager.merge_worktree()

**Key Features**:

1. Conflict Detection:
   - Parses git merge output for conflict markers
   - Detects files with <<<<<<< or ======= or >>>>>>>
   - Returns list of conflicted file paths

2. Security Detection:
   - Detects security-related files by pattern
   - Patterns: security_*.py, credentials.py, secrets.py, *.key, *.pem, *.crt
   - Path patterns: /security/, /credentials/, /secrets/
   - Forces manual review regardless of confidence

3. Confidence Thresholds:
   - AUTO_COMMIT_THRESHOLD = 0.8 (80%)
   - High confidence (>=0.8) + not security = auto-commit
   - Medium confidence (0.6-0.8) = suggest but manual review
   - Low confidence (<0.6) = fallback to manual
   - Security files always require manual review

4. Three-Tier Escalation:
   - Tier 1: Auto-resolve and auto-commit (high confidence, not security)
   - Tier 2: Suggest resolution, require manual approval (medium confidence or security file)
   - Tier 3: Fallback to manual merge (low confidence or AI error)

5. Feature Flag Integration:
   - Checks conflict_resolver feature flag
   - Returns empty results if feature disabled
   - Graceful degradation if API key missing

**Public API**:

Key functions:
- resolve_worktree_conflicts(conflict_files: List[str], api_key: Optional[str]) -> List[ConflictResolutionResult] - Resolve multiple files
- should_auto_commit(result: ConflictResolutionResult) -> bool - Check if should auto-commit
- get_resolution_confidence(result: ConflictResolutionResult) -> float - Extract confidence score
- detect_conflicts_in_output(git_output: str) -> List[str] - Parse git output for conflicts
- has_conflict_markers(file_path: str) -> bool - Check if file has conflict markers
- is_security_related(file_path: str) -> bool - Detect security files

**Configuration**:

Feature Flags:
- conflict_resolver feature flag (must be enabled)

Environment Variables:
- ANTHROPIC_API_KEY - Required for AI resolution

Constants:
- AUTO_COMMIT_THRESHOLD = 0.8 - Confidence threshold for auto-commit

**Security**:

1. Path Validation:
   - All file paths validated via validate_path() (CWE-22)
   - Rejects relative paths with ..
   - Rejects symlinks

2. Security File Detection:
   - Strict pattern matching (avoids false positives)
   - Requires manual review for security files
   - Always requires manual review regardless of confidence

3. API Key Handling:
   - Read from environment only (never logged)
   - Graceful failure if missing
   - Returns empty results if missing

4. Audit Logging:
   - All resolutions logged via audit_log()
   - All errors logged with context
   - Non-sensitive information only

5. Error Handling:
   - Path validation errors handled gracefully
   - Missing API key returns empty results
   - Resolution failures fallback to manual
   - Missing dependencies handled safely

**Integration Points**:

1. Worktree Manager: Called by merge_worktree(auto_resolve=True)
2. Conflict Resolver: Calls resolve_conflicts() for each file
3. Feature Flags: Checks is_feature_enabled('conflict_resolver')
4. Git Automation: Results feed into auto-commit decision

**Test Coverage**:

Unit Tests:
- is_security_related() with various patterns
- detect_conflicts_in_output() with git merge output
- has_conflict_markers() with conflict marker detection
- resolve_worktree_conflicts() with single/multiple files
- should_auto_commit() with confidence thresholds
- get_resolution_confidence() with valid/missing resolutions
- Path validation and error handling
- Graceful degradation scenarios

Integration Tests:
- End-to-end merge with conflict resolution
- Security file detection and manual review enforcement
- Feature flag integration
- Error scenarios (missing API key, disabled feature)

**Version History**:
- v1.0.0 (2026-01-02) - Initial release integrating conflict resolver into worktree (Issue #193)

**Dependencies**:
- conflict_resolver.py (Issue #183) - AI resolution logic
- feature_flags.py - Feature configuration
- security_utils.py - Path validation and audit logging
- path_utils.py - Dynamic path detection
- Standard library: json, re, subprocess, pathlib, typing

**Files Added**:
- plugins/autonomous-dev/lib/worktree_conflict_integration.py (387 lines)
- tests/unit/lib/test_worktree_conflict_integration.py (test suite)
- tests/integration/test_worktree_merge_with_conflicts.py (integration tests)

---
100 percent compatible - optional integration layer that preserves existing /worktree --merge behavior when disabled or on errors.


## 67. research_persistence.py (901 lines, v1.0.0 - Issue #196, enhanced Issue #628)

**Purpose**: Auto-save research findings to docs/research/ with frontmatter metadata and caching, enabling research reuse across sessions and features without duplication.

**Problem**: Research findings are lost when conversation clears with /clear. No caching mechanism for repeated research topics. No centralized research knowledge base. Manual research duplication across features wastes time and introduces inconsistency.

**Solution**: Create research_persistence.py library providing save/load functions, age-based cache checking, and automatic index generation for research catalog.

**Key Features**:

1. **Research Saving** (save_research):
   - Saves to docs/research/TOPIC_NAME.md (SCREAMING_SNAKE_CASE naming)
   - YAML frontmatter: topic, created, updated, sources
   - Markdown content: findings plus automatically generated source links
   - Atomic write pattern (temp file plus replace) for safe concurrent access
   - Preserves created timestamp on updates

2. **Cache Checking** (check_cache):
   - Returns path if recent research exists
   - Age-based checking: max_age_days parameter (default: 30 days)
   - Fast path: file existence plus stat check (O(1))

3. **Research Loading** (load_cached_research):
   - Loads file and parses YAML frontmatter
   - Returns dict with: topic, created, updated, sources, content
   - Handles malformed files gracefully (returns None)

4. **Index Generation** (update_index):
   - Scans all .md files in docs/research/ (except README.md)
   - Generates README.md with research catalog table
   - Columns: Topic, Created, Sources, File

5. **Topic to Filename** (topic_to_filename):
   - Converts JWT Authentication to JWT_AUTHENTICATION.md
   - SCREAMING_SNAKE_CASE naming
   - Sanitizes special characters and truncates to filesystem limits

6. **Issue Research Detection** (detect_issue_research):
   - Scans a GitHub issue body for H2 headings that indicate pre-researched content from /create-issue
   - Recognises 24 sections (13 original + 11 empirical/scientific added in Issue #1009): "Implementation Approach", "What Does NOT Work", "Security Considerations", "Test Scenarios", "Architecture", "Research Findings", "Technical Details", "Existing Patterns", "Edge Cases", "Background", "Context", "Dependencies", "Scenarios", "Data Source", "Empirical Analysis", "Empirical Evidence", "Experimental Results", "Findings Source", "Measurements", "Observed Behavior", "Proposed Configuration", "Proposed Values", "References", "Results"
   - Returns is_research_rich (True when section_count >= 3), matched_sections, section_count, and issue_body_as_research (concatenated content)
   - Used by /implement STEP 3 to skip redundant STEP 4 research when the issue already contains sufficient context

**Public API**:

Key functions:
- save_research(topic: str, findings: str, sources: List[str]) -> Path
- check_cache(topic: str, max_age_days: int = 30) -> Optional[Path]
- load_cached_research(topic: str) -> Optional[Dict[str, Any]]
- update_index() -> Path
- topic_to_filename(topic: str) -> str
- detect_issue_research(issue_body: str) -> Dict[str, Any]

Custom Exception:
- ResearchPersistenceError - Raised on validation/IO errors

**Security Features**:

1. **Atomic Write Pattern**: Temp file plus atomic rename for safe concurrent access
2. **Path Traversal Prevention (CWE-22)**: Sanitized filenames, validated paths
3. **Symlink Rejection (CWE-59)**: Via validate_session_path()
4. **Input Validation**: Topic, findings, sources validation
5. **Error Handling**: Disk full (ENOSPC), permission errors handled gracefully

**Integration with Path Utils**:

- Uses get_research_dir() from path_utils.py (NEW in Issue #196)
- Portable path detection (works from any directory)
- Creates docs/research/ with safe permissions (0o755)

**Configuration**:

Constants:
- Cache age: max_age_days parameter (default: 30 days)
- Filename truncation: 252 chars max (255 - 3 for .md)
- Permissions: 0o644 for research files, 0o755 for directories

**Dependencies**:

Standard Library:
- os - temp file creation, write operations
- re - topic sanitization regex
- tempfile - atomic write pattern
- datetime - timestamp generation
- pathlib - path operations
- typing - type hints

Project Dependencies:
- path_utils.py - get_research_dir() function
- validation.py - validate_session_path() function

**Usage Examples**:

Save research with metadata and sources:
```
from research_persistence import save_research
path = save_research(
    topic=JWT Authentication,
    findings=## Key Findings: 1. JWT is stateless,
    sources=[https://jwt.io]
)
```


Save pre-merged research blob for pipeline restart scenarios (Issue #1232):
```
from research_persistence import save_merged_research_blob
path = save_merged_research_blob(
    merged="## Merged Research Content...",
    cache_key="jwt_authentication_2026_01_15"
)
```
Check cache before researching:
```
from research_persistence import check_cache
cached_path = check_cache(JWT Authentication, max_age_days=30)
if cached_path:
    print(Cache hit, use existing research)
```

Load cached research:
```
from research_persistence import load_cached_research
data = load_cached_research(JWT Authentication)
if data:
    print(data[content])
```

Update research catalog:
```
from research_persistence import update_index
readme_path = update_index()
```

**Test Coverage**:

Unit Tests (50+ test cases):
- topic_to_filename conversion (SCREAMING_SNAKE_CASE)
- save_research function (file creation, frontmatter, atomic writes)
- check_cache function (age-based checking)
- load_cached_research function (parsing, error handling)
- update_index function (catalog generation)
- Frontmatter parsing (YAML validation)
- Security validation (CWE-22, CWE-59)
- Error handling (disk full, permissions, corruption)

Integration Tests:
- Save and load round-trip
- Multiple research files with index generation
- Cache hit/miss with age boundaries
- Cross-project portability

**Performance**:

Time Complexity:
- save_research(): O(n) where n = findings size
- check_cache(): O(1) file existence check
- load_cached_research(): O(n) where n = file size
- update_index(): O(m) where m = number of .md files

Typical Performance:
- save_research: less than 50ms for typical research
- check_cache: less than 5ms (file stat check)
- load_cached_research: less than 20ms for typical file
- update_index: less than 100ms for 50 research files

**Version History**:
- v1.0.0 (2026-01-03) - Initial release for research persistence (Issue #196)

**Files Added**:
- plugins/autonomous-dev/lib/research_persistence.py (700 lines)
- tests/unit/lib/test_research_persistence.py (1023 lines)

**Files Modified**:
- plugins/autonomous-dev/lib/path_utils.py - Added get_research_dir() function
- plugins/autonomous-dev/config/install_manifest.json - Added research_persistence.py to lib section

---
100 percent compatible - new optional library for research caching without affecting existing workflows.

## 93. comprehensive_doc_validator.py (708 lines, v1.0.0 - Issue #198)

**Purpose**: Validate cross-references between documentation files to prevent documentation drift and ensure accuracy.

**Problem**: Documentation gets out of sync with code during development. Commands listed in README may not exist in code. Features listed in PROJECT.md may not be implemented. Code examples may have wrong API signatures. No systematic validation catches drift until manual reviews, causing user confusion.

**Solution**: Comprehensive documentation validator with four validation categories (command exports, project features, code examples, counts) plus auto-fix engine for safe patterns. Integrates into /implement pipeline via doc-master agent.

**Key APIs**:

**DataClasses**:
- ValidationIssue: Represents single validation issue
  - category: str - Issue category (command, feature, example, count)
  - severity: str - Issue severity (error, warning, info)
  - message: str - Human-readable description
  - file_path: str - Path to file with issue
  - line_number: int - Line number (0 if unknown)
  - auto_fixable: bool - Whether issue can be auto-fixed safely
  - suggested_fix: str - Suggested fix description

- ValidationReport: Comprehensive validation report
  - issues: List[ValidationIssue] - All issues found
  - has_issues: bool (property) - Whether any issues found
  - has_auto_fixable: bool (property) - Whether any can be auto-fixed
  - has_manual_review: bool (property) - Whether any require manual review
  - auto_fixable_issues: List[ValidationIssue] (property) - Filtered auto-fixable list
  - manual_review_issues: List[ValidationIssue] (property) - Filtered manual review list

**Main Class**:
- ComprehensiveDocValidator:
  - __init__(repo_root: Path, batch_mode: bool = False) - Initialize validator
  - validate_all() -> ValidationReport - Run all validation checks
  - validate_command_exports() -> List[ValidationIssue] - Validate README vs commands/
  - validate_project_features() -> List[ValidationIssue] - Validate PROJECT.md SCOPE vs code
  - validate_code_examples() -> List[ValidationIssue] - Validate API signatures in docs
  - auto_fix_safe_patterns(issues: List[ValidationIssue]) -> int - Auto-fix safe patterns

**Validation Categories**:

1. **Command Export Validation** (validate_command_exports):
   - Scans plugins/autonomous-dev/commands/ for all command files
   - Extracts command names from filenames and docstrings
   - Checks each command has entry in plugins/autonomous-dev/README.md
   - Detects missing command entries (error severity)
   - Detects orphaned command files with no README entries (warning severity)
   - Auto-fix: Generates markdown snippet for missing entries

2. **Project Feature Validation** (validate_project_features):
   - Parses PROJECT.md SCOPE (In Scope) section
   - Extracts implemented features from code files and agents
   - Detects features in PROJECT.md but not implemented (warning severity)
   - Detects implemented features not in PROJECT.md (error severity)
   - Auto-fix: Adds missing features to PROJECT.md SCOPE with descriptions

3. **Code Example Validation** (validate_code_examples):
   - Extracts docstring examples from agent and skill files
   - Parses function signatures from actual code
   - Validates example signatures match implementation
   - Reports line numbers for manual review (warning severity, not auto-fixable)
   - Handles parse errors gracefully (reports as issues, doesn't crash)

4. **Count Validation** (implicit in validate_project_features):
   - Validates agent counts in CLAUDE.md (Agents: X)
   - Validates command counts (Commands: X)
   - Validates skill counts (Skills: X)
   - Detects count mismatches with actual implementation
   - Auto-fix: Updates numbers to match actual counts

**Auto-Fix Engine** (auto_fix_safe_patterns):
- Safely patches documentation with suggested fixes
- Only fixes safe patterns:
  - Missing command entries (appends to README)
  - Count mismatches (updates numbers in-place)
  - Not auto-fixed: feature descriptions, example signatures, complex logic
- Non-blocking: Never raises exceptions
- Logs all fixes to audit trail
- Returns count of successfully fixed issues

**Integration Points**:

- /implement pipeline: Runs after doc-master agent completes
- doc-master agent: Calls ComprehensiveDocValidator before finalizing docs
- /sync command: Includes validation in sync workflow
- PreCommit hook: Optional validation gate before commit (VALIDATE_COMPREHENSIVE_DOCS=true)

**Configuration**:

Environment Variables:
- VALIDATE_COMPREHENSIVE_DOCS: Enable/disable validation (default: false)
  - Set to true in batch mode to enable validation
  - Set to false to disable validation checks

**Security Features**:

- Path validation via security_utils (CWE-22, CWE-59 prevention)
  - Validates all file paths before opening
  - Prevents path traversal attacks
  - Rejects symlinks via validate_path()
- Non-blocking design: Never raises exceptions
  - Logs issues safely
  - Continues validation on errors
  - Graceful error handling for corrupted files
- Input sanitization
  - Topic validation
  - Filename sanitization
  - Content encoding checks
- Audit logging
  - Logs all validation operations
  - Records fixes applied
  - Timestamps all events

**Performance**:

Time Complexity:
- validate_command_exports(): O(m) where m = number of command files
- validate_project_features(): O(n) where n = number of code files
- validate_code_examples(): O(n*k) where n = files, k = avg examples per file
- auto_fix_safe_patterns(): O(p) where p = issues to fix

Typical Performance:
- Small project (10 commands, 50 code files): 100-200ms total
- Medium project (50 commands, 500 code files): 500-1000ms total
- Large project (100+ commands): 1-3 seconds total

Scales linearly with codebase size.

**Files Added**:
- plugins/autonomous-dev/lib/comprehensive_doc_validator.py (708 lines)
- tests/unit/lib/test_comprehensive_doc_validator.py (1082 lines)

**Test Coverage**: 44 tests covering:
- Command export validation (8 tests): Missing entries, orphaned files, cross-reference checks
- Feature validation (10 tests): PROJECT.md SCOPE vs code, missing features, extra features
- Code example validation (12 tests): Docstring parsing, signature extraction, mismatch detection
- Count validation (6 tests): Agent/command/skill counts, detection of mismatches
- Auto-fix engine (5 tests): Safe pattern fixing, count updates, entry generation
- Report generation (3 tests): Filtering, property access, sorting

**Dependencies**:
- security_utils.py - Path validation and audit logging
- pathlib, ast, re, dataclasses - Standard library

**Backward Compatibility**: 100% compatible - new optional validator, does not affect existing validation or commands

**Version History**:
- v1.0.0 (2026-01-03) - Initial release for comprehensive documentation validation (Issue #198)


## 94. test_runner.py (396 lines, v1.0.0 - Issue #200)

**Purpose**: Autonomous test execution with structured results for debug-first enforcement.

**Problem**: Test execution during autonomous development requires structured results (pass/fail counts, duration) rather than just exit codes. Developers need quick verification without manual parsing.

**Solution**: test_runner library that executes pytest and returns TestResult dataclass with pass/fail counts, output, and duration.

### Features

- Execute pytest and return structured TestResult
- Run single test file or function
- Verify all tests pass (boolean check)
- Handle pytest not found gracefully
- Handle timeout gracefully
- Handle test failures gracefully
- Parse pytest output for counts and duration

### API Classes

#### TestResult

Structured test execution result with:
- passed: bool - All tests passed (no failures/errors)
- pass_count: int - Number of passing tests
- fail_count: int - Number of failing tests
- error_count: int - Number of errored tests
- output: str - Raw pytest output
- duration_seconds: float - Test execution time

### Functions

#### run_tests()

Execute pytest and return structured results.

Signature: run_tests(test_dir=None, pattern=None, verbose=False, coverage=False, timeout=300) -> TestResult

Parameters:
- test_dir: str - Directory to run tests in (default: current directory)
- pattern: str - Test file pattern to match
- verbose: bool - Use verbose output (-v)
- coverage: bool - Run with coverage
- timeout: int - Timeout in seconds (default: 300)

Returns: TestResult with test execution results

Example:
    from test_runner import run_tests
    result = run_tests()
    if result.passed:
        print(f'All {result.pass_count} tests passed!')

#### run_single_test()

Run a single test file or function.

Signature: run_single_test(test_path: str, timeout: int = 300) -> TestResult

Parameters:
- test_path: str - Path to test file or function
- timeout: int - Timeout in seconds

Returns: TestResult with test execution results

#### verify_all_tests_pass()

Quick boolean check if all tests pass.

Signature: verify_all_tests_pass(test_dir=None, timeout=300) -> bool

Parameters:
- test_dir: str - Directory to run tests in (default: current directory)
- timeout: int - Timeout in seconds

Returns: True if all tests passed, False otherwise

#### TestRunner class

Stateful test runner for repeated test execution.

Constructor: TestRunner(timeout=300, verbose=False)

Methods:
- run(test_dir=None, pattern=None, coverage=False) -> TestResult
- run_single(test_path: str) -> TestResult
- verify(test_dir=None) -> bool

### Error Handling

- pytest not found: Returns TestResult with passed=False, error_count=1
- Timeout: Returns TestResult with passed=False, error_count=1
- KeyboardInterrupt: Returns TestResult with passed=False, error_count=1
- Other errors: Returns TestResult with passed=False, error_count=1

**Performance**: O(1) - Delegates to pytest (scales with test count), Typical 10 test run: 100-500ms

**Dependencies**: subprocess, pathlib, dataclasses, re - Standard library

**Version History**: v1.0.0 (2026-01-03) - Initial release for debug-first enforcement (Issue #200)

---

## 95. code_path_analyzer.py (291 lines, v1.0.0 - Issue #200)

**Purpose**: Discover all code paths matching a pattern for debug-first enforcement and code discovery.

**Problem**: Developers need to find all locations matching a pattern (e.g., debug statements, TODOs, specific patterns). ripgrep/grep require external tools; need pure Python solution for portability.

**Solution**: code_path_analyzer library that searches project for regex patterns and returns CodePath objects with file location, line number, context.

### Features

- Find all locations matching a regex pattern
- Return CodePath objects with file_path, line_number, context, match_text
- Handle empty results gracefully
- Handle invalid patterns gracefully
- Search recursively in project directory
- Filter by file types (e.g., ["*.py", "*.md"])
- Exclude common directories (.git, __pycache__, node_modules, venv, build, dist)
- Support multiline context (N lines before/after match)

### API Classes

#### CodePath

A code path matching a search pattern with:
- file_path: str - Path to file containing match
- line_number: int - Line number of match (1-indexed)
- context: str - Surrounding lines for context
- match_text: str - The matched text

#### CodePathAnalyzer

Stateful code path analyzer for repeated searches.

Constructor: CodePathAnalyzer(project_root: str, exclude_patterns=None)

Methods:
- find(pattern, file_types=None, context_lines=3, case_sensitive=True) -> List[CodePath]

### Functions

#### find_all_code_paths()

Find all code paths matching a pattern.

Signature: find_all_code_paths(pattern, project_root=None, file_types=None, context_lines=3, case_sensitive=True, exclude_patterns=None) -> List[CodePath]

Parameters:
- pattern: str - Regex pattern to search for
- project_root: str - Root directory to search (default: current directory)
- file_types: List[str] - File type patterns like ["*.py", "*.md"] (None = all)
- context_lines: int - Number of lines before/after match to include
- case_sensitive: bool - Case-sensitive search (default: True)
- exclude_patterns: List[str] - Additional directories to exclude (beyond defaults)

Returns: List of CodePath objects for each match

Raises: ValueError if pattern is invalid regex, FileNotFoundError if project_root does not exist

### Default Exclude Patterns

- .git
- __pycache__
- node_modules
- venv
- .venv
- build
- dist
- .pytest_cache
- .mypy_cache

### Performance

- O(n) where n = number of files in project
- Excludes __pycache__, .git, node_modules by default
- Typical small project (100 files): 100-500ms
- Binary files and permission errors handled gracefully

**Dependencies**: pathlib, dataclasses, re - Standard library

**Version History**: v1.0.0 (2026-01-03) - Initial release for debug-first enforcement (Issue #200)

---

## 96. doc_update_risk_classifier.py (168 lines, v1.0.0 - Issue #204)

**Purpose**: Risk classification for documentation updates to support auto-apply workflow in doc-master agent.

**Problem**: Documentation updates should be auto-applied when they're safe (low-risk) but require user approval when they're strategic changes (high-risk). The doc-master agent needs to classify updates and make intelligent decisions about application.

**Solution**: doc_update_risk_classifier library that classifies documentation changes as LOW_RISK (auto-apply) or HIGH_RISK (requires approval).

### Features

- Classify documentation files by risk level
- LOW_RISK files: CHANGELOG.md, README.md, and PROJECT.md metadata
- HIGH_RISK sections: PROJECT.md GOALS, CONSTRAINTS, SCOPE, ARCHITECTURE
- Confidence scoring for classification (0.0 to 1.0)
- Pattern-based metadata detection (timestamps, component counts, compliance dates)
- Conservative defaults (unknown files classified as HIGH_RISK)

### API Classes

#### RiskLevel

Enumeration of risk levels:
- LOW_RISK: "low_risk" - Auto-apply without prompt
- HIGH_RISK: "high_risk" - Requires user approval

#### RiskClassification

Named tuple with classification result:
- risk_level: RiskLevel - Classified risk level
- confidence: float - Confidence score (0.0 to 1.0)
- reason: str - Human-readable reason for classification
- requires_approval: bool - Whether user approval is required

#### DocUpdateRiskClassifier

Stateless risk classifier for documentation updates.

Class attributes:
- LOW_RISK_FILES: Set[str] = {"CHANGELOG.md", "README.md"}
- HIGH_RISK_SECTIONS: Set[str] = {"GOALS", "CONSTRAINTS", "SCOPE", "ARCHITECTURE"}
- LOW_RISK_PATTERNS: List[str] - Regex patterns for metadata detection

Class methods:
- classify(file_path: str, changes: List[str]) -> RiskClassification - Classify a documentation update
- _classify_project_md(changes: List[str]) -> RiskClassification - Specialized PROJECT.md classification

### Functions

#### classify_doc_update()

Convenience function to classify a documentation update.

Signature: classify_doc_update(file_path: str, changes: List[str]) -> RiskClassification

Parameters:
- file_path: str - Path to the documentation file
- changes: List[str] - List of changed lines or content

Returns: RiskClassification with risk level, confidence, and reason

### Classification Rules

1. CHANGELOG.md: Always LOW_RISK (confidence 0.95)
2. README.md: Always LOW_RISK (confidence 0.95)
3. PROJECT.md with GOALS/CONSTRAINTS/SCOPE/ARCHITECTURE headers: HIGH_RISK (confidence 0.9)
4. PROJECT.md with metadata patterns (timestamps, counts): LOW_RISK (confidence 0.7-0.95)
5. PROJECT.md other content: HIGH_RISK conservative default (confidence 0.6)
6. Unknown files: HIGH_RISK conservative default (confidence 0.5)
7. Empty/None inputs: LOW_RISK with low confidence (0.3) for known files

### Metadata Patterns

Patterns matched for LOW_RISK classification in PROJECT.md:
- **Last Updated**: timestamp
- **Last Compliance Check**: timestamp
- **Last Validated**: timestamp
- Component version table rows (Skills, Commands, Agents, Hooks, Settings)

**Performance**: O(n) where n = number of changes (regex pattern matching)

**Dependencies**: enum, typing, pathlib, re - Standard library

**Version History**: v1.0.0 (2026-01-09) - Initial release for doc-master auto-apply (Issue #204)

---

## 97. doc_master_auto_apply.py (249 lines, v1.0.0 - Issue #204)

**Purpose**: Auto-apply documentation updates with intelligent approval workflow for doc-master agent.

**Problem**: The doc-master agent updates documentation but needs different handling for safe vs strategic changes. Interactive prompts for every change disrupt autonomous workflows; batch mode must skip high-risk changes.

**Solution**: doc_master_auto_apply library that applies LOW_RISK updates automatically and prompts for HIGH_RISK updates in interactive mode (or skips in batch mode).

### Features

- Auto-apply LOW_RISK documentation updates without user interaction
- Interactive approval workflow for HIGH_RISK updates
- Batch mode support (skip HIGH_RISK updates automatically)
- Comprehensive error handling and logging
- Applied/skipped update tracking
- Support for both object-based and parameter-based API calls

### API Classes

#### DocUpdate

Data class representing a documentation update:
- file_path: str - Path to the documentation file
- content: str - New content to write
- risk_classification: RiskClassification - Risk classification result

#### DocUpdateResult

Named tuple with update application result:
- applied: bool - Whether update was applied
- required_approval: bool - Whether update required approval
- user_approved: Optional[bool] - User approval decision (interactive mode only)
- message: str - Human-readable status message
- file_path: str - Path to the documentation file
- error: Optional[str] - Error message if application failed

#### DocUpdateApplier

Stateful applier for documentation updates.

Constructor: DocUpdateApplier(batch_mode: bool = False, auto_approve: bool = False)

Parameters:
- batch_mode: If True, skip HIGH_RISK updates instead of prompting
- auto_approve: If True, auto-approve all updates (testing only)

Methods:
- apply(update: DocUpdate) -> DocUpdateResult - Apply a single documentation update
- _write_update(update: DocUpdate) -> DocUpdateResult - Write update to disk
- skipped_updates: List[DocUpdate] - Property for skipped HIGH_RISK updates
- applied_updates: List[DocUpdateResult] - Property for successfully applied updates

### Functions

#### auto_apply_doc_update()

Convenience function to classify and apply a documentation update.

Signature: auto_apply_doc_update(
    update: Optional[DocUpdate] = None,
    file_path: Optional[str] = None,
    content: Optional[str] = None,
    changes: Optional[List[str]] = None,
    batch_mode: bool = False
) -> DocUpdateResult

Supports two call patterns:

1. Object-based: auto_apply_doc_update(update=DocUpdate(...), batch_mode=False)
2. Parameter-based: auto_apply_doc_update(file_path="...", content="...", changes=[...], batch_mode=False)

Parameters:
- update: Pre-built DocUpdate object
- file_path: Path to the documentation file
- content: New content to write
- changes: List of changed lines (for risk classification)
- batch_mode: If True, skip HIGH_RISK updates

Returns: DocUpdateResult with success status and action taken

#### apply_doc_updates_batch()

Apply multiple documentation updates in batch mode.

Signature: apply_doc_updates_batch(updates: List[DocUpdate], batch_mode: bool = True) -> List[DocUpdateResult]

Parameters:
- updates: List of DocUpdate objects to apply
- batch_mode: If True, skip HIGH_RISK updates (default: True)

Returns: List of DocUpdateResult for each update

### Workflow

1. **Classify**: Risk classifier determines risk level and confidence
2. **LOW_RISK**: Write immediately, return success
3. **HIGH_RISK in batch mode**: Log and skip, return skipped status
4. **HIGH_RISK in interactive mode**: Display warning, prompt user, apply if approved
5. **File system**: Create parent directories, write content, handle errors

### Error Handling

- File write failures: Returns DocUpdateResult with error details
- Invalid inputs: Returns error result with message
- Missing file paths: Creates parent directories automatically
- Permission errors: Returns error result

**Performance**: O(n) where n = size of content being written (file I/O dominated)

**Dependencies**: os, json, logging, pathlib, typing, dataclasses, datetime, doc_update_risk_classifier

**Version History**: v1.0.0 (2026-01-09) - Initial release for doc-master auto-apply (Issue #204)

---

## 98. auto_implement_pipeline.py (257 lines, v1.0.0 - Issue #204)

**Purpose**: Integration of project-progress-tracker into /implement pipeline (Step 4.3).

**Problem**: The /implement pipeline completes doc-master updates (Step 4.1) but doesn't update PROJECT.md with completion status, issue references, and timestamps. Users manually update progress tracking.

**Solution**: auto_implement_pipeline library that invokes project-progress-tracker after doc-master to update PROJECT.md automatically.

### Features

- Invoke project-progress-tracker after doc-master (Step 4.3)
- Update stage completion status in PROJECT.md
- Update issue references from GitHub issue number
- Update Last Updated timestamp with issue reference
- Graceful degradation if PROJECT.md not found
- Support for both legacy context dict and direct parameters
- Comprehensive error handling and result tracking

### API Classes

#### ProgressTrackerResult

Named tuple with progress tracker invocation result:
- success: bool - Whether invocation succeeded
- project_md_updated: bool - Whether PROJECT.md was modified
- error: Optional[str] - Error message if invocation failed
- updates_made: List[str] - List of updates applied (e.g., ["Stage status", "Issue #204 reference", "Last Updated timestamp"])

### Functions

#### invoke_progress_tracker()

Invoke project-progress-tracker after doc-master in the pipeline.

Signature: invoke_progress_tracker(
    issue_number: Optional[int] = None,
    stage: Optional[str] = None,
    workflow_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    doc_master_output: Optional[Dict[str, Any]] = None
) -> ProgressTrackerResult

Parameters:
- issue_number: GitHub issue number for reference
- stage: Current pipeline stage (e.g., "implementation_complete")
- workflow_id: Workflow identifier for tracking
- context: Legacy context dict with workflow_id, issue_number, changed_files
- doc_master_output: Output from doc-master step (optional, for context)

Returns: ProgressTrackerResult with success status and updates made

Supports both call patterns:
1. Direct args: invoke_progress_tracker(issue_number=204, stage="implementation_complete")
2. Legacy context: invoke_progress_tracker(context={"issue_number": 204, "stage": "implementation_complete"})

#### execute_step8_parallel_validation()

Execute Step 4.1 (parallel validation) with progress tracker integration.

Signature: execute_step8_parallel_validation(context: Dict[str, Any]) -> Dict[str, Any]

Parameters:
- context: Pipeline context with issue_number, stage, workflow_id

Returns: Dict with validation results including progress_tracker result

### PROJECT.md Updates

#### 1. Stage Status Update

Pattern: **Stage**: <value> or Current stage: <value>

Updates stage field to reflect current pipeline stage:
- alignment_check
- complexity_assessment
- research
- planning
- implementation
- implementation_complete
- parallel_validation
- git_automation
- context_clear

#### 2. Issue Reference Update

Pattern: **Last Updated**: YYYY-MM-DD (optional issue reference)

Adds or updates issue reference on Last Updated line:
- **Last Updated**: 2026-01-09 (Issue #204)

Checks for existing reference to avoid duplicates.

#### 3. Timestamp Update

Updates Last Updated timestamp to current date with optional issue reference:
- Pattern: **Last Updated**: YYYY-MM-DD
- Replacement: **Last Updated**: <today> (Issue #NNN) if issue_number provided

### Helper Functions

#### _find_project_md()

Find PROJECT.md in current project.

Checks locations:
- .claude/PROJECT.md
- PROJECT.md
- $CWD/.claude/PROJECT.md
- $CWD/PROJECT.md

Returns: Optional[Path] - Path to PROJECT.md or None if not found

#### _update_stage_status(content: str, stage: str) -> tuple[str, bool]

Update stage status in PROJECT.md.

Returns: (new_content, was_updated) tuple

#### _update_issue_reference(content: str, issue_number: int) -> tuple[str, bool]

Add or update issue reference in PROJECT.md.

Returns: (new_content, was_updated) tuple

#### _update_timestamp(content: str, issue_number: Optional[int] = None) -> tuple[str, bool]

Update Last Updated timestamp in PROJECT.md.

Returns: (new_content, was_updated) tuple

### Error Handling

- PROJECT.md not found: Returns success=False with error message
- File write failures: Returns success=False with error details
- Regex pattern not found: Gracefully skips update with no error
- Invalid date: Uses current date from datetime.now()

### Pipeline Integration

Step 4.3 of /implement pipeline:
1. doc-master completes (Step 4.1)
2. invoke_progress_tracker() called with issue_number and stage
3. PROJECT.md updated with completion status
4. Results returned to pipeline
5. Pipeline continues to Step 4.4 (auto_git_workflow)

**Performance**: O(n) where n = size of PROJECT.md file (regex pattern matching)

**Dependencies**: logging, typing, pathlib, datetime, re - Standard library

**Version History**: v1.0.0 (2026-01-09) - Initial release for progress tracker integration (Issue #204)

## 99. alignment_gate.py (642 lines, v1.0.0 - Issue #251)

**Purpose**: Strict PROJECT.md alignment validation using GenAI with score-based gating for feature proposals.

**Problem**: When proposing new features, it's unclear if they align with PROJECT.md goals and scope. Features that don't explicitly match SCOPE items are approved anyway, leading to scope creep. No systematic way to validate alignment with constraints.

**Solution**: Alignment gate library that validates features against PROJECT.md using GenAI. Features must:
1. Score >= 7 on alignment (0-10 scale)
2. EXPLICITLY match a SCOPE item (not just "related to")
3. Not violate CONSTRAINTS
4. Pass strict gatekeeper validation (rejects ambiguous features)

### Features

- GenAI-powered strict alignment validation
- Score-based gating (7+ threshold for approval)
- Explicit SCOPE membership requirement (not "related to")
- Constraint violation detection (blocks even high-scoring features)
- Decision tracking to alignment_history.jsonl (JSONL format)
- Meta-validation statistics (approval rate, average score, constraint violations)
- Support for both Anthropic and OpenRouter APIs
- Comprehensive error messages with actionable suggestions
- Audit logging for all validation decisions

### API Classes

#### AlignmentGateResult

Result of strict alignment validation with complete analysis.

**Attributes**:
- `aligned: bool` - Whether feature aligns with PROJECT.md (score >= 7, no constraints)
- `score: int` - Alignment score 0-10 (7+ = pass, <7 = fail)
- `violations: List[str]` - List of SCOPE/GOAL violations
- `reasoning: str` - Detailed reasoning for alignment decision
- `relevant_scope: List[str]` - List of SCOPE items that match
- `suggestions: List[str]` - Suggestions for improving alignment
- `constraint_violations: List[str]` - List of CONSTRAINT violations (blocks approval)
- `confidence: str` - Confidence level (high/medium/low)

**Methods**:
- `to_dict() -> Dict[str, Any]` - Convert to dictionary for JSON serialization

### Functions

#### validate_alignment_strict()

Strict alignment validation using GenAI. This is a STRICT GATEKEEPER that:
- Requires EXPLICIT SCOPE match (not "related to")
- Scores ambiguous features 4-6 (not 7+)
- Blocks constraint violations even if score is high
- Requires score >= 7 to pass

Signature: validate_alignment_strict(
    feature_desc: str,
    project_md_path: Optional[Path] = None
) -> AlignmentGateResult

Parameters:
- `feature_desc: str` - Feature description to validate
- `project_md_path: Optional[Path]` - Path to PROJECT.md (default: .claude/PROJECT.md)

Returns: `AlignmentGateResult` with validation decision

Raises: `AlignmentError` if feature description is empty/invalid or PROJECT.md issues

Example:
```python
from alignment_gate import validate_alignment_strict

result = validate_alignment_strict("Add CLI command for git status")
if result.aligned and result.score >= 7:
    print("Feature approved!")
else:
    print(f"Feature blocked: {result.reasoning}")
    for violation in result.violations:
        print(f"  - {violation}")
```

#### check_scope_membership()

Check if feature EXPLICITLY matches an IN SCOPE item (strict matching).

Signature: check_scope_membership(feature: str, scope_section: str) -> bool

Parameters:
- `feature: str` - Feature description
- `scope_section: str` - SCOPE section content from PROJECT.md

Returns: `True` if explicit match found, `False` otherwise

Logic:
- Extract scope items from PROJECT.md SCOPE section
- Remove common stopwords (the, a, and, for, etc.)
- Normalize plural forms (s suffix)
- Require at least 50% of significant words to match
- For compound terms, require > 1 match to avoid false positives

Example:
```python
from alignment_gate import check_scope_membership

scope = "- CLI commands\n- Git automation\n- Testing framework"
result = check_scope_membership("Add CLI command", scope)
# Returns: True (matches "CLI commands")
```

#### track_alignment_decision()

Track alignment decision to history file (JSONL format).

Signature: track_alignment_decision(result: AlignmentGateResult) -> None

Appends decision record to logs/alignment_history.jsonl with timestamp:
```json
{"aligned": true, "score": 8, "violations": [], ..., "timestamp": "2026-01-19T15:30:00Z"}
```

#### get_alignment_stats()

Get meta-validation statistics from alignment history.

Signature: get_alignment_stats() -> Dict[str, Any]

Returns dict with keys:
- `total_decisions: int` - Total number of alignment decisions
- `approved_count: int` - Number of approved features
- `rejected_count: int` - Number of rejected features
- `approval_rate: float` - Percentage of approved features (0.0-1.0)
- `average_score: float` - Average alignment score
- `constraint_violation_count: int` - Number of decisions with constraint violations

Example:
```python
from alignment_gate import get_alignment_stats

stats = get_alignment_stats()
print(f"Approval rate: {stats['approval_rate']:.1%}")
print(f"Average score: {stats['average_score']:.1f}")
```

### GenAI Integration

#### LLM Client Selection

Automatically selects LLM provider (priority order):
1. Anthropic API (if ANTHROPIC_API_KEY set) - Uses claude-sonnet-4-5-20250929
2. OpenRouter API (if OPENROUTER_API_KEY set) - Uses anthropic/claude-sonnet-4.5

Raises `AlignmentError` if no API key found.

#### Prompt Strategy

STRICT GATEKEEPER prompt that:
- Provides PROJECT.md context (GOALS, SCOPE, CONSTRAINTS, CURRENT_SPRINT)
- Enforces explicit SCOPE membership requirement
- Assigns ambiguous features scores 4-6
- Blocks constraint violations regardless of score
- Defines clear scoring scale:
  - 9-10: Perfect explicit match, no violations
  - 7-8: Good explicit match, minor concerns
  - 4-6: Ambiguous, needs clarification, or tangentially related
  - 1-3: Clearly out of scope, not aligned with GOALS
  - 0: Completely unrelated or harmful

### Scoring Rules

**Perfect Match (9-10)**:
- Explicitly matches SCOPE item
- Aligns with GOALS
- No constraint violations
- Clear, detailed description

**Good Match (7-8)**:
- Good explicit match to SCOPE
- Aligns with GOALS
- No major constraint violations
- Minor concerns addressed

**Ambiguous (4-6)**:
- Vague descriptions ("improve performance")
- One-word descriptions
- Missing context or metrics
- Only tangentially related to SCOPE
- Needs clarification

**Out of Scope (1-3)**:
- Clearly doesn't match SCOPE
- Not aligned with GOALS
- Missing implementation details

**Harmful (0)**:
- Completely unrelated
- Contradicts GOALS
- Major constraint violations

### Decision Tracking

Decisions tracked to `logs/alignment_history.jsonl` (JSONL format):
- One JSON record per line
- ISO 8601 timestamps (UTC)
- Complete decision data: score, violations, reasoning, suggestions
- JSONL format allows easy querying and statistical analysis

### PROJECT.md Integration

**Required Sections**:
- `## GOALS` - Project success criteria and objectives
- `## SCOPE` - In-scope and out-of-scope features
- `## CONSTRAINTS` - Technical, resource, and philosophical limits
- `## CURRENT_SPRINT` - Active focus (optional)

**Validation Errors**:
- Missing PROJECT.md: Raises error with helpful path hints
- Missing GOALS/SCOPE sections: Raises error listing found sections
- Malformed content: Raises error with expected format

### Error Handling

- Empty/invalid feature descriptions: Raises `AlignmentError`
- PROJECT.md not found: Raises `AlignmentError` with path hints
- API key missing: Raises `AlignmentError` with setup instructions
- GenAI response parsing: Raises `AlignmentError` with response snippet
- Malformed JSON response: Raises `AlignmentError` with details

### Performance

- GenAI API call: 1-3 seconds (network dependent)
- SCOPE membership check: O(n) where n = number of SCOPE items
- History statistics: O(m) where m = number of tracked decisions
- Total validation: 1-3 seconds per feature

### Security

- Input sanitization for GenAI prompts (no prompt injection)
- JSON output validation and error handling
- Audit logging for all decisions via security_utils
- File path validation via pathlib (CWE-22 prevention)
- Project root detection with fallback handling

### Integration Points

**Feature Proposal Workflow**:
1. User proposes new feature
2. Feature description validated via validate_alignment_strict()
3. GenAI scores feature against PROJECT.md
4. Decision tracked to alignment_history.jsonl
5. Result shown to user (approved/rejected with reasoning)

**Analysis Tools**:
- Use `get_alignment_stats()` to monitor approval trends
- Query `logs/alignment_history.jsonl` directly for detailed analysis
- Track constraint violations separately from low-score rejections

### Constants

- `ALIGNMENT_SCORE_THRESHOLD = 7` - Score required for approval
- `PROJECT_ROOT` - Dynamically detected from .git or .claude
- `ALIGNMENT_HISTORY_PATH` - logs/alignment_history.jsonl (relative to PROJECT_ROOT)

### Module Exports

```python
__all__ = [
    "AlignmentGateResult",
    "validate_alignment_strict",
    "check_scope_membership",
    "track_alignment_decision",
    "get_alignment_stats",
    "AlignmentError",
    "ALIGNMENT_SCORE_THRESHOLD",
]
```

### Testing

54 unit tests covering:
- Alignment validation with various feature types
- SCOPE membership checking (explicit vs tangential)
- Score calculation and threshold enforcement
- Constraint violation detection
- GenAI response parsing
- History file I/O (JSONL format)
- Statistics calculations
- Error handling and edge cases
- API client selection (Anthropic vs OpenRouter)
- Project root detection

**Test File**: tests/unit/lib/test_alignment_gate.py

---

## reviewer_benchmark.py (541 lines, v1.1.1 - Issue #568)

**Purpose**: Harness effectiveness benchmark for the reviewer agent. Loads labeled datasets of real diffs with ground-truth verdicts, constructs reviewer prompts, parses model verdicts, and computes scoring metrics.

**Problem**: No objective way to measure whether the reviewer agent correctly identifies defective code vs. clean code, or whether its verdicts are consistent across repeated invocations.

**Solution**: A standalone benchmark library that drives the reviewer against labeled diff samples and reports balanced accuracy, false positive rate, false negative rate, inter-trial consistency, and per-difficulty/per-defect-category breakdowns.

**Location**: `plugins/autonomous-dev/lib/reviewer_benchmark.py`

**Key Concepts**:
- Binary classification: BLOCKING/REQUEST_CHANGES = positive (defective), APPROVE = negative (clean)
- Balanced accuracy = (TPR + TNR) / 2 — accounts for class imbalance
- Consistency rate = average fraction of trials matching majority verdict across samples
- PARSE_ERROR results are excluded from accuracy calculations but counted in consistency
- Difficulty stratification: easy/medium/hard tiers with per-tier accuracy breakdowns
- Defect taxonomy: 91-category taxonomy with per-category accuracy breakdowns

**Data Structures**:

```python
@dataclass
class BenchmarkSample:
    sample_id: str
    source_repo: str
    issue_ref: str
    diff_text: str
    expected_verdict: str          # APPROVE | REQUEST_CHANGES | BLOCKING
    expected_categories: List[str]
    category_tags: List[str]
    description: str
    difficulty: str = "medium"     # easy | medium | hard
    commit_sha: str = ""           # git commit SHA for provenance
    defect_category: str = ""      # primary category from taxonomy

@dataclass
class BenchmarkResult:
    sample_id: str
    predicted_verdict: str
    expected_verdict: str
    findings: List[Dict[str, Any]]
    raw_response: str
    trial_index: int

@dataclass
class ScoringReport:
    balanced_accuracy: float
    false_positive_rate: float
    false_negative_rate: float
    per_category: Dict[str, Dict[str, Any]]
    confusion_matrix: Dict[str, int]   # keys: TP, TN, FP, FN
    total_samples: int
    trials_per_sample: int
    consistency_rate: float
    per_difficulty: Dict[str, Dict[str, Any]]      # accuracy by easy/medium/hard
    per_defect_category: Dict[str, Dict[str, Any]] # accuracy by taxonomy category
    timestamp: str
```

**Public API**:
- `load_dataset(path: Path) -> List[BenchmarkSample]` — loads and validates a JSON dataset; raises `FileNotFoundError` or `ValueError` on invalid input
- `build_reviewer_prompt(sample, reviewer_instructions) -> str` — constructs full reviewer prompt from a sample
- `parse_verdict(response: str) -> Tuple[str, List[Dict]]` — extracts verdict and findings; looks for `## Verdict: VERDICT` heading first (case-insensitive), falls back to bare keyword search in last 200 characters (also case-insensitive, returns upper-cased result); returns `"PARSE_ERROR"` when no verdict found
- `score_results(results: List[BenchmarkResult], *, samples: Optional[List[BenchmarkSample]] = None) -> ScoringReport` — computes all metrics; pass `samples` to enable `per_difficulty` and `per_defect_category` breakdowns, and to change `per_category` grouping from `expected_verdict` keys to `category_tags` from the sample metadata (a single result contributes to every tag in its sample's `category_tags` list)
- `store_benchmark_run(store, report: ScoringReport) -> None` — persists report to a `BenchmarkStore` under key `"reviewer-effectiveness"`

**Dataset Format** (`tests/benchmarks/reviewer/dataset.json`):
```json
{
  "samples": [
    {
      "sample_id": "string",
      "source_repo": "string",
      "issue_ref": "#NNN",
      "diff_text": "unified diff...",
      "expected_verdict": "APPROVE|REQUEST_CHANGES|BLOCKING",
      "expected_categories": ["category"],
      "category_tags": ["tag"],
      "description": "Human-readable description",
      "difficulty": "easy|medium|hard",
      "commit_sha": "optional git sha",
      "defect_category": "optional taxonomy category"
    }
  ]
}
```

**CLI Runner**: `scripts/run_reviewer_benchmark.py` — drives the full benchmark loop against an Anthropic model, collects results across trials, and saves the report. Supports `--filter-difficulty` (easy/medium/hard), `--filter-category` (taxonomy category name), and `--validate-dataset` (report stats without API calls).

**Mining Scripts** (Issue #573):
- `scripts/mine_git_samples.py` — scans fix commits and clean commits in a git repository to generate labeled diff sample candidates; uses `tests/benchmarks/reviewer/taxonomy.json` for defect classification
- `scripts/mine_session_logs.py` — parses Claude Code session activity JSONL logs to identify reviewer-related events and potential missed defects for benchmark expansion

**Dataset**: `tests/benchmarks/reviewer/dataset.json` — expanded from 14 to 146 labeled samples (Issue #573)

**Taxonomy**: `tests/benchmarks/reviewer/taxonomy.json` — 91 defect categories used for sample classification and `--filter-category` filtering (Issue #573)

**Testing**: `tests/unit/lib/test_reviewer_benchmark.py`, `tests/unit/scripts/test_mine_git_samples.py`, `tests/unit/scripts/test_mine_session_logs.py`, `tests/genai/test_acceptance_benchmark_expansion.py`

**Version History**:
- v1.1.1 (2026-03-29) - 4 bug fixes: invalid-JSON raises `ValueError` with path context; `--validate-dataset` no longer requires `ANTHROPIC_API_KEY`; bare verdict keyword matching is now case-insensitive; `per_category` groups by `category_tags` (not `expected_verdict`) when `samples` are supplied (Issue #568)
- v1.1.0 (2026-03-28) - Expanded to 146 samples, 91-category taxonomy, difficulty stratification, per-difficulty/per-defect-category scoring, mining scripts (Issue #573)
- v1.0.0 (2026-03-28) - Initial release for harness effectiveness benchmark suite (Issue #567)

**Version History**: v1.0.0 (2026-01-19) - Initial release for strict PROJECT.md alignment validation (Issue #251)

---

## runtime_data_aggregator.py (v1.0.0 - Issue #579)

**Purpose**: Collect, normalize, rank, and persist improvement signals from session logs, benchmark history, CI bypass patterns, GitHub issues, and CIA findings to drive the automated reviewer improvement loop.

**Problem**: Improvement signals exist across 5 disparate sources (session activity logs, benchmark history, CI logs, GitHub issues, CIA findings from `.claude/logs/findings/`). There was no unified way to collect, normalize severity, compute cross-source priority, or persist ranked reports for downstream consumers.

**Solution**: A single `aggregate()` entry point that collects from all sources in parallel, normalizes severity to [0,1], applies type-specific priority weights, ranks signals, caps at top_n, and appends to an append-only JSONL report log.

**Location**: `plugins/autonomous-dev/lib/runtime_data_aggregator.py`

**Security**:
- CWE-532: Secret scrubbing (API keys, tokens, passwords) via `scrub_secrets()`
- CWE-400: Line cap on session log reading (`MAX_LINES = 100_000`)
- CWE-78: All subprocess calls use argument lists (no shell invocation)
- CWE-22: Path validation via `resolve()` within `project_root`

### Data Classes

#### `AggregatedSignal`
A single aggregated improvement signal.

**Attributes**:
- `source: str` - Origin (session, benchmark, ci, github)
- `signal_type: str` - Classification (hook_failure, benchmark_weakness, bypass_detected, tool_failure, agent_crash, github_issue)
- `description: str` - Human-readable description (secrets scrubbed)
- `frequency: int` - How many times observed in the window
- `severity: float` - Normalized severity score (0.0–1.0)
- `raw_data: Dict[str, Any]` - Original data for traceability
- `timestamp: str` - ISO 8601 timestamp of most recent occurrence

#### `SourceHealth`
Health status of a signal source.

**Attributes**:
- `source: str` - Source name
- `status: str` - "ok", "error", or "empty"
- `signal_count: int` - Number of signals collected
- `error_message: str` - Error details when status is "error"

#### `AggregatedReport`
Complete report with ranked signals and per-source health.

**Attributes**:
- `signals: List[AggregatedSignal]` - Ranked signals (highest priority first)
- `source_health: List[SourceHealth]` - Health per source
- `window_start: str` - ISO 8601 start of analysis window
- `window_end: str` - ISO 8601 end of analysis window
- `generated_at: str` - ISO 8601 report generation timestamp
- `top_n: int` - Maximum signals included

### Public API

#### `aggregate()`

Main entry point. Collects from all 5 sources, ranks, and persists.

```python
aggregate(
    project_root: Path,
    *,
    window_days: int = 7,
    top_n: int = 10,
    repo: str = "akaszubski/autonomous-dev",
) -> AggregatedReport
```

**Parameters**:
- `project_root` - Root directory of the project
- `window_days` - Days to look back (default: 7)
- `top_n` - Maximum signals in report (default: 10)
- `repo` - GitHub repository for issue collection

**Returns**: `AggregatedReport` with ranked signals and source health

**Side effect**: Appends report to `.claude/logs/aggregated_reports.jsonl`

#### `collect_session_signals(logs_dir, window_days)`
Reads `.claude/logs/activity/*.jsonl`, extracts tool failures (`success=false`), hook errors, and agent crashes. Groups by `(signal_type, description)` for frequency counting.

#### `collect_benchmark_signals(history_path, window_days)`
Uses `BenchmarkHistory` to load entries, filters by time window, converts per-category accuracy deficits below `BENCHMARK_ACCURACY_THRESHOLD` (0.70) into signals.

#### `collect_ci_signals(logs_dir, patterns_path, window_days)`
Reads session logs and cross-references against `known_bypass_patterns.json` to detect model intent bypasses. Deduplicates by `(pattern_id, date)`.

#### `collect_github_signals(repo)`
Runs `gh issue list --label auto-improvement` via subprocess. Gracefully falls back if `gh` is unavailable or times out (30s).

#### `collect_cia_findings(findings_dir, window_days=90) -> Tuple[List[AggregatedSignal], SourceHealth]`
Reads `.claude/logs/findings/YYYY-MM.jsonl` files within the time window. Groups records by `root_cause_tag`, then clusters within each tag by title-token Jaccard similarity via `issue_triage_analyzer.cluster_within_tag`. Emits one `AggregatedSignal` per sub-cluster with `signal_type=root_cause_tag`, `frequency=cluster_size`, `severity=CIA_FINDING_SEVERITY_MAP[max_severity_label]`. `findings_dir` must be absolute (raises `ValueError` otherwise). Returns `([], SourceHealth(status="empty"))` when the directory does not exist. `CIA_FINDING_SEVERITY_MAP = {"info": 0.33, "warning": 0.66, "error": 1.0}`. (Issue #1200)

#### `compute_priority(signal) -> float`
Priority formula: `SEVERITY_WEIGHTS[signal_type] * severity * log(1 + frequency)`

**Type weights** (higher = more urgent):
- bypass_detected: 1.5
- hook_failure: 1.4
- benchmark_weakness: 1.3
- step_skipping: 1.2
- github_issue: 1.0

### Usage Example

```python
from pathlib import Path
from runtime_data_aggregator import aggregate

report = aggregate(
    Path("/path/to/project"),
    window_days=7,
    top_n=10,
)

for signal in report.signals:
    print(f"[{signal.source}] {signal.signal_type}: {signal.description}")
    print(f"  severity={signal.severity:.2f}, frequency={signal.frequency}")

for health in report.source_health:
    print(f"{health.source}: {health.status} ({health.signal_count} signals)")
```

**Testing**:
- `tests/unit/lib/test_runtime_data_aggregator.py` — unit tests
- `tests/unit/test_acceptance_runtime_data_aggregator.py` — acceptance tests (relocated from `tests/genai/`, Issue #1528/#1526 misfiling fix — file performs static file-inspection only, no LLM call)

## issue_triage_analyzer.py (v1.0.0 - Issue #1099)

**Purpose**: Periodic-aggregation root-cause clustering for the open `auto-improvement` GitHub issue queue. Reads issues via `fetch_open_issues_with_label()`, groups them by bracket tag (primary) and Jaccard token similarity (secondary), ranks clusters by `cluster_size * severity_weight * recency_decay`, and surfaces cross-cluster dependencies via shared file path references. Designed to be idempotent — byte-identical output on unchanged inputs (only time-varying input is `now`, pinned in tests).

**Location**: `plugins/autonomous-dev/lib/issue_triage_analyzer.py`

**Key algorithm**:
- Primary clustering: extract `[TAG]` from each issue title; ungrouped issues land in `UNTAGGED`
- Secondary clustering: union-find within each tag using Jaccard token similarity (threshold: 2 shared tokens after stopword removal); prevents one mega-cluster per common tag
- Rank score: `cluster_size * SEVERITY_WEIGHTS[severity] * exp(-0.693 * age_days / RECENCY_HALF_LIFE_DAYS)`
- Deterministic sort: `rank_score DESC`, then `root_cause_tag ASC`, then `sub_cluster_id ASC`, then `issue_numbers ASC`

### Data Classes

#### `TriageFinding`
A single root-cause cluster of related auto-improvement issues.

**Attributes**:
- `root_cause_tag: str` — Bracket content from the issue title (e.g., `"CI"`). `"UNTAGGED"` if no bracket tag present.
- `sub_cluster_id: int` — 1-indexed sub-cluster ID within `root_cause_tag`
- `issue_numbers: Tuple[int, ...]` — Sorted ASC tuple of GitHub issue numbers in the cluster
- `issue_titles: Tuple[str, ...]` — Parallel to `issue_numbers`
- `cluster_size: int` — `len(issue_numbers)`
- `severity: str` — `"low"`, `"medium"`, or `"high"` (most severe label across all issues)
- `rank_score: float` — Cluster priority score
- `shared_files: Tuple[str, ...]` — Sorted file paths mentioned in 2+ issue bodies
- `dependency_notes: Tuple[str, ...]` — Sorted notes describing cross-cluster dependencies
- `suggested_fix_order: int` — 1-indexed global rank after sorting by `rank_score` DESC

### Public API

#### `run_triage()`

Main entry point.

```python
run_triage(
    repo: str = "akaszubski/autonomous-dev",
    limit: int = 200,
    include_fp_acknowledged: bool = False,
    _now: Optional[datetime] = None,
) -> Tuple[List[TriageFinding], SourceHealth]
```

**Parameters**:
- `repo` — GitHub repository in `owner/repo` format (default: `"akaszubski/autonomous-dev"`)
- `limit` — Maximum number of issues to fetch via `gh` CLI
- `include_fp_acknowledged` — If `False` (default), issues with the `fp-acknowledged` label are filtered out
- `_now` — Override current time (used in tests for deterministic recency decay)

**Returns**: Tuple of (`findings`, `source_health`). `findings` is sorted by `suggested_fix_order` ASC. Empty list on `gh` failure.

#### `format_report()`

Render findings to a human-readable text report.

```python
format_report(findings: List[TriageFinding], source_health: SourceHealth) -> str
```

**Usage**:

```python
from pathlib import Path
import sys
sys.path.insert(0, "plugins/autonomous-dev/lib")
from issue_triage_analyzer import run_triage, format_report

findings, health = run_triage(repo="owner/repo")
print(format_report(findings, health))
```

**Testing**:
- `tests/unit/lib/test_issue_triage_analyzer.py` — 21 unit tests
- `tests/integration/test_triage_command.py` — 10 integration tests
- `tests/structural/test_triage_command_structure.py` — 4 structural tests
- `tests/fixtures/triage/seeded_queue.json` — 11 seeded issues for deterministic integration tests

---

## 176+1. runtime_verification_classifier.py (373 lines, v1.0.0 - Issue #564)

**Purpose**: Classify changed files into runtime verification targets so the reviewer agent can decide which opt-in runtime checks to run after completing static code review.

**GitHub Issue**: #564 — Runtime Verification Classifier

### Public API

```python
from runtime_verification_classifier import classify_runtime_targets

plan = classify_runtime_targets(["src/routes/api.py", "public/index.html"])
print(plan.has_targets)  # True
print(plan.summary)      # "Frontend: 1 target(s), API: 1 target(s)"
```

### Data Classes

- **`FrontendTarget`** — A frontend file verifiable via Playwright or browser. Fields: `file_path`, `framework` (html|react|vue|svelte), `suggested_checks`.
- **`ApiTarget`** — An API route/endpoint verifiable via curl. Fields: `file_path`, `framework` (fastapi|flask|express|generic), `endpoints`, `methods`.
- **`CliTarget`** — A CLI tool or script verifiable via subprocess. Fields: `file_path`, `tool_name`, `suggested_commands`.
- **`RuntimeVerificationPlan`** — Aggregated plan. Fields: `has_targets` (bool), `frontend` (List[FrontendTarget]), `api` (List[ApiTarget]), `cli` (List[CliTarget]), `summary` (str).

### Detection Rules

- **Frontend**: matches `.html`, `.tsx`, `.jsx`, `.vue`, `.svelte` extensions; excludes test files.
- **API**: matches `routes/`, `api/`, `endpoints/`, `views/` path patterns and common server filenames (`app.py`, `main.py`, `server.py`, `server.js`, `server.ts`); guesses framework (fastapi, flask, express) from path; excludes test files.
- **CLI**: matches files with no extension or explicit CLI naming patterns; excludes test files.

### Testing

- `tests/unit/lib/test_runtime_verification_classifier.py` — unit tests
- `tests/unit/test_acceptance_runtime_verification.py` — acceptance tests (relocated from `tests/genai/`, Issue #1528/#1526 misfiling fix — file performs static file-inspection only, no LLM call)

**Version History**: v1.0.0 (2026-03-28) - Initial release for runtime data aggregation (Issue #579, Component 1)

## 176+2. python_write_detector.py (404 lines, v1.1.0 - Issues #589, #698)

**Purpose**: Detect file-write operations in Python code snippets (e.g., `python3 -c` arguments, heredoc bodies) using AST-based extraction with regex fallback. Used by `unified_pre_tool.py` to close the Bash-wrapped write bypass gap — wrapping a `Path.write_text()` call in a Bash command would otherwise evade the infrastructure-file write guard.

**GitHub Issues**: #589 — Python3 Path.write_text() bypass detection hardening; #698 — os.rename/os.replace/Path.rename/Path.replace inline bypass detection

### Public API

```python
from python_write_detector import extract_write_targets, has_suspicious_exec, SUSPICIOUS_EXEC_SENTINEL

# Primary entry point: AST first, regex fallback
targets = extract_write_targets('from pathlib import Path as P; P("hooks/foo.py").write_text("x")')
# => ["hooks/foo.py"]

# Quick check for dynamic eval/exec
is_suspicious = has_suspicious_exec("exec(user_input)")
# => True
```

### Functions

- **`extract_write_targets(code: str) -> List[str]`** — Main entry point. Tries AST parsing first; falls back to regex on `SyntaxError`, `RecursionError`, `MemoryError`, `ValueError`, `TypeError`. Returns list of file paths that would be written to. May include `SUSPICIOUS_EXEC_SENTINEL` if `eval()`/`exec()` with dynamic (non-constant) arguments is detected. Truncates input to `MAX_SNIPPET_LENGTH = 10_000` characters before parsing. Pre-processes literal `\n`/`\t` escape sequences (common in shell `-c` strings) before AST parsing.
- **`extract_write_targets_ast(code: str) -> List[str]`** — AST-only extraction. Raises `SyntaxError` on invalid Python. Detects: `Path(...).write_text/write_bytes` with any import alias; `open(path, 'w'/'a'/'wb'/'ab')`; `shutil.copy/copy2/move/copyfile` destination arguments; `os.rename(src, dst)`/`os.replace(src, dst)` with aliased `os` module and `from os import rename` style; `Path(...).rename(dst)`/`Path(...).replace(dst)` (destination is first argument); `eval()`/`exec()` with non-constant first argument.
- **`extract_write_targets_regex(code: str) -> List[str]`** — Regex fallback. Less accurate but handles syntactically invalid snippets. Same detection categories as AST variant, except `import os as o; o.rename(...)` and `from os import rename` alias tracking require the AST path.
- **`has_suspicious_exec(code: str) -> bool`** — Quick check for `eval()`/`exec()` with dynamic arguments.

### Constants

- **`SUSPICIOUS_EXEC_SENTINEL`** (`"__SUSPICIOUS_EXEC__"`) — Sentinel string appended to results when dynamic `eval()`/`exec()` is detected. Callers check `t != SUSPICIOUS_EXEC_SENTINEL` when iterating targets to separate real paths from this flag.
- **`MAX_SNIPPET_LENGTH`** (`10_000`) — Maximum input length; longer snippets are truncated before parsing to prevent DoS.

### Detection Coverage

| Pattern | AST | Regex |
|---------|-----|-------|
| `Path("f").write_text(...)` | Yes | Yes |
| `from pathlib import Path as P; P("f").write_text(...)` | Yes (alias tracking) | Yes |
| `open("f", "w")` / `open("f", "a")` | Yes | Yes |
| `shutil.copy(src, "dst")` / `copy2` / `move` / `copyfile` | Yes | Yes |
| `import shutil as s; s.copy(src, "dst")` | Yes (alias tracking) | No |
| `os.rename(src, "dst")` / `os.replace(src, "dst")` | Yes | Yes |
| `import os as o; o.rename(src, "dst")` | Yes (alias tracking) | Yes |
| `from os import rename; rename(src, "dst")` | Yes (alias tracking) | No |
| `Path("src").rename("dst")` / `Path("src").replace("dst")` | Yes | Yes |
| `eval(var)` / `exec(var)` | Yes | Yes |
| `exec("literal string")` | Not flagged (safe) | Not flagged |

### Testing

- `tests/unit/lib/test_python_write_detector.py` — unit tests

**Version History**: v1.0.0 (2026-03-29) - Initial release for AST-based Python write detection in Bash bypass hardening (Issue #589); v1.1.0 (2026-04-07) - Added detection of `os.rename`/`os.replace`/`Path.rename`/`Path.replace` inline bypass patterns (Issue #698)

## 176+3. agent_ordering_gate.py (414 lines, v1.5.0 - Issues #625, #629, #632, #669, #697, #838, #957, #1158, #1196)

**Purpose**: Pure-logic gate for pipeline agent ordering decisions. No I/O, no side effects. Receives state as input, returns gate decisions. Used by `unified_pre_tool.py` to enforce agent invocation order at hook level, preventing out-of-order Agent/Task tool calls during pipeline execution.

**GitHub Issues**: #625, #629, #632 — Hook-level enforcement for pipeline agent ordering; #669 — Defense-in-depth for parallel mode: `launched_agents` parameter + `warning` field on `GateResult`; #697 — Mode-aware prerequisite filtering: `pipeline_mode` parameter skips prerequisites for agents not in the current mode's required set; #838 — pytest-gate as virtual prerequisite for STEP 10 agents; reviewer→security-auditor moved to SEQUENTIAL_REQUIRED (always enforced); `MODE_DEPENDENT_PAIRS` emptied; #957 — CIA ordering enforcement: `continuous-improvement-analyst` added to `STEP_ORDER` at step 7.0 and three new `SEQUENTIAL_REQUIRED` pairs enforce CIA-last placement; #1158 — spec-validator registration: `spec-validator` added to `STEP_ORDER` at step 5.7 and three new `SEQUENTIAL_REQUIRED` pairs enforce spec-validator placement between pytest-gate and reviewer (closes audit D4); #1196 — `check_ordering_with_session_fallback` now falls back to the sentinel-resolved session_id when the primary session has no recorded completions, with 3600-second mtime TTL to prevent cross-session bleed (sentinel files older than 1 hour are NOT honored)

### Public API

```python
from agent_ordering_gate import check_ordering_prerequisites, check_minimum_agent_count, check_batch_agent_completeness, GateResult

# Check if prerequisites are met before invoking a target agent (full mode, default)
result = check_ordering_prerequisites("implementer", {"planner"})
# result.passed == True (prerequisites met)

# Fix mode: planner is not part of the pipeline, so its prerequisite is skipped
result = check_ordering_prerequisites("implementer", set(), pipeline_mode="fix")
# result.passed == True (planner prerequisite skipped — not in fix pipeline)

# Parallel mode: pass launched_agents to distinguish "running concurrently" from "skipped"
result = check_ordering_prerequisites(
    "security-auditor", {"implementer"}, validation_mode="parallel",
    launched_agents={"implementer", "reviewer"}
)
# result.passed == True, result.warning set (reviewer launched but not completed)
```

### Functions

- **`check_ordering_prerequisites(target_agent, completed_agents, *, validation_mode="sequential", launched_agents=None, pipeline_mode="full") -> GateResult`** — Check if ordering prerequisites are met for a target agent. In sequential mode, all `SEQUENTIAL_REQUIRED` pairs are enforced. As of Issue #838, `reviewer → security-auditor` is in `SEQUENTIAL_REQUIRED` (always enforced, even in parallel mode). In parallel mode, only the `MODE_DEPENDENT_PAIRS` set is relaxed — currently empty, so there is no effective difference between sequential and parallel mode for core prerequisites. Prerequisites for agents not in the current `pipeline_mode`'s required set are skipped — e.g., in `--fix` mode, the `planner → implementer` prerequisite is skipped because planner is not part of the fix pipeline (Issue #697). `pytest-gate` acts as a virtual prerequisite that must complete before reviewer, security-auditor, and doc-master (Issue #838). When the prerequisite is launched but not yet completed, a `warning` is attached to the result for observability. Unknown agents always pass through.
- **`get_required_agents(mode="full", *, research_skipped=False, plan_critic_skipped=False) -> Set[str]`** — Return the set of required agents for a given pipeline mode ("full", "light", "fix", or "tdd-first"). `plan_critic_skipped=True` excludes plan-critic from the required set (pre-validated plan bypass, Step 5.5a — Issue #878).
- **`check_minimum_agent_count(completed_agents, *, required_agents) -> GateResult`** — Check that all required agents have completed (e.g., before git operations).
- **`check_batch_agent_completeness(completed_agents, issue_number, *, mode="default") -> GateResult`** — Check if all required agents have completed for a batch issue. Supports `"default"` (full pipeline), `"light"`, and `"fix"` modes.

### Dataclasses

- **`GateResult`** — `passed: bool`, `reason: str`, `missing_agents: list[str]`, `warning: Optional[str]` — `warning` is set in parallel mode when a prerequisite has been launched but not yet completed (Issue #669)

### Constants

- **`FULL_PIPELINE_AGENTS`** — Set of agents required for a complete pipeline run (researcher-local, researcher, planner, implementer, pytest-gate, reviewer, security-auditor, doc-master)
- **`LIGHT_PIPELINE_AGENTS`** — Reduced set for `--light` mode (planner, implementer, pytest-gate, doc-master, continuous-improvement-analyst)
- **`FIX_PIPELINE_AGENTS`** — Reduced set for `--fix` mode (implementer, pytest-gate, reviewer, doc-master, continuous-improvement-analyst)
- **`STEP_ORDER`** — Dict mapping agent name to step number (imported from `pipeline_intent_validator` with inline fallback). Includes `continuous-improvement-analyst: 7.0` — CIA is always the last step, after all validation/implementation agents (Issue #957).
- **`SEQUENTIAL_REQUIRED`** — List of `(prerequisite, target)` pairs always enforced in sequential mode; includes `pytest-gate → reviewer`, `pytest-gate → security-auditor`, `pytest-gate → doc-master`, `reviewer → security-auditor` (all always enforced regardless of mode — Issue #838), `implementer → spec-validator`, `pytest-gate → spec-validator`, `spec-validator → reviewer` (spec-validator runs at STEP 8.5 after tests pass and before review — Issue #1158), and `implementer → continuous-improvement-analyst`, `reviewer → continuous-improvement-analyst`, `doc-master → continuous-improvement-analyst` (CIA must run after all validation agents complete — Issue #957). Note: `security-auditor → continuous-improvement-analyst` is intentionally absent because security-auditor is conditional (only in sequential mode with security-sensitive files); requiring it would break `--fix` mode.
- **`MODE_DEPENDENT_PAIRS`** — Empty set. Previously held `reviewer → security-auditor` but that pair was moved into `SEQUENTIAL_REQUIRED` (always enforced) in Issue #838. Kept for backward compatibility.

### Testing

- `tests/unit/lib/test_agent_ordering_gate.py` — unit tests (6 regression tests added in Issue #751 verifying CIA inclusion in FIX_PIPELINE_AGENTS and LIGHT_PIPELINE_AGENTS; 8 regression tests added in Issue #697 via `TestPipelineModeFiltering` class; 14 regression tests added in Issue #669; new tests for Issue #838 pytest-gate ordering and reviewer→security-auditor always-enforced behavior)
- `tests/regression/test_issue_957_cia_ordering.py` — 14 regression tests for CIA ordering enforcement: CIA blocked before implementer/reviewer/doc-master, CIA allowed after all prerequisites complete, fix-mode prerequisites respected, security-auditor exclusion from CIA prerequisites, and pipeline_intent_validator STEP_ORDER/SEQUENTIAL_REQUIRED constants verified (Issue #957)

**Version History**:
- v1.5.0 (2026-06-09) - spec-validator registration: `spec-validator` added to `STEP_ORDER` at step 5.7 (between pytest-gate 5.5 and reviewer 6.0); three new `SEQUENTIAL_REQUIRED` pairs: `implementer → spec-validator`, `pytest-gate → spec-validator`, `spec-validator → reviewer`; mirrors identical change in `pipeline_intent_validator.py` (Issue #1158, closes audit D4)
- v1.4.0 (2026-05-23) - CIA ordering enforcement: `continuous-improvement-analyst` added to `STEP_ORDER` at step 7.0; three new `SEQUENTIAL_REQUIRED` pairs added: `implementer → CIA`, `reviewer → CIA`, `doc-master → CIA`; `security-auditor → CIA` intentionally excluded (conditional agent — skipped in `--fix` mode); mirrors identical change in `pipeline_intent_validator.py` (Issue #957)
- v1.3.0 (2026-04-14) - pytest-gate added as virtual prerequisite for reviewer, security-auditor, and doc-master; `reviewer → security-auditor` moved from `MODE_DEPENDENT_PAIRS` to `SEQUENTIAL_REQUIRED` (always enforced, even in parallel mode); `MODE_DEPENDENT_PAIRS` emptied (kept for backward compat); `STEP_ORDER` updated with `"pytest-gate": 5.5`; `FULL_PIPELINE_AGENTS`, `LIGHT_PIPELINE_AGENTS`, and `FIX_PIPELINE_AGENTS` updated to include `pytest-gate` (Issue #838)
- v1.2.0 (2026-04-07) - Mode-aware prerequisite filtering: `pipeline_mode` parameter skips prerequisites for agents not in the current mode's required set; `_get_pipeline_mode_from_state()` helper in `unified_pre_tool.py` reads mode from pipeline state file (Issue #697)
- v1.1.0 (2026-04-07) - Defense-in-depth: `launched_agents` parameter blocks parallel mode bypass when prerequisite not launched; `GateResult.warning` field for observability; fail-open logging in `unified_pre_tool.py` (Issue #669)
- v1.0.0 (2026-03-30) - Initial release for hook-level pipeline ordering enforcement (Issues #625, #629, #632)

## 176+4. pipeline_completion_state.py (v1.16.0 - Issues #625, #629, #632, #686, #712, #786, #802, #837, #838, #878, #989, #1041, #1045, #1046, #1048, #1081, #1093, #1146, #1169, #1170, #1544)

**Purpose**: Shared state for agent ordering enforcement. Manages a per-session JSON state file that tracks which pipeline agents have completed and which have been launched. Written by `unified_session_tracker.py` (SubagentStop for completions) and `unified_pre_tool.py` (PreToolUse for launches), read by `unified_pre_tool.py` to enforce ordering. All 8 public state-mutating functions (`record_agent_completion`, `record_agent_launch`, `record_prompt_baseline`, `set_validation_mode`, `record_doc_verdict`, `record_research_skipped`, `record_plan_critic_skipped`, `record_plan_critic_passed`) route through the internal `_locked_rmw()` read-modify-write helper, and `_write_state()` itself self-wraps through `_locked_rmw()` when not already inside one — so a caller reaching for the raw write path is serialized whether or not its author knew the convention (Issue #1544).

**State file path**: Two schemes are supported:
- Legacy (default): `/tmp/pipeline_agent_completions_{sha256(session_id)[:8]}.json` — used when `run_id` is not provided; backward-compatible with all existing callers
- Run-id-scoped (optional): `/tmp/pipeline_agent_completions_{run_id}.json` — used when `run_id` keyword argument is provided; enables per-invocation isolation and crash-resume without hash collision (#1041)

Both paths auto-expire after 2 hours (`_gc_stale_states`, mtime-based, unrelated to concurrency — see Issue #1544 note below). Callers that omit `run_id` always get the legacy **path** — but no longer byte-identical **behavior**: since Issue #1045 the legacy session file also carries run identity (see "Run identity inside the legacy session file" below). Writes are atomic: `_atomic_write_state()` stages the new content via `tempfile.mkstemp()` in the same directory, `chmod 0o600` before `os.replace()`, so a concurrent reader always sees either the complete prior file or the complete new one — never a truncated 0-byte file (Issue #1544).

**Run identity inside the legacy session file (Issue #1045)**: the run-id-scoped path above is a *different physical file*, and **zero production call sites pass `run_id=`** — so before #1045 the completeness gate only ever read the session file, which had no notion of which RUN produced a completion. A second `/implement` run inside one session therefore inherited the authority the first run earned: with all five fix-mode agents recorded by run A, run B passed the gate having executed nothing (a confused deputy). `record_run_start()` now stamps `current_run_id` into that same session file at STEP 0, `record_agent_completion()` stamps each completion into a `completion_run_ids` sibling map, and `get_completed_agents()` credits only the current run's completions. The sibling-map shape copies the `completion_times` precedent (#1454) — the completion readers iterate `issue_completions.items()` treating every key as an agent name, so a nested key inside an entry would be mistaken for an agent.

The filter (`_filter_to_current_run`) implements this policy:

| State | Condition | Behaviour |
|---|---|---|
| (a1) | no `current_run_id`, no `completion_run_ids` | permissive, silent — pre-migration file, or any non-`/implement` session (including the `unified_session_tracker` SubagentStop path, which fires for ANY subagent) |
| (a2) | no `current_run_id`, stamps present | **all records excluded, gate refuses**, loud stderr naming `SKIP_AGENT_COMPLETENESS_GATE` as the recovery |
| (b) | `current_run_id` set, record unstamped | excluded |
| (c) | `current_run_id` set, stamp != current | excluded (this is the defect above) |
| (d) | stamp == current | included |

(a2) is unreachable through the public API — a stamp is only ever written while `current_run_id` is set — so it means the run id was **lost**, and crediting those records would credit an unknown run. It never fires on pre-migration files and is recoverable through the documented audited bypasses, so it cannot deadlock.

There is no flag day in either direction: readers deployed first see no `current_run_id` anywhere and land in (a1) — today's behaviour; writers deployed first add an inert extra key. **Residual (characterized, not fixed)**: `_locked_rmw` fails open when `flock` fails (typically NFS), and the resulting unlocked read-modify-write can clobber `current_run_id`, degrading the gate to (a1). Measured across 40 forced interleavings: 27 landed in (a1), 13 in (d), (a2) never. Lost updates cost completeness, never soundness — a foreign run's agent is never credited.

**GitHub Issues**: #625, #629, #632 — Hook-level enforcement for pipeline agent ordering; #686 — Agent launch tracking for parallel-mode defense-in-depth; #838 — pytest-gate virtual agent: `record_pytest_gate_passed()` and `get_pytest_gate_passed()` convenience wrappers; `SKIP_PYTEST_GATE=1` escape hatch; #878 — plan-critic skip recording: `record_plan_critic_skipped()` and `get_plan_critic_skipped()` convenience functions so the completeness gate excludes plan-critic when a pre-validated plan bypasses its invocation; #1041 — optional `run_id` keyword parameter wired through all public functions for per-invocation state isolation; #1045 — `record_run_start()` plus per-completion run stamping, so the completeness gate is scoped to the RUN rather than the SESSION

### Public API

```python
from pipeline_completion_state import (
    record_run_start,
    record_agent_completion, get_completed_agents,
    record_agent_launch, get_launched_agents,
    record_doc_verdict,
    set_validation_mode, get_validation_mode, clear_session,
    ensure_sentinel_heartbeat,
)

# Stamp this run's identity BEFORE any agent runs (implement.md STEP 0, #1045).
# Without it the gate is session-scoped and a second run in the same session
# inherits the first run's completed agents.
record_run_start("abc123", "9f2c1ab4de77c015")  # -> True

# Record that an agent completed (called by unified_session_tracker.py)
record_agent_completion(session_id="abc123", agent_type="planner", issue_number=42, success=True)

# Record that an agent was launched (called by unified_pre_tool.py in PreToolUse)
record_agent_launch(session_id="abc123", agent_type="reviewer", issue_number=42)

# Read completed agents (called by unified_pre_tool.py)
completed = get_completed_agents(session_id="abc123", issue_number=42)
# => {"planner"}

# Read launched agents (used by parallel-mode defense-in-depth guard)
launched = get_launched_agents(session_id="abc123", issue_number=42)
# => {"reviewer"}

# Record doc-master verdict for a batch issue (called by coordinator after parsing doc-master output)
record_doc_verdict(session_id="abc123", issue_number=42, verdict="PASS")
```

### Functions

- **`record_agent_completion(session_id, agent_type, *, issue_number=0, success=True, run_id=None, _single_scope=False) -> None`** — Record that an agent has completed for a given session and issue. By default performs a **tri-scope write**: the completion entry is written under three keys in the `completions` dict — `str(issue_number)` (the primary key, e.g. `"42"`), `"0"` (unscoped/default), and `"unscoped"` (stable alias for readers needing an issue-agnostic view). When `issue_number=0` only `"0"` and `"unscoped"` are written (no separate numeric key). This eliminates the need for callers to invoke the function multiple times with different `issue_number` values and ensures all five aggregating readers find the completion regardless of which scope key they query. Pass `_single_scope=True` to write only to `str(issue_number)` — intended for test isolation only, not production callers. `run_id` selects the run-id-scoped state file when provided (#1041). Called by `unified_session_tracker.py` on SubagentStop. Also called explicitly by the coordinator (implement.md, implement-batch.md) for `doc-master` after parsing its verdict, because SubagentStop does not fire reliably for background agents — without the explicit call, `doc-master` would be absent from the completed agents set even after a successful run (Issue #852). (Issues #852, #1041, #1046)
- **`record_run_start(session_id, run_id, *, issue_number=None, _run_id_for_path=None) -> bool`** — Stamp `state["current_run_id"]` for a session. When `issue_number` is supplied the run additionally claims OWNERSHIP of that issue scope in the `issue_run_starts` sibling map — that is what arms the two batch aggregate gates (see `_filter_to_owning_run` below); `None` (the default, and every non-batch caller) records no ownership and leaves those gates at their pre-change permissive behaviour. Called once per `/implement` invocation at STEP 0, BEFORE any agent runs; every subsequent `record_agent_completion()` for that session is stamped with `run_id`, and `get_completed_agents()` then credits only that run's completions. **Idempotent** — calling twice with the same `run_id` (the `--resume` case) leaves state unchanged and returns `True`, so a resumed run keeps the completions it already earned. `run_id` must match `[a-zA-Z0-9_-]{1,64}` (the same regex `_state_file_path` enforces). **Never raises**: state code must not be able to block the gate, so any failure prints a loud `[pipeline_completion_state] WARNING: failed to record run start` block on stderr and returns `False`. Callers in `implement.md` / `implement-batch.md` treat `False` as fatal and exit 1 — the degraded alternative is silent reversion to the pre-#1045 session-scoped gate. `_run_id_for_path` chooses which *file* to write (defaults to the legacy session-hashed path, the only shape production uses) and is deliberately separate from `run_id`, the value stamped *into* it. (Issue #1045)
- **`get_completed_agents(session_id, *, issue_number=0, run_id=None) -> set[str]`** — Get the set of agents that have completed successfully for a session/issue. Returns empty set on any read error (fail-open). Since Issue #1045 the result is additionally restricted to the current run via `_filter_to_current_run` (policy table above), composed with — never replacing — the existing success (`_completion_is_success`) and gate-countability (`_is_gate_countable_agent`) filters. The `'unknown'`-session merge is filtered by the `'unknown'` file's OWN `current_run_id`, not the primary session's, because the two files are independent. Signature unchanged.
- **`record_agent_launch(session_id, agent_type, *, issue_number=0) -> None`** — Record that an agent has been launched (started) for a given session and issue. Called by `unified_pre_tool.py` in PreToolUse BEFORE the agent runs. Used by the parallel-mode defense-in-depth guard to distinguish "running concurrently" from "skipped entirely". (Issue #686)
- **`get_launched_agents(session_id, *, issue_number=0) -> set[str]`** — Get the set of agents that have been launched for a session/issue. Returns empty set on any read error. (Issue #686)
- **`record_prompt_baseline(agent_type, issue_number, word_count, *, state_dir=None) -> None`** — Record baseline prompt word count for an agent. Persists to `.claude/logs/prompt_baselines.json`. Hook uses `issue_number=0` as a sentinel when seeding from the prompt integrity gate (Issue #723).
- **`get_prompt_baseline(agent_type, *, issue_number=None, state_dir=None) -> Optional[int]`** — Get the baseline word count for an agent (per-issue isolated). When `issue_number` is provided, returns the baseline for THAT exact issue ONLY — if no baseline exists for that issue yet (e.g. first dispatch of a new batch issue), returns `None` so the caller seeds a new baseline from observation. This is the per-issue isolation contract from Issue #764. The silent cross-issue fallback that Issue #867 added was removed in Issue #1082 Phase 1a because it caused guaranteed false-positive shrinkage blocks on every new issue's first dispatch. When `issue_number` is `None`, returns the word count from the lowest-numbered recorded issue (backward-compatible single-issue mode). Returns `None` if no baseline exists at all (fail-open). For explicit cross-issue baseline lookup, use `get_cross_issue_baseline()` instead.
- **`get_cross_issue_baseline(agent_type, *, exclude_issue=None, state_dir=None) -> Optional[int]`** — Get the lowest-issue baseline across all recorded issues for an agent. Returns the word-count baseline from the lowest-numbered issue with a recorded baseline. When `exclude_issue` is provided, that issue is excluded from consideration — useful for comparing against OTHER issues' baselines. This is the explicit cross-issue lookup that was previously a silent fallback inside `get_prompt_baseline` (Issue #867); it was extracted in Issue #1082 Phase 1a to resolve the contradiction with Issue #764's per-issue isolation contract. For batch-mode drift detection, prefer `record_batch_observation()` + `get_cumulative_shrinkage()` (Issue #794).
- **`set_validation_mode(session_id, mode) -> None`** — Set ordering enforcement mode (`"sequential"` or `"parallel"`).
- **`get_validation_mode(session_id) -> str`** — Get ordering enforcement mode (default: `"sequential"`).
- **`clear_session(session_id) -> None`** — Remove the state file for a session (called at pipeline cleanup).
- **`verify_batch_cia_completions(session_id) -> tuple[bool, list[int], list[int]]`** — Verify `continuous-improvement-analyst` completed for all batch issues. Returns `(all_passed, issues_with_cia, issues_missing_cia)`. Skips issue key `"0"` (non-batch). Fails open on any error or missing state. Bypass via `SKIP_BATCH_CIA_GATE=1`. Called by `unified_pre_tool.py` before allowing git commit in batch mode. Since Issue #1045 the per-issue credit is restricted to the run that OWNS the issue scope via `_filter_to_owning_run` — this reader iterates `state["completions"]` directly and never calls `get_completed_agents()`, so the first pass of #1045 left it session-scoped and a batch retry inherited a prior run's CIA. (Issues #712, #1045)
- **`record_doc_verdict(session_id, issue_number, verdict) -> None`** — Record a doc-master verdict string for a specific batch issue. Persists the verdict under `"doc-master-verdict"` in the per-issue completions dict. Valid verdicts: `"PASS"`, `"FAIL"`, `"DOCS-UPDATED"`, `"NO-UPDATE-NEEDED"`, `"DOCS-DRIFT-FOUND"`. Invalid sentinel values (`"MISSING"`, `"SHALLOW"`) cause `verify_batch_doc_master_completions()` to treat the issue as incomplete. Called by the coordinator (implement.md and implement-batch.md) immediately after parsing the doc-master agent's verdict line. (Issue #837)
- **`verify_batch_doc_master_completions(session_id) -> tuple[bool, list[int], list[int]]`** — Verify `doc-master` completed with a valid verdict for all batch issues. Returns `(all_passed, issues_with_doc_master, issues_missing_doc_master)`. An issue is considered incomplete when doc-master never ran OR when it ran but recorded no valid verdict (MISSING/SHALLOW). Backward compatible: issues with doc-master completion but no recorded `"doc-master-verdict"` field (old state) pass through as valid. Skips issue key `"0"` (non-batch). Fails open on any error or missing state. Bypass via `SKIP_BATCH_DOC_MASTER_GATE=1`. Called by `unified_pre_tool.py` before allowing git commit in batch mode. Since Issue #1045 the per-issue doc-master credit is restricted to the run that OWNS the issue scope via `_filter_to_owning_run`. The **verdict** is deliberately still read raw: it is not an agent completion, carries no run stamp, and is only consulted once doc-master itself passed the run filter — filtering it too would convert an invalid `SHALLOW`/`MISSING` verdict into the backward-compatible "no verdict recorded" branch and WEAKEN the gate. (Issues #786, #837, #1045)

**Batch aggregate run scoping — why NOT `current_run_id` (Issue #1045)**: `verify_batch_cia_completions` and `verify_batch_doc_master_completions` are wired straight into the commit-blocking hook, and both read the raw `completions` map. Applying `get_completed_agents`'s `_filter_to_current_run` to them would be wrong: batch mode creates ONE RUN PER ISSUE inside ONE session (`implement-batch.md` generates a fresh `ISSUE_RUN_ID` per issue), so `current_run_id` is overwritten by each issue in turn and holds the LAST issue's id when the batch commits — measured, a clean 3-issue batch loses issues 1 and 2 and the commit is refused. The authority for a per-issue aggregate is instead the run that most recently STARTED work on that issue, recorded by `record_run_start(..., issue_number=N)` into `issue_run_starts` and consumed by `_filter_to_owning_run`. Policy: (o0) no ownership entry → pass through (pre-migration state, and any caller that omits `issue_number` — a stale `implement-batch.md` deployment must degrade, not block); (o1) agent stamped with the owning run → credited; (o2) agent stamped with a superseded run → excluded, with a loud `EXCLUDING issue scope ... SUPERSEDED run` block on stderr so the refusal is not misread as "the agent never ran"; (o3) agent unstamped → excluded. The stamp match itself lives once, in `_agents_stamped_with`, shared with `_filter_to_current_run`.
- **`record_research_skipped(session_id, *, issue_number=0, run_id=None) -> None`** — Record that research was skipped for a given session/issue. Called by the coordinator after STEP 3.5 determines that research agents should be skipped (fully-specified change detection). When recorded, `verify_pipeline_agent_completions()` excludes researcher agents from the required set. `run_id` selects the run-id-scoped state file when provided. (Issues #802, #1045)
- **`get_research_skipped(session_id, *, issue_number=0, run_id=None) -> bool`** — Check whether research was recorded as skipped for a given session/issue. Returns `True` if skipped, `False` otherwise (fail-open on read error). `run_id` selects the run-id-scoped state file when provided. (Issues #802, #1045)
- **`verify_pipeline_agent_completions(session_id, pipeline_mode="full", *, issue_number=0) -> tuple[bool, set[str], set[str]]`** — Verify all required agents completed for a pipeline run. Reads completed agents from state, determines required agents based on `pipeline_mode` and `research_skipped` flag, and returns `(passed, completed_agents, missing_agents)`. Fail-open on any error or missing state. `pipeline_mode` accepts `"full"`, `"light"`, `"fix"`, or `"tdd-first"`. **Validator-artifact cross-check (single-issue runs only, new)**: for `issue_number == 0`, when `reviewer` and/or `security-auditor` are both required and recorded complete, `_missing_validator_artifacts()` additionally requires a non-empty `.claude/logs/activity/validators/<current_run_id>/<agent>.txt` on disk — the file `implement.md` instructs the coordinator to write. A recorded completion with no artifact adds a `<agent>-artifact:<path>(absent-or-empty)` sentinel to `missing`; emptiness is zero bytes only, no threshold. Batch runs are exempt (the artifact directory name is not derivable from `current_run_id` there), as is any indeterminate case (no `current_run_id`, a `current_run_id` failing the run-id regex, no resolvable activity dir, any `OSError`) — all contribute nothing, leaving the verdict byte-identical to pre-change behaviour. Bypass (in order of reliability): (1) `touch /tmp/skip_agent_completeness_gate` as a separate command, then retry — file-based one-shot, works mid-session; (2) `export SKIP_AGENT_COMPLETENESS_GATE=1` BEFORE launching claude (env vars don't propagate mid-session — Issue #779). Both bypasses short-circuit before the artifact cross-check runs. Called by `unified_pre_tool.py` via `_check_pipeline_agent_completions()` before allowing git commit during an active pipeline session. (Issue #802, #1086)
- **`record_pytest_gate_passed(session_id, *, issue_number=0, passed=True) -> None`** — Record pytest gate result as a virtual agent completion using `agent_type="pytest-gate"`. Delegates to `record_agent_completion()` so `get_completed_agents()` automatically includes `"pytest-gate"` when the gate has passed. Called by the coordinator after STEP 8 (quality gate) completes. Bypass via `SKIP_PYTEST_GATE=1`. (Issue #838)
- **`get_pytest_gate_passed(session_id, *, issue_number=0) -> bool`** — Check if pytest gate has been recorded as passed. Returns `True` if `"pytest-gate"` is in completed agents OR `SKIP_PYTEST_GATE=1` is set. Returns `False` if not recorded or recorded as failed. Used by the ordering gate to enforce pytest-gate → reviewer/security-auditor/doc-master prerequisites. (Issue #838)
- **`record_plan_critic_skipped(session_id, *, issue_number=0, run_id=None) -> None`** — Record that plan-critic was skipped for a given session/issue. Called by the coordinator at STEP 5.5a when a pre-validated plan is found in `.claude/plans/` (containing "Verdict: PROCEED"), bypassing plan-critic invocation. When recorded, `verify_pipeline_agent_completions()` excludes plan-critic from the required agent set so the completeness gate does not block the commit. `run_id` selects the run-id-scoped state file when provided. (Issues #878, #1045)
- **`get_plan_critic_skipped(session_id, *, issue_number=0, run_id=None) -> bool`** — Check whether plan-critic was recorded as skipped for a given session/issue. Returns `True` if skipped, `False` otherwise (fail-open on read error). `run_id` selects the run-id-scoped state file when provided. (Issues #878, #1045)
- **`record_tier1_allow(session_id, file_path, lines_added, *, run_id=None) -> None`** — Append a Tier-1 (`fix`) classification event to a per-`(session_id, file_path)` ring buffer stored under the `"tier1_ring_buffers"` key in the existing state file. Soft FIFO cap = 10 (oldest entry evicted when full). Each record contains `timestamp` (UTC ISO-8601) and `lines_added` (int). Reuses existing `fcntl`-locked atomic write. Used by the sliding-window cumulative escalation check in `unified_pre_tool._check_write_pipeline_required` (Issue #1146).
- **`get_recent_tier1_allows(session_id, file_path, *, window_seconds=60, run_id=None) -> list[dict]`** — Return all ring-buffer entries for `(session_id, file_path)` whose `timestamp` falls within the last `window_seconds` seconds. Each entry is a dict with `timestamp` and `lines_added` keys. Returns an empty list on any read error (fail-open). Used to compute cumulative lines-added across the sliding window before deciding tier escalation. (Issue #1146)
- **`clear_tier1_ring_buffer(session_id, file_path, *, run_id=None) -> None`** — Remove the ring-buffer list for `(session_id, file_path)` from the `"tier1_ring_buffers"` key. Called by `_check_write_pipeline_required` immediately after a sliding-window escalation fires, so a single threshold crossing does not keep re-triggering. Fails silently on any error. (Issue #1146)
- **`ensure_sentinel_heartbeat(session_id, state_path=None) -> bool`** — Verify that the pipeline sentinel file (`<repo>/.claude/local/implement_pipeline_state.json` by default via `get_legacy_sentinel_path()`, or the value of `PIPELINE_STATE_FILE`; was `/tmp/implement_pipeline_state.json` before Issue #1206) exists and its `session_id` field matches `session_id`. If the sentinel is missing, corrupt, or owned by a different session (e.g., `clear_stale_state()` in `hook_recovery.py` deleted it because a subprocess ran under a different `CLAUDE_SESSION_ID`), recreates a minimal sentinel `{"session_id": ..., "recovered": True, "recovered_at": "<iso>"}` and emits `[SENTINEL-HEARTBEAT-MISSING] state_path=... recovering_for_session=...` to stderr. Returns `True` when the sentinel was already healthy; returns `False` when the sentinel was absent or mismatched and was recreated. Never raises — all error paths degrade gracefully. Called by `unified_session_tracker.py` after each `record_agent_completion()` call to guard against mid-pipeline sentinel loss. (Issue #989) **Atomicity fix**: the recovery write itself previously used `sentinel.write_text(json.dumps(...))` followed by a separate `os.chmod`, which truncates the file at open time — a process killed mid-write left a 0-byte sentinel, meaning the code that repairs a corrupted sentinel could itself corrupt one. It now delegates to `pipeline_state.atomic_write_json` (temp file in the destination directory, chmod 0o600 before rename, `os.replace`), making the separate `os.chmod` call redundant and removed.

### State File Format

```json
{
  "session_id": "abc123",
  "created_at": "2026-03-30T12:00:00+00:00",
  "validation_mode": "sequential",
  "completions": {
    "42": {"planner": true, "test-master": true, "doc-master": true, "doc-master-verdict": "PASS"},
    "0": {"planner": true, "test-master": true, "doc-master": true},
    "unscoped": {"planner": true, "test-master": true, "doc-master": true}
  },
  "launches": {
    "42": {"reviewer": true, "security-auditor": true}
  },
  "research_skipped": {
    "42": true
  },
  "plan_critic_skipped": {
    "42": true
  },
  "prompt_baselines": {},
  "tier1_ring_buffers": {
    "abc123:plugins/autonomous-dev/lib/foo.py": [
      {"timestamp": "2026-06-08T10:00:00+00:00", "lines_added": 8},
      {"timestamp": "2026-06-08T10:00:15+00:00", "lines_added": 14}
    ]
  }
}
```

### Testing

- `tests/unit/lib/test_pipeline_completion_state.py` — unit tests
- `tests/unit/lib/test_pipeline_completion_state_agent_completeness.py` — 15 unit tests for Issue #802 functions
- `tests/unit/lib/test_pipeline_completion_state_verdict.py` — 13 unit tests for Issue #837 verdict recording and verification functions
- `tests/unit/hooks/test_batch_doc_master_gate.py` — includes 4 new regression tests for differentiated "never ran" vs "no valid verdict" block messages (Issue #837)
- `tests/regression/test_issue_802_agent_completeness_gate.py` — 7 regression tests for the hook-level gate
- `tests/unit/lib/test_pipeline_completion_state_run_id.py` — 33 unit tests for run_id path routing, back-compat, path-traversal rejection, and tri-scope write behavior (Issues #1041, #1045, #1046)
- `tests/spec_validation/test_spec_1045_run_id.py` — 13 spec-validation tests verifying keyword-only parameter contract, path isolation, and zero-caller-modification guarantee (Issue #1045)
- `tests/unit/lib/test_pipeline_completion_state_run_id_stamping.py` — 14 unit tests (12 for the run-scoped gate below, plus 2 for the validator-artifact cross-check's indeterminate scoping): the (d) positive arm, the (c) defect arm (run B inherits nothing from run A), (b) legacy-unstamped exclusion, (a1) permissive-and-silent, the (a2) loud refusal **with (a1) as its negative control**, the `_locked_rmw` fail-open race with a lock-intact positive control, `record_run_start` failure degrading to (a1) without raising, `pytest-gate` stamping, and both SubagentStop-shaped record cases. Every writer uses the PRODUCTION call shape (no `run_id=` kwarg) and every two-run test binds two distinct `uuid4` literals — deliberately kept OUT of `test_pipeline_completion_state_run_id.py`, whose fixtures all pass `run_id=` to the writer, a shape production does not have.
- `tests/regression/test_validator_artifact_receipt_gate.py` — 17 regression tests for `_missing_validator_artifacts()` / the validator-artifact cross-check in `verify_pipeline_agent_completions()`: the determinable-absent refusal (missing file, zero-byte file), the positive control (non-empty artifact present, no sentinel emitted), batch-mode exemption, no-`current_run_id` indeterminacy, a `current_run_id` failing `_RUN_ID_RE` (path-traversal guard), an unresolvable activity directory, and `OSError` fail-open — each proven not to raise into the gate.
- `tests/regression/test_issue_1045_batch_aggregate_run_scope.py` — 10 regression tests for the BATCH AGGREGATE gates, which the first pass of #1045 missed because they read `state["completions"]` directly and never call `get_completed_agents()`. Refusing arm: run B re-targets issue 100, executes nothing, and both `verify_batch_*` functions must now report it missing (before the fix both returned `(True, [100], [])`). Permitting arms, deliberately a DIFFERENT SHAPE from the reproducer so they refuse a naive `current_run_id` filter: a clean 3-issue batch with three sequential per-issue runs must still pass, a retry that actually re-runs its agents must be credited, and a state written without `issue_number` (stale deployment) must stay permissive. Plus the stderr report, the `SHALLOW`-verdict semantics that must survive the filter, and per-scope ownership recording.
- `tests/integration/test_pipeline_run_id_resume.py` — 5 tests: resume through the session file with the same run id inherits completions, a DIFFERENT run id does not (negative control), and a characterization pinning that `get_completed_agents(sid, run_id=X)` returns EMPTY for a production-shaped writer — the pre-existing #1041/#1047 gap (the documented resume read targets a physical file no production writer populates), written down rather than implied.
- `tests/unit/lib/test_pipeline_state_gc.py` — 10 unit tests for `_gc_stale_states` covering stale removal, fresh preservation, lockfile cleanup, permission errors, and result dict structure (Issue #1048)
- `tests/unit/lib/test_pipeline_completion_state_resolve_session_id.py` — 11 unit tests for `resolve_session_id()` 4-step fallback chain: env var, sentinel file (including "unknown" skip-through), activity-log scan, and "unknown" terminal step (Issues #1081, #1093)
- `tests/unit/lib/test_pipeline_completion_state.py::TestSentinelHeartbeat` — 6 regression tests for `ensure_sentinel_heartbeat()`: healthy sentinel returns True, sentinel recreated when missing between steps, sentinel recreated when session_id mismatched, sentinel recreated when corrupt, never raises on any input, healthy sentinel is not overwritten (Issue #989)
- `tests/regression/test_issue_1544_state_write_race.py` — 35 regression tests for the truncate-before-lock write race: concurrent-writer fuzzing that the state file is never observed 0-byte or mid-truncation, `_atomic_write_state` staging-file permissions and cleanup, `_read_state` retry-with-backoff and loud-stderr-on-persistent-failure (not silent `{}` on genuine parse failure), all 8 mutators routing through `_locked_rmw`, self-wrapping re-entrancy guard on direct `_write_state` callers (including the second-`flock`-on-same-lockfile deadlock this introduced and then fixed), `_gc_stale_states` staging-file glob cleanup, and negative controls pinning that the Issue #1413 staleness/mtime-refresh path is unchanged.

**Version History**:
- v1.16.0 (2026-08-30) - Validator-artifact receipt cross-check (no issue filed; found while investigating a 2026-08-29 incident in which a reviewer REQUEST_CHANGES finding that drove a full remediation cycle existed only in narration — the coordinator's `record_agent_completion()` call and its separate `implement.md`-mandated artifact write are two independently-forgettable writes by the same party, so recording the completion is not proof the artifact exists). New private `_missing_validator_artifacts(state_run_id, completed, required, issue_number, activity_dir=None) -> frozenset[str]` requires `reviewer`/`security-auditor`, when both required and recorded complete on a single-issue run (`issue_number == 0`), to also have a non-empty `.claude/logs/activity/validators/<current_run_id>/<agent>.txt` on disk; a missing/zero-byte file adds a `<agent>-artifact:<path>(absent-or-empty)` sentinel to `verify_pipeline_agent_completions()`'s `missing` return value. Emptiness is zero bytes only — a `>=200 bytes AND >=2 lines` threshold tried during development misclassified 6 of 19 genuine artifacts, since the smallest real artifact is a 138-byte single-line APPROVE verdict. Deliberately inert (contributes nothing) for batch mode (the validators directory name is not derivable from `current_run_id` there — `implement-batch.md` binds two different values to that name), no `current_run_id`, a `current_run_id` failing `_RUN_ID_RE` (path-traversal guard, reused from `_state_file_path`), an unresolvable activity directory, or any `OSError` — every one of those leaves the verdict byte-identical to pre-change behaviour. Both `SKIP_AGENT_COMPLETENESS_GATE` and the file-based bypass short-circuit before this check runs. No file under `plugins/autonomous-dev/hooks/` was modified — both existing call sites render the new sentinel through their pre-existing missing-agents message unchanged. 19 new tests: 2 in `tests/unit/lib/test_pipeline_completion_state_run_id_stamping.py`, 17 in new `tests/regression/test_validator_artifact_receipt_gate.py`.
- v1.15.0 (2026-08-30) - Run-scoped completeness gate (Issue #1045 follow-up). The gate keyed completions by SESSION, so a second `/implement` run inside one session inherited the authority the first run earned — reproduced both arms: run A records all five fix-mode agents, run B (same session, zero agents executed) read `passed=True, missing=[]`. Confused-deputy class; it bit a real run in which a spec-validator was stopped mid-run and the gate still read satisfied. Fix: new public `record_run_start(session_id, run_id)` stamps `current_run_id` into the existing session file at STEP 0; new private `_record_completion_run_ids()` stamps each completion into a `completion_run_ids` sibling map (one added line in `record_agent_completion._mutator`, honouring `_single_scope`); new private `_filter_to_current_run()` restricts both comprehension results in `get_completed_agents()` — the primary read and the `'unknown'` merge — to the current run, composed with (never replacing) the existing success and gate-countability filters. No signature changed. Wired at `implement.md` STEP 0 and per-issue in `implement-batch.md` (batch creates one run per issue in one session — the highest-volume generator of the defect). Rejected alternatives: re-keying readers onto `_state_file_path(..., run_id=...)` (~13 unmigrated writers; would block commits in five repos) and carrying the id through the sentinel (`ensure_sentinel_heartbeat` writes only `{session_id, recovered, recovered_at}`, so run identity cannot survive that path). 12 unit tests in `tests/unit/lib/test_pipeline_completion_state_run_id_stamping.py`, 5 in `tests/integration/test_pipeline_run_id_resume.py`.
- v1.15.1 (2026-08-30) - Batch aggregate gates brought under run scoping (Issue #1045, completing v1.15.0). v1.15.0 fixed `get_completed_agents()` but missed `verify_batch_cia_completions()` and `verify_batch_doc_master_completions()`, which read `state["completions"]` directly and never call it — so both kept the pre-fix session-scoped shape while wired straight into the commit-blocking hook. A batch retry of one issue in the same session passed the final batch commit gate on the prior run's CIA / doc-master credit, with no stderr and no test coverage. The audit that missed them enumerated *readers of `get_completed_agents`*, not *readers of the raw map*; the complete enumeration is now mechanical (AST walk over `.get("completions")` / `["completions"]`), 8 sites. Fix: `record_run_start()` gains an optional `issue_number=` recording per-issue run OWNERSHIP in a new `issue_run_starts` sibling map; new private `_filter_to_owning_run()` scopes each issue's credit to its owning run; new private `_agents_stamped_with()` holds the stamp match once, shared with `_filter_to_current_run()`; new private `_credited_agents_for_scope()` composes the success and run filters for both verifiers. `current_run_id` is explicitly NOT the authority here — batch creates one run per issue in one session, so filtering to it refuses a clean 3-issue batch (measured). 10 regression tests in `tests/regression/test_issue_1045_batch_aggregate_run_scope.py`.
- v1.14.0 (2026-08-19) - Truncate-before-lock write race (Issue #1544). `_write_state()` previously called `open(path, "w")` — which truncates the file — **before** acquiring `fcntl.LOCK_EX`; a concurrent `_read_state()` landing in that window got `JSONDecodeError` on a 0-byte file, which was silently treated as "no state yet" and rebuilt as a blank skeleton, discarding every recorded completion. Root cause, not the originally-suspected wall-clock TTL (the Issue #1413 staleness path is untouched). Fix: all 8 public mutators (previously only 2 of `_locked_rmw`'s callers) now route through `_locked_rmw()`; `_write_state()` self-wraps through `_locked_rmw()` via a new thread-local re-entrancy guard (`_RMW_GUARD`/`_in_locked_rmw()`) when not already inside one, so future direct callers are serialized by construction; new `_atomic_write_state()` writes via `tempfile.mkstemp()` + `chmod 0o600` + `fsync` + `os.replace()` so a reader never observes a partial file; `_read_state()` no longer equates a parse failure with absence — 3 retries with 10ms backoff, then a loud stderr report naming path/cause/effect, still returning `{}` (fail-open, callers gate reads) rather than raising. New private helpers: `_atomic_write_state`, `_in_locked_rmw`, `_new_state_skeleton`, `_ensure_state_inplace`, `_report_unreadable_state`, `_record_completion_times`. Measured overhead: write path 0.795 ms/call, read path 0.108 ms/call. 35 regression tests in `tests/regression/test_issue_1544_state_write_race.py`.
- v1.16.0 (2026-09-05) - `resolve_session_id()`'s sentinel-read branch previously caught `(OSError, json.JSONDecodeError, ValueError)` and silently returned `data = None`, so an absent sentinel and a corrupt/unparseable one (e.g. the 0-byte truncate shape a killed writer leaves) were indistinguishable in the log — both fell through to the next fallback step with no trace. The except now sits provably inside the `os.stat()`-success branch (the file exists) and emits `[SENTINEL-UNREADABLE] path=... err=<ExceptionType>: <msg>` to stderr before continuing the fallback chain; a merely-absent sentinel still raises from `os.stat()` and is handled by the outer, silent branch, so the two cases are now distinguishable by the presence/absence of this log line. Same change consolidated the five inline `_resolve_session_id()` copies previously duplicated across `implement.md` (STEP 0, Pre-Dispatch, Post-Dispatch) and `implement-batch.md` (per-issue STEP 0, Post-Dispatch) onto this single function — `implement-batch.md`'s copy had drifted furthest: it defaulted to the legacy machine-global `/tmp/implement_pipeline_state.json` literal rather than `get_legacy_sentinel_path()`, a different file from the per-repo sentinel every other call site reads. Callers MUST now pass `sentinel_path=os.environ.get('PIPELINE_STATE_FILE') or None` explicitly — `resolve_session_id()` defaults to `get_legacy_sentinel_path()` and does not itself read `PIPELINE_STATE_FILE`, so omitting the keyword silently drops env honouring.
- v1.13.0 (2026-06-14) - Sentinel heartbeat recovery (Issue #989). New public function `ensure_sentinel_heartbeat(session_id, state_path=None) -> bool` verifies that the pipeline sentinel (`<repo>/.claude/local/implement_pipeline_state.json` resolved by `get_legacy_sentinel_path()`, or `PIPELINE_STATE_FILE`; was `/tmp/implement_pipeline_state.json` before Issue #1206) still exists with the correct `session_id` after each SubagentStop agent completion. When `clear_stale_state()` in `hook_recovery.py` deletes the sentinel because a subprocess ran under a different `CLAUDE_SESSION_ID`, the function recreates a minimal sentinel `{session_id, recovered: True, recovered_at: iso}` and emits `[SENTINEL-HEARTBEAT-MISSING]` to stderr so the deletion is observable. Returns `True` when the sentinel was already healthy, `False` when it was recreated. Never raises. Called by `unified_session_tracker.py` immediately after `record_agent_completion()`. 6 regression tests in `tests/unit/lib/test_pipeline_completion_state.py::TestSentinelHeartbeat`.
- v1.12.0 (2026-06-10) - Security and concurrency hardening bundle (Issues #1169, #1170). `_write_state()` now calls `os.chmod(path, 0o600)` immediately after opening the state file and before taking `fcntl.LOCK_EX`, protecting state-file contents from read by other local users on shared dev machines (CWE-732); chmod failure is non-fatal (logged, write proceeds). New private helper `_locked_rmw(session_id, mutator, *, run_id=None)` wraps the ring-buffer read-modify-write with an external sibling lockfile at `/tmp/pipeline_agent_completions_{key}.lock`, opened in `"a+"` mode to prevent truncation; `fcntl.LOCK_EX` on the lockfile serializes concurrent callers across the full R-M-W sequence, closing the TOCTOU race where two hook processes could read the same state, both mutate, and the last write silently dropped the other's entry. `record_tier1_allow()` and `clear_tier1_ring_buffer()` now call `_locked_rmw` instead of calling `_write_state` directly. 14 regression tests in `tests/regression/test_cluster2_security_bundle.py` covering chmod behavior, lockfile-exclusive RMW, and non-fatal chmod failure path.
- v1.11.0 (2026-06-08) - Sliding-window Tier-1 ring buffer (Issue #1146). Three new public functions: `record_tier1_allow(session_id, file_path, lines_added, *, run_id=None)`, `get_recent_tier1_allows(session_id, file_path, *, window_seconds=60, run_id=None)`, `clear_tier1_ring_buffer(session_id, file_path, *, run_id=None)`. Storage: nested under `"tier1_ring_buffers"` key in the existing state file. Soft FIFO cap = 10. Reuses existing fcntl-locked atomic write. Enables `_check_write_pipeline_required` to escalate cumulative Tier-1 edits to `light` when ≥20 lines accumulate on the same `(session_id, file_path)` within 60 seconds. 7 new tests in `tests/unit/hooks/test_classifier_robustness.py::TestSlidingWindowMultiEdit`.
- v1.10.0 (2026-05-10) - `resolve_session_id()` extended from a 3-step to a **4-step** fallback chain: `env → sentinel → activity-log → "unknown"`. Two new private helpers: `_find_activity_log_dir(start_dir)` discovers `.claude/logs/activity/` by walking up from the CWD (mirrors the pattern in `session_activity_logger.py`); `_resolve_session_id_from_activity_log()` scans today's JSONL for the most recent entry with a real session id. The sentinel step now skips through when the sentinel's `session_id` field is the literal `"unknown"` (a boot-time placeholder written before the real id is available), falling through to the activity-log scan. Root cause: Bash subprocess contexts at boot write `"unknown"` as their sentinel before `CLAUDE_SESSION_ID` is exported, causing all 3 prior steps to return `"unknown"` and triggering a manual `record_agent_completion()` workaround. Post-fix, `resolve_session_id()` returns the real UUID from the activity log (`0df986e1-81ba-4caa-a524-dfa559f5d2bb` in the original report). 5 new tests in `tests/unit/lib/test_pipeline_completion_state_resolve_session_id.py` (11 total). (Issues #1081, #1093)
- v1.9.0 (2026-05-04) - New private helper `_gc_stale_states(max_age_seconds=7200)` garbage-collects stale `/tmp` artifacts on pipeline init. Deletes three glob patterns: `pipeline_agent_completions_*.json` (both legacy sha256 and run_id paths), `implement_pipeline_*.json` (per-run sentinel files), and `pipeline_*.lock` (orphaned lockfiles). Default TTL is 7200 seconds (2× `STALE_UNKNOWN_TTL_SECONDS`). Returns a dict with keys `state_files_removed`, `sentinels_removed`, `lockfiles_removed`, and `errors` (list of per-path OSError strings). Called from `commands/implement.md` STEP 0 immediately before `RUN_ID` generation. All 10 heredoc sites and 4 `rm -f` cleanup commands across `implement.md`, `implement-batch.md`, and `implement-fix.md` migrated from the bare `/tmp/implement_pipeline_state.json` literal to the env-var-aware form `${PIPELINE_STATE_FILE:-/tmp/implement_pipeline_state.json}`, making every sentinel reference honor the `PIPELINE_STATE_FILE` override. Security guards in `unified_pre_tool.py` (line 3209 `_check_bash_state_deletion`) and the HMAC fail-open mtime check in `pipeline_state.py` (`LEGACY_SENTINEL_PATH`) were explicitly NOT migrated — their hardcoded paths are intentional and pinned by regression tests. 26 new tests: 10 unit tests in `test_pipeline_state_gc.py`, 16 integration tests in `test_implement_heredoc_honors_env.py`. (Issue #1048)
- v1.8.0 (2026-05-04) - `record_agent_completion()` now performs a **tri-scope write** by default: completion entries are written to `str(issue_number)`, `"0"`, and `"unscoped"` keys simultaneously, eliminating the need for callers to invoke the function multiple times with different `issue_number` values. When `issue_number=0`, only `"0"` and `"unscoped"` are written. New `_single_scope=True` opt-out parameter restricts writes to `str(issue_number)` only — intended for test isolation. Reader audit confirmed all 5 aggregating readers are safe: `"unscoped"` is filtered by `int()` exception handlers at all aggregating sites. 18 new tests in `test_pipeline_completion_state_run_id.py`. (Issue #1046)
- v1.7.0 (2026-05-04) - Optional `run_id: Optional[str] = None` keyword-only parameter wired through all 9 public functions (including `get_research_skipped` and `get_plan_critic_skipped`) and private helpers (`_state_file_path`, `_read_state`, `_write_state`, `_ensure_state`). When provided, the state file path is `/tmp/pipeline_agent_completions_{run_id}.json`; when omitted, the legacy sha256(session_id)[:8] path is used with byte-identical behavior. Path-traversal validation added via `_RUN_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")` — `ValueError` is raised when `run_id` contains invalid characters, path-traversal sequences, or exceeds 64 characters; empty string falls through to the legacy path (Security Finding 1 — CWE-22/A03). Zero existing callers modified. 28 new tests: 15 unit tests (7 traversal-rejection) + 13 spec-validation. (Issues #1041, #1045)
- v1.6.0 (2026-04-15) - `implement.md` and `implement-batch.md` coordinators now call `record_agent_completion(session_id, 'doc-master', ...)` explicitly alongside `record_doc_verdict()`, closing the gap where SubagentStop fails to fire for background agents — `doc-master` was absent from the completed agents set in 11 of 14 invocations despite completing successfully (Issue #852). 4 regression tests in `tests/regression/test_issue_852_doc_verdict_completion.py`.
- v1.5.0 (2026-04-14) - Added `record_pytest_gate_passed()` and `get_pytest_gate_passed()` convenience wrappers; pytest-gate stored as a virtual agent completion (`agent_type="pytest-gate"`) so all existing ordering and completeness machinery automatically treats it as a completed agent; `SKIP_PYTEST_GATE=1` escape hatch bypasses the gate entirely; `unified_pre_tool.py` injects `"pytest-gate"` into completed set when env var is set before running the ordering check (Issue #838)
- v1.4.0 (2026-04-14) - Added `record_doc_verdict()` and `_VALID_DOC_VERDICTS`; enhanced `verify_batch_doc_master_completions()` to check verdict presence (not just completion) — issues where doc-master ran but produced no valid verdict are now treated as incomplete; `unified_pre_tool.py` differentiates "doc-master never ran" vs "ran but no valid verdict" in block messages (Issue #837)
- v1.3.0 (2026-04-13) - Added `record_research_skipped()`, `get_research_skipped()`, and `verify_pipeline_agent_completions()` for hook-level agent completeness gate; `unified_pre_tool.py` blocks git commit when required pipeline agents haven't completed; `research_skipped` state key added; bypass via `SKIP_AGENT_COMPLETENESS_GATE=1` (Issue #802)
- v1.2.0 (2026-04-12) - Added `verify_batch_doc_master_completions()` batch commit gate mirroring `verify_batch_cia_completions()`; `unified_pre_tool.py` blocks git commit in batch worktrees when doc-master has not run for all issues (Issue #786)
- v1.1.0 (2026-04-07) - Added `record_agent_launch()` and `get_launched_agents()` for parallel-mode defense-in-depth; `unified_pre_tool.py` now passes `launched_agents` to ordering gate (Issue #686)
- v1.0.0 (2026-03-30) - Initial release for pipeline ordering state management (Issues #625, #629, #632)

---

## 176+5. tier_registry.py (226 lines, v1.0.0 - Issue #677)

**Purpose**: Single source of truth for Diamond Model test tier classification. Maps test directories to tier IDs (T0–T3), lifecycle policies, pytest markers, and max duration constraints. Replaces the hardcoded `DIRECTORY_MARKERS` dict that previously lived in `tests/conftest.py`.

**GitHub Issue**: #677 — Test tiering classification — Diamond Model layer metadata

### Public API

```python
from tier_registry import get_tier_for_path, get_all_tiers, get_tier_distribution, is_prunable, build_directory_markers

# Match a test path to its tier
tier = get_tier_for_path("tests/unit/lib/test_foo.py")
# => TierInfo(tier_id="T3", name="Unit", lifecycle="ephemeral", markers=["unit"], max_duration="1s")

# Check pruning eligibility
is_prunable("tests/unit/lib/test_foo.py")  # => True (ephemeral)
is_prunable("tests/genai/test_congruence.py")  # => False (permanent)

# Count tiers across a set of paths
distribution = get_tier_distribution(["tests/unit/...", "tests/genai/..."])
# => {"T3": 1, "T0": 1}

# Build conftest-compatible marker dict
markers = build_directory_markers()
# => {"unit/": ["unit"], "genai/": ["genai", "acceptance"], ...}
```

### Key Data Structure

`TierInfo` (frozen dataclass): `tier_id` (T0–T3), `name`, `directory_pattern`, `lifecycle` (permanent|stable|semi-stable|ephemeral), `markers` (list), `max_duration` (optional string).

`TIER_REGISTRY` (list of TierInfo): Ordered most-specific to least-specific for pattern matching. First match wins.

### Tier Definitions

| Tier | Lifecycle | Directories |
|------|-----------|-------------|
| T0 | permanent | `tests/genai/`, `tests/regression/smoke/` |
| T1 | stable | `tests/e2e/`, `tests/integration/` |
| T2 | semi-stable | `tests/regression/regression/`, `tests/regression/extended/`, `tests/property/` |
| T3 | ephemeral | `tests/regression/progression/`, `tests/unit/`, `tests/hooks/`, `tests/security/` |

### Functions

- **`get_tier_for_path(test_path: str) -> Optional[TierInfo]`** — Match a test file path against the registry. Normalizes path separators. Returns first matching TierInfo or None.
- **`get_all_tiers() -> List[TierInfo]`** — Return all tier definitions sorted by tier_id then name.
- **`get_tier_distribution(test_paths: List[str]) -> Dict[str, int]`** — Count paths per tier_id; unmatched paths counted under `"unknown"`.
- **`is_prunable(test_path: str) -> bool`** — True for ephemeral (T3, always prunable) and semi-stable (T2, prunable after 90d unused). False for T0, T1, or unknown.
- **`build_directory_markers() -> Dict[str, List[str]]`** — Convert registry to conftest.py-compatible `{pattern_suffix: [markers]}` dict.

### Integration

- **`tests/conftest.py`**: Imports `build_directory_markers()` at startup to populate `DIRECTORY_MARKERS`. Falls back to hardcoded dict if import fails (e.g., running outside project).
- **`tests/conftest.py` terminal summary**: Uses `get_tier_for_path()` in `pytest_terminal_summary` hook to print tier distribution after each test run.
- **`step5_quality_gate.py`**: Imports `get_tier_distribution()` to include tier breakdown in the STEP 5 quality gate report.

### Testing

- `tests/unit/lib/test_tier_registry.py` — unit tests for all public functions

**Version History**: v1.0.0 (2026-04-06) - Initial release for Diamond Model tier classification (Issue #677)

---

## 176+6. test_pruning_analyzer.py (v1.0.0 - Issue #674; pruning: Issue #736)

**Purpose**: AST-based test hygiene analyzer that detects orphaned, stale, and redundant tests. Invoked by `/sweep --tests` to produce an informational pruning report. The `prune_tests()` method can delete fully-flagged files when explicitly requested (dry-run by default).

**Problem**: Test suites accumulate dead weight — imports that reference deleted modules, tests for archived code, zero-assertion stubs, and stale regression markers. Manual identification is tedious and error-prone.

**Solution**: `TestPruningAnalyzer` walks all `test_*.py` / `*_test.py` files using Python's `ast` module and runs 5 detectors in sequence, reporting each finding with severity, prunable flag (from `tier_registry`), and a suggested action. The optional `prune_tests()` method deletes files where every test function is flagged by a safe category, with multiple safety guards.

### Detection Categories

| Category | Enum Value | Severity | Description |
|----------|------------|----------|-------------|
| Dead Imports | `DEAD_IMPORT` | HIGH | Import from a module not found in source |
| Archived References | `ARCHIVED_REF` | MEDIUM | Import referencing an `archived/` path |
| Zero-Assertion Tests | `ZERO_ASSERTION` | HIGH/MEDIUM | Test function with no meaningful assertions |
| Duplicate Coverage | `DUPLICATE_COVERAGE` | LOW | Test whose entire set of non-framework call signatures is a strict subset of another test's signatures (per-test subset granularity, not per-call matching; test framework utilities such as `Mock`, `patch`, `assert_called_*` are excluded from signatures) |
| Stale Regressions | `STALE_REGRESSION` | LOW | Test name matches `TestIssueNNN` / `test_issue_NNN` pattern |

### Public API

```python
from test_pruning_analyzer import (
    TestPruningAnalyzer, PruningReport, PruningFinding, PruneResult,
    find_vacuous_tests, VacuousTestFinding,
)
from pathlib import Path

analyzer = TestPruningAnalyzer(Path("."))
report = analyzer.analyze()
print(report.format_table())

# Pruning (dry run by default — no files deleted):
result = analyzer.prune_tests()
# Actually delete:
result = analyzer.prune_tests(dry_run=False)

# Vacuous-test detection (module-level, source-string input, no file I/O):
findings = find_vacuous_tests(source_text, filename="test_example.py")
```

**`TestPruningAnalyzer(project_root: Path)`**
- `analyze() -> PruningReport` — runs all detectors and returns consolidated report
- `prune_tests(*, dry_run=True, categories=None, exclude_dirs=None) -> PruneResult` — delete fully-flagged test files with safety guards; safe categories only by default (`dead_import`, `archived_ref`, `zero_assertion`); security tests excluded (`tests/security/`); whole-file-only deletion (all test functions must be flagged); respects tier protection (T0/T1 never deleted)

**`PruningReport`**
- `findings: List[PruningFinding]` — all findings across scanned files
- `scan_duration_ms: float` — total scan time
- `files_scanned: int` — number of test files analyzed
- `format_table() -> str` — renders findings as a markdown table sorted by severity

**`PruningFinding`**
- `file_path: str`, `line: int`, `category: PruningCategory`, `severity: Severity`
- `description: str`, `suggestion: str`, `prunable: bool`

**`PruneResult`**
- `deleted_files: List[Path]` — files deleted (or would-be deleted in dry run)
- `skipped_files: List[Tuple[Path, str]]` — files skipped with reason (excluded dir, partial flag, tier protection)
- `dry_run: bool` — whether this was a dry run
- `error_messages: List[str]` — errors from failed deletions

**`find_vacuous_tests(source: str, filename: str = "<string>") -> List[VacuousTestFinding]`**
- Module-level function, separate from `TestPruningAnalyzer.analyze()`. Flags `test_*` functions whose only assertions are constant placeholders (`assert True`, `assert None`, `assert 1`) — narrower than `ZERO_ASSERTION` (which catches pass-only bodies), and reuses the same `_has_only_placeholder_asserts` rule rather than duplicating it. Takes source text directly (no disk I/O); an unparseable source returns `[]`. Pinned by a shrink-only ratchet (`tests/unit/lib/test_vacuous_test_ratchet.py`) that lives in `tests/` and is not part of the shipped detector (`install_manifest.json` carries no `tests/` paths).

**`VacuousTestFinding`** (frozen dataclass)
- `name: str`, `line: int`, `reason: str`

### Prunable Flag

`prunable` is determined by `tier_registry.is_prunable(path)`. T2/T3 tier test files are prunable; T0/T1 are not. This prevents accidentally flagging smoke tests and critical regression tests as safe to delete.

### Integration

- Used by `plugins/autonomous-dev/commands/sweep.md` (`/sweep --tests` and `/sweep --tests --prune` modes)
- Depends on `tier_registry.get_tier_for_path()` and `tier_registry.is_prunable()`
- Skips `__pycache__`, `.git`, `.worktrees`, `archived`, `node_modules`, `.tox`, `.venv`, `venv` directories

### Testing

- `tests/unit/lib/test_test_pruning_analyzer.py` — unit tests for all 5 detectors and pruning behavior

## 176+7. test_issue_tracer.py (v1.0.0 - Issue #675)

**Purpose**: Map test files to GitHub issues and flag tracing gaps (untested issues, orphaned pairs, untraced test files).

**Problem**: As the codebase grows, it becomes difficult to verify that every GitHub issue has a corresponding test and that tests reference current (not closed) issues.

**Solution**: Static scan of `tests/` for 7 issue-reference patterns, cross-referenced against live GitHub issues via `gh` CLI, producing a structured `TracingReport` with three finding categories.

**Location**: `plugins/autonomous-dev/lib/test_issue_tracer.py`

**Key Features**:
- 7 reference patterns: `TestIssueNNN` class names, `test_issue_NNN` function names, docstring `#NNN`, comment `# Issue: #NNN`, `GH-NNN` shorthand, `@pytest.mark.issue(NNN)`, and keyword phrases (`Regression #NNN`, `Closes #NNN`, `Fixes #NNN`)
- False-positive filtering: excludes hex colors, `# noqa`, `# type: ignore`, `# pragma`, and `#0`–`#2`
- Deduplication: one `IssueReference` per `(file_path, issue_number)` pair
- GitHub cross-reference via `gh issue list --state all --limit 500`; caches results for 300s
- Non-blocking: `check_issue_has_test()` returns `True` on any exception to never block the pipeline
- Three finding categories: `UNTESTED_ISSUE` (open issue, no test ref), `ORPHANED_PAIR` (test refs closed issue), `UNTRACED_TEST` (test file with zero issue refs)
- All findings are severity `info` — advisory only

### Public API

**`TestIssueTracer(project_root: Path)`**
- `scan_test_references() -> List[IssueReference]` — scan `tests/` for all issue references
- `fetch_github_issues(*, cache_ttl_seconds=300) -> Dict[int, dict]` — fetch issues via `gh` CLI with caching
- `analyze() -> TracingReport` — full cross-reference analysis
- `check_issue_has_test(issue_number: int) -> bool` — quick single-issue check

**`TracingReport`**
- `findings: List[TracingFinding]`, `references: List[IssueReference]`
- `scan_duration_ms: float`, `issues_scanned: int`, `tests_scanned: int`
- `format_table() -> str` — renders markdown summary table

**`IssueReference`**
- `file_path: str`, `line: int`, `issue_number: int`, `reference_type: str`

**`TracingFinding`**
- `category: TracingCategory`, `severity: str`, `description: str`
- `issue_number: Optional[int]`, `file_path: Optional[str]`

### Integration

- Used by `plugins/autonomous-dev/commands/audit.md` (`/audit --test-tracing` flag)
- Used by `plugins/autonomous-dev/commands/implement.md` STEP 13 non-blocking warning
- Gracefully degrades when `gh` CLI is unavailable or unauthenticated (returns empty issue dict)

### Testing

- `tests/unit/test_test_issue_tracer.py` — unit tests for scanning, cross-reference, and false-positive filtering

**Version History**: v1.0.0 (2026-04-06) - Initial release for `/sweep --tests` test pruning analysis (Issue #674)

## 176+8. autoresearch_engine.py (v1.0.0 - Issue #654)

**Purpose**: Autonomous experiment loop engine for the `/autoresearch` command. Provides target validation, metric execution, experiment history tracking, and stall detection for the hypothesis-test-measure loop.

**Location**: `plugins/autonomous-dev/lib/autoresearch_engine.py`

**Key Features**:
- Target whitelist enforcement: only `agents/*.md` and `skills/*/SKILL.md` paths are allowed as optimization targets, preventing uncontrolled modifications to arbitrary files
- Metric script execution: runs a Python script and parses `METRIC: <float>` from stdout/stderr; last matching line wins; raises `ValueError` when no line matches
- Experiment history: append-only JSONL log (`.claude/logs/autoresearch/<target-name>.jsonl`) tracking hypothesis, before/after metrics, outcome, and delta per iteration; tolerates corrupt lines on read
- Stall detection: `check_stall()` halts the loop when N consecutive iterations fail to improve the metric (default N=3)
- Git integration: `create_experiment_branch()` creates `autoresearch/<target-name>-<timestamp>` branches; `commit_improvement()` stages and commits improvements; `revert_target()` restores the last committed state on failure
- `dry_run` mode: skips all git operations (no branch, no commits) for safe local experimentation

### Public API

**`ExperimentConfig`** (dataclass)
- `target` (Path): File to optimize
- `metric_script` (Path): Benchmark script that emits `METRIC: <float>`
- `iterations` (int): Max iterations (default 20)
- `min_improvement` (float): Min delta to count as improvement (default 0.01)
- `dry_run` (bool): Skip git operations (default False)
- `experiment_branch` (str): Override branch name (auto-generated if empty)
- `max_stall` (int): Max consecutive failures before halt (default 3)

**Functions**
- `validate_target(target, *, repo_root) -> Tuple[bool, str]` — check target is within repo and matches whitelist
- `validate_metric(metric_script) -> Tuple[bool, str]` — check metric script exists and is a file
- `run_metric(metric_script, *, timeout=300) -> Tuple[float, str]` — execute benchmark script, return (metric_value, raw_output)
- `create_experiment_branch(target_name) -> str` — create and checkout `autoresearch/<name>-<timestamp>` branch
- `revert_target(target) -> None` — `git checkout --` to discard uncommitted changes
- `commit_improvement(target, *, message) -> str` — stage, commit, return SHA
- `check_stall(history, *, max_consecutive=3) -> bool` — True when consecutive failures >= max_consecutive

**`ExperimentHistory`** (class)
- `__init__(path: Path)` — JSONL history file path
- `append(*, hypothesis, metric_before, metric_after, outcome)` — append experiment result
- `load_all() -> List[Dict]` — all valid entries, oldest first; corrupt lines skipped silently
- `load_recent(n=10) -> List[Dict]` — up to N most recent entries, newest first
- `consecutive_failures() -> int` — count of consecutive non-improved outcomes from end
- `summary() -> Dict` — total/improved/reverted/error counts and best/worst deltas

### Integration

- Used exclusively by `plugins/autonomous-dev/commands/autoresearch.md` (`/autoresearch` command)
- Allowed targets: `agents/*.md`, `skills/*/SKILL.md` (whitelist enforced by `validate_target()`)

### Testing

- Tests added as part of Issue #654 implementation

**Version History**: v1.0.0 (2026-04-07) - Initial release for `/autoresearch` autonomous experiment loop (Issue #654)

## 176+9. covers_index.py (v1.0.0 - Issue #713)

**Purpose**: Pre-computed source-path to doc-file mapping for doc-master optimization. Parses `covers:` YAML frontmatter from all `docs/*.md` files once (at index build time) and stores the result as `docs/covers_index.json`, eliminating the per-invocation 23-file scan that previously ran on every doc-master call.

**Location**: `plugins/autonomous-dev/lib/covers_index.py`

**Key Features**:
- Frontmatter extraction: reads YAML between `---` delimiters, returns the `covers:` list as strings; gracefully handles missing frontmatter, YAML parse errors, and encoding errors
- Three matching modes in `get_affected_docs()`: exact match, prefix match (index key ends with `/`), and glob match (index key contains `*`, matched with `fnmatch`)
- Metadata preservation: `save_covers_index()` writes `_generated` (ISO timestamp) and `_doc_count` alongside the index; `load_covers_index()` strips metadata keys (prefix `_`) on read so callers receive a clean dict
- Deterministic output: doc lists within each index key are sorted; index keys are sorted when serialized
- CLI companion: `scripts/build_covers_index.py` regenerates `docs/covers_index.json` and prints a summary line (`N source paths, M doc mappings`)

### Public API

**Functions**:
- `build_covers_index(docs_dir: Path) -> dict[str, list[str]]` — scan all `*.md` files in docs_dir, return source-path → doc-file mapping
- `get_affected_docs(changed_files: list[str], index: dict[str, list[str]]) -> list[str]` — return deduplicated sorted list of doc files affected by the given changed paths
- `save_covers_index(index: dict[str, list[str]], output_path: Path) -> None` — write index + metadata as formatted JSON
- `load_covers_index(index_path: Path) -> dict[str, list[str]]` — load and return index without metadata keys; raises `FileNotFoundError` or `json.JSONDecodeError` on failure

### Integration

- Consumed by `doc-master` agent (`agents/doc-master.md`) to replace the per-invocation bash frontmatter scan
- Pre-built by `scripts/build_covers_index.py`; generated output stored at `docs/covers_index.json`
- Dependency: `pyyaml` (already required by several other lib modules)

### Testing

- `tests/unit/lib/test_covers_index.py` — 24 tests covering build, query (exact/prefix/glob), save/load round-trip, metadata stripping, and error handling

**Version History**: v1.0.0 (2026-04-08) - Initial release for doc-master covers index optimization (Issue #713)

## 176+10. dependabot_tracker.py (v1.0.0 - Issue #767)

**Purpose**: Queries the GitHub Dependabot API and auto-creates deduplicated security tracking issues in the repository. Invoked non-blocking at STEP 13 of `/implement` (after `git push`, before `gh issue close`). Any failure is logged with a `[dependabot-tracker]` prefix and the pipeline continues without interruption.

**Location**: `plugins/autonomous-dev/lib/dependabot_tracker.py`

**Key Features**:
- SSH and HTTPS remote URL parsing via `parse_owner_repo()` using a single regex covering `git@github.com:owner/repo.git` and `https://github.com/owner/repo` formats
- Subprocess wrapper `_gh()` runs `gh` CLI with `shell=False`, parses JSON output, and returns `None` on any error (timeout, missing binary, bad JSON, non-zero exit)
- GHSA ID validation via `_validate_ghsa_id()` — enforces `GHSA-xxxx-xxxx-xxxx` lowercase alphanumeric format before any issue creation
- `get_open_alerts(owner, repo)` — queries `gh api repos/{owner}/{repo}/dependabot/alerts` filtered to `state=open` alerts
- `issue_exists_for_ghsa(owner, repo, ghsa_id)` — searches existing issues for a deduplication HTML comment marker (`<!-- dependabot-ghsa: GHSA-... -->`) to prevent duplicate tracking issues
- `create_individual_issue(owner, repo, alert)` — creates a GitHub issue titled `[Security] Dependabot: {package} {GHSA_ID}` with severity label (`critical` or `high`) and the deduplication marker; only fires for `critical` and `high` severity alerts
- `_maybe_create_medium_batch(owner, repo, medium_alerts)` — creates one batch issue per ISO calendar week for medium severity alerts; deduplicates via `<!-- dependabot-medium-batch: YYYY-WNN -->` marker
- `run_dependabot_tracker(owner, repo)` — non-blocking entry point: fetches alerts, partitions by severity, calls individual and batch creators, returns `{"created": N}` dict

### Public API

**Functions**:
- `parse_owner_repo(remote_url: str) -> Optional[Tuple[str, str]]` — parse GitHub owner and repo from SSH or HTTPS remote URL
- `get_open_alerts(owner: str, repo: str) -> List[Dict]` — fetch open Dependabot vulnerability alerts via `gh` CLI
- `issue_exists_for_ghsa(owner: str, repo: str, ghsa_id: str) -> bool` — check whether a deduplication marker already exists in any open or closed issue
- `create_individual_issue(owner: str, repo: str, alert: Dict) -> bool` — create a labeled tracking issue for a single critical/high alert; returns True on success
- `run_dependabot_tracker(owner: str, repo: str) -> Dict[str, int]` — orchestrate full tracker run, returns `{"created": N}`

### Integration

- Called from `plugins/autonomous-dev/commands/implement.md` STEP 13 after `git push`, in a `try/except` block with `2>/dev/null || true` shell suppression
- Entry point pattern: import `run_dependabot_tracker` and `parse_owner_repo`, obtain remote URL via `git remote get-url origin`, call `parse_owner_repo`, then `run_dependabot_tracker(*parsed)`
- Non-blocking contract: all exceptions are caught; pipeline proceeds regardless of tracker outcome

### Testing

- `tests/unit/lib/test_dependabot_tracker.py` — 34 unit tests across 10 test classes covering URL parsing, GHSA validation, alert fetching, issue deduplication, issue creation, medium batch handling, entry point orchestration, and a security invariant check (shell=False enforcement)
- `tests/unit/lib/test_acceptance_dependabot_tracker.py` — 16 static file inspection acceptance tests verifying all feature deliverables

**Version History**: v1.0.0 (2026-04-11) - Initial release, Dependabot security tracking at STEP 13 (Issue #767)

## 176+11. prompt_quality_rules.py (v1.1.0 - Issue #842, updated Issue #1119)

**Purpose**: Shared anti-pattern detection library for agent and command prompt files. Used as the rule engine by both the static inspection test suite (`tests/unit/test_prompt_quality.py`) and the unified_pre_tool.py Layer 6 write-time gate. Centralizes all anti-pattern definitions so enforcement is consistent between static analysis and runtime blocking.

**Location**: `plugins/autonomous-dev/lib/prompt_quality_rules.py`

**Key Features**:
- `PERSONA_PATTERN` — compiled regex that matches banned expert-qualifier persona openers (`You are an expert`, `You are a senior`, `You are a world-class`, `You are a renowned/leading/top`) while explicitly allowing legitimate role assignments (`You are the **implementer** agent`)
- `CASUAL_REGISTER_PATTERNS` — list of compiled regexes for six casual register phrases that weaken enforcement prompts: `check for`, `look for`, `make sure`, `try to`, `you should`, `feel free`
- `CONSTRAINT_DENSITY_THRESHOLD = 8` — maximum bullet items (lines starting with `- ` or `* `) allowed per `##` section before flagging as oversized
- `EXEMPT_HEADER_TOKENS` — tuple of case-insensitive header substrings whose `##` sections are exempt from bullet-density counting: `FORBIDDEN`, `HARD GATE`, `HARD-GATE`, `REQUIRED`, `MUST NOT`; these sections are load-bearing enforcement text, not prose, so capping their length forces agents into symbol-prefix workarounds (Issue #1119)
- `_is_exempt_section(header)` — returns True if a `## ` section header (with leading `## ` stripped) contains any exempt token via case-insensitive substring match
- `check_persona(content)` — scans for persona pattern matches, returning violation strings with line numbers; legitimate role assignments pass through
- `check_casual_register(content)` — scans for all casual register patterns; each match produces a violation string with line number and the matched phrase
- `check_constraint_density(content, threshold=8)` — parses content into `##`-delimited sections, counts bullet items per section, and flags sections exceeding the threshold; sections whose headers contain any `EXEMPT_HEADER_TOKENS` token are skipped entirely (Issue #1119); the final section is also checked after the loop completes
- `check_all(content)` — orchestrates all three checks and returns a combined violation list; an empty return means the content passes all checks

### Public API

**Functions**:
- `check_persona(content: str) -> List[str]` — detect banned expert-qualifier persona openers; returns violation strings with line numbers
- `check_casual_register(content: str) -> List[str]` — detect casual register phrases that weaken enforcement; returns violation strings with line numbers
- `check_constraint_density(content: str, threshold: int = 8) -> List[str]` — detect oversized constraint sections exceeding the bullet-item threshold; `##` sections whose headers contain `FORBIDDEN`, `HARD GATE`, `HARD-GATE`, `REQUIRED`, or `MUST NOT` (case-insensitive) are exempt (Issue #1119)
- `check_all(content: str) -> List[str]` — run all three checks and return combined violations (empty = pass)

### Integration

- Consumed by `plugins/autonomous-dev/hooks/unified_pre_tool.py` Layer 6 via `importlib.util.spec_from_file_location` dynamic import; invoked on Write/Edit content targeting `agents/*.md` or `commands/*.md` during active pipeline sessions
- Consumed by `tests/unit/test_prompt_quality.py` static inspection tests which scan all existing `plugins/autonomous-dev/agents/*.md` files for violations at test time
- Imported defensively: any `ImportError` or `Exception` during `check_all()` causes the hook to fail-open (no block) rather than halt the pipeline

### Testing

- `tests/unit/test_prompt_quality.py` — 27 tests covering unit-level rule checks (persona detection, casual register, constraint density) and static inspection of all existing agent `.md` files
- `tests/unit/test_prompt_quality_rules.py` — 9 regression tests covering the Issue #1119 exemption: FORBIDDEN/HARD GATE/REQUIRED sections with more than 8 bullets pass the check, non-exempt sections still fail, `_is_exempt_section` header matching, and the diff-aware path via `_section_bullet_counts` correctly omits exempt sections
- `tests/spec_validation/test_spec_issue842_prompt_quality_gate.py` — 30 spec-validation tests covering hook integration, Layer 6 enforcement behavior, and test routing config

## session_mode.py (Issue #998 — Phase D)

**Purpose**: Session-mode artifact writer. Wires the semantic intent classifier to a per-session JSON snapshot at `/tmp/session_mode_<sha256(session_id)[:8]>.json` after each `UserPromptSubmit` when `INTENT_CLASSIFIER_ENABLED=true`. The artifact is consumed by Phase E (separate issue) to gate routing decisions in downstream `PreToolUse` hooks without requiring those hooks to parse the JSONL activity log.

**Location**: `plugins/autonomous-dev/lib/session_mode.py`

**Design rationale** (decision: option (b) — separate per-session file):
- O(1) lookup vs activity-log scan: PreToolUse hooks (hot path) must read the current session mode without walking a daily JSONL file
- Atomic last-writer-wins via `os.replace()` — same-filesystem tempfile ensures atomicity
- Schema isolation from telemetry: telemetry is append-only JSONL; session-mode is overwrite-style "current-state" snapshot
- Artifact TTL: 1 hour (`TTL_SECONDS = 3600`) — readers MUST honor `expires_at` and treat expired artifacts as missing

### Constants

- `SCHEMA_VERSION: int = 1` — bump when fields are added, renamed, or removed; Phase E reader must migrate v1 artifacts
- `TTL_SECONDS: int = 3600` — artifact lifetime; aligns with `pipeline_completion_state.py` stale TTL

### Public API

#### write_session_mode()

Signature: `write_session_mode(session_id: Any, intent_result: Any, prompt: str) -> None`

NEVER raises. Every exception path is swallowed silently. The observe-mode goal is byte-identical hook behavior when the artifact write fails.

**Parameters**:
- `session_id` — raw session id from `CLAUDE_SESSION_ID`; may be None, empty, or `"unknown"`
- `intent_result` — any duck-typed object with `.intent.value`, `.confidence`, `.regex_hit`, `.llm_used`, `.fail_open`, `.requires_security_audit`
- `prompt` — original user prompt text; hashed via SHA-256 (never stored verbatim)

**Artifact schema** (15 fields, all always present):
- `schema_version` (int) — SCHEMA_VERSION at write time
- `session_id` (str) — resolved session id (PID-suffixed for unknown sentinel)
- `intent_class` (str) — one of the 9 IntentClass values or "ambiguous"
- `confidence` (float) — classifier confidence in [0.0, 1.0]
- `regex_hit` (bool) — whether security-keyword regex matched (short-circuits LLM)
- `llm_used` (bool) — whether LLM was invoked
- `fail_open` (bool) — whether any fail-open path was triggered
- `requires_security_audit` (bool) — whether downstream hooks MUST preserve security checks
- `prompt_hash` (str) — `sha256(prompt)[:16]` hex digest for log correlation
- `written_at` (str) — ISO 8601 UTC timestamp
- `expires_at` (int) — Unix epoch seconds; readers treat expired artifacts as missing
- `enforce_mode` (bool) — value of `INTENT_CLASSIFIER_ENFORCE` at write time; Phase E reads this to decide whether to gate or observe
- `clarification_asked` (bool) — whether an AskUserQuestion round-trip was initiated (Issue #1024 M2); always False on initial write
- `clarified_intent` (str or None) — user-supplied intent override after AMBIGUOUS disambiguation; None on initial write
- `user_prompt_text` (str or None) — up to 1000 chars of the raw prompt text (Issue #1263); used by `get_user_msg_token()` to derive a fire-once-per-turn deduplication token for the SWE router. Readers MUST use `data.get("user_prompt_text")` — artifacts written before Issue #1263 lack this field

### Environment Variables

- `INTENT_CLASSIFIER_ENFORCE` (default: `false`) — plumbed in Phase D but unused. Phase E will read the `enforce_mode` field written into the artifact to decide whether to apply enforcement gates in downstream hooks. Setting `true` while Phase E is not deployed has no behavioral effect.

### Integration

Called from `unified_prompt_validator.py` `main()` when `INTENT_CLASSIFIER_ENABLED=true` and a non-None `IntentResult` is produced by the classifier:

```python
if INTENT_CLASSIFIER_ENABLED and intent_result is not None:
    from session_mode import write_session_mode
    write_session_mode(session_id, intent_result, user_prompt)
```

The call is wrapped in a bare `try/except` so any import or write failure is silently swallowed — observe-mode byte-identity is preserved.

### Fail-open contract

`write_session_mode()` MUST NEVER raise. Phase D is observe-mode only: a failed write MUST NOT change downstream behavior. Phase E reader-side fail-open is implemented in `enforcement_decision.py` (Issue #999).

### Testing

- `tests/unit/lib/test_session_mode.py` — unit tests covering artifact write, atomic replace, TTL field, schema fields, PID-suffixed unknown sentinel, non-string session id, and fail-open on OSError
- `tests/unit/lib/test_session_mode_reader.py` — reader-side unit tests: `read_session_mode()` stale/missing/mismatch paths, `should_pipeline_enforce()` decision table (12 tests, Phase E, Issue #999)
- `tests/integration/test_intent_classifier_observe_mode.py` — integration tests verifying byte-identical hook output when flag disabled (observe-mode contract)

#### get_user_msg_token()

Signature: `get_user_msg_token(session_id: Any) -> str | None`

Returns a 16-char hex content-addressed token for fire-once-per-turn deduplication in the Phase 2 SWE router (Issue #1263). Token is derived from the artifact's `user_prompt_text` field via `sha256(user_prompt_text)[:16]`; two consecutive PreToolUse events within the same user turn share the same token so the router fires only once per turn. Forward-compat fallback: if the artifact predates Issue #1263 (no `user_prompt_text` field), falls back to the existing `prompt_hash` field (first 16 hex chars). Returns `None` when the artifact is missing, stale, or malformed. NEVER raises.

**Version History**: v1.0.0 (2026-05-02) — Initial release, Phase D observe-mode wiring (Issue #998); v1.1.0 (2026-05-02) — Added `read_session_mode()` and `should_pipeline_enforce()` reader API, `_SKIP_INTENT_CLASSES` constant (Issue #999); v1.2.0 (2026-06-20) — Added `user_prompt_text` artifact field (≤1000 chars of raw prompt) and `get_user_msg_token()` helper for SWE router deduplication (Issue #1263)

**Version History**: v1.0.0 (2026-04-14) - Initial release, prompt anti-pattern detection shared library (Issue #842)

---

## hook_stdin.py (Issue #999 — Phase E)

**Purpose**: Single-read stdin cache and session_id extractor for Phase E PreToolUse hooks. Hooks that need to read the PreToolUse JSON payload AND extract `session_id` previously risked exhausting the stdin stream on the first read. This module provides a module-level consumed-once cache so multiple callers within the same hook process always receive the same parsed dict without re-reading the stream.

**Location**: `plugins/autonomous-dev/lib/hook_stdin.py`

### Design notes

- NOT `lru_cache` — `sys.stdin.read()` exhausts the stream after the first call; the cache is consumed-once, not key-indexed memoization.
- Module-level `_stdin_data` + `_stdin_consumed` sentinel: distinguishes "read returned None because stdin was empty/malformed" from "read has not been called yet".
- Fail-open: any IO/JSON exception returns `None`. Phase E hooks treat `None` as "no session context — enforce normally".

### Public API

#### read_stdin_once()

Signature: `read_stdin_once() -> dict | None`

Returns the parsed PreToolUse hook input dict on the first call; returns the cached result on subsequent calls. Returns `None` on empty stdin, malformed JSON, non-dict result, or any IO error. NEVER raises.

#### extract_session_id()

Signature: `extract_session_id(data: dict | None) -> str | None`

Extracts `session_id` from a hook input dict. Lookup order:
1. `data["session_id"]` (top-level field on every PreToolUse payload)
2. `CLAUDE_SESSION_ID` env var (set by Claude Code)

Sentinel handling: empty strings and the literal string `"unknown"` return `None`. Matches the convention in `session_mode._resolve_session_id`.

### Testing

- `tests/unit/lib/test_hook_stdin.py` — 10 unit tests covering first read, repeated reads return cached, empty stdin, malformed JSON, non-dict, IOError, session_id extraction from dict, env fallback, "unknown" sentinel, and None data

**Version History**: v1.0.0 (2026-05-02) — Initial release, Phase E stdin cache (Issue #999)

---

## enforcement_decision.py (Issue #999 — Phase E)

**Purpose**: Pure policy layer for Phase E hook gating. Accepts a hook name, optional function name, and optional session_id; consults the hard-floor registry, the enforcement env var, and the session-mode artifact; returns a `(skip: bool, reason: str)` tuple. Zero filesystem or stdin side effects — the wrapping hook decides what to do with the result.

**Location**: `plugins/autonomous-dev/lib/enforcement_decision.py`

### Design notes

Priority order (first match wins):
1. `is_hard_floor(...)` true → `(False, "hard_floor")` — hard floors always fire
2. `INTENT_CLASSIFIER_ENFORCE` not `"true"` → `(False, "enforcement_off")` — default-off rollout knob
3. session_id missing/unknown → `(False, "no_session_id_safety")`
4. artifact missing or stale → `(False, "ambiguous_safety")`
5. `mode["fail_open"]` true → `(False, "classifier_fail_open")`
6. `mode["requires_security_audit"]` true → `(False, "security_audit_required")`
7. `should_pipeline_enforce(intent_class)` true → `(False, f"mode_enforce:{intent_class}")`
8. else → `(True, f"mode_skip:{intent_class}")` — the only True return

The fail-safe direction is "enforce" (return `False`). Rule 8 is the only skip path, requiring a fully-qualified, classifier-confident, non-security intent class.

### Public API

#### should_skip_enforcement()

Signature: `should_skip_enforcement(*, hook_name: str, function_name: str | None = None, session_id: str | None = None) -> tuple[bool, str]`

Returns `(skip, reason)`. `skip == True` means the calling check SHOULD be bypassed. `skip == False` means the gate runs as today. On any internal exception, returns `(False, "exception_safety")`. NEVER raises.

**Parameters**:
- `hook_name` — filename of the calling hook (e.g. `"unified_pre_tool.py"`)
- `function_name` — optional function name within the hook for fine-grained hard-floor matching
- `session_id` — the session id resolved by the calling hook (may be `None`)

**Reason string prefixes** (machine-parseable):
- `"hard_floor"` — hard-floor registry blocked the skip
- `"enforcement_off"` — `INTENT_CLASSIFIER_ENFORCE` not set to `"true"`
- `"no_session_id_safety"` — no usable session id
- `"ambiguous_safety"` — artifact missing or stale
- `"classifier_fail_open"` — classifier itself fell back
- `"security_audit_required"` — session touched a security keyword
- `"mode_enforce:{class}"` — intent class requires enforcement
- `"mode_skip:{class}"` — intent class permits skip (only True return)
- `"exception_safety"` — unexpected internal exception

### Testing

- `tests/unit/lib/test_enforcement_decision.py` — 13 unit tests covering each priority rule, the exception_safety path, and the single True return condition
- `tests/unit/hooks/test_phase_e_integration.py` — 10 hook integration tests verifying `_phase_e_skip()` helper + 5 wrap sites in `unified_pre_tool.py`
- `tests/integration/test_enforcement_mode_cutover.py` — 3 integration tests for end-to-end enforcement vs skip with real artifact fixture

**Version History**: v1.0.0 (2026-05-02) — Initial release, Phase E pure policy layer (Issue #999)

## goa_state.py (v1.0.0 — Issue #1320)

GOA (Governance, Observability, Audit) manifest state management. Manages the GOA manifest at `.claude/local/goa_manifest.json` — a JSON file recording which cron triggers are registered and what conservative-mode thresholds are active. All writes use `pipeline_state.atomic_write_json` for atomicity (temp-file + rename, 0o600 permissions).

### Constants

- `MANIFEST_VERSION = 1` — Schema version for forward-compat detection
- `DEFAULT_THRESHOLDS` — Conservative-mode defaults: drop rate >70% in 12h window, DOWN events >2 in 12h window, frequency gate 3 issues per 24h

### Public API

- `get_manifest_path(project_root=None) -> Path` — Returns `<repo>/.claude/local/goa_manifest.json`
- `read_manifest(project_root=None) -> dict` — Reads manifest; returns empty dict on missing or malformed file (fail-open)
- `write_manifest(data, project_root=None) -> None` — Atomically writes manifest via `atomic_write_json`
- `is_goa_active(project_root=None) -> bool` — Returns True when `status == "active"` in manifest
- `get_thresholds(project_root=None) -> dict` — Returns active thresholds, falling back to `DEFAULT_THRESHOLDS` on missing keys

### Testing

- `tests/unit/test_goa_state.py` — Unit tests covering manifest read/write round-trip, fail-open on corrupt JSON, threshold fallback, and is_goa_active logic

## goa_watcher.py (v1.0.0 — Issue #1320)

GOA watcher — core health-check logic for the `/goa` command. Reads activity logs and healthchecks.io event history to detect anomalies, then files GitHub issues when thresholds are breached. No I/O beyond `gh` CLI subprocess calls and HTTPS via `urllib.request`.

### Module Constants (Conservative-mode defaults)

- `DROP_RATE_PCT_THRESHOLD = 70.0` — Alert when scheduled-vs-fired drop rate exceeds 70%
- `DROP_WINDOW_HOURS = 12` — Rolling window for evaluating cron drop rate
- `DOWN_EVENTS_THRESHOLD = 2` — Alert when healthcheck reports >= 2 down transitions
- `DOWN_WINDOW_HOURS = 12` — Rolling window for evaluating down-event count
- `FREQUENCY_GATE_MAX_PER_24H = 3` — Maximum GOA issues that may be filed in any 24-hour window

### Public API

- `check_drop_rate(project_root=None, *, now=None) -> dict` — Returns `{triggered: bool, rate_pct: float, reason: str}` by comparing scheduled cron fires against actual activity log entries within `DROP_WINDOW_HOURS`
- `check_down_events(hc_url, *, now=None) -> dict` — Returns `{triggered: bool, count: int, reason: str}` by fetching healthchecks.io JSON events and counting DOWN transitions in `DOWN_WINDOW_HOURS`
- `check_frequency_gate(project_root=None, *, now=None) -> dict` — Returns `{gate_open: bool, count: int}` by querying open GitHub issues with `goa` label via `gh issue list`; gate is open when `count < FREQUENCY_GATE_MAX_PER_24H`
- `file_goa_issue(title, body, project_root=None) -> bool` — Creates a GitHub issue with label `goa,auto-improvement` via `gh issue create`; returns True on success

### Design Notes

- Comparator `>=` (not `>`) for DOWN_EVENTS_THRESHOLD — an event count equal to the threshold triggers an alert (AC7 fix in STEP 11 remediation)
- Frequency gate uses `gh issue query` for persistence across sessions (AC9 fix in STEP 11 remediation)

### Testing

- `tests/unit/test_goa_watcher.py` — Unit tests covering drop-rate calculation, down-event counting, frequency gate, and issue filing with mocked `gh` subprocess

## goa_cli.py (v1.0.0 — Issue #1320)

GOA CLI entry point providing the argparse interface for the `/goa` slash command. Subcommands: `start`, `stop`, `status`, and `watch`.

### Public API

- `main(argv=None) -> int` — Entry point; returns exit code (0 = success, 1 = error)

### Subcommands

- `start [--record-trigger-id ID1,ID2,...]` — Activates GOA by writing manifest with `status=active` and optional trigger IDs for `/schedule` integration; emits spec-first `/schedule create` paste lines per AC2
- `stop` — Sets `status=inactive` in manifest; emits confirmation
- `status` — Reads manifest and prints current GOA state, thresholds, and last-run timestamp
- `watch` — Runs a single health-check cycle: checks drop rate and DOWN events; if frequency gate is open and any check triggers, files a GitHub issue

### Integration

- Imported by `plugins/autonomous-dev/commands/goa.md` as the slash command backend
- Registered in `plugins/autonomous-dev/config/install_manifest.json` as `/goa`

### Testing

- `tests/unit/commands/test_goa_command.py` — Unit tests covering all subcommands, frequency gate enforcement, and issue filing

## eval_metrics.py (v1.0.0 — Issue #1453)

CORE, dependency-free eval-metrics primitives for scoring non-deterministic agent/model evaluations. Stdlib-only (`math`, `statistics`, `dataclasses`, `typing`) — no file I/O, no network, no subprocess; every function is a pure computation over its arguments. Four families of primitives:

1. **Reliability** — `pass_at_k(n, c, k)` returns the Chen et al. unbiased pass@k estimator (any-of-k success probability, numerically stable product form). `pass_hat_k(success_rate, k)` returns `success_rate ** k`, the pass^k CONSISTENCY metric (all-of-k success under resampling) — distinct from pass@k and used as THE gating metric for reliability. `pass_hat_k_dataset(per_task, k)` returns the dataset-level pass^k as the mean of per-task `(c_i/n_i) ** k` values (averaging the powers per task, not raising the pooled rate to the k-th power, to avoid Jensen's-inequality understatement bias).
2. **Statistical gating** — `wilson_interval(successes, n, confidence=0.95)` / `WilsonInterval` dataclass return the Wilson score confidence interval (well-behaved at extreme rates and small samples, z-critical value derived from `statistics.NormalDist` rather than a hardcoded table). `gate_decision(successes, n, baseline, margin=0.05, confidence=0.95)` returns `(passed, message)` — a non-flaky pass/fail gate using the Wilson lower bound vs. `baseline - margin`, robust to a lucky run whose point estimate clears the bar but whose lower bound does not.
3. **Judge calibration** — `cohens_kappa(a, b, c, d)` returns chance-corrected inter-rater agreement for a 2x2 confusion matrix (degenerate `p_e == 1.0` case returns `0.0` rather than raising). `agreement_report(a, b, c, d)` / `AgreementReport` dataclass report BOTH raw agreement and kappa plus the `overstatement_gap` (raw agreement minus kappa) and a Landis-Koch interpretation band, so raw agreement's chance inflation is never the unqualified headline metric.
4. **Contamination detection (CapBencher)** — `capbencher_binomial_test(n, k, bayes_cap, alpha=0.05)` / `CapBencherResult` dataclass run a one-sided exact binomial test (Karlin-Rubin UMP) testing `H0: true accuracy <= bayes_cap`; a small p-value (`flagged=True`) suggests the observed accuracy is implausibly high under the Bayes cap, indicating benchmark contamination (memorized test items).

Deferred / explicitly NOT implemented here (per module docstring): judge-panel aggregation (ships with the #1452 judge wiring), DeepEval integration, trajectory/span evals, Krippendorff's alpha for >2 raters, and sealed-holdout plumbing into `/autoresearch` / `/improve`. This module has no command-level integration yet — it is a CORE primitives library consumed by future eval-gating work.

### Testing

- `tests/unit/lib/test_eval_metrics.py` — 51 unit tests covering golden values for all four families (pass@k boundary cases, pass^k Jensen's-inequality averaging, Wilson interval clamping/degenerate n, gate_decision n==0 short-circuit, Cohen's kappa degenerate p_e==1.0 case and Landis-Koch bands, CapBencher one-sided p-value and flagging threshold)

## alignment_classifier.py (v1.0.0 — Issue #1467)

Two-stage alignment gate for `/implement` STEP 2 (also L1/F1/I1.6), replacing coordinator self-attestation with a deterministic-first, citation-verified decision.

- **Stage 0** (deterministic, this module): `run_stage0(feature_text, doc) -> Stage0Result` scans untrusted feature text for injection signals (`injection_signals()` combines the canonical phrase markers imported from `genai_utils.detect_injection` with structural/authority-claim/gate-bypass/prompt-override regex patterns), PROJECT.md OUT-of-scope keyword overlap (`detect_out_of_scope()` — token-overlap scoring gated so IN-scope vocabulary reuse does not falsely escalate), and architecture-invariant deltas (`detect_architecture_delta()` — only active when PROJECT.md documents an `### INVARIANTS` section; `ARCHITECTURE_DELTA_PHRASES` maps to INV-1..INV-8). **Matching rule (Issue #1600)**: a phrase is not sufficient on its own. The text is split into segments on `[\n.;:!?,]` and a phrase escalates only when the segment carrying it OPENS with a `PROPOSAL_ONSET_VERBS` token — matched by exact token equality after trimming surrounding punctuation and truncating at an apostrophe, so `Let's` matches `let` while the third-person `Replaces` does not match `replace`. The opener may be preceded by a contiguous run of `PROPOSAL_FRAME_TOKENS` (first/second-person subjects, opinion verbs, hedging adverbs), so `We should drop ...` and `I think we should drop ...` qualify while `A reviewer asked whether we should duplicate ...` stops at the first content word and does not; each segment is additionally matched de-gerunded (`Consider dropping the hmac` reaches `drop the hmac`), consulted only after the raw segment so a rewrite can add a match but never remove one. Repair verbs (`fix`, `add`, `document`, `harden`, `enforce`, ...) are deliberately excluded from the onset set: a brief that repairs an invariant violation opens with exactly those. Before this rule, all 30 phrases admitted a plain descriptive sentence that escalated (measured 30/30), so briefs *describing* a violation were escalated as though they proposed one. **Errors in the onset set are not one-directional.** A spurious opener over-escalates (cheap, visible); a MISSING opener under-escalates silently, because this set is the only route by which a phrase can reach an escalation and there is no detector behind it. The first pass of #1600 shipped an imperatives-only set and thereby cleared four measured proposals (`Proposal to drop the hmac ...`, `I want to drop ...`, `Suggest we drop ...`, `We should drop ...`) that the pre-#1600 substring matcher had escalated. Every edit to either set is therefore re-measured in both directions — the 30-row descriptive census and the named 12-entry positive population — before it lands. Per INV-6, a Stage 0 `ESCALATE`/`BLOCK` is FINAL and can never be overridden by Stage 1.
- **Stage 1** (the `alignment-classifier` Haiku agent, external): returns a classification (`in_scope`, `out_of_scope`, `architecture_delta`, `ambiguous`) plus a cited PROJECT.md clause. `map_verdict(stage0, classification, cited_clause, doc, user_approved=...)` folds both stages into the final `Verdict` (`auto_pass`, `escalate`, `user_approved`, `block`) per a documented truth table; only an `in_scope` classification with a clause that `verify_citation()` confirms verbatim in PROJECT.md can produce `auto_pass`. `ALLOWED_VERDICTS = {auto_pass, user_approved}` — downstream consumers MUST test membership, not equality, so a human-approved escalation is never read as a failure.
- **Entry point**: `evaluate_and_record(feature_text, classifier_json=None, *, project_md_path=None, state_path=None, session_id="unknown", repo_root=None, user_approved=False, issue_number="")` is the single function the `/implement` STEP 2 (and L1/F1/I1.6) snippets call — it parses PROJECT.md, runs `run_stage0()`, folds the Stage 1 payload through `map_verdict()`, builds the `AlignmentVerdict`, and hands it to `record_alignment_verdict()`. No decision logic lives outside this module, so the command files cannot drift from the library surface. Returns a JSON-safe dict: the `AlignmentVerdict.to_dict()` payload plus `alignment_passed`, `has_invariants`, and `project_md_found`.
- **Persistence and the autonomy gate**: `record_alignment_verdict(verdict, *, state_path, session_id, repo_root, user_approved=False, autonomous_context=None)` is the SOLE writer of `alignment_passed` AND the sole place a human approval takes effect. It writes the audit artifact (`.claude/alignment_verdict.json`, atomic temp-file + `os.replace`) and JSONL log (`.claude/logs/alignment_verdicts.jsonl`) FIRST; if that write fails, the verdict is downgraded to `escalate` before `alignment_passed` is set — an unrecorded pass is never indistinguishable from a passed gate (INV-7). `alignment_passed` and the co-signed `alignment_verdict` are then written into the signed pipeline state and re-signed via `pipeline_state.sign_state()`. **Approval hardening**: an `escalate` -> `user_approved` upgrade (or a verdict that already arrives as `user_approved`) is REFUSED when `is_autonomous_context()` is true — no human is present to have approved anything — and the verdict is forced back to `escalate` with `user_approved_refused = "autonomous_context"` set on the `AlignmentVerdict` (serialized only when non-empty, so the artifact schema is unchanged for ordinary verdicts). An applied interactive upgrade instead records an `approval` sub-object (`source: "ask_user_question"`, `approved_at`, `stage0_reason`, `citation_verified`) so a real `AskUserQuestion` round-trip is auditable and distinguishable from a bare flag flip. `map_verdict()` itself is pure and reads no environment — the autonomy check happens exclusively at this recording choke point.
- **Autonomy detection**: `is_autonomous_context(env=None, repo_root=None) -> bool` — true when `AUTONOMOUS_DEV_NONINTERACTIVE` is truthy or a drain-pending marker exists; determines whether an `escalate` verdict routes to `AskUserQuestion` (interactive) or a hard BLOCK + `needs-scope-decision` label (autonomous/batch), and gates the `user_approved` upgrade above. `unified_pre_tool.py`'s `PROTECTED_ENV_VARS` includes `ALIGNMENT_USER_APPROVED` so the approval signal cannot be inline-spoofed in a Bash command.
- **PROJECT.md parsing**: `parse_project_md(path)` / `parse_project_md_text(text) -> ProjectDoc` tolerantly extracts GOALS, SCOPE (IN/OUT bullets), CONSTRAINTS, ARCHITECTURE, and the `### INVARIANTS` subsection; a malformed or missing PROJECT.md degrades to "no scope evidence" (which citation verification turns into `escalate`) rather than crashing the gate. `ProjectDoc.has_invariants` gates architecture-delta detection so repos without a documented `INVARIANTS` section are never architecture-blocked.
- **Unicode/text normalization**: `_normalize_text()` applies NFKC normalization plus removal of Unicode category `Cf` (zero-width joiners/spaces, BOM, other invisible format characters) once at the Stage 0 boundary, before `injection_signals()`, tokenization, OUT-of-scope matching, or architecture-delta matching run. This closes an obfuscation bypass where fullwidth characters or a zero-width splice inside a phrase marker (e.g. "ign​ore previous instructions") could defeat literal substring matching.
- **Fail-closed by design (INV-7)**: a missing/unimportable injection detector, an unverifiable citation, an invented/unknown Stage 1 classification, a failed artifact write, and an attempted approval upgrade with no human present all resolve to `escalate` rather than a pass.

### Testing

- `tests/unit/lib/test_alignment_classifier.py` (89 tests) — Stage 0 detectors, citation verification, `map_verdict` truth table, persistence/HMAC re-signing, fail-closed paths, `TestUserApprovalAutonomyGate` (approval refused/downgraded in autonomous context), `TestEvaluateAndRecordApprovalGate` (end-to-end `evaluate_and_record()` approval wiring), `TestUnicodeNormalization` (NFKC + zero-width obfuscation)
- `tests/unit/lib/test_pipeline_state_alignment_verdict.py` (9 tests) — `alignment_verdict` field in the HMAC-signed state
- `tests/unit/hooks/test_alignment_verdict_gate.py` (32 tests) — `unified_pre_tool.py` verdict-aware gate behavior (`_has_alignment_passed`, `_explicit_alignment_verdict_block`), including the fail-open deviation-logging paths of `_alignment_strict_available()`/`_allowed_alignment_verdicts()` and `TestApprovalEnvVarProtection` (`ALIGNMENT_USER_APPROVED` inline-spoofing defense)
- `tests/regression/test_alignment_classifier_corpus.py` (20 tests) — seeded-corpus CI floors against `tests/fixtures/alignment_classifier_corpus.json`
- `tests/regression/test_alignment_delta_precision.py` (42 test functions) — Issue #1600 sentence-onset gating: a 30-row descriptive-prose census (one per live phrase, asserting the `reason` BRANCH rather than the outcome), recall preservation over a named 12-entry positive population, the `arch-006` injection-precedence exception, refusing-arm controls for BOTH the imperative shape (`Proposal:` lead-in, markdown bullet) and the hedged shape (`We should ...`, `I think we should ...`, `Proposal to ...`, gerund complements), permitting-arm controls that reported speech still clears, repair-verb exclusion from `PROPOSAL_ONSET_VERBS`, reporting-verb exclusion from `PROPOSAL_FRAME_TOKENS`, a class-level guard that no named proposal is lost versus the reconstructed pre-#1600 substring matcher, programmatic delimiter safety over the live tuple, the consumer-repo `has_invariants` exemption asserted as the first statement of the function body, and the two production misfires (#1600's own repair brief, #1586's measured finding)
- `tests/regression/test_alignment_gate_backcompat.py` (27 tests) — legacy boolean-only pipeline state and consumer-repo (no classifier library, no `INVARIANTS` section) backward compatibility
- `tests/unit/lib/test_alignment_integration_wiring.py` (17 tests) — end-to-end wiring between `alignment_classifier`, `pipeline_state`, and the hook gate

## git_operations.py (Issue #1564 — first documented here)

**Purpose**: Low-level git primitives behind the automated commit/push path. `auto_implement_git_integration.py` (section 11) is the orchestration layer; this module is where the git subprocesses actually run.

**Location**: `plugins/autonomous-dev/lib/git_operations.py`

**Coverage note**: this library had no entry in this document before Issue #1564 despite `covers:` claiming all of `plugins/autonomous-dev/lib/`. The cross-references elsewhere in this file to "git_operations.py Section 16" are stale — no such section marker exists in the module. Treat the enumeration below as the current public surface and verify against the filesystem rather than trusting it to stay current.

### Public API

**Preflight / state queries**:
- `validate_git_repo() -> Tuple[bool, str]` — is this a git repository
- `check_git_config() -> Tuple[bool, str]` — `user.name` / `user.email` configured
- `detect_merge_conflict() -> Tuple[bool, List[str]]` — unmerged paths; the canonical query for conflicts
- `is_detached_head() -> bool`
- `has_uncommitted_changes() -> bool` — working tree, not index

**Staging**:
- `get_files_to_stage(cwd=None) -> Tuple[List[str], List[str]]`
- `stage_all_changes(cwd=None, gitignore_aware=False) -> Tuple[bool, str]` — stages the whole working tree, untracked files included
- `get_staged_files(cwd=None) -> List[str]` — **new in Issue #1564**. The index contents. Queried via `git status --porcelain -z` rather than `git diff --cached` so it works with no `HEAD` (root commits), and so `core.quotePath` cannot mangle non-ASCII or space-bearing paths into strings that do not exist on disk. The index status is the first porcelain column; ` `, `?`, and `!` mean not staged. Unmerged paths (`U` in either column, plus the `AA` and `DD` pairs that carry no `U`) are excluded — a conflicted path has no single staged blob, so it is not a staged path; use `detect_merge_conflict()` for those. Renames report the destination path

**Commit / push**:
- `commit_changes(message) -> Tuple[bool, str, str]`
- `count_committed_files(ref='HEAD', cwd=None) -> int` — **new in Issue #1564**. Files actually changed by a commit, via `git diff-tree -r -m --root`. `git show --name-only` is not usable here: its combined diff suppresses every path matching a parent, returning `0` for a real merge commit. `--root` is required or a root commit reports nothing. A flag-shaped `ref` raises `ValueError` in-process (the trailing `--` does not prevent option parsing, and answering with `0` would collide with this function's "no commit was created" sentinel). Returns `0` only when no commit was measured
- `get_remote_name() -> str`
- `push_to_remote(...)`, `push_worktree_branch(...)`, `create_feature_branch(branch_name)`
- `auto_commit_and_push(commit_message, branch, push=True, stage_all=True) -> Dict[str, Any]` — the full commit-and-push orchestration. `stage_all=True` (default) preserves commit-everything semantics; `stage_all=False` commits the caller's index verbatim and adds nothing to it. The emptiness precheck follows the mode: whole working tree when `stage_all=True`, index only when `False`. Returns `success`, `commit_sha`, `pushed`, `files_committed`, `error`
- `auto_commit_and_push_worktree(...)` — worktree variant

**Worktree helpers**:
- `is_worktree() -> bool`, `get_worktree_parent() -> Optional[Path]`

**Facade**: `GitOperations` — static-method wrappers (`validate_repo`, `check_config`, `detect_conflicts`, `is_detached`, `has_changes`, `stage_all`, `commit`, `push`, `auto_commit_push(commit_message, branch='main', push=True, stage_all=True)`).

### Staging scope (Issue #1564)

`auto_commit_and_push()` previously called `stage_all_changes()` unconditionally, discarding whatever the caller had staged and sweeping the working tree — untracked files included — into the commit. `stage_all` makes that conditional; the default is unchanged, so every existing caller (batch, worktree, drain, `/implement` STEP 12.7) behaves exactly as before. No caller passes `False` yet. Precondition and pipeline wiring caveats: [GIT-AUTOMATION.md § Staging scope](GIT-AUTOMATION.md#staging-scope-issue-1564).

### Testing

- `tests/unit/lib/test_git_operations_staging.py` — 34 test functions covering `get_staged_files()` porcelain parsing (rename/copy record pairing under `-z` for index-side `R `/`RM` **and** worktree-side ` R`, quoted and non-UTF-8 paths, unmerged-state exclusion), `count_committed_files()` (merge commits, root commits, flag-shaped refs), and `auto_commit_and_push()` under both `stage_all` modes
- `tests/integration/test_auto_implement_git.py` — `create_commit_with_agent_message()` forwarding and `files_committed` propagation
- `tests/regression/test_drain_commit_gate.py` — commit-path regression coverage for the drain loop
