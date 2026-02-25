# 儿童创意工坊 - 技术架构 V2（基于正确的 Agent SDK 理解）

> **重要更新**: 本架构基于 Claude Agent SDK 的正确理解重新设计

---

## 核心架构变更

### ❌ 之前的错误理解

```python
# 错误：自己实现 Agent 基类和工具执行循环
class BaseAgent:
    async def run(self, input_data):
        # 手动管理工具调用...
        while response.stop_reason == "tool_use":
            # 手动处理...
```

### ✅ 正确的 Agent SDK 使用方式

```python
# 正确：SDK 自动处理执行循环
from claude_agent_sdk import query, ClaudeAgentOptions

async for message in query(
    prompt="分析这幅儿童画作并生成故事",
    options=ClaudeAgentOptions(
        allowed_tools=["Read", "mcp__vision__analyze"],
        mcp_servers={...}
    )
):
    # SDK 自动处理工具调用
    if isinstance(message, ResultMessage):
        print(message.result)
```

---

## 1. 正确的架构设计

### 1.0 Artifact Graph（新增）

Artifact 系统采用 Story 容器 + Artifact 一等实体的混合模型，详细设计见：

- [ARTIFACT_GRAPH_MODEL.md](./ARTIFACT_GRAPH_MODEL.md)

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                   FastAPI (Web API)                     │
│  - 接收用户请求（画作、故事需求）                        │
│  - 返回生成结果                                          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────┐
│              Agent Orchestrator (调度层)                │
│  - 创建 Agent 任务                                      │
│  - 配置 ClaudeAgentOptions                             │
│  - 处理 Agent 消息流                                    │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────┐
│            Claude Agent SDK (核心引擎)                  │
│  - 自动管理工具执行循环                                 │
│  - 调用 MCP Tools                                       │
│  - 调用 Skills                                          │
└───────┬─────────────────┬────────────────┬──────────────┘
        │                 │                │
        ↓                 ↓                ↓
   ┌─────────┐      ┌──────────┐    ┌──────────┐
   │  Built  │      │   MCP    │    │  Skills  │
   │  -in    │      │  Tools   │    │ (.claude/│
   │  Tools  │      │(External)│    │  skills/)│
   └─────────┘      └──────────┘    └──────────┘
```

### 1.2 关键概念对应关系

| 需求 | 实现方式 | Claude SDK 概念 |
|------|---------|----------------|
| 画作分析 | MCP Tool (Vision API) | `mcp__vision__analyze` |
| 故事生成 | Agent Prompt + Skills | `.claude/skills/story-generation/` |
| 向量搜索 | MCP Tool (ChromaDB) | `mcp__vector-search__search_similar_drawings` |
| 内容安全审查 | Custom MCP Tool | SDK MCP Server |
| 年龄适配 | Skill (Markdown) | `.claude/skills/age-adapter/` |
| TTS 生成 | MCP Tool (OpenAI) | `mcp__openai__tts` |

---

## 2. MCP Tools 设计

### 2.1 Vision Analysis MCP Server

```python
# src/mcp_servers/vision_analysis_server.py
from claude_agent_sdk import tool, create_sdk_mcp_server
from anthropic import Anthropic
from typing import Any
import base64

@tool(
    name="analyze_children_drawing",
    description="""分析儿童画作，识别物体、场景和情绪。

    使用场景：
    - 儿童上传画作后，分析画作内容
    - 识别画中的主要元素（动物、人物、物体）
    - 判断画作的场景（室内/户外、白天/夜晚）
    - 识别情绪氛围（快乐、兴奋、平静）

    返回：
    - objects: 识别出的物体列表
    - scene: 场景描述
    - mood: 情绪/氛围
    - colors: 主要颜色
    """,
    input_schema={
        "image_path": {"type": "string", "description": "图片文件路径"}
    }
)
async def analyze_children_drawing(args: dict[str, Any]) -> dict[str, Any]:
    """分析儿童画作"""
    client = Anthropic()

    # 读取图片并转为 base64
    with open(args['image_path'], 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')

    # 调用 Claude Vision API
    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_data
                    }
                },
                {
                    "type": "text",
                    "text": """请分析这幅儿童画作：
                    1. 列出画中的所有物体（动物、人物、植物、物品）
                    2. 描述场景（室内/户外、地点）
                    3. 识别情绪氛围（快乐、兴奋、平静、好奇等）
                    4. 主要颜色

                    请以 JSON 格式返回：
                    {
                        "objects": ["物体1", "物体2"],
                        "scene": "场景描述",
                        "mood": "情绪",
                        "colors": ["颜色1", "颜色2"]
                    }
                    """
                }
            ]
        }]
    )

    # 解析返回的 JSON
    import json
    result = json.loads(response.content[0].text)

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(result, ensure_ascii=False, indent=2)
        }]
    }


