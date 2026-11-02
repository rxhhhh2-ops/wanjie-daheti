# -*- coding: utf-8 -*-
"""AI 解盘：命盘资料包（context）与对话消息组装；不做网络调用。

设计原则：
- 只把引擎已产出的“事实层＋规则层”交给模型，模型不得改动四柱/藏干/星运/神煞。
- 资料包按段组织（命主/四柱/格局/逐柱/大运/流年/六亲/神煞），每段带规则号。
- 人设由用户自定义；硬性写作要求固定附在人设之后，避免模型编造或宿命恐吓。
- 网络请求在 paipan/server.py 的 POST /api/ai 中完成，本模块可独立单测。
"""
from __future__ import annotations

import re

POS = ("年", "月", "日", "时")

DEFAULT_PERSONA = (
    "你是一位严谨的传统子平命理师，熟悉《三命通会》《渊海子平》《千里命稿》。"
    "你的任务是依据排盘引擎给出的资料解盘：先讲结构（格局、用神、身强弱），"
    "再逐柱讲盘面，再讲大运流年与六亲神煞，最后给可执行的生活建议。"
    "语气平和、具体、可核对；不故弄玄虚，不夸大吉凶。"
)

RULES = """写作要求（硬性）：
1. 只依据下面的命盘资料与规则号推断，不得改动四柱、藏干、星运、神煞等事实。
2. 每个判断尽量附规则号（如 SS-019、ZP-025、YS-004）；没有规则支撑的取象须标“取象/推测”。
3. 遇到流派分歧（羊刃、藏干、天德、六亲、调候与格局先后等）要并列说明，不擅自裁断。
4. 不作宿命恐吓；健康、法律、投资只作传统命理的象义提示，并建议当事人寻求专业意见。
5. 先给结论，再给依据；按“格局与用神 → 逐柱盘面 → 大运流年 → 六亲神煞 → 建议”分段。
6. 资料不足时直说不足，不要补写不存在的规则或冒充古籍原文。
7. 作答从简：直接给结论与关键依据，正文控制在 1200 字以内；不要复述资料全文、不要展开演算过程。
   （若为推理模型：请从简思考、尽快进入作答，避免长时间内部推理。）
8. 默认不输出应期：不得给出具体年份、月份、日期、期限、快慢、早晚，也不得把大运/流年写成“某年必应”。
   仅当用户本轮问题明确要求应期（含“应期/何时/多久/几时/哪年/哪月/哪日/日期/今年/明年/此期”等）时，
   才可依据资料包中的“应期”段说明，并逐条标明出处与不确定性；资料包没有对应规则时直说“无可靠应期规则”。"""


def _l(v) -> str:
    if not v:
        return ""
    if isinstance(v, (list, tuple)):
        return "、".join(str(x) for x in v if x)
    return str(v)


def _sh_by_col(chart: dict) -> dict[str, list[str]]:
    per = {p: [] for p in POS}
    for name, ent in ((chart.get("神煞") or {}).get("按神煞") or {}).items():
        if not ent.get("命中"):
            continue
        for col in ent.get("命中柱位") or []:
            key = str(col)[:1]
            if key in per:
                per[key].append(name)
    return per


