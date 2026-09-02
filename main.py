"""
Chimeras v2.0 — Entry Point

Interactive setup, operation launch, and status reporting.

v2: Pre-flight TUI wizard replaces the old interactive_setup flow.
When you run `python main.py` with no arguments, the wizard:
  1. Checks for swarm-config.json
  2. If missing, runs interactive mission setup
  3. Tests LLM connectivity for every bot (live table)
  4. If any fail, offers reconfigure or retry
  5. Shows summary, waits for confirmation
  6. Does NOT proceed until all checks pass or user exits
"""

import asyncio
import argparse
import json
import re
import shutil
from pathlib import Path
from datetime import datetime

from core.config import ConfigManager
from core.state import SwarmState
from graph import compile_graph


def _clean_engagement_dir(engagement_dir: Path) -> None:
    """Remove all contents of the engagement directory for a fresh run.

    Keeps the directory itself, recreates standard subdirs.
    """
    if engagement_dir.exists():
        for item in engagement_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    else:
        engagement_dir.mkdir(parents=True, exist_ok=True)
    # Recreate standard subdirectories
    (engagement_dir / "raw").mkdir(exist_ok=True)
    (engagement_dir / "report").mkdir(exist_ok=True)
    (engagement_dir / "poc").mkdir(exist_ok=True)
    (engagement_dir / "findings").mkdir(exist_ok=True)


def parse_scope_from_mission(mission_path: Path) -> str:
    """Extract the target scope from mission.md."""
    if not mission_path.exists():
        return ""
    content = mission_path.read_text()
    # Find Scope section
    scope_match = re.search(r'## Scope\s*\n(.+?)(?=\n##|\Z)', content, re.DOTALL)
    if scope_match:
        scope_text = scope_match.group(1).strip()
        # Parse all targets from the scope section — one per line, comma-separated
        # v2.1: Previously only read the first line, missing additional scope targets
        targets = []
        for line in scope_text.split('\n'):
            line = line.strip()
            if not line or line.startswith('-'):
                line = line.lstrip('-').strip()
            if not line:
                continue
            # Handle comma-separated targets on a single line
            for token in line.split(','):
                token = token.strip()
                if token:
                    targets.append(token)
        if targets:
            return ', '.join(targets)
        # Fallback: extract first IP or domain
        ip_match = re.search(r'\d+\.\d+\.\d+\.\d+(/\d+)?', scope_text)
        if ip_match:
            return ip_match.group(0)
        return scope_text.split('\n')[0]
    return ""


