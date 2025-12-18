# Elite Trade Analysis Report - Design Document

## Vision

Generate a **short research paper** for every trade analysis, leveraging our 750K+ nodes of player data and R²=0.80 ML model (temporal evaluation). Instead of simple value comparisons, Elite users get a comprehensive dynasty intelligence report.

---

## Data Sources Available

### Neo4j Nodes We Can Query

| Node Type | Count | Trade-Relevant Data |
|-----------|-------|---------------------|
| **KTCSnapshot** | 52K | Value history, trends, momentum |
| **HistoricalWeeklyStats** | 143K | Recent production, consistency |
| **HistoricalSeasonStats** | 14K | Career trajectory, peak seasons |
| **PlayByPlayAggregates** | 15K | EPA, aDOT, WOPR, red zone |
| **PlayerInjuryProfile** | 4K | Injury burden, risk score |
| **InjuryReport** | 49K | Specific injuries, games missed |
| **PlayerRoleProfile** | 700 | Starter rate, slot rate, role |
| **DepthChartEntry** | 18K | Depth position, competition |
| **CombineResult** | 7K | Athletic profile, percentiles |
| **DraftPick** | 7K | Draft capital, NFL investment |
| **KTCTrend** | 292 | Buy/sell signals, dip opportunities |
| **HistoricalNGS** | 24K | Next Gen Stats (separation, speed) |

### ML Model Outputs

- Projected PPG (R² = 0.80, temporal evaluation)
- Confidence intervals (floor/ceiling)
- Position rank projections
- Breakout/bust probability

---

## Trade Report Structure

### 1. Executive Summary (Top of Report)

```
┌─────────────────────────────────────────────────────────────────┐
│  TRADE VERDICT: WIN (+18.3% Value Edge)                        │
│  ─────────────────────────────────────────────────────────────  │
│  You're acquiring younger assets with higher projected         │
│  ceilings while giving up aging production. This trade         │
│  favors rebuilding teams with a 2-3 year window.               │
│                                                                 │
│  ML Confidence: 78%  │  Best For: Rebuild  │  Risk: Moderate   │
└─────────────────────────────────────────────────────────────────┘
```

**Data Points:**
- Win/Lose/Fair verdict with percentage
- One-paragraph narrative summary
- ML confidence score
- Team archetype fit (Rebuild / Contend / Transitioning)
- Overall risk level

---

### 2. Value Analysis Section

#### Current Market Value
| Player | Position | Age | KTC Value | Pos Rank | Value/Age Ratio |
|--------|----------|-----|-----------|----------|-----------------|
| CeeDee Lamb | WR | 25 | 9,200 | WR2 | 368 |
| Bijan Robinson | RB | 22 | 9,800 | RB1 | 445 |

#### Value Trajectory Chart
```
Value Over Time (12 months)
     ▲
9500 │        ╭──── CeeDee Lamb
9000 │   ╭────╯
8500 │───╯
     │
9800 │              ╭─── Bijan Robinson
9000 │         ╭────╯
8500 │    ╭────╯
     └────────────────────────────────▶
       Jan   Apr   Jul   Oct   Now
```

**Data Points:**
- Current KTC value
- 30-day change (% and absolute)
- 90-day trend direction
- 1-year high/low
- Position rank
- Value per year of age (dynasty efficiency metric)

#### Projected Future Value
| Player | Current | +1 Year | +2 Years | +3 Years |
|--------|---------|---------|----------|----------|
| CeeDee Lamb | 9,200 | 8,800 | 7,900 | 6,800 |
| Bijan Robinson | 9,800 | 9,400 | 8,600 | 7,500 |

*Based on position-specific aging curves and production projections*

---

### 3. Production Profile Section

#### Recent Performance
| Player | Last 4 Avg | Season PPG | vs Last Year | Consistency |
|--------|------------|------------|--------------|-------------|
| CeeDee Lamb | 21.4 | 19.8 | +2.1 | High (σ=4.2) |
| Bijan Robinson | 18.2 | 17.6 | +1.8 | Medium (σ=6.1) |

#### Efficiency Metrics (from PlayByPlayAggregates)
| Player | EPA/Touch | aDOT | WOPR | RZ Target % | RZ TD Rate |
|--------|-----------|------|------|-------------|------------|
| CeeDee Lamb | +0.18 | 11.2 | 0.62 | 22% | 31% |
| Bijan Robinson | +0.12 | 3.1 | N/A | 28% | 24% |

