# Health Check API

> API endpoints for service health status monitoring

## Overview

The Health Check API provides service status monitoring functionality, used to check the operational status of the API service and its dependent components.

**Base URL:** `/`

---

## Endpoint List

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Root path health check |
| GET | `/health` | Detailed health check |

---

## 1. Root Path Health Check

### `GET /`

Quickly check whether the service is running.

#### Request Example

```bash
curl "http://localhost:8000/"
```

#### Response Format

**Status Code:** `200 OK`

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-01-31T10:30:00",
  "services": {
    "api": "running",
    "session_manager": "running"
  }
}
```

---

## 2. Detailed Health Check

### `GET /health`

Check the status of the service and all dependent components.

#### Request Example

```bash
curl "http://localhost:8000/health"
```

#### Response Format

**Status Code:** `200 OK`

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-01-31T10:30:00",
  "services": {
    "api": "running",
    "session_manager": "running",
    "environment": "configured"
  }
}
```

#### Degraded State

When certain components encounter issues:

```json
{
  "status": "degraded",
  "version": "1.0.0",
  "timestamp": "2026-01-31T10:30:00",
  "services": {
    "api": "running",
    "session_manager": "degraded",
    "environment": "missing_keys"
  }
}
```

---

## Status Descriptions

### Overall Status (status)

| Status | Description |
|--------|-------------|
| `healthy` | All services are running normally |
| `degraded` | Some services are abnormal, but core functionality is available |

### Service Status (services)

| Service | Status Value | Description |
|---------|-------------|-------------|
| `api` | `running` | API service is running |
| `session_manager` | `running` | Session manager is healthy |
| `session_manager` | `degraded` | Session directory is inaccessible |
| `environment` | `configured` | Environment variables are configured |
| `environment` | `missing_keys` | Required environment variables are missing |

---

## Required Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `OPENAI_API_KEY` | OpenAI API key (for TTS) |

---

## Use Cases

### Load Balancer Health Check

```nginx
# Nginx configuration example
upstream backend {
    server localhost:8000;
}

server {
    location /health {
        proxy_pass http://backend/health;
    }
}
```

### Kubernetes Liveness/Readiness Probe

```yaml
# Kubernetes configuration example
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: creative-agent
    livenessProbe:
      httpGet:
        path: /health
        port: 8000
      initialDelaySeconds: 10
      periodSeconds: 30
    readinessProbe:
      httpGet:
        path: /
        port: 8000
      initialDelaySeconds: 5
      periodSeconds: 10
```

### Docker Compose

```yaml
# docker-compose.yml
services:
  api:
    image: creative-agent
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## Monitoring Examples

### Python Health Check Script

```python
import requests
import sys

def check_health():
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        data = response.json()

        if data["status"] == "healthy":
            print("Service is healthy")
            return 0
        else:
            print(f"Service is degraded: {data['services']}")
            return 1

    except requests.exceptions.RequestException as e:
        print(f"Service is down: {e}")
        return 2

if __name__ == "__main__":
    sys.exit(check_health())
```

### Shell Health Check

```bash
#!/bin/bash

health=$(curl -s http://localhost:8000/health | jq -r '.status')

if [ "$health" == "healthy" ]; then
    echo "Service is healthy"
    exit 0
else
    echo "Service is not healthy: $health"
    exit 1
fi
```
