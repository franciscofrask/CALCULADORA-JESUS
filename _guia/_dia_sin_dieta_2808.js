/**
 * EL DÍA QUE NO TIENE DIETA · los puntos 205 a 209 (parte 6 del 28-08).
 *
 *   205  «Guardado» no puede salir en un día vacío
 *   206  los tres ceros, sin color y sin punto
 *   207  el día, con su nombre entero arriba y en la tarjeta
 *   209  los tres caminos se quedan como están
 *
 * Mira el día vacío tal y como lo ve el cliente y, para no cargarse el aviso de guardado,
 * comprueba también que SÍ sale en cuanto el día tiene algo. Repone todo al terminar.
 *
 * Uso:  node _guia/_dia_sin_dieta_2808.js [ancho]     (390 móvil · 1280 ordenador)
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const POLLO = 498;

let malas = 0;
const ok = (b) => { if (!b) malas++; return b ? 'BIEN' : 'MAL '; };

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

    const rc = await page.request.post(`${API}/api/auth/login`, { data: { email: CUENTA, password: CLAVE } });
    const tok = (await rc.json()).access_token;
    const cab = { Authorization: `Bearer ${tok}` };

    const d = new Date();
    const HOY = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    console.log(`\n=== EL DÍA SIN DIETA · ${ancho} px · hoy ${HOY} ===\n`);

    const antes = await (await page.request.get(`${API}/api/diets/${HOY}`, { headers: cab })).json();
    const habia = !!antes.exists;
    // Vaciar de verdad: guardar con `comidas: {}` NO borra lo que ya hay (el guardado es
    // por campos), así que primero se tira el día y luego se crea vacío.
    const vaciar = async () => {
        await page.request.delete(`${API}/api/diets/${HOY}`, { headers: cab });
        await page.request.post(`${API}/api/diets`, { headers: cab,
            data: { fecha: HOY, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 0,
                    opcion_peri: 'intra_post', comidas: {} } });
    };

    await vaciar();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);
    await page.goto(`${APP}/dashboard/nutrition?date=${HOY}`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(9000);
    await quitarRecorrido(page);
    // El aviso de guardado sale con retardo: se le da tiempo a aparecer si va a hacerlo.
    await page.waitForTimeout(6000);

    console.log(`la pantalla del día vacío          ${ok((await page.locator('[data-testid="dia-vacio"]').count()) === 1)}`);

    // ── 205 · «Guardado» en un día vacío ────────────────────────────────────
    const leerAviso = async () => {
        const e = page.locator('[data-testid="estado-guardado"]');
        return (await e.count()) ? (await e.innerText()).trim() : '(no sale)';
    };
    const aviso = await leerAviso();
    console.log(`\n205 · el aviso de guardado dice         -> «${aviso}»`);
    console.log(`205 · sin «Guardado» con el día vacío   ${ok(!/guardad/i.test(aviso))}`);

    // ── 206 · los tres ceros, sin color ─────────────────────────────────────
    console.log('');
    for (const k of ['P', 'H', 'G']) {
        const punto = await page.locator(`[data-testid="dia-punto-${k}"]`).count();
        const pal = page.locator(`[data-testid="dia-palabra-${k}"]`).first();
        const texto = (await pal.innerText()).trim();
        const color = await pal.evaluate(el => getComputedStyle(el).color);
        const naranja = /255,\s*(90|103)/.test(color);
        const verde = /34,\s*197|22,\s*163/.test(color);
        console.log(`206 · ${k}: «${texto}» · ${color} · punto ${punto}   ${ok(!naranja && !verde && punto === 0)}`);
    }

    // ── 207 · el día, con su nombre entero en los dos sitios ────────────────
    const arriba = (await page.locator('[data-testid="open-calendar-btn"]').innerText()).trim();
    const tarjeta = (await page.locator('[data-testid="dia-vacio"] .caption').first().innerText()).trim();
    const largo = (t) => /\d{1,2} de [a-záéíóú]+/i.test(t) && !/\b\d{1,2} [A-Za-z]{3}\b/.test(t);
    console.log(`\n207 · arriba                            -> «${arriba}»   ${ok(largo(arriba))}`);
    console.log(`207 · en la tarjeta                     -> «${tarjeta}»   ${ok(largo(tarjeta))}`);
    const mesArriba = (arriba.match(/de ([a-záéíóú]+)/i) || [])[1];
    const mesTarjeta = (tarjeta.match(/de ([a-záéíóú]+)/i) || [])[1];
    console.log(`207 · el mismo día escrito igual        ${ok(Boolean(mesArriba) && mesArriba.toLowerCase() === (mesTarjeta || '').toLowerCase())}`);

    // ── 209 · los tres caminos ──────────────────────────────────────────────
    const caminos = [];
    for (const t of ['dia-vacio-crear', 'dia-vacio-favoritas', 'dia-vacio-repetir']) {
        if (await page.locator(`[data-testid="${t}"]`).count()) caminos.push(t);
    }
    console.log(`\n209 · los tres caminos, en su orden     -> ${caminos.length} de 3   ${ok(caminos.length === 3)}`);

    await page.screenshot({ path: `_guia/_dia_sin_dieta_${ancho}.png`, fullPage: true });

    // ── 207 · y en un día QUE NO ES HOY, que es el de la captura del documento ──
    let OTRO = null;
    for (let atras = 2; atras <= 40 && !OTRO; atras++) {
        const d3 = new Date(d); d3.setDate(d3.getDate() - atras);
        const f = `${d3.getFullYear()}-${String(d3.getMonth() + 1).padStart(2, '0')}-${String(d3.getDate()).padStart(2, '0')}`;
        const x = await (await page.request.get(`${API}/api/diets/${f}`, { headers: cab })).json();
        const montado = Object.values(x.comidas || {}).some(m => (m.alimentos || []).length);
        if (!montado) OTRO = f;
    }
    const habiaOtro = !OTRO;
    if (OTRO) {
        await page.goto(`${APP}/dashboard/nutrition?date=${OTRO}`, { waitUntil: 'networkidle' }).catch(() => {});
        await page.waitForTimeout(8000);
        await quitarRecorrido(page);
        const a2 = (await page.locator('[data-testid="open-calendar-btn"]').innerText()).trim();
        const t2 = await page.locator('[data-testid="dia-vacio"] .caption').first()
            .innerText().then(t => t.trim()).catch(() => '(no sale el día vacío)');
        console.log(`\n207 · en el ${OTRO}, arriba        -> «${a2}»   ${ok(largo(a2))}`);
        console.log(`207 · y en la tarjeta                   -> «${t2}»   ${ok(largo(t2))}`);
        console.log(`207 · y ahí no pone «Hoy»              ${ok(!/\bhoy\b/i.test(t2))}`);
    } else {
        console.log('\n207 · no hay ningún día vacío atrás para probarlo');
    }

    // ── Y el aviso de guardado SIGUE saliendo cuando hay algo ───────────────
    await page.request.post(`${API}/api/diets`, { headers: cab,
        data: { fecha: HOY, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 0,
                opcion_peri: 'intra_post', comidas: { C1: { alimentos: [{ alimento_id: POLLO, cantidad_g: 150 }] } } } });
    await page.goto(`${APP}/dashboard/nutrition?date=${HOY}`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(9000);
    await quitarRecorrido(page);
    // Se toca algo para que el día se guarde de verdad: el selector de tipo de día.
    await page.locator('[data-testid="tipo-dia-descanso"]').click().catch(() => {});
    await page.waitForTimeout(7000);
    const aviso2 = await leerAviso();
    console.log(`\n205 · y con el día montado sí sale      -> «${aviso2}»   ${ok(/guardad/i.test(aviso2))}`);

    // Se cierra el navegador ANTES de reponer: al soltar la pantalla, Nutrición guarda el
    // día que deja, y si se repone primero ese guardado lo vuelve a pisar.
    await nav.close();
    const limpio = await chromium.launch();
    const p2 = await (await limpio.newContext()).newPage();
    await p2.request.delete(`${API}/api/diets/${HOY}`, { headers: cab });
    if (habia) {
        await p2.request.post(`${API}/api/diets`, { headers: cab,
            data: { fecha: HOY, tipo_dia: antes.tipo_dia, num_comidas: antes.num_comidas,
                    momento_entreno: antes.momento_entreno, opcion_peri: antes.opcion_peri, comidas: antes.comidas } });
    }
    await limpio.close();
    console.log(`\n${malas ? malas + ' MAL' : 'todo BIEN'} · día repuesto · captura -> _guia/_dia_sin_dieta_${ancho}.png`);
    process.exit(malas ? 1 : 0);
})();
