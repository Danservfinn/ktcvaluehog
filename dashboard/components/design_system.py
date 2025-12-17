"""
Thoth Design System
====================
Unified styling and branding for the Thoth dynasty fantasy football platform.
"""

# =============================================================================
# THOTH COLOR PALETTE
# =============================================================================

COLORS = {
    # Primary brand colors
    'primary': '#1E3A5F',        # Dynasty Blue - main brand color
    'primary_light': '#2C5282',  # Lighter blue
    'primary_dark': '#1A365D',   # Darker blue

    # Signal colors
    'success': '#10B981',        # Edge Green - BUY signals
    'success_light': '#D1FAE5',  # Light green background
    'success_dark': '#065F46',   # Dark green text

    'danger': '#EF4444',         # Alert Red - SELL signals
    'danger_light': '#FEE2E2',   # Light red background
    'danger_dark': '#991B1B',    # Dark red text

    'warning': '#F59E0B',        # Orange - caution
    'warning_light': '#FEF3C7',  # Light orange background
    'warning_dark': '#92400E',   # Dark orange text

    'neutral': '#6B7280',        # Gray - HOLD signals
    'neutral_light': '#F3F4F6',  # Light gray background
    'neutral_dark': '#374151',   # Dark gray text

    # Background colors
    'background': '#F9FAFB',     # Page background
    'card': '#FFFFFF',           # Card background
    'card_hover': '#F3F4F6',     # Card hover state

    # Text colors
    'text_primary': '#111827',   # Primary text
    'text_secondary': '#6B7280', # Secondary text
    'text_muted': '#9CA3AF',     # Muted text
}

# =============================================================================
# SIGNAL STYLING
# =============================================================================

SIGNAL_COLORS = {
    'STRONG_BUY': {
        'bg': '#D1FAE5',
        'text': '#065F46',
        'emoji': '🟢',
        'icon': '📈'
    },
    'BUY': {
        'bg': '#ECFDF5',
        'text': '#047857',
        'emoji': '🟢',
        'icon': '📈'
    },
    'HOLD': {
        'bg': '#F3F4F6',
        'text': '#374151',
        'emoji': '⚪',
        'icon': '➖'
    },
    'SELL': {
        'bg': '#FEF3C7',
        'text': '#92400E',
        'emoji': '🟠',
        'icon': '📉'
    },
    'STRONG_SELL': {
        'bg': '#FEE2E2',
        'text': '#991B1B',
        'emoji': '🔴',
        'icon': '📉'
    }
}

# =============================================================================
# CSS STYLESHEET
# =============================================================================

