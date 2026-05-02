#!/usr/bin/env python3
"""
Settings 配置类
定义知识库系统的核心配置结构
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dochris.settings.constants import DEFAULT_LLM_API_BASE

logger = logging.getLogger(__name__)

# 尝试导入 python-dotenv，如果不存在则提示安装
try:
    from dotenv import load_dotenv
except ImportError:
    logger.warning("python-dotenv 未安装，将只使用环境变量")
    logger.warning("安装命令: pip install python-dotenv")

    # 类型忽略：这是一个兼容性处理，提供默认实现
    def load_dotenv(*args: object, **kwargs: object) -> bool:  # type: ignore[misc]
        """空函数，当 dotenv 不可用时使用"""
        return False


@dataclass
class Settings:
    """知识库系统配置

    配置优先级: .env 文件 > 环境变量 > 默认值
    """

    # ============================================================
    # 路径配置
    # ============================================================

    workspace: Path = field(default_factory=lambda: Path.home() / ".knowledge-base")
    """工作区路径，默认 ~/.knowledge-base"""

    source_path: Path | None = None
    """源文件扫描路径，可选"""

    obsidian_vaults: list[Path] = field(default_factory=list)
    """Obsidian vault 路径列表"""

    openclaw_config_path: Path = field(
        default_factory=lambda: Path.home() / ".openclaw/openclaw.json"
    )
    """OpenClaw 配置文件路径"""

    # ============================================================
    # API 配置
    # ============================================================

    api_key: str | None = None
    """LLM API 密钥"""

    api_base: str = field(
        default_factory=lambda: os.environ.get(
            "OPENAI_API_BASE", DEFAULT_LLM_API_BASE
        )
    )
    """LLM API 基础 URL"""

    model: str = field(default_factory=lambda: os.environ.get("MODEL", "glm-5.1"))
    """默认 LLM 模型"""

    llm_provider: str = field(default_factory=lambda: os.environ.get("LLM_PROVIDER", "openai_compat"))
    """LLM 提供商类型 (openai_compat, ollama)"""

    query_model: str = "glm-4-flash"
    """Phase 3 查询专用模型"""

    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    """向量嵌入模型"""

    # ============================================================
    # 向量配置
    # ============================================================

    vector_store: str = field(
        default_factory=lambda: os.environ.get("VECTOR_STORE", "chromadb")
    )
    """向量数据库类型 (chromadb, faiss)"""

    # OpenRouter 备用配置
    openrouter_api_base: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "qwen/qwen-2.5-72b-instruct:free"

    # 本地 LLM 配置（Ollama 等本地服务）
    local_llm_base_url: str = field(
        default_factory=lambda: os.environ.get("LOCAL_LLM_BASE_URL", "")
    )
    """本地 LLM API 基础 URL（如 Ollama: http://localhost:11434/v1）"""

    local_llm_model: str = field(
        default_factory=lambda: os.environ.get("LOCAL_LLM_MODEL", "qwen:14b")
    )
    """本地 LLM 模型名称"""

    local_llm_api_key: str = field(
        default_factory=lambda: os.environ.get("LOCAL_LLM_API_KEY", "ollama")
    )
    """本地 LLM API 密钥（Ollama 通常为 "ollama"）"""

    # ============================================================
    # 编译配置
    # ============================================================

    max_concurrency: int = field(
        default_factory=lambda: int(os.environ.get("MAX_CONCURRENCY", "3"))
    )
    """最大并发数"""

    batch_size: int = 10
    """批处理大小"""

    llm_max_tokens: int = 40000
    """LLM 最大 token 数"""

    llm_temperature: float = 0.1
    """LLM 温度参数"""

    llm_timeout: float = 300.0
    """LLM 请求超时（秒）"""

    llm_request_delay: float = 5.0
    """LLM 请求间隔（秒）"""

    # ============================================================
    # 质量配置
    # ============================================================

    min_quality_score: int = field(
        default_factory=lambda: int(os.environ.get("MIN_QUALITY_SCORE", "85"))
    )
    """最低质量分数（通过门槛）"""

    max_content_chars: int = field(
        default_factory=lambda: int(os.environ.get("MAX_CONTENT_CHARS", "20000"))
    )
    """单文件最大字符数"""

    # ============================================================
    # 重试配置
    # ============================================================

    max_retries: int = 3
    """最大重试次数"""

    retry_delay_429: float = 20.0
    """429 错误初始延迟（秒）"""

    retry_delay_connection: float = 15.0
    """连接错误初始延迟（秒）"""

    retry_delay_general: float = 10.0
    """一般错误初始延迟（秒）"""

    # ============================================================
    # Phase 1 配置
    # ============================================================

    max_file_size: int = field(
        default_factory=lambda: 500 * 1024 * 1024  # 500MB
    )
    """最大文件大小"""

    # ============================================================
    # 日志配置
    # ============================================================

    log_level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO"))
    """日志级别"""

    log_format: str = "%(asctime)s.%(msecs)03d [%(levelname)-8s] %(message)s"
    log_format_simple: str = "%(asctime)s [%(levelname)s] %(message)s"
    log_date_format: str = "%Y%m%d_%H%M%S"

    # ============================================================
    # 插件配置
    # ============================================================

    plugin_dirs: list[str] = field(default_factory=list)
    """插件目录列表"""

    plugins_enabled: list[str] = field(default_factory=list)
    """启用的插件列表"""

    plugins_disabled: list[str] = field(default_factory=list)
    """禁用的插件列表"""

    # ============================================================
    # 缓存配置
    # ============================================================

    cache_retention_days: int = 30
    """缓存保留天数"""

    min_text_length: int = 100
    """文本最小长度（判断是否有意义）"""

    # ============================================================
    # 工厂方法
    # ============================================================

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Settings":
        """从环境变量和 .env 文件加载配置

        Args:
            env_file: .env 文件路径，默认为 workspace/.env

        Returns:
            Settings 实例
        """
        # 1. 先尝试从可能的 workspace 位置加载 .env
        env_paths = [
            Path.cwd() / ".env",
            Path.home() / ".knowledge-base" / ".env",
            Path.home() / ".openclaw" / "knowledge-base" / ".env",
        ]
        if env_file:
            env_paths.insert(0, env_file)

        for env_path in env_paths:
            if env_path.exists():
                load_dotenv(env_path)
                break

        # 2. 解析特殊配置
        workspace_str = os.environ.get("WORKSPACE")
        workspace: Path
        if workspace_str:
            workspace = Path(workspace_str).expanduser()
        else:
            # 尝试检测当前是否在知识库目录中
            cwd = Path.cwd()
            if (cwd / "scripts" / "config.py").exists():
                workspace = cwd
            elif (cwd.parent / "scripts" / "config.py").exists():
                workspace = cwd.parent
            else:
                workspace = Path.home() / ".knowledge-base"

        # 解析 source_path
        source_path_str = os.environ.get("SOURCE_PATH")
        source_path = Path(source_path_str).expanduser() if source_path_str else None

        # 解析 obsidian_vaults
        obsidian_vaults_str = os.environ.get("OBSIDIAN_VAULTS", "")
        obsidian_vaults: list[Path] = []
        if obsidian_vaults_str:
            obsidian_vaults = [Path(p).expanduser() for p in obsidian_vaults_str.split(":")]
        elif os.environ.get("OBSIDIAN_VAULT"):
            obsidian_vaults = [Path(os.environ["OBSIDIAN_VAULT"]).expanduser()]

        # 解析 API 配置
        api_key = os.environ.get("OPENAI_API_KEY")
        api_base = os.environ.get("OPENAI_API_BASE", DEFAULT_LLM_API_BASE)
        model = os.environ.get("MODEL", "glm-5.1")

        # 解析插件配置
        plugin_dirs_str = os.environ.get("PLUGIN_DIRS", "")
        plugin_dirs = [Path(p).expanduser() for p in plugin_dirs_str.split(":")] if plugin_dirs_str else []

        plugins_enabled_str = os.environ.get("PLUGINS_ENABLED", "")
        plugins_enabled = plugins_enabled_str.split(",") if plugins_enabled_str else []

        plugins_disabled_str = os.environ.get("PLUGINS_DISABLED", "")
        plugins_disabled = plugins_disabled_str.split(",") if plugins_disabled_str else []

        # 3. 创建实例
        return cls(
            workspace=workspace,
            source_path=source_path,
            obsidian_vaults=obsidian_vaults,
            api_key=api_key,
            api_base=api_base,
            model=model,
            llm_provider=os.environ.get("LLM_PROVIDER", "openai_compat"),
            query_model=os.environ.get("QUERY_MODEL", "glm-4-flash"),
            embedding_model=os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"),
            vector_store=os.environ.get("VECTOR_STORE", "chromadb"),
            max_concurrency=int(os.environ.get("MAX_CONCURRENCY", "3")),
            min_quality_score=int(os.environ.get("MIN_QUALITY_SCORE", "85")),
            max_content_chars=int(os.environ.get("MAX_CONTENT_CHARS", "20000")),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            plugin_dirs=[str(p) for p in plugin_dirs],
            plugins_enabled=plugins_enabled,
            plugins_disabled=plugins_disabled,
        )

    # ============================================================
    # 路径访问器
    # ============================================================

    @property
    def logs_dir(self) -> Path:
        """日志目录"""
        return self.workspace / "logs"

    @property
    def cache_dir(self) -> Path:
        """缓存目录"""
        return self.workspace / "cache"

    @property
    def outputs_dir(self) -> Path:
        """输出目录"""
        return self.workspace / "outputs"

    @property
    def raw_dir(self) -> Path:
        """原始文件目录"""
        return self.workspace / "raw"

    @property
    def wiki_dir(self) -> Path:
        """Wiki 目录"""
        return self.workspace / "wiki"

    @property
    def wiki_summaries_dir(self) -> Path:
        """Wiki 摘要目录"""
        return self.wiki_dir / "summaries"

    @property
    def wiki_concepts_dir(self) -> Path:
        """Wiki 概念目录"""
        return self.wiki_dir / "concepts"

    @property
    def curated_dir(self) -> Path:
        """精选内容目录"""
        return self.workspace / "curated"

    @property
    def curated_promoted_dir(self) -> Path:
        """精选已推送目录"""
        return self.curated_dir / "promoted"

    @property
    def manifests_dir(self) -> Path:
        """Manifest 目录"""
        return self.workspace / "manifests" / "sources"

    @property
    def data_dir(self) -> Path:
        """数据目录"""
        return self.workspace / "data"

    @property
    def progress_file(self) -> Path:
        """进度文件"""
        return self.workspace / "progress.json"

    @property
    def phase2_lock_file(self) -> Path:
        """Phase 2 锁文件"""
        return self.workspace / "phase2.lock"

    # ============================================================
    # 验证方法
    # ============================================================

    def validate_api_key(self) -> str:
        """验证 API 密钥是否存在

        Returns:
            API 密钥字符串

        Raises:
            ValueError: 当 API 密钥未设置时
        """
        api_key = self.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY 环境变量未设置\n"
                "请设置: export OPENAI_API_KEY='your-api-key'\n"
                "或在 .env 文件中添加: OPENAI_API_KEY=your-api-key"
            )
        return api_key

    def validate(self) -> list[str]:
        """验证关键配置项

        验证规则：
            - api_base 不能为空字符串
            - model 不能为空
            - workspace 路径应该存在或可创建
            - api_key 应该存在（警告级别，可通过 OpenClaw config 获取）

        Returns:
            警告信息列表（空列表表示无警告）

        Raises:
            ValueError: 当关键配置无效时
        """
        warnings: list[str] = []

        # 验证 api_base
        if not self.api_base or not self.api_base.strip():
            raise ValueError("api_base 不能为空，请设置 OPENAI_API_BASE 环境变量")

        # 验证 model
        if not self.model or not self.model.strip():
            raise ValueError("model 不能为空，请设置 MODEL 环境变量")

        # 验证 workspace
        if not self.workspace:
            raise ValueError("workspace 路径不能为空")

        # 尝试创建 workspace 目录
        try:
            self.workspace.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ValueError(
                f"workspace 路径无效或无法创建: {self.workspace}\n错误: {e}"
            ) from e

        # 验证 api_key（警告级别）
        api_key = self.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            # 检查 OpenClaw 配置文件
            if self.openclaw_config_path.exists():
                warnings.append(
                    f"OPENAI_API_KEY 未设置，可能从 OpenClaw 配置获取: {self.openclaw_config_path}"
                )
            else:
                warnings.append(
                    "OPENAI_API_KEY 未设置，请在运行前设置环境变量或 .env 文件"
                )

        return warnings


# ============================================================
# 全局单例
# ============================================================

_global_settings: Settings | None = None


def get_settings(reload: bool = False) -> Settings:
    """获取全局 Settings 实例

    Args:
        reload: 是否重新加载配置

    Returns:
        Settings 实例
    """
    global _global_settings
    if _global_settings is None or reload:
        _global_settings = Settings.from_env()
    return _global_settings


def reset_settings() -> None:
    """重置全局 Settings（主要用于测试）"""
    global _global_settings
    _global_settings = None
