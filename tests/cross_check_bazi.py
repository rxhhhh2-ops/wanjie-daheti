# -*- coding: utf-8 -*-
"""四柱引擎 vs lunar_python 交叉对拍。

对拍口径（经实验确认）：
  - 年界：双方均以立春换年；
  - 引擎默认 23:00 换日（晚子时算次日，日柱时柱皆按次日）≈ lunar_python sect=1；
  - 引擎 00:00 换日（日柱时柱皆按当天）在 lunar_python 中无完全等价流派，
    其日柱 ≈ sect=2，时柱按五鼠遁自洽性单独验证。

历法层节气表实现约束：排盘需取当年±1 年节气，故实际支持 1901–2099。

用法：py -3.12 tests/cross_check_bazi.py   （须在项目根目录运行）
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "engine"))

from lunar_python import Solar          # 成熟开源历法库（对照方）
from bazi_engine import BaziEngine      # 被测方

ENG = BaziEngine()

FIXED = [  # 代表性用例：节气交界 / 换日边界 / 闰月 / 世纪极值
    (1984, 2, 4, 23, 10, "立春当日 晚子时"),
    (1984, 2, 4, 22, 50, "立春当日 亥时"),
    (1990, 6, 15, 14, 30, "常规"),
    (2000, 2, 4, 12, 0, "立春前后"),
    (2000, 2, 5, 0, 30, "立春后 早子"),
    (2023, 3, 22, 10, 0, "闰二月"),
    (2024, 2, 10, 0, 0, "正月初一 零点"),
    (1950, 10, 1, 8, 0, "常规"),
    (1901, 1, 1, 0, 0, "支持下限"),
    (1901, 12, 31, 23, 59, "支持下限年末 晚子"),
    (2099, 12, 31, 23, 59, "支持上限"),
    (2026, 10, 30, 15, 40, "当前时刻"),
    (1997, 7, 1, 0, 0, "整点"),
    (2033, 11, 1, 13, 5, "闰十一月（2033 问题年）"),
]

def ref_pillars(y, m, d, hh, mi, sect=2):
    ec = Solar.fromYmdHms(y, m, d, hh, mi, 0).getLunar().getEightChar()
    ec.setSect(sect)
    return [ec.getYear(), ec.getMonth(), ec.getDay(), ec.getTime()]

def eng_pillars(y, m, d, hh, mi, boundary=None):
    cfg = {"day_boundary": boundary} if boundary else None
    eng = BaziEngine(cfg) if cfg else ENG
    q = eng.pillars_from_datetime(y, m, d, hh, mi)["四柱"]
    return [q["年"], q["月"], q["日"], q["时"]]

def main():
    random.seed(20261030)
    cases = list(FIXED)
    for _ in range(60):  # 随机抽样：1901-2099（历法层实际支持区间）均匀分布
        cases.append((random.randint(1901, 2099), random.randint(1, 12),
                      random.randint(1, 28), random.randint(0, 23),
                      random.choice([0, 15, 30, 45]), "随机"))

    passed = failed = 0
    fails = []
    for (y, m, d, hh, mi, tag) in cases:
        try:
            got = eng_pillars(y, m, d, hh, mi)
        except Exception as exc:
            failed += 1
            fails.append((f"{y}-{m}-{d} {hh}:{mi} {tag}", "引擎异常", str(exc), ""))
            continue
        want = ref_pillars(y, m, d, hh, mi, sect=1)   # 晚子时算次日 ≡ 引擎默认 23:00 换日
        if got == want:
            passed += 1
        else:
            failed += 1
            fails.append((f"{y}-{m}-{d} {hh}:{mi} {tag}", "/".join(want), "/".join(got), ""))

    # 00:00 换日口径：日柱按当天（≈ sect=2），时柱按当天日干五鼠遁自洽验证
    WUSHU = {"甲": "甲", "己": "甲", "乙": "丙", "庚": "丙", "丙": "戊",
             "辛": "戊", "丁": "壬", "壬": "壬", "戊": "甲", "癸": "甲"}  # 日干→子时起干
    for (y, m, d, hh, mi) in [(1990, 6, 15, 23, 30), (2024, 8, 8, 23, 59), (2001, 1, 1, 23, 1)]:
        got = eng_pillars(y, m, d, hh, mi, boundary="00:00")
        want = ref_pillars(y, m, d, hh, mi, sect=2)
        day_ok = got[2] == want[2]
        hour_ok = got[3][0] == WUSHU[got[2][0]] and got[3][1] == "子"   # 晚子时的时柱
        if day_ok and hour_ok:
            passed += 1
        else:
            failed += 1
            fails.append((f"{y}-{m}-{d} {hh}:{mi} 00:00换日", "/".join(want), "/".join(got),
                          "日柱不符" if not day_ok else "时柱五鼠遁不符"))

    print(f"四柱干支对拍：{passed} 通过，{failed} 不一致（共 {passed + failed} 例）")
    for when, want, got, _ in fails[:20]:
        print(f"  ✗ {when}\n      lunar_python: {want}\n      引擎输出:     {got}")
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
