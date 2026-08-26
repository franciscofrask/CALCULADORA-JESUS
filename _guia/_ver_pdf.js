/** Captura las paginas de un PDF como imagen, para revisarlo sin poppler. */
const { chromium } = require('playwright');
const { pathToFileURL } = require('url');
const path = require('path');
(async () => {
    const nav = await chromium.launch({ channel: 'chrome' });
    const p = await nav.newPage({ viewport: { width: 900, height: 1300 } });
    await p.goto(pathToFileURL(path.resolve(process.argv[2])).href);
    await p.waitForTimeout(3500);
    for (let i = 0; i < Number(process.argv[3] || 3); i++) {
        await p.screenshot({ path: path.join(__dirname, '_nutricion_2608', `pdf-${i + 1}.jpg`), type: 'jpeg', quality: 72 });
        await p.keyboard.press('PageDown');
        await p.waitForTimeout(900);
    }
    await nav.close();
})();
