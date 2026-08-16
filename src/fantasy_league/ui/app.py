import json
from collections import Counter
from typing import Any

import pandas as pd
import requests
import streamlit as st

from fantasy_league import sleeper, vs_team
from fantasy_league.analysis import (
    WAIVER_POSITIONS,
    build_player_rows,
    player_name,
    projection_for,
    recommend,
)
from fantasy_league.paths import COMBINED_FILE, PLAYERS_CACHE, VS_TEAM_FILE

BASE = "https://api.sleeper.app/v1"


def load_combined() -> dict[str, Any]:
    if not COMBINED_FILE.exists():
        return {}
    with open(COMBINED_FILE, encoding="utf-8") as f:
        return json.load(f)


def fetch_combined(league_id: str, week: int | None = None) -> dict[str, Any]:
    combined = sleeper.combine_league_data(league_id, analysis_week=week)
    COMBINED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(COMBINED_FILE, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)
    return combined


def fetch_player_map() -> dict[str, Any]:
    if PLAYERS_CACHE.exists():
        with open(PLAYERS_CACHE, encoding="utf-8") as f:
            return json.load(f)
    st.info("Downloading Sleeper player data for the first time (~5 MB)...")
    r = requests.get(f"{BASE}/players/nfl", timeout=30)
    r.raise_for_status()
    players = r.json()
    PLAYERS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(PLAYERS_CACHE, "w", encoding="utf-8") as f:
        json.dump(players, f)
    return players


@st.cache_data(show_spinner=False)
def get_player_map() -> dict[str, Any]:
    return fetch_player_map()


def player_label(pid: str, players: dict[str, Any]) -> str:
    p = players.get(pid, {})
    name = p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or pid
    pos = p.get("position", "?")
    team = p.get("team", "FA")
    return f"{name} ({pos}, {team})"


def roster_team_name(roster_id: int, combined: dict[str, Any]) -> str:
    rosters = {r["roster_id"]: r for r in combined.get("rosters", [])}
    users = {u["user_id"]: u for u in combined.get("users", [])}
    r = rosters.get(roster_id)
    if not r:
        return f"Roster {roster_id}"
    u = users.get(r.get("owner_id"))
    return (u.get("metadata") or {}).get("team_name") or (u or {}).get("display_name") or f"Roster {roster_id}"


def user_avatar(user: dict[str, Any], thumb: bool = True) -> str | None:
    av = (user or {}).get("avatar")
    if not av:
        return None
    return f"https://sleepercdn.com/avatars/{'thumbs/' if thumb else ''}{av}"


def _diff_text(my_total: float, opp_total: float) -> str:
    if opp_total > my_total:
        return f"behind by {opp_total - my_total:.1f}"
    return f"ahead by {my_total - opp_total:.1f}"


