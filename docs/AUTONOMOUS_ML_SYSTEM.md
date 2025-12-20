# Autonomous ML Improvement System

## Quick Start - Monitoring Dashboard

```bash
# Start the dashboard
streamlit run dashboard/autonomous_ml_monitor.py --server.port 8502

# Or use the convenience script
./scripts/run_ml_monitor.sh
```

**Dashboard URL**: http://localhost:8502

### Dashboard Pages

| Page | Description |
|------|-------------|
| **Dashboard** | Real-time metrics, performance charts, experiment summaries |
| **Queue** | View and filter pending hypotheses, see LLM-generated vs rule-based |
| **Experiments** | Experiment history, R² improvements, detailed metrics |
| **LLM Studio** | Brainstorm features, generate code, analyze errors with local LLM |
| **Logs** | Live log streaming from the autonomous system |
| **Controls** | Trigger cycles, run specific agents, manage the system |

---

A self-improving machine learning system that continuously discovers, tests, and deploys model improvements **without human intervention** and at **$0 cost** using your local LLM.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          ML IMPROVEMENT ORCHESTRATOR                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ DataScout    │  │ Feature      │  │ Architecture │  │ LLM Creative │        │
│  │ Agent        │  │ Engineer     │  │ Search Agent │  │ Agent        │        │
│  │              │  │ Agent        │  │              │  │              │        │
│  │ - Discovers  │  │ - Generates  │  │ - NAS        │  │ - Brainstorms│        │
│  │   new data   │  │   features   │  │ - Ensemble   │  │ - Code gen   │        │
│  │ - Quality    │  │ - Evaluates  │  │   search     │  │ - Prioritizes│        │
│  │   checks     │  │   candidates │  │ - Layer      │  │ - $0 cost!   │        │
│  └──────────────┘  └──────────────┘  │   configs    │  └──────────────┘        │
│                                       └──────────────┘                          │
│                                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ Error        │  │ Drift        │  │ Meta         │  │ Model        │        │
│  │ Analyst      │  │ Monitor      │  │ Learner      │  │ Promoter     │        │
│  │              │  │              │  │              │  │              │        │
│  │ - Clusters   │  │ - Tracks     │  │ - Predicts   │  │ - Canary     │        │
│  │   failures   │  │   drift      │  │   success    │  │   deploys    │        │
│  │ - Proposes   │  │ - Triggers   │  │ - Prioritizes│  │ - Rollback   │        │
│  │   fixes      │  │   retrain    │  │   queue      │  │ - A/B test   │        │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘        │
│                                                                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                          EXPERIMENT REGISTRY & STATE                             │
│  - Hypothesis queue (priority-sorted)                                            │
│  - Experiment results history (500 max)                                          │
│  - Model versions and lineage                                                    │
│  - Persistent across restarts                                                    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Local LLM Integration ($0 Cost)

The system uses your local LLM for intelligent reasoning:

