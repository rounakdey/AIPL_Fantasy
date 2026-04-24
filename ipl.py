import streamlit as st
import pandas as pd
import time
from datetime import datetime, timezone, timedelta
from streamlit_autorefresh import st_autorefresh
import extra_streamlit_components as stx

# Import our custom modules
import utils
import database as db
import scraper

# Initialize Cookie Manager at the very top of the script
cookie_manager = stx.CookieManager()

# Initialize a master key flag for locking the team after match has started
lock_master_flag = True # Set True before deploying

# Initialize a flag to track manual logouts
if 'manual_logout' not in st.session_state:
    st.session_state.manual_logout = False

# Define a function to handle cookie-based login
def check_cookies():
    if not st.session_state.get('logged_in') and not st.session_state.manual_logout:
        saved_user = cookie_manager.get('ipl_username')
        saved_token = cookie_manager.get('ipl_token')  # This would be the hashed password

        if saved_user and saved_token:
            # Verify against database
            res = db.check_login(saved_user, saved_token)
            if res:
                st.session_state.logged_in = True
                st.session_state.username = saved_user
                return True
    return False


# Trigger the check
check_cookies()

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
        remember_me = st.checkbox("Remember Me")  # New Checkbox

        if u and p:
            hpw = utils.hash_password(p)
            c1, c2 = st.columns(2)

            # --- LOGIN BUTTON ---
            if c1.button("Login"):
                user_data = db.check_login(u, hpw)
                if user_data:
                    st.session_state.logged_in = True
                    st.session_state.username = u
                    st.session_state.manual_logout = False  # Reset the flag

                    if remember_me:
                        # Add unique 'key' arguments to avoid the DuplicateElementKey error
                        cookie_manager.set('ipl_username', u,
                                           expires_at=datetime.now() + timedelta(days=60),
                                           key="set_user_cookie")

                        # The second set needs a different key
                        cookie_manager.set('ipl_token', hpw,
                                           expires_at=datetime.now() + timedelta(days=60),
                                           key="set_token_cookie")
                        # CRITICAL: Wait 0.5 seconds for the browser to catch up
                        time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Invalid credentials")

            # --- JOIN LEAGUE BUTTON (Keeping your 10-player logic) ---
            if c2.button("Join League"):
                # 1. Check if user already exists
                existing_pw = db.get_user_password(u)

                if existing_pw is not None:
                    # SCENARIO: User exists. Check for Reset token "0"
                    if existing_pw == "0":
                        try:
                            # Reset: Update the "0" with the new hashed password
                            db.update_password(u, hpw)
                            st.success("Password Reset Successful!")
                            st.session_state.logged_in = True
                            st.session_state.username = u

                            if remember_me:
                                cookie_manager.set('ipl_username', u, expires_at=datetime.now() + timedelta(days=60),
                                                   key="reset_user_cookie")
                                cookie_manager.set('ipl_token', hpw, expires_at=datetime.now() + timedelta(days=60),
                                                   key="reset_token_cookie")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Reset failed: {e}")
                    else:
                        # SCENARIO: User exists but is not in reset mode
                        st.error("Username already taken. Please use 'Login' or contact Admin to reset.")

                else:
                    # SCENARIO: Brand New User
                    if db.get_total_user_count() < 10:
                        try:
                            db.join_league_all_matches(u, hpw)
                            st.success(f"Welcome {u}!")
                            st.session_state.logged_in = True
                            st.session_state.username = u

                            # Also remember them if they join with checkbox checked
                            if remember_me:
                                cookie_manager.set('ipl_username', u,
                                                   expires_at=datetime.now() + timedelta(days=60),
                                                   key="join_user_cookie")
                                cookie_manager.set('ipl_token', hpw,
                                                   expires_at=datetime.now() + timedelta(days=60),
                                                   key="join_token_cookie")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Join failed: {e}")
                    else:
                        st.error("League is full! (Max 10 players)")
    else:
        # --- LOGGED IN VIEW ---
        st.success(f"User: {st.session_state.username}")
        if st.button("Logout"):
            # 1. Clear session state immediately
            st.session_state.manual_logout = True
            st.session_state.logged_in = False
            st.session_state.username = None

            # 2. Handle Cookie Deletion (with the KeyError fix)
            try:
                if cookie_manager.get('ipl_username'):
                    cookie_manager.delete('ipl_username', key="delete_user_cookie")
                if cookie_manager.get('ipl_token'):
                    cookie_manager.delete('ipl_token', key="delete_token_cookie")

                # 3. Give the browser a moment to process the cookie deletion
                time.sleep(0.5)
            except:
                pass  # Fail gracefully if cookies were already gone

            # 4. Force an immediate full-page refresh
            st.rerun()

