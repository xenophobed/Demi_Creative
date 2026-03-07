"""
MCP Tools Contract Tests

测试 MCP Tools 的输入输出契约，确保工具符合规范。
"""

import pytest
import json
import os
from pathlib import Path
from PIL import Image
import io


def _call_tool(tool_ref, args):
    """Call an MCP tool, unwrapping SdkMcpTool if the SDK is installed."""
    handler = getattr(tool_ref, "handler", tool_ref)
    return handler(args)


class TestVisionAnalysisContract:
    """Vision Analysis MCP Tool 契约测试"""

    @pytest.fixture
    def sample_drawing_path(self, tmp_path):
        """创建测试用的儿童画作"""
        # 创建一个简单的测试图片
        img = Image.new('RGB', (400, 300), color='lightblue')
        img_path = tmp_path / "test_drawing.png"
        img.save(img_path)
        return str(img_path)

    @pytest.mark.asyncio
    async def test_analyze_children_drawing_contract(self, sample_drawing_path):
        """测试 analyze_children_drawing 工具的输入输出契约"""
        from backend.src.mcp_servers.vision_analysis_server import analyze_children_drawing

        # 准备输入
        input_data = {
            "image_path": sample_drawing_path,
            "child_age": 7
        }

        # 调用工具
        result = await _call_tool(analyze_children_drawing, input_data)

        # 验证输出格式
        assert "content" in result, "输出必须包含 content 字段"
        assert isinstance(result["content"], list), "content 必须是列表"
        assert len(result["content"]) > 0, "content 不能为空"

        # 验证内容格式
        content_item = result["content"][0]
        assert "type" in content_item, "content 项必须包含 type 字段"
        assert content_item["type"] == "text", "content 类型必须是 text"
        assert "text" in content_item, "content 项必须包含 text 字段"

        # 解析 JSON 响应
        data = json.loads(content_item["text"])

        # 验证必需字段存在
        assert "objects" in data, "输出必须包含 objects 字段"
        assert "scene" in data, "输出必须包含 scene 字段"
        assert "mood" in data, "输出必须包含 mood 字段"
        assert "confidence_score" in data, "输出必须包含 confidence_score 字段"

        # 验证字段类型
        assert isinstance(data["objects"], list), "objects 必须是列表"
        assert isinstance(data["scene"], str), "scene 必须是字符串"
        assert isinstance(data["mood"], str), "mood 必须是字符串"
        assert isinstance(data["confidence_score"], (int, float)), "confidence_score 必须是数字"

        # 验证值范围
        assert 0.0 <= data["confidence_score"] <= 1.0, "confidence_score 必须在 0.0-1.0 之间"

        # 验证可选字段存在且类型正确
        if "colors" in data:
            assert isinstance(data["colors"], list), "colors 必须是列表"

        if "recurring_characters" in data:
            assert isinstance(data["recurring_characters"], list), "recurring_characters 必须是列表"
            for char in data["recurring_characters"]:
                assert isinstance(char, dict), "每个角色必须是字典"
                if "name" in char:
                    assert isinstance(char["name"], str), "角色名称必须是字符串"
                if "description" in char:
                    assert isinstance(char["description"], str), "角色描述必须是字符串"

    @pytest.mark.asyncio
    async def test_analyze_children_drawing_age_range(self, sample_drawing_path):
        """测试不同年龄段的输入"""
        from backend.src.mcp_servers.vision_analysis_server import analyze_children_drawing

        ages = [3, 5, 7, 9, 12]
        for age in ages:
            input_data = {
                "image_path": sample_drawing_path,
                "child_age": age
            }

            result = await _call_tool(analyze_children_drawing, input_data)
            data = json.loads(result["content"][0]["text"])

            assert "objects" in data, f"年龄 {age} 的输出必须包含 objects"
            assert isinstance(data["objects"], list), f"年龄 {age} 的 objects 必须是列表"

    @pytest.mark.asyncio
    async def test_analyze_children_drawing_invalid_path(self):
        """测试无效图片路径的错误处理"""
        from backend.src.mcp_servers.vision_analysis_server import analyze_children_drawing

        input_data = {
            "image_path": "/nonexistent/path/image.jpg",
            "child_age": 7
        }

        result = await _call_tool(analyze_children_drawing, input_data)
        data = json.loads(result["content"][0]["text"])

        # 应该返回错误信息
        assert "error" in data, "无效路径应该返回错误"

    @pytest.mark.asyncio
    async def test_analyze_children_drawing_required_fields(self, sample_drawing_path):
        """测试必需字段验证"""
        from backend.src.mcp_servers.vision_analysis_server import analyze_children_drawing

        # 测试缺少 child_age
        with pytest.raises(KeyError):
            await _call_tool(analyze_children_drawing, {
                "image_path": sample_drawing_path
            })

        # 测试缺少 image_path
        with pytest.raises(KeyError):
            await _call_tool(analyze_children_drawing, {
                "child_age": 7
            })


