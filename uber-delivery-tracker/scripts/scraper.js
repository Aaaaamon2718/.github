/**
 * scraper.js - Uber API直接呼び出し版（完全版）
 */
const { chromium } = require('playwright');
const fs   = require('fs');
const path = require('path');

const args       = process.argv.slice(2);
const dateArg    = args[args.indexOf('--date') + 1] || 'today';
const targetDate = dateArg === 'today'
  ? new Date(Date.now() + 9*60*60*1000).toISOString().slice(0,10)
  : dateArg;
const fromArg = args[args.indexOf('--from') + 1] || null;
const toArg   = args[args.indexOf('--to')   + 1] || null;

console.log(`\n🚀 scraper.js 起動（API直接版）`);
console.log(`   対象日 : ${targetDate}`);

const SESSION_PATH = path.join(__dirname, '../session/session.json');
const RAW_DIR      = path.join(__dirname, '../data/raw');
const OUTPUT_PATH  = path.join(RAW_DIR, `${targetDate}.json`);

if (!fs.existsSync(SESSION_PATH)) { console.error('❌ session.json なし'); process.exit(1); }
if (!fs.existsSync(RAW_DIR)) fs.mkdirSync(RAW_DIR, { recursive: true });

const wait = ms => new Promise(r => setTimeout(r, ms));

const parseDurationSec = (str) => {
  if (!str) return 0;
  const m = str.match(/(\d+)\s*分\s*(\d+)\s*秒/);
  if (m) return parseInt(m[1]) * 60 + parseInt(m[2]);
  return 0;
};
const formatDuration = (str) => {
  if (!str) return '不明';
  const m = str.match(/(\d+)\s*分\s*(\d+)\s*秒/);
  if (m) return `${m[1]}:${String(m[2]).padStart(2,'0')}`;
  return str;
};
const parseEarnings = (str) => {
  if (!str) return 0;
  const m = str.match(/[\d,]+/);
  return m ? parseInt(m[0].replace(',','')) : 0;
};
const parseDistance = (str) => {
  if (!str) return 0;
  const m = str.match(/([\d.]+)/);
  return m ? parseFloat(m[1]) : 0;
};
const unixToDatetime = (unix) => {
  const d = new Date((unix + 9*60*60) * 1000);
  const y  = d.getUTCFullYear();
  const mo = d.getUTCMonth() + 1;
  const da = d.getUTCDate();
  const h  = d.getUTCHours();
  const mi = String(d.getUTCMinutes()).padStart(2,'0');
  const ampm = h < 12 ? '午前' : '午後';
  const h12  = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${y}年${mo}月${da}日 ${ampm}${h12}時${mi}分`;
};
const unixToJstDate = (unix) => {
  const d = new Date((unix + 9*60*60) * 1000);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth()+1).padStart(2,'0')}-${String(d.getUTCDate()).padStart(2,'0')}`;
};

