#!/usr/bin/env python3
"""
LLM 客户端模块

提供与 LLM API 交互的异步客户端，支持：
- 结构化摘要生成
- 自动重试机制（429、连接错误、超时）
- 速率限制
- JSON 响应解析（支持 json_repair）
- 内容过滤检测

主要类:
    LLMClient: 异步 LLM 客户端

使用示例:
    client = LLMClient(api_key="xxx", base_url="https://api.example.com")
    result = await client.generate_summary(text, title)
"""

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dochris.core.text_chunker import TextChunk

try:
    from openai import AsyncOpenAI
except ImportError:
    logging.warning("openai not installed. Please install: pip install openai")
    AsyncOpenAI = None

logger = logging.getLogger(__name__)

# 最大重试等待时间（秒）
MAX_RETRY_WAIT = 60

# 分层摘要最大字符数（超过此大小会截断）
MAX_HIERARCHICAL_CHARS = 100000  # 10 万字


class LLMClient:
    """异步 LLM 客户端

    提供结构化摘要生成功能，支持自动重试和速率限制。

    Attributes:
        client: AsyncOpenAI 客户端实例
        model: 模型名称
        max_tokens: 最大 token 数
        temperature: 温度参数（0.1 保证稳定输出）
        request_delay: 请求间隔（秒）
        last_request_time: 上次请求时间
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "zai/glm-4.7",
        max_tokens: int = 40000,
        temperature: float = 0.1,
        request_delay: float = 5.0,
    ) -> None:
        """初始化 LLM 客户端

        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            model: 模型名称（默认 zai/glm-4.7）
            max_tokens: 最大生成 token 数（默认 40000）
            temperature: 采样温度（默认 0.1，较低温度保证稳定输出）
            request_delay: 请求间隔秒数（默认 5.0，用于速率限制）

        Raises:
            ImportError: openai 包未安装时抛出
        """
        if AsyncOpenAI is None:
            raise ImportError("openai package not installed")

        import httpx

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=120.0,  # 2分钟超时
            http_client=httpx.AsyncClient(
                limits=httpx.Limits(max_connections=1),
                timeout=120.0,
            ),
            max_retries=0,  # 禁用 openai 库内置重试，由 LLMClient 自行处理
        )
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.request_delay = request_delay
        self.no_think = model and "qwen3" in model.lower()
        self.last_request_time = 0.0

    def _apply_no_think(self, messages: list) -> list:
        """qwen3 模型需要在 system prompt 末尾加 /no_think"""
        if self.no_think and messages and messages[0].get("role") == "system":
            messages = [m.copy() for m in messages]
            messages[0]["content"] += " /no_think"
        return messages

    async def _rate_limit(self) -> None:
        """速率限制：确保两次请求之间有足够间隔

        如果距离上次请求时间不足 request_delay，则等待剩余时间。
        """
        import time

        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.request_delay:
            wait_time = self.request_delay - time_since_last
            await asyncio.sleep(wait_time)

        self.last_request_time = time.time()

    async def generate_summary(
        self, text: str, title: str, max_retries: int = 8
    ) -> dict[str, Any] | None:
        """生成结构化摘要（带自动重试）

        Args:
            text: 待摘要的文本内容
            title: 文本标题
            max_retries: 最大重试次数（默认 3）

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
            - 429 错误: 指数退避（20s, 40s, 80s）
            - 连接/超时错误: 指数退避（15s, 30s, 60s）
            - 内容过滤: 不重试，直接返回 None
            - 其他错误: 指数退避（10s, 20s, 40s）
        """
        # 速率限制：确保两次请求之间有足够间隔
        await self._rate_limit()

        for attempt in range(max_retries):
            try:
                messages = self._build_messages(text, title)

                # qwen3 模型需要 /no_think 禁用思考过程
                messages = self._apply_no_think(messages)

                response = await self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    messages=self._apply_no_think(messages),
                )

                content = response.choices[0].message.content.strip()

                # 解析 JSON
                try:
                    result = json.loads(content)
                except json.JSONDecodeError:
                    # 尝试使用 json_repair
                    try:
                        import json_repair

                        result = json_repair.loads(content)
                    except ImportError:
                        logger.warning("json_repair not installed, trying simple extraction")
                        # 简单尝试提取 JSON
                        result = self._extract_json_from_text(content)

                logger.info(f"✓ LLM call succeeded on attempt {attempt + 1}")
                return result

            except Exception as e:
                error_str = str(e)

                # 429/限流错误：指数退避重试
                if "429" in error_str or "rate" in error_str.lower():
                    wait = min(30 * (2**attempt), MAX_RETRY_WAIT)  # 指数退避，最多 5 分钟
                    logger.warning(
                        f"429/rate limit error (attempt {attempt + 1}), waiting {wait}s..."
                    )
                    await asyncio.sleep(wait)

                # 连接错误/超时：延迟重试
                elif (
                    "connection" in error_str.lower()
                    or "timeout" in error_str.lower()
                    or "timed out" in error_str.lower()
                ):
                    wait = min(20 * (2**attempt), MAX_RETRY_WAIT)  # 指数退避，最多 5 分钟
                    logger.warning(
                        f"Connection/timeout error (attempt {attempt + 1}), waiting {wait}s..."
                    )
                    await asyncio.sleep(wait)

                # 内容过滤：不重试
                elif "contentFilter" in error_str.lower() or "content filter" in error_str.lower():
                    logger.warning(f"Content filter triggered: {e}")
                    return None

                # 其他错误：重试
                elif attempt < max_retries - 1:
                    wait = min(10 * (2**attempt), MAX_RETRY_WAIT)  # 增加延迟，最多 5 分钟
                    logger.warning(f"LLM call failed (attempt {attempt + 1}): {e}")
                    logger.info(f"Waiting {wait}s before retry...")
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"LLM call failed after {max_retries} attempts: {e}")
                    return None

        return None

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
        if self.no_think:
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
  "detailed_summary": "1000-2000字的详细摘要。要求：\n- 字数不少于1000字，充分展开论述\n- 按逻辑顺序组织，每个论点都要有充分的分析和解释\n- 包含核心论点、支撑证据、关键结论\n- 保留原文的论证逻辑和因果关系\n- 使用"方法""策略""技巧""原理""规律""核心""本质""提升""学习""掌握""改善""优化"等学习导向的措辞\n- 用自己的话重新表述，不要照搬原文句子\n- 结尾总结核心学习收获和实践启示",
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

    def _extract_json_from_text(self, text: str) -> dict[str, Any] | None:
        """从文本中提取 JSON（栈匹配方法）

        当标准 JSON 解析失败时的备用方案。使用栈来正确匹配嵌套的
        大括号，提取第一个完整的 JSON 对象。

        Args:
            text: 包含 JSON 的文本

        Returns:
            解析后的字典，失败返回 None

        Examples:
            >>> _extract_json_from_text('前缀 {"a": 1} 后缀')
            {"a": 1}
            >>> _extract_json_from_text('前缀 {"a": {"b": 2}} 后缀')
            {"a": {"b": 2}}
        """
        # 使用栈匹配嵌套的大括号
        stack: list[int] = []  # 存储左括号的位置
        in_string = False
        escape_next = False
        quote_char = None

        for i, char in enumerate(text):
            if escape_next:
                escape_next = False
                continue

            if char == "\\":
                escape_next = True
                continue

            # 处理字符串中的引号
            if char in ('"', "'") and not in_string:
                in_string = True
                quote_char = char
                continue
            elif char == quote_char and in_string:
                in_string = False
                quote_char = None
                continue

            # 只在非字符串内容中处理大括号
            if not in_string:
                if char == "{":
                    stack.append(i)
                elif char == "}" and stack:
                    # 找到匹配的左括号（栈顶是最内层的 {）
                    start = stack.pop()
                    if not stack:
                            # 栈为空，找到完整的 JSON 对象
                            json_str = text[start : i + 1]
                            try:
                                return json.loads(json_str)
                            except json.JSONDecodeError:
                                # 继续尝试下一个可能的 JSON 对象
                                continue

        # 如果使用栈方法失败，回退到简单方法
        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1 or end <= start:
            return None

        json_str = text[start : end + 1]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None

    # ============================================================
    # 分层摘要方法
    # ============================================================

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
            return await self.generate_map_reduce_summary(
                text, title, max_retries, chunk_size=chunk_size
            )
        else:  # hierarchical
            return await self.generate_hierarchical_summary(text, title, max_retries)

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
            logger.warning(
                f"分层摘要: 块数 {len(chunks)} 超过上限 {MAX_CHUNKS}，已均匀采样"
            )

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
        import asyncio
        import logging

        logger = logging.getLogger(__name__)

        async def summarize_one(chunk: "TextChunk", index: int) -> dict[str, Any] | None:
            """为单个块生成摘要"""
            chunk_title = chunk.title or f"{title} - 第 {index + 1} 部分"

            # 使用简化的 prompt
            messages = self._build_chunk_messages(chunk.content, chunk_title)

            for attempt in range(max_retries):
                try:
                    await self._rate_limit()

                    response = await self.client.chat.completions.create(
                        model=self.model,
                        max_tokens=8000,
                        temperature=self.temperature,
                        messages=self._apply_no_think(messages),
                    )

                    content = response.choices[0].message.content.strip()

                    # 解析 JSON
                    try:
                        result = json.loads(content)
                        return result
                    except json.JSONDecodeError:
                        try:
                            import json_repair

                            result = json_repair.loads(content)
                            return result
                        except ImportError:
                            result = self._extract_json_from_text(content)
                            if result:
                                return result

                except Exception as e:
                    error_str = str(e)

                    # 429/限流错误
                    if "429" in error_str or "rate" in error_str.lower():
                        wait = 30 * (2**attempt)
                        logger.warning(f"Chunk {index + 1}: 429 错误，等待 {wait}s")
                        await asyncio.sleep(wait)
                    # 连接错误/超时
                    elif "connection" in error_str.lower() or "timeout" in error_str.lower():
                        wait = 20 * (2**attempt)
                        logger.warning(f"Chunk {index + 1}: 连接错误，等待 {wait}s")
                        await asyncio.sleep(wait)
                    # 内容过滤
                    elif "contentFilter" in error_str.lower():
                        logger.warning(f"Chunk {index + 1}: 内容过滤")
                        return None
                    # 其他错误
                    elif attempt < max_retries - 1:
                        wait = 10 * (2**attempt)
                        logger.warning(f"Chunk {index + 1}: 失败，等待 {wait}s 后重试")
                        await asyncio.sleep(wait)
                    else:
                        logger.error(f"Chunk {index + 1}: 失败 {max_retries} 次")
                        return None

            return None

        # 并行处理所有块
        results = await asyncio.gather(
            *[summarize_one(chunk, i) for i, chunk in enumerate(chunks)], return_exceptions=True
        )

        # 过滤掉 None 和异常
        valid_results = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error(f"Chunk {i + 1}: 异常 - {r}")
            elif r is not None:
                valid_results.append(r)

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
                if not self.no_think
                else "你是一位资深知识工程师，擅长知识合并和结构化整理。请严格按照用户要求的 JSON 格式输出。",
            },
            {"role": "user", "content": merged_content},
        ]

        for attempt in range(max_retries):
            try:
                await self._rate_limit()

                response = await self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    messages=self._apply_no_think(messages),
                )

                content = response.choices[0].message.content.strip()

                # 解析 JSON
                try:
                    result = json.loads(content)
                    logger.info("✓ 合并摘要成功")
                    return result
                except json.JSONDecodeError:
                    try:
                        import json_repair

                        result = json_repair.loads(content)
                        logger.info("✓ 合并摘要成功（使用 json_repair）")
                        return result
                    except ImportError:
                        result = self._extract_json_from_text(content)
                        if result:
                            logger.info("✓ 合并摘要成功（简单提取）")
                            return result

            except Exception as e:
                error_str = str(e)

                if "429" in error_str or "rate" in error_str.lower():
                    wait = 30 * (2**attempt)
                    logger.warning(f"合并摘要 429 错误，等待 {wait}s")
                    await asyncio.sleep(wait)
                elif attempt < max_retries - 1:
                    wait = 10 * (2**attempt)
                    logger.warning(f"合并摘要失败，等待 {wait}s 后重试")
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"合并摘要失败 {max_retries} 次: {e}")
                    return None

        return None

    def _build_chunk_messages(self, chunk_text: str, chunk_title: str) -> list[dict]:
        """为单个文本块构建消息"""
        if self.no_think:
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
  "detailed_summary": "200-400字的详细摘要。要求：\n- 聚焦本片段的核心论点和论证\n- 保留关键数据、引用和结论\n- 如果本片段是论证的一部分，说明它在全文中的逻辑位置",
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
        if self.no_think:
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
        from collections import defaultdict

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
        import asyncio
        import logging

        logger = logging.getLogger(__name__)

        async def summarize_section(section_title: str, summaries: list) -> dict[str, Any] | None:
            """为单个章节生成摘要"""
            if len(summaries) == 1:
                return summaries[0]

            # 合并该章节的所有摘要
            return await self._merge_summaries(summaries, f"{title} - {section_title}", max_retries)

        # 并行处理所有章节
        results = await asyncio.gather(
            *[summarize_section(st, sums) for st, sums in sections.items()], return_exceptions=True
        )

        # 过滤掉 None 和异常
        valid_results = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                logger.error(f"Section {i + 1}: 异常 - {r}")
            elif r is not None:
                valid_results.append(r)

        logger.info(f"章节摘要完成: {len(valid_results)}/{len(sections)} 成功")
        return valid_results
