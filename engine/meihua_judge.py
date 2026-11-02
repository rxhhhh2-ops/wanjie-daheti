# -*- coding: utf-8 -*-
"""梅花易数解卦判断引擎（v0.2）。
原则：
  1) 任何"人/地/时/物数"结论一律以【候选】输出，附角色依据、原文出处、分级，禁止自动択一；
  2) 事类断语原文照录（解卦断占总诀.json），标明出处 URL 与 [原文] 分级；
  3) 旺衰只按《梅花易数》原文列出的卦判（春震巽旺/坤艮衰…），原文未列的卦标"不判"；
  4) 应期按原文"行取半、坐加倍、立全数"，需显式提供动静。
"""
import json, os, re

HERE = os.path.dirname(__file__)
KN = os.path.join(HERE, "..", "knowledge", "03-梅花易数")
DUAN = json.load(open(os.path.join(KN, "解卦断占总诀.json"), encoding="utf-8"))
LEI = json.load(open(os.path.join(KN, "万物类象.json"), encoding="utf-8"))

# 问题关键词 → 占事节名（顺序即优先级）
QMAP = [
    (["求财", "财运", "赚钱", "生意", "买卖盈亏", "收入", "亏"], "求財占第十"),
    (["失物", "丢", "寻物", "找东西", "找不到", "遗失"], "失物占第十五"),
    (["婚姻", "婚", "感情", "恋爱", "嫁娶", "对象"], "婚姻占第五"),
    (["疾病", "病", "健康", "身体不适", "治疗"], "疾病占第十六"),
    (["官讼", "诉讼", "官司", "打官司", "纠纷", "起诉"], "官訟占第十七"),
    (["出行", "出门", "远行", "旅行", "出差"], "出行占第十二"),
    (["行人", "寻人", "找人", "何时回", "归期", "回家"], "行人占第十三"),
    (["求名", "考试", "功名", "升迁", "求职", "面试"], "求名占第九"),
    (["求谋", "谋事", "办事", "合作", "计划", "可行"], "求謀占第八"),
    (["生产", "分娩", "怀孕", "生育", "生男", "生女"], "生產占第六"),
    (["家宅", "住宅", "搬家", "房屋", "风水", "房子"], "家宅占第三"),
    (["屋舍", "店铺", "厂房", "店面"], "屋舍占第四"),
    (["饮食", "请客", "宴席", "吃", "饭局"], "飲食占第七"),
    (["交易", "签约", "合同", "成交", "买卖"], "交易占第十一"),
    (["谒见", "拜访", "见贵人", "求见", "探望", "领导", "长辈"], "謁見占第十四"),
    (["天时", "天气", "下雨", "晴"], "天時占第一"),
    (["坟墓", "墓地", "安葬"], "墳墓占第十八"),
    (["人事", "动静", "今天如何"], "人事占第二"),
]

# 卦气旺衰（原文·卷一：震巽木旺于春…坤艮土旺于辰戌丑未月；衰者反列）
WANG = {"春": {"震", "巽"}, "夏": {"离"}, "秋": {"乾", "兑"}, "冬": {"坎"}, "四季": {"坤", "艮"}}
SHUAI = {"春": {"坤", "艮"}, "夏": {"乾", "兑"}, "秋": {"震", "巽"}, "冬": {"离"}, "四季": {"坎"}}

def season_of_month(m):
    """农历月→季（辰戌丑未归四季月，仅用于土）；用于卦气旺衰。"""
    if not (1 <= m <= 12):
        raise ValueError(f"月必须 1–12：{m}")
    if m in (3, 6, 9, 12):
        return "四季"
    return {1: "冬", 2: "春", 4: "春", 5: "夏", 7: "夏", 8: "秋", 10: "秋", 11: "冬"}[m]

def match_topic(question):
    for keys, title in QMAP:
        if any(k in question for k in keys):
            return title
    return None

def gua_state(g, season):
    """返回 (状态, 说明, 分级)。原文只列特定卦：春震巽旺/坤艮衰，秋震巽衰…"""
    if g in WANG[season]:
        return "旺", f"《梅花易数·卦气旺》：{season}月{g}旺", "[原文]"
    if g in SHUAI[season]:
        return "衰", f"《梅花易数·卦气衰》：{season}月{g}衰", "[原文]"
    return "不判", f"原文只列 {season} 月旺衰的特定卦，{g}未列，不作强弱判断", "[原文]"

