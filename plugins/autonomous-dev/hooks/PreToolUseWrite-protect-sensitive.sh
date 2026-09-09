#!/usr/bin/env bash
# PreToolUseWrite hook for autonomous-dev v2.0
# Guards sensitive files: refuses writes an agent has no business making, and
# prompts the human for the files a human legitimately edits.
#
# Issue #1587 — refusing and recording are ONE act.
#
# This hook produced a valid deny payload on two paths and recorded nothing,
# so every refusal it made was invisible in .claude/logs/hook-blocks.jsonl.
# The fix is deliberately NOT "add a logging call next to each heredoc" —
# that reproduces the defect class, where refusing and recording are two acts
# and the second is forgettable. `deny_and_record` below is the ONLY thing in
# this file that emits a refusing payload, so no path can refuse without
# recording. That property is why the function keeps its #1587 name even
# though it now emits `ask` as well as `deny`: the name is pinned in the
# #1588 refusal-sink ratchet's SANCTIONED_SINKS and REFUSAL_EMITTER_NAMES,
# and renaming it would mean editing a ratchet's pinned vocabulary as a side
# effect of a policy change.
#
# Recording delegates to lib/hook_telemetry.py's log_block_event() rather than
# appending JSON from shell: the row schema, the JSON escaping, the flock
# line-integrity guard (Issue #992), the reason cap, the HOOK_TELEMETRY_DISABLED
# rollback switch and the read-only-FS stderr fallback then live in exactly one
# place instead of two that drift. python3 is already a hard dependency of every
# hook registration in this repo, so this adds no new dependency — and the
# interpreter is spawned only on the refusal path, never on the allow path.
#
# Telemetry is strictly subordinate to enforcement. The decision payload is
# written to stdout BEFORE any recording is attempted, and every recording
# failure mode (python3 absent, hook_telemetry unimportable, unwritable log,
# recorder raising) degrades to "refused but unrecorded" — never to "allowed".
#
# Issue #1588 — the guard was dead three independent ways.
#
#   1. NOT REGISTERED. install_manifest.json shipped it to every consumer repo
#      while no settings surface bound it to any lifecycle event, so it had
#      never run in production. It is now registered on PreToolUse in every
#      settings surface that registers unified_pre_tool.py, and its sidecar
#      declares type "lifecycle" so generate_hook_config.py keeps it there.
#   2. WRONG INPUT KEY. It read `.parameters.file_path`, a key that appears in
#      no real Claude Code PreToolUse payload. Against a live write the
#      variable was empty, every pattern missed, and the hook fell through to
#      allow. It now reads `.tool_input.file_path`.
#   3. WRONG ENVELOPE. It emitted a bare top-level `permissionDecision`, which
#      Claude Code honours neither as `hookSpecificOutput.permissionDecision`
#      (unified_pre_tool.py:6302) nor as the legacy top-level
#      `{"decision": "block"}` (:6273), so the write proceeded regardless. It
#      now emits the same envelope unified_pre_tool.py emits, on the allow
#      path as well as the refusal path.
#
# Fixing 2 and 3 turns a hook that refused nothing into one that refuses live
# writes everywhere the plugin is installed. That is a POLICY change, and it
# was made deliberately: the single pattern list SPLITS into two classes.
#
#   DENY — credentials, secrets, private keys, .pem, .key, .git/
#          An agent has no business writing these at all.
#   ASK  — .env, .env.*, PROJECT.md
#          A human legitimately edits these. The PROJECT.md rule's own reason
#          text already says "edit PROJECT.md manually", which is a request
#          for a human decision, not a refusal. A blanket deny cannot express
#          "stop the agent, let the human decide" — `ask` can.
#
# An `ask` is a refusal to proceed silently, so it is recorded in
# hook-blocks.jsonl exactly as a deny is, with the ACTUAL decision in
# metadata.decision so triage can separate the two classes.
#
# Issue #1588 arm 4 — the match was CASE-SENSITIVE, so every class above fell
# through on an uppercase spelling: it denied secrets.yaml and allowed
# SECRETS.yaml, denied a.pem and allowed a.PEM, asked on .env and allowed .ENV.
# The deployment target is macOS/APFS, which is case-INSENSITIVE by default, so
# those are not two files that look alike — they are ONE file with two
# spellings. The guard refused a write and then permitted the identical write
# to the identical file, one shift key later. A guard bypassed by pressing
# shift is worse than no guard: it manufactures confidence it has not earned.
#
# The fix removes the category rather than enumerating members. An alternation
# like `SECRETS|Secrets|secrets` is the same defect with more spellings and
# still falls through on `SeCrEtS`; case-insensitive matching cannot. And it is
# applied at ONE match site (`matches_pattern` below) rather than three greps,
# for the same reason `deny_and_record` is one emitter: three sites is three
# chances to fix deny and forget ask, which is this defect reappearing in a new
# place. Case-insensitivity widens only HOW a path is spelled, never WHAT is
# protected — docs/environment.md and docs/ENVIRONMENT.md both still allow,
# and both are asserted.
#
# Issue #1588 remediation cycle 2 — THE FAIL-OPEN CLASS.
#
# Arms 1-4 above are four ways this guard permitted what it claimed to block.
# They share one shape with the two defects fixed here: whenever this hook
# fails to put a VALID decision payload on stdout, Claude Code parses no
# decision and the write PROCEEDS. Silence and malformed output are both
# indistinguishable from consent. So the property below is now structural
# rather than incidental: FROM THE INSTALLATION OF THE EXIT TRAP ONWARD, THE
# HOOK CANNOT EXIT WITHOUT EMITTING A PAYLOAD — AND NOTHING THAT RUNS BEFORE
# THAT POINT CAN FAIL, BECAUSE EVERYTHING BEFORE IT IS EITHER A LITERAL
# ASSIGNMENT OR A FUNCTION DEFINITION.
#
# That claim carries its boundary on purpose. An earlier revision stated it
# unconditionally, in capitals, while 236 lines ran ahead of the trap — one of
# which (`SCRIPT_DIR="$(cd -- "$(dirname -- ...)" && pwd)"`) spawns three
# external commands and dies under `set -e` if any is unreachable, with empty
# stdout and no trap yet installed to notice. The fail-open class this section
# exists to close was sitting inside the comment claiming the class was closed.
# A comment that describes behaviour more confidently than the code delivers is
# precisely how arms 2 and 3 survived for months in this same file, so prose and
# code are now pinned against each other by
# TestIssue1588TrapCoversEveryFallibleCommand, which reads this source and
# refuses ANY fallible construct above the trap — not merely the one that was
# there.
#
#   INSTANCE 1 — UNTRUSTED CONTENT BROKE THE JSON. The reason string embeds
#     FILE_PATH, which is attacker-influenced, and was interpolated RAW into a
#     heredoc. A path carrying a double quote, a backslash, a newline or a
#     control character produced malformed stdout — and the telemetry row was
#     still written, so hook-blocks.jsonl recorded a refusal that never took
#     effect. A guard that lies in your favour is worse than one that is
#     simply off: it manufactures the positive evidence you would use to catch
#     it. This interpolation predates arm 2, but it was UNREACHABLE — with the
#     wrong input key FILE_PATH was always empty and no reason string was ever
#     built. Fixing arm 2 is what made it live, so it belongs here.
#
#   INSTANCE 2 — THE HOOK EMITTED NOTHING. Under `set -euo pipefail` a stdin
#     payload jq cannot parse killed the script at the parse (rc=5, empty
#     stdout) before any payload was written. Not agent-reachable — an agent
#     cannot make Claude Code send non-JSON on hook stdin — and fixed anyway,
#     because a known route to silent permission is a guard that has not been
#     proven to refuse, whether or not an adversary can walk it.
#
# THE FIX IS THE CLASS, NOT THE TWO INSTANCES.
#
#   a. ESCAPING IS DELEGATED, NOT HAND-ROLLED. Every reason — refusing and
#      permitting alike — is rendered into a JSON string literal by
#      `jq -Rs .`, which is total over byte sequences: quotes, backslashes,
#      newlines and control characters all round-trip exactly. Enumerating bad
#      characters is the arm-4 defect in new clothes (a list that still falls
#      through on the member nobody thought of); delegating to a complete
#      escaper cannot have that failure mode. The allow payload is routed
#      through the same escaper even though its reason is currently the empty
#      string, so a later edit that puts content there cannot reintroduce this.
#
#   b. NOTHING IS INTERPOLATED RAW EXCEPT THE DECISION, WHICH IS NEVER
#      TAINTED. The three decision values are internal literals ("deny",
#      "ask", UNDETERMINED_DECISION). No caller can reach them with input.
#
#   c. AN EXIT TRAP MAKES SILENCE IMPOSSIBLE. `_emit_undetermined_on_exit`
#      fires on every exit path and, if no payload has been emitted, emits one
#      through the SAME single emitter. It covers failure modes nobody has
#      enumerated — which is the point, since instance 2 was one nobody had.
#      The trap is installed BEFORE stdin is read, because the failure it must
#      catch happens at the parse.
#
#      IT IS INSTALLED AS EARLY AS IT CAN BE, WHICH IS NOT LINE ONE, AND THE
#      DIFFERENCE IS LOAD-BEARING. Bash executes a script as it reads it; it
#      does NOT parse the whole file first. A trap naming a function defined
#      further down therefore fires as `_emit_undetermined_on_exit: command
#      not found` and produces exactly the silence it was installed to
#      prevent. Measured, not assumed. Under `set -u` the same is true of
#      data: a trap that reads a variable not yet assigned dies half-way
#      through and emits nothing, so every variable on the trap path —
#      DECISION_EMITTED, UNDETERMINED_DECISION, NL, HOOK_NAME, LIB_DIR,
#      TOOL_USE, FILE_PATH, UNRENDERABLE_REASON_JSON — is assigned above the
#      trap.
#
#      So the trap sits immediately after the last function definition, and
#      the region above it was reduced to constructs that CANNOT fail. The one
#      command up there that could — the SCRIPT_DIR/LIB_DIR resolution, which
#      needs `dirname`, `cd` and `pwd` — moved BELOW the trap rather than the
#      trap moving above it, because the trap cannot precede the functions it
#      calls. LIB_DIR is initialised to "" above the trap so the trap path
#      stays `set -u`-safe if the resolution never completes; a resolution
#      that dies then yields the undetermined `ask` with the refusal
#      unrecorded, which is the enforcement-over-telemetry ordering used
#      everywhere else in this file.
#
#   d. THE ENVELOPE IS RENDERED BY printf, NOT BY `jq -n`. A DELIBERATE
#      departure from the reviewed remedy, and the reason is (c): jq is this
#      hook's own hard dependency, so a fallback built ON jq cannot cover jq
#      being unreachable — the trap would fire, the emitter would fail to
#      render, and the hook would exit silently, which is the very class being
#      fixed. printf is a bash builtin and cannot go missing. jq is still what
#      escapes the reason; when it is unreachable the emitter substitutes a
#      CONSTANT pre-escaped reason and still emits a valid, correctly-decided
#      payload. Verified with jq removed from PATH, not assumed.
#
#   e. THE UNDETERMINED CASE IS `ask`, NOT `deny`. Chosen, not defaulted. A
#      hard deny on every payload this hook cannot parse would wedge a session
#      outright if the harness ever changed its payload shape — a real and
#      unbounded cost, paid by the human, for a case that carries no evidence
#      of wrongdoing. `ask` surfaces the anomaly to the human without wedging
#      anything, and still stops the agent proceeding silently, which is the
#      property that actually matters. It is recorded under its own rule
#      (`undetermined_payload`) so triage can tell "I could not read the
#      payload" apart from "an agent tried to write a secret".
#
# The single-emitter property survives all of this: `deny_and_record` remains
# the ONLY producer of a refusing payload, the trap routes through it rather
# than emitting its own, and the allow tail hardcodes the literal "allow" so
# it cannot become a refusal surface by edit.
#
# Issue #1588 arm 5 — ARM 2 REPEATING, FOR A DIFFERENT TRANSPORT.
#
# This hook's matcher is `Write|Edit|MultiEdit|NotebookEdit|mcp__.*` on every
# settings surface that binds it, so it FIRES for MCP editing tools. It then
# read a single key, `.tool_input.file_path` — and MCP editors never send that
# key. `mcp__serena__replace_symbol_body` and `mcp__serena__replace_content`
# both carry their target under `relative_path`. Measured against the live
# script: `Write` + file_path=credentials.json denied, while the SAME path
# under `relative_path` on three different serena writers allowed. The key
# control is conclusive — feeding an MCP tool NAME together with a `file_path`
# key still denied, so the tool name was never the problem. `// empty` left
# FILE_PATH empty, every pattern missed, and the guard permitted every MCP
# write to every protected path it claims to block.
#
# That is arm 2 with one word changed. Arm 2 read a key that appears in no real
# payload; arm 5 read a key that appears in no real MCP payload. Fixing arm 2
# for the built-in transports and stopping there is what left this open.
#
# THE FIX DELEGATES RATHER THAN ENUMERATING. Adding `relative_path` to the jq
# expression would be arm 4's defect in new clothes: a list that still falls
# through on the next server that names its argument `path`, `target_file` or
# `uri`. `lib/tool_intent.py`'s `write_targets()` already owns the tool-name ->
# path-key mapping for every transport in this repo, and is already the
# canonical answer to "is this a write, and to what?" at the Issue #1435 hard
# floor. So this file delegates to it exactly as it already delegates escaping
# to `jq -Rs .` and the telemetry row schema to `lib/hook_telemetry.py`. A new
# MCP writer is covered by registering it once, there — not by editing a regex
# here that nobody will remember exists.
#
# IT IS A UNION, NOT A REPLACEMENT, AND THAT IS THE LOAD-BEARING CHOICE. The
# jq `file_path` extraction is untouched and its result is always target 0. Two
# reasons, both measured rather than assumed:
#
#   * DEGRADATION MUST NOT REACH THE BUILT-INS. python3 absent, tool_intent
#     unimportable, or the classifier raising all yield zero extra targets. The
#     jq value is still there, so a degraded host loses MCP coverage and keeps
#     every built-in refusal. The reverse — delegating outright — would make a
#     missing interpreter a fail-open for `Write` itself, which is the class
#     this whole file exists to close.
#   * A PAYLOAD WITH NO `tool_name` MUST NOT BECOME AN ALLOW. `write_targets`
#     returns [] for an empty tool name, by design. Delegating outright would
#     therefore have turned "I cannot attribute this call to a tool" into
#     silent permission — a NEW fail-open, invented while closing an old one.
#
# The union can only ever ADD a refusal; it cannot turn any decision this hook
# reached before into an allow. The consequence, stated rather than hidden: a
# `Read` payload carrying a protected `file_path` still denies, as it did
# before this change. That is over-refusal, not fail-open, and it is
# unreachable in production because `Read` is not in this hook's matcher.
# Narrowing it would mean making the guard SEE FEWER paths inside a change
# whose entire purpose is making it see more.
#
# KNOWN GAP, RECORDED HERE AND DELIBERATELY NOT FIXED HERE: DENY_PATTERNS does
# not match `id_rsa` or `id_ed25519`, the canonical OpenSSH private-key
# filenames. Measured — both ALLOW, while `my_private_key` DENIES, so the
# `private.*key` pattern works and the gap is in its coverage, not its
# matching. That is a POLICY gap in WHAT is protected; arm 5 is an extraction
# defect in WHICH PATHS ARE SEEN. Widening the pattern list inside this change
# would mix the two and make the regression proof below unattributable.
# `~/.ssh/**` is independently covered by `Edit(~/.ssh/**)` in the settings
# deny list, so the gap is not unguarded in the meantime.

