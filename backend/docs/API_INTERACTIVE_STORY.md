# Interactive Story API (互动故事)

> 生成多分支互动故事的 API 服务，让儿童在关键点做出选择影响故事走向

## 概述

Interactive Story API 允许用户创建互动故事会话，儿童可以在故事的关键节点做出选择，影响故事的发展方向。所有分支最终都会导向积极正面的结局。

**Base URL:** `/api/v1/story/interactive`

---

## 端点列表

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/start` | 开始新的互动故事 |
| POST | `/{session_id}/choose` | 选择故事分支 |
| GET | `/{session_id}/status` | 获取会话状态 |

---

## 1. 开始互动故事

### `POST /api/v1/story/interactive/start`

创建新的互动故事会话，生成故事开场。

#### 请求格式

**Content-Type:** `application/json`

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `child_id` | string | 是 | 儿童唯一标识符 |
| `age_group` | string | 是 | 年龄组：`3-5`, `6-8`, `9-12` |
| `interests` | array | 是 | 兴趣标签列表（1-5个） |
| `theme` | string | 否 | 故事主题（可选） |
| `voice` | string | 否 | 语音类型，默认 `fable` |
| `enable_audio` | boolean | 否 | 是否生成语音，默认 `true` |

#### 请求示例

```bash
curl -X POST "http://localhost:8000/api/v1/story/interactive/start" \
  -H "Content-Type: application/json" \
  -d '{
    "child_id": "child_001",
    "age_group": "6-8",
    "interests": ["恐龙", "冒险"],
    "theme": "恐龙探险",
    "voice": "fable",
    "enable_audio": false
  }'
```

#### 响应格式

**状态码:** `201 Created`

```json
{
  "session_id": "c04adb72-163a-44e3-90b9-4bdce58ba1bb",
  "story_title": "恐龙探险之旅",
  "opening": {
    "segment_id": 0,
    "text": "在一个阳光明媚的早晨，小明在花园里发现了一颗闪闪发光的恐龙蛋！它比鹅蛋还要大，上面有漂亮的绿色花纹...",
    "audio_url": null,
    "choices": [
      {
        "choice_id": "choice_0_a",
        "text": "立刻去探索",
        "emoji": "🔍"
      },
      {
        "choice_id": "choice_0_b",
        "text": "先找朋友一起",
        "emoji": "👫"
      },
      {
        "choice_id": "choice_0_c",
        "text": "仔细观察一下",
        "emoji": "👀"
      }
    ],
    "is_ending": false
  },
  "created_at": "2026-01-31T10:30:00"
}
```

---

## 2. 选择故事分支

### `POST /api/v1/story/interactive/{session_id}/choose`

在互动故事中做出选择，获取下一段故事。

#### 路径参数

| 参数 | 类型 | 描述 |
|------|------|------|
| `session_id` | string | 会话 ID |

#### 请求格式

**Content-Type:** `application/json`

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `choice_id` | string | 是 | 选择的选项 ID |

#### 请求示例

```bash
curl -X POST "http://localhost:8000/api/v1/story/interactive/c04adb72-163a-44e3-90b9-4bdce58ba1bb/choose" \
  -H "Content-Type: application/json" \
  -d '{
    "choice_id": "choice_0_a"
  }'
```

#### 响应格式（继续中）

**状态码:** `200 OK`

```json
{
  "session_id": "c04adb72-163a-44e3-90b9-4bdce58ba1bb",
  "next_segment": {
    "segment_id": 1,
    "text": "小明决定立刻去探索。他小心翼翼地把恐龙蛋捧起来，发现它暖暖的，还在微微发光。突然，蛋壳出现了裂缝...",
    "audio_url": null,
    "choices": [
      {
        "choice_id": "choice_1_a",
        "text": "帮助小恐龙破壳",
        "emoji": "🐣"
      },
      {
        "choice_id": "choice_1_b",
        "text": "等待它自己出来",
        "emoji": "⏳"
      }
    ],
    "is_ending": false
  },
  "choice_history": ["choice_0_a"],
  "progress": 0.25
}
```

#### 响应格式（结局）

当故事到达结局时：

```json
{
  "session_id": "c04adb72-163a-44e3-90b9-4bdce58ba1bb",
  "next_segment": {
    "segment_id": 3,
    "text": "经过这次奇妙的冒险，小明和小恐龙成为了最好的朋友。他学会了勇敢面对未知，也明白了友谊的珍贵。这真是一次难忘的经历！",
    "audio_url": null,
    "choices": [],
    "is_ending": true
  },
  "choice_history": ["choice_0_a", "choice_1_a", "choice_2_b"],
  "progress": 1.0
}
```

#### 错误响应

| 状态码 | 描述 |
|--------|------|
| 400 | 会话已完成或已过期 |
| 404 | 会话不存在 |
| 500 | 故事生成失败 |

---

## 3. 获取会话状态

### `GET /api/v1/story/interactive/{session_id}/status`

查询互动故事会话的当前状态。

#### 路径参数

| 参数 | 类型 | 描述 |
|------|------|------|
| `session_id` | string | 会话 ID |

#### 请求示例

```bash
curl "http://localhost:8000/api/v1/story/interactive/c04adb72-163a-44e3-90b9-4bdce58ba1bb/status"
```

#### 响应格式

**状态码:** `200 OK`

```json
{
  "session_id": "c04adb72-163a-44e3-90b9-4bdce58ba1bb",
  "status": "completed",
  "child_id": "child_001",
  "story_title": "恐龙探险之旅",
  "current_segment": 4,
  "total_segments": 4,
  "choice_history": ["choice_0_a", "choice_1_a", "choice_2_b"],
  "educational_summary": {
    "themes": ["勇气", "友谊"],
    "concepts": ["决策", "探索"],
    "moral": "勇敢面对挑战，和朋友一起会更有力量"
  },
  "created_at": "2026-01-31T10:30:00",
  "updated_at": "2026-01-31T10:35:00",
  "expires_at": "2026-02-01T10:30:00"
}
```

#### 会话状态

| 状态 | 描述 |
|------|------|
| `active` | 会话进行中，可以继续选择 |
| `completed` | 故事已完成 |
| `expired` | 会话已过期（24小时后） |

---

## 年龄适配配置

根据年龄组，故事的复杂度和长度会自动调整：

| 年龄组 | 总段落数 | 每段字数 | 句子长度 | 主题深度 |
|--------|----------|----------|----------|----------|
| 3-5岁 | 3 | 50-100字 | 5-10字 | 简单、具体、与日常生活相关 |
| 6-8岁 | 4 | 100-200字 | 10-15字 | 有趣的冒险，简单的道德选择 |
| 9-12岁 | 5 | 150-300字 | 15-25字 | 复杂情节，品德和智慧的考验 |

---

## 故事流程

```
开始故事 (POST /start)
    ↓
