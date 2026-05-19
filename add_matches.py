# Run this script only once to expand the match list in the database
import database as db

def expand_match_teams_pool():
    # 1. Fetch all unique active managers currently in your system
    try:
        # Pulling existing usernames directly from your user base
        users_res = db.supabase.table("users").select("username").execute()
        managers = [row['username'] for row in users_res.data]
    except Exception as e:
        print(f"Error fetching managers: {e}")
        return

    if not managers:
        print("No managers found to expand matches for.")
        return

    print(f"Found {len(managers)} managers. Injecting placeholders for matches 71 to 80...")

    new_rows = []
    # 2. Generate placeholder data structures for matches 71 through 80
    for match_num in range(71, 81):
        match_id = f"match_{match_num}"
        for mgr in managers:
            new_rows.append({
                "username": mgr,
                "match_id": match_id,
                "captain": "-",
                "vice_captain": "-",
                "banned": "-"
            })

    # 3. Bulk insert rows safely into Supabase
    try:
        # .upsert() updates existing records and inserts new ones safely
        db.supabase.table("match_teams").upsert(
            new_rows,
            on_conflict="username,match_id"  # Explicitly tell it where to check for duplicates
        ).execute()
        print(f"🎉 Success! Safely synchronized placeholder slots across matches.")
    except Exception as e:
        print(f"Database upsert failed: {e}")

if __name__ == "__main__":
    expand_match_teams_pool()