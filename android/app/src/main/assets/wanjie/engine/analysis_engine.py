# -*- coding: utf-8 -*-
"""分析引擎：六亲星落位、神煞断语、综合分析报告。

依据（均为 rules/ 已有规则，此前未接入引擎）：
- 六亲取用：J7-060（三命）、ZP-016（渊海）、千里更定（ZP-027 三说配置）
- 宫位：J7-061 / SS-019
- 落位吉凶：J7-062（坐长生旺库禄马贵人 → 富贵；空刑克煞死绝 → 贫薄；混合 → 有寿而贫贱）
- 妻星取法：J7-064
- 神煞断语：SSH-080 元辰／081 灾煞／082 六厄／083 勾绞／084 孤寡／085 天罗地网／086 总原则
- 报告组装：各层已有输出 + YS-007 十二宫断 + YS-004 用神喜忌 + GJ-004 层次

原则：每句断语附规则号；格局派/扶抑派分歧不裁断；落位吉凶的柱位对应标注（推定）。
"""
from __future__ import annotations

from bazi_engine import ten_god, WUXING, WUXING_ZHI, KE  # noqa: E402

STAGE_ORDER = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"]
STAGE_GOOD = {"长生", "临官", "帝旺", "墓", "冠带", "养"}
STAGE_BAD = {"衰", "病", "死", "绝"}
POS_ORDER = ("年", "月", "日", "时")
# YL-007 名义表键名（含异名）
STAGE_YL_KEY = {"长生": "长生", "沐浴": "沐浴/败", "冠带": "冠带", "临官": "临官",
                "帝旺": "帝旺", "衰": "衰", "病": "病", "死": "死", "墓": "墓/库",
                "绝": "受气/绝", "胎": "受胎", "养": "成形"}
CAI_GUAN = ("正财", "偏财", "正官", "七杀")


