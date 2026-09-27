#!/usr/bin/env python3
"""
Acme Advisory: Context Bank Simulation

Main entry point that runs experimental conditions and calculates metrics.

Supports four experimental conditions:
- SILOED_TYPICAL: Agent only sees their department's context (~55% accuracy)
- SILOED_ADVANCED: Agent sees department + adjacent departments (~62% accuracy)
- GLOBAL_RAG: Agent sees all context, but no sophistication features (~70% accuracy)
- CONTEXT_BANK: Full visibility + full sophistication (~85% accuracy)

Usage:
    python main.py              # Run standard 2-way comparison (silo vs bank)
    python main.py --4-way      # Run full 4-condition comparison
    python main.py --quick      # Run abbreviated 4-week simulation
    python main.py --verbose    # Run with detailed output
    python main.py --chaos      # Run with chaos injection enabled (v3.0)
    python main.py --bpi        # Run with BPI calibration enabled (v3.0)
"""

import argparse
import json
from dataclasses import asdict
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from config.simulation_config import SIMULATION_CONFIG, RunCondition
from simulation.clock import SimulationClock
from measurement.metrics import MetricsCalculator
from measurement.ground_truth import GroundTruthEvaluator
from results.charts import ChartGenerator
from results.summary import SummaryGenerator
from simulation.mechanistic import MechanisticConfig
from calibration.realism_config import (
    RealismConfig, ChaosConfig, BPICalibrationConfig,
    DEFAULT_REALISM_CONFIG, CHAOS_ENABLED_CONFIG, FULL_REALISM_CONFIG,
)


