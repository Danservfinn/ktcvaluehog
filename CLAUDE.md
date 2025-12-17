# Dynasty Edge - Claude Code Instructions

## Project Overview
Dynasty fantasy football analysis platform using Neo4j graph database, KTC valuations, and Claude AI.

## Knowledge Base Maintenance

This project uses `kb-claude` for structured documentation in `.claude/`. **When making code changes, update the relevant knowledge base entries.**

### IMPORTANT: Task Completion Checklist

**At the END of every task that modifies code, ALWAYS:**
1. Update relevant knowledge base entries
2. Run `kb-claude manifest` to regenerate the index
3. Explicitly list KB updates made in your response summary

Example task completion format:
```
## Knowledge Base Updated
- Added: `code_index/new-module.md` - Documents new module
- Updated: `cheatsheets/dashboard-commands.md` - Added new commands
- Manifest regenerated
```

### When to Update Knowledge Base

| Change Type | Action |
|-------------|--------|
| New file/module | Add entry to `code_index` |
| Bug fix with learnings | Add entry to `debug_history` |
| Architecture change | Update `patterns` entries |
| New command/script | Update `cheatsheets` |
| Answered a complex question | Add entry to `qa` |
| Implementation plan | Add entry to `plans` |

### Commands

```bash
# Create new entry
kb-claude new "Title" -t <type> -g <tag>

# Types: metadata, debug_history, qa, code_index, patterns, plans, cheatsheets, memory_anchors

# After changes, regenerate manifest
kb-claude manifest

# Validate entries
kb-claude validate
```

### Entry Template
When creating entries, include:
- Clear title describing the content
- Relevant tags (-g flag)
- Code snippets where applicable
- Links to related files

## Key Files

- `dashboard.py` - Streamlit web UI
- `valuation_model.py` - Player valuation logic with aging curves
- `setup_neo4j.py` - Graph database initialization
- `dynasty_agent_enhanced.py` - Claude AI agent
- `nfl_data_integration.py` - NFLverse data fetching

## Running the Project

```bash
# Dashboard
streamlit run dashboard.py

# Data refresh
python scripts/fetch_ktc_data.py
python scripts/fetch_sleeper_data.py
```

## Environment Variables

Required in `.env`:
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
- `ANTHROPIC_API_KEY` (for AI chat)
- `SLEEPER_LEAGUE_ID`
