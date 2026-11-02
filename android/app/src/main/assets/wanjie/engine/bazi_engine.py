# -*- coding: utf-8 -*-
"""四柱排盘引擎（三命通会体系）。

数据源：rules/*.json（仅加载 engine.loadable=true 的规则；门禁由 rules_loader 强制）。
输出原则：每个计算元素附 `依据`（规则 ID）；规则未覆盖或被门禁拦下的一律标注，不推断。

用法：
    python bazi_engine.py 1984-02-05 08:30            # 排盘
    python bazi_engine.py --analyze 丙午 庚子 壬午 丙午  # 四柱直析
"""
from __future__ import annotations

import datetime as dt
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "common"))

import calendar_layer as C  # noqa: E402
from rules_loader import load_rules  # noqa: E402

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
WUXING = dict(zip(GAN, "木木火火土土金金水水"))
WUXING_ZHI = dict(zip(ZHI, "水土木木土火火土金金土水"))
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}  # 我生
SHENG_WO = {"木": "水", "火": "木", "土": "火", "金": "土", "水": "金"}  # 生我
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}  # 我克
KE_WO = {"木": "金", "火": "水", "土": "木", "金": "火", "水": "土"}  # 克我
SANHE = {"寅午戌": "火", "申子辰": "水", "巳酉丑": "金", "亥卯未": "木"}
BRANCH_GROUP = {b: g for g in SANHE for b in g}  # 支 → 三合局名
FANG = {b: g for g in ("亥子丑", "寅卯辰", "巳午未", "申酉戌") for b in g}  # 支 → 方位组（孤辰寡宿）
# 十二节（定月建）；中气不换月
JIE = ["立春", "惊蛰", "清明", "立夏", "芒种", "小暑", "立秋", "白露", "寒露", "立冬", "大雪", "小寒"]
JIE_TO_MONTH = dict(zip(JIE, "寅卯辰巳午未申酉戌亥子丑"))
# 天德宫组（SSH-008：四正/四库/四生各配一组干，原文未逐支展开——通行-需注）
GONG = {}
for b in "子午卯酉":
    GONG[b] = "子午卯酉"
for b in "辰戌丑未":
    GONG[b] = "辰戌丑未"
for b in "寅申巳亥":
    GONG[b] = "寅申巳亥"


def gz_index(gz: str) -> int:
    """六十甲子序号（甲子=0）。"""
    g, z = gz[0], gz[1]
    if g not in GAN or z not in ZHI:
        raise ValueError(f"非法干支: {gz}")
    g_i, z_i = GAN.index(g), ZHI.index(z)
    for p in range(60):
        if p % 10 == g_i and p % 12 == z_i:
            return p
    raise AssertionError

def gz_from_index(p: int) -> str:
    return GAN[p % 10] + ZHI[p % 12]

def gz_step(gz: str, n: int) -> str:
    return gz_from_index((gz_index(gz) + n) % 60)

def year_gz_of_year(y: int) -> str:
    """公元 y 年的干支（立春后口径；年前属上一年干支由调用方处理）。"""
    return gz_from_index((y - 4) % 60)

def ten_god(day_gan: str, other: str) -> str:
    """十神判定（SS-005 公式）。"""
    a, b = WUXING[day_gan], WUXING[other]
    same = (GAN.index(day_gan) % 2) == (GAN.index(other) % 2)
    if a == b:
        return "比肩" if same else "劫财"
    if SHENG.get(a) == b:
        return "食神" if same else "伤官"
    if SHENG_WO.get(a) == b:
        return "偏印" if same else "正印"
    if KE.get(a) == b:
        return "偏财" if same else "正财"
    if KE_WO.get(a) == b:
        return "七杀" if same else "正官"
    raise AssertionError((day_gan, other))


