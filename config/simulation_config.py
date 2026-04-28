"""
Simulation configuration for Acme Advisory.

Defines the simulation clock, event rates, exception injection schedule,
and run structure for comparing WITH_BANK vs WITHOUT_BANK conditions.

Includes realism calibration for graduated performance improvement.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class RunCondition(str, Enum):
    """The two experimental conditions being compared."""
    WITHOUT_BANK = "WITHOUT_BANK"
    WITH_BANK = "WITH_BANK"


@dataclass
class EventsPerWeek:
    """Number of events to generate per week by workflow."""
    W1_engagements: int = 4       # 4 active engagements per week
    W2_proposals: int = 2          # 2 proposals in flight
    W3_staffing_requests: int = 6  # 6 staffing decisions per week
    W4_vendor_events: int = 3      # 3 vendor interactions
    W5_billing_events: int = 5     # 5 billing events
    behavioral_events: int = 150   # total behavioral exhaust events per week

    def get_workflow_events(self, workflow_id: str) -> int:
        """Get event count for a specific workflow."""
        mapping = {
            "W1": self.W1_engagements,
            "W2": self.W2_proposals,
            "W3": self.W3_staffing_requests,
            "W4": self.W4_vendor_events,
            "W5": self.W5_billing_events,
        }
        return mapping.get(workflow_id, 0)


@dataclass
class ExceptionInjectionSchedule:
    """
    Weeks when specific exception scenarios are triggered.

    These are the key scenarios that test whether the Context Bank
    provides value by surfacing relevant institutional memory.
    """
    # Weeks where Brightline SOW is triggered (CTX-001 is relevant)
    brightline_sow: List[int] = field(default_factory=lambda: [3, 7, 11])

    # Weeks where financial services verbal scope expansion occurs (CTX-002)
    financial_services_scope: List[int] = field(default_factory=lambda: [2, 6, 9])

    # Weeks where Marcus Webb override scenario occurs (CTX-003)
    hartwell_override: List[int] = field(default_factory=lambda: [4, 8])

    # Weeks where TerraLogic payment delay scenario occurs (CTX-006)
    terralogic_payment: List[int] = field(default_factory=lambda: [5, 10])

    # Weeks where Jordan Park conflict scenario occurs (CTX-010)
    jordan_park_conflict: List[int] = field(default_factory=lambda: [6, 11])

    def get_injections_for_week(self, week: int) -> List[str]:
        """Get list of exception scenarios to inject in a given week."""
        injections = []
        if week in self.brightline_sow:
            injections.append("brightline_sow")
        if week in self.financial_services_scope:
            injections.append("financial_services_scope")
        if week in self.hartwell_override:
            injections.append("hartwell_override")
        if week in self.terralogic_payment:
            injections.append("terralogic_payment")
        if week in self.jordan_park_conflict:
            injections.append("jordan_park_conflict")
        return injections

    def is_brightline_week(self, week: int) -> bool:
        """Check if this week has a Brightline SOW scenario."""
        return week in self.brightline_sow


@dataclass
class RetrievalNoiseConfig:
    """
    Configuration for retrieval noise to simulate imperfect context matching.

    Introduces realistic imperfections in context retrieval to prevent
    100%/0% accuracy splits.
    """
    # Probability of retrieving correct context when it exists (0-1)
    retrieval_success_rate: float = 0.85

    # Probability of irrelevant context being included in results (0-1)
    false_positive_rate: float = 0.10

    # Probability of agent correctly interpreting retrieved context (0-1)
    interpretation_accuracy: float = 0.90

    # Confidence threshold below which context may be ignored
    confidence_ignore_threshold: float = 0.4

    def get_effective_accuracy(self) -> float:
        """Calculate effective accuracy from retrieval and interpretation."""
        return self.retrieval_success_rate * self.interpretation_accuracy


@dataclass
class PerformanceCalibration:
    """
    Calibration for graduated performance improvement over time.

    WITHOUT_BANK starts at baseline and may slightly improve (learning).
    WITH_BANK starts at baseline and improves more rapidly as bank grows.
    """
    # Baseline accuracy for WITHOUT_BANK (week 1)
    # This represents agent accuracy with no institutional memory
    baseline_accuracy_without_bank: float = 0.25

    # Baseline accuracy for WITH_BANK (week 1)
    # Starts similar but with seeded context available
    baseline_accuracy_with_bank: float = 0.70

    # Weekly improvement multiplier for WITHOUT_BANK
    # Small improvement from ad-hoc learning
    weekly_improvement_without_bank: float = 0.02

    # Weekly improvement multiplier for WITH_BANK
    # Larger improvement as bank accumulates knowledge
    weekly_improvement_with_bank: float = 0.03

    # Maximum accuracy caps
    max_accuracy_without_bank: float = 0.40
    max_accuracy_with_bank: float = 0.95

    def get_accuracy_for_week(self, condition: "RunCondition", week: int) -> float:
        """
        Calculate expected accuracy for a given condition and week.

        Args:
            condition: WITHOUT_BANK or WITH_BANK
            week: Simulation week (1-indexed)

        Returns:
            Expected accuracy as a float between 0 and 1
        """
        if condition == RunCondition.WITHOUT_BANK:
            baseline = self.baseline_accuracy_without_bank
            improvement = self.weekly_improvement_without_bank
            cap = self.max_accuracy_without_bank
        else:
            baseline = self.baseline_accuracy_with_bank
            improvement = self.weekly_improvement_with_bank
            cap = self.max_accuracy_with_bank

        # Linear improvement from baseline
        weeks_elapsed = week - 1
        accuracy = baseline + (improvement * weeks_elapsed)
        return min(accuracy, cap)


@dataclass
class SimulationConfig:
    """Complete simulation configuration."""
    # Duration
    weeks: int = 12

    # Event generation rates
    events_per_week: EventsPerWeek = field(default_factory=EventsPerWeek)

    # Exception injection timing
    exception_injection: ExceptionInjectionSchedule = field(
        default_factory=ExceptionInjectionSchedule
    )

    # Reproducibility
    random_seed: int = 42

    # Experimental conditions to run
    runs: List[RunCondition] = field(
        default_factory=lambda: [RunCondition.WITHOUT_BANK, RunCondition.WITH_BANK]
    )

    # Agent configuration
    agent_model: str = "claude-sonnet-4-20250514"
    agent_max_tokens: int = 1024
    agent_temperature: float = 0.7

    # Context Bank retrieval settings
    retrieval_top_k: int = 5  # Number of context objects to retrieve per query
    retrieval_min_confidence: float = 0.3  # Minimum confidence to include in retrieval

    # Realism calibration
    retrieval_noise: RetrievalNoiseConfig = field(default_factory=RetrievalNoiseConfig)
    performance_calibration: PerformanceCalibration = field(default_factory=PerformanceCalibration)

    # Metrics thresholds
    decision_quality_threshold: float = 0.7  # Score above this = "correct" decision
    contradiction_similarity_threshold: float = 0.85  # Similarity for contradiction detection

    # Output settings
    output_dir: str = "results"
    save_intermediate: bool = True  # Save weekly snapshots


# Global simulation configuration instance
SIMULATION_CONFIG = SimulationConfig()


# Agent definitions
AGENTS = {
    "proposal_agent": {
        "id": "proposal_agent",
        "name": "Proposal Agent",
        "role": "Drafts and coordinates proposals",
        "workflows": ["W2"],
        "decision_authority": "recommend_only",
        "context_retrieval": True,
        "system_prompt_template": """You are the Proposal Agent at Acme Advisory, a mid-market consulting firm.

