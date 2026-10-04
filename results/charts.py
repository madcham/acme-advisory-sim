"""
Visualization Charts for Simulation Results.

Creates business and technical dashboards using Plotly.
"""

from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import json

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


def _weekly_with_gaps(metrics: Dict[str, Any], key: str) -> List[Optional[float]]:
    """A weekly primary metric, with None (a gap) for weeks that had no decisions.

    Weekly rates report 0.0 for empty weeks, which would plot as 0%.
    """
    rates = metrics["primary_metrics"][key]
    counts = metrics["primary_metrics"].get("decisions_per_week") or [1] * len(rates)
    weekly = [rate if n else None for rate, n in zip(rates, counts)]
    return weekly + [None] * (12 - len(weekly))


def _weekly_accuracy(metrics: Dict[str, Any]) -> List[Optional[float]]:
    """Weekly accuracy, with gaps for weeks that had no decisions."""
    return _weekly_with_gaps(metrics, "exception_handling_rates")


def create_business_dashboard(
    comparison_data: Dict[str, Any],
    output_path: str = "results/business_dashboard.html",
    labels: Tuple[str, str] = ("Without Bank", "With Bank"),
    note: str = "",
    accuracies: Optional[Dict[str, float]] = None,
) -> str:
    """
    Create business leader readable dashboard.

    Four charts:
    1. DQS over 12 weeks (WITH vs WITHOUT)
    2. OER comparison
    3. IMU progression
    4. Exception handling outcomes on Brightline scenario

    Args:
        comparison_data: Output from MetricsCalculator.compare_conditions()
        output_path: Where to save the HTML file
        labels: Names of the two compared conditions (reference, other)
        note: Context shown under the title (decision mode, sample size)

    Returns:
        Path to generated HTML file
    """
    if not PLOTLY_AVAILABLE:
        return _create_fallback_html(comparison_data, output_path, "Business Dashboard")

    without = comparison_data["without_bank"]
    with_bank = comparison_data["with_bank"]
    weeks = list(range(1, 13))

    # Create subplot figure
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "Accuracy by Week (gaps: no decisions)",
            "Incorrect Decisions",
            f"Relevant Knowledge Read ({labels[1]})",
            "Overall Accuracy"
        ),
        specs=[[{"type": "scatter"}, {"type": "bar"}],
               [{"type": "scatter"}, {"type": "bar"}]]
    )

    # Chart 1: accuracy by week
    without_dqs = _weekly_accuracy(without)
    with_dqs = _weekly_accuracy(with_bank)

    fig.add_trace(
        go.Scatter(
            x=weeks, y=without_dqs,
            mode='lines+markers',
            name=labels[0],
            line=dict(color='#EF4444', width=2),
            marker=dict(size=8)
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=weeks, y=with_dqs,
            mode='lines+markers',
            name=labels[1],
            line=dict(color='#10B981', width=2),
            marker=dict(size=8)
        ),
        row=1, col=1
    )

    # Chart 2: Total errors comparison
    without_errors = without["summary"]["incorrect_decisions"]
    with_errors = with_bank["summary"]["incorrect_decisions"]

    fig.add_trace(
        go.Bar(
            x=list(labels),
            y=[without_errors, with_errors],
            marker_color=['#EF4444', '#10B981'],
            text=[without_errors, with_errors],
            textposition='auto',
            showlegend=False
        ),
        row=1, col=2
    )

    # Chart 3: IMU over time
    with_imu = _weekly_with_gaps(with_bank, "institutional_memory_utilization")

    fig.add_trace(
        go.Scatter(
            x=weeks, y=with_imu,
            mode='lines+markers',
            name='Relevant knowledge read %',
            line=dict(color='#3B82F6', width=2),
            marker=dict(size=8),
            fill='tozeroy',
            fillcolor='rgba(59, 130, 246, 0.1)'
        ),
        row=2, col=1
    )

    # Chart 4: overall accuracy, for every condition in the run when given
    if not accuracies:
        accuracies = {
            labels[0]: without["summary"]["accuracy"],
            labels[1]: with_bank["summary"]["accuracy"],
        }

    fig.add_trace(
        go.Bar(
            x=list(accuracies),
            y=list(accuracies.values()),
            marker_color='#6B7280',
            text=[f'{a:.1f}%' for a in accuracies.values()],
            textposition='auto',
            showlegend=False
        ),
        row=2, col=2
    )

    # Update layout
    fig.update_layout(
        title={
            'text': f'Acme Advisory: Single Run, {labels[0]} vs {labels[1]}'
                    + (f'<br><sup>{note}</sup>' if note else ''),
            'font': {'size': 22}
        },
        height=800,
        showlegend=True,
        legend=dict(orientation="h", yanchor="top", y=-0.08, xanchor="left", x=0),
        margin=dict(t=110),
        template='plotly_white'
    )

    # Update axes labels
    fig.update_xaxes(title_text="Week", row=1, col=1)
    fig.update_yaxes(title_text="Accuracy %", row=1, col=1)
    fig.update_yaxes(title_text="Error Count", row=1, col=2)
    fig.update_xaxes(title_text="Week", row=2, col=1)
    fig.update_yaxes(title_text="% of relevant objects", row=2, col=1)
    fig.update_yaxes(title_text="Accuracy %", row=2, col=2)

    # Save
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output))

    return str(output)


