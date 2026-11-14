"""
Chimeras v2.0 — Config Manager + Interactive Setup

Handles mission initialization, swarm-config.json management,
engagement folder structure, and interactive CLI setup.

v2 Phase 0: Config migration — auto-upgrades v1 configs to v2 schema.
  - Adds version field
  - Fills missing bots with defaults
  - Initializes v2 state fields in config
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


# v2 config schema version
CONFIG_VERSION = "2.0"

DEFAULT_SWARM_CONFIG = {
    "version": CONFIG_VERSION,
    "created": None,
    "mission_name": None,
    "bots": {
        "warchief":     {"provider": "openai", "model": "glm-5.2", "base_url": "https://ollama.com/v1"},
        "aria":         {"provider": "openai", "model": "glm-5.2", "base_url": "https://ollama.com/v1"},
        "lisa":         {"provider": "openai", "model": "glm-5.2", "base_url": "https://ollama.com/v1"},
        "bloodhound":   {"provider": "openai", "model": "glm-5.2", "base_url": "https://ollama.com/v1"},
        "wasp":         {"provider": "openai", "model": "glm-5.2", "base_url": "https://ollama.com/v1"},
        "marksman":     {"provider": "openai", "model": "glm-5.2", "base_url": "https://ollama.com/v1"},
        "thief":        {"provider": "openai", "model": "glm-5.2", "base_url": "https://ollama.com/v1"},
        "magician":     {"provider": "openai", "model": "glm-5.2", "base_url": "https://ollama.com/v1"},
        "bookkeeper":   {"provider": "openai", "model": "glm-5.2", "base_url": "https://ollama.com/v1"},
    },
    "fallback_chain": ["ollama"],
    "human_approval_required": True,
    # v2 fields
    "max_loops_per_phase": 5,
    "default_aggressiveness": "cautious",
    # v3.0: Docker sandboxing
    "enable_docker": False,
    # v3.0: Budget management (USD cap per engagement, None = unlimited)
    "budget_usd": None,
    # v3.3: Authentication for grey/white-box engagements
    "auth": {
        "targets": [],  # List of AuthCredential dicts
    },
}

# Engagement folder structure
ENGAGEMENT_DIRS = [
    "report",
    "findings",
    "poc",
    "raw",
    "auth",
]

ENGAGEMENT_FILES = {
    "plan.md": "# Engagement Plan\n\nMission: {mission_name}\nCreated: {timestamp}\n\n## Objectives\n{objectives}\n\n## Scope\n{scope}\n\n## Rules of Engagement\n{roe}\n\n## Bot Execution Order\nWarChief → ARIA → Lisa → Bloodhound → [HUMAN APPROVAL] → Surgeon → Magician + Thief → Bookkeeper\n",
    "log.md": "# Operation Log\n\nMission: {mission_name}\nStarted: {timestamp}\n\n## Ledger\n\n",
    "findings.md": "# Findings\n\nMission: {mission_name}\nCreated: {timestamp}\n\n",
}


class ConfigManager:
    """Manages Chimeras configuration, mission setup, and engagement folders."""

    def __init__(self, mission_dir: Optional[Path] = None):
        self.mission_dir = mission_dir or Path.cwd() / "mission"
        self.config_path = self.mission_dir / "swarm-config.json"
        self.mission_path = self.mission_dir / "mission.md"
        self.soul_path = self.mission_dir / "soul.md"

    def setup_mission(self, mission_name: str, objectives: str, scope: str,
                      roe: str, contacts: Optional[Dict[str, str]] = None,
                      lateral_objectives: Optional[str] = None,
                      internal_scope: Optional[str] = None) -> Path:
        """
        Initialize a new mission workspace.

        Creates:
        - mission/swarm-config.json
        - mission/mission.md
        - mission/soul.md
        - mission/engagement/  (plan.md, log.md, findings.md)
        - mission/engagement/report/
        - mission/engagement/findings/
        - mission/engagement/poc/
        - mission/payloads/
        - mission/exfil-staging/
        - mission/operation-vault/
        """
        self.mission_dir.mkdir(parents=True, exist_ok=True)

        # Create operational subdirectories
        for d in ["payloads", "exfil-staging", "operation-vault"]:
            (self.mission_dir / d).mkdir(exist_ok=True)

        # Create engagement folder structure
        engagement_dir = self.mission_dir / "engagement"
        engagement_dir.mkdir(exist_ok=True)
        for d in ENGAGEMENT_DIRS:
            (engagement_dir / d).mkdir(exist_ok=True)

        timestamp = datetime.utcnow().isoformat()

        # Write engagement files (plan.md, log.md, findings.md)
        for filename, template in ENGAGEMENT_FILES.items():
            content = template.format(
                mission_name=mission_name,
                timestamp=timestamp,
                objectives=objectives,
                scope=scope,
                roe=roe,
            )
            (engagement_dir / filename).write_text(content)

        # Write swarm-config.json
        config = DEFAULT_SWARM_CONFIG.copy()
        config["created"] = timestamp
        config["mission_name"] = mission_name
        # Deep copy bots dict to avoid mutation
        config["bots"] = json.loads(json.dumps(DEFAULT_SWARM_CONFIG["bots"]))
        # v2 Phase 3: lateral movement objectives
        if lateral_objectives:
            config["lateral_objectives"] = lateral_objectives
        if internal_scope:
            config["internal_scope"] = internal_scope
        self._write_json(config)

        # Write mission.md
        lateral_section = ""
        if lateral_objectives:
            lateral_section += f"\n## Lateral Movement Objectives\n{lateral_objectives}\n"
            lateral_section += "\nNOTE: Lateral objectives do NOT auto-authorize lateral movement.\n"
            lateral_section += "The lateral_approval gate must still be passed.\n"
        if internal_scope:
            lateral_section += f"\n## Internal Scope (lateral movement)\n{internal_scope}\n"

        mission_content = f"""# Mission: {mission_name}
