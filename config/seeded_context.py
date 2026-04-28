"""
Seeded Institutional Memory (Ground Truth Context Objects).

These 12 context objects are pre-loaded into the bank before week one.
They encode real organizational intelligence that an agent should find and use.
Their presence or absence in agent decision-making is a primary measurement signal.

Note: CTX-011 and CTX-012 are intentionally low-grade expired process objects.
Agents that correctly ignore or deprioritize these demonstrate that context
grade classification is working.
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
        # CTX-001: Brightline Consulting secondary approval
        # THIS IS THE KEY SCENARIO - Brightline SOW must route through David Okafor
        ContextObject(
            id="CTX-001",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W4",
            week=0,
            content_type=ContentType.tribal_knowledge,
            payload=(
                "Brightline Consulting always requires secondary approval from David Okafor "
                "before SOW issuance. Root cause: 2022 invoice dispute where Brightline billed "
                "40% above agreed rate on a federal engagement."
            ),
            structured_data={
                "vendor": "brightline_consulting",
                "required_approver": "david_okafor",
                "approval_type": "secondary",
                "root_cause_year": 2022,
                "incident_type": "invoice_dispute",
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

        # CTX-002: Financial services scope creep pattern
        ContextObject(
            id="CTX-002",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W1",
            week=0,
            content_type=ContentType.tribal_knowledge,
            payload=(
                "Financial services clients verbally expand scope in week 3-4 of engagements. "
                "Always document verbal expansions within 24 hours or billing disputes follow."
            ),
            structured_data={
                "client_vertical": "financial_services",
                "scope_expansion_window": "week_3_4",
                "documentation_deadline_hours": 24,
                "consequence": "billing_disputes",
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

        # CTX-003: Marcus Webb Hartwell Group override
        ContextObject(
            id="CTX-003",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W2",
            week=0,
            content_type=ContentType.tribal_knowledge,
            payload=(
                "Marcus Webb will override go/no-go on any Hartwell Group opportunity "
                "regardless of margin. Historical relationship, not subject to standard process."
            ),
            structured_data={
                "partner": "marcus_webb",
                "client": "hartwell_group",
                "override_type": "go_no_go",
                "reason": "historical_relationship",
                "margin_override": True,
            },
            valid_from=base_time,
            decay_function=DecayFunction.permanent,
            confidence_at_creation=0.83,
            context_grade=ContextGrade.institutional_memory,
            context_grade_confidence=0.85,
            org_lineage=OrgLineage.political_settlement,
            org_lineage_confidence=0.90,
        ),

        # CTX-004: Priya Nair 72-hour notice requirement
        ContextObject(
            id="CTX-004",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W3",
            week=0,
            content_type=ContentType.policy,
            payload=(
                "Priya Nair requires 72-hour notice before any senior resource reallocation. "
                "Violations create two-week morale recovery periods."
            ),
            structured_data={
                "stakeholder": "priya_nair",
                "notice_hours": 72,
                "resource_level": "senior",
                "consequence": "morale_impact",
                "recovery_weeks": 2,
            },
            valid_from=base_time,
            decay_function=DecayFunction.step_function,
            confidence_at_creation=0.95,
            context_grade=ContextGrade.compliance_scaffolding,
            context_grade_confidence=0.97,
            org_lineage=OrgLineage.documented_policy,
            org_lineage_confidence=0.94,
        ),

        # CTX-005: Vance Analytics pricing negotiation
        ContextObject(
            id="CTX-005",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W4",
            week=0,
            content_type=ContentType.tribal_knowledge,
            payload=(
                "Vance Analytics pricing is negotiable up to 15% below list when engagement "
                "is over $500K. Do not disclose this in initial SOW."
            ),
            structured_data={
                "vendor": "vance_analytics",
                "discount_percent": 15,
                "threshold_amount": 500000,
                "disclosure_rule": "do_not_disclose_initially",
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

        # CTX-006: TerraLogic payment cycle
        ContextObject(
            id="CTX-006",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W5",
            week=0,
            content_type=ContentType.tribal_knowledge,
            payload=(
                "Client TerraLogic has a 60-day payment cycle regardless of contract terms. "
                "Do not escalate before day 65. Premature escalation caused account loss in 2023."
            ),
            structured_data={
                "client": "terralogic",
                "actual_payment_days": 60,
                "escalation_threshold_days": 65,
                "incident_year": 2023,
                "incident_type": "account_loss",
            },
            valid_from=base_time,
            decay_function=DecayFunction.step_function,
            confidence_at_creation=0.89,
            context_grade=ContextGrade.institutional_memory,
            context_grade_confidence=0.91,
            org_lineage=OrgLineage.failure_recovery,
            org_lineage_confidence=0.93,
        ),

        # CTX-007: Conflict of interest manual check
        ContextObject(
            id="CTX-007",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W2",
            week=0,
            content_type=ContentType.policy,
            payload=(
                "Conflict of interest check is required for any engagement where former Acme "
                "staff now work at the client. System does not flag this automatically. "
                "Manual check required."
            ),
            structured_data={
                "check_type": "conflict_of_interest",
                "trigger": "former_staff_at_client",
                "automation_status": "not_automated",
                "action_required": "manual_check",
            },
            valid_from=base_time,
            decay_function=DecayFunction.permanent,
            confidence_at_creation=0.94,
            context_grade=ContextGrade.compliance_scaffolding,
            context_grade_confidence=0.96,
            org_lineage=OrgLineage.documented_policy,
            org_lineage_confidence=0.92,
        ),

        # CTX-008: Elena Vasquez FS methodology
        ContextObject(
            id="CTX-008",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W1",
            week=0,
            content_type=ContentType.tribal_knowledge,
            payload=(
                "Elena Vasquez holds the master methodology for financial services engagements. "
                "Not in the knowledge base. Must be consulted directly for FS projects."
            ),
            structured_data={
                "knowledge_holder": "elena_vasquez",
                "domain": "financial_services",
                "knowledge_type": "methodology",
                "kb_status": "not_documented",
                "access_method": "direct_consultation",
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

        # CTX-009: CEO write-off approval threshold
        ContextObject(
            id="CTX-009",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W5",
            week=0,
            content_type=ContentType.tribal_knowledge,
            payload=(
                "Write-off requests above $15K require CEO approval regardless of what the "
                "approval matrix says. James Holloway updated this verbally in Q3 2024. "
                "Not in policy docs."
            ),
            structured_data={
                "threshold_amount": 15000,
                "approver": "james_holloway",
                "approver_role": "ceo",
                "policy_status": "verbal_only",
                "update_date": "Q3_2024",
                "documented": False,
            },
            valid_from=base_time,
            decay_function=DecayFunction.step_function,
            confidence_at_creation=0.85,
            context_grade=ContextGrade.institutional_memory,
            context_grade_confidence=0.88,
            org_lineage=OrgLineage.political_settlement,
            org_lineage_confidence=0.86,
        ),

        # CTX-010: Jordan Park Nexum conflict
        ContextObject(
            id="CTX-010",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W3",
            week=0,
            content_type=ContentType.policy,
            payload=(
                "Staff member Jordan Park has a documented conflict with client Nexum Partners. "
                "Do not assign to any Nexum work. HR record exists but system does not flag."
            ),
            structured_data={
                "staff_member": "jordan_park",
                "client": "nexum_partners",
                "conflict_type": "documented",
                "hr_record": True,
                "system_flag": False,
                "action": "do_not_assign",
            },
            valid_from=base_time,
            decay_function=DecayFunction.permanent,
            confidence_at_creation=0.97,
            context_grade=ContextGrade.compliance_scaffolding,
            context_grade_confidence=0.98,
            org_lineage=OrgLineage.failure_recovery,
            org_lineage_confidence=0.95,
        ),

        # CTX-011: Friday proposal submission (EXPIRED PROCESS)
        # Intentionally low-grade - agents should deprioritize
        ContextObject(
            id="CTX-011",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W2",
            week=0,
            content_type=ContentType.observation,
            payload=(
                "Proposals submitted on Fridays have a 23% lower win rate based on three years "
                "of data. Internal best practice: submit Tuesday through Thursday."
            ),
            structured_data={
                "metric": "win_rate",
                "friday_delta_percent": -23,
                "data_period_years": 3,
                "recommended_days": ["tuesday", "wednesday", "thursday"],
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

        # CTX-012: 50-page deliverable review (EXPIRED PROCESS)
        # Intentionally low-grade - agents should deprioritize
        ContextObject(
            id="CTX-012",
            created_at=base_time,
            created_by="system",
            source_type=SourceType.system,
            workflow_id="W1",
            week=0,
            content_type=ContentType.policy,
            payload=(
                "Senior partner review of all deliverables over 50 pages was policy until 2023. "
                "Now only applies to regulatory submissions. Many staff still follow old rule "
                "unnecessarily."
            ),
            structured_data={
                "old_threshold_pages": 50,
                "old_policy_end_year": 2023,
                "current_scope": "regulatory_submissions_only",
                "compliance_status": "over_applied",
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
