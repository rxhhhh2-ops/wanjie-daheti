# -*- coding: utf-8 -*-
"""神煞引擎：按规则库 data 表批量计算，逐条附依据与口径。

覆盖（可编码且有表可查）：
- 日柱系：十恶大败（含年日冲配）、八专、九丑、孤鸾寡鹊、阴阳差错、天赦
- 年支系：劫煞、亡神、灾煞、六厄、桃花、将星、华盖、驿马、孤辰寡宿、
          暗金的煞、元辰、勾绞、三公煞、旌钺别种
- 日干系：天乙贵人、太极贵人、文昌、天印、学堂、词馆
- 月支系：月德、天德、月空、月厌、月煞、天喜、旌德、旌钺
- 其他：三奇、破煞、天罗地网、天乙喜忌

未编码（原文仅存歌诀/断语或需纳音）者不臆造，输出 `未编码` 清单。
"""
from __future__ import annotations

from bazi_engine import ZHI

STAGE_ORDER = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"]

SEASON_OF = {"寅": "春", "卯": "春", "辰": "春", "巳": "夏", "午": "夏", "未": "夏",
             "申": "秋", "酉": "秋", "戌": "秋", "亥": "冬", "子": "冬", "丑": "冬"}
SANHE_OF = {}
for _g in ("申子辰", "亥卯未", "寅午戌", "巳酉丑"):
    for _b in _g:
        SANHE_OF[_b] = _g
FANG_OF = {}
for _g in ("亥子丑", "寅卯辰", "巳午未", "申酉戌"):
    for _b in _g:
        FANG_OF[_b] = _g
GROUP4_OF = {}
for _g in ("子午卯酉", "寅申巳亥", "辰戌丑未"):
    for _b in _g:
        GROUP4_OF[_b] = _g
# 月厌（通行：正月戌、二月酉……）；原文「正月戊」疑「戌」形近
YUEYAN = {"寅": "戌", "卯": "酉", "辰": "申", "巳": "未", "午": "午", "未": "巳",
          "申": "辰", "酉": "卯", "戌": "寅", "亥": "丑", "子": "子", "丑": "亥"}
CHONG = {"子": "午", "午": "子", "丑": "未", "未": "丑", "寅": "申", "申": "寅",
         "卯": "酉", "酉": "卯", "辰": "戌", "戌": "辰", "巳": "亥", "亥": "巳"}

UNENCODED = [
    ("SSH-010", "月厌", "原文正月作『戊』，疑『戌』形近；本引擎按通行戌序计算并标注待校"),
    ("SSH-036", "自缢煞", "支对表与断语并存，未逐条核校"),
    ("SSH-037", "水溺煞", "需纳音与咸池/金刃/羊刃组合，纳音层未建"),
    ("SSH-038", "挂剑煞", "需官符/元辰/白虎/金神组合"),
    ("SSH-039", "天火煞", "需寅午戌全＋丙丁＋五位无水，条件可判但断语从简"),
    ("SSH-040", "天屠煞", "支对表可判，断语未展开"),
    ("SSH-041", "天刑煞", "原文有疑字（甲丙时/疑辰），待校"),
    ("SSH-042", "雷霆煞", "起法为月建顺数，需月建层"),
    ("SSH-043", "陷煞", "歌诀多歧，待校"),
    ("SSH-044", "官符病符丧门吊客", "岁前/命前诸辰，属流年层，见 yunsui_engine"),
    ("SSH-045", "日刑煞", "需命宫极刑/三合对宫，未编码"),
    ("SSH-046", "流血煞", "需本生月起子顺数至本年，未编码"),
    ("SSH-047", "剑锋煞", "旬首→剑锋表可判，断语从简"),
    ("SSH-048", "戟锋煞", "原文有疑字（十二巳/疑戊己），待校"),
    ("SSH-049", "浮沈煞", "需命宫十二宫，未编码"),
    ("SSH-051", "返本煞", "需纳音下克上，未编码"),
    ("SSH-052", "阴阳煞", "戊午/丙子日＋元辰咸池同宫，可判未编码"),
    ("SSH-064", "贵合与贵食", "组合表未逐条结构化"),
    ("SSH-065", "天乙扶身", "需夹拥太岁，未编码"),
    ("SSH-066", "干夹贵神", "夹丑未条件可判，未编码"),
    ("SSH-067", "夹贵逢六合", "组合表未逐条结构化"),
    ("SSH-070", "正印五行库", "需纳音，未编码"),
    ("SSH-072", "福聚印等五印", "条件为断语组合，未编码"),
    ("SSH-074", "德秀", "原表两栏分属不清，待校"),
]