def render_my_team(combined: dict[str, Any], my_name: str) -> None:
    users = combined.get("users", [])
    my_user = next((u for u in users if u.get("display_name") == my_name), None)
    if not my_user:
        st.warning(f"Could not find a user with display name '{my_name}'. Set it in the sidebar.")
        return
    rosters = combined.get("rosters", [])
    my_roster = next((r for r in rosters if r.get("owner_id") == my_user.get("user_id")), None)
    if not my_roster:
        st.warning("Could not find your roster.")
        return

    my_team_name = (my_user.get("metadata") or {}).get("team_name") or my_user.get("display_name")
    week = combined.get("analysis_week")
    matchups = combined.get("matchups", [])
    my_matchup = next((m for m in matchups if m.get("roster_id") == my_roster.get("roster_id")), None)
    opp_roster = opp_user = opp_matchup = None
    if my_matchup:
        opp_matchup = next(
            (
                m
                for m in matchups
                if m.get("matchup_id") == my_matchup.get("matchup_id")
                and m.get("roster_id") != my_roster.get("roster_id")
            ),
            None,
        )
        if opp_matchup:
            opp_roster = next((r for r in rosters if r.get("roster_id") == opp_matchup.get("roster_id")), None)
            opp_user = next((u for u in users if u.get("user_id") == (opp_roster or {}).get("owner_id")), None)
    opp_team_name = (
        (opp_user.get("metadata") or {}).get("team_name") or opp_user.get("display_name", "Unknown")
        if opp_user
        else "Bye / no matchup"
    )

    hcol_a, hcol_b = st.columns([1, 1])
    with hcol_a:
        av = user_avatar(my_user)
        if av:
            st.image(av, width=64)
        st.markdown(f"### {my_team_name}")
    with hcol_b:
        av = user_avatar(opp_user)
        if av:
            st.image(av, width=64)
        st.markdown(f"### {opp_team_name}")

    players = get_player_map()
    vs = vs_team.load_vs_team()
    season = combined.get("analysis_season")
    opp_map = vs_team.load_opponents_by_week(int(season), int(week)) if season and week is not None else {}

    my_starters = set(my_matchup.get("starters", [])) if my_matchup else set()
    my_rows = build_player_rows(my_roster.get("players", []), my_starters, players, combined, opp_map, vs)
    rec = recommend(my_rows, combined.get("roster_positions", []))
    rec_by_pid = {r["pid"]: slot for slot, r, _ in rec}

    opp_starters = set(opp_matchup.get("starters", [])) if opp_matchup else set()
    opp_rows = (
        build_player_rows((opp_roster or {}).get("players", []), opp_starters, players, combined, {}, vs)
        if opp_roster
        else []
    )
    opp_starter_rows = [r for r in opp_rows if r["starter"]]

    my_proj_total = sum((projection_for(r["pid"], combined) or 0) for _, r, _ in rec)
    opp_proj_total = sum(r["proj"] or 0 for r in opp_starter_rows)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("My Team", my_team_name)
    c2.metric("Opponent", opp_team_name)
    c3.metric("Week", week or "—")
    c4.metric("Projected", f"{my_proj_total:.1f} pts")

    st.markdown(
        f"**Projected total vs opponent:** {my_proj_total:.1f} — {opp_proj_total:.1f} "
        f"({_diff_text(my_proj_total, opp_proj_total)})"
    )

    # Recommended lineup table
    disp = []
    for slot, r, alt in rec:
        vs_txt = f"{r['vs_avg']:.1f} ({r['vs_games']}g)" if r["vs_avg"] is not None else "—"
        disp.append(
            {
                "Slot": slot,
                "Player": r["name"],
                "Pos": r["pos"],
                "Team": r["team"],
                "Opp DEF": r["opp"] or "—",
                "Proj": r["proj"],
                "vs Opp avg": vs_txt,
                "Blended": round(r["blended"], 1) if r["blended"] is not None else None,
                "Currently starting": "Yes" if r["starter"] else "No",
            }
        )
    st.subheader(f"Recommended lineup (Week {week})")
    st.dataframe(pd.DataFrame(disp), hide_index=True, width="stretch")

    # Suggestions
    suggestions = []
    for slot, r, alt in rec:
        if not r["starter"]:
            if r["proj"] is not None:
                reasoning = f"**Start {r['name']} ({r['pos']})** — projected {r['proj']:.1f}"
            else:
                reasoning = f"**Start {r['name']} ({r['pos']})**"
            if r["vs_avg"] is not None:
                reasoning += f", avg {r['vs_avg']:.1f} vs {r['opp']} ({r['vs_games']} games)"
            if alt and alt["blended"] is not None and r["blended"] is not None:
                reasoning += f". Next best: {alt['name']} ({r['blended'] - alt['blended']:.1f} pts better)."
            suggestions.append((reasoning, r, 0))
        elif alt and alt["blended"] is not None and r["blended"] is not None and alt["blended"] > r["blended"] + 0.5:
            suggestion = (
                f"**Consider swapping {alt['name']} ({alt['pos']}) into {slot}** over {r['name']} "
                f"(blended {alt['blended']:.1f} vs {r['blended']:.1f})."
            )
            suggestions.append((suggestion, r, alt["blended"] - r["blended"]))
    for r in my_rows:
        if r["starter"] and r["pid"] not in rec_by_pid:
            suggestions.append((f"**Bench {r['name']} ({r['pos']})** — not in the recommended lineup this week.", r, 0))
    suggestions.sort(key=lambda t: -t[2])

    st.subheader("Start/sit suggestions")
    if suggestions:
        for text, r, _ in suggestions[:8]:
            st.markdown(f"- {text}")
    else:
        st.write("No changes recommended — your current lineup looks optimal.")

    # Roster detail expanders
    with st.expander(f"Opponent: {opp_team_name} — roster"):
        if opp_starter_rows:
            odf = pd.DataFrame(
                [
                    {
                        "Player": r["name"],
                        "Pos": r["pos"],
                        "Team": r["team"],
                        "Proj": r["proj"],
                    }
                    for r in opp_starter_rows
                ]
            )
            st.dataframe(odf, hide_index=True, width="stretch")
        if opp_rows:
            st.write("Bench:")
            bench_lines = []
            for r in opp_rows:
                if r["starter"]:
                    continue
                base = f"{r['name']} ({r['pos']}, {r['team']})"
                bench_lines.append(f"{base} — {r['proj']:.1f}" if r["proj"] is not None else base)
            st.write("\n".join(bench_lines))

    with st.expander("My full roster"):
        for r in sorted(my_rows, key=lambda x: (x["pos"] or "", -(x["blended"] or 0))):
            mark = "**START**" if r["pid"] in rec_by_pid else "bench"
            st.write(
                f"{mark} — {r['name']} ({r['pos']}, {r['team']})"
                + (f" proj {r['proj']:.1f}" if r["proj"] is not None else "")
                + (f" vs {r['opp']} avg {r['vs_avg']:.1f}/{r['vs_games']}g" if r["vs_avg"] is not None else "")
            )


