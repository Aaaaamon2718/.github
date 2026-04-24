#!/usr/bin/env node
/**
 * Uber Eats 配達データスクレイパー
 * 実行: node scripts/scraper.js [--date YYYY-MM-DD|today]
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const SESSION_PATH = path.join(__dirname, '../session/session.json');
const RAW_DIR = path.join(__dirname, '../data/raw');

const MAX_RETRIES = 3;
const WAIT_MS = 1500;

function getTargetDate(args) {
  const dateArg = args.find(a => a.startsWith('--date'));
  if (!dateArg) return formatDate(new Date());
  const val = dateArg.includes('=') ? dateArg.split('=')[1] : args[args.indexOf(dateArg) + 1];
  if (val === 'today') return formatDate(new Date());
  if (/^\d{4}-\d{2}-\d{2}$/.test(val)) return val;
  throw new Error(`無効な日付形式: ${val}  (YYYY-MM-DD形式で指定してください)`);
}

function formatDate(d) {
  return d.toISOString().split('T')[0];
}

async function withRetry(fn, label) {
  for (let i = 1; i <= MAX_RETRIES; i++) {
    try {
      return await fn();
    } catch (e) {
      if (i === MAX_RETRIES) throw e;
      console.warn(`  リトライ ${i}/${MAX_RETRIES}: ${label} — ${e.message}`);
      await new Promise(r => setTimeout(r, 1000 * i));
    }
  }
}

async function checkSessionExpired(page) {
  const url = page.url();
  if (url.includes('/login') || url.includes('/signin') || url.includes('auth')) {
    console.error('ERROR: SESSION_EXPIRED — セッションが失効しています。node scripts/auth/save-session.js を再実行してください。');
    process.exit(1);
  }
}

async function extractDeliveryDetails(page) {
  return await page.evaluate(() => {
    const getText = selector => {
      const el = document.querySelector(selector);
      return el ? el.textContent.trim() : null;
    };

    const parseYen = str => {
      if (!str) return 0;
      return parseInt(str.replace(/[^0-9]/g, ''), 10) || 0;
    };

    const parseDistance = str => {
      if (!str) return null;
      const m = str.match(/[\d.]+/);
      return m ? parseFloat(m[0]) : null;
    };

    const parseDuration = str => {
      if (!str) return null;
      return str.trim();
    };

    return {
      earnings: parseYen(getText('[data-testid="trip-earnings"], .trip-earnings, [class*="earnings"]')),
      tipAmount: parseYen(getText('[data-testid="tip-amount"], .tip-amount, [class*="tip"]')),
      distance: parseDistance(getText('[data-testid="trip-distance"], .trip-distance, [class*="distance"]')),
      duration: parseDuration(getText('[data-testid="trip-duration"], .trip-duration, [class*="duration"]')),
      storeName: getText('[data-testid="restaurant-name"], .restaurant-name, [class*="restaurant"], [class*="store"]'),
      area: getText('[data-testid="dropoff-address"], .dropoff-address, [class*="dropoff"], [class*="destination"]'),
      questBonus: parseYen(getText('[data-testid="quest-bonus"], .quest-bonus, [class*="bonus"], [class*="quest"]')),
    };
  });
}

async function scrapeActivityPage(page, date) {
  const from = date;
  const to = date;
  const url = `https://drivers.uber.com/p3/payments/activity-details?from=${from}&to=${to}`;

  console.log(`\nアクティビティページを読み込み中: ${url}`);
  await withRetry(() => page.goto(url, { waitUntil: 'networkidle', timeout: 45000 }), 'ページ読み込み');
  await checkSessionExpired(page);
  await page.waitForTimeout(WAIT_MS);

  const deliveries = [];

  // 配達行を全件取得
  const rows = await page.$$('[data-testid="activity-row"], .activity-row, [class*="ActivityRow"], [class*="activity-item"]');
  console.log(`  検出した配達行: ${rows.length}件`);

  if (rows.length === 0) {
    console.log('  配達データが見つかりませんでした（当日データなし、またはセレクター要調整）');
    return deliveries;
  }

  for (let i = 0; i < rows.length; i++) {
    console.log(`  処理中 ${i + 1}/${rows.length}...`);

    try {
      // 完了時刻を行から取得
      const completedAt = await rows[i].evaluate(el => {
        const timeEl = el.querySelector('[class*="time"], [class*="date"], time');
        return timeEl ? timeEl.textContent.trim() : null;
      });

      // 詳細ボタンをクリック
      const detailBtn = await rows[i].$('button, [role="button"], a[href*="detail"]');
      if (detailBtn) {
        await detailBtn.click();
        await page.waitForTimeout(WAIT_MS);

        const details = await extractDeliveryDetails(page);
        deliveries.push({ completedAt, ...details });

        // モーダルを閉じる
        const closeBtn = await page.$('[aria-label="Close"], [data-testid="modal-close"], button[class*="close"]');
        if (closeBtn) {
          await closeBtn.click();
          await page.waitForTimeout(800);
        } else {
          await page.keyboard.press('Escape');
          await page.waitForTimeout(800);
        }
      } else {
        // 行自体をクリックして詳細ページへ
        await rows[i].click();
        await page.waitForTimeout(WAIT_MS);
        await checkSessionExpired(page);

        const details = await extractDeliveryDetails(page);
        deliveries.push({ completedAt, ...details });

        await page.goBack({ waitUntil: 'networkidle', timeout: 30000 });
        await page.waitForTimeout(WAIT_MS);

        // DOM再取得が必要なためループ変数を再取得
      }
    } catch (e) {
      console.warn(`  警告: ${i + 1}件目の取得に失敗 — ${e.message}`);
      deliveries.push({ index: i + 1, error: e.message });
    }
  }

  return deliveries;
}

(async () => {
  const args = process.argv.slice(2);
  const date = getTargetDate(args);

  console.log(`=== Uber Eats スクレイパー ===`);
  console.log(`対象日: ${date}`);

  if (!fs.existsSync(SESSION_PATH)) {
    console.error(`セッションファイルが見つかりません: ${SESSION_PATH}`);
    console.error('先に node scripts/auth/save-session.js を実行してください。');
    process.exit(1);
  }

  if (!fs.existsSync(RAW_DIR)) {
    fs.mkdirSync(RAW_DIR, { recursive: true });
  }

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-blink-features=AutomationControlled'],
  });

  const context = await browser.newContext({
    storageState: SESSION_PATH,
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    viewport: { width: 1280, height: 800 },
  });

  const page = await context.newPage();

  try {
    const deliveries = await scrapeActivityPage(page, date);

    const output = {
      date,
      scrapedAt: new Date().toISOString(),
      totalDeliveries: deliveries.filter(d => !d.error).length,
      deliveries,
    };

    const outPath = path.join(RAW_DIR, `${date}.json`);
    fs.writeFileSync(outPath, JSON.stringify(output, null, 2), 'utf-8');

    console.log(`\n完了: ${outPath} に保存しました`);
    console.log(`取得件数: ${output.totalDeliveries}件`);
  } catch (e) {
    console.error('\nスクレイピングエラー:', e.message);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
