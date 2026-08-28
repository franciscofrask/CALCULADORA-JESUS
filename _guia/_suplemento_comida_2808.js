/**
 * EL SUPLEMENTO DEBAJO DE LA COMIDA · punto 202 (parte 6 del 28-08).
 *
 *   «+ Creatina» va en GRIS y con una › al final, no en el naranja de la marca.
 *   Y sigue llevando a Suplementos, que es lo que pedía el 190.
 *
 * Se comprueba en las DOS pantallas donde sale: Nutrición e Inicio.
 *
 * Monta un día con suplementos pautados y lo repone todo al terminar.
 *
 * Uso:  node _guia/_suplemento_comida_2808.js [ancho]
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const ADMIN = process.env.ADMIN || 'francisco@test.com';
const ADMIN_CLAVE = process.env.ADMIN_CLAVE || 'demo123';
const POLLO = 498, ARROZ = 1657, ACEITE = 3;

let malas = 0;
const ok = (b) => { if (!b) malas++; return b ? 'BIEN' : 'MAL '; };
const esNaranja = (c) => /255,\s*(103|90)/.test(c || '');

const SUPS = [
    { titulo: 'Creatina', cuando: 'Todos los días, entrenes o no', cuanto: '5 g', comida: 'C3' },
    { titulo: 'Omega 3', cuando: 'Con una comida que lleve grasa', cuanto: '2 cápsulas', comida: 'C4' },
];

const quitarRecorrido = async (page) => {
    for (let i = 0; i < 4; i++) {
        const s = page.locator('[data-testid="recorrido-saltar"]');
        if (!(await s.count())) break;
        await s.click({ force: true }).catch(() => {});
        await page.waitForTimeout(1200);
    }
    await page.locator('[data-testid="recorrido-overlay"]').waitFor({ state: 'detached', timeout: 8000 }).catch(() => {});
    await page.waitForTimeout(1000);
};

(async () => {
    const ancho = Number(process.argv[2]) || 390;
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 1100 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();

    const tok = (await (await page.request.post(`${API}/api/auth/login`, { data: { email: CUENTA, password: CLAVE } })).json()).access_token;
    const cab = { Authorization: `Bearer ${tok}` };
    const cabAdmin = { Authorization: `Bearer ${(await (await page.request.post(`${API}/api/auth/login`, { data: { email: ADMIN, password: ADMIN_CLAVE } })).json()).access_token}` };
    const yo = await (await page.request.get(`${API}/api/auth/me`, { headers: cab })).json();
    const lista = await (await page.request.get(`${API}/api/admin/clients?include_incomplete=true`, { headers: cabAdmin, timeout: 90000 })).json();
    const cli = (Array.isArray(lista) ? lista : []).find(c => ((c.user || {}).email || '').toLowerCase() === yo.email.toLowerCase());

    const d = new Date();
    const HOY = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    console.log(`\n=== EL SUPLEMENTO DEBAJO DE LA COMIDA · ${ancho} px ===\n`);

    const antes = await (await page.request.get(`${API}/api/diets/${HOY}`, { headers: cab })).json();
    const habia = !!antes.exists;
    const fichaAdmin = await (await page.request.get(`${API}/api/admin/clients/${cli.id}`, { headers: cabAdmin })).json().catch(() => ({}));
    const antesProt = (fichaAdmin || {}).supplement_protocol || null;
    const habiaProt = !!(antesProt && (antesProt.versiones || []).length);

    await page.request.delete(`${API}/api/diets/${HOY}`, { headers: cab });
    await page.request.post(`${API}/api/diets`, { headers: cab,
        data: { fecha: HOY, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 0,
                opcion_peri: 'intra_post', comidas: {
                    C3: { alimentos: [{ alimento_id: POLLO, cantidad_g: 120 }, { alimento_id: ARROZ, cantidad_g: 60 }] },
                    C4: { alimentos: [{ alimento_id: POLLO, cantidad_g: 100 }, { alimento_id: ACEITE, cantidad_g: 10 }] },
                } } });
    await page.request.post(`${API}/api/admin/supplements/save?client_id=${cli.id}`, {
        headers: cabAdmin, data: { actual: SUPS, actual_fecha: HOY, siguiente: [] } });

    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);

    // ── Nutrición ───────────────────────────────────────────────────────────
    await page.goto(`${APP}/dashboard/nutrition?date=${HOY}`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(9000);
    await quitarRecorrido(page);

    // En el ordenador la vista de siempre es lista + detalle, y el suplemento sale en la
    // comida ABIERTA: hay que abrir la que lo lleva. En el móvil salen todas seguidas.
    const visible = async (k) => {
        const todos = await page.locator(`[data-testid="suplementos-comida-${k}"]`).all();
        for (const e of todos) if (await e.isVisible().catch(() => false)) return e;
        return null;
    };
    for (const k of ['C3', 'C4']) {
        if (!(await visible(k))) {
            await page.locator(`[data-testid="meal-select-${k}"]`).first().click().catch(() => {});
            await page.waitForTimeout(2500);
        }
        const e = await visible(k);
        if (!e) { console.log(`202 · Nutrición ${k}: NO SE VE   ${ok(false)}`); continue; }
        const txt = (await e.innerText()).replace(/\s+/g, ' ').trim();
        const color = await e.evaluate(el => getComputedStyle(el).color);
        const flecha = await e.locator('svg').count();
        console.log(`202 · Nutrición ${k}: «${txt}» · ${color}`);
        console.log(`      en gris, no en naranja           ${ok(!esNaranja(color))}`);
        console.log(`      con su flecha al final           ${ok(flecha > 0)}`);
    }
    await page.screenshot({ path: `_guia/_suplemento_nutricion_${ancho}.png`, fullPage: true });

    // Y lleva a Suplementos.
    const paraTocar = (await visible('C4')) || (await visible('C3'));
    if (paraTocar) await paraTocar.click().catch(() => {});
    await page.waitForTimeout(4000);
    console.log(`202 · y desde ahí se llega a Suplementos -> ${page.url().split('/dashboard')[1]}   ${ok(/supplements/.test(page.url()))}`);

    // ── Inicio ──────────────────────────────────────────────────────────────
    await page.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(9000);
    await quitarRecorrido(page);
    for (const k of ['C3', 'C4']) {
        const e = page.locator(`[data-testid="suplementos-${k}"]`).first();
        if (!(await e.count())) { console.log(`202 · Inicio ${k}: NO SALE   ${ok(false)}`); continue; }
        const txt = (await e.innerText()).replace(/\s+/g, ' ').trim();
        const color = await e.evaluate(el => getComputedStyle(el).color);
        const flecha = await e.locator('svg').count();
        console.log(`202 · Inicio ${k}: «${txt}» · ${color}`);
        console.log(`      en gris, no en naranja           ${ok(!esNaranja(color))}`);
        console.log(`      con su flecha al final           ${ok(flecha > 0)}`);
    }
    await page.screenshot({ path: `_guia/_suplemento_inicio_${ancho}.png`, fullPage: true });

    // ── Se repone ───────────────────────────────────────────────────────────
    await nav.close();
    const limpio = await chromium.launch();
    const p2 = await (await limpio.newContext()).newPage();
    await p2.request.delete(`${API}/api/diets/${HOY}`, { headers: cab });
    if (habia) {
        await p2.request.post(`${API}/api/diets`, { headers: cab,
            data: { fecha: HOY, tipo_dia: antes.tipo_dia, num_comidas: antes.num_comidas,
                    momento_entreno: antes.momento_entreno, opcion_peri: antes.opcion_peri, comidas: antes.comidas } });
    }
    if (habiaProt) {
        await p2.request.post(`${API}/api/admin/supplements/save?client_id=${cli.id}`, { headers: cabAdmin,
            data: { actual: antesProt.actual || [], actual_fecha: antesProt.actual_fecha || HOY, siguiente: antesProt.siguiente || [] } });
    } else {
        await p2.request.delete(`${API}/api/admin/supplements/version/${HOY}?client_id=${cli.id}`, { headers: cabAdmin });
    }
    await limpio.close();
    console.log(`\n${malas ? malas + ' MAL' : 'todo BIEN'} · todo repuesto · capturas -> _guia/_suplemento_{nutricion,inicio}_${ancho}.png`);
    process.exit(malas ? 1 : 0);
})();
