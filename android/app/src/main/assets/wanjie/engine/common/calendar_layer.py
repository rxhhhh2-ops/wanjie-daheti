# -*- coding: utf-8 -*-
"""历法层（五体系共用）。
三个独立实现的职责划分（禁止互相"借用"结论）：
  - lunar_python：公农历换算、干支（年/月/日/时）——口径提供方
  - lunardate   ：农历日期/闰月的独立校验表（1900–2099）
  - ephem       ：节气【交节时刻】的独立天文计算（太阳视黄经每15°）
约定显式化：
  - year_basis="lunar"（农历年，正月初一换年，官方历法口径）
  - year_basis="lichun"（命理口径，立春换年）
  - day_boundary="23:00"（晚子时换日，主流命理）或 "00:00"
  - 时区：北京时间（东经120°平太阳时）。真太阳时另算（local_apparent_solar_time）。
"""
import datetime as dt
import math
import ephem
import lunardate
from lunar_python import Solar

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
# 节气顺序（按公历年内出现顺序）与太阳视黄经
TERMS = ["小寒", "大寒", "立春", "雨水", "惊蛰", "春分", "清明", "谷雨", "立夏", "小满", "芒种", "夏至",
         "小暑", "大暑", "立秋", "处暑", "白露", "秋分", "寒露", "霜降", "立冬", "小雪", "大雪", "冬至"]
TERM_LON = {name: ((i - 5) * 15) % 360 for i, name in enumerate(TERMS)}
# 春分=0°；TERMS[5]=春分 → i=5 → 0°。小寒 i=0 → 285° ✓，立春 i=2 → 315° ✓

class CalendarError(ValueError):
    pass

def _check_date(y, m, d):
    try:
        return dt.date(y, m, d)
    except ValueError as e:
        raise CalendarError(f"非法日期 {y}-{m}-{d}: {e}")

def _lunar_day(y, m, d, strict=False):
    """返回 (lunar_python 农历对象, 校验警告或 None)。

    lunar_python 为口径提供方；lunardate 仅作独立校验。二者在农历月界偶有差一日
    （实测 1900–2100 共 476 天，如 1978-09-02、1933-07-22），香港天文台对照表
    与 lunar_python 一致。默认以 lunar_python 为准并返回警告；strict=True 时抛错。
    """
    l = Solar.fromYmd(y, m, d).getLunar()
    ref = lunardate.LunarDate.from_solar_date(y, m, d)
    # 闰月编码不同：lunar_python 月=-n；lunardate 月=n+isLeapMonth 标志。归一后比较。
    lp_month, lp_leap = abs(l.getMonth()), l.getMonth() < 0
    ld_month, ld_leap = ref.month, bool(ref.isLeapMonth)
    if (l.getYear(), lp_month, lp_leap, l.getDay()) != (ref.year, ld_month, ld_leap, ref.day):
        msg = (f"农历双实现差一日 {y}-{m}-{d}: lunar_python={l.getYear()}年"
               f"{'闰' if lp_leap else ''}{lp_month}月{l.getDay()}日 vs lunardate="
               f"{ref.year}年{'闰' if ld_leap else ''}{ld_month}月{ref.day}日；"
               f"以 lunar_python 为准（HKO 对照表佐证）")
        if strict:
            raise CalendarError(msg)
        return l, msg
    return l, None

def solar_to_lunar(y, m, d, strict=False):
    """公历→农历（双实现校验）。返回 dict（含闰月标记与校验结果）。"""
    _check_date(y, m, d)
    l, warning = _lunar_day(y, m, d, strict)
    return {"year": l.getYear(), "month": l.getMonth(), "day": l.getDay(),
            "is_leap": l.getMonth() < 0, "year_ganzhi_lunar": l.getYearInGanZhi(),
            "year_ganzhi_lichun": l.getYearInGanZhiByLiChun(),
            "month_ganzhi": l.getMonthInGanZhiExact(), "day_ganzhi": l.getDayInGanZhi(),
            "time_zhi": l.getTimeZhi(),
            "校验": {"双实现一致": warning is None, "警告": warning}}

def year_ganzhi(y, m, d, basis="lichun"):
    """年干支。basis='lunar'：正月初一换年；basis='lichun'：立春换年（命理）。"""
    _check_date(y, m, d)
    l, _ = _lunar_day(y, m, d)
    if basis == "lunar":
        return l.getYearInGanZhi()
    if basis == "lichun":
        return l.getYearInGanZhiByLiChun()
    raise CalendarError(f"未知年口径: {basis}")

def day_ganzhi(y, m, d, hour=0, minute=0, boundary="23:00"):
    """日干支；23:00 之后按约定换日。返回 (日干支, 实际采用的日期)。"""
    _check_date(y, m, d)
    dd = dt.date(y, m, d)
    if boundary not in ("23:00", "00:00"):
        raise CalendarError(f"未知日界约定: {boundary}")
    if boundary == "23:00" and (hour, minute) >= (23, 0):
        dd += dt.timedelta(days=1)
    gz = Solar.fromYmdHms(dd.year, dd.month, dd.day, 12, 0, 0).getLunar().getDayInGanZhi()
    return gz, dd

