# Claude Code Environment Setup Guide

This document provides instructions to replicate the Claude Code environment with all installed skills, plugins, MCP servers, and configuration.

## Prerequisites

- Claude Code CLI installed (`npm install -g @anthropic/claude-code` or via Homebrew)
- Node.js 18+ and npm
- Cargo/Rust (for kb-claude knowledge base tool)

---

## 1. Plugins (Marketplaces)

Install the following plugin marketplaces and enable plugins:

### Add Marketplaces

```bash
# Official Anthropic plugins
claude plugins add anthropics/claude-plugins-official

# Claude Code templates by davila7
claude plugins add https://github.com/davila7/claude-code-templates.git

# Claude memory system by thedotmack
claude plugins add thedotmack/claude-mem
```

### Enable Plugins

```bash
# Enable memory plugin
claude plugins enable claude-mem@thedotmack

# Enable code review plugin
claude plugins enable code-review@claude-plugins-official

# Enable AI/ML toolkit
claude plugins enable ai-ml-toolkit@claude-code-templates
```

---

## 2. Skills (43 Total)

Install these skills into `~/.claude/skills/`:

### Development & Architecture
| Skill | Description |
|-------|-------------|
| `senior-architect` | System architecture and design patterns |
| `senior-backend` | Backend development (Node.js, Python, Go) |
| `senior-frontend` | Frontend development (React, Next.js) |
| `senior-fullstack` | Complete web application development |
| `senior-devops` | DevOps, CI/CD, infrastructure |
| `senior-data-engineer` | Data pipelines and ETL |
| `senior-data-scientist` | Data science and analytics |
| `senior-ml-engineer` | Machine learning engineering |
| `senior-computer-vision` | Computer vision applications |
| `senior-prompt-engineer` | Prompt engineering and LLM optimization |

### Code Quality & Review
| Skill | Description |
|-------|-------------|
| `code-reviewer` | Comprehensive code review with checklists |
| `critical-reviewer` | Adversarial analysis of web pages and claims |
| `receiving-code-review` | How to receive and process code reviews |
| `requesting-code-review` | How to request effective code reviews |
| `systematic-debugging` | Root cause analysis before fixing bugs |
| `verification-before-completion` | Verify work before marking complete |

### Planning & Strategy
| Skill | Description |
|-------|-------------|
| `writing-plans` | Create implementation plans |
| `executing-plans` | Execute plans systematically |
| `cto-advisor` | Technical leadership guidance |
| `product-strategist` | Product strategy and roadmaps |
| `brainstorming` | Ideation and creative thinking |

### Agent Development
| Skill | Description |
|-------|-------------|
| `agent-development` | Build Claude agents |
| `skill-creator` | Create new Claude skills |
| `skill-development` | Develop and refine skills |
| `command-development` | Create custom CLI commands |
| `subagent-driven-development` | Orchestrate parallel agents |
| `dispatching-parallel-agents` | Dispatch multiple agents |
| `using-superpowers` | Leverage Claude's advanced capabilities |

### UI/UX & Design
| Skill | Description |
|-------|-------------|
| `frontend-design` | Frontend design patterns |
| `ui-design-system` | Design system creation |
| `ux-researcher-designer` | UX research and design |
| `theme-factory` | Theme and styling generation |
| `web-artifacts-builder` | Build web components |
| `webapp-testing` | Web application testing |

### Content & Research
| Skill | Description |
|-------|-------------|
| `content-research-writer` | Research and content creation |
| `lead-research-assistant` | Deep research assistance |
| `seo-optimizer` | SEO optimization |
| `changelog-generator` | Generate changelogs |
| `writing-rules` | Writing guidelines and style |

### Utilities
| Skill | Description |
|-------|-------------|
| `accessibility-auditor` | Accessibility compliance checking |
| `file-organizer` | File organization and cleanup |
| `video-downloader` | Video downloading utilities |

### Installation

Skills are typically installed via:

```bash
# From a marketplace
claude skills install <skill-name>

# Or manually copy skill folders to ~/.claude/skills/
```

---

## 3. MCP Servers

Configure MCP servers in `~/.claude/mcp.json`:

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

### Additional MCP Servers (Optional)

