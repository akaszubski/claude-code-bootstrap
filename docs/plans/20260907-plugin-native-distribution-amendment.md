# Plugin-native distribution prerequisite

**Status:** PROPOSED v4 — independently reviewed; exact commit/SHA-256 adoption
is required before the first protected preregistration changeset

**Historical base superseded:** `docs/plans/20260906-control-tool-capability-ladder.md` v10 at commit
`7f79f49ea608edcb40f0891efd774466b0ba1c9d`, SHA-256
`a4231518301940ccf9347173c50d59bcf2bb84fc52c57e55c4f306328ebde195`
is provenance only. Adopted authority will be this file and the co-committed v11
ladder at one new commit, with both exact digests recorded on #1757.

**Scope:** repair the execution observer and mutable-root contract first, make
the existing Claude adapter a valid native plugin, remove ambiguous runtime
lookup, prove source/cached/consumer behavior, and then migrate the fleet away
from copied executable trees. The standalone assurance contracts and their
file names remain unchanged. The native plugin is a distribution/adapter
envelope, not the product boundary.

**Navigation:** #1757 is the prerequisite ledger. #1756 owns private execution,
#1755 native plugin discovery, #1758 runtime resolution, and #1759 fleet
cutover/subtraction. Each is a durable rung ledger and is never passed directly
to `/implement`; protected A/B changesets get separate execution children so
automatic issue closure cannot create a release state. #1745 remains blocked
until #1757 is closed; closure requires all four explicit promotion records and
current-byte P0-P3 reruns, including `PLUGIN_CARRIER_RELEASED`.

## 1. Corrected decision

Ship autonomous-dev's Claude adapter as one native Claude Code plugin. Claude
Code owns plugin acquisition, caching, version selection, commands, agents,
skills, and the final hook registry. The plugin contains its Python support
libraries and scripts. After migration, no autonomous-dev mechanism copies
executable code into a consumer's `.claude/` tree or
`~/.claude/{hooks,lib,commands,agents,skills,scripts,config}`.

Keep the provider-neutral standalone artifact required by C0, C0O, C0T, CI,
and non-Claude consumers. Until the capability ladder versions that contract,
`plugins/autonomous-dev/config/install_manifest.json` remains the canonical
minimal standalone file list. Plugin-native cutover may narrow it to proved
standalone files; it may not delete it, rename the frozen `lib/assurance_*` or
`scripts/adevctl.py` paths, or erase/reclassify `install_audit` operational
history as logging. Its legacy writer may retire only after P3-A names the
final producer/consumer disposition and preserves read-only historical state;
C1/T2a later owns authoritative installed-subject receipts. A public
package/index release remains a separate decision. The sole provider-neutral
builder is `plugins/autonomous-dev/scripts/build_standalone.py`: it accepts
explicit source, destination, and manifest paths, copies exactly classified
manifest members, writes no settings, and refuses missing, extra, fallback, or
digest-mismatched bytes.

There is no live duplicate-policy shadow. Before activation, the native hook
manifest contains only one dedicated, non-blocking diagnostic canary that
always exits zero and writes only inside its supplied private proof root. Real
policy hooks are exercised as direct subprocess subjects and replayed against
the frozen truth tables without registering them a second time. The final
native policy registry is activated only during the bounded fleet switch.

## 2. Verified present state

Evidence was rechecked at the adopted commit with Claude Code 2.1.236.

1. Strict validation rejects the current plugin manifest because `repository`
   is an object rather than a string.
2. Strict validation treats the nested `.claude-plugin/marketplace.json` as a
   marketplace and rejects missing `owner` and `plugins`.
3. A real `--plugin-dir` run loads zero native plugin agents and hooks; legacy
   command/skill discovery is not native carrier proof.
4. Version identity is worse than a three-value mismatch: six distinct values
   occur across eleven metadata/documentation sources, including stale root
   `plugin.json` and `install_manifest.json` copies.
5. The canonical install manifest lists 17 agents, 26 commands, 15 config
   files, 68 hook files, 243 library files, 23 scripts, 42 skill files, and 9
   templates. The plugin tree also exposes archived component directories that
   native discovery would otherwise load.
6. There are 34 `*.hook.json` sidecars but no native `hooks/hooks.json`.
   Sidecars and settings generators are current migration inputs, not a Claude
   plugin registration contract.
7. Runtime lookup is ambiguous: 908 files contain `sys.path.insert` and 87
   reference `.claude/lib`; stale copied files have repeatedly won over source.
