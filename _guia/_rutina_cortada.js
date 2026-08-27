/**
 * Barrido de la pantalla de Rutina: que texto sale cortado por `truncate` en el movil.
 * Uso:  node _guia/_rutina_cortada.js [ancho]
 */
const { chromium } = require('playwright');
const path = require('path');
const APP = 'http://localhost:3000';
const API = 'http://127.0.0.1:8000';

(async () => {
    const ancho = Number(process.argv[2]) || 390;
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 1400 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: 'francisco@test.com', password: 'demo123' } });
    const { access_token, token } = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, access_token || token);
    await page.goto(`${APP}/dashboard/routine`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(7000);
    const saltar = page.getByRole('button', { name: /saltar/i }).first();
    if (await saltar.count()) { await saltar.click().catch(() => {}); await page.waitForTimeout(1500); }

    const cortados = await page.evaluate(() => {
        const fuera = [];
        for (const el of document.querySelectorAll('*')) {
            const r = el.getBoundingClientRect();
            if (r.width < 2 || r.height < 2) continue;
            // Solo hojas con texto propio.
            const propio = [...el.childNodes].filter((n) => n.nodeType === 3 && n.textContent.trim());
            if (!propio.length) continue;
            if (el.scrollWidth > el.clientWidth + 1) {
                fuera.push(`«${el.textContent.trim().slice(0, 24)}» cabe ${Math.round(r.width)}px y pide ${el.scrollWidth}px  [${el.className.toString().slice(0, 44)}]`);
            }
        }
        return [...new Set(fuera)];
    });
    console.log(`A ${ancho} px, textos cortados en Rutina: ${cortados.length}`);
    cortados.forEach((c) => console.log('   ' + c));
    await page.screenshot({ path: path.join(__dirname, '_nutricion_2608', `rutina-${ancho}.jpg`), type: 'jpeg', quality: 72, fullPage: true });
    await nav.close();
})();