set -euo pipefail

# EVERY assignment from here down to the `trap` line is a literal — no command
# substitution, no pipeline, no external command — so none of them can fail
# under `set -euo pipefail`. That is what makes the pre-trap region safe, and
# it is enforced by test rather than by this comment: see (c) in the header.
HOOK_NAME="PreToolUseWrite-protect-sensitive.sh"

# Resolved BELOW the trap, because resolving it needs `dirname`, `cd` and
# `pwd`, and a failure there must produce the undetermined `ask` rather than
# silence. Initialised here so the trap path can read it under `set -u` even
# when the resolution never ran. Empty means the recorder cannot import
# hook_telemetry and the refusal degrades to unrecorded — never to allowed.
LIB_DIR=""

# A real newline, for reason strings. The reasons used to carry two-character
# `\n` sequences that read as newlines only because they were pasted into JSON
# unescaped — the same raw interpolation that IS instance 1. Now that reasons
# are escaped properly, a literal backslash-n would reach the model as the two
# characters `\` and `n`, so the newlines have to be real.
NL=$'\n'

# Set the moment any payload reaches stdout. The exit trap reads it to decide
# whether the hook is about to exit having decided nothing.
DECISION_EMITTED=0

# Pre-initialised so the exit trap can reference them under `set -u` even when
# it fires before stdin has been read — which is exactly when instance 2 bites.
TOOL_USE=""
FILE_PATH=""

