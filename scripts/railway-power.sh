#!/usr/bin/env bash
# Power on/off the Railway prod service on demand.
#
# Usage:
#   scripts/railway-power.sh up        # bring service online (uses last build, ~30s)
#   scripts/railway-power.sh down      # take service offline (stops billing for RAM)
#   scripts/railway-power.sh status    # show current deployment + live URL state
#   scripts/railway-power.sh window    # idempotent: ensure up if inside WINDOW, down otherwise
#
# Schedule example (macOS launchd or crontab):
#   # weekdays 8pm: up; 10pm: down
#   0 20 * * 1-5  /path/to/scripts/railway-power.sh up
#   0 22 * * 1-5  /path/to/scripts/railway-power.sh down
#
# Cost note: `down` removes the running container (no RAM billing). `up` redeploys
# the last successful build with no rebuild step — typical wake time ~20-40s.
# Build time is only paid on commits, not on power cycles.

set -euo pipefail

# Linked project assumed via `railway link`. Verify with: railway status
PROJECT_NAME="${RAILWAY_POWER_PROJECT:-kids-creative-backend}"
SERVICE_NAME="${RAILWAY_POWER_SERVICE:-kids-creative-backend}"
HEALTH_URL="${RAILWAY_POWER_HEALTH_URL:-https://kids-creative-backend-production.up.railway.app/health}"

# Window mode: hours in 24h local time. Defaults to 20:00-22:00 (8pm-10pm).
WINDOW_START_HOUR="${RAILWAY_POWER_START_HOUR:-20}"
WINDOW_END_HOUR="${RAILWAY_POWER_END_HOUR:-22}"

log() { printf '[railway-power] %s\n' "$*" >&2; }

require_link() {
  if ! railway status >/dev/null 2>&1; then
    log "ERROR: not linked. Run: railway link --project $PROJECT_NAME"
    exit 2
  fi
}

cmd_up() {
  require_link
  log "starting service $SERVICE_NAME ..."
  railway redeploy --yes --service "$SERVICE_NAME"
  log "redeploy triggered. polling $HEALTH_URL ..."
  for i in $(seq 1 60); do
    code="$(curl -sS -o /dev/null -w '%{http_code}' -m 5 "$HEALTH_URL" || echo 000)"
    if [ "$code" = "200" ]; then
      log "service is UP after ${i}0s (HTTP 200)"
      exit 0
    fi
    sleep 10
  done
  log "WARNING: service did not return 200 within 10 minutes. Check: railway logs --deployment"
  exit 1
}

cmd_down() {
  require_link
  log "stopping service $SERVICE_NAME ..."
  railway down --yes --service "$SERVICE_NAME"
  log "service stopped. RAM billing paused."
}

cmd_status() {
  require_link
  echo "=== Railway status ==="
  railway status
  echo
  echo "=== Live health check ==="
  code="$(curl -sS -o /dev/null -w '%{http_code}' -m 5 "$HEALTH_URL" || echo 000)"
  echo "$HEALTH_URL -> HTTP $code"
}

cmd_window() {
  require_link
  hour="$(date +%H)"
  hour="${hour#0}" # strip leading zero
  : "${hour:=0}"
  if [ "$hour" -ge "$WINDOW_START_HOUR" ] && [ "$hour" -lt "$WINDOW_END_HOUR" ]; then
    log "inside window ($WINDOW_START_HOUR-$WINDOW_END_HOUR), ensuring UP"
    cmd_up
  else
    log "outside window ($WINDOW_START_HOUR-$WINDOW_END_HOUR), ensuring DOWN"
    cmd_down
  fi
}

case "${1:-}" in
  up)     cmd_up ;;
  down)   cmd_down ;;
  status) cmd_status ;;
  window) cmd_window ;;
  *)
    sed -n '2,18p' "$0"
    exit 1
    ;;
esac
