# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.0] - 2026-05-04

### Added
- **API 文档站**：mkdocs-material 静态站点（22 个页面），GitHub Pages 自动部署
- **Web UI 增强**：中文状态标签、搜索过滤、知识图谱 D3.js 可视化
- **查询历史**：Web UI 保存最近 20 条查询记录
- **系统信息面板**：显示 dochris 版本号及各依赖版本
- **CLAUDE.md 文档全面更新**：项目结构同步至实际代码（新增 api/, graph/, llm/, settings/, web/, admin/, plugin/, vector/ 子包）

### Fixed
- **CI 全面修复**：依赖安装、测试兼容性、安全扫描配置
- **json_repair 返回值验证**：防御性编程，防止空值导致崩溃
- **ruff lint**：0 errors

### Changed
- **ROADMAP P3 全部完成**
- **Dependabot**：自动更新 GitHub Actions 版本

## [1.3.1] - 2026-05-02

### Fixed
- **知识图谱可视化**：D3.js 力导向图（Web UI Tab 6）+ API + CLI
- **CORS 安全**：`allow_origins` 从 `DOCHRIS_CORS_ORIGINS` 环境变量配置
- **API 认证**：`DOCHRIS_API_KEY` 中间件（未设置时跳过）
- **Logger 迁移**：非 CLI 模块 199 个 `print()` 替换为 `logger`
- **subprocess 安全**：`shell=True` 改为列表形式
- **Plugin 安全**：`exec()` 添加 safe builtins 限制
- **Gradio + FastAPI 统一**：`kb serve` 单端口同时服务 API + Web UI
- **ruff lint**：0 errors

## [1.3.0] - 2026-05-02

### Added
- **Gradio Web UI**：5 个功能页面（知识库查询、文件管理、编译控制、系统状态、质量仪表盘）
- **`kb serve --web`**：启动 Gradio Web UI（端口 7860）
- **`[web]` optional dependency**：`pip install dochris[web]`
- **Docker 部署优化**：多阶段构建 + BUILD_TARGET 参数（core/pdf/api/web/all）
- **docker-compose.yml**：ChromaDB 独立服务 + API 服务 + healthcheck
- **性能基准测试**：5 个 benchmark（编译/索引/查询/向量/解析）
- **text_chunker 优化**：减少字符串拷贝
- **Makefile**：新增 `web`、`web-api`、`docker-all`、`bench` 等 targets
- **测试覆盖率 80%**：2675 tests（+23 Web UI tests）

## [1.2.0] - 2026-05-02

### Added
- **API 文档站**：mkdocs-material 自动部署到 GitHub Pages
- **HTTP API 层**：FastAPI REST 接口（查询、编译、状态）
- **Codecov 集成**：CI 覆盖率可视化
- **异常规范化**：38 个 `except Exception` 审查确认均为合法 fallback

### Changed
- **覆盖率**：70% → 76%（+315 tests，2087→2402）
- **mypy**：114 errors → 0 errors
- **测试**：18 个参数化测试类 + 14 个集成测试
- **批量质量改进**：6 个 examples、299 新测试、uv.lock
- **设置模块拆分**：settings.py（801行）→ settings/ 包（6个文件）
- **异常规范化**：30+ `except Exception` → 具体异常类型
- **Promote 质量门槛**：compile 时检查 quality_score

### Fixed
- B904 ruff 规则：所有 except 使用 `raise ... from`
- chromadb 类型冲突：`cast(Any, ...)` 解决
- CLI 错误处理：6 个退出码

## [1.1.0] - 2026-05-01

### Added
- **插件系统**：6 个扩展点（ingest_parser, pre_compile, post_compile, quality_score, pre_query, post_query）
- **LLM 提供商抽象层**：OpenAI 兼容 + Ollama 本地模型
- **向量数据库抽象层**：ChromaDB + FAISS 双后端
- **结构化日志**：JSON/text 格式，CLI `--log-format` 切换
- **类型系统**：types.py + protocols.py（PEP 544 协议）
- **常量模块**：constants.py（项目级 + 设置级分离）
- **设置模块拆分**：settings.py（801 行）→ settings/ 包（6 个文件）
- **CLI 补全**：`kb --completion bash/zsh/fish`
- **Makefile**：18 个常用命令
- **pre-commit hooks**：ruff + mypy
- **.editorconfig**：统一代码风格
- **Benchmark 测试**：parsers + quality 性能基准
- **6 个示例插件**：epub_parser, compile_notify, query_enhance
- **6 个使用示例**：basic_ingest 到 plugin_hooks
- **Dockerfile** + docker_entrypoint.sh
- **git-cliff** 自动 CHANGELOG 生成
- **Dependabot**：pip + GitHub Actions 依赖更新
- **Stale Bot**：自动关闭过期 Issue/PR
- **py.typed**（PEP 561）、.gitattributes、CODEOWNERS、FUNDING.yml
- **异常规范化**：15 种 → 具体异常类型
- **2000+ 测试**（70% 覆盖率，2087 passed）

### Changed
- **mypy 0 errors**（从 114 个减少）
- **ruff 0 errors**（从 528 个减少）
- 测试覆盖率 50% → 70.01%
- 项目重命名：kb-compiler → dochris
- Settings 拆分为独立模块
- CLI 入口重构：558→368 行
- 质量门禁提升至 60%

