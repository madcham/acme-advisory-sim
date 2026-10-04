# Legacy calibrated-mode outputs (not supported findings)

These files are single runs (15 decisions per condition, or 9 in the oldest
2-way run) from the original **calibrated mode**, generated in May 2026.

In calibrated mode each decision succeeds when a random draw falls below the
condition's accuracy as **set in `config/simulation_config.py`**; retrieved
context does not affect outcomes. The accuracies here therefore restate that
configuration. Claims in these files, including 44% to 78% accuracy, the Context
Bank at 80%, a 46-point "partial sophistication trap" and the narrative in
`summary.md`, are **not supported** and the current code does not reproduce them
exactly.

They are kept for reference because they back earlier public claims, made in
["The Partial Sophistication Trap"](https://andsnotors.substack.com/p/the-partial-sophistication-trap-what)
(May 2026) and corrected in
["I Stress-Tested My Own Simulation"](https://andsnotors.substack.com/p/i-stress-tested-my-own-simulation)
(October 2026). For current
results, see `../mechanistic/`, `../mechanistic_no_chaos/` and
`docs/MECHANISTIC_MODE.md`.
