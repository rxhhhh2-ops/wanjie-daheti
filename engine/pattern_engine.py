# -*- coding: utf-8 -*-
"""完整格局引擎：月令取格 → 身强弱 → 成格/破格 → 倾向与分歧并列。

口径与依据（全部可在 rules/*.json 查到）：
- 取格次序：YL-001 / YL-014 / CG-004 / GJ-015（月令为先，明干→暗藏）
- 身强弱：ZP-025 / ZP-026（千里命稿强弱篇）＋ YL-006（旺相休囚死）＋ YL-008（十二长生）
- 正官：GJ-010/011/012/013/014/015
- 偏官：GJ-030/031/032/033/036/041/042
- 建禄：GJ-050/051/052/054
- 财/印/伤官/食神：GJ-080/081/082/085/086
- 从格专旺：GJ-060..070、ZP-002..005
- 杂气：GJ-084
- 外格：GJ-100..125、WG2-001、ZP-001
- 地支关系：ZP-006（合）、ZP-021（冲）、ZP-022（刑）、ZP-023（害）、ZP-024（并见）、SSH-050（破）

原则：
1. 每个判定附 `依据`；原文未覆盖的条件标 `参考`/`待岁运`，不补写。
2. 输出 `倾向` 为「成格 / 疑似成格 / 破格 / 待定 / 成格（岁运待验）」之一，并列出缺失条件。
3. 多书分歧一律 `分歧` 并列，配置项见 `DEFAULT_CONFIG`。
"""
from __future__ import annotations

from collections import defaultdict

from bazi_engine import (
    GAN, WUXING, WUXING_ZHI, KE, SHENG, SHENG_WO, KE_WO, ten_god,
)

# ---------- 地支关系表 ----------
LIUHE = {"子丑", "寅亥", "卯戌", "辰酉", "巳申", "午未"}
LIUCHONG = {"子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥"}
LIUHAI = {"子未", "丑午", "寅巳", "卯辰", "申亥", "酉戌"}
# SSH-050 三命破煞：卯午、丑辰、子酉、未戌；寅申巳亥原破却三合不取
LIUPO = {"卯午", "丑辰", "子酉", "未戌"}
XING3 = ("寅巳申", "丑戌未")
XING2 = {"子卯"}
ZIXING = "辰午酉亥"
SANHE = {"申子辰": "水", "亥卯未": "木", "寅午戌": "火", "巳酉丑": "金"}
SANHE_WANG = {"申子辰": "子", "亥卯未": "卯", "寅午戌": "午", "巳酉丑": "酉"}
SANHUI = {"寅卯辰": "东方木", "巳午未": "南方火", "申酉戌": "西方金", "亥子丑": "北方水"}
HE_PARTNER = {"甲": "己", "己": "甲", "乙": "庚", "庚": "乙", "丙": "辛", "辛": "丙",
              "丁": "壬", "壬": "丁", "戊": "癸", "癸": "戊"}

SEASON = {"寅": "春", "卯": "春", "辰": "六月", "巳": "夏", "午": "夏", "未": "六月",
          "申": "秋", "酉": "秋", "戌": "六月", "亥": "冬", "子": "冬", "丑": "六月"}
STAGE_ORDER = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"]
STAGE_LOST = {"衰", "病", "死", "绝"}  # 千里以衰病死绝为失气（与 YL-010 四贵四忌不同，见分歧）

HELP_GODS = {"比肩", "劫财", "正印", "偏印"}
DRAIN_GODS = {"正官", "七杀", "食神", "伤官"}
CAI_GODS = {"正财", "偏财"}
YIN_GODS = {"正印", "偏印"}
SHISHANG = {"食神", "伤官"}

GONG = {}
for _b in "子午卯酉":
    GONG[_b] = "子午卯酉"
for _b in "辰戌丑未":
    GONG[_b] = "辰戌丑未"
for _b in "寅申巳亥":
    GONG[_b] = "寅申巳亥"

# 渊海《又地支藏遁歌》与藏干通行口径（CG-007，未列者循 CG-003）的差异（ZP-020）
# 丑：通行沿用 CG-003 原文余气作庚，渊海作辛；辰未：集合相同、次序不同
YH_CANGGAN = {"丑": ["癸", "辛", "己"], "辰": ["乙", "戊", "癸"],
              "未": ["乙", "己", "丁"], "午": ["丁", "己"]}

DEFAULT_CONFIG = {
    "yangren": "三命",       # 三命（十干皆有刃｜禄前一辰）/ 渊海（五阴无刃）/ 千里（阴刃禄后）
    "canggan": "通行",       # 通行（CG-007）/ 渊海
    "tiande": "并呈",        # 三命 / 千里 / 并呈
    "huoqi": "并呈",         # 三命（正化月）/ 千里（唯四季月）/ 并呈
    "shangugan_ji_guan": "丙丁",  # 火土伤官忌见官（GJ-085）；余干不忌
    "liuqin": "三命",        # 六亲取用：三命（J7-060）/ 渊海（ZP-016）/ 千里（ZP-027）
    "yongshen_order": "调候优先",  # 调候优先 / 格局优先（流派分歧，ZP-029）
}

# 用神链优先级预设：角色 → 优先级（数字小者先）
YONGSHEN_ORDER = {
    "调候优先": {"从化神": 1, "调候神": 2, "格神": 3, "相神": 4, "扶抑神": 4, "病药神": 5},
    "格局优先": {"从化神": 1, "格神": 2, "相神": 3, "调候神": 3, "扶抑神": 4, "病药神": 5},
}

# 用神行运喜忌（YS-004：官欲生、煞欲制、财欲扶、印欲旺、食欲生）；
# 伤官项 YS-004 未列，按 GJ-085『伤官要财不要官』扩展。
YONGSHEN_XIJI = {
    "正官": {"喜": ["正印", "偏印"], "忌": ["伤官"], "文本": "官欲运生，不欲运伤（YS-004/GJ-016）"},
    "七杀": {"喜": ["食神", "伤官"], "忌": ["正财", "偏财"], "文本": "煞欲制，不欲助（YS-004）"},
    "正财": {"喜": ["食神"], "忌": ["比肩", "劫财"], "文本": "财欲扶，不欲劫（YS-004/GJ-080）"},
    "偏财": {"喜": ["食神"], "忌": ["比肩", "劫财"], "文本": "财欲扶，不欲劫（YS-004/GJ-081）"},
    "正印": {"喜": ["正官", "七杀"], "忌": ["正财", "偏财"], "文本": "印欲旺（官煞生印），不欲衰（财破印）（YS-004/GJ-082）"},
    "偏印": {"喜": ["正官", "七杀"], "忌": ["正财", "偏财"], "文本": "印欲旺，不欲衰（YS-004/GJ-082）"},
    "食神": {"喜": ["比肩", "劫财"], "忌": ["偏印"], "文本": "食欲生（比劫生食），不欲枭绝（YS-004/GJ-086）"},
    "伤官": {"喜": ["正财", "偏财"], "忌": ["正官"], "文本": "伤官要财不要官（GJ-085；YS-004 未列，扩展）"},
}

# GJ-002 取用六法：用神之配套十神
LIUFA_PAIR = {
    "正官": ("财", "逢官看财"),
    "七杀": ("印", "逢煞看印"),
    "正印": ("官", "逢印看官"),
    "偏印": ("官", "逢印看官"),
    "食神": ("身旺", "食须身旺而吐（GJ-086 食神生旺）"),
    "伤官": ("财", "伤官要财（GJ-085）"),
    "正财": ("身旺", "财须身旺任（GJ-080 日主有力）"),
    "偏财": ("身旺", "财须身旺任（GJ-081）"),
}

GOD_GROUPS = {"伤食": ("食神", "伤官"), "官杀": ("正官", "七杀"),
              "财": ("正财", "偏财"), "印": ("正印", "偏印"), "比劫": ("比肩", "劫财")}
GOD_RULE_NAMES = {"比肩", "劫财", "食神", "伤官", "正财", "偏财",
                  "正官", "七杀", "正印", "偏印"}


def C(cond: str, met, ref: str, note: str = "", nature: str = "必需") -> dict:
    return {"条件": cond, "满足": met, "依据": ref, "说明": note, "性质": nature}


def B(factor: str, hit: bool, ref: str, note: str = "") -> dict:
    return {"因素": factor, "命中": hit, "依据": ref, "说明": note}


