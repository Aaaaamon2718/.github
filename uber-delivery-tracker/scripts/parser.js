/**
 * parser.js - 完全版
 *
 * PDFフォーマットを完全再現しつつ、分析・蓄積・進化のための
 * 多層データ構造を同時出力する。
 *
 * 出力:
 *   data/reports/YYYY-MM-DD.md   → PDFと同一の人間が読むレポート
 *   data/reports/YYYY-MM-DD.json → 分析・ダッシュボード用の構造化データ
 *
 * 使用方法:
 *   node scripts/parser.js --date today
 *   node scripts/parser.js --date 2026-04-21
 */

const fs   = require('fs');
const path = require('path');

// ---- 引数処理 ----
const args = process.argv.slice(2);
const dateArg    = args[args.indexOf('--date') + 1] || 'today';
const targetDate = dateArg === 'today'
  ? new Date().toISOString().slice(0, 10)
  : dateArg;

const RAW_PATH    = path.join(__dirname, `../data/raw/${targetDate}.json`);
const REPORTS_DIR = path.join(__dirname, '../data/reports');
const MD_PATH     = path.join(REPORTS_DIR, `${targetDate}.md`);
const JSON_PATH   = path.join(REPORTS_DIR, `${targetDate}.json`);

if (!fs.existsSync(RAW_PATH)) {
  console.error(`❌ ${RAW_PATH} が見つかりません。先に scraper.js を実行してください。`);
  process.exit(1);
}
if (!fs.existsSync(REPORTS_DIR)) fs.mkdirSync(REPORTS_DIR, { recursive: true });

const raw = JSON.parse(fs.readFileSync(RAW_PATH, 'utf-8'));

// ================================================================
// ユーティリティ
// ================================================================

const yen = (n) => `¥${Number(Math.round(n)).toLocaleString('ja-JP')}`;

const parseEarnings = (d) => {
  if (typeof d.earnings === 'number') return d.earnings;
  if (d.earningsText) {
    const m = d.earningsText.match(/¥([\d,]+)/);
    return m ? parseInt(m[1].replace(',', '')) : 0;
  }
  return 0;
};

const parseDistance = (d) => {
  if (!d.distance) return 0;
  const m = String(d.distance).match(/([\d.]+)/);
  return m ? parseFloat(m[1]) : 0;
};

const parseDurationSec = (d) => {
  if (!d.duration) return 0;
  const m = String(d.duration).match(/(\d+)分(\d+)秒/);
  if (m) return parseInt(m[1]) * 60 + parseInt(m[2]);
  const m2 = String(d.duration).match(/(\d+):(\d+)/);
  if (m2) return parseInt(m2[1]) * 60 + parseInt(m2[2]);
  return 0;
};

const formatDuration = (sec) => {
  if (!sec) return '不明';
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
};

const parseTime = (d) => {
  if (!d.datetime) return '不明';
  const m = d.datetime.match(/(午前|午後)\s*(\d+)時(\d+)分/);
  if (!m) return d.datetime || '不明';
  let hour = parseInt(m[2]);
  const min = m[3];
  if (m[1] === '午後' && hour !== 12) hour += 12;
  if (m[1] === '午前' && hour === 12) hour = 0;
  return `${String(hour).padStart(2, '0')}:${min}`;
};

const getHour = (d) => {
  if (!d.datetime) return -1;
  const m = d.datetime.match(/(午前|午後)\s*(\d+)時/);
  if (!m) return -1;
  let hour = parseInt(m[2]);
  if (m[1] === '午後' && hour !== 12) hour += 12;
  if (m[1] === '午前' && hour === 12) hour = 0;
  return hour;
};

const getTimeSlot = (d) => {
  const h = getHour(d);
  if (h < 0)              return 'その他';
  if (h >= 6  && h < 10) return '朝（6〜10時）';
  if (h >= 10 && h < 14) return '昼（10〜14時）';
  if (h >= 14 && h < 18) return '夕（14〜18時）';
  if (h >= 18 && h < 22) return '夜（18〜22時）';
  return 'その他';
};

const calcEfficiency = (earnings, distance) =>
  distance > 0 ? Math.round(earnings / distance) : 0;

