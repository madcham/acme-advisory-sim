"""
Acme Advisory Context Bank Simulation - Interactive UI

Streamlit-based interface for exploring simulation results, context bank,
and decision traces.

Run with: streamlit run app.py
"""

import streamlit as st
import json
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from config.simulation_config import SIMULATION_CONFIG, RunCondition, AGENTS, CLIENTS, VENDORS
from config.seeded_context import SEEDED_CONTEXT_OBJECTS
from models.context_object import ContextObject, ContextGrade, DecayFunction
from bank.context_bank import ContextBank
from simulation.clock import SimulationClock
from measurement.metrics import MetricsCalculator
from generators.agent_exhaust import (
    BRIGHTLINE_SOW_SCENARIO,
    JORDAN_PARK_STAFFING_SCENARIO,
    TERRALOGIC_PAYMENT_SCENARIO,
    HARTWELL_PROPOSAL_SCENARIO,
)


# Page config
st.set_page_config(
    page_title="Acme Advisory - Context Bank Simulation",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)


def load_results() -> Optional[Dict[str, Any]]:
    """Load simulation results from JSON file."""
    results_path = Path("results/simulation_results.json")
    if results_path.exists():
        with open(results_path) as f:
            return json.load(f)
    return None


def load_decisions() -> Optional[Dict[str, Any]]:
    """Load all decisions from JSON file."""
    decisions_path = Path("results/all_decisions.json")
    if decisions_path.exists():
        with open(decisions_path) as f:
            return json.load(f)
    return None


def load_bank_state() -> Optional[Dict[str, Any]]:
    """Load final bank state from JSON file."""
    bank_path = Path("results/final_bank_state.json")
    if bank_path.exists():
        with open(bank_path) as f:
            return json.load(f)
    return None


# Sidebar
st.sidebar.title("🏢 Acme Advisory")
st.sidebar.markdown("**Context Bank Simulation**")

# Check for existing results
results = load_results()
has_results = results is not None

if has_results:
    st.sidebar.success("✓ Results loaded")
    st.sidebar.caption(f"Generated: {results.get('metadata', {}).get('timestamp', 'Unknown')[:10]}")
else:
    st.sidebar.warning("No results found")
    st.sidebar.caption("Run `python main.py` first")

st.sidebar.divider()

# Tab selection
tabs = st.tabs([
    "📋 Scenario Selector",
    "🏦 Context Bank Explorer",
    "🔍 Decision Trace Viewer",
    "📊 Comparative Dashboard",
    "🧠 Synthesis Engine",
    "⚡ Realism & Chaos",
])