# The decision emitted when the hook cannot determine one. See (e) above for
# why this is `ask` and not `deny`.
UNDETERMINED_DECISION="ask"

# A pre-escaped, CONSTANT JSON string literal, used only when jq cannot be
# reached to escape the real reason — see (d). It contains no interpolation by
# construction, so it is valid JSON without needing an escaper.
UNRENDERABLE_REASON_JSON='"🔒 This write was stopped, but its reason could not be rendered (jq unavailable). Treat it as unexplained and inspect the target path manually."'

# The permitting payload's reason. A named variable rather than an inline
# literal so it goes through the same escaper the refusing reasons do. The
# point of escaping an empty string is not today's empty string: it is that
# the NEXT edit, the one that puts a path or a rule name in here, is escaped
# without anyone having to remember.
ALLOW_REASON=""

# Patterns an agent must never write. Refused outright.
DENY_PATTERNS="credentials|secrets|private.*key|\.pem$|\.key$|\.git/"

# Patterns a human legitimately edits. The agent is stopped and the human is
# asked, rather than refused. See the header for why these moved out of DENY.
# Two named lists rather than one, because they carry different reason text
# and different triage rules.
ASK_ENV_PATTERNS="\.env$|\.env\..*"
ASK_PROJECT_PATTERNS="PROJECT\.md$"

