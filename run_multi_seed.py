#!/usr/bin/env python3
"""
Multi-Seed Simulation Runner.

Runs the 4-condition comparison (SILOED_TYPICAL, SILOED_ADVANCED, GLOBAL_RAG,
CONTEXT_BANK) under many random seeds to assess statistical robustness.

Every condition gets the same realism configuration (BPI calibration, and chaos
unless --no-chaos), so differences between conditions are not an artifact of
only one condition facing disruption.

Reported per condition: mean accuracy, standard deviation and a 95% confidence
interval. Reported per comparison: the paired difference (same seed, both
conditions) with its 95% confidence interval and win/tie/loss counts.

Usage:
    python run_multi_seed.py                    # 30 seeds (42-71), chaos on
    python run_multi_seed.py --n-seeds 100      # 100 seeds starting at 42
    python run_multi_seed.py --seeds 42 43 44   # Specific seeds
    python run_multi_seed.py --quick            # 4-week simulation per seed
    python run_multi_seed.py --no-chaos         # Disable chaos injection
    python run_multi_seed.py --mode mechanistic # Outcomes follow from retrieval
"""

import argparse
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Tuple

from main import run_4way_comparison
from simulation.mechanistic import MechanisticConfig
from calibration.realism_config import (
    FULL_REALISM_CONFIG, RealismConfig, ChaosConfig, BPICalibrationConfig
)


CONDITIONS = ["SILOED_TYPICAL", "SILOED_ADVANCED", "GLOBAL_RAG", "CONTEXT_BANK"]

# (label, condition, reference): difference reported as condition - reference
COMPARISONS: List[Tuple[str, str, str]] = [
    ("SILOED_ADVANCED vs SILOED_TYPICAL (partial sophistication)", "SILOED_ADVANCED", "SILOED_TYPICAL"),
    ("GLOBAL_RAG vs SILOED_TYPICAL", "GLOBAL_RAG", "SILOED_TYPICAL"),
    ("CONTEXT_BANK vs SILOED_TYPICAL", "CONTEXT_BANK", "SILOED_TYPICAL"),
    ("CONTEXT_BANK vs GLOBAL_RAG (value of primitives)", "CONTEXT_BANK", "GLOBAL_RAG"),
]

# Two-sided 95% critical values of Student's t, by degrees of freedom
_T_CRIT_95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
    8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145,
    15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 21: 2.080,
    22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056, 27: 2.052, 28: 2.048,
    29: 2.045, 30: 2.042, 40: 2.021, 60: 2.000, 120: 1.980,
}


def _t_crit(df: int) -> float:
    """95% two-sided t critical value, using the next lower tabulated df."""
    if df >= 120:
        return 1.960 if df > 1000 else _T_CRIT_95[120]
    return _T_CRIT_95[max(k for k in _T_CRIT_95 if k <= df)]


def calc_stats(values: List[float]) -> Dict[str, float]:
    """Mean, spread and 95% confidence interval of the mean."""
    n = len(values)
    mean = statistics.mean(values)
    std = statistics.stdev(values) if n > 1 else 0.0
    half_width = _t_crit(n - 1) * std / math.sqrt(n) if n > 1 else 0.0
    return {
        "mean": mean,
        "std": std,
        "ci95_low": mean - half_width,
        "ci95_high": mean + half_width,
        "min": min(values),
        "max": max(values),
        "n": n,
    }