// ================================================================
// データ整形
// ================================================================

const deliveries = raw.deliveries
  .filter(d => !d.error && parseEarnings(d) > 0)
  .map((d, i) => {
    const earnings     = parseEarnings(d);
    const distance     = parseDistance(d);
    const durationSec  = parseDurationSec(d);
    const tip          = d.tip || 0;
    const efficiency   = calcEfficiency(earnings, distance);
    return {
      no:                i + 1,
      completedTime:     parseTime(d),
      datetime:          d.datetime || null,
      hour:              getHour(d),
      timeSlot:          getTimeSlot(d),
      storeName:         (d.storeName  || '不明').trim(),
      area:              (d.destAddress || '不明').trim(),
      earnings,
      tip,
      baseEarnings:      earnings - tip,
      distance,
      durationSec,
      durationFormatted: d.duration || formatDuration(durationSec),
      efficiency,
    };
  });

// ================================================================
// マクロ集計
// ================================================================

const totalEarnings    = deliveries.reduce((s, d) => s + d.earnings, 0);
const totalDistance    = deliveries.reduce((s, d) => s + d.distance, 0);
const totalTip         = deliveries.reduce((s, d) => s + d.tip, 0);
const totalDurationSec = deliveries.reduce((s, d) => s + d.durationSec, 0);
const avgEarnings      = deliveries.length > 0 ? Math.round(totalEarnings / deliveries.length) : 0;
const avgDistance      = deliveries.length > 0 ? totalDistance / deliveries.length : 0;
const avgEfficiency    = totalDistance > 0 ? Math.round(totalEarnings / totalDistance) : 0;
const avgDurationSec   = deliveries.length > 0 ? Math.round(totalDurationSec / deliveries.length) : 0;

// ================================================================
// 分析軸① 時間帯別
// ================================================================

const TIME_SLOTS = ['朝（6〜10時）', '昼（10〜14時）', '夕（14〜18時）', '夜（18〜22時）', 'その他'];
const slotStats  = {};
TIME_SLOTS.forEach(s => slotStats[s] = { count: 0, earnings: 0, distance: 0, durationSec: 0 });
deliveries.forEach(d => {
  slotStats[d.timeSlot].count++;
  slotStats[d.timeSlot].earnings    += d.earnings;
  slotStats[d.timeSlot].distance    += d.distance;
  slotStats[d.timeSlot].durationSec += d.durationSec;
});

// ================================================================
// 分析軸② エリア別
// ================================================================

const areaStats = {};
deliveries.forEach(d => {
  const key = d.area.match(/(.+?区)/) ? d.area.match(/(.+?区)/)[1] : d.area;
  if (!areaStats[key]) areaStats[key] = { count: 0, earnings: 0, distance: 0 };
  areaStats[key].count++;
  areaStats[key].earnings += d.earnings;
  areaStats[key].distance += d.distance;
});
const areaRanking = Object.entries(areaStats)
  .map(([area, s]) => ({ area, ...s, avgEarnings: Math.round(s.earnings / s.count) }))
  .sort((a, b) => b.earnings - a.earnings);

// ================================================================
// 分析軸③ 店舗別
// ================================================================

const storeStats = {};
deliveries.forEach(d => {
  if (!storeStats[d.storeName]) storeStats[d.storeName] = { count: 0, earnings: 0, distance: 0 };
  storeStats[d.storeName].count++;
  storeStats[d.storeName].earnings += d.earnings;
  storeStats[d.storeName].distance += d.distance;
});
const storeRanking = Object.entries(storeStats)
  .map(([store, s]) => ({ store, ...s, avgEarnings: Math.round(s.earnings / s.count) }))
  .sort((a, b) => b.earnings - a.earnings)
  .slice(0, 10);

// ================================================================
// 日付表示
// ================================================================

const [y, mo, da] = targetDate.split('-');
const weekdays    = ['日', '月', '火', '水', '木', '金', '土'];
const dateObj     = new Date(`${targetDate}T12:00:00+09:00`);
const wday        = weekdays[dateObj.getDay()];
const dateJP      = `${y}年${parseInt(mo)}月${parseInt(da)}日（${wday}）`;

