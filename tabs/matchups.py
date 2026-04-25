import streamlit as st
import pandas as pd
import database as db
import utils


def render_t3(match_id, live_df):
    st.header("Matchups Comparison")
    ld = db.load_league_data(match_id)
    active_mgrs = [m for m, data in ld.items() if data['c'] != "-"]

    if len(active_mgrs) >= 2:
        # Selectbox logic with default index for logged in user...
        # Comparison logic...
        pass
    else:
        st.info("Need at least 2 managers with teams to compare.")