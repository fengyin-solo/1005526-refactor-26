"""告警事件接口：路由由 app.modules.router.build_router 统一生成。

历史路径（含 GET /api/alarm/export 下载入口）与出入参保持不变；字段口径、
取数范围与导出实现统一维护在 app.modules，不再在本文件各写一份。
"""
from __future__ import annotations

from app.modules.router import build_router
from app.modules.specs import get_spec
from app.services.alarm import AlarmService

SPEC = get_spec("alarm")
# 兼容历史常量导入。
LIST_FIELDS = list(SPEC.fields)
STATUSES = list(SPEC.statuses)
service = AlarmService()

router = build_router(SPEC)