def build_context(chart: dict) -> str:
    """把引擎 JSON 压成给模型看的资料包（约 5–12k 字）。"""
    out: list[str] = []
    info = chart.get("显示") or {}
    inp = chart.get("输入") or {}
    gender = chart.get("性别") or inp.get("性别") or "未填"
    out.append("【命主】")
    out.append(f"公历：{inp.get('datetime', '')}｜性别：{gender}｜农历：{info.get('农历', '')}｜"
               f"生肖：{info.get('生肖', '')}｜节气：{info.get('节气', '')}")
    extra = []
    mg = (chart.get("命宫") or {}).get("命宫")
    if mg:
        extra.append(f"命宫 {mg}")
    for k in ("胎元", "身宫"):
        if info.get(k):
            extra.append(f"{k} {info[k]}")
    kw = (chart.get("空亡") or {}).get("空亡")
    if kw:
        extra.append(f"旬空 {''.join(kw)}")
    if extra:
        out.append("；".join(extra))

    # 四柱
    qz = chart.get("四柱") or {}
    ss = (chart.get("十神") or {}).get("天干") or {}
    hid = chart.get("藏干") or {}
    hid_gods = (chart.get("十神") or {}).get("藏干") or {}
    star = chart.get("星运") or {}
    nayin = info.get("纳音") or []
    per = _sh_by_col(chart)
    out.append("【四柱】")
    for i, p in enumerate(POS):
        gz = qz.get(p)
        if not gz:
            continue
        hg = []
        for lvl, label in (("本", "本"), ("中", "中"), ("余", "余")):
            for ch in hid.get(p, {}).get(lvl, "") or []:
                g = (hid_gods.get(p) or {}).get(ch, "")
                hg.append(f"{ch}({label}{g})" if g else f"{ch}({label})")
        line = (f"- {p}柱 {gz}：天干{ss.get(p) or ('日主' if p == '日' else '')}；"
                f"藏干{_l(hg) or '—'}；"
                f"星运{star.get(p, '—')}；纳音{nayin[i] if i < len(nayin) else '—'}；"
                f"神煞{_l(per[p]) or '无'}")
        out.append(line)

    wx = chart.get("五行统计")
    if wx:
        lack = "、".join(wx.get("缺") or []) or "无"
        out.append(f"【五行】金{wx.get('金', 0)} 木{wx.get('木', 0)} 水{wx.get('水', 0)} "
                   f"火{wx.get('火', 0)} 土{wx.get('土', 0)}；缺：{lack}")

    # 格局与用神
    g = chart.get("格局") or {}
    st = g.get("日主强弱") or {}
    y = g.get("用神") or {}
    ds = y.get("定神") or {}
    out.append("【格局与用神】")
    if st.get("判定"):
        sig = st.get("信号") or {}
        out.append(f"日主强弱：{st['判定']}（当令{'是' if sig.get('当令') else '否'}；"
                   f"天干帮扶{sig.get('天干帮扶', '—')}、支帮扶{sig.get('支帮扶', '—')}；"
                   f"克泄{sig.get('克泄（官杀食伤）', '—')}；支得气{'是' if sig.get('支得气') else '否'}）")
    if ds.get("神"):
        out.append(f"用神：{ds['神']}（{ds.get('主法', '')}；置信{ds.get('置信', '')}；"
                   f"备选{_l(ds.get('备选')) or '无'}）")
    xs = (y.get("行运喜忌") or {}).get("文本")
    if xs:
        out.append(f"行运喜忌：{xs}")
    for e in (g.get("格局判定") or [])[:8]:
        line = f"- {e.get('格', '')}（{e.get('类别', '')}·{e.get('倾向', '')}）"
        if e.get("缺失条件"):
            line += "；缺：" + "、".join(e["缺失条件"])
        bad = [b.get("因素") for b in (e.get("破格因素") or []) if b.get("命中")]
        if bad:
            line += "；破格因素：" + "、".join(str(x) for x in bad)
        out.append(line)
    lvl = g.get("格局层次") or {}
    if lvl.get("断"):
        out.append(f"格局层次：{lvl['断']}")

    # 逐柱详解
    pm = (chart.get("分析") or {}).get("盘面详解") or {}
    if pm.get("逐柱"):
        out.append("【逐柱详解】")
        for c in pm["逐柱"]:
            pal = c.get("宫位") or {}
            gan = c.get("天干") or {}
            m = gan.get("含义") or {}
            line = (f"- {c.get('柱')}柱 {c.get('干支')}"
                    f"（{_l(pal.get('六亲'))}｜{pal.get('物', '')}｜{pal.get('断', '')}）："
                    f"天干{gan.get('十神', '')}")
            if m.get("规则"):
                line += f"（{m['规则']}）"
            if m.get("关系"):
                line += f"（{m['关系']}）"
            if m.get("正面"):
                line += "；正面：" + "；".join(m["正面"][:2])
            if m.get("负面"):
                line += "；负面：" + "；".join(m["负面"][:2])
            z = c.get("地支") or {}
            line += (f"；地支{z.get('字', '')}{z.get('五行', '')}，"
                     f"星运{z.get('星运', '')}（{z.get('星运等第', '')}）")
            if c.get("藏干"):
                line += "；藏干：" + "、".join(
                    f"{h.get('字')}{h.get('层')}{h.get('十神')}" for h in c["藏干"])
            if c.get("关系"):
                line += "；关系：" + "、".join(
                    f"{r.get('类型')}{r.get('支')}" for r in c["关系"])
            if c.get("神煞"):
                line += "；神煞：" + "、".join(s.get("名", "") for s in c["神煞"])
            for d in (c.get("神煞断语") or [])[:2]:
                line += f"；{d.get('神煞')}：{d.get('断')}"
            out.append(line)
        if pm.get("位置初义"):
            out.append("十神位置初义：" + "；".join(pm["位置初义"]))
        if pm.get("空亡"):
            out.append("空亡：" + str(pm["空亡"].get("断", "")))
        if pm.get("十神分布"):
            out.append("十神分布：" + "；".join(
                f"{d.get('神')}{d.get('数')}" for d in pm["十神分布"]))

    # 大运
    dy = chart.get("大运") or {}
    rows = dy.get("大运（前八步）") or []
    if rows:
        qy = dy.get("起运")
        qy = qy.get("文本") if isinstance(qy, dict) else qy
        out.append(f"【大运】{dy.get('方向', '')}；起运 {qy or '—'}")
        for r in rows:
            xf = r.get("用神喜忌") or {}
            hits = "；".join(f"{h.get('位置')}{h.get('十神')}{h.get('判')}"
                            for h in (xf.get("命中") or [])) or "无"
            out.append(f"- {r.get('起始岁（约）')}岁起 {r.get('干支')} "
                       f"{r.get('十神（干）')}/{r.get('十神（支本气）')} "
                       f"{r.get('十二宫')}（{r.get('十二宫取象', '')}）；用神喜忌：{hits}")
    else:
        out.append("【大运】未生成（未填性别时引擎不出大运；可补性别后重排）")

    # 流年
    ln = chart.get("流年") or {}
    if ln.get("流年"):
        cur = ln["流年"]
        out.append(f"【流年】{cur.get('年')} {cur.get('干支')}"
                   f"（{cur.get('十神（干）')}/{cur.get('十神（支本气）')}）")
        for r in (ln.get("关系") or [])[:20]:
            out.append(f"- {r.get('规则')}：{r.get('结论')}")

    # 六亲
    lq = ((chart.get("分析") or {}).get("六亲") or {}).get("六亲") or {}
    if lq:
        out.append("【六亲】")
        skip = {"夫"} if gender == "男" else ({"妻", "妾"} if gender == "女" else set())
        for name, v in lq.items():
            if name in skip:
                continue
            out.append(f"- {name}（{_l(v.get('星'))}）：{v.get('主断') or v.get('断', '')}")

    # 神煞断语
    dyu = (chart.get("分析") or {}).get("神煞断语") or []
    if dyu:
        out.append("【神煞断语】")
        for d in dyu:
            out.append(f"- {d.get('神煞')}（{d.get('依据')}）：{d.get('断')}")

    # 引擎总论（各段已带规则号）
    rep = (chart.get("分析") or {}).get("报告") or []
    if rep:
        out.append("【引擎总论】")
        for sec in rep:
            txt = " ".join(str(s.get("t", "")) for s in (sec.get("句子") or []))
            if txt:
                out.append(f"- {sec.get('标题', '')}：{txt}")

    return "\n".join(out)


