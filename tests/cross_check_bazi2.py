# -*- coding: utf-8 -*-
"""四柱衍生层对拍：藏干 / 十神 / 空亡 / 大运干支序列。

对照方：lunar_python EightChar / Lunar / Yun（成熟开源实现）。
用法：py -3.12 tests/cross_check_bazi2.py  （须在项目根目录运行）
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "engine"))

from lunar_python import Solar
from bazi_engine import BaziEngine
from yunsui_engine import YunSuiEngine

ENG = BaziEngine()
POS = ["年", "月", "日", "时"]

# 藏干通行口径（rules/02-藏干.json CG-007，按问真八字/通行主流，2026-10-31 对齐）：
#   子癸、丑己癸辛、寅甲丙戊、卯乙、辰戊乙癸、巳丙庚戊、午丁己、未己丁乙、
#   申庚壬戊、酉辛、戌戊辛丁、亥壬甲。与 lunar_python 通表一致。
_TONGXING_HIDE = {
    "子": ["癸"], "丑": ["己", "癸", "辛"], "寅": ["甲", "丙", "戊"],
    "卯": ["乙"], "辰": ["戊", "乙", "癸"], "巳": ["丙", "庚", "戊"],
    "午": ["丁", "己"], "未": ["己", "丁", "乙"], "申": ["庚", "壬", "戊"],
    "酉": ["辛"], "戌": ["戊", "辛", "丁"], "亥": ["壬", "甲"],
}

CASES = [(1990, 6, 15, 14, 30), (1984, 2, 4, 23, 10), (2024, 2, 10, 0, 0),
         (1950, 10, 1, 8, 0), (2033, 11, 1, 13, 5), (2000, 2, 4, 12, 0)]
random.seed(42)
CASES += [(random.randint(1901, 2099), random.randint(1, 12), random.randint(1, 28),
           random.randint(0, 23), random.choice([0, 30])) for _ in range(20)]

passed = failed = 0
fails = []

def check(label, got, want, ctx):
    global passed, failed
    if got == want:
        passed += 1
    else:
        failed += 1
        fails.append(f"  ✗ {ctx} {label}\n      参考: {want}\n      引擎: {got}")

for (y, m, d, hh, mi) in CASES:
    ctx = f"{y}-{m:02d}-{d:02d} {hh:02d}:{mi:02d}"
    p = ENG.pillars_from_datetime(y, m, d, hh, mi)
    qz = p["四柱"]
    lunar = Solar.fromYmdHms(y, m, d, hh, mi, 0).getLunar()
    ec = lunar.getEightChar()
    ec.setSect(1)  # ≡ 引擎默认 23:00 换日

    a = ENG.analyze(qz["年"], qz["月"], qz["日"], qz["时"], gender="男")

    # --- 藏干：本气与参考库对拍；全表与通行口径对拍（子午卯酉已改通行版） ---
    ref_hide = [ec.getYearHideGan(), ec.getMonthHideGan(), ec.getDayHideGan(), ec.getTimeHideGan()]
    for i, pos in enumerate(POS):
        zhi = qz[pos][1]
        got = a["藏干"][pos]["本"] + a["藏干"][pos]["中"] + a["藏干"][pos]["余"]
        check(f"{pos}藏干本气", [got[0]], [ref_hide[i][0]], ctx)
        check(f"{pos}藏干通行表", got, _TONGXING_HIDE[zhi], ctx)

    # --- 天干十神（年/月/时；日主本身无十神） ---
    ref_gan = {"年": ec.getYearShiShenGan(), "月": ec.getMonthShiShenGan(),
               "时": ec.getTimeShiShenGan()}
    for pos in ("年", "月", "时"):
        check(f"{pos}干十神", a["十神"]["天干"][pos], ref_gan[pos], ctx)

    # --- 藏干十神：本气用参考库，中余气用独立书写的十神函数（十神=五行生克+阴阳，数学规则） ---
    WUXING = {"甲": ("木", 1), "乙": ("木", 0), "丙": ("火", 1), "丁": ("火", 0),
              "戊": ("土", 1), "己": ("土", 0), "庚": ("金", 1), "辛": ("金", 0),
              "壬": ("水", 1), "癸": ("水", 0)}
    SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
    KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

    def shishen(day_gan, other):
        de, oe = WUXING[day_gan], WUXING[other]
        same_yy = de[1] == oe[1]
        if de[0] == oe[0]:
            base = "比肩" if same_yy else "劫财"
        elif SHENG[de[0]] == oe[0]:
            base = "食神" if same_yy else "伤官"
        elif SHENG[oe[0]] == de[0]:
            base = "正印" if not same_yy else "偏印"
        elif KE[de[0]] == oe[0]:
            base = "正财" if not same_yy else "偏财"
        else:
            base = "正官" if not same_yy else "七杀"
        return base

    ref_zhi = [ec.getYearShiShenZhi(), ec.getMonthShiShenZhi(),
               ec.getDayShiShenZhi(), ec.getTimeShiShenZhi()]
    for i, pos in enumerate(POS):
        hg = a["藏干"][pos]["本"] + a["藏干"][pos]["中"] + a["藏干"][pos]["余"]
        got_map = a["十神"]["藏干"][pos]
        got = [got_map[g] for g in hg]
        want = [shishen(qz["日"][0], g) for g in hg]     # 十神=数学规则，参考实现独立书写
        check(f"{pos}藏干十神", got, want, ctx)
        # 交叉佐证：与参考库比对本气十神（中/余气两表分歧且顺序不同，不比）
        if len(ref_zhi[i]) and got:
            check(f"{pos}藏干十神(库)#0", got[0], ref_zhi[i][0], ctx)

    # --- 空亡（日旬） ---
    check("空亡", sorted(a["空亡"]["空亡"]), sorted(list(lunar.getDayXunKong())), ctx)
    check("旬首", a["空亡"]["旬首"], lunar.getDayXun(), ctx)

    # --- 大运干支序列（阳男/阴女顺排、阴男/阳女逆排，男女各测） ---
    for gender, gcode in (("男", 1), ("女", 0)):
        eng_ys = YunSuiEngine(ENG).dayun(qz, gender, p["节气距离"], birth_year=y)
        got_dy = [s["干支"] for s in eng_ys["大运（前八步）"]]
        ref_dy = [d.getGanZhi() for d in ec.getYun(gcode).getDaYun()]
        ref_dy = [g for g in ref_dy if g][:8]       # 参考首项为起运前空干支，剔除
        check(f"大运序列({gender})", got_dy, ref_dy, ctx)

print(f"衍生层对拍：{passed} 通过，{failed} 不一致（用例 {len(CASES)} 个，共 {passed + failed} 项断言）")
for line in fails[:24]:
    print(line)
sys.exit(1 if failed else 0)
