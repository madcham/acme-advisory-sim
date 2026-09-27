"""
Seeded Institutional Memory (Ground Truth Context Objects).

These 12 context objects represent the institutional knowledge that exists in every
organization but is typically scattered across people's heads, old emails, and
tribal knowledge. They are pre-loaded into the Context Bank before week one.

The simulation tests whether agents can find and use this knowledge to make
correct decisions — and what happens when they can't.

KNOWLEDGE CATEGORIES:
- Vendor Rules (CTX-001, CTX-005): How to handle specific vendors
- Client Rules (CTX-002, CTX-003, CTX-006): Client-specific behaviors and exceptions
- Staff Rules (CTX-004, CTX-008, CTX-010): People-specific policies and knowledge
- Compliance Rules (CTX-007, CTX-009): Required approvals and checks
- Expired Rules (CTX-011, CTX-012): Outdated knowledge that should be deprioritized

Each object includes:
- display_name: Human-readable title for the rule
- payload: The actual institutional knowledge
- structured_data: Machine-readable details for retrieval
- Confidence, decay, and classification metadata
"""

from datetime import datetime, timezone

from models.context_object import (
    ContextObject,
    ContentType,
    SourceType,
    DecayFunction,
    ContextGrade,
    OrgLineage,
)


def _create_seeded_objects() -> list[ContextObject]:
    """Create the 12 seeded context objects as defined in the spec."""

    # Base timestamp for all seeded objects (pre-simulation)
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)

    objects = [
        # =================================================================
        # CTX-001: OVERBILLING VENDOR - SECONDARY APPROVAL REQUIRED
        # =================================================================
        # Scenario: Brightline Consulting submits a new SOW
        # Correct: Route to David Okafor (Finance Director) for secondary approval
        # Wrong: Approve based solely on current terms
        # Why it matters: They overbilled us 40% in 2022
        ContextObject(
            id="CTX-001",
            display_name="Overbilling Vendor: Secondary Approval Required",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W4",
            department="Vendor & Procurement",
            week=0,
            content_type=ContentType.tribal_knowledge,
            payload=(
                "Brightline Consulting overbilled us 40% on a federal engagement in 2022. "
                "RULE: Always get secondary approval from David Okafor (Finance Director) "
                "before signing any Brightline SOW. No exceptions."
            ),
            structured_data={
                "vendor_name": "Brightline Consulting",
                "vendor_id": "brightline_consulting",
                "risk_level": "high",
                "required_approver": "David Okafor",
                "approver_role": "Finance Director",
                "approval_type": "secondary",
                "incident_year": 2022,
                "incident_type": "overbilling",
                "overcharge_percent": 40,
            },
            valid_from=base_time,
            decay_function=DecayFunction.step_function,
            confidence_at_creation=0.91,
            context_grade=ContextGrade.institutional_memory,
            context_grade_confidence=0.95,
            org_lineage=OrgLineage.failure_recovery,
            org_lineage_confidence=0.92,
        ),

        # =================================================================
        # CTX-002: FINANCIAL SERVICES SCOPE CREEP WARNING
        # =================================================================
        # Scenario: Working with a financial services client
        # Correct: Document any verbal scope expansion within 24 hours
        # Wrong: Let verbal agreements slide without documentation
        # Why it matters: These clients always try to expand scope verbally
        ContextObject(
            id="CTX-002",
            display_name="Financial Services Clients: Document Scope Changes Within 24 Hours",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W1",
            department="Client Engagements",
            week=0,
            content_type=ContentType.tribal_knowledge,
            payload=(
                "Financial services clients verbally expand scope in weeks 3-4 of engagements. "
                "RULE: Document any verbal scope expansion within 24 hours via email confirmation. "
                "If you don't, billing disputes will follow."
            ),
            structured_data={
                "client_type": "Financial Services",
                "risk_window": "Weeks 3-4",
                "action_required": "Document verbal scope changes",
                "deadline_hours": 24,
                "consequence_if_ignored": "Billing disputes",
            },
            valid_from=base_time,
            decay_function=DecayFunction.exponential,
            decay_rate=0.08,
            confidence_at_creation=0.87,
            context_grade=ContextGrade.institutional_memory,
            context_grade_confidence=0.90,
            org_lineage=OrgLineage.failure_recovery,
            org_lineage_confidence=0.88,
        ),

        # =================================================================
        # CTX-003: PARTNER OVERRIDE - HARTWELL GROUP EXCEPTION
        # =================================================================
        # Scenario: Hartwell Group opportunity comes in for go/no-go decision
        # Correct: Skip detailed margin analysis - Marcus Webb will approve regardless
        # Wrong: Spend hours on margin analysis that will be overridden anyway
        # Why it matters: Historical relationship, decision is predetermined
        ContextObject(
            id="CTX-003",
            display_name="Partner Override: Hartwell Group Always Approved",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W2",
            department="Business Development",
            week=0,
            content_type=ContentType.tribal_knowledge,
            payload=(
                "Marcus Webb (Senior Partner) will approve any Hartwell Group opportunity "
                "regardless of margin analysis. This is a historical relationship that bypasses "
                "the standard go/no-go process. Don't waste time on detailed analysis."
            ),
            structured_data={
                "decision_maker": "Marcus Webb",
                "decision_maker_role": "Senior Partner",
                "client_name": "Hartwell Group",
                "override_type": "Automatic approval",
                "reason": "Historical relationship",
                "standard_process_applies": False,
            },
            valid_from=base_time,
            decay_function=DecayFunction.permanent,
            confidence_at_creation=0.83,
            context_grade=ContextGrade.institutional_memory,
            context_grade_confidence=0.85,
            org_lineage=OrgLineage.political_settlement,
            org_lineage_confidence=0.90,
        ),

        # =================================================================
        # CTX-004: SENIOR STAFF REALLOCATION - 72-HOUR NOTICE REQUIRED
        # =================================================================
        # Scenario: Need to move a senior consultant to a different project
        # Correct: Give Priya Nair (HR Director) 72 hours notice first
        # Wrong: Reallocate immediately without notice
        # Why it matters: Surprise reassignments cause 2-week morale damage
        ContextObject(
            id="CTX-004",
            display_name="Senior Staff Reallocation: 72-Hour Notice to HR",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W3",
            department="Resource Management",
            week=0,
            content_type=ContentType.policy,
            payload=(
                "Before reallocating any senior resource, notify Priya Nair (HR Director) "
                "at least 72 hours in advance. Surprise reassignments create two-week "
                "morale recovery periods that hurt project delivery."
            ),
            structured_data={
                "stakeholder": "Priya Nair",
                "stakeholder_role": "HR Director",
                "notice_required_hours": 72,
                "applies_to": "Senior resources",
                "consequence_if_ignored": "2-week morale recovery period",
            },
            valid_from=base_time,
            decay_function=DecayFunction.step_function,
            confidence_at_creation=0.95,
            context_grade=ContextGrade.compliance_scaffolding,
            context_grade_confidence=0.97,
            org_lineage=OrgLineage.documented_policy,
            org_lineage_confidence=0.94,
        ),

        # =================================================================
        # CTX-005: VENDOR DISCOUNT - VANCE ANALYTICS NEGOTIATION LEVERAGE
        # =================================================================
        # Scenario: Negotiating a $500K+ engagement with Vance Analytics
        # Correct: Push for 15% discount (but don't reveal this upfront)
        # Wrong: Accept list pricing on large engagements
        # Why it matters: We've successfully negotiated this before
        ContextObject(
            id="CTX-005",
            display_name="Vendor Discount: Vance Analytics 15% on Large Deals",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W4",
            department="Vendor & Procurement",
            week=0,
            content_type=ContentType.tribal_knowledge,
            payload=(
                "Vance Analytics will discount up to 15% below list price on engagements "
                "over $500K. We've done this before. Don't reveal this leverage in the "
                "initial SOW — let them propose pricing first, then negotiate down."
            ),
            structured_data={
                "vendor_name": "Vance Analytics",
                "discount_available": "15%",
                "minimum_deal_size": "$500,000",
                "negotiation_tip": "Don't reveal leverage upfront",
            },
            valid_from=base_time,
            decay_function=DecayFunction.exponential,
            decay_rate=0.12,
            confidence_at_creation=0.78,
            context_grade=ContextGrade.institutional_memory,
            context_grade_confidence=0.82,
            org_lineage=OrgLineage.direct_observation,
            org_lineage_confidence=0.75,
        ),

        # =================================================================
        # CTX-006: CLIENT PAYMENT CYCLE - TERRALOGIC 60-DAY RULE
        # =================================================================
        # Scenario: TerraLogic invoice is overdue per contract terms
        # Correct: Wait until day 65 before escalating
        # Wrong: Escalate at day 30/45 like normal clients
        # Why it matters: Premature escalation cost us this account in 2023
        ContextObject(
            id="CTX-006",
            display_name="Client Payment Cycle: TerraLogic Always Pays at 60 Days",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W5",
            department="Finance & Billing",
            week=0,
            content_type=ContentType.tribal_knowledge,
            payload=(
                "TerraLogic has a 60-day payment cycle regardless of what the contract says. "
                "DO NOT escalate before day 65. We lost this account in 2023 because someone "
                "escalated prematurely. They always pay — just on their own schedule."
            ),
            structured_data={
                "client_name": "TerraLogic",
                "actual_payment_cycle_days": 60,
                "do_not_escalate_before_day": 65,
                "incident_year": 2023,
                "incident_consequence": "Account loss",
                "key_insight": "They always pay, just on their schedule",
            },
            valid_from=base_time,
            decay_function=DecayFunction.step_function,
            confidence_at_creation=0.89,
            context_grade=ContextGrade.institutional_memory,
            context_grade_confidence=0.91,
            org_lineage=OrgLineage.failure_recovery,
            org_lineage_confidence=0.93,
        ),

        # =================================================================
        # CTX-007: COMPLIANCE - FORMER EMPLOYEE CONFLICT CHECK
        # =================================================================
        # Scenario: Engaging with a client where former Acme staff now work
        # Correct: Run manual conflict of interest check before proceeding
        # Wrong: Assume the system flags this automatically (it doesn't)
        # Why it matters: Legal/compliance requirement, system gap
        ContextObject(
            id="CTX-007",
            display_name="Compliance: Manual COI Check for Former Employees at Client",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W2",
            department="Business Development",
            week=0,
            content_type=ContentType.policy,
            payload=(
                "When engaging with any client where former Acme employees now work, "
                "a conflict of interest check is REQUIRED. The system does NOT flag this "
                "automatically — you must check manually before proceeding."
            ),
            structured_data={
                "check_type": "Conflict of Interest",
                "trigger": "Former employee at client",
                "system_automated": False,
                "action_required": "Manual check before engagement",
                "compliance_requirement": True,
            },
            valid_from=base_time,
            decay_function=DecayFunction.permanent,
            confidence_at_creation=0.94,
            context_grade=ContextGrade.compliance_scaffolding,
            context_grade_confidence=0.96,
            org_lineage=OrgLineage.documented_policy,
            org_lineage_confidence=0.92,
        ),

        # =================================================================
        # CTX-008: SUBJECT MATTER EXPERT - FINANCIAL SERVICES METHODOLOGY
        # =================================================================
        # Scenario: Kicking off a financial services engagement
        # Correct: Consult Elena Vasquez directly for methodology
        # Wrong: Look for FS methodology in the knowledge base (it's not there)
        # Why it matters: Critical undocumented expertise lives in one person's head
        ContextObject(
            id="CTX-008",
            display_name="Expert Knowledge: Elena Vasquez Owns FS Methodology",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W1",
            department="Client Engagements",
            week=0,
            content_type=ContentType.tribal_knowledge,
            payload=(
                "Elena Vasquez (Practice Lead) holds the master methodology for all "
                "financial services engagements. This is NOT documented in any knowledge base. "
                "For any FS project, consult her directly before starting."
            ),
            structured_data={
                "expert_name": "Elena Vasquez",
                "expert_role": "Practice Lead",
                "domain": "Financial Services",
                "knowledge_type": "Methodology",
                "documented_in_kb": False,
                "access_method": "Direct consultation required",
            },
            valid_from=base_time,
            decay_function=DecayFunction.exponential,
            decay_rate=0.15,
            confidence_at_creation=0.72,
            context_grade=ContextGrade.institutional_memory,
            context_grade_confidence=0.78,
            org_lineage=OrgLineage.direct_observation,
            org_lineage_confidence=0.70,
        ),

        # =================================================================
        # CTX-009: CEO APPROVAL REQUIRED - WRITE-OFFS ABOVE $15K
        # =================================================================
        # Scenario: Processing a write-off request over $15,000
        # Correct: Route to CEO (James Holloway) regardless of approval matrix
        # Wrong: Follow the documented approval matrix (it's outdated)
        # Why it matters: CEO changed this rule verbally, not in official docs
        ContextObject(
            id="CTX-009",
            display_name="CEO Approval: Write-offs Over $15K Need James Holloway",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W5",
            department="Finance & Billing",
            week=0,
            content_type=ContentType.tribal_knowledge,
            payload=(
                "Write-off requests above $15,000 require CEO approval from James Holloway. "
                "This overrides the documented approval matrix. James announced this verbally "
                "in Q3 2024 but it was never added to the policy docs."
            ),
            structured_data={
                "threshold_amount": "$15,000",
                "required_approver": "James Holloway",
                "approver_role": "CEO",
                "policy_documented": False,
                "policy_announced": "Q3 2024 (verbal)",
                "overrides_approval_matrix": True,
            },
            valid_from=base_time,
            decay_function=DecayFunction.step_function,
            confidence_at_creation=0.85,
            context_grade=ContextGrade.institutional_memory,
            context_grade_confidence=0.88,
            org_lineage=OrgLineage.political_settlement,
            org_lineage_confidence=0.86,
        ),

        # =================================================================
        # CTX-010: STAFF-CLIENT CONFLICT - JORDAN PARK / NEXUM PARTNERS
        # =================================================================
        # Scenario: Assigning staff to a Nexum Partners project
        # Correct: Never assign Jordan Park to Nexum work
        # Wrong: Assign Jordan based on skills/availability (ignoring conflict)
        # Why it matters: Documented HR conflict, system doesn't flag it
        ContextObject(
            id="CTX-010",
            display_name="Staff Conflict: Jordan Park Cannot Work with Nexum Partners",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W3",
            department="Resource Management",
            week=0,
            content_type=ContentType.policy,
            payload=(
                "Jordan Park has a documented HR conflict with Nexum Partners. "
                "NEVER assign Jordan to any Nexum work. There is an HR record of this "
                "conflict, but the staffing system does NOT flag it automatically."
            ),
            structured_data={
                "staff_name": "Jordan Park",
                "client_name": "Nexum Partners",
                "conflict_type": "Documented HR conflict",
                "hr_record_exists": True,
                "system_flags_automatically": False,
                "action_required": "Never assign to this client",
            },
            valid_from=base_time,
            decay_function=DecayFunction.permanent,
            confidence_at_creation=0.97,
            context_grade=ContextGrade.compliance_scaffolding,
            context_grade_confidence=0.98,
            org_lineage=OrgLineage.failure_recovery,
            org_lineage_confidence=0.95,
        ),

        # =================================================================
        # CTX-011: [EXPIRED] FRIDAY PROPOSAL TIMING OBSERVATION
        # =================================================================
        # This is INTENTIONALLY low-grade expired knowledge
        # Agents should learn to deprioritize or ignore this
        # Tests: Does the system correctly identify outdated knowledge?
        ContextObject(
            id="CTX-011",
            display_name="[EXPIRED] Friday Proposal Win Rate Observation",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W2",
            department="Business Development",
            week=0,
            content_type=ContentType.observation,
            payload=(
                "[OUTDATED - LOW CONFIDENCE] Historical observation that Friday proposals "
                "had 23% lower win rates. Based on old data. Market conditions have changed. "
                "Do not rely on this for decision-making."
            ),
            structured_data={
                "observation_type": "Win rate correlation",
                "data_age": "3+ years old",
                "current_validity": "Questionable",
                "recommendation": "Do not rely on this",
            },
            valid_from=base_time,
            decay_function=DecayFunction.exponential,
            decay_rate=0.20,
            confidence_at_creation=0.41,
            context_grade=ContextGrade.expired_process,
            context_grade_confidence=0.75,
            org_lineage=OrgLineage.direct_observation,
            org_lineage_confidence=0.65,
        ),

        # =================================================================
        # CTX-012: [EXPIRED] 50-PAGE PARTNER REVIEW REQUIREMENT
        # =================================================================
        # This is INTENTIONALLY low-grade expired knowledge
        # Old policy that no longer applies broadly
        # Tests: Does the system correctly identify outdated policies?
        ContextObject(
            id="CTX-012",
            display_name="[EXPIRED] Partner Review for 50+ Page Deliverables",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W1",
            department="Client Engagements",
            week=0,
            content_type=ContentType.policy,
            payload=(
                "[OUTDATED - POLICY CHANGED] The old rule requiring senior partner review "
                "for all deliverables over 50 pages ended in 2023. It now ONLY applies to "
                "regulatory submissions. Many staff still follow the old rule unnecessarily."
            ),
            structured_data={
                "policy_status": "Expired in 2023",
                "current_scope": "Regulatory submissions only",
                "common_mistake": "Staff still over-applying old rule",
                "action": "Only enforce for regulatory submissions",
            },
            valid_from=base_time,
            decay_function=DecayFunction.exponential,
            decay_rate=0.25,
            confidence_at_creation=0.31,
            context_grade=ContextGrade.expired_process,
            context_grade_confidence=0.80,
            org_lineage=OrgLineage.documented_policy,
            org_lineage_confidence=0.70,
        ),
    ]

    return objects


# Pre-created seeded context objects
SEEDED_CONTEXT_OBJECTS: list[ContextObject] = _create_seeded_objects()


def get_seeded_object(ctx_id: str) -> ContextObject:
    """Retrieve a specific seeded context object by ID."""
    for obj in SEEDED_CONTEXT_OBJECTS:
        if obj.id == ctx_id:
            return obj
    raise ValueError(f"Unknown seeded context object: {ctx_id}")


def get_seeded_objects_for_workflow(workflow_id: str) -> list[ContextObject]:
    """Get all seeded context objects relevant to a specific workflow."""
    return [obj for obj in SEEDED_CONTEXT_OBJECTS if obj.workflow_id == workflow_id]


def get_high_confidence_objects(threshold: float = 0.80) -> list[ContextObject]:
    """Get seeded objects with confidence above threshold."""
    return [obj for obj in SEEDED_CONTEXT_OBJECTS if obj.confidence_at_creation >= threshold]


def get_expired_process_objects() -> list[ContextObject]:
    """Get the intentionally low-grade expired process objects (CTX-011, CTX-012)."""
    return [obj for obj in SEEDED_CONTEXT_OBJECTS if obj.context_grade == ContextGrade.expired_process]
