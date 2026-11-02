# -*- coding: utf-8 -*-
"""梅花易数起卦引擎（v0.1）。
规则依据：knowledge/03-梅花易数/起卦与断卦规则.md（出处=知命书院本卷一，未经校对）。
爻序：自下而上（初爻在前）。卦以八除、爻以六除，余0作8/6。"""
import json, os

XIANG = {"乾": [1, 1, 1], "兑": [1, 1, 0], "离": [1, 0, 1], "震": [1, 0, 0],
         "巽": [0, 1, 1], "坎": [0, 1, 0], "艮": [0, 0, 1], "坤": [0, 0, 0]}
GUA64 = {  # (上卦, 下卦) -> 卦名
    ("乾","乾"):"乾为天",("乾","兑"):"天泽履",("乾","离"):"天火同人",("乾","震"):"天雷无妄",
    ("乾","巽"):"天风姤",("乾","坎"):"天水讼",("乾","艮"):"天山遁",("乾","坤"):"天地否",
    ("兑","乾"):"泽天夬",("兑","兑"):"兑为泽",("兑","离"):"泽火革",("兑","震"):"泽雷随",
    ("兑","巽"):"泽风大过",("兑","坎"):"泽水困",("兑","艮"):"泽山咸",("兑","坤"):"泽地萃",
    ("离","乾"):"火天大有",("离","兑"):"火泽睽",("离","离"):"离为火",("离","震"):"火雷噬嗑",
    ("离","巽"):"火风鼎",("离","坎"):"火水未济",("离","艮"):"火山旅",("离","坤"):"火地晋",
    ("震","乾"):"雷天大壮",("震","兑"):"雷泽归妹",("震","离"):"雷火丰",("震","震"):"震为雷",
    ("震","巽"):"雷风恒",("震","坎"):"雷水解",("震","艮"):"雷山小过",("震","坤"):"雷地豫",
    ("巽","乾"):"风天小畜",("巽","兑"):"风泽中孚",("巽","离"):"风火家人",("巽","震"):"风雷益",
    ("巽","巽"):"巽为风",("巽","坎"):"风水涣",("巽","艮"):"风山渐",("巽","坤"):"风地观",
    ("坎","乾"):"水天需",("坎","兑"):"水泽节",("坎","离"):"水火既济",("坎","震"):"水雷屯",
    ("坎","巽"):"水风井",("坎","坎"):"坎为水",("坎","艮"):"水山蹇",("坎","坤"):"水地比",
    ("艮","乾"):"山天大畜",("艮","兑"):"山泽损",("艮","离"):"山火贲",("艮","震"):"山雷颐",
    ("艮","巽"):"山风蛊",("艮","坎"):"山水蒙",("艮","艮"):"艮为山",("艮","坤"):"山地剥",
    ("坤","乾"):"地天泰",("坤","兑"):"地泽临",("坤","离"):"地火明夷",("坤","震"):"地雷复",
    ("坤","巽"):"地风升",("坤","坎"):"地水师",("坤","艮"):"地山谦",("坤","坤"):"坤为地"}
NAME64 = {v: k for k, v in GUA64.items()}
BIT2GUA = {tuple(v): k for k, v in XIANG.items()}
LEIXIANG = json.load(open(os.path.join(os.path.dirname(__file__), "..",
    "knowledge", "03-梅花易数", "万物类象.json"), encoding="utf-8"))

def mod8(n): return ((n - 1) % 8) + 1
def mod6(n): return ((n - 1) % 6) + 1
def _pos_int(n, name):
    if not isinstance(n, int) or n <= 0:
        raise ValueError(f"{name}必须为正整数：{n!r}")
    return n
def _hour_z(h):
    if not isinstance(h, int) or not (1 <= h <= 12):
        raise ValueError(f"时支序数必须为 1–12（子1…亥12）：{h!r}")
    return h