# The ONLY pattern-match site in this file. Every decision class routes through
# it, so case handling cannot be applied to one class and forgotten on another.
# `-i` is load-bearing, not cosmetic: see the arm-4 note in the header. A
# here-string rather than a pipe so `set -o pipefail` has no pipeline to
# observe.
#
# $1 pattern — extended regex
# Returns 0 when FILE_PATH matches, 1 otherwise.
matches_pattern() {
  grep -qiE "$1" <<<"$FILE_PATH"
}

# Ask the classifier which paths this tool call would WRITE, and emit them
# NUL-delimited on stdout.
#
# Issue #1588 arm 5 — WHICH PATHS ARE SEEN. See the arm-5 note in the header.
# The whole point of this function is that it does NOT know any key names:
# ``tool_intent.write_targets`` owns the tool-name -> path-key mapping, the
# same way ``jq -Rs .`` owns escaping and ``hook_telemetry`` owns the row
# schema. Adding ``relative_path`` to a jq expression here would be arm 4 in
# new clothes — a list that still falls through on the next server that says
# ``path`` or ``target_file``.
#
# NUL rather than newline because a target may legitimately CONTAIN a newline;
# the hostile-path tests feed exactly that, and a line-delimited reader would
# split one path into two and name neither correctly in the reason.
#
# TOTALLY non-fatal by construction. python3 absent, tool_intent unimportable,
# a malformed payload, an interpreter that raises — every one of them yields
# empty stdout here, and the caller still has the jq-extracted ``file_path``.
# Losing MCP coverage on a degraded host is acceptable; losing built-in
# coverage is not, which is why this AUGMENTS the jq extraction rather than
# replacing it.
#
# Reads TOOL_USE and LIB_DIR. Echoes zero or more NUL-terminated paths.
_write_targets_nul() {
  printf '%s' "$TOOL_USE" \
    | PYTHONPATH="$LIB_DIR${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import json
import sys

try:
    import tool_intent

    payload = json.loads(sys.stdin.read())
    tool_name = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    out = sys.stdout.buffer
    for target in tool_intent.write_targets(tool_name, tool_input):
        if isinstance(target, str) and target:
            out.write(target.encode("utf-8", "surrogateescape"))
            out.write(b"\x00")
    out.flush()
except Exception:
    pass
' 2>/dev/null || true
}