def run_simulation(
    weeks: int = 12,
    verbose: bool = True,
    output_dir: str = "results",
    realism_config: Optional[RealismConfig] = None,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Run the complete simulation comparing both conditions.

    Args:
        weeks: Number of weeks to simulate (default 12)
        verbose: Print progress updates
        output_dir: Directory for output files
        realism_config: Optional realism configuration (v3.0)
        seed: Random seed for reproducibility (default: 42)

    Returns:
        Complete results dictionary
    """
    # Use provided seed or default
    if seed is None:
        seed = SIMULATION_CONFIG.random_seed
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # v3.0: Display realism mode
    realism_mode = "Standard"
    if realism_config:
        if realism_config.chaos.enabled and realism_config.bpi_calibration.enabled:
            realism_mode = "Full Realism (BPI + Chaos)"
        elif realism_config.chaos.enabled:
            realism_mode = "Chaos Enabled"
        elif realism_config.bpi_calibration.enabled:
            realism_mode = "BPI Calibrated"

    if verbose:
        print("=" * 70)
        print("  ACME ADVISORY: CONTEXT BANK SIMULATION")
        print("=" * 70)
        print(f"  Simulating {weeks} weeks of operations")
        print(f"  Realism mode: {realism_mode}")
        print(f"  Output directory: {output_path.absolute()}")
        print("=" * 70)
        print()

    # ================================================================
    # RUN WITHOUT BANK
    # ================================================================
    if verbose:
        print("PHASE 1: Running WITHOUT Context Bank")
        print("-" * 50)

    # Realism (chaos, BPI) applies to both arms so the comparison is fair
    clock_without = SimulationClock(
        RunCondition.WITHOUT_BANK,
        realism_config=realism_config,
        seed=seed,
    )
    snapshots_without = []

    for week in range(1, weeks + 1):
        snapshot = clock_without.run_week(week)
        snapshots_without.append(snapshot)

        if verbose:
            decisions = len(snapshot.agent_decisions)
            errors = snapshot.organizational_error_count
            print(f"  Week {week:2d}: {decisions} decisions, {errors} errors")
            for d in snapshot.agent_decisions:
                status = "✗" if d.outcome.value == "incorrect" else "✓"
                print(f"           {status} {d.scenario_type}")

    summary_without = clock_without.get_summary()

    if verbose:
        print()
        print(f"  WITHOUT BANK COMPLETE")
        print(f"  Total decisions: {summary_without['total_decisions']}")
        print(f"  Correct: {summary_without['correct_decisions']}")
        print(f"  Incorrect: {summary_without['incorrect_decisions']}")
        print(f"  Accuracy: {summary_without['overall_accuracy']:.1f}%")
        print()

    # ================================================================
    # RUN WITH BANK
    # ================================================================
    if verbose:
        print("PHASE 2: Running WITH Context Bank")
        print("-" * 50)

    clock_with = SimulationClock(
        RunCondition.WITH_BANK,
        realism_config=realism_config,
        seed=seed,
    )
    snapshots_with = []

    for week in range(1, weeks + 1):
        snapshot = clock_with.run_week(week)
        snapshots_with.append(snapshot)

        if verbose:
            decisions = len(snapshot.agent_decisions)
            errors = snapshot.organizational_error_count
            bank_size = snapshot.bank_snapshot.total_objects if snapshot.bank_snapshot else 0
            chaos_count = len(snapshot.chaos_impacts)
            chaos_str = f", chaos={chaos_count}" if chaos_count > 0 else ""
            print(f"  Week {week:2d}: {decisions} decisions, {errors} errors, bank={bank_size}{chaos_str}")

            # Show chaos events (v3.0)
            for impact in snapshot.chaos_impacts:
                print(f"           ⚡ {impact.event.chaos_type.value}: {impact.impact_description[:50]}")

            for d in snapshot.agent_decisions:
                status = "✓" if d.outcome.value == "correct" else "✗"
                ctx = f" [{','.join(d.context_used)}]" if d.context_used else ""
                print(f"           {status} {d.scenario_type}{ctx}")

    summary_with = clock_with.get_summary()

    if verbose:
        print()
        print(f"  WITH BANK COMPLETE")
        print(f"  Total decisions: {summary_with['total_decisions']}")
        print(f"  Correct: {summary_with['correct_decisions']}")
        print(f"  Incorrect: {summary_with['incorrect_decisions']}")
        print(f"  Accuracy: {summary_with['overall_accuracy']:.1f}%")
        print(f"  Final bank size: {summary_with['final_bank_size']}")
        print()

    # ================================================================
    # CALCULATE METRICS
    # ================================================================
    if verbose:
        print("PHASE 3: Calculating Metrics")
        print("-" * 50)

    calculator = MetricsCalculator()
    comparison = calculator.compare_conditions(snapshots_without, snapshots_with)

    if verbose:
        print(f"  DQS improvement: +{comparison['comparison']['dqs_improvement']:.1f}")
        print(f"  EHR improvement: +{comparison['comparison']['ehr_improvement']:.1f}%")
        print(f"  Errors avoided: {comparison['comparison']['errors_avoided']}")
        print(f"  Accuracy improvement: +{comparison['comparison']['accuracy_improvement']:.1f}%")
        print()

    # ================================================================
    # GENERATE OUTPUTS
    # ================================================================
    if verbose:
        print("PHASE 4: Generating Output Artifacts")
        print("-" * 50)

    # Save raw JSON results
    results = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "weeks_simulated": weeks,
            "random_seed": seed,
            "realism_mode": realism_mode,
            "realism_config": realism_config.to_dict() if realism_config else None,
        },
        "without_bank_summary": summary_without,
        "with_bank_summary": summary_with,
        "comparison": comparison,
    }

    results_file = output_path / "simulation_results.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    if verbose:
        print(f"  Saved: {results_file}")

    # Save decisions
    all_decisions = {
        "without_bank": [
            {
                "decision_id": d.decision_id,
                "week": d.week,
                "agent_id": d.agent_id,
                "scenario_type": d.scenario_type,
                "decision_taken": d.decision_taken,
                "outcome": d.outcome.value,
                "context_retrieved": d.context_retrieved,
                "context_used": d.context_used,
            }
            for d in clock_without.all_decisions
        ],
        "with_bank": [
            {
                "decision_id": d.decision_id,
                "week": d.week,
                "agent_id": d.agent_id,
                "scenario_type": d.scenario_type,
                "decision_taken": d.decision_taken,
                "outcome": d.outcome.value,
                "context_retrieved": d.context_retrieved,
                "context_used": d.context_used,
            }
            for d in clock_with.all_decisions
        ],
    }

    decisions_file = output_path / "all_decisions.json"
    with open(decisions_file, "w") as f:
        json.dump(all_decisions, f, indent=2)

    if verbose:
        print(f"  Saved: {decisions_file}")

    # Save bank state
    if clock_with.bank:
        bank_file = output_path / "final_bank_state.json"
        with open(bank_file, "w") as f:
            json.dump(clock_with.bank.export_to_dict(), f, indent=2, default=str)
        if verbose:
            print(f"  Saved: {bank_file}")

    # Generate charts
    chart_gen = ChartGenerator(str(output_path))
    chart_paths = chart_gen.generate_all(comparison)

    if verbose:
        for name, path in chart_paths.items():
            print(f"  Saved: {path}")

    # Generate summary
    summary_gen = SummaryGenerator(str(output_path))
    summary_path = summary_gen.generate(comparison)

    if verbose:
        print(f"  Saved: {summary_path}")

    # ================================================================
    # FINAL SUMMARY
    # ================================================================
    if verbose:
        print()
        print("=" * 70)
        print("  SIMULATION COMPLETE")
        print("=" * 70)
        print()
        print("  KEY RESULTS:")
        print(f"    WITHOUT Bank accuracy: {summary_without['overall_accuracy']:.1f}%")
        print(f"    WITH Bank accuracy:    {summary_with['overall_accuracy']:.1f}%")
        print(f"    Improvement:           +{comparison['comparison']['accuracy_improvement']:.1f}%")
        print(f"    Errors avoided:        {comparison['comparison']['errors_avoided']}")
        print()
        print("  OUTPUT FILES:")
        print(f"    Results JSON:     {results_file}")
        print(f"    Decisions JSON:   {decisions_file}")
        print(f"    Business Charts:  {chart_paths.get('business_dashboard', 'N/A')}")
        print(f"    Technical Charts: {chart_paths.get('technical_dashboard', 'N/A')}")
        print(f"    Summary:          {summary_path}")
        print()
        print("=" * 70)

    return results


def run_4way_comparison(
    weeks: int = 12,
    verbose: bool = True,
    output_dir: str = "results",
    realism_config: Optional[RealismConfig] = None,
    seed: Optional[int] = None,
    generate_reports: bool = True,
    decision_mode: str = "calibrated",
    mechanistic_config: Optional[MechanisticConfig] = None,
) -> Dict[str, Any]:
    """
    Run the complete 4-condition comparison simulation.

    This compares all four experimental conditions:
    - SILOED_TYPICAL: Department-only visibility (~55% accuracy)
    - SILOED_ADVANCED: Department + adjacent visibility (~62% accuracy)
    - GLOBAL_RAG: All visibility, no sophistication (~70% accuracy)
    - CONTEXT_BANK: Full visibility + sophistication (~85% accuracy)

    Args:
        weeks: Number of weeks to simulate (default 12)
        verbose: Print progress updates
        output_dir: Directory for output files
        realism_config: Optional realism configuration (v3.0)
        seed: Random seed for reproducibility (default: 42)
        generate_reports: Write bank state, dashboards and summary (the dashboards
            are ~9MB; multi-seed runs turn this off)
        decision_mode: "calibrated" or "mechanistic" (see simulation/mechanistic.py)
        mechanistic_config: Parameters for mechanistic mode

    Returns:
        Complete results dictionary with all 4 conditions
    """
    # Use provided seed or default
    if seed is None:
        seed = SIMULATION_CONFIG.random_seed
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # v3.0: Display realism mode
    realism_mode = "Standard"
    if realism_config:
        if realism_config.chaos.enabled and realism_config.bpi_calibration.enabled:
            realism_mode = "Full Realism (BPI + Chaos)"
        elif realism_config.chaos.enabled:
            realism_mode = "Chaos Enabled"
        elif realism_config.bpi_calibration.enabled:
            realism_mode = "BPI Calibrated"

    if verbose:
        print("=" * 70)
        print("  ACME ADVISORY: 4-CONDITION COMPARISON SIMULATION")
        print("=" * 70)
        print(f"  Simulating {weeks} weeks of operations")
        print(f"  Realism mode: {realism_mode}")
        print(f"  Output directory: {output_path.absolute()}")
        print()
        print("  CONDITIONS:")
        print("    1. SILOED_TYPICAL   - Department-only context visibility")
        print("    2. SILOED_ADVANCED  - Department + adjacent departments")
        print("    3. GLOBAL_RAG       - All context, no sophistication")
        print("    4. CONTEXT_BANK     - Full visibility + full sophistication")
        print("=" * 70)
        print()

    # Store results for each condition
    condition_results = {}
    conditions = [
        (RunCondition.SILOED_TYPICAL, "SILOED_TYPICAL", "Department-Only"),
        (RunCondition.SILOED_ADVANCED, "SILOED_ADVANCED", "Dept + Adjacent"),
        (RunCondition.GLOBAL_RAG, "GLOBAL_RAG", "Global RAG"),
        (RunCondition.CONTEXT_BANK, "CONTEXT_BANK", "Context Bank"),
    ]

    for i, (condition, name, display_name) in enumerate(conditions, 1):
        if verbose:
            print(f"PHASE {i}: Running {display_name} ({name})")
            print("-" * 50)

        # Realism (chaos, BPI) applies to every condition so the comparison is fair
        clock = SimulationClock(
            condition,
            realism_config=realism_config,
            seed=seed,
            decision_mode=decision_mode,
            mechanistic_config=mechanistic_config,
        )
        snapshots = []

        for week in range(1, weeks + 1):
            snapshot = clock.run_week(week)
            snapshots.append(snapshot)

            if verbose:
                decisions = len(snapshot.agent_decisions)
                errors = snapshot.organizational_error_count
                extras = []

                if hasattr(snapshot, 'bank_snapshot') and snapshot.bank_snapshot:
                    extras.append(f"bank={snapshot.bank_snapshot.total_objects}")

                if hasattr(snapshot, 'chaos_impacts') and snapshot.chaos_impacts:
                    extras.append(f"chaos={len(snapshot.chaos_impacts)}")

                extra_str = f", {', '.join(extras)}" if extras else ""
                print(f"  Week {week:2d}: {decisions} decisions, {errors} errors{extra_str}")

                for d in snapshot.agent_decisions:
                    status = "✓" if d.outcome.value == "correct" else "✗"
                    ctx = f" [{','.join(d.context_used)}]" if d.context_used else ""
                    print(f"           {status} {d.scenario_type}{ctx}")

        summary = clock.get_summary()
        condition_results[name] = {
            "snapshots": snapshots,
            "summary": summary,
            "clock": clock,
        }

        if verbose:
            print()
            print(f"  {display_name.upper()} COMPLETE")
            print(f"  Total decisions: {summary['total_decisions']}")
            print(f"  Correct: {summary['correct_decisions']}")
            print(f"  Incorrect: {summary['incorrect_decisions']}")
            print(f"  Accuracy: {summary['overall_accuracy']:.1f}%")
            if 'final_bank_size' in summary:
                print(f"  Final bank size: {summary['final_bank_size']}")
            print()

    # ================================================================
    # CALCULATE COMPARISON METRICS
    # ================================================================
    if verbose:
        print("PHASE 5: Calculating Comparison Metrics")
        print("-" * 50)

    calculator = MetricsCalculator()

    # Compare SILOED_TYPICAL vs CONTEXT_BANK (main comparison)
    main_comparison = calculator.compare_conditions(
        condition_results["SILOED_TYPICAL"]["snapshots"],
        condition_results["CONTEXT_BANK"]["snapshots"],
    )

    # Calculate accuracy improvements across all conditions
    accuracies = {
        name: data["summary"]["overall_accuracy"]
        for name, data in condition_results.items()
    }

    if verbose:
        print()
        print("  ACCURACY COMPARISON:")
        print("  " + "-" * 46)
        for name, acc in accuracies.items():
            bar_len = int(acc / 2)  # Scale to fit
            bar = "█" * bar_len + "░" * (50 - bar_len)
            print(f"  {name:20} {acc:5.1f}%  {bar[:40]}")
        print("  " + "-" * 46)
        print()
        print("  IMPROVEMENT ANALYSIS:")
        baseline = accuracies["SILOED_TYPICAL"]
        for name in ["SILOED_ADVANCED", "GLOBAL_RAG", "CONTEXT_BANK"]:
            improvement = accuracies[name] - baseline
            print(f"    {name:20} vs Baseline: +{improvement:.1f}%")
        print()
        print("  GAP ANALYSIS:")
        gap_advanced_rag = accuracies["GLOBAL_RAG"] - accuracies["SILOED_ADVANCED"]
        gap_rag_bank = accuracies["CONTEXT_BANK"] - accuracies["GLOBAL_RAG"]
        print(f"    Global RAG over SILOED_ADVANCED: +{gap_advanced_rag:.1f}%")
        print(f"    Context Bank over Global RAG:    +{gap_rag_bank:.1f}% (sophistication value)")
        print()

    # ================================================================
    # GENERATE OUTPUTS
    # ================================================================
    if verbose:
        print("PHASE 6: Generating Output Artifacts")
        print("-" * 50)

    # Save raw JSON results
    results = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "weeks_simulated": weeks,
            "random_seed": seed,
            "realism_mode": realism_mode,
            "comparison_type": "4-way",
            "decision_mode": decision_mode,
            "mechanistic_config": asdict(mechanistic_config or MechanisticConfig())
            if decision_mode == "mechanistic" else None,
            "realism_config": realism_config.to_dict() if realism_config else None,
        },
        "condition_summaries": {
            name: data["summary"] for name, data in condition_results.items()
        },
        "accuracies": accuracies,
        "improvements_over_baseline": {
            name: accuracies[name] - accuracies["SILOED_TYPICAL"]
            for name in ["SILOED_ADVANCED", "GLOBAL_RAG", "CONTEXT_BANK"]
        },
        "main_comparison": main_comparison,
    }

    results_file = output_path / "simulation_results_4way.json"
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    if verbose:
        print(f"  Saved: {results_file}")

    # Save decisions for each condition
    all_decisions = {}
    for name, data in condition_results.items():
        all_decisions[name] = [
            {
                "decision_id": d.decision_id,
                "week": d.week,
                "agent_id": d.agent_id,
                "scenario_type": d.scenario_type,
                "decision_taken": d.decision_taken,
                "outcome": d.outcome.value,
                "context_retrieved": d.context_retrieved,
                "context_used": d.context_used,
            }
            for d in data["clock"].all_decisions
        ]

    decisions_file = output_path / "all_decisions_4way.json"
    with open(decisions_file, "w") as f:
        json.dump(all_decisions, f, indent=2)

    if verbose:
        print(f"  Saved: {decisions_file}")

    if not generate_reports:
        return results

    # Save bank state (only CONTEXT_BANK has a bank)
    bank_clock = condition_results["CONTEXT_BANK"]["clock"]
    if hasattr(bank_clock, 'bank') and bank_clock.bank:
        bank_file = output_path / "final_bank_state.json"
        with open(bank_file, "w") as f:
            json.dump(bank_clock.bank.export_to_dict(), f, indent=2, default=str)
        if verbose:
            print(f"  Saved: {bank_file}")

    # Generate charts (use main comparison for chart generation)
    chart_gen = ChartGenerator(str(output_path))
    chart_paths = chart_gen.generate_all(main_comparison)

    if verbose:
        for name, path in chart_paths.items():
            print(f"  Saved: {path}")

    # Generate summary
    summary_gen = SummaryGenerator(str(output_path))
    summary_path = summary_gen.generate(main_comparison)

    if verbose:
        print(f"  Saved: {summary_path}")

    # ================================================================
    # FINAL SUMMARY
    # ================================================================
    if verbose:
        print()
        print("=" * 70)
        print("  4-WAY COMPARISON COMPLETE")
        print("=" * 70)
        print()
        print("  KEY RESULTS (Accuracy by Condition):")
        print()
        print("    ┌─────────────────────┬──────────┬─────────────┐")
        print("    │ Condition           │ Accuracy │ vs Baseline │")
        print("    ├─────────────────────┼──────────┼─────────────┤")
        baseline = accuracies["SILOED_TYPICAL"]
        for name in ["SILOED_TYPICAL", "SILOED_ADVANCED", "GLOBAL_RAG", "CONTEXT_BANK"]:
            acc = accuracies[name]
            improvement = acc - baseline
            imp_str = f"+{improvement:.1f}%" if improvement > 0 else "baseline"
            print(f"    │ {name:19} │ {acc:6.1f}%  │ {imp_str:>11} │")
        print("    └─────────────────────┴──────────┴─────────────┘")
        print()
        print("  INSIGHT: Context Bank's sophistication features (decay, provenance,")
        print(f"  attribution) add +{accuracies['CONTEXT_BANK'] - accuracies['GLOBAL_RAG']:.1f}% accuracy over basic RAG.")
        print()
        print("  OUTPUT FILES:")
        print(f"    Results JSON:     {results_file}")
        print(f"    Decisions JSON:   {decisions_file}")
        print(f"    Business Charts:  {chart_paths.get('business_dashboard', 'N/A')}")
        print(f"    Summary:          {summary_path}")
        print()
        print("=" * 70)

    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Acme Advisory Context Bank Simulation"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run abbreviated 4-week simulation"
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=12,
        help="Number of weeks to simulate (default: 12)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Print detailed progress (default: True)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="results",
        help="Output directory (default: results)"
    )
    # v3.0 realism options
    parser.add_argument(
        "--chaos",
        action="store_true",
        help="Enable chaos injection (knowledge departure, policy contradiction, agent drift)"
    )
    parser.add_argument(
        "--bpi",
        action="store_true",
        help="Enable BPI Challenge calibration for timing distributions"
    )
    parser.add_argument(
        "--full-realism",
        action="store_true",
        help="Enable both chaos and BPI calibration"
    )
    parser.add_argument(
        "--4-way",
        dest="four_way",
        action="store_true",
        help="Run full 4-condition comparison (SILOED_TYPICAL, SILOED_ADVANCED, GLOBAL_RAG, CONTEXT_BANK)"
    )
    parser.add_argument(
        "--mode",
        choices=["calibrated", "mechanistic"],
        default="calibrated",
        help="Decision model for --4-way runs: accuracy set per condition in config "
             "(calibrated) or outcomes driven by what agents retrieve (mechanistic)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility (default: 42)"
    )

    args = parser.parse_args()

    weeks = 4 if args.quick else args.weeks
    verbose = not args.quiet

    # Build realism config (v3.0)
    realism_config = None
    if args.full_realism:
        realism_config = FULL_REALISM_CONFIG
    elif args.chaos and args.bpi:
        realism_config = FULL_REALISM_CONFIG
    elif args.chaos:
        realism_config = CHAOS_ENABLED_CONFIG
    elif args.bpi:
        realism_config = RealismConfig(
            bpi_calibration=BPICalibrationConfig(enabled=True),
            chaos=ChaosConfig(enabled=False),
        )

    try:
        if args.four_way:
            results = run_4way_comparison(
                weeks=weeks,
                verbose=verbose,
                output_dir=args.output,
                realism_config=realism_config,
                seed=args.seed,
                decision_mode=args.mode,
            )
        else:
            results = run_simulation(
                weeks=weeks,
                verbose=verbose,
                output_dir=args.output,
                realism_config=realism_config,
                seed=args.seed,
            )
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
