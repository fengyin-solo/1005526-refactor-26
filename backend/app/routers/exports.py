"""全量导出管理接口：起服务后一键真跑一遍所有模块的全量导出。

报告逐模块给出 ok/total/文件路径/错误信息：哪个模块坏了一眼可见。
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.exporting.registry import REGISTRY
from app.exporting.runner import run_full_export

router = APIRouter(prefix="/api/exports", tags=["全量导出"])


@router.post("/run")
def run_all(
    only: str | None = Query(default=None, description="逗号分隔的模块名；不传=全部已登记模块"),
) -> dict[str, object]:
    """逐个模块执行全量导出；单模块失败不影响其它模块，失败堆栈随报告返回。"""
    selected = [name.strip() for name in only.split(",") if name.strip()] if only else None
    if selected:
        unknown = [name for name in selected if name not in REGISTRY]
        if unknown:
            return {"ok": False, "failed": len(unknown), "results": [], "unknown_modules": unknown}
    return run_full_export(only=selected)


@router.get("/modules")
def list_modules() -> dict[str, object]:
    """查看已登记的导出模块及其字段口径。"""
    return {
        name: {"label": spec.label, "fields": list(spec.fields)}
        for name, spec in REGISTRY.items()
    }