# Test one pattern against EVERY target, not just the first.
#
# ``write_targets`` returns a LIST, so a decision made from ``TARGETS[0]``
# would be a guard scoped to the first element — the same shape as a guard
# scoped to the instance that prompted it. Any target matching is a refusal.
#
# It calls ``matches_pattern`` rather than matching itself, so this file still
# has exactly ONE pattern-match site. Three sites is three chances to fix deny
# and forget ask; that reasoning does not weaken just because the second site
# would be a loop.
#
# On a match, FILE_PATH is left pointing at the OFFENDING target, so the reason
# and the telemetry row name the path that actually tripped the rule. On no
# match it is restored to PRIMARY_TARGET, so a later rule sees the same value
# an earlier rule did.
#
# $1 pattern — extended regex
# Returns 0 when any target matches, 1 otherwise.
match_any_target() {
  local pattern="$1"
  local candidate
  for candidate in "${TARGETS[@]}"; do
    if [[ -z "$candidate" ]]; then
      continue
    fi
    FILE_PATH="$candidate"
    if matches_pattern "$pattern"; then
      return 0
    fi
  done
  FILE_PATH="$PRIMARY_TARGET"
  return 1
}

# Render an arbitrary byte string as a valid JSON string literal.
#
# The whole of instance 1 in one function. `jq -Rs .` is TOTAL over byte
# sequences — quotes, backslashes, newlines, tabs and control characters are
# all escaped, and the original bytes round-trip exactly — so no caller has to
# know which characters are dangerous. That is the property a hand-rolled
# substitution cannot have, and enumerating characters is how arm 4 got here.
#
# When jq is unreachable the CONSTANT pre-escaped literal is substituted rather
# than the raw text. The reason degrades; the payload's validity does not. See
# (d) in the header for why this cannot itself depend on jq.
#
# $1 reason — arbitrary text, possibly attacker-influenced
# Echoes a JSON string literal (including its surrounding quotes).
render_reason_json() {
  local rendered
  rendered=$(printf '%s' "$1" | jq -Rs . 2>/dev/null) || rendered=""
  if [[ -z "$rendered" ]]; then
    rendered="$UNRENDERABLE_REASON_JSON"
  fi
  printf '%s' "$rendered"
}

