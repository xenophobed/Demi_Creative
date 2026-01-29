# 儿童创意工坊 | Kids Creative Workshop

> 基于 Claude Agent SDK 的儿童内容创作平台

## 项目简介

儿童创意工坊是一个 AI 驱动的创意内容生成平台，利用 Claude Agent 技术为 3-12 岁儿童提供：
- 🎨 **画作转故事**: 将儿童画作转化为个性化故事
- 📖 **互动故事**: 多分支选择，儿童参与创作
- 📰 **新闻儿童化**: 将成人新闻转化为适合儿童的资讯
- 🛡️ **安全保障**: 严格的内容安全审查和价值观引导

## 核心特色

### 1. Agent-First 架构
- 以 AI Agent 为核心，不是传统 CRUD 应用
- Agent 自主推理、决策、使用工具
- Contract 即 Skill，TDD 驱动开发

### 2. Contract-Driven Development
```python
# 1. 定义契约
class ImageAnalysisInput(BaseModel):
    image_url: str
    child_age: int = Field(ge=3, le=12)

# 2. 契约作为 Agent Skill
agent = ImageAnalysisAgent(
    skills=[
        ContractSkill(ImageAnalysisInput, ImageAnalysisResult),
        VisionAnalysisSkill(),
        VectorSearchSkill()
    ]
)

# 3. Agent 自动验证输入输出
result = await agent.run(input_data)  # 符合契约才能通过
```

### 3. 简化的存储设计
- JSON 文件存储用户数据和配置
- Qdrant 本地向量数据库（记忆系统）
- 避免复杂的关系型数据库

## 文档结构

| 文档 | 内容 | 阅读顺序 |
|------|------|----------|
| [DOMAIN.md](DOMAIN.md) | 领域背景、核心概念、业务规则 | 1️⃣ 必读 |
| [PRD.md](PRD.md) | 产品功能定义、用户场景 | 2️⃣ 产品人员 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 技术架构、Agent 设计、TDD 流程 | 3️⃣ 开发人员 |
| [README.md](README.md) | 项目简介、快速开始 | 0️⃣ 这里 |

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
cd creative_agent

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r backend/requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
# Claude API
ANTHROPIC_API_KEY=your_api_key_here

# OpenAI TTS (可选)
OPENAI_API_KEY=your_api_key_here

# 向量数据库（本地 Qdrant）
QDRANT_PATH=./data/vectors
```

### 3. 运行契约测试

```bash
# 运行所有契约测试（TDD 第一步）
pytest tests/contracts/ -v

# 预期结果：部分测试失败（Agent 还未实现）
# ❌ test_image_analysis_agent - FAILED
# ❌ test_story_generator_agent - FAILED
# ✅ test_contract_models - PASSED
```

### 4. 启动开发环境

```bash
# 启动本地向量数据库
docker run -d -p 6333:6333 qdrant/qdrant

# 启动 FastAPI 开发服务器
uvicorn src.main:app --reload --port 8000

# 访问 API 文档
open http://localhost:8000/docs
```

## 开发工作流（TDD）

```
┌─────────────────────────────────────────────────────────┐
│ Step 1: 定义契约                                        │
│   编写 tests/contracts/logic_contract.py               │
│   定义 Pydantic 模型（输入/输出）                       │
└───────────────────────┬─────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ Step 2: 运行测试（RED）                                 │
│   pytest tests/contracts/ -v                            │
│   预期失败：Agent 还未实现                              │
└───────────────────────┬─────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ Step 3: 实现 Skills                                     │
│   编写 src/skills/vision_analysis_skill.py             │
│   实现 execute() 和 to_claude_tool()                   │
└───────────────────────┬─────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ Step 4: 实现 Agent                                      │
│   编写 src/agents/image_analysis_agent.py              │
│   使用 ContractSkill 验证输入输出                      │
└───────────────────────┬─────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ Step 5: 运行测试（GREEN）                               │
│   pytest tests/contracts/ -v                            │
│   ✅ 所有测试通过                                       │
└───────────────────────┬─────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ Step 6: 重构（REFACTOR）                                │
│   优化代码，保持测试通过                                │
└─────────────────────────────────────────────────────────┘
```

## 示例：实现 ImageAnalysisAgent

### 1. 定义契约
```python
# tests/contracts/logic_contract.py

