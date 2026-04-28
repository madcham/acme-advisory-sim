"""
Structured System Exhaust Generator using PM4Py.

Generates OCEL 2.0 format event logs for all five primary workflows.
Each log entry maps to context object attributes for later ingestion.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum
import random
import uuid

from config.workflows import (
    WORKFLOWS, Workflow, WorkflowStep, ExceptionPath,
    get_workflow, get_relevant_context_objects,
)
from config.org_structure import get_all_staff, get_department_staff, StaffMember
from config.simulation_config import (
    SIMULATION_CONFIG, CLIENTS, VENDORS,
    EventsPerWeek, ExceptionInjectionSchedule,
)
from models.context_object import ContentType, OrgLineage


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class EventOutcome(str, Enum):
    """Possible outcomes for workflow events."""
    SUCCESS = "success"
    FAILURE = "failure"
    ESCALATED = "escalated"
    PENDING = "pending"
    EXCEPTION = "exception"


@dataclass
class WorkflowEvent:
    """
    A single event in a workflow execution.

    Maps to OCEL 2.0 event format and context object fields.
    """
    # OCEL 2.0 fields
    event_id: str
    case_id: str  # Maps to workflow_id in ContextObject
    activity: str  # Step name
    timestamp: datetime
    resource: str  # Staff member ID, maps to created_by

    # Extended fields
    workflow_id: str  # W1, W2, etc.
    step_id: str
    outcome: EventOutcome
    duration_hours: float

    # Exception tracking
    is_deviation: bool = False
    exception_id: Optional[str] = None
    exception_type: Optional[str] = None

    # Context object mapping hints
    inferred_content_type: Optional[ContentType] = None
    inferred_org_lineage: Optional[OrgLineage] = None

    # Additional data
    client_id: Optional[str] = None
    vendor_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_ocel_dict(self) -> Dict[str, Any]:
        """Convert to OCEL 2.0 compatible dictionary."""
        return {
            "ocel:eid": self.event_id,
            "ocel:activity": self.activity,
            "ocel:timestamp": self.timestamp.isoformat(),
            "case:concept:name": self.case_id,
            "org:resource": self.resource,
            "workflow:id": self.workflow_id,
            "workflow:step": self.step_id,
            "event:outcome": self.outcome.value,
            "event:duration_hours": self.duration_hours,
            "event:is_deviation": self.is_deviation,
            "event:exception_type": self.exception_type,
            "client:id": self.client_id,
            "vendor:id": self.vendor_id,
        }


@dataclass
class WorkflowCase:
    """A complete case (instance) of a workflow."""
    case_id: str
    workflow_id: str
    events: List[WorkflowEvent]
    client_id: Optional[str] = None
    vendor_id: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    had_exception: bool = False
    exception_ids: List[str] = field(default_factory=list)


class StructuredExhaustGenerator:
    """
    Generates structured event logs for workflow execution.

    Uses PM4Py concepts but implements a custom generator for the simulation.
    Events include realistic timing noise and exception injection.
    """

    def __init__(self, seed: int = 42):
        """Initialize generator with random seed for reproducibility."""
        self.rng = random.Random(seed)
        self.staff = get_all_staff()
        self._event_counter = 0

    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        self._event_counter += 1
        return f"EVT-{self._event_counter:06d}"

    def _generate_case_id(self, workflow_id: str, week: int) -> str:
        """Generate a unique case ID."""
        return f"{workflow_id}-W{week:02d}-{uuid.uuid4().hex[:6].upper()}"

    def _select_resource(self, workflow: Workflow, step: WorkflowStep) -> StaffMember:
        """Select a staff member to perform a workflow step."""
        # Get staff from primary department
        dept_staff = get_department_staff(workflow.primary_department)

        # Filter by required roles if specified
        if step.required_roles:
            # Map role names to actual roles (simplified)
            qualified = [s for s in dept_staff if s.role.value in step.required_roles
                         or any(r in s.role.value for r in step.required_roles)]
            if qualified:
                return self.rng.choice(qualified)

        # Fall back to any department staff
        if dept_staff:
            return self.rng.choice(dept_staff)

        # Last resort: any staff
        return self.rng.choice(self.staff)

    def _add_timing_noise(self, base_hours: float) -> float:
        """Add Gaussian noise to timing."""
        # Standard deviation is 20% of base
        std_dev = base_hours * 0.2
        noisy = self.rng.gauss(base_hours, std_dev)
        return max(0.5, noisy)  # Minimum 30 minutes

    def _should_trigger_exception(
        self,
        exception: ExceptionPath,
        week: int,
        injection_schedule: ExceptionInjectionSchedule,
    ) -> bool:
        """Determine if an exception should trigger."""
        # Check if this is a scheduled injection week
        injections = injection_schedule.get_injections_for_week(week)

        # Map exception IDs to injection types
        exception_mapping = {
            "W4_EX_02": "brightline_sow",  # Historical pricing dispute
            "W1_EX_01": "financial_services_scope",  # Scope expansion
            "W2_EX_03": "hartwell_override",  # Partner override
            "W5_EX_02": "terralogic_payment",  # Payment delayed
            "W3_EX_03": "jordan_park_conflict",  # Staff refusal
        }

        injection_type = exception_mapping.get(exception.id)
        if injection_type and injection_type in injections:
            return True

        # Otherwise, use probability
        return self.rng.random() < exception.occurrence_rate

    def generate_workflow_case(
        self,
        workflow_id: str,
        week: int,
        base_timestamp: datetime,
        client_id: Optional[str] = None,
        vendor_id: Optional[str] = None,
        force_exception: Optional[str] = None,
    ) -> WorkflowCase:
        """
        Generate a complete workflow case with events.

        Args:
            workflow_id: Which workflow (W1-W5)
            week: Simulation week number
            base_timestamp: Starting timestamp for the case
            client_id: Optional client involved
            vendor_id: Optional vendor involved
            force_exception: Force a specific exception ID

        Returns:
            WorkflowCase with all events
        """
        workflow = get_workflow(workflow_id)
        case_id = self._generate_case_id(workflow_id, week)
        events = []
        current_time = base_timestamp
        exception_triggered = None

        # Determine if exception should occur
        if force_exception:
            for exc in workflow.exception_paths:
                if exc.id == force_exception:
                    exception_triggered = exc
                    break
        else:
            for exc in workflow.exception_paths:
                if self._should_trigger_exception(
                    exc, week, SIMULATION_CONFIG.exception_injection
                ):
                    exception_triggered = exc
                    break

        # Generate events for each step
        for i, step in enumerate(workflow.standard_path):
            resource = self._select_resource(workflow, step)
            duration = self._add_timing_noise(step.typical_duration_days * 24)

            # Check if this step triggers the exception
            is_exception_step = (
                exception_triggered
                and i >= len(workflow.standard_path) // 3  # Exception in middle third
                and not any(e.is_deviation for e in events)  # Not already triggered
            )

            outcome = EventOutcome.SUCCESS
            is_deviation = False
            exc_id = None
            exc_type = None
            inferred_content_type = None
            inferred_org_lineage = None

            if is_exception_step:
                is_deviation = True
                exc_id = exception_triggered.id
                exc_type = exception_triggered.name
                outcome = EventOutcome.EXCEPTION

                # Infer content type and lineage from exception
                inferred_content_type = ContentType.exception
                if "pricing" in exception_triggered.name.lower():
                    inferred_org_lineage = OrgLineage.failure_recovery
                elif "override" in exception_triggered.name.lower():
                    inferred_org_lineage = OrgLineage.political_settlement
                else:
                    inferred_org_lineage = OrgLineage.exception_handling

            event = WorkflowEvent(
                event_id=self._generate_event_id(),
                case_id=case_id,
                activity=step.name,
                timestamp=current_time,
                resource=resource.id,
                workflow_id=workflow_id,
                step_id=step.id,
                outcome=outcome,
                duration_hours=duration,
                is_deviation=is_deviation,
                exception_id=exc_id,
                exception_type=exc_type,
                inferred_content_type=inferred_content_type,
                inferred_org_lineage=inferred_org_lineage,
                client_id=client_id,
                vendor_id=vendor_id,
                metadata={
                    "week": week,
                    "staff_tenure": resource.tenure_years,
                    "staff_department": resource.department,
                },
            )
            events.append(event)

            # Advance time
            current_time += timedelta(hours=duration)

        return WorkflowCase(
            case_id=case_id,
            workflow_id=workflow_id,
            events=events,
            client_id=client_id,
            vendor_id=vendor_id,
            started_at=events[0].timestamp if events else None,
            completed_at=events[-1].timestamp if events else None,
            had_exception=exception_triggered is not None,
            exception_ids=[exception_triggered.id] if exception_triggered else [],
        )

    def generate_weekly_events(
        self,
        week: int,
        base_timestamp: Optional[datetime] = None,
    ) -> Tuple[List[WorkflowCase], List[WorkflowEvent]]:
        """
        Generate all workflow events for a week.

        Returns:
            Tuple of (list of cases, flat list of all events)
        """
        if base_timestamp is None:
            # Start of the simulation week
            base_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(weeks=week)

        events_config = SIMULATION_CONFIG.events_per_week
        injection_schedule = SIMULATION_CONFIG.exception_injection
        cases = []
        all_events = []

        # Get injections for this week
        week_injections = injection_schedule.get_injections_for_week(week)

        # W1: Client Engagements
        clients_list = list(CLIENTS.keys())
        for i in range(events_config.W1_engagements):
            client = self.rng.choice(clients_list)
            offset = timedelta(hours=self.rng.randint(0, 40))

            # Check for financial services scope injection
            force_exc = None
            if "financial_services_scope" in week_injections and i == 0:
                # Force scope expansion on first FS client engagement
                if CLIENTS[client].get("vertical") == "financial_services":
                    force_exc = "W1_EX_01"

            case = self.generate_workflow_case(
                "W1", week, base_timestamp + offset,
                client_id=client, force_exception=force_exc
            )
            cases.append(case)
            all_events.extend(case.events)

        # W2: Proposals
        for i in range(events_config.W2_proposals):
            client = self.rng.choice(clients_list)
            offset = timedelta(hours=self.rng.randint(0, 40))

            # Check for Hartwell override injection
            force_exc = None
            if "hartwell_override" in week_injections and client == "hartwell_group":
                force_exc = "W2_EX_03"

            case = self.generate_workflow_case(
                "W2", week, base_timestamp + offset,
                client_id=client, force_exception=force_exc
            )
            cases.append(case)
            all_events.extend(case.events)

        # W3: Staffing
        for i in range(events_config.W3_staffing_requests):
            client = self.rng.choice(clients_list)
            offset = timedelta(hours=self.rng.randint(0, 40))

            # Check for Jordan Park conflict injection
            force_exc = None
            if "jordan_park_conflict" in week_injections and client == "nexum_partners" and i == 0:
                force_exc = "W3_EX_03"

            case = self.generate_workflow_case(
                "W3", week, base_timestamp + offset,
                client_id=client, force_exception=force_exc
            )
            cases.append(case)
            all_events.extend(case.events)

        # W4: Vendor Management - THE KEY WORKFLOW FOR BRIGHTLINE
        vendors_list = list(VENDORS.keys())
        for i in range(events_config.W4_vendor_events):
            vendor = self.rng.choice(vendors_list)
            offset = timedelta(hours=self.rng.randint(0, 40))

            # Check for Brightline SOW injection
            force_exc = None
            if "brightline_sow" in week_injections and vendor == "brightline_consulting":
                force_exc = "W4_EX_02"
            elif "brightline_sow" in week_injections and i == 0:
                # Force first vendor event to be Brightline if it's an injection week
                vendor = "brightline_consulting"
                force_exc = "W4_EX_02"

            case = self.generate_workflow_case(
                "W4", week, base_timestamp + offset,
                vendor_id=vendor, force_exception=force_exc
            )
            cases.append(case)
            all_events.extend(case.events)

        # W5: Billing
        for i in range(events_config.W5_billing_events):
            client = self.rng.choice(clients_list)
            offset = timedelta(hours=self.rng.randint(0, 40))

            # Check for TerraLogic payment injection
            force_exc = None
            if "terralogic_payment" in week_injections and client == "terralogic":
                force_exc = "W5_EX_02"
            elif "terralogic_payment" in week_injections and i == 0:
                # Force first billing event to be TerraLogic if it's an injection week
                client = "terralogic"
                force_exc = "W5_EX_02"

            case = self.generate_workflow_case(
                "W5", week, base_timestamp + offset,
                client_id=client, force_exception=force_exc
            )
            cases.append(case)
            all_events.extend(case.events)

        return cases, all_events


def generate_weekly_events(
    week: int,
    seed: Optional[int] = None,
) -> Tuple[List[WorkflowCase], List[WorkflowEvent]]:
    """
    Convenience function to generate weekly events.

    Args:
        week: Simulation week number (1-12)
        seed: Optional random seed (defaults to config seed + week)

    Returns:
        Tuple of (cases, events)
    """
    if seed is None:
        seed = SIMULATION_CONFIG.random_seed + week

    generator = StructuredExhaustGenerator(seed=seed)
    return generator.generate_weekly_events(week)


def events_to_ocel(events: List[WorkflowEvent]) -> Dict[str, Any]:
    """Convert events to OCEL 2.0 format."""
    return {
        "ocel:global-event": {
            "ocel:activity": "__INVALID__"
        },
        "ocel:global-object": {
            "ocel:type": "__INVALID__"
        },
        "ocel:global-log": {
            "ocel:attribute-names": [
                "workflow:id", "workflow:step", "event:outcome",
                "event:duration_hours", "event:is_deviation",
                "event:exception_type", "client:id", "vendor:id"
            ],
            "ocel:version": "1.0",
            "ocel:ordering": "timestamp"
        },
        "ocel:events": [e.to_ocel_dict() for e in events],
    }
