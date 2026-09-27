"""
Tests for Chaos Engine.

Tests:
- Chaos event generation
- Knowledge departure effects
- Policy contradiction injection
- Agent drift effects
- Workload surge effects
- Impact tracking
"""

import pytest
from datetime import datetime, timezone, timedelta

from calibration.chaos_engine import ChaosEngine, ChaosImpact
from calibration.realism_config import (
    ChaosConfig, ChaosEvent, ChaosType,
    KnowledgeDepartureConfig, PolicyContradictionConfig,
    AgentDriftConfig, WorkloadSurgeConfig,
)
from models.context_object import (
    ContextObject, ContentType, SourceType, DecayFunction, ContextGrade,
)


class TestChaosConfig:
    """Tests for ChaosConfig and related classes."""

    def test_chaos_event_to_dict(self):
        """Test ChaosEvent serialization."""
        event = ChaosEvent(
            week=5,
            chaos_type=ChaosType.KNOWLEDGE_DEPARTURE,
            target="david_okafor",
            severity=0.7,
            description="Staff departure",
        )

        d = event.to_dict()

        assert d["week"] == 5
        assert d["chaos_type"] == "knowledge_departure"
        assert d["target"] == "david_okafor"
        assert d["severity"] == 0.7

    def test_chaos_config_disabled_returns_no_events(self):
        """Test that disabled chaos config returns no events via engine."""
        # The enabled flag is checked by ChaosEngine, not ChaosConfig
        config = ChaosConfig(enabled=False)
        engine = ChaosEngine(config=config)
        events = engine.get_events_for_week(4)  # Would have events if enabled
        assert events == []

    def test_chaos_config_returns_knowledge_departures(self):
        """Test knowledge departure events are returned."""
        config = ChaosConfig(
            enabled=True,
            knowledge_departure=KnowledgeDepartureConfig(
                departure_weeks=[4],
                departing_staff=["david_okafor"],
            ),
        )

        events = config.get_events_for_week(4)

        assert len(events) == 1
        assert events[0].chaos_type == ChaosType.KNOWLEDGE_DEPARTURE
        assert events[0].target == "david_okafor"

    def test_chaos_config_returns_policy_contradictions(self):
        """Test policy contradiction events are returned."""
        config = ChaosConfig(
            enabled=True,
            policy_contradiction=PolicyContradictionConfig(
                contradiction_scenarios=[{
                    "week": 5,
                    "original_context_id": "CTX-001",
                    "contradicting_payload": "New policy text",
                    "source": "policy_update",
                }],
            ),
        )

        events = config.get_events_for_week(5)

        assert len(events) == 1
        assert events[0].chaos_type == ChaosType.POLICY_CONTRADICTION
        assert events[0].target == "CTX-001"


class TestChaosEngine:
    """Tests for ChaosEngine class."""

    @pytest.fixture
    def enabled_config(self):
        """Return enabled chaos config."""
        return ChaosConfig(
            enabled=True,
            knowledge_departure=KnowledgeDepartureConfig(
                departure_weeks=[4],
                departing_staff=["david_okafor"],
            ),
            agent_drift=AgentDriftConfig(
                drift_start_weeks=[6],
                drifting_agents=["vendor_agent"],
                accuracy_degradation=1.5,
            ),
            workload_surge=WorkloadSurgeConfig(
                surge_weeks=[3],
                event_multiplier=2.5,
            ),
            random_chaos_probability=0.0,  # Disable random for tests
        )

    @pytest.fixture
    def engine(self, enabled_config):
        """Create chaos engine with fixed seed."""
        return ChaosEngine(config=enabled_config, seed=42)

    @pytest.fixture
    def base_time(self):
        return datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_engine_initialization(self, enabled_config):
        """Test engine initialization."""
        engine = ChaosEngine(config=enabled_config, seed=42)

        assert engine.config == enabled_config
        assert len(engine.active_knowledge_gaps) == 0
        assert len(engine.active_agent_drift) == 0
        assert engine.current_event_multiplier == 1.0

    def test_get_events_for_week_empty(self, engine):
        """Test getting events for week with no events."""
        events = engine.get_events_for_week(week=1)
        assert events == []

    def test_get_events_for_week_with_departure(self, engine):
        """Test getting events for week with knowledge departure."""
        events = engine.get_events_for_week(week=4)

        assert len(events) == 1
        assert events[0].chaos_type == ChaosType.KNOWLEDGE_DEPARTURE

    def test_reset_clears_state(self, engine, base_time):
        """Test that reset clears all state."""
        # Add some state
        event = ChaosEvent(
            week=4,
            chaos_type=ChaosType.KNOWLEDGE_DEPARTURE,
            target="david_okafor",
        )
        engine.apply_knowledge_departure(event, [], 4)
        engine.current_event_multiplier = 2.5

        engine.reset()

        assert len(engine.active_knowledge_gaps) == 0
        assert len(engine.active_agent_drift) == 0
        assert engine.current_event_multiplier == 1.0
        assert len(engine.impacts) == 0