def num_to_gua(n): return {1:"乾",2:"兑",3:"离",4:"震",5:"巽",6:"坎",7:"艮",8:"坤"}[mod8(n)]
def hexagram_bits(top, bottom): return XIANG[bottom] + XIANG[top]
def bits_name(bits6):
    top = BIT2GUA[tuple(bits6[3:])]
    bottom = BIT2GUA[tuple(bits6[:3])]
    return GUA64[(top, bottom)]
def bits3_name(b3):
    return BIT2GUA[tuple(b3)]

def _assemble(upper, lower, moving, method, note="", total=None):
    bits6 = hexagram_bits(upper, lower)
    name = GUA64[(upper, lower)]
    m = list(bits6); m[moving - 1] ^= 1
    changed = None if m == bits6 else bits_name(m)
    # 互卦：取本卦去初上爻，2/3/4 为下互，3/4/5 为上互；乾坤无互，互其变卦
    base = bits6
    if name in ("乾为天", "坤为地") and changed:
        base = hexagram_bits(*NAME64[changed])
    lo_int, hi_int = bits3_name(base[1:4]), bits3_name(base[2:5])
    mutual = {"上互": hi_int, "下互": lo_int}
    ti, yong = (upper, lower) if moving <= 3 else (lower, upper)
    return {"方法": method, "上卦": upper, "下卦": lower, "卦名": name, "动爻": moving,
            "互卦": mutual, "变卦": changed or "（无）", "体卦": ti, "用卦": yong,
            "体用生克": _shengke(ti, yong), "注": note, "总数": total}

def _shengke(ti, yong):
    WX = {"乾":"金","兑":"金","离":"火","震":"木","巽":"木","坎":"水","艮":"土","坤":"土"}
    SHENG = {"金":"水","水":"木","木":"火","火":"土","土":"金"}
    KE = {"金":"木","木":"土","土":"水","水":"火","火":"金"}
    t, y = WX[ti], WX[yong]
    if t == y: return "比和（吉）"
    if SHENG[y] == t: return "用生体（进益之喜）"
    if SHENG[t] == y: return "体生用（耗失之患）"
    if KE[y] == t: return "用克体（凶）"
    if KE[t] == y: return "体克用（吉）"
    return "?"

# ---------- 起卦法 ----------
def cast_datetime(lunar_yz, month, day, hour_z, method="年月日时起卦"):
    """lunar_yz: 年支序数(子1..亥12); month/day: 农历; hour_z: 时支序数(子1..亥12)"""
    _hour_z(hour_z)
    if not (isinstance(lunar_yz, int) and 1 <= lunar_yz <= 12):
        raise ValueError(f"年支序数必须为 1–12：{lunar_yz!r}")
    if not (isinstance(month, int) and 1 <= month <= 12):
        raise ValueError(f"农历月必须为 1–12：{month!r}")
    if not (isinstance(day, int) and 1 <= day <= 30):
        raise ValueError(f"农历日必须为 1–30：{day!r}")
    _hour_z(hour_z)
    up = num_to_gua(lunar_yz + month + day)
    lo = num_to_gua(lunar_yz + month + day + hour_z)
    mv = mod6(lunar_yz + month + day + hour_z)
    return _assemble(up, lo, mv, method, f"({lunar_yz}+{month}+{day})%8上, +{hour_z}%8下, 总%6爻", lunar_yz+month+day+hour_z)

def cast_manual(upper, lower, moving, method="手动排卦"):
    """手动指定上卦、下卦、动爻（1-6，自下而上）。用于研究、复盘与复现他人所报卦。"""
    if upper not in XIANG or lower not in XIANG:
        raise ValueError(f"卦名必须是八卦之一：{sorted(XIANG)}")
    if not isinstance(moving, int) or not (1 <= moving <= 6):
        raise ValueError(f"动爻必须为 1–6：{moving!r}")
    return _assemble(upper, lower, moving, method,
                     f"手动：{upper}上/{lower}下，动{moving}爻")

def cast_counts(count, hour_z, method="物数占"):
    _pos_int(count, "物数"); _hour_z(hour_z)
    return _assemble(num_to_gua(count), num_to_gua(hour_z), mod6(count + hour_z), method,
                     f"物数{count}%8上, 时{hour_z}%8下, 合{count+hour_z}%6爻", count+hour_z)