def get_thoth_css():
    """Return the complete Thoth CSS stylesheet."""
    return """
<style>
    /* ================================
       THOTH DESIGN SYSTEM
       ================================ */

    /* Root variables */
    :root {
        --thoth-primary: #1E3A5F;
        --thoth-primary-light: #2C5282;
        --thoth-success: #10B981;
        --thoth-danger: #EF4444;
        --thoth-warning: #F59E0B;
        --thoth-neutral: #6B7280;
        --thoth-bg: #F9FAFB;
    }

    /* Main header styling */
    .thoth-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1E3A5F;
        margin-bottom: 0.25rem;
        letter-spacing: -0.025em;
    }

    .thoth-subheader {
        font-size: 1.1rem;
        color: #6B7280;
        margin-bottom: 1.5rem;
        font-weight: 400;
    }

    /* Section headers */
    .section-header {
        font-size: 1.25rem;
        font-weight: 600;
        color: #1E3A5F;
        margin: 1.5rem 0 0.75rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #E5E7EB;
    }

    /* Signal badges */
    .signal-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .signal-strong-buy {
        background-color: #D1FAE5;
        color: #065F46;
    }

    .signal-buy {
        background-color: #ECFDF5;
        color: #047857;
    }

    .signal-hold {
        background-color: #F3F4F6;
        color: #374151;
    }

    .signal-sell {
        background-color: #FEF3C7;
        color: #92400E;
    }

    .signal-strong-sell {
        background-color: #FEE2E2;
        color: #991B1B;
    }

    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, #FFFFFF 0%, #F9FAFB 100%);
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        padding: 1.25rem;
        margin: 0.5rem 0;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        transition: all 0.2s ease;
    }

    .metric-card:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        transform: translateY(-1px);
    }

    .metric-card-title {
        font-size: 0.875rem;
        color: #6B7280;
        font-weight: 500;
        margin-bottom: 0.25rem;
    }

    .metric-card-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: #1E3A5F;
    }

    .metric-card-delta {
        font-size: 0.875rem;
        margin-top: 0.25rem;
    }

    .delta-positive {
        color: #10B981;
    }

    .delta-negative {
        color: #EF4444;
    }

    /* Player cards */
    .player-card {
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
        transition: all 0.2s ease;
    }

    .player-card:hover {
        border-color: #1E3A5F;
        box-shadow: 0 4px 12px rgba(30, 58, 95, 0.15);
    }

    .player-name {
        font-weight: 600;
        color: #1E3A5F;
        font-size: 1rem;
    }

    .player-meta {
        color: #6B7280;
        font-size: 0.875rem;
    }

    /* Data tables */
    .thoth-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.875rem;
    }

    .thoth-table th {
        background: #F9FAFB;
        color: #1E3A5F;
        font-weight: 600;
        text-align: left;
        padding: 0.75rem 1rem;
        border-bottom: 2px solid #E5E7EB;
    }

    .thoth-table td {
        padding: 0.75rem 1rem;
        border-bottom: 1px solid #F3F4F6;
    }

    .thoth-table tr:hover {
        background: #F9FAFB;
    }

    /* Value displays */
    .value-positive {
        color: #10B981;
        font-weight: 600;
    }

    .value-negative {
        color: #EF4444;
        font-weight: 600;
    }

    .value-neutral {
        color: #6B7280;
    }

    /* Info boxes */
    .info-box {
        background: #EFF6FF;
        border: 1px solid #BFDBFE;
        border-radius: 8px;
        padding: 1rem;
        color: #1E40AF;
        font-size: 0.875rem;
    }

    .success-box {
        background: #ECFDF5;
        border: 1px solid #A7F3D0;
        border-radius: 8px;
        padding: 1rem;
        color: #065F46;
        font-size: 0.875rem;
    }

    .warning-box {
        background: #FFFBEB;
        border: 1px solid #FCD34D;
        border-radius: 8px;
        padding: 1rem;
        color: #92400E;
        font-size: 0.875rem;
    }

    /* Footer */
    .thoth-footer {
        margin-top: 2rem;
        padding-top: 1rem;
        border-top: 1px solid #E5E7EB;
        color: #9CA3AF;
        font-size: 0.75rem;
        text-align: center;
    }

    /* Sidebar styling */
    .sidebar-section {
        margin-bottom: 1.5rem;
    }

    .sidebar-title {
        font-weight: 600;
        color: #1E3A5F;
        margin-bottom: 0.5rem;
    }

    /* Quick actions */
    .quick-action {
        display: inline-flex;
        align-items: center;
        padding: 0.5rem 1rem;
        background: #F3F4F6;
        border-radius: 8px;
        color: #374151;
        font-size: 0.875rem;
        margin: 0.25rem;
        cursor: pointer;
        transition: all 0.2s;
    }

    .quick-action:hover {
        background: #E5E7EB;
        color: #1E3A5F;
    }

    /* Model metrics */
    .model-stat {
        display: inline-block;
        background: #EFF6FF;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-size: 0.75rem;
        color: #1E40AF;
        font-weight: 500;
    }

    /* Responsive adjustments */
    @media (max-width: 768px) {
        .thoth-header {
            font-size: 1.75rem;
        }
        .metric-card-value {
            font-size: 1.25rem;
        }
    }

    /* Hide Streamlit branding (optional) */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Custom scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }

    ::-webkit-scrollbar-track {
        background: #F3F4F6;
    }

    ::-webkit-scrollbar-thumb {
        background: #CBD5E1;
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: #94A3B8;
    }
</style>
"""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_signal_badge(signal: str) -> str:
    """Return HTML for a signal badge."""
    signal = signal.upper() if signal else 'HOLD'
    signal_class = signal.lower().replace('_', '-')
    return f'<span class="signal-badge signal-{signal_class}">{signal.replace("_", " ")}</span>'


def get_signal_color(signal: str) -> dict:
    """Return color info for a signal."""
    signal = signal.upper() if signal else 'HOLD'
    return SIGNAL_COLORS.get(signal, SIGNAL_COLORS['HOLD'])


