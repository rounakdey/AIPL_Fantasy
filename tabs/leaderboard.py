import streamlit as st
import pandas as pd
import database as db
import utils


def render_t1(match_id, live_df, is_match_started):
    st.header(f"Leaderboard: {match_id.replace('_', ' ').upper()}")

    ld = db.load_league_data(match_id)
    curr_user = st.session_state.get('username')

    if not ld:
        st.info("No teams submitted for this match yet.")
        return

    # --- Standings Calculation ---
    standings = []
    p_map = live_df.set_index('Player')['Total Points'].to_dict() if not live_df.empty else {}
    round3_matches = [f"match_{i}" for i in range(19, 28)]
    opener_set = set(live_df[live_df['Opener'] == True]['Player']) if not live_df.empty else set()

    for u, info in ld.items():
        if info['c'] == "-": continue

        score = 0
        opener_count = 0
        for p in info['p']:
            pts = p_map.get(p, 0)
            if p == info['c']:
                score += pts * 2
            elif p == info['vc']:
                score += pts * 1.5
            else:
                score += pts
            if p in opener_set: opener_count += 1

        if match_id in round3_matches: score -= (opener_count * 50)

        ldbrd_row = {
            "Manager": u,
            "Score": int(score),
            "Captain": info['c'] if is_match_started else "🔒 Hidden",
            "Vice-Captain": info['vc'] if is_match_started else "🔒 Hidden",
        }
        if match_id in round3_matches:
            ldbrd_row["Openers"] = opener_count if is_match_started else "🔒 Hidden"
        standings.append(ldbrd_row)

    standings = sorted(standings, key=lambda x: x['Score'], reverse=True)
    st.table(pd.DataFrame(standings))

    # --- Gemini Path to #1 ---
    if st.session_state.get('logged_in') and not live_df.empty and len(standings) > 0:
        user_in_standings = any(s['Manager'] == curr_user for s in standings)
        if user_in_standings:
            render_path_to_one(curr_user, standings, ld)

    # --- Live Player Performance ---
    st.divider()
    st.subheader("Live Player Performance")
    if not live_df.empty:
        active_ld = {m: data for m, data in ld.items() if data['c'] != "-"}
        pick_counts = {}
        for mgr_data in active_ld.values():
            for player in mgr_data['p']:
                pick_counts[player] = pick_counts.get(player, 0) + 1

        display_df = live_df.copy()
        display_df.insert(display_df.columns.get_loc("Total Points") + 1, "Picked By",
                          display_df['Player'].map(lambda x: f"{pick_counts.get(x, 0)} Mgrs"))

        for mgr_name, mgr_data in active_ld.items():
            display_df[mgr_name[:10]] = display_df['Player'].apply(
                lambda x: "⭐ C" if x == mgr_data['c'] else "🎖️ VC" if x == mgr_data['vc'] else "✅" if x in mgr_data[
                    'p'] else ""
            )
        st.dataframe(display_df, use_container_width=True, hide_index=True)


def render_path_to_one(curr_user, standings, ld):
    # (Insert the Logic for Root For / Oppose here as per previous prompts)
    pass