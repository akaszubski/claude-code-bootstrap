---
name: implement-fix
description: Minimal pipeline for test-fixing tasks
version: 1.0.0
user-invocable: false
user_facing: false
allowed-tools: [Agent, Read, Write, Edit, Bash, Grep, Glob, mcp__searxng__search, mcp__searxng__fetch, WebSearch]
---

# FIX MODE

> The key words "MUST", "MUST NOT", "SHOULD", and "MAY" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

Minimal pipeline (5 steps, 4 agents minimum) for test-fixing tasks.
Invoked via `/implement --fix "description"`. Skips research and planning
since the problem is already known (failing tests).

## Coordinator Role — HARD GATE

The coordinator is a **dispatcher**, not a substitute for specialist agents. These constraints apply globally — before any step definitions — and MUST NOT be violated regardless of circumstances.

### Agent Management

The coordinator dispatches work to specialists; it MUST NOT do the work itself.

**FORBIDDEN — You MUST NOT do any of the following**:
- ❌ You MUST NOT write, edit, or modify any project files directly — ALL file modifications MUST go through specialist agents (implementer, doc-master)
- ❌ You MUST NOT do an agent's work when the agent crashes — RETRY once, then BLOCK with a clear error message; never substitute coordinator judgment for agent execution
- ❌ You MUST NOT skip any STEP in the pipeline
- ❌ You MUST NOT summarize agent output instead of passing full results to the next agent — verbatim output is required

### Pipeline Integrity

Step ordering and post-completion behavior are strictly constrained.

**FORBIDDEN — You MUST NOT do any of the following**:
- ❌ You MUST NOT parallelize agents from different pipeline phases (e.g., running F3 and F4 concurrently)
- ❌ You MUST NOT clean up pipeline state before STEP F5 launches
- ❌ You MUST NOT perform any file edits after agents complete — the coordinator's only permitted post-agent actions are: outputting the final summary, git operations (add, commit, push), and launching STEP F5
- ❌ You MUST NOT skip STEP F4.7 when the changeset matches the activation trigger (SQL, ORM models, execution/order/trade/payment paths) — even if the unit tests pass green. The 4-fix chain #1285 → #1288 happened with all-green unit tests. (#1210)

### Output Fidelity

The coordinator MUST transmit agent outputs intact.

**FORBIDDEN — You MUST NOT do any of the following**:
- ❌ You MUST NOT paraphrase or condense agent output when passing to the next stage
- ❌ You MUST NOT pass fewer than 50% of the implementer output words to the reviewer — if context is a constraint, include the implementer's file change list and test results in full before trimming any prose sections

## Fix Mode Progress Protocol

Output structured progress at each step. Same format conventions as the full pipeline protocol.

**Step Banner**: `STEP FN/5 — Step Name` with agent info where applicable.
**Timing**: Capture `FIX_START=$(date +%s)` at pipeline start. Capture per-step timing.
**Gate Results**: `GATE: name — PASS/BLOCKED`
**Final Summary** (after STEP F6 persists the CIA report, before STEP F6.5 cleanup):
```
========================================
FIX COMPLETE
========================================
Step  Description         Agent(s)                           Time    Status
----  ------------------  ---------------------------------  ------  ------
F1    Alignment           —                                  2s      PASS
F1.5  Pre-staged check    —                                  1s      PASS
F2    Test context        —                                  5s      done
F3    Implementation      implementer (Opus)                 2:30    done
F3    Test gate           —                                  8s      PASS
F4    Review + docs       reviewer, doc-master               45s     done
F5    CI analysis         continuous-improvement-analyst     30s     done
F6    Persist CIA report  — (coordinator Write, #1209)       1s      done
========================================
Total: 4:02 | Tests: N passed, M failed | Files changed: N | CIA: .claude/local/cia-DATE-issue-NNNN-fix.md
========================================
```

## Implementation

## Steps F1-F2: Alignment and Test Context

### STEP F1: Validate PROJECT.md Alignment

**Progress**: Output step banner (STEP F1/5 — Alignment). Capture FIX_START. Output gate result.

Read `.claude/PROJECT.md`. If missing: BLOCK ("Run `/setup` or `/align --retrofit`").

#### Pipeline State Initialization (Before Alignment Verdict)