# 创建 Vision MCP Server
vision_server = create_sdk_mcp_server(
    name="vision-analysis",
    version="1.0.0",
    tools=[analyze_children_drawing]
)
```

### 2.2 Vector Search MCP Server

```python
# src/mcp_servers/vector_search_server.py
from claude_agent_sdk import tool, create_sdk_mcp_server
import chromadb
from typing import Any
import json

@tool(
    name="search_similar_drawings",
    description="""在向量数据库中搜索相似的儿童画作。

    使用场景：
    - 查找儿童之前画过的相似作品
    - 识别重复出现的角色（如"闪电小狗"）
    - 分析儿童的创作主题偏好

    返回：
    - 相似画作列表（包含相似度分数）
    - 每个画作的描述信息
    """,
    input_schema={
        "drawing_description": {"type": "string", "description": "画作描述（用于生成查询向量）"},
        "user_id": {"type": "string", "description": "用户ID"},
        "top_k": {"type": "integer", "description": "返回结果数量", "default": 5}
    }
)
async def search_similar_drawings(args: dict[str, Any]) -> dict[str, Any]:
    """搜索相似画作"""
    client = chromadb.PersistentClient(path="./data/vectors")

    # 生成查询向量（使用 Claude 的嵌入功能）
    from anthropic import Anthropic
    anthropic = Anthropic()

    # 注意：实际需要使用嵌入模型生成向量
    # 这里简化处理
    query_vector = [0.1] * 1024  # 实际应该从 embedding model 获取

    # 在向量数据库中搜索
    results = client.search(
        collection_name="children_drawings",
        query_vector=query_vector,
        limit=args.get('top_k', 5),
        query_filter={
            "must": [
                {"key": "user_id", "match": {"value": args['user_id']}}
            ]
        }
    )

    # 格式化结果
    similar_drawings = []
    for hit in results:
        similar_drawings.append({
            "id": hit.id,
            "score": hit.score,
            "objects": hit.payload.get("objects", []),
            "scene": hit.payload.get("scene", ""),
            "created_at": hit.payload.get("created_at", "")
        })

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(similar_drawings, ensure_ascii=False, indent=2)
        }]
    }


# 创建 Vector Search MCP Server
vector_server = create_sdk_mcp_server(
    name="vector-search",
    version="1.0.0",
    tools=[search_similar_drawings]
)
```

### 2.3 Safety Check MCP Server

```python
# src/mcp_servers/safety_check_server.py
from claude_agent_sdk import tool, create_sdk_mcp_server
from anthropic import Anthropic
from typing import Any
import json

@tool(
    name="check_content_safety",
    description="""检查内容是否适合儿童（3-12岁）。

    检查维度：
    1. 负面内容：暴力、恐怖、不当语言
    2. 价值观：性别平等、文化多样性
    3. 适龄性：是否符合目标年龄

    返回：
    - is_safe: 是否安全
    - safety_score: 安全分数 (0-1)
    - issues: 发现的问题列表
    - suggestions: 修改建议
    """,
    input_schema={
        "content": {"type": "string", "description": "待检查的内容"},
        "target_age": {"type": "integer", "description": "目标年龄（3-12）"}
    }
)
async def check_content_safety(args: dict[str, Any]) -> dict[str, Any]:
    """安全检查"""
    client = Anthropic()

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system="""你是儿童内容安全审查专家。

审查标准：

【禁止内容】：
- 暴力：打斗、血腥、武器
- 恐怖：鬼怪、黑暗、惊悚
- 不当语言：脏话、侮辱、歧视
- 成人话题：性、毒品、政治争议

【价值观检查】：
- 性别平等：避免刻板印象（如医生总是男性）
- 文化多样性：展现不同文化、种族背景
- 品德教育：友谊、勇气、诚实、同理心

请评估内容并返回 JSON：
{
    "is_safe": true/false,
    "safety_score": 0.0-1.0,
    "issues": [
        {
            "category": "violence/gender_bias/...",
            "severity": "low/medium/high",
            "description": "具体问题描述"
        }
    ],
    "suggestions": ["修改建议1", "修改建议2"]
}

评分标准：
- < 0.7: 不通过
- 0.7-0.85: 警告
- > 0.85: 通过
""",
        messages=[{
            "role": "user",
            "content": f"目标年龄：{args['target_age']}岁\n\n待检查内容：\n{args['content']}"
        }]
    )

    result = json.loads(response.content[0].text)

    return {
        "content": [{
            "type": "text",
            "text": json.dumps(result, ensure_ascii=False, indent=2)
        }]
    }


