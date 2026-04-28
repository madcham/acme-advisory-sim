"""
Visualization Charts for Simulation Results.

Creates business and technical dashboards using Plotly.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import json

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


def create_business_dashboard(
    comparison_data: Dict[str, Any],
    output_path: str = "results/business_dashboard.html",
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
            "Decision Quality Score Over Time",
            "Organizational Errors by Condition",
            "Institutional Memory Utilization",
            "Exception Handling Success Rate"
        ),
        specs=[[{"type": "scatter"}, {"type": "bar"}],
               [{"type": "scatter"}, {"type": "bar"}]]
    )

    # Chart 1: DQS over time
    # Get average DQS per week for each condition
    without_dqs = without["primary_metrics"]["exception_handling_rates"]
    with_dqs = with_bank["primary_metrics"]["exception_handling_rates"]

    # Pad to 12 weeks if needed
    without_dqs = without_dqs + [0] * (12 - len(without_dqs))
    with_dqs = with_dqs + [0] * (12 - len(with_dqs))

    fig.add_trace(
        go.Scatter(
            x=weeks, y=without_dqs,
            mode='lines+markers',
            name='Without Bank',
            line=dict(color='#EF4444', width=2),
            marker=dict(size=8)
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=weeks, y=with_dqs,
            mode='lines+markers',
            name='With Bank',
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
            x=['Without Bank', 'With Bank'],
            y=[without_errors, with_errors],
            marker_color=['#EF4444', '#10B981'],
            text=[without_errors, with_errors],
            textposition='auto',
            showlegend=False
        ),
        row=1, col=2
    )

    # Chart 3: IMU over time
    with_imu = with_bank["primary_metrics"]["institutional_memory_utilization"]
    with_imu = with_imu + [0] * (12 - len(with_imu))

    fig.add_trace(
        go.Scatter(
            x=weeks, y=with_imu,
            mode='lines+markers',
            name='IMU %',
            line=dict(color='#3B82F6', width=2),
            marker=dict(size=8),
            fill='tozeroy',
            fillcolor='rgba(59, 130, 246, 0.1)'
        ),
        row=2, col=1
    )

    # Chart 4: Success rate by condition
    without_accuracy = without["summary"]["accuracy"]
    with_accuracy = with_bank["summary"]["accuracy"]

    fig.add_trace(
        go.Bar(
            x=['Without Bank', 'With Bank'],
            y=[without_accuracy, with_accuracy],
            marker_color=['#EF4444', '#10B981'],
            text=[f'{without_accuracy:.1f}%', f'{with_accuracy:.1f}%'],
            textposition='auto',
            showlegend=False
        ),
        row=2, col=2
    )

    # Update layout
    fig.update_layout(
        title={
            'text': 'Acme Advisory: Context Bank Impact - Business View',
            'font': {'size': 24}
        },
        height=800,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        template='plotly_white'
    )

    # Update axes labels
    fig.update_xaxes(title_text="Week", row=1, col=1)
    fig.update_yaxes(title_text="DQS Score", row=1, col=1)
    fig.update_yaxes(title_text="Error Count", row=1, col=2)
    fig.update_xaxes(title_text="Week", row=2, col=1)
    fig.update_yaxes(title_text="IMU %", row=2, col=1)
    fig.update_yaxes(title_text="Success Rate %", row=2, col=2)

    # Save
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output))

    return str(output)


def create_technical_dashboard(
    comparison_data: Dict[str, Any],
    output_path: str = "results/technical_dashboard.html",
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
            "Decision Accuracy by Week",
            "Contradiction Detection",
            "Bank Utilization",
            "Improvement Summary"
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
    ehr = with_bank["primary_metrics"]["exception_handling_rates"]
    ehr = ehr + [0] * (12 - len(ehr))

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
    imu = with_bank["primary_metrics"]["institutional_memory_utilization"]
    imu = imu + [0] * (12 - len(imu))

    fig.add_trace(
        go.Bar(
            x=weeks, y=imu,
            marker_color='#3B82F6',
            name='IMU %'
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
                'bar': {'color': '#10B981'},
                'steps': [
                    {'range': [0, 50], 'color': '#FEE2E2'},
                    {'range': [50, 75], 'color': '#FEF3C7'},
                    {'range': [75, 100], 'color': '#D1FAE5'}
                ],
                'threshold': {
                    'line': {'color': 'red', 'width': 2},
                    'thickness': 0.75,
                    'value': 90
                }
            },
            title={'text': 'With Bank Accuracy %'}
        ),
        row=3, col=2
    )

    # Update layout
    fig.update_layout(
        title={
            'text': 'Acme Advisory: Context Bank Technical Metrics',
            'font': {'size': 24}
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
        <div class="metric-label">Overall Accuracy Improvement</div>
        <div class="metric-value">+{data.get('comparison', {}).get('accuracy_improvement', 0):.1f}%</div>
    </div>
    <div class="metric">
        <div class="metric-label">Errors Avoided</div>
        <div class="metric-value">{data.get('comparison', {}).get('errors_avoided', 0)}</div>
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
    ) -> Dict[str, str]:
        """
        Generate all dashboards.

        Returns dict mapping dashboard name to file path.
        """
        paths = {}

        paths["business_dashboard"] = create_business_dashboard(
            comparison_data,
            str(self.output_dir / "business_dashboard.html")
        )

        paths["technical_dashboard"] = create_technical_dashboard(
            comparison_data,
            str(self.output_dir / "technical_dashboard.html")
        )

        return paths
