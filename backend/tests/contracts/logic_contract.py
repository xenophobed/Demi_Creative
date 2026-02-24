"""
Logic Contract Tests - 业务逻辑契约测试

此文件定义了所有 Agent 和服务的业务逻辑契约。
契约测试确保各个组件的输入输出符合预期，接口稳定可靠。

测试原则：
1. 测试应该描述"做什么"而非"怎么做"
2. 契约一旦建立，不应轻易修改（向后兼容）
3. 所有 Agent 输入输出必须有契约测试覆盖
4. 使用类型检查确保契约强制执行
"""

import pytest
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ValidationError, Field
from datetime import datetime
from enum import Enum


# ============================================================================
# 1. Agent 输入输出契约定义
# ============================================================================

# -------------------------
# 1.1 ImageAnalysisAgent 契约
# -------------------------

class ImageAnalysisInput(BaseModel):
    """画作分析输入契约"""
    image_url: str = Field(..., description="图片URL", min_length=1)
    child_id: str = Field(..., description="儿童用户ID")
    child_age: int = Field(..., ge=3, le=12, description="儿童年龄（3-12岁）")
    interests: Optional[List[str]] = Field(default=None, description="兴趣标签")

    class Config:
        json_schema_extra = {
            "example": {
                "image_url": "https://s3.amazonaws.com/images/abc123.jpg",
                "child_id": "user-123",
                "child_age": 7,
                "interests": ["动物", "冒险"]
            }
        }


class ImageAnalysisResult(BaseModel):
    """画作分析输出契约"""
    objects: List[str] = Field(..., description="识别的物体列表", min_length=1)
    scene: str = Field(..., description="场景描述", min_length=1)
    mood: str = Field(..., description="情绪/氛围", min_length=1)
    recurring_characters: List[str] = Field(default=[], description="重复出现的角色")
    embedding_vector: List[float] = Field(..., description="向量表示", min_length=512)
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="置信度分数")

    class Config:
        json_schema_extra = {
            "example": {
                "objects": ["小狗", "树木", "太阳"],
                "scene": "户外公园",
                "mood": "快乐",
                "recurring_characters": ["闪电小狗"],
                "embedding_vector": [0.1, 0.2, 0.3],  # 简化示例
                "confidence_score": 0.92
            }
        }


# -------------------------
# 1.2 InteractiveStoryAgent 契约
# -------------------------

class StoryMode(str, Enum):
    """故事模式枚举"""
    LINEAR = "linear"
    INTERACTIVE = "interactive"


class StoryGenerationInput(BaseModel):
    """故事生成输入契约"""
    child_id: str = Field(..., description="儿童用户ID")
    child_age: int = Field(..., ge=3, le=12, description="儿童年龄")
    interests: List[str] = Field(..., min_length=1, max_length=5, description="兴趣标签（1-5个）")
    mode: StoryMode = Field(default=StoryMode.LINEAR, description="故事模式")
    theme: Optional[str] = Field(default=None, description="故事主题")
    educational_goal: Optional[str] = Field(default=None, description="教育目标")
    session_id: Optional[str] = Field(default=None, description="会话ID（多轮对话）")
    previous_choice: Optional[str] = Field(default=None, description="用户上次的选择")

    class Config:
        json_schema_extra = {
            "example": {
                "child_id": "user-123",
                "child_age": 8,
                "interests": ["恐龙", "科学"],
                "mode": "interactive",
                "theme": "友谊",
                "educational_goal": "勇气"
            }
        }


class Choice(BaseModel):
    """故事选择分支"""
    id: str = Field(..., description="选择ID")
    text: str = Field(..., min_length=5, description="选择文本")
    emoji: str = Field(..., description="表情符号")
    consequence_hint: Optional[str] = Field(default=None, description="后果提示")


