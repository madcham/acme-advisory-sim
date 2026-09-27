"""
Tests for Contradiction Detection.

Tests:
- Entity extraction
- Direct opposition detection
- Value conflict detection
- Temporal supersession
- Rule-based detection patterns
- Integration with Context Bank
"""

import pytest
from datetime import datetime, timezone, timedelta

from bank.contradiction import (
    ContradictionDetector,
    Contradiction,
    extract_entities,
    detect_contradictions_batch,
)
from models.context_object import (
    ContextObject, ContentType, SourceType, DecayFunction, ContextGrade,
)


class TestEntityExtraction:
    """Tests for entity extraction from context objects."""

    def test_extract_vendor_entity(self):
        """Test extracting vendor entities from payload."""
        payload = "Brightline consulting always overbills on federal contracts."
        entities = extract_entities(payload)

        assert "brightline" in entities

    def test_extract_client_entity(self):
        """Test extracting client entities from payload."""
        payload = "TerraLogic has a history of delayed payments."
        entities = extract_entities(payload)

        assert "terralogic" in entities

    def test_extract_person_entity(self):
        """Test extracting person entities from payload."""
        payload = "David Okafor must approve all vendor contracts over $50k."
        entities = extract_entities(payload)

        assert "okafor" in entities or "david" in entities

    def test_extract_from_structured_data(self):
        """Test extracting entities from structured data."""
        payload = "There's an issue with this vendor."
        structured_data = {"vendor": "brightline"}

        entities = extract_entities(payload, structured_data)

        assert "brightline" in entities

    def test_exclude_generic_terms(self):
        """Test that generic terms are excluded from entities."""
        payload = "SOW process requires approval for policy review."
        entities = extract_entities(payload)

        # These should NOT be extracted as entities
        assert "sow" not in entities
        assert "process" not in entities
        assert "approval" not in entities
        assert "policy" not in entities

    def test_multiple_entities(self):
        """Test extracting multiple entities."""
        payload = "Brightline and TerraLogic have a partnership."
        entities = extract_entities(payload)

        assert "brightline" in entities
        assert "terralogic" in entities


class TestContradictionDetector:
    """Tests for ContradictionDetector class."""

    @pytest.fixture
    def detector(self):
        """Return a detector with API disabled for tests."""
        return ContradictionDetector(use_api=False)

    @pytest.fixture
    def base_time(self):
        return datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_no_contradiction_without_shared_entities(self, detector, base_time):
        """Test that objects without shared entities don't conflict."""
        obj1 = ContextObject(
            id="CTX-001",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="Brightline always requires secondary approval.",
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.9,
        )

        obj2 = ContextObject(
            id="CTX-002",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="TerraLogic never pays on time.",
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.9,
        )

        contradictions = detector.detect(obj1, [obj2], current_week=1)

        assert len(contradictions) == 0

    def test_value_conflict_detection(self, detector, base_time):
        """Test detection of value conflicts in structured data."""
        obj1 = ContextObject(
            id="CTX-001",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.policy,
            payload="TerraLogic escalation threshold is 45 days.",
            structured_data={
                "client": "terralogic",
                "escalation_threshold_days": 45,
            },
            decay_function=DecayFunction.permanent,
            confidence_at_creation=0.9,
        )

        obj2 = ContextObject(
            id="CTX-002",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="TerraLogic actually requires 65 days before escalation.",
            structured_data={
                "client": "terralogic",
                "escalation_threshold_days": 65,
            },
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.9,
        )

        contradictions = detector.detect(obj1, [obj2], current_week=1)

        assert len(contradictions) == 1
        assert contradictions[0].contradiction_type == "value_conflict"
        assert "terralogic" in contradictions[0].shared_entities

    def test_skip_low_confidence_objects(self, detector, base_time):
        """Test that low-confidence objects are skipped."""
        low_conf = ContextObject(
            id="CTX-LOW",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="Brightline is terrible.",
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.3,  # Below 0.5 threshold
        )

        high_conf = ContextObject(
            id="CTX-HIGH",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="Brightline is excellent.",
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.9,
        )

        # Low confidence new object should produce no contradictions
        contradictions = detector.detect(low_conf, [high_conf], current_week=1)
        assert len(contradictions) == 0


