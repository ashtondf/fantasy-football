import requests
import pandas as pd
from typing import List, Dict, Any

BASE = "https://api.sleeper.app/v1"

def get_league(league_id: str) -> Dict[str, Any]:
    url = f"{BASE}/league/{league_id}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

def get_rosters(league_id: str) -> List[Dict[str, Any]]:
    url = f"{BASE}/league/{league_id}/rosters"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

def get_users(league_id: str) -> List[Dict[str, Any]]:
    url = f"{BASE}/league/{league_id}/users"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

def get_player_news(limit: int = 25) -> List[Dict[str, Any]]:
    # Example global endpoint for player news
    url = f"{BASE}/players/nfl/news"
    params = {"limit": limit}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def combine_league_data(league_id: str) -> Dict[str, Any]:
    league = get_league(league_id)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    news = get_player_news(limit=50)

    # Build quick lookup for owners by user_id
    owners_by_id = {u["user_id"]: u for u in users}

    # Attach owner info to each roster
    for roster in rosters:
        owner_id = roster.get("owner_id")
        roster["owner"] = owners_by_id.get(owner_id, {})

    combined = {
        "league": league,
        "rosters": rosters,
        "users": users,
        "player_news_sample": news[:10],  # keep sample small
    }
    return combined

def rosters_to_dataframe(rosters: List[Dict[str, Any]]) -> pd.DataFrame:
    # Flatten roster info for a simple table
    rows = []
    for r in rosters:
        rows.append({
            "roster_id": r.get("roster_id"),
            "owner_id": r.get("owner_id"),
            "owner_display_name": r.get("owner", {}).get("display_name"),
            "players_count": len(r.get("players", [])),
            "settings": r.get("settings"),
        })
    return pd.DataFrame(rows)

def main():
    # Replace with a real public league ID you have access to or a sample league id
    league_id = "1359362301764861952"  # <-- change this to a real league ID

    try:
        combined = combine_league_data(league_id)
    except requests.HTTPError as e:
        print("HTTP error:", e)
        return
    except requests.RequestException as e:
        print("Request failed:", e)
        return

    # Print summary
    print("League name:", combined["league"].get("name"))
    print("Total rosters:", len(combined["rosters"]))
    print("Total users:", len(combined["users"]))
    print("Sample player news items:", len(combined["player_news_sample"]))

    # Optional: show rosters as a DataFrame
    try:
        df = rosters_to_dataframe(combined["rosters"])
        print("\nRosters table:")
        print(df.head(10).to_string(index=False))
    except Exception as e:
        print("Could not build DataFrame:", e)

    # Save combined JSON to file for later use
    import json
    with open("sleeper_league_combined.json", "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)
    print("\nSaved combined data to sleeper_league_combined.json")

if __name__ == "__main__":
    main()
