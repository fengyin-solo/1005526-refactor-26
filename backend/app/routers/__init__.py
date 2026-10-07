"""业务模块路由汇总。

ROUTERS 复用各模块文件里由 app.modules.router.build_router 生成的同一份路由，
顺序沿用历史的模块顺序；全量批量导出路由放在最后。模块名有可能和内置名撞车
（某个业务模块就叫 dict、list 这种名字时），按名字直接 import 会把内置类型
覆盖掉，函数注解在运行时求值就会报 'module' object is not subscriptable，
因此这里仍然按别名持有各模块模块对象。
"""
from __future__ import annotations

from app.modules.specs import MODULE_NAMES
from app.routers import export_all as router_export_all

# 各业务模块模块对象仍按别名暴露，兼容外部 from app.routers import router_xxx。
from app.routers import pv_array as router_pv_array
from app.routers import inverter as router_inverter
from app.routers import combiner_box as router_combiner_box
from app.routers import transformer as router_transformer
from app.routers import energy_storage as router_energy_storage
from app.routers import boosting_station as router_boosting_station
from app.routers import meter as router_meter
from app.routers import environment as router_environment
from app.routers import cleaning as router_cleaning
from app.routers import patrol as router_patrol
from app.routers import defect as router_defect
from app.routers import maintenance as router_maintenance
from app.routers import spare_parts as router_spare_parts
from app.routers import alarm as router_alarm
from app.routers import dispatch as router_dispatch
from app.routers import safety as router_safety
from app.routers import contract as router_contract
from app.routers import report as router_report

_ROUTER_MODULES = [
    router_pv_array,
    router_inverter,
    router_combiner_box,
    router_transformer,
    router_energy_storage,
    router_boosting_station,
    router_meter,
    router_environment,
    router_cleaning,
    router_patrol,
    router_defect,
    router_maintenance,
    router_spare_parts,
    router_alarm,
    router_dispatch,
    router_safety,
    router_contract,
    router_report,
]

# ROUTERS 仍是"带 .router 属性的模块对象"列表，main.py 按 module.router 挂载。
ROUTERS: list = [*_ROUTER_MODULES, router_export_all]
# 注册顺序与模块注册表同源，做一次一致性兜底，防止漏挂或顺序漂移。
assert [module.router.prefix for module in _ROUTER_MODULES] == [
    f"/api/{name}" for name in MODULE_NAMES
]