8. The existing `/implement` carrier writes absolute `/tmp` state/scratch and
   ignored repository-local caches/logs outside its claimed private root.
9. CI cannot observe a new failure merely placed in the standing-red unit tier
   or the ratcheted integration tier. The `smoke` job is the current hard
   decision path.
10. `~/.claude/settings.json` currently owns 17 hook registrations across eight
    events. Project settings own none. The switch is therefore fleet/global,
    not a project-local atomic edit.
11. A pristine source checkout makes four current guards fail open because
    repository detection depends on the ignored copied path
    `.claude/commands/implement.md`; the existing proof-of-block CI step is
    non-blocking.
12. The live tracker confirms #1731, #1737, #1745–#1747, and #1755–#1759 have the
    intended identities. `tests/regression/test_issue_1747_manifest_completeness.py`
    is a stale/misleading historical label and must be renamed or corrected
    before #1747 is executed; it cannot serve as issue identity evidence.

Historical disposition: the sidecar-to-generated-hook design in
`20260906-repository-integrity-recovery.md` is evidence only. This prerequisite
supersedes it because retaining canonical sidecars plus a generated native
registry would preserve two representations and a freshness edge. Final Claude
registration has one directly reviewed `hooks/hooks.json` owner; old sidecars
are removed only with their readers and generators after the final inventory
proves no surviving consumer.

## 3. Product and state boundaries

### 3.1 Shipped tree

```text
.claude-plugin/
  marketplace.json                 # one repository marketplace catalog
plugins/autonomous-dev/
  .claude-plugin/plugin.json        # one plugin identity/version
  agents/                           # active identities only
  commands/                         # active identities only
  skills/                           # active identities only
  hooks/
    hooks.json                      # sole final Claude registration owner
    ...entrypoints...
  lib/                              # current stable module paths retained
  scripts/                          # current stable entrypoints retained
    build_standalone.py             # sole provider-neutral manifest builder
  config/                           # immutable policy/schema/profile inputs
  templates/                        # immutable generation inputs
```

All `archived/` trees move outside the plugin root before native discovery can
release. Exact component identity sets—not counts—are preregistered and proved.
The repository-root marketplace is created; the invalid nested marketplace and
its readers are migrated and then removed. Human-facing version/count text is a
checked projection of the one plugin identity source.

### 3.2 Mutable roots

- `ADEV_RUN_ROOT/<run-id>/`: active-run scratch, state, locks, logs, caches,
  raw observations, temporary outputs, and active-run secret material. The
  root is explicit, absolute, private (`0700` directories, `0600` files),
  no-follow, bounded, and lifecycle-owned by one supervisor.
- `${CLAUDE_PLUGIN_DATA}`: persistent Claude-plugin-owned data only. Claude
  Code 2.1.236 substitutes it for plugin hooks; skill-hook commands may rely
  only on `${CLAUDE_PLUGIN_ROOT}` and explicit inputs.
- Consumer-profile paths: repository-owned policy, durable receipts, and any
  provider-neutral persistent security state. The adapter supplies these
  explicitly; core code does not discover them from `$HOME`.
- Legacy `~/.claude/pipeline_secrets/<run-id>.key` is inventoried as persistent
  security state, not falsely classified as scratch. P0 may move active-run
  keys into the run root; any post-run authority change waits for T0's frozen
  secret/state contract.

Never write mutable data to the immutable plugin cache, arbitrary absolute
`/tmp`, ambient `.claude/lib`, or a source checkout fallback. The P0 observer
claims persistent-write isolation only over its enumerated snapshot roots; it
does not claim to observe transient syscalls that leave no artifact.

### 3.3 Dependencies

The decision-bearing assurance and hook path remains Python-standard-library
only. Current optional `anthropic` imports are capability-gated and cannot make
an enforcement result pass; `lib/covers_index.py`'s PyYAML dependency is either
removed from the activation path or declared as an optional unavailable
capability. SessionStart cannot install an environment and then call failure a
success. Any optional locked environment lives under `${CLAUDE_PLUGIN_DATA}`
and receives its own source/license/digest/absence cases before use.

The bounded external trusted base records the exact paths, versions, and where
practical digests of Claude, Python, Git, pytest, Ruff, `shasum`, and the OS.
Coverage percentage is not deciding evidence because current CI overrides the
repository coverage option.

## 4. Bootstrap observer before carrier repair

