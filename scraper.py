import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime
import streamlit as st
from utils import clean_name

SCORING = {
    'run': 1, 'four': 2, 'six': 3, 'duck': -10,
    'wicket': 25, 'maiden': 15,
    'catch': 15, 'stumping': 10, 'runout': 10
}

def parse_fielding(dismissal_text):
    fielders = []
    text, norm_text = dismissal_text.strip(), dismissal_text.strip().lower()
    if "run out" in norm_text:
        match = re.search(r'\((.*?)\)', text)
        if match:
            for n in match.group(1).split('/'): fielders.append({'name': clean_name(n), 'type': 'runout'})
    elif norm_text.startswith("c and b "):
        fielders.append({'name': clean_name(text[8:]), 'type': 'catch'})
    elif norm_text.startswith("st "):
        fielders.append({'name': clean_name(text[3:].split(" b ")[0]), 'type': 'stumping'})
    elif norm_text.startswith("c "):
        fielders.append({'name': clean_name(text[2:].split(" b ")[0].strip()), 'type': 'catch'})
    return fielders

def get_live_stats(url):
    try:
        st.session_state.last_refresh = datetime.now().strftime("%H:%M:%S")
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')

        # New: List to store openers
        openers = []

        # Batting Tables
        bat_tables = soup.find_all('div', id=re.compile('innings-\\d'))
        for table in bat_tables:
            # Find all batting rows in this innings
            rows = table.find_all('div', class_='scorecard-bat-grid')
            # The first two rows with actual player names are the openers
            count = 0
            for row in rows:
                name_link = row.find('a', class_='text-cbTextLink')
                if name_link and count < 2:
                    name = clean_name(name_link.text)
                    if name not in openers:
                        openers.append(name)
                    count += 1

        unique_batting, unique_bowling, fielding_pts, processed = {}, {}, {}, set()

        for row in soup.find_all('div', class_='scorecard-bat-grid'):
            cols = row.find_all('div', recursive=False)
            if not cols or "Batter" in cols[0].text: continue
            try:
                name = clean_name(row.find('a', class_='text-cbTextLink').text.strip())
                d_div = cols[0].find('div', class_='text-cbTxtSec')
                if d_div:
                    raw_d_text = d_div.text.strip()
                    d_text_lower = raw_d_text.lower()  # Use this for the Duck check

                    if f"{name}_{d_text_lower}" not in processed:
                        for f in parse_fielding(raw_d_text):
                            f_name = f['name']
                            fielding_pts[f_name] = fielding_pts.get(f_name, 0) + SCORING.get(f['type'], 0)
                        processed.add(f"{name}_{d_text_lower}")
                else:
                    d_text_lower = "not out"

                # Now use the lower version for the duck check
                is_not_out = any(
                    phrase in d_text_lower for phrase in ["batting", "not out", "retired hurt", "absent out", "absent", "hurt"])
                # Note: "retired out" DOES count as a dismissal/duck
                if name not in unique_batting:
                    runs, balls, fours, sixes = int(cols[1].text), int(cols[2].text), int(cols[3].text), int(cols[4].text)
                    b_pts = (runs * SCORING['run']) + (fours * SCORING['four']) + (sixes * SCORING['six'])
                    b_pts += (runs // 25) * 10        # Milestone: +10 every 25 runs
                    b_pts += (runs - balls)           # Strike-rate: Runs - Balls
                    if runs == 0 and not is_not_out:
                        b_pts += SCORING['duck']
                    unique_batting[name] = {"BatPts": b_pts}
            except: continue

        for row in soup.find_all('div', class_='scorecard-bowl-grid'):
            try:
                name = clean_name(row.find('a', class_='text-cbTextLink').text.strip())
                if name in unique_bowling: continue
                cols = row.find_all('div', recursive=False)
                ov_str = cols[0].text.split('.')
                total_balls = (int(ov_str[0]) * 6) + (int(ov_str[1]) if len(ov_str) > 1 else 0)
                m, r_conc, w = int(cols[1].text), int(cols[2].text), int(cols[3].text)
                w_pts = (w * SCORING['wicket']) + (m * SCORING['maiden'])
                w_pts += (total_balls * 2) - r_conc  # Economy: (Balls x 2) - Runs
                if w >= 7: w_pts += 100           # 7-Wicket Haul
                elif w >= 5: w_pts += 50         # 5-Wicket Haul
                elif w >= 3: w_pts += 25         # 3-Wicket Haul
                unique_bowling[name] = {"BowlPts": w_pts}
            except: continue

        all_p = set(list(unique_batting.keys()) + list(unique_bowling.keys()) + list(fielding_pts.keys()))
        potm_name = get_potm(url)
        merged = []
        for p in all_p:
            bat = unique_batting.get(p, {'BatPts': 0})['BatPts']
            bowl = unique_bowling.get(p, {'BowlPts': 0})['BowlPts']
            fld = fielding_pts.get(p, 0)

            total = bat + bowl + fld

            # 3. Add POTM Bonus
            potm_bonus = 0
            if potm_name and p.lower() == potm_name.lower():
                potm_bonus = 25
                total += potm_bonus

            merged.append({
                "Player": p,
                "Batting": bat,
                "Bowling": bowl,
                "Fielding": fld,
                "POTM": potm_bonus,
                "Total Points": total,
                "Opener": p in openers
            })
        return pd.DataFrame(merged)
    except: return pd.DataFrame()


def get_potm(scorecard_url):
    """
    Swaps URL to /live-cricket-scores/ and looks for the POTM name.
    Returns the name as a string or None if not found/match not over.
    """
    try:
        # Generate the 'scores' URL from the 'scorecard' URL
        scores_url = scorecard_url.replace("/live-cricket-scorecard/", "/live-cricket-scores/")
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(scores_url, headers=headers, timeout=5)
        soup = BeautifulSoup(r.text, 'html.parser')

        # Look for the DIV containing "PLAYER OF THE MATCH"
        # Based on your HTML: it's inside a div with text "PLAYER OF THE MATCH"
        potm_label = soup.find("div", text=re.compile("PLAYER OF THE MATCH", re.IGNORECASE))
        if potm_label:
            # The name is usually in the next sibling span or a link nearby
            # Based on your snippet: <span>Jacob Duffy</span> is inside an <a> tag
            potm_container = potm_label.find_next("span")
            if potm_container:
                return clean_name(potm_container.text)
    except:
        pass  # "Be chill" - if the page isn't ready or layout is different, return None
    return None


def get_lineups(scorecard_url):
    """
    Scrapes the squads page to determine who is playing, sub, or benched.
    Green = Playing XI, Purple = Subs, Red = Bench.
    """
    try:
        # Convert scorecard URL to squads URL
        squad_url = scorecard_url.replace("/live-cricket-scorecard/", "/cricket-match-squads/")
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(squad_url, headers=headers, timeout=5)
        soup = BeautifulSoup(r.text, 'html.parser')

        status_map = {}
        # Find the main sections (Playing XI, Substitutes, Bench)
        # Cricbuzz usually groups these inside divs with <h1> headers
        sections = soup.find_all("div", class_="pb-5")

        for section in sections:
            header = section.find("h1")
            if not header: continue

            label = header.get_text().lower()
            # Determine color/status based on header text
            if "playing xi" in label:
                status = "🟢"  # Green
            elif "substitutes" in label:
                status = "🟣"  # Purple
            elif "bench" in label:
                status = "🔴"  # Red
            else:
                continue

            # Extract player names from this section
            # Names are usually inside <span> tags within <a> links
            player_links = section.find_all("a", href=re.compile(r'/profiles/'))
            for link in player_links:
                name_span = None
                all_spans = link.find_all("span")
                for s in all_spans:
                    if s.get_text(strip=True):  # Checks if the span isn't empty
                        name_span = s
                        break
                if name_span:
                    p_name = clean_name(name_span.get_text())
                    status_map[p_name] = status

        return status_map
    except:
        return {}