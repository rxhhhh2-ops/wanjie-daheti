# -*- coding: utf-8 -*-
"""奇门定局外部校验（经 HTTP 调本机服务）。

独立参照：时家奇门通行的「二十四节气三元局数表」+ 拆补法符头分元规则
（符头地支 子午卯酉→上元、寅申巳亥→中元、辰戌丑未→下元）。
同时用 lunar_python 交接节气时刻，独立校验引擎的节气判定。

用法：py -3.12 tests/check_qimen_ju.py   （须先启动 server.py，在项目根目录运行）
"""
import json
import sys
import urllib.request
from datetime import datetime, timedelta

from lunar_python import Solar

BASE = "http://127.0.0.1:8899"

# 二十四节气三元局数（上元, 中元, 下元）——通行表
JU_TABLE = {
    "冬至": (1, 7, 4), "小寒": (2, 8, 5), "大寒": (3, 9, 6),
    "立春": (8, 5, 2), "雨水": (9, 6, 3), "惊蛰": (1, 7, 4),
    "春分": (3, 9, 6), "清明": (4, 1, 7), "谷雨": (5, 2, 8),
    "立夏": (4, 1, 7), "小满": (5, 2, 8), "芒种": (6, 3, 9),
    "夏至": (9, 3, 6), "小暑": (8, 2, 5), "大暑": (7, 1, 4),
    "立秋": (2, 5, 8), "处暑": (1, 4, 7), "白露": (9, 3, 6),
    "秋分": (7, 1, 4), "寒露": (6, 9, 3), "霜降": (5, 8, 2),
    "立冬": (6, 9, 3), "小雪": (5, 8, 2), "大雪": (4, 7, 1),
}
YANG_TERMS = {"冬至", "小寒", "大寒", "立春", "雨水", "惊蛰", "春分", "清明",
              "谷雨", "立夏", "小满", "芒种"}
YUAN_IDX = {"上": 0, "中": 1, "下": 2}
# 符头地支 → 元
YANG_YUAN = {"子": "上", "午": "上", "卯": "上", "酉": "上",
             "寅": "中", "申": "中", "巳": "中", "亥": "中",
             "辰": "下", "戌": "下", "丑": "下", "未": "下"}


def fetch(dt):
    url = f"{BASE}/qimen/api/chart?dt={dt}"
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r)["chart"]


def main():
    # 采样：2023-2026 每年 24 个日期（每节气附近 ±2 天各一个），覆盖 24 节气
    samples = []
    for year in (2023, 2024, 2025):
        solar = Solar.fromYmd(year, 1, 1)
        lunar = solar.getLunar()
        for name, day in lunar.getJieQiTable().items():
            if name in JU_TABLE and day.getYear() == year:
                d0 = datetime(day.getYear(), day.getMonth(), day.getDay())
                for off in (-1, 0, 1):
                    dd = d0 + timedelta(days=off)
                    samples.append(dd.strftime("%Y-%m-%dT10:00"))

    passed = failed = 0
    fails = []
    for dt in samples:
        try:
            c = fetch(dt)
        except Exception as exc:
            failed += 1
            fails.append(f"✗ {dt} 请求异常 {exc}")
            continue
        t = c["term"]
        term, dun, ju, yuan = t["term"], t["dun"], t["ju"], t["yuan"]
        fz = t["futou_gz"]
        errs = []
        # 1) 阴阳遁：冬至→芒种阳遁，夏至→大雪阴遁
        want_dun = "阳" if term in YANG_TERMS else "阴"
        if dun != want_dun:
            errs.append(f"阴阳遁 {dun}≠{want_dun}")
        # 2) 局数 = 该节气对应元的局数
        if term in JU_TABLE:
            want_ju = JU_TABLE[term][YUAN_IDX[yuan]]
            if ju != want_ju:
                errs.append(f"局数 {ju}≠{want_ju}({term}{yuan}元)")
        else:
            errs.append(f"未知节气 {term}")
        # 3) 符头地支与元的一致性（拆补法）
        if len(fz) >= 2 and fz[1] in YANG_YUAN:
            want_yuan = YANG_YUAN[fz[1]]
            if yuan != want_yuan:
                errs.append(f"符头{fz}→{want_yuan}元, 引擎{yuan}元")
        # 4) 节气时刻与 lunar_python 独立对照（取 ±2 年表中与引擎时刻最近的一条，容差 1 天）
        try:
            got = datetime.strptime(t["term_time"].split(".")[0], "%Y-%m-%d %H:%M:%S")
            cands = []
            for yy in (got.year - 1, got.year, got.year + 1):
                tb = Solar.fromYmd(yy, 6, 1).getLunar().getJieQiTable().get(term)
                if tb is not None:
                    cands.append(datetime(tb.getYear(), tb.getMonth(), tb.getDay(),
                                          tb.getHour(), tb.getMinute(), tb.getSecond()))
            if cands:
                ref = min(cands, key=lambda x: abs((x - got).total_seconds()))
                if abs((got - ref).total_seconds()) > 86400:
                    errs.append(f"节气时刻 {got} vs lunar_python {ref}")
        except Exception as exc:
            errs.append(f"节气时刻对照异常 {exc}")
        if errs:
            failed += 1
            fails.append(f"✗ {dt} {term} {dun}遁{ju}局{yuan}元[{fz}]: " + "；".join(errs))
        else:
            passed += 1

    print(f"奇门定局外部校验：{passed} 通过，{failed} 不一致（共 {passed + failed} 例）")
    for line in fails[:20]:
        print(line)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
