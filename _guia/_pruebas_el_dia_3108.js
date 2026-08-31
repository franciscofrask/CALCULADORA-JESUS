/**
 * LAS PRUEBAS DE «EL DÍA», UNA POR PUNTO.
 *
 * Saca una captura de la app REAL por cada punto del documento, recortada a lo que hay que
 * mirar. De aquí sale el Word (`_guia/_word_el_dia_3108.py`), que pone al lado lo que pedía
 * el documento y lo que hace hoy el sistema.
 *
 * Lo que no se puede fotografiar tal cual -- las horas -- se fotografía forzando la respuesta
 * del servidor, que es lo mismo que ve el navegador a esa hora: la REGLA la prueban los 30
 * casos de `backend/tests/test_ventana_del_dia_3108.py`, y aquí se prueba que la pantalla la
 * pinta.
 *
 * Deja la cuenta como estaba: las preferencias se guardan al empezar y se reponen al salir.
 *
 * Uso:  node _guia/_pruebas_el_dia_3108.js
 */
const fs = require('fs');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || process.env.DESTINO || 'http://127.0.0.1:8000';
const CLIENTE = process.env.CUENTA || 'clientedemo@test.com';
const ADMIN = process.env.ADMIN || 'francisco@test.com';
const CLAVE = process.env.CLAVE || 'demo123';

const CARPETA = '_guia/_pruebas_el_dia';
if (!fs.existsSync(CARPETA)) fs.mkdirSync(CARPETA, { recursive: true });

const hoy = new Date().toLocaleDateString('en-CA');
const ayer = new Date(Date.now() - 86400000).toLocaleDateString('en-CA');

const quitarRecorrido = async (page) => {
    for (let i = 0; i < 4; i++) {
        const s = page.locator('[data-testid="recorrido-saltar"]');
        if (!(await s.count())) break;
        await s.click({ force: true }).catch(() => {});
        await page.waitForTimeout(1200);
    }
    await page.waitForTimeout(1000);
};

/** Recorta a un elemento, con un poco de aire alrededor para que se lea en contexto. */
const foto = async (page, nombre, selector, aire = 14) => {
    const destino = `${CARPETA}/${nombre}.png`;
    if (!selector) {
        await page.screenshot({ path: destino, fullPage: true });
    } else {
        const el = page.locator(selector).first();
        if (!(await el.count())) { console.log(`   [${nombre}] no encuentro ${selector}`); return null; }
        await el.scrollIntoViewIfNeeded().catch(() => {});
        await page.waitForTimeout(350);
        const b = await el.boundingBox();
        if (!b) { console.log(`   [${nombre}] sin caja`); return null; }
        const v = page.viewportSize();
        await page.screenshot({ path: destino, clip: {
            x: Math.max(0, b.x - aire), y: Math.max(0, b.y - aire),
            width: Math.min(v.width - Math.max(0, b.x - aire), b.width + aire * 2),
            height: Math.min(v.height - Math.max(0, b.y - aire), b.height + aire * 2),
        } });
    }
    console.log(`   ✓ ${nombre}.png`);
    return destino;
};

