"""统一导出通道。

各模块只声明"取数范围"（keyword/status），字段口径来自 ModuleSpec，
取数复用 ModuleService.query_rows —— 与列表接口读到的是同一份数据、同一套
过滤顺序，分页导出与全量导出不再可能各出一套结果。

落盘规则：同一模块、同一范围（含全量）永远写到同一个文件名，重复导出只覆盖、
不追加；批量导出时单个模块失败会被隔离并在结果里点名，不影响其余模块。
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from app.config import settings
from app.modules.base import get_service
from app.modules.specs import EMPTY_PLACEHOLDER, MODULE_NAMES, ModuleSpec

# 导出文件落盘目录，可用环境变量覆盖。
EXPORT_DIR = settings.export_dir

# 投影后一行的类型：字段 -> 字符串值（空值统一为占位符）。
ProjectedRow = dict[str, str]


@dataclass(frozen=True)
class ExportScope:
    """一次导出的取数范围，也是去重/覆盖的依据。"""

    keyword: str | None = None
    status: str | None = None

    def params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self.keyword:
            params["keyword"] = self.keyword
        if self.status:
            params["status"] = self.status
        return params

    def fingerprint(self) -> str:
        """同一范围指纹相同；全量（无任何条件）固定为 all。"""
        params = self.params()
        if not params:
            return "all"
        raw = json.dumps(params, ensure_ascii=False, sort_keys=True)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def projection(spec: ModuleSpec, rows: list[dict[str, Any]]) -> list[ProjectedRow]:
    """按统一字段口径把原始行投影成导出行。

    - 字段集合与顺序一律以 spec.fields 为准（即历史导出列顺序，不动）；
    - None / 空串 / 纯空白 统一落到 EMPTY_PLACEHOLDER，与列表页占位一致；
    - 兼容既有字段：行里多出的字段不进导出，行里缺失的字段补占位符；
    - 原始行不会被修改，列表与详情仍可读到原值。
    """
    projected: list[ProjectedRow] = []
    for row in rows:
        projected.append(
            {
                name: (
                    EMPTY_PLACEHOLDER
                    if _is_empty(row.get(name))
                    else str(row.get(name))
                )
                for name in spec.fields
            }
        )
    return projected


def render_csv(spec: ModuleSpec, rows: list[ProjectedRow]) -> str:
    """渲染为带 BOM 的 UTF-8 CSV，表头顺序即 spec.fields。"""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(spec.fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    # UTF-8 BOM，保证 Excel 直接打开中文不乱码。
    return "\ufeff" + buffer.getvalue()


def _file_stem(spec: ModuleSpec, scope: ExportScope) -> str:
    return f"{spec.name}.{scope.fingerprint()}"


@dataclass
class ExportResult:
    """单次导出结果。

    items 保持为历史 /export 返回的原始行（含 id/status 等，老消费方不受影响）；
    rows 是按统一字段口径投影后的导出行（列顺序与空值占位固定），也是落盘内容。
    """

    module: str
    scope: ExportScope
    total: int
    items: list[dict[str, Any]]
    """原始行：与历史 /export 响应、列表读到的数据完全一致。"""

    rows: list[ProjectedRow]
    """投影后的导出行（列顺序与空值占位固定），即文件内容。"""

    fields: list[str]
    file: str
    """落盘文件的绝对路径；同一范围重复导出指向同一文件。"""

    exported_at: str
    matched: bool = True
    """导出条数是否与列表 total 一致；正常恒为 True，False 说明通道异常。"""

    error: str | None = None

    def to_payload(self) -> dict[str, Any]:
        """老 /export 入口的响应体：原有键 module/total/items 原样保留，
        新增键只追加不改语义。"""
        return {
            "module": self.module,
            "total": self.total,
            "items": self.items,
            "fields": self.fields,
            "rows": self.rows,
            "scope": self.scope.params(),
            "file": self.file,
            "exported_at": self.exported_at,
            "matched": self.matched,
        }


def export_module(
    spec: ModuleSpec,
    *,
    scope: ExportScope | None = None,
    fmt: str = "json",
    write: Callable[[str, str], None] | None = None,
) -> ExportResult:
    """导出单个模块：取数、投影、渲染、落盘覆盖一条龙。

    write 可注入用于测试；默认原子写盘（先写临时文件再替换），保证读到的文件
    永远是一份完整结果，重复导出覆盖同名文件而不是追加。
    """
    scope = scope or ExportScope()
    service = get_service(spec.name)

    # 与列表接口完全相同的取数范围；rows 即列表会读到的同一批原始行。
    rows = service.query_rows(keyword=scope.keyword, status=scope.status)
    projected = projection(spec, rows)

    # 自检：列表分页口径下的 total 必须等于导出条数。
    _, list_total = service.list_entries(
        keyword=scope.keyword,
        status=scope.status,
        page=1,
        size=settings.page_size_default,
    )
    matched = list_total == len(projected)

    exported_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    stem = _file_stem(spec, scope)
    ext = "csv" if fmt == "csv" else "json"
    path = os.path.join(EXPORT_DIR, f"{stem}.{ext}")

    if fmt == "csv":
        body = render_csv(spec, projected)
    else:
        body = json.dumps(
            {
                "module": spec.name,
                "scope": scope.params(),
                "total": len(projected),
                "fields": list(spec.fields),
                "exported_at": exported_at,
                "items": projected,
            },
            ensure_ascii=False,
            indent=2,
        )

    writer = write or _atomic_write
    writer(path, body)

    return ExportResult(
        module=spec.name,
        scope=scope,
        total=len(projected),
        items=rows,
        rows=projected,
        fields=list(spec.fields),
        file=path,
        exported_at=exported_at,
        matched=matched,
    )


def _atomic_write(path: str, body: str) -> None:
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="") as handle:
        handle.write(body)
    os.replace(tmp_path, path)


@dataclass
class BatchReport:
    """全量批量导出的汇总报告，失败模块会被逐个点名。"""

    ok: bool
    total_modules: int
    succeeded: int
    failed: int
    total_rows: int
    results: list[ExportResult] = field(default_factory=list)
    failures: list[dict[str, str]] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "total_modules": self.total_modules,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "total_rows": self.total_rows,
            "results": [result.to_payload() for result in self.results],
            "failures": self.failures,
        }


def batch_export_all(
    *,
    only: list[str] | None = None,
    fmt: str = "json",
) -> BatchReport:
    """对全部（或指定）模块跑一遍全量导出。

    每个模块独立 try：某个模块坏了只记录到 failures（带模块名与原因），
    其余模块照常落盘，最后用 ok=False 汇总，方便一眼看出是谁坏了。
    """
    from app.modules.specs import get_spec

    names = list(only) if only else list(MODULE_NAMES)
    results: list[ExportResult] = []
    failures: list[dict[str, str]] = []
    total_rows = 0

    for name in names:
        try:
            spec = get_spec(name)
            result = export_module(spec, scope=ExportScope(), fmt=fmt)
            if not result.matched:
                raise RuntimeError(
                    f"导出条数 {result.total} 与列表总数不一致（通道自检失败）"
                )
            results.append(result)
            total_rows += result.total
        except Exception as exc:  # noqa: BLE001 - 批量任务需要隔离单模块故障
            failures.append({"module": name, "error": f"{type(exc).__name__}: {exc}"})

    return BatchReport(
        ok=not failures,
        total_modules=len(names),
        succeeded=len(results),
        failed=len(failures),
        total_rows=total_rows,
        results=results,
        failures=failures,
    )
