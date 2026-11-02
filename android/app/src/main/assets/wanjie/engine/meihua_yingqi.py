# -*- coding: utf-8 -*-
"""梅花易数应期落地：卦气候选日 + 成卦总数 + 行/坐/立。

规则出处：
- 卷二《先天后天论》：「先天之卦，定事應之期，則取之卦氣，如乾、兌則應如庚、辛及申金之日，
  或坤為戌、亥之日時，兌為酉日時。如震、巽當應於甲、乙及支木之日，或震取卯，巽取辰之類。」
- 卷二《老人有忧色占》附：「行則應速，以成卦之數中分而取其半；坐則事應遲，當倍其成卦之數；
  立則半遲半速，止以成卦之數定之。」
- 卷三《占卜克应之诀》：「以數而刻期……視全卦之數，以為約定之期。」
未明列之卦（坎/离/艮）不推补：原文只列乾、兑、坤、震、巽，按“宁缺毋滥”留空。
"""
import datetime as dt

try:
    from lunar_python import Solar
except ImportError:  # pragma: no cover
    Solar = None

# 卦气应期表：只录原文明确列出的卦与干支，不按五行推补。
# 原文：「乾、兑则应如庚、辛及申金之日，或坤为戌、亥之日时，兑为酉日时。
#        如震、巽当应于甲、乙及支木之日，或震取卯，巽取辰之类。」
QI = {
    "乾": {"干": ["庚", "辛"], "支": ["申"], "级": "[原文]"},
    "兑": {"干": ["庚", "辛"], "支": ["申", "酉"], "级": "[原文]"},
    "坤": {"干": [], "支": ["戌", "亥"], "级": "[原文]"},
    "震": {"干": ["甲", "乙"], "支": ["卯"], "级": "[原文]"},
    "巽": {"干": ["甲", "乙"], "支": ["辰"], "级": "[原文]"},
}


def ganzhi_of(d: dt.date) -> str:
    """公历日 → 日干支（经 lunar_python；不可用时返回空串）。"""
    if Solar is None:
        return ""
    lunar = Solar.fromYmdHms(d.year, d.month, d.day, 12, 0, 0).getLunar()
    return lunar.getDayInGanZhi()


def dates_for_gua(gua: str, base: dt.date, days: int = 60, limit: int = 6) -> dict:
    """从基准日起 days 天内，找该卦卦气所应之日（干或支相符）。"""
    q = QI.get(gua)
    if not q:
        return {"卦": gua, "级": "[无]", "候选": [], "说明": "未收录"}
    cands = []
    total = 0
    for i in range(days + 1):
        d = base + dt.timedelta(days=i)
        gz = ganzhi_of(d)
        if not gz:
            continue
        if gz[0] in q["干"] or gz[1] in q["支"]:
            total += 1
            if len(cands) < limit:
                cands.append({"日期": d.strftime("%Y-%m-%d"), "日干支": gz,
                              "值": "干" if gz[0] in q["干"] else "支"})
    parts = []
    if q["干"]:
        parts.append("干" + "/".join(q["干"]))
    if q["支"]:
        parts.append("支" + "/".join(q["支"]))
    return {"卦": gua, "级": q["级"], "候选": cands, "命中数": total,
            "规则": " 或 ".join(parts)}


def yingqi(res: dict, base: dt.date, motion: str | None = None,
           days: int = 60, switch=None) -> dict:
    """综合应期：卦气（体/用/变）＋成卦总数＋行坐立。switch 为可选的卦→变卦取卦函数。"""
    out = {"基准日": base.strftime("%Y-%m-%d"), "卦气": [],
           "成卦总数": None, "动静": None, "说明": []}
    roles = [("体卦", res.get("体卦")), ("用卦", res.get("用卦"))]
    chg = res.get("变卦")
    if switch and chg and chg not in (None, "（无）"):
        roles.append(("变卦", switch(chg, res.get("动爻", 0))))
    for role, g in roles:
        if g:
            out["卦气"].append({"角色": role, **dates_for_gua(g, base, days)})
    n = res.get("总数")
    if n:
        d = base + dt.timedelta(days=int(n))
        out["成卦总数"] = {"数": n, "日期": d.strftime("%Y-%m-%d"),
                           "说明": f"成卦之数 {n}，按日计（原文「以成卦之數定之」）"}
    if motion and n:
        if motion == "行":
            val = int(n) // 2
            why = f"成卦之数 {n} 中分取半（行则应速）"
        elif motion == "坐":
            val = int(n) * 2
            why = f"成卦之数 {n} 倍之（坐则应迟）"
        elif motion == "立":
            val = int(n)
            why = f"成卦之数 {n} 全数（立则半迟半速）"
        else:
            val, why = None, f"未知动静：{motion}"
        if val:
            out["动静"] = {"动静": motion, "数": val,
                           "日期": (base + dt.timedelta(days=val)).strftime("%Y-%m-%d"),
                           "说明": why + "（《老人有忧色占》附）"}
    out["说明"] = [
        "[原文] 卦气应期只取原文所列之乾、兑、坤、震、巽；坎/离/艮原文未列，不推补、不输出候选。",
        "[原文] 成卦总数按日计；原文亦提示「永遠之占，則以日為月，以月為年」，长事须自行换算。",
        "[待核] 卦气日期按当前历法库日干支计算；跨节气/换年边界未做额外校正。",
    ]
    return out
