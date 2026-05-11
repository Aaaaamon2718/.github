#!/usr/bin/env node
/**
 * 稼働最適化戦略レポート — Goldman Sachs Edition
 * 9〜23時の時間別エリア戦略・遷移推奨・オファー受諾基準を出力
 * 実行: node scripts/route-strategy.js --mode weekday|weekend [--from YYYY-MM-DD] [--to YYYY-MM-DD]
 */

const fs   = require('fs');
const path = require('path');

const RAW_DIR      = path.join(__dirname, '../data/raw');
const CALENDAR_DIR = path.join(__dirname, '../data/calendar');
const WEATHER_DIR  = path.join(__dirname, '../data/weather');
const REPORTS_DIR  = path.join(__dirname, '../data/reports');

const DOW = ['日', '月', '火', '水', '木', '金', '土'];

// 分析対象時間帯
const TARGET_HOURS = Array.from({ length: 15 }, (_, i) => i + 9); // 9〜23

// 時間ブロック定義
const BLOCKS = [
  { label: 'モーニング',   hours: [9, 10],          emoji: '🌅' },
  { label: 'ランチ前',     hours: [10, 11],          emoji: '⏳' },
  { label: 'ランチラッシュ', hours: [11, 12, 13],    emoji: '🔥' },
  { label: 'ランチ後',     hours: [13, 14],           emoji: '📉' },
  { label: 'アフタヌーン', hours: [14, 15, 16],      emoji: '☁️' },
  { label: 'ディナー前',   hours: [17],               emoji: '⏫' },
  { label: 'ディナーラッシュ', hours: [18, 19, 20],  emoji: '🔥' },
  { label: 'レイトナイト', hours: [21, 22, 23],      emoji: '🌙' },
];

// ── t分布 95%CI ────────────────────────────────────
const T_CRITICAL = { 1: 12.71, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
  6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
  15: 2.131, 20: 2.086, 30: 2.042, 60: 2.000 };
function tCritical(n) {
  if (n <= 1) return 12.71;
  const keys = Object.keys(T_CRITICAL).map(Number).sort((a, b) => a - b);
  for (const k of keys) if (n - 1 <= k) return T_CRITICAL[k];
  return 1.96;
}

// ── ユーティリティ ────────────────────────────────

function getArgs() {
  const args = process.argv.slice(2);
  const get  = key => { const i = args.indexOf(key); return i !== -1 ? args[i + 1] : null; };
  const mode = get('--mode') || 'weekday';
  if (!['weekday', 'weekend'].includes(mode)) {
    console.error('--mode は weekday または weekend を指定してください'); process.exit(1);
  }
  return { mode, from: get('--from') || '2026-04-21', to: get('--to') || '2026-05-10' };
}

function dateRange(from, to) {
  const dates = [], cur = new Date(from + 'T12:00:00+09:00'), end = new Date(to + 'T12:00:00+09:00');
  while (cur <= end) { dates.push(cur.toISOString().split('T')[0]); cur.setDate(cur.getDate() + 1); }
  return dates;
}

function getCalendarDay(dateStr) {
  const p = path.join(CALENDAR_DIR, `${dateStr.split('-')[0]}.json`);
  if (!fs.existsSync(p)) return null;
  const cal = JSON.parse(fs.readFileSync(p, 'utf-8'));
  return (cal.days && cal.days[dateStr]) || null;
}

