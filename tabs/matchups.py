import streamlit as st
import pandas as pd
import database as db
from utils import rounds


def render_matchups(match_id):
    st.header("Matchups Comparison")

    # --- MOBILE COMPACT CSS ---
    st.markdown("""
                <style>
                    [data-testid="column"] {
                        width: calc(50% - 0.5rem) !important;
                        flex: 1 1 calc(50% - 0.5rem) !important;
                        min-width: calc(50% - 0.5rem) !important;
                    }
                    .common-p { color: #00d4ff; font-weight: bold; font-size: 13px; margin-bottom: 2px; display: block; }
                    .unique-p { color: #ffcc00; font-weight: bold; font-size: 13px; margin-bottom: 2px; display: block; }
                    /* Banned Player Styling */
                    .banned-p { color: #ff4b4b !important; font-weight: bold; font-size: 13px; margin-bottom: 2px; display: block; }

                    .mgr-head { 
                        font-size: 15px; 
                        border-bottom: 1px solid #444; 
                        margin-bottom: 5px; 
                        font-weight: bold; 
                        text-transform: uppercase;
                    }
                    .stMarkdown div p { margin-bottom: 2px !important; font-size: 13px !important; }
                </style>
            """, unsafe_allow_html=True)

    ld = db.load_league_data(match_id)
    # Only show managers who have created a team
    mgrs = [m for m, data in ld.items() if data['c'] != "-"]

    # --- ROUND 7: Ban Registry ---
    ban_registry = {}
    if match_id in rounds.get('round7', []):
        for m_name, m_info in ld.items():
            if m_info['c'] != "-":
                b_p = m_info.get('b', "-")
                if b_p != "-" and b_p != "":
                    if b_p not in ban_registry:
                        ban_registry[b_p] = []
                    ban_registry[b_p].append(m_name)

    def is_player_banned(p_name, mgr_name):
        if match_id not in rounds.get('round7', []): return False
        if p_name in ban_registry:
            banners = ban_registry[p_name]
            # Rule: Banned if >1 person banned him OR (1 person banned him and it wasn't you)
            if len(banners) > 1 or mgr_name not in banners:
                return True
        return False

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
                if is_player_banned(p, user): continue
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
                # Check C/VC Ban Status
                c_dead = is_player_banned(c, manager)
                vc_dead = is_player_banned(vc, manager)
                c_pts = int(p_map.get(c, 0) * 2) if not c_dead else 0
                vc_pts = int(p_map.get(vc, 0) * 1.5) if not vc_dead else 0
                if not c_dead and (c in opener_set) and (match_id in rounds.get('round3', [])): c_pts -= 50
                if not vc_dead and (vc in opener_set) and (match_id in rounds.get('round3', [])): vc_pts -= 50

                # Render Captain
                if c_dead:
                    st.markdown(f"<div class='banned-p'>🚫 C: {c} (0)</div>", unsafe_allow_html=True)
                else:
                    st.write(f"⭐ **C:** {c} ({c_pts})")

                # Render Vice-Captain
                if vc_dead:
                    st.markdown(f"<div class='banned-p'>🚫 VC: {vc} (0)</div>", unsafe_allow_html=True)
                else:
                    st.write(f"🎖️ **VC:** {vc} ({vc_pts})")

                # Display remaining players
                for p in sorted(list(pks - {c, vc})):
                    p_dead = is_player_banned(p, manager)
                    pts = int(p_map.get(p, 0)) if not p_dead else 0
                    if not p_dead and (p in opener_set) and (match_id in rounds.get('round3', [])): pts -= 50

                    if p_dead:
                        cls, symbol = "banned-p", "✕"
                    else:
                        cls = "common-p" if p in other_pks else "unique-p"
                        symbol = "●" if p in other_pks else "○"

                    st.markdown(f"<div class='{cls}'>{symbol} {p}: {pts}</div>", unsafe_allow_html=True)
    else:
        st.info("Need at least 2 users to compare matchups.")