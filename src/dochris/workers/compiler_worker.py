#!/usr/bin/env python3
"""
编译 Worker (协调各个模块)
支持：
- 多种文件格式（PDF、Office、代码、文本、音视频转录）
- 智谱优先 + 本地 Ollama 兜底的双通道策略
- 插件系统扩展
"""

import logging
import re
from pathlib import Path
from typing import Any, cast

# 导入核心模块
from dochris.core.cache import cache_dir, file_hash, load_cached, save_cached
from dochris.core.llm_client import LLMClient
from dochris.core.quality_scorer import score_summary_quality_v4
from dochris.core.utils import sanitize_filename
from dochris.exceptions import CompilationError
from dochris.manifest import get_default_workspace, get_manifest, update_manifest_status

# 导入解析器
from dochris.parsers.code_parser import detect_code_file, extract_from_code
from dochris.parsers.doc_parser import detect_document_file, parse_document
from dochris.parsers.pdf_parser import parse_pdf
from dochris.plugin import get_plugin_manager

# Layer 0 + Layer 1 质量系统
from dochris.quality.lint import lint_compile_result, lint_result_to_dict
from dochris.quality.provenance import compute_provenance, provenance_to_dict
from dochris.settings import get_settings

logger = logging.getLogger(__name__)

# ============================================================
# 默认配置：LLM API（主） + 本地 LLM（备）
# ============================================================


from dochris.settings.constants import CODING_LLM_API_BASE, DEFAULT_LLM_API_BASE

DEFAULT_LLM_MODEL = "glm-5.1"


