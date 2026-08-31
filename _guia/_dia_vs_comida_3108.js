/**
 * «SOLO HAY UNA COMIDA CARGADA, OSEA ESOS SON LOS UNICOS MACROS CUBIERTOS PERO NO COINCIDEN»
 * (Francisco, 31-08-2026).
 *
 * Con una sola comida montada, el bloque del día y el de la comida están contando lo mismo.
 * Esto lee LOS DOS de la pantalla y los pone al lado, y además saca los macros crudos del
 * estado para ver si la diferencia es de cálculo o solo de cómo se pinta.
 *
 * Uso:  node _guia/_dia_vs_comida_3108.js
 */
const fs = require('fs');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';

const FECHA = '2026-12-23';
const CARPETA = '_guia/_dia_vs_comida';
if (!fs.existsSync(CARPETA)) fs.mkdirSync(CARPETA, { recursive: true });

// La comida de la captura: catorce alimentos, solo en la C1.
const COMIDA = [
    [110, 'Calabacín', 100], [642, 'Solomillo de pavo', 50], [2828, 'Arroz tres delicias', 240],
    [2018, 'Almendras', 20], [4, 'Aceite de oliva', 5], [2906, 'Arroz negro', 80],
    [10003, 'Filete de cerdo empanado', 25], [2875, 'Albóndigas pollo y pavo', 50],
    [2959, 'Albóndigas de cerdo', 25], [3040, 'Albóndigas de pollo', 50],
    [749, 'Alas de pollo adobadas', 50], [2867, 'Bacon', 100],
    [1353, 'Brochetas de pollo', 50], [2652, 'Carne picada de cerdo', 25],
].map(([id, nombre, cantidad_g]) => ({ id, alimento_id: id, nombre, cantidad_g }));

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

(async () => {
    TOKEN = (await pide('/auth/login', { method: 'POST',
        body: JSON.stringify({ email: CUENTA, password: CLAVE }) })).access_token;
    if (!TOKEN) { console.log('no he podido entrar'); return; }

    await pide(`/diets/${FECHA}`, { method: 'DELETE' }).catch(() => {});
    await pide('/diets', { method: 'POST', body: JSON.stringify({
        fecha: FECHA, tipo_dia: 'entrenamiento', num_comidas: 4,
        momento_entreno: 1, opcion_peri: 'intra_post',
        comidas: { C1: { alimentos: COMIDA } },
    }) });

    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: 1500, height: 1100 }, deviceScaleFactor: 2 });
    const p = await ctx.newPage();
    await p.goto(APP, { waitUntil: 'domcontentloaded' });
    await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, TOKEN);
    await p.goto(`${APP}/dashboard/nutrition?date=${FECHA}`, { waitUntil: 'networkidle' }).catch(() => {});
    await p.waitForTimeout(10000);
    for (let i = 0; i < 4; i++) {
        const s = p.locator('[data-testid="recorrido-saltar"]');
        if (!(await s.count())) break;
        await s.click({ force: true }).catch(() => {});
        await p.waitForTimeout(900);
    }
    await p.waitForTimeout(2000);

    const leer = async (sel) => {
        const el = p.locator(sel).first();
        if (!(await el.count())) return '(no está)';
        return (await el.innerText()).replace(/\s+/g, ' ').trim();
    };

    console.log('\n── EL BLOQUE DEL DÍA (arriba) ──');
    for (const k of ['P', 'H', 'G']) console.log(`   ${k}: ${await leer(`[data-testid="dia-${k}"]`)}`);

    console.log('\n── EL BLOQUE DE LA COMIDA 1 ──');
    for (const k of ['P', 'H', 'G']) console.log(`   ${k}: ${await leer(`[data-testid="comida-macro-C1-${k}"]`)}`);

    // Y los macros CRUDOS: lo que suman los alimentos del día, sin redondear. Si estos
    // coinciden, lo que no coincide es cómo se pintan.
    const crudos = await pide(`/diets/${FECHA}`);
    const suma = (crudos.comidas?.C1?.alimentos || []).reduce((s, a) => ({
        P: s.P + (a.macros_efectivos?.P || 0),
        H: s.H + (a.macros_efectivos?.H || 0),
        G: s.G + (a.macros_efectivos?.G || 0),
    }), { P: 0, H: 0, G: 0 });
    console.log('\n── LO QUE SUMAN DE VERDAD LOS ALIMENTOS DE LA C1 ──');
    console.log(`   P ${suma.P.toFixed(3)}   H ${suma.H.toFixed(3)}   G ${suma.G.toFixed(3)}`);
    console.log('   (no hay más comidas con alimentos, así que el día tiene que ser esto mismo)');

    await p.screenshot({ path: `${CARPETA}/dia_vs_comida.png`, fullPage: false });
    await pide(`/diets/${FECHA}`, { method: 'DELETE' });
    console.log(`\n(día de pruebas borrado: ${(await pide(`/diets/${FECHA}`)).exists ? 'NO' : 'sí'})`);
    await nav.close();
})();
