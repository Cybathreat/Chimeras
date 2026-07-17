# Chimeras v2 Development Roadmap

**Scope**: Transform Chimeras from a fixed linear pipeline into a true **adaptive reasoning swarm** where WarChief acts as a real pentester lead: dispatching agents, adapting to findings, improvising when plans fail, and routing dynamically based on what the team discovers.

---

## Current State (v1)

### What Works
- ✅ Core agent framework (BaseBot, LLM routing, tool execution)
- ✅ Scope enforcement (category-based tool scoping)
- ✅ Human approval gate before exploitation
- ✅ File-based inter-bot communication
- ✅ Professional report generation
- ✅ Provider abstraction (OpenAI, Anthropic, Groq, custom endpoints)

### Critical Gap
- ❌ WarChief runs once, writes plan, exits. Never re-enters.
- ❌ No dynamic routing. Fixed linear pipeline: WarChief → ARIA → Lisa → Bloodhound → gate → Pathologist → Surgeon → Magician → Thief → Bookkeeper → END.
- ❌ No adaptation. If recon finds nothing, swarm still executes full scanning. If scanning finds zero services, swarm still proceeds to vuln detection.
- ❌ No decision loop. `next_bot`, `mission_phase`, `needed` fields in WarChief output are **dead code** — never read by the graph.
- ❌ No pivoting. Cannot redirect to lateral movement recon if initial scope is exhausted.

---

## v2 Vision

### High-Level Goal
**WarChief becomes a dynamic router** — a real pentester who:
1. Plans the initial engagement
2. **Re-evaluates after each phase** (recon, scanning, vuln detection, post-exploit)
3. **Routes the next action** based on actual findings vs. plan
4. **Adapts scope** when initial targets don't pan out
5. **Decides loopback vs. forward progression**
6. **Handles failure gracefully** (dead-end vectors, blocked paths, insufficient data)

### Architecture Shift
```
v1 (linear):
WarChief (once) → ARIA → Lisa → Bloodhound → gate → Pathologist → Surgeon → Magician → Thief → Bookkeeper → END

v2 (adaptive loop):
WarChief (init) → ARIA → WarChief (route) ⇄ Lisa → WarChief (route) ⇄ Bloodhound 
              → WarChief (route) ⇄ [gate] ⇄ Pathologist → Surgeon → WarChief (route)
              → Magician → Thief → WarChief (final) → Bookkeeper → END
```

### WarChief Decision Points
1. **After ARIA (recon)**: "Do we have enough targets to scan? Need deeper OSINT? Pivot scope?"
2. **After Lisa (scanning)**: "Do we have enough data for vuln detection? Need more scanning? Insufficient data to continue?"
3. **After Bloodhound (vulns)**: "Do we have exploitable vulns? Need more recon/scanning? Should we pivot?"
4. **After Surgeon (exploitation)**: "Did we get initial access? Need lateral recon? Try different vector? Jump to privesc?"
5. **After Magician (privesc)**: "Did we escalate? Need lateral movement? Continue exfil? Mission complete?"
6. **After Thief (exfil)**: "Did we get the data? Can we do more? Or close out and report?"

---

## Implementation Phases

### Phase -1: Prerequisites & Risk Closure (BLOCKING — must land before Phase 3)
**Goal**: Close the scope-enforcement gap before adding autonomy that depends on it. v1's `ScopeEnforcer` only validates the tool category (first word of the command); it never validates the *target*. Building lateral-movement pivoting (Phase 3) on top of that means WarChief could autonomously direct exploitation at hosts nobody authorized, with the LLM's judgment as the only safeguard. This is not acceptable for a tool marketed as "for authorized security testing only."

- [ ] **Hard target/CIDR validation in `tool_executor.py` or `scope.py`**
  - Parse the command for IP/hostname arguments, resolve them, and reject execution if the resolved target falls outside `state["mission"]["scope"]`
  - This must be a code-level check, not a prompt instruction — the LLM should not be the only thing keeping the swarm inside scope
  - Applies to every category, but is most urgent for `exploitation`, `privesc`, `exfiltration` (categories that already include raw `bash`/`python3`)

