# Image to Story API (画作转故事)

> 将儿童画作转化为个性化故事的 API 服务

## 概述

Image to Story API 允许用户上传儿童画作，AI Agent 会分析画作内容并生成适合儿童年龄的个性化故事。

**Base URL:** `/api/v1`

---

## 端点列表

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | `/image-to-story` | 上传画作并生成故事 |
| GET | `/stories/{story_id}` | 获取故事详情 |
| GET | `/stories` | 列出所有故事 |

---

## 1. 画作转故事

### `POST /api/v1/image-to-story`

上传儿童画作，AI 生成个性化故事。

#### 请求格式

**Content-Type:** `multipart/form-data`

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `image` | File | 是 | 儿童画作图片（PNG/JPG/WEBP，最大10MB） |
| `child_id` | string | 是 | 儿童唯一标识符 |
| `age_group` | string | 是 | 年龄组：`3-5`, `6-8`, `9-12` |
| `interests` | string | 否 | 兴趣标签，用逗号分隔（最多5个） |
| `voice` | string | 否 | 语音类型，默认 `nova` |
| `enable_audio` | boolean | 否 | 是否生成语音，默认 `true` |

#### 语音类型

| 值 | 描述 |
|------|------|
| `nova` | 温柔女性 |
| `shimmer` | 活泼女性 |
| `alloy` | 中性 |
| `echo` | 男性 |
| `fable` | 故事讲述者 |
| `onyx` | 深沉男性 |

#### 请求示例

```bash
curl -X POST "http://localhost:8000/api/v1/image-to-story" \
  -F "image=@drawing.png" \
  -F "child_id=child_001" \
  -F "age_group=6-8" \
  -F "interests=动物,冒险,太空" \
  -F "voice=nova" \
  -F "enable_audio=true"
```

#### 响应格式

**状态码:** `201 Created`

```json
{
  "story_id": "550e8400-e29b-41d4-a716-446655440000",
  "story": {
    "text": "在一个阳光明媚的早晨，小兔子发现了一片神奇的花园...",
    "word_count": 285,
    "age_adapted": true
  },
  "audio_url": "/data/audio/550e8400-e29b-41d4-a716-446655440000.mp3",
  "educational_value": {
    "themes": ["友谊", "勇气"],
    "concepts": ["颜色", "大自然"],
    "moral": "帮助朋友是一件快乐的事情"
  },
  "characters": [
    {
      "character_name": "小兔子",
      "description": "一只可爱的白色小兔子",
      "appearances": 1
    }
  ],
  "analysis": {
    "detected_objects": ["兔子", "花园", "太阳"],
    "emotions": ["快乐", "好奇"],
    "colors": ["绿色", "粉色", "黄色"]
  },
  "safety_score": 0.95,
  "created_at": "2026-01-31T10:30:00"
}
```

#### 错误响应

| 状态码 | 描述 |
|--------|------|
| 400 | 请求参数错误（文件格式不支持、兴趣标签过多等） |
| 413 | 文件大小超过限制（10MB） |
| 500 | 服务器内部错误 |

```json
{
  "error": "ValidationError",
  "message": "不支持的文件格式。允许的格式: .jpg, .jpeg, .png, .webp",
  "timestamp": "2026-01-31T10:30:00"
}
```

---

## 2. 获取故事详情

### `GET /api/v1/stories/{story_id}`

根据故事 ID 获取已生成的故事详情。

#### 路径参数

| 参数 | 类型 | 描述 |
|------|------|------|
| `story_id` | string | 故事唯一标识符 |

#### 请求示例

```bash
curl "http://localhost:8000/api/v1/stories/550e8400-e29b-41d4-a716-446655440000"
```

#### 响应格式

**状态码:** `200 OK`

```json
{
  "story_id": "550e8400-e29b-41d4-a716-446655440000",
  "child_id": "child_001",
  "age_group": "6-8",
  "story": {
    "text": "在一个阳光明媚的早晨...",
    "word_count": 285,
    "age_adapted": true
  },
  "audio_url": "/data/audio/550e8400-e29b-41d4-a716-446655440000.mp3",
  "educational_value": {
    "themes": ["友谊", "勇气"],
    "concepts": ["颜色", "大自然"],
    "moral": "帮助朋友是一件快乐的事情"
  },
  "characters": [...],
  "analysis": {...},
  "safety_score": 0.95,
  "created_at": "2026-01-31T10:30:00",
  "image_path": "./data/uploads/child_001/abc123.png",
  "stored_at": "2026-01-31T10:30:05"
}
```

#### 错误响应

| 状态码 | 描述 |
|--------|------|
| 404 | 故事不存在 |

---

## 3. 列出所有故事

### `GET /api/v1/stories`

获取所有已生成故事的列表。

#### 查询参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `child_id` | string | 否 | 按儿童 ID 筛选 |
| `limit` | integer | 否 | 返回数量限制，默认 20 |

#### 请求示例

```bash
# 获取所有故事
curl "http://localhost:8000/api/v1/stories"

# 按儿童 ID 筛选
curl "http://localhost:8000/api/v1/stories?child_id=child_001&limit=10"
```

#### 响应格式

**状态码:** `200 OK`

```json
{
  "total": 3,
  "stories": [
    {
      "story_id": "550e8400-e29b-41d4-a716-446655440000",
      "child_id": "child_001",
      "created_at": "2026-01-31T10:30:00",
      "word_count": 285,
      "has_audio": true
    },
    {
      "story_id": "661f9511-f30c-52e5-b827-557766551111",
      "child_id": "child_001",
      "created_at": "2026-01-30T15:20:00",
      "word_count": 320,
      "has_audio": true
    }
  ]
}
```

---

## 年龄适配

根据年龄组，生成的故事会自动调整：

| 年龄组 | 字数范围 | 句子长度 | 词汇水平 |
|--------|----------|----------|----------|
| 3-5岁 | 100-200字 | 5-10字 | 基础日常词汇 |
| 6-8岁 | 200-400字 | 10-15字 | 小学低年级词汇 |
| 9-12岁 | 400-800字 | 15-25字 | 小学高年级词汇 |

---

## 安全审查

所有生成的故事都会经过安全审查：

- **安全评分范围:** 0.0 - 1.0
- **通过标准:** >= 0.85
- **审查内容:**
  - 过滤暴力、恐怖、不当语言
  - 确保性别平等、文化多样性
  - 融入品德教育元素

---

## 使用示例

### Python

```python
import requests

url = "http://localhost:8000/api/v1/image-to-story"

files = {
    "image": ("drawing.png", open("drawing.png", "rb"), "image/png")
}

data = {
    "child_id": "child_001",
    "age_group": "6-8",
    "interests": "动物,冒险",
    "voice": "fable",
    "enable_audio": "true"
}

response = requests.post(url, files=files, data=data)
result = response.json()

print(f"故事标题: {result['story']['text'][:50]}...")
print(f"教育主题: {result['educational_value']['themes']}")
```

### JavaScript

```javascript
const formData = new FormData();
formData.append('image', fileInput.files[0]);
formData.append('child_id', 'child_001');
formData.append('age_group', '6-8');
formData.append('interests', '动物,冒险');

const response = await fetch('http://localhost:8000/api/v1/image-to-story', {
  method: 'POST',
  body: formData
});

const result = await response.json();
console.log('故事:', result.story.text);
```
