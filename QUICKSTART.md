# Dynasty Edge - Quick Start Guide
## AI-Powered Dynasty Fantasy Football Analysis

This guide walks you through setting up Dynasty Edge with the AI Data Science Team integration.

---

## Prerequisites

1. **Python 3.10+**
2. **Neo4j Database** (Desktop or Aura)
3. **API Keys**:
   - Anthropic (for Claude agent)
   - OpenAI (for ai-data-science-team agents)
4. **Java 11+** (for H2O ML - optional)

---

## Step 1: Installation

```bash
# Clone or create project directory
mkdir dynasty-edge
cd dynasty-edge

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install core dependencies
pip install neo4j pandas anthropic python-dotenv scipy

# Install AI Data Science Team (optional but recommended)
pip install ai-data-science-team langchain-openai

# Install H2O for ML (optional)
pip install h2o
```

---

## Step 2: Neo4j Setup

### Option A: Neo4j Desktop (Local - Recommended for Development)

1. Download from https://neo4j.com/download/
2. Create a new project and database
3. Start the database
4. Note the bolt URI (usually `bolt://localhost:7687`)

### Option B: Neo4j Aura (Cloud - Free Tier Available)

1. Create account at https://neo4j.com/cloud/aura/
2. Create a free database
3. Note the connection URI and credentials

---

## Step 3: Environment Configuration

Create a `.env` file in your project root:

```bash
# .env file

# Neo4j Database
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here

# Anthropic API (for Claude agent)
ANTHROPIC_API_KEY=sk-ant-your-key-here

# OpenAI API (for ai-data-science-team agents)
OPENAI_API_KEY=sk-your-key-here

# Sleeper League (for data fetching)
SLEEPER_LEAGUE_ID=your_league_id

# Data paths
DATA_PATH=./data
```

---

## Step 4: Initialize Database

```bash
# Copy your CSV files to ./data directory
cp /path/to/ktc_lucid_losers.csv ./data/
cp /path/to/rosters_standings.csv ./data/

# Run the setup script
python setup_neo4j.py
```

This will:
- Create player, team, and fantasy team nodes
- Create relationships (PLAYS_FOR, TARGETS_FROM, etc.)
- Calculate initial edge values

---

## Step 5: Create Initial Snapshots (for Temporal Tracking)

```bash
python temporal_pipeline.py
```

This creates the first set of snapshots. Run this twice daily (via cron or GitHub Actions) to build temporal data.

---

## Step 6: Start the Agent

```bash
# Basic agent (Neo4j only)
python dynasty_agent.py

# Enhanced agent (with AI Data Science Team)
python dynasty_agent_enhanced.py
```

---

## Usage Examples

### Basic Queries

```
You: "Show me BUY signals for WRs"
You: "Analyze my roster"
You: "What's Drake London's KTC history?"
```

### AI-Powered Analysis

```
You: "Run a full analysis on WRs to discover what drives their KTC"
You: "What correlations have you found between targets and KTC changes?"
You: "Train a model to predict KTC changes for RBs"
You: "Suggest weight adjustments based on discovered correlations"
```

### Weight Management

```
You: "What weights should I adjust based on the latest correlations?"
You: "Increase the weight for targets_per_game to 1.3 because of strong correlation"
```

---

## File Structure

```
dynasty-edge/
├── .env                          # Environment variables
├── data/
│   ├── ktc_lucid_losers.csv      # KTC values
│   ├── rosters_standings.csv     # League rosters
│   └── traded_picks.csv          # Draft pick ownership
├── logs/
│   └── ai_agents/                # AI agent logs
├── setup_neo4j.py                # Database setup
├── temporal_pipeline.py          # Snapshot creation
├── ai_ds_team_integration.py     # Integration module
├── dynasty_agent_enhanced.py     # Main agent
├── requirements_full.txt         # Dependencies
└── README.md
```

---

## Automated Data Pipeline (GitHub Actions)

Create `.github/workflows/data-refresh.yml`:

```yaml
name: Dynasty Edge Data Refresh

on:
  schedule:
    - cron: '0 11 * * *'  # 6 AM ET
    - cron: '0 23 * * *'  # 6 PM ET
  workflow_dispatch:

jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install neo4j pandas requests beautifulsoup4
      
      - name: Fetch KTC data
        run: python scripts/fetch_ktc.py
        env:
          NEO4J_URI: ${{ secrets.NEO4J_URI }}
          NEO4J_PASSWORD: ${{ secrets.NEO4J_PASSWORD }}
      
      - name: Create snapshots
        run: python temporal_pipeline.py
      
      - name: Commit updated data
        run: |
          git config user.email "action@github.com"
          git config user.name "GitHub Action"
          git add data/
          git commit -m "Data refresh $(date)" || exit 0
          git push
```

---

## Understanding the Analysis Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    ANALYSIS WORKFLOW                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. DATA COLLECTION (Twice Daily)                               │
│     └─→ Fetch KTC values, player stats                          │
│     └─→ Create temporal snapshots                               │
│     └─→ Calculate deltas from previous snapshot                 │
│                                                                  │
│  2. FEATURE ENGINEERING (On Demand)                             │
│     └─→ AI agent generates dynasty-relevant features            │
│     └─→ years_remaining, QB quality scores, trends              │
│     └─→ Generates reusable Python code                          │
│                                                                  │
│  3. CORRELATION DISCOVERY (Weekly)                              │
│     └─→ AI agent analyzes metric → KTC relationships            │
│     └─→ Stores significant correlations in Neo4j                │
│     └─→ Suggests weight adjustments                             │
│                                                                  │
│  4. ML MODELING (On Demand)                                     │
│     └─→ H2O trains hundreds of models                           │
│     └─→ Returns feature importance rankings                     │
│     └─→ Predicts future KTC changes                             │
│                                                                  │
│  5. WEIGHT ADJUSTMENT (Based on Evidence)                       │
│     └─→ Review suggested weights                                │
│     └─→ Apply changes with documented reasoning                 │
│     └─→ Track weight change history                             │
│                                                                  │
│  6. TRADE DECISIONS (Ongoing)                                   │
│     └─→ Query for BUY/SELL signals                              │
│     └─→ Analyze specific trade proposals                        │
│     └─→ Maximize KTC value acquisition                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Troubleshooting

### "AI agents not available"
- Ensure `OPENAI_API_KEY` is set in `.env`
- Install: `pip install ai-data-science-team langchain-openai`

### "Neo4j connection failed"
- Check Neo4j is running
- Verify credentials in `.env`
- Check bolt URI (default: `bolt://localhost:7687`)

### "H2O failed to start"
- Install Java 11+: `brew install openjdk@11` (Mac)
- Set JAVA_HOME environment variable

### "Not enough data for analysis"
- Need 10+ snapshots for correlations
- Need 50+ records for ML training
- Run `temporal_pipeline.py` for several days first

---

## Next Steps

1. **Build temporal data**: Run the pipeline twice daily for 2+ weeks
2. **Discover correlations**: Use `run_full_analysis` on each position
3. **Adjust weights**: Apply data-driven weight changes
4. **Make trades**: Use edge signals to find mispriced players
5. **Track accuracy**: Monitor prediction accuracy over time

---

## Support

For issues or questions:
1. Check Neo4j logs for database errors
2. Check `logs/ai_agents/` for AI agent errors
3. Verify API keys are valid and have sufficient credits
