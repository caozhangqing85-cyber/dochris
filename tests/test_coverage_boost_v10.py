"""覆盖率提升 v10 — 最后 2 行冲刺"""




class TestMonitorWorkerSaveReport:
    """覆盖 monitor_worker.py line 93"""

    def test_save_report_default_path(self, tmp_path):
        from dochris.workers.monitor_worker import MonitorWorker
        mw = MonitorWorker()
        mw.workspace = tmp_path
        mw.save_report()  # 不传 report_path，触发默认路径逻辑
        # 检查文件是否创建
        reports = list((tmp_path / "monitoring-reports").glob("compile_report_*.json"))
        assert len(reports) == 1


class TestTextChunkerLine175:
    """覆盖 text_chunker.py line 175 — 标题正则不匹配时取行前50字符"""

    def test_no_heading_detected(self):
        from dochris.core.text_chunker import semantic_chunk
        # 使用纯文本，没有 markdown 标题
        text = "\n".join([f"This is paragraph number {i} with some content." for i in range(50)])
        result = semantic_chunk(text, chunk_size=200, overlap=0)
        assert isinstance(result, list)
        assert len(result) > 0
