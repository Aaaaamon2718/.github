#!/usr/bin/env node
/**
 * 土日祝限定パフォーマンス分析レポート — Goldman Sachs Edition
 * 分析軸: 時間別・区分別（土/日/祝）・エリア・天気・距離効率・リスク調整後リターン
 * 実行: node scripts/weekend-holiday-analysis.js [--from YYYY-MM-DD] [--to YYYY-MM-DD]
 */

const fs = require('fs');
const path = require('path');

const RAW_DIR      = path.join(__dirname, '../data/raw');
const CALENDAR_DIR = path.join(__dirname, '../data/calendar');
const WEATHER_DIR  = path.join(__dirname, '../data/weather');
const REPORTS_DIR  = path.join(__dirname, '../data/reports');

// ── 定数 ─────────────────────────────────────────

const slotShort = s => s ? s.replace('時台', '時') : '—';
const DOW = ['日', '月', '火', '水', '木', '金', '土'];

// 区分の表示順
const DAYTYPE_ORDER = ['土', '日', '土祝', '日祝', '祝（平日）'];

// t分布 95%CI 用の臨界値（自由度 = n-1）
const T_CRITICAL = { 1: 12.71, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
  6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
  15: 2.131, 20: 2.086, 30: 2.042, 60: 2.000, 120: 1.980 };

function tCritical(n) {
  if (n <= 1) return 12.71;
  const keys = Object.keys(T_CRITICAL).map(Number).sort((a, b) => a - b);
  for (const k of keys) { if (n - 1 <= k) return T_CRITICAL[k]; }
  return 1.96;
}

// ── ユーティリティ ────────────────────────────────

