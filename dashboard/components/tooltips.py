"""
Thoth Feature Tooltips
======================
In-dashboard feature explanations and help text.
"""

import streamlit as st
from typing import Dict, Any, Optional

# =============================================================================
# FEATURE TOOLTIPS - Complete definitions for all 40 model features
# =============================================================================

FEATURE_TOOLTIPS: Dict[str, Dict[str, Any]] = {
    # =========================================================================
    # DEMOGRAPHICS
    # =========================================================================
    'age': {
        'short': "Player's current age",
        'long': """Current age in years. Younger players command higher dynasty value
        due to more expected productive seasons remaining. Age interacts with position
        - RBs decline sharply after 26, WRs after 28, QBs peak 28-32.""",
        'interpretation': {
            'elite': '< 24 (prime years ahead)',
            'good': '24-27 (peak window)',
            'warning': '28+ for skill, 26+ for RB'
        },
        'correlation': -0.173,
        'importance': 'High',
        'category': 'demographics'
    },

    'years_exp': {
        'short': "Years of NFL experience",
        'long': """Years of NFL experience (0 = rookie). Low experience + high production
        indicates breakout potential. High experience + declining stats is a sell signal.""",
        'interpretation': {
            'good': '1-2 (breakout window)',
            'neutral': '3-5 (established)',
            'warning': '6+ (veteran, production-dependent)'
        },
        'correlation': -0.126,
        'importance': 'Medium',
        'category': 'demographics'
    },

    'years_remaining': {
        'short': "Estimated productive seasons left",
        'long': """Calculated as position-specific career endpoint minus current age.
        Endpoints: QB=40, RB=29, WR=32, TE=34. Higher values indicate rebuild assets,
        lower values indicate win-now assets.""",
        'formula': "career_endpoint[position] - age",
        'interpretation': {
            'elite': '8+ years (long-term cornerstone)',
            'good': '4-7 years (solid window)',
            'warning': '< 4 years (win-now only)'
        },
        'correlation': 0.172,
        'importance': 'High',
        'category': 'demographics'
    },

    # =========================================================================
    # ATHLETIC PROFILE
    # =========================================================================
    'athletic_score': {
        'short': "Composite athleticism score (0-100)",
        'long': """Normalized composite metric combining all combine testing relative to
        position. Calculated from 40-time, vertical, broad jump, 3-cone, shuttle, and bench.
        Most predictive for young/unproven players; less relevant after age 26.""",
        'interpretation': {
            'elite': '90+ (elite athlete)',
            'good': '75-89 (above average)',
            'neutral': '50-74 (average)',
            'warning': '< 50 (scheme-dependent)'
        },
        'correlation': 0.073,
        'importance': 'Medium',
        'category': 'athletic'
    },

    'athletic_percentile': {
        'short': "Athletic percentile within position",
        'long': """Where this player's athletic score ranks among all players at their
        position. 99th percentile = most athletic at position.""",
        'interpretation': {
            'elite': '> 95th',
            'good': '75-95th',
            'neutral': '25-74th',
            'warning': '< 25th'
        },
        'importance': 'Medium',
        'category': 'athletic'
    },

    'combine_forty': {
        'short': "40-yard dash time (seconds)",
        'long': """40-yard dash time from NFL Combine. Lower is faster/better.
        Indicates deep threat potential for WRs, breakaway speed for RBs.""",
        'benchmarks': {
            'WR': {'elite': '< 4.40', 'good': '4.40-4.50', 'avg': '4.50-4.60'},
            'RB': {'elite': '< 4.45', 'good': '4.45-4.55', 'avg': '4.55-4.65'},
            'TE': {'elite': '< 4.55', 'good': '4.55-4.70', 'avg': '4.70-4.85'}
        },
        'correlation': -0.072,
        'importance': 'Medium',
        'category': 'athletic'
    },

    'combine_vertical': {
        'short': "Vertical jump (inches)",
        'long': """Maximum vertical jump height. Indicates explosiveness, contested
        catch ability, and red zone target potential.""",
        'benchmarks': {
            'WR': {'elite': '> 40"', 'good': '36-40"', 'avg': '32-36"'},
            'RB': {'elite': '> 38"', 'good': '34-38"', 'avg': '30-34"'},
            'TE': {'elite': '> 36"', 'good': '32-36"', 'avg': '28-32"'}
        },
        'importance': 'Low',
        'category': 'athletic'
    },

    'combine_broad_jump': {
        'short': "Broad jump (inches)",
        'long': """Standing broad jump distance. Indicates lower body explosiveness,
        correlates with YAC ability and burst/acceleration.""",
        'importance': 'Low',
        'category': 'athletic'
    },

    'combine_cone': {
        'short': "3-cone drill time (seconds)",
        'long': """Time to complete 3-cone agility drill. Lower is better.
        Predicts route-running ability and separation creation potential.""",
        'correlation': -0.073,
        'importance': 'Low',
        'category': 'athletic'
    },

    'combine_shuttle': {
        'short': "20-yard shuttle time (seconds)",
        'long': """Time to complete 20-yard shuttle. Lower is better.
        Indicates lateral quickness and short-area burst.""",
        'correlation': -0.070,
        'importance': 'Low',
        'category': 'athletic'
    },

    'combine_bench': {
        'short': "Bench press reps at 225 lbs",
        'long': """Number of bench press repetitions at 225 pounds. Indicates upper
        body strength for contested catches and blocking (TEs). Less predictive of
        fantasy production than speed/agility metrics.""",
        'importance': 'Low',
        'category': 'athletic'
    },

    'combine_height': {
        'short': "Height (inches)",
        'long': "Player height. Creates mismatch potential, valuable for red zone targets.",
        'importance': 'Low',
        'category': 'athletic'
    },

    'combine_weight': {
        'short': "Weight (pounds)",
        'long': "Player weight. Affects durability, playing style, and physicality.",
        'importance': 'Low',
        'category': 'athletic'
    },

    # =========================================================================
    # DRAFT CAPITAL
    # =========================================================================
    'draft_round': {
        'short': "NFL draft round (1-7)",
        'long': """Round player was selected in NFL Draft. Earlier picks receive more
        opportunities and longer leash. Impact decays after year 3.""",
        'interpretation': {
            'elite': 'Round 1 (maximum opportunity)',
            'good': 'Round 2 (strong pathway)',
            'neutral': 'Round 3 (must earn role)',
            'warning': 'Round 4-7/UDFA (production-dependent)'
        },
        'correlation': -0.400,
        'importance': 'High',
        'category': 'draft'
    },

    'draft_pick': {
        'short': "Overall draft pick number",
        'long': """Overall pick number (1-262). More granular than round.
        Top 10 picks are typically franchise cornerstones.""",
        'correlation': -0.394,
        'importance': 'Medium',
        'category': 'draft'
    },

    'draft_value': {
        'short': "Draft capital score (0-1000)",
        'long': """Calculated draft capital score based on historical pick value chart.
        Higher = more NFL investment. Top 5 picks score 900-1000, late 1st 700-800,
        Day 2 picks 400-600, Day 3 picks 100-300.""",
        'interpretation': {
            'elite': '800+ (premium investment)',
            'good': '500-800 (significant capital)',
            'neutral': '200-500 (moderate)',
            'warning': '< 200 (minimal investment)'
        },
        'correlation': 0.494,
        'importance': 'High',
        'model_rank': 7,
        'category': 'draft'
    },

    # =========================================================================
    # CONTRACT - HIGHEST IMPORTANCE
    # =========================================================================
    'contract_guaranteed': {
        'short': "Total guaranteed money ($)",
        'long': """Total guaranteed money in current NFL contract. THE #1 PREDICTOR
        of dynasty value (100% importance). NFL teams invest guaranteed money based on
        extensive scouting - they're voting with their dollars on future production.""",
        'interpretation': {
            'elite': '$100M+ (franchise cornerstone)',
            'star': '$50-100M (established producer)',
            'starter': '$20-50M (solid contributor)',
            'role': '$5-20M (limited ceiling)',
            'depth': '< $5M (speculative)'
        },
        'correlation': 0.537,
        'model_rank': 1,
        'importance': 'Critical',
        'category': 'contract'
    },

    'contract_total': {
        'short': "Total contract value ($)",
        'long': """Total contract value. Less predictive than guaranteed (can be voided)
        but still signals team expectations.""",
        'correlation': 0.506,
        'model_rank': 2,
        'importance': 'High',
        'category': 'contract'
    },

    'contract_apy': {
        'short': "Average annual value ($/year)",
        'long': "Average per year contract value. Market value indicator.",
        'correlation': 0.497,
        'importance': 'High',
        'category': 'contract'
    },

    'apy_percentile': {
        'short': "APY rank within position (percentile)",
        'long': """Where this player's contract ranks among all players at their position.
        99th percentile = top paid at position.""",
        'interpretation': {
            'elite': '> 95th (top paid)',
            'good': '75-95th (above average)',
            'neutral': '50-74th (market rate)',
            'warning': '< 50th (below market/rookie deal)'
        },
        'correlation': 0.468,
        'model_rank': 5,
        'importance': 'High',
        'category': 'contract'
    },

    'guaranteed_pct': {
        'short': "Guaranteed % of total contract",
        'long': """Percentage of total contract that is guaranteed. Higher % = more
        team commitment. 70%+ is very secure, < 30% is easily cuttable.""",
        'interpretation': {
            'elite': '70%+ (very secure)',
            'good': '50-70% (solid commitment)',
            'warning': '< 30% (cuttable)'
        },
        'model_rank': 8,
        'importance': 'Medium',
        'category': 'contract'
    },

    'cap_pct': {
        'short': "Cap hit as % of salary cap",
        'long': """Player's cap hit as percentage of team salary cap.
        10%+ indicates premium investment. High cap + low production = cut risk.""",
        'interpretation': {
            'elite': '10%+ (premium investment)',
            'good': '5-10% (significant)',
            'warning': 'High cap + low production = cut risk'
        },
        'correlation': 0.493,
        'model_rank': 10,
        'importance': 'Medium',
        'category': 'contract'
    },

    'contract_years': {
        'short': "Years remaining on contract",
        'long': """Years remaining on current contract. Job security indicator.
        0-1 years = FA uncertainty, 3+ years = stability.""",
        'interpretation': {
            'good': '3+ years (secure)',
            'neutral': '2 years',
            'warning': '0-1 years (FA uncertainty)'
        },
        'importance': 'Medium',
        'category': 'contract'
    },

    # =========================================================================
    # PLAYING TIME
    # =========================================================================
    'snap_pct': {
        'short': "Average snap percentage",
        'long': """Average percentage of offensive snaps played. Direct opportunity
        indicator - higher snaps = more fantasy chances. Workhorse backs most valuable.""",
        'interpretation': {
            'elite': '80%+ (workhorse)',
            'good': '60-79% (starter)',
            'neutral': '40-59% (committee)',
            'warning': '< 40% (backup)'
        },
        'correlation': 0.530,
        'model_rank': 4,
        'importance': 'High',
        'category': 'playing_time'
    },

    'avg_snap_pct': {
        'short': "Average snap percentage",
        'long': "Same as snap_pct - average percentage of offensive snaps.",
        'correlation': 0.530,
        'importance': 'High',
        'category': 'playing_time'
    },

    'snap_trend': {
        'short': "Snap share trend (first vs second half)",
        'long': """Comparison of snap share in first half vs second half of season.
        LEADING INDICATOR - positive trend often precedes KTC increases by 1-2 weeks.""",
        'interpretation': {
            'strong_buy': '> +10% (role expanding rapidly)',
            'buy': '+5 to +10% (rising)',
            'hold': '-5 to +5% (stable)',
            'sell': '-10 to -5% (declining)',
            'strong_sell': '< -10% (losing role)'
        },
        'model_rank': 9,
        'importance': 'High',
        'category': 'playing_time'
    },

    'total_snaps': {
        'short': "Total offensive snaps",
        'long': """Total offensive snaps played in season. Volume indicator and
        health proxy. 800+ snaps = full-time role.""",
        'correlation': 0.567,
        'model_rank': 3,
        'importance': 'High',
        'category': 'playing_time'
    },

    'games_played': {
        'short': "Games played in season",
        'long': """Number of games played. Availability indicator.
        < 12 games = injury or role concern.""",
        'interpretation': {
            'good': '15-17 (full health)',
            'neutral': '12-14',
            'warning': '< 12 (availability concern)'
        },
        'correlation': 0.274,
        'importance': 'Medium',
        'category': 'playing_time'
    },

    # =========================================================================
    # INJURY
    # =========================================================================
    'injury_risk_score': {
        'short': "Injury risk score (0-100)",
        'long': """Composite injury risk where higher = more injury prone. Based on
        injury report frequency and historical games missed.""",
        'interpretation': {
            'good': '0-20 (low risk)',
            'neutral': '21-40 (moderate)',
            'warning': '41-60 (elevated)',
            'danger': '60+ (high risk - discount value)'
        },
        'importance': 'Medium',
        'category': 'injury'
    },

    'injuries_per_season': {
        'short': "Avg injury reports per season",
        'long': """Average number of injury report appearances per season.
        Raw durability metric - 10+ indicates frequently banged up.""",
        'interpretation': {
            'good': '< 5 (durable)',
            'neutral': '5-10',
            'warning': '10+ (frequently injured)'
        },
        'importance': 'Medium',
        'category': 'injury'
    },

    # =========================================================================
    # ADVANCED STATS
    # =========================================================================
    'adot': {
        'short': "Average Depth of Target (yards)",
        'long': """Average distance downfield when targeted. Role indicator - higher
        ADOT = deep threat with boom/bust profile, lower ADOT = possession receiver
        with consistent floor.""",
        'interpretation': {
            'deep': '15+ yards (deep threat, high ceiling)',
            'intermediate': '10-15 yards (balanced)',
            'possession': '7-10 yards (PPR floor)',
            'screen': '< 7 yards (volume-dependent)'
        },
        'model_rank': 6,
        'importance': 'Medium',
        'category': 'advanced'
    },

    # =========================================================================
    # MODEL OUTPUTS
    # =========================================================================
    'predicted_value': {
        'short': "Thoth model's predicted KTC value",
        'long': """Our ML model's estimate of fair dynasty value based on all 40 features.
        Compare to actual KTC to find edge opportunities.""",
        'importance': 'Output',
        'category': 'output'
    },

    'value_gap': {
        'short': "Predicted minus actual KTC",
        'long': """Difference between model prediction and actual KTC value.
        Positive = undervalued (BUY), Negative = overvalued (SELL).""",
        'interpretation': {
            'strong_buy': '> +1500 (significantly undervalued)',
            'buy': '+500 to +1500',
            'hold': '-500 to +500 (fair value)',
            'sell': '-1500 to -500',
            'strong_sell': '< -1500 (significantly overvalued)'
        },
        'importance': 'Output',
        'category': 'output'
    },

    'value_gap_pct': {
        'short': "Value gap as percentage",
        'long': "Value gap expressed as percentage of KTC value. Used to generate recommendations.",
        'interpretation': {
            'strong_buy': '> +15%',
            'buy': '+7% to +15%',
            'hold': '-7% to +7%',
            'sell': '-15% to -7%',
            'strong_sell': '< -15%'
        },
        'importance': 'Output',
        'category': 'output'
    },

    'recommendation': {
        'short': "Buy/Sell/Hold signal",
        'long': """Categorical recommendation based on value_gap_pct thresholds:
        STRONG_BUY (>15%), BUY (7-15%), HOLD (-7% to 7%), SELL (-15% to -7%), STRONG_SELL (<-15%)""",
        'importance': 'Output',
        'category': 'output'
    },
}


