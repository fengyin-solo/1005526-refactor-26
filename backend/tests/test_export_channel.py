"""统一导出通道与模块路由的端到端行为测试（基于 FastAPI TestClient）。"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules import exporting
from app.modules.specs import MODULE_NAMES, SPECS
from app.store import store

client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    # 每个用例独立的导出目录与独立的数据状态。
    monkeypatch.setattr(exporting, "EXPORT_DIR", str(tmp_path))
    store.reset()
    yield
    store.reset()


# ---------------------------------------------------------------------------
# 下载入口与列表同源
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", MODULE_NAMES)
def test_export_entry_preserved_and_matches_list(name):
    """老入口 /api/<m>/export 不变；导出条数 == 列表 total；列顺序/空值占位固定。"""
    spec = SPECS[name]

    list_resp = client.get(f"/api/{name}")
    assert list_resp.status_code == 200
    list_payload = list_resp.json()
    assert list_payload["total"] == 3

    export_resp = client.get(f"/api/{name}/export")
    assert export_resp.status_code == 200
    payload = export_resp.json()

    # 历史响应键原样保留，且 items 仍是与列表一致的原始行（含 id/status 等）。
    assert payload["module"] == name
    assert set(["module", "total", "items"]).issubset(payload)
    assert payload["total"] == list_payload["total"] == 3
    assert len(payload["items"]) == 3
    assert payload["matched"] is True
    assert payload["fields"] == list(spec.fields)

    # 投影行（即落盘内容）列顺序与空值占位固定。
    assert len(payload["rows"]) == 3
    for raw_row, proj_row in zip(payload["items"], payload["rows"]):
        assert list(proj_row.keys()) == list(spec.fields)
        assert all(value != "" for value in proj_row.values())
        # 原始行与列表读到的同一份一致。
        assert raw_row[spec.fields[0]] == proj_row[spec.fields[0]]


@pytest.mark.parametrize("name", MODULE_NAMES)
def test_export_follows_same_filters_as_list(name):
    """分页列表与导出共用过滤范围：keyword / status 两者必须一致。"""
    spec = SPECS[name]
    first_code = store.rows(name)[0][spec.keyword_field]
    first_status = store.rows(name)[0]["status"]

    for params in (
        {"keyword": str(first_code)},
        {"status": first_status},
        {"keyword": str(first_code), "status": first_status},
    ):
        listed = client.get(f"/api/{name}", params=params).json()
        exported = client.get(f"/api/{name}/export", params=params).json()
        assert exported["total"] == listed["total"], (name, params)
        assert len(exported["items"]) == listed["total"]
        assert exported["scope"] == {k: v for k, v in params.items()}


def test_export_keyword_no_match_is_empty_not_all():
    """收拢前的 bug：导出忽略 keyword 会返回全量。现在必须是空集。"""
    listed = client.get("/api/pv_array", params={"keyword": "NOT-EXIST"}).json()
    exported = client.get("/api/pv_array/export", params={"keyword": "NOT-EXIST"}).json()
    assert listed["total"] == 0
    assert exported["total"] == 0
    assert exported["items"] == []


def test_export_status_filter_uses_status_field():
    exported = client.get("/api/alarm/export", params={"status": "未确认"}).json()
    assert exported["total"] == 1
    assert exported["items"][0]["告警编号"] == "ALAR-0001"


# ---------------------------------------------------------------------------
# 分页与全量是同一套结果
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", MODULE_NAMES)
def test_paginated_and_full_export_same_source(name):
    pages = []
    page = 1
    while True:
        resp = client.get(f"/api/{name}", params={"page": page, "size": 2}).json()
        pages.extend(resp["items"])
        if page * 2 >= resp["total"]:
            break
        page += 1

    exported = client.get(f"/api/{name}/export").json()
    # 列表逐页拼起来与全量导出是同一批 id（同一数据源同一顺序）。
    assert [row["id"] for row in pages] == [
        store_rows_id(name, i) for i in range(exported["total"])
    ]
    exported_codes = [row[SPECS[name].fields[0]] for row in exported["items"]]
    paged_codes = [row[SPECS[name].fields[0]] for row in pages]
    assert exported_codes == paged_codes


def store_rows_id(name, index):
    return store.rows(name)[index]["id"]


def test_page_size_limit_still_enforced():
    resp = client.get("/api/pv_array", params={"size": 201})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 落盘：覆盖不追加、范围决定文件名
# ---------------------------------------------------------------------------

def test_repeat_export_overwrites_same_file(tmp_path):
    first = client.get("/api/pv_array/export", params={"keyword": "PV_A"}).json()
    path = first["file"]
    with open(path, encoding="utf-8") as handle:
        assert json.load(handle)["total"] == 3

    # 再导一次同范围：同一文件，内容仍为 3 条，不追加。
    second = client.get("/api/pv_array/export", params={"keyword": "PV_A"}).json()
    assert second["file"] == path
    with open(path, encoding="utf-8") as handle:
        body = json.load(handle)
    assert body["total"] == 3
    assert len(body["items"]) == 3
    assert len(list(tmp_path.iterdir())) == 1  # 没有产生第二份文件


def test_different_scopes_get_different_files(tmp_path):
    full = client.get("/api/pv_array/export").json()
    filtered = client.get("/api/pv_array/export", params={"status": "限功率"}).json()
    assert full["file"] != filtered["file"]
    assert filtered["total"] == 1
    assert full["file"].endswith("pv_array.all.json")


def test_csv_export_keeps_header_order_and_placeholder(tmp_path):
    resp = client.get("/api/alarm/export", params={"fmt": "csv"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    text = resp.content.decode("utf-8")
    assert text.startswith("﻿")
    lines = text.lstrip("﻿").splitlines()
    assert lines[0] == ",".join(SPECS["alarm"].fields)
    assert len(lines) == 4  # 表头 + 3 行
    # 同时已按同一份投影落盘
    assert (tmp_path / "alarm.all.csv").exists()
    on_disk = (tmp_path / "alarm.all.csv").read_text(encoding="utf-8")
    assert on_disk == text


def test_unknown_format_rejected():
    resp = client.get("/api/pv_array/export", params={"fmt": "pdf"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 全量批量导出与失败定位
# ---------------------------------------------------------------------------

def test_batch_export_all_modules():
    resp = client.get("/api/exports")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["total_modules"] == 18
    assert payload["succeeded"] == 18
    assert payload["failed"] == 0
    assert payload["total_rows"] == 18 * 3
    assert payload["failures"] == []
    modules = {item["module"] for item in payload["results"]}
    assert modules == set(MODULE_NAMES)


def test_batch_export_subset():
    resp = client.get("/api/exports", params={"modules": "alarm,meter"})
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["total_modules"] == 2
    assert {r["module"] for r in payload["results"]} == {"alarm", "meter"}


def test_batch_export_unknown_module_400():
    resp = client.get("/api/exports", params={"modules": "nope"})
    assert resp.status_code == 400
    assert "nope" in resp.json()["detail"]


def test_batch_export_failure_is_isolated_and_named(monkeypatch):
    """某个模块坏了：批量继续，且结果里能一眼看出是哪个模块、什么错。"""
    from app.modules import exporting as exp

    real = exp.export_module

    def flaky(spec, **kwargs):
        if spec.name == "meter":
            raise RuntimeError("模拟模块损坏")
        return real(spec, **kwargs)

    monkeypatch.setattr(exp, "export_module", flaky)

    resp = client.get("/api/exports")
    payload = resp.json()
    assert resp.status_code == 200
    assert payload["ok"] is False
    assert payload["failed"] == 1
    assert payload["succeeded"] == 17
    assert payload["failures"] == [
        {"module": "meter", "error": "RuntimeError: 模拟模块损坏"}
    ]
    # 其他模块文件仍已落盘
    failed_modules = {f["module"] for f in payload["failures"]}
    assert "meter" in failed_modules
    others = {r["module"] for r in payload["results"]}
    assert "alarm" in others and "meter" not in others


def test_batch_mismatch_is_reported(monkeypatch):
    """通道自检发现条数不一致时按失败处理并点名模块。"""
    from app.modules.exporting import ExportResult

    def fake(spec, **kwargs):
        return ExportResult(
            module=spec.name, scope=kwargs.get("scope") or exp_scope(),
            total=99, items=[], rows=[], fields=list(spec.fields),
            file="/tmp/x", exported_at="now", matched=False,
        )

    def exp_scope():
        from app.modules.exporting import ExportScope
        return ExportScope()

    monkeypatch.setattr("app.modules.exporting.export_module", fake)
    payload = client.get("/api/exports").json()
    assert payload["ok"] is False
    assert payload["failed"] == 18
    assert all("不一致" in f["error"] for f in payload["failures"])


# ---------------------------------------------------------------------------
# 历史行为：动作、登记、明细、文案
# ---------------------------------------------------------------------------

def test_action_flow_and_messages_preserved():
    resp = client.post(
        "/api/pv_array/1/actions", json={"values": {"action": "降功率运行"}}
    )
    body = resp.json()
    assert body["ok"] is True
    assert body["message"] == "光伏阵列已降功率运行"
    assert body["entry"]["status"] == "限功率"

    bad = client.post(
        "/api/pv_array/1/actions", json={"values": {"action": "不存在的动作"}}
    ).json()
    assert bad["ok"] is False
    assert "不属于光伏阵列可执行范围" in bad["message"]


def test_negative_action_marks_abnormal():
    resp = client.post(
        "/api/combiner_box/1/actions", json={"values": {"action": "停用设备"}}
    ).json()
    assert resp["entry"]["abnormal"] is True
    assert resp["entry"]["status"] == "已停用"


def test_create_missing_fields_message():
    resp = client.post("/api/alarm", json={"values": {}}).json()
    assert resp["ok"] is False
    assert resp["message"] == "缺少必填字段：告警编号、告警来源、告警类型"


def test_create_success_message():
    resp = client.post(
        "/api/alarm",
        json={"values": {"告警编号": "ALAR-9", "告警来源": "x", "告警类型": "y"}},
    ).json()
    assert resp["ok"] is True
    assert resp["message"] == "告警事件已登记"
    # 新建后立即可被列表与导出读到（同一份数据）
    assert client.get("/api/alarm/export").json()["total"] == 4


def test_detail_404_message():
    resp = client.get("/api/pv_array/999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "光伏阵列 999 不存在或已归档"


# ---------------------------------------------------------------------------
# 空值占位与既有字段兼容
# ---------------------------------------------------------------------------

def test_projection_empty_values_become_placeholder():
    from app.modules.exporting import projection

    spec = SPECS["meter"]
    row = {name: None for name in spec.fields}
    row[spec.fields[0]] = "METE-0009"
    row[spec.fields[1]] = "   "
    projected = projection(spec, [row])[0]
    assert projected[spec.fields[0]] == "METE-0009"
    assert projected[spec.fields[1]] == "—"
    for name in spec.fields[2:]:
        assert projected[name] == "—"


def test_projection_extra_fields_dropped_and_missing_filled():
    from app.modules.exporting import projection

    spec = SPECS["pv_array"]
    projected = projection(spec, [{"阵列编号": "X", "unknown_field": "dropped"}])[0]
    assert "unknown_field" not in projected
    assert projected["阵列编号"] == "X"
    assert projected["所属片区"] == "—"
    assert list(projected) == list(spec.fields)


def test_original_rows_not_mutated_by_export():
    raw_before = client.get("/api/meter").json()["items"][0]
    client.get("/api/meter/export")
    raw_after = client.get("/api/meter").json()["items"][0]
    # 投影不修改原始行（None 仍是 None，不会被替换成占位符）。
    assert raw_before == raw_after
