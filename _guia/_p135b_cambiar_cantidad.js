/**
 * 135 (segunda mitad) · Cambiar la cantidad DENTRO de la ventana.
 *
 * `recalcFoodMacros` rehacia la cuenta desde los macros de la etiqueta, que llegan del
 * servidor ya puestos a cero por la regla de categoria: al pulsar «+» sobre unos anacardos
 * su proteina calibrada se iba a cero. Aqui se comprueba que ya no, y que el motor del dia
 * confirma el numero.
 *
 * Uso:  node _guia/_p135b_cambiar_cantidad.js
 */
const { chromium } = require('playwright');
const path = require('path');
const APP = 'http://localhost:3000';
const API = 'http://127.0.0.1:8000';
const C = 'C3';

(async () => {
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: 390, height: 1400 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: 'francisco@test.com', password: 'demo123' } });
    const { access_token, token } = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, access_token || token);
    await page.goto(`${APP}/dashboard/nutrition`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(6500);
    const saltar = page.getByRole('button', { name: /saltar/i }).first();
    if (await saltar.count()) { await saltar.click().catch(() => {}); await page.waitForTimeout(1500); }
    const tarjeta = page.locator(`[data-testid="meal-card-${C}"]`).filter({ visible: true }).first();
    await tarjeta.waitFor({ timeout: 25000 });
    await tarjeta.locator('button').first().click();
    await page.waitForTimeout(3000);

    await page.getByRole('button', { name: /Añadir ingrediente/i }).first().click();
    await page.waitForSelector('input[placeholder="Buscar alimento..."]', { timeout: 15000 });
    await page.locator('[data-testid="added-bar-toggle"]').click();
    await page.waitForTimeout(1500);

    const leer = async (donde) => console.log(donde + ': ' + (await page.evaluate(() => {
        const t = document.querySelector('[role="dialog"]')?.innerText || '';
        const i = t.indexOf('Proteína');
        const j = t.indexOf('añadidos');
        return (i >= 0 ? t.slice(i, i + 34).replace(/\s+/g, ' ') : '') + '   ||   ' +
               (j >= 0 ? t.slice(j, j + 32).replace(/\s+/g, ' ') : '') + '   ||   ' +
               [...document.querySelectorAll('[data-testid^="temp-mas-"]')].map((b) => {
                   const c = b.parentElement?.querySelector('input');
                   return c ? c.value + ' g' : '?';
               }).join(' / ');
    })));
    await leer('ANTES        ');

    for (let i = 0; i < 6; i++) { await page.locator('[data-testid="temp-mas-1"]').click(); await page.waitForTimeout(350); }
    await page.waitForTimeout(600);
    await leer('AL PULSAR «+»');
    // El motor del dia responde con 350 ms de retardo mas el viaje.
    await page.waitForTimeout(4000);
    await leer('YA CONFIRMADO');
    await page.screenshot({ path: path.join(__dirname, '_nutricion_2608', 'p135b.jpg'), type: 'jpeg', quality: 70 });
    await nav.close();
})();