# 类象全部 25 字段（原文卷一八卦万物属类详表；繁体键→简体标签）
CAND_FIELDS = ["天時", "地理", "人物", "人事", "身體", "時序", "動物", "靜物", "屋舍", "家宅",
               "婚姻", "飲食", "生產", "求名", "謀旺", "交易", "求利", "出行", "謁見", "疾病",
               "方道", "五色", "姓字", "數目", "五味"]
FIELD_LABEL = {"天時": "天时", "地理": "地理", "人物": "人物", "人事": "人事", "身體": "身体",
               "時序": "时序", "動物": "动物", "靜物": "静物", "屋舍": "屋舍", "家宅": "家宅",
               "婚姻": "婚姻", "飲食": "饮食", "生產": "生产", "求名": "求名", "謀旺": "谋旺",
               "交易": "交易", "求利": "求利", "出行": "出行", "謁見": "谒见", "疾病": "疾病",
               "方道": "方位", "五色": "五色", "姓字": "姓字", "數目": "数目", "五味": "五味"}

def _candidates(res):
    """四层角色 × 类象字段 → 候选列表（不択一）。"""
    rows = []
    roles = [("体卦（求测人/主）", res["体卦"]), ("用卦（所测事）", res["用卦"]),
             ("上互（过程）", res["互卦"]["上互"]), ("下互（过程）", res["互卦"]["下互"])]
    if res["变卦"] not in (None, "（无）") and res["变卦"] in __import__("meihua_engine").NAME64:
        import meihua_engine as ME
        idx = 1 if res["动爻"] <= 3 else 0
        roles.append(("变卦所变之卦（结局）", ME.NAME64[res["变卦"]][idx]))
    for role, g in roles:
        d = LEI.get(g, {}).get("类象", {})
        for f in CAND_FIELDS:
            if f in d:
                rows.append({"角色": role, "卦": g, "类别": FIELD_LABEL.get(f, f), "象": d[f],
                             "出处": f"万物类象.json（{g}·{FIELD_LABEL.get(f, f)}）", "分级": "[原文]",
                             "状态": "候选：须结合所问事类与现场确认，勿直接断定"})
    return rows

def judge(res, question, month=None, season=None, motion=None):
    """返回结构化判断。motion: '行'|'坐'|'立'（应期用，原文要求自察动静）。"""
    topic = match_topic(question)
    out = {"问题": question, "匹配占事": topic or "（未匹配到十八占事，只给基础结构）",
           "起局": {"方法": res["方法"], "算式": res["注"], "总数": res["总数"]},
           "基础结构": {"卦": res["卦名"], "动爻": res["动爻"], "体": res["体卦"], "用": res["用卦"],
                     "互": f'{res["互卦"]["上互"]}/{res["互卦"]["下互"]}', "变": res["变卦"],
                     "体用生克": res["体用生克"], "分级": "[原文]（体用总诀）"},
           "旺衰": None, "事类断语": None, "取象候选": _candidates(res),
           "应期": None, "分歧与限制": []}
    if season is None and month is not None:
        season = season_of_month(month)
    if season:
        st, why, lv = gua_state(res["体卦"], season)
        out["旺衰"] = {"季节": season, "体卦": res["体卦"], "状态": st, "说明": why, "分级": lv}
    out["倾向"] = tendency(res, season=season)
    if topic and topic in DUAN:
        sec = DUAN[topic]
        out["事类断语"] = {"标题": topic, "原文": sec["text"], "出处": sec["url"],
                        "来源文件": sec["file"], "分级": "[原文]"}
    if motion and res.get("总数"):
        n = res["总数"]
        if motion == "行":
            val, why = n // 2, f"成卦之数 {n} 中分取半（行则应速）"
        elif motion == "坐":
            val, why = n * 2, f"成卦之数 {n} 倍之（坐则应迟）"
        elif motion == "立":
            val, why = n, f"成卦之数 {n} 全数（立则半迟半速）"
        else:
            val, why = None, f"未知动静：{motion}"
        if val:
            out["应期"] = {"动静": motion, "应期数": val, "单位": "日（原文例皆以日计）",
                         "说明": why + "（《梅花易数·老人有忧色占》'行则取半，坐则倍之，立即全数'）",
                         "分级": "[原文]"}
    out["分歧与限制"] = [
        "[待核] 断语文本为网络转录，未经影印本逐字校对；引用时保留原文并自行复核。",
        "[原文] 类象词条多为多义（如兑=少女/泽/口/毁折），本工具只列候选，不替你选定。",
        "[扩展] 问题→占事的匹配是关键词映射，非古籍分类；未匹配时只给基础结构。",
    ]
    if res.get("方法", "").startswith("方位占"):
        out["分歧与限制"].append("[扩展] 纯方位起卦原文未单列（端法要求物为上卦），属工具扩展。")
    return out

