# Acme Advisory: Context Bank Simulation

A simulation that tests whether a **Context Bank** (shared institutional memory
whose records carry confidence, decay, provenance and validation) helps AI agents
make better organizational decisions than siloed or plain retrieval-augmented
(RAG) approaches.

The simulated organization is Acme Advisory, a fictional 90-person consulting
firm. Over 12 weeks, four agents (procurement, staffing, proposals, billing)
face 15 decisions where institutional memory matters: for example, Brightline
Consulting SOWs need secondary approval from the Finance head because of a past
billing dispute, a fact recorded nowhere official.

**Background:** the original results were published in
["The Partial Sophistication Trap"](https://andsnotors.substack.com/p/the-partial-sophistication-trap-what)
(May 2026) and corrected in
["I Stress-Tested My Own Simulation"](https://andsnotors.substack.com/p/i-stress-tested-my-own-simulation)
(October 2026). The correction explains what changed and why.

## Current findings

Use the **mechanistic mode** results. Full method, ablation, sensitivity and
limitations: [`docs/MECHANISTIC_MODE.md`](docs/MECHANISTIC_MODE.md).

100 seeds, mean decision accuracy with 95% confidence interval:

| Condition | With chaos | Without chaos |
|---|---|---|
| SILOED_TYPICAL (no retrieval) | 18.9% [17.0, 20.8] | 24.9% [22.7, 27.0] |
| SILOED_ADVANCED (own + adjacent departments) | 58.3% [55.8, 60.9] | 68.1% [65.6, 70.7] |
| GLOBAL_RAG (everything, relevance only) | 70.1% [67.5, 72.8] | 85.3% [82.5, 88.1] |
| CONTEXT_BANK (everything, with trust signals) | 75.7% [73.7, 77.6] | 88.5% [86.8, 90.2] |

- The Context Bank beats plain RAG by **+5.5 points [+2.5, +8.6]** when records
  contain misleading information (chaos), and by **+3.3 [+0.1, +6.5]** without.
- It wins by not acting on stale or contradicting records. Confidence filtering
  and outcome validation each recover most of that advantage; removing both
  erases it. The features are partly redundant, not jointly necessary.
- The "partial sophistication trap" (partial retrieval doing worse than none)
  does not appear.

These come from a small, hand-built world (7 scenario types, 15 decisions per
run). They show how the mechanisms behave under stated assumptions, not how a
real organization would fare.

### Earlier claims that are not supported

Earlier results (44% to 78% accuracy, CONTEXT_BANK at about 80-85%, a 46-point
"partial sophistication trap") came from the **calibrated mode**, where each
condition's accuracy is a number set in `config/simulation_config.py` and
retrieved context does not affect outcomes. Those results restate the
configuration; with equal settings, CONTEXT_BANK and GLOBAL_RAG score
identically. Files that still show them are listed under
[Results files](#results-files).

## Quick start

Requires Python 3.10+.

```bash
pip install -r requirements.txt        # pydantic, plotly, pytest are required

# Multi-seed comparison of all four conditions (the numbers above)
python run_multi_seed.py --mode mechanistic --n-seeds 100
python run_multi_seed.py --mode mechanistic --n-seeds 100 --no-chaos

# One run with per-decision output (15 decisions per condition: too few to compare)
python main.py --4-way --mode mechanistic --full-realism

# Tests
python -m pytest
```

Results are reproducible: the same seed gives the same result in any process.

## How it works

Each week the simulation generates workflow events and staff communications
("behavioral exhaust"), injects the scheduled decision scenarios, has agents
decide, and deposits what they did back into the store.

**Conditions** differ only in what an agent can see and how results are ranked:

| Condition | Can see | Ranking |
|---|---|---|
| SILOED_TYPICAL | nothing | no retrieval |
| SILOED_ADVANCED | own + adjacent departments | relevance x decayed confidence |
| GLOBAL_RAG | everything | relevance only |
| CONTEXT_BANK | everything, minus superseded and low-confidence records | relevance x confidence x validation record, plus outcome feedback and synthesis |

**Decision modes:**

- `mechanistic` (`simulation/mechanistic.py`): the agent acts on the top-ranked
  record that bears on the decision. True knowledge usually leads to the right
  call; false policies and records of past mistakes lead to the wrong one; with
  nothing usable the agent follows standard process. Relevance, noise, base
  rate and chaos effects are identical for every condition.
- `calibrated` (original, default for `main.py`): a decision succeeds when a
  random draw falls below the condition's configured accuracy. Kept for
  reference; do not use it to compare conditions.

**Chaos** (`--full-realism`, on by default in `run_multi_seed.py`) applies to
every condition: false policy updates, agent drift and workload surges. Staff
departures are scheduled but currently have no effect (see limitations in
`docs/MECHANISTIC_MODE.md`).

## Repository layout

| Path | Contents |
|---|---|
| `main.py` | Single-run entry point (2-way legacy or `--4-way`) |
| `run_multi_seed.py` | Multi-seed runs with confidence intervals and paired comparisons |
| `simulation/` | Weekly clock and the mechanistic decision model |
| `bank/` | Context Bank: storage, retrieval, contradiction detection, synthesis, deposit validation |
| `models/context_object.py` | The context object (confidence, decay, provenance, validation) |
| `generators/` | Workflow events, staff communications, scenarios and the calibrated agent |
| `calibration/` | Chaos engine, BPI process-timing calibration, Enron communication analysis |
| `config/` | Organization, departments, seeded institutional memory, calibrated accuracies |
| `measurement/` | Metrics |
| `results/` | Generated outputs (see below) |
| `app.py` | Streamlit explorer (`streamlit run app.py`): current results on top, legacy calibrated run in the tabs |
| `docs/` | Write-ups; start with `MECHANISTIC_MODE.md` |
| `tests/` | Test suite |

## Results files

| Path | What it is |
|---|---|
| `results/mechanistic/`, `results/mechanistic_no_chaos/` | **Current results** (100 seeds each) |
| `results/multi_seed/`, `results/multi_seed_no_chaos/` | Calibrated mode, 30 seeds: restates configured accuracies |
| `results/legacy_calibrated/` | Earlier single runs in calibrated mode, kept because they back earlier public claims; those claims are not supported (see its README) |

`python main.py` writes a single run's `summary.md`, dashboards and JSON into
`results/` (or `--output`). The summary states the decision mode and sample size
and shows all conditions; a single run is too small to compare conditions.

## Data sources

- **BPI Challenge** process logs (4TU.ResearchData), optional, for process timing
  (`--bpi`). Falls back to synthetic timing if the download fails.
- **CMU Enron email corpus**, optional. `calibration/enron_*.py` computes
  descriptive communication statistics from it (not included in the repo). These
  statistics are **not applied to the simulation**: no reported run uses them, and
  the behavioral generator ignores the calibrated rates. See the status note in
  `docs/ENRON_VALIDATION.md`.

Everything else, including the organization, people and scenarios, is fictional.
