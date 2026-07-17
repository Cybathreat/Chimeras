"""
Chimeras v1.0 — Scope Enforcement

Per-bot tool categories (NOT hardcoded tool lists).
The LLM decides which tools to run. Scope enforcer checks the tool
falls within the bot's authorized category.

Tools are discovered dynamically — no hardcoded tool names in bot agents.
"""

from typing import List, Dict, Set, Optional
import shlex
import re
import shutil
import os


# ─── Tool Categories ───
# Each category maps to a set of tool names that fall within that role.
# Bots reference categories, not individual tools.

TOOL_CATEGORIES: Dict[str, Set[str]] = {
    "passive_recon": {
        "dig", "host", "whois", "curl", "theHarvester", "subfinder",
        "amass", "crtsh", "dnsrecon", "fierce", "waybackurls",
        "ghdb", "shodan", "censys", "wafw00f", "whatweb",
        "dnsx", "httpx",
    },
    "active_scan": {
        "nmap", "masscan", "rustscan", "naabu", "nikto",
        "whatweb", "wpscan", "dirb", "gobuster", "ffuf",
        "httpx", "dnsx",
    },
    "vuln_detection": {
        "nmap", "nuclei", "searchsploit", "nikto",
        "vulners", "wapiti", "wafw00f", "ssh-audit",
        "sslscan", "testssl", "nmap-script",
    },
    "payload_fab": {
        "msfvenom", "msfconsole", "searchsploit", "curl",
    },
    "exploitation": {
        "msfconsole", "msfvenom", "sqlmap", "curl",
        "nc", "ncat", "python3", "bash", "exploit",
    },
    "privesc": {
        "linpeas", "winpeas", "pspy", "find", "cat", "ls",
        "python3", "bash", "ssh", "smbclient", "crackmapexec",
        "impacket-secretsdump", "mimikatz",
    },
    "exfiltration": {
        "curl", "wget", "nc", "python3", "bash", "tar", "gzip",
        "scp", "rsync",
    },
    "none": set(),
}


# ─── Bot → Category mapping ───
# Bots declare their category, not their tools.

BOT_CATEGORIES: Dict[str, str] = {
    "aria": "passive_recon",
    "lisa": "active_scan",
    "bloodhound": "vuln_detection",
    "pathologist": "payload_fab",
    "surgeon": "exploitation",
    "magician": "privesc",
    "thief": "exfiltration",
    "bookkeeper": "none",
    "warchief": "none",
}


# ─── Scope violation error ───

class ScopeViolation(Exception):
    """Raised when a bot attempts to use a tool outside its scope."""
    def __init__(self, bot_name: str, tool: str):
        self.bot_name = bot_name
        self.tool = tool
        super().__init__(
            f"SCOPE VIOLATION: {bot_name} attempted to use '{tool}' — "
            f"not in its scope. Category: {BOT_CATEGORIES.get(bot_name, 'none')}"
        )


class ScopeEnforcer:
    """Enforces per-bot tool categories. Not hardcoded tool lists."""

    # Shell control flow keywords — not tools, but bash constructs
    SHELL_KEYWORDS = {
        "for", "while", "if", "case", "until", "select",
        "{", "(", "[[",
    }

    @staticmethod
    def get_bot_category(bot_name: str) -> str:
        """Return the tool category for a bot."""
        return BOT_CATEGORIES.get(bot_name, "none")

    @staticmethod
    def get_allowed_tools(bot_name: str) -> Set[str]:
        """Return the set of allowed tools for a bot based on its category."""
        category = BOT_CATEGORIES.get(bot_name, "none")
        return TOOL_CATEGORIES.get(category, set())

    @staticmethod
    def _discover_installed_tools() -> Set[str]:
        """Dynamically discover which tools are actually installed on the system."""
        installed = set()
        for category_tools in TOOL_CATEGORIES.values():
            for tool in category_tools:
                if shutil.which(tool) or os.path.isfile(f"/usr/local/bin/{tool}") or os.path.isfile(f"/usr/bin/{tool}"):
                    installed.add(tool)
        return installed

    @staticmethod
    def describe_scope(bot_name: str) -> str:
        """Return human-readable scope description for a bot."""
        category = BOT_CATEGORIES.get(bot_name, "none")
        if category == "none":
            return f"{bot_name}: No tool execution (reads/writes files only)"
        tools = TOOL_CATEGORIES.get(category, set())
        installed = ScopeEnforcer._discover_installed_tools()
        available = tools & installed
        missing = tools - installed
        desc = f"{bot_name} [{category}]: {', '.join(sorted(available))}"
        if missing:
            desc += f" (not installed: {', '.join(sorted(missing))})"
        return desc

    @staticmethod
    def check(bot_name: str, command: str) -> tuple[bool, str]:
        """
        Check if a command is within the bot's scope.

        Returns:
            (allowed: bool, reason: str)
        """
        allowed_tools = ScopeEnforcer.get_allowed_tools(bot_name)

        # Bookkeeper and WarChief don't run tools at all
        if not allowed_tools:
            return False, f"{bot_name} has no tool execution permissions"

        # Parse the command to find the base tool
        try:
            parts = shlex.split(command)
            if not parts:
                return False, "Empty command"
            tool = parts[0]
            # Handle paths like /usr/bin/nmap → nmap
            if "/" in tool:
                tool = tool.split("/")[-1]
        except Exception:
            tool = command.strip().split()[0] if command.strip() else ""
            if "/" in tool:
                tool = tool.split("/")[-1]

        # If first word is a shell keyword (for/while/if), check if bash is allowed
        if tool in ScopeEnforcer.SHELL_KEYWORDS:
            if "bash" in allowed_tools:
                return True, "OK (bash control flow)"
            for allowed_tool in allowed_tools:
                if re.search(rf'\b{re.escape(allowed_tool)}\b', command):
                    return True, f"OK (shell wrapper around {allowed_tool})"
            return False, f"SCOPE VIOLATION: {bot_name} cannot use shell control flow '{tool}'. Allowed: {sorted(allowed_tools)}"

        if tool in allowed_tools:
            return True, "OK"

        return False, f"SCOPE VIOLATION: {bot_name} cannot use '{tool}'. Allowed: {sorted(allowed_tools)}"

    @staticmethod
    def enforce(bot_name: str, command: str) -> str:
        """
        Enforce scope. Raises ScopeViolation if violated.
        Returns the command if allowed.
        """
        allowed, reason = ScopeEnforcer.check(bot_name, command)
        if not allowed:
            raise ScopeViolation(bot_name, command.split()[0] if command.split() else "unknown")
        return command