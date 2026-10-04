"""
Simulation configuration for Acme Advisory.

Defines the simulation clock, event rates, exception injection schedule,
and run structure for comparing four experimental conditions:

1. SILOED_TYPICAL   - Each agent sees only their department's knowledge (baseline)
2. SILOED_ADVANCED  - Department + adjacent departments, with basic time decay
3. GLOBAL_RAG       - All agents see all knowledge, but no sophistication
4. CONTEXT_BANK     - Full sophistication: decay, provenance, synthesis, validation

Includes realism calibration for graduated performance improvement.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from enum import Enum


class RunCondition(str, Enum):
    """
    The four experimental conditions being compared.

    Each represents a different level of context sophistication:
    - SILOED_TYPICAL: Basic vendor setup (department-only RAG)
    - SILOED_ADVANCED: Sophisticated vendor (dept + adjacent, basic decay)
    - GLOBAL_RAG: Naive centralization (shared but dumb)
    - CONTEXT_BANK: Full institutional memory (shared + sophisticated)
    """
    SILOED_TYPICAL = "SILOED_TYPICAL"
    SILOED_ADVANCED = "SILOED_ADVANCED"
    GLOBAL_RAG = "GLOBAL_RAG"
    CONTEXT_BANK = "CONTEXT_BANK"

    # Legacy aliases for backwards compatibility
    WITHOUT_BANK = "SILOED_TYPICAL"  # Maps to basic silos
    WITH_BANK = "CONTEXT_BANK"       # Maps to full sophistication


# =============================================================================
# DEPARTMENT STRUCTURE
# =============================================================================
# Defines which departments exist and their relationships (for silo overlap)

DEPARTMENTS = {
    "Business Development": {
        "id": "biz_dev",
        "workflows": ["W2"],
        "adjacent_departments": ["Client Engagements", "Resource Management"],
        "context_ids": ["CTX-003", "CTX-007", "CTX-011"],  # Knowledge owned by this dept
    },
    "Client Engagements": {
        "id": "client_eng",
        "workflows": ["W1"],
        "adjacent_departments": ["Business Development", "Finance & Billing"],
        "context_ids": ["CTX-002", "CTX-008", "CTX-012"],
    },
    "Resource Management": {
        "id": "resource_mgmt",
        "workflows": ["W3"],
        "adjacent_departments": ["Business Development", "Client Engagements"],
        "context_ids": ["CTX-004", "CTX-010"],
    },
    "Vendor & Procurement": {
        "id": "vendor_proc",
        "workflows": ["W4"],
        "adjacent_departments": ["Finance & Billing"],
        "context_ids": ["CTX-001", "CTX-005"],
    },
    "Finance & Billing": {
        "id": "finance",
        "workflows": ["W5"],
        "adjacent_departments": ["Vendor & Procurement", "Client Engagements"],
        "context_ids": ["CTX-006", "CTX-009"],
    },
}


def get_visible_context_ids(department: str, condition: RunCondition) -> Set[str]:
    """
    Get the context IDs visible to a department under a given condition.

    Args:
        department: The department name (e.g., "Finance & Billing")
        condition: The experimental condition

    Returns:
        Set of context IDs the department can see
    """
    if condition in [RunCondition.GLOBAL_RAG, RunCondition.CONTEXT_BANK, RunCondition.WITH_BANK]:
        # Full visibility - all context IDs
        all_ids = set()
        for dept_info in DEPARTMENTS.values():
            all_ids.update(dept_info["context_ids"])
        return all_ids

    dept_info = DEPARTMENTS.get(department)
    if not dept_info:
        return set()

    visible = set(dept_info["context_ids"])

    if condition == RunCondition.SILOED_ADVANCED:
        # Add adjacent department context
        for adj_dept in dept_info["adjacent_departments"]:
            adj_info = DEPARTMENTS.get(adj_dept)
            if adj_info:
                visible.update(adj_info["context_ids"])

    # SILOED_TYPICAL only sees own department
    return visible


def get_department_for_agent(agent_id: str) -> str:
    """Get the department name for an agent."""
    agent_departments = {
        "proposal_agent": "Business Development",
        "staffing_agent": "Resource Management",
        "vendor_agent": "Vendor & Procurement",
        "billing_agent": "Finance & Billing",
    }
    return agent_departments.get(agent_id, "Unknown")


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

    Includes both within-department scenarios and cross-domain scenarios
    (where an agent needs knowledge from another department).
    """
    # Within-department scenarios (agent has access in siloed mode)
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

    # CROSS-DOMAIN SCENARIOS (agent needs knowledge from another department)
    # These demonstrate where siloed approaches fail most dramatically

    # Billing agent needs Client Engagements knowledge (CTX-002)
    meridian_billing_cross: List[int] = field(default_factory=lambda: [4, 9])

    # Staffing agent needs Vendor knowledge (CTX-001)
    brightline_staffing_cross: List[int] = field(default_factory=lambda: [5, 10])

    # Billing agent needs Business Development knowledge (CTX-003)
    hartwell_collection_cross: List[int] = field(default_factory=lambda: [7, 12])

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
        # Cross-domain scenarios
        if week in self.meridian_billing_cross:
            injections.append("meridian_billing_cross")
        if week in self.brightline_staffing_cross:
            injections.append("brightline_staffing_cross")
        if week in self.hartwell_collection_cross:
            injections.append("hartwell_collection_cross")
        return injections

    def is_brightline_week(self, week: int) -> bool:
        """Check if this week has a Brightline SOW scenario."""
        return week in self.brightline_sow

    def get_cross_domain_scenarios_for_week(self, week: int) -> List[str]:
        """Get cross-domain scenarios for a given week."""
        scenarios = []
        if week in self.meridian_billing_cross:
            scenarios.append("meridian_billing_cross")
        if week in self.brightline_staffing_cross:
            scenarios.append("brightline_staffing_cross")
        if week in self.hartwell_collection_cross:
            scenarios.append("hartwell_collection_cross")
        return scenarios


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
class ConditionCalibration:
    """
    Calibration parameters for a single experimental condition.

    Defines baseline accuracy, improvement rate, and caps for
    normal, chaos, and cross-domain scenarios.
    """
    # Base accuracy in normal (steady-state) operations
    baseline_normal: float

    # Weekly improvement rate (positive = improves, negative = degrades)
    weekly_improvement: float

    # Maximum accuracy cap
    max_accuracy: float

    # Accuracy under chaos conditions (staff departure, policy conflict, etc.)
    chaos_multiplier: float = 1.0  # Applied to baseline during chaos

    # Accuracy for cross-domain decisions (requires multi-department knowledge)
    cross_domain_multiplier: float = 1.0  # Applied to baseline for cross-domain