# =============================================================================
# TAB 1: SCENARIO SELECTOR
# =============================================================================
with tabs[0]:
    st.header("Scenario Selector")
    st.markdown("""
    Select a scenario to explore how the Context Bank impacts decision-making.
    Each scenario represents a real organizational challenge that requires institutional memory.
    """)

    col1, col2 = st.columns(2)

    scenarios = {
        "Brightline SOW": {
            "scenario": BRIGHTLINE_SOW_SCENARIO,
            "description": "Brightline Consulting overbilled 40% in 2022. Now requires secondary approval from David Okafor.",
            "relevant_ctx": "CTX-001",
            "weeks": [3, 7, 11],
        },
        "Jordan Park Conflict": {
            "scenario": JORDAN_PARK_STAFFING_SCENARIO,
            "description": "Jordan Park has a documented HR conflict with Nexum Partners. Cannot be assigned to their work.",
            "relevant_ctx": "CTX-010",
            "weeks": [6, 11],
        },
        "TerraLogic Payment": {
            "scenario": TERRALOGIC_PAYMENT_SCENARIO,
            "description": "TerraLogic pays on 60-day cycles regardless of contract. Escalation before day 65 causes problems.",
            "relevant_ctx": "CTX-006",
            "weeks": [5, 10],
        },
        "Hartwell Override": {
            "scenario": HARTWELL_PROPOSAL_SCENARIO,
            "description": "Marcus Webb overrides go/no-go for Hartwell Group regardless of margin analysis.",
            "relevant_ctx": "CTX-003",
            "weeks": [4, 8],
        },
    }

    with col1:
        selected_scenario = st.selectbox(
            "Select Scenario",
            list(scenarios.keys()),
        )

    scenario_data = scenarios[selected_scenario]

    with col2:
        st.info(f"**Relevant Context:** {scenario_data['relevant_ctx']}")
        st.caption(f"Appears in weeks: {', '.join(map(str, scenario_data['weeks']))}")

    st.markdown(f"### {selected_scenario}")
    st.markdown(scenario_data["description"])

    st.divider()

    # Show scenario details
    st.subheader("Scenario Details")
    scenario = scenario_data["scenario"]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Workflow:** " + scenario.workflow_id)
    with col2:
        st.markdown("**Type:** " + scenario.scenario_type)
    with col3:
        st.markdown("**Ground Truth Context:** " + ", ".join(scenario.ground_truth_context_ids))

    st.markdown("#### Scenario Description")
    st.markdown(scenario.description)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Entities Involved:**")
        for key, value in scenario.entities.items():
            st.markdown(f"- **{key}:** {value}")

    with col2:
        st.success(f"**Correct Action:** {scenario.correct_action}")
        st.error(f"**Incorrect Action:** {scenario.incorrect_action}")

    # Show relevant context object
    st.divider()
    st.subheader("Relevant Context Object")

    relevant_ctx_id = scenario_data["relevant_ctx"]
    relevant_ctx = next((obj for obj in SEEDED_CONTEXT_OBJECTS if obj.id == relevant_ctx_id), None)

    if relevant_ctx:
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown(f"**{relevant_ctx.id}**")
            st.markdown(relevant_ctx.payload)
        with col2:
            st.metric("Confidence", f"{relevant_ctx.confidence_at_creation:.0%}")
            st.caption(f"Grade: {relevant_ctx.context_grade.value if relevant_ctx.context_grade else 'Unknown'}")
            st.caption(f"Decay: {relevant_ctx.decay_function.value}")


# =============================================================================
# TAB 2: CONTEXT BANK EXPLORER
# =============================================================================
with tabs[1]:
    st.header("Context Bank Explorer")
    st.markdown("Explore the seeded context objects and their relationships.")

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        grade_filter = st.selectbox(
            "Filter by Grade",
            ["All"] + [g.value for g in ContextGrade],
        )

    with col2:
        decay_filter = st.selectbox(
            "Filter by Decay Function",
            ["All"] + [d.value for d in DecayFunction],
        )

    with col3:
        confidence_threshold = st.slider(
            "Minimum Confidence",
            min_value=0.0,
            max_value=1.0,
            value=0.0,
            step=0.1,
        )

    # Filter objects
    filtered_objects = SEEDED_CONTEXT_OBJECTS.copy()

    if grade_filter != "All":
        filtered_objects = [o for o in filtered_objects if o.context_grade and o.context_grade.value == grade_filter]

    if decay_filter != "All":
        filtered_objects = [o for o in filtered_objects if o.decay_function.value == decay_filter]

    filtered_objects = [o for o in filtered_objects if o.confidence_at_creation >= confidence_threshold]

    st.caption(f"Showing {len(filtered_objects)} of {len(SEEDED_CONTEXT_OBJECTS)} objects")

    # Display objects
    for obj in filtered_objects:
        with st.expander(f"{obj.id} - {obj.payload[:50]}..."):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"**Payload:**\n{obj.payload}")
                if obj.structured_data:
                    st.markdown("**Structured Data:**")
                    st.json(obj.structured_data)

            with col2:
                st.metric("Confidence", f"{obj.confidence_at_creation:.0%}")
                st.caption(f"**Grade:** {obj.context_grade.value if obj.context_grade else 'N/A'}")
                st.caption(f"**Lineage:** {obj.org_lineage.value if obj.org_lineage else 'N/A'}")
                st.caption(f"**Decay:** {obj.decay_function.value}")
                st.caption(f"**Workflow:** {obj.workflow_id or 'N/A'}")

    st.divider()

    # Confidence decay visualization
    st.subheader("Confidence Decay Over Time")

    # Calculate decay curves for each object
    weeks = list(range(1, 13))
    decay_data = []

    for obj in SEEDED_CONTEXT_OBJECTS[:6]:  # Show first 6 for clarity
        for week in weeks:
            confidence = obj.compute_current_confidence(week)
            decay_data.append({
                "Object": obj.id,
                "Week": week,
                "Confidence": confidence,
            })

    if decay_data:
        fig = px.line(
            decay_data,
            x="Week",
            y="Confidence",
            color="Object",
            title="Context Object Confidence Decay",
            markers=True,
        )
        fig.update_layout(yaxis_range=[0, 1])
        st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# TAB 3: DECISION TRACE VIEWER
