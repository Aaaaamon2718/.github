#!/usr/bin/env node
/**
 * 平日限定パフォーマンス分析レポート生成
 * 対象: 指定期間の月〜金（祝日除く）
 * 実行: node scripts/weekday-analysis.js [--from YYYY-MM-DD] [--to YYYY-MM-DD]
 */

const fs = require('fs');
const path = require('path');

const RAW_DIR     = path.join(__dirname, '../data/raw');
const CALENDAR_DIR = path.join(__dirname, '../data/calendar');
const REPORTS_DIR = path.join(__dirname, '../data/reports');

// ── ユーティリティ ────────────────────────────────

function getArgs() {
  const args = process.argv.slice(2);
  const from = args[args.indexOf('--from') + 1] || '2026-04-29';
  const to   = args[args.indexOf('--to')   + 1] || '2026-05-10';
  return { from, to };
}

function dateRange(from, to) {
  const dates = [];
  const cur = new Date(from + 'T12:00:00+09:00');
  const end = new Date(to   + 'T12:00:00+09:00');
  while (cur <= end) {
    dates.push(cur.toISOString().split('T')[0]);
    cur.setDate(cur.getDate() + 1);
  }
  return dates;
}

function isWeekday(dateStr) {
  const d = new Date(dateStr + 'T12:00:00+09:00');
  const dow = d.getDay();
  return dow >= 1 && dow <= 5; // 月〜金
}

function isHoliday(dateStr) {
  const year = dateStr.split('-')[0];
  const p = path.join(CALENDAR_DIR, `${year}.json`);
  if (!fs.existsSync(p)) return false;
  const cal = JSON.parse(fs.readFileSync(p, 'utf-8'));
  const day = cal.days && cal.days[dateStr];
  return day ? !!day.holiday : false;
}

function parseHour(datetimeStr) {
  if (!datetimeStr) return null;
  const m = datetimeStr.match(/(午前|午後)(\d+)時/);
  if (!m) return null;
  let h = parseInt(m[2]);
  if (m[1] === '午後' && h !== 12) h += 12;
  if (m[1] === '午前' && h === 12) h = 0;
  return h;
}

function slot(hour) {
  if (hour === null) return null;
  if (hour >= 6  && hour < 10) return '朝 (6-10時)';
  if (hour >= 10 && hour < 14) return '昼 (10-14時)';
  if (hour >= 14 && hour < 18) return '夕 (14-18時)';
  if (hour >= 18 && hour < 22) return '夜 (18-22時)';
  return '深夜 (22-6時)';
}

const SLOT_ORDER = ['朝 (6-10時)', '昼 (10-14時)', '夕 (14-18時)', '夜 (18-22時)', '深夜 (22-6時)'];

function extractArea(fullAddress) {
  if (!fullAddress) return '不明';
  let addr = fullAddress.replace(/^東京都/, '');
  const wardMatch = addr.match(/^([^\s区]+区)/);
  const ward = wardMatch ? wardMatch[1] : '';
  let area = addr.replace(ward, '').replace(/[０-９0-9一二三四五六七八九十]+丁目.*/, '').replace(/[０-９0-9]+番.*/, '').trim();
  return (area && area.length > 1) ? area : (ward || '不明');
}

function yen(n) { return `¥${Math.round(n).toLocaleString('ja-JP')}`; }
function pct(n, total) { return total > 0 ? (n / total * 100).toFixed(1) + '%' : '—'; }

function stats(arr) {
  if (arr.length === 0) return { n: 0, mean: 0, median: 0, max: 0, min: 0, sum: 0 };
  const sorted = [...arr].sort((a, b) => a - b);
  const sum = arr.reduce((s, x) => s + x, 0);
  const mean = sum / arr.length;
  const mid = Math.floor(sorted.length / 2);
  const median = sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
  return { n: arr.length, mean, median, max: sorted[sorted.length - 1], min: sorted[0], sum };
}

function bar(value, max, width = 20) {
  const filled = max > 0 ? Math.round((value / max) * width) : 0;
  return '█'.repeat(filled) + '░'.repeat(width - filled);
}

// ── データ読み込み & フィルタリング ──────────────────