function getArgs() {
  const args = process.argv.slice(2);
  const fi = args.indexOf('--from');
  const ti = args.indexOf('--to');
  return {
    from: fi !== -1 ? args[fi + 1] : '2026-04-29',
    to:   ti !== -1 ? args[ti + 1] : '2026-05-10',
  };
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

function getCalendarDay(dateStr) {
  const year = dateStr.split('-')[0];
  const p = path.join(CALENDAR_DIR, `${year}.json`);
  if (!fs.existsSync(p)) return null;
  const cal = JSON.parse(fs.readFileSync(p, 'utf-8'));
  return (cal.days && cal.days[dateStr]) || null;
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
  return `${String(hour).padStart(2, '0')}時台`;
}

function extractArea(fullAddress) {
  if (!fullAddress) return '不明';
  const addr = fullAddress.replace(/^東京都/, '');
  const wardMatch = addr.match(/^([^\s区]+区)/);
  return wardMatch ? wardMatch[1] : '不明';
}

// 区分ラベルを判定（土/日/土祝/日祝/祝（平日））
function getDayType(dateStr, calDay) {
  const dow = new Date(dateStr + 'T12:00:00+09:00').getDay();
  const isWeekend = dow === 0 || dow === 6;
  const isHol = !!(calDay && calDay.holiday);
  if (dow === 6) return isHol ? '土祝' : '土';
  if (dow === 0) return isHol ? '日祝' : '日';
  return '祝（平日）'; // 月〜金かつ祝日
}

function yen(n)     { return `¥${Math.round(n).toLocaleString('ja-JP')}`; }
function pct(a, b)  { return b > 0 ? (a / b * 100).toFixed(1) + '%' : '—'; }
function fmt1(n)    { return isFinite(n) ? n.toFixed(1) : '—'; }

function stats(arr) {
  if (!arr || arr.length === 0) return { n: 0, mean: 0, median: 0, max: 0, min: 0, sum: 0, std: 0, cv: 0, ci95: 0, sharpe: 0 };
  const sorted = [...arr].sort((a, b) => a - b);
  const n   = arr.length;
  const sum = arr.reduce((s, x) => s + x, 0);
  const mean = sum / n;
  const mid  = Math.floor(n / 2);
  const median = n % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
  const variance = n > 1 ? arr.reduce((s, x) => s + (x - mean) ** 2, 0) / (n - 1) : 0;
  const std  = Math.sqrt(variance);
  const cv   = mean > 0 ? std / mean : 0;
  const ci95 = n > 1 ? tCritical(n) * std / Math.sqrt(n) : 0;
  const sharpe = std > 0 ? mean / std : 0;
  return { n, sum, mean, median, max: sorted[n - 1], min: sorted[0], std, cv, ci95, sharpe };
}

function bar(value, max, width = 16) {
  const filled = max > 0 ? Math.round((value / max) * width) : 0;
  return '█'.repeat(Math.min(filled, width)) + '░'.repeat(Math.max(width - filled, 0));
}

function confidenceNote(n) {
  if (n < 5)  return '⚠️ 参考値';
  if (n < 10) return '△ 限定的';
  return '✓';
}

// ── 天気データ読み込み ─────────────────────────────

function loadWeather(date) {
  const p = path.join(WEATHER_DIR, `${date}.json`);
  if (!fs.existsSync(p)) return null;
  const raw = JSON.parse(fs.readFileSync(p, 'utf-8'));
  return raw.hourly ? raw : null;
}

function getWeatherAtHour(weather, hour) {
  if (!weather || hour === null) return null;
  return weather.hourly.find(h => h.hour === hour) || null;
}

// ── データ読み込み ────────────────────────────────

function loadWeekendHolidayData(from, to) {
  const result = [];
  const weatherCoverage = {};
  const datesMeta = {}; // date → { dayType, holidayName }

  for (const date of dateRange(from, to)) {
    const day    = new Date(date + 'T12:00:00+09:00');
    const dow    = day.getDay();
    const calDay = getCalendarDay(date);
    const isWeekend = dow === 0 || dow === 6;
    const isHoliday = !!(calDay && calDay.holiday);

    // 土日 OR 祝日のみ対象
    if (!isWeekend && !isHoliday) continue;

    const dayType = getDayType(date, calDay);
    const holidayName = calDay?.holiday || null;

    const rawPath = path.join(RAW_DIR, `${date}.json`);
    if (!fs.existsSync(rawPath)) { console.log(`  データなし: ${date}(${DOW[dow]}) [${dayType}]`); continue; }

    const raw     = JSON.parse(fs.readFileSync(rawPath, 'utf-8'));
    const weather = loadWeather(date);
    const valid   = (raw.deliveries || []).filter(d => !d.error);
    if (valid.length === 0) { console.log(`  0件スキップ: ${date}(${DOW[dow]}) [${dayType}]`); continue; }

    weatherCoverage[date] = !!weather;
    datesMeta[date] = { dayType, holidayName };

    const label = holidayName ? `${dayType}・${holidayName}` : dayType;
    console.log(`  読み込み: ${date}(${DOW[dow]}) [${label}] → ${valid.length}件 ${weather ? '✅天気あり' : '❌天気なし'}`);

    for (const d of valid) {
      const hour = parseHour(d.datetime);
      const w    = getWeatherAtHour(weather, hour);
      result.push({
        date,
        dow:     DOW[dow],
        dayType,
        holidayName,
        hour,
        slot:    slot(hour),
        earnings:    d.earnings || 0,
        distance:    d.distance || 0,
        durationSec: d.durationSec || 0,
        area:        extractArea(d.destAddress),
        storeName:   d.storeName || '—',
        isRainy:     w ? w.isRainy : null,
        weatherCond: w ? w.condition : null,
        tempC:       w ? w.temperature : null,
        precipMm:    w ? w.precipitation : null,
        yenPerKm:    (d.distance > 0) ? (d.earnings || 0) / d.distance : null,
        yenPerMin:   (d.durationSec > 0) ? (d.earnings || 0) / (d.durationSec / 60) : null,
      });
    }
  }
  return { deliveries: result, weatherCoverage, datesMeta };
}

// ── 分析関数 ─────────────────────────────────────

function groupBy(arr, key) {
  return arr.reduce((m, x) => { (m[x[key]] = m[x[key]] || []).push(x); return m; }, {});
}

// ── レポート生成 ──────────────────────────────────

function generateReport(deliveries, weatherCoverage, datesMeta, from, to) {
  const uniqueDates = [...new Set(deliveries.map(d => d.date))].sort();
  const N = deliveries.length;

  // ─ 基本統計
  const overallStats = stats(deliveries.map(d => d.earnings));

  // ─ 時間別（1時間粒度）
  const SLOT_ORDER = [...new Set(deliveries.filter(d => d.slot).map(d => d.slot))].sort();
  const bySlotGroup = groupBy(deliveries.filter(d => d.slot), 'slot');
  const bySlot = SLOT_ORDER
    .filter(s => bySlotGroup[s])
    .map(s => ({ slot: s, ...stats(bySlotGroup[s].map(d => d.earnings)),
      kmStats:  stats(bySlotGroup[s].filter(d => d.yenPerKm  !== null).map(d => d.yenPerKm)),
      minStats: stats(bySlotGroup[s].filter(d => d.yenPerMin !== null).map(d => d.yenPerMin)),
    }));
  const maxSlotMean = Math.max(...bySlot.map(s => s.mean));
  const sortedSlots = [...bySlot].sort((a, b) => b.mean - a.mean);
  const bestSlot  = sortedSlots[0];
  const worstSlot = sortedSlots[sortedSlots.length - 1];

  // ─ 区分別（土/日/祝）
  const byDayTypeGroup = groupBy(deliveries, 'dayType');
  const byDayType = DAYTYPE_ORDER
    .filter(t => byDayTypeGroup[t])
    .map(t => ({ dayType: t, ...stats(byDayTypeGroup[t].map(d => d.earnings)) }));

  // ─ エリア別
  const byAreaGroup = groupBy(deliveries, 'area');
  const byArea = Object.entries(byAreaGroup)
    .map(([area, arr]) => ({
      area,
      ...stats(arr.map(d => d.earnings)),
      kmStats:  stats(arr.filter(d => d.yenPerKm  !== null).map(d => d.yenPerKm)),
      minStats: stats(arr.filter(d => d.yenPerMin !== null).map(d => d.yenPerMin)),
    }))
    .sort((a, b) => b.mean - a.mean);

  // ─ エリア × 時間帯
  const areaSlotMap = {};
  for (const d of deliveries) {
    if (!d.slot) continue;
    const key = `${d.area}|||${d.slot}`;
    (areaSlotMap[key] = areaSlotMap[key] || []).push(d.earnings);
  }
  const areaSlotRank = Object.entries(areaSlotMap)
    .map(([key, arr]) => { const [area, s] = key.split('|||'); return { area, slot: s, ...stats(arr) }; })
    .filter(r => r.n >= 2)
    .sort((a, b) => b.mean - a.mean);

  // ─ 天気分析
  const withWeather = deliveries.filter(d => d.isRainy !== null);
  const rainy = withWeather.filter(d => d.isRainy);
  const clear = withWeather.filter(d => !d.isRainy);
  const rainyStats = stats(rainy.map(d => d.earnings));
  const clearStats = stats(clear.map(d => d.earnings));
  const rainPremium = clearStats.mean > 0
    ? Math.round((rainyStats.mean - clearStats.mean) / clearStats.mean * 100) : null;
  const hasWeather = withWeather.length > 0;

  // 天気 × 時間帯
  const weatherSlotMap = {};
  for (const d of withWeather.filter(x => x.slot)) {
    const key = `${d.isRainy ? '雨' : '晴'}|||${d.slot}`;
    (weatherSlotMap[key] = weatherSlotMap[key] || []).push(d.earnings);
  }

  // ─ Pareto 分析
  const sorted = [...deliveries].sort((a, b) => b.earnings - a.earnings);
  const top20pctN = Math.ceil(N * 0.2);
  const top20sum  = sorted.slice(0, top20pctN).reduce((s, d) => s + d.earnings, 0);
  const paretoRatio = pct(top20sum, overallStats.sum);

  // ─ 距離・時間効率
  const kmArr  = deliveries.filter(d => d.yenPerKm  !== null && d.distance > 0.5).map(d => d.yenPerKm);
  const minArr = deliveries.filter(d => d.yenPerMin !== null && d.durationSec > 60).map(d => d.yenPerMin);
  const kmStats  = stats(kmArr);
  const minStats = stats(minArr);

  // ─ 店舗別
  const byStoreGroup = groupBy(deliveries, 'storeName');

  function buildStoreEntry(name, arr) {
    const s = stats(arr.map(d => d.earnings));
    const mode = counts => Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] || '不明';
    const areaCounts = {}, slotCounts = {};
    for (const d of arr) {
      areaCounts[d.area] = (areaCounts[d.area] || 0) + 1;
      if (d.slot) slotCounts[d.slot] = (slotCounts[d.slot] || 0) + 1;
    }
    return {
      name, ...s,
      primaryArea: mode(areaCounts),
      primarySlot: mode(slotCounts),
      records: arr.slice().sort((a, b) => a.date.localeCompare(b.date) || (a.hour ?? 99) - (b.hour ?? 99)),
    };
  }

  const byStore = Object.entries(byStoreGroup)
    .map(([name, arr]) => buildStoreEntry(name, arr))
    .filter(s => s.n >= 2)
    .sort((a, b) => b.mean - a.mean);

  const highValueStores = Object.entries(byStoreGroup)
    .map(([name, arr]) => buildStoreEntry(name, arr))
    .filter(s => s.mean > overallStats.mean)
    .sort((a, b) => b.mean - a.mean);

  // ─ 日次 × 時間マトリクス
  const activeSlotsArr = bySlot.map(s => s.slot);
  const slotDateMatrix = {};
  for (const s of activeSlotsArr) slotDateMatrix[s] = {};
  for (const d of deliveries) {
    if (!d.slot) continue;
    (slotDateMatrix[d.slot][d.date] = slotDateMatrix[d.slot][d.date] || []).push(d.earnings);
  }

  // ─ 全体 Sharpe
  const overallSharpe = overallStats.std > 0
    ? (overallStats.mean / overallStats.std).toFixed(2) : '—';

  // ─ 対象日の注記（祝日名を付加）
  const dateLabels = uniqueDates.map(d => {
    const meta = datesMeta[d];
    const dow  = DOW[new Date(d + 'T12:00:00+09:00').getDay()];
    const tag  = meta?.holidayName ? `[${meta.holidayName}]` : `[${meta?.dayType ?? dow}]`;
    return `${d.slice(5)}(${dow})${tag}`;
  });

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // Markdown 生成
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  let md = `# 土日祝パフォーマンス精密分析レポート
**分析期間**: ${from} 〜 ${to}　**稼働日**: ${uniqueDates.length}日間（土曜・日曜・祝日）
**対象日**: ${dateLabels.join(' / ')}
**総サンプル数**: N = ${N}件　**生成日時**: ${new Date().toLocaleString('ja-JP')}

---

## Ⅰ. エグゼクティブサマリー

| 指標 | 値 | 補足 |
|---|---|---|
| 総売上 | **${yen(overallStats.sum)}** | ${uniqueDates.length}日間合計 |
| 総配達件数 | **${N}件** | 平均 ${fmt1(N / uniqueDates.length)}件/日 |
| 日平均売上 | **${yen(overallStats.sum / uniqueDates.length)}** | |
| 平均単価 | **${yen(overallStats.mean)}** | 95%CI: ±${yen(overallStats.ci95)} |
| 中央値単価 | ${yen(overallStats.median)} | 歪み: ${overallStats.mean > overallStats.median ? '右歪み（高額外れ値あり）' : '左歪み'} |
| 標準偏差 | ${yen(overallStats.std)} | CV = ${fmt1(overallStats.cv * 100)}%（${overallStats.cv < 0.3 ? '安定' : overallStats.cv < 0.5 ? '中程度' : '高ボラティリティ'}）|
| Sharpe Ratio | ${overallSharpe} | リスク調整後リターン（高いほど安定的に稼げる）|
| 最高単価 | ${yen(overallStats.max)} | |
| 最低単価 | ${yen(overallStats.min)} | |
| 上位20%の売上占有率 | **${paretoRatio}** | Pareto集中度 |
| 最高効率時間 | **${bestSlot?.slot ?? '—'}** | 平均 ${bestSlot ? yen(bestSlot.mean) : '—'}（Sharpe: ${bestSlot?.sharpe.toFixed(2) ?? '—'}）|
| 最低効率時間 | ${worstSlot?.slot ?? '—'} | 平均 ${worstSlot ? yen(worstSlot.mean) : '—'} |
${hasWeather ? `| 雨天プレミアム | **${rainPremium !== null ? (rainPremium >= 0 ? '+' : '') + rainPremium + '%' : '—'}** | 雨${rainyStats.n}件 vs 晴${clearStats.n}件 |` : '| 天気データ | なし | weather.jsを先に実行 |'}

`;

  // ── Ⅱ. 時間別単価分析（1時間粒度）
  md += `---

## Ⅱ. 時間別パフォーマンス分析（1時間粒度）

### A. 時間別 単価・効率サマリー

| 時間 | N | 平均単価 | 95%CI | 中央値 | Sharpe | ¥/km | ¥/分 | 効率バー |
|---|---|---|---|---|---|---|---|---|
`;
  for (const s of bySlot) {
    const km  = s.kmStats.n  > 0 ? yen(s.kmStats.mean)  : '—';
    const min = s.minStats.n > 0 ? yen(s.minStats.mean) : '—';
    md += `| **${s.slot}** | ${s.n} | ${yen(s.mean)} | ±${yen(s.ci95)} | ${yen(s.median)} | ${s.sharpe.toFixed(2)} | ${km} | ${min} | \`${bar(s.mean, maxSlotMean)}\` |\n`;
  }

  // 時間 × 日次推移マトリクス
  md += `\n### B. 時間 × 日次 単価推移マトリクス\n\n`;
  let h2 = '| 時間 |', sep2 = '|---|';
  for (const d of uniqueDates) {
    const meta = datesMeta[d];
    const dw   = DOW[new Date(d + 'T12:00:00+09:00').getDay()];
    const tag  = meta?.holidayName ? `祝` : (meta?.dayType ?? dw);
    h2  += ` ${d.slice(5)}(${tag}) |`;
    sep2 += '---|';
  }
  h2 += ' **平均** |'; sep2 += '---|';
  md += h2 + '\n' + sep2 + '\n';
  for (const s of activeSlotsArr) {
    let row = `| **${slotShort(s)}** |`;
    const allVals = [];
    for (const d of uniqueDates) {
      const arr = slotDateMatrix[s][d];
      if (arr && arr.length > 0) {
        const m = arr.reduce((a, b) => a + b) / arr.length;
        allVals.push(m);
        row += ` ${yen(m)}(${arr.length}件) |`;
      } else { row += ' — |'; }
    }
    const avg = allVals.length > 0 ? yen(allVals.reduce((a, b) => a + b) / allVals.length) : '—';
    row += ` **${avg}** |`;
    md += row + '\n';
  }

  // ── Ⅲ. 天気コントロール変数分析
  const missingWeatherDates = Object.entries(weatherCoverage).filter(([, v]) => !v).map(([d]) => d);
  const coveredDates = Object.entries(weatherCoverage).filter(([, v]) => v).map(([d]) => d);
  const weatherCoverageNote = missingWeatherDates.length > 0
    ? `\n> ⚠️ **天気データ欠落**: ${missingWeatherDates.join(', ')} — これらの日の配達は天気分析から除外。`
    + `\n> ✅ **天気あり**: ${coveredDates.join(', ')}（${withWeather.length}件 / 全${deliveries.length}件中 ${pct(withWeather.length, deliveries.length)}）\n`
    : '';

  md += `---

## Ⅲ. 天気コントロール変数分析
${weatherCoverageNote}`;
  if (!hasWeather) {
    md += '\n> ❌ 全日付で天気データなし。`node scripts/weather.js --date YYYY-MM-DD` を実行後に再生成してください。\n\n';
  } else {
    md += `
### A. 雨天 vs. 晴天 パフォーマンス比較

| 区分 | N | 平均単価 | 95%CI | 中央値 | Sharpe | 判定 |
|---|---|---|---|---|---|---|
| **雨天** ☔ | ${rainyStats.n} | ${yen(rainyStats.mean)} | ±${yen(rainyStats.ci95)} | ${yen(rainyStats.median)} | ${rainyStats.sharpe.toFixed(2)} | ${confidenceNote(rainyStats.n)} |
| **晴天** ☀️ | ${clearStats.n} | ${yen(clearStats.mean)} | ±${yen(clearStats.ci95)} | ${yen(clearStats.median)} | ${clearStats.sharpe.toFixed(2)} | ${confidenceNote(clearStats.n)} |
| **差分（雨プレミアム）** | — | **${rainPremium !== null ? (rainPremium >= 0 ? '+' : '') + rainPremium + '%' : '—'}** | — | — | — | |

> **解釈**: ${rainPremium === null ? 'データ不足' : rainPremium > 10 ? '雨天は明確に高単価。悪天候時は積極稼働推奨。' : rainPremium > 0 ? '雨天でやや高単価だが効果は軽微。' : '雨天でも単価優位性なし（ただし需要増の可能性）。'}

### B. 天気 × 時間帯 クロス分析

| 天気 × 時間帯 | N | 平均単価 | 最高 |
|---|---|---|---|
`;
    const wxSlotRows = Object.entries(weatherSlotMap)
      .map(([key, arr]) => { const [wx, s] = key.split('|||'); return { wx, slot: s, ...stats(arr) }; })
      .sort((a, b) => b.mean - a.mean);
    for (const r of wxSlotRows) {
      md += `| ${r.wx === '雨' ? '☔' : '☀️'} ${r.wx} × ${r.slot} | ${r.n} | ${yen(r.mean)} | ${yen(r.max)} |\n`;
    }
    md += '\n';
  }

  // ── Ⅳ. 距離・時間効率分析
  md += `---

## Ⅳ. 距離・時間効率分析（リソース効率指標）

### A. 全体効率指標

| 指標 | 平均 | 中央値 | 最高 | 最低 | N |
|---|---|---|---|---|---|
| ¥/km（距離効率） | ${yen(kmStats.mean)} | ${yen(kmStats.median)} | ${yen(kmStats.max)} | ${yen(kmStats.min)} | ${kmStats.n} |
| ¥/分（時間効率） | ${yen(minStats.mean)} | ${yen(minStats.median)} | ${yen(minStats.max)} | ${yen(minStats.min)} | ${minStats.n} |

> **¥/km** = 1km移動あたりの収益。高いほど近距離高単価ルート。
> **¥/分** = 1分あたりの収益。実質的な時給換算の根拠指標。

### B. 時間帯別 距離・時間効率

| 時間帯 | ¥/km | ¥/分 | 推定時給（×60分） |
|---|---|---|---|
`;
  for (const s of bySlot) {
    const km  = s.kmStats.n  > 0 ? yen(s.kmStats.mean)  : '—';
    const min = s.minStats.n > 0 ? yen(s.minStats.mean) : '—';
    const hourly = s.minStats.n > 0 ? yen(s.minStats.mean * 60) : '—';
    md += `| **${slotShort(s.slot)}** | ${km} | ${min} | **${hourly}** |\n`;
  }
  md += '\n';

  // ── Ⅴ. エリア分析
  md += `---

## Ⅴ. エリア別パフォーマンス分析

### A. エリア総合ランキング（上位15、平均単価順）

| 順位 | エリア | N | 平均単価 | 95%CI | Sharpe | ¥/km | 売上比率 | 信頼性 |
|---|---|---|---|---|---|---|---|---|
`;
  for (const [i, a] of byArea.slice(0, 15).entries()) {
    const km = a.kmStats.n > 0 ? yen(a.kmStats.mean) : '—';
    md += `| ${i + 1} | **${a.area}** | ${a.n} | ${yen(a.mean)} | ±${yen(a.ci95)} | ${a.sharpe.toFixed(2)} | ${km} | ${pct(a.sum, overallStats.sum)} | ${confidenceNote(a.n)} |\n`;
  }

  // エリア × 時間帯ヒートマップ
  const topAreas = byArea.slice(0, 12).map(a => a.area);
  const areaSlotData = {};
  for (const d of deliveries) {
    if (!d.slot) continue;
    if (!areaSlotData[d.area]) areaSlotData[d.area] = {};
    (areaSlotData[d.area][d.slot] = areaSlotData[d.area][d.slot] || []).push(d.earnings);
  }

  md += `\n### B. エリア × 時間帯 単価ヒートマップ（上位12エリア）\n\n`;
  let hh = '| エリア |', ss = '|---|';
  for (const s of activeSlotsArr) { hh += ` ${slotShort(s)} |`; ss += '---|'; }
  hh += ' 総平均 |'; ss += '---|';
  md += hh + '\n' + ss + '\n';
  for (const area of topAreas) {
    let row = `| **${area}** |`;
    const allE = [];
    for (const s of activeSlotsArr) {
      const arr = areaSlotData[area] && areaSlotData[area][s];
      if (arr && arr.length > 0) {
        const m = arr.reduce((a, b) => a + b) / arr.length;
        allE.push(...arr);
        row += ` ${yen(m)}(${arr.length}) |`;
      } else { row += ' — |'; }
    }
    const totalAvg = allE.length > 0 ? yen(allE.reduce((a, b) => a + b) / allE.length) : '—';
    row += ` **${totalAvg}** |`;
    md += row + '\n';
  }

  // エリア × 時間帯 ベストコンビランキング
  md += `\n### C. エリア × 時間帯 高単価コンビランキング（N≥2）\n\n`;
  md += `| 順位 | エリア | 時間帯 | N | 平均単価 | Sharpe | 最高 |\n|---|---|---|---|---|---|---|\n`;
  for (const [i, r] of areaSlotRank.slice(0, 10).entries()) {
    md += `| ${i + 1} | **${r.area}** | ${r.slot} | ${r.n} | ${yen(r.mean)} | ${r.sharpe.toFixed(2)} | ${yen(r.max)} |\n`;
  }
  md += '\n';

  // ── Ⅵ. 区分別パフォーマンス（土/日/祝）
  md += `---

## Ⅵ. 区分別パフォーマンス（土曜・日曜・祝日）

| 区分 | N | 平均単価 | 95%CI | 中央値 | 最高 | Sharpe |
|---|---|---|---|---|---|---|
`;
  for (const t of byDayType) {
    md += `| **${t.dayType}** | ${t.n} | ${yen(t.mean)} | ±${yen(t.ci95)} | ${yen(t.median)} | ${yen(t.max)} | ${t.sharpe.toFixed(2)} |\n`;
  }

  // 区分 × 時間帯 クロス
  md += `\n### 区分 × 時間帯 クロス分析\n\n`;
  const dayTypeSlotMap = {};
  for (const d of deliveries.filter(x => x.slot)) {
    const key = `${d.dayType}|||${d.slot}`;
    (dayTypeSlotMap[key] = dayTypeSlotMap[key] || []).push(d.earnings);
  }
  const presentDayTypes = DAYTYPE_ORDER.filter(t => byDayTypeGroup[t]);
  let dth = '| 時間 |', dts = '|---|';
  for (const t of presentDayTypes) { dth += ` ${t} |`; dts += '---|'; }
  md += dth + '\n' + dts + '\n';
  for (const s of activeSlotsArr) {
    let row = `| **${slotShort(s)}** |`;
    for (const t of presentDayTypes) {
      const arr = dayTypeSlotMap[`${t}|||${s}`];
      row += arr ? ` ${yen(arr.reduce((a, b) => a + b) / arr.length)}(${arr.length}) |` : ' — |';
    }
    md += row + '\n';
  }
  md += '\n';

  // ── Ⅶ. 店舗別（n>=2）
  md += `---

## Ⅶ. 出店ブランド別単価（N≥2 上位10）

| 順位 | 店舗 | N | 平均単価 | 最高 |
|---|---|---|---|---|
`;
  for (const [i, s] of byStore.slice(0, 10).entries()) {
    const name = s.name.slice(0, 28) + (s.name.length > 28 ? '…' : '');
    md += `| ${i + 1} | ${name} | ${s.n} | ${yen(s.mean)} | ${yen(s.max)} |\n`;
  }
  md += '\n';

  // ── Ⅷ. 収益分布（パレート）
  const pctiles = [10, 25, 50, 75, 90, 95].map(p => {
    const idx = Math.floor(sorted.length * p / 100);
    return { p, val: sorted[idx]?.earnings ?? 0 };
  });
  md += `---

## Ⅷ. 収益分布分析

### パーセンタイル分布

| パーセンタイル | 単価 | 意味 |
|---|---|---|
`;
  md += `| 10th | ${yen(pctiles[0].val)} | 下位10%ラインの案件 |\n`;
  md += `| 25th | ${yen(pctiles[1].val)} | 下位25%（Q1） |\n`;
  md += `| 50th | ${yen(pctiles[2].val)} | 中央値 |\n`;
  md += `| 75th | ${yen(pctiles[3].val)} | 上位25%（Q3） |\n`;
  md += `| 90th | ${yen(pctiles[4].val)} | 上位10%ライン |\n`;
  md += `| 95th | ${yen(pctiles[5].val)} | 上位5%（高単価案件） |\n`;
  md += `\n**Pareto集中度**: 上位20%の案件（${top20pctN}件）が総売上の **${paretoRatio}** を占める。\n\n`;

  // ── Ⅸ. 統合インサイト & 推奨アクション
  const bestDayType = [...byDayType].sort((a, b) => b.mean - a.mean)[0];
  md += `---

## Ⅸ. 統合インサイト & 推奨アクション（GS水準）

### 🎯 最優先アクション（ROI最大化）

`;
  if (bestSlot) {
    md += `1. **稼働時間の集中**: \`${bestSlot.slot}\` が最高効率（¥${Math.round(bestSlot.mean)}/件、Sharpe ${bestSlot.sharpe.toFixed(2)}）。この時間帯のシフト比率を最大化せよ。\n`;
  }
  if (areaSlotRank.length > 0) {
    const t = areaSlotRank[0];
    md += `2. **ゴールデンコンビ確保**: \`${t.slot}\` × \`${t.area}\` は最高単価コンビ（平均 ${yen(t.mean)}）。この時間帯はエリア内待機を優先せよ。\n`;
  }
  if (byArea.length > 0) {
    const topA = byArea.slice(0, 3).map(a => a.area).join('・');
    md += `3. **高単価エリア優先**: \`${topA}\` が単価上位3エリア。遠回りしてでもこのエリアのオファーを受け入れる価値がある。\n`;
  }
  if (bestDayType) {
    md += `4. **高単価区分の優先稼働**: \`${bestDayType.dayType}\` が最高単価区分（平均 ${yen(bestDayType.mean)}/件）。稼働日の選択肢がある場合はこの区分を優先せよ。\n`;
  }

  md += `
### 📊 天気戦略
`;
  if (hasWeather && rainPremium !== null) {
    if (rainPremium > 10) {
      md += `- **雨天時は確実に稼働せよ**: 雨天プレミアム +${rainPremium}%。競合ドライバーが減る中、需要増・単価増の二重メリット。\n`;
    } else if (rainPremium > 0) {
      md += `- 雨天プレミアムは軽微（+${rainPremium}%）。単価への直接効果より、競合減少による受注率向上が主効果と推測される。\n`;
    } else {
      md += `- 現時点のデータでは雨天プレミアムは確認されない（${rainPremium}%）。継続モニタリングが必要。\n`;
    }
  } else {
    md += '- 天気データを蓄積後に再分析が必要。`weather.js` を各日付に対して実行すること。\n';
  }

  md += `
### ⚠️ 統計的留意事項（必読）

- **サンプル規模の制約**: 本分析は土日祝${uniqueDates.length}日・N=${N}件に基づく。特にエリア×時間帯の組み合わせでN<5の結果は参考値扱いとし、月次データ蓄積後の再検証を推奨。
- **GW特有のバイアス**: 本分析期間にGW連休が含まれる場合、平常の土日祝と需要パターンが異なる可能性が高い。GW期間データと通常週末データの分離分析を将来的に推奨。
- **祝日の異質性**: 「祝（平日）」は曜日構造が平日と同一だが需要は休日型。連休中日か単独祝日かで行動パターンが大きく異なる点に注意。
- **因果性の注意**: 本レポートは相関分析であり因果関係を示すものではない。
- **Sharpe Ratio の解釈**: ここでのSharpe比は（平均単価）÷（標準偏差）。無リスクレート控除なし。時間帯・区分間の相対比較指標として使用すること。

---

## 📋 参考データ: 高単価店舗リスト（全体平均 ${yen(overallStats.mean)} 超え）

> 全体平均単価を上回る店舗の一覧。「配達先エリア」は顧客住所から取得した最多区（店舗所在地とは異なる場合がある）。
> 「時間帯」はその店舗からの注文が最も多い時間帯。

| 順位 | 店舗名 | N | 平均単価 | 最高単価 | 配達先エリア | 主な時間帯 | vs 全体平均 |
|---|---|---|---|---|---|---|---|
${highValueStores.map((s, i) => {
  const diff = Math.round((s.mean - overallStats.mean) / overallStats.mean * 100);
  const sign = diff >= 0 ? '+' : '';
  return `| ${i + 1} | **${s.name.slice(0, 30)}** | ${s.n} | ${yen(s.mean)} | ${yen(s.max)} | ${s.primaryArea} | ${s.primarySlot} | **${sign}${diff}%** |`;
}).join('\n') || '| — | 平均超えの店舗なし | — | — | — | — | — | — |'}

### 配達履歴詳細

${highValueStores.map(s => {
  const rows = s.records.map(r => {
    const meta = datesMeta[r.date];
    const dw   = DOW[new Date(r.date + 'T12:00:00+09:00').getDay()];
    const tag  = meta?.holidayName ? `祝` : (meta?.dayType ?? dw);
    return `| ${r.date.slice(5)}(${tag}) | ${r.slot || '—'} | ${r.area} | ${yen(r.earnings)} |`;
  }).join('\n');
  return `#### ${s.name}\n| 日付 | 時間帯 | 配達先エリア | 単価 |\n|---|---|---|---|\n${rows}`;
}).join('\n\n') || '> データなし'}