YAOCI = json.load(open(os.path.join(HERE, "data", "yijing_yaoci.json"), encoding="utf-8"))

JIXIANG_WORDS = ["元亨", "亨", "吉", "利", "元吉", "大吉"]
XIONG_WORDS = ["凶", "悔", "吝", "咎", "厉", "灾"]

def yao_title(gua_name, moving, bits6):
    """动爻→爻题（初九/六二…）。bits6 为本卦六爻[初..上]，1=阳。"""
    pos_names = ["初", "二", "三", "四", "五", "上"]
    yin_yang = "九" if bits6[moving - 1] == 1 else "六"
    if moving in (1, 6):
        return pos_names[moving - 1] + yin_yang
    return yin_yang + pos_names[moving - 1]

def yaoci_signal(res):
    """断卦第一步（占卜总决）：先看周易爻辞，以断吉凶。返回信号 dict。"""
    import meihua_engine as ME
    bits6 = ME.hexagram_bits(res["上卦"], res["下卦"])
    title = yao_title(res["卦名"], res["动爻"], bits6)
    book = YAOCI.get(res["卦名"], {})
    ci = book.get("爻辞", {}).get(title)
    gua_ci = book.get("卦辞")
    good = [w for w in JIXIANG_WORDS if ci and w in ci]
    bad = [w for w in XIONG_WORDS if ci and w in ci]
    return {"爻题": title, "爻辞": ci, "卦辞": gua_ci,
            "小象": book.get("小象", {}).get(title),
            "大象": book.get("大象"), "彖": book.get("彖"),
            "吉词": good, "凶词": bad,
            "出处": book.get("来源"), "分级": "[原文]（劝学网周易白文）"}

def tendency(res, season=None):
    """倾向结论：按《占卜总决》"俱吉则大吉；俱凶则大凶；有凶有吉则详审"。
    信号源：①爻辞吉凶词 ②体用生克 ③体卦旺衰（原文所列卦才参与）④互变与体的生克（他卦者谓用互变）。"""
    import meihua_engine as ME
    WX = ME_WX = {"乾":"金","兑":"金","离":"火","震":"木","巽":"木","坎":"水","艮":"土","坤":"土"}
    SHENG = {"金":"水","水":"木","木":"火","火":"土","土":"金"}
    support, oppose, neutral = [], [], []
    y = yaoci_signal(res)
    if y["爻辞"]:
        if y["吉词"] and not y["凶词"]:
            support.append(f"爻辞[{y['爻题']}「{y['爻辞']}」]含吉词：{'、'.join(y['吉词'])}")
        elif y["凶词"] and not y["吉词"]:
            oppose.append(f"爻辞[{y['爻题']}「{y['爻辞']}」]含凶词：{'、'.join(y['凶词'])}")
        elif y["吉词"] and y["凶词"]:
            neutral.append(f"爻辞吉凶词并存（{('、'.join(y['吉词']))} / {('、'.join(y['凶词']))}），依总诀须详审")
        else:
            neutral.append(f"爻辞[{y['爻题']}]无明确吉凶词")
    else:
        neutral.append(f"爻辞[{y['爻题']}]未获取（{res['卦名']}）")
    sk = res["体用生克"]
    if "吉" in sk:
        support.append(f"体用生克：{sk}")
    elif "凶" in sk or "耗失" in sk:
        oppose.append(f"体用生克：{sk}")
    else:
        neutral.append(f"体用生克：{sk}")
    if season:
        st, why, lv = gua_state(res["体卦"], season)
        if st == "旺":
            support.append(f"体卦旺（体盛则吉）：{why}")
        elif st == "衰":
            oppose.append(f"体卦衰（体衰则凶）：{why}")
        else:
            neutral.append(why)
    KE = {"金":"木","木":"土","土":"水","水":"火","火":"金"}
    ti_wx = WX[res["体卦"]]
    for role, g in [("上互", res["互卦"]["上互"]), ("下互", res["互卦"]["下互"])]:
        g_wx = WX[g]
        if SHENG[g_wx] == ti_wx:
            support.append(f"{role}{g}生体")
        elif KE[g_wx] == ti_wx:
            oppose.append(f"{role}{g}克体")
    if res["变卦"] and res["变卦"] != "（无）" and res["变卦"] in ME.NAME64:
        idx = 1 if res["动爻"] <= 3 else 0
        g_ch = ME.NAME64[res["变卦"]][idx]
        g_wx = WX[g_ch]
        if SHENG[g_wx] == ti_wx:
            support.append(f"变卦{g_ch}生体")
        elif KE[g_wx] == ti_wx:
            oppose.append(f"变卦{g_ch}克体")
    # 结论（总决逻辑）
    if support and not oppose:
        concl = "吉（诸依据一致）"
    elif oppose and not support:
        concl = "凶（诸依据一致）"
    elif support and oppose:
        # 用凶变吉者，先凶后吉；用吉变凶者，先吉后凶（原文体用总诀）
        has_var_support = any("变卦" in s and "生体" in s for s in support)
        has_var_oppose = any("变卦" in s and "克体" in s for s in oppose)
        if "凶" in sk and has_var_support:
            concl = "先凶后吉（用凶而变生体，原文：用凶变吉者，先凶后吉）"
        elif "吉" in sk and has_var_oppose:
            concl = "先吉后凶（用吉而变克体，原文：用吉变凶者，先吉后凶）"
        else:
            concl = "分歧：吉凶依据并存，依总决须详审卦辞与克应"
    else:
        concl = "依据不足：诸信号皆中性，依总决须详审"
    return {"倾向": concl, "支持": support, "反对": oppose, "未参与/中性": neutral,
            "爻辞信号": y, "裁定次序": "占卜总决：爻辞→体用→克应→动静；他卦者谓用互变",
            "分级": "[原文]框架＋[原文]数据"}

