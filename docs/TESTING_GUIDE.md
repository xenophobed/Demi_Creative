# API 接口测试指南

完整的 API 接口测试步骤和验证方法

## 目录

1. [环境准备](#环境准备)
2. [基础测试](#基础测试)
3. [功能测试](#功能测试)
4. [错误处理测试](#错误处理测试)
5. [性能测试](#性能测试)

---

## 环境准备

### 1. 安装依赖

```bash
cd /Users/xenodennis/Fun/python101/projects/claude_code/creative_agent/backend
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cd ..
cp .env.example .env
# 编辑 .env 文件，添加以下内容：
# ANTHROPIC_API_KEY=your_key_here
# OPENAI_API_KEY=your_key_here
```

### 3. 启动服务

在一个终端窗口中：

```bash
cd /Users/xenodennis/Fun/python101/projects/claude_code/creative_agent
python3 -m backend.src.main
```

服务将在 http://localhost:8000 启动

---

## 基础测试

### 测试 1: 健康检查

#### 测试根路径

```bash
curl http://localhost:8000/
```

**预期响应** (200 OK):
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-01-28T...",
  "services": {
    "api": "running",
    "session_manager": "running"
  }
}
```

#### 测试健康端点

```bash
curl http://localhost:8000/health
```

**预期响应** (200 OK):
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-01-28T...",
  "services": {
    "api": "running",
    "session_manager": "running",
    "environment": "configured"
  }
}
```

**验证点**:
- ✅ 状态码为 200
- ✅ status 字段存在且为 "healthy" 或 "degraded"
- ✅ 所有服务状态正常
- ✅ 返回当前时间戳

---

### 测试 2: API 文档

#### 访问 Swagger UI

```bash
# 在浏览器中打开
open http://localhost:8000/api/docs
```

**验证点**:
- ✅ 页面加载成功
- ✅ 显示所有 API 端点
- ✅ 可以展开查看详细信息
- ✅ 包含请求/响应示例

#### 访问 ReDoc

```bash
# 在浏览器中打开
open http://localhost:8000/api/redoc
```

**验证点**:
- ✅ 页面加载成功
- ✅ 文档格式清晰
- ✅ 包含所有端点说明

#### 获取 OpenAPI 规范

```bash
curl http://localhost:8000/api/openapi.json | python3 -m json.tool
```

**验证点**:
- ✅ 返回有效的 JSON
- ✅ 包含 openapi、info、paths 字段
- ✅ 版本号正确

---

## 功能测试

### 测试 3: 互动故事 - 开始故事

#### 创建测试请求

```bash
curl -X POST http://localhost:8000/api/v1/story/interactive/start \
  -H "Content-Type: application/json" \
  -d '{
    "child_id": "test_child_001",
    "age_group": "6-8",
    "interests": ["动物", "冒险"],
    "theme": "森林探险",
    "voice": "fable",
    "enable_audio": true
  }'
```

**预期响应** (201 Created):
```json
{
  "session_id": "uuid-here",
  "story_title": "神秘的冒险之旅",
  "opening": {
    "segment_id": 0,
    "text": "在一个阳光明媚的早晨...",
    "audio_url": null,
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
  "created_at": "2026-01-28T..."
}
```

**验证点**:
- ✅ 状态码为 201
- ✅ 返回有效的 session_id
- ✅ story_title 存在
- ✅ opening 包含文本和选项
- ✅ choices 数组不为空
- ✅ 每个选项有 choice_id、text、emoji

**保存 session_id 供后续测试使用**

---

### 测试 4: 互动故事 - 获取状态

使用上一步获取的 session_id：

```bash
SESSION_ID="your-session-id-here"

curl http://localhost:8000/api/v1/story/interactive/$SESSION_ID/status
```

**预期响应** (200 OK):
```json
{
  "session_id": "uuid-here",
  "status": "active",
  "child_id": "test_child_001",
  "story_title": "神秘的冒险之旅",
  "current_segment": 1,
  "total_segments": 5,
  "choice_history": [],
  "educational_summary": null,
  "created_at": "2026-01-28T...",
  "updated_at": "2026-01-28T...",
  "expires_at": "2026-01-29T..."
}
```

**验证点**:
- ✅ 状态码为 200
- ✅ status 为 "active"
- ✅ child_id 匹配
- ✅ current_segment 为 1（包含开场）
- ✅ choice_history 为空数组
- ✅ expires_at 在未来（24小时后）

---

### 测试 5: 互动故事 - 选择分支

```bash
SESSION_ID="your-session-id-here"

curl -X POST http://localhost:8000/api/v1/story/interactive/$SESSION_ID/choose \
  -H "Content-Type: application/json" \
  -d '{
    "choice_id": "choice_0_a"
  }'
```

**预期响应** (200 OK):
```json
{
  "session_id": "uuid-here",
  "next_segment": {
    "segment_id": 1,
    "text": "故事继续发展...",
    "audio_url": null,
    "choices": [
      {
        "choice_id": "choice_1_a",
        "text": "选项A",
        "emoji": "⭐"
      },
      {
        "choice_id": "choice_1_b",
        "text": "选项B",
        "emoji": "🌟"
      }
    ],
    "is_ending": false
  },
  "choice_history": ["choice_0_a"],
  "progress": 0.2
}
```

**验证点**:
- ✅ 状态码为 200
- ✅ next_segment 存在
- ✅ choice_history 包含刚才的选择
- ✅ progress 在 0-1 之间
- ✅ 如果不是结局，choices 不为空

---

### 测试 6: 完整故事流程

继续选择直到结局：

```bash
# 选择第二次
curl -X POST http://localhost:8000/api/v1/story/interactive/$SESSION_ID/choose \
  -H "Content-Type: application/json" \
  -d '{"choice_id": "choice_1_a"}'

# 选择第三次
curl -X POST http://localhost:8000/api/v1/story/interactive/$SESSION_ID/choose \
  -H "Content-Type: application/json" \
  -d '{"choice_id": "choice_2_a"}'

# 继续直到 is_ending: true
```

**最终验证**:

```bash
curl http://localhost:8000/api/v1/story/interactive/$SESSION_ID/status
```

**预期**:
- ✅ status 为 "completed"
- ✅ educational_summary 存在
- ✅ choice_history 包含所有选择
- ✅ current_segment 等于 total_segments

---

### 测试 7: 画作转故事 (需要图片)

#### 准备测试图片

创建一个测试图片或使用现有图片：

```bash
# 使用 Python 创建测试图片
python3 -c "
from PIL import Image
img = Image.new('RGB', (400, 300), color='lightblue')
from PIL import ImageDraw
draw = ImageDraw.Draw(img)
draw.ellipse([50, 50, 150, 150], fill='yellow')  # 太阳
draw.rectangle([200, 200, 250, 280], fill='brown')  # 树
img.save('/tmp/test_drawing.png')
print('测试图片已创建: /tmp/test_drawing.png')
"
```

#### 上传画作

```bash
curl -X POST http://localhost:8000/api/v1/image-to-story \
  -F "image=@/tmp/test_drawing.png" \
  -F "child_id=test_child_002" \
  -F "age_group=6-8" \
  -F "interests=自然,动物" \
  -F "voice=nova" \
  -F "enable_audio=true"
```

**注意**: 此端点需要真实的 Agent 调用，可能需要配置 API keys

**预期响应** (201 Created):
```json
{
  "story_id": "uuid-here",
  "story": {
    "text": "从前有一个...",
    "word_count": 350,
    "age_adapted": true
  },
  "audio_url": "...",
  "educational_value": {
    "themes": ["..."],
    "concepts": ["..."],
    "moral": "..."
  },
  "characters": [...],
  "analysis": {...},
  "safety_score": 0.95,
  "created_at": "2026-01-28T..."
}
```

---

## 错误处理测试

### 测试 8: 无效年龄组

```bash
curl -X POST http://localhost:8000/api/v1/story/interactive/start \
  -H "Content-Type: application/json" \
  -d '{
    "child_id": "test_child",
    "age_group": "invalid",
    "interests": ["动物"]
  }'
```

**预期响应** (422 Unprocessable Entity):
```json
{
  "error": "ValidationError",
  "message": "请求参数验证失败",
  "details": [
    {
      "field": "body.age_group",
      "message": "...",
      "code": "..."
    }
  ],
  "timestamp": "2026-01-28T..."
}
```

**验证点**:
- ✅ 状态码为 422
- ✅ error 为 "ValidationError"
- ✅ details 数组包含错误信息

---

### 测试 9: 缺少必填字段

```bash
curl -X POST http://localhost:8000/api/v1/story/interactive/start \
  -H "Content-Type: application/json" \
  -d '{
    "child_id": "test_child"
  }'
```

**预期响应** (422):
```json
{
  "error": "ValidationError",
  "message": "请求参数验证失败",
  "details": [
    {
      "field": "body.age_group",
      "message": "Field required",
      "code": "missing"
    },
    {
      "field": "body.interests",
      "message": "Field required",
      "code": "missing"
    }
  ],
  "timestamp": "..."
}
```

**验证点**:
- ✅ 状态码为 422
- ✅ details 列出所有缺失字段

---

### 测试 10: 不存在的会话

```bash
curl http://localhost:8000/api/v1/story/interactive/nonexistent_id/status
```

**预期响应** (404 Not Found):
```json
{
  "detail": "会话不存在"
}
```

**验证点**:
- ✅ 状态码为 404
- ✅ 错误消息清晰

---

### 测试 11: 已完成的会话继续选择

```bash
# 先获取一个已完成的会话 ID
# 然后尝试继续选择

curl -X POST http://localhost:8000/api/v1/story/interactive/$COMPLETED_SESSION_ID/choose \
  -H "Content-Type: application/json" \
  -d '{"choice_id": "choice_x_a"}'
```

**预期响应** (400 Bad Request):
```json
{
  "detail": "会话已completed，无法继续"
}
```

**验证点**:
- ✅ 状态码为 400
- ✅ 错误消息说明原因

---

### 测试 12: 兴趣标签过多

```bash
curl -X POST http://localhost:8000/api/v1/story/interactive/start \
  -H "Content-Type: application/json" \
  -d '{
    "child_id": "test_child",
    "age_group": "6-8",
    "interests": ["动物", "冒险", "太空", "科学", "音乐", "运动"]
  }'
```

**预期响应** (422):
```json
{
  "error": "ValidationError",
  "message": "请求参数验证失败",
  "details": [
    {
      "field": "body.interests",
      "message": "兴趣标签数量必须在1-5之间",
      "code": "value_error"
    }
  ],
  "timestamp": "..."
}
```

---

## 性能测试

### 测试 13: 并发请求

使用 Apache Bench 或类似工具：

```bash
# 安装 ab (如果没有)
# brew install httpd

# 并发测试健康检查端点
ab -n 100 -c 10 http://localhost:8000/health
```

**关注指标**:
- Requests per second
- Time per request
- Failed requests (should be 0)

### 测试 14: 响应时间

```bash
# 测量响应时间
curl -w "Time: %{time_total}s\n" -o /dev/null -s http://localhost:8000/health
```

**预期**:
- ✅ 健康检查 < 100ms
- ✅ 互动故事开始 < 2s
- ✅ 选择分支 < 1s

---

## 自动化测试

### 使用 pytest

```bash
cd /Users/xenodennis/Fun/python101/projects/claude_code/creative_agent

# 运行所有测试
pytest tests/ -v

# 运行 API 测试
pytest tests/api/ -v

# 运行集成测试
pytest tests/integration/ -v

# 生成覆盖率报告
pytest tests/ --cov=backend/src --cov-report=html
```

### 使用自定义测试脚本

```bash
python3 run_tests.py
```

---

## 测试检查清单

### 基础功能
- [ ] 健康检查端点正常
- [ ] API 文档可访问
- [ ] OpenAPI 规范有效

### 互动故事
- [ ] 开始故事成功
- [ ] 获取状态正常
- [ ] 选择分支有效
- [ ] 完整流程无错误
- [ ] 会话正确保存

### 画作转故事
- [ ] 文件上传成功
- [ ] 图片验证正确
- [ ] 故事生成正常
- [ ] 响应格式正确

### 错误处理
- [ ] 无效参数被拒绝
- [ ] 缺失字段被检测
- [ ] 不存在资源返回 404
- [ ] 验证器正确工作
- [ ] 错误消息清晰

### 性能
- [ ] 响应时间合理
- [ ] 并发请求稳定
- [ ] 无内存泄漏

---

## 故障排查

### 问题 1: 服务无法启动

**症状**: `python3 -m backend.src.main` 失败

**解决**:
1. 检查依赖是否安装: `pip list | grep fastapi`
2. 检查端口是否被占用: `lsof -i :8000`
3. 检查环境变量: `cat .env`

### 问题 2: 测试失败

**症状**: pytest 测试失败

**解决**:
1. 确保服务未运行（测试会启动自己的实例）
2. 清理测试数据: `rm -rf data/test_sessions`
3. 检查依赖版本: `pip list`

### 问题 3: API 返回 500

**症状**: 内部服务器错误

**解决**:
1. 查看服务日志
2. 检查 MCP Tools 是否正确初始化
3. 验证 API keys 是否配置

---

## 下一步

测试通过后，可以：

1. **部署到生产环境**
   - 配置 HTTPS
   - 设置负载均衡
   - 启用日志记录

2. **前端集成**
   - React 组件开发
   - API 客户端封装
   - 用户界面设计

3. **监控和告警**
   - 设置健康检查
   - 配置错误追踪
   - 性能监控

---

**文档版本**: 1.0.0
**最后更新**: 2026-01-28
