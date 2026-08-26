/**
 * El cartel de la calibracion (puntos 133 y 134 de la parte 4).
 * Uso:  node _guia/_calibracion_2608.js
 */
const { chromium } = require('playwright');
const path = require('path');
const APP = 'http://localhost:3000';
const API = 'http://localhost:8000';
const C = 'C3';

(async () => {
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: 390, height: 1100 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: 'francisco@test.com', password: 'demo123' } });
    const { access_token, token } = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, access_token || token);
    await page.goto(`${APP}/dashboard/nutrition`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(6000);
    const saltar = page.getByRole('button', { name: /saltar/i }).first();
    if (await saltar.count()) { await saltar.click().catch(() => {}); await page.waitForTimeout(1200); }
    await page.locator(`[data-testid="meal-card-${C}"] button`).first().click();
    // La calibracion se pide con 300 ms de retardo y viaja al servidor: hay que
    // esperar al contador, no a un reloj.
    await page.waitForSelector(`[data-testid="meal-card-${C}"] [data-testid^="contador-"]`,
        { timeout: 20000 }).catch(() => console.log('(el contador no llego)'));
    await page.waitForTimeout(600);
    console.log(JSON.stringify(await page.evaluate((c) => {
        const card = document.querySelector(`[data-testid="meal-card-${c}"]`);
        return [...card.querySelectorAll('[data-testid^="contador-"]')]
            .map((el) => {
                const fila = el.closest('div[class*="rounded"]') || el.parentElement;
                const nombre = (fila?.innerText || '').split('\n')[0];
                return `${nombre.slice(0, 22)} -> ${el.innerText.trim()}`;
            });
    }, C), null, 1));
    await page.screenshot({ path: path.join(__dirname, '_nutricion_2608', 'calibracion-390.jpg'), type: 'jpeg', quality: 70, fullPage: true });
    await nav.close();
})();
