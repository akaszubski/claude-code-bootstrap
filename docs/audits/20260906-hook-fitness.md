# Hook fitness for purpose — 34 hooks, measured 2026-09-06

Answers: *do we need these, are they useful to PROJECT.md intent, and will they work?*
Method: registration read from every LIVE settings surface (user, project, global template,
6 shipped templates); refusal capability from a real block path in source
(`"decision": "block"`, `permissionDecision.*deny`, `exit(2)`); refusal counts from
`docs/audits/mechanism-view.json`. Declared type from each `*.hook.json` sidecar.

| Verdict | n | lines | meaning |
|---|---|---|---|
| **WORKING GATE** | 5 | 13,181 | registered, can refuse, HAS refused |
| **NOT A GATE + unwired** | 15 | 5,587 | no event, no block path — cannot fire, cannot refuse |
| **NOT A GATE (observer)** | 12 | 5,400 | fires, but has no block path — logging/telemetry, not enforcement |
| **UNPROVEN** | 1 | 505 | registered and CAN refuse, never has |
| **DEAD GATE** | 1 | 344 | CAN refuse, HAS 118 recorded refusals, now registered NOWHERE |

## The five that actually enforce
unified_pre_tool (2,916 refusals) · unified_prompt_validator (115) · plan_gate (98) ·
validate_claude_md_size (2) · enforce_file_organization (2).
`unified_pre_tool` is 90% of all refusals ever recorded.

## The sharpest finding
**`enforce_orchestrator` — 344 lines, has a real block path, 118 recorded refusals, and is
registered on NO lifecycle event on any surface.** A guard that was working and silently
stopped. This is PROJECT.md's "the controls themselves drift, die, and misreport", live.

## Declaration contradicts deployment (3)
`stop_quality_gate`, `SessionStart-batch-recovery`, `auto_format` are declared
`"type": "utility"` in their sidecar but ARE registered on live lifecycle events.
The sidecar is not authoritative, so any tool trusting `type` is wrong about these three.

## Instrument correction made during this audit
The first scan read only `settings.json` surfaces and reported 16 hooks as "cannot fire".
That was WRONG: hooks also carry `*.hook.json` sidecars. The contradiction that exposed it —
`enforce_orchestrator` showing unregistered yet holding 118 refusals — is why the number
above is 1 dead gate and not 16. Same lesson as the subtraction campaign: repair the
instrument before trusting it.

## What this does NOT establish
"Never refused" is not "useless" — an observer hook that logs is legitimately not a gate,
and a gate may simply never have met a violation. What it does establish is that only 5 of
34 have a PROVEN refusing arm, which is the measurement PROJECT.md asks for and does not have.