P0-A lifts the generic Claude execution observer previously planned inside
C0-A into an earlier immutable test-only changeset. This resolves the
bootstrap circularity without creating a second product or telemetry system.
C0-A later binds the released observer's exact digest unchanged and adds only
its C0-specific case manifest/fixtures/driver behavior.

P0-A owns exactly:

- `tests/bootstrap/observe_claude_execution.py` — data-only capture/reconcile;
- `tests/bootstrap/plugin_carrier_bootstrap.schema.json` — closed proof packet;
- `tests/bootstrap/test_plugin_carrier_bootstrap.py` — observer self-tests;
- `tests/fixtures/plugin_carrier/claude-observer.settings.json` — supplemental
  diagnostic-canary registration;
- `tests/fixtures/plugin_carrier/` synthetic stream/debug/transcript/settings/
  filesystem inventories and their one-at-a-time mutants;
- `tests/acceptance/plugin-carrier-p0.json` — immutable P0 case manifest;
- one explicit hard `smoke` job step invoking the exact P0 verifier nodes.

The observer imports no product module, exposes no provider/extension API,
writes no production journal, cannot emit a release state, and never changes a
hook decision. Its controlled child uses a caller-supplied working directory,
run root, session UUID, settings overlay, `--setting-sources`,
`--output-format stream-json`, `--include-hook-events`, `--verbose`, and
`--debug-file`. `--safe-mode` and `--no-session-persistence` are forbidden for
carrier proof. The observer records the argv/environment allowlist, executable
identities, settings sources/digests, pre/post Git state, bounded stream/debug/
transcript metadata, hook lifecycle joins, and a recursive pre/post path/digest/
mode inventory for every declared writable root plus known legacy absolute
paths. Prompt/tool/file contents are not copied into the final packet.

P0-A is constructed by the legacy carrier from a clean worktree, but that run
may produce bytes only. The observer is accepted only when ordinary Python/OS
oracles independently validate its closed schema, import boundary, synthetic
fixtures, expected path inventories, and killed mutants. The real canary then
uses the committed observer from a second clean worktree. Legacy activity logs,
pipeline completions, agent summaries, and candidate verdicts cannot promote
it. Missing or ambiguous evidence is `UNMEASURED`/`ERROR`.

## 5. Immutable rung protocol

Every P0–P3 rung has three states:

1. **A — preregistration:** a protected execution child creates only the exact
   case manifest, schemas/fixtures, observer extensions, and a hard CI smoke
   route; it ends in an immutable pre-implementation commit.
2. **B — candidate:** one or more separately scoped protected execution
   children implement against the frozen A bytes. Any change to a bound input
   invalidates B and requires a replacement A commit.
3. **C — independent proof and promotion:** the released P0 observer and
   ordinary external tools run from a new clean worktree against the immutable
   candidate. C is not passed to `/implement` unless proof code itself must
   change, in which case it becomes a new A. A valid packet can report
   `CANDIDATE_PASS`; only an explicit digest-bound user promotion record creates
   the rung's release state.

Reviewer, security, documentation, spec-validator, and CIA verdicts are packet
inputs. They cannot waive a failed deterministic case, create `PASS`, change a
threshold, or promote a rung.

Each `tests/acceptance/plugin-carrier-pN.json` binds: exact case ID/node,
subject paths and digests, fixtures and digests, positive/opposite arms,
counterfactual, external oracle, runner, timeout/output bounds, expected
settings/components, allowed persistent-write roots, invalidation rule, and the
exact smoke-job command. Zero collection, skip, missing arm, collection error,
unknown schema, or unavailable required tool is non-pass.

Each manifest classifies every node by execution carrier. Portable nodes run
directly in CI; real-Claude/plugin-install nodes run under the P0 supervisor on
the declared macOS carrier and produce bounded digest-bound receipts. CI has a
separate hard `smoke` step that recomputes the manifest, current candidate,
tool, and receipt identities and rejects absent, stale, skipped, unavailable,
or non-pass carrier evidence. It has no `continue-on-error`, `|| true`, or
standing-failure ceiling, and the summary job depends on it. An unavailable
Claude binary never becomes pass merely because CI cannot execute that node.
Unit/integration suites remain supporting evidence until their standing-red
baselines are repaired; they are not the only route for a P0-P3 decision.

Each rung owns its release-gate module and every candidate test module that a
later rung may change. An A manifest may bind a shared immutable node by its
own fixture/input digests and semantic identity, but never bind the whole-file
digest of a module another rung owns; current-byte reruns recompute the actual
subject and dependency identities rather than accepting an earlier packet.