# Append one hook-blocks.jsonl row for a refusal. Never fatal, never noisy on
# success. Called only from deny_and_record.
#
# $1 decision — "deny" or "ask"; the decision actually emitted
# $2 reason   — the exact model-visible reason string that was emitted
# $3 rule     — which refusal rule fired, for triage
_record_block() {
  local decision="$1"
  local reason="$2"
  local rule="$3"
  local repo_root tool_name session_id

  if ! command -v python3 >/dev/null 2>&1; then
    printf '[hook-telemetry] %s: refusal unrecorded (python3 unavailable)\n' \
      "$HOOK_NAME" >&2
    return 0
  fi

  # Anchor the log at the repo root, not the invoking process's cwd. Without
  # this a write issued from a subdirectory writes <subdir>/.claude/logs/
  # instead of the repo's. Same resolution order the settings templates use.
  repo_root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || true)}"
  # `|| true` on both: TOOL_USE is not guaranteed to be JSON at all on the
  # undetermined path, and a recorder that died trying to read it would take
  # the refusal down with it.
  tool_name=$(printf '%s' "$TOOL_USE" | jq -r '.tool_name // ""' 2>/dev/null || true)
  session_id=$(printf '%s' "$TOOL_USE" | jq -r '.session_id // ""' 2>/dev/null || true)

  PYTHONPATH="$LIB_DIR${PYTHONPATH:+:$PYTHONPATH}" python3 - \
    "$HOOK_NAME" "$reason" "$rule" "$FILE_PATH" "$tool_name" "$session_id" \
    "$repo_root" "$decision" <<'PY' || true
import sys
from pathlib import Path

(
    _,
    hook_name,
    reason,
    rule,
    file_path,
    tool_name,
    session_id,
    repo_root,
    decision,
) = sys.argv

try:
    from hook_telemetry import log_block_event