#### Production Trajectory
```
Career PPG Trend
     ▲
22   │           ╭── CeeDee (Peak?)
20   │      ╭────╯
18   │ ╭────╯
16   │─╯
     │
18   │      ╭──── Bijan (Rising)
16   │ ╭────╯
14   │─╯
     └────────────────────────────────▶
       '21   '22   '23   '24   '25 proj
```

---

### 4. Dynasty Outlook Section

#### Age & Peak Window Analysis
| Player | Age | Peak Window | Years Remaining | Aging Curve Position |
|--------|-----|-------------|-----------------|---------------------|
| CeeDee Lamb | 25 | 24-29 (WR) | 4 years | Early Peak |
| Bijan Robinson | 22 | 23-26 (RB) | 4 years | Pre-Peak |

#### Position-Specific Context
```
WR Aging Curve                    RB Aging Curve
     ▲                                 ▲
PPG  │    ╭────╮                  PPG  │  ╭──╮
     │  ╭╯    ╰╮                       │ ╭╯  ╰╮
     │ ╭╯      ╰╮                      │╭╯    ╰──
     │╭╯        ╰──                    ├╯
     └────────────────▶                └────────────────▶
      22  25  28  31  34               22  25  28  31  34
          ▲ CeeDee                         ▲ Bijan
```

#### ML Production Projections
| Player | 2025 Proj | Floor | Ceiling | Confidence | Pos Rank |
|--------|-----------|-------|---------|------------|----------|
| CeeDee Lamb | 19.2 PPG | 16.8 | 22.4 | 87% | WR4 |
| Bijan Robinson | 18.8 PPG | 14.2 | 21.6 | 79% | RB2 |

---

### 5. Risk Assessment Section

#### Injury Risk Profile (from PlayerInjuryProfile)
| Player | Injury Burden | Risk Level | Games Missed (3yr) | Key Concerns |
|--------|---------------|------------|-------------------|--------------|
| CeeDee Lamb | 12 | Low | 2 | Minor soft tissue |
| Bijan Robinson | 8 | Low | 0 | None recorded |

#### Situation Dependency Score
| Player | Team Stability | QB Situation | Scheme Fit | Depth Security |
|--------|---------------|--------------|------------|----------------|
| CeeDee Lamb | Medium | Uncertain | Excellent | Locked |
| Bijan Robinson | High | Stable | Excellent | Locked |

**Situation Analysis:**
> CeeDee Lamb's production is somewhat tied to QB play, with Dak Prescott's
> contract situation creating uncertainty. However, elite WRs maintain value
> regardless of QB due to target volume floors.

> Bijan Robinson operates in a run-first offense with a stable coaching staff.
> Limited competition for touches provides high floor but caps ceiling in
> pass-heavy game scripts.

#### Volatility Index
| Player | Week-to-Week σ | Boom Rate (20+ pts) | Bust Rate (<10 pts) |
|--------|----------------|---------------------|---------------------|
| CeeDee Lamb | 4.2 | 45% | 8% |
| Bijan Robinson | 6.1 | 32% | 18% |

---

### 6. Opportunity Analysis Section

#### Current Usage Profile
| Player | Target Share | Touch Share | Snap % | Routes/Game |
|--------|--------------|-------------|--------|-------------|
| CeeDee Lamb | 28% | N/A | 92% | 38 |
| Bijan Robinson | 12% | 72% | 68% | 22 |

#### Upside Scenarios
**CeeDee Lamb:**
- Upside trigger: New QB with higher aDOT preference
- Ceiling: 24+ PPG season
- Probability: 25%

**Bijan Robinson:**
- Upside trigger: Increased passing game involvement
- Ceiling: 22+ PPG season
- Probability: 30%

#### Competition Analysis
| Player | Primary Competition | Threat Level | Notes |
|--------|--------------------|--------------| ------|
| CeeDee Lamb | Brandin Cooks, Jalen Tolbert | Low | Clear alpha |
| Bijan Robinson | Tyler Allgeier | Low | Bell cow role |

---

### 7. Historical Comparisons Section

#### Similar Players at Same Age
**CeeDee Lamb (25-year-old elite WR):**
| Comparable | Age-25 Value | Age-28 Value | Change |
|------------|--------------|--------------|--------|
| Davante Adams | 8,400 | 7,200 | -14% |
| Tyreek Hill | 8,900 | 7,800 | -12% |
| **Average** | | | **-13%** |

