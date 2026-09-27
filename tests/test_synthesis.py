"""
Tests for Active Intelligence Synthesis Engine.

Tests:
- Pattern crystallization
- Validation propagation
- Adaptive decay adjustment
- Intelligence score computation
- Entity extraction
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock

from bank.synthesis import (
    SynthesisEngine,
    SynthesisResult,
    PatternCluster,
    compute_synthesis_intelligence_score,
    run_synthesis_pass,
)
from bank.context_bank import ContextBank
from models.context_object import (
    ContextObject, ContentType, SourceType, DecayFunction,
    ContextGrade, OrgLineage, AgentAction, ProvenanceLink,
)


class TestSynthesisResult:
    """Tests for SynthesisResult dataclass."""

    def test_result_defaults(self):
        """Test that SynthesisResult has correct defaults."""
        result = SynthesisResult()

        assert result.patterns_crystallized == 0
        assert result.validations_propagated == 0
        assert result.decay_rates_adjusted == 0
        assert result.new_objects_created == []
        assert result.objects_updated == []
        assert result.confidence_boosts == {}

    def test_result_to_dict(self):
        """Test conversion to dictionary."""
        result = SynthesisResult(
            patterns_crystallized=2,
            validations_propagated=5,
            new_objects_created=["CTX-001", "CTX-002"],
        )

        d = result.to_dict()

        assert d["patterns_crystallized"] == 2
        assert d["validations_propagated"] == 5
        assert d["new_objects_created"] == ["CTX-001", "CTX-002"]


class TestSynthesisEngine:
    """Tests for SynthesisEngine class."""

    @pytest.fixture
    def base_time(self):
        return datetime(2024, 1, 1, tzinfo=timezone.utc)

    @pytest.fixture
    def bank_with_patterns(self, base_time):
        """Create a bank with pattern-forming context objects."""
        bank = ContextBank(enable_validation=False)

        # Create 3+ objects about Brightline (forms a cluster)
        for i in range(4):
            obj = ContextObject(
                id=f"CTX-BRIGHT-{i}",
                created_at=base_time + timedelta(weeks=i),
                created_by=f"user_{i}",
                source_type=SourceType.human,
                week=i,
                content_type=ContentType.observation,
                payload=f"Brightline consulting always overbills. This is observation {i} about their billing practices.",
                structured_data={"vendor": "brightline"},
                decay_function=DecayFunction.linear,
                confidence_at_creation=0.75 + i * 0.05,
            )
            bank.deposit(obj, skip_validation=True)

        # Create 2 objects about TerraLogic (not enough to form pattern)
        for i in range(2):
            obj = ContextObject(
                id=f"CTX-TERRA-{i}",
                created_at=base_time + timedelta(weeks=i),
                created_by=f"user_{i}",
                source_type=SourceType.human,
                week=i,
                content_type=ContentType.observation,
                payload=f"TerraLogic pays slowly. Observation {i}.",
                structured_data={"client": "terralogic"},
                decay_function=DecayFunction.exponential,
                confidence_at_creation=0.8,
            )
            bank.deposit(obj, skip_validation=True)

        return bank

    @pytest.fixture
    def engine(self, bank_with_patterns):
        """Create synthesis engine with API disabled."""
        return SynthesisEngine(
            bank=bank_with_patterns,
            pattern_threshold=3,
            use_api=False,
        )

    def test_engine_initialization(self, bank_with_patterns):
        """Test engine initialization."""
        engine = SynthesisEngine(
            bank=bank_with_patterns,
            pattern_threshold=3,
            validation_boost=0.1,
            decay_reduction_factor=0.5,
            use_api=False,
        )

        assert engine.pattern_threshold == 3
        assert engine.validation_boost == 0.1
        assert engine.decay_reduction_factor == 0.5
        assert engine.use_api is False

    def test_identify_pattern_clusters(self, engine):
        """Test pattern cluster identification."""
        clusters = engine._identify_pattern_clusters(current_week=5)

        # Should find at least the Brightline cluster
        assert len(clusters) >= 1

        # Find the Brightline cluster
        brightline_cluster = None
        for cluster in clusters:
            if "brightline" in cluster.primary_entity:
                brightline_cluster = cluster
                break

        assert brightline_cluster is not None
        assert len(brightline_cluster.related_objects) >= 3

    def test_extract_entities(self, engine, base_time):
        """Test entity extraction from context object."""
        obj = ContextObject(
            id="CTX-TEST",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="Brightline and Okafor discussed the contract.",
            structured_data={"vendor": "brightline"},
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.8,
        )

        entities = engine._extract_entities(obj)

        assert "brightline" in entities
        assert "okafor" in entities

    def test_infer_pattern_type_vendor(self, engine):
        """Test pattern type inference for vendors."""
        pattern_type = engine._infer_pattern_type("brightline", [])
        assert pattern_type == "vendor_caution"

    def test_infer_pattern_type_client(self, engine):
        """Test pattern type inference for clients."""
        pattern_type = engine._infer_pattern_type("terralogic", [])
        assert pattern_type == "client_preference"

    def test_infer_pattern_type_stakeholder(self, engine):
        """Test pattern type inference for stakeholders."""
        pattern_type = engine._infer_pattern_type("okafor", [])
        assert pattern_type == "stakeholder_preference"


class TestPatternCrystallization:
    """Tests for pattern crystallization."""

    @pytest.fixture
    def base_time(self):
        return datetime(2024, 1, 1, tzinfo=timezone.utc)

    @pytest.fixture
    def bank_with_patterns(self, base_time):
        """Create bank with enough objects to form pattern."""
        bank = ContextBank(enable_validation=False)

        # 4 objects about Brightline
        for i in range(4):
            obj = ContextObject(
                id=f"CTX-BRIGHT-{i}",
                created_at=base_time + timedelta(weeks=i),
                created_by=f"user_{i}",
                source_type=SourceType.human,
                week=i,
                content_type=ContentType.observation,
                payload=f"Brightline overbilled 40% in 2022. Always require secondary approval. Observation {i}.",
                structured_data={"vendor": "brightline"},
                decay_function=DecayFunction.linear,
                confidence_at_creation=0.8,
            )
            bank.deposit(obj, skip_validation=True)

        return bank

    def test_crystallize_creates_new_object(self, bank_with_patterns, base_time):
        """Test that crystallization creates new synthesized objects."""
        engine = SynthesisEngine(
            bank=bank_with_patterns,
            pattern_threshold=3,
            use_api=False,
        )

        initial_count = len(bank_with_patterns)
        created_ids = engine._crystallize_patterns(current_week=5)

        # Should create at least one crystallized object
        assert len(created_ids) >= 1

        # Bank should have more objects now
        assert len(bank_with_patterns) > initial_count

    def test_crystallized_object_properties(self, bank_with_patterns, base_time):
        """Test properties of crystallized object."""
        engine = SynthesisEngine(
            bank=bank_with_patterns,
            pattern_threshold=3,
            use_api=False,
        )

        created_ids = engine._crystallize_patterns(current_week=5)
        assert len(created_ids) > 0

        crystal = bank_with_patterns.get(created_ids[0])

        # Check properties
        assert crystal.source_type == SourceType.derived
        assert crystal.content_type == ContentType.inference
        assert crystal.decay_function == DecayFunction.permanent
        assert crystal.context_grade == ContextGrade.institutional_memory
        assert "brightline" in crystal.payload.lower()

        # Check structured data
        assert crystal.structured_data.get("crystallized_from") == "brightline"
        assert crystal.structured_data.get("pattern_type") == "vendor_caution"
        assert crystal.structured_data.get("source_count") >= 3

    def test_no_duplicate_crystals(self, bank_with_patterns, base_time):
        """Test that running crystallization twice doesn't create duplicates."""
        engine = SynthesisEngine(
            bank=bank_with_patterns,
            pattern_threshold=3,
            use_api=False,
        )

        # First pass
        created_1 = engine._crystallize_patterns(current_week=5)
        count_after_first = len(bank_with_patterns)

        # Second pass
        created_2 = engine._crystallize_patterns(current_week=6)

        # Should not create new crystals for same pattern
        assert len(created_2) == 0
        assert len(bank_with_patterns) == count_after_first


