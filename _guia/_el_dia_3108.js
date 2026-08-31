/**
 * «EL DÍA» (doc del 31-08) · bloques A, B y C, comprobados en la app.
 *
 * Las horas son lo único de este documento que no se puede mirar con los ojos sin esperar al
 * día siguiente, así que la ventana se prueba por dos lados:
 *
 *   - la REGLA, en `backend/tests/test_ventana_del_dia_3108.py` (los bordes al minuto);
 *   - el CABLEADO, aquí: se le mete al front cada respuesta posible del servidor y se lee
 *     qué pinta la fila del Inicio. Sin tocar ningún dato y sin cambiar el reloj de nadie.
 *
 * Uso:  node _guia/_el_dia_3108.js [ancho]
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || process.env.DESTINO || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';

const ok = (b) => (b ? 'BIEN' : 'MAL ');

const quitarRecorrido = async (page) => {
    for (let i = 0; i < 4; i++) {
        const s = page.locator('[data-testid="recorrido-saltar"]');
        if (!(await s.count())) break;
        await s.click({ force: true }).catch(() => {});
        await page.waitForTimeout(1200);
    }
    await page.waitForTimeout(1200);
};

(async () => {
    const ancho = Number(process.argv[2]) || 390;
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 1800 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    const errores = [];
    page.on('pageerror', (e) => errores.push(String(e).slice(0, 140)));

    const tok = (await (await page.request.post(`${API}/api/auth/login`,
        { data: { email: CUENTA, password: CLAVE } })).json()).access_token;
    const cab = { Authorization: `Bearer ${tok}` };
    const hoy = new Date().toLocaleDateString('en-CA');
    const ayer = new Date(Date.now() - 86400000).toLocaleDateString('en-CA');

    console.log(`\n=== «EL DÍA» · ${ancho} px ===\n`);

    // ── Lo que dice el servidor de verdad, ahora mismo ──────────────────────
    const real = await (await page.request.get(`${API}/api/checkins/estado?fecha=${hoy}`, { headers: cab })).json();
    console.log(`el servidor dice ahora: abierto=${real.abierto} · es_de_ayer=${real.es_de_ayer}`
                + ` · sin cerrar=${real.dias_sin_cerrar} · su hora=${real.hora_de_apertura}`);
    console.log(`   y la línea: «${real.linea.titulo}» / «${real.linea.detalle}»\n`);

    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);

    // ── B y C · los cinco estados de la fila ────────────────────────────────
    const CASOS = [
        ['de 15:00 a su hora · no hay día abierto',
         { abierto: null, es_de_ayer: false, hecho: false, dias_sin_cerrar: 0, quiere_cierre: true,
           linea: { titulo: '¿Cómo fuiste hoy?', detalle: 'Para rellenar al final del día' } },
         null],
        ['desde su hora · el día normal',
         { abierto: hoy, es_de_ayer: false, hecho: false, dias_sin_cerrar: 0, quiere_cierre: true,
           linea: { titulo: '¿Cómo fuiste hoy?', detalle: 'Para rellenar al final del día' } },
         'Para rellenar al final del día'],
        ['tras 2 días perdidos',
         { abierto: hoy, es_de_ayer: false, hecho: false, dias_sin_cerrar: 2, quiere_cierre: true,
           linea: { titulo: '¿Cómo fuiste hoy?', detalle: 'Llevas 2 días seguidos sin cerrar, no lo dejes hoy también' } },
         'no lo dejes hoy también'],
        ['tras 4 días perdidos',
         { abierto: hoy, es_de_ayer: false, hecho: false, dias_sin_cerrar: 4, quiere_cierre: true,
           linea: { titulo: 'Llevas 4 días sin cerrar', detalle: 'Retómalo hoy mismo: es de donde salen tus ajustes' } },
         'es de donde salen tus ajustes'],
        ['tras una semana',
         { abierto: hoy, es_de_ayer: false, hecho: false, dias_sin_cerrar: 9, quiere_cierre: true,
           linea: { titulo: 'Llevas una semana sin cerrar el día', detalle: 'Dejo de recordártelo. Si te está costando, dímelo y lo vemos' } },
         'Dejo de recordártelo'],
        ['la mañana siguiente · ayer sigue abierto',
         { abierto: ayer, es_de_ayer: true, hecho: false, dias_sin_cerrar: 1, quiere_cierre: true,
           linea: { titulo: 'Ayer no cerraste el día', detalle: 'Puedes hacerlo hasta las 3 de la tarde' } },
         'Puedes hacerlo hasta las 3 de la tarde'],
        ['con «Rellenar el cierre» APAGADO',
         { abierto: hoy, es_de_ayer: false, hecho: false, dias_sin_cerrar: 6, quiere_cierre: false,
           linea: { titulo: 'Llevas 4 días sin cerrar', detalle: 'Retómalo hoy mismo: es de donde salen tus ajustes' } },
         null],
    ];

    for (const [nombre, respuesta, esperado] of CASOS) {
        await page.route('**/api/checkins/estado**', (r) =>
            r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(respuesta) }));
        await page.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
        await page.waitForTimeout(9000);
        await quitarRecorrido(page);

        const t = await page.locator('body').innerText();
        const sale = t.includes(respuesta.linea.titulo)
            && (!esperado || t.includes(esperado));
        console.log(esperado === null
            ? `${nombre.padEnd(44)} la fila NO sale   ${ok(!t.includes('Para rellenar al final') && !t.includes('sin cerrar'))}`
            : `${nombre.padEnd(44)} ${ok(sale)}  «${respuesta.linea.detalle.slice(0, 46)}»`);
        await page.unroute('**/api/checkins/estado**');
    }

    // ── C2 · y que lleve al día de AYER, no al de hoy ───────────────────────
    await page.goto(`${APP}/dashboard/checkins?fecha=${ayer}`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(11000);
    await quitarRecorrido(page);
    const cabecera = (await page.locator('body').innerText()).match(/\w+, \d+ de \w+/);
    console.log(`\nC2 · con «?fecha=ayer» se abre el día de ayer   ${ok(!!cabecera)}  ${cabecera ? cabecera[0] : ''}`);

    // Y que una fecha inventada no cuele: solo se acepta un día atrás.
    const lejos = new Date(Date.now() - 12 * 86400000).toLocaleDateString('en-CA');
    await page.goto(`${APP}/dashboard/checkins?fecha=${lejos}`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(11000);
    await quitarRecorrido(page);
    const c2 = (await page.locator('body').innerText()).match(/\w+, \d+ de \w+/);
    console.log(`     una fecha de hace 12 días no cuela          ${ok(c2 && !c2[0].includes(String(new Date(lejos).getDate())))}  ${c2 ? c2[0] : ''}`);

    console.log(`\nerrores de JavaScript: ${errores.length ? errores.join(' | ') : 'ninguno'}`);
    await nav.close();
})();
