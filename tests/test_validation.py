"""
Tests for Input Validation Layer.

Tests:
- Source credibility scoring
- Content quality checks
- Policy consistency validation
- Confidence calibration
- Specialized validators (behavioral, agent, structured)
"""

import pytest
from datetime import datetime, timezone

from bank.validation import (
    ExhaustValidator,
    BehavioralExhaustValidator,
    AgentExhaustValidator,
    StructuredExhaustValidator,
    ValidationResult,
    ValidationStatus,
    ValidationCategory,
    SourceCredibilityProfile,
    create_validator_suite,
    validate_before_deposit,
)
from models.context_object import (
    ContextObject, ContentType, SourceType, DecayFunction,
)


class TestSourceCredibilityProfile:
    """Tests for source credibility scoring."""

    def test_high_credibility_senior(self):
        """Test that senior employees get high credibility."""
        profile = SourceCredibilityProfile(
            source_id="senior_consultant",
            source_type=SourceType.human,
            tenure_years=15.0,
            role_authority_level=4,
            past_validation_rate=0.9,
        )

        score = profile.compute_credibility_score()
        assert score > 0.7  # High credibility

    def test_low_credibility_junior(self):
        """Test that new employees get lower credibility."""
        profile = SourceCredibilityProfile(
            source_id="new_hire",
            source_type=SourceType.human,
            tenure_years=0.5,
            role_authority_level=1,
            past_validation_rate=0.3,
        )

        score = profile.compute_credibility_score()
        assert score < 0.4  # Low credibility

    def test_credibility_bounded(self):
        """Test that credibility score is bounded 0-1."""
        # Maximum profile
        max_profile = SourceCredibilityProfile(
            source_id="ceo",
            source_type=SourceType.human,
            tenure_years=30.0,
            role_authority_level=5,
            past_validation_rate=1.0,
        )
        assert max_profile.compute_credibility_score() <= 1.0

        # Minimum profile
        min_profile = SourceCredibilityProfile(
            source_id="temp",
            source_type=SourceType.human,
            tenure_years=0.0,
            role_authority_level=1,
            past_validation_rate=0.0,
        )
        assert min_profile.compute_credibility_score() >= 0.0


class TestExhaustValidator:
    """Tests for base ExhaustValidator."""

    @pytest.fixture
    def validator(self):
        return ExhaustValidator(
            min_payload_length=20,
            min_confidence_threshold=0.3,
        )

    @pytest.fixture
    def valid_context(self, base_time):
        return ContextObject(
            id="CTX-VALID-001",
            created_at=base_time,
            created_by="test_user",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="This is a sufficiently long and meaningful observation about the process.",
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.8,
        )

    def test_validate_returns_result(self, validator, valid_context):
        """Test that validate returns ValidationResult."""
        result = validator.validate(valid_context)

        assert isinstance(result, ValidationResult)
        assert result.object_id == valid_context.id

    def test_valid_context_passes(self, validator, valid_context):
        """Test that a valid context allows deposit (even if needs review)."""
        result = validator.validate(valid_context)

        # Unknown sources trigger NEEDS_REVIEW, but should_deposit is still True
        assert result.should_deposit is True
        # The overall status may be NEEDS_REVIEW for unknown sources, which is expected

    def test_short_payload_warning(self, validator, base_time):
        """Test that short payloads get a warning."""
        short_context = ContextObject(
            id="CTX-SHORT-001",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="Too short",  # Less than 20 chars
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.8,
        )

        result = validator.validate(short_context)

        # Should have a warning about payload length
        warnings = [c for c in result.checks if c.status == ValidationStatus.WARNING]
        assert len(warnings) > 0

    def test_missing_payload_fails(self, validator, base_time):
        """Test that missing payload fails validation."""
        no_payload = ContextObject(
            id="CTX-NOPAYLOAD",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="",  # Empty payload
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.8,
        )

        result = validator.validate(no_payload)

        assert result.overall_status == ValidationStatus.FAILED
        assert result.should_deposit is False

    def test_vague_language_warning(self, validator, base_time):
        """Test that vague language gets a warning."""
        vague_context = ContextObject(
            id="CTX-VAGUE-001",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="I think maybe probably this might sometimes be the case, perhaps.",
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.8,
        )

        result = validator.validate(vague_context)

        # Should have warning about vague language
        quality_checks = [
            c for c in result.checks
            if c.category == ValidationCategory.CONTENT_QUALITY
        ]
        vague_warnings = [c for c in quality_checks if "vague" in c.message.lower()]
        assert len(vague_warnings) > 0

    def test_high_value_language_boost(self, validator, base_time):
        """Test that actionable language gets a confidence boost."""
        actionable = ContextObject(
            id="CTX-ACTION-001",
            created_at=base_time,
            created_by="policy_team",
            source_type=SourceType.system,
            week=1,
            content_type=ContentType.policy,
            payload="This vendor always requires approval from the Finance Director. Never proceed without it.",
            decay_function=DecayFunction.permanent,
            confidence_at_creation=0.8,
        )

        result = validator.validate(actionable)

        # Should have positive adjustment
        assert result.adjusted_confidence is not None
        assert result.adjusted_confidence >= actionable.confidence_at_creation


