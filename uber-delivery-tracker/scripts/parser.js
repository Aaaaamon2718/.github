/**
 * parser.js - 完全版（天気×配達分析対応）
 *
 * 出力:
 *   data/reports/YYYY-MM-DD.md   → 人間が読むレポート
 *   data/reports/YYYY-MM-DD.json → 分析・ダッシュボード用
 *
 * 使用方法:
 *   node scripts/parser.js --date today
 *   node scripts/parser.js --date 2026-04-29
 */

const fs   = require('fs');
const path = require('path');

const args = process.argv.slice(2);
const dateArg    = args[args.indexOf('--date') + 1] || 'today';
const targetDate = dateArg === 'today'
  ? new Date().toISOString().slice(0, 10)
  : dateArg;

const RAW_PATH     = path.join(__dirname, `../data/raw/${targetDate}.json`);
const WEATHER_PATH = path.join(__dirname, `../data/weather/${targetDate}.json`);
const REPORTS_DIR  = path.join(__dirname, '../data/reports');
const MD_PATH      = path.join(REPORTS_DIR, `${targetDate}.md`);
const JSON_PATH    = path.join(REPORTS_DIR, `${targetDate}.json`);

if (!fs.existsSync(RAW_PATH)) {
  console.error(`❌ ${RAW_PATH} が見つかりません。先に scraper.js を実行してください。`);
  process.exit(1);
}
if (!fs.existsSync(REPORTS_DIR)) fs.mkdirSync(REPORTS_DIR, { recursive: true });

const raw = JSON.parse(fs.readFileSync(RAW_PATH, 'utf-8'));

// 天気データ読み込み（新形式 daily+hourly / 旧形式 フラット 両対応）
let weather = null;
if (fs.existsSync(WEATHER_PATH)) {
  const w = JSON.parse(fs.readFileSync(WEATHER_PATH, 'utf-8'));
  // 新形式: { daily: {...}, hourly: [...] }
  if (w.daily) {
    weather = w;
  } else {
    // 旧形式をラップ
    weather = {
      date: w.date, location: w.location, source: w.source,
      daily: {
        condition: w.condition, conditionCode: w.conditionCode,
        isRainy: w.isRainy, tempMax: w.tempMax, tempMin: w.tempMin,
        precipitation: w.precipitation, windspeedMax: w.windspeedMax,
      },
      hourly: null,
    };
  }
}

// 時間別天気ルックアップ（hourly データがある場合のみ）
const getWeatherAtHour = (hour) => {
  if (!weather?.hourly) return null;
  return weather.hourly.find(h => h.hour === hour) || null;
};

// ================================================================
// ユーティリティ
// ================================================================

const yen = n => `¥${Number(Math.round(n)).toLocaleString('ja-JP')}`;

const parseEarnings = d => {
  if (typeof d.earnings === 'number') return d.earnings;
  if (d.earningsText) { const m = d.earningsText.match(/¥([\d,]+)/); return m ? parseInt(m[1].replace(',','')) : 0; }
  return 0;
};
const parseDistance = d => {
  if (!d.distance) return 0;
  const m = String(d.distance).match(/([\d.]+)/);
  return m ? parseFloat(m[1]) : 0;
};
const parseDurationSec = d => {
  if (!d.duration) return 0;
  const m = String(d.duration).match(/(\d+)分(\d+)秒/);
  if (m) return parseInt(m[1])*60 + parseInt(m[2]);
  const m2 = String(d.duration).match(/(\d+):(\d+)/);
  if (m2) return parseInt(m2[1])*60 + parseInt(m2[2]);
  return 0;
};
const formatDuration = sec => {
  if (!sec) return '不明';
  return `${Math.floor(sec/60)}:${String(sec%60).padStart(2,'0')}`;
};
const parseTime = d => {
  if (!d.datetime) return '不明';
  const m = d.datetime.match(/(午前|午後)\s*(\d+)時(\d+)分/);
  if (!m) return d.datetime || '不明';
  let h = parseInt(m[2]);
  if (m[1]==='午後' && h!==12) h+=12;
  if (m[1]==='午前' && h===12) h=0;
  return `${String(h).padStart(2,'0')}:${m[3]}`;
};
const getHour = d => {
  if (!d.datetime) return -1;
  const m = d.datetime.match(/(午前|午後)\s*(\d+)時/);
  if (!m) return -1;
  let h = parseInt(m[2]);
  if (m[1]==='午後' && h!==12) h+=12;
  if (m[1]==='午前' && h===12) h=0;
  return h;
};
const getTimeSlot = d => {
  const h = getHour(d);
  if (h<0)            return 'その他';
  if (h>=6  && h<10) return '朝（6〜10時）';
  if (h>=10 && h<14) return '昼（10〜14時）';
  if (h>=14 && h<18) return '夕（14〜18時）';
  if (h>=18 && h<22) return '夜（18〜22時）';
  return 'その他';
};

