/**
 * El borde naranja del intra y el post en la lista de comidas del Inicio.
 * Se perdio al partir la fila para meter la casilla de marcar (commit 7e1e0f9).
 *
 * Uso:  node _guia/_borde_peri_2608.js
 */
const { chromium } = require('playwright');
const path = require('path');
const APP = 'http://localhost:3000';
const API = 'http://127.0.0.1:8000';

(async () => {
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: 390, height: 1500 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: 'francisco@test.com', password: 'demo123' } });
    const { access_token, token } = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, access_token || token);
    // Sin entreno no hay intra ni post, y el interruptor del dia vive en Nutricion.
    await page.goto(`${APP}/dashboard/nutrition`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(7000);
    const saltar0 = page.getByRole('button', { name: /saltar/i }).first();
    if (await saltar0.count()) { await saltar0.click().catch(() => {}); await page.waitForTimeout(1500); }
    const entreno = page.getByRole('button', { name: /^Entreno$/i }).first();
    if (await entreno.count()) { await entreno.click(); await page.waitForTimeout(5000); }

    await page.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(7000);
    const saltar = page.getByRole('button', { name: /saltar/i }).first();
    if (await saltar.count()) { await saltar.click().catch(() => {}); await page.waitForTimeout(1500); }
    // La pestaña de «Llevas», que es donde va la lista de comidas.
    const llevas = page.getByRole('button', { name: /llevas/i }).first();
    if (await llevas.count()) { await llevas.click(); await page.waitForTimeout(2500); }

    console.log('EL BORDE IZQUIERDO DE CADA FILA:');
    console.log(await page.evaluate(() => [...document.querySelectorAll('[data-testid^="comida-hoy-"]')]
        .map((f) => {
            const s = getComputedStyle(f);
            const nombre = (f.innerText || '').split('\n')[0].slice(0, 14);
            return `   ${nombre.padEnd(16)} ${s.borderLeftWidth.padStart(4)}  ${s.borderLeftColor}`;
        }).join('\n')));
    const fila = page.locator('[data-testid="comida-hoy-Intra"]');
    if (await fila.count()) {
        await fila.scrollIntoViewIfNeeded();
        await page.waitForTimeout(400);
        await fila.screenshot({ path: path.join(__dirname, '_nutricion_2608', 'borde-intra.jpg'), type: 'jpeg', quality: 85 });
    }
    await page.screenshot({ path: path.join(__dirname, '_nutricion_2608', 'borde-peri.jpg'), type: 'jpeg', quality: 72, fullPage: true });
    await nav.close();
})();
