"""
Run simulation WITH Context Bank.

Agents have access to the Context Bank containing seeded institutional
memory. They retrieve relevant context before making decisions and
deposit learnings back into the bank.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from config.simulation_config import SIMULATION_CONFIG, RunCondition
from simulation.clock import SimulationClock, WeeklySnapshot


def run_with_bank(
    output_dir: str = "results",
    save_intermediate: bool = True,
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    Run the full 12-week simulation with the Context Bank.

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
        print("ACME ADVISORY SIMULATION - WITH CONTEXT BANK")
        print("=" * 60)
        print(f"Running {SIMULATION_CONFIG.weeks} weeks")
        print("Agents have access to institutional memory")
        print("Starting with 12 seeded context objects")
        print("-" * 60)

    # Initialize simulation
    clock = SimulationClock(RunCondition.WITH_BANK)

    # Run each week
    snapshots: List[WeeklySnapshot] = []
    for week in range(1, SIMULATION_CONFIG.weeks + 1):
        snapshot = clock.run_week(week)
        snapshots.append(snapshot)

        if verbose:
            decisions = len(snapshot.agent_decisions)
            errors = snapshot.organizational_error_count
            bank_size = snapshot.bank_snapshot.total_objects if snapshot.bank_snapshot else 0
            new_ctx = len(snapshot.new_context_objects)

            print(f"Week {week:2d}: {decisions} decisions, {errors} errors, "
                  f"bank={bank_size} (+{new_ctx})")

            # Show decision details
            for d in snapshot.agent_decisions:
                status = "✓" if d.outcome.value == "correct" else "✗"
                ctx_info = f" (used: {d.context_used})" if d.context_used else ""
                print(f"         {status} {d.scenario_type}: {d.outcome.value}{ctx_info}")

    # Get summary
    summary = clock.get_summary()
    summary["run_timestamp"] = datetime.now(timezone.utc).isoformat()

    if verbose:
        print("-" * 60)
        print(f"COMPLETED: {summary['total_decisions']} total decisions")
        print(f"  Correct: {summary['correct_decisions']}")
        print(f"  Incorrect: {summary['incorrect_decisions']}")
        print(f"  Accuracy: {summary['overall_accuracy']:.1f}%")
        print(f"  Final bank size: {summary['final_bank_size']}")
        print(f"  Final avg confidence: {summary['final_avg_confidence']:.2f}")

    # Save results
    if save_intermediate:
        # Save summary
        summary_file = output_path / "with_bank_summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2, default=str)

        # Save weekly snapshots
        snapshots_data = [s.to_dict() for s in snapshots]
        snapshots_file = output_path / "with_bank_snapshots.json"
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
        decisions_file = output_path / "with_bank_decisions.json"
        with open(decisions_file, "w") as f:
            json.dump(decisions_data, f, indent=2)

        # Save final bank state
        if clock.bank is not None:
            bank_data = clock.bank.export_to_dict()
            bank_file = output_path / "with_bank_context_objects.json"
            with open(bank_file, "w") as f:
                json.dump(bank_data, f, indent=2, default=str)

        if verbose:
            print(f"\nResults saved to: {output_path}")

    return summary


if __name__ == "__main__":
    summary = run_with_bank(verbose=True)
