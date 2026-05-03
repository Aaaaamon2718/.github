#!/usr/bin/env node
/**
 * weather.js - 天気データ取得スクリプト（1時間粒度版）
 *
 * 過去の日付 → OpenMeteo archive API（無料・APIキー不要）
 * 当日・未来 → OpenMeteo forecast API（無料・APIキー不要）
 *             .env に OPENWEATHER_API_KEY があればOpenWeatherも使用可
 *
 * 取得データ（1時間ごと × 24件）:
 *   気温・体感気温・降水量・降水確率・風速・湿度・天気コード
 *
 * 実行: node scripts/weather.js --date YYYY-MM-DD|today
 */

const fs   = require('fs');
const path = require('path');

try { require('dotenv').config({ path: path.join(__dirname, '../.env') }); } catch {}

const args = process.argv.slice(2);
const dateArg    = args[args.indexOf('--date') + 1] || 'today';
const targetDate = dateArg === 'today'
  ? new Date(Date.now() + 9*60*60*1000).toISOString().slice(0, 10)
  : dateArg;

const WEATHER_DIR = path.join(__dirname, '../data/weather');
const OUTPUT_PATH = path.join(WEATHER_DIR, `${targetDate}.json`);

const LAT = 35.6762;  // 東京
const LON = 139.6503;

// WMO 天気コード → 日本語
const WMO = {
  0:'快晴', 1:'晴れ', 2:'晴れ時々曇り', 3:'曇り',
  45:'霧', 48:'霧氷',
  51:'小雨', 53:'雨', 55:'強い雨',
  61:'弱い雨', 63:'雨', 65:'強い雨',
  71:'小雪', 73:'雪', 75:'大雪', 77:'雪粒',
  80:'にわか雨', 81:'にわか雨', 82:'激しいにわか雨',
  85:'にわか雪', 86:'激しいにわか雪',
  95:'雷雨', 96:'雷雨(ひょう)', 99:'激しい雷雨',
};
const wmoLabel    = c => WMO[c] || `コード${c}`;
const isRainyCode = c => c >= 51;

// ── 時間別データのパース（archive / forecast 共通） ──
function parseHourly(h, isArchive) {
  const codes = h.weathercode ?? h.weather_code ?? [];
  return h.time.map((t, i) => {
    const code   = codes[i] ?? 0;
    const precip = (h.precipitation?.[i]) ?? 0;
    // 過去データに降水確率はないため null
    const prob   = isArchive ? null : (h.precipitation_probability?.[i] ?? null);
    return {
      hour:                     parseInt(t.slice(11, 13)),
      time:                     t.slice(11, 16),           // "HH:MM"
      temperature:              round1(h.temperature_2m?.[i] ?? 0),
      apparentTemperature:      round1(h.apparent_temperature?.[i] ?? 0),
      precipitationProbability: prob,                      // % (forecast のみ)
      precipitation:            round1(precip),            // mm
      windspeed:                round1(h.windspeed_10m?.[i] ?? 0), // km/h
      humidity:                 h.relativehumidity_2m?.[i] ?? null, // %
      conditionCode:            code,
      condition:                wmoLabel(code),
      // 過去: 実測降水量で判定 / 予報: 天気コードで判定
      isRainy:                  isArchive ? precip >= 0.5 : isRainyCode(code),
    };
  });
}

const round1 = v => Math.round(v * 10) / 10;

// ── OpenMeteo Archive（過去データ・無料） ──
async function fetchArchive(date) {
  const hourlyVars = [
    'temperature_2m',
    'apparent_temperature',
    'precipitation',
    'windspeed_10m',
    'relativehumidity_2m',
    'weathercode',
  ].join(',');
  const dailyVars = 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max';

  const url = [
    'https://archive-api.open-meteo.com/v1/archive',
    `?latitude=${LAT}&longitude=${LON}`,
    `&start_date=${date}&end_date=${date}`,
    `&hourly=${hourlyVars}`,
    `&daily=${dailyVars}`,
    '&timezone=Asia%2FTokyo',
  ].join('');

  const res = await fetch(url);
  if (!res.ok) throw new Error(`OpenMeteo archive HTTP ${res.status}`);
  const data = await res.json();

  const d    = data.daily;
  const code = d.weather_code[0];
  return {
    date,
    location: '東京',
    source:   'openmeteo-archive',
    daily: {
      condition:     wmoLabel(code),
      conditionCode: code,
      isRainy:       isRainyCode(code),
      tempMax:       d.temperature_2m_max[0],
      tempMin:       d.temperature_2m_min[0],
      precipitation: d.precipitation_sum[0],
      windspeedMax:  d.windspeed_10m_max[0],
    },
    hourly: parseHourly(data.hourly, true),
  };
}