function isHoliday(dateStr) {
  const cal = getCalendarDay(dateStr);
  return !!(cal && cal.holiday);
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

function extractArea(addr) {
  if (!addr) return '不明';
  const a = addr.replace(/^東京都/, '');
  const m = a.match(/^([^\s区]+区)/);
  return m ? m[1] : '不明';
}

function yen(n)  { return `¥${Math.round(n).toLocaleString('ja-JP')}`; }
function pct(a, b) { return b > 0 ? (a / b * 100).toFixed(1) + '%' : '—'; }
function fmt1(n) { return isFinite(n) ? n.toFixed(1) : '—'; }

function stats(arr) {
  if (!arr || arr.length === 0) return { n: 0, mean: 0, median: 0, max: 0, min: 0, sum: 0, std: 0, ci95: 0 };
  const sorted = [...arr].sort((a, b) => a - b), n = arr.length;
  const mean = arr.reduce((s, x) => s + x, 0) / n;
  const mid  = Math.floor(n / 2);
  const median = n % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
  const std  = Math.sqrt(n > 1 ? arr.reduce((s, x) => s + (x - mean) ** 2, 0) / (n - 1) : 0);
  return { n, mean, median, max: sorted[n - 1], min: sorted[0], sum: arr.reduce((s, x) => s + x, 0), std,
    ci95: n > 1 ? tCritical(n) * std / Math.sqrt(n) : 0 };
}

// ── データ読み込み ────────────────────────────────

function loadData(mode, from, to) {
  const result = [], dates = [];
  for (const date of dateRange(from, to)) {
    const day = new Date(date + 'T12:00:00+09:00');
    const dow = day.getDay();
    const isWeekend = dow === 0 || dow === 6;
    const holiday   = isHoliday(date);

    if (mode === 'weekday' && (isWeekend || holiday)) continue;
    if (mode === 'weekend' && !isWeekend && !holiday) continue;

    const rawPath = path.join(RAW_DIR, `${date}.json`);
    if (!fs.existsSync(rawPath)) continue;

    const raw   = JSON.parse(fs.readFileSync(rawPath, 'utf-8'));
    const valid = (raw.deliveries || []).filter(d => !d.error);
    if (valid.length === 0) continue;

    dates.push(date);
    const calDay = getCalendarDay(date);

    for (const d of valid) {
      const hour = parseHour(d.datetime);
      if (hour === null) continue;
      result.push({
        date, dow: DOW[dow],
        dayType: mode === 'weekend' ? getDayType(dow, calDay) : DOW[dow] + '曜',
        hour, area: extractArea(d.destAddress),
        earnings: d.earnings || 0,
        distance: d.distance || 0,
        durationSec: d.durationSec || 0,
        storeName: d.storeName || '—',
        yenPerKm:  (d.distance > 0) ? (d.earnings || 0) / d.distance : null,
        yenPerMin: (d.durationSec > 0) ? (d.earnings || 0) / (d.durationSec / 60) : null,
      });
    }
  }
  return { deliveries: result, days: [...new Set(dates)].sort() };
}

function getDayType(dow, calDay) {
  const isHol = !!(calDay && calDay.holiday);
  if (dow === 6) return isHol ? '土祝' : '土';
  if (dow === 0) return isHol ? '日祝' : '日';
  return '祝（平日）';
}

// ── 分析コア ─────────────────────────────────────

// 時間×エリア マトリクス構築（単価・所要時間を両方収集）
function buildHourAreaMatrix(deliveries) {
  const matrix = {}; // hour → area → { earnings[], durationSec[] }
  for (const d of deliveries) {
    if (d.hour < 9 || d.hour > 23) continue;
    if (!matrix[d.hour]) matrix[d.hour] = {};
    if (!matrix[d.hour][d.area]) matrix[d.hour][d.area] = { earnings: [], durationSec: [] };
    matrix[d.hour][d.area].earnings.push(d.earnings);
    if (d.durationSec > 0) matrix[d.hour][d.area].durationSec.push(d.durationSec);
  }
  return matrix;
}

// 期待時給 = 平均単価 × (60分 ÷ 平均所要時間)
// データが少ないセルは時間帯全体→全体平均の順にフォールバック
function buildExpectedHourlyEarning(matrix, deliveries) {
  // フォールバック用: 時間帯全体の平均所要時間
  const hourAvgDur = {};
  for (const [h, areas] of Object.entries(matrix)) {
    const allDurs = Object.values(areas).flatMap(a => a.durationSec).filter(d => d > 0);
    if (allDurs.length > 0)
      hourAvgDur[h] = allDurs.reduce((a, b) => a + b, 0) / allDurs.length;
  }
  // フォールバック用: 全体平均所要時間
  const allDurs = deliveries.filter(d => d.durationSec > 0).map(d => d.durationSec);
  const overallAvgDur = allDurs.length > 0
    ? allDurs.reduce((a, b) => a + b, 0) / allDurs.length
    : 1200; // デフォルト20分

  const result = {};
  for (const [h, areas] of Object.entries(matrix)) {
    result[h] = {};
    for (const [area, cell] of Object.entries(areas)) {
      const s = stats(cell.earnings);
      // 所要時間: セル内に3件以上あればセル値、なければ時間帯→全体の順でフォールバック
      const durs = cell.durationSec.filter(d => d > 0);
      const avgDurSec = durs.length >= 3
        ? durs.reduce((a, b) => a + b, 0) / durs.length
        : (hourAvgDur[h] || overallAvgDur);
      const avgDurMin      = avgDurSec / 60;
      const delivPerHour   = 60 / avgDurMin; // 1時間に何件こなせるか
      const expectedHourly = s.mean * delivPerHour;

      result[h][area] = {
        ...s,
        avgDurMin,
        delivPerHour,
        expectedHourly,
      };
    }
  }
  return result;
}

// 連続配達ペア（同日内の連続する2件）から遷移行列を構築
function buildTransitionMatrix(deliveries) {
  const byDate = {};
  for (const d of deliveries) {
    if (!byDate[d.date]) byDate[d.date] = [];
    byDate[d.date].push(d);
  }
  // fromArea → toArea → toEarnings[]
  const matrix = {};
  for (const arr of Object.values(byDate)) {
    const sorted = arr.filter(d => d.hour !== null).sort((a, b) => a.hour - b.hour || 0);
    for (let i = 0; i < sorted.length - 1; i++) {
      const from = sorted[i].area, to = sorted[i + 1];
      if (!matrix[from]) matrix[from] = {};
      if (!matrix[from][to.area]) matrix[from][to.area] = [];
      matrix[from][to.area].push(to.earnings);
    }
  }
  return matrix;
}

// 各エリアから遷移した場合の最適次エリア（上位3）
function getBestTransitions(transMatrix, fromArea) {
  if (!transMatrix[fromArea]) return [];
  return Object.entries(transMatrix[fromArea])
    .map(([toArea, arr]) => ({ toArea, ...stats(arr) }))
    .filter(r => r.n >= 1)
    .sort((a, b) => b.mean - a.mean)
    .slice(0, 3);
}

// 各時間帯ブロックでの最適エリア（期待時給ベース）
function getBlockBestAreas(eMatrix, block, top = 3) {
  const all = {};
  for (const h of block.hours) {
    if (!eMatrix[h]) continue;
    for (const [area, data] of Object.entries(eMatrix[h])) {
      if (!all[area]) all[area] = { expectedHourlyList: [], meanList: [], delivPerHourList: [], durList: [] };
      all[area].expectedHourlyList.push(data.expectedHourly);
      all[area].meanList.push(data.mean);
      all[area].delivPerHourList.push(data.delivPerHour);
      all[area].durList.push(data.avgDurMin);
    }
  }
  const avg = arr => arr.reduce((a, b) => a + b, 0) / arr.length;
  return Object.entries(all)
    .map(([area, d]) => ({
      area,
      avgEarnings:    avg(d.meanList),
      avgDelivPerHour: avg(d.delivPerHourList),
      avgDurMin:      avg(d.durList),
      expectedHourly: avg(d.expectedHourlyList),
    }))
    .sort((a, b) => b.expectedHourly - a.expectedHourly)
    .slice(0, top);
}

// ── レポート生成 ──────────────────────────────────

function generateReport(mode, deliveries, days, from, to) {
  const N       = deliveries.length;
  const numDays = days.length;
  if (N === 0) return null;

  const matrix   = buildHourAreaMatrix(deliveries);
  const eMatrix  = buildExpectedHourlyEarning(matrix, deliveries);
  const transMx  = buildTransitionMatrix(deliveries);

  // 全体の平均所要時間・推定件数/時間（ベースライン用）
  const allDurs = deliveries.filter(d => d.durationSec > 0).map(d => d.durationSec);
  const overallAvgDurMin  = allDurs.length > 0 ? (allDurs.reduce((a,b) => a+b,0)/allDurs.length)/60 : 20;
  const overallDelivPerHr = 60 / overallAvgDurMin;
  const allStats = stats(deliveries.map(d => d.earnings));
  const modeLabel = mode === 'weekday' ? '平日' : '土日祝';

  // 全エリア一覧（出現回数上位）
  const areaCounts = {};
  for (const d of deliveries) areaCounts[d.area] = (areaCounts[d.area] || 0) + 1;
  const topAreas = Object.entries(areaCounts).sort((a, b) => b[1] - a[1]).map(([a]) => a).slice(0, 15);

  // 時間別TOP1エリア（期待時給ベース）
  const hourBestArea = {};
  for (const h of TARGET_HOURS) {
    if (!eMatrix[h]) { hourBestArea[h] = null; continue; }
    const ranked = Object.entries(eMatrix[h])
      .map(([area, d]) => ({ area, ...d }))
      .sort((a, b) => b.expectedHourly - a.expectedHourly);
    hourBestArea[h] = ranked[0] || null;
  }

  // ブロック別最適エリア
  const blockStrategy = BLOCKS.map(block => ({
    ...block, topAreas: getBlockBestAreas(eMatrix, block, 3),
  }));

  // 日次収益シミュレーション（戦略通りに動いた場合）
  let strategyDailyEarnings = 0;
  for (const h of TARGET_HOURS) {
    const best = hourBestArea[h];
    if (best) strategyDailyEarnings += best.expectedHourly;
  }
  // ベースライン：全体平均単価 × (60分÷全体平均所要時間) × 稼働時間
  const baselineDailyEarnings = allStats.mean * overallDelivPerHr * TARGET_HOURS.length;

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // Markdown 生成
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  let md = `# ${modeLabel}稼働最適化戦略レポート
**稼働想定**: 09:00〜23:00（14時間）　**分析ベース**: ${from} 〜 ${to}（${modeLabel} ${numDays}日・N=${N}件）
**生成日時**: ${new Date().toLocaleString('ja-JP')}

---

## 0. 戦略フレームワーク

Uber Eats 配達員が操作できる変数は以下の3つのみ。本レポートはこの3変数を最適化する。

| 変数 | 内容 | 本レポートでの対応 |
|---|---|---|
| **待機エリア** | 次の注文を受けるために待つ場所 | 時間別推奨エリアマップ（Section Ⅱ） |
| **オファー受諾/拒否** | 来た注文を受けるか断るか | 受諾判断マトリクス（Section Ⅴ） |
| **移動タイミング** | いつ別エリアへ移動するか | エリア遷移戦略（Section Ⅳ） |

> **基本思想**: 高単価注文が多い時間帯に、その注文が集中するエリアで待機する。
> 低単価エリアへの配達後は、積極的に高単価エリアへ再ポジショニングする。

---

## Ⅰ. 時間別エリア単価ヒートマップ（09〜23時）

> 各時間帯・エリアの**平均単価**（N≥1の実績のみ表示、—はデータなし）

`;

  // ヒートマップテーブル（行=エリア、列=時間帯）
  const heatHours = TARGET_HOURS;
  let hhdr = '| エリア |', hsep = '|---|';
  for (const h of heatHours) { hhdr += ` ${String(h).padStart(2,'0')}時 |`; hsep += '---|'; }
  hhdr += ' **合計N** | **平均** |'; hsep += '---|---|';
  md += hhdr + '\n' + hsep + '\n';

  for (const area of topAreas) {
    let row = `| **${area}** |`;
    let totalN = 0, totalEarnings = 0;
    for (const h of heatHours) {
      const d = eMatrix[h] && eMatrix[h][area];
      if (d && d.n > 0) {
        row += ` ${yen(d.mean)}(${d.n}) |`;
        totalN += d.n; totalEarnings += d.sum;
      } else { row += ' — |'; }
    }
    const areaAvg = totalN > 0 ? yen(totalEarnings / totalN) : '—';
    row += ` ${totalN} | **${areaAvg}** |`;
    md += row + '\n';
  }

  // 期待時給マップ（行=エリア、列=時間帯）
  md += `\n### 期待時給マップ（平均単価 ÷ 平均所要時間 × 60分）

> **期待時給** = 平均単価 × (60 ÷ 平均所要時間[分]) で算出。所要時間が短いほど1時間に多く回せる。
> **太字**は期待時給 ¥2,000以上のセル。

`;
  let ehdr = '| エリア |', esep = '|---|';
  for (const h of heatHours) { ehdr += ` ${String(h).padStart(2,'0')}時 |`; esep += '---|'; }
  md += ehdr + '\n' + esep + '\n';

  for (const area of topAreas) {
    let row = `| **${area}** |`;
    for (const h of heatHours) {
      const d = eMatrix[h] && eMatrix[h][area];
      if (d && d.n > 0) {
        const eh = d.expectedHourly;
        row += eh >= 2000 ? ` **${yen(eh)}** |` : ` ${yen(eh)} |`;
      } else { row += ' — |'; }
    }
    md += row + '\n';
  }

  md += `\n> 例: 平均単価¥800、平均所要時間20分 → 期待時給 ¥800×3件=¥2,400/h\n\n`;

  // ── Ⅱ. 時間ブロック別戦略
  md += `---

## Ⅱ. 時間ブロック別 最適エリア戦略

`;
  for (const block of blockStrategy) {
    const hoursLabel = `${String(block.hours[0]).padStart(2,'0')}〜${String(block.hours[block.hours.length-1]+1).padStart(2,'0')}時`;
    md += `### ${block.emoji} ${block.label}（${hoursLabel}）\n\n`;
    if (block.topAreas.length === 0) {
      md += '> データなし（この時間帯の配達実績がない）\n\n';
      continue;
    }
    md += `| 順位 | 推奨エリア | **期待時給** | 平均単価 | 平均所要時間 | 推定件数/時間 | 理由 |\n|---|---|---|---|---|---|---|\n`;
    for (const [i, a] of block.topAreas.entries()) {
      const rank = i === 0 ? '🥇 **最優先**' : i === 1 ? '🥈 次善' : '🥉 代替';
      const reason = i === 0
        ? `このブロックで最高の期待時給。待機拠点として最優先。`
        : i === 1
          ? `1位エリアが混雑・移動コスト高の場合の代替。`
          : `さらなる代替。1・2位エリアにポジションが取れない場合。`;
      md += `| ${rank} | **${a.area}** | **${yen(a.expectedHourly)}** | ${yen(a.avgEarnings)} | ${fmt1(a.avgDurMin)}分 | ${fmt1(a.avgDelivPerHour)}件 | ${reason} |\n`;
    }
    md += '\n';
  }

  // ── Ⅲ. 時刻表アクションプラン（09-23時）
  md += `---

## Ⅲ. 時刻表アクションプラン（09:00〜23:00）

> 1時間単位の推奨行動。「推奨エリア」は**期待時給**の高いエリア。
> 前の時間と同エリアの場合は**キープ**、異なる場合は**移動推奨**を示す。

| 時刻 | 推奨待機エリア | **期待時給** | 平均単価 | 所要時間 | 推定件数/h | アクション | 移動判断 |
|---|---|---|---|---|---|---|---|
`;
  let prevArea = null;
  for (const h of TARGET_HOURS) {
    const ranked = eMatrix[h]
      ? Object.entries(eMatrix[h]).map(([area, d]) => ({ area, ...d })).sort((a, b) => b.expectedHourly - a.expectedHourly)
      : [];
    const best = ranked[0] || null;
    const timeLabel = `${String(h).padStart(2,'0')}:00`;

    if (!best) {
      md += `| ${timeLabel} | — | — | — | — | — | データなし | — |\n`;
      continue;
    }

    const move = (prevArea && prevArea !== best.area)
      ? `🔄 **${prevArea}→${best.area}**へ移動`
      : prevArea === best.area
        ? '⏸ キープ'
        : '🚀 スタート';

    const action = (() => {
      if (h === 9)  return 'セッション開始。このエリアから稼働。';
      if (h === 11) return '🔥 ランチラッシュ開始。フル稼働。';
      if (h === 14) return 'ランチ後の閑散期。移動コストを考慮し最高期待値エリアへ。';
      if (h === 17) return 'ディナー前。夕方ラッシュ備えポジション確保。';
      if (h === 18) return '🔥 ディナーラッシュ開始。フル稼働。';
      if (h === 21) return '需要が落ち着く。高単価注文に絞り受諾。';
      if (h === 23) return '最終時間帯。遠距離案件は拒否。近距離高単価のみ。';
      return '前時間帯の戦略を継続。';
    })();

    md += `| **${timeLabel}** | **${best.area}** | **${yen(best.expectedHourly)}** | ${yen(best.mean)} | ${fmt1(best.avgDurMin)}分 | ${fmt1(best.delivPerHour)}件 | ${action} | ${move} |\n`;
    prevArea = best.area;
  }

  // ── Ⅳ. エリア遷移戦略
  md += `\n---

## Ⅳ. エリア遷移マトリクス（配達後の最適ポジショニング）

> 「このエリアに配達した後、次はどのエリアで待機すべきか」。
> 実績データから連続する2件の配達ペアを分析し、配達先エリアA → 次注文エリアBの単価を集計。

`;
  const transAreas = topAreas.slice(0, 10);
  md += `| 現在地（配達後） | 推奨次エリア① | 期待単価 | 推奨次エリア② | 期待単価 | 推奨次エリア③ | 期待単価 | 戦略 |\n`;
  md += `|---|---|---|---|---|---|---|---|\n`;

  for (const fromArea of transAreas) {
    const trans = getBestTransitions(transMx, fromArea);
    const t1 = trans[0], t2 = trans[1], t3 = trans[2];
    const strategy = !t1 ? '実績不足' :
      t1.toArea === fromArea ? `${fromArea}に留まれ（同エリア継続が最効率）` :
      `${t1.toArea}へ移動（期待単価差 +${yen(t1.mean - (stats(deliveries.filter(d=>d.area===fromArea).map(d=>d.earnings)).mean || 0))}）`;
    md += `| **${fromArea}** | ${t1 ? t1.toArea : '—'} | ${t1 ? yen(t1.mean) : '—'} | ${t2 ? t2.toArea : '—'} | ${t2 ? yen(t2.mean) : '—'} | ${t3 ? t3.toArea : '—'} | ${t3 ? yen(t3.mean) : '—'} | ${strategy} |\n`;
  }

  md += `\n> **読み方**: 渋谷区に配達後、次注文の期待単価が最も高いエリアへ移動。
> 同エリアが1位の場合は移動コスト（時間・体力）ゼロで最適。異エリアの場合は移動時間と単価差のトレードオフを考慮。\n\n`;

  // ── Ⅴ. オファー受諾判断基準
  md += `---

## Ⅴ. オファー受諾判断マトリクス

> 注文が来た際の受諾/拒否の基準。「現在いるエリア（高/低単価）」×「配達先エリア（高/低単価）」の4象限で判断。

### 判断マトリクス

| 現在地 × 配達先 | 配達先 = 高単価エリア | 配達先 = 低単価エリア |
|---|---|---|
| **現在地 = 高単価エリア** | ✅ **即受諾** — 単価維持+優良エリアへ配達 | ⚠️ **慎重** — 単価低下&戻り移動コスト発生。距離短ければ受諾 |
| **現在地 = 低単価エリア** | ✅ **受諾** — 低単価から脱出できる。たとえ単価低くても移動手段として活用 | ❌ **拒否推奨** — 低単価エリア→低単価エリアは生産性最悪。積極拒否し再ポジショニング待機 |

### ${modeLabel}高単価エリア vs 低単価エリア分類

`;
  const areaRanked = topAreas.map(area => {
    const arr = deliveries.filter(d => d.area === area).map(d => d.earnings);
    return { area, ...stats(arr) };
  }).sort((a, b) => b.mean - a.mean);

  const medianAreaMean = areaRanked[Math.floor(areaRanked.length / 2)]?.mean || allStats.mean;
  const highAreas = areaRanked.filter(a => a.mean >= medianAreaMean).map(a => a.area);
  const lowAreas  = areaRanked.filter(a => a.mean < medianAreaMean).map(a => a.area);

  md += `| 区分 | エリア一覧 | 平均単価目安 |\n|---|---|---|\n`;
  md += `| 🟢 **高単価エリア** | ${highAreas.join('・')} | ${yen(medianAreaMean)}以上 |\n`;
  md += `| 🔴 **低単価エリア** | ${lowAreas.join('・')} | ${yen(medianAreaMean)}未満 |\n\n`;

  md += `### 具体的な拒否基準
- **配達先が低単価エリア かつ 距離 > 3km**: 拒否推奨（移動コスト大・戻り困難）
- **現在地が高単価エリア かつ 配達先が低単価エリア かつ ピーク時間帯（11-14時・18-21時）**: 即拒否（機会損失が最大）
- **深夜（21-23時）かつ 配達先が遠距離（>4km）**: 拒否（セッション終了に間に合わない可能性）
- **単価提示が全体平均 ${yen(allStats.mean)} の70%以下（${yen(allStats.mean * 0.7)}未満）**: 原則拒否

\n`;

  // ── Ⅵ. 収益ポテンシャルシミュレーション
  md += `---

## Ⅵ. 収益ポテンシャルシミュレーション（09:00〜23:00）

> 期待時給ベースの日次収益推計。**実績データの平均を用いた期待値**であり、実際の収益を保証するものではない。

| シナリオ | 想定 | 推定日次収益 | 推定月収（22日稼働）|
|---|---|---|---|
| 🏆 **最適戦略** | 各時間の期待時給最高エリアで待機 | **${yen(strategyDailyEarnings)}** | **${yen(strategyDailyEarnings * 22)}** |
| 📊 **ベースライン** | エリア最適化なし（全体平均で稼働） | ${yen(baselineDailyEarnings)} | ${yen(baselineDailyEarnings * 22)} |
| 📈 **戦略プレミアム** | 最適戦略による上乗せ | **+${yen(strategyDailyEarnings - baselineDailyEarnings)}** | **+${yen((strategyDailyEarnings - baselineDailyEarnings) * 22)}** |

> **計算式**: 期待時給 = 平均単価 × (60分 ÷ 平均所要時間)
> 全体平均所要時間: ${fmt1(overallAvgDurMin)}分 → 理論最大 ${fmt1(overallDelivPerHr)}件/時間
> ⚠️ 上記は「待機時間ゼロ・全時間フル稼働」の理論値。実際は待機・移動時間があるため下振れする。

### 時間ブロック別 収益内訳（最適戦略）

| ブロック | 時間 | 推奨エリア | 期待時給 | ブロック小計 |
|---|---|---|---|---|
`;
  for (const block of blockStrategy) {
    const hoursCount = block.hours.length;
    const best = block.topAreas[0];
    const blockTotal = best ? best.expectedHourly * hoursCount : 0;
    const hoursLabel = `${String(block.hours[0]).padStart(2,'0')}-${String(block.hours[block.hours.length-1]+1).padStart(2,'0')}時`;
    md += `| ${block.emoji} ${block.label} | ${hoursLabel}（${hoursCount}h） | ${best ? best.area : '—'} | ${best ? yen(best.expectedHourly) : '—'} | ${best ? yen(blockTotal) : '—'} |\n`;
  }
  md += `| **合計** | 14時間 | — | — | **${yen(strategyDailyEarnings)}** |\n\n`;

  // ── Ⅶ. 総合戦略インサイト
  const topBlockByEarning = [...blockStrategy].filter(b => b.topAreas.length > 0).sort((a, b) => (b.topAreas[0]?.expectedHourly || 0) - (a.topAreas[0]?.expectedHourly || 0));
  const peakBlock = topBlockByEarning[0];
  const peakArea  = blockStrategy.flatMap(b => b.topAreas).sort((a, b) => b.expectedHourly - a.expectedHourly)[0];

  md += `---

## Ⅶ. 統合戦略インサイト & 実行優先順位

### 🎯 最重要アクション（この3つだけ実行すれば収益は最大化される）

1. **ピークブロックに全力を集中せよ**: \`${peakBlock?.label}\` ブロック（${peakBlock ? `${String(peakBlock.hours[0]).padStart(2,'0')}-${String(peakBlock.hours[peakBlock.hours.length-1]+1).padStart(2,'0')}時` : '—'}）が最高期待時給。このブロックは休憩なしでフル稼働。稼ぎの大半はここで決まる。

2. **最高値エリアの確保**: \`${peakArea?.area || '—'}\` が最高期待時給エリア（${peakArea ? yen(peakArea.expectedHourly) + '/時' : '—'}）。このエリア内のポジションを最優先で確保し、低単価エリアへの配達後は素早くリポジション。

3. **閑散時間帯の損切り**: ランチ後（14-17時）は期待値が下がる。低単価案件を拒否し、高単価エリアへの移動手段として案件を活用。時間を無駄にしないこと。

### 📋 ${modeLabel}特有の留意点

`;
  if (mode === 'weekday') {
    md += `- **オフィス需要の波**: 平日の昼（11-14時）はオフィスランチ需要がピーク。ビジネス街エリア（千代田区・中央区・港区）は特に高需要になりやすい。
- **夕方のリポジション**: 14-17時の閑散期に高単価エリアへの移動を完了させ、18時のディナーラッシュ開始と同時に最適ポジションにいること。
- **平日深夜（21-23時）**: 需要は限定的。距離が短く単価の高い案件に絞り込む。翌日に備えた体力温存も考慮。
`;
  } else {
    md += `- **レジャー消費の波**: 土日祝は外出後の帰宅時配達（夕方〜夜）と、外出前の昼食（11-13時）に二峰性の需要ピーク。
- **祝日の特殊性**: GW・連休中の祝日は通常の土日より需要が分散する可能性がある。連休初日は外出増・連休終盤は在宅増という傾向に注意。
- **イベント連動**: 花火大会・スポーツイベント当日は会場周辺のエリアが急騰する。events.jsのseedデータと照合し、当日の重点エリアを調整せよ。
- **土日の夜（21-23時）**: 平日より需要が持続しやすい。飲食後の帰宅需要。ただし遠距離案件はセッション終了を逆算して受諾判断。
`;
  }

  md += `
### ⚠️ 統計的留意事項（必読）

- **サンプル規模**: ${numDays}日・${N}件のデータに基づく。時間別・エリア別の分解では各セルのNが極めて小さくなる。N<3のセルは参考値以下として扱え。
- **期待時給の不確実性**: 注文数は確率変数であり、1日の分散が大きい。期待値は長期平均であり、単日では大きく外れることがある。
- **因果と相関**: 「エリアAの単価が高い」は「エリアAに行けば必ず高単価が来る」ことを意味しない。注文数・競合ドライバー数・天候などの交絡変数を排除できていない。
- **データ蓄積後の再校正**: 月次データが蓄積されたら本レポートを再生成し、推奨エリアを更新すること。初期フェーズの推奨はあくまで「現状ベストの仮説」に過ぎない。

---
*${modeLabel}稼働最適化戦略レポート — Goldman Sachs Analytics Edition*
*根拠データ: ${from} 〜 ${to} / ${modeLabel} ${numDays}日 / N=${N}件*
*生成: ${new Date().toLocaleString('ja-JP')}*
`;
  return md;
}

// ── メイン ────────────────────────────────────────

(async () => {
  const { mode, from, to } = getArgs();
  console.log(`=== ${mode === 'weekday' ? '平日' : '土日祝'}稼働最適化戦略生成 ===`);
  console.log(`期間: ${from} 〜 ${to}`);

  const { deliveries, days } = loadData(mode, from, to);
  if (deliveries.length === 0) {
    console.error('データなし。日付範囲とRAWデータファイルを確認してください。');
    process.exit(1);
  }

  console.log(`対象日: ${days.join(', ')} (${days.length}日)`);
  console.log(`総配達件数: ${deliveries.length}件`);

  if (!fs.existsSync(REPORTS_DIR)) fs.mkdirSync(REPORTS_DIR, { recursive: true });

  const md = generateReport(mode, deliveries, days, from, to);
  const outPath = path.join(REPORTS_DIR, `route-strategy-${mode}-${from}-${to}.md`);
  fs.writeFileSync(outPath, md, 'utf-8');

  console.log(`\n✅ 完了: ${outPath}`);
})();
