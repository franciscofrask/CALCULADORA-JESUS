/**
 * La imagen del chat se abre AQUI y no en otra pestaña (Francisco, 26-08).
 *
 * Antes era un <a target="_blank">: en el movil eso te saca de la app y de la conversacion
 * para ver una foto. Ahora abre el visor encima.
 *
 * Uso:  node _guia/_visor_chat_2608.js [ancho] [texto de la conversacion]
 */
const { chromium } = require('playwright');
const path = require('path');
const APP = 'http://localhost:3000';
const API = 'http://127.0.0.1:8000';

(async () => {
    const ancho = Number(process.argv[2]) || 390;
    const texto = process.argv[3] || 'La etiqueta del bote';
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 800 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    page.on('pageerror', (e) => console.log('  [pageerror]', String(e).slice(0, 160)));
    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: 'francisco@test.com', password: 'demo123' } });
    const j = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, j.access_token || j.token);
    await page.goto(`${APP}/admin/messages`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(9000);

    const conv = page.getByText(texto).first();
    if (await conv.count()) { await conv.click(); await page.waitForTimeout(6000); }

    const img = page.locator('[data-testid="adjunto-imagen"]').first();
    const n = await img.count();
    console.log('imagenes en la conversacion:', n);
    if (!n) { console.log('(no hay imagen; no se puede probar)'); await nav.close(); return; }

    console.log('¿sigue siendo un enlace que se va fuera?',
        await img.evaluate((e) => (e.tagName === 'A' ? 'SI, es <a target=_blank>' : `no, es <${e.tagName.toLowerCase()}>`)));
    await img.click();
    await page.waitForTimeout(1300);
    const visor = page.locator('[data-testid="visor-foto"]');
    console.log('¿abre el visor?', (await visor.count()) ? 'SI' : 'NO');
    console.log('   pestañas abiertas:', ctx.pages().length, '(tiene que seguir habiendo 1)');
    if (await visor.count()) {
        console.log('   ' + await page.evaluate(() => {
            const i = document.querySelector('[data-testid="visor-foto-imagen"]');
            const r = i.getBoundingClientRect();
            return `la foto ocupa ${Math.round(r.width)}x${Math.round(r.height)} con object-fit: ${getComputedStyle(i).objectFit}`;
        }));
        await page.screenshot({ path: path.join(__dirname, '_nutricion_2608', 'visor-chat.jpg'), type: 'jpeg', quality: 78 });
        await page.locator('[data-testid="visor-foto-cerrar"]').click();
        await page.waitForTimeout(900);
        console.log('¿lo cierra la X?', (await visor.count()) ? 'NO' : 'SI');
    }
    await nav.close();
})();
