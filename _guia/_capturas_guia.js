/**
 * Capturas de todas las pantallas de la app, para la guia de uso.
 *
 * Recorre el circuito del cliente y el del admin, en escritorio y en movil, y deja un
 * PNG por pantalla en _guia/capturas/.
 *
 * Uso:  node _capturas_guia.js
 * Hace falta el frontend en :3000 y el backend en :8000.
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const APP = 'http://localhost:3000';
const API = 'http://localhost:8000';
const SALIDA = path.join(__dirname, '_guia', 'capturas');

const CLIENTE = { email: 'clientedemo@test.com', password: 'demo123' };
const ADMIN = { email: 'francisco@test.com', password: 'demo123' };

// Pantallas del cliente, en el orden en que las recorre de verdad.
const PANTALLAS_CLIENTE = [
    ['01-panel', '/dashboard'],
    ['02-nutricion', '/dashboard/nutrition'],
    ['03-asistente-ia', '/dashboard/chatbot'],
    ['04-rutina', '/dashboard/routine'],
    ['05-reportes', '/dashboard/reports'],
    ['06-check-ins', '/dashboard/checkins'],
    ['07-suplementos', '/dashboard/supplements'],
    ['08-ajustar-macros', '/dashboard/macro-calculator'],
    ['09-alimentos', '/dashboard/foods'],
    ['10-mensajes', '/dashboard/messages'],
    ['11-mi-perfil', '/dashboard/profile'],
    ['12-planes', '/planes'],
    ['13-renovacion', '/renovacion'],
];

const PANTALLAS_ADMIN = [
    ['20-admin-panel', '/admin'],
    ['21-admin-clientes', '/admin/clients'],
    ['22-admin-leads', '/admin/leads'],
    ['23-admin-mensajes', '/admin/messages'],
    ['24-admin-rutinas', '/admin/routines'],
    ['25-admin-suplementos', '/admin/supplements-catalog'],
    ['26-admin-menus', '/admin/menus'],
    ['27-admin-alimentos', '/admin/alimentos'],
    ['28-admin-usuarios', '/admin/usuarios'],
    ['29-admin-planes', '/admin/planes'],
];

// Pantallas publicas: sin sesion, tal como las ve alguien de fuera.
const PANTALLAS_PUBLICAS = [
    ['00-entrar', '/auth'],
    ['00-test-de-nivel', '/test'],
];

async function entrar(page, credenciales) {
    const r = await page.request.post(`${API}/api/auth/login`, { data: credenciales });
    if (!r.ok()) throw new Error(`No se pudo entrar como ${credenciales.email}: ${r.status()}`);
    const { access_token, token } = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => localStorage.setItem('token', t), access_token || token);
}

async function salir(page) {
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate(() => localStorage.clear());
}

async function capturar(page, nombre, ruta, sufijo = '') {
    const destino = path.join(SALIDA, `${nombre}${sufijo}.png`);
    try {
        await page.goto(`${APP}${ruta}`, { waitUntil: 'networkidle', timeout: 45000 });
    } catch {
        // networkidle no siempre llega (sondeos, websockets): con el DOM basta.
        await page.waitForTimeout(2500);
    }
    await page.waitForTimeout(2200);   // que terminen las animaciones y los datos
    await page.screenshot({ path: destino, fullPage: true });
    const texto = await page.evaluate(() => (document.querySelector('#root')?.innerText || '').slice(0, 160).replace(/\s+/g, ' '));
    console.log(`  ${nombre}${sufijo}  ->  ${texto.slice(0, 110)}`);
    return destino;
}

(async () => {
    fs.mkdirSync(SALIDA, { recursive: true });
    const navegador = await chromium.launch();

    // ── ESCRITORIO ────────────────────────────────────────────────────────────
    const escritorio = await navegador.newContext({ viewport: { width: 1440, height: 900 } });
    const page = await escritorio.newPage();

    console.log('\n== PUBLICAS (sin sesion) ==');
    await salir(page);
    for (const [n, r] of PANTALLAS_PUBLICAS) await capturar(page, n, r);

    console.log('\n== CLIENTE ==');
    await entrar(page, CLIENTE);
    for (const [n, r] of PANTALLAS_CLIENTE) await capturar(page, n, r);

    console.log('\n== ADMIN ==');
    await salir(page);
    await entrar(page, ADMIN);
    for (const [n, r] of PANTALLAS_ADMIN) await capturar(page, n, r);

    // La ficha de un cliente concreto: se busca su id, no se clava a mano.
    try {
        const t = await page.evaluate(() => localStorage.getItem('token'));
        const lista = await page.request.get(`${API}/api/admin/clients`, {
            headers: { Authorization: `Bearer ${t}` },
        });
        const clientes = await lista.json();
        const demo = clientes.find(c => (c.email || '').toLowerCase() === CLIENTE.email) || clientes[0];
        if (demo?.id) await capturar(page, '30-admin-ficha-cliente', `/admin/clients/${demo.id}`);
    } catch (e) {
        console.log('  (no se pudo capturar la ficha de cliente:', e.message, ')');
    }
    await escritorio.close();

    // ── MOVIL ─────────────────────────────────────────────────────────────────
    // Un movil de verdad (viewport estrecho), que es lo unico que activa los
    // breakpoints. Encoger un div NO vale: window.innerWidth no cambia.
    console.log('\n== MOVIL (390x844) ==');
    const movil = await navegador.newContext({
        viewport: { width: 390, height: 844 },
        deviceScaleFactor: 2,
        isMobile: true,
        hasTouch: true,
    });
    const pm = await movil.newPage();
    await entrar(pm, CLIENTE);
    for (const [n, r] of [
        ['40-movil-panel', '/dashboard'],
        ['41-movil-nutricion', '/dashboard/nutrition'],
        ['42-movil-asistente', '/dashboard/chatbot'],
        ['43-movil-reportes', '/dashboard/reports'],
        ['44-movil-planes', '/planes'],
    ]) await capturar(pm, n, r);
    await salir(pm);
    await capturar(pm, '45-movil-test-de-nivel', '/test');
    await movil.close();

    await navegador.close();
    const total = fs.readdirSync(SALIDA).filter(f => f.endsWith('.png')).length;
    console.log(`\nLISTO: ${total} capturas en ${SALIDA}`);
})();
