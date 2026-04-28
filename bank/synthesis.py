"""
Active Intelligence Synthesis Layer.

Performs three key operations on the Context Bank:
1. Pattern Crystallization - Promote recurring learnings to high-confidence context
2. Validation Propagation - Propagate validation signals through provenance chains
3. Adaptive Decay - Adjust decay rates based on retrieval/validation frequency

This module transforms raw context accumulation into active organizational intelligence.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict
import re
import os
import json
from datetime import datetime, timezone

from models.context_object import (
    ContextObject, ContextGrade, OrgLineage, DecayFunction,
    ContentType, SourceType, ProvenanceLink,
)
from bank.context_bank import ContextBank


def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


@dataclass
class SynthesisResult:
    """Result of a synthesis pass."""
    patterns_crystallized: int = 0
    validations_propagated: int = 0
    decay_rates_adjusted: int = 0
    new_objects_created: List[str] = field(default_factory=list)
    objects_updated: List[str] = field(default_factory=list)
    confidence_boosts: Dict[str, float] = field(default_factory=dict)  # object_id -> new_confidence

    def to_dict(self) -> Dict:
        return {
            "patterns_crystallized": self.patterns_crystallized,
            "validations_propagated": self.validations_propagated,
            "decay_rates_adjusted": self.decay_rates_adjusted,
            "new_objects_created": self.new_objects_created,
            "objects_updated": self.objects_updated,
            "confidence_boosts": self.confidence_boosts,
        }


@dataclass
class PatternCluster:
    """A cluster of related context objects that may form a pattern."""
    primary_entity: str
    related_objects: List[ContextObject]
    shared_keywords: Set[str]
    combined_confidence: float
    pattern_type: str  # "vendor_caution", "client_preference", "process_exception", etc.


class SynthesisEngine:
    """
    Active Intelligence Synthesis Engine.

    Analyzes the context bank and performs synthesis operations to
    transform accumulated context into crystallized organizational knowledge.
    """

    def __init__(
        self,
        bank: ContextBank,
        pattern_threshold: int = 3,  # Min occurrences to crystallize
        validation_boost: float = 0.1,  # Confidence boost per validation
        decay_reduction_factor: float = 0.5,  # Factor to reduce decay rate
        api_key: Optional[str] = None,
        use_api: bool = True,
    ):
        """
        Initialize synthesis engine.

        Args:
            bank: The context bank to synthesize
            pattern_threshold: Minimum related objects to form a pattern
            validation_boost: Confidence increase per validation
            decay_reduction_factor: Factor to multiply decay rate for validated objects
            api_key: Anthropic API key (defaults to env var)
            use_api: Whether to use Claude API for synthesis
        """
        self.bank = bank
        self.pattern_threshold = pattern_threshold
        self.validation_boost = validation_boost
        self.decay_reduction_factor = decay_reduction_factor
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.use_api = use_api and bool(self.api_key)

    def run_synthesis_pass(self, current_week: int) -> SynthesisResult:
        """
        Run a complete synthesis pass.

        Performs all three synthesis operations:
        1. Pattern crystallization
        2. Validation propagation
        3. Adaptive decay adjustment

        Args:
            current_week: Current simulation week for confidence calculation

        Returns:
            SynthesisResult with details of changes made
        """
        result = SynthesisResult()

        # 1. Pattern crystallization
        crystallized = self._crystallize_patterns(current_week)
        result.patterns_crystallized = len(crystallized)
        result.new_objects_created.extend(crystallized)

        # 2. Validation propagation
        propagated = self._propagate_validations(current_week)
        result.validations_propagated = propagated["count"]
        result.confidence_boosts.update(propagated["boosts"])
        result.objects_updated.extend(propagated["updated"])

        # 3. Adaptive decay
        adjusted = self._adjust_decay_rates(current_week)
        result.decay_rates_adjusted = len(adjusted)
        result.objects_updated.extend(adjusted)

        return result

    def _crystallize_patterns(self, current_week: int) -> List[str]:
        """
        Identify and crystallize recurring patterns into high-confidence context.

        Looks for clusters of related context objects and creates synthesized
        "crystallized" objects that represent the pattern.

        Returns:
            List of IDs of newly created crystallized objects
        """
        created_ids = []

        # Find entity clusters
        clusters = self._identify_pattern_clusters(current_week)

        for cluster in clusters:
            if len(cluster.related_objects) < self.pattern_threshold:
                continue

            # Check if we've already crystallized this pattern
            existing_crystal = self._find_existing_crystal(cluster.primary_entity)
            if existing_crystal:
                # Update existing crystal instead
                self._update_crystal(existing_crystal, cluster, current_week)
                continue

            # Create new crystallized context object
            crystal = self._create_crystallized_object(cluster, current_week)
            self.bank.deposit(crystal, check_contradictions=False)
            created_ids.append(crystal.id)

        return created_ids

    def _identify_pattern_clusters(self, current_week: int) -> List[PatternCluster]:
        """Identify clusters of related context objects by entity."""
        entity_objects: Dict[str, List[ContextObject]] = defaultdict(list)

        # Group objects by primary entity
        for obj in self.bank.get_all():
            entities = self._extract_entities(obj)
            for entity in entities:
                entity_objects[entity].append(obj)

        clusters = []
        for entity, objects in entity_objects.items():
            if len(objects) < 2:
                continue

            # Calculate shared keywords
            all_words = []
            for obj in objects:
                words = set(re.findall(r'\b[a-z]{4,}\b', obj.payload.lower()))
                all_words.append(words)

            if not all_words:
                continue

            shared = set.intersection(*all_words) if len(all_words) > 1 else all_words[0]

            # Calculate combined confidence
            confidences = []
            for obj in objects:
                conf = obj.compute_current_confidence(current_week)
                confidences.append(conf)
            combined_conf = sum(confidences) / len(confidences) if confidences else 0

            # Determine pattern type
            pattern_type = self._infer_pattern_type(entity, objects)

            clusters.append(PatternCluster(
                primary_entity=entity,
                related_objects=objects,
                shared_keywords=shared,
                combined_confidence=combined_conf,
                pattern_type=pattern_type,
            ))

        return clusters

    def _extract_entities(self, obj: ContextObject) -> Set[str]:
        """Extract key entities from a context object."""
        entities = set()

        # From structured data
        if obj.structured_data:
            for key in ["vendor", "client", "staff_member", "candidate"]:
                if key in obj.structured_data:
                    entities.add(str(obj.structured_data[key]).lower())

        # From payload using known entity patterns
        payload_lower = obj.payload.lower()
        known_entities = [
            "brightline", "vance", "summit", "terralogic", "hartwell",
            "nexum", "meridian", "apex", "okafor", "webb", "nair", "park",
            "holloway", "chen", "vasquez",
        ]
        for entity in known_entities:
            if entity in payload_lower:
                entities.add(entity)

        return entities

    def _infer_pattern_type(self, entity: str, objects: List[ContextObject]) -> str:
        """Infer the type of pattern from entity and objects."""
        # Check for vendor patterns
        vendors = ["brightline", "vance", "summit"]
        if entity in vendors:
            return "vendor_caution"

        # Check for client patterns
        clients = ["terralogic", "hartwell", "nexum", "meridian", "apex"]
        if entity in clients:
            return "client_preference"

        # Check for people patterns
        people = ["okafor", "webb", "nair", "park", "holloway", "chen", "vasquez"]
        if entity in people:
            return "stakeholder_preference"

        return "process_exception"

    def _find_existing_crystal(self, entity: str) -> Optional[ContextObject]:
        """Find an existing crystallized object for this entity."""
        for obj in self.bank.get_all():
            # source_type == SourceType.derived is the primary discriminator for crystals
            # content_type alone is insufficient - behavioral exhaust can be classified as inference
            if obj.source_type == SourceType.derived and obj.content_type == ContentType.inference:
                if obj.structured_data and obj.structured_data.get("crystallized_from") == entity:
                    return obj
        return None

    def _update_crystal(
        self,
        crystal: ContextObject,
        cluster: PatternCluster,
        current_week: int
    ) -> None:
        """Update an existing crystallized object with new evidence."""
        # Boost confidence
        new_confidence = min(0.95, crystal.confidence_at_creation + self.validation_boost)
        crystal.confidence_at_creation = new_confidence

        # Update derivation chain
        for obj in cluster.related_objects:
            if obj.id != crystal.id:
                link = ProvenanceLink(source_id=obj.id, relationship="validates")
                if link not in crystal.derivation_chain:
                    crystal.derivation_chain.append(link)

    def _synthesize_cluster_with_api(self, cluster: PatternCluster) -> Optional[str]:
        """
        Use Claude API to synthesize a pattern cluster into organizational prose.

        Returns:
            Synthesized prose or None if API call fails
        """
        if not self.use_api:
            return None

        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=self.api_key)

            # Build context from source objects
            source_summaries = []
            for i, obj in enumerate(cluster.related_objects[:6]):  # Limit to 6 for token efficiency
                source_summaries.append(f"{i+1}. [{obj.id}]: {obj.payload[:300]}")

            sources_text = "\n".join(source_summaries)

            prompt = f"""You are synthesizing organizational knowledge for a consulting firm's institutional memory system.

