# -*- coding: utf-8 -*-
"""四柱合法性校验 + 由四柱反推公历/农历时间。

校验分三层：
1. 每柱是否为六十甲子（天干地支阴阳相配）；
2. 月干是否符合五虎遁（年上起月），时干是否符合五鼠遁（日上起时）；
3. 该四柱在 1901–2099 公历范围内是否存在真实日期（节气月/晚子换日）。

反推只使用 BaziEngine 的历法口径，确保与 /bazi/api/paipan 排盘结果一致。
"""
from __future__ import annotations

import datetime as dt
from typing import Iterable

from lunar_python import Solar

import bazi_engine as B
import calendar_layer as C

GAN = B.GAN
ZHI = B.ZHI
JIE = B.JIE
JIE_TO_MONTH = B.JIE_TO_MONTH

# 十二时辰代表时刻（分钟）
HOUR_REP = {
    "子": (0, 30),
    "丑": (2, 0), "寅": (4, 0), "卯": (6, 0), "辰": (8, 0), "巳": (10, 0),
    "午": (12, 0), "未": (14, 0), "申": (16, 0), "酉": (18, 0), "戌": (20, 0), "亥": (22, 0),
}
# 时辰显示范围
HOUR_RANGE = {
    "子": "00:00–00:59 / 23:00–23:59",
    "丑": "01:00–02:59", "寅": "03:00–04:59", "卯": "05:00–06:59",
    "辰": "07:00–08:59", "巳": "09:00–10:59", "午": "11:00–12:59",
    "未": "13:00–14:59", "申": "15:00–16:59", "酉": "17:00–18:59",
    "戌": "19:00–20:59", "亥": "21:00–22:59",
}

STEM_GROUP = {
    "甲": "甲己", "己": "甲己", "乙": "乙庚", "庚": "乙庚",
    "丙": "丙辛", "辛": "丙辛", "丁": "丁壬", "壬": "丁壬",
    "戊": "戊癸", "癸": "戊癸",
}


def _is_60(gz: str) -> bool:
    if not isinstance(gz, str) or len(gz) != 2:
        return False
    if gz[0] not in GAN or gz[1] not in ZHI:
        return False
    return (GAN.index(gz[0]) - ZHI.index(gz[1])) % 2 == 0


def expected_month_gz(engine: B.BaziEngine, year_gz: str, month_zhi: str) -> str:
    wuhu = engine.data("SZ-007")
    group = STEM_GROUP[year_gz[0]]
    yin_gan = wuhu[group][0]
    off = (ZHI.index(month_zhi) - ZHI.index("寅")) % 12
    return GAN[(GAN.index(yin_gan) + off) % 10] + month_zhi


def expected_hour_gz(engine: B.BaziEngine, day_gz: str, hour_zhi: str) -> str:
    wushu = engine.data("SZ-008")
    group = STEM_GROUP[day_gz[0]]
    zi_gan = wushu[group][0]
    off = ZHI.index(hour_zhi)
    return GAN[(GAN.index(zi_gan) + off) % 10] + hour_zhi


def validate_pillars(engine: B.BaziEngine, pillars: dict) -> dict:
    """结构校验：返回 {valid, errors, expected}。"""
    errors: list[str] = []
    expected: dict[str, str] = {}
    labels = {"年": "年柱", "月": "月柱", "日": "日柱", "时": "时柱"}
    for key in ("年", "月", "日", "时"):
        gz = (pillars.get(key) or "").strip()
        if not _is_60(gz):
            errors.append(f"{labels[key]}「{gz or '空'}」不是合法六十甲子：须为天干＋地支，且阴阳相配（如甲子、丙寅）。")
    if errors:
        return {"valid": False, "errors": errors, "expected": expected}

    ygz, mgz, dgz, hgz = (pillars[k] for k in ("年", "月", "日", "时"))
    exp_m = expected_month_gz(engine, ygz, mgz[1])
    if mgz != exp_m:
        expected["月柱"] = exp_m
        errors.append(
            f"月柱「{mgz}」与年柱「{ygz}」不符：按五虎遁，{ygz[0]}年（{STEM_GROUP[ygz[0]]}）"
            f"寅月起{engine.data('SZ-007')[STEM_GROUP[ygz[0]]][0]}，{mgz[1]}月应为「{exp_m}」。"
        )
    exp_h = expected_hour_gz(engine, dgz, hgz[1])
    if hgz != exp_h:
        expected["时柱"] = exp_h
        errors.append(
            f"时柱「{hgz}」与日柱「{dgz}」不符：按五鼠遁，{dgz[0]}日（{STEM_GROUP[dgz[0]]}）"
            f"子时起{engine.data('SZ-008')[STEM_GROUP[dgz[0]]][0]}，{hgz[1]}时应为「{exp_h}」。"
        )
    return {"valid": not errors, "errors": errors, "expected": expected}


def _jie_events(engine: B.BaziEngine, years: Iterable[int]) -> list[tuple[dt.datetime, str]]:
    out = []
    for y in years:
        terms = engine._terms(y)
        for name in JIE:
            out.append((terms[name], name))
    out.sort()
    return out


