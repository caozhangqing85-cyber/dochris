#!/usr/bin/env python3
"""
摘要生成器模块

提供基础摘要生成功能，从 LLMClient 拆分出来。
"""

import json
import logging
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from .llm_client import LLMClient

from .retry_manager import RetryManager

logger = logging.getLogger(__name__)


class SummaryGenerator:
    """摘要生成器

    封装基础摘要生成逻辑，依赖 LLMClient 进行 API 调用。

    Attributes:
        llm_client: LLMClient 实例
    """

    def __init__(self, llm_client: "LLMClient") -> None:
        """初始化摘要生成器

        Args:
            llm_client: LLMClient 实例
        """
        self.llm_client = llm_client

    async def generate_summary(
        self, text: str, title: str, max_retries: int = 8
    ) -> dict[str, Any] | None:
        """生成结构化摘要（带自动重试）

        Args:
            text: 待摘要的文本内容
            title: 文本标题
            max_retries: 最大重试次数（默认 8）

        Returns:
            包含以下字段的字典:
                - one_line: 一句话摘要
                - key_points: 要点列表
                - detailed_summary: 详细摘要
                - concepts: 概念列表
            失败时返回 None

        Raises:
            不抛出异常，失败返回 None

        重试策略:
            - 429 错误: 指数退避（30s, 60s, 120s...）
            - 连接/超时错误: 指数退避（20s, 40s, 80s...）
            - 内容过滤: 不重试，直接返回 None
            - 其他错误: 指数退避（10s, 20s, 40s...）
        """

        async def _do_llm_call() -> dict[str, Any]:
            """执行实际的 LLM API 调用"""
            # 速率限制：确保两次请求之间有足够间隔
            await self.llm_client._rate_limit()

            messages = self._build_messages(text, title)
            # qwen3 模型需要 /no_think 禁用思考过程
            messages = self.llm_client._apply_no_think(messages)

            response = await self.llm_client.client.chat.completions.create(
                model=self.llm_client.model,
                max_tokens=self.llm_client.max_tokens,
                temperature=self.llm_client.temperature,
                messages=messages,
            )

            content = response.choices[0].message.content.strip()

            # 解析 JSON
            try:
                return cast(dict[str, Any], json.loads(content))
            except json.JSONDecodeError:
                # 尝试使用 json_repair
                try:
                    import json_repair

                    repaired = json_repair.loads(content)
                    if isinstance(repaired, dict):
                        return cast(dict[str, Any], repaired)
                    logger.warning("json_repair returned non-dict: %s", type(repaired).__name__)
                    raise ValueError("json_repair returned non-dict value") from None
                except ImportError:
                    logger.warning("json_repair not installed, trying simple extraction")
                    result = self.llm_client._extract_json_from_text(content)
                    if result is None:
                        raise ValueError("Failed to extract JSON from LLM response") from None
                    return result

        # 使用统一的重试逻辑
        result = await RetryManager.llm_retry_with_filter(
            _do_llm_call, max_retries=max_retries, on_content_filter=None
        )

        if result is not None:
            logger.info("✓ LLM call succeeded")
        return result

    def _build_messages(self, text: str, title: str) -> list[dict]:
        """构建 LLM 消息

        根据模型类型自动选择 prompt 模板：
        - qwen3 模型使用专用高质量模板（含思考引导和更详细的格式约束）
        - 其他模型使用通用模板

        Args:
            text: 待摘要的文本内容
            title: 文本标题

        Returns:
            包含 system 和 user 消息的列表
        """
        if self.llm_client.no_think:
            return self._build_messages_qwen3(text, title)

        system_prompt = """你是知识库编译器。整理文本并生成结构化 JSON。

【核心任务】
提取文本中的**关键知识点**和**学习价值**，生成高质量的知识摘要。

【强制 JSON 格式要求】
1. 必须输出合法的 JSON 对象，前后不要任何文字或代码块标记
2. JSON 对象必须包含以下 4 个字段：
   - one_line: 一句话摘要（10-50 字）
   - key_points: 字符串数组，必须包含 4-5 个独立要点
   - detailed_summary: 详细摘要（800-1500 字）
   - concepts: 对象数组，必须包含 3-5 个概念

3. key_points 数组中的每个要点必须是：
   - 15-30 字的完整句子
   - 独立的信息点
"""

        user_prompt = f"""请为以下内容生成结构化摘要：

标题: {title}

内容:
{text}

请以 JSON 格式输出，不要包含任何其他文字。"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _build_messages_qwen3(self, text: str, title: str) -> list[dict]:
        """为 qwen3 模型构建专用消息

        qwen3 的特点：
        - 14B 参数，中文能力强，逻辑推理优秀
        - 默认启用思维链，需要 /no_think 禁用
        - 需要更明确的 JSON 格式约束
        - 适合深度分析，不受内容过滤限制
        """
        system_prompt = """你是一位资深知识工程师，擅长从复杂文本中提取结构化知识。

