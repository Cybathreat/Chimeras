"""
Chimeras v1.0 — Entry Point

Interactive setup, operation launch, and status reporting.
"""

import asyncio
import argparse
import json
import re
from pathlib import Path
from datetime import datetime

from core.config import ConfigManager, interactive_setup
from core.state import SwarmState
from graph import compile_graph


def parse_scope_from_mission(mission_path: Path) -> str:
    """Extract the target scope from mission.md."""
    if not mission_path.exists():
        return ""
    content = mission_path.read_text()
    # Find Scope section
    scope_match = re.search(r'## Scope\s*\n(.+?)(?=\n##|\Z)', content, re.DOTALL)
    if scope_match:
        scope = scope_match.group(1).strip()
        # Extract first IP or domain
        ip_match = re.search(r'\d+\.\d+\.\d+\.\d+(/\d+)?', scope)
        if ip_match:
            return ip_match.group(0)
        return scope.split('\n')[0]
    return ""


async def run_operation(mission_dir: Path, swarm_config: dict, auto_approve: bool = False) -> SwarmState:
    """Execute a full Chimeras operation."""

    engagement_dir = mission_dir / "engagement"
    mission_path = mission_dir / "mission.md"

    # Parse scope from mission file
    target_scope = parse_scope_from_mission(mission_path)

    # Initialize state
    state = SwarmState(
        mission={
            "name": swarm_config.get("mission_name", "unnamed"),
            "path": str(mission_path),
            "created": swarm_config.get("created"),
            "scope": target_scope,
            "target": target_scope.split("/")[0] if target_scope else "",
        },
        swarm_config=swarm_config,
        human_approval=False,
        abort_flag=False,
        engagement_dir=str(engagement_dir),
    )

    # Compile graph
    app = compile_graph(swarm_config, auto_approve)

    print("\n" + "=" * 60)
    print("CHIMERAS OPERATION LAUNCHED")
    print("=" * 60)
    print(f"Mission: {state['mission'].get('name')}")
    print(f"Target: {target_scope or 'N/A'}")
    print(f"Started: {datetime.utcnow().isoformat()}")
    print(f"Engagement: {engagement_dir}")
    print("=" * 60 + "\n")

    # Execute graph
    final_state = await app.ainvoke(state)

    print("\n" + "=" * 60)
    print("OPERATION COMPLETE")
    print("=" * 60)
    final_report = final_state.get("final_report", {})
    print(f"Final Report Generated: {final_report.get('generated_at', 'N/A')}")
    print(f"Bots Deployed: {list(final_state.get('reasoning_reports', {}).keys())}")
    print(f"Engagement Folder: {engagement_dir}")
    print("=" * 60 + "\n")

    return final_state


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Chimeras v1.0 - Autonomous AI Security Testing Swarm",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                          # Interactive setup + run
  python main.py setup --mission "Op Alpha" --objectives "Pentest web app" --scope "10.10.10.0/24" --roe "No DoS"
  python main.py run --mission-dir ./mission
  python main.py status --mission-dir ./mission
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    setup_parser = subparsers.add_parser("setup", help="Initialize new mission")
    setup_parser.add_argument("--mission", "-m", required=True, help="Mission name")
    setup_parser.add_argument("--objectives", "-o", required=True, help="Mission objectives")
    setup_parser.add_argument("--scope", "-s", required=True, help="Scope of engagement (IPs/domains)")
    setup_parser.add_argument("--roe", "-r", required=True, help="Rules of engagement")
    setup_parser.add_argument("--dir", "-d", default="mission", help="Mission directory")

    run_parser = subparsers.add_parser("run", help="Execute operation")
    run_parser.add_argument("--mission-dir", "-d", default="mission", help="Mission directory")
    run_parser.add_argument("--config", "-c", help="Custom swarm-config.json")
    run_parser.add_argument("--approve", action="store_true", help="Auto-approve exploitation phase (skip human gate)")

    status_parser = subparsers.add_parser("status", help="Show operation status")
    status_parser.add_argument("--mission-dir", "-d", default="mission", help="Mission directory")

    args = parser.parse_args()

    if args.command == "setup":
        manager = ConfigManager(Path(args.dir))
        mission_path = manager.setup_mission(
            mission_name=args.mission,
            objectives=args.objectives,
            scope=args.scope,
            roe=args.roe,
        )
        print(f"\n✓ Mission initialized at: {mission_path.absolute()}")
        print(f"  Engagement folder: {mission_path / 'engagement'}")
        print(f"  Run: python main.py run --mission-dir {args.dir}")

    elif args.command == "run":
        mission_dir = Path(args.mission_dir)
        config_path = mission_dir / "swarm-config.json"

        if not config_path.exists():
            print(f"Error: No swarm-config.json found in {mission_dir}")
            print("Run: python main.py setup --mission <name> ...")
            return

        with open(config_path) as f:
            swarm_config = json.load(f)

        asyncio.run(run_operation(mission_dir, swarm_config, args.approve))

    elif args.command == "status":
        mission_dir = Path(args.mission_dir)
        config_path = mission_dir / "swarm-config.json"

        if not config_path.exists():
            print(f"No mission found in {mission_dir}")
            return

        with open(config_path) as f:
            config = json.load(f)

        print(f"\nMission: {config.get('mission_name')}")
        print(f"Created: {config.get('created')}")
        print(f"Bots configured: {len(config.get('bots', {}))}")
        for bot, cfg in config.get("bots", {}).items():
            line = f"  {bot}: {cfg.get('provider')}/{cfg.get('model')}"
            if cfg.get("base_url"):
                line += f" (gateway: {cfg['base_url']})"
            print(line)

        eng_dir = mission_dir / "engagement"
        if eng_dir.exists():
            print(f"\nEngagement folder: {eng_dir}")
            for item in sorted(eng_dir.iterdir()):
                if item.is_dir():
                    count = len(list(item.iterdir()))
                    print(f"  {item.name}/ ({count} files)")
                else:
                    size = item.stat().st_size
                    print(f"  {item.name} ({size} bytes)")

    else:
        # Interactive mode
        params = interactive_setup()

        manager = ConfigManager(Path(params["dir"]))
        mission_path = manager.setup_mission(
            mission_name=params["mission_name"],
            objectives=params["objectives"],
            scope=params["scope"],
            roe=params["roe"],
        )
        print(f"✓ Mission initialized at: {mission_path.absolute()}")
        print(f"✓ Engagement folder: {mission_path / 'engagement'}")

        config_path = mission_path / "swarm-config.json"
        with open(config_path) as f:
            swarm_config = json.load(f)

        asyncio.run(run_operation(mission_path, swarm_config))


if __name__ == "__main__":
    main()