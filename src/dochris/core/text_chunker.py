#!/usr/bin/env python3
"""
文本分块模块

提供结构感知的文本分块功能：
1. 优先按 Markdown 标题结构分段
2. 回退到语义分块（在段落/句子边界断开）
3. 固定长度分段（最后的回退方案）

主要函数:
    structure_aware_split(): 按文档结构分段
    semantic_chunk(): 语义分块
    fixed_size_chunk(): 固定长度分块

使用示例:
    from dochris.core.text_chunker import structure_aware_split

    chunks = structure_aware_split(text, chunk_size=4000, overlap=200)
"""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    """文本块数据类

    Attributes:
        content: 块内容
        title: 块标题（如果有）
        level: 标题层级（1-6，0 表示无标题）
        index: 块索引
    """

    content: str
    title: str = ""
    level: int = 0
    index: int = 0

    def __len__(self) -> int:
        """返回内容长度（字符数）"""
        return len(self.content)


def structure_aware_split(text: str, chunk_size: int = 4000, overlap: int = 200) -> list[TextChunk]:
    """按文档结构智能分段

    优先级：
    1. 检测 Markdown 标题结构（# ## ### 等）
    2. 检测数字编号结构（1. 2. 3. 或 一、二、三、）
    3. 回退到语义分块

    Args:
        text: 待分段的文本
        chunk_size: 目标块大小（字符数）
        overlap: 重叠字符数（用于上下文连续性）

    Returns:
        TextChunk 列表
    """
    # 尝试 Markdown 标题分段
    chunks = _split_by_markdown_headers(text)
    if chunks and len(chunks) > 1:
        logger.debug(f"使用 Markdown 标题分段，共 {len(chunks)} 块")
        # 如果单个块过大，进一步分块
        return _refine_large_chunks(chunks, chunk_size, overlap)

    # 尝试数字编号分段
    chunks = _split_by_numbering(text)
    if chunks and len(chunks) > 1:
        logger.debug(f"使用数字编号分段，共 {len(chunks)} 块")
        return _refine_large_chunks(chunks, chunk_size, overlap)

    # 回退到语义分块
    logger.debug("回退到语义分块")
    return semantic_chunk(text, chunk_size, overlap)


def _split_by_markdown_headers(text: str) -> list[TextChunk]:
    """按 Markdown 标题分段

    识别 # ## ### #### ##### ###### 等标题
    """
    chunks: list[TextChunk] = []
    lines = text.split("\n")

    current_chunk: list[str] = []
    current_title = ""
    current_level = 0

    for line in lines:
        # 检测 Markdown 标题
        header_match = re.match(r"^(#{1,6})\s+(.+)$", line)

        if header_match:
            # 保存当前块
            if current_chunk:
                content = "\n".join(current_chunk).strip()
                if content:
                    chunks.append(
                        TextChunk(
                            content=content,
                            title=current_title,
                            level=current_level,
                            index=len(chunks),
                        )
                    )

            # 开始新块
            current_level = len(header_match.group(1))
            current_title = header_match.group(2).strip()
            current_chunk = [line]
        else:
            current_chunk.append(line)

    # 保存最后一块
    if current_chunk:
        content = "\n".join(current_chunk).strip()
        if content:
            chunks.append(
                TextChunk(
                    content=content, title=current_title, level=current_level, index=len(chunks)
                )
            )

    return chunks


def _split_by_numbering(text: str) -> list[TextChunk]:
    """按数字编号分段

    识别：
    - 1. 2. 3. 等数字编号
    - 一、二、三、等中文编号
    - （1）（2）（3）等括号编号
    """
    chunks: list[TextChunk] = []
    lines = text.split("\n")

    current_chunk: list[str] = []
    current_title = ""
    current_index = 0

    # 编号正则表达式
    patterns = [
        r"^(\d+|[一二三四五六七八九十]+)[.、]\s*(.+)$",  # 1. 或 一、
        r"^[（(]\s*\d+\s*[)）]\s*(.+)$",  # （1）
    ]
    combined_pattern = "|".join(f"({p})" for p in patterns)

    for line in lines:
        match = re.match(combined_pattern, line)

        if match and current_chunk:
            # 检查是否真的是新的章节（行首，前面有空行）
            if len(current_chunk) > 0:
                # 保存当前块
                content = "\n".join(current_chunk).strip()
                if content:
                    chunks.append(
                        TextChunk(content=content, title=current_title, level=1, index=len(chunks))
                    )

            # 开始新块
            # 提取标题（从各个匹配组中找到）
            for group in match.groups()[1::2]:  # 跳过完整匹配，只看捕获组
                if group:
                    current_title = group.strip()
                    break
            else:
                current_title = line.strip()[:50]  # 取前50字符作为标题
            current_chunk = [line]
            current_index += 1
        else:
            if line.strip() or current_chunk:  # 只添加非空行
                current_chunk.append(line)

    # 保存最后一块
    if current_chunk:
        content = "\n".join(current_chunk).strip()
        if content:
            chunks.append(
                TextChunk(content=content, title=current_title, level=1, index=len(chunks))
            )

    # 只有多于1个块时才认为分段成功
    return chunks if len(chunks) > 1 else []


def _refine_large_chunks(chunks: list[TextChunk], chunk_size: int, overlap: int) -> list[TextChunk]:
    """处理过大的块

    对超过 chunk_size 的块进行进一步分块
    """
    result = []

    for chunk in chunks:
        if len(chunk) <= chunk_size:
            result.append(chunk)
        else:
            # 对大块进行语义分块
            sub_chunks = semantic_chunk(chunk.content, chunk_size, overlap)
            # 添加子块，继承父块标题
            for _i, sub_chunk in enumerate(sub_chunks):
                sub_chunk.title = chunk.title or sub_chunk.title
                sub_chunk.level = chunk.level
                sub_chunk.index = len(result)
                result.append(sub_chunk)

    return result


