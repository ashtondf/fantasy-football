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

## Docker

The dashboard ships as a self-contained image (`ashtondf/fantasy-league`). It
needs nothing from your machine except Docker — Sleeper, nflverse, and the
player database are all fetched from inside the container.

All generated data lives in `/data` inside the container. Mount a named volume
there so cached data survives restarts and is shared across containers.

### Prerequisites

- [Docker Desktop](https://docs.docker.com/get-docker/) (or Docker Engine)
  running locally.

### Getting started

Pull and run the official image, keeping data in a named volume:

```bash
docker pull ashtondf/fantasy-league:latest
docker run --rm -p 8501:8501 -v fantasy-data:/data ashtondf/fantasy-league:latest
```

Open http://localhost:8501, then in the sidebar:

1. Enter your **League ID** (Sleeper → League settings → copy the Legion ID).
2. Enter your **display name**.
3. Click **Pull fresh data from Sleeper** (first load takes a few seconds).
4. Optional: click **Build vs-team history (nflverse)** to enable per-opponent
   start/sit context.

Everything is cached under `/data`, so restarts are instant.

### Useful commands

| Command | What it does |
| ------- | ------------ |
| `docker run --rm -p 8501:8501 -v fantasy-data:/data ashtondf/fantasy-league:latest` | Run the dashboard (foreground) |
| `docker run -d --name fantasy-league -p 8501:8501 -v fantasy-data:/data ashtondf/fantasy-league:latest` | Run in the background |
| `docker logs -f fantasy-league` | Tail the dashboard logs |
| `docker stop fantasy-league && docker rm fantasy-league` | Stop and remove the container |
| `docker volume ls` / `docker volume rm fantasy-data` | Inspect / wipe cached data |
| `docker run --rm -v fantasy-data:/data ashtondf/fantasy-league:latest sleeper-pull` | Refresh data without starting the UI |

### Refresh data without the UI

The image bundles the `sleeper-pull` CLI:

```bash
docker run --rm -v fantasy-data:/data ashtondf/fantasy-league:latest sleeper-pull --league 1359362301764861952 --week 3
```

Omitting `--week` uses the league's current week.

### Update to a new image

```bash
docker pull ashtondf/fantasy-league:latest
docker run --rm -p 8501:8501 -v fantasy-data:/data ashtondf/fantasy-league:latest
```

Your `/data` volume is preserved across image updates.

### Build from source / local compose

```bash
# from a local checkout
docker build -t fantasy-league .
docker compose up -d                      # run dashboard (persistent volume)
docker compose run --rm data-pull --league <id>   # one-shot data refresh
```

### Publish to Docker Hub

```bash
docker login
docker tag fantasy-league:local <user>/fantasy-league:latest
docker push <user>/fantasy-league:latest
```

### Troubleshooting

- **`address already in use` on 8501** — another Streamlit/Docker process owns
  the port. Find it with `lsof -nP -iTCP:8501 -sTCP:LISTEN` (macOS/Linux) and
  stop it, or map a different host port: `-p 8502:8501`.
- **Slow first load** — the first *Pull fresh data* downloads the ~5MB player
  map plus nflverse weeklies; later loads are served from `/data`.

### Sharing the dashboard

The container listens on all interfaces, so it's reachable on your local
network via your machine's LAN IP (`http://<your-ip>:8501`). To share across
the internet, use a tunnel:

```bash
cloudflared tunnel --url http://localhost:8501   # free, no account needed
```

The tunnel URL exposes everything (including the data-refresh buttons), so
share it selectively rather than publicly.

## Commands

| Command          | Purpose                                    |
| ---------------- | ------------------------------------------ |
| `make install`   | editable install with dev dependencies     |
| `make pull`      | refresh league data                        |
| `make run`       | launch the Streamlit UI                    |
| `make test`      | run the test suite                         |
| `make lint`      | ruff lint + import sorting check           |
| `docker compose up -d` | build and run the dashboard in Docker |
| `docker compose run --rm data-pull` | refresh data inside the container |

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