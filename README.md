# Dynasty Edge 🏈

**AI-Powered Dynasty Fantasy Football Analysis Platform**

Maximize your KTC (KeepTradeCut) roster value using graph intelligence, temporal causality tracking, and automated AI analysis.

---

## 🚀 Features

### Core Capabilities
- **Neo4j Graph Database** - Model player relationships (QB→WR, depth charts, team context)
- **Temporal Snapshots** - Track how metrics change over time and correlate with KTC movements
- **Edge Scoring** - Calculate true player values vs KTC to find buy/sell opportunities
- **Claude AI Agent** - Conversational interface for analysis and trade recommendations

### AI Data Science Team Integration (NEW!)
- **Feature Engineering Agent** - Auto-generates dynasty-relevant features
- **EDA Agent** - Discovers correlations between metrics and KTC changes
- **H2O ML Agent** - Trains predictive models for KTC movements
- **Dynamic Weight Adjustment** - Update valuation model based on discovered correlations

---

## 📁 Project Structure

```
ktcvaluehog/
├── data/                           # Raw data files
│   ├── ktc_lucid_losers.csv        # KTC player values
│   ├── rosters_standings.csv       # League rosters
│   ├── traded_picks.csv            # Draft pick ownership
│   └── ...
├── scripts/                        # Data fetching scripts
│   ├── fetch_sleeper_data.py       # Sleeper API integration
│   └── ktc_to_csv.py               # KTC scraper
├── .github/workflows/              # GitHub Actions
│   └── refresh-data.yml            # Twice-daily data refresh
│
├── # Neo4j & Analysis (NEW)
├── setup_neo4j.py                  # Initialize graph database
├── temporal_pipeline.py            # Create temporal snapshots
├── ai_ds_team_integration.py       # AI agent integration
├── dynasty_agent_enhanced.py       # Claude agent with all tools
├── demo_integration.py             # Demo without full setup
│
├── requirements_full.txt           # All dependencies
├── QUICKSTART.md                   # Setup guide
└── README.md
```

---

## 🛠️ Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/Danservfinn/ktcvaluehog.git
cd ktcvaluehog
```

### 2. Install Dependencies
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Core dependencies
pip install neo4j pandas anthropic python-dotenv scipy

# AI Data Science Team (optional but recommended)
pip install ai-data-science-team langchain-openai
```

### 3. Configure Environment
Create a `.env` file:
```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

ANTHROPIC_API_KEY=sk-ant-your-key
OPENAI_API_KEY=sk-your-key  # For AI agents

SLEEPER_LEAGUE_ID=1180199027998867456
```

### 4. Run the Demo
```bash
# Test without Neo4j
python demo_integration.py

# Or start the full agent
python dynasty_agent_enhanced.py
```

---

## 💬 Usage Examples

### With the Claude Agent
```
You: "Run a full analysis on WRs to discover what drives their KTC"

Agent: [Runs Feature Engineering → EDA → ML Training]
       
       Top correlations with KTC changes:
       1. targets_per_game: r=0.72 (Strong)
       2. target_share: r=0.65 (Moderate)
       
       Recommendation: Increase w_targets_per_game to 1.35
```

```
You: "Show me BUY signals for WRs under 25"

Agent: Based on edge scores, these WRs are undervalued:
       1. Malik Nabers - KTC: 7801, Edge: 8500 (+9%)
       2. Drake London - KTC: 7062, Edge: 7800 (+10%)
```

---

## 📊 How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                    DYNASTY EDGE ARCHITECTURE                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  DATA COLLECTION (Twice Daily via GitHub Actions)               │
│  └─→ Fetch KTC values, Sleeper rosters, NFL stats               │
│                                                                  │
│  NEO4J GRAPH DATABASE                                           │
│  └─→ Players, Teams, Relationships, Temporal Snapshots          │
│                                                                  │
│  AI DATA SCIENCE AGENTS                                         │
│  └─→ Feature Engineering, Correlation Discovery, ML Models      │
│                                                                  │
│  VALUATION ENGINE                                                │
│  └─→ Calculate edge values using weighted factors               │
│  └─→ Dynamically adjust weights based on correlations           │
│                                                                  │
│  CLAUDE AGENT                                                    │
│  └─→ Conversational interface for analysis and recommendations  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Automated Data Refresh

GitHub Actions runs twice daily (6 AM and 6 PM ET) to:
1. Fetch latest KTC values
2. Pull Sleeper league data
3. Create temporal snapshots
4. Commit updated data

---

## 📈 Roadmap

- [x] Basic KTC scraper and Sleeper integration
- [x] GitHub Actions for automated refresh
- [x] Neo4j graph database architecture
- [x] Temporal causality tracking
- [x] AI Data Science Team integration
- [ ] Web dashboard (Streamlit)
- [ ] Trade simulator with KTC projections
- [ ] Multi-league support

---

## 🤝 Contributing

Pull requests welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- [KeepTradeCut](https://keeptradecut.com) for dynasty player valuations
- [Sleeper](https://sleeper.com) for the fantasy platform and API
- [ai-data-science-team](https://github.com/business-science/ai-data-science-team) for AI agent framework

---

## 🏈 NFL Data Integration (NEW!)

Dynasty Edge now integrates with **nflverse** for comprehensive NFL statistics:

### Available Data
- **Weekly Player Stats** - Targets, receptions, yards, TDs, fantasy points
- **Snap Counts** - Offensive/defensive snap percentages  
- **Next Gen Stats** - Separation, cushion, target share, air yards
- **Pro Football Reference** - Advanced metrics since 2018
- **Player ID Mappings** - Link Sleeper IDs to NFL/ESPN/Yahoo/PFF

### Key Metrics for Dynasty Value
| Metric | Source | Why It Matters |
|--------|--------|----------------|
| Targets Per Game | Weekly Stats | Volume = opportunity |
| Target Share | Next Gen Stats | % of team air yards |
| Snap Share | Snap Counts | Playing time indicator |
| Separation | Next Gen Stats | Ability to get open |

### Quick Start
```python
from nfl_data_integration import NFLDataFetcher

# Fetch data
fetcher = NFLDataFetcher()
weekly = fetcher.get_weekly_stats([2024])
ngs = fetcher.get_nextgen_receiving([2024])

# Current target leaders
print(weekly[weekly['position']=='WR'].groupby('player_display_name')['targets'].sum().nlargest(10))
```

### Load into Neo4j
```python
from nfl_data_integration import NFLDataLoader

loader = NFLDataLoader()
loader.run_full_load([2024])  # Loads all NFL data into graph database
```

See `NFL_DATA_MAPPING.md` for detailed metric correlations and dynasty value formulas.
