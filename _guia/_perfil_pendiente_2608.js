/**
 * Mi perfil con la ficha incompleta (punto 111 de la parte 3): el aviso mudado desde
 * Nutricion y el punto naranja del menu.
 * Uso:  node _guia/_perfil_pendiente_2608.js [ancho]
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const APP = 'http://localhost:3000';
const API = 'http://localhost:8000';
const SALIDA = path.join(__dirname, '_nutricion_2608');

(async () => {
    const ancho = Number(process.argv[2]) || 390;
    fs.mkdirSync(SALIDA, { recursive: true });
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 900 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: 'francisco@test.com', password: 'demo123' } });
    const { access_token, token } = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, access_token || token);

    await page.goto(`${APP}/dashboard/profile`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(4000);
    const saltar = page.getByRole('button', { name: /saltar/i }).first();
    if (await saltar.count()) { await saltar.click().catch(() => {}); await page.waitForTimeout(1200); }

    console.log(JSON.stringify(await page.evaluate(() => ({
        aviso: (document.querySelector('[data-testid="macros-provisionales"]')?.innerText || '').replace(/\n+/g, ' · '),
        puntoMenuLateral: !!document.querySelector('[data-testid="punto-ficha-pendiente"]'),
        puntoEnMas: !!document.querySelector('[data-testid="punto-ficha-pendiente-mas"]'),
    })), null, 1));
    await page.screenshot({ path: path.join(SALIDA, `perfil-${ancho}.jpg`), type: 'jpeg', quality: 70 });

    // Y que en Nutricion ya NO esta.
    await page.goto(`${APP}/dashboard/nutrition`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(3500);
    console.log('en Nutricion:', await page.evaluate(() =>
        !!document.querySelector('[data-testid="macros-provisionales"]')));
    await nav.close();
})();
