#!/usr/bin/env python3
"""
基础摄入示例

演示如何扫描目录并创建 manifest。

使用方法:
    1. 修改下面的 notes_path 为你的笔记目录
    2. 运行: python examples/01_basic_ingest.py

输出:
    - 显示发现的文件数量和前 5 个文件信息
"""
from __future__ import annotations

from pathlib import Path


def main() -> None:
    """执行基础摄入扫描"""
    # ==================== 配置区 ====================
    # 修改此路径为你的笔记目录
    notes_path = Path("/path/to/your/notes")
    # ================================================

    # 检查路径是否存在
    if not notes_path.exists():
        print(f"⚠️  路径不存在: {notes_path}")
        print("请修改脚本中的 notes_path 变量")
        return

    # 导入扫描函数
    from dochris.phases.phase1_ingestion import scan_source_dir
    import logging

    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)

    # 扫描目录
    print(f"📂 扫描目录: {notes_path}")
    files = scan_source_dir(notes_path, logger)

    # 显示结果
    print(f"\n✅ 发现 {len(files)} 个文件")
    if files:
        print("\n前 5 个文件:")
        for f in files[:5]:
            size_mb = f.get("size", 0) / 1024 / 1024
            print(f"  - {f['name']} ({f['ext']}, {f['category']}, {size_mb:.2f} MB)")

    # 按类别统计
    if files:
        from collections import Counter

        cat_counts = Counter(f["category"] for f in files)
        print("\n类别分布:")
        for cat, count in cat_counts.most_common():
            print(f"  {cat}: {count} 个文件")


if __name__ == "__main__":
    main()
