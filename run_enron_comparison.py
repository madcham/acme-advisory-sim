#!/usr/bin/env python3
"""
Single-run 4-condition comparison, optionally reporting Enron corpus statistics.

LIMITATIONS (read before using any output):
- Runs one seed in calibrated mode, where each condition's accuracy is set in
  config/simulation_config.py; the accuracies printed restate that config.
- The Enron calibration is computed but NOT applied: SimulationClock does not
  accept it, and the behavioral generator does not use the calibrated rates.
  Corpus statistics are descriptive only.

For comparisons, use run_multi_seed.py --mode mechanistic (docs/MECHANISTIC_MODE.md).
"""

import sys
from datetime import datetime, timezone
from typing import Dict, Any, List

from config.simulation_config import RunCondition
from simulation.clock import SimulationClock
from measurement.ground_truth import GroundTruthEvaluator
from calibration.enron_calibrator import calibrate_from_enron, BehavioralExhaustParameters


def run_condition(
    condition: RunCondition,
    weeks: int,
    seed: int,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Run a single condition and return metrics."""
    clock = SimulationClock(condition)
    snapshots = []

    total_decisions = 0
    correct_decisions = 0
    total_errors = 0
    context_used_count = 0

    for week in range(1, weeks + 1):
        snapshot = clock.run_week(week)
        snapshots.append(snapshot)

        for decision in snapshot.agent_decisions:
            total_decisions += 1
            if decision.outcome.value == "correct":
                correct_decisions += 1
            if decision.context_used:
                context_used_count += 1

        total_errors += snapshot.organizational_error_count

        if verbose:
            print(f"    Week {week}: {len(snapshot.agent_decisions)} decisions, {snapshot.organizational_error_count} errors")

    accuracy = (correct_decisions / total_decisions * 100) if total_decisions > 0 else 0
    context_utilization = (context_used_count / total_decisions * 100) if total_decisions > 0 else 0

    # Get synthesis metrics for Context Bank
    synthesis_patterns = 0
    if condition == RunCondition.CONTEXT_BANK and hasattr(clock, '_context_bank'):
        bank = clock._context_bank
        synthesis_patterns = len([o for o in bank.get_all_objects()
                                  if o.source_type == "synthesis"])

    return {
        "condition": condition.value,
        "total_decisions": total_decisions,
        "correct_decisions": correct_decisions,
        "accuracy": accuracy,
        "total_errors": total_errors,
        "context_utilization": context_utilization,
        "synthesis_patterns": synthesis_patterns,
    }


def run_comparison(
    weeks: int = 12,
    enron_path: str = None,
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    Run full 4-condition comparison.

    Args:
        weeks: Number of weeks to simulate
        enron_path: Path to Enron CSV for calibration (optional)
        verbose: Print progress

    Returns:
        Comparison results
    """
    # Load Enron calibration if path provided
    calibration = None
    calibration_info = {"source": "default", "sample_size": 0}

    if enron_path:
        if verbose:
            print("Loading Enron calibration...")
        result = calibrate_from_enron(enron_path)
        calibration = result.parameters
        calibration_info = {
            "source": "enron",
            "sample_size": result.sample_size,
            "confidence": result.confidence,
            "patterns_found": sum(result.pattern_counts.values()),
        }
        if verbose:
            print(f"  Calibrated from {result.sample_size:,} emails")
            print(f"  Found {sum(result.pattern_counts.values()):,} knowledge patterns")
            print()

    conditions = [
        (RunCondition.SILOED_TYPICAL, "SILOED_TYPICAL", "Dept-Only (No Primitives)"),
        (RunCondition.SILOED_ADVANCED, "SILOED_ADVANCED", "Dept+Adjacent (No Primitives)"),
        (RunCondition.GLOBAL_RAG, "GLOBAL_RAG", "Global RAG (No Primitives)"),
        (RunCondition.CONTEXT_BANK, "CONTEXT_BANK", "Context Bank (Full Primitives)"),
    ]

    results = {}

    if verbose:
        print("=" * 70)
        print("  4-CONDITION COMPARISON: CONTEXT PRIMITIVES THESIS")
        print("=" * 70)
        print(f"  Calibration: {calibration_info['source']}")
        if calibration_info['source'] == 'enron':
            print(f"  Sample size: {calibration_info['sample_size']:,} emails")
        print(f"  Simulation: {weeks} weeks")
        print("=" * 70)
        print()

    for condition, name, display in conditions:
        if verbose:
            print(f"Running {display}...")

        metrics = run_condition(
            condition=condition,
            weeks=weeks,
            seed=42,
            verbose=False,
        )
        results[name] = metrics

        if verbose:
            print(f"  → Accuracy: {metrics['accuracy']:.1f}%")
            print(f"  → Errors: {metrics['total_errors']}")
            if metrics['synthesis_patterns'] > 0:
                print(f"  → Synthesis patterns: {metrics['synthesis_patterns']}")
            print()

    return {
        "calibration": calibration_info,
        "weeks": weeks,
        "conditions": results,
    }


def print_summary(results: Dict[str, Any]) -> None:
    """Print formatted comparison summary."""
    conditions = results["conditions"]

    print()
    print("=" * 70)
    print("  RESULTS: CONTEXT PRIMITIVES ADVANTAGE")
    print("=" * 70)
    print()

    # Main comparison table
    print("  CONDITION                      | ACCURACY | ERRORS | PRIMITIVES?")
    print("  " + "-" * 66)

    for name in ["SILOED_TYPICAL", "SILOED_ADVANCED", "GLOBAL_RAG", "CONTEXT_BANK"]:
        c = conditions[name]
        has_primitives = "YES" if name == "CONTEXT_BANK" else "NO"
        marker = "→" if name == "CONTEXT_BANK" else " "
        print(f"  {marker} {name:28} | {c['accuracy']:6.1f}% | {c['total_errors']:6} | {has_primitives}")

    print()

    # Calculate gaps
    baseline = conditions["SILOED_TYPICAL"]["accuracy"]
    bank_accuracy = conditions["CONTEXT_BANK"]["accuracy"]
    rag_accuracy = conditions["GLOBAL_RAG"]["accuracy"]

    gap_vs_baseline = bank_accuracy - baseline
    gap_vs_rag = bank_accuracy - rag_accuracy

    print("  DIFFERENCES (single run):")
    print(f"    • Context Bank vs Siloed Typical:  +{gap_vs_baseline:.1f} points")
    print(f"    • Context Bank vs Global RAG:      +{gap_vs_rag:.1f} points")
    print()

    # Error reduction
    baseline_errors = conditions["SILOED_TYPICAL"]["total_errors"]
    bank_errors = conditions["CONTEXT_BANK"]["total_errors"]
    # Counts, not a percentage reduction: with a handful of decisions a ratio
    # like "100% fewer" is meaningless
    print(f"    • Incorrect decisions: {baseline_errors} (SILOED_TYPICAL) vs {bank_errors} (CONTEXT_BANK)")
    print()

    # Synthesis value
    synthesis = conditions["CONTEXT_BANK"].get("synthesis_patterns", 0)
    if synthesis > 0:
        print(f"    • Synthesis crystallized {synthesis} patterns from weak signals")
        print()

    print("  " + "=" * 66)
    print("  Calibrated mode, single seed: these accuracies restate configured")
    print("  values. Use run_multi_seed.py --mode mechanistic for comparisons.")
    print("  " + "=" * 66)
    print()

    # Calibration note
    cal = results["calibration"]
    if cal["source"] == "enron":
        print(f"  Note: Enron statistics were computed from {cal['sample_size']:,} emails")
        print(f"        but are not applied to the simulation (descriptive only).")
    print()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run 4-condition comparison")
    parser.add_argument("--weeks", type=int, default=12, help="Weeks to simulate")
    parser.add_argument("--enron", type=str, help="Path to Enron emails.csv (optional)")
    parser.add_argument("--quick", action="store_true", help="Quick 4-week run")

    args = parser.parse_args()

    weeks = 4 if args.quick else args.weeks
    enron_path = args.enron

    results = run_comparison(
        weeks=weeks,
        enron_path=enron_path,
        verbose=True,
    )

    print_summary(results)
