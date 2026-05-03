import streamlit as st
import pandas as pd
import hashlib
import re
from datetime import datetime

pd.set_option('future.no_silent_downcasting', True)

# Define the special rounds globally
rounds = {
    'round1': [f"match_{i}" for i in range(1, 10)],
    'round2': [f"match_{i}" for i in range(10, 20)],
    'round3': [f"match_{i}" for i in range(20, 29)],
    'round4': [f"match_{i}" for i in range(29, 38)],
    'round5': [f"match_{i}" for i in range(38, 47)],
    'round6': [f"match_{i}" for i in range(47, 56)],
}

def get_three_part_name_map(player_list):
    """
    Creates a mapping where variations of 3-part names (e.g., First Last,
    Middle Last, First Middle) point back to the full 3-part name.
    """
    name_map = {}
    for full_name in player_list:
        parts = full_name.split()
        if len(parts) == 3:
            first, middle, last = parts[0], parts[1], parts[2]
            # Common Cricbuzz variations for 3-part names
            variations = [
                f"{first} {last}",   # First Last
                f"{middle} {last}",  # Middle Last
                f"{first} {middle}"  # First Middle
            ]
            for var in variations:
                name_map[var] = full_name
    return name_map

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


def prepare_pick_counts(ld, live_df):
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

def prepare_ranks(match_id, ld, live_df):
    # --- STEP 1: Get Lineups from Session State or Scraper ---

    # Check if lineups exist and are for the current match_id
    if (st.session_state.get("lineup_match") != match_id) or ("lineups" not in st.session_state):
        st.session_state.lineups = scraper.get_lineups(match_info['URL'])
        st.session_state.lineup_match = match_id

    lineups = st.session_state.lineups  # This is your status_map {Player: "🟢", etc.}

    # --- STEP 2: Filter for Playing XI only ---
    # In your scraper.py, status "🟢" represents "Playing XI"

    playing_xi_players = [
        player for player, status in lineups.items()
        if status == "🟢"
    ]

    # 1. Extract all players from all managers who have locked in a team
    # We filter for info['c'] != "-" to ensure we only count active submissions
    all_picked_players = set().union(*(info['p'] for info in ld.values() if info['c'] != "-"))

    # 1. Create a combined unique list of all relevant players
    all_players = set(live_df['Player']).union(set(playing_xi_players)).union(all_picked_players)

    # 2. Create a base dataframe with these names
    expanded_df = pd.DataFrame({'Player': list(all_players)})

    # 3. Merge with the original live_df to bring in existing stats
    # Players not in live_df will have NaN values initially
    expanded_df = pd.merge(expanded_df, live_df, on='Player', how='left')

    # 4. Fill NaNs with 0 for all statistical columns
    # Identify numeric columns (Batting, Bowling, Fielding, etc.)
    numeric_cols = expanded_df.select_dtypes(include=['number']).columns
    expanded_df[numeric_cols] = expanded_df[numeric_cols].fillna(0)

    # 5. Add the 'Played' Column
    # A player is considered to have "Played" if they were in the official Playing XI (🟢)
    # or if they were an Impact Sub who actually took the field (found in live_df)
    def check_if_played(player_name):
        if player_name in playing_xi_players:
            return True
        # If they aren't in Playing XI, check if they have any recorded stats in live_df
        # (This covers Impact Subs who actually batted, bowled, or caught)
        if player_name in live_df['Player'].values:
            return True
        return False

    expanded_df['Played'] = expanded_df['Player'].apply(check_if_played)

    # 6. Final Polish: Ensure Opener column exists (default False for new players)
    if 'Opener' in expanded_df.columns:
        expanded_df['Opener'] = expanded_df['Opener'].fillna(False)

    # Get the ranks
    expanded_df['Rank'] = expanded_df['Total Points'].rank(method='dense', ascending=False)

    # 2. Update Total Points for DNP players (Played == False) who currently have 0
    # This assigns them the largest rank value, making them contribute to the manager's sum.
    expanded_df['Actual Points'] = expanded_df['Batting'] + expanded_df['Bowling'] + expanded_df['Fielding'] + expanded_df['POTM']

    expanded_df.loc[
        (expanded_df['Actual Points'] == 0) & (expanded_df['Played'] == False),
        'Rank'
    ] = 0

    expanded_df.loc[
        (expanded_df['Actual Points'] == 0) & (expanded_df['Played'] == False),
        'Total Points'
    ] = expanded_df['Actual Points'].max() + 1

    expanded_df.rename(columns={'Total Points': 'Scored Points', 'Rank': 'Total Points'}, inplace=True)
    expanded_df.drop(columns = ['Actual Points'], inplace = True)

    return expanded_df