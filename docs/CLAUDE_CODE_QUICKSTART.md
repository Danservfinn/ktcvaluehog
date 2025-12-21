# Claude Code Quickstart Guide

A complete guide to set up Claude Code with plugins, skills, and best practices.

---

## Prerequisites

- **Node.js 18+**: https://nodejs.org
- **Rust/Cargo** (for kb-claude): https://rustup.rs

---

## Step 1: Install Claude Code

```bash
# Via npm
npm install -g @anthropic-ai/claude-code

# Or via Homebrew (macOS)
brew install claude-code
```

Verify installation:
```bash
claude --version
```

---

## Step 2: Add Plugin Marketplaces

```bash
claude plugins add anthropics/claude-plugins-official
claude plugins add https://github.com/davila7/claude-code-templates.git
claude plugins add thedotmack/claude-mem
```

---

## Step 3: Enable Plugins

```bash
claude plugins enable claude-mem@thedotmack
claude plugins enable code-review@claude-plugins-official
claude plugins enable ai-ml-toolkit@claude-code-templates
```

---

## Step 4: Install Skills CLI

Access 250+ skills from the aitmpl.com collection:

```bash
npm install -g claude-code-templates
```

Browse and install skills:
```bash
claude-code-templates
```

Or browse online: https://aitmpl.com/skills

**Available Skill Sources:**
| Source | Count | Description |
|--------|-------|-------------|
| Anthropic Official | 21 | Official Anthropic skills |
| K-Dense-AI Scientific | 139 | Biology, chemistry, medicine |
| Obra Superpowers | 14 | Workflow skills |
| Alireza Rezvani | 36 | Professional role skills |
| wshobson Agents | 48 | Agent templates |

---

## Step 5: Configure MCP Servers

Create `~/.claude/mcp.json`:

```json
{
  "mcpServers": {
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-chrome-devtools"]
    }
  }
}
```

---

## Step 6: Configure Global Settings

Create `~/.claude/settings.json`:

```json
{
  "enabledPlugins": {
    "claude-mem@thedotmack": true,
    "code-review@claude-plugins-official": true,
    "ai-ml-toolkit@claude-code-templates": true
  },
  "alwaysThinkingEnabled": true
}
```

---

## Step 7: Install Knowledge Base Tool

```bash
cargo install kb-claude
```

Verify:
```bash
kb-claude --version
```

Initialize in your project:
```bash
cd your-project
kb-claude init
```

This creates:
```
.claude/
├── manifest.md           # Auto-generated index
├── metadata/             # Project info
├── code_index/           # Module docs
├── patterns/             # Architecture patterns
├── plans/                # Implementation plans
├── cheatsheets/          # Quick reference
├── debug_history/        # Bug fix learnings
└── qa/                   # Q&A knowledge
```

---

## Step 8: Create Your CLAUDE.md

Create a `CLAUDE.md` file in your project root. Keep it under 100 lines.

**Template:**

```markdown
# Project Name

## Overview
[1-2 sentences describing what this project does]

## Tech Stack
- Frontend: [framework, hosting]
- Backend: [framework, hosting]
- Database: [type, hosting]

## Project Structure
src/
├── frontend/    # React/Next.js app
├── backend/     # API service
└── scripts/     # Utilities

## Development Commands
# Start dev server
npm run dev

# Run tests
npm test

# Build
npm run build

## Key Files
- `src/app/page.tsx` - Main entry
- `src/api/routes.py` - API endpoints
- `docs/architecture.md` - System design

## Before Committing
1. Run build (must pass)
2. Run tests (must pass)
```

**Best Practices** (from [HumanLayer](https://www.humanlayer.dev/blog/writing-a-good-claude-md)):
- Keep under 100 lines (max 300)
- Include WHAT (tech stack), WHY (purpose), HOW (workflow)
- Reference separate docs instead of copying content
- Don't use as a linter - use actual linters

---

## Verification

```bash
# Check plugins
claude plugins list

# Check skills directory
ls ~/.claude/skills/

# Check MCP config
cat ~/.claude/mcp.json

# Check settings
cat ~/.claude/settings.json

# Check kb-claude
kb-claude --version
```

---

## Resources

| Resource | URL |
|----------|-----|
| Skills Browser | https://aitmpl.com/skills |
| Skills Docs | https://docs.aitmpl.com |
| CLAUDE.md Guide | https://www.humanlayer.dev/blog/writing-a-good-claude-md |
| Claude Plugins | https://github.com/anthropics/claude-plugins-official |
| Claude Mem | https://github.com/thedotmack/claude-mem |
| Claude Code Templates | https://github.com/davila7/claude-code-templates |

---

## Quick Copy-Paste Setup

Run this entire block in your terminal:

```bash
# Plugins
claude plugins add anthropics/claude-plugins-official
claude plugins add https://github.com/davila7/claude-code-templates.git
claude plugins add thedotmack/claude-mem
claude plugins enable claude-mem@thedotmack
claude plugins enable code-review@claude-plugins-official
claude plugins enable ai-ml-toolkit@claude-code-templates

# Skills CLI
npm install -g claude-code-templates

# Knowledge base
cargo install kb-claude

# MCP config
mkdir -p ~/.claude
cat > ~/.claude/mcp.json << 'EOF'
{
  "mcpServers": {
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-chrome-devtools"]
    }
  }
}
EOF

# Settings
cat > ~/.claude/settings.json << 'EOF'
{
  "enabledPlugins": {
    "claude-mem@thedotmack": true,
    "code-review@claude-plugins-official": true,
    "ai-ml-toolkit@claude-code-templates": true
  },
  "alwaysThinkingEnabled": true
}
EOF

echo "Setup complete!"
```

---

Happy coding with Claude!
