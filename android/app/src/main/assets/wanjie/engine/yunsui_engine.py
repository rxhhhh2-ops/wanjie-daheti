# -*- coding: utf-8 -*-
"""运岁流年引擎：大运（顺逆/起运/十二宫/十神）＋流年（太岁/岁运关系）。

依据：YS-001～016（rules/10-运岁.json）。
- 大运：YS-001 顺逆、YS-002 起运折算、YS-003 重地支、YS-005 原有官财应期、
        YS-007 运程十二宫、YS-014 支无官财运干可发。
- 流年：YS-009 当生/游行太岁、YS-010 岁伤日/日犯岁、YS-011 真太岁/征太岁/岁运并临/
        日年相并、YS-012 日犯轻重、YS-013 岁运冲月/返吟伏吟、YS-015 晦气、
        YS-016 大运与太岁克冲。

原则：只输出规则明确的条件命中与原文断语；不臆造吉凶总评。岁运用神喜忌（YS-004）
须待格局用神结构化后接入，当前只报十神与原局有无官财煞。
"""
from __future__ import annotations

from bazi_engine import (
    GAN, ZHI, WUXING, KE, ten_god, gz_step, year_gz_of_year,
)
from pattern_engine import YONGSHEN_XIJI

STAGE_ORDER = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"]
CHONG = {"子": "午", "午": "子", "丑": "未", "未": "丑", "寅": "申", "申": "寅",
         "卯": "酉", "酉": "卯", "辰": "戌", "戌": "辰", "巳": "亥", "亥": "巳"}
HE = {"甲": "己", "己": "甲", "乙": "庚", "庚": "乙", "丙": "辛", "辛": "丙",
      "丁": "壬", "壬": "丁", "戊": "癸", "癸": "戊"}
YANG_GAN = set("甲丙戊庚壬")


def _ke(a: str, b: str) -> bool:
    """五行 a 克 b。"""
    return KE[WUXING[a]] == WUXING[b]