# 创建 Safety Check MCP Server
safety_server = create_sdk_mcp_server(
    name="safety-check",
    version="1.0.0",
    tools=[check_content_safety]
)
```

### 2.4 TTS Generation MCP Server

```python
# src/mcp_servers/tts_server.py
from claude_agent_sdk import tool, create_sdk_mcp_server
from openai import OpenAI
from typing import Any
import hashlib
import os

@tool(
    name="generate_story_audio",
    description="""将故事文本转为语音音频。

    支持的声音类型：
    - grandmother: 温柔奶奶
    - child: 调皮小精灵
    - narrator: 旁白叙述者

    返回音频文件路径
    """,
    input_schema={
        "text": {"type": "string", "description": "故事文本"},
        "voice_type": {"type": "string", "enum": ["grandmother", "child", "narrator"], "default": "grandmother"}
    }
)
async def generate_story_audio(args: dict[str, Any]) -> dict[str, Any]:
    """生成故事音频"""
    client = OpenAI()

    # 映射语音类型到 OpenAI TTS 声音
    voice_map = {
        "grandmother": "nova",      # 温柔女声
        "child": "shimmer",         # 活泼女声
        "narrator": "onyx"          # 稳重男声
    }

    voice = voice_map.get(args.get('voice_type', 'grandmother'), 'nova')

    # 生成音频
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=args['text']
    )

    # 保存音频文件
    text_hash = hashlib.md5(args['text'].encode()).hexdigest()
    audio_path = f"./data/audio/story_{text_hash}.mp3"
    os.makedirs(os.path.dirname(audio_path), exist_ok=True)

    response.stream_to_file(audio_path)

    return {
        "content": [{
            "type": "text",
            "text": f"音频已生成：{audio_path}"
        }]
    }


# 创建 TTS MCP Server
tts_server = create_sdk_mcp_server(
    name="tts-generation",
    version="1.0.0",
    tools=[generate_story_audio]
)
```

---

## 3. Skills 设计

### 3.1 Story Generation Skill

```markdown
<!-- .claude/skills/story-generation/SKILL.md -->
---
description: "为儿童创作适龄的个性化故事"
allowed_tools:
  - "Read"
  - "mcp__vision__analyze_children_drawing"
  - "mcp__vector__search_similar_drawings"
  - "mcp__safety__check_content_safety"
  - "mcp__tts__generate_story_audio"
---

# Story Generation Skill

你是一个专业的儿童故事作家，擅长根据儿童画作和兴趣创作故事。

## 工作流程

当用户要求"将画作转为故事"时，按以下步骤执行：

### 1. 分析画作
使用 `analyze_children_drawing` 工具分析画作：
- 识别画中的物体、人物、动物
- 理解场景（室内/户外、时间）
- 感知情绪氛围

### 2. 搜索历史
使用 `search_similar_drawings` 工具查找相似画作：
- 识别重复出现的角色（如"闪电小狗"）
- 了解孩子的创作偏好
- 保持故事连续性

### 3. 创作故事
根据分析结果创作故事，遵循以下规则：

**年龄适配**：
- 3-5岁：简单句子，100-200字，明确结局
- 6-8岁：复杂句子，200-400字，可以有小转折
- 9-12岁：丰富修辞，400-800字，可以开放式结局

**内容要求**：
- 融入画作中的所有主要元素
- 如果有重复角色，保持角色特征一致
- 故事必须正面积极，有教育意义
- 使用儿童能理解的日常词汇