class TestOppositionPatterns:
    """Tests for linguistic opposition pattern detection."""

    @pytest.fixture
    def detector(self):
        return ContradictionDetector(use_api=False)

    def test_sentences_oppose_always_never(self, detector):
        """Test detection of always/never opposition."""
        sent1 = "brightline always requires secondary approval"
        sent2 = "brightline never requires secondary approval"

        assert detector._sentences_oppose(sent1, sent2) is True

    def test_sentences_oppose_must_must_not(self, detector):
        """Test detection of must/must not opposition."""
        sent1 = "you must escalate terralogic after 45 days"
        sent2 = "you must not escalate terralogic before 65 days"

        assert detector._sentences_oppose(sent1, sent2) is True

    def test_sentences_do_not_oppose_unrelated(self, detector):
        """Test that unrelated sentences don't oppose."""
        sent1 = "brightline requires secondary approval"
        sent2 = "brightline is based in chicago"

        assert detector._sentences_oppose(sent1, sent2) is False


class TestDirectOppositionDetection:
    """Tests for direct opposition detection with multiple shared entities."""

    @pytest.fixture
    def detector(self):
        return ContradictionDetector(use_api=False)

    @pytest.fixture
    def base_time(self):
        return datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_opposition_with_multiple_entities(self, detector, base_time):
        """Test opposition detection requires multiple shared entities."""
        # Objects sharing two entities (brightline + okafor)
        obj1 = ContextObject(
            id="CTX-001",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.policy,
            payload="For Brightline contracts, Okafor must always approve before signing.",
            structured_data={"vendor": "brightline", "approver": "okafor"},
            decay_function=DecayFunction.permanent,
            confidence_at_creation=0.9,
        )

        obj2 = ContextObject(
            id="CTX-002",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=2,
            content_type=ContentType.observation,
            payload="For Brightline, Okafor said approval is never required for small SOWs.",
            structured_data={"vendor": "brightline", "approver": "okafor"},
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.8,
        )

        contradictions = detector.detect(obj2, [obj1], current_week=2)

        assert len(contradictions) == 1
        assert contradictions[0].contradiction_type == "direct_opposition"


class TestTemporalSupersession:
    """Tests for temporal supersession detection."""

    @pytest.fixture
    def detector(self):
        return ContradictionDetector(use_api=False)

    @pytest.fixture
    def base_time(self):
        return datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_detect_supersession_with_expired_process(self, detector, base_time):
        """Test detection of supersession when old process is expired."""
        old_obj = ContextObject(
            id="CTX-OLD",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.policy,
            payload="Brightline requires form A for all contracts.",
            structured_data={"vendor": "brightline"},
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.8,
            context_grade=ContextGrade.expired_process,
        )

        new_obj = ContextObject(
            id="CTX-NEW",
            created_at=base_time + timedelta(weeks=20),
            created_by="test",
            source_type=SourceType.human,
            week=21,
            content_type=ContentType.policy,
            payload="Starting in 2024, Brightline now uses the new streamlined process.",
            structured_data={"vendor": "brightline"},
            decay_function=DecayFunction.permanent,
            confidence_at_creation=0.95,
        )

        contradictions = detector.detect(new_obj, [old_obj], current_week=21)

        assert len(contradictions) == 1
        assert contradictions[0].contradiction_type == "outdated_superseded"


class TestBatchContradictionDetection:
    """Tests for batch contradiction detection."""

    @pytest.fixture
    def base_time(self):
        return datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_batch_detection(self, base_time):
        """Test detecting contradictions across a batch of objects."""
        objects = [
            ContextObject(
                id="CTX-001",
                created_at=base_time,
                created_by="test",
                source_type=SourceType.human,
                week=1,
                content_type=ContentType.policy,
                payload="TerraLogic payment cycle is 30 days.",
                structured_data={"client": "terralogic", "payment_days": 30},
                decay_function=DecayFunction.permanent,
                confidence_at_creation=0.9,
            ),
            ContextObject(
                id="CTX-002",
                created_at=base_time,
                created_by="test",
                source_type=SourceType.human,
                week=2,
                content_type=ContentType.observation,
                payload="TerraLogic actually pays on 60-day cycle.",
                structured_data={"client": "terralogic", "payment_days": 60},
                decay_function=DecayFunction.linear,
                confidence_at_creation=0.85,
            ),
            ContextObject(
                id="CTX-003",
                created_at=base_time,
                created_by="test",
                source_type=SourceType.human,
                week=1,
                content_type=ContentType.observation,
                payload="Brightline is based in Chicago.",
                structured_data={"vendor": "brightline"},
                decay_function=DecayFunction.linear,
                confidence_at_creation=0.8,
            ),
        ]

        contradictions = detect_contradictions_batch(objects, use_api=False)

        # Should find the TerraLogic payment conflict
        assert len(contradictions) == 1
        assert "terralogic" in contradictions[0].shared_entities

    def test_batch_no_contradictions(self, base_time):
        """Test batch with no contradictions."""
        objects = [
            ContextObject(
                id="CTX-001",
                created_at=base_time,
                created_by="test",
                source_type=SourceType.human,
                week=1,
                content_type=ContentType.observation,
                payload="Brightline is a vendor.",
                decay_function=DecayFunction.linear,
                confidence_at_creation=0.8,
            ),
            ContextObject(
                id="CTX-002",
                created_at=base_time,
                created_by="test",
                source_type=SourceType.human,
                week=1,
                content_type=ContentType.observation,
                payload="TerraLogic is a client.",
                decay_function=DecayFunction.linear,
                confidence_at_creation=0.8,
            ),
        ]

        contradictions = detect_contradictions_batch(objects, use_api=False)

        assert len(contradictions) == 0