class ImageAnalysisInput(BaseModel):
    image_url: str
    child_id: str
    child_age: int = Field(ge=3, le=12)

class ImageAnalysisResult(BaseModel):
    objects: List[str]
    scene: str
    mood: str
    confidence_score: float = Field(ge=0.0, le=1.0)

def test_image_analysis_agent():
    """测试画作分析 Agent 契约"""
    input_data = ImageAnalysisInput(
        image_url="https://example.com/image.jpg",
        child_id="user_123",
        child_age=7
    )
    # 预期：Agent 返回符合 ImageAnalysisResult 的数据
```

### 2. 实现 Agent
```python
# src/agents/image_analysis_agent.py

from tests.contracts.logic_contract import ImageAnalysisInput, ImageAnalysisResult

class ImageAnalysisAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="ImageAnalysisAgent",
            system_prompt="""你是一个儿童画作分析专家。
            使用 vision_analyze skill 分析画作，
            使用 contract_validator 验证输出。
            """,
            skills=[
                ContractSkill(ImageAnalysisInput, ImageAnalysisResult),
                VisionAnalysisSkill(),
                VectorSearchSkill()
            ]
        )
```

### 3. 运行测试
```bash
pytest tests/contracts/logic_contract.py::test_image_analysis_agent -v
# ✅ PASSED
```

## API 使用示例

### 画作转故事
```bash
curl -X POST http://localhost:8000/api/v1/image-to-story \
  -F "image=@/path/to/drawing.jpg" \
  -F "child_age=7" \
  -F "interests=动物,冒险"
```

响应：
```json
{
  "story": "闪电小狗今天又来到了它最喜欢的公园...",
  "audio_url": "http://localhost:8000/audio/story_123.mp3",
  "image_analysis": {
    "objects": ["小狗", "树木", "太阳"],
    "scene": "户外公园",
    "mood": "快乐"
  },
  "safety_score": 0.95
}
```

### 互动故事
```bash
# 开始互动故事
curl -X POST http://localhost:8000/api/v1/story/interactive/start \
  -H "Content-Type: application/json" \
  -d '{
    "child_id": "user_123",
    "child_age": 8,
    "interests": ["恐龙", "科学"],
    "mode": "interactive"
  }'
```

响应：
```json
{
  "story_text": "小恐龙在森林里发现了一个神秘的山洞...",
  "choices": [
    {"id": "choice-1", "text": "勇敢地走进去", "emoji": "🏔️"},
    {"id": "choice-2", "text": "先回家叫朋友", "emoji": "👫"}
  ],
  "session_id": "session_abc123",
  "is_ending": false
}
```

```bash
# 做出选择，继续故事
curl -X POST http://localhost:8000/api/v1/story/interactive/session_abc123/choose \
  -H "Content-Type: application/json" \
  -d '{"choice_id": "choice-1"}'
```

## 项目结构

```
creative_agent/
├── DOMAIN.md                   # 领域背景文档
├── PRD.md                      # 产品需求文档
├── ARCHITECTURE.md             # 技术架构文档
├── README.md                   # 项目简介（本文档）
│
├── src/                        # 源代码
│   ├── agents/                # Agent 实现
│   │   ├── __init__.py
│   │   ├── base_agent.py      # Agent 基类
│   │   ├── image_analysis_agent.py
│   │   ├── story_generator_agent.py
│   │   ├── news_converter_agent.py
│   │   └── safety_agent.py
│   │
│   ├── skills/                # Skill 实现
│   │   ├── __init__.py
│   │   ├── contract_skill.py  # 契约验证技能
│   │   ├── vision_analysis_skill.py
│   │   ├── vector_search_skill.py
│   │   ├── tts_generator_skill.py
│   │   └── age_adapter_skill.py
│   │
│   ├── api/                   # FastAPI 路由
│   │   ├── __init__.py
│   │   └── main.py
│   │
│   └── utils/                 # 工具函数
│       ├── __init__.py
│       └── storage.py         # JSON 文件存储
│
├── tests/                     # 测试文件
│   └── contracts/             # 契约测试（TDD 核心）
│       ├── __init__.py
│       ├── logic_contract.py  # 业务逻辑契约
│       ├── data_contract.py   # 数据契约
│       └── system_contract.py # 系统集成契约
│
├── data/                      # 数据存储（本地）
│   ├── users/                 # 用户数据（JSON）
│   ├── content/               # 内容数据（JSON）
│   └── vectors/               # 向量数据（Qdrant）
│
└── tools/                     # 开发工具
    └── generate_skills.py     # 从契约生成 Skills