def roster_record(r: dict[str, Any], combined: dict[str, Any], players: dict[str, Any]) -> dict[str, Any]:
    users = {u["user_id"]: u for u in combined.get("users", [])}
    owner = r.get("owner", {}) or {}
    user = users.get(r.get("owner_id"))
    team_name = (user or {}).get("metadata", {}).get("team_name")
    settings = r.get("settings", {}) or {}
    division_num = settings.get("division")
    divisions = combined.get("league", {}).get("metadata", {}) or {}
    division_label = divisions.get(f"division_{division_num}", f"Division {division_num}" if division_num else "—")
    player_list = [player_label(pid, players) for pid in (r.get("players", []) or [])]
    return {
        "roster_id": r.get("roster_id"),
        "Team": team_name or owner.get("display_name") or f"Roster {r.get('roster_id')}",
        "Owner": owner.get("display_name") or user.get("display_name", "—"),
        "Division": division_label,
        "Record": f"{settings.get('wins', 0)}-{settings.get('losses', 0)}",
        "Fpts": settings.get("fpts", 0),
        "Players": len(player_list),
        "_player_list": player_list,
    }


def render_waiver(combined: dict[str, Any], my_name: str) -> None:
    players = get_player_map()
    owned: set = set()
    for r in combined.get("rosters", []):
        owned.update(r.get("players", []) or [])

    users = combined.get("users", [])
    my_user = next((u for u in users if u.get("display_name") == my_name), None)
    if not my_user:
        st.warning(f"Could not find user '{my_name}'. Set it in the sidebar.")
        return
    my_roster = next((r for r in combined.get("rosters", []) if r.get("owner_id") == my_user.get("user_id")), None)
    if not my_roster:
        st.warning("Could not find your roster.")
        return

    league = combined.get("league", {})
    ls = league.get("settings", {}) or {}
    total_budget = ls.get("waiver_budget", 1000)
    used = (my_roster.get("settings", {}) or {}).get("waiver_budget_used", 0)
    remaining = max(0, total_budget - used)

    roster_positions = combined.get("roster_positions", [])
    slots = Counter(p for p in roster_positions if p not in ("BN", "IR", "RES", "TAXI"))
    slots.pop("FLEX", None)
    slots.pop("SUPER_FLEX", None)
    required = dict(slots)
    capacity = len(roster_positions) + ls.get("taxi_slots", 0) + ls.get("reserve_slots", 0)

    my_pids = my_roster.get("players", [])
    have = Counter(players.get(pid, {}).get("position") for pid in my_pids)
    need = {pos: required.get(pos, 0) - have.get(pos, 0) for pos in required}

    my_rows = build_player_rows(my_pids, set(), players, combined, {}, {})
    rec_pids = {r["pid"] for _, r, _ in recommend(my_rows, roster_positions)}
    bench = sorted(
        (r for r in my_rows if r["pid"] not in rec_pids and r["pos"] in WAIVER_POSITIONS),
        key=lambda r: r["blended"] if r["blended"] is not None else -1.0,
    )

    free_agents: list[tuple[str, dict[str, Any], float]] = []
    for pid, p in players.items():
        if pid in owned:
            continue
        pos = p.get("position")
        if pos not in WAIVER_POSITIONS:
            continue
        if p.get("status") not in (None, "Active"):
            continue
        proj = projection_for(pid, combined)
        if proj is None or proj <= 0:
            continue
        free_agents.append((pid, p, proj))
    free_agents.sort(key=lambda x: -x[2])
    top = free_agents[:200]

    need_txt = {
        pos: f"{'SHORT' if n > 0 else 'ok'} ({have.get(pos, 0)} rostered / {required.get(pos, 0)} start)"
        for pos, n in need.items()
    }

    c1, c2, c3 = st.columns(3)
    c1.metric("Remaining FAAB", f"${remaining}")
    c2.metric("Roster size", f"{len(my_pids)}/{capacity}")
    c3.metric("Free agents with projections", len(top))

    if len(my_pids) >= capacity:
        st.warning(f"Roster is full ({len(my_pids)}/{capacity}) — every pickup requires dropping someone.")

    pos_opts = ["All"] + [p for p in ("QB", "RB", "WR", "TE") if any(x[1].get("position") == p for x in top)]
    filt = st.selectbox("Position", pos_opts)

    rows = []
    for pid, p, proj in top:
        pos = p.get("position")
        if filt != "All" and pos != filt:
            continue
        rows.append(
            {
                "Player": p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or pid,
                "Pos": pos,
                "Team": p.get("team", "FA"),
                "Proj": proj,
                "My need": need_txt.get(pos, "ok"),
            }
        )
    st.subheader("Top available players")
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    scored = []
    for pid, p, proj in top:
        pos = p.get("position")
        n = need.get(pos, 0)
        rank = proj + (n * 2.0 if n > 0 else -proj * 0.2)
        scored.append((rank, pid, p, proj, n))
    scored.sort(key=lambda x: -x[0])

    st.subheader("Pickup suggestions")
    for rank, pid, p, proj, n in scored[:10]:
        pos = p.get("position")
        name = p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or pid
        line = f"**{name}** ({pos}, {p.get('team', 'FA')}) — proj {proj:.1f}"
        if n > 0:
            line += f" — fills your {pos} shortage ({have.get(pos, 0)} rostered / {required.get(pos, 0)} starters)"
        drop = next((r for r in bench if r["pos"] == pos), None) or (bench[0] if bench else None)
        if drop:
            dproj = drop["proj"] if drop["proj"] is not None else 0.0
            line += f". Drop **{drop['name']}** (proj {dproj:.1f})"
        pct = 0.25 if proj >= 15 else (0.15 if proj >= 10 else 0.05)
        line += f". Suggested bid: **${int(remaining * pct)}**"
        st.markdown(f"- {line}")

    if not bench:
        st.info("No bench candidates identified for dropping.")
    with st.expander("My bench (drop candidates)"):
        st.write("\n".join(f"{r['name']} ({r['pos']}, {r['team']})" for r in bench))


