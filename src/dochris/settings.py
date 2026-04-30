#!/usr/bin/env python3
"""
统一配置管理 - Settings 类

支持配置优先级: .env 文件 > 环境变量 > 默认值
使用 python-dotenv 实现 .env 文件加载
使用 dataclass 定义配置结构，支持类型检查

用法:
    from dochris.settings import get_settings

    settings = get_settings()
    print(settings.workspace)
    print(settings.api_key)
"""

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 默认 LLM API Base URL（统一常量，所有引用都从这里取）
DEFAULT_LLM_API_BASE = "https://open.bigmodel.cn/api/paas/v4"

# 尝试导入 python-dotenv，如果不存在则提示安装
try:
    from dotenv import load_dotenv
except ImportError:
    print("警告: python-dotenv 未安装，将只使用环境变量", file=sys.stderr)
    print("安装命令: pip install python-dotenv", file=sys.stderr)

    def load_dotenv(*args, **kwargs) -> bool:
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

    query_model: str = "glm-4-flash"
    """Phase 3 查询专用模型"""

    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    """向量嵌入模型"""

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

        # 3. 创建实例
        return cls(
            workspace=workspace,
            source_path=source_path,
            obsidian_vaults=obsidian_vaults,
            api_key=api_key,
            api_base=api_base,
            model=model,
            query_model=os.environ.get("QUERY_MODEL", "glm-4-flash"),
            embedding_model=os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"),
            max_concurrency=int(os.environ.get("MAX_CONCURRENCY", "3")),
            min_quality_score=int(os.environ.get("MIN_QUALITY_SCORE", "85")),
            max_content_chars=int(os.environ.get("MAX_CONTENT_CHARS", "20000")),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
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


# ============================================================
# 向后兼容函数
# ============================================================


def get_workspace() -> Path:
    """获取工作区路径（向后兼容）"""
    return get_settings().workspace


def get_logs_dir() -> Path:
    """获取日志目录路径（向后兼容）"""
    return get_settings().logs_dir


def get_cache_dir() -> Path:
    """获取缓存目录路径（向后兼容）"""
    return get_settings().cache_dir


def get_outputs_dir() -> Path:
    """获取输出目录路径（向后兼容）"""
    return get_settings().outputs_dir


def get_raw_dir() -> Path:
    """获取原始文件目录路径（向后兼容）"""
    return get_settings().raw_dir


def get_wiki_dir() -> Path:
    """获取 Wiki 目录路径（向后兼容）"""
    return get_settings().wiki_dir


def get_wiki_summaries_dir() -> Path:
    """获取 Wiki 摘要目录路径（向后兼容）"""
    return get_settings().wiki_summaries_dir


def get_wiki_concepts_dir() -> Path:
    """获取 Wiki 概念目录路径（向后兼容）"""
    return get_settings().wiki_concepts_dir


def get_manifests_dir() -> Path:
    """获取 Manifest 目录路径（向后兼容）"""
    return get_settings().manifests_dir


def get_data_dir() -> Path:
    """获取数据目录路径（向后兼容）"""
    return get_settings().data_dir


def get_progress_file() -> Path:
    """获取进度文件路径（向后兼容）"""
    return get_settings().progress_file


def get_phase2_lock_file() -> Path:
    """获取 Phase 2 锁文件路径（向后兼容）"""
    return get_settings().phase2_lock_file


def get_query_model() -> str:
    """获取查询模型（向后兼容）"""
    return get_settings().query_model


def get_embedding_model() -> str:
    """获取向量嵌入模型（向后兼容）"""
    return get_settings().embedding_model


# ============================================================
# 文件类型常量
# ============================================================

# 文件类型 -> 目标子目录映射
FILE_TYPE_MAP: dict[str, str] = {
    # Documents
    ".pdf": "pdfs",
    ".doc": "pdfs",
    ".docx": "pdfs",
    ".txt": "articles",
    ".html": "articles",
    ".htm": "articles",
    # Books
    ".mobi": "ebooks",
    ".epub": "ebooks",
    # Audio
    ".mp3": "audio",
    ".m4a": "audio",
    ".wav": "audio",
    ".flac": "audio",
    ".aac": "audio",
    ".ogg": "audio",
    # Video
    ".mp4": "videos",
    ".mkv": "videos",
    ".avi": "videos",
    ".mov": "videos",
    ".wmv": "videos",
    # Obsidian / Markdown
    ".md": "articles",
}

# 不处理的文件扩展名
SKIP_EXTENSIONS: set[str] = {
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".deb",
    ".rpm",
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
    ".bz2",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".svg",
    ".webp",
    ".ico",
    ".mpv",
    ".srt",
    ".ass",
    ".vtt",
    ".lrc",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".py",
    ".js",
    ".sh",
    ".bat",
    ".ps1",
}

# 音频文件扩展名
AUDIO_EXTENSIONS: set[str] = {
    ".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".wma", ".opus"
}

# 视频文件扩展名
VIDEO_EXTENSIONS: set[str] = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"
}

# PDF 文件扩展名
PDF_EXTENSIONS: set[str] = {".pdf"}

