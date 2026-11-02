# -*- coding: utf-8 -*-
"""应期引擎（服务端）：奇门、八字。

原则：只输出有明确出处的规则；原文未列或无法核实的组合不写入。
- 奇门：据《奇门法窍·论应期》的值符相冲/相刑/旬空三法。
- 八字：据 rules/10-运岁.json 的 YS-004/005/009/011/013/015/016。
六壬、紫微的应期在前端 assets/yingqi.js 中计算（纯前端盘面）。
"""
from __future__ import annotations

import datetime as dt
from typing import Iterable

try:
    from lunar_python import Solar
except ImportError:  # pragma: no cover
    Solar = None

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
CHONG = {"子": "午", "午": "子", "丑": "未", "未": "丑", "寅": "申", "申": "寅",
         "卯": "酉", "酉": "卯", "辰": "戌", "戌": "辰", "巳": "亥", "亥": "巳"}
HE6 = {"子": "丑", "丑": "子", "寅": "亥", "亥": "寅", "卯": "戌", "戌": "卯",
       "辰": "酉", "酉": "辰", "巳": "申", "申": "巳", "午": "未", "未": "午"}
# 刑：据《奇门法窍·论应期》三例（子刑卯、戌刑未、寅刑巳）及通行三刑
XING = {
    "子": ["卯"], "卯": ["子"],
    "寅": ["巳", "申"], "巳": ["申", "寅"], "申": ["寅", "巳"],
    "丑": ["戌", "未"], "戌": ["未", "丑"], "未": ["丑", "戌"],
    "辰": ["辰"], "午": ["午"], "酉": ["酉"], "亥": ["亥"],
}

# 八字应期只取“条件命中即列”的岁运规则；YS-009 为通用层级，不逐条算应期。
BZ_RULES = {
    "YS-010": {"title": "岁伤日干与日犯岁君", "level": "[原文]",
               "source": "rules/10-运岁.json YS-010（三命通会 卷02）"},
    "YS-011": {"title": "真太岁 / 征太岁 / 岁运并临", "level": "[原文]",
               "source": "rules/10-运岁.json YS-011（三命通会 卷02）"},
    "YS-012": {"title": "日犯岁君轻重", "level": "[原文]",
               "source": "rules/10-运岁.json YS-012（三命通会 卷02）"},
    "YS-013": {"title": "伏吟 / 返吟", "level": "[原文]",
               "source": "rules/10-运岁.json YS-013（三命通会 卷02）"},
    "YS-015": {"title": "晦气煞", "level": "[原文]",
               "source": "rules/10-运岁.json YS-015（三命通会 卷02）"},
    "YS-016": {"title": "大运与太岁克冲", "level": "[原文]",
               "source": "rules/10-运岁.json YS-016（三命通会 卷02）"},
}


def day_gz(d: dt.date) -> str:
    """公历日 → 日干支（lunar_python；不可用时按 1984-01-31 甲子锚点）。"""
    if Solar is not None:
        return Solar.fromYmdHms(d.year, d.month, d.day, 12, 0, 0).getLunar().getDayInGanZhi()
    anchor = dt.date(1984, 1, 31)
    i = ((d - anchor).days % 60 + 60) % 60
    return GAN[i % 10] + ZHI[i % 12]


def next_dates_for_branch(branch: str, base: dt.date, days: int = 60,
                          limit: int = 8) -> list[dict]:
    out: list[dict] = []
    for i in range(days + 1):
        if len(out) >= limit:
            break
        d = base + dt.timedelta(days=i)
        gz = day_gz(d)
        if gz and gz[1] == branch:
            out.append({"date": d.isoformat(), "gz": gz})
    return out


def _norm_gong(v) -> str:
    if v is None:
        return ""
    m = str(v)
    return m