- [ ] **Second human gate before lateral movement**
  - Discovering an internal network and getting a shell on an external host does not imply authorization to attack the internal network
  - Add a `lateral_approval` gate (same pattern as the existing exploitation gate) that fires whenever WarChief's decision is `pivot_lateral_recon` or any `lateral_*` value
  - Real engagements frequently scope external and internal separately — this reflects that

- [ ] **`shell=True` command-injection review**
  - `ToolExecutor.run()` passes the LLM-generated command string directly to `subprocess.run(shell=True)`. The scope check only inspects the first token, so `;`, `&&`, `|`, backticks, and `$()` all bypass category enforcement entirely
  - At minimum: reject commands containing shell metacharacters unless the tool category explicitly requires them (e.g. `bash` category); consider moving to `shell=False` with argument lists for categories that don't need a shell

- [ ] **Runtime fallback for malformed WarChief output**
  - v1: WarChief runs once: a bad JSON parse kills one planning step
  - v2: WarChief is invoked at 5-6 decision points and every stage depends on it succeeding — it's now a single point of failure for the whole engagement
  - Add a defined fallback when `decision` is missing, invalid, or the LLM call fails/times out: default to a safe conservative route (e.g. `report`) rather than crashing the run or looping on garbage input
  - This needs to be runtime code, not just a Phase 6 test — testing confirms the fallback exists, it doesn't create it

**Effort**: 3-4 days
**Testing**: Attempt scope bypass via shell metacharacters and out-of-scope IPs; verify both are blocked at the code level, not just flagged by the LLM
**Risk**: High if skipped — this is the actual liability surface once autonomy increases; low technical risk to implement
**Blocking**: Phase 3 (Lateral Movement) must not start until this lands

---

### Phase 0: Foundation (v1 → v1.1) — No Graph Changes
**Goal**: Make WarChief output meaningful without changing graph wiring yet.

- [ ] Expand WarChief prompt to produce real routing decisions
  - Current output: plan only
  - New output: `{"assessment": "...", "decision": "recon|scan|vulns_found_exploit|insufficient_data_abort|lateral_...|report", "reasoning": "...", "updated_plan": "..."}`
  
- [ ] Update `warchief/agent.py` to parse and store `last_decision` in state
  
- [ ] Add `_update_state()` to write decision reasoning to `plan.md` with timestamp
  
- [ ] Update all downstream agent prompts to include WarChief's latest decision
  - Agents should read: "WarChief's last decision was X. Here's what you found. Prepare data for WarChief's next assessment."

- [ ] Add decision logging to engagement folder
  - New file: `engagement/warchief_decisions.log` (timestamped routing decisions)

**Effort**: 2-3 days solo  
**Testing**: Unit test WarChief prompt parsing; manual runs to verify decision output is valid JSON  
**Risk**: Low — no graph changes, purely expanding WarChief's reasoning

---

### Phase 1: Graph Rewiring (v2 Foundation)
**Goal**: Replace linear edges with conditional routing based on WarChief decisions.

- [ ] Refactor `graph.py`
  - Remove: `workflow.add_edge("warchief", "aria")`
  - Add: WarChief as a **decision router** after each phase
  - Add conditional edges: `workflow.add_conditional_edges("warchief", route_func, {...})`
  
- [ ] Define routing functions for each decision point:
  ```python
  def route_after_recon(state) → str:  # "aria" | "lisa" | "bookkeeper"
  def route_after_scan(state) → str:   # "aria" | "lisa" | "bloodhound" | "bookkeeper"
  def route_after_vuln(state) → str:   # "aria" | "lisa" | "human_approval" | "bookkeeper"
  def route_after_exploit(state) → str: # "aria" | "lisa" | "surgeon" | "magician" | "bookkeeper"
  def route_after_privesc(state) → str: # "aria" | "lisa" | "surgeon" | "bookkeeper"
  ```
  
