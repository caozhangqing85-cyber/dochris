"""
CLI 工具函数：颜色输出、样式、状态显示
"""

import sys
from pathlib import Path

from dochris.manifest import (
    get_all_manifests,
)
from dochris.settings import (
    get_default_workspace,
    get_logs_dir,
    get_manifests_dir,
    get_outputs_dir,
    get_raw_dir,
    get_settings,
    get_wiki_dir,
)

# ============================================================
# 颜色输出
# ============================================================


class Colors:
    """ANSI 颜色代码"""

    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    DIM = "\033[2m"


def style(text: str, color: str) -> str:
    """应用颜色样式"""
    if not sys.stdout.isatty():
        return text
    return f"{color}{text}{Colors.RESET}"


def success(text: str) -> str:
    return style(text, Colors.GREEN)


def warning(text: str) -> str:
    return style(text, Colors.YELLOW)


def error(text: str) -> str:
    return style(text, Colors.RED)


def info(text: str) -> str:
    return style(text, Colors.CYAN)


def dim(text: str) -> str:
    return style(text, Colors.DIM)


def bold(text: str) -> str:
    return style(text, Colors.BOLD)


# ============================================================
# 状态显示
# ============================================================


def show_status(workspace: Path | None = None) -> int:
    """显示系统状态概览"""
    if workspace is None:
        workspace = get_default_workspace()

    print(f"\n{'=' * 60}")
    print(f"{info('知识库系统状态')}")
    print(f"{'=' * 60}")

    # 工作区信息
    print(f"\n{bold('工作区:')}")
    print(f"  路径: {workspace}")

    # 源目录配置
    _s = get_settings()
    print(f"\n{bold('源目录:')}")
    if _s.source_path:
        print(f"  主源: {_s.source_path}")
        if _s.source_path.exists() and _s.source_path.is_dir():
            files_count = sum(1 for _ in _s.source_path.rglob("*") if _.is_file())
            print(f"  状态: {success('✓ 可用')} ({files_count} 个文件)")
        else:
            print(f"  状态: {warning('⚠ 不存在或不是目录')}")
    else:
        print(f"  主源: {dim('未配置')}")

    if _s.obsidian_vaults:
        print(f"  Obsidian Vaults: {len(_s.obsidian_vaults)} 个")
        for v in _s.obsidian_vaults[:3]:
            status = success("✓") if v.exists() else error("✗")
            print(f"    {status} {v}")
    else:
        print(f"  Obsidian Vaults: {dim('未配置')}")

    # 目录结构
    print(f"\n{bold('目录结构:')}")
    dirs = [
        ("原始文件", get_raw_dir()),
        ("编译输出", get_outputs_dir()),
        ("Wiki 内容", get_wiki_dir()),
        ("Manifests", get_manifests_dir()),
        ("日志文件", get_logs_dir()),
    ]
    for name, path in dirs:
        if path.exists() and path.is_dir():
            files = sum(1 for _ in path.rglob("*.md") if _.is_file())
            print(f"  {name}: {success('✓')} ({files} 文件)")
        else:
            print(f"  {name}: {dim('-')}")

    # Manifest 统计
    print(f"\n{bold('Manifest 统计:')}")
    manifests = get_all_manifests(workspace)
    status_counts = {}
    score_total = 0
    score_count = 0
    for m in manifests:
        s = m["status"]
        status_counts[s] = status_counts.get(s, 0) + 1
        score = m.get("quality_score", 0)
        if score > 0:
            score_total += score
            score_count += 1

    print(f"  总计: {len(manifests)} 个")
    for status, count in sorted(status_counts.items()):
        color = success if status in ("compiled", "promoted_to_wiki", "promoted") else warning
        print(f"  {status}: {color(str(count))} 个")

    if score_count > 0:
        avg_score = score_total / score_count
        print(f"  平均质量分: {score_total}/{score_count} = {info(str(round(avg_score, 1)))}")

    # API 配置
    print(f"\n{bold('API 配置:')}")
    api_key = _s.api_key
    if api_key:
        masked = f"...{api_key[-6:]}" if len(api_key) > 6 else "***"
        print(f"  API Key: {success('✓ 已配置')} ({masked})")
        print(f"  Base URL: {_s.api_base}")
        print(f"  模型: {_s.model}")
    else:
        print(f"  API Key: {error('✗ 未配置')}")

    print(f"\n{bold('其他配置:')}")
    print(f"  并发数: {_s.max_concurrency}")
    print(f"  质量门槛: {_s.min_quality_score}")
    print(f"  最大内容: {_s.max_content_chars} 字符")

    print(f"{'=' * 60}\n")
    return 0
