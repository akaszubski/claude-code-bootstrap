# Control-tool v12 — contain first, then prove one thin vertical slice

**Status:** PROPOSED. This document does not change the currently adopted authority until the exact commit and SHA-256 are explicitly adopted. On adoption it explicitly supersedes the v11 adoption recorded in [#1757 on 2026-09-06](https://github.com/akaszubski/autonomous-dev/issues/1757#issuecomment-5562381846), including P0-A authorization, and supersedes the execution sequence and completion rules in the v11 capability ladder and plugin-native prerequisite; those documents remain historical design evidence, not executable authority.

**Intent:** autonomous-dev is a retrofit-capable policy-as-code SDLC tool. It must turn project intent, standards, and change criteria into deterministic controls with observable, traceable, provenance-bound results. The tool must dogfood itself, but self-hosting is not consumer proof.

## 1. Why this revision exists

The prior plan correctly required independent evidence, refused model authority, separated observation from promotion, and treated `source`/`installed`/`executing` identity as distinct. It nevertheless built too much assurance machinery before delivering one improved control.

Current evidence makes that concrete:

- against adopted base `9e75f5e3934b4bf8d8efb2ff8a295abb13eb03fe`, the P0-A candidate adds 21,983 lines before changing a production control: 4,658 observer lines, 13,698 test lines, a 1,025-line schema, and 2,602 additional manifest/fixture/CI/doc lines;
- the sensitive-write MCP defect was fixed in `PreToolUseWrite-protect-sensitive.sh` at `d90f85390512ccbdf3e7c91939d6ff0d7c1cf216`, using unchanged `tool_intent.py` as a dependency; primary local installed hooks now match source, while stale worktree and `.codex` mirrors demonstrate unresolved fan-out;
- a denominator derived only by the classifier being tested can omit decision sites and still report full coverage;
- kernel digest changes can invalidate many proofs at once, creating pressure to bypass the system.

Therefore candidate `7eaffbecfdff7a253d937dc786a337496133a811` is retained as research evidence but is not landed or promoted. Its useful cases may be re-expressed only when a later thin slice needs them.

## 2. Small stable kernel

The initial product kernel has only four concepts:

1. **case** — subject, stimulus, expected outcome, opposite arm, fault arm, and declared invalidation inputs;
2. **observation** — raw process or hook result with exact exit, bounded output digests, subject identity including `stage ∈ {source, installed, executing}`, and carrier identifiers when present;
3. **decision** — `PASS`, `FAIL`, `UNMEASURED`, or `ERROR`, produced only by deterministic comparison;
4. **receipt** — immutable canonical JSON binding the case, observation, decision, tool version, and dependency digests.

No other taxonomy, graph vocabulary, transaction state machine, persistent service, dynamic plugin framework, dashboard, or general policy language is introduced before the first real control is released. New vocabulary requires a demonstrated case the four concepts cannot represent and a separate reviewed schema version.

The first implementation uses:

- Claude Code's native `stream-json` plus hook lifecycle records as raw carrier evidence;
- one small standard-library verifier that propagates the real process exit and correlates carrier events only when the carrier supplies a frozen exact key; `451cb1c6` proves a timestamp query over dispatcher OTel events, not an exact identifier join, so timestamp proximity may aid diagnosis but can never create a passing correlation;
- one canonical JSON receipt file per run;
- existing Git, Python, pytest, Ruff, shell, and Claude executables recorded by path/version/digest where relevant.

The native transcript is evidence, not authority. A model may explain a result but cannot create `PASS`, weaken a case, choose its own denominator, or promote a candidate.

## 3. Non-negotiable invariants

1. A missing, empty, skipped, timed-out, stale, malformed, or unjoinable observation cannot pass.
2. The candidate never certifies itself: frozen cases, a primitive process oracle, and its comparator are committed and explicitly adopted before candidate implementation; a dedicated CI job owned outside the candidate grants `RUNNER_TRUSTED` only from their exit.
3. Each decision fact has one owner; settings, hooks, CI, deploy, and docs are adapters or projections.
4. `source`, `installed`, and `executing` bytes are named separately. A `source` pass is never an `installed` pass.
5. Every permitting and refusing control has both arms, a fault arm, and at least one mutant that must turn the instrument red.
6. A production activation removes or demotes the superseded decision owner in the same change.
7. A control that cannot emit its required observation fails closed at enforcement boundaries.
8. Every new mechanism has an owner, consumer, removal condition, and measured cost.

## 4. Program states that emit useful signal

The program uses reachable states rather than an all-or-nothing definition:

| State | Meaning |
|---|---|
| `CONTAINED` | known live false-permit is fixed on every reachable installed target; unreachable targets are named `UNMEASURED` |
| `RUNNER_TRUSTED` | the verifier agrees with a separately frozen primitive process oracle on exit and selected subjects, and passes mutation, tamper, and stale-subject controls |
| `DELIVERY_PROVEN` | one plugin-native, source-free clean install runs the verifier and a real hook |
| `FIRST_CONTROL_RELEASED` | one real control is pure, connected, installed, observed, and the old owner is removed |
| `MIGRATING` | additional controls move one at a time through the same method |
| `RETROFIT_PROVEN` | a distinct consumer repository/profile passes without source or ambient-home fallback |
| `COMPLETE` | all declared active controls have one owner and current receipts; remaining legacy mechanisms are explicitly historical or rejected |

The program ledger always records the current state, the next missing receipt, elapsed effort, and any `UNMEASURED` target. Partial progress is therefore visible and cannot masquerade as completion. `COMPLETE` is a digest-bound release snapshot, not a permanent badge: an invalidated receipt immediately lowers the reported state to the highest state still supported by current evidence.

## 5. Corrected execution sequence

### S0 — contain the known MCP false-permit now

Contain the already-reviewed `PreToolUseWrite-protect-sensitive.sh` fix, whose unchanged dependency `tool_intent.write_targets()` extracts built-in and MCP paths, through the existing deploy path before building new infrastructure. Primary local installed hooks currently match source; S0 must classify stale worktree and `.codex` mirrors as installed, historical, or unreachable rather than treating every copy as executable.

Required evidence:

- source regression arms for built-in deny, MCP `relative_path` deny, and ordinary-path allow;
- exact source-to-installed digests for every reached local consumer;
- direct installed-hook execution of the three arms;
- a fresh real-Claude/Serena carrier attempt;
- remote or disconnected consumers explicitly `UNMEASURED`, never implied green.

This is containment, not proof that legacy deployment is the final architecture. It is allowed to be superseded later.

### F0 — freeze the next cases before building the runner

Freeze the exact current discovery, `executing`, `installed`, S0, and first delivery-slice cases. Commit alongside them a tiny POSIX process oracle and comparator owned by the bootstrap test harness, not the candidate verifier. The harness runs the candidate and oracle independently; the oracle writes raw command exit and sorted selected node IDs to a file whose path is not exposed to the candidate, and the comparator checks those facts directly against the candidate receipt. Neither bootstrap program can emit the product decision vocabulary or write the product ledger. An absent, empty, malformed, or unchanged-from-a-prior-run oracle file is a named failing arm.

F0 exits only when the case manifest, oracle, comparator, their mutation controls, and their exact digests are explicitly frozen on the program issue. It must also measure the identifiers present in real Claude hook ingress, hook result, dispatcher OTel, and `stream-json` records; any proposed cross-record join key is recorded as observed or absent rather than assumed. R0 implementation cannot begin on plan adoption alone: it requires a second explicit authorization naming that F0 commit and digest.

The bootstrap verdict belongs to a separate `control-runner-trust` workflow containing only the frozen trust suite, not to the ambiently red general CI workflow. The same frozen suite and environment profile must be runnable locally for diagnosis; the workflow independently re-executes and records the promotion verdict rather than originating different logic. Before R0 exists, that workflow must be green on the frozen F0 base using its known-good fixture and must turn red for forged-receipt, mutated-comparator, stale-digest, and absent/empty/malformed/unchanged-oracle arms. R0 is then tested with the same digest-bound bootstrap bytes and environment; only the dedicated workflow's own green base and candidate results may grant `RUNNER_TRUSTED`. The candidate cannot write that state or make unrelated CI failures appear green.

### R0 — trust the smallest useful runner

Replace the rejected P0-A candidate with a bounded verifier over native Claude events and ordinary process results. It supports only the observation shapes required by S0 and the next delivery slice.

Required controls:

- capture process status before formatting output; no pipeline can overwrite it;
- produce a receipt that the frozen comparator agrees byte-for-byte with the primitive oracle on raw exit and selected node IDs; disagreement makes the external CI job fail and the program state remains below `RUNNER_TRUSTED`;
- record the exact command, cwd, executable identity, selected case IDs, collected node IDs/count, start/end, timeout, stdout/stderr digests, output truncation, and every carrier identifier actually emitted;
- zero selection, changed addopts/plugins, wrong cwd, missing hook event, duplicate hook event, mismatched carrier identity, and stale subject are non-pass; a missing identifier is `UNMEASURED` whenever the frozen case requires that identifier for exact correlation;
- a harmless mutant of the control produces named failures;
- a no-op/ordinary-path control stays permitted;
- run the same immutable verifier against base and candidate; compare node-ID sets, not only counts;
- a seeded omitted decision site makes denominator coverage fail.

Exit: the external `control-runner-trust` CI job releases one source-free verifier executable, the four-concept v1 schema, and one receipt format as `RUNNER_TRUSTED`. The candidate cannot write that state. The case owns the declared invalidation inputs; the receipt owns only the resolved dependency digests observed for that run.

### Existing proof machinery disposition

No second verifier family is created implicitly:

| Existing mechanism | Disposition in v12 |
|---|---|
| `plugins/autonomous-dev/scripts/proof_of_block.py` | Reuse unchanged, including its recorded-artifact/baseline format, as the only persistent block-proof owner for S0 and legacy block-capable hooks. R0 must not write an equivalent hook-block authority beside it. W0 may adapt its output to the canonical receipt or atomically supersede it only after its live manifest/CI/health-check consumers are enumerated and equivalent cases pass. |
| `lib/retrofit_verifier.py` | Reuse for its current D0 readiness role; R0 consumes no readiness decision from it. Reconcile or remove only in D0. |
| `lib/completion_verifier.py` | Out of scope: retains its existing pipeline-completion role and cannot grant a control-tool state. |
| `lib/batch_agent_verifier.py` | Out of scope: retains its existing agent-completeness role and cannot grant a control-tool state. |
| `lib/runtime_verification_classifier.py` | Reuse only where an existing route already consumes it; W0 does not fork its vocabulary or completeness claims. |
| OTel query proven at `451cb1c6` | Reuse as a raw Claude evidence source and timestamp query shape; do not rebuild the 4,658-line observer and do not treat its timestamp association as exact provenance. Current legacy hook-block rows have no `tool_use_id` and predominantly empty `session_id`; F0 measures live carriers, and ambiguous correlation is non-pass. |
| Issue #1660 / `scripts/integration_ceiling.py` | Extend the shipped mutation-harness pattern for R0's verifier and comparator mutants; do not build another mutation framework. |

### D0 — one plugin delivery path

Build only the delivery path the product needs: one native Claude plugin containing active commands, agents, skills, hooks, libraries, scripts, config, and templates, plus one manifest-built standalone profile for CI/non-Claude use.

Use two implementation changesets after F0:

1. implement one plugin root and one runtime resolver, migrating bounded component families;
2. prove update, rollback, uninstall, dogfood, standalone, and a source-free clean consumer, then remove copied executable `.claude/` delivery paths.

There is no separate P1/P2/P3 vocabulary. Each changeset still has frozen input, candidate, independent proof, and explicit promotion. Existing Issue #1755/#1758/#1759 evidence is folded into D0; overlapping issues receive an append-only disposition rather than duplicate acceptance text. D0 begins RED because open #1755 records that installed Claude Code 2.1.236 rejects the shipped plugin manifests; its first case reproduces that exact installed-CLI failure before changing delivery code.

Exit: `DELIVERY_PROVEN` on exact `installed` bytes. The clean-consumer proof launches only an installed entrypoint from an isolated temporary cwd, starts from `env -i`, sets isolated `HOME`, `CLAUDE_CONFIG_DIR`, caches, settings, and a pinned minimal `PATH`, explicitly unsets `CLAUDE_PROJECT_DIR` and `PYTHONPATH`, and runs Python entrypoints in isolated mode (`-I`). It rejects any executable/module/path provenance under the source checkout. A clean installed control must pass; a fault arm that injects an otherwise importable source-checkout module or executable must be detected and fail. Same-owner machines do not imply organizational independence; independence is claimed only for boundaries that were actually observed.

### K0/O0/W0 — first useful vertical control

Build one walking slice around sensitive-write enforcement:

1. **K0:** apply the four-concept kernel and CLI released by R0 to this control; extend the schema only if a frozen failing case cannot be expressed, otherwise add no vocabulary;
2. **O0:** persist the minimal canonical observation record needed by this control; do not migrate general activity/archive/telemetry yet;
3. **W0:** extract sensitive-write policy into a pure function, keep one thin Claude adapter using canonical tool-intent path extraction, exercise built-in and MCP carriers, deploy to a clean consumer, then remove the old shell decision owner.

This slice proves the tool by improving one real control. It does not wait for the full logging migration, transaction chain, documentation compiler, connectivity graph, native-permission migration, or chained canary.

Exit: `FIRST_CONTROL_RELEASED` with exact `source`/`installed`/`executing` receipts and a rehearsed rollback.

### T0 then M0 — govern changes and migrate incrementally

Only after W0 works:

- add the minimal transaction chain needed for `/implement` to consume receipts and for the commit hook to refuse missing/stale/wrong-subject evidence;
- migrate one additional control family at a time;
- migrate legacy logging fact families only when a released control needs them, removing each old writer/reader/registration in the activation change;
- update the architecture, runbook, command/user reference, control inventory, issue ledger, and changelog in the same activation that changes their facts; `NO_DOC_IMPACT` is permitted only under the floor below. Projection generation is added only when a released route first demonstrates repeated hand-maintained duplication;
- prove a distinct retrofit consumer before `RETROFIT_PROVEN`.

Native permission migration and a multi-hop chained canary are deferred. They return only with measured evidence that they remove more decision logic or catch a fault the thin adapter and direct carrier receipts do not.

### Planning envelope

These are solo-engineering estimates, not completion claims: S0 local containment ≤0.5 day; F0 2–3 days, including the isolated trust workflow, complexity ratchet, and live four-carrier identifier census; R0 2–4 days; D0 3–5 days; K0/O0/W0 together 3–5 days; T0 2–4 days; each later M0 adapter 1–3 days. The first useful release through W0 is therefore budgeted at 10.5–17.5 engineering days. Each issue freezes its narrower estimate before work, and crossing twice that estimate triggers replanning rather than an overdue-milestone failure.

## 6. Proof protocol for every changeset

Every execution issue freezes a small table before implementation:

| Field | Required content |
|---|---|
| subject | exact files/components and expected digest source |
| denominator | declared sites plus an independent observed source |
| arms | permit, refuse, fault, and mutant |
| runner | exact executable/command/cwd/config/plugins and timeout |
| carrier | standalone, hook, CI, deploy, or consumer |
| expected | exit, selected IDs/counts, output fields, forbidden effects |
| invalidation | exact dependencies that make the receipt stale |
| promotion | observation period/sample and allowed unexplained differences |

### Runner counter-controls

A proof packet is invalid unless all hold:

1. process status is captured directly and is non-zero in the positive-red control;
2. selected and collected subjects are non-empty and equal the frozen manifest;
3. a zero-selection invocation fails;
4. a control mutation causes the expected named failure;
5. base and candidate are run by the same digest-bound runner and environment profile;
6. any runner/config/plugin difference is reported as a separate variable, not attributed to product code;
7. repeated concurrency checks run enough times to expose the preregistered race and report every exit, not a summary pipeline.

### Denominator independence

Coverage cannot use one enumerator as both numerator and denominator. Each control declares at least two differently grounded sources, for example:

- static code discovery plus settings/manifest registrations;
- declared route graph plus `executing` hook/tool IDs;
- documentation dependency declaration plus changed-subject observation.

The union is the denominator. Disagreement is `UNMEASURED` or `FAIL`. Every enumerator has a seeded missing-site control that must fail.

W0 additionally requires observed `executing` hook identity plus the exact carrier correlation key frozen by F0 because static discovery and registrations cannot establish the string-embedded shell-to-Python binding in `PreToolUseWrite-protect-sensitive.sh`. If no exact tool-invocation key is present, W0 records that carrier `UNMEASURED` rather than substituting timestamps. A seeded site of a structurally different shape must be missed by each enumerator and recovered by another source; otherwise the union is only a measured lower bound and cannot support a completeness claim.

### Shadow-to-enforcement promotion

Each adapter freezes its trigger, exact correlation key, and one volume profile before shadowing. `(session_id, tool_use_id, hook_name)` is only the initial W0 hypothesis: F0 must measure whether those fields actually exist across live hook ingress/result and dispatcher records. A **qualifying event** is one unique, non-synthetic top-level tool invocation that reaches the adapter's declared matcher and has start/completion/result evidence joined by the frozen carrier key; timestamp proximity alone never qualifies, and retries or duplicate registrations count once. If no exact carrier key exists, affected events are `UNMEASURED` and cannot contribute to promotion. A **real trigger event** is the same set excluding frozen synthetic cases. The standard profile is available only when the preceding 30 days contain at least 100 qualifying events. W0 conservatively preselects the low-volume profile because the legacy preceding-30-day proxy contains only 65 sensitive-write records, but those proxy rows do not establish a qualifying denominator: F0 measures the stricter definition, and if the low-volume floor is unreachable the W0 estimate is replanned rather than the key weakened. Later issues record their measured profile before shadowing. Promotion requires:

- at least 7 elapsed days and 100 qualifying events; or, for W0 or another preselected low-volume adapter, at least 7 elapsed days, at least 10 real trigger events, and the complete frozen synthetic corpus;
- zero unexplained decision differences;
- zero false negatives across adverse arms;
- for the default profile, at most one explained false positive and a rate at or below 1%; for an adopted low-volume profile below 100 events, at most one explained false positive and the rate is reported but is not a gate;
- current `installed`/`executing` identity, recovery receipt, and explicit user promotion.

Doc-master refusal uses the same expiry and false-positive accounting. There is no discretionary “looks stable” promotion.

### Documentation no-impact floor

`NO_DOC_IMPACT` is valid only when:

- the changed subjects were found by both denominator sources;
- a frozen known-impact corpus still returns impact;
- an always-no-impact mutant fails;
- unknown/unclassified changed subjects are non-pass;
- the rule-set digest is current and the known-impact false-no-impact rate remains zero. Each new no-impact rule must also turn a known-impact case falsely green when injected as a fault, proving that the corpus can detect added permissiveness.

## 7. Complexity and effort ratchets

Every A/spec issue records an estimate and hard budget before B/build:

- runtime modules, public commands/types/schemas/stores/registrations added;
- production, test, fixture, generated, workflow/configuration, and documentation lines added/removed;
- expected engineering days and proof runtime;
- legacy authorities/integration paths removed at activation.

Default v1 limits per adopted rung, including every issue or capability split from it, are: at most 2 new runtime modules, 1 schema, 1 CLI surface, 1 persistent store, 600 non-generated runtime lines, and 1,500 non-generated proof lines. Exceeding any limit stops the build and requires subtraction or one explicitly adopted exception for that rung; splitting work cannot reset a budget. Generated fixtures are reported separately and must come from one checked-in generator or be removed.

Enforcement extends the ceiling/high-water-mark and mutation pattern already used by `tests/unit/lib/test_vacuous_test_ratchet.py` and Issue #1660's `scripts/integration_ceiling.py`. F0 adds one machine-readable cumulative rung budget and one `control-tool-complexity-ratchet` CI step. It refuses a diff when the frozen base-to-candidate aggregate exceeds a limit, when a split issue omits itself from the rung aggregate, when a ceiling is raised without the rung's explicit exception, or when declared removals are absent. Its own over-budget, omitted-split, stale-base, and raised-ceiling mutants must turn it red. Section 7 is not a prose gate.

Promotion additionally requires:

- no net increase in decision authorities;
- no duplicate persistent fact owner;
- at least one superseded integration path removed for each newly activated path;
- a reviewer-confirmed explanation for every surviving concept and compatibility layer;
- actual effort no greater than twice the frozen estimate without replanning.

The contract kernel has a ratcheted inventory of public concepts, fields, stores, and entrypoints. Adding one requires a failing real case that cannot be expressed by the existing kernel; synonyms and adapter-local taxonomies are rejected. Each activation reports the cumulative live inventory and may consume at most the rung's single adopted exception.

## 8. Invalidation blast radius and cheap re-proof

Receipts list direct dependencies. The verifier computes and prints the affected receipt set before a change is accepted:

- a leaf adapter change reruns only that adapter's cases plus the current end-to-end route;
- a policy change reruns that policy and each active adapter;
- a kernel/schema change invalidates all dependent receipts and therefore requires an explicit blast-radius count, measured full-reproof duration, and migration/compatibility decision before merge.

The last-known-good owner remains active while a candidate shadows. Cache keys may speed unchanged dependencies but never make changed bytes current. Each rung must maintain a local leaf re-proof path with a hard 10-minute budget; exceeding it blocks activation until the path is reduced or the rung's single exception is explicitly adopted. The full active-route re-proof is measured and budgeted before kernel activation. An unbounded fan-out is a design failure, not a request for a bypass.

## 9. GitHub operating model

One program issue is the ledger. One capability/adapter issue owns the frozen acceptance table. One implementation issue owns one changeset. Issues link immutable plan/case bytes rather than copying mutable acceptance prose.

Before execution resumes, the program issue checklist and linked commit statuses are the administrative ledger; §9 does not claim a runtime decision. CI verifies that every implementation issue named by the rung is present in the machine-readable aggregate, while issue closure remains human-authorized:

1. comment on #1757 that v11 remains current authority but successor work is paused pending v12 adoption;
2. mark #1760 candidate `7eaffbec...` as rejected-for-size, preserving its evidence and branch;
3. consolidate #1755/#1758/#1759 under D0 with explicit overlap dispositions; do not close user-created issues without approval;
4. keep #1673 as the containment/migration ledger, explicitly mark its old "0 of 4 settings" claim stale, and record local S0 evidence plus remote/real-Serena `UNMEASURED` status;
5. use open #1521 as the existing source-to-installed copy-consistency owner and open #1522 as the duplicate-registration/execution owner, linking both to closed #1483; do not create a duplicate fan-out issue or route the work to unrelated #1641;
6. give every later issue an estimate, complexity budget, promotion trigger, denominator counter-control, invalidation set, and consumer profile.

## 10. Adoption and immediate authorization

This section is a human authorization boundary, not an automated product gate. Before requesting adoption, complete at least three independent plan-critic rounds, run the final round over pinned commit bytes, and record every review verdict/digest on #1757. The exact user text and GitHub's append-only history are the authority; no model or candidate writes an adoption decision. Adoption text:

`I adopt control-tool v12 commit <FULL_COMMIT> with SHA-256 <FULL_SHA256>, supersede the v11 adoption recorded at #1757 comment 5562381846 including P0-A authorization, accept S0 local containment with remote and real-Serena carrier UNMEASURED, reject P0-A candidate 7eaffbecfdff7a253d937dc786a337496133a811 for size, and authorize F0 only.`

That line authorizes only the F0 bootstrap artifacts. R0 implementation requires a later exact authorization of the frozen F0 commit and digest. Neither line promotes a candidate, waives an unmeasured carrier, closes an existing issue, or authorizes paid infrastructure.
