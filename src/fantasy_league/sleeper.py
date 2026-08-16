"""Client and aggregation layer for the Sleeper API."""

import argparse
import json
from typing import Any

import pandas as pd
import requests

from fantasy_league.paths import COMBINED_FILE

BASE = "https://api.sleeper.app/v1"
DEFAULT_LEAGUE_ID = "1359362301764861952"
PROJ_POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")


def get_league(league_id: str) -> dict[str, Any]:
    url = f"{BASE}/league/{league_id}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def get_rosters(league_id: str) -> list[dict[str, Any]]:
    url = f"{BASE}/league/{league_id}/rosters"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def get_users(league_id: str) -> list[dict[str, Any]]:
    url = f"{BASE}/league/{league_id}/users"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def get_trending_players(trend_type: str = "add", limit: int = 25) -> list[dict[str, Any]]:
    url = f"{BASE}/players/nfl/trending/{trend_type}"
    params = {"limit": limit}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def get_nfl_state() -> dict[str, Any]:
    r = requests.get(f"{BASE}/state/nfl", timeout=10)
    r.raise_for_status()
    return r.json()


def get_matchups(league_id: str, week: int) -> list[dict[str, Any]]:
    url = f"{BASE}/league/{league_id}/matchups/{week}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def get_transactions(league_id: str, week: int) -> list[dict[str, Any]]:
    url = f"{BASE}/league/{league_id}/transactions/{week}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def get_traded_picks(league_id: str) -> list[dict[str, Any]]:
    url = f"{BASE}/league/{league_id}/traded_picks"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def get_drafts(league_id: str) -> list[dict[str, Any]]:
    url = f"{BASE}/league/{league_id}/drafts"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def get_draft_picks(draft_id: str) -> list[dict[str, Any]]:
    url = f"{BASE}/draft/{draft_id}/picks"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def get_bracket(league_id: str, kind: str = "winners_bracket") -> list[dict[str, Any]]:
    url = f"{BASE}/league/{league_id}/{kind}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def get_projections(season: str, week: int, positions=PROJ_POSITIONS) -> dict[str, dict[str, Any]]:
    proj: dict[str, dict[str, Any]] = {}
    for pos in positions:
        url = f"https://api.sleeper.com/projections/nfl/{season}/{week}/"
        params = {"season_type": "regular", "position[]": pos}
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


def _default_analysis_week(state: dict[str, Any], league: dict[str, Any]) -> int:
    start_week = league.get("settings", {}).get("start_week", 1)
    if state.get("season_type") == "regular":
        return state.get("week", start_week)
    return start_week


def combine_league_data(league_id: str, analysis_week: int | None = None) -> dict[str, Any]:
    league = get_league(league_id)
    rosters = get_rosters(league_id)
    users = get_users(league_id)
    trending = get_trending_players(limit=50)
    state = get_nfl_state()

    if analysis_week is None:
        analysis_week = _default_analysis_week(state, league)

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

    return {
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


def rosters_to_dataframe(rosters: list[dict[str, Any]]) -> pd.DataFrame:
    """Flatten roster info for a simple table."""
    rows = []
    for r in rosters:
        rows.append(
            {
                "roster_id": r.get("roster_id"),
                "owner_id": r.get("owner_id"),
                "owner_display_name": r.get("owner", {}).get("display_name"),
                "players_count": len(r.get("players", [])),
                "settings": r.get("settings"),
            }
        )
    return pd.DataFrame(rows)


def save_combined(combined: dict[str, Any]) -> None:
    COMBINED_FILE.parent.mkdir(parents=True, exist_ok=True)
    COMBINED_FILE.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sleeper-pull",
        description="Fetch and combine Sleeper league data into data/sleeper_league_combined.json",
    )
    parser.add_argument("--league", default=DEFAULT_LEAGUE_ID, help="Sleeper league ID")
    parser.add_argument("--week", type=int, default=None, help="Analysis week (defaults to the current league week)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        combined = combine_league_data(args.league, args.week)
    except requests.HTTPError as e:
        print("HTTP error:", e)
        return 1
    except requests.RequestException as e:
        print("Request failed:", e)
        return 1

    print("League name:", combined["league"].get("name"))
    print("Analysis week:", combined["analysis_week"], "| projections:", len(combined["projections"]))
    print("Rosters:", len(combined["rosters"]), "| Users:", len(combined["users"]))
    print("Transactions:", len(combined["transactions"]), "| traded picks:", len(combined["traded_picks"]))

    save_combined(combined)
    print(f"\nSaved combined data to {COMBINED_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
