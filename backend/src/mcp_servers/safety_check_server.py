"""
Safety Check MCP Server

Provides tools for checking content safety and ensuring age-appropriateness.
"""

import os
import json
from typing import Any, Dict, List

from anthropic import Anthropic
from claude_agent_sdk import tool, create_sdk_mcp_server


# 安全检查规则
SAFETY_RULES = """
# 内容安全检查规则

## 负面内容过滤（必须避免）
1. **暴力**: 打斗、血腥、武器使用、伤害他人
2. **恐怖**: 鬼怪、黑暗恐怖元素、惊悚场景
3. **不当语言**: 脏话、侮辱性词汇、歧视性表达
4. **成人话题**: 性相关内容、毒品、酗酒、政治争议

## 正向价值引导（应该包含）
1. **性别平等**: 避免刻板印象（如"医生总是男性"、"护士总是女性"）
2. **文化多样性**: 展现不同文化、种族、家庭结构
3. **品德教育**: 友谊、勇气、诚实、同理心、责任感
4. **包容性**: 尊重不同能力、外貌、背景的人
5. **环保意识**: 爱护自然、保护动物

## 评分标准
- 0.0-0.3: 严重不合格，含有明显不当内容
- 0.3-0.7: 不合格，存在问题需要修改
- 0.7-0.85: 基本合格，建议改进
- 0.85-1.0: 优秀，符合儿童内容标准
"""


@tool(
    "check_content_safety",
    """检查内容是否适合儿童，确保符合安全标准。

    这个工具会：
    1. 检测负面内容（暴力、恐怖、不当语言等）
    2. 检查正向价值引导（性别平等、文化多样性等）
    3. 评估年龄适配性
    4. 给出安全评分（0.0-1.0）
    5. 提供修改建议（如有问题）

    所有生成的内容在呈现给儿童前必须通过此检查。""",
    {"content_text": str, "content_type": str, "target_age": int}
)
async def check_content_safety(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    检查内容安全性

    Args:
        args: 包含 content_text, content_type, target_age 的字典

    Returns:
        包含安全检查结果的字典
    """
    content_text = args["content_text"]
    content_type = args.get("content_type", "story")
    target_age = args["target_age"]

    # 根据年龄确定检查重点
    age_context = ""
    if target_age <= 5:
        age_context = "3-5岁学龄前儿童：需要极度温和，避免任何可能引起恐惧的内容。"
    elif target_age <= 8:
        age_context = "6-8岁小学低年级：可以有轻微冲突，但必须正面解决，不能有暴力。"
    else:
        age_context = "9-12岁小学高年级：可以有复杂情节，但仍需避免暴力、恐怖等不当内容。"

    prompt = f"""请作为一个儿童内容安全审查专家，仔细检查以下内容。

目标年龄：{target_age}岁
内容类型：{content_type}
{age_context}

# 待检查内容：
```
{content_text}
```

# 检查标准：
{SAFETY_RULES}

请按以下 JSON 格式返回检查结果：

{{
  "safety_score": 0.95,
  "is_safe": true,
  "issues": [
    {{
      "type": "暴力",
      "severity": "低",
      "description": "问题描述",
      "location": "内容中的具体位置或句子"
    }}
  ],
  "positive_aspects": [
    "展现了友谊的力量",
    "鼓励勇敢面对困难"
  ],
  "suggestions": [
    "建议修改第3段的描述，避免使用'打斗'这个词"
  ],
  "age_appropriateness": {{
    "is_appropriate": true,
    "reasoning": "语言简单，情节积极，适合7岁儿童"
  }},
  "value_guidance": {{
    "gender_equality": "良好",
    "cultural_diversity": "一般",
    "moral_education": "优秀",
    "inclusivity": "良好"
  }}
}}

注意：
1. safety_score 范围：0.0-1.0，分数越高越安全
2. issues 列出所有发现的问题（如无问题则为空数组）
3. severity 等级：低、中、高
4. positive_aspects 列出内容的正面价值
5. suggestions 仅在发现问题时提供修改建议
"""

    try:
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # 提取响应文本
        response_text = response.content[0].text

        # 解析 JSON
        try:
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            result = json.loads(response_text)

            # 验证必需字段
            if "safety_score" not in result:
                result["safety_score"] = 0.5
            if "is_safe" not in result:
                result["is_safe"] = result["safety_score"] >= 0.7
            if "issues" not in result:
                result["issues"] = []
            if "positive_aspects" not in result:
                result["positive_aspects"] = []
            if "suggestions" not in result:
                result["suggestions"] = []

            # 添加元数据
            result["target_age"] = target_age
            result["content_type"] = content_type
            result["passed"] = result["safety_score"] >= 0.85  # 优秀标准

            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, ensure_ascii=False, indent=2)
                }]
            }

        except json.JSONDecodeError:
            # 如果无法解析，返回默认安全结果
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "error": "无法解析安全检查响应",
                        "raw_response": response_text,
                        "safety_score": 0.5,
                        "is_safe": False,
                        "issues": [{"type": "系统错误", "severity": "高", "description": "无法完成安全检查"}],
                        "passed": False
                    }, ensure_ascii=False)
                }]
            }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"安全检查失败: {str(e)}",
                    "safety_score": 0.0,
                    "is_safe": False,
                    "issues": [{"type": "系统错误", "severity": "高", "description": str(e)}],
                    "passed": False
                }, ensure_ascii=False)
            }]
        }


@tool(
    "suggest_content_improvements",
    """根据安全检查结果，生成改进后的内容。

    这个工具会：
    1. 接收原始内容和安全检查结果
    2. 根据发现的问题进行修改
    3. 保持故事的核心情节和教育意义
    4. 返回改进后的内容

    仅在安全检查未通过时使用。""",
    {"original_content": str, "safety_check_result": dict, "target_age": int}
)
async def suggest_content_improvements(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    根据安全检查结果改进内容

    Args:
        args: 包含原始内容和安全检查结果的字典

    Returns:
        改进后的内容
    """
    original_content = args["original_content"]
    safety_check = args["safety_check_result"]
    target_age = args["target_age"]

    # 提取问题和建议
    issues = safety_check.get("issues", [])
    suggestions = safety_check.get("suggestions", [])

    if not issues and not suggestions:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "improved_content": original_content,
                    "changes_made": [],
                    "message": "内容无需改进，已符合安全标准"
                }, ensure_ascii=False)
            }]
        }

    prompt = f"""请作为一个儿童内容编辑专家，改进以下内容。

目标年龄：{target_age}岁

# 原始内容：
```
{original_content}
```

# 发现的问题：
{json.dumps(issues, ensure_ascii=False, indent=2)}

# 改进建议：
{json.dumps(suggestions, ensure_ascii=False, indent=2)}

请根据上述问题和建议，改写内容，确保：
1. 修复所有安全问题
2. 保持故事的核心情节和教育意义
3. 语言适合目标年龄
4. 正向价值引导

请按以下 JSON 格式返回：

{{
  "improved_content": "改进后的完整内容",
  "changes_made": [
    "具体修改说明1",
    "具体修改说明2"
  ],
  "safety_improvements": "安全性改进总结"
}}
"""

    try:
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        response_text = response.content[0].text

        # 解析 JSON
        try:
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            result = json.loads(response_text)

            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, ensure_ascii=False, indent=2)
                }]
            }

        except json.JSONDecodeError:
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "error": "无法解析改进建议",
                        "improved_content": original_content,
                        "changes_made": []
                    }, ensure_ascii=False)
                }]
            }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"内容改进失败: {str(e)}",
                    "improved_content": original_content,
                    "changes_made": []
                }, ensure_ascii=False)
            }]
        }