**教育融合**：
- 自然融入品德教育（友谊、勇气、诚实）
- 可以加入 STEAM 元素（科学、数学概念）
- 避免说教，通过故事情节传递价值观

### 4. 安全检查
使用 `check_content_safety` 工具检查故事：
- 确保没有暴力、恐怖、不当内容
- 检查性别平等和文化多样性
- 如果安全分数 < 0.85，修改故事

### 5. 生成语音
使用 `generate_story_audio` 工具生成音频：
- 3-6岁：使用 grandmother 声音（温柔）
- 7-12岁：使用 narrator 声音（旁白）

## 示例输出

```json
{
  "story_title": "闪电小狗的公园冒险",
  "story_text": "闪电小狗今天又来到了它最喜欢的公园。阳光暖暖地照在身上，树叶在微风中沙沙作响。闪电开心地摇着尾巴，突然，它发现草地上有一个亮闪闪的东西...",
  "word_count": 245,
  "reading_time_seconds": 90,
  "educational_points": ["友谊", "好奇心", "分享"],
  "audio_path": "./data/audio/story_abc123.mp3",
  "safety_score": 0.92
}
```

## 注意事项

- 如果画作内容不清晰，询问用户补充信息
- 如果发现重复角色，主动提及："这是你的老朋友闪电小狗！"
- 故事长度根据年龄调整，不要超出限制
- 所有故事必须有明确的结局（3-8岁）或启发性结尾（9-12岁）
```

### 3.2 Interactive Story Skill

```markdown
<!-- .claude/skills/interactive-story/SKILL.md -->
---
description: "创作多分支互动故事，让儿童参与选择"
allowed_tools:
  - "Read"
  - "Write"
  - "mcp__vector__search_similar_drawings"
  - "mcp__safety__check_content_safety"
  - "mcp__tts__generate_story_audio"
---

# Interactive Story Skill

你是一个互动故事设计专家，擅长创作"选择你的冒险"式儿童故事。

## 互动故事规则

### 决策点设置
- 每个故事 2-4 个决策点
- 每 100-150 字设置一个决策点
- 每次提供 2-3 个选项
- **重要**：所有选项都导向"好结局"（不惩罚儿童的选择）

### 选项设计
```
示例：
小恐龙发现了一个神秘山洞，他应该：
A. 勇敢地走进去探险 🏔️
B. 先回家叫上朋友一起来 👫

分析：
- 选项 A：培养勇气，冒险精神
- 选项 B：强调友谊，团队合作
- 两个选项都是正面的，只是侧重点不同
```

### 状态管理

使用 JSON 文件存储会话状态：

```json
{
  "session_id": "session_abc123",
  "user_id": "user_123",
  "child_age": 8,
  "current_segment": 2,
  "choices_history": ["choice-1", "choice-3"],
  "character_state": {
    "小恐龙": {
      "location": "山洞",
      "has_treasure": true,
      "friends": ["小兔子"]
    }
  },
  "story_so_far": "第一段故事...\n第二段故事..."
}
```

## 工作流程

### 开始新故事
1. 接收用户兴趣标签（恐龙、太空等）
2. 使用 `search_similar_drawings` 了解偏好
3. 生成开篇（100-200字）
4. 创建第一个决策点
5. 保存会话状态到 `./data/sessions/session_{id}.json`

### 继续故事
1. 读取会话状态
2. 根据用户选择生成下一段
3. 更新角色状态
4. 创建新决策点或结局
5. 保存更新后的状态

### 结束故事
1. 生成结局（基于所有选择）
2. 总结教育要点
3. 使用 `generate_story_audio` 生成完整音频
4. 删除会话文件

## 示例交互

**Round 1 (开篇)**：
```
小恐龙在森林里发现了一个神秘的山洞，洞口闪烁着奇异的光芒...

你会怎么做？
A. 勇敢地走进去 🏔️ (培养勇气)
B. 先回家叫朋友 👫 (强调友谊)
```

**Round 2 (选择 A 后)**：
```
小恐龙鼓起勇气走进山洞，里面竟然有一块会发光的化石！这时，他听到了脚步声...

接下来：
A. 仔细研究化石 🔬 (科学探索)
B. 藏起来看看是谁 🙈 (谨慎思考)
```

**Round 3-4**: 继续...

