# GOAL — Enforcement Proven Everywhere, and Smaller

**Created**: 2026-08-24 · **Revised**: 2026-08-25 (v3 — two adversarial evaluations against stated intent; #1663 answered; 13 internal contradictions fixed) · **Re-baselined**: 2026-08-28 (v4 — §5 resequenced to root-cause order; §7.5 slip counter carries forward, §7.6 added) · **v5 2026-08-29 — MECHANISM added (§2.0): every artifact answers Q1 is-it-connected and Q2 does-it-work; carrier is the existing sidecar, teeth are the existing manifest, declarations are generated, non-conformance is ratcheted. §5 resequenced into Phases 1-3. §7.5 second-rewrite clause confronted, not waived**
**Status**: ABORTED 2026-09-06 · **§7.5 fired: the carried slip plus the missed 2026-08-31 Phase 1 deadline reached the two-slip abort threshold; Phase 2a also remained unmet after 2026-09-03. No third rewrite. Historical evidence and unfinished milestones remain below.**
**Owner**: Andrew Kaszubski (solo dev)
**Supersedes**: `GOAL_2026-07-31.md`

---

## 1. Mission

The product's claim is that its guarantees hold. Measured 2026-08-24, they do not: **4 of 8
block-capable guards fail open silently** under fault injection *in this repo with the full
install*, and realign and spektiv have 27 hooks apiece with **0 proof artifacts**. Meanwhile
the system carries **142,869 lines** of enforcement code, 1,733 lines of agent-improvement
machinery invoked by nothing, 414 tests that have never run in CI, and 262 open issues.

**Correction, 2026-08-25 (MEASURED).** This paragraph originally listed a `SoftFailureTracker`
"requested by 0 tests but advertised in 2 docs" as a sixth dead mechanism. That was **wrong**.
`tests/unit/genai/test_genai_client.py` and `tests/unit/genai/test_soft_failure_thresholds.py`
hold 51 tests that exercise it and pass **51/51** (`pytest tests/unit/genai/ -q`). They read as
absent because both use a bare `from conftest import ...` (introduced 2026-04-11 in #772), which
binds to `tests/integration/conftest.py` whenever `tests/unit` and `tests/integration` are
collected together — so both files raise `ImportError` at collection under the repo's own
`CANONICAL_BASELINE_CMD`. The original "0" was inherited from a run in which they never executed:
**a count over a population that failed to collect, which is the same defect as a pass over zero.**
`SoftFailureTracker` is therefore resolved **WIRED**, not a deletion candidate — acting on the
original line would have deleted 51 passing tests. The import defect is filed separately.

Both halves are the same disease. Unproven guards create false security; unused machinery
creates the impression of coverage. This goal makes enforcement **provable** and the system
**smaller** — and treats an increase in enforcement code without a matching increase in proven
guards as a failure, not progress.

Five properties, from the stated intent: **effective** (guards demonstrably fire), **simple**
(less code, no dead mechanisms), **accurate** (both arms, measured error rates), **durable**
(holds in every repo), **consistent** (one canonical mechanism per rule).

## 2. Definition of Done

### 2.0 THE MECHANISM (v5, 2026-08-29) — every artifact answers two questions

*This section is new. Everything below it states the OUTCOME this goal wants; none of it stated
the MECHANISM, which is why the outcome kept not arriving. Added after six instances of a single
defect shape in one session — see the evidence below.*

**Q1 — Is it CONNECTED?** Something invokes it, and the route is machine-checkable. Prose naming
a module is not a route (INV-1). A manifest entry is not a route. A test that mocks the call site
is not a route.

**Q2 — Does it WORK AS DESIGNED?** Watched doing its job, and watched *not* doing it when it
should not — both arms, against the thing that executes, not the thing that describes it.

**An artifact that cannot answer both is not done.** Shipping one anyway is an explicit recorded
decision, never a default. (Also stated in `PROJECT.md` § DEFINITION OF DONE — and note that
statement enforces nothing on its own, which is the whole point of this section.)

**The carrier is the existing hook sidecar, extended.** `config/hook-metadata.schema.json`
already requires `name`, `type`, `interpreter` and takes `registrations` — that is half of Q1,
for 1 of 6 artifact types. Two required fields close it: **`invoked_by`** (the route) and
**`proves`** (the test that watches both arms). No new format; no new mechanism.

**The teeth are the existing manifest.** A file absent from `install_manifest.json` does not
deploy — that already has force in every consumer repo. Make a manifest entry require a
**verified** declaration, and "unwired" stops being shippable rather than being something a
human is asked to remember.

**Declarations are GENERATED, not hand-written.** The reachability walk already computes the
route for every `lib/` module (116 reached / 132 not). So `invoked_by` is auto-populated for
what resolves, and what does not becomes an honest pinned backlog. This is what makes "bring the
whole repo up to standard" tractable rather than 380 files of hand-editing.

**Non-conformance is RATCHETED, never big-banged.** #1698 found 132 unreached modules and fixed
zero — it pinned the set and refused growth. Same here: pin today's undeclared artifacts, refuse
the next one, reduce opportunistically. No permanently-red signal, and it works from day one.

#### Why this section exists — six instances, one session, 2026-08-28

Every one is *a check whose subject is the artifact's description rather than its behaviour*:

1. A definition-of-done rule written into `PROJECT.md`, whose gate (`validate_project_alignment`)
   is registered in **0** settings surfaces and has emitted **0** refusals (#1639).
2. `--sync-timeouts` silently rewrote an undeclared hook's budget **down to 5** across 7
   surfaces and exited 0 — `reg.get("timeout", 5)` reintroduced under a new name, in the write
   path, inside the fix for exactly that line.
3. The overrun recorder compared elapsed time to the **declared** budget, never the **enforced**
   one — under deploy skew it under-reported 100% of real skips.
4. The coordinator ran `--check-timeouts`, read four printed violations, and reported the
   mechanism as enforcing — with `exit=0` in its own output. It printed; it did not gate.
5. `library_timeout_or` discards its fallback whenever config is readable, so the test claiming
   to "lock the fail-safe literal" compared X to X. Six literals unchecked under a false
   coverage claim — a #1660 tautology inside the fix.
6. `deploy-all.sh`'s `✓ permission patterns: all deny rules syntactically valid` passes on an
   **empty deny list** and on `Frobnicate(~/.ssh/**)`. It green-lit a deploy that removed
   `~/.ssh` write protection.

**None was caught by whoever made it.** Each was caught by something with independent context —
a ratchet, an adversarial reviewer, or the user. That is the empirical case for Q1/Q2 as
*mechanisms* rather than as principles anyone is expected to hold in mind.

#### The layer that does NOT gate

A generative/judgement layer is legitimate for the one uncomputable question — *does this do what
its own docstring claims* — and **cannot be load-bearing**. MEASURED 2026-08-28: `claude -p`
succeeded on **1 of 5** calls, latency 4.6 s → >120 s, with three of five exceeding the 60 s
schema ceiling for hooks. And the existing judge carries a confirmed false negative it passed at
`assert score >= 5`. It may advise. It may not refuse.

---

**Effective — guards demonstrably fire**

> ⚠️ **PARTIALLY MET — and I overclaimed this. CORRECTED 2026-08-25 (same day).**
> I wrote "MET" below on the strength of `proof_of_block`'s **8 declared guards**. The hook
> carries **51 checks** (`docs/audits/unified-pre-tool-51-check-audit.md`, three parallel audits
> 2026-08-21) and ~127 fail-open exception paths (93 `except: pass`, 34 `except -> allow`).
> So the headline rests on a sample of roughly **16% of the checks** and a far smaller share of
> the exception surface. **"8 of 8 guards proven" and "enforcement is proven" are not the same
> claim, and I wrote the second while measuring the first** — the exact "one location is a lower
> bound, not a total" error I corrected in others' numbers and my own four times today.
> **Worse, the gate that most needs a scenario has none.** `CLAUDE.md:11` states the PROJECT.md
> alignment gate — first in the pipeline — **has never refused anything (#1639)**. Grep for
> `alignment|project_md|validate_project` in `proof_of_block.py`: **0 matches**. The prover is
> silent about it, so "8/8 PROVEN" says nothing about the gate with a known zero-refusal record.
> Filed against the detector per the Self-applying criterion. What IS met is stated precisely
> below; what is not is that this generalises to the enforcement surface.
>
> ✅ **What is genuinely met: 0 silent fail-opens across the 8 proven scenarios in ALL THREE
> repos**, six days before the
> 2026-08-31 milestone. Baseline was 4 of 8 here, and 0 consumer evidence anywhere.
> Measured against the **deployed** copies, not the source: autonomous-dev **0**, realign **0**,
> spektiv **0 genuine** — its one remaining row is `write-pipeline-gate` under that repo's
> *committed* `.claude/.bypass`, a documented opt-out rather than a failure (the prover cannot yet
> tell those apart — #1685).
> Two fixes, both root causes rather than reproducers. **#1682**: one shared fallback tuple
> enumerated native transports only, so every MCP write transport classified as a non-write
> whenever `tool_intent` was unavailable — that single defect was 3 of the 4. **#1684**: a corrupt
> plan-exit marker was read as *no* marker, encoding a verification failure as a pass, and the file
> was unlinked so the event left no trace; `st_mtime` supplied the bounded fallback clock its
> author lacked.
> **What makes the zero trustworthy:** #1684 required changing `proof_of_block` itself, because
> its landing proof for `state_corrupt` was *"the marker was unlinked"* — coupled to the very bug
> being fixed. Changing an instrument to move the metric it measures is the shape of gaming, so
> the modified prover was pointed at the **pre-fix deployed hook** (9,229 lines, zero occurrences
> of the fix) and still reported `FAILS OPEN SILENTLY`. The instrument was not taught to stop
> reporting — the zero comes from the hook.
- [~] ⚠️ `proof_of_block.py` reports **0 guards failing open silently** (baseline: 4 of 8) —
      TRUE for the 8 declared scenarios in all three repos, measured against each repo's
      **deployed** copy. **NOT re-checkable as "the criterion is met"**: the denominator is 8,
      the hook has 51 checks, and the alignment gate (#1639, zero refusals ever) has no scenario
      at all. Re-open as met only when the denominator is defensible — see #1689.
- [x] ✅ Every guard shows a **REFUSES and a PERMITS** row — one arm does not count (#1617).
      MET: `8/8 guards PROVEN` in autonomous-dev and realign; `7/8` in spektiv, where the eighth
      is `NOT-ENFORCED` under that repo's committed opt-out and is reported as **UNMEASURED, not
      clean** — an honest "cannot distinguish here" rather than a green cell.
- [x] ✅ **DONE 2026-08-25 — committed proof artifacts in realign AND spektiv** (baseline: 0 in
      both). `spektiv 7a769ac33` (pushed), `realign bb342e12` (committed; push blocked — see
      below). **This clears abort condition 1 ("no consumer proof by 09-07"), 13 days early.**
      The artifacts are not identical, and that is the finding:
      | repo | PROVEN | silent fail-opens | which |
      |---|---|---|---|
      | autonomous-dev | 8/8 | **1** | plan-exit-gate |
      | realign | 8/8 | **1** | plan-exit-gate |
      | spektiv | **7/8** (I wrote 8/8 — wrong, see below) | **2** | plan-exit-gate **+ write-pipeline-gate** |
      **Third truncation error of the session:** I recorded spektiv as 8/8 PROVEN. It was **7/8**
      — the `N/8 guards PROVEN` line sits above the verdict table and I read the output with
      `tail`, so I never saw it and filled the cell from the other two repos. Caught by the #1685
      implementer re-measuring rather than inheriting my number. Same shape as missing the
      `bypass : present` header line, and as reporting 10 unbound hooks from one settings layer.
      **The pattern is not carelessness about a value — it is reading a truncated view and
      completing the picture from expectation.**
      **CORRECTION 2026-08-25, same day — the spektiv divergence is NOT a portability defect.**
      I first wrote that this was one guard behaving differently across repos and read it as
      evidence for "measuring in one repo does not measure everywhere". The observation is real;
      the inference was wrong. **spektiv carries a *committed* `.claude/.bypass`** (tracked since
      `7997575f1`, 17 Jun) — the documented durable per-repo opt-out in `CLAUDE.md`. Under bypass
      the #1435 protected-infrastructure hard floor still holds, which is exactly why the six
      protected-infra/MCP guards still REFUSE there while `write-pipeline-gate` (#1142, an
      ordinary gate) does not. That is the design working as written, not a portability failure.
      Neither autonomous-dev nor realign has a bypass. **So the honest cross-repo reading is
      1 silent fail-open in all three**, plus one deliberate opt-out in spektiv.
      **How I got it wrong is the reusable part:** `proof_of_block` prints
      `bypass : present` in its *header*, and I read its output with `tail`, so I analysed the
      verdict table without the line that explained it. Truncated output is not a summary.
      **The residual defect is real, though, and narrower (#1685):** the prover reports bypass in
      the header but does **not** factor it into the verdict, so a deliberately opted-out gate is
      counted as `FAILS OPEN SILENTLY`. That inflates the count in opted-out repos — and worse,
      makes a *genuine* fail-open there indistinguishable from the opt-out. It is also material
      to this goal: abort condition 3 fires on "more than 4 silent fail-opens", a threshold that
      can now be tripped by consumer repos exercising a supported feature.
      `realign` needed a `.gitignore` fix to make the artifact committable at all: `.claude/*`
      plus a blanket `*.json` at `:84` meant **both** a directory negation and a `**` content
      negation were required — the directory one alone leaves the file caught by `*.json`.
      Carve-out verified not to over-reach (`.claude/logs/`, `.claude/cache/`,
      `SESSION_STATE.json` all still ignored). Its push is blocked by a pre-existing conflict in
      `tests/unit/core/test_dependency_registry.py` with realign **120 commits ahead** of
      `origin/main` — unrelated in-flight work, deliberately not resolved here.
- [ ] **CORRECTED 2026-08-25 — "27 hooks apiece" counts files, not enforcement.** MEASURED across
      project, project-local and user-global settings layers in both repos: **33 hook files on
      disk, 6 bound in settings, and exactly ONE of the six is a blocking gate**
      (`unified_pre_tool.py`; two of the other five are `session_activity_logger.py`, which
      logs). Identical in realign and spektiv because both match `settings.default.json`.
      autonomous-dev binds **16** for itself; the strictest consumer template binds **8**. So the
      product applies ~2× the enforcement to itself that it ships to anyone, and `plan_gate.py`,
      `enforce_file_organization.py`, `stop_quality_gate.py` and `unified_prompt_validator.py`
      reach **no** consumer template at all — not even strict mode. Recorded on #1640.
      **Not proven:** that the 27 unbound files are dead — `batch_permission_approver.py` is
      dispatched from inside `unified_pre_tool.py` rather than bound, so some may be reachable
      through the one gate that is. That distinction is #1674. Quote 6-of-33; do not quote
      "27 dead".

**Simple — fewer mechanisms, not fewer lines**

- [ ] **STANDING RULE (v4, 2026-08-28): a finding that CAN refuse becomes a guard, not an
      issue.** Before filing, ask whether the finding can be expressed as a check that refuses
      automatically. If yes, build the guard and do not file. Issues are reserved for decisions
      that genuinely need human judgement — a budget to choose, a scope call, a tradeoff.

      **Why this is a Definition-of-Done item and not a preference.** Measured 2026-08-28:
      **114 issues opened, 25 closed in 7 days — net +89, 290 open.** Filing runs 4.5× ahead of
      resolving, and §Out-of-scope already names volume as *the symptom* of exactly this. An
      issue at position 290 has near-zero expected value: it needs a human to read, rank and
      act, against a queue growing faster than it drains. A guard costs the same to write and
      then acts forever, unread.

      The comparison is not hypothetical — both happened on 2026-08-28. Five issues were filed
      (#1700, #1702, #1703, #1704, and #1437 reopened) and read by nobody. In the same session
      the #1698 reachability ratchet **refused this goal's own mutation-harness work at
      midnight, unprompted**, forcing it out of `lib/` because its only consumer was itself
      unreached — and the implementing agent retracted a false "the mechanism is live in the
      pipeline" claim as a direct result. One of those two outputs scales without a reader.

      Enforced by abort condition §7.6.

- [ ] **Count MECHANISMS, not lines.** Line count is the wrong denominator — `lib/*.py` is
      120,001 of the 142,869 and is mostly non-enforcement code, so "net lines down" is
      satisfiable by deleting unrelated library code. The metric is the **named dead-mechanism
      list**, each item resolved to `WIRED` or `DELETED`, no item left `UNRESOLVED`:
      | Mechanism | Baseline | Target |
      |---|---|---|
      | Dead guards (#1612) | **CORRECTED 2026-08-25: not 5.** `enforce_orchestrator.py` is LIVE — 42 recorded refusals, latest 2026-08-24, through an invoker found in no settings file and no tracked source (#1675). `PreToolUseWrite-protect-sensitive.sh` is a deferred policy decision, not dead code (#1673). The remaining 3 are unregistered and have never refused, but are **not provably unreachable**: no sink distinguishes "never invoked" from "invoked and allowed" (#1674). Deletion halted, nothing removed. | 3 pending #1674 |
      | ~~`SoftFailureTracker`~~ | **RESOLVED WIRED 2026-08-25** — the "0 tests" baseline was false; 51 tests exercise it and pass 51/51. See the Correction above. | done |
      | Mutation testing (#1668) | **RESOLVED → DELETED 2026-08-25 (scope revised).** Verdict: retire the vendored mutmut. Scope is LARGER than first noted — it also includes `tests/unit/lib/test_acceptance_mutation_testing.py`, **19 tests that all pass while `import mutmut` raises ModuleNotFoundError**. Their own docstring says they are *"static file inspection tests that verify the mutation testing infrastructure is properly set up"*: they assert a line exists in a requirements file, a config section exists, a script is executable, a report exists. Not one asserts the tool runs. **That is why #770 could be closed as done** — 19 green tests over a mechanism that has never executed, the cleanest instance of #1587s thesis in the repo. KEEP `test_mutation_killers.py` (13 real boundary tests, needs no mutmut) and the conceptual explanation shipped at `skills/testing-guide/SKILL.md:585`. It is a *second* mechanism for a rule already served by a working one — the subprocess mutation harnesses in `test_hook_reachability_ratchet.py` (48 tests, `_substitute` asserts `count == 1` so a zero-match anchor is refused) and `test_vacuous_test_ratchet.py` (8 tests, external-witness injection), plus the #1682 drift guard watched failing under two source perturbations this session. Deletion scope is only `setup.cfg`'s `[mutmut]` section and `scripts/run_mutation_tests.sh`. **Correction, then correction OF the correction — the second one was mine.** I first "corrected" #1668's citation by asserting `requirements-dev.txt` does not exist. It does: `plugins/autonomous-dev/requirements-dev.txt:13`, `mutmut>=2.4.0`. The original citation was substantively right and merely omitted the path prefix; I had checked the repo root, found nothing, and declared absence. **A search establishing PRESENCE may stop at the first hit; a search establishing ABSENCE must be exhaustive** — and every absence claim I got wrong today (10 unbound hooks when it was 3; spektiv 8/8 when it was 7/8; an unseen `bypass : present`) was a partial view narrated as a total. An over-correction is still an error. **Recorded gap:** #770's actual ask — broad `lib/` mutation coverage — remains unbuilt, and is logged rather than quietly dropped. | resolved |
      | ~~Mutation testing, original entry~~ | **ADDED 2026-08-25.** `mutmut` pinned, `[mutmut]` in setup.cfg, runner script executable, baseline report committed — and it has **never run**: every cell is `TBD`, `import mutmut` fails, and the script is referenced by no CI job, manifest, command or runbook. Issue #770 was **closed as done** on it 2026-04-11. | 0 unresolved |
      | `SessionStart-batch-recovery` (#1672) | **ADDED 2026-08-25, CORRECTED same day.** My first entry said it "ships (`install_manifest.json:101-102`)" — **wrong**; those lines are `deploy_state.py` and `genai_install_wrapper.py`, and the hook appears **nowhere** in the manifest. So it neither ships nor is bound, while `CLAUDE.md:69` documents it as *the* session-continuity mechanism — consumers never receive the file. The wrong line number was inherited from a glance rather than measured at point of use. | 0 unresolved |
      | `enforce_file_organization.py` (#1672 comment) | **ADDED 2026-08-25.** Ships in the manifest and is declared `PreToolUse` in `settings.autonomous-dev.json`, but is bound in **no live settings layer** and is **absent from `settings.default.json`** — the template consumers install. Meanwhile `PROJECT.md:38` lists "File organisation enforcement" as in-scope and `PROJECT.md:95` names it as hook-enforced. | 0 unresolved |
      | Reviewer improvement machinery | 1,733 lines, 0 invocations | 0 unresolved |
      | genai tests calling no judge | **176 CONFIRMED EXACT 2026-08-25** (238 of 414 do call one). **60 of the 176 belong to #1688's reviewer-machinery cluster** — `test_acceptance_reviewer_improvement.py` 35/35 and `test_acceptance_benchmark_expansion.py` 25/29 — so resolving #1688 as DELETED removes them automatically. **Residual genuinely separate: 116.** These rows are NOT independent and must not be summed. *Methodology note:* a file-granularity count (files where NO test calls a judge) gives **103**, not 176 — the ledger's figure is per-TEST. I matched the methodology before comparing rather than "correcting" 176 to 103, which is the error I made earlier today on `requirements-dev.txt`. | 116 residual |
      | Dark test files | 95 across 7 dirs | 0 unresolved |
      | **A whole second test suite** (ADDED 2026-08-25) | **MEASURED: `plugins/autonomous-dev/tests/` holds 500 collectable tests that nothing runs.** It has its own `plugins/autonomous-dev/pytest.ini` — 6 markers where the root declares 15, `--strict-markers` on in both, **no `--cov` at all** (so no coverage floor; a sixth declaration site for #1677), and no `norecursedirs`, so it collects `archived`. The root suite cannot reach it (`testpaths = tests` resolves to the repo-root tree), and `.github/` + `scripts/` contain **zero** references to the path. It also has **3 live collection errors** (`test_claude_alignment.py`, `test_doc_change_detection.py`, `test_enforce_logging_only.py`). Not in `install_manifest.json`, so it does not ship. **May overlap the 95-dark-files row above — that row does not name its 7 dirs, so the overlap is unquantified and these must not be summed.** | 0 unresolved |
- [ ] **No net new mechanism without a retirement.** Each mechanism added under this goal names
      one retired or wired in the same change. Enforced by review, recorded in the ledger.
- [ ] Every deletion **names what it removed and why** — a bulk removal does not satisfy this

**Accurate — claims are measured**
- [ ] `test-master` cannot emit a test without an **observed failure against a mutated
      target**, enforced by hook (#1660 at the agent boundary)
- [ ] The improvement loop produces a **first weakness report** for at least one agent using
      **deterministic checks only** — cited `file:line` resolves, claimed commands were
      actually run, verdict stability across identical input. No LLM, no cost, not blocked.
      **Threshold: ≥3 findings, each independently confirmed true by re-running the check.**
      "≥1 finding" is satisfiable without doing the work — the #1660 defect, and it was in
      v2 of this document.
- [ ] Every mechanism shipped under this goal has a **bypass-hunt record**.
      **Threshold: ≥5 distinct evasion shapes attempted, each with a recorded outcome, and at
      least one drawn from a category the mechanism's author did not anticipate.** Ships when
      the successful-evasion list is empty or the survivors are named and accepted.

**Outcome — did the system get better at its job, not just better guarded**

Every other criterion here is internal (guards fire, mechanisms resolved, tiers bounded). This
one asks whether the product improved. Without it the goal can be fully met while the tool is
no more useful than today.

- [ ] **Rework-per-fix falls below the 2026-08-24 baseline.** MEASURED from existing git
      history, no new instrumentation: a `fix(...)` commit re-touching a production file that
      another `fix(...)` touched ≤7 days earlier, excluding `CHANGELOG.md`, `docs/`, `tests/`,
      `.claude/` and all `*.md` (those are touched by convention on every fix — counting them
      measures hygiene, not rework, and doing so inflated the raw figure from 66 to 180).
      | Window | Fixes | Rework | Rework-per-fix |
      |---|---|---|---|
      | 60→30 days ago | 40 | 15 | **37.5%** |
      | last 30 days | 76 | 66 | **86.8%** |
      Concentrated in `unified_pre_tool.py` (10×), `pipeline_completion_state.py` (6×),
      `agent_dispatch_sentinel.py` (5×).
- [ ] **The metric is controlled before it gates anything.** It currently discriminates between
      periods, which is a positive control. It still lacks a negative control: it cannot
      distinguish "fixed badly, three times" from "fixed deliberately in three passes." Until
      that is resolved the number is *tracked and reported*, never used to block.
- [ ] **Remediation cycles per pipeline run** are recorded per run and trend down. Baseline
      2026-08-24: three remediation cycles on a two-line comment fix.

**GenAI transport — standing constraint**
- [ ] **All GenAI in this system runs via `claude -p`.** Not OpenRouter, not a paid
      `ANTHROPIC_API_KEY`. Known call sites that violate this today:
      `scripts/run_reviewer_benchmark.py:69` (`Anthropic(api_key=...)`),
      `plugins/autonomous-dev/lib/genai_validate.py:82-118`, `tests/genai/conftest.py:224-232`.
- [ ] The `claude -p` invocation is **one shared helper**, not copied per call site — extending
      the proven one at `scripts/extract_and_label_intent_corpus.py:717-790`
      (`--output-format json`, `--max-turns 1`, `cwd=Path.home()` for #1064, fence stripping
      for #1065, envelope error checks)
- [x] Design assumes the **CI-measured** cost, not the laptop one. MEASURED in Actions
      2026-08-25 (spike run 32762603032), 5 sequential judge-sized calls:
      3469 / 3951 / 3850 / 5250 / 4923 ms → **median 3.95s**, roughly 2× faster than the 7.6s
      measured locally. Recomputed: 137 judges × 1 trial = **9.0 min** (now inside a 10-min
      cap); × 5 trials = **45.1 min** (still nightly). Calibrating against the local number
      would have over-estimated by 2× — the same wrong-environment error as the 512 pin.
- [ ] **Parse the envelope, never the exit code.** MEASURED: the negative control returned
      **exit 0** while failing, with the failure carried in `is_error: true` inside the JSON.
      Any helper that checks `$?` will read auth failure as success.
- [ ] Concurrency re-tested rather than assumed away. MEASURED: no `~/.claude/.credentials.json`
      exists in Actions (`P5_CREDS_ABSENT`), so GH #24317's file-corruption mode appears
      inapplicable there. If parallelism is safe, the 45 min falls substantially.

**Durable — it holds outside this repo**
- [ ] Every tier reports **EXECUTED=N**; a tier reporting success over zero **fails**
- [ ] `.claude/.bypass` is no longer all-or-nothing (#1647)
- [ ] Every rule discovered during this goal ends as a **hook, a shipped script, or an
      explicitly-recorded known gap** — never as prose alone
- [x] **#1663 ANSWERED 2026-08-25** (spike run 32762603032, workflow since deleted).
      `claude -p` **does** authenticate in GitHub Actions on `CLAUDE_CODE_OAUTH_TOKEN`:
      exit 0, `is_error:false`, 4s. The negative control (same call, token removed) returned
      `is_error:true`, so the token is what made it work. `--bare` returned
      `"Not logged in · Please run /login"` — **GH #38022 confirmed** in this environment.
      Unverified and worth checking against billing: the envelope reported
      `total_cost_usd: 0.037342` per call, which on a Max subscription is probably nominal
      accounting rather than a charge — but "it's $0" has not been proven.

**Consistent**
- [ ] No rule has two mechanisms; no mechanism has two divergent copies (the duplicate
      `GenAIClient` in `templates/genai-uat/` is the known instance)
- [ ] **The coverage floor is one number, not five (#1677, ADDED 2026-08-25).** MEASURED: one
      rule declared at five sites with two values — `pytest.ini:24` = **4**;
      `auto_test.py:98`, `safety-net.yml:133`, `PROJECT.md:85` and the shipped
      `python-standards/SKILL.md:184` = **80**. The lowest is the only one that executes on
      every local run, and its "never decrease this value" instruction (`pytest.ini:23`) has
      **no mechanism whatsoever** — no test, hook, script or workflow reads it. A ratchet whose
      entire enforcement is a code comment is the INV-1 case in miniature. Actual coverage is
      **UNKNOWN** and must be measured before any floor is moved, or the fix becomes #1576's
      cry-wolf pattern a second time.

**Self-applying — the detector is subject to its own rules**
- [ ] Every mechanism built under this goal is **itself** subject to the rules it enforces: it
      has both arms observed, a bypass-hunt record, and an entry in the dead-mechanism ledger
      if it stops being invoked. No mechanism is exempt because it is the one doing the checking.
- [ ] **When the detector misses something, that becomes a filed finding against the detector.**
      Concretely: any defect found by a human, an agent, or a later session that a shipped gate
      *should* have caught results in an issue naming the gate that missed it — not only the
      defect. Baseline evidence this is needed: the four silent fail-opens were found by fault
      injection, not by any gate; the #1620 fix was flagged as undeployed four times by a
      findings store nobody read; and this goal's own v2 contained the exact tautology defect
      filed as #1660 four hours earlier.

## 3. Scope Boundaries

**In scope** — the 4 silent fail-opens; cross-repo proof in realign and spektiv; deletion of
dead mechanisms; `test-master` output enforcement; the deterministic half of the agent
improvement loop; tier-execution honesty; bypass granularity (#1647); ~~the #1663 spike~~
(**done 2026-08-25**); the known-red running tiers (§7a).

**Out of scope, with reasons** — draining the 262 backlog (volume is the symptom; it grew from
108 while guards rotted). The genai tier's LLM half and agent calibration corpora (#1566,
#1664): **no longer transport-blocked as of 2026-08-25** — the spike showed `claude -p` works
in Actions at a CI-measured 3.95s median, so one non-repeated pass over 137 judges is ~9 min
and fits a 10-min cap, while 5-trial calibration at ~45 min does not. They stay out of scope
here because they still need a corpus that does not exist and a redesign around nightly or
sampled execution — but the reason is now scope, not impossibility. anyclaude: no install
detected.

## 4. Success Criteria

| Criterion | Verification | Threshold | Source |
|---|---|---|---|
| No silent fail-open | `python3 plugins/autonomous-dev/scripts/proof_of_block.py` | 0 silent fail-opens | MEASURED: 4 of 8 |
| Both arms per guard | same | every guard REFUSES **and** PERMITS | #1617 |
| Proof in consumer repos | run in `~/Dev/realign`, `~/Dev/spektiv` | artifact committed, exit 0 | MEASURED: 0 |
| Dead mechanisms resolved | per-item check against the §2 table | **0 items UNRESOLVED** | 5 guards, tracker, 1,733 lines, 176 tests, 95 files |
| test-master enforcement | write a test with no failure-proof | REFUSED; proven one PERMITTED | #1660 |
| First weakness report | the deterministic loop | **≥3 findings, each re-confirmed**, 0 LLM calls | §2 |
| Bypass-hunt per mechanism | the record | **≥5 evasion shapes, ≥1 unanticipated** | §2 |
| Tier honesty | CI on master | every tier prints EXECUTED=N; N=0 fails | integration precedent |

## 5. Milestones

> **v4 RE-BASELINE, 2026-08-28 — explicit scope change, user-approved, reason recorded.**
> The v3 plan below was written 2026-08-24 against facts that 08-27/28 measurement falsified.
> Milestone 1 (`test-master` enforcement, 2026-08-27) **slipped by one day and is partially
> delivered**; under §7.5 that is slip #1, and 08-29 was on track to be slip #2 and abort the
> goal. Rather than slip silently (drift) or race a threshold that says *"≥3 findings each
> independently re-confirmed"* (gaming — the exact defect filed as #1660), the plan is rewritten
> against what is now known. **The abort clause stays armed, against the new dates.** The
> mission and the Definition of Done are UNCHANGED; only sequencing moves.
>
> **The three measurements that invalidated the old plan:**
> 1. **The LLM tier is dead, and it is dead on a PAID dependency this project forbids.**
>
>    > **CORRECTED 2026-08-28, same day, before acting on it.** My first version of this bullet
>    > said the tier "cannot succeed as configured" because `claude -p` is 12,766 ms against a
>    > 5 s budget, and cited the 76.8% fail-open as agreeing telemetry. **The causal claim was
>    > false and I am not leaving it in.** The two facts are unrelated: `intent_classifier`
>    > does not use `claude -p` at all. It calls `GenAIAnalyzer` (`hooks/genai_utils.py`), which
>    > uses the **Anthropic SDK on `ANTHROPIC_API_KEY`**. Measured: no key is set (correctly —
>    > INV-8 forbids paid dependencies), so the client is `None`, `_get_analyzer()` returns
>    > `None` at `:665-666`, and every call short-circuits to `fail_open` before any timeout is
>    > consulted. **The 76.8% is an AUTH failure, not a budget failure** — which is exactly what
>    > #1593's title says, and I read the timeout into it because I had just measured a timeout.
>    > A correlation between two numbers I happened to hold at once.
>
>    What is measured and stands: 42,100 classifications → `fail_open` 32,322 (76.8%),
>    `regex` 9,408 (22.3%), `llm` 370 (0.9%). No API key present; `GenAIAnalyzer.client is None`.
>    The tier was built on a metered API that INV-8 forbids, so it is correctly unconfigured and
>    therefore permanently dead. **The fix is the `claude -p` migration (#1000), not a budget.**
>
>    The budget matters *next*, not now: at **12,766 ms median** (3/3 calls 12.2–13.1 s),
>    `claude -p` cannot fit a 5 s hook slot, so the timeout work is a **prerequisite for the
>    migration** rather than a cure for today's fail-open. Sequencing is unchanged; the reason
>    is. This also corrects v3's 3.95 s figure, measured in Actions and 2.5× optimistic locally.
>
>    A third independent `5` was found while establishing this: `genai_utils.py` carries its own
>    `DEFAULT_TIMEOUT`, alongside `intent_classifier_config.json:timeout_seconds` and the hook
>    registrations — three declarations, no shared source.
> 2. **Detectors do not reach the repos they protect.** `install_manifest.json` ships **0**
>    `tests/` paths, so every ratchet built under this goal (#1588, #1593, #1667, #1698) is
>    canonical-repo-only. realign and spektiv have `prior_art_search.py` and **no** reachability
>    ratchet. The 2026-09-21 "cross-repo proof" milestone had no delivery mechanism under it.
> 3. **Hook budgets silently drop enforcement.** 266 of 84,339 invocations exceeded 5 s in one
>    week; 23 were `unified_pre_tool.py`, each skipping all ~51 checks at once. Letting them all
>    finish costs **803.8 s — about 13 minutes across the entire week**.
>
> **And one about how we were working**, which changes the method rather than the dates:
> **114 issues opened, 25 closed in 7 days — net +89, now 290 open.** Filing is running 4.5×
> ahead of resolving, and this goal already names the backlog as *the symptom*. New standing
> rule, §2-enforced: **a finding that can refuse becomes a guard, not an issue.** Issues are
> reserved for decisions needing human judgement. Evidence it works: the #1698 ratchet refused
> this goal's own 2026-08-28 work, unprompted, before any human read anything.

| Date | Deliverable | Verification |
|---|---|---|
| ~~2026-08-27~~ **DONE 2026-08-25** | ~~#1663 spike~~ — pulled forward and answered | Run 32762603032; abort 2 retired. **Latency figure superseded — see v4 note** |
| ~~2026-08-27~~ **PARTIAL 2026-08-28** | `test-master` failure-proof enforcement (#1660) | Harness shipped `a87c0ca2`: 5 blocking defects fixed red→green, 8-shape bypass hunt, 78 tests. **NOT met** — no producer, so it is a harness test-master *may* use, not one it *cannot* avoid. Slip #1, recorded |
| ~~2026-08-30~~ **DONE 2026-08-29** | #1704 — one canonical timeout config, sized from measurement | Shipped `63c1769d`, **deployed and verified in the executing copy**: `unified_pre_tool` 5→20, `unified_prompt_validator` 5→50, `hook_budgets.py` present in `~/.claude/lib/`. `--check-timeouts` exits 0 against installed settings — the skew gate went green because the skew was removed. 120 tests. Three review rounds removed three defects **from the fix itself** |

### v5 PHASES (2026-08-29) — the §2.0 mechanism, sequenced

> Replaces the remaining v4 rows. Rationale in §2.0; the abort-clause confrontation is in §7.5.
> **Phase 1 is smaller than the work it replaces** — that is deliberate, and it is the test of
> whether this is a mechanism or another plan.

| Date | Deliverable | Verification |
|---|---|---|
| **2026-08-31** | **PHASE 1 — new work cannot regress** | Two required schema fields (`invoked_by`, `proves`) in `hook-metadata.schema.json`; `install_manifest.json` refuses an entry whose declaration does not verify. Both arms: a conforming artifact ships, a non-conforming one is REFUSED. Existing corpus untouched — pinned, not fixed |
| **2026-09-03** | **PHASE 2a — declarations GENERATED for `lib/` and `hooks/`** | `invoked_by` auto-populated from the reachability walk for the 116 reached modules; the 132 unreached pinned as the honest backlog. Hand-written declarations are a smell — if the generator cannot derive a route, that IS the finding |
| **2026-09-07** | **PHASE 2b — corpus extended to `scripts/` and `config/`** | The two artifact types that let `--check-timeouts` and `hook_time_budgets.json` ship unwired. Ratchet from a measured baseline; no big-bang |
| **2026-09-09** | **MID-POINT ABORT REVIEW (§7)** | ≥1 consumer proof artifact; 0 UNRESOLVED items ≤ baseline; **net issue delta ≤ 0 over the preceding 7 days**; **Phase 1 gate observed REFUSING** |
| **2026-09-12** | **PHASE 3 — the checks that fire on the COORDINATOR** | Claim-binding: a report of the form "X refuses" must carry a captured non-zero exit code, or it is rejected. CIA 2026-08-28: *"no mechanism binds a claim to a captured exit code"* — the gap that let a print statement be reported as a gate. Plus the periodic conformance reader, so drift surfaces without being asked for |
| 2026-09-14 | Producer for #1660 — closes the slipped milestone | test-master emits a claim per new test; the completion sink refuses a return adding test files with zero claims. `test_no_producer_exists_yet` goes red |
| 2026-09-16 | Deterministic weakness report for one agent | **≥3 findings, each re-confirmed**, 0 LLM calls |
| 2026-09-18 | 4 silent fail-opens fixed; dead mechanisms resolved | `proof_of_block` → 0 silent fail-opens; **0 items UNRESOLVED** in the §2 table |
| 2026-09-21 | #1703 + cross-repo proof in realign and spektiv | Detector ships; baselines per-repo, never inherited; both arms proven **in a consumer**; committed artifacts in both |
| 2026-09-25 | Collected-floor generalised; dark tiers resolved | EXECUTED=N per tier; each of the 95 files run or removed with a stated reason |

## 6. Tracking

**Must close**: #1612, #1617, #1636, #1647, #1660, #1661, #1662
**Answered, close on next pass**: #1663 (spike run 32762603032, 2026-08-25)
**Re-scope**: #1566, #1664 — **no longer gated on #1663**; both now need a corpus that does not
exist and a nightly/sampled design around the CI-measured 3.95s, not a transport decision
**Artifacts**: this document; `tests/proofs/` in realign and spektiv; the bypass-hunt records;
the first deterministic weakness report
**Memory**: `feedback_enforcement_not_memory.md`, `project_pipeline_gate_history.md`

## 7. Abort Conditions

1. **Mid-point stall (2026-09-07)** — no consumer-repo proof artifact by this date. Pivot:
   re-scope to autonomous-dev only; file the cross-repo work as its own goal.
2. ~~**Transport dead-end** — #1663 returns no $0 path.~~ **RETIRED 2026-08-25.** The spike
   answered it: `claude -p` authenticates in Actions on `CLAUDE_CODE_OAUTH_TOKEN`, median
   3.95s per judge-sized call. This condition can no longer fire. Replaced by: **if the
   `total_cost_usd` reported per call turns out to be a real charge rather than nominal
   subscription accounting, STOP** — that would make every GenAI gate a paid dependency and
   violate INV-8.
3. **Enforcement regression** — `proof_of_block.py` reports more than 4 silent fail-opens at
   any milestone. Pivot: freeze feature work, fix the regression first.
4. **Complexity regression** — the dead-mechanism list has **more UNRESOLVED items** at the
   mid-point than at baseline, or a mechanism was added without a retirement. Pivot: stop
   adding, resolve first. Adding to a system already carrying 142k lines of unproven
   enforcement is how this state was reached.
5. **Schedule abort (v3 — the time-box must bite).** If **two or more milestones** slip past
   their dates, STOP and re-scope. v2 said slip "is expected and is not itself an abort
   trigger," which neutered the time-box that was chosen as the kill switch — a schedule with
   no consequence is decoration. Velocity evidence for the scepticism: on 2026-08-24 a
   **two-line comment fix** consumed a full pipeline and three remediation cycles. Milestone
   dates below are estimates against that observed rate, not aspirations.

   > **v4 status, 2026-08-28.** **Slip #1 is on the board**: `test-master` enforcement
   > (2026-08-27) is partially delivered — harness shipped, producer absent. **One more slip
   > aborts.** The clause is armed against the §5 v4 dates, NOT the v3 dates. This re-baseline
   > must not be read as resetting the counter: the counter carries forward, deliberately, so
   > the kill switch still bites. A re-baseline is available **once**; a second one is itself
   > an abort, because a plan rewritten twice to avoid its own deadline is drift wearing
   > process.
   >
   > **v5 CONFRONTS THAT CLAUSE HEAD-ON, 2026-08-29.** §2.0 and the §5 phases are a second
   > rewrite of this document within 24 hours. The clause immediately above says that is an
   > abort. **I am not going to smooth that over.**
   >
   > **The argument for proceeding:** v4 rewrote the SCHEDULE against facts that falsified its
   > dates. v5 rewrites the MECHANISM — it does not move a deadline, it specifies how the
   > Definition of Done gets met at all. The old §2 named outcomes ("every guard proven refusing
   > AND permitting") and never named a mechanism, which is why the outcome kept not arriving.
   > No milestone was made later to accommodate a slip; Phase 1 is *smaller* than the work it
   > replaces.
   >
   > **The argument against, recorded because it is the stronger-looking one:** "this rewrite is
   > different in kind" is precisely the reasoning anyone would use to dodge an abort clause,
   > and a clause that yields to a good argument is not a kill switch. Someone reading this in a
   > month should weigh that seriously.
   >
   > **Disposition:** the user was asked explicitly, with the goal's one slip and this clause in
   > view, and chose to rewrite. That decision is the record — not my argument for it. **The
   > slip counter still stands at 1 and still carries forward.** No third rewrite: if the Phase
   > dates in §5 slip, the goal aborts, and this clause is not available again.

6. **Backlog-growth abort (v4, NEW).** If the **net issue delta over any trailing 7 days is
   positive** at a milestone check, STOP filing and resolve. Measured 2026-08-28: **114 opened,
   25 closed, net +89, 290 open** — filing is running 4.5× ahead of resolving, and this goal's
   own §Out-of-scope names volume as *the symptom*. The pivot is not "file fewer findings," it
   is **§2's standing rule: a finding that can refuse becomes a guard, not an issue.** The
   evidence that guards outperform issues here is this goal's own: the #1698 ratchet refused
   the 2026-08-28 mutation work unprompted, at midnight, before any human read anything —
   while five issues filed the same day were read by nobody.

## 7a. Known-red CI is in scope, not deferred

"Consistent" cannot hold while tiers that DO run fail constantly. Baseline MEASURED
2026-08-24: unit **104** failures, regression **205**, integration **521** (ratcheted).
- [ ] Every running tier has a **pinned failure ceiling that may only decrease** — the
      integration ratchet generalised, so a tier that runs and fails 205 times is bounded
      rather than ignored
- [ ] No tier is left both running and unbounded. A permanently-red unbounded tier trains
      dismissal of the whole class, which is how the integration tier stayed dark for months.

## 8. Progress Ledger

- `proof_of_block.py` — headline metric, on demand
- The **§2 dead-mechanism table** — the simplicity metric. Count items still `UNRESOLVED`.
  Deliberately NOT `wc -l` on hooks+lib: that was v2's metric and it is gameable, since
  `lib/*.py` is 120,001 of the 142,869 lines and mostly is not enforcement code.
- `gh issue list --state open | wc -l` — 262 at baseline (MEASURED 2026-08-24)
- **Headline metric RE-MEASURED live 2026-08-25** (not inherited): `proof_of_block.py` reports
  **8/8 guards PROVEN, 4 failing open silently** — the 2026-08-24 baseline holds. The instrument
  passed all seven of its own controls (fault positive, fault negative, trace positive, trace
  negative, and three classifier arms), so the number is trustworthy at the point of use.
  **Root-caused the same day: 3 of the 4 are ONE defect, not three** (#1682). `_ti_is_write()`'s
  fallback at `unified_pre_tool.py:132` is a literal four-tuple of *native* tool names, so with
  `tool_intent` unavailable every MCP write transport classifies as a non-write. Driven
  end-to-end against the real hook: `Write`→DENY, `Edit`→DENY,
  `mcp__serena__replace_symbol_body`→**ALLOW**, `mcp__serena__rename_symbol`→**ALLOW**,
  `Read`→ALLOW (correct). So `CLAUDE.md`'s promise that the #1435 floor holds for "an MCP editor
  such as `mcp__serena__replace_symbol_body`… even under bypass" is false under fault.
  **And the prover cannot see it**: its hard-floor scenario is `/ Write`, the one transport the
  fallback tuple saves — a guard certified by the arm that survives. The 4th fail-open
  (`plan-exit-gate` / `state_corrupt`) is a genuinely separate cause and looks like an INV-7
  breach: a corrupt marker is treated as "stage not active", i.e. as *fewer* restrictions.
- **A set diff needs an environment control too** (MEASURED 2026-08-25). The *Outcome* criterion
  tracks rework-per-fix, and the operating rule is "attribute by set, not count". That rule is
  necessary and **not sufficient**. Attributing `tests/unit` failures for #1666 via a `git
  worktree` baseline produced 3 "new failures" and 16 "fixes" — a credible-looking regression
  signal in which **all 19 were artifacts**: `.claude/lib` is gitignored (`.gitignore:147`), so a
  worktree has no installed copy, and tests asserting the installed copy exists flip against
  tests asserting it does not. Zero were attributable to the change. The instrument that held was
  structural, not comparative — no file under `tests/unit/` outside `tests/unit/genai/` references
  the changed modules, so the change could not reach them. **Any rework-per-fix figure taken from
  a worktree run in this repo is contaminated by ~19 tests before it measures anything.**
- **Both-arms observations recorded as they happen** — the goal's headline criterion is one
  REFUSES row and one PERMITS row per guard, so they are logged when observed rather than
  reconstructed later:
  - `agent_ordering_gate` — **PERMITS** `implementer` after `planner` completed (`ORDERING OK`);
    **REFUSES** `doc-master` before the pytest gate closed, and `continuous-improvement-analyst`
    before `doc-master` (`ORDERING VIOLATION ... requires [pytest-gate] to complete first`).
    Both arms, same session, 2026-08-25. ✅
  - `prompt_integrity` — **REFUSES** an implementer dispatch compressed 24% below the 980-word
    baseline; **PERMITS** the reconstructed dispatch carrying the planner's full output. The
    refusal was *correct*: the coordinator had paraphrased the plan instead of passing it
    verbatim, which is the FORBIDDEN behaviour the gate exists to catch. Both arms. ✅
  - `test_issue_1666_no_bare_conftest_import` — **REFUSES** two scratch files (`from conftest
    import Foo`, `import conftest`); **PERMITS** a package-qualified import *and* a
    different-shaped near-miss (`import conftest_helpers`) that a naive prefix match would have
    false-flagged. Verified by the coordinator independently of the implementer's own run. ✅
- **The four-number attrition chain** (MEASURED 2026-08-25) — the denominator this goal actually
  needs, because each step silently drops guards the previous step counted:
  **33 on disk → 26 shipped → 15 bound in any template → 12 bound in live settings.**
  Enumerate ALL settings layers (project, project-local, user-global, managed) — reading only
  `.claude/settings.json` reported 10 unbound where the true figure is 3, because seven are
  bound via `~/.claude/settings.json`. Caveats that must travel with the number: several
  manifest entries are not lifecycle hooks (`genai_utils.py`, `genai_prompts.py`, `setup.py`,
  `*.hook.json`), and at least one — `batch_permission_approver.py` — is dispatched from
  `unified_pre_tool.py` rather than bound in settings, so "not bound" is **not** "dead". That
  ambiguity is #1674, and it bounds how far this chain can be read as a coverage figure.
- `collect_cia_findings()` over `.claude/logs/findings/` — readable since #1658
- This document, updated per milestone with deltas named

---

**Risks stated at creation.** (a) The headline metric depends on two repos whose roadmaps this
goal does not own — abort 1 catches that at the mid-point. (b) The dead-mechanism criterion can
be gamed by deleting tests rather than dead code; every deletion must name what it removed and
why, and the dark-tier item requires a stated reason per file rather than a bulk removal.
(c) Seven milestones in four weeks against a 262-issue backlog and a red CI is aggressive —
and **two slipped milestones abort the goal (§7.5)**. That is deliberate: the time-box was
chosen as the kill switch, so it has to bite.

> **v2→v3 correction.** v2's footer read "milestone slip is expected and is not itself an abort
> trigger — only the four conditions above are." That sentence cancelled abort 5 while abort 5
> sat forty lines above it, and it miscounted the conditions. It survived because I edited
> sections without re-reading the document end to end — the same drift this goal exists to
> catch, found only by printing the whole thing. Logged rather than silently overwritten.
