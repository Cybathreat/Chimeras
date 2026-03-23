"""
SwarmBots v2.0 — Entry Point

Project setup CLI and operation launch.
"""

import asyncio
import argparse
import json
from pathlib import Path
from datetime import datetime

from core.config import ConfigManager, setup_cli
from core.state import SwarmState
from graph import compile_graph


async def run_operation(mission_dir: Path, swarm_config: dict) -> SwarmState:
    """
    Execute a full SwarmBots operation.
    
    Args:
        mission_dir: Path to mission workspace
        swarm_config: Loaded swarm-config.json
    
    Returns:
        Final state with all reports
    """
    # Initialize state
    state = SwarmState(
        mission={},
        swarm_config=swarm_config,
        human_approval=False,
        abort_flag=False
    )
    
    # Load mission details
    mission_path = mission_dir / "mission.md"
    if mission_path.exists():
        state["mission"] = {
            "name": swarm_config.get("mission_name", "unnamed"),
            "path": str(mission_path),
            "created": swarm_config.get("created")
        }
    
    # Compile graph
    app = compile_graph(swarm_config)
    
    # Run operation
    print("\n" + "="*60)
    print("SWARMBOTS OPERATION LAUNCHED")
    print("="*60)
    print(f"Mission: {state['mission'].get('name')}")
    print(f"Started: {datetime.utcnow().isoformat()}")
    print("="*60 + "\n")
    
    # Execute graph
    final_state = await app.ainvoke(state)
    
    print("\n" + "="*60)
    print("OPERATION COMPLETE")
    print("="*60)
    print(f"Final Report Generated: {final_state.get('final_report', {}).get('generated_at')}")
    print(f"Bots Deployed: {list(final_state.get('reasoning_reports', {}).keys())}")
    print(f"Total Actions: {len(final_state.get('operation_ledger', []))}")
    print("="*60 + "\n")
    
    return final_state


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="SwarmBots v2.0 - Autonomous AI Security Testing Swarm",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  swarmbots setup --mission "Operation Alpha" --objectives "Pentest web app" --scope "192.168.1.0/24" --roe "No DoS"
  swarmbots run --mission-dir ./mission
  swarmbots status --mission-dir ./mission
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Initialize new mission")
    setup_parser.add_argument("--mission", "-m", required=True, help="Mission name")
    setup_parser.add_argument("--objectives", "-o", required=True, help="Mission objectives")
    setup_parser.add_argument("--scope", "-s", required=True, help="Scope of engagement")
    setup_parser.add_argument("--roe", "-r", required=True, help="Rules of engagement")
    setup_parser.add_argument("--dir", "-d", default="mission", help="Mission directory")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Execute operation")
    run_parser.add_argument("--mission-dir", "-d", default="mission", help="Mission directory")
    run_parser.add_argument("--config", "-c", help="Custom swarm-config.json")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show operation status")
    status_parser.add_argument("--mission-dir", "-d", default="mission", help="Mission directory")
    
    args = parser.parse_args()
    
    if args.command == "setup":
        manager = ConfigManager(Path(args.dir))
        mission_path = manager.setup_mission(
            mission_name=args.mission,
            objectives=args.objectives,
            scope=args.scope,
            roe=args.roe
        )
        print(f"\n✓ Mission initialized at: {mission_path.absolute()}")
        print(f"  Run: swarmbots run --mission-dir {args.dir}")
    
    elif args.command == "run":
        mission_dir = Path(args.mission_dir)
        config_path = mission_dir / "swarm-config.json"
        
        if not config_path.exists():
            print(f"Error: No swarm-config.json found in {mission_dir}")
            print("Run: swarmbots setup --mission <name> ...")
            return
        
        with open(config_path) as f:
            swarm_config = json.load(f)
        
        asyncio.run(run_operation(mission_dir, swarm_config))
    
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
            print(f"  {bot}: {cfg.get('provider')}/{cfg.get('model')}")


if __name__ == "__main__":
    main()
