/**
 * scraper.js - React SPA対応版
 *
 * UberはReact SPAのため、クリック後にDOMのレンダリング完了を
 * 明示的に待ってからデータを取得する。
 */

const { chromium } = require('playwright');
const fs   = require('fs');
const path = require('path');

// ================================================================
// 引数処理
// ================================================================
const args       = process.argv.slice(2);
const DEBUG      = args.includes('--debug');
const dateArg    = args[args.indexOf('--date') + 1] || 'today';
const targetDate = dateArg === 'today'
  ? new Date(Date.now() + 9*60*60*1000).toISOString().slice(0,10)
  : dateArg;

console.log(`\n🚀 scraper.js 起動（React SPA対応版）`);
console.log(`   対象日 : ${targetDate}`);

// ================================================================
// パス設定
// ================================================================
const SESSION_PATH = path.join(__dirname, '../session/session.json');
const RAW_DIR      = path.join(__dirname, '../data/raw');
const DEBUG_DIR    = path.join(__dirname, '../data/debug');
const OUTPUT_PATH  = path.join(RAW_DIR, `${targetDate}.json`);

if (!fs.existsSync(SESSION_PATH)) {
  console.error('❌ session/session.json が見つかりません。');
  process.exit(1);
}
[RAW_DIR, DEBUG_DIR].forEach(d => { if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true }); });

// ================================================================
// ユーティリティ
// ================================================================
const wait      = ms => new Promise(r => setTimeout(r, ms));
const humanWait = () => wait(1000 + Math.random() * 800);

