// Renders each storyboard HTML file in a folder to a 1280x720 PNG. Used by storyboard.py.
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const dir = process.argv[2];
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  for (const f of fs.readdirSync(dir).filter(f => f.endsWith('.html')).sort()) {
    await page.setContent(fs.readFileSync(path.join(dir, f), 'utf8'));
    await page.screenshot({ path: path.join(dir, f.replace(/\.html$/, '.png')) });
  }
  await browser.close();
})();
