"""
Tests for the mechanistic decision model.

Tests:
- Relevance matching of scenarios to seeded knowledge
- Guidance labels (ground truth, contradictions, decision records, synthesis)
- Condition-specific ranking of a contradiction against the original policy
- Siloed visibility
- Outcome feedback recorded by the Context Bank only
- Reproducibility and seed sensitivity
"""

import copy

import pytest

from bank.context_bank import ContextBank
from config.seeded_context import SEEDED_CONTEXT_OBJECTS
from config.simulation_config import RunCondition
from generators.agent_exhaust import (
    BRIGHTLINE_SOW_SCENARIO, BRIGHTLINE_STAFFING_SCENARIO, HARTWELL_COLLECTION_SCENARIO,
    HARTWELL_PROPOSAL_SCENARIO, JORDAN_PARK_STAFFING_SCENARIO, MERIDIAN_BILLING_SCENARIO,
    TERRALOGIC_PAYMENT_SCENARIO, DecisionOutcome,
)
from models.context_object import (
    ContextObject, ContentType, DecayFunction, ProvenanceLink, SourceType,
)
from simulation.clock import SimulationClock
from simulation.mechanistic import (
    Guidance, MechanisticConfig, MechanisticDecisionModel, guidance, relevance, scenario_terms,
)


ALL_SCENARIOS = [
    BRIGHTLINE_SOW_SCENARIO, JORDAN_PARK_STAFFING_SCENARIO, TERRALOGIC_PAYMENT_SCENARIO,
    HARTWELL_PROPOSAL_SCENARIO, MERIDIAN_BILLING_SCENARIO, BRIGHTLINE_STAFFING_SCENARIO,
    HARTWELL_COLLECTION_SCENARIO,
]

# No retrieval or interpretation noise, so ranking alone decides the outcome
NOISELESS = MechanisticConfig(retrieval_recall=1.0, interpretation_accuracy=1.0, base_success_rate=0.0)


@pytest.fixture
def seeded_bank() -> ContextBank:
    bank = ContextBank()
    for obj in SEEDED_CONTEXT_OBJECTS:
        bank.deposit(copy.deepcopy(obj), check_contradictions=False)
    bank.current_week = 6
    return bank


def _contradiction(original_id: str, workflow_id: str, payload: str) -> ContextObject:
    return ContextObject(
        created_by="compliance_update_2025",
        source_type=SourceType.human,
        workflow_id=workflow_id,
        week=5,
        content_type=ContentType.policy,
        payload=payload,
        structured_data={"is_chaos_injection": True, "contradicts": original_id},
        decay_function=DecayFunction.linear,
        decay_rate=0.08,
        confidence_at_creation=0.85,
    )


class TestRelevanceAndGuidance:
    """Shared relevance function and guidance labels."""

    @pytest.mark.parametrize("scenario", ALL_SCENARIOS, ids=lambda s: s.scenario_type)
    def test_ground_truth_is_relevant_to_its_scenario(self, scenario):
        names, topics = scenario_terms(scenario.entities)
        for ctx_id in scenario.ground_truth_context_ids:
            obj = next(o for o in SEEDED_CONTEXT_OBJECTS if o.id == ctx_id)
            assert relevance(obj, names, topics) > 0

    def test_ground_truth_guidance_is_correct(self):
        obj = next(o for o in SEEDED_CONTEXT_OBJECTS if o.id == "CTX-001")
        assert guidance(obj, ["CTX-001"]) == Guidance.CORRECT
        assert guidance(obj, ["CTX-006"]) == Guidance.NEUTRAL

    def test_contradiction_guidance_is_wrong(self):
        obj = _contradiction("CTX-001", "W4", "Brightline Consulting cleared for standard SOW process.")
        assert guidance(obj, ["CTX-001"]) == Guidance.WRONG

    def test_decision_record_guidance_follows_outcome(self):
        def record(correct: bool) -> ContextObject:
            return ContextObject(
                created_by="vendor_agent", source_type=SourceType.agent, workflow_id="W4",
                week=3, content_type=ContentType.decision, payload="Brightline Consulting SOW",
                structured_data={"supports_context_id": "CTX-001", "decision_correct": correct},
                decay_function=DecayFunction.exponential, confidence_at_creation=0.6,
            )
        assert guidance(record(True), ["CTX-001"]) == Guidance.CORRECT
        assert guidance(record(False), ["CTX-001"]) == Guidance.WRONG

    def test_synthesized_object_inherits_majority_guidance(self, seeded_bank):
        wrong = _contradiction("CTX-001", "W4", "Brightline cleared.")
        seeded_bank.deposit(wrong, check_contradictions=False)
        crystal = ContextObject(
            created_by="synthesis_engine", source_type=SourceType.derived, workflow_id="W4",
            week=6, content_type=ContentType.inference, payload="Brightline pattern",
            decay_function=DecayFunction.exponential, confidence_at_creation=0.8,
            derivation_chain=[
                ProvenanceLink(source_id="CTX-001", relationship="derived_from"),
                ProvenanceLink(source_id=wrong.id, relationship="derived_from"),
                ProvenanceLink(source_id=wrong.id, relationship="derived_from"),
            ],
        )
        # Duplicate links count once, so this is a 1-1 tie
        assert guidance(crystal, ["CTX-001"], seeded_bank) == Guidance.NEUTRAL
        crystal.derivation_chain = crystal.derivation_chain[:1]
        assert guidance(crystal, ["CTX-001"], seeded_bank) == Guidance.CORRECT


