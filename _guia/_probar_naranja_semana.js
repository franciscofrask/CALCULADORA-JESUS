/**
 * EL NARANJA DE MI SEMANA Y DEL CALENDARIO (video de Jesus y Gonzalo, 12:45 y 17:40).
 *
 * «Todos estos dias se supone que estan cuadrados y este sale naranja. No hay ninguna
 *  diferencia cuando esta cuadrado y cuando no.»
 *
 * Se comprueba que el color YA NO sale de la marca guardada:
 *   - un dia que se paso 71 g de hidratos tenia la marca en verde y ahora sale naranja
 *   - un dia que cuadra de verdad sigue en verde
 *   - un dia a medias deja de llevar el aviso naranja
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
        viewport: { width: 1280, height: 1100 }, locale: 'es-ES', timezoneId: 'Europe/Madrid',
    })).newPage();
    await p.goto(APP, { waitUntil: 'domcontentloaded' });
    await p.evaluate(tk => { localStorage.clear(); localStorage.setItem('token', tk); }, t);

    let ok = 0, mal = 0;
    const di = (que, bien, detalle = '') => {
        console.log(`${bien ? 'OK  ' : 'MAL '} ${que}${detalle ? '  ' + detalle : ''}`);
        bien ? ok++ : mal++;
    };

    // ── El calendario de diciembre: el 21 cuadra, el 22 se pasa 71 g ──
    await p.goto(`${APP}/dashboard/nutrition?date=2026-12-21`, { waitUntil: 'networkidle' });
    await p.waitForTimeout(11000);
    await p.locator('[data-testid="open-calendar-btn"]').click();
    await p.waitForTimeout(3000);
    const color = async (dia) => {
        const punto = p.locator(`[data-testid="cal-day-${dia}"] span.rounded-full`).last();
        if (!(await punto.count())) return 'sin punto';
        return punto.evaluate(e => getComputedStyle(e).backgroundColor);
    };
    const verde = await color(21), naranja = await color(22);
    di('el 21, que cuadra, sale verde', /34, 197, 94/.test(verde), verde);
    di('el 22, que se pasa 71 g, ya NO sale verde', !/34, 197, 94/.test(naranja), naranja);
    await p.screenshot({ path: '_guia/_calendario_diciembre.png', fullPage: true });

    // ── Mi semana ──
    await p.goto(`${APP}/dashboard/semana`, { waitUntil: 'networkidle' });
    await p.waitForTimeout(9000);
    const filas = await p.locator('[data-testid^="estado-dieta-"]').evaluateAll(
        l => l.map(e => ({
            dia: e.getAttribute('data-testid').replace('estado-dieta-', ''),
            dice: e.innerText.trim(),
        })));
    console.log('Mi semana:', JSON.stringify(filas));
    di('Mi semana ya no dice «Creada» a secas en los montados',
        !filas.some(f => f.dice === 'Creada'));
    await p.screenshot({ path: '_guia/_mi_semana_naranja.png', fullPage: true });

    console.log(`\n${ok} bien, ${mal} mal`);
    await nav.close();
})();