The tracked plan authority is a two-document set: this file plus
`20260906-control-tool-capability-ladder.md` from the same commit. Both blob IDs
and SHA-256 values are recorded on #1757 and mirrored byte-for-byte into
`.claude/plans/`. The execution preflight refuses a missing, stale, extra, or
independently mixed mirror. The mirror never becomes authority.

## 6. Exact preregistered case identities

The future nodes below are immutable names. A manifests add their exact fixture
and subject digests before candidate code exists.

### 6.1 P0 — private execution carrier (#1756)

Manifest: `tests/acceptance/plugin-carrier-p0.json`.

| Case | Exact deciding node | Required arms / independent observation | Budget |
|---|---|---|---|
| `P0-C01` | `tests/bootstrap/test_plugin_carrier_bootstrap.py::test_observer_has_closed_schema_no_product_import_and_kills_every_decision_mutant` | valid fixtures reconcile / unknown field, candidate import, verdict reuse, and surviving mutant refuse | 20s |
| `P0-C02` | `tests/unit/lib/test_execution_run_root.py::test_run_root_is_explicit_private_bounded_and_no_follow` | valid root/namespace/modes pass / relative, reused, symlink, wrong-owner, wrong-mode, escape, and capacity faults refuse | 10s |
| `P0-C03` | `tests/structural/test_execution_sink_inventory.py::test_every_implement_sink_has_one_declared_run_root_owner` | frozen command/lib/hook/test/cache/log/state/secret inventory is classified once / absolute temp, ignored repo sink, fallback, or missing owner fails | 10s |
| `P0-C04` | `tests/integration/test_execution_run_root.py::test_implement_fixture_redirects_every_declared_persistent_artifact` | bounded edit/test/revert writes only tracked subject plus run root / each restored legacy sink is observed and fails | 60s |
| `P0-C05` | `tests/integration/test_execution_run_root.py::test_concurrent_crash_cleanup_and_capacity_faults_preserve_other_runs` | concurrent namespaces and stale cleanup are exact / live-owner deletion, cross-run write, partial/disk-full acknowledgement, and cleanup failure refuse | 45s |
| `P0-C06` | `tests/regression/test_execution_run_root_policy_equivalence.py::test_path_migration_preserves_every_frozen_hook_decision_envelope` | old/new permit/refuse/error/timeout envelopes match / any decision or payload-key mutation fails | 45s |
| `P0-C07` | `tests/e2e/test_execution_run_root_claude.py::test_real_claude_implement_fixture_has_no_unexpected_persistent_write` | real persisted session joins stream/transcript/hooks and declared inventories / missing join, unregistered artifact, ordinary-store leak, hidden non-zero, or source mutation refuses | 120s |
| `P0-C08` | `tests/regression/smoke/test_plugin_carrier_p0_release_gate.py::test_p0_packet_matches_frozen_manifest_and_candidate` | exact packet/manifest/candidate/tool digests pass / stale packet, zero nodes, altered manifest, or non-pass state blocks smoke | 15s |

P0 sequence: A freezes the observer and all cases; B introduces one run-root
resolver and migrates sinks without policy changes; C runs the committed
candidate from clean bytes and requests `PRIVATE_CARRIER_RELEASED`.

### 6.2 P1 — native plugin discovery carrier (#1755)

Manifest: `tests/acceptance/plugin-carrier-p1.json`.

