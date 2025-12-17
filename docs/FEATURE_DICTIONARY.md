# Thoth Feature Dictionary v1.0

> Complete reference for all 40 features used in the Thoth dynasty value prediction model.

---

## Quick Reference

| Category | Features | Key Insight |
|----------|----------|-------------|
| **Demographics** (3) | age, years_exp, years_remaining | Younger = more future value |
| **Athletic** (10) | athletic_score, forty, vertical... | Physical ceiling indicator |
| **Draft Capital** (3) | draft_round, draft_pick, draft_value | NFL investment signal |
| **Contract** (7) | contract_apy, guaranteed... | **#1 predictor** - teams vote with $ |
| **Playing Time** (4) | snap_pct, snap_trend... | Opportunity = production |
| **Injury** (2) | injury_risk, injuries_per_season | Availability discount |
| **Advanced** (1) | adot | Role/ceiling indicator |
| **Position** (4) | pos_QB, pos_RB, pos_WR, pos_TE | Position-specific adjustments |

---

## Feature Importance Rankings

| Rank | Feature | Importance | Direction | Category |
|------|---------|------------|-----------|----------|
| 1 | contract_guaranteed | 100.0% | + | Contract |
| 2 | contract_total | 55.0% | + | Contract |
| 3 | total_snaps | 21.0% | + | Playing Time |
| 4 | snap_pct | 16.3% | + | Playing Time |
| 5 | apy_percentile | 13.9% | + | Contract |
| 6 | adot | 13.4% | + | Advanced |
| 7 | draft_value | 10.4% | + | Draft Capital |
| 8 | guaranteed_pct | 9.8% | + | Contract |
| 9 | snap_trend | 8.9% | + | Playing Time |
| 10 | cap_pct | 7.1% | + | Contract |

---

## Demographics (3 Features)

### `age`
| Property | Value |
|----------|-------|
| **Type** | Continuous |
| **Range** | 20-42 years |
| **Source** | NFLverse roster data |
| **Correlation** | r = -0.173 (weak negative) |

**Definition:** Player's current age in years.

**Dynasty Impact:**
- Most critical demographic factor for value
- RBs decline sharply after 26, WRs after 28, QBs peak 28-32
- Each year reduces expected remaining productive seasons

**Interpretation:**
| Age Range | Signal | Action |
|-----------|--------|--------|
| < 24 | Elite youth | Premium value, long-term hold |
| 24-27 | Prime window | Peak production expected |
| 28-30 | Aging (skill) | Monitor for decline signals |
| 26-28 | Aging (RB) | High sell priority |
| 30+ | Veteran | Win-now asset only |

---

### `years_exp`
| Property | Value |
|----------|-------|
| **Type** | Discrete |
| **Range** | 0-20 seasons |
| **Source** | NFLverse roster data |
| **Correlation** | r = -0.126 (weak negative) |

**Definition:** Years of NFL experience (0 = rookie).

**Dynasty Impact:**
- Combines with age to reveal player trajectory
- Low exp + high production = breakout candidate
- High exp + declining stats = sell signal
- Rookies (0) get benefit of doubt on projection

**Interpretation:**
| Experience | Context |
|------------|---------|
| 0 (Rookie) | Projection-based value |
| 1-2 | Breakout window |
| 3-5 | Established production |
| 6+ | Veteran, production-dependent |

---

### `years_remaining`
| Property | Value |
|----------|-------|
| **Type** | Derived |
| **Range** | 0-18 years |
| **Formula** | `career_endpoint[position] - age` |
| **Correlation** | r = +0.172 (weak positive) |

**Definition:** Estimated productive fantasy seasons remaining.

**Career Endpoints by Position:**
| Position | Endpoint | Reasoning |
|----------|----------|-----------|
| QB | 40 | Brady/Brees extended modern endpoint |
| RB | 29 | Sharp decline after 26-27 |
| WR | 32 | Production typically fades after 30 |
| TE | 34 | Late bloomers, longer careers |

**Dynasty Impact:**
- Core component of "future value" calculation
- High years_remaining = rebuild asset
- Low years_remaining = win-now asset

---

## Athletic Profile (10 Features)

### `athletic_score`
| Property | Value |
|----------|-------|
| **Type** | Composite |
| **Range** | 0-100 |
| **Source** | Calculated from combine metrics |
| **Correlation** | r = +0.073 (very weak) |

