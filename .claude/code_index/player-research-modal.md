---
title: Player Research Modal
link: player-research-modal
type: code_index
ontological_relations: []
tags:
- frontend
- modal
- player
- research
- neo4j
- radix-ui
created_at: 2025-12-20T00:00:00Z
updated_at: 2025-12-20T00:00:00Z
uuid: f1a2b3c4-d5e6-7890-abcd-ef1234567890
---

# Player Research Modal

## Overview
Consolidated player research modal that displays comprehensive Neo4j data when clicking on any player row in the Players page (formerly Rankings).

## Components

### Backend
- **Endpoint**: `GET /api/v1/players/{player_id}/research`
- **File**: `backend/app/routers/players.py`
- **Model**: `PlayerResearch` in `backend/app/models/player.py`

### Frontend
- **Modal**: `frontend/components/player/player-research-modal.tsx`
- **Dialog**: `frontend/components/ui/dialog.tsx` (Radix primitive)
- **Integration**: `frontend/app/(dashboard)/rankings/page.tsx`

## Data Sections (7 per Miller's Law)

1. **Header** - Name, position badge, team, age, grade, KTC value
2. **Value Analysis** - Current value, 1yr/2yr/3yr projections, rank
3. **Production Metrics** - PPG, receiving/rushing stats, efficiency (EPA, WOPR, ADOT)
4. **Dynasty Outlook** - Aging curve position, peak window, ML projections
5. **Risk Assessment** - Injury burden, games missed, depth chart security
6. **Athletic Profile** - Combine metrics (40, vert, broad, 3-cone, shuttle, bench)
7. **Draft Capital** - Round, pick, year, college

## Neo4j Data Sources
- `KTCTrend` - Value trends and momentum
- `PlayerInjuryProfile` - Injury burden scoring
- `PlayerRoleProfile` - Depth chart security, starter rate
- `PlayByPlayAggregates` - EPA/touch, target share, red zone share
- `HistoricalSeasonStats` - PPG, receiving/rushing stats
- `CombineResult` - Athletic testing metrics
- `DraftPick` - Draft capital

## Key Features
- Clickable table rows with hover effect
- Loading spinner during API fetch
- Error handling for failed requests
- Position-appropriate stats (RB shows touch%, WR/TE shows target%)
- Collapsible sections (Value/Production default open, Athletic/Draft collapsed)

## Related Files
- `frontend/lib/api.ts` - `getPlayerResearch()` method and types
- `frontend/app/(dashboard)/players/page.tsx` - Redirects to /rankings
- `frontend/app/(dashboard)/layout.tsx` - Navigation renamed Rankings→Players
