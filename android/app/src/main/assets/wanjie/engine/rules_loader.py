# -*- coding: utf-8 -*-
"""rules/*.json 加载器（带门禁）。

用法：
    python tools/rules_loader.py                 # 打印统计
    python tools/rules_loader.py --category GJ   # 只看某类
    python tools/rules_loader.py --all           # 包含需校勘/参考项（仅审阅）

API：
    load_rules() -> list[dict]                   # 默认只返回 engine.loadable=true 的规则
    load_rules(include_blocked=True)             # 返回全部，带 blocked 标记
    get_rule("SZ-007") -> dict | None
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RULES_DIR = os.path.join(ROOT, "rules")


def _files(category: str | None = None) -> list[str]:
    paths = sorted(glob.glob(os.path.join(RULES_DIR, "*.json")))
    paths = [p for p in paths if not os.path.basename(p).startswith("00-")]
    if category:
        prefix = category.upper()
        paths = [p for p in paths if os.path.basename(p).startswith("")
                 and json.load(open(p, encoding="utf-8"))["category_id"] == prefix]
    return paths


def load_rules(category: str | None = None, include_blocked: bool = False) -> list[dict]:
    rules: list[dict] = []
    seen: set[str] = set()
    for path in _files(category):
        data = json.load(open(path, encoding="utf-8"))
        if "rules" not in data:
            # 其他子系统（如奇门）的 JSON 规则库也放在 rules/ 下，跳过
            continue
        for r in data["rules"]:
            if r["id"] in seen:
                raise ValueError(f"duplicate rule id: {r['id']}")
            seen.add(r["id"])
            if not include_blocked and not r["engine"]["loadable"]:
                continue
            rules.append(r)
    return rules


def get_rule(rule_id: str) -> dict | None:
    for r in load_rules(include_blocked=True):
        if r["id"] == rule_id:
            return r
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", default=None, help="SZ/CG/SS/YL/LM/YR/KW/GJ")
    ap.add_argument("--all", action="store_true", help="包含需校勘/参考项")
    args = ap.parse_args()

    all_rules = load_rules(category=args.category, include_blocked=True)
    loadable = [r for r in all_rules if r["engine"]["loadable"]]
    blocked = [r for r in all_rules if not r["engine"]["loadable"]]
    print(f"total: {len(all_rules)}; loadable: {len(loadable)}; blocked/reference: {len(blocked)}")
    if blocked:
        print("blocked/reference:")
        for r in blocked:
            print(f"  - {r['id']} {r['title']} [{r['level']}/{r['status']}]")
    if args.all:
        print("all rules:")
        for r in all_rules:
            print(f"  {r['id']}\t{r['level']}\t{r['status']}\t{r['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
