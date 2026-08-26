/**
 * Comprobacion de PRODUCCION tras el deploy del 26-08: que el buscador de alimentos
 * enseña lo nuevo. Se entra con una cuenta del equipo y solo se LEE.
 *
 * Uso:  node _guia/_comprobar_prod_2608.js <email> <clave>
 */
const { chromium } = require('playwright');
const path = require('path');
const APP = 'https://12en12app.jesusgallegopt.com';

(async () => {
    const email = process.argv[2], clave = process.argv[3];
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: 390, height: 1300 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    const r = await page.request.post(`${APP}/api/auth/login`, { data: { email, password: clave } });
    if (!r.ok()) { console.log('  no entra:', r.status()); await nav.close(); return; }
    const { access_token, token } = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, access_token || token);
    await page.goto(`${APP}/dashboard/foods`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(6000);
    const saltar = page.getByRole('button', { name: /saltar/i }).first();
    if (await saltar.count()) { await saltar.click().catch(() => {}); await page.waitForTimeout(1500); }

    console.log('CABECERA:');
    console.log((await page.evaluate(() => {
        const h = document.querySelector('h1')?.parentElement?.parentElement;
        return (h?.innerText || '').split('\n').filter(Boolean).slice(0, 5).map(l => '  ' + l).join('\n');
    })));

    await page.locator('input[type="text"]').first().fill('almendras');
    await page.waitForTimeout(2500);
    console.log('\nPRIMER RESULTADO:');
    console.log('  ' + (await page.evaluate(() => {
        const c = document.querySelector('[data-testid="alimento"]');
        return c ? c.innerText.replace(/\n+/g, ' · ') : '(sin resultados)';
    })));
    const tramos = page.locator('[data-testid^="tramos-"]').first();
    if (await tramos.count()) {
        await tramos.click();
        await page.waitForTimeout(700);
        console.log('\nAL ABRIRLO:');
        console.log('  ' + (await page.evaluate(() => {
            const d = document.querySelector('[data-testid^="tramos-abiertos-"]');
            return d ? d.innerText.replace(/\n+/g, ' · ') : '(no abre)';
        })));
    }
    await page.screenshot({ path: path.join(__dirname, '_nutricion_2608', 'prod-buscador.jpg'), type: 'jpeg', quality: 70 });
    await nav.close();
})();
