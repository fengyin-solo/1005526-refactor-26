"""关口计量业务规则：状态流转、字段校验与筛选口径都收在这里。

实现已收拢到 app.modules 公共通道：字段口径见 app.modules.specs，列表取数与
状态流转见 app.modules.base，导出见 app.modules.exporting。本文件只保留与
模块同名的 service 类，供旧引用方继续使用。
"""
from __future__ import annotations

from app.modules.base import ModuleService
from app.modules.specs import get_spec

# 模块内常量保留只读引用，兼容历史 import 路径。
SPEC = get_spec("meter")
MODULE = SPEC.name
REQUIRED_FIELDS = list(SPEC.required)
STATUS_ORDER = list(SPEC.statuses)
ACTION_RULES = dict(SPEC.actions)
NEGATIVE_ACTIONS = list(SPEC.negative_actions)


class MeterService(ModuleService):
    """meter 模块 service：行为完全由 SPEC 驱动。"""

    def __init__(self) -> None:
        super().__init__(get_spec("meter"))
