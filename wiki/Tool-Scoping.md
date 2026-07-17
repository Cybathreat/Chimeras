# Tool Scoping

## The Problem

In a multi-agent security tool, you need strict per-bot tool restrictions. A recon bot should not be running exploits. An exfiltration bot should not be scanning ports. But hardcoding tool lists in each bot agent is brittle — every new tool requires editing bot code.

## The Solution: Category-Based Scoping

Chimeras separates tool *categories* from tool *names*. Bots declare a category. The scope enforcer maps categories to tool sets and dynamically discovers which tools are actually installed.

### How It Works

1. **Bot declares a category** in `core/scope.py`:
```python
BOT_CATEGORIES = {
    "aria": "passive_recon",
    "lisa": "active_scan",
    "bloodhound": "vuln_detection",
    ...
}
```

2. **Categories map to tool sets** in the same file:
```python
TOOL_CATEGORIES = {
    "passive_recon": {"dig", "host", "whois", "curl", "whatweb", ...},
    "active_scan": {"nmap", "nikto", "gobuster", "ffuf", ...},
    ...
}
```

3. **Dynamic discovery** — `ScopeEnforcer._discover_installed_tools()` uses `shutil.which()` to find which tools are actually installed on the system. The LLM is only told about available tools.

4. **Scope check** — before any command executes, `ScopeEnforcer.check()` parses the command, extracts the tool name, and verifies it's in the bot's category. If not, the command is blocked before execution.

### Adding a New Tool

Just add it to the appropriate category in `TOOL_CATEGORIES`. Every bot in that category automatically gets access. No bot agent code changes needed.

### Shell Control Flow

Shell keywords (`for`, `while`, `if`, `case`) are not tools but bash constructs. The scope checker handles these: if `bash` is in the bot's allowed tools, shell control flow is permitted. Otherwise, the checker looks for an allowed tool name within the command.

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