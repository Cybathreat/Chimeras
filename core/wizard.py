"""
Chimeras v2.0 — TUI Setup Wizard

Interactive terminal UI for pre-flight configuration and LLM verification.

Flow:
  1. Welcome banner
  2. Config file check — if missing, interactive mission setup
  3. LLM connectivity check — test every bot's LLM connection live
  4. If any bot fails — offer reconfigure or retry
  5. Summary — show full config, ready to launch
  6. Does NOT proceed until all checks pass or user exits

Uses Rich for terminal rendering. No external TUI framework needed.
"""

import json
import os
import textwrap
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.live import Live
from rich import box

from core.config import ConfigManager, DEFAULT_SWARM_CONFIG, interactive_setup
from core.llm_router import LLMRouter


console = Console()

# ─── Bot metadata for display ───

BOT_INFO = {
    "warchief":   {"role": "Orchestrator",      "icon": "👑"},
    "aria":       {"role": "Passive Recon",     "icon": "🔍"},
    "lisa":       {"role": "Active Scanner",    "icon": "📡"},
    "bloodhound": {"role": "Vuln Detection",   "icon": "🩺"},
    "wasp":        {"role": "Web Vuln Det",    "icon": "🐝"},
    "marksman":   {"role": "Exploit Ops",      "icon": "🎯"},
    "magician":   {"role": "Privilege Esc",     "icon": "🎩"},
    "thief":      {"role": "Exfiltration",      "icon": "📦"},
    "bookkeeper": {"role": "Report Writer",    "icon": "📝"},
}

BOT_ORDER = ["warchief", "aria", "lisa", "bloodhound", "wasp", "marksman",
             "magician", "thief", "bookkeeper"]


def print_banner():
    """Print the Chimeras welcome banner."""
    banner = r"""
 ██████╗██╗  ██╗██╗███╗   ███╗███████╗██████╗  █████╗ ███████╗
██╔════╝██║  ██║██║████╗ ████║██╔════╝██╔══██╗██╔══██╗██╔════╝
██║     ███████║██║██╔████╔██║█████╗  ██████╔╝███████║███████╗
██║     ██╔══██║██║██║╚██╔╝██║██╔══╝  ██╔══██╗██╔══██║╚════██║
╚██████╗██║  ██║██║██║ ╚═╝ ██║███████╗██║  ██║██║  ██║███████║
 ╚═════╝╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝
"""
    console.print(banner, style="bold red")
    console.print("  [bold]Autonomous AI Pentest Swarm[/bold] — v3.2", style="dim")
    console.print("  [dim]Docker-Sandboxed | 3-Tier Scope Enforcement | 9-Bot Adaptive Architecture[/dim]")
    console.print()


def print_separator(title: str = ""):
    """Print a section separator."""
    console.print()
    if title:
        console.print(f"  [bold cyan]━━ {title} ━━[/bold cyan]")
    console.print()


def step_header(num: int, title: str, subtitle: str = ""):
    """Print a numbered step header."""
    console.print()
    console.print(
        Panel(
            f"[bold white on blue] STEP {num} [/bold white on blue]  [bold]{title}[/bold]",
            subtitle=f"[dim]{subtitle}[/dim]" if subtitle else "",
            border_style="blue",
            padding=(0, 1),
        )
    )


def check_config_file(mission_dir: Path) -> Optional[Dict[str, Any]]:
    """Check if swarm-config.json exists and is valid.

    v2: Uses ConfigManager.load_config() which auto-migrates v1 configs.

    Returns:
        - Config dict if found and valid
        - None if not found or invalid
    """
    config_path = mission_dir / "swarm-config.json"

    if not config_path.exists():
        console.print("  [yellow]⚠  No swarm-config.json found[/yellow]")
        return None

    try:
        with open(config_path) as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        console.print(f"  [red]✗  Config file is corrupted: {e}[/red]")
        return None

    # Validate required fields
    if "bots" not in config:
        console.print("  [red]✗  Config missing 'bots' section[/red]")
        return None

    # v2: Auto-migrate if needed
    config_version = config.get("version", "1.0")
    if config_version != "2.0":
        console.print(f"  [yellow]→  Migrating config from v{config_version} to v2.0...[/yellow]")
        manager = ConfigManager(mission_dir)
        config = manager._migrate_config(config)
        console.print("  [green]✓  Config migrated to v2.0[/green]")

    missing_bots = [b for b in BOT_ORDER if b not in config["bots"]]
    if missing_bots:
        console.print(f"  [yellow]⚠  Config missing bots: {', '.join(missing_bots)}[/yellow]")
        for bot in missing_bots:
            config["bots"][bot] = DEFAULT_SWARM_CONFIG["bots"][bot].copy()
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        console.print("  [green]✓  Missing bots filled with defaults[/green]")

    return config