- [ ] Add loopback edges
  - ARIA → WarChief → {ARIA, Lisa, Bloodhound, Bookkeeper}
  - Lisa → WarChief → {ARIA, Lisa, Bloodhound, Bookkeeper}
  - Bloodhound → WarChief → {ARIA, Lisa, Human Gate, Bookkeeper}
  - Surgeon → WarChief → {ARIA, Lisa, Surgeon, Magician, Bookkeeper}
  - Thief → WarChief → {ARIA, Lisa, Surgeon, Bookkeeper}

- [ ] Update human gate logic
  - Still blocks exploitation if operator denies
  - But WarChief can decide to pivot/recon after gate denial (don't jump straight to Bookkeeper)

- [ ] Test graph topology
  - Verify no infinite loops (add max loop counter in state: `loop_count`, abort if > 5)
  - Verify all paths eventually reach Bookkeeper

**Effort**: 3-4 days  
**Testing**: 
  - Graph topology tests (verify edges are wired correctly)
  - Trace all possible paths from entry to END
  - Simulate decision sequences (recon → scan → vuln → report)
  - Test loop detection (5+ recon cycles should halt)
**Risk**: Medium — graph changes are core; one wrong edge breaks the entire flow

---

### Phase 2: WarChief Decision Logic (v2 Core)
**Goal**: Teach WarChief to make intelligent routing decisions based on findings.

- [ ] Expand WarChief system prompt with decision criteria
  ```
  "If ARIA found no new targets and we've already scanned common OSINT sources → route to scan"
  "If Lisa found only 2 open ports and both are low-value (SMTP, DNS) → route to recon for lateral movement"
  "If Bloodhound found 0 CVEs but lots of config misconfigs → stay in vuln_detection or route back to recon"
  "If Surgeon got shell but no privilege escalation viable → try lateral movement (back to ARIA for internal recon)"
  "If Thief confirmed data exfil → route to Bookkeeper, mission complete"
  ```

- [ ] Add "context window" to WarChief
  - Include last 3-5 findings/logs so WarChief sees trends, not just current data
  - Example: "ARIA has run 3 times. Second run found nothing new. If third run also empty, time to pivot."

- [ ] Implement decision confidence threshold
  - If WarChief confidence < 0.6, include uncertainty in prompt: "If unsure, default to [scan] and let Lisa find more data"
  
- [ ] Add "mission state machine" tracking
  - State: init → recon → scanning → vuln_detection → exploitation_prep → exploitation → post_exploit → lateral_recon → lateral_scanning → reporting → complete
  - WarChief adjusts routing based on state transitions
  - **Scope-qualified backtracking rule** (supersedes the blanket rule below — see note): backtracking from `exploitation` to `scanning` is blocked *within the original external scope* (no re-scanning the same targets after shell). It is explicitly *allowed* when the target context is `lateral` (i.e. Phase 3's `lateral_scan` decision, operating on newly-discovered internal targets under the `lateral_approval` gate from Phase -1). The state machine needs a `context: external | lateral` flag alongside the phase name so routing functions know which rule applies.
  - *Note: earlier drafts of this phase stated a flat "no backtrack to scanning after shell" rule with no lateral exception — that was inconsistent with Phase 3 and has been corrected here.*

- [ ] Implement scope exhaustion logic
  - Track unique targets discovered (in state dict: `discovered_targets`)
  - If ARIA runs twice and finds zero new targets → mark scope exhausted
  - If scope exhausted and no viable vulns → route to Bookkeeper with "scope depleted" reason

**Effort**: 4-5 days  
**Testing**:
  - Prompt injection tests: verify WarChief doesn't route to invalid next_bot
  - Decision trace analysis: run 10 realistic pentest scenarios, log all routing decisions
  - Scope exhaustion tests: verify swarm halts after N iterations of zero-finding recon
**Risk**: Medium-High — LLM reasoning quality depends heavily on prompt engineering; may need iterative refinement

---

### Phase 3: Lateral Movement & Pivoting (v2 Advanced)
**Requires**: Phase -1 complete (target/CIDR validation and `lateral_approval` gate). Do not start this phase on top of an unenforced scope boundary.

**Goal**: Enable WarChief to pivot from initial scope to internal/lateral discovery.

- [ ] Add "pivot" decision type to WarChief
  - `"decision": "pivot_lateral_recon"` — we found internal network, restart OSINT on it
  - This decision routes to the `lateral_approval` gate (Phase -1) before ARIA runs, not directly to ARIA — pivoting requires a second sign-off, same as the original exploitation gate
  - Update ARIA agent: add "internal network recon" substrat (DNS enum, SMB enumeration, credential dumping for pivoting)

- [ ] Track attack surface state
  - `state["external_targets"]` = set of external-facing hosts (initial scope)
  - `state["internal_targets"]` = set of internally-discovered hosts
  - `state["exploited_hosts"]` = set of hosts with confirmed access
  - `state["target_context"]` = `"external"` or `"lateral"` — read by the scope-qualified backtracking rule in Phase 2

- [ ] Implement pivot logic in WarChief
  - If Lisa found high-value internal service (SQL Server, DC, file share) → route to `lateral_approval` gate, then ARIA for lateral recon if approved
  - If Surgeon got shell on Windows → enable privesc with ARIA providing lateral movement intel

- [ ] Add lateral movement objectives to mission
  - During setup: `--lateral-objectives "dump SAM, escalate to SYSTEM, exfil NTDS.dit"`
  - WarChief uses these to decide if lateral exploitation is worth the effort
  - These objectives do NOT auto-authorize lateral movement — the `lateral_approval` gate still fires regardless of what was pre-declared at setup

**Effort**: 4-5 days (was 3-4; +1 day for the lateral approval gate wiring)
**Testing**:
  - Scenario: external-facing web app → internal database → pivot to file share
  - Verify WarChief routes through `lateral_approval` before ARIA re-runs on internal targets
  - Verify a denied lateral gate routes to Bookkeeper, not a retry loop
  - Verify scope enforcement (Phase -1) blocks any command targeting hosts outside both `external_targets` and approved `internal_targets`
**Risk**: Medium — introduces state complexity; must avoid getting stuck in lateral loop

---

### Phase 4: Failure Handling & Backtracking (v2 Resilience)
**Goal**: Make swarm graceful under adversity (blocked paths, WAF, honeypots, auth failures).

- [ ] Track failed attempts
  - `state["failed_vectors"]` = list of {target, tool, error}
  - WarChief considers failures when routing: "Surgeon tried SQLi on target X 3 times, all blocked. Try lateral movement or different host."

- [ ] Implement backtracking
  - If exploitation route is blocked → don't route to Surgeon again, route back to ARIA for alternative intel
  - If scanning route times out → route back with note "target slow/evasive, try slower scan"

- [ ] Add WAF/IPS detection
  - Lisa and Bloodhound detect signs of WAF (403 rates, rate limiting, honeypots)
  - WarChief adjusts: "WAF detected, avoid active scanning. Switch to passive recon + slow manual testing."

- [ ] **Rate/stealth calibration** (not just binary blocked/not-blocked)
  - `run_demo.sh`'s own example ROE says "No DoS" — a swarm that can now loop scanning across multiple cycles needs a throttle tied to target fragility, not just a WAF on/off signal
  - Add a `state["aggressiveness"]` level (e.g. `normal | cautious | passive_only`) that WarChief can downgrade based on target response, and have Lisa/Bloodhound honor it by adjusting tool flags (scan timing templates, request delays) rather than just switching tools on/off
  - This is a real ROE-compliance requirement, not just an evasion nicety

- [ ] Implement graceful abort
  - If 3+ decision cycles with no forward progress → WarChief: "Scope exhausted despite multiple attempts. Routing to report."
  - Log reason: "scope depleted" | "target hardened" | "no viable vectors" | "authorization issues"

**Effort**: 3-4 days  
**Testing**:
  - Scenario: target blocks all SQLi attempts → verify swarm pivots to credential harvesting or lateral movement
  - Scenario: WAF blocks active scanning → verify swarm falls back to passive recon
  - Scenario: 4 recon cycles with no new data → verify swarm aborts to Bookkeeper
**Risk**: Low-Medium — mostly state tracking; failure detection already exists in agents

---

### Phase 4.5: Cleanup & Rollback (v2 Professional Conduct)
**Goal**: A pentest that leaves implants, dropped tools, or reverse shells on the target after the engagement isn't a professional one — this was missing from the original plan entirely.

- [ ] Add a `cleanup` decision type WarChief routes to after Thief (or after Surgeon/Magician if exploitation was denied further progress)
  - New lightweight agent or extend Bookkeeper: remove dropped payloads, close persistent shells, revert any config changes made during exploitation/privesc
  - Log every cleanup action taken (or attempted-but-failed, e.g. lost connection to target) into the final report — a client needs to know if something wasn't fully rolled back

- [ ] Track "artifacts left on target" in state
  - `state["target_artifacts"]` = list of {host, artifact_type, path/description, cleaned: bool}
  - Surgeon/Magician/Thief append to this whenever they drop a file, create a scheduled task, add a user, etc.
  - Cleanup phase iterates this list and attempts removal; anything not cleaned gets flagged prominently in the report, not buried

**Effort**: 2-3 days
**Testing**: Verify a simulated engagement's dropped artifacts (test payload, test cron entry) are tracked and removal is attempted; verify failed cleanups are surfaced in the report, not silently dropped
**Risk**: Low — additive, doesn't touch existing routing logic

---

### Phase 5: Reporting & Decision Audit Trail (v2 Visibility)
**Goal**: Make every routing decision visible and explainable in the final report.

- [ ] Expand `plan.md` structure
  - Current: `## WarChief Assessment (timestamp)` — static plan written once
  - New: dynamic decision log showing all routing decisions with reasoning
  
  ```markdown
  ## Engagement Flow

  ### Initial Plan
  [original WarChief plan]

  ### Phase 1: Reconnaissance
  - ARIA Run 1: Found 3 subdomains, 2 mail servers
  - **WarChief Decision**: Route to Lisa (scanning)
  - Reasoning: Sufficient OSINT targets, proceed to active scan

  ### Phase 2: Scanning
  - Lisa Run 1: Found 5 open ports on web server
  - **WarChief Decision**: Route to Bloodhound (vuln detection)
  - Reasoning: Sufficient scanning data, proceed to vulnerability detection

  ### Phase 3: Vulnerability Detection
  - Bloodhound Run 1: Found CVE-2024-1234 (RCE), CVE-2024-5678 (XSS)
  - **WarChief Decision**: Route to Human Approval Gate
  - Reasoning: Exploitable vulnerabilities found, require human approval before exploitation

  [etc.]
  ```

- [ ] Add decision metrics to report
  - Total recon cycles, scanning cycles, exploitation cycles
  - Decision flow diagram (ASCII or text-based)
  - Why swarm ended (mission complete | scope exhausted | authorization issues)

- [ ] Create `engagement/warchief_decisions.json` 
  - Machine-readable log of all routing decisions with full context
  - Useful for auditing, replay, learning

**Effort**: 2-3 days  
**Testing**:
  - Run full engagement, verify plan.md has all decisions with correct reasoning
  - Verify JSON log is valid and complete
  - Spot-check decision reasoning is accurate
**Risk**: Low — mostly formatting/output, no logic changes

---

### Phase 6: Testing & Validation (v2 QA)
**Goal**: Comprehensive testing across realistic scenarios.

- [ ] Unit tests
  - WarChief decision parsing: all valid decision types produce correct output
  - Graph routing: each conditional edge routes correctly based on state
  - Loop detection: max cycle counter prevents infinite loops

- [ ] Integration tests
  - Full happy-path: setup → recon → scanning → vuln → approval → exploit → privesc → exfil → report
  - Pivot scenario: initial scope empty → pivot to lateral movement → full chain
  - Abort scenario: 4 recon cycles, no data → graceful abort
  - Failure scenario: SQLi blocked by WAF → reroute to credential harvesting

- [ ] Prompt quality tests
  - WarChief should never output invalid decision type
  - WarChief reasoning should be coherent (no contradictions)
  - Other agents should understand WarChief's latest decision without confusion

- [ ] Performance/reliability tests
  - Run 5 full engagements end-to-end with different targets
  - Measure: completion time, decision correctness, report quality
  - Log any hangs, crashes, or nonsensical decisions

- [ ] Penetration testing on test environment
  - Use intentionally vulnerable targets (DVWA, WebGoat, HackTheBox)
  - Verify swarm successfully chains recon → scan → vuln → exploit
  - Verify lateral movement scenarios work as intended

**Effort**: 5-7 days  
**Testing**: Requires test infrastructure (vulnerable VMs or cloud labs)
**Risk**: Medium — integration testing always finds edge cases

---

## Effort Estimate & Timeline

| Phase | Effort | Timeline | Blocking | Risk |
|-------|--------|----------|----------|------|
| **Phase -1 (Prerequisites & Risk Closure)** | **3-4 days** | **Week 1** | **None** | **High if skipped, low to build** |
| Phase 0 (Foundation) | 2-3 days | Week 1 | None | Low |
| Phase 1 (Graph Rewiring) | 3-4 days | Week 1-2 | Phase 0 | Medium |
| Phase 2 (Decision Logic) | 4-5 days | Week 2-3 | Phase 1 | Medium-High |
| Phase 3 (Lateral Movement) | 4-5 days | Week 3-4 | Phase 2, **Phase -1** | Medium |
| Phase 4 (Failure Handling) | 3-4 days | Week 3-4 | Phase 2 | Low-Medium |
| Phase 4.5 (Cleanup & Rollback) | 2-3 days | Week 4 | Phase 4 | Low |
| Phase 5 (Reporting & Audit) | 2-3 days | Week 4-5 | Phase 4.5 | Low |
| Phase 6 (Testing & Validation) | 5-7 days | Week 5-6 | Phases -1, 1-5 | Medium |
| **Total** | **28-38 days** | **~6-7 weeks** | — | — |

**Critical Path**: Phase -1 → Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 6  
**Parallelizable**: Phases 4, 4.5, 5 can run in parallel with Phase 3 once Phase 2 is complete  
**Realistic**: 6-7 weeks solo; 4-5 weeks with another dev
**Note**: Phase -1 was not in the original draft. It's the difference between "adaptive tool" and "adaptive tool with an actual scope guarantee" — do not compress or skip it to hit an earlier timeline.

---

## Success Criteria (Definition of Done for v2)

- ✅ **Target/CIDR validation enforced in code — not just prompt instruction — before any lateral movement code ships**
- ✅ **Second human approval gate fires before any lateral/internal pivot, independent of pre-declared `--lateral-objectives`**
- ✅ **Shell-metacharacter injection bypass in `tool_executor.py` closed or explicitly scoped to categories that require it**
- ✅ **WarChief has a defined fallback for malformed/failed decisions — engagement degrades safely, doesn't crash**
- ✅ WarChief re-enters the graph after each phase (not a one-shot planner)
- ✅ WarChief makes routing decisions that adapt to findings (not hardcoded)
- ✅ Swarm can loop back (ARIA → Lisa → ARIA for deeper recon, etc.)
- ✅ Swarm can pivot to lateral movement if initial scope exhausted, gated by human approval
- ✅ Swarm handles failures gracefully (blocked vectors, WAF, dead-end paths)
- ✅ Swarm calibrates scan aggressiveness against target fragility, not just binary WAF detection
- ✅ **Artifacts left on target are tracked and cleanup is attempted before final report**
- ✅ All routing decisions are logged and auditable in final report
- ✅ Integration tests pass: 5+ realistic pentest scenarios (recon → exploit → report)
- ✅ No infinite loops (max 5 decision cycles per phase enforced)
- ✅ README updated with v2 architecture and real examples of adaptive routing

---

## Known Limitations & Future Work (v3+)

- [ ] **Dependency chains**: Currently each bot waits for the previous one. v3 could parallelize independent scans.
- [ ] **Tool learning**: WarChief doesn't learn tool effectiveness over time. v3 could track "SQLi works on this target type" and reuse.
- [ ] **Dynamic team sizing**: Currently 9 fixed bots. v3 could spawn specialized bots for specific vectors (e.g., "Kerberoaster" for AD enumeration).
- [ ] **Conflict resolution**: If two agents disagree on next move, current design escalates to WarChief. v3 could implement debate/consensus.
- [ ] **Real-time operator input**: Currently human gate is binary (y/n). v3 could allow operator to inject guidance mid-engagement ("focus on this subnet").
- [ ] **Multi-target engagement**: Currently scoped to one target/CIDR. v3 could parallelize multiple independent targets with WarChief coordinating priorities.

### Flagged during roadmap review — should not wait for v3

- [ ] **Context/token growth is unbounded.** `plan.md`, `findings.md`, `log.md` are appended to on every loop cycle and re-read in full by every subsequent LLM call. With up to 5-6 decision points × up to 5 loop cycles each, a single engagement's context fed to the LLM grows substantially over its lifetime. This has direct cost implications for a service billed per-engagement — needs a summarization or truncation strategy (e.g. WarChief gets a rolling digest of the last N entries, not the full file) before v2 ships, not after.
- [ ] **Config/state migration.** Adding `last_decision`, `loop_count`, `discovered_targets`, `target_context`, `target_artifacts` to state changes the schema. No plan yet for whether existing `swarm-config.json` files or in-progress v1 engagements need a migration step or are simply incompatible with v2.
- [ ] **Docs debt.** `CLAUDE.md` and the `wiki/` pages (Architecture, Bot Reference, Tool Scoping, Security & Legal) describe the v1 linear architecture. These need a full rewrite alongside Phase 5, not as a trailing cleanup task — the "Security & Legal" wiki page in particular needs updating to describe the Phase -1 scope enforcement and lateral approval gate once they exist.

---

## Quick-Start for Contribution

If you want to jump in:

1. **Start with Phase -1**: Close the scope/target validation gap and wire the lateral approval gate — this is a prerequisite, not optional groundwork
2. **Then Phase 0**: Expand WarChief prompt, test decision output
3. **Then Phase 1**: Rewrite `graph.py`, add conditional edges, test routing
4. **Then Phase 2**: Refine WarChief reasoning, add context windows
5. **Test constantly**: Don't wait for Phase 6 to validate; test after each phase

**Entry points for code review**:
- `core/scope.py`, `core/tool_executor.py` — Phase -1: target validation, shell-metacharacter handling
- `warchief/agent.py` — decision prompt and parsing
- `graph.py` — conditional edge routing, `lateral_approval` gate
- `core/base_bot.py` — state management for decisions, fallback on malformed output
- `core/state.py` — ensure state dict supports new fields (`last_decision`, `loop_count`, `discovered_targets`, `target_context`, `target_artifacts`)

---

## Questions & Decisions Outstanding

1. **Loop bounds**: Should max cycles be 5? Per-phase? Global?
2. **Lateral movement bot strategy**: Should Surgeon be reusable post-pivoting, or spawn a specialized "Infiltrator" bot for internal exploitation?
3. **Operator feedback**: Should WarChief ask for guidance at decision points ("I see 3 paths, which should I pursue?") or make unilateral decisions (subject to the Phase -1 gates)?
4. **Report structure**: Should failed/blocked vectors be highlighted separately, or integrated into the narrative?
5. **Aggressiveness default**: Should `state["aggressiveness"]` default to `cautious` for all new engagements, or `normal` with downgrade-on-detection only?

*(Resolved during this review, no longer open: "when does scope pivot trigger" → gated by explicit human approval, not WarChief heuristic alone; "should lateral movement need separate authorization" → yes, `lateral_approval` gate.)*

---

**Version**: Chimeras v2 Roadmap (rev. 2 — Phase -1 prerequisites added)  
**Last Updated**: 2026-07-17  
**Status**: In Design  
**Next Step**: Phase -1 implementation (target/CIDR validation, lateral approval gate) — do not begin Phase 0 work as a substitute for this