// ================================================================
// データ整形
// ================================================================

const deliveries = raw.deliveries
  .filter(d => !d.error && parseEarnings(d) > 0)
  .map((d, i) => {
    const earnings    = parseEarnings(d);
    const distance    = parseDistance(d);
    const durationSec = parseDurationSec(d);
    const hour        = getHour(d);
    const hw          = getWeatherAtHour(hour);
    return {
      no:                i + 1,
      completedTime:     parseTime(d),
      datetime:          d.datetime || null,
      hour,
      timeSlot:          getTimeSlot(d),
      storeName:         (d.storeName   || '不明').trim(),
      area:              (d.destAddress || '不明').trim(),
      earnings,
      tip:               d.tip || 0,
      baseEarnings:      earnings - (d.tip || 0),
      distance,
      durationSec,
      durationFormatted: d.duration || formatDuration(durationSec),
      efficiency:        distance > 0 ? Math.round(earnings/distance) : 0,
      // 時間別天気
      weatherAtDelivery: hw,
    };
  });

// ================================================================
// マクロ集計
// ================================================================

const totalEarnings    = deliveries.reduce((s,d) => s+d.earnings, 0);
const totalDistance    = deliveries.reduce((s,d) => s+d.distance, 0);
const totalTip         = deliveries.reduce((s,d) => s+d.tip, 0);
const totalDurationSec = deliveries.reduce((s,d) => s+d.durationSec, 0);
const avgEarnings      = deliveries.length > 0 ? Math.round(totalEarnings/deliveries.length) : 0;
const avgDistance      = deliveries.length > 0 ? totalDistance/deliveries.length : 0;
const avgEfficiency    = totalDistance > 0 ? Math.round(totalEarnings/totalDistance) : 0;
const avgDurationSec   = deliveries.length > 0 ? Math.round(totalDurationSec/deliveries.length) : 0;

// ================================================================
// 分析軸
// ================================================================

const TIME_SLOTS = ['朝（6〜10時）','昼（10〜14時）','夕（14〜18時）','夜（18〜22時）','その他'];
const slotStats  = {};
TIME_SLOTS.forEach(s => slotStats[s] = {count:0, earnings:0, distance:0});
deliveries.forEach(d => {
  slotStats[d.timeSlot].count++;
  slotStats[d.timeSlot].earnings += d.earnings;
  slotStats[d.timeSlot].distance += d.distance;
});

const areaStats = {};
deliveries.forEach(d => {
  const key = d.area.match(/(.+?区)/)?.[1] || d.area;
  if (!areaStats[key]) areaStats[key] = {count:0, earnings:0, distance:0};
  areaStats[key].count++; areaStats[key].earnings += d.earnings; areaStats[key].distance += d.distance;
});
const areaRanking = Object.entries(areaStats)
  .map(([area,s]) => ({area, ...s, avgEarnings: Math.round(s.earnings/s.count)}))
  .sort((a,b) => b.earnings - a.earnings);

const storeStats = {};
deliveries.forEach(d => {
  if (!storeStats[d.storeName]) storeStats[d.storeName] = {count:0, earnings:0, distance:0};
  storeStats[d.storeName].count++; storeStats[d.storeName].earnings += d.earnings; storeStats[d.storeName].distance += d.distance;
});
const storeRanking = Object.entries(storeStats)
  .map(([store,s]) => ({store, ...s, avgEarnings: Math.round(s.earnings/s.count)}))
  .sort((a,b) => b.earnings - a.earnings).slice(0,10);

