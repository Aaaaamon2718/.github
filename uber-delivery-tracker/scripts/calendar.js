#!/usr/bin/env node
/**
 * 祝日・給料日カレンダー取得・計算スクリプト
 * データソース: holidays-jp.github.io（無料・APIキー不要）
 * 実行: node scripts/calendar.js [--year YYYY]
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

const CALENDAR_DIR = path.join(__dirname, '../data/calendar');
const HOLIDAYS_CACHE = path.join(CALENDAR_DIR, 'holidays.json');

// 給料日設定（日本の一般的な給与支払日）
const PAYDAY_DAYS = [25]; // 毎月25日（月末は動的計算で追加）
const INCLUDE_MONTH_END = true; // 月末給料日も含める

function fetchUrl(url) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        if (res.statusCode !== 200) {
          reject(new Error(`HTTP ${res.statusCode}`));
          return;
        }
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(new Error(`JSON parse error: ${e.message}`)); }
      });
    }).on('error', reject);
  });
}

async function fetchHolidays() {
  console.log('祝日データを取得中... (holidays-jp.github.io)');
  const data = await fetchUrl('https://holidays-jp.github.io/api/v1/date.json');
  return data; // { "YYYY-MM-DD": "祝日名", ... }
}

function isWeekend(dateStr) {
  const d = new Date(dateStr + 'T12:00:00+09:00');
  const day = d.getDay();
  return day === 0 || day === 6; // 0=日, 6=土
}

function getDayOfWeek(dateStr) {
  const d = new Date(dateStr + 'T12:00:00+09:00');
  return ['日', '月', '火', '水', '木', '金', '土'][d.getDay()];
}

function addDays(dateStr, n) {
  const d = new Date(dateStr + 'T12:00:00+09:00');
  d.setDate(d.getDate() + n);
  return d.toISOString().split('T')[0];
}

function getMonthEnd(year, month) {
  // month is 1-based
  const lastDay = new Date(year, month, 0).getDate();
  return `${year}-${String(month).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`;
}

// 土日祝の場合、直前の平日にシフト
function shiftToPrevBusinessDay(dateStr, holidays) {
  let d = dateStr;
  while (isWeekend(d) || holidays[d]) {
    d = addDays(d, -1);
  }
  return d;
}

function calcPaydays(year, holidays) {
  const paydays = {};

  for (let month = 1; month <= 12; month++) {
    const pad = String(month).padStart(2, '0');

    // 25日給料日
    for (const day of PAYDAY_DAYS) {
      const raw = `${year}-${pad}-${String(day).padStart(2, '0')}`;
      const actual = shiftToPrevBusinessDay(raw, holidays);
      if (!paydays[actual]) paydays[actual] = [];
      paydays[actual].push(actual === raw ? `給料日(${day}日)` : `給料日(${day}日振替)`);
    }

    // 月末給料日
    if (INCLUDE_MONTH_END) {
      const raw = getMonthEnd(year, month);
      const actual = shiftToPrevBusinessDay(raw, holidays);
      if (!paydays[actual]) paydays[actual] = [];
      const lastDay = parseInt(raw.split('-')[2]);
      paydays[actual].push(actual === raw ? `給料日(月末${lastDay}日)` : `給料日(月末振替)`);
    }
  }

  return paydays;
}

function buildDayInfo(dateStr, holidays, paydays) {
  const dow = getDayOfWeek(dateStr);
  const weekend = isWeekend(dateStr);
  const holiday = holidays[dateStr] || null;
  const paydayLabels = paydays[dateStr] || [];

  const types = [];
  if (holiday) types.push('祝日');
  else if (weekend) types.push(dow === '土' ? '土曜' : '日曜');
  else types.push('平日');
  if (paydayLabels.length > 0) types.push(...paydayLabels);

  // 連休判定（前後3日以内に祝日・週末が続くか）
  let consecutive = 0;
  for (let i = -3; i <= 3; i++) {
    if (i === 0) continue;
    const adj = addDays(dateStr, i);
    if (isWeekend(adj) || holidays[adj]) consecutive++;
  }

  return {
    date: dateStr,
    dayOfWeek: dow,
    isWeekend: weekend,
    holiday,
    paydays: paydayLabels,
    types,
    isLongWeekend: consecutive >= 2,
  };
}

function getTargetYear(args) {
  const idx = args.indexOf('--year');
  if (idx === -1) return new Date().getFullYear();
  return parseInt(args[idx + 1]);
}

(async () => {
  const args = process.argv.slice(2);
  const year = getTargetYear(args);

  console.log(`=== カレンダーデータ生成 (${year}年) ===`);

  if (!fs.existsSync(CALENDAR_DIR)) {
    fs.mkdirSync(CALENDAR_DIR, { recursive: true });
  }

  let holidays;
  try {
    holidays = await fetchHolidays();
    console.log(`祝日取得完了: ${Object.keys(holidays).length}件`);
  } catch (err) {
    // キャッシュがあれば使用
    if (fs.existsSync(HOLIDAYS_CACHE)) {
      console.warn(`⚠️ APIエラー、キャッシュを使用: ${err.message}`);
      const cached = JSON.parse(fs.readFileSync(HOLIDAYS_CACHE, 'utf-8'));
      holidays = cached.holidays;
    } else {
      console.error(`❌ 祝日データ取得失敗: ${err.message}`);
      process.exit(1);
    }
  }

  const paydays = calcPaydays(year, holidays);

  // 対象年の全日を生成
  const days = {};
  const start = new Date(`${year}-01-01T12:00:00+09:00`);
  const end = new Date(`${year}-12-31T12:00:00+09:00`);
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    const dateStr = d.toISOString().split('T')[0];
    days[dateStr] = buildDayInfo(dateStr, holidays, paydays);
  }

  const output = {
    year,
    updatedAt: new Date().toISOString(),
    holidays,
    paydays,
    days,
  };

  const outPath = path.join(CALENDAR_DIR, `${year}.json`);
  fs.writeFileSync(outPath, JSON.stringify(output, null, 2), 'utf-8');
  fs.writeFileSync(HOLIDAYS_CACHE, JSON.stringify({ holidays, updatedAt: new Date().toISOString() }, null, 2), 'utf-8');

  console.log(`\n✅ 保存完了: ${outPath}`);

  // サマリー表示
  const yearHolidays = Object.entries(holidays).filter(([d]) => d.startsWith(String(year)));
  console.log(`\n${year}年の祝日一覧:`);
  for (const [d, name] of yearHolidays) {
    const dow = getDayOfWeek(d);
    const pd = paydays[d] ? ` ＋${paydays[d].join('/')}` : '';
    console.log(`  ${d}（${dow}）${name}${pd}`);
  }

  console.log(`\n給料日（振替含む）:`);
  for (const [d, labels] of Object.entries(paydays).sort()) {
    if (!d.startsWith(String(year))) continue;
    const dow = getDayOfWeek(d);
    const hol = holidays[d] ? `（${holidays[d]}）` : '';
    console.log(`  ${d}（${dow}）${hol} ${labels.join(' / ')}`);
  }
})();
