"""全量导出编排：逐模块走同一条公共通道。

任何一个模块坏掉都不影响其它模块——单模块异常被捕获并记录，调用方拿到的
报告里直接能看出“是哪个模块坏了、坏在哪”，最后以 ok 汇总成败。
"""
from __future__ import annotations

import time
import traceback
from dataclasses import asdict, dataclass, field
from typing import Any

from app.exporting.pipeline import export_module, registered_modules
from app.exporting.registry import REGISTRY


@dataclass
class ModuleRunResult:
    module: str
    label: str
    ok: bool
    total: int = 0
    path: str | None = None
    error: str | None = None
    elapsed_ms: int = 0
    traceback_text: str | None = field(default=None, repr=False)


def run_full_export(*, only: list[str] | None = None) -> dict[str, Any]:
    """对已登记模块逐个执行全量导出，返回可直接序列化的汇总报告。"""
    modules = only if only else registered_modules()
    results: list[ModuleRunResult] = []
    for module in modules:
        label = REGISTRY[module].label if module in REGISTRY else module
        started = time.monotonic()
        try:
            result = export_module(module, fmt="csv")
            results.append(
                ModuleRunResult(
                    module=module,
                    label=result.label,
                    ok=True,
                    total=result.total,
                    path=str(result.path) if result.path else None,
                    elapsed_ms=int((time.monotonic() - started) * 1000),
                )
            )
        except Exception as exc:  # 单模块故障隔离：继续跑完其余模块
            results.append(
                ModuleRunResult(
                    module=module,
                    label=label,
                    ok=False,
                    error=f"{type(exc).__name__}: {exc}",
                    elapsed_ms=int((time.monotonic() - started) * 1000),
                    traceback_text=traceback.format_exc(),
                )
            )

    ok_modules = [r for r in results if r.ok]
    failed = [r for r in results if not r.ok]
    return {
        "ok": not failed,
        "total_modules": len(results),
        "succeeded": len(ok_modules),
        "failed": len(failed),
        "total_rows": sum(r.total for r in ok_modules),
        "results": [
            {k: v for k, v in asdict(r).items() if k != "traceback_text"}
            for r in results
        ],
        # 堆栈单独放：列表用于快速定位坏模块，需要细节时再看这里。
        "tracebacks": {
            r.module: r.traceback_text for r in failed if r.traceback_text
        },
    }
