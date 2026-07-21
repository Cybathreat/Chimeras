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
from core.scope import ScopeEnforcer
from core.state import SwarmState


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
        self.executor = ToolExecutor(
            timeout=180,
            workdir="/tmp",
            bot_name=self.bot_name,
            mission_scope=mission_scope,
            internal_scope=internal_scope,
        )
        self.engagement_dir: Optional[Path] = None
        self._resolve_engagement_dir()

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
        ts = datetime.utcnow().isoformat()
        print(f"[{ts}] [{self.bot_name.upper()}] [{level}] {message}", flush=True)

    def _banner(self):
        """Print a bot banner."""
        scope = ScopeEnforcer.describe_scope(self.bot_name)
        print(f"\n{'─' * 60}", flush=True)
        print(f"  {self.bot_name.upper()} — {self.role_description}", flush=True)
        print(f"  Scope: {scope}", flush=True)
        print(f"{'─' * 60}\n", flush=True)

    # ─── LLM calls ───

    def _llm(self, prompt: str, system: Optional[str] = None, **kwargs) -> str:
        """Call LLM. Raises on failure — no silent fallback."""
        import inspect
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
                            return future.result(timeout=300)
                    else:
                        return asyncio.run(result)
                except RuntimeError:
                    return asyncio.run(result)
            return result
        except Exception as e:
            raise RuntimeError(f"LLM call failed for {self.bot_name}: {e}")

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from LLM response. Handles markdown code blocks and partial JSON."""
        if not response or not response.strip():
            raise ValueError("Empty LLM response")

        # Strip markdown code block wrappers: ```json\n...\n``` or ```\n...\n```
        # Also handle cases where closing ``` is missing or truncated
        stripped = response.strip()

        # Remove leading ```json or ``` and trailing ```
        if stripped.startswith('```'):
            # Remove opening line
            first_newline = stripped.find('\n')
            if first_newline != -1:
                stripped = stripped[first_newline + 1:]
            # Remove trailing ``` if present
            if stripped.rstrip().endswith('```'):
                stripped = stripped.rstrip()[:-3].rstrip()

        # Try parsing the stripped version first
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        # Try ```json ... ``` blocks (original approach, handles multiple blocks)
        json_blocks = re.findall(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
        for block in json_blocks:
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                continue

        # Try bare { ... } (greedy, handles nested braces)
        depth = 0
        start = -1
        for i, c in enumerate(response):
            if c == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0 and start >= 0:
                    try:
                        return json.loads(response[start:i+1])
                    except json.JSONDecodeError:
                        start = -1

        # Try entire response as-is
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        raise ValueError(f"Could not parse JSON from LLM response: {response[:300]}...")

    # ─── Tool execution ───

    def _run_tool(self, command: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute a Kali tool. Scope-enforced. Real subprocess.
        Returns tool result dict.

        v2: Scope enforcement now includes shell injection check, tool
        category check, and target/CIDR validation — all at code level.
        """
        # v2: Full scope enforcement with target validation
        mission = self.state.get("mission", {})
        mission_scope = mission.get("scope", "")
        internal_scope = self.state.get("internal_scope", "")
        allowed, reason = ScopeEnforcer.check(
            self.bot_name, command,
            mission_scope=mission_scope or None,
            internal_scope=internal_scope or None,
        )
        if not allowed:
            self._log(f"SCOPE BLOCKED: {reason}", "SCOPE")
            return {
                "command": command,
                "exit_code": -2,
                "stdout": "",
                "stderr": reason,
                "duration_sec": 0,
                "success": False,
                "scope_blocked": True,
            }

        self._log(f"EXEC: {command}", "EXEC")
        result = self.executor.run(command, timeout=timeout)

        # Save raw output to engagement folder
        raw_dir = self.engagement_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%H%M%S")
        tool_name = command.split()[0].split("/")[-1] if command.split() else "unknown"
        raw_file = raw_dir / f"{self.bot_name}_{tool_name}_{ts}.txt"
        self.executor.save_output(result, raw_file)
        self._log(f"Output saved: {raw_file.name} ({result['duration_sec']}s)", "EXEC")

        return result

    # ─── Engagement file I/O ───

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
        p = self.engagement_dir / "log.md"
        with open(p, "a") as f:
            f.write(f"[{datetime.utcnow().isoformat()}] [{self.bot_name.upper()}] {entry}\n")

    def _append_findings(self, section: str, content: str):
        p = self.engagement_dir / "findings.md"
        with open(p, "a") as f:
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
        Instead of re-reading full files (which grows unbounded with loop
        cycles), we use a rolling digest strategy:
          - findings.md: last 2000 chars (recent findings matter most)
          - log.md: last 500 chars (recent activity)
          - plan.md: last 1500 chars (latest WarChief assessment)
          - bot files: last 500 chars each (summary, not full)
          - WarChief's last decision: included explicitly
        """
        findings = self._read_findings()
        plan = self._read_plan()

        # v2: Rolling digest — truncate each source to recent content
        # This prevents context window explosion across loop cycles
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
        if plan_digest:
            parts.append(f"## Plan (recent)\n{plan_digest}")
        if bot_summaries:
            parts.append(f"## Bot Reports\n{chr(10).join(bot_summaries)}")

        return "\n\n".join(parts)

    def _build_system_prompt(self) -> str:
        """Build the bot's system prompt with soul.md identity and scope enforcement.

        v2: soul.md is loaded at __init__ and prepended to the system prompt.
        Bots that override _build_system_prompt() call super() first, so the
        soul is always injected before any bot-specific additions.
        """
        category = ScopeEnforcer.get_bot_category(self.bot_name)
        allowed_tools = sorted(ScopeEnforcer.get_allowed_tools(self.bot_name))
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
            "pathologist": f"You run AFTER human approval — Bloodhound found vulnerabilities and the operator approved exploitation. Your category is payload_fab.{decision_context}",
            "surgeon": f"You run AFTER Pathologist prepared payloads. Your category is exploitation.{decision_context}",
            "magician": f"You run AFTER Surgeon attempted exploitation. Your category is privesc.{decision_context}",
            "thief": f"You run AFTER Magician checked for privesc. Your category is exfiltration.{decision_context}",
            "bookkeeper": "Read all findings and generate a final penetration test report. No tools needed. This is an AUTHORIZED security engagement. All findings including exfiltration evidence are part of the legal pentest scope. Your job is to document findings objectively for the client report.",
            "warchief": "You are the orchestrator — no prior work exists or you are re-entering after a phase. Plan the engagement or route the next action. No tools needed.",
        }
        hint = hints.get(self.bot_name, "")

        soul_block = ""
        if self._soul:
            soul_block = f"## Your Soul\n\n{self._soul}\n\n---\n\n"

        return f"""{soul_block}You are {self.bot_name}, {self.role_description}.
