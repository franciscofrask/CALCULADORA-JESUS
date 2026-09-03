/**
 * LOS TRES PRIMEROS DEL VIDEO DE JESUS Y GONZALO.
 *
 *   16:06  al pulsar una comida en Inicio se entra EN ESA COMIDA
 *   11:59  las verduras dicen «No aporta macros», no «sin macros»
 *   10:59  el letrero de cuadrar no habla de quitar cuando lo que pasa es que falta
 */
const { chromium } = require('playwright');
const APP = 'http://localhost:3000', API = 'http://127.0.0.1:8000';

(async () => {
    const t = await fetch(`${API}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'francisco@test.com', password: 'demo123' }),
    }).then(r => r.json()).then(r => r.access_token);

    const nav = await chromium.launch();
    const p = await (await nav.newContext({
        viewport: { width: 390, height: 1400 }, locale: 'es-ES', timezoneId: 'Europe/Madrid',
    })).newPage();
    await p.goto(APP, { waitUntil: 'domcontentloaded' });
    await p.evaluate(tk => { localStorage.clear(); localStorage.setItem('token', tk); }, t);

    let ok = 0, mal = 0;
    const di = (que, bien, detalle = '') => {
        console.log(`${bien ? 'OK  ' : 'MAL '} ${que}${detalle ? '  ' + detalle : ''}`);
        bien ? ok++ : mal++;
    };

    // ── 16:06 · cada comida aterriza en la suya ──
    await p.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' });
    await p.waitForTimeout(9000);
    for (let i = 0; i < 4; i++) {
        const s = p.locator('[data-testid="recorrido-saltar"]');
        if (!(await s.count())) break;
        await s.click({ force: true }).catch(() => { });
        await p.waitForTimeout(700);
    }
    const filas = await p.locator('[data-testid^="comida-hoy-"]').evaluateAll(
        l => l.map(e => e.getAttribute('data-testid').replace('comida-hoy-', '')));
    console.log(`comidas en Inicio: ${filas.join(', ')}`);
    for (const k of filas.slice(0, 4)) {
        await p.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' });
        await p.waitForTimeout(4500);
        await p.locator(`[data-testid="comida-hoy-${k}"] button`).nth(1).click({ force: true });
        await p.waitForTimeout(3500);
        const url = p.url();
        di(`pulsar ${k} en Inicio lleva a ${k}`, url.includes(`comida=${k}`), url.split('/dashboard')[1]);
    }

    // ── 11:59 · «No aporta macros» ──
    await p.goto(`${APP}/dashboard/nutrition`, { waitUntil: 'networkidle' });
    await p.waitForTimeout(9000);
    const cuerpo = (await p.locator('body').innerText()).replace(/\s+/g, ' ');
    di('no queda ni un «sin macros» en la pantalla', !/sin macros/i.test(cuerpo));

    await p.screenshot({ path: '_guia/_video_bloque1.png', fullPage: true });
    console.log(`\n${ok} bien, ${mal} mal`);
    await nav.close();
})();