class YunSuiEngine:
    def __init__(self, engine):
        self.eng = engine

    # ================= 大运 =================
    def dayun(self, pillars: dict, gender: str, jie_days: dict | None = None,
              birth_year: int | None = None, steps: int = 8,
              yong_shen: str | None = None) -> dict:
        self.pillars = pillars
        self.day_gan = pillars["日"][0]
        year_gan = pillars["年"][0]
        yang = year_gan in YANG_GAN
        forward = (yang and gender == "男") or ((not yang) and gender == "女")
        step = 1 if forward else -1
        seq = [gz_step(pillars["月"], step * (i + 1)) for i in range(steps)]

        qiyun = None
        start_age = None
        if jie_days:
            try:
                from datetime import datetime as _dt
                m0 = _dt.fromisoformat(jie_days["出生时刻"])
                a = _dt.fromisoformat(jie_days["上一节"])
                b = _dt.fromisoformat(jie_days["下一节"]) if jie_days.get("下一节") else None
                qiyun = (self.eng.qiyun_from_span(m0, b) if forward and b
                         else self.eng.qiyun_from_span(a, m0) if not forward else None)
            except (KeyError, TypeError, ValueError):
                qiyun = None
            if qiyun is None:
                days = jie_days.get("距下一节天数") if forward else jie_days.get("距上一节天数")
                if days is not None:
                    qiyun = self.eng.qiyun_from_days(days)
            if qiyun:
                start_age = qiyun["岁"] + qiyun["月"] / 12.0

        rows = []
        for i, gz in enumerate(seq):
            stage = self._stage(gz[1])
            item = {
                "序": i + 1,
                "干支": gz,
                "十神（干）": ten_god(self.day_gan, gz[0]),
                "十神（支本气）": ten_god(self.day_gan, self._benqi(gz[1])),
                "十二宫": stage,
                "十二宫取象": self._stage_image(stage),
                "依据": ["YS-003", "YS-007"],
            }
            if start_age is not None:
                item["起始岁（约）"] = round(start_age + i * 10, 2)
                item["结束岁（约）"] = round(start_age + (i + 1) * 10, 2)
                if birth_year:
                    item["起始年（约）"] = round(birth_year + start_age + i * 10, 1)
                    item["结束年（约）"] = round(birth_year + start_age + (i + 1) * 10, 1)
            if yong_shen:
                item["用神喜忌"] = self._ys004_step(
                    yong_shen, item["十神（干）"], item["十神（支本气）"])
            rows.append(item)

        return {
            "方向": "顺行" if forward else "逆行",
            "年干阴阳": "阳" if yang else "阴",
            "起运": qiyun or "未计算（缺少节气距离；排盘路径会自动给出）",
            "大运（前八步）": rows,
            "原局官财煞": self._original_cai_guan_sha(),
            "说明": ("大运重地支（YS-003）；起运按 3日=1年、1日=4月、1时辰=10日 折算（YS-002，问真/通行口径）；"
                     "起始年按周岁估算，未计虚岁/交运月日。"),
            "依据": ["YS-001", "YS-002", "YS-003", "YS-005", "YS-007", "YS-014"],
        }

    def _stage(self, branch: str) -> str:
        seq = self.eng.data("YL-008")[self.day_gan]
        return STAGE_ORDER[seq.index(branch)]

    def _stage_image(self, stage: str) -> str:
        table = self.eng.data("YS-007")
        key = {"沐浴": "败", "墓": "库"}.get(stage, stage)
        return table.get(key, "未列（养等）")

    def _benqi(self, branch: str) -> str:
        v = self.eng.data("CG-007")[branch]["本"]
        return (v[0] if isinstance(v, (list, tuple)) else v[0])

    def _original_cai_guan_sha(self) -> dict:
        """原局四支本气所含官/财/煞（YS-005/YS-014 用）。"""
        out = {"官": [], "财": [], "煞": []}
        for p in ("年", "月", "日", "时"):
            god = ten_god(self.day_gan, self._benqi(self.pillars[p][1]))
            if god == "正官":
                out["官"].append(p)
            elif god == "七杀":
                out["煞"].append(p)
            elif god in ("正财", "偏财"):
                out["财"].append(p)
        return out

    # ================= 流年 =================
    def liunian(self, pillars: dict, year: int, gender: str | None = None,
                birth_year: int | None = None, jie_days: dict | None = None,
                dayun_gz: str | None = None, yong_shen: str | None = None) -> dict:
        self.pillars = pillars
        self.day_gan = pillars["日"][0]
        self.day_zhi = pillars["日"][1]
        ln = year_gz_of_year(year)
        ln_gan, ln_zhi = ln[0], ln[1]
        out: dict = {
            "流年": {"年": year, "干支": ln,
                     "十神（干）": ten_god(self.day_gan, ln_gan),
                     "十神（支本气）": ten_god(self.day_gan, self._benqi(ln_zhi))},
            "太岁": {"当生太岁": pillars["年"][1], "游行太岁": ln_zhi},
            "关系": [],
            "断语": [],
            "说明": "岁用天元、运用地支（YS-009/003）；条件命中即列原文断语，不作吉凶总评。",
            "依据": ["YS-009", "YS-010", "YS-011", "YS-012", "YS-013", "YS-015", "YS-016"],
        }

        # 取大运
        dy_gz = dayun_gz
        dy_info = None
        if dy_gz is None and gender and birth_year and jie_days:
            dy = self.dayun(pillars, gender, jie_days, birth_year)
            age = year - birth_year
            picked = None
            for row in dy["大运（前八步）"]:
                s, e = row.get("起始岁（约）"), row.get("结束岁（约）")
                if s is not None and s <= age < e:
                    picked = row
                    break
            if picked:
                dy_gz = picked["干支"]
                dy_info = picked
            else:
                out["大运"] = "未交大运（童限，专用小运 YS-008）"
        if dy_gz:
            out["大运"] = dy_info or {"干支": dy_gz}
        else:
            out.setdefault("大运", "未提供（可用 --gender/--birth-year 或 dayun_gz 指定）")

        def add(rule, cond, conclusion, **extra):
            out["关系"].append({"规则": rule, "条件": cond, "结论": conclusion, **extra})

        # YS-009 当生/游行
        add("YS-009", f"生年支{self.pillars['年'][1]}、流年支{ln_zhi}",
            "当生太岁终身主、游行太岁主一年；太岁为君、大运为臣")

        # YS-010/012 岁伤日干 / 日犯岁君
        if _ke(ln_gan, self.day_gan):
            add("YS-010", f"流年干{ln_gan}克日干{self.day_gan}", "岁伤日干，有祸必轻")
        if _ke(self.day_gan, ln_gan):
            heavy = self.day_gan in YANG_GAN
            add("YS-012", f"日干{self.day_gan}克流年干{ln_gan}",
                f"日犯岁君，灾殃必重；{'五阳干重' if heavy else '五阴干轻'}")
            rescue = self._find_rescue(ln_gan, dy_gz)
            if rescue:
                add("YS-010", f"{rescue}", "有救/有情，可解")

        # YS-011 真太岁（转趾煞）
        for pos in ("日", "时"):
            if self.pillars[pos] == ln:
                add("YS-011", f"流年{ln}与{pos}柱{self.pillars[pos]}相同",
                    "真太岁（转趾煞）：大运日主与太岁和顺则吉，刑冲破害战克则凶")

        # YS-011 征太岁 / 天冲地击
        if self._tian_ke_di_chong(ln, self.pillars["日"]):
            add("YS-011", f"流年{ln}与日柱{self.pillars['日']}天克地冲",
                "征太岁（天冲地击），其年凶")
        if dy_gz and self._tian_ke_di_chong(ln, dy_gz):
            add("YS-011", f"流年{ln}与大运{dy_gz}天克地冲", "征太岁，其年凶")

        # YS-011 岁运并临
        if dy_gz and dy_gz == ln:
            god = ten_god(self.day_gan, ln_gan)
            ren = self.eng.data("YR-002")[self.day_gan]["羊刃"]
            bad = god == "七杀" or any(
                ten_god(self.day_gan, self._benqi(gz[1])) == "七杀"
                for gz in self.pillars.values()
            )
            blade = dy_gz[1] == ren or ln_zhi == ren
            hints = []
            if bad:
                hints.append("命中七煞")
            if blade:
                hints.append("运岁临羊刃")
            add("YS-011", f"大运{dy_gz}＝流年{ln}",
                "岁运并临；独羊刃、七煞为凶，财官印绶亦吉"
                + (f"（{'、'.join(hints)}，重点提示）" if hints else ""))

        # YS-011 日年相并
        if self.pillars["日"] == ln:
            add("YS-011", f"日柱{self.pillars['日']}＝流年{ln}",
                "日年相并：君子得之为君臣庆会，常人遇之最不善；生时相和则灾轻")

        # YS-013 岁运冲月 / 返吟伏吟
        if ln_zhi == CHONG[self.pillars["月"][1]]:
            add("YS-013", f"流年支{ln_zhi}冲月支{self.pillars['月'][1]}", "岁运冲月必祸")
        if dy_gz:
            if dy_gz[1] == CHONG[self.pillars["月"][1]]:
                add("YS-013", f"大运支{dy_gz[1]}冲月支{self.pillars['月'][1]}", "岁运冲月必祸")
            if dy_gz == self.pillars["日"]:
                add("YS-013", f"大运{dy_gz}压日柱{self.pillars['日']}", "伏吟：不利六亲、破财")
            elif self._tian_ke_di_chong(dy_gz, self.pillars["日"]):
                add("YS-013", f"大运{dy_gz}与日柱{self.pillars['日']}相对",
                    "返吟：不利六亲、破财")
        if self._tian_ke_di_chong(ln, self.pillars["日"]):
            add("YS-013", f"流年{ln}与日柱{self.pillars['日']}相对",
                "返吟（与征太岁同象，两说并列）：不利六亲、破财")

        # YS-015 晦气
        for pos in ("日", "时"):
            stem = self.pillars[pos][0]
            if HE.get(stem) == ln_gan:
                if stem == "甲" and ln_gan == "己":
                    weight = "甲合己，灾重"
                elif stem == "己" and ln_gan == "甲":
                    weight = "己合甲，灾轻"
                else:
                    weight = "日/时干与太岁天元合"
                add("YS-015", f"{pos}干{stem}合流年干{ln_gan}", f"晦气煞：{weight}")

        # YS-016 大运与太岁克冲
        if dy_gz:
            if _ke(dy_gz[0], ln_gan):
                add("YS-016", f"大运干{dy_gz[0]}克流年干{ln_gan}", "运克岁，尤忌，主破耗丧事")
            elif _ke(ln_gan, dy_gz[0]):
                add("YS-016", f"流年干{ln_gan}克大运干{dy_gz[0]}", "岁克运，不宜")
            if dy_gz[1] == CHONG[ln_zhi]:
                add("YS-016", f"大运支{dy_gz[1]}冲流年支{ln_zhi}", "运岁相冲，不宜")

        # YS-014 支无官财运干可发（原文限『运干』，此处只查大运干）
        orig = self._original_cai_guan_sha()
        if dy_gz:
            for kind, god_name in (("官", ("正官",)), ("财", ("正财", "偏财")), ("煞", ("七杀",))):
                if orig[kind]:
                    continue
                stem = dy_gz[0]
                if ten_god(self.day_gan, stem) in god_name:
                    conclusion = ("运干官可发福" if kind == "官" else
                                  "运干财可发财" if kind == "财" else "运干煞足为祸")
                    add("YS-014", f"原局地支无{kind}，运干{stem}为{ten_god(self.day_gan, stem)}",
                        conclusion)

        # YS-005 原有官财应期（只报大运十神对应）
        if dy_gz:
            for kind in ("官", "财", "煞"):
                if orig[kind]:
                    god = ten_god(self.day_gan, dy_gz[0])
                    if (kind == "官" and god == "正官") or (kind == "煞" and god == "七杀") \
                            or (kind == "财" and god in ("正财", "偏财")):
                        add("YS-005", f"原局有{kind}，大运干{dy_gz[0]}为{god}",
                            f"原有{kind}，行{kind}运而{kind}事应")

        # YS-004 用神行运喜忌（流年干/支）
        if yong_shen:
            for label, god in (("流年干", ten_god(self.day_gan, ln_gan)),
                               ("流年支", ten_god(self.day_gan, self._benqi(ln_zhi)))):
                v = self._ys004(yong_shen, god)
                if v and v["判"] != "平":
                    add("YS-004", f"用神{yong_shen}，{label}{god}为{v['判']}",
                        f"{v['文本']}（{v['判']}）")

        out["断语数"] = len(out["关系"])
        return out

    def _ys004_step(self, yong_shen: str, stem_god: str, branch_god: str) -> dict:
        hits = []
        for label, god in (("运干", stem_god), ("运支本气", branch_god)):
            v = self._ys004(yong_shen, god)
            if v and v["判"] != "平":
                hits.append({"位置": label, "十神": god, **v})
        return {"用神": yong_shen, "命中": hits,
                "说明": "运干/运支本气见用神喜忌神；YS-004 官欲生、煞欲制、财欲扶、印欲旺、食欲生"}

    @staticmethod
    def _ys004(yong_shen: str, god: str) -> dict | None:
        m = YONGSHEN_XIJI.get(yong_shen)
        if not m:
            return None
        if god in m["喜"]:
            return {"判": "喜", "文本": m["文本"]}
        if god in m["忌"]:
            return {"判": "忌", "文本": m["文本"]}
        return {"判": "平", "文本": m["文本"]}

    def _find_rescue(self, ln_gan: str, dy_gz: str | None) -> str:
        """有救：有克日干之干（官杀）制身；有情：有干合流年干。"""
        notes = []
        others = [self.pillars[p][0] for p in ("年", "月", "时")]
        stems = list(others)
        if dy_gz:
            stems.append(dy_gz[0])
        for s in others + ([dy_gz[0]] if dy_gz else []):
            if _ke(s, self.day_gan):
                notes.append(f"{s}干克日干为有救")
        for s in stems:
            if HE.get(s) == ln_gan:
                notes.append(f"{s}干合流年干为有情")
        return "；".join(dict.fromkeys(notes))

    @staticmethod
    def _tian_ke_di_chong(a: str, b: str) -> bool:
        return _ke(a[0], b[0]) and CHONG[a[1]] == b[1]
