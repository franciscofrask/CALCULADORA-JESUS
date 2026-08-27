/**
 * El acceso al asistente (chatbot), oculto para todos (Francisco, 26-08).
 * Son TRES puertas: el menu lateral, la tarjeta de Mi perfil y la propia direccion.
 *
 * Uso:  node _guia/_asistente_oculto_2608.js [ancho]
 */
const { chromium } = require('playwright');
const APP = 'http://localhost:3000';
const API = 'http://127.0.0.1:8000';

(async () => {
    const ancho = Number(process.argv[2]) || 1280;
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 900 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    page.on('pageerror', (e) => console.log('  [pageerror]', String(e).slice(0, 160)));
    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: 'francisco@test.com', password: 'demo123' } });
    const j = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, j.access_token || j.token);

    await page.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(7000);
    const saltar = page.getByRole('button', { name: /saltar/i }).first();
    if (await saltar.count()) { await saltar.click().catch(() => {}); await page.waitForTimeout(1500); }
    const enElMenu = await page.getByText('Asistente IA').count();
    console.log(`1) en el menu (${ancho} px):`, enElMenu ? 'SIGUE SALIENDO' : 'no sale');

    await page.goto(`${APP}/dashboard/profile`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(6000);
    console.log('2) en Mi perfil:', (await page.getByText('Asistente IA').count()) ? 'SIGUE SALIENDO' : 'no sale');

    await page.goto(`${APP}/dashboard/chatbot`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(6000);
    console.log('3) por la direccion:', page.url().includes('/chatbot') ? 'ENTRA IGUAL -> ' + page.url() : 'no entra, va a ' + page.url().replace(APP, ''));
    await nav.close();
})();