def cast_sound(count, hour_z, method="声音占"):
    return cast_counts(count, hour_z, method)

def cast_two_counts(c1, c2, hour_z, method="两声占（扣门借物例）"):
    """两声各起一卦：先声为上卦、后声为下卦，合两数加时取爻（原文扣门借物例）。"""
    _pos_int(c1, "先声数"); _pos_int(c2, "后声数"); _hour_z(hour_z)
    return _assemble(num_to_gua(c1), num_to_gua(c2), mod6(c1 + c2 + hour_z), method,
                     f"{c1}+{c2}+时{hour_z}={c1+c2+hour_z}%6", c1+c2+hour_z)

def cast_strokes(strokes_up, strokes_lo, method="字画占（西林寺例）"):
    """按笔画数起卦：上卦=上字画数，下卦=下字画数，合数取爻（不足则加时）。"""
    _pos_int(strokes_up, "上字笔画"); _pos_int(strokes_lo, "下字笔画")
    total = strokes_up + strokes_lo
    return _assemble(num_to_gua(strokes_up), num_to_gua(strokes_lo), mod6(total), method,
                     f"{strokes_up}画+{strokes_lo}画={total}%6", total)

def cast_tone_groups(tone_sum_up, tone_sum_lo, method="平仄声调占"):
    """按平仄声调计数：上组之和起上卦、下组之和起下卦，合数取爻（今日动静例：平1上去3入4）。"""
    _pos_int(tone_sum_up, "上组声调数"); _pos_int(tone_sum_lo, "下组声调数")
    total = tone_sum_up + tone_sum_lo
    return _assemble(num_to_gua(tone_sum_up), num_to_gua(tone_sum_lo), mod6(total), method,
                     f"{tone_sum_up}+{tone_sum_lo}={total}%6", total)

def cast_zhangchi(zhang, chi, method="丈尺占"):
    """丈数为上卦、尺数为下卦，合丈尺之数取爻；寸数不用（原文卷一·丈尺占）。"""
    _pos_int(zhang, "丈数"); _pos_int(chi, "尺数")
    total = zhang + chi
    return _assemble(num_to_gua(zhang), num_to_gua(chi), mod6(total), method,
                     f"丈{zhang}+尺{chi}={total}%6（寸不用）", total)

def cast_cunzi(chi, cun, hour_z, method="尺寸占"):
    """尺数为上卦、寸数为下卦，合尺寸之数加时取爻；分数不用（原文卷一·尺寸占）。"""
    _pos_int(chi, "尺数"); _pos_int(cun, "寸数"); _hour_z(hour_z)
    total = chi + cun + hour_z
    return _assemble(num_to_gua(chi), num_to_gua(cun), mod6(total), method,
                     f"尺{chi}+寸{cun}+时{hour_z}={total}%6（分不用）", total)

def cast_words(text, method="字占"):
    """按字数规则：2字各一，3字1+2，4字平分（平仄另接口），5字2+3，6平分，7字3+4，
    8平分，9字4+5，10平分，11+均分。一字需笔画数（未实现，抛错）。"""
    n = len([c for c in text.strip() if not c.isspace()])
    if n < 2:
        raise ValueError("一字占需左右笔画数（接口未实现），请改用 cast_strokes")
    if n == 2: up, lo = 1, 1
    elif n == 3: up, lo = 1, 2
    elif n in (4, 6, 8, 10): up, lo = n // 2, n // 2
    elif n == 5: up, lo = 2, 3
    elif n == 7: up, lo = 3, 4
    elif n == 9: up, lo = 4, 5
    else: up, lo = (n + 1) // 2, n // 2
    total = up + lo
    return _assemble(num_to_gua(up), num_to_gua(lo), mod6(total), method, f"{n}字分{up}+{lo}")

