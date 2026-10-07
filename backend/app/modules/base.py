"""通用业务 service：所有模块共用一套列表取数与状态流转实现。

模块之间的差异只体现在 ModuleSpec 的常量上；这里不再允许各模块各写一份
筛选/分页逻辑，从根上消除"导出条数与列表总数对不上"的可能。
"""
from __future__ import annotations

from typing import Any

from app.modules.specs import ModuleSpec
from app.store import store


class ModuleService:
    """按 ModuleSpec 驱动的通用 service，行为与历史各模块 service 一致。"""

    def __init__(self, spec: ModuleSpec) -> None:
        self.spec = spec

    # -- 取数范围：列表与导出唯一共用的口径 --------------------------------

    def query_rows(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """按关键字与状态圈定本模块的数据范围，不做分页。

        列表接口在其结果上分页，导出接口取全量；两者范围完全一致。
        """
        rows = store.rows(self.spec.name)
        if keyword:
            key_field = self.spec.keyword_field
            rows = [row for row in rows if keyword in str(row.get(key_field, ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        return rows

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """分页列表：total 是过滤后的总数，items 是同一范围上的一页。"""
        rows = self.query_rows(keyword=keyword, status=status)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    # -- 明细 / 登记 / 动作 -------------------------------------------------

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(self.spec.name, entry_id)

    def create_entry(
        self, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [
            field_name
            for field_name in self.spec.required
            if not str(values.get(field_name) or "").strip()
        ]
        if missing:
            return None, missing
        rows = store.rows(self.spec.name)
        entry: dict[str, Any] = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1
        }
        entry.update({field_name: values.get(field_name) for field_name in self.spec.required})
        entry["status"] = self.spec.statuses[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(
        self, entry_id: int, action: str
    ) -> tuple[dict[str, Any] | None, str]:
        spec = self.spec
        entry = store.find(spec.name, entry_id)
        if entry is None:
            return None, f"{spec.entity} {entry_id} 不存在或已归档"
        if action not in spec.actions:
            return None, f"动作「{action}」不属于{spec.tag}可执行范围"
        target = spec.actions[action]
        if target not in spec.statuses:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != spec.statuses[-1]
        entry["abnormal"] = action in spec.negative_actions
        return entry, f"{spec.entity}已{action}"


# 各模块 service 单例：路由层仍然按"一个模块一个 service 实例"使用。
_SERVICES: dict[str, ModuleService] = {}


def get_service(name: str) -> ModuleService:
    from app.modules.specs import get_spec

    if name not in _SERVICES:
        _SERVICES[name] = ModuleService(get_spec(name))
    return _SERVICES[name]
