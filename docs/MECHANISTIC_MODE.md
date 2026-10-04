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
| GLOBAL_RAG | 70.1% [67.5, 72.8] | 85.3% [82.5, 88.1] |
| CONTEXT_BANK | 75.8% [73.7, 77.9] | 88.3% [86.6, 89.9] |

Paired difference CONTEXT_BANK minus GLOBAL_RAG:

- **With chaos: +5.7 points [+2.5, +8.8]** (wins/ties/losses 56/13/31).
- **Without chaos: +3.0 points [-0.1, +6.1]** (42/18/40), not statistically
  distinguishable from zero.

The bank's advantage is a chaos-resilience effect: it matters when the record
contains misleading information. CONTEXT_BANK is also the most consistent
condition (std 10.4 vs 13.2 under chaos, 8.2 vs 14.0 without).

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
| GLOBAL_RAG | 68% | 7% | 8% | 18% |
| CONTEXT_BANK | 73% | 1% | 10% | 15% |

The bank wins by not acting on wrong guidance: injected contradictions and
records of past mistakes.

Ablation (CONTEXT_BANK minus GLOBAL_RAG, points, 95% CI):

| Bank features | Chaos | No chaos |
|---|---|---|
| All | +5.7 [+2.5, +8.8] | +3.0 [-0.1, +6.1] |
| Without confidence filtering | +4.1 [+0.8, +7.4] | +1.3 [-1.8, +4.4] |
| Without validation | +6.7 [+3.3, +10.0] | +3.6 [+0.6, +6.6] |
| Without supersession | +5.7 (never triggers) | +3.0 |
| None (synthesis only) | +1.3 [-2.0, +4.5] | -0.2 [-3.5, +3.1] |

Confidence filtering carries most of the effect. Validation, as modeled, is
slightly harmful: outcome feedback also discredits correct knowledge whenever
the agent misapplies it, and that cost outweighs what it adds once confidence
filtering is already catching most wrong guidance. Supersession never triggers.
The "complete stack" claim is not supported: one primitive does most of the work.

## Sensitivity

With chaos, CONTEXT_BANK minus GLOBAL_RAG stays between +4.5 and +5.8 points,
every 95% interval above zero, when varying base rate (0.10-0.40), recall
(0.70-0.95), interpretation accuracy (0.80-0.90) and top-k (3-10). Without
chaos it ranges +2.6 to +4.4, and about half the intervals include zero.

## Review fixes (October 2026)

A hostile review found and fixed issues that inflated the first published
version of these numbers (bank minus RAG was +6.7 with chaos, +5.1 without):

- Consecutive run seeds reused each other's weeks (seed + week), so the 100 runs
  were not independent and the intervals were too narrow. Weekly seeds are now
  seed * 1000 + week.
- The bank credited or blamed wrong guidance the agent had not followed.
- A workload surge persisted until the next week with any chaos event.
- Seed 0 was silently replaced by 42.

Calibrated-mode results are unchanged by these fixes.

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
- **Workload overload errors are not applied.** The chaos config defines an
  error increase during surges, but no agent ever reads it (in either mode).
  It would apply equally to all conditions.
