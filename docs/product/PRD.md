# 儿童创意工坊 - 产品需求文档 (PRD)

> **定位**: 本文档专注于产品功能定义，技术实现见 [ARCHITECTURE.md](ARCHITECTURE.md)，领域背景见 [DOMAIN.md](DOMAIN.md)

---

## 1. 产品概述

### 1.1 产品定位
儿童创意工坊是一个基于 AI Agent 的创意内容生成平台，为 3-12 岁儿童提供安全、有趣、富有教育意义的内容创作服务。

### 1.2 核心价值主张
- **激发创造力**: AI 将儿童画作转化为生动故事
- **互动参与**: 多分支互动故事，让儿童成为故事的创作者
- **个性化体验**: 记住每个孩子的创作历史，保持故事连续性
- **知识普及**: 双角色随时听播客(Kids Daily)将复杂新闻转化为有趣的儿童对话体验，随时按需生成
- **安全保障**: 所有内容经过严格审查，符合儿童内容标准

---

## 2. 目标用户

### 2.1 用户画像

**小明 (7岁) - 小画家**
- 喜欢画画，想看到自己的画"活"起来
- 对恐龙、太空、动物感兴趣
- 注意力集中时间：15-20分钟

**李女士 (35岁) - 家长**
- 关注儿童教育和内容安全
- 希望孩子接触有教育意义的内容
- 担心互联网上的不良内容

**张老师 (教师) - 教育工作者**
- 需要有趣的教学素材
- 希望激发学生创造力
- 寻找适合不同年龄段的内容

---

## 3. 核心功能

### 3.1 画作转故事 (Image-to-Story) [Near Complete]

#### 功能描述
儿童上传画作，AI Agent 分析画作内容，生成个性化故事。

#### 用户场景
```
小明画了一只小狗在公园玩耍
  ↓
上传到系统
  ↓
AI 识别：小狗、树木、太阳、快乐情绪
AI 发现：小明上周也画过这只狗，叫"闪电"
  ↓
生成故事："闪电小狗今天又来到了它最喜欢的公园..."
  ↓
输出：文字故事 + 语音朗读
```

#### 输入
- **必填**: 画作图片 (PNG/JPG, 最大 10MB)
- **可选**: 儿童年龄、兴趣标签

#### 输出
- 故事文本 (200-500字，根据年龄调整)
- 语音朗读 (可选声音：温柔奶奶、调皮小精灵等)
- 教育要点总结

#### 特色功能
- **角色记忆**: 识别重复出现的角色（如"闪电小狗"），保持故事连续性
- **年龄适配**: 3-5岁简短故事（100-200字），6-8岁中等（200-400字），9-12岁更长（400-800字）
- **安全审查**: 自动过滤不适合儿童的内容

#### 验收标准 (Acceptance Criteria)
- [ ] 故事长度符合年龄段规则：3-5岁(100-200字)、6-8岁(200-400字)、9-12岁(400-800字)
- [x] 安全评分 ≥ 0.85 才能交付
- [ ] 响应时间 < 10秒
- [x] 角色记忆：识别重复角色
- [x] 同步路径：完整的 provenance 追踪
- [ ] 流式路径：provenance 追踪与同步路径对齐
- [ ] 流式路径：角色同步到 character 表
- [ ] 契约测试覆盖 agent 输出 schema 和 API 响应格式
- [ ] Happy-path API 测试断言已启用

#### 3.1.1 画作风格转换 (Art Style Transfer) [Phase 2]

##### 功能描述
儿童上传画作后可选择一种艺术风格（卡通、油画、水彩、像素画、动漫、蜡笔、绘本），系统使用 AI 图像转换将画作变为对应风格。风格化后的图片作为故事封面，同时为故事生成提供额外创意上下文。原始画作始终保留。

##### 用户场景
```
小明画了一只小狗在公园玩耍
  ↓
上传画作，选择"卡通"风格
  ↓
AI 将画作转换为卡通风格（保留小狗和公园的核心元素）
  ↓
卡通版画作成为故事封面
AI 结合卡通风格生成更富创意的故事
  ↓
输出：卡通封面 + 文字故事 + 语音朗读
```

##### 技术实现
- **模型**: `black-forest-labs/flux-kontext-pro`（Replicate，SDK 已在 `requirements.txt`）
- **新 MCP 工具服务**: `image_style_server.py`，工具名 `mcp__image-style__transform_art_style`
- **管线变更**: `upload → vision_analysis → [style_transfer if theme ≠ none] → [image_safety_check] → vector_search → story_gen → safety_check → tts`
- **安全门**: 风格化图片通过 Vision API 验证儿童适宜性，不通过则回退到原始画作
- **原始保留**: 原始画作永远不被覆盖或删除

##### 可用风格 (ArtTheme)
| 风格 | 英文 ID | 提示词模板示例 |
|------|---------|---------------|
| 卡通 | `cartoon` | "Make this a colorful cartoon illustration" |
| 油画 | `oil_painting` | "Transform this into an oil painting style" |
| 水彩 | `watercolor` | "Make this a soft watercolor painting" |
| 像素画 | `pixel_art` | "Convert this to pixel art style" |
| 动漫 | `anime` | "Make this in anime illustration style" |
| 蜡笔画 | `crayon` | "Make this look like a crayon drawing" |
| 绘本 | `storybook` | "Transform this into a storybook illustration" |
| 保持原样 | `none` | （跳过转换） |

##### 年龄适配
| 年龄组 | 可用风格 | 说明 |
|--------|---------|------|
| 3-5岁 | cartoon, crayon, watercolor, storybook | 仅柔和、简单的风格 |
| 6-8岁 | 全部 | 完整风格目录 |
| 9-12岁 | 全部 | 完整风格目录 |

##### 内容安全要求
- 每张风格化图片必须通过 Vision API 安全验证后才能使用
- 验证失败时静默回退到原始画作，记录警告日志
- 安全评分记录到溯源链（Provenance）

##### 边界情况
- **未选择风格**: 完全跳过转换，向后兼容
- **Replicate API 失败**: 回退到原始画作，记录警告，继续故事生成
- **生成图片不适宜**: 回退到原始画作，标记待审查
- **大图片 (>5MB)**: 转换前自动缩放

##### 验收标准
- [ ] `ArtTheme` 枚举包含 8 个值（含 `none`）
- [ ] `POST /api/v1/image-to-story` 接受可选 `art_theme` 参数
- [ ] `image_style_server.py` MCP 工具使用 `flux-kontext-pro` 模型
- [ ] 风格转换在 15 秒内完成
- [ ] 原始画作核心元素在风格化后保留
- [ ] 风格化图片通过 Vision API 安全验证
- [ ] 3-5 岁仅显示 4 种柔和风格
- [ ] 未选择风格时管线行为与现有完全一致
- [ ] 契约测试覆盖 `transform_art_style` MCP 工具
- [ ] 风格化图片作为故事封面展示
- [ ] 前端 UploadPage 新增风格选择步骤（可视化卡片）

##### 不在本期范围
- 自定义风格提示词（用户自由输入风格描述）
- 多次风格叠加（一次只能选一种）
- 风格预览（实时预览需额外 API 调用，成本过高）
- 风格应用到互动故事或新闻内容

> **Parent Epic**: #40 | **Phase**: 2 | **Milestone**: Phase 2 — Interactive + Memory + News

#### 已知差距 (Remaining Gaps)
1. 故事长度无运行时验证——LLM 生成内容可能超出年龄段目标范围
2. 流式路径缺少 provenance 追踪和角色同步（同步路径已完整）
3. 无契约测试锁定 agent 输出 schema
4. Happy-path API 测试断言被注释掉，CI 无法捕获回归

