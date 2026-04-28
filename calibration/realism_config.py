"""
Realism Configuration for Simulation.

Defines configuration for BPI-calibrated parameters and chaos mechanisms.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class ChaosType(Enum):
    """Types of chaos events that can disrupt the simulation."""
    KNOWLEDGE_DEPARTURE = "knowledge_departure"  # Senior staff leaves
    POLICY_CONTRADICTION = "policy_contradiction"  # Conflicting policies introduced
    AGENT_DRIFT = "agent_drift"  # Agent begins making suboptimal decisions
    CONTEXT_CORRUPTION = "context_corruption"  # Context object becomes unreliable
    WORKLOAD_SURGE = "workload_surge"  # Sudden spike in events


@dataclass
class ChaosEvent:
    """A single chaos event to inject into simulation."""
    week: int
    chaos_type: ChaosType
    target: Optional[str] = None  # staff_id, context_id, agent_id, etc.
    severity: float = 0.5  # 0.0 = mild, 1.0 = severe
    description: str = ""

    def to_dict(self) -> Dict:
        return {
            "week": self.week,
            "chaos_type": self.chaos_type.value,
            "target": self.target,
            "severity": self.severity,
            "description": self.description,
        }


@dataclass
class KnowledgeDepartureConfig:
    """Configuration for knowledge departure chaos."""
    # Weeks when senior staff depart
    departure_weeks: List[int] = field(default_factory=lambda: [4, 8])

    # IDs of staff who depart (maps to context objects they created)
    departing_staff: List[str] = field(default_factory=lambda: [
        "david_okafor",  # Finance head - knows Brightline history
        "marcus_webb",   # Senior partner - knows client override patterns
    ])

    # Impact on context confidence when creator departs
    confidence_decay_multiplier: float = 2.0

    # Whether to mark departed staff's context as "source unavailable"
    mark_source_unavailable: bool = True


@dataclass
class PolicyContradictionConfig:
    """Configuration for policy contradiction injection."""
    # Weeks when contradicting policies appear
    injection_weeks: List[int] = field(default_factory=lambda: [5, 9])

    # Types of contradictions to inject
    contradiction_scenarios: List[Dict] = field(default_factory=lambda: [
        {
            "week": 5,
            "original_context_id": "CTX-001",  # Brightline secondary approval
            "contradicting_payload": "Brightline Consulting has been cleared for standard SOW process after 2025 audit.",
            "source": "compliance_update_2025",
        },
        {
            "week": 9,
            "original_context_id": "CTX-006",  # TerraLogic payment timing
            "contradicting_payload": "TerraLogic now pays within 30 days per new CFO policy. Standard escalation applies.",
            "source": "ar_policy_update",
        },
    ])


@dataclass
class AgentDriftConfig:
    """Configuration for agent performance drift."""
    # Weeks when agents begin drifting
    drift_start_weeks: List[int] = field(default_factory=lambda: [6, 10])

    # Agents that drift
    drifting_agents: List[str] = field(default_factory=lambda: [
        "vendor_agent",
        "billing_agent",
    ])

    # How much accuracy degrades (multiplier on error rate)
    accuracy_degradation: float = 1.5

    # Probability of ignoring retrieved context
    context_ignore_probability: float = 0.3


@dataclass
class WorkloadSurgeConfig:
    """Configuration for workload surge events."""
    # Weeks with workload surges
    surge_weeks: List[int] = field(default_factory=lambda: [3, 7])

    # Event multiplier during surge
    event_multiplier: float = 2.5

    # Whether surge affects agent accuracy (overload)
    causes_overload_errors: bool = True

    # Error rate increase during overload
    overload_error_increase: float = 0.15


@dataclass
class ChaosConfig:
    """Complete chaos configuration."""
    enabled: bool = False

    knowledge_departure: KnowledgeDepartureConfig = field(
        default_factory=KnowledgeDepartureConfig
    )
    policy_contradiction: PolicyContradictionConfig = field(
        default_factory=PolicyContradictionConfig
    )
    agent_drift: AgentDriftConfig = field(
        default_factory=AgentDriftConfig
    )
    workload_surge: WorkloadSurgeConfig = field(
        default_factory=WorkloadSurgeConfig
    )

    # Random chaos events (in addition to configured ones)
    random_chaos_probability: float = 0.1  # Per week

    def get_events_for_week(self, week: int) -> List[ChaosEvent]:
        """Get all configured chaos events for a specific week."""
        events = []

        # Knowledge departures
        if week in self.knowledge_departure.departure_weeks:
            for staff in self.knowledge_departure.departing_staff:
                events.append(ChaosEvent(
                    week=week,
                    chaos_type=ChaosType.KNOWLEDGE_DEPARTURE,
                    target=staff,
                    severity=0.7,
                    description=f"{staff} has departed the organization",
                ))

        # Policy contradictions
        for scenario in self.policy_contradiction.contradiction_scenarios:
            if scenario["week"] == week:
                events.append(ChaosEvent(
                    week=week,
                    chaos_type=ChaosType.POLICY_CONTRADICTION,
                    target=scenario["original_context_id"],
                    severity=0.6,
                    description=scenario["contradicting_payload"][:100],
                ))

        # Agent drift
        if week in self.agent_drift.drift_start_weeks:
            for agent in self.agent_drift.drifting_agents:
                events.append(ChaosEvent(
                    week=week,
                    chaos_type=ChaosType.AGENT_DRIFT,
                    target=agent,
                    severity=self.agent_drift.accuracy_degradation - 1.0,
                    description=f"{agent} performance degradation begins",
                ))

        # Workload surges
        if week in self.workload_surge.surge_weeks:
            events.append(ChaosEvent(
                week=week,
                chaos_type=ChaosType.WORKLOAD_SURGE,
                target=None,
                severity=self.workload_surge.event_multiplier - 1.0,
                description=f"Workload surge: {self.workload_surge.event_multiplier}x normal volume",
            ))

        return events


@dataclass
class BPICalibrationConfig:
    """Configuration for BPI-based calibration."""
    enabled: bool = True

    # Which BPI dataset to use
    dataset: str = "BPI2012"

    # Scale factor for event counts (BPI has ~5000/week, Acme ~150)
    event_scale_factor: float = 0.001

    # Whether to use BPI timing distributions
    use_timing_distribution: bool = True

    # Whether to use BPI resource patterns
    use_resource_patterns: bool = True

    # Whether to use BPI workflow complexity
    use_workflow_complexity: bool = True


@dataclass
class RealismConfig:
    """Complete realism configuration for simulation."""
    # BPI calibration settings
    bpi_calibration: BPICalibrationConfig = field(
        default_factory=BPICalibrationConfig
    )

    # Chaos injection settings
    chaos: ChaosConfig = field(
        default_factory=ChaosConfig
    )

    # Noise and variability
    base_noise_level: float = 0.1  # Random variation in outcomes
    temporal_noise: float = 0.05  # Variation in timing

    # Decision accuracy bounds
    min_accuracy_floor: float = 0.20  # No agent worse than 20%
    max_accuracy_ceiling: float = 0.95  # No agent better than 95%

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "bpi_calibration": {
                "enabled": self.bpi_calibration.enabled,
                "dataset": self.bpi_calibration.dataset,
                "use_timing": self.bpi_calibration.use_timing_distribution,
            },
            "chaos": {
                "enabled": self.chaos.enabled,
                "knowledge_departure_weeks": self.chaos.knowledge_departure.departure_weeks,
                "policy_contradiction_weeks": [
                    s["week"] for s in self.chaos.policy_contradiction.contradiction_scenarios
                ],
                "agent_drift_weeks": self.chaos.agent_drift.drift_start_weeks,
                "workload_surge_weeks": self.chaos.workload_surge.surge_weeks,
            },
            "noise_level": self.base_noise_level,
        }


# Default configurations
DEFAULT_REALISM_CONFIG = RealismConfig()

CHAOS_ENABLED_CONFIG = RealismConfig(
    chaos=ChaosConfig(enabled=True)
)

FULL_REALISM_CONFIG = RealismConfig(
    bpi_calibration=BPICalibrationConfig(enabled=True),
    chaos=ChaosConfig(enabled=True),
)
