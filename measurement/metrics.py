"""
Metrics Calculation for Simulation Results.

Implements the four primary metrics (DQS, EHR, IMU, OER) and
secondary technical metrics for the simulation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import statistics

from typing import TYPE_CHECKING

from generators.agent_exhaust import AgentDecision, DecisionOutcome
from bank.context_bank import BankSnapshot
from bank.synthesis import SynthesisResult, compute_synthesis_intelligence_score
from simulation.clock import WeeklySnapshot


@dataclass
class SimulationMetrics:
    """Complete metrics for a simulation run."""
    # Primary metrics (business readable)
    decision_quality_scores: Dict[str, List[float]]  # by agent, per week
    exception_handling_rates: List[float]  # per week
    institutional_memory_utilization: List[float]  # per week
    organizational_error_rates: List[int]  # per week

    # Secondary metrics (technical)
    context_object_growth: List[int]  # total objects per week
    confidence_distribution_history: List[Dict[str, int]]  # per week
    avg_confidence_history: List[float]  # per week
    contradiction_counts: List[int]  # cumulative per week
    provenance_chain_depths: List[float]  # avg depth per week

    # Synthesis metrics
    synthesis_results: List[Optional[Dict]] = field(default_factory=list)  # per week
    synthesis_intelligence_scores: List[float] = field(default_factory=list)  # per week
    total_patterns_crystallized: int = 0
    total_validations_propagated: int = 0
    total_decay_adjustments: int = 0

    # Summary statistics
    total_decisions: int = 0
    correct_decisions: int = 0
    incorrect_decisions: int = 0
    final_bank_size: int = 0
    final_avg_confidence: float = 0.0

    def overall_dqs(self) -> float:
        """Calculate overall Decision Quality Score."""
        all_scores = []
        for agent_scores in self.decision_quality_scores.values():
            all_scores.extend(agent_scores)
        return statistics.mean(all_scores) if all_scores else 0.0

    def weekly_dqs(self) -> List[float]:
        """
        Calculate week-by-week aggregate DQS.

        Returns a list aligned to EHR history (one per simulation week).
        Only weeks with decisions will have non-zero values.
        """
        # Use EHR history as the reference for week count
        # since it's one entry per week
        return self.exception_handling_rates

    def overall_ehr(self) -> float:
        """Calculate overall Exception Handling Rate."""
        return statistics.mean(self.exception_handling_rates) if self.exception_handling_rates else 0.0

    def overall_imu(self) -> float:
        """Calculate overall Institutional Memory Utilization."""
        return statistics.mean(self.institutional_memory_utilization) if self.institutional_memory_utilization else 0.0

    def total_oer(self) -> int:
        """Calculate total Organizational Error Rate."""
        return sum(self.organizational_error_rates)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "primary_metrics": {
                "decision_quality_scores": self.decision_quality_scores,
                "weekly_dqs": self.weekly_dqs(),
                "overall_dqs": self.overall_dqs(),
                "exception_handling_rates": self.exception_handling_rates,
                "overall_ehr": self.overall_ehr(),
                "institutional_memory_utilization": self.institutional_memory_utilization,
                "overall_imu": self.overall_imu(),
                "organizational_error_rates": self.organizational_error_rates,
                "total_oer": self.total_oer(),
            },
            "secondary_metrics": {
                "context_object_growth": self.context_object_growth,
                "avg_confidence_history": self.avg_confidence_history,
                "contradiction_counts": self.contradiction_counts,
            },
            "synthesis_metrics": {
                "synthesis_results": self.synthesis_results,
                "intelligence_scores": self.synthesis_intelligence_scores,
                "total_patterns_crystallized": self.total_patterns_crystallized,
                "total_validations_propagated": self.total_validations_propagated,
                "total_decay_adjustments": self.total_decay_adjustments,
            },
            "summary": {
                "total_decisions": self.total_decisions,
                "correct_decisions": self.correct_decisions,
                "incorrect_decisions": self.incorrect_decisions,
                "accuracy": (self.correct_decisions / self.total_decisions * 100) if self.total_decisions > 0 else 0,
                "final_bank_size": self.final_bank_size,
                "final_avg_confidence": self.final_avg_confidence,
            },
        }


def calculate_dqs(
    decisions: List[AgentDecision],
    by_agent: bool = True,
) -> Dict[str, float]:
    """
    Calculate Decision Quality Score.

    Per agent per week, 0 to 100. Scored by comparing agent decision
    to ground truth.

    Args:
        decisions: List of agent decisions
        by_agent: Group by agent (True) or aggregate (False)

    Returns:
        Dict mapping agent_id to DQS score (0-100)
    """
    if not by_agent:
        total = len(decisions)
        correct = len([d for d in decisions if d.outcome == DecisionOutcome.CORRECT])
        return {"overall": (correct / total * 100) if total > 0 else 0}

    agent_scores = {}
    agent_totals = {}

    for decision in decisions:
        agent = decision.agent_id
        if agent not in agent_scores:
            agent_scores[agent] = 0
            agent_totals[agent] = 0

        agent_totals[agent] += 1
        if decision.outcome == DecisionOutcome.CORRECT:
            agent_scores[agent] += 1

    return {
        agent: (agent_scores[agent] / agent_totals[agent] * 100) if agent_totals[agent] > 0 else 0
        for agent in agent_totals
    }


def calculate_ehr(decisions: List[AgentDecision]) -> float:
    """
    Calculate Exception Handling Rate.

    Percentage of exception scenarios handled correctly versus
    incorrectly versus escalated unnecessarily.

    Returns:
        EHR as percentage (0-100)
    """
    # All decisions in our simulation are exception scenarios
    total = len(decisions)
    if total == 0:
        return 0.0

    correct = len([d for d in decisions if d.outcome == DecisionOutcome.CORRECT])
    return correct / total * 100


def calculate_imu(
    decisions: List[AgentDecision],
    bank_snapshot: Optional[BankSnapshot] = None,
) -> float:
    """
    Calculate Institutional Memory Utilization.

    Percentage of relevant seeded context objects successfully
    retrieved and applied by agents.

    Returns:
        IMU as percentage (0-100)
    """
    if not decisions:
        return 0.0

    # Count decisions that retrieved relevant context
    decisions_with_context = len([d for d in decisions if d.context_retrieved])

    # Count decisions that used retrieved context
    decisions_using_context = len([d for d in decisions if d.context_used])

    if decisions_with_context == 0:
        return 0.0

    return decisions_using_context / len(decisions) * 100


def calculate_oer(decisions: List[AgentDecision]) -> int:
    """
    Calculate Organizational Error Rate.

    Count of decisions that would have caused real organizational harm.

    Returns:
        Number of errors
    """
    return len([d for d in decisions if d.outcome == DecisionOutcome.INCORRECT])


class MetricsCalculator:
    """
    Calculates all metrics from simulation snapshots.

    Processes weekly snapshots and produces complete metrics.
    """

    def __init__(self):
        pass

    def calculate_from_snapshots(
        self,
        snapshots: List[WeeklySnapshot],
    ) -> SimulationMetrics:
        """
        Calculate all metrics from a list of weekly snapshots.

        Args:
            snapshots: List of WeeklySnapshot from simulation run

        Returns:
            SimulationMetrics with all calculated values
        """
        # Initialize tracking
        dqs_by_agent: Dict[str, List[float]] = {}
        ehr_history = []
        imu_history = []
        oer_history = []
        growth_history = []
        confidence_dist_history = []
        avg_conf_history = []
        contradiction_history = []
        chain_depth_history = []

        # Synthesis tracking
        synthesis_results = []
        synthesis_scores = []
        total_crystals = 0
        total_validations = 0
        total_decay_adj = 0

        all_decisions = []

        for snapshot in snapshots:
            # Collect all decisions
            all_decisions.extend(snapshot.agent_decisions)

            # DQS per agent this week
            week_dqs = calculate_dqs(snapshot.agent_decisions, by_agent=True)
            for agent, score in week_dqs.items():
                if agent not in dqs_by_agent:
                    dqs_by_agent[agent] = []
                dqs_by_agent[agent].append(score)

            # EHR this week
            ehr_history.append(calculate_ehr(snapshot.agent_decisions))

            # IMU this week
            imu_history.append(snapshot.institutional_memory_utilization)

            # OER this week
            oer_history.append(snapshot.organizational_error_count)

            # Bank metrics
            if snapshot.bank_snapshot:
                growth_history.append(snapshot.bank_snapshot.total_objects)
                confidence_dist_history.append(snapshot.bank_snapshot.confidence_distribution)
                avg_conf_history.append(snapshot.bank_snapshot.avg_confidence)
                contradiction_history.append(snapshot.bank_snapshot.contradictions_count)
            else:
                growth_history.append(0)
                confidence_dist_history.append({})
                avg_conf_history.append(0.0)
                contradiction_history.append(0)

            # Provenance chain depth (placeholder - would need object traversal)
            chain_depth_history.append(0.0)

            # Synthesis results
            if snapshot.synthesis_result:
                sr = snapshot.synthesis_result
                synthesis_results.append(sr.to_dict())
                bank_size = snapshot.bank_snapshot.total_objects if snapshot.bank_snapshot else 0
                score = compute_synthesis_intelligence_score(sr, bank_size)
                synthesis_scores.append(score)
                total_crystals += sr.patterns_crystallized
                total_validations += sr.validations_propagated
                total_decay_adj += sr.decay_rates_adjusted
            else:
                synthesis_results.append(None)
                synthesis_scores.append(0.0)

        # Calculate summary statistics
        total_decisions = len(all_decisions)
        correct_decisions = len([d for d in all_decisions if d.outcome == DecisionOutcome.CORRECT])
        incorrect_decisions = len([d for d in all_decisions if d.outcome == DecisionOutcome.INCORRECT])

        final_snapshot = snapshots[-1] if snapshots else None
        final_bank_size = final_snapshot.bank_snapshot.total_objects if final_snapshot and final_snapshot.bank_snapshot else 0
        final_avg_confidence = final_snapshot.bank_snapshot.avg_confidence if final_snapshot and final_snapshot.bank_snapshot else 0.0

        return SimulationMetrics(
            decision_quality_scores=dqs_by_agent,
            exception_handling_rates=ehr_history,
            institutional_memory_utilization=imu_history,
            organizational_error_rates=oer_history,
            context_object_growth=growth_history,
            confidence_distribution_history=confidence_dist_history,
            avg_confidence_history=avg_conf_history,
            contradiction_counts=contradiction_history,
            provenance_chain_depths=chain_depth_history,
            synthesis_results=synthesis_results,
            synthesis_intelligence_scores=synthesis_scores,
            total_patterns_crystallized=total_crystals,
            total_validations_propagated=total_validations,
            total_decay_adjustments=total_decay_adj,
            total_decisions=total_decisions,
            correct_decisions=correct_decisions,
            incorrect_decisions=incorrect_decisions,
            final_bank_size=final_bank_size,
            final_avg_confidence=final_avg_confidence,
        )

    def compare_conditions(
        self,
        without_bank_snapshots: List[WeeklySnapshot],
        with_bank_snapshots: List[WeeklySnapshot],
    ) -> Dict[str, Any]:
        """
        Compare metrics between WITHOUT_BANK and WITH_BANK conditions.

        Returns comprehensive comparison data for visualization.
        """
        without_metrics = self.calculate_from_snapshots(without_bank_snapshots)
        with_metrics = self.calculate_from_snapshots(with_bank_snapshots)

        return {
            "without_bank": without_metrics.to_dict(),
            "with_bank": with_metrics.to_dict(),
            "comparison": {
                "dqs_improvement": with_metrics.overall_dqs() - without_metrics.overall_dqs(),
                "ehr_improvement": with_metrics.overall_ehr() - without_metrics.overall_ehr(),
                "imu_improvement": with_metrics.overall_imu() - without_metrics.overall_imu(),
                "errors_avoided": without_metrics.total_oer() - with_metrics.total_oer(),
                "accuracy_improvement": (
                    (with_metrics.correct_decisions / with_metrics.total_decisions * 100)
                    - (without_metrics.correct_decisions / without_metrics.total_decisions * 100)
                ) if without_metrics.total_decisions > 0 and with_metrics.total_decisions > 0 else 0,
            },
        }