**Final (结局)**：
```
小恐龙成功保护了化石，还交到了新朋友小兔子。他们决定一起研究这个神奇的发现！

🎓 你学到了：
- 勇气：面对未知敢于探索
- 友谊：朋友让冒险更有趣
- 科学：保持好奇心，探索世界
```
```

### 3.3 Age Adapter Skill

```markdown
<!-- .claude/skills/age-adapter/SKILL.md -->
---
description: "根据儿童年龄调整语言复杂度和内容深度"
---

# Age Adapter Skill

根据儿童年龄自动调整故事的语言和内容。

## 年龄分组标准

### 3-5岁（学龄前）

**认知特点**：
- 具象思维，需要简单明确的概念
- 注意力集中时间短（10-15分钟）
- 喜欢重复，喜欢熟悉的故事

**语言要求**：
- 简单句子：主谓宾结构，不超过10个字
- 常用词汇：动物、颜色、数字、日常物品
- 重复结构："小狗跑啊跑，跑到了公园"

**故事长度**：100-200字

**示例**：
```
小狗在公园玩。
太阳很大，天空很蓝。
小狗看到了一个球。
小狗很开心，跑去追球。
```

---

### 6-8岁（小学低年级）

**认知特点**：
- 开始逻辑思考
- 好奇心强，喜欢探索
- 能理解简单的因果关系

**语言要求**：
- 复杂句子：可以用形容词和副词
- 词汇量扩展：可以引入新词汇（并解释）
- 适当修辞：比喻、拟人

**故事长度**：200-400字

**示例**：
```
闪电小狗今天特别兴奋，因为主人答应带它去公园。
阳光暖暖地照在身上，就像妈妈温柔的拥抱。
公园里的树叶在微风中沙沙作响，好像在唱歌。
闪电突然发现草地上有一个亮闪闪的东西，
好奇心让它忍不住跑过去看看...
```

---

### 9-12岁（小学高年级）

**认知特点**：
- 抽象思维能力增强
- 开始批判性思考
- 能理解复杂的人际关系

**语言要求**：
- 丰富表达：使用成语、修辞手法
- 复杂情节：可以有多线叙事
- 深度思考：引发思考的开放式问题

**故事长度**：400-800字

**示例**：
```
夕阳的余晖洒在公园的每个角落，给这片熟悉的天地镀上了一层金色。
闪电小狗已经记不清这是第几次来这里了，但每一次，
它都能发现新的惊喜——也许是一只新来的蝴蝶，
也许是一朵刚刚绽放的花。

今天，它的好奇心被草地上一个若隐若现的光点吸引了。
那不是普通的石头，也不是掉落的硬币。
随着它一步步靠近，一个令人兴奋的可能性在它心中升起：
这会是传说中的"星辰之石"吗？

就在这时，身后传来了熟悉的脚步声...
```

## 转换规则

### 词汇替换表

| 复杂词汇 | 3-5岁 | 6-8岁 | 9-12岁 |
|---------|-------|-------|--------|
| 探索 | 看看 | 去找找 | 探索 |
| 勇敢 | 不怕 | 勇敢 | 勇敢 |
| 友谊 | 好朋友 | 友谊 | 友谊 |
| 发现 | 看到 | 发现 | 发现 |
| 神秘 | 奇怪 | 神秘 | 神秘 |

### 句式转换

**原句（9-12岁）**：
"夕阳的余晖洒在公园的每个角落，给这片熟悉的天地镀上了一层金色。"

**转换为 6-8岁**：
"太阳快下山了，公园变成了金黄色，就像披上了金色的衣服。"

**转换为 3-5岁**：
"太阳要回家了。公园变成了黄色的。很好看。"

## 使用方式

在生成故事后，自动检查目标年龄：
1. 如果是 3-5岁，简化句子和词汇
2. 如果是 6-8岁，保持适度复杂度
3. 如果是 9-12岁，可以使用丰富表达
```

---

## 4. Agent 使用示例

### 4.1 画作转故事 Agent

```python
# src/agents/image_to_story.py
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage, AssistantMessage
from src.mcp_servers.vision_analysis_server import vision_server
from src.mcp_servers.vector_search_server import vector_server
from src.mcp_servers.safety_check_server import safety_server
from src.mcp_servers.tts_server import tts_server
import json

