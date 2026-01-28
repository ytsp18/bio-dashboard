"""Theme configuration for Bio Dashboard - Dark Mode Only."""
import streamlit as st

DARK_THEME = """
<style>
    /* Main background */
    [data-testid="stAppViewContainer"] {
        background-color: #0e1117 !important;
    }

    [data-testid="stHeader"] {
        background-color: #0e1117 !important;
    }

    [data-testid="stSidebar"] {
        background-color: #161b22 !important;
    }

    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
        color: #c9d1d9 !important;
    }

    [data-testid="stSidebar"] label {
        color: #c9d1d9 !important;
    }

    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
    }

    /* Section headers */
    .section-header {
        background: linear-gradient(90deg, #21262d 0%, #161b22 100%);
        color: #c9d1d9;
        padding: 12px 20px;
        border-radius: 8px;
        margin: 20px 0 15px 0;
        font-size: 1em;
        font-weight: 600;
        border-left: 4px solid #58a6ff;
    }

    .section-title {
        font-size: 1.1em;
        font-weight: 600;
        color: #8b949e !important;
        margin: 25px 0 15px 0;
        padding-bottom: 8px;
        border-bottom: 1px solid #30363d;
    }

    /* Stat cards */
    .stat-card {
        background: #161b22;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        border: 1px solid #30363d;
    }

    .stat-number {
        font-size: 2.5em;
        font-weight: bold;
        color: #58a6ff;
    }

    .stat-label {
        font-size: 0.9em;
        color: #8b949e;
        margin-top: 5px;
    }

    /* Alert boxes */
    .alert-box {
        background: #2d1f1f;
        border-left: 4px solid #f85149;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
        color: #f85149;
    }

    .success-box {
        background: #1f2d1f;
        border-left: 4px solid #3fb950;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
        color: #3fb950;
    }

    .info-box {
        background: #1f2d3d;
        border-left: 4px solid #58a6ff;
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
        color: #58a6ff;
    }

    .card-detail {
        background: #161b22;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #30363d;
        margin: 10px 0;
        color: #c9d1d9;
    }

    .filter-section {
        background: #161b22;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
    }

    /* Text colors */
    h1, h2, h3, h4, h5, h6 {
        color: #c9d1d9 !important;
    }

    p, span, label {
        color: #8b949e;
    }

    .stSelectbox label, .stMultiSelect label, .stTextInput label, .stDateInput label {
        color: #c9d1d9 !important;
    }

    /* Metrics */
    [data-testid="stMetricValue"] {
        color: #58a6ff !important;
    }

    [data-testid="stMetricLabel"] {
        color: #8b949e !important;
    }

    [data-testid="stMetricDelta"] {
        color: #3fb950 !important;
    }

    /* DataFrame styling */
    [data-testid="stDataFrame"] {
        background-color: #161b22 !important;
    }

    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #161b22 !important;
    }

    .stTabs [data-baseweb="tab"] {
        color: #c9d1d9 !important;
    }

    /* Button styling */
    .stButton > button {
        background-color: #21262d !important;
        color: #c9d1d9 !important;
        border-color: #30363d !important;
    }

    .stButton > button:hover {
        background-color: #30363d !important;
    }

    /* Download button */
    .stDownloadButton > button {
        background-color: #238636 !important;
        color: white !important;
        border-color: #238636 !important;
    }

    .stDownloadButton > button:hover {
        background-color: #2ea043 !important;
    }

    /* Info/Warning/Error boxes */
    [data-testid="stAlert"] {
        background-color: #161b22 !important;
        color: #c9d1d9 !important;
    }

    /* Input fields */
    .stTextInput input {
        background-color: #0d1117 !important;
        color: #c9d1d9 !important;
        border-color: #30363d !important;
    }

    .stDateInput input {
        background-color: #0d1117 !important;
        color: #c9d1d9 !important;
    }

    /* Expander */
    .streamlit-expanderHeader {
        background-color: #161b22 !important;
        color: #c9d1d9 !important;
    }

    /* Radio buttons */
    .stRadio label {
        color: #c9d1d9 !important;
    }

    /* Checkbox */
    .stCheckbox label {
        color: #c9d1d9 !important;
    }
</style>
"""

def apply_theme():
    """Apply dark theme CSS."""
    st.markdown(DARK_THEME, unsafe_allow_html=True)

def render_theme_toggle():
    """Placeholder for theme toggle - now always dark mode."""
    # No longer needed since we only use dark mode
    pass
