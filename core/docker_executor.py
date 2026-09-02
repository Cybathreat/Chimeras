"""
Chimeras v3.0 — Tiered Docker Sandbox Executor

7-layer architecture (Council Session 20 consensus):
1. Tiered images — recon-slim, discovery-mid, full-exploit
2. Per-bot network policies — nftables rules from engagement scope
3. Kernel-level scope enforcement — iptables/nftables inside container
4. Evidence pipeline — hash-chained command log, court-admissible
5. Phase snapshots — overlayfs rollback on failure
6. Per-bot resource limits — right-sized per phase
7. Auto-expiry — container TTL

Image tiers:
- recon (chimeras-recon:latest) — ARIA. ~200MB. DNS + passive recon.
- scan (chimeras-scan:latest) — Lisa, Bloodhound, Wasp. ~400MB. Scanning + vuln detection.
- exploit (chimeras-exploit:latest) — Marksman, Magician, Thief. ~1.2GB. Full toolset.

Container lifecycle:
- Persistent per engagement (fast — no startup per command)
- Commands run via docker exec
- Evidence auto-captured per command
- Snapshot before each phase
- Auto-destroy on TTL expiry
"""

import hashlib
import json
import logging
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# ============================================================
# LIVE EXECUTOR REGISTRY — WarChief pushes scope to running containers
# ============================================================
# Every TieredDockerExecutor with a running container registers itself.
# When WarChief expands scope (scope_change decision), the swarm calls
# expand_all_scopes() and every LIVE bot container's kernel firewall is
# updated instantly — no restart, no stale firewalls.
_LIVE_EXECUTORS: List["TieredDockerExecutor"] = []


def expand_all_scopes(new_ips: str, new_domains: str = "") -> Dict[str, bool]:
    """Push a scope expansion to every running bot container.
    
    Called by the swarm orchestrator after WarChief's scope_change
    decision passes validation. Returns per-bot success map.
    """
    results: Dict[str, bool] = {}
    for ex in list(_LIVE_EXECUTORS):
        try:
            results[ex.bot_name] = ex.expand_scope(new_ips, new_domains)
        except Exception as e:
            logger.error(f"[{ex.bot_name}] expand_all_scopes error: {e}")
            results[ex.bot_name] = False
    if results:
        logger.info(f"Scope expansion propagated to {len(results)} live containers")
    return results


def live_containers() -> List[str]:
    """Names of bots with running containers."""
    return [ex.bot_name for ex in _LIVE_EXECUTORS if ex._container_name]


# ============================================================
# IMAGE-SIDE TOOL DISCOVERY
# ============================================================
# The LLM can only pick tools it can see. With Docker mode, tools live in
# the tier image, NOT on the host — shutil.which() on the host showed bots
# "not installed: msfconsole, ffuf, masscan" while those tools sat unused
# inside their own containers. This discovers tools the way the bot will
# actually run them.

_IMAGE_TOOLS_CACHE: Dict[str, frozenset] = {}


def discover_image_tools(image: str, candidate_tools: Optional[set] = None) -> frozenset:
    """Discover which candidate tools exist inside a tier image.

    Runs one shell loop inside a throwaway container. Cached per image —
    images are immutable between builds, so this is stable.
    """
    if image in _IMAGE_TOOLS_CACHE:
        return _IMAGE_TOOLS_CACHE[image]

    if candidate_tools is None:
        from core.scope import TOOL_CATEGORIES
        candidate_tools = set()
        for tools in TOOL_CATEGORIES.values():
            candidate_tools.update(tools)

    if not candidate_tools:
        return frozenset()

    tool_list = " ".join(sorted(candidate_tools))
    probe = (
        f"for t in {tool_list}; do "
        f"command -v \"$t\" >/dev/null 2>&1 && echo \"$t\"; done"
    )
    try:
        result = subprocess.run(
            ["docker", "run", "--rm", "--entrypoint", "sh", image, "-c", probe],
            capture_output=True, text=True, timeout=60,
        )
        found = frozenset(line.strip() for line in result.stdout.splitlines() if line.strip())
    except Exception as e:
        logger.error(f"Image tool discovery failed for {image}: {e}")
        found = frozenset()

    _IMAGE_TOOLS_CACHE[image] = found
    return found

