/**
 * scraper.js - 実践版
 *
 * 【使い方】
 *
 * Step A: HTML構造確認モード（初回必須）
 *   node scripts/scraper.js --debug --date 2026-04-21
 *   → data/debug/ にHTMLダンプを出力。セレクタ確認用。
 *
 * Step B: 本番スクレイピング
 *   node scripts/scraper.js --date today
 *   node scripts/scraper.js --date 2026-04-21
 *   → data/raw/YYYY-MM-DD.json に保存
 */

const { chromium } = require('playwright');
const fs   = require('fs');
const path = require('path');

// ================================================================
// 引数処理
// ================================================================
const args      = process.argv.slice(2);
const DEBUG     = args.includes('--debug');
const dateArg   = args[args.indexOf('--date') + 1] || 'today';
const targetDate = dateArg === 'today'
  ? new Date(Date.now() + 9 * 60 * 60 * 1000).toISOString().slice(0, 10)
  : dateArg;

console.log(`\n🚀 scraper.js 起動`);
console.log(`   対象日  : ${targetDate}`);
console.log(`   モード  : ${DEBUG ? 'DEBUGモード（HTMLダンプ）' : '本番スクレイピング'}`);

// ================================================================
// パス設定
// ================================================================
const SESSION_PATH = path.join(__dirname, '../session/session.json');
const RAW_DIR      = path.join(__dirname, '../data/raw');
const DEBUG_DIR    = path.join(__dirname, '../data/debug');
const OUTPUT_PATH  = path.join(RAW_DIR, `${targetDate}.json`);

if (!fs.existsSync(SESSION_PATH)) {
  console.error('\n❌ session/session.json が見つかりません。');
  console.error('   先に: node scripts/auth/save-session.js を実行してください。');
  process.exit(1);
}
if (!fs.existsSync(RAW_DIR))   fs.mkdirSync(RAW_DIR,   { recursive: true });
if (!fs.existsSync(DEBUG_DIR)) fs.mkdirSync(DEBUG_DIR, { recursive: true });

// ================================================================
// ユーティリティ
// ================================================================

// 人間らしいウェイト（bot検知対策）
const wait = (ms) => new Promise(r => setTimeout(r, ms));
const humanWait = () => wait(800 + Math.random() * 700); // 0.8〜1.5秒

// HTMLから各フィールドを抽出
const extractFromHTML = (html, url) => {
  // ------ 売上金額 ------
  // パターン: ¥840 や ¥1,484 など
  const earningsMatch = html.match(/¥([\d,]+)(?=\s*<\/h[12]|\s*この)/);
  const earnings = earningsMatch
    ? parseInt(earningsMatch[1].replace(',', ''))
    : (() => {
        // フォールバック: 最初に出てくる大きい金額
        const all = [...html.matchAll(/¥([\d,]+)/g)].map(m => parseInt(m[1].replace(',', '')));
        return all.filter(n => n >= 100).sort((a, b) => b - a)[0] || 0;
      })();

  // ------ 時間 ------
  // パターン1: "27 分 34 秒" or "27分34秒"
  // パターン2: "27:34"
  let durationSec = 0;
  let durationFormatted = '不明';
  const durMatch1 = html.match(/(\d+)\s*分\s*(\d+)\s*秒/);
  const durMatch2 = html.match(/>(\d+):(\d+)</);
  if (durMatch1) {
    const m = parseInt(durMatch1[1]), s = parseInt(durMatch1[2]);
    durationSec = m * 60 + s;
    durationFormatted = `${m}:${String(s).padStart(2, '0')}`;
  } else if (durMatch2) {
    const m = parseInt(durMatch2[1]), s = parseInt(durMatch2[2]);
    durationSec = m * 60 + s;
    durationFormatted = `${m}:${String(s).padStart(2, '0')}`;
  }

  // ------ 距離 ------
  const distMatch = html.match(/([\d.]+)\s*km/);
  const distance = distMatch ? parseFloat(distMatch[1]) : 0;

  // ------ 日時 ------
  // パターン: "Delivery・2026年4月22日・午後7時16分"
  const dtMatch = html.match(/(\d{4}年\d{1,2}月\d{1,2}日)[・\s]*(午前|午後)\s*(\d+)時(\d+)分/);
  const datetime = dtMatch
    ? `${dtMatch[1]} ${dtMatch[2]}${dtMatch[3]}時${dtMatch[4]}分`
    : null;

  // ------ 店舗名 ------
  // Uberの詳細画面: ルートの「出発点」が店舗名
  // パターン候補を複数試す
  let storeName = '不明';
  const storePatterns = [
    /class="[^"]*origin[^"]*"[^>]*>\s*<[^>]+>\s*([^<]{3,50})\s*</i,
    /class="[^"]*pickup[^"]*"[^>]*>\s*<[^>]+>\s*([^<]{3,50})\s*</i,
    /"storeName":"([^"]+)"/,
    /"name":"([^"]+)"/,
    // テキストベースのフォールバック
    /(?:ピックアップ|pickup|配達元)[^\n]*\n\s*([^\n<]{3,50})/i,
  ];
  for (const pat of storePatterns) {
    const m = html.match(pat);
    if (m && m[1] && m[1].trim().length > 2) {
      storeName = m[1].trim();
      break;
    }
  }

  // ------ 配達先住所 ------
  let destAddress = '不明';
  const destPatterns = [
    /class="[^"]*destination[^"]*"[^>]*>\s*<[^>]+>\s*([^<]{5,80})\s*</i,
    /class="[^"]*dropoff[^"]*"[^>]*>\s*<[^>]+>\s*([^<]{5,80})\s*</i,
    /"dropoffAddress":"([^"]+)"/,
    /東京都([^<\n]{3,30}(?:区|市))[^<\n]{0,30}/,
  ];
  for (const pat of destPatterns) {
    const m = html.match(pat);
    if (m && m[1] && m[1].trim().length > 2) {
      destAddress = m[1].trim();
      break;
    }
  }

  // ------ チップ ------
  const tipMatch = html.match(/(?:チップ|Tip)[^\d¥]*¥?([\d,]+)/) ||
                   html.match(/"tip[aA]mount":\s*([\d.]+)/);
  const tip = tipMatch ? parseInt(tipMatch[1].replace(',', '')) : 0;

  return { earnings, durationSec, durationFormatted, distance, datetime, storeName, destAddress, tip };
};

