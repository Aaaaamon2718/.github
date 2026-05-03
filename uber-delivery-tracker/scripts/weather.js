#!/usr/bin/env node
/**
 * weather.js - 天気データ取得スクリプト
 *
 * 過去の日付 → OpenMeteo（無料・APIキー不要）
 * 当日・未来 → OpenWeather API（.envに OPENWEATHER_API_KEY を設定）
 *
 * 実行: node scripts/weather.js --date YYYY-MM-DD|today
 */

const fs   = require('fs');
const path = require('path');

// .envからAPIキーを読み込む（ファイルがなくても落ちない）
try {
  require('dotenv').config({ path: path.join(__dirname, '../.env') });
} catch {}

const args = process.argv.slice(2);
const dateArg    = args[args.indexOf('--date') + 1] || 'today';
const targetDate = dateArg === 'today'
  ? new Date(Date.now() + 9*60*60*1000).toISOString().slice(0, 10)
  : dateArg;

const WEATHER_DIR = path.join(__dirname, '../data/weather');
const OUTPUT_PATH = path.join(WEATHER_DIR, `${targetDate}.json`);

// 東京の座標
const LAT = 35.6762;
const LON = 139.6503;

// WMO天気コード → 日本語
const WMO_LABELS = {
  0: '快晴', 1: '晴れ', 2: '晴れ時々曇り', 3: '曇り',
  45: '霧', 48: '霧氷',
  51: '小雨', 53: '雨', 55: '強い雨',
  61: '弱い雨', 63: '雨', 65: '強い雨',
  71: '小雪', 73: '雪', 75: '大雪', 77: '雪粒',
  80: 'にわか雨', 81: 'にわか雨', 82: '激しいにわか雨',
  85: 'にわか雪', 86: '激しいにわか雪',
  95: '雷雨', 96: '雷雨（ひょう）', 99: '激しい雷雨',
};

const wmoLabel   = (code) => WMO_LABELS[code] || `天候コード${code}`;
const isRainyCode = (code) => code >= 51;

// ── OpenMeteo（過去データ・無料） ──
async function fetchOpenMeteo(date) {
  const url = [
    'https://archive-api.open-meteo.com/v1/archive',
    `?latitude=${LAT}&longitude=${LON}`,
    `&start_date=${date}&end_date=${date}`,
    '&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max',
    '&timezone=Asia%2FTokyo',
  ].join('');

  const res = await fetch(url);
  if (!res.ok) throw new Error(`OpenMeteo HTTP ${res.status}`);
  const data = await res.json();
  if (!data.daily) throw new Error('OpenMeteo: dailyフィールドなし');

  const code = data.daily.weather_code[0];
  return {
    date,
    location:      '東京',
    source:        'openmeteo',
    condition:     wmoLabel(code),
    conditionCode: code,
    isRainy:       isRainyCode(code),
    tempMax:       data.daily.temperature_2m_max[0],
    tempMin:       data.daily.temperature_2m_min[0],
    precipitation: data.daily.precipitation_sum[0],
    windspeedMax:  data.daily.windspeed_10m_max[0],
    humidity:      null,
  };
}

// ── OpenWeather API（当日・予報） ──
async function fetchOpenWeather(date) {
  const apiKey = process.env.OPENWEATHER_API_KEY;
  if (!apiKey) throw new Error('OPENWEATHER_API_KEY が .env に未設定');

  const url = [
    'https://api.openweathermap.org/data/2.5/weather',
    `?lat=${LAT}&lon=${LON}`,
    `&appid=${apiKey}&units=metric&lang=ja`,
  ].join('');

  const res = await fetch(url);
  if (!res.ok) throw new Error(`OpenWeather HTTP ${res.status}`);
  const data = await res.json();

  const main = data.weather[0];
  return {
    date,
    location:      '東京',
    source:        'openweather',
    condition:     main.description,
    conditionCode: main.id,
    isRainy:       main.id >= 300 && main.id < 700,
    tempMax:       data.main.temp_max,
    tempMin:       data.main.temp_min,
    precipitation: (data.rain && data.rain['1h']) || 0,
    windspeedMax:  parseFloat((data.wind.speed * 3.6).toFixed(1)), // m/s → km/h
    humidity:      data.main.humidity,
  };
}

(async () => {
  console.log(`\n🌤️  天気データ取得: ${targetDate}`);

  if (!fs.existsSync(WEATHER_DIR)) {
    fs.mkdirSync(WEATHER_DIR, { recursive: true });
  }

  // 今日より2日以上前 → 過去データとしてOpenMeteoを使用
  const today  = new Date(Date.now() + 9*60*60*1000).toISOString().slice(0, 10);
  const isPast = targetDate < today;

  try {
    let weather;
    if (isPast) {
      console.log('   → OpenMeteo（過去データ・無料）を使用');
      weather = await fetchOpenMeteo(targetDate);
    } else {
      console.log('   → OpenWeather API（当日）を使用');
      weather = await fetchOpenWeather(targetDate);
    }

    fs.writeFileSync(OUTPUT_PATH, JSON.stringify(weather, null, 2), 'utf-8');

    const icon = weather.isRainy ? '🌧️ ' : '☀️  ';
    console.log(`   ${icon}${weather.condition}`);
    console.log(`   最高 ${weather.tempMax}℃ / 最低 ${weather.tempMin}℃ / 降水 ${weather.precipitation}mm / 最大風速 ${weather.windspeedMax} km/h`);
    console.log(`   保存: ${OUTPUT_PATH}`);
  } catch (e) {
    console.error(`   ❌ 取得失敗: ${e.message}`);
    process.exit(1);
  }
})();