- **URL**: `http://172.16.108.209:1234`
- **Model**: `openai/gpt-oss-20b`
- **API**: OpenAI-compatible
- **Cost**: $0 (only your computer's energy)

### LLM-Powered Capabilities

| Capability | Description |
|------------|-------------|
| **Brainstorming** | Generate creative feature ideas based on domain knowledge |
| **Code Generation** | Automatically write pandas code for feature engineering |
| **Error Analysis** | Analyze prediction errors with natural language reasoning |
| **Prioritization** | Re-prioritize hypothesis queue based on learned patterns |
| **Report Generation** | Write insightful narrative reports on progress |

## Agents

### 1. DataScoutAgent
Discovers and evaluates new data sources:
- Check nflverse for new datasets
- Monitor data freshness
- Evaluate data quality
- Detect new seasons/weeks

### 2. EnhancedFeatureEngineerAgent
Generates feature engineering hypotheses:
- Interaction features (top-correlated pairs)
- Ratio features (yards per attempt, etc.)
- Polynomial features (squared terms)
- Position-relative features
- Lag/time-series features

### 3. ArchitectureSearchAgent
Explores neural network architectures:
- Layer configurations
- Attention mechanisms
- Ensemble compositions
- Embedding dimensions

### 4. ErrorAnalystAgent
Learns from prediction failures:
- Clusters high-error predictions
- Identifies systematic biases
- Proposes targeted fixes
- Generates adversarial examples

### 5. DriftMonitorAgent
Monitors production model health:
- Tracks prediction distribution changes
- Detects feature importance shifts
- Alerts on performance degradation
- Triggers retraining when needed

### 6. MetaLearnerAgent
Learns from experiment history:
- Predicts experiment success probability
- Optimizes hypothesis prioritization
- Identifies promising research directions
- Avoids repeated failures

### 7. LLMCreativeAgent
Uses local LLM for intelligent reasoning:
- Brainstorms creative features
- Generates feature engineering code
- Analyzes errors with natural language
- Suggests new data sources
- Re-prioritizes queue with reasoning

### 8. ExperimentLab
Runs model experiments:
- Train with GradientBoosting
- Position-specific evaluation
- Model checkpointing
- Resource-aware execution

### 9. ModelPromoterAgent
Handles safe production deployment:
- Canary deployments
- A/B testing framework
- Automatic rollback on degradation
- Model version registry

## Improvement Strategies

| Strategy | Focus | Agents Used |
|----------|-------|-------------|
| **Exploration** | Diverse hypothesis generation | data_scout, feature_engineer, architecture_search, meta_learner, llm_creative |
| **Exploitation** | Focus on winning areas | feature_engineer, meta_learner, llm_creative |
| **Adversarial** | Target prediction failures | error_analyst, drift_monitor, llm_creative |
| **Ensemble** | Optimize model composition | architecture_search, feature_engineer |
| **Architecture** | Neural architecture search | architecture_search |
| **Data-Centric** | Focus on data quality | data_scout, drift_monitor, llm_creative |

## Usage

### Run Single Improvement Cycle
```bash
python -m src.ml.autonomous_ml_system --cycle
```

### Run Continuously (Hourly)
```bash
python -m src.ml.autonomous_ml_system --continuous --interval 3600
```

### Run with Specific Strategy
```bash
python -m src.ml.autonomous_ml_system --cycle --strategy adversarial
```

### Run Specific Agent
```bash
# Run LLM creative agent only
python -m src.ml.autonomous_ml_system --agent llm_creative

# Run feature engineer only
python -m src.ml.autonomous_ml_system --agent feature_engineer
```

### Check System Status
```bash
python -m src.ml.autonomous_ml_system --status
```

### Generate Report
```bash
python -m src.ml.autonomous_ml_system --report
```

### Test LLM Connection
```bash
python -m src.ml.llm_agents --status
python -m src.ml.llm_agents --test-connection
```

### LLM Brainstorming
```bash
python -m src.ml.llm_agents --brainstorm
```

## How It Works Autonomously

### Phase 1: Hypothesis Generation
Each agent generates hypotheses based on its specialty:
- DataScout checks for stale data, new seasons
- FeatureEngineer analyzes correlations, proposes features
- ArchitectureSearch proposes layer/ensemble configs
- LLMCreative brainstorms creative ideas via local LLM
- ErrorAnalyst identifies systematic prediction failures
- MetaLearner learns from experiment history

### Phase 2: Experiment Execution
ExperimentLab runs experiments:
- Trains GradientBoosting with proposed changes
- Evaluates on holdout set
- Calculates improvement vs baseline
- Records position-specific metrics

### Phase 3: Evaluation & Promotion
ModelPromoter handles deployment:
- Checks if improvement exceeds threshold (0.3% R²)
- Validates RMSE doesn't increase too much
- Promotes winning models to production
- Maintains rollback capability

### Continuous Loop
When run with `--continuous`:
1. Executes improvement cycle
2. Sleeps for interval (default: 1 hour)
3. Repeats indefinitely
4. Self-heals from errors

## Configuration

### LLM Configuration
```python
from src.ml.llm_agents import LLMConfig, LLMAgentHub

config = LLMConfig(
    base_url="http://172.16.108.209:1234",
    model="openai/gpt-oss-20b",
    max_tokens=2048,
    temperature=0.7,
    timeout=120,
)

hub = LLMAgentHub(config)
```

### Promotion Thresholds
```python
PROMOTION_THRESHOLDS = {
    'min_r2_improvement': 0.003,      # Must improve R² by 0.3%
    'max_rmse_increase': 0.05,        # RMSE can't increase by more than 0.05
    'min_sample_size': 100,           # Need at least 100 test samples
    'canary_success_rate': 0.95,      # 95% success in canary
}
```

## Files

| File | Purpose |
|------|---------|
| `src/ml/autonomous_ml_system.py` | Main orchestrator and all agents |
| `src/ml/llm_agents.py` | Local LLM integration (brainstorm, codegen, analysis) |
| `data/ml_experiments/hypothesis_queue_v2.json` | Pending hypotheses |
| `data/ml_experiments/experiment_results_v2.json` | Experiment history |
| `data/ml_experiments/model_versions.json` | Model registry |
| `logs/autonomous_ml.log` | System logs |

## Example Output

### LLM-Generated Feature Ideas
```
1. offensive_line_strength
   Players behind stronger offensive lines get more opportunities

2. target_share_vs_top_three_receivers
   Relative target share compared to team's top receivers

3. schedule_flexibility_index
   Measure of favorable upcoming matchups

4. weather_adjusted_yards_per_attempt
   Efficiency accounting for weather conditions

5. injury_risk_score
   Historical injury patterns predicting future risk
```

### LLM-Suggested Data Sources
```
1. Pro Football Focus (PFF) Advanced Metrics
   Access: Paid API subscription

2. ESPN Fantasy API (Unofficial)
   Access: Web scraping or unofficial endpoints

3. Football Outsiders Adjusted Net Yards
   Access: Web scraping or data export
```

## Key Design Decisions

1. **$0 Cost**: Uses local LLM exclusively, no cloud API costs
2. **Persistent State**: All hypotheses and results survive restarts
3. **Self-Healing**: Catches and logs errors, continues operation
4. **Priority Queue**: Higher-priority experiments run first
5. **Gradual Promotion**: Canary deployments prevent bad models
6. **Multi-Strategy**: Different strategies for different goals
7. **Meta-Learning**: System learns what works over time