DIR_MAP = {"东":"震","南":"离","西":"兑","北":"坎","东南":"巽","西南":"坤","西北":"乾","东北":"艮"}
DIR_OF = {v: k for k, v in DIR_MAP.items()}

def cast_azimuth(direction, hour_z, method="方位占（物数占之方位变体，原文未单列）"):
    """纯方位起卦：方位卦为上卦、时数卦为下卦、合数取爻。
    说明：原文端法后天要求'物为上卦、方位为下卦'；本函数是物数占句式的方位延伸，
    供只有方向可记时使用，输出会标注为扩展用法。"""
    g = DIR_MAP.get(direction, direction)
    return _assemble(g, num_to_gua(hour_z), mod6(XIANG_ORDER[g] + hour_z), method,
                     f"方位{direction}={g}({XIANG_ORDER[g]})上, 时{hour_z}下, 合{XIANG_ORDER[g]+hour_z}%6", XIANG_ORDER[g]+hour_z)

def direction_summary(res):
    """方位推断：体=己方/主位，用=事之方，互=过程方；并给后天八方表。"""
    LX = LEIXIANG
    def fang(g):
        d = LX.get(g, {}).get("类象", {})
        return d.get("方道") or d.get("地理", "")
    rows = [("体卦（己方/主位）", res["体卦"], fang(res["体卦"])),
            ("用卦（事之方）", res["用卦"], fang(res["用卦"])),
            ("上互（过程中）", res["互卦"]["上互"], fang(res["互卦"]["上互"])),
            ("下互（过程中）", res["互卦"]["下互"], fang(res["互卦"]["下互"]))]
    if res["变卦"] and res["变卦"] != "（无）":
        name = res["变卦"]
        if name in NAME64:
            # 动爻在 1-3 爻变的是下卦，4-6 爻变的是上卦——取变化的那一卦
            idx = 1 if res["动爻"] <= 3 else 0
            g_changed = NAME64[name][idx]
            rows.append(("变卦（结局方）", g_changed, fang(g_changed)))
    table = "、".join(f"{d}→{g}" for d, g in DIR_MAP.items())
    return rows, table

def cast_direction(obj_gua, dir_gua, hour_z, method="端法后天起卦", note=""):
    """物为上卦，方位为下卦，合二卦数加时数取动爻（原文扣门/老人忧色等例）。
    dir_gua 可传卦名（离）或方位名（南/东南…）；服色/颜色归 obj_gua。"""
    if dir_gua in DIR_MAP:
        dir_gua = DIR_MAP[dir_gua]
    s = XIANG_ORDER[obj_gua] + XIANG_ORDER[dir_gua] + hour_z
    return _assemble(obj_gua, dir_gua, mod6(s), method, f"{obj_gua}({XIANG_ORDER[obj_gua]})+{dir_gua}({XIANG_ORDER[dir_gua]})+时{hour_z}={s}%6", s)

XIANG_ORDER = {k: v for k, v in [(g, i + 1) for i, g in enumerate(["乾","兑","离","震","巽","坎","艮","坤"])]}

def cast_color(color, direction, hour_z, method="颜色/服色占"):
    """按《八卦类象》'五色'字段定物象卦，方位名可为南/东南等；颜色歧义时报出候选（原文类象确有歧义）。"""
    hits = [g for g, d in LEIXIANG.items() if color in d.get("类象", {}).get("五色", "")]
    if len(hits) != 1:
        raise ValueError(f"颜色'{color}'匹配到 {hits}（原文类象确有歧义），请改用 cast_direction 指定物象卦")
    return cast_direction(hits[0], direction, hour_z, method)

# 生肖→卦：两套并行体系（见 knowledge/03-梅花易数/生肖与身体对应表.md）
ANIMAL_SHUOGUA = {"马":"乾","牛":"坤","龙":"震","蛇":"震","鸡":"巽","豕":"坎","猪":"坎","雉":"离",
                  "狗":"艮","虎":"艮","鼠":"艮","羊":"兑","兔":"震","猴":"坤"}
