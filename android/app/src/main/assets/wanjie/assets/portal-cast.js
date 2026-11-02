/* 万界大合体 · 首页「合一推演」
 *
 * 一项数据 → 一个或多个工具：
 *   单选：跳转到该工具页（auto=1，自动排盘），保留其全部功能；
 *   多选：在本页下方生成合参面板，每个工具一个 iframe（embed=1），同屏对照。
 * 数据写入 SuiteData，下次进入自动回填；不占新路由，不改后端。
 */
(function () {
  'use strict';
  if (!window.SuiteData) return;
  var SD = window.SuiteData;
  var host = document.getElementById('suite-cast');
  if (!host) return;

  var kind = 'ming';
  var picked = {};
  var data = SD.load();

  function el(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  /* ---------- 表单 ---------- */
  function fillForm() {
    el('cf-dt-ming').value = SD.normDt(data.ming.dt) || '';
    el('cf-gender').value = data.ming.gender || '男';
    el('cf-dt-zhan').value = SD.normDt(data.zhan.dt) || SD.nowLocal();
    el('cf-question').value = data.zhan.question || '';
  }

  function readForm() {
    if (kind === 'ming') {
      data = SD.set('ming', {
        dt: SD.normDt(el('cf-dt-ming').value),
        gender: el('cf-gender').value
      });
    } else {
      data = SD.set('zhan', {
        dt: SD.normDt(el('cf-dt-zhan').value) || SD.nowLocal(),
        question: el('cf-question').value.trim()
      });
    }
    return data;
  }

  /* ---------- 工具勾选 ---------- */
  function renderTools() {
    var list = SD.toolsFor(kind);
    var box = el('cf-tools');
    box.innerHTML = list.map(function (t) {
      return '<button type="button" class="cf-tool' + (picked[t.id] ? ' on' : '') +
        '" data-id="' + t.id + '" aria-pressed="' + (!!picked[t.id]) + '">' +
        '<b>' + esc(t.short) + '</b><span>' + esc(t.desc) + '</span></button>';
    }).join('');
    var n = list.filter(function (t) { return picked[t.id]; }).length;
    el('cf-count').textContent = '已选 ' + n + ' / ' + list.length + ' 个工具';
    el('cf-hint').textContent = n > 1
      ? '多选：在本页下方同屏对照，每个工具都可单独打开完整页面。'
      : '单选：直接进入该工具的完整页面并自动排盘。';
  }

  function defaultPick() {
    picked = {};
    SD.toolsFor(kind).forEach(function (t) { picked[t.id] = true; });
  }

  host.querySelector('.cast-kind').addEventListener('click', function (e) {
    var b = e.target.closest('button[data-kind]');
    if (!b) return;
    readForm();                                   // 切换前先留住当前输入
    kind = b.getAttribute('data-kind');
    host.querySelectorAll('.cast-kind button').forEach(function (x) {
      x.classList.toggle('on', x === b);
    });
    el('cf-ming').hidden = kind !== 'ming';
    el('cf-zhan').hidden = kind !== 'zhan';
    defaultPick();
    renderTools();
  });

  el('cf-tools').addEventListener('click', function (e) {
    var b = e.target.closest('.cf-tool');
    if (!b) return;
    var id = b.getAttribute('data-id');
    picked[id] = !picked[id];
    renderTools();
  });
  el('cf-all').addEventListener('click', function () { defaultPick(); renderTools(); });
  el('cf-none').addEventListener('click', function () { picked = {}; renderTools(); });
  el('cf-now').addEventListener('click', function () { el('cf-dt-zhan').value = SD.nowLocal(); });

  /* ---------- 合参面板 ---------- */
  var lastItems = [];          // 当前合参面板的工具清单（供导出重建 iframe 引用）
  var exportTimer = null;      // 面板尺寸稳定后延迟采集导出文本

  function autoHeight(frame) {
    var doc = null;
    function measure() {
      try {
        doc = frame.contentDocument;
        if (!doc || !doc.body) return;
        var h = Math.max(doc.body.scrollHeight, doc.documentElement.scrollHeight);
        if (h > 0) frame.style.height = (h + 24) + 'px';
      } catch (e) {}
    }
    measure();
    // 排盘结果为异步渲染，监听文档尺寸变化；失败则用短轮询兜底
    try {
      if (window.ResizeObserver && frame.contentDocument) {
        var ro = new ResizeObserver(measure);
        ro.observe(frame.contentDocument.body);
        frame.__ro = ro;
      }
    } catch (e) {}
    var n = 0;
    var timer = setInterval(function () {
      measure();
      if (++n >= 10) clearInterval(timer);
    }, 700);
  }

  /* ---------- 导出 ----------
   * 文本来源：每个 iframe 的 window.SuiteExport.text()（由 suite-bridge.js 注入）。
   * iframe 同源，可直接读取；某页尚未出盘则给「（尚未出盘）」占位。
   * 打印：把各页报告写入一个隐藏的打印容器，配合 @media print 只打印它。
   */
  function collectReports() {
    var frames = document.querySelectorAll('#cr-panels iframe');
    var out = [];
    frames.forEach(function (frame) {
      var name = frame.title || '';
      var body = '';
      try {
        var w = frame.contentWindow;
        if (w && w.SuiteExport && typeof w.SuiteExport.text === 'function') {
          body = String(w.SuiteExport.text() || '');
        }
      } catch (e) {}
      out.push({ name: name, body: body });
    });
    return out;
  }

  function buildReport() {
    var d = SD.load();
    var src = kind === 'ming' ? d.ming : d.zhan;
    var L = [];
    L.push('万界大合体 · 合参报告');
    L.push('生成时间：' + new Date().toLocaleString('zh-CN'));
    L.push(kind === 'ming'
      ? '命主：' + (src.dt || '—') + '　性别：' + (src.gender || '—')
      : '占事：' + (src.question || '（未填）') + '　时间：' + (src.dt || '—'));
    L.push('参与工具：' + lastItems.map(function (i) { return i.short; }).join('、'));
    L.push('');
    var reports = collectReports();
    reports.forEach(function (r, i) {
      L.push('━━━ ' + (i + 1) + '. ' + r.name + ' ━━━');
      L.push(r.body || '（该工具尚未出盘）');
      L.push('');
    });
    L.push('—— 本报告由各工具规则引擎自动汇总，仅供传统文化研究参考。');
    return L.join('\n');
  }

  function flashBtn(btn, text) {
    var old = btn.textContent;
    btn.textContent = text;
    btn.disabled = true;
    setTimeout(function () { btn.textContent = old; btn.disabled = false; }, 1200);
  }

  /* 打印：把当前报告写入打印容器（只取文本，iframe 序列化不可靠） */
  function preparePrint() {
    var holder = document.getElementById('suite-print');
    if (!holder) return false;
    holder.innerHTML = '';
    var h = document.createElement('h1');
    h.textContent = '万界大合体 · 合参报告';
    holder.appendChild(h);
    buildReport().split('\n').forEach(function (line) {
      var p = document.createElement('div');
      if (/^━━━/.test(line)) p.className = 'pt-sec';
      p.textContent = line;
      holder.appendChild(p);
    });
    return true;
  }

  function bindExport() {
    var btnCopy = el('cr-copy');
    if (btnCopy) btnCopy.addEventListener('click', function () {
      var txt = buildReport();
      var done = function (ok) { flashBtn(btnCopy, ok ? '已复制 ✓' : '复制失败'); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(txt).then(function () { done(true); }, function () { done(false); });
      } else {
        try {
          var ta = document.createElement('textarea');
          ta.value = txt; ta.style.cssText = 'position:fixed;left:-9999px;top:0';
          document.body.appendChild(ta); ta.select();
          var ok = document.execCommand('copy'); ta.remove(); done(ok);
        } catch (e) { done(false); }
      }
    });
    var btnTxt = el('cr-dl');
    if (btnTxt) btnTxt.addEventListener('click', function () {
      var blob = new Blob([buildReport()], { type: 'text/plain;charset=utf-8' });
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      var stamp = new Date().toISOString().slice(0, 16).replace(/[T:]/g, '-');
      a.href = url;
      a.download = '合参报告-' + lastItems.map(function (i) { return i.short; }).join('') + '-' + stamp + '.txt';
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
      flashBtn(btnTxt, '已下载 ✓');
    });
    var btnPrint = el('cr-print');
    if (btnPrint) btnPrint.addEventListener('click', function () {
      if (preparePrint()) window.print();
    });
  }

  function renderPanels(items) {
    var box = el('cr-panels');
    box.innerHTML = '';
    lastItems = items;
    items.forEach(function (it) {
      var wrap = document.createElement('div');
      wrap.className = 'cr-panel';
      wrap.innerHTML =
        '<div class="cr-bar"><b>' + esc(it.name) + '</b>' +
        '<span class="cr-url">' + esc(it.url) + '</span>' +
        '<a href="' + esc(it.url) + '" target="_blank" rel="noopener">单独打开 ↗</a>' +
        '<button type="button" class="cr-fold">收起</button></div>';
      var load = document.createElement('div');
      load.className = 'cr-load';
      load.textContent = '正在载入「' + it.short + '」…';
      wrap.appendChild(load);

      var frame = document.createElement('iframe');
      frame.src = it.url;
      frame.title = it.name;
      frame.setAttribute('loading', 'eager');
      frame.addEventListener('load', function () {
        load.hidden = true;                       // 载入完成即撤掉占位
        autoHeight(frame);
      });
      wrap.appendChild(frame);
      wrap.querySelector('.cr-fold').addEventListener('click', function () {
        var hide = frame.style.display !== 'none';
        frame.style.display = hide ? 'none' : '';
        this.textContent = hide ? '展开' : '收起';
      });
      box.appendChild(wrap);
    });
    el('cr-summary').textContent = items.map(function (i) { return i.short; }).join(' · ');
    el('cf-result').hidden = false;
    el('cf-result').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  el('cr-close').addEventListener('click', function () {
    el('cr-panels').innerHTML = '';               // 卸载 iframe，停止其中的渲染与观察
    el('cf-result').hidden = true;
    try { history.replaceState(null, '', '/'); } catch (e) {}
    host.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  /* ---------- 开始推演 ---------- */
  el('cf-go').addEventListener('click', function () {
    var d = readForm();
    var ids = SD.toolsFor(kind).filter(function (t) { return picked[t.id]; })
      .map(function (t) { return t.id; });
    var err = el('cf-error');
    if (!ids.length) { err.textContent = '请至少选择一个工具。'; return; }
    if (!SD.normDt((kind === 'ming' ? d.ming : d.zhan).dt)) {
      err.textContent = kind === 'ming' ? '请填写出生日期时间。' : '请填写占测时间（或点「用现在」）。';
      return;
    }
    err.textContent = '';

    if (ids.length === 1) {                       // 单工具：完整页面
      location.href = SD.buildUrl(ids[0], d, { auto: true });
      return;
    }
    renderPanels(SD.buildMany(ids, d, { auto: true, embed: true }));
    writeShareUrl(ids, d);                        // 多工具结果可收藏、可分享
  });

  /* 把当前合参条件写进地址栏，刷新或分享后能原样恢复 */
  function writeShareUrl(ids, d) {
    try {
      var u = new URL(location.origin + '/');
      var src = kind === 'ming' ? d.ming : d.zhan;
      u.searchParams.set('go', '1');
      u.searchParams.set('kind', kind);
      u.searchParams.set('tools', ids.join(','));
      u.searchParams.set('dt', src.dt);
      if (kind === 'ming') u.searchParams.set('gender', src.gender || '');
      else if (src.question) u.searchParams.set('q', src.question);
      history.replaceState(null, '', u.pathname + u.search);
    } catch (e) {}
  }

  fillForm();
  defaultPick();
  renderTools();
  bindExport();
  restoreFromUrl();

  /* 从合参链接恢复：/?go=1&kind=zhan&tools=meihua,qimen&dt=…&q=… */
  function restoreFromUrl() {
    var q = new URLSearchParams(location.search);
    if (q.get('go') !== '1') return;
    var k = q.get('kind') === 'zhan' ? 'zhan' : 'ming';
    if (k !== kind) {
      var b = host.querySelector('.cast-kind button[data-kind="' + k + '"]');
      if (b) b.click();                            // 复用切换逻辑，保持单一事实来源
    }
    if (q.get('dt')) {
      if (kind === 'ming') el('cf-dt-ming').value = q.get('dt');
      else el('cf-dt-zhan').value = q.get('dt');
    }
    if (kind === 'ming' && q.get('gender')) el('cf-gender').value = q.get('gender');
    if (kind === 'zhan' && q.has('q')) el('cf-question').value = q.get('q');
    var ids = (q.get('tools') || '').split(',').filter(function (id) {
      var t = SD.tool(id);
      return t && t.kind === kind;                 // 丢弃不属于当前数据类型的工具
    });
    if (!ids.length) return;
    picked = {};
    ids.forEach(function (id) { picked[id] = true; });
    renderTools();
    el('cf-go').click();
  }
})();
