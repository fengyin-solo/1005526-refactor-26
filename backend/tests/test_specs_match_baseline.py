"""逐模块比对：注册表口径必须与合并前各模块三处定义的核对底稿完全一致。

底稿 tests/expected_specs.json 是从收拢前的 services / routers / 前端页面
三处常量提取并交叉校验过的，作为"存量字段逐个模块核对"的冻结凭据。
"""
from __future__ import annotations

import json
from pathlib import Path

from app.modules.specs import MODULE_NAMES, SPECS

BASELINE = json.loads(Path(__file__).with_name("expected_specs.json").read_text("utf-8"))


def test_baseline_covers_every_module():
    assert sorted(BASELINE) == sorted(MODULE_NAMES)
    assert len(MODULE_NAMES) == 18


def test_each_module_matches_baseline():
    for name, base in BASELINE.items():
        spec = SPECS[name]
        assert spec.prefix == base["prefix"]
        assert spec.tag == base["tag"]
        assert spec.entity == base["noun"]
        assert spec.created == base["created"]
        assert spec.keyword_field == base["keyword"]
        assert list(spec.fields) == base["fields"]
        assert list(spec.required) == base["required"]
        assert list(spec.statuses) == base["statuses"]
        assert dict(spec.actions) == base["actions"]
        assert sorted(spec.negative_actions) == sorted(base["negative"])


def test_derived_invariants():
    for name in MODULE_NAMES:
        spec = SPECS[name]
        # 关键字字段恒为首列，必填恒为前三列：合并时各模块即此口径。
        assert spec.keyword_field == spec.fields[0]
        assert tuple(spec.required) == spec.fields[:3]
        # 动作目标必须落在状态序列内。
        assert set(spec.actions.values()) <= set(spec.statuses)
        assert set(spec.negative_actions) <= set(spec.actions)
        # 字段不允许重名重复（历史列顺序里每个字段唯一）。
        assert len(set(spec.fields)) == len(spec.fields)
