"""Promote 接口测试 — POST /api/v1/promote"""

from unittest.mock import MagicMock, patch


class TestPromoteEndpoint:
    def test_promote_success(self, client):
        with patch("dochris.api.routes.promote.get_manifest") as mock_get, \
             patch("dochris.api.routes.promote.get_settings") as mock_gs, \
             patch("dochris.promote.promote_to_wiki", return_value=True):
            mock_get.return_value = {
                "id": "SRC-0001", "status": "compiled",
                "quality_score": 92, "filename": "test.pdf",
            }
            mock_gs.return_value.workspace = MagicMock()
            resp = client.post("/api/v1/promote/SRC-0001", json={"target": "wiki"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_promote_not_found(self, client):
        with patch("dochris.api.routes.promote.get_manifest", return_value=None), \
             patch("dochris.api.routes.promote.get_settings") as mock_gs:
            mock_gs.return_value.workspace = MagicMock()
            resp = client.post("/api/v1/promote/SRC-9999", json={"target": "wiki"})
        assert resp.status_code == 404

    def test_promote_invalid_target(self, client):
        resp = client.post("/api/v1/promote/SRC-0001", json={"target": "invalid"})
        assert resp.status_code == 400

    def test_promote_failure(self, client):
        with patch("dochris.api.routes.promote.get_manifest") as mock_get, \
             patch("dochris.api.routes.promote.get_settings") as mock_gs, \
             patch("dochris.promote.promote_to_wiki", return_value=False):
            mock_get.return_value = {
                "id": "SRC-0001", "status": "compiled",
                "quality_score": 92, "filename": "test.pdf",
            }
            mock_gs.return_value.workspace = MagicMock()
            resp = client.post("/api/v1/promote/SRC-0001", json={"target": "wiki"})
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    def test_promote_exception(self, client):
        with patch("dochris.api.routes.promote.get_manifest") as mock_get, \
             patch("dochris.api.routes.promote.get_settings") as mock_gs, \
             patch("dochris.promote.promote_to_wiki", side_effect=Exception("db error")):
            mock_get.return_value = {
                "id": "SRC-0001", "status": "compiled",
                "quality_score": 92, "filename": "test.pdf",
            }
            mock_gs.return_value.workspace = MagicMock()
            resp = client.post("/api/v1/promote/SRC-0001", json={"target": "wiki"})
        assert resp.status_code == 500

    def test_promote_to_curated_success(self, client):
        """晋升到 curated 成功"""
        with patch("dochris.api.routes.promote.get_manifest") as mock_get, \
             patch("dochris.api.routes.promote.get_settings") as mock_gs, \
             patch("dochris.promote.promote_to_curated", return_value=True):
            mock_get.return_value = {
                "id": "SRC-0001", "status": "promoted_to_wiki",
                "quality_score": 92, "filename": "test.pdf",
            }
            mock_gs.return_value.workspace = MagicMock()
            resp = client.post("/api/v1/promote/SRC-0001", json={"target": "curated"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["target"] == "curated"

    def test_promote_query_param_target(self, client):
        """通过 query 参数传递 target"""
        with patch("dochris.api.routes.promote.get_manifest") as mock_get, \
             patch("dochris.api.routes.promote.get_settings") as mock_gs, \
             patch("dochris.promote.promote_to_wiki", return_value=True):
            mock_get.return_value = {
                "id": "SRC-0001", "status": "compiled",
                "quality_score": 92, "filename": "test.pdf",
            }
            mock_gs.return_value.workspace = MagicMock()
            # 不发 body，用 query parameter
            resp = client.post("/api/v1/promote/SRC-0001?target=wiki")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_promote_default_target_is_wiki(self, client):
        """无 target 参数时默认晋升到 wiki"""
        with patch("dochris.api.routes.promote.get_manifest") as mock_get, \
             patch("dochris.api.routes.promote.get_settings") as mock_gs, \
             patch("dochris.promote.promote_to_wiki", return_value=True):
            mock_get.return_value = {
                "id": "SRC-0001", "status": "compiled",
                "quality_score": 92, "filename": "test.pdf",
            }
            mock_gs.return_value.workspace = MagicMock()
            resp = client.post("/api/v1/promote/SRC-0001")
        assert resp.status_code == 200
        assert resp.json()["target"] == "wiki"
