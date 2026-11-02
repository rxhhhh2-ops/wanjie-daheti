# -*- coding: utf-8 -*-
"""奇门排盘结构不变量检查（经 HTTP 调本机服务）。

不变量（奇门基本盘面性质）：
  - 9 宫齐备，每宫必备字段非空；
  - 八门分据八宫、互不重复（中宫无门）；
  - 天盘/地盘各宫干为三奇六仪九宫分布（各自无重复）；
  - 值符、值使各恰好一宫；
  - 节气字段与四柱齐备。
抽样：默认配置 + 拆补/置闰两流派 × 32 个时间。
用法：py -3.12 tests/check_qimen.py
"""
import json
import random
import urllib.request

BASE = "http://127.0.0.1:8899"
CHART = {"戊", "己", "庚", "辛", "壬", "癸", "丁", "丙", "乙"}  # 三奇六仪
DOORS = {"休门", "生门", "伤门", "杜门", "景门", "死门", "惊门", "开门"}
STARS = {"天蓬", "天任", "天冲", "天辅", "天英", "天禽", "天芮", "天柱", "天心"}

def fetch(dt, extra=""):
    url = f"{BASE}/qimen/api/chart?dt={dt}{extra}"
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r)["chart"]

def check_chart(c, ctx):
    errs = []
    cells = c.get("cells") or {}
    if len(cells) != 9:
        errs.append(f"宫数 {len(cells)} != 9")
        return errs
    doors, tg, dg, stars = [], [], [], []
    zhifu = zhishi = 0
    for gong, cell in cells.items():
        mid = (str(gong) == "5")  # 中五宫：不布门与神盘（寄宫制），允许缺 shen/door/tian_gan
        need = ("star", "di_gan") if mid else ("shen", "star", "tian_gan", "di_gan")
        for k in need:
            if not cell.get(k):
                errs.append(f"宫{gong} 缺 {k}")
        doors.append((cell.get("door") or {}).get("name"))
        stars.append((cell.get("star") or {}).get("name"))
        tg += cell.get("tian_gan") or []
        dg += cell.get("di_gan") or []
        zhifu += bool(cell.get("is_zhifu"))
        zhishi += bool(cell.get("is_zhishi"))
    named_doors = [d for d in doors if d]
    if len(named_doors) != 8 or set(named_doors) != DOORS:
        errs.append(f"八门异常: {sorted(set(named_doors))}")
    if not set(tg) <= CHART or not (8 <= len(tg) <= 10):
        errs.append(f"天盘干异常: {sorted(tg)}")
    # 中宫天禽所带天盘干记于 zhong_gong.gan（寄宫制），并入校验
    mid_gan = (c.get("zhong_gong") or {}).get("gan")
    if mid_gan and set(tg + [mid_gan]) != CHART:
        errs.append(f"天盘干（含中宫）缺干: {sorted(set(tg + [mid_gan]))}")
    if set(dg) != CHART or len(dg) != 9:
        errs.append(f"地盘干异常: {sorted(dg)}")
    if set(stars) != STARS:
        errs.append(f"九星异常: {sorted(set(stars))}")
    if zhifu != 1 or zhishi != 1:
        errs.append(f"值符{zhifu}/值使{zhishi} 数量异常")
    if not c.get("term") or not c.get("four_pillars"):
        errs.append("缺节气或四柱字段")
    return errs

def main():
    random.seed(7)
    times = [f"{random.randint(2000, 2035)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}T{random.randint(0, 23):02d}:{random.choice([0, 15, 30, 45]):02d}"
             for _ in range(32)]
    total, bad = 0, 0
    for dt in times:
        for extra, tag in (("", "拆补"), ("&ding_ju=zhirun", "置闰")):
            total += 1
            try:
                errs = check_chart(fetch(dt, extra), f"{dt} {tag}")
            except Exception as exc:
                errs = [f"请求异常 {exc}"]
            if errs:
                bad += 1
                print(f"✗ {dt} [{tag}]: " + "；".join(errs[:3]))
    print(f"奇门结构不变量：{total - bad}/{total} 通过")
    return 1 if bad else 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
