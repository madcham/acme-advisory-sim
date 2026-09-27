"""
Tests for Context Bank core operations.

Tests:
- Deposit operations
- Retrieval operations
- Snapshot functionality
- Decay computation
- Validation recording
"""

import pytest
from datetime import datetime, timezone, timedelta

from bank.context_bank import ContextBank, DepositResult, BankSnapshot
from models.context_object import (
    ContextObject, ContentType, SourceType, DecayFunction,
    ContextGrade, OrgLineage,
)


class TestDeposit:
    """Tests for ContextBank.deposit()"""

    def test_deposit_minimal_object(self, empty_bank: ContextBank, minimal_context: ContextObject):
        """Test depositing a minimal valid context object."""
        result = empty_bank.deposit(minimal_context)

        assert result.success is True
        assert result.object_id == minimal_context.id
        assert result.error is None
        assert minimal_context.id in empty_bank

    def test_deposit_returns_deposit_result(self, empty_bank: ContextBank, minimal_context: ContextObject):
        """Test that deposit returns a DepositResult."""
        result = empty_bank.deposit(minimal_context)

        assert isinstance(result, DepositResult)
        assert hasattr(result, 'success')
        assert hasattr(result, 'object_id')
        assert hasattr(result, 'error')

    def test_deposit_duplicate_fails(self, empty_bank: ContextBank, minimal_context: ContextObject):
        """Test that depositing a duplicate ID fails."""
        # First deposit succeeds
        result1 = empty_bank.deposit(minimal_context)
        assert result1.success is True

        # Second deposit with same ID should fail
        result2 = empty_bank.deposit(minimal_context)
        assert result2.success is False
        assert "already exists" in result2.error.lower()

    def test_deposit_without_id_fails(self, empty_bank: ContextBank, base_time: datetime):
        """Test that depositing without an ID fails."""
        obj = ContextObject(
            id="",  # Empty ID
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="Test",
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.8,
        )

        result = empty_bank.deposit(obj)
        assert result.success is False

    def test_deposit_with_contradiction_checking(
        self,
        empty_bank: ContextBank,
        conflicting_context_pair: tuple,
    ):
        """Test that contradiction checking works during deposit."""
        original, conflicting = conflicting_context_pair

        # Deposit original
        result1 = empty_bank.deposit(original, check_contradictions=True)
        assert result1.success is True

        # Deposit conflicting - should still succeed but flag contradiction
        result2 = empty_bank.deposit(conflicting, check_contradictions=True)
        assert result2.success is True
        # Note: Contradiction detection is handled separately

    def test_deposit_increments_count(self, empty_bank: ContextBank, create_context_object):
        """Test that deposit increments object count."""
        assert len(empty_bank) == 0

        for i in range(5):
            obj = create_context_object(id=f"CTX-COUNT-{i}")
            empty_bank.deposit(obj)

        assert len(empty_bank) == 5


class TestRetrieval:
    """Tests for ContextBank retrieval operations."""

    def test_get_existing_object(self, seeded_bank: ContextBank, vendor_context: ContextObject):
        """Test retrieving an existing object by ID."""
        obj = seeded_bank.get(vendor_context.id)

        assert obj is not None
        assert obj.id == vendor_context.id
        assert obj.payload == vendor_context.payload

    def test_get_nonexistent_returns_none(self, seeded_bank: ContextBank):
        """Test that getting a nonexistent ID returns None."""
        obj = seeded_bank.get("CTX-NONEXISTENT")
        assert obj is None

    def test_contains_check(self, seeded_bank: ContextBank, vendor_context: ContextObject):
        """Test the __contains__ method."""
        assert vendor_context.id in seeded_bank
        assert "CTX-NONEXISTENT" not in seeded_bank

    def test_get_all_returns_list(self, seeded_bank: ContextBank):
        """Test that get_all returns a list of all objects."""
        all_objects = seeded_bank.get_all()

        assert isinstance(all_objects, list)
        assert len(all_objects) == len(seeded_bank)

    def test_get_by_workflow(self, full_bank: ContextBank):
        """Test filtering by workflow ID."""
        w4_objects = [obj for obj in full_bank.get_all() if obj.workflow_id == "W4"]

        assert len(w4_objects) > 0
        for obj in w4_objects:
            assert obj.workflow_id == "W4"

    def test_get_by_content_type(self, full_bank: ContextBank):
        """Test filtering by content type."""
        policies = [
            obj for obj in full_bank.get_all()
            if obj.content_type == ContentType.policy
        ]

        for obj in policies:
            assert obj.content_type == ContentType.policy


