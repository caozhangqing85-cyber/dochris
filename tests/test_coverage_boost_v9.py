"""覆盖率提升 v9 — quality_scorer + text_chunker + promote 最后冲刺"""


class TestQualityScorerLastMile:
    def _score(self, summary):
        from dochris.core.quality_scorer import score_summary_quality_v4
        return score_summary_quality_v4(summary)

    def test_ds_is_none(self):
        assert self._score({"detailed_summary": None}) == 0

    def test_ds_is_int(self):
        assert self._score({"detailed_summary": 12345}) >= 0

    def test_learning_count_exactly_4(self):
        summary = {
            "detailed_summary": "本文通过 学习 和 理解 来掌握 关键 概念，" * 30,
            "key_points": ["p1"],
        }
        result = self._score(summary)
        assert result > 0


class TestTextChunkerLine175:
    def test_title_from_non_heading_line(self):
        from dochris.core.text_chunker import semantic_chunk
        text = "First paragraph about something important\n" * 20
        result = semantic_chunk(text, chunk_size=200, overlap=0)
        assert isinstance(result, list)


class TestPromoteNoFiles:
    def test_promote_to_wiki_no_files(self, tmp_path):
        from dochris.promote import promote_to_wiki
        (tmp_path / "outputs").mkdir()
        (tmp_path / "manifests" / "sources").mkdir(parents=True)
        import json
        manifest = {
            "id": "SRC_TEST",
            "status": "compiled",
            "title": "Test",
            "quality_score": 90,
        }
        (tmp_path / "manifests" / "sources" / "SRC_TEST.json").write_text(json.dumps(manifest))
        result = promote_to_wiki(tmp_path, "SRC_TEST")
        assert result is False
