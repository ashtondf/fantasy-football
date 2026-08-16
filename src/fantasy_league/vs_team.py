import json
from typing import Any

from fantasy_league.paths import DATA_DIR, NFLVERSE_CACHE_DIR, VS_TEAM_FILE, schedule_cache_file

SEASONS = [2023, 2024, 2025]


def _configure() -> None:
    from nflreadpy.config import update_config

    update_config(
        cache_mode="filesystem",
        cache_dir=NFLVERSE_CACHE_DIR,
        cache_duration=3600 * 24 * 7,
        verbose=False,
    )


def gsis_to_sleeper_map() -> dict[str, str]:
    _configure()
    import nflreadpy as nfl
    import polars as pl

    ids = nfl.load_ff_playerids()
    df = (
        ids.filter(pl.col("gsis_id").is_not_null() & pl.col("sleeper_id").is_not_null())
        .select(["gsis_id", "sleeper_id"])
        .unique()
    )
    return {r["gsis_id"]: r["sleeper_id"] for r in df.to_dicts()}


def build_vs_team(seasons: list[int] | None = None) -> dict[str, Any]:
    seasons = seasons or SEASONS
    _configure()
    import nflreadpy as nfl
    import polars as pl

    stats = nfl.load_player_stats(seasons, summary_level="week")
    grouped = (
        stats.filter(pl.col("season_type") == "REG")
        .group_by(["player_id", "opponent_team"])
        .agg(
            [
                pl.col("fantasy_points").count().alias("games"),
                pl.col("fantasy_points").sum().alias("total"),
                pl.col("fantasy_points").mean().alias("avg"),
            ]
        )
    )
    id_map = gsis_to_sleeper_map()
    vs: dict[str, Any] = {}
    for row in grouped.to_dicts():
        sleeper_id = id_map.get(row["player_id"])
        opp = row["opponent_team"]
        if not sleeper_id or not opp:
            continue
        vs.setdefault(sleeper_id, {})[opp] = {
            "games": int(row["games"]),
            "total": round(float(row["total"]), 2),
            "avg": round(float(row["avg"]), 2),
        }
    VS_TEAM_FILE.parent.mkdir(parents=True, exist_ok=True)
    VS_TEAM_FILE.write_text(json.dumps(vs), encoding="utf-8")
    return vs


def load_vs_team() -> dict[str, Any]:
    if not VS_TEAM_FILE.exists():
        return {}
    return json.loads(VS_TEAM_FILE.read_text(encoding="utf-8"))


def load_season_opponents(season: int) -> dict[int, dict[str, str]]:
    cache_file = schedule_cache_file(season)
    if cache_file.exists():
        return {int(k): v for k, v in json.loads(cache_file.read_text(encoding="utf-8")).items()}
    _configure()

    import nflreadpy as nfl

    try:
        sched = nfl.load_schedules(season)
    except Exception:
        return {}
    out: dict[int, dict[str, str]] = {}
    if sched is None or len(sched) == 0:
        return out
    for row in sched.to_dicts():
        w = row.get("week")
        home, away = row.get("home_team"), row.get("away_team")
        if w is None:
            continue
        m = out.setdefault(int(w), {})
        if home:
            m[home] = away
        if away:
            m[away] = home
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(out), encoding="utf-8")
    return out


def load_opponents_by_week(season: int, week: int) -> dict[str, str]:
    return load_season_opponents(season).get(int(week), {})
