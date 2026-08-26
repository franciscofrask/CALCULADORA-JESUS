/**
 * 129 (el tercer camino) · Bajar la cantidad por debajo del minimo se llevaba el alimento
 * SIN AVISO NINGUNO. Jesus nombro Vaciar y la papelera; Francisco cerro el 26-08 que este
 * tambien pregunta.
 *
 * Son DOS caminos y los dos tenian que preguntar: el boton «−» a golpes, que borraba en
 * silencio y sin deshacer, y escribir 0 a mano, que borraba con un deshacer de 8 s.
 * Se comprueba que preguntan, que decir que NO deja el alimento donde estaba y que decir
 * que SI lo quita.
 *
 * Uso:  node _guia/_p129_tercer_camino.js
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
    page.on('pageerror', (e) => console.log('  [pageerror]', String(e).slice(0, 180)));
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
    await page.waitForTimeout(4000);   // que termine la recalibracion del dia

    const cuantos = () => tarjeta.locator('[data-testid^="qty-"]').count();
    const dialogo = page.locator('[data-testid="confirm-dialog"]');
    console.log('ingredientes al empezar:', await cuantos());

    // Deja el primer alimento en su minimo, para que el siguiente «−» cruce el suelo.
    const escribir = async (valor) => {
        await tarjeta.locator(`[data-testid="qty-${C}-0"]`).click();
        await page.waitForTimeout(1200);
        const caja = tarjeta.locator('input[type="number"]').first();
        await caja.waitFor({ timeout: 8000 });
        await caja.click();
        await caja.press('Control+a');
        await caja.type(String(valor), { delay: 120 });
        await caja.press('Enter');
        await page.waitForTimeout(1500);
    };

    // ── CAMINO 1 · el boton «−» ────────────────────────────────────────────────
    console.log('\nCAMINO 1 · el boton «−» hasta cruzar el minimo');
    const bajar = tarjeta.locator(`[data-testid="qty-${C}-0"]`).locator('xpath=preceding-sibling::button[1]');
    for (let i = 0; i < 40 && !(await dialogo.count()); i++) {
        await bajar.click({ timeout: 5000 }).catch(() => {});
        await page.waitForTimeout(260);
    }
    console.log('   ¿pregunta?', (await dialogo.count()) ? 'SI' : 'NO');
    if (await dialogo.count()) {
        console.log('   ', (await dialogo.innerText()).replace(/\n+/g, ' · '));
        await page.screenshot({ path: path.join(__dirname, '_nutricion_2608', 'p129-menos.jpg'), type: 'jpeg', quality: 70 });
        await page.locator('[data-testid="confirm-cancel"]').click();
        await page.waitForTimeout(1500);
        console.log('   digo que NO -> ingredientes:', await cuantos());
    }

    // ── CAMINO 2 · escribir 0 a mano ───────────────────────────────────────────
    console.log('\nCAMINO 2 · escribir 0 a mano');
    await escribir(0);
    console.log('   ¿pregunta?', (await dialogo.count()) ? 'SI' : 'NO');
    if (await dialogo.count()) {
        console.log('   ', (await dialogo.innerText()).replace(/\n+/g, ' · '));
        await page.locator('[data-testid="confirm-cancel"]').click();
        await page.waitForTimeout(1500);
        console.log('   digo que NO -> ingredientes:', await cuantos());
        await escribir(0);
        await page.locator('[data-testid="confirm-ok"]').click();
        await page.waitForTimeout(2000);
        console.log('   digo que SI -> ingredientes:', await cuantos());
    }
    await page.screenshot({ path: path.join(__dirname, '_nutricion_2608', 'p129-final.jpg'), type: 'jpeg', quality: 70 });
    await nav.close();
})();
