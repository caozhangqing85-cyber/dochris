#!/usr/bin/env python3
"""
kb init 命令：交互式初始化知识库工作区
支持 --non-interactive 非交互模式（CI/CD、脚本场景）
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any

from dochris.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


def cmd_init(args: Any) -> int:
    """初始化知识库工作区

    Args:
        args: 命令行参数
            - non_interactive: 是否非交互模式
            - api_key: API Key（非交互模式可选）

    Returns:
        退出码（0 表示成功，非 0 表示错误）
    """
    non_interactive = getattr(args, "non_interactive", False)
    api_key_arg = getattr(args, "api_key", None)
    path_arg = getattr(args, "path", None)

    # 如果指定了路径，设置 WORKSPACE 环境变量
    if path_arg:
        workspace = Path(path_arg).expanduser().resolve()
        os.environ["WORKSPACE"] = str(workspace)

    print("\n" + "=" * 60)
    print("📚 Dochris 知识库初始化向导")
    if non_interactive:
        print("   (非交互模式)")
    print("=" * 60 + "\n")

    # 1. 检查 Python 版本
    python_version = sys.version_info
    if python_version < (3, 11):
        print(f"❌ Python 版本过低: {python_version.major}.{python_version.minor}")
        print("   要求: Python 3.11 或更高版本")
        return 1

    print(f"✅ Python 版本: {python_version.major}.{python_version.minor}.{python_version.micro}")

    # 2. 检查工作区
    from dochris.settings import get_default_workspace

    workspace = get_default_workspace()

    if workspace.exists():
        # 检查是否已初始化
        env_file = workspace / ".env"
        if env_file.exists():
            print(f"\n⚠️  工作区已存在: {workspace}")
            if non_interactive:
                print("   非交互模式，跳过确认，将覆盖现有 .env 文件")
            else:
                response = input("   是否要重新初始化？这会覆盖现有 .env 文件。[y/N]: ")
                if response.lower() != "y":
                    print("   已取消初始化")
                    return 0

    # 3. 创建目录结构
    print("\n📁 创建工作区目录结构...")
    try:
        workspace.mkdir(parents=True, exist_ok=True)

        # 创建核心目录
        directories = [
            "raw/pdfs",
            "raw/articles",
            "raw/markdown",
            "raw/audio",
            "raw/videos",
            "raw/ebooks",
            "raw/other",
            "manifests/sources",
            "outputs/summaries",
            "outputs/concepts",
            "wiki/summaries",
            "wiki/concepts",
            "curated/summaries",
            "curated/concepts",
            "locked",
            "data",
            "logs",
            "transcripts",
        ]

        for dir_path in directories:
            (workspace / dir_path).mkdir(parents=True, exist_ok=True)
            print(f"   ✓ {dir_path}/")

        print(f"✅ 工作区目录已创建: {workspace}")

    except OSError as e:
        print(f"❌ 创建目录失败: {e}")
        return 1

    # 4. 创建 .env 文件
    print("\n🔧 配置 API Key...")

    # 尝试从现有 .env 读取
    env_file = workspace / ".env"
    existing_key = None
    if env_file.exists():
        try:
            content = env_file.read_text(encoding="utf-8")
            for line in content.split("\n"):
                if line.startswith("OPENAI_API_KEY=") and "your_api_key_here" not in line:
                    existing_key = line.split("=", 1)[1].strip()
                    break
        except OSError:
            pass

    if non_interactive:
        # 非交互模式：参数 > 环境变量 > 现有key > 占位符
        api_key = api_key_arg or os.environ.get("OPENAI_API_KEY") or existing_key
        if not api_key:
            print("   ⚠️  未提供 API Key（--api-key 或 OPENAI_API_KEY 环境变量）")
            print("   将使用占位符，请后续编辑 .env 文件配置 API Key")
            api_key = "your_api_key_here"
        else:
            print(f"   使用 API Key: {api_key[:10]}...")
    elif existing_key:
        print(f"   检测到现有 API Key: {existing_key[:10]}...")
        use_existing = input("   是否使用现有 API Key？[Y/n]: ")
        api_key = existing_key if use_existing.lower() != "n" else _prompt_api_key()
    else:
        api_key = _prompt_api_key()

    if not api_key:
        print("❌ API Key 是必需的")
        return 1

    # 5. 写入 .env 文件
    try:
        _create_env_file(env_file, api_key)
        print(f"✅ 配置已保存: {env_file}")
    except OSError as e:
        print(f"❌ 写入配置文件失败: {e}")
        return 1

    # 6. 验证配置
    print("\n🔍 验证配置...")
    try:
        os.environ["WORKSPACE"] = str(workspace)

        from dochris.settings import get_settings

        settings = get_settings()
        warnings = settings.validate()

        if warnings:
            print("   ⚠️  配置警告:")
            for warning in warnings:
                print(f"      - {warning}")

        print("✅ 配置验证通过")

    except ConfigurationError as e:
        print(f"❌ 配置验证失败: {e}")
        return 1

    # 7. 显示欢迎信息
    print("\n" + "=" * 60)
    print("🎉 初始化完成！")
    print("=" * 60)
    print(f"\n📍 工作区路径: {workspace}")
    print("\n📖 下一步操作:")
    print("   1. 将源文件放入工作区或配置 SOURCE_PATH")
    print("   2. 运行: kb ingest <源文件目录>")
    print("   3. 运行: kb compile")
    print('   4. 运行: kb query "关键词"')
    print("\n💡 提示:")
    print("   - 使用 kb --help 查看所有可用命令")
    print("   - 使用 kb config 查看当前配置")
    print()

    return 0


def _prompt_api_key() -> str | None:
    """提示用户输入 API Key"""
    print("\n请输入 API Key（获取地址: https://open.bigmodel.cn/）")
    print("或留空使用 OpenRouter 免费模型")
    api_key = input("API Key: ").strip()

    if not api_key:
        # 使用 OpenRouter
        print("   将使用 OpenRouter 免费模型")
        return "sk-or-v1-..."  # 占位符，用户需要自己注册

    return api_key


def _create_env_file(env_file: Path, api_key: str) -> None:
    """创建 .env 文件"""
    # 检测是否使用 OpenRouter
    is_openrouter = api_key.startswith("sk-or-v1")

    if is_openrouter:
        base_url = "https://openrouter.ai/api/v1"
        model = "qwen/qwen-2.5-72b-instruct:free"
    else:
        base_url = "https://open.bigmodel.cn/api/paas/v4"
        model = "glm-5.1"

    content = f"""# ============================================================
# 知识库系统配置文件
# ============================================================
# 配置优先级: .env 文件 > 环境变量 > 默认值

# ============================================================
# LLM API 配置
# ============================================================
OPENAI_API_KEY={api_key}
OPENAI_API_BASE={base_url}
MODEL={model}

# ============================================================
# 工作区配置
# ============================================================
WORKSPACE=~/.knowledge-base

# ============================================================
# Phase 1: 数据摄入配置
# ============================================================
# 源文件扫描路径（可选）
SOURCE_PATH=/path/to/your/materials

# ============================================================
# Phase 2: 编译配置
# ============================================================
MAX_CONCURRENCY=3
MIN_QUALITY_SCORE=85
MAX_CONTENT_CHARS=20000

# ============================================================
# Phase 3: 查询配置
# ============================================================
QUERY_MODEL=glm-4-flash
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5

# ============================================================
# 日志配置
# ============================================================
LOG_LEVEL=INFO
"""

    env_file.write_text(content, encoding="utf-8")
