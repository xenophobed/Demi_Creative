#!/usr/bin/env python3
"""
启动 FastAPI 服务器
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=== 启动 Creative Agent API 服务 ===\n")

try:
    print("1. 导入 FastAPI...")
    import fastapi
    print(f"   ✅ FastAPI 版本: {fastapi.__version__}")

    print("2. 导入 uvicorn...")
    import uvicorn
    print(f"   ✅ Uvicorn 已导入")

    print("3. 导入应用...")
    from backend.src.main import app
    print("   ✅ 应用导入成功")

    print("\n4. 启动服务器...")
    print("   地址: http://localhost:8000")
    print("   文档: http://localhost:8000/api/docs")
    print("   按 Ctrl+C 停止服务\n")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

except ImportError as e:
    print(f"\n❌ 导入错误: {e}")
    print("\n请确保已安装所有依赖:")
    print("  cd backend")
    print("  pip install -r requirements.txt")
    sys.exit(1)

except Exception as e:
    print(f"\n❌ 启动失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
