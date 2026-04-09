import streamlit as st
import pandas as pd
import hashlib
import re
from datetime import datetime

def clean_name(name):
    return re.sub(r'\(.*?\)', '', name).strip()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def sort_squad(df, lineups):
    # Mapping for Status: 🟢 (1), 🟣 (2), 🔴 (3), None (4)
    status_order = {"🟢": 1, "🟣": 2, "🔴": 3}

    # Mapping for Roles
    role_order = {
        "Batsman": 1,
        "WK-Batsman": 2,
        "Batting Allrounder": 3,
        "Bowling Allrounder": 4,
        "Bowler": 5
    }

    def get_sort_keys(row):
        p_name = row['Player Name']
        status = lineups.get(p_name, "")

        # 1. Status Rank
        s_rank = status_order.get(status, 4)
        # 2. Role Rank
        r_rank = role_order.get(row['Role'], 6)
        # 3. Name (Alphabetical)
        return (s_rank, r_rank, p_name)

    # Apply the sort
    df['sort_key'] = df.apply(get_sort_keys, axis=1)
    df = df.sort_values('sort_key').drop(columns=['sort_key'])
    return df

@st.cache_data
def load_schedule():
    df = pd.read_csv("match_schedule.csv")
    df['match_dt'] = pd.to_datetime(df['Date'] + ' ' + df['Start Time'], format='%b %d %Y %H:%M %Z')
    df['display'] = df.apply(
        lambda x: f"Match {x.name + 1}: {x['Team 1']} vs {x['Team 2']}, {x['Date']}, {x['Start Time']}", axis=1)
    return df

@st.cache_data
def load_squads():
    # Ensure squads.csv has: Player Name, Role, Team, Category
    return pd.read_csv("squads.csv")