```

## 技术栈

### 核心
- **Python 3.11+**: 语言
- **Claude Agent SDK**: AI Agent 框架
- **FastAPI**: 轻量级 API 层
- **Pydantic**: 数据验证和契约定义

### AI & 存储
- **Claude API**: GPT-4 级别的 AI 能力
- **OpenAI TTS**: 语音合成
- **Qdrant**: 本地向量数据库

### 开发工具
- **pytest**: 测试框架
- **structlog**: 结构化日志
- **black**: 代码格式化
- **mypy**: 类型检查

## 关键概念

### Agent
自主的智能实体，能够：
- 感知输入（接收任务）
- 推理决策（选择使用哪些 Skills）
- 执行动作（调用 Skills 完成任务）
- 验证输出（使用 ContractSkill 确保符合规范）

### Skill
Agent 可以使用的工具，分为三类：
1. **Contract Skill**: 验证输入输出（自动从 Pydantic 模型生成）
2. **Integration Skill**: 调用外部服务（Claude Vision、TTS 等）
3. **Business Skill**: 执行业务逻辑（年龄适配、分支生成等）

### Contract
使用 Pydantic 模型定义的输入输出规范，同时作为：
- 测试用例（TDD）
- Agent Skill（运行时验证）
- API 文档（自动生成）

## 开发规范

### 代码风格
```bash
# 格式化代码
black src/ tests/

# 类型检查
mypy src/

# 运行测试
pytest tests/ -v --cov=src
```

### 提交规范
```
feat: 添加画作分析 Agent
fix: 修复契约验证错误
docs: 更新架构文档
test: 添加故事生成契约测试
```

## 部署

### 本地开发
```bash
# 启动 Qdrant
docker run -d -p 6333:6333 qdrant/qdrant

# 启动 API
uvicorn src.main:app --reload
```

### 生产部署
```bash
# 使用 Docker Compose
docker-compose up -d

# 数据持久化到 ./data 目录
```

## 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. **编写契约测试** (TDD 第一步！)
4. 实现功能
5. 运行测试 (`pytest tests/`)
6. 提交代码 (`git commit -m 'feat: Add AmazingFeature'`)
7. Push 到分支 (`git push origin feature/AmazingFeature`)
8. 创建 Pull Request

## 常见问题

### Q: 为什么不用传统数据库？
A: 本项目核心是 Agent，不是 CRUD。使用 JSON + 向量数据库更轻量，部署简单。

### Q: Contract as Skill 是什么意思？
A: 契约测试不仅是测试，还会转化为 Agent 的 Skill。Agent 在运行时使用 ContractSkill 验证输入输出，确保符合规范。

### Q: 如何添加新的 Agent？
A:
1. 在 `tests/contracts/logic_contract.py` 定义输入输出契约
2. 运行测试（应该失败）
3. 在 `src/agents/` 实现 Agent
4. 运行测试（应该通过）

### Q: 向量数据库用来做什么？
A: 实现"记忆系统"，记住儿童的画作历史、故事偏好，实现角色连续性。

## 许可证

MIT License

## 联系方式

- 项目负责人: [Your Name]
- 邮箱: your.email@example.com
- 问题反馈: [GitHub Issues](https://github.com/your-repo/issues)

---

**⭐ 如果你觉得这个项目有趣，请给个 Star！**
