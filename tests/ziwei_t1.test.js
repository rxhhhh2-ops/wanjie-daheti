/* 紫微 T1 金标用例验证：阳男 公历1984-8-13 申时(时辰序号8)
   预期（资料集《排盘基准与流派差异》T1）：阳男·顺行·水二局·命宫子 */
global.self = global;
const iztro = require('../apps/ziwei/iztro.min.js');

iztro.astro.config({ dayDivide: 'forward', yearDivide: 'exact' });
const a = iztro.astro.bySolar('1984-8-13', 8, '男', true, 'zh-CN');
const ming = a.palaces.find(p => p.name === '命宫');
const shen = a.palaces.find(p => p.isBodyPalace);

let pass = 0, fail = 0;
function eq(label, got, want) {
  if (String(got) === String(want)) { pass++; console.log(`  ok  ${label} = ${got}`); }
  else { fail++; console.log(`  FAIL ${label}: 期望 ${want}, 实际 ${got}`); }
}
eq('农历', a.lunarDate, '一九八四年七月十七');
eq('时辰', a.time, '申时');
eq('干支', a.chineseDate, '甲子 壬申 己卯 壬申');
eq('五行局', a.fiveElementsClass, '水二局');
eq('命宫地支', ming && ming.earthlyBranch, '子');
eq('性别', a.gender, '男');
console.log(`\nT1 结果: ${pass} 通过, ${fail} 失败`);
process.exit(fail ? 1 : 0);
