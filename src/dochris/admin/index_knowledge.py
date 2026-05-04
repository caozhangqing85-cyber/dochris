#!/usr/bin/env python3
"""
知识库向量索引脚本
索引 Obsidian 和资料库的关键文件到 ChromaDB
"""

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import chromadb
from chromadb.utils import embedding_functions

# 导入配置
sys.path.insert(0, str(Path(__file__).parent))
from dochris.settings import (
    get_data_dir,
    get_settings,
    get_workspace,
)

# ============================================================
# 配置（从 config 获取）
# ============================================================

CHROMA_PATH = get_data_dir()

# 关键文件列表（优先索引）
# 相对于 Obsidian vault 的路径
PRIORITY_FILES = [
    # Obsidian 职业规划
    "职业规划/AI学习复利系统SOP-最终版.md",
    "职业规划/Obsidian学习模板配置指南.md",
    "职业规划/总览-人生设计仪表盘_2026.md",
    "职业规划/计划-6周执行SOP_2026.md",
    # Obsidian 改造计划
    "04-个人成长/个人提升计划/00-总览.md",
    "04-个人成长/个人提升计划/01-近视手术/医疗记录-近视手术.md",
    "04-个人成长/个人提升计划/02-减肥塑形/居家生活记录.md",
    "04-个人成长/个人提升计划/03-体态纠正/我的体态纠正训练计划.md",
    # 资料库 PDF（恋爱、减肥、学习方法）
    "恋爱社交/好男人恋爱课",
    "减肥健康/冯雪科学减肥",
    "学习方法/费曼学习法",
]

# 初始化日志
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# 初始化 ChromaDB
try:
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
except Exception as e:
    logger.error(f"初始化 ChromaDB 失败: {e}")
    logger.error(f"请确保数据目录存在: {CHROMA_PATH}")
    sys.exit(1)

# 使用 HuggingFace embeddings
try:
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="BAAI/bge-small-zh-v1.5"  # 中文语义模型
    )
except Exception as e:
    logger.error(f"初始化 embedding 函数失败: {e}")
    logger.error("请确保已安装: pip install sentence-transformers")
    sys.exit(1)

# 创建或获取 collection
collection = client.get_or_create_collection(
    name="knowledge_base",
    embedding_function=cast(Any, sentence_transformer_ef),
)


def clean_text(text: str) -> str:
    """清理文本，去除多余空白"""
    if not text:
        return ""
    # 移除多余空白
    text = re.sub(r"\n+", "\n", text)
    text = re.sub(r" +", " ", text)
    return text.strip()


def truncate_text(text: str, max_chars: int = 4000) -> str:
    """截断文本到最大字符数"""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def extract_markdown_summary(md_file: str | Path) -> str:
    """从 markdown 文件提取摘要"""
    text = Path(md_file).read_text(encoding="utf-8", errors="ignore")
    lines = text.split("\n")

    # 提取标题和前 100 行
    summary_lines = []
    for _i, line in enumerate(lines[:100]):
        if line.strip():
            summary_lines.append(line)

    # 提取所有 ## 标题下的内容
    for line in lines:
        if line.startswith("## "):
            line.strip()
            idx = lines.index(line)
            # 提取该标题下的 20 行
            content = "\n".join(lines[idx : idx + 20])
            summary_lines.append(content)

    return "\n".join(summary_lines)


def index_file(file_path: str | Path, source_type: str = "obsidian") -> None:
    """索引单个文件"""
    try:
        file_path = Path(file_path)

        if not file_path.exists():
            logger.warning(f"文件不存在: {file_path}")
            return

        logger.info(f"索引中: {file_path}")

        if source_type == "obsidian":
            # Markdown 文件
            if file_path.suffix == ".md":
                content = extract_markdown_summary(file_path)
                doc_type = "markdown"

                # 提取标题
                title = file_path.stem
                try:
                    text = file_path.read_text(encoding="utf-8", errors="ignore")
                    first_line = text.split("\n")[0]
                    if first_line.strip().startswith("#"):
                        title = first_line.strip("#").strip()
                except (OSError, UnicodeDecodeError) as e:
                    logger.debug(f"读取标题失败: {e}")

            else:
                return

        elif source_type == "pdf":
            # PDF 文件（暂时跳过，需要 markitdown）
            logger.info(f"跳过 PDF（需要 markitdown 处理）: {file_path}")
            return

        # 清理和截断
        content = clean_text(content)
        content = truncate_text(content, 4000)

        # 生成唯一 ID
        # 尝试将路径转换为相对路径
        workspace = get_workspace()
        try:
            rel_path = file_path.relative_to(workspace)
        except ValueError:
            # 尝试相对于其他可能的基础路径
            rel_path = Path(file_path.name)
            _s = get_settings()
            obsidian_vault = _s.obsidian_vaults[0] if _s.obsidian_vaults else None
            if obsidian_vault and file_path.is_relative_to(obsidian_vault):
                rel_path = file_path.relative_to(obsidian_vault)
            elif _s.source_path and file_path.is_relative_to(_s.source_path):
                rel_path = file_path.relative_to(_s.source_path)

        doc_id = f"{source_type}_{rel_path}".replace("/", "_")

        # 添加到 collection
        collection.add(
            documents=[content],
            metadatas=[
                {
                    "path": str(file_path),
                    "type": doc_type,
                    "source": source_type,
                    "title": title,
                    "indexed_at": datetime.now().isoformat(),
                }
            ],
            ids=[doc_id],
        )

        logger.info(f"已索引: {title}")

    except (OSError, json.JSONDecodeError, KeyError, ValueError, RuntimeError) as e:
        logger.error(f"索引失败 {file_path}: {e}")


