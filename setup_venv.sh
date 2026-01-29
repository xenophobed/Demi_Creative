#!/bin/bash

# 虚拟环境设置脚本

echo "=========================================="
echo "创建虚拟环境"
echo "=========================================="
echo ""

# 检查当前目录
echo "当前目录: $(pwd)"
echo ""

# 创建虚拟环境
echo "步骤 1: 创建虚拟环境..."
python3 -m venv venv

# 检查是否创建成功
if [ -d "venv" ]; then
    echo "✅ 虚拟环境创建成功！"
    echo ""

    echo "步骤 2: 检查虚拟环境结构..."
    ls -la venv/
    echo ""

    echo "=========================================="
    echo "✅ 虚拟环境已准备好！"
    echo "=========================================="
    echo ""
    echo "下一步："
    echo "1. 激活虚拟环境："
    echo "   source venv/bin/activate"
    echo ""
    echo "2. 安装依赖："
    echo "   pip install -r backend/requirements.txt"
    echo ""
    echo "3. 启动服务："
    echo "   python -m backend.src.main"
    echo ""
else
    echo "❌ 虚拟环境创建失败"
    echo ""
    echo "可能的原因："
    echo "1. Python venv 模块未安装"
    echo "2. 磁盘空间不足"
    echo "3. 权限问题"
    echo ""
    echo "尝试使用 virtualenv："
    echo "  virtualenv venv"
    exit 1
fi
