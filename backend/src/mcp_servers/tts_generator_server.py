"""
TTS Generation MCP Server

Provides tools for generating audio narration using OpenAI TTS API.
"""

import os
import json
from typing import Any, Dict, Optional
from pathlib import Path
import hashlib
from datetime import datetime

from openai import OpenAI
from claude_agent_sdk import tool, create_sdk_mcp_server


# 可用的声音选项
AVAILABLE_VOICES = {
    "alloy": "中性温和声音，适合各年龄段",
    "echo": "男声，清晰友好",
    "fable": "英式口音，适合讲故事",
    "onyx": "低沉男声",
    "nova": "温柔女声，适合幼儿",
    "shimmer": "活泼女声"
}


def get_audio_output_path():
    """获取音频输出目录"""
    audio_dir = os.getenv("AUDIO_OUTPUT_PATH", "./data/audio")
    Path(audio_dir).mkdir(parents=True, exist_ok=True)
    return audio_dir


@tool(
    name="generate_story_audio",
    description="""将故事文本转换为语音音频文件。

    这个工具用于：
    1. 将文字故事转换为语音朗读
    2. 支持多种声音选择
    3. 适合不同年龄段的儿童
    4. 生成 MP3 格式音频文件

    返回音频文件路径。""",
    input_schema={
        "type": "object",
        "properties": {
            "story_text": {
                "type": "string",
                "description": "要转换为语音的故事文本"
            },
            "voice": {
                "type": "string",
                "description": "声音选项",
                "enum": list(AVAILABLE_VOICES.keys()),
                "default": "nova"
            },
            "speed": {
                "type": "number",
                "description": "朗读速度（0.25-4.0，默认 1.0）",
                "minimum": 0.25,
                "maximum": 4.0,
                "default": 1.0
            },
            "child_age": {
                "type": "integer",
                "description": "儿童年龄，用于调整朗读速度（可选）",
                "minimum": 3,
                "maximum": 12
            }
        },
        "required": ["story_text"]
    }
)
async def generate_story_audio(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成故事音频

    Args:
        args: 包含 story_text, voice, speed 的字典

    Returns:
        包含音频文件路径的字典
    """
    story_text = args["story_text"]
    voice = args.get("voice", "nova")
    speed = args.get("speed", 1.0)
    child_age = args.get("child_age")

    # 根据年龄调整速度
    if child_age and not args.get("speed"):
        if child_age <= 5:
            speed = 0.9  # 3-5岁：稍慢
        elif child_age <= 8:
            speed = 1.0  # 6-8岁：正常
        else:
            speed = 1.1  # 9-12岁：稍快

    try:
        # 检查 OpenAI API Key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "error": "未配置 OPENAI_API_KEY 环境变量",
                        "audio_path": None
                    }, ensure_ascii=False)
                }]
            }

        client = OpenAI(api_key=api_key)

        # 生成唯一文件名
        timestamp = datetime.now().isoformat()
        text_hash = hashlib.md5(story_text.encode()).hexdigest()[:8]
        filename = f"story_{text_hash}_{timestamp.replace(':', '-')}.mp3"

        audio_dir = get_audio_output_path()
        audio_path = os.path.join(audio_dir, filename)

        # 调用 OpenAI TTS API
        response = client.audio.speech.create(
            model="tts-1",  # 或 "tts-1-hd" 用于高质量
            voice=voice,
            input=story_text,
            speed=speed
        )

        # 保存音频文件
        response.stream_to_file(audio_path)

        # 获取文件大小
        file_size = os.path.getsize(audio_path)
        file_size_mb = round(file_size / (1024 * 1024), 2)

        # 估算音频时长（约 150 字/分钟）
        estimated_duration = len(story_text) / 150 * 60 / speed  # 秒

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "audio_path": audio_path,
                    "filename": filename,
                    "voice": voice,
                    "speed": speed,
                    "file_size_mb": file_size_mb,
                    "estimated_duration_seconds": round(estimated_duration, 1),
                    "text_length": len(story_text)
                }, ensure_ascii=False, indent=2)
            }]
        }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": f"TTS 生成失败: {str(e)}",
                    "audio_path": None
                }, ensure_ascii=False)
            }]
        }


@tool(
    name="list_available_voices",
    description="""列出所有可用的 TTS 声音选项。

    返回声音列表及其描述，帮助选择合适的声音。""",
    input_schema={
        "type": "object",
        "properties": {},
        "required": []
    }
)
async def list_available_voices(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    列出可用的声音选项

    Args:
        args: 空字典

    Returns:
        声音列表
    """
    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "voices": [
                    {
                        "id": voice_id,
                        "description": description,
                        "recommended_for": _get_recommendation(voice_id)
                    }
                    for voice_id, description in AVAILABLE_VOICES.items()
                ]
            }, ensure_ascii=False, indent=2)
        }]
    }