def index_obsidian_priority() -> None:
    """索引 Obsidian 优先文件"""
    _s = get_settings()
    obsidian_vault = _s.obsidian_vaults[0] if _s.obsidian_vaults else None
    if obsidian_vault is None:
        logger.warning("未配置 OBSIDIAN_VAULT，请在 .env 中设置 OBSIDIAN_VAULT")
        logger.warning("或使用环境变量: export OBSIDIAN_VAULT=/path/to/vault")
        return

    logger.info("=" * 60)
    logger.info("索引 Obsidian 优先文件")
    logger.info(f"Vault: {obsidian_vault}")
    logger.info("=" * 60)

    for rel_path in PRIORITY_FILES:
        file_path = obsidian_vault / rel_path
        if file_path.exists():
            index_file(file_path, "obsidian")
        else:
            logger.warning(f"文件不存在: {rel_path}")


def index_obsidian_all(limit: int = 50) -> None:
    """索引 Obsidian 所有 markdown 文件（限制数量）"""
    _s = get_settings()
    obsidian_vault = _s.obsidian_vaults[0] if _s.obsidian_vaults else None
    if obsidian_vault is None:
        logger.warning("未配置 OBSIDIAN_VAULT，请在 .env 中设置 OBSIDIAN_VAULT")
        logger.warning("或使用环境变量: export OBSIDIAN_VAULT=/path/to/vault")
        return

    logger.info("=" * 60)
    logger.info(f"索引 Obsidian 所有文件（最多 {limit} 个）")
    logger.info(f"Vault: {obsidian_vault}")
    logger.info("=" * 60)

    count = 0
    for md_file in obsidian_vault.rglob("*.md"):
        if count >= limit:
            break
        index_file(md_file, "obsidian")
        count += 1


def search_knowledge(query: str, n_results: int = 5) -> None:
    """搜索知识库"""
    logger.info(f"搜索: '{query}'")
    logger.info("=" * 60)

    results = collection.query(query_texts=[query], n_results=n_results)

    documents = results.get("documents")
    if not documents or not documents[0]:
        logger.info("未找到结果")
        return

    metadatas = results.get("metadatas")
    if not metadatas:
        metadatas_list: list[list] = [[]]
    else:
        metadatas_list = metadatas

    for i, (doc, meta) in enumerate(zip(documents[0], metadatas_list[0], strict=False)):
        meta_dict = dict(meta) if not isinstance(meta, dict) else meta
        logger.info(f"{i + 1}. {meta_dict.get('title', '无标题')}")
        logger.info(f"路径: {meta_dict.get('path', '')}")
        logger.info(f"类型: {meta_dict.get('type', '')} | 来源: {meta_dict.get('source', '')}")
        logger.info(f"内容片段: {doc[:300]}...")


def show_stats() -> None:
    """显示统计信息"""
    logger.info("=" * 60)
    logger.info("向量数据库统计")
    logger.info("=" * 60)

    count = collection.count()
    logger.info(f"总文档数: {count}")

    # 按来源分组
    sources: dict[str, int] = {}
    collection_data = collection.get()
    metadatas = collection_data.get("metadatas")
    if metadatas:
        for doc in metadatas:
            doc_dict = dict(doc) if not isinstance(doc, dict) else doc
            source = str(doc_dict.get("source", "unknown"))
            sources[source] = sources.get(source, 0) + 1

    logger.info("按来源分组:")
    for source, cnt in sources.items():
        logger.info(f"  - {source}: {cnt}")


def main() -> None:
    """主函数"""
    if len(sys.argv) < 2:
        print("用法:")
        print("  python index_knowledge.py index-priority  # 索引优先文件")
        print("  python index_knowledge.py index-all       # 索引所有文件")
        print("  python index_knowledge.py search <查询>    # 搜索")
        print("  python index_knowledge.py stats           # 统计")
        print("\n配置:")
        print(
            f"  Obsidian Vault: {get_settings().obsidian_vaults[0] if get_settings().obsidian_vaults else None}"
        )
        print(f"  Source Path: {get_settings().source_path}")
        print(f"  Workspace: {get_workspace()}")
        print(f"  Data Dir: {CHROMA_PATH}")
        sys.exit(1)

    command = sys.argv[1]

    if command == "index-priority":
        index_obsidian_priority()
        show_stats()

    elif command == "index-all":
        index_obsidian_all(limit=50)
        show_stats()

    elif command == "search":
        if len(sys.argv) < 3:
            print("请提供搜索查询")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        search_knowledge(query)

    elif command == "stats":
        show_stats()

    else:
        print(f"未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
