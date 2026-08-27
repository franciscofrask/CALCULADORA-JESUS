/**
 * PARTE 6 · lo que enseña la maqueta de Nutrición, y las dos decisiones del 27-08 por la
 * tarde (Francisco: «respeta el documento» en las dos).
 *
 *   El aviso de pasarse, con las palabras de la maqueta y NO las del vídeo.
 *   Ni un color en toda la pantalla: por debajo del objetivo no se pinta nada.
 *   Los objetivos con letra:  Objetivo · 33P · 20H · 10G
 *   El día con su nombre:     Jueves, 27 de agosto
 *   «Nutrición», no «Plan nutricional»
 *   El rótulo «Comidas del día», también en el móvil
 *   Los Extras plegados, con su «+»
 *   El intra y el post con su estado
 *   «+ Creatina» debajo de su comida, también aquí
 *
 * Monta un día A MEDIAS con suplementos pautados y lo deja todo como estaba.
 *
 * Uso:  node _guia/_parte6_maqueta_2708.js [ancho]
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || process.env.DESTINO || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const ADMIN = process.env.ADMIN || 'francisco@test.com';
const ADMIN_CLAVE = process.env.ADMIN_CLAVE || 'demo123';

const ok = (b) => (b ? 'BIEN' : 'MAL ');
const POLLO = 498, ARROZ = 1657, ACEITE = 3;
const SUPS = [
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

    const d = new Date();
    const FECHA = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    console.log(`\n=== PARTE 6 · la maqueta de Nutrición · ${ancho} px ===\n`);

    const antesDia = await (await page.request.get(`${API}/api/diets/${FECHA}`, { headers: cab })).json();
    const habiaDia = !!antesDia.exists;
    const antesProt = await (await page.request.get(`${API}/api/supplements/current`, { headers: cab })).json().catch(() => null);
    const habiaProt = !!(antesProt && (antesProt.versiones || []).length);

    await page.request.post(`${API}/api/diets`, {
        headers: cab,
        data: { fecha: FECHA, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 0,
                opcion_peri: 'intra_post',
                comidas: { C1: { alimentos: [
                    { alimento_id: POLLO, cantidad_g: 150 },
                    { alimento_id: ARROZ, cantidad_g: 60 },
                    { alimento_id: ACEITE, cantidad_g: 10 },
                ] } } },
    });
    await page.request.post(`${API}/api/admin/supplements/save?client_id=${cli.id}`, {
        headers: cabAdmin, data: { actual: SUPS, actual_fecha: FECHA, siguiente: [] },
    });

    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);
    await page.goto(`${APP}/dashboard/nutrition?date=${FECHA}`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(11000);
    await quitarRecorrido(page);
    const texto = await page.locator('body').innerText();

    // ── El rótulo y el día ──────────────────────────────────────────────────
    const eyebrow = (await page.locator('.caption').first().innerText()).trim();
    console.log(`«Nutrición», no «Plan nutricional» -> «${eyebrow}»   ${ok(/^nutrici/i.test(eyebrow))}`);
    const fecha = (await page.locator('[data-testid="open-calendar-btn"]').innerText()).trim();
    console.log(`el día con su nombre               -> «${fecha}»   ${ok(!/^hoy$/i.test(fecha) && /de /.test(fecha))}`);
    console.log(`el rótulo «Comidas del día»        ${ok(/Comidas del día/i.test(texto))}`);

    // ── Los objetivos con letra ─────────────────────────────────────────────
    const obj = (await page.locator('[data-testid="objetivo-C1"]').first().innerText()).trim().replace(/\s+/g, ' ');
    console.log(`los objetivos con letra            -> «${obj}»   ${ok(/\d+P · \d+H · \d+G/.test(obj))}`);

    // ── El intra y el post, con su estado ───────────────────────────────────
    for (const k of ['Intra', 'Post']) {
        const e = page.locator(`[data-testid="estado-comida-${k}"]`).first();
        console.log(`el ${k.toLowerCase()} lleva su estado`.padEnd(35) + `-> ${(await e.count()) ? '«' + (await e.innerText()).trim() + '»   BIEN' : 'NO SALE   MAL '}`);
    }

    // ── Los suplementos, también aquí ───────────────────────────────────────
    const sup = page.locator('[data-testid="suplementos-comida-C1"]').first();
    console.log(`«+ Creatina» debajo de su comida   -> ${(await sup.count()) ? '«' + (await sup.innerText()).trim() + '»   BIEN' : 'NO SALE   MAL '}`);

    // ── Los Extras, plegados ────────────────────────────────────────────────
    const masExtras = await page.locator('[data-testid="extras-abrir"]').count();
    const campoVisible = await page.locator('[data-testid="extras-campo"]').first().isVisible().catch(() => false);
    console.log(`los Extras, plegados con su «+»    -> botón ${masExtras}, campo ${campoVisible ? 'abierto' : 'cerrado'}   ${ok(masExtras === 1 && !campoVisible)}`);
    if (masExtras) {
        await page.locator('[data-testid="extras-abrir"]').click();
        await page.waitForTimeout(1200);
        console.log(`   y al tocarlo se abre          ${ok(await page.locator('[data-testid="extras-campo"]').first().isVisible())}`);
    }

    // ── Ni un color: por debajo del objetivo no se pinta nada ───────────────
    const colores = await page.evaluate(() => {
        const fuera = [];
        document.querySelectorAll('[data-testid^="dia-palabra-"], [data-testid^="estado-comida-"]').forEach((e) => {
            const c = getComputedStyle(e).color;
            if (/255,\s*90,\s*46/.test(c) || /255,\s*103,\s*31/.test(c)) fuera.push(e.dataset.testid + ' «' + e.innerText.trim() + '» ' + c);
        });
        return fuera;
    });
    console.log(`\nen naranja, sólo lo que se pasa    -> ${colores.length ? colores.join(' | ') : 'nada en naranja'}   ${ok(colores.length === 0)}`);
    const cab3 = await page.locator('[data-testid="dia-palabra-P"]').first().evaluate(el => getComputedStyle(el).color).catch(() => '?');
    console.log(`la cabecera, «faltan X»            -> ${cab3}   ${ok(!/255,\s*90,\s*46/.test(cab3))}`);

    await page.screenshot({ path: `_guia/_parte6_maqueta_${ancho}.png`, fullPage: true });

    // ── El aviso de pasarse, con las palabras del documento ─────────────────
    await page.request.post(`${API}/api/diets`, {
        headers: cab,
        data: { fecha: FECHA, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 0,
                opcion_peri: 'intra_post', comidas: { C1: { alimentos: [{ alimento_id: ARROZ, cantidad_g: 2000 }] } } },
    });
    await page.reload({ waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(10000);
    await quitarRecorrido(page);
    const aviso = page.locator('[data-testid="banner-recuadrar"]');
    if (await aviso.count()) {
        const t = (await aviso.innerText()).replace(/\n+/g, ' | ');
        console.log(`\nel aviso dice: ${t}`);
        console.log(`«de ahora», como el documento      ${ok(/macros de ahora/i.test(t) && !/macros actuales/i.test(t))}`);
        console.log(`«te reajustamos»                   ${ok(/te reajustamos/i.test(t))}`);
        const boton = (await page.locator('[data-testid="boton-recuadrar-dia"]').innerText()).trim();
        console.log(`el botón dice «${boton}»           ${ok(boton === 'Cuadrar el día')}`);
    } else {
        console.log('\nel aviso de pasarse no salió');
    }

    // ── Se repone ───────────────────────────────────────────────────────────
    if (habiaDia) {
        await page.request.post(`${API}/api/diets`, { headers: cab,
            data: { fecha: FECHA, tipo_dia: antesDia.tipo_dia, num_comidas: antesDia.num_comidas,
                    momento_entreno: antesDia.momento_entreno, opcion_peri: antesDia.opcion_peri, comidas: antesDia.comidas } });
    } else {
        await page.request.delete(`${API}/api/diets/${FECHA}`, { headers: cab });
    }
    if (habiaProt) {
        await page.request.post(`${API}/api/admin/supplements/save?client_id=${cli.id}`, { headers: cabAdmin,
            data: { actual: antesProt.actual || [], actual_fecha: antesProt.actual_fecha || FECHA, siguiente: antesProt.siguiente || [] } });
    } else {
        await page.request.delete(`${API}/api/admin/supplements/version/${FECHA}?client_id=${cli.id}`, { headers: cabAdmin });
    }
    console.log(`\ntodo repuesto · captura -> _guia/_parte6_maqueta_${ancho}.png`);
    await nav.close();
})();
