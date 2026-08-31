/**
 * LOS DOS FALLOS DEL 31-08, COMPROBADOS EN LA APP DE VERDAD.
 *
 *   1) Una favorita de 3 comidas pedía el reparto para 4: los objetivos por comida salían
 *      bajos y al día le faltaba una cuarta parte que no se pinta en ningún sitio.
 *   2) Aplicar una favorita (o copiar un día) dejaba dentro las comidas que la favorita no
 *      trae: desaparecían de la pantalla, pero volvían al recargar.
 *
 * Monta el escenario en dos fechas sueltas de la cuenta de pruebas, lo mira con el navegador
 * y lo borra todo al terminar. No toca ningún día real.
 *
 * Uso:  node _guia/_verificar_favoritas_3108.js
 */
const fs = require('fs');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';

const ORIGEN = '2026-12-15';    // de donde sale la favorita
const DESTINO = '2026-12-16';   // el día que recibe la favorita, con lentejas dentro
const TERCERO = '2026-12-17';   // el que recibe la copia, también con lentejas dentro
const CARPETA = '_guia/_favoritas_3108';
if (!fs.existsSync(CARPETA)) fs.mkdirSync(CARPETA, { recursive: true });

const POLLO = { id: 498, nombre: 'Pechuga de pollo' };
const LENTEJAS = { id: 366, nombre: 'Lentejas cocidas (Hacendado)' };
const MERLUZA = { id: 1656, nombre: 'Merluza' };

