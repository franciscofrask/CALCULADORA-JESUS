/**
 * El «···» de la cabecera de Nutricion (puntos 113 y 119 de la parte 3).
 * Uso:  node _guia/_menu_nutricion_2608.js [ancho]
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
    await page.goto(`${APP}/dashboard/nutrition`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(4500);
    const saltar = page.getByRole('button', { name: /saltar/i }).first();
    if (await saltar.count()) { await saltar.click().catch(() => {}); await page.waitForTimeout(1200); }

    const antes = await page.evaluate(() => ({
        pdf: !!document.querySelector('[data-testid="export-pdf-btn"]'),
        menu: !!document.querySelector('[data-testid="menu-pantalla"]'),
        pdfAbajo: !!document.querySelector('[data-testid="export-pdf-btn-mobile"]'),
        tuerca: !!document.querySelector('[data-testid="toggle-ajustes-vista"]'),
        resumenViejo: !!document.querySelector('[data-testid="toggle-config"]')
            || !!document.querySelector('[data-testid="toggle-config-escritorio"]'),
    }));
    console.log('cabecera:', JSON.stringify(antes));

    await page.locator('[data-testid="menu-pantalla"]').click();
    await page.waitForTimeout(600);
    console.log('menu:', JSON.stringify(await page.evaluate(() =>
        [...document.querySelectorAll('[data-testid^="menu-pantalla-"]')]
            .filter(b => b.dataset.testid !== 'menu-pantalla-abierto')
            .map(b => b.innerText.replace(/\n+/g, ' · ')))));
    await page.screenshot({ path: path.join(SALIDA, `menu-${ancho}.jpg`), type: 'jpeg', quality: 70 });

    // Que la configuracion se abra desde el menu y se pueda cerrar.
    await page.locator('[data-testid="menu-pantalla-config"]').click();
    await page.waitForTimeout(700);
    console.log('config abierta:', await page.evaluate(() => !!document.querySelector('[data-testid="config-section"]')));
    await page.locator('[data-testid="cerrar-config"]').click();
    await page.waitForTimeout(500);
    console.log('config cerrada:', await page.evaluate(() => !document.querySelector('[data-testid="config-section"]')));
    await nav.close();
})();