class ShenshaEngine:
    def __init__(self, engine):
        self.eng = engine
        self.results: dict[str, dict] = {}

    # ---------- 入口 ----------
    def compute(self, pillars: dict, hid: dict, gender: str | None = None,
                ming_gong: dict | None = None) -> dict:
        self.pillars, self.hid = pillars, hid
        self.gender = gender
        self.day_gz = pillars["日"]
        self.day_gan = self.day_gz[0]
        self.year_gz = pillars["年"]
        self.month_zhi = pillars["月"][1]
        self.hour_gz = pillars["时"]
        self.stems = {p: pillars[p][0] for p in ("年", "月", "日", "时")}
        self.branches = {p: pillars[p][1] for p in ("年", "月", "日", "时")}
        self.branch_list = [self.branches[p] for p in ("年", "月", "日", "时")]
        self.voids = self._voids()
        self.season = SEASON_OF[self.month_zhi]
        self.month_group = SANHE_OF[self.month_zhi]
        self.year_group = SANHE_OF[self.branches["年"]]
        self.year_fang = FANG_OF[self.branches["年"]]
        self.year_group4 = GROUP4_OF[self.branches["年"]]
        self.year_yang = self.year_gz[0] in "甲丙戊庚壬"

        self._day_pillar_checks()
        self._year_branch_checks()
        self._day_gan_checks()
        self._month_checks()
        self._other_checks()

        hits = [r for r in self.results.values() if r["命中"]]
        return {
            "按神煞": self.results,
            "命中": hits,
            "命中数": len(hits),
            "未编码": [{"规则": rid, "神煞": name, "原因": why} for rid, name, why in UNENCODED],
            "说明": ("神煞为断语辅助层，须与格局/用神合看，不单独定吉凶（SSH-086）。"
                     "同一神煞按年支/日支、天德两表等口径并列；未提供性别时元辰/勾绞两说并列。"),
        }

    # ---------- 工具 ----------
    def _voids(self) -> list[str]:
        from bazi_engine import gz_index, gz_from_index
        p = gz_index(self.day_gz)
        xun = gz_from_index(p - p % 10)
        return self.eng.data("KW-002")[xun]

    def _rule(self, rid: str) -> dict:
        return self.eng.rule(rid)

    def _add(self, name: str, category: str, basis: str, value, hit_positions: list[str],
             rule: str, note: str = "", level: str | None = None):
        if name in self.results:  # 同名合并命中柱位
            old = self.results[name]
            old["命中柱位"] = sorted(set(old["命中柱位"]) | set(hit_positions))
            old["命中"] = bool(old["命中柱位"])
            return
        self.results[name] = {
            "神煞": name,
            "类别": category,
            "基准": basis,
            "值": value,
            "命中柱位": sorted(set(hit_positions)),
            "命中": bool(hit_positions),
            "依据": rule,
            "level": level or self._rule(rule)["level"],
            "备注": note,
        }

    def _stem_positions(self, target: str) -> list[str]:
        return [p for p in ("年", "月", "日", "时") if self.stems[p] == target]

    def _branch_positions(self, target: str) -> list[str]:
        return [p for p in ("年", "月", "日", "时") if self.branches[p] == target]

    def _gz_positions(self, target: str) -> list[str]:
        return [p for p in ("年", "月", "日", "时")
                if self.pillars[p] == target]

    def _stage_of(self, stem: str, branch: str) -> str:
        seq = self.eng.data("YL-008")[stem]
        return STAGE_ORDER[seq.index(branch)]

    # ---------- 日柱系 ----------
    def _day_pillar_checks(self):
        d = self.day_gz
        # 十恶大败（SSH-034）
        shi_e = self.eng.data("SSH-034")["日"]
        self._add("十恶大败", "日柱系", "日柱", d,
                  ["日"] if d in shi_e else [], "SSH-034",
                  "以日上见之为是" if d in shi_e else "")
        # 十恶大败年日冲配（SSH-035）
        pairs = [tuple(x) for x in self.eng.data("SSH-035")["配"]]
        hit = (self.year_gz, d) in pairs
        self._add("十恶大败年日冲配", "日柱系", "年柱＋日柱", f"{self.year_gz}/{d}",
                  [p for p in ("年", "日") if hit] if hit else [], "SSH-035")
        # 八专（SSH-053）
        bz = self.eng.data("SSH-053")["日"]
        self._add("八专", "日柱系", "日柱", d, ["日"] if d in bz else [], "SSH-053",
                  "淫欲之煞" if d in bz else "")
        # 九丑（SSH-054）
        jc = self.eng.data("SSH-054")["日"]
        self._add("九丑", "日柱系", "日柱", d, ["日"] if d in jc else [], "SSH-054",
                  "妨害之辰" if d in jc else "")
        # 孤鸾寡鹊（SSH-055）
        gl = self.eng.data("SSH-055")["日"]
        self._add("孤鸾寡鹊", "日柱系", "日柱", d, ["日"] if d in gl else [], "SSH-055",
                  "男克妻女克夫" if d in gl else "")
        # 阴阳差错（SSH-056）
        yc = self.eng.data("SSH-056")["日"]
        self._add("阴阳差错", "日柱系", "日柱", d, ["日"] if d in yc else [], "SSH-056")
        # 天赦（SSH-012）
        she = self.eng.data("SSH-012")["天赦"].get(self.season)
        self._add("天赦", "日柱系", "日柱＋季节", f"{self.season}:{she}",
                  ["日"] if d == she else [], "SSH-012")

    # ---------- 年支系 ----------
    def _year_branch_checks(self):
        yb, db = self.branches["年"], self.branches["日"]
        day_group = SANHE_OF[db]
        # 三合组起法类：年/日双口径并列（LM-011：取用柱位原文不统一）
        for name, rid in (
            ("劫煞", "SSH-018"),
            ("亡神", "SSH-019"),
            ("灾煞", "SSH-029"),
            ("六厄", "SSH-030"),
            ("桃花（咸池）", "SSH-057"),
            ("将星", "SSH-087"),
            ("华盖", "SSH-088"),
            ("驿马", "LM-003"),
        ):
            table = self.eng.data(rid)
            ty, td = table[self.year_group], table[day_group]
            positions = sorted(set(self._branch_positions(ty) + self._branch_positions(td)))
            self._add(name, "年支系", f"年支{yb}（{self.year_group}）/ 日支{db}（{day_group}）",
                      {"年支口径": ty, "日支口径": td}, positions, rid,
                      "取用柱位原文不统一，年/日双口径并列（LM-011）" if ty != td else "")
        # 孤辰寡宿（SSH-032）
        gua_y = self.eng.data("SSH-032")[self.year_fang]
        gua_d = self.eng.data("SSH-032")[FANG_OF[db]]
        for role in ("孤", "寡"):
            ty, td = gua_y[role], gua_d[role]
            positions = sorted(set(self._branch_positions(ty) + self._branch_positions(td)))
            self._add("孤辰" if role == "孤" else "寡宿", "年支系",
                      f"年支{yb}（{self.year_fang}）/ 日支{db}（{FANG_OF[db]}）",
                      {"年支口径": ty, "日支口径": td}, positions, "SSH-032",
                      "年/日双口径并列（LM-011）")
        # 暗金的煞（SSH-028）
        aq = self.eng.data("SSH-028")[self.year_group4]
        self._add("暗金的煞", "年支系", f"年支{yb}", aq,
                  self._branch_positions(aq), "SSH-028")
        # 元辰（SSH-027）
        self._yuan_chen()
        # 勾绞（SSH-031）
        self._gou_jiao()
        # 三公煞（SSH-014）
        sg = self.eng.data("SSH-014")[self.year_group]
        self._add("三公煞", "年支系", f"年支{yb}→{self.year_group}", sg,
                  self._gz_positions(sg), "SSH-014")
        # 旌钺别种（SSH-013）
        jb = self.eng.data("SSH-013")["旌钺别种"][self.year_fang]
        self._add("旌钺别种", "年支系", f"年支{yb}（{self.year_fang}）", jb,
                  ["日"] if self.day_gz == jb else [], "SSH-013")

    def _yuan_chen(self):
        idx = ZHI.index(self.branches["年"])
        chong = (idx + 6) % 12
        yang = self.year_yang

        def target(forward: bool) -> str:
            return ZHI[(chong + (1 if forward else -1)) % 12]

        if self.gender in ("男", "女"):
            # 阳男阴女→冲前一位；阴男阳女→冲后一位
            forward = (yang and self.gender == "男") or ((not yang) and self.gender == "女")
            t = target(forward)
            self._add("元辰", "年支系", "年支", t, self._branch_positions(t), "SSH-027",
                      "冲前一位" if forward else "冲后一位")
        else:
            a, b = target(True), target(False)
            self._add("元辰", "年支系", "年支", f"{a}（阳男阴女）/ {b}（阴男阳女）",
                      sorted(set(self._branch_positions(a) + self._branch_positions(b))),
                      "SSH-027", "未提供性别：两说并列")

    def _gou_jiao(self):
        idx = ZHI.index(self.branches["年"])
        yang = self.year_yang
        if self.gender in ("男", "女"):
            forward = (yang and self.gender == "男") or ((not yang) and self.gender == "女")
            gou = ZHI[(idx + (3 if forward else -3)) % 12]
            jiao = ZHI[(idx - (3 if forward else -3)) % 12]
            self._add("勾绞（勾）", "年支系", "命前/后三辰", gou,
                      self._branch_positions(gou), "SSH-031",
                      "命前三辰" if forward else "命后三辰")
            self._add("勾绞（绞）", "年支系", "命前/后三辰", jiao,
                      self._branch_positions(jiao), "SSH-031",
                      "命后三辰" if forward else "命前三辰")
        else:
            plus, minus = ZHI[(idx + 3) % 12], ZHI[(idx - 3) % 12]
            self._add("勾绞（勾）", "年支系", "命前/后三辰", f"{plus}/{minus}",
                      sorted(set(self._branch_positions(plus) + self._branch_positions(minus))),
                      "SSH-031", "未提供性别：两说并列")
            self._add("勾绞（绞）", "年支系", "命前/后三辰", f"{plus}/{minus}",
                      sorted(set(self._branch_positions(plus) + self._branch_positions(minus))),
                      "SSH-031", "未提供性别：两说并列")

    # ---------- 日干系 ----------
    def _day_gan_checks(self):
        # 天乙贵人（SSH-005）：年干/日干双口径
        tg = self.eng.data("SSH-005")
        targets = sorted(set(tg[self.year_gz[0]] + tg[self.day_gan]))
        hit = [p for p in ("年", "月", "日", "时") if self.branches[p] in targets]
        self._add("天乙贵人", "日干系", "年干＋日干", targets, hit, "SSH-005",
                  self._tianyi_note(targets))
        # 太极贵人（SSH-015）
        taiji = self._taiji_targets()
        self._add("太极贵人", "日干系", "年干＋日干", taiji,
                  [p for p in ("年", "月", "日", "时") if self.branches[p] in taiji], "SSH-015")
        # 文昌 / 天印（SSH-016，文昌取千里表 ZP-013）
        wc, ty = self.eng.data("SSH-016")["文昌"], self.eng.data("SSH-016")["天印"]
        for name, table, note in (("文昌", wc, "取千里表（ZP-013）；三命歌诀待核"),
                                  ("天印", ty, "原文歌诀；待校")):
            tset = sorted({table[self.year_gz[0]], table[self.day_gan]})
            self._add(name, "日干系", "年干＋日干", tset,
                      [p for p in ("年", "月", "日", "时") if self.branches[p] in tset],
                      "SSH-016", note)
        # 学堂/词馆（SSH-017）：日干长生/临官
        seq = self.eng.data("YL-008")[self.day_gan]
        cs, lg = seq[0], seq[3]
        self._add("学堂", "日干系", f"日干{self.day_gan}长生", cs,
                  self._branch_positions(cs), "SSH-017",
                  "三命以纳音长生为正位；引擎按日干长生（通行），须复核")
        self._add("词馆", "日干系", f"日干{self.day_gan}临官", lg,
                  self._branch_positions(lg), "SSH-017",
                  "三命以纳官临官为正位；引擎按日干临官（通行），须复核")

    def _taiji_targets(self) -> list[str]:
        data = self.eng.data("SSH-015")
        out = set()
        for gan in (self.year_gz[0], self.day_gan):
            for key, vals in data.items():
                if gan in key:
                    for v in vals:
                        if v == "辰戌丑未库":
                            out.update("辰戌丑未")
                        else:
                            out.add(v)
                    break
        return sorted(out)

    def _tianyi_note(self, targets: list[str]) -> str:
        """SSH-063：喜生旺、无冲破、不落空亡。"""
        bad = []
        for p in ("年", "月", "日", "时"):
            if self.branches[p] not in targets:
                continue
            b = self.branches[p]
            if b in self.voids:
                bad.append(f"{p}支{b}落空亡")
            if CHONG.get(b) in self.branch_list:
                bad.append(f"{p}支{b}逢冲")
            if self._stage_of(self.day_gan, b) in ("死", "绝", "病"):
                bad.append(f"{p}支{b}处死绝病")
        return "；".join(dict.fromkeys(bad)) if bad else "喜生旺、无冲破空亡"

    # ---------- 月支系 ----------
    def _month_checks(self):
        mz, mg = self.month_zhi, self.month_group
        # 月德（SSH-007）
        yd = self.eng.data("SSH-007")[mg]
        self._add("月德", "月支系", f"月支{mz}→{mg}", yd,
                  self._stem_positions(yd), "SSH-007")
        # 天德（SSH-008 三命宫组 vs ZP-012 千里表）
        gong = GROUP4_OF[mz]
        three = self.eng.data("SSH-008")[gong]
        qian = self._qianli_tiande()
        self._add("天德", "月支系", f"月支{mz}（{gong}）",
                  {"三命宫组": three, "千里表": qian},
                  self._stem_positions(qian), "SSH-008",
                  f"三命按宫组配干（{three}），千里按月支单干（{qian}）；两说并列（ZP-012）")
        # 月空（SSH-009）
        yk = self.eng.data("SSH-009")[mg]
        self._add("月空", "月支系", f"月支{mz}→{mg}", yk,
                  self._stem_positions(yk), "SSH-009",
                  self.eng.data("SSH-009").get("备注", ""))
        # 月厌（SSH-010）
        yy = YUEYAN[mz]
        self._add("月厌", "月支系", f"月支{mz}", yy, self._branch_positions(yy),
                  "SSH-010", "原文正月作『戊』，疑『戌』形近；按通行戌序计算")
        # 月煞（SSH-011）
        ys = self.eng.data("SSH-011")[mg]
        self._add("月煞", "月支系", f"月支{mz}→{mg}", ys,
                  self._branch_positions(ys), "SSH-011")
        # 天喜（SSH-012）
        tx = self.eng.data("SSH-012")["天喜"][self.season]
        self._add("天喜", "月支系", f"月支{mz}（{self.season}）", tx,
                  self._branch_positions(tx), "SSH-012",
                  "原文天喜作『春戊』，疑『戌』形近；按戌实现")
        # 旌德 / 旌钺（SSH-013）
        jd = self.eng.data("SSH-013")["旌德"][mg]
        self._add("旌德", "月支系", f"月支{mz}→{mg}", jd,
                  [p for p in ("日", "时") if self.stems[p] == jd], "SSH-013")
        jy = self.eng.data("SSH-013")["旌钺时"][mg]
        self._add("旌钺", "月支系", f"月支{mz}→{mg}", jy,
                  ["时"] if self.branches["时"] == jy else [], "SSH-013")

    def _qianli_tiande(self) -> str:
        data = self.eng.data("ZP-012")
        for k, v in data.items():
            if self.month_zhi in k:
                return v
        return "未列"

    # ---------- 其他 ----------
    def _other_checks(self):
        # 三奇（SSH-006）
        groups = self.eng.data("SSH-006")["组"]
        names = self.eng.data("SSH-006")["名"]
        pos = {p: i for i, p in enumerate(("年", "月", "日", "时"))}
        for grp in groups:
            present = [p for p in ("年", "月", "日", "时") if self.stems[p] in grp]
            if len({self.stems[p] for p in present}) == 3:
                idxs = sorted(pos[p] for p in present)
                shun = idxs == list(range(idxs[0], idxs[0] + 3))
                key = "".join(grp)
                self._add("三奇", "其他", "四柱天干", key,
                          present, "SSH-006",
                          f"{names.get(key, '')}；{'顺布' if shun else '逆布/间隔（喜顺布，SSH-068）'}")
                break
        # 破煞（SSH-050）
        po_hit = []
        for pair in self.eng.data("SSH-050")["破"]:
            if all(b in self.branch_list for b in pair):
                po_hit += [p for p in ("年", "月", "日", "时") if self.branches[p] in pair]
        self._add("破煞", "其他", "四柱地支", self.eng.data("SSH-050")["破"],
                  sorted(set(po_hit)), "SSH-050")
        # 天罗地网（SSH-033）
        luo = [p for p in ("年", "月", "日", "时") if self.branches[p] in ("戌", "亥")]
        wang = [p for p in ("年", "月", "日", "时") if self.branches[p] in ("辰", "巳")]
        note = self.eng.data("SSH-033")["适用"] + "；引擎仅报支见，未按纳音筛选（纳音层未建）"
        self._add("天罗", "其他", "四柱地支", "戌亥", luo, "SSH-033", note)
        self._add("地网", "其他", "四柱地支", "辰巳", wang, "SSH-033", note)