class TestValidationPropagation:
    """Tests for validation propagation."""

    @pytest.fixture
    def base_time(self):
        return datetime(2024, 1, 1, tzinfo=timezone.utc)

    @pytest.fixture
    def bank_with_validations(self, base_time):
        """Create bank with validated objects."""
        bank = ContextBank(enable_validation=False)

        # Object that has been acted on with correct outcome
        obj = ContextObject(
            id="CTX-VALIDATED",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="This is validated knowledge about the process.",
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.7,
        )
        obj.acted_on_by.append(AgentAction(
            agent_id="vendor_agent",
            timestamp=base_time,
            action_taken="Applied to decision",
            outcome="correct",
        ))
        bank.deposit(obj, skip_validation=True)

        return bank

    def test_validation_propagation_boosts_confidence(self, bank_with_validations):
        """Test that validation propagation boosts confidence."""
        engine = SynthesisEngine(
            bank=bank_with_validations,
            validation_boost=0.1,
            use_api=False,
        )

        result = engine._propagate_validations(current_week=5)

        assert result["count"] >= 1
        assert "CTX-VALIDATED" in result["boosts"]
        assert result["boosts"]["CTX-VALIDATED"] > 0.7  # Original confidence


class TestAdaptiveDecay:
    """Tests for adaptive decay adjustment."""

    @pytest.fixture
    def base_time(self):
        return datetime(2024, 1, 1, tzinfo=timezone.utc)

    @pytest.fixture
    def bank_with_active_objects(self, base_time):
        """Create bank with frequently used objects."""
        bank = ContextBank(enable_validation=False)

        # Object with high activity
        obj = ContextObject(
            id="CTX-ACTIVE",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="This is frequently accessed knowledge.",
            decay_function=DecayFunction.linear,
            decay_rate=0.1,
            confidence_at_creation=0.8,
        )
        # Add multiple reads
        for i in range(4):
            obj.record_read(f"agent_{i}", f"Read for decision {i}")
        bank.deposit(obj, skip_validation=True)

        # Object with low activity
        inactive = ContextObject(
            id="CTX-INACTIVE",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="This is rarely accessed knowledge.",
            decay_function=DecayFunction.linear,
            decay_rate=0.1,
            confidence_at_creation=0.8,
        )
        bank.deposit(inactive, skip_validation=True)

        return bank

    def test_high_activity_reduces_decay(self, bank_with_active_objects):
        """Test that high activity reduces decay rate."""
        engine = SynthesisEngine(
            bank=bank_with_active_objects,
            decay_reduction_factor=0.5,
            use_api=False,
        )

        adjusted = engine._adjust_decay_rates(current_week=5)

        # Active object should have adjusted decay
        assert "CTX-ACTIVE" in adjusted

        active_obj = bank_with_active_objects.get("CTX-ACTIVE")
        assert active_obj.decay_rate < 0.1  # Original rate was 0.1

    def test_permanent_objects_not_adjusted(self, base_time):
        """Test that permanent objects are not adjusted."""
        bank = ContextBank(enable_validation=False)

        obj = ContextObject(
            id="CTX-PERM",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.system,
            week=1,
            content_type=ContentType.policy,
            payload="Permanent policy.",
            decay_function=DecayFunction.permanent,
            confidence_at_creation=0.95,
        )
        # Add activity
        for i in range(5):
            obj.record_read(f"agent_{i}", "Read")
        bank.deposit(obj, skip_validation=True)

        engine = SynthesisEngine(bank=bank, use_api=False)
        adjusted = engine._adjust_decay_rates(current_week=5)

        # Should not be in adjusted list
        assert "CTX-PERM" not in adjusted


