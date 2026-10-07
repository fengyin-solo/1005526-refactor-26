"""导出端点工厂：所有模块的 GET /api/<模块>/export 都由这里生成。

- URL、按钮入口、method 与切换前完全一致，只是背后的实现收拢到了公共通道；
- keyword/status 与列表接口同参同口径，默认全量；传 page/size 时按同一口径
  导出当前页（分页导出与全量导出是同一个函数，结果不可能对不上）；
- 默认返回 CSV 文件下载；?format=json 保留切换前的老 JSON 响应。
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.exporting.pipeline import export_module
from app.exporting.registry import get_spec


def build_export_router(module: str) -> APIRouter:
    """生成模块导出子路由。由模块 router 在 /{entry_id} 之前挂载，
    避免「export」被当成 entry_id 的影子路由（切换前的 422 老 bug）。
    """
    spec = get_spec(module)
    router = APIRouter()

    @router.get("/export", include_in_schema=False)
    def export_entries(
        keyword: str | None = Query(default=None, description=f"按{spec.keyword_field}检索，与列表同参"),
        status: str | None = Query(default=None, description="状态过滤，取值与列表接口一致"),
        page: int | None = Query(default=None, ge=1, description="不传=全量导出；传则导出该页"),
        size: int = Query(default=200, ge=1, description="分页导出时每页条数，上限 200"),
        format: str = Query(default="csv", description="csv=文件下载（默认）；json=老结构响应"),
    ) -> Any:
        fmt = format.lower()
        if fmt not in ("csv", "json"):
            raise HTTPException(status_code=400, detail="format 仅支持 csv 或 json")
        if size > 200:
            raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")

        try:
            result = export_module(
                module,
                keyword=keyword,
                status=status,
                fmt=fmt,
                page=page,
                size=size,
            )
        except KeyError as exc:
            # 未登记模块/服务属于装配错误，不应以 500 暴露给下载入口
            raise HTTPException(status_code=503, detail=str(exc).strip("'")) from None

        if fmt == "json":
            payload: dict[str, Any] = {
                "module": result.module,
                "total": result.total,
                "items": result.items,
            }
            if page is not None:  # 老结构没有分页字段，仅在分页导出时补充
                payload["page"] = page
                payload["size"] = size
            return payload

        download_name = result.path.name if result.path else f"export_{module}.csv"
        return Response(
            content=result.extra["content"],
            media_type="text/csv; charset=utf-8",
            headers={
                # filename* 给中文模块名；ASCII 回退名与落盘文件同名，重复下载只覆盖
                "Content-Disposition": (
                    f"attachment; filename={download_name}; "
                    f"filename*=UTF-8''{quote(f'{spec.label}清单.csv')}"
                ),
                "X-Export-Module": module,
                "X-Export-Total": str(result.total),
                "X-Export-Count": str(len(result.items)),
            },
        )

    return router
