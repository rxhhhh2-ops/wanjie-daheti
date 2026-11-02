# -*- coding: utf-8 -*-
"""应期功能冒烟/结构断言。

运行：python tests/check_yingqi.py
只做轻量断言，不替代人工核对原文。
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "engine"))

import server  # noqa: E402
import qimen_engine as Q  # noqa: E402
import yingqi_engine as YQ  # noqa: E402
import ai_coach  # noqa: E402


def _need(cond, msg):
    if not cond:
        raise AssertionError(msg)


def check_rules_json():
    path = os.path.join(ROOT, "rules", "19-应期.json")
    data = json.load(open(path, encoding="utf-8"))
    _need(set(data["tools"]) == {"梅花", "奇门", "六壬", "八字", "紫微"}, "五个工具应齐全")
    n = 0
    for tool, block in data["tools"].items():
        for r in block["rules"]:
            n += 1
            for key in ("id", "title", "rule", "source", "file", "quote", "level", "status"):
                _need(r.get(key), f"{tool}/{r.get('id')} 缺 {key}")
            _need(r["level"].startswith("["), f"{tool}/{r['id']} level 未分级")
        _need(block.get("gaps"), f"{tool} 未写缺口")
    return n


def check_bazi():
    d = server.bazi_paipan(1984, 2, 5, 8, 30, "男", 2026, None)
    y = d.get("应期")
    _need(isinstance(y, dict) and not y.get("error"), "四柱应期缺失或报错")
    _need(y["sections"], "四柱应期无分段")
    for c in y["candidates"]:
        _need(c.get("src") and c.get("level"), "四柱候选缺出处")
        _need(not str(c.get("basis", "")).startswith("用神行运喜忌"), "YS-004 不应单独作应期候选")
    return len(y["candidates"])


def check_qimen():
    # 2026-10-12 00:30 值符甲子加震三宫，子刑卯 → 取丑；应有候选。
    at = dt.datetime(2026, 10, 12, 0, 30)
    chart = Q.cast(at, Q.QimenConfig())
    y = YQ.qimen_yingqi(chart, at.date())
    _need(y["candidates"], "奇门相刑法未生成候选")
    for c in y["candidates"]:
        _need("法窍" in c["src"] or "奇门法窍" in c["src"], "奇门候选缺法窍出处")
        _need(c.get("date") and c.get("gz"), "奇门候缺少日期/干支")
    # 另一个普通盘应诚实留空并给出缺口
    at2 = dt.datetime(2026, 10, 31, 15, 30)
    y2 = YQ.qimen_yingqi(Q.cast(at2, Q.QimenConfig()), at2.date())
    _need(y2["gaps"], "奇门未列明算法时应写缺口")
    return len(y["candidates"])


def check_meihua():
    # 水山蹇：体艮、用坎、变坤；坎/艮原文未列，不得有候选或“推定”。
    q = {"mode": ["dt"], "dt": ["2026-10-31 15:30"], "question": ["求财"], "motion": ["行"]}
    d = server.mh_build(q)
    yq = d["yingqi"]
    text = json.dumps(yq, ensure_ascii=False)
    _need("推定" not in text, "梅花仍含推定内容")
    for x in yq["卦气"]:
        if x["卦"] in ("坎", "离", "艮"):
            _need(not x["候选"], f"{x['卦']} 不应有推补候选")
    _need(any(x["候选"] for x in yq["卦气"]), "原文所列之卦应能出候选")
    return len(yq["卦气"])


def check_ai_gate():
    chart = server.bazi_paipan(1984, 2, 5, 8, 30, "男", 2026, None)
    a = ai_coach.build_messages(chart, None, "请整体解读。", None, allow_yingqi=False)
    b = ai_coach.build_messages(chart, None, "请说明应期。", None, allow_yingqi=True)
    _need("应期禁令" in a[0]["content"], "默认 system 缺应期禁令")
    _need("应期（仅供用户明确要求时使用）" not in a[1]["content"], "默认上下文泄露应期")
    _need("应期（仅供用户明确要求时使用）" in b[1]["content"], "明确要求时应提供应期上下文")
    _need("应期禁令" not in b[0]["content"], "明确要求时不应再禁令")


def main():
    n = check_rules_json()
    bz = check_bazi()
    qm = check_qimen()
    mh = check_meihua()
    check_ai_gate()
    print(f"OK  rules={n}  bazi_candidates={bz}  qimen_candidates={qm}  meihua_roles={mh}")


if __name__ == "__main__":
    main()
