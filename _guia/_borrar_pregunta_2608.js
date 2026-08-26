/**
 * Punto 129: la papelera y Vaciar preguntan antes.
 * Uso:  node _guia/_borrar_pregunta_2608.js [ancho]
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const APP = 'http://localhost:3000';
const API = 'http://localhost:8000';
const SALIDA = path.join(__dirname, '_nutricion_2608');
const C = 'C3';

(async () => {
    const ancho = Number(process.argv[2]) || 390;
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
    await page.locator(`[data-testid="meal-card-${C}"] button`).first().click();
    await page.waitForTimeout(1500);

    const cuantos = () => page.evaluate((c) =>
        document.querySelectorAll(`[data-testid="meal-card-${c}"] [data-testid^="remove-"]`).length, C);
    console.log('ingredientes al empezar:', await cuantos());

    // 1 · La papelera pregunta, y al cancelar no se va nada.
    await page.locator(`[data-testid="remove-${C}-0"]`).click();
    await page.waitForTimeout(600);
    console.log('papelera · pregunta:', await page.evaluate(() => {
        const d = document.querySelector('[data-testid="confirm-dialog"]');
        return d ? d.innerText.replace(/\n+/g, ' · ') : null;
    }));
    await page.screenshot({ path: path.join(SALIDA, `pregunta-papelera-${ancho}.jpg`), type: 'jpeg', quality: 70 });
    await page.locator('[data-testid="confirm-cancel"]').click();
    await page.waitForTimeout(600);
    console.log('papelera · tras cancelar:', await cuantos());

    // 2 · Y al confirmar sí.
    await page.locator(`[data-testid="remove-${C}-0"]`).click();
    await page.waitForTimeout(500);
    await page.locator('[data-testid="confirm-ok"]').click();
    await page.waitForTimeout(800);
    console.log('papelera · tras confirmar:', await cuantos());

    // 3 · Vaciar, desde el «···».
    await page.locator(`[data-testid="meal-card-${C}"] [data-testid="menu-pantalla"]`).click();
    await page.waitForTimeout(400);
    await page.locator(`[data-testid="menu-pantalla-vaciar-${C}"]`).click();
    await page.waitForTimeout(600);
    console.log('vaciar · pregunta:', await page.evaluate(() => {
        const d = document.querySelector('[data-testid="confirm-dialog"]');
        return d ? d.innerText.replace(/\n+/g, ' · ') : null;
    }));
    await page.locator('[data-testid="confirm-cancel"]').click();
    await page.waitForTimeout(600);
    console.log('vaciar · tras cancelar:', await cuantos());
    await nav.close();
})();