async def image_to_story(
    image_path: str,
    child_id: str,
    child_age: int,
    interests: list[str] = None
) -> dict:
    """画作转故事"""

    # 配置 Agent
    options = ClaudeAgentOptions(
        # 配置 MCP Servers
        mcp_servers={
            "vision": vision_server,
            "vector": vector_server,
            "safety": safety_server,
            "tts": tts_server
        },

        # 允许使用的工具
        allowed_tools=[
            "mcp__vision__analyze_children_drawing",
            "mcp__vector__search_similar_drawings",
            "mcp__safety__check_content_safety",
            "mcp__tts__generate_story_audio",
            "Skill"  # 启用 Skills
        ],

        # Skills 配置
        cwd=".",  # 项目根目录
        setting_sources=["user", "project"],  # 从 .claude/skills/ 加载

        # 权限模式
        permission_mode="acceptEdits"  # 自动批准文件读写
    )

    # 创建任务提示词
    prompt = f"""
任务：将儿童画作转化为个性化故事

画作信息：
- 图片路径：{image_path}
- 儿童ID：{child_id}
- 儿童年龄：{child_age}岁
- 兴趣标签：{', '.join(interests) if interests else '未知'}

请使用 Story Generation Skill 完成以下步骤：

1. 分析画作（使用 analyze_children_drawing）
2. 搜索相似历史画作（使用 search_similar_drawings）
3. 创作适龄故事（根据年龄调整语言）
4. 安全检查（使用 check_content_safety）
5. 生成语音（使用 generate_story_audio）

最后返回完整的故事信息（JSON格式）。
"""

    result_data = {}

    # 执行 Agent
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if hasattr(block, 'text'):
                    print(f"[Agent] {block.text}")
                elif hasattr(block, 'name'):
                    print(f"[Tool] {block.name}")

        elif isinstance(message, ResultMessage):
            if message.subtype == "success":
                result_data = json.loads(message.result)
                print(f"\n[Success] 故事生成完成！")

    return result_data


# FastAPI 路由
from fastapi import FastAPI, UploadFile, File
import shutil

app = FastAPI()

@app.post("/api/v1/image-to-story")
async def api_image_to_story(
    image: UploadFile = File(...),
    child_id: str,
    child_age: int,
    interests: str = ""
):
    """画作转故事 API"""

    # 保存上传的图片
    image_path = f"./data/uploads/{image.filename}"
    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    # 调用 Agent
    result = await image_to_story(
        image_path=image_path,
        child_id=child_id,
        child_age=child_age,
        interests=interests.split(',') if interests else None
    )

    return {
        "success": True,
        "data": result
    }
```

### 4.2 互动故事 Agent

```python
# src/agents/interactive_story.py
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage
from src.mcp_servers.vector_search_server import vector_server
from src.mcp_servers.safety_check_server import safety_server
from src.mcp_servers.tts_server import tts_server
import json
import uuid

async def start_interactive_story(
    child_id: str,
    child_age: int,
    interests: list[str]
) -> dict:
    """开始互动故事"""

    session_id = str(uuid.uuid4())

    options = ClaudeAgentOptions(
        mcp_servers={
            "vector": vector_server,
            "safety": safety_server,
            "tts": tts_server
        },
        allowed_tools=[
            "mcp__vector__search_similar_drawings",
            "mcp__safety__check_content_safety",
            "mcp__tts__generate_story_audio",
            "Read", "Write", "Skill"
        ],
        cwd=".",
        setting_sources=["user", "project"],
        permission_mode="acceptEdits"
    )

    prompt = f"""
任务：创建互动故事的开篇

用户信息：
- 儿童ID：{child_id}
- 年龄：{child_age}岁
- 兴趣：{', '.join(interests)}
- 会话ID：{session_id}

使用 Interactive Story Skill：
1. 搜索用户历史偏好
2. 生成开篇（100-200字）
3. 创建第一个决策点（2-3个选项）
4. 保存会话状态到 ./data/sessions/session_{session_id}.json

返回开篇故事和选项（JSON格式）。
"""

    result_data = {}
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage) and message.subtype == "success":
            result_data = json.loads(message.result)

    return result_data