class CompilerWorker:
    """编译 Worker（双通道：智谱优先 + 本地兜底）"""

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = DEFAULT_LLM_MODEL,
        # 本地兜底配置（从 settings 读取默认值）
        fallback_base_url: str = "",
        fallback_model: str = "",
        fallback_api_key: str = "",
        # 其他参数
        enable_fallback: bool = True,
        # 工作区路径（由调用方传入，避免全局 Settings 缓存问题）
        workspace: Path | None = None,
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

        # 从环境变量补充 API key（优先 Coding Plan 专用变量）
        import os

        if not api_key:
            api_key = (
                os.environ.get("BIGMODEL_API_KEY", "").strip()
                or os.environ.get("OPENAI_API_KEY", "")
                or os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
            )

        # 自动检测 base_url：优先 Coding Plan 端点
        if not base_url:
            bigmodel_key = os.environ.get("BIGMODEL_API_KEY", "").strip()
            anthropic_key = os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()
            if bigmodel_key or anthropic_key:
                base_url = CODING_LLM_API_BASE
            else:
                base_url = settings.api_base or DEFAULT_LLM_API_BASE

        # 主通道 LLM（智谱）
        if api_key and base_url:
            self.llm = LLMClient(api_key, base_url, model, request_delay=10.0)
            logger.info(f"主通道: {model} @ {base_url}")
        else:
            self.llm = None
            logger.warning("主通道未配置 API key，将仅使用本地兜底")

        # 兜底通道 LLM（本地 Ollama）
        if enable_fallback:
            self.fallback_llm = LLMClient(
                fallback_api_key, fallback_base_url, fallback_model, request_delay=5.0
            )
            logger.info(f"兜底通道: {fallback_model} @ {fallback_base_url}")
        else:
            self.fallback_llm = None

        self.enable_fallback = enable_fallback
        self.workspace = workspace if workspace is not None else get_default_workspace()
        self.cache_dir = cache_dir(self.workspace)

        # 向量存储实例缓存（避免每个文档重复初始化 embedding 模型）
        self._vector_store: Any | None = None

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
                await self._save_result(src_id, cached, int(cached.get("quality_score", 0) or 0))
                return cached

        # 3. 根据文件类型选择处理方式
        try:
            text = await self._extract_text(file_path, manifest["title"], src_id)

            if text is None:
                return None

            # 3.5 编译前处理（插件 hook）
            metadata = manifest.copy()
            pre_result = self.plugin_manager.call_hook_firstresult("pre_compile", text, metadata)
            if pre_result:
                text, metadata = pre_result
                logger.debug(f"应用 pre_compile hook: {src_id}")

            # 4. LLM 编译（带兜底）
            compile_result = await self._generate_with_fallback(text, manifest["title"])

            if not compile_result:
                logger.warning(f"⚠ LLM returned None for {src_id} ({file_path.name})")
                await self._mark_failed(src_id, "LLM compilation failed")
                return None

            # 5. 质量评分（支持插件自定义，Phase A 保留旧打分兜底）
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

            # 5.5 Layer 0 溯源标签 + Layer 1 结构化 Lint（Phase A 新增）
            try:
                provenance_result = compute_provenance(compile_result, text)
                compile_result["provenance"] = provenance_to_dict(provenance_result)
                logger.debug(
                    f"溯源标签: {provenance_result.overall_label} "
                    f"(置信度={provenance_result.confidence:.1f})"
                )
            except Exception as e:
                logger.warning(f"溯源分析异常（不影响编译）: {e}")
                compile_result["provenance"] = None

            try:
                lint_result = lint_compile_result(compile_result, text)
                compile_result["lint"] = lint_result_to_dict(lint_result)
                if not lint_result.passed:
                    logger.warning(
                        f"Lint 未通过: {lint_result.error_count} errors, "
                        f"{lint_result.warning_count} warnings"
                    )
            except Exception as e:
                logger.warning(f"Lint 校验异常（不影响编译）: {e}")
                compile_result["lint"] = None

            # 6. 保存到缓存
            if fh:
                save_success = save_cached(self.cache_dir, fh, compile_result)
                if not save_success:
                    logger.warning(f"Failed to save cache for {src_id}")

            # 7. 保存结果
            await self._save_result(src_id, compile_result, quality_score)

            # 7.1 原文 chunk 索引（可选，INDEX_RAW_CHUNKS 控制开关）
            self._index_raw_chunks(src_id, text, manifest)

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
        plugin_text = self.plugin_manager.call_hook_firstresult("ingest_parser", str(file_path))
        if plugin_text:
            logger.info(f"使用插件解析器提取文本: {file_path.name}")
            return cast(str | None, plugin_text)

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
        # 标准化 concepts：将字符串格式转为 {name, explanation} 格式
        raw_concepts = result.get("concepts", [])
        normalized_concepts = self._normalize_concepts(raw_concepts, result)
        result["concepts"] = normalized_concepts

        # 保存摘要（只写一份，按 src_id 命名）
        summaries_path = self.workspace / "outputs/summaries"
        summaries_path.mkdir(parents=True, exist_ok=True)

        # 构建 concepts 列表文本
        concept_lines = []
        for c in raw_concepts:
            name = c.get("name", "") if isinstance(c, dict) else str(c) if c else ""
            if name:
                concept_lines.append(f"- [[{name}]]")

        summary_content = (
            f"# {result.get('one_line', '')}\n\n"
            f"## Key Points\n\n"
            f"{chr(10).join(f'- {p}' for p in result.get('key_points', []))}\n\n"
            f"## Detailed Summary\n\n"
            f"{result.get('detailed_summary', '')}\n\n"
            f"## Concepts\n\n"
            f"{chr(10).join(concept_lines)}\n"
        )

        summary_file = summaries_path / f"{src_id}.md"
        summary_file.write_text(summary_content, encoding="utf-8")

        # 按标题创建符号链接（避免重复文件）
        manifest = get_manifest(self.workspace, src_id) or {}
        title = str(manifest.get("title", "")).strip()
        if title:
            safe_title = sanitize_filename(title, max_length=80)
            # 去掉标题自带的 .md 后缀，避免 ".md.md" 双重扩展名
            if safe_title.lower().endswith(".md"):
                safe_title = safe_title[:-3]
            title_file = summaries_path / f"{safe_title}.md"
            if title_file != summary_file and not title_file.exists():
                try:
                    title_file.symlink_to(summary_file)
                except OSError as e:
                    # symlink 失败会导致按标题查询找不到文件，记录 warning 便于排查
                    logger.warning(f"创建标题符号链接失败 {title_file.name}: {e}")

        # 保存概念文件（始终写入，不受质量门槛限制）
        concepts_dir = self.workspace / "outputs/concepts"
        concepts_dir.mkdir(parents=True, exist_ok=True)

        for idx, concept in enumerate(normalized_concepts, 1):
            concept_name = concept["name"]
            concept_desc = concept.get("explanation", "")

            # 清理概念名中的非法路径字符
            safe_name = re.sub(r'[<>:"/\\|?*]', "", concept_name.strip()).replace(" ", "_")[:60]
            if not safe_name:
                safe_name = f"concept_{idx}"
            concept_file = concepts_dir / f"{safe_name}.md"
            # 避免同名覆盖：追加序号
            if concept_file.exists():
                concept_file = concepts_dir / f"{safe_name}_{src_id}.md"
            concept_content = f"# {concept_name}\n\n{concept_desc}\n"
            concept_file.write_text(concept_content, encoding="utf-8")

        # 向量嵌入：将摘要和概念嵌入到向量数据库
        self._embed_to_vector_store(src_id, result, manifest)

        # 计算 trust_level（基于 provenance + lint 的真实质量信号）
        trust_level = self._compute_trust_level(result)

        # 更新 manifest（一次性写入，包含 provenance/lint 元数据）
        update_manifest_status(
            self.workspace,
            src_id,
            "compiled",
            quality_score=quality_score,
            summary=result,
            compiled_summary=result,
            promoted_to="",  # 空字符串哨兵：重新编译时清空旧的晋升标记
            trust_level=trust_level,
        )

    @staticmethod
    def _compute_trust_level(result: dict[str, Any]) -> str:
        """基于 provenance + lint 计算信任等级

        Returns:
            "high"    — extracted/merged + lint passed
            "medium"  — inferred 或 lint 有 warning
            "low"     — ambiguous 或 lint 有 error
        """
        prov = result.get("provenance")
        lint_data = result.get("lint")

        prov_label = ""
        if prov and isinstance(prov, dict):
            prov_label = prov.get("overall_label", "")

        lint_passed = True
        has_errors = False
        if lint_data and isinstance(lint_data, dict):
            lint_passed = lint_data.get("passed", True)
            has_errors = any(i.get("severity") == "error" for i in lint_data.get("issues", []))

        if has_errors or prov_label == "ambiguous":
            return "low"
        if lint_passed and prov_label in ("extracted", "merged"):
            return "high"
        return "medium"

    def _get_vector_store(self) -> Any:
        """获取向量存储实例（缓存复用，避免重复初始化 embedding 模型）。"""
        if self._vector_store is not None:
            return self._vector_store
        try:
            from dochris.vector import get_store

            settings = get_settings()
            data_dir = self.workspace / "data"
            store_cls = get_store(settings.vector_store)
            self._vector_store = store_cls(persist_directory=str(data_dir))
            return self._vector_store
        except ImportError:
            logger.debug("向量存储依赖未安装")
            return None
        except Exception as e:
            logger.warning(f"向量存储初始化失败: {e}")
            return None

    def _index_raw_chunks(
        self, src_id: str, text: str, manifest: dict[str, Any]
    ) -> None:
        """将原文切分为 chunk 并索引到向量库的 chunks collection。

        由 INDEX_RAW_CHUNKS 配置控制开关，默认关闭。
        切分策略由 CHUNK_STRATEGY 配置（structure/recursive/semantic）。

        Args:
            src_id: manifest ID
            text: 原文全文
            manifest: manifest 数据
        """
        try:
            settings = get_settings()
            # 开关：默认关闭，避免影响现有行为
            if settings.index_raw_chunks != "true":
                return
            if not text or not text.strip():
                return

            from dochris.rag.chunking import (
                ChunkMetadata,
                create_chunker,
            )

            strategy = getattr(settings, "chunk_strategy", "structure")
            # recursive 用 token 维度，其他用字符维度
            if strategy == "recursive":
                chunk_size = getattr(settings, "chunk_size_tokens", 800)
                overlap = getattr(settings, "chunk_overlap_tokens", 120)
            else:
                chunk_size = getattr(settings, "chunk_size_chars", 4000)
                overlap = getattr(settings, "chunk_overlap_chars", 200)

            chunker_kwargs: dict[str, Any] = {"chunk_size": chunk_size, "overlap": overlap}
            if strategy == "semantic":
                chunker_kwargs["breakpoint_percentile"] = getattr(
                    settings, "semantic_breakpoint_percentile", 95.0
                )
                chunker_kwargs["embedding_model"] = getattr(
                    settings, "embedding_model", "BAAI/bge-small-zh-v1.5"
                )

            chunker = create_chunker(strategy, **chunker_kwargs)
            metadata = ChunkMetadata(
                src_id=src_id,
                title=manifest.get("title", src_id),
                strategy=strategy,
            )
            chunks = chunker.split(text, metadata)
            if not chunks:
                return

            store = self._get_vector_store()
            if store is None:
                return

            documents = [c.content for c in chunks]
            ids = [c.id for c in chunks]
            metadatas = [
                {
                    "source": src_id,
                    "title": manifest.get("title", src_id),
                    "type": manifest.get("type", "unknown"),
                    "section": c.metadata.section,
                    "start_char": c.metadata.start_char,
                    "end_char": c.metadata.end_char,
                    "strategy": c.metadata.strategy,
                    "chunk_index": idx,
                    "trust_level": "outputs",
                }
                for idx, c in enumerate(chunks)
            ]

            store.add_documents(
                collection="chunks",
                documents=documents,
                ids=ids,
                metadatas=metadatas,
            )
            logger.info(f"索引 {len(chunks)} 个原文 chunk: {src_id} (strategy={strategy})")
        except ImportError:
            logger.debug("chunking 依赖未安装，跳过原文索引")
        except Exception as e:
            logger.warning(f"原文 chunk 索引失败（不影响编译结果）: {e}")

    def _embed_to_vector_store(
        self, src_id: str, result: dict[str, Any], manifest: dict[str, Any]
    ) -> None:
        """将编译结果嵌入向量数据库

        将摘要和概念文本分别存入向量库的不同 collection，
        支持后续的语义相似度检索。

        Args:
            src_id: manifest ID
            result: 编译结果
            manifest: manifest 数据
        """
        try:
            store = self._get_vector_store()
            if store is None:
                return

            title = manifest.get("title", src_id)

            # 1. 嵌入摘要
            summary_parts: list[str] = []
            if result.get("one_line"):
                summary_parts.append(result["one_line"])
            if result.get("key_points"):
                summary_parts.extend(result["key_points"])
            if result.get("detailed_summary"):
                summary_parts.append(result["detailed_summary"][:2000])

            if summary_parts:
                summary_text = "\n".join(summary_parts)
                store.add_documents(
                    collection="summaries",
                    documents=[summary_text],
                    ids=[f"{src_id}_summary"],
                    metadatas=[
                        {
                            "source": src_id,
                            "title": title,
                            "type": manifest.get("type", "unknown"),
                            "file": f"outputs/summaries/{src_id}.md",
                        }
                    ],
                )
                logger.debug(f"向量嵌入摘要: {src_id}")

            # 2. 嵌入概念
            concepts = result.get("concepts", [])
            if concepts:
                concept_docs = []
                concept_ids = []
                concept_metas = []
                for idx, concept in enumerate(concepts):
                    if isinstance(concept, dict):
                        name = concept.get("name", "")
                        explanation = concept.get("explanation", "")
                    elif isinstance(concept, str):
                        name = concept
                        explanation = ""
                    else:
                        continue

                    if not name:
                        continue

                    doc_text = f"{name}: {explanation}" if explanation else name
                    concept_docs.append(doc_text)
                    concept_ids.append(f"{src_id}_concept_{idx}")
                    concept_metas.append(
                        {
                            "source": src_id,
                            "title": title,
                            "concept_name": name,
                            "type": "concept",
                        }
                    )

                if concept_docs:
                    store.add_documents(
                        collection="concepts",
                        documents=concept_docs,
                        ids=concept_ids,
                        metadatas=concept_metas,
                    )
                    logger.debug(f"向量嵌入 {len(concept_docs)} 个概念: {src_id}")

        except ImportError:
            logger.debug("向量存储依赖未安装，跳过向量嵌入")
        except Exception as e:
            logger.warning(f"向量嵌入失败（不影响编译结果）: {e}")

    async def _mark_failed(self, src_id: str, error_message: str) -> None:
        """标记编译失败"""
        manifest = get_manifest(self.workspace, src_id) or {}
        current_status = manifest.get("status")
        if current_status in {"compiled", "promoted_to_wiki", "promoted"}:
            logger.warning(
                "跳过失败状态回写: %s 当前已是 %s，保留已有成功结果",
                src_id,
                current_status,
            )
            return
        update_manifest_status(self.workspace, src_id, "failed", error_message=error_message)

    @staticmethod
    def _normalize_concepts(
        raw_concepts: list[Any], result: dict[str, Any]
    ) -> list[dict[str, str]]:
        """将 concepts 标准化为 {name, explanation} 格式

        LLM 有时返回纯字符串列表而非对象列表，此方法将字符串格式
        转为 {name, explanation} 格式，explanation 从详细摘要中提取。

        Args:
            raw_concepts: 原始概念列表（可能是字符串或字典）
            result: 完整编译结果（用于提取 explanation）

        Returns:
            标准化的概念列表 [{"name": str, "explanation": str}]
        """
        detailed_summary = result.get("detailed_summary", "")
        normalized: list[dict[str, str]] = []

        for concept in raw_concepts:
            if isinstance(concept, dict):
                name = str(concept.get("name", "")).strip()
                explanation = str(
                    concept.get("explanation") or concept.get("description") or ""
                ).strip()
                if not name:
                    continue
                # 如果有 explanation，直接使用
                if explanation:
                    normalized.append({"name": name, "explanation": explanation})
                else:
                    # 从详细摘要中提取包含该概念名的句子
                    explanation = _extract_concept_context(name, detailed_summary)
                    normalized.append({"name": name, "explanation": explanation})
            elif isinstance(concept, str) and concept.strip():
                name = concept.strip()
                explanation = _extract_concept_context(name, detailed_summary)
                normalized.append({"name": name, "explanation": explanation})

        return normalized