# ============================================================
# TIERED IMAGE MAPPING — bot → image tier
# ============================================================
BOT_TIER = {
    "aria":         "recon",
    "lisa":         "scan",
    "bloodhound":   "scan",
    "wasp":         "scan",
    "marksman":     "exploit",
    "magician":     "exploit",
    "thief":        "exploit",
    "bookkeeper":   "recon",  # no tools needed, lightweight
    "warchief":     "recon",  # no tools needed, lightweight
}

IMAGE_NAMES = {
    "recon":   "chimeras-recon:latest",
    "scan":    "chimeras-scan:latest",
    "exploit": "chimeras-exploit:latest",
}

# ============================================================
# PER-BOT RESOURCE LIMITS
# ============================================================
BOT_RESOURCES = {
    "aria":         {"cpus": "0.5", "memory": "256m", "pids": "50"},
    "lisa":         {"cpus": "1.0", "memory": "512m", "pids": "100"},
    "bloodhound":   {"cpus": "1.0", "memory": "512m", "pids": "100"},
    "wasp":         {"cpus": "1.0", "memory": "512m", "pids": "100"},
    "marksman":     {"cpus": "2.0", "memory": "2g",   "pids": "200"},
    "magician":     {"cpus": "1.0", "memory": "512m", "pids": "100"},
    "thief":        {"cpus": "1.0", "memory": "512m", "pids": "100"},
    "bookkeeper":   {"cpus": "0.5", "memory": "256m", "pids": "50"},
    "warchief":     {"cpus": "0.5", "memory": "256m", "pids": "50"},
}

# Per-bot Linux capabilities (least privilege)
BOT_CAPABILITIES = {
    "aria":         ["NET_RAW"],           # DNS resolution
    "lisa":         ["NET_RAW", "NET_ADMIN"],  # nmap SYN scans
    "bloodhound":   ["NET_RAW"],           # vuln scanning
    "wasp":         [],                    # HTTP only, no raw sockets
    "marksman":     ["NET_RAW", "NET_ADMIN"],  # exploitation, reverse shells
    "magician":     [],                    # local privesc, no network
    "thief":        ["NET_RAW"],           # exfiltration
    "bookkeeper":   [],                    # no tools
    "warchief":     [],                    # no tools
}

# Per-bot network port profiles (host-side nftables injection)
# "restricted"  — scoped IPs only, no extra ports
# "web_only"    — scoped IPs + standard web ports
# "full"        — scoped IPs, all ports
BOT_NET_PROFILE = {
    "aria":         "web_only",
    "lisa":         "restricted",
    "bloodhound":   "restricted",
    "wasp":         "web_only",
    "marksman":     "full",
    "magician":     "restricted",
    "thief":        "full",
    "bookkeeper":   "restricted",
    "warchief":     "restricted",
}