**Definition:** Normalized composite athleticism metric combining all combine testing relative to position.

**Calculation:** Weighted average of:
- 40-yard dash (25%)
- Vertical jump (20%)
- Broad jump (20%)
- 3-cone (15%)
- Shuttle (10%)
- Bench press (10%)

All metrics normalized to position percentiles.

**Dynasty Impact:**
- Indicates physical ceiling
- Most predictive for young/unproven players
- Less relevant after age 26 (production > potential)
- Elite athleticism (90+) = higher breakout probability

**Interpretation:**
| Score | Tier | Example Players |
|-------|------|-----------------|
| 90-100 | Elite | DK Metcalf, Tyreek Hill |
| 75-89 | Above Average | Most starting WRs |
| 50-74 | Average | Reliable producers |
| < 50 | Below Average | Scheme-dependent value |

---

### `combine_forty` (40-yard dash)
| Property | Value |
|----------|-------|
| **Type** | Continuous |
| **Range** | 4.2-5.2 seconds |
| **Source** | NFL Combine |
| **Correlation** | r = -0.072 (lower = faster = better) |

**Definition:** 40-yard dash time in seconds.

**Position Benchmarks:**
| Position | Elite | Good | Average |
|----------|-------|------|---------|
| WR | < 4.40 | 4.40-4.50 | 4.50-4.60 |
| RB | < 4.45 | 4.45-4.55 | 4.55-4.65 |
| TE | < 4.55 | 4.55-4.70 | 4.70-4.85 |

**Dynasty Impact:**
- Deep threat indicator for WRs
- Breakaway speed for RBs
- Mismatch potential for TEs

---

### `combine_vertical` (Vertical Jump)
| Property | Value |
|----------|-------|
| **Type** | Continuous |
| **Range** | 25-46 inches |
| **Source** | NFL Combine |

**Definition:** Maximum vertical jump height in inches.

**Position Benchmarks:**
| Position | Elite | Good | Average |
|----------|-------|------|---------|
| WR | > 40" | 36-40" | 32-36" |
| RB | > 38" | 34-38" | 30-34" |
| TE | > 36" | 32-36" | 28-32" |

**Dynasty Impact:**
- Contested catch ability for WRs/TEs
- Explosiveness indicator
- Red zone target potential

---

### `combine_broad_jump`
| Property | Value |
|----------|-------|
| **Type** | Continuous |
| **Range** | 100-145 inches |
| **Source** | NFL Combine |

**Definition:** Standing broad jump distance in inches.

**Dynasty Impact:**
- Lower body explosiveness
- Correlates with YAC ability
- Burst/acceleration indicator

---

### `combine_cone` (3-Cone Drill)
| Property | Value |
|----------|-------|
| **Type** | Continuous |
| **Range** | 6.5-8.0 seconds |
| **Source** | NFL Combine |
| **Correlation** | r = -0.073 (lower = better) |

**Definition:** Time to complete 3-cone agility drill.

**Position Benchmarks:**
| Position | Elite | Good | Average |
|----------|-------|------|---------|
| WR | < 6.80 | 6.80-7.00 | 7.00-7.20 |
| RB | < 6.90 | 6.90-7.10 | 7.10-7.30 |

**Dynasty Impact:**
- Route-running ability predictor
- Change of direction skill
- Separation creation potential

---

### `combine_shuttle` (20-yard Shuttle)
| Property | Value |
|----------|-------|
| **Type** | Continuous |
| **Range** | 3.9-4.8 seconds |
| **Source** | NFL Combine |
| **Correlation** | r = -0.070 (lower = better) |

**Definition:** Time to complete 20-yard shuttle drill.

**Dynasty Impact:**
- Lateral quickness
- Short-area burst
- Slot receiver viability

---

### `combine_bench` (Bench Press)
| Property | Value |
|----------|-------|
| **Type** | Discrete |
| **Range** | 0-40 reps |
| **Source** | NFL Combine |

**Definition:** Number of 225-lb bench press repetitions.

**Dynasty Impact:**
- Upper body strength
- Contested catch advantage
- Blocking ability (TEs)
- Less predictive of fantasy production than speed/agility

---

### `combine_height` / `combine_weight`
| Property | Height | Weight |
|----------|--------|--------|
| **Type** | Continuous | Continuous |
| **Range** | 66-80 inches | 170-270 lbs |
| **Source** | NFL Combine |

