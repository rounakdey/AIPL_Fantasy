import streamlit as st
import database as db
import utils
import time

def render_admin(match_id, match_info):
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