ANIMAL_DIZHI = {"鼠":"坎","牛":"艮","虎":"艮","兔":"震","龙":"巽","蛇":"巽","马":"离",
                "羊":"坤","猴":"坤","鸡":"兑","狗":"乾","猪":"乾"}

def animal_gua(name, system="说卦"):
    """生肖/动物→卦。system='说卦'（见物取象，原文占例依据）或 '地支'（年命属相）。"""
    name = {"猪":"猪", "豕":"猪"}.get(name, name)
    d = ANIMAL_SHUOGUA if system == "说卦" else ANIMAL_DIZHI
    if name not in d:
        raise KeyError(f"未收录动物：{name}；可用：{sorted(d)}")
    return d[name]

def body_summary(res):
    """身体部位对应：体=己身、用=所问之事涉及的身体部位、互=过程、变=结果。"""
    rows = []
    for role, g in [("体卦（己身）", res["体卦"]), ("用卦（事/人）", res["用卦"])]:
        d = LEIXIANG.get(g, {}).get("类象", {})
        rows.append((role, g, d.get("身體", "—")))
    return rows

# ---------- 笔画/拆字辅助（一字占、多字笔画占） ----------
import sys as _sys
_sys.path.insert(0, os.path.join(os.path.dirname(__file__), "common"))
import strokes_counts as _SC  # 康熙/现代双口径（Unihan 数据，简体自动繁体化）
try:
    from hanzi_chaizi import HanziChaizi as _HC
    _hc = _HC()
except Exception:
    _hc = None

def char_strokes(ch, standard="kangxi"):
    """单字笔画数。standard='kangxi'（默认，简体先繁体化）或 'modern'。
    返回 (数, 口径标注)。数据缺失返回 (None, 原因)。"""
    return _SC.total(ch, standard)

def char_left_right_strokes(ch, standard="kangxi"):
    """[推定] 左/右笔画划分：拆字库首个部件为左（或外框），其余为右（或内），
    笔画数按指定口径。原文规则本为笔画几何左右分，部件近似未必精确——标记推定。"""
    if _hc is None:
        return None
    parts = _hc.query(ch)
    if not parts:
        return None
    left, right = parts[0], "".join(parts[1:]) if len(parts) > 1 else ""
    if not right:
        return None
    ls, lt = char_strokes(left, standard)
    rs, rt = char_strokes(right, standard)
    if ls is None or rs is None:
        return None
    return {"左部件": left, "右部件": right, "左画": ls, "右画": rs,
            "口径": standard, "左标注": lt, "右标注": rt,
            "分级": "[推定]部件拆分，非原文笔画几何规则", "字": ch}

def cast_one_char(ch, left=None, right=None, total=None, method="一字占", standard="kangxi"):
    """原文（卷一·一字占）：楷书上卦=居左笔画数，下卦=居右笔画数，全画取爻。
    left/right 显式给定时为[原文]用法（standard='manual' 表示用户自己数笔画）；
    未给定时用部件推定（默认康熙口径，简体自动繁体化）。"""
    if left is None or right is None:
        if standard == "manual":
            raise ValueError("manual（人工数笔画）模式必须同时提供 left 与 right")
        est = char_left_right_strokes(ch, standard)
        if est is None:
            raise ValueError("需显式提供 left/right 笔画数（部件拆分不可靠时请人工判定）")
        left, right = est["左画"], est["右画"]
        note = f"[推定] 左部件{est['左部件']}={left}画，右{est['右部件']}={right}画（{standard}口径）"
    else:
        note = "[原文] 人工数笔画：左%d画、右%d画" % (left, right) if standard == "manual" \
            else f"[原文] 人工指定左右笔画（{standard}口径：左{left}右{right}）"
        if standard != "manual":
            # 人工给定但保留口径标注，便于核对数据表与人工结果是否一致
            ls, _ = char_strokes(ch, standard)
            if ls is not None and ls != left + right:
                note += f"；⚠️ 与{standard}总画 {ls} 不一致，已按人工数为准"
    _pos_int(left, "左画数"); _pos_int(right, "右画数")
    t = total if total is not None else left + right
    return _assemble(num_to_gua(left), num_to_gua(right), mod6(t), method, note, t)

