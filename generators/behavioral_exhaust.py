"""
Behavioral Exhaust Generator (Enhanced v2.0).

Models behavioral exhaust as CONVERSATIONAL EXCHANGES, not isolated messages.
Every knowledge-seeking message from a short-tenure employee triggers a
knowledge-sharing response from a long-tenure employee. The ANSWER is what
becomes the context object, not the question.

Simulates the between-systems work that never lands in structured logs.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum
import random
import uuid

from config.org_structure import (
    get_all_staff, get_department_staff, get_staff_by_tenure, StaffMember,
    Role, TenureBand, KEY_INDIVIDUALS,
)
from config.simulation_config import SIMULATION_CONFIG


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class BehaviorType(str, Enum):
    """Categories of behavioral exhaust."""
    COMMUNICATION = "communication"
    DATA_TRANSFER = "data_transfer"
    DECISION_MAKING = "decision_making"
    WORKAROUND = "workaround"
    KNOWLEDGE_SHARING = "knowledge_sharing"
    PROCESS_BYPASS = "process_bypass"
    KNOWLEDGE_EXCHANGE = "knowledge_exchange"


class ApplicationType(str, Enum):
    """Applications involved in behavioral patterns."""
    EMAIL = "email"
    SLACK = "slack"
    CRM = "crm"
    SPREADSHEET = "spreadsheet"
    PSA_TOOL = "psa_tool"
    KNOWLEDGE_BASE = "knowledge_base"
    CALENDAR = "calendar"
    PHONE = "phone"
    VIDEO_CALL = "video_call"
    TEAMS = "teams"


class AnswerSpecificity(str, Enum):
    """How specific/actionable is the answer."""
    HIGH = "high"      # Named specific people, dates, amounts
    MEDIUM = "medium"  # General pattern without specifics
    LOW = "low"        # Vague recollection


@dataclass
class BehavioralExchange:
    """
    A knowledge exchange between employees.

    Models the question-answer pattern where short-tenure employees ask
    and long-tenure employees share institutional knowledge. The ANSWER
    is what becomes the context object payload.
    """
    exchange_id: str
    timestamp: datetime
    week: int
    application: ApplicationType

    # Initiator (typically short-tenure, asking the question)
    initiator_id: str
    initiator_name: str
    initiator_tenure_years: float
    question: str

    # Responder (typically long-tenure, providing the answer)
    responder_id: str
    responder_name: str
    responder_tenure_years: float
    answer: str

    # Knowledge classification
    knowledge_category: str
    answer_specificity: AnswerSpecificity
    confidence: float

    # Entities mentioned (for context object extraction)
    entities: Dict[str, str] = field(default_factory=dict)

    # Inferred context grade and lineage
    inferred_grade: Optional[str] = None
    inferred_grade_confidence: float = 0.0
    inferred_lineage: Optional[str] = None
    inferred_lineage_confidence: float = 0.0


@dataclass
class BehavioralEvent:
    """
    A single behavioral exhaust event.

    Captures informal work patterns that signal institutional knowledge.
    """
    event_id: str
    timestamp: datetime
    staff_id: str
    staff_name: str
    staff_tenure_years: float
    staff_role: str
    staff_department: str

    # Behavior details
    behavior_type: BehaviorType
    application: ApplicationType
    action: str
    description: str

    # Context signals
    involves_decision: bool = False
    involves_knowledge_transfer: bool = False
    is_process_bypass: bool = False
    is_workaround: bool = False

    # Knowledge signal strength (weighted by tenure)
    knowledge_signal_weight: float = 0.0

    # Related entities
    related_client: Optional[str] = None
    related_vendor: Optional[str] = None
    related_staff: List[str] = field(default_factory=list)

    # Raw content (for potential context extraction)
    raw_content: Optional[str] = None

    # Associated exchange (if this event came from an exchange)
    exchange: Optional[BehavioralExchange] = None

    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# GROUND TRUTH ALIGNED ANSWER TEMPLATES
# These templates reinforce the seeded context objects (CTX-001 through CTX-012)
# ============================================================================

GROUND_TRUTH_ANSWERS = {
    # CTX-001: Brightline secondary approval
    "brightline_approval": {
        "category": "vendor_pricing",
        "entities": {"vendor": "brightline_consulting", "approver": "david_okafor"},
        "specificity": AnswerSpecificity.HIGH,
        "templates": [
            "{responder}: For Brightline, always loop in David Okafor before you commit to anything. "
            "We got burned in 2022 when they billed 40% over the agreed rate on a federal engagement. "
            "David knows the full history and has to sign off on every SOW now.",

            "{responder}: Brightline Consulting requires secondary approval from David Okafor before "
            "any SOW issuance. This isn't in the system but it's mandatory. The 2022 invoice dispute "
            "was brutal - they overbilled us 40% and it took months to resolve.",

            "{responder}: Heads up on Brightline - never issue a SOW without David Okafor reviewing it first. "
            "There's a documented pricing dispute from 2022 where they charged 40% above the agreed rate. "
            "Finance put in the secondary approval requirement after that.",
        ],
    },

    # CTX-002: Financial services scope creep
    "fs_scope_documentation": {
        "category": "client_behavior",
        "entities": {"client_vertical": "financial_services"},
        "specificity": AnswerSpecificity.HIGH,
        "templates": [
            "{responder}: Financial services clients always expand scope verbally around week 3-4. "
            "Document everything they ask for within 24 hours or you will lose that billing argument. "
            "I learned this the hard way on three separate engagements.",

            "{responder}: With FS clients, scope creep hits like clockwork in week 3 or 4. They'll ask for "
            "'just one more analysis' verbally. Get it in writing within 24 hours. If you don't, the billing "
            "dispute is unwinnable. Trust me on this one.",

            "{responder}: Rule of thumb for financial services engagements - any verbal scope expansion, "
            "document it same day, 24 hours max. They always ask for more around week 3-4 and if you don't "
            "have it documented, you're eating that work.",
        ],
    },

    # CTX-003: Marcus Webb Hartwell override
    "hartwell_override": {
        "category": "approval_process",
        "entities": {"partner": "marcus_webb", "client": "hartwell_group"},
        "specificity": AnswerSpecificity.HIGH,
        "templates": [
            "{responder}: The policy says one thing but Marcus Webb makes the actual call on Hartwell Group. "
            "Run it by him first before going through the formal go/no-go process. He'll override anyway "
            "if it's Hartwell - historical relationship trumps margin analysis.",

            "{responder}: Hartwell Group is Marcus Webb's account, full stop. Standard margin thresholds "
            "don't apply. If Marcus wants it, we pursue it regardless of what the numbers say. "
            "Don't waste time on the formal approval - just get his blessing first.",

            "{responder}: For any Hartwell opportunity, Marcus Webb will override the go/no-go regardless "
            "of margin. It's a relationship thing going back years. The 25% threshold? Doesn't apply to them.",
        ],
    },

    # CTX-004: Priya Nair 72-hour notice
    "priya_notice": {
        "category": "approval_process",
        "entities": {"stakeholder": "priya_nair"},
        "specificity": AnswerSpecificity.HIGH,
        "templates": [
            "{responder}: Priya Nair needs 72 hours notice on senior resource reallocation. "
            "The system won't stop you from reassigning people same-day, but the morale fallout "
            "lasts two weeks. She's documented this requirement but it's not automated.",

            "{responder}: Never move a senior resource without giving Priya at least 72 hours heads up. "
            "I know it's not enforced by the system but the consequences are real - two weeks of "
            "team friction and she'll remember it at review time.",

            "{responder}: The 72-hour rule for Priya on staffing changes is real. Violate it once and "
            "you'll see the morale impact ripple through for two weeks. Not worth it.",
        ],
    },

    # CTX-005: Vance Analytics pricing negotiation
    "vance_pricing": {
        "category": "vendor_pricing",
        "entities": {"vendor": "vance_analytics"},
        "specificity": AnswerSpecificity.HIGH,
        "templates": [
            "{responder}: Vance Analytics has a standard rate but there's room to negotiate on big engagements. "
            "For anything over $500K, you can get 15% below list. Don't put the discount in the initial SOW "
            "draft though - wait for them to push back first.",

            "{responder}: With Vance, the list rate isn't the real rate. On $500K+ engagements, "
            "15% discount is on the table but you have to negotiate for it. Key thing: don't reveal "
            "you know this in the initial conversation.",

            "{responder}: Vance Analytics pricing is negotiable up to 15% below list when the engagement "
            "is over $500K. But keep that card close - don't disclose it in the initial SOW.",
        ],
    },

    # CTX-006: TerraLogic payment cycle
    "terralogic_payment": {
        "category": "client_behavior",
        "entities": {"client": "terralogic"},
        "specificity": AnswerSpecificity.HIGH,
        "templates": [
            "{responder}: TerraLogic pays on 60 days regardless of what the contract says. "
            "Don't escalate before day 65 - we lost the account once by escalating at 45 days. "
            "Their finance team just operates on a different cycle.",

            "{responder}: For TerraLogic collections, the contract says 30 days but they actually pay "
            "at 60. Premature escalation caused an account loss in 2023. Wait until day 65 minimum "
            "before even mentioning it.",

            "{responder}: TerraLogic is a 60-day payer, period. I know the contract says different "
            "but that's how they operate. We lost them once by pushing too early. Day 65 is the "
            "earliest you should even think about escalation.",
        ],
    },

    # CTX-007: COI manual check
    "coi_manual_check": {
        "category": "conflict_flags",
        "entities": {},
        "specificity": AnswerSpecificity.MEDIUM,
        "templates": [
            "{responder}: The system doesn't flag conflict of interest for former staff at clients. "
            "If any of our former people now work at the client company, you need to do a manual "
            "COI check. The automated screening misses this completely.",

            "{responder}: Former Acme staff at client companies = manual COI check required. "
            "The system doesn't catch this automatically. I've seen it burn people who assumed "
            "the automated screening was comprehensive.",

            "{responder}: Conflict of interest check is required when former Acme staff are at the client. "
            "System does not flag this automatically - manual check required every time.",
        ],
    },

    # CTX-008: Elena Vasquez FS methodology
    "elena_methodology": {
        "category": "approval_process",
        "entities": {"stakeholder": "elena_vasquez"},
        "specificity": AnswerSpecificity.HIGH,
        "templates": [
            "{responder}: Elena Vasquez holds the master methodology for financial services engagements. "
            "It's not in the knowledge base - you have to consult her directly for FS projects. "
            "Don't waste time searching, just schedule 30 minutes with her.",

            "{responder}: For FS methodology, go straight to Elena Vasquez. The knowledge base has "
            "outdated stuff. She's the source of truth and she actually prefers being asked directly.",

            "{responder}: The FS methodology isn't documented anywhere useful. Elena Vasquez is the holder. "
            "Must be consulted directly for any financial services project. Nobody documents this.",
        ],
    },

    # CTX-009: CEO write-off threshold
    "ceo_writeoff": {
        "category": "exception_handling",
        "entities": {"stakeholder": "james_holloway"},
        "specificity": AnswerSpecificity.HIGH,
        "templates": [
            "{responder}: Write-offs above $15K need CEO sign-off now. James Holloway updated this "
            "verbally in Q3 but it's not in the policy docs yet. The approval matrix shows partner "
            "level but that's outdated.",

            "{responder}: The write-off threshold changed - anything over $15K goes to James Holloway "
            "regardless of what the approval matrix says. This was a verbal update from Q3 2024. "
            "Not documented anywhere official.",

            "{responder}: CEO approval required for write-offs above $15K. James Holloway changed this "
            "verbally last year. The policy docs still show the old threshold - ignore them.",
        ],
    },

    # CTX-010: Jordan Park Nexum conflict
    "jordan_nexum_conflict": {
        "category": "conflict_flags",
        "entities": {"staff_member": "jordan_park", "client": "nexum_partners", "hr_contact": "priya_nair"},
        "specificity": AnswerSpecificity.HIGH,
        "templates": [
            "{responder}: Do not put Jordan Park on any Nexum Partners work. There's a documented "
            "HR situation. The staffing system won't flag it but it's real. Check with Priya Nair "
            "if you need details but the short answer is just don't assign them.",

            "{responder}: Jordan Park and Nexum Partners - documented conflict in HR records. "
            "The system doesn't flag this automatically. Hard no on any assignment there.",

            "{responder}: Jordan Park has a documented conflict with Nexum Partners. "
            "HR record exists but the system does not flag it. Do not assign to any Nexum work.",
        ],
    },

    # CTX-011: Friday submissions (expired process - low confidence)
    "friday_submissions": {
        "category": "exception_handling",
        "entities": {},
        "specificity": AnswerSpecificity.LOW,
        "templates": [
            "{responder}: There used to be a thing about not submitting proposals on Fridays - "
            "supposedly lower win rates. I'm not sure if that's still true or if it ever was. "
            "Some people still follow it but I wouldn't worry about it.",

            "{responder}: The Friday proposal thing? That's old data. Three years ago maybe it mattered. "
            "I wouldn't base decisions on it now. Most people don't know it changed.",
        ],
    },

    # CTX-012: 50-page review (expired process - low confidence)
    "page_review_old": {
        "category": "exception_handling",
        "entities": {},
        "specificity": AnswerSpecificity.LOW,
        "templates": [
            "{responder}: The old rule about senior partner review for deliverables over 50 pages - "
            "that only applies to regulatory submissions now. Changed in 2023 but many staff still "
            "follow the old rule unnecessarily. Don't waste time with it unless it's regulatory.",

            "{responder}: Senior partner review over 50 pages was policy until 2023. Now it's only "
            "for regulatory submissions. A lot of people don't know this changed though.",
        ],
    },
}

# Generic answer templates for random knowledge (not ground truth aligned)
GENERIC_ANSWERS = {
    "vendor_general": {
        "category": "vendor_pricing",
        "specificity": AnswerSpecificity.MEDIUM,
        "templates": [
            "{responder}: For {vendor}, always get Finance to review the rates before signing. "
            "There's often room to negotiate if you know the history.",

            "{responder}: {vendor} has been reliable but watch the invoicing carefully. "
            "Cross-check everything against the SOW.",
        ],
    },
    "client_general": {
        "category": "client_behavior",
        "specificity": AnswerSpecificity.MEDIUM,
        "templates": [
            "{responder}: {client} tends to push on timelines. Build in buffer and document "
            "any scope changes immediately.",

            "{responder}: The relationship with {client} is good but they're demanding. "
            "Make sure the engagement manager sets expectations early.",
        ],
    },
    "process_general": {
        "category": "approval_process",
        "specificity": AnswerSpecificity.MEDIUM,
        "templates": [
            "{responder}: The formal process says one thing but in practice, check with "
            "{stakeholder} first. They usually have context the system doesn't capture.",

            "{responder}: For {topic}, the documented process is a starting point. "
            "Talk to someone who's done it before - there are always undocumented steps.",
        ],
    },
}

# Question templates (what short-tenure employees ask)
QUESTION_TEMPLATES = [
    "Hey, do you remember how we handled the {entity} situation?",
    "Quick question - what's the approval process for {entity} again?",
    "Who should I talk to about {topic}? I know there's history here.",
    "Is there anything special I should know about {entity}?",
    "What's the deal with {entity}? I heard there's background.",
    "Before I proceed with {entity}, anything I should be aware of?",
]


def compute_behavioral_confidence(
    responder_tenure_years: float,
    answer_specificity: AnswerSpecificity,
) -> float:
    """
    Calculate confidence score based on responder tenure and answer specificity.

    Long-tenure employees with specific answers produce high-confidence context objects.
    Short-tenure employees asking questions produce low-confidence signals only.
    """
    # Base confidence from tenure (0.5 to 0.9 range)
    base = min(0.9, 0.5 + (responder_tenure_years * 0.06))

    # Specificity multiplier
    specificity_multipliers = {
        AnswerSpecificity.HIGH: 1.0,    # Named specific people, dates, amounts
        AnswerSpecificity.MEDIUM: 0.85,  # General pattern without specifics
        AnswerSpecificity.LOW: 0.65,     # Vague recollection
    }

    multiplier = specificity_multipliers.get(answer_specificity, 0.85)
    return round(base * multiplier, 2)


def infer_context_grade_from_behavioral(
    payload: str,
    structured_data: dict,
) -> Tuple[str, float]:
    """
    Infer context_grade from behavioral exhaust content.
    Returns (grade, confidence) tuple.
    """
    payload_lower = payload.lower()

    # Strong signals for institutional memory
    institutional_signals = [
        "learned this the hard way", "we got burned", "history here",
        "lost the account", "the hard way", "nobody documents",
        "not in the policy", "verbally", "remember how we handled",
        "trust me on this", "i've seen it", "years ago",
        "historical relationship", "documented dispute", "overbilled",
    ]

    # Strong signals for compliance scaffolding
    compliance_signals = [
        "required", "always loop in", "need approval", "manual check",
        "documented", "system won't", "hr situation", "policy says",
        "sign off", "mandatory", "must be consulted", "coi check",
    ]

    # Strong signals for expired process
    expired_signals = [
        "old rule", "used to", "changed", "doesn't apply anymore",
        "most people don't know", "no longer", "was policy until",
        "outdated", "that's old", "changed in 2023", "not sure if",
    ]

    institutional_score = sum(1 for s in institutional_signals if s in payload_lower)
    compliance_score = sum(1 for s in compliance_signals if s in payload_lower)
    expired_score = sum(1 for s in expired_signals if s in payload_lower)

    scores = {
        "institutional_memory": institutional_score,
        "compliance_scaffolding": compliance_score,
        "expired_process": expired_score,
    }

    top_grade = max(scores, key=scores.get)
    top_score = scores[top_grade]

    if top_score == 0:
        return "institutional_memory", 0.45  # default with low confidence

    grade_confidence = min(0.9, 0.5 + (top_score * 0.12))
    return top_grade, round(grade_confidence, 2)


def infer_org_lineage_from_behavioral(
    payload: str,
    structured_data: dict,
) -> Tuple[str, float]:
    """
    Infer org_lineage from behavioral exhaust content.
    Returns (lineage, confidence) tuple.
    """
    payload_lower = payload.lower()

    lineage_signals = {
        "failure_recovery": [
            "burned", "lost the account", "dispute", "hard way",
            "overbilled", "billing dispute", "incident", "went wrong",
        ],
        "political_settlement": [
            "relationship", "regardless of", "override", "his call",
            "trumps", "doesn't apply to them", "verbally", "informal",
        ],
        "documented_policy": [
            "policy", "documented", "official", "required",
            "mandatory", "hr record", "signed off",
        ],
        "direct_observation": [
            "i've seen", "noticed", "tends to", "usually",
            "pattern", "three times", "every time", "clockwork",
        ],
        "exception_handling": [
            "special case", "edge case", "exception", "workaround",
        ],
    }

    scores = {}
    for lineage, signals in lineage_signals.items():
        scores[lineage] = sum(1 for s in signals if s in payload_lower)

    top_lineage = max(scores, key=scores.get)
    top_score = scores[top_lineage]

    if top_score == 0:
        return "direct_observation", 0.45

    lineage_confidence = min(0.9, 0.5 + (top_score * 0.15))
    return top_lineage, round(lineage_confidence, 2)


class BehavioralExhaustGenerator:
    """
    Generates behavioral exhaust as conversational exchanges.

    Models knowledge transfer between short-tenure and long-tenure employees.
    The ANSWER from the long-tenure employee becomes the context object payload.
    """

    def __init__(self, seed: int = 42):
        """Initialize generator with random seed."""
        self.rng = random.Random(seed)
        self.staff = get_all_staff()
        self._event_counter = 0
        self._exchange_counter = 0

        # Separate staff by tenure for exchange matching
        self.short_tenure = [s for s in self.staff
                            if s.tenure_band in (TenureBand.UNDER_1_YEAR, TenureBand.ONE_TO_THREE)]
        self.long_tenure = [s for s in self.staff
                           if s.tenure_band in (TenureBand.THREE_TO_SEVEN, TenureBand.OVER_7_YEARS)]

        # Fallback lists for variety
        self.clients = ["hartwell_group", "terralogic", "nexum_partners", "meridian_financial", "apex_manufacturing"]
        self.vendors = ["brightline_consulting", "vance_analytics", "summit_research"]
        self.stakeholders = ["david_okafor", "priya_nair", "elena_vasquez", "marcus_webb", "sarah_chen"]
        self.topics = ["pricing", "staffing", "scope", "billing", "approval", "timeline"]

    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        self._event_counter += 1
        return f"BEV-{self._event_counter:06d}"

    def _generate_exchange_id(self) -> str:
        """Generate unique exchange ID."""
        self._exchange_counter += 1
        return f"BEX-{self._exchange_counter:06d}"

    def _select_ground_truth_template(self) -> Tuple[str, Dict]:
        """
        Select a ground truth-aligned answer template.
        Weighted to favor high-value institutional memory.
        """
        # Weight ground truth templates - high confidence ones more likely
        weighted_keys = []
        for key, data in GROUND_TRUTH_ANSWERS.items():
            if data["specificity"] == AnswerSpecificity.HIGH:
                weighted_keys.extend([key] * 3)  # 3x weight for high specificity
            elif data["specificity"] == AnswerSpecificity.MEDIUM:
                weighted_keys.extend([key] * 2)
            else:
                weighted_keys.append(key)

        selected_key = self.rng.choice(weighted_keys)
        return selected_key, GROUND_TRUTH_ANSWERS[selected_key]

    def _generate_exchange(
        self,
        week: int,
        base_timestamp: datetime,
        force_ground_truth: bool = False,
    ) -> Optional[BehavioralExchange]:
        """
        Generate a knowledge exchange between employees.

        A short-tenure employee asks a question, a long-tenure employee answers.
        """
        if not self.short_tenure or not self.long_tenure:
            return None

        # Select participants
        initiator = self.rng.choice(self.short_tenure)
        responder = self.rng.choice(self.long_tenure)

        # Decide whether to use ground truth or generic template
        # 60% chance of ground truth template to reinforce seeded knowledge
        use_ground_truth = force_ground_truth or self.rng.random() < 0.6

        if use_ground_truth:
            template_key, template_data = self._select_ground_truth_template()
            answer_templates = template_data["templates"]
            category = template_data["category"]
            entities = template_data["entities"].copy()
            specificity = template_data["specificity"]
        else:
            # Use generic template
            generic_key = self.rng.choice(list(GENERIC_ANSWERS.keys()))
            template_data = GENERIC_ANSWERS[generic_key]
            answer_templates = template_data["templates"]
            category = template_data["category"]
            specificity = template_data["specificity"]
            entities = {
                "vendor": self.rng.choice(self.vendors),
                "client": self.rng.choice(self.clients),
                "stakeholder": self.rng.choice(self.stakeholders),
                "topic": self.rng.choice(self.topics),
            }

        # Generate answer from responder
        answer_template = self.rng.choice(answer_templates)
        answer = answer_template.format(responder=responder.name, **entities)

        # Generate question from initiator
        entity_mention = entities.get("vendor") or entities.get("client") or entities.get("stakeholder", "this")
        question_template = self.rng.choice(QUESTION_TEMPLATES)
        question = question_template.format(entity=entity_mention, topic=self.rng.choice(self.topics))

        # Calculate confidence
        confidence = compute_behavioral_confidence(responder.tenure_years, specificity)

        # Infer context grade and lineage
        inferred_grade, grade_conf = infer_context_grade_from_behavioral(answer, entities)
        inferred_lineage, lineage_conf = infer_org_lineage_from_behavioral(answer, entities)

        # Timestamp
        hour_offset = self.rng.uniform(9, 17)
        day_offset = self.rng.randint(0, 4)
        timestamp = base_timestamp + timedelta(days=day_offset, hours=hour_offset)

        return BehavioralExchange(
            exchange_id=self._generate_exchange_id(),
            timestamp=timestamp,
            week=week,
            application=self.rng.choice([ApplicationType.SLACK, ApplicationType.TEAMS, ApplicationType.EMAIL]),
            initiator_id=initiator.id,
            initiator_name=initiator.name,
            initiator_tenure_years=initiator.tenure_years,
            question=question,
            responder_id=responder.id,
            responder_name=responder.name,
            responder_tenure_years=responder.tenure_years,
            answer=answer,
            knowledge_category=category,
            answer_specificity=specificity,
            confidence=confidence,
            entities=entities,
            inferred_grade=inferred_grade,
            inferred_grade_confidence=grade_conf,
            inferred_lineage=inferred_lineage,
            inferred_lineage_confidence=lineage_conf,
        )

    def _exchange_to_event(self, exchange: BehavioralExchange) -> BehavioralEvent:
        """Convert a BehavioralExchange to a BehavioralEvent for compatibility."""
        return BehavioralEvent(
            event_id=self._generate_event_id(),
            timestamp=exchange.timestamp,
            staff_id=exchange.responder_id,  # Responder is the knowledge source
            staff_name=exchange.responder_name,
            staff_tenure_years=exchange.responder_tenure_years,
            staff_role="knowledge_sharer",
            staff_department="",
            behavior_type=BehaviorType.KNOWLEDGE_EXCHANGE,
            application=exchange.application,
            action="knowledge_exchange",
            description=f"Knowledge exchange: {exchange.initiator_name} asked, {exchange.responder_name} answered",
            involves_decision=False,
            involves_knowledge_transfer=True,
            is_process_bypass=False,
            is_workaround=False,
            knowledge_signal_weight=exchange.confidence,
            raw_content=exchange.answer,  # THE ANSWER is the content, not the question
            exchange=exchange,
            metadata={
                "week": exchange.week,
                "question": exchange.question,
                "knowledge_category": exchange.knowledge_category,
                "entities": exchange.entities,
                "answer_specificity": exchange.answer_specificity.value,
                "inferred_grade": exchange.inferred_grade,
                "inferred_grade_confidence": exchange.inferred_grade_confidence,
                "inferred_lineage": exchange.inferred_lineage,
                "inferred_lineage_confidence": exchange.inferred_lineage_confidence,
            },
        )

    def generate_weekly_exchanges(
        self,
        week: int,
        base_timestamp: Optional[datetime] = None,
        num_exchanges: int = 15,
    ) -> List[BehavioralExchange]:
        """Generate knowledge exchanges for a week."""
        if base_timestamp is None:
            base_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(weeks=week)

        exchanges = []

        # First few exchanges should be ground truth aligned
        num_ground_truth = min(num_exchanges // 2, 8)

        for i in range(num_exchanges):
            force_ground_truth = i < num_ground_truth
            exchange = self._generate_exchange(week, base_timestamp, force_ground_truth)
            if exchange:
                exchanges.append(exchange)

        return exchanges

    def generate_weekly_events(
        self,
        week: int,
        base_timestamp: Optional[datetime] = None,
        total_events: int = 150,
    ) -> List[BehavioralEvent]:
        """
        Generate all behavioral events for a week.

        Includes both exchange-based events (with substantive answers)
        and standard behavioral events.
        """
        if base_timestamp is None:
            base_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(weeks=week)

        events = []

        # Generate knowledge exchanges (these become high-value context objects)
        num_exchanges = min(20, total_events // 5)  # ~20% of events are exchanges
        exchanges = self.generate_weekly_exchanges(week, base_timestamp, num_exchanges)

        for exchange in exchanges:
            events.append(self._exchange_to_event(exchange))

        # Fill remaining with standard behavioral events
        remaining = total_events - len(events)
        standard_events = self._generate_standard_events(week, base_timestamp, remaining)
        events.extend(standard_events)

        # Sort by timestamp
        events.sort(key=lambda e: e.timestamp)

        return events

    def _generate_standard_events(
        self,
        week: int,
        base_timestamp: datetime,
        count: int,
    ) -> List[BehavioralEvent]:
        """Generate standard (non-exchange) behavioral events."""
        events = []

        # Behavioral patterns by role
        patterns = {
            "consultant": [
                {"app": ApplicationType.EMAIL, "action": "check_email", "type": BehaviorType.COMMUNICATION},
                {"app": ApplicationType.CRM, "action": "update_crm", "type": BehaviorType.DATA_TRANSFER},
                {"app": ApplicationType.PSA_TOOL, "action": "log_time", "type": BehaviorType.DATA_TRANSFER},
            ],
            "manager": [
                {"app": ApplicationType.PSA_TOOL, "action": "review_utilization", "type": BehaviorType.DECISION_MAKING},
                {"app": ApplicationType.CALENDAR, "action": "schedule_meeting", "type": BehaviorType.COMMUNICATION},
            ],
            "partner": [
                {"app": ApplicationType.PHONE, "action": "client_call", "type": BehaviorType.COMMUNICATION},
                {"app": ApplicationType.EMAIL, "action": "strategic_direction", "type": BehaviorType.DECISION_MAKING},
            ],
        }

        for _ in range(count):
            staff = self.rng.choice(self.staff)
            role_key = staff.role.value if staff.role.value in patterns else "consultant"
            pattern = self.rng.choice(patterns.get(role_key, patterns["consultant"]))

            hour_offset = self.rng.uniform(8, 18)
            day_offset = self.rng.randint(0, 4)
            timestamp = base_timestamp + timedelta(days=day_offset, hours=hour_offset)

            events.append(BehavioralEvent(
                event_id=self._generate_event_id(),
                timestamp=timestamp,
                staff_id=staff.id,
                staff_name=staff.name,
                staff_tenure_years=staff.tenure_years,
                staff_role=staff.role.value,
                staff_department=staff.department,
                behavior_type=pattern["type"],
                application=pattern["app"],
                action=pattern["action"],
                description=f"{staff.name} performed {pattern['action']}",
                knowledge_signal_weight=staff.institutional_knowledge_weight * 0.3,
                metadata={"week": week},
            ))

        return events


def generate_behavioral_events(
    week: int,
    seed: Optional[int] = None,
    total_events: int = 150,
) -> List[BehavioralEvent]:
    """
    Convenience function to generate weekly behavioral events.
    """
    if seed is None:
        seed = SIMULATION_CONFIG.random_seed + week + 1000

    generator = BehavioralExhaustGenerator(seed=seed)
    return generator.generate_weekly_events(week, total_events=total_events)


def extract_knowledge_events(events: List[BehavioralEvent]) -> List[BehavioralEvent]:
    """Filter to events with high knowledge signal (answers, not questions)."""
    return [e for e in events if e.knowledge_signal_weight > 0.5 and e.raw_content]


def extract_exchange_events(events: List[BehavioralEvent]) -> List[BehavioralEvent]:
    """Filter to events that came from knowledge exchanges."""
    return [e for e in events if e.exchange is not None]


def extract_decision_events(events: List[BehavioralEvent]) -> List[BehavioralEvent]:
    """Filter to events involving decisions."""
    return [e for e in events if e.involves_decision]


def extract_bypass_events(events: List[BehavioralEvent]) -> List[BehavioralEvent]:
    """Filter to events that bypass standard process."""
    return [e for e in events if e.is_process_bypass]