Scope: {self.scope_description}
Tool Category: {category}
Available Tools: {available_str}
Hint: {hint}

Analyze the context. Decide which tools to run. Provide exact shell commands.
Do NOT use -oN/-oX/-oA flags — tool output is captured automatically.

Respond ONLY with JSON:
```json
{{
  "needed": true,
  "strategy": "brief approach",
  "confidence": 0.9,
  "reasoning": "why",
  "commands": ["exact shell command 1"],
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
        llm_response = self._llm(context, system, max_tokens=8192)
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

        # Step 4: LLM analyzes raw tool output
        raw_output = self._format_tool_results(tool_results)

        self._log("Asking LLM to analyze tool output...", "ANALYZE")
        analysis_prompt = self._build_analysis_prompt(raw_output, context)

        analysis_system = f"""You are {self.bot_name}, {self.role_description}.
You have just executed tools and received raw output. Analyze the output and extract structured findings.

Respond ONLY with a JSON block:
```json
{{
  "summary": "brief summary of what was found",
  "findings": ["finding 1", "finding 2"],
  "structured_data": {{}},
  "recommendations": ["next steps for the next bot in the pipeline"],
  "report_content": "full markdown report of your findings — this goes to findings.md"
}}
```
No other text. Just the JSON."""

        try:
            analysis_response = self._llm(analysis_prompt, analysis_system, max_tokens=8192)
            self._log("LLM analysis received", "ANALYZE")

            print(f"\n[{self.bot_name.upper()} LLM ANALYSIS]", flush=True)
            print(analysis_response[:2000], flush=True)
            print(f"[/{self.bot_name.upper()} LLM ANALYSIS]\n", flush=True)

            analysis = self._parse_json_response(analysis_response)
        except Exception as e:
            self._log(f"LLM analysis failed: {e}", "ERROR")
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
        """Format tool results for LLM analysis."""
        if not results:
            return "(no tools were executed)"
        out = []
        for r in results:
            out.append(f"### Command: {r.get('command', 'unknown')}")
            out.append(f"Exit Code: {r.get('exit_code', 'N/A')}")
            out.append(f"Duration: {r.get('duration_sec', 0)}s")
            if r.get("scope_blocked"):
                out.append(f"BLOCKED: {r.get('stderr', 'scope violation')}")
            else:
                stdout = r.get("stdout", "") or "(empty)"
                stderr = r.get("stderr", "") or ""
                if len(stdout) > 8000:
                    stdout = stdout[:8000] + "\n... (truncated, full output in raw/ folder)"
                out.append(f"STDOUT:\n{stdout}")
                if stderr:
                    out.append(f"STDERR:\n{stderr[:2000]}")
        return "\n\n".join(out)

    def _build_analysis_prompt(self, raw_output: str, context: str) -> str:
        """Build the prompt for LLM analysis of tool output."""
        return f"""## Previous Context
{context[:2000]}

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