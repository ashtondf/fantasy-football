"""Tests for the Sleeper aggregation helpers (no network calls)."""

from fantasy_league import sleeper


def test_default_analysis_week_regular_season():
    state = {"season_type": "regular", "week": 5}
    league = {"settings": {"start_week": 1}}
    assert sleeper._default_analysis_week(state, league) == 5


def test_default_analysis_week_falls_back_to_start_week():
    state = {"season_type": "pre", "week": 1}
    league = {"settings": {"start_week": 1}}
    assert sleeper._default_analysis_week(state, league) == 1


def test_default_analysis_week_missing_week_uses_start_week():
    state = {"season_type": "regular"}
    league = {"settings": {"start_week": 3}}
    assert sleeper._default_analysis_week(state, league) == 3


def test_save_combined_roundtrips(tmp_path, monkeypatch):
    monkeypatch.setattr(sleeper, "COMBINED_FILE", tmp_path / "combined.json")
    sleeper.save_combined({"hello": "world"})
    import json

    assert json.loads((tmp_path / "combined.json").read_text()) == {"hello": "world"}
