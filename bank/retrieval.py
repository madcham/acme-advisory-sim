"""
Context Retrieval for the Context Bank.

Implements confidence-weighted retrieval of context objects
relevant to agent decision-making scenarios.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import re

from models.context_object import ContextObject, ContextGrade


@dataclass
class RetrievalResult:
    """Result of a context retrieval operation."""
    objects: List[ContextObject]
    query_terms: List[str]
    workflow_filter: Optional[str]
    total_candidates: int
    retrieval_time_ms: float = 0.0

    @property
    def count(self) -> int:
        """Number of objects retrieved."""
        return len(self.objects)

    def format_for_prompt(self) -> str:
        """Format retrieved objects for inclusion in agent prompt."""
        if not self.objects:
            return "No relevant context found."

        lines = ["Relevant organizational context:"]
        for i, obj in enumerate(self.objects, 1):
            conf = obj.current_confidence or obj.confidence_at_creation
            grade = obj.context_grade.value if obj.context_grade else "unknown"
            lines.append(f"\n[{i}] (confidence: {conf:.2f}, type: {grade})")
            lines.append(f"    {obj.payload}")

            # Add key structured data if present
            if obj.structured_data:
                key_fields = _extract_key_fields(obj.structured_data)
                if key_fields:
                    lines.append(f"    Data: {key_fields}")

        return "\n".join(lines)


def _extract_key_fields(data: dict) -> str:
    """Extract key fields from structured data for display."""
    priority_keys = [
        "vendor", "client", "staff_member", "stakeholder", "approver",
        "required_approver", "threshold_amount", "notice_hours",
        "action", "action_required"
    ]

    extracted = []
    for key in priority_keys:
        if key in data:
            extracted.append(f"{key}={data[key]}")

    return ", ".join(extracted[:4])  # Limit to 4 fields


def retrieve_relevant_context(
    bank,  # ContextBank - avoid circular import
    scenario: Dict[str, Any],
    workflow_id: Optional[str] = None,
    min_confidence: float = 0.3,
    top_k: int = 5,
    exclude_expired: bool = False,
) -> RetrievalResult:
    """
    Retrieve context objects relevant to a decision scenario.

    Args:
        bank: The ContextBank instance to query.
        scenario: Dict describing the decision scenario with keys like:
                 - vendor: vendor being considered
                 - client: client involved
                 - action: action being taken
                 - keywords: additional search terms
        workflow_id: Optional workflow to filter by.
        min_confidence: Minimum confidence threshold.
        top_k: Maximum number of objects to retrieve.
        exclude_expired: Whether to exclude expired_process grade objects.

    Returns:
        RetrievalResult with matching objects.
    """
    import time
    start_time = time.time()

    # Build search terms from scenario
    search_terms = _extract_search_terms(scenario)

    # Get initial candidates from workflow filter
    if workflow_id:
        candidates = bank.query(
            workflow_id=workflow_id,
            min_confidence=min_confidence,
            exclude_superseded=True,
            exclude_expired=exclude_expired,
        )
    else:
        candidates = bank.query(
            min_confidence=min_confidence,
            exclude_superseded=True,
            exclude_expired=exclude_expired,
        )

    total_candidates = len(candidates)

    # Score candidates by relevance to scenario
    scored = []
    for obj in candidates:
        score = _score_relevance(obj, scenario, search_terms)
        if score > 0:
            scored.append((obj, score))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    # Take top_k
    results = [obj for obj, _ in scored[:top_k]]

    elapsed_ms = (time.time() - start_time) * 1000

    return RetrievalResult(
        objects=results,
        query_terms=search_terms,
        workflow_filter=workflow_id,
        total_candidates=total_candidates,
        retrieval_time_ms=elapsed_ms,
    )


def _extract_search_terms(scenario: Dict[str, Any]) -> List[str]:
    """Extract search terms from a scenario dict."""
    terms = []

    # Direct entity terms
    for key in ["vendor", "client", "staff_member", "stakeholder"]:
        if key in scenario and scenario[key]:
            terms.append(str(scenario[key]).lower())

    # Action terms
    if "action" in scenario:
        terms.extend(scenario["action"].lower().split("_"))

    # Explicit keywords
    if "keywords" in scenario:
        if isinstance(scenario["keywords"], list):
            terms.extend([k.lower() for k in scenario["keywords"]])
        else:
            terms.extend(scenario["keywords"].lower().split())

    return list(set(terms))


def _score_relevance(
    obj: ContextObject,
    scenario: Dict[str, Any],
    search_terms: List[str],
) -> float:
    """
    Score how relevant a context object is to a scenario.

    Returns a score from 0.0 to 1.0.
    """
    score = 0.0

    # Check structured data matches (highest weight)
    if obj.structured_data:
        for key in ["vendor", "client", "staff_member", "stakeholder"]:
            if key in scenario and key in obj.structured_data:
                if str(scenario[key]).lower() == str(obj.structured_data[key]).lower():
                    score += 0.5  # Strong entity match

    # Check keyword matches in payload
    payload_lower = obj.payload.lower()
    for term in search_terms:
        if term in payload_lower:
            score += 0.15

    # Check keyword matches in structured_data
    if obj.structured_data:
        struct_str = str(obj.structured_data).lower()
        for term in search_terms:
            if term in struct_str and term not in payload_lower:
                score += 0.1

    # Boost high-confidence objects
    confidence = obj.current_confidence or obj.confidence_at_creation
    score *= (0.5 + confidence * 0.5)  # Scale by confidence

    # Penalize expired process grade
    if obj.context_grade == ContextGrade.expired_process:
        score *= 0.3

    # Boost compliance_scaffolding slightly (important to not miss)
    if obj.context_grade == ContextGrade.compliance_scaffolding:
        score *= 1.1

    return min(1.0, score)


def retrieve_for_vendor_sow(
    bank,
    vendor_id: str,
    workflow_id: str = "W4",
    min_confidence: float = 0.3,
    top_k: int = 5,
) -> RetrievalResult:
    """
    Specialized retrieval for vendor SOW scenarios.

    This is the key retrieval path for the Brightline scenario.
    """
    scenario = {
        "vendor": vendor_id,
        "action": "sow_issuance",
        "keywords": ["approval", "secondary", "pricing", "dispute"],
    }

    return retrieve_relevant_context(
        bank=bank,
        scenario=scenario,
        workflow_id=workflow_id,
        min_confidence=min_confidence,
        top_k=top_k,
    )


def retrieve_for_staffing(
    bank,
    client_id: str,
    staff_id: Optional[str] = None,
    workflow_id: str = "W3",
    min_confidence: float = 0.3,
    top_k: int = 5,
) -> RetrievalResult:
    """Specialized retrieval for staffing decisions."""
    scenario = {
        "client": client_id,
        "action": "staffing_assignment",
        "keywords": ["conflict", "assignment", "notice"],
    }
    if staff_id:
        scenario["staff_member"] = staff_id

    return retrieve_relevant_context(
        bank=bank,
        scenario=scenario,
        workflow_id=workflow_id,
        min_confidence=min_confidence,
        top_k=top_k,
    )


def retrieve_for_billing(
    bank,
    client_id: str,
    action: str = "invoice",
    workflow_id: str = "W5",
    min_confidence: float = 0.3,
    top_k: int = 5,
) -> RetrievalResult:
    """Specialized retrieval for billing decisions."""
    scenario = {
        "client": client_id,
        "action": action,
        "keywords": ["payment", "escalation", "write-off", "billing"],
    }

    return retrieve_relevant_context(
        bank=bank,
        scenario=scenario,
        workflow_id=workflow_id,
        min_confidence=min_confidence,
        top_k=top_k,
    )


def retrieve_for_proposal(
    bank,
    client_id: str,
    workflow_id: str = "W2",
    min_confidence: float = 0.3,
    top_k: int = 5,
) -> RetrievalResult:
    """Specialized retrieval for proposal decisions."""
    scenario = {
        "client": client_id,
        "action": "proposal_decision",
        "keywords": ["go", "no-go", "override", "conflict", "margin"],
    }

    return retrieve_relevant_context(
        bank=bank,
        scenario=scenario,
        workflow_id=workflow_id,
        min_confidence=min_confidence,
        top_k=top_k,
    )
