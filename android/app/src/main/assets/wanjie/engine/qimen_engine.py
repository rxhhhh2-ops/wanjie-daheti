# -*- coding: utf-8 -*-
"""奇门遁甲·时家排盘引擎（定局＋布局；不含断语/用神/法术）。

接口与规则见 knowledge/04-奇门遁甲/排盘引擎接口与黄金用例.md。
黄金用例见 tools/cases/qimen_cases.json（tools/build_qimen_cases.py 生成）。

设计要点：
  - 历法只消费 tools/common/calendar_layer.py 的结论（现代年份）；
    历史年份（<1900）用儒略日连续干支公式 + 原文交节日期，供用例复算。
  - 转盘一律按八宫环序 [坎1,艮8,震3,巽4,离9,坤2,兑7,乾6]；禁止宫数线性加减。
  - 直使按宫数顺/逆飞（不入中五），门盘随直使目标宫按环序旋转。
  - 每条结果带 source/level；异说带 pai。
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from dataclasses import dataclass, asdict, field
from functools import lru_cache
from typing import Optional

# 允许 tools/ 下直接运行
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
from common import calendar_layer as cal  # noqa: E402

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
RING = [1, 8, 3, 4, 9, 2, 7, 6]
GONG_SEQ = [1, 2, 3, 4, 6, 7, 8, 9]          # 宫数序，不入中五
STAR_HOME = {1: "天蓬", 2: "天芮", 3: "天冲", 4: "天辅", 5: "天禽",
             6: "天心", 7: "天柱", 8: "天任", 9: "天英"}
DOOR_HOME = {1: "休门", 2: "死门", 3: "伤门", 4: "杜门", 6: "开门",
             7: "惊门", 8: "生门", 9: "景门"}
YI = ["戊", "己", "庚", "辛", "壬", "癸"]
QI = ["丁", "丙", "乙"]
XUN_YI = {"甲子": "戊", "甲戌": "己", "甲申": "庚", "甲午": "辛", "甲辰": "壬", "甲寅": "癸"}
XUN_KONG = {"甲子": ("戌", "亥"), "甲戌": ("申", "酉"), "甲申": ("午", "未"),
            "甲午": ("辰", "巳"), "甲辰": ("寅", "卯"), "甲寅": ("子", "丑")}
# 驿马：时支三合局 → 马星
MA_XING = {"申": "寅", "子": "寅", "辰": "寅", "寅": "申", "午": "申", "戌": "申",
           "巳": "亥", "酉": "亥", "丑": "亥", "亥": "巳", "卯": "巳", "未": "巳"}
JU_TABLE = {
    "冬至": (1, 7, 4), "小寒": (2, 8, 5), "大寒": (3, 9, 6),
    "立春": (8, 5, 2), "雨水": (9, 6, 3), "惊蛰": (1, 7, 4),
    "春分": (3, 9, 6), "清明": (4, 1, 7), "谷雨": (5, 2, 8),
    "立夏": (4, 1, 7), "小满": (5, 2, 8), "芒种": (6, 3, 9),
    "夏至": (9, 3, 6), "小暑": (8, 2, 5), "大暑": (7, 1, 4),
    "立秋": (2, 5, 8), "处暑": (1, 4, 7), "白露": (9, 3, 6),
    "秋分": (7, 1, 4), "寒露": (6, 9, 3), "霜降": (5, 8, 2),
    "立冬": (6, 9, 3), "小雪": (5, 8, 2), "大雪": (4, 7, 1),
}
YANG_TERMS = ["冬至", "小寒", "大寒", "立春", "雨水", "惊蛰",
              "春分", "清明", "谷雨", "立夏", "小满", "芒种"]
YIN_TERMS = ["夏至", "小暑", "大暑", "立秋", "处暑", "白露",
             "秋分", "寒露", "霜降", "立冬", "小雪", "大雪"]
TERM_ORDER = YANG_TERMS + YIN_TERMS          # 自冬至起
YUAN_NAME = ["上", "中", "下"]

# 八神系
SHEN_SETS = {
    "yuding": ["值符", "螣蛇", "太阴", "六合", "朱雀", "白虎", "九地", "九天"],
    "baihu":  ["值符", "螣蛇", "太阴", "六合", "白虎", "玄武", "九地", "九天"],
    "goutian": ["值符", "螣蛇", "太阴", "六合", "勾陈", "朱雀", "九地", "九天"],
    "jiu":    ["值符", "螣蛇", "太阴", "六合", "勾陈", "太常", "朱雀", "九地", "九天"],
}


@dataclass(frozen=True)
class QimenConfig:
    ding_ju: str = "chaibu"        # chaibu(当前节气，主流)|zhirun_9|zhirun_7|zhirun_10|xianshu|qiyu
    jigong: str = "kun2"           # kun2|yang2yin8|siwei|none
    bushen: str = "baihu"          # baihu(主流)|yuding|goutian|jiu
    shen_bufa: str = "ring"        # ring|fly9
    menpo: str = "men_zhi"
    shigan_mu: str = "main"
    ding_mu: str = "liu"
    zhishi_bufa: str = "gongshu"
    day_boundary: str = "23:00"
    true_solar_time: bool = False
    longitude: float = 120.0

    def fingerprint(self):
        import hashlib
        raw = json.dumps(asdict(self), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()[:12]


# ---------- 干支（儒略日连续公式，任意年份） ----------
_REF = {}


def _jdn(y, m, d):
    a = (14 - m) // 12
    y2 = y + 4800 - a
    m2 = m + 12 * a - 3
    return d + (153 * m2 + 2) // 5 + 365 * y2 + y2 // 4 - y2 // 100 + y2 // 400 - 32045


def _ref_day_gz():
    """用 lunar_python 取一个现代锚点（2000-01-01），换算成儒略日偏移。"""
    if "off" in _REF:
        return _REF["off"]
    gz, _ = cal.day_ganzhi(2000, 1, 1)
    idx = (GAN.index(gz[0])) % 10
    # 60 甲子序
    i60 = next(i for i in range(60) if GAN[i % 10] == gz[0] and ZHI[i % 12] == gz[1])
    _REF["off"] = (_jdn(2000, 1, 1), i60)
    return _REF["off"]


def day_gz_any(y, m, d):
    ref_jdn, ref_i = _ref_day_gz()
    i = (ref_i + (_jdn(y, m, d) - ref_jdn)) % 60
    return GAN[i % 10] + ZHI[i % 12]


def gz_index(gz):
    return next(i for i in range(60) if GAN[i % 10] == gz[0] and ZHI[i % 12] == gz[1])


def is_futou(gz):
    return gz[0] in ("甲", "己")


def futou_date(d: dt.date):
    for k in range(10):
        dd = d - dt.timedelta(days=k)
        if is_futou(day_gz_any(dd.year, dd.month, dd.day)):
            return dd
    raise RuntimeError("符头查找失败")


def yuan_from_zhi(z):
    if z in "子午卯酉":
        return "上"
    if z in "寅申巳亥":
        return "中"
    return "下"


def xun_shou(hour_gz):
    i = gz_index(hour_gz)
    return ["甲子", "甲戌", "甲申", "甲午", "甲辰", "甲寅"][i // 10]


def xun_delta(hour_gz):
    return gz_index(hour_gz) % 10


# ---------- 定局 ----------
@lru_cache(maxsize=256)
def _terms_year(y: int):
    try:
        return tuple(cal.solar_terms(y).items())
    except Exception:
        return tuple()


def build_terms(year: int):
    """返回按时间排序的 [(name, datetime)]，覆盖 year-1..year+1。"""
    out = []
    for y in (year - 1, year, year + 1):
        out.extend(_terms_year(y))
    out.sort(key=lambda x: x[1])
    return out


def assign_term(futou: dt.date, terms):
    """符头归节：符头在节前 9 日、节后 5 日内；返回 (term_name, term_datetime, state, days)。"""
    best = None
    for name, td in terms:
        diff = (td.date() - futou).days
        if -5 <= diff <= 8:                       # 符头在节前 8 日（超九日）/ 节后 5 日内
            if best is None or abs(diff) < abs(best[2]):
                best = (name, td, diff)
    if best is None:
        # 退化：节间距偶有 >14 日，窗口出现空档，取日期最近的节
        name, td = min(terms, key=lambda x: abs((x[1].date() - futou).days))
        diff = (td.date() - futou).days
        return name, td, ("超神" if diff > 0 else ("正授" if diff == 0 else "接气")), \
            (diff + 1 if diff > 0 else -diff)
    name, td, diff = best
    if diff > 0:
        return name, td, "超神", diff + 1        # 原文按含首尾计（"超九日"）
    if diff == 0:
        return name, td, "正授", 0
    return name, td, "接气", -diff


def term_dun(name):
    return "阳" if name in YANG_TERMS else "阴"


def ding_ju_pure(term_name, term_dt, futou: dt.date, config: QimenConfig, forced_state=None):
    """纯定局：给定节气与符头，返回 dict（供历史用例与日历路径共用）。"""
    fgz = day_gz_any(futou.year, futou.month, futou.day)
    yuan = yuan_from_zhi(fgz[1])
    # 超神/接气看上元符头：中元退 5 日、下元退 10 日
    f0 = futou - dt.timedelta(days={"上": 0, "中": 5, "下": 10}[yuan])
    # 原文"超九日/接五日"用含首尾的日数：超神 = 日差 + 1
    diff = (term_dt.date() - f0).days
    if forced_state:
        state, days = forced_state, 0
    elif diff > 0:
        state, days = "超神", diff + 1
    elif diff == 0:
        state, days = "正授", 0
    else:
        state, days = "接气", -diff
    thr = {"zhirun_9": 9, "zhirun_7": 7, "zhirun_10": 10}.get(config.ding_ju)
    run = False
    ju_term = term_name
    if (not forced_state) and thr and state == "超神" and days >= thr and term_name in ("夏至", "冬至"):
        run = True
        ju_term = "芒种" if term_name == "夏至" else "大雪"
        state = "闰奇"
    ju = JU_TABLE[ju_term][YUAN_NAME.index(yuan)]
    return {
        "term": term_name, "term_time": term_dt.isoformat(sep=" "),
        "futou": futou.isoformat(), "futou_gz": fgz,
        "yuan": yuan, "state": state, "chao_days": round(days, 1),
        "run": run, "ju_term": ju_term, "dun": term_dun(ju_term), "ju": ju,
    }


def ding_ju(d: dt.date, config: QimenConfig, now: dt.datetime | None = None):
    terms = build_terms(d.year)
    f = futou_date(d)
    if config.ding_ju in ("chaibu", "xianshu"):
        # 拆补/时宪口径：按交节时刻换局（分钟级），局＝当前节气＋符头元
        t = now if now is not None else dt.datetime.combine(d, dt.time(12, 0))
        cur = None
        for name, td in terms:
            if td <= t:
                cur = (name, td)
            else:
                break
        if cur is None:
            cur = terms[0]
        label = "拆补" if config.ding_ju == "chaibu" else "时宪书"
        return ding_ju_pure(cur[0], cur[1], f, config, forced_state=label)
    fgz = day_gz_any(f.year, f.month, f.day)
    yuan = yuan_from_zhi(fgz[1])
    f0 = f - dt.timedelta(days={"上": 0, "中": 5, "下": 10}[yuan])
    name, td, state, days = assign_term(f0, terms)   # 上元符头归节
    return ding_ju_pure(name, td, f, config)


# ---------- 布局 ----------
def di_pan(ju: int, dun: str):
    out = {}
    step = 1 if dun == "阳" else -1
    g = ju
    for gan in YI:
        out[g] = gan
        g = (g - 1 + step) % 9 + 1
    for gan in QI:
        out[g] = gan
        g = (g - 1 + step) % 9 + 1
    return out


def _ring_idx(g):
    return RING.index(g)


def _ring_shift(src, dst):
    s = (_ring_idx(dst) - _ring_idx(src)) % 8
    return s - 8 if s > 4 else s


def jigong_gong(config: QimenConfig, dun: str):
    if config.jigong == "kun2":
        return 2
    if config.jigong == "yang2yin8":
        return 2 if dun == "阳" else 8
    if config.jigong == "siwei":
        return 2   # 法窍四维随令：需节气，暂以坤二为基准，输出注明
    return None


def rotate(mapping: dict, steps: int, center_gong: Optional[int]):
    """按八宫环序旋转；center_gong 上的内容随后者一起转（寄宫）。"""
    out = {}
    for g, v in mapping.items():
        if g == center_gong:
            continue
        out[RING[(_ring_idx(g) + steps) % 8]] = v
    # 寄宫内容跟随寄宫宫位
    if center_gong and center_gong in mapping:
        out[RING[(_ring_idx(center_gong) + steps) % 8]] = mapping[center_gong]
    return out


GONG_SEQ9 = [1, 2, 3, 4, 5, 6, 7, 8, 9]


def zhishi_target(home: int, delta: int, dun: str, mode: str = "gongshu9"):
    """直使飞宫。gongshu9=九宫顺逆（主流，落五寄坤二）；
    gongshu8=真授秘集顺飞八宫不入中五；zhanggong=张公十八局一律顺行。"""
    step = 1 if dun == "阳" else -1
    if mode == "gongshu8":
        seq = GONG_SEQ
        i = seq.index(home) if home in seq else seq.index(2)
        return seq[(i + step * delta) % len(seq)]
    if mode == "zhanggong":
        seq = GONG_SEQ
        i = seq.index(home) if home in seq else seq.index(2)
        return seq[(i + delta) % len(seq)]
    seq = GONG_SEQ9
    i = seq.index(home) if home in seq else seq.index(2)
    t = seq[(i + step * delta) % len(seq)]
    return 2 if t == 5 else t        # 值使入中五，寄坤二


def current_term(dt_in: dt.datetime):
    """当前天文节气（用于显示；定局另按符头归节）。"""
    terms = build_terms(dt_in.year)
    cur = None
    for name, td in terms:
        if td <= dt_in:
            cur = (name, td)
        else:
            break
    return cur


def cast(dt_in: dt.datetime, config: QimenConfig = QimenConfig()):
    d = dt_in.date()
    if config.true_solar_time:
        dt_in = cal.local_apparent_solar_time(dt_in, config.longitude)
        d = dt_in.date()
    day_gz, hour_gz, used = cal.time_ganzhi(d.year, d.month, d.day, dt_in.hour, dt_in.minute,
                                            boundary=config.day_boundary)
    d = used
    dj = ding_ju(d, config, now=dt_in)
    ct = current_term(dt_in)
    if ct:
        dj["current_term"] = ct[0]
        dj["current_term_time"] = ct[1].isoformat(sep=" ")

    dp = di_pan(dj["ju"], dj["dun"])
    center = jigong_gong(config, dj["dun"])
    # 中五寄宫：地盘输出保留 5，但天盘旋转时寄宫宫位承载中五干
    dp_for_rot = {g: v for g, v in dp.items() if g != 5}   # 中五干不随天盘旋转

    xs = xun_shou(hour_gz)
    yi = XUN_YI[xs]
    home = next(g for g, v in dp.items() if v == yi)
    home_eff = center if home == 5 and center else home
    zf_star = STAR_HOME[home]
    zs_door = DOOR_HOME.get(home_eff, DOOR_HOME[2]) if home != 5 else DOOR_HOME[2]

    shi_gan = hour_gz[0]
    if shi_gan == "甲":
        # 旬首时（甲时）：甲隐于旬首之仪，值符加本宫（伏吟）
        tg = home_eff
    else:
        tg = next((g for g, v in dp.items() if v == shi_gan), None)
        if tg == 5 and center:
            tg = center
    shift = _ring_shift(home_eff, tg) if tg else 0

    tp = rotate(dp_for_rot, shift, None)
    stars = {g: STAR_HOME[g] for g in RING}          # 星本位
    stars = rotate(stars, shift, None)
    # 中五之星天禽随寄宫转：目标宫并列（如 "天芮/天禽"）
    if center:
        dest = RING[(_ring_idx(center) + shift) % 8]
        if "天禽" not in stars.get(dest, ""):
            stars[dest] = stars.get(dest, "") + "/天禽"

    delta = xun_delta(hour_gz)
    zs_gong = zhishi_target(home_eff, delta, dj["dun"], config.zhishi_bufa)
    door_shift = _ring_shift(home_eff, zs_gong)
    doors = rotate(dict(DOOR_HOME), door_shift, None)

    # 八神
    start = tg if tg else home_eff
    seq = SHEN_SETS[config.bushen]
    shen = {}
    if config.shen_bufa == "fly9" or config.bushen == "jiu":
        order = GONG_SEQ
        i = order.index(start) if start in order else order.index(2)
        step = 1 if dj["dun"] == "阳" else -1
        for k, name in enumerate(seq):
            shen[order[(i + step * k) % len(order)]] = name
    else:
        i = _ring_idx(start)
        step = 1 if dj["dun"] == "阳" else -1
        for k, name in enumerate(seq[:8]):
            shen[RING[(i + step * k) % 8]] = name

    # 格局（起步集）
    year_gz, month_gz = _year_month_gz(dt_in)
    # 每宫细目（供网页盘内展示）
    month_zhi = (month_gz or "甲子")[1]
    kong = XUN_KONG[xs]
    cells = {}
    for g in range(1, 10):
        zhis = GONG_ZHI.get(g, ())
        if g == 5:
            cells["5"] = {"gong_wx": "土", "zhi": [], "kong": False, "ma": False,
                          "shen": None,
                          "star": {"name": "天禽", "wx": "土",
                                   "wang": star_wang("天禽", month_zhi)},
                          "tian_gan": [], "di_gan": _chars(dp.get(5)),
                          "door": None, "is_zhifu": False, "is_zhishi": False,
                          "day_gan": False, "hour_gan": False, "jigong": center}
            continue
        st = stars.get(g, "")
        st_name = st.split("/")[0] if st else None
        cells[str(g)] = {
            "gong_wx": _GONG_WX.get(g),
            "zhi": list(zhis),
            "kong": any(z in kong for z in zhis),
            "ma": MA_XING.get(hour_gz[1]) in zhis,
            "shen": shen.get(g),
            "star": {"name": st_name, "wx": STAR_WX.get(st_name),
                     "wang": star_wang(st_name, month_zhi)} if st_name else None,
            "tian_gan": _chars(tp.get(g)),
            "di_gan": _chars(dp.get(g)),
            "door": {"name": doors.get(g), "wx": _DOOR_WX.get(doors.get(g)),
                     "relation": door_gong_relation(doors.get(g), g)} if doors.get(g) else None,
            "is_zhifu": g == tg,
            "is_zhishi": g == zs_gong,
            "day_gan": day_gz[0] in _chars(tp.get(g)) or day_gz[0] in _chars(dp.get(g)),
            "hour_gan": hour_gz[0] in _chars(tp.get(g)) or hour_gz[0] in _chars(dp.get(g)),
        }

    ge = _ge_ju({
        "dp": dp, "tp": tp, "doors": doors, "stars": stars, "shen": shen,
        "hour_gz": hour_gz, "day_gz": day_gz, "year_gz": year_gz, "month_gz": month_gz,
        "xun_yi": yi, "xun_shou": xs, "zf_gong": tg, "zs_gong": zs_gong, "config": config,
    })

    return {
        "input": {"time": dt_in.isoformat(sep=" "), "config": asdict(config),
                  "config_fingerprint": config.fingerprint()},
        "four_pillars": {"year": year_gz,
                         "month": month_gz, "day": day_gz, "hour": hour_gz},
        "term": dj,
        "pan": {
            "di_pan": {str(g): dp[g] for g in range(1, 10)},
            "tian_pan": {str(g): v for g, v in sorted(tp.items())},
            "jiu_xing": {str(g): v for g, v in sorted(stars.items())},
            "ba_men": {str(g): v for g, v in sorted(doors.items())},
            "ba_shen": {str(g): v for g, v in sorted(shen.items())},
        },
        "xun_kong": {"xun": xs, "kong": list(XUN_KONG[xs])},
        "cells": cells,
        "ma_xing": MA_XING.get(hour_gz[1]),
        "zhi_fu": {"star": zf_star, "home_gong": home, "add_to_gong": tg},
        "zhi_shi": {"door": zs_door, "home_gong": home_eff, "add_to_gong": zs_gong},
        "zhong_gong": {"gan": dp.get(5), "jigong": center, "jigong_rule": config.jigong,
                       "ji_men": DOOR_HOME[2] if center == 2 else None},
        "ge_ju": ge,
        "provenance": [
            {"field": "term.ju", "source": "定局与排盘规则 §二.3", "level": "[原文]"},
            {"field": "pan.di_pan", "source": "定局与排盘规则 §三.1", "level": "[原文]"},
            {"field": "zhi_fu/zhi_shi", "source": "宝鉴004/演义012/笺元002", "level": "[原文]"},
            {"field": "pan.tian_pan/ba_men", "source": "八宫环序转盘（011 两例）", "level": "[原文]"},
        ],
        "warnings": _warnings(dj, config),
    }


_DUAN = None


def _load_duan():
    global _DUAN
    if _DUAN is None:
        path = os.path.normpath(os.path.join(_HERE, "..", "rules", "17-奇门断语.json"))
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        _DUAN = {
            "A": {(e["tian"], e["di"]): e for e in d["A_干加干"]},
            "B": {e["gan"]: e for e in d["B_时干克应"]},
            "C": {e["gan"]: e for e in d["C_时加六干"]},
            "D": {(e["tian"], e["di"]): e for e in d.get("D_混合百神", [])},
        }
    return _DUAN


def duan_yu(chart):
    """按时干与天地盘干加，取出适用断语（法窍）。"""
    d = _load_duan()
    out = []
    dp = {int(k): v for k, v in chart["pan"]["di_pan"].items()}
    tp = {int(k): v for k, v in chart["pan"]["tian_pan"].items()}
    xun = (chart.get("xun_kong") or {}).get("xun") or xun_shou(chart["four_pillars"]["hour"])
    xun_yi = XUN_YI.get(xun)
    for g in RING:
        for tg in _chars(tp.get(g)):
            # 若本地盘干即旬首之仪，优先取“X加甲（旬首）”条，避免与“X加本干”重复
            e = d["A"].get((tg, "甲")) if dp.get(g) == xun_yi else None
            if not e:
                for dg in _chars(dp.get(g)):
                    e = d["A"].get((tg, dg))
                    if e:
                        break
            if e:
                out.append({"kind": "干加干", "name": e["name"], "gong": g,
                            "text": e["text"],
                            "source": f"奇门法窍 L{e['line']}", "level": "[原文]",
                            "pai": "法窍", "note": e.get("note")})
    # D 宝鉴《混合百神》：天盘甲＝旬首（值符宫），地盘甲＝旬首之仪
    seen = set()
    zfg = (chart.get("zhi_fu") or {}).get("add_to_gong")
    for g in RING:
        cand = []
        for tg in _chars(tp.get(g)):
            for dg in _chars(dp.get(g)):
                cand.append((tg, dg))
        if zfg is not None and g == zfg:
            cand += [("甲", dg) for dg in _chars(dp.get(g))]
        if xun_yi and dp.get(g) == xun_yi:
            cand += [(tg, "甲") for tg in _chars(tp.get(g))]
        for key in cand:
            if key in seen:
                continue
            e = d["D"].get(key)
            if e:
                seen.add(key)
                out.append({"kind": "干加干·混合百神", "name": e["name"], "gong": g,
                            "text": e["text"], "source": e["source"], "level": "[原文]",
                            "pai": e.get("pai")})

    hour = chart["four_pillars"]["hour"]
    gan = hour[0]
    if gan in d["B"]:
        e = d["B"][gan]
        out.append({"kind": "时干克应", "name": f"六{gan}", "gong": None,
                    "text": e["verse"] + e["text"], "source": e["source"],
                    "level": "[原文]", "pai": "法窍"})
    if gan in d["C"]:
        e = d["C"][gan]
        out.append({"kind": "时加六干", "name": f"时加六{gan}", "gong": None,
                    "text": e["text"], "source": f"奇门法窍 L{e['line']}",
                    "level": "[原文]", "pai": "法窍"})
    return out


_YONG = None


def _load_yong():
    global _YONG
    if _YONG is None:
        path = os.path.normpath(os.path.join(_HERE, "..", "rules", "18-奇门用神.json"))
        with open(path, encoding="utf-8") as f:
            _YONG = json.load(f)["questions"]
    return _YONG


_GOOD_DOOR = {"开门", "休门", "生门"}
_BAD_DOOR = {"死门", "惊门", "伤门"}
_GOOD_SHEN = {"值符", "太阴", "六合", "九地", "九天"}
_BAD_SHEN = {"螣蛇", "白虎", "玄武", "朱雀", "勾陈"}


def _resolve_yong(chart, type_, target):
    """用神落宫。返回 [(宫, 说明)]。"""
    cells = chart.get("cells") or {}
    if type_ == "gan":
        if target in ("DAY", "HOUR"):
            gan = chart["four_pillars"]["day" if target == "DAY" else "hour"][0]
            label = "日干" if target == "DAY" else "时干"
        else:
            gan, label = target, target
        if gan == "甲":
            g = chart["zhi_fu"].get("add_to_gong")
            return ([(g, f"甲（旬首）临值符宫")] if g else [])
        tian_hits, di_hits = [], []
        for g in RING:
            c = cells.get(str(g), {})
            if gan in c.get("tian_gan", []):
                tian_hits.append((g, f"{label}{gan}（天盘）"))
            elif gan in c.get("di_gan", []):
                di_hits.append((g, f"{label}{gan}（地盘）"))
        # 用神以天盘落宫为主；天盘不见时才取地盘
        return tian_hits or di_hits
    if type_ == "door":
        return [(int(g), f"{target}") for g in cells
                if (cells[g].get("door") or {}).get("name") == target]
    if type_ == "star":
        return [(int(g), f"{target}") for g in cells
                if (cells[g].get("star") or {}).get("name") == target]
    if type_ == "shen":
        return [(int(g), f"{target}") for g in cells if cells[g].get("shen") == target]
    if type_ == "ma":
        return [(int(g), "马星") for g in cells if cells[g].get("ma")]
    return []


def _eval_gong(chart, g):
    """评估一宫，返回 (factors, subtotal)。"""
    cells = chart.get("cells") or {}
    c = cells.get(str(g), {})
    factors = []

    def add(delta, text, source):
        factors.append({"delta": delta, "text": text, "source": source})

    door = c.get("door") or {}
    dn = door.get("name")
    if dn in _GOOD_DOOR:
        add(1, f"吉门（{dn}）", "演义006/笺元002：开休生三吉门")
    elif dn in _BAD_DOOR:
        add(-1, f"凶门（{dn}）", "演义006/笺元002：死惊伤三凶门")
    if door.get("relation", "").startswith("门克宫"):
        add(-1, "门迫（门克宫）", "宝鉴005/笺元007")
    star = c.get("star") or {}
    if star.get("wang") in ("旺", "相"):
        add(1, f"星{star['wang']}（{star.get('name')}{star.get('wx')}）", "演义009/笺元007")
    elif star.get("wang") in ("休", "囚", "废"):
        add(-1, f"星{star['wang']}（{star.get('name')}{star.get('wx')}）", "演义009/笺元007")
    shen = c.get("shen")
    if shen in _GOOD_SHEN:
        add(1, f"吉神（{shen}）", "宝鉴003 八神取用")
    elif shen in _BAD_SHEN:
        add(-1, f"凶神（{shen}）", "宝鉴003 八神取用")
    if set(c.get("tian_gan", [])) & {"乙", "丙", "丁"}:
        add(1, "三奇临宫", "宝鉴003 释奇")
    if c.get("kong"):
        add(-1, "旬空", "演义007 空亡")
    for x in chart.get("ge_ju", []):
        if x.get("gong") != g:
            continue
        if x.get("type") == "吉":
            add(1, f"吉格（{x['name']}）", x.get("source"))
        elif x.get("type") == "凶":
            add(-1, f"凶格（{x['name']}）", x.get("source"))
        if x["name"] in ("六仪击刑", "三奇入墓", "时干入墓", "门迫"):
            add(-1, f"{x['name']}", x.get("source"))
    sub = sum(f["delta"] for f in factors)
    return factors, sub


def interpret(chart, question="通用"):
    """解盘：用神取用＋逐宫评估＋倾向（等权计数，明示非结论）。"""
    questions = _load_yong()
    q = questions.get(question) or questions["通用"]
    items = []
    for ys in q["yong_shen"]:
        hits = _resolve_yong(chart, ys["type"], ys["target"])
        if not hits:
            items.append({"role": ys["role"], "target": ys["target"], "type": ys["type"],
                          "gong": None, "palace": None, "factors": [], "subtotal": 0,
                          "note": "本盘未见（可能在盘外或该神未布）"})
            continue
        for g, label in hits:
            factors, sub = _eval_gong(chart, g)
            c = (chart.get("cells") or {}).get(str(g), {})
            items.append({
                "role": ys["role"], "target": ys["target"], "type": ys["type"],
                "gong": g, "label": label,
                "palace": {"gong_wx": c.get("gong_wx"),
                           "star": (c.get("star") or {}).get("name"),
                           "star_wang": (c.get("star") or {}).get("wang"),
                           "door": (c.get("door") or {}).get("name"),
                           "door_relation": (c.get("door") or {}).get("relation"),
                           "shen": c.get("shen"), "kong": c.get("kong"), "ma": c.get("ma")},
                "factors": factors, "subtotal": sub,
                "source": ys.get("source"), "level": ys.get("level"),
            })

    # 倾向：只取日干、时干（人、事）计分；同宫只计一次
    core = [x for x in items if x["target"] in ("DAY", "HOUR") and x["gong"]]
    seen, total = set(), 0
    for x in core:
        if x["gong"] in seen:
            continue
        seen.add(x["gong"])
        total += x["subtotal"]
    if total >= 3:
        level = "偏吉"
    elif total >= 1:
        level = "稍吉"
    elif total == 0:
        level = "平"
    elif total >= -2:
        level = "稍凶"
    else:
        level = "偏凶"
    key = sorted([{"role": x["role"], "gong": x["gong"], "text": f["text"],
                   "delta": f["delta"], "source": f["source"]}
                  for x in items for f in x["factors"]],
                 key=lambda z: -abs(z["delta"]))[:6]
    caveats = [
        "倾向按日干、时干两宫的要素等权加减（吉门/凶门、星旺衰、吉凶神、三奇、旬空、迫刑墓格），未计轻重、主客与神煞叠加，仅供参看。",
        "日干＝人、时干＝事为通例；其余用神（财、婚、病、讼、文等）为通行取法，各派可调。",
        "空亡仅标旬空，未判填实、冲空；马星只标动象，不判吉凶。",
    ]
    if question != "通用":
        caveats.append(f"“{q['label']}”专用用神见下方各条 source，属通行取象。")
    return {"question": q["label"], "verdict": {"level": level, "score": total,
                                               "basis": "日干宫＋时干宫（同宫计一次）"},
            "yong_shen": items, "key_points": key, "caveats": caveats}


_EVID = None


def _load_evidence():
    global _EVID
    if _EVID is None:
        path = os.path.normpath(os.path.join(_HERE, "..", "rules", "16-奇门依据卡.json"))
        with open(path, encoding="utf-8") as f:
            _EVID = json.load(f)["cards"]
    return _EVID


def explain(chart):
    """把盘面字段映射为“依据卡”：值＋原文摘句＋出处＋分级。"""
    ev = _load_evidence()
    cards = []

    def add(field, value):
        c = ev.get(field, {})
        cards.append({"field": field, "label": c.get("label", field), "value": value,
                      "quote": c.get("quote"), "source": c.get("source"),
                      "level": c.get("level")})

    t = chart["term"]
    fp = chart["four_pillars"]
    add("four_pillars", f"{fp['year']}年 {fp['month']}月 {fp['day']}日 {fp['hour']}时")
    add("term", f"{t['dun']}遁{t['ju']}局（{t['ju_term']}{t['yuan']}元）")
    add("term.state", f"{t['state']}（符头 {t['futou']}{t['futou_gz']}，"
                      f"超接 {t['chao_days']} 日）")
    if t.get("run"):
        add("term.run", "置闰：闰奇（芒种/大雪前置闰）")
    add("pan.di_pan", " ".join(f"{g}{v}" for g, v in chart["pan"]["di_pan"].items()))
    zf, zs = chart["zhi_fu"], chart["zhi_shi"]
    add("zhi_fu", f"{zf['star']}（{zf['home_gong']}宫 → {zf['add_to_gong']}宫）")
    add("zhi_shi", f"{zs['door']}（{zs['home_gong']}宫 → {zs['add_to_gong']}宫）")
    add("pan.tian_pan", " ".join(f"{g}{v}" for g, v in chart["pan"]["tian_pan"].items()))
    add("pan.ba_men", " ".join(f"{g}{v}" for g, v in chart["pan"]["ba_men"].items()))
    add("pan.ba_shen", " ".join(f"{g}{v}" for g, v in chart["pan"]["ba_shen"].items()))
    zg = chart["zhong_gong"]
    add("zhong_gong", f"中五{zg['gan']}寄{zg['jigong']}宫（{zg['jigong_rule']}）")
    for g in chart["ge_ju"]:
        cards.append({"field": "ge_ju", "label": g["name"],
                      "value": (f"{g['gong']}宫 " if g.get("gong") else "") + g["wu"],
                      "quote": None, "source": g.get("source"), "level": g.get("level"),
                      "pai": g.get("pai")})
    return cards


def _year_month_gz(dt_in):
    """年柱/月柱：按立春与节的精确时刻切换。

    lunar_python 的 Exact 方法以交节时刻为界，与主流排盘工具一致；
    非 Exact 方法按日切换，会在交节当天日出错。
    """
    try:
        from lunar_python import Solar
        l = Solar.fromYmdHms(dt_in.year, dt_in.month, dt_in.day,
                             dt_in.hour, dt_in.minute, 0).getLunar()
        return l.getYearInGanZhiExact(), l.getMonthInGanZhiExact()
    except Exception:
        return cal.year_ganzhi(dt_in.year, dt_in.month, dt_in.day), None


def _warnings(dj, config):
    w = []
    if dj["state"] == "闰奇":
        w.append("本日按置闰法判为闰奇；不同流派（七日/九日/拆补/时宪书）结论可能不同")
    if dj["state"] == "接气":
        w.append("接气：节气先到而符头后到，局数按符头所归之节")
    if config.jigong == "siwei":
        w.append("法窍四维随令尚未按节气细分，当前以坤二为基准")
    if config.bushen == "jiu" and config.shen_bufa != "fly9":
        w.append("九神含太常需九宫顺飞，已强制 fly9")
    if dj.get("state") == "接气" and dj.get("chao_days", 0) > 5:
        w.append("接气逾五日：多因节间距，宜按逐年置闰链校核")
    if config.zhishi_bufa == "gongshu8":
        w.append("值使按真授秘集八宫飞（不入中五），与主流九宫法可能不同")
    return w


_GE_RULES = None
_HE = ["甲己", "乙庚", "丙辛", "丁壬", "戊癸"]


def _load_ge_rules():
    global _GE_RULES
    if _GE_RULES is None:
        path = os.path.normpath(os.path.join(_HERE, "..", "rules", "15-奇门格局.json"))
        with open(path, encoding="utf-8") as f:
            _GE_RULES = json.load(f)["ge_ju"]
    return _GE_RULES


def _chars(v):
    return [c for c in (v or "") if c in GAN]


def _pair_hit(ctx, tian, di):
    """tian/di 可为具体干、XUNYI、DAY/MONTH/YEAR/HOUR。返回 [(宫, 实际对)]。"""
    xunyi = ctx["xun_yi"]
    t_set = {xunyi} if tian == "XUNYI" else {tian}
    d_set = {xunyi} if di == "XUNYI" else {di}
    if di in ("DAY", "MONTH", "YEAR", "HOUR"):
        d_set = {ctx["day_gz"][0] if di == "DAY" else
                 (ctx["month_gz"] or "甲")[0] if di == "MONTH" else
                 (ctx["year_gz"] or "甲")[0] if di == "YEAR" else ctx["hour_gz"][0]}
    hits = []
    for g in RING:
        tg = set(_chars(ctx["tp"].get(g)))
        dg = set(_chars(ctx["dp"].get(g)))
        if tg & t_set and dg & d_set:
            t0 = sorted(tg & t_set)[0]
            d0 = sorted(dg & d_set)[0]
            if tian == "XUNYI" and di == "XUNYI":
                hits.append((g, f"{t0}加旬首"))
            elif tian == "XUNYI":
                hits.append((g, f"旬首（{ctx.get('xun_shou','')}{xunyi}）加{d0}"))
            elif di == "XUNYI":
                hits.append((g, f"{t0}加旬首（{ctx.get('xun_shou','')}{xunyi}）"))
            else:
                hits.append((g, f"{t0}加{d0}"))
    return hits


def _ge_ju(ctx):
    """按 rules/15-奇门格局.json 扫描；每命中一条带 id/name/gong/wu/source/level/pai。"""
    out = []
    cfg = ctx["config"]
    dp, tp, doors, stars, shen = ctx["dp"], ctx["tp"], ctx["doors"], ctx["stars"], ctx["shen"]
    for rule in _load_ge_rules():
        det = rule.get("detect")
        if not det:
            continue
        kind = det["kind"]
        hits = []
        if kind == "tian_di_pair":
            hits = _pair_hit(ctx, det["tian"], det["di"])
        elif kind == "tian_xunyi_di_gan":
            hits = _pair_hit(ctx, "XUNYI", det["di"])
        elif kind == "qi_with_door":
            for g in RING:
                if (set(_chars(tp.get(g))) | set(_chars(dp.get(g)))) & set(QI) and \
                        doors.get(g) in det["doors"]:
                    hits.append((g, "三奇＋" + doors.get(g)))
        elif kind == "di_gan_at_zhishi":
            g = ctx["zs_gong"]
            if det["gan"] in dp.get(g, ""):
                hits.append((g, f"地盘{det['gan']}守值使{doors.get(g)}"))
        elif kind == "door_qi_di":
            for g in RING:
                if doors.get(g) == det["door"] and set(_chars(tp.get(g))) & set(QI) \
                        and det["di"] in dp.get(g, ""):
                    hits.append((g, f"{det['door']}＋奇＋{det['di']}"))
        elif kind == "door_qi_shen":
            for g in RING:
                if doors.get(g) == det["door"] and set(_chars(tp.get(g))) & set(QI) \
                        and shen.get(g) == det["shen"]:
                    hits.append((g, f"{det['door']}＋奇＋{det['shen']}"))
        elif kind == "hour_gan":
            if ctx["hour_gz"][0] == det["gan"]:
                hits.append((None, "时柱" + ctx["hour_gz"]))
        elif kind == "hour_day_he":
            if any(set(p) == {ctx["hour_gz"][0], ctx["day_gz"][0]} for p in _HE):
                hits.append((None, f"时干{ctx['hour_gz'][0]}合日干{ctx['day_gz'][0]}"))
        elif kind == "tian_gan_at_day":
            hits = [(g, w) for g, w in _pair_hit(ctx, "庚", "DAY")]
            if dp.get(ctx["zs_gong"], "").find("庚") >= 0:
                pass
        elif kind == "day_gan_at_tian":
            day = ctx["day_gz"][0]
            for g in RING:
                if day in _chars(tp.get(g)) and "庚" in dp.get(g, ""):
                    hits.append((g, f"{day}加庚"))
        elif kind == "tian_gan_at_zhifu":
            hits = [(g, w) for g, w in _pair_hit(ctx, "庚", "XUNYI")]
        elif kind == "zhifu_at_tian_gan":
            hits = [(g, w) for g, w in _pair_hit(ctx, "XUNYI", "庚")]
        elif kind == "tian_gan_at_year":
            hits = [(g, w) for g, w in _pair_hit(ctx, "庚", "YEAR")]
        elif kind == "tian_gan_at_month":
            hits = [(g, w) for g, w in _pair_hit(ctx, "庚", "MONTH")]
        elif kind == "tian_gan_at_hour":
            hits = [(g, w) for g, w in _pair_hit(ctx, "庚", "HOUR")]
        elif kind == "qi_mu":
            for g in RING:
                gs = dp.get(g, "")
                if "乙" in gs and g == 2:
                    hits.append((g, "乙临坤二"))
                if ("丙" in gs or "丁" in gs) and g == (8 if cfg.ding_mu == "chou" and "丁" in gs else 6):
                    hits.append((g, f"{'丙' if '丙' in gs else '丁'}临{'艮八' if g == 8 else '乾六'}"))
        elif kind == "shigan_mu":
            main = {"戊戌", "壬辰", "丙戌", "癸未", "丁丑"}
            bao = {"戊辰", "壬辰", "己未", "癸未", "辛丑"}
            if ctx["hour_gz"] in (bao if cfg.shigan_mu == "baojian" else main):
                hits.append((None, "时柱" + ctx["hour_gz"] + "入墓"))
        elif kind == "yi_jixing":
            jx = {"戊": 3, "己": 2, "庚": 8, "辛": 9, "壬": 4, "癸": 4}
            for yi, g in jx.items():
                if yi in dp.get(g, ""):
                    hits.append((g, f"{yi}临{g}宫击刑"))
        elif kind == "door_ke_gong":
            for g in RING:
                if doors.get(g) and _door_ke_gong(doors[g], g):
                    hits.append((g, f"{doors[g]}克{g}宫"))
        elif kind == "fuyin":
            if all(stars.get(g, "").split("/")[0] == STAR_HOME[g] for g in RING):
                hits.append((None, "九星各归本宫"))
            if all(doors.get(g) == DOOR_HOME[g] for g in RING):
                hits.append((None, "八门各归本宫"))
        elif kind == "fanyin":
            if all(stars.get(g, "").split("/")[0] == STAR_HOME[RING[(_ring_idx(g) + 4) % 8]]
                   for g in RING):
                hits.append((None, "九星加对冲宫"))
            if all(doors.get(g) == DOOR_HOME[RING[(_ring_idx(g) + 4) % 8]] for g in RING):
                hits.append((None, "八门加对冲宫"))
        elif kind == "hour_ke_day":
            if _ke(ctx["hour_gz"][0], ctx["day_gz"][0]):
                hits.append((None, f"时干{ctx['hour_gz'][0]}克日干{ctx['day_gz'][0]}"))
        elif kind == "qi_shouzhi":
            for g in RING:
                gs = dp.get(g, "")
                if ("乙" in gs and g in (6, 7)) or (("丙" in gs or "丁" in gs) and g == 1):
                    hits.append((g, f"{'乙' if '乙' in gs else ('丙' if '丙' in gs else '丁')}临{g}宫受制"))
        elif kind == "zha":
            for g in RING:
                if doors.get(g) in ("开门", "休门", "生门") and \
                        set(_chars(tp.get(g))) & set(QI) and shen.get(g) in ("太阴", "六合", "九地"):
                    hits.append((g, f"{doors[g]}＋奇＋{shen[g]}"))
        for g, wu in hits:
            out.append({"id": rule["id"], "name": rule["name"], "type": rule.get("type"),
                        "gong": g, "wu": wu, "pai": rule.get("pai"),
                        "source": rule.get("source"), "level": rule.get("level")})
    return out


_WX = {"甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土", "己": "土",
       "庚": "金", "辛": "金", "壬": "水", "癸": "水"}
_GONG_WX = {1: "水", 2: "土", 3: "木", 4: "木", 5: "土", 6: "金", 7: "金", 8: "土", 9: "火"}
_DOOR_WX = {"休门": "水", "死门": "土", "伤门": "木", "杜门": "木",
            "开门": "金", "惊门": "金", "生门": "土", "景门": "火"}
_KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
_SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
GONG_ZHI = {1: ("子",), 8: ("丑", "寅"), 3: ("卯",), 4: ("辰", "巳"),
            9: ("午",), 2: ("未", "申"), 7: ("酉",), 6: ("戌", "亥"), 5: ()}
STAR_WX = {"天蓬": "水", "天芮": "土", "天冲": "木", "天辅": "木", "天禽": "土",
           "天心": "金", "天柱": "金", "天任": "土", "天英": "火"}
ZHI_WX = {"子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
          "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水"}


def star_wang(star, month_zhi):
    """九星旺衰（演义009/笺元007）：同行为相，我生月为旺，父母为废，财为休，鬼为囚。"""
    sw, mw = STAR_WX.get(star), ZHI_WX.get(month_zhi)
    if not sw or not mw:
        return None
    if sw == mw:
        return "相"
    if _SHENG[sw] == mw:
        return "旺"
    if _SHENG[mw] == sw:
        return "废"
    if _KE[sw] == mw:
        return "休"
    return "囚"


def door_gong_relation(door, gong):
    dw, gw = _DOOR_WX.get(door), _GONG_WX.get(gong)
    if not dw or not gw:
        return None
    if dw == gw:
        return "比和"
    if _KE[dw] == gw:
        return "门克宫（迫）"
    if _KE[gw] == dw:
        return "宫克门（制）"
    if _SHENG[dw] == gw:
        return "门生宫"
    return "宫生门"


def _ke(a, b):
    return _KE.get(_WX.get(a), None) == _WX.get(b)


def _door_ke_gong(door, gong):
    return _KE.get(_DOOR_WX.get(door)) == _GONG_WX.get(gong)


# ---------- CLI ----------
def _fmt(chart):
    p = chart["pan"]
    lines = []
    lines.append(f"时间 {chart['input']['time']}  四柱 {chart['four_pillars']}")
    t = chart["term"]
    lines.append(f"节气 {t['term']}（{t['term_time']}）{t['dun']}遁{t['ju']}局 "
                 f"[{t['state']} 符头{t['futou']}{t['futou_gz']} {t['yuan']}元]")
    lines.append("宫    地盘  天盘  九星  八门  八神")
    for g in [4, 9, 2, 3, 5, 7, 8, 1, 6]:
        lines.append(f"{g}宫  {p['di_pan'].get(str(g),'')}    {p['tian_pan'].get(str(g),'')}   "
                     f"{p['jiu_xing'].get(str(g),'')}  {p['ba_men'].get(str(g),'')}  {p['ba_shen'].get(str(g),'')}")
    xk = chart.get("xun_kong", {})
    lines.append(f"值符 {chart['zhi_fu']}  值使 {chart['zhi_shi']}  中宫 {chart['zhong_gong']}")
    lines.append(f"旬空 {xk.get('xun','')}旬 {'、'.join(xk.get('kong', []))}  马星 {chart.get('ma_xing')}")
    if chart["ge_ju"]:
        lines.append("格局：" + "；".join(f"{x['name']}({x['gong']}宫,{x['wu']})" for x in chart["ge_ju"]))
    for w in chart["warnings"]:
        lines.append("⚠ " + w)
    return "\n".join(lines)


def _fmt_explain(chart):
    lines = [_fmt(chart), "", "—— 依据卡 ——"]
    for i, c in enumerate(explain(chart), 1):
        lines.append(f"{i}. 【{c['label']}】{c['value']}")
        if c.get("quote"):
            lines.append(f"   原文：{c['quote']}")
        lines.append(f"   出处：{c['source']}  {c['level']}" + (f"  流派：{c['pai']}" if c.get("pai") else ""))
    return chr(10).join(lines)


def _fmt_interpret(chart, question="通用"):
    r = interpret(chart, question)
    v = r["verdict"]
    lines = [_fmt(chart), "", f"—— 解盘（{r['question']}）：{v['level']}（{v['score']:+d}）——"]
    for x in r["yong_shen"]:
        where = f"{x['gong']}宫 " if x.get("gong") else "— "
        p = x.get("palace") or {}
        lines.append(f"· {x['role']}：{where}{p.get('star','')} {p.get('door','')} {p.get('shen','')}"
                     f"（{x.get('subtotal',0):+d}）")
        for f in x["factors"]:
            lines.append(f"    {f['delta']:+d} {f['text']}  [{f['source']}]")
    if r["key_points"]:
        lines.append("关键象：")
        for k in r["key_points"]:
            lines.append(f"  {k['delta']:+d} {k['role']}@{(str(k['gong'])+'宫') if k['gong'] else '—'} {k['text']}")
    lines.append("注意：")
    for c in r["caveats"]:
        lines.append("  - " + c)
    return chr(10).join(lines)


def _fmt_duan(chart):
    items = duan_yu(chart)
    lines = [_fmt(chart), "", "—— 断语（奇门法窍）——"]
    for i, c in enumerate(items, 1):
        where = f"{c['gong']}宫 " if c.get("gong") else ""
        lines.append(f"{i}. [{c['kind']}] {where}{c['name']}")
        lines.append(f"   {c['text']}")
        lines.append(f"   出处：{c['source']}  {c['level']}" + (f"  {c['note']}" if c.get("note") else ""))
    if not items:
        lines.append("（本盘无匹配断语）")
    return chr(10).join(lines)


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description="奇门遁甲时家排盘")
    ap.add_argument("--time", required=True, help='如 "2026-10-28 14:30"')
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--explain", action="store_true", help="输出依据卡")
    ap.add_argument("--duan", action="store_true", help="输出断语（法窍/宝鉴）")
    ap.add_argument("--interpret", action="store_true", help="输出解盘")
    ap.add_argument("--question", default="通用", help="占问类型：通用/求财/婚姻/疾病/官讼/出行/失物/考试/谋事/家宅")
    ap.add_argument("--config", default=None, help="JSON 字符串或配置文件路径")
    a = ap.parse_args(argv)
    fmt = "%Y-%m-%d %H:%M"
    t = dt.datetime.strptime(a.time, fmt) if ":" in a.time.split(" ")[-1] else \
        dt.datetime.strptime(a.time, "%Y-%m-%d %H")
    cfg = QimenConfig()
    if a.config:
        raw = a.config
        if os.path.exists(raw):
            raw = open(raw, encoding="utf-8").read()
        cfg = QimenConfig(**json.loads(raw))
    chart = cast(t, cfg)
    if a.interpret:
        print(_fmt_interpret(chart, a.question))
    elif a.duan:
        print(_fmt_duan(chart))
    elif a.explain:
        print(_fmt_explain(chart))
    else:
        print(json.dumps(chart, ensure_ascii=False, indent=1) if a.json else _fmt(chart))


if __name__ == "__main__":
    main(sys.argv[1:])
