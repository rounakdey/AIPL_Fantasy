import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from streamlit_autorefresh import st_autorefresh

# Import our custom modules
import utils
import database as db
import scraper

# --- APP UI CONFIG ---
st.set_page_config(page_title="IPL 2026 Season", layout="wide")

if "refresh_enabled" not in st.session_state: st.session_state.refresh_enabled = True
if "last_refresh" not in st.session_state: st.session_state.last_refresh = "Never"

# --- TIME LOGIC ---
now_gmt = datetime.now(timezone.utc)
schedule = utils.load_schedule()

# Cold Start Match Selection (Current time minus 6 hours)
if "selected_idx" not in st.session_state:
    target_time = now_gmt - timedelta(hours=6)
    # Find the first match where match_dt >= target_time
    future_matches = schedule[schedule['match_dt'] >= target_time]

    if not future_matches.empty:
        st.session_state.selected_idx = int(future_matches.index[0])
    else:
        st.session_state.selected_idx = 0

# Sidebar
with st.sidebar:
    st.title("IPL 2026")
    st.metric("Current Time (GMT)", now_gmt.strftime("%H:%M:%S GMT"))

    # Selectbox uses session state for persistence but allows user change
    selected_idx = st.selectbox(
        "Select Match",
        options=schedule.index,
        index=st.session_state.selected_idx,
        format_func=lambda x: schedule.iloc[x]['display'],
        key="match_selector"
    )
    # Update state only if user manually changes it
    st.session_state.selected_idx = selected_idx

    match_info = schedule.iloc[selected_idx]
    match_id = f"match_{selected_idx + 1}"
    current_url = match_info['URL']
    match_start_gmt = match_info['match_dt']
    is_match_started = now_gmt >= match_start_gmt

    st.divider()
    if 'logged_in' not in st.session_state: st.session_state.logged_in = False

    if not st.session_state.logged_in:
        u = st.text_input("Username")
        p = st.text_input("Password", type='password')
        if u and p:
            hpw = utils.hash_password(p)
            c1, c2 = st.columns(2)
            if c1.button("Login"):
                user_data = db.check_login(u, hpw)
                if user_data:
                    st.session_state.logged_in = True
                    st.session_state.username = u
                    st.rerun()
                else:
                    st.error("Invalid credentials")
            if c2.button("Join League"):
                # Check global count instead of match-specific count
                if db.get_total_user_count() < 10:
                    try:
                        db.join_league_all_matches(u, hpw)
                        st.success(f"Welcome {u}! Account Created Successfully.")
                        st.session_state.logged_in = True
                        st.session_state.username = u
                        st.rerun()
                    except Exception as e:
                        st.error(f"Join failed: {e}")
                else:
                    st.error("League is full! (Max 10 players)")
    else:
        st.success(f"User: {st.session_state.username}")
        if st.button("Logout"): st.session_state.logged_in = False; st.rerun()

# Auto-Refresh Logic
if st.session_state.refresh_enabled:
    st_autorefresh(interval=60000, key="global_refresh")
    st.session_state.live_df = scraper.get_live_stats(current_url)

tab_list = ["🏆 Leaderboard", "🏏 My Selection"]
if is_match_started:
    tab_list.append("⚔️ Matchups")
tabs = st.tabs(tab_list)
t1, t2 = tabs[0], tabs[1]
if is_match_started:
    t3 = tabs[2]