| Case | Exact deciding node | Required arms / independent observation | Budget |
|---|---|---|---|
| `P1-C01` | `tests/regression/test_native_plugin_manifest.py::test_claude_2_1_236_strictly_validates_plugin_and_root_marketplace` | both exact native schemas exit zero / malformed repository, missing owner/plugins, unknown component metadata, or version skew fails | 20s |
| `P1-C02` | `tests/structural/test_native_plugin_inventory.py::test_exact_active_component_identities_are_singular_and_archives_are_outside_plugin_root` | frozen command/agent/skill/hook identities each occur once / removed, renamed, duplicate, ignored, archived, or extra identity fails | 10s |
| `P1-C03` | `tests/integration/test_native_plugin_canary.py::test_diagnostic_hook_is_non_blocking_and_private` | one distinct canary exits zero and writes only to proof root / policy entrypoint registration, shared-state write, duplicate invocation, or non-zero fails | 30s |
| `P1-C04` | `tests/e2e/test_native_plugin_canary.py::test_plugin_dir_executes_exact_command_agent_skill_and_canary_hook` | real Claude source profile executes all four named identities and joins native IDs / discovery-only, legacy fallback, wrong identity, or missing lifecycle pair fails | 120s |
| `P1-C05` | `tests/regression/test_native_plugin_manifest.py::test_one_field_and_one_component_mutants_turn_carrier_red` | every registered mutant is killed / any surviving or unexecuted mutant fails | 45s |
| `P1-C06` | `tests/integration/test_native_plugin_canary.py::test_source_and_cached_component_subjects_match_exactly` | source and cache inventories/digests match / missing, extra, stale, or duplicate executable byte fails | 45s |
| `P1-C07` | `tests/regression/test_native_plugin_manifest.py::test_metadata_and_hook_registration_have_one_owner_and_no_stale_reader` | one version owner and one native registry owner / stale root manifests, sidecar authority, or old reader/generator fails | 15s |
| `P1-C08` | `tests/regression/smoke/test_plugin_carrier_p1_release_gate.py::test_p1_packet_matches_frozen_manifest_and_candidate` | exact current packet passes / previous-bytes P1 proof, altered case, or non-pass blocks smoke | 15s |

P1 creates the root marketplace, valid plugin identity, active-only component
tree, and one diagnostic native hook. It does not register real policy hooks.
It records exact behavior for Claude 2.1.236; support for another version is a
new compatibility row, not inferred from “latest.” P1 C requests
`NATIVE_DISCOVERY_RELEASED`.

### 6.3 P2 — one runtime resolver (#1758)

Manifest: `tests/acceptance/plugin-carrier-p2.json`.

| Case | Exact deciding node | Required arms / independent observation | Budget |
|---|---|---|---|
| `P2-C01` | `tests/unit/lib/test_runtime_locator.py::test_explicit_adapter_root_resolves_one_tree_and_rejects_fallbacks` | plugin or standalone root resolves exact sibling / cwd, home, source, path-order, and missing-root fallbacks refuse | 10s |
| `P2-C02` | `tests/structural/test_runtime_locator_inventory.py::test_every_runtime_bootstrap_is_owned_once_by_frozen_migration_ledger` | every `sys.path`/`.claude/lib`/loader occurrence is classified once / unlisted, multiply owned, or restored occurrence fails | 15s |
| `P2-C03` | `tests/integration/test_native_runtime_resolution.py::test_hook_family_runs_with_python_s_and_poisoned_ambient_paths` | each migrated hook family imports bundled current bytes / poisoned ambient or source fallback cannot rescue or replace it | 90s |
| `P2-C04` | `tests/integration/test_native_runtime_resolution.py::test_command_script_and_library_families_run_from_explicit_artifact_roots` | each migrated family executes from plugin and standalone roots / missing dependency, wrong root, or extra file fails | 90s |
| `P2-C05` | `tests/regression/test_native_runtime_resolution.py::test_decision_path_is_stdlib_only_and_optional_dependencies_are_explicit` | enforcement path passes with `-S` / PyYAML/Anthropic absence cannot silently alter a decision or become pass | 30s |
| `P2-C06` | `tests/e2e/test_native_plugin_runtime.py::test_cached_plugin_runs_with_source_unavailable_and_ambient_poisoned` | cached command-agent-hook-library-receipt chain matches source / source removal, empty home, or poison changes no resolved identity | 120s |
| `P2-C07` | `tests/e2e/test_native_plugin_runtime.py::test_p1_discovery_execution_reproved_on_p2_candidate_bytes` | every immutable P1 node reruns on current P2 subjects / prior packet or prior import chain cannot satisfy it | 120s |
| `P2-C08` | `tests/regression/smoke/test_plugin_carrier_p2_release_gate.py::test_p2_packet_matches_frozen_manifest_and_candidate` | exact current packet passes / incomplete ledger, prior proof, or non-pass blocks smoke | 15s |

P2-A freezes a complete occurrence/consumer ledger. P2-B0 adds the resolver
without migrating consumers. Later B children migrate one component family and
at most 25 entrypoint files per protected changeset; each child has an exact
denominator and reruns its affected P1/P2 cases. No blanket 908-file rewrite is
one changeset. P2-C reruns all P1 cases on final bytes and requests
`RUNTIME_RESOLUTION_RELEASED`.