// 雨天 vs 晴天 分析
const rainyDeliveries = deliveries.filter(d => d.weatherAtDelivery?.isRainy);
const clearDeliveries = deliveries.filter(d => d.weatherAtDelivery && !d.weatherAtDelivery.isRainy);
const unknownDeliveries = deliveries.filter(d => !d.weatherAtDelivery);
const rainyEarnings = rainyDeliveries.reduce((s,d) => s+d.earnings, 0);
const clearEarnings = clearDeliveries.reduce((s,d) => s+d.earnings, 0);
const rainyAvg = rainyDeliveries.length > 0 ? Math.round(rainyEarnings/rainyDeliveries.length) : 0;
const clearAvg = clearDeliveries.length > 0 ? Math.round(clearEarnings/clearDeliveries.length) : 0;
const rainPremium = clearAvg > 0 ? Math.round((rainyAvg - clearAvg) / clearAvg * 100) : null;

// ================================================================
// 日付表示
// ================================================================

const [y,mo,da] = targetDate.split('-');
const dateObj   = new Date(`${targetDate}T12:00:00+09:00`);
const wday      = ['日','月','火','水','木','金','土'][dateObj.getDay()];
const dateJP    = `${y}年${parseInt(mo)}月${parseInt(da)}日（${wday}）`;

// ================================================================
// Markdown生成
// ================================================================

let md = '';
md += `# Uber Eats 配達レポート\n対象日: ${dateJP}\n\n`;

// ── 天気サマリー ──
if (weather?.daily) {
  const w    = weather.daily;
  const icon = w.isRainy ? '🌧️ ' : '☀️  ';
  md += `## 天気（東京）\n\n`;
  md += `| 天候 | 最高気温 | 最低気温 | 降水量 | 最大風速 |\n|---|---|---|---|---|\n`;
  md += `| ${icon}${w.condition} | ${w.tempMax}℃ | ${w.tempMin}℃ | ${w.precipitation}mm | ${w.windspeedMax ?? '-'} km/h |\n\n`;

  // 稼働時間帯の時間別天気（hourly がある場合）
  if (weather.hourly) {
    const activeHours = weather.hourly.filter(h => h.hour >= 10 && h.hour <= 22);
    if (activeHours.length > 0) {
      md += `### 時間別天気（稼働時間帯）\n\n`;
      md += `| 時刻 | 天候 | 気温 | 体感 | 降水量 | 降水確率 | 湿度 | 風速 |\n`;
      md += `|---|---|---|---|---|---|---|---|\n`;
      activeHours.forEach(h => {
        const hIcon = h.isRainy ? '🌧️' : '☀️';
        const prob  = h.precipitationProbability !== null ? `${h.precipitationProbability}%` : '—';
        md += `| ${h.time} | ${hIcon} ${h.condition} | ${h.temperature}℃ | ${h.apparentTemperature}℃ | ${h.precipitation}mm | ${prob} | ${h.humidity ?? '—'}% | ${h.windspeed}km/h |\n`;
      });
      md += '\n';
    }
  }

  if (w.isRainy) md += `> 🌧️ **雨天稼働日** — 天気プレミアムの影響を下記で確認してください\n\n`;
}

// ── 全体サマリー ──
md += `## 全体サマリー\n\n| 項目 | 値 |\n|---|---|\n`;
md += `| 総売上 | **${yen(totalEarnings)}** |\n`;
md += `| 配達件数 | **${deliveries.length} 件** |\n`;
md += `| 総距離 | **${totalDistance.toFixed(2)} km** |\n`;
md += `| 件単価（平均） | **${yen(avgEarnings)}** |\n`;
md += `| 平均距離 | **${avgDistance.toFixed(2)} km** |\n`;
md += `| 距離効率 | **${yen(avgEfficiency)}/km** |\n`;
md += `| 平均配達時間 | **${formatDuration(avgDurationSec)}** |\n`;
if (totalTip > 0) md += `| 総チップ | **${yen(totalTip)}** |\n`;
md += '\n';