// ── OpenMeteo Forecast（当日・未来・無料） ──
async function fetchForecast(date) {
  const hourlyVars = [
    'temperature_2m',
    'apparent_temperature',
    'precipitation_probability',
    'precipitation',
    'windspeed_10m',
    'relativehumidity_2m',
    'weather_code',
  ].join(',');
  const dailyVars = 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max,precipitation_probability_max';

  const url = [
    'https://api.open-meteo.com/v1/forecast',
    `?latitude=${LAT}&longitude=${LON}`,
    `&hourly=${hourlyVars}`,
    `&daily=${dailyVars}`,
    '&timezone=Asia%2FTokyo',
    '&forecast_days=2',
  ].join('');

  const res = await fetch(url);
  if (!res.ok) throw new Error(`OpenMeteo forecast HTTP ${res.status}`);
  const data = await res.json();

  // 対象日の 24 件だけ抽出
  const indices = data.hourly.time
    .map((t, i) => t.startsWith(date) ? i : -1)
    .filter(i => i >= 0);

  const hourly = {};
  Object.keys(data.hourly).forEach(k => {
    hourly[k] = indices.map(i => data.hourly[k][i]);
  });

  const di   = data.daily.time.indexOf(date);
  const d    = data.daily;
  const code = d.weather_code[di] ?? d.weather_code[0];
  return {
    date,
    location: '東京',
    source:   'openmeteo-forecast',
    daily: {
      condition:              wmoLabel(code),
      conditionCode:          code,
      isRainy:                isRainyCode(code),
      tempMax:                d.temperature_2m_max[di],
      tempMin:                d.temperature_2m_min[di],
      precipitation:          d.precipitation_sum[di],
      windspeedMax:           d.windspeed_10m_max[di],
      precipitationProbMax:   d.precipitation_probability_max?.[di] ?? null,
    },
    hourly: parseHourly(hourly, false),
  };
}

// ── メイン ──
(async () => {
  console.log(`\n🌤️  天気データ取得（1時間粒度）: ${targetDate}`);
  if (!fs.existsSync(WEATHER_DIR)) fs.mkdirSync(WEATHER_DIR, { recursive: true });

  const today  = new Date(Date.now() + 9*60*60*1000).toISOString().slice(0, 10);
  const isPast = targetDate < today;

  try {
    const weather = isPast
      ? await fetchArchive(targetDate)
      : await fetchForecast(targetDate);

    fs.writeFileSync(OUTPUT_PATH, JSON.stringify(weather, null, 2), 'utf-8');

    const icon = weather.daily.isRainy ? '🌧️ ' : '☀️  ';
    console.log(`   ${icon}${weather.daily.condition}`);
    console.log(`   最高 ${weather.daily.tempMax}℃ / 最低 ${weather.daily.tempMin}℃ / 降水 ${weather.daily.precipitation}mm`);
    console.log(`   時間別データ: ${weather.hourly.length}件（0〜23時）`);

    // サンプル表示（稼働時間帯 10〜22時）
    console.log('   ┌─ 時間別サマリー（10〜22時）─────────────────┐');
    weather.hourly
      .filter(h => h.hour >= 10 && h.hour <= 22)
      .filter((_, i) => i % 3 === 0)  // 3時間ごとに表示
      .forEach(h => {
        const rainStr = h.precipitationProbability !== null
          ? `降水確率${h.precipitationProbability}%`
          : `降水${h.precipitation}mm`;
        const icon = h.isRainy ? '🌧' : '☀';
        console.log(`   │ ${h.time} ${icon} ${h.temperature}℃ 湿度${h.humidity}% ${rainStr}`);
      });
    console.log('   └───────────────────────────────────────────────┘');
    console.log(`   保存: ${OUTPUT_PATH}`);
  } catch (e) {
    console.error(`   ❌ 取得失敗: ${e.message}`);
    process.exit(1);
  }
})();