# Auto-Refresh Logic
if st.session_state.refresh_enabled:
    st_autorefresh(interval=60000, key="global_refresh")
    st.session_state.live_df = scraper.get_live_stats(current_url, match_id)

# --- DYNAMIC TABS ---
is_admin = st.session_state.get('username') == "Valar Morghulis" # Set your admin username here
# Define the base tabs
tab_list = ["🏆 Leaderboard", "🏏 My Selection"]
if is_match_started:
    tab_list.append("⚔️ Matchups")
    # Add Admin tab if logged in as admin
    if is_admin:
        tab_list.append("🛠️ Admin Edit")

tabs = st.tabs(tab_list)
t1, t2 = tabs[0], tabs[1]
if is_match_started:
    t3 = tabs[2]
    if is_admin:
        # If match is started, t3 is Matchups, so Admin is t4.
        t_admin = tabs[3]

with t2:
    if st.session_state.logged_in:
        time_to_start = (match_info['match_dt'] - now_gmt).total_seconds() / 60

        if "lineups" not in st.session_state or st.session_state.get("lineup_match") != match_id:
            if time_to_start <= 30:  # Start checking slightly early
                st.session_state.lineups = scraper.get_lineups(match_info['URL'])
                st.session_state.lineup_match = match_id
            else:
                st.session_state.lineups = {}
        lineups = st.session_state.get("lineups", {})

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
    else:
        st.subheader("🏏 Ready to build your XI?")
        st.info("Please **Log In** or **Join** via the sidebar to select your team for this match.")

        # Optional: Add a nice visual or tip for logged-out users
        st.markdown("""
                **Selection Rules Preview:**
                * Pick exactly 11 players.
                * Max 8 players from one team.
                * Must include: 1 WK, 1 Allrounder, 1 Batsman, 1 Bowler.
                """)