---

### 3.2 互动故事生成器 (Interactive Story) [In Progress]

#### 功能描述
基于儿童兴趣生成多分支互动故事，让儿童在关键点做出选择，影响故事走向。

#### 用户场景
```
小红想听恐龙故事
  ↓
AI 生成开篇："小恐龙发现了一个神秘山洞..."
  ↓
展示选择：
  A. 勇敢地走进去 🏔️
  B. 先回家叫上朋友 👫
  ↓
小红选择 A
  ↓
AI 生成下一段："小恐龙走进山洞，发现了发光的化石..."
  ↓
继续 2-4 轮，最终到达结局
  ↓
总结教育要点：勇气、科学探索精神
```

#### 两种模式

**线性模式** (Traditional) [Not Started]
- 一次性生成完整故事
- 适合睡前故事、阅读练习
- 300-800字

**互动模式** (Interactive) [Complete — core flow]
- 分段生成，每段 100-300字
- 2-4 个决策点，每次 2-3 个选项
- 所有分支都是"好结局"（不惩罚儿童的选择）
- SSE streaming for opening and choices
- Age-based audio strategy (audio-first for 3-5, simultaneous for 6-9, text-first for 10-12)
- Preference tracking on story completion
- Save completed stories to My Library

#### 输入
- **必填**: 儿童年龄、兴趣标签（1-5个）
- **可选**: 故事主题、教育目标、互动模式

#### 输出
- 故事段落 + 语音朗读
- 互动选项（含emoji）
- 教育要点总结
- 会话ID（用于多轮对话）

#### 特色功能
- **个性化推荐**: 根据历史偏好调整主题
- **教育融合**: 自然融入 STEAM 和品德教育
- **语言适配**: 根据年龄自动调整词汇和句式复杂度

#### 已实现 (What's Built)
- ✅ Core interactive mode: start → choose → progress → ending
- ✅ SSE streaming for all generation endpoints
- ✅ Age-based configuration (word count, complexity, segment count, audio mode)
- ✅ Safety check integration via MCP tool
- ✅ TTS audio generation with age-appropriate voice/speed
- ✅ Vector search for similar content
- ✅ Preference storage on completion (themes, concepts, interests, choices)
- ✅ Session management (create, track progress, expire)
- ✅ Full frontend: setup → playing → completed states with 2.5D visual effects
- ✅ Story save to My Library on completion
- ✅ Educational summary display with tags

#### Phase 2 增强 (Planned Enhancements)
- ✅ **偏好感知生成**: 将儿童累积偏好 (themes, concepts, recent_choices) 注入开篇提示词。`_fetch_preference_context()` 读取主题、兴趣和近期选择并注入故事开篇和分支续写提示词
- 🔲 **角色延续**: 跨会话搜索和重用重复角色（如"闪电小狗"在互动故事中继续出现），目前仅画作转故事有角色记忆
- 🔲 **主题推荐**: 基于偏好历史推荐故事主题，替代当前的纯手动输入
- 🔲 **会话恢复**: 列出活跃会话并支持中断后继续，后端 `list_sessions` 已存在但无 API 路由暴露
- 🔲 **故事回放**: 重新阅读已完成的互动故事（含完整分支路径），目前保存的仅为拼接文本
- 🔲 **选择特质追踪**: 追踪选择揭示的性格特质（勇气、友谊等），提示词已定义但 Pydantic 模型缺少 `trait` 字段
- 🔲 **线性模式**: 添加一键生成完整故事模式，适合睡前阅读
- 🔲 **故事地图可视化**: 展示选择的分支树，让儿童看到自己的冒险路径
- 🔲 **跨会话故事宇宙**: 引用前次会话中的角色和事件（"还记得上次闪电小狗的冒险吗？"）

#### 已知技术债
- 开篇和续段的提示词在普通/流式函数间重复，应提取为共享函数
- 互动故事领域缺少契约测试 (`backend/tests/contracts/`)

> **GitHub Epic**: #41 | **Phase**: 2 (core flow complete, enhancements in Phase 2) | **Milestone**: Phase 2 — Interactive + Memory + News

---

### 3.3 每日新闻 (Kids Daily) [Phase 2]

> 升级原 "新闻儿童化转换器"，从单篇文本转换进化为沉浸式双角色播客体验，配备可视化动画和每日自动推送。保留原有手动转换功能作为"手动模式"。

#### 3.3.1 每日新闻对话模式 (Kids Daily Dialogue)

##### 功能描述
LLM 将新闻改写为双角色对话剧本："好奇宝宝" (Curious Kid) 提出孩子会问的问题，"趣味专家" (Fun Expert) 用生动的比喻和故事回答。如果儿童在画作转故事或互动故事中创建过重复角色（如"闪电小狗"），该角色可以作为"特邀嘉宾主播"参与对话。

##### 用户场景
```
系统从 SpaceX 新闻生成每日新闻：

好奇宝宝：嘿！我听说有人往月球发射了一辆超级大公交车？
趣味专家：没错！科学家们造了一艘巨大的火箭，比30层楼还高！
好奇宝宝：哇，那比我们学校还高！它是怎么飞上去的？
趣味专家：它用了超级强大的发动机，喷出的火焰有蓝色和橙色...
[闪电小狗特邀嘉宾]：汪汪！我也想坐火箭去月球！月球上有骨头吗？
趣味专家：哈哈，月球上没有骨头，但有很多陨石坑...
```

##### 技术实现
- 使用 Claude Agent SDK 生成结构化对话剧本（JSON 格式，标注角色和台词）
- 通过 Memory System 查询儿童重复角色，注入对话作为嘉宾
- 使用 OpenAI TTS 多次调用（不同 voice 参数）生成各角色音频
- 音频拼接为完整播客（前端顺序播放）
- 全部内容通过安全审查（safety_score >= 0.85）

#### 3.3.2 可视化动画体验 (Visual Animatic)

##### 功能描述
播客播放时，屏幕展示 3-4 张 AI 生成的新闻主题插画，配合平移、缩放等 2.5D 动画效果和角色说话时的音频可视化。效果类似视频，但只需要图片+音频的成本。

##### 技术实现
- 基于新闻主题和对话内容生成 3-4 张插画（使用图片生成 API）
- 前端使用 CSS 动画实现平移/缩放（Ken Burns 效果）
- 角色头像在说话时显示音频波形动画
- 插画切换与对话段落同步（通过时间戳标记）

#### 3.3.3 每日推送 (Daily Drop)

##### 功能描述
儿童可以订阅感兴趣的新闻频道（太空、恐龙、动物、机器人等）。系统每日自动生成个性化播客并推送到"我的创作库"。

##### 用户场景
```
家长帮小明订阅了"太空"和"动物"频道
  ↓
系统每天凌晨自动：
  1. 获取最新儿童友好新闻
  2. 生成双角色对话剧本
  3. 渲染多角色音频
  4. 生成配套插画
  5. 打包为完整每日新闻
  ↓
小明早上打开 App，"我的创作库"里有新节目等着他
```

##### 技术实现
- 后端定时任务（可配置时间，默认凌晨 2:00）
- 按用户订阅频道批量生成
- 生成结果保存为 story_type = "morning_show"，出现在我的创作库
- 生成失败时跳过该频道，不阻塞其他频道
- 频率限制：每个订阅频道每天最多 1 集

#### 3.3.5 按需生成 (On-Demand Generation)

##### 功能描述
儿童无需等待次日的 Daily Drop，可以随时按下"立即收听"按钮，系统实时获取最新新闻并生成个性化播客节目。这将"每日新闻"升级为"随时听"(Kids Daily)，降低使用门槛，让儿童在任何想听新闻的时刻都能立即获得内容。

