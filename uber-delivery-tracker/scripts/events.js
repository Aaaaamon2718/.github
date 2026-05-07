#!/usr/bin/env node
/**
 * イベントデータ取得・統合スクリプト
 * - NPB 東京ドーム（巨人）・神宮球場（ヤクルト）試合スケジュールを自動取得
 * - 2026-seed.json のプリシードイベントとマージ
 * - data/events/YYYY.json に出力
 * 実行: node scripts/events.js [--year YYYY]
 */

const fs = require('fs');
const path = require('path');
const https = require('https');

const EVENTS_DIR = path.join(__dirname, '../data/events');

const NPB_TEAMS = [
  { name: '読売ジャイアンツ', short: '巨人', code: 'g', venue: '東京ドーム', area: '文京区', venueType: 'stadium' },
  { name: '東京ヤクルトスワローズ', short: 'ヤクルト', code: 's', venue: '明治神宮野球場', area: '新宿区', venueType: 'stadium' },
];

function getTargetYear(args) {
  const idx = args.indexOf('--year');
  if (idx === -1) return new Date().getFullYear();
  return parseInt(args[idx + 1]);
}

function fetchUrl(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ja,en;q=0.9',
      },
    }, (res) => {
      if (res.statusCode === 301 || res.statusCode === 302) {
        return fetchUrl(res.headers.location).then(resolve).catch(reject);
      }
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve({ status: res.statusCode, body: data }));
    });
    req.on('error', reject);
    req.setTimeout(10000, () => { req.destroy(); reject(new Error('Timeout')); });
  });
}

function parseNpbScheduleHtml(html, team, year) {
  const games = [];
  // npb.jp のスケジュールページをパース
  // <td class="day">4月3日(金)</td> のような構造を探す
  const datePattern = /(\d{1,2})月(\d{1,2})日[（(][月火水木金土日][）)]/g;
  const gameRowPattern = /<tr[^>]*class="[^"]*game[^"]*"[^>]*>([\s\S]*?)<\/tr>/gi;
  const homePattern = new RegExp(team.short, 'g');

  // より汎用的なアプローチ: 日付と対戦カードを探す
  const lines = html.split('\n');
  let currentDate = null;

  for (const line of lines) {
    // 日付パターンを探す
    const dateMatch = line.match(/(\d{1,2})月(\d{1,2})日/);
    if (dateMatch) {
      const month = String(dateMatch[1]).padStart(2, '0');
      const day = String(dateMatch[2]).padStart(2, '0');
      currentDate = `${year}-${month}-${day}`;
    }

    // ホームゲーム + 球場名 + 試合時間を探す
    if (currentDate && line.includes(team.venue)) {
      const timeMatch = line.match(/(\d{1,2}):(\d{2})/);
      const time = timeMatch ? `${String(timeMatch[1]).padStart(2, '0')}:${timeMatch[2]}` : '18:00';

      // 重複チェック
      if (!games.find(g => g.date === currentDate && g.name.includes(team.short))) {
        games.push({
          date: currentDate,
          name: `${team.short} ホームゲーム（${team.venue}）`,
          type: 'stadium',
          venue: team.venue,
          area: team.area,
          start_time: time,
          end_time: null,
          impact: 'medium',
          source: 'npb_auto',
          note: `${team.name} ホームゲーム。周辺エリア（${team.area}）は試合前後に混雑。`,
        });
      }
    }
  }
  return games;
}

async function fetchNpbSchedule(team, year) {
  const urls = [
    `https://npb.jp/games/${year}/schedule_${team.code}/`,
    `https://www.giants.jp/game/schedule/?year=${year}`,
  ];

  for (const url of urls) {
    try {
      console.log(`  NPB取得中: ${url}`);
      const { status, body } = await fetchUrl(url);
      if (status === 200 && body.length > 1000) {
        const games = parseNpbScheduleHtml(body, team, year);
        console.log(`  → ${team.short}: ${games.length}試合取得`);
        return games;
      }
    } catch (e) {
      console.warn(`  → ${url} 失敗: ${e.message}`);
    }
  }
  console.warn(`  ⚠️ ${team.short} スケジュール取得失敗（シードデータのみ使用）`);
  return [];
}

function loadSeedEvents(year) {
  const seedPath = path.join(EVENTS_DIR, `${year}-seed.json`);
  if (!fs.existsSync(seedPath)) {
    console.warn(`シードファイルなし: ${seedPath}`);
    return [];
  }
  const data = JSON.parse(fs.readFileSync(seedPath, 'utf-8'));
  return (data.events || []).map(e => ({ ...e, source: e.source || 'seed' }));
}

function mergeEvents(seedEvents, npbEvents) {
  const all = [...seedEvents];

  for (const npbGame of npbEvents) {
    // 同じ日付・会場の重複を避ける
    const dup = all.find(e => e.date === npbGame.date && e.venue === npbGame.venue);
    if (!dup) all.push(npbGame);
  }

  // 日付でソート
  all.sort((a, b) => a.date.localeCompare(b.date));
  return all;
}

function groupByDate(events) {
  const byDate = {};
  for (const e of events) {
    if (!byDate[e.date]) byDate[e.date] = [];
    byDate[e.date].push(e);
  }
  return byDate;
}

function printSummary(byDate, year) {
  console.log(`\n📅 ${year}年 イベントサマリー（登録件数上位）:`);
  const months = {};
  for (const [date, events] of Object.entries(byDate)) {
    const month = date.slice(0, 7);
    months[month] = (months[month] || 0) + events.length;
  }
  for (const [month, count] of Object.entries(months).sort()) {
    console.log(`  ${month}: ${count}件`);
  }

  console.log(`\n⚡ インパクト: critical / high のイベント:`);
  const important = Object.entries(byDate)
    .filter(([, evs]) => evs.some(e => e.impact === 'critical' || e.impact === 'high'))
    .slice(0, 15);
  for (const [date, evs] of important) {
    const top = evs.filter(e => e.impact === 'critical' || e.impact === 'high');
    console.log(`  ${date}: ${top.map(e => e.name).join(' / ')}`);
  }
}

(async () => {
  const args = process.argv.slice(2);
  const year = getTargetYear(args);

  console.log(`=== イベントデータ生成 (${year}年) ===`);

  if (!fs.existsSync(EVENTS_DIR)) {
    fs.mkdirSync(EVENTS_DIR, { recursive: true });
  }

  // 1. シードデータ読み込み
  const seedEvents = loadSeedEvents(year);
  console.log(`シードイベント: ${seedEvents.length}件`);

  // 2. NPB スケジュール取得
  let npbEvents = [];
  for (const team of NPB_TEAMS) {
    const games = await fetchNpbSchedule(team, year);
    npbEvents = npbEvents.concat(games);
    // サーバー負荷軽減
    await new Promise(r => setTimeout(r, 1000));
  }
  console.log(`NPB自動取得: ${npbEvents.length}試合`);

  // 3. マージ & 日付別インデックス作成
  const allEvents = mergeEvents(seedEvents, npbEvents);
  const byDate = groupByDate(allEvents);

  const output = {
    year,
    generatedAt: new Date().toISOString(),
    totalEvents: allEvents.length,
    npbGames: npbEvents.length,
    seedEvents: seedEvents.length,
    byDate,
  };

  const outPath = path.join(EVENTS_DIR, `${year}.json`);
  fs.writeFileSync(outPath, JSON.stringify(output, null, 2), 'utf-8');

  printSummary(byDate, year);
  console.log(`\n✅ 保存完了: ${outPath} (${allEvents.length}件)`);
})();
