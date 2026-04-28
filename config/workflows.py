"""
Workflow definitions for Acme Advisory.

Defines the five primary and three secondary workflows with their standard paths,
exception paths, and exception occurrence rates.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class WorkflowType(str, Enum):
    """Classification of workflow importance."""
    PRIMARY = "primary"
    SECONDARY = "secondary"


@dataclass
class WorkflowStep:
    """A single step in a workflow."""
    id: str
    name: str
    description: str
    typical_duration_days: float
    required_roles: List[str] = field(default_factory=list)
    can_be_skipped: bool = False


@dataclass
class ExceptionPath:
    """An exception path that can occur during a workflow."""
    id: str
    name: str
    description: str
    occurrence_rate: float  # Probability of this exception occurring (0.0 to 1.0)
    trigger_condition: str
    resolution_steps: List[str]
    context_objects_relevant: List[str] = field(default_factory=list)  # CTX IDs that help resolve


@dataclass
class Workflow:
    """A complete workflow definition."""
    id: str
    name: str
    workflow_type: WorkflowType
    description: str
    standard_path: List[WorkflowStep]
    exception_paths: List[ExceptionPath]
    primary_department: str
    supporting_departments: List[str] = field(default_factory=list)
    agents_involved: List[str] = field(default_factory=list)


# W1: Client Engagement Delivery
W1_CLIENT_ENGAGEMENT = Workflow(
    id="W1",
    name="Client Engagement Delivery",
    workflow_type=WorkflowType.PRIMARY,
    description="End-to-end execution of client engagements from kickoff to close-out",
    primary_department="client_delivery",
    supporting_departments=["talent_staffing", "finance_operations", "knowledge_management"],
    agents_involved=[],  # No agent directly assigned
    standard_path=[
        WorkflowStep("W1_01", "Kickoff", "Initial client meeting and project setup", 2.0, ["manager", "partner"]),
        WorkflowStep("W1_02", "Discovery", "Requirements gathering and analysis", 5.0, ["consultant", "senior_consultant"]),
        WorkflowStep("W1_03", "Analysis", "Data analysis and insight development", 7.0, ["consultant", "senior_consultant", "manager"]),
        WorkflowStep("W1_04", "Draft Deliverable", "Create initial deliverable", 5.0, ["consultant", "senior_consultant"]),
        WorkflowStep("W1_05", "Client Review", "Client reviews and provides feedback", 5.0, ["manager"]),
        WorkflowStep("W1_06", "Revision", "Incorporate client feedback", 3.0, ["consultant", "senior_consultant"]),
        WorkflowStep("W1_07", "Final Delivery", "Deliver final work product", 1.0, ["manager", "partner"]),
        WorkflowStep("W1_08", "Close-out", "Project closure and knowledge capture", 2.0, ["manager"]),
    ],
    exception_paths=[
        ExceptionPath(
            id="W1_EX_01",
            name="Scope Expansion Request",
            description="Client requests additional scope mid-engagement",
            occurrence_rate=0.35,
            trigger_condition="Client verbally requests work outside original SOW",
            resolution_steps=["Document verbal request within 24 hours", "Draft change order", "Get client sign-off", "Update project plan"],
            context_objects_relevant=["CTX-002"],  # FS scope creep pattern
        ),
        ExceptionPath(
            id="W1_EX_02",
            name="Key Team Member Departure",
            description="Critical team member leaves mid-engagement",
            occurrence_rate=0.12,
            trigger_condition="Staff resignation or reassignment during active project",
            resolution_steps=["Knowledge transfer session", "Identify replacement", "Client communication", "Onboard replacement"],
            context_objects_relevant=["CTX-004"],  # Priya 72hr notice
        ),
        ExceptionPath(
            id="W1_EX_03",
            name="Client Escalation",
            description="Client escalates due to deliverable quality concerns",
            occurrence_rate=0.18,
            trigger_condition="Client expresses dissatisfaction with deliverable quality",
            resolution_steps=["Partner engagement", "Root cause analysis", "Recovery plan", "Quality review gate"],
            context_objects_relevant=["CTX-008"],  # Elena methodology
        ),
        ExceptionPath(
            id="W1_EX_04",
            name="Subcontractor Underperformance",
            description="Subcontractor fails to meet quality or timeline expectations",
            occurrence_rate=0.09,
            trigger_condition="Subcontractor deliverable rejected or delayed",
            resolution_steps=["Performance review", "Replacement sourcing", "SOW amendment", "Timeline adjustment"],
            context_objects_relevant=["CTX-001", "CTX-005"],  # Brightline, Vance
        ),
    ]
)

# W2: Proposal Development and Pursuit
W2_PROPOSAL = Workflow(
    id="W2",
    name="Proposal Development and Pursuit",
    workflow_type=WorkflowType.PRIMARY,
    description="Full pursuit cycle from opportunity identification to win/loss",
    primary_department="business_development",
    supporting_departments=["client_delivery", "finance_operations"],
    agents_involved=["proposal_agent"],
    standard_path=[
        WorkflowStep("W2_01", "Opportunity Identified", "New business opportunity surfaces", 1.0, ["senior_manager", "partner"]),
        WorkflowStep("W2_02", "Go/No-Go Decision", "Evaluate fit and capacity", 2.0, ["partner"]),
        WorkflowStep("W2_03", "Proposal Team Assembly", "Staff the proposal effort", 1.0, ["manager"]),
        WorkflowStep("W2_04", "RFP Response Drafted", "Write proposal content", 5.0, ["consultant", "senior_consultant", "manager"]),
        WorkflowStep("W2_05", "Pricing Approved", "Internal pricing review and approval", 2.0, ["partner", "finance"]),
        WorkflowStep("W2_06", "Submission", "Submit proposal to client", 0.5, ["manager"]),
        WorkflowStep("W2_07", "Follow-up", "Post-submission engagement", 10.0, ["senior_manager", "partner"]),
        WorkflowStep("W2_08", "Win/Loss", "Outcome determination", 1.0, ["partner"]),
    ],
    exception_paths=[
        ExceptionPath(
            id="W2_EX_01",
            name="Pricing Exception Required",
            description="Proposed margin falls below threshold",
            occurrence_rate=0.28,
            trigger_condition="Margin calculation below 25% threshold",
            resolution_steps=["Exception request form", "Finance review", "Partner approval", "Document rationale"],
            context_objects_relevant=["CTX-005"],  # Vance pricing
        ),
        ExceptionPath(
            id="W2_EX_02",
            name="Conflict of Interest Check",
            description="Potential COI identified requiring review",
            occurrence_rate=0.15,
            trigger_condition="Former Acme staff at client or competitive conflict",
            resolution_steps=["COI form completion", "Legal review", "Partner sign-off", "Mitigation plan"],
            context_objects_relevant=["CTX-007"],  # COI manual check
        ),
        ExceptionPath(
            id="W2_EX_03",
            name="Partner Override on Go/No-Go",
            description="Partner overrides standard go/no-go decision",
            occurrence_rate=0.20,
            trigger_condition="Strategic relationship trumps standard criteria",
            resolution_steps=["Document override rationale", "Adjust resource plan", "Notify finance"],
            context_objects_relevant=["CTX-003"],  # Marcus Webb Hartwell
        ),
        ExceptionPath(
            id="W2_EX_04",
            name="Rushed Timeline",
            description="Proposal timeline requires senior resource reallocation",
            occurrence_rate=0.22,
            trigger_condition="RFP deadline less than 5 days out",
            resolution_steps=["Identify available seniors", "Get staffing approval", "Compress timeline"],
            context_objects_relevant=["CTX-004"],  # Priya 72hr notice
        ),
    ]
)

# W3: Resource Allocation and Staffing
W3_STAFFING = Workflow(
    id="W3",
    name="Resource Allocation and Staffing",
    workflow_type=WorkflowType.PRIMARY,
    description="Matching resources to engagement needs",
    primary_department="talent_staffing",
    supporting_departments=["client_delivery", "executive_leadership"],
    agents_involved=["staffing_agent"],
    standard_path=[
        WorkflowStep("W3_01", "Project Need Identified", "Engagement requires staffing", 0.5, ["manager"]),
        WorkflowStep("W3_02", "Skills Match", "Identify candidates with required skills", 1.0, ["staffing"]),
        WorkflowStep("W3_03", "Availability Check", "Verify candidate availability", 0.5, ["staffing"]),
        WorkflowStep("W3_04", "Assignment", "Make staffing decision", 0.5, ["staffing", "manager"]),
        WorkflowStep("W3_05", "Confirmation", "Staff member confirms assignment", 1.0, ["consultant"]),
        WorkflowStep("W3_06", "Onboarding", "Orient staff to engagement", 2.0, ["manager"]),
    ],
    exception_paths=[
        ExceptionPath(
            id="W3_EX_01",
            name="No Available Match",
            description="No internal staff available, requires subcontractor",
            occurrence_rate=0.31,
            trigger_condition="All qualified staff at or above utilization target",
            resolution_steps=["Subcontractor request", "Vendor check", "SOW issuance", "Onboarding"],
            context_objects_relevant=["CTX-001", "CTX-005"],  # Brightline, Vance
        ),
        ExceptionPath(
            id="W3_EX_02",
            name="Assignment Conflict",
            description="Two projects competing for same resource",
            occurrence_rate=0.24,
            trigger_condition="Resource requested by multiple active engagements",
            resolution_steps=["Priority assessment", "Partner escalation", "Client impact review", "Decision"],
            context_objects_relevant=[],
        ),
        ExceptionPath(
            id="W3_EX_03",
            name="Staff Refusal",
            description="Staff refuses assignment due to prior client relationship",
            occurrence_rate=0.08,
            trigger_condition="Staff has documented conflict or history with client",
            resolution_steps=["Review conflict", "HR check", "Alternative staffing", "Document reason"],
            context_objects_relevant=["CTX-010"],  # Jordan Park Nexum
        ),
        ExceptionPath(
            id="W3_EX_04",
            name="Utilization Override",
            description="Leadership overrides utilization constraint",
            occurrence_rate=0.17,
            trigger_condition="Strategic priority trumps utilization target",
            resolution_steps=["Document override", "Adjust forecast", "Notify affected projects"],
            context_objects_relevant=["CTX-004"],  # Priya notice
        ),
    ]
)

# W4: Vendor and Subcontractor Management
W4_VENDOR = Workflow(
    id="W4",
    name="Vendor and Subcontractor Management",
    workflow_type=WorkflowType.PRIMARY,
    description="Procuring and managing external vendor relationships",
    primary_department="finance_operations",
    supporting_departments=["client_delivery", "talent_staffing"],
    agents_involved=["vendor_agent"],
    standard_path=[
        WorkflowStep("W4_01", "Need Identified", "External resource requirement identified", 0.5, ["manager"]),
        WorkflowStep("W4_02", "Approved Vendor Check", "Check if vendor is pre-approved", 0.5, ["finance"]),
        WorkflowStep("W4_03", "SOW Issued", "Statement of work drafted and sent", 2.0, ["finance", "manager"]),
        WorkflowStep("W4_04", "Work Delivered", "Vendor completes work", 10.0, ["consultant"]),
        WorkflowStep("W4_05", "Quality Review", "Review vendor deliverable", 2.0, ["manager"]),
        WorkflowStep("W4_06", "Invoice Approved", "Approve vendor invoice", 1.0, ["finance"]),
        WorkflowStep("W4_07", "Payment", "Process payment to vendor", 3.0, ["finance"]),
    ],
    exception_paths=[
        ExceptionPath(
            id="W4_EX_01",
            name="Vendor Not on Approved List",
            description="Requested vendor requires new vendor setup",
            occurrence_rate=0.33,
            trigger_condition="Vendor not in approved vendor database",
            resolution_steps=["New vendor form", "Due diligence", "Finance approval", "Add to list"],
            context_objects_relevant=[],
        ),
        ExceptionPath(
            id="W4_EX_02",
            name="Historical Pricing Dispute",
            description="Vendor has prior billing issues requiring secondary approval",
            occurrence_rate=0.41,
            trigger_condition="Vendor flagged for past pricing discrepancy",
            resolution_steps=["Pull historical records", "Secondary approval from David Okafor", "Rate negotiation", "SOW with explicit terms"],
            context_objects_relevant=["CTX-001"],  # Brightline secondary approval - THIS IS THE KEY SCENARIO
        ),
        ExceptionPath(
            id="W4_EX_03",
            name="Quality Dispute",
            description="Vendor deliverable fails quality review",
            occurrence_rate=0.19,
            trigger_condition="Deliverable rejected by engagement team",
            resolution_steps=["Document issues", "Vendor communication", "Rework or replacement", "Relationship review"],
            context_objects_relevant=[],
        ),
        ExceptionPath(
            id="W4_EX_04",
            name="Sole Source Justification",
            description="Only one vendor can meet requirement",
            occurrence_rate=0.14,
            trigger_condition="Unique capability or timeline constraint",
            resolution_steps=["Sole source form", "Partner approval", "Document rationale"],
            context_objects_relevant=["CTX-005"],  # Vance pricing negotiation
        ),
    ]
)

# W5: Client Billing and Collections
W5_BILLING = Workflow(
    id="W5",
    name="Client Billing and Collections",
    workflow_type=WorkflowType.PRIMARY,
    description="Invoicing clients and collecting payment",
    primary_department="finance_operations",
    supporting_departments=["client_delivery"],
    agents_involved=["billing_agent"],
    standard_path=[
        WorkflowStep("W5_01", "Milestone Achieved", "Billing milestone reached", 0.5, ["manager"]),
        WorkflowStep("W5_02", "Time Logged", "Team time entries completed", 1.0, ["consultant"]),
        WorkflowStep("W5_03", "Invoice Generated", "Create invoice from time and expenses", 1.0, ["finance"]),
        WorkflowStep("W5_04", "Client Review", "Client reviews invoice", 5.0, ["client"]),
        WorkflowStep("W5_05", "Payment Received", "Payment processed", 30.0, ["finance"]),
    ],
    exception_paths=[
        ExceptionPath(
            id="W5_EX_01",
            name="Scope Dispute",
            description="Client disputes charges as out of scope",
            occurrence_rate=0.29,
            trigger_condition="Client challenges invoice line items",
            resolution_steps=["Pull SOW and change orders", "Document verbal agreements", "Partner negotiation", "Adjustment or hold firm"],
            context_objects_relevant=["CTX-002"],  # FS scope documentation
        ),
        ExceptionPath(
            id="W5_EX_02",
            name="Payment Delayed",
            description="Payment exceeds 45 days requiring escalation",
            occurrence_rate=0.22,
            trigger_condition="Invoice unpaid after 45 days",
            resolution_steps=["Collections call", "Partner engagement", "Payment plan", "Legal if needed"],
            context_objects_relevant=["CTX-006"],  # TerraLogic 60-day cycle
        ),
        ExceptionPath(
            id="W5_EX_03",
            name="Write-off Request",
            description="Uncollectable amount requires write-off approval",
            occurrence_rate=0.11,
            trigger_condition="Client cannot or will not pay portion of invoice",
            resolution_steps=["Document collection attempts", "Calculate write-off", "Partner approval", "CEO approval if >$15K"],
            context_objects_relevant=["CTX-009"],  # CEO write-off threshold
        ),
        ExceptionPath(
            id="W5_EX_04",
            name="Billing Rate Dispute",
            description="Client challenges rate based on prior engagement",
            occurrence_rate=0.16,
            trigger_condition="Client references different rate from past",
            resolution_steps=["Pull prior contract", "Compare rates", "Explain difference or adjust"],
            context_objects_relevant=[],
        ),
    ]
)

# W6: New Hire Onboarding (Secondary)
W6_ONBOARDING = Workflow(
    id="W6",
    name="New Hire Onboarding",
    workflow_type=WorkflowType.SECONDARY,
    description="Onboarding new employees and capturing institutional knowledge transfer",
    primary_department="talent_staffing",
    supporting_departments=["knowledge_management"],
    agents_involved=[],
    standard_path=[
        WorkflowStep("W6_01", "First Day Setup", "IT, access, workspace", 1.0, ["hr"]),
        WorkflowStep("W6_02", "Orientation", "Company overview and policies", 2.0, ["hr"]),
        WorkflowStep("W6_03", "Buddy Assignment", "Assign experienced staff mentor", 0.5, ["manager"]),
        WorkflowStep("W6_04", "Knowledge Transfer", "Shadow and learn from team", 10.0, ["consultant"]),
        WorkflowStep("W6_05", "First Assignment", "Begin contributing to engagement", 5.0, ["manager"]),
    ],
    exception_paths=[]
)

# W7: Internal Knowledge Contribution (Secondary)
W7_KNOWLEDGE = Workflow(
    id="W7",
    name="Internal Knowledge Contribution",
    workflow_type=WorkflowType.SECONDARY,
    description="Capturing when and why practitioners document vs hoard knowledge",
    primary_department="knowledge_management",
    supporting_departments=["client_delivery"],
    agents_involved=[],
    standard_path=[
        WorkflowStep("W7_01", "Knowledge Identified", "Valuable insight recognized", 0.5, ["consultant"]),
        WorkflowStep("W7_02", "Documentation Decision", "Decide whether to document", 0.5, ["consultant"]),
        WorkflowStep("W7_03", "Content Creation", "Write up the knowledge", 2.0, ["consultant"]),
        WorkflowStep("W7_04", "Review", "KM team reviews submission", 1.0, ["km"]),
        WorkflowStep("W7_05", "Publication", "Add to knowledge base", 0.5, ["km"]),
    ],
    exception_paths=[]
)

# W8: Leadership Escalation (Secondary)
W8_ESCALATION = Workflow(
    id="W8",
    name="Leadership Escalation",
    workflow_type=WorkflowType.SECONDARY,
    description="Capturing decision traces at the highest organizational level",
    primary_department="executive_leadership",
    supporting_departments=["client_delivery", "business_development", "finance_operations"],
    agents_involved=[],
    standard_path=[
        WorkflowStep("W8_01", "Issue Identified", "Problem requiring executive attention", 0.5, ["manager"]),
        WorkflowStep("W8_02", "Escalation Request", "Formal escalation submitted", 0.5, ["senior_manager"]),
        WorkflowStep("W8_03", "Executive Review", "CEO or partner reviews", 1.0, ["partner", "ceo"]),
        WorkflowStep("W8_04", "Decision", "Executive decision made", 1.0, ["partner", "ceo"]),
        WorkflowStep("W8_05", "Communication", "Decision communicated to stakeholders", 0.5, ["senior_manager"]),
    ],
    exception_paths=[]
)


# All workflows indexed by ID
WORKFLOWS: Dict[str, Workflow] = {
    "W1": W1_CLIENT_ENGAGEMENT,
    "W2": W2_PROPOSAL,
    "W3": W3_STAFFING,
    "W4": W4_VENDOR,
    "W5": W5_BILLING,
    "W6": W6_ONBOARDING,
    "W7": W7_KNOWLEDGE,
    "W8": W8_ESCALATION,
}

# Primary workflows only
PRIMARY_WORKFLOWS = {k: v for k, v in WORKFLOWS.items() if v.workflow_type == WorkflowType.PRIMARY}

# Secondary workflows only
SECONDARY_WORKFLOWS = {k: v for k, v in WORKFLOWS.items() if v.workflow_type == WorkflowType.SECONDARY}


def get_workflow(workflow_id: str) -> Workflow:
    """Get a workflow by its ID."""
    if workflow_id not in WORKFLOWS:
        raise ValueError(f"Unknown workflow: {workflow_id}")
    return WORKFLOWS[workflow_id]


def get_exception_rate(workflow_id: str, exception_id: str) -> float:
    """Get the occurrence rate for a specific exception path."""
    workflow = get_workflow(workflow_id)
    for exc in workflow.exception_paths:
        if exc.id == exception_id:
            return exc.occurrence_rate
    raise ValueError(f"Unknown exception {exception_id} in workflow {workflow_id}")


def get_relevant_context_objects(workflow_id: str, exception_id: str) -> List[str]:
    """Get context object IDs relevant to handling a specific exception."""
    workflow = get_workflow(workflow_id)
    for exc in workflow.exception_paths:
        if exc.id == exception_id:
            return exc.context_objects_relevant
    return []