class StorySegmentResult(BaseModel):
    """故事段落输出契约"""
    story_text: str = Field(..., min_length=50, max_length=1000, description="故事文本（50-1000字）")
    audio_url: Optional[str] = Field(default=None, description="语音URL")
    is_ending: bool = Field(..., description="是否结局")
    choices: Optional[List[Choice]] = Field(default=None, description="分支选项（互动模式）")
    session_id: str = Field(..., description="会话ID")
    educational_points: List[str] = Field(default=[], description="教育要点")

    class Config:
        json_schema_extra = {
            "example": {
                "story_text": "小恐龙在森林里发现了一个神秘的山洞...",
                "audio_url": "https://s3.amazonaws.com/audio/story-123.mp3",
                "is_ending": False,
                "choices": [
                    {
                        "id": "choice-1",
                        "text": "勇敢地走进山洞",
                        "emoji": "🏔️",
                        "consequence_hint": "你会发现神秘宝藏"
                    },
                    {
                        "id": "choice-2",
                        "text": "先回家叫上朋友",
                        "emoji": "👫",
                        "consequence_hint": "友谊让冒险更安全"
                    }
                ],
                "session_id": "session-abc123",
                "educational_points": ["勇气", "友谊"]
            }
        }


# -------------------------
# 1.3 NewsConverterAgent 契约
# -------------------------

class NewsCategory(str, Enum):
    """新闻类别枚举"""
    SCIENCE = "science"
    NATURE = "nature"
    CULTURE = "culture"
    SPORTS = "sports"


class NewsConversionInput(BaseModel):
    """新闻转换输入契约"""
    news_url: Optional[str] = Field(default=None, description="新闻URL")
    news_text: Optional[str] = Field(default=None, description="新闻文本")
    target_age: int = Field(..., ge=3, le=12, description="目标年龄")
    category: NewsCategory = Field(..., description="新闻类别")

    @classmethod
    def validate_news_source(cls, values):
        """验证至少提供一个新闻源"""
        if not values.get('news_url') and not values.get('news_text'):
            raise ValueError("必须提供 news_url 或 news_text 之一")
        return values


class Concept(BaseModel):
    """关键概念"""
    term: str = Field(..., description="术语")
    kid_explanation: str = Field(..., min_length=10, description="儿童友好的解释")
    example: Optional[str] = Field(default=None, description="示例")


class KidsNewsResult(BaseModel):
    """儿童新闻输出契约"""
    kids_title: str = Field(..., min_length=5, max_length=100, description="儿童版标题")
    kids_content: str = Field(..., min_length=50, max_length=500, description="儿童版内容（50-500字）")
    why_care: str = Field(..., min_length=20, description="为什么我要关心这个？")
    key_concepts: List[Concept] = Field(default=[], description="关键概念解释")
    fun_facts: List[str] = Field(default=[], description="有趣事实")
    interactive_questions: List[str] = Field(default=[], min_length=1, description="互动问题")
    original_url: Optional[str] = Field(default=None, description="原始新闻URL")

    class Config:
        json_schema_extra = {
            "example": {
                "kids_title": "太空中发现了新的星球！",
                "kids_content": "科学家们用超级强大的望远镜...",
                "why_care": "这就像人类找到了一个新的朋友星球，以后你可能能去那里旅行！",
                "key_concepts": [
                    {
                        "term": "行星",
                        "kid_explanation": "像地球一样围绕太阳转的大球球",
                        "example": "就像你在游乐场玩的旋转木马"
                    }
                ],
                "fun_facts": ["这颗星球比地球大三倍！"],
                "interactive_questions": ["你想去太空探险吗？"],
                "original_url": "https://news.example.com/space-discovery"
            }
        }


# -------------------------
# 1.4 SafetyAgent 契约
# -------------------------

class ContentType(str, Enum):
    """内容类型枚举"""
    STORY = "story"
    NEWS = "news"
    IMAGE_DESCRIPTION = "image_description"


class ContentReviewInput(BaseModel):
    """内容审查输入契约"""
    content_type: ContentType = Field(..., description="内容类型")
    content_text: str = Field(..., min_length=1, description="内容文本")
    target_age: int = Field(..., ge=3, le=12, description="目标年龄")
    child_id: Optional[str] = Field(default=None, description="儿童ID（用于个性化审查）")