with t2:
    if st.session_state.logged_in:
        st.header(f"Squad Selection: {match_info['Team 1']} vs {match_info['Team 2']}")

        # Display Rules
        with st.expander("Show Selection Rules 📜"):
            st.markdown("""
            * **Total:** Exactly 11 players.
            * **Team Limit:** Max 8 players from one team.
            * **Overseas:** Max 4 overseas players (✈️).
            * **Roles:** At least 1 Batsman, 1 Bowler, 1 WK-Batsman, and 1 Allrounder.
            """)

        sq = utils.load_squads()
        ld = db.load_league_data(match_id)
        my_data = ld.get(st.session_state.username, {"p": set(), "c": "-", "vc": "-"})

        t1_p = sq[sq['Team'] == match_info['Team 1']]
        t2_p = sq[sq['Team'] == match_info['Team 2']]

        selected_players = []
        colL, colR = st.columns(2)

        with colL:
            st.subheader(match_info['Team 1'])
            for _, row in t1_p.iterrows():
                p_n = row['Player Name']
                icon = " ✈️" if str(row.get('Category', '')).strip() == "Overseas" else ""
                if st.checkbox(f"{p_n} ({row['Role']}){icon}", value=(p_n in my_data['p']), key=f"t1_{p_n}"):
                    selected_players.append(p_n)

        with colR:
            st.subheader(match_info['Team 2'])
            for _, row in t2_p.iterrows():
                p_n = row['Player Name']
                icon = " ✈️" if str(row.get('Category', '')).strip() == "Overseas" else ""
                if st.checkbox(f"{p_n} ({row['Role']}){icon}", value=(p_n in my_data['p']), key=f"t2_{p_n}"):
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
        valid_overseas = (overseas_count <= 4)
        valid_teams = (team1_count <= 8 and team2_count <= 8)
        valid_roles = (n_bat >= 1 and n_bowl >= 1 and n_wk >= 1 and n_ar >= 1)

        # UI Indicators
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Selected", f"{len(selected_players)}/11")
        c2.metric("Overseas ✈️", f"{overseas_count}/4", delta=None if valid_overseas else "Too many",
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
            if not valid_overseas: errors.append("Max 4 Overseas players allowed.")
            if not valid_teams: errors.append("Max 8 players from a single team.")
            if not valid_roles: errors.append("Must have at least 1 Batsman, 1 Bowler, 1 WK, and 1 Allrounder.")

            for err in errors:
                st.warning(err)
    else:
        st.subheader("🏏 Ready to build your XI?")
        st.info("Please **Log In** or **Join** via the sidebar to select your team for this match.")

        # Optional: Add a nice visual or tip for logged-out users
        st.markdown("""
                **Selection Rules Preview:**
                * Pick exactly 11 players.
                * Max 8 players from one team.
                * Max 4 Overseas players (✈️).
                * Must include: 1 WK, 1 Allrounder, 1 Batsman, 1 Bowler.
                """)

with t1:
    st.header(f"Standings: {match_info['Team 1']} vs {match_info['Team 2']}")
    cA, cB, cC = st.columns([1, 1, 1])
    if cA.button("🔄 FETCH NOW", key="f1"): st.session_state.live_df = scraper.get_live_stats(current_url)
    st.session_state.refresh_enabled = cB.checkbox("Auto Refresh (60s)", value=st.session_state.refresh_enabled,
                                                   key="c1")
    cC.write(f"⏱️ Last Update: **{st.session_state.last_refresh}**")

    live_df = st.session_state.get('live_df', pd.DataFrame())
    ld = db.load_league_data(match_id)
    if ld:
        standings = []
        # Create a points map if live data exists, else empty dict
        p_map = live_df.set_index('Player')['Total Points'].to_dict() if not live_df.empty else {}

        for u, info in ld.items():
            # --- NEW FILTER LOGIC ---
            # Skip this manager if they haven't picked a captain yet
            if info['c'] == "-":
                continue

            # Calculate score only if p_map is not empty, otherwise default to 0
            total_score = 0
            if p_map:
                for n in info['p']:
                    p_pts = p_map.get(n, 0)
                    if n == info['c']:
                        total_score += p_pts * 2
                    elif n == info['vc']:
                        total_score += p_pts * 1.5
                    else:
                        total_score += p_pts

            # Privacy: Hide C/VC if match hasn't started
            standings.append({
                "Manager": u,
                "Score": int(total_score),
                "Captain": info['c'] if is_match_started else "🔒 Hidden",
                "Vice-Captain": info['vc'] if is_match_started else "🔒 Hidden"
            })

        # Only show the table if we have at least one active manager
        if standings:
            st.table(pd.DataFrame(standings).sort_values(by="Score", ascending=False))
        else:
            st.info("No managers have locked in their teams for this match yet.")
    else:
        st.info("No registered managers found in the league.")

        # Show the player points table only if it actually has data
    if not live_df.empty:
        st.dataframe(live_df.sort_values(by="Total Points", ascending=False), width='stretch', hide_index=True)
    else:
        st.info("Waiting for live match data to appear on Cricbuzz...")

    st.divider()
    with st.expander("View Scoring System 📈"):
        st.table(pd.DataFrame([
            {"Category": "Batting", "Action": "Run / 4 / 6", "Points": "+1 / +2 / +3"},
            {"Category": "Batting", "Action": "Milestone Bonus", "Points": "+10 every 25 runs"},
            {"Category": "Batting", "Action": "Strike-rate Bonus", "Points": "Runs - Balls"},
            {"Category": "Batting", "Action": "Duck", "Points": "-10"},
            {"Category": "Bowling", "Action": "Wicket / Maiden", "Points": "+25 / +15"},
            {"Category": "Bowling", "Action": "Economy Bonus", "Points": "(Balls x 2) - Runs"},
            {"Category": "Bowling", "Action": "Hauls (3/5/7)", "Points": "+25 / +50 / +100"},
            {"Category": "Fielding", "Action": "Catch / Stump / Run-out", "Points": "+15 / +10 / +10"},
            {"Category": "Bonus", "Action": "Player of the Match", "Points": "+25"},
            {"Category": "Multipliers", "Action": "Captain", "Points": "2x Total Points"},
            {"Category": "Multipliers", "Action": "Vice-Captain", "Points": "1.5x Total Points"}
        ]))

if is_match_started:
    with t3:
        st.header("Matchups Comparison")
        ld = db.load_league_data(match_id)
        mgrs = list(ld.keys())

        if len(mgrs) >= 2:
            col_sel1, col_sel2 = st.columns(2)
            m1 = col_sel1.selectbox("Friend 1", mgrs, index=0)
            m2 = col_sel2.selectbox("Friend 2", mgrs, index=1)

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
                return int(score)


            score1, score2 = calc_score(m1), calc_score(m2)
            diff = abs(score1 - score2)

            # Display Difference
            st.divider()
            if score1 > score2:
                st.subheader(f"🏆 {m1} is ahead of {m2} by {diff} points")
            elif score2 > score1:
                st.subheader(f"🏆 {m2} is ahead of {m1} by {diff} points")
            else:
                st.subheader("🤝 Both teams are currently tied!")
            st.divider()

            # Define Colors
            st.markdown("""
                <style>
                    .common-p { color: #00d4ff; font-weight: bold; } /* Cyan for common */
                    .unique-p { color: #ffcc00; font-weight: bold; } /* Gold for unique */
                    .role-header { font-size: 1.1em; border-bottom: 1px solid #444; margin-bottom: 10px; }
                </style>
            """, unsafe_allow_html=True)

            # Identify Common/Unique non-C/VC players
            s1, c1, vc1 = ld[m1]['p'], ld[m1]['c'], ld[m1]['vc']
            s2, c2, vc2 = ld[m2]['p'], ld[m2]['c'], ld[m2]['vc']

            # Players to compare (excluding their specific C/VC roles)
            comp1 = s1 - {c1, vc1}
            comp2 = s2 - {c2, vc2}
            common = comp1.intersection(comp2)

            cA, cB = st.columns(2)
            for manager, col, pks, c, vc, other_pks in [(m1, cA, s1, c1, vc1, s2), (m2, cB, s2, c2, vc2, s1)]:
                with col:
                    st.markdown(f"<div class='role-header'>{manager}'s Squad</div>", unsafe_allow_html=True)
                    st.write(f"⭐ **Captain:** {c} ({int(p_map.get(c, 0) * 2)} pts)")
                    st.write(f"🎖️ **Vice-Captain:** {vc} ({int(p_map.get(vc, 0) * 1.5)} pts)")

                    # Sort and display remaining players
                    for p in sorted(list(pks - {c, vc})):
                        pts = int(p_map.get(p, 0))
                        # Determine if player is common or unique
                        cls = "common-p" if p in other_pks else "unique-p"
                        symbol = "●" if p in other_pks else "○"
                        st.markdown(f"<span class='{cls}'>{symbol} {p}: {pts} pts</span>", unsafe_allow_html=True)
        else:
            st.info("Need at least 2 users to compare matchups.")
else:
    # Inform users why the tab is missing if they are looking for it
    st.sidebar.info("⚔️ Matchups will unlock once the match starts.")