def semantic_chunk(text: str, chunk_size: int = 4000, overlap: int = 200) -> list[TextChunk]:
    """语义分块

    在段落/句子边界处断开，避免在句子中间截断

    Args:
        text: 待分块的文本
        chunk_size: 目标块大小（字符数）
        overlap: 重叠字符数

    Returns:
        TextChunk 列表
    """
    chunks = []

    # 按段落分割（保留空行作为段落分隔）
    paragraphs = text.split("\n\n")

    current_chunk: list[str] = []
    current_length = 0
    chunk_index = 0

    for para in paragraphs:
        para_length = len(para)

        # 如果单个段落就超过 chunk_size，需要按句子分割
        if para_length > chunk_size:
            # 先保存当前块
            if current_chunk:
                chunks.append(
                    TextChunk(content="\n\n".join(current_chunk).strip(), index=chunk_index)
                )
                chunk_index += 1
                current_chunk = []
                current_length = 0

            # 对大段落进行句子级分割
            sentences = _split_sentences(para)
            for sentence in sentences:
                if current_length + len(sentence) > chunk_size and current_chunk:
                    chunks.append(
                        TextChunk(content=" ".join(current_chunk).strip(), index=chunk_index)
                    )
                    chunk_index += 1
                    # 保留 overlap
                    current_chunk = _get_overlap_sentences(
                        sentences,
                        sentences.index(sentence) if sentence in sentences else 0,
                        overlap,
                    )
                    current_length = sum(len(s) for s in current_chunk)
                else:
                    current_chunk.append(sentence)
                    current_length += len(sentence)
        else:
            # 正常段落处理
            if current_length + para_length > chunk_size and current_chunk:
                chunks.append(
                    TextChunk(content="\n\n".join(current_chunk).strip(), index=chunk_index)
                )
                chunk_index += 1

                # 处理 overlap
                if overlap > 0 and current_chunk:
                    # 从上一个块的末尾提取 overlap 内容
                    last_content = "\n\n".join(current_chunk)
                    overlap_text = (
                        last_content[-overlap:] if len(last_content) > overlap else last_content
                    )
                    current_chunk = [overlap_text, para]
                    current_length = len(overlap_text) + para_length
                else:
                    current_chunk = [para]
                    current_length = para_length
            else:
                current_chunk.append(para)
                current_length += para_length

    # 保存最后一块
    if current_chunk:
        chunks.append(TextChunk(content="\n\n".join(current_chunk).strip(), index=chunk_index))

    return chunks


def _split_sentences(text: str) -> list[str]:
    """将文本分割成句子

    简单实现，基于中文和英文的句号、问号、感叹号
    """
    # 句子分隔符（包括中英文）
    sentence_endings = r"([。！？.!?]+)\s*"
    parts = re.split(sentence_endings, text)

    sentences = []
    current = ""

    for i, part in enumerate(parts):
        if i % 2 == 0:
            # 文本部分
            current += part
        else:
            # 标点符号部分
            current += part
            if current.strip():
                sentences.append(current.strip())
            current = ""

    # 处理最后剩余的文本
    if current.strip():
        sentences.append(current.strip())

    return sentences


def _get_overlap_sentences(sentences: list[str], current_index: int, overlap: int) -> list[str]:
    """获取重叠部分的句子

    从当前索引向前获取约 overlap 字符数的句子
    """
    overlap_sentences = []
    overlap_length = 0

    # 从当前向前找
    for i in range(max(0, current_index - 10), current_index):
        if i < len(sentences):
            sentence = sentences[i]
            if overlap_length + len(sentence) <= overlap:
                overlap_sentences.append(sentence)
                overlap_length += len(sentence)
            else:
                break

    return overlap_sentences


def fixed_size_chunk(text: str, chunk_size: int = 4000, overlap: int = 200) -> list[TextChunk]:
    """固定长度分块（最后的回退方案）

    Args:
        text: 待分块的文本
        chunk_size: 块大小（字符数）
        overlap: 重叠字符数

    Returns:
        TextChunk 列表
    """
    chunks = []
    text_length = len(text)

    start = 0
    index = 0

    while start < text_length:
        end = start + chunk_size

        # 如果不是最后一块，尝试在最近的换行符处断开
        if end < text_length:
            # 查找最近的换行符
            newline_pos = text.rfind("\n", start, end)
            if newline_pos > start + chunk_size // 2:  # 至少有半个块
                end = newline_pos + 1

        chunk_content = text[start:end].strip()
        if chunk_content:
            chunks.append(TextChunk(content=chunk_content, index=index))
            index += 1

        # 移动 start，考虑 overlap
        start = end - overlap if end < text_length else end

    return chunks


def count_chars(text: str) -> int:
    """统计文本字符数（汉字+英文+标点）

    Args:
        text: 待统计的文本

    Returns:
        字符数
    """
    return len(text)


def should_use_hierarchical(text: str, direct_limit: int = 10000) -> str:
    """判断应该使用哪种摘要策略

    Args:
        text: 待处理的文本
        direct_limit: 直接摘要的字符数上限（默认 1 万字）

    Returns:
        策略名称: "direct", "map_reduce", "hierarchical"
    """
    char_count = count_chars(text)

    if char_count <= direct_limit:
        return "direct"
    elif char_count <= direct_limit * 3:  # 3 万字以下
        return "map_reduce"
    elif char_count <= direct_limit * 10:  # 10 万字以下
        return "hierarchical"
    else:
        # 超大文档（>10万字）使用 map_reduce + 大块，避免 API 调用爆炸
        return "map_reduce"
