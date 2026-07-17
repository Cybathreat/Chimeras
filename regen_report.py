#!/usr/bin/env python3
"""Regenerate only the Bookkeeper report from existing engagement files."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.state import SwarmState
from bookkeeper.agent import Bookkeeper


async def main():
    mission_dir = Path("mission_cyberian")
    config_path = mission_dir / "swarm-config.json"

    with open(config_path) as f:
        swarm_config = json.load(f)

    engagement_dir = mission_dir / "engagement"

    state = SwarmState(
        mission={
            "name": swarm_config.get("mission_name", "unnamed"),
            "path": str(mission_dir / "mission.md"),
            "created": swarm_config.get("created"),
            "scope": "cyberian-defenses.com",
            "target": "cyberian-defenses.com",
        },
        swarm_config=swarm_config,
        human_approval=True,
        abort_flag=False,
        engagement_dir=str(engagement_dir),
    )

    # Populate reasoning_reports with existing bot files so Bookkeeper knows who ran
    for bot_file in engagement_dir.glob("*.md"):
        name = bot_file.stem
        if name not in ("plan", "log", "findings"):
            state.setdefault("reasoning_reports", {})[name] = {"ran": True}

    bot = Bookkeeper(state, swarm_config)
    await bot.run()
    print("\n✓ Report regenerated at mission_cyberian/engagement/report/final_report.md")


if __name__ == "__main__":
    asyncio.run(main())