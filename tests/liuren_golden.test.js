/* 六壬前端引擎金标自检：从 apps/liuren/index.html 提取引擎与 48 例金标，在 node 中执行 */
const fs = require('fs');
const html = fs.readFileSync('apps/liuren/index.html', 'utf8');
const lines = html.split('\n').map(l => l.replace(/\r/g, ''));

// 按行提取内联 JSON 数据块
const els = {};
for (const ln of lines) {
  const m = ln.match(/^<script id="(lp-gold|lp-terms|lp-ktsrc)" type="application\/json">([\s\S]*)<\/script>$/);
  if (m) els[m[1]] = m[2];
}
if (!els['lp-gold'] || !els['lp-ktsrc']) {
  console.error('数据块提取失败:', Object.keys(els));
  process.exit(2);
}

// 主引擎脚本块：只取引擎本体（LREN/LREX），跳过尾部 DOM 初始化
let start = -1, end = -1;
for (let i = 184; i < lines.length; i++) { if (lines[i].trim() === '<script>') { start = i; break; } }
for (let i = start + 1; i < lines.length; i++) { if (lines[i].trim() === '</script>') { end = i; break; } }
let code = lines.slice(start + 1, end).join('\n');
const cut = code.indexOf('/*LREX-END*/');
if (cut > 0) code = code.slice(0, cut);

const stubEl = () => ({ textContent: '', value: 'auto', addEventListener() {}, style: {},
  classList: { add() {}, remove() {}, toggle() {} }, appendChild() {}, setAttribute() {} });
global.document = {
  getElementById: (id) => els[id] !== undefined ? { textContent: els[id] } : stubEl(),
  addEventListener() {}, createElement: stubEl, body: stubEl(),
  querySelectorAll: () => [], querySelector: stubEl
};
global.window = { addEventListener() {}, document: global.document };
global.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };
global.navigator = {};
global.CustomEvent = function () {};

eval(code + '\n;globalThis.__LREN = LREN;');
const LREN = globalThis.__LREN;
if (!LREN) { console.error('LREN 未定义'); process.exit(2); }

const GOLD = JSON.parse(els['lp-gold']);
let pass = 0; const bad = [];
for (const g of GOLD) {
  const r = LREN.pan(g.day, g.hour, g.jiang, g.dn, {});
  const four = r.lessons.map(L => [L.上, L.下名]);
  const san = r.chuan.map(c => [c.支, c.天将]);
  const kt = r.keti.map(k => k.名);
  const kong = r.xi.kong.slice().sort();
  const e = g.exp;
  // 课体：文献课例(lit=1)只要求金标标签全部命中；随机盘(lit=0)要求集合全等
  const ktOk = g.lit ? e.kt.every(n => kt.includes(n))
                     : JSON.stringify(kt) === JSON.stringify(e.kt);
  const ok = JSON.stringify(four) === JSON.stringify(e.four)
    && JSON.stringify(san) === JSON.stringify(e.san)
    && r.sc.门 === e.men && JSON.stringify(kong) === JSON.stringify(e.kong)
    && ktOk;
  if (ok) pass++; else bad.push(`${g.day}${g.hour}将${g.jiang}: 门${r.sc.门}/${e.men}` + (ktOk ? "" : " 课体"));
}
console.log(`六壬金标自检: ${pass}/${GOLD.length} 过`);
if (bad.length) console.log('未过:', bad.join('；'));
process.exit(bad.length ? 1 : 0);