function loadWeekdayData(from, to) {
  const all = dateRange(from, to);
  const result = [];

  for (const date of all) {
    if (!isWeekday(date)) continue;
    if (isHoliday(date)) { console.log(`  除外（祝日）: ${date}`); continue; }

    const rawPath = path.join(RAW_DIR, `${date}.json`);
    if (!fs.existsSync(rawPath)) { console.log(`  データなし: ${date}`); continue; }

    const raw = JSON.parse(fs.readFileSync(rawPath, 'utf-8'));
    const valid = (raw.deliveries || []).filter(d => !d.error);
    if (valid.length === 0) { console.log(`  0件スキップ: ${date}`); continue; }

    console.log(`  読み込み: ${date} → ${valid.length}件`);

    for (const d of valid) {
      const hour = parseHour(d.datetime);
      result.push({
        date,
        hour,
        slot: slot(hour),
        earnings: d.earnings || 0,
        distance: d.distance || 0,
        durationSec: d.durationSec || 0,
        area: extractArea(d.destAddress),
        storeName: d.storeName || '—',
      });
    }
  }
  return result;
}

// ── 分析関数 ─────────────────────────────────────

function analyzeBySlot(deliveries) {
  const map = {};
  for (const d of deliveries) {
    if (!d.slot) continue;
    if (!map[d.slot]) map[d.slot] = [];
    map[d.slot].push(d.earnings);
  }
  return SLOT_ORDER
    .filter(s => map[s])
    .map(s => ({ slot: s, ...stats(map[s]) }));
}

function analyzeBySlotAndDate(deliveries, dates) {
  const matrix = {};
  for (const s of SLOT_ORDER) matrix[s] = {};
  for (const d of deliveries) {
    if (!d.slot) continue;
    if (!matrix[d.slot][d.date]) matrix[d.slot][d.date] = [];
    matrix[d.slot][d.date].push(d.earnings);
  }
  return matrix;
}

function analyzeByArea(deliveries) {
  const map = {};
  for (const d of deliveries) {
    if (!map[d.area]) map[d.area] = [];
    map[d.area].push(d.earnings);
  }
  return Object.entries(map)
    .map(([area, arr]) => ({ area, ...stats(arr) }))
    .sort((a, b) => b.mean - a.mean);
}

function analyzeAreaBySlot(deliveries) {
  const matrix = {}; // matrix[area][slot] = earnings[]
  for (const d of deliveries) {
    if (!d.slot) continue;
    if (!matrix[d.area]) matrix[d.area] = {};
    if (!matrix[d.area][d.slot]) matrix[d.area][d.slot] = [];
    matrix[d.area][d.slot].push(d.earnings);
  }
  return matrix;
}

// ── Markdown 生成 ──────────────────────────────────

