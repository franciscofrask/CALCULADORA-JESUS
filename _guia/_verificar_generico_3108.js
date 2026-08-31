/**
 * «SELECCIONO ALIMENTOS GENÉRICOS Y ME SALEN TAMBIÉN OTROS ALIMENTOS Y TODAS SUS MARCAS»
 * (un cliente, 31-08-2026).
 *
 * El chip «Genérico» ya filtraba bien por su cuenta -- `es_generico`, por la URL de la ficha --
 * pero la búsqueda POR TEXTO no mandaba los chips: en cuanto escribías, el filtro encendido
 * dejaba de existir. Esto comprueba las tres cosas en la app de verdad:
 *
 *   1. buscando «pechuga de pollo» sin filtro salen las marcas,
 *   2. con «Genérico» encendido desaparecen,
 *   3. y encender el chip CON el texto ya escrito también rehace la lista.
 *
 * Uso:  node _guia/_verificar_generico_3108.js
 */
const fs = require('fs');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const CARPETA = '_guia/_generico';
if (!fs.existsSync(CARPETA)) fs.mkdirSync(CARPETA, { recursive: true });

(async () => {
    const tok = (await (await fetch(`${API}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: CUENTA, password: CLAVE }),
    })).json()).access_token;
    if (!tok) { console.log('no he podido entrar'); return; }

    const nav = await chromium.launch();
    const p = await (await nav.newContext({ viewport: { width: 1400, height: 1100 }, deviceScaleFactor: 2 })).newPage();
    const errores = [];
    p.on('console', (m) => { if (m.type() === 'error') errores.push(m.text().slice(0, 200)); });
    // Lo que la pantalla le pide de verdad al servidor: aquí se ve si el chip viaja.
    const peticiones = [];
    p.on('request', (r) => {
        if (r.url().includes('/calculator/search')) peticiones.push(r.url().split('?')[1] || '');
    });

    // La ventana «Lo hago yo» solo tiene botón propio cuando la comida está vacía, así que
    // se trabaja en un día suelto sin nada montado.
    const FECHA = '2026-12-24';
    const api = (ruta, o = {}) => fetch(`${API}/api${ruta}`, { ...o,
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${tok}`, ...(o.headers || {}) } });
    await api(`/diets/${FECHA}`, { method: 'DELETE' }).catch(() => {});
    // Con el día ENTERO vacío la pantalla es otra (la del día vacío) y no hay tarjetas de
    // comida: se monta la C2 para que el día exista y la C1 siga vacía.
    await api('/diets', { method: 'POST', body: JSON.stringify({
        fecha: FECHA, tipo_dia: 'entrenamiento', num_comidas: 4,
        momento_entreno: 1, opcion_peri: 'intra_post',
        comidas: { C2: { alimentos: [{ id: 498, alimento_id: 498, nombre: 'Pechuga de pollo', cantidad_g: 150 }] } },
    }) });

    await p.goto(APP, { waitUntil: 'domcontentloaded' });
    await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);
    await p.goto(`${APP}/dashboard/nutrition?date=${FECHA}`, { waitUntil: 'networkidle' }).catch(() => {});
    await p.waitForTimeout(10000);
    for (let i = 0; i < 4; i++) {
        const s = p.locator('[data-testid="recorrido-saltar"]');
        if (!(await s.count())) break;
        await s.click({ force: true }).catch(() => {});
        await p.waitForTimeout(900);
    }
    await p.waitForTimeout(1500);

    // Abrir «Lo hago yo» de la Comida 1, que es donde está el buscador con sus chips.
    await p.locator('[data-testid="build-meal-C1"]').first().click().catch(() => {});
    await p.waitForTimeout(3000);

    const buscar = async (texto) => {
        const caja = p.locator('input[placeholder*="uscar"], input[type="text"]').first();
        await caja.fill('');
        await caja.type(texto, { delay: 40 });
        await p.waitForTimeout(3500);
    };
    const resultados = async () => {
        const filas = await p.locator('[data-testid^="fav-search-"], [data-testid^="food-"]').all();
        if (filas.length) return filas.length;
        return (await p.locator('button:has-text("Pechuga"), button:has-text("pechuga")').all()).length;
    };
    const nombres = async () => {
        const t = await p.locator('[role="dialog"]').first().innerText();
        return t.split('\n').map(s => s.trim())
            .filter(s => /pechuga de pollo/i.test(s)).slice(0, 12);
    };

    console.log('\n══ 1 · «pechuga de pollo» SIN filtro ══');
    await buscar('Pechuga de pollo');
    const sinFiltro = await nombres();
    sinFiltro.forEach(n => console.log('   ', n));
    console.log(`   (${sinFiltro.length} lineas con «pechuga de pollo»)`);
    await p.screenshot({ path: `${CARPETA}/1_sin_filtro.png`, fullPage: false });

    console.log('\n══ 2 · encender «Genérico» CON el texto ya escrito ══');
    // El rail de «Preparación» solo se pinta cuando hay una categoría elegida, que es como
    // lo tenía el cliente en su captura (Aves marcada y los chips de preparación debajo).
    await p.locator('button[aria-label="Aves"]').first().click().catch(() => {});
    await p.waitForTimeout(2500);
    const chip = p.locator('button[aria-label="Genérico"]').first();
    if (!(await chip.count())) {
        console.log('   no encuentro el chip Genérico ni con una categoría elegida');
    } else {
        peticiones.length = 0;
        await chip.click();
        await p.waitForTimeout(4000);
        console.log('   ¿se rehace la búsqueda?:', peticiones.length ? 'sí' : 'NO  <-- MAL');
        console.log('   lo que pide al servidor:', peticiones[peticiones.length - 1] || '(nada)');
        const conFiltro = await nombres();
        conFiltro.forEach(n => console.log('   ', n));
        console.log(`   (${conFiltro.length} lineas con «pechuga de pollo»)`);
        const marcas = conFiltro.filter(n => /\([A-ZÁÉÍÓÚ]/.test(n));
        console.log('   marcas que se cuelan:', marcas.length ? marcas.join(' | ') + '  <-- MAL' : 'ninguna  (bien)');
        await p.screenshot({ path: `${CARPETA}/2_con_generico.png`, fullPage: false });
    }

    if (errores.length) console.log('\n   errores de consola:', errores.slice(0, 4));
    await api(`/diets/${FECHA}`, { method: 'DELETE' }).catch(() => {});
    console.log(`\ncapturas en ${CARPETA}/`);
    await nav.close();
})();
