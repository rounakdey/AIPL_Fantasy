import streamlit as st
import pandas as pd
from supabase import create_client

SUPABASE_URL = st.secrets["connections"]["supabase"]["url"]
SUPABASE_KEY = st.secrets["connections"]["supabase"]["key"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_user_count(match_id):
    res = supabase.table("users").select("username", count="exact").eq("match_id", match_id).execute()
    return res.count if res.count is not None else 0

def save_user_team(username, match_id, players, captain, vice_captain):
    # Clear old selections
    supabase.table("selections").delete().eq("username", username).eq("match_id", match_id).execute()
    # Insert new selections
    sel_data = [{"username": username, "match_id": match_id, "player_name": p} for p in players]
    supabase.table("selections").insert(sel_data).execute()
    # Update Captain AND Vice-Captain
    supabase.table("users").update({
        "captain": captain,
        "vice_captain": vice_captain
    }).eq("username", username).eq("match_id", match_id).execute()
    st.cache_data.clear()

@st.cache_data(ttl=30)
def load_league_data(match_id):
    try:
        users_res = supabase.table("users").select("username, captain, vice_captain").eq("match_id", match_id).execute()
        sels_res = supabase.table("selections").select("*").eq("match_id", match_id).execute()
        u_df = pd.DataFrame(users_res.data)
        s_df = pd.DataFrame(sels_res.data)
        data = {}
        if not u_df.empty:
            for _, row in u_df.iterrows():
                u = row['username']
                u_p = set(s_df[s_df['username'] == u]['player_name']) if not s_df.empty else set()
                # Store both C and VC in the dictionary
                data[u] = {"p": u_p, "c": row['captain'], "vc": row.get('vice_captain', '-')}
        return data
    except:
        return {}

def join_user(username, match_id, hashed_pw):
    # Added default vice_captain as '-'
    return supabase.table("users").insert(
        {"username": username, "match_id": match_id, "password": hashed_pw, "captain": "-", "vice_captain": "-"}
    ).execute()

def check_login(username, hashed_pw):
    res = supabase.table("users").select("*").eq("username", username).eq("password", hashed_pw).execute()
    return res.data