## 你的工作流程
1. 通读全文，理解核心论点和知识结构
2. 识别关键概念及其相互关系
3. 提取有学习价值的观点和论证
4. 用清晰的结构化 JSON 输出结果

## 输出格式（严格遵守）
你必须且只能输出一个合法的 JSON 对象。不要输出任何 JSON 之外的文字。
不要使用 markdown 代码块包裹（不要 ```json ```）。
不要在 JSON 前后添加任何说明文字。

JSON 结构如下：
{
  "one_line": "用一句话精准概括全文核心内容（20-50字）",
  "key_points": [
    "要点1：独立完整的句子，20-40字",
    "要点2：另一个独立的信息点",
    "要点3",
    "要点4",
    "要点5"
  ],
  "detailed_summary": "1000-2000字的详细摘要。要求：\\n- 字数不少于1000字，充分展开论述\\n- 按逻辑顺序组织，每个论点都要有充分的分析和解释\\n- 包含核心论点、支撑证据、关键结论\\n- 保留原文的论证逻辑和因果关系\\n- 使用"方法""策略""技巧""原理""规律""核心""本质""提升""学习""掌握""改善""优化"等学习导向的措辞\\n- 用自己的话重新表述，不要照搬原文句子\\n- 结尾总结核心学习收获和实践启示",
  "concepts": [
    {"name": "概念名称", "explanation": "50-100字的详细解释，包含定义、作用和上下文关系"},
    {"name": "概念2", "explanation": "..."},
    {"name": "概念3", "explanation": "..."},
    {"name": "概念4", "explanation": "..."},
    {"name": "概念5", "explanation": "..."}
  ]
}

## 质量标准（严格）
- one_line：20-50字，信息密度高，不能是泛泛而谈
- key_points：至少5个独立要点，每个20-40字
- detailed_summary：不少于1000字，这是硬性要求。要充分展开分析，不要惜字如金
- concepts：至少3个概念，每个explanation要详细实用
- 禁止使用"作为AI""作为语言模型"等套话，直接以知识工程师身份输出"""

        user_prompt = f"""请为以下文档生成高质量的结构化知识摘要。

文档标题：{title}

文档内容：
{text}

请严格按照上述 JSON 格式输出。记住：只输出 JSON 对象本身，不要任何额外文字。"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    async def generate_summary_smart(
        self, text: str, title: str, direct_limit: int = 10000, max_retries: int = 8
    ) -> dict[str, Any] | None:
        """智能摘要：根据文本长度自动选择策略

        策略选择：
        - < direct_limit 字：直接全文摘要
        - direct_limit ~ direct_limit*3 字：Map-Reduce
        - > direct_limit*3 字：分层摘要

        Args:
            text: 待摘要的文本
            title: 文本标题
            direct_limit: 直接摘要的字符数上限（默认 1 万字）
            max_retries: 最大重试次数

        Returns:
            包含 one_line, key_points, detailed_summary, concepts 的字典
        """
        from dochris.core.text_chunker import should_use_hierarchical

        strategy = should_use_hierarchical(text, direct_limit)
        char_count = len(text)

        logger.info(f"文本长度: {char_count} 字，策略: {strategy}")

        if strategy == "direct":
            return await self.generate_summary(text, title, max_retries)
        elif strategy == "map_reduce":
            # 超大文档（>10万字）使用更大的块以减少 API 调用
            chunk_size = min(16000, max(4000, char_count // 20))
            from dochris.core.hierarchical_summarizer import HierarchicalSummarizer

            summarizer = HierarchicalSummarizer(self.llm_client)
            return await summarizer.generate_map_reduce_summary(
                text, title, max_retries, chunk_size=chunk_size
            )
        else:  # hierarchical
            from dochris.core.hierarchical_summarizer import HierarchicalSummarizer

            summarizer = HierarchicalSummarizer(self.llm_client)
            return await summarizer.generate_hierarchical_summary(text, title, max_retries)