返回开场 + 选项
    ↓
用户选择 (POST /{session_id}/choose)
    ↓
返回下一段 + 新选项
    ↓
... 重复 2-4 轮 ...
    ↓
到达结局 (is_ending: true)
    ↓
返回教育总结
```

---

## 设计原则

### 1. 所有分支都是好结局

无论儿童做出什么选择，故事最终都会导向积极正面的结局。不会因为"错误"的选择而惩罚儿童。

### 2. 教育融合

每个故事都自然融入 STEAM 或品德教育元素：
- **科学探索精神**
- **友谊与合作**
- **勇气与自信**
- **同理心与善良**

### 3. 年龄适配

根据年龄自动调整：
- 词汇复杂度
- 句子长度
- 情节复杂度
- 选项数量

---

## 使用示例

### Python - 完整故事流程

```python
import requests
import time

BASE_URL = "http://localhost:8000/api/v1/story/interactive"

# 1. 开始故事
start_response = requests.post(f"{BASE_URL}/start", json={
    "child_id": "child_001",
    "age_group": "6-8",
    "interests": ["恐龙", "冒险"],
    "theme": "恐龙探险"
})
story = start_response.json()
session_id = story["session_id"]

print(f"故事标题: {story['story_title']}")
print(f"开场: {story['opening']['text']}")
print(f"选项: {[c['text'] for c in story['opening']['choices']]}")

# 2. 循环进行选择直到结局
while True:
    # 获取可用选项
    status = requests.get(f"{BASE_URL}/{session_id}/status").json()

    if status["status"] == "completed":
        print("\n故事结束!")
        print(f"教育总结: {status['educational_summary']}")
        break

    # 这里可以让用户选择，示例中自动选择第一个
    choice_id = story.get('opening', {}).get('choices', [{}])[0].get('choice_id') or \
                next_segment.get('choices', [{}])[0].get('choice_id')

    # 做出选择
    choose_response = requests.post(f"{BASE_URL}/{session_id}/choose", json={
        "choice_id": choice_id
    })
    next_segment = choose_response.json()["next_segment"]

    print(f"\n段落 {next_segment['segment_id']}: {next_segment['text']}")
    print(f"进度: {choose_response.json()['progress'] * 100:.0f}%")

    if next_segment["is_ending"]:
        break

    print(f"选项: {[c['text'] for c in next_segment['choices']]}")
```

### JavaScript - React 组件示例

```javascript
import { useState, useEffect } from 'react';

function InteractiveStory({ childId, ageGroup, interests }) {
  const [sessionId, setSessionId] = useState(null);
  const [segment, setSegment] = useState(null);
  const [progress, setProgress] = useState(0);
  const [isEnding, setIsEnding] = useState(false);

  // 开始故事
  const startStory = async () => {
    const response = await fetch('/api/v1/story/interactive/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ child_id: childId, age_group: ageGroup, interests })
    });
    const data = await response.json();
    setSessionId(data.session_id);
    setSegment(data.opening);
  };

  // 做出选择
  const makeChoice = async (choiceId) => {
    const response = await fetch(`/api/v1/story/interactive/${sessionId}/choose`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ choice_id: choiceId })
    });
    const data = await response.json();
    setSegment(data.next_segment);
    setProgress(data.progress);
    setIsEnding(data.next_segment.is_ending);
  };

  return (
    <div className="story-container">
      {!sessionId ? (
        <button onClick={startStory}>开始故事</button>
      ) : (
        <>
          <div className="progress-bar" style={{ width: `${progress * 100}%` }} />
          <p className="story-text">{segment?.text}</p>

          {!isEnding && segment?.choices?.map(choice => (
            <button
              key={choice.choice_id}
              onClick={() => makeChoice(choice.choice_id)}
            >
              {choice.emoji} {choice.text}
            </button>
          ))}

          {isEnding && <p>故事结束！</p>}
        </>
      )}
    </div>
  );
}
```

---

## 错误处理

### 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| 会话不存在 | session_id 无效 | 重新开始故事 |
| 会话已完成 | 故事已结束 | 获取状态查看教育总结，或开始新故事 |
| 会话已过期 | 超过24小时 | 开始新故事 |
| 选项无效 | choice_id 不匹配 | 使用返回的有效 choice_id |

### 错误响应示例

```json
{
  "detail": "会话不存在"
}
```

```json
{
  "detail": "会话已completed，无法继续"
}
```