def hour_zhi(hour, minute=0):
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise CalendarError(f"非法时刻 {hour}:{minute}")
    return ZHI[((hour + 1) % 24) // 2]

def hour_ganzhi(day_gan, hour, minute=0):
    """五鼠遁：甲己还加甲，乙庚丙作初，丙辛从戊起，丁壬庚子居，戊癸壬子途。"""
    if day_gan not in GAN:
        raise CalendarError(f"非法日干: {day_gan}")
    start = {"甲": 0, "己": 0, "乙": 2, "庚": 2, "丙": 4, "辛": 4, "丁": 6, "壬": 6, "戊": 8, "癸": 8}[day_gan]
    idx = ((hour + 1) % 24) // 2
    return GAN[(start + idx) % 10] + ZHI[idx]

def time_ganzhi(y, m, d, hour, minute=0, boundary="23:00"):
    gz_day, used = day_ganzhi(y, m, d, hour, minute, boundary)
    return gz_day, hour_ganzhi(gz_day[0], hour, minute), used

# ---------- 节气交节时刻（ephem 独立计算） ----------
def _ecl_lon(d):
    """太阳视黄经（度），d 为 ephem.Date（UTC）。"""
    s = ephem.Sun(d)
    eq = ephem.Equatorial(s.ra, s.dec, epoch=d)
    return math.degrees(ephem.Ecliptic(eq, epoch=d).lon) % 360

def _find_crossing(d0, d1, target):
    """在 [d0,d1] 内二分求黄经越过 target 的时刻（UTC）。"""
    def f(d):
        diff = (_ecl_lon(d) - target + 180) % 360 - 180
        return diff
    lo, hi = ephem.Date(d0), ephem.Date(d1)
    if f(lo) * f(hi) > 0:
        raise CalendarError(f"区间内无 {target}° 交点")
    for _ in range(60):
        mid = (lo + hi) / 2
        if f(lo) * f(mid) <= 0:
            hi = mid
        else:
            lo = mid
        if abs(hi - lo) < 1e-7:  # ~0.01 秒
            break
    return (lo + hi) / 2

def solar_terms(y, tz_hours=8):
    """返回 {节气: 北京时间 datetime}。日期须与 lunar_python 口径一致（交叉校验）。"""
    if not (1900 <= y <= 2100):
        raise CalendarError("年份超出支持范围 1900–2100")
    out = {}
    # 仅在【当年 1/1 – 12/31】窗口内搜索每个 15° 交点（每节气每年恰一次），避免误取上一年交节
    win_start = ephem.Date(f"{y}/1/1") - 1
    win_end = ephem.Date(f"{y}/12/31") + 1
    for name, lon in TERM_LON.items():
        d_prev = win_start
        found = None
        while d_prev < win_end:
            d_next = d_prev + 1
            f_prev = ((_ecl_lon(d_prev) - lon + 180) % 360) - 180
            f_next = ((_ecl_lon(d_next) - lon + 180) % 360) - 180
            if f_prev <= 0 < f_next:
                found = _find_crossing(d_prev, d_next, lon)
                break
            d_prev = d_next
        if found is None:
            raise CalendarError(f"{y} 年未找到 {name}")
        dt_utc = ephem.Date(found).datetime()
        out[name] = dt_utc + dt.timedelta(hours=tz_hours)
    return out

def verify_terms_with_lunar_python(y):
    """交叉校验：ephem 交节日期 vs lunar_python 节气表日期（应逐项一致）。"""
    from lunar_python import Solar as S2
    terms = solar_terms(y)
    bad = []
    for name, t in terms.items():
        # lunar_python 节气表中"冬至"固定指农历年起始的上一年冬至；
        # 故取 y+1 年的表来读 y 年冬至，其余节气取 y 年表。
        ref_y = y + 1 if name == "冬至" else y
        ref = S2.fromYmdHms(ref_y, 6, 1, 12, 0, 0).getLunar()
        jq = ref.getJieQiTable().get(name)
        if jq is None:
            bad.append((name, "lunar_python无此项"))
            continue
        jq_date = jq.getYear(), jq.getMonth(), jq.getDay()
        if jq_date != (t.year, t.month, t.day):
            bad.append((name, f"ephem={t.date()} vs lunar_python={jq_date}"))
    return bad

# ---------- 真太阳时 ----------
def local_apparent_solar_time(dt_beijing, longitude, latitude=30.0):
    """由北京时间求当地真太阳时（ephem 天文计算，含经度差与均时差）。"""
    utc = dt_beijing - dt.timedelta(hours=8)
    obs = ephem.Observer()
    obs.lon = str(longitude)
    obs.lat = str(latitude)
    obs.date = utc
    sun = ephem.Sun(obs)
    lst_hours = obs.sidereal_time() * 12 / math.pi  # 当地恒星时（小时）
    ra_hours = sun.ra * 12 / math.pi
    app_hours = (lst_hours - ra_hours + 12) % 24
    h = int(app_hours); m = int((app_hours - h) * 60)
    return dt.datetime(dt_beijing.year, dt_beijing.month, dt_beijing.day, h, m)
