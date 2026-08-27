/**
 * EL NOMBRE DEL SUPLEMENTO QUE VE EL CLIENTE (vídeo de Jesús del 27-08).
 *
 * «Él solamente ve Aceite de krill. No tiene que ver Aceite de krill, tres perlas.»
 * «Ve el nombre del suplemento, pero no ve lo de hombre o lo de mujer.»
 *
 * Son dos vistas del mismo dato, como en Calma: el cliente ve el nombre limpio y EL PANEL
 * SIGUE VIENDO SU CHULETA, que es lo que le dice qué versión le puso a quién. Aquí se
 * comprueban las dos, porque arreglar una rompiendo la otra no arregla nada.
 *
 * Deja la cuenta como estaba.
 *
 * Uso:  node _guia/_nombres_suplementos_2708.js
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || process.env.DESTINO || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const ADMIN = process.env.ADMIN || 'francisco@test.com';
const ADMIN_CLAVE = process.env.ADMIN_CLAVE || 'demo123';

const ok = (b) => (b ? 'BIEN' : 'MAL ');

// Los de verdad, tal y como están guardados hoy en producción.
const PRUEBA = [
    { titulo: 'Creatina hombre', cuando: 'Todos los días, con el desayuno (entrenes o no)', cuanto: '10 g' },
    { titulo: 'Omega 3 hombre', cuando: 'Todos los días, en dos tomas (desayuno y cena)', cuanto: '3 perlas por toma' },
    { titulo: 'Aceite de krill 3 perlas', cuando: 'Todos los días, en dos tomas (desayuno y cena)', cuanto: '3 perlas por toma' },
    { titulo: 'Fat burner hardcore mes 3', cuando: 'Todos los días, en dos tomas', cuanto: '1 cápsula' },
    { titulo: 'Cafeína anhidra 200 mg suelta', cuando: 'Antes de entrenar', cuanto: '1 cápsula' },
    { titulo: 'Whey Isolate + crema de arroz (post-entreno)', cuando: 'Justo después de entrenar', cuanto: 'Lo que cuadre' },
];
// Lo que tiene que ver el cliente de cada uno.
const LIMPIO = {
    'Creatina hombre': 'Creatina',
    'Omega 3 hombre': 'Omega 3',
    'Aceite de krill 3 perlas': 'Aceite de krill',
    'Fat burner hardcore mes 3': 'Fat burner hardcore',
    'Cafeína anhidra 200 mg suelta': 'Cafeína anhidra 200 mg',
    'Whey Isolate + crema de arroz (post-entreno)': 'Whey Isolate + crema de arroz (post-entreno)',
};

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
    const ctx = await nav.newContext({ viewport: { width: 390, height: 900 } });
    const page = await ctx.newPage();

    const rc = await page.request.post(`${API}/api/auth/login`, { data: { email: CUENTA, password: CLAVE } });
    const tok = (await rc.json()).access_token;
    const cab = { Authorization: `Bearer ${tok}` };
    const ra = await page.request.post(`${API}/api/auth/login`, { data: { email: ADMIN, password: ADMIN_CLAVE } });
    const cabAdmin = { Authorization: `Bearer ${(await ra.json()).access_token}` };
    const yo = await (await page.request.get(`${API}/api/auth/me`, { headers: cab })).json();
    const lista = await (await page.request.get(`${API}/api/admin/clients?include_incomplete=true`, { headers: cabAdmin, timeout: 90000 })).json();
    const cli = (Array.isArray(lista) ? lista : []).find(c => ((c.user || {}).email || '').toLowerCase() === yo.email.toLowerCase());
    if (!cli) { console.log('no encuentro al cliente'); await nav.close(); return; }

    const d = new Date();
    const FECHA = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    console.log('\n=== EL NOMBRE QUE VE EL CLIENTE ===\n');

    const antes = await (await page.request.get(`${API}/api/supplements/current`, { headers: cab })).json();
    const habia = !!(antes && (antes.versiones || []).length);
    await page.request.post(`${API}/api/admin/supplements/save?client_id=${cli.id}`, {
        headers: cabAdmin, data: { actual: PRUEBA, actual_fecha: FECHA, siguiente: [] },
    });

    // 1 · Lo que le llega al cliente.
    const prot = await (await page.request.get(`${API}/api/supplements/current`, { headers: cab })).json();
    console.log('lo que le llega al CLIENTE:');
    const guardados = PRUEBA.map(p => p.titulo);
    for (let i = 0; i < guardados.length; i++) {
        const ve = (prot.actual[i] || {}).titulo;
        console.log(`   ${ok(ve === LIMPIO[guardados[i]])} «${guardados[i]}»\n        -> «${ve}»`);
    }

    // 2 · Y que el PANEL siga viendo la chuleta.
    const ficha = await (await page.request.get(`${API}/api/admin/clients/${cli.id}`, { headers: cabAdmin })).json();
    const enPanel = ((ficha.supplement_protocol || {}).actual || []).map(x => x.titulo);
    const intacto = guardados.every(g => enPanel.includes(g));
    console.log(`\nel PANEL sigue viendo su chuleta   ${ok(intacto)}`);
    console.log('   ' + enPanel.join(' · '));

    // 3 · Y en la pantalla del cliente, que es lo que importa.
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);
    await page.goto(`${APP}/dashboard/supplements`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(8000);
    await quitarRecorrido(page);
    const enPantalla = await page.locator('body').innerText();
    console.log('\nen la pantalla de Suplementos del cliente:');
    for (const g of guardados) {
        const limpio = LIMPIO[g];
        const saleSucio = g !== limpio && enPantalla.includes(g);
        const saleLimpio = enPantalla.includes(limpio);
        console.log(`   ${ok(saleLimpio && !saleSucio)} «${limpio}»${saleSucio ? '   <-- SIGUE SALIENDO «' + g + '»' : ''}`);
    }
    await page.screenshot({ path: '_guia/_nombres_suplementos.png', fullPage: true });

    // Se repone.
    if (habia) {
        await page.request.post(`${API}/api/admin/supplements/save?client_id=${cli.id}`, {
            headers: cabAdmin, data: { actual: antes.actual || [], actual_fecha: antes.actual_fecha || FECHA, siguiente: antes.siguiente || [] } });
        console.log('\nprotocolo repuesto');
    } else {
        const b = await page.request.delete(`${API}/api/admin/supplements/version/${FECHA}?client_id=${cli.id}`, { headers: cabAdmin });
        console.log('\nprotocolo de prueba borrado ->', b.status());
    }
    console.log('captura -> _guia/_nombres_suplementos.png');
    await nav.close();
})();
