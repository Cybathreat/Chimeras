"""
Chimeras v2.0 — Abstract Base Bot

The LLM IS the brain. No hardcoded fallback.
Bots read engagement files, LLM decides what tools to run,
real tools execute, LLM analyzes output, findings written to files.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json
import re

from core.llm_router import LLMRouter
from core.tool_executor import ToolExecutor
from core.docker_executor import TieredDockerExecutor, _docker_available, build_images, IMAGE_NAMES
from core.scope import ScopeEnforcer
from core.state import SwarmState
from core.json_parser import parse_llm_json
from core.telemetry import Telemetry
from core.tool_cache import ToolCache
from core.critical_buffer import CriticalFindingsBuffer
from core.findings_store import FindingsStore
from core.schemas import validate_bot_output, BotDecision, BotAnalysis, compute_content_hash
from core.context_compaction import ContextCompactor


class BaseBot(ABC):
    """
    Abstract base class for all Chimeras agents.

    Execution loop:
    1. Wake — resolve engagement dir, read previous bot findings from files
    2. Think — LLM analyzes context, decides what tools to run (or skip)
    3. Execute — run real Kali tools via subprocess (scope-enforced)
    4. Analyze — LLM reads raw tool output, extracts structured findings
    5. Write — bot file, findings.md, log.md, PoC files
    6. Report — state update for graph flow
    """

    bot_name: str = "base"
    role_description: str = "Base bot role"
    scope_description: str = "No scope defined"

    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        self.state = state
        self.swarm_config = swarm_config or {}
        self._soul = self._load_soul()
        self.llm_router = self._init_router()
        # v2: Pass mission scope and bot name to ToolExecutor for target validation
        mission = state.get("mission", {})
        mission_scope = mission.get("scope", "")
        internal_scope = state.get("internal_scope", "")
        mission_roe = mission.get("roe", "")
        self.executor = ToolExecutor(
            timeout=180,
            workdir="/tmp",
            bot_name=self.bot_name,
            mission_scope=mission_scope,
            internal_scope=internal_scope,
            roe=mission_roe,
        )
        # v3.0: Tiered Docker sandbox — per-bot images, kernel scope enforcement, evidence chain
        self._enable_docker = self.state.get("enable_docker", False) or self.swarm_config.get("enable_docker", False)
        self.docker_executor: Optional[TieredDockerExecutor] = None
        self.engagement_dir: Optional[Path] = None
        self._resolve_engagement_dir()
        if self._enable_docker and _docker_available():
            # Parse scope IPs and domains for kernel-level enforcement
            scope_ips = mission_scope
            scope_domains = ""
            if mission_scope:
                # Extract domains from scope (non-IP entries)
                parts = [p.strip() for p in mission_scope.split(",")]
                domains = [p for p in parts if not p.replace(".", "").isdigit() and "/" not in p]
                scope_domains = ",".join(domains)
            
            self.docker_executor = TieredDockerExecutor(
                bot_name=self.bot_name,
                engagement_dir=str(self.engagement_dir.resolve()) if self.engagement_dir else "/tmp/chimeras-engagement",
                mission_scope=scope_ips,
                mission_domains=scope_domains,
            )
            self._log(f"Docker sandbox enabled — tier={self.docker_executor.tier}, image={self.docker_executor.image}", "DOCKER")
        elif self._enable_docker and not _docker_available():
            self._log("Docker enabled in config but daemon not available — falling back to host execution", "WARN")

        # v2.3: Telemetry, tool cache, critical findings buffer
        self.telemetry = Telemetry(self.engagement_dir)
        # v2.3 fix: Read scope_version from state so WarChief's invalidation propagates
        self.tool_cache = ToolCache(
            self.engagement_dir,
            scope_version=self.state.get("scope_version", 0)
        )
        self.critical_buffer = CriticalFindingsBuffer(self.engagement_dir)
        # v2.4: Lossless findings store — per-bot JSONL, never truncated
        self.findings_store = FindingsStore(self.engagement_dir)
        # v2.4: Verification cache — tracks which findings WarChief already verified
        # Feature-flag: default off until validated. Set via state.
        self._verification_cache: Dict[str, int] = {}  # content_hash → cycle_number
        self._enable_verification_cache = self.state.get("enable_verification_cache", False)

    def _load_soul(self) -> str:
        """Load soul.md from the bot's directory. Returns empty string if not found.

        soul.md defines the bot's identity, personality, behavioral constraints,
        and communication style. It is injected at the top of the system prompt,
        before role/scope/hint instructions. This externalizes bot identity from
        code — operators can tune behavior without editing agent.py.
        """
        try:
            # Find the bot's directory: look for soul.md relative to the agent module
            import inspect
            cls = type(self)
            module = inspect.getmodule(cls)
            if module and hasattr(module, "__file__") and module.__file__:
                bot_dir = Path(module.__file__).parent
                soul_path = bot_dir / "soul.md"
                if soul_path.exists():
                    return soul_path.read_text().strip()
        except Exception:
            pass
        return ""

    def _init_router(self) -> LLMRouter:
        return LLMRouter.from_config(self.bot_name, self.swarm_config)

    def _resolve_engagement_dir(self):
        eng = self.state.get("engagement_dir")
        if eng:
            self.engagement_dir = Path(eng)
            return
        mission_path = self.state.get("mission", {}).get("path", "")
        if mission_path:
            mission_dir = Path(mission_path).parent
            eng_dir = mission_dir / "engagement"
            if eng_dir.exists():
                self.engagement_dir = eng_dir
                return
        self.engagement_dir = Path("mission/engagement")

    # ─── Logging ───

    def _log(self, message: str, level: str = "INFO"):
        # v3.3: route to live TUI activity feed when active; else legacy print
        from core.live_ui import log as _ui_log
        if _ui_log(self.bot_name, level, message):
            return
        ts = datetime.utcnow().isoformat()
        print(f"[{ts}] [{self.bot_name.upper()}] [{level}] {message}", flush=True)

    def _banner(self):
        """Announce bot start (to TUI activity feed or console)."""
        scope = ScopeEnforcer.describe_scope(self.bot_name)
        self._log(f"{self.role_description} | scope: {scope}", "WAKE")

    # ─── LLM calls ───

    def _llm(self, prompt: str, system: Optional[str] = None, **kwargs) -> str:
        """Call LLM with retry + telemetry + truncation detection.

        v2.5: If response is truncated (finish_reason=length or truncation note),
        retry once with reduced context (strip raw tool output to summaries).
        """
        import inspect
        import time as _time

        start = _time.monotonic()
        attempt = 0
        max_attempts = 3
        base_delay = 2.0
        last_error = None
        truncated_at_least_once = False

        # v3.1: Proactive context compaction — compact before sending if over budget
        try:
            compactor = ContextCompactor()
            if compactor.should_compact(prompt):
                self._log("Proactive context compaction triggered", "COMPACT")
                prompt, compaction_stats = compactor.compact(prompt)
                if compaction_stats.get("compaction_needed"):
                    self._log(
                        f"Context compacted: {compaction_stats['original_tokens']}→"
                        f"{compaction_stats['compacted_tokens']} tokens, "
                        f"{compaction_stats['items_summarized']} items summarized",
                        "COMPACT"
                    )
        except Exception as e:
            # Compaction failure should never block the LLM call
            pass

        while attempt < max_attempts:
            attempt += 1
            try:
                result = self.llm_router.generate(prompt, system, **kwargs)
                if inspect.isawaitable(result):
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor() as pool:
                                future = pool.submit(lambda: asyncio.run(result))
                                result = future.result(timeout=300)
                        else:
                            result = asyncio.run(result)
                    except RuntimeError:
                        result = asyncio.run(result)

                # v2.5: Truncation detection — if truncated, retry with reduced context
                if "[NOTE: Response truncated" in result or "[NOTE: Response may have been truncated" in result:
                    truncated_at_least_once = True
                    if attempt < max_attempts:
                        self._log(f"LLM response truncated (attempt {attempt}/{max_attempts}) — retrying with reduced context", "TRUNC")
                        # Strip raw tool output sections to reduce input size
                        reduced_prompt = self._reduce_context_for_retry(prompt)
                        if reduced_prompt != prompt:
                            prompt = reduced_prompt
                            continue

                # v2.3: Telemetry
                duration = _time.monotonic() - start
                # v2.4: Record with provider/model info
                # v2.5: parse_ok=False if truncation was detected and never
                # fully resolved — the response may be incomplete even after
                # retries, so downstream JSON parsing may fail or use fallback.
                provider_name = getattr(self.llm_router, 'provider_name', 'unknown')
                model_name = getattr(self.llm_router, 'model', 'unknown')
                still_truncated = ("[NOTE: Response truncated" in result
                                   or "[NOTE: Response may have been truncated" in result)
                self.telemetry.record_llm_call(
                    self.bot_name, provider_name, model_name,
                    duration, parse_ok=not (truncated_at_least_once and still_truncated)
                )
                return result
            except (ValueError, TypeError, KeyError) as e:
                # Logic errors — don't retry
                duration = _time.monotonic() - start
                self.telemetry.record(
                    self.bot_name, "llm_call", self.state.get("mission_state", ""),
                    duration, success=False, error=str(e)
                )
                raise RuntimeError(f"LLM call failed for {self.bot_name}: {e}")
            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                retryable = any(k in error_msg for k in ("rate", "429", "timeout", "connection", "503", "502", "500", "overloaded", "reset"))
                if not retryable or attempt >= max_attempts:
                    duration = _time.monotonic() - start
                    self.telemetry.record(
                        self.bot_name, "llm_call", self.state.get("mission_state", ""),
                        duration, success=False, error=str(e)
                    )
                    raise RuntimeError(f"LLM call failed for {self.bot_name} after {attempt} attempts: {e}")
                delay = min(base_delay * (2 ** (attempt - 1)), 30.0)
                self._log(f"LLM retry {attempt}/{max_attempts} after {delay:.1f}s: {e}", "RETRY")
                _time.sleep(delay)

        # Should not reach here, but just in case
        raise RuntimeError(f"LLM call failed for {self.bot_name}: {last_error}")

    def _reduce_context_for_retry(self, prompt: str) -> str:
        """v2.5: Reduce prompt size by truncating raw tool output sections.

        When LLM response is truncated, the input is too large. This method
        strips raw tool output blocks (between ``` markers) to their first 200 chars,
        keeping the reasoning context but removing verbose raw output.
        """
        import re
        # Truncate code blocks (raw tool output) to first 200 chars
        def truncate_block(match):
            content = match.group(1)
            if len(content) > 200:
                return f"```\n{content[:200]}\n... (truncated for retry)\n```"
            return match.group(0)

        reduced = re.sub(r'```\n(.*?)```', truncate_block, prompt, flags=re.DOTALL)
        # Also truncate any line longer than 500 chars
        lines = reduced.split('\n')
        reduced_lines = []
        for line in lines:
            if len(line) > 500:
                reduced_lines.append(line[:500] + '... (truncated)')
            else:
                reduced_lines.append(line)
        return '\n'.join(reduced_lines)

    def _parse_json_response(self, response: str, schema=None) -> Dict[str, Any]:
        """Parse JSON from LLM response using v2.3 hardened parser.
        v2.4: Optional Pydantic schema validation via validate_bot_output.
        """
        try:
            data = parse_llm_json(response)
            if schema is not None:
                data = validate_bot_output(data, schema)
            return data
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"JSON parse error: {e}")

    def _mark_verified(self, tool_results: List[Dict[str, Any]], cycle_number: int) -> int:
        """v2.4: Mark tool results as verified by this cycle.
        Returns count of newly verified results (not previously cached).
        """
        newly_verified = 0
        for result in tool_results:
            if not isinstance(result, dict):
                continue
            content_hash = result.get("content_hash")
            if not content_hash:
                continue
            if content_hash not in self._verification_cache:
                self._verification_cache[content_hash] = cycle_number
                result["verified_by_cycle"] = cycle_number
                newly_verified += 1
            else:
                # Already verified — mark with the cached cycle
                result["verified_by_cycle"] = self._verification_cache[content_hash]
        return newly_verified

    def _is_verified(self, content_hash: str) -> bool:
        """v2.4: Check if a content hash has been verified before."""
        return content_hash in self._verification_cache

    # ─── Tool execution ───

    def _capture_scope_candidate(self, command: str, reason: str) -> None:
        """v2.1: Capture out-of-scope targets for scope expansion debrief.

        When a bot tries to target something outside the mission scope, extract
        the target from the reason string and add it to scope_expansion_candidates.
        WarChief will later debrief the user and ask whether to add them to scope.
        """
        try:
            import re as _re
            # Extract target from reason: "TARGET OUT OF SCOPE: hostname 'X' is not..."
            # or "TARGET OUT OF SCOPE: IP X is not..."
            host_match = _re.search(r"hostname '([^']+)'", reason)
            ip_match = _re.search(r"IP (\S+) is not", reason)

            target = None
            if host_match:
                target = host_match.group(1)
            elif ip_match:
                target = ip_match.group(1)

            if not target:
                return

            # Skip AWS metadata IPs, localhost — these are never scope candidates
            if target in ("169.254.169.254", "127.0.0.1", "localhost"):
                return
            # v2.3: Use stdlib ipaddress.is_private instead of hardcoded prefix list
            try:
                import ipaddress
                ip = ipaddress.ip_address(target)
                if ip.is_private or ip.is_loopback or ip.is_link_local:
                    return
            except ValueError:
                # Not an IP — could be a hostname, let it through
                pass

            candidates = self.state.get("scope_expansion_candidates", [])
            if not isinstance(candidates, list):
                candidates = []

            # Don't add duplicates
            existing_targets = {c.get("target") for c in candidates if isinstance(c, dict)}
            approved = set(self.state.get("approved_extra_targets", []))
            if target not in existing_targets and target not in approved:
                candidates.append({
                    "target": target,
                    "found_by": self.bot_name,
                    "command": command[:200],
                    "reason": reason,
                    "timestamp": datetime.utcnow().isoformat(),
                })
                self.state["scope_expansion_candidates"] = candidates
                self._log(f"Captured scope candidate: {target}", "SCOPE")
        except Exception as e:
            print(f"[{self.bot_name.upper()}] Scope candidate capture error: {e}")

    def _run_tool(self, command: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute a Kali tool. Scope-enforced. Real subprocess.
        v2.3: Tool result cache + telemetry.

        Returns tool result dict.
        """
        import time as _time
        start = _time.monotonic()

        # v2: Full scope enforcement with target validation
        mission = self.state.get("mission", {})
        mission_scope = mission.get("scope", "")
        # v2.1: Include approved extra targets in scope check
        approved_extra = self.state.get("approved_extra_targets", [])
        full_scope = mission_scope
        if approved_extra:
            full_scope = ", ".join([mission_scope] + approved_extra) if mission_scope else ", ".join(approved_extra)
        internal_scope = self.state.get("internal_scope", "")
        mission_roe = mission.get("roe", "")
        allowed, reason = ScopeEnforcer.check(
            self.bot_name, command,
            mission_scope=full_scope or None,
            internal_scope=internal_scope or None,
            roe=mission_roe or None,
        )
        if not allowed:
            self._log(f"SCOPE BLOCKED: {reason}", "SCOPE")
            # v2.1: Capture out-of-scope targets for scope expansion debrief
            if "TARGET OUT OF SCOPE" in reason:
                self._capture_scope_candidate(command, reason)
            self.telemetry.record(
                self.bot_name, "tool_exec", self.state.get("mission_state", ""),
                0, success=False, error=f"SCOPE BLOCKED: {reason}",
                extra={"command": command[:100]}
            )
            return {
                "command": command,
                "exit_code": -2,
                "stdout": "",
                "stderr": reason,
                "duration_sec": 0,
                "success": False,
                "scope_blocked": True,
            }

        # v2.3: Tool result cache check
        tool_name = command.split()[0].split("/")[-1] if command.split() else "unknown"
        target_str = full_scope or "unknown"
        cached = self.tool_cache.get(tool_name, target_str, command)
        if cached:
            self._log(f"CACHE HIT: {tool_name} (cached result)", "CACHE")
            cached["cached"] = True
            self.telemetry.record(
                self.bot_name, "tool_exec", self.state.get("mission_state", ""),
                _time.monotonic() - start, success=True,
                extra={"command": command[:100], "cached": True}
            )
            return cached

        self._log(f"EXEC: {command}", "EXEC")
        # v3.0: Route through Docker sandbox if enabled, else host execution
        if self.docker_executor is not None:
            self._log(f"DOCKER EXEC: {command[:80]}", "DOCKER")
            result = self.docker_executor.run(command, timeout=timeout)
        else:
            result = self.executor.run(command, timeout=timeout)

        # Save raw output to engagement folder
        raw_dir = self.engagement_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%H%M%S")
        raw_file = raw_dir / f"{self.bot_name}_{tool_name}_{ts}.txt"
        self.executor.save_output(result, raw_file)
        self._log(f"Output saved: {raw_file.name} ({result['duration_sec']}s)", "EXEC")

        # v2.3: Cache the result
        self.tool_cache.put(tool_name, target_str, command, result)

        # v2.4: Verification metadata — content_hash for WarChief verification cache
        stdout_text = result.get("stdout", "") or ""
        result["content_hash"] = compute_content_hash(stdout_text + command)
        result["tool_name"] = tool_name
        result["target"] = target_str
        result["verified_by_cycle"] = None  # set by WarChief after verification

        # v2.3: Telemetry
        self.telemetry.record(
            self.bot_name, "tool_exec", self.state.get("mission_state", ""),
            _time.monotonic() - start, success=result.get("success", True),
            extra={"command": command[:100], "tool": tool_name,
                   "exit_code": result.get("exit_code")}
        )

        return result

    # ─── Engagement file I/O ───

    @staticmethod
    def _sanitize_for_llm(text: str) -> str:
        """v2.3: Sanitize tool output before LLM re-ingestion.

        Strips prompt injection vectors from tool output that could
        cause the LLM to execute unintended commands:
        - Remove ANSI escape sequences (terminal control)
        - Remove null bytes
        - Remove common prompt injection patterns
        - Cap line length to prevent oversized injection payloads
        """
        if not text:
            return text
        import re as _re
        # Strip ANSI escape sequences
        text = _re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)
        # Strip null bytes
        text = text.replace('\x00', '')
        # Strip other control characters except newline/tab
        text = _re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f]', '', text)
        # Neutralize common prompt injection patterns from tool banners
        # e.g., "IGNORE PREVIOUS INSTRUCTIONS" or "```json" in tool output
        text = _re.sub(r'(?i)ignore\s+(previous|all|prior)\s+instructions?', '[SANITIZED]', text)
        text = _re.sub(r'(?i)disregard\s+(previous|all|prior)', '[SANITIZED]', text)
        text = _re.sub(r'(?i)you\s+are\s+now\s+a', '[SANITIZED]', text)
        text = _re.sub(r'(?i)system\s+prompt:', '[SANITIZED]', text)
        # Cap individual line length to prevent oversized payloads
        lines = text.split('\n')
        capped_lines = [line[:500] if len(line) > 500 else line for line in lines]
        return '\n'.join(capped_lines)

    def _read_file(self, filename: str) -> str:
        """Read an engagement file."""
        p = self.engagement_dir / filename
        return p.read_text() if p.exists() else ""

    def _read_findings(self) -> str:
        return self._read_file("findings.md")

    def _read_log(self) -> str:
        return self._read_file("log.md")

    def _read_plan(self) -> str:
        return self._read_file("plan.md")

    def _read_bot_file(self, bot_name: str) -> str:
        return self._read_file(f"{bot_name}.md")

    def _append_log(self, entry: str):
        import fcntl
        p = self.engagement_dir / "log.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a") as f:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            except (OSError, ImportError):
                pass  # fcntl not available on all platforms
            f.write(f"[{datetime.utcnow().isoformat()}] [{self.bot_name.upper()}] {entry}\n")

    def _append_findings(self, section: str, content: str):
        import fcntl
        p = self.engagement_dir / "findings.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a") as f:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            except (OSError, ImportError):
                pass
            f.write(f"\n### [{self.bot_name.upper()}] {section}\n\n{content}\n")

    def _write_bot_file(self, content: str):
        p = self.engagement_dir / f"{self.bot_name}.md"
        p.write_text(content)

    def _append_bot_file(self, content: str):
        p = self.engagement_dir / f"{self.bot_name}.md"
        with open(p, "a") as f:
            f.write(content)

    def _write_poc(self, name: str, content: str):
        d = self.engagement_dir / "poc"
        d.mkdir(exist_ok=True)
        (d / name).write_text(content)

    def _write_report(self, name: str, content: str):
        d = self.engagement_dir / "report"
        d.mkdir(exist_ok=True)
        (d / name).write_text(content)

    # ─── Context building ───

    def _build_context(self) -> str:
        """Build context string from engagement files for the LLM.

        v2 Phase 0: Context truncation via rolling digest.
        v2.3: Tool output sanitized before LLM re-ingestion to prevent
        prompt injection from tool banners/headers.
        """
        findings = self._read_findings()
        plan = self._read_plan()

        # v2.3: Sanitize findings — strip prompt injection vectors
        findings = self._sanitize_for_llm(findings)

        # v2: Rolling digest — truncate each source to recent content
        findings_digest = findings[-2000:] if len(findings) > 2000 else findings
        plan_digest = plan[-1500:] if len(plan) > 1500 else plan

        # Read other bot files — truncated to recent content
        bot_summaries = []
        for f in sorted(self.engagement_dir.glob("*.md")):
            if f.name in ("plan.md", "log.md", "findings.md", "warchief_decisions.log"):
                continue
            bname = f.stem
            if bname == self.bot_name:
                continue
            content = f.read_text()
            # Take last 500 chars — most recent findings from this bot
            if len(content) > 500:
                content = "...(earlier content truncated)...\n" + content[-500:]
            bot_summaries.append(f"### {bname}\n{content}")

        parts = []
        parts.append(f"## Target\n{self.state.get('mission', {}).get('target', 'N/A')}")
        parts.append(f"## Scope\n{self.state.get('mission', {}).get('scope', 'N/A')}")

        # v2: Include WarChief's last decision so downstream bots know the route
        last_decision = self.state.get("last_decision", "")
        if last_decision:
            parts.append(f"## WarChief's Last Decision: {last_decision}")
            # Include WarChief's reasoning if available
            warchief_report = self.state.get("reasoning_reports", {}).get("warchief", {})
            if warchief_report:
                wc_reasoning = warchief_report.get("reasoning", "")
                wc_assessment = warchief_report.get("assessment", "")
                if wc_reasoning:
                    parts.append(f"**Reasoning**: {wc_reasoning}")
                if wc_assessment:
                    parts.append(f"**Assessment**: {wc_assessment}")

        # v2: Include aggressiveness level
        aggressiveness = self.state.get("aggressiveness", "cautious")
        if aggressiveness != "cautious":
            parts.append(f"## Aggressiveness: {aggressiveness}")

        # v2: Include target context (external vs lateral)
        target_context = self.state.get("target_context", "external")
        if target_context == "lateral":
            parts.append("## Target Context: LATERAL (internal network — scope is different)")

        if findings_digest:
            parts.append(f"## Findings (recent)\n{findings_digest}")

        # v2.3: Critical findings buffer — never truncated
        critical = self.critical_buffer.format_for_context()
        if critical:
            parts.append(critical)

        if plan_digest:
            parts.append(f"## Plan (recent)\n{plan_digest}")
        if bot_summaries:
            parts.append(f"## Bot Reports\n{chr(10).join(bot_summaries)}")

        return "\n\n".join(parts)

    def _build_system_prompt(self) -> str:
        """Build the bot's system prompt with soul.md identity and scope enforcement.

        v2.3: System prompt is cached after first build. Only delta context
        (WarChief's last decision, aggressiveness) is injected per cycle.
        """
        # v2.3: Cache the static part of the system prompt
        if not hasattr(self, "_cached_static_prompt") or self._cached_static_prompt is None:
            self._cached_static_prompt = self._build_static_system_prompt()
        return self._cached_static_prompt

    def _build_static_system_prompt(self) -> str:
        """Build the static part of the system prompt. Called once, cached after.

        v3.0: Tries Jinja2 template first, falls back to f-string if template unavailable.
        """
        category = ScopeEnforcer.get_bot_category(self.bot_name)
        allowed_tools = sorted(ScopeEnforcer.get_allowed_tools(self.bot_name))
        # v3.0: With Docker mode, tools live in the bot's tier image —
        # discover them THERE, not on the host. The LLM must see the tools
        # it will actually be able to run.
        if self.docker_executor is not None:
            try:
                from core.docker_executor import discover_image_tools
                installed = discover_image_tools(self.docker_executor.image)
            except Exception:
                installed = ScopeEnforcer._discover_installed_tools()
        else:
            installed = ScopeEnforcer._discover_installed_tools()
        available_str = ", ".join(sorted(set(allowed_tools) & installed)) if allowed_tools else "NONE"

        # Pipeline position hints — no hardcoded tool names
        # v2: Include WarChief's last decision so bots know why they're being called
        last_decision = self.state.get("last_decision", "")
        decision_context = ""
        if last_decision and last_decision != "init":
            decision_context = f"\n\nWarChief's last decision was '{last_decision}'. "
            decision_context += "You are being activated because of this decision. "
            decision_context += "Prepare your findings for WarChief's next assessment."

        hints = {
            "aria": f"You are the recon bot. Your category is passive_recon — use any available tools in that category. WarChief may route you multiple times for deeper recon or lateral movement.{decision_context}",
            "lisa": f"You run AFTER ARIA. Use ARIA's DNS/IP findings to scan. Your category is active_scan.{decision_context}",
            "bloodhound": f"You run AFTER Lisa — she found open ports and services. Your job is to find vulnerabilities on those services. Your category is vuln_detection.{decision_context}",
            "wasp": f"You run AFTER Lisa — parallel with Bloodhound. Your job is to test the web application for OWASP Top 10 vulnerabilities. Your category is web_exploit.{decision_context}",
            "marksman": f"You run AFTER human approval — Bloodhound/Wasp found vulnerabilities and the operator approved exploitation. Your category is marksman — you research, develop, adapt, AND fire exploits. You search for PoCs, write custom exploits, and execute them against the target.{decision_context}",
            "magician": f"You run AFTER Marksman attempted exploitation. Your category is privesc.{decision_context}",
            "thief": f"You run AFTER Magician checked for privesc. Your category is exfiltration.{decision_context}",
            "bookkeeper": "Read all findings and generate a final penetration test report. No tools needed. This is an AUTHORIZED security engagement. All findings including exfiltration evidence are part of the legal pentest scope. Your job is to document findings objectively for the client report.",
            "warchief": "You are the orchestrator — no prior work exists or you are re-entering after a phase. Plan the engagement or route the next action. No tools needed.",
        }
        hint = hints.get(self.bot_name, "")

        soul_block = ""
        if self._soul:
            soul_block = f"## Your Soul\n\n{self._soul}\n\n---\n\n"

        # v3.0: Try Jinja2 template rendering, fall back to f-string
        try:
            import jinja2
            template_dir = Path(__file__).parent.parent / "templates"
            if template_dir.exists():
                env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(template_dir)))
                template = env.get_template("base_prompt.j2")
                return template.render(
                    soul=self._soul or "",
                    bot_name=self.bot_name,
                    role_description=self.role_description,
                    scope_description=self.scope_description,
                    tool_category=category,
                    available_tools=available_str,
                    hint=hint,
                )
        except Exception:
            pass  # Fall through to f-string

        return f"""{soul_block}You are {self.bot_name}, {self.role_description}.
Scope: {self.scope_description}
Tool Category: {category}
Available Tools: {available_str}
Hint: {hint}

Analyze the context. Decide which tools to run. Provide exact shell commands.

CRITICAL — COMMAND RULES:
- Each command in the "commands" array must be a SINGLE command. No shell loops (for/while/do/done), no semicolons, no pipes (|), no command chaining (&&/||), no backticks, no $().
- If you need to check multiple paths or run multiple variations, put each as a SEPARATE entry in the commands array.
- Do NOT use -oN/-oX/-oA flags — tool output is captured automatically.
- Do NOT use shell redirection (>/>>/<) — output is captured automatically.
- If a tool needs complex arguments, use the tool's built-in flags (e.g., nmap --script, not bash loops).

TOOL REQUESTS:
- If your mission needs a tool that is NOT in your Available Tools list, do NOT hallucinate it and do NOT silently degrade. File a request in the "tool_requests" array instead.
- Each request: tool (exact name), description (what it does), use_case (why THIS engagement needs it), arguments (typical invocation).
- Requests are logged to the engagement's tool_requests.csv and reviewed to improve the arsenal between engagements. A filed request is never wasted — it makes the next engagement stronger.
- You may still run your available commands while filing requests.

Respond ONLY with JSON:
```json
{{
  "needed": true,
  "strategy": "brief approach",
  "confidence": 0.9,
  "reasoning": "why",
  "commands": ["exact shell command 1", "exact shell command 2"],
  "tool_requests": [{{"tool": "name", "description": "...", "use_case": "...", "arguments": "..."}}],
  "skip_reason": "if not needed"
}}
```"""

    # ─── Main execution flow ───

    async def run(self) -> Dict[str, Any]:
        """Main bot execution flow. LLM decides everything."""
        self._banner()
        self._log("Bot awakened — reading engagement files", "WAKE")
        self._append_log("Bot awakened — starting reasoning phase")

        # Step 1: Build context from engagement files
        context = self._build_context()
        system = self._build_system_prompt()

        # Step 2: LLM decides what to do
        self._log("Asking LLM to decide strategy and tools...", "THINK")
        llm_response = self._llm(context, system, max_tokens=32768)
        self._log("LLM response received, parsing...", "THINK")

        # Print raw LLM reasoning to terminal (live streaming effect)
        print(f"\n[{self.bot_name.upper()} LLM REASONING]", flush=True)
        print(llm_response[:2000], flush=True)
        print(f"[/{self.bot_name.upper()} LLM REASONING]\n", flush=True)

        # Parse the decision
        try:
            decision = self._parse_json_response(llm_response)
        except ValueError as e:
            # v2 Phase -1: Safe fallback for malformed LLM output.
            # In v1, this crashed the bot with "FAILED" — acceptable when each
            # bot runs once. In v2, WarChief is invoked at 5-6 decision points
            # and every stage depends on it succeeding. A crash here is a
            # single point of failure for the entire engagement.
            #
            # Fallback: write a conservative decision that skips the bot and
            # lets the pipeline continue. This is safer than crashing because:
            #   - The bot's file gets a valid (if empty) entry
            #   - Downstream bots see the bot ran (even if it found nothing)
            #   - The graph doesn't stall waiting for a bot that died
            #   - WarChief (if this IS WarChief) produces a default "report" route
            self._log(f"LLM response unparseable: {e} — using safe fallback", "ERROR")
            self._append_log("WARNING: LLM response unparseable. Using safe fallback (conservative skip).")
            # v2.5: Record parse failure in telemetry so it shows up in
            # parse_failure_rate — previously this was invisible.
            self.telemetry.record_tool_exec(
                self.bot_name, "llm_parse", "",
                0.0, exit_code=-1, parse_ok=False,
            )
            self._write_bot_file(
                f"# {self.bot_name.upper()} — SAFE FALLBACK\n\n"
                "LLM response could not be parsed.\n"
                "Fallback: conservative skip (bot did not execute).\n"
                f"Error: {e}\n"
            )
            # Build a conservative fallback decision
            fallback_decision = {
                "needed": False,
                "strategy": "safe_fallback",
                "confidence": 0.0,
                "reasoning": f"LLM response unparseable — conservative skip. Error: {e}",
                "commands": [],
                "skip_reason": "LLM parse failure — safe fallback activated",
            }
            self.state.setdefault("reasoning_reports", {})[self.bot_name] = fallback_decision
            return {"reasoning": fallback_decision, "executed": False, "failed": True,
                    "fallback": True}

        needed = decision.get("needed", True)
        strategy = decision.get("strategy", "unknown")
        confidence = decision.get("confidence", 0.5)
        reasoning = decision.get("reasoning", "")
        commands = decision.get("commands", [])
        skip_reason = decision.get("skip_reason", "")
        tool_requests = decision.get("tool_requests", [])

        # v3.0.2: File tool requests — the arsenal improvement loop
        if tool_requests and isinstance(tool_requests, list):
            from core.tool_requests import log_tool_requests
            filed = log_tool_requests(
                bot_name=self.bot_name,
                requests=tool_requests,
                engagement_dir=str(self.engagement_dir) if self.engagement_dir else None,
                source="llm_request",
            )
            if filed:
                self._log(f"{filed} tool request(s) filed — see tool_requests.csv", "REQUEST")
                self._append_log(f"Tool requests filed: {[r.get('tool') for r in tool_requests]}")

        self._log(f"Decision: needed={needed}, strategy={strategy}, confidence={confidence}", "DECIDE")
        self._append_log(f"LLM decision: needed={needed}, strategy={strategy}, confidence={confidence}")
        self._append_log(f"Reasoning: {reasoning}")

        # Write initial bot file
        bot_header = f"""# {self.bot_name.upper()} — Work Log

Bot: {self.bot_name}
Role: {self.role_description}
Scope: {ScopeEnforcer.describe_scope(self.bot_name)}
Timestamp: {datetime.utcnow().isoformat()}

## LLM Reasoning

- Needed: {needed}
- Strategy: {strategy}
- Confidence: {confidence}
- Reasoning: {reasoning}
"""
        if not needed:
            bot_header += f"\n## Skipped\n\n{skip_reason}\n"
            self._write_bot_file(bot_header)
            self._append_log(f"Bot skipped — {skip_reason}")
            self._log(f"Bot not needed — {skip_reason}", "SKIP")
            self.state.setdefault("reasoning_reports", {})[self.bot_name] = decision
            return {"reasoning": decision, "executed": False}

        # Write bot file header
        bot_header += "\n## Tool Execution\n\n"
        self._write_bot_file(bot_header)

        # Step 3: Execute tools (scope-enforced)
        tool_results = []
        if commands:
            self._log(f"Executing {len(commands)} tool command(s)...", "EXEC")
            for cmd in commands:
                self._log(f"Running: {cmd}", "EXEC")
                result = self._run_tool(cmd, timeout=180)
                tool_results.append(result)

                # Append to bot file
                self._append_bot_file(f"### Command: {cmd}\n")
                self._append_bot_file(f"- Exit Code: {result.get('exit_code', 'N/A')}\n")
                self._append_bot_file(f"- Duration: {result.get('duration_sec', 0)}s\n")
                self._append_bot_file(f"- Success: {result.get('success', False)}\n\n")
                if result.get("scope_blocked"):
                    self._append_bot_file(f"- BLOCKED: {result.get('stderr', 'scope violation')}\n\n")
                else:
                    stdout_preview = (result.get("stdout") or "")[:500]
                    self._append_bot_file(f"```\n{stdout_preview}\n```\n\n")

                self._append_log(f"Tool: {cmd[:80]} → exit={result.get('exit_code', 'N/A')} ({result.get('duration_sec', 0)}s)")
        else:
            self._log("No commands to execute", "EXEC")
            self._append_bot_file("(no tool commands generated by LLM)\n\n")

        # v3.0.2: Auto-detect implicit tool requests — 'command not found'
        # failures are requests the bot already made. Feed the improvement loop.
        if tool_results:
            from core.tool_requests import detect_not_found, log_tool_requests
            implicit = detect_not_found(tool_results)
            if implicit:
                filed = log_tool_requests(
                    bot_name=self.bot_name,
                    requests=implicit,
                    engagement_dir=str(self.engagement_dir) if self.engagement_dir else None,
                    source="auto_not_found",
                )
                if filed:
                    self._log(f"{filed} missing tool(s) auto-requested: "
                              f"{[r['tool'] for r in implicit]}", "REQUEST")

        # Step 4: LLM analyzes raw tool output
        raw_output = self._format_tool_results(tool_results)

        self._log("Asking LLM to analyze tool output...", "ANALYZE")
        analysis_prompt = self._build_analysis_prompt(raw_output, context)

        analysis_system = f"""You are {self.bot_name}, {self.role_description}.
You have just executed tools and received raw output. Analyze the output and extract structured findings.

v2.4: Output structured_findings as a list of objects, each with:
- finding_id: "{self.bot_name.upper()[:3]}-NNN" (e.g., "{self.bot_name.upper()[:3]}-001")
- title: one-line finding title
- severity: Critical | High | Medium | Low | Info
- cvss: float 0.0-10.0 (or null if unknown)
- host: target host/IP (or null)
- port: target port (or null)
- service: service name (or null)
- status: Confirmed | Probable | Theoretical
- description: technical description (max 200 chars)
- risks: business impact (max 100 chars)
- attack_vectors: how to exploit (max 200 chars)
- poc: exact commands used (max 200 chars)
- proof_of_existence: raw tool output proving the finding (max 300 chars — truncate with ...)
- remediation: one-line fix (max 100 chars)

IMPORTANT: Keep ALL field values SHORT. Truncate raw output to 300 chars max. Do not paste full tool output into proof_of_existence — summarize it. If you have many findings, report only the top 10 most important ones.

Respond ONLY with a JSON block:
```json
{{
  "summary": "brief summary of what was found",
  "findings": ["finding 1", "finding 2"],
  "structured_findings": [
    {{
      "finding_id": "{self.bot_name.upper()[:3]}-001",
      "title": "...",
      "severity": "...",
      "cvss": null,
      "host": null,
      "port": null,
      "service": null,
      "status": "Confirmed",
      "description": "...",
      "risks": "...",
      "attack_vectors": "...",
      "poc": "...",
      "proof_of_existence": "...",
      "remediation": "..."
    }}
  ],
  "structured_data": {{}},
  "recommendations": ["next steps for the next bot in the pipeline"],
  "report_content": "full markdown report of your findings — this goes to findings.md"
}}
```
No other text. Just the JSON."""""

        try:
            analysis_response = self._llm(analysis_prompt, analysis_system, max_tokens=32768)
            self._log("LLM analysis received", "ANALYZE")

            print(f"\n[{self.bot_name.upper()} LLM ANALYSIS]", flush=True)
            print(analysis_response[:2000], flush=True)
            print(f"[/{self.bot_name.upper()} LLM ANALYSIS]\n", flush=True)

            analysis = self._parse_json_response(analysis_response)
        except Exception as e:
            self._log(f"LLM analysis failed: {e}", "ERROR")
            # v2.5: Record parse failure in telemetry.
            self.telemetry.record_tool_exec(
                self.bot_name, "llm_analysis_parse", "",
                0.0, exit_code=-1, parse_ok=False,
            )
            analysis = {
                "summary": f"Tool execution completed but LLM analysis failed: {e}",
                "findings": [],
                "structured_data": {},
                "recommendations": [],
                "report_content": f"## {self.bot_name.upper()} Results\n\nRaw tool output saved to engagement/raw/ folder.\nLLM analysis failed: {e}",
            }

        # Step 5: Write findings to engagement files
        report_content = analysis.get("report_content", analysis.get("summary", ""))
        if report_content:
            self._append_findings(strategy.title(), report_content)

        # v2.4: Save structured findings to lossless JSONL store
        structured_findings = analysis.get("structured_findings", [])
        if structured_findings:
            for finding in structured_findings:
                if isinstance(finding, dict):
                    self.findings_store.add(self.bot_name, finding)
            self._log(f"Saved {len(structured_findings)} structured findings to JSONL", "STORE")

        # Also feed critical findings to the critical buffer
        if structured_findings:
            for finding in structured_findings:
                if isinstance(finding, dict):
                    cvss = finding.get("cvss")
                    if cvss and isinstance(cvss, (int, float)) and cvss >= 7.0:
                        self.critical_buffer.add(
                            finding_text=finding.get("title", ""),
                            bot_name=self.bot_name,
                            cvss=float(cvss),
                            target=finding.get("host", ""),
                        )

        # Update bot file with analysis
        self._append_bot_file("\n## Analysis\n\n")
        self._append_bot_file(f"Summary: {analysis.get('summary', 'N/A')}\n\n")
        self._append_bot_file("Findings:\n")
        for f in analysis.get("findings", []):
            self._append_bot_file(f"- {f}\n")
        self._append_bot_file("\nRecommendations:\n")
        for r in analysis.get("recommendations", []):
            self._append_bot_file(f"- {r}\n")

        self._append_log(f"Analysis complete: {analysis.get('summary', 'N/A')[:100]}")
        self._append_log("Execution complete — bot going to sleep")

        # Step 6: Update state
        self._update_state(decision, analysis, tool_results)

        self._log("Bot complete", "SLEEP")

        return {
            "reasoning": decision,
            "execution": {
                "analysis": analysis,
                "tool_results": tool_results,
                "strategy": strategy,
            },
            "executed": True,
        }

    def _format_tool_results(self, results: List[Dict[str, Any]]) -> str:
        """Format tool results for LLM analysis.

        v2.5: Aggressive truncation to prevent LLM token limit issues.
        Each command's stdout is capped at 2000 chars. Total output capped at 15000 chars.
        Full output is always preserved in raw/ folder — this is just for LLM context.
        """
        if not results:
            return "(no tools were executed)"
        out = []
        total_chars = 0
        for r in results:
            entry = []
            entry.append(f"### Command: {r.get('command', 'unknown')}")
            entry.append(f"Exit Code: {r.get('exit_code', 'N/A')}")
            entry.append(f"Duration: {r.get('duration_sec', 0)}s")
            if r.get("scope_blocked"):
                entry.append(f"BLOCKED: {r.get('stderr', 'scope violation')}")
            else:
                stdout = r.get("stdout", "") or "(empty)"
                stderr = r.get("stderr", "") or ""
                # v2.5: Aggressive truncation — 2000 chars per command (was 8000)
                if len(stdout) > 2000:
                    stdout = stdout[:2000] + "\n... (truncated, full output in raw/ folder)"
                entry.append(f"STDOUT:\n{stdout}")
                if stderr:
                    entry.append(f"STDERR:\n{stderr[:500]}")
            entry_text = "\n".join(entry)
            # v2.5: Stop adding entries if we've hit the total cap
            if total_chars + len(entry_text) > 15000:
                remaining = len(results) - len(out)
                out.append(f"### ... {remaining} more command(s) omitted (output cap reached — see raw/ folder)")
                break
            out.append(entry_text)
            total_chars += len(entry_text)
        return "\n\n".join(out)

    def _build_analysis_prompt(self, raw_output: str, context: str) -> str:
        """Build the prompt for LLM analysis of tool output.

        v2.5: Context reduced to 1000 chars (was 2000) to stay within token limits.
        """
        return f"""## Previous Context
{context[:1000]}

## Your Tool Results
{raw_output}

## Your Task
Analyze the raw tool output above. Extract structured findings relevant to your role ({self.role_description}).
Focus on what you found that the NEXT bot in the pipeline needs to know.
Write a detailed report_content in markdown that will be appended to findings.md."""

    @abstractmethod
    def _update_state(self, decision: Dict[str, Any], analysis: Dict[str, Any], tool_results: List[Dict[str, Any]]):
        """Update SwarmState with bot-specific findings. Implemented by each bot."""
        pass