except Exception as exc:  # stale install / missing lib
    sys.stderr.write(
        "[hook-telemetry] %s: refusal unrecorded "
        "(hook_telemetry unimportable: %s)\n" % (hook_name, exc)
    )
    raise SystemExit(0)

try:
    log_block_event(
        hook_name=hook_name,
        # "dict" == a printed JSON envelope, and a member of
        # scripts/hook_perf_report.py BLOCK_SHAPES, so this refusal is
        # counted as a block by the existing report. That applies to "ask"
        # rows too: BLOCK_SHAPES keys off the PAYLOAD SHAPE, not the decision
        # value, so an ask lands in the block counts alongside a deny. It is
        # a refusal to proceed silently, so that is the intended reading —
        # and metadata.decision below is what lets triage separate them.
        decision_shape="dict",
        reason=reason,
        metadata={
            "tool_name": tool_name,
            "file_path": file_path,
            "rule": rule,
            # Which decision was actually emitted: "deny" or "ask".
            "decision": decision,
            # Issue #1588 arm 3: this hook emitted a bare top-level
            # permissionDecision, which Claude Code ignores. It now emits the
            # documented envelope. Recording which variant was emitted keeps
            # the fact in the DATA, so a future regression shows up in triage
            # rather than only in prose.
            "envelope": "hookSpecificOutput.permissionDecision",
        },
        session_id=session_id or None,
        start_dir=Path(repo_root) if repo_root else None,
    )
except Exception as exc:  # log_block_event is documented never to raise
    sys.stderr.write(
        "[hook-telemetry] %s: refusal unrecorded (recorder failed: %s)\n"
        % (hook_name, exc)
    )

raise SystemExit(0)
PY
}

# The ONLY producer of a refusing payload in this file. Emits the decision and
# records it as a single indivisible act, then exits. Parameterised over the
# decision so that adding the "ask" class did NOT add a second emitter — a
# second emitter is the separable surface #1587 exists to prevent, and it
# would be separable for exactly the same reason whether it emitted deny or
# ask. The undetermined-payload path added in remediation cycle 2 routes here
# too, for the same reason.
#
# The envelope is rendered by printf and the reason by render_reason_json, so
# the ONLY value interpolated raw is $decision — an internal literal that no
# input can reach. See (a), (b) and (d) in the header.
#
# $1 decision — "deny" or "ask"
# $2 reason   — model-visible reason; may contain ANY bytes, including a
#               path an attacker chose
# $3 rule     — which refusal rule fired, for triage
deny_and_record() {
  local decision="$1"
  local reason="$2"
  local rule="$3"
  local reason_json

  # Claimed before the payload is written, not after: if anything below
  # fails, the exit trap must not conclude that nothing was decided and
  # start a second emission on top of a half-written one.
  DECISION_EMITTED=1

  reason_json=$(render_reason_json "$reason")

  # Refuse FIRST. Nothing in the recording path can suppress this.
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"%s","permissionDecisionReason":%s}}\n' \
    "$decision" "$reason_json"

  _record_block "$decision" "$reason" "$rule" || true
  exit 0
}

# Fires on EVERY exit path. If the hook is about to exit having emitted no
# payload, it emits one — because an exit with empty stdout is a decision to
# permit, made by omission. This is the structural half of the cycle-2 fix:
# instance 2 was a failure mode nobody had enumerated, so the guard cannot be
# a list of the ones we now know about.
#
# It routes through deny_and_record rather than emitting its own payload, so
# the single-emitter property holds and the undetermined case is recorded like
# any other refusal.
_emit_undetermined_on_exit() {
  local rc=$?
  if [[ "$DECISION_EMITTED" -eq 1 ]]; then
    return 0
  fi
  deny_and_record \
    "$UNDETERMINED_DECISION" \
    "🔐 This hook could not determine a decision for this write (it exited ${rc} before emitting one).${NL}${NL}The payload it received could not be read, so the write has NOT been checked against the protected-path rules. Approve only if you are sure this write is safe." \
    "undetermined_payload"
}