class TestContradictionInContextBank:
    """Tests for contradiction detection integration with Context Bank."""

    @pytest.fixture
    def base_time(self):
        return datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_deposit_detects_contradiction(self, base_time):
        """Test that deposit detects and records contradictions."""
        from bank.context_bank import ContextBank

        bank = ContextBank(enable_validation=False)

        # Deposit first object
        obj1 = ContextObject(
            id="CTX-001",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.policy,
            payload="TerraLogic escalation threshold is 45 days.",
            structured_data={"client": "terralogic", "escalation_threshold_days": 45},
            decay_function=DecayFunction.permanent,
            confidence_at_creation=0.9,
        )
        bank.deposit(obj1)

        # Deposit conflicting object
        obj2 = ContextObject(
            id="CTX-002",
            created_at=base_time + timedelta(weeks=1),
            created_by="test",
            source_type=SourceType.human,
            week=2,
            content_type=ContentType.observation,
            payload="TerraLogic escalation threshold should be 65 days.",
            structured_data={"client": "terralogic", "escalation_threshold_days": 65},
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.85,
        )
        result = bank.deposit(obj2)

        assert result.success is True
        assert len(result.contradictions_detected) == 1
        assert result.contradictions_detected[0].contradiction_type == "value_conflict"

    def test_contradiction_updates_objects(self, base_time):
        """Test that detected contradictions update object contradicts lists."""
        from bank.context_bank import ContextBank

        bank = ContextBank(enable_validation=False)

        obj1 = ContextObject(
            id="CTX-A",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.policy,
            payload="TerraLogic uses 30-day payment cycle.",
            structured_data={"client": "terralogic", "payment_days": 30},
            decay_function=DecayFunction.permanent,
            confidence_at_creation=0.9,
        )
        bank.deposit(obj1)

        obj2 = ContextObject(
            id="CTX-B",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=2,
            content_type=ContentType.observation,
            payload="TerraLogic actually uses 60-day payment cycle.",
            structured_data={"client": "terralogic", "payment_days": 60},
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.85,
        )
        bank.deposit(obj2)

        # Check that both objects have their contradicts lists updated
        retrieved_obj1 = bank.get("CTX-A")
        retrieved_obj2 = bank.get("CTX-B")

        assert "CTX-B" in retrieved_obj1.contradicts
        assert "CTX-A" in retrieved_obj2.contradicts

    def test_get_contradictions(self, base_time):
        """Test retrieving all contradictions from bank."""
        from bank.context_bank import ContextBank

        bank = ContextBank(enable_validation=False)

        # Create objects with value conflict
        obj1 = ContextObject(
            id="CTX-1",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.policy,
            payload="Brightline requires 24 hours notice.",
            structured_data={"vendor": "brightline", "notice_hours": 24},
            decay_function=DecayFunction.permanent,
            confidence_at_creation=0.9,
        )
        obj2 = ContextObject(
            id="CTX-2",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=2,
            content_type=ContentType.observation,
            payload="Brightline actually requires 48 hours notice.",
            structured_data={"vendor": "brightline", "notice_hours": 48},
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.85,
        )

        bank.deposit(obj1)
        bank.deposit(obj2)

        all_contradictions = bank.get_contradictions()

        assert len(all_contradictions) == 1
        assert all_contradictions[0].contradiction_type == "value_conflict"
