import streamlit as st
import database as db
import utils


def render_t2(match_id, lock_master_flag, is_match_started):
    st.header("Build Your Team")
    username = st.session_state.username

    # Check lock status
    is_locked = lock_master_flag and is_match_started

    if is_locked:
        st.warning("🔒 Match has started. Teams are locked!")

    # Squad selection logic...
    # (Extract the multiselect and save button logic from your current ipl.py)