# 创建 MCP Server
safety_server = create_sdk_mcp_server(
    name="safety-check",
    version="1.0.0",
    tools=[check_content_safety, suggest_content_improvements]
)


if __name__ == "__main__":
    """测试工具"""
    import asyncio

    async def test():
        print("=== 测试 Safety Check ===\n")

        # 测试安全内容
        print("1. 测试安全内容...")
        safe_result = await check_content_safety({
            "content_text": "小兔子在森林里找到了一个胡萝卜，它高兴地和朋友们分享。大家一起度过了快乐的一天。",
            "target_age": 5,
            "content_type": "story"
        })
        print("安全检查结果:")
        result = json.loads(safe_result["content"][0]["text"])
        print(f"评分: {result.get('safety_score')}")
        print(f"是否通过: {result.get('passed')}")
        print()

        # 测试问题内容
        print("2. 测试问题内容...")
        unsafe_result = await check_content_safety({
            "content_text": "小明和小红打架了，小明用拳头打了小红。",
            "target_age": 6,
            "content_type": "story"
        })
        print("安全检查结果:")
        result = json.loads(unsafe_result["content"][0]["text"])
        print(f"评分: {result.get('safety_score')}")
        print(f"问题: {result.get('issues')}")
        print()

        # 测试内容改进
        if not result.get('passed'):
            print("3. 测试内容改进...")
            improved = await suggest_content_improvements({
                "original_content": "小明和小红打架了，小明用拳头打了小红。",
                "safety_check_result": result,
                "target_age": 6
            })
            print("改进结果:")
            print(json.loads(improved["content"][0]["text"]))

    asyncio.run(test())
