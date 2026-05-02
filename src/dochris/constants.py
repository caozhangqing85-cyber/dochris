"""Dochris 全局常量

本模块统一管理项目中分散的魔法数字和字符串。
注意：现有代码仍在使用 settings.py，迁移常量引用是独立的任务。
"""

from pathlib import Path

# ============================================================
# 项目信息
# ============================================================

PROJECT_NAME = "dochris"
PROJECT_VERSION = "1.3.1"
PROJECT_AUTHOR = "caozhangqing85-cyber"
REPO_URL = "https://github.com/caozhangqing85-cyber/dochris"

# ============================================================
# 默认配置
# ============================================================

# LLM API 配置
DEFAULT_API_BASE = "https://open.bigmodel.cn/api/paas/v4"
DEFAULT_MODEL = "glm-5.1"
DEFAULT_QUERY_MODEL = "glm-4-flash"
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"

# 并发与批处理
DEFAULT_MAX_CONCURRENCY = 3
DEFAULT_BATCH_SIZE = 10

# 质量评分
DEFAULT_QUALITY_THRESHOLD = 85

# 日志
DEFAULT_LOG_LEVEL = "INFO"

# ============================================================
# 文件处理
# ============================================================

# 文件大小限制
MAX_FILE_SIZE_MB = 500  # 500MB
MAX_CONTENT_CHARS = 20000

# 支持的文件扩展名（按类型分类）
SUPPORTED_EXTENSIONS = {
    # 文档
    ".txt",
    ".md",
    ".pdf",
    ".docx",
    ".doc",
    ".html",
    ".htm",
    ".rst",
    # 音频
    ".wav",
    ".mp3",
    ".m4a",
    ".flac",
    ".aac",
    ".ogg",
    ".wma",
    ".opus",
    # 视频
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
    # 电子书
    ".mobi",
    ".epub",
    ".azw3",
    ".fb2",
    # 图片
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".svg",
    ".webp",
    ".ico",
}

AUDIO_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".flac",
    ".aac",
    ".ogg",
    ".wma",
    ".opus",
}

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
}

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".svg",
    ".webp",
    ".ico",
}

DOCUMENT_EXTENSIONS = {
    ".txt",
    ".md",
    ".pdf",
    ".docx",
    ".doc",
    ".html",
    ".htm",
    ".rst",
}

EBOOK_EXTENSIONS = {
    ".mobi",
    ".epub",
    ".azw3",
    ".fb2",
}

CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".java",
    ".c",
    ".cpp",
    ".go",
    ".rs",
    ".rb",
    ".cs",
    ".kt",
    ".swift",
    ".lua",
    ".zig",
    ".php",
    ".m",
    ".mm",
}

# 跳过的文件扩展名（不处理）
SKIP_EXTENSIONS = {
    # 可执行文件
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".deb",
    ".rpm",
    # 压缩文件
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
    ".bz2",
    # 字幕文件
    ".srt",
    ".ass",
    ".vtt",
    ".lrc",
    # 配置文件
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
}

# ============================================================
# 质量评分
# ============================================================

QUALITY_EXCELLENT = 90
QUALITY_GOOD = 80
QUALITY_PASS = 70
QUALITY_THRESHOLD = 85

# 模板检测扣分
TEMPLATE_DEDUCTION = 20

# 模板检测关键词
TEMPLATE_PATTERNS = [
    "这里是一个摘要",
    "这是一个概括",
    "summary",
    "概括",
    "总结",
]

# 学习价值关键词
LEARNING_KEYWORDS = [
    "学习",
    "提升",
    "改善",
    "掌握",
    "理解",
    "应用",
    "运用",
    "技能",
    "知识",
    "能力",
    "经验",
    "方法",
    "策略",
    "技巧",
    "教训",
    "重点",
    "关键",
    "核心",
    "本质",
    "规律",
    "模式",
    "原理",
    "机制",
    "流程",
    "步骤",
    "效果",
    "结果",
    "成果",
    "优化",
    "增强",
    "改进",
    "提高",
    "训练",
    "实践",
    "实验",
    "操作",
    "实施",
    "使用",
    "利用",
]

# 信息密度关键词
INFO_KEYWORDS = [
    "方法",
    "策略",
    "技巧",
    "经验",
    "教训",
    "重点",
    "关键",
    "核心",
    "本质",
    "规律",
    "模式",
    "原理",
    "机制",
    "流程",
    "步骤",
]

# ============================================================
# 目录结构
# ============================================================

DIR_DATA = "data"
DIR_RAW = "raw"
DIR_OUTPUTS = "outputs"
DIR_WIKI = "wiki"
DIR_CURATED = "curated"
DIR_LOCKED = "locked"
DIR_MANIFESTS = "manifests"
DIR_LOGS = "logs"
DIR_CACHE = "cache"

# 子目录
DIR_SUMMARIES = "summaries"
DIR_CONCEPTS = "concepts"
DIR_PROMOTED = "promoted"

# 文件类型映射（扩展名 -> 子目录）
FILE_TYPE_MAP: dict[str, str] = {
    # 文档
    ".pdf": "pdfs",
    ".doc": "pdfs",
    ".docx": "pdfs",
    ".txt": "articles",
    ".html": "articles",
    ".htm": "articles",
    # 电子书
    ".mobi": "ebooks",
    ".epub": "ebooks",
    # 音频
    ".mp3": "audio",
    ".m4a": "audio",
    ".wav": "audio",
    ".flac": "audio",
    ".aac": "audio",
    ".ogg": "audio",
    # 视频
    ".mp4": "videos",
    ".mkv": "videos",
    ".avi": "videos",
    ".mov": "videos",
    ".wmv": "videos",
    # Markdown
    ".md": "articles",
}

# ============================================================
# LLM 参数
# ============================================================

LLM_MAX_TOKENS = 40000
LLM_TEMPERATURE = 0.1
LLM_TIMEOUT = 300.0  # 秒
LLM_REQUEST_DELAY = 5.0  # 秒

# ============================================================
# 重试策略
# ============================================================

MAX_RETRIES = 3
RETRY_INITIAL_DELAY_429 = 20.0  # 429 错误初始延迟
RETRY_INITIAL_DELAY_CONNECTION = 15.0  # 连接错误初始延迟
RETRY_INITIAL_DELAY_GENERAL = 10.0  # 一般错误初始延迟
RETRY_MAX_DELAY = 60.0  # 最大等待时间
RETRY_BACKOFF_FACTOR = 2  # 指数退避因子

# ============================================================
# 分层摘要限制
# ============================================================

MAX_HIERARCHICAL_CHARS = 100000  # 10 万字
MAX_CHUNKS = 50

# ============================================================
# 缓存配置
# ============================================================

CACHE_RETENTION_DAYS = 30
MIN_TEXT_LENGTH = 100  # 文本最小长度（判断是否有意义）

# ============================================================
# 路径常量
# ============================================================

DEFAULT_WORKSPACE = Path.home() / ".knowledge-base"
OPENCLAW_CONFIG_PATH = Path.home() / ".openclaw/openclaw.json"

# ============================================================
# OpenRouter 备用配置
# ============================================================

OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "qwen/qwen-2.5-72b-instruct:free"

# ============================================================
# 本地 LLM 默认配置（Ollama 等）
# ============================================================

LOCAL_LLM_DEFAULT_BASE_URL = "http://localhost:11434/v1"
LOCAL_LLM_DEFAULT_MODEL = "qwen:14b"
LOCAL_LLM_DEFAULT_API_KEY = "ollama"