class TestKnowledgeDeparture:
    """Tests for knowledge departure chaos effects."""

    @pytest.fixture
    def base_time(self):
        return datetime(2024, 1, 1, tzinfo=timezone.utc)

    @pytest.fixture
    def config(self):
        return ChaosConfig(
            enabled=True,
            knowledge_departure=KnowledgeDepartureConfig(
                departure_weeks=[4],
                departing_staff=["david_okafor"],
                confidence_decay_multiplier=2.0,
                mark_source_unavailable=True,
            ),
        )

    @pytest.fixture
    def engine(self, config):
        return ChaosEngine(config=config, seed=42)

    def test_knowledge_departure_degrades_objects(self, engine, base_time):
        """Test that knowledge departure degrades creator's objects."""
        # Create objects from departing staff
        obj = ContextObject(
            id="CTX-OKAFOR-001",
            created_at=base_time,
            created_by="david_okafor",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.tribal_knowledge,
            payload="Important knowledge from David Okafor.",
            decay_function=DecayFunction.linear,
            decay_rate=0.05,
            confidence_at_creation=0.9,
        )

        event = ChaosEvent(
            week=4,
            chaos_type=ChaosType.KNOWLEDGE_DEPARTURE,
            target="david_okafor",
        )

        impact = engine.apply_knowledge_departure(event, [obj], week=4)

        # Object should be degraded
        assert obj.id in impact.objects_degraded
        # Decay rate should be multiplied
        assert obj.decay_rate == 0.05 * 2.0
        # Source should be marked unavailable
        assert obj.structured_data.get("source_unavailable") is True
        assert obj.structured_data.get("departure_week") == 4

    def test_knowledge_departure_tracks_gap(self, engine):
        """Test that departure is tracked."""
        event = ChaosEvent(
            week=4,
            chaos_type=ChaosType.KNOWLEDGE_DEPARTURE,
            target="david_okafor",
        )

        engine.apply_knowledge_departure(event, [], week=4)

        assert engine.is_staff_departed("david_okafor") is True
        assert engine.is_staff_departed("other_staff") is False