##### 用户场景
```
小明放学回家，想听太空新闻
  ↓
打开"儿童新闻"页面，看到订阅的频道卡片
  ↓
点击"太空"频道的"立即收听"按钮
  ↓
系统实时：
  1. 通过 Tavily 获取最新太空相关儿童友好新闻
  2. 生成双角色对话剧本
  3. 渲染多角色音频
  4. 生成配套插画
  ↓
30 秒内，播放器启动，小明开始收听
```

##### 技术实现
- 新增 `POST /api/v1/morning-show/generate-now` 端点，接收 `child_id`、`category`、`age_group`
- 从 Daily Drop 调度器提取 `_fetch_news_text()` 为共享模块 `news_headline_fetcher.py`，供调度器和按需端点共用
- 新增 SSE 流式变体 `POST /api/v1/morning-show/generate-now/stream`，推送生成进度
- 速率限制：每个儿童每小时最多 3 次按需生成（Daily Drop 不计入限制）
- 超出限制返回 429 + 友好提示："你今天听了好多！X 分钟后再来吧"
- 生成的节目保存为 `story_type = "morning_show"`，标记 `is_new = true`
- 复用现有安全管线：`check_content_safety`（safety_score >= 0.85）+ 失败时 fail-closed 回退

##### 前端交互
- 订阅管理页：每个频道卡片增加"立即收听"按钮，点击后展示加载动画
- 新闻中心 Kids Daily 模式：频道卡片同样提供"立即收听"操作
- 生成完成后自动跳转播放器页面
- 首次使用引导文案更新：从"明天早上会有新节目"改为"随时点击任意频道开始收听"

##### 速率限制与成本控制
- 按需生成涉及 Claude Agent SDK + Tavily + OpenAI TTS + 可选插画生成，成本较高
- 每小时 3 次上限在用户体验与成本之间取得平衡
- 超限时展示友好倒计时，引导儿童回看历史节目

##### 边界情况
| 场景 | 预期行为 |
|------|---------|
| Tavily 不可用/返回空结果 | 展示错误提示："现在找不到新鲜新闻，过几分钟再试试！" |
| Claude Agent SDK 生成失败 | 回退到确定性 mock 对话，标记 `is_degraded = true` |
| 儿童无订阅但访问 generate-now | 返回 400 提示先订阅频道 |
| 速率超限 | 返回 429 + `retry_after` 头 + 友好消息 |
| 同一儿童同一频道并发请求 | 允许（生成不同 episode_id），速率限制防滥用 |

#### 3.3.4 统一新闻中心 (Unified News Hub)

##### 功能描述
前端将"手动新闻转换"和"每日新闻"合并为单一入口"儿童新闻"(Kids News)，提供两种模式切换。首页导航、创作库标签页均统一为一个入口，降低儿童认知负担。

##### 用户场景
```
儿童/家长从首页点击"儿童新闻"卡片
  ↓
进入新闻中心页面，顶部有模式切换：
  - 快速阅读 (Quick Read)：粘贴新闻文本/URL → 获得简化文章
  - 每日新闻 (Kids Daily)：生成完整对话播客 + 插画 + 音频
  ↓
创作库中，"儿童新闻"标签页统一展示两种类型：
  - 每日新闻节目：显示播放按钮、时长
  - 快速阅读：显示文本预览
  ↓
按创建时间倒序排列，无需在两个标签页间切换
```

##### 技术实现
- 前端首页合并为一个"Kids News"导航卡片
- `NewsPage` 重构为 News Hub，提供 Quick Read / Kids Daily 模式切换
- `MorningShowPage` 保留为节目播放器（从 News Hub 或创作库跳转）
- 创作库 `ContentTab` 合并 `news_to_kids` + `morning_show` 为统一 `kids-news` 标签页
- 后端 library API 支持 `content_type=kids-news` 同时返回两种 `story_type`
- 原有深链接 `/news` 和 `/morning-show/:id` 继续工作（重定向或别名）

##### 年龄适配
- 与 §3.3 年龄适配表一致，模式切换 UI 对 3-5 岁使用图标而非文字

#### 输入
- **按需模式**: 订阅频道 + 儿童年龄 + 一键触发（On-Demand Generation）
- **自动模式**: 订阅频道 + 儿童年龄 + 偏好记忆（Daily Drop）
- **手动模式**: 新闻 URL/文本 + 年龄（保留原有转换功能）

#### 输出
- 双角色对话剧本（JSON + 可读文本）
- 多角色音频（分段播放，各角色不同语音）
- 3-4 张主题插画（配合 Ken Burns 动画）
- 儿童版标题、为什么重要、关键概念、互动问题（保留原有输出）

#### 年龄适配

| 年龄组 | 节目时长 | 插画数 | 对话风格 | 语音配置 |
|--------|---------|--------|---------|---------|
| 3-5岁  | 1分钟   | 2张    | 好奇宝宝问"为什么"，专家一句话回答 | nova + shimmer, 0.9x 速度, 音频自动播放 |
| 6-8岁  | 2分钟   | 3张    | 好奇宝宝问"怎么"和"如果"，专家用比喻解释 | shimmer + fable, 1.0x 速度, 文字+音频同步 |
| 9-12岁 | 3分钟   | 4张    | 好奇宝宝挑战"但是..."，专家深入分析 | echo + fable, 1.1x 速度, 文字优先+音频切换 |

#### 内容安全要求
- 所有对话剧本通过 `check_content_safety`（safety_score >= 0.85）后才生成 TTS
- 新闻源预过滤：跳过涉及暴力、死亡、战争、性、政治争议、伤亡灾难的文章
- 嘉宾角色对话单独安全检查（用户创建角色可能有意外名称/特征）
- 订阅频道为策划允许列表（NewsCategory 枚举），不支持自由文本
- Daily Drop 包含安全门：生成失败的节目被丢弃，替换为备用趣味知识话题

#### 已实现 (What's Built)
- ✅ Claude Agent SDK 集成：`_generate_with_sdk()` 调用 Claude 生成结构化对话剧本（PR #129）
- ✅ 每日新闻提示词：`backend/src/prompts/morning-show.md` 定义双角色对话格式
- ✅ `DialogueScript` / `DialogueScriptOutput` Pydantic 模型解析 SDK JSON 响应
- ✅ 时间戳单调递增归一化 + 角色名标准化 + 嘉宾台词注入
- ✅ Memory System 集成：通过 `child_id` 查询重复角色注入为嘉宾
- ✅ 多角色 TTS：各角色使用不同语音+语速组合（OpenAI TTS）
- ✅ 可视化动画：AI 插画 + Ken Burns 平移/缩放 + 音频波形
- ✅ 播放页面分屏：插画+对话文本+音频控件+角色头像
- ✅ 节目在我的创作库显示为 "morning_show" 类型
- ✅ SDK 不可用时自动回退到确定性 mock 模式
- ✅ 年龄适配：`_AGE_CONFIG` 按年龄组配置对话行数、时长、语音

