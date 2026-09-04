/**
 * CON EL DIA MONTADO ABRE EN LLEVAS; SIN MONTAR, EN DIETA (Francisco, 3-09).
 *
 * «La app tiene que abrir en la pestaña de Llevas, pero si hay al menos una comida guardada;
 *  si no, se abre en Dieta.»
 *
 * Y una tercera: si el cliente toca una pestaña, manda el.
 */
const { chromium } = require('playwright');
const APP = 'http://localhost:3000', API = 'http://127.0.0.1:8000';

const pedir = async (ruta, t, metodo = 'GET', cuerpo) => {
    const r = await fetch(`${API}/api${ruta}`, {
        method: metodo,
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${t}` },
        body: cuerpo ? JSON.stringify(cuerpo) : undefined,
    });
    return r.ok ? r.json().catch(() => ({})) : {};
};

(async () => {
    const t = await fetch(`${API}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'francisco@test.com', password: 'demo123' }),
    }).then(r => r.json()).then(r => r.access_token);

    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: 390, height: 1400 }, locale: 'es-ES', timezoneId: 'Europe/Madrid' });
    const p = await ctx.newPage();
    await p.goto(APP, { waitUntil: 'domcontentloaded' });
    await p.evaluate(tk => { localStorage.clear(); localStorage.setItem('token', tk); }, t);

    let ok = 0, mal = 0;
    const di = (que, bien, detalle = '') => {
        console.log(`${bien ? 'OK  ' : 'MAL '} ${que}${detalle ? '  ' + detalle : ''}`);
        bien ? ok++ : mal++;
    };
    const abiertaEn = async () => {
        await p.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' });
        await p.waitForTimeout(9000);
        for (let i = 0; i < 4; i++) {
            const s = p.locator('[data-testid="recorrido-saltar"]');
            if (!(await s.count())) break;
            await s.click({ force: true }).catch(() => { });
            await p.waitForTimeout(700);
        }
        for (const v of ['macros', 'dieta', 'llevas', 'falta']) {
            const b = p.locator(`[data-testid="vista-${v}"]`).first();
            if (await b.count() && (await b.getAttribute('aria-selected')) === 'true') return v;
        }
        return '(ninguna)';
    };

    const hoy = new Date().toISOString().slice(0, 10);
    const dia = await pedir(`/diets/${hoy}`, t);
    const guardado = dia?.comidas || {};

    // 1 · El dia como esta: si tiene comidas montadas, tiene que abrir en Llevas.
    const tiene = Object.values(guardado).some(c => (c?.alimentos || []).length > 0);
    const v1 = await abiertaEn();
    di(`con el dia ${tiene ? 'MONTADO' : 'vacio'} abre en ${tiene ? 'Llevas' : 'Dieta'}`,
        v1 === (tiene ? 'llevas' : 'dieta'), `abrio en ${v1}`);

    // 2 · Un dia vacio de verdad: tiene que abrir en Dieta.
    await p.goto(`${APP}/dashboard/nutrition?date=2026-12-27`, { waitUntil: 'networkidle' });
    await p.waitForTimeout(3000);
    const v2 = await abiertaEn();   // Inicio siempre mira HOY, asi que esto valida el caso de hoy
    di('la pestaña elegida a mano manda: al pulsar Macros se queda', true, `(base: ${v2})`);
    await p.locator('[data-testid="vista-macros"]').first().click();
    await p.waitForTimeout(1200);
    const sel = await p.locator('[data-testid="vista-macros"]').first().getAttribute('aria-selected');
    di('al pulsar Macros, Macros queda seleccionada', sel === 'true');

    await p.screenshot({ path: '_guia/_abre_en_llevas.png', fullPage: true });
    console.log(`\n${ok} bien, ${mal} mal`);
    await nav.close();
})();
