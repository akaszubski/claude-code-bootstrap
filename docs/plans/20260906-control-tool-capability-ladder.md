# Control-tool capability ladder — build the instrument before wiring the system

**Status:** PROPOSED v11 — incorporates the plugin-native prerequisite in [`20260907-plugin-native-distribution-amendment.md`](20260907-plugin-native-distribution-amendment.md), which must release the private observer/carrier before C0-A; then promotes the improved execution-observation method into a standalone canonical observation journal and early autonomous-dev cutover while retaining the bounded bootstrap recorder, direct hook-identifier binding, complete settings provenance, universal assurance transaction, authenticated-carrier boundary, external bootstrap overlay, and durable-rung/execution-child split

**Date:** 2026-09-06

**Governing intent:** [`PROJECT.md`](../../PROJECT.md), especially INV-1, INV-5, INV-6, INV-7, INV-8, Q1, and Q2

**Product decision:** `autonomous-dev` is a local control-assurance tool with Claude Code integrations. It is not a Claude Code hook solution with supporting utilities.

**Bootstrap decision:** until the tool is trustworthy enough to judge later work, a smaller independent promotion overlay judges the tool from immutable criteria and raw observations; the candidate never certifies itself.

**Execution rule:** build and prove one standalone capability, connect it to one real trigger in report-only mode, prove that carrier and rollback, activate it as the sole decision owner, remove the superseded owner, and only then start the next rung.

**Carrier prerequisite:** the current `/implement` and Claude plugin carriers are not reliable enough to construct C0-A under its own isolation contract. The separately reviewed plugin-native prerequisite therefore runs P0 through P3 first. It changes distribution and execution plumbing, not the C0/C0O/C0T capability semantics, and each prerequisite rung has its own immutable A/B/C cases, hard smoke route, independent packet, recovery rehearsal, and explicit user promotion.

## WHY + SCOPE

The repository-integrity audit remains valuable: it found disconnected hooks, multiple authorities, stale claims, source/install skew, shallow tests, weak provenance, and controls that exist without evidence they operate. Its proposed Bootstrap B0 is nevertheless still solution-shaped. B0 asks one change program to introduce a proof capability, connect `/implement`, CI, deploy, and phase closeout, exercise a fresh Claude process, and replace old acceptance authority before any part has an independently stable contract.

That creates the failure pattern this repository is meant to prevent:

- the capability cannot mature independently of the first integration;
- a defect cannot be localized to core logic, adapter, carrier, deployment, or observation;
- activation requires trusting several new edges at once;
- rollback restores a whole solution rather than one decision boundary;
- the next migration begins before the instrument used to judge it is trustworthy;
- useful mechanisms become large because every trigger-specific concern is pulled into their core.

The correction is not to discard the audit or to add another framework. It is to turn the desired assurance behavior into a small product, then make existing workflow elements clients of that product.

## 2. Product boundary

The proposed product interface is a thin local CLI, provisionally named `adevctl`, over small pure-Python capability modules:

```text
policy / adopted criteria / canonical declarations
                       |
                       v
       +----------------------------------+
       | standalone control capabilities |
       | pure inputs -> typed result      |
       +----------------------------------+
                       |
                       v
              adevctl JSON contract
                       |
            canonical, bound receipt
                       |
        +--------------+--------------+
        |              |              |
        v              v              v
   /implement         CI        deploy / health
     adapter        adapter          adapter
        |              |              |
        +---------- real triggers ----+
```

The core does not import command Markdown, hook scripts, GitHub APIs, deployment scripts, Claude Code settings, or agent definitions. Adapters may invoke the CLI; the CLI never invokes an adapter. A hook is a transport adapter, not the owner of policy, path extraction, evidence semantics, or telemetry.

The canonical durable operational record has two disjoint owners over the same C0 receipt encoding: C0O's observation journal owns what runtime event was durably observed, and C0T's transaction chain owns whether a governed change may advance or promote. Transaction records reference exact observation-receipt digests; an observation never authorizes a transition by itself. Native transcripts, bounded bootstrap captures, debug/stream output, and test reports are external inputs or corroborating witnesses; activity/timing/session views, summaries, dashboards, and issue comments are read-only projections. No projection or aggregate count may authorize a transition, no fact may have two authoritative stores, and the current append-mode activity/archive/telemetry sinks are migration sources rather than final architecture.

This is a two-tier library design:

1. **Core:** deterministic functions over explicit data, with no ambient repository discovery when an explicit root/subject is supplied.
2. **CLI:** validation, bounded subprocess execution, canonical JSON, exit codes, and human diagnostics.

There is no dynamic plugin framework, network service, external database, dashboard, second pipeline, or new specialist agent. C0O's bounded local SQLite journal is the sole runtime-event store; declared operational state stores remain separate, and C0T later owns a disjoint transaction chain. New capabilities are ordinary explicit modules and subcommands. Existing mechanisms are reused behind the contract only when their behavior and ownership are proven; their current APIs and file boundaries are not preserved merely for compatibility.

The same contract applies to any software repository. A repository supplies an explicit versioned profile naming its policy sources, subject root, supported runners, documentation owners, and integration carriers; the core does not infer those facts from Claude-specific paths. Claude Code agents, hooks, and commands are one adapter family. A repository with no agents or hooks can use the identical case manifests and receipts from a shell, CI job, or another orchestrator.

## Existing Solutions

The repository already contains partial capabilities. They are evidence and reuse candidates, not proof that the new product boundary exists:

