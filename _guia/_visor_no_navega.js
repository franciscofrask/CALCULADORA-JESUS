/**
 * Cerrar la foto NO puede llevarte a otra pantalla ni recargar (Francisco, 26-08, visto en
 * produccion: al cerrar aparecia en el Inicio).
 *
 * La causa era un `pushState` propio que machacaba el `idx` de React Router.
 *
 * Uso:  node _guia/_visor_no_navega.js [ancho]
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.DESTINO || 'http://127.0.0.1:8000';

(async () => {
    const ancho = Number(process.argv[2]) || 390;
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 800 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: process.env.CUENTA || 'qa.b10.hombre@test.com', password: process.env.CLAVE || 'demo123' } });
    const j = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, j.access_token || j.token);

    // Se navega COMO UN CLIENTE, para que el historial tenga entradas de verdad:
    // Inicio -> Seguimiento -> Evolucion. Ahi estaba el fallo.
    await page.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(7000);
    const saltar = page.getByRole('button', { name: /saltar/i }).first();
    if (await saltar.count()) { await saltar.click().catch(() => {}); await page.waitForTimeout(1500); }
    await page.goto(`${APP}/dashboard/reports`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(6000);
    const ev = page.getByText('Evolución', { exact: true }).first();
    if (await ev.count()) { await ev.click(); await page.waitForTimeout(7000); }
    await page.waitForSelector('[data-testid="foto-comparativa"]', { timeout: 20000 }).catch(() => {});

    const fotos = page.locator('[data-testid="foto-comparativa"]');
    if (!(await fotos.count())) { console.log('(sin fotos, no se puede probar)'); await nav.close(); return; }

    // Marca en la ventana: si la pagina recarga, se pierde.
    await page.evaluate(() => { window.__marca = 'sigo-viva'; });
    const urlAntes = page.url();
    const estadoAntes = JSON.stringify(await page.evaluate(() => window.history.state));
    console.log('antes de abrir  ->', urlAntes.replace(APP, ''), '| history.state:', estadoAntes);

    await fotos.first().click();
    await page.waitForTimeout(1000);
    console.log('visor abierto   ->', (await page.locator('[data-testid="visor-foto"]').count()) ? 'SI' : 'NO',
        '| history.state:', JSON.stringify(await page.evaluate(() => window.history.state)));

    await page.locator('[data-testid="visor-foto-cerrar"]').click();
    await page.waitForTimeout(2000);
    const urlDespues = page.url();
    const marca = await page.evaluate(() => window.__marca);
    console.log('\ntras cerrar con la X:');
    console.log('   ¿me ha movido de pantalla?', urlAntes === urlDespues ? 'NO, sigo en ' + urlDespues.replace(APP, '') : 'SI -> ' + urlDespues.replace(APP, ''));
    console.log('   ¿ha recargado?', marca === 'sigo-viva' ? 'NO' : 'SI, se perdio la marca');
    console.log('   ¿sigo viendo la comparativa?', (await page.locator('[data-testid="comparativa-cliente"]').count()) ? 'SI' : 'NO');
    console.log('   history.state:', JSON.stringify(await page.evaluate(() => window.history.state)));

    // Y cerrando por el fondo.
    await fotos.first().click();
    await page.waitForTimeout(900);
    await page.locator('[data-testid="visor-foto"]').click({ position: { x: 5, y: 400 } });
    await page.waitForTimeout(1500);
    console.log('\ntras cerrar tocando el fondo:');
    console.log('   ¿me ha movido?', page.url() === urlAntes ? 'NO' : 'SI -> ' + page.url().replace(APP, ''));
    console.log('   ¿ha recargado?', (await page.evaluate(() => window.__marca)) === 'sigo-viva' ? 'NO' : 'SI');
    await nav.close();
})();