**Dynasty Impact:**
- Size creates mismatch potential
- Height valuable for red zone targets
- Weight affects durability and playing style

---

## Draft Capital (3 Features)

### `draft_round`
| Property | Value |
|----------|-------|
| **Type** | Discrete |
| **Range** | 1-7 (or UDFA) |
| **Source** | NFL Draft records |
| **Correlation** | r = -0.400 (moderate negative - lower round = better) |

**Definition:** NFL draft round selected.

**Dynasty Impact:**
- Earlier picks receive more opportunities
- Longer leash from coaching staff
- Higher breakout probability (Round 1-2)
- Impact decays after year 3

**Interpretation:**
| Round | NFL Investment | Dynasty Relevance |
|-------|----------------|-------------------|
| 1 | Premium | Maximum opportunity guarantee |
| 2 | High | Strong pathway to starting role |
| 3 | Moderate | Needs to earn role |
| 4-7 | Low | Must outperform draft slot |
| UDFA | Minimal | Production-dependent only |

---

### `draft_pick`
| Property | Value |
|----------|-------|
| **Type** | Discrete |
| **Range** | 1-262 |
| **Source** | NFL Draft records |
| **Correlation** | r = -0.394 (moderate negative) |

**Definition:** Overall draft pick number.

**Dynasty Impact:**
- More granular than round
- Top 10 picks = franchise cornerstones
- Correlates strongly with guaranteed money

---

### `draft_value`
| Property | Value |
|----------|-------|
| **Type** | Derived |
| **Range** | 0-1000 |
| **Formula** | Based on historical pick value chart |
| **Correlation** | r = +0.494 (moderate positive) |

**Definition:** Calculated draft capital score where higher = more draft investment.

**Dynasty Impact:**
- Quantifies NFL team's investment
- Top 5 picks: 900-1000
- Late 1st: 700-800
- Day 2: 400-600
- Day 3: 100-300

---

## Contract Features (7 Features) - HIGHEST IMPORTANCE

### `contract_guaranteed`
| Property | Value |
|----------|-------|
| **Type** | Continuous |
| **Range** | $0 - $250M+ |
| **Source** | Spotrac/OverTheCap |
| **Correlation** | r = +0.537 |
| **Model Importance** | **#1 (100%)** |

**Definition:** Total guaranteed money in current NFL contract.

**Why It's #1:**
NFL teams employ hundreds of scouts and analysts. When they invest guaranteed money, they're putting their capital where their data is. This feature alone explains ~50% of KTC variance.

**Dynasty Impact:**
- STRONGEST predictor of dynasty value
- Signals team confidence in future production
- Guarantees playing time and opportunity
- Extension = long-term commitment

**Interpretation:**
| Guaranteed | Tier | Dynasty Signal |
|------------|------|----------------|
| $100M+ | Elite | Franchise cornerstone (9000+ KTC) |
| $50-100M | Star | Established producer (6000-9000 KTC) |
| $20-50M | Starter | Solid contributor (3000-6000 KTC) |
| $5-20M | Role Player | Limited ceiling (1000-3000 KTC) |
| < $5M | Depth | Speculative value only |

---

### `contract_total`
| Property | Value |
|----------|-------|
| **Type** | Continuous |
| **Range** | $0 - $300M+ |
| **Source** | Spotrac/OverTheCap |
| **Correlation** | r = +0.506 |
| **Model Importance** | #2 (55%) |

**Definition:** Total contract value.

**Dynasty Impact:**
- Less predictive than guaranteed (can be voided)
- Still signals team expectations
- Compare to guaranteed for "real" commitment

---

### `contract_apy`
| Property | Value |
|----------|-------|
| **Type** | Continuous |
| **Range** | $0 - $60M+/year |
| **Source** | Spotrac/OverTheCap |
| **Correlation** | r = +0.497 |

**Definition:** Average annual contract value.

**Dynasty Impact:**
- Year-over-year commitment level
- Market value indicator
- Position-relative ranking important

---

### `apy_percentile`
| Property | Value |
|----------|-------|
| **Type** | Derived |
| **Range** | 0-100 |
| **Source** | Calculated from position APY ranks |
| **Correlation** | r = +0.468 |
| **Model Importance** | #5 (13.9%) |

