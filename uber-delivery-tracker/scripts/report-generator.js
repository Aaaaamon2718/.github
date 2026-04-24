#!/usr/bin/env node
/**
 * 週次・月次サマリーレポート生成
 * 実行: node scripts/report-generator.js [--date YYYY-MM-DD|today] [--type daily|weekly|monthly]
 */

const fs = require('fs');
const path = require('path');

const RAW_DIR = path.join(__dirname, '../data/raw');
const REPORTS_DIR = path.join(__dirname, '../data/reports');

function formatDate(d) {
  return d.toISOString().split('T')[0];
}

function formatYen(amount) {
  return `¥${amount.toLocaleString('ja-JP')}`;
}

function getTargetDate(args) {
  const dateArg = args.find(a => a.startsWith('--date'));
  if (!dateArg) return formatDate(new Date());
  const val = dateArg.includes('=') ? dateArg.split('=')[1] : args[args.indexOf(dateArg) + 1];
  return val === 'today' ? formatDate(new Date()) : val;
}

function getReportType(args) {
  const typeArg = args.find(a => a.startsWith('--type'));
  if (!typeArg) return 'daily';
  return typeArg.includes('=') ? typeArg.split('=')[1] : args[args.indexOf(typeArg) + 1];
}

function loadRawData(date) {
  const p = path.join(RAW_DIR, `${date}.json`);
  if (!fs.existsSync(p)) return null;
  return JSON.parse(fs.readFileSync(p, 'utf-8'));
}

function aggregateDays(dates) {
  const result = {
    totalEarnings: 0,
    totalTips: 0,
    totalDistance: 0,
    totalDeliveries: 0,
    byDate: {},
  };

  for (const date of dates) {
    const data = loadRawData(date);
    if (!data) continue;
    const valid = data.deliveries.filter(d => !d.error);
    const earnings = valid.reduce((s, d) => s + (d.earnings || 0), 0);
    const tips = valid.reduce((s, d) => s + (d.tipAmount || 0), 0);
    const dist = valid.reduce((s, d) => s + (d.distance || 0), 0);

    result.totalEarnings += earnings;
    result.totalTips += tips;
    result.totalDistance += dist;
    result.totalDeliveries += valid.length;
    result.byDate[date] = { earnings, tips, distance: dist, count: valid.length };
  }

  return result;
}

function dateRange(start, end) {
  const dates = [];
  const cur = new Date(start);
  const last = new Date(end);
  while (cur <= last) {
    dates.push(formatDate(cur));
    cur.setDate(cur.getDate() + 1);
  }
  return dates;
}

function weekRange(dateStr) {
  const d = new Date(dateStr);
  const day = d.getDay();
  const monday = new Date(d);
  monday.setDate(d.getDate() - ((day + 6) % 7));
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  return { start: formatDate(monday), end: formatDate(sunday) };
}

function monthRange(dateStr) {
  const [y, m] = dateStr.split('-').map(Number);
  const start = `${y}-${String(m).padStart(2, '0')}-01`;
  const last = new Date(y, m, 0).getDate();
  const end = `${y}-${String(m).padStart(2, '0')}-${String(last).padStart(2, '0')}`;
  return { start, end };
}

function weekNumber(dateStr) {
  const d = new Date(dateStr);
  const startOfYear = new Date(d.getFullYear(), 0, 1);
  return Math.ceil(((d - startOfYear) / 86400000 + startOfYear.getDay() + 1) / 7);
}

