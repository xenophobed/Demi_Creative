# Creative Agent API - 使用指南

儿童创意工坊 FastAPI 服务

## 目录

- [快速开始](#快速开始)
- [API 端点](#api-端点)
- [开发指南](#开发指南)
- [测试指南](#测试指南)

---

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp ../.env.example ../.env
# 编辑 .env 文件，添加必要的 API keys
```

必需的环境变量：
```env
ANTHROPIC_API_KEY=your_anthropic_api_key
OPENAI_API_KEY=your_openai_api_key
```

### 3. 启动服务

```bash
# 开发模式（自动重载）
python -m backend.src.main

# 或使用 uvicorn
uvicorn backend.src.main:app --reload --host 0.0.0.0 --port 8000
```

服务将在 `http://localhost:8000` 启动

### 4. 访问 API 文档

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI JSON**: http://localhost:8000/api/openapi.json

---

## API 端点

### 健康检查

#### GET /
根路径健康检查

**响应示例**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-26T10:00:00",
  "services": {
    "api": "running",
    "session_manager": "running"
  }
}
```

#### GET /health
详细健康检查

**响应示例**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-26T10:00:00",
  "services": {
    "api": "running",
    "session_manager": "running",
    "environment": "configured"
  }
}
```

---

### 画作转故事

#### POST /api/v1/image-to-story
上传儿童画作，生成个性化故事

**请求参数** (Form Data):
- `image` (file, 必填): 画作图片（PNG/JPG，最大10MB）
- `child_id` (string, 必填): 儿童唯一标识符
- `age_group` (enum, 必填): 年龄组（"3-5", "6-8", "9-12"）
- `interests` (string, 可选): 兴趣标签，逗号分隔（最多5个）
- `voice` (string, 可选): 语音类型（默认: "nova"）
- `enable_audio` (boolean, 可选): 是否生成语音（默认: true）

**示例请求**:
```bash
curl -X POST "http://localhost:8000/api/v1/image-to-story" \
  -F "image=@drawing.png" \
  -F "child_id=child_001" \
  -F "age_group=6-8" \
  -F "interests=动物,冒险,太空" \
  -F "voice=nova" \
  -F "enable_audio=true"
```

**响应示例** (201 Created):
```json
{
  "story_id": "uuid-here",
  "story": {
    "text": "从前有一只小狗...",
    "word_count": 350,
    "age_adapted": true
  },
  "audio_url": "https://example.com/audio.mp3",
  "educational_value": {
    "themes": ["友谊", "勇气"],
    "concepts": ["颜色", "动物"],
    "moral": "友谊让我们更强大"
  },
  "characters": [
    {
      "character_name": "闪电小狗",
      "description": "一只勇敢的小狗",
      "appearances": 2
    }
  ],
  "analysis": {
    "objects": ["小狗", "树"],
    "emotions": ["快乐"]
  },
  "safety_score": 0.95,
  "created_at": "2024-01-26T10:00:00"
}
```

---

### 互动故事

#### POST /api/v1/story/interactive/start
开始新的互动故事会话

**请求体** (JSON):
```json
{
  "child_id": "child_001",
  "age_group": "6-8",
  "interests": ["动物", "冒险"],
  "theme": "森林探险",
  "voice": "fable",
  "enable_audio": true
}
```

**响应示例** (201 Created):
```json
{
  "session_id": "uuid-here",
  "story_title": "神秘的森林探险",
  "opening": {
    "segment_id": 0,
    "text": "在一个阳光明媚的早晨...",
    "audio_url": "https://example.com/audio.mp3",
    "choices": [
      {
        "choice_id": "choice_0_a",
        "text": "立刻打开看看",
        "emoji": "🔓"
      },
      {
        "choice_id": "choice_0_b",
        "text": "先找朋友一起来",
        "emoji": "👫"
      }
    ],
    "is_ending": false
  },
  "created_at": "2024-01-26T10:00:00"
}
```

#### POST /api/v1/story/interactive/{session_id}/choose
在互动故事中做出选择

**路径参数**:
- `session_id`: 会话ID

**请求体** (JSON):
```json
{
  "choice_id": "choice_0_a"
}
```

**响应示例** (200 OK):
```json
{
  "session_id": "uuid-here",
  "next_segment": {
    "segment_id": 1,
    "text": "小主人公勇敢地走进山洞...",
    "audio_url": "https://example.com/audio.mp3",
    "choices": [
      {
        "choice_id": "choice_1_a",
        "text": "继续深入",
        "emoji": "➡️"
      },
      {
        "choice_id": "choice_1_b",
        "text": "停下来观察",
        "emoji": "👀"
      }
    ],
    "is_ending": false
  },
  "choice_history": ["choice_0_a"],
  "progress": 0.2
}
```

#### GET /api/v1/story/interactive/{session_id}/status
获取互动故事会话状态

**路径参数**:
- `session_id`: 会话ID

**响应示例** (200 OK):
```json
{
  "session_id": "uuid-here",
  "status": "active",
  "child_id": "child_001",
  "story_title": "神秘的森林探险",
  "current_segment": 2,
  "total_segments": 5,
  "choice_history": ["choice_0_a", "choice_1_b"],
  "educational_summary": null,
  "created_at": "2024-01-26T10:00:00",
  "updated_at": "2024-01-26T10:05:00",
  "expires_at": "2024-01-27T10:00:00"
}
```

---

## 开发指南

### 项目结构

```
backend/
├── src/
│   ├── api/
│   │   ├── models.py          # Pydantic 模型
│   │   ├── routes/
│   │   │   ├── image_to_story.py
│   │   │   └── interactive_story.py
│   │   └── __init__.py
│   ├── services/
│   │   ├── session_manager.py # 会话管理
│   │   └── __init__.py
│   ├── agents/
│   │   └── image_to_story_agent.py
│   ├── mcp_servers/           # MCP Tools
│   └── main.py                # FastAPI 应用
└── requirements.txt
```

### 添加新端点

1. 在 `src/api/models.py` 中定义请求/响应模型
2. 在 `src/api/routes/` 中创建路由文件
3. 在 `src/main.py` 中注册路由

示例：
```python
# src/api/routes/new_feature.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["新功能"])

@router.post("/new-feature")
async def new_feature():
    return {"message": "Hello"}

# src/main.py
from .api.routes import new_feature
app.include_router(new_feature.router)
```

### 环境配置

- **开发环境**: `ENVIRONMENT=development`
- **测试环境**: `ENVIRONMENT=test`
- **生产环境**: `ENVIRONMENT=production`

### 日志记录

使用 Python 标准库的 logging:
```python
import logging

logger = logging.getLogger(__name__)
logger.info("信息日志")
logger.error("错误日志")
```

---

## 测试指南

### 运行所有测试

```bash
# 从项目根目录运行
pytest tests/ -v
```

### 运行特定测试

```bash
# API 测试
pytest tests/api/ -v

# 集成测试
pytest tests/integration/ -v

# 契约测试
pytest tests/contracts/ -v

# 单个测试文件
pytest tests/api/test_health.py -v

# 单个测试类
pytest tests/api/test_health.py::TestHealthCheck -v

# 单个测试函数
pytest tests/api/test_health.py::TestHealthCheck::test_root_endpoint -v
```

### 测试覆盖率

```bash
# 生成覆盖率报告
pytest tests/ --cov=backend/src --cov-report=html

# 查看报告
open htmlcov/index.html
```

### 跳过慢速测试

某些测试（如端到端测试）可能需要外部服务，使用 `@pytest.mark.skip` 标记：

```bash
# 运行除跳过外的所有测试
pytest tests/ -v
```

### 测试文件组织

```
tests/
├── api/                      # API 端点测试
│   ├── test_health.py
│   ├── test_image_to_story.py
│   └── test_interactive_story.py
├── integration/              # 集成测试
│   ├── test_session_integration.py
│   └── test_end_to_end.py
└── contracts/                # 契约测试
    └── mcp_tools_contract.py
```

### Mock 外部依赖

对于依赖外部服务的测试，使用 `pytest-mock`:

```python
@pytest.mark.asyncio
async def test_with_mock(mocker):
    # Mock Agent 调用
    mock_result = {"story": "测试故事"}
    mocker.patch(
        "backend.src.agents.image_to_story_agent.image_to_story",
        return_value=mock_result
    )

    # 测试代码...
```

---

## 常见问题

### Q: API 启动失败
A: 检查以下项目：
1. 环境变量是否正确配置（`.env` 文件）
2. 依赖是否完全安装（`pip install -r requirements.txt`）
3. 端口 8000 是否被占用

### Q: 文件上传失败
A: 确保：
1. 文件大小 < 10MB
2. 文件格式为 PNG/JPG/WEBP
3. `python-multipart` 已安装

### Q: 测试失败
A: 常见原因：
1. 缺少环境变量（测试用）
2. 外部服务未 mock
3. 测试数据目录权限问题

---

## 性能优化

### 建议的生产配置

```bash
# 使用多个 worker
uvicorn backend.src.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --log-level info
```

### 使用 Gunicorn（推荐）

```bash
gunicorn backend.src.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

---

## 安全建议

1. **永远不要提交 `.env` 文件到版本控制**
2. **生产环境使用 HTTPS**
3. **限制 CORS 允许的源**
4. **实现速率限制** (使用 `slowapi` 等)
5. **定期更新依赖**

---

## 支持

如有问题，请查看：
- [ARCHITECTURE.md](../ARCHITECTURE.md) - 技术架构
- [PRD.md](../PRD.md) - 产品需求
- [IMPLEMENTATION_LOG.md](../IMPLEMENTATION_LOG.md) - 实现日志

---

**版本**: 1.0.0
**最后更新**: 2024-01-26