// ================================================================
// Markdown生成
// ================================================================

let md = '';

// ヘッダー（PDF完全再現）
md += `# Uber Eats 配達レポート（完全版）\n`;
md += `対象日: ${dateJP}\n\n`;

// ── マクロ：全体サマリー ──
md += `## 全体サマリー\n\n`;
md += `| 項目 | 値 |\n|---|---|\n`;
md += `| 総売上 | **${yen(totalEarnings)}** |\n`;
md += `| 配達件数 | **${deliveries.length} 件** |\n`;
md += `| 総距離 | **${totalDistance.toFixed(2)} km** |\n`;
md += `| 件単価（平均） | **${yen(avgEarnings)}** |\n`;
md += `| 平均距離 | **${avgDistance.toFixed(2)} km** |\n`;
md += `| 距離効率 | **${yen(avgEfficiency)}/km** |\n`;
md += `| 平均配達時間 | **${formatDuration(avgDurationSec)}** |\n`;
if (totalTip > 0) md += `| 総チップ | **${yen(totalTip)}** |\n`;
md += `\n`;

// ── ミクロ：配達明細テーブル（PDF完全再現） ──
md += `## 配達明細\n\n`;
md += `| No | 完了時刻 | ピック店舗 | エリア | 売上 | 距離 | 時間 |\n`;
md += `|---|---|---|---|---|---|---|\n`;
deliveries.forEach(d => {
  const tipStr = d.tip > 0 ? `<br>内チップ${yen(d.tip)}` : '';
  md += `| ${d.no} | ${d.completedTime} | ${d.storeName}${tipStr} | ${d.area} | ${yen(d.earnings)} | ${d.distance.toFixed(2)} km | ${d.durationFormatted} |\n`;
});
md += `\n`;

// ── 分析①：時間帯別 ──
md += `## 時間帯別分析\n\n`;
md += `| 時間帯 | 件数 | 売上 | 平均単価 | 平均距離 | 効率(円/km) |\n`;
md += `|---|---|---|---|---|---|\n`;
TIME_SLOTS.forEach(slot => {
  const s = slotStats[slot];
  if (s.count === 0) return;
  md += `| ${slot} | ${s.count}件 | ${yen(s.earnings)} | ${yen(Math.round(s.earnings / s.count))} | ${(s.distance / s.count).toFixed(2)} km | ${yen(s.distance > 0 ? Math.round(s.earnings / s.distance) : 0)} |\n`;
});
md += `\n`;

// ── 分析②：エリア別 ──
md += `## エリア別分析\n\n`;
md += `| エリア | 件数 | 売上 | 平均単価 |\n`;
md += `|---|---|---|---|\n`;
areaRanking.forEach(a => {
  md += `| ${a.area} | ${a.count}件 | ${yen(a.earnings)} | ${yen(a.avgEarnings)} |\n`;
});
md += `\n`;

// ── 分析③：店舗別 TOP10 ──
md += `## 店舗別売上 TOP10\n\n`;
md += `| 店舗 | 件数 | 売上 | 平均単価 |\n`;
md += `|---|---|---|---|\n`;
storeRanking.forEach(s => {
  md += `| ${s.store} | ${s.count}件 | ${yen(s.earnings)} | ${yen(s.avgEarnings)} |\n`;
});
md += `\n`;

// ── 分析④：効率 TOP5（円/km） ──
md += `## 距離効率 TOP5（円/km）\n\n`;
md += `| No | 店舗 | 売上 | 距離 | 効率(円/km) |\n`;
md += `|---|---|---|---|---|\n`;
[...deliveries].sort((a, b) => b.efficiency - a.efficiency).slice(0, 5).forEach(d => {
  md += `| ${d.no} | ${d.storeName} | ${yen(d.earnings)} | ${d.distance.toFixed(2)} km | ${yen(d.efficiency)} |\n`;
});
md += `\n`;

// ── 分析⑤：高単価 TOP5 ──
md += `## 高単価配達 TOP5\n\n`;
md += `| No | 店舗 | 売上 | 距離 | 時間 |\n`;
md += `|---|---|---|---|---|\n`;
[...deliveries].sort((a, b) => b.earnings - a.earnings).slice(0, 5).forEach(d => {
  md += `| ${d.no} | ${d.storeName} | ${yen(d.earnings)} | ${d.distance.toFixed(2)} km | ${d.durationFormatted} |\n`;
});
md += `\n`;