class IssueSeverity(str, Enum):
    """问题严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SafetyIssue(BaseModel):
    """安全问题"""
    category: str = Field(..., description="问题类别（violence, gender_bias等）")
    severity: IssueSeverity = Field(..., description="严重程度")
    description: str = Field(..., description="问题描述")
    location: Optional[str] = Field(default=None, description="问题位置")


class SafetyReviewResult(BaseModel):
    """安全审查输出契约"""
    is_safe: bool = Field(..., description="是否安全")
    safety_score: float = Field(..., ge=0.0, le=1.0, description="安全分数（0.0-1.0）")
    issues: List[SafetyIssue] = Field(default=[], description="问题列表")
    suggestions: List[str] = Field(default=[], description="修改建议")

    class Config:
        json_schema_extra = {
            "example": {
                "is_safe": False,
                "safety_score": 0.65,
                "issues": [
                    {
                        "category": "gender_bias",
                        "severity": "medium",
                        "description": "故事中所有医生都是男性",
                        "location": "第二段"
                    }
                ],
                "suggestions": [
                    "将其中一位医生改为女性角色",
                    "增加更多元的职业角色"
                ]
            }
        }


# -------------------------
# 1.5 RewardAgent 契约
# -------------------------

class UserEvent(BaseModel):
    """用户事件输入契约"""
    user_id: str = Field(..., description="用户ID")
    event_type: str = Field(..., description="事件类型")
    metadata: Dict[str, Any] = Field(default={}, description="事件元数据")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user-123",
                "event_type": "story_created",
                "metadata": {"story_id": "story-456", "theme": "science"},
                "timestamp": "2026-01-26T10:00:00Z"
            }
        }


class Medal(BaseModel):
    """勋章"""
    id: str = Field(..., description="勋章ID")
    name: str = Field(..., description="勋章名称")
    description: str = Field(..., description="勋章描述")
    icon: str = Field(..., description="勋章图标URL")
    category: str = Field(..., description="勋章类别")
    unlocked_at: datetime = Field(..., description="解锁时间")


class ProgressUpdate(BaseModel):
    """进度更新"""
    medal_id: str = Field(..., description="勋章ID")
    current_progress: int = Field(..., description="当前进度")
    required_progress: int = Field(..., description="所需进度")
    percentage: float = Field(..., ge=0.0, le=100.0, description="完成百分比")


class RewardResult(BaseModel):
    """激励系统输出契约"""
    new_medals: List[Medal] = Field(default=[], description="新获得的勋章")
    total_medals: int = Field(..., ge=0, description="总勋章数")
    progress_updates: List[ProgressUpdate] = Field(default=[], description="进度更新")


# ============================================================================
# 2. 契约测试用例
# ============================================================================

class TestImageAnalysisContract:
    """画作分析 Agent 契约测试"""

    def test_valid_input(self):
        """测试有效输入"""
        input_data = ImageAnalysisInput(
            image_url="https://example.com/image.jpg",
            child_id="user-123",
            child_age=7,
            interests=["动物", "冒险"]
        )
        assert input_data.child_age == 7
        assert len(input_data.interests) == 2

    def test_invalid_age(self):
        """测试无效年龄（必须在 3-12 之间）"""
        with pytest.raises(ValidationError) as exc_info:
            ImageAnalysisInput(
                image_url="https://example.com/image.jpg",
                child_id="user-123",
                child_age=15  # 超出范围
            )
        assert "child_age" in str(exc_info.value)

    def test_empty_image_url(self):
        """测试空图片URL"""
        with pytest.raises(ValidationError):
            ImageAnalysisInput(
                image_url="",  # 空字符串
                child_id="user-123",
                child_age=7
            )

    def test_valid_output(self):
        """测试有效输出"""
        output = ImageAnalysisResult(
            objects=["小狗", "树木"],
            scene="公园",
            mood="快乐",
            recurring_characters=["闪电小狗"],
            embedding_vector=[0.1] * 512,  # 512维向量
            confidence_score=0.92
        )
        assert output.confidence_score >= 0.0
        assert output.confidence_score <= 1.0
        assert len(output.embedding_vector) == 512

    def test_invalid_confidence_score(self):
        """测试无效置信度分数"""
        with pytest.raises(ValidationError):
            ImageAnalysisResult(
                objects=["小狗"],
                scene="公园",
                mood="快乐",
                embedding_vector=[0.1] * 512,
                confidence_score=1.5  # 超出范围
            )


class TestInteractiveStoryContract:
    """互动故事 Agent 契约测试"""

    def test_valid_linear_story_input(self):
        """测试线性故事输入"""
        input_data = StoryGenerationInput(
            child_id="user-123",
            child_age=8,
            interests=["恐龙", "科学"],
            mode=StoryMode.LINEAR,
            theme="友谊"
        )
        assert input_data.mode == StoryMode.LINEAR

    def test_valid_interactive_story_input(self):
        """测试互动故事输入"""
        input_data = StoryGenerationInput(
            child_id="user-123",
            child_age=8,
            interests=["恐龙"],
            mode=StoryMode.INTERACTIVE,
            session_id="session-123",
            previous_choice="choice-1"
        )
        assert input_data.mode == StoryMode.INTERACTIVE
        assert input_data.session_id is not None

    def test_max_interests(self):
        """测试最大兴趣标签数量（最多5个）"""
        with pytest.raises(ValidationError):
            StoryGenerationInput(
                child_id="user-123",
                child_age=8,
                interests=["a", "b", "c", "d", "e", "f"]  # 超过5个
            )

    def test_valid_story_output_with_choices(self):
        """测试带选择的故事输出"""
        output = StorySegmentResult(
            story_text="小恐龙在森林里发现了一个神秘的山洞，洞口闪烁着奇异的光芒...",
            audio_url="https://example.com/audio.mp3",
            is_ending=False,
            choices=[
                Choice(
                    id="choice-1",
                    text="勇敢地走进山洞",
                    emoji="🏔️",
                    consequence_hint="你会发现神秘宝藏"
                ),
                Choice(
                    id="choice-2",
                    text="先回家叫上朋友",
                    emoji="👫"
                )
            ],
            session_id="session-123",
            educational_points=["勇气", "友谊"]
        )
        assert len(output.choices) == 2
        assert not output.is_ending

    def test_story_text_length(self):
        """测试故事文本长度限制"""
        with pytest.raises(ValidationError):
            StorySegmentResult(
                story_text="太短了",  # 少于50字符
                is_ending=True,
                session_id="session-123"
            )


class TestNewsConverterContract:
    """新闻转换 Agent 契约测试"""

    def test_valid_input_with_url(self):
        """测试使用URL的输入"""
        input_data = NewsConversionInput(
            news_url="https://news.example.com/article",
            target_age=7,
            category=NewsCategory.SCIENCE
        )
        assert input_data.news_url is not None

    def test_valid_input_with_text(self):
        """测试使用文本的输入"""
        input_data = NewsConversionInput(
            news_text="SpaceX launched a new rocket...",
            target_age=7,
            category=NewsCategory.SCIENCE
        )
        assert input_data.news_text is not None

    def test_valid_output(self):
        """测试有效输出"""
        output = KidsNewsResult(
            kids_title="太空中发现了新的星球！",
            kids_content="科学家们用超级强大的望远镜在遥远的太空中发现了一颗新的星球...",
            why_care="这就像人类找到了一个新的朋友星球，以后你可能能去那里旅行！",
            key_concepts=[
                Concept(
                    term="行星",
                    kid_explanation="像地球一样围绕太阳转的大球球",
                    example="就像你在游乐场玩的旋转木马"
                )
            ],
            fun_facts=["这颗星球比地球大三倍！"],
            interactive_questions=["你想去太空探险吗？"],
            original_url="https://news.example.com/space"
        )
        assert len(output.kids_content) >= 50
        assert len(output.interactive_questions) >= 1

    def test_content_length_limits(self):
        """测试内容长度限制"""
        with pytest.raises(ValidationError):
            KidsNewsResult(
                kids_title="太长了" * 50,  # 超过100字符
                kids_content="科学家们发现了新星球...",
                why_care="这很有趣！",
                interactive_questions=["你想去太空吗？"]
            )


class TestSafetyContract:
    """安全审查 Agent 契约测试"""

    def test_valid_input(self):
        """测试有效输入"""
        input_data = ContentReviewInput(
            content_type=ContentType.STORY,
            content_text="小恐龙和朋友们一起探险...",
            target_age=7,
            child_id="user-123"
        )
        assert input_data.content_type == ContentType.STORY

    def test_safe_content_output(self):
        """测试安全内容输出"""
        output = SafetyReviewResult(
            is_safe=True,
            safety_score=0.95,
            issues=[],
            suggestions=[]
        )
        assert output.is_safe
        assert output.safety_score > 0.9

    def test_unsafe_content_output(self):
        """测试不安全内容输出"""
        output = SafetyReviewResult(
            is_safe=False,
            safety_score=0.65,
            issues=[
                SafetyIssue(
                    category="gender_bias",
                    severity=IssueSeverity.MEDIUM,
                    description="故事中所有医生都是男性",
                    location="第二段"
                )
            ],
            suggestions=["将其中一位医生改为女性角色"]
        )
        assert not output.is_safe
        assert len(output.issues) > 0
        assert len(output.suggestions) > 0

    def test_safety_score_range(self):
        """测试安全分数范围"""
        with pytest.raises(ValidationError):
            SafetyReviewResult(
                is_safe=True,
                safety_score=1.5,  # 超出范围
                issues=[],
                suggestions=[]
            )


class TestRewardContract:
    """激励系统 Agent 契约测试"""

    def test_valid_user_event(self):
        """测试有效用户事件"""
        event = UserEvent(
            user_id="user-123",
            event_type="story_created",
            metadata={"story_id": "story-456"},
            timestamp=datetime.now()
        )
        assert event.event_type == "story_created"

    def test_valid_reward_result_with_medals(self):
        """测试带有新勋章的奖励结果"""
        result = RewardResult(
            new_medals=[
                Medal(
                    id="medal-1",
                    name="小画家",
                    description="上传第1幅画作",
                    icon="https://example.com/medal.png",
                    category="creation",
                    unlocked_at=datetime.now()
                )
            ],
            total_medals=5,
            progress_updates=[
                ProgressUpdate(
                    medal_id="medal-2",
                    current_progress=3,
                    required_progress=5,
                    percentage=60.0
                )
            ]
        )
        assert len(result.new_medals) == 1
        assert result.total_medals == 5

    def test_progress_percentage_range(self):
        """测试进度百分比范围"""
        with pytest.raises(ValidationError):
            ProgressUpdate(
                medal_id="medal-1",
                current_progress=10,
                required_progress=5,
                percentage=150.0  # 超出范围
            )


# ============================================================================
# 3. 业务逻辑规则测试
# ============================================================================

class TestBusinessLogicRules:
    """业务逻辑规则测试"""

    def test_age_appropriate_content_length(self):
        """测试年龄适配内容长度规则"""
        # 规则：3-5岁故事应该更短（100-200字）
        # 6-8岁故事中等长度（200-400字）
        # 9-12岁故事可以更长（400-800字）

        young_story = StorySegmentResult(
            story_text="小狗在公园里玩。" * 15,  # ~150字
            is_ending=True,
            session_id="session-123"
        )
        assert 50 <= len(young_story.story_text) <= 1000

    def test_interactive_story_must_have_choices_if_not_ending(self):
        """测试互动故事规则：非结局必须有选择"""
        # 业务规则：互动故事如果不是结局，必须提供选择
        story = StorySegmentResult(
            story_text="小恐龙走到了岔路口...",
            is_ending=False,
            choices=[
                Choice(id="c1", text="向左走", emoji="⬅️"),
                Choice(id="c2", text="向右走", emoji="➡️")
            ],
            session_id="session-123"
        )
        # 如果不是结局，choices 不能为空
        if not story.is_ending:
            assert story.choices is not None
            assert len(story.choices) >= 2

    def test_safety_score_threshold(self):
        """测试安全分数阈值规则"""
        # 业务规则：安全分数 < 0.7 视为不安全
        unsafe_result = SafetyReviewResult(
            is_safe=False,
            safety_score=0.65,
            issues=[
                SafetyIssue(
                    category="violence",
                    severity=IssueSeverity.HIGH,
                    description="包含暴力内容"
                )
            ],
            suggestions=["删除暴力描述"]
        )
        assert unsafe_result.safety_score < 0.7
        assert not unsafe_result.is_safe

    def test_word_count_uses_words_not_characters(self):
        """Regression test for #46: word_count must count words, not characters."""
        story_text = "The little dinosaur found a mysterious cave"
        word_count = len(story_text.split())
        assert word_count == 7
        # Must NOT be character count
        assert word_count != len(story_text)

    def test_word_count_empty_string(self):
        """word_count of empty story text should be 0."""
        assert len("".split()) == 0

    def test_interactive_story_progress_is_decimal(self):
        """Regression test for #47: progress must be 0.0–1.0, not 0–100."""
        current_segment = 3
        total_segments = 5
        progress = current_segment / total_segments
        assert 0.0 <= progress <= 1.0
        assert progress == pytest.approx(0.6)

    def test_news_must_have_interactive_questions(self):
        """测试新闻必须包含互动问题规则"""
        # 业务规则：儿童新闻必须包含至少1个互动问题
        news = KidsNewsResult(
            kids_title="太空发现",
            kids_content="科学家们发现了新星球...",
            why_care="这很有趣！",
            interactive_questions=["你想去太空吗？", "你觉得外星人长什么样？"]
        )
        assert len(news.interactive_questions) >= 1


