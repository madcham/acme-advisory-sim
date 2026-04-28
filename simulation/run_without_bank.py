"""
Run simulation WITHOUT Context Bank.

Cold start agents with no memory. Each week's agents have no access
to institutional memory and make decisions based only on their
training and the immediate context provided.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from config.simulation_config import SIMULATION_CONFIG, RunCondition
from simulation.clock import SimulationClock, WeeklySnapshot


def run_without_bank(
    output_dir: str = "results",
    save_intermediate: bool = True,
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    Run the full 12-week simulation without the Context Bank.

    Args:
        output_dir: Directory for output files
        save_intermediate: Whether to save weekly snapshots
        verbose: Print progress updates

    Returns:
        Summary statistics dictionary
    """
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if verbose:
        print("=" * 60)
        print("ACME ADVISORY SIMULATION - WITHOUT CONTEXT BANK")
        print("=" * 60)
        print(f"Running {SIMULATION_CONFIG.weeks} weeks")
        print("Agents have NO access to institutional memory")
        print("-" * 60)

    # Initialize simulation
    clock = SimulationClock(RunCondition.WITHOUT_BANK)

    # Run each week
    snapshots: List[WeeklySnapshot] = []
    for week in range(1, SIMULATION_CONFIG.weeks + 1):
        snapshot = clock.run_week(week)
        snapshots.append(snapshot)

        if verbose:
            decisions = len(snapshot.agent_decisions)
            errors = snapshot.organizational_error_count
            print(f"Week {week:2d}: {decisions} decisions, {errors} errors")

            # Show decision details
            for d in snapshot.agent_decisions:
                status = "✓" if d.outcome.value == "correct" else "✗"
                print(f"         {status} {d.scenario_type}: {d.outcome.value}")

    # Get summary
    summary = clock.get_summary()
    summary["run_timestamp"] = datetime.now(timezone.utc).isoformat()

    if verbose:
        print("-" * 60)
        print(f"COMPLETED: {summary['total_decisions']} total decisions")
        print(f"  Correct: {summary['correct_decisions']}")
        print(f"  Incorrect: {summary['incorrect_decisions']}")
        print(f"  Accuracy: {summary['overall_accuracy']:.1f}%")

    # Save results
    if save_intermediate:
        # Save summary
        summary_file = output_path / "without_bank_summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2, default=str)

        # Save weekly snapshots
        snapshots_data = [s.to_dict() for s in snapshots]
        snapshots_file = output_path / "without_bank_snapshots.json"
        with open(snapshots_file, "w") as f:
            json.dump(snapshots_data, f, indent=2, default=str)

        # Save all decisions
        decisions_data = [
            {
                "decision_id": d.decision_id,
                "week": d.week,
                "agent_id": d.agent_id,
                "scenario_type": d.scenario_type,
                "decision_taken": d.decision_taken,
                "confidence": d.confidence,
                "outcome": d.outcome.value,
                "context_retrieved": d.context_retrieved,
                "context_used": d.context_used,
            }
            for d in clock.all_decisions
        ]
        decisions_file = output_path / "without_bank_decisions.json"
        with open(decisions_file, "w") as f:
            json.dump(decisions_data, f, indent=2)

        if verbose:
            print(f"\nResults saved to: {output_path}")

    return summary


if __name__ == "__main__":
    summary = run_without_bank(verbose=True)
