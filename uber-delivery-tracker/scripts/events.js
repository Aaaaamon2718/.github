#!/usr/bin/env node
/**
 * イベントデータ取得・統合スクリプト
 * - NPB 東京ドーム（巨人）・神宮球場（ヤクルト）試合を Playwright で自動取得
 * - 2026-seed.json のプリシードイベントとマージ
 * - data/events/YYYY.json に出力
 * 実行: node scripts/events.js [--year YYYY]
 */

const fs = require('fs');
const path = require('path');

const EVENTS_DIR = path.join(__dirname, '../data/events');

const NPB_TEAMS = [
  {
    name: '読売ジャイアンツ',
    short: '巨人',
    venue: '東京ドーム',
    area: '文京区',
    scheduleUrl: 'https://www.giants.jp/game/schedule/',
  },
  {
    name: '東京ヤクルトスワローズ',
    short: 'ヤクルト',
    venue: '明治神宮野球場',
    area: '新宿区',
    scheduleUrl: 'https://www.yakult-swallows.co.jp/games/schedule',
  },
];

function getTargetYear(args) {
  const idx = args.indexOf('--year');
  if (idx === -1) return new Date().getFullYear();
  return parseInt(args[idx + 1]);
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

async function scrapeNpbWithPlaywright(team, year) {
  let chromium, browser;
  try {
    ({ chromium } = require('playwright'));
  } catch (e) {
    console.warn('  Playwright が見つかりません。NPBスキップ。');
    return [];
  }

  const games = [];
  try {
    browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
    const page = await browser.newPage();

    // 月ごとに巡回（4月〜10月）
    for (let month = 4; month <= 10; month++) {
      const url = `${team.scheduleUrl}?year=${year}&month=${month}`;
      console.log(`  取得中: ${url}`);
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 });
      await page.waitForTimeout(1500);

      // ページテキストから試合日・会場を抽出
      const text = await page.content();

      // 「東京ドーム」または「神宮」が含まれる行を日付と一緒に探す
      const lines = text.split('\n');
      let lastDate = null;

      for (const line of lines) {
        // 日付パターン: 4月3日、4/3、2026-04-03 など
        const dateMatch = line.match(/(\d{1,2})月(\d{1,2})日/) ||
                          line.match(/(\d{1,2})\/(\d{1,2})/) ||
                          line.match(/\d{4}-(\d{2})-(\d{2})/);
        if (dateMatch) {
          const m = String(dateMatch[1]).padStart(2, '0');
          const d = String(dateMatch[2]).padStart(2, '0');
          lastDate = `${year}-${m}-${d}`;
        }

        if (lastDate && (line.includes(team.venue) || line.includes('主催') || line.includes('ホーム'))) {
          const timeMatch = line.match(/(\d{1,2}):(\d{2})/);
          const time = timeMatch
            ? `${String(timeMatch[1]).padStart(2, '0')}:${timeMatch[2]}`
            : '18:00';

          if (!games.find(g => g.date === lastDate)) {
            games.push({
              date: lastDate,
              name: `${team.short} ホームゲーム（${team.venue}）`,
              type: 'stadium',
              venue: team.venue,
              area: team.area,
              start_time: time,
              impact: 'medium',
              source: 'npb_auto',
              note: `${team.name} ホームゲーム。周辺（${team.area}）は試合前後に混雑。`,
            });
          }
        }
      }
    }
  } catch (e) {
    console.warn(`  ⚠️ ${team.short} スクレイピングエラー: ${e.message}`);
  } finally {
    if (browser) await browser.close();
  }

  console.log(`  → ${team.short}: ${games.length}試合取得`);
  return games;
}

function mergeEvents(seedEvents, npbEvents) {
  const all = [...seedEvents];
  for (const npbGame of npbEvents) {
    const dup = all.find(e => e.date === npbGame.date && e.venue === npbGame.venue);
    if (!dup) all.push(npbGame);
  }
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

function printSummary(byDate, year, npbCount) {
  const totalDates = Object.keys(byDate).length;
  console.log(`\n📅 ${year}年: ${totalDates}日にイベントあり（NPB ${npbCount}試合含む）`);

  console.log('\n⚡ critical / high イベント（先頭15件）:');
  const important = Object.entries(byDate)
    .filter(([, evs]) => evs.some(e => ['critical', 'high'].includes(e.impact)))
    .slice(0, 15);
  for (const [date, evs] of important) {
    const top = evs.filter(e => ['critical', 'high'].includes(e.impact));
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

  const seedEvents = loadSeedEvents(year);
  console.log(`シードイベント: ${seedEvents.length}件`);

  let npbEvents = [];
  for (const team of NPB_TEAMS) {
    const games = await scrapeNpbWithPlaywright(team, year);
    npbEvents = npbEvents.concat(games);
  }
  console.log(`NPB自動取得: ${npbEvents.length}試合`);

  if (npbEvents.length === 0) {
    console.log('⚠️  NPB取得0件。シードデータのみで続行します。');
    console.log('   → data/events/2026-seed.json に手動追加も可能です。');
  }

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

  printSummary(byDate, year, npbEvents.length);
  console.log(`\n✅ 保存完了: ${outPath} (${allEvents.length}件)`);
})();
