"""补充测试 phase3_query.py — 覆盖 _build_manifest_index 代理"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestBuildManifestIndex:
    """覆盖 _build_manifest_index 代理函数"""

    @patch("dochris.phases.phase3_query.query_utils._build_manifest_index")
    def test_build_manifest_index_restores_path(self, mock_build):
        """_build_manifest_index 调用后恢复原始 MANIFESTS_PATH"""
        mock_build.return_value = {"path1": "SRC-0001"}

        from dochris.phases import phase3_query

        original_path = phase3_query.query_utils.MANIFESTS_PATH

        result = phase3_query._build_manifest_index()

        # 验证恢复了原始路径
        assert phase3_query.query_utils.MANIFESTS_PATH == original_path
        assert result == {"path1": "SRC-0001"}
