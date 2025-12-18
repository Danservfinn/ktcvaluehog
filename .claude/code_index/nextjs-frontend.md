---
title: Next.js 14 Frontend Architecture
link: nextjs-frontend
type: code_index
ontological_relations: []
tags:
- frontend
- nextjs
- react
- tailwind
- miller-law
- cloudflare-pages
- light-theme
created_at: 2025-12-17T00:00:00Z
updated_at: 2025-12-18T00:00:00Z
uuid: e5f6a7b8-c9d0-1234-ef56-789012345678
---

# Next.js 14 Frontend Architecture

## Overview

Thoth frontend built with Next.js 14 App Router, deployed to Cloudflare Pages. Implements Miller's Law (7±2 principle) throughout the UI design with a professional light theme.

## Deployment

| Platform | URL | Status |
|----------|-----|--------|
| Cloudflare Pages | `https://dynastyedge.pages.dev` | Live |

### Deploy Commands
```bash
# First time: login to Cloudflare
npx wrangler login

# Deploy to Cloudflare Pages
npx wrangler pages deploy out --project-name=dynastyedge
```

## Key Design Principles

### Miller's Law (7±2)
All UI elements follow cognitive load best practices:
- **Navigation**: 7 items (Dashboard, Players, Rankings, Trade, Projections, Chat, Settings)
- **Dashboard**: 5 widgets per view
- **Tables**: 7 columns default
- **Search Results**: 7 items initially
- **Trade Form**: Max 5 players per side

### Light Theme Design
Professional warm cream/gold theme:
```css
/* Core CSS Variables */
--background: 40 33% 98%;        /* Warm cream */
--foreground: 240 10% 10%;       /* Near black text */
--primary: 43 74% 42%;           /* Gold accent */
--card: 0 0% 100%;               /* White cards */
--secondary: 40 20% 94%;         /* Light secondary */
--border: 40 15% 88%;            /* Soft borders */

/* Glass effects for light mode */
.glass {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(24px);
  border: 1px solid rgba(0, 0, 0, 0.06);
}
```

### Position Colors (Light-optimized)
```css
/* Using 500-600 shades for visibility on light backgrounds */
QB: text-amber-600, bg-amber-100, border-amber-300
RB: text-emerald-600, bg-emerald-100, border-emerald-300
WR: text-sky-600, bg-sky-100, border-sky-300
TE: text-purple-600, bg-purple-100, border-purple-300
```

### BYOK (Bring Your Own Key)
- Anthropic API keys stored in localStorage only
- Never transmitted to our servers
- Used directly for Claude API calls via backend proxy

## Directory Structure

```
frontend/
├── app/
│   ├── page.tsx                    # Landing (7 sections)
│   ├── layout.tsx                  # Root layout + AuthProvider
│   ├── globals.css                 # CSS variables
│   ├── login/page.tsx              # Login page (Admin/Email modes)
│   ├── pricing/page.tsx            # Tier comparison
│   └── (dashboard)/                # Dashboard routes
│       ├── layout.tsx              # Sidebar nav + user state
│       ├── page.tsx                # Dashboard home
│       ├── players/page.tsx        # Player search
│       ├── rankings/page.tsx       # Rankings table
│       ├── trade/page.tsx          # Trade analyzer
│       ├── projections/page.tsx    # ML projections (Elite)
│       ├── chat/page.tsx           # Thoth AI (Elite)
│       └── settings/page.tsx       # Settings
├── components/
│   ├── ui/                         # UI components
│   │   ├── button.tsx              # Button variants
│   │   ├── card.tsx                # Card variants
│   │   ├── badge.tsx               # Position + status badges
│   │   └── input.tsx               # Form inputs
│   └── trade/
│       └── elite-trade-report.tsx  # Elite trade analysis report
├── contexts/
│   └── auth-context.tsx            # Auth provider (admin bypass + Supabase)
├── lib/
│   ├── utils.ts                    # cn() utility
│   ├── api.ts                      # FastAPI client
│   ├── supabase.ts                 # Supabase client (lazy init)
│   └── byok.ts                     # BYOK management
├── next.config.mjs                 # Static export config
├── wrangler.toml                   # Cloudflare Pages config
└── package.json                    # Dependencies
```

