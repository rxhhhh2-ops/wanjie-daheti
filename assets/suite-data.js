/* 万界大合体 · 共享数据层
 *
 * 职责：把「一项数据」与「能消费它的工具」解耦。
 *   - 命主（ming）：出生日期时间 + 性别      → 四柱、紫微（六壬可取生年作年命）
 *   - 占事（zhan）：占测日期时间 + 所问之事  → 梅花、奇门、六壬
 *
 * 数据存于 localStorage['suite-data-v1']，与既有各页 AI 配置键互不干扰。
 * 跨页传递一律走 URL 查询参数（见 buildUrl），页面侧由 suite-bridge.js 解释；
 * 不带参数访问任何页面时，行为与改造前完全一致。
 */
(function () {
  'use strict';

  var KEY = 'suite-data-v1';

  var TOOLS = [
    { id: 'bazi',   name: '四柱排盘', short: '四柱', kind: 'ming', url: '/bazi/',
      needs: '出生时间 + 性别', desc: '藏干十神 · 格局用神 · 大运流年' },
    { id: 'ziwei',  name: '紫微斗数', short: '紫微', kind: 'ming', url: '/ziwei/',
      needs: '出生时间 + 性别', desc: '十二宫垣 · 十四主星 · 四化飞星' },
    { id: 'meihua', name: '梅花易数', short: '梅花', kind: 'zhan', url: '/meihua/',
      needs: '占测时间 + 所问', desc: '年月日时起卦 · 体用互变 · 万物类象' },
    { id: 'qimen',  name: '奇门遁甲', short: '奇门', kind: 'zhan', url: '/qimen/',
      needs: '占测时间 + 所问', desc: '时家奇门 · 九宫三盘 · 格局断语' },
    { id: 'liuren', name: '大六壬',   short: '六壬', kind: 'zhan', url: '/liuren/',
      needs: '占测时间 + 所问', desc: '四课三传 · 九宗门 · 课体神煞' }
  ];

  var DT_RE = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/;

  function blank() {
    return {
      ming: { name: '', gender: '男', dt: '', place: '' },
      zhan: { dt: '', question: '' },
      updatedAt: 0
    };
  }

  function load() {
    var d = blank();
    try {
      var raw = JSON.parse(localStorage.getItem(KEY) || 'null');
      if (raw && typeof raw === 'object') {
        ['ming', 'zhan'].forEach(function (k) {
          if (raw[k] && typeof raw[k] === 'object') {
            Object.keys(d[k]).forEach(function (f) {
              if (raw[k][f] != null) d[k][f] = String(raw[k][f]);
            });
          }
        });
        d.updatedAt = Number(raw.updatedAt) || 0;
      }
    } catch (e) {}
    return d;
  }

  function save(data) {
    data.updatedAt = Date.now();
    try { localStorage.setItem(KEY, JSON.stringify(data)); } catch (e) {}
    try { window.dispatchEvent(new CustomEvent('suite-datachange', { detail: data })); } catch (e) {}
    return data;
  }

  /* 部分更新某一类数据，返回完整数据对象 */
  function set(kind, patch) {
    var d = load();
    if (!d[kind]) return d;
    Object.keys(patch || {}).forEach(function (k) { d[kind][k] = patch[k]; });
    return save(d);
  }

  function get(kind) { return load()[kind] || {}; }

  /* 规范为 datetime-local 需要的 YYYY-MM-DDTHH:MM；非法输入返回空串 */
  function normDt(s) {
    var m = DT_RE.exec(String(s || '').trim());
    if (!m) return '';
    return m[1] + '-' + m[2] + '-' + m[3] + 'T' + m[4] + ':' + m[5];
  }

  function nowLocal() {
    var n = new Date();
    function p(x) { return (x < 10 ? '0' : '') + x; }
    return n.getFullYear() + '-' + p(n.getMonth() + 1) + '-' + p(n.getDate()) +
      'T' + p(n.getHours()) + ':' + p(n.getMinutes());
  }

  function dtParts(s) {
    var v = normDt(s);
    if (!v) return null;
    return {
      dt: v,
      date: v.slice(0, 10),
      time: v.slice(11, 16),
      year: Number(v.slice(0, 4)),
      month: Number(v.slice(5, 7)),
      day: Number(v.slice(8, 10)),
      hour: Number(v.slice(11, 13)),
      minute: Number(v.slice(14, 16))
    };
  }

  /* 紫微时辰：0 早子 / 1-11 丑…亥 / 12 晚子 */
  function hourToShichen(h) {
    if (h === 23) return 12;
    if (h === 0) return 0;
    return Math.floor((h + 1) / 2);
  }

  /* 逆映射：紫微时辰序号 → 代表性小时（早子 00、晚子 23，其余取区间首小时） */
  function shichenToHour(sc) {
    sc = Number(sc);
    if (sc === 0) return 0;
    if (sc === 12) return 23;
    return sc * 2 - 1;
  }

  /*
   * 工具页回流：把页面采集到的值合并进共享数据。
   * 语义——只写「工具刚排过盘」的那类数据（ming 或 zhan），另一类不动；
   * embed iframe 里的页面不该写回（portal 侧负责），由调用方先判断。
   * 返回完整数据对象；没有任何可写字段时返回 null。
   */
  function mergeFromTool(kind, patch) {
    if (kind !== 'ming' && kind !== 'zhan') return null;
    var clean = {};
    Object.keys(patch || {}).forEach(function (k) {
      var v = patch[k];
      if (v == null) return;
      if (k === 'dt') {
        v = normDt(v);
        if (!v) return;
      } else {
        v = String(v);
        if (!v) return;
      }
      clean[k] = v;
    });
    if (!Object.keys(clean).length) return null;
    var d = load();
    if (!d[kind]) return null;
    Object.keys(clean).forEach(function (k) { d[kind][k] = clean[k]; });
    return save(d);
  }

  function toolsFor(kind) {
    return TOOLS.filter(function (t) { return t.kind === kind; });
  }

  function tool(id) {
    return TOOLS.filter(function (t) { return t.id === id; })[0] || null;
  }

  /*
   * 构造工具页 URL。opts: { auto:true|false, embed:true|false }
   * data 为完整数据对象（含 ming/zhan），便于六壬在占事时借用命主生年作年命。
   */
  function buildUrl(id, data, opts) {
    var t = tool(id);
    if (!t) return '/';
    opts = opts || {};
    data = data || load();
    var src = data[t.kind] || {};
    var p = dtParts(src.dt);
    var q = new URLSearchParams();

    if (t.kind === 'ming') {
      if (!p) return t.url;                 // 缺生辰则不携带参数，交还页面手动填写
      if (id === 'bazi' || id === 'ziwei') {
        q.set('dt', p.dt);
        if (src.gender) q.set('gender', src.gender);
      }
    } else {
      if (!p) return t.url;
      if (id === 'meihua') {
        q.set('mode', 'dt');                // 复用梅花原生 applyQuery 契约
        q.set('dt', p.dt);
        if (src.question) q.set('question', src.question);
      } else if (id === 'qimen') {
        q.set('dt', p.dt);
        if (src.question) q.set('question', src.question);
      } else if (id === 'liuren') {
        q.set('date', p.date);
        q.set('time', p.time);
        if (src.question) q.set('question', src.question);
        var ming = data.ming || {};
        var mp = dtParts(ming.dt);          // 年命：有命主数据则顺带填入
        if (mp) q.set('birth', String(mp.year));
        if (ming.gender) q.set('sex', ming.gender);
      }
    }

    if (opts.auto) q.set('auto', '1');
    if (opts.embed) q.set('embed', '1');
    var s = q.toString();
    return t.url + (s ? '?' + s : '');
  }

  /* 多工具合参：保持用户勾选顺序，去重 */
  function buildMany(ids, data, opts) {
    var seen = {};
    return (ids || []).filter(function (id) {
      if (seen[id] || !tool(id)) return false;
      seen[id] = true;
      return true;
    }).map(function (id) {
      var t = tool(id);
      return { id: id, name: t.name, short: t.short, url: buildUrl(id, data, opts) };
    });
  }

  window.SuiteData = {
    KEY: KEY,
    TOOLS: TOOLS,
    load: load,
    save: save,
    set: set,
    get: get,
    normDt: normDt,
    nowLocal: nowLocal,
    dtParts: dtParts,
    hourToShichen: hourToShichen,
    shichenToHour: shichenToHour,
    mergeFromTool: mergeFromTool,
    toolsFor: toolsFor,
    tool: tool,
    buildUrl: buildUrl,
    buildMany: buildMany
  };
})();
