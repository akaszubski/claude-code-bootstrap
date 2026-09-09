# Proof artifact — PreToolUseWrite-protect-sensitive.sh

**Date** 2026-09-06 · **Method** live script, real PreToolUse payloads on stdin, decision
parsed from `hookSpecificOutput.permissionDecision`. No mocks.
**Status before this proof**: registered on PreToolUse, contains a block path, **0 recorded
refusals ever** — i.e. the refusing arm was unproven. Issue #1588 had previously found this
guard dead FOUR independent ways.

## Q1 — CONNECTED?  YES
Registered on `PreToolUse` in the user, project and global-template settings surfaces;
sidecar declares `type: lifecycle`; present in `install_manifest.json`.

## Q2 — WORKS AS DESIGNED?  YES, both arms

| Input `tool_input.file_path` | Decision | Arm |
|---|---|---|
| `credentials.json` | **deny** | refusing |
| `server.pem` | **deny** | refusing |
| `app.key` | **deny** | refusing |
| `secrets.yaml` | **deny** | refusing |
| `SECRETS.yaml` (uppercase) | **deny** | refusing — #1588 arm-4 case regression |
| `a.PEM` (uppercase) | **deny** | refusing — #1588 arm-4 case regression |
| `my_private_key` | **deny** | refusing — proves `private.*key` fires |
| `.env` | **ask** | ask class |
| `PROJECT.md` | **ask** | ask class |
| `hello.py` | allow | permitting |
| `docs/ENVIRONMENT.md` | allow | permitting — negative control, does NOT over-match on uppercase |

The permitting arm is not decorative: `docs/ENVIRONMENT.md` is the case-insensitivity
negative control from the #1588 header, and it correctly allows. A guard that denied it
would be over-matching.

## GAP FOUND — canonical SSH private-key filenames are not covered

`DENY_PATTERNS="credentials|secrets|private.*key|\.pem$|\.key$|\.git/"`

| Input | Decision | Expected |
|---|---|---|
| `id_rsa` | **allow** | should be denied |
| `id_ed25519` | **allow** | should be denied |

`id_rsa` and `id_ed25519` are THE canonical OpenSSH private-key filenames and contain
neither "private" nor "key" nor a `.pem`/`.key` extension. `my_private_key` denies, so the
pattern works — it just describes the *words* a private key file might contain rather than
the *category*. Same shape as the #1588 arm-4 defect: enumerate members, miss the member
nobody thought of.

**Severity is MODERATE, not high**: `~/.ssh/**` is independently covered by
`Edit(~/.ssh/**)` in the settings deny list, which per Claude Code's docs governs all
built-in file-editing tools. The exposure is private keys living OUTSIDE `~/.ssh` — a key
in a project directory, `/tmp`, or a deploy folder.

## Correction made during this proof
The first probe used `~/.ssh/id_rsa`, got `allow`, and looked like a failure of the guard.
It was a failure of the PROBE: that path matches no DENY pattern, so `allow` was correct
behaviour. Reading the pattern list before trusting the result is what separated
"guard is broken" from "guard has a narrow gap".

---

# ARM 5 — MCP COVERAGE IS BROKEN (found 2026-09-06)

The hook is registered `matcher: "Write|Edit|MultiEdit|NotebookEdit|mcp__.*"` on BOTH the
project and user surfaces, so it FIRES for MCP editing tools. Line 466 then extracts:

    FILE_PATH=$(echo "$TOOL_USE" | jq -r '.tool_input.file_path // empty')

MCP editors do not send `file_path`. Confirmed against the LIVE tool schemas:
- `mcp__serena__replace_symbol_body` requires `name_path`, **`relative_path`**, `body`
- `mcp__serena__replace_content` requires **`relative_path`**, `needle`, `repl`, `mode`

Measured, with controls:

| Payload | Decision |
|---|---|
| POSITIVE CONTROL — `Write` + `file_path=credentials.json` | **deny** |
| `mcp__serena__replace_symbol_body` + `relative_path=credentials.json` | **allow** |
| `mcp__serena__replace_content` + `relative_path=server.pem` | **allow** |
| `mcp__serena__insert_after_symbol` + `relative_path=secrets.yaml` | **allow** |
| KEY CONTROL — same MCP tool + `file_path=credentials.json` | **deny** |

The key control is what makes this conclusive: the tool NAME is not the problem, the KEY is.
`// empty` makes FILE_PATH the empty string, every pattern misses, and the hook allows.

This is #1588 ARM 2 REPEATING. That arm read `.parameters.file_path`, "a key that appears in
no real Claude Code PreToolUse payload." It was fixed for built-in tools. The identical
defect was never fixed for the MCP tools the matcher explicitly claims to cover.

## Consequence for the hooks-vs-permissions question

MCP coverage was the ONE capability this hook had that `permissions.deny` cannot provide
(`Edit(<path>)` governs built-in file-editing tools only). That capability does not work.
What remains that permissions cannot do: `ask` with a model-visible reason, and telemetry.

For built-in tools `Edit(~/.ssh/**)` is one line, cannot fail open (silence/timeout/malformed
output are all consent for a hook, never for a permission rule), and announces its own
breakage at startup — which is how this session started.

---

## ARM 5 — FIXED (2026-09-06, same day)

`_write_targets_nul()` now shells out to `lib/tool_intent.py`'s `write_targets()` for the
tool-name → path-key mapping, and `match_any_target()` runs the existing `matches_pattern()`
over every extracted target. The extraction is a UNION, not a replacement: the original jq
`file_path` read is untouched and stays target 0, so a degraded host (python3 absent,
`tool_intent` unimportable) keeps full built-in coverage and only loses the added MCP reach.

Re-measured against the live script, same three MCP payloads from the table above:

| Payload | Decision (post-fix) |
|---|---|
| `mcp__serena__replace_symbol_body` + `relative_path=credentials.json` | **deny** |
| `mcp__serena__replace_content` + `relative_path=server.pem` | **deny** |
| `mcp__serena__insert_after_symbol` + `relative_path=secrets.yaml` | **deny** |
| `mcp__serena__replace_content` + `relative_path=src/hello.py` | allow (negative control) |

Built-in behaviour is unchanged (`credentials.json` deny, `.env` ask, `hello.py` allow).
The `id_rsa`/`id_ed25519` gap documented above is untouched by this fix — it is a policy
gap in WHAT is protected, not the extraction defect this arm closed. This proof should no
longer be read as recording an open MCP-coverage defect; see `CHANGELOG.md` [Unreleased]
and `docs/HOOKS.md` for the current state.
