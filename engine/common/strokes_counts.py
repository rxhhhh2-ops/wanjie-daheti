# -*- coding: utf-8 -*-
"""笔画数双口径：kangxi（默认，繁体化后按 kRSUnicode）与 modern（kTotalStrokes/GDI）。
数据：Unicode Unihan（tools/data/），部首笔画表见 build_kangxi.py。
约定：
  - kangxi：有 kTraditionalVariant 先转繁体再算（简→問、简→簡）；无繁体则用本字形 kRSUnicode；
    部首带撇号（169'=门 等，简体部首）退回 kTotalStrokes 并标注[简形]。
  - modern：kTotalStrokes 第一值；缺失退 GDI。
"""
import os, re

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(_HERE, "..", "data")
_cache = {}

def _load():
    if _cache:
        return _cache
    rs, tot, trad = {}, {}, {}
    p = os.path.join(DATA, "Unihan_IRGSources.txt")
    for line in open(p, encoding="utf-8"):
        m = re.match(r"U\+([0-9A-F]+)\tkRSUnicode\t([^\t\n]+)", line)
        if m:
            rs[m.group(1)] = m.group(2).split()
            continue
        m = re.match(r"U\+([0-9A-F]+)\tkTotalStrokes\t([^\t\n]+)", line)
        if m:
            tot[m.group(1)] = m.group(2).split()
    for line in open(os.path.join(DATA, "Unihan_Variants.txt"), encoding="utf-8"):
        m = re.match(r"U\+([0-9A-F]+)\tkTraditionalVariant\t([^\t\n]+)", line)
        if m:
            trad[m.group(1)] = m.group(2).split()
    _cache.update(rs=rs, tot=tot, trad=trad)
    return _cache

def _kRS(cp):
    vals = _load()["rs"].get(cp)
    if not vals:
        return None
    first = vals[0]
    m = re.match(r"(\d+)'?\.(\d+)$", first)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), "'" in first

def kangxi_total(ch):
    """返回 (总数, 标注) 或 (None, 原因)。"""
    cp = f"{ord(ch):04X}"
    load = _load()
    trads = load["trad"].get(cp)
    cp_eff = trads[0][2:] if trads else cp  # 简→繁
    converted = trads is not None
    kr = _kRS(cp_eff)
    if kr:
        rad, rem, apostrophe = kr
        if apostrophe:
            t = load["tot"].get(cp)
            if t:
                return int(t[0]), "[简形]kTotalStrokes"
            return None, "部首为简体撇号且无总数"
        if 1 <= rad <= 214:
            return load["_rad_strokes"][rad] + rem, ("[繁体化]" + (trads[0][2:][0] if trads else "") if converted else "")
        return None, f"部首序号越界 {rad}"
    t = load["tot"].get(cp)
    if t:
        return int(t[0]), "[kTotalStrokes]"
    return None, "无 kRSUnicode/kTotalStrokes"

# 部首序号→笔画（与 build_kangxi.py 同表）
def _rad_strokes_table():
    GROUPS = ["一丨丶丿乙亅",
              "二亠人儿入八冂冖冫几凵刀力勹匕匚匸十卜卩厂厶又",
              "口囗土士夂夊夕大女子宀寸小尢尸屮山巛工己巾干幺广廴廾弋弓彐彡彳",
              "心戈戶手支攴文斗斤方无日曰月木欠止歹殳毋比毛氏气水火爪父爻爿片牙牛犬",
              "玄玉瓜瓦甘生用田疋疒癶白皮皿目矛矢石示禸禾穴立",
              "竹米糸缶网羊羽老而耒耳聿肉臣自至臼舌舛舟艮色艸虍虫血行衣襾",
              "見角言谷豆豕豸貝赤走足身車辛辰辵邑酉釆里",
              "金長門阜隶隹雨靑非",
              "面革韋韭音頁風飛食首香",
              "馬骨高髟鬥鬯鬲鬼",
              "魚鳥鹵鹿麥麻",
              "黃黍黑黹",
              "黽鼎鼓鼠",
              "鼻齊",
              "齒",
              "龍龜",
              "龠"]
    table = {}
    out = {}
    for s, grp in enumerate(GROUPS, 1):
        for _ in grp:
            out[len(out) + 1] = s
    return out

def init_radix():
    if "_rad_strokes" not in _load():
        _load()["_rad_strokes"] = _rad_strokes_table()

def modern_total(ch):
    cp = f"{ord(ch):04X}"
    t = _load()["tot"].get(cp)
    if t:
        return int(t[0]), "[kTotalStrokes]"
    try:
        import strokes as _s
        r = _s.strokes(ch)
        return (r if isinstance(r, int) else len(r)), "[GDI]"
    except Exception:
        return None, "无数据"

def total(ch, standard="kangxi"):
    init_radix()
    if standard == "kangxi":
        return kangxi_total(ch)
    if standard == "modern":
        return modern_total(ch)
    raise ValueError(f"未知口径 {standard}")
