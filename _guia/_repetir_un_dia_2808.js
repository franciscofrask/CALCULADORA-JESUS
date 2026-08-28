/**
 * «REPETIR UN DÍA» · el recorrido de los puntos 210 a 213 (parte 7 del 28-08).
 *
 *   210  la lista va de hoy hacia atrás, y empieza por el último día montado
 *   211  cada día enseña sus macros de verdad, contados por el servidor
 *   212  ENCAJA sólo en el que encaja; los demás dicen por qué no
 *   213  la frase de abajo: «Se copian las comidas y se ajustan a tus macros de hoy»
 *
 * Deja el día de hoy VACÍO (que es la única forma de llegar a la pantalla de los tres
 * caminos), abre la lista, la lee entera y repone el día tal y como estaba.
 *
 * Uso:  node _guia/_repetir_un_dia_2808.js [ancho]     (390 móvil · 1280 ordenador)
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';

// Para fabricar el día que SÍ cuadra: proteína, hidratos y grasa casi puras.
const POLLO = 498, ARROZ = 1657, ACEITE = 3;

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
    console.log(`\n=== REPETIR UN DÍA · ${ancho} px · hoy ${HOY} ===\n`);

    const antes = await (await page.request.get(`${API}/api/diets/${HOY}`, { headers: cab })).json();
    const habia = !!antes.exists;

    // Vaciar de verdad: guardar con `comidas: {}` NO borra lo que ya hay (el guardado es
    // por campos), así que primero se tira el día y luego se crea vacío.
    await page.request.delete(`${API}/api/diets/${HOY}`, { headers: cab });
    await page.request.post(`${API}/api/diets`, {
        headers: cab,
        data: { fecha: HOY, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 0,
                opcion_peri: 'intra_post', comidas: {} },
    });
    // Y la forma de ver las comidas, la de siempre: se guarda en la ficha y una pasada
    // anterior puede haberla dejado en otra.
    await page.request.post(`${API}/api/user/ajustes-app`, { headers: cab, data: { vista: 'actual' } });

    // ── Un día de prueba QUE SÍ CUADRA, para poder ver el ENCAJA ────────────────
    // La cuenta de prueba no tiene ninguno: sus días están a medias y todos se quedan
    // cortos, así que sin esto no se vería nunca la etiqueta buena. Se monta un día viejo
    // con proteína, hidratos y grasa casi puros y se ajustan las cantidades a los macros
    // de hoy en un par de pasadas (la calibración cambia lo que cuenta cada alimento, así
    // que se mide y se corrige en vez de calcularlo a la primera). Se borra al final.
    const d2 = new Date(d); d2.setDate(d2.getDate() - 45);
    const CUADRA = `${d2.getFullYear()}-${String(d2.getMonth() + 1).padStart(2, '0')}-${String(d2.getDate()).padStart(2, '0')}`;
    const habiaCuadra = (await (await page.request.get(`${API}/api/diets/${CUADRA}`, { headers: cab })).json()).exists;

    const reparto = await (await page.request.post(`${API}/api/calculator/distribute`, {
        headers: cab,
        data: { fecha: HOY, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 0,
                opcion_peri: 'intra_post', single_meal: false },
    })).json();
    const meta = { P: reparto?.resumen?.P_total || 0, H: reparto?.resumen?.H_total || 0, G: reparto?.resumen?.G_total || 0 };
    console.log(`los macros de hoy: ${Math.round(meta.P)} P · ${Math.round(meta.H)} H · ${Math.round(meta.G)} G`);

    let g = { [POLLO]: 600, [ARROZ]: 350, [ACEITE]: 55 };
    let logrado = null;
    if (!habiaCuadra && meta.P > 0) {
        for (let paso = 0; paso < 6; paso++) {
            await page.request.post(`${API}/api/diets`, { headers: cab,
                data: { fecha: CUADRA, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 0,
                        opcion_peri: 'sin_peri', comidas: { C1: { alimentos: [
                            { alimento_id: POLLO, cantidad_g: Math.round(g[POLLO]) },
                            { alimento_id: ARROZ, cantidad_g: Math.round(g[ARROZ]) },
                            { alimento_id: ACEITE, cantidad_g: Math.round(g[ACEITE]) },
                        ] } } } });
            const lst = await (await page.request.get(
                `${API}/api/diets/recent?limit=40&para=${HOY}&hoy_cliente=${HOY}`, { headers: cab })).json();
            const fila = (lst.diets || []).find(x => x.fecha === CUADRA);
            logrado = fila?.macros;
            if (!logrado) break;
            const fuera = ['P', 'H', 'G'].filter(k => Math.abs(logrado[k] - meta[k]) > 3);
            if (!fuera.length) break;
            // Cada alimento manda sobre un macro: se corrige el suyo y se vuelve a medir.
            const ajusta = (id, k) => { if (logrado[k] > 0) g[id] *= Math.min(3, Math.max(0.3, meta[k] / logrado[k])); };
            ajusta(POLLO, 'P'); ajusta(ARROZ, 'H'); ajusta(ACEITE, 'G');
        }
        console.log(`día de prueba ${CUADRA} -> ${logrado ? `${Math.round(logrado.P)} P · ${Math.round(logrado.H)} H · ${Math.round(logrado.G)} G` : 'no se pudo montar'}`);
    }

    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);
    await page.goto(`${APP}/dashboard/nutrition?date=${HOY}`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(9000);
    await quitarRecorrido(page);

    console.log(`la pantalla del día vacío          ${ok((await page.locator('[data-testid="dia-vacio"]').count()) === 1)}`);
    const boton = page.locator('[data-testid="dia-vacio-repetir"]');
    console.log(`el camino «Repetir un día»         ${ok((await boton.count()) === 1)}`);
    if (!(await boton.count())) { await nav.close(); process.exit(1); }

    await boton.click();
    await page.waitForTimeout(2500);

    const filas = await page.locator('[data-testid^="dia-vacio-reciente-"]').all();
    const fechas = [];
    const lineas = [];
    console.log(`\nla lista, tal cual sale (${filas.length} días):`);
    for (const f of filas) {
        const fecha = (await f.getAttribute('data-testid')).replace('dia-vacio-reciente-', '');
        fechas.push(fecha);
        const t = (await f.innerText()).replace(/\n+/g, ' · ');
        lineas.push(t);
        console.log('   ' + t);
    }

    // ── 210 · de hoy hacia atrás ────────────────────────────────────────────
    const futuras = fechas.filter(f => f > HOY);
    console.log(`\n210 · ni una fecha por delante de hoy   -> ${futuras.length ? futuras.join(', ') : 'ninguna'}   ${ok(futuras.length === 0)}`);
    console.log(`210 · de hoy hacia atrás, sin saltos    ${ok(fechas.every((f, i) => i === 0 || f < fechas[i - 1]))}`);
    console.log(`210 · hay días que ofrecer              ${ok(fechas.length > 0)}`);
    const recientes = await (await page.request.get(
        `${API}/api/diets/recent?limit=14&para=${HOY}&hoy_cliente=${HOY}`, { headers: cab })).json();
    const api = recientes.diets || [];
    console.log(`210 · empieza por el último montado     -> «${fechas[0]}» · API «${(api[0] || {}).fecha}»   ${ok(fechas[0] === (api[0] || {}).fecha)}`);

    // ── 211 · con sus macros, y los mismos que al abrir el día ──────────────
    const ceros = lineas.filter(t => /\b0 P · 0 H · 0 G\b/.test(t));
    console.log(`\n211 · ninguno a 0 P · 0 H · 0 G         -> ${ceros.length ? ceros.length + ' filas' : 'ninguna'}   ${ok(ceros.length === 0)}`);
    const pintados = lineas.filter((t, i) => {
        const m = api.find(x => x.fecha === fechas[i]);
        return m && new RegExp(`${Math.round(m.macros.P)} P · ${Math.round(m.macros.H)} H · ${Math.round(m.macros.G)} G`).test(t);
    }).length;
    console.log(`211 · y es el que se pinta en la fila   -> ${pintados} de ${fechas.length}   ${ok(pintados === fechas.length)}`);

    // ── 212 · la etiqueta ───────────────────────────────────────────────────
    const etiquetas = [];
    for (const f of fechas) {
        const e = page.locator(`[data-testid="dia-vacio-etiqueta-${f}"]`);
        etiquetas.push((await e.count()) ? (await e.innerText()).trim() : '(sin etiqueta)');
    }
    const encajan = etiquetas.filter(t => /^ENCAJA$/i.test(t)).length;
    console.log(`\n212 · no lo lleva el cien por cien      -> ENCAJA en ${encajan} de ${etiquetas.length}   ${ok(encajan < etiquetas.length)}`);
    const conCuadra = fechas.indexOf(CUADRA);
    if (conCuadra >= 0) {
        console.log(`212 · el día que cuadra dice ENCAJA     -> «${etiquetas[conCuadra]}»   ${ok(/^ENCAJA$/i.test(etiquetas[conCuadra]))}`);
    }
    const otros = fechas.map((f, i) => ({ f, t: etiquetas[i], api: api.find(x => x.fecha === f) }))
        .filter(x => !x.api?.encaja);
    const mudos = otros.filter(x => x.t === '(sin etiqueta)' || /^ENCAJA$/i.test(x.t));
    console.log(`212 · los que no encajan dicen por qué  -> ${mudos.length ? mudos.map(x => x.f).join(', ') : 'todos lo dicen'}   ${ok(mudos.length === 0)}`);
    const descanso = otros.find(x => x.api?.motivo === 'otro_dia');
    if (descanso) {
        console.log(`212 · el de otro tipo dice «Otro día»   -> «${descanso.t}»   ${ok(/^OTRO DÍA$/i.test(descanso.t))}`);
    }
    const desviado = otros.find(x => x.api?.motivo === 'desvio');
    if (desviado) {
        const esperado = `${desviado.api.desvio > 0 ? '+' : '−'}${Math.abs(Math.round(desviado.api.desvio))} ${desviado.api.macro}`;
        console.log(`212 · y los demás, por dónde y cuánto   -> «${desviado.t}» (esperado «${esperado}»)   ${ok(desviado.t === esperado)}`);
    }
    // El color sólo en la que encaja: las demás en gris.
    const colores = await page.evaluate((fs) => fs.map((f) => {
        const e = document.querySelector(`[data-testid="dia-vacio-etiqueta-${f}"]`);
        return e ? getComputedStyle(e).color : null;
    }), fechas);
    const naranjas = colores.filter((c, i) => c && /255,\s*(103|90)/.test(c));
    const naranjasMalas = colores.filter((c, i) => c && /255,\s*(103|90)/.test(c) && !(api.find(x => x.fecha === fechas[i]) || {}).encaja);
    console.log(`212 · en color, sólo las que encajan    -> ${naranjas.length} en naranja, ${naranjasMalas.length} de más   ${ok(naranjasMalas.length === 0)}`);

    // ── 213 · la frase de abajo ─────────────────────────────────────────────
    const pie = page.locator('[data-testid="dia-vacio-pie"]');
    const textoPie = (await pie.count()) ? (await pie.innerText()).trim() : '(no sale)';
    console.log(`\n213 · la frase de abajo                 -> «${textoPie}»`);
    console.log(`213 · dice qué pasa, y en orden         ${ok(textoPie === 'Se copian las comidas y se ajustan a tus macros de hoy.')}`);
    console.log(`213 · fuera «se ajusta solo»            ${ok(!/se ajusta solo/i.test(textoPie))}`);
    console.log(`213 · fuera «de este día»               ${ok(!/de este día/i.test(textoPie))}`);

    await page.screenshot({ path: `_guia/_repetir_un_dia_${ancho}.png`, fullPage: true });

    // ── 211 · UNA FUENTE, UN NÚMERO ─────────────────────────────────────────
    // Lo que dice la fila tiene que ser lo mismo que dicen los tres números de arriba al
    // abrir ese día. Se comprueba abriéndolos de verdad, uno a uno, no contra un campo.
    console.log('');
    let cuadran = 0, mirados = 0;
    for (const f of fechas.slice(0, 4)) {
        await page.goto(`${APP}/dashboard/nutrition?date=${f}`, { waitUntil: 'networkidle' }).catch(() => {});
        await page.waitForTimeout(7000);
        await quitarRecorrido(page);
        const leidos = {};
        for (const k of ['P', 'H', 'G']) {
            const t = await page.locator(`[data-testid="dia-${k}"]`).first().innerText().catch(() => '');
            const m = t.replace(/\s+/g, ' ').match(/(-?\d+(?:[.,]\d+)?)/);
            leidos[k] = m ? Math.round(Number(m[1].replace(',', '.'))) : null;
        }
        const fila = api.find(x => x.fecha === f) || {};
        const esperado = { P: Math.round(fila.macros?.P || 0), H: Math.round(fila.macros?.H || 0), G: Math.round(fila.macros?.G || 0) };
        const igual = ['P', 'H', 'G'].every(k => leidos[k] === esperado[k]);
        mirados++; if (igual) cuadran++;
        console.log(`211 · ${f}: fila ${esperado.P}/${esperado.H}/${esperado.G} · cabecera ${leidos.P}/${leidos.H}/${leidos.G}   ${ok(igual)}`);
    }
    console.log(`211 · el mismo número que al abrir      -> ${cuadran} de ${mirados}   ${ok(cuadran === mirados)}`);

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
    if (!habiaCuadra) await p2.request.delete(`${API}/api/diets/${CUADRA}`, { headers: cab });
    await limpio.close();
    console.log(`\n${malas ? malas + ' MAL' : 'todo BIEN'} · día repuesto · captura -> _guia/_repetir_un_dia_${ancho}.png`);
    process.exit(malas ? 1 : 0);
})();