def _month_window(engine: B.BaziEngine, year_pillar_year: int, month_zhi: str) -> tuple[dt.datetime, dt.datetime]:
    """返回该年柱下某月支对应的节气月起止（北京时间）。"""
    jie_name = next(n for n, b in JIE_TO_MONTH.items() if b == month_zhi)
    # 年柱从立春 y 起；子月在大雪 y 至小寒 y+1，丑月在小寒 y+1 至立春 y+1
    jie_year = year_pillar_year + (1 if month_zhi == "丑" else 0)
    events = _jie_events(engine, (jie_year - 1, jie_year, jie_year + 1))
    start = engine._terms(jie_year)[jie_name]
    idx = next(i for i, (t, n) in enumerate(events) if t == start)
    end = events[idx + 1][0]
    return start, end


def _month_window_loose(engine: B.BaziEngine, year_pillar_year: int,
                        month_zhi: str) -> tuple[dt.datetime, dt.datetime]:
    """节气月窗口；历法库边界年（1900/2100）取 1950 年同月窗口平移并加 3 天余量。

    余量只扩大扫描范围，仍由四柱全量复核过滤，不会产生假候选。
    """
    try:
        return _month_window(engine, year_pillar_year, month_zhi)
    except Exception:
        s, e = _month_window(engine, 1950, month_zhi)
        start = dt.datetime(year_pillar_year + (s.year - 1950), s.month, s.day,
                            s.hour, s.minute, s.second)
        end = dt.datetime(year_pillar_year + (e.year - 1950), e.month, e.day,
                          e.hour, e.minute, e.second)
        pad = dt.timedelta(days=3)
        return start - pad, end + pad


def _fp(engine: B.BaziEngine, y: int, m: int, d: int, h: int, mi: int) -> dict:
    return engine.pillars_from_datetime(y, m, d, h, mi)["四柱"]


def reverse_pillars(engine: B.BaziEngine, pillars: dict,
                    start_year: int = 1901, end_year: int = 2099) -> dict:
    """由四柱反推公历/农历时间；返回 {ok, valid, errors, expected, candidates}。"""
    check = validate_pillars(engine, pillars)
    if not check["valid"]:
        return {"ok": True, "valid": False, "errors": check["errors"],
                "expected": check["expected"], "candidates": [], "count": 0}

    ygz, mgz, dgz, hgz = (pillars[k] for k in ("年", "月", "日", "时"))
    month_zhi, hour_zhi = mgz[1], hgz[1]
    errors: list[str] = []
    candidates: list[dict] = []
    seen: set[str] = set()

    # 年柱每 60 年重现；只在年柱匹配的公历年份里找。
    # 年初（立春前）仍属上一年柱，故向前多看一年，结果再按公历区间裁剪。
    years = [y for y in range(start_year - 1, end_year + 1)
             if B.year_gz_of_year(y) == ygz]
    if not years:
        errors.append(f"年柱「{ygz}」在 {start_year}–{end_year} 内没有对应公历年份。")

    lo, hi = dt.date(start_year, 1, 1), dt.date(end_year, 12, 31)
    for y in years:
        try:
            start, end = _month_window_loose(engine, y, month_zhi)
        except Exception:
            continue
        d0 = max(start.date() - dt.timedelta(days=1), lo)
        d1 = min(end.date() + dt.timedelta(days=1), hi)
        day = d0
        while day <= d1:
            # 子时：早子（当日 00:30）与晚子（当日 23:30，按 23:00 换日）
            hours = [(0, 30), (23, 30)] if hour_zhi == "子" else [HOUR_REP[hour_zhi]]
            for hh, mi in hours:
                try:
                    got = _fp(engine, day.year, day.month, day.day, hh, mi)
                except Exception:
                    continue
                if got != pillars:
                    continue
                # 用完整排盘复核，避免节气/日界边界误差
                try:
                    full = engine.pillars_from_datetime(day.year, day.month, day.day, hh, mi)
                except Exception:
                    continue
                if full["四柱"] != pillars:
                    continue
                solar = f"{day.year:04d}-{day.month:02d}-{day.day:02d}T{hh:02d}:{mi:02d}"
                if solar in seen:
                    continue
                seen.add(solar)
                lunar = Solar.fromYmdHms(day.year, day.month, day.day, hh, mi, 0).getLunar()
                candidates.append({
                    "solar": solar,
                    "date": f"{day.year:04d}-{day.month:02d}-{day.day:02d}",
                    "time": f"{hh:02d}:{mi:02d}",
                    "lunar": lunar.toString(),
                    "lunarShort": f"{lunar.getYearInGanZhi()}年{'闰' if lunar.getMonth() < 0 else ''}{abs(lunar.getMonth())}月{lunar.getDay()}日",
                    "hourBranch": hour_zhi,
                    "hourRange": HOUR_RANGE[hour_zhi],
                    "lateZi": hour_zhi == "子" and hh == 23,
                    "pillars": dict(full["四柱"]),
                    "dayBoundary": engine.config.get("day_boundary", "23:00"),
                    "note": ("23:00–23:59 晚子时，按 23:00 换日，日柱取次日。"
                             if hour_zhi == "子" and hh == 23 else
                             "00:00–00:59 早子时。" if hour_zhi == "子" else
                             f"{hour_zhi}时，按 {HOUR_RANGE[hour_zhi]}。"),
                })
            day += dt.timedelta(days=1)

    candidates.sort(key=lambda x: x["solar"])
    if not candidates:
        errors.append(
            f"在 {start_year}–{end_year} 年公历范围内未找到与该四柱完全匹配的日期。"
            "请检查月柱是否按节气月、时柱是否按五鼠遁，或该组合是否只在支持范围之外出现。"
        )
    return {"ok": True, "valid": True, "errors": errors, "expected": check["expected"],
            "candidates": candidates, "count": len(candidates)}
