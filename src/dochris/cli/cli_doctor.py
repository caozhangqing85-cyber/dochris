#!/usr/bin/env python3
"""
kb doctor 命令：环境诊断和配置检查
"""

import argparse
import os
import shutil
import sys

from dochris.cli.cli_utils import dim, error, info, success, warning
from dochris.exceptions import ConfigurationError
from dochris.settings import get_settings


def cmd_doctor(args: argparse.Namespace) -> int:
    """运行环境诊断

    Args:
        args: 命令行参数

    Returns:
        退出码（0 表示无问题，非 0 表示有问题）
    """
    print("\n" + "=" * 60)
    print("🔍 知识库环境诊断")
    print("=" * 60 + "\n")

    issues = []

    # 1. Python 版本检查
    print(info("1. Python 版本检查"))
    python_version = sys.version_info
    if python_version >= (3, 11):
        print(
            f"   {success('✓')} Python {python_version.major}.{python_version.minor}.{python_version.micro}"
        )
    else:
        print(
            f"   {error('✗')} Python {python_version.major}.{python_version.minor}.{python_version.micro}"
        )
        print(f"   {warning('要求: Python 3.11 或更高版本')}")
        issues.append("python_version")

    # 2. 获取配置
    print(f"\n{info('2. API 配置检查')}")
    try:
        settings = get_settings()
    except ConfigurationError as e:
        print(f"   {error('✗')} 配置加载失败: {e}")
        return 1

    # API Key 检查
    if settings.api_key:
        masked = f"...{settings.api_key[-6:]}" if len(settings.api_key) > 6 else "***"
        print(f"   {success('✓')} API Key 已配置 ({masked})")
    else:
        print(f"   {error('✗')} API Key 未配置")
        print(f"   {dim('提示: 在 .env 文件中设置 OPENAI_API_KEY')}")
        issues.append("api_key")

    # Base URL 检查
    if settings.api_base:
        print(f"   {success('✓')} Base URL: {settings.api_base}")
    else:
        print(f"   {warning('⚠')} Base URL 未配置（将使用默认值）")

    # 模型检查
    if settings.model:
        print(f"   {success('✓')} 模型: {settings.model}")
    else:
        print(f"   {warning('⚠')} 模型未配置（将使用默认值）")

    # 3. 工作区目录检查
    print(f"\n{info('3. 工作区目录检查')}")
    workspace = settings.workspace
    if workspace.exists():
        print(f"   {success('✓')} 工作区存在: {workspace}")
    else:
        print(f"   {warning('⚠')} 工作区不存在: {workspace}")
        print(f"   {dim('提示: 运行 kb init 初始化工作区')}")
        issues.append("workspace")

    # 必要子目录检查
    required_dirs = [
        "raw",
        "wiki/summaries",
        "wiki/concepts",
        "outputs/summaries",
        "outputs/concepts",
        "manifests/sources",
        "data",
        "logs",
    ]
    missing_dirs = []
    for dir_path in required_dirs:
        full_path = workspace / dir_path
        if not full_path.exists():
            missing_dirs.append(dir_path)

    if missing_dirs:
        print(f"   {warning('⚠')} 缺少目录: {', '.join(missing_dirs)}")
        print(f"   {dim('提示: 运行 kb init 创建目录结构')}")
    else:
        print(f"   {success('✓')} 所有必要目录存在")

    # 4. 磁盘空间检查
    print(f"\n{info('4. 磁盘空间检查')}")
    try:
        usage = shutil.disk_usage(workspace)
        free_gb = usage.free / (1024**3)
        total_gb = usage.total / (1024**3)
        used_gb = usage.used / (1024**3)
        used_percent = (usage.used / usage.total) * 100

        print(f"   总空间: {total_gb:.1f} GB")
        print(f"   已用: {used_gb:.1f} GB ({used_percent:.1f}%)")
        print(f"   可用: {free_gb:.1f} GB")

        if free_gb < 1:
            print(f"   {error('✗')} 磁盘空间不足（剩余 < 1GB）")
            issues.append("disk_space")
        elif free_gb < 5:
            print(f"   {warning('⚠')} 磁盘空间偏低（剩余 < 5GB）")
        else:
            print(f"   {success('✓')} 磁盘空间充足")
    except OSError as e:
        print(f"   {warning('⚠')} 无法检查磁盘空间: {e}")

    # 5. 核心依赖检查
    print(f"\n{info('5. 核心依赖检查')}")
    dependencies = [
        ("openai", "OpenAI API 客户端"),
        ("chromadb", "向量数据库"),
        ("markitdown", "文档解析"),
    ]

    missing_deps = []
    for module_name, description in dependencies:
        try:
            __import__(module_name)
            print(f"   {success('✓')} {module_name} ({description})")
        except ImportError:
            print(f"   {error('✗')} {module_name} ({description}) - 未安装")
            missing_deps.append(module_name)

    if missing_deps:
        print(f"   {dim('提示: pip install -e .[all] 安装所有依赖')}")
        issues.append("dependencies")

    # 6. 可选依赖检查
    print(f"\n{info('6. 可选依赖检查')}")
    optional_deps = [
        ("faster_whisper", "音频转录"),
        ("fitz", "PDF 解析 (PyMuPDF)"),
        ("pdfplumber", "PDF 解析 (pdfplumber)"),
        ("PIL", "图像处理 (Pillow)"),
    ]

    for module_name, description in optional_deps:
        try:
            __import__(module_name)
            print(f"   {success('✓')} {module_name} ({description})")
        except ImportError:
            print(f"   {dim('○')} {module_name} ({description}) - 未安装（可选）")

    # 6.5 外部工具检查
    print(f"\n{info('6.5 外部工具检查')}")
    external_tools = [
        ("ffprobe", "音频/视频时长检测", "brew install ffmpeg"),
    ]
    for tool_name, description, install_hint in external_tools:
        tool_path = shutil.which(tool_name)
        if tool_path:
            print(f"   {success('✓')} {tool_name} ({description})")
        else:
            print(f"   {warning('⚠')} {tool_name} ({description}) - 未安装")
            print(f"   {dim(f'提示: {install_hint}')}")

    # 7. 环境变量检查
    print(f"\n{info('7. 环境变量检查')}")
    env_vars = [
        "OPENAI_API_KEY",
        "OPENAI_API_BASE",
        "MODEL",
        "WORKSPACE",
    ]

    for var in env_vars:
        value = os.environ.get(var)
        if value:
            if var == "OPENAI_API_KEY":
                display_value = f"...{value[-6:]}" if len(value) > 6 else "***"
            else:
                display_value = value
            print(f"   {success('✓')} {var} = {display_value}")
        else:
            print(f"   {dim('○')} {var} = (未设置)")

    # 8. 配置文件检查
    print(f"\n{info('8. 配置文件检查')}")
    env_file = workspace / ".env"
    if env_file.exists():
        print(f"   {success('✓')} .env 文件存在")
    else:
        print(f"   {warning('⚠')} .env 文件不存在")
        print(f"   {dim('提示: 运行 kb init 创建配置文件')}")

    # 总结
    print("\n" + "=" * 60)
    if issues:
        print(f"{error('发现以下问题:')}")
        for issue in issues:
            if issue == "python_version":
                print("  - Python 版本过低，请升级到 3.11+")
            elif issue == "api_key":
                print("  - API Key 未配置，请在 .env 中设置 OPENAI_API_KEY")
            elif issue == "workspace":
                print("  - 工作区不存在，请运行 kb init")
            elif issue == "disk_space":
                print("  - 磁盘空间不足，请清理磁盘")
            elif issue == "dependencies":
                print("  - 核心依赖缺失，请运行 pip install -e .[all]")

        print("\n建议操作:")
        if "api_key" in issues or "workspace" in issues:
            print("  1. 运行: kb init")
        if "dependencies" in issues:
            print("  2. 运行: pip install -e .[all]")

        print()
        return 1
    else:
        print(f"{success('✓ 所有检查通过！环境配置正常。')}")
        print()
        return 0