---
*土日祝パフォーマンス精密分析レポート — Goldman Sachs Analytics Edition*
*生成: ${new Date().toLocaleString('ja-JP')}*
`;
  return md;
}

// ── メイン ────────────────────────────────────────

(async () => {
  const { from, to } = getArgs();
  console.log(`=== 土日祝限定精密分析 ===`);
  console.log(`期間: ${from} 〜 ${to}`);

  const { deliveries, weatherCoverage, datesMeta } = loadWeekendHolidayData(from, to);
  if (deliveries.length === 0) {
    console.error('データなし。日付範囲とファイルを確認してください。');
    process.exit(1);
  }

  const uniqueDates = [...new Set(deliveries.map(d => d.date))].sort();
  const missingW = Object.entries(weatherCoverage).filter(([, v]) => !v).map(([d]) => d);
  console.log(`\n対象土日祝: ${uniqueDates.join(', ')} (${uniqueDates.length}日)`);
  console.log(`総配達件数: ${deliveries.length}件`);
  if (missingW.length > 0) console.log(`⚠️ 天気データ欠落日: ${missingW.join(', ')}`);

  if (!fs.existsSync(REPORTS_DIR)) fs.mkdirSync(REPORTS_DIR, { recursive: true });

  const md = generateReport(deliveries, weatherCoverage, datesMeta, from, to);
  const outPath = path.join(REPORTS_DIR, `weekend-holiday-analysis-${from}-${to}.md`);
  fs.writeFileSync(outPath, md, 'utf-8');

  console.log(`\n✅ 完了: ${outPath}`);
})();