md += `---\n`;
md += `*Generated by Uber Delivery Tracker | ${new Date().toLocaleString('ja-JP', { timeZone: 'Asia/Tokyo' })}*\n`;

// ================================================================
// JSON出力（分析・ダッシュボード・将来の拡張用）
// ================================================================

const jsonReport = {
  date:        targetDate,
  dateJP,
  generatedAt: new Date().toISOString(),

  // マクロ
  summary: {
    totalEarnings,
    totalCount:          deliveries.length,
    totalDistance:       parseFloat(totalDistance.toFixed(2)),
    totalTip,
    avgEarnings,
    avgDistance:         parseFloat(avgDistance.toFixed(2)),
    avgEfficiency,
    avgDurationSec,
    avgDurationFormatted: formatDuration(avgDurationSec),
  },

  // ミクロ：全件明細
  deliveries: deliveries.map(d => ({
    no:                d.no,
    completedTime:     d.completedTime,
    datetime:          d.datetime,
    hour:              d.hour,
    timeSlot:          d.timeSlot,
    storeName:         d.storeName,
    area:              d.area,
    earnings:          d.earnings,
    tip:               d.tip,
    baseEarnings:      d.baseEarnings,
    distance:          d.distance,
    durationSec:       d.durationSec,
    durationFormatted: d.durationFormatted,
    efficiency:        d.efficiency,
  })),

  // 分析軸①
  byTimeSlot: TIME_SLOTS.filter(s => slotStats[s].count > 0).map(s => ({
    label:       s,
    count:       slotStats[s].count,
    earnings:    slotStats[s].earnings,
    distance:    parseFloat(slotStats[s].distance.toFixed(2)),
    avgEarnings: Math.round(slotStats[s].earnings / slotStats[s].count),
    efficiency:  slotStats[s].distance > 0 ? Math.round(slotStats[s].earnings / slotStats[s].distance) : 0,
  })),

  // 分析軸②
  byArea: areaRanking.map(a => ({
    area:        a.area,
    count:       a.count,
    earnings:    a.earnings,
    distance:    parseFloat(a.distance.toFixed(2)),
    avgEarnings: a.avgEarnings,
  })),

  // 分析軸③
  byStore: storeRanking.map(s => ({
    storeName:   s.store,
    count:       s.count,
    earnings:    s.earnings,
    distance:    parseFloat(s.distance.toFixed(2)),
    avgEarnings: s.avgEarnings,
  })),

  // 分析軸④
  efficiencyRanking: [...deliveries]
    .sort((a, b) => b.efficiency - a.efficiency)
    .map(d => ({
      no:         d.no,
      storeName:  d.storeName,
      efficiency: d.efficiency,
      earnings:   d.earnings,
      distance:   d.distance,
    })),
};

// ================================================================
// ファイル書き出し
// ================================================================

fs.writeFileSync(MD_PATH,   md, 'utf-8');
fs.writeFileSync(JSON_PATH, JSON.stringify(jsonReport, null, 2), 'utf-8');

console.log(`\n✅ レポート生成完了`);
console.log(`   Markdown : ${MD_PATH}`);
console.log(`   JSON     : ${JSON_PATH}`);
console.log(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
console.log(`📊 ${dateJP} サマリー`);
console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
console.log(`  総売上    : ${yen(totalEarnings)}`);
console.log(`  件数      : ${deliveries.length}件`);
console.log(`  総距離    : ${totalDistance.toFixed(2)} km`);
console.log(`  件単価    : ${yen(avgEarnings)}`);
console.log(`  距離効率  : ${yen(avgEfficiency)}/km`);
if (totalTip > 0) console.log(`  総チップ  : ${yen(totalTip)}`);
console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
console.log(`\n🏆 エリア別売上`);
areaRanking.forEach((a, i) => {
  console.log(`  ${i + 1}. ${a.area}: ${yen(a.earnings)}（${a.count}件）`);
});