def _get_recommendation(voice_id: str) -> str:
    """获取声音推荐"""
    recommendations = {
        "nova": "3-6岁，睡前故事",
        "shimmer": "6-9岁，活泼故事",
        "alloy": "所有年龄段",
        "echo": "9-12岁，冒险故事",
        "fable": "传统童话故事",
        "onyx": "9-12岁，科普内容"
    }
    return recommendations.get(voice_id, "通用")


@tool(
    name="generate_audio_batch",
    description="""批量生成多个音频文件。

    用于互动故事的多个段落，一次性生成所有音频。

    注意：批量生成可能需要较长时间，建议分段不超过 10 个。""",
    input_schema={
        "type": "object",
        "properties": {
            "story_segments": {
                "type": "array",
                "description": "故事段落列表",
                "items": {
                    "type": "object",
                    "properties": {
                        "segment_id": {"type": "string", "description": "段落ID"},
                        "text": {"type": "string", "description": "段落文本"}
                    },
                    "required": ["segment_id", "text"]
                }
            },
            "voice": {
                "type": "string",
                "description": "声音选项",
                "enum": list(AVAILABLE_VOICES.keys()),
                "default": "nova"
            },
            "speed": {
                "type": "number",
                "description": "朗读速度",
                "default": 1.0
            }
        },
        "required": ["story_segments"]
    }
)
async def generate_audio_batch(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    批量生成音频

    Args:
        args: 包含 story_segments, voice, speed 的字典

    Returns:
        包含所有音频文件路径的字典
    """
    story_segments = args["story_segments"]
    voice = args.get("voice", "nova")
    speed = args.get("speed", 1.0)

    results = []
    errors = []

    for segment in story_segments:
        segment_id = segment["segment_id"]
        text = segment["text"]

        try:
            # 调用单个音频生成
            result = await generate_story_audio({
                "story_text": text,
                "voice": voice,
                "speed": speed
            })

            result_data = json.loads(result["content"][0]["text"])
            if result_data.get("success"):
                results.append({
                    "segment_id": segment_id,
                    "audio_path": result_data["audio_path"],
                    "filename": result_data["filename"]
                })
            else:
                errors.append({
                    "segment_id": segment_id,
                    "error": result_data.get("error")
                })

        except Exception as e:
            errors.append({
                "segment_id": segment_id,
                "error": str(e)
            })

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "total_segments": len(story_segments),
                "successful": len(results),
                "failed": len(errors),
                "results": results,
                "errors": errors if errors else None
            }, ensure_ascii=False, indent=2)
        }]
    }


# 创建 MCP Server
tts_server = create_sdk_mcp_server(
    name="tts-generation",
    version="1.0.0",
    tools=[generate_story_audio, list_available_voices, generate_audio_batch]
)


if __name__ == "__main__":
    """测试工具"""
    import asyncio

    async def test():
        print("=== 测试 TTS Generation ===\n")

        # 测试列出声音
        print("1. 列出可用声音...")
        voices_result = await list_available_voices({})
        print(json.loads(voices_result["content"][0]["text"]))
        print()

        # 测试生成音频
        print("2. 生成故事音频...")
        audio_result = await generate_story_audio({
            "story_text": "从前有一只小兔子，它喜欢在森林里探险。有一天，它发现了一个神秘的洞穴...",
            "voice": "nova",
            "child_age": 5
        })
        result = json.loads(audio_result["content"][0]["text"])
        print(f"生成结果: {result.get('success')}")
        if result.get('audio_path'):
            print(f"音频文件: {result['audio_path']}")
            print(f"文件大小: {result['file_size_mb']} MB")
            print(f"预计时长: {result['estimated_duration_seconds']} 秒")

    asyncio.run(test())
