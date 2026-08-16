"""Tests for the lineup recommendation logic."""

from fantasy_league.analysis import (
    build_player_rows,
    projection_for,
    recommend,
    required_starting_slots,
)

ROSTER_POSITIONS = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "SUPER_FLEX", "BN", "BN"]


def make_players() -> dict:
    return {
        "qb1": {"full_name": "QB One", "position": "QB", "team": "SEA"},
        "qb2": {"full_name": "QB Two", "position": "QB", "team": "NYG"},
        "rb1": {"full_name": "RB One", "position": "RB", "team": "CHI"},
        "rb2": {"full_name": "RB Two", "position": "RB", "team": "BUF"},
        "rb3": {"full_name": "RB Three", "position": "RB", "team": "NO"},
        "wr1": {"full_name": "WR One", "position": "WR", "team": "IND"},
        "wr2": {"full_name": "WR Two", "position": "WR", "team": "DAL"},
        "wr3": {"full_name": "WR Three", "position": "WR", "team": "MIN"},
        "te1": {"full_name": "TE One", "position": "TE", "team": "KC"},
        "te2": {"full_name": "TE Two", "position": "TE", "team": "CAR"},
    }


def make_combined() -> dict:
    proj = {
        pid: {"stats": {"pts_half_ppr": val}}
        for pid, val in {
            "qb1": 20.0,
            "qb2": 15.0,
            "rb1": 16.0,
            "rb2": 14.0,
            "rb3": 10.0,
            "wr1": 18.0,
            "wr2": 12.0,
            "wr3": 11.0,
            "te1": 9.0,
            "te2": 7.0,
        }.items()
    }
    return {"projections": proj}


def test_required_starting_slots():
    required, flex, sf = required_starting_slots(ROSTER_POSITIONS)
    assert required == {"QB": 1, "RB": 2, "WR": 3, "TE": 1}
    assert flex == 1
    assert sf == 1


def test_recommend_fills_all_slots():
    combined = make_combined()
    rows = build_player_rows(list(make_players()), set(), make_players(), combined, {}, {})
    rec = recommend(rows, ROSTER_POSITIONS)
    assert len(rec) == 9  # QB, 2RB, 3WR, TE, FLEX, SUPER_FLEX
    slots = [s for s, _, _ in rec]
    assert slots.count("QB") == 1
    assert slots.count("RB") == 2
    assert slots.count("WR") == 3
    assert slots.count("TE") == 1
    assert slots.count("FLEX") == 1
    assert slots.count("SUPER_FLEX") == 1


def test_recommend_prioritizes_projection():
    combined = make_combined()
    players = make_players()
    rows = build_player_rows(list(players), set(), players, combined, {}, {})
    rec = recommend(rows, ROSTER_POSITIONS)
    chosen_qb = next(r["pid"] for s, r, _ in rec if s == "QB")
    chosen_sf = next(r["pid"] for s, r, _ in rec if s == "SUPER_FLEX")
    assert chosen_qb == "qb1"
    assert chosen_sf == "qb2"
    # Top WR should be wr1 (18.0)
    wr_starters = [r["pid"] for s, r, _ in rec if s == "WR"]
    assert "wr1" in wr_starters
    # Flex gets a strong remaining RB/WR/TE
    flex_pid = next(r["pid"] for s, r, _ in rec if s == "FLEX")
    assert flex_pid in {"rb1", "wr2", "wr3", "te1", "te2", "rb3"}
    assert rows[0]["blended"] > rows[1]["blended"]


def test_projection_for_missing_player():
    assert projection_for("nobody", make_combined()) is None


def test_build_player_rows_handles_missing_projection():
    combined = {"projections": {}}
    players = make_players()
    rows = build_player_rows(["qb1"], set(), players, combined, {}, {})
    assert rows[0]["proj"] is None
    assert rows[0]["blended"] is None


def test_recommend_runs_without_projections():
    combined = {"projections": {}}
    players = make_players()
    rows = build_player_rows(list(players), set(), players, combined, {}, {})
    rec = recommend(rows, ROSTER_POSITIONS)
    # Without scores nothing is chosen unless everyone has None -> still fills by position
    assert len(rec) > 0
