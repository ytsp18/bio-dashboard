"""Theme configuration for Bio Dashboard - Light Theme (BOI-inspired)."""
import streamlit as st

# Color Palette - Light Theme
COLORS = {
    "primary": "#2563eb",
    "primary_light": "#3B82F6",
    "primary_hover": "#1d4ed8",
    "success": "#16a34a",
    "warning": "#f59e0b",
    "danger": "#dc2626",
    "info": "#0891b2",
    "bg_main": "#f3f4f6",
    "bg_card": "#ffffff",
    "bg_sidebar": "#ffffff",
    "text_primary": "#1f2937",
    "text_secondary": "#6b7280",
    "text_muted": "#9ca3af",
    "border": "#e5e7eb",
}

LIGHT_THEME = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600;700&display=swap');

    /* Global font */
    html, body, [class*="css"] {
        font-family: 'Sarabun', sans-serif;
    }

    /* Metric Cards */
    .metric-card {
        background: #ffffff;
        border-radius: 8px;
        padding: 20px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        transition: transform 0.2s, box-shadow 0.2s;
    }

    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }

    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        line-height: 1.2;
        margin-bottom: 4px;
        color: #1f2937;
    }

    .metric-value-blue { color: #2563eb; }
    .metric-value-green { color: #16a34a; }
    .metric-value-orange { color: #f59e0b; }
    .metric-value-red { color: #dc2626; }

    .metric-label {
        font-size: 0.875rem;
        color: #6b7280;
        font-weight: 500;
    }

    /* Section Card */
    .section-card {
        background: #ffffff;
        border-radius: 8px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 20px;
        overflow: hidden;
    }

    .section-header {
        background: #ffffff;
        padding: 12px 20px;
        border-bottom: 1px solid #e5e7eb;
        border-left: 4px solid #2563eb;
        font-weight: 600;
        color: #1f2937;
    }

    .section-body {
        padding: 20px;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.5rem 1rem !important;
        font-weight: 600 !important;
        transition: all 0.2s !important;
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, #3B82F6 0%, #2563eb 100%) !important;
        box-shadow: 0 4px 6px rgba(37, 99, 235, 0.25) !important;
    }

    /* Download Button */
    .stDownloadButton > button {
        background: linear-gradient(135deg, #16a34a 0%, #15803d 100%) !important;
        color: white !important;
        border-radius: 8px !important;
        transition: all 0.2s !important;
    }

    .stDownloadButton > button:hover {
        box-shadow: 0 4px 6px rgba(22, 163, 74, 0.25) !important;
    }

    /* Alert Boxes */
    .alert-success {
        background: rgba(22, 163, 74, 0.08);
        border: 1px solid rgba(22, 163, 74, 0.2);
        border-left: 4px solid #16a34a;
        padding: 16px 20px;
        border-radius: 8px;
        color: #15803d;
    }

    .alert-warning {
        background: rgba(245, 158, 11, 0.08);
        border: 1px solid rgba(245, 158, 11, 0.2);
        border-left: 4px solid #f59e0b;
        padding: 16px 20px;
        border-radius: 8px;
        color: #b45309;
    }

    .alert-danger {
        background: rgba(220, 38, 38, 0.08);
        border: 1px solid rgba(220, 38, 38, 0.2);
        border-left: 4px solid #dc2626;
        padding: 16px 20px;
        border-radius: 8px;
        color: #b91c1c;
    }

    .alert-info {
        background: rgba(37, 99, 235, 0.08);
        border: 1px solid rgba(37, 99, 235, 0.2);
        border-left: 4px solid #2563eb;
        padding: 16px 20px;
        border-radius: 8px;
        color: #1d4ed8;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid #e5e7eb;
    }

    /* DataFrames */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        font-weight: 500;
    }

    /* Expander */
    .streamlit-expanderHeader {
        font-weight: 600;
        color: #1f2937;
    }
</style>
"""

# Keep backward compatibility
DARK_THEME = LIGHT_THEME


def apply_theme():
    """Apply light theme CSS."""
    st.markdown(LIGHT_THEME, unsafe_allow_html=True)


def get_color(name: str) -> str:
    """Get color by name from palette."""
    return COLORS.get(name, "#1f2937")


def render_theme_toggle():
    """Placeholder for theme toggle."""
    pass
