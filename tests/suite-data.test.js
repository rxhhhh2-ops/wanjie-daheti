/* 共享数据层单元测试：URL 契约与时间换算 */
const fs = require('fs');
const path = require('path');

const store = {};
global.localStorage = {
  getItem: k => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: k => { delete store[k]; }
};
global.window = { addEventListener() {}, dispatchEvent() {} };
global.CustomEvent = function () {};

const file = 'D:/zcodework1/万界大合体/万界大合体第一版/assets/suite-data.js';
eval(fs.readFileSync(file, 'utf8'));
const SD = global.window.SuiteData;

let pass = 0, fail = 0;
function eq(actual, expect, label) {
  const a = String(actual), e = String(expect);
  if (a === e) { pass++; console.log('  ok  ' + label); }
  else { fail++; console.log('  FAIL ' + label + '\n       期望 ' + e + '\n       实际 ' + a); }
}

console.log('[时辰换算]');
eq(SD.hourToShichen(0), 0, '00时 → 早子');
eq(SD.hourToShichen(1), 1, '01时 → 丑');
eq(SD.hourToShichen(2), 1, '02时 → 丑');
eq(SD.hourToShichen(12), 6, '12时 → 午');
eq(SD.hourToShichen(14), 7, '14时 → 未');
eq(SD.hourToShichen(22), 11, '22时 → 亥');
eq(SD.hourToShichen(23), 12, '23时 → 晚子');

console.log('[时间解析]');
eq(SD.normDt('1990-06-15 14:30'), '1990-06-15T14:30', '空格分隔规范化');
eq(SD.normDt('垃圾输入'), '', '非法输入返回空');
eq(SD.dtParts('1990-06-15T14:30').hour, 14, '小时提取');

console.log('[命主 → 工具]');
const data = {
  ming: { name: '', gender: '男', dt: '1990-06-15T14:30', place: '' },
  zhan: { dt: '2026-10-30T15:40', question: '求财' },
  updatedAt: 0
};
const bazi = SD.buildUrl('bazi', data, { auto: true });
eq(bazi, '/bazi/?dt=1990-06-15T14%3A30&gender=%E7%94%B7&auto=1', '四柱 URL');
const ziwei = SD.buildUrl('ziwei', data, { auto: true });
eq(ziwei.indexOf('/ziwei/?dt=1990-06-15T14%3A30'), 0, '紫微 URL 前缀');
eq(SD.toolsFor('ming').map(t => t.id).join(','), 'bazi,ziwei', '命主可用工具');

console.log('[占事 → 工具]');
eq(SD.toolsFor('zhan').map(t => t.id).join(','), 'meihua,qimen,liuren', '占事可用工具');
const mh = SD.buildUrl('meihua', data, { auto: true, embed: true });
eq(mh.indexOf('/meihua/?mode=dt&dt='), 0, '梅花沿用原生 mode=dt 契约');
eq(mh.indexOf('question=%E6%B1%82%E8%B4%A2') > 0, true, '梅花带所问');
eq(mh.indexOf('embed=1') > 0, true, '梅花嵌入标记');
const lr = SD.buildUrl('liuren', data, { auto: true });
eq(lr.indexOf('date=2026-10-30') > 0, true, '六壬日期');
eq(lr.indexOf('time=15%3A40') > 0, true, '六壬时间');
eq(lr.indexOf('birth=1990') > 0, true, '六壬借用命主生年作年命');
eq(lr.indexOf('sex=%E7%94%B7') > 0, true, '六壬借用命主性别');

console.log('[多工具与容错]');
const many = SD.buildMany(['bazi', 'ziwei', 'bazi', 'ghost'], data, { auto: true });
eq(many.length, 2, '去重并忽略未知工具');
eq(many.map(m => m.id).join(','), 'bazi,ziwei', '保持勾选顺序');
const empty = { ming: { dt: '', gender: '男' }, zhan: { dt: '', question: '' } };
eq(SD.buildUrl('bazi', empty, { auto: true }), '/bazi/', '缺数据时不带参数，交还手动填写');

console.log('[时辰逆映射（紫微回流用）]');
eq(SD.shichenToHour(0), 0, '早子 → 00 时');
eq(SD.shichenToHour(1), 1, '丑 → 01 时');
eq(SD.shichenToHour(6), 11, '午 → 11 时');
eq(SD.shichenToHour(12), 23, '晚子 → 23 时');
const ok = [0,1,2,3,4,5,6,7,8,9,10,11,12].every(s => SD.hourToShichen(SD.shichenToHour(s)) === s);
eq(ok, true, 'shichen→hour→shichen 往返一致');

console.log('[回流 mergeFromTool]');
SD.save(data);                                   // 基线：命主 1990-06-15 男，占事 求财
const back1 = SD.mergeFromTool('ming', { dt: '1984-08-13T16:00', gender: '女' });
eq(back1 && back1.ming.dt, '1984-08-13T16:00', '排盘后命主写回');
eq(back1 && back1.ming.gender, '女', '性别写回');
eq(back1 && back1.zhan.question, '求财', '占事不受影响');
const back2 = SD.mergeFromTool('zhan', { dt: '2026-10-30T18:30', question: '事业发展' });
eq(back2 && back2.zhan.dt, '2026-10-30T18:30', '占事写回');
eq(back2 && back2.ming.dt, '1984-08-13T16:00', '命主不受影响');
const back3 = SD.mergeFromTool('ming', { dt: '垃圾', gender: '' });
eq(back3, null, '全空/非法 patch 返回 null 且不写盘');
const back4 = SD.mergeFromTool('ming', { dt: '1990-06-15 14:30' });
eq(back4 && back4.ming.dt, '1990-06-15T14:30', '空格分隔规范化写回');
const back5 = SD.mergeFromTool('ghost', { dt: '1990-06-15T14:30' });
eq(back5, null, '未知数据类型返回 null');

console.log('[存储（首轮）]');
SD.save(data);                                   // 先落盘完整数据，再部分更新
SD.set('ming', { dt: '1984-08-13T16:00', gender: '女' });
const round = SD.load();
eq(round.ming.dt, '1984-08-13T16:00', '写入后可读回');
eq(round.ming.gender, '女', '性别读回');
eq(round.zhan.dt, '2026-10-30T15:40', '另一类数据不受影响');
eq(round.updatedAt > 0, true, '更新时间戳');

console.log('\n结果：' + pass + ' 通过，' + fail + ' 失败');
process.exit(fail ? 1 : 0);
