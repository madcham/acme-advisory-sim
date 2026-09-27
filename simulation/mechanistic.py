"""
Mechanistic decision model.

In the calibrated model (generators/agent_exhaust.py), each condition's accuracy
is a configured number and retrieved context never affects the outcome. Here the
outcome follows from what the agent actually retrieves:

    1. Rank the context objects the condition can see, using that condition's
       ranking rule.
    2. The agent acts on the highest-ranked result that bears on the decision.
       If that object carries correct guidance (the ground-truth knowledge, or a
       record of a past correct decision), the agent is usually right. If it
       carries wrong guidance (an injected contradicting policy, or a record of
       a past wrong decision), the agent is usually wrong.
    3. With nothing usable, the agent falls back to standard process and is
       right only at the base rate.

Everything except the ranking rule is shared by all conditions: the relevance
function, retrieval recall, interpretation accuracy, the base rate, and chaos
effects on agents. The conditions differ only as described in the thesis:

    SILOED_TYPICAL   no retrieval
    SILOED_ADVANCED  own + adjacent departments; relevance x decayed confidence
    GLOBAL_RAG       everything; relevance only
    CONTEXT_BANK     everything, minus superseded and low-confidence objects;
                     relevance x decayed confidence x validation record, and the
                     bank records outcome feedback on the objects agents act on
"""

import random
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from config.simulation_config import (
    AGENTS, DEPARTMENTS, RunCondition, get_department_for_agent,
)
from models.context_object import ContextObject, ContentType, DecayFunction, SourceType


# GROUND_TRUTH_ANSWERS template keys (generators/behavioral_exhaust.py) -> the
# seeded context object each one restates
GROUND_TRUTH_KEY_TO_CONTEXT = {
    "brightline_approval": "CTX-001",
    "fs_scope_documentation": "CTX-002",
    "hartwell_override": "CTX-003",
    "priya_notice": "CTX-004",
    "vance_pricing": "CTX-005",
    "terralogic_payment": "CTX-006",
    "coi_manual_check": "CTX-007",
    "elena_methodology": "CTX-008",
    "ceo_writeoff": "CTX-009",
    "jordan_nexum_conflict": "CTX-010",
    "friday_submissions": "CTX-011",
    "page_review_old": "CTX-012",
}

# Scenario entity keys whose values name a specific entity (matched as phrases)
_NAME_KEYS = ("vendor_name", "client_name", "candidate_name", "subcontractor_name")
# Scenario entity keys whose values describe the situation (matched as words)
_TOPIC_KEYS = ("engagement_type", "dispute_reason")

_WORKFLOW_TO_DEPARTMENT = {
    wf: dept for dept, info in DEPARTMENTS.items() for wf in info["workflows"]
}


class Guidance(str, Enum):
    """What acting on a context object would do for a given scenario."""
    CORRECT = "correct"
    WRONG = "wrong"
    NEUTRAL = "neutral"  # does not bear on this decision


@dataclass
class MechanisticConfig:
    """Parameters shared by every condition."""
    # P(correct) when acting on standard process with no usable context. The
    # scenarios are all exceptions, so standard process is usually wrong.
    base_success_rate: float = 0.25
    # P(a relevant object shows up in results at all)
    retrieval_recall: float = 0.85
    # P(the agent applies the guidance it acts on as intended)
    interpretation_accuracy: float = 0.90
    top_k: int = 5
    # CONTEXT_BANK only: objects below this decayed confidence are filtered out
    bank_min_confidence: float = 0.3

    # CONTEXT_BANK primitives, individually switchable for ablation
    use_confidence: bool = True
    use_validation: bool = True
    use_supersession: bool = True


def scenario_terms(entities: Dict[str, str]) -> Tuple[List[str], List[str]]:
    """Entity-name phrases and topic words to match a scenario against."""
    names = [entities[k].lower() for k in _NAME_KEYS if entities.get(k)]
    topics: List[str] = []
    for k in _TOPIC_KEYS:
        if entities.get(k):
            topics.extend(w for w in entities[k].lower().split("_") if len(w) >= 4)
    return names, topics


def relevance(obj: ContextObject, names: List[str], topics: List[str]) -> float:
    """Keyword relevance of an object to a scenario; identical for every condition."""
    text = (obj.payload + " " + str(obj.structured_data or "")).lower()
    return sum(1.0 for n in names if n in text) + sum(0.3 for t in topics if t in text)


