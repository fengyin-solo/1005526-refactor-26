"""模块路由工厂：按 ModuleSpec 生成列表/明细/登记/动作/导出五个接口。

18 个业务模块的路由此前是逐字复制的 18 份，唯一差异是模块常量与中文文案；
现在由工厂统一生成，下载入口（GET /api/<模块>/export）与路径、出入参保持不变。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response

from app.config import settings
from app.modules.base import get_service
from app.modules.exporting import ExportScope, export_module, render_csv
from app.modules.specs import ModuleSpec
from app.schemas import ActionResult, EntryPayload, PageResult


def build_router(spec: ModuleSpec) -> APIRouter:
    """为一个模块生成与历史行为一致的 APIRouter。"""

    router = APIRouter(prefix=spec.prefix, tags=[spec.tag])
    service = get_service(spec.name)
    # 老页面/脚本可能直接 import 这两个常量，继续在模块层暴露。
    router.LIST_FIELDS = list(spec.fields)  # type: ignore[attr-defined]
    router.STATUSES = list(spec.statuses)  # type: ignore[attr-defined]

    status_hint = "、".join(spec.statuses)

    @router.get("", response_model=PageResult[dict])
    def list_entries(
        keyword: str | None = Query(default=None, description=f"按{spec.keyword_field}检索"),
        status: str | None = Query(default=None, description=status_hint),
        page: int = 1,
        size: int = 20,
    ) -> PageResult[dict]:
        """按关键字与状态过滤列表；没有数据时返回空页，不报错。"""
        if size > settings.page_size_max:
            raise HTTPException(
                status_code=400,
                detail=f"每页最多 {settings.page_size_max} 条，请缩小分页范围",
            )
        items, total = service.list_entries(
            keyword=keyword, status=status, page=page, size=size
        )
        return PageResult(items=items, total=total, page=page, size=size)

    @router.get("/export")
    def export_entries(
        keyword: str | None = Query(default=None, description=f"按{spec.keyword_field}检索"),
        status: str | None = Query(default=None, description=status_hint),
        fmt: str = Query(default="json", description="导出格式：json 或 csv"),
    ) -> Any:
        """导出清单：与列表共用同一取数口径，支持与列表相同的过滤条件。

        - fmt=json（默认）：历史响应，module/total/items 原样保留，过滤条件现在
          会生效，保证导出条数与列表 total 一致；
        - fmt=csv：返回可下载的 CSV 文件（UTF-8 BOM），列顺序与空值占位固定。
        两种格式落盘的都是同一份投影数据，重复导出覆盖同名文件。
        """
        if fmt not in ("json", "csv"):
            raise HTTPException(status_code=400, detail="导出格式仅支持 json 或 csv")
        result = export_module(
            spec, scope=ExportScope(keyword=keyword, status=status), fmt=fmt
        )
        if fmt == "csv":
            filename = f"{spec.name}.csv"
            return Response(
                content=render_csv(spec, result.rows),
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        return result.to_payload()

    @router.get("/{entry_id}", response_model=dict)
    def get_entry(entry_id: int) -> dict:
        """读取单条明细；不存在时给出可读的错误说明。"""
        entry = service.get_entry(entry_id)
        if entry is None:
            raise HTTPException(
                status_code=404, detail=f"{spec.entity} {entry_id} 不存在或已归档"
            )
        return entry

    @router.post("", response_model=ActionResult)
    def create_entry(payload: EntryPayload) -> ActionResult:
        """登记一条记录，缺字段时说明原因而不是静默丢弃。"""
        entry, missing = service.create_entry(payload.values)
        if missing:
            return ActionResult(
                ok=False, message=f"缺少必填字段：{'、'.join(missing)}"
            )
        return ActionResult(
            ok=True, message=f"{spec.created}已登记", entry=entry
        )

    @router.post("/{entry_id}/actions", response_model=ActionResult)
    def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
        """对单条记录执行模块允许的动作；不允许的动作会被拦下并说明原因。"""
        action = str(payload.values.get("action") or "").strip()
        entry, message = service.run_action(entry_id, action)
        if entry is None:
            return ActionResult(ok=False, message=message)
        return ActionResult(ok=True, message=message, entry=entry)

    return router
