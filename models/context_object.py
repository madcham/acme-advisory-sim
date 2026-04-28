"""
Context Object Schema for Acme Advisory Simulation.

This module defines the core data model for Context Objects - the fundamental
unit of organizational memory in the Context Bank. Each object captures a piece
of institutional knowledge with temporal properties, organizational classification,
and cross-agent attribution.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List
import uuid

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


def generate_context_id() -> str:
    """Generate a unique context object ID."""
    return f"CTX-{str(uuid.uuid4())[:8].upper()}"


class ContentType(str, Enum):
    """Classification of what the context object contains."""
    decision = "decision"
    observation = "observation"
    inference = "inference"
    exception = "exception"
    policy = "policy"
    tribal_knowledge = "tribal_knowledge"


class SourceType(str, Enum):
    """Origin of the context object."""
    human = "human"
    agent = "agent"
    system = "system"
    derived = "derived"


class DecayFunction(str, Enum):
    """How confidence in the context object changes over time."""
    linear = "linear"
    exponential = "exponential"
    step_function = "step_function"
    permanent = "permanent"


class ContextGrade(str, Enum):
    """
    Classification of organizational friction type.

    - compliance_scaffolding: Required process that prevents harm
    - institutional_memory: Learned wisdom from past experience
    - expired_process: Once-valid process that no longer applies
    - generative_friction: Intentional friction that improves outcomes
    - pure_inefficiency: Waste that should be eliminated
    """
    compliance_scaffolding = "compliance_scaffolding"
    institutional_memory = "institutional_memory"
    expired_process = "expired_process"
    generative_friction = "generative_friction"
    pure_inefficiency = "pure_inefficiency"


class OrgLineage(str, Enum):
    """
    How the organizational knowledge came to exist.

    - failure_recovery: Learned from a past failure or incident
    - political_settlement: Result of organizational negotiation
    - documented_policy: Formal written policy
    - exception_handling: Pattern from handling edge cases
    - direct_observation: Observed behavior pattern
    """
    failure_recovery = "failure_recovery"
    political_settlement = "political_settlement"
    documented_policy = "documented_policy"
    exception_handling = "exception_handling"
    direct_observation = "direct_observation"


class AgentAction(BaseModel):
    """Records an agent's interaction with a context object."""
    agent_id: str
    timestamp: datetime
    action_taken: str
    outcome: Optional[str] = None
    validated: Optional[bool] = None


class ProvenanceLink(BaseModel):
    """Links context objects in a derivation chain."""
    source_id: str
    relationship: str  # "derived_from", "contradicts", "supersedes", "validates"


class ContextObject(BaseModel):
    """
    The fundamental unit of organizational memory.

    A Context Object captures a piece of institutional knowledge along with
    its temporal properties, organizational classification, provenance chain,
    and cross-agent attribution history.
    """

    # Identity
    id: str = Field(default_factory=generate_context_id)
    created_at: datetime = Field(default_factory=utc_now)
    created_by: str  # human_id or agent_id
    source_type: SourceType
    workflow_id: Optional[str] = None
    week: int  # simulation week when created

    # Content
    content_type: ContentType
    payload: str  # human-readable description of the context
    structured_data: Optional[dict] = None  # machine-readable structured fields

    # Temporal properties
    valid_from: datetime = Field(default_factory=utc_now)
    decay_function: DecayFunction
    decay_rate: float = 0.1  # per week, ignored for permanent and step_function
    confidence_at_creation: float = Field(ge=0.0, le=1.0)

    # Computed (updated on retrieval)
    current_confidence: Optional[float] = None

    # Organizational classification (AI-inferred)
    context_grade: Optional[ContextGrade] = None
    context_grade_confidence: Optional[float] = None
    org_lineage: Optional[OrgLineage] = None
    org_lineage_confidence: Optional[float] = None

    # Provenance
    derivation_chain: List[ProvenanceLink] = Field(default_factory=list)
    raw_evidence: List[str] = Field(default_factory=list)  # references to source events

    # Cross-agent attribution
    read_by: List[AgentAction] = Field(default_factory=list)
    acted_on_by: List[AgentAction] = Field(default_factory=list)
    validated_by: List[AgentAction] = Field(default_factory=list)
    invalidated_by: List[AgentAction] = Field(default_factory=list)

    # Relationships
    supersedes: Optional[str] = None
    superseded_by: Optional[str] = None
    contradicts: List[str] = Field(default_factory=list)

    def compute_current_confidence(self, current_week: int) -> float:
        """
        Calculate confidence score based on decay function and elapsed time.

        Args:
            current_week: The current simulation week.

        Returns:
            Confidence score between 0.05 and 1.0 (or original for permanent).
        """
        weeks_elapsed = current_week - self.week

        if self.decay_function == DecayFunction.permanent:
            return self.confidence_at_creation

        elif self.decay_function == DecayFunction.step_function:
            # Confidence holds until threshold then drops sharply
            threshold = 12  # weeks
            if weeks_elapsed < threshold:
                return self.confidence_at_creation
            else:
                return max(0.1, self.confidence_at_creation * 0.3)

        elif self.decay_function == DecayFunction.exponential:
            return max(0.05, self.confidence_at_creation * (1 - self.decay_rate) ** weeks_elapsed)

        elif self.decay_function == DecayFunction.linear:
            return max(0.05, self.confidence_at_creation - (self.decay_rate * weeks_elapsed))

        return self.confidence_at_creation

    def update_confidence(self, current_week: int) -> "ContextObject":
        """
        Update the current_confidence field based on decay.

        Returns self for method chaining.
        """
        self.current_confidence = self.compute_current_confidence(current_week)
        return self

    def record_read(self, agent_id: str, action: str, outcome: Optional[str] = None) -> None:
        """Record that an agent read this context object."""
        self.read_by.append(AgentAction(
            agent_id=agent_id,
            timestamp=utc_now(),
            action_taken=action,
            outcome=outcome
        ))

    def record_action(self, agent_id: str, action: str, outcome: Optional[str] = None) -> None:
        """Record that an agent acted on this context object."""
        self.acted_on_by.append(AgentAction(
            agent_id=agent_id,
            timestamp=utc_now(),
            action_taken=action,
            outcome=outcome
        ))

    def record_validation(self, agent_id: str, validated: bool, notes: Optional[str] = None) -> None:
        """Record an agent's validation or invalidation of this context object."""
        action = AgentAction(
            agent_id=agent_id,
            timestamp=utc_now(),
            action_taken="validation_check",
            outcome=notes,
            validated=validated
        )
        if validated:
            self.validated_by.append(action)
        else:
            self.invalidated_by.append(action)

    def is_superseded(self) -> bool:
        """Check if this context object has been superseded by another."""
        return self.superseded_by is not None

    def has_contradictions(self) -> bool:
        """Check if this context object has known contradictions."""
        return len(self.contradicts) > 0
