import streamlit as st
import pandas as pd
import database as db
from utils import rounds


def render_matchups(match_id, live_df):
    st.header("Matchups Comparison")

    # --- MOBILE COMPACT CSS ---
    st.markdown("""
            <style>
                /* Force columns to stay side-by-side even on mobile */
                [data-testid="column"] {
                    width: calc(50% - 0.5rem) !important;
                    flex: 1 1 calc(50% - 0.5rem) !important;
                    min-width: calc(50% - 0.5rem) !important;
                }
                /* Styling for common and unique players */
                .common-p { color: #00d4ff; font-weight: bold; font-size: 13px; margin-bottom: 2px; display: block; }
                .unique-p { color: #ffcc00; font-weight: bold; font-size: 13px; margin-bottom: 2px; display: block; }
                /* Header for manager name */
                .mgr-head { 
                    font-size: 15px; 
                    border-bottom: 1px solid #444; 
                    margin-bottom: 5px; 
                    font-weight: bold; 
                    text-transform: uppercase;
                }
                /* Tighten spacing for st.write elements */
                .stMarkdown div p { margin-bottom: 2px !important; font-size: 13px !important; }
            </style>
        """, unsafe_allow_html=True)

    ld = db.load_league_data(match_id)
    # Only show managers who have created a team
    mgrs = [m for m, data in ld.items() if data['c'] != "-"]

    if len(mgrs) >= 2:
        col_sel1, col_sel2 = st.columns(2)
        # Find the index of the logged-in user in the active list
        current_user = st.session_state.get('username')
        default_index_m1 = 0
        if current_user in mgrs:
            default_index_m1 = mgrs.index(current_user)

        # Set Manager 1 to the current user, and Manager 2 to the next person in the list
        m1 = col_sel1.selectbox("Manager 1", mgrs, index=default_index_m1)

        # Logic for Manager 2 default (ensure it's not the same as Manager 1)
        default_index_m2 = 1 if default_index_m1 == 0 else 0
        m2 = col_sel2.selectbox("Manager 2", mgrs, index=default_index_m2)

        # Get Live Points Map
        live_df = st.session_state.get('live_df', pd.DataFrame())
        p_map = live_df.set_index('Player')['Total Points'].to_dict() if not live_df.empty else {}

        # Helper to calculate total match score
        def calc_score(user):
            pks, c, vc = ld[user]['p'], ld[user]['c'], ld[user]['vc']
            score = 0
            for p in pks:
                pts = p_map.get(p, 0)
                if p == c:
                    score += pts * 2
                elif p == vc:
                    score += pts * 1.5
                else:
                    score += pts
                if (p in opener_set) and (match_id in rounds['round3']):
                    score -= 50

            return int(score)

        opener_set = set(live_df[live_df['Opener'] == True]['Player']) if not live_df.empty else set()
        score1, score2 = calc_score(m1), calc_score(m2)
        diff = abs(score1 - score2)

        # Compact Difference Banner
        st.info(f"🏆 {'Tie' if score1 == score2 else f'{(m1 if score1 > score2 else m2)} leads by {diff} pts'}")

        # Identify Common/Unique non-C/VC players
        s1, c1, vc1 = ld[m1]['p'], ld[m1]['c'], ld[m1]['vc']
        s2, c2, vc2 = ld[m2]['p'], ld[m2]['c'], ld[m2]['vc']

        cA, cB = st.columns(2)
        # Comparison loop
        for manager, col, pks, c, vc, other_pks in [(m1, cA, s1, c1, vc1, s2), (m2, cB, s2, c2, vc2, s1)]:
            with col:
                st.markdown(f"<div class='mgr-head'>{manager}</div>", unsafe_allow_html=True)
                c_pts = int(p_map.get(c, 0) * 2)
                vc_pts = int(p_map.get(vc, 0) * 1.5)
                if match_id in rounds['round3']:
                    if c in opener_set: c_pts -= 50
                    if vc in opener_set: vc_pts -= 50
                st.write(f"⭐ **C:** {c} ({c_pts})")
                st.write(f"🎖️ **VC:** {vc} ({vc_pts})")

                # Display remaining players
                for p in sorted(list(pks - {c, vc})):
                    pts = int(p_map.get(p, 0))
                    if (p in opener_set) and (match_id in rounds['round3']): pts -= 50
                    cls = "common-p" if p in other_pks else "unique-p"
                    symbol = "●" if p in other_pks else "○"
                    # Use div with display:block (via CSS) to ensure vertical stacking
                    st.markdown(f"<div class='{cls}'>{symbol} {p}: {pts}</div>", unsafe_allow_html=True)
    else:
        st.info("Need at least 2 users to compare matchups.")