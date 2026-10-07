"""全量批量导出接口：一条通道把所有模块各导出一份，并点名失败模块。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.modules.exporting import batch_export_all
from app.modules.specs import MODULE_NAMES, SPECS

router = APIRouter(prefix="/api/exports", tags=["全量导出"])


@router.get("")
def export_all(
    modules: str | None = Query(
        default=None, description="逗号分隔的模块名；缺省导出全部模块"
    ),
    fmt: str = Query(default="json", description="导出格式：json 或 csv"),
) -> dict[str, Any]:
    """跑一遍全量导出。

    成功返回 ok=True 与每个模块的落盘文件；某个模块失败时 ok=False 并在
    failures 里给出模块名与原因，其余模块的结果照常返回。
    """
    if fmt not in ("json", "csv"):
        raise HTTPException(status_code=400, detail="导出格式仅支持 json 或 csv")

    only: list[str] | None = None
    if modules:
        only = [part.strip() for part in modules.split(",") if part.strip()]
        unknown = [name for name in only if name not in SPECS]
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"未知模块：{'、'.join(unknown)}；可选：{'、'.join(MODULE_NAMES)}",
            )

    report = batch_export_all(only=only, fmt=fmt)
    return report.to_payload()
