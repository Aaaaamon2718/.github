/**
 * scraper.js - 一覧直接取得版
 * View Detailsページに個別アクセスして全データを取得する
 */
const { chromium } = require('playwright');
const fs   = require('fs');
const path = require('path');
const args       = process.argv.slice(2);
const dateArg    = args[args.indexOf('--date') + 1] || 'today';
const targetDate = dateArg === 'today'
  ? new Date(Date.now() + 9*60*60*1000).toISOString().slice(0,10)
  : dateArg;
console.log(`\n🚀 scraper.js 起動（直接URL版）`);
console.log(`   対象日 : ${targetDate}`);
const SESSION_PATH = path.join(__dirname, '../session/session.json');
const RAW_DIR      = path.join(__dirname, '../data/raw');
const DEBUG_DIR    = path.join(__dirname, '../data/debug');
const OUTPUT_PATH  = path.join(RAW_DIR, `${targetDate}.json`);
if (!fs.existsSync(SESSION_PATH)) { console.error('❌ session.json なし'); process.exit(1); }
[RAW_DIR, DEBUG_DIR].forEach(d => { if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true }); });
const wait      = ms => new Promise(r => setTimeout(r, ms));
const humanWait = () => wait(1000 + Math.random() * 800);
(async () => {
  const browser = await chromium.launch({
    headless: false,
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
  // セッション確認
  console.log('\n🔐 セッション確認中...');
  await page.goto('https://drivers.uber.com/p3/payments/activity-details', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await wait(3000);
  if (page.url().includes('auth') || page.url().includes('login')) {
    console.error('❌ セッション期限切れ'); await browser.close(); process.exit(1);
  }
  console.log('   ✅ セッション有効');
  // 対象日に移動
  const url = `https://drivers.uber.com/p3/payments/activity-details?from=${targetDate}&to=${targetDate}`;
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await wait(3000);
  // Reactレンダリング待ち
  await page.waitForFunction(() => document.querySelectorAll('td').length > 3, { timeout: 15000 }).catch(() => {});
  await wait(2000);
  // スクロールして全件ロード
  console.log('\n📋 全件ロード中...');
  let prevCount = 0;
  for (let i = 0; i < 30; i++) {
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await wait(1000);
    const count = await page.locator('button:has-text("View Details"), a:has-text("View Details")').count();
    if (count === prevCount && count > 0) break;
    prevCount = count;
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  await wait(1000);
  // View DetailsのリンクURLを全件収集
  const detailLinks = await page.evaluate(() => {
    const links = [];
    // aタグのhref
    document.querySelectorAll('a').forEach(a => {
      if (a.textContent.includes('View Details') && a.href) links.push(a.href);
    });
    // buttonタグの場合はdata属性やonclickからURL取得
    if (links.length === 0) {
      document.querySelectorAll('button').forEach(btn => {
        if (btn.textContent.includes('View Details')) {
          const url = btn.getAttribute('data-href') || btn.getAttribute('data-url');
          if (url) links.push(url);
        }
      });
    }
    return links;
  });
  console.log(`🔗 詳細リンク数: ${detailLinks.length}件`);
  // リンクがある場合は直接URLアクセス
  // リンクがない場合はクリック後に新しいページのURLを取得
  const totalButtons = await page.locator('button:has-text("View Details"), a:has-text("View Details")').count();
  console.log(`📦 View Detailsボタン: ${totalButtons}件`);
  const deliveries = [];
  for (let i = 0; i < totalButtons; i++) {
    console.log(`  [${i+1}/${totalButtons}] 取得中...`);
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await wait(2000);
      await page.waitForFunction(() => document.querySelectorAll('td').length > 3, { timeout: 10000 }).catch(() => {});
      await wait(1000);
      // スクロールして全件表示
      for (let s = 0; s < 5; s++) {
        await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
        await wait(500);
      }
      await page.evaluate(() => window.scrollTo(0, 0));
      const buttons = await page.locator('button:has-text("View Details"), a:has-text("View Details")').all();
      if (i >= buttons.length) break;
      await buttons[i].scrollIntoViewIfNeeded();
      await wait(500);
      // クリック前後でURLの変化を検知
      const beforeUrl = page.url();
      await buttons[i].click();
      await wait(2000);
      const afterUrl = page.url();
      let data;
      if (afterUrl !== beforeUrl) {
        // 別ページに遷移した場合
        console.log(`     📄 詳細ページに遷移: ${afterUrl}`);
        await page.waitForFunction(() => {
          const text = document.body.innerText;
          return text.includes('km') || text.includes('分');
        }, { timeout: 8000 }).catch(() => {});
        await wait(1000);
        const bodyText = await page.evaluate(() => document.body.innerText);
        if (i < 3) fs.writeFileSync(path.join(DEBUG_DIR, `detail_page_${targetDate}_${i+1}.txt`), bodyText, 'utf-8');
        data = extractData(bodyText);
      } else {
        // 同一ページでパネルが開いた場合
        await page.waitForFunction(() => {
          const text = document.body.innerText;
          return text.includes('km') && text.includes('分') && text.includes('¥');
        }, { timeout: 8000 }).catch(() => {});
        await wait(800);
        const bodyText = await page.evaluate(() => document.body.innerText);
        if (i < 3) fs.writeFileSync(path.join(DEBUG_DIR, `detail_panel_${targetDate}_${i+1}.txt`), bodyText, 'utf-8');
        data = extractData(bodyText);
        // パネルを閉じる
        for (const sel of ['[aria-label="Close"]', '[aria-label="閉じる"]', 'button:has-text("閉じる")']) {
          const btn = page.locator(sel).first();
          if (await btn.count() > 0) { await btn.click(); break; }
        }
        await page.keyboard.press('Escape');
        await humanWait();
      }
      deliveries.push({ no: i + 1, ...data });
      console.log(`     ✅ ${data.storeName} | ¥${data.earnings} | ${data.distance}km | ${data.duration}`);
    } catch (err) {
      console.warn(`  ⚠️  ${i+1}件目エラー: ${err.message}`);
      deliveries.push({ no: i+1, error: err.message });
    }
  }
  const result = {
    date: targetDate,
    scrapedAt: new Date().toISOString(),
    totalCount: deliveries.length,
    successCount: deliveries.filter(d => !d.error && d.earnings > 0).length,
    deliveries,
  };
  fs.writeFileSync(OUTPUT_PATH, JSON.stringify(result, null, 2), 'utf-8');
  console.log(`\n✅ 完了: ${result.successCount}/${result.totalCount}件`);
  await browser.close();
})();
function extractData(text) {
  const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0);
  // 売上
  let earnings = 0;
  for (const line of lines) {
    const m = line.match(/^[¥￥]([\d,]+)$/);
    if (m) { const v = parseInt(m[1].replace(',','')); if (v >= 100) { earnings = v; break; } }
  }
  // 時間
  let duration = '不明', durationSec = 0;
  const durMatch = text.match(/(\d+)\s*分\s*(\d+)\s*秒/);
  if (durMatch) {
    const m = parseInt(durMatch[1]), s = parseInt(durMatch[2]);
    durationSec = m*60+s;
    duration = `${m}:${String(s).padStart(2,'0')}`;
  }
  // 距離
  let distance = 0;
  const distMatch = text.match(/([\d.]+)\s*km/);
  if (distMatch) distance = parseFloat(distMatch[1]);
  // 日時
  let datetime = null;
  const dtMatch = text.match(/(\d{4}年\d{1,2}月\d{1,2}日)[^\n]*?(午前|午後)\s*(\d+)時(\d+)分/);
  if (dtMatch) datetime = `${dtMatch[1]} ${dtMatch[2]}${dtMatch[3]}時${dtMatch[4]}分`;
  // 店舗名・住所
  let storeName = '不明', destAddress = '不明';
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].match(/東京都|[都道府県].+[区市町村]/)) {
      destAddress = lines[i];
      for (let j = i-1; j >= Math.max(0, i-4); j--) {
        const c = lines[j];
        if (c.length > 2 && !c.includes('¥') && !c.includes('￥') && !c.match(/^\d+$/) &&
            !c.includes('Delivery') && !c.includes('km') && !c.includes('分') && !c.includes('View')) {
          storeName = c; break;
        }
      }
      break;
    }
  }
  // チップ
  let tip = 0;
  const tipMatch = text.match(/チップ[^\d¥￥]*[¥￥]?([\d,]+)/);
  if (tipMatch) tip = parseInt(tipMatch[1].replace(',',''));
  return { earnings, duration, durationSec, distance, datetime, storeName, destAddress, tip };
}
