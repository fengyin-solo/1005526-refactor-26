"""导出渲染：按注册口径把行数据投影成列、渲染成 CSV。

空值占位与前端列表保持一致：列表模板里 ``row[column] ?? '—'`` 只对
``null``/缺列生效，因此这里也只在值为 ``None`` 或缺列时填 ``—``，
空字符串原样保留，不擅自扩大占位范围。
"""
from __future__ import annotations

import csv
import io
from typing import Any

NULL_PLACEHOLDER = "—"


def project_row(row: dict[str, Any], fields: tuple[str, ...]) -> list[str]:
    """把一行原始数据按列顺序取值；null 或缺列统一填历史占位符 ``—``。"""
    cells: list[str] = []
    for field in fields:
        value = row.get(field)
        cells.append(NULL_PLACEHOLDER if value is None else str(value))
    return cells


def render_csv(fields: tuple[str, ...], rows: list[dict[str, Any]]) -> str:
    """渲染 CSV 文本：表头为注册列顺序，空值走 project_row 的统一占位。"""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(fields)
    for row in rows:
        writer.writerow(project_row(row, fields))
    return buffer.getvalue()


def encode_csv(text: str) -> bytes:
    """加 UTF-8 BOM，让 Excel 直接打开不乱码。"""
    return b"\xef\xbb\xbf" + text.encode("utf-8")