def _yingqi_text(chart: dict) -> str:
    """把应期结构压成给模型看的短段；只用于用户明确要求应期时。"""
    y = chart.get("应期")
    if not isinstance(y, dict) or y.get("error"):
        return ""
    out = ["【应期（仅供用户明确要求时使用）】"]
    for sec in y.get("sections") or []:
        out.append(f"- {sec.get('title', '')}")
        for it in sec.get("items") or []:
            out.append(f"  · {it.get('text', '')}"
                       + (f"［{it.get('src')}｜{it.get('level')}］" if it.get("src") else ""))
    for c in y.get("candidates") or []:
        when = c.get("date") or c.get("window") or (
            f"{c.get('year')}年" if c.get("year") is not None else "")
        out.append(f"- 候选：{when}（{c.get('gz', '')}）{c.get('basis', '')}"
                   + (f"［{c.get('src')}｜{c.get('level')}］" if c.get("src") else ""))
    for n in y.get("notes") or []:
        out.append(f"- 说明：{n}")
    for g in y.get("gaps") or []:
        out.append(f"- 资料缺口：{g}")
    return "\n".join(out)


def build_messages(chart: dict, persona: str | None, question: str | None,
                   history: list[dict] | None = None,
                   allow_yingqi: bool = False) -> list[dict]:
    """system（人设＋硬性要求）→ user（资料包）→ 历史问答 → user（本次问题）。

    allow_yingqi 默认 False：不把应期段交给模型，并在 system 中明确禁止输出应期。
    只有用户本轮问题明确要求应期时才置 True。
    """
    system = (persona or DEFAULT_PERSONA).strip() + "\n\n" + RULES
    if allow_yingqi:
        system += ("\n\n【应期】用户本轮已明确要求应期。只能依据资料包末尾的“应期”段作答，"
                   "逐条标出处与不确定性；没有对应规则就明说“无可靠应期规则”，不得补造。")
    else:
        system += ("\n\n【应期禁令】本轮用户未明确要求应期：正文不得出现具体年份、月份、日期、"
                   "期限、快慢或“某年必应”式判断；大运/流年只作结构说明。")
    ctx = build_context(chart)
    if allow_yingqi:
        extra = _yingqi_text(chart)
        if extra:
            ctx += "\n\n" + extra
    msgs = [{"role": "system", "content": system},
            {"role": "user", "content": "以下是排盘引擎的输出（事实层＋规则层），请据此解盘：\n\n"
                                        + ctx}]
    for h in (history or [])[-6:]:
        role = h.get("role")
        text = (h.get("content") or "").strip()
        if role in ("user", "assistant") and text:
            msgs.append({"role": role, "content": text[:4000]})
    msgs.append({"role": "user",
                 "content": (question or "请给出整体解读。").strip()})
    return msgs


def normalize_config(raw: dict | None) -> dict:
    """校验并补全 OpenAI 兼容配置；错误直接 ValueError，由服务端转 400。"""
    raw = raw or {}
    base = str(raw.get("base_url") or "https://api.openai.com/v1").strip().rstrip("/")
    if not re.match(r"^https?://", base):
        raise ValueError("API 地址须以 http:// 或 https:// 开头")
    model = str(raw.get("model") or "").strip()
    if not model:
        raise ValueError("未填写模型名")
    try:
        temp = float(raw.get("temperature", 0.6))
    except (TypeError, ValueError):
        raise ValueError("温度须为数字") from None
    if not 0 <= temp <= 2:
        raise ValueError("温度须在 0–2 之间")
    try:
        max_tokens = int(raw.get("max_tokens", 1600))
    except (TypeError, ValueError):
        raise ValueError("最大 tokens 须为整数") from None
    if not 64 <= max_tokens <= 32768:
        raise ValueError("最大 tokens 须在 64–32768 之间")
    key = str(raw.get("api_key") or "").strip()
    url = base if base.endswith("/chat/completions") else base + "/chat/completions"
    return {"base_url": base, "url": url, "model": model,
            "temperature": temp, "max_tokens": max_tokens, "api_key": key}
