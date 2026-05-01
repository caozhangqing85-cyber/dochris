"""测试 settings 模块: constants + env + file_category"""

import os
from pathlib import Path
from unittest.mock import patch

from dochris.settings.constants import (
    AUDIO_EXTENSIONS,
    BATCH_SIZE,
    CODE_EXTENSIONS,
    DEFAULT_CONCURRENCY,
    DEFAULT_LLM_API_BASE,
    DEFAULT_MODEL,
    DOC_EXTENSIONS,
    EBOOK_EXTENSIONS,
    FILE_TYPE_MAP,
    INFO_KEYWORDS,
    LEARNING_KEYWORDS,
    MIN_QUALITY_SCORE,
    OPENROUTER_API_BASE,
    OPENROUTER_MODEL,
    PDF_EXTENSIONS,
    QUALITY_THRESHOLD,
    SKIP_EXTENSIONS,
    TEMPLATE_DEDUCTION,
    TEMPLATE_PATTERNS,
    VIDEO_EXTENSIONS,
)
from dochris.settings.env import (
    get_env_bool,
    get_env_int,
    get_env_list,
    get_env_path,
    get_env_str,
)
from dochris.settings.file_category import get_file_category

# ---- constants ----


class TestConstants:
    def test_default_model(self):
        assert DEFAULT_MODEL == "glm-5.1"

    def test_default_api_base(self):
        assert "bigmodel.cn" in DEFAULT_LLM_API_BASE

    def test_quality_threshold(self):
        assert QUALITY_THRESHOLD == 85
        assert MIN_QUALITY_SCORE == 85

    def test_template_deduction(self):
        assert TEMPLATE_DEDUCTION == 20

    def test_template_patterns_not_empty(self):
        assert len(TEMPLATE_PATTERNS) > 0

    def test_learning_keywords_not_empty(self):
        assert len(LEARNING_KEYWORDS) > 0

    def test_info_keywords_not_empty(self):
        assert len(INFO_KEYWORDS) > 0

    def test_concurrency(self):
        assert DEFAULT_CONCURRENCY == 3
        assert BATCH_SIZE == 10

    def test_file_type_map_pdf(self):
        assert FILE_TYPE_MAP[".pdf"] == "pdfs"

    def test_file_type_map_txt(self):
        assert FILE_TYPE_MAP[".txt"] == "articles"

    def test_file_type_map_mp3(self):
        assert FILE_TYPE_MAP[".mp3"] == "audio"

    def test_file_type_map_mp4(self):
        assert FILE_TYPE_MAP[".mp4"] == "videos"

    def test_skip_extensions_exe(self):
        assert ".exe" in SKIP_EXTENSIONS

    def test_audio_extensions(self):
        assert ".mp3" in AUDIO_EXTENSIONS
        assert ".wav" in AUDIO_EXTENSIONS

    def test_video_extensions(self):
        assert ".mp4" in VIDEO_EXTENSIONS
        assert ".mkv" in VIDEO_EXTENSIONS

    def test_pdf_extensions(self):
        assert ".pdf" in PDF_EXTENSIONS

    def test_code_extensions(self):
        assert ".py" in CODE_EXTENSIONS
        assert ".js" in CODE_EXTENSIONS

    def test_doc_extensions(self):
        assert ".md" in DOC_EXTENSIONS
        assert ".txt" in DOC_EXTENSIONS

    def test_ebook_extensions(self):
        assert ".epub" in EBOOK_EXTENSIONS

    def test_openrouter_constants(self):
        assert "openrouter.ai" in OPENROUTER_API_BASE
        assert "qwen" in OPENROUTER_MODEL


# ---- env ----


class TestGetEnvPath:
    def test_returns_path_from_env(self):
        with patch.dict(os.environ, {"TEST_PATH": "/tmp/test"}):
            result = get_env_path("TEST_PATH")
            assert result == Path("/tmp/test")

    def test_returns_default_when_unset(self):
        result = get_env_path("NONEXISTENT_VAR_XYZ", default=Path("/default"))
        assert result == Path("/default")

    def test_returns_none_when_unset_no_default(self):
        result = get_env_path("NONEXISTENT_VAR_XYZ")
        assert result is None

    def test_expands_user(self):
        with patch.dict(os.environ, {"TEST_HOME": "~/dir"}):
            result = get_env_path("TEST_HOME")
            assert "~" not in str(result)


