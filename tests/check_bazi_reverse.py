# -*- coding: utf-8 -*-
"""手动八字校验 / 八字反推时间的回归断言。

运行：python tests/check_bazi_reverse.py
覆盖：六十甲子、五虎遁、五鼠遁、真实日期反推、早/晚子时、区间端点、随机回环。
"""
from __future__ import annotations

import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "engine"))

import bazi_engine as B  # noqa: E402
import bazi_reverse as BR  # noqa: E402

ENG = B.BaziEngine()
PASS = 0


def need(cond, msg):
    global PASS
    if not cond:
        raise AssertionError(msg)
    PASS += 1


def pillars_at(y, m, d, h, mi):
    return ENG.pillars_from_datetime(y, m, d, h, mi)["四柱"]


def pillars_of_solar(s):
    date, _, clock = s.partition("T")
    y, m, d = (int(x) for x in date.split("-"))
    h, mi = (int(x) for x in clock.split(":"))
    return pillars_at(y, m, d, h, mi)


def rev(p):
    return BR.reverse_pillars(ENG, p)


def check_invalid():
    j = rev({"年": "甲子", "月": "戊寅", "日": "己巳", "时": "戊辰"})
    need(j["valid"] is False and j["count"] == 0, "戊寅应判非法")
    need(j["expected"] == {"月柱": "丙寅"}, "只应提示月柱修正值")
    need("五虎遁" in j["errors"][0], "月柱错误应说明五虎遁")

    j = rev({"年": "甲子", "月": "丙寅", "日": "己巳", "时": "甲辰"})
    need(j["valid"] is False and j["expected"] == {"时柱": "戊辰"}, "只应提示时柱修正值")
    need("五鼠遁" in j["errors"][0], "时柱错误应说明五鼠遁")

    j = rev({"年": "甲丑", "月": "丙寅", "日": "己巳", "时": "戊辰"})
    need(j["valid"] is False and "六十甲子" in j["errors"][0], "甲丑应判非法干支")
    need(not j["expected"], "结构性错误不应给修正值")

    j = rev({"年": "丙寅", "月": "甲子", "日": "己巳", "时": "戊辰"})
    need(j["valid"] is False and j["expected"].get("月柱") == "庚子", "丙年子月应为庚子")


def check_anchor(y, m, d, h, mi):
    p = pillars_at(y, m, d, h, mi)
    j = rev(p)
    need(j["valid"] and j["count"] >= 1, f"{p} 应有候选")
    for c in j["candidates"]:
        need(pillars_of_solar(c["solar"]) == p, f"候选 {c['solar']} 回排不一致")
    stamp = f"{y:04d}-{m:02d}-{d:02d}T{h:02d}:{mi:02d}"
    if not (h == 23 and mi >= 30) and not (h == 0):
        need(any(c["solar"].startswith(stamp[:10]) for c in j["candidates"]),
             f"{stamp} 应出现在候选中，实际 {[c['solar'] for c in j['candidates']]}")


def check_zi():
    # 早子 00:30 与晚子 23:30 均须能反推，且晚子候选标记日界
    for h, mi in ((0, 30), (23, 30)):
        p = pillars_at(2000, 1, 1, h, mi)
        j = rev(p)
        need(j["valid"] and j["count"] >= 1, f"{h}:{mi} 应有候选")
        if h == 23:
            need(any(c.get("lateZi") for c in j["candidates"]), "23:30 应有晚子候选")
        else:
            need(any(not c.get("lateZi") for c in j["candidates"]), "00:30 应有早子候选")


def check_random(n=16):
    rnd = random.Random(20261101)
    for _ in range(n):
        y = rnd.randint(1902, 2098)
        m = rnd.randint(1, 12)
        d = rnd.randint(1, 28)
        h = rnd.randrange(24)
        mi = rnd.randrange(60)
        p = pillars_at(y, m, d, h, mi)
        j = rev(p)
        need(j["valid"] and j["count"] >= 1, f"随机 {y}-{m}-{d} {h}:{mi} 无候选")
        for c in j["candidates"]:
            need(pillars_of_solar(c["solar"]) == p, f"随机候选 {c['solar']} 回排不一致")


def main():
    check_invalid()
    for args in ((1984, 2, 5, 8, 30), (2024, 2, 4, 17, 0), (1990, 7, 17, 16, 0),
                 (1949, 5, 2, 12, 0), (2000, 1, 1, 0, 30), (2000, 1, 1, 23, 30),
                 (1901, 1, 1, 12, 0), (2098, 12, 31, 12, 0)):
        check_anchor(*args)
    check_zi()
    check_random()
    print(f"OK  bazi_reverse 断言 {PASS} 项全部通过")


if __name__ == "__main__":
    main()