def create_technical_dashboard(
    comparison_data: Dict[str, Any],
    output_path: str = "results/technical_dashboard.html",
    labels: Tuple[str, str] = ("Without Bank", "With Bank"),
    note: str = "",
) -> str:
    """
    Create technical leader readable dashboard.

    Six charts:
    1. Context object growth by grade
    2. Confidence score distribution evolution
    3. Provenance chain depth over time
    4. Contradiction detection log
    5. Decay function accuracy
    6. Classifier performance

    Args:
        comparison_data: Output from MetricsCalculator.compare_conditions()
        output_path: Where to save the HTML file

    Returns:
        Path to generated HTML file
    """
    if not PLOTLY_AVAILABLE:
        return _create_fallback_html(comparison_data, output_path, "Technical Dashboard")

    with_bank = comparison_data["with_bank"]
    weeks = list(range(1, 13))

    # Create subplot figure
    fig = make_subplots(
        rows=3, cols=2,
        subplot_titles=(
            "Context Object Growth",
            "Average Confidence Over Time",
            "Accuracy by Week (gaps: no decisions)",
            "Contradiction Detection",
            "Relevant Knowledge Read",
            f"{labels[1]} Accuracy % (delta vs {labels[0]})"
        ),
        specs=[[{"type": "scatter"}, {"type": "scatter"}],
               [{"type": "scatter"}, {"type": "scatter"}],
               [{"type": "bar"}, {"type": "indicator"}]]
    )

    # Chart 1: Context object growth
    growth = with_bank["secondary_metrics"]["context_object_growth"]
    growth = growth + [growth[-1] if growth else 0] * (12 - len(growth))

    fig.add_trace(
        go.Scatter(
            x=weeks, y=growth,
            mode='lines+markers',
            name='Total Objects',
            line=dict(color='#8B5CF6', width=2),
            fill='tozeroy',
            fillcolor='rgba(139, 92, 246, 0.1)'
        ),
        row=1, col=1
    )

    # Chart 2: Average confidence over time
    avg_conf = with_bank["secondary_metrics"]["avg_confidence_history"]
    avg_conf = avg_conf + [avg_conf[-1] if avg_conf else 0] * (12 - len(avg_conf))

    fig.add_trace(
        go.Scatter(
            x=weeks, y=avg_conf,
            mode='lines+markers',
            name='Avg Confidence',
            line=dict(color='#F59E0B', width=2)
        ),
        row=1, col=2
    )

    # Chart 3: Decision accuracy by week (EHR as proxy)
    ehr = _weekly_accuracy(with_bank)

    fig.add_trace(
        go.Scatter(
            x=weeks, y=ehr,
            mode='lines+markers',
            name='Accuracy %',
            line=dict(color='#10B981', width=2)
        ),
        row=2, col=1
    )

    # Chart 4: Contradiction counts
    contradictions = with_bank["secondary_metrics"]["contradiction_counts"]
    contradictions = contradictions + [contradictions[-1] if contradictions else 0] * (12 - len(contradictions))

    fig.add_trace(
        go.Scatter(
            x=weeks, y=contradictions,
            mode='lines+markers',
            name='Contradictions',
            line=dict(color='#EF4444', width=2)
        ),
        row=2, col=2
    )

    # Chart 5: Bank utilization (IMU)
    imu = _weekly_with_gaps(with_bank, "institutional_memory_utilization")

    fig.add_trace(
        go.Bar(
            x=weeks, y=imu,
            marker_color='#3B82F6',
            name='Relevant knowledge read %'
        ),
        row=3, col=1
    )

    # Chart 6: Improvement indicator
    improvement = comparison_data["comparison"]["accuracy_improvement"]

    fig.add_trace(
        go.Indicator(
            mode="gauge+number+delta",
            value=comparison_data["with_bank"]["summary"]["accuracy"],
            delta={'reference': comparison_data["without_bank"]["summary"]["accuracy"]},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': '#6B7280'},
            },
            # The subplot title already names the comparison
        ),
        row=3, col=2
    )

    # Update layout
    fig.update_layout(
        title={
            'text': f'Acme Advisory: Single Run, {labels[1]} Internals'
                    + (f'<br><sup>{note}</sup>' if note else ''),
            'font': {'size': 22}
        },
        height=1000,
        showlegend=True,
        template='plotly_white'
    )

    # Save
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output))

    return str(output)


