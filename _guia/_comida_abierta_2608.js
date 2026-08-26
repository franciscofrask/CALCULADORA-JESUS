/**
 * Una comida abierta (puntos 120 a 123 de la parte 4): el desglose siempre visible, con
 * decimales y con el suelo de 1 g.
 * Uso:  node _guia/_comida_abierta_2608.js [ancho] [comida]
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const APP = 'http://localhost:3000';
const API = 'http://localhost:8000';
const SALIDA = path.join(__dirname, '_nutricion_2608');

(async () => {
    const ancho = Number(process.argv[2]) || 390;
    const comida = process.argv[3] || 'C3';
    fs.mkdirSync(SALIDA, { recursive: true });
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 1000 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: 'francisco@test.com', password: 'demo123' } });
    const { access_token, token } = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, access_token || token);
    await page.goto(`${APP}/dashboard/nutrition`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(5000);
    const saltar = page.getByRole('button', { name: /saltar/i }).first();
    if (await saltar.count()) { await saltar.click().catch(() => {}); await page.waitForTimeout(1200); }

    // Abrir la comida.
    const cab = page.locator(`[data-testid="meal-card-${comida}"] button`).first();
    if (await cab.count()) { await cab.click().catch(() => {}); await page.waitForTimeout(1500); }

    console.log(JSON.stringify(await page.evaluate((c) => {
        const t = (s) => (document.querySelector(s)?.textContent || '').trim();
        return {
            macros: ['P', 'H', 'G'].map((k) => ({
                numero: t(`[data-testid="comida-macro-${c}-${k}"] .numero-grande`),
                palabra: t(`[data-testid="comida-palabra-${c}-${k}"]`),
            })),
            objetivo: t(`[data-testid="objetivo-${c}"]`),
            verDetalles: !!document.querySelector(`[data-testid="ver-detalles-${c}"]`),
            estadoEnCabecera: !!document.querySelector(`[data-testid="estado-comida-${c}"]`),
        };
    }, comida), null, 1));
    await page.screenshot({ path: path.join(SALIDA, `comida-${ancho}.jpg`), type: 'jpeg', quality: 70, fullPage: true });

    // Los controles (puntos 124 a 128).
    console.log('controles:', JSON.stringify(await page.evaluate((c) => {
        const t = (s) => (document.querySelector(s)?.textContent || '').trim();
        const card = document.querySelector(`[data-testid="meal-card-${c}"]`);
        return {
            ajuste: (card?.innerText || '').includes('AJUSTE DE CANTIDADES'),
            modoViejo: (card?.innerText || '').includes('MODO DE CÁLCULO'),
            explicacion: t(`[data-testid="ajuste-explicacion-${c}"]`),
            cuadrarAncho: !!document.querySelector(`[data-testid="cuadrar-${c}"]`),
            fraseCuadrar: (card?.innerText || '').includes('sin pasarme de tus macros'),
            leyendaVieja: (card?.innerText || '').includes('prioridad'),
            menu: !!card?.querySelector('[data-testid="menu-pantalla"]'),
            flechas: card.querySelectorAll('[data-testid^="reorder-"]').length,
        };
    }, comida)));

    // Y el modo ordenar.
    await page.locator(`[data-testid="meal-card-${comida}"] [data-testid="menu-pantalla"]`).click();
    await page.waitForTimeout(500);
    console.log('menu:', JSON.stringify(await page.evaluate(() =>
        [...document.querySelectorAll('[role="menuitem"]')].map(b => b.innerText.trim()))));
    await nav.close();
})();