# =============================================================================
with tabs[2]:
    st.header("Decision Trace Viewer")

    decisions_data = load_decisions()

    if not decisions_data:
        st.warning("No decisions found. Run the simulation first with `python main.py`.")
    else:
        # Condition selector
        condition = st.radio(
            "Condition",
            ["with_bank", "without_bank"],
            format_func=lambda x: "WITH Context Bank" if x == "with_bank" else "WITHOUT Context Bank",
            horizontal=True,
        )

        decisions = decisions_data.get(condition, [])

        st.caption(f"Total decisions: {len(decisions)}")

        # Week filter
        decision_weeks = sorted(set(d["week"] for d in decisions))
        selected_week = st.selectbox(
            "Filter by Week",
            ["All"] + decision_weeks,
        )

        filtered_decisions = decisions
        if selected_week != "All":
            filtered_decisions = [d for d in decisions if d["week"] == selected_week]

        # Display decisions
        for decision in filtered_decisions:
            outcome_color = "green" if decision["outcome"] == "correct" else "red"
            outcome_icon = "✓" if decision["outcome"] == "correct" else "✗"

            with st.expander(
                f"{outcome_icon} Week {decision['week']}: {decision['scenario_type']} ({decision['outcome']})",
                expanded=len(filtered_decisions) <= 3,
            ):
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.markdown(f"**Decision:** {decision['decision_taken']}")
                    st.markdown(f"**Agent:** {decision['agent_id']}")

                with col2:
                    st.metric("Outcome", decision["outcome"].upper())
                    if decision.get("context_used"):
                        st.success(f"Context Used: {', '.join(decision['context_used'])}")
                    elif decision.get("context_retrieved"):
                        st.warning(f"Context Retrieved: {', '.join(decision['context_retrieved'])}")
                    else:
                        st.info("No context available")


