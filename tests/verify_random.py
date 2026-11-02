# -*- coding: utf-8 -*-
"""四柱全环节随机验证（问真八字模块划分 × 独立参照）。

问真八字为闭源 App，无程序化接口，不作为自动对照源；本脚本按其展示模块
逐环节验证，参照方为独立实现与经典规则表：
  - 排盘/十神/藏干/空亡/纳音/星运/命宫/大运/流年/流月/流日/流时 → lunar_python（独立成熟库）
  - 神煞（天乙/驿马/桃花/华盖/将星）、小运（醉醒子）、十神全量 → 经典规则/数学规则独立重算
  - 格局/藏干 vs 规则库 → 自洽校验 + 独立取格复算
已知口径差异（非错误，单独计数）：丑余气（原文庚 vs 通行辛）、亥余气（原文多戊，CG-002）。

用法：py -3.12 tests/verify_random.py   （项目根目录）
"""
import os
import random
import sys
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "engine"))

from lunar_python import Solar          # 独立参照方
import server                            # 被测方（bazi_paipan / bazi_flow）
from bazi_engine import BaziEngine
from yunsui_engine import YunSuiEngine

ENG2 = BaziEngine()
POS = ["年", "月", "日", "时"]
ZHI = "子丑寅卯辰巳午未申酉戌亥"
WX_G = dict(zip("甲乙丙丁戊己庚辛壬癸", "木木火火土土金金水水"))
WX_Z = dict(zip(ZHI, "水土木木土火火土金金土水"))
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
YY = {"甲": 1, "乙": 0, "丙": 1, "丁": 0, "戊": 1, "己": 0, "庚": 1, "辛": 0, "壬": 1, "癸": 0}

# ---- 经典规则表（独立于引擎规则库） ----
TIANYI = {"甲": ("丑", "未"), "戊": ("丑", "未"), "庚": ("丑", "未"),
          "乙": ("子", "申"), "己": ("子", "申"),
          "丙": ("亥", "酉"), "丁": ("亥", "酉"),
          "壬": ("卯", "巳"), "癸": ("卯", "巳"), "辛": ("午", "寅")}
SANHE = {"申子辰": "水", "寅午戌": "火", "巳酉丑": "金", "亥卯未": "木"}
GROUP_OF = {}
for _g in SANHE:
    for _b in _g:
        GROUP_OF[_b] = _g
YIMA = {"申子辰": "寅", "寅午戌": "申", "巳酉丑": "亥", "亥卯未": "巳"}
TAOHUA = {"申子辰": "酉", "寅午戌": "卯", "巳酉丑": "午", "亥卯未": "子"}
HUAGAI = {"申子辰": "辰", "寅午戌": "戌", "巳酉丑": "丑", "亥卯未": "未"}
JIANGXING = {"申子辰": "子", "寅午戌": "午", "巳酉丑": "酉", "亥卯未": "卯"}
WUSHU = {"甲": "甲", "己": "甲", "乙": "丙", "庚": "丙", "丙": "戊",
         "辛": "戊", "丁": "壬", "壬": "壬", "戊": "甲", "癸": "甲"}
BENQI = {"子": "癸", "丑": "己", "寅": "甲", "卯": "乙", "辰": "戊", "巳": "丙",
         "午": "丁", "未": "己", "申": "庚", "酉": "辛", "戌": "戊", "亥": "壬"}
STAGE_ORDER = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"]
CHANGSHENG = {"甲": "亥", "乙": "午", "丙": "寅", "丁": "酉", "戊": "寅", "己": "酉",
              "庚": "巳", "辛": "子", "壬": "申", "癸": "卯"}


def di_shi(dm: str, z: str) -> str:
    """十二长生（经典表独立重算：阳顺阴逆）。"""
    i = ZHI.index(CHANGSHENG[dm])
    step = 1 if YY[dm] == 1 else -1
    for k, name in enumerate(STAGE_ORDER):
        if ZHI[(i + step * k) % 12] == z:
            return name
    return ""
GAN60 = "甲乙丙丁戊己庚辛壬癸"
ZHI60 = "子丑寅卯辰巳午未申酉戌亥"