def _create_fallback_html(
    data: Dict[str, Any],
    output_path: str,
    title: str,
) -> str:
    """Create a simple HTML fallback when Plotly is not available."""
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 40px; }}
        h1 {{ color: #1F2937; }}
        .metric {{ background: #F3F4F6; padding: 20px; margin: 10px 0; border-radius: 8px; }}
        .metric-value {{ font-size: 32px; font-weight: bold; color: #10B981; }}
        .metric-label {{ color: #6B7280; }}
        pre {{ background: #1F2937; color: #E5E7EB; padding: 20px; border-radius: 8px; overflow-x: auto; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <p>Install Plotly for interactive charts: <code>pip install plotly</code></p>
    <div class="metric">
        <div class="metric-label">Accuracy difference (points)</div>
        <div class="metric-value">{data.get('comparison', {}).get('accuracy_improvement', 0):+.1f}</div>
    </div>
    <div class="metric">
        <div class="metric-label">Difference in incorrect decisions (reference minus other)</div>
        <div class="metric-value">{data.get('comparison', {}).get('errors_avoided', 0):+d}</div>
    </div>
    <h2>Raw Data</h2>
    <pre>{json.dumps(data, indent=2, default=str)}</pre>
</body>
</html>"""

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'w') as f:
        f.write(html)

    return str(output)


class ChartGenerator:
    """
    Generates all charts for simulation results.
    """

    def __init__(self, output_dir: str = "results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_all(
        self,
        comparison_data: Dict[str, Any],
        labels: Tuple[str, str] = ("Without Bank", "With Bank"),
        note: str = "",
        accuracies: Optional[Dict[str, float]] = None,
    ) -> Dict[str, str]:
        """
        Generate all dashboards for a two-condition comparison.

        Args:
            comparison_data: Output from MetricsCalculator.compare_conditions()
            labels: Names of the two compared conditions (reference, other)
            note: Context shown under the title (decision mode, sample size)
            accuracies: Accuracy of every condition in the run, for the
                overall accuracy chart (defaults to the two compared)

        Returns dict mapping dashboard name to file path.
        """
        paths = {}

        paths["business_dashboard"] = create_business_dashboard(
            comparison_data,
            str(self.output_dir / "business_dashboard.html"),
            labels=labels,
            note=note,
            accuracies=accuracies,
        )

        paths["technical_dashboard"] = create_technical_dashboard(
            comparison_data,
            str(self.output_dir / "technical_dashboard.html"),
            labels=labels,
            note=note,
        )

        return paths