class TestConditionRanking:
    """Conditions differ only in how they rank and what they can see."""

    def _decide(self, condition, bank, scenario=BRIGHTLINE_SOW_SCENARIO, agent="vendor_agent"):
        model = MechanisticDecisionModel(condition, seed=1, config=NOISELESS)
        return model.decide(agent, scenario, week=bank.current_week, context_bank=bank)

    def test_global_rag_follows_more_relevant_contradiction(self, seeded_bank):
        # The contradiction names the vendor twice, so it outranks CTX-001 on relevance
        seeded_bank.deposit(_contradiction(
            "CTX-001", "W4",
            "Brightline Consulting cleared: Brightline Consulting now uses the standard SOW process.",
        ), check_contradictions=False)
        seeded_bank.get("CTX-001").record_validation("vendor_agent", validated=True)

        rag = self._decide(RunCondition.GLOBAL_RAG, seeded_bank)
        assert rag.outcome == DecisionOutcome.INCORRECT

    def test_context_bank_prefers_validated_policy(self, seeded_bank):
        contradiction = _contradiction(
            "CTX-001", "W4",
            "Brightline Consulting cleared: Brightline Consulting now uses the standard SOW process.",
        )
        seeded_bank.deposit(contradiction, check_contradictions=False)
        contradiction.record_validation("vendor_agent", validated=False)
        for _ in range(3):
            seeded_bank.get("CTX-001").record_validation("vendor_agent", validated=True)

        bank = self._decide(RunCondition.CONTEXT_BANK, seeded_bank)
        assert bank.outcome == DecisionOutcome.CORRECT
        assert bank.context_used == ["CTX-001"]

    def test_siloed_typical_never_retrieves(self, seeded_bank):
        decision = self._decide(RunCondition.SILOED_TYPICAL, seeded_bank)
        assert decision.context_retrieved == []
        assert decision.outcome == DecisionOutcome.INCORRECT  # base rate is 0 here

    def test_siloed_advanced_cannot_see_distant_department(self, seeded_bank):
        # Staffing (Resource Management) is not adjacent to Vendor & Procurement,
        # where CTX-001 lives
        decision = self._decide(
            RunCondition.SILOED_ADVANCED, seeded_bank,
            scenario=BRIGHTLINE_STAFFING_SCENARIO, agent="staffing_agent",
        )
        assert "CTX-001" not in decision.context_retrieved

    def test_only_context_bank_records_outcome_feedback(self, seeded_bank):
        for condition in (RunCondition.GLOBAL_RAG, RunCondition.CONTEXT_BANK):
            bank = copy.deepcopy(seeded_bank)
            self._decide(condition, bank)
            validations = len(bank.get("CTX-001").validated_by)
            assert validations == (1 if condition == RunCondition.CONTEXT_BANK else 0)


class TestMechanisticSimulation:
    """End-to-end runs through the simulation clock."""

    def _accuracy(self, condition, seed):
        clock = SimulationClock(condition, seed=seed, decision_mode="mechanistic")
        for week in range(1, 13):
            clock.run_week(week)
        return clock.get_summary()["overall_accuracy"], [d.outcome for d in clock.all_decisions]

    def test_same_seed_reproduces(self):
        assert self._accuracy(RunCondition.CONTEXT_BANK, 7) == self._accuracy(RunCondition.CONTEXT_BANK, 7)

    def test_results_vary_with_seed(self):
        outcomes = {tuple(self._accuracy(RunCondition.GLOBAL_RAG, s)[1]) for s in range(42, 52)}
        assert len(outcomes) > 1

    def test_invalid_mode_rejected(self):
        with pytest.raises(ValueError):
            SimulationClock(RunCondition.CONTEXT_BANK, decision_mode="bogus")


