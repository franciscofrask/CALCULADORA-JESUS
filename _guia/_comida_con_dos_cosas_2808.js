/**
 * LA COMIDA CON DOS COSAS · puntos 198 y 200 (parte 6 del 28-08).
 *
 *   198  cuando algo SOBRA y algo FALTA, se cantan los dos. El que sobra manda y va
 *        primero, con su punto y en naranja; el que falta detrás, sin punto y sin color.
 *   200  y el número de fuera es el mismo que el de dentro, con su decimal.
 *
 * Reproduce el caso de la Comida 4 del 27: se monta una comida que se pasa de hidratos y
 * se queda corta de grasa, y se lee lo que dice la lista y lo que dice la comida abierta.
 * Repone el día al terminar.
 *
 * Uso:  node _guia/_comida_con_dos_cosas_2808.js [ancho]
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const POLLO = 498, ARROZ = 1657, ACEITE = 3;

let malas = 0;
const ok = (b) => { if (!b) malas++; return b ? 'BIEN' : 'MAL '; };
const esNaranja = (c) => /255,\s*(103|90)/.test(c || '');

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

    const d = new Date();
    const HOY = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    console.log(`\n=== LA COMIDA CON DOS COSAS · ${ancho} px ===\n`);

    const antes = await (await page.request.get(`${API}/api/diets/${HOY}`, { headers: cab })).json();
    const habia = !!antes.exists;

    // El objetivo de la comida 1 para poder pasarse de hidratos y quedarse corto de grasa.
    const rep = await (await page.request.post(`${API}/api/calculator/distribute`, { headers: cab,
        data: { fecha: HOY, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 0,
                opcion_peri: 'sin_peri', single_meal: false } })).json();
    const obj = (rep.comidas || {}).C1 || { P: 40, H: 40, G: 15 };
    console.log(`el objetivo de la Comida 1: ${Math.round(obj.P)}P · ${Math.round(obj.H)}H · ${Math.round(obj.G)}G`);

    // Arroz de sobra (hidratos por encima) y nada de aceite (grasa por debajo).
    const gArroz = Math.round(((obj.H + 12) / 77) * 100);       // el arroz ronda 77 g de hidratos por 100
    const gPollo = Math.round((obj.P / 23) * 100);              // y el pollo, 23 g de proteína por 100
    await page.request.delete(`${API}/api/diets/${HOY}`, { headers: cab });
    await page.request.post(`${API}/api/diets`, { headers: cab,
        data: { fecha: HOY, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 0,
                opcion_peri: 'sin_peri',
                comidas: { C1: { alimentos: [
                    { alimento_id: POLLO, cantidad_g: gPollo },
                    { alimento_id: ARROZ, cantidad_g: gArroz },
                ] } } } });

    // La forma de ver las comidas se guarda en la FICHA, no solo en el navegador: si una
    // pasada anterior la dejó en «todo seguido», las tarjetas salen abiertas y el estado
    // cerrado no existe. Se pone la de siempre a propósito.
    await page.request.post(`${API}/api/user/ajustes-app`, { headers: cab, data: { vista: 'actual' } });

    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);
    await page.goto(`${APP}/dashboard/nutrition?date=${HOY}`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(9000);
    await quitarRecorrido(page);

    // LA TARJETA CERRADA CON SU FRASE ES DEL MÓVIL. En el ordenador la lista de la
    // izquierda enseña el estado con un punto y las barras, y las palabras salen dentro de
    // la comida, una por macro (punto 120: con la comida abierta el estado no se repite).
    // Así que cada tamaño se comprueba por donde el cliente lo ve.
    if (ancho >= 1024) {
        console.log('\n-- en el ordenador: las palabras van dentro de la comida --');
        for (const k of ['H', 'G']) {
            const e = page.locator(`[data-testid="comida-palabra-C1-${k}"]`).first();
            if (!(await e.count())) { console.log(`   ${k}: no sale   ${ok(false)}`); continue; }
            const t = (await e.innerText()).trim();
            const c = await e.evaluate(el => getComputedStyle(el).color);
            console.log(`   ${k}: «${t}» · ${c}`);
            if (k === 'H') console.log(`198 · los hidratos, que se pasan, en naranja ${ok(/sobran/i.test(t) && esNaranja(c))}`);
            if (k === 'G') console.log(`198 · la grasa, que falta, sin color         ${ok(/faltan/i.test(t) && !esNaranja(c))}`);
        }
        console.log(`198 · y las dos se ven a la vez              ${ok(true)}`);
        await page.screenshot({ path: `_guia/_comida_dos_cosas_${ancho}.png`, fullPage: true });
        await nav.close();
        const l2 = await chromium.launch();
        const q = await (await l2.newContext()).newPage();
        await q.request.delete(`${API}/api/diets/${HOY}`, { headers: cab });
        if (habia) {
            await q.request.post(`${API}/api/diets`, { headers: cab,
                data: { fecha: HOY, tipo_dia: antes.tipo_dia, num_comidas: antes.num_comidas,
                        momento_entreno: antes.momento_entreno, opcion_peri: antes.opcion_peri, comidas: antes.comidas } });
        }
        await l2.close();
        console.log(`\n${malas ? malas + ' MAL' : 'todo BIEN'} · día repuesto · captura -> _guia/_comida_dos_cosas_${ancho}.png`);
        process.exit(malas ? 1 : 0);
    }

    const est = page.locator('[data-testid="estado-comida-C1"]').first();
    if (!(await est.count())) {
        console.log(`el estado de la Comida 1 no sale   ${ok(false)}`);
    } else {
        const crudo = (await est.innerText()).trim();
        const texto = crudo.replace(/\s+/g, ' ');
        const lineas = crudo.split('\n').map(s => s.trim()).filter(Boolean);
        console.log(`\n198 · el estado de la Comida 1     -> «${texto}»`);
        console.log(`198 · canta lo que SOBRA               ${ok(/sobran/i.test(texto))}`);
        console.log(`198 · y también lo que FALTA           ${ok(/faltan/i.test(texto))}`);
        console.log(`198 · lo que sobra va primero          ${ok(texto.indexOf('sobran') < texto.indexOf('faltan'))}`);
        console.log(`198 · cada uno en su línea             -> ${lineas.length} líneas   ${ok(lineas.length === 2)}`);
        console.log(`198 · y sin separadores de más         ${ok(!/·/.test(crudo))}`);
        const trozos = await est.locator('> span').all();
        const detalle = [];
        for (const t of trozos) {
            detalle.push({ t: (await t.innerText()).replace(/\s+/g, ' ').trim(),
                           c: await t.evaluate(el => getComputedStyle(el).color),
                           p: await t.locator('span.rounded-full').count() });
        }
        for (const x of detalle) console.log(`      «${x.t}» · ${x.c} · puntos ${x.p}`);
        const sob = detalle.find(x => /sobran/i.test(x.t));
        const fal = detalle.find(x => /faltan/i.test(x.t));
        console.log(`198 · lo que sobra, naranja y con punto ${ok(Boolean(sob) && esNaranja(sob.c) && sob.p === 1)}`);
        console.log(`198 · lo que falta, sin color y sin punto ${ok(Boolean(fal) && !esNaranja(fal.c) && fal.p === 0)}`);

        // ── 200 · el mismo número fuera y dentro, macro a macro ─────────────
        const NOMBRE = { P: 'proteína', H: 'hidratos', G: 'grasa' };
        const deFuera = {};
        for (const [k, n] of Object.entries(NOMBRE)) {
            const m = crudo.match(new RegExp(`([\\d,]+) de ${n}`, 'i'));
            if (m) deFuera[k] = m[1];
        }
        await page.locator('[data-testid="meal-card-C1"]').first().scrollIntoViewIfNeeded().catch(() => {});
        if (!(await page.locator('[data-testid="comida-palabra-C1-H"]').first().count())) {
            await page.locator('[data-testid="meal-card-C1"] button').first().click().catch(() => {});
            await page.waitForTimeout(2500);
        }
        console.log('');
        let cuadran = 0, mirados = 0;
        for (const k of ['P', 'H', 'G']) {
            const e = page.locator(`[data-testid="comida-palabra-C1-${k}"]`).first();
            if (!(await e.count()) || !deFuera[k]) continue;
            const dentro = (await e.innerText()).trim();
            const nDentro = (dentro.match(/([\d,]+)/) || [])[1];
            mirados++;
            const igual = deFuera[k] === nDentro;
            if (igual) cuadran++;
            console.log(`200 · ${NOMBRE[k]}: fuera «${deFuera[k]}» · dentro «${dentro}»   ${ok(igual)}`);
        }
        console.log(`200 · el mismo número en los dos sitios -> ${cuadran} de ${mirados}   ${ok(mirados > 0 && cuadran === mirados)}`);
    }

    await page.screenshot({ path: `_guia/_comida_dos_cosas_${ancho}.png`, fullPage: true });

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
    console.log(`\n${malas ? malas + ' MAL' : 'todo BIEN'} · día repuesto · captura -> _guia/_comida_dos_cosas_${ancho}.png`);
    process.exit(malas ? 1 : 0);
})();
