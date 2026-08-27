/**
 * La tarjeta de EDAD en el repaso, sin recorrer el cuestionario entero.
 *
 * Se comprueba lo que fallaba: con el recorrido de «completar» (una sola pantalla, la de
 * contacto), la rejilla de «Confirma tus respuestas» salia SIN NINGUNA tarjeta.
 * Se llega al repaso pulsando «Continuar» en la pantalla de contacto, que ya viene
 * rellena, y de ahi al repaso.
 *
 * Uso:  node _guia/_repaso_directo.js
 */
const { chromium } = require('playwright');
const path = require('path');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.DESTINO || 'http://127.0.0.1:8000';

(async () => {
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: 390, height: 900 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    page.on('pageerror', (e) => console.log('  [pageerror]', String(e).slice(0, 180)));
    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: process.env.CUENTA || 'francisco@test.com', password: process.env.CLAVE || 'demo123' } });
    const j = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, j.access_token || j.token);
    await page.goto(`${APP}/questionnaire?completar=1`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(9000);

    // Se avanza SOLO por los botones de continuar (nunca se contesta nada): con eso se
    // llega hasta donde el recorrido pide algo, o hasta el repaso.
    for (let i = 0; i < 20; i++) {
        if (await page.locator('[data-testid="repaso-respuestas"]').count()) break;
        let b = page.getByRole('button', { name: /^(Empezar|Seguir|Continuar|Siguiente)$/i }).first();
        if (!(await b.count()) || !(await b.isEnabled().catch(() => false))) {
            // Pregunta de opciones: se elige la primera que no sea «Atras» ni «OK».
            b = page.locator('button').filter({ hasNotText: /^(Atrás|OK)$/ }).first();
            if (!(await b.count())) break;
        }
        await b.click().catch(() => {});
        await page.waitForTimeout(2000);
    }

    const enRepaso = await page.locator('[data-testid="repaso-respuestas"]').count();
    const donde = await page.evaluate(() => (document.querySelector('h1, h2')?.innerText || '').slice(0, 50));
    console.log('donde para:', donde, '| ¿repaso?', enRepaso ? 'SI' : 'no');
    if (enRepaso) {
        const tarjetas = await page.evaluate(() => [...document.querySelectorAll('[data-testid^="repaso-"]')]
            .filter(e => e.getAttribute('data-testid') !== 'repaso-respuestas')
            .map(e => e.innerText.replace(/\n+/g, ': ')));
        console.log('tarjetas:', tarjetas.length);
        tarjetas.forEach(t => console.log('   · ' + t));
        console.log('\n¿sale vacia (el fallo)?', tarjetas.length === 0 ? 'SI' : 'NO');
        console.log('¿tiene la tarjeta de Edad?', (await page.locator('[data-testid="repaso-contacto"]').count()) ? 'SI' : 'no');
    }
    await page.screenshot({ path: path.join(__dirname, '_nutricion_2608', 'repaso.jpg'), type: 'jpeg', quality: 75 });
    await nav.close();
})();