class BaziEngine:
    def __init__(self, config: dict | None = None):
        self.rules = load_rules()
        self.index = {r["id"]: r for r in self.rules}
        cfg = {
            "year_basis": "lichun",       # SZ-001（正月初一换年可切 'lunar'）
            "day_boundary": "23:00",      # SZ-005 方案A
            "true_solar": False,          # SZ-006
        }
        cfg.update(config or {})
        self.config = cfg
        self._terms_cache: dict[int, dict] = {}

    # ---------- 命宫 ----------
    def ming_gong(self, month_zhi: str, hour_zhi: str, year_gan: str) -> dict:
        """命宫（SZ-016）：问真/通行口径——节气月支序＋时支序，14/26 反推宫支；宫干五虎遁。"""
        mz = ("", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑")
        mi = mz.index(month_zhi)
        ti = mz.index(hour_zhi)
        off = mi + ti
        off = 26 - off if off >= 14 else 14 - off
        zhi = mz[off]
        k = (GAN.index(year_gan) + 1) * 2 + off
        while k > 10:
            k -= 10
        return {"支": zhi, "干": GAN[k - 1], "命宫": GAN[k - 1] + zhi,
                "公式": "宫支=节气月支序＋时支序→14/26 反推；宫干五虎遁（问真/通行口径）",
                "口径": "节气月支法", "依据": ["SZ-016"]}

    # ---------- 起运 ----------
    @staticmethod
    def qiyun_from_span(start, end) -> dict:
        """起运（YS-002 通行口径，与问真/lunar_python 一致）：3日=1年、1日=4月、1时辰=10日。
        日差按日历日（不看时刻），时辰差不足一天时回拨一日，与主流实现一致。"""
        def zi(x):
            return 11 if x.hour == 23 else (x.hour + 1) // 2

        hd = zi(end) - zi(start)
        dd = (end.date() - start.date()).days
        if hd < 0:
            hd += 12
            dd -= 1
        mdiff = int(hd * 10 / 30)
        month = dd * 4 + mdiff
        day = hd * 10 - mdiff * 30
        year = month // 12
        month -= year * 12
        return {"岁": year, "月": month, "天": day,
                "文本": f"{year}岁{month}个月{day}天",
                "折算": "3日=1年，1日=4月，1时辰=10日（问真/通行口径）",
                "依据": ["YS-002"]}

    @staticmethod
    def qiyun_from_days(days: float) -> dict:
        """起运岁数（旧版小数折算，保留作兼容回退）。"""
        years = days / 3.0
        y = int(years)
        months = int(round((years - y) * 12))
        if months == 12:
            y += 1
            months = 0
        return {"岁": y, "月": months, "文本": f"{y}岁{months}个月",
                "折算": "3日=1年（36时辰=1年）", "依据": ["YS-002"]}

    # ---------- 小运 ----------
    def xiaoyun(self, pillars: dict, gender: str, method: str = "醉醒子", steps: int = 10) -> dict:
        """小运（YS-008）：古法（男丙寅顺/女壬申逆）或醉醒子（生时起、以年定顺逆）。"""
        if method == "古法":
            start = "丙寅" if gender == "男" else "壬申"
            step = 1 if gender == "男" else -1
            seq = [gz_step(start, step * i) for i in range(steps)]
        elif method == "醉醒子":
            yang = pillars["年"][0] in "甲丙戊庚壬"
            forward = (yang and gender == "男") or (not yang and gender == "女")
            step = 1 if forward else -1
            seq = [gz_step(pillars["时"], step * (i + 1)) for i in range(steps)]
        else:
            raise ValueError("method 须为 古法/醉醒子")
        return {"流派": method, "序列（一岁一步）": seq, "依据": ["YS-008"]}

    # ---------- 基础 ----------
    def rule(self, rid: str):
        r = self.index.get(rid)
        if r is None:
            raise KeyError(f"规则 {rid} 不存在或被门禁拦截（loadable=false）")
        return r

    def data(self, rid: str):
        return self.rule(rid).get("data")

    def _terms(self, y: int):
        if y not in self._terms_cache:
            self._terms_cache[y] = C.solar_terms(y)
        return self._terms_cache[y]

    # ---------- 排盘 ----------
    def pillars_from_datetime(self, y: int, m: int, d: int, hour: int, minute: int = 0) -> dict:
        """由出生时刻排四柱。年按立春（SZ-001），月按节气＋五虎遁（SZ-002/SZ-007），日时按日界约定（SZ-003/004/005）。"""
        moment = dt.datetime(y, m, d, hour, minute)
        # 年柱：最近一次立春
        lichun_list = [(self._terms(yy)["立春"], yy) for yy in (y - 1, y, y + 1)]
        lichun_list = [(t, yy) for t, yy in lichun_list if t <= moment]
        if not lichun_list:
            raise C.CalendarError("无法定位立春（年份越界）")
        _, year_y = max(lichun_list, key=lambda x: x[0])
        year_gz = year_gz_of_year(year_y)
        # 月柱：最近的『节』
        jie_list = []
        for yy in (y - 1, y, y + 1):
            terms = self._terms(yy)
            for name in JIE:
                jie_list.append((terms[name], name))
        jie_list = [(t, n) for t, n in jie_list if t <= moment]
        if not jie_list:
            raise C.CalendarError("无法定位节气月")
        jie_time, jie_name = max(jie_list, key=lambda x: x[0])
        month_zhi = JIE_TO_MONTH[jie_name]
        # 五虎遁（SZ-007）：年干 → 寅月干，顺推至月支
        wuhu = self.data("SZ-007")
        group = {"甲": "甲己", "己": "甲己", "乙": "乙庚", "庚": "乙庚", "丙": "丙辛", "辛": "丙辛",
                 "丁": "丁壬", "壬": "丁壬", "戊": "戊癸", "癸": "戊癸"}[year_gz[0]]
        yin_gan = wuhu[group][0]
        month_gan = GAN[(GAN.index(yin_gan) + (ZHI.index(month_zhi) - ZHI.index("寅")) % 12) % 10]
        month_gz = month_gan + month_zhi
        # 日柱/时柱（日界约定）
        day_gz, used_date = C.day_ganzhi(y, m, d, hour, minute, self.config["day_boundary"])
        hour_gz = C.hour_ganzhi(day_gz[0], hour, minute)
        # 距节（大运用，起运折算被门禁拦下，只给原始天数）
        next_jie = min((t for t, _ in jie_list_all(self._terms, y) if t > moment), default=None)
        prev_jie = jie_time
        lunar = C.solar_to_lunar(y, m, d)
        mg = self.ming_gong(month_gz[1], hour_gz[1], year_gz[0])
        return {
            "输入": {"datetime": moment.isoformat(), "config": dict(self.config)},
            "四柱": {"年": year_gz, "月": month_gz, "日": day_gz, "时": hour_gz},
            "命宫": mg,
            "历法校验": lunar["校验"],
            "月柱依据": {"节": jie_name, "交节时刻": jie_time.isoformat(), "规则": ["SZ-002", "SZ-007"]},
            "年柱依据": {"立春": max(t for t, _ in lichun_list).isoformat(), "规则": ["SZ-001"]},
            "日时依据": {"实际采用日期": used_date.isoformat(), "规则": ["SZ-003", "SZ-004", "SZ-005"]},
            "节气距离": {
                "出生时刻": moment.isoformat(),
                "上一节": prev_jie.isoformat(),
                "下一节": next_jie.isoformat() if next_jie else None,
                "距上一节天数": round((moment - prev_jie).total_seconds() / 86400, 4),
                "距下一节天数": round((next_jie - moment).total_seconds() / 86400, 4) if next_jie else None,
                "起运折算": "已启用（YS-002，2026-10-28 与劝学网本互校解锁）；起运岁数见『大运.起运』",
            },
        }

    # ---------- 四柱分析 ----------
    def analyze(self, year_gz: str, month_gz: str, day_gz: str, hour_gz: str,
                gender: str | None = None) -> dict:
        for gz in (year_gz, month_gz, day_gz, hour_gz):
            gz_index(gz)  # 校验合法性
        pillars = {"年": year_gz, "月": month_gz, "日": day_gz, "时": hour_gz}
        day_gan = day_gz[0]
        month_zhi = month_gz[1]
        out: dict = {"四柱": pillars, "日主": day_gan, "依据": []}

        # 藏干（CG-007 通行口径；CG-003 三命原文归纳保留备查）
        canggan = self.data("CG-007")
        hid = {}
        for pz in ("年", "月", "日", "时"):
            z = pillars[pz][1]
            hid[pz] = {"支": z, **canggan[z]}
        out["藏干"] = hid
        out["依据"].append("CG-007")

        # 十神（SS-005）：天干 + 藏干
        gods = {"天干": {}, "藏干": {}}
        for pz in ("年", "月", "时"):
            gods["天干"][pz] = ten_god(day_gan, pillars[pz][0])
        for pz in ("年", "月", "日", "时"):
            gods["藏干"][pz] = {s: ten_god(day_gan, s) for s in
                                (hid[pz]["本"] + hid[pz]["中"] + hid[pz]["余"])}
        out["十神"] = gods
        out["依据"].append("SS-005")

        # 空亡（KW-002）：以日柱定旬
        p = gz_index(day_gz)
        xun_gz = gz_from_index(p - p % 10)
        voids = self.data("KW-002")[xun_gz]
        hit = [pz for pz in ("年", "月", "日", "时") if pillars[pz][1] in voids]
        out["空亡"] = {"旬首": xun_gz, "空亡": voids, "落空柱位": hit}
        out["依据"].append("KW-002")

        # 五行个数统计（八字符；事实层非断语）
        from collections import Counter
        cnt = Counter(WUXING[gz[0]] for gz in pillars.values())
        cnt.update(WUXING_ZHI[gz[1]] for gz in pillars.values())
        out["五行统计"] = {"金": cnt.get("金", 0), "木": cnt.get("木", 0), "水": cnt.get("水", 0),
                      "火": cnt.get("火", 0), "土": cnt.get("土", 0),
                      "缺": [wx for wx in ("金", "木", "水", "火", "土") if not cnt.get(wx, 0)]}

        # 禄/羊刃/金舆/驿马
        lu = self.data("LM-001")
        ren = self.data("YR-002")
        res = {
            "日干禄": lu[day_gan], "年干禄": lu[year_gz[0]],
            "日干羊刃": ren[day_gan]["羊刃"], "日干飞刃": ren[day_gan]["飞刃"],
            "金舆（禄前二辰）": ZHI[(ZHI.index(lu[day_gan]) + 2) % 12],
        }
        for base, key in (("年支", year_gz[1]), ("日支", day_gz[1])):
            res[f"驿马·{base}"] = self.data("LM-003")[BRANCH_GROUP[key]]
        out["禄马刃"] = res
        out["依据"] += ["LM-001", "LM-002", "LM-003", "YR-002"]

        # 神煞（shensha_engine：日柱/年支/日干/月支四系，逐条附依据；年/日双口径并列）
        from shensha_engine import ShenshaEngine
        out["神煞"] = ShenshaEngine(self).compute(pillars, hid, gender=gender)
        out["依据"].append("SSH-086")

        # 日时命式库
        out["日时命式"] = self.lookup_dayhour(day_gan, hour_gz[1], hour_gz[0])

        # 格局候选（机械可判部分，保留兼容字段）
        out["格局候选"] = self.pattern_candidates(pillars, hid)

        # 完整格局引擎：月令取格＋身强弱＋用神＋成格/破格＋分歧并列
        from pattern_engine import PatternEngine
        out["格局"] = PatternEngine(self, self.config).assess(pillars, hid)

        # 十神/宫位含义：关系、人、事、物、正负、物质/精神层面
        from meaning_engine import MeaningEngine
        out["含义"] = MeaningEngine(self, self.config).compute(pillars, hid)

        out["说明"] = ("格局层＝机械候选（格局候选）＋完整判定（格局）；成格/破格逐条列条件与破格因素，"
                       "岁运条件标『待岁运』；分歧项并列、不择一。含义层为十神/宫位取象。")
        return out

    # ---------- 日时命式库 ----------
    def lookup_dayhour(self, day_gan: str, hour_zhi: str, hour_gan: str = "") -> dict:
        """按日干＋时支查卷八九命式库；辛日缺节用 MS-004 易藏本补录。"""
        lib = self.data("MS-003")
        hits = [e for e in lib
                if e["命式"].startswith(f"{day_gan}日") and e["命式"].endswith(f"{hour_zhi}时")]
        if not hits and day_gan == "辛" and hour_zhi in ("寅", "卯", "未", "亥"):
            sup = self.data("MS-004") or []
            group = f"辛{hour_gan}{hour_zhi}" if hour_gan else None
            picked = [e for e in sup if e.get("组") == group]
            return {"命中": [], "补录（易藏本）": picked,
                    "说明": "知命书院本缺失，据易藏本《三命通会》补录；非原卷八九表"}
        return {"命中": hits}

    # ---------- 格局候选 ----------
    def pattern_candidates(self, pillars: dict, hid: dict) -> list[dict]:
        cands = []
        day_gz, hour_gz = pillars["日"], pillars["时"]
        day_gan, hour_zhi = day_gz[0], hour_gz[1]
        month_zhi = pillars["月"][1]
        branches = [pillars[pz][1] for pz in ("年", "月", "日", "时")]
        stems = [pillars[pz][0] for pz in ("年", "月", "日", "时")]
        lu = self.data("LM-001")

        def add(name, hit, rule, cond=""):
            cands.append({"格": name, "命中": hit, "规则": rule, "条件": cond})

        add("天元一气", len(set(stems)) == 1, "GJ-070", "四天干一气")
        groups = {BRANCH_GROUP[b] for b in branches}
        add("四位纯全", len(set(branches)) == 4 and len(groups) == 1 and
            set(branches) in (set("寅申巳亥"), set("子午卯酉"), set("辰戌丑未")), "GJ-069", "四支全同组")
        n_zi, n_wu = branches.count("子"), branches.count("午")
        add("子午双包", (n_zi >= 2 and n_wu >= 1) or (n_wu >= 2 and n_zi >= 1), "GJ-120", "两子两午/两午包一子/两子包一午")
        add("日贵", day_gz in self.data("GJ-117"), "GJ-117", "丁酉/丁亥/癸巳/癸卯")
        add("日德", day_gz in self.data("GJ-118"), "GJ-118", "甲寅/丙辰/戊辰/庚辰/壬戌")
        add("魁罡", day_gz in self.data("GJ-116"), "GJ-116", "庚辰/壬辰/戊戌/庚戌")
        add("日刃", day_gz in self.data("YR-014"), "YR-014", "戊午/丙午/壬子")
        add("六乙鼠贵", day_gan == "乙" and hour_gz == "丙子", "GJ-110", "乙日丙子时")
        add("六阴朝阳", day_gan == "辛" and hour_gz == "戊子", "GJ-109", "辛日戊子时")
        add("六壬趋艮", day_gan == "壬" and hour_gz == "甲寅", "GJ-114", "壬日甲寅时")
        add("六甲趋乾", day_gan == "甲" and "亥" in branches, "GJ-115", "甲日见亥（尤亥时）")
        add("飞天禄马", day_gz in ("庚子", "壬子", "辛亥", "癸亥"), "GJ-121", "四日生亥子月、柱无财官")
        add("倒冲禄", day_gz in ("丙午", "丁巳"), "GJ-122", "夏日纯阳、支多")
        add("财官双美", day_gz in self.data("WG2-001")["正格"], "WG2-001", "壬午/癸巳日")
        add("金神格", hour_gz in self.data("ZP-001")["三时"], "ZP-001", "癸酉/己巳/乙丑时；要制伏喜火乡")
        add("日禄归时", lu[day_gan] == hour_zhi, "GJ-111", "禄在时支；柱无官星为正")
        add("建禄格", lu[day_gan] == month_zhi, "GJ-050", "月支为日干禄")
        add("阳刃格", month_zhi == self.data("YR-002")[day_gan]["羊刃"], "YR-012", "月支为日干刃（五阳干口径）")
        add("曲直（候）", day_gan in "甲乙" and all(b in branches for b in "亥卯未"), "GJ-060", "亥卯未全＋柱有亥")
        add("炎上（候）", day_gan in "丙丁" and all(b in branches for b in "寅午戌"), "GJ-061", "寅午戌全＋柱有寅")
        add("从革（候）", day_gan in "庚辛" and all(b in branches for b in "巳酉丑"), "GJ-062", "巳酉丑全（原文以辛日立论）")
        add("润下（候）", day_gan in "壬癸" and all(b in branches for b in "申子辰"), "GJ-063", "申子辰全")
        add("稼穑（候）", day_gan in "戊己" and month_zhi in "辰戌丑未", "GJ-064", "四季月生")
        # 月令本气十神 → 正格候选
        mg = hid["月"]["本"]
        for s in mg:
            god = ten_god(day_gan, s)
            name = {"正官": "正官格", "七杀": "偏官格", "正印": "正印格", "偏印": "偏印格",
                    "正财": "正财格", "偏财": "偏财格", "食神": "食神格", "伤官": "伤官格",
                    "比肩": "建禄/月劫（候）", "劫财": "月劫格"}.get(god)
            if name:
                add(name, True, "YL-005", f"月支本气{s}＝{god}")
        return cands

    # ---------- 大运（方向、序列与起运） ----------
    def dayun_direction(self, pillars: dict, gender: str, jie_days: dict | None = None) -> dict:
        ys1 = self.rule("YS-001")
        yang = pillars["年"][0] in "甲丙戊庚壬"
        forward = (yang and gender == "男") or (not yang and gender == "女")
        step = 1 if forward else -1
        seq = [gz_step(pillars["月"], step * (i + 1)) for i in range(8)]
        out = {
            "方向": "顺行" if forward else "逆行",
            "依据": ["YS-001"],
            "年干阴阳": "阳" if yang else "阴",
            "大运序列（前八步）": seq,
        }
        if jie_days:
            try:
                m0 = dt.datetime.fromisoformat(jie_days["出生时刻"])
                a = dt.datetime.fromisoformat(jie_days["上一节"])
                b = (dt.datetime.fromisoformat(jie_days["下一节"])
                     if jie_days.get("下一节") else None)
                if forward and b:
                    out["起运"] = self.qiyun_from_span(m0, b)
                elif not forward:
                    out["起运"] = self.qiyun_from_span(a, m0)
                else:
                    out["起运"] = "无法计算（超出节气数据范围）"
            except (KeyError, TypeError, ValueError):
                days = jie_days.get("距下一节天数") if forward else jie_days.get("距上一节天数")
                if days is None:
                    out["起运"] = "无法计算（超出节气数据范围）"
                else:
                    out["起运"] = self.qiyun_from_days(days)
        else:
            out["起运"] = "未计算（排盘时未传节气距离）；YS-002 已校勘解锁，由排盘结果自动给出"
        return out


def jie_list_all(terms_fn, y):
    out = []
    for yy in (y - 1, y, y + 1):
        t = terms_fn(yy)
        for name in JIE:
            out.append((t[name], name))
    return out


def main() -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="+", help="YYYY-MM-DD HH:MM 或 四柱干支四个")
    ap.add_argument("--analyze", action="store_true", help="按四柱干支直接分析（跳过排盘）")
    ap.add_argument("--gender", choices=["男", "女"], default=None)
    ap.add_argument("--boundary", choices=["23:00", "00:00"], default=None)
    ap.add_argument("--year", type=int, default=None, help="加算流年（例：2026）")
    ap.add_argument("--birth-year", type=int, default=None, help="--analyze 时指定出生年（流年取大运用）")
    ap.add_argument("--dayun", default=None, help="手工指定当前大运干支（如 辛未；可选）")
    ap.add_argument("--yong-shen", default=None, help="手工指定用神（如 正官；默认由格局层取）")
    args = ap.parse_args()
    cfg = {}
    if args.boundary:
        cfg["day_boundary"] = args.boundary
    eng = BaziEngine(cfg)
    birth_year = args.birth_year
    jie_days = None
    if args.analyze:
        if len(args.target) != 4:
            ap.error("--analyze 需要四个干支（年 月 日 时）")
        ygz, mgz, dgz, hgz = args.target
        qz = {"年": ygz, "月": mgz, "日": dgz, "时": hgz}
        result = eng.analyze(ygz, mgz, dgz, hgz, gender=args.gender)
    elif len(args.target) == 2:
        d_part, t_part = args.target
        y, m, d = (int(x) for x in d_part.split("-"))
        h, mi = (int(x) for x in t_part.split(":"))
        result = eng.pillars_from_datetime(y, m, d, h, mi)
        qz = result["四柱"]
        birth_year = birth_year or y
        jie_days = result["节气距离"]
        result.update(eng.analyze(qz["年"], qz["月"], qz["日"], qz["时"], gender=args.gender))
        if args.gender:
            from yunsui_engine import YunSuiEngine
            yse = YunSuiEngine(eng)
            ys = args.yong_shen or (result.get("格局", {}).get("用神", {}) or {}).get("定神", {}).get("神")
            result["大运"] = yse.dayun(qz, args.gender, jie_days, birth_year=birth_year,
                                       yong_shen=ys)
            result["小运"] = eng.xiaoyun(qz, args.gender)
    elif len(args.target) == 4:
        ygz, mgz, dgz, hgz = args.target
        qz = {"年": ygz, "月": mgz, "日": dgz, "时": hgz}
        result = eng.analyze(ygz, mgz, dgz, hgz, gender=args.gender)
    else:
        ap.error("需要 'YYYY-MM-DD HH:MM' 或 四个干支")
    if args.year:
        from yunsui_engine import YunSuiEngine
        ys = args.yong_shen or (result.get("格局", {}).get("用神", {}) or {}).get("定神", {}).get("神")
        result["流年"] = YunSuiEngine(eng).liunian(
            qz, args.year, gender=args.gender, birth_year=birth_year,
            jie_days=jie_days, dayun_gz=args.dayun, yong_shen=ys,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
