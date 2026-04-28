"""
Contradiction Detection for Context Objects (Enhanced v2.0).

Uses semantic detection via Claude API when available, with improved
rule-based fallback that requires entity overlap before flagging.

Key principle: Two objects contradict ONLY if they:
1. Share at least one named entity (pre-filter)
2. Make opposing factual claims about that entity
Keyword overlap alone is NOT sufficient.
"""

from dataclasses import dataclass
from typing import List, Optional, Set, Dict, Any
import re
import os
import json

from models.context_object import ContextObject, ContextGrade


@dataclass
class Contradiction:
    """Represents a detected contradiction between context objects."""
    new_object_id: str
    existing_object_id: str
    contradiction_type: str  # "direct_opposition", "partial_conflict", "outdated_superseded", "value_conflict"
    description: str
    confidence: float  # How confident we are this is a real contradiction
    shared_entities: List[str] = None  # Entities both objects reference

    def __post_init__(self):
        if self.shared_entities is None:
            self.shared_entities = []


# Domain-specific entities for Acme Advisory
# NOTE: Only include SPECIFIC named entities, not generic terms like "sow"
DOMAIN_ENTITIES = {
    # Vendors (these are the key identifiers)
    "brightline", "brightline_consulting", "vance", "vance_analytics", "summit", "summit_research",
    # Clients
    "terralogic", "hartwell", "hartwell_group", "nexum", "nexum_partners", "meridian", "apex",
    # Key people (most specific - names that uniquely identify)
    "okafor", "david_okafor", "webb", "marcus_webb", "nair", "priya_nair",
    "park", "jordan_park", "holloway", "james_holloway", "chen", "sarah_chen",
    "vasquez", "elena_vasquez",
}

# Generic terms that should NOT be used for entity matching
# (they appear in many contexts without indicating same subject)
GENERIC_TERMS_EXCLUDE = {
    "sow", "write-off", "writeoff", "coi", "conflict_of_interest",
    "approval", "process", "policy", "review", "check", "escalate",
    "payment", "billing", "invoice", "scope", "engagement",
}


def extract_entities(payload: str, structured_data: Optional[dict] = None) -> Set[str]:
    """
    Extract named entities from payload and structured data.

    Uses:
    1. Domain-specific entity list (vendors, clients, people)
    2. Structured data entity fields

    Excludes generic terms that don't uniquely identify subjects.
    """
    entities = set()
    payload_lower = payload.lower()

    # Check for domain entities (specific named entities only)
    for entity in DOMAIN_ENTITIES:
        if entity in payload_lower:
            # Normalize to base form (e.g., "brightline_consulting" -> "brightline")
            base = entity.split("_")[0] if "_" in entity else entity
            entities.add(base)

    # Extract from structured data (most reliable source)
    if structured_data:
        entity_keys = ["vendor", "client", "staff_member", "stakeholder", "approver", "partner"]
        for key in entity_keys:
            if key in structured_data and structured_data[key]:
                value = str(structured_data[key]).lower()
                # Extract base name
                base = value.split("_")[0] if "_" in value else value
                # Only add if it's a meaningful entity, not a generic term
                if base not in GENERIC_TERMS_EXCLUDE and len(base) > 2:
                    entities.add(base)

    # Filter out any generic terms that may have slipped through
    entities = {e for e in entities if e not in GENERIC_TERMS_EXCLUDE}

    return entities


def _get_shared_entities(
    obj1: ContextObject,
    obj2: ContextObject,
) -> Set[str]:
    """Find entities shared between two context objects."""
    entities1 = extract_entities(obj1.payload, obj1.structured_data)
    entities2 = extract_entities(obj2.payload, obj2.structured_data)
    return entities1.intersection(entities2)


