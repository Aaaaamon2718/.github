#!/usr/bin/env node
/**
 * 生JSONデータをMarkdownレポートに変換するパーサー
 * 実行: node scripts/parser.js [--date YYYY-MM-DD|today]
 */

const fs = require('fs');
const path = require('path');

const RAW_DIR = path.join(__dirname, '../data/raw');
const REPORTS_DIR = path.join(__dirname, '../data/reports');

function getTargetDate(args) {
  const dateArg = args.find(a => a.startsWith('--date'));
  if (!dateArg) return formatDate(new Date());
  const val = dateArg.includes('=') ? dateArg.split('=')[1] : args[args.indexOf(dateArg) + 1];
  if (val === 'today') return formatDate(new Date());
  if (/^\d{4}-\d{2}-\d{2}$/.test(val)) return val;
  throw new Error(`無効な日付形式: ${val}`);
}

function formatDate(d) {
  return d.toISOString().split('T')[0];
}

function formatYen(amount) {
  return `¥${amount.toLocaleString('ja-JP')}`;
}

function formatJapaneseDate(dateStr) {
  const [y, m, d] = dateStr.split('-');
  return `${y}年${parseInt(m)}月${parseInt(d)}日`;
}

function getTimeSlot(timeStr) {
  if (!timeStr) return 'unknown';
  const hourMatch = timeStr.match(/(\d{1,2}):/);
  if (!hourMatch) return 'unknown';
  const hour = parseInt(hourMatch[1]);
  if (hour >= 6 && hour < 10) return '朝（6-10時）';
  if (hour >= 10 && hour < 14) return '昼（10-14時）';
  if (hour >= 14 && hour < 18) return '夕（14-18時）';
  if (hour >= 18 && hour < 22) return '夜（18-22時）';
  return '深夜（22-6時）';
}

function buildTimeSlotTable(deliveries) {
  const slots = {
    '朝（6-10時）': { count: 0, earnings: 0 },
    '昼（10-14時）': { count: 0, earnings: 0 },
    '夕（14-18時）': { count: 0, earnings: 0 },
    '夜（18-22時）': { count: 0, earnings: 0 },
    '深夜（22-6時）': { count: 0, earnings: 0 },
  };

  for (const d of deliveries) {
    if (d.error) continue;
    const slot = getTimeSlot(d.completedAt);
    if (slots[slot]) {
      slots[slot].count++;
      slots[slot].earnings += d.earnings || 0;
    }
  }

  const rows = Object.entries(slots)
    .filter(([, v]) => v.count > 0)
    .map(([slot, v]) => `| ${slot} | ${v.count}件 | ${formatYen(v.earnings)} |`)
    .join('\n');

  if (!rows) return '| （データなし） | — | — |';
  return rows;
}

function buildDetailSection(delivery, index) {
  if (delivery.error) {
    return `### No.${index} — 取得エラー\n- エラー: ${delivery.error}\n`;
  }

  const lines = [`### No.${index} — ${delivery.completedAt || '時刻不明'}完了`];
  if (delivery.storeName) lines.push(`- **店舗**: ${delivery.storeName}`);
  if (delivery.area) lines.push(`- **エリア**: ${delivery.area}`);

  const earningsStr = delivery.tipAmount
    ? `${formatYen(delivery.earnings)}（チップ: ${formatYen(delivery.tipAmount)}含む）`
    : formatYen(delivery.earnings || 0);
  lines.push(`- **売上**: ${earningsStr}`);

  if (delivery.questBonus) lines.push(`- **クエストボーナス**: ${formatYen(delivery.questBonus)}`);
  if (delivery.distance != null) lines.push(`- **距離**: ${delivery.distance.toFixed(2)} km`);
  if (delivery.duration) lines.push(`- **時間**: ${delivery.duration}`);

  return lines.join('\n');
}

function generateMarkdown(data) {
  const valid = data.deliveries.filter(d => !d.error);
  const totalEarnings = valid.reduce((s, d) => s + (d.earnings || 0), 0);
  const totalTips = valid.reduce((s, d) => s + (d.tipAmount || 0), 0);
  const totalDistance = valid.reduce((s, d) => s + (d.distance || 0), 0);
  const avgEarnings = valid.length > 0 ? Math.round(totalEarnings / valid.length) : 0;

  const details = data.deliveries
    .map((d, i) => buildDetailSection(d, i + 1))
    .join('\n\n');

  return `# Uber Eats 配達レポート — ${formatJapaneseDate(data.date)}

## サマリー
- 総売上: ${formatYen(totalEarnings)}
- 配達件数: ${valid.length}件
- 総距離: ${totalDistance.toFixed(2)} km
- 平均単価: ${formatYen(avgEarnings)}
- 総チップ: ${formatYen(totalTips)}

## 配達明細

${details}

## 時間帯分析
| 時間帯 | 件数 | 売上 |
|---|---|---|
${buildTimeSlotTable(data.deliveries)}

---
*生成日時: ${new Date().toLocaleString('ja-JP')}*
*スクレイピング日時: ${data.scrapedAt}*
`;
}

(async () => {
  const args = process.argv.slice(2);
  const date = getTargetDate(args);

  console.log(`=== パーサー ===`);
  console.log(`対象日: ${date}`);

  const rawPath = path.join(RAW_DIR, `${date}.json`);
  if (!fs.existsSync(rawPath)) {
    console.error(`生データが見つかりません: ${rawPath}`);
    console.error('先に node scripts/scraper.js --date を実行してください。');
    process.exit(1);
  }

  const data = JSON.parse(fs.readFileSync(rawPath, 'utf-8'));

  if (!fs.existsSync(REPORTS_DIR)) {
    fs.mkdirSync(REPORTS_DIR, { recursive: true });
  }

  const markdown = generateMarkdown(data);
  const outPath = path.join(REPORTS_DIR, `${date}.md`);
  fs.writeFileSync(outPath, markdown, 'utf-8');

  console.log(`完了: ${outPath} に保存しました`);
})();
