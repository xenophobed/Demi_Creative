"""
Safety Check MCP Server

Provides tools for checking content safety and ensuring age-appropriateness.
"""

import json
import os
from typing import Any, Dict, List

from ..utils.model_config import get_safety_model

try:
    from anthropic import Anthropic
except Exception:  # pragma: no cover - import fallback for test env
    Anthropic = None

try:
    from claude_agent_sdk import create_sdk_mcp_server, tool
except Exception:  # pragma: no cover - import fallback for test env

    def tool(*_args, **_kwargs):
        def decorator(func):
            return func

        return decorator

    def create_sdk_mcp_server(**kwargs):
        return kwargs


# Content safety rules
SAFETY_RULES = """
# Content Safety Rules

## Negative Content Filtering (Must Avoid)
1. **Violence**: Fighting, gore, weapon use, harming others
2. **Horror**: Ghosts, dark horror elements, thriller scenes
3. **Inappropriate Language**: Profanity, insults, discriminatory expressions
4. **Adult Topics**: Sexual content, drugs, alcoholism, political controversy

## Positive Value Guidance (Should Include)
1. **Gender Equality**: Avoid stereotypes (e.g. "doctors are always male", "nurses are always female")
2. **Cultural Diversity**: Represent different cultures, races, and family structures
3. **Moral Education**: Friendship, courage, honesty, empathy, responsibility
4. **Inclusivity**: Respect people of different abilities, appearances, and backgrounds
5. **Environmental Awareness**: Care for nature, protect animals

## Scoring Criteria
- 0.0-0.3: Severely non-compliant, contains clearly inappropriate content
- 0.3-0.7: Non-compliant, issues need to be fixed
- 0.7-0.85: Basically compliant, improvements recommended
- 0.85-1.0: Excellent, meets children's content standards
"""


