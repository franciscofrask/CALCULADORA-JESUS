/**
 * «EL NÚMERO CAMBIA SOLO DELANTE DEL CLIENTE» (Francisco, 27-08).
 *
 * Reproduce la secuencia que enseñó: unas almendras en la Comida 1, se les baja la cantidad, y
 * se mira QUÉ NÚMERO SE QUEDA en pantalla comparado con lo que dice el motor.
 *
 * Lo que hay que ver es la diferencia entre:
 *   - lo que pinta la pantalla justo al tocar   (`scaleFood`: una regla de tres)
 *   - lo que pinta 2 segundos después           (`/calibrar-dia`, que es el que manda)
 *   - lo que dice el motor de verdad
 *
 * La calibración es ESCALONADA -- hasta 20 g de la familia en el día no cuenta la proteína, de
 * 20 a 40 la mitad, de 40 en adelante toda -- así que una regla de tres sobre ella da un
 * número que ningún motor daría. Medido contra el catálogo: le pasa a 62 alimentos.
 *
 * Deja el día como estaba.
 *
 * Uso:  node _guia/_tres_motores_2708.js [ancho]
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || process.env.DESTINO || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';

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
    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: CUENTA, password: CLAVE } });
    const tok = (await r.json()).access_token;
    const cab = { Authorization: `Bearer ${tok}`, 'Content-Type': 'application/json' };

    const cat = await (await page.request.get(`${API}/api/calculator/foods-listado`, { headers: cab, timeout: 120000 })).json();
    const alm = cat.find(f => f.nombre === 'Almendras');
    const pavo = cat.find(f => f.nombre === 'Pechuga de pollo');

    const d = new Date();
    const FECHA = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    const antes = await (await page.request.get(`${API}/api/diets/${FECHA}`, { headers: cab })).json();
    const habia = !!antes.exists;

    const conFicha = (f, g) => ({ alimento_id: f.id, nombre: f.nombre, cantidad_g: g,
        categorias: f.categorias, unidades: f.unidades, racion: f.racion });

    // Un día con SOLO estas almendras como fruto seco: así el acumulado del día es el suyo y
    // se puede comparar contra el motor sin adivinar nada.
    await page.request.post(`${API}/api/diets`, {
        headers: cab,
        data: { fecha: FECHA, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 0,
                opcion_peri: 'intra_post',
                comidas: { C1: { alimentos: [conFicha(pavo, 250), conFicha(alm, 45)] } } },
    });

    console.log(`\n=== EL NÚMERO QUE CAMBIA SOLO · ${ancho} px ===\n`);
    console.log(`Almendras: ${alm.categorias}   ·   23 P / 100 g`);
    console.log('La regla: hasta 20 g de frutos secos en el día no cuenta su proteína,');
    console.log('de 20 a 40 la mitad, de 40 en adelante toda.\n');

    // Lo que dice el motor, para cada cantidad, con estas almendras como único fruto seco.
    const delMotor = async (g) => {
        const res = await (await page.request.post(`${API}/api/calculator/calibrar-dia`, {
            headers: cab,
            data: { meal_order: ['C1', 'Intra', 'Post', 'C2', 'C3', 'C4'],
                    comidas: { C1: [{ alimento_id: pavo.id, cantidad_g: 250 }, { alimento_id: alm.id, cantidad_g: g }] } },
        })).json();
        return ((res.comidas?.C1 || [])[1] || {}).macros_efectivos || {};
    };

    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);
    await page.goto(`${APP}/dashboard/nutrition?date=${FECHA}`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(11000);
    await quitarRecorrido(page);

    // Abrir la comida 1 si hace falta.
    let qty = page.locator('[data-testid="qty-C1-1"]:visible').first();
    if (!(await qty.count())) {
        await page.locator('[data-testid="meal-card-C1"]:visible').first().locator('button:visible').first().click().catch(() => {});
        await page.waitForTimeout(3000);
        qty = page.locator('[data-testid="qty-C1-1"]:visible').first();
    }
    if (!(await qty.count())) { console.log('no encuentro la fila de las almendras'); await nav.close(); return; }

    // La proteína que enseña la comida (el número grande de arriba de la tarjeta).
    const proteinaDeLaComida = async () => {
        const e = page.locator('[data-testid="comida-macro-C1-P"]:visible').first();
        if (!(await e.count())) return null;
        const t = await e.innerText();
        const m = t.match(/(\d+(?:[.,]\d+)?)/);
        return m ? parseFloat(m[1].replace(',', '.')) : null;
    };
    const cantidad = async () => {
        const m = (await qty.innerText()).match(/(\d+(?:[.,]\d+)?)/);
        return m ? parseFloat(m[1].replace(',', '.')) : null;
    };

    const bajar = async (veces) => {
        for (let i = 0; i < veces; i++) {
            await qty.locator('xpath=..').locator('button').first().click();   // el «−»
            await page.waitForTimeout(120);
        }
    };
    // Lo que se lee SIN ESPERAR: el recalculo tarda 300 ms en salir, asi que esto es lo que
    // el cliente tiene delante mientras tanto. Es «el numero que cambia solo».

    console.log(`${'cantidad'.padEnd(10)} ${'al tocar'.padEnd(12)} ${'2 s después'.padEnd(14)} ${'el motor'.padEnd(10)}`);
    for (const bajadas of [1, 1, 1, 1, 1]) {
        await bajar(bajadas);
        const alTocar = await proteinaDeLaComida();
        await page.waitForTimeout(4000);
        const despues = await proteinaDeLaComida();
        const g = await cantidad();
        const motor = await delMotor(g);
        // La comida son pavo (50 P fijos) + almendras: se descuenta el pavo para ver la suya.
        const suya = (x) => (x == null ? '?' : Math.round((x - 50) * 10) / 10);
        console.log(`${(g + ' g').padEnd(10)} ${String(suya(alTocar)).padEnd(12)} ${String(suya(despues)).padEnd(14)} ${String(motor.P).padEnd(10)}   ${suya(despues) === motor.P ? '' : '  <-- NO COINCIDEN'}`);
    }

    await page.screenshot({ path: `_guia/_tres_motores_${ancho}.png`, fullPage: true });
    if (habia) {
        await page.request.post(`${API}/api/diets`, { headers: cab,
            data: { fecha: FECHA, tipo_dia: antes.tipo_dia, num_comidas: antes.num_comidas,
                    momento_entreno: antes.momento_entreno, opcion_peri: antes.opcion_peri, comidas: antes.comidas } });
        console.log('\ndía repuesto');
    } else {
        await page.request.delete(`${API}/api/diets/${FECHA}`, { headers: cab });
        console.log('\ndía de prueba borrado');
    }
    await nav.close();
})();
