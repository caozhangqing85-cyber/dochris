#!/usr/bin/env python3
"""
配置常量
包含所有默认常量定义
"""

import os
from pathlib import Path

# ============================================================
# 默认 API 配置
# ============================================================

DEFAULT_LLM_API_BASE = "https://open.bigmodel.cn/api/paas/v4"
"""默认 LLM API Base URL（智谱通用 API）"""

CODING_LLM_API_BASE = "https://open.bigmodel.cn/api/coding/paas/v4"
"""智谱 GLM Coding Plan 专属 API 端点"""

OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
"""OpenRouter 备用 API Base URL"""

OPENROUTER_MODEL = "qwen/qwen-2.5-72b-instruct:free"
"""OpenRouter 备用模型"""

DEFAULT_API_KEY = ""
"""默认 API 密钥（空字符串）"""

DEFAULT_MODEL = "glm-5.1"
"""默认 LLM 模型"""

# ============================================================
# 质量评分常量
# ============================================================

QUALITY_THRESHOLD = 85
"""默认质量评分阈值"""

MIN_QUALITY_SCORE = 85
"""最低质量分数（通过门槛）"""

# 模板检测扣分
TEMPLATE_DEDUCTION = 20

# 模板检测关键词
TEMPLATE_PATTERNS: list[str] = ["这里是一个摘要", "这是一个概括", "summary", "概括", "总结"]

# 学习价值关键词
LEARNING_KEYWORDS: list[str] = [
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

# 信息密度关键词（与 LEARNING_KEYWORDS 无重叠）
INFO_KEYWORDS: list[str] = [
    "工具",
    "框架",
    "API",
    "SDK",
    "算法",
    "架构",
    "协议",
    "数据库",
    "缓存",
    "容器",
    "微服务",
    "中间件",
    "配置",
    "部署",
    "监控",
]

# ============================================================
# 默认并发配置
# ============================================================

DEFAULT_CONCURRENCY = 3
"""默认最大并发数"""

BATCH_SIZE = 10
"""批处理大小"""

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
AUDIO_EXTENSIONS: set[str] = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".wma", ".opus"}

# 视频文件扩展名
VIDEO_EXTENSIONS: set[str] = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"}

# PDF 文件扩展名
PDF_EXTENSIONS: set[str] = {".pdf"}

# 代码文件扩展名
CODE_EXTENSIONS: set[str] = {
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

# 文档文件扩展名
DOC_EXTENSIONS: set[str] = {".md", ".txt", ".rst", ".html"}

# 电子书文件扩展名
EBOOK_EXTENSIONS: set[str] = {".epub", ".mobi", ".azw3", ".fb2"}

# ============================================================
# 兼容性别名（旧模块名 → 新模块）
# ============================================================

# 旧代码中 OPENCLAW_CONFIG_PATH 的别名
OPENCLAW_CONFIG_PATH: str = os.environ.get(
    "OPENCLAW_CONFIG_PATH", str(Path.home() / ".openclaw/openclaw.json")
)
