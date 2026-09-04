/**
 * LAS CAPTURAS DE LA REGLA ÚNICA (3-09-2026), a 390 y a 1280.
 *
 * Cuatro sitios que hablan del mismo día y tenían que decir el mismo número:
 * Inicio (el global y la fila de la comida), la cabecera de Nutrición, la comida abierta y
 * la plegada, y Mi semana.
 *
 * Uso:  node _guia/_capturas_una_regla_0309.js
 */
const fs = require('fs');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const CARPETA = '_guia/_una_regla_redondeo';
if (!fs.existsSync(CARPETA)) fs.mkdirSync(CARPETA, { recursive: true });

(async () => {
    const r = await fetch(`${API}/api/auth/login`, { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: CUENTA, password: CLAVE }) });
    const TOKEN = (await r.json()).access_token;
    if (!TOKEN) { console.log('no he podido entrar'); return; }

    const nav = await chromium.launch();
    for (const [ancho, alto, etiqueta] of [[390, 1500, '390'], [1280, 1400, '1280']]) {
        const p = await (await nav.newContext({
            viewport: { width: ancho, height: alto }, deviceScaleFactor: 2 })).newPage();
        await p.goto(APP, { waitUntil: 'domcontentloaded' });
        await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, TOKEN);

        await p.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
        await p.waitForTimeout(12000);
        for (let i = 0; i < 4; i++) {
            const s = p.locator('[data-testid="recorrido-saltar"]');
            if (!(await s.count())) break;
            await s.click({ force: true }).catch(() => {});
            await p.waitForTimeout(900);
        }
        await p.screenshot({ path: `${CARPETA}/A_inicio_${etiqueta}.png`, fullPage: true });

        await p.goto(`${APP}/dashboard/nutrition`, { waitUntil: 'networkidle' }).catch(() => {});
        await p.waitForTimeout(14000);
        await p.screenshot({ path: `${CARPETA}/B_nutricion_${etiqueta}.png`, fullPage: true });

        await p.goto(`${APP}/dashboard/semana`, { waitUntil: 'networkidle' }).catch(() => {});
        await p.waitForTimeout(9000);
        await p.screenshot({ path: `${CARPETA}/C_mi_semana_${etiqueta}.png`, fullPage: true });
        console.log(`  ${etiqueta} listo`);
    }
    await nav.close();
    console.log(`capturas en ${CARPETA}`);
})();