class ContradictionDetector:
    """
    Detects contradictions between context objects.

    Uses semantic detection via Claude API when available, with improved
    rule-based fallback. Always requires entity overlap before flagging.

    Contradiction types:
    - direct_opposition: Explicit opposing claims about same entity
    - partial_conflict: Related statements that may conflict
    - outdated_superseded: One object supersedes another temporally
    - value_conflict: Same entity, different numeric values
    """

    def __init__(
        self,
        similarity_threshold: float = 0.75,
        use_api: bool = True,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the detector.

        Args:
            similarity_threshold: Minimum similarity for semantic comparison.
            use_api: Whether to use Claude API for semantic detection.
            api_key: Anthropic API key (defaults to env var).
        """
        self.similarity_threshold = similarity_threshold
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.use_api = use_api and bool(self.api_key)

        # Opposition indicators for rule-based detection
        self.opposition_patterns = [
            # Temporal oppositions
            (r"always\s+(\w+)", r"never\s+\1"),
            (r"do not", r"always"),
            (r"never", r"always"),
            (r"required", r"not required"),
            (r"before", r"after"),
            # Numeric oppositions (different values)
            (r"(\d+)\s*(day|hour|%|percent)", r"(\d+)\s*\2"),
        ]

    def detect(
        self,
        new_object: ContextObject,
        existing_objects: List[ContextObject],
        current_week: int,
    ) -> List[Contradiction]:
        """
        Detect contradictions between a new object and existing ones.

        Pre-filters by entity overlap before expensive checks.
        """
        contradictions = []

        # Pre-filter: only check objects with confidence > 0.5
        if (new_object.current_confidence or new_object.confidence_at_creation) < 0.5:
            return contradictions

        new_entities = extract_entities(new_object.payload, new_object.structured_data)

        # Only check against recent objects to limit API calls
        recent_objects = sorted(existing_objects, key=lambda x: x.week, reverse=True)[:10]

        for existing in recent_objects:
            # Skip same object
            if existing.id == new_object.id:
                continue

            # Skip low-confidence existing objects
            if (existing.current_confidence or existing.confidence_at_creation) < 0.5:
                continue

            # CRITICAL: Require entity overlap
            existing_entities = extract_entities(existing.payload, existing.structured_data)
            shared = new_entities.intersection(existing_entities)

            if not shared:
                continue  # No shared entities = no contradiction possible

            # Check for contradiction
            contradiction = self._check_contradiction(
                new_object, existing, shared, current_week
            )
            if contradiction:
                contradictions.append(contradiction)

        return contradictions

    def _check_contradiction(
        self,
        new_obj: ContextObject,
        existing_obj: ContextObject,
        shared_entities: Set[str],
        current_week: int,
    ) -> Optional[Contradiction]:
        """
        Check if two objects with shared entities contradict.

        Uses API if available, otherwise rule-based.
        Requires at least 2 shared entities before making API call.
        """
        # Require at least 2 shared entities for API check to limit calls
        if len(shared_entities) < 2:
            # Still do rule-based check for value conflicts with single entity
            return self._rule_based_contradiction_check(new_obj, existing_obj, shared_entities)

        # Try semantic detection first (only with 2+ shared entities)
        if self.use_api:
            result = self._semantic_contradiction_check(new_obj, existing_obj, shared_entities)
            if result:
                return result

        # Fall back to improved rule-based
        return self._rule_based_contradiction_check(new_obj, existing_obj, shared_entities)

    def _semantic_contradiction_check(
        self,
        new_obj: ContextObject,
        existing_obj: ContextObject,
        shared_entities: Set[str],
    ) -> Optional[Contradiction]:
        """
        Use Claude API to detect genuine logical contradictions.

        Only called when objects share entities and API is available.
        """
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=self.api_key)

            prompt = f"""You are evaluating two organizational context objects for logical contradiction.

Context Object A (existing):
"{existing_obj.payload}"

Context Object B (new):
"{new_obj.payload}"

They share these entities: {', '.join(shared_entities)}

A genuine contradiction means: both objects are about the same specific situation AND make
opposing factual claims that cannot both be true. For example:
- CONTRADICTION: "Always escalate TerraLogic after 45 days" vs "Never escalate TerraLogic before 65 days"
- NOT A CONTRADICTION: Two objects that both mention Brightline but describe different aspects
- NOT A CONTRADICTION: One object uses the word "not" in an unrelated context

Be conservative. Only flag genuine logical oppositions.

Respond in JSON only:
{{
  "is_contradiction": true/false,
  "confidence": 0.0-1.0,
  "reason": "one sentence explaining the contradiction or why it is not one",
  "contradiction_type": "direct_opposition|partial_conflict|outdated_superseded|not_contradictory"
}}"""

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                timeout=10.0,  # Prevent hanging on slow responses
                temperature=0.0,  # Deterministic for classification
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.content[0].text

            # Parse JSON from response
            json_match = re.search(r'\{[^}]+\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(result_text)

            if result.get("is_contradiction") and result.get("confidence", 0) > 0.7:
                return Contradiction(
                    new_object_id=new_obj.id,
                    existing_object_id=existing_obj.id,
                    contradiction_type=result.get("contradiction_type", "direct_opposition"),
                    description=result.get("reason", "Semantic contradiction detected"),
                    confidence=result.get("confidence", 0.75),
                    shared_entities=list(shared_entities),
                )

        except Exception as e:
            # Fall through to rule-based on any error
            pass

        return None

    def _rule_based_contradiction_check(
        self,
        new_obj: ContextObject,
        existing_obj: ContextObject,
        shared_entities: Set[str],
    ) -> Optional[Contradiction]:
        """
        Improved rule-based contradiction detection.

        Requires:
        1. Shared entities (already verified)
        2. Evidence of opposing claims, not just negation words
        """
        # Check for value contradictions in structured data (most reliable)
        value_contradiction = self._check_value_contradiction(new_obj, existing_obj, shared_entities)
        if value_contradiction:
            return value_contradiction

        # Check for direct opposition patterns (requires 2+ shared entities)
        opposition = self._check_opposition_patterns(new_obj, existing_obj, shared_entities)
        if opposition:
            return opposition

        # Check for temporal supersession (one explicitly outdates the other)
        temporal = self._check_temporal_supersession(new_obj, existing_obj, shared_entities)
        if temporal:
            return temporal

        return None

    def _check_value_contradiction(
        self,
        new_obj: ContextObject,
        existing_obj: ContextObject,
        shared_entities: Set[str],
    ) -> Optional[Contradiction]:
        """Check for same entity with conflicting numeric values."""
        if not new_obj.structured_data or not existing_obj.structured_data:
            return None

        value_keys = [
            "threshold_amount", "notice_hours", "payment_days", "actual_payment_days",
            "discount_percent", "overcharge_percent", "days", "hours",
            "escalation_threshold_days", "escalation_days", "wait_days",
        ]

        for key in value_keys:
            new_val = new_obj.structured_data.get(key)
            existing_val = existing_obj.structured_data.get(key)

            if new_val is not None and existing_val is not None:
                if new_val != existing_val:
                    return Contradiction(
                        new_object_id=new_obj.id,
                        existing_object_id=existing_obj.id,
                        contradiction_type="value_conflict",
                        description=f"Conflicting values for '{key}': {new_val} vs {existing_val}",
                        confidence=0.85,
                        shared_entities=list(shared_entities),
                    )

        return None

    def _check_opposition_patterns(
        self,
        new_obj: ContextObject,
        existing_obj: ContextObject,
        shared_entities: Set[str],
    ) -> Optional[Contradiction]:
        """
        Check for linguistic opposition patterns about shared entities.

        Must find evidence that both objects make claims about the same
        entity AND those claims oppose each other.

        Requires at least 2 shared meaningful entities to reduce false positives.
        """
        # Require multiple shared entities for linguistic opposition check
        # (value contradictions with single entity are handled separately)
        if len(shared_entities) < 2:
            return None

        new_lower = new_obj.payload.lower()
        existing_lower = existing_obj.payload.lower()

        # Build entity-specific context windows
        for entity in shared_entities:
            # Find sentences containing the entity in each object
            new_sentences = self._sentences_containing(new_lower, entity)
            existing_sentences = self._sentences_containing(existing_lower, entity)

            if not new_sentences or not existing_sentences:
                continue

            # Check for opposition within entity-relevant sentences
            for new_sent in new_sentences:
                for exist_sent in existing_sentences:
                    # Look for opposing verbs/actions
                    if self._sentences_oppose(new_sent, exist_sent):
                        return Contradiction(
                            new_object_id=new_obj.id,
                            existing_object_id=existing_obj.id,
                            contradiction_type="direct_opposition",
                            description=f"Opposing claims about '{entity}'",
                            confidence=0.75,
                            shared_entities=list(shared_entities),
                        )

        return None

    def _sentences_containing(self, text: str, entity: str) -> List[str]:
        """Extract sentences containing a specific entity."""
        sentences = re.split(r'[.!?]', text)
        return [s.strip() for s in sentences if entity in s and len(s.strip()) > 10]

    def _sentences_oppose(self, sent1: str, sent2: str) -> bool:
        """
        Check if two sentences make opposing claims.

        Looks for:
        - "always" vs "never"
        - "do X" vs "do not X" / "don't X"
        - "before X" vs "after X"
        - Opposite recommendations about same action
        """
        opposition_pairs = [
            ("always", "never"),
            ("do not", "always"),
            ("don't", "always"),
            ("required", "not required"),
            ("must", "must not"),
            ("should", "should not"),
            ("before", "after"),
            ("escalate", "do not escalate"),
            ("assign", "do not assign"),
            ("approve", "reject"),
        ]

        sent1_lower = sent1.lower()
        sent2_lower = sent2.lower()

        for term1, term2 in opposition_pairs:
            if (term1 in sent1_lower and term2 in sent2_lower) or \
               (term2 in sent1_lower and term1 in sent2_lower):
                return True

        return False

    def _check_temporal_supersession(
        self,
        new_obj: ContextObject,
        existing_obj: ContextObject,
        shared_entities: Set[str],
    ) -> Optional[Contradiction]:
        """Check if one object explicitly supersedes another temporally."""
        new_lower = new_obj.payload.lower()

        # Indicators that new object supersedes old
        supersession_indicators = [
            "no longer", "changed", "updated", "was policy until",
            "now", "as of", "starting", "since", "replaced",
        ]

        # Check if new object explicitly mentions temporal change
        has_temporal_indicator = any(ind in new_lower for ind in supersession_indicators)

        if not has_temporal_indicator:
            return None

        # Check if contexts relate to same topic
        if existing_obj.context_grade == ContextGrade.expired_process:
            return Contradiction(
                new_object_id=new_obj.id,
                existing_object_id=existing_obj.id,
                contradiction_type="outdated_superseded",
                description="New object may supersede existing expired process",
                confidence=0.70,
                shared_entities=list(shared_entities),
            )

        return None


def detect_contradictions_batch(
    objects: List[ContextObject],
    use_api: bool = False,
    similarity_threshold: float = 0.75,
) -> List[Contradiction]:
    """
    Detect all contradictions within a batch of objects.

    Pre-filters by entity overlap for efficiency.
    """
    detector = ContradictionDetector(
        similarity_threshold=similarity_threshold,
        use_api=use_api,
    )
    all_contradictions = []
    seen_pairs = set()

    for i, obj1 in enumerate(objects):
        for obj2 in objects[i + 1:]:
            pair_key = tuple(sorted([obj1.id, obj2.id]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            # Pre-filter: require entity overlap
            shared = _get_shared_entities(obj1, obj2)
            if not shared:
                continue

            contradiction = detector._check_contradiction(obj1, obj2, shared, current_week=0)
            if contradiction:
                contradiction.new_object_id = obj1.id
                contradiction.existing_object_id = obj2.id
                all_contradictions.append(contradiction)

    return all_contradictions