#### 待完成 (Remaining Gaps)
- ✅ **安全分数提取**: `_generate_with_sdk()` 从 SDK 结构化输出提取真实 `safety_score`（#135）
- ✅ **SDK 实时生成**: `_generate_with_sdk()` 使用真实 Claude SDK 生成结构化对话剧本（PR #129, #107）
- 🔲 **SDK 路径契约测试**: 仅 mock 路径有测试，SDK 响应解析/归一化/嘉宾注入无测试覆盖（#137）
- 🔲 **显式 Mock 环境标志**: 缺少 `MORNING_SHOW_FORCE_MOCK` 环境变量，当前仅依赖 pytest 检测（#137）
- 🔲 **角色命名**: 验收标准要求 Duo + Mimi 角色名，当前代码使用 `curious_kid` / `fun_expert`（#140）
- 🔲 **新闻转换无音频朗读**: News-to-Kids 手动转换模式接受 `enable_audio` 参数但忽略它，是唯一没有 TTS 音频的核心功能
- 🔲 **Daily Drop 调度器未自启动**: `morning_show_scheduler.start()` 从未在应用启动时被调用，订阅频道不会自动生成节目
- 🔲 **安全检查静默失败**: `_check_story_safety()` 在 MCP 工具不可用时返回 0.0 分，可能导致不安全内容绕过审查门槛

#### 验收标准
- [x] 每日新闻 Agent 从新闻文章生成双角色对话剧本（好奇宝宝 + 趣味专家）
- [x] Memory System 集成：儿童重复角色可注入为"特邀嘉宾主播"
- [x] 多角色 TTS：各角色使用不同语音+语速组合（OpenAI TTS 已有语音）
- [x] 可视化动画：每集 3-4 张 AI 插画，配合 Ken Burns 平移/缩放动画
- [x] 角色头像在说话时显示音频波形
- [x] 统一新闻中心：首页单一"儿童新闻"入口，News Hub 页面提供 Quick Read / Kids Daily 模式切换
- [x] 创作库合并标签页：`kids-news` 标签页统一展示 `news_to_kids` + `morning_show` 类型内容
- [x] Library API 支持 `content_type=kids-news` 联合查询
- [ ] 频道订阅 CRUD：订阅/取消订阅/列出订阅
- [ ] Daily Drop 定时任务：后台自动为订阅频道生成节目，保存到我的创作库
- [ ] 按需生成端点：`POST /generate-now` 自动获取新闻并生成节目，无需提供 URL
- [ ] 按需生成 SSE 流式变体：实时推送生成进度到前端
- [ ] 速率限制：每个儿童每小时最多 3 次按需生成，超限返回友好提示
- [ ] 前端"立即收听"按钮：订阅页和新闻中心均可一键触发按需生成
- [ ] 引导文案更新：从"明天有新节目"改为"随时点击收听"
- [x] 节目在我的创作库显示为新内容类型 "morning_show"
- [x] 播放页面支持分屏：插画+对话文本+音频控件+角色头像
- [ ] 首次使用引导：带插画的频道订阅选择向导
- [ ] 偏好追踪：订阅频道和收听完成情况反馈到 Memory System
- [ ] 节目生成延迟：剧本+音频+4张插画 < 60秒（不含队列等待）

#### 边界情况
- **无订阅**: 显示友好引导页："订阅你喜欢的频道，每天醒来就有新节目！"
- **生成失败**: 回退到基础新闻转换文本模式，记录失败日志
- **无可用新闻**: 跳过该频道，用内置趣味知识库生成"小贴士"填充
- **首次使用**: 引导儿童选择 1-3 个订阅频道
- **无重复角色**: 如 Memory System 无儿童角色，使用内置默认角色（如"猫头鹰教授"、"彗星船长"）
- **未认证用户**: 每日新闻需认证（订阅是用户专属），未认证用户看样品/预览节目

#### 不在本期范围
- 全 AI 视频生成（使用静态插画 + CSS 动画替代 Sora/Veo）
- 自动新闻爬取/抓取（初版使用策划来源或手动输入）
- 角色语音克隆（嘉宾使用已有 OpenAI TTS 语音，语音克隆为 Phase 3）
- 社交/分享功能（COPPA 隐私考虑）
- 家长分析仪表盘（Phase 3）
- 推送通知（Daily Drop 在库中创建节目，推送需通知服务）
- 背景音乐/音效（TTS epic #45 的声音设计管线单独增强）

> **GitHub Epic**: #44 (升级) | **Phase**: 2 | **Milestone**: Phase 2 — Interactive + Memory + News

---

### 3.4 内容安全系统 (Safety Check) [Complete]

#### 功能描述
对所有生成内容进行自动安全审查，确保符合儿童内容标准。

#### 审查维度

**负面内容过滤** (禁止)
- 暴力：打斗、血腥、武器
- 恐怖：鬼怪、黑暗、惊悚元素
- 不当语言：脏话、侮辱、歧视
- 成人话题：性、毒品、政治争议

**正向价值引导** (鼓励)
- 性别平等：避免刻板印象（医生总是男性）
- 文化多样性：展现不同文化、种族背景
- 品德教育：友谊、勇气、诚实、同理心
- 环保意识：爱护自然、保护动物

#### 输出
- 安全评分 (0.0-1.0)
- 问题列表（如有）
- 修改建议（如有）

#### 安全标准
- 分数 < 0.7：内容不通过，需要修改
- 分数 0.7-0.85：警告，建议修改
- 分数 > 0.85：通过

---

### 3.5 记忆管理系统 (Memory System) [In Progress]

#### 功能描述
记住每个孩子的创作历史和偏好，实现内容连续性。双层存储架构：SQLite 管理结构化数据（角色档案、偏好计数），ChromaDB 管理语义搜索（画作相似度、故事去重）。

#### 记忆类型

**角色记忆**
- 识别重复角色：如儿童多次画"闪电小狗"
- 保持一致性："闪电小狗"的特征在不同故事中保持
- 角色成长：随时间推移，角色可以"成长"
- 结构化存储：SQLite `characters` 表记录角色名称、视觉特征、性格标签、出场次数

**偏好记忆**
- 兴趣追踪：记录儿童喜欢的主题（恐龙、太空等）
- 互动记录：记录儿童在互动故事中的选择偏好
- 学习进度：根据反馈调整内容难度

**故事关联**
- 历史引用："你还记得上次闪电小狗的冒险吗？"
- 主题延续：优先推荐儿童喜欢的主题
- 避免重复：ChromaDB `story_embeddings` 集合做语义去重，防止生成近似故事

#### 实现方式 — 双层存储架构

| 数据类型 | 存储层 | 原因 |
|----------|--------|------|
| 角色档案（名称、特征、出场数） | SQLite `characters` 表 | 需要精确查询、计数、CRUD |
| 角色语义匹配（跨画作识别） | ChromaDB `children_drawings` | 嵌入相似度匹配，已实现 |
| 偏好与兴趣计数 | SQLite `child_preferences` | 结构化计数器，已实现 |
| 故事去重 | ChromaDB `story_embeddings` | 语义相似度检测近似故事 |
| 跨故事引用上下文 | SQLite `stories` 表 | 按 child_id 查询近期故事，已有表 |

#### 已实现 (What's Built)
- ✅ ChromaDB 向量搜索：`search_similar_drawings` + `store_drawing_embedding`（画作嵌入+角色元数据）
- ✅ 偏好仓储：`PreferenceRepository` 追踪 themes/concepts/interests/recent_choices/morning_show 参与度
- ✅ 偏好感知生成：`_fetch_preference_context()` 将偏好注入互动故事开篇和续段提示词
- ✅ 每日新闻嘉宾角色注入：通过 child_id 查询 ChromaDB 中的重复角色
- ✅ 多管线偏好更新：画作转故事、互动故事、新闻转换、每日新闻均更新偏好数据

