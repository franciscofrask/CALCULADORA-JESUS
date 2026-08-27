/**
 * PARTE 6 · bloque A (puntos 179 a 190): los tres estados de Suplementos.
 *
 *   Con plan y con protocolo   ->  «Mis suplementos». Sólo lo suyo. LA GUÍA NO SALE.
 *   Con plan, sin protocolo    ->  «Mis suplementos» + el aviso + la guía debajo.
 *   Sin plan personalizado     ->  «Suplementación»: la guía y nada más.
 *
 * Y de paso: las cuatro líneas por suplemento con la COMIDA en naranja (184), «Comprar con
 * descuento» (185), Alimentos antes que Básicos (186), sin el cajón «El resto de la guía»
 * (187), el código al final (188) y llegar desde Inicio tocando el «+ Creatina» (190).
 *
 * Deja la cuenta como estaba.
 *
 * Uso:  node _guia/_parte6_suplementos_2708.js [ancho]
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || process.env.DESTINO || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const ADMIN = process.env.ADMIN || 'francisco@test.com';
const ADMIN_CLAVE = process.env.ADMIN_CLAVE || 'demo123';

const ok = (b) => (b ? 'BIEN' : 'MAL ');

const PRUEBA = [
    { titulo: 'Monohidrato de creatina', cuando: 'Todos los días, con el desayuno (entrenes o no)', cuanto: '5 g' },
    { titulo: 'Omega 3', cuando: 'Todos los días, en dos tomas (desayuno y cena)', cuanto: '2 cápsulas' },
];

const quitarRecorrido = async (page) => {
    for (let i = 0; i < 4; i++) {
        const s = page.locator('[data-testid="recorrido-saltar"]');
        if (!(await s.count())) break;
        await s.click({ force: true }).catch(() => {});
        await page.waitForTimeout(1200);
    }
    await page.locator('[data-testid="recorrido-overlay"]').waitFor({ state: 'detached', timeout: 8000 }).catch(() => {});
    await page.waitForTimeout(1200);
};

const abrir = async (page, ruta) => {
    await page.goto(`${APP}${ruta}`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(8000);
    await quitarRecorrido(page);
    return (await page.locator('body').innerText());
};

(async () => {
    const ancho = Number(process.argv[2]) || 390;
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 900 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();

    const rc = await page.request.post(`${API}/api/auth/login`, { data: { email: CUENTA, password: CLAVE } });
    const tok = (await rc.json()).access_token;
    const cab = { Authorization: `Bearer ${tok}` };
    const ra = await page.request.post(`${API}/api/auth/login`, { data: { email: ADMIN, password: ADMIN_CLAVE } });
    const cabAdmin = { Authorization: `Bearer ${(await ra.json()).access_token}` };
    const yo = await (await page.request.get(`${API}/api/auth/me`, { headers: cab })).json();
    const lista = await (await page.request.get(`${API}/api/admin/clients?include_incomplete=true`, { headers: cabAdmin, timeout: 90000 })).json();
    const cli = (Array.isArray(lista) ? lista : []).find(c => ((c.user || {}).email || '').toLowerCase() === yo.email.toLowerCase());
    if (!cli) { console.log('no encuentro al cliente'); await nav.close(); return; }

    const d = new Date();
    const FECHA = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    console.log(`\n=== PARTE 6 · Suplementos · ${ancho} px ===\n`);

    const guia = await (await page.request.get(`${API}/api/supplements/guia`, { headers: cab })).json();
    console.log(`el servidor dice: con_plan=${guia.con_plan} · con_protocolo=${guia.con_protocolo}`);

    // ── 186 y 187 · el orden de las categorías y el cajón ───────────────────
    const nombres = (guia.secciones || []).filter(s => s.suplementos.length).map(s => s.nombre);
    console.log(`\n186  el orden -> ${nombres.join(' · ')}`);
    console.log(`     Alimentos antes que Básicos   ${ok(nombres.indexOf('Alimentos') === 0 && nombres.indexOf('Básicos') === 1)}`);
    console.log(`187  fichas sin categoría -> ${(guia.sin_seccion || []).length}   ${ok((guia.sin_seccion || []).length === 0)}`);

    // ── 182 · el texto de la guía ───────────────────────────────────────────
    const entrada = (guia.texto_entrada || '');
    console.log(`\n182  el texto de la guía, ${entrada.split('\n').length} líneas`);
    entrada.split('\n').forEach(l => console.log('     ' + l));
    console.log(`     sin el Catálogo Premium   ${ok(!/Cat[aá]logo Premium/i.test(entrada))}`);
    console.log(`     sin el *IMPORTANTE        ${ok(!/IMPORTANTE/i.test(entrada))}`);

    const antesProt = await (await page.request.get(`${API}/api/supplements/current`, { headers: cab })).json().catch(() => null);
    const habia = !!(antesProt && (antesProt.versiones || []).length);

    // ══ ESTADO 2 · con plan, SIN protocolo ══════════════════════════════════
    if (habia) {
        await page.request.delete(`${API}/api/admin/supplements/version/${antesProt.actual_fecha}?client_id=${cli.id}`, { headers: cabAdmin });
    }
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);
    let texto = await abrir(page, '/dashboard/supplements');
    const titulo2 = (await page.locator('h1').first().innerText()).trim();
    console.log(`\n── ESTADO 2 · con plan, sin protocolo ──`);
    console.log(`180  el título dice «${titulo2}»   ${ok(titulo2.toLowerCase() === 'mis suplementos')}`);
    console.log(`183  el aviso -> ${/Te lo estamos preparando/.test(texto) ? '«Te lo estamos preparando. Te avisamos en cuanto esté.»' : 'NO SALE'}   ${ok(/Te lo estamos preparando/.test(texto))}`);
    console.log(`183  y el «mientras tanto»          ${ok(/Mientras tanto, aquí tienes todo lo que uso/.test(texto))}`);
    console.log(`183  sin «empieza por los básicos»  ${ok(!/empezar por los b[aá]sicos/i.test(texto))}`);
    console.log(`182  fuera «Esto es solo la guía básica»   ${ok(!/gu[ií]a b[aá]sica/i.test(texto))}`);
    console.log(`179  y la guía SÍ sale debajo       ${ok(/Rendimiento/.test(texto) && /Descanso/.test(texto))}`);
    console.log(`187  sin «El resto de la guía»      ${ok(!/El resto de la gu[ií]a/i.test(texto))}`);
    console.log(`188  el código al final             ${ok(/GALLEGOVIP/.test(texto))}`);
    await page.screenshot({ path: `_guia/_parte6_sup_esperando_${ancho}.png`, fullPage: true });

    // ══ ESTADO 1 · con plan y CON protocolo ═════════════════════════════════
    await page.request.post(`${API}/api/admin/supplements/save?client_id=${cli.id}`, {
        headers: cabAdmin, data: { actual: PRUEBA, actual_fecha: FECHA, siguiente: [] },
    });
    texto = await abrir(page, '/dashboard/supplements');
    const titulo1 = (await page.locator('h1').first().innerText()).trim();
    console.log(`\n── ESTADO 1 · con plan y con protocolo ──`);
    console.log(`180  el título dice «${titulo1}»   ${ok(titulo1.toLowerCase() === 'mis suplementos')}`);
    console.log(`181  el subtítulo                   ${ok(/Lo que tienes pautado, dosis y cuándo tomarlo/.test(texto))}`);
    console.log(`179  LA GUÍA NO SALE                ${ok(!/La gu[ií]a de suplementaci[oó]n/i.test(texto) && !/Los suplementos que m[aá]s utilizo/i.test(texto))}`);
    const comidas = await page.locator('[data-testid="suplemento-comida"]').allInnerTexts();
    console.log(`184  la comida, en naranja -> ${comidas.join(' | ') || '(no sale)'}   ${ok(comidas.length >= 1)}`);
    if (comidas.length) {
        const color = await page.locator('[data-testid="suplemento-comida"]').first().evaluate(el => getComputedStyle(el).color);
        // «El mismo dato y el mismo color que vera en Inicio» (punto 184): #FF671F, el
        // naranja de la casa, no el #FFA500 que el mismo señalo en el 158.
        console.log(`     su color -> ${color}   ${ok(color === 'rgb(255, 103, 31)')}   <- el mismo que en Inicio`);
    }
    console.log(`184  «Dosis» y «Cuándo» sin interrogación   ${ok(/Dosis/.test(texto) && /Cuándo/.test(texto) && !/¿Cuánto\?/.test(texto) && !/¿Cuándo\?/.test(texto))}`);
    console.log(`188  el código al final             ${ok(/GALLEGOVIP/.test(texto))}`);
    await page.screenshot({ path: `_guia/_parte6_sup_mios_${ancho}.png`, fullPage: true });

    // ── 190 · desde Inicio, tocando el «+ Creatina» ─────────────────────────
    const dia = await (await page.request.get(`${API}/api/diets/${FECHA}`, { headers: cab })).json();
    const habiaDia = !!dia.exists;
    if (!habiaDia) {
        await page.request.post(`${API}/api/diets`, {
            headers: cab,
            data: { fecha: FECHA, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 0,
                    opcion_peri: 'intra_post', comidas: { C1: { alimentos: [] } } },
        });
    }
    await abrir(page, '/dashboard');
    const linea = page.locator('[data-testid="suplementos-C1"]');
    if (await linea.count()) {
        console.log(`\n190  en Inicio sale «${(await linea.innerText()).trim()}»`);
        await linea.click();
        await page.waitForTimeout(4000);
        const donde = page.url().replace(APP, '');
        console.log(`190  y al tocarlo lleva a ${donde}   ${ok(donde.includes('/dashboard/supplements'))}`);
    } else {
        console.log('\n190  no sale la línea de suplementos en el Inicio');
    }

    // ── Se repone todo ──────────────────────────────────────────────────────
    if (habia) {
        await page.request.post(`${API}/api/admin/supplements/save?client_id=${cli.id}`, {
            headers: cabAdmin, data: { actual: antesProt.actual || [], actual_fecha: antesProt.actual_fecha || FECHA, siguiente: antesProt.siguiente || [] } });
        console.log('\nprotocolo repuesto');
    } else {
        await page.request.delete(`${API}/api/admin/supplements/version/${FECHA}?client_id=${cli.id}`, { headers: cabAdmin });
        console.log('\nprotocolo de prueba borrado');
    }
    if (!habiaDia) await page.request.delete(`${API}/api/diets/${FECHA}`, { headers: cab });
    console.log(`capturas -> _guia/_parte6_sup_esperando_${ancho}.png y _guia/_parte6_sup_mios_${ancho}.png`);
    await nav.close();
})();
