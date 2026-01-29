#!/bin/bash

# Quick Test Script - API 快速测试脚本
# 测试 API 接口的核心功能

echo "==================================="
echo "Creative Agent API - 快速测试"
echo "==================================="
echo ""

# 检查是否在正确的目录
if [ ! -f "backend/src/main.py" ]; then
    echo "❌ 错误: 请在项目根目录运行此脚本"
    exit 1
fi

echo "📋 测试 1: 检查文件结构"
echo "-----------------------------------"

FILES=(
    "backend/src/main.py"
    "backend/src/api/models.py"
    "backend/src/api/routes/image_to_story.py"
    "backend/src/api/routes/interactive_story.py"
    "backend/src/services/session_manager.py"
    "backend/requirements.txt"
)

ALL_EXIST=true
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file"
    else
        echo "❌ $file (缺失)"
        ALL_EXIST=false
    fi
done

if [ "$ALL_EXIST" = true ]; then
    echo "✅ 所有必需文件存在"
else
    echo "⚠️  部分文件缺失"
    exit 1
fi
echo ""

echo "📋 测试 2: 检查 Python 环境"
echo "-----------------------------------"

if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "✅ Python 已安装: $PYTHON_VERSION"
else
    echo "❌ Python3 未安装"
    exit 1
fi
echo ""

echo "📋 测试 3: 检查依赖安装状态"
echo "-----------------------------------"

REQUIRED_PACKAGES=("fastapi" "uvicorn" "pydantic" "httpx")
MISSING_PACKAGES=()

for package in "${REQUIRED_PACKAGES[@]}"; do
    if python3 -c "import $package" 2>/dev/null; then
        echo "✅ $package 已安装"
    else
        echo "⚠️  $package 未安装"
        MISSING_PACKAGES+=("$package")
    fi
done

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo ""
    echo "提示: 安装缺失的依赖:"
    echo "  cd backend"
    echo "  pip install -r requirements.txt"
    echo ""
fi
echo ""

echo "📋 测试 4: 代码语法检查"
echo "-----------------------------------"

SYNTAX_OK=true
for file in backend/src/**/*.py; do
    if python3 -m py_compile "$file" 2>/dev/null; then
        echo "✅ $(basename $file)"
    else
        echo "❌ $(basename $file) - 语法错误"
        SYNTAX_OK=false
    fi
done

if [ "$SYNTAX_OK" = true ]; then
    echo "✅ 所有 Python 文件语法正确"
else
    echo "⚠️  部分文件有语法错误"
fi
echo ""

echo "📋 测试 5: 测试文件检查"
echo "-----------------------------------"

TEST_FILES=(
    "tests/api/test_health.py"
    "tests/api/test_image_to_story.py"
    "tests/api/test_interactive_story.py"
    "tests/integration/test_session_integration.py"
    "tests/integration/test_end_to_end.py"
)

TEST_COUNT=0
for file in "${TEST_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file"
        TEST_COUNT=$((TEST_COUNT + 1))
    else
        echo "❌ $file (缺失)"
    fi
done

echo "✅ 测试文件总数: $TEST_COUNT"
echo ""

echo "==================================="
echo "测试总结"
echo "==================================="

if [ "$ALL_EXIST" = true ] && [ "$SYNTAX_OK" = true ]; then
    echo "✅ 基础检查全部通过！"
    echo ""
    echo "下一步:"
    echo "1. 安装依赖 (如果还没安装):"
    echo "   cd backend && pip install -r requirements.txt"
    echo ""
    echo "2. 启动服务:"
    echo "   python3 -m backend.src.main"
    echo ""
    echo "3. 在另一个终端运行测试:"
    echo "   pytest tests/api/test_health.py -v"
    echo ""
    echo "4. 或使用 curl 测试:"
    echo "   curl http://localhost:8000/health"
else
    echo "⚠️  部分检查未通过，请修复后重试"
    exit 1
fi