function generateReport(deliveries, dates, from, to) {
  const totalStats  = stats(deliveries.map(d => d.earnings));
  const bySlot      = analyzeBySlot(deliveries);
  const byArea      = analyzeByArea(deliveries);
  const areaBySlot  = analyzeAreaBySlot(deliveries);
  const uniqueAreas = byArea.map(a => a.area);
  const uniqueDates = [...new Set(deliveries.map(d => d.date))].sort();

  const maxSlotMean = Math.max(...bySlot.map(s => s.mean));

  // ── 時間帯別 × 日次マトリクス
  const slotDateMatrix = analyzeBySlotAndDate(deliveries, uniqueDates);

  // ── ベスト/ワースト 時間帯
  const sortedSlots = [...bySlot].sort((a, b) => b.mean - a.mean);
  const bestSlot  = sortedSlots[0];
  const worstSlot = sortedSlots[sortedSlots.length - 1];

  // ── エリア×時間帯 ランキング（n>=2のみ）
  const areaSlotRank = [];
  for (const [area, slotMap] of Object.entries(areaBySlot)) {
    for (const [s, arr] of Object.entries(slotMap)) {
      if (arr.length >= 2) {
        const st = stats(arr);
        areaSlotRank.push({ area, slot: s, ...st });
      }
    }
  }
  areaSlotRank.sort((a, b) => b.mean - a.mean);

  // ── 日次サマリー
  const byDate = {};
  for (const d of deliveries) {
    if (!byDate[d.date]) byDate[d.date] = [];
    byDate[d.date].push(d.earnings);
  }

  const dow = ['日', '月', '火', '水', '木', '金', '土'];

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  let md = `# 平日限定パフォーマンス分析レポート
**分析期間**: ${from} 〜 ${to}（平日 ${uniqueDates.length}日間 / 祝日・土日除外）
**対象日**: ${uniqueDates.map(d => { const day = new Date(d + 'T12:00:00+09:00'); return `${d}（${dow[day.getDay()]}）`; }).join(' / ')}
**生成日時**: ${new Date().toLocaleString('ja-JP')}

---

## エグゼクティブサマリー

| 指標 | 値 |
|---|---|
| 総売上 | **${yen(totalStats.sum)}** |
| 総配達件数 | **${totalStats.n}件** |
| 稼働日数 | ${uniqueDates.length}日 |
| 日平均売上 | ${yen(totalStats.sum / uniqueDates.length)} |
| 平均単価 | ${yen(totalStats.mean)} |
| 中央値単価 | ${yen(totalStats.median)} |
| 最高単価 | ${yen(totalStats.max)} |
| 最低単価 | ${yen(totalStats.min)} |
| 最高効率時間帯 | **${bestSlot.slot}**（平均 ${yen(bestSlot.mean)} / ${bestSlot.n}件）|
| 最低効率時間帯 | ${worstSlot.slot}（平均 ${yen(worstSlot.mean)} / ${worstSlot.n}件）|

`;

  // ── 1. 日次サマリー
  md += `---

## 1. 日次パフォーマンス推移

| 日付 | 曜日 | 件数 | 売上 | 平均単価 | 最高単価 |
|---|---|---|---|---|---|
`;
  for (const date of uniqueDates) {
    const arr = byDate[date];
    const st  = stats(arr);
    const day = new Date(date + 'T12:00:00+09:00');
    md += `| ${date} | ${dow[day.getDay()]} | ${st.n}件 | ${yen(st.sum)} | ${yen(st.mean)} | ${yen(st.max)} |\n`;
  }
  md += '\n';

  // ── 2. 時間帯別単価分析
  md += `---

## 2. 時間帯別単価分析（平日合算）

| 時間帯 | 件数 | 売上合計 | 平均単価 | 中央値 | 最高 | 最低 | 効率バー |
|---|---|---|---|---|---|---|---|
`;
  for (const s of bySlot) {
    md += `| **${s.slot}** | ${s.n}件 | ${yen(s.sum)} | ${yen(s.mean)} | ${yen(s.median)} | ${yen(s.max)} | ${yen(s.min)} | \`${bar(s.mean, maxSlotMean)}\` |\n`;
  }

  // 除外時間帯の注記
  const activeSlotsSet = new Set(bySlot.map(s => s.slot));
  const inactiveSlots = SLOT_ORDER.filter(s => !activeSlotsSet.has(s));
  if (inactiveSlots.length > 0) {
    md += `\n> **除外時間帯**（稼働ゼロのため分析対象外）: ${inactiveSlots.join(' / ')}\n`;
  }
  md += '\n';

  // ── 3. 時間帯別 日次推移マトリクス
  md += `---

## 3. 時間帯別 日次単価推移

`;
  const activeSlotsArr = bySlot.map(s => s.slot);
  let header = '| 時間帯 |';
  let sep    = '|---|';
  for (const d of uniqueDates) {
    const day = new Date(d + 'T12:00:00+09:00');
    header += ` ${d.slice(5)}(${dow[day.getDay()]}) |`;
    sep    += '---|';
  }
  header += ' 平均 |';
  sep    += '---|';
  md += header + '\n' + sep + '\n';

  for (const s of activeSlotsArr) {
    let row = `| **${s}** |`;
    const allForSlot = [];
    for (const d of uniqueDates) {
      const arr = slotDateMatrix[s][d];
      if (arr && arr.length > 0) {
        const m = arr.reduce((a, b) => a + b) / arr.length;
        allForSlot.push(m);
        row += ` ${yen(m)}(${arr.length}件) |`;
      } else {
        row += ' — |';
      }
    }
    const overall = allForSlot.length > 0 ? allForSlot.reduce((a, b) => a + b) / allForSlot.length : 0;
    row += ` **${yen(overall)}** |`;
    md += row + '\n';
  }
  md += '\n';

  // ── 4. エリア別総合ランキング（上位15）
  md += `---

## 4. エリア別総合ランキング（平均単価順・上位15）

| 順位 | エリア | 件数 | 平均単価 | 中央値 | 最高単価 | 売上比率 |
|---|---|---|---|---|---|---|
`;
  for (const [i, a] of byArea.slice(0, 15).entries()) {
    md += `| ${i + 1} | **${a.area}** | ${a.n}件 | ${yen(a.mean)} | ${yen(a.median)} | ${yen(a.max)} | ${pct(a.sum, totalStats.sum)} |\n`;
  }
  md += '\n';

  // ── 5. エリア × 時間帯 ヒートマップ
  const topAreas = byArea.slice(0, 12).map(a => a.area);
  md += `---

## 5. エリア × 時間帯 単価ヒートマップ（上位12エリア）

> 表示: 平均単価（件数）/ データなしは —

`;
  let hHeader = '| エリア |';
  let hSep    = '|---|';
  for (const s of activeSlotsArr) {
    const label = s.replace(/ \(.*?\)/, '');
    hHeader += ` ${label} |`;
    hSep    += '---|';
  }
  hHeader += ' 合計件数 | 総平均 |';
  hSep    += '---|---|';
  md += hHeader + '\n' + hSep + '\n';

  for (const area of topAreas) {
    const slotMap = areaBySlot[area] || {};
    let row = `| **${area}** |`;
    let totalN = 0, totalE = 0;
    for (const s of activeSlotsArr) {
      const arr = slotMap[s];
      if (arr && arr.length > 0) {
        const m = arr.reduce((a, b) => a + b) / arr.length;
        row += ` ${yen(m)}(${arr.length}) |`;
        totalN += arr.length;
        totalE += arr.reduce((a, b) => a + b);
      } else {
        row += ' — |';
      }
    }
    row += ` ${totalN}件 | ${yen(totalE / totalN)} |`;
    md += row + '\n';
  }
  md += '\n';

  // ── 6. エリア × 時間帯 ベスト10（n>=2）
  md += `---

## 6. エリア × 時間帯 高単価ランキング（2件以上）

| 順位 | エリア | 時間帯 | 件数 | 平均単価 | 最高単価 |
|---|---|---|---|---|---|
`;
  for (const [i, r] of areaSlotRank.slice(0, 10).entries()) {
    md += `| ${i + 1} | **${r.area}** | ${r.slot} | ${r.n}件 | ${yen(r.mean)} | ${yen(r.max)} |\n`;
  }
  md += '\n';

  // ── 7. インサイト
  md += `---

## 7. 分析インサイト

### 効率最大化の推奨アクション

`;
  if (bestSlot) {
    md += `1. **${bestSlot.slot}に集中稼働**: 平均単価 ${yen(bestSlot.mean)} は全時間帯最高。同時間帯の${bestSlot.n}件のデータに基づく。\n`;
  }
  if (areaSlotRank.length > 0) {
    const top = areaSlotRank[0];
    md += `2. **${top.slot} × ${top.area}**: 最高効率の組み合わせ。平均 ${yen(top.mean)}（${top.n}件）。\n`;
  }
  if (topAreas.length > 0) {
    md += `3. **高単価エリア集中**: ${byArea.slice(0, 3).map(a => a.area).join('・')} は平均単価上位3エリア。積極的に向かうべきターゲットゾーン。\n`;
  }

  md += `
### 注意点・制約事項

- 本分析は**平日${uniqueDates.length}日間**（n=${totalStats.n}件）のデータに基づく。サンプルサイズが限定的であり、特に件数の少ないエリア×時間帯の組み合わせ（n<3）は統計的信頼性が低い。
- 祝日・土日を除外しているため、曜日効果・GW効果は本レポートでは検出不可。祝日分析は別途実施。
- 単価のみの分析であり、**時間効率**（配達時間・移動距離あたり）は別途距離あたり単価分析が必要。

---
*Goldman Sachs Analytics Style — Uber Eats 平日パフォーマンス分析*
*生成: ${new Date().toLocaleString('ja-JP')}*
`;
  return md;
}

// ── メイン ────────────────────────────────────────

(async () => {
  const { from, to } = getArgs();

  console.log(`=== 平日限定分析レポート ===`);
  console.log(`期間: ${from} 〜 ${to}`);
  console.log('データ読み込み中...');

  const deliveries = loadWeekdayData(from, to);

  if (deliveries.length === 0) {
    console.error('対象データが見つかりません。日付範囲とデータファイルを確認してください。');
    process.exit(1);
  }

  const uniqueDates = [...new Set(deliveries.map(d => d.date))].sort();
  console.log(`\n対象日: ${uniqueDates.join(', ')}`);
  console.log(`総件数: ${deliveries.length}件`);

  if (!fs.existsSync(REPORTS_DIR)) {
    fs.mkdirSync(REPORTS_DIR, { recursive: true });
  }

  const md = generateReport(deliveries, uniqueDates, from, to);
  const outPath = path.join(REPORTS_DIR, `weekday-analysis-${from}-${to}.md`);
  fs.writeFileSync(outPath, md, 'utf-8');

  console.log(`\n✅ 完了: ${outPath}`);
})();
