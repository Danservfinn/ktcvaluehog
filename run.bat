@echo off
REM Dynasty Edge Dashboard Launcher (Windows)
REM Run with: run.bat

echo Dynasty Edge Dashboard
echo =========================

REM Load from .env file if exists
if exist .env (
    for /f "tokens=*" %%a in (.env) do set %%a
)

set SLEEPER_LEAGUE_ID=1180199027998867456

REM Check if dependencies need installing
pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install streamlit pandas plotly anthropic nflreadpy polars pyarrow
)

echo Starting dashboard at http://localhost:8501
streamlit run dashboard.py
