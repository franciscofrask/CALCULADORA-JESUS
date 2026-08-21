/** Solo el bloque 11: el formulario del reporte en modo revisión (?ver=semanal, equipo). */
const { chromium } = require('playwright');
const path = require('path');
const APP = 'http://localhost:3000';
const API = 'http://localhost:8000';
const SALIDA = path.join(__dirname, 'capturas_repaso_2108');

(async () => {
    const navegador = await chromium.launch();
    const ctx = await navegador.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();
    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: 'francisco@test.com', password: 'demo123' } });
    const { access_token, token } = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, access_token || token);
    await page.goto(`${APP}/dashboard/reports?ver=semanal`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(4000);
    const texto = await page.evaluate(() => document.body.innerText);
    console.log('tiene formulario:', texto.includes('Reporte semanal'), '| tiene No puedo esta semana:', texto.includes('No puedo esta semana'));
    await page.screenshot({ path: path.join(SALIDA, 'b11-2-reportes-no-puedo.jpg'), type: 'jpeg', quality: 50, fullPage: true });
    // El flujo de aplazar abierto
    await page.goto(`${APP}/dashboard/reports?ver=semanal&aplazar=1`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3500);
    const t2 = await page.evaluate(() => document.body.innerText);
    console.log('aplazar abierto:', t2.includes('decirme algo') || t2.toLowerCase().includes('aplaz'));
    await page.screenshot({ path: path.join(SALIDA, 'b11-3-aplazar-abierto.jpg'), type: 'jpeg', quality: 50, fullPage: true });
    await navegador.close();
})();
