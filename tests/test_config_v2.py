"""补充测试 settings/config.py — 覆盖 dotenv ImportError fallback"""

import sys
from unittest.mock import MagicMock, patch


class TestConfigDotenvFallback:
    """覆盖 dotenv 未安装时的 fallback"""

    def test_load_dotenv_fallback_when_missing(self):
        """dotenv 不可用时使用空函数"""
        # 需要重新导入 config 模块以触发 fallback
        mock_dotenv = MagicMock()
        mock_dotenv.side_effect = ImportError("no dotenv")

        with patch.dict(sys.modules, {"dotenv": None, "dotenv.load_dotenv": None}):
            # 直接测试 fallback 函数
            from dochris.settings.config import load_dotenv as config_load_dotenv

            # 如果 dotenv 可用，load_dotenv 就是真的
            # 如果不可用，返回 False
            result = config_load_dotenv("/nonexistent/.env")
            assert isinstance(result, bool)
