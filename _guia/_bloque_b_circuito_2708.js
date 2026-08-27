/**
 * BLOQUE B, el circuito entero: el cliente pide una LATA desde la pantalla y el equipo la ve
 * en su panel con los datos nuevos (`es_conserva`, el peso escurrido y «no tiene web»).
 *
 * Se borra al terminar, para no gastarle el cupo semanal a la cuenta de pruebas ni dejar
 * basura en la bandeja del panel.
 *
 * Uso:  node _guia/_bloque_b_circuito_2708.js
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || process.env.DESTINO || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const ADMIN = process.env.ADMIN || 'francisco@test.com';
const ADMIN_CLAVE = process.env.ADMIN_CLAVE || 'demo123';

const ok = (b) => (b ? 'BIEN' : 'MAL ');
const PNG = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
    'base64');

(async () => {
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: 390, height: 900 } });
    const page = await ctx.newPage();

    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: CUENTA, password: CLAVE } });
    const tok = (await r.json()).access_token;
    const ra = await page.request.post(`${API}/api/auth/login`, { data: { email: ADMIN, password: ADMIN_CLAVE } });
    if (!ra.ok()) { console.log('no entro como admin:', ra.status()); await nav.close(); return; }
    const cabAdmin = { Authorization: `Bearer ${(await ra.json()).access_token}` };

    console.log('\n=== BLOQUE B · el circuito entero ===\n');

    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);
    await page.goto(`${APP}/dashboard/foods`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(8000);
    const s = page.locator('[data-testid="recorrido-saltar"]');
    if (await s.count()) { await s.click({ force: true }); await page.waitForTimeout(2000); }

    const NOMBRE = `Pechuga de pollo al natural lata (prueba ${Date.now().toString().slice(-6)})`;
    await page.locator('[data-testid="pedir-alimento"] button').click();
    await page.waitForTimeout(2500);
    await page.fill('[data-testid="solicitar-nombre"]', NOMBRE);
    await page.setInputFiles('[role="dialog"] input[type="file"] >> nth=0', { name: 'f.png', mimeType: 'image/png', buffer: PNG });
    await page.setInputFiles('[role="dialog"] input[type="file"] >> nth=1', { name: 'r.png', mimeType: 'image/png', buffer: PNG });
    await page.locator('[data-testid="solicitar-por-unidad"] button >> nth=1').click();   // por unidad
    await page.waitForTimeout(400);
    await page.fill('[data-testid="solicitar-racion"]', '52');
    const m = page.locator('[data-testid="solicitar-macros"] input');
    await m.nth(0).fill('13.5'); await m.nth(1).fill('0.3'); await m.nth(2).fill('0.5');
    await page.locator('[data-testid="solicitar-conserva"] button >> nth=1').click();     // si, lata
    await page.waitForTimeout(600);
    await page.locator('[data-testid="solicitar-escurrido"] button >> nth=0').click();    // si, escurrido
    await page.locator('[data-testid="solicitar-sin-web"]').check();
    await page.waitForTimeout(700);

    const boton = page.locator('[data-testid="solicitar-enviar"]');
    console.log('el botón, con todo puesto ->', (await boton.isDisabled()) ? 'sigue apagado  MAL' : 'encendido  BIEN');
    await boton.click();
    await page.waitForTimeout(4000);
    console.log('el diálogo se cierra      ->', ok(await page.locator('[data-testid="solicitar-enviar"]').count() === 0));

    // Y ahora, el panel del equipo.
    const panel = await (await page.request.get(`${API}/api/admin/food-suggestions?status=pending`, { headers: cabAdmin })).json();
    const mia = panel.find(x => (x.food || {}).nombre === NOMBRE);
    if (!mia) { console.log('MAL: no ha llegado al panel'); await nav.close(); return; }
    const f = mia.food;
    console.log('\nlo que ve el equipo:');
    console.log('   nombre        ->', f.nombre);
    console.log('   por unidad    ->', f.por_unidad, 'de', f.racion, 'g   ' + ok(f.por_unidad === true && f.racion === 52));
    console.log('   es conserva   ->', f.es_conserva, '  ' + ok(f.es_conserva === true));
    console.log('   tipo de peso  ->', f.peso_tipo, '  ' + ok(f.peso_tipo === 'escurrido'));
    console.log('   macros        ->', f.proteinas, f.hidratos, f.grasas);
    console.log('   sin web       ->', f.sin_web, '  ' + ok(f.sin_web === true));
    console.log('   fotos         ->', (mia.photos || []).join(' + '), '  ' + ok((mia.photos || []).length === 2));

    // Y en la PANTALLA del equipo, que es donde se revisa.
    const admin = await ctx.newPage();
    await admin.setViewportSize({ width: 1400, height: 950 });
    await admin.goto(APP, { waitUntil: 'domcontentloaded' });
    const tokAdmin = cabAdmin.Authorization.replace('Bearer ', '');
    await admin.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tokAdmin);
    await admin.goto(`${APP}/admin/alimentos`, { waitUntil: 'networkidle' }).catch(() => {});
    await admin.waitForTimeout(7000);
    const enPantalla = await admin.locator('body').innerText();
    const bloque = enPantalla.split('\n').filter(Boolean);
    const i = bloque.findIndex(l => l.includes(NOMBRE.slice(0, 30)));
    console.log('\nen la pantalla del equipo:');
    if (i < 0) {
        console.log('   MAL: no sale la solicitud en la pantalla');
    } else {
        console.log('   ' + bloque.slice(i, i + 8).map(s => s.trim()).join(' | '));
        console.log('   lo de la lata se ve ->', ok(/lata o conserva/i.test(enPantalla)));
        console.log('   «no tiene web»      ->', ok(/no tiene web/i.test(enPantalla)));
    }
    await admin.screenshot({ path: '_guia/_bloque_b_panel.png' });

    const bo = await page.request.delete(`${API}/api/admin/food-suggestions/${mia.id}`, { headers: cabAdmin });
    console.log('\nsolicitud de prueba borrada ->', bo.status());
    console.log('captura del panel -> _guia/_bloque_b_panel.png');
    await nav.close();
})();
