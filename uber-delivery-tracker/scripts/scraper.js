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
  const y = d.getUTCFullYear();
  const mo = d.getUTCMonth() + 1;
  const da = d.getUTCDate();
  const h = d.getUTCHours();
  const mi = String(d.getUTCMinutes()).padStart(2,'0');
  const ampm = h < 12 ? '午前' : '午後';
  const h12 = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${y}年${mo}月${da}日 ${ampm}${h12}時${mi}分`;
};
(async () => {
  // Playwrightでブラウザを起動してCookieを取得
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    storageState: SESSION_PATH,
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    locale: 'ja-JP',
    timezoneId: 'Asia/Tokyo',
  });
  const page = await context.newPage();
  // セッション確認
  console.log('\n🔐 セッション確認中...');
  await page.goto('https://drivers.uber.com/p3/payments/activity-details', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await wait(2000);
  if (page.url().includes('auth') || page.url().includes('login')) {
    console.error('❌ セッション期限切れ'); await browser.close(); process.exit(1);
  }
  console.log('   ✅ セッション有効');
  // APIをブラウザコンテキスト内から呼び出す（Cookie自動付与）
  console.log('\n📡 API呼び出し中...');
  const allActivities = [];
  let cursor = null;
  let page_num = 1;
  while (true) {
    console.log(`   ページ ${page_num} 取得中...`);
    const result = await page.evaluate(async ({ targetDate, cursor, fromDate, toDate }) => {
      // Uberは週単位でデータを返すため、対象日を含む週（月曜〜日曜）を指定
      const d = new Date(targetDate + 'T00:00:00+09:00');
      const dow = d.getDay(); // 0=日, 1=月...
      const monday = new Date(d);
      monday.setDate(d.getDate() - (dow === 0 ? 6 : dow - 1));
      const sunday = new Date(monday);
      sunday.setDate(monday.getDate() + 6);
      const fmt = (dt) => dt.toISOString().slice(0,10);
      const body = {
        startDateIso: fromDate,
        endDateIso:   toDate,
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
    }, { targetDate, cursor, fromDate: fromArg || targetDate, toDate: toArg || targetDate });
    if (result.status !== 'success') {
      console.error('❌ APIエラー:', JSON.stringify(result));
      break;
    }
    const activities = result.data.activities || [];
    allActivities.push(...activities);
    console.log(`   → ${activities.length}件取得（累計: ${allActivities.length}件）`);
    if (!result.data.pagination.hasMoreData) break;
    cursor = result.data.pagination.nextCursor;
    page_num++;
    await wait(500);
  }
  await browser.close();
  const dayStart = new Date(targetDate + 'T00:00:00+09:00').getTime() / 1000;
  const dayEnd   = new Date(targetDate + 'T23:59:59+09:00').getTime() / 1000;
  const trips = allActivities
    .filter(a =>
      a.activityTitle === 'Delivery' &&
      (a.type === 'TRIP' || a.type === 'CT') &&
      a.status === 'COMPLETED' &&
      a.recognizedAt >= dayStart &&
      a.recognizedAt <= dayEnd
    )
    .map((a, i) => {
      const meta = a.tripMetaData || {};
      return {
        no:          i + 1,
        earnings:    parseEarnings(a.formattedTotal),
        duration:    formatDuration(meta.formattedDuration),
        durationSec: parseDurationSec(meta.formattedDuration),
        distance:    parseDistance(meta.formattedDistance),
        datetime:    unixToDatetime(a.recognizedAt),
        storeName:   meta.pickupAddress  || '不明',
        destAddress: (() => {
          const addr = meta.dropOffAddress || '不明';
          // 英語住所を日本語に変換（例: "3-chōme Tokyo Minato Takanawa" → そのまま保持、区名だけ抽出）
          if (addr.includes('Tokyo')) {
            const m = addr.match(/Tokyo\s+(\w+)\s+City\s+(\w+)/i) ||
                      addr.match(/Tokyo\s+(\w+)\s+(\w+)/i);
            return addr; // 一旦そのまま保持
          }
          return addr;
        })(),
        tip:         0,
        uuid:        a.uuid,
      };
    });
  const result = {
    date:         targetDate,
    scrapedAt:    new Date().toISOString(),
    totalCount:   trips.length,
    successCount: trips.length,
    deliveries:   trips,
  };
  // デバッグ：4/23のDelivery全件をログ出力
  const allDeliveries = allActivities.filter(a => 
    a.activityTitle === 'Delivery' &&
    a.recognizedAt >= dayStart && 
    a.recognizedAt <= dayEnd
  );
  console.log(`\n🔍 デバッグ: 対象日のDelivery全件 = ${allDeliveries.length}件`);
  allDeliveries.forEach(a => {
    const t = new Date((a.recognizedAt + 9*60*60)*1000);
    console.log(`  ${t.getUTCHours()}:${String(t.getUTCMinutes()).padStart(2,'0')} ¥${a.formattedTotal} type=${a.type} status=${a.status}`);
  });
  fs.writeFileSync(OUTPUT_PATH, JSON.stringify(result, null, 2), 'utf-8');
  const totalEarnings = trips.reduce((s, t) => s + t.earnings, 0);
  console.log(`\n✅ 完了`);
  console.log(`   配達件数 : ${trips.length}件`);
  console.log(`   配達売上 : ¥${totalEarnings.toLocaleString('ja-JP')}`);
  console.log(`   保存先   : ${OUTPUT_PATH}`);
})();
