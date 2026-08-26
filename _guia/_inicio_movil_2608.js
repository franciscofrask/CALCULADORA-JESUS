/**
 * El Inicio del cliente a 390 px, pestaña a pestaña (artifact del 25-08, fases 2 y 3).
 * Comprueba lo que no se ve en el escritorio: que los tres números caben, que van en
 * blanco, y que el intra y el post salen con su círculo en su sitio.
 *
 * Uso:  node _guia/_inicio_movil_2608.js [cuenta]
 * Deja JPEG en _guia/_inicio_movil_2608/
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const APP = 'http://localhost:3000';
const API = 'http://localhost:8000';
const SALIDA = path.join(__dirname, '_inicio_movil_2608');

const CUENTAS = {
    demo: { email: 'clientedemo@test.com', password: 'demo123' },
    admin: { email: 'francisco@test.com', password: 'demo123' },
};

(async () => {
    const quien = process.argv[2] || 'demo';
    fs.mkdirSync(SALIDA, { recursive: true });
    const navegador = await chromium.launch();
    const ctx = await navegador.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();

    const r = await page.request.post(`${API}/api/auth/login`, { data: CUENTAS[quien] });
    if (!r.ok()) throw new Error(`login ${quien}: ${r.status()}`);
    const { access_token, token } = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, access_token || token);

    await page.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(4000);

    // El recorrido de la primera vez tapa la pantalla entera: al limpiar el navegador
    // vuelve a salir. Se salta, que aquí estorba.
    const saltar = page.getByRole('button', { name: /saltar/i }).first();
    if (await saltar.count()) { await saltar.click().catch(() => {}); await page.waitForTimeout(1500); }

    for (const pestana of ['Macros', 'Dieta', 'Llevas', 'Falta']) {
        const b = page.locator(`[data-testid="vista-${pestana.toLowerCase()}"]`).first();
        if (await b.count()) { await b.click().catch(() => {}); await page.waitForTimeout(800); }
        await page.screenshot({ path: path.join(SALIDA, `${quien}-${pestana.toLowerCase()}.jpg`), type: 'jpeg', quality: 70 });
        // Lo que de verdad importa: color y caja de los números.
        const datos = await page.evaluate(() => {
            const n = document.querySelector('.numero-grande');
            if (!n) return null;
            const cs = getComputedStyle(n);
            const caja = document.querySelector('[data-testid="macros-de-hoy"]');
            return {
                color: cs.color, peso: cs.fontWeight, tam: cs.fontSize,
                desborda: caja ? caja.scrollWidth > caja.clientWidth : null,
                numeros: [...document.querySelectorAll('.numero-grande')].map((x) => x.textContent),
            };
        });
        console.log(pestana, JSON.stringify(datos));
    }

    await page.screenshot({ path: path.join(SALIDA, `${quien}-completa.jpg`), type: 'jpeg', quality: 70, fullPage: true });
    const lista = await page.evaluate(() => [...document.querySelectorAll('[data-testid^="comida-hoy-"]')]
        .map((f) => f.innerText.replace(/\n+/g, ' · ')));
    console.log('LISTA:', JSON.stringify(lista, null, 1));

    await navegador.close();
    console.log('Capturas en', SALIDA);
})();