# =============================================================================
# TAB 4: COMPARATIVE DASHBOARD
# =============================================================================
with tabs[3]:
    st.header("Comparative Dashboard")

    if not results:
        st.warning("No results found. Run the simulation first with `python main.py`.")
    else:
        comparison = results.get("comparison", {})
        without = comparison.get("without_bank", {})
        with_bank = comparison.get("with_bank", {})
        improvement = comparison.get("comparison", {})

        # Key metrics
        st.subheader("Key Metrics")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            without_acc = without.get("summary", {}).get("accuracy", 0)
            with_acc = with_bank.get("summary", {}).get("accuracy", 0)
            st.metric(
                "Decision Accuracy",
                f"{with_acc:.1f}%",
                f"+{improvement.get('accuracy_improvement', 0):.1f}%",
            )

        with col2:
            st.metric(
                "Errors Avoided",
                improvement.get("errors_avoided", 0),
            )

        with col3:
            st.metric(
                "Final Bank Size",
                with_bank.get("summary", {}).get("final_bank_size", 0),
            )

        with col4:
            st.metric(
                "DQS Improvement",
                f"+{improvement.get('dqs_improvement', 0):.1f}",
            )

        st.divider()

        # Accuracy comparison chart
        st.subheader("Accuracy Comparison")

        col1, col2 = st.columns(2)

        with col1:
            # Bar chart comparing conditions
            fig = go.Figure(data=[
                go.Bar(
                    name="Without Bank",
                    x=["Decision Accuracy"],
                    y=[without_acc],
                    marker_color="indianred",
                ),
                go.Bar(
                    name="With Bank",
                    x=["Decision Accuracy"],
                    y=[with_acc],
                    marker_color="seagreen",
                ),
            ])
            fig.update_layout(
                title="Accuracy by Condition",
                yaxis_range=[0, 100],
                barmode="group",
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Pie chart of outcomes
            without_correct = without.get("summary", {}).get("correct_decisions", 0)
            without_incorrect = without.get("summary", {}).get("incorrect_decisions", 0)
            with_correct = with_bank.get("summary", {}).get("correct_decisions", 0)
            with_incorrect = with_bank.get("summary", {}).get("incorrect_decisions", 0)

            fig = go.Figure(data=[
                go.Pie(
                    labels=["Without Bank Correct", "Without Bank Incorrect",
                            "With Bank Correct", "With Bank Incorrect"],
                    values=[without_correct, without_incorrect, with_correct, with_incorrect],
                    hole=0.4,
                    marker_colors=["lightcoral", "indianred", "lightgreen", "seagreen"],
                ),
            ])
            fig.update_layout(title="Decision Outcomes")
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # Week-by-week progression
        st.subheader("Week-by-Week Performance")

        without_ehr = without.get("primary_metrics", {}).get("exception_handling_rates", [])
        with_ehr = with_bank.get("primary_metrics", {}).get("exception_handling_rates", [])
        bank_growth = with_bank.get("secondary_metrics", {}).get("context_object_growth", [])

        # Find weeks with decisions
        max_weeks = max(len(without_ehr), len(with_ehr), len(bank_growth))
        progression_data = []

        for week in range(max_weeks):
            w_val = without_ehr[week] if week < len(without_ehr) else 0
            wb_val = with_ehr[week] if week < len(with_ehr) else 0
            bank_size = bank_growth[week] if week < len(bank_growth) else 0

            if w_val > 0 or wb_val > 0 or bank_size > 0:
                progression_data.append({
                    "Week": week + 1,
                    "WITHOUT Bank": w_val,
                    "WITH Bank": wb_val,
                    "Bank Size": bank_size,
                })

        if progression_data:
            col1, col2 = st.columns(2)

            with col1:
                fig = px.line(
                    progression_data,
                    x="Week",
                    y=["WITHOUT Bank", "WITH Bank"],
                    title="Decision Accuracy Over Time",
                    markers=True,
                )
                fig.update_layout(yaxis_range=[0, 100], yaxis_title="Accuracy (%)")
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                fig = px.bar(
                    progression_data,
                    x="Week",
                    y="Bank Size",
                    title="Context Bank Growth",
                )
                st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # Summary table
        st.subheader("Summary Statistics")

        summary_data = {
            "Metric": [
                "Total Decisions",
                "Correct Decisions",
                "Incorrect Decisions",
                "Overall Accuracy",
                "Final Bank Size",
                "Final Avg Confidence",
            ],
            "WITHOUT Bank": [
                without.get("summary", {}).get("total_decisions", 0),
                without.get("summary", {}).get("correct_decisions", 0),
                without.get("summary", {}).get("incorrect_decisions", 0),
                f"{without.get('summary', {}).get('accuracy', 0):.1f}%",
                "N/A",
                "N/A",
            ],
            "WITH Bank": [
                with_bank.get("summary", {}).get("total_decisions", 0),
                with_bank.get("summary", {}).get("correct_decisions", 0),
                with_bank.get("summary", {}).get("incorrect_decisions", 0),
                f"{with_bank.get('summary', {}).get('accuracy', 0):.1f}%",
                with_bank.get("summary", {}).get("final_bank_size", 0),
                f"{with_bank.get('summary', {}).get('final_avg_confidence', 0):.2f}",
            ],
        }

        st.table(summary_data)


# =============================================================================
# TAB 5: SYNTHESIS ENGINE
# =============================================================================
with tabs[4]:
    st.header("Synthesis Engine")
    st.markdown("""
    The Synthesis Engine transforms raw context accumulation into active organizational intelligence
    through three key operations:

    1. **Pattern Crystallization** - Promotes recurring learnings to high-confidence context
    2. **Validation Propagation** - Propagates validation signals through provenance chains
    3. **Adaptive Decay** - Adjusts decay rates based on retrieval/validation frequency
    """)

    if not results:
        st.warning("No results found. Run the simulation first with `python main.py`.")
    else:
        comparison = results.get("comparison", {})
        with_bank = comparison.get("with_bank", {})
        synthesis = with_bank.get("synthesis_metrics", {})

        if not synthesis or not synthesis.get("synthesis_results"):
            st.info("No synthesis data available. Synthesis runs every 3 weeks in the simulation.")
        else:
            # Key synthesis metrics
            st.subheader("Synthesis Summary")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "Patterns Crystallized",
                    synthesis.get("total_patterns_crystallized", 0),
                    help="Recurring patterns promoted to high-confidence context",
                )

            with col2:
                st.metric(
                    "Validations Propagated",
                    synthesis.get("total_validations_propagated", 0),
                    help="Confidence boosts propagated through derivation chains",
                )

            with col3:
                st.metric(
                    "Decay Adjustments",
                    synthesis.get("total_decay_adjustments", 0),
                    help="Objects with reduced decay rates due to high activity",
                )

            with col4:
                scores = synthesis.get("intelligence_scores", [])
                avg_score = sum(s for s in scores if s > 0) / max(1, len([s for s in scores if s > 0]))
                st.metric(
                    "Avg Intelligence Score",
                    f"{avg_score:.2f}",
                    help="Average synthesis intelligence score (0-1)",
                )

            st.divider()

            # Intelligence score over time
            st.subheader("Synthesis Intelligence Over Time")

            scores = synthesis.get("intelligence_scores", [])
            if scores:
                # Find synthesis weeks
                synthesis_data = []
                for i, score in enumerate(scores):
                    if score > 0:
                        week = i + 1
                        synthesis_data.append({"Week": week, "Intelligence Score": score})

                if synthesis_data:
                    fig = px.bar(
                        synthesis_data,
                        x="Week",
                        y="Intelligence Score",
                        title="Synthesis Intelligence Score by Week",
                    )
                    fig.update_layout(yaxis_range=[0, 1])
                    st.plotly_chart(fig, use_container_width=True)

            st.divider()

            # Detailed synthesis results
            st.subheader("Synthesis Pass Details")

            synthesis_results = synthesis.get("synthesis_results", [])
            for i, sr in enumerate(synthesis_results):
                if sr is not None:
                    week = i + 1
                    with st.expander(f"Week {week} Synthesis Pass"):
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.markdown(f"**Patterns Crystallized:** {sr.get('patterns_crystallized', 0)}")
                            if sr.get('new_objects_created'):
                                st.markdown("New objects:")
                                for obj_id in sr.get('new_objects_created', []):
                                    st.code(obj_id)

                        with col2:
                            st.markdown(f"**Validations Propagated:** {sr.get('validations_propagated', 0)}")
                            if sr.get('confidence_boosts'):
                                st.markdown("Confidence boosts:")
                                for obj_id, conf in sr.get('confidence_boosts', {}).items():
                                    st.text(f"{obj_id}: {conf:.2f}")

                        with col3:
                            st.markdown(f"**Decay Adjustments:** {sr.get('decay_rates_adjusted', 0)}")
                            if sr.get('objects_updated'):
                                st.markdown("Updated objects:")
                                for obj_id in sr.get('objects_updated', [])[:5]:
                                    st.code(obj_id)

            st.divider()

            # Explanation
            st.subheader("How Synthesis Works")

            st.markdown("""
            #### Pattern Crystallization
            When multiple context objects reference the same entity and share common themes,
            the synthesis engine creates a new "crystallized" context object that:
            - Has **permanent** decay (won't lose confidence over time)
            - Links back to source objects via derivation chains
            - Represents validated organizational knowledge

            #### Validation Propagation
            When an agent validates context by using it successfully:
            - The validated object gets a confidence boost
            - Objects in its derivation chain also receive (smaller) boosts
            - This creates a "validation cascade" through related knowledge

            #### Adaptive Decay
            Objects that are frequently read, used, or validated:
            - Have their decay rates reduced
            - May be upgraded from linear to step-function decay
            - Effectively become "evergreen" institutional memory
            """)


