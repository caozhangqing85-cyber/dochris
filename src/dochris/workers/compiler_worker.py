#!/usr/bin/env python3
"""
编译 Worker (协调各个模块)
支持：
- 多种文件格式（PDF、Office、代码、文本、音视频转录）
- 智谱优先 + 本地 Ollama 兜底的双通道策略
- 插件系统扩展
"""

import logging
import sys
from pathlib import Path
from typing import Any

# 导入核心模块
scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

# 导入插件系统
# 导入 manifest 管理
from dochris.core.cache import cache_dir, file_hash, load_cached, save_cached
from dochris.core.llm_client import LLMClient
from dochris.core.quality_scorer import get_quality_threshold, score_summary_quality_v4
from dochris.exceptions import CompilationError
from dochris.manifest import get_default_workspace, get_manifest, update_manifest_status

# 导入解析器
from dochris.parsers.code_parser import detect_code_file, extract_from_code
from dochris.parsers.doc_parser import detect_document_file, parse_document
from dochris.parsers.pdf_parser import parse_pdf
from dochris.plugin import get_plugin_manager
from dochris.settings import get_settings

logger = logging.getLogger(__name__)

# ============================================================
# 默认配置：LLM API（主） + 本地 LLM（备）
# ============================================================


from dochris.settings import DEFAULT_LLM_API_BASE as DEFAULT_LLM_BASE_URL

DEFAULT_LLM_MODEL = "glm-5.1"


