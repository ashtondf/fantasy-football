# fantasy-league

Streamlit dashboard for a Sleeper dynasty fantasy football league. Pulls league
data from the [Sleeper API](https://docs.sleeper.com/), joins it with
historical player-vs-team stats from [nflverse](https://github.com/nflverse/nflreadpy),
and surfaces matchup, start/sit, and waiver-wire advice.

## Highlights

- **My Team** — your upcoming matchup, recommended lineup with projections and
  player-vs-team history, and start/sit suggestions.
- **Waiver Wire** — free-agent pool ranked to your roster's position needs,
  with drop candidates and FAAB bid guidance.
- **Overview / Rosters / Trending / Draft & Picks / Activity** — league-wide
  views, playoff bracket, future draft capital, and transaction history.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
make pull        # fetch league data -> data/sleeper_league_combined.json
make run         # start the Streamlit UI at http://localhost:8501
```

or use the convenience scripts:

```bash
./run-ui.sh
.venv/bin/sleeper-pull --help
```

## Data

All generated data is written to `data/` (gitignored):

- `sleeper_league_combined.json` — combined Sleeper league payload (rosters,
  matchups, projections, transactions, draft picks, ...)
- `players_nfl.json` — cached Sleeper player map (~5MB)
- `vs_team.json` — per-player average scoring vs each opponent (from nflverse)
- `schedule_<season>.json` — cached NFL schedule for opponent lookups
- `nflverse_cache/` — nflreadpy filesystem cache

Override the data location with the `FANTASY_DATA_DIR` environment variable.

## Commands

| Command          | Purpose                                    |
| ---------------- | ------------------------------------------ |
| `make install`   | editable install with dev dependencies     |
| `make pull`      | refresh league data                        |
| `make run`       | launch the Streamlit UI                    |
| `make test`      | run the test suite                         |
| `make lint`      | ruff lint + import sorting check           |

## Layout

```
src/fantasy_league/
├── sleeper.py       # Sleeper API client + combined-data aggregation (CLI: sleeper-pull)
├── vs_team.py       # nflverse player-vs-team history + schedule lookups
├── analysis.py      # lineup optimization / projection logic (framework-free)
├── paths.py         # shared runtime paths
└── ui/app.py        # Streamlit front-end
tests/               # pytest suite
```