**Bijan Robinson (22-year-old elite RB):**
| Comparable | Age-22 Value | Age-25 Value | Change |
|------------|--------------|--------------|--------|
| Saquon Barkley | 9,500 | 6,200 | -35% |
| Christian McCaffrey | 9,200 | 8,100 | -12% |
| **Average** | | | **-24%** |

#### Similar Trade History
> Trades involving WR1s for RB1s in the past 2 years have favored the
> WR-receiving side 62% of the time, primarily due to RB aging curves.

---

### 8. Final Analysis & Recommendations

#### Trade Score Breakdown
| Factor | Weight | You Give | You Get | Edge |
|--------|--------|----------|---------|------|
| Current Value | 30% | 9,200 | 9,800 | +6.5% |
| 3-Year Projected Value | 25% | 6,800 | 7,500 | +10.3% |
| Production (PPG) | 20% | 19.8 | 17.6 | -11.1% |
| Injury Risk | 10% | Low | Low | 0% |
| Age Factor | 15% | 25 | 22 | +12% |
| **TOTAL** | 100% | | | **+4.2%** |

#### Verdict
```
┌─────────────────────────────────────────────────────────────────┐
│  RECOMMENDATION: ACCEPT (Slight Win)                           │
│                                                                 │
│  This trade slightly favors you on paper (+4.2% composite      │
│  score), primarily due to age advantages. However, consider:   │
│                                                                 │
│  ✓ Accept if: Rebuilding or 2+ year window                     │
│  ✗ Decline if: Competing this year, need WR production now     │
│                                                                 │
│  To improve: Ask for a 2nd round pick to account for the       │
│  short-term production gap.                                    │
└─────────────────────────────────────────────────────────────────┘
```

#### Alternative Suggestions
If declined, consider asking for:
- Add: 2025 2nd round pick (value: ~1,200)
- Add: Bench WR3 (value: ~800-1,500)

---

## Implementation Plan

### Phase 1: Core Report (MVP)
1. Executive Summary with ML verdict
2. Value comparison table
3. Basic production stats
4. Age-based projections
5. Simple risk indicators

### Phase 2: Deep Analytics
1. Historical value charts
2. Efficiency metrics (EPA, WOPR, aDOT)
3. Injury risk profiles
4. Situation analysis
5. Similar player comparisons

### Phase 3: Advanced Features
1. Historical trade comps
2. PDF export
3. Share link generation
4. Custom weighting preferences
5. League-specific adjustments (SF, TEP, etc.)

---

## API Endpoints Needed

```
POST /api/v1/trades/analyze-elite
Request:
{
  "give_player_ids": ["player_1", "player_2"],
  "get_player_ids": ["player_3"],
  "league_settings": {
    "scoring": "ppr",
    "superflex": false,
    "tep": false
  }
}

Response:
{
  "verdict": "WIN",
  "score": 4.2,
  "confidence": 78,
  "executive_summary": "...",
  "players": {
    "give": [{ ...full player analysis }],
    "get": [{ ...full player analysis }]
  },
  "value_analysis": { ... },
  "production_profile": { ... },
  "dynasty_outlook": { ... },
  "risk_assessment": { ... },
  "opportunity_analysis": { ... },
  "historical_comps": { ... },
  "recommendations": { ... }
}
```

---

## UI Components

### Report Sections (Collapsible)
1. **Executive Summary** - Always visible
2. **Value Analysis** - Expandable
3. **Production Profile** - Expandable
4. **Dynasty Outlook** - Expandable
5. **Risk Assessment** - Expandable
6. **Opportunity Analysis** - Expandable
7. **Historical Context** - Expandable
8. **Final Recommendations** - Always visible

### Visual Elements
- Mini sparkline charts for trends
- Radar charts for player comparison
- Age curve visualizations
- Color-coded risk indicators
- Progress bars for metrics

### Export Options
- Copy as text
- Download as PDF
- Share link (7-day expiry)

---

## Estimated Development Time

| Phase | Scope | Backend | Frontend |
|-------|-------|---------|----------|
| MVP | Core report | 2-3 days | 2-3 days |
| Phase 2 | Deep analytics | 3-4 days | 3-4 days |
| Phase 3 | Advanced | 2-3 days | 2-3 days |

**Total: ~2-3 weeks for full implementation**
