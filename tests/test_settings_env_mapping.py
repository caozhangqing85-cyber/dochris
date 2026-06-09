#!/usr/bin/env python3
"""测试 Settings._env_mapping 自动映射机制

覆盖：
- _load_env_fields() 从环境变量正确读取
- 类型转换器（int）正常工作
- 默认值在环境变量缺失时使用
- 新增 RAG 配置项（reranker/observability/chunk）默认关闭
- from_env() 正确合并 _load_env_fields() 结果
"""

import os
from unittest import TestCase
from unittest.mock import patch


class TestEnvMappingMechanism(TestCase):
    """测试 _env_mapping 自动映射"""

    def test_load_env_fields_returns_mapping_fields(self) -> None:
        """_load_env_fields() 返回 _env_mapping 中定义的所有字段"""
        from dochris.settings.config import Settings

        fields = Settings._load_env_fields()
        # 核心字段应存在
        self.assertIn("model", fields)
        self.assertIn("llm_provider", fields)
        self.assertIn("vector_store", fields)
        self.assertIn("log_level", fields)

    def test_load_env_fields_with_custom_env(self) -> None:
        """环境变量覆盖默认值"""
        from dochris.settings.config import Settings

        with patch.dict(os.environ, {"MODEL": "custom-model", "LOG_LEVEL": "DEBUG"}):
            fields = Settings._load_env_fields()
            self.assertEqual(fields["model"], "custom-model")
            self.assertEqual(fields["log_level"], "DEBUG")

    def test_load_env_fields_default_values(self) -> None:
        """环境变量缺失时使用默认值"""
        from dochris.settings.config import Settings

        # 清除可能的环境变量
        env_to_clear = ["MODEL", "LOG_LEVEL", "MAX_CONCURRENCY"]
        with patch.dict(os.environ, {}, clear=False):
            for key in env_to_clear:
                os.environ.pop(key, None)
            fields = Settings._load_env_fields()
            self.assertEqual(fields["model"], "glm-5.1")
            self.assertEqual(fields["log_level"], "INFO")

    def test_int_converter(self) -> None:
        """int 转换器正确工作"""
        from dochris.settings.config import Settings

        with patch.dict(os.environ, {"MAX_CONCURRENCY": "10", "MIN_QUALITY_SCORE": "85"}):
            fields = Settings._load_env_fields()
            self.assertEqual(fields["max_concurrency"], 10)
            self.assertEqual(fields["min_quality_score"], 85)
            self.assertIsInstance(fields["max_concurrency"], int)

    def test_int_converter_fallback_on_invalid(self) -> None:
        """int 转换失败时使用默认值"""
        from dochris.settings.config import Settings

        with patch.dict(os.environ, {"MAX_CONCURRENCY": "not-a-number"}):
            fields = Settings._load_env_fields()
            # 应回退到默认值
            self.assertEqual(fields["max_concurrency"], "3")


class TestRAGConfigDefaults(TestCase):
    """测试 RAG 改进方案配置项默认关闭"""

    def test_reranker_disabled_by_default(self) -> None:
        """Reranker 默认关闭"""
        from dochris.settings.config import Settings

        settings = Settings()
        self.assertEqual(settings.reranker_enabled, "false")
        self.assertEqual(settings.reranker_provider, "bge")
        self.assertEqual(settings.reranker_model, "BAAI/bge-reranker-base")

    def test_observability_disabled_by_default(self) -> None:
        """可观测性默认关闭"""
        from dochris.settings.config import Settings

        settings = Settings()
        self.assertEqual(settings.observability_enabled, "false")
        self.assertEqual(settings.prometheus_enabled, "false")

    def test_chunk_strategy_default(self) -> None:
        """分块策略默认为 structure"""
        from dochris.settings.config import Settings

        settings = Settings()
        self.assertEqual(settings.chunk_strategy, "structure")
        self.assertEqual(settings.index_raw_chunks, "false")

    def test_reranker_enabled_via_env(self) -> None:
        """通过环境变量启用 Reranker"""
        from dochris.settings.config import Settings

        with patch.dict(os.environ, {"RERANKER_ENABLED": "true"}):
            fields = Settings._load_env_fields()
            self.assertEqual(fields["reranker_enabled"], "true")

    def test_chunk_strategy_via_env(self) -> None:
        """通过环境变量切换分块策略"""
        from dochris.settings.config import Settings

        with patch.dict(os.environ, {"CHUNK_STRATEGY": "semantic"}):
            fields = Settings._load_env_fields()
            self.assertEqual(fields["chunk_strategy"], "semantic")

    def test_all_rag_fields_in_mapping(self) -> None:
        """所有 RAG 配置项都在 _env_mapping 中注册"""
        from dochris.settings.config import Settings

        rag_fields = [
            "reranker_enabled",
            "reranker_provider",
            "reranker_model",
            "observability_enabled",
            "prometheus_enabled",
            "chunk_strategy",
            "index_raw_chunks",
        ]
        for field_name in rag_fields:
            self.assertIn(
                field_name,
                Settings._env_mapping,
                f"RAG 配置项 {field_name} 未在 _env_mapping 中注册",
            )


class TestFromEnvIntegration(TestCase):
    """测试 from_env() 正确合并 _load_env_fields()"""

    def test_from_env_includes_mapping_fields(self) -> None:
        """from_env() 返回的实例包含 _env_mapping 中的字段"""
        from dochris.settings.config import Settings

        with patch("dochris.settings.config.load_dotenv"):
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
                settings = Settings.from_env()
                # _env_mapping 字段应有默认值
                self.assertEqual(settings.model, "glm-5.1")
                self.assertEqual(settings.vector_store, "chromadb")
                # RAG 配置项默认关闭
                self.assertEqual(settings.reranker_enabled, "false")
                self.assertEqual(settings.observability_enabled, "false")

    def test_from_env_env_overrides_mapping(self) -> None:
        """from_env() 中环境变量覆盖 _env_mapping 默认值"""
        from dochris.settings.config import Settings

        with patch("dochris.settings.config.load_dotenv"):
            with patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "test-key",
                    "MODEL": "custom-model",
                    "RERANKER_ENABLED": "true",
                },
            ):
                settings = Settings.from_env()
                self.assertEqual(settings.model, "custom-model")
                self.assertEqual(settings.reranker_enabled, "true")