def render_draft(combined: dict[str, Any]) -> None:
    st.subheader("Future draft picks by team")
    traded = combined.get("traded_picks", [])
    if not traded:
        st.info("No traded-pick data loaded.")
    else:
        owned: dict[int, list] = {}
        sent: dict[int, list] = {}
        for p in traded:
            season, rnd = p.get("season"), p.get("round")
            owned.setdefault(p.get("owner_id"), []).append((season, rnd))
            sent.setdefault(p.get("roster_id"), []).append((season, rnd))
        rows = []
        for r in combined.get("rosters", []):
            rid = r["roster_id"]
            o = ", ".join(f"{s} R{rnd}" for s, rnd in sorted(owned.get(rid, []), key=lambda x: (x[0], x[1]))) or "—"
            s = ", ".join(f"{s} R{rnd}" for s, rnd in sorted(sent.get(rid, []), key=lambda x: (x[0], x[1]))) or "—"
            rows.append(
                {
                    "Team": roster_team_name(rid, combined),
                    "Picks owned": o,
                    "Own picks sent away": s,
                    "Net picks": len(owned.get(rid, [])) - len(sent.get(rid, [])),
                }
            )
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    drafts = combined.get("drafts", [])
    st.subheader("Draft results")
    if not drafts:
        st.info("No draft data loaded.")
        return
    for d in drafts:
        meta = d.get("metadata", {}) or {}
        st.caption(f"{meta.get('name') or 'Draft'} — {d.get('season')} {d.get('type')} ({d.get('status')})")
    picks = combined.get("draft_picks", [])
    if picks:
        players = get_player_map()
        rows = []
        for p in sorted(picks, key=lambda x: x.get("pick_no") or 0):
            rid = p.get("roster_id")
            try:
                rid = int(rid)
            except (TypeError, ValueError):
                rid = 0
            rows.append(
                {
                    "Pick": p.get("pick_no"),
                    "Round": p.get("round"),
                    "Player": player_name(p.get("player_id", ""), players),
                    "Team": roster_team_name(rid, combined),
                }
            )
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def render_activity(combined: dict[str, Any]) -> None:
    txs = combined.get("transactions", [])
    if not txs:
        st.info("No transactions loaded for this week.")
        return
    players = get_player_map()
    rows = []
    for tx in txs:
        teams = ", ".join(roster_team_name(rid, combined) for rid in (tx.get("roster_ids") or []))
        adds = ", ".join(player_name(pid, players) for pid in (tx.get("adds") or {}))
        drops = ", ".join(player_name(pid, players) for pid in (tx.get("drops") or {}))
        bid = (tx.get("settings") or {}).get("waiver_bid")
        rows.append(
            {
                "Type": tx.get("type"),
                "Week": tx.get("leg"),
                "Teams": teams,
                "Adds": adds or "—",
                "Drops": drops or "—",
                "FAAB": f"${bid}" if bid is not None else "—",
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, width="stretch")


def render_overview(combined: dict[str, Any]) -> None:
    league = combined.get("league", {})
    rosters = combined.get("rosters", [])
    users = combined.get("users", [])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("League", league.get("name", "—"))
    c2.metric("Status", str(league.get("status", "—")).replace("_", " ").title())
    c3.metric("Teams", len(rosters))
    c4.metric("Users", len(users))

    divisions = league.get("metadata", {}) or {}
    div_rows = []
    for i in range(1, 9):
        label = divisions.get(f"division_{i}")
        if label:
            count = sum(1 for r in rosters if (r.get("settings", {}) or {}).get("division") == i)
            div_rows.append({"Division": label, "Teams": count})
    if div_rows:
        st.subheader("Divisions")
        st.dataframe(pd.DataFrame(div_rows), hide_index=True, width="stretch")

    with st.expander("Raw league JSON"):
        st.json(league)

    bracket = combined.get("winners_bracket", []) or []
    if bracket:
        with st.expander("Playoff bracket (winners)"):
            rows = []
            for m in bracket:

                def label(x):
                    if x:
                        return roster_team_name(x, combined)
                    frm = m.get("t1_from") or m.get("t2_from") or {}
                    return f"{'W' if 'w' in frm else 'L'}{frm.get('w') or frm.get('l')}" if frm else "TBD"

                rows.append(
                    {
                        "Round": m.get("r"),
                        "Match": m.get("m"),
                        "Team 1": label(m.get("t1")),
                        "Team 2": label(m.get("t2")),
                        "Winner": roster_team_name(m["w"], combined) if m.get("w") else "—",
                    }
                )
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def render_rosters(combined: dict[str, Any]) -> None:
    rosters = combined.get("rosters", [])
    if not rosters:
        st.warning("No roster data loaded.")
        return

    players = get_player_map()

    divisions = set()
    for r in rosters:
        num = (r.get("settings", {}) or {}).get("division")
        meta = combined.get("league", {}).get("metadata", {}) or {}
        label = meta.get(f"division_{num}", f"Division {num}" if num else "All")
        divisions.add(label)
    options = ["All"] + sorted(divisions, key=lambda d: (d == "All", d))
    filter_div = st.selectbox("Filter by division", options)

    records = []
    for r in rosters:
        rec = roster_record(r, combined, players)
        if filter_div != "All" and rec["Division"] != filter_div:
            continue
        records.append(rec)

    df = pd.DataFrame([{k: v for k, v in rec.items() if k != "_player_list"} for rec in records])
    df["Fpts"] = df["Fpts"].astype(float)
    df = df.sort_values("Fpts", ascending=False)
    st.subheader(f"Rosters ({len(df)})")
    st.dataframe(df, hide_index=True, width="stretch")

    st.subheader("Full rosters")
    for rec in records:
        with st.expander(f"{rec['Team']} — {rec['Record']}"):
            st.write("\n".join(rec["_player_list"]))


def render_trending(combined: dict[str, Any]) -> None:
    players = get_player_map()

    def table(items: list[dict[str, Any]]) -> pd.DataFrame:
        rows = []
        for item in items:
            pid = item.get("player_id")
            p = players.get(pid, {})
            name = p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or pid
            rows.append(
                {
                    "Player": name,
                    "Position": p.get("position", "?"),
                    "Team": p.get("team", "FA"),
                    "Count (24h)": item.get("count", 0),
                }
            )
        return pd.DataFrame(rows).sort_values("Count (24h)", ascending=False)

    adds = combined.get("trending_players_add_sample", [])
    drops = combined.get("trending_players_drop_sample", [])
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Most added")
        if adds:
            st.dataframe(table(adds), hide_index=True, width="stretch")
        else:
            st.info("No add data loaded.")
    with c2:
        st.subheader("Most dropped")
        if drops:
            st.dataframe(table(drops), hide_index=True, width="stretch")
        else:
            st.info("No drop data loaded.")


def main() -> None:
    st.set_page_config(page_title="Sleeper League Dashboard", page_icon=":football:", layout="wide")
    st.title("Sleeper League Dashboard")

    st.sidebar.header("Data source")
    league_id = st.sidebar.text_input("League ID", value=combined_league_default())
    my_name = st.sidebar.text_input("Your display name", value="ashtondf")
    year_week = st.sidebar.number_input("Analysis week", min_value=1, max_value=21, value=analysis_week_default())

    if st.sidebar.button("Pull fresh data from Sleeper", type="primary"):
        with st.spinner("Fetching league data..."):
            try:
                fetch_combined(league_id.strip(), week=int(year_week))
            except requests.RequestException as e:
                st.sidebar.error(f"Failed: {e}")
            else:
                st.rerun()

    if st.sidebar.button("Build vs-team history (nflverse)"):
        with st.spinner("Downloading nflverse weekly stats..."):
            vs_team.build_vs_team()
        st.success("Player-vs-team history refreshed.")
        st.rerun()

    players_cached = PLAYERS_CACHE.exists()
    st.sidebar.caption(f"Combined data: {'loaded' if COMBINED_FILE.exists() else 'not loaded'}")
    st.sidebar.caption(f"Player name cache: {'cached' if players_cached else 'not cached'}")
    st.sidebar.caption(f"Vs-team history: {'cached' if VS_TEAM_FILE.exists() else 'not built'}")
    if st.sidebar.button("Refresh player name cache"):
        PLAYERS_CACHE.unlink(missing_ok=True)
        with st.spinner("Downloading players..."):
            get_player_map()
        st.rerun()

    combined = load_combined()
    if not combined:
        st.info("No combined data found yet. Click **Pull fresh data from Sleeper** in the sidebar.")
        st.stop()

    tab_my_team, tab_waiver, tab_overview, tab_rosters, tab_trending, tab_draft, tab_activity = st.tabs(
        ["My Team", "Waiver Wire", "Overview", "Rosters", "Trending", "Draft & Picks", "Activity"]
    )
    with tab_my_team:
        render_my_team(combined, my_name)
    with tab_waiver:
        render_waiver(combined, my_name)
    with tab_overview:
        render_overview(combined)
    with tab_rosters:
        render_rosters(combined)
    with tab_trending:
        render_trending(combined)
    with tab_draft:
        render_draft(combined)
    with tab_activity:
        render_activity(combined)


def combined_league_default() -> str:
    combined = load_combined()
    return combined.get("league", {}).get("league_id", "1359362301764861952")


def analysis_week_default() -> int:
    combined = load_combined()
    return int(combined.get("analysis_week", 1))


if __name__ == "__main__":
    main()
