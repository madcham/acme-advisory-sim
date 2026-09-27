"""
Tests for Validation Integration in Context Bank Deposit.

Tests:
- Validation runs during deposit
- Confidence adjustment applied from validation
- Validation failure blocks deposit
- skip_validation bypasses validation
- Source profile registration
"""

import pytest
from datetime import datetime, timezone

from bank.context_bank import ContextBank, DepositResult
from bank.validation import (
    SourceCredibilityProfile,
    ValidationStatus,
    ValidationResult,
)
from models.context_object import (
    ContextObject, ContentType, SourceType, DecayFunction,
)


class TestValidationIntegration:
    """Tests for validation during deposit."""

    @pytest.fixture
    def bank_with_validation(self):
        """Return a bank with validation enabled (default)."""
        return ContextBank(enable_validation=True)

    @pytest.fixture
    def bank_without_validation(self):
        """Return a bank with validation disabled."""
        return ContextBank(enable_validation=False)

    def test_deposit_runs_validation(self, bank_with_validation, base_time):
        """Test that deposit runs validation and returns result."""
        context = ContextObject(
            id="CTX-VAL-001",
            created_at=base_time,
            created_by="test_user",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="This is a valid observation with sufficient length.",
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.8,
        )

        result = bank_with_validation.deposit(context)

        assert result.success is True
        assert result.validation_result is not None
        assert isinstance(result.validation_result, ValidationResult)

    def test_deposit_without_validation_skips(self, bank_without_validation, base_time):
        """Test that validation disabled means no validation result."""
        context = ContextObject(
            id="CTX-NOVAL-001",
            created_at=base_time,
            created_by="test_user",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="Short",  # Would trigger warning with validation
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.8,
        )

        result = bank_without_validation.deposit(context)

        assert result.success is True
        assert result.validation_result is None

    def test_skip_validation_flag(self, bank_with_validation, base_time):
        """Test that skip_validation=True bypasses validation."""
        context = ContextObject(
            id="CTX-SKIP-001",
            created_at=base_time,
            created_by="test_user",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="Short",  # Would trigger warning
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.8,
        )

        result = bank_with_validation.deposit(context, skip_validation=True)

        assert result.success is True
        assert result.validation_result is None


class TestConfidenceAdjustment:
    """Tests for confidence adjustment during deposit."""

    @pytest.fixture
    def bank(self):
        return ContextBank(enable_validation=True)

    def test_high_credibility_source_boosts_confidence(self, bank, base_time):
        """Test that high-credibility sources get confidence boost."""
        # Register a senior source profile
        senior_profile = SourceCredibilityProfile(
            source_id="senior_partner",
            source_type=SourceType.human,
            tenure_years=20.0,
            role_authority_level=5,
            past_validation_rate=0.95,
        )
        bank.register_source_profile(senior_profile)

        context = ContextObject(
            id="CTX-SENIOR-001",
            created_at=base_time,
            created_by="senior_partner",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.tribal_knowledge,
            payload="Based on 20 years experience, this vendor always requires extra oversight.",
            decay_function=DecayFunction.step_function,
            confidence_at_creation=0.75,
        )

        result = bank.deposit(context)

        assert result.success is True
        # Confidence should be boosted
        assert result.adjusted_confidence is not None
        assert result.adjusted_confidence > result.original_confidence

    def test_low_credibility_source_reduces_confidence(self, bank, base_time):
        """Test that low-credibility sources get confidence reduction."""
        # Register a junior source profile
        junior_profile = SourceCredibilityProfile(
            source_id="new_hire",
            source_type=SourceType.human,
            tenure_years=0.3,
            role_authority_level=1,
            past_validation_rate=0.3,
        )
        bank.register_source_profile(junior_profile)

        context = ContextObject(
            id="CTX-JUNIOR-001",
            created_at=base_time,
            created_by="new_hire",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="I think maybe probably this might sometimes be the case.",  # Vague
            decay_function=DecayFunction.exponential,
            confidence_at_creation=0.75,
        )

        result = bank.deposit(context)

        assert result.success is True
        # Confidence should be reduced (low credibility + vague language)
        assert result.adjusted_confidence is not None
        assert result.adjusted_confidence < result.original_confidence

    def test_original_confidence_preserved(self, bank, base_time):
        """Test that original confidence is preserved in result."""
        context = ContextObject(
            id="CTX-ORIG-001",
            created_at=base_time,
            created_by="test_user",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="This is an observation with good length and content.",
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.85,
        )

        result = bank.deposit(context)

        assert result.original_confidence == 0.85