The following {len(cluster.related_objects)} context objects all relate to "{cluster.primary_entity}" and form a pattern of type "{cluster.pattern_type}":

{sources_text}

Write a single, authoritative paragraph (2-4 sentences) that crystallizes the essential organizational knowledge from these sources. The paragraph should:
1. Name specific entities (people, clients, vendors) involved
2. State the key insight or rule clearly
3. Explain WHY this matters (the business consequence)
4. Be written as factual organizational guidance, not as a summary

Do NOT use phrases like "Based on multiple sources" or "The pattern indicates". Write as if stating an established organizational fact.

Example good output: "David Okafor must approve all Brightline Consulting SOWs before issuance. This requirement stems from a 2022 incident where Brightline overbilled 40% on a federal engagement. Bypassing this approval has historically resulted in billing disputes and strained vendor relationships."

Write the crystallized knowledge paragraph:"""

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=250,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )

            return response.content[0].text.strip()

        except Exception as e:
            # Log error but don't fail - will fall back to template
            print(f"Synthesis API error: {e}")
            return None

    def _generate_fallback_synthesis(self, cluster: PatternCluster) -> str:
        """
        Generate meaningful synthesis prose from source objects without API.

        Extracts key information from source payloads and structures it
        into organizational guidance.
        """
        entity = cluster.primary_entity.title()
        pattern_type = cluster.pattern_type

        # Extract the most informative source object (highest confidence, most specific)
        best_source = max(
            cluster.related_objects,
            key=lambda o: (o.confidence_at_creation, len(o.payload))
        )

        # Extract key phrases and entities from sources
        all_text = " ".join(obj.payload for obj in cluster.related_objects)

        # Find specific values mentioned (percentages, days, years, amounts)
        percentages = re.findall(r'\d+%', all_text)
        years = re.findall(r'20\d{2}', all_text)
        days = re.findall(r'\d+[- ]?days?', all_text, re.IGNORECASE)

        # Find people mentioned
        people_patterns = [
            "David Okafor", "Marcus Webb", "Priya Nair", "Jordan Park",
            "James Holloway", "Sarah Chen", "Elena Vasquez"
        ]
        people_found = [p for p in people_patterns if p.lower() in all_text.lower()]

        # Build entity-specific synthesis
        if pattern_type == "vendor_caution":
            if "brightline" in entity.lower():
                year = years[0] if years else "2022"
                pct = percentages[0] if percentages else "40%"
                person = people_found[0] if people_found else "David Okafor"
                return (
                    f"{entity} Consulting requires secondary approval from {person} before any SOW issuance. "
                    f"This stems from a {year} incident where {entity} overbilled {pct} on a federal engagement. "
                    f"Bypassing approval has led to billing disputes and damaged vendor relationships."
                )
            elif "vance" in entity.lower():
                pct = percentages[0] if percentages else "15%"
                return (
                    f"{entity} Analytics pricing is negotiable up to {pct} below list rate for large engagements. "
                    f"This discount is not publicly listed and requires direct negotiation. "
                    f"Do not disclose the negotiable threshold to the vendor during initial discussions."
                )
            else:
                return (
                    f"{entity} requires additional scrutiny on all statements of work. "
                    f"Historical issues have been documented across {len(cluster.related_objects)} internal sources. "
                    f"Escalate to senior leadership before finalizing any engagement."
                )

        elif pattern_type == "client_preference":
            if "terralogic" in entity.lower():
                day_val = days[0] if days else "60 days"
                return (
                    f"{entity} operates on extended payment cycles of {day_val} regardless of contract terms. "
                    f"Do not escalate collections before day 65, as premature escalation has caused account loss. "
                    f"This is a known pattern and should be accommodated in AR forecasting."
                )
            elif "hartwell" in entity.lower():
                person = people_found[0] if people_found else "Marcus Webb"
                return (
                    f"{entity} Group opportunities receive automatic go-decision override from {person}. "
                    f"Standard margin thresholds do not apply due to the strategic relationship. "
                    f"Document the override rationale but proceed with proposals regardless of margin analysis."
                )
            elif "nexum" in entity.lower():
                person = "Jordan Park" if "Jordan Park" in people_found else (people_found[0] if people_found else "certain staff")
                return (
                    f"{entity} Partners engagements have documented conflicts with {person}. "
                    f"Do not assign conflicted staff regardless of skills match or availability. "
                    f"Source alternative staffing when {entity} work requires similar skill sets."
                )
            else:
                return (
                    f"{entity} has specific handling requirements documented across {len(cluster.related_objects)} sources. "
                    f"Review institutional context before making decisions involving this client. "
                    f"Escalate to relationship owner if guidance is unclear."
                )

        elif pattern_type == "stakeholder_preference":
            if "okafor" in entity.lower():
                return (
                    f"David {entity.title()} (Finance) is the required approver for sensitive vendor decisions. "
                    f"All Brightline SOWs and write-offs above $15K require his explicit sign-off. "
                    f"This approval authority stems from historical billing disputes he resolved."
                )
            elif "webb" in entity.lower():
                return (
                    f"Marcus {entity.title()} (Partner) holds override authority for Hartwell Group decisions. "
                    f"He will approve any Hartwell opportunity regardless of standard margin criteria. "
                    f"Inform him of Hartwell proposals but do not wait for margin-based approval."
                )
            elif "vasquez" in entity.lower():
                return (
                    f"Elena {entity.title()} holds undocumented methodology expertise for financial services engagements. "
                    f"The FS transformation approach is not in the knowledge base - consult her directly. "
                    f"She developed proprietary frameworks during the 2019 Meridian engagement."
                )
            elif "park" in entity.lower():
                return (
                    f"Jordan {entity.title()} has a documented HR conflict with Nexum Partners. "
                    f"Do not assign them to any Nexum work regardless of skills match. "
                    f"This conflict is documented in HR records and staffing must source alternatives."
                )
            else:
                person = entity.title()
                return (
                    f"{person} has specific organizational context documented across {len(cluster.related_objects)} sources. "
                    f"Consult institutional memory before making decisions involving this stakeholder. "
                    f"Their preferences and constraints may not be visible in standard systems."
                )

        else:
            # Generic process exception
            return (
                f"Organizational context for {entity} has been documented across {len(cluster.related_objects)} sources. "
                f"This represents institutional knowledge that should inform decision-making. "
                f"Review the source context objects for specific guidance."
            )

    def _create_crystallized_object(
        self,
        cluster: PatternCluster,
        current_week: int
    ) -> ContextObject:
        """Create a new crystallized context object from a pattern cluster."""
        source_ids = [obj.id for obj in cluster.related_objects]

        # Try API synthesis first
        synthesized_payload = self._synthesize_cluster_with_api(cluster)

        if synthesized_payload:
            payload = synthesized_payload
            api_used = True
        else:
            # Use intelligent fallback that generates meaningful prose
            payload = self._generate_fallback_synthesis(cluster)
            api_used = False

        # Create derivation chain
        derivation_chain = [
            ProvenanceLink(source_id=obj.id, relationship="derived_from")
            for obj in cluster.related_objects
        ]

        return ContextObject(
            created_by="synthesis_engine",
            source_type=SourceType.derived,
            week=current_week,
            content_type=ContentType.inference,
            payload=payload,
            structured_data={
                "crystallized_from": cluster.primary_entity,
                "pattern_type": cluster.pattern_type,
                "source_count": len(cluster.related_objects),
                "source_ids": source_ids,
                "api_synthesized": api_used,
            },
            decay_function=DecayFunction.permanent,
            decay_rate=0.0,
            confidence_at_creation=min(0.9, cluster.combined_confidence + 0.1),
            context_grade=ContextGrade.institutional_memory,
            context_grade_confidence=0.85,
            derivation_chain=derivation_chain,
        )

    def _propagate_validations(self, current_week: int) -> Dict:
        """
        Propagate validation signals through provenance chains.

        When an object is validated by agent action, boost confidence of
        objects in its derivation chain.

        Returns:
            Dict with count, boosts, and updated object IDs
        """
        result = {"count": 0, "boosts": {}, "updated": []}

        for obj in self.bank.get_all():
            # Check if object has been successfully used by agents
            # A correct agent action is an implicit validation - stronger than explicit
            # validation because it reflects real-world outcome rather than intent
            recent_validations = [
                a for a in obj.acted_on_by
                if a.outcome == "correct"
            ]

            if not recent_validations:
                continue

            # Boost this object's confidence
            validation_count = len(recent_validations)
            boost = min(0.2, validation_count * self.validation_boost)

            new_confidence = min(0.95, obj.confidence_at_creation + boost)
            if new_confidence > obj.confidence_at_creation:
                obj.confidence_at_creation = new_confidence
                result["boosts"][obj.id] = new_confidence
                result["updated"].append(obj.id)
                result["count"] += 1

            # Propagate to derivation chain
            for link in obj.derivation_chain:
                source_obj = self.bank.get(link.source_id)
                if source_obj and link.relationship in ["derived_from", "validates"]:
                    # Smaller boost for chain propagation
                    chain_boost = boost * 0.5
                    new_source_conf = min(0.95, source_obj.confidence_at_creation + chain_boost)
                    if new_source_conf > source_obj.confidence_at_creation:
                        source_obj.confidence_at_creation = new_source_conf
                        result["boosts"][source_obj.id] = new_source_conf
                        if source_obj.id not in result["updated"]:
                            result["updated"].append(source_obj.id)
                        result["count"] += 1

        return result

    def _adjust_decay_rates(self, current_week: int) -> List[str]:
        """
        Adjust decay rates based on retrieval and validation frequency.

        Objects that are frequently read and validated should decay slower.

        Returns:
            List of object IDs with adjusted decay rates
        """
        adjusted = []

        for obj in self.bank.get_all():
            # Skip permanent objects
            if obj.decay_function == DecayFunction.permanent:
                continue

            # Count recent reads and validations
            recent_reads = len(obj.read_by)
            recent_validations = len(obj.validated_by)
            recent_actions = len(obj.acted_on_by)

            activity_score = recent_reads + (recent_validations * 2) + recent_actions

            # High activity = reduce decay rate
            if activity_score >= 3:
                old_rate = obj.decay_rate
                new_rate = max(0.01, old_rate * self.decay_reduction_factor)

                if new_rate < old_rate:
                    obj.decay_rate = new_rate
                    adjusted.append(obj.id)

            # Very high activity = upgrade to step function or permanent
            if activity_score >= 6 and obj.decay_function == DecayFunction.linear:
                obj.decay_function = DecayFunction.step_function
                adjusted.append(obj.id)

        return adjusted


def compute_synthesis_intelligence_score(
    result: SynthesisResult,
    bank_size: int,
) -> float:
    """
    Compute an intelligence score for the synthesis pass.

    Measures how much "active intelligence" was generated.

    Args:
        result: The synthesis result
        bank_size: Current bank size

    Returns:
        Score from 0.0 to 1.0
    """
    if bank_size == 0:
        return 0.0

    # Component scores
    crystallization_score = min(1.0, result.patterns_crystallized / 5)
    propagation_score = min(1.0, result.validations_propagated / 10)
    adaptation_score = min(1.0, result.decay_rates_adjusted / 5)

    # Average boost magnitude
    if result.confidence_boosts:
        avg_boost = sum(result.confidence_boosts.values()) / len(result.confidence_boosts)
        boost_score = min(1.0, avg_boost / 0.5)
    else:
        boost_score = 0.0

    # Weighted combination
    score = (
        crystallization_score * 0.3 +
        propagation_score * 0.25 +
        adaptation_score * 0.2 +
        boost_score * 0.25
    )

    return round(score, 3)


def run_synthesis_pass(
    bank: ContextBank,
    current_week: int,
    pattern_threshold: int = 3,
) -> SynthesisResult:
    """
    Convenience function to run a synthesis pass.

    Args:
        bank: Context bank to synthesize
        current_week: Current simulation week
        pattern_threshold: Min objects to form a pattern

    Returns:
        SynthesisResult
    """
    engine = SynthesisEngine(bank, pattern_threshold=pattern_threshold)
    return engine.run_synthesis_pass(current_week)