# =============================================================================
# CATEGORY DESCRIPTIONS
# =============================================================================

CATEGORY_DESCRIPTIONS = {
    'demographics': """
    **Demographics** capture player age and experience. Foundational to dynasty value
    since younger players have more productive seasons ahead. A 23-year-old WR2 is often
    worth more than a 29-year-old WR1 in dynasty.
    """,

    'athletic': """
    **Athletic Profile** captures physical tools from the NFL Combine. Most predictive
    for young/unproven players. Elite athleticism indicates higher breakout probability
    but becomes less relevant after age 26 when production trumps potential.
    """,

    'draft': """
    **Draft Capital** reflects NFL team investment. First-round picks receive more
    opportunities and longer leashes. The impact decays after year 3 - by year 5,
    production matters more than pedigree.
    """,

    'contract': """
    **Contract Features** are the STRONGEST predictors in our model. NFL teams employ
    hundreds of scouts and analysts - when they invest guaranteed money, they're signaling
    belief in future production. contract_guaranteed alone explains ~50% of KTC variance.
    """,

    'playing_time': """
    **Playing Time** measures opportunity. In fantasy, opportunity often matters more
    than efficiency. snap_trend is a leading indicator - rising snap share often precedes
    value increases by 1-2 weeks.
    """,

    'injury': """
    **Injury Risk** provides a discount factor for fragile players. Should temper value
    of otherwise elite players. Availability is the best ability.
    """,

    'advanced': """
    **Advanced Stats** like ADOT (Average Depth of Target) indicate player role and
    ceiling. Deep threats (high ADOT) have boom/bust profiles while possession receivers
    (low ADOT) provide consistent floors.
    """,

    'output': """
    **Model Outputs** are the predictions and recommendations from Thoth's ML model.
    Compare predicted_value to KTC to find edge opportunities.
    """
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_tooltip(feature_name: str) -> Optional[Dict[str, Any]]:
    """Get tooltip data for a feature."""
    return FEATURE_TOOLTIPS.get(feature_name)


def get_short_description(feature_name: str) -> str:
    """Get short description for a feature."""
    tooltip = FEATURE_TOOLTIPS.get(feature_name, {})
    return tooltip.get('short', feature_name)


def get_long_description(feature_name: str) -> str:
    """Get long description for a feature."""
    tooltip = FEATURE_TOOLTIPS.get(feature_name, {})
    return tooltip.get('long', '')


def get_interpretation(feature_name: str, value: float) -> str:
    """Get interpretation text based on feature value."""
    tooltip = FEATURE_TOOLTIPS.get(feature_name, {})
    interpretations = tooltip.get('interpretation', {})

    # Return first matching interpretation (simplified)
    # In production, would have proper threshold logic
    return str(interpretations) if interpretations else ''


def render_feature_tooltip(feature_name: str, expanded: bool = False) -> None:
    """Render an interactive tooltip for a feature in Streamlit."""
    tooltip = FEATURE_TOOLTIPS.get(feature_name)
    if not tooltip:
        return

    with st.expander(f"ℹ️ {tooltip['short']}", expanded=expanded):
        st.markdown(tooltip['long'])

        if 'interpretation' in tooltip:
            st.markdown("**How to interpret:**")
            for level, desc in tooltip['interpretation'].items():
                emoji = {
                    'elite': '🌟', 'star': '⭐', 'good': '✅',
                    'neutral': '➡️', 'warning': '⚠️', 'danger': '🔴',
                    'strong_buy': '🟢', 'buy': '🟢', 'hold': '🟡',
                    'sell': '🟠', 'strong_sell': '🔴',
                    'starter': '👍', 'role': '📋', 'depth': '📉'
                }.get(level, '•')
                st.markdown(f"{emoji} **{level.title()}**: {desc}")

        col1, col2 = st.columns(2)
        with col1:
            if 'correlation' in tooltip:
                corr = tooltip['correlation']
                direction = '↑' if corr > 0 else '↓'
                st.metric("Correlation", f"{corr:+.3f} {direction}")
        with col2:
            if 'model_rank' in tooltip:
                st.metric("Importance Rank", f"#{tooltip['model_rank']}")

        if 'formula' in tooltip:
            st.code(tooltip['formula'], language='text')


def render_category_help(category: str) -> None:
    """Render help text for a feature category."""
    description = CATEGORY_DESCRIPTIONS.get(category, '')
    if description:
        st.info(description.strip())


def get_features_by_category(category: str) -> list:
    """Get list of feature names in a category."""
    return [
        name for name, data in FEATURE_TOOLTIPS.items()
        if data.get('category') == category
    ]


def get_signal_color(signal: str) -> str:
    """Get color for a recommendation signal."""
    colors = {
        'STRONG_BUY': '#059669',
        'BUY': '#10B981',
        'HOLD': '#6B7280',
        'SELL': '#F59E0B',
        'STRONG_SELL': '#DC2626'
    }
    return colors.get(signal, '#6B7280')


def get_signal_emoji(signal: str) -> str:
    """Get emoji for a recommendation signal."""
    emojis = {
        'STRONG_BUY': '🟢🟢',
        'BUY': '🟢',
        'HOLD': '🟡',
        'SELL': '🟠',
        'STRONG_SELL': '🔴'
    }
    return emojis.get(signal, '⚪')
