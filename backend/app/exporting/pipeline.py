"""导出主通道：取数、投影、落盘都在这里收口。

取数必须复用各模块 service 的 list_entries——和列表接口同一个函数、同一套
过滤参数，只把分页放大到全量。这样“导出的条数”天然等于“列表的 total”，
分页导出与全量导出不可能各出一套结果。
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from app.exporting.registry import ExportSpec, get_spec
from app.exporting.writer import encode_csv, render_csv

# 全量取数的分页大小：列表接口每页上限是 200，这里逐页取完再合并，
# 不绕开 service 的过滤口径，也不构造超大单页。
FETCH_PAGE_SIZE = 200

# 导出文件统一落盘目录（仓库根/backend/exports），文件名固定：
# export_<模块>.csv —— 重复导出同一模块只覆盖，绝不追加。
EXPORT_DIR = Path(__file__).resolve().parent.parent.parent / "exports"


class ListService(Protocol):
    """各模块 service 的最小接口：就是列表接口背后那个方法。"""

    def list_entries(
        self,
        *,
        keyword: str | None = ...,
        status: str | None = ...,
        page: int = ...,
        size: int = ...,
    ) -> tuple[list[dict[str, Any]], int]: ...


_SERVICE_REGISTRY: dict[str, ListService] = {}


def register_service(module: str, service: ListService) -> None:
    """登记模块的取数服务。各模块只说自己的取数入口，不关心怎么导出。"""
    if module in _SERVICE_REGISTRY:
        raise RuntimeError(f"模块 {module} 的导出服务已登记，请勿重复注册")
    _SERVICE_REGISTRY[module] = service


def registered_modules() -> list[str]:
    return sorted(_SERVICE_REGISTRY)


def fetch_dataset(
    module: str,
    *,
    keyword: str | None = None,
    status: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """按列表口径取全量数据：循环分页直到取满 total。

    返回 (全部行, total)。total 来自 service 的过滤后计数，与列表页脚展示的
    “共 N 条”是同一个值；若循环结束条数对不上 total，直接抛错而不是静默
    交一份残缺导出。
    """
    try:
        service = _SERVICE_REGISTRY[module]
    except KeyError:
        raise KeyError(f"模块 {module} 未登记导出取数服务") from None

    items: list[dict[str, Any]] = []
    page = 1
    while True:
        batch, total = service.list_entries(
            keyword=keyword, status=status, page=page, size=FETCH_PAGE_SIZE
        )
        items.extend(batch)
        if not batch or len(items) >= total:
            break
        page += 1
    if len(items) != total:
        raise RuntimeError(
            f"模块 {module} 导出取数不完整：列表计数 {total} 条，实际取到 {len(items)} 条"
        )
    return items, total


@dataclass
class ExportResult:
    """一次导出的产物：total 与列表 total 同源；文件为覆盖写入后的固定路径。"""

    module: str
    label: str
    total: int
    items: list[dict[str, Any]]
    fields: tuple[str, ...]
    format: str
    path: Path | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def _overwrite_file(path: Path, content: bytes) -> None:
    """同目录临时文件 + os.replace 原子覆盖；重复导出只覆盖，不追加。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def _scope_suffix(keyword: str | None, status: str | None) -> str:
    """取数范围指纹：同一批过滤条件得到同一个稳定后缀，只覆盖同名文件。

    无过滤（真正的全量）后缀为空，文件名维持 export_<模块>.csv；
    有过滤时用过滤参数的短哈希命名，避免把全量文件冲掉。
    """
    if not keyword and not status:
        return ""
    digest = hashlib.sha1(
        f"{keyword or ''}\x1f{status or ''}".encode("utf-8")
    ).hexdigest()[:8]
    # 过滤值可能含任意字符不宜直接入文件名，只用稳定短哈希做范围指纹
    return f"_scope-{digest}"


def export_module(
    module: str,
    *,
    keyword: str | None = None,
    status: str | None = None,
    fmt: str = "csv",
    page: int | None = None,
    size: int = FETCH_PAGE_SIZE,
) -> ExportResult:
    """统一导出入口：按注册表口径导出单个模块。

    数据始终先按列表口径取全量（与列表 total 同源），再在内存切片：

    - page 为空：全量导出，覆盖写入固定文件 export_<模块>.csv，重复导出不追加；
    - page 有值：分页导出，行集是同一份全量结果的切片，只返回下载内容、不落盘，
      避免用一页数据覆盖掉整份导出文件。

    fmt=csv：真正的下载文件，列顺序/空值占位以注册表为准；
    fmt=json：保留切换前的老响应结构 {module,total,items}，分页时附带 page/size。
    """
    spec: ExportSpec = get_spec(module)
    items, total = fetch_dataset(module, keyword=keyword, status=status)

    full_scope = page is None
    if not full_scope:
        start = max(page - 1, 0) * size
        items = items[start:start + size]

    if fmt == "json":
        # 兼容老行为：items 仍是 service 吐出的原始行，不做投影、不做占位改写，
        # 也不落盘——老的程序化调用方只拿到 JSON，没有文件副作用。
        return ExportResult(
            module=module,
            label=spec.label,
            total=total,
            items=items,
            fields=spec.fields,
            format="json",
            extra={"page": page, "size": size} if not full_scope else {},
        )

    if fmt != "csv":
        raise ValueError(f"不支持的导出格式：{fmt}（仅支持 csv/json）")

    csv_bytes = encode_csv(render_csv(spec.fields, items))
    path: Path | None = None
    if full_scope:
        # 全量/按固定范围导出才落盘；同范围重复导出只覆盖同名文件，不追加。
        path = EXPORT_DIR / f"export_{module}{_scope_suffix(keyword, status)}.csv"
        _overwrite_file(path, csv_bytes)
    return ExportResult(
        module=module,
        label=spec.label,
        total=total,
        items=items,
        fields=spec.fields,
        format="csv",
        path=path,
        extra={"content": csv_bytes, "full_scope": full_scope},
    )
