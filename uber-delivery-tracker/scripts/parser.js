#!/usr/bin/env node
/**
 * 生JSONデータをMarkdownレポートに変換するパーサー
 * 実行: node scripts/parser.js [--date YYYY-MM-DD|today]
 */

const fs = require('fs');
const path = require('path');

const RAW_DIR = path.join(__dirname, '../data/raw');
const REPORTS_DIR = path.join(__dirname, '../data/reports');
const WEATHER_DIR = path.join(__dirname, '../data/weather');
const CALENDAR_DIR = path.join(__dirname, '../data/calendar');

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
  return `¥${Math.round(amount).toLocaleString('ja-JP')}`;
}

function formatJapaneseDate(dateStr) {
  const [y, m, d] = dateStr.split('-');
  return `${y}年${parseInt(m)}月${parseInt(d)}日`;
}

// "2026年4月29日 午後11時14分" → "23:14"
function parseTime(datetimeStr) {
  if (!datetimeStr) return null;
  const m = datetimeStr.match(/(午前|午後)(\d+)時(\d+)分/);
  if (!m) return null;
  let hour = parseInt(m[2]);
  const minute = parseInt(m[3]);
  if (m[1] === '午後' && hour !== 12) hour += 12;
  if (m[1] === '午前' && hour === 12) hour = 0;
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`;
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

function loadCalendar(date) {
  const year = date.split('-')[0];
  const p = path.join(CALENDAR_DIR, `${year}.json`);
  if (!fs.existsSync(p)) return null;
  const cal = JSON.parse(fs.readFileSync(p, 'utf-8'));
  return cal.days[date] || null;
}

function loadWeather(date) {
  const p = path.join(WEATHER_DIR, `${date}.json`);
  if (!fs.existsSync(p)) return null;
  const raw = JSON.parse(fs.readFileSync(p, 'utf-8'));
  // 旧フォーマット（フラット）と新フォーマット（{daily,hourly}）の両対応
  if (raw.hourly && Array.isArray(raw.hourly)) return raw;
  return null;
}

function getWeatherAtHour(weather, timeStr) {
  if (!weather || !timeStr) return null;
  const m = timeStr.match(/(\d{1,2}):/);
  if (!m) return null;
  const hour = parseInt(m[1]);
  return weather.hourly.find(h => h.hour === hour) || null;
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
    const slot = getTimeSlot(parseTime(d.datetime));
    if (slots[slot]) {
      slots[slot].count++;
      slots[slot].earnings += d.earnings || 0;
    }
  }

  const rows = Object.entries(slots)
    .filter(([, v]) => v.count > 0)
    .map(([slot, v]) => `| ${slot} | ${v.count}件 | ${formatYen(v.earnings)} |`)
    .join('\n');

  return rows || '| （データなし） | — | — |';
}

function buildDetailSection(delivery, index, weather) {
  if (delivery.error) {
    return `### No.${index} — 取得エラー\n- エラー: ${delivery.error}\n`;
  }

  const timeStr = parseTime(delivery.datetime);
  const w = getWeatherAtHour(weather, timeStr);
  const timeDisplay = timeStr || delivery.datetime || '時刻不明';
  const lines = [`### No.${index} — ${timeDisplay}完了`];
  if (delivery.storeName) lines.push(`- **店舗**: ${delivery.storeName}`);
  if (delivery.destAddress) lines.push(`- **エリア**: ${delivery.destAddress}`);

  const tip = delivery.tip || delivery.tipAmount || 0;
  const earningsStr = tip > 0
    ? `${formatYen(delivery.earnings)}（チップ: ${formatYen(tip)}含む）`
    : formatYen(delivery.earnings || 0);
  lines.push(`- **売上**: ${earningsStr}`);

  if (delivery.distance != null) lines.push(`- **距離**: ${delivery.distance.toFixed(2)} km`);
  if (delivery.duration) lines.push(`- **所要時間**: ${delivery.duration}`);

  if (w) {
    const rainMark = w.isRainy ? ' 🌧' : '';
    lines.push(`- **天気**: ${w.condition}${rainMark}（${w.temperature}℃ / 降水${w.precipitation}mm）`);
  }

  return lines.join('\n');
}

function buildCalendarSection(cal) {
  if (!cal) return '';
  const typeStr = cal.types.join(' / ');
  const longWeekend = cal.isLongWeekend ? '（連休）' : '';
  return `## この日のコンテキスト
- 曜日: ${cal.dayOfWeek}曜日${longWeekend}
- 区分: ${typeStr}
${cal.holiday ? `- 祝日: ${cal.holiday}\n` : ''}
`;
}