Created: {timestamp}

## Objectives
{objectives}

## Scope
{scope}

## Rules of Engagement (RoE)
{roe}
{lateral_section}
## Emergency Contacts
{json.dumps(contacts or {}, indent=2)}

## Engagement Folder
{engagement_dir}/
  ├── plan.md       # Strategic plan, updated by WarChief
  ├── log.md        # Operation ledger, updated by all bots
  ├── findings.md   # Consolidated findings, updated by Bloodhound/Surgeon/Thief/Magician
  ├── report/       # Final report directory
  ├── findings/     # Detailed findings directory
  └── poc/          # Proof-of-concept directory
"""
        self.mission_path.write_text(mission_content)

        # Write soul.md
        soul_content = """# Bot Identities and Behavioral Constraints

## WarChief
Cold, strategic, orchestrator. Never acts without full state awareness.

## ARIA
Passive, observant, thorough. Leaves no trace.

## Lisa
Methodical, precise, comprehensive. Maps the attack surface.

## Bloodhound
Relentless, evidence-driven, patient. Finds what others miss.

## Surgeon
Surgical, precise, controlled. Strikes only when approved.

## Pathologist
Creative, adaptive, technical. Crafts custom tools.

## Thief
Ghost-like, covert, efficient. Never leaves evidence.

## Magician
Unpredictable, clever, lateral. Finds paths others cannot.