**Definition:** Player's APY rank within their position (percentile).

**Interpretation:**
| Percentile | Meaning |
|------------|---------|
| 95-100 | Top paid at position |
| 75-94 | Above average contract |
| 50-74 | Average market value |
| 25-49 | Below market |
| < 25 | Rookie deal or depth |

---

### `guaranteed_pct`
| Property | Value |
|----------|-------|
| **Type** | Derived |
| **Range** | 0-100% |
| **Formula** | `guaranteed / total * 100` |
| **Model Importance** | #8 (9.8%) |

**Definition:** Percentage of total contract that is guaranteed.

**Dynasty Impact:**
- Higher % = more team commitment
- 70%+ = very secure
- < 30% = easily cuttable

---

### `cap_pct`
| Property | Value |
|----------|-------|
| **Type** | Continuous |
| **Range** | 0-20% |
| **Source** | Spotrac/OverTheCap |
| **Model Importance** | #10 (7.1%) |

**Definition:** Player's cap hit as percentage of team salary cap.

**Dynasty Impact:**
- Resource allocation indicator
- 10%+ = premium investment
- High cap + low production = cut risk

---

### `contract_years`
| Property | Value |
|----------|-------|
| **Type** | Discrete |
| **Range** | 0-6 years |
| **Source** | Spotrac/OverTheCap |

**Definition:** Years remaining on current contract.

**Dynasty Impact:**
- Job security indicator
- 0-1 years = potential FA uncertainty
- 3+ years = stability

---

## Playing Time (4 Features)

### `snap_pct` (avg_snap_pct)
| Property | Value |
|----------|-------|
| **Type** | Continuous |
| **Range** | 0-100% |
| **Source** | NFLverse snap counts |
| **Correlation** | r = +0.530 |
| **Model Importance** | #4 (16.3%) |

**Definition:** Average percentage of offensive snaps played.

**Dynasty Impact:**
- Direct opportunity indicator
- Higher snaps = more fantasy chances
- Workhorse backs most valuable

**Interpretation:**
| Snap % | Role | Dynasty Value |
|--------|------|---------------|
| 80%+ | Workhorse | Premium - maximize touches |
| 60-79% | Starter | Solid floor |
| 40-59% | Committee | Volatile, matchup-dependent |
| < 40% | Backup | Handcuff value only |

---

### `snap_trend`
| Property | Value |
|----------|-------|
| **Type** | Derived |
| **Range** | -50% to +50% |
| **Formula** | `(second_half_snaps - first_half_snaps) / first_half_snaps` |
| **Model Importance** | #9 (8.9%) |

**Definition:** Comparison of snap share in first half vs second half of season.

**Dynasty Impact:**
- **Leading indicator** of role changes
- Positive trend = expanding role = BUY signal
- Negative trend = losing role = SELL signal
- Often precedes KTC changes by 1-2 weeks

**Interpretation:**
| Trend | Signal | Action |
|-------|--------|--------|
| > +10% | Strong rise | Aggressive buy |
| +5 to +10% | Rising | Buy candidate |
| -5 to +5% | Stable | Hold |
| -10 to -5% | Declining | Sell candidate |
| < -10% | Sharp decline | Aggressive sell |

---

### `total_snaps`
| Property | Value |
|----------|-------|
| **Type** | Continuous |
| **Range** | 0-1200+ |
| **Source** | NFLverse snap counts |
| **Correlation** | r = +0.567 |
| **Model Importance** | #3 (21.0%) |

**Definition:** Total offensive snaps played in season.

**Dynasty Impact:**
- Volume indicator
- Health proxy (more snaps = more games)
- 800+ snaps = full-time role

---

### `games_played`
| Property | Value |
|----------|-------|
| **Type** | Discrete |
| **Range** | 0-17 |
| **Source** | NFLverse |
| **Correlation** | r = +0.274 |

**Definition:** Number of games played in season.

**Dynasty Impact:**
- Availability indicator
- < 12 games = injury or role concern
- 17 games = full health/role

---

## Injury (2 Features)

### `injury_risk_score`
| Property | Value |
|----------|-------|
| **Type** | Derived |
| **Range** | 0-100 |
| **Formula** | Based on injury frequency and severity |
| **Source** | NFLverse injury reports |

**Definition:** Composite injury risk score where higher = more injury prone.

