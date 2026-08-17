# Contributing / Maintenance Guide

Internal guide for developing **fantasy-league** and shipping it inside the
Docker image. The end-user docs live in [README.md](README.md); this file is
for the maintainer.

## Repository layout

| Path | Purpose |
| ---- | ------- |
| `src/fantasy_league/sleeper.py` | Sleeper API client + combined-data aggregation; CLI entry point `sleeper-pull` |
| `src/fantasy_league/vs_team.py` | nflverse player-vs-team history + schedule lookups |
| `src/fantasy_league/analysis.py` | Lineup optimization / projection logic (framework-free, unit-testable) |
| `src/fantasy_league/paths.py` | Runtime data paths (`FANTASY_DATA_DIR`, default `data/`) |
| `src/fantasy_league/ui/app.py` | Streamlit front-end |
| `tests/` | pytest suite |
| `Dockerfile` | Production image definition |
| `docker-compose.yml` | Local compose: dashboard + `data-pull` service |

## Setting up a dev environment

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

`make install` does the same.

## Making and verifying changes

1. Edit code under `src/fantasy_league/`. Keep Streamlit imports out of
   framework-free modules (`analysis.py`, `paths.py`, `sleeper.py`,
   `vs_team.py`) so they stay testable.
2. Lint and format:

   ```bash
   make lint                      # ruff check + format --check
   .venv/bin/ruff check --fix .   # auto-fix issues
   .venv/bin/ruff format .        # auto-format
   ```

   Ruff config lives in `pyproject.toml` (`line-length = 120`, `E/F/I/UP`).
3. Run tests:

   ```bash
   make test
   ```

4. Smoke-test the UI:

   ```bash
   ./run-ui.sh                    # open http://localhost:8501
   ```

   or headless over Streamlit's testing framework:

   ```bash
   .venv/bin/python - <<'EOF'
   from streamlit.testing.v1 import AppTest
   at = AppTest.from_file("src/fantasy_league/ui/app.py", default_timeout=180)
   at.run()
   assert not at.exception
   print("ok:", at.exception)
   EOF
   ```

5. Refresh data during development:

   ```bash
   make pull                      # writes data/sleeper_league_combined.json
   ```

## Building the Docker image

The `Dockerfile` copies `src/`, `pyproject.toml`, and `README.md` into the
image and runs `pip install .` — so **any change under `src/` or
`pyproject.toml` requires a rebuild** (there is no bind mount in the
production image).

```bash
docker build -t fantasy-league:local .
```

Quick iteration during UI work can bind-mount live code:

```bash
docker run --rm -p 8501:8501 \
  -v "$PWD/src:/app/src" \
  -v fantasy-data:/data \
  fantasy-league:local
```

(Not recommended for final verification — always test the image as the person
pulling it will see it.)

## Verifying a built image

1. Boot the dashboard and check it becomes `healthy`:

   ```bash
   docker run -d --name ff-check -p 8501:8501 -v fantasy-data:/data \
     fantasy-league:local
   watch docker inspect --format '{{.State.Health.Status}}' ff-check
   curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8501/_stcore/health
   docker stop ff-check && docker rm ff-check
   ```

2. Exercise the CLI inside the container:

   ```bash
   docker run --rm -v fantasy-data:/data \
     fantasy-league:local sleeper-pull --league 1359362301764861952
   ```

   Confirms network access, entry point, and `/data` writes all work.

## Pushing to Docker Hub

The public image is `ashtondf/fantasy-league`. Steps:

```bash
docker login                       # interactive; needs your Docker Hub token

# single-arch (fast check) or multi-arch (recommended for distribution)
docker tag fantasy-league:local ashtondf/fantasy-league:latest
docker push ashtondf/fantasy-league:latest

# OR multi-arch in one step (linux/amd64 + linux/arm64) — what end users on
# Apple Silicon and x86 will actually pull:
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t ashtondf/fantasy-league:latest \
  --push .
```

`--push` builds and pushes all platforms in one command (requires Docker
Desktop or a buildx-capable Docker Engine). Verify the remote tag after
pushing:

```bash
docker buildx imagetools inspect ashtondf/fantasy-league:latest
```