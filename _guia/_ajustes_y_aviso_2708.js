/**
 * LOS DOS ÚLTIMOS DEL PANEL (puntos 62 y 64), COMPROBADOS EN LA APP.
 *
 *   62 · «El aviso del Dashboard empieza por Y - falta media frase.»
 *   64 · «Sacar los interruptores escondidos a una pantalla de ajustes: los correos y la
 *         frase del día están dentro de Planes.»
 *
 * Lo que se mira aquí:
 *   - el aviso del Dashboard se lee solo, sin depender de la línea de arriba
 *   - «Ajustes» existe en el menú y se entra
 *   - los interruptores están ahí y AL PULSARLOS SE GUARDAN de verdad (se lee el ajuste
 *     del servidor antes y después, y se deja como estaba)
 *   - el de los correos avisa de que manda correos de verdad
 *   - Planes ya NO los tiene, pero SÍ deja el rastro de dónde se fueron
 *   - la frase del día sigue guardándose desde su sitio nuevo
 *
 * No cambia ningún ajuste: lo que enciende lo vuelve a dejar como estaba.
 *
 * Uso:  node _guia/_ajustes_y_aviso_2708.js [ancho]
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'francisco@test.com';
const CLAVE = process.env.CLAVE || 'demo123';

const ok = (b) => (b ? 'BIEN' : 'MAL ');

(async () => {
    const ancho = Number(process.argv[2]) || 1280;
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 1000 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    const errores = [];
    page.on('pageerror', (e) => errores.push(String(e)));

    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: CUENTA, password: CLAVE } });
    const tok = (await r.json()).access_token;
    const cab = { Authorization: `Bearer ${tok}`, 'Content-Type': 'application/json' };
    const ajustesDelServidor = async () => (await (await page.request.get(`${API}/api/admin/settings`, { headers: cab })).json());

    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);

    // ── 62 · el aviso del Dashboard ──────────────────────────────────────────────
    console.log(`\n=== 62 · EL AVISO QUE EMPEZABA POR «Y» ===\n`);
    await page.goto(`${APP}/admin`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(6000);
    // Hoy en esta base no hay ningún registro a medias, así que el aviso no sale solo. Se
    // fuerza metiendo filas falsas EN LA RESPUESTA, sin tocar un dato: lo que se comprueba
    // es la frase, y la frase depende del número. Se prueban 1 y 3 porque cambia de singular
    // a plural en seis sitios de la misma línea.
    const leerAviso = async (cuantos) => {
        await page.route('**/api/admin/clients**', async (ruta) => {
            const res = await ruta.fetch();
            let datos;
            try { datos = await res.json(); } catch (e) { return ruta.fulfill({ response: res }); }
            const filas = Array.isArray(datos) ? datos : (datos.clients || datos.items || []);
            // En esta base hay 324 registros a medias de verdad, así que SUMAR no sirve para
            // probar el singular: se quitan los suyos y se deja el número exacto que se quiere.
            const enteros = filas.filter(c => c?.status !== 'registro_incompleto');
            const falsos = Array.from({ length: cuantos }, (_, i) => ({
                ...(filas[0] || {}), id: `falso-${i}`, user_id: `falso-${i}`,
                name: `Registro a medias ${i + 1}`, email: `medias${i}@example.com`,
                status: 'registro_incompleto', plan: null, es_tu_ficha: false,
            }));
            const nuevas = [...enteros, ...falsos];
            const salida = Array.isArray(datos) ? nuevas
                : { ...datos, ...(datos.clients ? { clients: nuevas } : { items: nuevas }) };
            await ruta.fulfill({ response: res, body: JSON.stringify(salida) });
        });
        // El aviso vive en la pantalla de CLIENTES (el «Dashboard» del punto), debajo del
        // recuento. No en /admin.
        await page.goto(`${APP}/admin/clients`, { waitUntil: 'networkidle' }).catch(() => {});
        await page.waitForTimeout(7000);
        const a = page.locator('[data-testid="registros-sin-terminar"]');
        const t = (await a.count()) ? (await a.first().innerText()).trim() : null;
        await page.unroute('**/api/admin/clients**');
        return t;
    };

    for (const cuantos of [3, 1]) {
        const t = await leerAviso(cuantos);
        if (!t) { console.log(`   con ${cuantos}: el aviso no sale   MAL`); continue; }
        console.log(`   con ${cuantos}: «${t}»`);
        console.log(`      no empieza por «Y »           ${ok(!/^y\s/i.test(t))}`);
        console.log(`      empieza con mayúscula         ${ok(/^[A-ZÁÉÍÓÚÑ]/.test(t))}`);
        console.log(`      se entiende sola (tiene verbo) ${ok(/\bhay\b/i.test(t))}`);
        console.log(`      concuerda en número           ${ok(cuantos === 1
            ? /1 registro más sin terminar: entró y no eligió plan/.test(t) && /no cuenta como cliente/.test(t) && /Está en/.test(t)
            : /3 registros más sin terminar: entraron y no eligieron plan/.test(t) && /no cuentan como clientes/.test(t) && /Están en/.test(t))}`);
    }

    // ── 64 · la pantalla de Ajustes ──────────────────────────────────────────────
    console.log(`\n=== 64 · LOS INTERRUPTORES, EN SU SITIO ===\n`);
    const enElMenu = page.locator('a[href="/admin/ajustes"]');
    console.log(`«Ajustes» está en el menú           ${ok(await enElMenu.count() > 0)}`);

    await page.goto(`${APP}/admin/ajustes`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(4000);
    console.log(`la pantalla abre                    ${ok(await page.locator('[data-testid="admin-ajustes"]').count() > 0)}`);

    const CLAVES = ['frase_del_dia', 't1_inicio_nuevo', 't2_suplementos', 't3_entreno',
                    't4_cierre_nuevo', 't5_diario', 't6_evolucion', 't10_avisos_nuevos', 'correos_avisos'];
    let faltan = [];
    for (const c of CLAVES) {
        if (!(await page.locator(`[data-testid="ajuste-${c}"]`).count())) faltan.push(c);
    }
    console.log(`están los ${CLAVES.length} interruptores           ${ok(!faltan.length)}${faltan.length ? '  faltan: ' + faltan.join(', ') : ''}`);

    const avisoCorreos = await page.locator('text=/se mandan correos de verdad/i').count();
    console.log(`avisa de que manda correos          ${ok(avisoCorreos > 0)}`);

    // QUE GUARDE DE VERDAD: se pulsa el del Diario y se lee el servidor.
    const antes = await ajustesDelServidor();
    const eraDiario = !!antes.pantallas?.t5_diario;
    await page.locator('[data-testid="ajuste-t5_diario"]').click();
    await page.waitForTimeout(2500);
    const trasPulsar = await ajustesDelServidor();
    console.log(`al pulsar, el servidor cambia       ${ok(!!trasPulsar.pantallas?.t5_diario === !eraDiario)}   (${eraDiario} -> ${!!trasPulsar.pantallas?.t5_diario})`);
    // y se deja como estaba
    await page.locator('[data-testid="ajuste-t5_diario"]').click();
    await page.waitForTimeout(2500);
    const repuesto = await ajustesDelServidor();
    console.log(`se deja como estaba                 ${ok(!!repuesto.pantallas?.t5_diario === eraDiario)}`);

    // La frase del día sigue viva en su sitio nuevo.
    const fraseAntes = antes.frase_del_dia?.texto || '';
    const caja = page.locator('input[placeholder*="secreto"]');
    console.log(`la frase del día está aquí          ${ok(await caja.count() > 0)}`);
    if (await caja.count()) {
        const PRUEBA = 'Prueba de la mudanza (27-08)';
        await caja.first().fill(PRUEBA);
        await page.locator('button:has-text("Guardar")').first().click();
        await page.waitForTimeout(2500);
        const tras = await ajustesDelServidor();
        console.log(`   guardar la frase funciona        ${ok((tras.frase_del_dia?.texto || '') === PRUEBA)}`);
        // OJO AL REPONERLA: si la frase que había venía de la rotación no estaba GUARDADA
        // (se calcula al leer), así que devolverla la guarda. El texto es el mismo que se
        // veía, y mañana la rotación vuelve a mandar sola, pero conviene decirlo.
        if (fraseAntes && (antes.frase_del_dia?.puesta_por === 'rotacion')) {
            console.log('   (la de antes venía de la rotación: al reponerla queda guardada, mismo texto, hasta mañana)');
        }
        if (fraseAntes) {
            await caja.first().fill(fraseAntes);
            await page.locator('button:has-text("Guardar")').first().click();
            await page.waitForTimeout(2500);
            const fin = await ajustesDelServidor();
            console.log(`   frase repuesta                   ${ok((fin.frase_del_dia?.texto || '') === fraseAntes)}`);
        } else {
            console.log('   (no había frase antes; queda la de prueba, quítala a mano si molesta)');
        }
    }
    await page.screenshot({ path: `_guia/_ajustes_${ancho}.png`, fullPage: true });

    // ── Planes: ya no los tiene, pero deja el rastro ─────────────────────────────
    console.log(`\n=== PLANES, SIN LOS INTERRUPTORES ===\n`);
    await page.goto(`${APP}/admin/planes`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(5000);
    const sigueLaFrase = await page.locator('input[placeholder*="secreto"]').count();
    // El bloque global tenía su propio título; el rastro que dejo NOMBRA esas pantallas, así
    // que se busca el título, no la frase suelta.
    const hayGlobales = await page.locator('h2:has-text("Pantallas de la app")').count();
    const rastro = await page.locator('[data-testid="planes-a-ajustes"]').count();
    const hayPlanes = await page.locator('text=/CATÁLOGO DE PLANES/i').count();
    // El de los correos SÍ sigue apareciendo, pero solo dentro de «Mi modo pruebas», que es
    // otra cosa: enciende para TU cuenta. Lo que no puede quedar aquí es el global.
    const correos = await page.evaluate(() => {
        const salen = [...document.querySelectorAll('span, p, button')]
            .filter(e => /Los avisos del reporte, por correo/i.test(e.textContent || '') && e.children.length === 0);
        return salen.map((e) => {
            let p = e, caja = null;
            while (p && p !== document.body) {
                if (/Mi modo pruebas/i.test(p.textContent || '')) { caja = 'mi modo pruebas'; break; }
                p = p.parentElement;
            }
            return caja || 'suelto en la pantalla';
        });
    });
    console.log(`la frase del día ya no está aquí    ${ok(sigueLaFrase === 0)}`);
    console.log(`el bloque global ya no está aquí    ${ok(hayGlobales === 0)}`);
    console.log(`el de correos, solo en «pruebas»    ${ok(correos.every(c => c === 'mi modo pruebas'))}   [${correos.join(', ') || 'no sale'}]`);
    // Se puso un rastro («esto está ahora en Ajustes») y Francisco lo quitó: Planes son
    // planes y punto. Se comprueba que no quede, que un cartel a medio borrar es peor.
    console.log(`sin cartel de la mudanza            ${ok(rastro === 0)}`);
    console.log(`y los planes siguen saliendo        ${ok(hayPlanes > 0)}`);
    await page.screenshot({ path: `_guia/_planes_sin_interruptores_${ancho}.png`, fullPage: true });

    console.log(`\nerrores de JavaScript: ${errores.length ? errores.join(' | ') : 'ninguno'}`);
    console.log(`capturas -> _guia/_ajustes_${ancho}.png y _guia/_planes_sin_interruptores_${ancho}.png`);
    await nav.close();
})();