### 6.4 P3 — installed consumers, fleet switch, and subtraction (#1759)

Manifest: `tests/acceptance/plugin-carrier-p3.json`.

| Case | Exact deciding node | Required arms / independent observation | Budget |
|---|---|---|---|
| `P3-C01` | `tests/e2e/test_native_plugin_install.py::test_local_marketplace_install_runs_clean_consumer_chain` | local marketplace install into isolated consumer executes command-agent-hook-library-receipt with exact IDs / source or ambient rescue fails | 180s |
| `P3-C02` | `tests/e2e/test_native_plugin_install.py::test_native_policy_registry_matches_frozen_direct_hook_truth_tables` | all final native entrypoints match permit/refuse/error/timeout and payload-shape vectors / wrong key, matcher, exit, timeout, or missing arm fails | 180s |
| `P3-C03` | `tests/e2e/test_native_plugin_install.py::test_session_epoch_switch_never_dispatches_one_logical_event_to_two_policy_owners` | each old or new session has one owner and declared epoch / duplicate same-event dispatch, any live old session after settings removal, zero-owner old or new session, or unknown epoch fails | 120s |
| `P3-C04` | `tests/integration/test_native_plugin_migration.py::test_migration_edits_only_manifest_proven_owned_settings_entries` | install/enable and owned-entry removal preserve consumer bytes / ambiguous owner, concurrent settings edit, partial write, or unrelated deletion refuses | 60s |
| `P3-C05` | `tests/e2e/test_native_plugin_install.py::test_rehearsed_recovery_restores_recorded_plugin_and_owned_settings_state` | disable candidate, restore digest-matching backup, restart, and verify old owner / changed backup target, missing cache, live ambiguity, or failed verification blocks | 180s |
| `P3-C06` | `tests/structural/test_plugin_delivery_subtraction.py::test_frozen_delivery_denominator_has_no_surviving_executable_copy_path` | every classified legacy writer/reader/registration path is removed or non-executable / restoration of any member or downstream copied setup/sync fails | 20s |
| `P3-C07` | `tests/regression/smoke/test_plugin_carrier_p3_release_gate.py::test_proof_of_block_is_hard_and_clean_checkout_has_no_silent_guard` | corrected baseline proves all guards with no silent regression and no `continue-on-error` / copied-tree removal mutant or repo-detection fallback fails | 45s |
| `P3-C08` | `tests/e2e/test_native_plugin_install.py::test_update_uninstall_and_current_standalone_manifest_remain_source_free` | two local versions update/restart/uninstall cleanly; each currently listed standalone member is preregistered as stdlib executable, immutable data, or optional capability, then executables run/import under `python3 -S`, data match digests, and absent optional dependencies return the declared unavailable result / stale cache, keep/remove-data error, wrong class, removed/extra member, or source fallback fails | 180s |
| `P3-C09` | `tests/regression/smoke/test_plugin_carrier_p3_release_gate.py::test_p3_packet_and_fleet_ledger_match_frozen_manifest_and_candidate` | every declared consumer/host epoch and digest is current / missing host, live old epoch, altered packet, or non-pass blocks smoke | 20s |

The P3-A removal denominator starts with these verified entrypoints and expands
to every transitive reader/writer found by AST/import/call/config scans:

- `install.sh`;
- `plugins/autonomous-dev/scripts/install.py`;
- `scripts/deploy-all.sh`, `deploy-to-repos.sh`, `deploy_local.sh`,
  `pull-plugin-update.sh`, `resync-dogfood.sh`, `test-user-install.sh`, and
  `update_hooks_for_uv.py`;
- `plugins/autonomous-dev/scripts/sync_settings_hooks.py`,
  `configure_global_settings.py`, `strip_duplicate_hooks.py`,
  `reset_global_hooks.py`, `migrate_hook_paths.py`,
  `uninstall_strip_repo_hooks.py`, `uninstall_unregister_plugin.py`, and
  `deploy_state.py`;
- `plugins/autonomous-dev/lib/uninstall_orchestrator.py` and the
  `sync_dispatcher/` package;
- stale `plugins/autonomous-dev/plugin.json` and
  `plugins/autonomous-dev/install_manifest.json` metadata copies;
- every already-copied downstream `/setup` or `/sync` command capable of
  reinstalling old bytes.