class TestDecay:
    """Tests for confidence decay computation."""

    def test_linear_decay(self, create_context_object):
        """Test linear decay function."""
        obj = create_context_object(
            decay_function=DecayFunction.linear,
            confidence=0.9,
            week=1,
        )
        obj.decay_rate = 0.1

        # Week 1: No decay
        conf_w1 = obj.compute_current_confidence(1)
        assert conf_w1 == 0.9

        # Week 5: 4 weeks of decay at 0.1/week
        conf_w5 = obj.compute_current_confidence(5)
        assert conf_w5 == pytest.approx(0.5, abs=0.01)

    def test_exponential_decay(self, create_context_object):
        """Test exponential decay function."""
        obj = create_context_object(
            decay_function=DecayFunction.exponential,
            confidence=1.0,
            week=1,
        )
        obj.decay_rate = 0.1

        # Week 1: No decay
        conf_w1 = obj.compute_current_confidence(1)
        assert conf_w1 == 1.0

        # Week 5: Exponential decay
        conf_w5 = obj.compute_current_confidence(5)
        # After 4 weeks: 1.0 * (0.9)^4 ≈ 0.6561
        assert conf_w5 == pytest.approx(0.6561, abs=0.01)

    def test_permanent_no_decay(self, create_context_object):
        """Test permanent decay function (no decay)."""
        obj = create_context_object(
            decay_function=DecayFunction.permanent,
            confidence=0.95,
            week=1,
        )

        # Should be same at any week
        assert obj.compute_current_confidence(1) == 0.95
        assert obj.compute_current_confidence(52) == 0.95
        assert obj.compute_current_confidence(100) == 0.95

    def test_step_function_decay(self, create_context_object):
        """Test step function decay."""
        obj = create_context_object(
            decay_function=DecayFunction.step_function,
            confidence=0.9,
            week=1,
        )

        # Before threshold (12 weeks): Full confidence
        assert obj.compute_current_confidence(10) == 0.9

        # After threshold: Drops to 30%
        conf_after = obj.compute_current_confidence(15)
        assert conf_after < 0.9
        assert conf_after >= 0.1

    def test_decay_minimum_floor(self, create_context_object):
        """Test that decay has a minimum floor."""
        obj = create_context_object(
            decay_function=DecayFunction.linear,
            confidence=0.5,
            week=1,
        )
        obj.decay_rate = 0.2

        # After many weeks, should hit floor
        conf = obj.compute_current_confidence(100)
        assert conf >= 0.05  # Minimum floor


class TestSnapshot:
    """Tests for bank snapshot functionality."""

    def test_snapshot_basic(self, seeded_bank: ContextBank):
        """Test basic snapshot creation."""
        snapshot = seeded_bank.snapshot()

        assert isinstance(snapshot, BankSnapshot)
        assert snapshot.total_objects == len(seeded_bank)

    def test_snapshot_by_grade(self, full_bank: ContextBank):
        """Test that snapshot includes grade breakdown."""
        snapshot = full_bank.snapshot()

        assert isinstance(snapshot.by_grade, dict)
        # Should have some graded objects
        total_graded = sum(snapshot.by_grade.values())
        assert total_graded > 0

    def test_snapshot_avg_confidence(self, seeded_bank: ContextBank):
        """Test average confidence calculation."""
        snapshot = seeded_bank.snapshot()

        assert 0.0 <= snapshot.avg_confidence <= 1.0


class TestValidationRecording:
    """Tests for validation recording on context objects."""

    def test_record_read(self, seeded_bank: ContextBank, vendor_context: ContextObject):
        """Test recording a read action."""
        seeded_bank.record_read(
            vendor_context.id,
            "test_agent",
            "Retrieved for vendor decision",
        )

        obj = seeded_bank.get(vendor_context.id)
        assert len(obj.read_by) == 1
        assert obj.read_by[0].agent_id == "test_agent"

    def test_record_action(self, seeded_bank: ContextBank, vendor_context: ContextObject):
        """Test recording an action."""
        seeded_bank.record_action(
            vendor_context.id,
            "vendor_agent",
            "Applied to SOW decision",
            outcome="correct",
        )

        obj = seeded_bank.get(vendor_context.id)
        assert len(obj.acted_on_by) == 1
        assert obj.acted_on_by[0].action_taken == "Applied to SOW decision"

    def test_record_validation(self, seeded_bank: ContextBank, vendor_context: ContextObject):
        """Test recording validation."""
        seeded_bank.record_validation(
            vendor_context.id,
            "human_reviewer",
            validated=True,
            notes="Confirmed accurate",
        )

        obj = seeded_bank.get(vendor_context.id)
        assert len(obj.validated_by) == 1
        assert obj.validated_by[0].validated is True

    def test_record_invalidation(self, seeded_bank: ContextBank, client_context: ContextObject):
        """Test recording invalidation."""
        seeded_bank.record_validation(
            client_context.id,
            "auditor",
            validated=False,
            notes="No longer accurate",
        )

        obj = seeded_bank.get(client_context.id)
        assert len(obj.invalidated_by) == 1
        assert obj.invalidated_by[0].validated is False


class TestSupersession:
    """Tests for context object supersession."""

    def test_supersede_object(self, seeded_bank: ContextBank, vendor_context: ContextObject, base_time: datetime):
        """Test superseding an existing object."""
        # Create new version
        new_version = ContextObject(
            id="CTX-VENDOR-002",
            display_name="Test Vendor: Updated Policy",
            created_at=base_time + timedelta(weeks=10),
            created_by="policy_team",
            source_type=SourceType.system,
            week=10,
            content_type=ContentType.policy,
            payload="Test Vendor now cleared for standard approval.",
            decay_function=DecayFunction.permanent,
            confidence_at_creation=0.95,
            supersedes=vendor_context.id,
        )

        # Deposit new version
        result = seeded_bank.deposit(new_version)
        assert result.success is True

        # Original should be marked as superseded
        original = seeded_bank.get(vendor_context.id)
        assert original.superseded_by == new_version.id

    def test_is_superseded_check(self, create_context_object):
        """Test the is_superseded method."""
        obj = create_context_object()

        assert obj.is_superseded() is False

        obj.superseded_by = "CTX-NEW-VERSION"
        assert obj.is_superseded() is True


class TestExport:
    """Tests for export functionality."""

    def test_export_to_dict(self, seeded_bank: ContextBank):
        """Test exporting bank to dictionary."""
        export = seeded_bank.export_to_dict()

        assert isinstance(export, dict)
        assert "objects" in export
        assert len(export["objects"]) == len(seeded_bank)

    def test_export_includes_all_objects(self, full_bank: ContextBank):
        """Test that export includes all objects."""
        export = full_bank.export_to_dict()

        object_ids = {obj["id"] for obj in export["objects"]}
        bank_ids = {obj.id for obj in full_bank.get_all()}

        assert object_ids == bank_ids
