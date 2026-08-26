/**
 * 135 · EL BUSCADOR DE DENTRO DE LA COMIDA NO APLICABA LA CALIBRACION.
 *
 * «Añades 100 g de almendras y la proteina no se mueve; al guardar, pasa a contar los 23 g.»
 * Lo que se comprueba: que el numero que enseña la ventana al añadir es EL MISMO que queda
 * en la comida al guardar, sea cual sea el tramo en el que este el dia.
 *
 * Uso:  node _guia/_p135_calibracion_al_anadir.js [comida] [alimento]
 */
const { chromium } = require('playwright');
const path = require('path');
const APP = 'http://localhost:3000';
const API = 'http://127.0.0.1:8000';

const numDe = (t, letra) => {
    const m = new RegExp(`([\d,\.]+)\s*${letra}\b`).exec(t || '');
    return m ? m[1].replace('.', ',') : null;
};

(async () => {
    const C = process.argv[2] || 'C1';
    const busca = process.argv[3] || 'Almendras';
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
    const crear = page.getByRole('button', { name: /^Crear el día$/i }).first();
    if (await crear.count()) { await crear.click(); await page.waitForTimeout(6000); }

    // Hay dos juegos de tarjetas (movil y escritorio) y solo uno se ve.
    const tarjeta = page.locator(`[data-testid="meal-card-${C}"]`).filter({ visible: true }).first();
    await tarjeta.waitFor({ timeout: 25000 });
    await tarjeta.locator('button').first().click();
    await page.waitForTimeout(3000);

    const abrir = page.locator(`[data-testid="build-meal-${C}"]`).first();
    if (await abrir.count()) await abrir.click();
    else await page.getByRole('button', { name: /Añadir ingrediente/i }).first().click();
    const caja = page.locator('input[placeholder="Buscar alimento..."]');
    await caja.waitFor({ timeout: 15000 });
    await caja.fill(busca);
    await page.waitForSelector('[data-testid^="food-item-"]', { timeout: 20000 });
    await page.waitForTimeout(1800);

    const fila = page.locator('[data-testid^="food-item-"]')
        .filter({ has: page.locator('div', { hasText: new RegExp(`^${busca}$`) }) }).first();
    if (!(await fila.count())) { console.log(`(no aparece la ficha «${busca}» a secas)`); await nav.close(); return; }
    const textoFila = (await fila.innerText()).replace(/\n+/g, ' · ');
    console.log('LA FILA DE LA VENTANA:   ' + textoFila);
    const pFila = numDe(textoFila, 'g') && /P=([\d,\.]+)/.exec(textoFila);

    await fila.click();
    await page.waitForTimeout(3500);
    const barras = await page.evaluate(() => {
        const t = document.querySelector('[role="dialog"]')?.innerText || '';
        const i = t.indexOf('Proteína');
        return i >= 0 ? t.slice(i, i + 110).replace(/\n+/g, ' · ') : '(no se ven)';
    });
    console.log('LAS BARRAS DE LA VENTANA: ' + barras);

    await page.locator('[data-testid="save-build-meal"]').click();
    await page.waitForTimeout(9000);
    const linea = await page.evaluate((c) => {
        const card = document.querySelector(`[data-testid="meal-card-${c}"]`);
        return [...card.querySelectorAll('[data-testid^="qty-"]')].map((q) => {
            let f = q.parentElement;
            while (f && !f.querySelector('[data-testid^="remove-"]')) f = f.parentElement;
            return (f?.innerText || '').replace(/\n+/g, ' · ');
        }).join('\n   ');
    }, C);
    console.log('\nLA COMIDA YA GUARDADA:\n   ' + linea);

    const pGuardado = /([\d,\.]+)P\b/.exec(linea);
    if (pFila && pGuardado) {
        const a = pFila[1].replace('.', ','), b = pGuardado[1].replace('.', ',');
        console.log(`\n  proteina en la ventana: ${a}   ·   ya guardada: ${b}   ->  ${a === b ? 'COINCIDEN' : 'NO COINCIDEN'}`);
    }
    await page.screenshot({ path: path.join(__dirname, '_nutricion_2608', 'p135-guardado.jpg'), type: 'jpeg', quality: 70, fullPage: true });
    await nav.close();
})();
