---
covers:
  - plugins/autonomous-dev/hooks/unified_pre_tool.py
  - plugins/autonomous-dev/config/auto_approve_policy.json
---

# MCP Auto-Approval for Tool Calls

> **Status: the approval/retry subsystem described below was deleted and never ran.**
> The modules named in this document were built, tested, shipped to five consumer
> repositories, and never once executed — measured UNREACHED by the reachability
> ratchet, and zero executions across 541,492 activity-log lines. What enforces
> tool permissions today is Claude Code's native rules (4 allow, 61 deny) plus
> `hooks/unified_pre_tool.py` (167 refusals in two days). Retained as design
> history; do not read it as a description of running code.


**Version**: v3.40.0 (Permissive Mode with Blacklist-First Security)
**Last Updated**: 2025-12-09
**Status**: Opt-in feature (disabled by default, requires explicit enablement)
**GitHub Issue**: #73 (original), #TBD (main conversation support)

---

## Table of Contents

- [Overview](#overview)
- [What's New in v3.38.0](#whats-new-in-v3380)
- [Why MCP Auto-Approval?](#why-mcp-auto-approval)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Security Model](#security-model)
- [How It Works](#how-it-works)
- [Policy File Reference](#policy-file-reference)
- [Troubleshooting](#troubleshooting)
- [For Contributors](#for-contributors)
- [Architecture](#architecture)

---

## DEPRECATION NOTICE (Issue #211)

**Status**: The standalone `auto_approve_tool.py` hook has been **archived** as of 2026-01-09.

**Reason**: Consolidated into unified security architecture for better maintainability.

**Migration**:
- All auto-approval functionality now provided by `unified_pre_tool.py` (Layer 4: Batch Permission Approver)
- Enable with `MCP_AUTO_APPROVE=true` (same as before)
- No configuration changes required
- Same security guarantees and features

**What Changed**:
- Old: Standalone `auto_approve_tool.py` hook
- New: Layer 4 of unified `unified_pre_tool.py` hook (4-layer security architecture)

**Benefits of Consolidation**:
- Single entry point for all pre-tool validation
- Consistent validation order (sandbox → MCP security → agent auth → batch approval)
- Easier to maintain and extend
- Better defense-in-depth with explicit layers

**See**: `plugins/autonomous-dev/hooks/archived/README.md` for complete deprecation documentation and functionality preservation details.

**For Users**: No action required. Auto-approval continues to work as documented below.

---

## Overview

**MCP Auto-Approval** is an opt-in feature that automatically approves MCP (Model Context Protocol) tool calls from both **main conversation** and **subagent workflows**. This eliminates the need for manual approval prompts for trusted operations, creating a seamless development experience.

**Implementation**: Layer 4 of the unified `unified_pre_tool.py` hook (previously standalone `auto_approve_tool.py`).

**Key Benefits**:
- **Zero Interruptions**: No manual approval prompts for trusted operations
- **Flexible Modes**: Auto-approve everywhere or only in subagents
- **Security**: 5 layers of defense-in-depth validation (6 in subagent mode)
- **Performance**: < 5ms validation overhead per tool call
- **Audit Trail**: Every approval/denial logged for compliance
- **Circuit Breaker**: Auto-disable after 10 consecutive denials (prevents runaway automation)

**Typical Workflows**:

**Everywhere Mode** (default when enabled):
```
Main conversation:
User: "what github issues should I work on next"
Claude: [Bash: gh issue list] → [AUTO-APPROVED] → Shows issues

Subagent workflow:
User → /implement → researcher agent → [Bash: pytest] → [AUTO-APPROVED] → ...
```

**Subagent-Only Mode** (legacy behavior):
```
Main conversation:
User: "what github issues should I work on next"
Claude: [Bash: gh issue list] → [PROMPT: Approve tool use?] → User approves

Subagent workflow:
User → /implement → researcher agent → [Bash: pytest] → [AUTO-APPROVED] → ...
```

---

## What's New in v3.40.0

**Permissive Mode**: Policy switched from whitelist-first to blacklist-first approach.

**Changes**:
- **New policy model**: `"mode": "blacklist"` - approve everything by default, block only dangerous patterns
- **Simplified config**: No more adding every safe command to whitelist
- **Zero friction**: All standard dev commands auto-approved without configuration
- **Security focus**: Comprehensive blacklist covers dangerous patterns (rm -rf, sudo, force push, etc.)

**Previous approach (v1.x)**:
```
Whitelist: pytest*, git status, ls*, cat*, ...  (100+ patterns)
Blacklist: rm -rf*, sudo*, ...
Logic: Deny by default, approve if whitelisted
Problem: Every new command required adding to whitelist
```

**New approach (v2.0)**:
```
Whitelist: ["*"]  (approve everything)
Blacklist: rm -rf*, sudo*, git push --force*, ...  (dangerous patterns)
Logic: Approve by default, deny if blacklisted
Benefit: Zero friction for legitimate dev work
```

**Migration**: Automatic. Existing users get the new permissive behavior immediately.

---

## Why MCP Auto-Approval?

### The Problem

Claude Code 2.0 introduced MCP (Model Context Protocol) for enhanced tool integration. However, by default, every tool call from a subagent requires manual approval:

```
Researcher agent: "I'll run pytest tests/unit/"
[PROMPT] Approve Bash tool use for command: pytest tests/unit/? (y/n)
User: y

Researcher agent: "I'll check git status"
[PROMPT] Approve Bash tool use for command: git status? (y/n)
User: y

Researcher agent: "I'll read the test file"
[PROMPT] Approve Read tool use for file: tests/unit/test_foo.py? (y/n)
User: y

... (50+ prompts per /implement run)
```

This defeats the purpose of autonomous development - the user becomes a "permission clicker" instead of focusing on creative work.

### The Solution

MCP Auto-Approval implements **defense-in-depth validation** to safely auto-approve trusted operations:

**Core Security Layers** (all modes):
1. **User Consent**: Must explicitly opt-in via `MCP_AUTO_APPROVE=true`
2. **Tool Whitelist**: Only approved tools (Bash, Read, Write, Grep, etc.)
3. **Command/Path Validation**: Whitelist/blacklist enforcement (e.g., allow `gh issue list`, deny `rm -rf`)
4. **Audit Logging**: Full trail of every approval/denial
5. **Circuit Breaker**: Auto-disable after 10 consecutive denials

**Additional Layer in Subagent Mode**:
6. **Agent Whitelist** (subagent_only mode): Only trusted agents can auto-approve (researcher, planner, test-master, implementer, reviewer, doc-master). In everywhere mode, all agents are trusted.

**Result**: Zero prompts for trusted operations, manual approval for dangerous operations, full audit trail for compliance.

---

## Quick Start

### Step 1: Configure Claude Code Permissions

Add to `~/.claude/settings.json` (user-level) for auto-approval of all tools:

```json
{
  "permissions": {
    "allow": [
      "Bash(:*)",
      "Read(**)",
      "Edit(**)",
      "Glob",
      "Grep",
      "NotebookEdit",
      "Task",
      "WebFetch",
      "WebSearch",
      "TodoWrite",
      "ExitPlanMode",
      "BashOutput",
      "KillShell",
      "AskUserQuestion",
      "Skill",
      "SlashCommand",
      "EnterPlanMode",
      "AgentOutputTool",
      "mcp__"
    ],
    "deny": [
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(~/.ssh/**)",
      "Read(~/.aws/**)",
      "Read(./secrets/**)",
      "Read(**/credentials/**)",
      "Edit(~/.ssh/**)",
      "Edit(~/.aws/**)",
      "Edit(//etc/**)",
      "Edit(//usr/**)",
      "Edit(//System/**)",
      "Bash(rm -rf /)",
      "Bash(rm -rf ~)",
      "Bash(sudo:*)",
      "Bash(chmod 777:*)",
      "Bash(eval:*)",
      "Bash(dd:*)",
      "Bash(mkfs:*)",
      "Bash(shutdown:*)",
      "Bash(reboot:*)"
    ],
    "ask": []
  }
}
```

**Permission Format Reference** (from [official Claude Code docs](https://code.claude.com/docs/en/settings)):

| Tool | Format | Example |
|------|--------|---------|
| Bash (all) | `Bash(:*)` | Allows all shell commands |
| Bash (prefix) | `Bash(npm run:*)` | Allows `npm run test`, `npm run build`, etc. |
| Read (all) | `Read(**)` | Allows reading any file |
| Read (path) | `Read(./src/**)` | Allows reading files in src/ |
| Edit (all) | `Edit(**)` | Allows writing AND editing any file — see note below |
| Other tools | `Write`, `Glob`, `Grep`, `WebFetch` | Just the tool name |
| MCP tools | `mcp__` | Prefix for all MCP server tools |

**Path-scoped file rules: use `Edit(path)`, never `Write(path)` (Issue #1409).**
Claude Code checks file permissions against `Edit(path)` and `Read(path)` rules
only. A path rule written for `Write`, `NotebookEdit`, `Glob`, or the legacy
`MultiEdit` is accepted and warned about at startup, but never consulted — so
`Write(docs/**)` grants and `Write(~/.ssh/**)` denies are both no-ops. One
`Edit(path)` rule governs Write, Edit and NotebookEdit alike. A **bare** tool
name with no parentheses (`"Write"`) is different: it matches at the tool level
everywhere, is not warned about, and is the correct way to grant or deny a whole
tool.

**Important**: Claude Code uses **prefix matching** for Bash, not regex. Use `:*` at the end for wildcards.

**Sources**:
- [Claude Code Settings - Official Docs](https://code.claude.com/docs/en/settings)
- [ggrigo/claude-code-tools - SETTINGS_JSON_GUIDE.md](https://github.com/ggrigo/claude-code-tools/blob/main/docs/SETTINGS_JSON_GUIDE.md)
- [Claude Code Built-in Tools Reference](https://www.vtrivedy.com/posts/claudecode-tools-reference)

### Step 2: Enable Auto-Approval Environment Variable

Add to `.env` file in your project root:

```bash
# Enable MCP auto-approval everywhere (main conversation + subagents)
MCP_AUTO_APPROVE=true

# OR: Only auto-approve in subagent workflows (legacy mode)
# MCP_AUTO_APPROVE=subagent_only
```

### Step 3: Run /implement

```bash
# First run - you'll see consent prompt
/implement "Add user authentication feature"

# On first subagent tool call, you see:
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║  🚀 MCP Auto-Approval for Subagent Tool Calls                ║
║                                                              ║
║  Automatic tool approval enabled for trusted operations:    ║
║                                                              ║
║    ✓ Trusted agents: researcher, planner, implementer, ...  ║
║    ✓ Safe commands: pytest, git status, ls, cat, grep, ...  ║
║    ✓ Project files only (no /etc, /var, /root access)       ║
║    ✓ Dangerous commands blocked (rm -rf, sudo, eval, ...)   ║
║                                                              ║
║  HOW TO OPT OUT:                                            ║
║                                                              ║
║  Remove or set to false in .env file:                       ║
║    MCP_AUTO_APPROVE=false                                   ║
║                                                              ║
║  See docs/TOOL-AUTO-APPROVAL.md for details                 ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

Do you want to enable automatic tool approval? (Y/n):

# Choose Y (default) or n
# Your choice is saved in ~/.autonomous-dev/user_state.json
```

### Step 4: Enjoy Zero-Interruption Workflow

After consent, all trusted operations are auto-approved:

```
Researcher agent invokes Bash: pytest tests/unit/
[AUTO-APPROVED] ✓ (whitelist match: pytest*)

Implementer agent invokes Write: /path/to/project/src/auth.py
[AUTO-APPROVED] ✓ (project directory, trusted agent)

Security-auditor agent invokes Bash: rm -rf /tmp/sensitive
[DENIED] ✗ (blacklist match: rm -rf*, manual approval required)
```

---

## Configuration

### Settings Templates (NEW in v3.38.0)

Choose the template that matches your security/convenience preference:

| Template | Description | Use When |
|----------|-------------|----------|
| **settings.autonomous-dev.json** | Full auto-approval with layered security (RECOMMENDED) | You want zero prompts with defense-in-depth |
| **settings.strict-mode.json** | Vibe coding with full enforcement | You want auto-orchestration on natural language |
| **settings.permission-batching.json** | 80% prompt reduction, batches writes | You want some oversight on writes |
| **settings.granular-bash.json** | Paranoid mode with explicit command whitelist | You want full control over every bash command |
| **settings.local.json** | Basic auto-approval | Simple setup with sensible defaults |

**Quick Setup** (copy to your project):
```bash
# Recommended: Full auto-approval with layered security
cp plugins/autonomous-dev/templates/settings.autonomous-dev.json .claude/settings.local.json

# Alternative: Paranoid mode with explicit bash whitelisting
cp plugins/autonomous-dev/templates/settings.granular-bash.json .claude/settings.local.json

# Alternative: Permission batching (80% reduction, still prompts for writes)
cp plugins/autonomous-dev/templates/settings.permission-batching.json .claude/settings.local.json
```

**Template Features Comparison**:

| Feature | autonomous-dev | strict-mode | permission-batching | granular-bash |
|---------|---------------|-------------|---------------------|---------------|
| Native `permissions` block | ✅ | ✅ | ✅ | ✅ |
| `mcp__` prefix for MCP tools | ✅ | ✅ | ✅ | ✅ |
| `disableBypassPermissionsMode` | ❌ | ✅ | ❌ | ✅ |
| `ask` level for specific tools | ✅ | ❌ | ✅ | ✅ |
| Granular bash patterns | ❌ | ❌ | ❌ | ✅ |
| PreToolUse hook | ✅ | ✅ | ✅ | ✅ |
| Auto-orchestration | ❌ | ✅ | ❌ | ❌ |

### Permission Format Reference

Claude Code uses **prefix matching** for permissions (not regex):

| Permission | Format | Example Matches |
|------------|--------|-----------------|
| All bash commands | `Bash(:*)` | Any bash command |
| Bash prefix | `Bash(pytest:*)` | `pytest`, `pytest tests/`, `pytest -v` |
| All file reads | `Read(**)` | Any file path |
| Specific directory | `Read(./src/**)` | Files in src/ directory |
| All file writes AND edits | `Edit(**)` | Any file path — see note below |
| Simple tools | `Write`, `Glob`, `Grep`, `WebFetch` | Just the tool name |
| All MCP tools | `mcp__` | Any MCP server tool (prefix match) |

**Three Permission Levels**:
- **`allow`**: Auto-approve immediately (no prompt)
- **`ask`**: Prompt user for confirmation
- **`deny`**: Block silently (no prompt, operation fails)

**Security Setting**:
```json
{
  "permissions": {
    "disableBypassPermissionsMode": "disable"
  }
}
```
This prevents users from using `--dangerously-skip-permissions` flag, forcing reliance on configured policies.

### Environment Variables

Add to `.env` file in project root:

```bash
# Master switch - enables MCP auto-approval for subagent tool calls
MCP_AUTO_APPROVE=false       # Default: false (opt-in design)

# Custom policy file path (optional)
AUTO_APPROVE_POLICY_FILE=/path/to/custom_policy.json  # Default: plugins/autonomous-dev/config/auto_approve_policy.json
```

### Policy File

Default location: `plugins/autonomous-dev/config/auto_approve_policy.json`

**Structure** (v2.0 - Permissive/Blacklist-First):
```json
{
  "version": "2.0",
  "description": "MCP Auto-Approval Policy - PERMISSIVE mode with dangerous command blacklist",
  "bash": {
    "mode": "blacklist",
    "whitelist": ["*"],
    "blacklist": [
      "rm -rf /*",
      "sudo *",
      "chmod 777*",
      "eval *",
      "git push --force origin main"
    ]
  },
  "file_paths": {
    "whitelist": ["*"],
    "blacklist": [
      "/etc/*",
      "/var/*",
      "/root/*",
      "*/.env",
      "*/secrets/*",
      "*/.ssh/*"
    ]
  },
  "agents": {
    "trusted": [
      "researcher",
      "planner",
      "test-master",
      "implementer",
      "reviewer",
      "doc-master"
    ],
    "restricted": [
      "security-auditor"
    ]
  }
}
```

**Glob Patterns**:
- `*` matches any characters within a path segment
- `?` matches a single character
- `[abc]` matches any character in brackets
- Examples:
  - `pytest*` matches `pytest`, `pytest tests/`, `pytest -v`
  - `git diff*` matches `git diff`, `git diff --cached`, `git diff HEAD~1`
  - `/tmp/*` matches any file in `/tmp/`

### Policy File Location (NEW in v3.41.0 - Issue #100)

Policy files support cascading lookup with fallback, enabling per-project customization.

**Lookup Order**:
1. **Project-Local Policy**: `.claude/config/auto_approve_policy.json` - Custom rules for this project
2. **Plugin Default**: `plugins/autonomous-dev/config/auto_approve_policy.json` - Stable plugin default
3. **Minimal Fallback**: Graceful degradation if both missing

**Per-Project Customization**:
```bash
# Create custom policy in your project
mkdir -p .claude/config/
cp plugins/autonomous-dev/config/auto_approve_policy.json .claude/config/auto_approve_policy.json

# Edit .claude/config/auto_approve_policy.json to customize rules for this project
# Example: Add project-specific trusted commands or blocked patterns
```

**Automatic Behavior**:
- If `.claude/config/auto_approve_policy.json` exists and is valid JSON, it takes priority
- Otherwise, falls back to plugin default
- No configuration needed - automatic detection and caching
- Policy file updates automatically after `/update-plugin` (no stale policy bug)

**Security Validation**:
- Rejects symlinks in policy file paths (CWE-59 - symlink attacks)
- Validates JSON format before use
- Gracefully degrades if policy file is unreadable
- Implements path containment to prevent escaping project boundaries

**Use Cases**:
- Stricter policies for sensitive projects (fewer auto-approved commands)
- Looser policies for internal tooling (more productive workflows)
- Team-specific policies (share `.claude/config/auto_approve_policy.json` in repo)
- Testing different policies without modifying plugin

**Implementation**: See `path_utils.get_policy_file()` in [docs/LIBRARIES.md](LIBRARIES.md) section 15 for API documentation.

---

## Security Model

> **REMOVED** — this section, the Policy File Reference, Troubleshooting, and
> For Contributors sections below all describe the deleted subsystem
> (`auto_approval_engine.py`, `auto_approval_consent.py`,
> `tool_approval_audit.py`) as if it were live: code samples, `Location:`
> paths, and `logs/tool_approval_audit.log` troubleshooting steps that write
> to or read from nothing that runs today. `tool_validator.py` and
> `plugins/autonomous-dev/config/auto_approve_policy.json` still exist on
> disk but nothing in the live `unified_pre_tool.py` path invokes them for
> this whitelist/blacklist logic. Read what follows as design history, not a
> guide to running code — see the top-of-file status banner.

### 6 Layers of Defense-in-Depth

**1. Subagent Context Isolation**

Only auto-approve tool calls from subagents (not from main Claude session):

```python
# Determine agent identity (Issue #591):
# 1. agent_type from hook stdin JSON (primary — available inside subagents
#    even when CLAUDE_AGENT_NAME is absent from subprocess env)
# 2. CLAUDE_AGENT_NAME env var (fallback for older contexts)
agent_name = _get_active_agent_name()
if not agent_name:
    # Not in subagent context → manual approval
    return {"approved": False, "reason": "Not in subagent context"}
```

**Why**: Prevents accidental auto-approval of user's manual tool invocations. Only autonomous workflows use auto-approval.

**Note (Issue #591)**: `CLAUDE_AGENT_NAME` may be absent from the subprocess environment when hooks fire inside a subagent. The hook reads `agent_type` from the stdin JSON payload first (populated by Claude Code even in subprocess contexts) and falls back to the env var. Both sources are consulted; `CLAUDE_AGENT_NAME` alone is no longer the sole identity signal.

**2. Agent Whitelist** (subagent_only mode)

Agent whitelist enforcement depends on the auto-approval mode:

```json
{
  "agents": {
    "trusted": ["researcher", "planner", "test-master", "implementer", "reviewer", "doc-master"],
    "restricted": ["security-auditor"]
  }
}
```

**Enforcement**:
- **Everywhere mode** (`MCP_AUTO_APPROVE=true`): Whitelist check **SKIPPED** - all agents trusted
- **Subagent-only mode** (`MCP_AUTO_APPROVE=subagent_only`): Whitelist check **ENFORCED** - only listed agents trusted

**Why**: In everywhere mode, the user has opted to trust all agents (main + subagent workflows). In subagent_only mode, the whitelist provides granular control over which agents can auto-approve (e.g., security-auditor may need manual oversight).

**3. Tool Whitelist**

Only approved MCP tools are auto-approved:

```python
ALLOWED_TOOLS = ["Bash", "Read", "Write", "Grep", "Edit"]

if tool_name not in ALLOWED_TOOLS:
    # Unknown tool → manual approval
    return {"approved": False, "reason": f"Tool not whitelisted: {tool_name}"}
```

**Why**: Prevents auto-approval of future unknown tools that may have security implications.

**4. Command/Path Validation**

**Bash Commands** - Whitelist/Blacklist Enforcement:

```python
# Whitelist examples (safe commands)
"pytest*"           # Run tests
"git status"        # Check git status
"git diff*"         # View changes
"ls*"               # List files
"cat*"              # Read files
"grep*"             # Search files

# Blacklist examples (dangerous commands)
"rm -rf*"           # Recursive delete (data loss)
"sudo*"             # Privilege escalation
"chmod 777*"        # Insecure permissions
"curl*|*bash"       # Remote code execution
"eval*"             # Arbitrary code execution
```

**File Paths** - Path Traversal Prevention (CWE-22):

```python
# Whitelist examples (safe paths)
"/Users/*/Documents/GitHub/*"  # Project directories
"/tmp/pytest-*"                # Pytest temp directories
"/tmp/tmp*"                    # Temp files

# Blacklist examples (dangerous paths)
"/etc/*"                       # System configuration
"/var/*"                       # System data
"/root/*"                      # Root home directory
"*/.env"                       # Environment secrets
"*/secrets/*"                  # Credentials
"*/.ssh/*"                     # SSH keys
"*/id_rsa*"                    # Private keys
```

**Command Injection Prevention** (CWE-78):

```python
# Detect command chaining and injection
INJECTION_PATTERNS = [
    r';\s*\w+',           # Command chaining with semicolon
    r'&&\s+\w+',          # AND command chaining
    r'\|\|\s+\w+',        # OR command chaining
    r'\|\s+bash\b',       # Pipe to bash
    r'`[^`]+`',           # Backticks command substitution
    r'\$\([^)]+\)',       # $() command substitution
    r'\n\s*\w+',          # Newline command injection
]

if any(pattern.search(command) for pattern in INJECTION_PATTERNS):
    # Command injection detected → deny
    return {"approved": False, "reason": "Command injection detected"}
```

**5. Audit Logging**

Every approval/denial is logged to `logs/tool_approval_audit.log`:

```json
{
  "timestamp": "2025-11-15T10:30:45.123456Z",
  "event": "tool_call_approved",
  "tool": "Bash",
  "agent": "researcher",
  "command": "pytest tests/unit/",
  "reason": "Whitelist match: pytest*",
  "status": "approved"
}

{
  "timestamp": "2025-11-15T10:30:46.789012Z",
  "event": "tool_call_denied",
  "tool": "Bash",
  "agent": "implementer",
  "command": "rm -rf /tmp/important-data",
  "reason": "Blacklist match: rm -rf*",
  "status": "denied"
}
```

**Why**: Provides full audit trail for compliance, security monitoring, and debugging. Can integrate with SIEM systems (Splunk, ELK, etc.).

**6. Circuit Breaker**

Auto-disable after 10 consecutive denials:

```python
if denial_count >= CIRCUIT_BREAKER_THRESHOLD:
    # Circuit breaker tripped → disable auto-approval
    audit_log("circuit_breaker_tripped", {"denial_count": denial_count})
    # All future requests denied → manual approval required
```

**Why**: Prevents runaway automation if policy is misconfigured or agent behavior is unexpected. User must manually reset by restarting session.

---

## How It Works

### Request Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Subagent invokes MCP tool                                │
│    Example: researcher agent → Bash("pytest tests/")        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Claude Code 2.0 PreToolUse Hook                          │
│    Triggers: pre_tool_use.py (standalone script)            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Check MCP_AUTO_APPROVE environment variable              │
│    If false: return {"approved": False} (manual approval)   │
│    If true: continue to validation                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Check User Consent                                       │
│    First run: display consent prompt → save to user state   │
│    Subsequent runs: check ~/.autonomous-dev/user_state.json │
│    If consent denied: return {"approved": False}            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Validate Subagent Context                                │
│    Check agent_type (stdin JSON) then CLAUDE_AGENT_NAME     │
│    If neither set: return {"approved": False}               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Validate Agent Whitelist                                 │
│    Check if agent in trusted list                           │
│    If restricted: return {"approved": False}                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. Validate Tool Call (ToolValidator)                       │
│    - Check tool whitelist (Bash, Read, Write, Grep, Edit)   │
│    - Validate Bash command (whitelist/blacklist)            │
│    - Validate file paths (CWE-22 prevention)                │
│    - Detect command injection (CWE-78 prevention)           │
│    If validation fails: return {"approved": False}          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. Audit Log Decision (ToolApprovalAuditor)                 │
│    Log to logs/tool_approval_audit.log                      │
│    Metrics: approval_count, denial_count, last_used         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 9. Check Circuit Breaker                                    │
│    If denial_count >= 10: trip circuit breaker              │
│    If tripped: all future requests denied                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 10. Return Decision                                         │
│     {"approved": True, "reason": "Whitelist match: pytest*"}│
│     OR                                                       │
│     {"approved": False, "reason": "Blacklist match: rm -rf"}│
└─────────────────────────────────────────────────────────────┘
```

---

## Policy File Reference

### Full Default Policy (v2.0 - Permissive Mode)

Location: `plugins/autonomous-dev/config/auto_approve_policy.json`

```json
{
  "version": "2.0",
  "description": "MCP Auto-Approval Policy - PERMISSIVE mode with dangerous command blacklist",
  "bash": {
    "mode": "blacklist",
    "whitelist": ["*"],
    "blacklist": [
      "rm -rf /*",
      "rm -rf ~*",
      "rm -rf /Users/*",
      "rm -rf /home/*",
      "rm -rf .git",
      "rm -rf .ssh*",
      "rm -rf .aws*",
      "rm -rf .gnupg*",
      "rm -rf .config*",
      "rm -rf node_modules",
      "sudo *",
      "su *",
      "chmod 777*",
      "chmod -R 777*",
      "chown *",
      "chgrp *",
      "eval *",
      "exec *",
      "dd *",
      "mkfs*",
      "fdisk*",
      "parted*",
      "kill -9 -1",
      "killall -9*",
      "pkill -9*",
      "> /dev/*",
      "shutdown*",
      "reboot*",
      "halt*",
      "poweroff*",
      "init 0*",
      "init 6*",
      "systemctl poweroff*",
      "systemctl reboot*",
      "nc -l*",
      "netcat -l*",
      "ncat -l*",
      "telnet *",
      "*/bin/sh -c*",
      "*/bin/bash -c*",
      "*/bin/zsh -c*",
      "| sh",
      "| bash",
      "| zsh",
      "|sh",
      "|bash",
      "|zsh",
      "curl * | sh",
      "curl * | bash",
      "wget * | sh",
      "wget * | bash",
      "git push --force origin main",
      "git push --force origin master",
      "git push -f origin main",
      "git push -f origin master",
      "git reset --hard HEAD~*",
      "git clean -fdx",
      "npm publish*",
      "pip upload*",
      "twine upload*",
      "docker rm -f $(docker ps -aq)",
      "docker system prune -af",
      "xargs rm*",
      "find * -delete",
      "find * -exec rm*",
      ":(){:|:&};:",
      "export PATH=",
      "unset PATH"
    ]
  },
  "file_paths": {
    "whitelist": ["*"],
    "blacklist": [
      "/etc/*",
      "/var/*",
      "/root/*",
      "/home/*/.ssh/*",
      "/Users/*/Library/*",
      "/Users/*/.ssh/*",
      "/Users/*/.aws/*",
      "/Users/*/.gnupg/*",
      "*/.env",
      "*/secrets/*",
      "*/credentials/*",
      "*/.ssh/*",
      "*/id_rsa*",
      "*/id_ed25519*",
      "*/id_ecdsa*",
      "*/.aws/*",
      "*/.config/gh/hosts.yml",
      "/System/*",
      "/usr/*",
      "/bin/*",
      "/sbin/*",
      "/boot/*"
    ]
  },
  "agents": {
    "trusted": [
      "researcher",
      "planner",
      "test-master",
      "implementer",
      "reviewer",
      "doc-master"
    ],
    "restricted": [
      "security-auditor"
    ]
  },
  "web_tools": {
    "whitelist": ["Fetch", "WebFetch", "WebSearch"],
    "allow_all_domains": true,
    "blocked_domains": [
      "localhost",
      "127.0.0.1",
      "0.0.0.0",
      "169.254.169.254",
      "metadata.google.internal",
      "[::1]",
      "10.*",
      "172.16.*",
      "192.168.*"
    ]
  }
}
```

**Blacklist Categories**:

| Category | Patterns | Why Blocked |
|----------|----------|-------------|
| **Destructive file ops** | `rm -rf /*`, `rm -rf ~*`, `find * -delete` | Data loss, system damage |
| **Privilege escalation** | `sudo *`, `su *`, `chmod 777*` | Security violation |
| **System commands** | `shutdown*`, `reboot*`, `init 0*` | System disruption |
| **Shell injection** | `| sh`, `| bash`, `| zsh` | Remote code execution |
| **Dangerous git** | `git push --force origin main` | Irreversible history loss |
| **Publishing** | `npm publish*`, `twine upload*` | Accidental releases |
| **Network listeners** | `nc -l*`, `netcat -l*` | Unauthorized access |
| **Fork bombs** | `:(){:|:&};:` | System crash |

### Customizing the Policy

**Option 1: Override Policy File**

Create custom policy file and set environment variable:

```bash
# .env
MCP_AUTO_APPROVE=true
AUTO_APPROVE_POLICY_FILE=/path/to/custom_policy.json
```

**Option 2: Extend Default Policy**

Copy default policy and add your own rules:

```bash
cp plugins/autonomous-dev/config/auto_approve_policy.json custom_policy.json
vim custom_policy.json
# Add your custom whitelist/blacklist entries
```

**Example: Add npm Commands**

```json
{
  "bash": {
    "whitelist": [
      "pytest*",
      "npm test",
      "npm run lint",
      "npm run build",
      "npm list"
    ],
    "blacklist": [
      "rm -rf*",
      "npm publish*"  // Prevent accidental publishing
    ]
  }
}
```

**Example: Allow Docker Commands (with restrictions)**

```json
{
  "bash": {
    "whitelist": [
      "docker ps",
      "docker images",
      "docker logs*",
      "docker exec* -- cat*"  // Read-only operations
    ],
    "blacklist": [
      "docker rm -f*",
      "docker rmi -f*",
      "docker system prune*"
    ]
  }
}
```

---

## Troubleshooting

### Auto-Approval Not Working

**Symptom**: Still seeing manual approval prompts for tool calls

**Diagnosis**:
```bash
# 1. Check environment variable
grep MCP_AUTO_APPROVE .env
# Should show: MCP_AUTO_APPROVE=true

# 2. Check user state file
cat ~/.autonomous-dev/user_state.json
# Should show: {"mcp_auto_approve_consent": true}

# 3. Check audit log
tail -20 logs/tool_approval_audit.log
# Look for denial reasons
```

**Common Fixes**:

1. **Environment variable not set**:
   ```bash
   echo "MCP_AUTO_APPROVE=true" >> .env
   ```

2. **User consent denied**:
   ```bash
   # Reset user state
   rm ~/.autonomous-dev/user_state.json
   # Re-run /implement and choose "Y" at consent prompt
   ```

3. **Command not in whitelist**:
   ```bash
   # Check audit log for denied command
   grep "tool_call_denied" logs/tool_approval_audit.log | tail -5
   # Add command to whitelist in policy file
   ```

### Circuit Breaker Tripped

**Symptom**: All tool calls denied after multiple denials

**Diagnosis**:
```bash
# Check audit log for circuit breaker event
grep "circuit_breaker_tripped" logs/tool_approval_audit.log
```

**Fix**:
```bash
# Restart Claude Code session to reset circuit breaker
# (Circuit breaker state is in-memory, resets on restart)
pkill -9 claude
# Wait 2 seconds, then reopen Claude Code
```

### Path Validation Errors

**Symptom**: File read/write operations denied even though path looks safe

**Diagnosis**:
```bash
# Check audit log for path validation failures
grep "path_traversal" logs/tool_approval_audit.log
# OR
grep "path validation failed" logs/tool_approval_audit.log
```

**Common Fixes**:

1. **Path not in whitelist**:
   ```json
   // Add to policy file
   {
     "file_paths": {
       "whitelist": [
         "/Users/*/Documents/GitHub/*",
         "/Users/*/Documents/MyProject/*"  // Add custom path
       ]
     }
   }
   ```

2. **Symbolic link issues**:
   ```bash
   # security_utils.validate_path() resolves symlinks
   # Ensure resolved path is in whitelist
   realpath /path/to/file  # Check where symlink points
   ```

### Command Injection False Positives

**Symptom**: Legitimate commands with special characters denied

**Example**:
```bash
# Denied because of pipe character
pytest tests/ -v | grep "FAILED"
```

**Fix**:

Option 1: Add to whitelist with escaped pattern:
```json
{
  "bash": {
    "whitelist": [
      "pytest* | grep*"  // Allow pytest piped to grep
    ]
  }
}
```

Option 2: Refactor command to avoid injection patterns:
```bash
# Instead of:
pytest tests/ -v | grep "FAILED"

# Use pytest's built-in filtering:
pytest tests/ -v --tb=short -x
```

### Audit Log Not Writing

**Symptom**: `logs/tool_approval_audit.log` file missing or empty

**Diagnosis**:
```bash
# Check if logs directory exists
ls -la logs/

# Check file permissions
ls -la logs/tool_approval_audit.log
```

**Fix**:
```bash
# Create logs directory if missing
mkdir -p logs

# Fix permissions
chmod 755 logs
chmod 644 logs/tool_approval_audit.log
```

---

## For Contributors

### Extending Whitelist/Blacklist

**Step 1: Identify New Commands**

Run `/implement` with `MCP_AUTO_APPROVE=false` and note denied commands:

```bash
# Check audit log for denied commands
grep "tool_call_denied" logs/tool_approval_audit.log | grep "whitelist" | tail -20
```

**Step 2: Evaluate Safety**

Ask yourself:
- ✅ Is this command read-only? (safe)
- ✅ Does it only affect project files? (safe)
- ✅ Can it cause data loss? (unsafe → blacklist)
- ✅ Can it escalate privileges? (unsafe → blacklist)
- ✅ Can it exfiltrate data? (unsafe → blacklist)

**Step 3: Add to Policy**

Edit `plugins/autonomous-dev/config/auto_approve_policy.json`:

```json
{
  "bash": {
    "whitelist": [
      // Existing commands...
      "your-new-command*"  // Add new safe command
    ],
    "blacklist": [
      // Existing commands...
      "dangerous-command*"  // Add new unsafe command
    ]
  }
}
```

**Step 4: Test**

```bash
# 1. Create test case
cat > tests/unit/lib/test_tool_validator_custom.py << 'EOF'
def test_validate_custom_command_approved():
    validator = ToolValidator()
    result = validator.validate_bash_command("your-new-command --flag")
    assert result.approved
    assert "whitelist" in result.reason.lower()

def test_validate_dangerous_command_denied():
    validator = ToolValidator()
    result = validator.validate_bash_command("dangerous-command --flag")
    assert not result.approved
    assert "blacklist" in result.reason.lower()
EOF

# 2. Run tests
pytest tests/unit/lib/test_tool_validator_custom.py -v

# 3. Test in real workflow
MCP_AUTO_APPROVE=true /implement "Feature that uses your-new-command"
```

**Step 5: Document**

Add to this file's "Policy File Reference" section:

```markdown
### Custom Commands - [Your Domain]

**your-new-command**: Brief description of what it does and why it's safe
```

### Adding New Agent to Whitelist (subagent_only mode)

**Note**: In everywhere mode (`MCP_AUTO_APPROVE=true`), all agents are trusted automatically. This section only applies to `MCP_AUTO_APPROVE=subagent_only` mode.

**Step 1: Evaluate Agent Trustworthiness**

Ask yourself:
- ✅ Does this agent only read/analyze code? (safe)
- ✅ Does this agent modify code? (needs validation)
- ✅ Does this agent access sensitive data? (restricted)

**Step 2: Add to Policy**

```json
{
  "agents": {
    "trusted": [
      "researcher",
      "planner",
      "test-master",
      "implementer",
      "reviewer",
      "doc-master",
      "your-new-agent"  // Add here if trusted
    ],
    "restricted": [
      "security-auditor",
      "your-sensitive-agent"  // Add here if needs manual approval
    ]
  }
}
```

**Step 3: Test**

```bash
# Create test case (Note: unified_pre_tool_use replaces auto_approve_tool)
cat > tests/unit/hooks/test_unified_pre_tool_use_custom_agent.py << 'EOF'
from plugins.autonomous_dev.hooks.unified_pre_tool_use import on_pre_tool_use
import os

def test_custom_agent_auto_approved():
    # Set CLAUDE_AGENT_NAME as the env-var fallback for agent identity.
    # In real subagent execution, agent_type from stdin JSON takes precedence
    # (Issue #591). The env var remains valid for unit test contexts where
    # stdin JSON is not present.
    os.environ["CLAUDE_AGENT_NAME"] = "your-new-agent"
    os.environ["MCP_AUTO_APPROVE"] = "true"

    result = on_pre_tool_use(tool="Bash", parameters={"command": "pytest tests/"})

    # Check new Claude Code format
    assert result["hookSpecificOutput"]["permissionDecision"] == "allow"
    assert "your-new-agent" in result["hookSpecificOutput"]["permissionDecisionReason"]
EOF

pytest tests/unit/hooks/test_unified_pre_tool_use_custom_agent.py -v
```

---

## Architecture

### Component Diagram

> **REMOVED** — this diagram describes the deleted `pre_tool_use.py` /
> `auto_approval_engine.py` / `tool_approval_audit.py` pipeline, none of
> which ever ran. It is retained as design history only; see the top-of-file
> status banner and `docs/MCP-SECURITY.md` for what actually enforces tool
> permissions today (`unified_pre_tool.py`).

```
┌─────────────────────────────────────────────────────────────┐
│                    Claude Code 2.0                           │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ PreToolUse Hook Lifecycle                              │ │
│  │                                                        │ │
│  │  Executes: python3 pre_tool_use.py                    │ │
│  │  Input: stdin (JSON with tool_name + tool_input)      │ │
│  │  Output: stdout (JSON with permissionDecision)        │ │
│  └─────────────────────┬──────────────────────────────────┘ │
│                        │                                     │
└────────────────────────┼─────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│         pre_tool_use.py (Standalone Hook Script)            │
│                                                              │
│  1. Read JSON from stdin (tool_name, tool_input)            │
│  2. Load .env file (MCP_AUTO_APPROVE, etc.)                 │
│  3. Call auto_approval_engine.should_auto_approve()         │
│  4. Format decision as hookSpecificOutput                   │
│  5. Write JSON to stdout                                    │
│  6. Exit 0 (always)                                         │
└────────┬────────────────────────────┬───────────────────────┘
         │                            │
         ▼                            ▼
┌──────────────────────┐    ┌──────────────────────────────┐
│   ToolValidator      │    │   ToolApprovalAuditor        │
│   (tool_validator.py)│    │   (tool_approval_audit.py)   │
│                      │    │                              │
│ - load_policy()      │    │ - log_approval()             │
│ - validate_bash()    │    │ - log_denial()               │
│ - validate_path()    │    │ - get_metrics()              │
│ - detect_injection() │    │ - circuit_breaker_check()    │
└──────────────────────┘    └──────────────────────────────┘
         │                            │
         │                            │
         ▼                            ▼
┌──────────────────────┐    ┌──────────────────────────────┐
│  auto_approve_       │    │  logs/tool_approval_         │
│  policy.json         │    │  audit.log                   │
│                      │    │                              │
│ - bash whitelist     │    │ - ISO 8601 timestamps        │
│ - bash blacklist     │    │ - JSON event format          │
│ - path whitelist     │    │ - Per-tool metrics           │
│ - path blacklist     │    │ - SIEM integration           │
│ - agent whitelist    │    │                              │
└──────────────────────┘    └──────────────────────────────┘
```

### File Structure

> **REMOVED** — `auto_approval_engine.py`, `tool_approval_audit.py`, and
> `auto_approval_consent.py` (and their test files below) were deleted; none
> ever executed. `tool_validator.py` and `security_utils.py` still exist on
> disk but are not invoked from any live hook path. The actual enforcement
> path today is `plugins/autonomous-dev/hooks/unified_pre_tool.py` — the
> hook filenames `pre_tool_use.py` / `unified_pre_tool_use.py` shown below
> do not exist in this repository.

```
plugins/autonomous-dev/
├── hooks/
│   ├── pre_tool_use.py              (PreToolUse hook script - historical, does not exist)
│   └── unified_pre_tool_use.py      (Legacy library code - historical, does not exist)
├── lib/
│   ├── auto_approval_engine.py      (Core auto-approval logic) — REMOVED, never executed
│   ├── tool_validator.py            (Whitelist/blacklist validation)
│   ├── tool_approval_audit.py       (Audit logging system) — REMOVED, never executed
│   ├── auto_approval_consent.py     (User consent management) — REMOVED, never executed
│   └── security_utils.py            (Path validation, CWE-22 prevention)
├── config/
│   └── auto_approve_policy.json     (Policy configuration)
└── tests/
    ├── unit/
    │   ├── lib/
    │   │   ├── test_tool_validator.py
    │   │   ├── test_tool_approval_audit.py     — REMOVED with the module it tested
    │   │   └── test_user_state_manager_auto_approval.py
    │   └── hooks/
    │       └── test_auto_approve_tool.py
    ├── integration/
    │   └── test_tool_auto_approval_end_to_end.py     — REMOVED with the module it tested
    └── security/
        └── test_tool_auto_approval_security.py
```

### Hook Registration

The hook must be registered in `~/.claude/settings.json` (not in plugin manifest):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 plugins/autonomous-dev/hooks/pre_tool_use.py",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

**Important**:
- Use absolute path to the script
- Claude Code only supports `"type": "command"` (shell execution)
- No Python module imports supported
- Must restart Claude Code after registration (Cmd+Q, not just `/exit`)

### API Reference

#### ToolValidator

**Location**: `plugins/autonomous-dev/lib/tool_validator.py`

**Class**: `ToolValidator`

**Constructor**:
```python
ToolValidator(policy_file: Path = DEFAULT_POLICY_FILE)
```

**Methods**:

- `validate_tool_call(tool: str, parameters: Dict[str, Any], agent_name: str) -> ValidationResult`
  - Validates complete tool call (tool + parameters + agent)
  - Returns: `ValidationResult(approved: bool, reason: str)`

- `validate_bash_command(command: str) -> ValidationResult`
  - Validates Bash command against whitelist/blacklist
  - Detects command injection patterns (CWE-78)
  - Returns: `ValidationResult(approved: bool, reason: str)`

- `validate_file_path(path: str) -> ValidationResult`
  - Validates file path against whitelist/blacklist
  - Prevents path traversal (CWE-22)
  - Returns: `ValidationResult(approved: bool, reason: str)`

**Example**:
```python
from tool_validator import ToolValidator

validator = ToolValidator()

# Validate Bash command
result = validator.validate_bash_command("pytest tests/")
if result.approved:
    print(f"Approved: {result.reason}")
else:
    print(f"Denied: {result.reason}")

# Validate file path
result = validator.validate_file_path("/tmp/output.txt")
if result.approved:
    print(f"Safe path: {result.reason}")

# Validate full tool call
result = validator.validate_tool_call(
    tool="Bash",
    parameters={"command": "git status"},
    agent_name="researcher"
)
```

#### ToolApprovalAuditor — REMOVED, never executed

> `plugins/autonomous-dev/lib/tool_approval_audit.py` and its class below were
> deleted; the API reference that follows describes a design, not code you can
> import. `logs/tool_approval_audit.log` is not written by anything running
> today.

**Location** (historical, file no longer exists): `plugins/autonomous-dev/lib/tool_approval_audit.py`

**Class**: `ToolApprovalAuditor`

**Constructor**:
```python
ToolApprovalAuditor(log_file: Path = DEFAULT_LOG_FILE)
```

**Methods**:

- `log_approval(tool: str, agent: str, details: Dict[str, Any])`
  - Logs approved tool call
  - Writes JSON event to audit log
  - Updates per-tool metrics

- `log_denial(tool: str, agent: str, reason: str, details: Dict[str, Any])`
  - Logs denied tool call
  - Writes JSON event to audit log
  - Updates per-tool metrics

- `get_tool_metrics() -> Dict[str, Any]`
  - Returns per-tool approval/denial counts
  - Format: `{tool_name: {"approval_count": int, "denial_count": int, "last_used": str}}`

**Example**:
```python
from tool_approval_audit import ToolApprovalAuditor

auditor = ToolApprovalAuditor()

# Log approval
auditor.log_approval(
    tool="Bash",
    agent="researcher",
    details={"command": "pytest tests/"}
)

# Log denial
auditor.log_denial(
    tool="Bash",
    agent="implementer",
    reason="Blacklist match: rm -rf*",
    details={"command": "rm -rf /tmp/data"}
)

# Get metrics
metrics = auditor.get_tool_metrics()
print(f"Bash approvals: {metrics['Bash']['approval_count']}")
print(f"Bash denials: {metrics['Bash']['denial_count']}")
```

---

## Changelog

### v3.40.0 (2025-12-09)

**Policy v2.0 - Permissive Mode**:
- Switched from whitelist-first to blacklist-first approach
- `whitelist: ["*"]` approves all commands by default
- Comprehensive blacklist covers dangerous patterns only
- Zero friction for legitimate development commands
- No more manual whitelist additions needed

**Blacklist Additions**:
- Fork bomb prevention (`:(){:|:&};:`)
- PATH manipulation (`export PATH=`, `unset PATH`)
- Docker destructive commands (`docker system prune -af`)
- Force push to protected branches (`git push --force origin main/master`)
- Publishing commands (`npm publish`, `twine upload`)
- Network listeners (`nc -l`, `netcat -l`)

### v3.39.0 (2025-12-08)

**Simplified**:
- Standalone `pre_tool_use.py` script replaces `unified_pre_tool_use.py` (library format)
- Hook registration now uses standard Claude Code shell command format
- Reads JSON from stdin, outputs JSON to stdout, exits 0
- Registered in `~/.claude/settings.json` (not plugin manifest)
- All existing validation logic preserved (just simpler interface)

**Rationale**:
- Claude Code only supports `"type": "command"` (shell execution), not Python module imports
- Previous approach (`"type": "python"`) was never supported by Claude Code
- Simplified architecture = fewer points of failure

### v3.38.0 (2025-12-08)

**Updated**:
- Unified PreToolUse hook (`unified_pre_tool_use.py`) replaced `auto_approve_tool.py`
- Hook return format updated to Claude Code official spec (hookSpecificOutput format)
- Eliminated hook collision between auto_approve_tool and mcp_security_enforcer
- Core auto-approval logic extracted to `auto_approval_engine.py` library

### v3.21.0 (2025-11-15)

**Added**:
- Initial implementation of MCP auto-approval feature
- PreToolUse hook handler (`auto_approve_tool.py`)
- Whitelist/blacklist validation engine (`tool_validator.py`)
- Audit logging system (`tool_approval_audit.py`)
- User consent management (`auto_approval_consent.py`)
- Default policy configuration (`auto_approve_policy.json`)

**Security**:
- 6 layers of defense-in-depth validation
- Path traversal prevention (CWE-22)
- Command injection prevention (CWE-78)
- Audit logging for compliance
- Circuit breaker protection

---

## References

- **GitHub Issue**: #73 (MCP Auto-Approval for Subagent Tool Calls)
- **CHANGELOG.md**: v3.21.0 release notes
- **CLAUDE.md**: MCP Auto-Approval Control section
- **plugins/autonomous-dev/README.md**: MCP Auto-Approval feature section
- **CWE-22**: Path Traversal - https://cwe.mitre.org/data/definitions/22.html
- **CWE-78**: OS Command Injection - https://cwe.mitre.org/data/definitions/78.html
- **CWE-117**: Log Injection - https://cwe.mitre.org/data/definitions/117.html

---

**Last Updated**: 2025-12-09
**Version**: v3.40.0
**Maintainer**: autonomous-dev plugin team
