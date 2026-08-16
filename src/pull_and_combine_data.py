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

def get_trending_players(trend_type: str = "add", limit: int = 25) -> List[Dict[str, Any]]:
    url = f"{BASE}/players/nfl/trending/{trend_type}"
    params = {"limit": limit}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def get_nfl_state() -> Dict[str, Any]:
    r = requests.get(f"{BASE}/state/nfl", timeout=10)
    r.raise_for_status()
    return r.json()

def get_matchups(league_id: str, week: int) -> List[Dict[str, Any]]:
    url = f"{BASE}/league/{league_id}/matchups/{week}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

def get_transactions(league_id: str, week: int) -> List[Dict[str, Any]]:
    url = f"{BASE}/league/{league_id}/transactions/{week}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

def get_traded_picks(league_id: str) -> List[Dict[str, Any]]:
    url = f"{BASE}/league/{league_id}/traded_picks"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

def get_drafts(league_id: str) -> List[Dict[str, Any]]:
    url = f"{BASE}/league/{league_id}/drafts"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

def get_draft_picks(draft_id: str) -> List[Dict[str, Any]]:
    url = f"{BASE}/draft/{draft_id}/picks"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

def get_bracket(league_id: str, kind: str = "winners_bracket") -> List[Dict[str, Any]]:
    url = f"{BASE}/league/{league_id}/{kind}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

PROJ_POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")

def get_projections(season: str, week: int, positions=PROJ_POSITIONS) -> Dict[str, Dict[str, Any]]:
    proj: Dict[str, Dict[str, Any]] = {}
    for pos in positions:
        url = "https://api.sleeper.com/projections/nfl/{}/{}/".format(season, week)
        params = {"season_type": "regular", f"position[]": pos}
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        for p in r.json():
            pid = p.get("player_id")
            if pid not in proj:
                proj[pid] = {
                    "player_id": pid,
                    "position": pos,
                    "team": (p.get("player") or {}).get("team"),
                    "stats": p.get("stats", {}) or {},
                }
    return proj

def combine_league_data(league_id: str, analysis_week: int | None = None) -> Dict[str, Any]:
    league = get_league(league_id)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    trending = get_trending_players(limit=50)
    state = get_nfl_state()

    if analysis_week is None:
        start_week = league.get("settings", {}).get("start_week", 1)
        analysis_week = state.get("week", start_week) if state.get("season_type") == "regular" else start_week

    matchups = get_matchups(league_id, analysis_week)
    projections = get_projections(league["season"], analysis_week)
    drops = get_trending_players("drop", limit=25)
    traded_picks = get_traded_picks(league_id)
    transactions = get_transactions(league_id, analysis_week)
    drafts = get_drafts(league_id)
    draft_picks = get_draft_picks(drafts[0]["draft_id"]) if drafts else []
    winners_bracket = get_bracket(league_id, "winners_bracket")
    losers_bracket = get_bracket(league_id, "losers_bracket")

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
        "trending_players_add_sample": trending[:10],  # keep sample small
        "trending_players_drop_sample": drops[:10],
        "nfl_state": state,
        "analysis_week": analysis_week,
        "analysis_season": league.get("season"),
        "matchups": matchups,
        "projections": projections,
        "roster_positions": league.get("roster_positions", []),
        "transactions": transactions,
        "traded_picks": traded_picks,
        "drafts": drafts,
        "draft_picks": draft_picks,
        "winners_bracket": winners_bracket,
        "losers_bracket": losers_bracket,
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
    print("Analysis week:", combined["analysis_week"], "| projections:", len(combined["projections"]))
    print("Transactions:", len(combined["transactions"]), "| traded picks:", len(combined["traded_picks"]))
    print("Sample trending players (adds):", len(combined["trending_players_add_sample"]),
          "| (drops):", len(combined["trending_players_drop_sample"]))

    # Optional: show rosters as a DataFrame
    try:
        df = rosters_to_dataframe(combined["rosters"])
        print("\nRosters table:")
        print(df.head(10).to_string(index=False))
    except Exception as e:
        print("Could not build DataFrame:", e)

    # Save combined JSON to file for later use
    import json
    import pathlib
    out_path = pathlib.Path(__file__).resolve().parent.parent / "data" / "sleeper_league_combined.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)
    print(f"\nSaved combined data to {out_path}")

if __name__ == "__main__":
    main()