@dataclass
class PerformanceCalibration:
    """
    Calibration for graduated performance improvement over time.

    Defines accuracy trajectories for all four experimental conditions:
    - SILOED_TYPICAL: Basic department-only silos
    - SILOED_ADVANCED: Sophisticated silos with overlap and decay
    - GLOBAL_RAG: Unified but unsophisticated
    - CONTEXT_BANK: Full sophistication

    Calibrated mode only. These numbers ARE the result in that mode: a decision
    succeeds when a random draw falls below them, and retrieved context does not
    change the outcome. With equal values for all conditions, GLOBAL_RAG and
    CONTEXT_BANK score identically. Mechanistic mode (simulation/mechanistic.py)
    does not use them.
    """

    # Per-condition calibration
    siloed_typical: ConditionCalibration = field(default_factory=lambda: ConditionCalibration(
        baseline_normal=0.55,
        weekly_improvement=-0.005,  # Slight degradation (knowledge goes stale)
        max_accuracy=0.60,
        chaos_multiplier=0.73,      # 40% accuracy under chaos (55% * 0.73)
        cross_domain_multiplier=0.55,  # 30% accuracy cross-domain (55% * 0.55)
    ))

    siloed_advanced: ConditionCalibration = field(default_factory=lambda: ConditionCalibration(
        baseline_normal=0.62,
        weekly_improvement=-0.003,  # Slower degradation (has basic decay)
        max_accuracy=0.65,
        chaos_multiplier=0.81,      # 50% under chaos
        cross_domain_multiplier=0.73,  # 45% cross-domain
    ))

    global_rag: ConditionCalibration = field(default_factory=lambda: ConditionCalibration(
        baseline_normal=0.70,
        weekly_improvement=-0.004,  # Degrades (signal-to-noise worsens)
        max_accuracy=0.72,
        chaos_multiplier=0.79,      # 55% under chaos
        cross_domain_multiplier=0.79,  # 55% cross-domain
    ))

    context_bank: ConditionCalibration = field(default_factory=lambda: ConditionCalibration(
        baseline_normal=0.75,
        weekly_improvement=0.012,   # Improves (validation reinforces good knowledge)
        max_accuracy=0.92,
        chaos_multiplier=0.94,      # 80% under chaos (resilient!)
        cross_domain_multiplier=0.97,  # 82% cross-domain (knowledge flows)
    ))

    # Legacy compatibility
    baseline_accuracy_without_bank: float = 0.55
    baseline_accuracy_with_bank: float = 0.75
    weekly_improvement_without_bank: float = -0.005
    weekly_improvement_with_bank: float = 0.012
    max_accuracy_without_bank: float = 0.60
    max_accuracy_with_bank: float = 0.92

    def _get_calibration(self, condition: "RunCondition") -> ConditionCalibration:
        """Get calibration for a condition."""
        mapping = {
            RunCondition.SILOED_TYPICAL: self.siloed_typical,
            RunCondition.SILOED_ADVANCED: self.siloed_advanced,
            RunCondition.GLOBAL_RAG: self.global_rag,
            RunCondition.CONTEXT_BANK: self.context_bank,
            # Legacy mappings
            RunCondition.WITHOUT_BANK: self.siloed_typical,
            RunCondition.WITH_BANK: self.context_bank,
        }
        return mapping.get(condition, self.siloed_typical)

    def get_accuracy_for_week(
        self,
        condition: "RunCondition",
        week: int,
        is_chaos: bool = False,
        is_cross_domain: bool = False,
    ) -> float:
        """
        Calculate expected accuracy for a given condition and week.

        Args:
            condition: The experimental condition
            week: Simulation week (1-indexed)
            is_chaos: Whether chaos conditions are active
            is_cross_domain: Whether this is a cross-domain decision

        Returns:
            Expected accuracy as a float between 0 and 1
        """
        cal = self._get_calibration(condition)

        # Base calculation
        weeks_elapsed = week - 1
        accuracy = cal.baseline_normal + (cal.weekly_improvement * weeks_elapsed)
        accuracy = min(accuracy, cal.max_accuracy)

        # Apply modifiers
        if is_chaos:
            accuracy *= cal.chaos_multiplier
        if is_cross_domain:
            accuracy *= cal.cross_domain_multiplier

        return max(0.1, min(accuracy, 1.0))  # Clamp to [0.1, 1.0]

    def get_all_accuracies(self, week: int) -> Dict[str, Dict[str, float]]:
        """Get accuracy for all conditions at a given week."""
        result = {}
        for condition in [
            RunCondition.SILOED_TYPICAL,
            RunCondition.SILOED_ADVANCED,
            RunCondition.GLOBAL_RAG,
            RunCondition.CONTEXT_BANK,
        ]:
            result[condition.value] = {
                "normal": self.get_accuracy_for_week(condition, week),
                "chaos": self.get_accuracy_for_week(condition, week, is_chaos=True),
                "cross_domain": self.get_accuracy_for_week(condition, week, is_cross_domain=True),
            }
        return result


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
    # Default: Run the two extremes (basic silos vs full context bank)
    # Full comparison: Run all four conditions
    runs: List[RunCondition] = field(
        default_factory=lambda: [RunCondition.SILOED_TYPICAL, RunCondition.CONTEXT_BANK]
    )

    # For full 4-way comparison, use:
    # runs = [SILOED_TYPICAL, SILOED_ADVANCED, GLOBAL_RAG, CONTEXT_BANK]

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


# =============================================================================
# AGENT DEFINITIONS
# =============================================================================
# Each agent handles a specific domain of organizational decisions.
# In SILOED mode, each agent only has access to knowledge in their domain.
# In CONTEXT_BANK mode, all agents access unified institutional memory.

AGENTS = {
    "proposal_agent": {
        "id": "proposal_agent",
        "name": "Business Development AI",
        "display_name": "Business Development AI",
        "short_name": "BizDev AI",
        "role": "Evaluates opportunities, coordinates proposals, makes go/no-go recommendations",
        "department": "Business Development",
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
        "name": "Resource Management AI",
        "display_name": "Resource Management AI",
        "short_name": "Staffing AI",
        "role": "Assigns staff to projects, manages resource allocation and conflicts",
        "department": "Resource Management",
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
        "name": "Procurement AI",
        "display_name": "Procurement AI",
        "short_name": "Vendor AI",
        "role": "Manages vendor contracts, SOWs, approvals, and pricing negotiations",
        "department": "Vendor & Procurement",
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
        "name": "Accounts Receivable AI",
        "display_name": "Accounts Receivable AI",
        "short_name": "Billing AI",
        "role": "Generates invoices, manages collections, handles payment escalations",
        "department": "Finance & Billing",
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