#### 待完成 (Remaining Gaps)
- ✅ **角色结构化存储**: `characters` SQLite 表 + `CharacterRepository` CRUD 已实现，画作转故事和互动故事完成时自动同步角色
- 🔲 **角色数据丰富度**: `upsert_character` 仅传入 name/description，未传入 visual_features/traits（schema 已支持但未填充）
- 🔲 **CharacterRepository user_id 作用域**: CharacterRepository 仅按 child_id 隔离，未使用 user_id:child_id 复合键（与 PreferenceRepository 不一致，存在跨用户数据泄露风险）
- 🔲 **故事去重**: `store_story_embedding` 和 `search_similar_stories` MCP 工具已实现，但无 agent 代码调用它们——生成前不查重，生成后不存储嵌入
- ✅ **跨故事记忆**: `story_memory.py` 注入最近 3 条故事摘要到 agent 提示词，支持跨故事引用
- ✅ **记忆 API 暴露**: `GET/DELETE /api/v1/memory/preferences/{child_id}` 和 `GET /api/v1/memory/characters/{child_id}` 已实现
- 🔲 **前端记忆消费**: 前端未调用记忆 API，无角色画廊、无偏好展示、无主题推荐
- ✅ **契约测试覆盖**: PreferenceRepository、偏好作用域、偏好保留、故事记忆、互动记忆契约测试已实现
- ✅ **隐私合规**: `recent_choices` 上限 50 条，主题分数 6 个月衰减，DELETE 端点清除 SQLite + ChromaDB 数据
- 🔲 **主题推荐引擎**: 偏好数据已积累但无推荐算法，未向用户展示个性化主题建议
- 🔲 **角色成长与难度进阶**: 角色特质随时间积累、阅读难度随使用自适应（P3 增强）

#### 内容安全要求
- 隐私保护：仅存储创作内容，不存储个人敏感信息
- COPPA 合规：提供家长可访问的数据删除端点
- 偏好数据最小化：`recent_choices` 限制为最近 50 条，过期主题分数自动衰减

#### 验收标准
- [x] `characters` SQLite 表：child_id, name, description, visual_features, traits, appearance_count, first/last_seen
- [x] `CharacterRepository` 服务：CRUD + 按 child_id 列出角色 + 按出场次数排序
- [x] 画作转故事和互动故事完成时自动同步角色到 `characters` 表
- [ ] `CharacterRepository` 使用 user_id:child_id 复合键隔离（与 PreferenceRepository 一致）
- [ ] `upsert_character` 调用传入 visual_features 和 traits（从视觉分析结果提取）
- [ ] ChromaDB `story_embeddings` 集合：生成前查询语义相似故事，相似度 > 0.9 触发去重
- [x] 生成提示词注入最近 3 条故事摘要，支持跨故事引用
- [x] `GET /api/v1/memory/preferences/{child_id}` 返回偏好数据
- [x] `GET /api/v1/memory/characters/{child_id}` 返回角色列表
- [x] `DELETE /api/v1/memory/preferences/{child_id}` 清除偏好数据（含 ChromaDB 清理）
- [x] `PreferenceRepository` 和 `vector_search_server` 契约测试覆盖
- [x] `recent_choices` 上限 50 条，主题分数 6 个月未更新自动衰减
- [ ] 前端 ProfilePage 展示角色画廊、偏好摘要、主题推荐
- [ ] 主题推荐引擎：基于偏好历史推荐个性化主题

#### 不在本期范围
- 角色成长机制（特质随时间演变）— Phase 3
- 阅读难度自适应（per-child reading_level）— Phase 3
- 跨儿童角色共享

> **GitHub Epic**: #42 | **Phase**: 2 | **Milestone**: Phase 2 — Interactive + Memory + News

---

### 3.6 我的创作库 (My Library) [Not Started]

#### 功能描述
统一的内容库，儿童可以浏览、搜索、收藏和回顾所有创作成果：画作故事、互动叙事和儿童新闻。创作库根据年龄组自适应展示，像一个"个人魔法书架"，随着孩子的创作不断成长。

#### 用户场景
```
儿童打开"我的创作库"
  ↓
看到所有创作，默认按最新排序
  ↓
使用标签筛选类型（画作故事 / 互动故事 / 新闻）
  ↓
可选：按关键词搜索、按日期或收藏排序
  ↓
点击星标收藏最喜欢的故事
  ↓
点击卡片回顾故事，或点击音频图标直接在库中收听
  ↓
家长切换到"成长"视图查看创作时间线
```

#### 功能特性
- **统一浏览**: 所有内容类型在一个视图中，每种类型有专属卡片设计
- **搜索**: 故事文本、标题、主题、角色的全文搜索
- **收藏**: 书签/星标系统，快速访问最爱内容
- **排序**: 按日期（最新/最旧）和收藏优先排序
- **音频预览**: 直接在库卡片上播放故事音频，无需跳转
- **网格/列表切换**: 紧凑网格和详细列表视图间切换
- **年龄适配**: UI 复杂度随年龄组自适应
- **成长时间线**: 可视化图表展示创作频率随时间的变化（详见下方"成长时间线"小节）

#### 成长时间线 (Growth Timeline)

##### 功能描述
家长和 9-12 岁儿童可在创作库顶部切换至"成长"视图，查看创作频率随时间变化的简单图表。帮助家长了解孩子的创作习惯，同时让大孩子对自己的进步产生成就感。

##### 用户场景
```
家长/大孩子打开"我的创作库"
  ↓
点击库顶部"成长"切换按钮
  ↓
看到按周（默认）/月分组的创作数量柱状/折线图
  ↓
切换周/月维度，查看不同时间跨度的趋势
  ↓
新用户看到鼓励性空状态："开始创作吧，你的成长故事从第一幅画开始！"
```

##### 技术实现
- **后端**: `GET /api/v1/library/stats?group_by=week|month` 返回按时段聚合的创作计数，含 `period`、`count`、可选 `content_type` 分类统计
- **前端**: 轻量级图表组件（纯 SVG 或小型库如 recharts-lite），无重型依赖
- **数据源**: 基于现有 library 数据库表按 `created_at` 聚合，无需新存储

##### 年龄与权限
| 条件 | 可见性 |
|------|--------|
| 年龄组 3-5 | 不显示成长视图入口 |
| 年龄组 6-8 | 不显示成长视图入口 |
| 年龄组 9-12 | 显示成长切换按钮和图表 |
| 家长身份 | 始终可见（无论孩子年龄组） |

##### 验收标准
- [ ] `GET /api/v1/library/stats` 返回按周/月分组的创作计数 JSON
- [ ] 响应包含 `period`（日期字符串）、`count`（整数）、可选 `by_type`（按内容类型分类）
- [ ] 前端图表组件渲染柱状或折线图，支持周/月切换
- [ ] 库顶部有切换按钮，在内容视图和成长视图之间切换
- [ ] 仅 9-12 岁和家长身份可见成长视图入口
- [ ] 无创作记录时显示鼓励性空状态消息
- [ ] 图表在移动端视口下响应式适配
- [ ] 不暴露任何个人隐私数据——仅聚合计数

##### 不在本期范围
- 按内容类型分别展示趋势图（仅提供总计数，`by_type` 为可选扩展）
- 与其他儿童的对比/排行榜（隐私与教育理念限制）
- 导出图表为图片/PDF

#### 年龄适配

| 年龄组 | 展示方式 |
|--------|---------|
| 3-5岁 | 大卡片布局（每行最多2个），突出的音频播放按钮，少文字，emoji标签，无搜索栏（家长可搜索），彩色背景 |
| 6-8岁 | 中等卡片（每行2-3个），搜索栏可见，简单排序下拉，星标收藏，主题标签可见 |
| 9-12岁 | 紧凑网格（每行3-4个），完整搜索+排序+筛选控件，字数统计和阅读数据可见，成长时间线可访问，列表/网格切换 |