async def continue_interactive_story(
    session_id: str,
    choice_id: str
) -> dict:
    """继续互动故事"""

    options = ClaudeAgentOptions(
        mcp_servers={
            "safety": safety_server,
            "tts": tts_server
        },
        allowed_tools=[
            "mcp__safety__check_content_safety",
            "mcp__tts__generate_story_audio",
            "Read", "Write", "Skill"
        ],
        cwd=".",
        setting_sources=["user", "project"],
        permission_mode="acceptEdits"
    )

    prompt = f"""
任务：继续互动故事

会话ID：{session_id}
用户选择：{choice_id}

使用 Interactive Story Skill：
1. 读取会话状态 ./data/sessions/session_{session_id}.json
2. 根据选择生成下一段（100-200字）
3. 更新角色状态
4. 创建新决策点或结局
5. 保存更新后的状态

返回下一段故事和选项（JSON格式）。
"""

    result_data = {}
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage) and message.subtype == "success":
            result_data = json.loads(message.result)

    return result_data


# FastAPI 路由
@app.post("/api/v1/story/interactive/start")
async def api_start_interactive_story(
    child_id: str,
    child_age: int,
    interests: str
):
    """开始互动故事"""
    result = await start_interactive_story(
        child_id=child_id,
        child_age=child_age,
        interests=interests.split(',')
    )
    return {"success": True, "data": result}


@app.post("/api/v1/story/interactive/{session_id}/choose")
async def api_continue_interactive_story(
    session_id: str,
    choice_id: str
):
    """继续互动故事"""
    result = await continue_interactive_story(
        session_id=session_id,
        choice_id=choice_id
    )
    return {"success": True, "data": result}
```

---

## 5. 契约测试（TDD）

### 5.1 MCP Tool 契约测试

```python
# tests/contracts/mcp_tools_contract.py
import pytest
from src.mcp_servers.vision_analysis_server import analyze_children_drawing
from src.mcp_servers.vector_search_server import search_similar_drawings
from src.mcp_servers.safety_check_server import check_content_safety
import json

class TestVisionAnalysisContract:
    """Vision Analysis MCP Tool 契约测试"""

    @pytest.mark.asyncio
    async def test_analyze_children_drawing_contract(self):
        """测试画作分析工具契约"""
        # 输入契约
        input_args = {
            "image_path": "./test_data/sample_drawing.jpg"
        }

        # 执行工具
        result = await analyze_children_drawing(input_args)

        # 输出契约验证
        assert "content" in result
        assert len(result["content"]) > 0

        content_text = result["content"][0]["text"]
        data = json.loads(content_text)

        # 验证必需字段
        assert "objects" in data
        assert "scene" in data
        assert "mood" in data
        assert "colors" in data

        # 验证数据类型
        assert isinstance(data["objects"], list)
        assert len(data["objects"]) > 0
        assert isinstance(data["scene"], str)
        assert isinstance(data["mood"], str)


class TestSafetyCheckContract:
    """Safety Check MCP Tool 契约测试"""

    @pytest.mark.asyncio
    async def test_check_content_safety_contract(self):
        """测试安全检查工具契约"""
        # 输入契约
        input_args = {
            "content": "小狗在公园里玩耍，遇到了好朋友小猫。",
            "target_age": 7
        }

        # 执行工具
        result = await check_content_safety(input_args)

        # 输出契约验证
        content_text = result["content"][0]["text"]
        data = json.loads(content_text)

        # 验证必需字段
        assert "is_safe" in data
        assert "safety_score" in data
        assert "issues" in data
        assert "suggestions" in data

        # 验证数据类型和范围
        assert isinstance(data["is_safe"], bool)
        assert 0.0 <= data["safety_score"] <= 1.0
        assert isinstance(data["issues"], list)
        assert isinstance(data["suggestions"], list)

        # 验证业务规则
        if data["safety_score"] < 0.7:
            assert not data["is_safe"]
        if data["safety_score"] > 0.85:
            assert data["is_safe"]
```

### 5.2 Agent 集成契约测试

```python
# tests/contracts/agent_integration_contract.py
import pytest
from src.agents.image_to_story import image_to_story
from src.agents.interactive_story import start_interactive_story

