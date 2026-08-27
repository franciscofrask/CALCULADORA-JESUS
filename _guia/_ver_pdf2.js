const { chromium } = require('playwright');
const { pathToFileURL } = require('url');
const path = require('path');
(async () => {
    const nav = await chromium.launch({ channel: 'chrome' });
    const p = await nav.newPage({ viewport: { width: 1000, height: 1350 } });
    await p.goto(pathToFileURL(path.resolve(process.argv[2])).href + '#page=' + (process.argv[3] || 3));
    await p.waitForTimeout(4000);
    await p.screenshot({ path: path.join(__dirname, '_nutricion_2608', 'pdf-pag.jpg'), type: 'jpeg', quality: 74 });
    await nav.close();
})();
