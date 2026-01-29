"""
API Tests Configuration

测试配置和共享 fixtures
"""

import pytest
import os
from pathlib import Path


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """设置测试环境"""
    # 设置测试环境变量
    os.environ["ENVIRONMENT"] = "test"

    # 确保测试数据目录存在
    test_data_dir = Path("./data/test")
    test_data_dir.mkdir(parents=True, exist_ok=True)

    yield

    # 清理（可选）
    # 注意：不要删除真实的数据目录


@pytest.fixture
def test_child_id():
    """测试儿童ID"""
    return "test_child_001"


@pytest.fixture
def test_age_group():
    """测试年龄组"""
    return "6-8"


@pytest.fixture
def test_interests():
    """测试兴趣列表"""
    return ["动物", "冒险", "太空"]
