"""
Chimeras v2.5 — File-based State Checkpointing

Saves graph state to engagement/checkpoint.json after each node execution.
On --resume, loads the last checkpoint and continues from the saved phase.

This is NOT a LangGraph checkpointer — it's a simpler approach that saves
the full state dict to a JSON file. The graph is re-compiled from scratch,
but the initial state is loaded from the checkpoint file.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


def save_checkpoint(engagement_dir: Path, state: Dict[str, Any]) -> None:
    """Save current graph state to checkpoint.json."""
    checkpoint_path = engagement_dir / "checkpoint.json"
    # Add metadata
    checkpoint = {
        "saved_at": datetime.utcnow().isoformat(),
        "mission_state": state.get("mission_state", "unknown"),
        "last_decision": state.get("last_decision", ""),
        "state": _serialize_state(state),
    }
    checkpoint_path.write_text(json.dumps(checkpoint, indent=2, default=str))
    print(f"[CHECKPOINT] State saved: phase={checkpoint['mission_state']}, decision={checkpoint['last_decision']}")


def load_checkpoint(engagement_dir: Path) -> Optional[Dict[str, Any]]:
    """Load state from checkpoint.json. Returns None if no checkpoint exists."""
    checkpoint_path = engagement_dir / "checkpoint.json"
    if not checkpoint_path.exists():
        return None
    try:
        checkpoint = json.loads(checkpoint_path.read_text())
        state = checkpoint.get("state", {})
        print(f"[CHECKPOINT] Resumed from {checkpoint.get('saved_at', 'unknown')}")
        print(f"[CHECKPOINT] Phase: {checkpoint.get('mission_state', 'unknown')}, Decision: {checkpoint.get('last_decision', 'unknown')}")
        return state
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[CHECKPOINT] Failed to load checkpoint: {e}")
        return None


def _serialize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize state dict for JSON storage. Handles non-serializable types."""
    serializable = {}
    for key, value in state.items():
        try:
            # Test if it's JSON serializable
            json.dumps(value, default=str)
            serializable[key] = value
        except (TypeError, ValueError):
            # Convert non-serializable to string
            serializable[key] = str(value)
    return serializable