#### 内容安全要求
- 库中仅显示已通过安全审查的内容（safety_score >= 0.85）
- 收藏/书签操作不需要重新安全检查（内容在创建时已检查）
- 搜索不暴露中间/归档状态的不安全内容——仅已发布/候选生命周期状态可查询

#### 验收标准
- [ ] 库显示所有三种内容类型（画作故事、互动会话、新闻），统一卡片设计
- [ ] 标签筛选正常工作："全部"、"画作故事"、"互动"、"儿童新闻"（合并 news_to_kids + morning_show）
- [ ] 搜索输入可按标题、故事文本预览、主题和角色名筛选
- [ ] 排序选项："最新优先"（默认）、"最旧优先"、"收藏优先"
- [ ] 每个库卡片上有收藏/取消收藏切换，持久化到后端
- [ ] 网格视图切换（网格显示更大缩略图）
- [ ] 所有内容类型的分页（"加载更多"）
- [ ] 库卡片上的音频迷你播放器：点击播放/暂停，无需离开库
- [ ] 库 UI 年龄适配（3-5: 大卡片; 6-8: 均衡; 9-12: 紧凑网格+数据）
- [ ] 成长时间线视图（详细验收标准见上方"成长时间线"小节）
- [ ] 已认证用户看服务端数据，未认证用户回退到本地存储

#### 个人主页统计 (Profile Stats)

##### 功能描述
个人主页展示用户在每个内容类型下的创作计数，替代当前的"最近故事/会话"列表。统计与创作库保持同步——在库中删除内容后，个人主页计数实时更新。

##### 统计分类
| 统计卡片 | 数据来源 | 对应库标签 |
|---------|---------|-----------|
| 画作故事 (Art Stories) | `stories WHERE story_type = 'image_to_story'` | Art Stories |
| 互动故事 (Interactive Tales) | `sessions` | Interactive |
| 儿童新闻 (Kids News) | `stories WHERE story_type IN ('news_to_kids', 'morning_show')` | Kids News |

##### 验收标准
- [ ] 个人主页显示 3 个统计卡片（画作故事、互动故事、儿童新闻），每个显示准确计数
- [ ] 不再显示"最近故事"和"最近会话"列表
- [ ] 在创作库中删除内容后，个人主页计数实时更新（React Query 缓存失效）
- [ ] 每个统计卡片可点击，跳转至创作库对应标签筛选
- [ ] 计数为零时优雅显示"0"

#### 首页最近作品与动态提示 (Homepage Recent Stories & Tips)

##### 功能描述
首页展示用户最近创作的 3 个内容（跨所有类型：画作故事、互动故事、儿童新闻），使用统一创作库 API 作为数据源。提示语在三种功能之间轮播切换。

##### 最近作品
- 数据源：`GET /api/v1/library?sort=newest&limit=3`
- 卡片显示内容类型标签，点击根据类型跳转正确页面
- 列表下方显示"More"按钮，链接至 `/library`

##### 动态提示轮播
| 功能 | 提示语 | 图标 |
|------|--------|------|
| Art to Story | The more colorful your artwork, the more magical your story! | 🎨 |
| Interactive Tales | Every choice leads to a different adventure! Try being brave~ | 🎭 |
| Kids News | Real-world events turned into fun, easy-to-understand stories! | 📰 |

##### 验收标准
- [ ] 首页显示最近 3 个混合类型作品，按时间倒序
- [ ] 每个卡片有类型标签和正确跳转路由
- [ ] "More"按钮跳转至创作库
- [ ] 无内容时显示通用空状态消息
- [ ] 提示语每 5 秒轮播，交叉淡入淡出动画

#### 不在本期范围
- 分享/社交功能（涉及隐私和 COPPA 合规）
- 合集/文件夹整理（Phase 3 考虑）
- 批量操作（保持对儿童简单）
- 完整家长分析仪表盘（Phase 3）
- 导出/下载为 PDF（Phase 3）
- 自定义图片上传头像（涉及内容审核）

> **GitHub Epic**: #49 | **Phase**: MVP | **Milestone**: MVP — Core Story Flow

---

### 3.7 制品生命周期 (Artifact Lifecycle) [In Progress]

#### 功能描述
系统中每一份 AI 生成的内容（图片分析、故事文本、音频、视频）都作为"制品"(Artifact) 被追踪，形成完整的生成溯源链。这使得内容安全审计、版本管理和自动清理成为可能。

#### 核心概念

**制品 (Artifact)**
系统生成的任何内容单元：上传的图片、生成的故事文本、TTS 音频、安全审查结果等。每个制品有唯一 ID、类型、生命周期状态和来源信息。

**生成运行 (Run)**
一次完整的内容生成过程（如一次画作转故事）。包含多个步骤 (AgentStep)，每步产生一个或多个制品。

**溯源链 (Lineage)**
从原始输入到最终输出的完整制品关系图。支持 `derived_from`（派生）、`variant_of`（变体）、`bundled_with`（捆绑）等关系类型。

**生命周期状态**
- `intermediate` — 生成过程中的中间产物（如未通过安全审查的初稿）
- `candidate` — 通过安全审查的候选输出
- `published` — 最终交付给用户的内容
- `archived` — 已归档，等待清理

#### 溯源覆盖范围

| 内容管线 | 溯源状态 | 说明 |
|----------|---------|------|
| 画作转故事 | ✅ 已实现 | 完整 Run/Step/Artifact 记录，制品链接到故事 |
| 互动故事 | 🔲 待实现 | 分支文本和音频未记录为制品 |
| 儿童新闻每日新闻 | 🔲 待实现 | 对话剧本和音频片段未记录为制品 |

#### 保留策略 (Retention)

| 生命周期状态 | 保留时长 | 说明 |
|-------------|---------|------|
| intermediate | 30 天 | 中间产物自动清理 |
| candidate | 90 天 | 未发布的候选内容 |
| archived | 7 天 | 已归档内容快速清理 |
| published | 永久 | 已发布内容永不自动删除 |

保留策略通过定时任务自动执行，保护已发布和规范制品不被误删。

#### 内容安全要求
- 制品系统记录每个制品的安全评分，使管理员可通过 `/admin/artifacts/safety-flagged` 端点查询所有管线中低于阈值的内容
- 溯源链使安全事件可追溯到具体的生成步骤和输入
- 我的创作库仅展示 `published` 或 `candidate` 状态的制品

#### 验收标准
- [x] 制品数据模型和数据库表（6 张表，含索引和迁移）
- [x] 仓储层 CRUD、谱系遍历、搜索、存储统计
- [x] ProvenanceTracker 服务：运行/步骤/制品的完整生命周期编排
- [x] 保留策略定义和管理员清理端点
- [x] 画作转故事管线的完整溯源集成
- [x] 我的创作库封面缩略图通过制品系统解析
- [ ] 互动故事管线的溯源集成
- [ ] 儿童新闻/每日新闻管线的溯源集成
- [ ] 保留清理定时任务自动运行
- [ ] 故事文本制品可链接到故事角色（STORY_TEXT 角色）

#### 不在本期范围
- 前端制品浏览器（管理员工具，Phase 3 考虑）
- 制品版本对比（diff 视图）
- 跨用户制品共享

> **GitHub Epic**: #43 | **Phase**: MVP | **Milestone**: MVP — Core Story Flow

---

### 3.8 TTS & 音频管线 (TTS & Audio Pipeline) [In Progress]

#### 功能描述

可插拔的多供应商 TTS 引擎，支持表情达意的语音朗读、场景风格匹配和声音设计。为所有内容管线（画作转故事、互动故事、每日新闻）提供统一的高质量语音生成能力。

#### 核心能力

**多供应商抽象层**

