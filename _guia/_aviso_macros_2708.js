/**
 * EL AVISO DE «TE PASAS», con las palabras de Jesús (vídeo del 27-08, minuto 6:52).
 *
 * Lo lee en voz alta y lo corrige sobre la marcha:
 *   «Este día se pasa de tus macros de ahora»  ->  «...de tus macros ACTUALES»
 *   «...podemos reajustar las cantidades»       ->  «...SIN QUITARTE NADA» (esto ya estaba)
 *   «Y entonces pondríamos recuadrar el día. No. Pondríamos REAJUSTAR.»
 *
 * Monta un día que se pasa de los macros para que el aviso salga, y lo deja como estaba.
 *
 * Uso:  node _guia/_aviso_macros_2708.js
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || process.env.DESTINO || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';

const ok = (b) => (b ? 'BIEN' : 'MAL ');
const ARROZ = 1657;   // arroz blanco: a 2 kg se pasa de cualquier objetivo

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
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: 1280, height: 950 } });
    const page = await ctx.newPage();
    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: CUENTA, password: CLAVE } });
    const tok = (await r.json()).access_token;
    const cab = { Authorization: `Bearer ${tok}` };

    const d = new Date();
    const FECHA = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    console.log('\n=== EL AVISO DE «TE PASAS» ===\n');

    const antes = await (await page.request.get(`${API}/api/diets/${FECHA}`, { headers: cab })).json();
    const habia = !!antes.exists;

    // Un día que se pasa de largo: 2 kg de arroz en la comida 1.
    await page.request.post(`${API}/api/diets`, {
        headers: cab,
        data: { fecha: FECHA, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 0,
                opcion_peri: 'intra_post',
                comidas: { C1: { alimentos: [{ alimento_id: ARROZ, cantidad_g: 2000 }] } } },
    });

    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);
    await page.goto(`${APP}/dashboard/nutrition?date=${FECHA}`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(10000);
    await quitarRecorrido(page);

    const aviso = page.locator('[data-testid="banner-recuadrar"]');
    if (!(await aviso.count())) {
        console.log('el aviso no ha salido: el día no se pasa lo bastante o la pantalla no cargó');
        await page.screenshot({ path: '_guia/_aviso_macros.png' });
    } else {
        const texto = (await aviso.innerText()).replace(/\n+/g, ' | ');
        console.log('el aviso dice:');
        console.log('   ' + texto);
        console.log();
        console.log(`«macros actuales», no «de ahora»   ${ok(/de tus macros actuales/i.test(texto) && !/de ahora/i.test(texto))}`);
        console.log(`«sin quitarte nada»                ${ok(/sin quitarte nada/i.test(texto))}`);
        const boton = (await page.locator('[data-testid="boton-recuadrar-dia"]').innerText()).trim();
        console.log(`el botón dice «${boton}»              ${ok(boton === 'Reajustar')}`);
        await page.screenshot({ path: '_guia/_aviso_macros.png' });
    }

    if (habia) {
        await page.request.post(`${API}/api/diets`, {
            headers: cab,
            data: { fecha: FECHA, tipo_dia: antes.tipo_dia, num_comidas: antes.num_comidas,
                    momento_entreno: antes.momento_entreno, opcion_peri: antes.opcion_peri,
                    comidas: antes.comidas },
        });
        console.log('\ndía repuesto');
    } else {
        const b = await page.request.delete(`${API}/api/diets/${FECHA}`, { headers: cab });
        console.log('\ndía de prueba borrado ->', b.status());
    }
    console.log('captura -> _guia/_aviso_macros.png');
    await nav.close();
})();