def run_mission_setup(mission_dir: Path) -> tuple[Dict[str, Any], Path]:
    """Run interactive mission setup using the existing interactive_setup().

    Returns (config, config_path) — the path of the config actually created,
    which may be in a non-default mission directory.
    """
    console.print()
    console.print("  [bold]No mission configured. Let's set one up.[/bold]")
    console.print()

    params = interactive_setup()

    manager = ConfigManager(Path(params["dir"]))
    manager.setup_mission(
        mission_name=params["mission_name"],
        objectives=params["objectives"],
        scope=params["scope"],
        roe=params["roe"],
    )

    config_path = Path(params["dir"]) / "swarm-config.json"
    with open(config_path) as f:
        config = json.load(f)

    console.print()
    console.print(f"  [green]✓  Mission created at {config_path}[/green]")

    if Confirm.ask("  Configure LLM backends for the 9 agents now?", default=True):
        config = configure_llm_backends(config, config_path)

    return config, config_path


def find_existing_missions(search_dir: Path) -> List[Path]:
    """Find mission directories (any dir containing swarm-config.json),
    one level deep. Lets the wizard reuse missions instead of re-creating."""
    try:
        return sorted(
            p.parent for p in search_dir.glob("*/swarm-config.json")
        )
    except OSError:
        return []


# ─── LLM backend configuration (shared or per-bot) ─────────────────────

PROVIDERS = ["openai", "anthropic", "google", "groq", "openrouter", "ollama", "custom"]

