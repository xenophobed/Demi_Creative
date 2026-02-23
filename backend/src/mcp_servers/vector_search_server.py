"""
Vector Search MCP Server

Provides tools for storing and searching children's drawings in vector database (ChromaDB).
"""

import os
import json
from typing import Any, Dict, List, Optional
from datetime import datetime
import hashlib

import anyio
try:
    import chromadb
except Exception:  # pragma: no cover - import fallback for test env
    chromadb = None

try:
    from claude_agent_sdk import tool, create_sdk_mcp_server
except Exception:  # pragma: no cover - import fallback for test env
    def tool(*_args, **_kwargs):
        def decorator(func):
            return func
        return decorator

    def create_sdk_mcp_server(**kwargs):
        return kwargs


# 初始化 ChromaDB 客户端
def get_chroma_client():
    """获取 ChromaDB 客户端"""
    if chromadb is None:
        raise RuntimeError("ChromaDB SDK is unavailable in current environment")

    # 使用持久化存储
    persist_directory = os.getenv("CHROMA_PATH", "./data/vectors")
    return chromadb.PersistentClient(path=persist_directory)


# 集合名称
COLLECTION_NAME = "children_drawings"


def get_or_create_collection():
    """获取或创建集合"""
    client = get_chroma_client()
    # ChromaDB 会自动创建集合（如果不存在）
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "儿童画作的向量存储"}
    )


