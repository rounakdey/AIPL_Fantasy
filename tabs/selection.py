import streamlit as st
import database as db
import utils


def render_selection(match_id, match_info, lock_master_flag, is_match_started):

    if is_match_started and lock_master_flag:
        # --- VIEW ONLY MODE ---
        st.warning("🔒 Match has started! Team selection is now locked.")

        # Load the user's saved team to show them what they picked
        ld = db.load_league_data(match_id)
        my_data = ld.get(st.session_state.username, {"p": set(), "c": "-", "vc": "-"})

        if my_data['c'] != "-":
            st.subheader("Your Locked XI")
            st.write(f"⭐ **Captain:** {my_data['c']}")
            st.write(f"🎖️ **Vice-Captain:** {my_data['vc']}")

            # Show the rest of the players in a simple list or read-only columns
            p_list = sorted(list(my_data['p'] - {my_data['c'], my_data['vc']}))
            st.write("🏃 **Players:** " + ", ".join(p_list))
        else:
            st.info("You did not submit a team for this match.")
    else:
        # --- MOBILE COMPACT CSS ---
        st.markdown("""
                    <style>
                        /* Force columns to stay side-by-side on mobile */
                        [data-testid="column"] {
                            width: calc(50% - 1rem) !important;
                            flex: 1 1 calc(50% - 1rem) !important;
                            min-width: calc(50% - 1rem) !important;
                        }
                        /* Tighten the spacing between checkboxes */
                        .stCheckbox {
                            margin-bottom: -15px;
                        }
                        /* Font size adjustment for names */
                        .stCheckbox label p {
                            font-size: 14px !important;
                            white-space: nowrap;
                            overflow: hidden;
                            text-overflow: ellipsis;
                        }
                    </style>
                """, unsafe_allow_html=True)

        # Mapping long roles to icons for space
        role_icons = {
            "Batsman": "🏏",
            "Bowler": "⚾",
            "WK-Batsman": "🧤",
            "Batting Allrounder": "🏏⚾",
            "Bowling Allrounder": "⚾🏏"
        }
        st.header(f"Squad Selection: {match_info['Team 1']} vs {match_info['Team 2']}")

        # Display Rules
        with st.expander("Show Selection Rules 📜"):
            st.markdown("""
            * **Total:** Exactly 11 players.
            * **Team Limit:** Max 8 players from one team.
            * **Roles:** At least 1 Batsman, 1 Bowler, 1 WK-Batsman, and 1 Allrounder.
            """)

        sq = utils.load_squads()
        ld = db.load_league_data(match_id)
        my_data = ld.get(st.session_state.username, {"p": set(), "c": "-", "vc": "-"})

        lineups = st.session_state.get("lineups", {})

        t1_p_raw = sq[sq['Team'] == match_info['Team 1']]
        t2_p_raw = sq[sq['Team'] == match_info['Team 2']]

        # Apply the new sort logic
        t1_p = utils.sort_squad(t1_p_raw.copy(), lineups)
        t2_p = utils.sort_squad(t2_p_raw.copy(), lineups)

        selected_players = []
        colL, colR = st.columns(2)

        # Display Columns with Icons
        for col, team_df, team_name in [(colL, t1_p, match_info['Team 1']), (colR, t2_p, match_info['Team 2'])]:
            with col:
                st.subheader(team_name[:3].upper())  # Shorten name (e.g., RCB)
                for _, row in team_df.iterrows():
                    p_n = row['Player Name']
                    role = row['Role']
                    icon = role_icons.get(role, "")
                    os_icon = "✈️" if str(row.get('Category', '')).strip() == "Overseas" else ""
                    # --- Lineup Dot ---
                    status_dot = lineups.get(p_n, "")  # Will be 🟢, 🟣, 🔴 or empty
                    # Create a very compact label: Icon + ShortName + OS
                    label = f"{icon}{p_n}{os_icon}{status_dot}"

                    if st.checkbox(label, value=(p_n in my_data['p']), key=f"sel_{team_name}_{p_n}"):
                        selected_players.append(p_n)

        # --- VALIDATION LOGIC ---
        st.divider()
        sel_df = sq[sq['Player Name'].isin(selected_players)]

        overseas_count = len(sel_df[sel_df['Category'] == 'Overseas'])
        team1_count = len(sel_df[sel_df['Team'] == match_info['Team 1']])
        team2_count = len(sel_df[sel_df['Team'] == match_info['Team 2']])

        # Role Counts
        n_bat = len(sel_df[sel_df['Role'] == 'Batsman'])
        n_bowl = len(sel_df[sel_df['Role'] == 'Bowler'])
        n_wk = len(sel_df[sel_df['Role'] == 'WK-Batsman'])
        n_ar = len(sel_df[sel_df['Role'].isin(['Batting Allrounder', 'Bowling Allrounder'])])

        # Validation Checks
        valid_count = (len(selected_players) == 11)
        valid_overseas = (overseas_count <= 11)
        valid_teams = (team1_count <= 8 and team2_count <= 8)
        valid_roles = (n_bat >= 1 and n_bowl >= 1 and n_wk >= 1 and n_ar >= 1)

        # UI Indicators
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Selected", f"{len(selected_players)}/11")
        c2.metric("Overseas ✈️", f"{overseas_count}/11", delta=None if valid_overseas else "Too many",
                  delta_color="inverse")
        c3.metric("Team Max", f"{max(team1_count, team2_count)}/8")
        c4.metric("WK/AR/Bat/Bowl", f"{n_wk}/{n_ar}/{n_bat}/{n_bowl}")

        if valid_count and valid_overseas and valid_teams and valid_roles:
            c1, c2 = st.columns(2)
            with c1:
                cap = st.selectbox("Select Captain (2x)", selected_players,
                                   index=selected_players.index(my_data['c']) if my_data[
                                                                                     'c'] in selected_players else 0)
            with c2:
                # Filter out the selected Captain from VC options
                vc_options = [p for p in selected_players if p != cap]
                vc = st.selectbox("Select Vice-Captain (1.5x)", vc_options,
                                  index=vc_options.index(my_data['vc']) if my_data['vc'] in vc_options else 0)

            if st.button("💾 Save My Team"):
                db.save_user_team(st.session_state.username, match_id, selected_players, cap, vc)
                st.success("Selection Locked!")
        else:
            errors = []
            if not valid_count: errors.append("Select exactly 11 players.")
            if not valid_overseas: errors.append("Max 11 overseas✈️ players allowed.")
            if not valid_teams: errors.append("Max 8 players from a single team.")
            if not valid_roles: errors.append("Must have at least 1 Batsman, 1 Bowler, 1 WK, and 1 Allrounder.")

            for err in errors:
                st.warning(err)