```json
{
  "mcpServers": {
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-chrome-devtools"]
    },
    "shadcn": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-shadcn"]
    }
  }
}
```

---

## 4. Global Settings

Configure `~/.claude/settings.json`:

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

## 5. Knowledge Base Tool (kb-claude)

Install the Rust-based knowledge base tool:

```bash
# Install via cargo
cargo install kb-claude

# Verify installation
kb-claude --version
# Should output: kb-claude 0.3.4 or later
```

### Initialize Knowledge Base in Project

```bash
cd your-project
kb-claude init
```

### Knowledge Base Structure

```
.claude/
├── manifest.md           # Auto-generated index
├── metadata/             # Project-level info
├── code_index/           # Module documentation
├── patterns/             # Architecture patterns
├── plans/                # Implementation plans
├── cheatsheets/          # Quick reference
├── debug_history/        # Bug fix learnings
├── qa/                   # Q&A knowledge
└── memory_anchors/       # Context anchors
```

### Common Commands

```bash
kb-claude new "Title" -t code_index -g tag1,tag2  # Create entry
kb-claude manifest                                  # Regenerate index
kb-claude validate                                  # Check entries
kb-claude search "query"                            # Search KB
```

---

## 6. Project-Level Settings

For project-specific permissions, create `.claude/settings.local.json`:

```json
{
  "permissions": {
    "allow": [
      "Skill(critical-reviewer)",
      "WebFetch(domain:your-domain.com)",
      "Bash(npm run build:*)",
      "Bash(npx wrangler pages deploy:*)"
    ]
  }
}
```

---

## 7. Prompt to Install Everything

Copy and paste this prompt into a new Claude Code session:

```
I need you to set up my Claude Code environment with the following:

## Plugins
1. Add marketplace: anthropics/claude-plugins-official
2. Add marketplace: https://github.com/davila7/claude-code-templates.git
3. Add marketplace: thedotmack/claude-mem
4. Enable: claude-mem@thedotmack
5. Enable: code-review@claude-plugins-official
6. Enable: ai-ml-toolkit@claude-code-templates

## MCP Servers
Configure ~/.claude/mcp.json with chrome-devtools MCP server:
{
  "mcpServers": {
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-chrome-devtools"]
    }
  }
}

## Settings
Configure ~/.claude/settings.json:
{
  "enabledPlugins": {
    "claude-mem@thedotmack": true,
    "code-review@claude-plugins-official": true,
    "ai-ml-toolkit@claude-code-templates": true
  },
  "alwaysThinkingEnabled": true
}

## Knowledge Base
Install kb-claude via cargo:
cargo install kb-claude

Please execute these setup commands and confirm each step.
```

---

## 8. Key Skills Reference

### Critical Reviewer (`/critical-reviewer` or `/critique`)
Adversarial analysis of web pages for data validity, ML claims, and design credibility. Use when reviewing features before launch.

### Systematic Debugging
Root cause investigation before fixing bugs. Core principle: NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST.

### Senior Fullstack
Complete toolkit for fullstack development with React, Next.js, Node.js, GraphQL, PostgreSQL.

### Code Reviewer
Comprehensive code review with PR analysis, quality checking, and report generation.

---

## 9. Source Repositories

| Component | Repository |
|-----------|------------|
| Claude Plugins Official | `github.com/anthropics/claude-plugins-official` |
| Claude Code Templates | `github.com/davila7/claude-code-templates` |
| Claude Mem | `github.com/thedotmack/claude-mem` |
| kb-claude | Available on crates.io |

---

## Verification

After setup, verify with:

```bash
# Check plugins
claude plugins list

# Check skills
ls ~/.claude/skills/

# Check MCP servers
cat ~/.claude/mcp.json

# Check settings
cat ~/.claude/settings.json

# Check kb-claude
kb-claude --version
```

---

## Notes

- Skills are stored in `~/.claude/skills/` as markdown files with YAML frontmatter
- Plugins are managed via the `claude plugins` command
- MCP servers extend Claude's capabilities with external tools
- The knowledge base (kb-claude) helps maintain project documentation that Claude can reference
- Always run `kb-claude manifest` after adding/updating knowledge base entries
