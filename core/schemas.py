"""
Chimeras v2.4 — Pydantic Schema Models for Bot Outputs

Enforces structured output from every bot. Schema validation happens
BEFORE output reaches WarChief — bad data never propagates.

The freeform_notes field is the escape valve for novel findings that
don't fit the schema. Use it; don't break the schema to fit edge cases.

Usage:
    from core.schemas import BotDecision, BotAnalysis, Finding

    # In base_bot.py:
    decision = parse_llm_json(response, schema=BotDecision)
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import json

try:
    from pydantic import BaseModel as _BaseModel, Field, ValidationError
    BaseModel = _BaseModel
    PYDANTIC_AVAILABLE = True
except ImportError:
    BaseModel = None
    ValidationError = Exception
    PYDANTIC_AVAILABLE = False
    # Fallback: no validation, just type hints
    def Field(default=None, **kwargs):
        return default


class Finding(BaseModel if PYDANTIC_AVAILABLE else object):
    """A single vulnerability or security finding from a bot.

    This is the canonical structure that flows through the entire pipeline:
    Bot → findings.jsonl → WarChief verification → Bookkeeper report.
    """
    finding_id: str = Field(description="Unique ID: BOT-NNN (e.g., BH-001)")
    title: str = Field(description="One-line finding title")
    severity: str = Field(description="Critical | High | Medium | Low | Info")
    cvss: Optional[float] = Field(default=None, description="CVSS 3.1 score 0.0-10.0")
    cvss_vector: Optional[str] = Field(default=None, description="CVSS vector string")
    host: Optional[str] = Field(default=None, description="Target host/IP")
    port: Optional[int] = Field(default=None, description="Target port")
    service: Optional[str] = Field(default=None, description="Service name (ssh, http, etc.)")
    status: str = Field(default="Confirmed", description="Exploited | Confirmed | Probable | Theoretical | Not Exploited")
    description: str = Field(default="", description="Technical description of the finding")
    risks: str = Field(default="", description="Business impact — what an attacker could do")
    attack_vectors: str = Field(default="", description="How to exploit — step by step")
    poc: str = Field(default="", description="Proof of concept — exact commands used")
    proof_of_existence: str = Field(default="", description="Raw tool output proving the finding exists")
    remediation: str = Field(default="", description="One-line fix recommendation")
    source_bot: str = Field(description="Which bot found this (bloodhound, wasp, etc.)")
    raw_output_ref: Optional[str] = Field(default=None, description="Path to raw tool output file")
    freeform_notes: Optional[str] = Field(default=None, description="Escape valve for anything that doesn't fit the schema")

    if not PYDANTIC_AVAILABLE:
        def __init__(self, **kwargs):
            # Fallback: just set attributes, no validation
            for k, v in kwargs.items():
                setattr(self, k, v)
            # Ensure required fields exist
            if not hasattr(self, 'finding_id'):
                self.finding_id = "UNKNOWN"
            if not hasattr(self, 'title'):
                self.title = "Unknown"
            if not hasattr(self, 'severity'):
                self.severity = "Info"
            if not hasattr(self, 'source_bot'):
                self.source_bot = "unknown"

        def model_dump(self) -> Dict[str, Any]:
            return {k: getattr(self, k, None) for k in [
                'finding_id', 'title', 'severity', 'cvss', 'cvss_vector',
                'host', 'port', 'service', 'status', 'description', 'risks',
                'attack_vectors', 'poc', 'proof_of_existence', 'remediation',
                'source_bot', 'raw_output_ref', 'freeform_notes'
            ]}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Finding":
        """Create from dict, filling missing fields with defaults."""
        if PYDANTIC_AVAILABLE:
            # Filter to known fields, pass rest to freeform_notes
            known = {f for f in cls.model_fields} if hasattr(cls, 'model_fields') else set()
            if known:
                clean = {k: v for k, v in data.items() if k in known}
                extras = {k: v for k, v in data.items() if k not in known and v is not None}
                if extras and 'freeform_notes' not in clean:
                    clean['freeform_notes'] = json.dumps(extras)
                return cls(**clean)
            return cls(**data)
        else:
            return cls(**data)


class ToolResult(BaseModel if PYDANTIC_AVAILABLE else object):
    """Tool execution result with verification metadata.

    Carries content_hash and verified_by_cycle so WarChief can skip
    re-verification when nothing changed.
    """
    command: str
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_sec: float = 0.0
    success: bool = True
    scope_blocked: bool = False
    cached: bool = False
    # v2.4: Verification metadata
    content_hash: Optional[str] = None
    verified_by_cycle: Optional[int] = None
    tool_name: Optional[str] = None
    target: Optional[str] = None

    if not PYDANTIC_AVAILABLE:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

        def model_dump(self) -> Dict[str, Any]:
            return {k: getattr(self, k, None) for k in [
                'command', 'exit_code', 'stdout', 'stderr', 'duration_sec',
                'success', 'scope_blocked', 'cached', 'content_hash',
                'verified_by_cycle', 'tool_name', 'target'
            ]}


class BotDecision(BaseModel if PYDANTIC_AVAILABLE else object):
    """Bot's initial decision: what tools to run and why."""
    needed: bool = True
    strategy: str = ""
    confidence: float = 0.5
    reasoning: str = ""
    commands: List[str] = Field(default_factory=list)
    skip_reason: str = ""

    if not PYDANTIC_AVAILABLE:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
            if not hasattr(self, 'commands'):
                self.commands = []
            if not hasattr(self, 'needed'):
                self.needed = True
            if not hasattr(self, 'confidence'):
                self.confidence = 0.5

        def model_dump(self) -> Dict[str, Any]:
            return {
                'needed': getattr(self, 'needed', True),
                'strategy': getattr(self, 'strategy', ''),
                'confidence': getattr(self, 'confidence', 0.5),
                'reasoning': getattr(self, 'reasoning', ''),
                'commands': getattr(self, 'commands', []),
                'skip_reason': getattr(self, 'skip_reason', ''),
            }