function buildWeatherSection(weather) {
  if (!weather) return '';

  const d = weather.daily;
  const hourlyTable = weather.hourly
    .filter(h => h.hour >= 10 && h.hour <= 22)
    .map(h => {
      const prob = h.precipitationProbability !== null ? `${h.precipitationProbability}%` : '—';
      const rain = h.isRainy ? ' 🌧' : '';
      return `| ${String(h.hour).padStart(2, '0')}:00 | ${h.condition}${rain} | ${h.temperature}℃ | ${h.precipitation}mm | ${prob} |`;
    })
    .join('\n');

  return `## 天気（${weather.location}）
- 天気: ${d.condition}
- 気温: ${d.temperatureMin}℃ 〜 ${d.temperatureMax}℃
- 降水量: ${d.precipitationSum}mm | 最大風速: ${d.windspeedMax}km/h
- データ元: ${weather.source}

### 時間帯別天気（10〜22時）
| 時間 | 天気 | 気温 | 降水量 | 降水確率 |
|---|---|---|---|---|
${hourlyTable || '| — | — | — | — | — |'}

`;
}

function buildRainPremiumSection(deliveries, weather) {
  if (!weather) return '';

  const withWeather = deliveries.filter(d => !d.error && d.weatherAtDelivery);
  if (withWeather.length === 0) return '';

  const rainy = withWeather.filter(d => d.weatherAtDelivery.isRainy);
  const clear = withWeather.filter(d => !d.weatherAtDelivery.isRainy);

  if (rainy.length === 0 || clear.length === 0) return '';

  const rainyAvg = rainy.reduce((s, d) => s + (d.earnings || 0), 0) / rainy.length;
  const clearAvg = clear.reduce((s, d) => s + (d.earnings || 0), 0) / clear.length;
  const premiumPct = Math.round((rainyAvg - clearAvg) / clearAvg * 100);
  const sign = premiumPct >= 0 ? '+' : '';

  return `## 雨天プレミアム分析
| 区分 | 件数 | 平均単価 |
|---|---|---|
| 雨天時 🌧 | ${rainy.length}件 | ${formatYen(rainyAvg)} |
| 晴天時 ☀️ | ${clear.length}件 | ${formatYen(clearAvg)} |
| **差分** | — | **${sign}${premiumPct}%** |

`;
}

function generateMarkdown(data, weather, cal) {
  const valid = data.deliveries.filter(d => !d.error);
  const totalEarnings = valid.reduce((s, d) => s + (d.earnings || 0), 0);
  const totalTips = valid.reduce((s, d) => s + (d.tip || d.tipAmount || 0), 0);
  const totalDistance = valid.reduce((s, d) => s + (d.distance || 0), 0);
  const avgEarnings = valid.length > 0 ? Math.round(totalEarnings / valid.length) : 0;

  // 各配達に天気情報を付与
  for (const d of valid) {
    d.weatherAtDelivery = getWeatherAtHour(weather, parseTime(d.datetime));
  }

  const details = data.deliveries
    .map((d, i) => buildDetailSection(d, i + 1, weather))
    .join('\n\n');

  const calendarSection = buildCalendarSection(cal);
  const weatherSection = buildWeatherSection(weather);
  const rainPremiumSection = buildRainPremiumSection(valid, weather);

  return `# Uber Eats 配達レポート — ${formatJapaneseDate(data.date)}

## サマリー
- 総売上: ${formatYen(totalEarnings)}
- 配達件数: ${valid.length}件
- 総距離: ${totalDistance.toFixed(2)} km
- 平均単価: ${formatYen(avgEarnings)}
- 総チップ: ${formatYen(totalTips)}

${calendarSection}${weatherSection}${rainPremiumSection}## 配達明細

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
  const weather = loadWeather(date);
  const cal = loadCalendar(date);

  if (weather) {
    console.log(`天気データ読み込み: ${weather.source}`);
  } else {
    console.log('天気データなし（weather.jsを先に実行してください）');
  }
  if (cal) {
    console.log(`カレンダー: ${cal.types.join(' / ')}`);
  } else {
    console.log('カレンダーデータなし（calendar.jsを先に実行してください）');
  }

  if (!fs.existsSync(REPORTS_DIR)) {
    fs.mkdirSync(REPORTS_DIR, { recursive: true });
  }

  const markdown = generateMarkdown(data, weather, cal);
  const outPath = path.join(REPORTS_DIR, `${date}.md`);
  fs.writeFileSync(outPath, markdown, 'utf-8');

  console.log(`完了: ${outPath} に保存しました`);
})();
