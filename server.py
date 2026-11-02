# -*- coding: utf-8 -*-
"""万界大合体 · 五术合一推演系统（本地服务）

    python server.py [--port 8899] [--host 127.0.0.1]

一个进程同时承载五个子系统：
    四柱排盘  /bazi/     （子平八字：排盘 / 格局 / 大运流年 / AI 解盘）
    梅花易数  /meihua/   （十四种起卦 / 体用互变 / 类象 / 应期 / AI 解卦）
    奇门遁甲  /qimen/    （时家奇门：定局 / 三盘 / 格局 / 断语 / AI）
    大六壬    /liuren/   （四课三传 / 九宗门 / 课体 / 神煞，纯前端）
    紫微斗数  /ziwei/    （十二宫 / 十四主星 / 四化 / 大限流年，纯前端）

页面端口只有这一个；所有 API 都在同源下，前端以相对路径访问。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "engine")
sys.path.insert(0, ENGINE)
sys.path.insert(0, os.path.join(ENGINE, "common"))

# ----------------------------- 引擎 -----------------------------
import bazi_engine as B          # noqa: E402
import bazi_reverse as BR       # noqa: E402
import qimen_engine as Q         # noqa: E402
import meihua_engine as M        # noqa: E402
import meihua_judge as J         # noqa: E402
import meihua_yingqi as Y        # noqa: E402
import meihua_waiying as W       # noqa: E402
import yingqi_engine as YQ       # noqa: E402

BAZI = B.BaziEngine()

ZH_BRANCH = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
OBJ_ALIAS = {"老人": "乾", "少女": "兑", "长女": "巽", "中男": "坎", "中女": "离", "少男": "艮",
             "老妇": "坤", "长子": "震", "牛": "坤", "鸡": "巽", "马": "乾", "龙": "震",
             "狗": "艮", "羊": "兑", "猪": "坎", "鼠": "艮", "虎": "艮", "兔": "震",
             "蛇": "震", "猴": "坤", "槁木": "离", "枯木": "离", "金玉": "乾", "土瓦": "坤"}
FIELDS = ["天時", "地理", "人物", "人事", "身體", "時序", "動物", "靜物", "屋舍", "家宅",
          "婚姻", "飲食", "生產", "求名", "謀旺", "交易", "求利", "出行", "謁見", "疾病",
          "方道", "五色", "姓字", "數目", "五味"]
FLABEL = {"天時": "天时", "地理": "地理", "人物": "人物", "人事": "人事", "身體": "身体",
          "時序": "时序", "動物": "动物", "靜物": "静物", "屋舍": "屋舍", "家宅": "家宅",
          "婚姻": "婚姻", "飲食": "饮食", "生產": "生产", "求名": "求名", "謀旺": "谋旺",
          "交易": "交易", "求利": "求利", "出行": "出行", "謁見": "谒见", "疾病": "疾病",
          "方道": "方位", "五色": "五色", "姓字": "姓字", "數目": "数目", "五味": "五味"}


# ======================= 四柱 =======================
def bazi_paipan(y: int, m: int, d: int, hh: int, mi: int, gender: str | None,
                year: int | None, boundary: str | None) -> dict:
    cfg = {"day_boundary": boundary} if boundary else None
    eng = B.BaziEngine(cfg)
    p = eng.pillars_from_datetime(y, m, d, hh, mi)
    qz = p["四柱"]
    out = dict(p)
    out.update(eng.analyze(qz["年"], qz["月"], qz["日"], qz["时"], gender=gender))
    out.setdefault("输入", {})["性别"] = gender
    if gender:
        from yunsui_engine import YunSuiEngine
        yse = YunSuiEngine(eng)
        ys = (out.get("格局", {}).get("用神", {}) or {}).get("定神", {}).get("神")
        out["大运"] = yse.dayun(qz, gender, out["节气距离"], birth_year=y, yong_shen=ys)
        out["小运"] = eng.xiaoyun(qz, gender)
    if year and year >= y:
        from yunsui_engine import YunSuiEngine
        ys = (out.get("格局", {}).get("用神", {}) or {}).get("定神", {}).get("神")
        out["流年"] = YunSuiEngine(eng).liunian(
            qz, year, gender=gender, birth_year=y, jie_days=out["节气距离"], yong_shen=ys)
    from lunar_python import Solar
    lunar = Solar.fromYmdHms(y, m, d, hh, mi, 0).getLunar()
    ec = lunar.getEightChar()
    out["显示"] = {
        "农历": lunar.toString(),
        "农历年干支": lunar.getYearInGanZhi(),
        "生肖": lunar.getYearShengXiao(),
        "节气": lunar.getJieQi(),
        "纳音": [ec.getYearNaYin(), ec.getMonthNaYin(), ec.getDayNaYin(), ec.getTimeNaYin()],
        "胎元": ec.getTaiYuan(),
        "身宫": ec.getShenGong(),
    }
    order = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"]
    seq = eng.data("YL-008")[qz["日"][0]]
    out["星运"] = {pos: order[seq.index(qz[pos][1])] for pos in ("年", "月", "日", "时")}
    from analysis_engine import AnalysisEngine
    out["分析"] = AnalysisEngine(eng, eng.config).analyze(out, gender=gender)
    try:
        out["应期"] = YQ.bazi_yingqi(out, y, gender, year or dt.date.today().year)
    except Exception as exc:  # noqa: BLE001
        out["应期"] = {"tool": "八字", "error": f"{type(exc).__name__}: {exc}"}
    return out


def bazi_analyze(ygz: str, mgz: str, dgz: str, hgz: str, gender: str | None,
                 year: int | None) -> dict:
    out = BAZI.analyze(ygz, mgz, dgz, hgz, gender=gender)
    if year:
        from yunsui_engine import YunSuiEngine
        ys = (out.get("格局", {}).get("用神", {}) or {}).get("定神", {}).get("神")
        out["流年"] = YunSuiEngine(BAZI).liunian(
            {"年": ygz, "月": mgz, "日": dgz, "时": hgz}, year,
            gender=gender, yong_shen=ys)
    from analysis_engine import AnalysisEngine
    out["分析"] = AnalysisEngine(BAZI, BAZI.config).analyze(out, gender=gender)
    return out


# ================= 四柱运程（流年/流岁/流月/流日/流时） =================
# 六十甲子纳音（30 对）
_NAYIN = {}
for _pair, _name in (
    ("甲子乙丑", "海中金"), ("丙寅丁卯", "炉中火"), ("戊辰己巳", "大林木"),
    ("庚午辛未", "路旁土"), ("壬申癸酉", "剑锋金"), ("甲戌乙亥", "山头火"),
    ("丙子丁丑", "涧下水"), ("戊寅己卯", "城头土"), ("庚辰辛巳", "白蜡金"),
    ("壬午癸未", "杨柳木"), ("甲申乙酉", "泉中水"), ("丙戌丁亥", "屋上土"),
    ("戊子己丑", "霹雳火"), ("庚寅辛卯", "松柏木"), ("壬辰癸巳", "长流水"),
    ("甲午乙未", "沙中金"), ("丙申丁酉", "山下火"), ("戊戌己亥", "平地木"),
    ("庚子辛丑", "壁上土"), ("壬寅癸卯", "金箔金"), ("甲辰乙巳", "覆灯火"),
    ("丙午丁未", "天河水"), ("戊申己酉", "大驿土"), ("庚戌辛亥", "钗钏金"),
    ("壬子癸丑", "桑柘木"), ("甲寅乙卯", "大溪水"), ("丙辰丁巳", "沙中土"),
    ("戊午己未", "天上火"), ("庚申辛酉", "石榴木"), ("壬戌癸亥", "大海水"),
):
    _NAYIN[_pair[0:2]] = _name
    _NAYIN[_pair[2:4]] = _name

_STAGES = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"]
_HE = {frozenset(x) for x in ("子丑", "寅亥", "卯戌", "辰酉", "巳申", "午未")}          # 六合
_CHONG = {frozenset(x) for x in ("子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥")}       # 六冲
_HAI = {frozenset(x) for x in ("子未", "丑午", "寅巳", "卯辰", "申亥", "酉戌")}         # 六害
_XING = {frozenset(x) for x in ("子卯", "寅巳", "巳申", "寅申", "丑戌", "戌未", "丑未")}  # 三刑
_SANHE = {}
for _g in ("申子辰", "寅午戌", "巳酉丑", "亥卯未"):
    for _b in _g:
        _SANHE[_b] = _g


def _branch_rel(a: str, b: str) -> tuple[str, ...]:
    """两支关系：六合/冲/害/刑/三合（同支自刑含辰午酉亥）。"""
    rel = []
    pair = frozenset((a, b))
    if pair in _HE:
        rel.append("六合")
    if pair in _CHONG:
        rel.append("冲")
    if pair in _HAI:
        rel.append("害")
    if pair in _XING or (a == b and a in "辰午酉亥"):
        rel.append("刑")
    if a != b and _SANHE.get(a) == _SANHE.get(b):
        rel.append("三合")
    return tuple(rel)


def _year_badges(relations: list[dict]) -> list[str]:
    """流年角标：岁运并临 / 真太岁 / 天克地冲 / 伏吟 / 返吟。"""
    tags = []
    if any("天克地冲" in r.get("条件", "") for r in relations):
        tags.append("天克地冲")
    if any(str(r.get("结论", "")).startswith("岁运并临") for r in relations):
        tags.append("岁运并临")
    if any(str(r.get("结论", "")).startswith("真太岁") for r in relations):
        tags.append("真太岁")
    if any(str(r.get("结论", "")).startswith("伏吟") for r in relations):
        tags.append("伏吟")
    if "天克地冲" not in tags and any(
            str(r.get("结论", "")).startswith("返吟") and "大运" in r.get("条件", "")
            for r in relations):
        tags.append("返吟")
    return tags


def bazi_flow(scope: str, y: int, m: int, d: int, hh: int, mi: int,
              gender: str | None, year: int | None = None, d_from: str | None = None,
              d_to: str | None = None, date_s: str | None = None,
              boundary: str | None = None, yong_shen: str | None = None) -> dict:
    """运程钻取：各层干支与十神（支藏干按 CG-007 通行表），附纳音/神煞/原局关系。"""
    eng = B.BaziEngine({"day_boundary": boundary} if boundary else None)
    p = eng.pillars_from_datetime(y, m, d, hh, mi)
    qz = p["四柱"]
    dm = qz["日"][0]
    cg = eng.data("CG-007")

    # 神煞（与神煞引擎同表）：驿马/桃花按年支三合局，天乙贵人按年干＋日干双口径
    from shensha_engine import SANHE_OF
    _yax = eng.data("LM-003")[SANHE_OF[qz["年"][1]]]
    _thx = eng.data("SSH-057")[SANHE_OF[qz["年"][1]]]
    _tyx = set(eng.data("SSH-005")[qz["年"][0]]) | set(eng.data("SSH-005")[dm])
    _yl = eng.data("YL-008")[dm]

    def hid(z: str) -> list[dict]:
        return [{"干": s, "层": lvl, "十神": B.ten_god(dm, s)}
                for lvl in ("本", "中", "余") for s in cg[z][lvl]]

    def ext(gz: str) -> dict:
        z = gz[1]
        rel = []
        for pos in ("年", "月", "日", "时"):
            r = _branch_rel(z, qz[pos][1])
            if r:
                rel.append({"柱": pos, "支": qz[pos][1], "关系": list(r)})
        ss = []
        if z == _yax:
            ss.append("驿马")
        if z == _thx:
            ss.append("桃花")
        if z in _tyx:
            ss.append("贵人")
        return {"纳音": _NAYIN.get(gz, ""), "星运": _STAGES[_yl.index(z)],
                "神煞": ss, "原局": rel}

    def gz_info(gz: str) -> dict:
        return {"干支": gz,
                "十神（干）": B.ten_god(dm, gz[0]),
                "十神（支本气）": B.ten_god(dm, cg[gz[1]]["本"][0]),
                "支藏": hid(gz[1]), **ext(gz)}

    if scope == "years":
        from yunsui_engine import YunSuiEngine
        yse = YunSuiEngine(eng)
        out: dict = {"scope": "years", "日主": dm, "四柱": qz, "出生年": y}
        rows: list[dict] = []
        if gender:
            dy = yse.dayun(qz, gender, p["节气距离"], birth_year=y, yong_shen=yong_shen)
            for i, r in enumerate(dy["大运（前八步）"]):
                s = int(round(r["起始年（约）"]))
                e = int(round(r["结束年（约）"]))
                info = gz_info(r["干支"])
                rows.append({"序": i + 1, "干支": r["干支"],
                             "十神（干）": r["十神（干）"],
                             "十神（支本气）": r["十神（支本气）"],
                             "十二宫": r.get("十二宫"), "十二宫取象": r.get("十二宫取象"),
                             "用神喜忌": r.get("用神喜忌"),
                             "起始岁": r["起始岁（约）"], "结束岁": r["结束岁（约）"],
                             "起始年": s, "结束年": e - 1, "支藏": info["支藏"],
                             "纳音": info["纳音"], "星运": info["星运"],
                             "神煞": info["神煞"], "原局": info["原局"]})
            xs = eng.xiaoyun(qz, gender)["序列（一岁一步）"]
            sui = []
            for i, g in enumerate(xs):
                age = i + 1
                dy_of = next((r for r in rows
                              if r["起始岁"] <= age < r["结束岁"]), None)
                sui.append({"虚岁": age, "对应大运": dy_of["干支"] if dy_of else "童限",
                            **gz_info(g)})
            out["流岁（小运）"] = sui
        else:
            out["流岁（小运）"] = []
        out["大运（前八步）"] = rows

        target = year or dt.datetime.now().year
        cur: dict
        if not rows:
            years = [target]
            cur = {"序": 0, "干支": "童限", "起始年": target, "结束年": target}
        elif target < rows[0]["起始年"]:
            years = list(range(y, rows[0]["起始年"]))
            cur = {"序": 0, "干支": "童限", "起始年": y,
                   "结束年": rows[0]["起始年"] - 1}
        else:
            pick = rows[-1]
            for r in rows:
                if r["起始年"] <= target <= r["结束年"]:
                    pick = r
                    break
            years = list(range(pick["起始年"], pick["结束年"] + 1))
            cur = {k: pick[k] for k in ("序", "干支", "起始年", "结束年")}
        if not years:
            years = [cur["起始年"]]
        out["当前大运"] = cur

        ln_list = []
        for yr in years:
            dy_gz = None if cur["序"] == 0 else cur["干支"]
            ln = yse.liunian(qz, yr, gender=gender, birth_year=y,
                             jie_days=p["节气距离"], dayun_gz=dy_gz)
            ln_gz = ln["流年"]["干支"]
            rel = ln.get("关系", [])
            item = {"年": yr, "虚岁": yr - y + 1, **gz_info(ln_gz),
                    "生肖": "鼠牛虎兔龙蛇马羊猴鸡狗猪"["子丑寅卯辰巳午未申酉戌亥".index(ln_gz[1])],
                    "大运": dy_gz or "童限",
                    "标记": _year_badges(rel),
                    "关系": rel, "断语": ln.get("断语", [])}
            if cur["序"] == 0 and out["流岁（小运）"]:
                xz = item["虚岁"] - 1
                if 0 <= xz < len(out["流岁（小运）"]):
                    item["小运"] = out["流岁（小运）"][xz]["干支"]
            ln_list.append(item)
        out["流年"] = ln_list
        return out

    if scope == "months":
        if not year:
            raise ValueError("流月查询需 year 参数")
        if not 1901 <= year <= 2098:
            raise ValueError("流月支持 1901–2098 年（需 year+1 节气表）")
        import calendar_layer as C
        t1, t2 = C.solar_terms(year), C.solar_terms(year + 1)
        mdefs = [("正月", "立春"), ("二月", "惊蛰"), ("三月", "清明"), ("四月", "立夏"),
                 ("五月", "芒种"), ("六月", "小暑"), ("七月", "立秋"), ("八月", "白露"),
                 ("九月", "寒露"), ("十月", "立冬"), ("十一月", "大雪"), ("十二月", "小寒")]
        starts = [t1[term] if term != "小寒" else t2["小寒"] for _, term in mdefs]
        stops = starts[1:] + [t2["立春"]]
        months = []
        for i, (name, term) in enumerate(mdefs):
            probe = starts[i] + dt.timedelta(minutes=10)
            q = eng.pillars_from_datetime(probe.year, probe.month, probe.day,
                                          probe.hour, probe.minute)["四柱"]
            months.append({"序": i + 1, "月名": name, "节": term,
                           "起": starts[i].strftime("%Y-%m-%d %H:%M"),
                           "止": (stops[i] - dt.timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M"),
                           **gz_info(q["月"]), "年柱": q["年"]})
        return {"scope": "months", "年": year, "日主": dm, "月": months}

    if scope == "days":
        if not d_from or not d_to:
            raise ValueError("流日查询需 from/to 参数")
        d0 = dt.date.fromisoformat(d_from)
        d1 = dt.date.fromisoformat(d_to)
        if not 0 <= (d1 - d0).days <= 62:
            raise ValueError("流日区间须为 0–62 天")
        from lunar_python import Solar as _S
        days = []
        cur = d0
        while cur <= d1:
            q = eng.pillars_from_datetime(cur.year, cur.month, cur.day, 12, 0)["四柱"]
            try:
                lu = _S.fromYmd(cur.year, cur.month, cur.day).getLunar()
                lunar = lu.getMonthInChinese() + "月" + lu.getDayInChinese()
            except Exception:  # noqa: BLE001
                lunar = ""
            days.append({"日期": cur.isoformat(), "星期": "周" + "一二三四五六日"[cur.weekday()],
                         "农历": lunar, **gz_info(q["日"])})
            cur += dt.timedelta(days=1)
        return {"scope": "days", "日主": dm, "日": days}

    if scope == "hours":
        if not date_s:
            raise ValueError("流时查询需 date 参数")
        dd = dt.date.fromisoformat(date_s)
        slots = [("早子", 0, "00:00–00:59"), ("丑", 1, "01:00–02:59"),
                 ("寅", 3, "03:00–04:59"), ("卯", 5, "05:00–06:59"),
                 ("辰", 7, "07:00–08:59"), ("巳", 9, "09:00–10:59"),
                 ("午", 11, "11:00–12:59"), ("未", 13, "13:00–14:59"),
                 ("申", 15, "15:00–16:59"), ("酉", 17, "17:00–18:59"),
                 ("戌", 19, "19:00–20:59"), ("亥", 21, "21:00–22:59"),
                 ("晚子", 23, "23:00–23:59（次日）")]
        hrs = []
        for name, h, span in slots:
            q = eng.pillars_from_datetime(dd.year, dd.month, dd.day, h, 0)["四柱"]
            hrs.append({"时辰": name, "时段": span, "日柱": q["日"], **gz_info(q["时"])})
        return {"scope": "hours", "日主": dm, "时": hrs}

    raise ValueError("scope 须为 years/months/days/hours")


def bazi_lunar(q: dict) -> dict:
    """农历/公历互转与月历信息（四柱选时弹窗用）。"""
    from lunar_python import Lunar, LunarMonth, LunarYear, Solar

    def g(k, default=None):
        v = q.get(k)
        return v[0] if v else default

    mode = g("mode") or ""
    if mode == "solar2lunar":
        dt_s = (g("dt") or "").replace("T", " ").strip()
        date_part, _, time_part = dt_s.partition(" ")
        y, m, d = (int(x) for x in date_part.split("-"))
        hh, mi = (int(x) for x in time_part.split(":")) if time_part else (0, 0)
        l = Solar.fromYmdHms(y, m, d, hh, mi, 0).getLunar()
        mm = l.getMonth()
        return {"ok": True, "solar": f"{y:04d}-{m:02d}-{d:02d}T{hh:02d}:{mi:02d}",
                "lunar": {"year": l.getYear(), "month": abs(mm), "day": l.getDay(),
                          "leap": mm < 0, "text": l.toString()}}
    if mode == "lunar2solar":
        y, m, d = int(g("y")), int(g("m")), int(g("d"))
        leap = str(g("leap") or "0") in ("1", "true", "True")
        hh, mi = int(g("h") or 0), int(g("mi") or 0)
        if not (1900 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 30):
            raise ValueError("农历日期超出支持范围（1900–2100）")
        try:
            lm = LunarMonth.fromYm(y, -m if leap else m)
        except Exception:
            lm = None
        if lm is None:
            raise ValueError(f"{y} 年不存在闰{m}月" if leap else f"{y} 年{m}月不存在")
        if d > lm.getDayCount():
            raise ValueError(f"农历{y}年{'闰' if leap else ''}{m}月只有 {lm.getDayCount()} 天")
        l = Lunar.fromYmd(y, -m if leap else m, d)
        s = l.getSolar()
        if not (1901 <= s.getYear() <= 2099):
            raise ValueError("换算所得公历年份超出排盘支持范围（1901–2099）")
        return {"ok": True,
                "solar": f"{s.getYear():04d}-{s.getMonth():02d}-{s.getDay():02d}T{hh:02d}:{mi:02d}",
                "lunar": {"year": y, "month": m, "day": d, "leap": leap, "text": l.toString()}}
    if mode == "info":
        y = int(g("y"))
        if not (1900 <= y <= 2100):
            raise ValueError("年份超出支持范围（1900–2100）")
        leap = 0
        try:
            leap = LunarYear.fromYear(y).getLeapMonth() or 0
        except Exception:
            leap = 0
        months = {}
        for m in range(1, 13):
            try:
                months[str(m)] = LunarMonth.fromYm(y, m).getDayCount()
            except Exception:
                months[str(m)] = 29
        if leap:
            try:
                months["leap%d" % leap] = LunarMonth.fromYm(y, -leap).getDayCount()
            except Exception:
                pass
        return {"ok": True, "year": y, "leap_month": leap, "months": months}
    raise ValueError("mode 须为 solar2lunar / lunar2solar / info")


def _call_openai(cfg: dict, messages: list[dict]) -> dict:
    payload = {"model": cfg["model"], "messages": messages, "stream": False,
               "temperature": cfg["temperature"], "max_tokens": cfg["max_tokens"]}
    req = urllib.request.Request(
        cfg["url"], data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    if cfg["api_key"]:
        req.add_header("Authorization", "Bearer " + cfg["api_key"])
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:800]
        raise RuntimeError(f"上游 API 返回 {exc.code}：{detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法连接 API：{exc.reason}") from exc
    except json.JSONDecodeError:
        raise RuntimeError("API 返回的不是 JSON") from None
    try:
        msg = data["choices"][0]["message"]
        content = msg["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("API 返回格式不是 OpenAI 兼容格式（缺 choices[0].message.content）") from None
    if not (content or "").strip():
        reason = str(msg.get("reasoning_content") or "")
        raise RuntimeError(
            f"模型只输出思考内容、正文为空（思考 {len(reason)} 字）："
            "请提高最大 tokens（如 4096+）或更换非推理模型")
    return {"content": content, "model": data.get("model") or cfg["model"],
            "usage": data.get("usage")}


def bazi_ai_reply(body: dict) -> dict:
    from ai_coach import build_messages, normalize_config
    cfg = normalize_config(body.get("config"))
    if body.get("test"):
        messages = [{"role": "user", "content": "请只回复两个字母：OK"}]
        cfg["max_tokens"] = min(cfg["max_tokens"], 16)
    else:
        chart = body.get("chart")
        if not isinstance(chart, dict) or not chart.get("四柱"):
            raise ValueError("缺少命盘数据（chart）")
        messages = build_messages(chart, body.get("persona"), body.get("question"),
                                  body.get("history"), allow_yingqi=bool(body.get("yingqi")))
    got = _call_openai(cfg, messages)
    return {"ok": True, "content": got["content"], "model": got["model"], "usage": got["usage"]}


def bazi_ai_stream(handler, body: dict):
    """四柱 AI 流式转发（SSE）：边生成边回传，避免长思考触发前端超时。"""
    from ai_coach import build_messages, normalize_config
    try:
        cfg = normalize_config(body.get("config"))
        chart = body.get("chart")
        if not isinstance(chart, dict) or not chart.get("四柱"):
            raise ValueError("缺少命盘数据（chart）")
        messages = build_messages(chart, body.get("persona"), body.get("question"),
                                  body.get("history"), allow_yingqi=bool(body.get("yingqi")))
        payload = {"model": cfg["model"], "messages": messages,
                   "temperature": cfg["temperature"], "max_tokens": cfg["max_tokens"],
                   "stream": True}
        headers = {"Content-Type": "application/json"}
        if cfg["api_key"]:
            headers["Authorization"] = "Bearer " + cfg["api_key"]
        up = urllib.request.Request(
            cfg["url"], data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers, method="POST")
        resp = urllib.request.urlopen(up, timeout=600)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:800]
        handler._json({"ok": False, "error": f"上游 API 返回 {exc.code}：{detail}"}, 502)
        return
    except Exception as exc:  # noqa: BLE001
        handler._json({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, 400)
        return
    try:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("Connection", "close")
        handler.end_headers()
        with resp:
            while True:
                chunk = resp.read(2048)
                if not chunk:
                    break
                handler.wfile.write(chunk)
                handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        try:
            resp.close()
        except Exception:  # noqa: BLE001
            pass


def ai_test(body: dict) -> dict:
    """统一 AI 配置的连通性测试：最小请求，不回显 Key。"""
    base = (body.get("base_url") or "").strip().rstrip("/")
    key = (body.get("api_key") or "").strip()
    model = (body.get("model") or "").strip() or "gpt-4o-mini"
    if not base.startswith(("http://", "https://")):
        raise ValueError("API 端点需以 http:// 或 https:// 开头")
    url = base if base.endswith("/chat/completions") else base + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "请只回复两个字母：OK"}],
        "temperature": 0,
        "max_tokens": 16,
        "stream": False,
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    if key:
        req.add_header("Authorization", "Bearer " + key)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"上游返回 {exc.code}：{detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法连接：{exc.reason}") from exc
    except json.JSONDecodeError:
        raise RuntimeError("返回的不是 JSON（可能不是 OpenAI 兼容接口）") from None
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("返回格式不是 OpenAI 兼容格式（缺 choices[0].message.content）") from None
    return {"ok": True, "content": str(content)[:200], "model": data.get("model") or model}


# ======================= 梅花易数 =======================
def mh_hour_no(s: str) -> int:
    s = (s or "").strip()
    if s.isdigit():
        n = int(s)
        if 1 <= n <= 12:
            return n
    if ":" in s:
        h = int(s.split(":")[0])
        return ((h + 1) % 24) // 2 + 1
    raise ValueError(f"时辰无法识别：{s!r}（用 HH:MM 或 1-12）")


def mh_parse_dt(s: str) -> dt.datetime:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"时间格式无法识别：{s!r}")


def mh_attach_gua_texts(board):
    for key in ("本卦", "互卦", "变卦"):
        layer = board[key]
        name = layer["名"]
        book = J.YAOCI.get(name, {})
        bits = layer["爻"]
        titles = [J.yao_title(name, i + 1, bits) for i in range(6)]
        layer["爻题"] = titles
        layer["爻辞"] = {t: book.get("爻辞", {}).get(t, "") for t in titles}
        layer["小象"] = {t: book.get("小象", {}).get(t, "") for t in titles}
        layer["大象"] = book.get("大象", "")
        layer["详情"] = {
            "卦名": name, "上卦": layer["上卦"], "下卦": layer["下卦"],
            "卦辞": book.get("卦辞", ""), "彖": book.get("彖", ""),
            "大象": book.get("大象", ""), "爻辞": book.get("爻辞", {}),
            "小象": book.get("小象", {}), "文言": book.get("文言", []),
            "来源": book.get("来源", ""),
        }
    return board


def mh_leixiang_table(res):
    roles = [("体卦", res["体卦"]), ("用卦", res["用卦"]),
             ("上互", res["互卦"]["上互"]), ("下互", res["互卦"]["下互"])]
    if res["变卦"] and res["变卦"] != "（无）" and res["变卦"] in M.NAME64:
        idx = 1 if res["动爻"] <= 3 else 0
        roles.append(("变卦", M.NAME64[res["变卦"]][idx]))
    table = {}
    for f in FIELDS:
        row = {}
        for role, g in roles:
            v = M.LEIXIANG.get(g, {}).get("类象", {}).get(f)
            if v:
                row[role] = v
        if row:
            table[FLABEL[f]] = row
    return table


def mh_build(q: dict):
    mode = (q.get("mode") or ["dt"])[0]
    g = lambda k, d=None: (q.get(k) or [d])[0]  # noqa: E731
    lunar_note = None
    base_date = dt.date.today()
    month = int(g("month")) if g("month") else None
    if mode == "dt":
        from lunar_python import Solar
        d = mh_parse_dt(g("dt", dt.datetime.now().strftime("%Y-%m-%d %H:%M")))
        lunar = Solar.fromYmdHms(d.year, d.month, d.day, d.hour, d.minute, 0).getLunar()
        yz = ZH_BRANCH.index(lunar.getYearZhi()) + 1
        hz = ZH_BRANCH.index(lunar.getTimeZhi()) + 1
        lm = lunar.getMonth()
        leap = lm < 0
        month_num = abs(lm) if leap else lm
        res = M.cast_datetime(yz, month_num, lunar.getDay(), hz)
        base_date = d.date()
        month = month or month_num
        lunar_note = f"农历 {lunar}（年支{lunar.getYearZhi()}={yz}，时支{lunar.getTimeZhi()}={hz}）"
        if leap:
            lunar_note += f"；闰{month_num}月按本月计"
        lunar_note += "；年支按农历年（春节换年）；23:00–23:59 按晚子时（日不变、时支子）"
        if g("place"):
            lunar_note += f"；地点 {g('place')}（时辰边界附近建议真太阳时校正）"
    elif mode == "count":
        res = M.cast_counts(int(g("count")), mh_hour_no(g("hour", "12:00")))
    elif mode == "sound":
        res = M.cast_sound(int(g("count")), mh_hour_no(g("hour", "12:00")))
    elif mode == "sound2":
        res = M.cast_two_counts(int(g("c1")), int(g("c2")), mh_hour_no(g("hour", "12:00")))
    elif mode == "words":
        res = M.cast_words(g("text", "今日动静如何"))
    elif mode == "strokes":
        std = g("standard", "kangxi")
        if g("pairs"):
            items = []
            for tok in re.split(r"[,，\s]+", g("pairs").strip()):
                if "=" in tok:
                    z, c = tok.split("=", 1)
                    items.append((z, int(c)))
            res = M.cast_words_strokes(items)
        elif g("numbers"):
            nums = [int(x) for x in re.split(r"[,，\s]+", g("numbers").strip()) if x]
            res = M.cast_words_strokes(nums)
        else:
            chars = [c for c in g("chars", "") if not c.isspace()]
            res = M.cast_words_strokes(chars, standard=std)
    elif mode == "zi":
        ch = g("char", "湖")
        if g("left") and g("right"):
            res = M.cast_one_char(ch, int(g("left")), int(g("right")), standard="manual")
        else:
            res = M.cast_one_char(ch, standard=g("standard", "kangxi"))
    elif mode == "tones":
        up = sum(int(x) for x in re.split(r"[,，\s]+", g("up", "1")) if x)
        lo = sum(int(x) for x in re.split(r"[,，\s]+", g("lo", "1")) if x)
        res = M.cast_tone_groups(up, lo)
    elif mode == "manual":
        res = M.cast_manual(g("upper", "乾"), g("lower", "兑"), int(g("moving", 1)))
    elif mode == "zhangchi":
        res = M.cast_zhangchi(int(g("zhang", 1)), int(g("chi", 2)))
    elif mode == "cunzi":
        res = M.cast_cunzi(int(g("chi", 2)), int(g("cun", 3)), mh_hour_no(g("hour", "12:00")))
    elif mode == "dir":
        obj = g("obj", "老人")
        obj_gua = M.DIR_MAP.get(obj, obj) if obj in M.DIR_MAP else OBJ_ALIAS.get(obj, obj)
        res = M.cast_direction(obj_gua, g("dir", "南"), mh_hour_no(g("hour", "12:00")))
    elif mode == "azimuth":
        res = M.cast_azimuth(g("dir", "南"), mh_hour_no(g("hour", "12:00")))
    elif mode == "color":
        res = M.cast_color(g("color", "紫"), g("dir", "南"), mh_hour_no(g("hour", "12:00")))
    else:
        raise ValueError(f"未知起卦方式：{mode}")

    question = g("question", "")
    motion = g("motion") or None
    judge = J.judge(res, question, month=month, motion=motion)
    lx = mh_leixiang_table(res)
    bd = mh_attach_gua_texts(M.board(res))
    yq = Y.yingqi(res, base_date, motion=motion,
                  switch=lambda name, mv: M.NAME64[name][1 if mv <= 3 else 0])
    return {"ok": True, "mode": mode, "result": res, "board": bd,
            "leixiang": lx, "direction": M.direction_summary(res), "body": M.body_summary(res),
            "judge": judge, "yingqi": yq, "lunar": lunar_note}


MH_GOLDEN = [
    ("观梅占", lambda: M.cast_datetime(5, 12, 17, 9),
     dict(卦名="泽火革", 动爻=1, 互="乾/巽", 变="泽山咸", 体="兑", 用="离")),
    ("牡丹占", lambda: M.cast_datetime(6, 3, 16, 4),
     dict(卦名="天风姤", 动爻=5, 互="乾/乾", 变="火风鼎", 体="巽", 用="乾")),
    ("扣门借物", lambda: M.cast_two_counts(1, 5, 10),
     dict(卦名="天风姤", 动爻=4, 互="乾/乾", 变="巽为风", 体="巽", 用="乾")),
    ("今日动静", lambda: M.cast_tone_groups(8, 5),
     dict(卦名="地风升", 动爻=1, 互="震/兑", 变="地天泰", 体="坤", 用="巽")),
    ("西林寺", lambda: M.cast_strokes(7, 8),
     dict(卦名="山地剥", 动爻=3, 互="坤/坤", 变="艮为山", 体="艮", 用="坤")),
    ("老人有忧色", lambda: M.cast_direction("乾", "巽", 4),
     dict(卦名="天风姤", 动爻=4, 互="乾/乾", 变="巽为风", 体="巽", 用="乾")),
    ("少年有喜色", lambda: M.cast_direction("艮", "离", 7),
     dict(卦名="山火贲", 动爻=5, 互="震/坎", 变="风火家人", 体="离", 用="艮")),
    ("牛哀鸣", lambda: M.cast_direction("坤", "坎", 7),
     dict(卦名="地水师", 动爻=3, 互="坤/震", 变="地风升", 体="坤", 用="坎")),
    ("鸡悲鸣", lambda: M.cast_direction("巽", "乾", 4),
     dict(卦名="风天小畜", 动爻=4, 互="离/兑", 变="乾为天", 体="乾", 用="巽")),
    ("枯枝坠地", lambda: M.cast_direction("离", "兑", 5),
     dict(卦名="火泽睽", 动爻=4, 互="坎/离", 变="山泽损", 体="兑", 用="离")),
]


def mh_selftest() -> dict:
    cases = []
    passed = 0
    for name, fn, exp in MH_GOLDEN:
        try:
            r = fn()
            got = dict(卦名=r["卦名"], 动爻=r["动爻"],
                       互=f'{r["互卦"]["上互"]}/{r["互卦"]["下互"]}', 变=r["变卦"],
                       体=r["体卦"], 用=r["用卦"])
            ok = all(got[k] == v for k, v in exp.items())
            b = M.board(r)
            ok = ok and len(b["本卦"]["爻"]) == 6 and len(b["互卦"]["爻"]) == 6
            ti_upper = r["动爻"] <= 3
            ok = ok and b["本卦"]["体用"]["上"] == ("体" if ti_upper else "用")
            cases.append({"name": name, "pass": ok, "expect": exp, "actual": got})
            passed += 1 if ok else 0
        except Exception as e:  # noqa: BLE001
            cases.append({"name": name, "pass": False, "error": str(e)})
    return {"ok": True, "total": len(MH_GOLDEN), "passed": passed, "cases": cases}


MH_SYSTEM = """你是《梅花易数》解卦助手。硬性规则：
1. 只依据用户给出的卦盘事实与规则原文讲解；不得编造卦象、爻辞、规则或应期。
2. 引用断语须注明依据（体用总诀/十八占/万物类象/周易爻辞/卦气旺衰）；不确定处标“待核”。
3. 类象多义时列候选并说明取舍条件，不武断；体用、互变、旺衰分层次讲。
4. 不作绝对化断言，不提供医疗、法律、投资保证；涉及健康/纠纷提示现实求助。
5. 输出用简体中文，分「起卦/卦象与体用/互变与过程/类象取用/旺衰/建议」六段，每段简短。"""

MH_YINGQI_ALLOW = """【应期】用户本轮已明确要求应期：可在“旺衰”段后补一小段“应期”，
只能依据用户资料中的卦气/成卦数/行坐立候选说明，逐条标出处与不确定性；
原文未列的卦（坎/离/艮）不得推补；没有候选就明说“无可靠应期规则”。"""

MH_YINGQI_DENY = """【应期禁令】本轮用户未明确要求应期：正文不得出现具体年份、月份、日期、期限、
快慢或“某日必应”式判断；卦气、成卦数、行坐立等待应期数据不得写入正文。"""


def meihua_ai_proxy(p: dict) -> dict:
    endpoint = (p.get("endpoint") or "").strip()
    key = (p.get("api_key") or "").strip()
    model = (p.get("model") or "").strip()
    persona = (p.get("persona") or "").strip()
    context = (p.get("context") or "").strip()
    question = (p.get("question") or "").strip()
    if not endpoint.startswith(("http://", "https://")):
        raise ValueError("API 端点必须以 http:// 或 https:// 开头")
    if not key:
        raise ValueError("请填写 API Key")
    if not model:
        raise ValueError("请填写模型名")
    if not context:
        raise ValueError("请先起卦，再让 AI 解卦")
    allow_yingqi = bool(p.get("yingqi"))
    url = endpoint.rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    sysmsg = (MH_SYSTEM + "\n\n" + (MH_YINGQI_ALLOW if allow_yingqi else MH_YINGQI_DENY)
              + (f"\n\n人设/语气：{persona}" if persona else ""))
    user = (f"{context}\n\n【所问】{question or '未填写（请作总体讲解）'}\n\n"
            + ("请严格按六段讲解，并在关键判断后标注依据；应期另起一小段。"
               if allow_yingqi else
               "请严格按六段讲解，并在关键判断后标注依据；本轮不要输出应期。"))
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": sysmsg},
                     {"role": "user", "content": user}],
        "temperature": 0.6, "max_tokens": 1400,
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:600]
        raise RuntimeError(f"上游 {e.code}：{detail}")
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"调用失败：{e}")
    content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    if not content.strip():
        raise RuntimeError("上游未返回内容")
    return {"ok": True, "content": content, "model": data.get("model", model),
            "usage": data.get("usage")}


# ======================= 奇门 =======================
QIMEN_CONFIG_KEYS = ("ding_ju", "jigong", "bushen", "shen_bufa", "menpo", "shigan_mu",
                     "ding_mu", "zhishi_bufa", "day_boundary")
QDT_FORMATS = ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S")


def qm_parse_dt(s: str) -> dt.datetime:
    for fmt in QDT_FORMATS:
        try:
            return dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"时间格式无法识别：{s}")


def qm_build_config(qs: dict) -> Q.QimenConfig:
    kw = {}
    for k in QIMEN_CONFIG_KEYS:
        if k in qs and qs[k][0]:
            kw[k] = qs[k][0]
    if "true_solar_time" in qs:
        kw["true_solar_time"] = qs["true_solar_time"][0] in ("1", "true", "True")
    if "longitude" in qs and qs["longitude"][0]:
        kw["longitude"] = float(qs["longitude"][0])
    return Q.QimenConfig(**kw)


def qm_payload(at: dt.datetime, cfg: Q.QimenConfig, question: str = "通用") -> dict:
    chart = Q.cast(at, cfg)
    try:
        yingqi = YQ.qimen_yingqi(chart, at.date())
    except Exception as exc:  # noqa: BLE001
        yingqi = {"tool": "奇门", "error": f"{type(exc).__name__}: {exc}"}
    return {"chart": chart, "explain": Q.explain(chart), "duan": Q.duan_yu(chart),
            "interpret": Q.interpret(chart, question), "yingqi": yingqi}


def qm_ai_stream(handler, req: dict):
    base = (req.get("base_url") or "").rstrip("/")
    if not base.startswith(("http://", "https://")):
        handler._json({"error": "base_url 需以 http(s):// 开头"}, 400)
        return
    url = base if base.endswith("/chat/completions") else base + "/chat/completions"
    payload = {
        "model": req.get("model") or "gpt-4o-mini",
        "messages": req.get("messages") or [],
        "temperature": float(req.get("temperature", 0.6)),
        "stream": True,
    }
    headers = {"Content-Type": "application/json"}
    if req.get("api_key"):
        headers["Authorization"] = "Bearer " + req["api_key"]
    up = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                headers=headers, method="POST")
    with urllib.request.urlopen(up, timeout=120) as resp:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("Connection", "close")
        handler.end_headers()
        while True:
            chunk = resp.read(1024)
            if not chunk:
                break
            handler.wfile.write(chunk)
            handler.wfile.flush()


# ======================= 静态与路由 =======================
MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
}

APP_DIRS = {
    "/bazi/": os.path.join(HERE, "apps", "bazi"),
    "/meihua/": os.path.join(HERE, "apps", "meihua"),
    "/qimen/": os.path.join(HERE, "apps", "qimen"),
    "/liuren/": os.path.join(HERE, "apps", "liuren"),
    "/ziwei/": os.path.join(HERE, "apps", "ziwei"),
}

MODULES = [
    {"id": "bazi", "name": "四柱", "full": "四柱排盘", "url": "/bazi/",
     "desc": "子平八字 · 格局用神 · 大运流年"},
    {"id": "meihua", "name": "梅花", "full": "梅花易数", "url": "/meihua/",
     "desc": "十四种起卦 · 体用互变 · 万物类象"},
    {"id": "qimen", "name": "奇门", "full": "奇门遁甲", "url": "/qimen/",
     "desc": "时家奇门 · 拆补定局 · 九宫断语"},
    {"id": "liuren", "name": "六壬", "full": "大六壬", "url": "/liuren/",
     "desc": "四课三传 · 九宗门 · 课体神煞"},
    {"id": "ziwei", "name": "紫微", "full": "紫微斗数", "url": "/ziwei/",
     "desc": "十二宫垣 · 十四主星 · 四化飞星"},
]


# ======================= 健康自检 =======================
_SELF_CHECK: dict = {"at": 0.0, "result": None}
_SELF_CHECK_TTL = 60.0  # 秒；期间 /api/health 复用上次结论


def _selfcheck(fresh: bool = False) -> dict:
    """真跑一遍五术的最小用例，返回 {engine: {ok, detail, ms}}。

    只做轻量断言（每项 <1s 量级），不代替 tests/ 下的完整对拍：
      bazi   —— 已知时刻排四柱，与 lunar_python 独立实现互证；
      meihua —— 年月日时起卦最小例 + 互变卦结构断言；
      qimen  —— 一次排盘：九宫齐全、八门为标准门集、规则库已加载；
      liuren —— 前端资源存在（纯前端引擎，启动期只验资源）；
      ziwei  —— 前端资源存在（iztro 库文件可读且体积正常）。
    """
    now = time.time()
    if not fresh and _SELF_CHECK["result"] and now - _SELF_CHECK["at"] < _SELF_CHECK_TTL:
        cached = dict(_SELF_CHECK["result"])
        cached["cached"] = True
        return cached

    checks: dict = {}

    def run(name, fn):
        t0 = time.time()
        try:
            detail = fn()
            checks[name] = {"ok": True, "detail": detail, "ms": round((time.time() - t0) * 1000)}
        except Exception as exc:  # noqa: BLE001
            checks[name] = {"ok": False, "detail": f"{type(exc).__name__}: {exc}",
                            "ms": round((time.time() - t0) * 1000)}

    def chk_bazi() -> str:
        p = B.BaziEngine().pillars_from_datetime(1984, 2, 5, 8, 30)
        qz = p["四柱"]
        from lunar_python import Solar
        ec = Solar.fromYmdHms(1984, 2, 5, 8, 30, 0).getLunar().getEightChar()
        ref = [ec.getYear(), ec.getMonth(), ec.getDay(), ec.getTime()]
        mine = [qz["年"], qz["月"], qz["日"], qz["时"]]
        if mine != ref:
            raise AssertionError(f"四柱 {mine} != 独立实现 {ref}")
        return "1984-02-05 08:30 → " + " ".join(mine) + "（与 lunar_python 一致）"

    def chk_meihua() -> str:
        # 子年正月初一子时：1+1+1=3 → 离上；3+1(时)=4? 动爻=(3+1)%6=4？以引擎口径为准做结构断言
        r = M.cast_datetime(1, 1, 1, 1)
        b = M.board(r)
        if r["卦名"] != "火雷噬嗑" or r["动爻"] != 4:
            raise AssertionError(f"金例不符：{r['卦名']} 动{r['动爻']}（期望 火雷噬嗑 动4）")
        if len(b["本卦"]["爻"]) != 6 or not b["互卦"]["名"] or not b["变卦"]["名"]:
            raise AssertionError("互/变卦结构缺失")
        return f"{r['卦名']} 动{r['动爻']}爻，互{b['互卦']['名']} 变{b['变卦']['名']}"

    def chk_qimen() -> str:
        c = Q.cast(dt.datetime(2026, 10, 30, 12, 0))
        doors = set(c["pan"]["ba_men"].values())
        want = {"休门", "生门", "伤门", "杜门", "景门", "死门", "惊门", "开门"}
        if doors != want:
            raise AssertionError(f"八门异常：{sorted(doors)}")
        if len(c["cells"]) != 9 or not c["term"].get("ju"):
            raise AssertionError("九宫/定局缺失")
        n_rules = len(Q._load_duan() or [])
        return f"{c['term']['dun']}遁{c['term']['ju']}局 · 九宫八门齐 · 断语库 {n_rules} 条"

    def chk_static(app: str, min_size: int) -> str:
        path = os.path.join(HERE, "apps", app, "index.html")
        size = os.path.getsize(path) if os.path.isfile(path) else 0
        if size < min_size:
            raise AssertionError(f"{app}/index.html 缺失或异常（{size} 字节）")
        extra = ""
        if app == "ziwei":
            lib = os.path.join(HERE, "apps", "ziwei", "iztro.min.js")
            lsize = os.path.getsize(lib) if os.path.isfile(lib) else 0
            if lsize < 100_000:
                raise AssertionError(f"iztro.min.js 缺失或异常（{lsize} 字节）")
            extra = f"，iztro 库 {lsize // 1024}KB"
        return f"{app}/index.html {size // 1024}KB{extra}"

    run("bazi", chk_bazi)
    run("meihua", chk_meihua)
    run("qimen", chk_qimen)
    run("liuren", lambda: chk_static("liuren", 50_000))
    run("ziwei", lambda: chk_static("ziwei", 50_000))

    result = {
        "ok": all(v["ok"] for v in checks.values()),
        "checked_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "checks": checks,
    }
    _SELF_CHECK["at"] = now
    _SELF_CHECK["result"] = result
    out = dict(result)
    out["cached"] = False
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "WanjieDaheti/1.0"

    # ---------- helpers ----------
    def _send(self, code: int, body: bytes, ctype: str):
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except ConnectionError:
            # 客户端提前断开（刷新、取消、无头浏览器关闭、curl 超时）。
            # 属正常中止，不是服务端故障：不再向上抛，避免 except 分支二次写失败。
            self.close_connection = True

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _read_json(self, limit: int = 4_000_000) -> dict:
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > limit:
            raise ValueError("请求体为空或过大")
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def _serve_file(self, path: str) -> bool:
        real = os.path.realpath(path)
        if not real.startswith(os.path.realpath(HERE) + os.sep) or not os.path.isfile(real):
            return False
        ext = os.path.splitext(real)[1].lower()
        st = os.stat(real)
        etag = f'"{st.st_mtime_ns:x}-{st.st_size:x}"'
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.end_headers()
            return True
        with open(real, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("ETag", etag)
        self.send_header("Cache-Control", "no-cache")  # 允许缓存，每次再校验
        self.end_headers()
        try:
            self.wfile.write(data)
        except ConnectionError:
            # 静态资源写到一半客户端就关了（切页、无头截图），静默结束即可
            self.close_connection = True
        return True

    def log_message(self, fmt, *args):
        pass

    # ---------- GET ----------
    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        path = unquote(u.path)
        q = parse_qs(u.query)
        try:
            # 首页
            if path in ("/", "/index.html"):
                if self._serve_file(os.path.join(HERE, "portal", "index.html")):
                    return
                self._json({"ok": False, "error": "缺少 portal/index.html"}, 500)
                return
            if path == "/api/health":
                sc = _selfcheck(fresh=(q.get("fresh") or [""])[0] in ("1", "true", "True"))
                self._json({
                    "ok": sc["ok"],
                    "name": "万界大合体",
                    "version": "1.1",
                    "modules": MODULES,
                    # engines 布尔映射保留：旧调用方（页脚判断 d.ok）不受影响
                    "engines": {k: v["ok"] for k, v in sc["checks"].items()},
                    "selftest": {"checked_at": sc["checked_at"], "cached": sc["cached"],
                                 "checks": sc["checks"]},
                    "time": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                return
            # 静态资源
            if path == "/favicon.ico":
                if self._serve_file(os.path.join(HERE, "assets", "favicon.svg")):
                    return
            if path.startswith("/assets/"):
                if self._serve_file(os.path.join(HERE, path.lstrip("/"))):
                    return
                self._json({"ok": False, "error": "资源不存在"}, 404)
                return
            # 应用目录（带尾斜杠）
            for prefix, folder in APP_DIRS.items():
                if path == prefix.rstrip("/"):
                    self.send_response(302)
                    self.send_header("Location", prefix)
                    self.end_headers()
                    return
                if path == prefix:
                    if self._serve_file(os.path.join(folder, "index.html")):
                        return
                    self._json({"ok": False, "error": "页面不存在"}, 404)
                    return
                if path.startswith(prefix) and "/api/" not in path:
                    rel = path[len(prefix):]
                    if rel and self._serve_file(os.path.join(folder, rel)):
                        return
                    self._json({"ok": False, "error": "资源不存在"}, 404)
                    return
            # ---------- 四柱 API ----------
            if path == "/bazi/api/paipan":
                try:
                    dt_s = (q.get("dt") or [""])[0].replace("T", " ").strip()
                    date_part, _, time_part = dt_s.partition(" ")
                    y, m, d = (int(x) for x in date_part.split("-"))
                    hh, mi = (int(x) for x in time_part.split(":")) if time_part else (12, 0)
                    if not (1901 <= y <= 2099):
                        raise ValueError(f"历法层节气表支持 1901–2099 年，收到 {y}")
                    _g = (q.get("gender") or [None])[0]
                    if _g and _g not in ("男", "女"):
                        raise ValueError("gender 仅接受 男 / 女")
                    self._json(bazi_paipan(y, m, d, hh, mi,
                                           (q.get("gender") or [None])[0],
                                           int(q["year"][0]) if q.get("year") else None,
                                           (q.get("boundary") or [None])[0]))
                except Exception as exc:  # noqa: BLE001
                    msg = f"{type(exc).__name__}: {exc}"
                    self._json({"错误": msg, "ok": False, "error": msg}, 400)
                return
            if path == "/bazi/api/analyze":
                try:
                    self._json(bazi_analyze(q["y"][0], q["m"][0], q["d"][0], q["t"][0],
                                            (q.get("gender") or [None])[0],
                                            int(q["year"][0]) if q.get("year") else None))
                except Exception as exc:  # noqa: BLE001
                    msg = f"{type(exc).__name__}: {exc}"
                    self._json({"错误": msg, "ok": False, "error": msg}, 400)
                return
            if path == "/bazi/api/flow":
                try:
                    dt_s = (q.get("dt") or [""])[0].replace("T", " ").strip()
                    date_part, _, time_part = dt_s.partition(" ")
                    y, m, d = (int(x) for x in date_part.split("-"))
                    hh, mi = (int(x) for x in time_part.split(":")) if time_part else (12, 0)
                    if not (1901 <= y <= 2099):
                        raise ValueError(f"历法层支持 1901–2099 年，收到 {y}")
                    scope = (q.get("scope") or ["years"])[0]
                    self._json(bazi_flow(
                        scope, y, m, d, hh, mi,
                        (q.get("gender") or [None])[0],
                        int(q["year"][0]) if q.get("year") else None,
                        (q.get("from") or [None])[0],
                        (q.get("to") or [None])[0],
                        (q.get("date") or [None])[0],
                        (q.get("boundary") or [None])[0],
                        (q.get("ys") or [None])[0],
                    ))
                except Exception as exc:  # noqa: BLE001
                    msg = f"{type(exc).__name__}: {exc}"
                    self._json({"错误": msg, "ok": False, "error": msg}, 400)
                return
            if path == "/bazi/api/reverse":
                try:
                    pillars = {
                        "年": (q.get("y") or q.get("year") or [""])[0].strip(),
                        "月": (q.get("m") or q.get("month") or [""])[0].strip(),
                        "日": (q.get("d") or q.get("day") or [""])[0].strip(),
                        "时": (q.get("t") or q.get("hour") or [""])[0].strip(),
                    }
                    self._json(BR.reverse_pillars(BAZI, pillars))
                except Exception as exc:  # noqa: BLE001
                    msg = f"{type(exc).__name__}: {exc}"
                    self._json({"ok": False, "valid": False, "error": msg, "errors": [msg],
                                "candidates": [], "count": 0}, 400)
                return
            if path == "/bazi/api/lunar":
                try:
                    self._json(bazi_lunar(q))
                except Exception as exc:  # noqa: BLE001
                    msg = f"{type(exc).__name__}: {exc}"
                    self._json({"ok": False, "error": msg}, 400)
                return
            # ---------- 梅花 API ----------
            if path == "/meihua/api/cast":
                self._json(mh_build(q))
                return
            if path == "/meihua/api/selftest":
                self._json(mh_selftest())
                return
            if path == "/meihua/api/waiying":
                text = (q.get("q") or [""])[0]
                ti = (q.get("ti") or [None])[0]
                self._json(W.match(text, ti))
                return
            if path == "/meihua/api/now":
                self._json({"now": dt.datetime.now().strftime("%Y-%m-%d %H:%M")})
                return
            # ---------- 奇门 API ----------
            if path == "/qimen/api/now":
                self._json({"now": dt.datetime.now().strftime("%Y-%m-%dT%H:%M")})
                return
            if path == "/qimen/api/chart":
                at = qm_parse_dt((q.get("dt") or [dt.datetime.now().strftime("%Y-%m-%dT%H:%M")])[0])
                cfg = qm_build_config(q)
                question = (q.get("question") or ["通用"])[0] or "通用"
                self._json(qm_payload(at, cfg, question))
                return
            self._json({"ok": False, "error": f"未知路径 {path}"}, 404)
        except Exception as exc:  # noqa: BLE001
            self._json({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, 400)

    # ---------- POST ----------
    def do_POST(self):  # noqa: N802
        u = urlparse(self.path)
        path = unquote(u.path)
        try:
            if path == "/bazi/api/ai":
                try:
                    self._json(bazi_ai_reply(self._read_json()))
                except ValueError as exc:
                    self._json({"ok": False, "error": str(exc)}, 400)
                except Exception as exc:  # noqa: BLE001
                    self._json({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, 502)
                return
            if path == "/bazi/api/ai/stream":
                bazi_ai_stream(self, self._read_json())
                return
            if path == "/meihua/api/ai":
                try:
                    self._json(meihua_ai_proxy(self._read_json()))
                except ValueError as exc:
                    self._json({"ok": False, "error": str(exc)}, 400)
                except Exception as exc:  # noqa: BLE001
                    self._json({"ok": False, "error": str(exc)}, 502)
                return
            if path == "/qimen/api/ai":
                try:
                    qm_ai_stream(self, self._read_json(1_000_000))
                except urllib.error.HTTPError as e:
                    detail = e.read()[:500].decode("utf-8", "replace")
                    self._json({"error": f"上游返回 {e.code}：{detail}"}, 502)
                except Exception as e:  # noqa: BLE001
                    try:
                        self._json({"error": str(e)}, 502)
                    except Exception:
                        pass
                return
            if path == "/api/ai-test":
                try:
                    self._json(ai_test(self._read_json(200_000)))
                except ValueError as exc:
                    self._json({"ok": False, "error": str(exc)}, 400)
                except Exception as exc:  # noqa: BLE001
                    self._json({"ok": False, "error": str(exc)}, 502)
                return
            self._json({"ok": False, "error": f"未知路径 {path}"}, 404)
        except Exception as exc:  # noqa: BLE001
            self._json({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, 400)


class QuietServer(ThreadingHTTPServer):
    """浏览器刷新、取消请求、无头截图提前关闭等会造成 WinError 10053/10054。
    这类连接中止不是服务端故障，不打印 traceback；真实异常仍照常上报。"""

    daemon_threads = True

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionError, TimeoutError)):
            return
        super().handle_error(request, client_address)


def main() -> int:
    ap = argparse.ArgumentParser(description="万界大合体 · 五术合一推演系统")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    args = ap.parse_args()
    try:
        srv = QuietServer((args.host, args.port), Handler)
    except OSError as exc:
        print(f"[启动失败] 端口 {args.port} 无法使用：{exc}")
        print("可能已有本系统在运行，或该端口被其他程序占用。")
        print(f"可换一个端口，例如：python server.py --port {args.port + 1}")
        return 2
    url = f"http://{args.host}:{args.port}/"
    print("=" * 56)
    print("  万界大合体 · 五术合一推演系统")
    print(f"  首页：{url}")
    print("  四柱 /bazi    梅花 /meihua   奇门 /qimen")
    print("  六壬 /liuren  紫微 /ziwei")
    print("  Ctrl+C 停止")
    print("=" * 56)
    if args.open:
        import threading
        import webbrowser
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
