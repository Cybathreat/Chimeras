"""
Chimeras v2.3 — Tool Result Cache

Caches tool execution results by (target_hash, tool_name, args_hash).
Invalidated when WarChief changes scope (scope_version incremented).

Lisa's port scan feeds Bloodhound without re-execution. Saves ~30%
of tool executions on re-engagements. Compliance intact — WarChief
still reviews cached results, just doesn't wait for redundant runs.

Usage:
    from core.tool_cache import ToolCache

    cache = ToolCache(engagement_dir)
    cached = cache.get("nmap", "10.10.10.5", "-sV --top-ports 100")
    if cached:
        return cached  # skip execution
    result = executor.run(cmd)
    cache.put("nmap", "10.10.10.5", "-sV --top-ports 100", result)
"""

import json
import hashlib
import time
from pathlib import Path
from typing import Optional, Dict, Any


class ToolCache:
    """File-based tool result cache. Scope-invalidated."""

    DEFAULT_TTL = 3600  # 1 hour — engagement lifetime is typically < 30 min
    CACHE_DIR = "tool_cache"

    def __init__(self, engagement_dir: Optional[Path] = None,
                 scope_version: int = 0, ttl: int = DEFAULT_TTL):
        self.engagement_dir = Path(engagement_dir) if engagement_dir else Path("mission/engagement")
        self._cache_dir = self.engagement_dir / self.CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self.scope_version = scope_version
        self.ttl = ttl

    def _key(self, tool_name: str, target: str, args: str) -> str:
        """Generate cache key hash."""
        raw = f"{self.scope_version}:{tool_name}:{target}:{args}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def get(self, tool_name: str, target: str, args: str) -> Optional[Dict[str, Any]]:
        """Get cached result if exists and not expired."""
        try:
            key = self._key(tool_name, target, args)
            cache_file = self._cache_dir / f"{key}.json"
            if not cache_file.exists():
                return None
            with open(cache_file) as f:
                entry = json.load(f)
            # Check TTL
            if time.time() - entry.get("cached_at", 0) > self.ttl:
                return None  # expired
            # v2.3 fix: Return result WITH cached flag set on the result dict itself
            result = entry.get("result")
            if result and isinstance(result, dict):
                result["cached"] = True
            return result
        except Exception:
            return None  # cache miss on any error

    def put(self, tool_name: str, target: str, args: str,
            result: Dict[str, Any]) -> None:
        """Cache a tool result."""
        try:
            key = self._key(tool_name, target, args)
            cache_file = self._cache_dir / f"{key}.json"
            entry = {
                "cached_at": time.time(),
                "scope_version": self.scope_version,
                "tool": tool_name,
                "target": target,
                "result": result,
            }
            with open(cache_file, "w") as f:
                json.dump(entry, f)
        except Exception as e:
            print(f"[TOOL_CACHE] Failed to write: {e}")

    def invalidate_all(self) -> None:
        """Invalidate entire cache when scope changes."""
        try:
            for f in self._cache_dir.glob("*.json"):
                f.unlink()
        except Exception:
            pass

    def update_scope_version(self, new_version: int) -> None:
        """Update scope version — invalidates all cached entries."""
        if new_version != self.scope_version:
            self.scope_version = new_version
            self.invalidate_all()