def render(out):
    L = []
    L.append(f"问题：{out['问题']} → 占事：{out['匹配占事']}")
    b = out["基础结构"]
    L.append(f"基础：{b['卦']}（{b['体']}体/{b['用']}用）动{b['动爻']}爻，{b['体用生克']}；互{b['互']}，变{b['变']}  {b['分级']}")
    L.append(f"起局：{out['起局']['方法']}｜{out['起局']['算式']}｜成卦总数 {out['起局']['总数']}")
    if out.get("倾向"):
        t = out["倾向"]
        y = t["爻辞信号"]
        if y.get("爻辞"):
            L.append(f"爻辞[{y['爻题']}]：{y['爻辞']}（{y['分级']}）")
            if y.get("小象"):
                L.append(f"小象：{y['小象']}")
        L.append(f"倾向：{t['倾向']}　[次序：{t['裁定次序']}]")
        for s in t["支持"]:
            L.append(f"  支持· {s}")
        for s in t["反对"]:
            L.append(f"  反对· {s}")
        for s in t["未参与/中性"]:
            L.append(f"  中性· {s}")
    if out["旺衰"]:
        w = out["旺衰"]
        season_label = "四季月（辰戌丑未）" if w["季节"] == "四季" else f"{w['季节']}季"
        L.append(f"旺衰：{season_label} {w['体卦']} → {w['状态']}（{w['说明']}）{w['分级']}")
    if out["应期"]:
        y = out["应期"]
        L.append(f"应期：{y['说明']} → {y['应期数']} {y['单位']} {y['分级']}")
    if out["事类断语"]:
        s = out["事类断语"]
        L.append(f"\n【{s['标题']}·原文】{s['分级']}\n{s['原文'][:600]}{'……' if len(s['原文'])>600 else ''}\n出处：{s['出处']}")
    L.append("\n【取象候选】（须结合问题确认，勿直接断定）")
    seen = set()
    for c in out["取象候选"]:
        key = (c["角色"], c["类别"])
        if key in seen: continue
        seen.add(key)
        L.append(f"  {c['角色']} {c['卦']}·{c['类别']}：{c['象']}")
    L.append("\n【分歧与限制】")
    for x in out["分歧与限制"]:
        L.append("  - " + x)
    return "\n".join(L)