class TestSourceCredibilityValidation:
    """Tests for source credibility validation."""

    @pytest.fixture
    def validator_with_profiles(self):
        validator = ExhaustValidator()

        # Register some source profiles
        senior = SourceCredibilityProfile(
            source_id="senior_partner",
            source_type=SourceType.human,
            tenure_years=20.0,
            role_authority_level=5,
            past_validation_rate=0.95,
        )
        junior = SourceCredibilityProfile(
            source_id="new_analyst",
            source_type=SourceType.human,
            tenure_years=0.3,
            role_authority_level=1,
            past_validation_rate=0.4,
        )

        validator.register_source_profile(senior)
        validator.register_source_profile(junior)

        return validator

    def test_high_credibility_source_boost(self, validator_with_profiles, base_time):
        """Test that high-credibility source gets confidence boost."""
        context = ContextObject(
            id="CTX-SENIOR-001",
            created_at=base_time,
            created_by="senior_partner",  # High credibility
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.tribal_knowledge,
            payload="Based on 20 years of experience, this vendor always overbills on federal contracts.",
            decay_function=DecayFunction.step_function,
            confidence_at_creation=0.75,
        )

        result = validator_with_profiles.validate(context)

        # Should get a boost
        assert result.adjusted_confidence > context.confidence_at_creation

    def test_low_credibility_source_reduction(self, validator_with_profiles, base_time):
        """Test that low-credibility source gets confidence reduction."""
        context = ContextObject(
            id="CTX-JUNIOR-001",
            created_at=base_time,
            created_by="new_analyst",  # Low credibility
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="I heard from someone that this vendor might have issues. Not sure though.",
            decay_function=DecayFunction.exponential,
            confidence_at_creation=0.75,
        )

        result = validator_with_profiles.validate(context)

        # Should get a reduction (low credibility + vague language)
        assert result.adjusted_confidence < context.confidence_at_creation


class TestBehavioralExhaustValidator:
    """Tests for behavioral exhaust validation."""

    @pytest.fixture
    def validator(self):
        return BehavioralExhaustValidator()

    def test_senior_to_junior_transfer_boost(self, validator, base_time):
        """Test that senior-to-junior knowledge transfer gets boost."""
        senior = SourceCredibilityProfile(
            source_id="veteran",
            source_type=SourceType.human,
            tenure_years=15.0,
            role_authority_level=4,
            past_validation_rate=0.85,
        )
        junior = SourceCredibilityProfile(
            source_id="newbie",
            source_type=SourceType.human,
            tenure_years=0.5,
            role_authority_level=1,
            past_validation_rate=0.5,
        )

        context = ContextObject(
            id="CTX-TRANSFER-001",
            created_at=base_time,
            created_by="veteran",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.tribal_knowledge,
            payload="When newbie asked about vendor approvals, veteran explained the secondary approval requirement for Brightline.",
            decay_function=DecayFunction.exponential,
            confidence_at_creation=0.7,
        )

        result = validator.validate_knowledge_transfer(junior, senior, context)

        # Should allow deposit (source credibility may trigger NEEDS_REVIEW for unknown sources)
        assert result.should_deposit is True
        # The senior-to-junior pattern should add a positive check
        credibility_checks = [
            c for c in result.checks
            if c.category == ValidationCategory.SOURCE_CREDIBILITY
        ]
        assert any("senior to junior" in c.message.lower() for c in credibility_checks)