# Installed BEFORE stdin is read, and before the first command in this file
# that can fail. Instance 2 was a death at the jq parse below; the remediation
# that followed found a second, earlier route — 236 lines of setup ran ahead of
# this line, including a SCRIPT_DIR resolution that dies under `set -e` when
# `dirname` is unreachable, emitting nothing. Everything above is now literal
# assignment and function definition; everything that can fail is below.
#
# This is as early as the trap can go: bash executes as it reads, so a trap
# installed above `_emit_undetermined_on_exit` would fire as "command not
# found" and emit the silence it exists to prevent. See (c) in the header.
trap _emit_undetermined_on_exit EXIT

# Sibling lib/ in both layouts: plugins/autonomous-dev/{hooks,lib} in source,
# .claude/{hooks,lib} when deployed. Deliberately still fatal on failure — it
# is now fatal INTO the trap, which converts it to an `ask`, instead of fatal
# into an empty stdout that Claude Code reads as consent.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/../lib"

TOOL_USE=$(cat)
# Issue #1588 arm 2: `.tool_input.file_path` is the field Claude Code actually
# sends on PreToolUse. The previous `.parameters.file_path` matched nothing.
# A parse failure here is deliberately left fatal: the trap converts it into
# the undetermined `ask` rather than into a fall-through allow.
FILE_PATH=$(echo "$TOOL_USE" | jq -r '.tool_input.file_path // empty')

# Issue #1588 arm 5 — the set of paths under consideration. See the arm-5 note
# in the header for why this is a UNION rather than a replacement.
#
# Element 0 is the jq-extracted file_path and is ALWAYS present, possibly as
# the empty string. That is deliberate on two counts: it keeps built-in
# coverage identical on a host where the classifier cannot run, and it keeps
# `"${TARGETS[@]}"` safe to expand under `set -u` with no special-casing.
TARGETS=("$FILE_PATH")
while IFS= read -r -d "" _extra_target; do
  if [[ -n "$_extra_target" && "$_extra_target" != "$FILE_PATH" ]]; then
    TARGETS+=("$_extra_target")
  fi
done < <(_write_targets_nul)

# The path the reason text and the telemetry row name by default: the first
# non-empty target. For a built-in write that is the file_path, unchanged. For
# an MCP write, where file_path does not exist, it is the classifier's target
# instead of the empty string the old code carried.
for _candidate in "${TARGETS[@]}"; do
  if [[ -n "$_candidate" ]]; then
    FILE_PATH="$_candidate"
    break
  fi
done
PRIMARY_TARGET="$FILE_PATH"

# DENY class — checked first, and across ALL targets before any ASK rule is
# consulted, so a call touching both a denied and a merely-queried path is
# refused rather than prompted.
if match_any_target "$DENY_PATTERNS"; then
  deny_and_record \
    "deny" \
    "🔒 Cannot write to sensitive file: ${FILE_PATH}${NL}${NL}Protected patterns: .git/, credentials, secrets, private keys, .pem, .key" \
    "sensitive_file_pattern"
fi

# ASK class — .env and .env.* are routine human edits, so the human decides.
if match_any_target "$ASK_ENV_PATTERNS"; then
  deny_and_record \
    "ask" \
    "🔐 ${FILE_PATH} holds environment configuration.${NL}${NL}Editing it is normal human work but not an agent's call. Approve if you intended this write." \
    "human_editable_pattern"
fi

# ASK class — PROJECT.md drives alignment validation. Automatic modification
# would compromise it; a human edit is exactly what the rule always asked for.
if match_any_target "$ASK_PROJECT_PATTERNS"; then
  deny_and_record \
    "ask" \
    "🔐 PROJECT.md is protected${NL}${NL}To update project goals/scope/constraints, edit PROJECT.md manually.${NL}Automatic modifications would compromise alignment validation." \
    "project_md_protected"
fi

# Allow other files. Deliberately records nothing — a recorder that also fired
# on allows would corrupt every count derived from the block log. Same envelope
# AND the same renderer as the refusal path: two divergent output shapes in one
# file is the arm-3 defect, and two divergent ESCAPING rules is instance 1, so
# fixing only the refusing one would leave each half-present.
#
# The decision is the hardcoded literal "allow" rather than a variable, so this
# site cannot become a second refusing emitter by edit.
ALLOW_REASON_JSON=$(render_reason_json "$ALLOW_REASON")
DECISION_EMITTED=1
printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":%s}}\n' \
  "$ALLOW_REASON_JSON"
