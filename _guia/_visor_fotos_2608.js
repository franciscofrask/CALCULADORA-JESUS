/**
 * Al tocar una foto se ve en grande (Francisco, 26-08).
 * Se comprueba en Seguimiento: que abre, que la foto sale ENTERA (object-contain y no
 * recortada), que el fondo no se mueve, que se cierra con la X, tocando fuera y con el
 * gesto de atras del movil.
 *
 * Uso:  node _guia/_visor_fotos_2608.js [ancho] [email]
 */
const { chromium } = require('playwright');
const path = require('path');
const APP = 'http://localhost:3000';
const API = 'http://127.0.0.1:8000';

(async () => {
    const ancho = Number(process.argv[2]) || 390;
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 800 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    page.on('pageerror', (e) => console.log('  [pageerror]', String(e).slice(0, 160)));
    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: process.argv[3] || 'qa.b10.hombre@test.com', password: 'demo123' } });
    const { access_token, token } = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, access_token || token);
    await page.goto(`${APP}/dashboard/reports`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(8000);
    const saltar = page.getByRole('button', { name: /saltar/i }).first();
    if (await saltar.count()) { await saltar.click().catch(() => {}); await page.waitForTimeout(1500); }

    // Seguimiento es un indice: las fotos viven dentro de «Evolucion».
    const evolucion = page.getByText('Evolución', { exact: true }).first();
    if (await evolucion.count()) { await evolucion.click(); await page.waitForTimeout(7000); }
    await page.waitForSelector('[data-testid="foto-comparativa"]', { timeout: 20000 }).catch(() => {});

    const fotos = page.locator('[data-testid="foto-comparativa"]');
    const n = await fotos.count();
    console.log('fotos en la comparativa:', n);
    if (!n) { console.log('(esta cuenta no tiene fotos; no se puede probar)'); await nav.close(); return; }

    const scrollAntes = await page.evaluate(() => window.scrollY);
    await fotos.first().click();
    await page.waitForTimeout(900);
    const visor = page.locator('[data-testid="visor-foto"]');
    console.log('¿abre el visor?', (await visor.count()) ? 'SI' : 'NO');
    if (await visor.count()) {
        console.log('   ' + await page.evaluate(() => {
            const img = document.querySelector('[data-testid="visor-foto-imagen"]');
            const s = getComputedStyle(img);
            const r = img.getBoundingClientRect();
            const cuerpo = getComputedStyle(document.body);
            const pie = document.querySelector('[data-testid="visor-foto-pie"]');
            return `la foto ocupa ${Math.round(r.width)}x${Math.round(r.height)} con object-fit: ${s.objectFit}`
                + `  ·  el fondo bloqueado: ${cuerpo.overflow}`
                + `  ·  pie: ${pie ? '«' + pie.innerText + '»' : '(sin pie)'}`;
        }));
        await page.screenshot({ path: path.join(__dirname, '_nutricion_2608', `visor-${ancho}.jpg`), type: 'jpeg', quality: 78 });

        // Cerrar con el gesto de atras, que es lo primero que se hace en un movil.
        await page.goBack();
        await page.waitForTimeout(900);
        console.log('¿lo cierra el boton atras?', (await visor.count()) ? 'NO, sigue abierto' : 'SI');
        console.log('   ¿sigo en Seguimiento?', page.url().includes('/reports') ? 'SI' : 'NO -> ' + page.url());
        console.log('   ¿el fondo vuelve a moverse?', await page.evaluate(() => getComputedStyle(document.body).overflow || '(sin bloquear)'));

        // Y con la X.
        await fotos.first().click();
        await page.waitForTimeout(800);
        await page.locator('[data-testid="visor-foto-cerrar"]').click();
        await page.waitForTimeout(900);
        console.log('¿lo cierra la X?', (await visor.count()) ? 'NO' : 'SI');
        const scrollDespues = await page.evaluate(() => window.scrollY);
        console.log('   la pagina sigue donde estaba:', scrollAntes === scrollDespues ? 'SI' : `NO (${scrollAntes} -> ${scrollDespues})`);
    }
    await nav.close();
})();