# =============================================================================
# TAB 6: REALISM & CHAOS
# =============================================================================
with tabs[5]:
    st.header("Realism & Chaos Engine")
    st.markdown("""
    The v3.0 Realism Enhancement introduces empirically-calibrated parameters and chaos mechanisms
    that test the Context Bank's resilience under realistic organizational disruptions.
    """)

    # Check for realism data
    realism_mode = results.get("metadata", {}).get("realism_mode", "Standard") if results else "Standard"
    realism_config = results.get("metadata", {}).get("realism_config") if results else None

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Current Mode")
        if realism_mode == "Standard":
            st.info(f"**Mode:** {realism_mode}")
            st.caption("Run with `--chaos` or `--bpi` flags to enable realism features")
        else:
            st.success(f"**Mode:** {realism_mode}")

    with col2:
        st.subheader("Available Modes")
        st.markdown("""
        | Command | Description |
        |---------|-------------|
        | `python main.py` | Standard simulation |
        | `python main.py --chaos` | Chaos injection enabled |
        | `python main.py --bpi` | BPI timing calibration |
        | `python main.py --full-realism` | Both chaos and BPI |
        """)

    st.divider()

    # BPI Calibration Section
    st.subheader("BPI Challenge Calibration")
    st.markdown("""
    Event timing distributions calibrated from real process mining data:
    - **BPI Challenge 2012**: Loan application process (13,087 cases, 262,200 events)
    - **BPI Challenge 2017**: Extended loan process (31,509 cases, 1.2M events)
    """)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Hourly Distribution**")
        st.markdown("Peak activity: 10-11 AM")

        # Create sample hourly distribution chart
        hours = list(range(24))
        weights = [
            0.01, 0.01, 0.01, 0.01, 0.01, 0.01,  # 0-5
            0.02, 0.04, 0.07, 0.09, 0.10, 0.10,  # 6-11
            0.08, 0.09, 0.09, 0.08, 0.06, 0.05,  # 12-17
            0.03, 0.02, 0.01, 0.01, 0.01, 0.01,  # 18-23
        ]
        fig = px.bar(x=hours, y=weights, title="Event Distribution by Hour")
        fig.update_layout(xaxis_title="Hour", yaxis_title="Probability")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("**Daily Distribution**")
        st.markdown("Weekday-weighted, minimal weekend activity")

        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        day_weights = [0.18, 0.20, 0.20, 0.20, 0.18, 0.03, 0.01]
        fig = px.bar(x=days, y=day_weights, title="Event Distribution by Day")
        fig.update_layout(xaxis_title="Day", yaxis_title="Probability")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Chaos Engine Section
    st.subheader("Chaos Mechanisms")
    st.markdown("""
    Chaos events test the Context Bank's resilience under realistic organizational disruptions.
    """)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Knowledge Departure")
        st.markdown("""
        **What:** Senior staff leave the organization, taking undocumented knowledge.

        **Impact:**
        - Context objects created by departed staff have accelerated decay
        - Tacit knowledge not deposited in bank is lost forever
        - Tests whether the bank captures institutional memory effectively
        """)

        st.markdown("#### Agent Drift")
        st.markdown("""
        **What:** Agents begin making suboptimal decisions due to "model drift".

        **Impact:**
        - Higher error rate for affected agents
        - May ignore retrieved context with some probability
        - Tests whether context retrieval can correct drifting behavior
        """)

    with col2:
        st.markdown("#### Policy Contradiction")
        st.markdown("""
        **What:** New policies are introduced that contradict existing context.

        **Impact:**
        - Contradicting context objects deposited into bank
        - Tests contradiction detection system
        - Simulates organizational policy conflicts
        """)

        st.markdown("#### Workload Surge")
        st.markdown("""
        **What:** Sudden spike in event volume (2-3x normal).

        **Impact:**
        - Event count multiplied during surge weeks
        - May cause "overload errors" as agents process more decisions
        - Tests bank performance under load
        """)

    st.divider()

    # Chaos impact display (if chaos was enabled)
    if realism_config and realism_config.get("chaos", {}).get("enabled"):
        st.subheader("Chaos Impact Summary")

        with_bank_summary = results.get("with_bank_summary", {})
        chaos_summary = with_bank_summary.get("chaos_summary", {})

        if chaos_summary:
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total Chaos Events", chaos_summary.get("total_events", 0))

            with col2:
                st.metric("Knowledge Departures", chaos_summary.get("knowledge_departures", 0))

            with col3:
                st.metric("Agent Drifts", chaos_summary.get("agent_drifts", 0))

            with col4:
                st.metric("Objects Degraded", chaos_summary.get("total_objects_degraded", 0))

            # Show detailed impacts
            impacts = chaos_summary.get("impacts", [])
            if impacts:
                st.markdown("#### Chaos Event Timeline")
                for impact in impacts:
                    event = impact.get("event", {})
                    week = event.get("week", "?")
                    chaos_type = event.get("chaos_type", "unknown")
                    description = impact.get("impact_description", "")

                    st.markdown(f"- **Week {week}** - `{chaos_type}`: {description}")
    else:
        st.info("Chaos was not enabled for this simulation run. Use `--chaos` flag to enable.")

    st.divider()

    # Configuration details
    st.subheader("Configuration Reference")

    with st.expander("Chaos Event Schedule (Default)"):
        st.markdown("""
        | Week | Event Type | Target |
        |------|------------|--------|
        | 4 | Knowledge Departure | david_okafor |
        | 5 | Policy Contradiction | CTX-001 (Brightline) |
        | 6 | Agent Drift | vendor_agent |
        | 7 | Workload Surge | All |
        | 8 | Knowledge Departure | marcus_webb |
        | 9 | Policy Contradiction | CTX-006 (TerraLogic) |
        | 10 | Agent Drift | billing_agent |
        """)

    with st.expander("BPI Dataset Statistics"):
        st.markdown("""
        **BPI Challenge 2012**
        - Total cases: 13,087
        - Total events: 262,200
        - Average events/case: 20.04
        - Average case duration: 8.62 days
        - Number of activities: 24
        - Number of resources: 69

        **BPI Challenge 2017**
        - Total cases: 31,509
        - Total events: 1,202,267
        - Average events/case: 38.15
        - Average case duration: 22.27 days
        - Number of activities: 26
        - Number of resources: 145
        """)


# Footer
st.divider()
st.caption("Acme Advisory Context Bank Simulation | Built with Streamlit")
st.caption("Run simulation: `python main.py` | Launch UI: `streamlit run app.py`")
