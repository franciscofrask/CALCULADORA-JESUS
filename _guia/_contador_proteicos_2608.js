/**
 * EL CONTADOR DE LA FAMILIA DENTRO DE LA COMIDA (26-08).
 *
 * Los cereales y panes proteicos pasan la puerta del tercio pero no tienen tramo: su
 * proteina cuenta entera desde el primer gramo. El contador les decia «su proteina todavia
 * no te cuenta · con 50 g te cuenta la mitad». Aqui se comprueba que ya no sale, que a los
 * que si crecen (anacardos) les sigue saliendo, y que a los que no cuentan nunca (nueces)
 * les sale su frase.
 *
 * Uso:  node _guia/_contador_proteicos_2608.js
 */
const { chromium } = require('playwright');
const path = require('path');
const APP = 'http://localhost:3000';
const API = 'http://127.0.0.1:8000';
const C = 'C3';
const BUSCAR = ['Protein Granola caramelo', 'Anacardos', 'Nueces'];

(async () => {
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: 390, height: 1400 }, deviceScaleFactor: 2 });
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
    await page.waitForTimeout(1500);

    // Los tres de una tanda: el modal acumula y se guarda al final.
    await page.getByRole('button', { name: /Añadir ingrediente/i }).first().click();
    const caja = page.locator('input[placeholder="Buscar alimento..."]');
    await caja.waitFor({ timeout: 15000 });
    for (const q of BUSCAR) {
        await caja.fill(q);
        await page.waitForSelector('[data-testid^="food-item-"]', { timeout: 20000 });
        await page.waitForTimeout(900);
        const fila = page.locator('[data-testid^="food-item-"]').first();
        console.log('puesto:', (await fila.innerText()).split('\n')[0].slice(0, 52));
        await fila.click();
        await page.waitForTimeout(1200);
    }
    await page.locator('[data-testid="save-build-meal"]').click();
    // La calibracion se pide con 300 ms de retardo y viaja al servidor.
    await page.waitForTimeout(6000);

    console.log('\nLINEAS DE LA COMIDA:');
    console.log(await page.evaluate((c) => {
        const card = document.querySelector(`[data-testid="meal-card-${c}"]`);
        return [...card.querySelectorAll('[data-testid^="qty-"]')].map((q) => {
            let fila = q.parentElement;
            while (fila && !fila.querySelector('[data-testid^="remove-"]')) fila = fila.parentElement;
            const cont = fila?.querySelector('[data-testid^="contador-"]');
            const nombre = (fila?.innerText || '').split('\n')[0].slice(0, 30);
            return `  - ${nombre.padEnd(32)} contador: ${cont ? cont.innerText.trim() : '(ninguno)'}`;
        }).join('\n');
    }, C));
    await page.screenshot({ path: path.join(__dirname, '_nutricion_2608', 'contador-proteicos-390.jpg'), type: 'jpeg', quality: 70, fullPage: true });
    await nav.close();
})();
