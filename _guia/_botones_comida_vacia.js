/**
 * Los botones de una comida vacia en el movil: «Lo hago yo» se parte por palabra.
 * Uso:  node _guia/_botones_comida_vacia.js [ancho] [comida]
 */
const { chromium } = require('playwright');
const path = require('path');
const APP = 'http://localhost:3000';
const API = 'http://127.0.0.1:8000';

(async () => {
    const ancho = Number(process.argv[2]) || 390;
    const C = process.argv[3] || 'C1';
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 1400 }, deviceScaleFactor: 2 });
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

    console.log(`A ${ancho} px, los botones de la comida vacia ${C}:`);
    for (const texto of ['Sugiéreme un menú', 'Lo hago yo', 'Repetir', 'Favoritas']) {
        const b = tarjeta.locator('button', { hasText: texto }).filter({ visible: true }).first();
        if (!(await b.count())) { console.log(`   ${texto.padEnd(20)} (no esta)`); continue; }
        const m = await b.evaluate((el) => {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            // El texto va en un nodo suelto: se mide con un rango para saber si se parte.
            const rango = document.createRange();
            const t = [...el.childNodes].find((n) => n.nodeType === 3 && n.textContent.trim());
            let lineas = 1;
            if (t) { rango.selectNodeContents(t); lineas = rango.getClientRects().length; }
            return { w: Math.round(r.width), h: Math.round(r.height), px: s.paddingLeft, lineas };
        });
        const svg = await b.evaluate((el) => {
            const s = el.querySelector('svg');
            if (!s) return '(sin icono)';
            const r = s.getBoundingClientRect();
            return `${Math.round(r.width)}x${Math.round(r.height)}`;
        });
        console.log(`   ${texto.padEnd(20)} ancho ${String(m.w).padStart(3)}px  padding-x ${m.px}  texto en ${m.lineas} linea(s)${m.lineas > 1 ? ' <-- SE PARTE' : ''}  icono ${svg}${svg.startsWith('0x') ? ' <-- APLASTADO' : ''}`);
    }
    const zona = tarjeta.locator('button', { hasText: /Lo hago yo/ }).first();
    if (await zona.count()) {
        await zona.scrollIntoViewIfNeeded();
        await page.waitForTimeout(400);
        const caja = await zona.evaluate((b) => { const r = b.parentElement.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height }; });
        await page.screenshot({ path: path.join(__dirname, '_nutricion_2608', `botones-${ancho}.jpg`), type: 'jpeg', quality: 85, clip: caja });
    }
    await nav.close();
})();
