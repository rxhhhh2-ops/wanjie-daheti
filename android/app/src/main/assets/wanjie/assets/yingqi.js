/* 万界大合体 · 应期共享模块（纯前端，无依赖）
 *
 * 原则：只收录有明确出处的应期规则；原文未列、无法核实或相互冲突者不写入。
 * 本文件负责：
 *   1) 六壬、紫微的前端应期候选计算；
 *   2) 五术共用的应期面板渲染；
 *   3) AI 解盘的“默认不输出应期 / 用户明确要求才输出”门禁。
 *
 * 规则出处见 rules/19-应期.json 与 knowledge/08-应期/00-应期资料核查.md。
 */
(function (global) {
  "use strict";

  const GAN = "甲乙丙丁戊己庚辛壬癸";
  const ZHI = "子丑寅卯辰巳午未申酉戌亥";
  const GAN_WX = { 甲: "木", 乙: "木", 丙: "火", 丁: "火", 戊: "土", 己: "土", 庚: "金", 辛: "金", 壬: "水", 癸: "水" };
  const ZHI_WX = { 子: "水", 丑: "土", 寅: "木", 卯: "木", 辰: "土", 巳: "火", 午: "火", 未: "土", 申: "金", 酉: "金", 戌: "土", 亥: "水" };
  const SHENG = { 木: "火", 火: "土", 土: "金", 金: "水", 水: "木" };
  const KE = { 木: "土", 土: "水", 水: "火", 火: "金", 金: "木" };
  const CHONG = { 子: "午", 午: "子", 丑: "未", 未: "丑", 寅: "申", 申: "寅", 卯: "酉", 酉: "卯", 辰: "戌", 戌: "辰", 巳: "亥", 亥: "巳" };
  const HE6 = { 子: "丑", 丑: "子", 寅: "亥", 亥: "寅", 卯: "戌", 戌: "卯", 辰: "酉", 酉: "辰", 巳: "申", 申: "巳", 午: "未", 未: "午" };
  // 刑：按《奇门法窍·论应期》例（子刑卯、戌刑未、寅刑巳）及通行三刑
  const XING = {
    子: ["卯"], 卯: ["子"],
    寅: ["巳", "申"], 巳: ["申", "寅"], 申: ["寅", "巳"],
    丑: ["戌", "未"], 戌: ["未", "丑"], 未: ["丑", "戌"],
    辰: ["辰"], 午: ["午"], 酉: ["酉"], 亥: ["亥"]
  };

  const SOURCES = {
    MH_QI: {
      title: "《梅花易数·卷二·先天后天论》",
      text: "先天之卦，定事应之期，则取之卦气，如乾、兑则应如庚、辛及申金之日，或坤为戌、亥之日时，兑为酉日时。如震、巽当应于甲、乙及支木之日，或震取卯，巽取辰之类。",
      file: "materials/03-梅花易数/梅花易数-知命书院本/006-卷二（1）.md#L36",
      level: "[原文]"
    },
    MH_DONGJING: {
      title: "《梅花易数·卷一·老人有忧色占》附",
      text: "行则应速，以成卦之数中分而取其半；坐则事应迟，当倍其成卦之数；立则半迟半速，止以成卦之数定之。",
      file: "knowledge/03-梅花易数/精读笔记/精读-序与卷一（象数易理）.md XS-42",
      level: "[原文]"
    },
    QM_FAJUE: {
      title: "《奇门法窍·论应期》（清·锡孟樨）",
      text: "先定其支，后配其干，其得干支之法，惟在正时定之……甲子直符加离九宫为子午一冲，子与丑合，应在丑年月日时……直符落在旬空，必以出旬断之……如又不冲、又不刑、又不空，断之则必看天盘六仪所带之支以定……以星门生克定之，生逢生日，克逢克日应之。内中且有先后分别，符应主先，使应符后。",
      file: "materials/01-奇门遁甲/易藏本-奇门法窍-清-锡孟樨/正文.txt#L935",
      level: "[原文]"
    },
    LR_DUAN: {
      title: "《六壬大全》卷三·轩辕肘後经余",
      text: "用起太岁一年中，斗建发时当月见……传辰旬内应期详，用日克期在朝晚……气首难过半月间，应候休言五日远，得时不出八刻中。",
      file: "materials/02-大六壬/六壬大全-知命书院本/020-卷三（6）.md#L36-L44",
      level: "[原文]"
    },
    LR_QIANHOU: {
      title: "《注解大六壬指南》卷二·九天玄女指掌赋",
      text: "用在日前事情已过，用居日后事起将来。日辰发用应今时……年月旬日发用，事应年月节旬。",
      file: "materials/02-大六壬/注解大六壬指南-知命书院本/009-卷二  大六壬九天玄女指掌赋（1）.md#L90",
      level: "[原文]"
    },
    LR_YINGRI: {
      title: "《六壬大全》卷三·应日",
      text: "吉凶之卦各言因，今日生我为吉日，克我干者是凶神。",
      file: "materials/02-大六壬/六壬大全-知命书院本/020-卷三（6）.md#L48",
      level: "[原文]"
    },
    LR_CAVEAT: {
      title: "《注解大六壬指南》卷二·张洪注",
      text: "应期之法变化多端，课体不同，应期之法却当活论。",
      file: "materials/02-大六壬/注解大六壬指南-知命书院本/009-卷二  大六壬九天玄女指掌赋（1）.md#L96",
      level: "[注]"
    },
    ZW_DAXIAN: {
      title: "《紫微斗数全书》卷三·论大限十年祸福",
      text: "如宫分星缠全吉庙旺得地，无擎羊陀罗火铃空劫者，主十年安静，人财全美……大限将出，有吉众者无灾悔，少者灾多，损人破财不利。",
      file: "materials/06-紫微斗数/紫微斗数全书-知命书院本/017-卷三（1）.md#L140-L142",
      level: "[原文]"
    },
    ZW_NANBEI: {
      title: "《紫微斗数全书》卷三·论行限分南北斗",
      text: "北斗诸星吉凶，大限断上五年应，小限断上半年应。南斗诸星吉凶，大限断下五年应，小限断下半年应。",
      file: "materials/06-紫微斗数/紫微斗数全书-知命书院本/017-卷三（1）.md#L150",
      level: "[原文]"
    },
    ZW_SUIJUN: {
      title: "《紫微斗数全书》卷二·岁君火",
      text: "岁君火，乃流年太岁星君……忌与大小二限相冲。",
      file: "materials/06-紫微斗数/紫微斗数全书-知命书院本/013-卷二（6）.md#L52",
      level: "[原文]"
    },
    ZW_JI: {
      title: "《紫微斗数全书》卷二·化忌星",
      text: "小限逢之一年不足，大限相遇十年悔吝，二限并太岁交临，断然蹭蹬。",
      file: "materials/06-紫微斗数/紫微斗数全书-知命书院本/013-卷二（6）.md#L30",
      level: "[原文]"
    },
    BZ_YS005: {
      title: "《三命通会》卷02·原有官财应期（rules/10-运岁.json YS-005）",
      text: "原有官/财/灾，则行相应运而发：命中有官则行官运发，有财则行财运发，有灾则行灾运应。",
      file: "rules/10-运岁.json YS-005；knowledge/06-四柱/精读笔记/精读-卷一至卷二.md R7.5",
      level: "[原文]"
    },
    BZ_YS009: {
      title: "《三命通会》卷02·太岁当生与游行（YS-009）",
      text: "当生太岁终身主、游行太岁主一年；太岁为君、大运为臣。",
      file: "rules/10-运岁.json YS-009",
      level: "[原文]"
    },
    BZ_YS011: {
      title: "《三命通会》卷02·真太岁与岁运并临（YS-011）",
      text: "真太岁（转趾煞）、征太岁、岁运并临（羊刃七煞凶）、日年相并（君子君臣庆会/常人凶）。",
      file: "rules/10-运岁.json YS-011",
      level: "[原文]"
    },
    BZ_YS004: {
      title: "《三命通会》卷02·用神行运喜忌（YS-004）",
      text: "官欲生、煞欲制、财欲扶、印欲旺、食欲生；反之为忌。",
      file: "rules/10-运岁.json YS-004",
      level: "[原文]"
    },
    BZ_YS013: {
      title: "《三命通会》·伏吟返吟（YS-013）",
      text: "大运/流年与日柱相同为伏吟；天克地冲为返吟。",
      file: "rules/10-运岁.json YS-013",
      level: "[原文]"
    },
    BZ_YS015: {
      title: "《三命通会》·晦气煞（YS-015）",
      text: "日/时干与太岁天元合为晦气煞。",
      file: "rules/10-运岁.json YS-015",
      level: "[原文]"
    },
    BZ_YS016: {
      title: "《三命通会》·大运与太岁克冲（YS-016）",
      text: "运克岁尤忌；岁克运不宜；运岁相冲不宜。",
      file: "rules/10-运岁.json YS-016",
      level: "[原文]"
    }
  };

  const SRC_ORDER = Object.keys(SOURCES);

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function fmtDate(d) {
    const y = d.getFullYear(), m = String(d.getMonth() + 1).padStart(2, "0"), dd = String(d.getDate()).padStart(2, "0");
    return y + "-" + m + "-" + dd;
  }

  // 1984-01-31 为甲子日（项目内六壬/四柱均以该锚点校验）
  const ANCHOR = Date.UTC(1984, 0, 31);
  function dayGz(date) {
    const d = new Date(date.getFullYear(), date.getMonth(), date.getDate(), 12, 0, 0);
    const idx = Math.round((Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) - ANCHOR) / 86400000);
    const i = ((idx % 60) + 60) % 60;
    return GAN[i % 10] + ZHI[i % 12];
  }

  function parseDate(s) {
    if (s instanceof Date) return new Date(s.getFullYear(), s.getMonth(), s.getDate(), 12);
    const m = String(s || "").match(/(\d{4})-(\d{1,2})-(\d{1,2})/);
    if (m) return new Date(+m[1], +m[2] - 1, +m[3], 12);
    const n = new Date();
    return new Date(n.getFullYear(), n.getMonth(), n.getDate(), 12);
  }

  function nextDatesForBranch(branch, base, days, limit) {
    days = days || 60; limit = limit || 8;
    const out = [];
    const b = parseDate(base);
    for (let i = 0; i <= days && out.length < limit; i++) {
      const d = new Date(b.getFullYear(), b.getMonth(), b.getDate() + i, 12);
      const gz = dayGz(d);
      if (gz[1] === branch) out.push({ date: fmtDate(d), gz: gz });
    }
    return out;
  }

  function nextDatesForElement(dayElement, base, days, limit) {
    // dayElement 为“日干五行”；找日支五行生我 / 克我 的日期。
    days = days || 60; limit = limit || 6;
    const out = { sheng: [], ke: [] };
    const b = parseDate(base);
    for (let i = 0; i <= days && (out.sheng.length < limit || out.ke.length < limit); i++) {
      const d = new Date(b.getFullYear(), b.getMonth(), b.getDate() + i, 12);
      const gz = dayGz(d);
      const wx = ZHI_WX[gz[1]];
      const rec = { date: fmtDate(d), gz: gz };
      if (SHENG[wx] === dayElement && out.sheng.length < limit) out.sheng.push(rec);
      if (KE[wx] === dayElement && out.ke.length < limit) out.ke.push(rec);
    }
    return out;
  }

  function signedDiff(a, b) {
    let d = (ZHI.indexOf(a) - ZHI.indexOf(b) + 12) % 12;
    if (d > 6) d -= 12;
    return d;
  }

  function yearZhi(year) {
    return ZHI[(((Number(year) - 4) % 12) + 12) % 12];
  }

  function srcLine(id) {
    const s = SOURCES[id];
    if (!s) return "";
    return "［" + s.title + "｜" + s.file + "｜" + s.level + "］";
  }

  /* ---------------- AI 门禁 ---------------- */
  function explicit(text) {
    const s = String(text || "");
    // 只认“明确问时间/应期”的词；不把单独的大运/流年当作应期请求。
    return /(应期|应验|验期|何时|什么时候|多久|几时|哪年|哪一年|何年|何月|何日|几年|几月|几日|几号|日期|时间点|期限|快慢|今年|明年|后年|本年|本月|下月|本周|下周|此期|该期|这期|运期)/.test(s);
  }

  function aiRule(allow) {
    const base = "【应期输出规则】默认不输出任何应期或时间推断：不得给出具体年份、月份、日期、期限、快慢、早晚，也不得把大运/流年写成“某年必应”。";
    if (allow) {
      return base + " 用户本轮已明确要求应期，可依据资料包中的“应期候选/应期规则”说明，但必须逐条标明出处与不确定性；资料包没有对应规则时直说“无可靠应期规则”，不得自行补造。";
    }
    return base + " 本轮用户未明确要求应期，请只讲结构、象义、条件与建议；大运/流年只作结构说明，不落具体应期。";
  }

  /* ---------------- 通用渲染 ---------------- */
  function render(el, data) {
    if (!el) return;
    if (!data) {
      el.innerHTML = '<div style="font-size:12px;opacity:.72">暂无可显示的应期数据。</div>';
      return;
    }
    if (data.error) {
      el.innerHTML = '<div style="font-size:12px;color:#a83a2e">应期计算未完成：' + esc(data.error) + "</div>";
      return;
    }
    const H = [];
    H.push('<div style="font-size:12px;opacity:.72;margin-bottom:6px">' +
      esc(data.title || "应期（规则候选）") +
      (data.base ? "｜基准 " + esc(data.base) : "") +
      '｜只列有出处的规则，不保证应验</div>');

    (data.sections || []).forEach(function (sec) {
      H.push('<div style="margin:8px 0 4px;font-weight:600;font-size:13px">' + esc(sec.title) + "</div>");
      (sec.items || []).forEach(function (it) {
        H.push('<div style="font-size:12.5px;line-height:1.7;margin:2px 0 2px 10px">· ' + esc(it.text) +
          (it.src ? ' <span style="opacity:.62;font-size:11.5px">［' + esc(it.src) + (it.level ? "｜" + esc(it.level) : "") + "］</span>" : "") +
          "</div>");
      });
    });

    if ((data.candidates || []).length) {
      H.push('<div style="margin:10px 0 4px;font-weight:600;font-size:13px">候选应期（规则命中）</div>');
      data.candidates.forEach(function (c) {
        const when = c.date || c.window || (c.year != null ? c.year + "年" : "");
        H.push('<div style="font-size:12.5px;line-height:1.7;margin:3px 0 3px 10px;padding:4px 8px;border-left:2px solid currentColor;opacity:.92">' +
          "<b>" + esc(when) + "</b>" + (c.gz ? "（" + esc(c.gz) + "）" : "") +
          "　" + esc(c.basis || "") +
          (c.src ? ' <span style="opacity:.62;font-size:11.5px">［' + esc(c.src) + (c.level ? "｜" + esc(c.level) : "") + "］</span>" : "") +
          "</div>");
      });
    }

    if ((data.notes || []).length) {
      H.push('<div style="margin:10px 0 4px;font-weight:600;font-size:13px">说明</div>');
      data.notes.forEach(function (n) {
        H.push('<div style="font-size:12px;line-height:1.65;margin:2px 0 2px 10px;opacity:.8">· ' + esc(n) + "</div>");
      });
    }
    if ((data.gaps || []).length) {
      H.push('<div style="margin:10px 0 4px;font-weight:600;font-size:13px">资料缺口（未写入）</div>');
      data.gaps.forEach(function (g) {
        H.push('<div style="font-size:12px;line-height:1.65;margin:2px 0 2px 10px;opacity:.72">· ' + esc(g) + "</div>");
      });
    }
    el.innerHTML = H.join("");
  }

  function plain(data) {
    if (!data || data.error) return "";
    const L = [];
    L.push(data.title || "应期（规则候选）");
    (data.sections || []).forEach(function (sec) {
      L.push("【" + sec.title + "】");
      (sec.items || []).forEach(function (it) {
        L.push("· " + it.text + (it.src ? "［" + it.src + (it.level ? "｜" + it.level : "") + "］" : ""));
      });
    });
    if ((data.candidates || []).length) {
      L.push("【候选应期】");
      data.candidates.forEach(function (c) {
        const when = c.date || c.window || (c.year != null ? c.year + "年" : "");
        L.push("· " + when + (c.gz ? "（" + c.gz + "）" : "") + "：" + (c.basis || "") +
          (c.src ? "［" + c.src + (c.level ? "｜" + c.level : "") + "］" : ""));
      });
    }
    (data.notes || []).forEach(function (n) { L.push("说明：" + n); });
    (data.gaps || []).forEach(function (g) { L.push("缺口：" + g); });
    return L.join("\n");
  }

  /* ---------------- 六壬 ---------------- */
  function liuren(r, ex, zhan, baseDate) {
    if (!r || !r.chuan || !r.chuan.length) return { error: "课盘缺少三传" };
    const base = parseDate(baseDate);
    const fa = r.chuan[0].支;
    const dayGzStr = r.day || "";
    const dayZhi = dayGzStr[1] || "";
    const dayGan = dayGzStr[0] || "";
    const yearZ = yearZhi(r.year || new Date().getFullYear());
    const monthZ = r.mj || "";
    const xunZ = (r.xi && r.xi.head) ? r.xi.head[1] : "";
    const kong = (r.xi && r.xi.kong) ? r.xi.kong.join("、") : "—";

    const sections = [];
    const items = [];
    items.push({ text: "占日 " + dayGzStr + "，发用 " + fa + "；月建 " + monthZ + "，太岁支 " + yearZ + "，旬首 " + (r.xi ? r.xi.head : "—") + "，空亡 " + kong, src: "课盘事实" });
    let matched = false;
    if (fa === yearZ) { matched = true; items.push({ text: "发用支＝太岁支（" + fa + "）：用起太岁，事在一年内（应一年）。", src: "六壬大全 020#L36｜QD-123", level: "[原文]" }); }
    if (fa === monthZ) { matched = true; items.push({ text: "发用支＝月建支（" + fa + "）：斗建发用，事在本月内（应一月）。", src: "六壬大全 020#L36｜QD-123", level: "[原文]" }); }
    if (fa === dayZhi) { matched = true; items.push({ text: "发用支＝日支（" + fa + "）：用日应当日，事应在今日。", src: "六壬大全 020#L36｜QD-123", level: "[原文]" }); }
    if (!matched) {
      items.push({ text: "发用支 " + fa + " 不直太岁/月建/日支；原文应期分年/月/旬/日/气/候/时七层，本工具不强行裁定，需再结合节气与占时取用。", src: "六壬大全 020#L36｜QD-123", level: "[原文]" });
    }
    items.push({ text: "原文另有“传辰应一旬”一层；‘传辰’所指（旬首或三传地支）诸家用法不一，本工具只列三传地支（" + r.chuan.map(function (c) { return c.支; }).join("、") + "）供人工取用，不自动定应。", src: "六壬大全 020#L36｜QD-123", level: "[原文]" });
    sections.push({ title: "一、发用定应期层级", items: items });

    const diff = signedDiff(fa, dayZhi);
    let qianhou;
    if (diff === 0) qianhou = "发用即日支，事应在今时。";
    else if (Math.abs(diff) === 6) qianhou = "发用支与日支相对（六位），前后难判；原文要求“应期之法却当活论”，本工具不强行定先后。";
    else if (diff > 0) qianhou = "用居日后（发用支在日支后 " + diff + " 位），事起将来，主事在未来。";
    else qianhou = "用在日前（发用支在日支前 " + (-diff) + " 位），事已过，主事已发生或已启动。";
    sections.push({ title: "二、发用前后", items: [{ text: qianhou, src: "注解大六壬指南 009#L90｜ZN-058", level: "[原文]" }] });

    const dayWx = GAN_WX[dayGan] || "";
    const ri = nextDatesForElement(dayWx, base, 60, 5);
    const riItems = [];
    if (ri.sheng.length) riItems.push({ text: "若课判吉：取“生我”之日为应日——" + ri.sheng.map(function (x) { return x.date + "（" + x.gz + "）"; }).join("、"), src: "六壬大全 020#L48", level: "[原文]" });
    if (ri.ke.length) riItems.push({ text: "若课判凶：取“克我”之日为应日——" + ri.ke.map(function (x) { return x.date + "（" + x.gz + "）"; }).join("、"), src: "六壬大全 020#L48", level: "[原文]" });
    riItems.push({ text: "原文只说“吉卦以生今日者为应日，凶卦以克今日者为应日”；课体吉凶须先由课体、类神、旺衰判定，不可倒果为因。", src: "六壬大全 020#L48", level: "[原文]" });
    sections.push({ title: "三、吉凶应日", items: riItems });

    const faDates = nextDatesForBranch(fa, base, 60, 4);
    const candidates = faDates.map(function (x) {
      return { date: x.date, gz: x.gz, basis: "发用支 " + fa + " 值日；仅作“用日应当日”的核对候选", src: "六壬大全 020#L36", level: "[原文]" };
    });

    const notes = [
      "应期以发用为核心；三传、类神、神煞可作辅证，但本工具不把未列明的组合写成定应。",
      "“用起太岁应一年、斗建应一月、传辰应一旬、用日应当日、气首应半月、候应五日、时应八刻”为原文分层，实际取用须结合占事远近。",
      "神煞与类神数目应期（如邵彦和数法）未纳入自动计算，须人工按占类取用。"
    ];
    const gaps = [
      "六壬“气首/候/时”三层需要节气与时辰的精确起算，本项目未建立可核对的自动表，未写入。",
      "空亡填实、冲空等应期说法在已收录文本中未形成统一可编码规则，未写入。"
    ];
    return { tool: "六壬", title: "大六壬应期（规则候选）", base: fmtDate(base), sections: sections, candidates: candidates, notes: notes, gaps: gaps };
  }

  /* ---------------- 紫微 ---------------- */
  const BR = ["寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥", "子", "丑"];
  const XIAO_START = { 寅: "辰", 午: "辰", 戌: "辰", 申: "戌", 子: "戌", 辰: "戌", 巳: "未", 酉: "未", 丑: "未", 亥: "丑", 卯: "丑", 未: "丑" };
  const ZW_GAN = "甲乙丙丁戊己庚辛壬癸";

  function ziwei(a, opts) {
    if (!a || !a.palaces) return { error: "命盘数据不完整" };
    opts = opts || {};
    const mingP = a.palaces.find(function (p) { return p.name === "命宫"; });
    if (!mingP) return { error: "未找到命宫" };
    const startAge = mingP.decadal.range[0];
    const n = opts.daxian || 1;
    const dp = a.palaces.find(function (p) { return p.decadal.range[0] === startAge + 10 * (n - 1); });
    if (!dp) return { error: "未找到当前大限" };
    const birthYear = a.rawDates && a.rawDates.lunarDate ? a.rawDates.lunarDate.lunarYear : null;
    const range = dp.decadal.range;
    const startYear = birthYear ? birthYear + range[0] - 1 : null;
    const endYear = birthYear ? birthYear + range[1] - 1 : null;
    const nowYear = opts.lnYear || new Date().getFullYear();

    const sections = [];
    const dItems = [];
    dItems.push({
      text: "第" + n + "限（" + range[0] + "–" + range[1] + "岁）在 " + dp.earthlyBranch + "宫（本命" + dp.name + "）" +
        (startYear ? "，约 " + startYear + "–" + endYear + " 年" : "") + "；大限以十年为一段。",
      src: "紫微斗数全书 017#L140-L142｜ZW_DAXIAN", level: "[原文]"
    });
    if (startYear) {
      dItems.push({ text: "北斗诸星：大限断上五年应（约 " + startYear + "–" + (startYear + 4) + " 年）。", src: "紫微斗数全书 017#L150｜ZW_NANBEI", level: "[原文]" });
      dItems.push({ text: "南斗诸星：大限断下五年应（约 " + (startYear + 5) + "–" + endYear + " 年）。", src: "紫微斗数全书 017#L150｜ZW_NANBEI", level: "[原文]" });
      if (nowYear === endYear) dItems.push({ text: "今年为第" + n + "限最后一年，原文谓“大限将出”：有吉众者无灾悔，少者灾多、损人破财不利。", src: "紫微斗数全书 017#L142｜ZW_DAXIAN", level: "[原文]" });
    } else {
      dItems.push({ text: "命盘未提供农历生年，无法换算大限公历年份；只列岁数区间。", src: "命盘事实" });
    }
    sections.push({ title: "一、大限分应", items: dItems });

    const lItems = [];
    let xiaoxian = null;
    if (opts.lnYear) {
      const y = opts.lnYear;
      const lnStem = ZW_GAN[((y - 4) % 10 + 10) % 10];
      const lnBr = yearZhi(y);
      lItems.push({ text: "流年 " + y + "（" + lnStem + lnBr + "）：流年太岁主一年；太岁在命宫行者祸福尤紧。", src: "紫微斗数全书 013#L52｜ZW_SUIJUN", level: "[原文]" });
      if (birthYear) {
        const xuNian = y - birthYear + 1;
        const byb = (a.rawDates && a.rawDates.chineseDate) ? a.rawDates.chineseDate.yearly[1] : "";
        const xs = XIAO_START[byb] || "辰";
        const idx = BR.indexOf(xs) + (a.gender === "男" ? 1 : -1) * (xuNian - 1);
        xiaoxian = BR[((idx % 12) + 12) % 12];
        const xxPal = a.palaces.find(function (p) { return p.earthlyBranch === xiaoxian; });
        lItems.push({ text: "小限在 " + xiaoxian + " 宫（本命" + (xxPal ? xxPal.name : "—") + "，虚岁 " + xuNian + "）：北斗诸星小限断上半年，南斗诸星小限断下半年。", src: "紫微斗数全书 017#L150｜ZW_NANBEI", level: "[原文]" });
        if (lnBr === xiaoxian || lnBr === dp.earthlyBranch) {
          lItems.push({ text: "流年支与" + (lnBr === dp.earthlyBranch ? "大限宫" : "小限") + "同位：原文谓“二限并太岁交临，断然蹭蹬”，只作提醒，不直接断凶。", src: "紫微斗数全书 013#L30｜ZW_JI", level: "[原文]" });
        }
      }
    } else {
      lItems.push({ text: "未填流年：只列大限分应；在顶部输入流年后可补流年/小限的层级。", src: "操作提示" });
    }
    sections.push({ title: "二、流年与小限", items: lItems });

    const candidates = [];
    if (opts.lnYear) {
      const y = opts.lnYear;
      candidates.push({ year: y, gz: ZW_GAN[((y - 4) % 10 + 10) % 10] + yearZhi(y), basis: "流年太岁主一年；只作年度层级，不精确到月日。", src: "紫微斗数全书 013#L52", level: "[原文]" });
    }
    if (startYear) {
      candidates.push({ window: startYear + "–" + (startYear + 4) + "年", basis: "北斗诸星大限上五年应。", src: "紫微斗数全书 017#L150", level: "[原文]" });
      candidates.push({ window: (startYear + 5) + "–" + endYear + "年", basis: "南斗诸星大限下五年应。", src: "紫微斗数全书 017#L150", level: "[原文]" });
    }

    const notes = [
      "紫微斗数的“应期”在《紫微斗数全书》中主要落实为大限十年、上/下五年、小限上/下半年、流年一年四级；没有统一的流月/流日应期表。",
      "上/下五年与上/下半年是“分应”层级，原文未逐星列出具体应期，不能据此精确到单星或单日。",
      "二限并太岁、大限将出等为条件提示，不等于事件必然发生；须合三方四正、四化与现实中因。"
    ];
    const gaps = [
      "流月/流日应期：本书未列可编码的统一表，未写入。",
      "流年昌曲科甲、流曜逐星应期等条件断语未自动判定，未写入。",
      "大限上/下五年只到“北斗/南斗诸星”层级，未逐星拆分，未写入单星应期。"
    ];
    return { tool: "紫微", title: "紫微斗数应期（运限层级）", base: String(nowYear), sections: sections, candidates: candidates, notes: notes, gaps: gaps };
  }

  global.YQ = {
    GAN: GAN, ZHI: ZHI, GAN_WX: GAN_WX, ZHI_WX: ZHI_WX,
    SOURCES: SOURCES, SRC_ORDER: SRC_ORDER,
    esc: esc, fmtDate: fmtDate, dayGz: dayGz, parseDate: parseDate,
    nextDatesForBranch: nextDatesForBranch, nextDatesForElement: nextDatesForElement,
    explicit: explicit, aiRule: aiRule,
    render: render, plain: plain, srcLine: srcLine,
    liuren: liuren, ziwei: ziwei
  };
})(typeof window !== "undefined" ? window : globalThis);
