# -*- coding: utf-8 -*-
"""三要十应外应匹配：把所见所闻映射为卦，与体卦合参生克。

原则：只给候选，不自动择一；同一类别取最长匹配词（如“东南”优先于“东”）；
引用出处保留（卷二·三要灵应/十应诸目、卷三·占卜十应诀）。
"""
import json
import os

HERE = os.path.dirname(__file__)
DATA = json.load(open(os.path.join(HERE, "..", "knowledge", "03-梅花易数",
                                   "十应外应.json"), encoding="utf-8"))

WX = {"乾": "金", "兑": "金", "离": "火", "震": "木", "巽": "木", "坎": "水", "艮": "土", "坤": "土"}
SHENG = {"金": "水", "水": "木", "木": "火", "火": "土", "土": "金"}
KE = {"金": "木", "木": "土", "土": "水", "水": "火", "火": "金"}


def relation(wai: str, ti: str):
    """外应卦（当作外卦/用）与体卦的五行关系。"""
    if wai not in WX or ti not in WX:
        return None
    a, b = WX[wai], WX[ti]
    if a == b:
        return "比和（吉）"
    if SHENG[a] == b:
        return "外应生体（吉）"
    if SHENG[b] == a:
        return "体生外应（泄）"
    if KE[a] == b:
        return "外应克体（凶）"
    if KE[b] == a:
        return "体克外应（吉）"
    return None


def match(text: str, ti: str | None = None) -> dict:
    text = (text or "").strip()
    hits = []
    if text:
        for cat, entries in DATA["类别"].items():
            best = None  # (匹配词长度, entry, 词)
            for e in entries:
                for w in e["词"]:
                    if w and w in text:
                        if best is None or len(w) > best[0]:
                            best = (len(w), e, w)
            if best:
                _, e, w = best
                h = {"类别": cat, "词": w, "卦": e.get("卦"), "吉凶": e.get("吉凶"),
                     "提示": e.get("提示", ""), "出处": e.get("出处", "")}
                if e.get("卦") and ti:
                    h["与体"] = relation(e["卦"], ti)
                hits.append(h)
    # 汇总
    s = {"吉": 0, "凶": 0, "未定": 0}
    for h in hits:
        rel = h.get("与体") or ""
        if "吉" in rel or h.get("吉凶") == "吉":
            s["吉"] += 1
        elif "凶" in rel or "泄" in rel or h.get("吉凶") == "凶":
            s["凶"] += 1
        else:
            s["未定"] += 1
    return {"ok": True, "text": text, "体卦": ti, "hits": hits, "汇总": s,
            "说明": [
                "[原文] 外应只作候选：同一景象多义时须结合所问与现场确认。",
                "[原文] 与体卦合参：外应生体/比和/体克外应为吉，外应克体为凶，体生外应为泄。",
                "[待核] 词库依据网络转录文本整理，未逐条对影印本；类别判定为关键词匹配，可能漏配。",
            ]}


def categories():
    return list(DATA["类别"].keys())
