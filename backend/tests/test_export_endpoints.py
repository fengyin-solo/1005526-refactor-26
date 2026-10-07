"""导出端点 HTTP 行为测试：下载入口、过滤参数与老影子路由 bug。"""
from __future__ import annotations

import unittest

from app.exporting.registry import REGISTRY

try:
    from fastapi.testclient import TestClient

    from app.main import app

    CLIENT_AVAILABLE = True
except Exception:  # 缺少 httpx 等测试依赖时跳过本文件
    CLIENT_AVAILABLE = False


@unittest.skipUnless(CLIENT_AVAILABLE, "需要安装 requirements-dev.txt 中的 httpx")
class ExportEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_export_url_still_resolves(self) -> None:
        """切换前后下载入口完全一致：GET /api/<模块>/export 不再 422。"""
        for module in REGISTRY:
            with self.subTest(module=module):
                resp = self.client.get(f"/api/{module}/export")
                self.assertEqual(resp.status_code, 200, resp.content[:200])
                self.assertIn("attachment", resp.headers["content-disposition"])

    def test_csv_headers_and_total_header(self) -> None:
        list_resp = self.client.get("/api/inverter")
        total = list_resp.json()["total"]
        resp = self.client.get("/api/inverter/export")
        self.assertEqual(int(resp.headers["x-export-total"]), total)
        self.assertEqual(int(resp.headers["x-export-count"]), total)
        self.assertTrue(resp.content.startswith(b"\xef\xbb\xbf"))  # UTF-8 BOM

    def test_filtered_export_matches_filtered_list(self) -> None:
        status = "正常运行"
        list_resp = self.client.get("/api/inverter", params={"status": status})
        total = list_resp.json()["total"]
        resp = self.client.get("/api/inverter/export", params={"status": status})
        self.assertEqual(int(resp.headers["x-export-total"]), total)
        body_lines = resp.content.decode("utf-8-sig").strip().splitlines()
        self.assertEqual(len(body_lines) - 1, total)  # 去表头

    def test_paged_export_same_pipeline(self) -> None:
        resp = self.client.get(
            "/api/inverter/export", params={"page": 1, "size": 2}
        )
        self.assertEqual(resp.status_code, 200)
        body_lines = resp.content.decode("utf-8-sig").strip().splitlines()
        self.assertEqual(len(body_lines) - 1, 2)
        # total 仍是全量计数，count 是本页条数
        self.assertEqual(int(resp.headers["x-export-count"]), 2)
        self.assertGreaterEqual(int(resp.headers["x-export-total"]), 2)

    def test_legacy_json_shape(self) -> None:
        resp = self.client.get("/api/inverter/export", params={"format": "json"})
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(set(payload.keys()), {"module", "total", "items"})
        self.assertEqual(payload["module"], "inverter")

    def test_full_export_run_reports_each_module(self) -> None:
        resp = self.client.post("/api/exports/run")
        self.assertEqual(resp.status_code, 200)
        report = resp.json()
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["total_modules"], 18)
        self.assertEqual(report["failed"], 0)
        for item in report["results"]:
            self.assertTrue(item["ok"], item)
            self.assertTrue(item["path"].endswith(f"export_{item['module']}.csv"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