class TestRunSynthesisPass:
    """Tests for complete synthesis pass."""

    @pytest.fixture
    def base_time(self):
        return datetime(2024, 1, 1, tzinfo=timezone.utc)

    @pytest.fixture
    def full_bank(self, base_time):
        """Create a bank with various patterns and activities."""
        bank = ContextBank(enable_validation=False)

        # Brightline pattern (4 objects)
        for i in range(4):
            obj = ContextObject(
                id=f"CTX-BRIGHT-{i}",
                created_at=base_time + timedelta(weeks=i),
                created_by=f"user_{i}",
                source_type=SourceType.human,
                week=i,
                content_type=ContentType.observation,
                payload=f"Brightline overbilled 40%. Always require approval. Note {i}.",
                structured_data={"vendor": "brightline"},
                decay_function=DecayFunction.linear,
                decay_rate=0.1,
                confidence_at_creation=0.8,
            )
            bank.deposit(obj, skip_validation=True)

        # Validated object
        validated = ContextObject(
            id="CTX-VALIDATED",
            created_at=base_time,
            created_by="test",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="Validated knowledge.",
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.7,
        )
        validated.acted_on_by.append(AgentAction(
            agent_id="agent",
            timestamp=base_time,
            action_taken="Used",
            outcome="correct",
        ))
        bank.deposit(validated, skip_validation=True)

        return bank

    def test_full_synthesis_pass(self, full_bank):
        """Test running a complete synthesis pass."""
        result = run_synthesis_pass(
            bank=full_bank,
            current_week=10,
            pattern_threshold=3,
        )

        assert isinstance(result, SynthesisResult)
        # Should have crystallized the Brightline pattern
        assert result.patterns_crystallized >= 1
        # Should have propagated validation
        assert result.validations_propagated >= 1


