import streamlit as st
import pandas as pd
import database as db
import utils
from utils import rounds

# --- Leaderboard ---
def render_leaderboard(match_id, is_match_started, ld, live_df):
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
            if match_id in rounds['round3']: total_score -= (opener_count * 50)

        # Privacy: Hide C/VC if match hasn't started
        ldbrd_row = {
            "Manager": u,
            "Score": int(total_score),
            "Captain": info['c'] if is_match_started else "🔒 Hidden",
            "Vice-Captain": info['vc'] if is_match_started else "🔒 Hidden",
        }
        if match_id in rounds['round3']: ldbrd_row["Openers"] = opener_count if is_match_started else "🔒 Hidden"
        standings.append(ldbrd_row)

    standings = sorted(standings, key=lambda x: (-x['Score'], x['Manager']))
    # Only show the table if we have at least one active manager
    if standings:
        st.table(pd.DataFrame(standings))
    else:
        st.info("No managers have locked in their teams for this match yet.")

    return standings


# --- Path to H2H/#1 analysis ---
def render_strategy(curr_user, h2h_sched, match_id, standings, ld, live_df):
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
                    gap = target['Score'] - next(s['Score'] for s in standings if s['Manager'] == curr_user)
                    st.write(
                        f"🏆 **You are currently leading** with a {abs(gap)} pts lead over **{target['Manager']}**!"
                        f" To stay ahead, here is the breakdown:")
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

def render_performance(match_id, ld, live_df):
    st.subheader("Live Player Performance")
    # Show the player points table only if it actually has data
    if not live_df.empty:
        display_df = live_df.copy()
        if match_id not in rounds['round3']: display_df.drop(columns = ['Opener'], inplace = True)

        # 1. Identify active managers and count player picks
        active_ld = {m: data for m, data in ld.items() if data['c'] != "-"}

        # Add columns for each manager
        for mgr_name, mgr_data in active_ld.items():

            def get_mgr_status(player_name):
                if player_name == mgr_data['c']: return "⭐"
                elif player_name == mgr_data['vc']: return "🎖️"
                elif player_name in mgr_data['p']: return "✅"
                return ""

            display_df[mgr_name[:10]] = display_df['Player'].apply(get_mgr_status)
        st.dataframe(display_df.sort_values(by="Total Points", ascending=False), width='stretch', hide_index=True)
        st.info("⭐ = Captain, 🎖️ = Vice-captain")
    else:
        st.info("Waiting for live match data to appear on Cricbuzz...")