- `TTSProvider` 协议接口，支持热切换和自动回退
- 当前供应商：OpenAI `tts-1`（基线）、Replicate minimax（表情控制）、ElevenLabs（SOTA 表现力）
- 三级回退链：ElevenLabs → Replicate → OpenAI，确保音频生成从不失败

**表情达意控制**

- 情感参数：`emotion`（happy, sad, neutral, surprised, disgusted），按年龄组过滤
- 语音设置：`stability`、`similarity_boost`、`style`（ElevenLabs 专用）
- 基础参数：`voice`、`speed`、`pitch`、`volume`

**场景风格预设 (Scene Profiles)**

- `bedtime` — 低稳定性、慢速、温柔声音（适合睡前故事）
- `adventure` — 高表现力、正常速度、活力声音（适合冒险故事）
- `spooky` — 中等稳定性、稍慢、低沉声音（适合神秘故事，9-12岁）
- `educational` — 高稳定性、清晰、中性声音（适合知识内容）

**声音设计管线** [Phase 2+]

- 可选环境音底层 + 事件音效混合（ducking narration）
- 可按请求开启/关闭，可配置强度级别

#### 供应商对比

| 供应商 | 模型 | 优势 | 延迟 | 语音数 |
|--------|------|------|------|--------|
| OpenAI | tts-1 | 稳定基线、低成本 | ~200ms | 6 |
| Replicate | minimax/speech-02-turbo | 情感/音调控制 | ~300ms | 16 |
| ElevenLabs | eleven_flash_v2_5 | SOTA 表现力、大语音库 | ~75ms | 8 (策划) |

#### 年龄适配

| 年龄组 | 默认语速 | 可用情感 | 可见语音数 | 场景预设 |
|--------|---------|---------|-----------|---------|
| 3-5岁 | 0.9x | happy, neutral | 最多 4 个（友好标签） | bedtime, adventure |
| 6-8岁 | 1.0x | happy, sad, surprised, neutral | 完整目录（简单标签） | 全部 |
| 9-12岁 | 1.1x | 全部（除 angry/fearful） | 完整目录（含供应商信息） | 全部 |

#### 已实现 (What's Built)

- ✅ `TTSProvider` 协议接口 + `OpenAITTSProvider` + `ReplicateTTSProvider`（#149）
- ✅ 情感参数 + 年龄过滤（`AGE_EMOTION_MAP`）
- ✅ Replicate → OpenAI 双级回退 + 重试
- ✅ `list_available_voices` MCP 工具（合并 OpenAI + Replicate 目录）
- ✅ `generate_audio_batch` MCP 工具（多段批量生成）
- ✅ 多角色 TTS 编排（每日新闻）
- ✅ 按需音频生成 API（`/api/v1/audio/generate`）
- ✅ 契约测试：供应商协议形状、情感过滤、向后兼容

#### 待完成 (Remaining Gaps)

- 🔲 **ElevenLabs 供应商**: 添加 `ElevenLabsTTSProvider`，策划儿童叙述语音目录（#243）
- 🔲 **语音目录 REST API**: 暴露 `GET /api/v1/audio/voices` 端点供前端消费（#244）
- 🔲 **场景风格预设**: 按故事类型自动选择 stability/style/speed 组合（#245）
- 🔲 **语音预览播放**: 后端 `GET /api/v1/audio/preview` 端点生成 2-4 秒样本音频（固定安全预览文本），磁盘缓存 `data/audio/previews/{provider}_{voice_id}.mp3`，前端 `VoicePicker` 调用并通过 Howl 播放。同一语音二次点击即停，切换语音自动停止上一段。每 IP 每分钟限 10 次请求。（#333, #334, #336）
- 🔲 **语音供应商透传**: 前端 VoicePicker 选择的 `provider` 字段须随画作转故事请求一起发送到后端，确保最终语音与预览一致。（#335）
- 🔲 **评估框架**: MOS 评分标准 + 延迟/成本指标 + 黄金故事集 A/B 测试（#246）
- 🔲 **声音设计**: 环境音 + 音效混合管线（Phase 2+）
- 🔲 **流式 TTS**: 支持边生成边播放（ElevenLabs Flash 模型天然支持）

#### 验收标准

- [ ] 供应商接口支持至少 3 个供应商（OpenAI + Replicate + ElevenLabs）
- [ ] API 支持表情参数且不破坏现有客户端
- [ ] 场景风格预设可按请求指定或从故事类型自动推断
- [ ] 每个年龄组至少 5 个故事样本跨供应商基准测试
- [ ] P95 生成延迟和每分钟成本在日志/指标中追踪
- [ ] 前端语音选择器显示年龄适配的语音目录 + 3-5 秒预览
- [ ] 声音设计模式可按请求开启/关闭
- [ ] 三级回退链确保音频生成 99.9% 可用性

#### 不在本期范围

- 全自定义语音克隆（→ #150，Phase 3）
- 全自动配乐生成
- 实时语音对话（非 TTS 场景）

> **GitHub Epic**: #45 | **Phase**: 2 | **Milestone**: Phase 2 — Interactive + Memory + News

---

## 4. 用户旅程

### 4.1 首次使用

```
Step 1: 家长注册账号
  ↓
Step 2: 创建儿童档案（年龄、兴趣）
  ↓
Step 3: 儿童上传第一幅画作
  ↓
Step 4: AI 生成第一个故事
  ↓
Step 5: 儿童听故事（文字 + 语音）
  ↓
Step 6: 系统记录：画作内容、兴趣标签、互动反馈
```

### 4.2 日常使用

```
场景 A: 画作转故事
  儿童画画 → 上传 → 5-10秒生成 → 听故事

场景 B: 互动故事
  选择主题 → 开始故事 → 做选择 → 继续故事 → 结局（重复2-4轮）

场景 C: 儿童新闻（统一入口）
  点击"儿童新闻"卡片 → 进入新闻中心
  → 快速阅读模式：家长粘贴新闻 → AI 简化 → 和孩子一起阅读
  → 每日新闻模式：生成对话播客 → 听好奇宝宝和趣味专家聊天
  → 闪电小狗作为嘉宾出场 → 学到新知识
  → 创作库"儿童新闻"标签页统一查看所有新闻内容
```

### 4.3 长期使用

```
Week 1: 创作 3 个故事，系统识别兴趣：动物、冒险
  ↓
Week 2: 系统推荐相关主题，儿童创作角色"闪电小狗"
  ↓
Week 3: 系统记住"闪电小狗"，在新故事中继续使用
  ↓
Week 4: 角色"成长"，闪电小狗学会了新技能
  ↓
Month 3: 儿童创作了 20+ 个故事，形成自己的"故事宇宙"
```

---

## 5. 功能优先级

### MVP (Minimum Viable Product) - 第一阶段

**必须有**:
- ✅ 画作转故事（基础功能）
- ✅ 线性故事生成
- ✅ 内容安全审查
- ✅ 语音朗读（TTS）
- ✅ 基础记忆（识别重复角色）
- 🔲 我的创作库（统一内容浏览、搜索、收藏）

### Phase 2 - 第二阶段 (Launch Gate — §3.9)

**生产发布前置条件 (blocks public launch)**:
- 🔲 每用户每日生成配额 + 用量追踪（§3.9.1）
- 🔲 邮箱注册 + 邮件验证（§3.9.2）
- 🔲 Railway 后端部署 + Vercel 前端部署（§3.9.3）
- 🔲 "Buy Me a Coffee" 捐赠入口（§3.9.4）