Your role is to draft and coordinate proposals for new business opportunities.

Current simulation week: {week}

Your responsibilities:
- Evaluate go/no-go decisions for opportunities
- Assemble proposal teams
- Draft RFP responses
- Coordinate pricing approvals
- Track proposal outcomes

{context_section}

When making decisions, consider:
1. Client relationship history
2. Resource availability
3. Margin requirements (standard threshold: 25%)
4. Conflict of interest concerns
5. Strategic partner priorities

Provide your recommendation with confidence level and reasoning.""",
    },
    "staffing_agent": {
        "id": "staffing_agent",
        "name": "Staffing Agent",
        "role": "Matches resources to engagements",
        "workflows": ["W3"],
        "decision_authority": "recommend_only",
        "context_retrieval": True,
        "system_prompt_template": """You are the Staffing Agent at Acme Advisory, a mid-market consulting firm.

Your role is to match resources to engagement needs.

Current simulation week: {week}

Your responsibilities:
- Identify candidates with required skills
- Check availability against utilization targets (72%)
- Make staffing recommendations
- Flag conflicts or concerns
- Coordinate with subcontractors when needed

{context_section}

When making staffing decisions, consider:
1. Skills match
2. Current utilization levels
3. Client history and conflicts
4. Notice requirements for senior resources
5. Subcontractor options if no internal match

