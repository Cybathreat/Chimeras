"""
SwarmBots v2.0 — Abstract Base Bot

All bot agents inherit from this base class.
Implements the 9-step autonomous reasoning loop with live streaming.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, AsyncIterator
from datetime import datetime
import sys

from core.llm_router import LLMRouter
from core.state import SwarmState


class BaseBot(ABC):
    """
    Abstract base class for all SwarmBots agents.
    
    Implements the 9-step reasoning loop:
    1. Wake - Read mission state and config
    2. Connect - Instantiate LLM provider
    3. Reason - Send context + role prompt, stream thinking
    4. Decide - Determine if needed and strategy
    5. Recommend - Write ReasoningReport to state
    6. Wait - Await WarChief acknowledgment
    7. Execute - Run tools based on chosen strategy
    8. Report - Write output to state
    9. Sleep - Signal completion
    """
    
    bot_name: str = "base"
    role_description: str = "Base bot role"
    
    def __init__(self, state: SwarmState, swarm_config: Optional[Dict[str, Any]] = None):
        self.state = state
        self.swarm_config = swarm_config or {}
        self.llm_router = self._init_router()
        self.reasoning_complete = False
        self.execution_complete = False
    
    def _init_router(self) -> LLMRouter:
        """Initialize LLM router from swarm config."""
        return LLMRouter.from_config(self.bot_name, self.swarm_config)
    
    def _log(self, message: str, level: str = "INFO"):
        """Stream log message to terminal."""
        timestamp = datetime.utcnow().isoformat()
        prefix = f"[{timestamp}] [{self.bot_name.upper()}] [{level}]"
        print(f"{prefix} {message}", flush=True)
    
    def _stream_reasoning(self, prompt: str, system: Optional[str] = None) -> AsyncIterator[str]:
        """Stream LLM reasoning live to terminal."""
        self._log("Starting reasoning loop...", "REASON")
        
        async def reasoning_stream():
            full_response = []
            async for token in self.llm_router.stream(prompt, system):
                full_response.append(token)
                # Stream live to terminal
                print(token, end="", flush=True)
            print()  # Newline after stream
            self._log("Reasoning complete", "REASON")
            return "".join(full_response)
        
        return reasoning_stream()
    
    def _build_role_prompt(self) -> str:
        """Build the role-specific system prompt."""
        return f"""You are {self.bot_name}, {self.role_description}.

You operate within a multi-agent swarm for penetration testing.
Your reasoning must be autonomous, strategic, and aligned with the mission.

Current Mission Context:
{self.state.get('mission', {})}

Your role is to:
1. Analyze the current state
2. Decide if your expertise is needed
3. Recommend a strategy if engaged
4. Execute only after WarChief acknowledgment

Think step-by-step. Be precise. No fluff."""
    
    @abstractmethod
    async def reason(self) -> Dict[str, Any]:
        """
        Step 3-5: Reason about the mission and produce a ReasoningReport.
        
        Returns:
            dict: {
                "needed": bool,
                "strategy": str,
                "confidence": float,
                "reasoning": str,
                "recommended_actions": list
            }
        """
        pass
    
    @abstractmethod
    async def execute(self) -> Dict[str, Any]:
        """
        Step 7-8: Execute the chosen strategy and produce output.
        
        Returns:
            dict: Bot-specific output report
        """
        pass
    
    async def run(self) -> Dict[str, Any]:
        """
        Main execution flow for the bot.
        
        Returns:
            dict: Combined reasoning + execution report
        """
        # Step 1-2: Wake + Connect (done in __init__)
        self._log("Bot awakened", "WAKE")
        
        # Step 3-5: Reason
        reasoning_report = await self.reason()
        self.state.setdefault("reasoning_reports", {})[self.bot_name] = reasoning_report
        self._log(f"Reasoning complete: needed={reasoning_report.get('needed')}", "DECIDE")
        
        # Step 6: Wait (WarChief handles this in graph)
        if not reasoning_report.get("needed", True):
            self._log("Bot not needed, skipping execution", "SKIP")
            self.reasoning_complete = True
            return {"reasoning": reasoning_report, "executed": False}
        
        # Check human approval gate for exploitation bots
        if self._requires_human_approval() and not self.state.get("human_approval", False):
            self._log("Awaiting human approval", "WAIT")
            self.reasoning_complete = True
            return {"reasoning": reasoning_report, "executed": False, "awaiting_approval": True}
        
        # Step 7-8: Execute
        self._log("Executing strategy", "EXECUTE")
        execution_report = await self.execute()
        self.execution_complete = True
        
        # Step 9: Sleep
        self._log("Bot completing", "SLEEP")
        
        return {
            "reasoning": reasoning_report,
            "execution": execution_report,
            "executed": True
        }
    
    def _requires_human_approval(self) -> bool:
        """Check if this bot requires human approval before execution."""
        # Only Surgeon (exploitation) requires the human-in-loop gate
        return self.bot_name == "surgeon"
    
    def _append_ledger(self, action: str, details: Dict[str, Any]):
        """Append action to Bookkeeper's operation ledger."""
        ledger_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "bot": self.bot_name,
            "action": action,
            "details": details
        }
        self.state.setdefault("operation_ledger", []).append(ledger_entry)
