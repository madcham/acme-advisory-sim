"""
Summary Generation for Simulation Results.

Writes a factual markdown summary of a single run: accuracy per condition,
signed differences, and outcomes per scenario type. It states the decision mode
and the sample size, and makes no claims the data does not show.

A single run has 15 decisions per condition, so one decision moves accuracy by
about 6.7 points. Comparisons belong to run_multi_seed.py.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

MODE_NOTES = {
    "calibrated": (
        "**Calibrated mode.** Each decision succeeds when a random draw falls below "
        "the condition's accuracy as set in `config/simulation_config.py` "
        "(`PerformanceCalibration`); retrieved context does not affect outcomes. "
        "These numbers restate that configuration and are not evidence about the "
        "Context Bank."
    ),
    "mechanistic": (
        "**Mechanistic mode.** Each outcome follows from what the agent retrieved "
        "(`simulation/mechanistic.py`, `docs/MECHANISTIC_MODE.md`)."
    ),
}


def _scenario_table(decisions: Dict[str, List[Any]], names: List[str]) -> str:
    """Correct decisions out of total, per scenario type and condition."""
    scenario_types: List[str] = []
    for name in names:
        for d in decisions.get(name, []):
            if d.scenario_type not in scenario_types:
                scenario_types.append(d.scenario_type)
    if not scenario_types:
        return "_No decisions recorded._"

    rows = ["| Scenario | " + " | ".join(names) + " |",
            "|---|" + "---|" * len(names)]
    for scenario in scenario_types:
        cells = []
        for name in names:
            these = [d for d in decisions.get(name, []) if d.scenario_type == scenario]
            correct = sum(1 for d in these if d.outcome.value == "correct")
            cells.append(f"{correct}/{len(these)}")
        rows.append(f"| {scenario} | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def generate_summary_markdown(
    summaries: Dict[str, Dict[str, Any]],
    output_path: str = "results/summary.md",
    decisions: Optional[Dict[str, List[Any]]] = None,
    decision_mode: str = "calibrated",
    headline: Optional[tuple] = None,
    seed: Optional[int] = None,
    realism_mode: Optional[str] = None,
) -> str:
    """
    Write a factual summary of one run.

    Args:
        summaries: Condition name -> SimulationClock.get_summary() output
        output_path: Where to save the markdown file
        decisions: Condition name -> list of AgentDecision, for the scenario table
        decision_mode: "calibrated" or "mechanistic"
        headline: (condition, reference) pair whose difference is shown first
        seed: Run seed, for the header
        realism_mode: Realism description, for the header

    Returns:
        Path to the generated markdown file
    """
    names = list(summaries)
    n_decisions = max((s.get("total_decisions", 0) for s in summaries.values()), default=0)
    step = 100 / n_decisions if n_decisions else 0

    lines = [
        "# Acme Advisory: Single-Run Summary",
        "",
        f"*Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*  ",
        f"*Seed: {seed if seed is not None else 'default'} · Realism: {realism_mode or 'Standard'} "
        f"· Decision mode: {decision_mode}*",
        "",
        MODE_NOTES.get(decision_mode, ""),
        "",
        f"**Sample size.** {n_decisions} decisions per condition, so one decision moves "
        f"accuracy by {step:.1f} points. A single run cannot show a difference between "
        "conditions; use `run_multi_seed.py` (current results: `results/mechanistic/`).",
        "",
        "## Accuracy by condition",
        "",
        "| Condition | Correct | Incorrect | Accuracy |",
        "|---|---|---|---|",
    ]
    for name, s in summaries.items():
        lines.append(
            f"| {name} | {s.get('correct_decisions', 0)} | {s.get('incorrect_decisions', 0)} "
            f"| {s.get('overall_accuracy', 0):.1f}% |"
        )

    if headline and all(c in summaries for c in headline):
        a, b = headline
        diff = summaries[a].get("overall_accuracy", 0) - summaries[b].get("overall_accuracy", 0)
        lines += ["", f"**{a} minus {b}: {diff:+.1f} points** in this run."]

    if decisions:
        lines += ["", "## Correct decisions by scenario", "", _scenario_table(decisions, names)]

    bank_rows = [
        (name, s) for name, s in summaries.items() if s.get("final_bank_size")
    ]
    if bank_rows:
        lines += ["", "## Context store at week 12", "",
                  "| Condition | Objects | Average confidence |", "|---|---|---|"]
        for name, s in bank_rows:
            lines.append(f"| {name} | {s['final_bank_size']} | {s.get('final_avg_confidence', 0):.2f} |")

    lines += [
        "",
        "---",
        "",
        "*Acme Advisory is a fictional organization; all scenarios are synthetic.*",
        "",
    ]

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines))
    return str(output)


class SummaryGenerator:
    """Writes the single-run summary markdown."""

    def __init__(self, output_dir: str = "results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        summaries: Dict[str, Dict[str, Any]],
        decisions: Optional[Dict[str, List[Any]]] = None,
        decision_mode: str = "calibrated",
        headline: Optional[tuple] = None,
        seed: Optional[int] = None,
        realism_mode: Optional[str] = None,
    ) -> str:
        """Generate the summary; returns the path to the generated file."""
        return generate_summary_markdown(
            summaries,
            str(self.output_dir / "summary.md"),
            decisions=decisions,
            decision_mode=decision_mode,
            headline=headline,
            seed=seed,
            realism_mode=realism_mode,
        )