def guidance(obj: ContextObject, ground_truth_ids: List[str], bank=None, _depth: int = 0) -> Guidance:
    """Whether acting on this object leads to the right or wrong decision."""
    if obj.id in ground_truth_ids:
        return Guidance.CORRECT
    data = obj.structured_data or {}
    if data.get("contradicts") in ground_truth_ids:
        return Guidance.WRONG
    if data.get("supports_context_id") in ground_truth_ids:
        return Guidance.CORRECT if data.get("decision_correct", True) else Guidance.WRONG
    if GROUND_TRUTH_KEY_TO_CONTEXT.get(data.get("ground_truth_key")) in ground_truth_ids:
        return Guidance.CORRECT

    # Synthesized objects say what the majority of their sources say
    sources = [link.source_id for link in obj.derivation_chain if link.relationship == "derived_from"]
    if sources and bank is not None and _depth < 3:
        votes = [
            guidance(src, ground_truth_ids, bank, _depth + 1)
            for src in (bank.get(sid) for sid in dict.fromkeys(sources))
            if src is not None
        ]
        correct, wrong = votes.count(Guidance.CORRECT), votes.count(Guidance.WRONG)
        if correct > wrong:
            return Guidance.CORRECT
        if wrong > correct:
            return Guidance.WRONG
    return Guidance.NEUTRAL


def _apply_error_multiplier(p_correct: float, multiplier: float) -> float:
    """Scale the error rate (chaos agent drift), as the calibrated model does."""
    if multiplier <= 1.0:
        return p_correct
    return 1.0 - min(0.9, (1.0 - p_correct) * multiplier)