## Configuration

### next.config.mjs
```javascript
const nextConfig = {
  output: "export",  // Static HTML for Vercel
  images: { unoptimized: true },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  },
};
```

### wrangler.toml
```toml
name = "dynastyedge"
compatibility_date = "2024-12-01"
pages_build_output_dir = "out"

[vars]
NEXT_PUBLIC_API_URL = "https://dynasty-api-production.up.railway.app"
```

## Key Components

### Card Variants
```typescript
const variants = {
  default: "rounded-xl border bg-card shadow-sm",
  glass: "rounded-xl border border-border/60 bg-white/70 backdrop-blur-xl shadow-sm",
  premium: "rounded-xl border border-amber-200/80 bg-gradient-to-br from-amber-50 via-white to-amber-50/50 shadow-lg shadow-amber-200/30",
  elevated: "rounded-xl border border-border/60 bg-white shadow-lg shadow-black/5",
};
```

### Button Variants
```typescript
const buttonVariants = {
  default: "bg-primary text-primary-foreground shadow-md hover:bg-primary/90",
  premium: "bg-gradient-to-r from-amber-500 via-yellow-400 to-amber-500 text-black font-semibold shadow-lg shadow-amber-300/40",
  glass: "bg-white/70 backdrop-blur-xl border border-border/60 text-foreground hover:bg-white/90",
  outline: "border border-border bg-white hover:bg-secondary",
};
```

## Authentication System

### Admin Login (Testing)
For testing Elite features without Supabase:
1. Go to `/login`
2. Use Admin tab (default)
3. Password: `thoth2025elite`
4. Session lasts 24 hours (stored in localStorage)

### Auth Context (`contexts/auth-context.tsx`)
```typescript
const { user, isElite, isPro, loading, logout } = useAuth();

// User object when logged in:
{
  id: "admin",
  email: "admin@thoth.local",
  tier: "elite"  // "free" | "pro" | "elite"
}
```

### Protected Pages
Pages that use auth context for tier-based features:

| Page | Auth Behavior |
|------|---------------|
| `/projections` | Full page gated - shows upgrade prompt if not Elite |
| `/chat` | Full page gated - shows upgrade prompt if not Elite |
| `/trade` | Partial gating - ML analysis section only for Elite |
| `(dashboard)/layout.tsx` | Shows user info in sidebar, login/logout buttons |

Example pattern:
```typescript
function ProjectionsContent() {
  const { isElite, loading: authLoading } = useAuth();

  if (authLoading) return <Loading />;
  if (!isElite) return <UpgradePrompt />;

  return <ActualContent />;
}
```

### Supabase Integration
When Supabase is configured (env vars set), the auth context:
- Uses Supabase for email/password auth
- Reads user tier from `app_metadata.tier`
- Falls back to admin bypass when Supabase unavailable

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
- ML trade analysis (win probability, value projections)
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

# Deploy to Cloudflare Pages
npx wrangler pages deploy out --project-name=dynastyedge
```

## Elite Trade Report Component

`components/trade/elite-trade-report.tsx` - Comprehensive trade analysis display:
- Executive Summary with verdict badge (WIN/LOSE/FAIR)
- Key Insights section
- Side-by-side player comparison with:
  - Value analysis (current, 1yr/2yr/3yr projections)
  - Production profile (PPG, target share, efficiency metrics)
  - Dynasty outlook (peak window, aging curve position)
  - Risk assessment (injury burden, depth chart security)
- Collapsible Score Breakdown section
- Recommendations (Accept If / Decline If)
- Dynasty Context with peak windows

Usage:
```typescript
import { EliteTradeReport } from "@/components/trade/elite-trade-report";

// After fetching elite analysis
{eliteAnalysis && <EliteTradeReport analysis={eliteAnalysis} />}
```

## Related Files
- `frontend/app/` - All page components
- `frontend/components/ui/` - Reusable UI components
- `frontend/components/trade/` - Trade-specific components
- `frontend/lib/` - Utilities and API client
- `backend/app/routers/` - API endpoints consumed by frontend