(async () => {
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-blink-features=AutomationControlled'],
  });
  const context = await browser.newContext({
    storageState: SESSION_PATH,
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    locale: 'ja-JP',
    timezoneId: 'Asia/Tokyo',
  });
  const page = await context.newPage();

  console.log('\n🔐 セッション確認中...');
  await page.goto('https://drivers.uber.com/p3/payments/activity-details', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await wait(2000);
  if (page.url().includes('auth') || page.url().includes('login')) {
    console.error('❌ セッション期限切れ'); await browser.close(); process.exit(1);
  }
  console.log('   ✅ セッション有効');

  // クエリ範囲の決定
  // --from/--to が渡されない場合は対象日当日のみ（+翌日2日バッファはdaily.sh側で付与）
  const d = new Date(targetDate + 'T00:00:00+09:00');
  const fmt = (dt) => dt.toISOString().slice(0, 10);
  const nextDay = new Date(d);
  nextDay.setDate(d.getDate() + 2);
  const startDate = fromArg || fmt(d);
  const endDate   = toArg   || fmt(nextDay);

  console.log(`\n📡 API呼び出し中... (${startDate} 〜 ${endDate})`);
  const allActivities = [];
  let cursor = null;
  let page_num = 1;

  while (true) {
    console.log(`   ページ ${page_num} 取得中...`);
    const result = await page.evaluate(async ({ startDate, endDate, cursor }) => {
      const body = {
        startDateIso: startDate,
        endDateIso:   endDate,
        paginationOption: cursor ? { cursor } : {},
      };
      const res = await fetch('https://drivers.uber.com/earnings/api/getWebActivityFeed?localeCode=ja-JP', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-csrf-token': 'x',
        },
        body: JSON.stringify(body),
      });
      return await res.json();
    }, { startDate, endDate, cursor });

    if (result.status !== 'success') {
      console.error('❌ APIエラー:', JSON.stringify(result));
      console.error('   → botブロックの場合は数分待ってから再実行してください');
      break;
    }
    const activities = result.data.activities || [];
    allActivities.push(...activities);
    console.log(`   → ${activities.length}件取得（累計: ${allActivities.length}件）`);
    if (!result.data.pagination.hasMoreData) break;
    cursor = result.data.pagination.nextCursor;
    page_num++;
    // bot検知回避: ページ間に1.5秒待機
    await wait(1500);
  }

  await browser.close();

  // 取得データの日付分布（JST）
  const dateCounts = {};
  allActivities.forEach(a => {
    const dateStr = unixToJstDate(a.recognizedAt);
    dateCounts[dateStr] = (dateCounts[dateStr] || 0) + 1;
  });
  console.log('\n📅 取得データの日付分布（JST）:');
  Object.entries(dateCounts).sort().forEach(([d, c]) => console.log(`  ${d}: ${c}件`));

  // 日付フィルター
  // dayStart: 対象日 00:00 JST
  // dayEnd: 翌日 06:00 JST（深夜〜早朝のrecognized処理を吸収）
  const dayStart = new Date(targetDate + 'T00:00:00+09:00').getTime() / 1000;
  const dayEnd   = dayStart + 30 * 3600; // +30時間 = 翌日06:00 JST
  const dayEndStrict = new Date(targetDate + 'T23:59:59+09:00').getTime() / 1000;

  const tripsAll = allActivities.filter(a =>
    a.activityTitle === 'Delivery' &&
    (a.type === 'TRIP' || a.type === 'CT') &&
    a.status === 'COMPLETED' &&
    a.recognizedAt >= dayStart &&
    a.recognizedAt <= dayEnd
  );

  const extendedTrips = tripsAll.filter(a => a.recognizedAt > dayEndStrict);
  if (extendedTrips.length > 0) {
    console.log(`\n⚠️  翌日早朝にrecognized処理された配達: ${extendedTrips.length}件`);
  }

  // フィルター外の近傍データ（デバッグ用）
  const nearBoundary = allActivities.filter(a =>
    a.activityTitle === 'Delivery' &&
    a.recognizedAt > dayEnd &&
    a.recognizedAt <= dayEnd + 18*3600
  );
  if (nearBoundary.length > 0) {
    console.log(`\n🔍 フィルター外の近傍配達（参考）: ${nearBoundary.length}件`);
    nearBoundary.slice(0, 3).forEach(a => {
      console.log(`   JST日付=${unixToJstDate(a.recognizedAt)} ¥${a.formattedTotal}`);
    });
  }

  console.log(`\n🔍 対象日フィルター結果: ${tripsAll.length}件（うち翌日認識分: ${extendedTrips.length}件）`);

  const trips = tripsAll.map((a, i) => {
    const meta = a.tripMetaData || {};
    return {
      no:          i + 1,
      earnings:    parseEarnings(a.formattedTotal),
      duration:    formatDuration(meta.formattedDuration),
      durationSec: parseDurationSec(meta.formattedDuration),
      distance:    parseDistance(meta.formattedDistance),
      datetime:    unixToDatetime(a.recognizedAt),
      recognizedDate: unixToJstDate(a.recognizedAt),
      storeName:   meta.pickupAddress  || '不明',
      destAddress: meta.dropOffAddress || '不明',
      tip:         0,
      uuid:        a.uuid,
    };
  });

  const output = {
    date:         targetDate,
    scrapedAt:    new Date().toISOString(),
    totalCount:   trips.length,
    successCount: trips.length,
    deliveries:   trips,
  };

  fs.writeFileSync(OUTPUT_PATH, JSON.stringify(output, null, 2), 'utf-8');

  const totalEarnings = trips.reduce((s, t) => s + t.earnings, 0);
  console.log(`\n✅ 完了`);
  console.log(`   配達件数 : ${trips.length}件`);
  console.log(`   配達売上 : ¥${totalEarnings.toLocaleString('ja-JP')}`);
  console.log(`   保存先   : ${OUTPUT_PATH}`);
})();