class TestIntelligenceScore:
    """Tests for intelligence score computation."""

    def test_zero_bank_returns_zero(self):
        """Test that empty bank returns zero score."""
        result = SynthesisResult()
        score = compute_synthesis_intelligence_score(result, bank_size=0)
        assert score == 0.0

    def test_active_synthesis_has_score(self):
        """Test that active synthesis has positive score."""
        result = SynthesisResult(
            patterns_crystallized=3,
            validations_propagated=5,
            decay_rates_adjusted=2,
            confidence_boosts={"CTX-001": 0.85, "CTX-002": 0.9},
        )

        score = compute_synthesis_intelligence_score(result, bank_size=50)

        assert score > 0
        assert score <= 1.0

    def test_no_activity_low_score(self):
        """Test that no synthesis activity gives low score."""
        result = SynthesisResult()  # All zeros
        score = compute_synthesis_intelligence_score(result, bank_size=50)
        assert score == 0.0


class TestFallbackSynthesis:
    """Tests for fallback synthesis (no API)."""

    @pytest.fixture
    def base_time(self):
        return datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_fallback_generates_meaningful_prose(self, base_time):
        """Test that fallback synthesis creates meaningful content."""
        bank = ContextBank(enable_validation=False)

        # Create Brightline pattern
        for i in range(3):
            obj = ContextObject(
                id=f"CTX-BRIGHT-{i}",
                created_at=base_time,
                created_by=f"user_{i}",
                source_type=SourceType.human,
                week=1,
                content_type=ContentType.observation,
                payload=f"Brightline overbilled 40% in 2022. David Okafor must approve.",
                structured_data={"vendor": "brightline"},
                decay_function=DecayFunction.linear,
                confidence_at_creation=0.8,
            )
            bank.deposit(obj, skip_validation=True)

        engine = SynthesisEngine(bank=bank, pattern_threshold=3, use_api=False)

        # Get the cluster
        clusters = engine._identify_pattern_clusters(current_week=5)
        brightline_cluster = next(c for c in clusters if "brightline" in c.primary_entity)

        # Generate fallback synthesis
        prose = engine._generate_fallback_synthesis(brightline_cluster)

        # Should contain meaningful content
        assert "Brightline" in prose
        assert len(prose) > 50
        assert "40%" in prose or "approval" in prose.lower()
