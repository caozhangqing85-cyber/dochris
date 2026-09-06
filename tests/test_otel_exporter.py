"""可选 OTel 导出器测试（OBS-02）。"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from dochris.observability.otel_exporter import export_span, otel_enabled, reset_cache
from dochris.observability.tracing import span, trace_request

pytestmark = pytest.mark.fast


@pytest.fixture(autouse=True)
def _reset_otel_cache():
    reset_cache()
    yield
    reset_cache()


def test_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("DOCHRIS_OTEL_ENABLED", raising=False)
    assert otel_enabled() is False
    assert export_span("op", "ab" * 16, "cd" * 8, 1.0, {}) is False


def test_enabled_flag_without_sdk_stays_off(monkeypatch) -> None:
    monkeypatch.setenv("DOCHRIS_OTEL_ENABLED", "true")
    monkeypatch.setitem(sys.modules, "opentelemetry", None)  # 模拟未安装
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk", None)
    reset_cache()
    assert otel_enabled() is False


def test_enabled_with_sdk_exports_span(monkeypatch) -> None:
    monkeypatch.setenv("DOCHRIS_OTEL_ENABLED", "true")
    trace_mock = MagicMock()
    fake_span = MagicMock()
    trace_mock.get_tracer.return_value.start_span.return_value = fake_span
    parent_pkg = MagicMock()
    parent_pkg.trace = trace_mock  # import a.b as x 绑定的是父包属性
    monkeypatch.setitem(sys.modules, "opentelemetry", parent_pkg)
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk", MagicMock())
    monkeypatch.setitem(sys.modules, "opentelemetry.trace", trace_mock)
    reset_cache()

    exported = export_span("query.retrieve", "ab" * 16, "cd" * 8, 12.5, {"top_k": 5})

    assert exported is True
    fake_span.set_attribute.assert_called_once_with("top_k", 5)
    fake_span.end.assert_called_once()


def test_enabled_with_invalid_ids_skips(monkeypatch) -> None:
    monkeypatch.setenv("DOCHRIS_OTEL_ENABLED", "true")
    monkeypatch.setitem(sys.modules, "opentelemetry", MagicMock())
    monkeypatch.setitem(sys.modules, "opentelemetry.sdk", MagicMock())
    monkeypatch.setitem(sys.modules, "opentelemetry.trace", MagicMock())
    reset_cache()

    assert export_span("op", "", "", 1.0) is False
    assert export_span("op", "xyz", "cd" * 8, 1.0) is False  # 非十六进制


def test_trace_span_bridges_to_exporter_on_end(monkeypatch) -> None:
    monkeypatch.delenv("DOCHRIS_OTEL_ENABLED", raising=False)
    with patch(
        "dochris.observability.otel_exporter.export_span", return_value=False
    ) as mock_export:
        with trace_request("trace-1"):
            with span("query.retrieve", top_k=5):
                pass

    mock_export.assert_called_once()
    args = mock_export.call_args[0]
    assert args[0] == "query.retrieve"
    assert args[1] == "trace-1"
    assert args[4] == {"top_k": 5}
