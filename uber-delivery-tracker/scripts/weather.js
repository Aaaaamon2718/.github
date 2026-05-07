#!/usr/bin/env node
/**
 * 天気データ取得スクリプト
 * 過去日: OpenMeteo Archive API（無料・APIキー不要）
 * 当日/未来: OpenMeteo Forecast API（無料・APIキー不要）
 * 実行: node scripts/weather.js [--date YYYY-MM-DD|today]
 */

require('dotenv').config({ path: require('path').join(__dirname, '../.env') });

const fs = require('fs');
const path = require('path');
const https = require('https');

const WEATHER_DIR = path.join(__dirname, '../data/weather');
const LAT = 35.6762;
const LON = 139.6503;
const LOCATION_NAME = '東京都渋谷区';

const WMO_LABELS = {
  0: '快晴', 1: '晴れ', 2: '晴れ時々曇り', 3: '曇り',
  45: '霧', 48: '霧氷',
  51: '小雨', 53: '雨', 55: '強雨',
  61: '小雨', 63: '雨', 65: '大雨',
  71: '小雪', 73: '雪', 75: '大雪',
  77: '霰',
  80: 'にわか雨', 81: 'にわか雨', 82: '激しいにわか雨',
  85: 'にわか雪', 86: '大雪',
  95: '雷雨', 96: '雷雨(雹)', 99: '激しい雷雨(雹)',
};

function getLabel(code) {
  return WMO_LABELS[code] || `コード${code}`;
}

function isRainyCode(code) {
  return code >= 51;
}

function getTargetDate(args) {
  const idx = args.indexOf('--date');
  if (idx === -1) return new Date().toISOString().split('T')[0];
  const val = args[idx + 1];
  return val === 'today' ? new Date().toISOString().split('T')[0] : val;
}

function fetchUrl(url) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        if (res.statusCode !== 200) {
          reject(new Error(`HTTP ${res.statusCode}: ${url}`));
          return;
        }
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(new Error(`JSON parse error: ${e.message}`)); }
      });
    }).on('error', reject);
  });
}

function parseHourlyArchive(raw) {
  const times = raw.hourly.time;
  return times.map((t, i) => {
    const hour = parseInt(t.split('T')[1].split(':')[0]);
    const code = raw.hourly.weathercode[i];
    const precip = raw.hourly.precipitation[i] || 0;
    return {
      hour,
      time: t.replace('T', ' '),
      temperature: raw.hourly.temperature_2m[i],
      apparentTemperature: raw.hourly.apparent_temperature[i],
      precipitationProbability: null,
      precipitation: precip,
      windspeed: raw.hourly.windspeed_10m[i],
      humidity: raw.hourly.relativehumidity_2m[i],
      conditionCode: code,
      condition: getLabel(code),
      isRainy: precip >= 0.5,
    };
  });
}

function parseHourlyForecast(raw) {
  const times = raw.hourly.time;
  return times.map((t, i) => {
    const hour = parseInt(t.split('T')[1].split(':')[0]);
    const code = raw.hourly.weather_code[i];
    return {
      hour,
      time: t.replace('T', ' '),
      temperature: raw.hourly.temperature_2m[i],
      apparentTemperature: raw.hourly.apparent_temperature[i],
      precipitationProbability: raw.hourly.precipitation_probability[i],
      precipitation: raw.hourly.precipitation[i] || 0,
      windspeed: raw.hourly.windspeed_10m[i],
      humidity: raw.hourly.relativehumidity_2m[i],
      conditionCode: code,
      condition: getLabel(code),
      isRainy: isRainyCode(code),
    };
  });
}

async function fetchArchive(date) {
  const hourlyVars = [
    'temperature_2m', 'apparent_temperature', 'precipitation',
    'windspeed_10m', 'relativehumidity_2m', 'weathercode',
  ].join(',');
  const dailyVars = [
    'weather_code', 'temperature_2m_max', 'temperature_2m_min',
    'precipitation_sum', 'windspeed_10m_max',
  ].join(',');

  const url = `https://archive-api.open-meteo.com/v1/archive?latitude=${LAT}&longitude=${LON}` +
    `&start_date=${date}&end_date=${date}` +
    `&hourly=${hourlyVars}&daily=${dailyVars}&timezone=Asia%2FTokyo`;

  const raw = await fetchUrl(url);
  const daily = raw.daily;

  return {
    date,
    location: LOCATION_NAME,
    source: 'openmeteo-archive',
    daily: {
      conditionCode: daily.weather_code[0],
      condition: getLabel(daily.weather_code[0]),
      temperatureMax: daily.temperature_2m_max[0],
      temperatureMin: daily.temperature_2m_min[0],
      precipitationSum: daily.precipitation_sum[0],
      windspeedMax: daily.windspeed_10m_max[0],
    },
    hourly: parseHourlyArchive(raw),
  };
}