def run_multi_seed(
    seeds: List[int],
    weeks: int = 12,
    output_base: str = "results/multi_seed",
    verbose: bool = True,
    enable_chaos: bool = True,
    decision_mode: str = "calibrated",
    mechanistic_config: MechanisticConfig = None,
) -> Dict[str, Any]:
    """
    Run the 4-condition simulation for each seed and aggregate results.

    Args:
        seeds: List of random seeds to use
        weeks: Number of weeks to simulate per run
        output_base: Base directory for output
        verbose: Print progress
        enable_chaos: Whether to enable chaos injection (default: True)
        decision_mode: "calibrated" or "mechanistic" (see simulation/mechanistic.py)
        mechanistic_config: Parameters for mechanistic mode

    Returns:
        Aggregated results with statistics
    """
    output_path = Path(output_base)
    output_path.mkdir(parents=True, exist_ok=True)

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
        print("  MULTI-SEED SIMULATION RUNNER (4 conditions)")
        print("=" * 70)
        print(f"  Seeds: {len(seeds)} ({seeds[0]}..{seeds[-1]})")
        print(f"  Weeks per run: {weeks}")
        print(f"  Realism mode: {realism_mode} (applied to all conditions)")
        print(f"  Decision mode: {decision_mode}")
        print(f"  Output directory: {output_path.absolute()}")
        print("=" * 70)
        print()

    accuracies: Dict[str, List[float]] = {c: [] for c in CONDITIONS}
    decisions_per_run: Dict[str, int] = {}
    per_seed_results = []

    for i, seed in enumerate(seeds, 1):
        seed_output = output_path / f"seed_{seed}"
        seed_output.mkdir(exist_ok=True)

        result = run_4way_comparison(
            weeks=weeks,
            verbose=False,
            output_dir=str(seed_output),
            realism_config=realism_config,
            seed=seed,
            generate_reports=False,
            decision_mode=decision_mode,
            mechanistic_config=mechanistic_config,
        )

        for condition in CONDITIONS:
            accuracies[condition].append(result["accuracies"][condition])
            decisions_per_run[condition] = result["condition_summaries"][condition]["total_decisions"]

        per_seed_results.append({"seed": seed, "accuracies": result["accuracies"]})

        if verbose:
            row = "  ".join(f"{c}={result['accuracies'][c]:5.1f}%" for c in CONDITIONS)
            print(f"  [{i:3d}/{len(seeds)}] seed {seed}: {row}")

    condition_stats = {c: calc_stats(accuracies[c]) for c in CONDITIONS}

    comparison_stats = {}
    for label, condition, reference in COMPARISONS:
        diffs = [a - b for a, b in zip(accuracies[condition], accuracies[reference])]
        stats = calc_stats(diffs)
        stats.update({
            "condition": condition,
            "reference": reference,
            "wins": sum(1 for d in diffs if d > 0),
            "ties": sum(1 for d in diffs if d == 0),
            "losses": sum(1 for d in diffs if d < 0),
        })
        comparison_stats[label] = stats

    aggregated = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "seeds": seeds,
            "weeks_per_run": weeks,
            "realism_mode": realism_mode,
            "chaos_enabled": enable_chaos,
            "decision_mode": decision_mode,
            "realism_applied_to": CONDITIONS,
            "total_runs": len(seeds),
            "decisions_per_run": decisions_per_run,
        },
        "raw_accuracies": accuracies,
        "condition_statistics": condition_stats,
        "paired_comparisons": comparison_stats,
        "per_seed_results": per_seed_results,
    }

    results_file = output_path / "aggregated_results.json"
    with open(results_file, "w") as f:
        json.dump(aggregated, f, indent=2, default=str)

    if verbose:
        print()
        print("=" * 70)
        print(f"  AGGREGATED RESULTS ({len(seeds)} seeds, {realism_mode}, {decision_mode})")
        print("=" * 70)
        print()
        print(f"  {'Condition':18} {'Mean':>7} {'Std':>6}   95% CI")
        for c in CONDITIONS:
            s = condition_stats[c]
            print(f"  {c:18} {s['mean']:6.1f}% {s['std']:5.1f}   [{s['ci95_low']:5.1f}, {s['ci95_high']:5.1f}]")
        print()
        print("  PAIRED DIFFERENCES (same seed, percentage points):")
        for label, s in comparison_stats.items():
            print(f"  {label}")
            print(f"      mean {s['mean']:+6.1f}  95% CI [{s['ci95_low']:+6.1f}, {s['ci95_high']:+6.1f}]"
                  f"  wins/ties/losses {s['wins']}/{s['ties']}/{s['losses']}")
        print()
        print("=" * 70)
        print(f"  Results saved to: {results_file}")
        print("=" * 70)

    return aggregated


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run the 4-condition simulation with multiple seeds"
    )
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=None,
        help="Specific random seeds to use (overrides --n-seeds)"
    )
    parser.add_argument(
        "--n-seeds",
        type=int,
        default=30,
        help="Number of consecutive seeds starting at 42 (default: 30)"
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
        default=None,
        help="Base output directory (default: results/multi_seed or results/multi_seed_no_chaos)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output"
    )
    parser.add_argument(
        "--mode",
        choices=["calibrated", "mechanistic"],
        default="calibrated",
        help="Decision model: accuracy set per condition in config (calibrated) "
             "or outcomes driven by what agents retrieve (mechanistic)"
    )
    parser.add_argument(
        "--no-chaos",
        dest="no_chaos",
        action="store_true",
        help="Disable chaos injection (stable baseline mode)"
    )

    args = parser.parse_args()

    seeds = args.seeds or list(range(42, 42 + args.n_seeds))
    weeks = 4 if args.quick else args.weeks
    default_dir = "results/multi_seed" if args.mode == "calibrated" else "results/mechanistic"
    output = args.output or (default_dir + ("_no_chaos" if args.no_chaos else ""))

    try:
        run_multi_seed(
            seeds=seeds,
            weeks=weeks,
            output_base=output,
            verbose=not args.quiet,
            enable_chaos=not args.no_chaos,
            decision_mode=args.mode,
        )
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