// ================================================================
// メイン
// ================================================================
(async () => {
  const browser = await chromium.launch({
    headless: false, // React SPAはheadlessだと不安定なため常にtrue以外
    args: ['--no-sandbox', '--disable-blink-features=AutomationControlled'],
  });

  const context = await browser.newContext({
    storageState: SESSION_PATH,
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    locale: 'ja-JP',
    timezoneId: 'Asia/Tokyo',
    viewport: { width: 1280, height: 900 },
  });

  await context.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => false });
  });

  const page = await context.newPage();

  // ---- セッション確認 ----
  console.log('\n🔐 セッション確認中...');
  await page.goto('https://drivers.uber.com/p3/payments/activity-details', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await wait(3000);

  if (page.url().includes('auth.uber.com') || page.url().includes('login')) {
    console.error('❌ セッション期限切れ。save-session.js を再実行してください。');
    await browser.close();
    process.exit(1);
  }
  console.log('   ✅ セッション有効');

  // ---- 対象日に移動 ----
  const url = `https://drivers.uber.com/p3/payments/activity-details?from=${targetDate}&to=${targetDate}`;
  console.log(`\n📄 移動中: ${url}`);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });

  // Reactのレンダリングを待つ（テーブルの行が出るまで）
  console.log('   Reactレンダリング待機中...');
  await page.waitForFunction(() => {
    const cells = document.querySelectorAll('td');
    return cells.length > 3;
  }, { timeout: 15000 }).catch(() => console.warn('   ⚠️ テーブル待機タイムアウト'));
  await wait(2000);

  // ---- DEBUGモード ----
  if (DEBUG) {
    // 1件目のView Detailsをクリックして詳細HTMLをダンプ
    const btns = await page.locator('button:has-text("View Details"), a:has-text("View Details")').all();
    if (btns.length > 0) {
      await btns[0].click();
      // React描画待ち：金額要素が出るまで
      await page.waitForFunction(() => {
        const body = document.body.innerText;
        return body.includes('km') && body.includes('分');
      }, { timeout: 10000 }).catch(() => {});
      await wait(2000);
      const html = await page.content();
      const dumpPath = path.join(DEBUG_DIR, `detail_rendered_${targetDate}.html`);
      fs.writeFileSync(dumpPath, html, 'utf-8');
      console.log(`\n🔍 レンダリング済みHTMLを保存: ${dumpPath}`);

      // テキストも保存（確認しやすい）
      const bodyText = await page.evaluate(() => document.body.innerText);
      const txtPath  = path.join(DEBUG_DIR, `detail_text_${targetDate}.txt`);
      fs.writeFileSync(txtPath, bodyText, 'utf-8');
      console.log(`📝 テキスト版を保存: ${txtPath}`);
      console.log('\n--- 取得テキスト（先頭100行）---');
      console.log(bodyText.split('\n').slice(0, 100).join('\n'));
    }
    await browser.close();
    return;
  }

  // ---- 全件スクロールしてロード ----
  console.log('\n📋 全件ロード中...');
  let prevCount = 0;
  for (let i = 0; i < 30; i++) {
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await wait(800);
    const count = await page.locator('button:has-text("View Details"), a:has-text("View Details")').count();
    if (count === prevCount && count > 0) break;
    prevCount = count;
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  await wait(1000);

  const totalButtons = await page.locator('button:has-text("View Details"), a:has-text("View Details")').count();
  console.log(`📦 View Detailsボタン: ${totalButtons}件`);

  if (totalButtons === 0) {
    console.error('❌ View Detailsボタンが見つかりません。--debugで確認してください。');
    await browser.close();
    process.exit(1);
  }

  // ---- 各配達の詳細取得 ----
  const deliveries = [];

  for (let i = 0; i < totalButtons; i++) {
    console.log(`  [${i+1}/${totalButtons}] 取得中...`);
    try {
      // ボタン再取得
      const buttons = await page.locator('button:has-text("View Details"), a:has-text("View Details")').all();
      await buttons[i].scrollIntoViewIfNeeded();
      await humanWait();
      await buttons[i].click();

      // ★ React描画完了を待つ ★
      // 「分」「km」「¥」が同時に画面に出るまで待機
      await page.waitForFunction(() => {
        const text = document.body.innerText;
        return (
          (text.includes('分') || text.includes(':')) &&
          text.includes('km') &&
          text.includes('¥') &&
          !text.includes('読み込み中')
        );
      }, { timeout: 8000 }).catch(() => {});
      await wait(800);

      // テキストベースで全データ取得（セレクタ不要）
      const data = await page.evaluate(() => {
        const text = document.body.innerText;
        const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0);

        // 売上（¥XXX 形式で最初に出てくる大きな数字）
        let earnings = 0;
        for (const line of lines) {
          const m = line.match(/^¥([\d,]+)$/);
          if (m) {
            const val = parseInt(m[1].replace(',', ''));
            if (val >= 100) { earnings = val; break; }
          }
        }

        // 時間（XX分XX秒）
        let duration = '不明';
        let durationSec = 0;
        const durMatch = text.match(/(\d+)\s*分\s*(\d+)\s*秒/);
        if (durMatch) {
          const m = parseInt(durMatch[1]), s = parseInt(durMatch[2]);
          durationSec = m * 60 + s;
          duration = `${m}:${String(s).padStart(2,'0')}`;
        }

        // 距離（X.XX km）
        let distance = 0;
        const distMatch = text.match(/([\d.]+)\s*km/);
        if (distMatch) distance = parseFloat(distMatch[1]);

        // 日時（Delivery・YYYY年M月D日・午前/午後HH時MM分）
        let datetime = null;
        const dtMatch = text.match(/(\d{4}年\d{1,2}月\d{1,2}日)[^\n]*?(午前|午後)\s*(\d+)時(\d+)分/);
        if (dtMatch) datetime = `${dtMatch[1]} ${dtMatch[2]}${dtMatch[3]}時${dtMatch[4]}分`;

        // 店舗名・配達先（ルート部分のテキスト）
        // Uberの詳細画面: 「●店舗名\n■住所」の形式
        let storeName = '不明';
        let destAddress = '不明';

        // 「東京都」を含む行の前後を店舗名・住所として取得
        for (let i = 0; i < lines.length; i++) {
          if (lines[i].includes('東京都') || lines[i].match(/[都道府県].+[区市町村]/)) {
            destAddress = lines[i];
            // 住所の2〜4行前が店舗名のことが多い
            for (let j = i - 1; j >= Math.max(0, i - 4); j--) {
              const candidate = lines[j];
              if (
                candidate.length > 2 &&
                !candidate.includes('¥') &&
                !candidate.match(/^\d+$/) &&
                !candidate.includes('Delivery') &&
                !candidate.includes('km') &&
                !candidate.includes('分') &&
                !candidate.includes('View')
              ) {
                storeName = candidate;
                break;
              }
            }
            break;
          }
        }

        // チップ
        let tip = 0;
        const tipMatch = text.match(/チップ[^\d¥]*¥?([\d,]+)/);
        if (tipMatch) tip = parseInt(tipMatch[1].replace(',', ''));

        return { earnings, duration, durationSec, distance, datetime, storeName, destAddress, tip, _rawLines: lines.slice(0, 30) };
      });

      deliveries.push({ no: i + 1, ...data });
      console.log(`     ✅ ${data.storeName} | ¥${data.earnings} | ${data.distance}km | ${data.duration}`);

      // デバッグ用：最初の3件はテキストダンプ
      if (i < 3) {
        fs.writeFileSync(
          path.join(DEBUG_DIR, `detail_text_${targetDate}_${i+1}.txt`),
          data._rawLines.join('\n'), 'utf-8'
        );
      }
      delete data._rawLines;

      // 閉じる
      let closed = false;
      for (const sel of ['[aria-label="Close"]', '[aria-label="閉じる"]', 'button:has-text("閉じる")', '[data-testid="close"]']) {
        const btn = page.locator(sel).first();
        if (await btn.count() > 0) { await btn.click(); closed = true; break; }
      }
      if (!closed) await page.keyboard.press('Escape');
      await humanWait();

    } catch (err) {
      console.warn(`  ⚠️  ${i+1}件目エラー: ${err.message}`);
      deliveries.push({ no: i+1, error: err.message });
      await page.keyboard.press('Escape').catch(() => {});
      await wait(1000);
    }
  }

  // ---- 保存 ----
  const result = {
    date: targetDate,
    scrapedAt: new Date().toISOString(),
    totalCount: deliveries.length,
    successCount: deliveries.filter(d => !d.error && d.earnings > 0).length,
    deliveries,
  };
  fs.writeFileSync(OUTPUT_PATH, JSON.stringify(result, null, 2), 'utf-8');

  console.log(`\n✅ スクレイピング完了`);
  console.log(`   保存先    : ${OUTPUT_PATH}`);
  console.log(`   成功件数  : ${result.successCount}/${result.totalCount}件`);

  await browser.close();
})();