let TOKEN = '';
const pide = async (ruta, opciones = {}) => {
    const r = await fetch(`${API}/api${ruta}`, {
        ...opciones,
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${TOKEN}`,
                   ...(opciones.headers || {}) },
    });
    const t = await r.text();
    try { return JSON.parse(t); } catch { return { _status: r.status, _texto: t }; }
};

const comidaCon = (f, g) => ({ alimentos: [{ id: f.id, alimento_id: f.id, nombre: f.nombre, cantidad_g: g }] });

(async () => {
    TOKEN = (await pide('/auth/login', { method: 'POST',
        body: JSON.stringify({ email: CUENTA, password: CLAVE }) })).access_token;
    if (!TOKEN) { console.log('no he podido entrar'); return; }

    // ── Escenario ────────────────────────────────────────────────────────────
    await pide(`/diets/${ORIGEN}`, { method: 'DELETE' }).catch(() => {});
    await pide(`/diets/${DESTINO}`, { method: 'DELETE' }).catch(() => {});

    const configuracion = { tipo_dia: 'entrenamiento', num_comidas: 3,
                            momento_entreno: 1, opcion_peri: 'intra_post' };

    // El día de ORIGEN: tres comidas, SIN peri (como las favoritas «de descanso» del cliente).
    await pide('/diets', { method: 'POST', body: JSON.stringify({
        fecha: ORIGEN, ...configuracion,
        comidas: { C1: comidaCon(MERLUZA, 200), C2: comidaCon(MERLUZA, 200), C3: comidaCon(MERLUZA, 200) },
    }) });
    const fav = await pide('/diets/favorites', { method: 'POST', body: JSON.stringify({
        name: 'PRUEBA 3108 tres comidas', ...configuracion,
        comidas: { C1: comidaCon(MERLUZA, 200), C2: comidaCon(MERLUZA, 200), C3: comidaCon(MERLUZA, 200) },
    }) });
    const favId = fav.id || fav.favorite?.id;

    // El día de DESTINO: tres comidas Y peri, con LENTEJAS en el intra.
    await pide('/diets', { method: 'POST', body: JSON.stringify({
        fecha: DESTINO, ...configuracion,
        comidas: {
            C1: comidaCon(POLLO, 150), C2: comidaCon(POLLO, 150), C3: comidaCon(POLLO, 150),
            Intra: comidaCon(LENTEJAS, 250), Post: comidaCon(POLLO, 100),
        },
    }) });

    // ── Navegador ────────────────────────────────────────────────────────────
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: 1500, height: 1100 }, deviceScaleFactor: 2 });
    const p = await ctx.newPage();
    const errores = [];
    p.on('console', (m) => { if (m.type() === 'error') errores.push(m.text().slice(0, 200)); });

    // Lo que la pantalla le pide al servidor al aplicar la favorita: aquí se veía el `4`.
    let pedido = null;
    p.on('request', (r) => {
        if (r.url().includes('/calculator/refit-diet') && r.method() === 'POST') {
            try { pedido = JSON.parse(r.postData() || '{}'); } catch { /* nada */ }
        }
    });

    const abrir = async (fecha) => {
        await p.goto(APP, { waitUntil: 'domcontentloaded' });
        await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, TOKEN);
        await p.goto(`${APP}/dashboard/nutrition?date=${fecha}`, { waitUntil: 'networkidle' }).catch(() => {});
        await p.waitForTimeout(9000);
        for (let i = 0; i < 4; i++) {
            const s = p.locator('[data-testid="recorrido-saltar"]');
            if (!(await s.count())) break;
            await s.click({ force: true }).catch(() => {});
            await p.waitForTimeout(900);
        }
        await p.waitForTimeout(1500);
    };

    const objetivos = async () => {
        const salida = {};
        for (const k of ['C1', 'C2', 'C3', 'C4', 'Intra', 'Post']) {
            const el = p.locator(`[data-testid="objetivo-${k}"]`).first();
            if (await el.count()) salida[k] = (await el.innerText()).replace(/\s+/g, ' ').trim();
        }
        return salida;
    };
    const comidasPintadas = async () => Promise.all(
        (await p.locator('[data-testid^="meal-card-"]').all())
            .map(async (c) => (await c.getAttribute('data-testid')).replace('meal-card-', '')));

    /** Qué hay DENTRO de cada comida, leído de la tarjeta (las plegadas también). */
    const loQueHayDentro = async () => {
        const salida = {};
        for (const c of await p.locator('[data-testid^="meal-card-"]').all()) {
            const k = (await c.getAttribute('data-testid')).replace('meal-card-', '');
            const t = (await c.innerText()).replace(/\s+/g, ' ');
            salida[k] = [POLLO, LENTEJAS, MERLUZA].filter((f) => t.includes(f.nombre))
                .map((f) => f.nombre).join(', ') || '(nada a la vista)';
        }
        return salida;
    };

    /** El «···» de la CABECERA, no el de una comida. */
    const abrirMenuDeLaPantalla = async () => {
        const cabecera = p.locator('[data-testid="menu-pantalla"]').first();
        await cabecera.click();
        await p.waitForTimeout(700);
    };

    await abrir(DESTINO);
    console.log('\n── El día de destino, ANTES ──');
    console.log('   comidas :', (await comidasPintadas()).join(' · '));
    console.log('   objetivos:', JSON.stringify(await objetivos(), null, 0));
    console.log('   dentro   :', JSON.stringify(await loQueHayDentro(), null, 0));
    await p.screenshot({ path: `${CARPETA}/1_antes.png`, fullPage: true });

    // Aplicar la favorita desde la pantalla, como lo hace el cliente.
    await abrirMenuDeLaPantalla();
    await p.locator('[data-testid="menu-pantalla-favoritas"]').click().catch(() => {});
    await p.waitForTimeout(2500);
    const aplicar = p.locator(`[data-testid="fav-apply-${favId}"]`);
    if (!(await aplicar.count())) {
        console.log('\n   NO ENCUENTRO EL BOTÓN DE APLICAR. Dejo captura y sigo.');
        await p.screenshot({ path: `${CARPETA}/x_sin_boton.png`, fullPage: true });
    } else {
        await aplicar.click();
        await p.waitForTimeout(6000);
    }

    console.log('\n── Lo que la pantalla le pidió al servidor ──');
    console.log('   num_comidas:', pedido?.num_comidas,
        pedido?.num_comidas === 3 ? '  (BIEN: las tres que tiene el día)' : '  <-- MAL');
    console.log('   comidas    :', Object.keys(pedido?.comidas || {}).join(' · '));

    const avisos = await p.locator('[data-sonner-toast], [role="status"]').allInnerTexts().catch(() => []);
    console.log('\n── Lo que le dice la app al cliente ──');
    avisos.map(t => t.replace(/\s+/g, ' ').trim()).filter(Boolean).forEach(t => console.log('   ·', t));

    console.log('\n── El día de destino, DESPUÉS de aplicar la favorita ──');
    console.log('   comidas :', (await comidasPintadas()).join(' · '));
    console.log('   objetivos:', JSON.stringify(await objetivos(), null, 0));
    console.log('   dentro   :', JSON.stringify(await loQueHayDentro(), null, 0));
    await p.screenshot({ path: `${CARPETA}/2_aplicada.png`, fullPage: true });

    // Y ahora lo que de verdad importa: recargar. Aquí es donde volvían las lentejas.
    await p.waitForTimeout(5000);   // que llegue el autoguardado
    await abrir(DESTINO);
    const dentroDespues = await loQueHayDentro();
    const lentejasDespues = Object.values(dentroDespues).some((t) => t.includes(LENTEJAS.nombre));
    console.log('\n── Tras recargar ──');
    console.log('   comidas :', (await comidasPintadas()).join(' · '));
    console.log('   dentro  :', JSON.stringify(dentroDespues, null, 0));
    console.log('   lentejas:', lentejasDespues ? 'SIGUEN AHÍ  <-- MAL' : 'no están  (BIEN)');
    await p.screenshot({ path: `${CARPETA}/3_tras_recargar.png`, fullPage: true });

    const guardado = await pide(`/diets/${DESTINO}`);
    console.log('\n   lo que hay guardado en el servidor:');
    Object.entries(guardado.comidas || {}).forEach(([k, c]) =>
        console.log(`      ${k.padEnd(6)} ${(c.alimentos || []).map(a => a.nombre).join(', ') || '(vacía)'}`));

    // ── «Copiar a otro día» ──────────────────────────────────────────────────
    // El cartel promete que la dieta del destino «se sustituye». Se comprueba copiando
    // encima de un día que tiene lentejas en una comida que el origen no lleva.
    console.log('\n── Copiar a otro día ──');
    await pide(`/diets/${TERCERO}`, { method: 'DELETE' }).catch(() => {});
    await pide('/diets', { method: 'POST', body: JSON.stringify({
        fecha: TERCERO, ...configuracion,
        comidas: {
            C1: comidaCon(POLLO, 150), C2: comidaCon(POLLO, 150), C3: comidaCon(LENTEJAS, 250),
            Intra: comidaCon(LENTEJAS, 100), Post: comidaCon(POLLO, 100),
        },
    }) });
    // El origen: el día que acabamos de dejar con solo C1..C3 (sin peri).
    await abrir(DESTINO);
    await abrirMenuDeLaPantalla();
    await p.locator('[data-testid="menu-pantalla-copiar"]').click().catch(() => {});
    await p.waitForTimeout(1200);
    await p.locator('input[type="date"]').last().fill(TERCERO).catch(() => {});
    await p.waitForTimeout(600);
    await p.locator('button:has-text("Copiar"), button:has-text("Sustituirla")').last().click().catch(() => {});
    await p.waitForTimeout(1200);
    // El diálogo de confirmación («ya tiene dieta»)
    await p.locator('button:has-text("Sustituirla")').last().click().catch(() => {});
    await p.waitForTimeout(3500);
    const copiado = await pide(`/diets/${TERCERO}`);
    console.log('   el día destino de la copia, después:');
    Object.entries(copiado.comidas || {}).forEach(([k, c]) =>
        console.log(`      ${k.padEnd(6)} ${(c.alimentos || []).map(a => a.nombre).join(', ') || '(vacía)'}`));
    const quedanLentejas = Object.values(copiado.comidas || {}).some(
        (c) => (c.alimentos || []).some((a) => (a.nombre || '').includes('Lentejas')));
    console.log('   lentejas del día que se sustituyó:',
        quedanLentejas ? 'SIGUEN AHÍ  <-- MAL' : 'no están  (BIEN)');

    if (errores.length) console.log('\n   errores de consola:', errores.slice(0, 5));

    // ── Se recoge ────────────────────────────────────────────────────────────
    if (favId) await pide(`/diets/favorites/${favId}`, { method: 'DELETE' });
    for (const f of [ORIGEN, DESTINO, TERCERO]) await pide(`/diets/${f}`, { method: 'DELETE' });
    const quedan = [];
    for (const f of [ORIGEN, DESTINO, TERCERO]) if ((await pide(`/diets/${f}`)).exists) quedan.push(f);
    console.log(`\n(escenario borrado: ${quedan.length ? 'NO, quedan ' + quedan.join(', ') : 'sí'})`);
    console.log(`capturas en ${CARPETA}/`);
    await nav.close();
})();