class TestGetEnvStr:
    def test_returns_value(self):
        with patch.dict(os.environ, {"TEST_STR": "hello"}):
            assert get_env_str("TEST_STR") == "hello"

    def test_returns_default(self):
        assert get_env_str("NONEXISTENT_VAR_XYZ", "def") == "def"

    def test_empty_default(self):
        assert get_env_str("NONEXISTENT_VAR_XYZ") == ""


class TestGetEnvInt:
    def test_returns_int(self):
        with patch.dict(os.environ, {"TEST_INT": "42"}):
            assert get_env_int("TEST_INT") == 42

    def test_returns_default_when_unset(self):
        assert get_env_int("NONEXISTENT_VAR_XYZ", 10) == 10

    def test_returns_default_on_invalid(self):
        with patch.dict(os.environ, {"TEST_BAD_INT": "not_a_number"}):
            assert get_env_int("TEST_BAD_INT", 5) == 5

    def test_default_zero(self):
        assert get_env_int("NONEXISTENT_VAR_XYZ") == 0


class TestGetEnvBool:
    def test_true_values(self):
        for val in ("1", "true", "yes", "on"):
            with patch.dict(os.environ, {"TEST_BOOL": val}):
                assert get_env_bool("TEST_BOOL") is True

    def test_false_values(self):
        for val in ("0", "false", "no", "off"):
            with patch.dict(os.environ, {"TEST_BOOL": val}):
                assert get_env_bool("TEST_BOOL") is False

    def test_default_when_unset(self):
        assert get_env_bool("NONEXISTENT_VAR_XYZ") is False
        assert get_env_bool("NONEXISTENT_VAR_XYZ", default=True) is True

    def test_case_insensitive(self):
        with patch.dict(os.environ, {"TEST_BOOL": "TRUE"}):
            assert get_env_bool("TEST_BOOL") is True


class TestGetEnvList:
    def test_parses_comma_separated(self):
        with patch.dict(os.environ, {"TEST_LIST": "a,b,c"}):
            result = get_env_list("TEST_LIST")
            assert result == ["a", "b", "c"]

    def test_strips_whitespace(self):
        with patch.dict(os.environ, {"TEST_LIST": "a , b , c"}):
            result = get_env_list("TEST_LIST")
            assert result == ["a", "b", "c"]

    def test_custom_separator(self):
        with patch.dict(os.environ, {"TEST_LIST": "a|b"}):
            result = get_env_list("TEST_LIST", separator="|")
            assert result == ["a", "b"]

    def test_returns_default_when_unset(self):
        assert get_env_list("NONEXISTENT_VAR_XYZ") == []
        assert get_env_list("NONEXISTENT_VAR_XYZ", default=["x"]) == ["x"]

    def test_empty_string_returns_default(self):
        with patch.dict(os.environ, {"TEST_LIST": ""}):
            # 空字符串经过 split 会得到 [''] 但 strip 过滤掉空项
            result = get_env_list("TEST_LIST")
            assert result == []


# ---- file_category ----


class TestGetFileCategory:
    def test_pdf(self):
        assert get_file_category(".pdf") == "pdfs"

    def test_mp3(self):
        assert get_file_category(".mp3") == "audio"

    def test_mp4(self):
        assert get_file_category(".mp4") == "videos"

    def test_md(self):
        assert get_file_category(".md") == "articles"

    def test_skip_extension(self):
        assert get_file_category(".exe") is None
        assert get_file_category(".json") is None

    def test_unknown_extension(self):
        assert get_file_category(".xyz") == "other"

    def test_case_insensitive(self):
        assert get_file_category(".PDF") == "pdfs"
        assert get_file_category(".Mp3") == "audio"

    def test_epub(self):
        assert get_file_category(".epub") == "ebooks"