class TestReviewRegressions:
    """Regressions for bugs found in review."""

    def test_unfollowed_wrong_guidance_gets_no_credit(self, seeded_bank):
        # Wrong guidance the agent never follows (interpretation accuracy 0) must
        # not be validated by a lucky standard-process outcome (base rate 1)
        seeded_bank.deposit(_contradiction(
            "CTX-001", "W4",
            "Brightline Consulting cleared: Brightline Consulting now uses the standard SOW process.",
        ), check_contradictions=False)
        # Hide the ground truth below the bank's confidence floor
        seeded_bank.get("CTX-001").decay_function = DecayFunction.linear
        seeded_bank.get("CTX-001").decay_rate = 1.0
        cfg = MechanisticConfig(retrieval_recall=1.0, interpretation_accuracy=0.0, base_success_rate=1.0)
        model = MechanisticDecisionModel(RunCondition.CONTEXT_BANK, seed=1, config=cfg)

        decision = model.decide("vendor_agent", BRIGHTLINE_SOW_SCENARIO, week=6, context_bank=seeded_bank)

        assert decision.outcome == DecisionOutcome.CORRECT
        assert decision.outcome_notes == "standard process"
        assert decision.context_used == []
        assert all(not o.validated_by for o in seeded_bank.get_all())

    def test_seed_zero_is_not_replaced_by_default(self):
        assert SimulationClock(RunCondition.CONTEXT_BANK, seed=0).seed == 0

    def test_consecutive_seeds_do_not_share_weeks(self):
        def week_events(seed, week):
            clock = SimulationClock(RunCondition.SILOED_TYPICAL, seed=seed)
            snapshot = clock.run_week(week)
            return [e.raw_content for e in snapshot.behavioral_events if e.raw_content]

        assert week_events(43, 1) != week_events(42, 2)

    def test_workload_surge_lasts_one_week(self):
        from calibration.realism_config import CHAOS_ENABLED_CONFIG

        realism = copy.deepcopy(CHAOS_ENABLED_CONFIG)  # the test edits the schedule
        clock = SimulationClock(RunCondition.SILOED_TYPICAL, seed=42, realism_config=realism)
        surge_week = realism.chaos.workload_surge.surge_weeks[0]
        for week in range(1, surge_week + 1):
            clock.run_week(week)
        assert clock.chaos_engine.get_event_multiplier() > 1.0

        clock.chaos_engine.config.random_chaos_probability = 0.0
        clock.chaos_engine.config.knowledge_departure.departure_weeks = []
        clock.chaos_engine.config.policy_contradiction.contradiction_scenarios = []
        clock.chaos_engine.config.agent_drift.drift_start_weeks = []
        clock.run_week(surge_week + 1)  # a week with no chaos events at all
        assert clock.chaos_engine.get_event_multiplier() == 1.0


