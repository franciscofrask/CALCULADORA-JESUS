/**
 * PUNTO 174 · la otra mitad: el desplegable de la ficha del catálogo.
 *
 * «¿Con qué comida sale en su Inicio?» se elige UNA vez por suplemento y manda sobre el texto
 * del «¿Cuándo?». Aquí se comprueba que se ve, que se guarda, y que de verdad pisa al texto:
 * se coge un suplemento cuyo «¿Cuándo?» dice «con el desayuno» (que sería la primera comida),
 * se le pone «La última comida del día» y se mira que el servidor lo mande a la última.
 *
 * Deja el catálogo como estaba.
 *
 * Uso:  node _guia/_p174_ficha_2708.js
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || process.env.DESTINO || 'http://127.0.0.1:8000';
const ADMIN = process.env.ADMIN || 'francisco@test.com';
const ADMIN_CLAVE = process.env.ADMIN_CLAVE || 'demo123';

const ok = (b) => (b ? 'BIEN' : 'MAL ');

(async () => {
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: 1400, height: 950 } });
    const page = await ctx.newPage();
    const ra = await page.request.post(`${API}/api/auth/login`, { data: { email: ADMIN, password: ADMIN_CLAVE } });
    const tok = (await ra.json()).access_token;
    const cab = { Authorization: `Bearer ${tok}` };

    console.log('\n=== PUNTO 174 · el desplegable de la ficha ===\n');

    // Un suplemento cuyo texto diga «desayuno»: sin tocar nada iría a la primera comida.
    const cat = await (await page.request.get(`${API}/api/admin/supplements/catalog?include_inactive=true`, { headers: cab })).json();
    const ficha = (cat || []).find(c => /desayuno/i.test(c.cuando || '') && !/cena/i.test(c.cuando || ''));
    if (!ficha) { console.log('no hay ninguna ficha con «desayuno» en el ¿Cuándo?'); await nav.close(); return; }
    console.log(`ficha de prueba: «${ficha.titulo}»`);
    console.log(`   ¿Cuándo? -> ${ficha.cuando}`);
    console.log(`   comida guardada hoy -> "${ficha.comida || '(vacío: automático)'}"`);
    const comidaOriginal = ficha.comida || '';

    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);
    await page.goto(`${APP}/admin/supplements-catalog`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(7000);

    // Abrir la ficha por su título.
    const tarjeta = page.locator('p', { hasText: new RegExp(`^${ficha.titulo.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`) }).first();
    if (!(await tarjeta.count())) {
        console.log('no encuentro la ficha en la pantalla. URL actual:', page.url());
        await page.screenshot({ path: '_guia/_p174_ficha_perdida.png', fullPage: true });
        await nav.close(); return;
    }
    await tarjeta.locator('xpath=ancestor::*[contains(@class,"p-4")][1]').locator('button').first().click();
    await page.waitForTimeout(2000);

    const sel = page.locator('[data-testid="catalogo-comida"]');
    console.log(`\nel desplegable sale en la ficha   ${ok(await sel.count() === 1)}`);
    const opciones = await sel.locator('option').allInnerTexts();
    console.log('   opciones ->', opciones.join(' | '));

    await sel.selectOption('ultima');
    await page.getByRole('button', { name: /guardar/i }).last().click();
    await page.waitForTimeout(3500);

    const cat2 = await (await page.request.get(`${API}/api/admin/supplements/catalog?include_inactive=true`, { headers: cab })).json();
    const f2 = (cat2 || []).find(c => c.id === ficha.id);
    console.log(`\nse guarda en la ficha            -> "${f2?.comida}"   ${ok(f2?.comida === 'ultima')}`);

    // Y QUE DE VERDAD PISE AL TEXTO. Se le pauta a un cliente de prueba una línea que apunta
    // a esta ficha y que NO trae comida elegida: su «¿Cuándo?» dice «desayuno» -- la primera
    // comida --, así que si sale «ultima» es porque ha mandado la ficha.
    const rc = await page.request.post(`${API}/api/auth/login`, { data: { email: 'clientedemo@test.com', password: 'demo123' } });
    const tokC = (await rc.json()).access_token;
    const cabC = { Authorization: `Bearer ${tokC}` };
    const yo = await (await page.request.get(`${API}/api/auth/me`, { headers: cabC })).json();
    const lista = await (await page.request.get(`${API}/api/admin/clients?include_incomplete=true`, { headers: cab, timeout: 90000 })).json();
    const cli = (Array.isArray(lista) ? lista : []).find(c => ((c.user || {}).email || '').toLowerCase() === yo.email.toLowerCase());
    // Por la puerta del PANEL: `/supplements/current` limpia los nombres antes de servirlos,
    // así que reponer eso borraría de la base la chuleta de Jesús («Creatina hombre»).
    const _fichaAdmin = await (await page.request.get(`${API}/api/admin/clients/${cli.id}`, { headers: cab })).json().catch(() => ({}));
    const antes = (_fichaAdmin || {}).supplement_protocol || {};
    const habia = !!(antes && (antes.versiones || []).length);
    const d = new Date();
    const FECHA = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    await page.request.post(`${API}/api/admin/supplements/save?client_id=${cli.id}`, {
        headers: cab,
        data: { actual: [{ catalog_id: ficha.id, titulo: ficha.titulo, cuando: ficha.cuando, cuanto: ficha.cuanto || '' }],
                actual_fecha: FECHA, siguiente: [] },
    });
    const prot = await (await page.request.get(`${API}/api/supplements/current`, { headers: cabC })).json();
    const sale = ((prot.actual || [])[0] || {}).en_comidas || [];
    console.log(`\nla ficha pisa al texto           -> [${sale.join(',') || 'nada'}]   ${ok(sale.join(',') === 'ultima')}`);
    console.log('   (el «¿Cuándo?» dice «desayuno», que sería la primera; la ficha dice la última)');
    if (habia) {
        await page.request.post(`${API}/api/admin/supplements/save?client_id=${cli.id}`, {
            headers: cab, data: { actual: antes.actual || [], actual_fecha: antes.actual_fecha || FECHA, siguiente: antes.siguiente || [] } });
    } else {
        await page.request.delete(`${API}/api/admin/supplements/version/${FECHA}?client_id=${cli.id}`, { headers: cab });
    }

    // Se repone.
    await page.request.put(`${API}/api/admin/supplements/catalog/${ficha.id}`, {
        headers: cab, data: { ...ficha, comida: comidaOriginal },
    });
    const cat3 = await (await page.request.get(`${API}/api/admin/supplements/catalog?include_inactive=true`, { headers: cab })).json();
    const f3 = (cat3 || []).find(c => c.id === ficha.id);
    console.log(`\nficha repuesta                   -> "${f3?.comida || '(vacío)'}"   ${ok((f3?.comida || '') === comidaOriginal)}`);
    await nav.close();
})();
