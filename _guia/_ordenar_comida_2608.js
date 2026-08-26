/**
 * El modo «Ordenar los alimentos» de una comida (punto 126 de la parte 4).
 * Uso:  node _guia/_ordenar_comida_2608.js [ancho] [comida]
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const APP = 'http://localhost:3000';
const API = 'http://localhost:8000';
const SALIDA = path.join(__dirname, '_nutricion_2608');

(async () => {
    const ancho = Number(process.argv[2]) || 390;
    const c = process.argv[3] || 'C3';
    fs.mkdirSync(SALIDA, { recursive: true });
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 1100 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: 'francisco@test.com', password: 'demo123' } });
    const { access_token, token } = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, access_token || token);
    await page.goto(`${APP}/dashboard/nutrition`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(5000);
    const saltar = page.getByRole('button', { name: /saltar/i }).first();
    if (await saltar.count()) { await saltar.click().catch(() => {}); await page.waitForTimeout(1200); }

    await page.locator(`[data-testid="meal-card-${c}"] button`).first().click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: path.join(SALIDA, `comida-cerrada-${ancho}.jpg`), type: 'jpeg', quality: 70, fullPage: true });

    await page.locator(`[data-testid="meal-card-${c}"] [data-testid="menu-pantalla"]`).click();
    await page.waitForTimeout(400);
    await page.locator(`[data-testid="menu-pantalla-ordenar-${c}"]`).click();
    await page.waitForTimeout(700);
    console.log('ordenando:', JSON.stringify(await page.evaluate((c) => {
        const card = document.querySelector(`[data-testid="meal-card-${c}"]`);
        const flechas = [...card.querySelectorAll('[data-testid^="reorder-"]')];
        return {
            barra: !!card.querySelector(`[data-testid="ordenando-${c}"]`),
            flechas: flechas.length,
            primeraApagada: flechas[0]?.disabled === true,
            opacidadPrimera: flechas[0] ? getComputedStyle(flechas[0]).opacity : null,
        };
    }, c)));
    await page.screenshot({ path: path.join(SALIDA, `ordenando-${ancho}.jpg`), type: 'jpeg', quality: 70, fullPage: true });

    await page.locator(`[data-testid="ordenar-listo-${c}"]`).click();
    await page.waitForTimeout(500);
    console.log('tras Listo, flechas:', await page.evaluate((c) =>
        document.querySelectorAll(`[data-testid="meal-card-${c}"] [data-testid^="reorder-"]`).length, c));
    await nav.close();
})();