def qimen_yingqi(chart: dict, base: dt.date | None = None) -> dict:
    """奇门应期：据《奇门法窍·论应期》值符相冲/相刑/旬空三法。"""
    base = base or dt.date.today()
    xun = str(((chart.get("xun_kong") or {}).get("xun") or ""))
    fu_zhi = xun[1] if len(xun) >= 2 else ""
    zf = chart.get("zhi_fu") or {}
    zs = chart.get("zhi_shi") or {}
    gong = _norm_gong(zf.get("add_to_gong"))
    cell = ((chart.get("cells") or {}).get(gong) or {})
    palace_zhi = list(cell.get("zhi") or [])
    kong = bool(cell.get("kong"))
    kong_branches = list((chart.get("xun_kong") or {}).get("kong") or [])
    source = "《奇门法窍·论应期》正文.txt#L935"

    sections = [{
        "title": "一、值符值使",
        "items": [
            {"text": f"值符 {zf.get('star', '—')}（{zf.get('home_gong', '—')}宫→{gong or '—'}宫）；"
                     f"值使 {zs.get('door', '—')}（{zs.get('home_gong', '—')}宫→{zs.get('add_to_gong', '—')}宫）",
             "src": "奇门盘面", "level": "[盘面]"},
            {"text": f"旬首 {xun or '—'}，值符所带之支 {fu_zhi or '—'}；值符落宫地支 "
                     f"{'、'.join(palace_zhi) or '—'}；旬空 {'、'.join(kong_branches) or '—'}",
             "src": "奇门盘面", "level": "[盘面]"},
            {"text": "符应主先，使应符后。", "src": source, "level": "[原文]"},
        ],
    }]

    mode = ""
    basis = ""
    cand_branches: list[str] = []
    if fu_zhi and any(CHONG.get(fu_zhi) == z or CHONG.get(z) == fu_zhi for z in palace_zhi):
        mode = "冲"
        cand_branches = [HE6[fu_zhi]]
        hit = next(z for z in palace_zhi if CHONG.get(fu_zhi) == z or CHONG.get(z) == fu_zhi)
        basis = (f"值符支 {fu_zhi} 与落宫地支 {hit} 相冲；原文“逢冲以决其合定支”，"
                 f"{fu_zhi} 与 {HE6[fu_zhi]} 合，故先取 {HE6[fu_zhi]} 日/月/年。")
    elif fu_zhi and any(z in XING.get(fu_zhi, []) for z in palace_zhi):
        mode = "刑"
        cand_branches = [HE6[fu_zhi]]
        hit = next(z for z in palace_zhi if z in XING.get(fu_zhi, []))
        basis = (f"值符支 {fu_zhi} 与落宫地支 {hit} 相刑；原文“值符相刑法，定支者亦如是”，"
                 f"仍取 {fu_zhi} 之六合 {HE6[fu_zhi]}。")
    elif kong:
        mode = "空"
        cand_branches = list(kong_branches)
        basis = (f"值符落宫逢旬空（{'、'.join(palace_zhi) or '—'}）；原文“直符落在旬空，必以出旬断之”，"
                 f"应在出旬之 {'、'.join(kong_branches) or '—'} 日；原文又谓“以戌为重，阳与阳比，阴与阴比”，"
                 "本工具并列空支，不替读者定轻重。")
    else:
        basis = ("值符落宫与旬首支既不冲、又不刑、又不空。原文要求“看天盘六仪所带之支以定，"
                 "其冲合逢冲以决其合、逢合以决其冲”，再以星门生克“生逢生日、克逢克日”定应；"
                 "本工具不自动裁定此类组合，避免把未明列的条件写成定应。")

    sections.append({
        "title": "二、定支",
        "items": [{"text": basis, "src": source, "level": "[原文]"}],
    })

    candidates = []
    for z in cand_branches:
        for x in next_dates_for_branch(z, base, days=60, limit=6):
            candidates.append({
                "date": x["date"], "gz": x["gz"],
                "basis": f"{mode}法取支 {z}；{basis}",
                "src": source, "level": "[原文]",
            })

    if not candidates:
        sections.append({
            "title": "三、候选",
            "items": [{"text": "未自动生成候选日；请按原文人工取天盘六仪带支、星门生克与值使先后。",
                       "src": source, "level": "[原文]"}],
        })

    notes = [
        "原文总纲：应何年月日时要看事之远近、星门奇仪衰旺，“神而明之，不可执定”。",
        "本工具只自动执行“值符相冲 / 相刑 / 旬空”三法；其余条件保留原文，不臆造算法。",
        "应期单位可为年/月/日/时；本表按 60 日内日干支列候选，长事须按原文换算。",
    ]
    gaps = [
        "天盘六仪所带之支的取法，已收录文本未给出可逐步核对的统一表，未写入自动算法。",
        "“生逢生日、克逢克日”的星门生克应日，未建立可核对的自动映射，未写入自动算法。",
        "值使应期（“使应符后”）原文未给独立例句，未写入自动算法。",
    ]
    return {
        "tool": "奇门", "title": "奇门遁甲应期（法窍三法）",
        "base": base.isoformat(), "sections": sections,
        "candidates": candidates, "notes": notes, "gaps": gaps,
    }


def _original_guan_cai_sha(chart: dict) -> dict[str, bool]:
    """原局是否见官/财/煞（天干＋藏干）。"""
    seen = {"官": False, "财": False, "煞": False}
    ss = chart.get("十神") or {}
    vals: list[str] = []
    for v in (ss.get("天干") or {}).values():
        vals.append(str(v))
    for col in (ss.get("藏干") or {}).values():
        if isinstance(col, dict):
            vals.extend(str(v) for v in col.values())
    for v in vals:
        if v == "正官":
            seen["官"] = True
        elif v == "七杀":
            seen["煞"] = True
        elif v in ("正财", "偏财"):
            seen["财"] = True
    return seen


