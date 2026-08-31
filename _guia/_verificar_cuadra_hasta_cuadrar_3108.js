/**
 * «LOS MACROS TIENEN QUE QUEDAR CUADRADOS, ESE ES EL OBJETIVO DEL BOTÓN» (Francisco, 31-08).
 *
 * Reproduce SU comida: catorce alimentos que con todo a su mínimo pesable siguen dando 50 g
 * de grasa contra un objetivo de 12. Ahí no hay «de dónde bajo» que valga -- bajar no puede
 * arreglarlo -- y la app se limitaba a decir «tendrías que quitar o bajar Almendras», que ni
 * siquiera resolvía nada.
 *
 * Comprueba que ahora:
 *   1. pregunta QUÉ QUITAR, diciendo por qué (bajar ya no da más de sí),
 *   2. sigue preguntando vuelta tras vuelta en lugar de rendirse a la primera,
 *   3. y acaba con la comida CUADRADA.
 *
 * Trabaja en una fecha suelta de la cuenta de pruebas y la borra al terminar.
 *
 * Uso:  node _guia/_verificar_cuadra_hasta_cuadrar_3108.js
 */
const fs = require('fs');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';

const FECHA = '2026-12-21';
const CARPETA = '_guia/_cuadra_hasta_cuadrar';
if (!fs.existsSync(CARPETA)) fs.mkdirSync(CARPETA, { recursive: true });

// La comida tal y como la pegó Francisco.
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
    const ctx = await nav.newContext({ viewport: { width: 1400, height: 1200 }, deviceScaleFactor: 2 });
    const p = await ctx.newPage();
    const errores = [];
    p.on('console', (m) => { if (m.type() === 'error') errores.push(m.text().slice(0, 220)); });

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
    await p.waitForTimeout(1500);

    const objetivo = await p.locator('[data-testid="objetivo-C1"]').first().innerText().catch(() => '?');
    console.log('\nobjetivo de la comida:', objetivo.replace(/\s+/g, ' ').trim());

    await p.locator('[data-testid="cuadrar-C1"]').first().click();
    await p.waitForTimeout(3500);

    // Se contesta siempre la PRIMERA opción, que es la que más quita. Un cliente elegiría
    // otra cosa; lo que se prueba aquí es que la app sigue preguntando y acaba cuadrando.
    let vueltas = 0;
    while (vueltas < 20) {
        const dlg = p.locator('[data-testid="confirm-dialog"]').first();
        if (!(await dlg.count())) break;
        vueltas++;
        const titulo = (await dlg.locator('h2, [class*="DialogTitle"]').first().innerText()
            .catch(async () => (await dlg.innerText()).split('\n')[0])).replace(/\s+/g, ' ').trim();
        const primera = dlg.locator('[data-testid^="elegir-"]').first();
        const queElijo = (await primera.innerText().catch(() => '?')).replace(/\s+/g, ' ').trim();
        console.log(`\n  vuelta ${vueltas}: ${titulo}`);
        console.log(`     elijo -> ${queElijo}`);
        if (vueltas === 1) await dlg.screenshot({ path: `${CARPETA}/1_que_quito.png` }).catch(() => {});
        await primera.click();
        await p.waitForTimeout(3500);
    }
    console.log(`\n  (${vueltas} preguntas en total)`);

    await p.waitForTimeout(3000);
    const macros = await p.locator('[data-testid="meal-progress-C1"]').first().innerText().catch(() => '?');
    console.log('\ncomo queda la comida:');
    macros.split('\n').map(s => s.trim()).filter(Boolean).forEach(l => console.log('   ', l));
    await p.screenshot({ path: `${CARPETA}/2_como_queda.png`, fullPage: true });

    const avisos = await p.locator('[data-sonner-toast], [role="status"]').allInnerTexts().catch(() => []);
    avisos.map(t => t.replace(/\s+/g, ' ').trim()).filter(Boolean).forEach(t => console.log('   aviso:', t));

    await p.waitForTimeout(4000);
    const guardado = await pide(`/diets/${FECHA}`);
    const quedan = (guardado.comidas?.C1?.alimentos || []);
    console.log(`\n   quedan ${quedan.length} alimentos de los 14:`);
    quedan.forEach(a => console.log(`      ${a.nombre.split(' (')[0]} ${a.cantidad_g} g`));

    if (errores.length) console.log('\n   errores de consola:', errores.slice(0, 5));

    await pide(`/diets/${FECHA}`, { method: 'DELETE' });
    console.log(`\n(día de pruebas borrado: ${(await pide(`/diets/${FECHA}`)).exists ? 'NO' : 'sí'})`);
    console.log(`capturas en ${CARPETA}/`);
    await nav.close();
})();
