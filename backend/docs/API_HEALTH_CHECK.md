# Health Check API (健康检查)

> 服务健康状态检查的 API 端点

## 概述

Health Check API 提供服务状态监控功能，用于检查 API 服务及其依赖组件的运行状态。

**Base URL:** `/`

---

## 端点列表

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/` | 根路径健康检查 |
| GET | `/health` | 详细健康检查 |

---

## 1. 根路径健康检查

### `GET /`

快速检查服务是否运行。

#### 请求示例

```bash
curl "http://localhost:8000/"
```

#### 响应格式

**状态码:** `200 OK`

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

## 2. 详细健康检查

### `GET /health`

检查服务及所有依赖组件的状态。

#### 请求示例

```bash
curl "http://localhost:8000/health"
```

#### 响应格式

**状态码:** `200 OK`

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

#### 降级状态

当某些组件出现问题时：

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

## 状态说明

### 整体状态 (status)

| 状态 | 描述 |
|------|------|
| `healthy` | 所有服务正常运行 |
| `degraded` | 部分服务异常，核心功能可用 |

### 服务状态 (services)

| 服务 | 状态值 | 描述 |
|------|--------|------|
| `api` | `running` | API 服务正在运行 |
| `session_manager` | `running` | 会话管理器正常 |
| `session_manager` | `degraded` | 会话目录不可访问 |
| `environment` | `configured` | 环境变量已配置 |
| `environment` | `missing_keys` | 缺少必需的环境变量 |

---

## 必需的环境变量

| 变量名 | 描述 |
|--------|------|
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 |
| `OPENAI_API_KEY` | OpenAI API 密钥（用于 TTS） |

---

## 使用场景

### 负载均衡器健康检查

```nginx
# Nginx 配置示例
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
# Kubernetes 配置示例
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

## 监控示例

### Python 健康检查脚本

```python
import requests
import sys

def check_health():
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        data = response.json()

        if data["status"] == "healthy":
            print("✅ Service is healthy")
            return 0
        else:
            print(f"⚠️ Service is degraded: {data['services']}")
            return 1

    except requests.exceptions.RequestException as e:
        print(f"❌ Service is down: {e}")
        return 2

if __name__ == "__main__":
    sys.exit(check_health())
```

### Shell 健康检查

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