def bazi_yingqi(chart: dict, birth_year: int, gender: str | None,
                base_year: int | None = None, years: int = 10) -> dict:
    """八字应期：岁运候选。

    - YS-005：原有官/财/煞，行相应大运而发（十年窗口）。
    - YS-004/010/011/012/013/015/016：流年条件命中（逐年候选）。
    不输出流月/流日：现有规则库没有可编码的流月流日应期表。
    """
    base_year = base_year or dt.date.today().year
    sections: list[dict] = []
    candidates: list[dict] = []
    notes: list[str] = []
    gaps: list[str] = []

    dy = chart.get("大运") or {}
    rows = dy.get("大运（前八步）") or []
    orig = _original_guan_cai_sha(chart)
    dy_items = []
    if rows:
        for r in rows:
            gz = str(r.get("干支") or "")
            god = str(r.get("十神（干）") or "")
            kind = None
            if orig["官"] and god == "正官":
                kind = "官"
            elif orig["煞"] and god == "七杀":
                kind = "煞"
            elif orig["财"] and god in ("正财", "偏财"):
                kind = "财"
            if not kind:
                continue
            s = r.get("起始年（约）")
            e = r.get("结束年（约）")
            try:
                sy, ey = int(round(float(s))), int(round(float(e)))
            except (TypeError, ValueError):
                sy = ey = None
            window = (f"{sy}–{ey}年" if sy is not None else
                      f"{r.get('起始岁（约）')}–{r.get('结束岁（约）')}岁")
            dy_items.append({
                "text": f"{gz}运（{window}）：原局有{kind}，大运干{gz[0] if gz else '—'}为{god}，"
                        f"原文“原有{kind}，行{kind}运而{kind}事应”。",
                "src": "YS-005", "level": "[原文]",
            })
            candidates.append({
                "window": window, "gz": gz,
                "basis": f"原局有{kind}，行{kind}运而{kind}事应（大运十年窗口，不精确到年）。",
                "src": "YS-005", "level": "[原文]",
            })
    else:
        dy_items.append({"text": "未生成大运（未填性别时引擎不出大运）；补性别后可重排。",
                         "src": "操作提示"})
    sections.append({"title": "一、大运窗口（原有官财煞）", "items": dy_items})

    ln_items = []
    if gender and rows:
        try:
            from bazi_engine import BaziEngine
            from yunsui_engine import YunSuiEngine
        except Exception:  # pragma: no cover
            BaziEngine = None  # type: ignore
            YunSuiEngine = None  # type: ignore
        if YunSuiEngine is not None:
            eng = BaziEngine()
            yse = YunSuiEngine(eng)
            qz = chart.get("四柱") or {}
            jie = chart.get("节气距离")
            yong = (((chart.get("格局") or {}).get("用神") or {}).get("定神") or {}).get("神")
            seen = set()
            for y in range(base_year, base_year + max(1, years)):
                try:
                    ln = yse.liunian(qz, y, gender=gender, birth_year=birth_year,
                                     jie_days=jie, yong_shen=yong)
                except Exception:
                    continue
                gz = ((ln.get("流年") or {}).get("干支") or "")
                for rel in (ln.get("关系") or []):
                    rule = str(rel.get("规则") or "")
                    info = BZ_RULES.get(rule)
                    if not info:
                        continue
                    key = (y, rule, str(rel.get("条件") or ""))
                    if key in seen:
                        continue
                    seen.add(key)
                    basis = f"{rel.get('条件', '')}：{rel.get('结论', '')}"
                    ln_items.append({
                        "text": f"{y}年（{gz}）{info['title']}：{basis}",
                        "src": f"{rule}｜{info['source']}", "level": info["level"],
                    })
                    candidates.append({
                        "year": y, "gz": gz,
                        "basis": f"{info['title']}：{basis}",
                        "src": rule, "level": info["level"],
                    })
    if not ln_items:
        ln_items.append({
            "text": "未生成流年应期候选；需填性别（出大运）并在规则命中时列出。"
                    "即使填了性别，也只有 YS 条件命中才列，不把普通流年写成应期。",
            "src": "操作提示",
        })
    sections.append({"title": "二、流年条件命中", "items": ln_items})

    notes = [
        "八字应期以岁运为纲：大运十年、流年一年（YS-009）；本表只列规则命中项，不作吉凶总评。",
        "“原有官财灾则行相应运而发”是原文的条件句，不等于该十年必发；须合原局喜忌、格局成破与现实条件。",
        "岁运并临、真太岁、征太岁、返吟伏吟、晦气煞等皆为条件提示，不直接等同于灾祸。",
    ]
    gaps = [
        "流月/流日应期：现有 rules/10-运岁.json 未提供可编码的流月流日应期表，未写入。",
        "神煞应期（天月德、贵人等）未单独形成应期规则，未写入。",
        "“得气深浅、迎运/过运”只有方向性原文（YS-006），未给可核对的年份表，未写入自动候选。",
    ]
    return {
        "tool": "八字", "title": "四柱应期（岁运候选）",
        "base": str(base_year), "sections": sections,
        "candidates": candidates, "notes": notes, "gaps": gaps,
    }
