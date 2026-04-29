"""CLI 命令：状态、晋升、质量检查"""

import argparse
import json
from pathlib import Path

from dochris.cli.cli_utils import error, info, show_status, success
from dochris.settings import get_default_workspace


def cmd_status(args: argparse.Namespace) -> int:
    """显示状态"""
    workspace = args.workspace if hasattr(args, "workspace") else None
    if isinstance(workspace, str):
        workspace = Path(workspace)
    return show_status(workspace)


def cmd_promote(args: argparse.Namespace) -> int:
    """Promote 操作"""
    from dochris.promote import (
        promote_to_curated,
        promote_to_wiki,
    )
    from dochris.quality.quality_gate import quality_gate

    src_id = args.src_id.upper()
    target = args.to

    workspace = get_default_workspace()

    # 先进行质量门禁检查
    gate = quality_gate(workspace, src_id)
    if not gate["passed"]:
        print(f"{error('✗ 质量门禁未通过')}")
        print(f"  原因: {gate['reason']}")
        return 1

    print(f"{info('✓ 质量门禁通过')} (分数: {gate.get('quality_score', 0)})")

    if target == "wiki":
        ok = promote_to_wiki(workspace, src_id)
    elif target == "curated":
        ok = promote_to_curated(workspace, src_id)
    elif target == "obsidian":
        from dochris.vault.bridge import promote_to_obsidian

        ok = promote_to_obsidian(workspace, src_id)
    else:
        print(f"{error('未知目标')}: {target}")
        print("  支持: wiki, curated, obsidian")
        return 1

    if ok:
        print(f"{success(f'✓ 晋升成功: {src_id} → {target}')}")
        return 0
    else:
        print(f"{error(f'✗ 晋升失败: {src_id}')}")
        return 1


def cmd_quality(args: argparse.Namespace) -> int:
    """质量检查"""
    from dochris.quality.quality_gate import (
        check_pollution,
        generate_report,
        quality_gate,
        scan_wiki,
    )

    workspace = get_default_workspace()

    if args.report:
        report = generate_report(workspace)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.check_pollution:
        result = check_pollution(workspace)
        if result["polluted"]:
            print(f"{error('✗ 发现污染!')}")
            print(f"  {result['details']}")
            return 1
        else:
            print(f"{success('✓ wiki/ 干净，无污染')}")
            return 0

    if args.src_id:
        result = quality_gate(workspace, args.src_id)
        if result["passed"]:
            print(f"{success('✓ 质量门禁通过')}")
            print(f"  {result['src_id']}: {result.get('title', '')[:50]}")
            print(f"  质量分数: {result.get('quality_score', 0)}/100")
            return 0
        else:
            print(f"{error('✗ 质量门禁未通过')}")
            print(f"  原因: {result['reason']}")
            return 1

    # 默认扫描 wiki
    result = scan_wiki(workspace)
    print(info("wiki/ 扫描结果:"))
    print(f"  摘要文件: {result['wiki_summaries']}")
    print(f"  概念文件: {result['wiki_concepts']}")
    print(f"  总计: {result['wiki_total']}")
    return 0
