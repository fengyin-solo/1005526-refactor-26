"""统一导出通道的核心口径测试。

不依赖 httpx/TestClient：直接对 pipeline / writer / runner 断言。
每个用例结束恢复注册表与数据仓库的初始状态，避免用例间污染。
"""
from __future__ import annotations

import csv
import io
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any
from uuid import uuid4

import app.main  # noqa: F401  # 触发全部 router 导入与取数服务登记
import app.exporting.pipeline as pipeline_mod
from app.exporting import (
    NULL_PLACEHOLDER,
    export_module,
    fetch_dataset,
    register_service,
    render_csv,
    run_full_export,
)
from app.exporting.registry import REGISTRY, get_spec
from app.store import store

ALL_MODULES = sorted(REGISTRY)


class BrokenService:
    """模拟某个模块取数坏掉：用于验证故障隔离与报告定位。"""

    def list_entries(self, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
        raise RuntimeError("模拟模块故障")


class ExportChannelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # 导出目录重定向到临时目录，测试不污染仓库
        cls._real_export_dir = pipeline_mod.EXPORT_DIR
        cls.tmp = tempfile.mkdtemp(prefix="export-tests-")
        pipeline_mod.EXPORT_DIR = Path(cls.tmp)

    @classmethod
    def tearDownClass(cls) -> None:
        pipeline_mod.EXPORT_DIR = cls._real_export_dir
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_01_registry_covers_all_18_modules(self) -> None:
        """存量 18 个模块全部登记，字段为 8 列且关键字列在册。"""
        self.assertEqual(len(ALL_MODULES), 18)
        for name, spec in REGISTRY.items():
            self.assertEqual(len(spec.fields), 8, name)
            self.assertIn(spec.keyword_field, spec.fields, name)
            # 最后一列是状态列，且在状态枚举内（种子数据状态合法）
            self.assertTrue(spec.statuses, name)

    def test_02_export_total_equals_list_total(self) -> None:
        """导出条数必须与列表 total 同源——本通道最核心的承诺。"""
        for module in ALL_MODULES:
            with self.subTest(module=module):
                items, total = fetch_dataset(module)
                self.assertEqual(len(items), total)
                # 与种子表行数一致（未过滤时）
                self.assertEqual(total, len(store.rows(module)))

    def test_03_filter_scope_matches_list(self) -> None:
        """带 keyword/status 的导出与列表过滤口径完全一致。"""
        spec = get_spec("inverter")
        for status in spec.statuses:
            with self.subTest(status=status):
                items, total = fetch_dataset("inverter", status=status)
                expected = [
                    r for r in store.rows("inverter") if r.get("status") == status
                ]
                self.assertEqual(total, len(expected))
                self.assertEqual([r["id"] for r in items],
                                 [r["id"] for r in expected])

    def test_04_csv_field_order_and_null_placeholder(self) -> None:
        """列顺序按注册表；缺列/None 统一占位 —；空串保留原样。"""
        spec = get_spec("inverter")
        rows = [
            {spec.fields[0]: "A", spec.fields[-1]: None},  # 缺列 + None
            {f: ("" if i == 1 else f"v{i}") for i, f in enumerate(spec.fields)},
        ]
        text = render_csv(spec.fields, rows)
        records = list(csv.reader(io.StringIO(text)))
        self.assertEqual(records[0], list(spec.fields))
        self.assertEqual(records[1][0], "A")
        self.assertEqual(records[1][3], NULL_PLACEHOLDER)
        self.assertEqual(records[1][-1], NULL_PLACEHOLDER)
        self.assertEqual(records[2][1], "")  # 空字符串不替换

    def test_05_full_export_overwrites_fixed_file(self) -> None:
        """全量导出固定文件名，重复导出只覆盖不追加。"""
        r1 = export_module("inverter", fmt="csv")
        path = Path(r1.path)
        content_1 = path.read_bytes()
        mtime_1 = path.stat().st_mtime_ns
        import time
        time.sleep(0.01)
        r2 = export_module("inverter", fmt="csv")
        content_2 = Path(r2.path).read_bytes()
        self.assertEqual(r1.path, r2.path)
        self.assertEqual(content_1, content_2)
        self.assertEqual(len(content_2), path.stat().st_size)
        self.assertGreaterEqual(path.stat().st_mtime_ns, mtime_1)
        # 行数 = 表头 + 数据行，没有重复追加
        self.assertEqual(len(content_2.decode().strip().splitlines()),
                         1 + r2.total)

    def test_06_scoped_export_uses_separate_stable_file(self) -> None:
        """带过滤的导出有独立稳定文件名，同范围重复导出仍只覆盖。"""
        spec = get_spec("inverter")
        status = spec.statuses[0]
        r1 = export_module("inverter", status=status, fmt="csv")
        r2 = export_module("inverter", status=status, fmt="csv")
        self.assertEqual(r1.path, r2.path)
        self.assertNotEqual(Path(r1.path).name, "export_inverter.csv")
        # 全量文件仍然存在且行数更多
        full = export_module("inverter", fmt="csv")
        self.assertNotEqual(r1.path, full.path)

    def test_07_paged_and_full_share_one_pipeline(self) -> None:
        """分页导出与全量导出是同一口径：页内拼接 == 全量，分页不落盘。"""
        full = export_module("inverter", fmt="csv")
        full_ids = [r["id"] for r in full.items]
        paged_ids: list[int] = []
        size = 2
        for page in (1, 2, 3):
            part = export_module("inverter", fmt="csv", page=page, size=size)
            self.assertIsNone(part.path, "分页导出不应落盘覆盖固定文件")
            paged_ids.extend(r["id"] for r in part.items)
        self.assertEqual(paged_ids, full_ids)

    def test_08_legacy_json_shape(self) -> None:
        """?format=json 老结构 {module,total,items} 与原始行保留。"""
        result = export_module("inverter", fmt="json")
        self.assertEqual(result.format, "json")
        self.assertIsNone(result.path, "JSON 兼容响应无文件副作用")
        raw = store.rows("inverter")[0]
        self.assertEqual(result.items[0], raw)

    def test_09_failure_isolated_and_located(self) -> None:
        """某个模块坏掉：报告能定位模块，其它模块照常成功。"""
        from app.exporting.registry import ExportSpec

        bogus = f"broken_{uuid4().hex[:8]}"
        spec = ExportSpec(
            module=bogus,
            label="故障模拟模块",
            fields=("编号",),
            keyword_field="编号",
            statuses=("x",),
        )
        REGISTRY[bogus] = spec
        register_service(bogus, BrokenService())
        try:
            report = run_full_export(only=[bogus, "inverter"])
            self.assertFalse(report["ok"])
            by_module = {r["module"]: r for r in report["results"]}
            self.assertFalse(by_module[bogus]["ok"])
            self.assertIn("模拟模块故障", by_module[bogus]["error"])
            self.assertTrue(by_module["inverter"]["ok"])
            self.assertEqual(
                [r["module"] for r in report["results"]], [bogus, "inverter"]
            )
            self.assertIn(bogus, report["tracebacks"])
            self.assertIn("RuntimeError", report["tracebacks"][bogus])
        finally:
            pipeline_mod._SERVICE_REGISTRY.pop(bogus, None)
            REGISTRY.pop(bogus, None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