| Existing mechanism | Keep/reuse | Current limitation |
|---|---|---|
| `plugins/autonomous-dev/lib/goa_cli.py` | precedent for a useful CLI before trigger activation | narrow scheduled-health product; prints manual trigger instructions and is not a general control contract |
| `plugins/autonomous-dev/scripts/proof_of_block.py` | subprocess transport, permit/refuse/fault idioms | specialized internal model and receipts; direct subprocess is not proof of registration/runtime dispatch |
| `scripts/mutation_witness.py` | bounded mutation, restoration journal, verdict classification | separate claim format and disputed/stale reachability statements; not a common acceptance contract |
| `plugins/autonomous-dev/lib/acceptance_criteria_tracker.py` | historical counterexample fixtures | presence/string-count semantics cannot establish operating effectiveness |
| `plugins/autonomous-dev/lib/pipeline_state.py` | current HMAC/state implementation as T0 adapter evidence | atomic JSON is pipeline-coupled; HMAC covers only seven fixed fields, accepts unsigned legacy state, and may accept stale invalid state; C0 receipt persistence is therefore owned separately by `assurance_contract.write_receipt()` |
| inventory, reachability, settings, and manifest validators | parsers and graph inputs after independent characterization | parallel output formats and success claims do not share one typed authority |
| closed Issue #119 bootstrap-first installer | precedent for solving a distribution bootstrap paradox with a smaller outer mechanism | installs the system but does not solve the epistemic bootstrap problem of an incomplete assurance tool judging itself |
| [in-toto attestations](https://github.com/in-toto/attestation/blob/main/spec/README.md) | field-shape precedent for subject plus predicate and signed functionary evidence | a supply-chain envelope does not define our policy claims, opposite arms, invalidation, or promotion states; keep an explicit field mapping and no runtime dependency in C0/C0T |
| [SLSA build provenance v1.2](https://slsa.dev/spec/v1.2/build-provenance) | precedent for subject, build definition, run details, and dependency/material identity | build provenance is one evidence type, not a software-policy verdict; use compatible meanings where they fit and record incompatibilities rather than claiming conformance |
| [Agent Client Protocol v1](https://agentclientprotocol.com/protocol/overview) plus maintained [Claude](https://github.com/agentclientprotocol/claude-agent-acp) and [Codex](https://github.com/agentclientprotocol/codex-acp) adapters | future precedent for a neutral supervisor to negotiate sessions, prompts, permissions, cancellation, and event transport across coding agents | adapter and negotiated-session identity do not prove the exact installed agent binary, Claude settings registration, or native hook payloads required by O0/T0; no current ladder dependency is introduced, and any later adoption requires its own D-G adapter proof with exact adapter/agent identities and rollback |
| [A2A Protocol](https://a2a-protocol.org/latest/topics/key-concepts/) | vocabulary precedent for task, context, message, state, and artifact exchange | transport lifecycle is not assurance lifecycle, promotion authority, or durable evidence; C0T's digest-bound artifact chain remains authoritative and this plan adds no A2A service or runtime dependency |
| [OpenTelemetry Logs Data Model](https://opentelemetry.io/docs/specs/otel/logs/data-model/) and [W3C Trace Context](https://www.w3.org/TR/trace-context/) | stable field semantics for event/observed timestamps, event name, severity, resource, trace ID, span ID, parentage, and cross-component correlation | use compatible semantics and golden mappings in C0O, while keeping native Claude/run/tool/agent identifiers separate; do not add an OpenTelemetry SDK, Collector, OTLP service, arbitrary attributes, sampling authority, or network dependency |
| [Claude Code hooks reference](https://code.claude.com/docs/en/hooks) and [Agent SDK hook types](https://code.claude.com/docs/en/agent-sdk/python) | documented hook input fields include `session_id`, `transcript_path`, per-call `tool_use_id`, and optional in-agent `agent_id`/`agent_type`; local Claude Code 2.1.236 also persists main-agent hook attachments with exact command/outcome/duration and matching `toolUseID`, while a real Agent run exposed `agent_id`/`agent_type` at `SubagentStart`, on inner tool hooks, and as `agentId`/`agentType` in the outer Agent result | the transcript attachment schema is observed rather than a stable authority, omits silent-success attachments on some events, and does not attach inner subagent hooks to subagent transcripts; use persisted transcripts for execution observation only and direct live hook-input receipts for T0 authority |
| closed #907, #755, #1461, #1654, and #1718 plus the append-writer ratchet | root-cause and counterexample corpus: producer/consumer drift, missing agents, phantom events, one-armed outcome fields, 33 independent append writers, and 13 writers targeting the activity area | local repairs repeatedly moved the defect; #1718 explicitly leaves collapsing the 13 activity writers as follow-on work, so C0O/O0 own the class rather than another per-logger repair |
| `conversation_archiver.py`, `session_activity_logger.py`, `hook_telemetry.py`, `hook_timing.py`, `session_telemetry_reader.py`, and other append-mode telemetry producers; open #1728, #1726/#1697, #1716, #1419, #1543, #1674, #1635, and #1522 | migration inputs, recovery fixtures, and current reader requirements | the stores disagree in both directions and cannot distinguish several missing paths from success; C0O replaces their event model/store and O0 migrates each fact family, switches its readers, removes its legacy writer/registration, and preserves old bytes only as explicitly untrusted historical evidence—no aggregator, dual authority, or indefinite legacy projection |
| open Issue #1749 | bounded live stale-test fixture: a test requires `plan_gate` in `settings.local.json` although #1183 intentionally made that hook block empty | fix independently without restoring duplicate registration; retain its missing/exactly-one/duplicate arms as C4/C5 regression evidence |

C0 does not copy or extract the pipeline-state writer. It owns one receipt-specific `assurance_contract.write_receipt()` implementation with the exact persistence semantics in section 3.3; pipeline state remains an adapter concern and no second general atomic-JSON utility is introduced.

The tool uses a deliberately narrow canonical JSON subset rather than claiming that ordinary “sorted JSON” is portable canonicalization: UTF-8; objects, arrays, strings, booleans, null, and integers only; no floats or NaN; keys sorted by Unicode code point; `json.dumps(..., ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))`; exact UTF-8 bytes hashed with SHA-256. Golden vectors include non-ASCII strings, key ordering, negative/large integers, arrays, escaped controls, and rejection of floats. If cross-language consumers later require RFC 8785, that is a versioned capability change with compatibility vectors, not an unannounced encoding change.

## 3. Stable contract established before capabilities expand

Rung C0 establishes the smallest contract every later capability and adapter must use.

### 3.1 Input

Every invocation receives explicit, schema-versioned input containing:

- `capability_id` and `case_id` or `control_id`;
- governing policy/acceptance references;
- a declared subject kind, path or identifier, optional profile, and expected digest;
- explicit declared dependency identifiers and expected digests;
- stimulus and binary oracle, including the opposite arm for conditional behavior;
- evidence level required;
- timeout, output bound, and allowed environment names;
- trigger context when an adapter invokes it.

The tool independently computes the observed subject/dependency digests where the input names local bytes; it reports declared and observed identities separately. Neither a caller-provided adapter name nor an unkeyed digest is called authenticated provenance.

Executable commands are argument arrays passed with `shell=False`, an explicit cwd constrained to the declared root, a reconstructed allowlisted environment, a resolved/allowed executable, closed stdin, bounded stdout/stderr, and a new process session whose whole descendant group is terminated and reaped on timeout. The tool never evaluates a shell string, inherits an unfiltered environment, silently changes cwd, or converts timeout, skip, missing dependency, parser failure, or zero selection into success.

C0 has two runner kinds only: `process` and `pytest_nodes`. Its closed oracle vocabulary is an AND-list of `exit_code_is`, `timed_out_is`, `stdout_exact`, `stdout_contains`, `stderr_exact`, `stderr_contains`, `stdout_json_equals`, `path_sha256_is`, and `path_absent`; `pytest_nodes` additionally requires the exact pre-collected node IDs plus passed/failed/skipped/error counts from a machine-readable result. Regex, Python expressions, shell fragments, arbitrary predicates, plugins, and natural-language verdicts are invalid. A later capability must version the schema to add another observation type.

### 3.2 Result and exit semantics

Every subcommand returns one typed state:

| State | Meaning | Exit |
|---|---|---:|
| `PASS` | The declared oracle passed on the exact subject and dependencies | 0 |
| `FAIL` | The tool ran and observed the counterexample or failed oracle | 1 |
| `INVALID` | Input/schema/selection is malformed, empty, ambiguous, or conflicting | 2 |
| `UNMEASURED` | The required carrier or observation was unavailable | 3 |
| `BEHIND` | Receipt or declared subject/dependency digest differs from independently observed current bytes | 4 |
| `ERROR` | The tool could not complete its own operation safely | 5 |

Only `PASS` permits an enforcing adapter. Report-only adapters attempt durable persistence for every state and surface persistence failure as `ERROR` with no receipt; they never translate a non-pass state into enforcement until activation is approved. Human output is a projection of the typed result, never an independent verdict.

### 3.3 Receipt

Canonical JSON receipts contain only the generic C0 facts required by every later capability:

- schema and tool contract version;
- capability/control/case and policy references;
- tool source digest and caller-declared adapter identity, if any;
- declared and independently observed subject identity/profile/digest;
- sorted declared and independently observed direct dependency identities;
- expected and observed outcomes for every required arm;
- start/end time, monotonic duration, bounded output digests, and explicit omissions;
- caller-declared trigger/carrier identity and invocation ID when present;
- state, ordered reason codes, and receipt integrity digest.

Receipts are immutable observations, not current status. C0 detects byte mismatch by recomputing explicitly named local subjects/dependencies; delivery semantics are C1 and policy-claim currency is C4. The unkeyed receipt digest proves integrity against accidental or later byte change, not author authenticity. Its preimage is the narrow canonical JSON encoding of the complete receipt with the `receipt_digest` key omitted; the stored digest is lowercase 64-character SHA-256 hex, and verification removes that key and recomputes. Authenticated provenance is a separate observed carrier credential or keyed signature and remains `UNMEASURED` when none exists.

C0 owns mandatory receipt persistence through one `assurance_contract.write_receipt()` implementation used by `adevctl --receipt`. It performs same-directory temporary creation, full write/flush/fsync, mode `0600`, atomic replace, and best-effort parent-directory fsync; it removes the temporary on failure. This is receipt-specific, not a second exported general JSON writer, and C0 does not change pipeline state. The CLI also returns the typed result on stdout; if durable persistence fails, it emits an `ERROR` decision with `receipt_persisted: false` on stdout/stderr and leaves no success receipt. An enforcing adapter must fail closed from that decision channel. T0 adds a versioned strict pipeline state whose HMAC message actually includes the receipt digest and whose gating verifier rejects missing/invalid signatures; legacy fail-open state can remain readable only as non-authoritative history.

C0 is Python-standard-library-only at runtime. JSON Schema files are design/build artifacts checked by independent development tooling, while the installed CLI enforces the same closed fields and types without importing `jsonschema` or any site package. The manifest-only test runs Python with `-S`, removes source paths, and begins with an empty temporary user configuration.

### 3.4 Non-negotiable properties

- The same input produces the same decision apart from declared observations such as time and runtime identity.
- Empty denominators, missing arms, unknown tool effects, missing routes, and corrupt inputs cannot pass.
- Observability/persistence failure cannot change a refusal into permission; the decision channel returns `ERROR` while durable evidence is explicitly absent.
- A receipt proves only its declared/observed subject kind; C1 later defines source/stage/install/runtime equivalence.
- An adapter cannot weaken core exit semantics or manufacture `PASS`.
- Every public function and subcommand has one owner, one schema, and one testable contract.

### 3.5 Universal software-assurance transaction

Every protected change, whether to this toolkit or to consumer software, is one subject-bound transaction. The durable transaction is data, not a conversation transcript, prompt, checklist, issue body, or agent verdict:

```text
POLICY_BOUND -> CASES_FROZEN -> OBSERVERS_PROVEN -> SUBJECT_BUILT
             -> RAW_OBSERVED -> INDEPENDENTLY_REVIEWED -> DOCS_BOUND
             -> PROMOTED | REFUSED | INVALIDATED
```

The transaction manifest is frozen before protected production implementation begins and contains:

- transaction, repository-profile, policy-claim, case, and issue identifiers plus their immutable digests;
- declared subject and dependency selectors, expected pre-change identity, and invalidation rules;
- for every claim: evidence level, runner, argv, explicit root/environment, stimulus, oracle, opposite arm, counterfactual or mutant, timeout, and required raw observations;
- named role authorities, including who may propose, freeze, build, observe, review, document, and promote;
- an explicit frozen documentation/projection impact set and the expected final-subject binding; C4 may later derive and verify that set from the released graph without changing transaction semantics;
- every permitted omission as an explicit `UNMEASURED` item, never an implicit pass.

For new behavior, the observer must fail against the pre-change subject or a bound negative fixture. For preserved behavior or refactoring, a deliberate mutant/counter-control must prove the observer can turn red. A criterion, oracle, fixture, threshold, or observer changed after implementation results exist invalidates the transaction and requires a superseding preregistration; history remains immutable.

Agent separation is mechanical where the carrier can prove it and explicitly unmeasured where it cannot. The core always verifies the allowed transition, predecessor, artifact, and subject digests; it records caller-declared role separately from any adapter-observed authenticated carrier identity. Preventive write isolation belongs to a capable adapter such as Claude hooks or CI permissions, while a generic shell profile can provide only after-the-fact digest detection unless it supplies an authenticated carrier. Missing or unverifiable identity is `UNMEASURED`, never silently promoted to authenticated provenance. Agent prose can explain a typed observation but cannot create `PASS`, waive a failed deterministic case, change promotion state, or substitute for missing raw evidence.

The generic role contract is:

| Existing role | Required input | Required artifact | Forbidden authority |
|---|---|---|---|
| planner | policy/profile plus discovered scope | transaction and case-manifest proposal | implementation, observation, or promotion |
| plan-critic | proposal plus policy and independent prior art | critique and frozen-spec recommendation bound to exact digests | post-result criterion weakening |
| test-master | frozen cases without candidate implementation details | executable observers, fixtures, and red/mutant sensitivity packet | editing criteria or production code |
| implementer | frozen cases/observers and approved scope | changed subject plus build diagnostics | editing frozen inputs or self-verdict |
| spec-validator | frozen cases and independently runnable observers | raw observation packet and typed comparisons | trusting implementer summaries or overriding deterministic failure |
| reviewer/security-auditor | final subject, diff, policy, and raw packet | typed defects, risks, and invalidation requests | waiving failed or missing evidence |
| doc-master | graph-derived impact set and final subject/receipt digests | updated documentation/projections and semantic observations | choosing its own denominator or asserting currency from prose |
| continuous-improvement analyst | complete transaction/event stream | post-run process findings and proposed future cases | current-run promotion |

Skills provide one canonical assurance method plus domain-specific case/observer templates; they do not duplicate the workflow, result states, role authority, or forbidden-action lists. Prompts become thin role adapters that name exact schemas and digests. Hooks become thin carrier adapters that verify current receipts and propagate typed exits. CI, deploy, and health consume the same contract. Independence derives from frozen inputs, isolated execution, distinct raw observations, and mutation sensitivity—not from giving two agents different names.

The four product qualities are therefore mechanically testable:

| Quality | Required property | Refusal example |
|---|---|---|
| accurate | every promoted claim has a falsifiable case, sensitive observer, raw result, and exact subject binding | aggregate green but opposite arm, mutant, authenticated carrier where required, or real trigger missing |
| simple | one schema, one policy owner, one decision owner, and thin adapters; removal accompanies replacement | duplicate extractor, registry, prompt rule, or enforcement owner |
| durable | immutable history, explicit invalidation, installed/runtime identity, bounded failure behavior, and rehearsed recovery | current receipt depends on changed bytes or recovery was not exercised |
| consistent | the same contract and result semantics across local, CI, deploy, health, and supported hosts; projections are generated or checked | source/installed or Claude/Codex projection differs without a declared transform |

## 4. The repeatable rung

Every capability follows the same seven transitions. One durable rung issue owns one standalone capability (A–C) or one adapter (D–G), never both. Every protected changeset underneath that rung uses its own execution child issue and owns exactly one transition or indivisible owner-switch package. The rung issue is never passed to `/implement`: `/implement` automatically injects `Closes #N`, so using a rung issue as its carrier would confuse “a changeset landed” with “the capability was promoted.” An execution-child close is implementation evidence only; the rung remains open until its independently defined release state exists.

| Transition | Required evidence | State after success |
|---|---|---|
| A. Specify | frozen input/result/receipt schema, threat model, acceptance cases, old behavior characterization | `SPECIFIED` |
| B. Build | pure core and thin CLI; no production trigger changed | `BUILT` |
| C. Prove standalone | parser/linter, unit, CLI subprocess, both-arm, fault, tamper, timeout, and mutation cases | `STANDALONE_RELEASED` |
| D. Add one adapter | one real caller invokes the identical CLI contract in report-only mode | `SHADOWING` |
| E. Prove the trigger | actual carrier fires on exact installed/runtime subject; missing/wrong carrier controls fail | `TRIGGER_PROVEN` |
| F. Activate | one decision owner switches; rollback is rehearsed; superseded owner is removed or made non-authoritative | `ACTIVE` |
| G. Stabilize | full acceptance rerun, current receipt, docs/changelog transaction, no unexplained differential | `ADAPTER_RELEASED` |

No work starts on transition A of the next peer capability until all planned adapter rungs for the current capability are `ADAPTER_RELEASED`. A dependency-neutral kernel with no direct production adapter may feed one explicitly named standalone capability before that capability receives its first adapter; the sole initial sequence is C0 -> C0O -> O0a -> O0b -> O0c -> O0d -> C0T -> T0. Multiple adapters for one capability are separate D–G issues and are added sequentially. The old control remains the sole enforcement owner during shadowing; the new adapter may observe but cannot enforce. At activation, there is no dual-enforcing interval.

### Change-size limits

- One new capability or one new trigger per protected changeset.
- One enforcement-owner switch per activation changeset.
- No capability may require all future adapters to exist.
- No adapter may contain business/control logic beyond input translation and result translation.
- No compatibility layer survives without a named external caller, removal condition, and expiry issue.

## Testing Strategy

The test object is the claim, not the file or function. Each acceptance criterion names the subject, carrier, stimulus, expected observation, forbidden effect, opposite arm, counterfactual, proof level, runner, timeout, and invalidation rule before implementation.

### 5.1 Evidence levels

| Level | What it proves | Minimum counter-control |
|---|---|---|
| P0 — structural | schemas, AST/import graph, settings/workflow syntax, generated parity | corrupt schema or removed edge is rejected |
| P1 — core | pure capability semantics | closest permit/refuse or current/stale opposite arm |
| P2 — CLI | fresh subprocess, real files/stdin/stdout/exit codes | timeout, empty selection, wrong cwd/profile, tampered receipt |
| P3 — adapter | adapter invokes the same contract without semantic translation | adapter removed, wrong key, ignored exit, duplicated owner |
| P4 — trigger | actual Claude/CI/deploy/health carrier fires | disabled registration, wrong settings source, stale installed byte |
| P5 — consumer | clean installed consumer behaves on exact shipped bytes | source fallback, missing manifest member, clean-clone or rollback failure |

A higher level does not erase lower-level failure. `UNMEASURED` is honest evidence state and never activation evidence.

### 5.2 Required validation dimensions

Every activation packet answers all six dimensions separately:

1. **Design:** does the declared control cover the policy/criterion?
2. **Logic:** does the core return the right result on both arms and dependency faults?
3. **Connectivity:** did the intended entrypoint reach the intended capability exactly once?
4. **Deployment:** were the proved bytes/profile the bytes/profile actually loaded?
5. **Observability:** did the decision channel report every fail-open, timeout, and observation failure, and—when persistence succeeded—does the immutable receipt match it? Sink failure must explicitly report that no durable receipt exists.
6. **Provenance/currency:** can the receipt be bound to exact inputs and invalidated after any relevant change?

Aggregate suite green, coverage, test count, file presence, issue checkboxes, agent prose, and log volume cannot satisfy any dimension by themselves.

### 5.3 Bootstrap assurance overlay and anti-self-certification

The build temporarily has two distinct systems:

1. **Candidate tool:** the new `adevctl` capability being built.
2. **Bootstrap assurance overlay:** a deliberately smaller promotion procedure that does not import, call for its verdict, or trust the candidate's decision code.

This avoids an infinite regress. The overlay is not a second product, runtime library, registry, hook, or framework. It is one bounded test-only package: one promotion executor, `tests/bootstrap/run_control_tool_bootstrap.py`; one Claude capture/reconciliation helper, `tests/bootstrap/observe_claude_execution.py`; one frozen supplemental-settings fixture; and one packet schema, `tests/bootstrap/control-tool-bootstrap-packet.schema.json`. P0-A first releases the generic data-only observer and its carrier fixtures under the plugin-native prerequisite. C0-A binds that exact released digest unchanged, adds the C0-specific driver/schema/fixtures, and freezes the combined package before candidate code exists. The package cannot import candidate modules, is never installed, exposes no extension/provider API, accepts only the closed C0 case manifest, and is never called by production adapters. Its only durable repository output is a bootstrap packet under `docs/audits/proofs/control-tool-bootstrap/<candidate-commit>/bootstrap.json`.

#### Separation of authority

| Plane | Owner | May do | Cannot do |
|---|---|---|---|
| Specification | adopted plan, C0-A manifest, user, plan-critic | freeze claims, cases, subjects, counterfactuals, thresholds, and invalidation | inspect candidate results and then weaken criteria |
| Construction | implementer in later C0-B run | implement against immutable inputs, supply diagnostics | edit bound schemas/cases/fixtures or promote itself |
| Observation | frozen bootstrap driver invoking standard parsers/digest tools, direct subprocess/native carrier, mutation controls | produce raw bytes, exits, process state, installed identities, and mutant outcomes | import candidate modules or consume the candidate's summarized verdict as its observation |
| Adversarial judgment | fresh spec-validator/reviewer/security/doc-master/CIA perspectives | challenge omissions and compare raw observations to adopted criteria | override a failed deterministic case or manufacture missing evidence |
| Promotion | user-bound adopted plan plus deterministic packet result | release, reject, or require a new preregistration | infer success from agent consensus, aggregate suite green, or candidate self-report |

Agents add scrutiny but are not roots of trust. Independence comes from different inputs and mechanisms: immutable criteria written before implementation; the frozen driver running in a verifier process whose import audit and `sys.path` exclude candidate modules; standard SHA-256 recomputation over raw bytes; direct process/OS observations; a clean manifest-only install; real-carrier invocation; and mutations that prove each deciding observation can turn red.

#### Minimal trusted base

C0-A records exact executable path, version, and where practical digest for `git`, `python3`, the OS/platform, `shasum`, Ruff, pytest and any parser/linter used by the overlay. It records which claim each tool independently observes and forbids one derived output from serving as both candidate result and external oracle. It also freezes and hashes the driver, observer, observer-settings fixture, and packet schema; proves the driver and observer reject imports from `plugins/autonomous-dev/lib` and `plugins/autonomous-dev/scripts`; and runs mutation controls against each decision class before candidate construction. Runtime C0 remains stdlib-only; development tools are part of the observed bootstrap environment, not product dependencies.

The frozen driver recomputes at least these claims without importing `assurance_contract`, `assurance_case`, or `adevctl`:

- plan, case-manifest, schema, fixture, candidate-source, staged, and installed digests;
- schema rejection of malformed/unknown/empty inputs;
- exact pre/post pytest node collection and skip/error counts;
- process cwd/environment, child termination, output bounds, and exit states from OS-visible facts;
- source-free `python3 -S` execution from a manifest-only install;
- receipt canonical bytes and SHA-256 from the frozen encoding formula;
- one deliberately broken instance of every decision-bearing observation, with the expected raw failure retained;
- recovery to the exact pre-mutation/pre-promotion digest.

The bootstrap packet records raw observation, candidate claim, comparison and status separately. If candidate output and an external observation disagree, the packet is `INVALID`; neither side wins by precedence. The case is investigated, corrected through a new immutable preregistration when necessary, and rerun in full. Negative and inconclusive results remain in the packet. The driver may emit `BOOTSTRAP_PASS`, but it cannot emit `STANDALONE_RELEASED`.

Every manifest entry binds two distinct identifiers: candidate test node `C0-Cnn` and frozen external oracle `BOOT-Cnn`. The candidate node is useful diagnostic/self-check evidence; only the bootstrap driver may execute the corresponding `BOOT-Cnn` raw observation. Candidate and external paths may share fixtures and immutable expected bytes, but they may not share verdict code. For deterministic cases the required result is exhaustive agreement over the frozen fixture/mutant matrix, not a statistical confidence claim; sampled timing claims separately report population, sample count, distribution and uncertainty as specified in the trigger protocol.

#### Bootstrap and self-hosting rule

- **C0-B construction:** the candidate may emit only `CANDIDATE_PASS` or a non-pass state; it cannot emit `STANDALONE_RELEASED`.
- **C0-C proof:** the frozen C0-A driver runs against the immutable C0-B candidate commit and emits the independent packet. Only an explicit user promotion record that cites a `BOOTSTRAP_PASS` packet, exact candidate commit, plan digest, driver digest, case-manifest digest and packet digest creates `STANDALONE_RELEASED`.
- **New leaf capability:** the last released `adevctl` version (N-1) may check unchanged contract/integrity rules for candidate N, but targeted independent observations must still prove the new behavior.
- **Adapter-only change:** the released capability digest stays fixed; the overlay concentrates on the actual carrier, installed subject, exit propagation, evidence sink, timing, and recovery.
- **Kernel change:** any change to canonical encoding, schemas, result states/exits, runner isolation, receipt persistence/verification, CLI dispatch, or strict signing returns the staged candidate to the full C0 overlay. Installed N-1 and its subject-bound receipts remain production authority throughout evaluation; staged N cannot invalidate or replace them.

Version N can never be the sole authority that promotes version N. N-1 is useful compatibility evidence, not sufficient proof; for the first version there is no N-1 and the overlay supplies all promotion evidence. Only after staged N passes the overlay, every affected adapter passes shadow/real-carrier proof, and one atomic owner switch activates N do receipts whose runtime tool/kernel dependency changed become `BEHIND`; unaffected receipts retain their own dependency-derived status, N-1 receipts become historical evidence, and rollback re-establishes N-1 authority only after exact subject re-verification.

#### Retirement and permanence

After C0 release, manual duplication retires case by case only when the released tool reproduces the observation and an independent mutation proves the replacement detects its own absence or corruption. Each retired step is recorded with its tool-owned replacement and recovery path. The full overlay is no longer run for ordinary adapters or unchanged leaf capabilities, but its frozen driver, Claude observer/settings fixture, packet schema, immutable fixtures and raw-oracle commands remain the permanent re-entry suite for every kernel or Claude-carrier change. They may change only in a new pre-candidate specification commit with independent review. Any new provider mechanism, product import, installed/runtime consumer, non-kernel/adapter scope, or second promotion driver is rejected; a growing second harness is a program failure.

### 5.4 Trigger proving protocol

For each adapter:

1. record old-owner decisions on a frozen truth table;
2. deploy the new adapter report-only with exact source/install digests;
3. drive the real trigger, not its function, on permit/refuse/error cases;
4. compare old and new decisions and explain every differential;
5. prove that removing the trigger, changing the payload key, changing settings source/profile, loading stale bytes, ignoring the exit code, or breaking the receipt sink is detected;
6. measure the actual carrier workload and record sample count, time window, machine/profile, cold/warm status, failures, and max; publish p95/p99 only after at least 100 representative samples, otherwise publish every observation plus median/max, and set timeouts from those data rather than inherited defaults;
7. rehearse the identical rollback vector from a clean pre-activation revision;
8. activate one owner, remove or demote the old owner, and repeat the same cases;
9. update generated projections, architecture/runbook/testing docs, and changelog in the same final-digest transaction.

## Plan adoption and execution carrier

The tracked plan is the durable authority. Until #1757 releases, authority is the exact two-document set `20260906-control-tool-capability-ladder.md` plus `20260907-plugin-native-distribution-amendment.md` from one commit; `.claude/plans/` is only the ignored byte-verified execution mirror consumed by the current `/implement` command. Publishing the proposal or issues does not create that mirror and does not authorize protected-infrastructure edits.

After the user explicitly adopts an exact commit and SHA-256:

1. update #1757, #1737, and the rung/execution issue graph from proposed to adopted authority, preserving old-plan links as history;
2. extract both committed plan blobs, not mutable working-tree bytes, with `git show <adopted-commit>:<tracked-plan-path>`;
3. write both as their named `.claude/plans/` mirrors;
4. independently verify both extracted bytes against their adopted SHA-256 values and refuse mixed commits;
5. record both source blob IDs/SHA-256 values, mirror paths, and the adoption event on #1757;
6. invoke only the P0-A execution child named by #1756 and the prerequisite; never pass rung ledgers #1756 or #1731 to `/implement`;
7. invoke `/implement #1745 C0-A` only after #1757 is closed, which requires all four explicit prerequisite promotion records and current-byte P0-P3 reruns, naming both adopted plan digests.

### Pre-T0 execution evidence recorder

Claude may execute C0-A and C0-B, but it cannot certify either changeset from its own summary or from the repository's current activity aggregates. The frozen `run_control_tool_bootstrap.py` is the sole external supervisor and cleanup owner. It launches a fresh persisted Claude process with an explicit session UUID, exact working-tree/commit identity, bounded tools and permissions, `--output-format stream-json --include-hook-events --verbose`, a dedicated debug file, and a version-proven isolated Claude configuration/session root inside the private run root described below. `--no-session-persistence` is forbidden for these runs because it removes the richer transcript record. If the installed Claude version cannot prove that isolation or writes a raw artifact outside the private root, the run is `ERROR`. Before launch the supervisor records the Claude executable/version/digest; every requested and resolved managed, user, project, local, plugin, agent/skill-frontmatter, and CLI-supplied settings source or its explicit absence; all resulting settings digests; the adopted plan digest; invocation arguments; and pre-run git state. After exit it derives bounded observations from stdout/stderr, process exit, stream/debug/transcript, post-run git state, changed-subject digests, test outputs, and every negative result, then retains only the allowed metadata and source digests in the final packet.

For main-agent actions, the supervisor joins the assistant `tool_use.id` to transcript `attachment.toolUseID` and the matching `tool_result.tool_use_id`. The bootstrap packet freezes the Claude version and exact field-path map used for that join. Every persisted hook attachment must name its exact command, event, exit code, duration, and output; the expected commands are reconciled to the hashed settings inputs, not guessed from ordering. Missing transcript, unknown/missing/ambiguous schema field, unmatched IDs, unexpected duplicate registrations, a non-zero hook exit hidden by overall session success, or an expected deciding hook with neither a joinable attachment nor a direct receipt is a named non-pass. A silent-success hook whose attachment is omitted is `UNMEASURED`, not passed; raw stream lifecycle events may show that the event occurred but cannot prove which command handled it. Neither stream timing nor the current `scripts/events_parser.py` can substitute for the ID join because the current parser hides allow events and non-blocking hook errors.

The ordinary live transcript under `~/.claude/projects/` was the primary execution-observation source for the manual schema probe; `~/.claude/archive/conversations/` is a per-Stop overwrite of that transcript and may lag by a turn, so it is a recovery copy, not an independent witness. Controlled C0-A/C0-B runs use only the equivalent transcript created under their isolated private run root; they never copy or mutate the ordinary stores. Subagent `.meta.json` records link the parent Agent dispatch `toolUseId` and declared `agentType` to a named subagent transcript, and that transcript binds its own tool calls to results, but current subagent transcripts do not persist their inner hook attachments. C0-A/C0-B may therefore use subagent transcripts to reconstruct work and compare final artifacts, but may not claim inner-hook execution, role authentication, or T0 readiness from them. Those dimensions remain `UNMEASURED` until T0's direct carrier receipts are released.

P0-A first turns the generic portion of this protocol into the frozen `tests/bootstrap/observe_claude_execution.py` deliverable and plugin-carrier fixtures named by the prerequisite. C0-A verifies and binds that released observer digest without editing it, adds the C0-specific `tests/fixtures/assurance/claude-observer.settings.json`, driver, and packet schema, and freezes the complete C0 overlay. Capture streams an opaque SHA-256 over the exact stdin bytes and records an allowlisted envelope of version, run/session, event, tool, per-call ID, agent identity, native duration when supplied, sorted top-level key/type shape, and explicit redaction/omission markers; it never copies prompt, tool-input, tool-output, environment, or file contents. The opaque hash is only a deduplication/tamper fingerprint and cannot satisfy a semantic claim whose preimage was discarded. Reconcile consumes the frozen settings inventory, stream, debug, persisted main/subagent transcript metadata, capture records, process result, and pre/post subject identities; derives lifecycle outcomes only from their named source; and emits a data-only observation fragment containing no comparison, state, eligibility, or promotion field. `run_control_tool_bootstrap.py` is the sole validator, comparison/status owner, and final packet writer under the existing bootstrap packet schema.

The supervisor uses one private run directory outside the repository/deploy tree for the child's isolated configuration/session state, stdout/stderr stream, debug log, transcript/subagent metadata, and hook-capture records. The contract freezes its parent, opaque run-root identifier, one-hour crash-retention TTL, directory mode `0700`, file mode `0600`, owner, exclusive no-follow creation, maximum total/per-file/stdin bytes and record count, atomic finalized file per event, file and parent-directory fsync, and prohibition on shared JSONL append. The supervisor bounds child pipes while draining them; overflow, partial write, collision, symlink, unexpected path escape, wrong permission/owner, fsync, parse, or finalize failure is `ERROR` and cannot pass. The observer reads these native artifacts in place and never copies their raw content. `bootstrap.json` contains only allowlisted observations, digests, result/reason fields, and a cleanup receipt keyed by the opaque run-root identifier—never raw prompt/tool/output/debug/transcript content or a sensitive absolute path.

For every terminal result, including `FAIL`, `UNMEASURED`, `INVALID`, and `ERROR`, `run_control_tool_bootstrap.py` constructs the non-final packet in memory, closes and digests every raw input, deletes the entire private run root, adds the bounded cleanup outcome, and then atomically persists `bootstrap.json` exactly once outside that root. Cleanup failure is recorded in that one final write and makes the packet non-promoting; the final packet is never reopened or amended. A crash can leave an in-progress root: one hour is its frozen stale threshold, not a wall-clock deletion guarantee. At the next explicit driver entry—capture, reconcile, cleanup, or promotion—the same driver sweeps expired roots, refuses to touch a root still held by a live exclusive owner, and blocks launch/promotion if a stale root or cleanup failure remains. Frozen tests cover single-write finalization, crash residue below and above the threshold, live-owner refusal, stale-root deletion, path escape, symlink substitution, and cleanup failure. The observer and settings fixture are hashed in the C0-A manifest, never installed, never imported by product code, never write the global activity/archive sinks, and never change a hook decision.

Before C0-B starts, the committed observer must reproduce the two documented Claude Code 2.1.236 fixture shapes and fail on missing/duplicate registration, missing/unmatched/cross-run identifiers, wrong agent or settings source, unknown/ambiguous schema, truncated/oversize record or pipe, non-zero hook hidden by overall success, omitted expected deciding evidence, unisolated or unwritable raw-artifact destination, unsafe path/mode/owner, expired crash residue, live-root deletion attempt, failed cleanup, capture mutation, and non-zero outer process. Its own construction is judged by the already recorded manual probe recipe, exact post-commit bytes, independent reviewer comparison, and these synthetic mutants; it cannot certify the commit that first introduces it. A failed recorder is `ERROR`, an unavailable required field is `UNMEASURED`, and neither state authorizes C0-B.

This recorder is external bootstrap observation, not another product library, telemetry authority, registry, or promotion authority. C0O reimplements the proved event/identity/privacy semantics as the standalone product contract without importing or calling the bootstrap observer; O0 then makes C0O the sole runtime event-fact owner and removes the current logging stack. T0 direct carrier receipts subsequently bind those observations into C0T transitions. The frozen recorder remains only as an independent kernel/Claude-adapter re-entry oracle and never writes the production journal.

The ignored mirror never becomes acceptance authority. A changed tracked plan requires a new critic verdict, commit, digest, explicit adoption event, and mirror replacement. A stale or mismatched mirror blocks execution rather than silently seeding the planner.

## Minimal Path

This order builds the measurement instrument, makes autonomous-dev use it instead of the current logging stack, and only then uses the trustworthy evidence base to build and simplify the remaining controls.

### P0–P3 — release the private native plugin carrier

Execute the exact A/B/C sequence and case identities in `20260907-plugin-native-distribution-amendment.md`: P0 private observer/run root (#1756), P1 active-only native discovery carrier (#1755), P2 bounded one-root runtime migrations (#1758), and P3 installed-consumer/fleet switch/subtraction (#1759). Every rung retains the previous production owner until its digest-bound user promotion. #1757 closes only after all four explicit promotion records and current-byte P0-P3 reruns, including `PLUGIN_CARRIER_RELEASED`; no prerequisite packet promotes C0 or changes a standalone capability contract.

### C0 — assurance kernel and executable-case runner

**Rung issue:** repurpose #1731. **Execution children:** #1745 owns C0-A, #1746 owns C0-B, and #1747 owns independent C0-C proof/promotion.

Build only the common contract plus `case check`, `case run`, and `receipt verify`. It must be useful from a shell with no Claude Code, GitHub, deploy, or hook integration. Pre-register a small fixture matrix covering pass, fail, opposite-arm omission, zero collection, skip, timeout, malformed input, environment leakage, wrong subject/profile, tamper, stale receipt, dependency loss, and tool self-mutation.

Transition A is a dedicated `/implement #1745 C0-A` run ending in an immutable C0-pre commit. It creates `tests/acceptance/control-tool-c0.json` containing the schemas' exact versions and SHA-256 digests; every C0-A fixture/golden-vector, bootstrap driver/observer/settings and packet-schema path and SHA-256; the paired candidate-node/external-oracle cases; trusted-base identities; and no production implementation. The later `/implement #1746 C0-B` run may not edit the manifest, either schema, any bootstrap file, or any bound fixture/golden vector. A necessary correction stops B/C and requires a reviewed replacement C0-A execution issue and preregistration commit rebinding all affected digests before implementation resumes. Candidate and bootstrap file ownership are deliberately small:

| Path | C0 responsibility |
|---|---|
| `plugins/autonomous-dev/config/assurance-case.schema.json` | case input schema and closed vocabulary |
| `plugins/autonomous-dev/config/assurance-receipt.schema.json` | typed result/receipt schema |
| `plugins/autonomous-dev/lib/assurance_contract.py` | canonical encoding, digest verification, typed models/results, and the one receipt-specific atomic persistence implementation |
| `plugins/autonomous-dev/lib/assurance_case.py` | bounded runner and binary-oracle evaluation |
| `plugins/autonomous-dev/scripts/adevctl.py` | thin argparse/JSON/exit-code adapter; installed standalone entrypoint |
| `tests/unit/lib/test_assurance_contract.py` | pure schema/canonical/result/integrity tests |
| `tests/integration/test_adevctl_case.py` | real subprocess/isolation/oracle/fault tests |
| `tests/e2e/test_adevctl_install.py` | manifest-only installed CLI without source fallback |
| `tests/fixtures/assurance/` | frozen non-production subjects, cases, mutants, and golden JSON vectors |
| `tests/acceptance/control-tool-c0.json` | immutable C0-pre case manifest; B/C reads but cannot modify it |
| `tests/bootstrap/run_control_tool_bootstrap.py` | frozen test-only independent executor; never installed and never imported by product code |
| `tests/bootstrap/observe_claude_execution.py` | P0-released, digest-bound unchanged by C0; frozen test-only hook-event capture/reconciliation observer for C0-A/C0-B and later adapter diagnostics; never installed or authoritative |
| `tests/bootstrap/control-tool-bootstrap-packet.schema.json` | frozen schema separating raw observation, candidate claim, comparison, and promotion prerequisites |
| `tests/bootstrap/test_control_tool_bootstrap.py` | pre-candidate driver contract/import-boundary tests and one killed mutant per decision class |
| `tests/fixtures/assurance/claude-observer.settings.json` | frozen supplemental settings used only by controlled Claude child processes; no production registration |
| `docs/audits/proofs/control-tool-bootstrap/<candidate-commit>/bootstrap.json` | C0-C immutable evidence packet produced after candidate construction; not candidate source or a runtime input |
| `plugins/autonomous-dev/config/install_manifest.json` | adds only the proved C0 files to the P3-released standalone manifest; no settings, hook, command, or workflow registration |

No `__main__` package, dynamic provider registry, command Markdown, hook, settings entry, CI workflow, deploy call, or pipeline-state change is in C0.

The immutable C0 case manifest pre-registers these minimum candidate nodes and their distinct `BOOT-C01` through `BOOT-C12` external oracles. Each external oracle independently observes the stated outcome using the frozen driver; it does not invoke the named candidate test as its verdict:

| Case | Exact node | Required oracle / counterfactual | Budget |
|---|---|---|---:|
| `C0-C01` | `tests/unit/lib/test_assurance_contract.py::test_schema_rejects_empty_ambiguous_and_unknown_fields` | valid minimal case parses / empty, duplicate, ambiguous, or unknown fields are `INVALID` | 5s |
| `C0-C02` | `tests/unit/lib/test_assurance_contract.py::test_canonical_json_golden_vectors_and_float_rejection` | every golden byte/digest matches / key-order, Unicode, escape, integer mutation changes digest and float rejects | 5s |
| `C0-C03` | `tests/unit/lib/test_assurance_contract.py::test_result_states_have_one_stable_exit_code` | six states map exactly / unknown state and `PASS` with reasons refuse | 5s |
| `C0-C04` | `tests/integration/test_adevctl_case.py::test_process_uses_no_shell_explicit_root_and_rebuilt_environment` | argv reaches allowed executable with exact cwd/env / shell metacharacter, cwd escape, secret inheritance, and disallowed executable refuse | 10s |
| `C0-C05` | `tests/integration/test_adevctl_case.py::test_timeout_kills_descendants_and_bounds_both_output_streams` | process group is reaped and outputs bounded / surviving child, unbounded stream, or timeout reported as pass fails | 15s |
| `C0-C06` | `tests/integration/test_adevctl_case.py::test_binary_oracle_requires_expected_and_opposite_arms` | both named arms produce expected observations / missing arm, wrong exit, zero collection, skip, or collection error refuses | 15s |
| `C0-C07` | `tests/integration/test_adevctl_case.py::test_declared_and_observed_subjects_cannot_substitute` | declared and computed bytes/profile agree / wrong digest, dependency, subject, or profile is `BEHIND` | 10s |
| `C0-C08` | `tests/integration/test_adevctl_case.py::test_receipt_integrity_detects_tamper_without_claiming_authenticity` | unchanged receipt verifies and authenticity is null / result, output, subject, dependency, or caller mutation fails integrity | 10s |
| `C0-C09` | `tests/integration/test_adevctl_case.py::test_receipt_sink_failure_returns_error_on_decision_channel` | persistence succeeds at restrictive permissions / unwritable, partial, replace, or permission failure returns `ERROR` and no durable-success claim | 10s |
| `C0-C10` | `tests/integration/test_adevctl_case.py::test_candidate_exposes_observable_kernel_mutants` | candidate exposes the frozen inputs/outputs needed for independent observation / result, digest, timeout, environment, import boundary, or oracle mutant survives or cannot be externally distinguished | 45s |
| `C0-C11` | `tests/e2e/test_adevctl_install.py::test_manifest_only_install_runs_without_source_fallback` | copied manifest files run under `python3 -S` for `--version`, case, and verify with source/site paths excluded / omitted file, extra file, third-party import, or source fallback refuses | 60s |
| `C0-C12` | `tests/integration/test_adevctl_case.py::test_measurement_packet_records_workload_samples_and_max` | every observation plus n/window/profile/max is present / sparse p95/p99, omitted error, or inherited timeout claim refuses | 30s |

**Exit:** #1746 closes with immutable candidate bytes and at most `CANDIDATE_PASS`; this does not release C0. Under #1747 the frozen driver independently proves the standalone CLI and schema on source and a clean temporary tree built from the exact committed `config/install_manifest.json`, then writes a digest-bound `BOOTSTRAP_PASS` packet; the post-C0 run must also re-prove P3-C08 against the newly populated manifest. C0 creates no production trigger, settings entry, or adapter switch, so promotion does not invoke a deployment script or alter a live owner. Only the explicit user promotion record creates `STANDALONE_RELEASED`. Recovery keeps the recorded N-1 standalone release selected, removes the failed unreferenced temporary tree, verifies its digests, and requires repaired source/install/P3-C08 proof before a later promotion. Because no caller is registered, C0 failure cannot change enforcement decisions.

### C0O — standalone canonical observation journal

**Rung issue:** #1750. Its A/B execution children and independent C proof issue are created only after C0 is `STANDALONE_RELEASED`.

C0O turns C0 receipts into the product's one runtime-observation system before autonomous-dev builds more controls. It is independently useful for any local process: record a bounded typed event, verify its receipt and store chain, query it deterministically, reconcile an explicit expected-event manifest, and distinguish observed, missing, duplicate, expired, corrupt, and sink-failed evidence. The core accepts an explicit store root and has no Claude, hook, settings, GitHub, network, command-Markdown, agent, or repository-discovery dependency.

The closed v1 event envelope uses compatible OpenTelemetry/W3C meanings without claiming protocol conformance or adding their runtime:

- schema/tool identity; deterministic `event_id`; `event_name`; severity; event timestamp and observed timestamp;
- 32-hex `trace_id`, 16-hex `span_id`, and optional `parent_span_id`, always separate from native Claude `session_id`, `tool_use_id`, `agent_id`, `agent_type`, pipeline `run_id`, and transaction identifiers;
- opaque resource/repository/profile identity, exact producer and registration identity, subject/dependency digests, lifecycle phase, outcome, duration, and ordered reason codes;
- `required_for_decision`, retention class, payload-shape digest, explicit missing/redacted fields, and bounded allowlisted facts only—never prompts, tool inputs/outputs, environment values, secrets, arbitrary attributes, absolute user paths, or exception text without an allowlisted code.

`event_id` is derived from the canonical logical-event, producer-registration, phase, and native invocation identities, not wall-clock order. A repeated identifier never produces a second event: byte-identical retry returns the unchanged original receipt inside a typed operation response with `idempotent_replay: true`; conflicting bytes return `ERROR`; neither may be counted as another observation. A separately emitted event or second registration for one expected logical event is `DUPLICATE` and cannot reconcile as observed-once. Missing native identity remains explicit and cannot be fabricated from timestamps or sequence. Store sequence expresses durable append order only; trace/span parentage expresses causality.

The physical store is one stdlib SQLite WAL-backed `observations.sqlite3` journal under a caller-supplied explicit private root, plus only SQLite-owned WAL/SHM and bounded temporary files. The root and files are owner-checked, no-follow, `0700`/`0600`, and bounded; `synchronous=FULL`, transactional unique constraints, and one writer implementation own persistence. Every 100,000 records forms a logical segment whose immutable seal records count/range/root digest plus the prior segment-seal digest before the next segment becomes active. Crash recovery either restores one verified active head or returns `ERROR`; commit success followed by output/ack loss is recovered by the same event ID and returns the original receipt without another row. The core forbids event update, deletion, pruning, and ID reuse. The default profile labels an observation `EXPIRED` for decision use after 90 days while retaining and verifying its bytes; v1 does no physical retention deletion. Any future deletion requires a separately released C0O version with transaction-aware content-addressed export/pinning, non-reusable ID tombstones, and independent counter-controls; it is not part of this migration.

C0O-A measures encoded event count/bytes and SQLite page growth against the frozen producer/workload ledger, records sample window/count/failures/max and available-volume facts, then freezes numeric `max_event_bytes`, `max_store_bytes`, `min_free_bytes`, SQLite `page_size`, and `max_page_count` in the storage profile before candidate construction. It must demonstrate at least a 180-day capacity horizon at twice the directly observed worst-day count and maximum encoded-event/page-growth cost; below 100 representative events it publishes every sample and may not claim the horizon. Record preflight refuses before a transaction when the maximum event cannot fit under both the page ceiling and free-space reserve; `SQLITE_FULL`, reserve breach, growth beyond the frozen ceiling, or unavailable capacity measurement returns `ERROR` and no acknowledgement. The adapter applies the pre-/post-decision sink rules above, never auto-deletes evidence or silently raises the ceiling, and requires a newly specified profile plus recovery proof to resume after exhaustion.

The sole CLI surface is `adevctl observe record`, `observe verify`, `observe query`, and `observe reconcile`. `query` verifies segment and event chains before deterministic JSON rendering, requires explicit filters or a bounded limit, labels schema eras, and never writes. `reconcile` consumes an explicit expected-event manifest derived independently from registrations and native-carrier activity; it does not treat absence as permit, infer handler success from a lifecycle event, or merge unknown schemas. Failure to persist a required pre-decision event prevents permission; failure to persist a required post-decision event cannot undo an executed action but prevents its subsequent transaction or promotion. Diagnostic-only sink failure does not change the underlying tool decision, but it marks the session evidence `ERROR` so no downstream assurance claim can pass.

#### C0O file and case boundary

| Path | C0O responsibility |
|---|---|
| `plugins/autonomous-dev/config/assurance-observation.schema.json` | closed event, expected-event, segment-seal, retention, and reconciliation vocabulary |
| `plugins/autonomous-dev/lib/assurance_observation.py` | pure event identity, validation, trace/native-ID separation, redaction, and reconciliation semantics |
| `plugins/autonomous-dev/lib/assurance_observation_store.py` | sole SQLite persistence, global event-ID uniqueness, chain/logical-segment verification, rotation, and non-destructive expiry implementation |
| `plugins/autonomous-dev/scripts/adevctl.py` | thin `observe record/verify/query/reconcile` subcommands |
| `tests/unit/lib/test_assurance_observation.py` | schema, identity, privacy, reconciliation, and state tests |
| `tests/integration/test_adevctl_observe.py` | concurrency, replay, storage, crash, query, rotation, retention, and fault cases |
| `tests/e2e/test_adevctl_observe_generic.py` | manifest-only installed proof in a repository with no Claude assets |
| `tests/fixtures/assurance/observation/` | frozen events, expected manifests, stores, corruptions, races, and standard-field mappings |
| `tests/acceptance/control-tool-observation-v1.json` | immutable pre-implementation cases, exact nodes, subjects, fixtures, budgets, and oracle digests |
| `docs/audits/proofs/control-tool-observation/<candidate-commit>/proof.json` | released-C0 receipts plus independent raw comparisons for C0O promotion |

The exact minimum cases frozen before implementation are:

| Case | Exact node | Required oracle / counterfactual |
|---|---|---|
| `C0O-C01` | `tests/unit/lib/test_assurance_observation.py::test_closed_event_schema_and_standard_field_mapping` | valid bounded OpenTelemetry/W3C-shaped meanings round-trip / unknown fields, arbitrary attributes, raw content, secrets, paths, or incompatible ID shapes refuse |
| `C0O-C02` | `tests/unit/lib/test_assurance_observation.py::test_event_identity_is_deterministic_and_native_ids_are_not_trace_ids` | same logical producer event has one ID and explicit native IDs / timestamp ordering, native-ID substitution, missing-parent fabrication, or conflicting replay refuses |
| `C0O-C03` | `tests/integration/test_adevctl_observe.py::test_private_sqlite_store_appends_one_chained_receipt` | one bounded event commits and verifies / symlink, owner, mode, path escape, unsafe pragma, partial write, or sink fault produces no success receipt |
| `C0O-C04` | `tests/integration/test_adevctl_observe.py::test_concurrent_record_is_exactly_once_and_conflicts_are_visible` | concurrent distinct events serialize once each and identical retry returns the original receipt / duplicate registration, distinct duplicate emission, conflicting replay, lock timeout, and stale writer cannot inflate counts |
| `C0O-C05` | `tests/integration/test_adevctl_observe.py::test_crash_recovery_never_invents_or_loses_acknowledged_event` | committed event survives, uncommitted event is absent, and retry after commit-success/output-ack-loss returns the original receipt / WAL, SHM, checkpoint, fsync, or active-head corruption cannot verify |
| `C0O-C06` | `tests/integration/test_adevctl_observe.py::test_logical_segment_rotation_and_non_destructive_expiry` | 100,000-record boundary seals and links once and expired evidence remains byte-verifiable but cannot decide / early expiry, physical deletion, ID reuse, silent zero, partial seal, or old-segment rewrite refuses |
| `C0O-C07` | `tests/integration/test_adevctl_observe.py::test_query_verifies_before_deterministic_read_only_output` | explicit bounded query renders verified order and schema eras without mutation / tamper, ambient store discovery, unknown schema, unbounded query, or repeated read cannot hide or change state |
| `C0O-C08` | `tests/integration/test_adevctl_observe.py::test_reconcile_distinguishes_observed_missing_duplicate_expired_and_sink_failed` | expected logical events and handlers reconcile exactly / zero denominator, event-for-handler substitution, missing allow, duplicate, expiry, or sink failure cannot become observed/pass |
| `C0O-C09` | `tests/integration/test_adevctl_observe.py::test_measured_volume_latency_and_storage_claims_bind_workload` | every sample, failure, database growth, n/window/profile/max is retained / sparse percentile, omitted error, or extrapolated retention claim refuses |
| `C0O-C10` | `tests/e2e/test_adevctl_observe_generic.py::test_installed_observer_runs_without_claude_assets_or_source_fallback` | manifest-only Python `-S` install records/verifies/queries/reconciles a generic process trace / source import, extra file, missing dependency, or Claude asset changes semantics |
| `C0O-C11` | `tests/integration/test_adevctl_observe.py::test_capacity_and_free_space_limits_fail_without_loss_or_auto_deletion` | measured profile enforces event/page/store ceilings and reserve while retaining prior receipts / projected overflow, `SQLITE_FULL`, low space, unknown capacity, profile mutation, or attempted auto-prune returns `ERROR`, acknowledges no event, and leaves the verified head unchanged |

C0O-A freezes schema, manifest, fixtures, storage profile, exact nodes, and independent observers; C0O-B builds only the pure modules/CLI/tests; C0O-C uses released C0 from a source-free install to compare canonical logical receipt, row, chain, and seal bytes plus the recorded SQLite library version and effective pragmas—never SQLite/WAL physical file bytes—without importing candidate observation modules. Promotion follows the same candidate/bootstrap/user authority split as C0. Only `STANDALONE_RELEASED` C0O may be connected to autonomous-dev.

### O0 — replace autonomous-dev's current logging

**Migration umbrella:** repurpose #1728 as the navigation and closure ledger; it is not passed to `/implement` and is not itself an adapter rung. Four sequential durable adapter-rung issues own the exhaustive production cutover: O0a #1751, O0b #1752, O0c #1753, and O0d #1754. O0a begins only after C0O is `STANDALONE_RELEASED`; C0T waits until all four are `ADAPTER_RELEASED` and #1728 records the completed cutover.

O0 makes the new journal autonomous-dev's actual observability system, not a sidecar beside the existing one. Its preregistration freezes a writer/registration/reader/fact ledger from the AST ratchet and runtime settings: the current measured baseline is 33 append-mode writer modules, 13 targeting the activity area, plus every activity/archive/telemetry/timing/session/CIA/GOA consumer. State stores that gates actively read remain state and are not relabelled as logs merely to reduce a count. The scope-lock set is revalidated at each O0 specification commit and initially contains `pipeline_completion_state.py`, `install_audit.py`, `drain_queue_state.py`, and `cia_finding_store.py`; the formerly cited `batch_retry_manager.py` is absent and cannot remain in the denominator.

One thin `observation_adapter` maps real Claude, hook, pipeline, CI, deploy, and maintenance carriers into C0O; one minimal lifecycle hook may capture non-decision events. Decision-owning hooks emit their permit/refuse/error/timeout fact through the same adapter at the decision exit so outcome and timing cannot disagree. O0's installed profile resolves exactly one private global store root, `~/.claude/autonomous-dev/observations/v1`, before invoking the core and records an opaque repository identity at `SessionStart`, eliminating cwd-dependent split trees. Tests and generic consumers still supply their own explicit roots; the core never expands home paths or discovers a profile. Native Claude transcripts remain in place as version-scoped external witnesses for reconciliation and recovery; autonomous-dev stops copying their raw prompt/tool content into its own archive.

The preregistered producer/event/consumer ledger assigns every existing or planned event to exactly one immutable primary fact family; overlap, unknown family, or an uncovered producer is `INVALID` and stops migration. Hook-transport facts never substitute for workflow-semantic facts, and interactive workflow facts never substitute for non-session operations:

1. **O0a #1751 — Claude hook carrier:** hook invocation/lifecycle, permit/refuse/error/timeout decision, measured duration, and bypass use.
2. **O0b #1752 — SDLC workflow:** non-hook agent dispatch/completion, pipeline transition, validator result, and role-artifact production; hook calls that carry these remain O0a events, while their semantic results are O0b events with explicit causal links.
3. **O0c #1753 — session continuity:** session lifecycle, recovery, compaction/resume, and native-transcript reference metadata without copied transcript content.
4. **O0d #1754 — non-session operations:** CI, install/deploy/health, GOA/scheduled work, and observation of drain/finding queue processing outside an interactive Claude session; queue mutation, retry, lease, checkpoint, and gating state remain owned by their declared operational state modules and cannot migrate to C0O. An interactive CIA role result belongs to O0b, while later scheduled/queue processing observations belong to O0d.

Each durable issue owns one adapter D–G. Each protected D, E, F, or G changeset gets its own execution child and runs only after the predecessor rung is released:

1. **D — shadow:** register or call the C0O adapter report-only while the named family remains wholly legacy-owned; bind source/install/settings/registration identities and expected events.
2. **E — prove:** drive actual permit/refuse/error/timeout or lifecycle arms, reconcile direct receipts with the native carrier and frozen expected-handler manifest, inject missing/duplicate/wrong-agent/wrong-run/wrong-store/sink/schema/test-contamination faults, and measure latency/volume.
3. **F — switch atomically:** make C0O the sole owner for that fact family, switch every declared family reader to verified `observe query/reconcile`, and disable the matching event emissions in every legacy writer/registration in the same changeset; later families remain wholly legacy-owned and there is no dual-authority interval for either side.
4. **G — subtract:** remove the demoted family-specific writer path, compatibility adapter, duplicate registration, reader workaround, stale test, documentation claim, and obsolete hard-floor/manifest entry; a shared legacy module survives only for enumerated later families and is deleted after O0d. Repeat source/stage/install/runtime/recovery proof before starting the next rung.

Tests and development tools must always receive an explicit temporary store and a `test=true` resource identity; any write to the production store from pytest is a failing counter-control. Existing JSONL, SQLite archive indexes, and timing files are never backfilled into C0O because their duplication, attribution, and schema defects are not repairable facts. They become read-only historical evidence with an explicit untrusted-era marker, then are removed only under the user's retention policy; no current reader may fall back to them. `conversation_archiver.py`, `session_activity_logger.py`, `hook_telemetry.py`, `hook_timing.py`, `session_telemetry_reader.py`, their settings/hard-floor/manifest registrations, and all other ledger-classified telemetry writers/readers must be removed or reduced to a temporary no-write compatibility call that has a named removal child. The append-writer ratchet and a new AST/manifest connectivity guard must prove that exactly one C0O store implementation exists and that no `.claude/logs` telemetry writer or undeclared event producer returns.

`O0-SCOPE-C01`, exact node `tests/contract/test_observation_migration_scope.py::test_operational_state_stores_remain_state_and_are_excluded_from_event_migration`, is mandatory in every O0a–O0d D preregistration and G rerun. It parametrizes the revalidated scope-lock set, proves each module still owns a declared mutation plus an active gate/consumer, and fails if the migration ledger classifies it as an event writer, removes it for a count target, routes mutation through C0O, or retains a name that no longer exists. The paired positive arm proves an actual ledger-classified telemetry writer is selected, migrated, and subtracted.

**Exit:** O0a through O0d each have actual-carrier receipts for observed and missing arms and an `ADAPTER_RELEASED` receipt; all production readers use verified C0O queries; source and installed settings name one adapter/store; legacy telemetry has no active writer or fallback reader; session recovery works from native transcript plus journal metadata; the old writer count ratchet has fallen by the removed modules; and #1726/#1697, #1716, #1419, #1543, #1674, #1635, #1522, #907, #755, #1461, #1654, and #1718 each have an evidence-backed absorbed/residual/historical disposition. Only then may #1728 record `CUTOVER_COMPLETE` and C0T begin.

### C0T — standalone assurance-transaction lifecycle

**Issue:** #1748. Its A/B execution children and independent C proof issue are created only after C0O is `STANDALONE_RELEASED`, O0a–O0d are each `ADAPTER_RELEASED`, and #1728 records `CUTOVER_COMPLETE`.

C0T is the reusable change-lifecycle capability described in section 3.5. It consumes released C0 canonical encoding, case execution, result states, and receipts plus released C0O observation receipts and verified queries without changing either contract. It has no command-Markdown, agent, hook, settings, CI, deploy, health, or documentation-review integration. O0a–O0d have already made C0O the product's event-fact owner; T0 is the first production adapter for the separate C0T transition authority.

C0T stores an append-only chain of immutable transition records rather than one mutable success flag. `transaction_manifest_digest` always means the digest of the complete frozen manifest described in section 3.5; `case_manifest_digest` is the distinct digest of its executable-case set. Each record binds both digests plus transaction/profile/policy identity; prior-record digest; requested transition; declared role; adapter-observed carrier credential or explicit absence; input and produced artifact identities; subject/dependency identities; referenced C0 case receipts and C0O runtime-observation receipts; documentation/projection impact-set digest; result; reason codes; and its own receipt digest. The core validates state order and allowed artifact classes, but never claims to authenticate a declared role. A profile may require authenticated carrier evidence for specified transitions; absence, spoof, run mismatch, or credential mismatch is `UNMEASURED` or `FAIL` according to the frozen case, never `PASS`.

The chain itself is the transaction log; C0O remains the disjoint owner of runtime event facts. `adevctl transaction inspect` is the sole read-only transition view: it verifies before rendering, emits deterministic JSON for the complete ordered transition/reason/evidence set, and resolves referenced C0O receipts only through explicit verified queries. It labels missing or expired observations rather than filling them from transcripts, historical JSONL, or aggregates; writes nothing; performs no ambient discovery; and cannot change eligibility or promotion.

The initial closed transition vocabulary is `POLICY_BOUND`, `CASES_FROZEN`, `OBSERVERS_PROVEN`, `SUBJECT_BUILT`, `RAW_OBSERVED`, `INDEPENDENTLY_REVIEWED`, `DOCS_BOUND`, `PROMOTED`, `REFUSED`, and `INVALIDATED`. `PROMOTED` is legal only from `DOCS_BOUND` with all required C0 receipts current and passing, no deciding `UNMEASURED`, and any required external promotion credential present. `REFUSED` retains the failed raw evidence. `INVALIDATED` is terminal for that chain; correction creates a new transaction identifier linked to the superseded chain.

#### C0T file and command boundary

| Path | C0T responsibility |
|---|---|
| `plugins/autonomous-dev/config/assurance-transaction.schema.json` | closed transaction manifest, transition record, role/carrier, impact-set, and chain schema |
| `plugins/autonomous-dev/lib/assurance_transaction.py` | pure transition validation, chain verification, invalidation, and promotion eligibility |
| `plugins/autonomous-dev/scripts/adevctl.py` | thin `transaction check`, `transaction advance`, `transaction verify`, and read-only `transaction inspect` subcommands |
| `tests/unit/lib/test_assurance_transaction.py` | state, chain, authority, invalidation, and promotion unit cases |
| `tests/integration/test_adevctl_transaction.py` | fresh-process transition, concurrency/replay, tamper, observer-receipt, and fault cases |
| `tests/e2e/test_adevctl_generic_repository.py` | manifest-only installed CLI over a repository with no Claude artifacts |
| `tests/fixtures/assurance/transaction/` | frozen manifests, chains, credentials, impact sets, mutants, and one case-specific external observer with no candidate imports |
| `tests/acceptance/control-tool-transaction-v1.json` | immutable pre-implementation C0T cases and exact fixture/observer digests |
| `docs/audits/proofs/control-tool-transaction/<candidate-commit>/proof.json` | released-C0 receipts plus independent raw comparisons for C0T promotion |

The exact nodes frozen before implementation are:

| Case | Exact node | Required oracle / counterfactual |
|---|---|---|
| `C0T-C01` | `tests/unit/lib/test_assurance_transaction.py::test_closed_state_machine_rejects_replay_skip_and_out_of_order` | every legal edge advances once / replay, skipped state, unknown state, and transition after terminal state refuse |
| `C0T-C02` | `tests/unit/lib/test_assurance_transaction.py::test_chain_binds_manifest_predecessor_inputs_artifacts_and_subject` | complete chain verifies / transaction manifest, case manifest, predecessor, policy, artifact, subject, or dependency mutation refuses |
| `C0T-C03` | `tests/unit/lib/test_assurance_transaction.py::test_declared_role_is_not_authenticated_carrier_identity` | declared and observed identities remain distinct / role spoof, missing required carrier, wrong run, or credential substitution cannot pass |
| `C0T-C04` | `tests/unit/lib/test_assurance_transaction.py::test_frozen_input_change_invalidates_instead_of_rewriting_history` | superseding transaction preserves prior chain / edited criterion, oracle, fixture, threshold, or observer invalidates the old chain |
| `C0T-C05` | `tests/integration/test_adevctl_transaction.py::test_observer_sensitivity_requires_prechange_failure_or_killed_mutant` | new behavior fails before change or preserved behavior kills mutant / always-green or implementation-authored substitution refuses |
| `C0T-C06` | `tests/integration/test_adevctl_transaction.py::test_promotion_requires_current_raw_receipts_and_explicit_impact_set` | all required current receipts and explicit final impact set permit eligibility / missing, stale, failed, invalid, error, or unmeasured evidence refuses |
| `C0T-C07` | `tests/integration/test_adevctl_transaction.py::test_concurrent_partial_and_sink_failures_never_create_promoted_chain` | one atomic ordered record per transition / race, partial write, broken sink, duplicate advance, or crash cannot promote |
| `C0T-C08` | `tests/e2e/test_adevctl_generic_repository.py::test_installed_transaction_runs_without_claude_assets_or_source_fallback` | installed CLI completes a non-Claude process-runner transaction / missing Claude files, source exclusion, and absent agents do not alter semantics |
| `C0T-C09` | `tests/integration/test_adevctl_transaction.py::test_transaction_inspect_is_verified_deterministic_and_read_only` | verified chain renders every ordered transition/reason/evidence identity without mutation / missing reference, tampered chain, ambient transcript/activity data, or repeated inspection cannot hide or change state |

The C0T-A specification changeset freezes the schema, case manifest, fixtures, case-specific external observer, and nodes before production implementation. C0T-B builds only the pure module/CLI/tests. C0T-C uses the already released C0/C0O tools to execute the frozen case-specific observer in a source-free installed environment and compares candidate claims with independently parsed transaction and observation bytes; the observer may not import `assurance_transaction` or `assurance_observation`. C0T is `STANDALONE_RELEASED` only after every C0T-C01 through C0T-C09 receipt and counter-control is current, the external comparison agrees, and recovery restores the prior installed C0+C0O/O0a–O0d baseline exactly.

### T0 — `/implement` adapter

**Issue:** repurpose #1732.

Convert `/implement` into the first consumer of the universal software-assurance transaction, then make the already registered `PreToolUse` git-commit gate verify the resulting receipt. Command Markdown and agent prose are producers, never enforcement authority: activation occurs only when the blocking hook refuses commit for a missing, non-pass, wrong-run, wrong-subject, wrong-manifest, invalid-role-chain, invalidated, or invalidly signed receipt.

T0 is one adapter rung but not one large changeset. After C0T is released, create four execution children and run them in order:

1. **T0-D — produce in shadow:** make planner/plan-critic/test-master create and freeze the schema-valid transaction, cases, observers, and sensitivity packet; compare with current prose criteria without enforcing.
2. **T0-E — observe the real workflow:** make implementer consume immutable inputs, spec-validator emit raw observations/typed comparisons, reviewer/security request invalidation rather than waivers, and doc-master/CIA emit their bounded artifacts against the explicitly frozen v1 impact set; prove context and write boundaries with removed-artifact, wrong-role, changed-criterion, implementation-leakage, and stale-subject controls.
3. **T0-F — activate one transaction owner:** bind the final transaction receipt into strict pipeline state; make the strict commit gate the sole decision owner; switch every decision-bearing `/implement` transition reader and writer from bootstrap/completion/prose inference to complete-chain verification and verified `adevctl transaction inspect` output over referenced C0O observations; and delete or structurally demote marker, prose, presence-based acceptance, and duplicate transaction-fact authority in the same changeset. There is no dual-authority interval.
4. **T0-G — stabilize and subtract transaction duplication:** rerun the complete workflow from a fresh installed Claude process; prove recovery; migrate diagnostic readers that still need transition facts to the read-only `transaction inspect` projection; retain native transcripts and the frozen recorder only as external diagnostics already reconciled through C0O; remove already-demoted transaction writers, readers, registrations, workarounds, and stale tests with no declared consumer; update the explicitly declared final-subject documentation; and record the remaining prompt/skill/projection duplication inventory as input to C5/T6/M0. O0a–O0d have already removed the legacy logging system before T0 begins.

Until T0-F, the existing workflow remains authoritative and the transaction is report-only. A differential is evidence to investigate, not a reason to make the new path agree with the old one. T0 does not rewrite every prompt at once: each execution child changes only the roles needed for its transition, and frozen cases prove the handoff before the next child begins.

T0-E uses one thin `transaction_carrier` adapter called from the O0a/O0b-migrated Claude hooks; it does not treat completion records, environment variables, transcripts, or SubagentStop prose as credentials. At blocking `PreToolUse` of the native `Agent`/`Task` carrier, Claude supplies `session_id`, `tool_use_id`, and `tool_input.subagent_type`; the adapter verifies the requested role and predecessor, then mints a single-use HMAC dispatch record under the current run secret/nonce. That record binds run, transaction manifest, case manifest, predecessor transition, role, dispatch `tool_use_id`, exact input artifacts, allowed output artifact class/path, and prompt digest. T0 v1 permits only one claimable/live specialist generation across the complete `(session_id, run_id)` carrier namespace: the native `SubagentStart` event must atomically claim that sole pending record with its non-empty `agent_id` and matching `agent_type`, and a missing, second, wrong-role, or ambiguous claim leaves the generation unable to write. Every subsequent in-agent `PreToolUse`/`PostToolUse` payload must carry that bound `session_id`, `agent_id`, and `agent_type`; its direct per-call `tool_use_id` pairs the permission with the resulting artifact digest. The outer Agent/Task `PostToolUse` must carry the original dispatch `tool_use_id` and return the same `agentId`/`agentType` before the transition can advance. Each carrier step first records one C0O event receipt; the C0T transition then references those exact receipt digests and appends its bounded transition fact. Missing, distinct duplicate, expired, or mismatched identifiers/observations refuse; a byte-identical transport retry resolves to the original receipt and cannot advance twice. Transcript/timestamp/FIFO or after-the-fact event-count correlation cannot substitute. `SubagentStop` remains a diagnostic C0O lifecycle event only.

| Role | Claude-observed carrier | Local issuer and verifier | Required run/artifact binding |
|---|---|---|---|
| planner | blocking Agent/Task `PreToolUse` plus in-agent write `PreToolUse`/`PostToolUse` | T0 `transaction_carrier` signed dispatch record and strict verifier | policy/profile -> transaction proposal |
| plan-critic | same carrier; exact critic prompt digest | same issuer/verifier, distinct single-use role record | proposal/policy/prior-art digests -> frozen-spec recommendation |
| test-master | same carrier; candidate production paths excluded from its declared inputs | same issuer/verifier, distinct single-use role record | frozen cases -> observer/fixture/sensitivity packet |
| implementer | same carrier; frozen input paths read-only and production output paths explicit | same issuer/verifier, distinct single-use role record | frozen transaction/observers -> changed-subject digest |
| spec-validator | same carrier; observers invoked independently of implementer summary | same issuer/verifier, distinct single-use role record | final subject/frozen cases -> raw observation packet |
| reviewer | same carrier | same issuer/verifier, distinct single-use role record | final subject/diff/raw packet -> typed review artifact |
| security-auditor | same carrier | same issuer/verifier, distinct single-use role record | final subject/diff/raw packet -> typed security artifact |
| doc-master | same carrier; writes limited to explicit frozen impact set | same issuer/verifier, distinct single-use role record | final subject/impact set -> documentation artifact digests |
| continuous-improvement analyst | same carrier; no current transaction-write authority | same issuer/verifier records observation only | complete event/receipt set -> advisory future-case artifact |

These records authenticate the local hook carrier within the repository's stated accidental-error threat model, not a human or remote principal. If the exact Claude version does not expose the required fields on a real invocation, if the blocking hook is absent, or if issuance/start/write/post-write/outer-result binding cannot be observed, that role's identity dimension remains `UNMEASURED` and T0 cannot activate. Required negative proof substitutes the coordinator, a different role, and a second same-role agent for each artifact writer; presents a correct inner or dispatch `tool_use_id` with the wrong `agent_id`; reuses a prior generation; mutates one bound input/path/prompt/run; deletes the record; races a second Agent/Task dispatch and SubagentStart claim; and sends a spoofed SubagentStop. None may write an authorized artifact or advance the chain.

The exact authority carrier is the existing per-repository `.claude/local/implement_pipeline_state.json`, upgraded to schema v2 with an `assurance` object. `pipeline_state.record_assurance_receipt()` writes and re-signs it; `pipeline_state.verify_assurance_state_strict()` is the only T0 authorization reader. Its HMAC message is the C0 canonical encoding of exactly `{schema_version, session_start, mode, run_id, explicitly_invoked, alignment_passed, alignment_verdict, nonce, assurance: {contract_version, transaction_id, transaction_manifest_digest, run_id, case_manifest_digest, transaction_chain_digest, subject_kind, subject_digest, receipt_digest}}`; only the `hmac` field is omitted. The transaction-chain digest covers every predecessor, declared role, adapter-observed carrier credential or absence, produced artifact, referenced observation receipt, impact set, and transition result. The strict reader independently loads and verifies the complete chain against both manifest digests before comparing its recomputed chain digest with signed state; it never trusts the embedded digest alone. To preserve the existing secret model exactly, HMAC-SHA256 key bytes are `(per_run_secret + nonce).encode("utf-8")`; the nonce is therefore intentionally present in both key derivation and the signed message. Missing secrets, unsigned/legacy schema, invalid HMAC, stale sentinel, run mismatch, transaction/manifest/chain mismatch, or subject mismatch fail closed for T0 even if older state readers remain backward-compatible elsewhere. `pipeline_completion_state.py` remains the independent agent-completeness carrier and cannot satisfy assurance.

Live code has no current mechanical acceptance owner at commit: the advisory tracker is written by `/implement`, read only by the pinned-unreachable `step5_quality_gate.py`, while the commit hook verifies agent-completion state. The current evidence-manifest check proves a table marker, and the spec-validator returns a prose verdict; neither binds raw observations to frozen criteria and final bytes. T0 therefore introduces the first executable-case owner; report-only results compare against those mechanisms only to expose differences, not to claim enforcement equivalence. At activation the unreachable/advisory acceptance tracker and marker/prose acceptance paths are deleted or explicitly demoted to non-authoritative projections, while the existing agent-completeness control remains separate and cannot authorize acceptance.

Exercise a fresh project-local Claude process and prove exact command expansion, role-specific context/write boundaries, immutable artifact handoffs, observer sensitivity, state/receipt creation, real commit refusal/permission, changed criteria after freeze, implementer-authored oracle substitution, missing raw evidence, wrong settings source, missing CLI, ignored result, invalid HMAC, stale sentinel, wrong run, wrong manifest, and stale installed copy. Measure before setting a budget. Activate only this boundary.

**Exit:** `/implement` has one generic assurance-transaction owner, every role is mechanically bounded to typed artifacts, the final receipt binds policy/cases/observers/final subject/docs, and rollback is rehearsed; CI and deploy remain unchanged.

### T1 — exact-SHA CI adapter

**Issue:** repurpose #1733.

Add the same C0 contract as one independent CI job plus one required-summary edge. Prove it on an actual Actions run whose `headSha` equals the candidate. Job absence, skip, `continue-on-error`, artifact loss, wrong SHA, and receipt mismatch refuse.

**Exit:** local `/implement` and CI use the same schema/evaluator but remain independent carriers.

### C1 — delivery identity and provenance

**Issue:** repurpose #1734.

Add explicit source, stage, install, runtime, profile, manifest, and dependency identities plus comparison/currency functions. This capability reads caller-supplied subjects; it does not deploy. Prove missing, extra, stale, duplicate, wrong-profile, source-fallback, and unrelated-change cases standalone.

**Exit:** `adevctl delivery verify` can distinguish design/source proof from what is staged, installed, and running without any deploy integration.

### T2a — deploy-postflight adapter

**Issue:** repurpose #1735.

Connect C1 in report-only mode to the P3-released delivery postflight: native plugin cache/registry verification for Claude profiles and manifest-built standalone-tree verification for provider-neutral profiles. Prove local staging, install, and recovery against the identical frozen target vector, then activate.

**Exit:** deployment creates the authoritative installed-subject receipt and never infers runtime truth from source.

### T2b — health adapter

**Issue:** #1738.

After T2a is `ADAPTER_RELEASED`, connect the same capability to `/health-check` and prove it on the installed subject. Health reads/recomputes installed identity; it cannot reuse deployment success as current status.

**Exit:** health independently detects later skew without becoming a second deployment owner.

### C2 — artifact/control connectivity graph

**Issue:** repurpose #1736.

C2 v1 compiles only the first released transaction route: declared policy source/profile -> C0T manifest -> frozen observers -> changed subject -> C0 receipts -> C0O runtime-event receipts -> C0T transition records -> explicit documentation impact set. It also covers the C0/C0O/O0a–O0d/C0T/T0 source, install-manifest, CLI, observation-store, command, settings, hook, and role-artifact carrier edges needed by that route. It distinguishes `declared`, `shipped`, `registered`, `reachable`, `invoked`, and `proved`, rejects duplicate owners and unknown edges, and retains evidence for dynamic edges rather than assuming them. Every supported policy-source fallback is one ordered profile rule with fixtures; commands, hooks, and libraries may not independently rediscover `PROJECT.md` or another policy source. Use current inventory and reachability logic as inputs but preserve none of their duplicate output formats. Activate a no-new-unmapped-edge ratchet for this bounded denominator; extend the graph only when the next control family is preregistered rather than attempting a whole-repository ontology in v1.

**Exit:** `adevctl graph check` proves route existence and non-vacuity standalone against fixtures and the repository snapshot; it is not yet a gate.

### T3 — connectivity CI adapter

**Issue:** #1739.

Run C2 in report-only CI, seed removal of a registration, manifest member, entrypoint edge, dynamic target, and proof edge, then activate it as the one connectivity gate. Existing inventory/count checks become projections or are removed from authority.

**Exit:** a disconnected or duplicate artifact cannot merge, and a current graph receipt names the exact failed edge.

### C3 — behavioral control proof

**Issue:** use #1587 as the governing existing epic; #1660 supplies the mutation/non-vacuity residual.

Normalize the reusable behavior in `proof_of_block.py` and `mutation_witness.py` behind the tool contract: exact subject, real subprocess transport, permit/refuse arms, dependency-fault classification, mutation witness, restoration proof, bounded execution, and explicit unsupported cases. Do not merge all tests into one large engine and do not claim hook registration from direct-script execution.

**Exit:** `adevctl control prove` works standalone for one declared control family and independently detects a surviving mutant, silent fail-open, over-block, wrong payload shape, failed restoration, and stale subject.

### T4 — phase-closeout behavioral adapter

**Issue:** #1740.

Connect C3 to one phase-closeout boundary in report-only mode and run both arms through real carriers. Activate only after exact installed/runtime subjects are observed. `/health-check` may display the receipt but does not become a second decision owner.

**Exit:** a phase cannot close because tests merely exist; its named control behavior must have current both-arm evidence.

### C4 — claim currency and documentation impact

**Issue:** #1741; #1585 and #1575 remain inputs, not new-agent requirements.

Add typed normative, derived, measured, and historical claims; direct/transitive dependency identities; `CURRENT`, `BEHIND`, `STALE`, `UNVERIFIED`, `CONFLICTED`, and `HISTORICAL` precedence; and graph-derived documentation impact. Start only with PROJECT goal/status projection and documents touched by capabilities C0–C3. Ordinary prose is not scraped into a denominator, and a `Last Updated` field is not evidence.

**Exit:** `adevctl claims check` detects the repository's known stale/contradictory fixtures and can distinguish required update, regenerated projection, grounded no-impact, and historical correction.

### T5 — documentation-transaction adapter

**Issue:** #1742.

Connect C4 to the existing documentation review/final-closeout boundary in report-only mode. The doc-master supplies semantic judgments for graph-derived narrative claims, but the tool owns completeness, subject binding, and invalidation. Prove code-after-review, test-after-review, stale generated block, missing impacted doc, false no-impact, and unavailable semantic-review cases before activation.

**Exit:** code, tests, generated projections, affected documentation, and changelog form one final-subject transaction; prose verdicts cannot override missing evidence.

### C5 — canonical projection compiler

**Issue:** #1743.

C5 v1 owns one already-proven divergent family only: `plugins/autonomous-dev/skills/planning-workflow/SKILL.md` and `plugins/autonomous-dev/skills/testing-guide/SKILL.md` are the canonical sources; `.claude/skills/<name>/SKILL.md` is a byte-identical Claude projection; `.agents/skills/<name>/SKILL.md` is either byte-identical or produced by the finite anchored replacements in `plugins/autonomous-dev/config/host_projection_transforms.json`, with every changed block recorded in a reviewed difference manifest and golden output. Unknown, ambiguous, unused, or overlapping replacements refuse generation. It does not synthesize prose or copy workflow ownership into the projections.

After that family is released and consumed by T6, later C5 versions may add one projection family at a time—settings registrations, hook metadata, install-manifest membership, command/reference indexes, count summaries, then other agent/skill/prompt projections—each with its own frozen source/destination/transform/consumer cases. There is no all-family initial compiler and no universal configuration language.

**Exit:** `adevctl project generate/check` reproduces each bounded projection byte-for-byte, explains every intentional host difference, and refuses hand-edited, stale, orphaned, or multiply owned outputs; the presently divergent source/loaded planning and testing skills are fixtures that must fail before repair.

### T6 — install/deploy projection adapter

**Issue:** #1744.

Make install/deploy consume checked C5 projections one family at a time. Prove source/stage/install equivalence, canary, and rollback for each projection before deleting its old handwritten owner.

**Exit:** deployment no longer reconciles competing settings/manifests by convention.

### M0 — vertical migration and subtraction

**First slice:** #1673, the sensitive-write control, only after C0, C0O, O0a–O0d, C0T, C1–C5, and T0–T6 are released as shown in the dependency graph.

Migrate one control family at a time:

1. freeze its policy truth table and old real-carrier behavior;
2. move pure decision logic to the appropriate capability module;
3. make the hook/function hook a thin typed adapter;
4. shadow and compare on actual payload schemas, including unknown/broad/non-filesystem effects;
5. activate one owner and remove duplicate registrations, path extractors, telemetry authority, and compatibility code;
6. rerun standalone, adapter, trigger, installed, rollback, currency, and projection checks;
7. update architecture, hook/library references, runbook, testing method, and changelog.

Function Hooks / Hooks 2.0 may replace shell or command adapters where the installed Claude Code contract is independently proven, but no core capability depends on that API. A transport upgrade is one trigger issue, not a reason to rewrite the tool.

O0a–O0d have already removed the legacy activity/archive/telemetry system before M0 starts. Each M0 family migrates only its policy decision logic into a pure capability and thin carrier, emits its runtime outcome through the existing C0O adapter, and binds any governed change to C0T; it may not create a family-specific logger, event schema, path extractor, timing sink, or fallback reader. If a required observation shape is missing, M0 stops and versions C0O first rather than reintroducing a local telemetry path.

After the sensitive-write exemplar is released, group remaining migrations by decision owner—not file type—and create one bounded issue per family. Delete unreferenced libraries only from graph evidence plus behavioral equivalence; the current measured architecture count is 238 libraries, but neither that topology nor any lower count is a target.

### P7 — installed-consumer proof and continuing assurance

**Issue:** retain #1636.

Install manifest-selected bytes into a clean consumer, run the released tool without source fallback, exercise representative real triggers, verify rollback, and schedule periodic read-only checks only after their underlying subcommands are independently released. Scheduling observes released capabilities; it never makes them correct.

## 7. Dependency graph and stop conditions

```text
C0 -> C0O -> O0a -> O0b -> O0c -> O0d -> C0T -> T0 -> T1 -> C1 -> T2a -> T2b
                                                                          |
                                                                          v
                                                    C2 -> T3 -> C3 -> T4 -> C4 -> T5
                                                                          |
                                                                          v
                                                             C5 -> T6 -> M0 exemplar
                                                                          |
                                                                          v
                                                        remaining migrations -> P7
```

The following stop the next transition:

- prior standalone or adapter rung is not in its required `STANDALONE_RELEASED` or `ADAPTER_RELEASED` state on current bytes;
- required proof is `UNMEASURED`, `BEHIND`, `INVALID`, `ERROR`, skipped, or expired;
- report-only comparison has an unexplained differential;
- the actual trigger or installed subject was not exercised;
- rollback was not rehearsed with the same deployment vector;
- a new duplicate authority or compatibility layer lacks removal criteria;
- docs/projections/changelog do not match the final subject;
- a timeout lacks current measurements or observation coverage is incomplete;
- issue acceptance criteria refer to mutable prose instead of immutable plan bytes/case IDs.

## 8. GitHub issue operating model

The program issue is the navigation ledger. This plan is the acceptance authority after explicit adoption of an exact commit and SHA-256. Durable rung issues own acceptance/state; execution child issues own exactly one protected changeset and auto-close when that changeset lands. Issues link plan rung/case IDs and evidence; they do not restate or mutate policy semantics.

Every rung issue must contain:

- one rung only: standalone capability A–C or one adapter D–G, never both;
- predecessor release receipt and successor issue;
- in-scope files/interfaces and explicit non-goals;
- pre-registered case IDs with subject, carrier, oracle, opposite arm, counterfactual, level, runner, and timeout;
- source/stage/install/runtime requirements that apply;
- observability, traceability, provenance, currency, performance, security, and rollback criteria;
- for every event fact, the C0O event owner, store/retention class, expected-manifest source, deciding-versus-diagnostic status, and verified consumer; for every transition fact, the disjoint C0T owner;
- exact closure packet fields;
- the universal transaction states and exact role/artifact authorities used by the rung;
- overlap dispositions: `absorbed`, `residual`, `independent`, `historical`, or `rejected with reason`.

Every execution child additionally names one transition/changeset, its rung parent, exact immutable inputs, produced artifact/commit, and the fact that its automatic close is not promotion. A proof/promotion step that does not require protected edits is not passed to `/implement`; this prevents automatic `Closes #N` from substituting for independent judgment.

No rung issue closes from a commit reference alone. Existing issues remain open until their individual residual is evidenced or explicitly rejected. Contradictory historical text receives an append-only correction and stops acting as current authority; history is not rewritten.

## 9. Immediate next execution package

Only P0-A becomes implementation-ready after explicit adoption of the two-document plan set. C0-A remains blocked until P0–P3 each complete their separately reviewed preregistration, candidate, independent proof, recovery, and explicit promotion sequence and #1757 is closed after all four promotion records and current-byte P0-P3 reruns.

The `/implement #1745 C0-A` package contains only:

1. case and receipt schemas;
2. `tests/acceptance/control-tool-c0.json` with C0-C01 through C0-C12 paired to BOOT-C01 through BOOT-C12, exact future nodes, subjects, oracles, counterfactuals, budgets, independent raw observations, trusted-base executable/version/digest identities, and the SHA-256 of both product schemas, the bootstrap driver/observer/settings/packet schema, and every fixture/golden vector;
3. the bound non-production fixtures/golden vectors, immutable to C0-B-C;
4. the frozen `tests/bootstrap/run_control_tool_bootstrap.py`, the unchanged P0-released `tests/bootstrap/observe_claude_execution.py`, supplemental observer-settings fixture, packet schema and `tests/bootstrap/test_control_tool_bootstrap.py`, with exact P0 observer digest plus driver/observer mutation tests confirming ID joins, settings provenance, privacy-bounded capture, observation independence, no candidate import/decision reuse, no provider/extension surface, and no production implementation or trigger change;
5. the immutable C0-pre commit.

The frozen fixture set includes a repository with no Claude settings, agents, hooks, or command Markdown so that the `process` runner and receipt contract are proven as software-tool behavior rather than as Claude workflow behavior.

The `/implement #1746 C0-B` package consumes that exact manifest and contains:

1. pure contract/receipt core and thin `adevctl` case/receipt CLI;
2. standalone P0–P2 candidate tests and observable mutation/tamper fixtures, but no independent promotion packet;
3. manifest-only installed-copy proof under Python `-S`;
4. install-manifest entry only after that staged-copy proof; no command, hook, CI, deploy-postflight, or doc-master trigger;
5. architecture/testing/runbook/changelog updates limited to candidate C0 facts;
6. measured candidate output and an immutable candidate commit that can report only `CANDIDATE_PASS` or non-pass.

Issue #1747 then runs the frozen driver without `/implement`, retains every raw/candidate comparison and negative result in the schema-valid packet, performs manifest-only and exact clean-worktree recovery proof, and requests the explicit digest-bound user promotion record. Only that record closes #1747 and parent #1731 as `STANDALONE_RELEASED`.

C0O is the next standalone capability after C0 promotion and receives its own A, B, and C execution children under #1750. O0a #1751, O0b #1752, O0c #1753, and O0d #1754 then each receive D, E, F, and G execution children only after their predecessor release; each moves exactly one frozen fact family and leaves later families wholly legacy-owned. After all four reach `ADAPTER_RELEASED`, the current activity/archive/telemetry system has no active production writer, registration, or fallback reader and umbrella #1728 records `CUTOVER_COMPLETE`. Only then does C0T receive its A, B, and C execution children; T0 begins only after C0T is `STANDALONE_RELEASED` and consumes the released C0, C0O/O0a–O0d, and C0T contracts unchanged. If any later rung reveals a kernel, journal, adapter, or transaction defect, it stops and the owning capability is reopened and repaired as its own versioned change before work resumes.

## 10. Program completion

The program completes only when:

- each capability is independently usable and proven without its adapters;
- each production trigger was added and activated one at a time on real installed/runtime subjects;
- every active control has one decision owner and current permit/refuse/fault evidence where applicable;
- source, stage, install, runtime, receipt, and policy identities are traceable end to end;
- stale or contradictory claims cannot act as current authority;
- settings, manifests, registrations, indexes, and maintained counts have one canonical owner;
- every runtime event fact has exactly one C0O journal owner, every governed transition fact has exactly one C0T chain owner, and transaction records reference the exact observation-receipt digests they used;
- no production activity/archive/telemetry writer, duplicate event schema, `.claude/logs` fallback reader, or copied raw Claude transcript remains; native transcripts are external witnesses only, and summaries/dashboards/issues are verified projections that cannot convert missing evidence into pass;
- the AST/manifest ledger proves the measured 33 append-writer baseline and 13 activity-area writers fell by every migrated logging module while explicitly named operational state stores remained state rather than being deleted for a count target;
- agent, skill, and prompt roles exchange typed digest-bound artifacts, with authority enforced outside their prose;
- supported host projections and policy-source discovery follow one declared profile and cannot drift silently;
- superseded hooks, libraries, configs, tests, and documentation claims are removed or explicitly historical;
- a clean consumer proves the shipped toolkit without source fallback;
- the resulting system is smaller in authorities and integration paths, with complexity remaining only in independently testable capabilities.
- the temporary bootstrap overlay has retired every observation the released tool can safely own, while its bounded raw-oracle re-entry suite remains available for kernel, C0O, and Claude-carrier changes and has not grown into a second harness.

## Acceptance Criteria

- **AC-01 — product boundary:** C0 is callable and useful as a manifest-only installed CLI without Claude Code, GitHub, command Markdown, hooks, workflows, deployment execution, or agents; core imports do not cross into adapter/runtime owners.
- **AC-02 — narrow stable contract:** the no-float canonical JSON subset/digest preimage, closed two-runner/oracle vocabulary, six result states/exit codes, declared-versus-observed identity, receipt integrity limits, receipt-specific atomic persistence, subprocess isolation, stdlib-only runtime, and sink-failure semantics pass C0-C01 through C0-C12 and independent mutant controls.
- **AC-03 — no self-certification:** P0-A first releases the generic observer through immutable cases and independent raw/mutant proof; `/implement #1745 C0-A` binds that exact observer digest unchanged and freezes the C0 manifest, schemas, fixtures, promotion driver, settings fixture, and packet schema before `/implement #1746 C0-B`; #1747 independently executes paired BOOT-C01 through BOOT-C12 raw observations, and only an explicit digest-bound user promotion—not candidate `PASS`, a commit close, or agent consensus—creates `STANDALONE_RELEASED`.
- **AC-04 — one rung at a time:** each durable GitHub rung issue owns one A–C capability or D–G adapter, while each protected changeset has a separate auto-closing execution child; the rung parent is never passed to `/implement`, peer capabilities wait for every planned adapter, and the sole initial composition is C0 -> independently released C0O -> sequentially released O0a/O0b/O0c/O0d -> independently released C0T -> T0.
- **AC-05 — real enforcement endpoint:** report-only integrations cannot enforce; an activated integration terminates at a real blocking hook/job/deploy failure, proves both permission and refusal through the actual carrier, and has exactly one decision owner.
- **AC-06 — signed gate binding:** before T0 activation, transaction, manifest, chain, receipt, run, and subject identity are covered in the exact schema-v2 sentinel HMAC preimage and read through a strict assurance verifier; the chain covers role/carrier, predecessor, artifacts, observations, and impact-set facts; unsigned, invalid, legacy, wrong-run, wrong-transaction, wrong-chain, wrong-subject, and stale state cannot authorize commit or be substituted by agent-completion state.
- **AC-07 — dimensional proof:** each activation reports design, logic, connectivity, deployment, C0O observability, and provenance/currency separately; missing/failed/behind/unmeasured dimensions never collapse into aggregate pass, and a Claude carrier claim binds direct per-call `tool_use_id` plus `agent_id`/`agent_type` where required rather than inferring identity from order or timestamps.
- **AC-08 — measured performance:** trigger budgets name workload, machine/profile, window, sample count, failures, and maximum; p95/p99 are withheld below 100 representative samples.
- **AC-09 — rollback and subtraction:** the identical deployment vector is rehearsed before activation; the superseded authority is removed or made structurally non-authoritative in the owner-switch changeset, with no dual-enforcing interval.
- **AC-10 — currency and documentation:** C4/T5 make final code, tests, projections, impacted documentation, and changelog one subject-bound transaction; `Last Updated`, issue state, test presence, counts, and agent prose cannot establish currency.
- **AC-11 — safe simplification:** behavior migrates vertically one control family at a time; adapters contain translation only, duplicate settings/path extraction/registries/telemetry authority are subtracted with their replacement, and no module-count target drives deletion.
- **AC-12 — durable execution authority:** the tracked adopted two-document plan set at one commit with both blob/SHA-256 identities is authority until the prerequisite releases; `.claude/plans/` is a byte-verified ignored mirror only, and every issue/evidence packet links immutable case IDs and exact subjects.
- **AC-13 — independent bootstrap scrutiny:** C0 promotion is decided from immutable pre-implementation criteria plus the single frozen test-only bootstrap package and raw observations that do not import or trust candidate decision code; candidate/external disagreement is `INVALID`; later version N is never promoted solely by N; N-1 remains production authority until the atomic switch; and every overlay step either maps to a proved tool-owned replacement or remains in the bounded kernel/carrier re-entry suite.
- **AC-14 — universal assurance transaction:** C0T independently proves `POLICY_BOUND` through promotion/refusal/invalidation on an append-only digest chain before T0 integration; declared role and authenticated carrier identity remain distinct, required missing identity is `UNMEASURED`, pre-change or mutant sensitivity and post-result criterion-change invalidation are mechanical, raw observations persist, and an installed non-Claude fixture completes without agent or hook authority.
- **AC-15 — independent external oracle:** P0-A releases one privacy-bounded generic Claude recorder/reconciler; C0-A binds it unchanged with the C0-specific settings and packet contract. It detects missing, duplicate, cross-run, misbound, unknown-schema, hidden-error, sink-failure, and non-zero-process cases before C0-B, never writes the production journal, and remains a bounded re-entry oracle rather than autonomous-dev logging.
- **AC-16 — canonical product observability:** C0O independently proves a closed privacy-bounded event contract, deterministic native-ID correlation, idempotent-retry/exactly-once SQLite journal, verified query/reconciliation, crash/logical-rotation/non-destructive-expiry behavior, and source-free install; O0a–O0d then move the exhaustive autonomous-dev event families and readers to that journal one released adapter at a time, prove real observed and missing arms, prevent test contamination, and remove the matching activity/archive/telemetry writer path, registration, fallback, and stale test before C0T or later control migrations begin.

## Critique History

### Round 1 — plan-critic — 2026-09-06

**Verdict: REVISE** — composite 2.17/5.

Accepted revisions: add the `.claude/plans/` execution-mirror protocol and required plan sections; narrow C0; define canonical JSON and subprocess trust boundaries; distinguish declared identity, observed identity, integrity, and authentication; separate `STANDALONE_RELEASED` from `ADAPTER_RELEASED`; pre-register C0 files/cases; bind T0 receipts inside strict HMAC state; terminate T0 at a blocking PreToolUse commit gate; define sink failure honestly; add measurement sample rules; correct the live library count.

### Round 2 — plan-critic — 2026-09-06

**Verdict: REVISE** — composite 2.67/5.

Accepted revisions: split C0-A and C0-B-C into separate `/implement` runs/commits; freeze the exact case-manifest path; choose receipt-specific persistence; define digest preimage, closed oracle vocabulary, and stdlib-only installed runtime; correct the absent old acceptance owner; name the schema-v2 signed sentinel and strict assurance HMAC preimage; separate decision-channel evidence from sink persistence; replace nonexistent rollback with the exact clean-worktree deploy/recovery vector; rename T2a/T2b; align M0 with the dependency graph; require GitHub graph correction before execution.

### Round 3 — plan-critic — 2026-09-06

**Verdict: REVISE** — composite 3.17/5; Assumption Audit remained 1/5.

Accepted revisions: remove the ambiguous HMAC/nonce wording by freezing both exact message and `(per_run_secret + nonce)` key bytes; bind both schemas and every C0-A fixture/golden vector by SHA-256 in the immutable case manifest; forbid C0-B-C from changing any bound input without a replacement pre-registration commit.

### Round 4 — plan-critic — 2026-09-06

**Verdict: PROCEED** — composite 4.00/5; every axis 4/5.

The critic confirmed the exact HMAC message/key/nonce contract, immutable binding of both schemas and every C0-A fixture/golden vector, staged C0/T0 boundary, installed-runtime cases, plan validation, and clean-worktree recovery. Remaining risk is editorial only: AC-03/AC-06 summarize the detailed singular formulas rather than duplicating them.

### Round 5 — plan-critic — 2026-09-06

**Verdict: REVISE** — composite 2.17/5.

Accepted revisions: name and freeze one test-only bootstrap executor and packet schema; forbid candidate imports, extensions, installation and production consumers; separate `CANDIDATE_PASS`, `BOOTSTRAP_PASS`, explicit user promotion and `STANDALONE_RELEASED`; preserve N-1 authority through staged evaluation and invalidate only dependency-affected receipts after atomic activation; split durable rung issues from `/implement` execution children because the latter auto-inject `Closes #N`.

### Round 6 — plan-critic — 2026-09-06

**Verdict: PROCEED** — composite 4.00/5; every axis 4/5.

The critic confirmed the single non-production driver/packet boundary, distinct candidate/bootstrap/user-promotion authorities, N-1 production authority through staged evaluation, dependency-specific receipt invalidation after atomic activation, paired C0-Cnn/BOOT-Cnn verdict independence, and the #1745/#1746/#1747 split that prevents `/implement` auto-close from promoting parent #1731.

### Round 7 — plan-critic — 2026-09-06

**Verdict: REVISE** — composite 2.17/5.

Accepted revisions: move the new lifecycle state machine, immutable artifact chain, invalidation, and promotion logic out of thin T0 into separately proved C0T; add exact schema/module/CLI/test/fixture boundaries and C0T-C01 through C0T-C08; remove the C0 persistence-choice contradiction; use explicit v1 documentation impacts until C4; defer prompt/skill subtraction until C5/T6; distinguish declared role from authenticated carrier identity and bind the final chain into strict T0 state; bound C2 v1 to the first transaction route and C5 v1 to the two already divergent skill families; add explicit in-toto/SLSA dispositions.

### Round 8 — plan-critic — 2026-09-06

**Verdict: REVISE** — composite 2.83/5.

Accepted revisions: define and bind distinct `transaction_manifest_digest` and `case_manifest_digest` fields in every C0T transition and the exact T0 HMAC preimage; make the strict reader independently recompute the chain; add transaction-manifest mutation to C0T-C02; define T0's live local credential issuer/verifier as a single-use signed `transaction_carrier` dispatch record over Claude `PreToolUse`/`PostToolUse`; list the exact binding for every existing role; exclude unreliable SubagentStop/FIFO/transcript inference from deciding authority; require real-carrier role substitution, replay, race, field mutation, missing-hook, and missing-field failures before activation.

### Round 9 — plan-critic — 2026-09-06

**Verdict: PROCEED** — composite 4.00/5; every axis 4/5.

The critic confirmed distinct transaction/case manifest binding and mutation, full-chain recomputation before strict state comparison, integration-free C0T ownership, a single bounded T0 carrier rather than a new identity framework, honest local-carrier authentication limits, explicit `UNMEASURED` handling, and a real-carrier substitution/replay/race/missing-field matrix for every role.

### Round 10 — plan-critic — 2026-09-06

**Verdict: PROCEED** — composite 4.17/5.

The critic verified ACP v1, the maintained Claude/Codex ACP adapters, and A2A prior art. It confirmed that ACP is a future neutral-supervisor transport precedent rather than proof of the exact installed Claude settings/hook carrier, that A2A task/message/artifact states do not replace the assurance transaction, and that neither belongs in C0/C0T/T0 or warrants a new rung now. The two Existing Solutions dispositions preserve the research without expanding the current build.

### Round 11 — plan-critic — 2026-09-06

**Verdict: PROCEED** — composite 4.33/5.

The critic re-read the v7 diff and primary protocol sources, confirmed that only status, prior-art disposition, and critique history changed, and found no new dependency, rung, acceptance requirement, or sequence change. It also confirmed that T0 still requires the exact installed native Claude hook carrier and that ACP/A2A cannot substitute for its real `PreToolUse`/`PostToolUse` evidence.

### Round 12 — plan-critic — 2026-09-06

**Verdict: REVISE** — composite 3.67/5; Assumption Audit remained 1/5.

Accepted revisions: inventory and digest every resolved settings source rather than only project/user settings; version-scope the observed transcript field map and make unknown/missing/ambiguous schema `UNMEASURED`; atomically bind the sole pending specialist generation to native `SubagentStart.agent_id`/`agent_type`; require the same identity on every inner tool receipt and cross-check it against outer Agent/Task `PostToolUse.tool_response.agentId`/`agentType`; and add wrong-agent/same-role, correct-tool-ID/wrong-agent, concurrent dispatch/start, and missing outer-result counter-controls. The plan retains transcripts as temporary observation only and adds no parser framework or product dependency.

### Round 13 — plan-critic — 2026-09-06

**Verdict: PROCEED** — composite 4.67/5; every axis at least 4/5.

The critic re-read the v8 revision against the second live Claude Code 2.1.236 carrier probe and confirmed the identifier graph: outer dispatch `tool_use_id` -> atomic `SubagentStart.agent_id`/`agent_type` claim -> inner Pre/Post identity plus per-call `tool_use_id` -> outer Agent/Task result identity cross-check. It also confirmed complete settings-source accounting, version-scoped transcript parsing, explicit `UNMEASURED` handling, no transcript authority, and no added parser framework, product dependency, or rung. The sole claimable generation is explicitly scoped across `(session_id, run_id)` and after-the-fact event counting remains non-authoritative.

### Round 14 — plan-critic — 2026-09-06

**Verdict: REVISE** — composite 3.00/5.

Accepted revisions: restrict the Claude observer to a data-only observation fragment while keeping `run_control_tool_bootstrap.py` the sole comparison, status, eligibility, and final-packet owner; treat the exact-stdin digest only as a tamper/deduplication fingerprint and separately retain an allowlisted typed envelope with explicit redactions; freeze private capture storage, bounds, atomicity, permissions, retention, and error behavior; and move every decision-bearing `/implement` reader/writer switch into T0-F so T0-G contains only installed validation, diagnostic projection migration, and subtraction after authority has already moved atomically.

### Round 15 — plan-critic — 2026-09-06

**Verdict: REVISE** — composite 3.17/5.

Accepted revisions: place the controlled child's isolated Claude configuration/session state, stdout/stderr stream, debug log, transcript/subagent metadata, and hook captures under one supervisor-owned private-root contract; apply frozen byte/record bounds, `0700`/`0600` permissions, exclusive no-follow creation, path containment, atomicity, and fsync to the complete raw-artifact set; keep raw content and sensitive absolute paths out of `bootstrap.json`; designate `run_control_tool_bootstrap.py` as the sole lifecycle owner; delete the complete root after every terminal result; and require its one-hour crash-retention sweep, live-owner protection, stale-root deletion, and cleanup-failure controls before any later run can launch or promote.

### Round 16 — plan-critic — 2026-09-06

**Verdict: REVISE** — composite 3.33/5.

Accepted revisions: make finalization executable by constructing the non-final packet in memory, closing and digesting raw inputs, deleting the private run root, adding the cleanup outcome, and atomically writing `bootstrap.json` exactly once; forbid later packet amendment; and define one hour as the crash-residue stale threshold enforced on the next explicit driver entry rather than claiming an unimplemented wall-clock reaper.

### Round 17 — plan-critic — 2026-09-06

**Verdict: PROCEED** — composite 4.33/5; every axis at least 4/5.

The critic confirmed one frozen data-only observer under the sole bootstrap driver, a single private-root contract for every raw Claude artifact, an honest next-entry crash-retention threshold, one-write packet finalization after cleanup, no second authoritative store, and a verified read-only C0T inspection projection. It also confirmed C0 -> C0T -> T0 sequencing, an atomic T0-F authority switch with no dual-owner interval, and T0-G limited to installed validation and diagnostic subtraction.

### Round 18 — plan-critic — 2026-09-06

**Verdict: REVISE** — composite 2.50/5.

Accepted revisions: distinguish byte-identical idempotent retry from duplicate production and add commit-success/output-ack-loss recovery; make #1728 an O0 migration umbrella and split the exhaustive event partition into four sequential D–G adapter rungs #1751–#1754; correct C0O from sole operational store to sole runtime-event store; remove physical retention deletion from v1 so expired evidence remains verifiable and IDs cannot be reused; require any later deletion to have a separately released transaction-aware content-addressed export/pinning contract; and compare canonical logical receipt/row/chain/seal bytes plus recorded SQLite version/pragmas rather than unstable SQLite/WAL file bytes.

### Round 19 — plan-critic — 2026-09-06

**Verdict: REVISE** — composite 3.33/5.

Accepted revisions: add mandatory parametrized `O0-SCOPE-C01` negative and positive arms over the live `pipeline_completion_state.py`, `install_audit.py`, `drain_queue_state.py`, and `cia_finding_store.py` scope lock while excluding the absent `batch_retry_manager.py`; preserve operational mutation/gating state rather than gaming the append-writer count; narrow O0d to queue-processing observations; and freeze measured event/store/page/free-space bounds with an explicit 180-day horizon, preflight, `SQLITE_FULL`, reserve-breach, no-acknowledgement, no-auto-delete, and recovery behavior in C0O-C09/C11.

### Round 20 — plan-critic — 2026-09-06

**Verdict: PROCEED** — composite 4.00/5; every axis 4/5.

The critic confirmed idempotent replay and acknowledgement-loss recovery, logical-byte rather than SQLite-file proof, non-destructive expiry, bounded capacity failure, the live operational-state scope lock, and the exhaustive four-rung O0 partial-cutover topology. It found no remaining blocking change before committing v10 and binding its exact commit and SHA-256 into the reserved GitHub issues.

### Round 21 — plugin-native prerequisite critique — 2026-09-07

**Verdict: REVISE, REVISE, then PROCEED on v3.**

Three independent Claude Code 2.1.236 / Opus sessions challenged the new carrier prerequisite. The first required immutable per-rung cases, hard packet gates, a pre-carrier observer, honest non-atomic fleet semantics, recovery, archive relocation, and bounded migration. The second removed post-P3 dependencies on deleted delivery scripts, premature C0 claims, settings edits before old-session drain, ambiguous digest authority, and inconsistent #1745 gating. The third confirmed those blockers closed and returned `PROCEED`; its non-blocking precision cautions were incorporated into v4. To avoid recursively changing bytes merely to embed their own verdict, the final exact-v4 review session, result, commit, and both committed SHA-256 values are recorded on #1757, the external adoption ledger.
