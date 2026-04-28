"""
Ground Truth Definitions for Scenario Evaluation.

Defines correct answers for each key scenario to enable
automated evaluation of agent decisions.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Callable, Any
import re

from generators.agent_exhaust import AgentDecision, DecisionOutcome


@dataclass
class GroundTruth:
    """Ground truth definition for a scenario."""
    scenario_type: str
    relevant_context_ids: List[str]
    correct_action_keywords: List[str]
    incorrect_action_keywords: List[str]
    description: str
    evaluation_fn: Optional[Callable[[AgentDecision], DecisionOutcome]] = None


# Ground truth for all key scenarios
GROUND_TRUTH_SCENARIOS: Dict[str, GroundTruth] = {
    "vendor_sow": GroundTruth(
        scenario_type="vendor_sow",
        relevant_context_ids=["CTX-001"],
        correct_action_keywords=[
            "secondary approval", "david okafor", "route through",
            "approval required", "okafor"
        ],
        incorrect_action_keywords=[
            "issue directly", "proceed with sow", "standard process",
            "issue sow"
        ],
        description="Brightline SOW requires secondary approval from David Okafor",
    ),
    "staffing_assignment": GroundTruth(
        scenario_type="staffing_assignment",
        relevant_context_ids=["CTX-010"],
        correct_action_keywords=[
            "do not assign", "conflict", "alternative", "find another",
            "cannot assign", "not assign"
        ],
        incorrect_action_keywords=[
            "assign jordan", "proceed with assignment", "skills match",
            "assign to"
        ],
        description="Jordan Park has documented conflict with Nexum Partners",
    ),
    "payment_escalation": GroundTruth(
        scenario_type="payment_escalation",
        relevant_context_ids=["CTX-006"],
        correct_action_keywords=[
            "do not escalate", "wait until", "day 65", "60-day cycle",
            "premature", "hold"
        ],
        incorrect_action_keywords=[
            "escalate", "collections", "overdue", "past due",
            "proceed with escalation"
        ],
        description="TerraLogic has 60-day actual payment cycle, wait until day 65",
    ),
    "go_no_go": GroundTruth(
        scenario_type="go_no_go",
        relevant_context_ids=["CTX-003"],
        correct_action_keywords=[
            "proceed", "go", "override", "marcus webb", "relationship",
            "approve"
        ],
        incorrect_action_keywords=[
            "no-go", "reject", "margin below", "decline",
            "do not proceed"
        ],
        description="Marcus Webb overrides go/no-go for Hartwell Group",
    ),
    "scope_documentation": GroundTruth(
        scenario_type="scope_documentation",
        relevant_context_ids=["CTX-002"],
        correct_action_keywords=[
            "document within 24", "document immediately", "written record",
            "document verbal"
        ],
        incorrect_action_keywords=[
            "verbal is fine", "no documentation needed",
            "proceed without"
        ],
        description="Financial services scope expansions must be documented within 24 hours",
    ),
    "write_off_approval": GroundTruth(
        scenario_type="write_off_approval",
        relevant_context_ids=["CTX-009"],
        correct_action_keywords=[
            "ceo approval", "james holloway", "above 15k",
            "requires ceo"
        ],
        incorrect_action_keywords=[
            "partner approval sufficient", "approval matrix",
            "standard approval"
        ],
        description="Write-offs above $15K require CEO approval",
    ),
    "fs_methodology": GroundTruth(
        scenario_type="fs_methodology",
        relevant_context_ids=["CTX-008"],
        correct_action_keywords=[
            "elena vasquez", "consult directly", "not in knowledge base",
            "consult elena"
        ],
        incorrect_action_keywords=[
            "check knowledge base", "standard methodology",
            "documented approach"
        ],
        description="Elena Vasquez holds undocumented FS methodology",
    ),
    "coi_check": GroundTruth(
        scenario_type="coi_check",
        relevant_context_ids=["CTX-007"],
        correct_action_keywords=[
            "manual check", "former staff", "not automated",
            "coi check required"
        ],
        incorrect_action_keywords=[
            "system will flag", "automated check",
            "no manual check needed"
        ],
        description="COI check for former staff is manual, not automated",
    ),
    "senior_reallocation": GroundTruth(
        scenario_type="senior_reallocation",
        relevant_context_ids=["CTX-004"],
        correct_action_keywords=[
            "72 hour", "priya nair", "notice required",
            "72-hour notice"
        ],
        incorrect_action_keywords=[
            "immediate reallocation", "no notice needed",
            "proceed immediately"
        ],
        description="Senior resource reallocation requires 72-hour notice to Priya",
    ),
    "vance_pricing": GroundTruth(
        scenario_type="vance_pricing",
        relevant_context_ids=["CTX-005"],
        correct_action_keywords=[
            "negotiate", "15% below", "discount available",
            "do not disclose"
        ],
        incorrect_action_keywords=[
            "list price only", "no negotiation",
            "accept list price"
        ],
        description="Vance Analytics pricing is negotiable 15% below list for large engagements",
    ),
}


def evaluate_decision(
    decision: AgentDecision,
    ground_truth: Optional[GroundTruth] = None,
) -> DecisionOutcome:
    """
    Evaluate a single decision against ground truth.

    Args:
        decision: The agent decision to evaluate
        ground_truth: Optional specific ground truth (defaults to lookup by scenario_type)

    Returns:
        DecisionOutcome
    """
    # Get ground truth for this scenario type
    if ground_truth is None:
        ground_truth = GROUND_TRUTH_SCENARIOS.get(decision.scenario_type)

    if ground_truth is None:
        return DecisionOutcome.UNKNOWN

    # Use custom evaluation function if provided
    if ground_truth.evaluation_fn:
        return ground_truth.evaluation_fn(decision)

    # Keyword-based evaluation
    action_lower = decision.decision_taken.lower()
    reasoning_lower = decision.reasoning.lower()
    full_text = f"{action_lower} {reasoning_lower}"

    # Count keyword matches
    correct_matches = sum(
        1 for kw in ground_truth.correct_action_keywords
        if kw in full_text
    )
    incorrect_matches = sum(
        1 for kw in ground_truth.incorrect_action_keywords
        if kw in full_text
    )

    # Check if relevant context was used
    context_used = set(decision.context_used)
    relevant_context = set(ground_truth.relevant_context_ids)
    context_overlap = len(context_used & relevant_context) / len(relevant_context) if relevant_context else 0

    # Determine outcome
    if correct_matches > incorrect_matches and context_overlap >= 0.5:
        return DecisionOutcome.CORRECT
    elif correct_matches > 0 and context_overlap > 0:
        return DecisionOutcome.PARTIAL
    elif "escalate" in action_lower or "review" in action_lower:
        return DecisionOutcome.ESCALATED
    elif incorrect_matches > correct_matches or correct_matches == 0:
        return DecisionOutcome.INCORRECT
    else:
        return DecisionOutcome.UNKNOWN


def evaluate_all_decisions(
    decisions: List[AgentDecision],
) -> Dict[str, Dict[str, int]]:
    """
    Evaluate all decisions and return outcome counts by scenario type.

    Returns:
        Dict mapping scenario_type to outcome counts
    """
    results = {}

    for decision in decisions:
        if decision.scenario_type not in results:
            results[decision.scenario_type] = {
                "correct": 0,
                "incorrect": 0,
                "partial": 0,
                "escalated": 0,
                "unknown": 0,
            }

        outcome = evaluate_decision(decision)
        results[decision.scenario_type][outcome.value] += 1

    return results


class GroundTruthEvaluator:
    """
    Evaluates agent decisions against ground truth.

    Provides detailed analysis and comparison between conditions.
    """

    def __init__(self):
        self.ground_truths = GROUND_TRUTH_SCENARIOS

    def evaluate_decision(self, decision: AgentDecision) -> DecisionOutcome:
        """Evaluate a single decision."""
        return evaluate_decision(decision)

    def evaluate_batch(self, decisions: List[AgentDecision]) -> List[DecisionOutcome]:
        """Evaluate a batch of decisions."""
        return [self.evaluate_decision(d) for d in decisions]

    def compare_conditions(
        self,
        without_bank_decisions: List[AgentDecision],
        with_bank_decisions: List[AgentDecision],
    ) -> Dict[str, Any]:
        """
        Compare outcomes between WITHOUT_BANK and WITH_BANK conditions.

        Returns detailed comparison statistics.
        """
        # Evaluate both conditions
        without_outcomes = evaluate_all_decisions(without_bank_decisions)
        with_outcomes = evaluate_all_decisions(with_bank_decisions)

        # Calculate totals
        def sum_outcomes(outcomes: Dict) -> Dict[str, int]:
            totals = {"correct": 0, "incorrect": 0, "partial": 0, "escalated": 0, "unknown": 0}
            for scenario in outcomes.values():
                for outcome, count in scenario.items():
                    totals[outcome] += count
            return totals

        without_totals = sum_outcomes(without_outcomes)
        with_totals = sum_outcomes(with_outcomes)

        # Calculate improvement
        without_accuracy = without_totals["correct"] / max(1, sum(without_totals.values())) * 100
        with_accuracy = with_totals["correct"] / max(1, sum(with_totals.values())) * 100
        improvement = with_accuracy - without_accuracy

        return {
            "without_bank": {
                "by_scenario": without_outcomes,
                "totals": without_totals,
                "accuracy": without_accuracy,
            },
            "with_bank": {
                "by_scenario": with_outcomes,
                "totals": with_totals,
                "accuracy": with_accuracy,
            },
            "improvement": {
                "accuracy_delta": improvement,
                "errors_avoided": without_totals["incorrect"] - with_totals["incorrect"],
            },
        }

    def get_scenario_analysis(
        self,
        decisions: List[AgentDecision],
        scenario_type: str,
    ) -> Dict[str, Any]:
        """Get detailed analysis for a specific scenario type."""
        scenario_decisions = [d for d in decisions if d.scenario_type == scenario_type]

        if not scenario_decisions:
            return {"error": f"No decisions found for scenario: {scenario_type}"}

        gt = self.ground_truths.get(scenario_type)

        return {
            "scenario_type": scenario_type,
            "description": gt.description if gt else "Unknown",
            "relevant_context": gt.relevant_context_ids if gt else [],
            "total_decisions": len(scenario_decisions),
            "outcomes": {
                outcome.value: len([d for d in scenario_decisions if self.evaluate_decision(d) == outcome])
                for outcome in DecisionOutcome
            },
            "context_retrieval_rate": sum(
                1 for d in scenario_decisions if d.context_retrieved
            ) / len(scenario_decisions) * 100,
            "context_usage_rate": sum(
                1 for d in scenario_decisions if d.context_used
            ) / len(scenario_decisions) * 100,
        }
