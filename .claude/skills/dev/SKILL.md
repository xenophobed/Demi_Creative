---
name: dev
description: Start, stop, or restart the backend and frontend dev servers. Kills existing instances before starting new ones.
allowed-tools: Bash
argument-hint: [start | stop | restart | status | logs]
disable-model-invocation: true
---

# Dev Servers Skill

Manage dev servers: $ARGUMENTS

## Current State

- Backend PID: !`cat /tmp/demi_backend.pid 2>/dev/null || echo "not running"`
- Frontend PID: !`cat /tmp/demi_frontend.pid 2>/dev/null || echo "not running"`

## Commands

Based on `$ARGUMENTS` (default is `start` if nothing provided):

### `start` or `restart` (or no argument)

1. **Kill any existing instances first**:
   ```bash
   # Kill backend
   if [ -f /tmp/demi_backend.pid ]; then
     kill $(cat /tmp/demi_backend.pid) 2>/dev/null
     rm -f /tmp/demi_backend.pid
   fi
   # Also kill any stray uvicorn on port 8000
   lsof -ti:8000 | xargs kill -9 2>/dev/null || true

   # Kill frontend
   if [ -f /tmp/demi_frontend.pid ]; then
     kill $(cat /tmp/demi_frontend.pid) 2>/dev/null
     rm -f /tmp/demi_frontend.pid
   fi
   # Also kill any stray node on port 5173
   lsof -ti:5173 | xargs kill -9 2>/dev/null || true
   ```

2. **Start backend**:
   ```bash
   cd backend
   nohup python scripts/start_server.py > /tmp/demi_backend.log 2>&1 &
   echo $! > /tmp/demi_backend.pid
   ```
   Wait 2 seconds then verify it's running:
   ```bash
   sleep 2 && curl -s http://localhost:8000/api/v1/health || echo "Backend failed to start — check /tmp/demi_backend.log"
   ```

3. **Start frontend**:
   ```bash
   cd frontend
   nohup npm run dev > /tmp/demi_frontend.log 2>&1 &
   echo $! > /tmp/demi_frontend.pid
   ```
   Wait 3 seconds then verify:
   ```bash
   sleep 3 && curl -s http://localhost:5173 > /dev/null && echo "Frontend running on http://localhost:5173" || echo "Frontend failed to start — check /tmp/demi_frontend.log"
   ```

4. **Report**:
   ```
   Backend:  http://localhost:8000  (API docs: http://localhost:8000/api/docs)
   Frontend: http://localhost:5173
   Logs:     /tmp/demi_backend.log, /tmp/demi_frontend.log
   ```

### `stop`

1. Kill backend and frontend using PID files and port cleanup (same as step 1 above)
2. Report: "All dev servers stopped."

### `status`

1. Check if backend is running:
   ```bash
   curl -s http://localhost:8000/api/v1/health && echo "Backend: running" || echo "Backend: stopped"
   ```
2. Check if frontend is running:
   ```bash
   curl -s http://localhost:5173 > /dev/null 2>&1 && echo "Frontend: running" || echo "Frontend: stopped"
   ```

### `logs`

1. Show last 30 lines of each log:
   ```bash
   echo "=== Backend ===" && tail -30 /tmp/demi_backend.log 2>/dev/null || echo "No backend log"
   echo "=== Frontend ===" && tail -30 /tmp/demi_frontend.log 2>/dev/null || echo "No frontend log"
   ```

## Notes

- Backend requires: `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` in environment
- Backend virtual env should be activated, or use the one at `backend/venv/`
- Frontend requires: `npm install` to have been run in `frontend/`
- Logs persist at `/tmp/demi_*.log` until next restart
