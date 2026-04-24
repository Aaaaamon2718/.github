/**
 * report-generator.js
 * 週次・月次サマリーレポートを生成し、index.json を更新する
 *
 * 使用方法:
 *   node scripts/report-generator.js --date today
 *   node scripts/report-generator.js --weekly
 *   node scripts/report-generator.js --monthly
 */
const fs   = require('fs');
const path = require('path');
const REPORTS_DIR = path.join(__dirname, '../data/reports');
const INDEX_PATH  = path.join(REPORTS_DIR, 'index.json');
if (!fs.existsSync(REPORTS_DIR)) fs.mkdirSync(REPORTS_DIR, { recursive: true });
const yen = (n) => `¥${Number(n).toLocaleString('ja-JP')}`;
const loadAllReports = () => {
  const files = fs.readdirSync(REPORTS_DIR)
    .filter(f => f.match(/^\d{4}-\d{2}-\d{2}\.json$/))
    .sort();
  return files.map(f => {
    try { return JSON.parse(fs.readFileSync(path.join(REPORTS_DIR, f), 'utf-8')); }
    catch { return null; }
  }).filter(Boolean);
};
const updateIndex = () => {
  const all = loadAllReports();
  const index = {
    lastUpdated: new Date().toISOString(),
    totalDays: all.length,
    allDates: all.map(r => r.date),
    recent30: all.slice(-30).map(r => ({
      date: r.date,
      totalEarnings: r.summary.totalEarnings,
      totalCount: r.summary.totalCount,
      totalDistance: r.summary.totalDistance,
    })),
    allTime: {
      totalEarnings: all.reduce((s, r) => s + r.summary.totalEarnings, 0),
      totalCount: all.reduce((s, r) => s + r.summary.totalCount, 0),
      totalDistance: parseFloat(all.reduce((s, r) => s + r.summary.totalDistance, 0).toFixed(2)),
    },
  };
  fs.writeFileSync(INDEX_PATH, JSON.stringify(index, null, 2), 'utf-8');
  console.log(`✅ index.json 更新完了`);
  return index;
};
const generateWeekly = () => {
  const all = loadAllReports();
  const now = new Date();
  const lastMonday = new Date(now);
  lastMonday.setDate(now.getDate() - now.getDay() - 6);
  lastMonday.setHours(0, 0, 0, 0);
  const lastSunday = new Date(lastMonday);
  lastSunday.setDate(lastMonday.getDate() + 6);
  const weekReports = all.filter(r => {
    const d = new Date(r.date);
    return d >= lastMonday && d <= lastSunday;
  });
  if (weekReports.length === 0) { console.log('⚠️  前週のデータがありません'); return; }
  const weekLabel = `${lastMonday.toISOString().slice(0,10)}_${lastSunday.toISOString().slice(0,10)}`;
  const totalEarnings = weekReports.reduce((s, r) => s + r.summary.totalEarnings, 0);
  const totalCount    = weekReports.reduce((s, r) => s + r.summary.totalCount, 0);
  const totalDistance = weekReports.reduce((s, r) => s + r.summary.totalDistance, 0);
  let md = `# Uber Eats 週次レポート\n`;
  md += `対象週: ${lastMonday.toLocaleDateString('ja-JP')} 〜 ${lastSunday.toLocaleDateString('ja-JP')}\n\n`;
  md += `## 週間サマリー\n\n| 項目 | 値 |\n|---|---|\n`;
  md += `| 総売上 | **${yen(totalEarnings)}** |\n`;
  md += `| 稼働日数 | **${weekReports.length}日** |\n`;
  md += `| 総配達件数 | **${totalCount}件** |\n`;
  md += `| 総距離 | **${totalDistance.toFixed(2)} km** |\n`;
  md += `| 日平均売上 | **${yen(Math.round(totalEarnings / weekReports.length))}** |\n\n`;
  md += `## 日別内訳\n\n| 日付 | 件数 | 売上 | 距離 |\n|---|---|---|---|\n`;
  weekReports.forEach(r => {
    md += `| ${r.dateJP} | ${r.summary.totalCount}件 | ${yen(r.summary.totalEarnings)} | ${r.summary.totalDistance} km |\n`;
  });
  const outPath = path.join(REPORTS_DIR, `week_${weekLabel}.md`);
  fs.writeFileSync(outPath, md, 'utf-8');
  console.log(`✅ 週次レポート生成: ${outPath}`);
};
const generateMonthly = () => {
  const all = loadAllReports();
  const now = new Date();
  const lastMonth = now.getMonth() === 0 ? 12 : now.getMonth();
  const lastMonthYear = now.getMonth() === 0 ? now.getFullYear() - 1 : now.getFullYear();
  const monthStr = `${lastMonthYear}-${String(lastMonth).padStart(2, '0')}`;
  const monthReports = all.filter(r => r.date.startsWith(monthStr));
  if (monthReports.length === 0) { console.log(`⚠️  ${monthStr} のデータがありません`); return; }
  const totalEarnings = monthReports.reduce((s, r) => s + r.summary.totalEarnings, 0);
  const totalCount    = monthReports.reduce((s, r) => s + r.summary.totalCount, 0);
  const totalDistance = monthReports.reduce((s, r) => s + r.summary.totalDistance, 0);
  const totalTip      = monthReports.reduce((s, r) => s + (r.summary.totalTip || 0), 0);
  const weekdays = ['日', '月', '火', '水', '木', '金', '土'];
  const wdayStats = {};
  weekdays.forEach(w => { wdayStats[w] = { count: 0, earnings: 0, days: 0 }; });
  monthReports.forEach(r => {
    const d = new Date(r.date);
    const w = weekdays[d.getDay()];
    wdayStats[w].count    += r.summary.totalCount;
    wdayStats[w].earnings += r.summary.totalEarnings;
    wdayStats[w].days++;
  });
  let md = `# Uber Eats 月次レポート\n対象月: ${lastMonthYear}年${lastMonth}月\n\n`;
  md += `## 月間サマリー\n\n| 項目 | 値 |\n|---|---|\n`;
  md += `| 総売上 | **${yen(totalEarnings)}** |\n`;
  md += `| 稼働日数 | **${monthReports.length}日** |\n`;
  md += `| 総配達件数 | **${totalCount}件** |\n`;
  md += `| 総距離 | **${totalDistance.toFixed(2)} km** |\n`;
  md += `| 日平均売上 | **${yen(Math.round(totalEarnings / monthReports.length))}** |\n`;
  md += `| 件平均単価 | **${yen(Math.round(totalEarnings / totalCount))}** |\n`;
  if (totalTip > 0) md += `| 総チップ | **${yen(totalTip)}** |\n`;
  md += `\n## 曜日別分析\n\n| 曜日 | 稼働日数 | 総件数 | 総売上 | 日平均 |\n|---|---|---|---|---|\n`;
  weekdays.forEach(w => {
    const s = wdayStats[w];
    if (s.days === 0) return;
    md += `| ${w}曜日 | ${s.days}日 | ${s.count}件 | ${yen(s.earnings)} | ${yen(Math.round(s.earnings / s.days))} |\n`;
  });
  md += `\n## 日別明細\n\n| 日付 | 件数 | 売上 | 距離 | 平均単価 |\n|---|---|---|---|---|\n`;
  monthReports.forEach(r => {
    md += `| ${r.dateJP} | ${r.summary.totalCount}件 | ${yen(r.summary.totalEarnings)} | ${r.summary.totalDistance} km | ${yen(r.summary.avgEarnings)} |\n`;
  });
  const outPath = path.join(REPORTS_DIR, `${monthStr}.md`);
  fs.writeFileSync(outPath, md, 'utf-8');
  console.log(`✅ 月次レポート生成: ${outPath}`);
};
const args = process.argv.slice(2);
updateIndex();
if (args.includes('--weekly'))  generateWeekly();
if (args.includes('--monthly')) generateMonthly();
console.log('✅ report-generator 完了');
