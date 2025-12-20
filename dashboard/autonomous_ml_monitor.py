#!/usr/bin/env python3
"""
Autonomous ML Improvement System - Monitoring Dashboard

A real-time dashboard to monitor and control the autonomous ML improvement system.

Features:
- Live agent status monitoring
- Hypothesis queue visualization
- Experiment results with charts
- Manual cycle triggers
- LLM brainstorming interface
- Live log streaming

Run:
    streamlit run dashboard/autonomous_ml_monitor.py --server.port 8502

Or use the convenience script:
    python dashboard/autonomous_ml_monitor.py
"""

import sys
from pathlib import Path
import json
import time
from datetime import datetime, timedelta
import subprocess
import threading
from typing import Dict, List, Optional
import os

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Page config
st.set_page_config(
    page_title="Autonomous ML Monitor",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .stMetric {
        background-color: #1e1e1e;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #333;
    }
    .stMetric label {
        color: #888 !important;
    }
    .status-running {
        color: #00ff00;
        font-weight: bold;
    }
    .status-idle {
        color: #888;
    }
    .status-error {
        color: #ff4444;
        font-weight: bold;
    }
    .hypothesis-card {
        background-color: #2d2d2d;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border-left: 4px solid #4CAF50;
    }
    .llm-badge {
        background-color: #9c27b0;
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 12px;
    }
    div[data-testid="stSidebarNav"] {
        background-color: #1e1e1e;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# Data Loading Functions
# =============================================================================

@st.cache_data(ttl=5)
def load_hypothesis_queue() -> List[Dict]:
    """Load current hypothesis queue."""
    queue_file = PROJECT_ROOT / "data" / "ml_experiments" / "hypothesis_queue_v2.json"
    if queue_file.exists():
        try:
            with open(queue_file) as f:
                return json.load(f)
        except:
            pass

    # Try v1 queue
    queue_file_v1 = PROJECT_ROOT / "data" / "ml_experiments" / "hypothesis_queue.json"
    if queue_file_v1.exists():
        try:
            with open(queue_file_v1) as f:
                return json.load(f)
        except:
            pass

    return []


@st.cache_data(ttl=5)
def load_experiment_results() -> List[Dict]:
    """Load experiment results history."""
    results_file = PROJECT_ROOT / "data" / "ml_experiments" / "experiment_results_v2.json"
    if results_file.exists():
        try:
            with open(results_file) as f:
                return json.load(f)
        except:
            pass

    # Try v1 results
    results_file_v1 = PROJECT_ROOT / "data" / "ml_experiments" / "experiment_results.json"
    if results_file_v1.exists():
        try:
            with open(results_file_v1) as f:
                return json.load(f)
        except:
            pass

    return []


@st.cache_data(ttl=5)
def load_model_versions() -> Dict:
    """Load model version registry."""
    versions_file = PROJECT_ROOT / "data" / "ml_experiments" / "model_versions.json"
    if versions_file.exists():
        try:
            with open(versions_file) as f:
                return json.load(f)
        except:
            pass
    return {}


def check_llm_status() -> Dict:
    """Check local LLM connection status."""
    try:
        import requests
        response = requests.get("http://172.16.108.209:1234/v1/models", timeout=3)
        if response.status_code == 200:
            return {"connected": True, "model": "openai/gpt-oss-20b"}
    except:
        pass
    return {"connected": False, "model": None}


def get_log_tail(n_lines: int = 50) -> str:
    """Get last N lines of the autonomous ML log."""
    log_file = PROJECT_ROOT / "logs" / "autonomous_ml.log"
    if log_file.exists():
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                return ''.join(lines[-n_lines:])
        except:
            pass
    return "No logs available"


# =============================================================================
# Sidebar
# =============================================================================

with st.sidebar:
    st.title("🤖 ML Monitor")
    st.markdown("---")

    # LLM Status
    llm_status = check_llm_status()
    if llm_status["connected"]:
        st.success("🟢 Local LLM Connected")
        st.caption(f"Model: {llm_status['model']}")
    else:
        st.error("🔴 Local LLM Offline")
        st.caption("URL: http://172.16.108.209:1234")

    st.markdown("---")

    # Quick Stats
    queue = load_hypothesis_queue()
    results = load_experiment_results()

    st.metric("Queue Size", len(queue))
    st.metric("Total Experiments", len(results))

    completed = [r for r in results if r.get('status') == 'completed']
    if completed:
        avg_improvement = sum(r.get('improvement', {}).get('r2', 0) for r in completed) / len(completed)
        st.metric("Avg R² Improvement", f"{avg_improvement:+.4f}")

    st.markdown("---")

    # Auto-refresh toggle
    auto_refresh = st.toggle("Auto Refresh", value=True)
    if auto_refresh:
        refresh_interval = st.slider("Refresh (seconds)", 5, 60, 10)
        st.caption(f"Refreshing every {refresh_interval}s")

    st.markdown("---")

    # Navigation
    page = st.radio(
        "Navigate",
        ["📊 Dashboard", "📋 Queue", "🧪 Experiments", "🤖 LLM Studio", "📜 Logs", "⚙️ Controls"],
        label_visibility="collapsed"
    )


# =============================================================================
# Dashboard Page
# =============================================================================

if page == "📊 Dashboard":
    st.title("Autonomous ML Improvement System")
    st.caption("Real-time monitoring of the self-improving ML pipeline")

    # Top metrics row
    col1, col2, col3, col4, col5 = st.columns(5)

    queue = load_hypothesis_queue()
    results = load_experiment_results()
    versions = load_model_versions()

    with col1:
        st.metric(
            "Pending Hypotheses",
            len(queue),
            delta=None
        )

    with col2:
        completed = len([r for r in results if r.get('status') == 'completed'])
        st.metric("Completed", completed)

    with col3:
        promoted = len([r for r in results if r.get('status') == 'promoted'])
        st.metric("Promoted", promoted)

    with col4:
        failed = len([r for r in results if r.get('status') == 'failed'])
        st.metric("Failed", failed, delta=None)

    with col5:
        st.metric("Model Versions", len(versions))

    st.markdown("---")

    # Two column layout
    left_col, right_col = st.columns([2, 1])

    with left_col:
        st.subheader("📈 Experiment Performance")

        if results:
            # Create performance chart
            df = pd.DataFrame(results)
            if 'improvement' in df.columns:
                df['r2_improvement'] = df['improvement'].apply(
                    lambda x: x.get('r2', 0) if isinstance(x, dict) else 0
                )
                df['timestamp'] = pd.to_datetime(df.get('timestamp', datetime.now()))

                fig = go.Figure()

                # Add improvement line
                fig.add_trace(go.Scatter(
                    x=list(range(len(df))),
                    y=df['r2_improvement'],
                    mode='lines+markers',
                    name='R² Improvement',
                    line=dict(color='#00ff88', width=2),
                    marker=dict(size=8)
                ))

                # Add zero line
                fig.add_hline(y=0, line_dash="dash", line_color="gray")

                # Add threshold line
                fig.add_hline(y=0.003, line_dash="dot", line_color="yellow",
                             annotation_text="Promotion Threshold")

                fig.update_layout(
                    title="R² Improvement Over Experiments",
                    xaxis_title="Experiment #",
                    yaxis_title="R² Improvement",
                    template="plotly_dark",
                    height=350
                )

                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No experiment data with improvements yet")
        else:
            st.info("No experiments run yet. Start a cycle to see results.")

    with right_col:
        st.subheader("🏆 Top Experiments")

        if results:
            completed = [r for r in results if r.get('status') in ['completed', 'promoted']]
            sorted_results = sorted(
                completed,
                key=lambda x: x.get('improvement', {}).get('r2', 0),
                reverse=True
            )[:5]

            for i, exp in enumerate(sorted_results, 1):
                improvement = exp.get('improvement', {}).get('r2', 0)
                status = exp.get('status', 'unknown')

                status_emoji = "🏆" if status == "promoted" else "✅"

                st.markdown(f"""
                **{i}. {exp.get('hypothesis_id', 'Unknown')[:20]}...**

                {status_emoji} R²: **{improvement:+.4f}** | Status: {status}
                """)
                st.progress(min(1.0, max(0, improvement * 50 + 0.5)))
        else:
            st.info("No experiments yet")

    st.markdown("---")

    # Hypothesis Type Distribution
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Hypothesis Types in Queue")

        if queue:
            types = [h.get('type', 'unknown') for h in queue]
            type_counts = pd.Series(types).value_counts()

            fig = px.pie(
                values=type_counts.values,
                names=type_counts.index,
                title="Hypothesis Distribution",
                hole=0.4
            )
            fig.update_layout(template="plotly_dark", height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Queue is empty")

    with col2:
        st.subheader("🎯 Hypothesis Sources")

        if queue:
            sources = [h.get('source', 'unknown') for h in queue]
            source_counts = pd.Series(sources).value_counts()

            fig = px.bar(
                x=source_counts.index,
                y=source_counts.values,
                title="Hypotheses by Source",
                labels={'x': 'Source', 'y': 'Count'}
            )
            fig.update_layout(template="plotly_dark", height=300)
            fig.update_traces(marker_color=['#9c27b0' if 'llm' in s else '#4CAF50' for s in source_counts.index])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Queue is empty")


# =============================================================================
# Queue Page
# =============================================================================

elif page == "📋 Queue":
    st.title("Hypothesis Queue")
    st.caption("Pending experiments sorted by priority")

    queue = load_hypothesis_queue()

    if not queue:
        st.info("🎉 Queue is empty! All hypotheses have been tested.")
        st.markdown("Run a cycle to generate new hypotheses.")
    else:
        # Filters
        col1, col2, col3 = st.columns(3)

        with col1:
            types = list(set(h.get('type', 'unknown') for h in queue))
            selected_types = st.multiselect("Filter by Type", types, default=types)

        with col2:
            sources = list(set(h.get('source', 'unknown') for h in queue))
            selected_sources = st.multiselect("Filter by Source", sources, default=sources)

        with col3:
            min_priority = st.slider("Min Priority", 0.0, 10.0, 0.0)

        # Filter queue
        filtered = [
            h for h in queue
            if h.get('type', 'unknown') in selected_types
            and h.get('source', 'unknown') in selected_sources
            and h.get('priority', 0) >= min_priority
        ]

        st.markdown(f"**Showing {len(filtered)} of {len(queue)} hypotheses**")
        st.markdown("---")

        # Display hypotheses
        for h in filtered:
            is_llm = 'llm' in h.get('source', '').lower() or 'llm' in h.get('id', '').lower()

            with st.expander(
                f"{'🤖 ' if is_llm else ''}**{h.get('id', 'Unknown')}** | "
                f"Priority: {h.get('priority', 0):.1f} | "
                f"Type: {h.get('type', 'unknown')}"
            ):
                col1, col2 = st.columns([3, 1])

                with col1:
                    st.markdown(f"**Description:** {h.get('description', 'No description')}")

                    if h.get('config'):
                        st.markdown("**Config:**")
                        st.json(h.get('config', {}))

                with col2:
                    st.metric("Priority", f"{h.get('priority', 0):.2f}")
                    st.metric("Novelty", f"{h.get('novelty_score', 0.5):.2f}")
                    st.metric("Cost", f"{h.get('resource_cost', 1.0):.1f}")

                    if is_llm:
                        st.markdown('<span class="llm-badge">LLM Generated</span>', unsafe_allow_html=True)


# =============================================================================
# Experiments Page
# =============================================================================

elif page == "🧪 Experiments":
    st.title("Experiment Results")
    st.caption("History of all experiments and their outcomes")

    results = load_experiment_results()

    if not results:
        st.info("No experiments have been run yet.")
    else:
        # Summary stats
        col1, col2, col3, col4 = st.columns(4)

        statuses = [r.get('status', 'unknown') for r in results]

        with col1:
            st.metric("Completed", statuses.count('completed'))
        with col2:
            st.metric("Promoted", statuses.count('promoted'))
        with col3:
            st.metric("Rejected", statuses.count('rejected'))
        with col4:
            st.metric("Failed", statuses.count('failed'))

        st.markdown("---")

        # Filter by status
        status_filter = st.multiselect(
            "Filter by Status",
            ['completed', 'promoted', 'rejected', 'failed'],
            default=['completed', 'promoted']
        )

        filtered = [r for r in results if r.get('status') in status_filter]

        # Sort options
        sort_by = st.selectbox("Sort by", ["R² Improvement", "Duration", "Recent First"])

        if sort_by == "R² Improvement":
            filtered = sorted(filtered, key=lambda x: x.get('improvement', {}).get('r2', 0), reverse=True)
        elif sort_by == "Duration":
            filtered = sorted(filtered, key=lambda x: x.get('duration_seconds', 0), reverse=True)
        else:
            filtered = list(reversed(filtered))

        st.markdown(f"**Showing {len(filtered)} experiments**")

        # Display as table
        if filtered:
            df = pd.DataFrame([
                {
                    'ID': r.get('hypothesis_id', 'Unknown')[:25],
                    'Status': r.get('status', 'unknown'),
                    'R² Improvement': r.get('improvement', {}).get('r2', 0),
                    'RMSE Change': r.get('improvement', {}).get('rmse', 0),
                    'Duration (s)': r.get('duration_seconds', 0),
                }
                for r in filtered
            ])

            # Color code the improvements
            def color_improvement(val):
                if val > 0.003:
                    return 'background-color: #1b5e20; color: white'
                elif val > 0:
                    return 'background-color: #33691e; color: white'
                elif val < -0.01:
                    return 'background-color: #b71c1c; color: white'
                else:
                    return ''

            styled_df = df.style.applymap(color_improvement, subset=['R² Improvement'])
            st.dataframe(styled_df, use_container_width=True, height=400)

        # Detailed view
        st.markdown("---")
        st.subheader("Experiment Details")

        selected_id = st.selectbox(
            "Select experiment",
            [r.get('hypothesis_id', 'Unknown') for r in filtered]
        )

        selected = next((r for r in filtered if r.get('hypothesis_id') == selected_id), None)

        if selected:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Metrics:**")
                st.json(selected.get('metrics', {}))

            with col2:
                st.markdown("**Baseline:**")
                st.json(selected.get('baseline_metrics', {}))

            st.markdown("**Improvement:**")
            st.json(selected.get('improvement', {}))


# =============================================================================
# LLM Studio Page
# =============================================================================

elif page == "🤖 LLM Studio":
    st.title("LLM Creative Studio")
    st.caption("Interact with the local LLM for brainstorming and code generation")

    llm_status = check_llm_status()

    if not llm_status["connected"]:
        st.error("⚠️ Local LLM is not connected")
        st.markdown("""
        Make sure your local LLM is running at:
        - **URL**: http://172.16.108.209:1234
        - **Model**: openai/gpt-oss-20b
        """)
    else:
        st.success(f"🟢 Connected to {llm_status['model']}")

        tab1, tab2, tab3 = st.tabs(["💡 Brainstorm", "💻 Code Gen", "🔍 Error Analysis"])

        with tab1:
            st.subheader("Brainstorm Feature Ideas")
            st.markdown("Let the LLM generate creative feature engineering ideas.")

            if st.button("🎲 Generate Ideas", type="primary"):
                with st.spinner("Brainstorming with local LLM..."):
                    try:
                        result = subprocess.run(
                            ["python", "-m", "src.ml.llm_agents", "--brainstorm"],
                            capture_output=True,
                            text=True,
                            timeout=120,
                            cwd=str(PROJECT_ROOT)
                        )

                        if result.returncode == 0:
                            st.markdown("### Generated Ideas")
                            st.text(result.stdout)
                        else:
                            st.error(f"Error: {result.stderr}")
                    except subprocess.TimeoutExpired:
                        st.error("Request timed out")
                    except Exception as e:
                        st.error(f"Failed: {e}")

        with tab2:
            st.subheader("Generate Feature Code")
            st.markdown("Describe a feature and let the LLM write the pandas code.")

            feature_name = st.text_input("Feature Name", placeholder="e.g., target_efficiency_ratio")
            feature_desc = st.text_area(
                "Feature Description",
                placeholder="Describe what this feature should capture..."
            )

            if st.button("🔨 Generate Code"):
                if feature_name and feature_desc:
                    with st.spinner("Generating code..."):
                        try:
                            result = subprocess.run(
                                ["python", "-m", "src.ml.llm_agents", "--codegen", feature_name],
                                capture_output=True,
                                text=True,
                                timeout=60,
                                cwd=str(PROJECT_ROOT)
                            )

                            if result.returncode == 0:
                                st.markdown("### Generated Code")
                                st.code(result.stdout, language="python")
                            else:
                                st.error(f"Error: {result.stderr}")
                        except Exception as e:
                            st.error(f"Failed: {e}")
                else:
                    st.warning("Please provide both name and description")

        with tab3:
            st.subheader("Error Analysis")
            st.markdown("Analyze prediction errors using LLM reasoning.")

            st.info("Run an improvement cycle first to generate prediction errors for analysis.")


# =============================================================================
# Logs Page
# =============================================================================

elif page == "📜 Logs":
    st.title("System Logs")
    st.caption("Real-time log output from the autonomous ML system")

    # Log controls
    col1, col2 = st.columns([3, 1])

    with col1:
        n_lines = st.slider("Lines to show", 20, 200, 50)

    with col2:
        if st.button("🔄 Refresh"):
            st.cache_data.clear()

    # Display logs
    log_content = get_log_tail(n_lines)

    st.code(log_content, language="log")

    # Download button
    st.download_button(
        label="📥 Download Full Log",
        data=log_content,
        file_name="autonomous_ml.log",
        mime="text/plain"
    )


# =============================================================================
# Controls Page
# =============================================================================

elif page == "⚙️ Controls":
    st.title("System Controls")
    st.caption("Manually trigger cycles and manage the autonomous system")

    st.warning("⚠️ These controls will execute operations on your ML pipeline.")

    st.markdown("---")

    # Run cycle
    st.subheader("🔄 Run Improvement Cycle")

    col1, col2 = st.columns(2)

    with col1:
        strategy = st.selectbox(
            "Strategy",
            ["exploration", "exploitation", "adversarial", "ensemble", "architecture", "data_centric"]
        )

    with col2:
        st.markdown("&nbsp;")  # Spacer
        if st.button("▶️ Run Cycle", type="primary"):
            with st.spinner(f"Running {strategy} cycle..."):
                try:
                    result = subprocess.run(
                        ["python", "-m", "src.ml.autonomous_ml_system",
                         "--cycle", "--strategy", strategy],
                        capture_output=True,
                        text=True,
                        timeout=300,
                        cwd=str(PROJECT_ROOT)
                    )

                    if result.returncode == 0:
                        st.success("Cycle completed!")
                        st.json(json.loads(result.stdout))
                    else:
                        st.error(f"Error:\n{result.stderr}")
                except subprocess.TimeoutExpired:
                    st.error("Cycle timed out after 5 minutes")
                except Exception as e:
                    st.error(f"Failed: {e}")

    st.markdown("---")

    # Run specific agent
    st.subheader("🤖 Run Specific Agent")

    col1, col2 = st.columns(2)

    with col1:
        agent = st.selectbox(
            "Agent",
            ["llm_creative", "feature_engineer", "data_scout", "error_analyst",
             "architecture_search", "drift_monitor", "meta_learner"]
        )

    with col2:
        st.markdown("&nbsp;")
        if st.button("▶️ Run Agent"):
            with st.spinner(f"Running {agent} agent..."):
                try:
                    result = subprocess.run(
                        ["python", "-m", "src.ml.autonomous_ml_system",
                         "--agent", agent],
                        capture_output=True,
                        text=True,
                        timeout=180,
                        cwd=str(PROJECT_ROOT)
                    )

                    if result.returncode == 0:
                        st.success("Agent completed!")
                        st.text(result.stdout)
                    else:
                        st.error(f"Error:\n{result.stderr}")
                except Exception as e:
                    st.error(f"Failed: {e}")

    st.markdown("---")

    # Continuous mode
    st.subheader("♾️ Continuous Mode")

    st.markdown("""
    Start the system in continuous mode to run improvement cycles automatically.

    **Command to run in terminal:**
    ```bash
    python -m src.ml.autonomous_ml_system --continuous --interval 3600
    ```

    This will run a cycle every hour (3600 seconds).
    """)

    col1, col2 = st.columns(2)

    with col1:
        interval = st.number_input("Interval (seconds)", min_value=60, value=3600, step=60)

    with col2:
        st.code(f"python -m src.ml.autonomous_ml_system --continuous --interval {interval}")

    st.markdown("---")

    # Clear queue
    st.subheader("🗑️ Queue Management")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Refresh Queue Cache"):
            st.cache_data.clear()
            st.success("Cache cleared!")

    with col2:
        if st.button("🗑️ Clear Queue", type="secondary"):
            queue_file = PROJECT_ROOT / "data" / "ml_experiments" / "hypothesis_queue_v2.json"
            if queue_file.exists():
                with open(queue_file, 'w') as f:
                    json.dump([], f)
                st.success("Queue cleared!")
                st.cache_data.clear()


# =============================================================================
# Auto-refresh
# =============================================================================

if auto_refresh and page in ["📊 Dashboard", "📋 Queue", "🧪 Experiments", "📜 Logs"]:
    time.sleep(0.1)  # Small delay
    st.rerun()


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    import sys

    # Check if running as script (not via streamlit run)
    if len(sys.argv) == 1 or sys.argv[0].endswith('autonomous_ml_monitor.py'):
        print("Starting Autonomous ML Monitor Dashboard...")
        print("Open: http://localhost:8502")
        print("\nPress Ctrl+C to stop\n")

        os.system(f"streamlit run {__file__} --server.port 8502")
