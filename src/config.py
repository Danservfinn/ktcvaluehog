"""Dynasty Edge Configuration."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
FEATURES_DIR = DATA_DIR / "features"
MODELS_DIR = DATA_DIR / "models"

# Ensure directories exist
for d in [DATA_DIR, RAW_DIR, FEATURES_DIR, MODELS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Neo4j Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Sleeper Configuration
SLEEPER_LEAGUE_ID = os.getenv("SLEEPER_LEAGUE_ID")

# NFLverse Settings
HISTORICAL_SEASONS = list(range(2020, 2026))  # 6 seasons of historical data
CURRENT_SEASON = 2025

# Position age curves (peak performance windows)
POSITION_AGE_CURVES = {
    'QB': {'prime_start': 26, 'prime_end': 34, 'cliff': 38},
    'RB': {'prime_start': 22, 'prime_end': 26, 'cliff': 30},
    'WR': {'prime_start': 24, 'prime_end': 30, 'cliff': 33},
    'TE': {'prime_start': 25, 'prime_end': 31, 'cliff': 34},
}

# Signal thresholds for buy/sell recommendations
SIGNAL_THRESHOLDS = {
    'STRONG_BUY': -20,   # Model predicts 20%+ undervalued
    'BUY': -10,          # Model predicts 10-20% undervalued
    'HOLD_LOW': -10,
    'HOLD_HIGH': 10,
    'SELL': 10,          # Model predicts 10-20% overvalued
    'STRONG_SELL': 20,   # Model predicts 20%+ overvalued
}