class TestAgentDrift:
    """Tests for agent drift chaos effects."""

    @pytest.fixture
    def config(self):
        return ChaosConfig(
            enabled=True,
            agent_drift=AgentDriftConfig(
                drift_start_weeks=[6],
                drifting_agents=["vendor_agent"],
                accuracy_degradation=1.5,
                context_ignore_probability=0.3,
            ),
        )

    @pytest.fixture
    def engine(self, config):
        return ChaosEngine(config=config, seed=42)

    def test_agent_drift_adds_accuracy_modifier(self, engine):
        """Test that agent drift adds accuracy modifier."""
        event = ChaosEvent(
            week=6,
            chaos_type=ChaosType.AGENT_DRIFT,
            target="vendor_agent",
        )

        impact = engine.apply_agent_drift(event, week=6)

        assert "vendor_agent" in engine.active_agent_drift
        assert engine.get_agent_accuracy_modifier("vendor_agent") == 1.5
        assert impact.accuracy_modifier == 0.5  # 1.5 - 1.0

    def test_unaffected_agent_has_no_modifier(self, engine):
        """Test that unaffected agents have no modifier."""
        assert engine.get_agent_accuracy_modifier("proposal_agent") == 1.0

    def test_agent_drift_context_ignore_probability(self, engine):
        """Test context ignore probability for drifting agents."""
        event = ChaosEvent(
            week=6,
            chaos_type=ChaosType.AGENT_DRIFT,
            target="vendor_agent",
        )

        engine.apply_agent_drift(event, week=6)

        assert engine.get_context_ignore_probability("vendor_agent") == 0.3
        assert engine.get_context_ignore_probability("other_agent") == 0.0


class TestWorkloadSurge:
    """Tests for workload surge chaos effects."""

    @pytest.fixture
    def config(self):
        return ChaosConfig(
            enabled=True,
            workload_surge=WorkloadSurgeConfig(
                surge_weeks=[3],
                event_multiplier=2.5,
                causes_overload_errors=True,
                overload_error_increase=0.15,
            ),
        )

    @pytest.fixture
    def engine(self, config):
        return ChaosEngine(config=config, seed=42)

    def test_workload_surge_sets_multiplier(self, engine):
        """Test that workload surge sets event multiplier."""
        event = ChaosEvent(
            week=3,
            chaos_type=ChaosType.WORKLOAD_SURGE,
        )

        impact = engine.apply_workload_surge(event, week=3)

        assert engine.get_event_multiplier() == 2.5
        assert impact.event_multiplier == 2.5

    def test_workload_surge_overload_errors(self, engine):
        """Test that surge causes overload errors."""
        event = ChaosEvent(
            week=3,
            chaos_type=ChaosType.WORKLOAD_SURGE,
        )

        impact = engine.apply_workload_surge(event, week=3)

        assert impact.accuracy_modifier == 0.15


class TestPolicyContradiction:
    """Tests for policy contradiction chaos effects."""

    @pytest.fixture
    def config(self):
        return ChaosConfig(
            enabled=True,
            policy_contradiction=PolicyContradictionConfig(
                contradiction_scenarios=[{
                    "week": 5,
                    "original_context_id": "CTX-001",
                    "contradicting_payload": "Brightline is now cleared for standard process.",
                    "source": "policy_update",
                }],
            ),
        )

    @pytest.fixture
    def engine(self, config):
        return ChaosEngine(config=config, seed=42)

    def test_policy_contradiction_creates_object(self, engine):
        """Test that policy contradiction creates new object."""
        event = ChaosEvent(
            week=5,
            chaos_type=ChaosType.POLICY_CONTRADICTION,
            target="CTX-001",
        )

        impact, new_obj = engine.apply_policy_contradiction(event, [], week=5)

        assert new_obj is not None
        assert "Brightline" in new_obj.payload
        assert new_obj.structured_data.get("is_chaos_injection") is True
        assert new_obj.structured_data.get("contradicts") == "CTX-001"

    def test_policy_contradiction_tracks_original(self, engine):
        """Test that impact tracks contradicted object."""
        event = ChaosEvent(
            week=5,
            chaos_type=ChaosType.POLICY_CONTRADICTION,
            target="CTX-001",
        )

        impact, _ = engine.apply_policy_contradiction(event, [], week=5)

        assert "CTX-001" in impact.objects_contradicted


