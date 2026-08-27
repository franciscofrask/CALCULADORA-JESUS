/**
 * PUNTO 178 (27-08): «el mismo día, la grasa dice 40 aquí y 41 en Nutrición».
 *
 * CAUSA. En la cabecera de Nutrición el número grande de grasa se pintaba con
 * `dayMacros.G`, que SÍ lleva la grasa del intra y del post, y se comparaba con un objetivo
 * (`G_total`) que NO la lleva: en el método el objetivo del perientreno no tiene grasa.
 * El Inicio no tenía el fallo -- allí lo montado sale de `servido_comidas`, que el servidor
 * cuenta sin el peri --, así que las dos pantallas enseñaban el mismo día con dos números.
 * `mainG` (día menos peri) ya existía y de él salía el ESTADO del día; solo se pintaba el
 * otro. Arreglado en components/nutrition/DayHeader.jsx.
 *
 * Este guión monta un día con grasa en el Post, mira las dos pantallas y las compara.
 * Deja la cuenta como estaba: si había dieta de hoy, la guarda y la repone al terminar.
 *
 * Uso:  node _guia/_p178_grasa_2708.js [ancho]
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || process.env.DESTINO || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'prueba.elm.2408@test.com';
const CLAVE = process.env.CLAVE || 'QaPrueba2026!';

// Con grasa de sobra, y por 100 g para que la cuenta sea de cabeza.
const GRANOLA = 3150;   // Granola con trozos de fresa (Hacendado): 9,9 P · 67 H · 10 G
const hoy = () => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

// El recorrido de la primera vez es un dialogo a pantalla completa y se come los clics.
// Con una cuenta recien estrenada sale SIEMPRE, asi que se quita antes de mirar nada.
const quitarRecorrido = async (page) => {
    for (let i = 0; i < 4; i++) {
        const s = page.locator('[data-testid="recorrido-saltar"]');
        if (!(await s.count())) break;
        await s.click({ force: true }).catch(() => {});
        await page.waitForTimeout(1200);
    }
    await page.locator('[data-testid="recorrido-overlay"]').waitFor({ state: 'detached', timeout: 8000 }).catch(() => {});
    await page.waitForTimeout(1500);
};

(async () => {
    const ancho = Number(process.argv[2]) || 1280;
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 950 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    const FECHA = hoy();

    const login = await page.request.post(`${API}/api/auth/login`, { data: { email: CUENTA, password: CLAVE } });
    if (!login.ok()) { console.log('no se pudo entrar:', login.status(), await login.text()); await nav.close(); return; }
    const tok = (await login.json()).access_token;
    const cab = { Authorization: `Bearer ${tok}` };

    // ── Lo que había, para reponerlo ────────────────────────────────────────
    const antes = await (await page.request.get(`${API}/api/diets/${FECHA}`, { headers: cab })).json();
    const habia = !!antes.exists;
    console.log(`\n=== PUNTO 178 · ${CUENTA} · ${FECHA} ===`);
    console.log(habia ? '(ya había dieta hoy: se repone al terminar)' : '(no había dieta hoy)');

    // ── El día de prueba: una comida normal y un POST CON GRASA ─────────────
    const comidas = {
        C1: { alimentos: [{ alimento_id: GRANOLA, cantidad_g: 100 }] },
        Post: { alimentos: [{ alimento_id: GRANOLA, cantidad_g: 100 }] },
    };
    const guardar = await page.request.post(`${API}/api/diets`, {
        headers: cab,
        data: { fecha: FECHA, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 0, opcion_peri: 'intra_post', comidas },
    });
    console.log('dia montado ->', guardar.status(), (await guardar.json()).message || '');

    // Lo que dice el SERVIDOR que suman las comidas (sin el peri): la vara de medir.
    const dia = await (await page.request.get(`${API}/api/diets/${FECHA}`, { headers: cab })).json();
    const servido = dia.servido_comidas || {};
    console.log('servido_comidas del servidor (sin peri) -> G =', servido.G);

    // ── La pantalla ─────────────────────────────────────────────────────────
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);

    // Nutrición: el número grande de grasa.
    await page.goto(`${APP}/dashboard/nutrition?date=${FECHA}`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(9000);
    await quitarRecorrido(page);
    await page.waitForSelector('[data-testid="dia-G"]', { timeout: 25000 }).catch(() => {});
    const nutricion = (await page.locator('[data-testid="dia-G"] .numero-grande').first().innerText().catch(() => '?')).trim();
    console.log('\nNUTRICIÓN · grasa creada ->', nutricion);
    await page.screenshot({ path: '_guia/_p178_nutricion.png', fullPage: false });

    // Inicio: pestaña «Dieta», que es la que enseña lo montado.
    await page.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(9000);
    await quitarRecorrido(page);
    await page.waitForSelector('[data-testid="vista-dieta"]', { timeout: 25000 }).catch(() => {});
    await page.locator('[data-testid="vista-dieta"]').click();
    await page.waitForTimeout(2000);
    const inicio = (await page.locator('[data-testid="dieta-hoy-dieta-G"] .numero-grande').first().innerText().catch(() => '?')).trim();
    console.log('INICIO · pestaña Dieta, grasa ->', inicio);
    await page.screenshot({ path: '_guia/_p178_inicio.png', fullPage: false });

    console.log('\n¿DICEN LO MISMO? ->', nutricion === inicio ? `SÍ, las dos ${inicio}` : `NO: Nutrición ${nutricion} vs Inicio ${inicio}`);
    console.log('(la grasa del Post es la que sobraba: 10 g en este día de prueba)');

    // ── Se repone la cuenta ─────────────────────────────────────────────────
    if (habia) {
        const limpio = { fecha: FECHA, tipo_dia: antes.tipo_dia, num_comidas: antes.num_comidas,
            momento_entreno: antes.momento_entreno, opcion_peri: antes.opcion_peri, comidas: antes.comidas };
        const rep = await page.request.post(`${API}/api/diets`, { headers: cab, data: limpio });
        console.log('\ndieta repuesta ->', rep.status());
    } else {
        const bo = await page.request.delete(`${API}/api/diets/${FECHA}`, { headers: cab });
        console.log('\ndia de prueba borrado ->', bo.status());
    }
    await nav.close();
})();