Initialize the fix-mode pipeline state file BEFORE running the alignment gate protocol below, so that `record_alignment_verdict` (Issue #1467) writes `alignment_passed` and `alignment_verdict` into an existing state file. This also ensures hook enforcement (prompt integrity, pipeline ordering) is active during fix mode:

```bash
python3 -c "
import sys, os, time
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', os.path.expanduser('~/.claude/lib')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
state = {'mode': 'fix', 'explicitly_invoked': True, 'start_time': int(time.time())}
# ATOMIC (Issue #1384). open(path,'w') truncates at OPEN time, so a kill
# between the open and the json.dump left a 0-BYTE sentinel with the prior
# content already gone; ensure_sentinel_heartbeat() then failed json.loads and
# recreated it as a bare {session_id, recovered, recovered_at}, which
# _is_pipeline_active() classifies NOT-active by design.
#
# PRECONDITION, load-bearing and deliberate: atomic_write_json requires the
# PARENT DIRECTORY to exist and raises OSError from mkstemp if it does not.
# There is NO 'mkdir -p' here and NO 'export PIPELINE_STATE_FILE' anywhere in
# this file (implement.md pairs those two; implement-batch.md deliberately has
# neither and every one of its blocks resolves the same default
# independently). Fix mode relies instead on get_legacy_sentinel_path()
# creating <repo>/.claude/local/ as a best-effort side effect, evaluated
# EAGERLY because it is the .get() default argument. That is cwd-dependent —
# the marker walk must land on the real repo. Do NOT reorder this to a lazy
# default and do NOT add 'export PIPELINE_STATE_FILE'.
from pathlib import Path
from pipeline_state import atomic_write_json, get_legacy_sentinel_path
atomic_write_json(
    Path(os.environ.get('PIPELINE_STATE_FILE', str(get_legacy_sentinel_path()))),
    state,
)
print('Pipeline state initialized for fix mode')
"
```

This ensures prompt integrity enforcement (Layer 5) can detect an active pipeline and apply baseline shrinkage checks in addition to the minimum word count gate.

Run the STEP 2 alignment gate protocol from implement.md (Stage 0 → alignment-classifier dispatch → record_alignment_verdict → verdict routing) using the fix description as the feature text. Initialize the fix-mode pipeline state BEFORE the verdict step so record_alignment_verdict writes alignment_passed and alignment_verdict into it.

This is the same alignment gate as the full pipeline STEP 1.

#### Prompt Baseline Reset (Defensive — Issue #1088 F3)

Before initializing pipeline state, clear any stale `prompt_baselines.json` from a prior session. /fix mode by design dispatches shorter, focused prompts; stale baselines from prior runs frequently exceed the 20% shrinkage threshold against fresh fix-mode prompts and produce false-positive integrity blocks.

```python
import sys, os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', os.path.expanduser('~/.claude/lib')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from prompt_integrity import clear_prompt_baselines
clear_prompt_baselines()
print('Prompt baselines cleared for fix mode')
```

Note: This step becomes unnecessary once #1082 Phase 1a (per-issue baseline split) lands. Until then, /fix mode SHOULD clear baselines defensively at pipeline start.

#### PIPELINE_BASE_COMMIT Capture (Issue #1069)

Immediately after initializing the pipeline state, capture the git HEAD as `PIPELINE_BASE_COMMIT` and persist it to the state file. This commit SHA anchors `git diff --name-only` commands at STEP F3.5 (spec-validator dispatch) so the diff reflects ONLY files changed by THIS pipeline run, not pre-existing working-tree state from prior sessions or unrelated edits. Without this anchor, spec-validator emits false-positive FAIL verdicts whenever the working tree already contained uncommitted changes when the pipeline started.

```bash
# Capture base commit for spec-validator anchoring (Issue #1069)
PIPELINE_BASE_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "")
python3 -c "
import sys, os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', os.path.expanduser('~/.claude/lib')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from pipeline_state import set_pipeline_base_commit
from pipeline_state import get_legacy_sentinel_path
state_path = os.environ.get('PIPELINE_STATE_FILE', str(get_legacy_sentinel_path()))
ok = set_pipeline_base_commit('$PIPELINE_BASE_COMMIT', state_path=state_path)
print(f'PIPELINE_BASE_COMMIT recorded: $PIPELINE_BASE_COMMIT (ok={ok})')
"
export PIPELINE_BASE_COMMIT
```

**FORBIDDEN**:
- ❌ Skipping the `PIPELINE_BASE_COMMIT` capture — STEP F3.5 spec-validator dispatch depends on this value to filter out pre-existing tree state.
- ❌ Using `git diff --name-only HEAD` in any acceptance criterion or spec-validator prompt template downstream of this step — always use `git diff --name-only $PIPELINE_BASE_COMMIT` so the diff reflects only files changed by this pipeline run.

### STEP F1.5: Pre-Staged Files Check — HARD GATE

**Progress**: Output step banner (STEP F1.5/5 — Pre-Staged Check). Output gate result.

```bash
STAGED_FILES=$(git diff --cached --name-only 2>/dev/null)
if [ -n "$STAGED_FILES" ]; then
  echo "BLOCKED: Pre-staged files detected"
  echo "$STAGED_FILES"
fi
```

If `STAGED_FILES` is non-empty: **BLOCK** the pipeline. Display:

```
BLOCKED — Pre-staged files detected.

The following files are already staged from a previous session:
[list files]

These would be bundled into this fix's commit, creating misleading git history.

Options:
A) Unstage: git reset HEAD
B) Commit first: git commit -m "wip: staged changes from previous session"
C) Review: git diff --cached
```

Do NOT proceed to STEP F2 until the staging area is clean.

**FORBIDDEN**:
- ❌ Proceeding with pre-staged files present
- ❌ Silently unstaging files without user confirmation
- ❌ Treating pre-staged files as part of the current fix

### STEP F2: Gather Test Context

**Progress**: Output step banner (STEP F2/5 — Test Context). Output test failure summary after.

Run the test suite to capture current failures:

```bash
pytest --tb=short -q 2>&1 | head -200
```

Parse the output to identify:
- Number of passing vs failing tests
- Names of failing tests
- Affected source files (from traceback paths)
- Error messages and assertion failures

If ALL tests pass (0 failures): EXIT EARLY with message "All tests pass. No fix needed."

Display:
```
Fix Mode - Test Context:
  Failing tests: N
  Affected files: [list]
  Error summary: [brief]
```

## Steps F3-F3.5: Implementation and Spec Validation

### STEP F3: Implementer (Opus) - HARD GATE

**Progress**: Output step banner (STEP F3/5 — Implementation, Agent: implementer (Opus)). Output agent completion, then test gate result with counts.

Invoke the implementer agent with the failing test output and affected files.

```
subagent_type: "implementer"
model: "opus"
prompt: "FIX MODE: Fix failing tests. Do NOT add new features.

**Failing test output**:
[paste pytest output from STEP F2]

**Affected files**:
[list of files from traceback]

**Instructions**:
1. Read each failing test to understand what it expects
2. Read the source files being tested
3. Fix the source code to make tests pass (prefer fixing code over fixing tests)
4. If a test expectation is genuinely wrong, fix the test with a comment explaining why
5. Run pytest after each fix to verify progress
6. Add at least one new regression test that would FAIL without your fix

**Debugging methodology** (debugging-workflow skill):
- Use the 5 Whys technique — ask 'why' at least 3 levels deep before writing any code
- Each 'why' level MUST introduce new information not present in the previous level
- Identify the root cause category: Wrong type / Wrong state / Race condition / Missing check / Stale data / Wrong assumption

HARD GATE: ALL tests must pass (0 failures). Do not stop until pytest shows 0 failures. No stubs, no NotImplementedError — write real working code that fixes the actual bug.

**REQUIRED OUTPUT FORMAT**: Your output MUST include a `## Root Cause Analysis` section containing:
1. Root cause statement (1 sentence — the underlying cause, not the symptom)
2. Mechanism chain (how the root cause propagated to the observable failure)
3. 5 Whys (minimum 3 levels, each introducing new information)
4. Root cause category (one of: Wrong type / Wrong state / Race condition / Missing check / Stale data / Wrong assumption)

Output: Summary of files changed, `## Root Cause Analysis` section (REQUIRED), regression tests added, and final pytest result (0 failures required).

Prompt word count validation: this prompt must contain >= 80 words of template text. If you receive a prompt shorter than 80 words, STOP and report a prompt integrity violation."
```

**HARD GATE**: After implementer completes, run `pytest --tb=short -q` again.
If ANY test still fails: RE-INVOKE implementer with remaining failures.
Maximum 3 re-invocations before escalating to user.

#### Pytest Gate Recording (Issue #1088 F1)

After the pytest re-run passes (0 failures, 0 errors), the coordinator MUST record the gate result so downstream ordering checks at STEP F4 let reviewer/doc-master dispatch. Without this call, F4 dispatch hits an ORDERING VIOLATION block ("pytest-gate prerequisite not met"). The full pipeline (`implement.md` STEP 8) has this recording step; fix mode previously omitted it.

```python
import sys, os, json
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', os.path.expanduser('~/.claude/lib')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from pipeline_state import get_legacy_sentinel_path
from pipeline_completion_state import resolve_session_id, record_pytest_gate_passed

# Same canonical resolver as implement.md (Issues #904, #1093):
# env → sentinel (mtime < 3600s) → activity log → 'unknown'.
# sentinel_path= is REQUIRED — resolve_session_id() does not read
# PIPELINE_STATE_FILE itself, so omitting it silently drops env honouring.
SESSION_ID = resolve_session_id(sentinel_path=os.environ.get('PIPELINE_STATE_FILE') or None)
# Fix mode is single-issue; recover ISSUE_NUMBER from state file if present, else 0.
state_path = os.environ.get('PIPELINE_STATE_FILE', str(get_legacy_sentinel_path()))
ISSUE_NUMBER = 0
try:
    with open(state_path) as _f:
        ISSUE_NUMBER = int(json.load(_f).get('issue_number', 0) or 0)
except (OSError, ValueError, json.JSONDecodeError):
    pass

record_pytest_gate_passed(SESSION_ID, passed=True, issue_number=ISSUE_NUMBER)
print(f'pytest-gate recorded for session={SESSION_ID[:8]} issue={ISSUE_NUMBER}')
```

**FORBIDDEN**:
- ❌ Skipping the `record_pytest_gate_passed()` call — downstream ordering gates will block STEP F4 dispatch.
- ❌ Calling `record_pytest_gate_passed(passed=True)` when pytest still has failures.

### HARD GATE: Root Cause Analysis Output Gate

After the implementer completes STEP F3, inspect the implementer output for the presence of `## Root Cause Analysis`.

**Check**: Does the implementer output contain the literal string `## Root Cause Analysis`?

**If absent on first completion**: Re-invoke the implementer once with the following addition to the prompt:
```
HARD GATE VIOLATION: Your output is missing the required `## Root Cause Analysis` section.
You MUST add it now. The section must include:
1. Root cause statement (1 sentence)
2. Mechanism chain (A → B → C → failure)
3. 5 Whys (minimum 3 levels, each introducing new information)
4. Root cause category (Wrong type / Wrong state / Race condition / Missing check / Stale data / Wrong assumption)
Output the complete Root Cause Analysis section and nothing else.
```

**If still absent after re-invocation**: BLOCK the pipeline with:
```
BLOCKED — Root Cause Analysis missing after retry.
The implementer did not produce the required ## Root Cause Analysis section.
This section is required in fix mode to ensure the root cause is identified,
not just the symptom. Re-invoke /implement --fix with a more specific bug description.
```

**FORBIDDEN**:
- ❌ Proceeding to STEP F3.5 without verifying `## Root Cause Analysis` is present in the output
- ❌ Treating a symptom description as a root cause analysis
- ❌ Skipping this gate when the implementer output is long (length does not exempt the gate)

### HARD GATE: Regression Test Requirement

If fixing a bug, at least one NEW test must be added that would FAIL without the fix. This ensures the bug never returns.

**Verification**: Compare test count from STEP F2 (before fix) vs after STEP F3 (after fix). If `after_count <= before_count`, BLOCK with message: "Bug fix requires at least one new regression test that reproduces the bug. Add a test that fails without your fix and passes with it."

**Exception**: If the bug was caught BY an existing failing test (i.e., the test that originally failed IS the regression test), this gate passes automatically. Document which existing test covers the regression.

**FORBIDDEN**:
- Fixing a bug without a test that proves it was broken
- Claiming "the fix is obvious and doesn't need a test"
- Adding a test that passes both with and without the fix (that's not a regression test)

### STEP F3.5: Spec-Blind Validation — HARD GATE

**Progress**: Output step banner (STEP F3.5/5 — Spec-Blind Validation, Agent: spec-validator (Opus)). Output verdict after.

Same context boundary as STEP 8.5 in the full pipeline. Pass ONLY:
- Bug description / fix description (from user input)
- Changed file paths (from `git diff --name-only $PIPELINE_BASE_COMMIT` — anchored to the commit captured at STEP F1 per Issue #1069; falls back to `HEAD` only when `PIPELINE_BASE_COMMIT` is empty)
- PROJECT.md scope sections

**Changed-file computation** (Issue #1069):

```bash
# Recover PIPELINE_BASE_COMMIT from state file (set at STEP F1)
PIPELINE_BASE_COMMIT=$(python3 -c "
import sys, os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', os.path.expanduser('~/.claude/lib')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from pipeline_state import get_pipeline_base_commit, get_legacy_sentinel_path
state_path = os.environ.get('PIPELINE_STATE_FILE', str(get_legacy_sentinel_path()))
print(get_pipeline_base_commit(state_path=state_path) or '')
")
# Anchor diff to PIPELINE_BASE_COMMIT so the file list reflects ONLY changes
# made by THIS pipeline run, not pre-existing working-tree state.
# Fallback to HEAD only when the base commit is missing (legacy state files).
if [ -n "$PIPELINE_BASE_COMMIT" ]; then
  CHANGED_FILES=$(git diff --name-only "$PIPELINE_BASE_COMMIT" 2>/dev/null)
else
  CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null)
fi
```

**FORBIDDEN**:
- ❌ Passing implementer output, code diffs, reviewer feedback, or any implementation details to the spec-validator.
- ❌ Generating acceptance criteria that reference `git diff --name-only HEAD` directly — always use `git diff --name-only $PIPELINE_BASE_COMMIT` (Issue #1069). Pre-existing working-tree modifications (e.g., docs edited before the pipeline started) appear in `git diff HEAD` and produce false-positive FAIL verdicts.

**Agent**(subagent_type="spec-validator", model="opus") — Pass bug description + changed file paths ONLY.

Parse verdict: `SPEC-VALIDATOR-VERDICT: PASS` or `SPEC-VALIDATOR-VERDICT: FAIL`. On FAIL, re-invoke implementer with failing test names only (max 2 cycles). Block if still failing after 2 cycles.

## Step F4: Review, Security, and Docs

### STEP F4: Reviewer + Doc-master (parallel)

**Progress**: Output step banner (STEP F4/5 — Review + Docs, Agents: reviewer (Sonnet), doc-master (Sonnet)). Output each agent completion. Then output Final Summary table.

#### Security-Sensitivity Detection — HARD GATE

Before invoking any STEP F4 agents, run deterministic security-sensitivity detection on the changed file list. The diff MUST be anchored to `PIPELINE_BASE_COMMIT` (Issue #1069) so pre-existing working-tree state is excluded:

```bash
# Recover PIPELINE_BASE_COMMIT from state file (set at STEP F1)
PIPELINE_BASE_COMMIT=$(python3 -c "
import sys, os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', os.path.expanduser('~/.claude/lib')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from pipeline_state import get_pipeline_base_commit, get_legacy_sentinel_path
state_path = os.environ.get('PIPELINE_STATE_FILE', str(get_legacy_sentinel_path()))
print(get_pipeline_base_commit(state_path=state_path) or '')
")
if [ -n "$PIPELINE_BASE_COMMIT" ]; then
  CHANGED_FILES=$(git diff --name-only "$PIPELINE_BASE_COMMIT" 2>/dev/null)
else
  CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null)
fi
```

Match each file path against security-sensitive patterns (substring match, case-insensitive). Patterns are grouped by domain — false positives are cheap (an extra security review), false negatives are expensive (missed security regression):

**Infrastructure**: `hooks/`, `lib/auto_approval_engine`, `lib/tool_validator`, `config/auto_approve_policy`, `lib/security`

**Auth/access**: `auth`, `crypto`, `permission`, `session`, `token`, `secret`, `credential`, `password`, `oauth`, `sso`, `jwt`, `rbac`

**Financial**: `trading`, `payment`, `billing`, `financial`, `transaction`, `wallet`

**Schema/environment**: `migration`, `alembic`, `.env`

**Exclusion rule**: File paths starting with `tests/` are excluded — test files that reference security topics do not themselves pose a security risk.

Output the detection result before proceeding:
```
Security-auditor: SKIP (no security-sensitive files)
```
or:
```
Security-auditor: REQUIRED (matched: [list of matched files and patterns])
```

When detection outputs `REQUIRED`, the security-auditor invocation is **mandatory** — it MUST be added to the parallel agent invocations in this step.

**FORBIDDEN**:
- ❌ Skipping security-auditor when detection flagged one or more files as REQUIRED
- ❌ Running the pattern match only against file names — match against full relative paths
- ❌ Proceeding without outputting the detection result

#### HARD GATE: Verbatim Implementer Output

You MUST pass the FULL implementer output from STEP F3 to the reviewer and security-auditor agents — do NOT summarize, condense, or paraphrase. The implementer output contains file paths, diff context, and test results that the reviewer needs verbatim to perform a thorough review. Truncating or summarizing this output is the root cause of prompt word count violations.

#### HARD GATE: Prompt Integrity Validation

Before invoking the reviewer or security-auditor agent, validate the constructed prompt word count:

1. Reviewer prompt MUST be >= 80 words
2. Security-auditor prompt (if invoked) MUST be >= 80 words
3. If below minimum, reconstruct prompt by including more context from the implementer output — add the full list of changed files, the complete test results, and the diff summary

The library function `validate_prompt_word_count(agent_type, prompt)` from `plugins/autonomous-dev/lib/prompt_integrity.py` provides this validation. Call it and check `result.passed` before invoking each critical agent.

**FORBIDDEN**:
- Sending a reviewer or security-auditor prompt with fewer than 80 words
- Summarizing or condensing the implementer output before passing it to the reviewer
- Omitting file paths, test results, or diff context from the reviewer prompt
- Invoking security-auditor with only the skeleton prompt template without the actual verbatim implementer output pasted in

Invoke agents in PARALLEL. When security-auditor is REQUIRED, invoke all three simultaneously. When security-auditor is SKIP, invoke two (reviewer + doc-master):

1. **Reviewer** (Sonnet): Review the fix for correctness, edge cases, and regressions.

```
subagent_type: "reviewer"
model: "sonnet"
prompt: "FIX MODE REVIEW: You are reviewing a test fix for correctness, edge cases, and potential regressions. Your review MUST be thorough and MUST cover all changed files.

**Review checklist — evaluate each item explicitly**:
1. Read every changed file listed below and verify the fix is correct
2. Identify edge cases that the fix may not handle
3. Verify that no regressions were introduced by the changes
4. Confirm that new regression tests exist and would fail without the fix
5. Verify that error handling is preserved and not weakened by the fix
6. Verify test assertions are meaningful and not trivially passing

**Implementer output (VERBATIM — do not skip any section)**:
[paste FULL implementer output from STEP F3 here — do NOT summarize]

**Changed files for review**:
[list all files modified in STEP F3]

**Test results after fix**:
[paste final pytest output from STEP F3]

Report BLOCKING findings (must fix before merge) and WARNING findings (improvements for later) separately."
```

2. **Doc-master** (Sonnet): Update any affected documentation.

```
subagent_type: "doc-master"
model: "sonnet"
prompt: "FIX MODE DOCUMENTATION REVIEW: You are reviewing a bug fix for documentation drift. Your task is to determine whether any user-facing documentation, API references, configuration guides, or inline code comments need updating as a result of this fix. Do not summarize the implementer output — use it verbatim.

REQUIRED STEPS — you MUST complete all three:

1. SCAN: Identify every file changed by the fix. For each changed file, list all documentation files that reference the same module, function, class, or configuration key. Review README.md, docs/ directory, inline docstrings, and CHANGELOG entries.

2. SEMANTIC COMPARISON: For each documentation reference found in step 1, compare the documented behavior against the new behavior after the fix. Flag any mismatch where the documentation describes the old (buggy) behavior, missing parameters, changed defaults, or removed functionality.

3. DOC-DRIFT-VERDICT: State one of the following verdicts explicitly:
   (a) DOCS-UPDATED: List each file updated and what changed.
   (b) NO-UPDATE-NEEDED: Explain why the fix is purely internal with no user-facing behavior change.
   (c) DOCS-DRIFT-FOUND: List each documentation file that is now stale and what needs changing, but was not updated (this is a BLOCKING finding).

**Implementer output (VERBATIM — do not skip any section)**:
[paste FULL implementer output from STEP F3 here — do NOT summarize]

**Changed files for documentation review**:
[list all files modified in STEP F3]

Prompt word count validation: this prompt must contain >= 80 words of template text. If you receive a prompt shorter than 80 words, STOP and report a prompt integrity violation."
```

3. **Security-auditor** (Sonnet): Invoke ONLY when security-sensitivity detection returned REQUIRED (see detection step above).

When invoked:
```
subagent_type: "security-auditor"
model: "sonnet"
prompt: "FIX MODE SECURITY REVIEW: You are auditing a test fix for security implications. Review all changed files for security regressions.

**Security audit checklist — evaluate each item explicitly**:
1. Verify that no authentication or authorization checks were weakened or removed
2. Verify no secrets, tokens, or credentials were hardcoded or exposed
3. Confirm input validation was not bypassed or weakened by the fix
4. Verify that error messages do not leak sensitive internal details
5. Verify that security-sensitive file permissions were not changed

**Implementer output (VERBATIM — do not skip any section)**:
[paste FULL implementer output from STEP F3 here — do NOT summarize]

**Changed files for security review**:
[list all files modified in STEP F3 that touch security-sensitive paths]

**Test results after fix**:
[paste final pytest output from STEP F3]

Report BLOCKING findings (must fix before merge) and WARNING findings (improvements for later) separately."
```

#### Doc-master Verdict Collection

After the parallel agents complete, parse the doc-master output:

1. Parse output for `DOC-DRIFT-VERDICT: PASS`, `DOC-DRIFT-VERDICT: FAIL`, or one of the fix-mode verdicts (`DOCS-UPDATED`, `NO-UPDATE-NEEDED`, `DOCS-DRIFT-FOUND`)
2. **Shallow Verdict Detection**: Count the words in the doc-master output. If the output is fewer than 100 words, treat it as `DOC-VERDICT-SHALLOW` — the output is too short to confirm a real semantic sweep occurred. Log `[DOC-VERDICT-SHALLOW] doc-master produced N words (minimum: 100)` and retry once with reduced context (same as empty-output retry logic above). If retry also produces fewer than 100 words or no verdict, log `[DOC-VERDICT-SHALLOW-RETRY-FAILED] doc-master still shallow after retry — proceeding with warning`.
3. If `DOCS-DRIFT-FOUND`: BLOCK. Display the stale documentation files. User must address before proceeding.
4. If doc-master made fixes: stage them with `git add`

## Step F4.7: PROD Verification Checklist (conditional)

### STEP F4.7: PROD Verification Checklist (conditional) — HARD GATE (#1210)

**Progress**: Output step banner (STEP F4.7/5 — PROD Verification). Output the activation-trigger evaluation. If skipped, output the SKIPPED line and proceed to STEP F5. Otherwise, output the verification checklist with the recommended query, the recording format, and the soft-gate warning.

**Motivation (#1210)**: The #1285 → #1286 → #1287 → #1288 chain on 2026-06-11 was four consecutive `--fix` pipelines that all chased the same PROD writeback failure for trade #321. Every fix was validated GREEN in unit tests yet failed in PROD because the test fixtures diverged from real PROD data:

- **#1285**: PASS unit tests; PROD: Fill recovery never ran at startup. Test covered only the 1102-handler path.
- **#1286**: PASS unit tests; PROD: IBKR symbol != market_key mismatch still broke. Fixture used market_key on both sides.
- **#1287**: PASS unit tests; PROD: `status='open'` failed Postgres uppercase enum. Fixture injected lowercase strings; no real Postgres.
- **#1288**: PASS unit tests; PROD: Disabled duplicate row shadowed enabled row. No duplicate row in test data.

A mandatory PROD verification step after deploy would have caught the regression at #1285 and collapsed the chain to a single fix. STEP F4.7 closes that gap.

#### Activation Trigger — When This Step is REQUIRED

This step is **REQUIRED** when the changed files (the diff captured at STEP F4) include **any** of the following:

- SQL or migration files: `*.sql`, paths under `migrations/`, paths under `alembic/`
- Database schema or model files: `*model*.py` carrying SQLAlchemy / Django / Pydantic ORM markers
- Execution / order / trade code: file or directory names matching `*trade*`, `*order*`, `*exec*`, `*execution*`
- Payment / financial code: file or directory names matching `*payment*`, `*billing*`, `*financial*`, `*transaction*`
- Any file under a `prod/`, `production/`, `live/`, or `mainnet/` directory

Match is **substring, case-insensitive** against the full relative path.

If **none** of these patterns match the changeset, this step is SKIPPED. Output:

```
STEP F4.7: SKIPPED — no DB/execution paths in changeset.
```

Then proceed directly to STEP F5.

#### REQUIRED Checklist — Within 10 Minutes of Git Commit

When the trigger matches, the coordinator MUST emit the following verification checklist as part of the step output. The coordinator MUST derive a **recommended query** from the fix's commit message and the changed lines (e.g., the predicate that was modified) and emit it on line 2 of the checklist.

```
[STEP F4.7] PROD VERIFICATION REQUIRED (#1210)
Within 10 minutes of git commit:
1. SSH to PROD (or invoke the PROD verification script)
2. Run the minimal query that exercises the fixed predicate:
     {RECOMMENDED_QUERY}
   (Derived from the fix's commit message + changed lines. Edit if the
    actual fixed predicate differs.)
3. Record the result as a comment on the GitHub issue using:
     VERIFIED: {query} → {result}
   If the result diverges from expected, record instead:
     UNVERIFIED-MISMATCH: {query} → {observed} vs expected {expected}
4. If result does not match expected: file a follow-up issue
   IMMEDIATELY — do not wait for the watchdog. Reference the original
   --fix issue and the diverging query/result.
```

#### Soft Gate — Initial Rollout

This step is a **SOFT GATE** for the initial rollout per #1210 — the coordinator emits the checklist as a warning but does **NOT** block pipeline completion if the verification has not yet been recorded. The intent is to roll the discipline out gradually before hardening to a BLOCK.

After emitting the checklist, the coordinator MUST also emit:

```
[STEP-F4.7-WARNING] PROD verification required within 10 minutes; no enforcement yet — will harden to BLOCK in a follow-up.
```

Hardening this gate to BLOCK is deferred to a follow-up issue (the `stop_quality_gate` hook can require a `VERIFIED:` line in the issue comment or commit message before closing the pipeline). Do NOT wire the hook in this commit.

**FORBIDDEN** — You MUST NOT do any of the following (#1210):

- ❌ You MUST NOT skip STEP F4.7 when the changeset matches the activation trigger — even if every unit test passes green. The 4-fix chain #1285 → #1288 happened with all-green unit tests.
- ❌ You MUST NOT emit only the SKIPPED line without showing the trigger evaluation (the reader needs to see WHICH patterns were checked and which did not match).
- ❌ You MUST NOT omit the recommended query from the checklist when the step activates — the operator needs the exact query to run, not a placeholder.
- ❌ You MUST NOT omit the `[STEP-F4.7-WARNING]` line — even though the gate is SOFT, the warning is what makes the discipline visible. The warning line is REQUIRED whenever the checklist is emitted.

## Step F5: Continuous Improvement

### STEP F5: Continuous Improvement

**Progress**: Output step banner (STEP F5/5 — Continuous Improvement). Output agent launch confirmation. After the agent returns, proceed to STEP F6 (Persist CIA Report) BEFORE pipeline state cleanup.

**REQUIRED**: **Agent**(subagent_type="continuous-improvement-analyst", model="sonnet") — Examines session logs for bypasses, test drift, and fix pipeline completeness.

CIA MUST run synchronously (NOT `run_in_background=true`) so the coordinator can capture its return value for STEP F6. Issue #1209 documented three consecutive fix pipelines (#1283, #1287, #1288 on 2026-06-11) where CIA attempted to self-persist via Bash and produced 30-byte placeholder reports because the OS/sandbox silently dropped the subprocess write. The coordinator-side capture-and-persist path (STEP F6) is the only reliable persistence mechanism.

**FORBIDDEN** — You MUST NOT do any of the following (violations = pipeline failure):
- ❌ You MUST NOT skip STEP F5 for any reason (time pressure, context limits, "already reported")
- ❌ You MUST NOT skip STEP F6 (Persist CIA Report) — the CIA output is lost if not persisted by the coordinator
- ❌ You MUST NOT launch CIA with `run_in_background=true` in --fix mode — STEP F6 needs the synchronous return value (#1209)
- ❌ You MUST NOT clean up pipeline state before STEP F6 completes
- ❌ You MUST NOT inline the analysis yourself instead of invoking the agent
- ❌ You MUST NOT instruct CIA to write its own report via Bash, `python3 -c "...write_text(...)"`, or `cat > .../cia-*.md << EOF` — those writes silently fail at the OS/sandbox level (#1209)

### STEP F6: Persist CIA Report — HARD GATE (#1209)

**Progress**: Output step banner (STEP F6 — Persist CIA Report). Output the persisted file path and byte count after.

After the CIA agent (STEP F5) returns, capture its full output text. This is the only reliable way to persist the CIA report to `.claude/local/` — see #1209 for evidence that CIA-internal Bash/subprocess writes silently fail at the OS/sandbox level.

**Compute the report path**:

```bash
TODAY=$(date +%Y-%m-%d)
ISSUE_NUMBER=$(python3 -c "
import sys, json, os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', os.path.expanduser('~/.claude/lib')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
        break
from pipeline_state import get_legacy_sentinel_path
state_path = os.environ.get('PIPELINE_STATE_FILE', str(get_legacy_sentinel_path()))
try:
    with open(state_path) as f:
        print(int(json.load(f).get('issue_number', 0) or 0))
except Exception:
    print(0)
")
CIA_REPORT_PATH=".claude/local/cia-${TODAY}-issue-${ISSUE_NUMBER}-fix.md"
mkdir -p .claude/local
echo "CIA report path: $CIA_REPORT_PATH"
```

**Persist via the Write tool from the coordinator (parent session)** — pass the captured CIA output text as the file content. Do NOT delegate the write to CIA via Bash. Do NOT use `python3 -c "...write_text(...)"`, `cat > ... << EOF`, or any subprocess write — those silently fail at the OS/sandbox level (#1209).

**Evidence — Persist-failure detection (>100 bytes required)**:

```bash
BYTES=$(wc -c < "$CIA_REPORT_PATH" 2>/dev/null || echo 0)
if [ "$BYTES" -lt 100 ]; then
    echo "[CIA-PERSIST-FAILED] $CIA_REPORT_PATH is only $BYTES bytes (expected >100, typical CIA reports are 500-5000 words)"
    echo "[CIA-PERSIST-FAILED] This indicates either CIA returned an empty output or the Write tool failed. Surface to user."
else
    echo "CIA report persisted: $CIA_REPORT_PATH ($BYTES bytes)"
fi
```

CIA reports typically range 500-5000 words (3,000-30,000 bytes). A persisted file under 100 bytes indicates a `[CIA-PERSIST-FAILED]` condition — either CIA returned empty output (re-invoke CIA once) or the coordinator failed to capture/Write the output (surface to user).

**FORBIDDEN**:
- ❌ Delegating the report write to CIA via Bash, `python3 -c`, heredoc, or any subagent tool (#1209 silent-failure mode)
- ❌ Using a path scheme other than `.claude/local/cia-YYYY-MM-DD-issue-NNNN-fix.md`
- ❌ Proceeding to pipeline state cleanup without verifying the persisted file is >100 bytes
- ❌ Logging `[CIA-PERSIST-FAILED]` and silently continuing — the failure MUST be surfaced to the user

### STEP F6.5: Pipeline State Cleanup

After STEP F6 has persisted the CIA report and verified the file size, clean up the pipeline state file:

```bash
# Issue #1376: resolve the per-repo sentinel via get_legacy_sentinel_path()
# rather than the legacy machine-global /tmp path. This file never exports
# PIPELINE_STATE_FILE, so the `:-` default IS the path used on every fix run —
# a /tmp literal here deleted a file that does not exist while the real
# sentinel accumulated under <repo>/.claude/local/.
CLEANUP_STATE_FILE="${PIPELINE_STATE_FILE:-$(python3 -c "
import sys, os
for _p in ('.claude/lib', 'plugins/autonomous-dev/lib', os.path.expanduser('~/.claude/lib')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p); break
from pipeline_state import get_legacy_sentinel_path
print(get_legacy_sentinel_path())
")}"
# Issue #1411: plain `rm` (no force flag) — the shipped deny rules
# hard-block the force-delete flags. `--` guards dash-prefixed names,
# `|| true` preserves force-remove semantics (no error if already gone).
rm -- "$CLEANUP_STATE_FILE" 2>/dev/null || true
```

**FORBIDDEN** (Issue #559): Cleaning up pipeline state before STEP F5 + F6 complete. The analyst reads pipeline state — cleanup before launch loses context. The coordinator reads CIA output — cleanup before persist loses the report.

---

## Agent Count

- **Minimum**: 4 agents (implementer, reviewer, doc-master, continuous-improvement-analyst)
- **Maximum**: 5 agents (+ security-auditor if security-sensitive files changed)

## Mutual Exclusivity

`--fix` is mutually exclusive with:
- `--batch` (batch file mode)
- `--issues` (batch issues mode)
- `--resume` (resume mode)

If combined with any of these, BLOCK with error message.