@tool(
    "search_similar_drawings",
    """在向量数据库中搜索与当前画作相似的历史画作。

    这个工具用于：
    1. 查找儿童之前画过的相似内容
    2. 识别重复出现的角色（如"闪电小狗"）
    3. 保持故事连续性

    返回相似画作列表，包含相似度分数。""",
    {"drawing_description": str, "child_id": str, "top_k": int}
)
async def search_similar_drawings(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    搜索相似的历史画作

    Args:
        args: 包含 drawing_description, child_id, top_k 的字典

    Returns:
        包含相似画作列表的字典
    """
    drawing_description = args["drawing_description"]
    child_id = args["child_id"]
    top_k = args.get("top_k", 5)

    try:
        # 获取集合（offload blocking ChromaDB call to thread）
        collection = await anyio.to_thread.run_sync(get_or_create_collection)

        # 使用 ChromaDB 的查询功能
        # ChromaDB 会自动将查询文本转换为向量并搜索
        results = await anyio.to_thread.run_sync(lambda: collection.query(
            query_texts=[drawing_description],
            n_results=top_k,
            where={"child_id": child_id}  # 过滤该儿童的画作
        ))

        # 格式化结果
        similar_drawings = []
        if results and results['ids'] and len(results['ids']) > 0:
            ids = results['ids'][0]
            distances = results['distances'][0] if 'distances' in results else [0] * len(ids)
            metadatas = results['metadatas'][0] if 'metadatas' in results else [{}] * len(ids)
            documents = results['documents'][0] if 'documents' in results else [""] * len(ids)

            for i, doc_id in enumerate(ids):
                # ChromaDB 返回的是距离，需要转换为相似度分数
                # 距离越小，相似度越高
                similarity_score = 1.0 / (1.0 + distances[i]) if i < len(distances) else 0.0

                similar_drawings.append({
                    "id": doc_id,
                    "similarity_score": round(similarity_score, 4),
                    "distance": round(distances[i], 4) if i < len(distances) else 0.0,
                    "drawing_data": metadatas[i] if i < len(metadatas) else {},
                    "description": documents[i] if i < len(documents) else ""
                })

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "similar_drawings": similar_drawings,
                    "total_found": len(similar_drawings),
                    "query": {
                        "child_id": child_id,
                        "top_k": top_k
                    }
                }, ensure_ascii=False, indent=2)
            }]
        }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"向量搜索失败: {str(e)}",
                    "similar_drawings": [],
                    "total_found": 0
                }, ensure_ascii=False)
            }]
        }


@tool(
    "store_drawing_embedding",
    """将儿童画作的分析结果存储到向量数据库。

    这个工具用于：
    1. 保存画作的向量表示
    2. 存储画作的元数据（物体、场景、角色等）
    3. 建立长期记忆系统

    每次创作新故事后调用此工具。""",
    {"drawing_description": str, "child_id": str, "drawing_analysis": dict, "story_text": str, "image_path": str}
)
async def store_drawing_embedding(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    存储画作到向量数据库

    Args:
        args: 包含画作信息的字典

    Returns:
        存储结果
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[VectorStore] 收到存储请求，参数: {json.dumps(args, ensure_ascii=False, default=str)[:500]}")

    drawing_description = args.get("drawing_description", "")
    child_id = args.get("child_id", "")
    drawing_analysis = args.get("drawing_analysis", {})
    story_text = args.get("story_text", "")
    image_path = args.get("image_path", "")

    # 参数验证
    if not drawing_description:
        logger.warning("[VectorStore] drawing_description 为空")
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": "drawing_description 不能为空"
                }, ensure_ascii=False)
            }]
        }

    if not child_id:
        logger.warning("[VectorStore] child_id 为空")
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": "child_id 不能为空"
                }, ensure_ascii=False)
            }]
        }

    # 如果 drawing_analysis 是字符串，尝试解析为 dict
    if isinstance(drawing_analysis, str):
        try:
            drawing_analysis = json.loads(drawing_analysis)
        except json.JSONDecodeError:
            drawing_analysis = {}

    try:
        # 获取集合（offload blocking ChromaDB call to thread）
        collection = await anyio.to_thread.run_sync(get_or_create_collection)

        # 生成唯一 ID
        timestamp = datetime.now().isoformat()
        doc_id = hashlib.md5(
            f"{child_id}_{timestamp}".encode()
        ).hexdigest()

        # 准备 metadata
        metadata = {
            "child_id": child_id,
            "scene": drawing_analysis.get("scene", ""),
            "mood": drawing_analysis.get("mood", ""),
            "story_text": story_text[:500] if story_text else "",  # 限制长度
            "image_path": image_path,
            "created_at": timestamp,
            # ChromaDB metadata 只支持基本类型，列表需要转为字符串
            "objects": json.dumps(drawing_analysis.get("objects", []), ensure_ascii=False),
            "colors": json.dumps(drawing_analysis.get("colors", []), ensure_ascii=False),
            "recurring_characters": json.dumps(
                drawing_analysis.get("recurring_characters", []),
                ensure_ascii=False
            )
        }

        # 存储到 ChromaDB
        # ChromaDB 会自动将文本转换为向量
        await anyio.to_thread.run_sync(lambda: collection.add(
            ids=[doc_id],
            documents=[drawing_description],
            metadatas=[metadata]
        ))

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "document_id": doc_id,
                    "message": "画作已成功存储到向量数据库"
                }, ensure_ascii=False, indent=2)
            }]
        }

    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": f"存储失败: {str(e)}"
                }, ensure_ascii=False)
            }]
        }


# 创建 MCP Server
vector_server = create_sdk_mcp_server(
    name="vector-search",
    version="1.0.0",
    tools=[search_similar_drawings, store_drawing_embedding]
)


if __name__ == "__main__":
    """测试工具"""
    import asyncio

    async def test():
        print("=== 测试 ChromaDB Vector Search ===\n")

        # 测试存储
        print("1. 测试存储画作...")
        store_result = await store_drawing_embedding({
            "drawing_description": "一只穿蓝色衣服的小狗在公园玩耍，旁边有树木和太阳",
            "child_id": "child_123",
            "drawing_analysis": {
                "objects": ["小狗", "树木", "太阳", "草地"],
                "scene": "户外公园",
                "mood": "快乐",
                "colors": ["蓝色", "绿色", "黄色"],
                "recurring_characters": [{
                    "name": "闪电",
                    "description": "穿蓝色衣服的小狗",
                    "visual_features": ["蓝色衣服", "尖耳朵"]
                }]
            },
            "story_text": "闪电小狗今天来到了它最喜欢的公园..."
        })
        print("存储结果:")
        print(json.loads(store_result["content"][0]["text"]))

        # 测试搜索
        print("\n2. 测试搜索相似画作...")
        search_result = await search_similar_drawings({
            "drawing_description": "一只小狗在户外",
            "child_id": "child_123",
            "top_k": 3
        })
        print("搜索结果:")
        print(json.loads(search_result["content"][0]["text"]))

    asyncio.run(test())