Provide your staffing recommendation with confidence level and reasoning.""",
    },
    "vendor_agent": {
        "id": "vendor_agent",
        "name": "Vendor Agent",
        "role": "Manages subcontractor SOWs and approvals",
        "workflows": ["W4"],
        "decision_authority": "initiate_only",
        "context_retrieval": True,
        "system_prompt_template": """You are the Vendor Agent at Acme Advisory, a mid-market consulting firm.

Your role is to manage subcontractor and vendor relationships.

Current simulation week: {week}

Your responsibilities:
- Check approved vendor list
- Draft statements of work
- Route for appropriate approvals
- Monitor vendor quality
- Manage vendor invoices

{context_section}

When making vendor decisions, consider:
1. Whether vendor is on approved list
2. Historical pricing and relationship issues
3. Required approval paths
4. Quality track record
5. Pricing negotiation opportunities

Provide your recommendation with confidence level and reasoning.
IMPORTANT: Always check if any vendor has special approval requirements before issuing SOWs.""",
    },
    "billing_agent": {
        "id": "billing_agent",
        "name": "Billing Agent",
        "role": "Generates invoices and manages collections",
        "workflows": ["W5"],
        "decision_authority": "recommend_only",
        "context_retrieval": True,
        "system_prompt_template": """You are the Billing Agent at Acme Advisory, a mid-market consulting firm.

Your role is to manage client billing and collections.

Current simulation week: {week}

Your responsibilities:
- Generate invoices from time entries
- Monitor payment status
- Manage collection escalations
- Handle billing disputes
- Process write-off requests

{context_section}

When making billing decisions, consider:
1. Contract terms and billing milestones
2. Client payment history and cycles
3. Scope documentation for disputes
4. Escalation timing
5. Write-off approval requirements

Provide your recommendation with confidence level and reasoning.
IMPORTANT: Be aware of client-specific payment patterns before escalating.""",
    },
}


# Client definitions for simulation
CLIENTS = {
    "hartwell_group": {
        "id": "hartwell_group",
        "name": "Hartwell Group",
        "vertical": "financial_services",
        "relationship_owner": "marcus_webb",
        "payment_terms_days": 30,
        "special_flags": ["partner_override_eligible"],
    },
    "terralogic": {
        "id": "terralogic",
        "name": "TerraLogic",
        "vertical": "technology",
        "relationship_owner": "sarah_chen",
        "payment_terms_days": 30,  # Contract says 30, actual is 60
        "actual_payment_days": 60,
        "special_flags": ["extended_payment_cycle"],
    },
    "nexum_partners": {
        "id": "nexum_partners",
        "name": "Nexum Partners",
        "vertical": "private_equity",
        "relationship_owner": "james_holloway",
        "payment_terms_days": 30,
        "special_flags": ["jordan_park_conflict"],
    },
    "meridian_financial": {
        "id": "meridian_financial",
        "name": "Meridian Financial",
        "vertical": "financial_services",
        "relationship_owner": "sarah_chen",
        "payment_terms_days": 30,
        "special_flags": ["scope_creep_risk"],
    },
    "apex_manufacturing": {
        "id": "apex_manufacturing",
        "name": "Apex Manufacturing",
        "vertical": "industrial",
        "relationship_owner": "marcus_webb",
        "payment_terms_days": 45,
        "special_flags": [],
    },
}


# Vendor definitions
VENDORS = {
    "brightline_consulting": {
        "id": "brightline_consulting",
        "name": "Brightline Consulting",
        "specialty": "federal_compliance",
        "list_rate_daily": 2500,
        "approved": True,
        "special_flags": ["secondary_approval_required", "pricing_history_dispute"],
        "required_approver": "david_okafor",
    },
    "vance_analytics": {
        "id": "vance_analytics",
        "name": "Vance Analytics",
        "specialty": "data_analytics",
        "list_rate_daily": 2200,
        "approved": True,
        "special_flags": ["negotiable_pricing"],
        "discount_threshold": 500000,
        "max_discount_percent": 15,
    },
    "summit_research": {
        "id": "summit_research",
        "name": "Summit Research",
        "specialty": "market_research",
        "list_rate_daily": 1800,
        "approved": True,
        "special_flags": [],
    },
}
