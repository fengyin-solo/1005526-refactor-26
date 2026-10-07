"""统一导出通道。

所有业务模块的导出都走这里：模块只在 registry 里登记字段口径、在 services 里
登记取数服务，导出端点由 build_export_route 统一生成。设计约束：

- 导出与列表读同一份数据：都调用同一个 service.list_entries，过滤参数完全一致，
  导出只是不分页；
- 字段口径（列顺序、空值占位）只认 registry，老的 JSON 结构继续保留；
- 文件落盘固定文件名，重复导出只覆盖不追加。
"""
from __future__ import annotations

from app.exporting.pipeline import (
    ExportResult,
    export_module,
    fetch_dataset,
    register_service,
)
from app.exporting.runner import ModuleRunResult, run_full_export
from app.exporting.writer import NULL_PLACEHOLDER, project_row, render_csv

__all__ = [
    "ExportResult",
    "ModuleRunResult",
    "NULL_PLACEHOLDER",
    "export_module",
    "fetch_dataset",
    "project_row",
    "register_service",
    "render_csv",
    "run_full_export",
]
