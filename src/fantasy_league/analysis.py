"""Lineup analysis and recommendation logic.

Pure functions (no I/O, no Streamlit) so they can be unit-tested and reused
by the dashboard or a future CLI.
"""

from collections import Counter
from typing import Any

WAIVER_POSITIONS = ("QB", "RB", "WR", "TE")
FLEX_POSITIONS = ("RB", "WR", "TE")
SUPER_FLEX_POSITIONS = ("QB", "RB", "WR", "TE")
_BENCH_SLOTS = ("BN", "IR", "RES", "TAXI")


def player_name(pid: str, players: dict[str, Any]) -> str:
    p = players.get(pid, {})
    return p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or pid


def projection_for(pid: str, combined: dict[str, Any]) -> float | None:
    entry = combined.get("projections", {}).get(pid)
    if not entry:
        return None
    val = (entry.get("stats") or {}).get("pts_half_ppr")
    return float(val) if val is not None else None


def build_player_rows(
    pids: list[str],
    starters: set,
    players: dict[str, Any],
    combined: dict[str, Any],
    opp_map: dict[str, str],
    vs: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for pid in pids:
        p = players.get(pid, {})
        team = p.get("team")
        pos = p.get("position")
        opp = opp_map.get(team) if team else None
        hist = vs.get(pid, {}).get(opp) if opp else None
        proj = projection_for(pid, combined)
        vs_avg = None
        if hist:
            vs_avg = hist.get("avg")
        if proj is None and vs_avg is not None:
            blended = vs_avg
        elif vs_avg is None and proj is not None:
            blended = proj
        elif proj is None:
            blended = None
        else:
            blended = 0.7 * float(proj) + 0.3 * float(vs_avg)
        rows.append(
            {
                "pid": pid,
                "name": player_name(pid, players),
                "pos": pos,
                "team": team,
                "opp": opp,
                "proj": float(proj) if proj is not None else None,
                "vs_avg": float(vs_avg) if vs_avg is not None else None,
                "vs_games": hist.get("games") if hist else None,
                "blended": float(blended) if blended is not None else None,
                "starter": pid in starters,
            }
        )
    return rows


def required_starting_slots(roster_positions: list[str]) -> tuple[dict[str, int], int, int]:
    """Return (mandatory positions->count, flex count, super-flex count)."""
    slots = Counter(p for p in roster_positions if p not in _BENCH_SLOTS)
    flex_count = slots.pop("FLEX", 0)
    sf_count = slots.pop("SUPER_FLEX", 0)
    return dict(slots), flex_count, sf_count


def recommend(
    rows: list[dict[str, Any]],
    roster_positions: list[str],
) -> list[tuple[str, dict[str, Any], dict[str, Any] | None]]:
    """Greedy lineup optimizer.

    Returns ``(slot, chosen_player, next_best_alternative)`` for every
    starting slot, where ``next_best_alternative`` is the runner-up for that
    slot (or ``None``).
    """
    required, flex_count, sf_count = required_starting_slots(roster_positions)
    pool = sorted(
        rows,
        key=lambda r: r["blended"] if r["blended"] is not None else float("-inf"),
        reverse=True,
    )
    chosen = set()
    result: list[tuple[str, dict[str, Any], dict[str, Any] | None]] = []

    def pick(cands: list[dict[str, Any]]) -> dict[str, Any]:
        picked = cands[0]
        chosen.add(picked["pid"])
        return picked

    for pos, cnt in required.items():
        cands = [r for r in pool if r["pos"] == pos and r["pid"] not in chosen]
        for _ in range(cnt):
            if not cands:
                break
            cur = pick(cands)
            cands = cands[1:]
            alt = next((r for r in cands if r["pos"] == pos), None)
            result.append((pos, cur, alt))
    if flex_count:
        cands = [r for r in pool if r["pos"] in FLEX_POSITIONS and r["pid"] not in chosen]
        for _ in range(flex_count):
            if not cands:
                break
            cur = pick(cands)
            cands = cands[1:]
            result.append(("FLEX", cur, cands[0] if cands else None))
    if sf_count:
        cands = [r for r in pool if r["pos"] in SUPER_FLEX_POSITIONS and r["pid"] not in chosen]
        for _ in range(sf_count):
            if not cands:
                break
            cur = pick(cands)
            cands = cands[1:]
            result.append(("SUPER_FLEX", cur, cands[0] if cands else None))
    return result