function generateWeeklyReport(dateStr, agg, range) {
  const avg = agg.totalDeliveries > 0 ? Math.round(agg.totalEarnings / agg.totalDeliveries) : 0;
  const daily = Object.entries(agg.byDate)
    .map(([d, v]) => `| ${d} | ${v.count}件 | ${formatYen(v.earnings)} | ${v.distance.toFixed(1)} km |`)
    .join('\n');

  return `# Uber Eats 週次レポート — ${range.start} 〜 ${range.end}

## サマリー
- 総売上: ${formatYen(agg.totalEarnings)}
- 配達件数: ${agg.totalDeliveries}件
- 総距離: ${agg.totalDistance.toFixed(2)} km
- 平均単価: ${formatYen(avg)}
- 総チップ: ${formatYen(agg.totalTips)}

## 日別内訳
| 日付 | 件数 | 売上 | 距離 |
|---|---|---|---|
${daily || '| （データなし） | — | — | — |'}

---
*生成日時: ${new Date().toLocaleString('ja-JP')}*
`;
}

function generateMonthlyReport(dateStr, agg, range) {
  const avg = agg.totalDeliveries > 0 ? Math.round(agg.totalEarnings / agg.totalDeliveries) : 0;
  const dailyAvgEarnings =
    Object.keys(agg.byDate).length > 0
      ? Math.round(agg.totalEarnings / Object.keys(agg.byDate).length)
      : 0;

  const daily = Object.entries(agg.byDate)
    .map(([d, v]) => `| ${d} | ${v.count}件 | ${formatYen(v.earnings)} | ${v.distance.toFixed(1)} km |`)
    .join('\n');

  const [y, m] = dateStr.split('-');
  return `# Uber Eats 月次レポート — ${y}年${parseInt(m)}月

## サマリー
- 総売上: ${formatYen(agg.totalEarnings)}
- 稼働日数: ${Object.keys(agg.byDate).length}日
- 配達件数: ${agg.totalDeliveries}件
- 総距離: ${agg.totalDistance.toFixed(2)} km
- 平均単価（1配達）: ${formatYen(avg)}
- 1日平均売上: ${formatYen(dailyAvgEarnings)}
- 総チップ: ${formatYen(agg.totalTips)}

## 日別内訳
| 日付 | 件数 | 売上 | 距離 |
|---|---|---|---|
${daily || '| （データなし） | — | — | — |'}

---
*生成日時: ${new Date().toLocaleString('ja-JP')}*
`;
}

function updateReportIndex() {
  const indexPath = path.join(REPORTS_DIR, 'index.json');
  const files = fs.readdirSync(REPORTS_DIR).filter(f => f.endsWith('.md'));
  const index = {
    updatedAt: new Date().toISOString(),
    reports: files.map(f => ({ file: f, name: f.replace('.md', '') })),
  };
  fs.writeFileSync(indexPath, JSON.stringify(index, null, 2), 'utf-8');
}

(async () => {
  const args = process.argv.slice(2);
  const date = getTargetDate(args);
  const type = getReportType(args);

  console.log(`=== レポート生成 (${type}) ===`);
  console.log(`基準日: ${date}`);

  if (!fs.existsSync(REPORTS_DIR)) {
    fs.mkdirSync(REPORTS_DIR, { recursive: true });
  }

  if (type === 'weekly') {
    const range = weekRange(date);
    const dates = dateRange(range.start, range.end);
    const agg = aggregateDays(dates);
    const wn = weekNumber(range.start);
    const year = range.start.split('-')[0];
    const outPath = path.join(REPORTS_DIR, `${year}-W${String(wn).padStart(2, '0')}.md`);
    fs.writeFileSync(outPath, generateWeeklyReport(date, agg, range), 'utf-8');
    console.log(`完了: ${outPath}`);
  } else if (type === 'monthly') {
    const range = monthRange(date);
    const dates = dateRange(range.start, range.end);
    const agg = aggregateDays(dates);
    const [y, m] = date.split('-');
    const outPath = path.join(REPORTS_DIR, `${y}-${m}.md`);
    fs.writeFileSync(outPath, generateMonthlyReport(date, agg, range), 'utf-8');
    console.log(`完了: ${outPath}`);
  } else {
    // daily: index.json だけ更新（Markdownはparser.jsが生成）
    console.log('daily モード: レポートインデックスを更新します');
  }

  updateReportIndex();
  console.log('インデックス更新完了: data/reports/index.json');
})();