// ── 雨天プレミアム分析 ──
if (weather?.hourly && (rainyDeliveries.length > 0 || clearDeliveries.length > 0)) {
  md += `## 🌧️ 雨天プレミアム分析\n\n`;
  md += `| 区分 | 件数 | 平均単価 | 合計売上 | 平均距離 |\n|---|---|---|---|---|\n`;
  if (clearDeliveries.length > 0) {
    const cd = clearDeliveries.reduce((s,d) => s+d.distance, 0) / clearDeliveries.length;
    md += `| ☀️ 晴れ・曇り | ${clearDeliveries.length}件 | ${yen(clearAvg)} | ${yen(clearEarnings)} | ${cd.toFixed(2)}km |\n`;
  }
  if (rainyDeliveries.length > 0) {
    const rd = rainyDeliveries.reduce((s,d) => s+d.distance, 0) / rainyDeliveries.length;
    md += `| 🌧️ 雨・にわか雨 | ${rainyDeliveries.length}件 | ${yen(rainyAvg)} | ${yen(rainyEarnings)} | ${rd.toFixed(2)}km |\n`;
  }
  if (rainPremium !== null && rainyDeliveries.length > 0 && clearDeliveries.length > 0) {
    const sign = rainPremium >= 0 ? '+' : '';
    md += `\n> 雨天プレミアム: **${sign}${rainPremium}%**（晴れ時との単価差）\n`;
  }
  md += '\n';
}

// ── 配達明細 ──
md += `## 配達明細\n\n`;
if (weather?.hourly) {
  md += `| No | 完了時刻 | 天気 | 気温 | ピック店舗 | エリア | 売上 | 距離 | 時間 |\n`;
  md += `|---|---|---|---|---|---|---|---|---|\n`;
  deliveries.forEach(d => {
    const hw      = d.weatherAtDelivery;
    const wIcon   = hw ? (hw.isRainy ? '🌧️' : '☀️') : '—';
    const wTemp   = hw ? `${hw.temperature}℃` : '—';
    const tipStr  = d.tip > 0 ? `<br>内チップ${yen(d.tip)}` : '';
    md += `| ${d.no} | ${d.completedTime} | ${wIcon} | ${wTemp} | ${d.storeName}${tipStr} | ${d.area} | ${yen(d.earnings)} | ${d.distance.toFixed(2)}km | ${d.durationFormatted} |\n`;
  });
} else {
  md += `| No | 完了時刻 | ピック店舗 | エリア | 売上 | 距離 | 時間 |\n`;
  md += `|---|---|---|---|---|---|---|\n`;
  deliveries.forEach(d => {
    const tipStr = d.tip > 0 ? `<br>内チップ${yen(d.tip)}` : '';
    md += `| ${d.no} | ${d.completedTime} | ${d.storeName}${tipStr} | ${d.area} | ${yen(d.earnings)} | ${d.distance.toFixed(2)}km | ${d.durationFormatted} |\n`;
  });
}
md += '\n';

// ── 時間帯別 ──
md += `## 時間帯別分析\n\n`;
md += `| 時間帯 | 件数 | 売上 | 平均単価 | 平均距離 | 効率(円/km) |\n|---|---|---|---|---|---|\n`;
TIME_SLOTS.forEach(slot => {
  const s = slotStats[slot];
  if (s.count === 0) return;
  md += `| ${slot} | ${s.count}件 | ${yen(s.earnings)} | ${yen(Math.round(s.earnings/s.count))} | ${(s.distance/s.count).toFixed(2)}km | ${yen(s.distance>0 ? Math.round(s.earnings/s.distance) : 0)} |\n`;
});
md += '\n';

// ── エリア別 ──
md += `## エリア別分析\n\n| エリア | 件数 | 売上 | 平均単価 |\n|---|---|---|---|\n`;
areaRanking.forEach(a => { md += `| ${a.area} | ${a.count}件 | ${yen(a.earnings)} | ${yen(a.avgEarnings)} |\n`; });
md += '\n';

// ── 店舗別 TOP10 ──
md += `## 店舗別売上 TOP10\n\n| 店舗 | 件数 | 売上 | 平均単価 |\n|---|---|---|---|\n`;
storeRanking.forEach(s => { md += `| ${s.store} | ${s.count}件 | ${yen(s.earnings)} | ${yen(s.avgEarnings)} |\n`; });
md += '\n';

