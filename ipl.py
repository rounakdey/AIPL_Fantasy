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

from utils import rounds
from tabs.selection import render_selection
from tabs.matchups import render_matchups
from tabs.admin_edit import render_admin
from tabs.leaderboard import render_leaderboard, render_strategy, render_performance

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

        render_selection(match_id, match_info, lock_master_flag, is_match_started)
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
    header_round_text = ""
    if match_id in rounds['round1']:
        header_round_text = "Round 1 (Vanilla):"
    elif match_id in rounds['round2']:
        header_round_text = "Round 2 (Foreigner Restriction):"
    elif match_id in rounds['round3']:
        header_round_text = "Round 3 (Opener Penalty):"
    elif match_id in rounds['round4']:
        header_round_text = "Round 4 (Bowler Bonus):"
    elif match_id in rounds['round5']:
        header_round_text = "Round 5 (Unique Player Bonus):"
    else:
        header_round_text = "Rules TBD:"

    # Construct the full HTML string
    full_header_html = f"""
    <div style="font-size:32px; font-weight:bold; line-height:1.2;">
        💎 {header_round_text}<br>
        {match_id.replace('_', ' ').upper()}, {match_info['Team 1']} vs {match_info['Team 2']}
    </div>
    <hr style="margin-top:5px; margin-bottom:20px; border:0; border-top:2px solid #31333F; opacity:0.2;">
    """

    st.markdown(full_header_html, unsafe_allow_html=True)

    cA, cB, cC = st.columns([1, 1, 1])
    if cA.button("🔄 FETCH NOW", key="f1"): st.session_state.live_df = scraper.get_live_stats(current_url, match_id)
    st.session_state.refresh_enabled = cB.checkbox("Auto Refresh (60s)", value=st.session_state.refresh_enabled,
                                                   key="c1")
    cC.write(f"⏱️ Last Update: **{st.session_state.last_refresh}**")

    live_df = st.session_state.get('live_df', pd.DataFrame())
    ld = db.load_league_data(match_id)

    # Add Pick counts and Scale scores if round 5
    if match_id in rounds['round5']:
        if not live_df.empty: live_df = utils.prepare_pick_counts(match_id, ld, live_df)

    # --- Leaderboard ---
    if ld:
        standings = render_leaderboard(match_id, is_match_started, ld, live_df)
    else:
        st.info("No registered managers found in the league.")

    st.divider()

    # --- Path to Top and H2H Analysis ---
    if st.session_state.logged_in:
        curr_user = st.session_state.username
        h2h_sched = utils.load_h2h_schedule()
        render_strategy(curr_user, h2h_sched, match_id, standings, ld, live_df)

    # --- Live Player Performances ---
    st.divider()
    render_performance(match_id, ld, live_df)

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
            {"Category": "Round 5 Specific", "Action": "Selection Rate Multiplier", "Points": "(10 / Picked by) x Total Points"},
        ]))

if is_match_started:
    with t3:
        render_matchups(match_id, live_df)

    # Only allow admin edits if the match has started
    if is_admin:
        with t_admin:
            render_admin(match_id, match_info)

else:
    # Inform users why the tab is missing if they are looking for it
    st.sidebar.info("⚔️ Matchups will unlock once the match starts.")