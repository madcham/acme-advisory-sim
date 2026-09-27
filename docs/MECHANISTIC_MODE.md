# Mechanistic Decision Mode

## Why it exists

In the original (calibrated) model, each condition's accuracy is a number in
`config/simulation_config.py` (`PerformanceCalibration`), and a decision succeeds
when a random draw falls below it. Retrieved context only reaches the prompt of a
real API call, so without an API key it never affects an outcome. Giving all four
conditions the same calibration makes CONTEXT_BANK and GLOBAL_RAG score
identically on every seed: the confidence, decay, provenance and validation
features change what is stored, never what is decided.

Mechanistic mode (`simulation/mechanistic.py`) removes the per-condition accuracy
numbers. The outcome follows from what the agent actually retrieves.

## How a decision is made

1. The condition ranks the context objects it can see.
2. The agent acts on the highest-ranked result that bears on the decision.
   - Ground-truth knowledge (the seeded object, tribal-knowledge exchanges that
     restate it, records of past correct decisions) gives **correct** guidance.
   - Injected contradicting policies and records of past wrong decisions give
     **wrong** guidance.
   - Synthesized objects take the majority guidance of their sources.
3. With nothing usable, the agent follows standard process, which is right only
   at the base rate (the scenarios are all exceptions).

Shared by every condition: the relevance function, retrieval recall (0.85),
interpretation accuracy (0.90), base rate (0.25), top-k (5), and chaos effects on
agents (drift, context ignoring, workload). The conditions differ only in:

| Condition | Can see | Ranking |
|---|---|---|
| SILOED_TYPICAL | nothing (no retrieval) | none |
| SILOED_ADVANCED | own + adjacent departments' systems | relevance x decayed confidence |
| GLOBAL_RAG | everything | relevance only |
| CONTEXT_BANK | everything, minus superseded and confidence < 0.3 | relevance x decayed confidence x validation record; records outcome feedback; runs synthesis |

## Results (100 seeds, 12 weeks, 15 decisions per run)

Mean accuracy with 95% confidence interval:

| Condition | Chaos | No chaos |
|---|---|---|
| SILOED_TYPICAL | 18.9% [17.0, 20.8] | 24.9% [22.7, 27.0] |
| SILOED_ADVANCED | 58.3% [55.8, 60.9] | 68.1% [65.6, 70.7] |
| GLOBAL_RAG | 69.3% [66.3, 72.3] | 84.7% [82.2, 87.3] |
| CONTEXT_BANK | 76.0% [74.0, 78.0] | 89.9% [88.3, 91.4] |

Paired difference CONTEXT_BANK minus GLOBAL_RAG: **+6.7 points [+3.3, +10.1]**
with chaos (wins/ties/losses 60/15/25), **+5.1 [+2.2, +8.0]** without.
CONTEXT_BANK is also the most consistent condition (std 9.8 vs 15.0 under chaos).

SILOED_ADVANCED beats SILOED_TYPICAL on 100 of 100 seeds with chaos, so the
"partial sophistication trap" does not appear. In the calibrated model it came
from configured accuracies plus an extra retrieval penalty applied only to
conditions that retrieve.

Regenerate with:

```bash
python run_multi_seed.py --mode mechanistic --n-seeds 100
python run_multi_seed.py --mode mechanistic --n-seeds 100 --no-chaos
```

## Where the advantage comes from

Share of decisions by path (chaos):

| | Correct guidance | Wrong guidance | Misapplied | Standard process |
|---|---|---|---|---|
| SILOED_ADVANCED | 53% | 9% | 6% | 31% |
| GLOBAL_RAG | 67% | 8% | 9% | 16% |
| CONTEXT_BANK | 74% | 1% | 10% | 16% |

The bank wins by not acting on wrong guidance: injected contradictions and
records of its own past mistakes.

Ablation (CONTEXT_BANK minus GLOBAL_RAG, points):

| Bank features | Chaos | No chaos |
|---|---|---|
| All | +6.7 | +5.2 |
| Without confidence filtering | +7.3 | +2.5 |
| Without validation | +8.0 | +3.6 |
| Without supersession | +6.7 | +5.2 |
| None (synthesis only) | +3.7 [-0.1, +7.6] | +0.1 |

Confidence and validation each catch most wrong guidance, so removing either
alone costs little; removing both erases the advantage. Supersession never
triggers in these runs. Under chaos, validation slightly hurts on its own,
because feedback also blames correct knowledge when the agent misapplies it.

## Sensitivity

CONTEXT_BANK minus GLOBAL_RAG stays between +4.3 and +7.5 points, with every
95% interval above zero, when varying base rate (0.10-0.40), recall
(0.70-0.95), interpretation accuracy (0.80-0.90) and top-k (3-10), with and
without chaos.

## Limitations

- **Contradictions are always misinformation.** The injected policy changes
  are wrong by construction, so the runs test resistance to bad updates, not the
  ability to adopt a genuine policy change. A bank that trusts validated old
  knowledge could be slower to accept a real change; this is not yet tested.
- **Knowledge departure has no effect.** Seeded knowledge is created by
  `system`, not by the departing staff, and its step/permanent decay ignores
  the accelerated decay rate.
- **Hand-built world.** Seven scenario types, fifteen decisions per run, keyword
  relevance, and guidance labels defined by us. Results show how the mechanisms
  behave under these assumptions, not how a real organization would fare.
- **SILOED_TYPICAL's gap is definitional**: it never retrieves.
- **Siloed conditions do not index chat-derived knowledge** (objects with no
  workflow), a modeling choice that favors the global conditions.
- **Feedback is immediate** and assigns credit to whatever the agent acted on.
