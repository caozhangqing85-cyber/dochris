#!/usr/bin/env python3
"""
分层摘要器模块

提供 Map-Reduce 和分层摘要功能，从 LLMClient 拆分出来。
"""

import asyncio
import json
import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from dochris.core.text_chunker import TextChunk

    from .llm_client import LLMClient

from .retry_manager import RetryManager

logger = logging.getLogger(__name__)

# 分层摘要最大字符数（超过此大小会截断）
MAX_HIERARCHICAL_CHARS = 100000  # 10 万字


class HierarchicalSummarizer:
    """分层摘要器

    封装 Map-Reduce 和分层摘要逻辑，依赖 LLMClient 进行 API 调用。

    Attributes:
        llm_client: LLMClient 实例
    """

    def __init__(self, llm_client: "LLMClient") -> None:
        """初始化分层摘要器

        Args:
            llm_client: LLMClient 实例
        """
        self.llm_client = llm_client

    async def generate_map_reduce_summary(
        self,
        text: str,
        title: str,
        max_retries: int = 8,
        chunk_size: int = 4000,
        overlap: int = 200,
    ) -> dict[str, Any] | None:
        """Map-Reduce 摘要：分段并行摘要后合并

        适用于 1-3 万字的文档。

        Args:
            text: 待摘要的文本
            title: 文本标题
            max_retries: 最大重试次数
            chunk_size: 分块大小（字符数）
            overlap: 重叠字符数

        Returns:
            包含 one_line, key_points, detailed_summary, concepts 的字典
        """
        from dochris.core.text_chunker import semantic_chunk

        # Map 阶段：分段摘要
        chunks = semantic_chunk(text, chunk_size, overlap)
        logger.info(f"Map-Reduce: 分为 {len(chunks)} 块")

        chunk_summaries = await self._summarize_chunks_parallel(chunks, title, max_retries)

        if not chunk_summaries:
            logger.error("Map-Reduce: 所有分块摘要失败")
            return None

        # Reduce 阶段：合并摘要
        return await self._merge_summaries(chunk_summaries, title, max_retries)

    async def generate_hierarchical_summary(
        self,
        text: str,
        title: str,
        max_retries: int = 8,
        chunk_size: int = 4000,
        overlap: int = 200,
    ) -> dict[str, Any] | None:
        """分层摘要：三层结构处理超长文档

        适用于 3 万字以上的文档：
        - 第一层：段落摘要（可并行）
        - 第二层：按章节合并段落摘要
        - 第三层：全局摘要

        Args:
            text: 待摘要的文本
            title: 文本标题
            max_retries: 最大重试次数
            chunk_size: 分块大小（字符数）
            overlap: 重叠字符数

        Returns:
            包含 one_line, key_points, detailed_summary, concepts 的字典
        """
        from dochris.core.text_chunker import structure_aware_split

        # 检查文档大小，超过上限时截断
        original_length = len(text)
        if original_length > MAX_HIERARCHICAL_CHARS:
            half_limit = MAX_HIERARCHICAL_CHARS // 2
            text = text[:half_limit] + "\n\n[...中间内容已截断...]\n\n" + text[-half_limit:]
            logger.warning(
                f"文档过大 ({original_length:,} 字)，已截断到 {MAX_HIERARCHICAL_CHARS:,} 字 "
                f"(保留前 {half_limit:,} 和后 {half_limit:,} 字)"
            )

        # 第一层：结构感知分块
        chunks = structure_aware_split(text, chunk_size, overlap)

        # 限制最大块数，防止 API 调用爆炸
        MAX_CHUNKS = 50
        if len(chunks) > MAX_CHUNKS:
            # 均匀采样，保留首尾
            step = len(chunks) / MAX_CHUNKS
            sampled = []
            for i in range(MAX_CHUNKS):
                idx = int(i * step)
                if idx < len(chunks):
                    sampled.append(chunks[idx])
            # 确保包含最后一块
            if chunks[-1] not in sampled:
                sampled[-1] = chunks[-1]
            chunks = sampled
            logger.warning(f"分层摘要: 块数 {len(chunks)} 超过上限 {MAX_CHUNKS}，已均匀采样")

        logger.info(f"分层摘要: 分为 {len(chunks)} 块")

        # 第一层：段落摘要（可并行）
        chunk_summaries = await self._summarize_chunks_parallel(chunks, title, max_retries)

        if not chunk_summaries:
            logger.error("分层摘要: 所有分块摘要失败")
            return None

        # 按章节/标题分组
        sections = self._group_chunks_by_section(chunks, chunk_summaries)

        # 第二层：章节摘要
        if len(sections) > 1:
            section_summaries = await self._summarize_sections_parallel(
                sections, title, max_retries
            )
            if not section_summaries:
                logger.warning("分层摘要: 章节摘要失败，使用段落摘要直接合并")
                return await self._merge_summaries(chunk_summaries, title, max_retries)
        else:
            # 只有一个章节，直接使用段落摘要
            section_summaries = chunk_summaries

        # 第三层：全局摘要
        return await self._merge_summaries(section_summaries, title, max_retries)

    async def _summarize_chunks_parallel(
        self, chunks: list, title: str, max_retries: int
    ) -> list[dict[str, Any]]:
        """并行对多个文本块生成摘要

        Args:
            chunks: TextChunk 对象列表
            title: 文档标题
            max_retries: 最大重试次数

        Returns:
            摘要列表
        """

        async def summarize_one(chunk: "TextChunk", index: int) -> dict[str, Any] | None:
            """为单个块生成摘要"""
            chunk_title = chunk.title or f"{title} - 第 {index + 1} 部分"

            async def _do_llm_call() -> dict[str, Any]:
                """执行实际的 LLM API 调用"""
                await self.llm_client._rate_limit()

                messages = self._build_chunk_messages(chunk.content, chunk_title)

                response = await self.llm_client.client.chat.completions.create(
                    model=self.llm_client.model,
                    max_tokens=8000,
                    temperature=self.llm_client.temperature,
                    messages=self.llm_client._apply_no_think(messages),
                )

                content = response.choices[0].message.content.strip()

                # 解析 JSON
                try:
                    return cast(dict[str, Any], json.loads(content))
                except json.JSONDecodeError:
                    try:
                        import json_repair

                        return cast(dict[str, Any], json_repair.loads(content))
                    except ImportError:
                        result = self.llm_client._extract_json_from_text(content)
                        if result:
                            return cast(dict[str, Any], result)
                        raise

            # 使用统一的重试逻辑
            return await RetryManager.llm_retry_with_filter(
                _do_llm_call,
                max_retries=max_retries,
                on_content_filter=None,
            )

        # 使用信号量控制并发，避免同时发出过多请求触发 API 限流
        max_parallel = 3
        sem = asyncio.Semaphore(max_parallel)

        async def limited_summarize(chunk_idx: tuple[int, "TextChunk"]) -> dict[str, Any] | Exception:
            i, chunk = chunk_idx
            async with sem:
                result = await summarize_one(chunk, i)
                return result if result is not None else Exception(f"Chunk {i + 1}: returned None")

        results = await asyncio.gather(
            *[limited_summarize((i, c)) for i, c in enumerate(chunks)], return_exceptions=True
        )

        # 过滤掉 None 和异常
        valid_results: list[dict[str, Any]] = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error(f"Chunk {i + 1}: 异常 - {r}")
            elif r is not None:
                valid_results.append(cast(dict[str, Any], r))

        logger.info(f"段落摘要完成: {len(valid_results)}/{len(chunks)} 成功")
        return valid_results

    async def _merge_summaries(
        self, summaries: list[dict[str, Any]], title: str, max_retries: int
    ) -> dict[str, Any] | None:
        """合并多个摘要为一个全局摘要

        Args:
            summaries: 摘要列表
            title: 文档标题
            max_retries: 最大重试次数

        Returns:
            合并后的摘要
        """
        if not summaries:
            return None

        # 如果只有一个摘要，直接返回
        if len(summaries) == 1:
            return summaries[0]

        async def _do_llm_call() -> dict[str, Any]:
            """执行实际的 LLM API 调用"""
            await self.llm_client._rate_limit()

            # 构建合并 prompt
            merged_content = self._build_merge_prompt(summaries, title)

            # qwen3 模型的合并 prompt 已内嵌在 _build_merge_prompt_qwen3 中，
            # 这里只设置通用 system prompt 作为 fallback
            merge_system = """你是知识库编译器。请将多个文档片段的摘要合并为一个连贯的全局摘要。

【强制 JSON 格式要求】
必须输出合法的 JSON 对象，包含以下 4 个字段：
  - one_line: 一句话摘要（10-50 字）
  - key_points: 字符串数组，必须包含 5-8 个独立要点
  - detailed_summary: 详细摘要（800-1500 字）
  - concepts: 对象数组，必须包含 5-10 个概念

注意：
- 合并时要去除重复内容
- 保留所有重要概念
- detailed_summary 应该是连贯的叙述，而非简单拼接"""

            messages = [
                {
                    "role": "system",
                    "content": merge_system
                    if not self.llm_client.no_think
                    else "你是一位资深知识工程师，擅长知识合并和结构化整理。请严格按照用户要求的 JSON 格式输出。",
                },
                {"role": "user", "content": merged_content},
            ]

            response = await self.llm_client.client.chat.completions.create(
                model=self.llm_client.model,
                max_tokens=self.llm_client.max_tokens,
                temperature=self.llm_client.temperature,
                messages=self.llm_client._apply_no_think(messages),
            )

            content = response.choices[0].message.content.strip()

            # 解析 JSON
            try:
                result = cast(dict[str, Any], json.loads(content))
                logger.info("✓ 合并摘要成功")
                return result
            except json.JSONDecodeError:
                try:
                    import json_repair

                    result = cast(dict[str, Any], json_repair.loads(content))
                    logger.info("✓ 合并摘要成功（使用 json_repair）")
                    return result
                except ImportError:
                    extracted_result = self.llm_client._extract_json_from_text(content)
                    if extracted_result:
                        logger.info("✓ 合并摘要成功（简单提取）")
                        return extracted_result
                    raise

        # 使用统一的重试逻辑
        return await RetryManager.llm_retry_with_filter(
            _do_llm_call,
            max_retries=max_retries,
            on_content_filter=None,
        )

    def _build_chunk_messages(self, chunk_text: str, chunk_title: str) -> list[dict]:
        """为单个文本块构建消息"""
        if self.llm_client.no_think:
            return self._build_chunk_messages_qwen3(chunk_text, chunk_title)

        system_prompt = """你是知识库编译器。请为以下文档片段生成结构化摘要。

【强制 JSON 格式要求】
必须输出合法的 JSON 对象，包含以下 4 个字段：
  - one_line: 本片段一句话摘要（10-50 字）
  - key_points: 本片段要点数组（3-5 个）
  - detailed_summary: 本片段详细摘要（200-400 字）
  - concepts: 本片段概念数组（2-4 个）

请只输出 JSON，不要包含任何其他文字。"""

        user_prompt = f"""请为以下内容生成结构化摘要：

标题: {chunk_title}

内容:
{chunk_text}

请以 JSON 格式输出。"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _build_chunk_messages_qwen3(self, chunk_text: str, chunk_title: str) -> list[dict]:
        """qwen3 专用的分段摘要 prompt

        分段摘要的质量直接影响最终合并结果。每个片段的摘要需要：
        - 精确概括本片段的核心内容
        - 提取本片段独有的概念（不重复其他片段的）
        - 保持与全文主题的关联性
        """
        system_prompt = """你是一位资深知识工程师，正在对一篇长文档进行分段知识提取。

