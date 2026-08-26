/**
 * La pantalla de Nutricion a 390 px (artifact del 25-08, parte 3).
 * Uso:  node _guia/_nutricion_movil_2608.js [cuenta]
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const APP = 'http://localhost:3000';
const API = 'http://localhost:8000';
const SALIDA = path.join(__dirname, '_nutricion_2608');
const CUENTAS = {
    demo: { email: 'clientedemo@test.com', password: 'demo123' },
    admin: { email: 'francisco@test.com', password: 'demo123' },
};

(async () => {
    const quien = process.argv[2] || 'admin';
    const ancho = Number(process.argv[3]) || 390;
    fs.mkdirSync(SALIDA, { recursive: true });
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 900 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();

    const r = await page.request.post(`${API}/api/auth/login`, { data: CUENTAS[quien] });
    if (!r.ok()) throw new Error(`login ${quien}: ${r.status()}`);
    const { access_token, token } = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, access_token || token);

    await page.goto(`${APP}/dashboard/nutrition`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(5000);
    const saltar = page.getByRole('button', { name: /saltar/i }).first();
    if (await saltar.count()) { await saltar.click().catch(() => {}); await page.waitForTimeout(1500); }

    const datos = await page.evaluate(() => {
        const t = (s) => (document.querySelector(s)?.textContent || '').trim();
        return {
            numeros: ['P', 'H', 'G'].map((k) => ({
                numero: t(`[data-testid="dia-${k}"] .numero-grande`),
                palabra: t(`[data-testid="dia-palabra-${k}"]`),
                punto: !!document.querySelector(`[data-testid="dia-punto-${k}"]`),
                barra: document.querySelector(`[data-testid="dia-barra-${k}"]`)?.style.width || null,
            })),
            pie: t('[data-testid="dia-pie"]'),
            titularViejo: !!document.querySelector('[data-testid="dia-titular"]'),
            escritorioViejo: !!document.querySelector('[data-testid="dia-escritorio-P"]'),
        };
    });
    console.log(JSON.stringify(datos, null, 1));
    await page.screenshot({ path: path.join(SALIDA, `${quien}-${ancho}.jpg`), type: 'jpeg', quality: 70 });
    await nav.close();
})();