def cast_words_strokes(stroke_list, standard="kangxi", method="多字笔画占"):
    """多字按【每字笔画数】起卦。三种输入：
    ①汉字列表（自动按口径取数）；②整数列表（视为人工数笔画）；③[(字,画),…] 人工对照。
    分卦规则同字占（2字各一、3字1+2、5字2+3…均分）。"""
    pairs = None
    if stroke_list and all(isinstance(x, tuple) and len(x) == 2 and isinstance(x[0], str) for x in stroke_list):
        pairs = stroke_list
        stroke_list = [int(c) for _, c in pairs]
        standard = "manual"
        _note = "人工数笔画：" + "、".join(f"{z}{c}" for z, c in pairs)
    else:
        chars = [s for s in stroke_list if isinstance(s, str)]
        if chars and len(chars) == len(stroke_list):
            stroke_list = [char_strokes(c, standard)[0] for c in chars]
            if any(v is None for v in stroke_list):
                raise ValueError(f"部分字无笔画数据：{chars}")
            _note = f"{standard}口径：" + "、".join(f"{z}{c}" for z, c in zip(chars, stroke_list))
        else:
            _note = "人工数笔画：" + "、".join(map(str, stroke_list))
            if standard != "manual":
                _note = f"[原文] {_note}"
    for v in stroke_list:
        _pos_int(v, "笔画数")
    n = len(stroke_list)
    if n < 2:
        raise ValueError("一字占请用 cast_one_char")
    if n == 2: up, lo = stroke_list[0], stroke_list[1]
    elif n == 3: up, lo = stroke_list[0], stroke_list[1] + stroke_list[2]
    elif n in (4, 6, 8, 10): up, lo = sum(stroke_list[:n//2]), sum(stroke_list[n//2:])
    elif n == 5: up, lo = sum(stroke_list[:2]), sum(stroke_list[2:])
    elif n == 7: up, lo = sum(stroke_list[:3]), sum(stroke_list[3:])
    elif n == 9: up, lo = sum(stroke_list[:4]), sum(stroke_list[4:])
    else:
        half = n // 2
        up, lo = sum(stroke_list[:half]), sum(stroke_list[half:])
    total = up + lo
    return _assemble(num_to_gua(up), num_to_gua(lo), mod6(total), method,
                     f"{_note}；分组 {up}+{lo}={total}", total)

def stroke_report(ch):
    """笔画查询：康熙/现代/部件拆分三方并列，供用户人工核对。"""
    k, kt = char_strokes(ch, "kangxi")
    m, mt = char_strokes(ch, "modern")
    est = char_left_right_strokes(ch, "kangxi")
    return {"字": ch, "康熙": (k, kt), "现代": (m, mt),
            "部件拆分(康熙)": est,
            "提示": "人工数笔画可用 CLI：zi 字 左画 右画（一字占）或 zistrokes 字=画 …（多字）"}

def board(res):
    """卦画结构：本卦/互卦/变卦三张盘，逐爻 1/0（自下而上），标出体卦/用卦与动爻。

    每张盘：
      名        64 卦名
      上卦/下卦 卦名（互卦为上互/下互）
      爻        长度 6 的 1/0 列表，自下而上（index0=初爻）
      动爻      本卦的动爻序数（1-6，自下而上）；互/变卦无
      体用      {上: "体/用/—", 下: ...}（互/变卦为 "—"）
      五行      {上: .., 下: ..}
      角色      主/事、过程、终局
    """
    WX = {"乾":"金","兑":"金","离":"火","震":"木","巽":"木","坎":"水","艮":"土","坤":"土"}
    bits6 = hexagram_bits(res["上卦"], res["下卦"])
    mv = res["动爻"]
    # 体用归属：动爻在 1-3 爻→上卦为体、下卦为用；4-6 爻→下卦为体、上卦为用
    ti_upper = mv <= 3
    mutual = res["互卦"]
    mu_bits = XIANG[mutual["下互"]] + XIANG[mutual["上互"]]
    mu_name = GUA64[(mutual["上互"], mutual["下互"])]
    chg_bits = list(bits6); chg_bits[mv - 1] ^= 1
    b = {
        "本卦": {"名": res["卦名"], "上卦": res["上卦"], "下卦": res["下卦"],
                 "爻": bits6, "动爻": mv,
                 "体用": {"上": "体" if ti_upper else "用", "下": "用" if ti_upper else "体"},
                 "五行": {"上": WX[res["上卦"]], "下": WX[res["下卦"]]},
                 "角色": "体卦为主（己身/求测人），用卦为事"},
        "互卦": {"名": mu_name, "上卦": mutual["上互"], "下卦": mutual["下互"],
                 "爻": mu_bits, "动爻": None,
                 "体用": {"上": "—", "下": "—"},
                 "五行": {"上": WX[mutual["上互"]], "下": WX[mutual["下互"]]},
                 "角色": "事之中间（上互随体位、下互随用位）"},
        "变卦": {"名": res["变卦"], "上卦": BIT2GUA[tuple(chg_bits[3:])],
                 "下卦": BIT2GUA[tuple(chg_bits[:3])],
                 "爻": chg_bits, "动爻": mv,
                 "体用": {"上": "—", "下": "—"},
                 "五行": {"上": WX[BIT2GUA[tuple(chg_bits[3:])]],
                          "下": WX[BIT2GUA[tuple(chg_bits[:3])]]},
                 "角色": "事之终应"},
    }
    # 变卦动爻保留原位标记（哪一爻由阴变阳/由阳变阴）
    b["变卦"]["变爻位置"] = mv
    b["互卦"]["爻来源"] = "本卦去初上爻：下互=2/3/4 爻，上互=3/4/5 爻"
    return b

def interpret(res, fields="all"):
    """从八卦类象（knowledge/03/万物类象.json）取体、用、互、变卦的类象字段。

    fields="all"（默认）输出全部 25 个字段；也可传字段简体名列表（如 ["数目","方位"]）。
    返回 {字段: [f"{卦}（角色）：原文", …]}，角色含体卦/用卦/上互/下互/变卦。"""
    LABEL = {"天時":"天时","地理":"地理","人物":"人物","人事":"人事","身體":"身体","時序":"时序",
             "動物":"动物","靜物":"静物","屋舍":"屋舍","家宅":"家宅","婚姻":"婚姻","飲食":"饮食",
             "生產":"生产","求名":"求名","謀旺":"谋旺","交易":"交易","求利":"求利","出行":"出行",
             "謁見":"谒见","疾病":"疾病","方道":"方位","五色":"五色","姓字":"姓字","數目":"数目","五味":"五味"}
    if fields == "all":
        keys = list(LABEL)
    else:
        want = {f.strip() for f in fields}
        keys = [k for k, v in LABEL.items() if v in want]
    roles = [("体卦（主）", res["体卦"]), ("用卦（事）", res["用卦"]),
             ("上互", res["互卦"]["上互"]), ("下互", res["互卦"]["下互"])]
    if res["变卦"] and res["变卦"] != "（无）" and res["变卦"] in NAME64:
        idx = 1 if res["动爻"] <= 3 else 0
        roles.append(("变卦", NAME64[res["变卦"]][idx]))
    out = {}
    for g, role in [(g, r) for r, g in roles]:
        d = LEIXIANG.get(g, {}).get("类象", {})
        for k in keys:
            if k in d:
                out.setdefault(LABEL[k], []).append(f"{g}（{role}）：{d[k]}")
    return out

def divination(res):
    """断卦一句话：体用生克 + 类象摘要（出处见万物类象.json/解卦断占总诀.json）。"""
    line = f"{res['卦名']}（{res['体卦']}为体/{res['用卦']}为用）动{res['动爻']}爻，{res['体用生克']}；互{res['互卦']['上互']}{res['互卦']['下互']}，变{res['变卦']}。"
    return line
