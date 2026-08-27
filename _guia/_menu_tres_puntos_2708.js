/**
 * «EN LA COMIDA HAY UN BOTÓN DE 3 PUNTOS, AL TOCARLO NO PASA NADA» (Francisco, 27-08).
 *
 * Sí pasaba: el menú se abría y la tarjeta de la comida se lo comía. La tarjeta lleva
 * `overflow-hidden` y el menú colgaba de ella, así que se salía por abajo y lo cortaba.
 * Medido antes del arreglo: de los 106 px que mide, se veían 11.
 *
 * Aquí se comprueban las tres cosas: que se abre, que se VE ENTERO, y que al elegir una
 * opción hace lo que dice (se prueba «Vaciar la comida», que es la que siempre está).
 *
 * Y también el «···» de la cabecera de la pantalla, que usa el mismo menú y no puede
 * romperse al arreglar el otro.
 *
 * Deja el día como estaba.
 *
 * Uso:  node _guia/_menu_tres_puntos_2708.js [ancho]
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
    const pavo = cat.find(f => f.nombre === 'Pechuga de pollo');
    const arroz = cat.find(f => f.nombre === 'Arroz blanco');
    const conFicha = (f, g) => ({ alimento_id: f.id, nombre: f.nombre, cantidad_g: g,
        categorias: f.categorias, unidades: f.unidades, racion: f.racion });

    const d = new Date();
    const FECHA = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    const antes = await (await page.request.get(`${API}/api/diets/${FECHA}`, { headers: cab })).json();
    const habia = !!antes.exists;
    const reponer = async () => {
        if (habia) {
            await page.request.post(`${API}/api/diets`, { headers: cab,
                data: { fecha: FECHA, tipo_dia: antes.tipo_dia, num_comidas: antes.num_comidas,
                        momento_entreno: antes.momento_entreno, opcion_peri: antes.opcion_peri, comidas: antes.comidas } });
        } else {
            await page.request.delete(`${API}/api/diets/${FECHA}`, { headers: cab });
        }
    };

    // Dos alimentos: así el menú lleva las tres opciones y es el más alto que puede salir.
    await page.request.post(`${API}/api/diets`, {
        headers: cab,
        data: { fecha: FECHA, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 0,
                opcion_peri: 'intra_post',
                comidas: { C1: { alimentos: [conFicha(pavo, 150), conFicha(arroz, 80)] } } },
    });

    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);
    await page.goto(`${APP}/dashboard/nutrition?date=${FECHA}`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(11000);
    await quitarRecorrido(page);

    console.log(`\n=== EL «···» DE LA COMIDA · ${ancho} px ===\n`);

    if (!(await page.locator('[data-testid="meal-card-C1"] [data-testid="menu-pantalla"]:visible').count())) {
        await page.locator('[data-testid="meal-card-C1"]:visible').first().locator('button:visible').first().click().catch(() => {});
        await page.waitForTimeout(3000);
    }
    const boton = page.locator('[data-testid="meal-card-C1"] [data-testid="menu-pantalla"]:visible').first();
    console.log(`el botón está en la comida        ${ok(await boton.count() === 1)}`);
    await boton.scrollIntoViewIfNeeded();
    await boton.click();
    await page.waitForTimeout(900);

    const menu = page.locator('[data-testid="menu-pantalla-abierto"]');
    console.log(`se abre                           ${ok(await menu.count() === 1)}`);
    if (await menu.count()) {
        const m = await menu.first().evaluate((el) => {
            const a = el.getBoundingClientRect();
            // ¿Lo recorta alguien? Se mira contra TODOS sus antepasados con overflow.
            let p = el.parentElement, recorte = 0;
            while (p && p !== document.body) {
                const s = getComputedStyle(p);
                if (s.overflow !== 'visible' || s.overflowY !== 'visible') {
                    const b = p.getBoundingClientRect();
                    recorte = Math.max(recorte, Math.round(Math.max(0, a.bottom - b.bottom) + Math.max(0, b.top - a.top)));
                }
                p = p.parentElement;
            }
            const fueraDePantalla = Math.round(Math.max(0, a.bottom - window.innerHeight) + Math.max(0, -a.top));
            return { alto: Math.round(a.height), ancho: Math.round(a.width), recorte, fueraDePantalla,
                     top: Math.round(a.top), bottom: Math.round(a.bottom), alto_ventana: window.innerHeight };
        });
        console.log(`   mide ${m.ancho}x${m.alto} y va de y=${m.top} a y=${m.bottom} (pantalla de ${m.alto_ventana})`);
        console.log(`   lo recorta un antepasado -> ${m.recorte} px   ${ok(m.recorte === 0)}`);
        console.log(`   se sale de la pantalla   -> ${m.fueraDePantalla} px   ${ok(m.fueraDePantalla === 0)}`);
        const opciones = await menu.locator('[role="menuitem"]').allInnerTexts();
        console.log(`   opciones: ${opciones.map(o => o.trim()).join(' · ')}`);
    }
    await page.screenshot({ path: `_guia/_menu_tres_puntos_${ancho}.png` });

    // Y que ELEGIR haga algo: «Vaciar la comida» tiene que preguntar.
    const vaciar = page.locator('[data-testid="menu-pantalla-vaciar-C1"]');
    if (await vaciar.count()) {
        await vaciar.click();
        await page.waitForTimeout(1500);
        const pregunta = await page.locator('text=/vaciar/i').count();
        console.log(`\nal elegir «Vaciar la comida» pasa algo   ${ok(pregunta > 0)}`);
        await page.keyboard.press('Escape').catch(() => {});
    } else {
        console.log('\nno encuentro la opción de vaciar en el menú   MAL');
    }

    // El de la CABECERA, que usa el mismo componente.
    await page.reload({ waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(9000);
    await quitarRecorrido(page);
    const cabecera = page.locator('[data-testid="menu-pantalla"]:visible').first();
    if (await cabecera.count()) {
        await cabecera.click();
        await page.waitForTimeout(900);
        const m2 = page.locator('[data-testid="menu-pantalla-abierto"]');
        console.log(`\nel «···» de la cabecera sigue bien       ${ok(await m2.count() === 1 && await m2.first().isVisible())}`);
        const op2 = await m2.locator('[role="menuitem"]').allInnerTexts().catch(() => []);
        console.log(`   opciones: ${op2.map(o => o.trim().split('\n')[0]).join(' · ')}`);
    }

    await reponer();
    console.log(`\ndía repuesto · captura -> _guia/_menu_tres_puntos_${ancho}.png`);
    await nav.close();
})();