def get_signal_emoji(signal: str) -> str:
    """Return emoji for a signal."""
    return get_signal_color(signal)['emoji']


def format_value(value, is_delta: bool = False) -> str:
    """Format a numeric value with appropriate styling."""
    if value is None:
        return "N/A"

    if is_delta:
        if value > 0:
            return f'<span class="value-positive">+{value:,.0f}</span>'
        elif value < 0:
            return f'<span class="value-negative">{value:,.0f}</span>'
        else:
            return f'<span class="value-neutral">{value:,.0f}</span>'
    else:
        return f"{value:,.0f}"


def format_percentage(value, is_delta: bool = False) -> str:
    """Format a percentage with appropriate styling."""
    if value is None:
        return "N/A"

    if is_delta:
        if value > 0:
            return f'<span class="value-positive">+{value:.1f}%</span>'
        elif value < 0:
            return f'<span class="value-negative">{value:.1f}%</span>'
        else:
            return f'<span class="value-neutral">{value:.1f}%</span>'
    else:
        return f"{value:.1f}%"


def create_metric_card(title: str, value: str, delta: str = None, delta_positive: bool = True) -> str:
    """Return HTML for a metric card."""
    delta_html = ""
    if delta:
        delta_class = "delta-positive" if delta_positive else "delta-negative"
        delta_html = f'<div class="metric-card-delta {delta_class}">{delta}</div>'

    return f'''
    <div class="metric-card">
        <div class="metric-card-title">{title}</div>
        <div class="metric-card-value">{value}</div>
        {delta_html}
    </div>
    '''


def create_player_card(name: str, position: str, team: str, age: int,
                       ktc_value: int, signal: str, value_gap: float = None) -> str:
    """Return HTML for a player card."""
    signal_badge = get_signal_badge(signal)
    gap_html = ""
    if value_gap is not None:
        gap_html = f'| Gap: {format_value(value_gap, is_delta=True)}'

    return f'''
    <div class="player-card">
        <div class="player-name">{name}</div>
        <div class="player-meta">{position} | {team} | Age {age}</div>
        <div style="margin-top: 0.5rem;">
            KTC: {ktc_value:,} {gap_html}
        </div>
        <div style="margin-top: 0.5rem;">{signal_badge}</div>
    </div>
    '''


# =============================================================================
# PAGE CONFIGURATION
# =============================================================================

THOTH_PAGE_CONFIG = {
    'page_title': 'Thoth - Dynasty Fantasy Football Intelligence',
    'page_icon': '🔮',
    'layout': 'wide',
    'initial_sidebar_state': 'expanded'
}


def apply_thoth_style():
    """Apply Thoth styling to a Streamlit page."""
    import streamlit as st
    st.markdown(get_thoth_css(), unsafe_allow_html=True)


def render_thoth_header(title: str, subtitle: str = None):
    """Render the standard Thoth page header."""
    import streamlit as st
    st.markdown(f'<h1 class="thoth-header">🔮 {title}</h1>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<p class="thoth-subheader">{subtitle}</p>', unsafe_allow_html=True)


def render_thoth_footer():
    """Render the standard Thoth footer."""
    import streamlit as st
    st.markdown('''
    <div class="thoth-footer">
        Thoth Dynasty Intelligence | ML Model R²=0.87 | 3,700+ Players | 40+ Features
    </div>
    ''', unsafe_allow_html=True)


# =============================================================================
# PLOTLY THEME
# =============================================================================

PLOTLY_THEME = {
    'layout': {
        'font': {'family': 'Inter, system-ui, sans-serif', 'color': '#374151'},
        'paper_bgcolor': 'rgba(0,0,0,0)',
        'plot_bgcolor': 'rgba(0,0,0,0)',
        'title': {'font': {'color': '#1E3A5F', 'size': 18}},
        'colorway': ['#1E3A5F', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899'],
    },
    'colors': {
        'buy': '#10B981',
        'sell': '#EF4444',
        'hold': '#6B7280',
        'primary': '#1E3A5F',
    }
}


def get_plotly_layout(title: str = None) -> dict:
    """Return Plotly layout with Thoth styling."""
    layout = PLOTLY_THEME['layout'].copy()
    if title:
        layout['title'] = {'text': title, **PLOTLY_THEME['layout']['title']}
    return layout