class TestVectorSearchContract:
    """Vector Search MCP Tool 契约测试"""

    @pytest.fixture
    def chroma_tmp_dir(self, tmp_path, monkeypatch):
        """Isolated ChromaDB directory for contract tests."""
        chroma_dir = tmp_path / "chroma"
        chroma_dir.mkdir()
        monkeypatch.setenv("CHROMA_PATH", str(chroma_dir))
        return chroma_dir

    @pytest.mark.asyncio
    async def test_store_drawing_embedding_contract(self, chroma_tmp_dir):
        """测试 store_drawing_embedding 工具的输入输出契约"""
        from backend.src.mcp_servers.vector_search_server import store_drawing_embedding

        result = await _call_tool(store_drawing_embedding, {
            "drawing_description": "A dog playing in the park",
            "child_id": "contract-child-001",
            "drawing_analysis": {
                "objects": ["dog", "tree"],
                "scene": "park",
                "mood": "happy",
                "colors": ["green", "brown"],
            },
        })

        # 验证 MCP 响应信封格式
        assert "content" in result
        assert isinstance(result["content"], list)
        assert result["content"][0]["type"] == "text"

        data = json.loads(result["content"][0]["text"])
        assert data["success"] is True
        assert "document_id" in data
        assert isinstance(data["document_id"], str)

    @pytest.mark.asyncio
    async def test_search_similar_drawings_contract(self, chroma_tmp_dir):
        """测试 search_similar_drawings 工具的输入输出契约"""
        from backend.src.mcp_servers.vector_search_server import search_similar_drawings

        result = await _call_tool(search_similar_drawings, {
            "drawing_description": "a cat on a sofa",
            "child_id": "contract-child-002",
            "top_k": 3,
        })

        # 验证 MCP 响应信封格式
        assert "content" in result
        assert isinstance(result["content"], list)
        assert result["content"][0]["type"] == "text"

        data = json.loads(result["content"][0]["text"])
        assert "similar_drawings" in data
        assert isinstance(data["similar_drawings"], list)
        assert "total_found" in data
        assert isinstance(data["total_found"], int)


class TestSafetyCheckContract:
    """Safety Check MCP Tool 契约测试"""

    @pytest.mark.asyncio
    async def test_check_content_safety_contract(self):
        """测试 check_content_safety 工具的输入输出契约 — uses real Anthropic API"""
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if not anthropic_key:
            pytest.skip("ANTHROPIC_API_KEY not set")

        from backend.src.mcp_servers.safety_check_server import check_content_safety

        result = await _call_tool(check_content_safety, {
            "content_text": "A bunny shared carrots with friends in the garden.",
            "content_type": "story",
            "target_age": 5,
        })

        # 验证 MCP 响应信封格式
        assert "content" in result
        assert isinstance(result["content"], list)
        assert result["content"][0]["type"] == "text"

        data = json.loads(result["content"][0]["text"])
        assert "safety_score" in data
        assert isinstance(data["safety_score"], (int, float))
        assert 0.0 <= data["safety_score"] <= 1.0
        assert "is_safe" in data
        assert isinstance(data["is_safe"], bool)
        assert "issues" in data
        assert isinstance(data["issues"], list)


class TestTTSGenerationContract:
    """TTS Generation MCP Tool 契约测试"""

    @pytest.mark.asyncio
    async def test_generate_story_audio_contract(self, tmp_path, monkeypatch):
        """测试 generate_story_audio 工具的输入输出契约 — uses real OpenAI API"""
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            pytest.skip("OPENAI_API_KEY not set")

        monkeypatch.setenv("AUDIO_OUTPUT_PATH", str(tmp_path))

        from backend.src.mcp_servers.tts_generator_server import generate_story_audio

        result = await _call_tool(generate_story_audio, {
            "story_text": "Hello!",
            "voice": "nova",
        })

        # 验证 MCP 响应信封格式
        assert "content" in result
        assert isinstance(result["content"], list)
        assert result["content"][0]["type"] == "text"

        data = json.loads(result["content"][0]["text"])
        assert data["success"] is True
        assert "audio_path" in data
        assert Path(data["audio_path"]).exists()

    @pytest.mark.asyncio
    async def test_list_available_voices_contract(self):
        """测试 list_available_voices 工具的输入输出契约 — no API key needed"""
        from backend.src.mcp_servers.tts_generator_server import list_available_voices

        result = await _call_tool(list_available_voices, {})

        assert "content" in result
        data = json.loads(result["content"][0]["text"])
        assert "voices" in data
        assert len(data["voices"]) > 0
        for voice in data["voices"]:
            assert "id" in voice
            assert "description" in voice
