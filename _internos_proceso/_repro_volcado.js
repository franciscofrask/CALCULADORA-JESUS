/**
 * REPRO del caso "los objetivos por comida no suman el total del dia y no sale
 * el boton Volcar macros aqui" (captura de un usuario, dia 1-ago).
 *
 * Monta en dev un dia cuyos objetivos guardados (distribution_targets) NO cuadran
 * con los macros vigentes del cliente, que es lo que se ve en la captura:
 *   objetivos por comida 40/40/33.5/46.5 P = 160   vs   dia 130 P
 *
 * Uso:  node _internos_proceso/_repro_volcado.js
 * Hace falta el frontend en :3000 y el backend en :8000.
 */
const { chromium } = require('playwright');

const APP = 'http://localhost:3000';
const API = 'http://localhost:8000';
const CLIENTE = { email: 'clientedemo@test.com', password: 'demo123' };
// Modo de perientreno a probar: sin_peri (el del caso) | intra_post | solo_intra | solo_post
const PERI = process.argv[2] || 'sin_peri';
// El dia de la captura era el 1-ago, pero para la prueba vale cualquiera: se usa HOY
// porque es el que abre la pantalla por defecto (navegar de dia choca con el tour).
const hoy = new Date();
const FECHA = `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}-${String(hoy.getDate()).padStart(2, '0')}`;

// Los objetivos de la captura (suman 160P/86H/50G)
const TARGETS_VIEJOS = {
    C1: { P: 40, H: 29, G: 10 },
    C2: { P: 40, H: 29, G: 10 },
    C3: { P: 33.5, H: 14, G: 15 },
    C4: { P: 46.5, H: 14, G: 15 },
};

async function login() {
    const r = await fetch(`${API}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(CLIENTE),
    });
    const d = await r.json();
    return d.access_token;
}

async function api(token, path, opts = {}) {
    const r = await fetch(`${API}/api${path}`, {
        ...opts,
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...(opts.headers || {}) },
    });
    const txt = await r.text();
    try { return { status: r.status, data: JSON.parse(txt) }; } catch { return { status: r.status, data: txt }; }
}

(async () => {
    const token = await login();

    // 1. Que reparto le toca HOY a ese dia (lo que vera la cabecera)
    const dist = await api(token, '/calculator/distribute', {
        method: 'POST',
        body: JSON.stringify({ fecha: FECHA, tipo_dia: 'entrenamiento', num_comidas: 4,
                               momento_entreno: 1, opcion_peri: PERI }),
    });
    const D = dist.data;
    console.log('== reparto vigente para', FECHA, '==');
    for (const [k, v] of Object.entries(D.comidas)) console.log(`   ${k}: ${v.P}P ${v.H}H ${v.G}G`);
    console.log('   resumen del dia:', D.resumen.P_total, 'P', D.resumen.H_total, 'H', D.resumen.G_total, 'G');

    // 2. Guardar el dia con objetivos VIEJOS (los de la captura) y un alimento en C1
    const comidas = { C1: { alimentos: [] }, C2: { alimentos: [] }, C3: { alimentos: [] }, C4: { alimentos: [] } };
    const save = await api(token, '/diets', {
        method: 'POST',
        body: JSON.stringify({
            fecha: FECHA, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 1,
            opcion_peri: PERI, comidas,
            macros_snapshot: { P_total: 130, H_total: 70, G_total: 50 },
            distribution_targets: TARGETS_VIEJOS,
            is_cuadrado: false, comida_volcada: null,
        }),
    });
    console.log('\nguardado el dia con objetivos viejos ->', save.status);

    // 3. Abrir la pantalla y leer lo que pinta
    const browser = await chromium.launch();
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    const logs = [];
    page.on('console', m => logs.push(m.text()));

    await page.goto(`${APP}/login`);
    await page.fill('input[type="email"]', CLIENTE.email);
    await page.fill('input[type="password"]', CLIENTE.password);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard**', { timeout: 20000 });
    await page.goto(`${APP}/dashboard/nutrition`);
    await page.waitForTimeout(2500);

    // Saltar onboarding y tour si aparecen
    for (const t of ['Ver mi primera dieta', 'EMPEZAR', 'Empezar']) {
        const b = page.getByText(t, { exact: false });
        if (await b.count()) { await b.first().click({ force: true }).catch(() => {}); await page.waitForTimeout(1200); }
    }
    // La pagina restaura la ultima fecha vista desde localStorage al montar: fijarla y recargar
    await page.evaluate(f => localStorage.setItem('nutrition_last_date', f), FECHA);
    await page.reload();
    await page.waitForTimeout(7000);
    for (const t of ['Ver mi primera dieta', 'EMPEZAR', 'Empezar']) {
        const b = page.getByText(t, { exact: false });
        if (await b.count()) { await b.first().click({ force: true }).catch(() => {}); await page.waitForTimeout(1500); }
    }
    await page.waitForTimeout(2000);

    const texto = await page.locator('body').innerText();
    const desde = texto.indexOf('PLAN NUTRICIONAL');
    console.log('\n===== LO QUE SE VE EN PANTALLA =====');
    console.log((desde >= 0 ? texto.slice(desde) : texto).split('\n').filter(l => l.trim()).slice(0, 60).join('\n'));

    console.log('\n===== consola del navegador (overlay) =====');
    console.log(logs.filter(l => /distribution_targets|overlay/i.test(l)).join('\n') || '(sin rastro)');

    // ¿Cuadra la cabecera con la suma de los objetivos por comida?
    const cab = {
        P: (texto.match(/Proteína\s*\n\s*[\d.]+\s*\/\s*([\d.]+)/) || [])[1],
        H: (texto.match(/Hidratos\s*\n\s*[\d.]+\s*\/\s*([\d.]+)/) || [])[1],
        G: (texto.match(/Grasa\s*\n\s*[\d.]+\s*\/\s*([\d.]+)/) || [])[1],
    };
    const porComida = [...texto.matchAll(/([\d.]+)P·([\d.]+)H·([\d.]+)G/g)];
    const suma = porComida.reduce((a, m) => ({
        P: a.P + parseFloat(m[1]), H: a.H + parseFloat(m[2]), G: a.G + parseFloat(m[3]),
    }), { P: 0, H: 0, G: 0 });
    console.log('\n===== COMPROBACION =====');
    console.log(`objetivo de la cabecera:      P${cab.P} H${cab.H} G${cab.G}`);
    console.log(`suma de los objetivos:        P${suma.P.toFixed(1)} H${suma.H.toFixed(1)} G${suma.G.toFixed(1)} (${porComida.length} comidas)`);
    const cuadra = ['P', 'H', 'G'].every(m => Math.abs(parseFloat(cab[m] || 0) - suma[m]) < 1.5);
    console.log(cuadra ? '-> CUADRAN' : '-> *** NO CUADRAN: el dia pide menos de lo que suman sus comidas ***');

    const hayBoton = await page.getByText('Volcar macros aquí').count();
    console.log('\nbotones "Volcar macros aquí" visibles:', hayBoton);

    await page.screenshot({ path: '_internos_proceso/_repro_volcado.png', fullPage: true });
    console.log('captura -> _internos_proceso/_repro_volcado.png');
    await browser.close();
})();
