"""业务模块公共层：口径注册表、通用列表查询与统一导出通道。"""
from __future__ import annotations

from app.modules.base import ModuleService, get_service
from app.modules.exporting import (
    ExportResult,
    batch_export_all,
    export_module,
    projection,
)
from app.modules.specs import EMPTY_PLACEHOLDER, MODULE_NAMES, SPECS, ModuleSpec, get_spec

__all__ = [
    "EMPTY_PLACEHOLDER",
    "MODULE_NAMES",
    "SPECS",
    "ModuleSpec",
    "get_spec",
    "ModuleService",
    "get_service",
    "ExportResult",
    "batch_export_all",
    "export_module",
    "projection",
]