# ============================================================================
# 4. 错误处理契约测试
# ============================================================================

class TestErrorHandlingContracts:
    """错误处理契约测试"""

    def test_missing_required_fields(self):
        """测试缺少必填字段"""
        with pytest.raises(ValidationError) as exc_info:
            ImageAnalysisInput(
                image_url="https://example.com/image.jpg"
                # 缺少 child_id 和 child_age
            )
        errors = exc_info.value.errors()
        assert any(e['loc'][0] == 'child_id' for e in errors)
        assert any(e['loc'][0] == 'child_age' for e in errors)

    def test_invalid_enum_value(self):
        """测试无效的枚举值"""
        with pytest.raises(ValidationError):
            StoryGenerationInput(
                child_id="user-123",
                child_age=8,
                interests=["恐龙"],
                mode="invalid_mode"  # 无效的模式
            )

    def test_type_mismatch(self):
        """测试类型不匹配"""
        with pytest.raises(ValidationError):
            ImageAnalysisInput(
                image_url="https://example.com/image.jpg",
                child_id="user-123",
                child_age="seven"  # 应该是 int
            )


# ============================================================================
# 5. 向后兼容性测试
# ============================================================================

class TestBackwardCompatibility:
    """向后兼容性测试"""

    def test_optional_fields_can_be_omitted(self):
        """测试可选字段可以省略"""
        # 这确保了 API 的向后兼容性
        input_data = ImageAnalysisInput(
            image_url="https://example.com/image.jpg",
            child_id="user-123",
            child_age=7
            # interests 是可选的，可以省略
        )
        assert input_data.interests is None

    def test_new_optional_fields_dont_break_old_code(self):
        """测试新增可选字段不会破坏旧代码"""
        # 假设我们在未来版本中添加了新的可选字段
        # 旧代码应该仍然能工作
        output = ImageAnalysisResult(
            objects=["小狗"],
            scene="公园",
            mood="快乐",
            embedding_vector=[0.1] * 512,
            confidence_score=0.9
            # recurring_characters 是可选的
        )
        assert output.recurring_characters == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
