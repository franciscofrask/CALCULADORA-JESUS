/**
 * El buscador de alimentos (puntos 137 a 143 de la parte 4).
 * Uso:  node _guia/_buscador_2608.js [ancho] [busqueda]
 */
const { chromium } = require('playwright');
const path = require('path');
const APP = 'http://localhost:3000';
const API = 'http://127.0.0.1:8000';

(async () => {
    const ancho = Number(process.argv[2]) || 390;
    const q = process.argv[3] || 'almendras';
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 1100 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: 'francisco@test.com', password: 'demo123' } });
    const { access_token, token } = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, access_token || token);
    await page.goto(`${APP}/dashboard/foods`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(5000);
    const saltar = page.getByRole('button', { name: /saltar/i }).first();
    if (await saltar.count()) { await saltar.click().catch(() => {}); await page.waitForTimeout(1200); }

    console.log('CABECERA:');
    console.log(await page.evaluate(() => {
        const h = document.querySelector('h1')?.parentElement?.parentElement;
        return (h?.innerText || '').split('\n').filter(Boolean).slice(0, 6).map(l => '  ' + l).join('\n');
    }));

    await page.locator('input[type="text"]').first().fill(q);
    await page.waitForTimeout(1500);
    console.log('\nRESULTADOS:');
    console.log(await page.evaluate(() => [...document.querySelectorAll('[data-testid="alimento"]')]
        .slice(0, 4).map(c => '  — ' + c.innerText.replace(/\n+/g, ' · ')).join('\n')));

    const tramos = page.locator('[data-testid^="tramos-"]').first();
    if (await tramos.count()) {
        await tramos.click();
        await page.waitForTimeout(600);
        console.log('\nAL ABRIRLO:');
        console.log(await page.evaluate(() => {
            const d = document.querySelector('[data-testid^="tramos-abiertos-"]');
            return d ? '  ' + d.innerText.replace(/\n+/g, ' · ') : '  (no abre)';
        }));
    } else { console.log('\n(este alimento no lleva punto)'); }
    await page.screenshot({ path: path.join(__dirname, '_nutricion_2608', `buscador-${ancho}.jpg`), type: 'jpeg', quality: 70 });
    await nav.close();
})();