## Bookkeeper
Meticulous, impartial, complete. Records everything.
"""
        self.soul_path.write_text(soul_content)

        return self.mission_dir

    def load_config(self) -> Dict[str, Any]:
        """Load swarm-config.json.

        v2: Auto-migrates v1 configs to v2 schema if needed.
        """
        if not self.config_path.exists():
            self._write_json(DEFAULT_SWARM_CONFIG)
        config = self._read_json(self.config_path)

        # v2: Check if migration is needed
        config_version = config.get("version", "1.0")
        if config_version != CONFIG_VERSION:
            config = self._migrate_config(config)

        return config

    def _migrate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate v1 config to v2 schema.

        Changes:
        - Adds version field
        - Fills missing bots with defaults
        - Adds v2 fields (max_loops_per_phase, default_aggressiveness)
        - Saves migrated config to disk
        """
        # Ensure all bots are present
        for bot_name, bot_default in DEFAULT_SWARM_CONFIG["bots"].items():
            if bot_name not in config.get("bots", {}):
                config["bots"][bot_name] = bot_default.copy()

        # Add v2 fields if missing
        if "max_loops_per_phase" not in config:
            config["max_loops_per_phase"] = 5
        if "default_aggressiveness" not in config:
            config["default_aggressiveness"] = "cautious"
        # v3.3: Add auth section if missing
        if "auth" not in config:
            config["auth"] = {"targets": []}

        # Update version
        config["version"] = CONFIG_VERSION

        # Save migrated config
        self._write_json(config)

        return config

    def update_bot_config(self, bot_name: str, provider: str,
                          model: Optional[str] = None,
                          base_url: Optional[str] = None) -> None:
        """Update a specific bot's LLM configuration.

        Args:
            bot_name: Bot identifier (e.g. 'warchief')
            provider: LLM provider (anthropic, openai, ollama, etc.)
            model: Model name (optional — keeps existing if not provided)
            base_url: Custom gateway/proxy URL (optional, OpenAI/Anthropic only).
                      Can also be set via OPENAI_BASE_URL / ANTHROPIC_BASE_URL env vars.
        """
        config = self.load_config()
        new_config = {
            "provider": provider,
            "model": model or config["bots"][bot_name].get("model")
        }
        if base_url:
            new_config["base_url"] = base_url
        config["bots"][bot_name] = new_config
        self._write_json(config)

    def _write_json(self, data: Dict[str, Any]) -> None:
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)

    def _read_json(self, path: Path) -> Dict[str, Any]:
        with open(path, "r") as f:
            return json.load(f)


def interactive_setup() -> Dict[str, str]:
    """
    Interactive CLI setup — prompts operator for mission details.

    Returns dict with: mission_name, objectives, scope, roe, dir
    """
    print()
    print("=" * 60)
    print("  CHIMERAS v2.0 — INTERACTIVE MISSION SETUP")
    print("=" * 60)
    print()

    mission_name = input("Mission name: ").strip()
    if not mission_name:
        mission_name = "Operation Default"
        print(f"  (using default: {mission_name})")

    print()
    objectives = input("Objectives (one line): ").strip()
    if not objectives:
        objectives = "Comprehensive penetration test of target infrastructure"
        print(f"  (using default: {objectives})")

    print()
    scope = input("Scope (IPs/domains): ").strip()
    if not scope:
        scope = "10.10.10.0/24"
        print(f"  (using default: {scope})")

    print()
    roe = input("Rules of Engagement: ").strip()
    if not roe:
        roe = "No DoS, no data destruction, stealth preferred, business hours only"
        print(f"  (using default: {roe})")

    print()
    mission_dir = input("Mission directory [mission]: ").strip()
    if not mission_dir:
        mission_dir = "mission"

    result = {
        "mission_name": mission_name,
        "objectives": objectives,
        "scope": scope,
        "roe": roe,
        "dir": mission_dir,
    }

    print()
    print("=" * 60)
    print("  MISSION PARAMETERS CONFIRMED")
    print("=" * 60)
    print(f"  Name:       {mission_name}")
    print(f"  Objectives: {objectives}")
    print(f"  Scope:      {scope}")
    print(f"  RoE:        {roe}")
    print(f"  Dir:        {mission_dir}")
    print("=" * 60)
    print()

    return result