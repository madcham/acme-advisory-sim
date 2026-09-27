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


# =============================================================================
# PAGE CONFIG & STYLING
# =============================================================================
st.set_page_config(
    page_title="Acme Advisory - Context Bank Simulation",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better readability
st.markdown("""
<style>
    .metric-help {
        font-size: 0.8em;
        color: #666;
        margin-top: -10px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# HUMAN-READABLE MAPPINGS
# =============================================================================

# Grade explanations for dropdowns
GRADE_LABELS = {
    "All": "All Grades",
    "institutional": "🏛️ Institutional — Core business rules that define how the organization operates",
    "compliance": "📋 Compliance — Required procedures and regulatory requirements",
    "operational": "⚙️ Operational — Day-to-day process knowledge and best practices",
    "deprecated": "🚫 Deprecated — Outdated rules that may still appear in decisions",
}

GRADE_HELP = """
**Knowledge Grades** classify how important each piece of institutional memory is:
- **Institutional**: Critical rules (e.g., "Always get secondary approval for Brightline")
- **Compliance**: Required procedures (e.g., audit trail requirements)
- **Operational**: Best practices (e.g., "TerraLogic pays on 60-day cycles")
- **Deprecated**: Outdated but not yet removed
"""

# Decay function explanations
DECAY_LABELS = {
    "All": "All Decay Types",
    "linear": "📉 Gradual Decline — Confidence decreases steadily over time",
    "step_function": "📊 Milestone Drops — Confidence drops at specific intervals",
    "permanent": "🔒 Never Decays — Critical knowledge that stays reliable forever",
}

DECAY_HELP = """
**Decay Functions** control how knowledge reliability changes over time:
- **Gradual Decline**: Confidence drops a little each week (e.g., 5%/week)
- **Milestone Drops**: Confidence stays stable, then drops at milestones (weeks 4, 8, 12)
- **Never Decays**: Evergreen knowledge that remains 100% reliable
"""

# Metric definitions
METRICS_GLOSSARY = {
    "DQS": ("Decision Quality Score", "Percentage of correct decisions made each week. Higher is better."),
    "EHR": ("Exception Handling Rate", "Percentage of edge cases handled correctly without escalation."),
    "IMU": ("Institutional Memory Utilization", "Percentage of decisions where agents successfully used relevant context."),
    "Confidence": ("Knowledge Reliability", "How trustworthy a piece of knowledge is (0-100%). Decays over time unless validated."),
}


# =============================================================================
# DATA LOADING
# =============================================================================

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


def format_grade(grade_value: str) -> str:
    """Convert grade enum value to human-readable label."""
    return GRADE_LABELS.get(grade_value, grade_value)


def format_decay(decay_value: str) -> str:
    """Convert decay enum value to human-readable label."""
    return DECAY_LABELS.get(decay_value, decay_value)


# =============================================================================
# SIDEBAR
# =============================================================================
st.sidebar.title("🏢 Acme Advisory")
st.sidebar.markdown("**Context Bank Simulation**")
st.sidebar.caption("_Institutional Memory for AI Agents_")

# Check for existing results
results = load_results()
has_results = results is not None

if has_results:
    st.sidebar.success("✓ Simulation results loaded")
    timestamp = results.get('metadata', {}).get('timestamp', 'Unknown')[:10]
    realism_mode = results.get('metadata', {}).get('realism_mode', 'Standard')
    st.sidebar.caption(f"Run date: {timestamp}")
    st.sidebar.caption(f"Mode: {realism_mode}")
else:
    st.sidebar.warning("No results found")
    st.sidebar.caption("Run `python main.py` first")

st.sidebar.divider()

# Quick glossary in sidebar
with st.sidebar.expander("📖 Quick Glossary"):
    st.markdown("""
    **Context Bank**: Repository of institutional knowledge that agents can query

    **Decision Quality**: % of correct decisions

    **Confidence**: How reliable a piece of knowledge is (0-100%)

    **Decay**: How confidence decreases over time

    **Chaos Events**: Simulated disruptions (staff leaving, policy changes)
    """)

st.sidebar.divider()
st.sidebar.caption("Run: `python main.py`")
st.sidebar.caption("UI: `streamlit run app.py`")

# =============================================================================
# WELCOME & TUTORIAL SECTION
# =============================================================================

# Session state for tutorial
if "show_welcome" not in st.session_state:
    st.session_state.show_welcome = True
if "tutorial_step" not in st.session_state:
    st.session_state.tutorial_step = 0

# Welcome Banner
if st.session_state.show_welcome:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 2rem; border-radius: 10px; margin-bottom: 1rem;">
        <h1 style="color: white; margin: 0;">🏢 Context Bank Simulation</h1>
        <p style="color: rgba(255,255,255,0.9); font-size: 1.2rem; margin-top: 0.5rem;">
            What happens when agents and employees operate on fragmented, siloed knowledge<br/>
            vs. a unified, continuously-updated institutional memory?
        </p>
    </div>
    """, unsafe_allow_html=True)

    # The Problem & Solution
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        ### 🚨 The Problem: Fragmented Reality

        Without a unified knowledge system, every entity operates on its own version of "how things work":

        - **Agents** retrieve context from siloed, outdated sources
        - **Employees** carry knowledge that never gets captured
        - **Policies** contradict each other across departments
        - **Decisions** get made on inconsistent assumptions

        **Result:** The same mistakes happen repeatedly because the right hand doesn't know what the left hand learned.
        """)

    with col2:
        st.markdown("""
        ### 💡 The Solution: Unified Context Bank

        A **single source of truth** that all agents and systems read from and write to — continuously updated from three exhaust streams:

        | Exhaust Stream | What Flows In |
        |----------------|---------------|
        | 📊 **Structured** | Workflow events, exceptions, process outcomes |
        | 💬 **Behavioral** | Knowledge exchanged between employees |
        | 🤖 **Agent** | AI decisions, reasoning, and learnings |

        **Everyone operates on the same reality** — no more silos, no more "I didn't know that was the rule."
        """)

    st.divider()

    # Key Results Teaser
    if has_results:
        comparison = results.get("comparison", {})
        without = comparison.get("without_bank", {})
        with_bank = comparison.get("with_bank", {})

        without_acc = without.get("summary", {}).get("accuracy", 0)
        with_acc = with_bank.get("summary", {}).get("accuracy", 0)
        improvement = with_acc - without_acc
        errors_avoided = comparison.get("comparison", {}).get("errors_avoided", 0)

        st.markdown("### 📈 Your Simulation Results")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Without Context Bank", f"{without_acc:.0f}%", help="Baseline accuracy")
        with col2:
            st.metric("With Context Bank", f"{with_acc:.0f}%", f"+{improvement:.0f}%", help="Improved accuracy")
        with col3:
            st.metric("Mistakes Prevented", errors_avoided, help="Errors avoided")
        with col4:
            bank_size = with_bank.get("summary", {}).get("final_bank_size", 0)
            st.metric("Knowledge Items", bank_size, help="Institutional memory captured")

        st.success(f"**Unified knowledge improved decision accuracy by {improvement:.0f}%** — preventing {errors_avoided} costly mistakes that occur when agents operate on fragmented, siloed information.")

    else:
        st.warning("""
        **No simulation results yet.** Run the simulation to see the impact:
        ```bash
        python main.py --full-realism
        ```
        """)

    st.divider()

    # Three Exhaust Types Explained
    with st.expander("📖 **Understanding the Three Exhaust Types** (click to expand)", expanded=False):
        st.markdown("""
        The Context Bank captures organizational knowledge from three distinct data streams:
        """)

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("""
            ### 📊 Structured Exhaust

            **Source:** Workflow systems, ERPs, ticketing tools

            **What it captures:**
            - Process execution logs (OCEL 2.0 format)
            - Event timestamps and durations
            - Success/failure outcomes
            - Exception patterns

            **Example:**
            > "Invoice #4521 was escalated at step 3 because amount exceeded $50K threshold"

            **Why it matters:**
            Process patterns reveal when rules are being bent or broken.
            """)

        with col2:
            st.markdown("""
            ### 💬 Behavioral Exhaust

            **Source:** Slack, email, meetings, hallway conversations

            **What it captures:**
            - Knowledge exchanges between staff
            - Questions from new hires
            - Answers from experienced employees
            - Tacit knowledge being transferred

            **Example:**
            > New hire: "Why is this client flagged?"
            > Senior: "Brightline overbilled 40% in 2022. Always get secondary approval from David."

            **Why it matters:**
            This is how tribal knowledge gets passed down—and lost when people leave.
            """)

        with col3:
            st.markdown("""
            ### 🤖 Agent Exhaust

            **Source:** AI agent decisions and reasoning

            **What it captures:**
            - Decision rationale
            - Context retrieved from bank
            - Whether context was actually used
            - Learnings deposited back

            **Example:**
            > "Approved Brightline SOW after confirming secondary approval from David Okafor per CTX-001"

            **Why it matters:**
            Agents learn from decisions and share knowledge with future agents.
            """)

    # Interactive Tutorial
    with st.expander("🎓 **Guided Tour: See the Context Bank in Action** (click to expand)", expanded=False):
        st.markdown("""
        Follow these steps to understand the power of institutional memory:
        """)

        st.markdown("""
        ---

        ### Step 1: See What Knowledge Prevents Mistakes

        👉 **Go to the "🎯 Test Scenarios" tab**

        1. Select **"🔴 Brightline Overbilling Risk"**
        2. Read the scenario — Brightline overbilled 40% in 2022
        3. See the **knowledge item** (CTX-001) that prevents this mistake
        4. Notice: Without this knowledge, an agent would just approve the SOW

        ---

        ### Step 2: Compare Decisions With vs Without the Bank

        👉 **Go to the "🔍 Decision History" tab**

        1. Toggle to **"WITHOUT Context Bank"**
        2. Find a decision marked ❌ — the agent made a mistake
        3. Toggle to **"WITH Context Bank"**
        4. Find the same scenario — now marked ✅
        5. See the **"📚 Used knowledge"** that made the difference

        ---

        ### Step 3: See the Overall Impact

        👉 **Go to the "📊 Results Dashboard" tab**

        1. Look at the **accuracy comparison** — before vs after
        2. Check the **"Mistakes Prevented"** metric
        3. See the **week-by-week chart** — accuracy improves as knowledge accumulates

        ---

        ### Step 4: Test System Resilience

        👉 **Go to the "⚡ Stress Testing" tab**

        1. See what **disruptions** were injected (staff leaving, policies changing)
        2. Notice the system **maintained high accuracy** despite chaos
        3. This proves the Context Bank preserves knowledge even under stress

        ---

        ### Step 5: Watch Knowledge Evolve

        👉 **Go to the "🧠 Learning Engine" tab**

        1. See how many **patterns** were identified
        2. See how **successful decisions** reinforced knowledge reliability
        3. This is how the system gets smarter over time
        """)

    # Quick Commands
    with st.expander("⚡ **Quick Start Commands**", expanded=False):
        st.markdown("""
        ### Run Simulations

        ```bash
        # Standard simulation (no stress testing)
        python main.py

        # With organizational disruptions (staff leaving, policy conflicts)
        python main.py --chaos

        # With real-world timing patterns (BPI Challenge data)
        python main.py --bpi

        # Full realism: both chaos and BPI calibration
        python main.py --full-realism
        ```

        ### View Results

        ```bash
        # Launch this interactive UI
        streamlit run app.py

        # View text summary
        cat results/summary.md

        # Open business dashboard (charts)
        open results/business_dashboard.html
        ```

        ### Output Files

        | File | Description |
        |------|-------------|
        | `results/simulation_results.json` | Complete metrics and data |
        | `results/all_decisions.json` | Every decision made |
        | `results/final_bank_state.json` | Context Bank snapshot |
        | `results/summary.md` | Human-readable summary |
        | `results/business_dashboard.html` | Visual charts |
        """)

    # Dismiss button
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("✓ Got it — Show me the simulation", use_container_width=True, type="primary"):
            st.session_state.show_welcome = False
            st.rerun()

    st.divider()

else:
    # Collapsed welcome - just show a small banner to bring it back
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("**🏢 Context Bank Simulation** — Unified institutional memory vs. fragmented silos")
    with col2:
        if st.button("📖 Show Tutorial"):
            st.session_state.show_welcome = True
            st.rerun()
    st.divider()

# =============================================================================
# TABS
# =============================================================================
tabs = st.tabs([
    "🎯 Test Scenarios",
    "📚 Knowledge Library",
    "🔍 Decision History",
    "📊 Results Dashboard",
    "🧠 Learning Engine",
    "⚡ Stress Testing",
])


# =============================================================================
# TAB 1: TEST SCENARIOS (formerly Scenario Selector)
# =============================================================================
with tabs[0]:
    st.header("🎯 Test Scenarios")
    st.markdown("""
    Each scenario represents a real business situation where having (or lacking) institutional
    memory makes the difference between a correct and incorrect decision.

    **Try it:** Select a scenario below to see what context the agent needs to make the right call.
    """)

    col1, col2 = st.columns([2, 1])

    scenarios = {
        "🔴 Brightline Overbilling Risk": {
            "scenario": BRIGHTLINE_SOW_SCENARIO,
            "description": "Brightline Consulting overbilled 40% in 2022. Any new SOW must get secondary approval from David Okafor before signing.",
            "relevant_ctx": "CTX-001",
            "weeks": [3, 7, 11],
            "risk_level": "High",
            "what_could_go_wrong": "Agent signs SOW without secondary approval → Risk of another overbilling incident",
        },
        "🟡 Jordan Park HR Conflict": {
            "scenario": JORDAN_PARK_STAFFING_SCENARIO,
            "description": "Jordan Park has a documented HR conflict with Nexum Partners. He cannot be assigned to any Nexum projects.",
            "relevant_ctx": "CTX-010",
            "weeks": [6, 11],
            "risk_level": "Medium",
            "what_could_go_wrong": "Agent assigns Jordan to Nexum project → HR complaint, potential lawsuit",
        },
        "🟡 TerraLogic Payment Cycle": {
            "scenario": TERRALOGIC_PAYMENT_SCENARIO,
            "description": "TerraLogic always pays on 60-day cycles, regardless of contract terms. Escalating before day 65 damages the relationship.",
            "relevant_ctx": "CTX-006",
            "weeks": [5, 10],
            "risk_level": "Medium",
            "what_could_go_wrong": "Agent escalates payment at day 45 → Client relationship damaged",
        },
        "🟢 Hartwell Override Rule": {
            "scenario": HARTWELL_PROPOSAL_SCENARIO,
            "description": "Marcus Webb always overrides standard go/no-go decisions for Hartwell Group. Don't waste time on detailed margin analysis.",
            "relevant_ctx": "CTX-003",
            "weeks": [4, 8],
            "risk_level": "Low",
            "what_could_go_wrong": "Agent spends hours on analysis that will be overridden anyway → Wasted effort",
        },
    }

    with col1:
        selected_scenario = st.selectbox(
            "Choose a scenario to explore:",
            list(scenarios.keys()),
            help="Each scenario tests whether the agent has access to critical institutional knowledge"
        )

    scenario_data = scenarios[selected_scenario]

    with col2:
        risk_colors = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
        st.metric("Risk Level", f"{risk_colors[scenario_data['risk_level']]} {scenario_data['risk_level']}")
        st.caption(f"Relevant knowledge: `{scenario_data['relevant_ctx']}`")

    st.divider()

    # Main scenario display
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("The Situation")
        st.markdown(scenario_data["description"])

        st.markdown("**⚠️ What could go wrong without this knowledge:**")
        st.warning(scenario_data["what_could_go_wrong"])

    with col2:
        st.subheader("Decision Windows")
        st.markdown(f"This scenario appears in **weeks {', '.join(map(str, scenario_data['weeks']))}**")

        scenario = scenario_data["scenario"]
        st.success(f"✅ **Correct:** {scenario.correct_action}")
        st.error(f"❌ **Wrong:** {scenario.incorrect_action}")

    st.divider()

    # Show the actual context object
    st.subheader("📄 The Knowledge That Prevents This Mistake")

    relevant_ctx_id = scenario_data["relevant_ctx"]
    relevant_ctx = next((obj for obj in SEEDED_CONTEXT_OBJECTS if obj.id == relevant_ctx_id), None)

    if relevant_ctx:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info(f"**{relevant_ctx.id}**\n\n{relevant_ctx.payload}")
        with col2:
            confidence_pct = relevant_ctx.confidence_at_creation * 100
            st.metric(
                "Reliability",
                f"{confidence_pct:.0f}%",
                help="How confident we are in this knowledge (100% = fully reliable)"
            )
            grade = relevant_ctx.context_grade.value if relevant_ctx.context_grade else 'Unknown'
            st.caption(f"**Type:** {grade.title()}")
            decay = relevant_ctx.decay_function.value
            st.caption(f"**Decay:** {decay.replace('_', ' ').title()}")


# =============================================================================
# TAB 2: KNOWLEDGE LIBRARY (formerly Context Bank Explorer)
# =============================================================================
with tabs[1]:
    st.header("📚 Knowledge Library")
    st.markdown("""
    Browse all institutional knowledge stored in the Context Bank. Use the filters below
    to find specific types of knowledge or filter by reliability level.
    """)

    # Filters with better labels
    st.subheader("🔍 Filter Knowledge")

    col1, col2, col3 = st.columns(3)

    with col1:
        grade_options = ["All"] + [g.value for g in ContextGrade]
        grade_filter = st.selectbox(
            "Knowledge Type",
            grade_options,
            format_func=lambda x: GRADE_LABELS.get(x, x).split(" — ")[0],
            help=GRADE_HELP
        )

    with col2:
        decay_options = ["All"] + [d.value for d in DecayFunction]
        decay_filter = st.selectbox(
            "How It Ages",
            decay_options,
            format_func=lambda x: DECAY_LABELS.get(x, x).split(" — ")[0],
            help=DECAY_HELP
        )

    with col3:
        confidence_threshold = st.slider(
            "Minimum Reliability",
            min_value=0,
            max_value=100,
            value=0,
            step=10,
            format="%d%%",
            help="Only show knowledge with at least this reliability level. 70%+ is typically considered trustworthy."
        )

    # Filter objects
    filtered_objects = SEEDED_CONTEXT_OBJECTS.copy()

    if grade_filter != "All":
        filtered_objects = [o for o in filtered_objects if o.context_grade and o.context_grade.value == grade_filter]

    if decay_filter != "All":
        filtered_objects = [o for o in filtered_objects if o.decay_function.value == decay_filter]

    filtered_objects = [o for o in filtered_objects if o.confidence_at_creation * 100 >= confidence_threshold]

    st.caption(f"Showing **{len(filtered_objects)}** of {len(SEEDED_CONTEXT_OBJECTS)} knowledge items")

    st.divider()

    # Display objects with better formatting
    for obj in filtered_objects:
        # Create a brief title from the payload
        title = obj.payload[:60] + "..." if len(obj.payload) > 60 else obj.payload

        with st.expander(f"📄 {obj.id}: {title}"):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown("**What we know:**")
                st.markdown(obj.payload)

                if obj.structured_data:
                    st.markdown("**Additional details:**")
                    st.json(obj.structured_data)

            with col2:
                confidence_pct = obj.confidence_at_creation * 100
                st.metric("Reliability", f"{confidence_pct:.0f}%")

                grade = obj.context_grade.value if obj.context_grade else 'N/A'
                grade_icon = {"institutional": "🏛️", "compliance": "📋", "operational": "⚙️", "deprecated": "🚫"}.get(grade, "")
                st.markdown(f"**Type:** {grade_icon} {grade.title()}")

                decay = obj.decay_function.value
                decay_icon = {"linear": "📉", "step_function": "📊", "permanent": "🔒"}.get(decay, "")
                st.markdown(f"**Aging:** {decay_icon} {decay.replace('_', ' ').title()}")

                if obj.workflow_id:
                    st.markdown(f"**Workflow:** {obj.workflow_id}")

    st.divider()

    # Confidence decay visualization with better explanation
    st.subheader("📈 How Knowledge Reliability Changes Over Time")
    st.markdown("""
    Knowledge becomes less reliable over time unless it's validated by successful use.
    The chart below shows how the reliability of different knowledge items decays over
    the 12-week simulation period.
    """)

    weeks = list(range(1, 13))
    decay_data = []

    # Show a mix of different decay types
    sample_objects = SEEDED_CONTEXT_OBJECTS[:6]

    for obj in sample_objects:
        for week in weeks:
            confidence = obj.compute_current_confidence(week)
            decay_data.append({
                "Knowledge Item": f"{obj.id}",
                "Week": week,
                "Reliability (%)": confidence * 100,
            })

    if decay_data:
        fig = px.line(
            decay_data,
            x="Week",
            y="Reliability (%)",
            color="Knowledge Item",
            title="Knowledge Reliability Over Time (sample items)",
            markers=True,
        )
        fig.update_layout(
            yaxis_range=[0, 105],
            yaxis_title="Reliability (%)",
            xaxis_title="Simulation Week",
            legend_title="Knowledge Item",
        )
        fig.add_hline(y=70, line_dash="dash", line_color="orange",
                      annotation_text="70% - Recommended trust threshold")
        st.plotly_chart(fig, use_container_width=True)

        st.caption("💡 **Tip:** Items that fall below 70% reliability may need revalidation before use.")


# =============================================================================
# TAB 3: DECISION HISTORY (formerly Decision Trace Viewer)
# =============================================================================
with tabs[2]:
    st.header("🔍 Decision History")
    st.markdown("""
    Review every decision made during the simulation. Compare how agents performed
    **with** and **without** access to the Context Bank.
    """)

    decisions_data = load_decisions()

    if not decisions_data:
        st.warning("No decisions recorded yet. Run the simulation first with `python main.py`.")
    else:
        # Condition selector with clear explanation
        st.subheader("Compare Conditions")

        col1, col2 = st.columns(2)

        with col1:
            condition = st.radio(
                "Which run do you want to review?",
                ["with_bank", "without_bank"],
                format_func=lambda x: "✅ WITH Context Bank (agents can access institutional memory)" if x == "with_bank"
                                       else "❌ WITHOUT Context Bank (agents rely only on immediate context)",
                help="The simulation runs twice: once where agents can query the knowledge library, and once where they cannot."
            )

        decisions = decisions_data.get(condition, [])

        with col2:
            correct = sum(1 for d in decisions if d["outcome"] == "correct")
            total = len(decisions)
            accuracy = (correct / total * 100) if total > 0 else 0
            st.metric(
                "Accuracy in this condition",
                f"{accuracy:.0f}%",
                f"{correct}/{total} correct",
                help="Percentage of decisions that matched the correct action"
            )

        st.divider()

        # Week filter
        decision_weeks = sorted(set(d["week"] for d in decisions))
        col1, col2 = st.columns([1, 3])

        with col1:
            selected_week = st.selectbox(
                "Filter by week:",
                ["All Weeks"] + [f"Week {w}" for w in decision_weeks],
                help="Focus on a specific week to see what happened"
            )

        filtered_decisions = decisions
        if selected_week != "All Weeks":
            week_num = int(selected_week.split()[1])
            filtered_decisions = [d for d in decisions if d["week"] == week_num]

        st.caption(f"Showing **{len(filtered_decisions)}** decisions")

        # Display decisions with clear outcome indicators
        for decision in filtered_decisions:
            is_correct = decision["outcome"] == "correct"
            icon = "✅" if is_correct else "❌"
            outcome_text = "Correct" if is_correct else "Incorrect"

            with st.expander(
                f"{icon} Week {decision['week']}: {decision['scenario_type'].replace('_', ' ').title()} — {outcome_text}",
                expanded=len(filtered_decisions) <= 3,
            ):
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.markdown(f"**What the agent decided:** {decision['decision_taken']}")
                    st.markdown(f"**Agent:** {decision['agent_id']}")

                    if not is_correct:
                        st.error("This decision did not match the expected correct action.")

                with col2:
                    if decision.get("context_used"):
                        st.success(f"📚 **Used knowledge:** {', '.join(decision['context_used'])}")
                        st.caption("The agent found and applied relevant institutional memory.")
                    elif decision.get("context_retrieved"):
                        st.warning(f"📋 **Found but didn't use:** {', '.join(decision['context_retrieved'])}")
                        st.caption("Knowledge was available but the agent didn't apply it.")
                    else:
                        st.info("🔍 **No relevant knowledge found**")
                        st.caption("The agent made this decision without institutional memory.")


# =============================================================================
# TAB 4: RESULTS DASHBOARD (formerly Comparative Dashboard)
# =============================================================================
with tabs[3]:
    st.header("📊 Results Dashboard")
    st.markdown("""
    See how the Context Bank improved decision-making. The simulation runs twice:
    once **without** the bank (baseline) and once **with** it.
    """)

    if not results:
        st.warning("No results found. Run the simulation first with `python main.py`.")
    else:
        comparison = results.get("comparison", {})
        without = comparison.get("without_bank", {})
        with_bank = comparison.get("with_bank", {})
        improvement = comparison.get("comparison", {})

        # Key metrics with explanations
        st.subheader("📈 Key Improvements")

        col1, col2, col3, col4 = st.columns(4)

        without_acc = without.get("summary", {}).get("accuracy", 0)
        with_acc = with_bank.get("summary", {}).get("accuracy", 0)
        acc_improvement = improvement.get('accuracy_improvement', 0)

        with col1:
            st.metric(
                "Decision Accuracy",
                f"{with_acc:.0f}%",
                f"+{acc_improvement:.0f}%" if acc_improvement > 0 else f"{acc_improvement:.0f}%",
                help="Percentage of decisions that were correct. The delta shows improvement over baseline."
            )
            st.caption(f"Baseline: {without_acc:.0f}%")

        with col2:
            errors_avoided = improvement.get("errors_avoided", 0)
            st.metric(
                "Mistakes Prevented",
                errors_avoided,
                help="Number of incorrect decisions that were avoided thanks to the Context Bank"
            )
            st.caption("Fewer errors = less risk")

        with col3:
            bank_size = with_bank.get("summary", {}).get("final_bank_size", 0)
            st.metric(
                "Knowledge Items",
                bank_size,
                help="Total pieces of institutional knowledge in the bank at simulation end"
            )
            st.caption("Organizational memory")

        with col4:
            dqs_imp = improvement.get('dqs_improvement', 0)
            st.metric(
                "Quality Score Gain",
                f"+{dqs_imp:.1f}",
                help="Improvement in Decision Quality Score (DQS). This measures week-over-week decision accuracy."
            )
            st.caption("Cumulative improvement")

        st.divider()

        # Visual comparison
        st.subheader("📊 Before vs After Comparison")

        col1, col2 = st.columns(2)

        with col1:
            fig = go.Figure(data=[
                go.Bar(
                    name="Without Context Bank",
                    x=["Decision Accuracy"],
                    y=[without_acc],
                    marker_color="#ff6b6b",
                    text=[f"{without_acc:.0f}%"],
                    textposition='outside',
                ),
                go.Bar(
                    name="With Context Bank",
                    x=["Decision Accuracy"],
                    y=[with_acc],
                    marker_color="#51cf66",
                    text=[f"{with_acc:.0f}%"],
                    textposition='outside',
                ),
            ])
            fig.update_layout(
                title="Accuracy: Baseline vs With Context Bank",
                yaxis_range=[0, 110],
                yaxis_title="Accuracy (%)",
                barmode="group",
                showlegend=True,
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            without_correct = without.get("summary", {}).get("correct_decisions", 0)
            without_incorrect = without.get("summary", {}).get("incorrect_decisions", 0)
            with_correct = with_bank.get("summary", {}).get("correct_decisions", 0)
            with_incorrect = with_bank.get("summary", {}).get("incorrect_decisions", 0)

            fig = go.Figure(data=[
                go.Bar(name="Correct", x=["Without Bank", "With Bank"],
                       y=[without_correct, with_correct], marker_color="#51cf66"),
                go.Bar(name="Incorrect", x=["Without Bank", "With Bank"],
                       y=[without_incorrect, with_incorrect], marker_color="#ff6b6b"),
            ])
            fig.update_layout(
                title="Decision Outcomes by Condition",
                barmode="stack",
                yaxis_title="Number of Decisions",
            )
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # Week-by-week progression
        st.subheader("📅 Week-by-Week Performance")
        st.markdown("""
        Watch how performance evolves over the 12-week simulation. The Context Bank
        typically shows increasing benefit as more knowledge accumulates and agents
        learn to retrieve it effectively.
        """)

        without_ehr = without.get("primary_metrics", {}).get("exception_handling_rates", [])
        with_ehr = with_bank.get("primary_metrics", {}).get("exception_handling_rates", [])
        bank_growth = with_bank.get("secondary_metrics", {}).get("context_object_growth", [])

        max_weeks = max(len(without_ehr), len(with_ehr), len(bank_growth))
        progression_data = []

        for week in range(max_weeks):
            w_val = without_ehr[week] if week < len(without_ehr) else 0
            wb_val = with_ehr[week] if week < len(with_ehr) else 0
            bank_size = bank_growth[week] if week < len(bank_growth) else 0

            progression_data.append({
                "Week": week + 1,
                "Without Bank (%)": w_val,
                "With Bank (%)": wb_val,
                "Knowledge Items": bank_size,
            })

        if progression_data:
            col1, col2 = st.columns(2)

            with col1:
                fig = px.line(
                    progression_data,
                    x="Week",
                    y=["Without Bank (%)", "With Bank (%)"],
                    title="Decision Accuracy Over Time",
                    markers=True,
                    color_discrete_map={
                        "Without Bank (%)": "#ff6b6b",
                        "With Bank (%)": "#51cf66"
                    }
                )
                fig.update_layout(
                    yaxis_range=[0, 105],
                    yaxis_title="Accuracy (%)",
                    legend_title="Condition",
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                fig = px.area(
                    progression_data,
                    x="Week",
                    y="Knowledge Items",
                    title="Knowledge Accumulation Over Time",
                )
                fig.update_traces(fill='tozeroy', line_color='#339af0')
                fig.update_layout(yaxis_title="Items in Context Bank")
                st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # Summary table
        st.subheader("📋 Full Summary")

        summary_data = {
            "Metric": [
                "Total Decisions",
                "Correct Decisions",
                "Incorrect Decisions",
                "Overall Accuracy",
                "Final Knowledge Items",
                "Avg Knowledge Reliability",
            ],
            "WITHOUT Context Bank": [
                without.get("summary", {}).get("total_decisions", 0),
                without.get("summary", {}).get("correct_decisions", 0),
                without.get("summary", {}).get("incorrect_decisions", 0),
                f"{without.get('summary', {}).get('accuracy', 0):.0f}%",
                "—",
                "—",
            ],
            "WITH Context Bank": [
                with_bank.get("summary", {}).get("total_decisions", 0),
                with_bank.get("summary", {}).get("correct_decisions", 0),
                with_bank.get("summary", {}).get("incorrect_decisions", 0),
                f"{with_bank.get('summary', {}).get('accuracy', 0):.0f}%",
                with_bank.get("summary", {}).get("final_bank_size", 0),
                f"{with_bank.get('summary', {}).get('final_avg_confidence', 0) * 100:.0f}%",
            ],
        }

        st.table(summary_data)


# =============================================================================
# TAB 5: LEARNING ENGINE (formerly Synthesis Engine)
# =============================================================================
with tabs[4]:
    st.header("🧠 Learning Engine")
    st.markdown("""
    The Learning Engine transforms raw knowledge into refined organizational intelligence.
    It runs periodically to strengthen valuable knowledge and let unused knowledge fade.
    """)

    # Simple explanation of what it does
    with st.expander("ℹ️ How the Learning Engine Works", expanded=False):
        st.markdown("""
        The engine performs three operations every few weeks:

        **1. Pattern Recognition** 🔍
        > When the same lesson appears in multiple contexts, the engine creates a
        > "crystallized" rule that won't decay over time.

        **2. Success Reinforcement** ✅
        > When agents use knowledge successfully, that knowledge (and related knowledge)
        > gets a reliability boost.

        **3. Adaptive Aging** ⏱️
        > Frequently-used knowledge decays more slowly. Unused knowledge fades faster.
        """)

    if not results:
        st.warning("No results found. Run the simulation first with `python main.py`.")
    else:
        comparison = results.get("comparison", {})
        with_bank = comparison.get("with_bank", {})
        synthesis = with_bank.get("synthesis_metrics", {})

        if not synthesis or not synthesis.get("synthesis_results"):
            st.info("No learning data available. The engine runs every 3 weeks during simulation.")
        else:
            # Key metrics with intuitive names
            st.subheader("📊 Learning Summary")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "Patterns Found",
                    synthesis.get("total_patterns_crystallized", 0),
                    help="Recurring lessons promoted to permanent knowledge"
                )

            with col2:
                st.metric(
                    "Success Boosts",
                    synthesis.get("total_validations_propagated", 0),
                    help="Times that successful use reinforced knowledge reliability"
                )

            with col3:
                st.metric(
                    "Aging Adjustments",
                    synthesis.get("total_decay_adjustments", 0),
                    help="Knowledge items with modified decay rates based on usage"
                )

            with col4:
                scores = synthesis.get("intelligence_scores", [])
                active_scores = [s for s in scores if s > 0]
                avg_score = sum(active_scores) / max(1, len(active_scores))
                st.metric(
                    "Learning Score",
                    f"{avg_score * 100:.0f}%",
                    help="Overall effectiveness of the learning process (higher = more refinement)"
                )

            st.divider()

            # Learning activity over time
            st.subheader("📈 Learning Activity Over Time")

            scores = synthesis.get("intelligence_scores", [])
            if scores:
                learning_data = []
                for i, score in enumerate(scores):
                    if score > 0:
                        learning_data.append({
                            "Week": i + 1,
                            "Learning Score (%)": score * 100
                        })

                if learning_data:
                    fig = px.bar(
                        learning_data,
                        x="Week",
                        y="Learning Score (%)",
                        title="When Learning Occurred (engine runs every ~3 weeks)",
                    )
                    fig.update_layout(yaxis_range=[0, 100])
                    fig.update_traces(marker_color='#845ef7')
                    st.plotly_chart(fig, use_container_width=True)

            st.divider()

            # Detailed results per pass
            st.subheader("🔬 Learning Pass Details")
            st.markdown("Expand each pass to see what the engine learned:")

            synthesis_results = synthesis.get("synthesis_results", [])
            for i, sr in enumerate(synthesis_results):
                if sr is not None:
                    week = i + 1
                    patterns = sr.get('patterns_crystallized', 0)
                    validations = sr.get('validations_propagated', 0)
                    decays = sr.get('decay_rates_adjusted', 0)

                    summary = []
                    if patterns > 0:
                        summary.append(f"{patterns} patterns")
                    if validations > 0:
                        summary.append(f"{validations} boosts")
                    if decays > 0:
                        summary.append(f"{decays} aging updates")

                    summary_text = ", ".join(summary) if summary else "No changes"

                    with st.expander(f"Week {week}: {summary_text}"):
                        col1, col2, col3 = st.columns(3)

                        with col1:
                            st.markdown(f"**🔍 Patterns Found:** {patterns}")
                            if sr.get('new_objects_created'):
                                st.markdown("New crystallized knowledge:")
                                for obj_id in sr.get('new_objects_created', []):
                                    st.code(obj_id)

                        with col2:
                            st.markdown(f"**✅ Success Boosts:** {validations}")
                            if sr.get('confidence_boosts'):
                                st.markdown("Reliability increased:")
                                for obj_id, conf in list(sr.get('confidence_boosts', {}).items())[:5]:
                                    st.text(f"{obj_id}: +{(conf-0.5)*100:.0f}%")

                        with col3:
                            st.markdown(f"**⏱️ Aging Updates:** {decays}")
                            if sr.get('objects_updated'):
                                st.markdown("Modified items:")
                                for obj_id in sr.get('objects_updated', [])[:5]:
                                    st.code(obj_id)


# =============================================================================
# TAB 6: STRESS TESTING (formerly Realism & Chaos)
# =============================================================================
with tabs[5]:
    st.header("⚡ Stress Testing")
    st.markdown("""
    Test how the Context Bank performs under realistic organizational stress.
    These simulated disruptions mirror real-world challenges that threaten institutional memory.
    """)

    # Check for realism data
    realism_mode = results.get("metadata", {}).get("realism_mode", "Standard") if results else "Standard"
    realism_config = results.get("metadata", {}).get("realism_config") if results else None

    # Mode indicator
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Current Test Mode")
        mode_colors = {
            "Standard": ("info", "No stress testing"),
            "Chaos Only": ("warning", "Disruptions active"),
            "BPI Calibrated": ("info", "Real timing patterns"),
            "Full Realism": ("success", "All features active"),
        }
        msg_type, description = mode_colors.get(realism_mode, ("info", ""))

        if msg_type == "success":
            st.success(f"**{realism_mode}**\n\n{description}")
        elif msg_type == "warning":
            st.warning(f"**{realism_mode}**\n\n{description}")
        else:
            st.info(f"**{realism_mode}**\n\n{description}")

    with col2:
        st.subheader("How to Run Stress Tests")
        st.markdown("""
        | Command | What It Does |
        |---------|--------------|
        | `python main.py` | Standard run, no stress |
        | `python main.py --chaos` | Add organizational disruptions |
        | `python main.py --bpi` | Use real-world timing patterns |
        | `python main.py --full-realism` | All stress features enabled |
        """)

    st.divider()

    # Stress test types
    st.subheader("🎭 Types of Organizational Stress")
    st.markdown("The simulation can inject these real-world disruptions:")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        ### 👋 Staff Departure
        **What happens:** A senior employee leaves, taking undocumented knowledge with them.

        **Why it matters:**
        - Knowledge they created becomes less reliable
        - Unwritten rules they enforced are lost
        - Tests if the bank captured their expertise

        ---

        ### 🤖 Agent Performance Drift
        **What happens:** An AI agent starts making more mistakes over time.

        **Why it matters:**
        - Models can degrade without retraining
        - Tests if context retrieval corrects errors
        - Simulates real ML system behavior
        """)

    with col2:
        st.markdown("""
        ### ⚖️ Policy Conflicts
        **What happens:** New policies contradict existing ones.

        **Why it matters:**
        - Organizations often have conflicting rules
        - Tests contradiction detection
        - Simulates regulatory/policy changes

        ---

        ### 📈 Workload Spikes
        **What happens:** Event volume suddenly increases 2-3x.

        **Why it matters:**
        - Tests performance under load
        - Simulates quarter-end, busy seasons
        - May cause decision quality to drop
        """)

    st.divider()

    # Real-world calibration
    st.subheader("📊 Real-World Timing Calibration")
    st.markdown("""
    When BPI calibration is enabled, the simulation uses timing patterns from real
    business process data (BPI Challenge datasets with millions of real events).
    """)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**When Events Happen (Hour of Day)**")
        hours = list(range(24))
        weights = [
            0.01, 0.01, 0.01, 0.01, 0.01, 0.01,
            0.02, 0.04, 0.07, 0.09, 0.10, 0.10,
            0.08, 0.09, 0.09, 0.08, 0.06, 0.05,
            0.03, 0.02, 0.01, 0.01, 0.01, 0.01,
        ]
        fig = px.bar(x=hours, y=[w*100 for w in weights])
        fig.update_layout(
            xaxis_title="Hour (24h)",
            yaxis_title="% of Events",
            showlegend=False,
            height=300,
        )
        fig.update_traces(marker_color='#339af0')
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Peak: 10-11 AM (matches real office patterns)")

    with col2:
        st.markdown("**When Events Happen (Day of Week)**")
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        day_weights = [0.18, 0.20, 0.20, 0.20, 0.18, 0.03, 0.01]
        fig = px.bar(x=days, y=[w*100 for w in day_weights])
        fig.update_layout(
            xaxis_title="Day",
            yaxis_title="% of Events",
            showlegend=False,
            height=300,
        )
        fig.update_traces(marker_color='#339af0')
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Weekday-heavy, minimal weekends (like real business)")

    st.divider()

    # Chaos impact display (if chaos was enabled)
    if realism_config and realism_config.get("chaos", {}).get("enabled"):
        st.subheader("🎯 Stress Test Results")
        st.markdown("Here's what happened during this simulation run:")

        with_bank_summary = results.get("with_bank_summary", {})
        chaos_summary = with_bank_summary.get("chaos_summary", {})

        if chaos_summary:
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "Disruptions Injected",
                    chaos_summary.get("total_events", 0),
                    help="Total number of stress events that occurred"
                )

            with col2:
                st.metric(
                    "Staff Departures",
                    chaos_summary.get("knowledge_departures", 0),
                    help="Simulated employees leaving"
                )

            with col3:
                st.metric(
                    "Agent Drifts",
                    chaos_summary.get("agent_drifts", 0),
                    help="AI agents that started underperforming"
                )

            with col4:
                st.metric(
                    "Knowledge Degraded",
                    chaos_summary.get("total_objects_degraded", 0),
                    help="Knowledge items affected by disruptions"
                )

            st.markdown("#### 📅 Disruption Timeline")

            impacts = chaos_summary.get("impacts", [])
            if impacts:
                for impact in impacts:
                    event = impact.get("event", {})
                    week = event.get("week", "?")
                    chaos_type = event.get("chaos_type", "unknown")
                    description = impact.get("impact_description", "")

                    type_icons = {
                        "knowledge_departure": "👋",
                        "agent_drift": "🤖",
                        "policy_contradiction": "⚖️",
                        "workload_surge": "📈",
                    }
                    icon = type_icons.get(chaos_type, "⚡")

                    type_names = {
                        "knowledge_departure": "Staff Departure",
                        "agent_drift": "Agent Drift",
                        "policy_contradiction": "Policy Conflict",
                        "workload_surge": "Workload Spike",
                    }
                    type_name = type_names.get(chaos_type, chaos_type)

                    st.markdown(f"- **Week {week}** {icon} _{type_name}_: {description}")
            else:
                st.info("No detailed impact data available.")
    else:
        st.info("Stress testing was not enabled for this run. Use `--chaos` or `--full-realism` to enable.")

    st.divider()

    # Configuration reference
    with st.expander("📋 Default Stress Schedule"):
        st.markdown("""
        When chaos is enabled, these events occur by default:

        | Week | Event | Target | Impact |
        |------|-------|--------|--------|
        | 4 | 👋 Staff Departure | david_okafor | Knowledge decay accelerated |
        | 5 | ⚖️ Policy Conflict | Brightline rule | Contradicting guidance added |
        | 6 | 🤖 Agent Drift | vendor_agent | Higher error rate |
        | 7 | 📈 Workload Spike | All agents | 2.5x event volume |
        | 8 | 👋 Staff Departure | marcus_webb | More knowledge degraded |
        | 9 | ⚖️ Policy Conflict | TerraLogic rule | Another contradiction |
        | 10 | 🤖 Agent Drift | billing_agent | More agent errors |
        """)

    with st.expander("📊 BPI Dataset Info"):
        st.markdown("""
        Timing patterns calibrated from real process mining data:

        **BPI Challenge 2019** (used for this simulation)
        - 251,734 real business cases
        - 1.6 million events
        - Purchase-to-pay process
        - 627 unique workers
        - 42 distinct activities

        This data comes from a real organization's ERP system and provides
        realistic timing, workload, and resource patterns.
        """)


# =============================================================================
# FOOTER
# =============================================================================
st.divider()
st.caption("Acme Advisory Context Bank Simulation | Built with Streamlit")
st.caption("Simulate: `python main.py` | Launch UI: `streamlit run app.py` | Help: `python main.py --help`")