class BotAnalysis(BaseModel if PYDANTIC_AVAILABLE else object):
    """Bot's analysis of tool output: structured findings."""
    summary: str = ""
    findings: List[str] = Field(default_factory=list)
    structured_data: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)
    report_content: str = ""
    # v2.4: Structured findings (not just string list)
    structured_findings: List[Dict[str, Any]] = Field(default_factory=list)

    if not PYDANTIC_AVAILABLE:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
            if not hasattr(self, 'findings'):
                self.findings = []
            if not hasattr(self, 'structured_data'):
                self.structured_data = {}
            if not hasattr(self, 'recommendations'):
                self.recommendations = []
            if not hasattr(self, 'structured_findings'):
                self.structured_findings = []

        def model_dump(self) -> Dict[str, Any]:
            return {
                'summary': getattr(self, 'summary', ''),
                'findings': getattr(self, 'findings', []),
                'structured_data': getattr(self, 'structured_data', {}),
                'recommendations': getattr(self, 'recommendations', []),
                'report_content': getattr(self, 'report_content', ''),
                'structured_findings': getattr(self, 'structured_findings', []),
            }


def validate_bot_output(data: Dict[str, Any], schema_class) -> Dict[str, Any]:
    """Validate bot output against a Pydantic schema.

    Returns validated dict. If validation fails, returns raw data with
    a warning logged. Never crashes — bad data is better than no data.
    """
    if schema_class is None:
        return data
    if not PYDANTIC_AVAILABLE:
        return data
    try:
        model = schema_class(**data)
        return model.model_dump()
    except ValidationError as e:
        import logging
        logging.getLogger("chimeras.schemas").warning(
            f"Schema validation failed for {schema_class.__name__}: {e}. "
            f"Returning raw data."
        )
        return data


def compute_content_hash(text: str) -> str:
    """Compute SHA-256 hash of content for verification caching."""
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()[:32]