def _docker_available() -> bool:
    """Check if Docker daemon is running and accessible."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _image_exists(image: str) -> bool:
    """Check if a Docker image exists locally."""
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def build_images() -> Dict[str, bool]:
    """Build all tiered Docker images. Returns dict of tier → success.
    
    Build context is the docker/ directory (entrypoint.sh lives there);
    each tier's Dockerfile is selected via -f.
    """
    results = {}
    docker_dir = Path(__file__).parent.parent / "docker"
    
    for tier, image_name in IMAGE_NAMES.items():
        dockerfile = docker_dir / tier / "Dockerfile"
        if not dockerfile.exists():
            logger.warning(f"Tier Dockerfile not found: {dockerfile}")
            results[tier] = False
            continue
        
        logger.info(f"Building {image_name} (context={docker_dir}, file={dockerfile})")
        try:
            result = subprocess.run(
                ["docker", "build", "-f", str(dockerfile), "-t", image_name, str(docker_dir)],
                capture_output=True, text=True, timeout=1800,
            )
            results[tier] = result.returncode == 0
            if results[tier]:
                logger.info(f"Built {image_name}")
            else:
                logger.error(f"Build failed for {image_name}: {result.stderr[-500:]}")
        except Exception as e:
            logger.error(f"Build error for {image_name}: {e}")
            results[tier] = False
    
    return results


class TieredDockerExecutor:
    """Executes tools inside tiered Docker containers with per-bot isolation.
    
    Architecture:
    - One persistent container per bot per engagement
    - Commands run via docker exec (fast — no container startup per command)
    - Kernel-level scope enforcement via nftables in entrypoint
    - Evidence pipeline: every command hash-chained
    - Phase snapshots: overlayfs rollback on failure
    - Per-bot resource limits and capabilities
    - Auto-expiry TTL
    """
    
    def __init__(
        self,
        bot_name: str,
        engagement_dir: str,
        mission_scope: str = "",
        mission_domains: str = "",
        ttl: int = 3600,
    ):
        self.bot_name = bot_name
        self.engagement_dir = engagement_dir
        self.mission_scope = mission_scope
        self.mission_domains = mission_domains
        self.ttl = ttl
        
        # Docker volume mounts need ABSOLUTE paths — resolve early,
        # refuse to operate on relative paths (they'd create bogus volumes)
        eng_path = Path(engagement_dir)
        if not eng_path.is_absolute():
            eng_path = (Path.cwd() / eng_path).resolve()
        self.engagement_dir = str(eng_path)
        self.mission_scope = mission_scope
        self.mission_domains = mission_domains
        
        self.tier = BOT_TIER.get(bot_name, "exploit")
        self.image = IMAGE_NAMES.get(self.tier, IMAGE_NAMES["exploit"])
        self.resources = BOT_RESOURCES.get(bot_name, BOT_RESOURCES["marksman"])
        self.capabilities = BOT_CAPABILITIES.get(bot_name, [])
        
        self._container_name: Optional[str] = None
        self._evidence_dir = Path(engagement_dir) / "evidence"
        self._evidence_dir.mkdir(parents=True, exist_ok=True)
        self._evidence_log = self._evidence_dir / f"evidence_{bot_name}.jsonl"
        self._prev_hash = "genesis"
        self._load_prev_hash()
    
    def _load_prev_hash(self) -> None:
        """Load the previous hash from the evidence chain."""
        hash_file = self._evidence_dir / f".hash_{self.bot_name}"
        if hash_file.exists():
            self._prev_hash = hash_file.read_text().strip()
    
    def _save_hash(self, hash_val: str) -> None:
        """Save the current hash for the next entry."""
        hash_file = self._evidence_dir / f".hash_{self.bot_name}"
        hash_file.write_text(hash_val)
        self._prev_hash = hash_val
    
    def _append_evidence(self, entry: Dict[str, Any]) -> str:
        """Append an entry to the hash-chained evidence log.
        
        Each entry includes a hash of the previous entry, creating a
        tamper-evident chain. Returns the new hash.
        """
        entry["prev_hash"] = self._prev_hash
        entry_str = json.dumps(entry, sort_keys=True)
        new_hash = hashlib.sha256(entry_str.encode()).hexdigest()
        entry["hash"] = new_hash
        
        with open(self._evidence_log, "a") as f:
            f.write(json.dumps(entry) + "\n")
        
        self._save_hash(new_hash)
        return new_hash
    
    def _ensure_container(self) -> str:
        """Start a persistent container for this bot if not already running."""
        if self._container_name and self._container_running(self._container_name):
            return self._container_name
        
        # v3.0 fix: ORPHAN PREVENTION — one container per bot. If a previous
        # run/re-dispatch left a container with our deterministic name alive,
        # adopt it instead of spawning another (each re-dispatch would leak).
        canonical_name = f"chimeras-{self.bot_name}-{self._engagement_tag()}"
        if self._container_running(canonical_name):
            logger.info(f"[{self.bot_name}] Adopting existing container: {canonical_name}")
            self._container_name = canonical_name
            return canonical_name
        
        container_name = canonical_name
        
        # Build docker run command with per-bot configuration
        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "--rm",
            # Resource limits (per bot)
            "--cpus", self.resources["cpus"],
            "--memory", self.resources["memory"],
            "--pids-limit", self.resources["pids"],
            # Security: drop all caps, add only what this bot needs
            "--cap-drop", "ALL",
        ]
        
        for cap in self.capabilities:
            cmd.extend(["--cap-add", cap])
        
        # Read-only root filesystem (defense in depth)
        # NOTE: no tmpfs on /root — it MASKS image content (nuclei templates
        # broke this way). Read-only rootfs already makes /root immutable.
        cmd.extend([
            "--read-only",
            "--tmpfs", "/tmp:rw,size=256m",
        ])
        
        # Mount engagement directory for evidence and findings
        cmd.extend([
            "-v", f"{self.engagement_dir}:/engagement:rw",
            "-v", f"{self._evidence_dir}:/evidence:rw",
        ])
        
        # Environment variables for entrypoint
        env = {
            "CHIMERAS_BOT_NAME": self.bot_name,
            "CHIMERAS_SCOPE_IPS": self.mission_scope,
            "CHIMERAS_SCOPE_DOMAINS": self.mission_domains,
            "CHIMERAS_EVIDENCE_DIR": "/evidence",
            "CHIMERAS_TTL": str(self.ttl),
        }
        for k, v in env.items():
            cmd.extend(["-e", f"{k}={v}"])
        
        # Log rotation (prevent disk fill)
        cmd.extend([
            "--log-driver", "json-file",
            "--log-opt", "max-size=50m",
            "--log-opt", "max-file=3",
        ])
        
        # Network: bridge (entrypoint handles nftables scope enforcement)
        cmd.extend(["--network", "bridge"])
        
        cmd.append(self.image)
        
        logger.info(f"[{self.bot_name}] Starting container: {container_name} (tier={self.tier})")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.error(f"Container start failed: {result.stderr}")
                raise RuntimeError(f"Docker container start failed: {result.stderr}")
            
            self._container_name = container_name
            
            # Register in live-executor registry (WarChief scope propagation)
            if self not in _LIVE_EXECUTORS:
                _LIVE_EXECUTORS.append(self)
            
            # Host-side firewall injection (container has no NET_ADMIN — cannot self-modify)
            if self._inject_firewall():
                self._append_evidence({
                    "event": "firewall_injected",
                    "bot": self.bot_name,
                    "profile": BOT_NET_PROFILE.get(self.bot_name, "restricted"),
                    "scope": self.mission_scope,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            else:
                logger.warning(f"[{self.bot_name}] Firewall injection failed — container is UNPROTECTED, killing it")
                try:
                    subprocess.run(["docker", "kill", container_name], capture_output=True, timeout=15)
                except Exception:
                    pass
                self._container_name = None
                raise RuntimeError("Refusing to run unprotected container: firewall injection failed")
            
            # Wait for entrypoint to complete
            time.sleep(2)
            
            # Log container start to evidence chain
            self._append_evidence({
                "event": "container_start",
                "bot": self.bot_name,
                "tier": self.tier,
                "image": self.image,
                "container": container_name,
                "resources": self.resources,
                "capabilities": self.capabilities,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            
            return container_name
        except Exception as e:
            logger.error(f"Container start error: {e}")
            raise
    
    def _engagement_tag(self) -> str:
        """Deterministic short tag from the engagement path — same engagement,
        same container name, so re-dispatches adopt instead of orphaning."""
        return hashlib.sha256(self.engagement_dir.encode()).hexdigest()[:8]
    
    def _container_running(self, name: str) -> bool:
        """Check if a container is running."""
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", name],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0 and "true" in result.stdout
        except Exception:
            return False
    
    def run(self, command: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """Execute a command inside the bot's container.
        
        Returns same dict format as ToolExecutor.run():
            {
                "command": str,
                "exit_code": int,
                "stdout": str,
                "stderr": str,
                "success": bool,
                "containerized": True,
                "evidence_hash": str
            }
        """
        t = timeout or 180
        container = self._ensure_container()
        ts = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"[{self.bot_name}] EXEC: {command[:100]}")
        
        # Run via docker exec
        exec_cmd = [
            "docker", "exec",
            container,
            "bash", "-c", command,
        ]
        
        start_time = time.time()
        try:
            result = subprocess.run(
                exec_cmd,
                capture_output=True,
                text=True,
                timeout=t,
            )
            elapsed = time.time() - start_time
            success = result.returncode == 0
            
            # Capture evidence
            evidence_hash = self._append_evidence({
                "event": "command_exec",
                "bot": self.bot_name,
                "command": command,
                "exit_code": result.returncode,
                "stdout_len": len(result.stdout),
                "stderr_len": len(result.stderr),
                "duration_sec": round(elapsed, 2),
                "success": success,
                "timestamp": ts,
            })
            
            return {
                "command": command,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration_sec": round(elapsed, 2),
                "success": success,
                "containerized": True,
                "evidence_hash": evidence_hash,
            }
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            evidence_hash = self._append_evidence({
                "event": "command_timeout",
                "bot": self.bot_name,
                "command": command,
                "timeout_sec": t,
                "timestamp": ts,
            })
            return {
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {t}s",
                "duration_sec": elapsed,
                "success": False,
                "containerized": True,
                "evidence_hash": evidence_hash,
            }
        except Exception as e:
            elapsed = time.time() - start_time
            evidence_hash = self._append_evidence({
                "event": "command_error",
                "bot": self.bot_name,
                "command": command,
                "error": str(e),
                "timestamp": ts,
            })
            return {
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Docker exec error: {e}",
                "duration_sec": elapsed,
                "success": False,
                "containerized": True,
                "evidence_hash": evidence_hash,
            }
    
    def run_batch(self, commands: List[str], timeout: Optional[int] = None) -> List[Dict[str, Any]]:
        """Execute multiple commands sequentially in the same container."""
        return [self.run(cmd, timeout=timeout) for cmd in commands]
    
    def snapshot(self, label: str = "") -> str:
        """Snapshot the container's writable layer for rollback.
        
        Uses docker commit to create an image of the current state.
        Returns the snapshot image ID.
        """
        if not self._container_name:
            return ""
        
        snapshot_name = f"chimeras-snap-{self.bot_name}-{label or uuid.uuid4().hex[:8]}"
        try:
            result = subprocess.run(
                ["docker", "commit", self._container_name, snapshot_name],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                self._append_evidence({
                    "event": "snapshot",
                    "bot": self.bot_name,
                    "snapshot": snapshot_name,
                    "label": label,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                logger.info(f"[{self.bot_name}] Snapshot: {snapshot_name}")
                return snapshot_name
        except Exception as e:
            logger.error(f"Snapshot failed: {e}")
        return ""
    
    def rollback(self, snapshot_name: str) -> bool:
        """Rollback the container to a previous snapshot."""
        if not snapshot_name:
            return False
        
        try:
            # Stop current container
            self.cleanup()
            
            # Start new container from snapshot
            self._container_name = None
            # Override image with snapshot
            original_image = self.image
            self.image = snapshot_name
            self._ensure_container()
            self.image = original_image
            
            self._append_evidence({
                "event": "rollback",
                "bot": self.bot_name,
                "snapshot": snapshot_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            
            logger.info(f"[{self.bot_name}] Rolled back to {snapshot_name}")
            return True
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
    
    def cleanup(self) -> None:
        """Stop and remove the container."""
        if self._container_name:
            # Unregister from live-executor registry
            try:
                _LIVE_EXECUTORS.remove(self)
            except ValueError:
                pass
            try:
                subprocess.run(
                    ["docker", "stop", self._container_name],
                    capture_output=True, text=True, timeout=10,
                )
            except Exception:
                pass
            self._append_evidence({
                "event": "container_stop",
                "bot": self.bot_name,
                "container": self._container_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            self._container_name = None
    
    def _inject_firewall(self) -> bool:
        """Inject nftables scope rules from the HOST into the container's
        network namespace via nsenter. Container has no NET_ADMIN, so a
        compromised bot cannot tamper with its own firewall.
        
        Drops all outbound traffic except:
        - loopback, established/related
        - DNS (UDP/TCP 53), NTP (123)
        - explicitly scoped IPs
        Plus per-bot port profiles (ARIA: 80/443 only, etc.)
        """
        if not self._container_name:
            return False
        
        pid = self._container_pid()
        if not pid:
            logger.error(f"[{self.bot_name}] Cannot get container PID for firewall injection")
            return False
        
        # Build the nftables program
        rules = [
            "add table inet chimeras_scope",
            "flush table inet chimeras_scope",
            "add chain inet chimeras_scope output { type filter hook output priority 0; policy drop; }",
            "add rule inet chimeras_scope output oif lo accept",
            "add rule inet chimeras_scope output ct state established,related accept",
            "add rule inet chimeras_scope output udp dport 53 accept",
            "add rule inet chimeras_scope output tcp dport 53 accept",
            "add rule inet chimeras_scope output udp dport 123 accept",
        ]
        
        # Scoped IPs — the ONLY destinations allowed (all ports for "full" profile)
        scoped_raw = [i.strip() for i in self.mission_scope.split(",") if i.strip()] if self.mission_scope else []
        
        # Resolve scoped DOMAINS to their current IPs (CDN rotation aware).
        # A domain in scope means ALL its current IPs are in scope.
        import socket
        scoped_v4 = []
        scoped_v6 = []
        for entry in scoped_raw:
            is_ip = entry.replace(".", "").replace(":", "").isdigit() or "/" in entry
            if is_ip:
                scoped_v4.append(entry)  # CIDR or plain IP
                continue
            try:
                infos = socket.getaddrinfo(entry, None)
                for ai in infos:
                    ip = ai[4][0]
                    if ":" in ip:
                        if ip not in scoped_v6:
                            scoped_v6.append(ip)
                    elif ip not in scoped_v4:
                        scoped_v4.append(ip)
                logger.info(f"[{self.bot_name}] Scope domain {entry} -> {len(set([ai[4][0] for ai in infos]))} IPs")
            except Exception as e:
                logger.warning(f"[{self.bot_name}] Could not resolve scoped domain {entry}: {e}")
        
        for ip in scoped_v4:
            rules.append(f"add rule inet chimeras_scope output ip daddr {ip} accept")
        for ip6 in scoped_v6:
            rules.append(f"add rule inet chimeras_scope output ip6 daddr {ip6} accept")
        
        # Per-bot port profile — web ports only to SCOPED IPs, never to arbitrary hosts
        profile = BOT_NET_PROFILE.get(self.bot_name, "restricted")
        if profile == "web_only":
            # Web ports to scoped IPs (v4). IPv6 covered by full-allow rules above.
            for ip in scoped_v4:
                if "/" not in ip:
                    rules.append(f"add rule inet chimeras_scope output ip daddr {ip} tcp dport {{ 80, 443, 8080, 8443 }} accept")
            # NO blanket web egress — that defeats IP scoping.
            # Out-of-scope OSINT lookups go through the HOST's web_search tool instead.
        
        nft_prog = "; ".join(rules)
        
        try:
            result = subprocess.run(
                ["nsenter", "-t", str(pid), "-n", "nft", "-f", "-"],
                input=nft_prog, capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                logger.info(f"[{self.bot_name}] Host-side firewall injected into container netns (pid={pid})")
                return True
            logger.error(f"[{self.bot_name}] Firewall injection failed: {result.stderr}")
        except Exception as e:
            logger.error(f"[{self.bot_name}] Firewall injection error: {e}")
        return False
    
    def _container_pid(self) -> Optional[int]:
        """Get the host-visible PID of the container's init process."""
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Pid}}", self._container_name],
                capture_output=True, text=True, timeout=5,
            )
            pid = int(result.stdout.strip())
            return pid if pid > 0 else None
        except Exception:
            return None
    
    def _log(self, msg: str) -> None:
        """Log a message (used by expand_scope)."""
        logger.info(msg)
    
    def expand_scope(self, new_ips: str, new_domains: str = "") -> bool:
        """Dynamically expand the nftables scope inside a running container.
        
        Called by WarChief when new hosts/IPs are discovered and approved.
        Adds new allow rules without restarting the container.
        
        Args:
            new_ips: comma-separated IPs/CIDRs to allow
            new_domains: comma-separated domains (resolved and added to /etc/hosts)
        
        Returns True if rules were updated successfully.
        """
        if not self._container_name or not self._container_running(self._container_name):
            logger.warning(f"[{self.bot_name}] Cannot expand scope — no running container")
            return False
        
        ts = datetime.now(timezone.utc).isoformat()
        added_ips = []
        added_domains = []
        
        # Add new IPs to nftables — HOST-side injection (container cannot self-modify)
        if new_ips:
            ips = [ip.strip() for ip in new_ips.split(",") if ip.strip()]
            pid = self._container_pid()
            if pid:
                for ip in ips:
                    try:
                        result = subprocess.run(
                            ["nsenter", "-t", str(pid), "-n", "nft",
                             "add", "rule", "inet", "chimeras_scope", "output",
                             "ip", "daddr", ip, "accept"],
                            capture_output=True, text=True, timeout=5,
                        )
                        if result.returncode == 0:
                            added_ips.append(ip)
                            self._log(f"Scope expanded: +{ip}")
                    except Exception as e:
                        logger.error(f"nftables rule add failed for {ip}: {e}")
        
        # Resolve and add new domains to /etc/hosts (resolve on HOST — container DNS is scope-limited)
        if new_domains:
            domains = [d.strip() for d in new_domains.split(",") if d.strip()]
            pid = self._container_pid()
            for domain in domains:
                try:
                    getent = subprocess.run(
                        ["getent", "hosts", domain],
                        capture_output=True, text=True, timeout=10,
                    )
                    host_ip = getent.stdout.split()[0] if getent.stdout.strip() else ""
                    if host_ip and pid:
                        # Add nftables allow rule for resolved IP
                        result = subprocess.run(
                            ["nsenter", "-t", str(pid), "-n", "nft",
                             "add", "rule", "inet", "chimeras_scope", "output",
                             "ip", "daddr", host_ip, "accept"],
                            capture_output=True, text=True, timeout=5,
                        )
                        if result.returncode == 0:
                            added_ips.append(host_ip)
                        # Pin in container /etc/hosts
                        subprocess.run(
                            ["docker", "exec", self._container_name,
                             "bash", "-c", f"echo '{host_ip} {domain}' >> /etc/hosts"],
                            capture_output=True, text=True, timeout=5,
                        )
                    added_domains.append(domain)
                    self._log(f"Scope expanded: +{domain} ({host_ip})")
                except Exception as e:
                    logger.error(f"Domain resolution failed for {domain}: {e}")
        
        # Log to evidence chain
        if added_ips or added_domains:
            self._append_evidence({
                "event": "scope_expansion",
                "bot": self.bot_name,
                "added_ips": added_ips,
                "added_domains": added_domains,
                "approved_by": "warchief",
                "timestamp": ts,
            })
            logger.info(f"[{self.bot_name}] Scope expanded: +{len(added_ips)} IPs, +{len(added_domains)} domains")
            return True
        return False
    
    def get_evidence_chain(self) -> List[Dict[str, Any]]:
        """Return the full evidence chain for this bot."""
        if not self._evidence_log.exists():
            return []
        entries = []
        for line in self._evidence_log.read_text().splitlines():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return entries