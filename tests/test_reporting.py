"""
Tests for result reporting: single-run summaries, dashboards and metrics.

These guard against reports that state conclusions the data does not show:
fixed narratives, hard-coded "+" signs, empty weeks plotted as 0%, and
utilization above 100%.
"""

import pytest

from calibration.realism_config import FULL_REALISM_CONFIG
from config.simulation_config import RunCondition
from measurement.metrics import MetricsCalculator
from results.charts import _weekly_with_gaps
from results.summary import generate_summary_markdown
from simulation.clock import SimulationClock


def _run(condition, seed=42, mode="mechanistic"):
    clock = SimulationClock(condition, seed=seed, realism_config=FULL_REALISM_CONFIG, decision_mode=mode)
    snapshots = [clock.run_week(week) for week in range(1, 13)]
    return clock, snapshots


class TestSummary:

    def _summary(self, tmp_path, summaries, mode="mechanistic", decisions=None):
        path = generate_summary_markdown(
            summaries, str(tmp_path / "summary.md"), decisions=decisions,
            decision_mode=mode, headline=("CONTEXT_BANK", "GLOBAL_RAG"), seed=42,
        )
        return open(path).read()

    def test_negative_difference_is_reported_as_negative(self, tmp_path):
        text = self._summary(tmp_path, {
            "GLOBAL_RAG": {"correct_decisions": 13, "incorrect_decisions": 2, "total_decisions": 15, "overall_accuracy": 86.7},
            "CONTEXT_BANK": {"correct_decisions": 11, "incorrect_decisions": 4, "total_decisions": 15, "overall_accuracy": 73.3},
        })
        assert "CONTEXT_BANK minus GLOBAL_RAG: -13.4 points" in text
        assert "+-" not in text

    def test_no_fixed_narrative(self, tmp_path):
        clock, _ = _run(RunCondition.CONTEXT_BANK)
        text = self._summary(
            tmp_path, {"CONTEXT_BANK": clock.get_summary()},
            decisions={"CONTEXT_BANK": clock.all_decisions},
        )
        for claim in ("stark", "prevented", "compound", "transformative", "avoided"):
            assert claim not in text.lower()

    def test_states_mode_and_sample_size(self, tmp_path):
        summaries = {"CONTEXT_BANK": {"total_decisions": 15, "overall_accuracy": 80.0}}
        calibrated = self._summary(tmp_path, summaries, mode="calibrated")
        mechanistic = self._summary(tmp_path, summaries, mode="mechanistic")

        assert "not evidence about the Context Bank" in calibrated
        assert "Mechanistic mode" in mechanistic
        assert "one decision moves accuracy by 6.7 points" in mechanistic

    def test_scenario_table_counts_match_decisions(self, tmp_path):
        clock, _ = _run(RunCondition.GLOBAL_RAG)
        text = self._summary(
            tmp_path, {"GLOBAL_RAG": clock.get_summary()},
            decisions={"GLOBAL_RAG": clock.all_decisions},
        )
        rows = [line for line in text.splitlines() if line.startswith("| vendor_sow")]
        correct = sum(1 for d in clock.all_decisions
                      if d.scenario_type == "vendor_sow" and d.outcome.value == "correct")
        total = sum(1 for d in clock.all_decisions if d.scenario_type == "vendor_sow")
        assert rows == [f"| vendor_sow | {correct}/{total} |"]


class TestMetrics:

    def test_weekly_rates_have_gaps_for_weeks_without_decisions(self):
        metrics = {"primary_metrics": {
            "exception_handling_rates": [0.0, 0.0, 100.0, 0.0],
            "decisions_per_week": [0, 0, 1, 2],
        }}
        assert _weekly_with_gaps(metrics, "exception_handling_rates")[:4] == [None, None, 100.0, 0.0]

    def test_utilization_and_exception_rate_stay_within_100(self):
        _, snapshots = _run(RunCondition.CONTEXT_BANK)
        for snapshot in snapshots:
            assert 0 <= snapshot.institutional_memory_utilization <= 100
            assert 0 <= snapshot.exception_handling_rate <= 100

    def test_overall_ehr_equals_accuracy_despite_empty_weeks(self):
        clock, snapshots = _run(RunCondition.CONTEXT_BANK)
        metrics = MetricsCalculator().calculate_from_snapshots(snapshots)
        assert any(n == 0 for n in metrics.decisions_per_week)  # weeks 1-2 are empty
        assert metrics.overall_ehr() == pytest.approx(clock.get_summary()["overall_accuracy"])


class TestApp:

    def test_app_runs_and_leads_with_current_results(self):
        pytest.importorskip("streamlit")
        from pathlib import Path
        from streamlit.testing.v1 import AppTest

        app = Path(__file__).resolve().parent.parent / "app.py"
        at = AppTest.from_file(str(app), default_timeout=120).run()

        assert not at.exception
        text = " ".join(m.value for m in at.markdown)
        assert "CONTEXT_BANK minus GLOBAL_RAG" in text
        for claim in ("improved decision accuracy", "proves the Context Bank", "Mistakes Prevented"):
            assert claim not in text