class TestImageToStoryAgentContract:
    """画作转故事 Agent 集成契约测试"""

    @pytest.mark.asyncio
    async def test_image_to_story_end_to_end(self):
        """测试完整的画作转故事流程"""
        # 输入
        result = await image_to_story(
            image_path="./test_data/sample_drawing.jpg",
            child_id="test_user_123",
            child_age=7,
            interests=["动物", "冒险"]
        )

        # 输出契约验证
        assert "story_title" in result
        assert "story_text" in result
        assert "word_count" in result
        assert "safety_score" in result
        assert "audio_path" in result

        # 验证业务规则
        # 7岁儿童的故事应该在 200-400 字
        assert 150 <= result["word_count"] <= 450

        # 安全分数应该 > 0.85
        assert result["safety_score"] > 0.85

        # 应该有教育要点
        assert "educational_points" in result
        assert len(result["educational_points"]) > 0
```

---

## 6. 项目结构

```
creative_agent/
├── .claude/
│   └── skills/                      # Skills (Markdown 文件)
│       ├── story-generation/
│       │   └── SKILL.md
│       ├── interactive-story/
│       │   └── SKILL.md
│       └── age-adapter/
│           └── SKILL.md
│
├── src/
│   ├── mcp_servers/                 # MCP Tools
│   │   ├── vision_analysis_server.py
│   │   ├── vector_search_server.py
│   │   ├── safety_check_server.py
│   │   └── tts_server.py
│   │
│   ├── agents/                      # Agent 编排
│   │   ├── image_to_story.py
│   │   ├── interactive_story.py
│   │   └── news_to_kids.py
│   │
│   └── api/
│       └── main.py                  # FastAPI 路由
│
├── tests/
│   └── contracts/                   # 契约测试
│       ├── mcp_tools_contract.py
│       └── agent_integration_contract.py
│
├── data/
│   ├── uploads/                     # 上传的图片
│   ├── audio/                       # 生成的音频
│   ├── sessions/                    # 互动故事会话
│   └── vectors/                     # ChromaDB 向量数据库
│
├── DOMAIN.md                        # 领域文档
├── PRD.md                           # 产品需求
├── ARCHITECTURE_V2.md               # 架构文档（本文档）
└── README.md                        # 项目简介
```

---

## 7. 开发工作流（TDD）

```
Step 1: 编写 MCP Tool 契约测试
  ├─ tests/contracts/mcp_tools_contract.py
  └─ 定义输入输出格式
        ↓
Step 2: 实现 MCP Tool
  ├─ src/mcp_servers/vision_analysis_server.py
  └─ 使用 @tool 装饰器定义工具
        ↓
Step 3: 运行契约测试
  ├─ pytest tests/contracts/mcp_tools_contract.py -v
  └─ 确保通过
        ↓
Step 4: 编写 Skill (Markdown)
  ├─ .claude/skills/story-generation/SKILL.md
  └─ 定义 Agent 行为和工作流程
        ↓
Step 5: 编写 Agent 编排代码
  ├─ src/agents/image_to_story.py
  └─ 使用 query() + ClaudeAgentOptions
        ↓
Step 6: 运行 Agent 集成测试
  ├─ pytest tests/contracts/agent_integration_contract.py -v
  └─ 验证端到端流程
```

---

## 8. 核心差异总结

| 之前的错误理解 | 正确的理解 |
|--------------|-----------|
| 自己实现 BaseAgent 类 | 使用 SDK 的 `query()` 函数 |
| 手动管理工具执行循环 | SDK 自动处理 |
| Skill = Python 类 | Skill = Markdown 文件 |
| 需要实现 `to_claude_tool()` | 使用 `@tool` 装饰器 |
| 复杂的数据库设计 | 简单的 JSON + ChromaDB |
| ContractSkill 作为运行时验证 | 契约测试 + MCP Tool 输入验证 |

---

## 附录

### A. 关键依赖

```
# Python
claude-agent-sdk==1.0.0
anthropic==0.18.1
openai==1.12.0
chromadb==1.4.1
fastapi==0.110.0
pydantic==2.6.1
pytest==8.0.0
```

### B. 环境变量

```env
ANTHROPIC_API_KEY=your_key
OPENAI_API_KEY=your_key
CHROMA_PATH=./data/vectors
```

### C. 快速开始

```bash
# 1. 安装依赖
pip install claude-agent-sdk anthropic openai chromadb fastapi

# 2. 设置 API Key
export ANTHROPIC_API_KEY=your_key
export OPENAI_API_KEY=your_key

# 3. 创建 Skills 目录
mkdir -p .claude/skills/story-generation

# 4. 运行契约测试
pytest tests/contracts/ -v

# 5. 启动 API
python -m src.api.main
```
