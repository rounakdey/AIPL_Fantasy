import streamlit as st
import pandas as pd
import hashlib
import re

def clean_name(name):
    return re.sub(r'\(.*?\)', '', name).strip()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@st.cache_data
def load_schedule():
    df = pd.read_csv("match_schedule.csv")
    df['display'] = df.apply(
        lambda x: f"Match {x.name + 1}: {x['Team 1']} vs {x['Team 2']}, {x['Date']}, {x['Start Time']}", axis=1)
    return df

@st.cache_data
def load_squads():
    # Ensure squads.csv has: Player Name, Role, Team, Category
    return pd.read_csv("squads.csv")