P3-A also freezes `build_standalone.py`'s input/output contract and cases, the
classification of every current standalone manifest member, and the explicit
`install_audit` producer/consumer/history disposition. P3-B adds that one
builder before removing any legacy standalone writer; P3-C08 proves it on
manifest-only bytes. The builder cannot edit Claude settings, plugin caches, or
consumer source and is not a plugin installer.

`scripts/deploy_state.py`'s existing digest/state primitives are reused for
source/cache/fleet receipts while they remain needed; no second tree-digest
owner is introduced. It is removed only if the final migration ledger proves
its replacement consumes every required fact.

Lowering a hard floor, reachability ceiling, dark-test baseline, manifest count,
or expected-failure ratchet is allowed only when P3-A names the exact removed
identities, the candidate proves every absence plus the retained positive arm,
a restoration mutant fails, and an independent reviewer confirms the change is
subtraction rather than threshold gaming. Aggregate line/module/count reduction
is never an oracle.

## 7. Achievable activation, fleet migration, and recovery

The owner switch is not described as atomic across Claude's plugin and settings
stores. The achievable contract is:

1. Build/install the candidate plugin locally and prove it without real policy
   registrations; record cache and settings digests with a recovery worktree.
2. Freeze the final native `hooks/hooks.json`, direct-subprocess parity packet,
   owned settings-entry manifest, supported consumer/host ledger, and a new
   session epoch.
3. For each declared host/consumer, refuse ambiguous session state, drain or
   stop every legacy-owned session, and independently prove that no old epoch
   remains live before editing settings. A live or unclassifiable old session
   blocks the host switch.
4. Only after that host is drained, enable the proved plugin at the intended
   scope, remove only exact manifest-proven autonomous-dev settings
   registrations using compare-before-write, and start a new canary session.
   No governed session may start between plugin enable and settings removal.
   Any live old session, zero-owner session, dual owner, or unknown epoch is a
   failing arm rather than a tolerated transition state.
5. Record the bounded interval in which that host has no active governed
   session. Promotion waits until every declared host is on the new epoch and
   every new canary proves one invocation per logical event.
6. Only then subtract copied executable paths and stale readers. Re-run all
   P0–P3 packets on current bytes plus clean source, cached install, dogfood,
   clean consumer, and standalone profiles.

Recovery is rehearsed, not called atomic: stop candidate sessions; disable the
candidate plugin; restore only autonomous-dev-owned settings from the recorded
backup when the current file digest equals the expected post-switch digest;
otherwise refuse automatic restore and require a reviewed merge; select the
recorded previous plugin/cache version or redeploy the recorded clean pre-P3
worktree; start new sessions; and prove restored owner/digests. Failed recovery
blocks activation and subtraction.

Native install proof uses the observed CLI surfaces:
`claude plugin marketplace add <local-path>`,
`claude plugin install <plugin>@<marketplace> --scope <scope>`, update (restart
required), disable/enable, and uninstall. The test harness supplies an explicit
settings-source profile and never infers successful loading from the install
command's exit alone.

## 8. Documentation and stale-information control

Every behavior changeset updates its impacted architecture, runbook,
troubleshooting, testing method, compatibility matrix, command reference,
changelog, issue relationships, and consumer-retrofit instructions in the same
transaction—or records a schema-valid no-impact result naming each owner.
Doc-master does not decide freshness from filenames or `Last Updated` text. It
compares changed public behavior/paths/config/schema/registration identities to
a canonical content-owner ledger and fails changeset closeout on an unupdated,
contradictory, multiply owned, or orphaned current claim. Before C4/T5, this is
an explicit protected-changeset obligation independently reviewed against the
frozen impact set, not a P0-P3 packet decision dimension or a claim that semantic
currency is automated. C4/T5 later makes it a subject-bound deciding case.

Historical evidence remains append-only and labeled historical. Stale issue
number references, component counts, version values, and paths cannot act as
current authority. The P0-A issue-reference correction for the misleading
#1747 test is a required negative-control fixture for the later C4/T5 currency
capability; it is not proof that the general currency capability already exists.

## 9. Promotion records and release meanings

Plan adoption authorizes only creation of the next A preregistration changeset;
it does not pre-promote P0–P3. Each C packet must be followed by an explicit user
record containing the plan commit/digests, rung/candidate commit, case-manifest
digest, observer/driver digest, proof-packet digest, recovery receipt digest,
and requested release state:

`I promote <P0|P1|P2|P3> candidate <FULL_COMMIT> from plan <FULL_COMMIT> using case manifest <SHA256>, observer <SHA256>, packet <SHA256>, and recovery receipt <SHA256> to <RELEASE_STATE>.`

