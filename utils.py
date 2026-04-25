import streamlit as st
import pandas as pd
import hashlib
import re
from datetime import datetime

# Define the special rounds globally
rounds = {
    'round3': [f"match_{i}" for i in range(20, 29)],
    'round4': [f"match_{i}" for i in range(29, 38)],
    'round5': [f"match_{i}" for i in range(38, 47)],
}

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

@st.cache_data
def load_h2h_schedule():
    # Expects columns: Match, Team1, Team2
    try:
        return pd.read_csv("h2h_schedule.csv")
    except:
        return pd.DataFrame()


def prepare_pick_counts(match_id, ld, live_df):
    """
    Calculates how many active managers picked each player and
    adds it as a 'Picked By' column to the live_df.
    """
    if live_df.empty:
        return live_df

    # 1. Identify active managers (those who locked in a Captain)
    active_ld = {m: data for m, data in ld.items() if data['c'] != "-"}

    # 2. Count occurrences of each player
    pick_counts = {}
    for mgr_data in active_ld.values():
        for player in mgr_data['p']:
            pick_counts[player] = pick_counts.get(player, 0) + 1

    # 3. Map the counts to the live_df
    # We use .get(x, 0) to handle players who are playing but picked by 0 managers
    live_df['Picked By'] = live_df['Player'].map(lambda x: pick_counts.get(x, 0))
    live_df['New Points'] = live_df.apply(
        lambda row: (row['Total Points'] * 10 / row['Picked By']) if row['Picked By'] > 0 else row['Total Points'],
        axis=1
    )
    live_df.rename(columns = {'Total Points': 'Scored Points', 'New Points': 'Total Points'}, inplace = True)
    return live_df