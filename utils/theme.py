"""Theme configuration for Bio Dashboard - Dark Theme."""
import streamlit as st

# Color Palette - Dark Theme
COLORS = {
    "primary": "#00D4AA",
    "primary_light": "#00E5BB",
    "success": "#10B981",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "bg_main": "#0E1117",
    "bg_card": "#1A1F2E",
    "bg_sidebar": "#1A1F2E",
    "text_primary": "#FAFAFA",
    "text_secondary": "#94A3B8",
    "text_muted": "#64748B",
    "border": "#2D3748",
}

DARK_THEME = """
<style>
    /* Metric Cards */
    .metric-card {
        background: #1A1F2E;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #2D3748;
    }

    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        line-height: 1.2;
        margin-bottom: 4px;
    }

    .metric-value-blue { color: #00D4AA; }
    .metric-value-green { color: #10B981; }
    .metric-value-orange { color: #F59E0B; }
    .metric-value-red { color: #EF4444; }

    .metric-label {
        font-size: 0.875rem;
        color: #94A3B8;
        font-weight: 500;
    }

    /* Section Card */
    .section-card {
        background: #1A1F2E;
        border-radius: 12px;
        border: 1px solid #2D3748;
        margin-bottom: 20px;
        overflow: hidden;
    }

    .section-header {
        background: #252B3B;
        padding: 12px 20px;
        border-bottom: 1px solid #2D3748;
        font-weight: 600;
        color: #FAFAFA;
    }

    .section-body {
        padding: 20px;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #00D4AA 0%, #00B894 100%) !important;
        color: #0E1117 !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.5rem 1rem !important;
        font-weight: 600 !important;
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, #00E5BB 0%, #00D4AA 100%) !important;
    }

    /* Download Button */
    .stDownloadButton > button {
        background: linear-gradient(135deg, #10B981 0%, #059669 100%) !important;
        color: white !important;
    }

    /* Alert Boxes */
    .alert-success {
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.3);
        border-left: 4px solid #10B981;
        padding: 16px 20px;
        border-radius: 8px;
        color: #10B981;
    }

    .alert-warning {
        background: rgba(245, 158, 11, 0.1);
        border: 1px solid rgba(245, 158, 11, 0.3);
        border-left: 4px solid #F59E0B;
        padding: 16px 20px;
        border-radius: 8px;
        color: #F59E0B;
    }

    .alert-danger {
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.3);
        border-left: 4px solid #EF4444;
        padding: 16px 20px;
        border-radius: 8px;
        color: #EF4444;
    }

    .alert-info {
        background: rgba(0, 212, 170, 0.1);
        border: 1px solid rgba(0, 212, 170, 0.3);
        border-left: 4px solid #00D4AA;
        padding: 16px 20px;
        border-radius: 8px;
        color: #00D4AA;
    }
</style>
"""

def apply_theme():
    """Apply dark theme CSS."""
    st.markdown(DARK_THEME, unsafe_allow_html=True)


def get_color(name: str) -> str:
    """Get color by name from palette."""
    return COLORS.get(name, "#FAFAFA")

def render_theme_toggle():
    """Placeholder for theme toggle."""
    pass
