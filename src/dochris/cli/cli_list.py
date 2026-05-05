"""CLI 命令：列出所有 manifest"""

import argparse

from dochris.cli.cli_utils import dim, error, info, success, warning
from dochris.manifest import get_all_manifests
from dochris.settings import get_default_workspace


def cmd_list(args: argparse.Namespace) -> int:
    """列出所有 manifest"""
    workspace = get_default_workspace()
    manifests = get_all_manifests(workspace, status=args.status)

    # 按类型过滤
    if args.type:
        manifests = [m for m in manifests if m.get("file_type", "") == args.type]

    # 排序
    sort_key = args.sort
    if sort_key == "quality":
        manifests.sort(key=lambda m: m.get("quality_score", 0), reverse=True)
    elif sort_key == "size":
        manifests.sort(key=lambda m: m.get("size_bytes", 0), reverse=True)
    elif sort_key == "time":
        manifests.sort(key=lambda m: m.get("ingested_at", ""), reverse=True)
    # 默认按 id 排序（已经是 sorted 的）

    # 限制数量
    limit = args.limit or 20
    manifests = manifests[:limit]

    if not manifests:
        print(f"\n{dim('没有找到匹配的 manifest 记录')}")
        if args.status or args.type:
            print(f"{dim('💡 尝试去掉过滤条件，或先运行 kb ingest 添加文件')}")
        return 0

    # 统计
    status_counts: dict[str, int] = {}
    for m in manifests:
        s = m.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    print(f"\n{info('Manifest 列表')} (显示 {len(manifests)} 条)")
    if args.status or args.type:
        filters = []
        if args.status:
            filters.append(f"状态={args.status}")
        if args.type:
            filters.append(f"类型={args.type}")
        print(f"  过滤: {', '.join(filters)}")
    print(f"{'=' * 80}")

    # 表头
    print(f"  {'ID':<12} {'状态':<14} {'类型':<10} {'标题':<30} {'质量':>4}  {'大小':>8}")
    print(f"  {'─' * 12} {'─' * 14} {'─' * 10} {'─' * 30} {'─' * 4}  {'─' * 8}")

    for m in manifests:
        src_id = m.get("id", "")
        status = m.get("status", "unknown")
        file_type = m.get("file_type", "")
        title = m.get("title", "")[:28]
        quality = m.get("quality_score", 0)
        size = m.get("size_bytes", 0)

        # 状态颜色
        if status == "compiled":
            status_str = success(status)
        elif status in ("promoted", "promoted_to_wiki"):
            status_str = info(status)
        elif status == "compile_failed":
            status_str = error(status)
        else:
            status_str = dim(status)

        # 质量分颜色
        if quality >= 85:
            quality_str = success(str(quality))
        elif quality > 0:
            quality_str = warning(str(quality))
        else:
            quality_str = dim("-")

        # 文件大小格式化
        if size > 1024 * 1024:
            size_str = f"{size / 1024 / 1024:.1f}MB"
        elif size > 1024:
            size_str = f"{size / 1024:.1f}KB"
        else:
            size_str = f"{size}B"

        print(
            f"  {src_id:<12} {status_str:<14} {file_type:<10} {title:<30} {quality_str:>4}  {dim(size_str):>8}"
        )

    print(f"{'=' * 80}")

    # 底部统计
    print("  状态分布: ", end="")
    parts = []
    for s, c in sorted(status_counts.items()):
        parts.append(f"{s}({c})")
    print(", ".join(parts))

    print()
    return 0