async function fetchForecast(date) {
  const hourlyVars = [
    'temperature_2m', 'apparent_temperature', 'precipitation_probability',
    'precipitation', 'windspeed_10m', 'relativehumidity_2m', 'weather_code',
  ].join(',');
  const dailyVars = [
    'weather_code', 'temperature_2m_max', 'temperature_2m_min',
    'precipitation_sum', 'windspeed_10m_max',
  ].join(',');

  const url = `https://api.open-meteo.com/v1/forecast?latitude=${LAT}&longitude=${LON}` +
    `&start_date=${date}&end_date=${date}` +
    `&hourly=${hourlyVars}&daily=${dailyVars}&timezone=Asia%2FTokyo`;

  const raw = await fetchUrl(url);
  const daily = raw.daily;

  return {
    date,
    location: LOCATION_NAME,
    source: 'openmeteo-forecast',
    daily: {
      conditionCode: daily.weather_code[0],
      condition: getLabel(daily.weather_code[0]),
      temperatureMax: daily.temperature_2m_max[0],
      temperatureMin: daily.temperature_2m_min[0],
      precipitationSum: daily.precipitation_sum[0],
      windspeedMax: daily.windspeed_10m_max[0],
    },
    hourly: parseHourlyForecast(raw),
  };
}

function isPastDate(dateStr) {
  const today = new Date().toISOString().split('T')[0];
  return dateStr < today;
}

function printTable(weatherData) {
  const { daily, hourly } = weatherData;
  console.log(`\n📍 ${weatherData.location} (${LAT}, ${LON})`);
  console.log(`📅 ${weatherData.date} [${weatherData.source}]`);
  console.log(`🌡️  気温: ${daily.temperatureMin}℃ 〜 ${daily.temperatureMax}℃`);
  console.log(`☔ 降水量: ${daily.precipitationSum}mm | 💨 風速: ${daily.windspeedMax}km/h`);
  console.log(`🌤️  天気: ${daily.condition}\n`);

  console.log('時間  | 天気             | 気温   | 降水量  | 降水確率');
  console.log('------|------------------|--------|---------|----------');
  const working = hourly.filter(h => h.hour >= 10 && h.hour <= 22);
  for (const h of working) {
    const time = String(h.hour).padStart(2, '0') + ':00';
    const cond = h.condition.padEnd(16);
    const temp = `${h.temperature}℃`.padEnd(7);
    const precip = `${h.precipitation}mm`.padEnd(8);
    const prob = h.precipitationProbability !== null
      ? `${h.precipitationProbability}%`
      : '— (過去)';
    const rain = h.isRainy ? ' 🌧' : '';
    console.log(`${time}  | ${cond} | ${temp} | ${precip} | ${prob}${rain}`);
  }
  console.log('');
}

(async () => {
  const args = process.argv.slice(2);
  const date = getTargetDate(args);

  console.log(`=== 天気データ取得 ===`);
  console.log(`対象日: ${date}`);

  if (!fs.existsSync(WEATHER_DIR)) {
    fs.mkdirSync(WEATHER_DIR, { recursive: true });
  }

  let weatherData;
  try {
    if (isPastDate(date)) {
      console.log('取得元: OpenMeteo Archive（過去データ）');
      weatherData = await fetchArchive(date);
    } else {
      console.log('取得元: OpenMeteo Forecast（当日/未来）');
      weatherData = await fetchForecast(date);
    }
  } catch (err) {
    console.error(`❌ 天気データ取得失敗: ${err.message}`);
    process.exit(1);
  }

  const outPath = path.join(WEATHER_DIR, `${date}.json`);
  fs.writeFileSync(outPath, JSON.stringify(weatherData, null, 2), 'utf-8');

  printTable(weatherData);
  console.log(`✅ 保存完了: ${outPath}`);
})();
