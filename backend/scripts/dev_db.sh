#!/usr/bin/env bash
# Thin wrapper around docker-compose for the local-dev Postgres + pgvector
# container. Useful so devs don't have to remember the compose syntax.
#
# Usage:
#   ./backend/scripts/dev_db.sh up      # start postgres (idempotent)
#   ./backend/scripts/dev_db.sh down    # stop postgres (volume preserved)
#   ./backend/scripts/dev_db.sh reset   # nuke volume + restart (DESTRUCTIVE)
#   ./backend/scripts/dev_db.sh psql    # open psql shell as the creative user
#   ./backend/scripts/dev_db.sh logs    # follow logs
#   ./backend/scripts/dev_db.sh status  # show container health
#
# After `up`, set DATABASE_URL in your shell:
#   export DATABASE_URL=postgresql://creative:creative@localhost:54329/creative_agent_dev

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

CMD="${1:-up}"

case "$CMD" in
  up)
    docker compose up -d postgres
    echo "Waiting for Postgres to be healthy..."
    until docker exec creative_agent_pg pg_isready -U creative -d creative_agent_dev >/dev/null 2>&1; do
      sleep 1
    done
    echo "Postgres ready on localhost:54329"
    echo
    echo "Next:"
    echo "  export DATABASE_URL=postgresql://creative:creative@localhost:54329/creative_agent_dev"
    echo "  python backend/scripts/start_server.py"
    ;;
  down)
    docker compose down
    ;;
  reset)
    echo "WARNING: this will destroy all local Postgres data."
    read -p "Type 'yes' to continue: " confirm
    if [[ "$confirm" == "yes" ]]; then
      docker compose down -v
      docker compose up -d postgres
      echo "Volume reset. Re-run init_schema by starting the app."
    else
      echo "Aborted."
      exit 1
    fi
    ;;
  psql)
    docker exec -it creative_agent_pg psql -U creative -d creative_agent_dev
    ;;
  logs)
    docker compose logs -f postgres
    ;;
  status)
    docker compose ps postgres
    ;;
  *)
    echo "Unknown command: $CMD"
    echo "Usage: $0 {up|down|reset|psql|logs|status}"
    exit 1
    ;;
esac