with t1:
    round3_matches = [f"match_{i}" for i in range(20, 29)]
    st.header(f"Standings: {match_info['Team 1']} vs {match_info['Team 2']}")
    cA, cB, cC = st.columns([1, 1, 1])
    if cA.button("🔄 FETCH NOW", key="f1"): st.session_state.live_df = scraper.get_live_stats(current_url, match_id)
    st.session_state.refresh_enabled = cB.checkbox("Auto Refresh (60s)", value=st.session_state.refresh_enabled,
                                                   key="c1")
    cC.write(f"⏱️ Last Update: **{st.session_state.last_refresh}**")

    live_df = st.session_state.get('live_df', pd.DataFrame())
    ld = db.load_league_data(match_id)
    if ld:
        standings = []
        # Create a points map if live data exists, else empty dict
        if not live_df.empty:
            p_map = live_df.set_index('Player')['Total Points'].to_dict()
            opener_set = set(live_df[live_df['Opener'] == True]['Player'])
        else:
            p_map = {}
            opener_set = set()

        for u, info in ld.items():
            # --- NEW FILTER LOGIC ---
            # Skip this manager if they haven't picked a captain yet
            if info['c'] == "-":
                continue

            # Calculate score only if p_map is not empty, otherwise default to 0
            total_score = 0
            opener_count = 0
            if p_map:
                for n in info['p']:
                    p_pts = p_map.get(n, 0)
                    if n == info['c']:
                        total_score += p_pts * 2
                    elif n == info['vc']:
                        total_score += p_pts * 1.5
                    else:
                        total_score += p_pts
                    # Check for opener penalty
                    if n in opener_set:
                        opener_count += 1

                # Apply Penalty: -50 per opener
                if match_id in round3_matches: total_score -= (opener_count * 50)

            # Privacy: Hide C/VC if match hasn't started
            ldbrd_row = {
                "Manager": u,
                "Score": int(total_score),
                "Captain": info['c'] if is_match_started else "🔒 Hidden",
                "Vice-Captain": info['vc'] if is_match_started else "🔒 Hidden",
            }
            if match_id in round3_matches: ldbrd_row["Openers"] = opener_count if is_match_started else "🔒 Hidden"
            standings.append(ldbrd_row)

        standings = sorted(standings, key=lambda x: (-x['Score'], x['Manager']))
        # Only show the table if we have at least one active manager
        if standings:
            st.table(pd.DataFrame(standings))
        else:
            st.info("No managers have locked in their teams for this match yet.")
    else:
        st.info("No registered managers found in the league.")

    # --- Path to Top and H2H Analysis ---
    if st.session_state.logged_in:
        curr_user = st.session_state.username
        h2h_sched = utils.load_h2h_schedule()
        # match_id is usually "match_25", convert to numeric index
        match_num = int(match_id.split('_')[1])

        # Find the row for this match and user
        h2h_row = h2h_sched[
            (h2h_sched['Match'] == match_num) &
            ((h2h_sched['Team1'] == curr_user) | (h2h_sched['Team2'] == curr_user))
            ]
        if not h2h_row.empty:
            row = h2h_row.iloc[0]
            opponent = row['Team2'] if row['Team1'] == curr_user else row['Team1']
        else:
            opponent = None

        if not live_df.empty and standings:
            user_in_standings = any(s['Manager'] == curr_user for s in standings)
            if user_in_standings:
                if opponent is not None:
                    # --- H2H Matchup ---
                    st.subheader(f"⚔️ H2H Strategy: Path to beating {opponent}")

                    # Check if opponent manager have created teams
                    opp_in_standings = any(s['Manager'] == opponent for s in standings)

                    if not opp_in_standings:
                        st.info(f"💡 You get a freebie, **{opponent}** has not created a team for this match.")
                    else:
                        # 2. Get Score Data from standings
                        my_score = next(s['Score'] for s in standings if s['Manager'] == curr_user)
                        opp_score = next(s['Score'] for s in standings if s['Manager'] == opponent)
                        h2h_diff = my_score - opp_score

                        if h2h_diff > 0:
                            st.write(f"✅ You are currently leading **{opponent}** by **{h2h_diff}** pts!")
                        elif h2h_diff < 0:
                            st.write(f"📈 You are trailing **{opponent}** by **{abs(h2h_diff)}** pts.")
                        else:
                            st.write(f"⚖️ You and **{opponent}** are currently tied!")

                        # 3. Structural Comparison (Mirroring your Path to #1 logic)
                        target_data = ld[opponent]
                        my_data = ld[curr_user]

                        col_root, col_oppose = st.columns(2)

                        with col_root:
                            st.success("📣 PLAYERS TO ROOT FOR")
                            # Unique Players
                            uniques = my_data['p'] - target_data['p']
                            for p in uniques:
                                if p == my_data['c']:
                                    st.write(f"⭐ **{p}**: Your Captain, they don't have him.")
                                elif p == my_data['vc']:
                                    st.write(f"🎖️ **{p}**: Your Vice-Captain, they don't have him.")
                                else:
                                    st.write(f"✅ **{p}**: You have him, they don't.")

                            # Captaincy Advantages
                            if my_data['c'] == target_data['vc']:
                                st.write(f"⭐ **{my_data['c']}**: Your Captain vs their Vice-Captain.")
                            if (my_data['c'] in target_data['p'] and my_data['c'] != target_data['c'] and my_data['c'] !=
                                    target_data['vc']):
                                st.write(f"⭐ **{my_data['c']}**: Your Captain vs their Regular.")
                            if my_data['vc'] in target_data['p'] and my_data['vc'] not in [target_data['c'],
                                                                                           target_data['vc']]:
                                st.write(f"🎖️ **{my_data['vc']}**: Your Vice-Captain vs their Regular.")

                        with col_oppose:
                            st.error("🚫 PLAYERS TO OPPOSE")
                            # Their Unique Players
                            their_uniques = target_data['p'] - my_data['p']
                            for p in their_uniques:
                                if p == target_data['c']:
                                    st.write(f"💀 **{p}**: Their Captain, you don't have him.")
                                elif p == target_data['vc']:
                                    st.write(f"⚠️ **{p}**: Their Vice-Captain, you don't have him.")
                                else:
                                    st.write(f"❌ **{p}**: They have him, you don't.")

                            # Their Captaincy Advantages
                            if target_data['c'] == my_data['vc']:
                                st.write(f"💀 **{target_data['c']}**: Their Captain vs your Vice-Captain.")
                            if (target_data['c'] in my_data['p'] and target_data['c'] != my_data['c'] and target_data[
                                'c'] != my_data['vc']):
                                st.write(f"💀 **{target_data['c']}**: Their Captain vs your Regular.")
                            if target_data['vc'] in my_data['p'] and target_data['vc'] not in [my_data['c'], my_data['vc']]:
                                st.write(f"⚠️ **{target_data['vc']}**: Their Vice-Captain vs your Regular.")
                else:
                    st.info(f"🏝️ You have no opponents for this match.")

                # --- Path to Top ---
                # Only calculate if there are at least two teams
                if len(standings) > 1:
                    st.subheader("🎯 Path to #1")
                    # 1. Identify Target (Top person, or 2nd if user is #1)
                    if standings[0]['Manager'] == curr_user:
                        target = standings[1]
                        st.write(
                            f"🏆 **You are currently leading!** To stay ahead of **{target['Manager']}**, here is the breakdown:")
                    else:
                        target = standings[0]
                        gap = target['Score'] - next(s['Score'] for s in standings if s['Manager'] == curr_user)
                        st.write(f"📈 **Chasing {target['Manager']}** ({gap} pts gap). Here is your path to the top:")

                    target_data = ld[target['Manager']]
                    my_data = ld[curr_user]

                    col_root, col_oppose = st.columns(2)

                    # 2. Logic: Who to Root For
                    with col_root:
                        st.success("📣 PLAYERS TO ROOT FOR")

                        # Unique Players
                        uniques = my_data['p'] - target_data['p']
                        for p in uniques:
                            if p == my_data['c']:
                                st.write(f"⭐ **{p}**: Your Captain, they don't have him.")
                            elif p == my_data['vc']:
                                st.write(f"🎖️ **{p}**: Your Vice-Captain, they don't have him.")
                            else:
                                st.write(f"✅ **{p}**: You have him, they don't.")

                        # Captaincy Advantages
                        # If I have C and they have VC/Regular OR I have VC and they have Regular
                        if my_data['c'] == target_data['vc']:
                            st.write(f"⭐ **{my_data['c']}**: Your Captain vs their Vice-Captain.")
                        if (my_data['c'] in target_data['p'] and my_data['c'] != target_data['c'] and my_data['c'] != target_data['vc']):
                            st.write(f"⭐ **{my_data['c']}**: Your Captain vs their Regular.")
                        if my_data['vc'] in target_data['p'] and my_data['vc'] not in [target_data['c'], target_data['vc']]:
                            st.write(f"🎖️ **{my_data['vc']}**: Your Vice-Captain vs their Regular.")

                    # 3. Logic: Who to Oppose
                    with col_oppose:
                        st.error("🚫 PLAYERS TO OPPOSE")

                        # Their Unique Players
                        their_uniques = target_data['p'] - my_data['p']
                        for p in their_uniques:
                            if p == target_data['c']:
                                st.write(f"💀 **{p}**: Their Captain, you don't have him.")
                            elif p == target_data['vc']:
                                st.write(f"⚠️ **{p}**: Their Vice-Captain, you don't have him.")
                            else:
                                st.write(f"❌ **{p}**: They have him, you don't.")

                        # Their Captaincy Advantages
                        if target_data['c'] == my_data['vc']:
                            st.write(f"💀 **{target_data['c']}**: Their Captain vs your Vice-Captain.")
                        if (target_data['c'] in my_data['p'] and target_data['c'] != my_data['c'] and target_data['c'] != my_data['vc']):
                            st.write(f"💀 **{target_data['c']}**: Their Captain vs your Regular.")
                        if target_data['vc'] in my_data['p'] and target_data['vc'] not in [my_data['c'], my_data['vc']]:
                            st.write(f"⚠️ **{target_data['vc']}**: Their Vice-Captain vs your Regular.")
        else:
            if opponent is not None:
                st.info(f"⚔️ **{opponent}** is your opponent for this match. Make sure to build a team to beat them!")
            else:
                st.info("🏝️ You have no opponents for this match.")

    st.divider()
    st.subheader("Live Player Performance")
    # Show the player points table only if it actually has data
    if not live_df.empty:
        display_df = live_df.copy()
        # Add columns for each manager
        for mgr_name, mgr_data in ld.items():
            # Skip managers who haven't picked a team (C is still "-")
            if mgr_data['c'] == "-":
                continue

            def get_mgr_status(player_name):
                if player_name == mgr_data['c']:
                    return "⭐"
                elif player_name == mgr_data['vc']:
                    return "🎖️"
                elif player_name in mgr_data['p']:
                    return "✅"
                return ""

            display_df[mgr_name[:10]] = display_df['Player'].apply(get_mgr_status)
        st.dataframe(display_df.sort_values(by="Total Points", ascending=False), width='stretch', hide_index=True)
        st.info("⭐ = Captain, 🎖️ = Vice-captain")
    else:
        st.info("Waiting for live match data to appear on Cricbuzz...")

    st.divider()
    with st.expander("View Scoring System 📈"):
        st.table(pd.DataFrame([
            {"Category": "Batting", "Action": "Run / 4 / 6 / Duck (only Non-Bowlers)", "Points": "+1 / +2 / +3 / -10"},
            {"Category": "Batting", "Action": "Milestone Bonus", "Points": "+10 every 25 runs"},
            {"Category": "Batting", "Action": "Strike-rate Bonus", "Points": "Runs - Balls"},
            {"Category": "Bowling", "Action": "Wicket / Maiden", "Points": "+25 / +15"},
            {"Category": "Bowling", "Action": "Economy Bonus", "Points": "(Balls x 3) - Runs"},
            {"Category": "Bowling", "Action": "Hauls (3/5/7)", "Points": "+25 / +50 / +100"},
            {"Category": "Fielding", "Action": "Catch / Stump / Run-out", "Points": "+15 / +10 / +10"},
            {"Category": "Bonus", "Action": "Player of the Match", "Points": "+25"},
            {"Category": "Multipliers", "Action": "Captain", "Points": "2x Total Points"},
            {"Category": "Multipliers", "Action": "Vice-Captain", "Points": "1.5x Total Points"},
            {"Category": "Round 3 Specific", "Action": "Per Opener", "Points": "-50"},
            {"Category": "Round 4 Specific", "Action": "Wicket / Hauls (3/5/7)", "Points": "+30 / +50 / +100 / +200"},
        ]))

