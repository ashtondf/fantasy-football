"""Shared runtime paths for the fantasy_league package.

All cached/generated data lives under the repository's ``data/`` directory
(created on demand). Override with the ``FANTASY_DATA_DIR`` environment
variable if you want to store it elsewhere.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = Path(os.environ.get("FANTASY_DATA_DIR", REPO_ROOT / "data"))

COMBINED_FILE = DATA_DIR / "sleeper_league_combined.json"
PLAYERS_CACHE = DATA_DIR / "players_nfl.json"
NFLVERSE_CACHE_DIR = DATA_DIR / "nflverse_cache"
VS_TEAM_FILE = DATA_DIR / "vs_team.json"


def schedule_cache_file(season: int) -> Path:
    return DATA_DIR / f"schedule_{season}.json"