def _extract_concept_context(concept_name: str, text: str, max_chars: int = 200) -> str:
    """从文本中提取包含概念名的上下文句子

    三级匹配策略：
    1. 精确匹配完整概念名
    2. 提取核心关键词（冒号/破折号前的部分）匹配
    3. 关键词片段匹配

    Args:
        concept_name: 概念名称
        text: 源文本（通常是详细摘要）
        max_chars: 最大提取字符数

    Returns:
        提取的上下文文本
    """
    import re

    sentences = re.split(r"[。！？\n]", text)

    def _search(patterns: list[str]) -> list[str]:
        hits = []
        for sent in sentences:
            sent = sent.strip()
            if len(sent) <= 5:
                continue
            if any(p in sent for p in patterns):
                hits.append(sent)
                if len(hits) >= 2:
                    break
        return hits

    # 1. 精确匹配完整概念名
    relevant = _search([concept_name])
    if relevant:
        return "。".join(relevant)[:max_chars]

    # 2. 提取核心关键词（冒号、破折号、括号前的部分）
    core_name = re.split(r"[:：\-—–(（]", concept_name)[0].strip()
    if core_name and len(core_name) >= 2 and core_name != concept_name:
        relevant = _search([core_name])
        if relevant:
            return "。".join(relevant)[:max_chars]

    # 3. 关键词片段匹配（去空格后）
    keywords = concept_name.replace(" ", "")
    relevant = _search([keywords])
    if relevant:
        return "。".join(relevant)[:max_chars]

    # 全部失败 — 使用默认模板
    return f"{concept_name}（详细解释请参阅原文）"
