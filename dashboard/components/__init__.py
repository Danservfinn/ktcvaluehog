"""
Thoth Dashboard Components
==========================
Reusable components for the Thoth dashboard.
"""

from .design_system import (
    COLORS,
    SIGNAL_COLORS,
    PLOTLY_THEME,
    get_thoth_css,
    get_signal_badge,
    get_signal_color,
    get_signal_emoji,
    format_value,
    format_percentage,
    create_metric_card,
    create_player_card,
    apply_thoth_style,
    render_thoth_header,
    render_thoth_footer,
    get_plotly_layout,
    THOTH_PAGE_CONFIG,
)

from .tooltips import (
    FEATURE_TOOLTIPS,
    get_tooltip,
    render_feature_tooltip,
)

__all__ = [
    # Design System
    'COLORS',
    'SIGNAL_COLORS',
    'PLOTLY_THEME',
    'get_thoth_css',
    'get_signal_badge',
    'get_signal_color',
    'get_signal_emoji',
    'format_value',
    'format_percentage',
    'create_metric_card',
    'create_player_card',
    'apply_thoth_style',
    'render_thoth_header',
    'render_thoth_footer',
    'get_plotly_layout',
    'THOTH_PAGE_CONFIG',
    # Tooltips
    'FEATURE_TOOLTIPS',
    'get_tooltip',
    'render_feature_tooltip',
]