**Calculation Factors:**
- Injury report frequency
- Games missed history
- Injury type severity weighting

**Dynasty Impact:**
- Discount factor for fragile players
- 50+ = significant concern
- Should temper value of otherwise elite players

**Interpretation:**
| Score | Risk Level | Dynasty Impact |
|-------|------------|----------------|
| 0-20 | Low | No discount |
| 21-40 | Moderate | Minor concern |
| 41-60 | Elevated | 5-10% value discount |
| 61-80 | High | 10-20% discount |
| 80+ | Severe | Major red flag |

---

### `injuries_per_season`
| Property | Value |
|----------|-------|
| **Type** | Continuous |
| **Range** | 0-20+ |
| **Source** | NFLverse injury reports |

**Definition:** Average number of injury report appearances per season.

**Dynasty Impact:**
- Raw durability metric
- 10+ = frequently banged up
- Context matters (minor vs major)

---

## Advanced Stats (1 Feature)

### `adot` (Average Depth of Target)
| Property | Value |
|----------|-------|
| **Type** | Continuous |
| **Range** | 0-20+ yards |
| **Source** | Next Gen Stats |
| **Model Importance** | #6 (13.4%) |

**Definition:** Average distance downfield when targeted.

**Dynasty Impact:**
- Role indicator (deep threat vs possession)
- Higher ADOT = boom/bust profile
- Lower ADOT = consistent floor

**Interpretation by Position:**
| WR ADOT | Role | Dynasty Profile |
|---------|------|-----------------|
| 15+ | Deep threat | High ceiling, low floor |
| 10-15 | Intermediate | Balanced |
| 7-10 | Possession | PPR floor, limited ceiling |
| < 7 | Screen/Slot | Volume-dependent |

---

## Position Dummies (4 Features)

### `pos_QB`, `pos_RB`, `pos_WR`, `pos_TE`
| Property | Value |
|----------|-------|
| **Type** | Binary (0 or 1) |
| **Purpose** | Position-specific model adjustments |

**Definition:** One-hot encoded position indicators.

**Model Impact:**
- Enables position-specific valuations
- RB age curve different from WR
- QB premium in superflex
- TE premium leagues adjust TE values

---

## Model Outputs

### `predicted_value`
**Definition:** Thoth model's predicted KTC value based on all 40 features.

**Usage:** Compare to actual KTC to find edge opportunities.

---

### `value_gap`
**Formula:** `predicted_value - ktc_value`

**Interpretation:**
- Positive = Model values higher than market (undervalued)
- Negative = Model values lower than market (overvalued)

---

### `value_gap_pct`
**Formula:** `(predicted_value - ktc_value) / ktc_value * 100`

**Interpretation:**
| Gap % | Signal | Action |
|-------|--------|--------|
| > +15% | STRONG_BUY | Aggressive acquisition target |
| +7% to +15% | BUY | Good trade target |
| -7% to +7% | HOLD | Fair value |
| -15% to -7% | SELL | Look for trade offers |
| < -15% | STRONG_SELL | Aggressive sell target |

---

### `recommendation`
**Definition:** Categorical signal based on value_gap_pct thresholds.

**Values:** `STRONG_BUY`, `BUY`, `HOLD`, `SELL`, `STRONG_SELL`

---

## Feature Correlations Summary

### Strongest Positive Correlations with KTC
| Feature | Correlation |
|---------|-------------|
| total_snaps | +0.567 |
| contract_guaranteed | +0.537 |
| snap_pct | +0.530 |
| contract_total | +0.506 |
| contract_apy | +0.497 |
| draft_value | +0.494 |
| cap_pct | +0.493 |

### Strongest Negative Correlations with KTC
| Feature | Correlation |
|---------|-------------|
| draft_round | -0.400 |
| draft_pick | -0.394 |
| age | -0.173 |
| years_exp | -0.126 |

---

## Data Freshness Requirements

| Feature Category | Update Frequency | Staleness Threshold |
|-----------------|------------------|---------------------|
| Contract | Weekly | 7 days |
| Playing Time | Weekly (in-season) | 1 week |
| Injury | Daily (in-season) | 24 hours |
| Demographics | Monthly | 30 days |
| Athletic | Annually | Never stale |
| Draft | Never changes | N/A |

---

*Last Updated: December 2025*
*Model Version: Thoth v1.0*
*R² = 0.87 | RMSE = 735*