# 代码文件扩展名
CODE_EXTENSIONS: set[str] = {
    ".py", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rs",
    ".rb", ".cs", ".kt", ".swift", ".lua", ".zig", ".php", ".m", ".mm",
}

# 文档文件扩展名
DOC_EXTENSIONS: set[str] = {".md", ".txt", ".rst", ".html"}

# 电子书文件扩展名
EBOOK_EXTENSIONS: set[str] = {".epub", ".mobi", ".azw3", ".fb2"}


# ============================================================
# 质量评分常量
# ============================================================

# 模板检测扣分
TEMPLATE_DEDUCTION = 20

# 模板检测关键词
TEMPLATE_PATTERNS: list[str] = [
    "这里是一个摘要", "这是一个概括", "summary", "概括", "总结"
]

# 学习价值关键词
LEARNING_KEYWORDS: list[str] = [
    "学习", "提升", "改善", "掌握", "理解", "应用", "运用", "技能", "知识",
    "能力", "经验", "方法", "策略", "技巧", "教训", "重点", "关键", "核心",
    "本质", "规律", "模式", "原理", "机制", "流程", "步骤", "效果", "结果",
    "成果", "优化", "增强", "改进", "提高", "训练", "实践", "实验", "操作",
    "实施", "运用", "使用", "利用",
]

# 信息密度关键词
INFO_KEYWORDS: list[str] = [
    "方法", "策略", "技巧", "经验", "教训", "重点", "关键", "核心",
    "本质", "规律", "模式", "原理", "机制", "流程", "步骤",
]


# ============================================================
# 兼容性别名（旧模块名 → 新模块）
# ============================================================

# 旧代码中 OPENCLAW_CONFIG_PATH 的别名
OPENCLAW_CONFIG_PATH: str = str(Path.home() / ".openclaw/openclaw.json")


# ============================================================
# 文件分类函数
# ============================================================


def get_file_category(ext: str) -> str | None:
    """根据文件扩展名获取分类

    Args:
        ext: 文件扩展名（含点号，如 '.pdf'）

    Returns:
        分类名称，如果不处理则返回 None
    """
    ext = ext.lower()
    if ext in SKIP_EXTENSIONS:
        return None
    return FILE_TYPE_MAP.get(ext, "other")


# ============================================================
# 模块级便捷变量（延迟访问模式）
# ============================================================
# 使用 __getattr__ 实现延迟访问，避免 import 时立即执行
# 这样可以保持向后兼容，同时支持配置动态更新


def __getattr__(name: str) -> Any:
    """延迟获取配置值

    允许以模块级变量形式访问配置，同时支持配置动态更新。
    例如: from dochris.settings import SOURCE_PATH

    Args:
        name: 配置项名称

    Returns:
        配置值

    Raises:
        AttributeError: 配置项不存在时
    """
    settings = get_settings()

    # 路径配置
    if name == "SOURCE_PATH":
        return settings.source_path
    elif name == "OBSIDIAN_PATHS":
        return settings.obsidian_vaults
    elif name == "OBSIDIAN_VAULT":
        return settings.obsidian_vaults[0] if settings.obsidian_vaults else None

    # 日志格式
    elif name == "LOG_FORMAT":
        return settings.log_format
    elif name == "LOG_FORMAT_SIMPLE":
        return settings.log_format_simple
    elif name == "LOG_DATE_FORMAT":
        return settings.log_date_format

    # 编译参数
    elif name == "DEFAULT_API_BASE":
        return settings.api_base
    elif name == "DEFAULT_API_KEY":
        return settings.api_key
    elif name == "DEFAULT_MODEL":
        return settings.model
    elif name == "DEFAULT_CONCURRENCY":
        return settings.max_concurrency
    elif name == "BATCH_SIZE":
        return settings.batch_size
    elif name == "LLM_MAX_TOKENS":
        return settings.llm_max_tokens
    elif name == "LLM_TEMPERATURE":
        return settings.llm_temperature
    elif name == "LLM_TIMEOUT":
        return settings.llm_timeout
    elif name == "LLM_REQUEST_DELAY":
        return settings.llm_request_delay

    # 质量/重试/缓存
    elif name == "MAX_CONTENT_CHARS":
        return settings.max_content_chars
    elif name == "MIN_QUALITY_SCORE":
        return settings.min_quality_score
    elif name == "MIN_TEXT_LENGTH" or name == "MIN_AUDIO_TEXT_LENGTH":
        return settings.min_text_length
    elif name == "MAX_FILE_SIZE":
        return settings.max_file_size
    elif name == "MAX_RETRIES":
        return settings.max_retries
    elif name == "CACHE_RETENTION_DAYS":
        return settings.cache_retention_days
    elif name == "QUERY_MODEL":
        return settings.query_model
    elif name == "EMBEDDING_MODEL":
        return settings.embedding_model

    # OpenRouter
    elif name == "OPENROUTER_API_BASE":
        return settings.openrouter_api_base
    elif name == "OPENROUTER_MODEL":
        return settings.openrouter_model

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def get_default_workspace() -> Path:
    """获取默认工作区路径（向后兼容）"""
    return get_settings().workspace
