/**
 * «AL CREAR EL INTRA, LOS GRAMOS SE MUEVEN DE A 1 Y DEBERÍA SER DE A 5» (Francisco, 27-08).
 *
 * El botón − / + tenía su propia tabla y decía «todo lo demás, 1 g»; el servidor
 * (`redondeo_salida.paso_en_gramos`) dice 5. O sea que se subía de gramo en gramo y, en cuanto
 * la app tocaba esa cantidad, se la dejaba en un múltiplo de 5.
 *
 * Se toca el «+» de verdad en el intra y se mira cuánto se mueve. Y de paso una comida normal
 * y una verdura, que tienen que seguir como estaban (50 g la verdura).
 *
 * Deja el día como estaba.
 *
 * Uso:  node _guia/_paso_gramos_2708.js [ancho]
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

// Un alimento por caso, con lo que TIENE que mover el botón.
const CASOS = [
    { donde: 'Intra', nombre: 'ciclodextrina', esperado: 5 },
    { donde: 'C1', nombre: 'pollo', esperado: 5 },
    { donde: 'C1', nombre: 'verdura', esperado: 50 },
];

(async () => {
    const ancho = Number(process.argv[2]) || 1280;
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 950 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: CUENTA, password: CLAVE } });
    const tok = (await r.json()).access_token;
    const cab = { Authorization: `Bearer ${tok}` };

    // Los ids, buscados por nombre para no fiarlos a un número escrito a mano.
    const buscar = async (q) => {
        const res = await (await page.request.get(`${API}/api/calculator/foods-listado`, { headers: cab, timeout: 120000 })).json();
        return res.find(f => new RegExp(q, 'i').test(f.nombre) && !f.unidades);
    };
    const ciclo = await buscar('^Ciclodextrina');
    const pollo = await buscar('^Pechuga de pollo$');
    const brocoli = await buscar('^Br[oó]coli$');
    console.log(`\n=== EL PASO DE LOS GRAMOS · ${ancho} px ===\n`);
    for (const [n, f] of [['intra', ciclo], ['normal', pollo], ['verdura', brocoli]]) {
        console.log(`  ${n.padEnd(8)} ${f ? f.nombre + '  (cat ' + f.categorias + ')' : 'NO ENCONTRADO'}`);
    }
    if (!ciclo || !pollo || !brocoli) { await nav.close(); return; }

    // El alimento como lo guarda la app: la ficha entera, no solo el id.
    const conFicha = (f, g) => ({
        alimento_id: f.id, nombre: f.nombre, cantidad_g: g,
        categorias: f.categorias, unidades: f.unidades, racion: f.racion,
    });

    const d = new Date();
    const FECHA = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    const antes = await (await page.request.get(`${API}/api/diets/${FECHA}`, { headers: cab })).json();
    const habia = !!antes.exists;

    await page.request.post(`${API}/api/diets`, {
        headers: cab,
        data: { fecha: FECHA, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 0,
                opcion_peri: 'intra_post',
                comidas: {
                    // CON SU FICHA DENTRO, como la guarda la app de verdad: el alimento del
                    // dia lleva `categorias`, `unidades` y `racion` (se comprobo contra
                    // produccion). Guardarlo con solo el id hacia que la pantalla no supiera
                    // que el brocoli es una verdura y la prueba mentia.
                    Intra: { alimentos: [conFicha(ciclo, 30)] },
                    C1: { alimentos: [conFicha(pollo, 100), conFicha(brocoli, 100)] },
                } },
    });

    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);
    await page.goto(`${APP}/dashboard/nutrition?date=${FECHA}`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(11000);
    await quitarRecorrido(page);

    // Se toca el «+» de cada ingrediente y se mira cuánto ha subido de verdad.
    // El indice lo controlo yo al montar el dia: Intra[0] = ciclodextrina, C1[0] = pollo,
    // C1[1] = brocoli. Asi no hay que adivinar que fila es cual.
    const mirar = async (comida, idx, esperado, etiqueta) => {
        let qty = page.locator(`[data-testid="qty-${comida}-${idx}"]:visible`).first();
        const tarjeta = page.locator(`[data-testid="meal-card-${comida}"]:visible`).first();
        if (!(await qty.count())) {
            // Plegada: se abre por su cabecera. En escritorio la comida se elige en la
            // columna de la izquierda, asi que primero se selecciona y luego se despliega.
            // En escritorio la comida se elige en la columna de la izquierda y solo se monta
            // la seleccionada; en el movil estan todas en el acordeon y hay que desplegarla.
            await page.locator(`[data-testid="meal-selector"] button`, { hasText: new RegExp(comida === 'C1' ? 'Comida 1' : comida, 'i') }).first().click().catch(() => {});
            await page.waitForTimeout(2500);
            if (await tarjeta.count()) {
                await tarjeta.locator('button:visible').first().click().catch(() => {});
                await page.waitForTimeout(3000);
            }
            qty = page.locator(`[data-testid="qty-${comida}-${idx}"]:visible`).first();
        }
        if (!(await qty.count())) { console.log(`  ${etiqueta}: no sale su cantidad en la ${comida}`); return; }
        const leer = async () => {
            const t = (await qty.innerText()).trim();
            const m = t.match(/(\d+(?:[.,]\d+)?)/);
            return m ? parseFloat(m[1].replace(',', '.')) : null;
        };
        const desde = await leer();
        // El control es [ − ][ cantidad ][ + ]: el «+» es el ultimo boton de esa caja.
        await qty.locator('xpath=..').locator('button').last().click();
        await page.waitForTimeout(3000);
        const hasta = await leer();
        const movio = (hasta != null && desde != null) ? Math.round((hasta - desde) * 10) / 10 : null;
        console.log(`  ${etiqueta.padEnd(16)} ${desde} -> ${hasta}   se mueve de ${movio}   ${ok(movio === esperado)}  (se espera ${esperado})`);
    };

    console.log('\ntocando el «+»:');
    await mirar('Intra', 0, 5, 'ciclodextrina');
    await mirar('C1', 0, 5, 'pollo');
    await mirar('C1', 1, 50, 'brócoli');

    await page.screenshot({ path: `_guia/_paso_gramos_${ancho}.png`, fullPage: true });

    if (habia) {
        await page.request.post(`${API}/api/diets`, { headers: cab,
            data: { fecha: FECHA, tipo_dia: antes.tipo_dia, num_comidas: antes.num_comidas,
                    momento_entreno: antes.momento_entreno, opcion_peri: antes.opcion_peri, comidas: antes.comidas } });
        console.log('\ndía repuesto');
    } else {
        const b = await page.request.delete(`${API}/api/diets/${FECHA}`, { headers: cab });
        console.log('\ndía de prueba borrado ->', b.status());
    }
    await nav.close();
})();