## 当前任务
这是文档的一个片段。请为这个片段生成结构化摘要。
注意：这是全文的一部分，你只需要关注本片段的内容。

## 输出格式（严格遵守）
只输出一个合法的 JSON 对象，不要任何额外文字，不要 markdown 代码块。

{
  "one_line": "本片段核心内容的一句话概括（15-50字）",
  "key_points": [
    "本片段最重要的3-5个独立信息点",
    "每个要点是15-40字的完整句子"
  ],
  "detailed_summary": "200-400字的详细摘要。要求：\\n- 聚焦本片段的核心论点和论证\\n- 保留关键数据、引用和结论\\n- 如果本片段是论证的一部分，说明它在全文中的逻辑位置",
  "concepts": [
    {"name": "本片段中的关键概念", "explanation": "50-80字的解释"},
    {"name": "概念2", "explanation": "..."}
  ]
}

## 质量要求
- 不要遗漏本片段中的重要信息，后续合并阶段依赖你的摘要
- concepts 只提取本片段中明确讨论的概念
- detailed_summary 宁可详细一些，合并阶段会去重"""

        user_prompt = f"""文档标题：{chunk_title}

文档片段内容：
{chunk_text}

请严格按照 JSON 格式输出本片段的结构化摘要。"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _build_merge_prompt(self, summaries: list[dict[str, Any]], title: str) -> str:
        """构建合并摘要的 prompt"""
        if self.llm_client.no_think:
            return self._build_merge_prompt_qwen3(summaries, title)

        summary_texts = []
        for i, s in enumerate(summaries, 1):
            summary_texts.append(f"""
## 片段 {i}
一句话摘要: {s.get("one_line", "")}
要点:
{chr(10).join(f"- {p}" for p in s.get("key_points", []))}

详细摘要:
{s.get("detailed_summary", "")}

概念:
{chr(10).join(f"- {c.get('name', c) if isinstance(c, dict) else c}" for c in s.get("concepts", []))}
""")

        return f"""请将以下 {len(summaries)} 个文档片段的摘要合并为一个连贯的全局摘要：

文档标题: {title}

{chr(10).join(summary_texts)}

请以 JSON 格式输出合并后的摘要，包含 one_line、key_points、detailed_summary、concepts 四个字段。"""

    def _build_merge_prompt_qwen3(self, summaries: list[dict[str, Any]], title: str) -> str:
        """qwen3 专用的合并摘要 prompt

        合并是整个分层编译最关键的一步，质量要求最高：
        - 需要理解各片段之间的逻辑关系
        - 去除重复信息
        - 重新组织为连贯的全文摘要
        - 概念去重和层级化
        """
        summary_texts = []
        for i, s in enumerate(summaries, 1):
            concepts_str = ""
            for c in s.get("concepts", []):
                if isinstance(c, dict):
                    concepts_str += f"  - {c.get('name', '?')}: {c.get('explanation', '')[:60]}\n"
                else:
                    concepts_str += f"  - {c}\n"
            summary_texts.append(f"""
### 片段 {i}
**核心**: {s.get("one_line", "")}
**要点**:
{chr(10).join(f"- {p}" for p in s.get("key_points", []))}
**详细摘要**: {s.get("detailed_summary", "")}
**概念**:\n{concepts_str}""")

        json_example = """{
  "one_line": "全文核心论点的一句话精准概括（15-50字）",
  "key_points": [
    "合并后的5-8个核心要点，按重要性排序",
    "每个要点是独立完整的信息点",
    "覆盖全文最重要的知识内容"
  ],
  "detailed_summary": "800-1500字的连贯全文摘要。要求：像一篇完整的分析文章，有开头、中间、结尾；按论证逻辑组织，而非按片段顺序；包含核心论点、支撑论据、关键结论；体现原文的知识深度和洞察",
  "concepts": [
    {"name": "去重后的核心概念", "explanation": "80-120字的详细解释，综合各片段中的相关内容"},
    {"name": "概念2", "explanation": "..."},
    {"name": "概念3", "explanation": "..."}
  ]
}"""

        merged_text = chr(10).join(summary_texts)

        return f"""你是一位资深知识工程师，现在需要将 {len(summaries)} 个文档片段的摘要合并为一篇完整的知识摘要。

## 合并目标
- 生成一份连贯、完整、有深度的全文知识摘要
- 体现原文的完整论证逻辑和知识结构
- 合并后的摘要质量应该高于任何单个片段

## 合并原则
1. **去重**: 多个片段提到的相同观点只保留最完整的版本
2. **逻辑重组**: 按照论证的逻辑顺序（而非片段顺序）组织内容
3. **概念去重**: 相同概念只保留一次，取最详细的解释
4. **信息保全**: 确保所有片段中的重要信息都被保留
5. **连贯性**: detailed_summary 应该像一篇完整的分析文章，而非片段拼接

## 输出格式（严格遵守）
只输出一个合法的 JSON 对象，不要任何额外文字，不要 markdown 代码块。

{json_example}

## 文档标题：{title}

## 各片段摘要：
{merged_text}

请严格按照上述 JSON 格式输出合并后的全文知识摘要。"""

    def _group_chunks_by_section(self, chunks: list, summaries: list[dict[str, Any]]) -> dict:
        """将块按章节/标题分组

        Args:
            chunks: TextChunk 对象列表
            summaries: 对应的摘要列表

        Returns:
            {section_title: [summary1, summary2, ...]}
        """
        sections = defaultdict(list)

        for chunk, summary in zip(chunks, summaries, strict=False):
            section_title = chunk.title if chunk.title else "未分类"
            sections[section_title].append(summary)

        return dict(sections)

    async def _summarize_sections_parallel(
        self, sections: dict, title: str, max_retries: int
    ) -> list[dict[str, Any]]:
        """并行对多个章节生成摘要

        Args:
            sections: {section_title: [summaries]}
            title: 文档标题
            max_retries: 最大重试次数

        Returns:
            章节摘要列表
        """

        async def summarize_section(
            section_title: str, summaries: list[dict[str, Any]]
        ) -> dict[str, Any] | None:
            """为单个章节生成摘要"""
            if len(summaries) == 1:
                return summaries[0]

            # 合并该章节的所有摘要
            return await self._merge_summaries(summaries, f"{title} - {section_title}", max_retries)

        # 使用信号量控制并发，避免同时发出过多请求触发 API 限流
        sem = asyncio.Semaphore(3)

        async def limited_summarize_section(item: tuple[str, list[dict[str, Any]]]) -> dict[str, Any] | Exception:
            st, sums = item
            async with sem:
                result = await summarize_section(st, sums)
                return result if result is not None else Exception(f"Section {st}: returned None")

        results = await asyncio.gather(
            *[limited_summarize_section((st, sums)) for st, sums in sections.items()], return_exceptions=True
        )

        # 过滤掉 None 和异常
        valid_results: list[dict[str, Any]] = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error(f"Section {i + 1}: 异常 - {r}")
            elif r is not None:
                valid_results.append(cast(dict[str, Any], r))

        logger.info(f"章节摘要完成: {len(valid_results)}/{len(sections)} 成功")
        return valid_results
