import streamlit as st
import pandas as pd
from supabase import create_client

SUPABASE_URL = st.secrets["connections"]["supabase"]["url"]
SUPABASE_KEY = st.secrets["connections"]["supabase"]["key"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_total_user_count():
    """Checks the global number of registered managers (Max 10)."""
    res = supabase.table("users").select("username", count="exact").execute()
    return res.count if res.count is not None else 0


def check_login(username, hashed_pw):
    """Authenticates against the global users table."""
    res = supabase.table("users").select("*").eq("username", username).eq("password", hashed_pw).execute()
    return res.data

def get_user_password(username):
    """Retrieves the hashed password for a specific user."""
    res = supabase.table("users").select("password").eq("username", username).execute()
    return res.data[0]['password'] if res.data else None

def update_password(username, new_hashed_pw):
    """Updates an existing user's password."""
    supabase.table("users").update({"password": new_hashed_pw}).eq("username", username).execute()

def join_league_all_matches(username, hashed_pw):
    """
    Registers a user globally and populates 70 matches in the match_teams table.
    """
    # 1. Register the global user account
    supabase.table("users").upsert({"username": username, "password": hashed_pw}).execute()

    # 2. Prepare 70 match entries for this user
    batch_data = [
        {"username": username, "match_id": f"match_{i}", "captain": "-", "vice_captain": "-"}
        for i in range(1, 71)
    ]

    # 3. Insert into match_teams (upsert handles existing entries safely)
    return supabase.table("match_teams").upsert(batch_data).execute()


def save_user_team(username, match_id, players, captain, vice_captain):
    """Saves match-specific squad and captains."""
    # Clear old selections for this specific match
    supabase.table("selections").delete().eq("username", username).eq("match_id", match_id).execute()

    # Insert new player selections
    if players:
        sel_data = [{"username": username, "match_id": match_id, "player_name": p} for p in players]
        supabase.table("selections").insert(sel_data).execute()

    # Update Captain/VC for this specific match only in the match_teams table
    supabase.table("match_teams").update({
        "captain": captain,
        "vice_captain": vice_captain
    }).eq("username", username).eq("match_id", match_id).execute()

    st.cache_data.clear()


@st.cache_data(ttl=30)
def load_league_data(match_id):
    """Loads all manager data (squads, C, VC) for a specific match ID."""
    try:
        # Pull match-specific info (Captains/VCs)
        users_res = supabase.table("match_teams").select("username, captain, vice_captain").eq("match_id",
                                                                                               match_id).execute()
        # Pull match-specific selections
        sels_res = supabase.table("selections").select("*").eq("match_id", match_id).execute()

        u_df = pd.DataFrame(users_res.data)
        s_df = pd.DataFrame(sels_res.data)
        data = {}

        if not u_df.empty:
            for _, row in u_df.iterrows():
                u = row['username']
                u_p = set(s_df[s_df['username'] == u]['player_name']) if not s_df.empty else set()
                data[u] = {
                    "p": u_p,
                    "c": row['captain'],
                    "vc": row.get('vice_captain', '-')
                }
        return data
    except Exception:
        return {}