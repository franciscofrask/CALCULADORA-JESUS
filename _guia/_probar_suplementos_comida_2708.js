/**
 * LOS SUPLEMENTOS DEBAJO DE CADA COMIDA (punto 174 + el vídeo del 27-08), EN LA APP.
 *
 * Recorre el camino entero, que es lo que se le pide a una persona que lo pruebe a mano:
 *
 *   1. En el catálogo de suplementos se elige «¿Con qué comida sale en su Inicio?»
 *   2. Se le pauta ese suplemento a un cliente
 *   3. En el Inicio del cliente sale debajo de ESA comida, y con el nombre limpio
 *   4. Se cambia la elección en la ficha y el Inicio la sigue, sin volver a pautar nada
 *
 * El paso 4 es el que importa: la comida NO se congela en la línea del cliente, se resuelve
 * al servir. Si Jesús se equivoca al pautarlo, lo corrige una vez en la ficha y se arregla
 * para todos los que lo llevan.
 *
 * Deja el catálogo y el protocolo como estaban.
 *
 * Uso:  node _guia/_probar_suplementos_comida_2708.js [ancho]
 *       DESTINO=https://12en12app.jesusgallegopt.com  para probarlo contra producción
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || process.env.DESTINO || 'http://127.0.0.1:8000';
const ADMIN = process.env.ADMIN || 'francisco@test.com';
const CLIENTE = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';

const ok = (b) => (b ? 'BIEN' : 'MAL ');

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
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 1000 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();

    const entrar = async (email) => {
        const r = await page.request.post(`${API}/api/auth/login`, { data: { email, password: CLAVE } });
        return (await r.json()).access_token;
    };
    const tokAdmin = await entrar(ADMIN);
    const tokCliente = await entrar(CLIENTE);
    const cabA = { Authorization: `Bearer ${tokAdmin}`, 'Content-Type': 'application/json' };
    const cabC = { Authorization: `Bearer ${tokCliente}`, 'Content-Type': 'application/json' };

    console.log(`\n=== LOS SUPLEMENTOS, CON SU COMIDA · ${APP} · ${ancho} px ===\n`);

    // ── De quién hablamos, y qué tenía ──────────────────────────────────────
    const perfil = await (await page.request.get(`${API}/api/clients/profile`, { headers: cabC })).json();
    const clientId = perfil.id;
    // LA COPIA SE HACE POR LA PUERTA DEL PANEL, NO POR LA DEL CLIENTE. `/supplements/current`
    // devuelve los nombres YA LIMPIOS («Creatina», no «Creatina hombre»), así que guardar eso
    // de vuelta borraría de la base la chuleta de Jesús para siempre y sin avisar. El panel
    // sirve la línea tal cual está guardada, que es lo que hay que reponer.
    const fichaAdmin = await (await page.request.get(`${API}/api/admin/clients/${clientId}`, { headers: cabA })).json();
    const protoAntes = fichaAdmin.supplement_protocol || { actual: [], siguiente: [] };

    const catalogo = await (await page.request.get(`${API}/api/admin/supplements/catalog`, { headers: cabA })).json();
    // Uno cuyo «¿Cuándo?» hable del desayuno: así se ve la deducción automática ANTES de
    // tocar nada, que es como lo va a ver Jesús en los 528 que ya tiene puestos.
    const suple = catalogo.find(c => /desayuno/i.test(c.cuando || '')) || catalogo.find(c => c.cuando && c.cuanto);
    if (!suple) { console.log('el catálogo no tiene ninguno con «¿Cuándo?»'); await nav.close(); return; }
    const comidaAntes = suple.comida || '';
    console.log(`suplemento de la prueba : «${suple.titulo}»`);
    console.log(`su «¿Cuándo?»           : «${suple.cuando}»`);
    console.log(`su comida en la ficha    : ${comidaAntes ? `«${comidaAntes}»` : '(vacía: automático)'}\n`);

    const ponerComida = async (valor) => {
        await page.request.put(`${API}/api/admin/supplements/catalog/${suple.id}`, {
            headers: cabA, data: { ...suple, comida: valor },
        });
    };
    const pautar = async () => {
        await page.request.post(`${API}/api/admin/supplements/save?client_id=${clientId}`, {
            headers: cabA,
            data: { actual: [{ catalog_id: suple.id, titulo: suple.titulo, imagen: suple.imagen,
                              enlaces: suple.enlaces || [], cuando: suple.cuando, cuanto: suple.cuanto,
                              observaciones: suple.observaciones }],
                    siguiente: [], actual_fecha: new Date().toISOString().slice(0, 10),
                    nota: 'Prueba del punto 174' },
        });
    };
    const dondeCae = async () => {
        const v = await (await page.request.get(`${API}/api/supplements/current`, { headers: cabC })).json();
        const l = (v.actual || [])[0] || {};
        return { comidas: l.en_comidas || [], titulo: l.titulo };
    };

    // ── 1 · Automático: lo saca del «¿Cuándo?» ──────────────────────────────
    await ponerComida('');
    await pautar();
    const auto = await dondeCae();
    console.log(`1. sin elegir nada, lo deduce del texto -> [${auto.comidas.join(', ') || 'ninguna'}]`);
    console.log(`   y el nombre le llega limpio: «${auto.titulo}»   ${ok(!/\b(hombre|mujer|perlas|c[aá]psulas)\b/i.test(auto.titulo))}`);

    // ── 2 · Elegida a mano: manda la ficha ──────────────────────────────────
    await ponerComida('C3');
    const tresC = await dondeCae();
    console.log(`2. eligiendo «Comida 3» en la ficha     -> [${tresC.comidas.join(', ')}]   ${ok(tresC.comidas.join() === 'C3')}`);
    console.log(`   (sin volver a pautarle nada al cliente: se resuelve al servir)`);

    // ── 3 · «En ninguna» ────────────────────────────────────────────────────
    await ponerComida('ninguna');
    const ninguna = await dondeCae();
    console.log(`3. eligiendo «En ninguna comida»        -> [${ninguna.comidas.join(', ') || 'ninguna'}]   ${ok(ninguna.comidas.length === 0)}`);

    // ── 4 · En el Inicio del cliente, con los ojos ──────────────────────────
    await ponerComida('C2');
    const d = new Date();
    const FECHA = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    const diaAntes = await (await page.request.get(`${API}/api/diets/${FECHA}`, { headers: cabC })).json();
    if (!diaAntes.exists) {
        await page.request.post(`${API}/api/diets`, { headers: cabC,
            data: { fecha: FECHA, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 0,
                    opcion_peri: 'intra_post', comidas: { C1: { alimentos: [] } } } });
    }

    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tokCliente);
    await page.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(9000);
    await quitarRecorrido(page);

    console.log('\n4. en el Inicio del cliente:');
    for (const k of ['C1', 'C2', 'C3', 'C4', 'Intra', 'Post']) {
        const linea = page.locator(`[data-testid="suplementos-${k}"]`);
        if (await linea.count()) console.log(`   ${k}: ${(await linea.first().innerText()).trim()}`);
    }
    const enC2 = await page.locator('[data-testid="suplementos-C2"]').count();
    const enPeri = (await page.locator('[data-testid="suplementos-Intra"]').count())
                 + (await page.locator('[data-testid="suplementos-Post"]').count());
    console.log(`   sale debajo de la Comida 2              ${ok(enC2 > 0)}`);
    console.log(`   y NO debajo del Intra ni del Post       ${ok(enPeri === 0)}`);
    await page.screenshot({ path: `_guia/_suplementos_comida_${ancho}.png`, fullPage: true });

    // ── Se repone todo ──────────────────────────────────────────────────────
    await ponerComida(comidaAntes);
    if (protoAntes && (protoAntes.actual || []).length) {
        await page.request.post(`${API}/api/admin/supplements/save?client_id=${clientId}`, {
            headers: cabA,
            data: { actual: protoAntes.actual, siguiente: protoAntes.siguiente || [],
                    actual_fecha: protoAntes.actual_fecha, siguiente_fecha: protoAntes.siguiente_fecha,
                    nota: protoAntes.nota },
        });
    }
    if (!diaAntes.exists) await page.request.delete(`${API}/api/diets/${FECHA}`, { headers: cabC });
    console.log(`\ncatálogo y protocolo repuestos · captura -> _guia/_suplementos_comida_${ancho}.png`);
    await nav.close();
})();
