/**
 * Barrido: que ningun boton visible de Nutricion tenga el texto partido en varias lineas.
 * «Lo hago yo» salia en tres, una por palabra, en la rejilla de la comida vacia (26-08).
 *
 * Uso:  node _guia/_botones_partidos.js [ancho]
 */
const { chromium } = require('playwright');
const APP = 'http://localhost:3000';
const API = 'http://127.0.0.1:8000';

(async () => {
    const ancho = Number(process.argv[2]) || 390;
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 1400 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: 'francisco@test.com', password: 'demo123' } });
    const { access_token, token } = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, access_token || token);
    await page.goto(`${APP}/dashboard/nutrition`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(6500);
    const saltar = page.getByRole('button', { name: /saltar/i }).first();
    if (await saltar.count()) { await saltar.click().catch(() => {}); await page.waitForTimeout(1500); }

    // Se abren todas las comidas, que es donde viven los botones de rejilla.
    for (const c of ['C1', 'C2', 'C3', 'C4', 'Intra', 'Post']) {
        const t = page.locator(`[data-testid="meal-card-${c}"]`).filter({ visible: true }).first();
        if (await t.count()) { await t.locator('button').first().click().catch(() => {}); await page.waitForTimeout(900); }
    }
    await page.waitForTimeout(2500);

    const malos = await page.evaluate(() => {
        const fuera = [];
        for (const b of document.querySelectorAll('button')) {
            const r = b.getBoundingClientRect();
            if (r.width < 2 || r.height < 2) continue;              // no visible
            const t = [...b.childNodes].find((n) => n.nodeType === 3 && n.textContent.trim());
            if (!t) continue;
            const rango = document.createRange();
            rango.selectNodeContents(t);
            const lineas = rango.getClientRects().length;
            if (lineas > 1) fuera.push(`${t.textContent.trim().slice(0, 26)} -> ${lineas} lineas, boton de ${Math.round(r.width)}px`);
        }
        return [...new Set(fuera)];
    });
    console.log(`A ${ancho} px, botones con el texto partido: ${malos.length}`);
    malos.forEach((m) => console.log('   ' + m));
    await nav.close();
})();
