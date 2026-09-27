"""
Input Validation Layer for Exhaust Streams.

CRITICAL FOR IDEA QUALITY: Prevents "garbage in → garbage out"

The Problem:
- Not all exhaust is equal quality
- A 20-year veteran's observation >> a new hire's guess
- An AI agent with 90% accuracy >> one with 50% accuracy
- "Always require X" >> "I think maybe sometimes possibly X"

What Validation Does:
- Scores source credibility (tenure + role + validation history)
- Detects vague language ("maybe", "probably", "I think")
- Checks for policy conflicts
- Adjusts confidence based on quality signals
- Blocks deposits that fail basic quality checks

Source Credibility Formula:
    credibility = (tenure_factor * 0.3) + (role_factor * 0.3) + (validation_factor * 0.4)

    where:
    - tenure_factor = min(0.3, years * 0.03)  # maxes at 10 years
    - role_factor = (authority_level / 5) * 0.3  # 1-5 scale
    - validation_factor = past_validation_rate * 0.4  # historical accuracy

Confidence Adjustments:
- High credibility source (>0.7): +10% boost
- Low credibility source (<0.3): -20% reduction
- Vague language detected: -15% reduction
- Actionable language ("always", "never", "must"): +5% boost

Integration:
- Called automatically during ContextBank.deposit()
- Returns ValidationResult with all checks
- Failed validation blocks deposit with clear error

This module validates incoming exhaust before deposit into the Context Bank.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Optional, Set, Tuple, Any
from enum import Enum
import re

from models.context_object import (
    ContextObject, ContentType, SourceType, DecayFunction,
    ContextGrade, OrgLineage,
)


class ValidationStatus(str, Enum):
    """Result of validation check."""
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class ValidationCategory(str, Enum):
    """Categories of validation checks."""
    SOURCE_CREDIBILITY = "source_credibility"
    CONTENT_QUALITY = "content_quality"
    POLICY_CONSISTENCY = "policy_consistency"
    CONFIDENCE_CALIBRATION = "confidence_calibration"
    STRUCTURAL_VALIDITY = "structural_validity"


@dataclass
class ValidationCheck:
    """Result of a single validation check."""
    category: ValidationCategory
    status: ValidationStatus
    message: str
    details: Optional[Dict[str, Any]] = None
    suggested_adjustment: Optional[float] = None  # Confidence adjustment


@dataclass
class ValidationResult:
    """Complete validation result for a context object."""
    object_id: str
    overall_status: ValidationStatus
    checks: List[ValidationCheck] = field(default_factory=list)
    adjusted_confidence: Optional[float] = None
    recommendations: List[str] = field(default_factory=list)
    should_deposit: bool = True
    requires_human_review: bool = False

    def add_check(self, check: ValidationCheck) -> None:
        """Add a validation check result."""
        self.checks.append(check)
        # Update overall status based on worst check
        if check.status == ValidationStatus.FAILED:
            self.overall_status = ValidationStatus.FAILED
            self.should_deposit = False
        elif check.status == ValidationStatus.NEEDS_REVIEW and self.overall_status != ValidationStatus.FAILED:
            self.overall_status = ValidationStatus.NEEDS_REVIEW
            self.requires_human_review = True
        elif check.status == ValidationStatus.WARNING and self.overall_status == ValidationStatus.PASSED:
            self.overall_status = ValidationStatus.WARNING


@dataclass
class SourceCredibilityProfile:
    """Profile for assessing source credibility."""
    source_id: str
    source_type: SourceType
    tenure_years: float = 0.0
    role_authority_level: int = 1  # 1-5, higher = more authority
    past_validation_rate: float = 0.5  # % of their contributions validated
    domain_expertise: Set[str] = field(default_factory=set)
    known_biases: List[str] = field(default_factory=list)

    def compute_credibility_score(self) -> float:
        """
        Compute overall credibility score (0.0-1.0).

        Factors:
        - Tenure: More experience = higher credibility
        - Role: Higher authority = higher credibility
        - Validation history: Past success = higher credibility
        """
        # Tenure factor (0-0.3): maxes out at 10 years
        tenure_factor = min(0.3, self.tenure_years * 0.03)

        # Role factor (0-0.3): scales with authority level
        role_factor = (self.role_authority_level / 5) * 0.3

        # Validation factor (0-0.4): based on past success
        validation_factor = self.past_validation_rate * 0.4

        return min(1.0, tenure_factor + role_factor + validation_factor)


class ExhaustValidator:
    """
    Validates incoming exhaust before deposit into Context Bank.

    This is the critical "garbage filter" that prevents bad data from
    polluting institutional memory.
    """

    def __init__(
        self,
        min_payload_length: int = 20,
        min_confidence_threshold: float = 0.3,
        require_structured_data: bool = False,
        strict_mode: bool = False,
    ):
        """
        Initialize validator.

        Args:
            min_payload_length: Minimum characters in payload
            min_confidence_threshold: Reject if confidence below this
            require_structured_data: Require structured_data field
            strict_mode: If True, warnings become failures
        """
        self.min_payload_length = min_payload_length
        self.min_confidence_threshold = min_confidence_threshold
        self.require_structured_data = require_structured_data
        self.strict_mode = strict_mode

        # Track source profiles for credibility assessment
        self._source_profiles: Dict[str, SourceCredibilityProfile] = {}

        # Known policies for consistency checking
        self._documented_policies: Dict[str, ContextObject] = {}

        # Vocabulary for quality checks
        self._vague_terms = {
            "sometimes", "maybe", "probably", "might", "could be",
            "i think", "i guess", "not sure", "possibly", "perhaps",
        }
        self._high_value_terms = {
            "always", "never", "must", "required", "exception",
            "rule", "policy", "override", "approval", "escalate",
        }

    def register_source_profile(self, profile: SourceCredibilityProfile) -> None:
        """Register a source's credibility profile."""
        self._source_profiles[profile.source_id] = profile

    def register_policy(self, policy: ContextObject) -> None:
        """Register a documented policy for consistency checking."""
        if policy.content_type == ContentType.policy:
            self._documented_policies[policy.id] = policy

    def validate(self, context_object: ContextObject) -> ValidationResult:
        """
        Perform complete validation of a context object.

        Returns:
            ValidationResult with all checks and recommendations
        """
        result = ValidationResult(
            object_id=context_object.id,
            overall_status=ValidationStatus.PASSED,
        )

        # Run all validation checks
        self._check_structural_validity(context_object, result)
        self._check_source_credibility(context_object, result)
        self._check_content_quality(context_object, result)
        self._check_policy_consistency(context_object, result)
        self._calibrate_confidence(context_object, result)

        # Generate recommendations
        self._generate_recommendations(context_object, result)

        return result

    def _check_structural_validity(
        self,
        obj: ContextObject,
        result: ValidationResult
    ) -> None:
        """Check basic structural requirements."""
        # Check ID exists
        if not obj.id:
            result.add_check(ValidationCheck(
                category=ValidationCategory.STRUCTURAL_VALIDITY,
                status=ValidationStatus.FAILED,
                message="Context object missing ID",
            ))
            return

        # Check payload exists and meets minimum length
        if not obj.payload:
            result.add_check(ValidationCheck(
                category=ValidationCategory.STRUCTURAL_VALIDITY,
                status=ValidationStatus.FAILED,
                message="Context object missing payload",
            ))
        elif len(obj.payload) < self.min_payload_length:
            result.add_check(ValidationCheck(
                category=ValidationCategory.STRUCTURAL_VALIDITY,
                status=ValidationStatus.WARNING if not self.strict_mode else ValidationStatus.FAILED,
                message=f"Payload too short ({len(obj.payload)} chars, minimum {self.min_payload_length})",
            ))
        else:
            result.add_check(ValidationCheck(
                category=ValidationCategory.STRUCTURAL_VALIDITY,
                status=ValidationStatus.PASSED,
                message="Structural validity check passed",
            ))

        # Check confidence is in valid range
        if obj.confidence_at_creation < 0 or obj.confidence_at_creation > 1:
            result.add_check(ValidationCheck(
                category=ValidationCategory.STRUCTURAL_VALIDITY,
                status=ValidationStatus.FAILED,
                message=f"Invalid confidence value: {obj.confidence_at_creation}",
            ))

        # Check required structured data if enabled
        if self.require_structured_data and not obj.structured_data:
            result.add_check(ValidationCheck(
                category=ValidationCategory.STRUCTURAL_VALIDITY,
                status=ValidationStatus.WARNING,
                message="Missing structured_data (recommended for retrieval)",
            ))

    def _check_source_credibility(
        self,
        obj: ContextObject,
        result: ValidationResult
    ) -> None:
        """Assess credibility of the source."""
        source_id = obj.created_by

        # Look up source profile
        profile = self._source_profiles.get(source_id)

        if profile:
            credibility = profile.compute_credibility_score()

            if credibility < 0.3:
                result.add_check(ValidationCheck(
                    category=ValidationCategory.SOURCE_CREDIBILITY,
                    status=ValidationStatus.WARNING,
                    message=f"Low source credibility ({credibility:.2f})",
                    details={
                        "source_id": source_id,
                        "tenure_years": profile.tenure_years,
                        "role_authority": profile.role_authority_level,
                        "past_validation_rate": profile.past_validation_rate,
                    },
                    suggested_adjustment=-0.2,  # Reduce confidence by 20%
                ))
            elif credibility > 0.7:
                result.add_check(ValidationCheck(
                    category=ValidationCategory.SOURCE_CREDIBILITY,
                    status=ValidationStatus.PASSED,
                    message=f"High source credibility ({credibility:.2f})",
                    suggested_adjustment=0.1,  # Boost confidence by 10%
                ))
            else:
                result.add_check(ValidationCheck(
                    category=ValidationCategory.SOURCE_CREDIBILITY,
                    status=ValidationStatus.PASSED,
                    message=f"Moderate source credibility ({credibility:.2f})",
                ))
        else:
            # Unknown source - assign based on source type
            if obj.source_type == SourceType.system:
                result.add_check(ValidationCheck(
                    category=ValidationCategory.SOURCE_CREDIBILITY,
                    status=ValidationStatus.PASSED,
                    message="System source - high credibility assumed",
                ))
            elif obj.source_type == SourceType.agent:
                result.add_check(ValidationCheck(
                    category=ValidationCategory.SOURCE_CREDIBILITY,
                    status=ValidationStatus.WARNING,
                    message="Agent source without profile - moderate credibility assumed",
                    suggested_adjustment=-0.1,
                ))
            else:
                result.add_check(ValidationCheck(
                    category=ValidationCategory.SOURCE_CREDIBILITY,
                    status=ValidationStatus.NEEDS_REVIEW,
                    message=f"Unknown source: {source_id} - needs review",
                ))

    def _check_content_quality(
        self,
        obj: ContextObject,
        result: ValidationResult
    ) -> None:
        """Assess quality and specificity of content."""
        payload_lower = obj.payload.lower()

        # Check for vague language
        vague_count = sum(1 for term in self._vague_terms if term in payload_lower)
        high_value_count = sum(1 for term in self._high_value_terms if term in payload_lower)

        if vague_count > 2:
            result.add_check(ValidationCheck(
                category=ValidationCategory.CONTENT_QUALITY,
                status=ValidationStatus.WARNING,
                message=f"Content contains vague language ({vague_count} vague terms)",
                details={"vague_terms_found": vague_count},
                suggested_adjustment=-0.15,
            ))
        elif high_value_count > 0:
            result.add_check(ValidationCheck(
                category=ValidationCategory.CONTENT_QUALITY,
                status=ValidationStatus.PASSED,
                message=f"Content contains actionable language ({high_value_count} high-value terms)",
                suggested_adjustment=0.05,
            ))
        else:
            result.add_check(ValidationCheck(
                category=ValidationCategory.CONTENT_QUALITY,
                status=ValidationStatus.PASSED,
                message="Content quality acceptable",
            ))

        # Check for specificity (named entities, numbers, dates)
        has_numbers = bool(re.search(r'\d+', obj.payload))
        has_names = bool(re.search(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+', obj.payload))
        has_percentages = bool(re.search(r'\d+%', obj.payload))

        specificity_score = sum([has_numbers, has_names, has_percentages])

        if specificity_score == 0 and obj.content_type in [ContentType.observation, ContentType.tribal_knowledge]:
            result.add_check(ValidationCheck(
                category=ValidationCategory.CONTENT_QUALITY,
                status=ValidationStatus.WARNING,
                message="Low specificity - no names, numbers, or dates found",
                suggested_adjustment=-0.1,
            ))

    def _check_policy_consistency(
        self,
        obj: ContextObject,
        result: ValidationResult
    ) -> None:
        """Check if content conflicts with documented policies."""
        if not self._documented_policies:
            result.add_check(ValidationCheck(
                category=ValidationCategory.POLICY_CONSISTENCY,
                status=ValidationStatus.PASSED,
                message="No policies registered for consistency check",
            ))
            return

        # Simple keyword-based conflict detection
        # In production, use semantic similarity
        conflicts_found = []

        obj_keywords = set(obj.payload.lower().split())

        for policy_id, policy in self._documented_policies.items():
            policy_keywords = set(policy.payload.lower().split())

            # Check for same entity with different rules
            if obj.structured_data and policy.structured_data:
                obj_entities = set(str(v).lower() for v in obj.structured_data.values())
                policy_entities = set(str(v).lower() for v in policy.structured_data.values())

                # Same entity mentioned
                if obj_entities & policy_entities:
                    # Check for contradictory action words
                    obj_actions = obj_keywords & {"approve", "deny", "require", "skip", "always", "never"}
                    policy_actions = policy_keywords & {"approve", "deny", "require", "skip", "always", "never"}

                    if obj_actions and policy_actions:
                        # Potential conflict - flag for review
                        conflicts_found.append({
                            "policy_id": policy_id,
                            "policy_name": policy.display_name,
                            "shared_entities": list(obj_entities & policy_entities),
                        })

        if conflicts_found:
            result.add_check(ValidationCheck(
                category=ValidationCategory.POLICY_CONSISTENCY,
                status=ValidationStatus.NEEDS_REVIEW,
                message=f"Potential conflict with {len(conflicts_found)} existing policy(ies)",
                details={"conflicts": conflicts_found},
            ))
        else:
            result.add_check(ValidationCheck(
                category=ValidationCategory.POLICY_CONSISTENCY,
                status=ValidationStatus.PASSED,
                message="No policy conflicts detected",
            ))

    def _calibrate_confidence(
        self,
        obj: ContextObject,
        result: ValidationResult
    ) -> None:
        """Calculate adjusted confidence based on validation checks."""
        base_confidence = obj.confidence_at_creation

        # Collect all suggested adjustments
        total_adjustment = 0.0
        for check in result.checks:
            if check.suggested_adjustment:
                total_adjustment += check.suggested_adjustment

        # Apply adjustment with bounds
        adjusted = base_confidence + total_adjustment
        adjusted = max(self.min_confidence_threshold, min(1.0, adjusted))

        result.adjusted_confidence = adjusted

        if abs(total_adjustment) > 0.1:
            result.add_check(ValidationCheck(
                category=ValidationCategory.CONFIDENCE_CALIBRATION,
                status=ValidationStatus.PASSED,
                message=f"Confidence adjusted: {base_confidence:.2f} → {adjusted:.2f}",
                details={
                    "original": base_confidence,
                    "adjustment": total_adjustment,
                    "final": adjusted,
                },
            ))

    def _generate_recommendations(
        self,
        obj: ContextObject,
        result: ValidationResult
    ) -> None:
        """Generate actionable recommendations based on checks."""
        for check in result.checks:
            if check.status == ValidationStatus.FAILED:
                result.recommendations.append(f"FIX: {check.message}")
            elif check.status == ValidationStatus.WARNING:
                result.recommendations.append(f"IMPROVE: {check.message}")
            elif check.status == ValidationStatus.NEEDS_REVIEW:
                result.recommendations.append(f"REVIEW: {check.message}")


class BehavioralExhaustValidator(ExhaustValidator):
    """Specialized validator for behavioral exhaust (employee Q&A)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.min_payload_length = 30  # Conversations should be longer

    def validate_knowledge_transfer(
        self,
        asker_profile: SourceCredibilityProfile,
        answerer_profile: SourceCredibilityProfile,
        context_object: ContextObject,
    ) -> ValidationResult:
        """
        Validate a knowledge transfer exchange.

        Knowledge from a senior person answering a junior's question
        is more credible than the reverse.
        """
        result = self.validate(context_object)

        # Check expertise direction
        if answerer_profile.tenure_years > asker_profile.tenure_years:
            # Expected direction: senior answers junior
            result.add_check(ValidationCheck(
                category=ValidationCategory.SOURCE_CREDIBILITY,
                status=ValidationStatus.PASSED,
                message="Knowledge flowing from senior to junior - expected pattern",
                suggested_adjustment=0.1,
            ))
        elif answerer_profile.tenure_years < asker_profile.tenure_years - 2:
            # Unusual: very junior answering senior
            result.add_check(ValidationCheck(
                category=ValidationCategory.SOURCE_CREDIBILITY,
                status=ValidationStatus.WARNING,
                message="Junior employee answering senior's question - unusual pattern",
                suggested_adjustment=-0.15,
            ))

        # Recalculate confidence after new checks
        self._calibrate_confidence(context_object, result)

        return result


class AgentExhaustValidator(ExhaustValidator):
    """Specialized validator for agent exhaust (AI decision reasoning)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Track agent performance over time
        self._agent_accuracy_history: Dict[str, List[bool]] = {}

    def record_agent_outcome(self, agent_id: str, was_correct: bool) -> None:
        """Record whether an agent's decision was correct."""
        if agent_id not in self._agent_accuracy_history:
            self._agent_accuracy_history[agent_id] = []
        self._agent_accuracy_history[agent_id].append(was_correct)
        # Keep last 50 decisions
        self._agent_accuracy_history[agent_id] = self._agent_accuracy_history[agent_id][-50:]

    def get_agent_accuracy(self, agent_id: str) -> float:
        """Get agent's recent accuracy rate."""
        history = self._agent_accuracy_history.get(agent_id, [])
        if not history:
            return 0.5  # Unknown agent, assume 50%
        return sum(history) / len(history)

    def validate_agent_reasoning(
        self,
        agent_id: str,
        context_object: ContextObject,
        context_ids_used: List[str],
    ) -> ValidationResult:
        """
        Validate reasoning deposited by an AI agent.

        Adjusts confidence based on:
        - Agent's historical accuracy
        - Whether context was actually used in reasoning
        - Quality of the reasoning itself
        """
        result = self.validate(context_object)

        # Check agent's track record
        accuracy = self.get_agent_accuracy(agent_id)

        if accuracy < 0.5:
            result.add_check(ValidationCheck(
                category=ValidationCategory.SOURCE_CREDIBILITY,
                status=ValidationStatus.WARNING,
                message=f"Agent {agent_id} has low accuracy ({accuracy:.1%})",
                suggested_adjustment=-0.2,
            ))
        elif accuracy > 0.8:
            result.add_check(ValidationCheck(
                category=ValidationCategory.SOURCE_CREDIBILITY,
                status=ValidationStatus.PASSED,
                message=f"Agent {agent_id} has high accuracy ({accuracy:.1%})",
                suggested_adjustment=0.1,
            ))

        # Check if context was actually used
        if context_ids_used:
            result.add_check(ValidationCheck(
                category=ValidationCategory.CONTENT_QUALITY,
                status=ValidationStatus.PASSED,
                message=f"Reasoning references {len(context_ids_used)} context object(s)",
                suggested_adjustment=0.05,
            ))
        else:
            result.add_check(ValidationCheck(
                category=ValidationCategory.CONTENT_QUALITY,
                status=ValidationStatus.WARNING,
                message="No context referenced in reasoning",
                suggested_adjustment=-0.1,
            ))

        # Recalculate confidence
        self._calibrate_confidence(context_object, result)

        return result


class StructuredExhaustValidator(ExhaustValidator):
    """Specialized validator for structured exhaust (workflow events)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Track expected workflow patterns
        self._expected_patterns: Dict[str, List[str]] = {}

    def register_expected_pattern(self, workflow_id: str, event_sequence: List[str]) -> None:
        """Register an expected event sequence for a workflow."""
        self._expected_patterns[workflow_id] = event_sequence

    def validate_workflow_event(
        self,
        context_object: ContextObject,
        event_type: str,
        workflow_id: str,
    ) -> ValidationResult:
        """
        Validate a workflow event.

        Checks if the event is part of an expected pattern or
        represents a deviation (which might be valuable context).
        """
        result = self.validate(context_object)

        expected = self._expected_patterns.get(workflow_id, [])

        if expected:
            if event_type in expected:
                result.add_check(ValidationCheck(
                    category=ValidationCategory.CONTENT_QUALITY,
                    status=ValidationStatus.PASSED,
                    message=f"Event '{event_type}' matches expected workflow pattern",
                ))
            else:
                # Deviation from expected - this is often valuable!
                result.add_check(ValidationCheck(
                    category=ValidationCategory.CONTENT_QUALITY,
                    status=ValidationStatus.PASSED,
                    message=f"Event '{event_type}' is a deviation from expected pattern - potentially high value",
                    suggested_adjustment=0.1,  # Boost confidence for exceptions
                ))

        return result


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_validator_suite() -> Dict[str, ExhaustValidator]:
    """Create a complete suite of validators for all exhaust types."""
    return {
        "behavioral": BehavioralExhaustValidator(
            min_payload_length=30,
            strict_mode=False,
        ),
        "agent": AgentExhaustValidator(
            min_payload_length=50,
            require_structured_data=True,
        ),
        "structured": StructuredExhaustValidator(
            min_payload_length=20,
            require_structured_data=True,
        ),
        "general": ExhaustValidator(
            min_payload_length=20,
        ),
    }


def validate_before_deposit(
    context_object: ContextObject,
    validators: Dict[str, ExhaustValidator],
) -> ValidationResult:
    """
    Validate a context object using the appropriate validator.

    Args:
        context_object: The object to validate
        validators: Dictionary of validators by exhaust type

    Returns:
        ValidationResult with all checks
    """
    # Choose validator based on source type
    if context_object.source_type == SourceType.agent:
        validator = validators.get("agent", validators["general"])
    elif context_object.source_type == SourceType.human:
        # Could be behavioral or manual entry
        validator = validators.get("behavioral", validators["general"])
    elif context_object.source_type == SourceType.system:
        validator = validators.get("structured", validators["general"])
    else:
        validator = validators["general"]

    return validator.validate(context_object)