**应该有**:
- ✅ 互动故事生成（多分支）— 核心流程已完成，增强功能见 §3.2
- 🔲 互动故事增强（✅ 偏好感知生成、🔲 角色延续、🔲 会话恢复、🔲 故事回放）
- 🔲 儿童新闻每日新闻（双角色对话播客 + 可视化动画 + 每日推送）— 见 §3.3
- 🔲 高级记忆（角色结构化存储、故事去重、记忆 API、隐私合规）
- 🔲 TTS & 音频管线升级（ElevenLabs SOTA 供应商 + 场景预设 + 语音选择器）— 见 §3.8
- 🔲 频道订阅系统（Daily Drop 自动生成）

### 跨阶段 — 响应式 UI 质量 (Responsive UI Polish) [In Progress]

**必须有** (MVP 质量门槛):
- 🔲 全局导航栏移动端适配（汉堡菜单或图标化）
- 🔲 Library 筛选标签横向滚动（移动端不截断）
- 🔲 Library 卡片标题双行截断（避免过度截断）
- 🔲 Upload 页步骤排序修复（CTA 按钮位置）
- 🔲 Login 页移动端 Logo 裁剪修复
- 🔲 Profile 页移动端布局修复（Edit Profile 按钮重叠）
- 🔲 UploadPage React 钩子顺序修复（useState 在条件 return 之后调用，违反 React 规则，可能导致状态损坏）

**应该有**:
- 🔲 Library「New」徽章时效规则（创建 7 天后自动消失）
- 🔲 Library 字数标签友好化（`60w` → `~1 分钟` 或 `60 words`）
- 🔲 Upload 语音选择器折叠/分页（28 个选项过长）
- 🔲 React Router v7 future flag 迁移
- 🔲 Upload 页 DOM 嵌套校验错误修复
- 🔲 StoryPage 成功横幅条件显示（仅在 `justGenerated === true` 时出现，从 Library 打开时不显示）
- 🔲 LibraryPage 每标签页独立空状态 UI（含 CTA 指引至对应创建页）

**可以有**:
- 🔲 Library/Profile 卡片 hover 反馈（桌面端 lift 效果）
- 🔲 UploadPage 艺术风格选择器可视化卡片（色块/渐变背景）— 完成 §3.1.1 验收标准「可视化卡片」
- 🔲 AvatarDisplay 组件去重（统一为目录版本，平级文件改为重新导出或删除）

### Phase 3 - 第三阶段

**可以有**:
- 动态绘本（画作元素动画）
- 视频生成（完整动画）
- 多语言支持
- 家长控制面板
- 激励勋章系统

---

## 6. 成功指标 (KPI)

### 使用指标
- **活跃度**: 儿童每周使用 3+ 次
- **完成率**: 互动故事完成率 > 80%
- **创作量**: 平均每用户每周创作 2+ 个故事

### 质量指标
- **家长满意度**: > 4.5/5.0
- **内容安全**: 不当内容通过率 < 0.1%
- **响应速度**: 故事生成 < 10 秒

### 教育效果
- **创造力**: 儿童主动创作频率提升 30%
- **阅读兴趣**: 阅读时长增加 50%
- **知识获取**: 能用自己的话解释新概念

---

## 7. 用户反馈与迭代

### 收集渠道
- 家长评分和评论
- 儿童互动行为分析（点击、完成率）
- A/B 测试不同故事风格

### 迭代方向
- 根据年龄段调整内容复杂度
- 优化互动分支设计
- 扩展兴趣主题库
- 改进安全审查准确性

---

## 3.9 Production Launch & Cost Sustainability [Phase 2 — Launch Gate]

Goal: deploy the product to a public URL so real users can register and use it, while keeping AI API costs predictable.

### 3.9.1 Per-User Generation Quota

Every authenticated user has a daily generation quota (default: **3 AI generations per day**, resets midnight UTC).
Quota covers: image-to-story, interactive story opening, morning show episode generation.

**Acceptance Criteria:**
- [ ] `usage_repository` tracks (user_id, date, feature, count) in SQLite
- [ ] Quota middleware returns HTTP 429 with `{"quota_remaining": 0, "resets_at": "..."}` when exceeded
- [ ] Frontend shows "X / 3 generations used today" on UploadPage and InteractiveStory start screen
- [ ] Quota is configurable via env var `DAILY_GENERATION_QUOTA` (default 3)

### 3.9.2 Email-Based Account Registration

Users register with email + password. A verification email must be confirmed before AI features are accessible.
Prevents throwaway accounts that drain quota.

**Acceptance Criteria:**
- [ ] Registration requires email + password (min 8 chars)
- [ ] Verification email sent on signup; unverified accounts blocked from AI endpoints
- [ ] Password reset flow (email link)
- [ ] Implementation: Supabase Auth (free tier) or self-hosted with FastAPI + email via SendGrid free tier

### 3.9.3 Production Hosting

| Layer | Service | Notes |
|-------|---------|-------|
| Frontend | Vercel (free) | Auto-deploys from `main` |
| Backend | Railway ($5–7/month) | FastAPI + SQLite + ChromaDB on same instance |
| Domain | Optional Cloudflare domain | ~$10/year |

**Acceptance Criteria:**
- [ ] Backend live at a stable public URL with all env vars set
- [ ] Frontend live on Vercel pointing to backend URL via `VITE_API_BASE_URL`
- [ ] CORS configured for production frontend origin
- [ ] Health check endpoint returns 200

### 3.9.4 "Buy Me a Coffee" Donation Widget

A voluntary tip widget on the home or profile page. Non-commercial — users choose to donate.
Lets the creator receive appreciation without gating any features.

**Acceptance Criteria:**
- [ ] BMC widget/button visible on HomePage or ProfilePage
- [ ] Clicking opens buymeacoffee.com/[creator] in a new tab
- [ ] Does not obstruct any child-facing UI

---

## 8. 风险与限制

### 产品风险
- **内容质量**: AI 生成内容可能不够吸引人
  - 缓解：持续优化 Agent prompt，A/B 测试

- **安全漏洞**: AI 可能生成不当内容
  - 缓解：多层安全审查，人工抽检

- **隐私担忧**: 家长担心儿童数据安全
  - 缓解：符合 COPPA 标准，透明的隐私政策

- **API 成本失控**: 真实用户大量使用 AI 接口导致费用超出预算
  - 缓解：每用户每日配额限制（§3.9.1）+ Anthropic/OpenAI 控制台月度消费上限（外部硬限制）

### 技术限制
- **生成速度**: AI 生成需要 5-10 秒
  - 缓解：优化模型，使用流式输出

- **成本**: TTS 和 AI 调用成本较高
  - 缓解：每用户配额限制（3次/天）；缓存常用内容；批量处理

---

## 9. 竞品分析

### 现有产品

| 产品 | 特点 | 不足 |
|------|------|------|
| Story.com | AI 生成故事 | 无个性化，无记忆 |
| Storybird | 图片配文字 | 非 AI，需人工创作 |
| Epic! | 电子书库 | 被动阅读，无创作 |

### 我们的优势
- ✅ 基于儿童画作的个性化创作
- ✅ 记忆系统实现故事连续性
- ✅ 互动式多分支故事
- ✅ 严格的内容安全审查
- ✅ 教育目标融合

---

## 附录

### A. 相关文档
- [DOMAIN.md](./DOMAIN.md) - 领域背景和核心概念
- [ARCHITECTURE.md](../architecture/ARCHITECTURE.md) - 技术架构设计
- [DEVELOPMENT_WORKFLOW.md](../guides/DEVELOPMENT_WORKFLOW.md) - 开发工作流
- [README.md](../../README.md) - 项目简介和快速开始

### B. 参考标准
- COPPA (儿童在线隐私保护法)
- Common Core State Standards (分年龄阅读标准)
- ESRB Rating System (娱乐软件分级)