class TestValidationFailure:
    """Tests for validation failure blocking deposit."""

    @pytest.fixture
    def bank(self):
        return ContextBank(enable_validation=True)

    def test_empty_payload_fails_validation(self, bank, base_time):
        """Test that empty payload fails validation and blocks deposit."""
        context = ContextObject(
            id="CTX-EMPTY-001",
            created_at=base_time,
            created_by="test_user",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="",  # Empty payload
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.8,
        )

        result = bank.deposit(context)

        assert result.success is False
        assert result.validation_result is not None
        assert result.validation_result.overall_status == ValidationStatus.FAILED
        # Object should NOT be in bank
        assert context.id not in bank

    def test_failed_validation_does_not_store(self, bank, base_time):
        """Test that failed validation prevents object storage."""
        context = ContextObject(
            id="CTX-FAIL-001",
            created_at=base_time,
            created_by="test_user",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="",  # Will fail
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.8,
        )

        initial_count = len(bank)
        result = bank.deposit(context)

        assert result.success is False
        assert len(bank) == initial_count  # No new objects


class TestPolicyRegistration:
    """Tests for policy registration and consistency checking."""

    @pytest.fixture
    def bank(self):
        return ContextBank(enable_validation=True)

    def test_register_policy(self, bank, base_time):
        """Test registering a policy with the bank."""
        policy = ContextObject(
            id="POL-001",
            created_at=base_time,
            created_by="policy_team",
            source_type=SourceType.system,
            week=1,
            content_type=ContentType.policy,
            payload="All vendor contracts over $50k require secondary approval.",
            structured_data={"threshold": 50000, "approval_type": "secondary"},
            decay_function=DecayFunction.permanent,
            confidence_at_creation=0.95,
        )

        bank.register_policy(policy)

        # Check policy is registered in all validators
        for validator in bank.validators.values():
            assert policy.id in validator._documented_policies


class TestDepositMany:
    """Tests for bulk deposit with validation."""

    @pytest.fixture
    def bank(self):
        return ContextBank(enable_validation=True)

    def test_deposit_many_with_validation(self, bank, base_time):
        """Test depositing multiple objects with validation."""
        objects = [
            ContextObject(
                id=f"CTX-MANY-{i}",
                created_at=base_time,
                created_by="test_user",
                source_type=SourceType.human,
                week=1,
                content_type=ContentType.observation,
                payload=f"Observation number {i} with sufficient length.",
                decay_function=DecayFunction.linear,
                confidence_at_creation=0.8,
            )
            for i in range(5)
        ]

        results = bank.deposit_many(objects)

        assert len(results) == 5
        assert all(r.success for r in results)
        assert len(bank) == 5

    def test_deposit_many_skip_validation(self, bank, base_time):
        """Test bulk deposit with validation skipped."""
        objects = [
            ContextObject(
                id=f"CTX-BULK-{i}",
                created_at=base_time,
                created_by="test_user",
                source_type=SourceType.human,
                week=1,
                content_type=ContentType.observation,
                payload="Short",  # Would warn with validation
                decay_function=DecayFunction.linear,
                confidence_at_creation=0.8,
            )
            for i in range(3)
        ]

        results = bank.deposit_many(objects, skip_validation=True)

        assert len(results) == 3
        assert all(r.success for r in results)
        # No validation results when skipped
        assert all(r.validation_result is None for r in results)
