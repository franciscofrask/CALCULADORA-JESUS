/**
 * EL BUCLE DE «MACROS PROVISIONALES» (Francisco, 26-08, visto en produccion).
 *
 * El aviso dice «revisa tu edad», llevas a «Completar mis datos» y el cuestionario salta
 * directo a «y ya estaria, estos son tus macros iniciales» sin preguntar nada, porque
 * `falta()` solo repregunta lo VACIO y una edad de 0 no esta vacia. Vuelves al Inicio y el
 * aviso sigue.
 *
 * Aqui se comprueba que ahora SI pregunta.
 *
 * Uso:  node _guia/_bucle_macros_provisionales.js [ancho]
 */
const { chromium } = require('playwright');
const path = require('path');
const APP = 'http://localhost:3000';
const API = 'http://127.0.0.1:8000';

(async () => {
    const ancho = Number(process.argv[2]) || 390;
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 900 }, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    page.on('pageerror', (e) => console.log('  [pageerror]', String(e).slice(0, 200)));
    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: 'francisco@test.com', password: 'demo123' } });
    const j = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, j.access_token || j.token);
    await page.goto(`${APP}/dashboard/profile`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(7000);
    const saltar = page.getByRole('button', { name: /saltar/i }).first();
    if (await saltar.count()) { await saltar.click().catch(() => {}); await page.waitForTimeout(1500); }

    const aviso = page.locator('[data-testid="macros-provisionales"]');
    console.log('¿sale el aviso en Mi perfil?', (await aviso.count()) ? 'SI' : 'NO');
    if (!(await aviso.count())) { console.log('(sin aviso no hay bucle que probar)'); await nav.close(); return; }
    console.log('   dice: ' + (await aviso.innerText()).replace(/\n+/g, ' · '));

    await page.getByText('Completar mis datos').first().click();
    await page.waitForTimeout(7000);
    console.log('\nURL:', page.url());
    const texto = await page.evaluate(() => document.body.innerText.replace(/\n+/g, ' · ').slice(0, 240));
    console.log('LA PRIMERA PANTALLA DEL RECORRIDO:');
    console.log('   ' + texto);
    const yaEsta = /ya estaría|estos son tus macros/i.test(texto);
    console.log('\n¿salta directo al final (el bucle)?', yaEsta ? 'SI, SIGUE EL BUCLE' : 'no, le pregunta');
    await page.screenshot({ path: path.join(__dirname, '_nutricion_2608', 'bucle-macros.jpg'), type: 'jpeg', quality: 75 });

    // Se recorre el cuestionario hasta el final, que es donde estaba el bucle.
    console.log('\nRECORRIENDO:');
    for (let i = 0; i < 25; i++) {
        // El titulo de la pregunta, no la cabecera fija de «ajustando tus macros».
        const t = await page.evaluate(() => {
            const h = document.querySelector('h1, h2');
            return (h?.innerText || document.body.innerText).replace(/\n+/g, ' · ').slice(0, 60);
        });
        const btn = page.getByRole('button', { name: /Continuar|Siguiente|Empezar|Entendido|Guardar|Entrar|Ir a mi panel|Vamos|Seguir|Listo|Terminar|Finalizar|Ver mis macros/i }).first();
        if (!(await btn.count())) {
            // Pregunta de opciones: se elige la primera que no sea «Atrás».
            const opcion = page.locator('button').filter({ hasNotText: /^Atrás$/ }).first();
            if (await opcion.count()) {
                console.log(`   [${i}] ${(await opcion.innerText()).replace(/\n/g, ' ').trim().slice(0, 14).padEnd(14)} | ${t}`);
                await opcion.click().catch(() => {});
                await page.waitForTimeout(2200);
                continue;
            }
            const botones = await page.evaluate(() => [...document.querySelectorAll('button')]
                .map(b => b.innerText.replace(/\n/g, ' ').trim()).filter(Boolean).slice(0, 6));
            console.log(`   [${i}] (ningun boton) ${t}  ·  hay: ${JSON.stringify(botones)}`);
            break;
        }
        const rotulo = (await btn.innerText()).replace(/\n/g, ' ').trim().slice(0, 14);
        console.log(`   [${i}] ${rotulo.padEnd(14)} | ` + t);
        if (page.url().includes('/dashboard')) break;
        await btn.click().catch(() => {});
        await page.waitForTimeout(2200);
    }

    // Y de vuelta a Mi perfil, que es donde el aviso se quedaba puesto.
    await page.goto(`${APP}/dashboard/profile`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(6000);
    const sigue = await page.locator('[data-testid="macros-provisionales"]').count();
    console.log('\n¿sigue el aviso tras el recorrido?', sigue ? 'SI' : 'NO, se ha ido');
    await nav.close();
})();
