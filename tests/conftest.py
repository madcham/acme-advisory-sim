"""
Pytest fixtures for Context Bank simulation tests.

Provides reusable fixtures for:
- Context objects with various configurations
- Context banks (empty and seeded)
- Agent scenarios
- Simulation clocks
- Mock API responses
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from unittest.mock import Mock, patch
import random

from models.context_object import (
    ContextObject, ContentType, SourceType, DecayFunction,
    ContextGrade, OrgLineage, AgentAction, ProvenanceLink,
)
from bank.context_bank import ContextBank
from config.simulation_config import RunCondition, SIMULATION_CONFIG
from generators.agent_exhaust import AgentScenario, AgentDecision, DecisionOutcome


# =============================================================================
# TIME FIXTURES
# =============================================================================

@pytest.fixture
def base_time() -> datetime:
    """Return a fixed base time for reproducible tests."""
    return datetime(2024, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def current_time(base_time: datetime) -> datetime:
    """Return current time (base + 12 weeks)."""
    return base_time + timedelta(weeks=12)


# =============================================================================
# CONTEXT OBJECT FIXTURES
# =============================================================================

@pytest.fixture
def minimal_context(base_time: datetime) -> ContextObject:
    """Return a minimal valid context object."""
    return ContextObject(
        id="CTX-TEST-001",
        created_at=base_time,
        created_by="test_user",
        source_type=SourceType.human,
        week=1,
        content_type=ContentType.observation,
        payload="Test observation content",
        decay_function=DecayFunction.linear,
        confidence_at_creation=0.8,
    )


@pytest.fixture
def vendor_context(base_time: datetime) -> ContextObject:
    """Return a context object about a vendor (like Brightline)."""
    return ContextObject(
        id="CTX-VENDOR-001",
        display_name="Test Vendor: Secondary Approval Required",
        created_at=base_time,
        created_by="david_okafor",
        source_type=SourceType.human,
        workflow_id="W4",
        department="Vendor & Procurement",
        week=0,
        content_type=ContentType.tribal_knowledge,
        payload="Test Vendor overbilled us 30% in 2023. Always get secondary approval.",
        structured_data={
            "vendor_name": "Test Vendor",
            "vendor_id": "test_vendor",
            "risk_level": "high",
            "required_approver": "David Okafor",
        },
        decay_function=DecayFunction.step_function,
        confidence_at_creation=0.9,
        context_grade=ContextGrade.institutional_memory,
        org_lineage=OrgLineage.failure_recovery,
    )


@pytest.fixture
def client_context(base_time: datetime) -> ContextObject:
    """Return a context object about a client."""
    return ContextObject(
        id="CTX-CLIENT-001",
        display_name="Test Client: Extended Payment Cycle",
        created_at=base_time,
        created_by="sarah_chen",
        source_type=SourceType.human,
        workflow_id="W5",
        department="Finance & Billing",
        week=0,
        content_type=ContentType.observation,
        payload="Test Client pays on 60-day cycle regardless of contract terms.",
        structured_data={
            "client_name": "Test Client",
            "client_id": "test_client",
            "payment_cycle_days": 60,
        },
        decay_function=DecayFunction.exponential,
        decay_rate=0.1,
        confidence_at_creation=0.85,
        context_grade=ContextGrade.institutional_memory,
        org_lineage=OrgLineage.direct_observation,
    )


@pytest.fixture
def conflicting_context_pair(base_time: datetime) -> tuple[ContextObject, ContextObject]:
    """Return two context objects that contradict each other."""
    original = ContextObject(
        id="CTX-CONFLICT-001",
        display_name="Policy A: Standard Approval",
        created_at=base_time,
        created_by="policy_team",
        source_type=SourceType.system,
        week=1,
        content_type=ContentType.policy,
        payload="Test Vendor is cleared for standard approval process.",
        structured_data={"vendor_id": "test_vendor", "approval_type": "standard"},
        decay_function=DecayFunction.permanent,
        confidence_at_creation=0.95,
    )

    conflicting = ContextObject(
        id="CTX-CONFLICT-002",
        display_name="Policy B: Secondary Approval Required",
        created_at=base_time + timedelta(weeks=4),
        created_by="compliance_team",
        source_type=SourceType.system,
        week=5,
        content_type=ContentType.policy,
        payload="Test Vendor requires secondary approval from Finance Director.",
        structured_data={"vendor_id": "test_vendor", "approval_type": "secondary"},
        decay_function=DecayFunction.permanent,
        confidence_at_creation=0.95,
    )

    return original, conflicting


@pytest.fixture
def expired_context(base_time: datetime) -> ContextObject:
    """Return a context object that should be expired (low confidence due to age)."""
    return ContextObject(
        id="CTX-EXPIRED-001",
        display_name="Old Process: Deprecated",
        created_at=base_time - timedelta(weeks=52),
        created_by="former_employee",
        source_type=SourceType.human,
        week=-52,  # Created a year ago
        content_type=ContentType.tribal_knowledge,
        payload="This old process is no longer valid.",
        decay_function=DecayFunction.exponential,
        decay_rate=0.2,  # Fast decay
        confidence_at_creation=0.7,
        context_grade=ContextGrade.expired_process,
    )


# =============================================================================
# CONTEXT BANK FIXTURES
# =============================================================================

@pytest.fixture
def empty_bank() -> ContextBank:
    """Return an empty context bank."""
    return ContextBank()


@pytest.fixture
def seeded_bank(vendor_context: ContextObject, client_context: ContextObject) -> ContextBank:
    """Return a context bank with some seeded objects."""
    bank = ContextBank()
    bank.deposit(vendor_context, check_contradictions=False)
    bank.deposit(client_context, check_contradictions=False)
    return bank


@pytest.fixture
def full_bank() -> ContextBank:
    """Return a context bank loaded with all seeded context objects."""
    from config.seeded_context import SEEDED_CONTEXT_OBJECTS
    import copy

    bank = ContextBank()
    for obj in SEEDED_CONTEXT_OBJECTS:
        bank.deposit(copy.deepcopy(obj), check_contradictions=False)
    return bank


# =============================================================================
# SCENARIO FIXTURES
# =============================================================================

@pytest.fixture
def vendor_sow_scenario() -> AgentScenario:
    """Return a vendor SOW approval scenario."""
    return AgentScenario(
        scenario_id="SCEN-TEST-VENDOR",
        scenario_type="vendor_sow",
        workflow_id="W4",
        description="Test scenario for vendor SOW approval.",
        entities={
            "vendor": "test_vendor",
            "vendor_name": "Test Vendor",
            "sow_value": "$100,000",
        },
        ground_truth_context_ids=["CTX-VENDOR-001"],
        correct_action="route through secondary approval",
        incorrect_action="issue SOW directly",
    )


@pytest.fixture
def payment_scenario() -> AgentScenario:
    """Return a payment escalation scenario."""
    return AgentScenario(
        scenario_id="SCEN-TEST-PAYMENT",
        scenario_type="payment_escalation",
        workflow_id="W5",
        description="Test scenario for payment collection.",
        entities={
            "client": "test_client",
            "client_name": "Test Client",
            "days_overdue": "45",
            "amount": "$50,000",
        },
        ground_truth_context_ids=["CTX-CLIENT-001"],
        correct_action="do not escalate until day 65",
        incorrect_action="escalate to collections",
    )


@pytest.fixture
def cross_domain_scenario() -> AgentScenario:
    """Return a scenario requiring cross-domain knowledge."""
    return AgentScenario(
        scenario_id="SCEN-CROSS-DOMAIN",
        scenario_type="cross_domain_decision",
        workflow_id="W3",
        description="Staffing decision that requires vendor knowledge.",
        entities={
            "client": "federal_client",
            "subcontractor": "test_vendor",
            "role": "Project Manager",
        },
        ground_truth_context_ids=["CTX-VENDOR-001"],  # From different department
        correct_action="flag for extra oversight",
        incorrect_action="proceed with standard assignment",
    )


# =============================================================================
# SIMULATION FIXTURES
# =============================================================================

@pytest.fixture
def fixed_seed() -> int:
    """Return a fixed random seed for reproducibility."""
    return 42


@pytest.fixture
def simulation_conditions() -> List[RunCondition]:
    """Return all four experimental conditions."""
    return [
        RunCondition.SILOED_TYPICAL,
        RunCondition.SILOED_ADVANCED,
        RunCondition.GLOBAL_RAG,
        RunCondition.CONTEXT_BANK,
    ]


# =============================================================================
# MOCK FIXTURES
# =============================================================================

@pytest.fixture
def mock_claude_response() -> Dict[str, Any]:
    """Return a mock Claude API response."""
    return {
        "action": "Route through secondary approval",
        "reasoning": "Based on context about vendor history",
        "confidence": 0.85,
        "concerns": ["Historical issues noted"],
        "context_considered": ["CTX-VENDOR-001"],
    }


@pytest.fixture
def mock_anthropic_client(mock_claude_response: Dict[str, Any]):
    """Return a mock Anthropic client."""
    import json

    mock_message = Mock()
    mock_message.content = [Mock(text=json.dumps(mock_claude_response))]
    mock_message.usage = Mock(input_tokens=100, output_tokens=50)

    mock_client = Mock()
    mock_client.messages.create.return_value = mock_message

    return mock_client


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

@pytest.fixture
def create_context_object(base_time: datetime):
    """Factory fixture to create context objects with custom parameters."""
    def _create(
        id: str = None,
        content_type: ContentType = ContentType.observation,
        source_type: SourceType = SourceType.human,
        decay_function: DecayFunction = DecayFunction.linear,
        confidence: float = 0.8,
        week: int = 1,
        payload: str = "Test payload",
        **kwargs
    ) -> ContextObject:
        return ContextObject(
            id=id or f"CTX-TEST-{random.randint(1000, 9999)}",
            created_at=base_time + timedelta(weeks=week),
            created_by="test_user",
            source_type=source_type,
            week=week,
            content_type=content_type,
            payload=payload,
            decay_function=decay_function,
            confidence_at_creation=confidence,
            **kwargs
        )
    return _create