def gz_step(gz: str, n: int) -> str:
    i = GAN60.index(gz[0]) + n
    j = ZHI60.index(gz[1]) + n
    return GAN60[i % 10] + ZHI60[j % 12]


def shishen(day_gan: str, other: str) -> str:
    de, oe = (WX_G[day_gan], YY[day_gan]), (WX_G[other], YY[other])
    same = de[1] == oe[1]
    if de[0] == oe[0]:
        return "比肩" if same else "劫财"
    if SHENG[de[0]] == oe[0]:
        return "食神" if same else "伤官"
    if SHENG[oe[0]] == de[0]:
        return "正印" if not same else "偏印"
    if KE[de[0]] == oe[0]:
        return "正财" if not same else "偏财"
    return "正官" if not same else "七杀"


# ---- 统计 ----
MODS = ["排盘四柱", "藏干", "十神天干", "十神藏干", "空亡", "星运", "命宫",
        "大运序列", "大运起运", "小运", "五行统计", "神煞", "格局", "流年干支",
        "流年十神", "流年神煞", "岁运角标", "流岁↔大运", "流月", "流日", "流时"]
stat = {m: [0, 0, []] for m in MODS}
diverge = {}


def check(mod, got, want, ctx):
    if got == want:
        stat[mod][0] += 1
    else:
        stat[mod][1] += 1
        if len(stat[mod][2]) < 3:
            stat[mod][2].append(f"{ctx}: 参考{want} / 引擎{got}")


def ref_pillars(y, m, d, hh, mi, sect=1):
    ec = Solar.fromYmdHms(y, m, d, hh, mi, 0).getLunar().getEightChar()
    ec.setSect(sect)
    return [ec.getYear(), ec.getMonth(), ec.getDay(), ec.getTime()], ec, \
        Solar.fromYmdHms(y, m, d, hh, mi, 0).getLunar()


FIXED = [(1984, 2, 4, 23, 10, "男"), (1984, 2, 4, 22, 50, "女"),
         (2024, 2, 10, 0, 0, "男"), (2023, 3, 22, 10, 0, "女"),
         (1901, 1, 1, 0, 0, "男"), (2099, 12, 31, 23, 59, "女"),
         (2033, 11, 1, 13, 5, "男"), (2000, 2, 5, 0, 30, "女"),
         (1949, 10, 1, 15, 0, "男")]
random.seed(20261031)
CASES = list(FIXED)
for _ in range(60):
    CASES.append((random.randint(1901, 2099), random.randint(1, 12), random.randint(1, 28),
                  random.randint(0, 23), random.choice([0, 7, 15, 23, 30, 45]),
                  random.choice(["男", "女"])))