class PatternEngine:
    def __init__(self, engine, config: dict | None = None):
        self.eng = engine
        self.cfg = dict(DEFAULT_CONFIG)
        for k in DEFAULT_CONFIG:
            if config and k in config:
                self.cfg[k] = config[k]
        self.pillars = self.hid = None

    # ================= 公共入口 =================
    def assess(self, pillars: dict, hid: dict) -> dict:
        self.pillars = pillars
        self.hid = hid
        self.day_gz = pillars["日"]
        self.day_gan = self.day_gz[0]
        self.month_zhi = pillars["月"][1]
        self.positions = [("年", pillars["年"]), ("月", pillars["月"]),
                          ("日", pillars["日"]), ("时", pillars["时"])]
        self.branches = [b for _, gz in self.positions for b in [gz[1]]]
        self.stems = {pos: gz[0] for pos, gz in self.positions}
        self.season = SEASON[self.month_zhi]
        self._gods = self._collect_gods()
        self.visible_gods = {pos: ten_god(self.day_gan, self.stems[pos]) for pos in ("年", "月", "时")}
        self.voids = self._voids()
        self.strength = self._strength()
        self.relations = self._relations()

        month_cands = self._month_candidates()
        entries = [self._assess_candidate(c) for c in month_cands]
        specials = self._special_entries()

        merged: dict[str, dict] = {}
        for e in entries + specials:
            key = e["格"]
            if key not in merged:
                merged[key] = e
            elif merged[key]["类别"] != "正格" and e["类别"] == "正格":
                # 同名时以正格为主，原外格/专旺条并列保留
                old = merged[key]
                merged[key] = e
                merged[key]["并列"] = merged[key].get("并列", []) + [old]
            else:
                merged[key]["并列"] = merged[key].get("并列", []) + [e]
        order = self._dedup_order([e["格"] for e in entries + specials])
        pattern_list = [merged[k] for k in order]

        stats = defaultdict(list)
        for e in pattern_list:
            v = e["倾向"]
            if v.startswith("成格"):
                stats["成格"].append(e["格"])
            elif v == "疑似成格":
                stats["疑似"].append(e["格"])
            elif v == "破格":
                stats["破格"].append(e["格"])
            else:
                stats["待定"].append(e["格"])

        return {
            "配置": dict(self.cfg),
            "用神": self._yongshen(month_cands, pattern_list),
            "月令取格": self._month_summary(month_cands),
            "日主强弱": self.strength,
            "地支关系": self.relations,
            "格局判定": pattern_list,
            "格局统计": dict(stats),
            "格局层次": self._pattern_level(pattern_list),
            "分歧并列": self._divergences(pattern_list),
            "说明": ("成格/破格依原文条件逐项核验；『岁运待验』项须第二步岁运流年接入。"
                     "倾向为规则倾向，不作吉凶总评；分歧项按配置并列，未擅自择一。"),
        }

    def _pattern_level(self, pattern_list: list[dict]) -> dict:
        """格局高低与清纯（GJ-004 格数多少断＋SS-008 数量断＋破格因素计数）。"""
        cheng = [e for e in pattern_list if e["倾向"].startswith("成格")]
        n = len(cheng)
        duan = ("一格二格，非卿即相" if n <= 2 else
                "三格四格，财官不纯，非刑卒即九流（GJ-004）" if n <= 4 else
                f"成格 {n} 项（GJ-004：三格四格已杂）")
        qing = []
        for e in cheng:
            k = len([b for b in e.get("破格因素", []) if b["命中"]])
            qing.append({"格": e["格"], "破格命中数": k,
                         "清纯": "清" if k == 0 else ("微浊" if k == 1 else "浊")})
        return {
            "成格数": n,
            "断": duan,
            "成格清纯": qing,
            "说明": ("格数为机械统计，按 GJ-004 供参考；清纯按各成格的破格因素计数（SS-008"
                     "数量断同口径）。须与月令、身强弱、岁运合看，不单独定贵贱。"),
            "依据": ["GJ-004", "SS-008"],
        }

    # ================= 基础采集 =================
    def _collect_gods(self) -> dict[str, list[dict]]:
        res: dict[str, list[dict]] = defaultdict(list)
        for pos in ("年", "月", "时"):
            god = ten_god(self.day_gan, self.stems[pos])
            res[god].append({"来源": f"{pos}干", "字": self.stems[pos]})
        for pos in ("年", "月", "日", "时"):
            for lvl, label in (("本", "本气"), ("中", "中气"), ("余", "余气")):
                for s in self.hid[pos].get(lvl, ""):
                    god = ten_god(self.day_gan, s)
                    res[god].append({"来源": f"{pos}支{label}", "字": s})
        return res

    def _eff(self, god: str) -> list[dict]:
        """有效十神：透干 ＋ 未透的本气；同一字『藏而透』只计一次。

        中气/余气不透者只作暗藏，不计入『官煞混杂/伤官见官』等破格判定
        （CG-004：本气不透再取中气，中气不透再取余气；GJ-013 破格取『见』不以暗藏论）。
        本气之字若已透干，视为同一星之根，不再重复计数（GJ-010『官星一位』）。
        """
        occs = self._gods.get(god, [])
        visible = [o for o in occs if o["来源"].endswith("干")]
        vis_chars = {o["字"] for o in visible}
        out = list(visible)
        for o in occs:
            if o["来源"].endswith("本气") and o["字"] not in vis_chars:
                out.append(o)
        return out

    def _n(self, god: str) -> int:
        return len(self._eff(god))

    def _n_all(self, god: str) -> int:
        return len(self._gods.get(god, []))

    def _n_pos(self, god: str) -> int:
        """按柱位计『成势』：某柱天干或本气含该神即计一柱（四柱纯煞＝4）。"""
        pos = set()
        for occ in self._gods.get(god, []):
            src = occ["来源"]
            if src.endswith("干") or src.endswith("本气"):
                pos.add(src[0])
        return len(pos)

    def _hid_stems(self, pos: str, level: str | None = None) -> str:
        """藏干统一为字符串（CG-007 的 本/中/余 为字符列表）。"""
        if level is not None:
            v = self.hid[pos].get(level, "")
            return "".join(v) if isinstance(v, (list, tuple)) else v
        return "".join(self._hid_stems(pos, k) for k in ("本", "中", "余"))

    def _has(self, god: str) -> bool:
        return self._n(god) > 0

    def _visible(self, god: str) -> list[str]:
        return [p for p in ("年", "月", "时") if self.visible_gods[p] == god]

    def _voids(self) -> list[str]:
        p = _gz_index(self.day_gz)
        xun = _gz_from_index(p - p % 10)
        return self.eng.data("KW-002")[xun]

    def _stage(self, branch: str) -> str:
        return self._stage_of(self.day_gan, branch)

    def _stage_of(self, stem: str, branch: str) -> str:
        seq = self.eng.data("YL-008")[stem]
        return STAGE_ORDER[seq.index(branch)]

    def _element_state(self, wx: str) -> str:
        tbl = self.eng.data("YL-006")[self.season]
        for state, el in tbl.items():
            if el == wx:
                return state
        raise KeyError(wx)

    # ================= 身强弱（ZP-025） =================
    def _strength(self) -> dict:
        state = self._element_state(WUXING[self.day_gan])
        dangling = state in ("旺", "相")

        stem_help = sum(1 for p in ("年", "月", "时") if self.visible_gods[p] in HELP_GODS)
        branch_help = sum(1 for p in ("年", "月", "日", "时")
                          if ten_god(self.day_gan, self.hid[p]["本"][0]) in HELP_GODS)
        stem_drain = sum(1 for p in ("年", "月", "时") if self.visible_gods[p] in DRAIN_GODS)
        branch_drain = sum(1 for p in ("年", "月", "日", "时")
                           if ten_god(self.day_gan, self.hid[p]["本"][0]) in DRAIN_GODS)
        drain = stem_drain + branch_drain

        qi = []
        for p in ("年", "日", "时"):
            st = self._stage(self.branches[("年", "月", "日", "时").index(p)])
            qi.append({"柱位": p, "支": self.branches[("年", "月", "日", "时").index(p)],
                       "十二宫": st, "得气": st not in STAGE_LOST})
        zhi_deqi = any(x["得气"] for x in qi)

        many_help = stem_help >= 2 or (stem_help >= 1 and branch_help >= 2)
        many_drain = drain >= 4

        if dangling:
            if many_drain:
                verdict = "中弱"
            elif not zhi_deqi:
                verdict = "次弱"
            elif many_help:
                verdict = "最强"
            else:
                verdict = "中强"
        else:
            if zhi_deqi and not many_help:
                verdict = "次强"
            elif many_drain and not zhi_deqi:
                verdict = "最弱"
            elif many_help:
                verdict = "中强"
            elif zhi_deqi:
                verdict = "次强"
            else:
                verdict = "次弱"

        strong = verdict in ("最强", "中强", "次强")
        divergences = []
        if not dangling and many_help:
            divergences.append({
                "主题": "身强弱归类（原文两例不一）",
                "说明": ("千里强弱篇：乙日『多帮扶而失令』作中强；丁日『失令少克泄而多帮扶』作中弱。"
                         "本引擎取『多帮扶＝中强』，请人工复核。"),
                "依据": ["ZP-025"],
            })
        divergences.append({
            "主题": "支得气口径",
            "说明": ("千里以衰病死绝为失气；YL-010 以死绝病败（败＝沐浴）为四忌、衰为四平。"
                     "本引擎取千里口径，两说并列。"),
            "依据": ["ZP-025", "YL-010", "YL-008"],
        })

        return {
            "判定": verdict,
            "身旺": strong,
            "信号": {
                "月令": self.month_zhi,
                "季节": self.season,
                "日干五行": WUXING[self.day_gan],
                "月令五行状态": state,
                "当令": dangling,
                "天干帮扶": stem_help,
                "支帮扶": branch_help,
                "多帮扶": many_help,
                "克泄（官杀食伤）": drain,
                "多克泄": many_drain,
                "年日时支十二宫": qi,
                "支得气": zhi_deqi,
            },
            "方法": ("千里命稿强弱篇三信号（当令/帮扶/克泄/支得气）＋工程阈值（推定）："
                     "多帮扶＝天干≥2 或 天干≥1且支≥2；多克泄＝≥4；支得气＝不逢衰病死绝。"),
            "依据": ["ZP-025", "ZP-026", "YL-006", "YL-008", "CG-007"],
            "分歧": divergences,
        }

    # ================= 地支关系（ZP-006/021/022/023/024/SSH-050） =================
    def _relations(self) -> list[dict]:
        out: list[dict] = []
        ps = self.positions
        for i in range(4):
            for j in range(i + 1, 4):
                a, b = ps[i][1][1], ps[j][1][1]
                dist = j - i
                pair = frozenset((a, b))
                pos = [ps[i][0], ps[j][0]]
                if pair in _fs(LIUHE):
                    ok = dist == 1
                    out.append({"类型": "六合", "支": a + b, "柱位": pos, "距离": dist,
                                "成立": ok, "力度": "紧贴" if ok else "间隔（千里：不能合）",
                                "依据": "ZP-006"})
                if pair in _fs(LIUCHONG):
                    ok = dist < 3
                    item = {"类型": "冲", "支": a + b, "柱位": pos, "距离": dist, "成立": ok,
                            "力度": "正冲" if dist == 1 else ("隔一位（冲力减轻）" if dist == 2 else "海底冲（不作冲）"),
                            "依据": "ZP-021"}
                    if ok:
                        item["胜负倾向"] = self._chong_winner(a, b)
                    out.append(item)
                if pair in _fs(LIUHAI):
                    ok = dist == 1
                    out.append({"类型": "害", "支": a + b, "柱位": pos, "距离": dist,
                                "成立": ok, "力度": "紧贴" if ok else "间隔（不以害论）",
                                "依据": "ZP-023"})
                if pair in _fs(LIUPO):
                    out.append({"类型": "破", "支": a + b, "柱位": pos, "距离": dist,
                                "成立": True, "力度": "相破", "依据": "SSH-050"})
                if pair in _fs(XING2):
                    out.append({"类型": "刑（子卯）", "支": a + b, "柱位": pos, "距离": dist,
                                "成立": True, "力度": "力轻", "依据": "ZP-022"})

        for trio in XING3:
            if all(z in self.branches for z in trio):
                out.append({"类型": "三刑", "支": trio,
                            "柱位": [p for p, gz in ps if gz[1] in trio],
                            "成立": True, "力度": "三刑全", "依据": "ZP-022"})
        for z in ZIXING:
            if self.branches.count(z) >= 2:
                out.append({"类型": "自刑", "支": z + z,
                            "柱位": [p for p, gz in ps if gz[1] == z],
                            "成立": True, "力度": "自刑", "依据": "ZP-022"})

        for group in SANHE:
            hits = [p for p, gz in ps if gz[1] in group]
            if len({gz[1] for p, gz in ps if gz[1] in group}) == 3:
                out.append({"类型": "局合（三合）", "支": group, "柱位": [p for p in hits],
                            "成立": True, "力度": "三支全", "依据": "ZP-006/ZP-024"})
            else:
                present = [z for z in group if z in self.branches]
                if len(present) == 2:
                    has_wang = SANHE_WANG[group] in present
                    out.append({"类型": "半合", "支": "".join(present), "柱位":
                                [p for p, gz in ps if gz[1] in present],
                                "成立": True, "力度": "有旺支（力近全合）" if has_wang else "无旺支（力弱）",
                                "依据": "ZP-006/ZP-024"})
        for group in SANHUI:
            if all(z in self.branches for z in group):
                out.append({"类型": "方合（三会）", "支": group,
                            "柱位": [p for p, gz in ps if gz[1] in group],
                            "成立": True, "力度": "三支全（力大于局合）", "依据": "ZP-006/ZP-024"})
        return out

    def _chong_winner(self, a: str, b: str) -> dict:
        wa, wb = WUXING_ZHI[a], WUXING_ZHI[b]
        sa, sb = self._element_state(wa), self._element_state(wb)
        score = {"旺": 2, "相": 1, "休": 0, "囚": -1, "死": -2}
        base = {a: 0, b: 0}
        ben = "同类"
        if wa != wb:
            if KE[wa] == wb:
                base[a], ben = 2, a
            elif KE[wb] == wa:
                base[b], ben = 2, b
        total = {
            a: base[a] + score[sa] + (self.branches.count(a) - 1),
            b: base[b] + score[sb] + (self.branches.count(b) - 1),
        }
        winner = a if total[a] > total[b] else (b if total[b] > total[a] else "相当")
        return {"方法": "本气＋时令＋多寡（ZP-021）", "本气胜方": ben,
                "时令": {a: sa, b: sb}, "多寡": {a: self.branches.count(a), b: self.branches.count(b)},
                "综合": winner, "说明": "胜负倾向为推定，破格判定只看冲是否成立"}

    def _relations_touching(self, positions: list[str], types: set[str] | None = None) -> list[dict]:
        types = types or {"冲", "破", "害", "刑（子卯）", "三刑", "自刑"}
        return [r for r in self.relations
                if r.get("成立") and r["类型"] in types and set(positions) & set(r.get("柱位", []))]

    # ================= 月令取格（YL-001/014、CG-004、GJ-015） =================
    def _pattern_name(self, god: str, branch: str) -> str:
        lu = self.eng.data("LM-001")[self.day_gan]
        ren = self._yangren()
        if god == "比肩":
            return "建禄格" if branch == lu else "月劫格"
        if god == "劫财":
            return "阳刃格" if ren and branch == ren else "月劫格"
        return {"正官": "正官格", "七杀": "偏官格", "正财": "正财格", "偏财": "偏财格",
                "正印": "正印格", "偏印": "偏印格", "食神": "食神格", "伤官": "伤官格"}.get(god, god + "格")

    def _yangren(self) -> str | None:
        """按配置取日干羊刃位。"""
        base = self.eng.data("YR-002")[self.day_gan]
        if self.day_gan in "甲丙戊庚壬":
            return base["羊刃"]
        if self.cfg["yangren"] == "三命":
            return base["羊刃"]
        if self.cfg["yangren"] == "渊海":
            return None
        if self.cfg["yangren"] == "千里":
            return self.eng.data("ZP-011")["说三（千里·禄后）"].get(self.day_gan)
        return base["羊刃"]

    def _month_candidates(self) -> list[dict]:
        cands: list[dict] = []
        hidden_only: list[dict] = []
        for lvl, label in (("本", "本气"), ("中", "中气"), ("余", "余气")):
            for s in self.hid["月"].get(lvl, ""):
                god = ten_god(self.day_gan, s)
                trans = [p for p in ("年", "月", "时") if self.stems[p] == s]
                item = {"十神": god, "藏干": s, "层级": label, "透干": bool(trans),
                        "透干柱位": trans, "格": self._pattern_name(god, self.month_zhi),
                        "来源": "月令" + label, "依据": ["YL-001", "YL-005", "CG-004", "YL-014"]}
                if lvl == "本":
                    cands.append(item)
                elif trans:
                    cands.append(item)
                else:
                    hidden_only.append(item)
        if self.month_zhi in "辰戌丑未":
            hid_all = self._hid_stems("月")
            cands.append({"十神": "杂气", "藏干": hid_all,
                          "层级": "杂气", "透干": any(self.stems[p] in hid_all
                                                    for p in ("年", "月", "时")),
                          "透干柱位": [], "格": "杂气格", "来源": "月令杂气", "依据": ["GJ-084"]})
        self._hidden_only = hidden_only

        if not any(c["十神"] in (CAI_GODS | YIN_GODS | SHISHANG | {"正官", "七杀"}) for c in cands):
            # YL-014/GJ-015：月令无可用 → 明干有气明干取，明干无气暗中取
            target = CAI_GODS | YIN_GODS | SHISHANG | {"正官", "七杀"}
            picked = False
            for pos in ("年", "月", "时"):
                god = self.visible_gods[pos]
                if god in target:
                    cands.append({"十神": god, "藏干": self.stems[pos], "层级": "他柱明干",
                                  "透干": True, "透干柱位": [pos], "格": self._pattern_name(god, self.month_zhi),
                                  "来源": f"{pos}干明取", "依据": ["GJ-015", "YL-014"]})
                    picked = True
                    break
            if not picked:
                for pos in ("年", "日", "时"):
                    found = False
                    for lvl, label in (("本", "本气"), ("中", "中气"), ("余", "余气")):
                        for s in self.hid[pos].get(lvl, ""):
                            god = ten_god(self.day_gan, s)
                            if god in target:
                                cands.append({"十神": god, "藏干": s, "层级": "他柱暗藏",
                                              "透干": False, "透干柱位": [], "格": self._pattern_name(god, self.month_zhi),
                                              "来源": f"{pos}支{label}暗取", "依据": ["GJ-015", "YL-014"]})
                                found = True
                                break
                        if found:
                            break
                    if found:
                        break
        return cands

    def _month_summary(self, cands: list[dict]) -> dict:
        return {
            "月支": self.month_zhi,
            "藏干": {k: self._hid_stems("月", k) for k in ("本", "中", "余")},
            "本气十神": ten_god(self.day_gan, self.hid["月"]["本"][0]),
            "取格候选": [{"格": c["格"], "来源": c["来源"], "十神": c["十神"],
                          "透干": c["透干"], "透干柱位": c["透干柱位"], "依据": c["依据"]}
                         for c in cands],
            "未透中余气": [{"十神": c["十神"], "藏干": c["藏干"], "层级": c["层级"]}
                          for c in getattr(self, "_hidden_only", [])],
            "用事说明": ("藏干日数为名义值，未按交节时刻折算（CG-006 需校勘）；"
                         "中气/余气取格须透干（CG-004）。"),
            "依据": ["YL-001", "YL-005", "YL-013", "YL-014", "CG-004", "GJ-015"],
        }

    # ================= 条件核验工具 =================
    def _cai(self) -> bool:
        return any(self._has(g) for g in CAI_GODS)

    def _yin(self) -> bool:
        return any(self._has(g) for g in YIN_GODS)

    def _guansha(self) -> bool:
        return self._has("正官") or self._has("七杀")

    def _shi_shang(self) -> bool:
        return any(self._has(g) for g in SHISHANG)

    def _bi_jie(self) -> bool:
        return self._has("比肩") or self._has("劫财")

    def _official_positions(self) -> list[str]:
        """官星所在柱位（含藏根）：刑冲破害落在官星本支或透干之柱均计。"""
        return sorted({occ["来源"][:1] for occ in self._gods.get("正官", [])})

    def _combined_official(self) -> dict:
        """贪合忘官：官星透干被合（日干之合不作合去，ZP-008②）。"""
        for pos in ("年", "月", "时"):
            if self.visible_gods[pos] != "正官":
                continue
            stem = self.stems[pos]
            partner = HE_PARTNER.get(stem)
            if not partner:
                continue
            hits = [p for p in ("年", "月", "时") if p != pos and self.stems[p] == partner]
            if hits:
                adjacent = any(abs("年月日时".index(p) - "年月日时".index(pos)) == 1 for p in hits)
                return {"合去": adjacent, "说明": f"{pos}干官星{stem}被{'/'.join(hits)}干{partner}合"
                                                  + ("（紧贴，合去）" if adjacent else "（隔位，半合，力减）")}
        return {"合去": False, "说明": ""}

    def _verdict(self, conds: list[dict], breaks: list[dict]) -> tuple[str, list[str]]:
        req = [c for c in conds if c["性质"] == "必需"]
        missing = [c["条件"] for c in req if c["满足"] is False]
        hit = [b for b in breaks if b["命中"]]
        if hit:
            return "破格", missing
        if not missing:
            if any(c["性质"] == "待岁运" for c in conds):
                return "成格（岁运待验）", []
            return "成格", []
        if len(missing) <= len(req) - 1:
            return "疑似成格", missing
        return "待定", missing

    def _entry(self, name, category, source, conds, breaks, refs, note="", 用神=""):
        verdict, missing = self._verdict(conds, breaks)
        return {"格": name, "类别": category, "来源": source, "倾向": verdict,
                "成格条件": conds, "破格因素": breaks, "缺失条件": missing,
                "用神提示": 用神, "依据": refs, "备注": note, "分歧": []}

    def _assess_candidate(self, cand: dict) -> dict:
        name = cand["格"]
        if name == "正官格":
            return self._zhengguan(cand)
        if name == "偏官格":
            return self._pian_guan(cand)
        if name == "建禄格":
            return self._jianlu(cand)
        if name in ("正财格", "偏财格"):
            return self._cai_ge(cand)
        if name in ("正印格", "偏印格"):
            return self._yin_ge(cand)
        if name == "伤官格":
            return self._shang_guan(cand)
        if name == "食神格":
            return self._shi_shen(cand)
        if name == "杂气格":
            return self._zaqi(cand)
        if name == "阳刃格":
            return self._yangren_ge(cand)
        if name == "月劫格":
            return self._yuejie(cand)
        return self._entry(name, "正格", cand["来源"],
                           [C("月令取格", True, "YL-001", cand["来源"])],
                           [], cand["依据"], note="该格成破细则未逐条编码")

    # ================= 正官（GJ-010/012/013） =================
    def _zhengguan(self, cand: dict) -> dict:
        conds, breaks = [], []
        n = self._n("正官")
        conds.append(C("官星一位", n == 1, "GJ-010", f"正官共 {n} 处（GJ-014：多则成败）"))
        conds.append(C("支藏干透", cand["透干"], "GJ-012",
                       f"{cand['藏干']} {'透 '+ '/'.join(cand['透干柱位']) if cand['透干'] else '不透'}"))
        conds.append(C("日主健旺", self.strength["身旺"], "GJ-012",
                       f"身强弱判定：{self.strength['判定']}"))
        conds.append(C("财印两扶", self._cai() and self._yin(), "GJ-012",
                       f"财{'有' if self._cai() else '无'}、印{'有' if self._yin() else '无'}"
                       "（按有效十神：本气或透干）"))
        conds.append(C("不见伤煞", not self._has("伤官") and not self._has("七杀"), "GJ-012",
                       f"伤官{'有' if self._has('伤官') else '无'}、"
                       f"七杀{'有' if self._has('七杀') else '无'}"))
        conds.append(C("官不过重", not (n > 2 and not self.strength["身旺"]), "GJ-014",
                       f"官 {n} 处、身{self.strength['判定']}；官重身轻则不堪（财官满目身弱不胜）"))
        conds.append(C("常见组合·官逢财生", bool(self._visible("正财") or self._visible("偏财")),
                       "GJ-002/GJ-012", "财星透干生官（渊海『时上兼有财星，真贵人』——引文未在易藏本命中，待校）",
                       "加分"))
        conds.append(C("常见组合·官印相生", bool(self._visible("正印") or self._visible("偏印")),
                       "GJ-002/GJ-016", "印透护官生身", "加分"))
        conds.append(C("行运引至官乡", None, "GJ-012", "须岁运，第二步接入", "待岁运"))
        breaks.append(B("伤官见官", self._has("伤官"), "GJ-013",
                        "伤官务要伤尽；见官祸患（GJ-085）"))
        breaks.append(B("七杀混杂", self._has("七杀"), "GJ-013/GJ-041",
                        "官煞混杂只取财印为用（GJ-041）"))
        rel = self._relations_touching(self._official_positions())
        breaks.append(B("官星逢刑冲破害", bool(rel), "GJ-013",
                        "；".join(f"{r['类型']}{r['支']}（{'/'.join(r['柱位'])}）" for r in rel)))
        comb = self._combined_official()
        breaks.append(B("贪合忘官", comb["合去"], "GJ-013", comb["说明"]))
        breaks.append(B("劫财分福", self._has("劫财"), "GJ-013", "劫财分官星之福"))
        note = ("GJ-013 原文例『甲生酉月见卯冲、酉刑、午破、戌害』中『午破酉』不在 SSH-050 六破表"
                "（仅卯午/丑辰/子酉/未戌），本引擎破格判定不据午破酉，两说并列。"
                "护卫条件：顺时等现代体系作『财或印』即可；本库从 GJ-012 原文『财印两扶』。")
        return self._entry("正官格", "正格", cand["来源"], conds, breaks,
                           ["GJ-010", "GJ-011", "GJ-012", "GJ-013", "GJ-014", "GJ-015",
                            "ZP-021", "ZP-022", "ZP-023", "SSH-050"],
                           用神=("财印为用；身弱印轻补印、身旺官轻补官（GJ-016）" if self.strength["身旺"]
                                else "身弱宜印，忌伤官运、忌财煞旺乡（GJ-014/GJ-016）"),
                           note=note)

    # ================= 偏官（GJ-030/031/036/041/042） =================
    def _pian_guan(self, cand: dict) -> dict:
        conds, breaks = [], []
        n_sha, n_guan = self._n("七杀"), self._n("正官")
        has_zhi = self._shi_shang()
        conds.append(C("煞一位", n_sha == 1, "GJ-036", f"七杀共 {n_sha} 处；多则不佳"))
        conds.append(C("有制", has_zhi, "GJ-030",
                       "食伤制煞；无制则按七煞论" if not has_zhi else "食伤制煞"))
        conds.append(C("日主健旺＋印绶助化", self.strength["身旺"] and self._yin(), "GJ-031①",
                       f"身{self.strength['判定']}、印{'有' if self._yin() else '无'}", "加分"))
        conds.append(C("身强煞弱有财", self.strength["身旺"] and n_sha == 1 and self._cai(), "GJ-031②",
                       "身强煞弱有财则吉（GJ-032）", "加分"))
        conds.append(C("食神透制", bool(self._visible("食神")), "GJ-031③",
                       "食神透干制煞", "加分"))
        conds.append(C("阳刃配合", bool(self._yangren() and self._yangren() in self.branches), "GJ-031④",
                       "煞刃相济（YR-016/ZP-017）", "加分"))
        n_zhi = self._n("食神") + self._n("伤官")
        conds.append(C("制伏有度", n_zhi <= 2, "GJ-033",
                       f"食伤制伏 {n_zhi} 处；煞止一而制伏二三处喜煞旺地，运再制则尽法无民"))
        breaks.append(B("官煞混杂", n_guan > 0 and n_sha > 0, "GJ-036/GJ-041",
                        "略见正官则混杂反贱；只取财印为用"))
        note = "常见组合：印绶化杀（杀印相生 GJ-037）、食神制杀（GJ-031③）、羊刃驾杀（YR-016/ZP-017）。"
        if not has_zhi:
            note += "无制伏：按七煞论（GJ-030），不作偏官格；若煞重身无归、无比肩印绶，转看弃命从煞（GJ-042）。"
        if self.strength["身旺"] is False and n_sha >= 3 and not self._has("比肩") and not self._yin():
            note += " 命中弃命从煞候选条件（GJ-042）：煞重、身无归、无比肩印绶。"
        note = note.rstrip("。") + "；七杀无制者，岁运引入食神、印星可解（YS-004『煞欲制』；GJ-033/034）。"
        return self._entry("偏官格", "正格", cand["来源"], conds, breaks,
                           ["GJ-030", "GJ-031", "GJ-032", "GJ-036", "GJ-041", "GJ-042",
                            "YR-016", "ZP-017"],
                           用神=("喜印化煞、食神制煞、阳刃合煞；忌财党煞（GJ-031/GJ-032）"),
                           note=note)

    # ================= 建禄（GJ-050/051/052/054） =================
    def _jianlu(self, cand: dict) -> dict:
        conds, breaks = [], []
        lu = self.eng.data("LM-001")[self.day_gan]
        conds.append(C("月支为日干禄", self.month_zhi == lu, "GJ-050", f"{self.day_gan}禄在{lu}"))
        cai_guan_visible = any(self._visible(g) for g in (CAI_GODS | {"正官", "七杀"}))
        conds.append(C("财官透", cai_guan_visible, "GJ-050/GJ-051",
                       "财官喜透天；无财官则福薄（宜时带偏官偏财食神）"))
        n_bijie = self._n("比肩") + self._n("劫财")
        conds.append(C("劫夺不重", n_bijie < 3, "GJ-050/GJ-051",
                       f"比劫共 {n_bijie} 处；再见比肩则克妻妨父损子，劫夺重则多贫贱"))
        conds.append(C("身不宜再旺", self.strength["判定"] != "最强", "GJ-050",
                       f"身{self.strength['判定']}", "加分"))
        gj52 = self.eng.data("GJ-052").get(self.day_gan + self.month_zhi)
        if gj52:
            hit = any(gz == gj52 for _, gz in self.positions)
            conds.append(C("见指定煞取贵", hit, "GJ-052",
                           f"{self.day_gan}{self.month_zhi} 见 {gj52}（原文未明柱位，按任一柱出现核验——推定）",
                           "加分"))
        return self._entry("建禄格", "正格", cand["来源"], conds, breaks,
                           ["GJ-050", "GJ-051", "GJ-052", "GJ-053", "GJ-054"],
                           用神=("财官为用；无财官宜时带偏官偏财食神（GJ-051）"),
                           note="建禄与比肩阳刃同气（GJ-054）；行运见财运官运则发（GJ-053）。")

    # ================= 财格（GJ-080/081） =================
    def _cai_ge(self, cand: dict) -> dict:
        conds, breaks = [], []
        n_cai = self._n("正财") + self._n("偏财")
        other = "偏财" if cand["十神"] == "正财" else "正财"
        de_shi = (ten_god(self.day_gan, self.hid["月"]["本"][0]) in CAI_GODS
                  or bool(self._visible(cand["十神"])))
        conds.append(C("得时乘旺", de_shi, "GJ-080",
                       "月令本气为财，或财星透干"))
        conds.append(C("日主有力", self.strength["身旺"], "GJ-080",
                       f"身{self.strength['判定']}；财多身弱则不能任"))
        conds.append(C("财不重叠", n_cai <= 2, "GJ-080", f"财共 {n_cai} 处"))
        conds.append(C("正偏不混", not self._has(other), "GJ-080",
                       f"另见{other} {self._n(other)} 处"))
        breaks.append(B("财多身弱无印", n_cai >= 3 and not self.strength["身旺"] and not self._yin(), "GJ-080"))
        breaks.append(B("财少身强带比劫", n_cai <= 1 and self.strength["身旺"] and self._bi_jie(), "GJ-080"))
        breaks.append(B("枭夺", self._has("偏印"), "GJ-080", "偏印（枭神）夺食/盗财"))
        breaks.append(B("刃劫", self._has("劫财") or bool(self._yangren() and self._yangren() in self.branches),
                        "GJ-080", "羊刃劫财分财"))
        void_hit = [occ for g in CAI_GODS for occ in self._gods.get(g, [])
                    if occ["来源"].endswith("本气") and
                    self.branches[("年", "月", "日", "时").index(occ["来源"][0])] in self.voids]
        breaks.append(B("财落空亡", bool(void_hit), "GJ-080", "财星所在支落旬空"))
        ru_mu = [occ for g in CAI_GODS for occ in self._gods.get(g, [])
                 if self._stage_of(occ["字"],
                                   self.branches[("年", "月", "日", "时").index(occ["来源"][0])]) == "墓"]
        breaks.append(B("财入墓", bool(ru_mu), "GJ-080", "库空/财入墓则不发"))
        conds.append(C("先财后印", self._order_ok("财", "印"), "GJ-080",
                       "先财后印为福、先印后财为辱", "加分"))
        conds.append(C("常见组合·食伤生财", self._shi_shang(), "GJ-080/081",
                       "食伤生财、身旺任财", "加分"))
        return self._entry(cand["格"], "正格", cand["来源"], conds, breaks,
                           ["GJ-080", "GJ-081"],
                           用神=("身旺用财、喜伤官生财；身弱用印（GJ-080）"),
                           note="正财宜藏忌露；偏财忌兄弟分夺、落空亡（GJ-080/GJ-081）。")

    def _order_ok(self, first_group: str, second_group: str) -> bool:
        """按年→月→日→时取天干十神组，判断先后。"""
        seq = [self.visible_gods[p] for p in ("年", "月")]
        f = {"财": CAI_GODS, "印": YIN_GODS}[first_group]
        s = {"财": CAI_GODS, "印": YIN_GODS}[second_group]
        for i, g in enumerate(seq):
            if g in f:
                return any(x in s for x in seq[i + 1:])
        return False

    # ================= 印绶（GJ-082） =================
    def _yin_ge(self, cand: dict) -> dict:
        conds, breaks = [], []
        has_root = any(self._has(g) for g in YIN_GODS) and any(
            occ["来源"].endswith(("本气", "中气", "余气")) for g in YIN_GODS for occ in self._gods.get(g, []))
        conds.append(C("印有根", has_root, "GJ-082", "印藏支有根；无根忌财"))
        conds.append(C("官煞生印", self._guansha(), "GJ-082", "印赖官生；喜七煞不可多", "加分"))
        conds.append(C("天月德", self._has_tiande() or self._has_yuede(), "GJ-082",
                       "印绶喜天月德", "加分"))
        conds.append(C("身弱用印", not self.strength["身旺"], "GJ-082",
                       f"身{self.strength['判定']}", "加分"))
        po_yin = self._cai() and not self._guansha()
        breaks.append(B("财破印", po_yin, "GJ-082",
                        "有官有财则财生官、官生印，不作破论" if self._cai() and self._guansha() else "财透无官通关"))
        bad = [occ for g in YIN_GODS for occ in self._gods.get(g, [])
               if self._stage_of(occ["字"], self.branches[("年", "月", "日", "时").index(occ["来源"][0])])
               in ("死", "绝", "墓")]
        breaks.append(B("印坐死绝墓地", bool(bad), "GJ-082", "印星坐支逢死绝墓"))
        return self._entry(cand["格"], "正格", cand["来源"], conds, breaks,
                           ["GJ-082", "WG2-022"],
                           用神=("喜官煞、天月德；忌财破印、忌入财乡（GJ-082）"),
                           note="印绶行运忌变合，三合成伤/财/煞局最不吉（WG2-022）。")

    # ================= 伤官（GJ-085） =================
    def _shang_guan(self, cand: dict) -> dict:
        conds, breaks = [], []
        ji_guan = self.day_gan in self.cfg["shangugan_ji_guan"]
        conds.append(C("伤尽（不见正官）", not self._has("正官"), "GJ-085",
                       "伤官务要伤尽方作贵"))
        conds.append(C("身旺", self.strength["身旺"], "GJ-085", "伤尽而身旺财旺印旺则贵", "加分"))
        conds.append(C("财旺", self._n("正财") + self._n("偏财") >= 2, "GJ-085", "伤官要财", "加分"))
        conds.append(C("印旺", self._n("正印") + self._n("偏印") >= 2, "GJ-085", "伤官佩印", "加分"))
        breaks.append(B("伤官见官", self._has("正官") and ji_guan, "GJ-085",
                        "火土伤官忌见官；金水木伤官不忌（按日干丙丁为火土伤官——推定）"
                        if not ji_guan else "火土伤官见官，祸患百端"))
        breaks.append(B("身弱财旺", not self.strength["身旺"] and self._n("正财") + self._n("偏财") >= 2,
                        "GJ-085", "身弱财旺主徒流死亡"))
        use = "身旺用财、身弱用印；用印去财、用财去印（GJ-085）"
        return self._entry("伤官格", "正格", cand["来源"], conds, breaks, ["GJ-085"],
                           用神=use,
                           note="伤官见官是否成祸，按日干分：火土伤官忌见官，金水木伤官不忌（GJ-085 原文；"
                                "日干分属为推定）。")

    # ================= 食神（GJ-086） =================
    def _shi_shen(self, cand: dict) -> dict:
        conds, breaks = [], []
        food_occs = self._eff("食神")
        shengwang = False
        for occ in food_occs:
            branch = self.pillars[occ["来源"][0]][1]
            if self._stage_of(occ["字"], branch) not in ("衰", "病", "死", "绝"):
                shengwang = True
                break
        conds.append(C("食神生旺", shengwang, "GJ-086",
                       f"食神{len(food_occs)}处；按食神自身十二宫不逢衰病死绝"))
        food_pos = [occ["来源"][0] for occ in self._gods.get("食神", [])]
        food_rel = self._relations_touching(food_pos, {"冲", "破"})
        conds.append(C("无冲破", not food_rel, "GJ-086",
                       "；".join(f"{r['类型']}{r['支']}" for r in food_rel) or "无冲无破"))
        conds.append(C("常见组合·食神生财", self._cai(), "GJ-086",
                       "食神生财为养命之源（身旺任财）", "加分"))
        breaks.append(B("倒食（枭神夺食）", self._has("偏印"), "GJ-086"))
        void_food = [p for p in food_pos if self.branches[("年", "月", "日", "时").index(p)] in self.voids]
        breaks.append(B("食神空亡", bool(void_food), "GJ-086"))
        mu = [occ for occ in self._gods.get("食神", [])
              if self._stage_of(occ["字"],
                                self.branches[("年", "月", "日", "时").index(occ["来源"][0])]) == "墓"]
        breaks.append(B("食神入墓", bool(mu), "GJ-086"))
        breaks.append(B("身衰枭旺", not self.strength["身旺"] and self._n("偏印") >= 2, "GJ-086"))
        breaks.append(B("重见变伤官", self._n("食神") >= 2, "GJ-086",
                        f"食神 {self._n('食神')} 处，重见则变伤官"))
        return self._entry("食神格", "正格", cand["来源"], conds, breaks, ["GJ-086"],
                           用神="食神生旺为寿星爵星；食多宜印运、食少不宜印运（GJ-086）",
                           note="食神忌倒食、空亡、入墓、身衰枭旺、重见（GJ-086）。")

    # ================= 杂气（GJ-084） =================
    def _zaqi(self, cand: dict) -> dict:
        conds, breaks = [], []
        hidden = self._hid_stems("月")
        trans = [p for p in ("年", "月", "时") if self.stems[p] in hidden]
        conds.append(C("透", bool(trans), "GJ-084", f"透干柱位：{trans or '无'}"))
        rel = self._relations_touching(["月"])
        conds.append(C("喜冲刑", bool(rel), "GJ-084",
                       "；".join(f"{r['类型']}{r['支']}" for r in rel) or "无冲刑"))
        conds.append(C("身不弱", self.strength["身旺"], "GJ-084", f"身{self.strength['判定']}"))
        ku_guan = [s for s in hidden if ten_god(self.day_gan, s) in {"正官", "七杀", "正财", "偏财"}]
        conds.append(C("库中财官", bool(ku_guan), "GJ-084",
                       f"库藏：{''.join(ku_guan) or '无财官'}", "加分"))
        breaks.append(B("压伏身弱", not self.strength["身旺"], "GJ-084"))
        breaks.append(B("冲刑太过气散", len(rel) >= 2, "GJ-084", "冲刑太过则气散"))
        return self._entry("杂气格", "正格", "月令杂气", conds, breaks, ["GJ-084"],
                           note="库中有财主丰厚、库头财主钱谷之任（GJ-084）。")

    # ================= 阳刃 / 月劫（YR-012/016、GJ-054） =================
    def _yangren_ge(self, cand: dict) -> dict:
        conds = [C("月支为日干羊刃", self.month_zhi == self._yangren(), "YR-012",
                   f"按{self.cfg['yangren']}说取刃位")]
        conds.append(C("煞刃相济", self._has("七杀"), "YR-016/ZP-017",
                       "杀无刃不显，刃无杀不威", "加分"))
        conds.append(C("印绶", self._yin(), "YR-016", "阳刃喜偏官印绶", "加分"))
        breaks = [B("反吟伏吟", False, "YR-016", "岁运项，第二步接入"),
                  B("魁罡", self.day_gz in self.eng.data("GJ-116"), "YR-016"),
                  B("三合", any(r["类型"].startswith("局合") for r in self.relations), "YR-016")]
        return self._entry("阳刃格", "正格", cand["来源"], conds, breaks,
                           ["YR-012", "YR-016", "ZP-017", "ZP-011"],
                           用神="喜偏官七杀、印绶；忌反伏魁罡三合（YR-016）",
                           note=f"羊刃起法采用『{self.cfg['yangren']}』说；三说并列见根部分歧。")

    def _yuejie(self, cand: dict) -> dict:
        conds = [C("月令比劫非禄非刃", True, "GJ-054")]
        conds.append(C("财官为用", any(self._visible(g) for g in (CAI_GODS | {"正官", "七杀"})),
                       "GJ-054", "与建禄同气，取用大略相同"))
        conds.append(C("劫夺不重", self._n("比肩") + self._n("劫财") < 3, "GJ-050/GJ-054"))
        return self._entry("月劫格", "正格", cand["来源"], conds, [],
                           ["GJ-054"], note="比劫不能成格（千里六神篇）；按建禄同气取用。")

    # ================= 神煞辅助 =================
    def _has_yuede(self) -> bool:
        group = _branch_group(self.month_zhi)
        de = self.eng.data("SSH-007")[group]
        return any(self.stems[p] == de for p in ("年", "月", "时"))

    def _has_tiande(self) -> bool:
        gong = GONG[self.month_zhi]
        de = self.eng.data("SSH-008")[gong]
        return any(self.stems[p] == de for p in ("年", "月", "时"))

    # ================= 专旺 / 从格 / 外格 =================
    def _special_entries(self) -> list[dict]:
        out: list[dict] = []
        n_cai = self._n("正财") + self._n("偏财")
        n_yin = self._n("正印") + self._n("偏印")
        n_bijie = self._n("比肩") + self._n("劫财")
        n_guan, n_sha = self._n("正官"), self._n("七杀")
        n_shi_shang = self._n("食神") + self._n("伤官")

        # 专旺五格（GJ-060..064）
        day = self.day_gan
        checks = [
            ("曲直格", day in "甲乙" and all(b in self.branches for b in "亥卯未"),
             [("亥卯未全", all(b in self.branches for b in "亥卯未"), "GJ-060"),
              ("柱有亥（带印）", "亥" in self.branches, "GJ-060"),
              ("无亥须见金土", ("亥" in self.branches) or self._has("正官") or self._has("七杀") or self._cai(), "GJ-060")],
             "GJ-060"),
            ("炎上格", day in "丙丁" and all(b in self.branches for b in "寅午戌"),
             [("寅午戌全", all(b in self.branches for b in "寅午戌"), "GJ-061"),
              ("柱有寅", "寅" in self.branches, "GJ-061")], "GJ-061"),
            ("从革格", day in "庚辛" and all(b in self.branches for b in "巳酉丑"),
             [("巳酉丑全", all(b in self.branches for b in "巳酉丑"), "GJ-062")], "GJ-062"),
            ("润下格", day in "壬癸" and all(b in self.branches for b in "申子辰"),
             [("申子辰全", all(b in self.branches for b in "申子辰"), "GJ-063")], "GJ-063"),
            ("稼穑格", day in "戊己" and self.month_zhi in "辰戌丑未",
             [("四季月生", self.month_zhi in "辰戌丑未", "GJ-064")], "GJ-064"),
        ]
        for name, hit, conds_spec, ref in checks:
            if not hit:
                continue
            conds = [C(c, m, r) for c, m, r in conds_spec]
            out.append(self._entry(name, "专旺", "三合局/月令", conds, [], [ref, "YL-010"],
                                   note="专旺格须三合局全；破格条件原文从简，未逐条编码。"))
        # 金白水清 GJ-066（核心结构不成立则不列，避免噪声）
        if self.day_gz in ("庚申", "辛酉") and self.season == "秋" and self.pillars["时"][1] in "亥子":
            conds = [C("日柱庚申/辛酉", True, "GJ-066"),
                     C("生秋月", True, "GJ-066"),
                     C("时支亥子", True, "GJ-066"),
                     C("无刑冲破害", not self._relations_touching(["日", "时", "年", "月"]), "GJ-066")]
            out.append(self._entry("金白水清", "专旺", "日柱＋时支", conds, [], ["GJ-066"]))
        # 木火交辉 GJ-067（须生春夏、柱无金水、时有木火，方列）
        if self.day_gz in ("甲戌", "甲午", "甲寅", "丙午", "丙寅", "丙戌"):
            no_metal_water = not any(WUXING_ZHI[b] in ("金", "水") for b in self.branches)
            fire_time = WUXING_ZHI[self.pillars["时"][1]] in ("木", "火")
            if self.season in ("春", "夏") and no_metal_water and fire_time:
                conds = [C("日柱合原文六日", True, "GJ-067"),
                         C("生春夏", True, "GJ-067"),
                         C("柱无金水", True, "GJ-067"),
                         C("时有木火", True, "GJ-067")]
                out.append(self._entry("木火交辉", "专旺", "日柱＋时支", conds, [], ["GJ-067"],
                                       note="木秀无火则不成局（GJ-067）。"))
        # 从财 GJ-065 / 从儿 ZP-002 / 从旺 ZP-003 / 从强 ZP-004 / 从官 ZP-005 / 从煞 GJ-042
        if (not self.strength["身旺"] and n_cai >= 3 and not self._yin()
                and n_guan + n_sha <= 1):
            out.append(self._entry("从财格", "从格", "财多身弱",
                                   [C("日主无气", True, "GJ-065"),
                                    C("财多成势", n_cai >= 3, "GJ-065", f"财 {n_cai} 处"),
                                    C("无印生身", not self._yin(), "GJ-065"),
                                    C("官杀不夺财势", n_guan + n_sha <= 1, "GJ-065",
                                      f"官杀 {n_guan + n_sha} 处；从财忌官杀破格（阈值为推定）")],
                                   [B("逢根气破格", self._has("比肩") or self._yin(), "GJ-065")],
                                   ["GJ-065"], 用神="行财旺运吉，逢根气破格（GJ-065）",
                                   note="从财的官杀≤1 门槛为工程口径（推定）；原文只言日主无气、财多成势。"))
        if not self.strength["身旺"] and not self._yin() and n_shi_shang >= 4:
            out.append(self._entry("从儿格", "从格", "伤食成势",
                                   [C("日主衰弱", True, "ZP-002"),
                                    C("无印生身", not self._yin(), "ZP-002"),
                                    C("伤食当旺", n_shi_shang >= 4, "ZP-002", f"食伤 {n_shi_shang} 处")],
                                   [], ["ZP-002"], 用神="用伤食，喜财，忌印与官杀（ZP-002）"))
        n_bijie_pos = self._n_pos("比肩") + self._n_pos("劫财")
        n_yin_pos = self._n_pos("正印") + self._n_pos("偏印")
        n_guan_pos = self._n_pos("正官")
        n_sha_pos = self._n_pos("七杀")
        if n_bijie_pos >= 4 and not self._guansha():
            out.append(self._entry("从旺格", "从格", "比劫成势",
                                   [C("四柱比劫成势", True, "ZP-003", f"比劫占 {n_bijie_pos} 柱"),
                                    C("无官杀之制", not self._guansha(), "ZP-003")],
                                   [], ["ZP-003"], 用神="用比劫（ZP-003）", note="从旺门槛（比劫占四柱）为工程口径（推定）。名目分歧：顺时等现代体系以『从强'』指日主极强、另立『从弱』名目；本引擎从千里，以『从旺』名比劫极旺。"))
        if n_bijie_pos + n_yin_pos >= 4 and n_yin_pos >= 1 and not self._cai() and not self._guansha():
            out.append(self._entry("从强格", "从格", "印比两旺",
                                   [C("印比两旺", True, "ZP-004", f"印比占 {n_bijie_pos + n_yin_pos} 柱"),
                                    C("无官杀、财星", not self._cai() and not self._guansha(), "ZP-004")],
                                   [], ["ZP-004"], 用神="用印比（ZP-004）", note="从强门槛（印比占四柱且印有气）为工程口径（推定）。名目分歧：千里『从强'』＝印比旺极、以印为重；顺时等现代体系『从强』指日主极强、另立『从弱』——两套名目并存，本引擎从千里。"))
        if not self.strength["身旺"] and not self._yin() and n_guan_pos >= 3 and n_sha_pos == 0:
            out.append(self._entry("从官格", "从格", "官星成势",
                                   [C("日主衰弱", True, "ZP-005"),
                                    C("无印滋身", not self._yin(), "ZP-005"),
                                    C("官旺而多（纯官）", n_guan_pos >= 3 and n_sha_pos == 0, "ZP-005",
                                      f"正官占 {n_guan_pos} 柱、七杀占 {n_sha_pos} 柱")],
                                   [], ["ZP-005"], 用神="喜财官滋生，忌印泄官、劫比抗官（ZP-005）", note="从官门槛（官占三柱、无印）为工程口径（推定）。"))
        if not self.strength["身旺"] and n_sha_pos >= 3 and not self._has("比肩") and not self._yin():
            out.append(self._entry("弃命从煞", "从格", "煞重身无归",
                                   [C("煞重", True, "GJ-042", f"七杀占 {n_sha_pos} 柱"),
                                    C("身无归、无比肩印绶", True, "GJ-042")],
                                   [B("阳木不从", self.day_gan == "甲", "GJ-042")],
                                   ["GJ-042"], 用神="行煞旺及财乡；忌扶身与煞为敌（GJ-042）", note="从煞门槛（煞占三柱、无比肩印）为工程口径（推定）。"))

        # 机械外格：命中即列，附原文条件；有成破细则者核验
        for c in self.eng.pattern_candidates(self.pillars, self.hid):
            name = c["格"]
            if not c["命中"]:
                continue
            if name in {"建禄格", "阳刃格"} or name.endswith("（候）"):
                continue
            out.append(self._outer_entry(name, c))

        # 外部对照补录外格（WG2-026～034，2026-10-28）
        out += self._wg2_extra()
        return out

    def _wg2_extra(self) -> list[dict]:
        out: list[dict] = []
        # 天福贵人（WG2-026）：正官之禄位见支，年/日干双口径
        for base in ("年", "日"):
            gan = self.stems[base]
            guan = self.eng.data("SS-006")[gan]["正官"]
            lu = self.eng.data("LM-001")[guan]
            if lu in self.branches:
                conds = [C("官星禄位见支", True, "WG2-026",
                           f"{base}干{gan}官{guan}，禄{lu}见支"),
                         C("得福神助（印/食）", self._yin() or self._has("食神"),
                           "WG2-026", "更得福神助之", "加分"),
                         C("身旺有气", self.strength["身旺"], "WG2-026",
                           f"身{self.strength['判定']}", "加分")]
                out.append(self._entry("天福贵人", "外格", f"{base}干官禄同现", conds,
                                       [B("伤官见官", self._has("伤官"), "WG2-026/GJ-013")],
                                       ["WG2-026", "LM-001", "SS-006"]))
        # 天元作禄（WG2-027）
        for group, days in self.eng.data("WG2-027").items():
            if self.day_gz in days:
                rel = self._relations_touching(["日"])
                out.append(self._entry("天元作禄", "外格", group,
                                       [C("日柱合原文五组", True, "WG2-027", group)],
                                       [B("刑冲破害", bool(rel), "WG2-027", "大忌刑冲破害")],
                                       ["WG2-027"], note="别名『天元坐禄』；须身贵相亭。"))
        # 禄库逢财（WG2-028）
        for group, day in self.eng.data("WG2-028").items():
            if self.day_gan in group and any(gz == day for _, gz in self.positions):
                rel = self._relations_touching([p for p, gz in self.positions if gz == day])
                out.append(self._entry("禄库逢财", "外格", group,
                                       [C(f"{group}逢{day}", True, "WG2-028")],
                                       [B("冲破", bool(rel), "WG2-028", "无冲破为贵")],
                                       ["WG2-028"]))
        # 相刑遇贵（WG2-029）
        xg = self.eng.data("WG2-029")
        for rel in self.relations:
            if rel["类型"] not in ("三刑", "刑（子卯）") or not rel.get("成立"):
                continue
            zs = set(rel["支"])
            key = "子卯" if zs == {"子", "卯"} else ("丑戌未" if zs & {"丑", "戌"} else "寅巳申")
            gui = xg[key]["贵人"]
            stem_hit = [f"{p}干{s}" for p, s in self.stems.items()
                        if s in gui and p != "日"]
            if stem_hit:
                out.append(self._entry("相刑遇贵", "外格", f"{key}刑",
                                       [C("刑见贵人干", True, "WG2-029",
                                          f"{rel['类型']}{rel['支']}；{'/'.join(stem_hit)}为贵人（{xg[key]['断']}）")],
                                       [], ["WG2-029", "ZP-022"],
                                       note="刑位对应为推定；主执法兵刑权势。"))
        # 三合遇贵（WG2-030，暗官格）
        guan_god = self.eng.data("SS-006")[self.day_gan]["正官"]
        guan_wx = {"甲": "金", "乙": "金", "丙": "水", "丁": "水", "戊": "木",
                   "己": "木", "庚": "火", "辛": "火", "壬": "土", "癸": "土"}.get(guan_god)
        if guan_wx in ("金", "木", "水", "火"):
            sanhe = {"金": "巳酉丑", "木": "亥卯未", "火": "寅午戌", "水": "申子辰"}[guan_wx]
            if all(b in self.branches for b in sanhe) \
                    and guan_god not in self.stems.values():
                out.append(self._entry("三合遇贵", "外格", "三合官局",
                                       [C("官干不透＋官局三合全", True, "WG2-030",
                                          f"官{guan_god}不透，{sanhe}全")],
                                       [], ["WG2-030", "ZP-006"], note="又名暗官格，主财谷。"))
        # 金木间隔（WG2-031）
        if self.day_gan in "甲乙":
            g_pos = ["年月日时".index(p) for p, s in self.stems.items() if s == "庚"]
            if len(g_pos) >= 2 and any(g_pos[j] - g_pos[i] >= 2
                                       for i in range(len(g_pos)) for j in range(i + 1, len(g_pos))):
                out.append(self._entry("金木间隔", "外格", "两庚间隔",
                                       [C("甲乙日两庚间隔", True, "WG2-031",
                                          f"庚在{'年月日时'[g_pos[0]]}与{'年月日时'[g_pos[-1]]}")],
                                       [], ["WG2-031"], note="木无金不成器；成器主贵。"))
        # 金火相成（WG2-032）
        if self.day_gan in "庚辛":
            fire = sum(1 for s in self.stems.values() if s in "丙丁") \
                + sum(1 for b in self.branches if b in ("巳", "午"))
            metal = sum(1 for p, s in self.stems.items() if s in "庚辛" and p != "日")
            if fire >= 2 and metal >= 2:
                out.append(self._entry("金火相成", "外格", "金火两停",
                                       [C("金火两停", True, "WG2-032",
                                          f"金{metal}（他柱干）、火{fire}")],
                                       [B("丑字损模", "丑" in self.branches, "WG2-032/GJ-068")],
                                       ["WG2-032", "GJ-068"]))
        # 水火既济（WG2-033）
        if self.day_gan == "丙" and self.pillars["日"][1] == "子":
            out.append(self._entry("水火既济", "外格", "丙子坐官",
                                   [C("丙日坐子（癸正官坐支）", True, "WG2-033",
                                     "广义为推定，原文仅丙子例")],
                                   [], ["WG2-033"], note="互换见官，主兵权万里。"))
        # 井栏叉格（WG2-034）
        if self.day_gz in ("庚子", "庚申") and self.pillars["时"] == "庚辰":
            shuizi = sum(1 for b in self.branches if b in "申子辰")
            no_fire = not any(s in "丙丁" for s in self.stems.values()) \
                and not any(b in ("巳", "午") for b in self.branches)
            conds = [C("庚日庚辰时", True, "WG2-034"),
                     C("申子辰会局（见二支以上）", shuizi >= 2, "WG2-034",
                       f"见 {shuizi} 支（推定）"),
                     C("柱无丙丁巳午", no_fire, "WG2-034")]
            out.append(self._entry("井栏叉格", "外格", "庚日庚辰时", conds, [],
                                   ["WG2-034", "ZP-018"],
                                   note="遥合巳中丙戊为官；庚辰日以魁罡论，不入本格。"))
        return out

    def _outer_entry(self, name: str, c: dict) -> dict:
        rule = c["规则"]
        conds = [C("命中条件", True, rule, c.get("条件", ""))]
        breaks: list[dict] = []
        if name == "日贵":
            rel = self._relations_touching(["日"])
            breaks.append(B("刑冲破害", bool(rel), "GJ-117", "日贵最怕刑冲破害"))
            breaks.append(B("空亡", self.branches[2] in self.voids, "GJ-117"))
        elif name == "日德":
            rel = self._relations_touching(["日"])
            breaks.append(B("刑冲破害", bool(rel), "GJ-118"))
            breaks.append(B("空亡", self.branches[2] in self.voids, "GJ-118"))
            breaks.append(B("魁罡", self.day_gz in self.eng.data("GJ-116"), "GJ-118"))
        elif name == "魁罡":
            breaks.append(B("见财官", self._cai() or self._guansha(), "GJ-116", "见财官立祸"))
            breaks.append(B("刑冲重临", bool(self._relations_touching(["日"])), "GJ-116"))
        elif name == "金神格":
            conds.append(C("要制伏", self._shi_shang() or self._has("七杀"), "ZP-001", "食伤制或杀刃", "加分"))
            water = (sum(1 for b in self.branches if WUXING_ZHI[b] == "水")
                     + sum(1 for s in self.stems.values() if s in "壬癸"))
            breaks.append(B("水乡", water >= 4, "ZP-001", f"水字 {water} 处；金神惧水乡"))
        elif name == "六乙鼠贵":
            breaks.append(B("午冲", "午" in self.branches, "GJ-110"))
            breaks.append(B("丑绊", "丑" in self.branches, "GJ-110"))
            breaks.append(B("官煞显露", self._has("正官") or self._has("七杀"), "GJ-110"))
        elif name == "六阴朝阳":
            breaks.append(B("午冲", "午" in self.branches, "GJ-109"))
            breaks.append(B("丑绊", "丑" in self.branches, "GJ-109"))
            breaks.append(B("丙巳填实", "丙" in self.stems.values() or "巳" in self.branches, "GJ-109"))
        elif name == "日禄归时":
            conds.append(C("柱无官星为正", not self._guansha(), "GJ-111"))
        elif name == "飞天禄马":
            breaks.append(B("官星显露", self._has("正官") or self._has("七杀"), "GJ-121"))
            breaks.append(B("合神羁绊", any(r["类型"].startswith("六合") for r in self.relations), "GJ-121"))
        elif name == "倒冲禄":
            breaks.append(B("官星显露", self._has("正官") or self._has("七杀"), "GJ-122"))
        note = "外格成破细则原文从简；未编码项仅报命中，须人工复核。"
        if name in ("飞天禄马", "倒冲禄", "冲合禄马"):
            note += " 渊海斥此类为『伤官析而为之、妄立格局』（ZP-018），两说并列。"
        return self._entry(name, "外格", "机械命中", conds, breaks,
                           [rule, "ZP-018"] if name in ("飞天禄马", "倒冲禄") else [rule], note=note)

    # ================= 用神（多因子：从化→调候→格神/相神→扶抑→病药） =================
    def _group_count(self, group: str) -> int:
        return sum(self._n(g) for g in GOD_GROUPS[group])

    def _group_or_god(self, name: str) -> str | None:
        if name in GOD_GROUPS:
            return self._pick_group_god(name)
        return name if name in GOD_RULE_NAMES else None

    def _element_group(self, element: str) -> str:
        d = WUXING[self.day_gan]
        if element == d:
            return "比劫"
        if SHENG_WO[d] == element:
            return "印"
        if SHENG[d] == element:
            return "伤食"
        if KE_WO[d] == element:
            return "官杀"
        if KE[d] == element:
            return "财"
        raise KeyError(element)

    def _element_counts(self) -> dict[str, int]:
        from collections import Counter
        cnt: Counter = Counter()
        for p in ("年", "月", "日", "时"):
            cnt[WUXING[self.stems[p]]] += 1
        for p in ("年", "月", "日", "时"):
            cnt[WUXING_ZHI[self.pillars[p][1]]] += 1
        return dict(cnt)

    def _diao_hou(self) -> dict:
        el = WUXING[self.day_gan]
        rid = {"木": "J4-005", "火": "J4-006", "土": "J4-007",
               "金": "J4-008", "水": "J4-009"}[el]
        row = (self.eng.data(rid).get("逐月喜忌") or {}).get(self.month_zhi)
        if not row:
            return {"需求": False, "说明": f"{el}日{self.month_zhi}月无可查调候行"}
        xi, ji = row.get("喜", []), row.get("忌", [])
        cnt = self._element_counts()
        xi_n = sum(cnt.get(e, 0) for e in xi)
        ji_n = sum(cnt.get(e, 0) for e in ji)
        severe = bool(ji) and ji_n >= 2 and xi_n <= 1
        god = self._pick_group_god(self._element_group(xi[0])) if xi else None
        return {
            "需求": severe, "日主五行": el, "月支": self.month_zhi,
            "喜": xi, "忌": ji, "喜数": xi_n, "忌数": ji_n,
            "五行分布": cnt, "调候神": god, "依据": [rid, "ZP-029"],
            "说明": (f"{el}日{self.month_zhi}月：喜{xi}、忌{ji}（{rid}）；"
                     f"原局喜{xi_n}、忌{ji_n}" + ("；忌神成势，调候为急（ZP-029）" if severe
                                                  else "；调候需求不显著")),
        }

    def _cong_candidates(self, patterns: list[dict]) -> list[dict]:
        """从化：从格/专旺以所从之神为用。"""
        mapping = {"从旺格": "比劫", "从强格": "印", "从儿格": "伤食", "从官格": "正官",
                   "弃命从煞": "七杀", "从财格": "财",
                   "曲直格": "比劫", "炎上格": "比劫", "从革格": "比劫",
                   "润下格": "比劫", "稼穑格": "比劫"}
        out = []
        for e in patterns:
            if e["格"] not in mapping:
                continue
            if not (e["倾向"].startswith("成格") or e["倾向"] == "疑似成格"):
                continue
            group = mapping[e["格"]]
            god = self._group_or_god(group)
            if not god:
                continue
            out.append({"神": god, "角色": "从化神", "优先级": 1, "来源": e["格"],
                        "有气": self._n(god) > 0, "依据": e["依据"] + ["ZP-029"],
                        "说明": f"命入{e['格']}（{e['倾向']}），以所从之神为用（{group}）"})
        return out

    def _pattern_candidates_for_yongshen(self, patterns: list[dict],
                                         month_cands: list[dict]) -> list[dict]:
        """格神（格局派月令用神）＋相神（格之所需）。"""
        needs = {"正官格": ["财", "印"], "偏官格": ["食伤", "印"],
                 "建禄格": ["官杀", "财", "食神"], "月劫格": ["官杀", "财", "食神"],
                 "阳刃格": ["官杀", "印"], "正财格": ["食神"], "偏财格": ["食神"],
                 "正印格": ["官杀"], "偏印格": ["官杀"], "食神格": ["食神"],
                 "伤官格": ["财", "印"], "杂气格": ["官杀", "财"]}
        out = []
        target = {"正官", "七杀", "正财", "偏财", "正印", "偏印", "食神", "伤官"}
        for c in month_cands:
            if c["十神"] not in target:
                continue
            name = self._pattern_name(c["十神"], self.month_zhi)
            e = next((x for x in patterns if x["格"] == name), None)
            broken = e is not None and e["倾向"] == "破格"
            primary = c["层级"] == "本气"
            out.append({"神": c["十神"], "角色": "格神", "优先级": 3,
                        "降级": 0 if (primary and not broken) else 1,
                        "来源": f"月令（格局派用神·{c['来源']}）", "有气": self._n(c["十神"]) > 0,
                        "依据": ["YL-001", "GJ-001"] + (["GJ-012"] if broken else []),
                        "说明": f"月令{c['藏干']}为{c['十神']}（{c['来源']}）"
                                + ("；格局破格，降级备查" if broken else "")})
            for need in needs.get(name, []):
                god = self._group_or_god(need)
                if god:
                    out.append({"神": god, "角色": "相神", "优先级": 4,
                                "来源": f"{name}所需（{need}）", "有气": self._n(god) > 0,
                                "依据": ["GJ-002"] + (["GJ-012"] if name == "正官格" else []),
                                "说明": f"{name}以{need}为相神（GJ-002 取用六法）"})
        return out

    def _bing_yao(self) -> list[dict]:
        """病药：SS-004 四怕 → 病神与药神。"""
        checks = [
            ("官怕伤", "正官", "伤官", "印", "官被伤，以印制伤护官"),
            ("财怕劫", "财", "劫财", "官杀", "财被劫，以官杀制劫护财"),
            ("印怕财", "印", "财", "比劫", "印被财破，以比劫制财存印"),
            ("食怕枭", "食神", "偏印", "财", "食被枭夺，以财制枭护食"),
        ]
        out = []
        for name, victim, offender, medicine, why in checks:
            v, o = self._group_or_god(victim), self._group_or_god(offender)
            if v and o and self._n(v) > 0 and self._n(o) > 0:
                med = self._group_or_god(medicine)
                out.append({"神": med, "角色": "病药神", "优先级": 5, "来源": name,
                            "有气": bool(med and self._n(med) > 0),
                            "依据": ["SS-004", "SS-007"],
                            "说明": f"{why}（病：{v}见{o}）"})
        return out

    def _yongshen(self, month_cands: list[dict], patterns: list[dict]) -> dict:
        cands: list[dict] = []
        cands += self._cong_candidates(patterns)                      # ① 从化
        dh = self._diao_hou()                                         # ② 调候
        if dh.get("需求") and dh.get("调候神"):
            cands.append({"神": dh["调候神"], "角色": "调候神", "优先级": 2, "来源": "调候",
                          "有气": self._n(dh["调候神"]) > 0,
                          "依据": dh["依据"], "说明": dh["说明"]})
        cands += self._pattern_candidates_for_yongshen(patterns, month_cands)  # ③ 格神/相神
        y27 = self._yongshen_27()                                     # ④ 扶抑
        cands.append({"神": y27["神"], "角色": "扶抑神", "优先级": 4, "来源": y27["取法"],
                      "有气": self._n(y27["神"]) > 0, "依据": ["ZP-028", "ZP-025"],
                      "说明": y27["说明"]})
        cands += self._bing_yao()                                     # ⑤ 病药

        # 流派优先级：调候优先 / 格局优先（配置项）
        order = YONGSHEN_ORDER.get(self.cfg.get("yongshen_order", "调候优先"),
                                   YONGSHEN_ORDER["调候优先"])
        for c in cands:
            if c.get("角色") in order:
                c["优先级"] = order[c["角色"]] + c.get("降级", 0)
        cands.sort(key=lambda c: (c["优先级"], 0 if c.get("有气") else 1))
        # 去重（同神保留优先级最高者）
        seen, uniq = set(), []
        for c in cands:
            if c["神"] in seen:
                continue
            seen.add(c["神"])
            uniq.append(c)
        top = uniq[0] if uniq else {"神": "待定", "角色": "无", "优先级": 9}
        same_pri = [c for c in uniq if c["优先级"] == top["优先级"]]
        if top["优先级"] <= 2 and len(same_pri) == 1 and top.get("有气"):
            conf = "高"
        elif top["优先级"] <= 3 and len(same_pri) == 1:
            conf = "中"
        else:
            conf = "低"
        note = top.get("说明", "")
        if top.get("有气") is False:
            note += "；原局该神缺气，用神待行运补（降低置信）"
        alts = [c for c in uniq[1:] if c["优先级"] == top["优先级"]]
        if not alts:
            alts = uniq[1:2]
        ding = {"神": top["神"], "主法": top.get("角色", "") + "｜" + top.get("来源", ""),
                "置信": conf, "备选": [c["神"] for c in alts[:3]], "说明": note}
        return {
            "定神": ding,
            "候选": uniq,
            "因子分析": {"从化": [c for c in uniq if c["角色"] == "从化神"],
                        "调候": dh,
                        "格局": [c for c in uniq if c["角色"] in ("格神", "相神")],
                        "扶抑": y27,
                        "病药": [c for c in uniq if c["角色"] == "病药神"]},
            "五神多寡": {g: self._group_count(g) for g in GOD_GROUPS},
            "配套六法": self._liufa(top["神"]),
            "行运喜忌": dict(YONGSHEN_XIJI.get(top["神"], {}), 依据="YS-004"),
            "优先级": ([f"{k}{v}" for k, v in
                        sorted(YONGSHEN_ORDER[self.cfg.get("yongshen_order", "调候优先")].items(),
                               key=lambda kv: kv[1])]),
            "采用口径": self.cfg.get("yongshen_order", "调候优先"),
            "依据": ["ZP-029", "ZP-028", "ZP-025", "YL-001", "GJ-001", "GJ-002", "SS-004", "YS-004"],
            "说明": ("多因子取用：从化＞调候＞格神/相神＞扶抑＞病药（顺序为规则倾向，非唯一正解）；"
                     "候选取各自因子之神并标优先级/有气；定神给置信与备选，冲突时不硬判。"
                     "调候可救普通忌神（ZP-029）。"),
        }

    def _yongshen_27(self) -> dict:
        counts = {g: self._group_count(g) for g in GOD_GROUPS}
        strong = self.strength["身旺"]
        table = self.eng.data("ZP-028")["身强" if strong else "身弱"]
        month_god = ten_god(self.day_gan, self.hid["月"]["本"][0])
        month_group = next((g for g, gs in GOD_GROUPS.items() if month_god in gs), None)
        tie_order = ["官杀", "财", "印", "伤食", "比劫"]
        pool = [(g, counts[g]) for g in GOD_GROUPS if counts[g] >= 2]
        pool.sort(key=lambda x: (-x[1], 0 if x[0] == month_group else 1, tie_order.index(x[0])))
        if not pool:
            return {"神": month_god, "取法": "五神均不多，回落月令本气（YL-001）",
                    "来源": "月令本气", "说明": "五神无≥2者，按 YL-001 以月令本气为用"}
        dominant = pool[0][0]
        row = table.get(dominant + "多")
        if not row:
            return {"神": month_god,
                    "取法": f"千里二十七法未列（{'身强' if strong else '身弱'}·{dominant}多），回落月令本气（YL-001）",
                    "来源": "月令本气",
                    "说明": f"五神多寡 {counts}；表中无此行，以月令本气为用并提示人工复核"}
        chosen, key = row["用"], "用"
        if counts.get(chosen, 0) == 0:
            for k in sorted([k for k in row if k != "用"],
                            key=lambda k: -len([g for g in k[1:].split("无") if g])):
                groups = [g for g in k[1:].split("无") if g]
                if all(counts.get(g, 0) == 0 for g in groups):
                    chosen, key = row[k], k
                    break
        god = self._pick_group_god(chosen)
        missing = counts.get(chosen, 0) == 0
        return {"神": god, "取法": f"千里二十七法（ZP-028）：{'身强' if strong else '身弱'}·{dominant}多→{key}",
                "来源": chosen, "说明": f"五神多寡 {counts}；" +
                ("原局所喜之神亦缺，待行运补之。" if missing else "所喜之神原局有气。")}

    def _pick_group_god(self, group: str) -> str:
        gs = GOD_GROUPS[group]
        present = [g for g in gs if self._n(g) > 0]
        return present[0] if present else gs[0]

    def _liufa(self, god: str) -> list[dict]:
        pair = LIUFA_PAIR.get(god)
        if not pair:
            return []
        kind, text = pair
        if kind == "身旺":
            met, note = self.strength["身旺"], f"身{self.strength['判定']}"
        elif kind == "财":
            met, note = self._cai(), f"财{'有' if self._cai() else '无'}"
        elif kind == "印":
            met, note = self._yin(), f"印{'有' if self._yin() else '无'}"
        elif kind == "官":
            met, note = self._guansha(), f"官煞{'有' if self._guansha() else '无'}"
        else:
            met, note = None, ""
        return [{"法": text, "配套": kind, "命中": met, "说明": note, "依据": "GJ-002"}]

    # ================= 分歧并列 =================
    def _divergences(self, patterns: list[dict]) -> list[dict]:
        out: list[dict] = []
        # 1) 羊刃三说
        out.append({
            "主题": "羊刃起法（三说）",
            "采用": self.cfg["yangren"],
            "诸说": {
                "三命（十干皆有刃，禄前一辰）": self.eng.data("YR-002"),
                "渊海（五阳有刃、五阴无刃）": "五阴无刃，惟见伤官",
                "千里（阳顺阴逆，阴刃禄后）": self.eng.data("ZP-011")["说三（千里·禄后）"],
            },
            "依据": ["YR-002", "ZP-011", "ZP-017"],
        })
        # 2) 天德两表
        three = self.eng.data("SSH-008")[GONG[self.month_zhi]]
        qian = self._qianli_tiande()
        out.append({
            "主题": "天德表（两说）",
            "采用": self.cfg["tiande"],
            "诸说": {"三命（按宫组配干）": three, "千里（按月支通行表）": qian},
            "说明": f"本月支{self.month_zhi}：三命表＝{three}；千里表＝{qian}。两表不一致时不择一。",
            "依据": ["SSH-008", "ZP-012"],
        })
        # 3) 藏干两说（通行 CG-007 与渊海藏遁歌集合不同时才列；辰未仅次序不同不列）
        if self.month_zhi in YH_CANGGAN:
            tx = list(self._hid_stems("月"))
            yh = YH_CANGGAN[self.month_zhi]
            if set(tx) != set(yh):
                out.append({
                    "主题": "藏干两说（藏干集合）",
                    "采用": self.cfg["canggan"],
                    "诸说": {
                        "通行（CG-007）": tx,
                        "渊海（藏遁歌）": yh,
                    },
                    "说明": "渊海《又地支藏遁歌》与通行口径在丑（余气庚/辛等）等处不同；两说并列，不擅择一（ZP-020）。",
                    "依据": ["CG-007", "CG-004", "ZP-020"],
                })
        # 4) 化气两说（日干有合）
        partner = HE_PARTNER.get(self.day_gan)
        if partner and any(self.stems[p] == partner for p in ("年", "月", "时")):
            out.append({
                "主题": "化气时令（两说）",
                "采用": self.cfg["huoqi"],
                "诸说": {
                    "三命（正化月，甲己次午等）": "按月令正化，含午月化土一说",
                    "千里（ZP-010）": "辰戌丑未只化土、亥卯未只化木、巳酉丑只化金、寅午戌只化火、申子辰只化水；寅月兼化木、申月兼化金、巳月兼化火、亥月兼化水",
                },
                "说明": f"日干{self.day_gan}见{partner}，合是否化须按两说并列校验。",
                "依据": ["ZP-010"],
            })
        # 5) 官煞混杂去留
        if self._has("正官") and self._has("七杀"):
            out.append({
                "主题": "官煞去留",
                "采用": "并呈",
                "诸说": {
                    "GJ-043": "有物去官留煞则以偏官论，有物去煞留官则以正官论；透者易去、藏者难去",
                    "GJ-044": "五阳日食神能去煞留官、伤官只能去官（须刃合方成去官留煞）；五阴日食神能去煞不能留官、伤官能去官留煞",
                },
                "依据": ["GJ-041", "GJ-043", "GJ-044", "GJ-046"],
            })
        # 6) 外格立场
        if any(p["类别"] == "外格" and p["格"] in ("飞天禄马", "倒冲禄") for p in patterns):
            out.append({
                "主题": "外格立场（三命 vs 渊海）",
                "采用": "按三命实现，附渊海按语",
                "诸说": {"三命": "飞天禄马/倒冲/冲合禄马列为外格（GJ-121/122/103）",
                        "渊海": "即伤官析而为之，妄立格局无实用（ZP-018，参考级）"},
                "依据": ["GJ-121", "GJ-122", "GJ-103", "ZP-018"],
            })
        # 7) 六破表与 GJ-013 例的出入
        if self.month_zhi == "酉" and "午" in self.branches:
            out.append({
                "主题": "『午破酉』（GJ-013 例 vs 六破表）",
                "采用": "按 SSH-050 六破表",
                "诸说": {"GJ-013 例": "甲生酉月见午破",
                        "SSH-050 六破": "卯午、丑辰、子酉、未戌；无午酉"},
                "说明": "本引擎破格判定不据午破酉；两说并列供人工复核。",
                "依据": ["GJ-013", "SSH-050"],
            })
        return out

    def _qianli_tiande(self) -> str:
        data = self.eng.data("ZP-012")
        for k, v in data.items():
            if self.month_zhi in k:
                return v
        return "未列"

    @staticmethod
    def _dedup_order(names: list[str]) -> list[str]:
        seen, out = set(), []
        for n in names:
            if n not in seen:
                seen.add(n)
                out.append(n)
        return out


def _fs(pairs: set[str]) -> set[frozenset]:
    return {frozenset(p) for p in pairs}


def _branch_group(zhi: str) -> str:
    for g in ("申子辰", "亥卯未", "寅午戌", "巳酉丑"):
        if zhi in g:
            return g
    raise KeyError(zhi)


def _gz_index(gz: str) -> int:
    from bazi_engine import gz_index
    return gz_index(gz)


def _gz_from_index(p: int) -> str:
    from bazi_engine import gz_from_index
    return gz_from_index(p)