# Provider → environment variables checked for its API key
KEY_ENV_VARS = {
    "openai": ["OPENAI_API_KEY", "OLLAMA_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "google": ["GOOGLE_API_KEY"],
    "groq": ["GROQ_API_KEY"],
    "openrouter": ["OPENROUTER_API_KEY"],
    "ollama": [],  # local Ollama needs no key
}


def prompt_llm_settings(current: Optional[Dict[str, Any]] = None,
                        bot_label: str = "") -> Dict[str, Any]:
    """Interactively collect provider/model/base_url/api_key.

    Returns a settings dict consumable by apply_llm_settings()."""
    current = current or {}
    header = f" for [bold]{bot_label}[/bold]" if bot_label else ""
    console.print()
    console.print(f"  [bold]LLM backend{header}[/bold]")
    console.print("  [bold]Providers:[/bold]")
    for i, p in enumerate(PROVIDERS, 1):
        marker = " ←" if p == current.get("provider") else ""
        label = {
            "custom": "custom (OpenAI-compatible gateway)",
            "ollama": "ollama (local or cloud)",
        }.get(p, p)
        console.print(f"    {i}. {label}{marker}")

    try:
        default_idx = PROVIDERS.index(current.get("provider", "ollama")) + 1
    except ValueError:
        default_idx = PROVIDERS.index("ollama") + 1
    choice = Prompt.ask("  Provider number", default=str(default_idx))
    try:
        provider = PROVIDERS[int(choice) - 1]
    except (ValueError, IndexError):
        provider = current.get("provider", "ollama")

    # Custom gateway = openai provider with a mandatory base_url.
    # Any OpenAI-compatible endpoint works: Ollama Cloud, vLLM, LM Studio,
    # Azure OpenAI, corporate gateways, etc.
    base_url = ""
    if provider == "custom":
        provider = "openai"
        while not base_url:
            base_url = Prompt.ask(
                "  Gateway base URL (e.g. https://gateway.local/v1)"
            ).strip()
    elif provider == "ollama":
        flavor = Prompt.ask(
            "  Ollama local or cloud?",
            choices=["local", "cloud"],
            default="local",
        )
        if flavor == "cloud":
            # Ollama Cloud speaks the OpenAI API → openai provider + base_url.
            # Key comes from OLLAMA_API_KEY (checked by the openai branch below).
            provider = "openai"
            base_url = Prompt.ask(
                "  Ollama Cloud base URL", default="https://ollama.com/v1"
            ).strip()
        else:
            base_url = Prompt.ask(
                "  Ollama host (empty = http://localhost:11434)",
                default=current.get("base_url", ""),
            ).strip()
    elif provider in ("openai", "anthropic"):
        base_url = Prompt.ask(
            "  Base URL (empty = official API)",
            default=current.get("base_url", ""),
        ).strip()

    model = Prompt.ask("  Model", default=current.get("model", "")).strip()

    settings: Dict[str, Any] = {"provider": provider, "model": model}
    if base_url:
        settings["base_url"] = base_url

    # API key: env first, session-only set, or opt-in plaintext persist
    env_vars = KEY_ENV_VARS.get(provider, [])
    if env_vars:
        existing = next((v for v in env_vars if os.environ.get(v)), None)
        if existing:
            console.print(f"  [green]✓  API key found in environment ({existing})[/green]")
        else:
            console.print(f"  [yellow]⚠  No API key found ({' / '.join(env_vars)})[/yellow]")
            key = Prompt.ask("  Enter API key (empty = skip)", password=True).strip()
            if key:
                persist = Confirm.ask(
                    "  Save key into swarm-config.json? (plaintext on disk)",
                    default=False,
                )
                if persist:
                    settings["api_key"] = key
                else:
                    os.environ[env_vars[0]] = key
                    console.print("  [dim]Set for this session only — export it to persist.[/dim]")

    return settings


def apply_llm_settings(config: Dict[str, Any], bot_names: List[str],
                       settings: Dict[str, Any]) -> Dict[str, Any]:
    """Apply an LLM settings dict to one or more bots. Pure function."""
    entry = {"provider": settings["provider"], "model": settings["model"]}
    for optional in ("base_url", "api_key"):
        if settings.get(optional):
            entry[optional] = settings[optional]
    config.setdefault("bots", {})
    for name in bot_names:
        config["bots"][name] = dict(entry)  # independent copies
    return config


def configure_llm_backends(config: Dict[str, Any], config_path: Path) -> Dict[str, Any]:
    """Shared-or-per-bot LLM configuration flow."""
    console.print()
    shared = Confirm.ask(
        "  [bold]Do all 9 agents share the same LLM configuration?[/bold]",
        default=True,
    )
    if shared:
        current = config.get("bots", {}).get("warchief") \
            or DEFAULT_SWARM_CONFIG["bots"]["warchief"]
        settings = prompt_llm_settings(current=current)
        apply_llm_settings(config, BOT_ORDER, settings)
        console.print("  [green]✓  Applied to all 9 agents[/green]")
    else:
        for bot in BOT_ORDER:
            info = BOT_INFO.get(bot, {"role": "?", "icon": "?"})
            settings = prompt_llm_settings(
                current=config.get("bots", {}).get(bot, {}),
                bot_label=f"{info['icon']} {bot} — {info['role']}",
            )
            apply_llm_settings(config, [bot], settings)

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    console.print(f"  [green]✓  LLM configuration saved to {config_path.name}[/green]")
    return config


def test_llm_connection(bot_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Test a single bot's LLM connection.

    Sends a minimal prompt and checks for a response.
    Returns dict with: bot_name, status, latency_ms, response_preview, error
    """
    bot_config = config.get("bots", {}).get(bot_name, {})
    provider = bot_config.get("provider", "ollama")
    model = bot_config.get("model", "unknown")
    base_url = bot_config.get("base_url")

    result = {
        "bot_name": bot_name,
        "provider": provider,
        "model": model,
        "base_url": base_url or "",
        "status": "testing",
        "latency_ms": 0,
        "response_preview": "",
        "error": "",
    }

    try:
        router = LLMRouter.from_config(bot_name, config)
        start = time.time()
        response = router.generate(
            "Reply with exactly: OK",
            system="You are a connectivity test. Reply with only 'OK' and nothing else.",
            max_tokens=50,
        )
        elapsed = int((time.time() - start) * 1000)

        result["status"] = "connected" if response and len(response.strip()) > 0 else "empty"
        result["latency_ms"] = elapsed
        result["response_preview"] = (response or "").strip()[:50]

    except ImportError as e:
        result["status"] = "missing_package"
        result["error"] = str(e)
    except Exception as e:
        result["status"] = "failed"
        error_msg = str(e)
        # Truncate long errors (keep enough for the actionable part)
        if len(error_msg) > 300:
            error_msg = error_msg[:300] + "..."
        result["error"] = error_msg

    return result


def render_connectivity_table(results: List[Dict[str, Any]]) -> Table:
    """Build the connectivity results table."""
    table = Table(
        title="LLM Connectivity Check",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Bot", style="bold", width=14)
    table.add_column("Role", width=16)
    table.add_column("Provider", width=12)
    table.add_column("Model", width=18)
    table.add_column("Status", width=14)
    table.add_column("Latency", justify="right", width=10)
    table.add_column("Detail", width=30)

    for r in results:
        bot = r["bot_name"]
        info = BOT_INFO.get(bot, {"role": "?", "icon": "?"})

        # Status with color
        status = r["status"]
        if status == "connected":
            status_str = f"[green]✓ {status}[/green]"
        elif status == "testing":
            status_str = f"[yellow]⟳ {status}[/yellow]"
        elif status == "empty":
            status_str = "[yellow]⚠ empty[/yellow]"
        else:
            status_str = f"[red]✗ {status}[/red]"

        latency = f"{r['latency_ms']}ms" if r["latency_ms"] > 0 else "-"
        detail = r.get("response_preview") or r.get("error", "")
        if len(detail) > 28:
            detail = detail[:28] + "..."

        table.add_row(
            f"{info['icon']} {bot}",
            info["role"],
            r["provider"],
            r["model"],
            status_str,
            latency,
            detail,
        )

    return table


def run_connectivity_check(config: Dict[str, Any]) -> tuple[List[Dict[str, Any]], bool]:
    """Run LLM connectivity check for all bots.

    Returns:
        (results, all_connected)
    """
    results = []
    all_connected = True

    # Initialize results with "pending" status
    for bot in BOT_ORDER:
        results.append({
            "bot_name": bot,
            "provider": config.get("bots", {}).get(bot, {}).get("provider", "?"),
            "model": config.get("bots", {}).get(bot, {}).get("model", "?"),
            "base_url": config.get("bots", {}).get(bot, {}).get("base_url", ""),
            "status": "pending",
            "latency_ms": 0,
            "response_preview": "",
            "error": "",
        })

    # Test each bot sequentially, updating the table live
    with Live(render_connectivity_table(results), console=console, refresh_per_second=4) as live:
        for i, bot in enumerate(BOT_ORDER):
            # Mark as testing
            results[i]["status"] = "testing"
            live.update(render_connectivity_table(results))

            # Run the actual test
            result = test_llm_connection(bot, config)
            results[i] = result
            live.update(render_connectivity_table(results))

            if result["status"] != "connected":
                all_connected = False

    return results, all_connected


def reconfigure_bot(bot_name: str, config: Dict[str, Any],
                    config_path: Path) -> Dict[str, Any]:
    """Interactive bot reconfiguration — same prompts as initial setup."""
    bot_config = config["bots"].get(bot_name, {})
    info = BOT_INFO.get(bot_name, {"role": "?", "icon": "?"})

    console.print()
    console.print(f"  [bold]Reconfiguring {info['icon']} {bot_name}[/bold] [dim]({info['role']})[/dim]")
    console.print(f"  [dim]Current: {bot_config.get('provider', '?')}/{bot_config.get('model', '?')}[/dim]")

    settings = prompt_llm_settings(current=bot_config)
    apply_llm_settings(config, [bot_name], settings)

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    console.print(f"  [green]✓  {bot_name} reconfigured and saved[/green]")

    return config


def show_config_summary(config: Dict[str, Any]):
    """Display the full configuration summary."""
    table = Table(
        title="Swarm Configuration",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Bot", style="bold", width=14)
    table.add_column("Role", width=16)
    table.add_column("Provider", width=12)
    table.add_column("Model", width=22)
    table.add_column("Gateway", width=30)

    for bot in BOT_ORDER:
        info = BOT_INFO.get(bot, {"role": "?", "icon": "?"})
        bc = config.get("bots", {}).get(bot, {})
        gateway = bc.get("base_url", "—") or "—"
        table.add_row(
            f"{info['icon']} {bot}",
            info["role"],
            bc.get("provider", "?"),
            bc.get("model", "?"),
            gateway,
        )

    console.print()
    console.print(table)

    # Mission info
    mission_name = config.get("mission_name", "N/A")
    created = config.get("created", "N/A")
    console.print()
    console.print(f"  [bold]Mission:[/bold] {mission_name}")
    console.print(f"  [bold]Created:[/bold] {created}")
    console.print(f"  [bold]Bots:[/bold] {len(config.get('bots', {}))} configured")


# ─── v3.3: Auth configuration ───────────────────────────────────────────

AUTH_METHODS = [
    ("web_form",                          "Web — Form login (POST username/password)"),
    ("web_basic",                         "Web — HTTP Basic Auth"),
    ("web_bearer",                        "Web — Bearer token (pre-existing)"),
    ("web_jwt",                           "Web — JWT token (pre-existing)"),
    ("web_cookie",                        "Web — Cookies (pre-existing)"),
    ("web_api_key",                       "Web — API key in header"),
    ("web_oauth2_password",               "Web — OAuth2 password grant"),
    ("web_oauth2_client_credentials",     "Web — OAuth2 client_credentials grant"),
    ("web_ntlm",                          "Web — NTLM auth"),
    ("ad_ldap_bind",                      "Active Directory — LDAP bind"),
    ("ad_kerberos",                       "Active Directory — Kerberos (kinit)"),
    ("ad_ntlm",                           "Active Directory — NTLM"),
    ("keycloak_oauth2_password",          "Keycloak — OAuth2 password grant"),
    ("keycloak_oauth2_client_credentials","Keycloak — OAuth2 client_credentials grant"),
    ("keycloak_oidc",                     "Keycloak — OIDC"),
    ("ldap_simple",                       "LDAP — Simple bind"),
    ("ldap_sasl",                         "LDAP — SASL (DIGEST-MD5/GSSAPI)"),
    ("ldap_anonymous",                    "LDAP — Anonymous bind"),
    ("db_mysql",                          "Database — MySQL"),
    ("db_postgresql",                     "Database — PostgreSQL"),
    ("db_mssql",                          "Database — MSSQL"),
    ("ssh_password",                      "SSH — Password"),
    ("ssh_key",                           "SSH — Key-based"),
]

# Fields needed per method (for prompting)
AUTH_REQUIRED_FIELDS: Dict[str, List[str]] = {
    "web_form":                           ["url", "username", "password"],
    "web_basic":                          ["url", "username", "password"],
    "web_bearer":                         ["url", "token"],
    "web_jwt":                            ["token"],
    "web_cookie":                         ["cookies"],
    "web_api_key":                        ["url", "token"],
    "web_oauth2_password":                ["url", "username", "password", "client_id"],
    "web_oauth2_client_credentials":      ["url", "client_id", "client_secret"],
    "web_ntlm":                           ["url", "username", "password", "domain"],
    "ad_ldap_bind":                       ["domain", "username", "password", "ldap_server", "ldap_base_dn"],
    "ad_kerberos":                        ["username", "password", "realm"],
    "ad_ntlm":                            ["url", "username", "password", "domain"],
    "keycloak_oauth2_password":           ["url", "username", "password", "client_id"],
    "keycloak_oauth2_client_credentials": ["url", "client_id", "client_secret"],
    "keycloak_oidc":                      ["url", "username", "password", "client_id"],
    "ldap_simple":                        ["ldap_server", "username", "password", "ldap_base_dn"],
    "ldap_sasl":                          ["ldap_server", "username", "password"],
    "ldap_anonymous":                     ["ldap_server", "ldap_base_dn"],
    "db_mysql":                           ["db_host", "username", "password"],
    "db_postgresql":                      ["db_host", "username", "password"],
    "db_mssql":                           ["db_host", "username", "password"],
    "ssh_password":                       ["url", "username", "password"],
    "ssh_key":                            ["url", "username", "ssh_key_path"],
}

# Human-readable field prompts
FIELD_PROMPTS = {
    "url":            ("Login URL or token endpoint", ""),
    "username":       ("Username", ""),
    "password":       ("Password", ""),
    "domain":         ("AD Domain (e.g. CORP)", ""),
    "realm":          ("Kerberos Realm (e.g. CORP.LOCAL)", ""),
    "token":          ("Token value", ""),
    "client_id":      ("Client ID", ""),
    "client_secret":  ("Client Secret", ""),
    "scope":          ("OAuth2 Scope (empty = default)", ""),
    "ldap_server":    ("LDAP server URL (e.g. ldap://dc01.corp.local)", ""),
    "ldap_base_dn":   ("LDAP Base DN (e.g. dc=corp,dc=local)", ""),
    "db_host":        ("Database host", ""),
    "db_name":        ("Database name", ""),
    "ssh_key_path":   ("SSH key file path", ""),
}


def configure_auth(config: Dict[str, Any], config_path: Path) -> Dict[str, Any]:
    """Interactive auth configuration for grey/white-box engagements.

    Lets the operator add auth targets (web portal, AD, LDAP, Keycloak, etc.)
    that bots will use to authenticate before testing.
    """
    console.print()
    console.print("  [dim]Configure credentials for authenticated testing.[/dim]")
    console.print("  [dim]Leave empty for black-box (no credentials) engagements.[/dim]")
    console.print()

    auth_section = config.get("auth", {"targets": []})
    targets = auth_section.get("targets", [])

    if not Confirm.ask("  Configure authentication targets?", default=bool(targets)):
        if not targets:
            return config  # Black-box — no auth needed
        # Keep existing
        return config

    while True:
        console.print()
        console.print("  [bold]Available auth methods:[/bold]")
        for i, (method_id, method_label) in enumerate(AUTH_METHODS, 1):
            console.print(f"    {i}. {method_label}")

        console.print()
        choice = Prompt.ask("  Method number (or 'done' to finish)", default="done")

        if choice.lower() == "done":
            break

        try:
            method_idx = int(choice) - 1
            method_id, method_label = AUTH_METHODS[method_idx]
        except (ValueError, IndexError):
            console.print("  [red]Invalid selection[/red]")
            continue

        # Get target ID
        console.print()
        target_id = Prompt.ask("  Target ID (logical name, e.g. 'web_portal')", default=method_id)

        # Check for duplicate
        existing_ids = [t.get("target_id") for t in targets if isinstance(t, dict)]
        if target_id in existing_ids:
            if not Confirm.ask(f"  Target '{target_id}' already exists. Replace?", default=True):
                continue
            targets = [t for t in targets if t.get("target_id") != target_id]

        # Prompt for required fields
        target_config: Dict[str, Any] = {
            "target_id": target_id,
            "method": method_id,
        }

        required = AUTH_REQUIRED_FIELDS.get(method_id, [])
        for field_name in required:
            prompt_text, default_val = FIELD_PROMPTS.get(field_name, (field_name, ""))
            is_secret = field_name in ("password", "client_secret", "token")
            if is_secret:
                value = Prompt.ask(f"  {prompt_text}", password=True, default=default_val)
            else:
                value = Prompt.ask(f"  {prompt_text}", default=default_val)
            if value:
                target_config[field_name] = value

        # Optional fields
        if Confirm.ask("  Configure optional fields?", default=False):
            optional_fields = [f for f in FIELD_PROMPTS if f not in required]
            for field_name in optional_fields:
                prompt_text, default_val = FIELD_PROMPTS.get(field_name, (field_name, ""))
                is_secret = field_name in ("password", "client_secret", "token")
                value = Prompt.ask(f"  {prompt_text} (empty = skip)", password=is_secret, default="")
                if value:
                    target_config[field_name] = value

        target_config["description"] = Prompt.ask(
            "  Description (optional)", default=""
        )

        targets.append(target_config)
        console.print(f"  [green]✓  Added auth target '{target_id}' ({method_id})[/green]")

        if not Confirm.ask("  Add another auth target?", default=False):
            break

    auth_section["targets"] = targets
    config["auth"] = auth_section

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    console.print(f"  [green]✓  Auth configuration saved ({len(targets)} targets)[/green]")

    return config


def run_wizard(mission_dir: Optional[Path] = None) -> Optional[tuple[Dict[str, Any], Path]]:
    """Run the full TUI setup wizard.

    Args:
        mission_dir: Mission directory path. If None, uses default "mission".

    Returns:
        (config, mission_dir) if all checks pass — mission_dir reflects the
        directory the config actually lives in (may differ from the default
        when the user picks an existing mission or types a custom dir).
        None if the user exits.
    """
    mission_dir = mission_dir or Path("mission")
    config_path = mission_dir / "swarm-config.json"

    # ─── Welcome ───
    print_banner()
    console.print()
    console.print("  [bold]Pre-flight Wizard[/bold] — verifying configuration before launch")
    console.print("  [dim]Press Ctrl+C at any time to exit[/dim]")

    while True:
        try:
            # ─── Step 1: Config File Check ───
            step_header(1, "Configuration File", "Check for swarm-config.json")

            config = check_config_file(mission_dir)

            if config is None:
                # Offer existing missions before creating a new one — users
                # often run from the default dir while their mission lives
                # elsewhere (e.g. cyberian-defenses_audit/).
                existing = find_existing_missions(Path.cwd())
                if existing:
                    console.print()
                    console.print(f"  [dim]No config in {mission_dir}/, but existing missions found:[/dim]")
                    for i, p in enumerate(existing, 1):
                        console.print(f"    {i}. {p}")
                    choice = Prompt.ask(
                        "  Mission number to open (or 'new')", default="1"
                    ).strip().lower()
                    if choice != "new":
                        try:
                            mission_dir = existing[int(choice) - 1]
                            config_path = mission_dir / "swarm-config.json"
                            config = check_config_file(mission_dir)
                        except (ValueError, IndexError):
                            console.print("  [red]Invalid selection[/red]")

            if config is None:
                console.print()
                should_setup = Confirm.ask(
                    "  No configuration found. Run interactive setup?",
                    default=True
                )
                if not should_setup:
                    console.print("  [yellow]Exiting — no configuration.[/yellow]")
                    return None
                config, config_path = run_mission_setup(mission_dir)
                mission_dir = config_path.parent
            else:
                console.print(f"  [green]✓  Configuration found: {config_path}[/green]")
                console.print(f"  [dim]   Mission: {config.get('mission_name', 'N/A')}[/dim]")
                console.print(f"  [dim]   Bots: {len(config.get('bots', {}))} configured[/dim]")

            # ─── Step 2: LLM Connectivity Check ───
            step_header(2, "LLM Connectivity Check", "Testing each bot's LLM connection")

            results, all_connected = run_connectivity_check(config)

            if all_connected:
                console.print()
                console.print("  [bold green]✓  All 9 bots connected successfully[/bold green]")
            else:
                failed_bots = [r for r in results if r["status"] != "connected"]
                console.print()
                console.print(f"  [bold red]✗  {len(failed_bots)} bot(s) failed connectivity[/bold red]")
                # Group identical errors — one message for 9 identical failures, not 9 dumps
                error_groups: Dict[str, List[str]] = {}
                for r in failed_bots:
                    error_groups.setdefault(r.get("error", "empty response"), []).append(r["bot_name"])
                for err, bots in error_groups.items():
                    console.print(f"    [red]• {', '.join(bots)}[/red]:")
                    console.print(textwrap.fill(err, width=88,
                                                initial_indent="      ",
                                                subsequent_indent="      "))

                # Offer to reconfigure failed bots
                console.print()
                all_failed = len(failed_bots) == len(results)
                action = Prompt.ask(
                    "  [bold]What do you want to do?[/bold]",
                    choices=["reconfigure-all", "reconfigure", "retry", "continue", "exit"],
                    default="reconfigure-all" if all_failed else "retry",
                )

                if action == "exit":
                    console.print("  [yellow]Exiting.[/yellow]")
                    return None
                elif action == "continue":
                    console.print("  [yellow]⚠  Proceeding with failed bots — some may not work[/yellow]")
                elif action == "reconfigure-all":
                    # Shared-or-per-bot flow — same as first-time setup
                    config = configure_llm_backends(config, config_path)
                    console.print()
                    console.print("  [bold]Re-running connectivity check...[/bold]")
                    continue  # Loop back to step 2
                elif action == "reconfigure":
                    # List failed bots for selection
                    console.print()
                    console.print("  [bold]Which bot to reconfigure?[/bold]")
                    for i, r in enumerate(failed_bots, 1):
                        info = BOT_INFO.get(r["bot_name"], {"role": "?", "icon": "?"})
                        console.print(
                            f"    {i}. {info['icon']} {r['bot_name']} "
                            f"({info['role']}) — {r['status']}"
                        )
                    choice = Prompt.ask("  Bot number (or 'all')", default="1")
                    if choice == "all":
                        for r in failed_bots:
                            config = reconfigure_bot(r["bot_name"], config, config_path)
                    else:
                        try:
                            bot_idx = int(choice) - 1
                            config = reconfigure_bot(
                                failed_bots[bot_idx]["bot_name"],
                                config,
                                config_path
                            )
                        except (ValueError, IndexError):
                            console.print("  [red]Invalid selection[/red]")

                    # Re-run connectivity check after reconfigure
                    console.print()
                    console.print("  [bold]Re-running connectivity check...[/bold]")
                    continue  # Loop back to step 2

                elif action == "retry":
                    console.print()
                    console.print("  [bold]Retrying connectivity check...[/bold]")
                    continue  # Loop back to step 2

            # ─── Step 3: Auth Configuration (grey/white-box) ───
            step_header(3, "Authentication Setup", "Configure credentials for grey/white-box engagements")

            config = configure_auth(config, config_path)

            # ─── Step 4: Summary ───
            step_header(4, "Configuration Summary", "Ready to launch")

            show_config_summary(config)

            console.print()
            ready = Confirm.ask("\n  Launch Chimeras with this configuration?", default=True)
            if ready:
                console.print()
                console.print("  [bold green]✓  Pre-flight complete. Launching...[/bold green]")
                console.print()
                return config, config_path.parent
            else:
                console.print()
                action = Prompt.ask(
                    "  [bold]What next?[/bold]",
                    choices=["reconfigure", "restart", "exit"],
                    default="exit",
                )
                if action == "exit":
                    return None
                elif action == "restart":
                    continue  # Loop back to step 1
                elif action == "reconfigure":
                    console.print()
                    console.print("  [bold]Which bot to reconfigure?[/bold]")
                    for i, bot in enumerate(BOT_ORDER, 1):
                        info = BOT_INFO.get(bot, {"role": "?", "icon": "?"})
                        console.print(f"    {i}. {info['icon']} {bot} ({info['role']})")
                    choice = Prompt.ask("  Bot number", default="1")
                    try:
                        bot_idx = int(choice) - 1
                        config = reconfigure_bot(BOT_ORDER[bot_idx], config, config_path)
                    except (ValueError, IndexError):
                        console.print("  [red]Invalid selection[/red]")
                    continue

        except KeyboardInterrupt:
            console.print()
            console.print("  [yellow]Exiting — interrupted by user.[/yellow]")
            return None