### Fixed
- 修复 quality_scorer 首次评分 10 分问题
- 修复 index_knowledge mock 路径
- 修复 B904 ruff 规则（raise from）
- 修复 chromadb 类型冲突（cast Any）
- 修复 pdf_parser 第三方库异常处理

---

## [1.0.0] - 2026-04-30

### Added
- `kb init` 命令：交互式初始化知识库工作区
- `kb doctor` 命令：环境诊断和配置检查
- GitHub Actions CI/CD 配置
- PR 模板和贡献指南
- 全面的测试覆盖（Phase 1, Phase 2, 质量评分等）

### Changed
- 统一配置管理：从 `config.py` 迁移到 `settings.py`
- 重构 CLI 命令结构，改进命令分组
- 改进错误处理和异常层级
- 优化重试逻辑和模型降级策略

### Fixed
- 移除硬编码的 API Key
- 修复质量评分首次总是 10 分的问题
- 修复 CLI 参数处理和并发控制

### Security
- 添加 SECURITY.md 安全策略
- 实现敏感词过滤和内容审核

## [0.5.0] - 2026-04-15

### Added
- Comprehensive test suite (pytest)
- Code coverage reporting
- Modular core/ and workers/ directories
- Custom exception classes (exceptions.py)
- Configuration centralization (config.py)
- Parser modules for different file types

### Changed
- Refactored Phase 2 compilation for better testability
- Improved error messages and logging
- Better separation of concerns across modules

### Fixed
- Race conditions in concurrent compilation
- Memory leaks in long-running compilation jobs
- Manifest index corruption on concurrent writes

## [0.4.0] - 2026-04-10

### Added
- Async compilation with proper async/await patterns
- Caching system for LLM responses
- Incremental compilation resume capability
- Better progress tracking

### Changed
- Improved retry logic with exponential backoff
- Optimized for long-running compilation sessions
- Better memory management

### Fixed
- Hanging processes on API timeouts
- Duplicate compilation of already-processed files
- Progress file corruption on crashes

## [0.3.0] - 2026-04-07

### Added
- Vault Bridge for Obsidian integration
- Bidirectional sync with Obsidian vaults
- Seed notes from Obsidian for compilation
- Promote artifacts back to Obsidian
- Associated notes listing

### Changed
- Enhanced manifest format with Obsidian metadata
- Improved content sanitization for Obsidian compatibility
- Better internal reference handling

### Fixed
- Broken wikilinks when promoting to Obsidian
- Metadata loss during vault sync

## [0.2.0] - 2026-04-05

### Added
- Quality scoring system (multi-dimensional evaluation)
- Pollution detection and automatic downgrade
- Quality gate enforcement
- Manifest-based tracking system
- Batch promotion tools
- Four-layer trust model architecture

### Changed
- Improved LLM prompt engineering for better outputs
- Enhanced error handling and retry logic
- Better progress tracking with JSON files

### Fixed
- Low-quality outputs passing through
- No visibility into compilation quality
- Difficulty tracking processed vs unprocessed files

## [0.1.0] - 2026-04-01

### Added
- Initial release
- Three-phase pipeline (Ingestion, Compilation, Query)
- ChromaDB vector store integration
- Chinese semantic embedding (BAAI/bge-small-zh-v1.5)
- markitdown for file-to-text conversion
- Support for PDFs, audio, video, ebooks, articles
- Structured JSON extraction (summaries, key points, concepts)
- Content sanitization for API compliance
- Failed queue tracking
- Progress.json tracking

### Features
- Phase 1: File ingestion with symlinks and deduplication
- Phase 2: LLM compilation with quality filtering
- Phase 3: Semantic search with ChromaDB
- Obsidian-style wikilink format in index.md

## [0.0.1] - 2026-03-15

### Added
- Project initialization
- Basic PDF processing pipeline
- LLM API integration

---

## Version History Summary

| Version | Date | Major Features |
|---------|------|----------------|
| 1.4.0 | 2026-05-04 | API 文档站 (mkdocs), Web UI 增强, 知识图谱可视化, CLAUDE.md 文档同步 |
| 1.3.1 | 2026-05-02 | 知识图谱 D3.js 可视化, CORS/API 认证, Logger 迁移, Gradio+FastAPI 统一 |
| 1.3.0 | 2026-05-02 | Gradio Web UI (5 页面), Docker 部署优化, Benchmark 测试, 80% 覆盖率 |
| 1.2.0 | 2026-05-02 | HTTP API 层 (FastAPI), API 文档站, 异常规范化, mypy 0 errors |
| 1.1.0 | 2026-05-01 | 插件系统, LLM/Ollama 抽象, FAISS 向量后端, 类型系统, 2000+ tests |
| 1.0.0 | 2026-04-30 | Production release: init/doctor commands, CI/CD, comprehensive tests |
| 0.5.0 | 2026-04-15 | Code quality, test coverage, modularization |
| 0.4.0 | 2026-04-10 | Async compilation, caching, resume support |
| 0.3.0 | 2026-04-07 | Vault Bridge, Obsidian integration |
| 0.2.0 | 2026-04-05 | Quality scoring, pollution detection, manifests |
| 0.1.0 | 2026-04-01 | Three-phase pipeline, ChromaDB, vector search |
| 0.0.1 | 2026-03-15 | Initial PDF processing prototype |