class TestAgentExhaustValidator:
    """Tests for agent exhaust validation."""

    @pytest.fixture
    def validator(self):
        return AgentExhaustValidator()

    def test_high_accuracy_agent_boost(self, validator, base_time):
        """Test that high-accuracy agent gets confidence boost."""
        # Record good track record
        for _ in range(10):
            validator.record_agent_outcome("vendor_agent", was_correct=True)

        context = ContextObject(
            id="CTX-AGENT-001",
            created_at=base_time,
            created_by="vendor_agent",
            source_type=SourceType.agent,
            week=1,
            content_type=ContentType.decision,
            payload="Agent decided to route through secondary approval based on CTX-001 about Brightline overbilling history.",
            structured_data={"scenario_type": "vendor_sow", "context_used": ["CTX-001"]},
            decay_function=DecayFunction.exponential,
            confidence_at_creation=0.8,
        )

        result = validator.validate_agent_reasoning(
            "vendor_agent",
            context,
            context_ids_used=["CTX-001"],
        )

        # Should get boost for high accuracy
        assert result.adjusted_confidence >= context.confidence_at_creation

    def test_low_accuracy_agent_reduction(self, validator, base_time):
        """Test that low-accuracy agent gets confidence reduction."""
        # Record poor track record
        for _ in range(10):
            validator.record_agent_outcome("bad_agent", was_correct=False)

        context = ContextObject(
            id="CTX-BADAGENT-001",
            created_at=base_time,
            created_by="bad_agent",
            source_type=SourceType.agent,
            week=1,
            content_type=ContentType.inference,
            payload="Agent inferred that standard approval is fine for this vendor.",
            decay_function=DecayFunction.exponential,
            confidence_at_creation=0.8,
        )

        result = validator.validate_agent_reasoning(
            "bad_agent",
            context,
            context_ids_used=[],
        )

        # Should get reduction for low accuracy + no context used
        assert result.adjusted_confidence < context.confidence_at_creation

    def test_no_context_used_warning(self, validator, base_time):
        """Test warning when agent doesn't reference context."""
        context = ContextObject(
            id="CTX-NOREF-001",
            created_at=base_time,
            created_by="vendor_agent",
            source_type=SourceType.agent,
            week=1,
            content_type=ContentType.decision,
            payload="Agent decided to proceed with standard approval process.",
            decay_function=DecayFunction.exponential,
            confidence_at_creation=0.8,
        )

        result = validator.validate_agent_reasoning(
            "vendor_agent",
            context,
            context_ids_used=[],  # No context referenced
        )

        # Should have warning about no context
        warnings = [c for c in result.checks if c.status == ValidationStatus.WARNING]
        assert any("context" in c.message.lower() for c in warnings)


class TestValidatorSuite:
    """Tests for validator suite factory."""

    def test_create_validator_suite(self):
        """Test creating a complete validator suite."""
        suite = create_validator_suite()

        assert "behavioral" in suite
        assert "agent" in suite
        assert "structured" in suite
        assert "general" in suite

        assert isinstance(suite["behavioral"], BehavioralExhaustValidator)
        assert isinstance(suite["agent"], AgentExhaustValidator)
        assert isinstance(suite["structured"], StructuredExhaustValidator)

    def test_validate_before_deposit_selects_correct_validator(self, base_time):
        """Test that validate_before_deposit selects the right validator."""
        suite = create_validator_suite()

        # Agent context should use agent validator
        agent_context = ContextObject(
            id="CTX-AGENT-TEST",
            created_at=base_time,
            created_by="test_agent",
            source_type=SourceType.agent,
            week=1,
            content_type=ContentType.decision,
            payload="Agent made a decision about this scenario based on available context.",
            structured_data={"scenario_type": "test"},
            decay_function=DecayFunction.exponential,
            confidence_at_creation=0.8,
        )

        result = validate_before_deposit(agent_context, suite)
        assert isinstance(result, ValidationResult)

        # Human context should use behavioral validator
        human_context = ContextObject(
            id="CTX-HUMAN-TEST",
            created_at=base_time,
            created_by="employee",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="Employee observed that this process usually takes longer than expected.",
            decay_function=DecayFunction.exponential,
            confidence_at_creation=0.7,
        )

        result = validate_before_deposit(human_context, suite)
        assert isinstance(result, ValidationResult)


class TestConfidenceCalibration:
    """Tests for confidence calibration based on validation."""

    @pytest.fixture
    def validator(self):
        return ExhaustValidator()

    def test_confidence_stays_in_bounds(self, validator, base_time):
        """Test that adjusted confidence stays between 0.3 and 1.0."""
        # Very low initial confidence + bad quality
        low_context = ContextObject(
            id="CTX-LOW-001",
            created_at=base_time,
            created_by="unknown",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="Maybe probably perhaps this might sometimes possibly be true, I think.",
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.35,
        )

        result = validator.validate(low_context)

        if result.adjusted_confidence is not None:
            assert result.adjusted_confidence >= 0.3  # Minimum threshold
            assert result.adjusted_confidence <= 1.0

    def test_multiple_adjustments_combine(self, validator, base_time):
        """Test that multiple positive/negative adjustments combine."""
        # Good content from unknown source
        context = ContextObject(
            id="CTX-MIXED-001",
            created_at=base_time,
            created_by="unknown_source",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.policy,
            payload="This vendor always requires secondary approval from David Okafor. Never skip this step. Documented in policy #123.",
            structured_data={"vendor": "test", "policy_number": "123"},
            decay_function=DecayFunction.permanent,
            confidence_at_creation=0.7,
        )

        result = validator.validate(context)

        # Should have multiple checks
        assert len(result.checks) >= 2
