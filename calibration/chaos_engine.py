"""
Chaos Engine for Simulation Realism.

Implements disruption mechanisms that test Context Bank resilience:
- Knowledge departure: Senior staff leave, taking undocumented context
- Policy contradiction: Conflicting policies are introduced
- Agent drift: Agents begin making suboptimal decisions
- Workload surge: Event volume spikes cause overload
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timezone
import random
import copy

from calibration.realism_config import (
    ChaosConfig, ChaosEvent, ChaosType,
    KnowledgeDepartureConfig, PolicyContradictionConfig,
    AgentDriftConfig, WorkloadSurgeConfig,
)
from models.context_object import (
    ContextObject, ContentType, SourceType, DecayFunction, ContextGrade,
)


@dataclass
class ChaosImpact:
    """Impact of a chaos event on simulation state."""
    event: ChaosEvent

    # Objects affected
    objects_degraded: List[str] = field(default_factory=list)
    objects_contradicted: List[str] = field(default_factory=list)
    objects_created: List[str] = field(default_factory=list)

    # Metrics impact
    accuracy_modifier: float = 0.0  # Added to error rate
    confidence_modifier: float = 0.0  # Multiplied to decay rate
    event_multiplier: float = 1.0  # Event count multiplier

    # Qualitative impact
    impact_description: str = ""

    def to_dict(self) -> Dict:
        return {
            "event": self.event.to_dict(),
            "objects_degraded": self.objects_degraded,
            "objects_contradicted": self.objects_contradicted,
            "objects_created": self.objects_created,
            "accuracy_modifier": self.accuracy_modifier,
            "confidence_modifier": self.confidence_modifier,
            "event_multiplier": self.event_multiplier,
            "impact_description": self.impact_description,
        }


class ChaosEngine:
    """
    Generates and applies chaos events to test Context Bank resilience.

    Chaos mechanisms simulate real organizational disruptions:
    1. Knowledge departure - tests memory persistence when creators leave
    2. Policy contradiction - tests contradiction detection and resolution
    3. Agent drift - tests whether context retrieval corrects agent errors
    4. Workload surge - tests performance under load
    """

    def __init__(
        self,
        config: Optional[ChaosConfig] = None,
        seed: Optional[int] = None,
    ):
        """
        Initialize chaos engine.

        Args:
            config: Chaos configuration (uses default if None)
            seed: Random seed for reproducibility
        """
        self.config = config or ChaosConfig()
        self.rng = random.Random(seed)

        # Track active effects
        self.active_knowledge_gaps: Dict[str, int] = {}  # staff_id -> departure_week
        self.active_agent_drift: Dict[str, float] = {}  # agent_id -> degradation
        self.current_event_multiplier: float = 1.0

        # Track all impacts
        self.impacts: List[ChaosImpact] = []

    def get_events_for_week(self, week: int) -> List[ChaosEvent]:
        """
        Get chaos events for a specific week.

        Combines configured events with random events if enabled.
        """
        events = []

        if not self.config.enabled:
            return events

        # Get configured events
        events.extend(self.config.get_events_for_week(week))

        # Add random events
        if self.rng.random() < self.config.random_chaos_probability:
            random_event = self._generate_random_event(week)
            if random_event:
                events.append(random_event)

        return events

    def _generate_random_event(self, week: int) -> Optional[ChaosEvent]:
        """Generate a random chaos event."""
        chaos_type = self.rng.choice(list(ChaosType))

        if chaos_type == ChaosType.KNOWLEDGE_DEPARTURE:
            staff = self.rng.choice([
                "elena_vasquez", "james_holloway", "sarah_chen", "priya_nair"
            ])
            return ChaosEvent(
                week=week,
                chaos_type=chaos_type,
                target=staff,
                severity=self.rng.uniform(0.3, 0.7),
                description=f"Random departure: {staff}",
            )

        elif chaos_type == ChaosType.AGENT_DRIFT:
            agent = self.rng.choice([
                "vendor_agent", "proposal_agent", "billing_agent", "staffing_agent"
            ])
            return ChaosEvent(
                week=week,
                chaos_type=chaos_type,
                target=agent,
                severity=self.rng.uniform(0.2, 0.5),
                description=f"Random drift: {agent}",
            )

        elif chaos_type == ChaosType.WORKLOAD_SURGE:
            return ChaosEvent(
                week=week,
                chaos_type=chaos_type,
                target=None,
                severity=self.rng.uniform(0.5, 1.5),
                description="Random workload surge",
            )

        return None

    def apply_knowledge_departure(
        self,
        event: ChaosEvent,
        context_objects: List[ContextObject],
        week: int,
    ) -> ChaosImpact:
        """
        Apply knowledge departure chaos.

        When a staff member departs:
        1. Context objects they created have confidence decay accelerated
        2. Their tacit knowledge (not deposited) is lost forever
        3. Objects they validated become less reliable
        """
        impact = ChaosImpact(
            event=event,
            impact_description=f"Staff {event.target} departed, degrading associated context",
        )

        staff_id = event.target
        self.active_knowledge_gaps[staff_id] = week

        # Find and degrade objects created by departing staff
        for obj in context_objects:
            created_by_match = (
                obj.created_by and
                (staff_id in obj.created_by.lower() or
                 staff_id.replace("_", " ") in obj.created_by.lower())
            )

            if created_by_match:
                # Accelerate decay
                original_decay = obj.decay_rate or 0.05
                obj.decay_rate = original_decay * self.config.knowledge_departure.confidence_decay_multiplier

                # Add metadata about source unavailability
                if self.config.knowledge_departure.mark_source_unavailable:
                    if obj.structured_data is None:
                        obj.structured_data = {}
                    obj.structured_data["source_unavailable"] = True
                    obj.structured_data["departure_week"] = week

                impact.objects_degraded.append(obj.id)

        impact.confidence_modifier = self.config.knowledge_departure.confidence_decay_multiplier

        self.impacts.append(impact)
        return impact

    def apply_policy_contradiction(
        self,
        event: ChaosEvent,
        existing_objects: List[ContextObject],
        week: int,
    ) -> Tuple[ChaosImpact, Optional[ContextObject]]:
        """
        Apply policy contradiction chaos.

        Introduces a new context object that contradicts an existing one.
        Tests the contradiction detection system.
        """
        impact = ChaosImpact(
            event=event,
            impact_description=f"Contradicting policy introduced for {event.target}",
        )

        # Find the scenario for this event
        scenario = None
        for s in self.config.policy_contradiction.contradiction_scenarios:
            if s["week"] == week and s["original_context_id"] == event.target:
                scenario = s
                break

        if not scenario:
            return impact, None

        # Create contradicting context object
        contradicting_obj = ContextObject(
            created_by=scenario["source"],
            source_type=SourceType.human,
            week=week,
            content_type=ContentType.policy,
            payload=scenario["contradicting_payload"],
            structured_data={
                "is_chaos_injection": True,
                "contradicts": scenario["original_context_id"],
            },
            decay_function=DecayFunction.linear,
            decay_rate=0.08,
            confidence_at_creation=0.85,  # High confidence to create conflict
        )

        impact.objects_created.append(contradicting_obj.id)
        impact.objects_contradicted.append(scenario["original_context_id"])

        self.impacts.append(impact)
        return impact, contradicting_obj

    def apply_agent_drift(
        self,
        event: ChaosEvent,
        week: int,
    ) -> ChaosImpact:
        """
        Apply agent drift chaos.

        Agent begins making worse decisions:
        1. Higher error rate
        2. May ignore retrieved context
        3. Effect persists until end of simulation
        """
        impact = ChaosImpact(
            event=event,
            impact_description=f"Agent {event.target} performance degrading",
        )

        agent_id = event.target
        degradation = self.config.agent_drift.accuracy_degradation

        # Store active drift
        self.active_agent_drift[agent_id] = degradation

        impact.accuracy_modifier = degradation - 1.0  # Convert to additive error

        self.impacts.append(impact)
        return impact

    def apply_workload_surge(
        self,
        event: ChaosEvent,
        week: int,
    ) -> ChaosImpact:
        """
        Apply workload surge chaos.

        Increases event count and potentially causes overload errors.
        """
        impact = ChaosImpact(
            event=event,
            impact_description=f"Workload surge: {self.config.workload_surge.event_multiplier}x volume",
        )

        self.current_event_multiplier = self.config.workload_surge.event_multiplier
        impact.event_multiplier = self.current_event_multiplier

        if self.config.workload_surge.causes_overload_errors:
            impact.accuracy_modifier = self.config.workload_surge.overload_error_increase

        self.impacts.append(impact)
        return impact

    def apply_events(
        self,
        events: List[ChaosEvent],
        context_objects: List[ContextObject],
        week: int,
    ) -> Tuple[List[ChaosImpact], List[ContextObject]]:
        """
        Apply all chaos events for a week.

        Returns:
            Tuple of (impacts, new_context_objects_to_deposit)
        """
        impacts = []
        new_objects = []

        # Reset per-week effects
        self.current_event_multiplier = 1.0

        for event in events:
            if event.chaos_type == ChaosType.KNOWLEDGE_DEPARTURE:
                impact = self.apply_knowledge_departure(event, context_objects, week)
                impacts.append(impact)

            elif event.chaos_type == ChaosType.POLICY_CONTRADICTION:
                impact, new_obj = self.apply_policy_contradiction(
                    event, context_objects, week
                )
                impacts.append(impact)
                if new_obj:
                    new_objects.append(new_obj)

            elif event.chaos_type == ChaosType.AGENT_DRIFT:
                impact = self.apply_agent_drift(event, week)
                impacts.append(impact)

            elif event.chaos_type == ChaosType.WORKLOAD_SURGE:
                impact = self.apply_workload_surge(event, week)
                impacts.append(impact)

        return impacts, new_objects

    def get_agent_accuracy_modifier(self, agent_id: str) -> float:
        """
        Get accuracy modifier for an agent due to drift.

        Returns:
            Error rate multiplier (1.0 = no change, >1.0 = more errors)
        """
        return self.active_agent_drift.get(agent_id, 1.0)

    def get_context_ignore_probability(self, agent_id: str) -> float:
        """
        Get probability that agent ignores retrieved context.

        Returns:
            Probability (0.0 = never ignore, 1.0 = always ignore)
        """
        if agent_id in self.active_agent_drift:
            return self.config.agent_drift.context_ignore_probability
        return 0.0

    def get_event_multiplier(self) -> float:
        """Get current event count multiplier."""
        return self.current_event_multiplier

    def is_staff_departed(self, staff_id: str) -> bool:
        """Check if a staff member has departed."""
        return staff_id in self.active_knowledge_gaps

    def get_impact_summary(self) -> Dict[str, Any]:
        """Get summary of all chaos impacts."""
        return {
            "total_events": len(self.impacts),
            "knowledge_departures": len(self.active_knowledge_gaps),
            "agent_drifts": len(self.active_agent_drift),
            "total_objects_degraded": sum(
                len(i.objects_degraded) for i in self.impacts
            ),
            "total_objects_contradicted": sum(
                len(i.objects_contradicted) for i in self.impacts
            ),
            "total_objects_created": sum(
                len(i.objects_created) for i in self.impacts
            ),
            "impacts": [i.to_dict() for i in self.impacts],
        }

    def reset(self):
        """Reset chaos engine state for new simulation run."""
        self.active_knowledge_gaps.clear()
        self.active_agent_drift.clear()
        self.current_event_multiplier = 1.0
        self.impacts.clear()