class MechanisticDecisionModel:
    """Makes decisions whose outcome depends on what the agent retrieves."""

    def __init__(
        self,
        condition: RunCondition,
        seed: int,
        config: Optional[MechanisticConfig] = None,
    ):
        legacy = {
            RunCondition.WITHOUT_BANK: RunCondition.SILOED_TYPICAL,
            RunCondition.WITH_BANK: RunCondition.CONTEXT_BANK,
        }
        self.condition = legacy.get(condition, condition)
        self.config = config or MechanisticConfig()
        self._rng = random.Random(seed)
        self._decision_counter = 0

    # ------------------------------------------------------------------
    # Visibility and ranking
    # ------------------------------------------------------------------

    def _visible_departments(self, agent_id: str) -> Optional[Set[str]]:
        """Departments whose objects the agent can see; None means all."""
        if self.condition in (RunCondition.GLOBAL_RAG, RunCondition.CONTEXT_BANK):
            return None
        department = get_department_for_agent(agent_id)
        visible = {department}
        if self.condition == RunCondition.SILOED_ADVANCED:
            visible.update(DEPARTMENTS.get(department, {}).get("adjacent_departments", []))
        return visible

    def _score(self, obj: ContextObject, rel: float) -> Optional[float]:
        """Condition-specific ranking score; None excludes the object."""
        if self.condition == RunCondition.GLOBAL_RAG:
            return rel

        confidence = obj.current_confidence or obj.confidence_at_creation
        if self.condition == RunCondition.SILOED_ADVANCED:
            return rel * confidence

        cfg = self.config
        if cfg.use_supersession and obj.is_superseded():
            return None
        score = rel
        if cfg.use_confidence:
            if confidence < cfg.bank_min_confidence:
                return None
            score *= confidence
        if cfg.use_validation:
            # Posterior mean reliability under a uniform prior, scaled so an
            # object with no track record keeps a factor of 1.0
            v, inv = len(obj.validated_by), len(obj.invalidated_by)
            score *= 2.0 * (v + 1) / (v + inv + 2)
        return score

    def _retrieve(self, bank, agent_id: str, entities: Dict[str, str]) -> List[ContextObject]:
        """Top-k objects for this condition, after recall noise."""
        names, topics = scenario_terms(entities)
        visible = self._visible_departments(agent_id)

        # Shuffle first so ties are broken randomly, not by insertion order
        candidates = bank.get_all()
        self._rng.shuffle(candidates)

        scored = []
        for obj in candidates:
            if visible is not None and _WORKFLOW_TO_DEPARTMENT.get(obj.workflow_id) not in visible:
                continue
            rel = relevance(obj, names, topics)
            if rel <= 0:
                continue
            score = self._score(obj, rel)
            if score is None:
                continue
            if self._rng.random() >= self.config.retrieval_recall:
                continue
            scored.append((score, obj))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [obj for _, obj in scored[: self.config.top_k]]

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    def decide(
        self,
        agent_id: str,
        scenario,  # AgentScenario
        week: int,
        context_bank=None,  # Optional ContextBank
        accuracy_modifier: float = 1.0,
        context_ignore_probability: float = 0.0,
    ):
        """Make one decision and return an AgentDecision."""
        from generators.agent_exhaust import AgentDecision, DecisionOutcome, utc_now

        cfg = self.config
        bank = context_bank
        gt_ids = scenario.ground_truth_context_ids

        retrieved: List[ContextObject] = []
        acted_on: Optional[ContextObject] = None
        acted_guidance = Guidance.NEUTRAL

        if bank is not None and self.condition != RunCondition.SILOED_TYPICAL:
            retrieved = self._retrieve(bank, agent_id, scenario.entities)
            ignores_context = self._rng.random() < context_ignore_probability
            if not ignores_context:
                for obj in retrieved:
                    g = guidance(obj, gt_ids, bank)
                    if g != Guidance.NEUTRAL:
                        acted_on, acted_guidance = obj, g
                        break

        p_follow = _apply_error_multiplier(cfg.interpretation_accuracy, accuracy_modifier)
        p_base = _apply_error_multiplier(cfg.base_success_rate, accuracy_modifier)

        if acted_guidance == Guidance.CORRECT:
            correct = self._rng.random() < p_follow
            path = "followed correct guidance" if correct else "misapplied correct guidance"
        elif acted_guidance == Guidance.WRONG and self._rng.random() < p_follow:
            correct = False
            path = "followed wrong guidance"
        else:
            correct = self._rng.random() < p_base
            path = "standard process"

        action = scenario.correct_action if correct else scenario.incorrect_action
        used = [acted_on.id] if acted_on is not None else []
        self._decision_counter += 1

        decision = AgentDecision(
            decision_id=f"DEC-MX-{self._decision_counter:06d}",
            agent_id=agent_id,
            agent_name=AGENTS[agent_id]["name"],
            workflow_id=scenario.workflow_id,
            week=week,
            timestamp=utc_now(),
            scenario_type=scenario.scenario_type,
            scenario_description=scenario.description,
            entities_involved=scenario.entities,
            decision_taken=action,
            reasoning=f"{path}" + (f" ({acted_on.id})" if acted_on is not None else ""),
            confidence=0.8 if acted_on is not None else 0.6,
            context_retrieved=[o.id for o in retrieved],
            context_used=used,
            outcome=DecisionOutcome.CORRECT if correct else DecisionOutcome.INCORRECT,
            outcome_notes=path,
        )

        if bank is not None and self.condition != RunCondition.SILOED_TYPICAL:
            for obj in retrieved:
                bank.record_read(obj.id, agent_id, f"Retrieved for {scenario.scenario_type}")
            decision.deposited_context = self._decision_record(decision, gt_ids, correct, week)
            if self.condition == RunCondition.CONTEXT_BANK and cfg.use_validation:
                # Outcome feedback: the bank credits or discredits what was acted on,
                # and stores the new decision record with its known outcome
                if acted_on is not None:
                    bank.record_validation(acted_on.id, agent_id, validated=correct)
                decision.deposited_context.record_validation(agent_id, validated=correct)

        return decision

    def _decision_record(
        self,
        decision,
        gt_ids: List[str],
        correct: bool,
        week: int,
    ) -> ContextObject:
        """Context object recording what the agent did, right or wrong."""
        names = ", ".join(
            v for k, v in decision.entities_involved.items() if k in _NAME_KEYS
        )
        return ContextObject(
            created_by=decision.agent_id,
            source_type=SourceType.agent,
            workflow_id=decision.workflow_id,
            week=week,
            content_type=ContentType.decision,
            payload=f"{decision.agent_name} on {decision.scenario_type} ({names}): {decision.decision_taken}",
            structured_data={
                "scenario_type": decision.scenario_type,
                "decision_id": decision.decision_id,
                "supports_context_id": gt_ids[0] if gt_ids else None,
                "decision_correct": correct,
            },
            decay_function=DecayFunction.exponential,
            decay_rate=0.15,
            confidence_at_creation=decision.confidence * 0.8,
        )