class AnalysisEngine:
    def __init__(self, engine, config: dict | None = None):
        self.eng = engine
        self.cfg = {"liuqin": "三命"}
        if config and "liuqin" in config:
            self.cfg["liuqin"] = config["liuqin"]

    # ================= 入口 =================
    def analyze(self, out: dict, gender: str | None = None) -> dict:
        self.out = out
        self.pillars = out["四柱"]
        self.day_gan = self.pillars["日"][0]
        self.hid = out["藏干"]
        self.voids = out["空亡"]["空亡"]
        self.relations = (out.get("格局") or {}).get("地支关系", [])
        # 六亲星落位扫描
        self.god_spots = self._collect_spots()
        liuqin = self.liuqin(gender)
        duanyu = self.shensha_duanyu()
        report = self.report(liuqin, duanyu, gender)
        return {"六亲": liuqin, "神煞断语": duanyu, "报告": report,
                "盘面详解": self.panmian(duanyu),
                "说明": ("断语均为规则原文或原文句式，逐条带规则号；落位吉凶的柱位对应为推定；"
                         "六亲取用三说并列（ZP-027），此处按配置采用口径输出。")}

    # ================= 落位扫描 =================
    def _collect_spots(self) -> dict[str, list[dict]]:
        """十神 → 落位列表 [{柱位, 级别(干/支本气…), 字, 支}]。"""
        res: dict[str, list[dict]] = {}
        for p in POS_ORDER:
            gz = self.pillars[p]
            b = gz[1]
            s = gz[0]
            res.setdefault(ten_god(self.day_gan, s), []).append(
                {"柱位": p, "级别": "干", "字": s, "支": b})
            for lvl, label in (("本", "本气"), ("中", "中气"), ("余", "余气")):
                for t in self.hid[p].get(lvl, ""):
                    res.setdefault(ten_god(self.day_gan, t), []).append(
                        {"柱位": p, "级别": f"支{label}", "字": t, "支": b})
        return res

    # ================= 六亲（J7-060/061/062/064、ZP-016/027） =================
    def liuqin(self, gender: str | None) -> dict:
        school = self.cfg["liuqin"]
        lu = self.eng.data("LM-001")
        yima = self.eng.data("LM-003")
        tianyi = self.eng.data("SSH-005")
        yima_key = None
        for r in self.relations:  # 驿马按年支/日支双口径，取年支
            pass
        yima_by_group = yima
        from bazi_engine import BRANCH_GROUP
        yg = BRANCH_GROUP[self.pillars["年"][1]]
        ma_branch = yima_by_group[yg]

        def star_spots(gods: list[str]) -> list[dict]:
            spots = []
            for g in gods:
                spots += self.god_spots.get(g, [])
            return spots

        def judge(spot: dict) -> dict:
            """J7-062 落位吉凶：星字对该柱支的状态＋禄马贵人＋空亡＋刑冲破害。"""
            s, b = spot["字"], spot["支"]
            state = STAGE_ORDER[self.eng.data("YL-008")[s].index(b)]
            good, bad = [], []
            if state in STAGE_GOOD:
                good.append(f"坐{state}")
            if state in STAGE_BAD:
                bad.append(f"坐{state}")
            if lu[s] == b:
                good.append("坐禄")
            if b == ma_branch:
                good.append("坐驿马")
            if b in tianyi.get(s, []):
                good.append("坐天乙")
            if b in self.voids:
                bad.append("落空亡")
            touch = [r for r in self.relations
                     if r.get("成立") and r["类型"] in ("冲", "破", "害", "刑（子卯）", "三刑", "自刑")
                     and spot["柱位"] in r.get("柱位", [])]
            if touch:
                bad.append("逢" + "、".join(r["类型"] for r in touch))
            if bad and not good:
                verdict = "贫薄破伤刑夭（坐空刑克煞死绝衰败之地，J7-062）"
            elif good and not bad:
                verdict = "富贵福寿荣耀（坐长生旺库禄马贵人之地，J7-062）"
            elif state in ("死", "绝"):
                verdict = "带刑破害，虽居生旺库亦贫贱；居死绝恐不送老（J7-062）"
            else:
                verdict = "带刑破害虽居生旺库，有寿而贫贱（J7-062）"
            return {"落位": f"{spot['柱位']}{spot['级别']}{s}（坐{b}）", "十二宫": state,
                    "吉": good, "凶": bad, "断": verdict}

        # 六亲 → 十神组（按流派；性别感知）
        is_male = (gender != "女")
        star_specs = {
            "三命": {"父": ["偏财"], "母": ["正印"], "妻": ["正财"], "夫": ["正官", "七杀"],
                    "兄弟姊妹": ["比肩", "劫财"],
                    "子": ["正官", "七杀"] if is_male else ["食神", "伤官"]},
            "渊海": {"母": ["正印"], "祖父": ["偏印"], "父": ["偏财"], "妻": ["正财"],
                    "妾": ["偏财"], "夫": ["正官", "七杀"], "兄弟姊妹": ["比肩"],
                    "子": ["七杀" if is_male else "正官"] if not is_male else ["七杀"],
                    "孙": ["食神", "伤官"]},
            "千里": {"父母": ["正印", "偏印"], "妻": ["正财", "偏财"], "夫": ["正官", "七杀"],
                    "兄弟": ["比肩", "劫财"], "子": ["食神", "伤官"]},
        }.get(school, {})
        out_members = {}
        for member, gods in star_specs.items():
            spots = star_spots(gods)
            if not spots:
                out_members[member] = {"星": gods, "命中": False,
                                       "断": "局中不见此星（J7-064：局中无者看所生之地/大运补）",
                                       "落位明细": []}
                continue
            judged = [judge(sp) for sp in spots]
            best = max(judged, key=lambda j: len(j["吉"]))
            out_members[member] = {"星": gods, "命中": True, "主断": best["断"],
                                   "落位明细": judged}
        palace = self.eng.rule("SS-019").get("data") or {}
        return {"采用流派": school, "三说并列": self.eng.rule("ZP-027").get("data") or {},
                "六亲": out_members,
                "宫位": {p: palace.get(p) for p in POS_ORDER},
                "依据": ["J7-060", "J7-061", "J7-062", "J7-064", "SS-019", "ZP-027"],
                "说明": "星落位吉凶按 J7-062 原文三式判（柱位对应为推定）；女命夫子二星优先（千里女命篇）"}

    # ================= 神煞断语（SSH-080～086） =================
    def shensha_duanyu(self) -> list[dict]:
        hits = {r["神煞"]: r for r in self.out.get("神煞", {}).get("命中", [])}
        out = []
        if hits.get("元辰", {}).get("命中"):
            out.append({"神煞": "元辰", "断": self.eng.rule("SSH-080")["rule"], "依据": "SSH-080"})
        if hits.get("灾煞", {}).get("命中"):
            out.append({"神煞": "灾煞", "断": self.eng.rule("SSH-081")["rule"], "依据": "SSH-081"})
        if hits.get("六厄", {}).get("命中"):
            out.append({"神煞": "六厄", "断": self.eng.rule("SSH-082")["rule"], "依据": "SSH-082"})
        if hits.get("勾绞（勾）", {}).get("命中") or hits.get("勾绞（绞）", {}).get("命中"):
            out.append({"神煞": "勾绞", "断": self.eng.rule("SSH-083")["rule"], "依据": "SSH-083"})
        for name in ("孤辰", "寡宿"):
            if hits.get(name, {}).get("命中"):
                extra = []
                if hits.get("驿马", {}).get("命中"):
                    extra.append("驿马并主放荡")
                if any(self.branches_void(pos) for pos in hits[name]["命中柱位"]):
                    extra.append("落空亡并无倚")
                out.append({"神煞": name, "断": self.eng.rule("SSH-084")["rule"]
                            + ("；" + "；".join(extra) if extra else ""),
                            "依据": "SSH-084"})
        luo = [r for r in hits.get("天罗", {}).get("命中柱位", [])]
        wang = [r for r in hits.get("地网", {}).get("命中柱位", [])]
        if luo or wang:
            detail = self.eng.rule("SSH-085")["rule"]
            extra = []
            if self.out.get("日主") in "火" and luo:
                extra.append("火命值天罗（正犯）")
            if self.out.get("日主") in "水土" and wang:
                extra.append("水土命值地网（正犯）")
            if len(luo) >= 2 or len(wang) >= 2:
                extra.append("重犯")
            out.append({"神煞": "天罗地网", "断": detail + ("；" + "；".join(extra) if extra else ""),
                        "依据": "SSH-085/SSH-033"})
        return out

    def branches_void(self, pos_col: str) -> bool:
        p = pos_col[0]
        return self.pillars[p][1] in self.voids

    # ================= 盘面详解（逐柱拆解） =================
    def panmian(self, duanyu: list[dict] | None = None) -> dict:
        """逐柱把宫位、天干十神、藏干十神、星运、神煞、支关系、空亡并置解释。

        每项带规则号；星运等第按 YL-010；空亡断语按 KW-005/KW-009；
        含义取 MeaningEngine 已产出的 SS-010..018；宫位取 SS-019。
        """
        stage_seq = self.eng.data("YL-008")[self.day_gan]
        stage_yl = dict(self.eng.rule("YL-007").get("data") or [])
        grade = self.eng.rule("YL-010").get("data") or {}
        gong = self.eng.rule("SS-019").get("data") or {}
        meanings = ((self.out.get("含义") or {}).get("十神含义")) or {}
        sh_all = ((self.out.get("神煞") or {}).get("按神煞")) or {}
        stages = {p: STAGE_ORDER[stage_seq.index(self.pillars[p][1])] for p in POS_ORDER}
        self.out.setdefault("星运", stages)

        def stage_grade(st: str) -> str:
            s = {"长生": "生", "帝旺": "旺", "墓": "库", "沐浴": "败"}.get(st, st)
            if s in grade.get("四贵", []):
                return "四贵"
            if s in grade.get("四忌", []):
                return "四忌"
            return "四平"

        def meaning(god: str) -> dict:
            m = meanings.get(god) or {}
            d = {k: m.get(k) for k in ("关系", "能力", "人", "事", "物", "正面", "负面",
                                       "物质层面", "精神层面", "别名", "六亲")
                 if m.get(k)}
            d["规则"] = m.get("规则")
            d["level"] = m.get("level")
            return d

        def shensha_of(pos: str) -> list[dict]:
            rows = []
            for name, ent in sh_all.items():
                if not ent.get("命中"):
                    continue
                if any((p or "")[:1] == pos for p in ent.get("命中柱位") or []):
                    rows.append({"名": name, "类别": ent.get("类别"), "依据": ent.get("依据"),
                                 "level": ent.get("level"), "备注": ent.get("备注", "")})
            return rows

        def relation_of(pos: str) -> list[dict]:
            rows = []
            for r in self.relations:
                if not r.get("成立") or pos not in (r.get("柱位") or []):
                    continue
                row = {"类型": r["类型"], "支": r["支"], "力度": r.get("力度", ""),
                       "依据": r.get("依据", "")}
                if r.get("胜负倾向"):
                    row["胜负"] = r["胜负倾向"].get("综合")
                rows.append(row)
            return rows

        def duanyu_of(names: list[str]) -> list[dict]:
            rows = []
            for d in duanyu or []:
                if any(d["神煞"] in n or n in d["神煞"] for n in names):
                    rows.append(d)
            return rows

        cols = []
        for pos in POS_ORDER:
            gan, zhi = self.pillars[pos]
            god = ten_god(self.day_gan, gan)
            hidden = []
            for lvl, label in (("本", "本气"), ("中", "中气"), ("余", "余气")):
                for ch in self.hid[pos].get(lvl, ""):
                    hg = ten_god(self.day_gan, ch)
                    hm = meanings.get(hg) or {}
                    hidden.append({"层": label, "字": ch, "十神": hg,
                                   "取象": {k: hm.get(k) for k in ("人", "事", "物") if hm.get(k)},
                                   "规则": hm.get("规则")})
            names = [s["名"] for s in shensha_of(pos)]
            cols.append({
                "柱": pos,
                "干支": gan + zhi,
                "宫位": gong.get(pos),
                "空亡": {"落空": zhi in self.voids,
                         "旬空": self.voids if zhi in self.voids else []},
                "天干": {"字": gan, "十神": "日主" if pos == "日" else god,
                         "十神本义": god,
                         "含义": ({"规则": "SS-005", "level": "原文",
                                  "说明": "日干为命主自身；比肩乃『同我』之名，兄弟朋友之取象不入本柱自身断。"}
                                 if pos == "日" else meaning(god))},
                "地支": {"字": zhi, "五行": WUXING_ZHI[zhi],
                         "星运": stages[pos], "星运等第": stage_grade(stages[pos]),
                         "星运义": stage_yl.get(STAGE_YL_KEY.get(stages[pos], ""), "")},
                "藏干": hidden,
                "神煞": shensha_of(pos),
                "神煞断语": duanyu_of(names),
                "关系": relation_of(pos),
            })

        # 十神分布（干＋藏干；日干为命主自身，不计入）
        dist = []
        for god, spots in sorted(self.god_spots.items(),
                                 key=lambda kv: (-len(kv[1]), kv[0])):
            spots = [s for s in spots if not (s["柱位"] == "日" and s["级别"] == "干")]
            if not spots:
                continue
            dist.append({"神": god, "数": len(spots),
                         "处": [f"{s['柱位']}{s['级别']}{s['字']}" for s in spots],
                         "规则": (meanings.get(god) or {}).get("规则")})

        # SS-009 十神位置初义
        gan_gods = {p: ten_god(self.day_gan, self.pillars[p][0]) for p in POS_ORDER}
        hints = []
        if gan_gods["年"] == "正官":
            hints.append("年干带日之官星则福厚（SS-009）。")
        if gan_gods["年"] == "七杀":
            hints.append("年干带日之七煞则终身不可除去（SS-009）。")
        ym = [p for p in ("年", "月") if gan_gods[p] in CAI_GUAN]
        ds = [p for p in ("日", "时") if gan_gods[p] in CAI_GUAN]
        if ym:
            hints.append("年月有财官为富贵之家、祖业早发（SS-009；本局" + "、".join(ym) + "干见财官）。")
        elif ds:
            hints.append("年月无而日时有则自己成立（SS-009；本局" + "、".join(ds) + "干见财官）。")
        else:
            hints.append("年月日时干俱无财官：SS-009 尚有『年月无且幼运不好则出身卑微、破祖伤父』一断，"
                         "须合幼运（大运/小运）方成，本引擎未串幼运，仅作参考。")

        void_pos = [p for p in POS_ORDER if self.pillars[p][1] in self.voids]
        void_note = None
        if void_pos:
            text = self.eng.rule("KW-005")["rule"]
            extra = ""
            if len(void_pos) >= 3:
                extra = "；月日时三位俱空亡则不害为大贵人（KW-008）"
            elif any(p in ("日", "时") for p in void_pos):
                extra = "；日上空亡多庶出或妻妾间离，时上空亡多拗性、为事高而虚（KW-009）"
            void_note = {"柱位": void_pos, "断": text + extra, "依据": "KW-005/KW-008/KW-009"}

        readme = [
            {"项": "十神", "说明": "以日干为我，按生克与阴阳定十神；四纲取义（印/食/官/财）。",
             "依据": ["SS-001", "SS-005"]},
            {"项": "天干", "说明": "天干为透出之显；月令取格先取本气，本气不透再取中气、余气。",
             "依据": ["CG-001", "CG-004"]},
            {"项": "藏干", "说明": "地支所藏人元，分本气/中气/余气；日支所藏兼看配偶宫。",
             "依据": ["CG-007", "CG-002"]},
            {"项": "星运", "说明": "日主临各支的十二长生；胎、生、旺、库为四贵，死、绝、病、败为四忌，余为四平。",
             "依据": ["YL-008", "YL-007", "YL-010"]},
            {"项": "神煞", "说明": "福神欲生旺、煞神欲死绝；吉凶神煞不可拘定，轻重较量要在通变。",
             "依据": ["SSH-086"]},
            {"项": "宫位", "说明": "年祖上祖业、月父母兄弟门户、日己身配偶、时子息归宿；早年/青年/中年/晚年为通行分期（推定）。",
             "依据": ["SS-019", "J7-061"]},
            {"项": "空亡", "说明": "旬空之支落于柱位则减力；带空亡生旺动招虚名、死绝则成败飘泊。",
             "依据": ["KW-001", "KW-005"]},
            {"项": "关系", "说明": "六合/三合/三会/冲/刑/害/破的成立与力度；冲之胜负按本气＋时令＋多寡（推定性结论）。",
             "依据": ["ZP-006", "ZP-021", "ZP-022", "ZP-023", "ZP-024"]},
        ]

        return {
            "日主": {"日干": self.day_gan, "五行": WUXING[self.day_gan],
                     "自坐": {"支": self.pillars["日"][1], "星运": stages["日"],
                              "等第": stage_grade(stages["日"])},
                     "说明": "日干即日主，其比肩之名义仅作参照；日支为配偶宫（SS-019）。"},
            "逐柱": cols,
            "十神分布": dist,
            "位置初义": hints,
            "空亡": void_note,
            "读法": readme,
            "说明": ("逐柱详解把同一柱的宫位、天干十神、藏干十神、星运、神煞、支关系并置，"
                     "便于对照；每项带规则号。断语为规则原文或原文句式，不作吉凶总评；"
                     "星运等第按 YL-010，空亡断语按 KW-005/008/009。"),
            "依据": ["SS-001", "SS-005", "SS-009", "SS-010", "SS-011", "SS-012", "SS-013",
                     "SS-014", "SS-015", "SS-016", "SS-017", "SS-018", "SS-019",
                     "CG-001", "CG-007", "CG-004", "YL-007", "YL-008", "YL-010",
                     "KW-005", "KW-008", "KW-009", "SSH-086", "J7-061",
                     "ZP-006", "ZP-021", "ZP-022", "ZP-023", "ZP-024"],
        }

    # ================= 综合报告 =================
    def report(self, liuqin: dict, duanyu: list[dict], gender: str | None) -> list[dict]:
        g = self.out.get("格局") or {}
        st = g.get("日主强弱") or {}
        yong = g.get("用神") or {}
        sig = st.get("信号", {})
        secs: list[dict] = []

        # 1 日主
        secs.append({"标题": "日主强弱", "句子": [
            {"t": f"日干{self.day_gan}生于{sig.get('月令')}月，月令五行状态「{sig.get('月令五行状态')}」，"
                  f"{'当令' if sig.get('当令') else '失令'}（YL-006/ZP-025）"},
            {"t": f"天干帮扶 {sig.get('天干帮扶')}、支帮扶 {sig.get('支帮扶')}；"
                  f"克泄（官杀食伤）{sig.get('克泄（官杀食伤）')}（ZP-025）"},
            {"t": f"年日时支{'得气' if sig.get('支得气') else '失气'}（十二长生，YL-008）"},
            {"t": f"判定：{st.get('判定')}——{('身强喜抑：宜克泄分（官杀食伤财），忌印比再扶（ZP-026）') if st.get('身旺') else '身弱喜扶：宜印比生助（ZP-026）'}"},
        ], "依据": ["ZP-025", "ZP-026", "YL-006", "YL-008"]})

        # 2 月令取格
        mg = g.get("月令取格") or {}
        secs.append({"标题": "月令取格", "句子": [
            {"t": f"月支{mg.get('月支')}藏{mg.get('藏干', {}).get('本', '')}（本气）"
                  f"{'、' + mg.get('藏干', {}).get('中', '') if mg.get('藏干', {}).get('中') else ''}"
                  f"{'、' + mg.get('藏干', {}).get('余', '') if mg.get('藏干', {}).get('余') else ''}，"
                  f"本气十神「{mg.get('本气十神')}」（CG-007/SS-005）"},
            {"t": "月令为命，先以月令取用；月令无可用再看年日时（YL-001/YL-014）"},
        ], "依据": ["YL-001", "YL-005", "YL-014", "CG-004"]})

        # 2b 五行统计与日柱命式（外部对照采纳：卜易居同口径；事实层＋规则断语）
        wxs = self.out.get("五行统计")
        if wxs:
            miss = "、".join(wxs.get("缺", [])) or "无"
            sent = [{"t": f"五行个数：金{wxs.get('金')} 木{wxs.get('木')} 水{wxs.get('水')} "
                          f"火{wxs.get('火')} 土{wxs.get('土')}；所缺：{miss}（八字符统计，事实层）"}]
            j4 = self.eng.data("J4-001").get(self.day_gan)
            if j4:
                sent.append({"t": f"日主{self.day_gan}喜忌（J4-001 十干坐支表）：喜{j4.get('喜', '—')}；忌{j4.get('忌', '—')}"})
            ms = self.out.get("日时命式", {})
            ms_items = ms.get("命中") or ms.get("补录（易藏本）") or []
            for it in ms_items[:2]:
                sent.append({"t": f"日时命式[{it.get('id', '')}] {it.get('命式', '')}：{it.get('断语', '')}（MS-003，三命通会卷八九）"})
            secs.append({"标题": "五行与日柱命式", "句子": sent,
                         "依据": ["J4-001", "MS-003"]})

        # 3 格局成败
        rows = []
        for e in g.get("格局判定", []):
            if e["倾向"].startswith("成格"):
                rows.append({"t": f"{e['格']}成格（{e.  get('来源', '')}）——{e.get('用神提示', '')}"})
            elif e["倾向"] == "破格":
                hard = [b["因素"] for b in e.get("破格因素", []) if b["命中"]]
                rescue = self._rescue(e["格"])
                rows.append({"t": f"{e['格']}破格：{'、'.join(hard) or '条件不足'}"
                                  f"{'；救应提示：' + rescue if rescue else ''}（GJ-013 等）"})
        cheng_n = len(g.get("格局统计", {}).get("成格", []))
        rows.append({"t": f"成格 {cheng_n} 项——{g.get('格局层次', {}).get('断', '')}（GJ-004/SS-008）"})
        secs.append({"标题": "格局成败", "句子": rows, "依据": ["GJ-004", "GJ-012", "GJ-013", "SS-008"]})

        # 4 用神
        ding = yong.get("定神", {})
        secs.append({"标题": "用神与喜忌", "句子": [
            {"t": f"用神「{ding.get('神')}」（{ding.get('主法', '')}，置信{ding.get('置信')}）；"
                  f"备选：{'、'.join(ding.get('备选', [])) or '—'}"},
            {"t": f"行运喜忌：{yong.get('行运喜忌', {}).get('文本', '—')}（YS-004）"},
            {"t": f"配套：{'；'.join(c['法'] for c in yong.get('配套六法', [])) or '—'}（GJ-002）"},
        ], "依据": ["ZP-029", "ZP-028", "GJ-002", "YS-004"]})

        # 5 大运
        dy = self.out.get("大运")
        sent = []
        if dy:
            sent.append({"t": f"大运{dy['方向']}（YS-001）；起运{dy['起运']['文本'] if isinstance(dy['起运'], dict) else dy['起运']}（YS-002）"})
            for r in dy.get("大运（前八步）", [])[:4]:
                yx = r.get("用神喜忌", {})
                tip = ""
                if yx.get("命中"):
                    tip = "；用神" + "、".join(f"{x['位置']}{x['十神']}为{x['判']}" for x in yx["命中"])
                sent.append({"t": f"{r['干支']}运（约{r.get('起始岁（约）', '?')}岁起）：{r['十神（干）']}／{r['十神（支本气）']}，"
                                  f"{r['十二宫']}——{r['十二宫取象']}（YS-007）{tip}"})
        else:
            sent.append({"t": "大运未计算（需性别；排盘页选性别后自动给出，YS-001/002）"})
        secs.append({"标题": "大运走势", "句子": sent, "依据": ["YS-001", "YS-002", "YS-003", "YS-007"]})

        # 6 神煞提示
        if duanyu:
            secs.append({"标题": "神煞提示", "句子": [
                {"t": f"{d['神煞']}：{d['断']}"} for d in duanyu],
                "依据": ["SSH-080", "SSH-081", "SSH-082", "SSH-083", "SSH-084", "SSH-085"]})
        secs.append({"标题": "总原则与限制", "句子": [
            {"t": "福神欲生旺、煞神欲死绝；吉凶神煞不可拘定，轻重较量要在通变（SSH-086）"},
            {"t": "神煞为断语辅助层，须与格局、用神合看，不单独定吉凶（SSH-086）"},
            {"t": "分歧项（羊刃三说/天德两表/藏干两说等）见『分歧并列』，未擅自择一（用户约定）"},
        ], "依据": ["SSH-086"]})
        num = "一二三四五六七八九"
        for i, sec in enumerate(secs):
            sec["标题"] = f"{num[i]}、{sec['标题']}"
        return secs

    def _rescue(self, ge_name: str) -> str:
        """破格救应提示（GJ-002 取用六法/GJ-043 去留/GJ-085）。"""
        m = {
            "正官格": "伤官见官用印制伤护官；官杀混杂则去煞留官（合杀/食制，GJ-043/044）",
            "偏官格": "补食神制杀或印绶化杀；制过则喜财通关（GJ-031/033）",
            "正财格": "财多身弱用印比帮身；比劫夺财喜官杀制劫（GJ-080）",
            "偏财格": "兄弟分夺喜官杀制劫（GJ-081）",
            "正印格": "财破印用比劫制财存印、或官杀通关（GJ-082）",
            "伤官格": "伤官见官用印制伤；身弱用印去财（GJ-085）",
            "食神格": "枭神夺食用财制枭护食（GJ-086）",
        }.get(ge_name, "")
        return m
