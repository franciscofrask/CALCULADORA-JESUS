/**
 * «ABRE EN LLEVAS, NO EN MACROS» («Todo lo validado antes del 1 de septiembre», 1.1).
 *
 * Comprueba los dos casos, porque el documento solo ilustra uno:
 *   1. Con comidas marcadas: entra y ve por donde va hoy.
 *   2. Sin nada marcado: la pestaña sigue siendo Llevas, pero no salen tres ceros pelados.
 *
 * Trabaja sobre el dia de HOY de la cuenta de pruebas, porque Inicio siempre enseña hoy.
 * Guarda lo que hubiera y lo repone al terminar.
 *
 * Uso:  node _guia/_verificar_inicio_llevas_0109.js
 */
const fs = require('fs');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const CARPETA = '_guia/_inicio_llevas';
if (!fs.existsSync(CARPETA)) fs.mkdirSync(CARPETA, { recursive: true });

// El dia que vive el cliente es el de su reloj, y el servidor cuenta en Madrid.
const HOY = new Date().toLocaleDateString('en-CA', { timeZone: 'Europe/Madrid' });

let TOKEN = '';
const api = async (ruta, o = {}) => {
    const r = await fetch(`${API}/api${ruta}`, { ...o,
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${TOKEN}`, ...(o.headers || {}) } });
    const t = await r.text();
    try { return JSON.parse(t); } catch { return { _texto: t }; }
};
const al = (id, n, g) => ({ id, alimento_id: id, nombre: n, cantidad_g: g });

(async () => {
    TOKEN = (await api('/auth/login', { method: 'POST',
        body: JSON.stringify({ email: CUENTA, password: CLAVE }) })).access_token;
    if (!TOKEN) { console.log('no he podido entrar'); return; }

    // ── Se guarda lo que hubiera hoy, para reponerlo ─────────────────────────
    const antes = await api(`/diets/${HOY}`);
    const habia = Boolean(antes?.exists);
    if (habia) fs.writeFileSync(`${CARPETA}/_dia_original.json`, JSON.stringify(antes, null, 1));
    console.log(`el dia ${HOY} de la cuenta de pruebas: ${habia ? 'tenia dieta (guardada para reponerla)' : 'estaba vacio'}`);

    const nav = await chromium.launch();
    const p = await (await nav.newContext({ viewport: { width: 390, height: 1400 }, deviceScaleFactor: 2 })).newPage();
    const errores = [];
    p.on('console', (m) => { if (m.type() === 'error') errores.push(m.text().slice(0, 160)); });

    const entrar = async () => {
        await p.goto(APP, { waitUntil: 'domcontentloaded' });
        await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, TOKEN);
        await p.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
        await p.waitForTimeout(12000);
        for (let i = 0; i < 4; i++) {
            const s = p.locator('[data-testid="recorrido-saltar"]');
            if (!(await s.count())) break;
            await s.click({ force: true }).catch(() => {});
            await p.waitForTimeout(1000);
        }
        await p.waitForTimeout(1800);
    };

    /** Cuál de las cuatro pestañas está encendida, leído del propio botón. */
    const pestanaActiva = async () => {
        for (const nombre of ['Macros', 'Dieta', 'Llevas', 'Falta']) {
            const b = p.locator(`button:text-is("${nombre}")`).first();
            if (!(await b.count())) continue;
            const cls = (await b.getAttribute('class')) || '';
            if (/bg-brand|text-white|bg-card|aria-selected/.test(cls)) return nombre;
            if ((await b.getAttribute('aria-selected')) === 'true') return nombre;
        }
        return '(no lo sé)';
    };

    const loQueDice = async () => {
        const c = p.locator('[data-testid="tu-dieta-hoy"], section').filter({ hasText: 'TU DIETA HOY' }).first();
        if (!(await c.count())) return '(no encuentro el bloque)';
        return (await c.innerText()).split('\n').map(s => s.trim()).filter(Boolean).slice(0, 14).join(' · ');
    };

    // ── Caso 1 · con comidas marcadas ────────────────────────────────────────
    await api(`/diets/${HOY}`, { method: 'DELETE' }).catch(() => {});
    // Los macros de cada alimento los calcula el servidor, igual que cuando el cliente monta
    // la comida. Poniendolos a mano salian a cero y «Llevas» decia «0 de 235», que es un
    // fallo del guion y no de la pantalla.
    const dia = { fecha: HOY, tipo_dia: 'entrenamiento', num_comidas: 4,
                  momento_entreno: 1, opcion_peri: 'intra_post' };
    const cuadrado = await api('/calculator/refit-diet', { method: 'POST', body: JSON.stringify({
        ...dia,
        comidas: {
            C1: { alimentos: [al(498, 'Pollo', 200), al(1657, 'Arroz', 80)] },
            C2: { alimentos: [al(498, 'Pollo', 150), al(1657, 'Arroz', 60)] },
            C3: { alimentos: [al(498, 'Pollo', 150)] },
        },
    }) });
    await api('/diets', { method: 'POST', body: JSON.stringify({
        ...dia, comidas: cuadrado.comidas || {}, comidas_completas: true,
    }) });
    for (const k of ['C1', 'C2']) {
        await api(`/diets/${HOY}/comida-marcada`, { method: 'PATCH',
            body: JSON.stringify({ comida: k, marcada: true }) });
    }
    await entrar();
    console.log('\n══ 1 · con dos comidas marcadas ══');
    console.log('   pestaña encendida:', await pestanaActiva());
    console.log('   dice:', await loQueDice());
    await p.screenshot({ path: `${CARPETA}/1_con_marcadas.png`, fullPage: false });

    // ── Caso 2 · con el día montado pero sin marcar nada ─────────────────────
    for (const k of ['C1', 'C2']) {
        await api(`/diets/${HOY}/comida-marcada`, { method: 'PATCH',
            body: JSON.stringify({ comida: k, marcada: false }) });
    }
    await entrar();
    console.log('\n══ 2 · sin nada marcado ══');
    console.log('   pestaña encendida:', await pestanaActiva());
    console.log('   dice:', await loQueDice());
    await p.screenshot({ path: `${CARPETA}/2_sin_marcar.png`, fullPage: false });

    if (errores.length) console.log('\n   errores de consola:', errores.slice(0, 4));

    // ── Se repone ────────────────────────────────────────────────────────────
    await api(`/diets/${HOY}`, { method: 'DELETE' }).catch(() => {});
    if (habia) {
        await api('/diets', { method: 'POST', body: JSON.stringify({
            fecha: HOY, tipo_dia: antes.tipo_dia, num_comidas: antes.num_comidas,
            momento_entreno: antes.momento_entreno, opcion_peri: antes.opcion_peri,
            comidas: antes.comidas, comidas_completas: true,
            macros_snapshot: antes.macros_snapshot,
            distribution_targets: antes.distribution_targets,
        }) });
    }
    const final = await api(`/diets/${HOY}`);
    console.log(`\n(el día de la cuenta de pruebas, repuesto: ${Boolean(final?.exists) === habia ? 'sí' : 'REVÍSALO'})`);
    console.log(`capturas en ${CARPETA}/`);
    await nav.close();
})();