@tool(
    "check_content_safety",
    """Check whether content is appropriate for children and meets safety standards.

    This tool will:
    1. Detect negative content (violence, horror, inappropriate language, etc.)
    2. Check for positive value guidance (gender equality, cultural diversity, etc.)
    3. Assess age appropriateness
    4. Provide a safety score (0.0-1.0)
    5. Offer improvement suggestions (if issues are found)

    All generated content must pass this check before being presented to children.""",
    {"content_text": str, "content_type": str, "target_age": int},
)
async def check_content_safety(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check content safety

    Args:
        args: Dictionary containing content_text, content_type, target_age

    Returns:
        Dictionary containing safety check results
    """
    content_text = args["content_text"]
    content_type = args.get("content_type", "story")
    target_age = args["target_age"]

    # Determine check focus based on age
    age_context = ""
    if target_age <= 5:
        age_context = "Ages 3-5 preschool: Content must be extremely gentle, avoiding anything that might cause fear."
    elif target_age <= 8:
        age_context = "Ages 6-8 early elementary: Light conflict is okay, but must be resolved positively, no violence."
    else:
        age_context = (
            "Ages 9-12 upper elementary: Complex plots are okay, but must still avoid violence, horror, and other inappropriate content."
        )

    prompt = f"""As a children's content safety review expert, carefully check the following content.

Target age: {target_age} years old
Content type: {content_type}
{age_context}

# Content to check:
```
{content_text}
```

# Review criteria:
{SAFETY_RULES}

Please return the review results in the following JSON format:

{{
  "safety_score": 0.95,
  "is_safe": true,
  "issues": [
    {{
      "type": "violence",
      "severity": "low",
      "description": "Description of the issue",
      "location": "Specific location or sentence in the content"
    }}
  ],
  "positive_aspects": [
    "Demonstrates the power of friendship",
    "Encourages bravely facing difficulties"
  ],
  "suggestions": [
    "Suggest modifying the description in paragraph 3 to avoid the word 'fighting'"
  ],
  "age_appropriateness": {{
    "is_appropriate": true,
    "reasoning": "Simple language, positive plot, suitable for a 7-year-old"
  }},
  "value_guidance": {{
    "gender_equality": "good",
    "cultural_diversity": "fair",
    "moral_education": "excellent",
    "inclusivity": "good"
  }}
}}

Notes:
1. safety_score range: 0.0-1.0, higher scores mean safer content
2. issues lists all discovered problems (empty array if no issues)
3. severity levels: low, medium, high
4. positive_aspects lists the positive values in the content
5. suggestions are only provided when issues are found

Always respond in English.
"""

    try:
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        response = client.messages.create(
            model=get_safety_model(),
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract response text
        response_text = response.content[0].text

        # Parse JSON
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

            # Validate required fields
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

            # Add metadata
            result["target_age"] = target_age
            result["content_type"] = content_type
            result["passed"] = result["safety_score"] >= 0.85  # Excellence threshold

            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2),
                    }
                ]
            }

        except json.JSONDecodeError:
            # If parsing fails, return default safety result
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "error": "Failed to parse safety check response",
                                "raw_response": response_text,
                                "safety_score": 0.5,
                                "is_safe": False,
                                "issues": [
                                    {
                                        "type": "system_error",
                                        "severity": "high",
                                        "description": "Failed to complete safety check",
                                    }
                                ],
                                "passed": False,
                            },
                            ensure_ascii=False,
                        ),
                    }
                ]
            }

    except Exception as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "error": f"Safety check failed: {str(e)}",
                            "safety_score": 0.0,
                            "is_safe": False,
                            "issues": [
                                {
                                    "type": "system_error",
                                    "severity": "high",
                                    "description": str(e),
                                }
                            ],
                            "passed": False,
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        }


@tool(
    "suggest_content_improvements",
    """Generate improved content based on safety check results.

    This tool will:
    1. Receive original content and safety check results
    2. Modify content based on discovered issues
    3. Preserve the core plot and educational value of the story
    4. Return the improved content

    Only use when safety check has not passed.""",
    {"original_content": str, "safety_check_result": dict, "target_age": int},
)
async def suggest_content_improvements(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Improve content based on safety check results.

    Args:
        args: Dictionary containing original content and safety check results

    Returns:
        Improved content
    """
    original_content = args["original_content"]
    safety_check = args["safety_check_result"]
    target_age = args["target_age"]

    # Extract issues and suggestions
    issues = safety_check.get("issues", [])
    suggestions = safety_check.get("suggestions", [])

    if not issues and not suggestions:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "improved_content": original_content,
                            "changes_made": [],
                            "message": "Content needs no improvement, already meets safety standards",
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        }

    prompt = f"""As a children's content editing expert, improve the following content.

Target age: {target_age} years old

# Original content:
```
{original_content}
```

# Issues found:
{json.dumps(issues, ensure_ascii=False, indent=2)}

# Improvement suggestions:
{json.dumps(suggestions, ensure_ascii=False, indent=2)}

Based on the issues and suggestions above, rewrite the content ensuring:
1. Fix all safety issues
2. Preserve the core plot and educational value
3. Language is appropriate for the target age
4. Positive value guidance is maintained

Please return in the following JSON format:

{{
  "improved_content": "The complete improved content",
  "changes_made": [
    "Specific change description 1",
    "Specific change description 2"
  ],
  "safety_improvements": "Summary of safety improvements"
}}

Always respond in English.
"""

    try:
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        response = client.messages.create(
            model=get_safety_model(),
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.content[0].text

        # Parse JSON
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
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2),
                    }
                ]
            }

        except json.JSONDecodeError:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "error": "Failed to parse improvement suggestions",
                                "improved_content": original_content,
                                "changes_made": [],
                            },
                            ensure_ascii=False,
                        ),
                    }
                ]
            }

    except Exception as e:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "error": f"Content improvement failed: {str(e)}",
                            "improved_content": original_content,
                            "changes_made": [],
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        }


# Create MCP Server
safety_server = create_sdk_mcp_server(
    name="safety-check",
    version="1.0.0",
    tools=[check_content_safety, suggest_content_improvements],
)


if __name__ == "__main__":
    """Test tools"""
    import asyncio

    async def test():
        print("=== Test Safety Check ===\n")

        # Test safe content
        print("1. Testing safe content...")
        safe_result = await check_content_safety(
            {
                "content_text": "A little rabbit found a carrot in the forest and happily shared it with friends. Everyone had a wonderful day together.",
                "target_age": 5,
                "content_type": "story",
            }
        )
        print("Safety check result:")
        result = json.loads(safe_result["content"][0]["text"])
        print(f"Score: {result.get('safety_score')}")
        print(f"Passed: {result.get('passed')}")
        print()

        # Test problematic content
        print("2. Testing problematic content...")
        unsafe_result = await check_content_safety(
            {
                "content_text": "Tom and Jane got into a fight. Tom punched Jane.",
                "target_age": 6,
                "content_type": "story",
            }
        )
        print("Safety check result:")
        result = json.loads(unsafe_result["content"][0]["text"])
        print(f"Score: {result.get('safety_score')}")
        print(f"Issues: {result.get('issues')}")
        print()

        # Test content improvement
        if not result.get("passed"):
            print("3. Testing content improvement...")
            improved = await suggest_content_improvements(
                {
                    "original_content": "Tom and Jane got into a fight. Tom punched Jane.",
                    "safety_check_result": result,
                    "target_age": 6,
                }
            )
            print("Improvement result:")
            print(json.loads(improved["content"][0]["text"]))

    asyncio.run(test())
