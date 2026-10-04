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

### Outcome feedback (CONTEXT_BANK only)

After each decision the outcome is known. The bank attributes it using only
what an observer could see: whether the action taken is the one the consulted
record recommends (read from the record's advice, not its truth).

| What happened | Record | Logged as an action |
|---|---|---|
| Agent followed the record's advice | credited if right, blamed if wrong | yes (feeds validation propagation) |
| Agent departed from the advice (e.g. misapplied correct knowledge) | left alone; the error is the agent's | no |
| Agent rejected wrong advice but took the action it recommends anyway | blamed (indistinguishable from following it) | yes |

The bank also stores each decision as a record, marked with its outcome.
Credited and blamed counts scale a record's ranking by 2(v+1)/(v+i+2): 1.0
with no history, higher when credited, lower when blamed. Every third week
synthesis boosts the confidence of records followed to correct outcomes, and of
their sources (validation propagation), and slows decay for frequently used
records.

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
| CONTEXT_BANK | 75.7% [73.7, 77.6] | 88.5% [86.8, 90.2] |

Paired difference CONTEXT_BANK minus GLOBAL_RAG:

- **With chaos: +5.5 points [+2.5, +8.6]** (wins/ties/losses 59/12/29).
- **Without chaos: +3.3 points [+0.1, +6.5]** (43/17/40), barely
  distinguishable from zero.

The advantage is larger when the record contains misleading information, which
is the realistic case. CONTEXT_BANK is also the most consistent condition
(std 9.9 vs 13.2 under chaos, 8.5 vs 14.0 without).

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
| CONTEXT_BANK | 73% | 1% | 10% | 16% |

The bank wins by not acting on wrong guidance: injected contradictions and
records of past mistakes.

Ablation (CONTEXT_BANK minus GLOBAL_RAG, points, 95% CI):

| Bank features | Chaos | No chaos |
|---|---|---|
| All | +5.5 [+2.5, +8.6] | +3.3 [+0.1, +6.4] |
| Without confidence filtering | +5.3 [+2.1, +8.6] | +1.9 [-1.1, +5.0] |
| Without validation (and propagation) | +6.7 [+3.4, +10.0] | +3.5 [+0.5, +6.5] |
| Without supersession | +5.5 (never triggers) | +3.3 |
| None (synthesis only) | +1.4 [-1.9, +4.7] | -0.3 [-3.6, +3.1] |

Compared directly (same seeds, 300 of them), the bank with and without
validation differs by -0.53 points [-1.40, +0.33] with chaos and -0.29
[-0.95, +0.37] without: **validation has no measurable effect**. Turning off
only validation propagation gives +6.0 with chaos, also within noise of the
full bank.

Confidence filtering and validation each catch most wrong guidance, so either
alone recovers most of the advantage; removing both erases it. Supersession
never triggers. The "complete stack" claim is not supported: the features are
largely redundant here, not jointly necessary.

Before outcome attribution was fixed (see Review fixes), validation was
measurably harmful under chaos (-0.91 [-1.79, -0.04] over 300 seeds, measured
before the reproducibility fix, so the exact figure can vary between runs),
because the bank blamed correct knowledge whenever the agent misapplied it. Validation
is only safe if it separates "the knowledge was wrong" from "the agent did not
follow it". That is a design requirement for any real implementation.

## Sensitivity

CONTEXT_BANK minus GLOBAL_RAG, varying base rate (0.10-0.40), recall
(0.70-0.95), interpretation accuracy (0.80-0.90) and top-k (3-10):

- With chaos: +5.1 to +6.4 points, every 95% interval above zero.
- Without chaos: +2.7 to +4.7 points; two of seven intervals include zero.

## Review fixes (October 2026)

Bank minus RAG across versions: first version +6.7 (chaos) / +5.1 (no chaos);
after the first review +5.7 / +3.0; final +5.5 / +3.3.

First review:

- Consecutive run seeds reused each other's weeks (seed + week), so the 100 runs
  were not independent and the intervals were too narrow. Weekly seeds are now
  seed * 1000 + week.
- The bank credited or blamed wrong guidance the agent had not followed.
- A workload surge persisted until the next week with any chaos event.
- Seed 0 was silently replaced by 42.

Outcome attribution:

- The bank blamed correct knowledge when the agent misapplied it. Feedback is
  now attributed by whether the action matched the record's advice.
- The bank's validation propagation (synthesis) never ran in this mode, because
  no agent actions were logged. Followed actions are now logged.
- Results were not reproducible between processes: synthesis iterated a set of
  entity names, whose order depends on Python's per-process string hashing, so
  the same seed could give different CONTEXT_BANK results on different runs.
  It now iterates in sorted order; all three result sets are identical across
  hash seeds, and a test runs two processes with different hash seeds.

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
- **Feedback is immediate and always observed.** Real outcomes arrive late and
  sometimes never.
- **Validation propagation compounds.** Each synthesis pass re-adds a boost for
  all past correct actions (capped at 0.95), and incorrect actions never reduce
  confidence through this path. This is the bank's existing design; it has no
  measurable effect on these results.
- **Workload overload errors are not applied.** The chaos config defines an
  error increase during surges, but no agent ever reads it (in either mode).
  It would apply equally to all conditions.
