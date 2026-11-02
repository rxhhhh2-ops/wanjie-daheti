/* 万界大合体 · 全局脚本：主题管理 + 导航注入 + 页面错误收集 */
(function () {
  'use strict';

  /* 同步标记嵌入模式：须在首渲染前完成，配合 CSS 让合参 iframe 内不预留导航高度 */
  try {
    if (new URLSearchParams(location.search).get('embed') === '1') {
      document.documentElement.setAttribute('data-embed', '1');
    }
  } catch (e) {}

  /* ---------- 页面级错误收集（便于联调排查，不影响页面功能） ---------- */
  window.__suiteErrors = window.__suiteErrors || [];
  window.addEventListener('error', function (e) {
    try {
      window.__suiteErrors.push({
        type: 'error',
        message: String(e.message || e.error || ''),
        source: String(e.filename || ''),
        line: e.lineno || 0
      });
    } catch (err) {}
  });
  window.addEventListener('unhandledrejection', function (e) {
    try {
      var r = e.reason;
      window.__suiteErrors.push({
        type: 'unhandledrejection',
        message: String((r && (r.stack || r.message)) || r || '')
      });
    } catch (err) {}
  });

  /* ---------- 主题管理 ---------- */
  var THEME_KEY = 'suite-theme';
  var THEMES = [
    { id: 'swiss',      name: '瑞士简约', en: 'Swiss',         dots: ['#fafaf8', '#002FA7', '#0a0a0a'] },
    { id: 'bauhaus',    name: '包豪斯',   en: 'Bauhaus',       dots: ['#f2efe6', '#2456a4', '#d3402c'] },
    { id: 'construct',  name: '构成主义', en: 'Constructivism',dots: ['#ece7da', '#c8321e', '#15120e'] },
    { id: 'minimal',    name: '极简主义', en: 'Minimal',       dots: ['#fbfbfa', '#234a6b', '#1f2023'] },
    { id: 'newwave',    name: '新浪潮',   en: 'New Wave',      dots: ['#fdfcf7', '#ff3eb5', '#101014'] },
    { id: 'ink',        name: '留白水墨', en: 'Ink',           dots: ['#f5f4ed', '#a03a2a', '#141413'] }
  ];
  var VALID = {};
  THEMES.forEach(function (t) { VALID[t.id] = true; });

  function getTheme() {
    try {
      var v = localStorage.getItem(THEME_KEY);
      return (v && VALID[v]) ? v : 'swiss';
    } catch (e) { return 'swiss'; }
  }
  function applyTheme(id, save) {
    if (!VALID[id]) id = 'swiss';
    document.documentElement.setAttribute('data-theme', id);
    if (save !== false) {
      try { localStorage.setItem(THEME_KEY, id); } catch (e) {}
    }
    refreshThemeUI(id);
    try { window.dispatchEvent(new CustomEvent('suite-themechange', { detail: { id: id } })); } catch (e) {}
  }
  function setTheme(id) { applyTheme(id, true); }
  window.__suiteSetTheme = setTheme;
  window.__suiteThemes = THEMES;
  window.__suiteGetTheme = getTheme;

  // 尽早应用，避免闪烁（本脚本在 <head> 中同步执行）
  applyTheme(getTheme(), false);
  try {
    window.addEventListener('storage', function (e) {
      if (e.key === THEME_KEY && e.newValue && VALID[e.newValue]) applyTheme(e.newValue, false);
    });
  } catch (e) {}

  function dotsHtml(t) {
    return '<span class="dots">' + t.dots.map(function (c) {
      return '<i style="background:' + c + '"></i>';
    }).join('') + '</span>';
  }
  function themeById(id) {
    return THEMES.filter(function (x) { return x.id === id; })[0] || THEMES[0];
  }
  function refreshThemeUI(id) {
    var t = themeById(id);
    var btn = document.querySelector('#suite-nav .sn-theme-btn');
    if (btn) {
      btn.querySelector('.sw').style.setProperty('--sw-a', t.dots[0]);
      btn.querySelector('.sw').style.setProperty('--sw-b', t.dots[1]);
      var txt = btn.querySelector('.txt');
      if (txt) txt.textContent = t.name;
    }
    document.querySelectorAll('.sn-theme-item').forEach(function (n) {
      n.classList.toggle('on', n.getAttribute('data-theme-id') === id);
    });
    document.querySelectorAll('#suite-themes .st-chip').forEach(function (n) {
      n.classList.toggle('on', n.getAttribute('data-theme-id') === id);
    });
    // 首页可收纳陈列架的折叠按钮同步当前主题
    var tg = document.querySelector('#suite-themes .st-toggle');
    if (tg) {
      tg.querySelector('.sw').style.setProperty('--sw-a', t.dots[0]);
      tg.querySelector('.sw').style.setProperty('--sw-b', t.dots[1]);
      var cur = tg.querySelector('.st-cur');
      if (cur) cur.textContent = '主题 · ' + t.name;
    }
  }

  /* ---------- 首页主题陈列架（可收纳，portal 注入） ---------- */
  function mountThemeStrip() {
    var host = document.getElementById('suite-themes');
    if (!host || host.childNodes.length) return;
    var cur = getTheme();
    host.innerHTML =
      '<button type="button" class="st-toggle" aria-expanded="false" title="展开 / 收起主题">' +
        '<span class="sw"></span><span class="st-cur"></span><span class="car">▸</span>' +
      '</button>' +
      '<div class="st-body">' + THEMES.map(function (t) {
        return '<button type="button" class="st-chip' + (t.id === cur ? ' on' : '') +
          '" data-theme-id="' + t.id + '">' + dotsHtml(t) +
          '<span class="st-name">' + t.name + '</span>' +
          '<span class="st-en">' + t.en + '</span></button>';
      }).join('') + '</div>';

    function collapse() {
      host.classList.remove('open');
      host.querySelector('.st-toggle').setAttribute('aria-expanded', 'false');
    }
    function expand() {
      host.classList.add('open');
      host.querySelector('.st-toggle').setAttribute('aria-expanded', 'true');
    }
    host.querySelector('.st-toggle').addEventListener('click', function (e) {
      e.stopPropagation();
      host.classList.contains('open') ? collapse() : expand();
    });
    host.querySelector('.st-body').addEventListener('click', function (e) {
      var b = e.target.closest('.st-chip');
      if (!b) return;
      setTheme(b.getAttribute('data-theme-id'));
      // 选完自动收纳，让页面保持干净
      setTimeout(collapse, 450);
    });
    document.addEventListener('click', function (e) {
      if (host.classList.contains('open') && !host.contains(e.target)) collapse();
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') collapse();
    });
    // 默认收纳
    collapse();
    refreshThemeUI(getTheme());
  }

  /* ---------- 统一 AI 配置中心（五术共用端点 / Key / 模型） ---------- */
  var AI_SHARED_KEY = 'suite-ai-cfg';
  var AI_SYNC_PREFIX = 'suite-ai-sync:';
  var AI_PAGES = ['bazi', 'meihua', 'qimen', 'liuren', 'ziwei'];
  var AI_PAGE_LABEL = { bazi: '四柱', meihua: '梅花', qimen: '奇门', liuren: '六壬', ziwei: '紫微' };

  function readJson(k) { try { return JSON.parse(localStorage.getItem(k) || '{}') || {}; } catch (e) { return {}; } }
  function writeJson(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } }
  function loadSharedAi() {
    var c = readJson(AI_SHARED_KEY);
    return { base_url: c.base_url || '', api_key: c.api_key || '', model: c.model || '', updatedAt: c.updatedAt || 0 };
  }
  function mergePageCfg(page, c) {
    if (!c || !c.base_url) return;
    if (page === 'bazi') {
      var b = readJson('wanwu.ai.cfg.v1');
      b.base_url = c.base_url; b.api_key = c.api_key || ''; if (c.model) b.model = c.model;
      if (b.temperature == null) b.temperature = 0.6;
      if (b.max_tokens == null) b.max_tokens = 1600;
      writeJson('wanwu.ai.cfg.v1', b);
    } else if (page === 'meihua') {
      var m = readJson('meihua_ai_cfg');
      m.endpoint = c.base_url; m.key = c.api_key || ''; if (c.model) m.model = c.model;
      if (m.enabled == null) m.enabled = true;
      writeJson('meihua_ai_cfg', m);
    } else if (page === 'qimen') {
      var q = readJson('qm-ai-cfg');
      q.base_url = c.base_url; q.api_key = c.api_key || ''; if (c.model) q.model = c.model;
      if (q.temperature == null) q.temperature = 0.6;
      writeJson('qm-ai-cfg', q);
    } else if (page === 'liuren') {
      var l = readJson('lp-ai-config');
      l.url = c.base_url; l.key = c.api_key || ''; if (c.model) l.model = c.model;
      writeJson('lp-ai-config', l);
    } else if (page === 'ziwei') {
      try {
        localStorage.setItem('zwds_api_base', c.base_url);
        localStorage.setItem('zwds_api_key', c.api_key || '');
        if (c.model) localStorage.setItem('zwds_api_model', c.model);
      } catch (e) {}
    }
  }
  function markPage(page, ts) { try { localStorage.setItem(AI_SYNC_PREFIX + page, String(ts || 0)); } catch (e) {} }
  function saveSharedAi(c) {
    c.updatedAt = Date.now();
    writeJson(AI_SHARED_KEY, c);
    AI_PAGES.forEach(function (p) { mergePageCfg(p, c); markPage(p, c.updatedAt); });
    return c;
  }
  // 页面加载时：共享配置有新版本才覆盖本页（保留各页自己的单独修改）
  function syncSharedAiToPage() {
    var c = loadSharedAi();
    if (!c.base_url) return;
    var page = document.documentElement.getAttribute('data-page') || '';
    if (AI_PAGES.indexOf(page) < 0) return;
    var marker = 0;
    try { marker = Number(localStorage.getItem(AI_SYNC_PREFIX + page) || 0); } catch (e) {}
    if (c.updatedAt && marker === c.updatedAt) return;
    mergePageCfg(page, c);
    markPage(page, c.updatedAt);
  }
  syncSharedAiToPage();

  function pageAiCfg(page) {
    if (page === 'bazi') { var b = readJson('wanwu.ai.cfg.v1'); return { base_url: b.base_url || '', api_key: b.api_key || '', model: b.model || '' }; }
    if (page === 'meihua') { var m = readJson('meihua_ai_cfg'); return { base_url: m.endpoint || '', api_key: m.key || '', model: m.model || '' }; }
    if (page === 'qimen') { var q = readJson('qm-ai-cfg'); return { base_url: q.base_url || '', api_key: q.api_key || '', model: q.model || '' }; }
    if (page === 'liuren') { var l = readJson('lp-ai-config'); return { base_url: l.url || '', api_key: l.key || '', model: l.model || '' }; }
    if (page === 'ziwei') {
      return {
        base_url: localStorage.getItem('zwds_api_base') || '',
        api_key: localStorage.getItem('zwds_api_key') || '',
        model: localStorage.getItem('zwds_api_model') || ''
      };
    }
    return { base_url: '', api_key: '', model: '' };
  }

  // 保存后把当前页面自己的设置面板同步刷新
  function fillPageInputs(c) {
    var page = document.documentElement.getAttribute('data-page') || '';
    function set(id, val) { var n = document.getElementById(id); if (n) n.value = val == null ? '' : val; }
    function text(id, val) { var n = document.getElementById(id); if (n) n.textContent = val; }
    if (page === 'bazi') {
      set('cfgBase', c.base_url); set('cfgKey', c.api_key); set('cfgModel', c.model);
      text('aiCfgLine', c.model ? ('模型 ' + c.model + ' · ' + c.base_url) : '未配置 API');
    } else if (page === 'meihua') {
      set('aiEndpoint', c.base_url); set('aiKey', c.api_key); set('aiModel', c.model);
    } else if (page === 'qimen') {
      set('ai-base', c.base_url); set('ai-key', c.api_key); set('ai-model', c.model);
      text('ai-state', c.base_url ? '已保存配置（本机浏览器）' : '未配置；可填任意 OpenAI 兼容接口');
    } else if (page === 'liuren') {
      set('lp-ai-url', c.base_url); set('lp-ai-key', c.api_key); set('lp-ai-model', c.model);
      text('lp-ai-status', c.base_url ? ('已配置：' + (c.model || '') + '（' + c.base_url.replace(/^https?:\/\//, '').split('/')[0] + '）') : '未配置（不影响排盘与规则解盘）');
    } else if (page === 'ziwei') {
      set('apiBase', c.base_url); set('apiKey', c.api_key); set('apiModel', c.model);
    }
  }

  function buildAiDialog() {
    if (document.getElementById('suite-ai-modal')) return;
    var m = el('div', 'sai-modal');
    m.id = 'suite-ai-modal';
    m.hidden = true;
    m.innerHTML =
      '<div class="sai-box" role="dialog" aria-modal="true" aria-label="统一 AI 配置">' +
        '<div class="sai-head"><b>统一 AI 配置</b><button type="button" class="sai-x" aria-label="关闭">✕</button></div>' +
        '<p class="sai-note">一处设置，五术共用（四柱 / 梅花 / 奇门 / 六壬 / 紫微）。Key 只保存在本机浏览器；测试与转发经本机服务，不写日志。</p>' +
        '<label>API 端点（OpenAI 兼容）<input id="sai-base" placeholder="https://api.openai.com/v1" autocomplete="off"></label>' +
        '<label>API Key <input id="sai-key" type="password" placeholder="sk-…（仅存本机）" autocomplete="off"></label>' +
        '<label>模型 <input id="sai-model" placeholder="gpt-4o-mini" autocomplete="off"></label>' +
        '<div class="sai-status" id="sai-status"></div>' +
        '<div class="sai-actions">' +
          '<button type="button" id="sai-test" class="ghost">测试连接</button>' +
          '<button type="button" id="sai-save" class="primary">保存并同步</button>' +
          '<button type="button" id="sai-clear" class="ghost">清除</button>' +
        '</div>' +
        '<p class="sai-foot">人设 / 语气仍在各工具页内单独设置</p>' +
      '</div>';
    document.body.appendChild(m);

    var status = m.querySelector('#sai-status');
    function setStatus(txt, cls) {
      status.textContent = txt || '';
      status.className = 'sai-status' + (cls ? ' ' + cls : '');
    }
    function close() { m.hidden = true; }
    m.querySelector('.sai-x').addEventListener('click', close);
    m.addEventListener('click', function (e) { if (e.target === m) close(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !m.hidden) close(); });

    m.querySelector('#sai-test').addEventListener('click', function () {
      var base = m.querySelector('#sai-base').value.trim();
      var key = m.querySelector('#sai-key').value.trim();
      var model = m.querySelector('#sai-model').value.trim() || 'gpt-4o-mini';
      if (!base) { setStatus('请填写 API 端点', 'err'); return; }
      setStatus('测试中…');
      fetch('/api/ai-test', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ base_url: base, api_key: key, model: model })
      }).then(function (r) { return r.json(); }).then(function (j) {
        if (j.ok) setStatus('连接成功 · ' + (j.model || model) + ' · 返回 ' + (j.content || '').slice(0, 20), 'ok');
        else setStatus('失败：' + (j.error || '未知错误'), 'err');
      }).catch(function (e) { setStatus('失败：' + e.message, 'err'); });
    });

    m.querySelector('#sai-save').addEventListener('click', function () {
      var base = m.querySelector('#sai-base').value.trim().replace(/\/+$/, '');
      var key = m.querySelector('#sai-key').value.trim();
      var model = m.querySelector('#sai-model').value.trim();
      if (!base || !/^https?:\/\//.test(base)) { setStatus('API 端点需以 http:// 或 https:// 开头', 'err'); return; }
      if (!model) { setStatus('请填写模型名', 'err'); return; }
      var c = saveSharedAi({ base_url: base, api_key: key, model: model });
      fillPageInputs(c);
      setStatus('已保存并同步到五术 · ' + model, 'ok');
    });

    m.querySelector('#sai-clear').addEventListener('click', function () {
      try {
        localStorage.removeItem(AI_SHARED_KEY);
        AI_PAGES.forEach(function (p) { localStorage.removeItem(AI_SYNC_PREFIX + p); });
        localStorage.removeItem('wanwu.ai.cfg.v1');
        localStorage.removeItem('meihua_ai_cfg');
        localStorage.removeItem('qm-ai-cfg');
        localStorage.removeItem('lp-ai-config');
        localStorage.removeItem('zwds_api_base');
        localStorage.removeItem('zwds_api_key');
        localStorage.removeItem('zwds_api_model');
      } catch (e) {}
      fillPageInputs({ base_url: '', api_key: '', model: '' });
      m.querySelector('#sai-base').value = '';
      m.querySelector('#sai-key').value = '';
      m.querySelector('#sai-model').value = '';
      setStatus('已清除本机 AI 配置', 'ok');
    });
  }

  function openAiDialog() {
    buildAiDialog();
    var m = document.getElementById('suite-ai-modal');
    var c = loadSharedAi();
    var page = document.documentElement.getAttribute('data-page') || '';
    if (!c.base_url) c = pageAiCfg(page);
    m.querySelector('#sai-base').value = c.base_url || '';
    m.querySelector('#sai-key').value = c.api_key || '';
    m.querySelector('#sai-model').value = c.model || '';
    var st = m.querySelector('#sai-status');
    st.className = 'sai-status';
    st.textContent = page && AI_PAGE_LABEL[page]
      ? ('当前页面：' + AI_PAGE_LABEL[page] + (c.base_url ? ' · 已配置' : ' · 尚未配置'))
      : '设置后自动同步到五个工具';
    m.hidden = false;
    setTimeout(function () { m.querySelector('#sai-base').focus(); }, 50);
  }
  window.__suiteOpenAI = openAiDialog;

  /* ---------- 工具页导航 ---------- */
  var NAV_ITEMS = [
    { href: '/', key: 'home', label: '首页' },
    { href: '/bazi/', key: 'bazi', label: '四柱' },
    { href: '/meihua/', key: 'meihua', label: '梅花' },
    { href: '/qimen/', key: 'qimen', label: '奇门' },
    { href: '/liuren/', key: 'liuren', label: '六壬' },
    { href: '/ziwei/', key: 'ziwei', label: '紫微' }
  ];

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text) n.textContent = text;
    return n;
  }

  function buildNav() {
    var path = location.pathname || '/';
    var active = 'home';
    if (/^\/bazi(\/|$)/.test(path)) active = 'bazi';
    else if (/^\/meihua(\/|$)/.test(path)) active = 'meihua';
    else if (/^\/qimen(\/|$)/.test(path)) active = 'qimen';
    else if (/^\/liuren(\/|$)/.test(path)) active = 'liuren';
    else if (/^\/ziwei(\/|$)/.test(path)) active = 'ziwei';

    var nav = document.createElement('nav');
    nav.id = 'suite-nav';
    nav.setAttribute('aria-label', '万界大合体导航');

    var brand = el('a', 'sn-brand');
    brand.href = '/';
    brand.appendChild(el('span', 'sn-seal', '合'));
    brand.appendChild(el('span', 'sn-name', '万界大合体'));
    brand.appendChild(el('span', 'sn-sub', '五术合一'));
    nav.appendChild(brand);

    var links = el('div', 'sn-links');
    NAV_ITEMS.forEach(function (it) {
      var a = el('a', it.key === active ? 'on' : '', it.label);
      a.href = it.href;
      if (it.key === active) a.setAttribute('aria-current', 'page');
      links.appendChild(a);
    });
    nav.appendChild(links);

    var status = el('div', 'sn-status');
    status.appendChild(el('i'));
    status.appendChild(document.createTextNode('本地运行'));
    nav.appendChild(status);

    // 统一 AI 配置入口
    var aiBtn = el('button', 'sn-ai-btn', 'AI');
    aiBtn.type = 'button';
    aiBtn.title = '统一 AI 配置（五术共用）';
    aiBtn.addEventListener('click', function (e) { e.stopPropagation(); openAiDialog(); });
    nav.appendChild(aiBtn);

    // 主题切换器
    var wrap = el('div', 'sn-theme');
    var btn = el('button', 'sn-theme-btn');
    btn.type = 'button';
    btn.setAttribute('aria-haspopup', 'true');
    btn.innerHTML = '<span class="sw"></span><span class="txt"></span><span class="car">▾</span>';
    var pop = el('div', 'sn-theme-pop');
    pop.hidden = true;
    pop.setAttribute('role', 'menu');
    pop.innerHTML = '<div class="pop-title">主题 · THEME</div>' + THEMES.map(function (t) {
      return '<button type="button" class="sn-theme-item" data-theme-id="' + t.id + '" role="menuitem">' +
        dotsHtml(t) + '<span>' + t.name + '</span><span class="en">' + t.en + '</span></button>';
    }).join('');
    wrap.appendChild(btn);
    wrap.appendChild(pop);
    nav.appendChild(wrap);

    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      pop.hidden = !pop.hidden;
    });
    pop.addEventListener('click', function (e) {
      var b = e.target.closest('.sn-theme-item');
      if (!b) return;
      setTheme(b.getAttribute('data-theme-id'));
      pop.hidden = true;
    });
    document.addEventListener('click', function (e) {
      if (!pop.hidden && !wrap.contains(e.target)) pop.hidden = true;
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') pop.hidden = true;
    });

    return nav;
  }

  function mount() {
    buildAiDialog();
    if (document.querySelector('.topbar') && !document.getElementById('sai-entry')) {
      var entry = document.createElement('button');
      entry.type = 'button'; entry.id = 'sai-entry'; entry.className = 'sai-entry';
      entry.textContent = 'AI 设置';
      entry.title = '统一 AI 配置（五术共用）';
      entry.addEventListener('click', openAiDialog);
      var meta = document.querySelector('.topbar .meta');
      if (meta) meta.parentNode.insertBefore(entry, meta);
      else document.querySelector('.topbar').appendChild(entry);
    }
    if (!document.querySelector('link[rel="icon"]')) {
      var icon = document.createElement('link');
      icon.rel = 'icon'; icon.type = 'image/svg+xml'; icon.href = '/assets/favicon.svg';
      document.head.appendChild(icon);
    }
    mountThemeStrip();
    // 首页不注入导航（首页有自己的顶栏与主题陈列架）
    if (document.getElementById('suite-nav')) return;
    if (location.pathname === '/' || location.pathname === '/index.html') return;
    // 合参嵌入模式：面板已有标题与「单独打开」入口，不再注入全局导航
    try {
      if (new URLSearchParams(location.search).get('embed') === '1') return;
    } catch (e) {}
    document.body.insertBefore(buildNav(), document.body.firstChild);
    refreshThemeUI(getTheme());
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
