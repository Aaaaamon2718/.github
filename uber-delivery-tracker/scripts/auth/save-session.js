#!/usr/bin/env node
/**
 * 初回ログイン・Cookie保存スクリプト
 * 実行: node scripts/auth/save-session.js
 * → ブラウザが開くので手動でログイン → Enterキーで保存
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const readline = require('readline');

const SESSION_PATH = path.join(__dirname, '../../session/session.json');
const SESSION_DIR = path.dirname(SESSION_PATH);

async function waitForEnter(message) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise(resolve => {
    rl.question(message, () => {
      rl.close();
      resolve();
    });
  });
}

(async () => {
  if (!fs.existsSync(SESSION_DIR)) {
    fs.mkdirSync(SESSION_DIR, { recursive: true });
  }

  console.log('=== Uber Eats セッション保存ツール ===');
  console.log('ブラウザが開きます。Uberドライバーポータルにログインしてください。');
  console.log('');

  const browser = await chromium.launch({
    headless: false,
    args: ['--no-sandbox', '--disable-blink-features=AutomationControlled'],
  });

  const context = await browser.newContext({
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    viewport: { width: 1280, height: 800 },
  });

  const page = await context.newPage();

  try {
    await page.goto('https://drivers.uber.com', { waitUntil: 'domcontentloaded', timeout: 30000 });
  } catch (e) {
    console.log('ページ読み込み中... ブラウザで手動でログインを完了させてください。');
  }

  await waitForEnter('\nログイン完了後、Enterキーを押してください...');

  await context.storageState({ path: SESSION_PATH });

  const stats = fs.statSync(SESSION_PATH);
  console.log(`\nセッションを保存しました: ${SESSION_PATH}`);
  console.log(`ファイルサイズ: ${stats.size} bytes`);
  console.log('\n次回からは以下のコマンドで配達データを取得できます:');
  console.log('  node scripts/scraper.js --date today');

  await browser.close();
})().catch(err => {
  console.error('エラー:', err.message);
  process.exit(1);
});