// ================================================================
// メイン処理
// ================================================================
(async () => {
  const browser = await chromium.launch({
    headless: !DEBUG, // デバッグ時はブラウザ表示
    args: ['--no-sandbox', '--disable-blink-features=AutomationControlled'],
  });

  const context = await browser.newContext({
    storageState: SESSION_PATH,
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    locale: 'ja-JP',
    timezoneId: 'Asia/Tokyo',
    viewport: { width: 1280, height: 800 },
  });

  // bot検知回避: webdriver フラグを消す
  await context.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => false });
  });

  const page = await context.newPage();

  // ---- セッション有効確認 ----
  console.log('\n🔐 セッション確認中...');
  await page.goto('https://drivers.uber.com/p3/payments/activity-details', {
    waitUntil: 'domcontentloaded',
    timeout: 30000,
  });
  await wait(2000);

  if (page.url().includes('auth.uber.com') || page.url().includes('login')) {
    console.error('❌ セッション期限切れ。node scripts/auth/save-session.js を再実行してください。');
    await browser.close();
    process.exit(1);
  }
  console.log('   ✅ セッション有効');

  // ---- 対象日のURLに移動 ----
  // Uberは週単位表示なので、対象日を含む週を表示
  const url = `https://drivers.uber.com/p3/payments/activity-details?from=${targetDate}&to=${targetDate}`;
  console.log(`\n📄 アクティビティページに移動: ${url}`);
  await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
  await wait(2000);

  // ---- DEBUGモード: ページHTMLをダンプして終了 ----
  if (DEBUG) {
    const listHTML = await page.content();
    const dumpPath = path.join(DEBUG_DIR, `list_${targetDate}.html`);
    fs.writeFileSync(dumpPath, listHTML, 'utf-8');
    console.log(`\n🔍 DEBUG: 一覧ページHTMLを保存しました`);
    console.log(`   ${dumpPath}`);
    console.log(`\n   ブラウザを確認してください。`);
    console.log(`   確認後、Ctrl+C で終了 or Enterで続行...\n`);
    await new Promise(r => process.stdin.once('data', r));
    await browser.close();
    return;
  }

  // ---- View Detailsボタンを全件収集 ----
  // まずページをスクロールして全件ロード
  console.log('\n📋 全件ロード中（スクロール）...');
  let prevCount = 0;
  for (let i = 0; i < 20; i++) {
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await wait(1000);
    const count = await page.locator('button:has-text("View Details"), a:has-text("View Details")').count();
    if (count === prevCount && count > 0) break;
    prevCount = count;
  }
  await page.evaluate(() => window.scrollTo(0, 0));

  const totalButtons = await page.locator('button:has-text("View Details"), a:has-text("View Details")').count();
  console.log(`📦 View Detailsボタン数: ${totalButtons}件`);

  if (totalButtons === 0) {
    console.warn('⚠️  View Detailsボタンが見つかりません。');
    console.warn('   --debug オプションでHTMLを確認してください。');
    await browser.close();
    process.exit(1);
  }

  // ---- 各配達の詳細を取得 ----
  const deliveries = [];

  for (let i = 0; i < totalButtons; i++) {
    console.log(`  [${i + 1}/${totalButtons}] 取得中...`);

    try {
      // ボタンを毎回再取得（DOM更新対策）
      const buttons = await page.locator('button:has-text("View Details"), a:has-text("View Details")').all();
      if (i >= buttons.length) {
        console.warn(`  ⚠️  ボタンが${i}番目で見つかりません（合計${buttons.length}件）`);
        break;
      }

      await buttons[i].scrollIntoViewIfNeeded();
      await humanWait();
      await buttons[i].click();
      await wait(1500);

      // 詳細パネルのHTMLを取得
      // → まず詳細専用コンテナを探し、なければページ全体を使う
      let detailHTML = '';
      const detailSelectors = [
        '[data-testid="trip-detail"]',
        '[class*="TripDetail"]',
        '[class*="trip-detail"]',
        '[class*="ActivityDetail"]',
        '[class*="activityDetail"]',
        'aside',
        '[role="dialog"]',
      ];
      for (const sel of detailSelectors) {
        const el = page.locator(sel).first();
        if (await el.count() > 0) {
          detailHTML = await el.innerHTML().catch(() => '');
          if (detailHTML.length > 100) break;
        }
      }
      // フォールバック: ページ全体
      if (detailHTML.length < 100) {
        detailHTML = await page.content();
      }

      // DEBUGダンプ（最初の3件のみ）
      if (i < 3) {
        const dumpPath = path.join(DEBUG_DIR, `detail_${targetDate}_${i + 1}.html`);
        fs.writeFileSync(dumpPath, detailHTML, 'utf-8');
      }

      const extracted = extractFromHTML(detailHTML, page.url());
      deliveries.push({ no: i + 1, ...extracted });

      console.log(`     ✅ ${extracted.storeName} | ${extracted.datetime} | ¥${extracted.earnings} | ${extracted.distance}km | ${extracted.durationFormatted}`);

      // 閉じる
      const closeSelectors = [
        '[aria-label="Close"]',
        '[aria-label="閉じる"]',
        'button:has-text("閉じる")',
        'button:has-text("Close")',
        '[class*="close"]',
        '[class*="Close"]',
      ];
      let closed = false;
      for (const sel of closeSelectors) {
        const btn = page.locator(sel).first();
        if (await btn.count() > 0) {
          await btn.click();
          closed = true;
          break;
        }
      }
      if (!closed) await page.keyboard.press('Escape');
      await humanWait();

    } catch (err) {
      console.warn(`  ⚠️  ${i + 1}件目でエラー: ${err.message}`);
      deliveries.push({ no: i + 1, error: err.message });
      // エラー時はEscapeで強制クローズ
      await page.keyboard.press('Escape').catch(() => {});
      await wait(1000);
    }
  }

  // ---- 結果保存 ----
  const result = {
    date:       targetDate,
    scrapedAt:  new Date().toISOString(),
    totalCount: deliveries.length,
    successCount: deliveries.filter(d => !d.error).length,
    deliveries,
  };

  fs.writeFileSync(OUTPUT_PATH, JSON.stringify(result, null, 2), 'utf-8');

  console.log(`\n✅ スクレイピング完了`);
  console.log(`   保存先    : ${OUTPUT_PATH}`);
  console.log(`   取得件数  : ${result.successCount}/${result.totalCount}件`);

  if (result.successCount < result.totalCount) {
    console.warn(`\n⚠️  ${result.totalCount - result.successCount}件が取得失敗。`);
    console.warn(`   data/debug/ のHTMLダンプを確認してセレクタを調整してください。`);
  }

  await browser.close();
})();
