# -*- coding: utf-8 -*-
"""十神/宫位含义引擎：每格十神 → 关系、人、事、物、正面、负面、物质、精神。

依据（rules/03-十神.json、rules/12-卷七断法.json）：
- SS-001/005：十神与日主关系（同我/生我/我生/克我/我克，阴阳分正偏）
- SS-010..018：每神含义（能力、人、事、物、正面、负面、物质层面、精神层面、别名、六亲）
- SS-019：四柱宫位总义（年祖业/月父母门户/日己身配偶/时子息）
- SS-004：喜忌总纲（官怕伤、财怕劫、印怕财、食怕枭）
- J7-060/061/062：六亲取用、宫位、落位吉凶
- ZP-027：六亲取用三说（三命/渊海/千里，配置键 liuqin）

原则：含义均为规则库有出处者；含推定处已在 data 中注明。
"""
from __future__ import annotations

from bazi_engine import ten_god

GOD_RULE = {"比肩": "SS-010", "劫财": "SS-010", "食神": "SS-011", "伤官": "SS-012",
            "正财": "SS-013", "偏财": "SS-014", "正官": "SS-015", "七杀": "SS-016",
            "正印": "SS-017", "偏印": "SS-018"}


class MeaningEngine:
    def __init__(self, engine, config: dict | None = None):
        self.eng = engine
        self.cfg = {"liuqin": "三命"}
        if config and "liuqin" in config:
            self.cfg["liuqin"] = config["liuqin"]

    def compute(self, pillars: dict, hid: dict) -> dict:
        day_gan = pillars["日"][0]
        gods: dict[str, list[str]] = {}
        for pos in ("年", "月", "日", "时"):
            gods.setdefault(ten_god(day_gan, pillars[pos][0]), []).append(f"{pos}干")
        for pos in ("年", "月", "日", "时"):
            for lvl in ("本", "中", "余"):
                for s in hid[pos].get(lvl, ""):
                    gods.setdefault(ten_god(day_gan, s), []).append(f"{pos}支{lvl}")

        meanings: dict[str, dict] = {}
        for god, poss in gods.items():
            rule = self.eng.rule(GOD_RULE[god])
            meanings[god] = {
                "规则": rule["id"],
                "level": rule["level"],
                "命中柱位": poss,
                **{k: v for k, v in (rule.get("data") or {}).items()},
            }

        gong = self.eng.rule("SS-019").get("data") or {}
        palaces = {}
        for pos in ("年", "月", "日", "时"):
            gan_g = ten_god(day_gan, pillars[pos][0])
            hidden_gods = {lvl: [ten_god(day_gan, s) for s in hid[pos].get(lvl, [])]
                           for lvl in ("本", "中", "余")}
            palaces[pos] = {
                "宫位含义": gong.get(pos),
                "天干十神": gan_g,
                "天干含义": {k: meanings[gan_g].get(k)
                             for k in ("关系", "正面", "负面", "物质层面", "精神层面")}
                if gan_g in meanings else None,
                "藏干十神": hidden_gods,
                "依据": ["SS-019", "J7-061", GOD_RULE.get(gan_g, "SS-005")],
            }

        return {
            "十神含义": meanings,
            "宫位": palaces,
            "六亲映射": self._liuqin(),
            "喜忌总纲": self.eng.rule("SS-004")["rule"],
            "说明": ("含义为规则倾向与取象，不作吉凶总评（SS-008 数量断与格局合看）；"
                     "六亲取用三说并列（ZP-027），配置键 liuqin；"
                     "日干本身为比肩（自我），含义供参照。"),
            "依据": ["SS-001", "SS-004", "SS-005", "SS-010", "SS-011", "SS-012", "SS-013",
                     "SS-014", "SS-015", "SS-016", "SS-017", "SS-018", "SS-019",
                     "J7-060", "J7-061", "J7-062", "ZP-027"],
        }

    def _liuqin(self) -> dict:
        data = self.eng.rule("ZP-027").get("data") or {}
        return {"采用": self.cfg["liuqin"], "三说": data,
                "说明": "六亲取用三说配置化；默认三命（J7-060），分歧并列见 ZP-027"}
