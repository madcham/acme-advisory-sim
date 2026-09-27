#!/usr/bin/env python3
"""
Multi-Seed Simulation Runner.

Runs the full-realism simulation multiple times with different random seeds
to assess statistical robustness of results.

Usage:
    python run_multi_seed.py                    # Run 5 seeds (42-46) with default settings
    python run_multi_seed.py --seeds 42 43 44  # Run specific seeds
    python run_multi_seed.py --quick           # Run 4-week simulation per seed
    python run_multi_seed.py --no-chaos        # Run without chaos injection (stable baseline)
"""

import argparse
import json
import sys
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from main import run_simulation
from calibration.realism_config import (
    FULL_REALISM_CONFIG, RealismConfig, ChaosConfig, BPICalibrationConfig
)


def run_multi_seed(
    seeds: List[int],
    weeks: int = 12,
    output_base: str = "results/multi_seed",
    verbose: bool = True,
    enable_chaos: bool = True,
) -> Dict[str, Any]:
    """
    Run simulation with multiple seeds and aggregate results.

    Args:
        seeds: List of random seeds to use
        weeks: Number of weeks to simulate per run
        output_base: Base directory for output
        verbose: Print progress
        enable_chaos: Whether to enable chaos injection (default: True)

    Returns:
        Aggregated results with statistics
    """
    output_path = Path(output_base)
    output_path.mkdir(parents=True, exist_ok=True)

    # Configure realism
    if enable_chaos:
        realism_config = FULL_REALISM_CONFIG
        realism_mode = "Full Realism (BPI + Chaos)"
    else:
        realism_config = RealismConfig(
            chaos=ChaosConfig(enabled=False),
            bpi_calibration=BPICalibrationConfig(enabled=True),
        )
        realism_mode = "BPI Calibrated (No Chaos)"

    if verbose:
        print("=" * 70)
        print("  MULTI-SEED SIMULATION RUNNER")
        print("=" * 70)
        print(f"  Seeds: {seeds}")
        print(f"  Weeks per run: {weeks}")
        print(f"  Realism mode: {realism_mode}")
        print(f"  Output directory: {output_path.absolute()}")
        print("=" * 70)
        print()

    # Store results for each seed
    all_results = []
    without_bank_accuracies = []
    with_bank_accuracies = []

    for i, seed in enumerate(seeds, 1):
        if verbose:
            print(f"[{i}/{len(seeds)}] Running seed {seed}...")

        # Create seed-specific output directory
        seed_output = output_path / f"seed_{seed}"
        seed_output.mkdir(exist_ok=True)

        # Run simulation with this seed
        result = run_simulation(
            weeks=weeks,
            verbose=False,  # Suppress per-run output
            output_dir=str(seed_output),
            realism_config=realism_config,
            seed=seed,
        )

        all_results.append({
            "seed": seed,
            "result": result,
        })

        # Extract accuracies
        without_acc = result["without_bank_summary"]["overall_accuracy"]
        with_acc = result["with_bank_summary"]["overall_accuracy"]

        without_bank_accuracies.append(without_acc)
        with_bank_accuracies.append(with_acc)

        if verbose:
            improvement = with_acc - without_acc
            print(f"      WITHOUT_BANK: {without_acc:.1f}%  |  WITH_BANK: {with_acc:.1f}%  |  Δ: +{improvement:.1f}%")

    # Calculate statistics
    def calc_stats(values: List[float]) -> Dict[str, float]:
        return {
            "mean": statistics.mean(values),
            "std": statistics.stdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
            "n": len(values),
        }

    without_stats = calc_stats(without_bank_accuracies)
    with_stats = calc_stats(with_bank_accuracies)

    # Calculate improvement statistics
    improvements = [w - wo for w, wo in zip(with_bank_accuracies, without_bank_accuracies)]
    improvement_stats = calc_stats(improvements)

    # Aggregate results
    aggregated = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "seeds": seeds,
            "weeks_per_run": weeks,
            "realism_mode": realism_mode,
            "chaos_enabled": enable_chaos,
            "total_runs": len(seeds),
        },
        "raw_results": {
            "without_bank_accuracies": without_bank_accuracies,
            "with_bank_accuracies": with_bank_accuracies,
            "improvements": improvements,
        },
        "statistics": {
            "without_bank": without_stats,
            "with_bank": with_stats,
            "improvement": improvement_stats,
        },
        "per_seed_results": all_results,
    }

    # Save aggregated results
    results_file = output_path / "aggregated_results.json"
    with open(results_file, "w") as f:
        json.dump(aggregated, f, indent=2, default=str)

    if verbose:
        print()
        print("=" * 70)
        print("  AGGREGATED RESULTS ACROSS ALL SEEDS")
        print("=" * 70)
        print()
        print("  WITHOUT_BANK Accuracy:")
        print(f"    Mean:   {without_stats['mean']:.1f}%")
        print(f"    Std:    {without_stats['std']:.1f}%")
        print(f"    Min:    {without_stats['min']:.1f}%")
        print(f"    Max:    {without_stats['max']:.1f}%")
        print()
        print("  WITH_BANK Accuracy:")
        print(f"    Mean:   {with_stats['mean']:.1f}%")
        print(f"    Std:    {with_stats['std']:.1f}%")
        print(f"    Min:    {with_stats['min']:.1f}%")
        print(f"    Max:    {with_stats['max']:.1f}%")
        print()
        print("  IMPROVEMENT (WITH_BANK - WITHOUT_BANK):")
        print(f"    Mean:   +{improvement_stats['mean']:.1f}%")
        print(f"    Std:    {improvement_stats['std']:.1f}%")
        print(f"    Min:    +{improvement_stats['min']:.1f}%")
        print(f"    Max:    +{improvement_stats['max']:.1f}%")
        print()
        print("=" * 70)
        print(f"  Results saved to: {results_file}")
        print("=" * 70)

    return aggregated


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run simulation with multiple seeds for statistical robustness"
    )
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=[42, 43, 44, 45, 46],
        help="Random seeds to use (default: 42 43 44 45 46)"
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=12,
        help="Number of weeks to simulate per run (default: 12)"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run abbreviated 4-week simulation per seed"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results/multi_seed",
        help="Base output directory (default: results/multi_seed)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output"
    )
    parser.add_argument(
        "--no-chaos",
        dest="no_chaos",
        action="store_true",
        help="Disable chaos injection (stable baseline mode)"
    )

    args = parser.parse_args()

    weeks = 4 if args.quick else args.weeks
    verbose = not args.quiet

    try:
        results = run_multi_seed(
            seeds=args.seeds,
            weeks=weeks,
            output_base=args.output,
            verbose=verbose,
            enable_chaos=not args.no_chaos,
        )
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