(async () => {
    const nav = await chromium.launch();
    const movil = await nav.newContext({ viewport: { width: 390, height: 1800 }, deviceScaleFactor: 2 });
    const escritorio = await nav.newContext({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2 });
    const p = await movil.newPage();
    const pa = await escritorio.newPage();

    const entrar = async (email) => (await (await p.request.post(`${API}/api/auth/login`,
        { data: { email, password: CLAVE } })).json()).access_token;
    const tokC = await entrar(CLIENTE);
    const tokA = await entrar(ADMIN);
    const cabC = { Authorization: `Bearer ${tokC}`, 'Content-Type': 'application/json' };

    const prefsAntes = await (await p.request.get(`${API}/api/notifications/preferencias`, { headers: cabC })).json();

    const irCliente = async (ruta) => {
        await p.goto(APP, { waitUntil: 'domcontentloaded' });
        await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tokC);
        await p.goto(`${APP}${ruta}`, { waitUntil: 'networkidle' }).catch(() => {});
        await p.waitForTimeout(11000);
        await quitarRecorrido(p);
    };

    console.log('\n=== BLOQUE A · la pantalla del cierre ===');
    await irCliente('/dashboard/checkins');
    // Si el cierre de hoy ya está hecho, la pantalla enseña el «Anotado. Mañana seguimos» y
    // las preguntas no se pintan. Se reabre con su propio botón (el de reabrir del 23-08),
    // que es exactamente lo que haría el cliente para corregirlo.
    const editar = p.locator('text=Editar lo de hoy');
    if (await editar.count()) {
        console.log('   (el cierre de hoy ya estaba hecho: se reabre con «Editar lo de hoy»)');
        await editar.first().click();
        await p.waitForTimeout(2500);
    }
    await foto(p, 'A0_pantalla_entera', null);
    await foto(p, 'A5_el_dia_todo_bien', '[data-testid="cierre-dieta-aviso"]');
    await foto(p, 'A1_primera_pregunta', '[data-testid="cierre-entreno"]');
    await foto(p, 'A2_suplementacion', '[data-testid="cierre-suplementos"]');
    await foto(p, 'A3_extras', '[data-testid="cierre-extras"]');
    await foto(p, 'A4_pie', '[data-testid="cierre-que-falta"]');
    // A6: se contesta una y se ve que NO se pliega ni se enciende otra.
    await p.locator('[data-testid="cierre-cardio-op-no"]').click().catch(() => {});
    await p.waitForTimeout(1200);
    await foto(p, 'A6_contestada_sigue_abierta', '[data-testid="cierre-cardio"]');

    console.log('\n=== BLOQUES B y C · la fila del Inicio ===');
    const ESTADOS = [
        ['B1_desde_su_hora', { abierto: hoy, es_de_ayer: false, hecho: false, dias_sin_cerrar: 0, quiere_cierre: true,
            linea: { titulo: '¿Cómo fuiste hoy?', detalle: 'Para rellenar al final del día' } }],
        ['B2_dos_dias', { abierto: hoy, es_de_ayer: false, hecho: false, dias_sin_cerrar: 2, quiere_cierre: true,
            linea: { titulo: '¿Cómo fuiste hoy?', detalle: 'Llevas 2 días seguidos sin cerrar, no lo dejes hoy también' } }],
        ['B3_cuatro_dias', { abierto: hoy, es_de_ayer: false, hecho: false, dias_sin_cerrar: 4, quiere_cierre: true,
            linea: { titulo: 'Llevas 4 días sin cerrar', detalle: 'Retómalo hoy mismo: es de donde salen tus ajustes' } }],
        ['B4_una_semana', { abierto: hoy, es_de_ayer: false, hecho: false, dias_sin_cerrar: 9, quiere_cierre: true,
            linea: { titulo: 'Llevas una semana sin cerrar el día', detalle: 'Dejo de recordártelo. Si te está costando, dímelo y lo vemos' } }],
        ['C2_la_manana_siguiente', { abierto: ayer, es_de_ayer: true, hecho: false, dias_sin_cerrar: 1, quiere_cierre: true,
            linea: { titulo: 'Ayer no cerraste el día', detalle: 'Puedes hacerlo hasta las 3 de la tarde' } }],
    ];
    for (const [nombre, respuesta] of ESTADOS) {
        await p.route('**/api/checkins/estado**', (r) =>
            r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(respuesta) }));
        await irCliente('/dashboard');
        await foto(p, nombre, '[data-testid="pendiente-cierre"], [data-testid="linea-cierre"]')
            || await foto(p, nombre, 'text=' + respuesta.linea.titulo, 20);
        await p.unroute('**/api/checkins/estado**');
    }
    // C1/C3: la franja muerta, con el servidor de verdad diciendo que no hay día abierto.
    const real = await (await p.request.get(`${API}/api/checkins/estado?fecha=${hoy}`, { headers: cabC })).json();
    await irCliente('/dashboard');
    await foto(p, 'C3_sin_dia_abierto', null);
    fs.writeFileSync(`${CARPETA}/_estado_real.json`, JSON.stringify(real, null, 1));

    // C2b · la pantalla del cierre abierta en el día de AYER
    await irCliente(`/dashboard/checkins?fecha=${ayer}`);
    await foto(p, 'C2b_cierre_de_ayer', '[data-testid="routine-page"], h1, header', 20);
    await foto(p, 'C2b_cierre_de_ayer_entero', null);

    console.log('\n=== BLOQUE D · los avisos ===');
    await irCliente('/dashboard/profile');
    // La tarjeta ENTERA: desde su título hasta el último interruptor. Se mide por los dos
    // extremos porque la tarjeta en sí no tiene un testid propio.
    {
        const arriba = p.locator('text=AVISOS Y RECORDATORIOS').first();
        const abajo = p.locator('[data-testid="aviso-por-correo"]').first();
        await arriba.scrollIntoViewIfNeeded().catch(() => {});
        await p.waitForTimeout(400);
        const a = await arriba.boundingBox();
        const b = await abajo.boundingBox();
        if (a && b) {
            await p.screenshot({ path: `${CARPETA}/D1_tarjeta.png`, clip: {
                x: 8, y: Math.max(0, a.y - 22),
                width: 374, height: Math.min(1780, b.y + b.height + 56 - a.y) } });
            console.log('   ✓ D1_tarjeta.png');
        } else {
            console.log('   [D1_tarjeta] no encuentro los dos extremos');
        }
    }
    await foto(p, 'D2_selector_de_hora', '[data-testid="aviso-hora-cierre"]', 90);
    // D4 · el diálogo de apagar
    await p.locator('[data-testid="aviso-cierre-dia"]').click();
    await p.waitForTimeout(1500);
    await foto(p, 'D4_dialogo_al_apagar', '[role="alertdialog"], [role="dialog"]', 8)
        || await foto(p, 'D4_dialogo_al_apagar', null);
    await p.locator('button:has-text("Dejarlo como está")').click().catch(() => {});
    await p.waitForTimeout(1200);

    console.log('\n=== BLOQUE E · el panel ===');
    const irPanel = async (ruta) => {
        await pa.goto(APP, { waitUntil: 'domcontentloaded' });
        await pa.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tokA);
        await pa.goto(`${APP}${ruta}`, { waitUntil: 'networkidle' }).catch(() => {});
        await pa.waitForTimeout(14000);
    };
    await irPanel('/admin/clients');
    await foto(pa, 'E1_columna_sin_cerrar', 'table', 6);
    // Con el cierre apagado, para ver «apagado» y «Avisos apagados»
    const perfil = await (await p.request.get(`${API}/api/clients/profile`, { headers: cabC })).json();
    await p.request.put(`${API}/api/notifications/preferencias`,
        { headers: cabC, data: { cierre_dia: false, avisos_en_la_app: false } });
    await irPanel('/admin/clients');
    await foto(pa, 'E2_apagado_en_la_tabla', `[data-testid="sin-cerrar-${perfil.id}"]`, 120);

    // Se repone
    await p.request.put(`${API}/api/notifications/preferencias`, { headers: cabC, data: prefsAntes });
    const fin = await (await p.request.get(`${API}/api/notifications/preferencias`, { headers: cabC })).json();
    console.log('\npreferencias repuestas:', JSON.stringify(fin) === JSON.stringify(prefsAntes) ? 'BIEN' : 'MAL');

    console.log(`\ncapturas en ${CARPETA}/`);
    await nav.close();
})();
