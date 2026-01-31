# Creative Agent API Documentation

> 儿童创意工坊 API 文档索引

## 概述

Creative Agent API 是一个基于 AI Agent 的创意内容生成平台，为 3-12 岁儿童提供安全、有趣、富有教育意义的内容创作服务。

**API 版本:** 1.0.0
**Base URL:** `http://localhost:8000`

---

## API 文档列表

| 文档 | 描述 |
|------|------|
| [API_IMAGE_TO_STORY.md](API_IMAGE_TO_STORY.md) | 画作转故事 API |
| [API_INTERACTIVE_STORY.md](API_INTERACTIVE_STORY.md) | 互动故事 API |
| [API_HEALTH_CHECK.md](API_HEALTH_CHECK.md) | 健康检查 API |

---

## 快速参考

### 画作转故事

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/api/v1/image-to-story` | 上传画作生成故事 |
| GET | `/api/v1/stories/{story_id}` | 获取故事详情 |
| GET | `/api/v1/stories` | 列出所有故事 |

### 互动故事

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/api/v1/story/interactive/start` | 开始互动故事 |
| POST | `/api/v1/story/interactive/{session_id}/choose` | 选择分支 |
| GET | `/api/v1/story/interactive/{session_id}/status` | 获取会话状态 |

### 健康检查

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | `/` | 快速健康检查 |
| GET | `/health` | 详细健康检查 |

---

## 认证

当前版本 API 无需认证。生产环境部署时应添加适当的认证机制。

---

## 通用响应格式

### 成功响应

```json
{
  "field1": "value1",
  "field2": "value2",
  ...
}
```

### 错误响应

```json
{
  "error": "ErrorType",
  "message": "错误描述",
  "details": [...],
  "timestamp": "2026-01-31T10:30:00"
}
```

### HTTP 状态码

| 状态码 | 描述 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 413 | 请求体过大 |
| 422 | 请求验证失败 |
| 500 | 服务器内部错误 |

---

## 年龄组

所有 API 使用统一的年龄组定义：

| 年龄组 | 描述 | 内容特点 |
|--------|------|----------|
| `3-5` | 学龄前儿童 | 简单词汇、短句、具体概念 |
| `6-8` | 小学低年级 | 基础词汇、简单情节、道德选择 |
| `9-12` | 小学高年级 | 丰富词汇、复杂情节、深度主题 |

---

## 语音类型

TTS 语音生成支持以下声音类型：

| 类型 | 描述 | 推荐场景 |
|------|------|----------|
| `nova` | 温柔女性 | 温馨故事 |
| `shimmer` | 活泼女性 | 欢快冒险 |
| `alloy` | 中性 | 通用 |
| `echo` | 男性 | 冒险故事 |
| `fable` | 故事讲述者 | 互动故事（默认） |
| `onyx` | 深沉男性 | 神秘故事 |

---

## 安全审查

所有生成的内容都会经过安全审查：

### 过滤内容
- 暴力、打斗、血腥
- 恐怖、惊悚元素
- 不当语言、歧视
- 成人话题

### 正向引导
- 性别平等
- 文化多样性
- 品德教育
- 环保意识

### 安全评分
- **0.0-0.3**: 严重不合格
- **0.3-0.7**: 不合格
- **0.7-0.85**: 基本合格
- **0.85-1.0**: 优秀（通过）

---

## 开发工具

### Swagger UI

访问 `http://localhost:8000/api/docs` 查看交互式 API 文档。

### ReDoc

访问 `http://localhost:8000/api/redoc` 查看 ReDoc 风格文档。

### OpenAPI Schema

访问 `http://localhost:8000/api/openapi.json` 获取 OpenAPI 规范文件。

---

## 快速开始

### 1. 启动服务

```bash
cd backend
source venv/bin/activate
uvicorn src.main:app --reload --port 8000
```

### 2. 测试画作转故事

```bash
curl -X POST "http://localhost:8000/api/v1/image-to-story" \
  -F "image=@drawing.png" \
  -F "child_id=child_001" \
  -F "age_group=6-8"
```

### 3. 测试互动故事

```bash
# 开始故事
curl -X POST "http://localhost:8000/api/v1/story/interactive/start" \
  -H "Content-Type: application/json" \
  -d '{"child_id": "child_001", "age_group": "6-8", "interests": ["恐龙"]}'

# 选择分支
curl -X POST "http://localhost:8000/api/v1/story/interactive/{session_id}/choose" \
  -H "Content-Type: application/json" \
  -d '{"choice_id": "choice_0_a"}'
```

---

## 环境变量

| 变量名 | 必需 | 描述 |
|--------|------|------|
| `ANTHROPIC_API_KEY` | 是 | Anthropic API 密钥 |
| `OPENAI_API_KEY` | 是 | OpenAI API 密钥（TTS） |
| `FRONTEND_URL` | 否 | 前端 URL（CORS） |

---

## 相关文档

- [PRD.md](../../docs/PRD.md) - 产品需求文档
- [ARCHITECTURE.md](../../docs/ARCHITECTURE.md) - 技术架构文档
- [DOMAIN.md](../../docs/DOMAIN.md) - 领域背景文档
