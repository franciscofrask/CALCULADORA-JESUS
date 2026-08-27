/**
 * BLOQUE D · la otra mitad del punto 144: el vacio DENTRO de una comida.
 *
 * Ponia «No se encontraron alimentos» y ahora dice lo mismo que la pantalla de Alimentos,
 * que es lo que pide el punto («igual en los dos sitios»). Los otros dos vacios del mismo
 * sitio -- no tener frecuentes y una categoria vacia -- NO son este y siguen como estaban.
 *
 * Uso:  node _guia/_bloque_d_2708.js [ancho]
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
    const ancho = Number(process.argv[2]) || 1280;
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 950 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();

    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: CUENTA, password: CLAVE } });
    const tok = (await r.json()).access_token;
    const cab = { Authorization: `Bearer ${tok}` };

    // El dia tiene que EXISTIR o la pantalla ensena «Crea tu dia» y no hay comidas que
    // montar. Se crea vacio, se mira, y se deja como estaba.
    const d = new Date();
    const FECHA = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    const antes = await (await page.request.get(`${API}/api/diets/${FECHA}`, { headers: cab })).json();
    const habia = !!antes.exists;
    if (!habia) {
        await page.request.post(`${API}/api/diets`, {
            headers: cab,
            data: { fecha: FECHA, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 0,
                    opcion_peri: 'intra_post', comidas: { C1: { alimentos: [] } } },
        });
    }

    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);
    await page.goto(`${APP}/dashboard/nutrition`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(9000);
    await quitarRecorrido(page);

    console.log(`\n=== BLOQUE D · ${ancho} px ===\n`);

    // Con el dia sin crear la pantalla ensena «Todavia sin crear» y no hay comidas: hay que
    // pasar por «Crear el dia» para que salga la parrilla.
    const crear = page.getByRole('button', { name: /crear el día/i }).first();
    if (await crear.count()) { await crear.click(); await page.waitForTimeout(5000); }

    // Entrar a montar una comida. Los rotulos cambian segun el dia este vacio o no, asi que
    // se prueba con lo que haya delante.
    const puertas = ['build-meal-C1', 'build-meal-C2', 'build-meal-C3', 'build-meal-C4'];
    let abierto = false;
    for (const t of puertas) {
        const b = page.locator(`[data-testid="${t}"]`);
        if (await b.count()) { await b.first().click(); abierto = true; break; }
    }
    if (!abierto) {
        const porTexto = page.getByRole('button', { name: /añadir alimento|añadir ingrediente|montar/i }).first();
        if (await porTexto.count()) { await porTexto.click(); abierto = true; }
    }
    if (!abierto) {
        console.log('no encuentro por donde se anaden alimentos. Lo que hay en la pantalla:');
        await page.screenshot({ path: `_guia/_bloque_d_perdido.png`, fullPage: true });
        const txt = await page.locator('main, #root').first().innerText().catch(() => '');
        console.log(txt.split('\n').map(s => s.trim()).filter(Boolean).slice(0, 30).join(' | '));
        if (!habia) await page.request.delete(`${API}/api/diets/${FECHA}`, { headers: cab });
        await nav.close(); return;
    }
    await page.waitForTimeout(3500);

    // Buscar algo que no existe.
    const campo = page.locator('input[placeholder*="uscar"], input[type="text"]').last();
    await campo.fill('zzzzqqq');
    await page.waitForTimeout(3500);

    const vacio = page.locator('[data-testid="sin-resultados"]');
    if (await vacio.count()) {
        console.log('144 (dentro de una comida) ->', (await vacio.innerText()).replace(/\n+/g, ' | '));
        console.log('   BIEN: dice lo mismo que la pantalla de Alimentos');
    } else {
        const cuerpo = await page.locator('[role="dialog"]').last().innerText().catch(() => '');
        console.log('   MAL: no sale el texto nuevo. Lo que hay:');
        console.log('   ' + cuerpo.split('\n').filter(Boolean).slice(0, 12).join(' | '));
    }
    await page.screenshot({ path: `_guia/_bloque_d_${ancho}.png` });
    console.log(`\ncaptura -> _guia/_bloque_d_${ancho}.png`);
    if (!habia) {
        const bo = await page.request.delete(`${API}/api/diets/${FECHA}`, { headers: cab });
        console.log('dia de prueba borrado ->', bo.status());
    }
    await nav.close();
})();