class CompilerWorker:
    """编译 Worker（双通道：智谱优先 + 本地兜底）"""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = DEFAULT_LLM_BASE_URL,
        model: str = DEFAULT_LLM_MODEL,
        # 本地兜底配置（从 settings 读取默认值）
        fallback_base_url: str = "",
        fallback_model: str = "",
        fallback_api_key: str = "",
        # 其他参数
        enable_fallback: bool = True,
    ) -> None:
        # 从 settings 获取本地 LLM 默认配置
        settings = get_settings()

        # 类型注解：LLM client 可能为 None
        self.llm: LLMClient | None = None
        self.fallback_llm: LLMClient | None = None

        # 本地 LLM 配置（如果未提供则使用 settings 中的默认值）
        if not fallback_base_url and settings.local_llm_base_url:
            fallback_base_url = settings.local_llm_base_url
        if not fallback_model:
            fallback_model = settings.local_llm_model
        if not fallback_api_key:
            fallback_api_key = settings.local_llm_api_key

        # 从环境变量补充 API key
        import os

        if not api_key:
            api_key = os.environ.get("OPENAI_API_KEY", "")

        # 主通道 LLM（智谱）
        if api_key and base_url:
            self.llm = LLMClient(api_key, base_url, model)
            logger.info(f"主通道: {model} @ {base_url}")
        else:
            self.llm = None
            logger.warning("主通道未配置 API key，将仅使用本地兜底")

        # 兜底通道 LLM（本地 Ollama）
        if enable_fallback:
            self.fallback_llm = LLMClient(fallback_api_key, fallback_base_url, fallback_model)
            logger.info(f"兜底通道: {fallback_model} @ {fallback_base_url}")
        else:
            self.fallback_llm = None

        self.enable_fallback = enable_fallback
        self.workspace = get_default_workspace()
        self.cache_dir = cache_dir(self.workspace)

        # 插件管理器
        self.plugin_manager = get_plugin_manager()
        self._init_plugins_from_settings(settings)

    def _init_plugins_from_settings(self, settings: Any) -> None:
        """从 settings 初始化插件

        Args:
            settings: Settings 实例
        """
        plugin_dirs = getattr(settings, "plugin_dirs", [])
        for plugin_dir in plugin_dirs:
            plugin_path = Path(plugin_dir).expanduser()
            if plugin_path.exists():
                loaded = self.plugin_manager.load_from_directory(plugin_path)
                logger.info(f"从 {plugin_dir} 加载了 {len(loaded)} 个插件")

        # 应用启用/禁用配置
        enabled = getattr(settings, "plugins_enabled", [])
        for name in enabled:
            self.plugin_manager.enable_plugin(name)

        disabled = getattr(settings, "plugins_disabled", [])
        for name in disabled:
            self.plugin_manager.disable_plugin(name)

    async def _generate_with_fallback(
        self,
        text: str,
        title: str,
    ) -> dict[str, Any] | None:
        """
        智谱优先编译，失败自动切本地 Ollama

        Returns:
            编译结果字典，或 None
        """
        # 1. 尝试主通道（智谱）
        if self.llm:
            result = await self.llm.generate_summary_smart(text, title)
            if result:
                logger.info(f"主通道编译成功: {title[:30]}")
                return result
            logger.warning(f"主通道失败，准备切换兜底: {title[:30]}")

        # 2. 尝试兜底通道（本地 Ollama）
        if self.fallback_llm:
            logger.info(f"使用兜底通道编译: {title[:30]}")
            result = await self.fallback_llm.generate_summary_smart(text, title)
            if result:
                logger.info(f"兜底通道编译成功: {title[:30]}")
                return result
            logger.error(f"兜底通道也失败: {title[:30]}")
            return None

        # 3. 没有可用的 LLM
        logger.error(f"无可用 LLM 通道: {title[:30]}")
        return None

    async def compile_document(self, src_id: str) -> dict[str, Any] | None:
        """
        编译单个文档

        Returns:
            编译结果，或 None
        """
        # 1. 读取 manifest
        manifest = get_manifest(self.workspace, src_id)
        if not manifest:
            logger.error(f"Manifest not found: {src_id}")
            return None

        file_path = self.workspace / manifest["file_path"]

        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        # 2. 检查缓存
        fh = file_hash(file_path)
        if fh:
            cached = load_cached(self.cache_dir, fh)
            if cached:
                logger.info(f"✓ Cache hit: {src_id}")
                await self._save_result(src_id, cached)
                return cached

        # 3. 根据文件类型选择处理方式
        try:
            text = await self._extract_text(file_path, manifest["title"], src_id)

            if text is None:
                return None

            # 3.5 编译前处理（插件 hook）
            metadata = manifest.copy()
            pre_result = self.plugin_manager.call_hook_firstresult(
                "pre_compile", text, metadata
            )
            if pre_result:
                text, metadata = pre_result
                logger.debug(f"应用 pre_compile hook: {src_id}")

            # 4. LLM 编译（带兜底）
            compile_result = await self._generate_with_fallback(text, manifest["title"])

            if not compile_result:
                logger.warning(f"⚠ LLM returned None for {src_id} ({file_path.name})")
                await self._mark_failed(src_id, "LLM compilation failed")
                return None

            # 5. 质量评分（支持插件自定义）
            plugin_score = self.plugin_manager.call_hook_firstresult(
                "quality_score",
                compile_result.get("detailed_summary", ""),
                manifest,
            )
            if plugin_score is not None:
                quality_score = int(plugin_score)
                logger.debug(f"使用插件质量评分: {quality_score}")
            else:
                quality_score = score_summary_quality_v4(compile_result)
            compile_result["quality_score"] = quality_score

            # 6. 保存到缓存
            if fh:
                save_success = save_cached(self.cache_dir, fh, compile_result)
                if not save_success:
                    logger.warning(f"Failed to save cache for {src_id}")

            # 7. 保存结果
            await self._save_result(src_id, compile_result, quality_score)

            # 7.5 编译后处理（插件 hook）
            self.plugin_manager.call_hook(
                "post_compile",
                src_id,
                {"status": "compiled", "result": compile_result, **manifest},
            )

            logger.info(f"✓ Compiled {src_id} (quality: {quality_score})")
            return compile_result

        except (CompilationError, OSError, ValueError, RuntimeError) as e:
            logger.error(f"Compilation failed for {src_id}: {e}", exc_info=True)
            await self._mark_failed(src_id, str(e))
            return None
        except Exception as e:
            # 顶层兜底：捕获未预期的错误
            logger.error(f"Compilation 未预期错误 for {src_id}: {e}", exc_info=True)
            await self._mark_failed(src_id, str(e))
            return None

    async def _extract_text(
        self,
        file_path: Path,
        title: str,
        src_id: str,
    ) -> str | None:
        """
        根据文件类型提取文本

        Returns:
            提取的文本，失败返回 None
        """
        # 首先尝试插件解析器
        plugin_text = self.plugin_manager.call_hook_firstresult(
            "ingest_parser", str(file_path)
        )
        if plugin_text:
            logger.info(f"使用插件解析器提取文本: {file_path.name}")
            return plugin_text

        ext = file_path.suffix.lower()

        # 音视频文件 → 查找对应转录 txt
        audio_exts = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".wma", ".opus"}
        video_exts = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"}
        if ext in audio_exts or ext in video_exts:
            txt_path = file_path.with_suffix(".txt")
            if txt_path.exists():
                text = txt_path.read_text(encoding="utf-8", errors="replace")
                if len(text) > 100:
                    logger.info(f"✓ 使用转录txt编译: {file_path.name}")
                    return text
                else:
                    await self._mark_failed(src_id, "转录txt内容过短")
                    return None
            else:
                await self._mark_failed(src_id, "未找到转录txt文件")
                return None

        # 代码文件
        if detect_code_file(file_path):
            code_result = extract_from_code(file_path)
            if code_result:
                text_parts = [
                    f"Language: {code_result.get('language', 'unknown')}",
                    f"Functions: {', '.join(code_result.get('functions', []))}",
                    f"Classes: {', '.join(code_result.get('classes', []))}",
                    f"\nExtracted Code:\n{code_result.get('text', '')}",
                ]
                return "\n".join(text_parts)
            return None

        # PDF 文件
        if ext == ".pdf":
            text = parse_pdf(file_path)
            if text:
                return text
            logger.warning(f"⚠ PDF 解析失败或返回空: {file_path.name}")
            await self._mark_failed(src_id, "PDF 解析失败")
            return None

        # 文档文件（.md/.txt/.docx/.pptx/.xlsx 等）
        if detect_document_file(file_path):
            doc_text = parse_document(file_path)
            if doc_text and len(doc_text) > 100:
                return doc_text
            elif doc_text:
                await self._mark_failed(src_id, f"文档内容过短 ({len(doc_text)}字)")
                return None
            return None

        # 其他文件：尝试纯文本读取
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            if len(text) > 100:
                return text
            return None
        except (OSError, UnicodeDecodeError, ValueError) as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return None

    async def _save_result(
        self, src_id: str, result: dict[str, Any], quality_score: int = 0
    ) -> None:
        """保存编译结果"""
        # 保存摘要 (保持现有格式)
        summaries_path = self.workspace / "outputs/summaries"
        summaries_path.mkdir(parents=True, exist_ok=True)

        summary_file = summaries_path / f"{src_id}.md"
        summary_file.write_text(
            f"# {result.get('one_line', '')}\n\n"
            f"## Key Points\n\n"
            f"{chr(10).join(f'- {p}' for p in result.get('key_points', []))}\n\n"
            f"## Detailed Summary\n\n"
            f"{result.get('detailed_summary', '')}\n\n"
            f"## Concepts\n\n"
            f"{chr(10).join(f'- {c}' for c in result.get('concepts', []))}\n",
            encoding="utf-8",
        )

        # 保存概念 (保持现有格式)
        if quality_score >= get_quality_threshold():
            concepts_path = self.workspace / "outputs/concepts" / src_id
            concepts_path.mkdir(parents=True, exist_ok=True)

            for idx, concept in enumerate(result.get("concepts", []), 1):
                # 处理概念（支持字符串和字典格式）
                if isinstance(concept, dict):
                    concept_name = str(concept.get("name", ""))
                    concept_desc = str(concept.get("description", ""))
                else:
                    concept_name = str(concept) if concept else ""
                    concept_desc = ""

                # 过滤空概念
                if not concept_name or not concept_name.strip():
                    continue

                # 清理概念名中的路径分隔符，防止生成嵌套目录
                safe_name = concept_name.strip().replace("/", "_").replace("\\", "_")
                concept_file = concepts_path / f"{idx:02d}_{safe_name}.md"
                concept_content = f"# {concept_name}\n\n{concept_desc}\n"
                concept_file.parent.mkdir(parents=True, exist_ok=True)
                concept_file.write_text(concept_content, encoding="utf-8")

        # 更新 manifest
        update_manifest_status(
            self.workspace,
            src_id,
            "compiled",
            quality_score=quality_score,
            summary=result,
            promoted_to=None,
        )

    async def _mark_failed(self, src_id: str, error_message: str) -> None:
        """标记编译失败"""
        update_manifest_status(self.workspace, src_id, "failed", error_message=error_message)
