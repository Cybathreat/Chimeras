"""
SwarmBots v2.0 — Project Setup CLI and Configuration Manager

Handles mission initialization, swarm-config.json management,
and LLM model selection.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


DEFAULT_SWARM_CONFIG = {
    "version": "2.0",
    "created": None,
    "mission_name": None,
    "bots": {
        "warchief": {"provider": "anthropic", "model": "claude-opus-4-6-20250929"},
        "aria": {"provider": "ollama", "model": "qwen2.5:14b"},
        "lisa": {"provider": "google", "model": "gemini-2.5-flash"},
        "bloodhound": {"provider": "anthropic", "model": "claude-sonnet-4-6-20250929"},
        "surgeon": {"provider": "anthropic", "model": "claude-opus-4-6-20250929"},
        "pathologist": {"provider": "groq", "model": "llama-3.3-70b-versatile"},
        "thief": {"provider": "ollama", "model": "qwen2.5:14b"},
        "magician": {"provider": "anthropic", "model": "claude-sonnet-4-6-20250929"},
        "bookkeeper": {"provider": "ollama", "model": "qwen2.5:7b"}
    },
    "fallback_chain": ["groq", "openrouter", "ollama"],
    "human_approval_required": True
}


class ConfigManager:
    """Manages SwarmBots configuration and mission setup."""
    
    def __init__(self, mission_dir: Optional[Path] = None):
        self.mission_dir = mission_dir or Path.cwd() / "mission"
        self.config_path = self.mission_dir / "swarm-config.json"
        self.mission_path = self.mission_dir / "mission.md"
        self.soul_path = self.mission_dir / "soul.md"
    
    def setup_mission(self, mission_name: str, objectives: str, scope: str, 
                      roe: str, contacts: Optional[Dict[str, str]] = None) -> Path:
        """
        Initialize a new mission workspace.
        
        Creates:
        - mission/swarm-config.json
        - mission/mission.md
        - mission/soul.md
        - mission/payloads/
        - mission/exfil-staging/
        - mission/operation-vault/
        """
        self.mission_dir.mkdir(parents=True, exist_ok=True)
        (self.mission_dir / "payloads").mkdir(exist_ok=True)
        (self.mission_dir / "exfil-staging").mkdir(exist_ok=True)
        (self.mission_dir / "operation-vault").mkdir(exist_ok=True)
        
        # Write swarm-config.json
        config = DEFAULT_SWARM_CONFIG.copy()
        config["created"] = datetime.utcnow().isoformat()
        config["mission_name"] = mission_name
        self._write_json(config)
        
        # Write mission.md
        mission_content = f"""# Mission: {mission_name}
Created: {datetime.utcnow().isoformat()}

## Objectives
{objectives}

## Scope
{scope}

## Rules of Engagement (RoE)
{roe}

## Emergency Contacts
{json.dumps(contacts or {}, indent=2)}
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
        """Load swarm-config.json."""
        if not self.config_path.exists():
            self._write_json(DEFAULT_SWARM_CONFIG)
        return self._read_json(self.config_path)
    
    def update_bot_config(self, bot_name: str, provider: str, 
                          model: Optional[str] = None) -> None:
        """Update a specific bot's LLM configuration."""
        config = self.load_config()
        config["bots"][bot_name] = {
            "provider": provider,
            "model": model or config["bots"][bot_name].get("model")
        }
        self._write_json(config)
    
    def _write_json(self, data: Dict[str, Any]) -> None:
        """Write JSON config file."""
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def _read_json(self, path: Path) -> Dict[str, Any]:
        """Read JSON config file."""
        with open(path, "r") as f:
            return json.load(f)


def setup_cli():
    """CLI entry point for mission setup."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="SwarmBots Mission Setup CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--mission", "-m", required=True, help="Mission name")
    parser.add_argument("--objectives", "-o", required=True, help="Mission objectives")
    parser.add_argument("--scope", "-s", required=True, help="Scope of engagement")
    parser.add_argument("--roe", "-r", required=True, help="Rules of engagement")
    parser.add_argument("--dir", "-d", default="mission", help="Mission directory")
    
    args = parser.parse_args()
    
    manager = ConfigManager(Path(args.dir))
    mission_path = manager.setup_mission(
        mission_name=args.mission,
        objectives=args.objectives,
        scope=args.scope,
        roe=args.roe
    )
    
    print(f"✓ Mission initialized at: {mission_path.absolute()}")
    print(f"  Config: {manager.config_path.absolute()}")
    print(f"  Mission: {manager.mission_path.absolute()}")


if __name__ == "__main__":
    setup_cli()