async def run_operation(mission_dir: Path, swarm_config: dict, auto_approve: bool = False, resume: bool = False) -> SwarmState:
    """Execute a full Chimeras operation.

    v2.5: --resume now loads graph state from checkpoint.json instead of
    just preserving engagement files. The graph continues from the last
    completed phase, not from scratch.
    """
    from core.checkpoint import load_checkpoint

    engagement_dir = mission_dir / "engagement"
    mission_path = mission_dir / "mission.md"

    # v2.1: Clean engagement dir for fresh run unless --resume is specified
    # Previous runs leave stale files that poison WarChief's context
    if not resume:
        _clean_engagement_dir(engagement_dir)

    # v2.5: Try to load checkpoint if resuming
    saved_state = None
    if resume:
        saved_state = load_checkpoint(engagement_dir)
        if saved_state:
            print(f"[RESUME] Loaded checkpoint from {engagement_dir / 'checkpoint.json'}")
            print(f"[RESUME] Continuing from phase: {saved_state.get('mission_state', 'unknown')}")
        else:
            print("[RESUME] No checkpoint found — starting fresh")

    # Parse scope from mission file
    target_scope = parse_scope_from_mission(mission_path)

    # Initialize state — v2 fields included
    # v2 Phase 3: Extract internal scope from config for lateral movement
    internal_scope = swarm_config.get("internal_scope", "")
    lateral_objectives = swarm_config.get("lateral_objectives", "")

    state = SwarmState(
        mission={
            "name": swarm_config.get("mission_name", "unnamed"),
            "path": str(mission_path),
            "created": swarm_config.get("created"),
            "scope": target_scope,
            "target": target_scope.split("/")[0] if target_scope else "",
            "lateral_objectives": lateral_objectives,
        },
        swarm_config=swarm_config,
        human_approval=auto_approve,          # v2.5: set from auto_approve so --resume with --approve works
        lateral_approval=auto_approve,        # v2.5: same
        abort_flag=False,
        engagement_dir=str(engagement_dir),
        # v2: initialize new state fields
        last_decision="",
        loop_count={},
        max_loops_per_phase=5,        # v2: per-phase, not global
        discovered_targets=[],
        # v2.1: Parse scope string into individual targets for external_targets
        external_targets=[t.strip() for t in target_scope.split(',') if t.strip()] if target_scope else [],
        internal_targets=[],
        exploited_hosts=[],
        target_context="external",    # v2: start in external scope
        target_artifacts=[],           # v2: for Phase 4.5 cleanup
        failed_vectors=[],            # v2: for Phase 4 resilience
        aggressiveness="cautious",     # v2: default to cautious
        # v2 Phase 2: decision logic state
        decision_history=[],            # Rolling window of last 5 decisions
        mission_state="init",           # State machine position
        scope_exhausted=False,          # Set when recon finds zero new targets
        confidence_threshold=0.6,       # Minimum confidence for routing
        # v2.1: Scope expansion
        scope_expansion_candidates=[],
        approved_extra_targets=[],
        # v3.0: Docker sandboxing
        enable_docker=swarm_config.get("enable_docker", False),
    )

    # v2.5: Override with saved state if resuming from checkpoint
    if saved_state:
        for key, value in saved_state.items():
            if key not in ("swarm_config",):  # Don't override config — use the one passed in
                state[key] = value
        # Re-apply auto_approve in case --approve was passed with --resume
        if auto_approve:
            state["human_approval"] = True
            state["lateral_approval"] = True
        print(f"[RESUME] State restored: {len(saved_state)} keys loaded")
        print(f"[RESUME] Last phase: {state.get('mission_state', 'unknown')}")
        print(f"[RESUME] Last decision: {state.get('last_decision', 'unknown')}")

    # v2 Phase 3: Store internal scope in state for ToolExecutor target validation
    # ToolExecutor reads this when lateral_approval is granted
    if internal_scope:
        state["internal_scope"] = internal_scope

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
        description="Chimeras v2.0 - Autonomous AI Security Testing Swarm",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                          # TUI wizard (interactive setup + checks)
  python main.py setup --mission "Op Alpha" --objectives "Pentest web app" --scope "10.10.10.0/24" --roe "No DoS"
  python main.py run --mission-dir ./mission
  python main.py run --mission-dir ./mission --approve  # Headless auto-approve
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
    run_parser.add_argument("--approve", action="store_true", help="Auto-approve exploitation + lateral gates")
    run_parser.add_argument("--docker", action="store_true", help="Enable Docker sandboxing for tool execution (v3.0)")
    run_parser.add_argument("--resume", action="store_true",
                            help="Resume from existing engagement files (skip cleanup)")
    run_parser.add_argument("--skip-wizard", action="store_true",
                            help="Skip TUI wizard, use config as-is (for headless runs)")

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

        # v2: Run TUI wizard unless --skip-wizard is passed
        if not args.skip_wizard:
            from core.wizard import run_wizard
            verified_config = run_wizard(mission_dir)
            if verified_config is None:
                print("Exiting — wizard cancelled or checks failed.")
                return
            swarm_config = verified_config

        if args.docker:
            swarm_config["enable_docker"] = True
        asyncio.run(run_operation(mission_dir, swarm_config, args.approve, args.resume))

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
        # No subcommand — run TUI wizard
        from core.wizard import run_wizard

        config = run_wizard(Path("mission"))
        if config is None:
            print("Exiting.")
            return

        # If wizard completed, ask if they want to run now
        from rich.console import Console
        from rich.prompt import Confirm
        console = Console()
        console.print()
        if Confirm.ask("  Start the operation now?", default=True):
            mission_dir = Path("mission")
            config_path = mission_dir / "swarm-config.json"
            if config_path.exists():
                asyncio.run(run_operation(mission_dir, config, auto_approve=False, resume=False))
            else:
                console.print("  [red]No mission directory found. Run 'python main.py setup' first.[/red]")


if __name__ == "__main__":
    main()