class TestOutcomeAttribution:
    """
    The Context Bank credits or blames a record only when the action taken is
    the one the record recommends; when the agent departs from the advice, the
    error is the agent's and the record is left alone.
    """

    CONTRADICTION = "Brightline Consulting cleared: Brightline Consulting now uses the standard SOW process."

    def _bank_with_contradiction_on_top(self, bank):
        """Make the false policy the consulted record by hiding CTX-001."""
        contradiction = _contradiction("CTX-001", "W4", self.CONTRADICTION)
        bank.deposit(contradiction, check_contradictions=False)
        truth = bank.get("CTX-001")
        truth.decay_function = DecayFunction.linear
        truth.decay_rate = 1.0  # below the bank's confidence floor by week 6
        return contradiction

    def _decide(self, bank, condition=RunCondition.CONTEXT_BANK, **cfg):
        config = MechanisticConfig(retrieval_recall=1.0, **cfg)
        model = MechanisticDecisionModel(condition, seed=1, config=config)
        return model.decide("vendor_agent", BRIGHTLINE_SOW_SCENARIO, week=6, context_bank=bank)

    @staticmethod
    def _untouched(obj):
        return not obj.validated_by and not obj.invalidated_by and not obj.acted_on_by

    def test_followed_correct_advice_credits_record(self, seeded_bank):
        decision = self._decide(seeded_bank, interpretation_accuracy=1.0)
        truth = seeded_bank.get("CTX-001")

        assert decision.outcome == DecisionOutcome.CORRECT
        assert decision.context_used == ["CTX-001"]
        assert len(truth.validated_by) == 1 and not truth.invalidated_by
        assert [a.outcome for a in truth.acted_on_by] == ["correct"]

    def test_misapplied_correct_advice_does_not_blame_record(self, seeded_bank):
        decision = self._decide(seeded_bank, interpretation_accuracy=0.0)

        assert decision.outcome == DecisionOutcome.INCORRECT
        assert decision.outcome_notes == "misapplied correct guidance"
        assert decision.context_used == ["CTX-001"]  # engaged with it, badly
        assert "deviated from CTX-001" in decision.reasoning
        assert self._untouched(seeded_bank.get("CTX-001"))

    def test_followed_wrong_advice_blames_record(self, seeded_bank):
        contradiction = self._bank_with_contradiction_on_top(seeded_bank)
        decision = self._decide(seeded_bank, interpretation_accuracy=1.0)

        assert decision.outcome_notes == "followed wrong guidance"
        assert decision.context_used == [contradiction.id]
        assert len(contradiction.invalidated_by) == 1 and not contradiction.validated_by
        assert [a.outcome for a in contradiction.acted_on_by] == ["incorrect"]

    def test_rejected_wrong_advice_then_right_action_leaves_record_alone(self, seeded_bank):
        contradiction = self._bank_with_contradiction_on_top(seeded_bank)
        decision = self._decide(seeded_bank, interpretation_accuracy=0.0, base_success_rate=1.0)

        assert decision.outcome == DecisionOutcome.CORRECT
        assert self._untouched(contradiction)

    def test_standard_action_matching_wrong_advice_blames_record(self, seeded_bank):
        # The agent did not rely on the false policy, but the action it took is
        # the one that policy recommends, and an observer cannot tell the two
        # apart; the bad outcome counts against the policy
        contradiction = self._bank_with_contradiction_on_top(seeded_bank)
        decision = self._decide(seeded_bank, interpretation_accuracy=0.0, base_success_rate=0.0)

        assert decision.outcome_notes == "standard process"
        assert decision.context_used == []
        assert len(contradiction.invalidated_by) == 1

    def test_decision_record_carries_its_outcome(self, seeded_bank):
        decision = self._decide(seeded_bank, interpretation_accuracy=0.0)
        record = decision.deposited_context

        assert record.structured_data["decision_correct"] is False
        assert len(record.invalidated_by) == 1 and not record.validated_by

    @pytest.mark.parametrize("condition", [
        RunCondition.SILOED_ADVANCED, RunCondition.GLOBAL_RAG,
    ])
    def test_other_conditions_record_no_feedback(self, seeded_bank, condition):
        decision = self._decide(seeded_bank, condition=condition, interpretation_accuracy=1.0)

        assert all(self._untouched(o) for o in seeded_bank.get_all())
        assert self._untouched(decision.deposited_context)

    def test_validation_switch_disables_all_feedback(self, seeded_bank):
        decision = self._decide(seeded_bank, interpretation_accuracy=1.0, use_validation=False)

        assert all(self._untouched(o) for o in seeded_bank.get_all())
        assert self._untouched(decision.deposited_context)

    def test_followed_actions_reach_validation_propagation(self, seeded_bank):
        from bank.synthesis import run_synthesis_pass

        truth = seeded_bank.get("CTX-001")
        truth.confidence_at_creation = 0.6  # room below propagation's 0.95 cap
        self._decide(seeded_bank, interpretation_accuracy=1.0)
        run_synthesis_pass(seeded_bank, 6)

        assert truth.confidence_at_creation > 0.6

    def test_deviations_do_not_reach_validation_propagation(self, seeded_bank):
        from bank.synthesis import run_synthesis_pass

        truth = seeded_bank.get("CTX-001")
        truth.confidence_at_creation = 0.6  # room below propagation's 0.95 cap
        self._decide(seeded_bank, interpretation_accuracy=0.0)
        run_synthesis_pass(seeded_bank, 6)

        assert truth.confidence_at_creation == 0.6


class TestCrossProcessReproducibility:
    """Same seeds must give the same results in every process."""

    SCRIPT = (
        "from simulation.clock import SimulationClock\n"
        "from config.simulation_config import RunCondition\n"
        "from calibration.realism_config import FULL_REALISM_CONFIG\n"
        "out = []\n"
        "for seed in range(42, 62):\n"
        "    clock = SimulationClock(RunCondition.CONTEXT_BANK, seed=seed,\n"
        "                            realism_config=FULL_REALISM_CONFIG, decision_mode='mechanistic')\n"
        "    for week in range(1, 13):\n"
        "        clock.run_week(week)\n"
        "    out.append(clock.get_summary()['overall_accuracy'])\n"
        "print(out)\n"
    )

    def _run(self, hash_seed: str) -> str:
        import os
        import subprocess
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        env = {**os.environ, "PYTHONHASHSEED": hash_seed, "PYTHONPATH": str(root)}
        result = subprocess.run(
            [sys.executable, "-c", self.SCRIPT], cwd=root, env=env,
            capture_output=True, text=True, check=True,
        )
        return result.stdout

    def test_results_do_not_depend_on_string_hashing(self):
        # Hash seeds 1 and 3 gave different results before synthesis iterated
        # entities in sorted order
        assert self._run("1") == self._run("3")