// ── 効率 TOP5 ──
md += `## 距離効率 TOP5（円/km）\n\n| No | 店舗 | 売上 | 距離 | 効率 |\n|---|---|---|---|---|\n`;
[...deliveries].sort((a,b) => b.efficiency-a.efficiency).slice(0,5).forEach(d => {
  md += `| ${d.no} | ${d.storeName} | ${yen(d.earnings)} | ${d.distance.toFixed(2)}km | ${yen(d.efficiency)} |\n`;
});
md += '\n';

// ── 高単価 TOP5 ──
md += `## 高単価配達 TOP5\n\n| No | 店舗 | 売上 | 距離 | 時間 |\n|---|---|---|---|---|\n`;
[...deliveries].sort((a,b) => b.earnings-a.earnings).slice(0,5).forEach(d => {
  md += `| ${d.no} | ${d.storeName} | ${yen(d.earnings)} | ${d.distance.toFixed(2)}km | ${d.durationFormatted} |\n`;
});
md += '\n';

md += `---\n*Generated by Uber Delivery Tracker | ${new Date().toLocaleString('ja-JP', {timeZone:'Asia/Tokyo'})}*\n`;

// ================================================================
// JSON出力
// ================================================================

const jsonReport = {
  date: targetDate, dateJP,
  generatedAt: new Date().toISOString(),
  weather: weather || null,
  summary: {
    totalEarnings, totalCount: deliveries.length,
    totalDistance: parseFloat(totalDistance.toFixed(2)),
    totalTip, avgEarnings,
    avgDistance: parseFloat(avgDistance.toFixed(2)),
    avgEfficiency, avgDurationSec,
    avgDurationFormatted: formatDuration(avgDurationSec),
  },
  weatherAnalysis: weather?.hourly ? {
    rainyCount:   rainyDeliveries.length,
    clearCount:   clearDeliveries.length,
    unknownCount: unknownDeliveries.length,
    rainyAvgEarnings: rainyAvg,
    clearAvgEarnings: clearAvg,
    rainPremiumPct:   rainPremium,
  } : null,
  deliveries: deliveries.map(d => ({
    no: d.no, completedTime: d.completedTime, datetime: d.datetime,
    hour: d.hour, timeSlot: d.timeSlot, storeName: d.storeName, area: d.area,
    earnings: d.earnings, tip: d.tip, baseEarnings: d.baseEarnings,
    distance: d.distance, durationSec: d.durationSec,
    durationFormatted: d.durationFormatted, efficiency: d.efficiency,
    weatherAtDelivery: d.weatherAtDelivery,
  })),
  byTimeSlot: TIME_SLOTS.filter(s => slotStats[s].count > 0).map(s => ({
    label: s, count: slotStats[s].count, earnings: slotStats[s].earnings,
    distance: parseFloat(slotStats[s].distance.toFixed(2)),
    avgEarnings: Math.round(slotStats[s].earnings/slotStats[s].count),
    efficiency: slotStats[s].distance > 0 ? Math.round(slotStats[s].earnings/slotStats[s].distance) : 0,
  })),
  byArea: areaRanking.map(a => ({
    area: a.area, count: a.count, earnings: a.earnings,
    distance: parseFloat(a.distance.toFixed(2)), avgEarnings: a.avgEarnings,
  })),
  byStore: storeRanking.map(s => ({
    storeName: s.store, count: s.count, earnings: s.earnings,
    distance: parseFloat(s.distance.toFixed(2)), avgEarnings: s.avgEarnings,
  })),
};

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
if (weather?.hourly && (rainyDeliveries.length > 0 || clearDeliveries.length > 0)) {
  console.log(`  雨天件数  : ${rainyDeliveries.length}件 / 晴天件数: ${clearDeliveries.length}件`);
  if (rainPremium !== null) {
    const sign = rainPremium >= 0 ? '+' : '';
    console.log(`  雨天プレミアム: ${sign}${rainPremium}%`);
  }
}
console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
console.log(`\n🏆 エリア別売上`);
areaRanking.forEach((a,i) => console.log(`  ${i+1}. ${a.area}: ${yen(a.earnings)}（${a.count}件）`));