if is_match_started:
    with t3:
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
                    if (p in opener_set) and (match_id in round3_matches):
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
                    if match_id in round3_matches:
                        if c in opener_set: c_pts -= 50
                        if vc in opener_set: vc_pts -= 50
                    st.write(f"⭐ **C:** {c} ({c_pts})")
                    st.write(f"🎖️ **VC:** {vc} ({vc_pts})")

                    # Display remaining players
                    for p in sorted(list(pks - {c, vc})):
                        pts = int(p_map.get(p, 0))
                        if (p in opener_set) and (match_id in round3_matches): pts -= 50
                        cls = "common-p" if p in other_pks else "unique-p"
                        symbol = "●" if p in other_pks else "○"
                        # Use div with display:block (via CSS) to ensure vertical stacking
                        st.markdown(f"<div class='{cls}'>{symbol} {p}: {pts}</div>", unsafe_allow_html=True)
        else:
            st.info("Need at least 2 users to compare matchups.")

    # Only allow admin edits if the match has started
    if is_admin:
        with t_admin:
            st.header("Admin Override: Manual Team Edit")
            st.info(
                "As Admin, you can edit any manager's team. Rules (Overseas/Role) are bypassed, but you must pick exactly 11 players.")

            # 1. Select which manager to edit
            all_managers = list(db.load_league_data(match_id).keys())
            target_user = st.selectbox("Select Manager to Edit", all_managers)

            # 2. Load the current team for the selected manager
            ld = db.load_league_data(match_id)
            target_data = ld.get(target_user, {"p": set(), "c": "-", "vc": "-"})

            # --- Compact Selection Grid (Reuse your T2 style) ---
            sq = utils.load_squads()
            lineups = st.session_state.get("lineups", {})

            t1_p_admin = sq[sq['Team'] == match_info['Team 1']]
            t2_p_admin = sq[sq['Team'] == match_info['Team 2']]

            # Apply the sort here too
            t1_p = utils.sort_squad(t1_p_admin.copy(), lineups)
            t2_p = utils.sort_squad(t2_p_admin.copy(), lineups)

            admin_selected = []
            colL, colR = st.columns(2)

            for col, team_df, team_name in [(colL, t1_p, match_info['Team 1']), (colR, t2_p, match_info['Team 2'])]:
                with col:
                    st.subheader(team_name[:3].upper())
                    for _, row in team_df.iterrows():
                        p_n = row['Player Name']
                        # Admin doesn't need icons, just names and status if available
                        lineups = st.session_state.get("lineups", {})
                        dot = lineups.get(p_n, "")
                        label = f"{p_n} {'✈️' if row['Category'] == 'Overseas' else ''}{dot}"

                        if st.checkbox(label, value=(p_n in target_data['p']), key=f"admin_{target_user}_{p_n}"):
                            admin_selected.append(p_n)

            st.divider()

            # 3. Captain/VC for the edited user
            c_col, vc_col = st.columns(2)
            with c_col:
                new_c = st.selectbox("Set Captain", ["-"] + admin_selected,
                                     index=admin_selected.index(target_data['c']) + 1 if target_data[
                                                                                             'c'] in admin_selected else 0,
                                     key="admin_c")
            with vc_col:
                new_vc = st.selectbox("Set Vice-Captain", ["-"] + admin_selected,
                                      index=admin_selected.index(target_data['vc']) + 1 if target_data[
                                                                                               'vc'] in admin_selected else 0,
                                      key="admin_vc")

            # 4. Save Logic (Bypass everything except the 11-player count)
            if st.button("🛠️ FORCE UPDATE TEAM", use_container_width=True):
                if len(admin_selected) != 11:
                    st.error(f"Error: Exactly 11 players required (Currently {len(admin_selected)})")
                elif new_c == "-" or new_vc == "-":
                    st.error("Error: Must select Captain and Vice-Captain")
                else:
                    try:
                        db.save_user_team(target_user, match_id, admin_selected, new_c, new_vc)
                        st.success(f"SUCCESS: {target_user}'s team updated by Admin!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Database Error: {e}")

            st.divider()
            st.subheader(f"Account Actions for {target_user}")

            # New Reset Password Button
            if st.button(f"🔄 RESET PASSWORD FOR {target_user.upper()}", use_container_width=True):
                try:
                    # Set the password to "0" as per our reset logic
                    db.update_password(target_user, "0")
                    st.success(f"Success! {target_user}'s password has been set to '0'.")
                    st.info(
                        "The user can now reset their password by using the 'Join League' button with their username.")
                except Exception as e:
                    st.error(f"Failed to reset password: {e}")

else:
    # Inform users why the tab is missing if they are looking for it
    st.sidebar.info("⚔️ Matchups will unlock once the match starts.")