/* 万界大合体 · 页面接入桥
 *
 * 在五个工具页末尾以 defer 引入。做三件事：
 *   1. embed=1：标记嵌入模式（suite.js 据此不再注入全局导航，避免合参视图里出现五层导航）。
 *   2. 下行：把 URL 上的共享数据翻译成本页表单，并在 auto=1 时触发一次排盘。
 *   3. 上行（回流）：页面主动排盘 / 修改字段后，把本页输入写回共享数据层
 *      （localStorage['suite-data-v1']），首页下次打开自动回填最新值。
 *      回流只发生在「用户亲手操作」的独立页；embed iframe 内不写回，避免合参面板互相覆盖。
 *
 * 不带任何参数访问时，除回流外不动页面；回流也只写共享键，不碰各页原有存储。
 * 梅花页自带 initFromURL（?mode=dt&dt=… 即自动起卦），下行无需在此适配。
 */
(function () {
  'use strict';

  var qs = new URLSearchParams(location.search);
  if (qs.get('embed') === '1') {
    document.documentElement.setAttribute('data-embed', '1');
  }
  if (!window.SuiteData) return;

  var page = document.documentElement.getAttribute('data-page') || '';
  var SD = window.SuiteData;
  var EMBED = qs.get('embed') === '1';

  function el(id) { return document.getElementById(id); }
  function setVal(id, v) {
    var n = el(id);
    if (!n || v == null || v === '') return false;
    n.value = v;
    try { n.dispatchEvent(new Event('change', { bubbles: true })); } catch (e) {}
    return true;
  }
  /* 下拉类字段：仅当取值确实存在于选项中才设置，避免写入非法值 */
  function setOption(id, v) {
    var n = el(id);
    if (!n || !v) return false;
    var hit = Array.prototype.some.call(n.options, function (o) {
      return o.value === v || o.text === v;
    });
    if (!hit) return false;
    n.value = v;
    try { n.dispatchEvent(new Event('change', { bubbles: true })); } catch (e) {}
    return true;
  }
  function click(id) {
    var n = el(id);
    if (n) { n.click(); return true; }
    return false;
  }

  /* ================= 下行：URL → 表单 ================= */

  /* 返回 true 表示本页识别到了数据参数 */
  function fill() {
    var p = SD.dtParts(qs.get('dt') || (qs.get('date') + 'T' + qs.get('time')));
    var gender = qs.get('gender') || qs.get('sex') || '';

    if (page === 'bazi') {
      if (!p) return false;
      setVal('dt', p.dt);
      var btn = el('dtBtn');                 // 该页用自定义选时器，按钮文本需同步
      if (btn) btn.textContent = p.dt.replace('T', ' ');
      setOption('gender', gender);
      return true;
    }

    if (page === 'ziwei') {
      if (!p) return false;
      setVal('dt', p.dt);
      var zwBtn = el('dtBtn');               // 紫微页也用选时器按钮文本
      if (zwBtn) zwBtn.textContent = p.dt.replace('T', ' ');
      setOption('g', gender);
      return true;
    }

    if (page === 'qimen') {
      if (!p) return false;
      setVal('dt', p.dt);
      setOption('question', qs.get('question'));
      return true;
    }

    if (page === 'liuren') {
      var d = qs.get('date'), t = qs.get('time');
      if (!d && !p) return false;
      if (d) setVal('lp-date', d);
      if (t) setVal('lp-time', t);
      if (!d && p) { setVal('lp-date', p.date); setVal('lp-time', p.time); }
      setOption('lp-zhan', qs.get('question'));
      setVal('lp-birth', qs.get('birth'));   // 年命：来自共享命主数据
      setOption('lp-sex', qs.get('sex'));
      return true;
    }

    return false;                            // meihua 走页面原生 initFromURL
  }

  function run() {
    if (page === 'bazi') {
      if (typeof window.paipan === 'function') window.paipan();
      return;
    }
    if (page === 'ziwei') { click('btnGo'); return; }
    if (page === 'qimen') { click('run'); return; }
    if (page === 'liuren') { click('lp-go'); return; }
  }

  /* ================= 上行：表单 → 共享数据 =================
   * 每页一个采集器：从本页控件读当前值，映射回 ming / zhan 两类字段。
   * 写回节流：排盘动作后 120ms 写一次；字段 change 后 500ms 合并写一次
   *（连续敲字/滚动年月不产生中间态）。
   */
  var KIND = { bazi: 'ming', ziwei: 'ming', meihua: 'zhan', qimen: 'zhan', liuren: 'zhan' };

  /* 只有用户真正动过页面（点/键/改）才回写：
   * 各页首次载入都会自动排一次默认盘，若不加闸门，打开 /bazi/ 就会用默认 1984 生辰
   * 覆盖共享数据里的命主——这正是「数据被静默改写」的典型事故。 */
  var armed = false;
  function arm() { armed = true; }
  ['pointerdown', 'keydown', 'wheel'].forEach(function (ev) {
    document.addEventListener(ev, arm, { once: true, capture: true, passive: true });
  });

  function val(id) { var n = el(id); return n ? String(n.value == null ? '' : n.value) : ''; }

  /* 采集器返回 patch；dt 统一给 YYYY-MM-DDTHH:MM（由 mergeFromTool 再规范化一次） */
  var COLLECT = {
    bazi: function () {
      var dtv = val('dt');
      return { dt: dtv, gender: val('gender') || '' };
    },
    ziwei: function () {
      var dtv = val('dt');
      return { dt: dtv, gender: val('g') || '' };
    },
    meihua: function () {
      if (curModeText !== 'dt') return null;          // 仅时间起卦与共享口径一致
      var dtv = null;
      var n = el('f_dt');
      if (n && n.value) dtv = n.value;
      return { dt: dtv || '', question: val('question') };
    },
    qimen: function () {
      return { dt: val('dt'), question: val('question') };
    },
    liuren: function () {
      var date = val('lp-date'), time = val('lp-time') || '12:00';
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return null;
      if (!/^\d{2}:\d{2}/.test(time)) time = '12:00';
      var patch = { dt: date + 'T' + time.slice(0, 5), question: val('lp-zhan') };
      return patch;
    }
  };
  var curModeText = 'dt';                              // 梅花：由页面切换钩子更新

  function pushBack(kind, patch) {
    if (!patch || Object.keys(patch).length === 0) return;
    try {
      SD.mergeFromTool(kind, patch);
    } catch (e) {}
  }

  var writeTimer = null;
  function writeNow() {
    if (EMBED || !armed || !COLLECT[page]) return;
    var patch;
    try { patch = COLLECT[page](); } catch (e) { return; }
    if (patch) pushBack(KIND[page], patch);
  }
  function scheduleWrite() {
    if (EMBED || !COLLECT[page]) return;
    if (writeTimer) clearTimeout(writeTimer);
    writeTimer = setTimeout(function () { writeTimer = null; writeNow(); }, 500);
  }

  /* 排盘动作：短暂延迟，确保采集的是「触发排盘」时的最终输入 */
  function hookAction(fnName) {
    var fn;
    try { fn = window[fnName]; } catch (e) { return; }
    if (typeof fn !== 'function' || fn.__suiteHooked) return;
    var wrapped = function () {
      var r = fn.apply(this, arguments);
      setTimeout(function () { writeNow(); }, 120);
      return r;
    };
    wrapped.__suiteHooked = true;
    try { window[fnName] = wrapped; } catch (e) {}
  }

  /* 监听字段变化用事件委托：梅花页切换起卦方式会重建字段节点，
   * 直接绑定会在换模式后失效（旧节点被丢弃），委托到 document 才稳。 */
  var WATCH = {
    bazi: ['dt', 'gender'],
    ziwei: ['dt', 'g'],
    meihua: ['question', 'f_dt'],
    qimen: ['dt', 'question'],
    liuren: ['lp-date', 'lp-time', 'lp-zhan']
  };

  function bindInputs() {
    if (EMBED || !COLLECT[page]) return;
    var ids = WATCH[page] || [];
    function onEdit(e) {
      var t = e.target;
      if (t && t.id && ids.indexOf(t.id) >= 0) scheduleWrite();
    }
    document.addEventListener('change', onEdit, true);
    document.addEventListener('input', onEdit, true);
  }

  var hasData = fill();
  if (hasData && qs.get('auto') === '1') {
    // 等页面自身脚本完成初始化后再触发，避免抢在事件绑定之前
    setTimeout(run, 60);
  }

  if (!EMBED) {
    // 排盘动作回流。注意两点：
    //  - bazi 的按钮是内联 onclick="paipan()"，运行时按全局名解析，钩 window 函数有效；
    //    applyPicker（选时器确定）内部同样调用全局 paipan，一并覆盖。
    //  - 其余各页是 `btn.onclick = fn` 绑定了原函数引用，钩 window 无效，
    //    改为监听按钮 click（捕获阶段，先于/独立于页面处理器），延时读取表单值。
    if (page === 'bazi') hookAction('paipan');

    var actionBtns = {
      ziwei:  ['btnGo'],
      qimen:  ['run', 'now'],
      meihua: ['castBtn', 'quickCast'],
      liuren: ['lp-go']
    };
    (actionBtns[page] || []).forEach(function (id) {
      var n = el(id);
      if (!n) return;
      n.addEventListener('click', function () {
        setTimeout(function () { writeNow(); }, 120);
      });
    });

    bindInputs();

    // 梅花模式切换：钩住 #modes 按钮容器，记录当前模式 id
    var modeBox = document.getElementById('modes');
    if (modeBox) {
      modeBox.addEventListener('click', function (e) {
        var b = e.target.closest('button[data-id]');
        if (!b) return;
        curModeText = b.getAttribute('data-id');
        scheduleWrite();
      });
      var on = modeBox.querySelector('button.on[data-id], button[data-id].on');
      if (on) curModeText = on.getAttribute('data-id') || 'dt';
    }
  }

  /* ================= 导出：window.SuiteExport =================
   * 合参视图（首页 iframe）需要一个统一的「取文本」出口：
   *   SuiteExport.text()  → 本页盘面的人类可读报告（无则空串）
   *   SuiteExport.meta()  → { title, ok }，供合参页拼接表头
   * 各页实现尽量复用已有的报告函数；无报告函数的页面按关键节点取文本。
   * 独立页同样可用（console / 控制台调用），但主要消费者是首页合参面板。
   */
  function textOf(id) {
    var n = el(id);
    return n ? (n.innerText || n.textContent || '') : '';
  }

  var EXPORT = {
    bazi: function () {
      var out = textOf('out');
      var head = '【四柱排盘】' + (val('dt') ? val('dt').replace('T', ' ') : '');
      return out ? head + '\n' + out : '';
    },
    ziwei: function () {
      // __astro 是脚本级 let，需按裸名引用；未排盘（占位文本）则不出报告
      var astro = (typeof __astro !== 'undefined') ? __astro : null;
      if (!astro) return '';
      var jp = el('jpBody');
      if (!jp || /排盘后/.test(jp.textContent || '')) return '';
      var head = '【紫微斗数】' + (astro.solarDate || '') + ' ' + (astro.time || '') +
        ' ' + (astro.gender ? (astro.gender + '命') : '') +
        '（' + (astro.chineseDate || astro.lunarDate || '') + '）';
      return head + '\n' + (jp.innerText || '');
    },
    meihua: function () {
      // 梅花页同样用脚本级 let lastState / function report，按裸名访问
      try {
        if (typeof report === 'function' && typeof lastState !== 'undefined' && lastState) {
          return report();
        }
      } catch (e) {}
      return '';
    },
    qimen: function () {
      // 奇门页的盘面存在脚本级 `let DATA`（不是 window 属性），需按裸名引用
      if (typeof DATA === 'undefined' || !DATA || !DATA.chart) return '';
      var c = DATA.chart, t = c.term || {}, fp = c.four_pillars || {};
      var head = '【奇门遁甲】' + (fp.year || '') + ' ' + (fp.month || '') + ' ' +
        (fp.day || '') + ' ' + (fp.hour || '') +
        '（' + (t.dun || '') + '遁' + (t.ju || '') + '局 · ' + (t.ju_term || '') + (t.yuan || '') + '元）';
      var v = (DATA.interpret && DATA.interpret.verdict) || null;
      if (v) head += '　倾向：' + v.level + '（' + (v.score > 0 ? '+' : '') + v.score + '）';
      var body = textOf('summary') + '\n' + textOf('pane-jie') + '\n' + textOf('pane-ge');
      return head + '\n' + body.trim();
    },
    liuren: function () {
      var info = textOf('lp-info');
      if (!info) return '';
      var head = '【大六壬】';
      var body = info + '\n' + textOf('lp-detail') + '\n' + textOf('lp-side') + '\n' + textOf('lp-jie');
      return head + '\n' + body.trim();
    }
  };

  window.SuiteExport = {
    text: function () {
      var fn = EXPORT[page];
      if (!fn) return '';
      try { return String(fn() || '').trim(); } catch (e) { return ''; }
    },
    meta: function () {
      var t = null;
      SD.TOOLS.forEach(function (x) { if (x.id === page) t = x; });
      var self = this;
      return {
        id: page,
        name: t ? t.name : page,
        ok: (function () { try { return !!self.text(); } catch (e) { return false; } })()
      };
    }
  };
})();
