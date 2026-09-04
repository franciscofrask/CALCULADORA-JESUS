/**
 * CUADRAR NO PUEDE ROMPER UN MACRO QUE ESTABA BIEN (video de Jesus y Gonzalo, 30:06).
 *
 * La C3 pide 40P · 10H · 15G. Con tomate frito, lechuga y calabacin entra con la GRASA
 * CLAVADA en 15 y 4,3 g de hidratos de mas. Bajar el tomate arregla los 4,3 y se lleva 7,5
 * de grasa por delante: la comida entraba con un macro bien y salia con ese macro mal.
 */
const { chromium } = require('playwright');
const APP = 'http://localhost:3000', API = 'http://127.0.0.1:8000';

(async () => {
    const t = await fetch(`${API}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'francisco@test.com', password: 'demo123' }),
    }).then(r => r.json()).then(r => r.access_token);

    const nav = await chromium.launch();
    const p = await (await nav.newContext({
        viewport: { width: 1280, height: 1100 }, locale: 'es-ES', timezoneId: 'Europe/Madrid',
    })).newPage();
    await p.goto(APP, { waitUntil: 'domcontentloaded' });
    await p.evaluate(tk => { localStorage.clear(); localStorage.setItem('token', tk); }, t);
    await p.goto(`${APP}/dashboard/nutrition?date=2026-12-28&comida=C3`, { waitUntil: 'networkidle' });
    await p.waitForTimeout(14000);
    await p.locator('[data-testid="meal-select-C3"]').first().click({ force: true });
    await p.waitForTimeout(2500);

    const grasa = async () => ({
        valor: (await p.locator('[data-testid="comida-macro-C3-G"]:visible').first().innerText()).trim(),
        palabra: (await p.locator('[data-testid="comida-palabra-C3-G"]:visible').first().innerText()).trim(),
    });
    const antes = await grasa();
    console.log(`ANTES   grasa ${antes.valor} · ${antes.palabra}`);

    await p.locator('[data-testid="cuadrar-C3"]:visible').first().click();
    await p.waitForTimeout(9000);
    const despues = await grasa();
    console.log(`DESPUES grasa ${despues.valor} · ${despues.palabra}`);
    for (const a of await p.locator('[data-sonner-toast]').allInnerTexts()) {
        console.log('   aviso:', a.replace(/\s+/g, ' ').slice(0, 140));
    }
    console.log('\nla grasa sigue cuadrada:', /cuadrado|válido/i.test(despues.palabra));
    await p.locator('[data-testid="meal-card-C3"]:visible').first()
        .screenshot({ path: '_guia/_cuadrar_no_rompe.png' }).catch(() => { });
    await nav.close();
})();