print(f"开始验证：{len(CASES)} 例（含 {len(FIXED)} 个边界用例）……")
for n, (y, m, d, hh, mi, gender) in enumerate(CASES):
    ctx = f"{y}-{m:02d}-{d:02d} {hh:02d}:{mi:02d} {gender}"
    try:
        p = server.bazi_paipan(y, m, d, hh, mi, gender, None, None)
    except Exception as exc:
        for mod in MODS[:13]:
            check(mod, "异常", "", f"{ctx} {type(exc).__name__}:{exc}")
        continue
    qz = p["四柱"]
    ref, ec, lunar = ref_pillars(y, m, d, hh, mi)
    got = [qz[k] for k in POS]

    # 1 排盘四柱
    check("排盘四柱", got, ref, ctx)

    # 2 藏干（全表 vs lunar_python 通表，问真/通行口径）
    ref_hide = [ec.getYearHideGan(), ec.getMonthHideGan(), ec.getDayHideGan(), ec.getTimeHideGan()]
    for i, pos in enumerate(POS):
        h = p["藏干"][pos]
        check("藏干", h["本"] + h["中"] + h["余"], ref_hide[i], f"{ctx} {pos}全表")

    # 3 十神天干
    ref_gan = {"年": ec.getYearShiShenGan(), "月": ec.getMonthShiShenGan(),
               "时": ec.getTimeShiShenGan()}
    for pos in ("年", "月", "时"):
        check("十神天干", p["十神"]["天干"][pos], ref_gan[pos], ctx)

    # 4 十神藏干（本气 vs 参考库；全量 vs 独立函数）
    ref_zhi = [ec.getYearShiShenZhi(), ec.getMonthShiShenZhi(),
               ec.getDayShiShenZhi(), ec.getTimeShiShenZhi()]
    for i, pos in enumerate(POS):
        hg = p["藏干"][pos]["本"] + p["藏干"][pos]["中"] + p["藏干"][pos]["余"]
        got_map = p["十神"]["藏干"][pos]
        got_gods = [got_map[g] for g in hg]
        want_gods = [shishen(qz["日"][0], g) for g in hg]
        check("十神藏干", got_gods, want_gods, ctx)
        if ref_zhi[i] and got_gods:
            check("十神藏干", [got_gods[0]], [ref_zhi[i][0]], f"{ctx} {pos}本气")

    # 5 空亡
    check("空亡", sorted(p["空亡"]["空亡"]), sorted(list(lunar.getDayXunKong())), ctx)
    check("空亡", p["空亡"]["旬首"], lunar.getDayXun(), ctx)

    # 6 星运（十二长生）
    ref_ds = [ec.getYearDiShi(), ec.getMonthDiShi(), ec.getDayDiShi(), ec.getTimeDiShi()]
    check("星运", [p["星运"][k] for k in POS], ref_ds, ctx)

    # 7 命宫（问真/通行口径：节气月支序＋时支序 → 14/26 反推）
    mg = p["命宫"]
    MZ = ("", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑")
    off = MZ.index(qz["月"][1]) + MZ.index(qz["时"][1])
    off = 26 - off if off >= 14 else 14 - off
    check("命宫", mg["支"], MZ[off], f"{ctx} 命宫公式")
    ec_mg = Solar.fromYmdHms(y, m, d, hh, mi, 0).getLunar().getEightChar()
    ec_mg.setSect(1)
    check("命宫", mg["命宫"], ec_mg.getMingGong(), f"{ctx} 对 lunar")

    # 8 大运序列/起运（男女各测）
    yse = YunSuiEngine(ENG2)
    q2 = ENG2.pillars_from_datetime(y, m, d, hh, mi)
    for gcode, gname in ((1, "男"), (0, "女")):
        ys = yse.dayun(q2["四柱"], gname, q2["节气距离"], birth_year=y)
        got_dy = [s["干支"] for s in ys["大运（前八步）"]]
        ry = ec.getYun(gcode)
        want_dy = [x.getGanZhi() for x in ry.getDaYun()]
        want_dy = [g for g in want_dy if g][:8]
        check("大运序列", got_dy, want_dy, f"{ctx}({gname})")
        if gname == gender:
            check("大运起运",
                  (p["大运"]["起运"]["岁"], p["大运"]["起运"]["月"]),
                  (ry.getStartYear(), ry.getStartMonth()), f"{ctx}({gname})")

    # 9 小运（醉醒子独立重算）
    if gender:
        yang = qz["年"][0] in "甲丙戊庚壬"
        forward = (yang and gender == "男") or (not yang and gender == "女")
        step = 1 if forward else -1
        want_xy = [gz_step(qz["时"], step * (i + 1)) for i in range(10)]
        check("小运", p["小运"]["序列（一岁一步）"], want_xy, ctx)

    # 10 五行统计
    want_wx = {"金": 0, "木": 0, "水": 0, "火": 0, "土": 0}
    for k in POS:
        want_wx[WX_G[qz[k][0]]] += 1
        want_wx[WX_Z[qz[k][1]]] += 1
    got_wx = {k: p["五行统计"][k] for k in want_wx}
    check("五行统计", got_wx, want_wx, ctx)
    check("五行统计", sum(p["五行统计"][k] for k in want_wx), 8, ctx)

    # 11 神煞（经典表独立重算：年支＋日支双口径并集，与引擎口径一致）
    branches = {k: qz[k][1] for k in POS}
    yg, dg = GROUP_OF[branches["年"]], GROUP_OF[branches["日"]]
    tg = set(TIANYI[qz["年"][0]]) | set(TIANYI[qz["日"][0]])
    want_pos = {name: sorted([k for k in POS if branches[k] in tgt])
                for name, tgt in [("天乙贵人", tg)]}
    for name, table in (("驿马", YIMA), ("桃花（咸池）", TAOHUA),
                        ("华盖", HUAGAI), ("将星", JIANGXING)):
        tgt = {table[yg], table[dg]}
        want_pos[name] = sorted([k for k in POS if branches[k] in tgt])
    for name, want in want_pos.items():
        entry = (p["神煞"]["按神煞"] or {}).get(name)
        if entry is None:
            check("神煞", "缺失", name, ctx)
            continue
        check("神煞", sorted(entry["命中柱位"]), want, f"{ctx} {name}")
        check("神煞", entry["命中"], bool(want), f"{ctx} {name}.命中")

    # 12 格局（自洽 + 独立复算）
    g = p["格局"]
    mg = g["月令取格"]
    check("格局", mg["月支"], qz["月"][1], ctx)
    canggan = p["藏干"]["月"]
    check("格局", (mg["藏干"]["本"], mg["藏干"]["中"], mg["藏干"]["余"]),
          ("".join(canggan["本"]), "".join(canggan["中"]), "".join(canggan["余"])), ctx)
    check("格局", mg["本气十神"], shishen(qz["日"][0], canggan["本"][0]), ctx)
    cands = mg.get("取格候选") or []
    if cands:
        check("格局", (cands[0]["来源"], cands[0]["十神"]),
              ("月令本气", mg["本气十神"]), ctx)
    gst = g.get("格局统计") or {}
    cheng, po = set(gst.get("成格") or []), set(gst.get("破格") or [])
    check("格局", sorted(cheng & po), [], ctx)
    check("格局", bool((g["用神"]["定神"] or {}).get("神")), True, f"{ctx} 用神非空")
    for e in g["格局判定"]:
        if not e.get("成格条件"):
            check("格局", "无条件", e["格"], ctx)

    # 13 运程钻取子样（每 4 例）：流年/流月/流日/流时/流岁↔大运
    if n % 4 == 0:
        try:
            yr = random.randint(y, min(y + 70, 2099))
            fy = server.bazi_flow("years", y, m, d, hh, mi, gender, year=yr)
            ln_gz_want = Solar.fromYmd(yr, 6, 1).getLunar().getYearInGanZhiByLiChun()
            for it in fy["流年"]:
                if it["年"] == yr:
                    check("流年干支", it["干支"], ln_gz_want, ctx)
                    check("流年十神", it["十神（干）"], shishen(qz["日"][0], it["干支"][0]), ctx)
                    check("流年十神", it["十神（支本气）"],
                          shishen(qz["日"][0], BENQI[it["干支"][1]]), ctx)
                    # 流年神煞（年支口径独立重算）
                    ss = list(it["神煞"])
                    want_ss = []
                    if it["干支"][1] == YIMA[GROUP_OF[branches["年"]]]:
                        want_ss.append("驿马")
                    if it["干支"][1] == TAOHUA[GROUP_OF[branches["年"]]]:
                        want_ss.append("桃花")
                    if it["干支"][1] in TIANYI[qz["年"][0]] or it["干支"][1] in TIANYI[qz["日"][0]]:
                        want_ss.append("贵人")
                    check("流年神煞", sorted(ss), sorted(want_ss), f"{ctx} {yr}")
                    # 岁运角标 ↔ 关系一致性
                    marks = it["标记"]
                    rels = it["关系"]
                    check("岁运角标", ("岁运并临" in marks),
                          (it["大运"] != "童限" and it["大运"] == it["干支"]), f"{ctx} {yr}")
                    check("岁运角标", ("真太岁" in marks), (it["干支"] == qz["日"]), f"{ctx} {yr}")
                    check("岁运角标", ("天克地冲" in marks),
                          any("天克地冲" in r["条件"] for r in rels), f"{ctx} {yr}")
                    for mk in marks:
                        ok = (mk == "岁运并临" and it["大运"] == it["干支"]) or \
                             (mk == "真太岁" and it["干支"] == qz["日"]) or \
                             (mk == "天克地冲" and any("天克地冲" in r["条件"] for r in rels)) or \
                             (mk in ("伏吟", "返吟"))
                        if not ok:
                            check("岁运角标", mk, "无对应关系命中", f"{ctx} {yr}")
            # 流岁 ↔ 大运
            rows = fy["大运（前八步）"]
            for s in fy["流岁（小运）"]:
                age = s["虚岁"]
                dy_of = next((r for r in rows if r["起始岁"] <= age < r["结束岁"]), None)
                want_dy_s = dy_of["干支"] if dy_of else "童限"
                check("流岁↔大运", s["对应大运"], want_dy_s, f"{ctx} 虚岁{age}")
            # 流月（12 个月柱 vs lunar_python）
            fm = server.bazi_flow("months", y, m, d, hh, mi, gender, year=yr)
            if len(fm["月"]) != 12:
                check("流月", len(fm["月"]), 12, ctx)
            for mm in fm["月"]:
                probe = datetime.strptime(mm["起"], "%Y-%m-%d %H:%M") + timedelta(minutes=10)
                ec2 = Solar.fromYmdHms(probe.year, probe.month, probe.day,
                                       probe.hour, probe.minute, 0).getLunar().getEightChar()
                ec2.setSect(1)
                check("流月", mm["干支"], ec2.getMonth(), f"{ctx} {mm['月名']}")
            # 流日/流时（随机 3 天）
            dd = date(yr, random.randint(1, 12), random.randint(1, 28))
            fd = server.bazi_flow("days", y, m, d, hh, mi, gender,
                                  d_from=dd.isoformat(), d_to=(dd + timedelta(days=2)).isoformat())
            for it in fd["日"]:
                dy_, dm_, dd_ = (int(x) for x in it["日期"].split("-"))
                ec3 = Solar.fromYmd(dy_, dm_, dd_).getLunar().getEightChar()
                ec3.setSect(1)
                check("流日", it["干支"], ec3.getDay(), f"{ctx} {it['日期']}")
            ft = server.bazi_flow("hours", y, m, d, hh, mi, gender, date_s=dd.isoformat())
            for it in ft["时"]:
                hh2 = {"早子": 0, "丑": 1, "寅": 3, "卯": 5, "辰": 7, "巳": 9, "午": 11,
                       "未": 13, "申": 15, "酉": 17, "戌": 19, "亥": 21, "晚子": 23}[it["时辰"]]
                ec4 = Solar.fromYmdHms(dd.year, dd.month, dd.day, hh2, 0, 0).getLunar().getEightChar()
                ec4.setSect(1)
                check("流时", it["干支"], ec4.getTime(), f"{ctx} {dd} {it['时辰']}")
                check("流时", it["星运"], di_shi(qz["日"][0], it["干支"][1]),
                      f"{ctx} {dd} {it['时辰']}.星运")
        except Exception as exc:
            check("流年干支", "异常", "", f"{ctx} {type(exc).__name__}:{exc}")

    if (n + 1) % 15 == 0:
        print(f"  … 已完成 {n + 1}/{len(CASES)} 例")

# ---- 纳音：60 甲子全表 vs lunar_python（从 1949-10-01 甲子日连续 60 天） ----
nayin_fail = 0
d0 = date(1949, 10, 1)
for i in range(60):
    dd = d0 + timedelta(days=i)
    ec5 = Solar.fromYmd(dd.year, dd.month, dd.day).getLunar().getEightChar()
    ec5.setSect(1)
    gz = ec5.getDay()
    mine = server._NAYIN.get(gz, "")
    if mine != ec5.getDayNaYin():
        nayin_fail += 1
        if nayin_fail <= 3:
            print(f"  ✗ 纳音 {gz}: 参考{ec5.getDayNaYin()} / 引擎表{mine}")
stat["纳音表"] = [60 - nayin_fail, nayin_fail, []]

print()
total_p = total_f = 0
for mod in MODS + ["纳音表"]:
    ps, fs, samples = stat[mod]
    total_p += ps
    total_f += fs
    flag = "✓" if fs == 0 else "✗"
    print(f"  {flag} {mod}: {ps} 通过, {fs} 不一致")
    for s in samples:
        print(f"      {s}")
print(f"\n已知口径差异（声明保留，非错误）：{diverge}")
print(f"合计：{total_p} 通过，{total_f} 不一致")
sys.exit(1 if total_f else 0)
