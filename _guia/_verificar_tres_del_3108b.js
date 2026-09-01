/**
 * LAS TRES DE LA CAPTURA DEL 31-08 POR LA NOCHE (Francisco).
 *
 *   1. El aviso de «Comida cuadrada» ya no arrastra la coletilla del redondeo.
 *   2. El estado de una comida nunca dice «faltan» a secas: dice de qué.
 *   3. La pantalla de Alimentos, en el telefono, trae de 40 en 40 y no de 20 en 20.
 *
 * Uso:  node _guia/_verificar_tres_del_3108b.js
 */
const fs = require('fs');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const FECHA = '2026-12-27';
const CARPETA = '_guia/_tres_del_3108b';
if (!fs.existsSync(CARPETA)) fs.mkdirSync(CARPETA, { recursive: true });

let TOKEN = '';
const api = async (ruta, o = {}) => {
    const r = await fetch(`${API}/api${ruta}`, { ...o,
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${TOKEN}`, ...(o.headers || {}) } });
    const t = await r.text();
    try { return JSON.parse(t); } catch { return { t }; }
};
const al = (id, n, g) => ({ id, alimento_id: id, nombre: n, cantidad_g: g });

(async () => {
    TOKEN = (await api('/auth/login', { method: 'POST',
        body: JSON.stringify({ email: CUENTA, password: CLAVE }) })).access_token;
    if (!TOKEN) { console.log('no he podido entrar'); return; }

    await api(`/diets/${FECHA}`, { method: 'DELETE' }).catch(() => {});
    await api('/diets', { method: 'POST', body: JSON.stringify({
        fecha: FECHA, tipo_dia: 'entrenamiento', num_comidas: 4,
        momento_entreno: 1, opcion_peri: 'intra_post',
        comidas: {
            C1: { alimentos: [al(498, 'Pollo', 250), al(1657, 'Arroz', 100)] },
            C3: { alimentos: [al(498, 'Pollo', 120), al(1657, 'Arroz', 60)] },
        },
    }) });

    const nav = await chromium.launch();
    const p = await (await nav.newContext({ viewport: { width: 390, height: 1500 }, deviceScaleFactor: 2 })).newPage();
    const errores = [];
    p.on('console', (m) => { if (m.type() === 'error') errores.push(m.text().slice(0, 200)); });

    const entrar = async (ruta) => {
        await p.goto(APP, { waitUntil: 'domcontentloaded' });
        await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, TOKEN);
        await p.goto(`${APP}${ruta}`, { waitUntil: 'networkidle' }).catch(() => {});
        await p.waitForTimeout(11000);
        for (let i = 0; i < 4; i++) {
            const s = p.locator('[data-testid="recorrido-saltar"]');
            if (!(await s.count())) break;
            await s.click({ force: true }).catch(() => {});
            await p.waitForTimeout(900);
        }
        await p.waitForTimeout(1500);
    };

    await entrar(`/dashboard/nutrition?date=${FECHA}`);

    console.log('\n══ 2 · el estado de cada comida ══');
    for (const k of ['C1', 'C2', 'C3', 'C4', 'Intra', 'Post']) {
        const e = p.locator(`[data-testid="estado-comida-${k}"]`).first();
        const txt = (await e.count()) ? (await e.innerText()).replace(/\s+/g, ' ').trim() : '(abierta)';
        const pelado = /^(faltan|sobran)$/.test(txt);
        console.log(`   ${k.padEnd(6)} ${txt}${pelado ? '   <-- MAL, no dice de que' : ''}`);
    }
    await p.screenshot({ path: `${CARPETA}/1_estados.png`, fullPage: true });

    console.log('\n══ 1 · el aviso al cuadrar ══');
    await p.locator('[data-testid="cuadrar-C1"]').first().click().catch(() => {});
    await p.waitForTimeout(4000);
    const avisos = (await p.locator('[data-sonner-toast], [role="status"]').allInnerTexts().catch(() => []))
        .map(t => t.replace(/\s+/g, ' ').trim()).filter(Boolean);
    avisos.forEach(t => console.log('   ', t));
    const coletilla = avisos.some(t => t.includes('redondeadas para pesarlas'));
    console.log('   ¿queda la coletilla del redondeo?:', coletilla ? 'SI  <-- MAL' : 'no  (bien)');
    await p.screenshot({ path: `${CARPETA}/2_aviso.png`, fullPage: false });

    console.log('\n══ 3 · Alimentos en el telefono, de cuantos en cuantos ══');
    await entrar('/dashboard/foods');
    const boton = p.locator('[data-testid="ver-mas-alimentos"]').first();
    if (!(await boton.count())) {
        console.log('   no encuentro el boton de ver mas');
    } else {
        console.log('   el boton dice:', (await boton.innerText()).replace(/\s+/g, ' ').trim());
        const antes = await p.locator('[data-testid="alimento"]').count();
        await boton.click();
        await p.waitForTimeout(1800);
        const despues = await p.locator('[data-testid="alimento"]').count();
        console.log(`   alimentos a la vista: ${antes} -> ${despues}  (trae ${despues - antes})`);
    }
    await p.screenshot({ path: `${CARPETA}/3_alimentos.png`, fullPage: false });

    if (errores.length) console.log('\n   errores de consola:', errores.slice(0, 4));
    await api(`/diets/${FECHA}`, { method: 'DELETE' });
    console.log(`\ncapturas en ${CARPETA}/`);
    await nav.close();
})();
