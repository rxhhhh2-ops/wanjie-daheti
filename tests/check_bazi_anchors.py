# -*- coding: utf-8 -*-
"""四柱外部锚点校验（直接调引擎，不依赖对齐方实现）。

锚点来源为可公开查证的历法事实：
  - 年柱：公历 3 月 1 日必在立春后，年柱即该农历年干支（1950 庚寅、1984 甲子、
    2000 庚辰、2024 甲辰、2025 乙巳、2033 癸丑、1901 辛丑、2099 己未）；
  - 日柱：1949-10-01 为甲子日（通行历法资料）；
  - 年界：2024 年立春 2 月 4 日 16:27（北京时）前后年柱切换；
  - 农历：1984-08-13 = 农历甲子年七月十七（与紫微资料 T1 一致）。

用法：py -3.12 tests/check_bazi_anchors.py   （项目根目录）
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "engine"))

from bazi_engine import BaziEngine

ENG = BaziEngine()
passed = failed = 0
fails = []


def pillars(y, m, d, hh=12, mi=0):
    return ENG.pillars_from_datetime(y, m, d, hh, mi)


def check(label, got, want):
    global passed, failed
    if got == want:
        passed += 1
    else:
        failed += 1
        fails.append(f"  ✗ {label}: 期望 {want}, 引擎 {got}")


YEAR_ANCHORS = [(1901, "辛丑"), (1950, "庚寅"), (1984, "甲子"), (2000, "庚辰"),
                (2024, "甲辰"), (2025, "乙巳"), (2033, "癸丑"), (2099, "己未")]
for y, gz in YEAR_ANCHORS:
    q = pillars(y, 3, 1)["四柱"]
    check(f"{y}-03-01 年柱", q["年"], gz)

# 1949-10-01 甲子日
q = pillars(1949, 10, 1, 15, 0)["四柱"]
check("1949-10-01 日柱", q["日"], "甲子")

# 2024 立春 02-04 16:27 前后
before = pillars(2024, 2, 4, 15, 0)["四柱"]
after = pillars(2024, 2, 4, 18, 0)["四柱"]
check("2024-02-04 15:00 年柱(立春前)", before["年"], "癸卯")
check("2024-02-04 18:00 年柱(立春后)", after["年"], "甲辰")

# 农历换算：1984-08-13 → 农历甲子年七月十七（与紫微资料 T1 一致）
from calendar_layer import solar_to_lunar
lr = solar_to_lunar(1984, 8, 13)
check("1984-08-13 农历年", lr.get("year"), 1984)
check("1984-08-13 农历月", lr.get("month"), 7)
check("1984-08-13 农历日", lr.get("day"), 17)

print(f"四柱外部锚点：{passed} 通过，{failed} 不一致（共 {passed + failed} 项）")
for line in fails:
    print(line)
sys.exit(1 if failed else 0)
