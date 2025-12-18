---
type: code_index
title: Next.js 14 Frontend Architecture
tags: [frontend, nextjs, react, tailwind, miller-law]
created: 2025-01-17
---

# Next.js 14 Frontend Architecture

## Overview

Dynasty Edge frontend built with Next.js 14 App Router, configured for static export to Cloudflare Pages. Implements Miller's Law (7±2 principle) throughout the UI design.

## Key Design Principles

### Miller's Law (7±2)
All UI elements follow cognitive load best practices:
- **Navigation**: 7 items (Dashboard, Players, Rankings, Trade, Projections, Chat, Settings)
- **Dashboard**: 5 widgets per view
- **Tables**: 7 columns default
- **Search Results**: 7 items initially
- **Trade Form**: Max 5 players per side

### BYOK (Bring Your Own Key)
- Anthropic API keys stored in localStorage only
- Never transmitted to our servers
- Encrypted with session token
- Used directly for Claude API calls

## Directory Structure

```
frontend/
├── app/
│   ├── page.tsx                    # Landing (7 sections)
│   ├── layout.tsx                  # Root layout
│   ├── globals.css                 # CSS variables
│   ├── pricing/page.tsx            # Tier comparison
│   └── (dashboard)/                # Auth-required routes
│       ├── layout.tsx              # Sidebar nav
│       ├── page.tsx                # Dashboard home
│       ├── players/page.tsx        # Player search
│       ├── rankings/page.tsx       # Rankings table
│       ├── trade/page.tsx          # Trade analyzer
│       ├── projections/page.tsx    # ML projections (Elite)
│       ├── chat/page.tsx           # Thoth AI (Elite)
│       └── settings/page.tsx       # Settings
├── components/ui/                   # UI components
├── lib/
│   ├── utils.ts                    # cn() utility
│   ├── api.ts                      # FastAPI client
│   └── byok.ts                     # BYOK management
└── next.config.mjs                 # Static export config
```

## Configuration

### next.config.mjs
```javascript
const nextConfig = {
  output: "export",  // Static HTML for Cloudflare Pages
  images: { unoptimized: true },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  },
};
```

### Tailwind Theme
```typescript
// Dynasty brand colors
colors: {
  dynasty: {
    gold: "#f59e0b",      // Primary accent
    dark: "#1a1a2e",      // Background
    card: "#16213e",      // Card backgrounds
    border: "#0f3460",    // Borders
  },
  position: {
    qb: "#f59e0b",        // Gold
    rb: "#22c55e",        // Green
    wr: "#3b82f6",        // Blue
    te: "#a855f7",        // Purple
  }
}
```

## Key Components

### API Client (lib/api.ts)
```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = {
  players: {
    search: (params) => fetch(`${API_URL}/api/v1/players/search?${params}`),
    get: (id) => fetch(`${API_URL}/api/v1/players/${id}`),
    compare: (ids) => fetch(`${API_URL}/api/v1/players/compare`, { method: 'POST', body: JSON.stringify({ player_ids: ids }) }),
  },
  rankings: {
    get: (params) => fetch(`${API_URL}/api/v1/rankings?${params}`),
  },
  // ... more endpoints
};
```

### BYOK Manager (lib/byok.ts)
```typescript
export function setAnthropicKey(key: string): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem('anthropic_api_key', key);
  }
}

export function getAnthropicKey(): string | null {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('anthropic_api_key');
  }
  return null;
}

export async function chatWithClaude(messages, options?) {
  const apiKey = getAnthropicKey();
  // Direct call to backend with user's key in header
}
```

## Tier Gating

### Free Tier
- Player search (all)
- Rankings (top 100)
- Trade analyzer (3/day)

### Pro Tier ($9.99/mo)
- Rankings (top 500)
- Unlimited trades
- Full player profiles

### Elite Tier ($19.99/mo)
- All rankings + rookies
- ML projections
- Thoth AI (BYOK)
- CSV export

## Commands

```bash
# Development
cd frontend && npm run dev

# Build for production
npm run build

# Type check
npm run lint
```

## Deployment

Cloudflare Pages deployment:
1. Build outputs to `frontend/out/`
2. Deploy via Wrangler or Git integration
3. Set `NEXT_PUBLIC_API_URL` environment variable

## Related Files
- `frontend/app/` - All page components
- `frontend/components/ui/` - Reusable UI components
- `frontend/lib/` - Utilities and API client
- `backend/app/routers/` - API endpoints consumed by frontend
