"""全量导出自检脚本：不依赖 HTTP，直接跑一遍所有模块的全量导出。

用法：
    .venv/bin/python -m scripts.export_all            # 全部模块
    .venv/bin/python -m scripts.export_all alarm meter
    .venv/bin/python -m scripts.export_all --fmt csv

任一模块失败会以非零码退出，并打印是哪个模块、什么原因，方便定位。
"""
from __future__ import annotations

import sys

from app.modules.exporting import batch_export_all


def main(argv: list[str]) -> int:
    fmt = "json"
    only: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--fmt":
            if i + 1 >= len(argv):
                print("--fmt 需要指定 json 或 csv", file=sys.stderr)
                return 2
            fmt = argv[i + 1]
            i += 2
            continue
        only.append(arg)
        i += 1

    if fmt not in ("json", "csv"):
        print(f"不支持的导出格式：{fmt}（仅支持 json/csv）", file=sys.stderr)
        return 2

    report = batch_export_all(only=only or None, fmt=fmt)

    for result in report.results:
        match_flag = "OK" if result.matched else "MISMATCH"
        print(f"[{match_flag}] {result.module}: {result.total} 条 -> {result.file}")

    if report.failures:
        print("\n以下模块导出失败：", file=sys.stderr)
        for failure in report.failures:
            print(f"  - {failure['module']}: {failure['error']}", file=sys.stderr)
        return 1

    print(
        f"\n全部通过：{report.succeeded}/{report.total_modules} 个模块，"
        f"共 {report.total_rows} 条。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
