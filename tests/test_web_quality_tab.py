"""Web 质量仪表盘 Tab 测试"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from dochris.web.quality_tab import (
    _get_low_quality_table,
    _get_quality_dashboard,
    _get_quality_distribution_df,
    handle_refresh_quality,
)


def _mock_manifests():
    """生成模拟 manifest 数据"""
    return [
        {
            "id": "SRC-0001",
            "original_filename": "优秀.pdf",
            "type": "pdf",
            "status": "compiled",
            "quality_score": 95,
        },
        {
            "id": "SRC-0002",
            "original_filename": "良好.pdf",
            "type": "pdf",
            "status": "compiled",
            "quality_score": 75,
        },
        {
            "id": "SRC-0003",
            "original_filename": "较差.pdf",
            "type": "audio",
            "status": "compiled",
            "quality_score": 30,
        },
        {
            "id": "SRC-0004",
            "original_filename": "低分.pdf",
            "type": "pdf",
            "status": "compiled",
            "quality_score": 15,
        },
        {
            "id": "SRC-0005",
            "original_filename": "未评分.txt",
            "type": "other",
            "status": "ingested",
            "quality_score": 0,
        },
        {
            "id": "SRC-0006",
            "original_filename": "满分.pdf",
            "type": "pdf",
            "status": "compiled",
            "quality_score": 100,
        },
    ]


# ── _get_quality_dashboard ─────────────────────────────────────


class TestGetQualityDashboard:
    """质量仪表盘数据"""

    @patch("dochris.web.quality_tab.get_manifest_data")
    @patch("dochris.web.quality_tab.get_settings")
    def test_empty_manifests(self, mock_settings, mock_data):
        """空 manifest 显示提示"""
        mock_data.return_value = ([], {}, {})
        mock_settings.return_value = MagicMock(min_quality_score=85)
        result = _get_quality_dashboard()
        assert "暂无质量评分数据" in result

    @patch("dochris.web.quality_tab.get_manifest_data")
    @patch("dochris.web.quality_tab.get_settings")
    def test_shows_overview(self, mock_settings, mock_data):
        """显示质量概览"""
        mock_data.return_value = (_mock_manifests(), {}, {})
        mock_settings.return_value = MagicMock(min_quality_score=85)
        result = _get_quality_dashboard()
        assert "质量概览" in result
        assert "已评分文件数" in result
        assert "平均分" in result

    @patch("dochris.web.quality_tab.get_manifest_data")
    @patch("dochris.web.quality_tab.get_settings")
    def test_shows_distribution(self, mock_settings, mock_data):
        """显示质量分布"""
        mock_data.return_value = (_mock_manifests(), {}, {})
        mock_settings.return_value = MagicMock(min_quality_score=85)
        result = _get_quality_dashboard()
        assert "质量分布" in result
        assert "0-20" in result
        assert "81-100" in result

    @patch("dochris.web.quality_tab.get_manifest_data")
    @patch("dochris.web.quality_tab.get_settings")
    def test_shows_low_quality_list(self, mock_settings, mock_data):
        """显示未达标文件列表"""
        mock_data.return_value = (_mock_manifests(), {}, {})
        mock_settings.return_value = MagicMock(min_quality_score=85)
        result = _get_quality_dashboard()
        assert "未达标文件" in result
        assert "较差.pdf" in result

    @patch("dochris.web.quality_tab.get_manifest_data")
    @patch("dochris.web.quality_tab.get_settings")
    def test_rating_green(self, mock_settings, mock_data):
        """平均分 >= 80 时评级为绿色"""
        manifests = [
            {
                "id": "SRC-0001",
                "original_filename": "a.pdf",
                "type": "pdf",
                "status": "compiled",
                "quality_score": 90,
            },
            {
                "id": "SRC-0002",
                "original_filename": "b.pdf",
                "type": "pdf",
                "status": "compiled",
                "quality_score": 85,
            },
        ]
        mock_data.return_value = (manifests, {}, {})
        mock_settings.return_value = MagicMock(min_quality_score=85)
        result = _get_quality_dashboard()
        assert "🟢" in result

    @patch("dochris.web.quality_tab.get_manifest_data")
    @patch("dochris.web.quality_tab.get_settings")
    def test_rating_yellow(self, mock_settings, mock_data):
        """平均分 60-80 时评级为黄色"""
        manifests = [
            {
                "id": "SRC-0001",
                "original_filename": "a.pdf",
                "type": "pdf",
                "status": "compiled",
                "quality_score": 70,
            },
        ]
        mock_data.return_value = (manifests, {}, {})
        mock_settings.return_value = MagicMock(min_quality_score=85)
        result = _get_quality_dashboard()
        assert "🟡" in result

    @patch("dochris.web.quality_tab.get_manifest_data")
    @patch("dochris.web.quality_tab.get_settings")
    def test_rating_red(self, mock_settings, mock_data):
        """平均分 < 60 时评级为红色"""
        manifests = [
            {
                "id": "SRC-0001",
                "original_filename": "a.pdf",
                "type": "pdf",
                "status": "compiled",
                "quality_score": 30,
            },
        ]
        mock_data.return_value = (manifests, {}, {})
        mock_settings.return_value = MagicMock(min_quality_score=85)
        result = _get_quality_dashboard()
        assert "🔴" in result


# ── _get_quality_distribution_df ───────────────────────────────


class TestGetQualityDistributionDf:
    """质量评分分布 DataFrame"""

    @patch("dochris.web.quality_tab.get_manifest_data")
    def test_empty_data(self, mock_data):
        """无评分数据返回占位 DataFrame"""
        mock_data.return_value = ([], {}, {})
        df = _get_quality_distribution_df()
        assert isinstance(df, pd.DataFrame)
        assert "暂无数据" in df.iloc[0]["分数段"]

    @patch("dochris.web.quality_tab.get_manifest_data")
    def test_buckets(self, mock_data):
        """评分分到正确的桶"""
        mock_data.return_value = (_mock_manifests(), {}, {})
        df = _get_quality_distribution_df()
        assert isinstance(df, pd.DataFrame)
        assert "分数段" in df.columns
        assert "文件数" in df.columns
        # 应该有 5 个桶
        assert len(df) == 5


# ── _get_low_quality_table ─────────────────────────────────────


class TestGetLowQualityTable:
    """低质量文件列表"""

    @patch("dochris.web.quality_tab.get_manifest_data")
    @patch("dochris.web.quality_tab.get_settings")
    def test_empty(self, mock_settings, mock_data):
        """无低质量文件"""
        mock_data.return_value = ([], {}, {})
        mock_settings.return_value = MagicMock(min_quality_score=85)
        rows = _get_low_quality_table()
        assert rows == []

    @patch("dochris.web.quality_tab.get_manifest_data")
    @patch("dochris.web.quality_tab.get_settings")
    def test_filters_below_threshold(self, mock_settings, mock_data):
        """只返回低于阈值的文件"""
        mock_data.return_value = (_mock_manifests(), {}, {})
        mock_settings.return_value = MagicMock(min_quality_score=85)
        rows = _get_low_quality_table()
        manifest_ids = [r[0] for r in rows]
        assert "SRC-0001" not in manifest_ids  # 95 >= 85
        assert "SRC-0006" not in manifest_ids  # 100 >= 85
        assert "SRC-0002" in manifest_ids  # 75 < 85

    @patch("dochris.web.quality_tab.get_manifest_data")
    @patch("dochris.web.quality_tab.get_settings")
    def test_row_limit_100(self, mock_settings, mock_data):
        """最多返回 100 行"""
        manifests = [
            {
                "id": f"SRC-{i:04d}",
                "original_filename": f"low{i}.pdf",
                "type": "pdf",
                "status": "compiled",
                "quality_score": 10,
            }
            for i in range(200)
        ]
        mock_data.return_value = (manifests, {}, {})
        mock_settings.return_value = MagicMock(min_quality_score=85)
        rows = _get_low_quality_table()
        assert len(rows) == 100


# ── handle_refresh_quality ─────────────────────────────────────


class TestHandleRefreshQuality:
    """刷新质量仪表盘"""

    @patch("dochris.web.quality_tab._get_quality_dashboard")
    def test_returns_dashboard(self, mock_dash):
        """返回仪表盘内容"""
        mock_dash.return_value = "质量概览\n..."
        result = handle_refresh_quality()
        assert result == "质量概览\n..."

    @patch("dochris.web.quality_tab._get_quality_dashboard")
    def test_handles_error(self, mock_dash):
        """异常时返回错误信息"""
        mock_dash.side_effect = RuntimeError("db error")
        result = handle_refresh_quality()
        assert "获取质量数据失败" in result