class TestApplyEvents:
    """Tests for applying multiple events."""

    @pytest.fixture
    def base_time(self):
        return datetime(2024, 1, 1, tzinfo=timezone.utc)

    @pytest.fixture
    def full_config(self):
        return ChaosConfig(
            enabled=True,
            knowledge_departure=KnowledgeDepartureConfig(
                departure_weeks=[4],
                departing_staff=["david_okafor"],
            ),
            agent_drift=AgentDriftConfig(
                drift_start_weeks=[4],
                drifting_agents=["vendor_agent"],
            ),
        )

    @pytest.fixture
    def engine(self, full_config):
        return ChaosEngine(config=full_config, seed=42)

    def test_apply_multiple_events(self, engine, base_time):
        """Test applying multiple events in one week."""
        obj = ContextObject(
            id="CTX-001",
            created_at=base_time,
            created_by="david_okafor",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="Knowledge from David.",
            decay_function=DecayFunction.linear,
            decay_rate=0.05,
            confidence_at_creation=0.8,
        )

        events = engine.get_events_for_week(4)
        impacts, new_objects = engine.apply_events(events, [obj], week=4)

        # Should have 2 impacts (departure + drift)
        assert len(impacts) == 2
        # Object should be degraded
        assert obj.decay_rate > 0.05
        # Agent should be drifting
        assert engine.get_agent_accuracy_modifier("vendor_agent") > 1.0


class TestImpactTracking:
    """Tests for impact tracking and summaries."""

    @pytest.fixture
    def config(self):
        return ChaosConfig(
            enabled=True,
            knowledge_departure=KnowledgeDepartureConfig(
                departure_weeks=[4],
                departing_staff=["david_okafor"],
            ),
        )

    @pytest.fixture
    def engine(self, config):
        return ChaosEngine(config=config, seed=42)

    def test_impact_to_dict(self):
        """Test ChaosImpact serialization."""
        event = ChaosEvent(
            week=4,
            chaos_type=ChaosType.KNOWLEDGE_DEPARTURE,
            target="david_okafor",
        )

        impact = ChaosImpact(
            event=event,
            objects_degraded=["CTX-001", "CTX-002"],
            accuracy_modifier=0.5,
            impact_description="Staff departed",
        )

        d = impact.to_dict()

        assert d["objects_degraded"] == ["CTX-001", "CTX-002"]
        assert d["accuracy_modifier"] == 0.5
        assert d["event"]["week"] == 4

    def test_get_impact_summary(self, engine, base_time):
        """Test getting impact summary."""
        obj = ContextObject(
            id="CTX-001",
            created_at=base_time,
            created_by="david_okafor",
            source_type=SourceType.human,
            week=1,
            content_type=ContentType.observation,
            payload="Test",
            decay_function=DecayFunction.linear,
            confidence_at_creation=0.8,
        )

        event = ChaosEvent(
            week=4,
            chaos_type=ChaosType.KNOWLEDGE_DEPARTURE,
            target="david_okafor",
        )
        engine.apply_knowledge_departure(event, [obj], week=4)

        summary = engine.get_impact_summary()

        assert summary["total_events"] == 1
        assert summary["knowledge_departures"] == 1
        assert summary["total_objects_degraded"] == 1


class TestRandomChaos:
    """Tests for random chaos event generation."""

    @pytest.fixture
    def config_with_random(self):
        return ChaosConfig(
            enabled=True,
            random_chaos_probability=1.0,  # Always generate random
        )

    @pytest.fixture
    def engine(self, config_with_random):
        return ChaosEngine(config=config_with_random, seed=42)

    def test_random_event_generation(self, engine):
        """Test that random events are generated."""
        events = engine.get_events_for_week(week=1)

        # Should have at least one random event
        assert len(events) >= 1

    def test_random_events_reproducible(self, config_with_random):
        """Test that random events are reproducible with same seed."""
        engine1 = ChaosEngine(config=config_with_random, seed=42)
        engine2 = ChaosEngine(config=config_with_random, seed=42)

        events1 = engine1.get_events_for_week(1)
        events2 = engine2.get_events_for_week(1)

        assert len(events1) == len(events2)
        if events1:
            assert events1[0].chaos_type == events2[0].chaos_type