Release states are sequential:

- #1756: `PRIVATE_CARRIER_RELEASED`;
- #1755: `NATIVE_DISCOVERY_RELEASED`;
- #1758: `RUNTIME_RESOLUTION_RELEASED`;
- #1759: `PLUGIN_CARRIER_RELEASED`;
- #1757 closes only after all four exact records and current P0–P3 reruns;
- #1745 remains blocked until that closure, then restarts C0-A from clean bytes,
  binding the released P0 observer
  and both adopted-plan documents. No pre-prerequisite evidence is reused.

Any non-pass, missing packet, changed bound byte, unmeasured deciding dimension,
unsupported Claude behavior, cleanup failure, surviving mutant, previous-bytes
proof, or unavailable recovery vector stops the sequence. It never triggers a
threshold edit, fallback owner, or inferred pass.

## 10. Corrected execution sequence

```text
adopt this two-document plan set
  -> P0-A observer + immutable P0 cases + hard smoke route
  -> P0-B private-root candidate
  -> P0-C clean proof + explicit PRIVATE_CARRIER_RELEASED
  -> P1-A immutable native-discovery cases
  -> P1-B valid active-only plugin + diagnostic canary
  -> P1-C clean proof + explicit NATIVE_DISCOVERY_RELEASED
  -> P2-A complete resolver migration ledger/cases
  -> P2-B0 resolver, then bounded family migrations (<=25 entrypoints each)
  -> P2-C full P1/P2 re-proof + explicit RUNTIME_RESOLUTION_RELEASED
  -> P3-A fleet/removal ledger/cases
  -> P3-B installed proof, session-epoch fleet switch, recovery rehearsal
  -> P3-C current-byte proof + explicit PLUGIN_CARRIER_RELEASED
  -> close #1757 after all four records and current-byte P0-P3 reruns
  -> restart #1745 C0-A
  -> C0 A/B/C -> C0O A/B/C -> O0a-d D/E/F/G
  -> C0T A/B/C -> T0-T6 -> M0 -> P7 clean-consumer proof
```

## 11. Adoption text

After this file and the ladder amendment are independently reviewed and
committed, calculate both SHA-256 values from committed bytes and update #1757.
Protected work begins only after the user states the exact published adoption
line. That line authorizes P0-A only; later B changesets are authorized by the
immutable P0-A issue/manifest, and every C promotion still requires the exact
record in section 9.

`I adopt plugin-native prerequisite commit <FULL_COMMIT> with ladder SHA-256 <FULL_SHA256> and prerequisite SHA-256 <FULL_SHA256>, and authorize P0-A.`

## 12. Independent critique record

Claude Code 2.1.236 / Opus independently reviewed v1 in persisted session
`b1f76e3f-6e85-42a9-8914-dcfdaa5e2368` and returned `REVISE`. V2 accepts all
fourteen blocking findings: immutable cases, hard smoke routing, earlier bounded
observer, per-rung promotion, unchanged standalone paths/manifest, enumerated
subtraction, guard re-arming, non-blocking canary, honest session/fleet switch,
rehearsed recovery, standalone acquisition, archive relocation, verified issue
identity, and P1 re-proof after bounded P2 migrations. Claude Code 2.1.236 /
Opus then reviewed v2 in persisted session
`8ea6ac0e-d5da-4a4b-a1d2-25f1dcf6509b` and returned `REVISE`. V3 accepted its
five blocking findings: post-P3 delivery semantics replace `deploy-all.sh` in
the later ladder, P3 tests only the currently populated standalone manifest,
old sessions drain before settings removal, the v10 digest is historical
provenance, and #1745 is gated by #1757 closure everywhere. Claude Code 2.1.236
/ Opus reviewed v3 in persisted session
`f09708ff-b4ba-4a62-8dcb-51b817844d31` and returned `PROCEED` with eleven
non-blocking cautions. V4 resolves them by tightening manifest additions and P0
ownership wording, confirming #1737, naming the standalone builder and
install-audit disposition, separating CI packet verification from macOS carrier
execution, giving each rung immutable test-module ownership, classifying
optional standalone members, forbidding session start inside the settings
sub-window, and making pre-C4 documentation review an explicit closeout
obligation. The final exact-byte verdict is recorded externally on #1757 after
review, avoiding a self-invalidating edit to embed the verdict in reviewed
bytes; `PROCEED` is not assumed from these edits.
