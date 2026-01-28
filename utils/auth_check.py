"""Authentication check utility for all pages."""
import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import check_authentication, logout_button, show_role_badge


def require_login():
    """
    Check authentication and show logout button.
    Call this at the beginning of each page.
    Returns True if authenticated, stops execution if not.
    """
    if not check_authentication():
        st.stop()
        return False

    # Show logout button in sidebar
    logout_button()

    # Show role badge
    show_role_badge()

    return True
