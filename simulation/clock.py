"""
Simulation Clock and Weekly Loop.

Orchestrates the weekly simulation cycle: generate events, run agents,
deposit context, and capture metrics.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any, Tuple
import json
import copy

from config.simulation_config import (
    SIMULATION_CONFIG, RunCondition, AGENTS, CLIENTS, VENDORS,
)
from config.seeded_context import SEEDED_CONTEXT_OBJECTS
from models.context_object import ContextObject
from bank.context_bank import ContextBank, BankSnapshot
from bank.synthesis import SynthesisEngine, SynthesisResult, run_synthesis_pass
from generators.structured_exhaust import generate_weekly_events, WorkflowCase, WorkflowEvent
from generators.behavioral_exhaust import generate_behavioral_events, BehavioralEvent
from generators.agent_exhaust import (
    AgentExhaustGenerator, AgentDecision, AgentScenario,
    BRIGHTLINE_SOW_SCENARIO, JORDAN_PARK_STAFFING_SCENARIO,
    TERRALOGIC_PAYMENT_SCENARIO, HARTWELL_PROPOSAL_SCENARIO,
)
from inference.classifier import classify_context_object, ContextClassifier


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


@dataclass
class WeeklySnapshot:
    """Complete snapshot of simulation state after a week."""
    week: int
    condition: RunCondition

    # Bank state
    bank_snapshot: Optional[BankSnapshot] = None

    # Events generated
    workflow_cases: List[WorkflowCase] = field(default_factory=list)
    workflow_events: List[WorkflowEvent] = field(default_factory=list)
    behavioral_events: List[BehavioralEvent] = field(default_factory=list)

    # Agent decisions
    agent_decisions: List[AgentDecision] = field(default_factory=list)

    # Context objects deposited this week
    new_context_objects: List[ContextObject] = field(default_factory=list)

    # Synthesis results
    synthesis_result: Optional[SynthesisResult] = None

    # Metrics
    decision_quality_scores: Dict[str, float] = field(default_factory=dict)
    exception_handling_rate: float = 0.0
    institutional_memory_utilization: float = 0.0
    organizational_error_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "week": self.week,
            "condition": self.condition.value,
            "bank_snapshot": {
                "total_objects": self.bank_snapshot.total_objects if self.bank_snapshot else 0,
                "by_grade": self.bank_snapshot.by_grade if self.bank_snapshot else {},
                "avg_confidence": self.bank_snapshot.avg_confidence if self.bank_snapshot else 0,
            },
            "event_counts": {
                "workflow_cases": len(self.workflow_cases),
                "workflow_events": len(self.workflow_events),
                "behavioral_events": len(self.behavioral_events),
            },
            "agent_decisions": len(self.agent_decisions),
            "new_context_objects": len(self.new_context_objects),
            "metrics": {
                "decision_quality_scores": self.decision_quality_scores,
                "exception_handling_rate": self.exception_handling_rate,
                "institutional_memory_utilization": self.institutional_memory_utilization,
                "organizational_error_count": self.organizational_error_count,
            },
        }


class SimulationClock:
    """
    Orchestrates the simulation across weeks.

    Manages the simulation state, event generation, agent execution,
    and metric collection.
    """

    def __init__(
        self,
        condition: RunCondition,
        seed: Optional[int] = None,
    ):
        """
        Initialize simulation clock.

        Args:
            condition: WITHOUT_BANK or WITH_BANK
            seed: Random seed (defaults to config)
        """
        self.condition = condition
        self.seed = seed or SIMULATION_CONFIG.random_seed
        self.use_bank = condition == RunCondition.WITH_BANK

        # Initialize bank
        self.bank = ContextBank() if self.use_bank else None

        # Load seeded context if using bank
        if self.use_bank and self.bank is not None:
            for obj in SEEDED_CONTEXT_OBJECTS:
                self.bank.deposit(copy.deepcopy(obj), check_contradictions=False)

        # Initialize generators
        self.agent_generator = AgentExhaustGenerator(
            use_context_bank=self.use_bank,
        )
        self.classifier = ContextClassifier(use_api=False)

        # State tracking
        self.current_week = 0
        self.snapshots: List[WeeklySnapshot] = []
        self.all_decisions: List[AgentDecision] = []

        # Scenario tracking
        self.scenario_schedule = self._build_scenario_schedule()

    def _build_scenario_schedule(self) -> Dict[int, List[AgentScenario]]:
        """Build the schedule of scenarios per week."""
        injection = SIMULATION_CONFIG.exception_injection
        schedule = {}

        # Map injection weeks to scenarios
        for week in injection.brightline_sow:
            if week not in schedule:
                schedule[week] = []
            schedule[week].append(BRIGHTLINE_SOW_SCENARIO)

        for week in injection.jordan_park_conflict:
            if week not in schedule:
                schedule[week] = []
            schedule[week].append(JORDAN_PARK_STAFFING_SCENARIO)

        for week in injection.terralogic_payment:
            if week not in schedule:
                schedule[week] = []
            schedule[week].append(TERRALOGIC_PAYMENT_SCENARIO)

        for week in injection.hartwell_override:
            if week not in schedule:
                schedule[week] = []
            schedule[week].append(HARTWELL_PROPOSAL_SCENARIO)

        return schedule

    def _get_agent_for_scenario(self, scenario: AgentScenario) -> str:
        """Get the appropriate agent for a scenario."""
        workflow_to_agent = {
            "W2": "proposal_agent",
            "W3": "staffing_agent",
            "W4": "vendor_agent",
            "W5": "billing_agent",
        }
        return workflow_to_agent.get(scenario.workflow_id, "vendor_agent")

    def _calculate_metrics(
        self,
        decisions: List[AgentDecision],
        scenarios: List[AgentScenario],
        bank_snapshot: Optional[BankSnapshot],
    ) -> Tuple[Dict[str, float], float, float, int]:
        """
        Calculate weekly metrics.

        Returns:
            Tuple of (dqs_by_agent, ehr, imu, oer)
        """
        # Decision Quality Score by agent
        dqs = {}
        agent_correct = {}
        agent_total = {}

        for decision in decisions:
            agent = decision.agent_id
            if agent not in agent_total:
                agent_total[agent] = 0
                agent_correct[agent] = 0

            agent_total[agent] += 1
            if decision.outcome.value == "correct":
                agent_correct[agent] += 1

        for agent in agent_total:
            dqs[agent] = (agent_correct[agent] / agent_total[agent] * 100) if agent_total[agent] > 0 else 0

        # Exception Handling Rate
        total_exceptions = len([d for d in decisions if d.scenario_type in
                               ["vendor_sow", "staffing_assignment", "payment_escalation", "go_no_go"]])
        correct_exceptions = len([d for d in decisions if d.outcome.value == "correct"])
        ehr = (correct_exceptions / total_exceptions * 100) if total_exceptions > 0 else 0

        # Institutional Memory Utilization
        if self.use_bank and bank_snapshot:
            read_count = bank_snapshot.objects_read_this_week
            total_relevant = len(set(
                ctx_id
                for scenario in scenarios
                for ctx_id in scenario.ground_truth_context_ids
            ))
            imu = (read_count / total_relevant * 100) if total_relevant > 0 else 0
        else:
            imu = 0

        # Organizational Error Rate
        oer = len([d for d in decisions if d.outcome.value == "incorrect"])

        return dqs, ehr, imu, oer

    def run_week(self, week: int) -> WeeklySnapshot:
        """
        Run a single week of simulation.

        Args:
            week: Week number (1-12)

        Returns:
            WeeklySnapshot with all data and metrics
        """
        self.current_week = week

        if self.bank is not None:
            self.bank.current_week = week

        # NOTE: Formula-based seeding (seed + week) does not guarantee identical
        # event sequences across WITHOUT_BANK and WITH_BANK conditions because
        # different code paths consume different numbers of random calls, causing
        # RNG state to diverge between arms.
        #
        # Current approach is sufficient for proof-of-concept demonstration.
        # Future iteration: snapshot RNG state before phase 1 begins and restore
        # it before phase 2 to guarantee matched event sequences across both
        # conditions. This would allow true controlled comparison rather than
        # approximately matched comparison.

        # Generate structured events
        cases, events = generate_weekly_events(week, seed=self.seed + week)

        # Generate behavioral events
        behavioral = generate_behavioral_events(
            week,
            seed=self.seed + week + 1000,
            total_events=SIMULATION_CONFIG.events_per_week.behavioral_events,
        )

        # Get scenarios for this week
        scenarios = self.scenario_schedule.get(week, [])

        # Run agent decisions
        decisions = []
        for scenario in scenarios:
            agent_id = self._get_agent_for_scenario(scenario)
            decision = self.agent_generator.generate_decision(
                agent_id=agent_id,
                scenario=scenario,
                week=week,
                context_bank=self.bank,
            )
            decisions.append(decision)
            self.all_decisions.append(decision)

            # Deposit agent-generated context
            if self.use_bank and decision.deposited_context is not None:
                self.bank.deposit(decision.deposited_context)

        # Extract potential context from behavioral events
        new_context = []
        if self.use_bank:
            new_context = self._extract_context_from_behavioral(behavioral, week)
            for obj in new_context:
                self.bank.deposit(obj)

        # Run synthesis pass (every 3 weeks or at specific milestones)
        synthesis_result = None
        if self.use_bank and self.bank is not None and week % 3 == 0:
            synthesis_result = run_synthesis_pass(self.bank, week)

        # Capture bank snapshot
        bank_snapshot = None
        if self.bank is not None:
            bank_snapshot = self.bank.snapshot()

        # Calculate metrics
        dqs, ehr, imu, oer = self._calculate_metrics(decisions, scenarios, bank_snapshot)

        # Create snapshot
        snapshot = WeeklySnapshot(
            week=week,
            condition=self.condition,
            bank_snapshot=bank_snapshot,
            workflow_cases=cases,
            workflow_events=events,
            behavioral_events=behavioral,
            agent_decisions=decisions,
            new_context_objects=new_context,
            synthesis_result=synthesis_result,
            decision_quality_scores=dqs,
            exception_handling_rate=ehr,
            institutional_memory_utilization=imu,
            organizational_error_count=oer,
        )

        self.snapshots.append(snapshot)
        return snapshot

    def _extract_context_from_behavioral(
        self,
        events: List[BehavioralEvent],
        week: int,
    ) -> List[ContextObject]:
        """
        Extract potential context objects from behavioral events.

        Only extracts from high-signal events.
        """
        from models.context_object import ContentType, SourceType, DecayFunction

        new_objects = []
        # Only process events with high knowledge signal and raw content
        high_signal = [e for e in events
                       if e.knowledge_signal_weight > 0.7 and e.raw_content]

        # Limit to avoid overwhelming the bank
        for event in high_signal[:3]:
            obj = ContextObject(
                created_by=event.staff_id,
                source_type=SourceType.human,
                week=week,
                content_type=ContentType.observation,
                payload=f"{event.staff_name} shared: {event.raw_content}",
                structured_data={
                    "source_event": event.event_id,
                    "behavior_type": event.behavior_type.value,
                    "application": event.application.value,
                    "staff_tenure_years": event.staff_tenure_years,
                },
                decay_function=DecayFunction.exponential,
                decay_rate=0.15,
                confidence_at_creation=min(0.75, event.knowledge_signal_weight),
            )

            # Classify the new object
            self.classifier.classify_and_update(obj)
            new_objects.append(obj)

        return new_objects

    def run_full_simulation(self) -> List[WeeklySnapshot]:
        """
        Run the full 12-week simulation.

        Returns:
            List of all weekly snapshots
        """
        for week in range(1, SIMULATION_CONFIG.weeks + 1):
            self.run_week(week)
        return self.snapshots

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics for the simulation run."""
        if not self.snapshots:
            return {}

        total_decisions = len(self.all_decisions)
        correct_decisions = len([d for d in self.all_decisions if d.outcome.value == "correct"])
        incorrect_decisions = len([d for d in self.all_decisions if d.outcome.value == "incorrect"])

        final_snapshot = self.snapshots[-1]

        return {
            "condition": self.condition.value,
            "weeks_run": len(self.snapshots),
            "total_decisions": total_decisions,
            "correct_decisions": correct_decisions,
            "incorrect_decisions": incorrect_decisions,
            "overall_accuracy": (correct_decisions / total_decisions * 100) if total_decisions > 0 else 0,
            "final_bank_size": final_snapshot.bank_snapshot.total_objects if final_snapshot.bank_snapshot else 0,
            "final_avg_confidence": final_snapshot.bank_snapshot.avg_confidence if final_snapshot.bank_snapshot else 0,
            "total_workflow_events": sum(len(s.workflow_events) for s in self.snapshots),
            "total_behavioral_events": sum(len(s.behavioral_events) for s in self.snapshots),
        }


def run_week(
    week: int,
    condition: RunCondition,
    bank: Optional[ContextBank] = None,
) -> WeeklySnapshot:
    """
    Convenience function to run a single week.

    Args:
        week: Week number
        condition: WITHOUT_BANK or WITH_BANK
        bank: Optional existing bank (for WITH_BANK)

    Returns:
        WeeklySnapshot
    """
    clock = SimulationClock(condition)
    if bank is not None:
        clock.bank = bank
    return clock.run_week(week)
