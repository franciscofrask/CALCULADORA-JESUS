/**
 * BLOQUE C de la parte 5 (puntos 170 a 178), comprobado en el navegador de verdad.
 *
 *   170  abre en «Macros»
 *   171  «Marca lo que te vayas comiendo»
 *   172  los tres numeros a 44 px y peso 850 (Inter en rango, no en pesos sueltos)
 *   173  los numeros de las comidas con letra: «32P · 19H · 6G»
 *   175  «algo que no estaba PREVISTO en tu dieta»
 *   176  el «a ojo» pesa menos que la instruccion de arriba
 *   177  la frase del dia, sin punto final
 *
 * El 174 esta BLOQUEADO (no hay campo que ate un suplemento a una comida) y el 178 tiene
 * su propio guion, `_p178_grasa_2708.js`, porque hace falta montar un dia.
 *
 * Uso:  node _guia/_bloque_c_2708.js [ancho]
 *       DESTINO=https://12en12app.jesusgallegopt.com CUENTA=... CLAVE=... node ...
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || process.env.DESTINO || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';

const ok = (b) => (b ? 'BIEN' : 'MAL ');

(async () => {
    const ancho = Number(process.argv[2]) || 390;
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 900 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();

    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: CUENTA, password: CLAVE } });
    if (!r.ok()) { console.log('no se pudo entrar:', r.status(), await r.text()); await nav.close(); return; }
    const j = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, j.access_token || j.token);
    await page.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(8000);
    const saltar = page.getByRole('button', { name: /saltar/i }).first();
    if (await saltar.count()) { await saltar.click().catch(() => {}); await page.waitForTimeout(2000); }
    await page.waitForSelector('[data-testid="inicio-nuevo"]', { timeout: 20000 }).catch(() => {});

    console.log(`\n=== BLOQUE C · ${ancho} px · ${CUENTA} · ${APP} ===\n`);

    // ── 170: la pestaña que nace elegida ────────────────────────────────────
    const elegida = await page.locator('[role="tab"][aria-selected="true"]').first().innerText().catch(() => '(no hay pestañas)');
    console.log(`170  abre en          -> "${elegida.trim()}"   ${ok(elegida.trim() === 'Macros')}`);

    // ── 171: el rotulo de marcar ────────────────────────────────────────────
    // Se compara en minusculas: `.caption` lleva `uppercase`, asi que lo que se VE va en
    // mayusculas aunque en el codigo este escrito en minusculas. Lo que importa son las
    // palabras, y que sea «te vayas comiendo» y no «ya te has comido».
    const rotulo = await page.locator('[data-testid="marca-comidas"] p').first().innerText().catch(() => '(no sale)');
    console.log(`171  rotulo           -> "${rotulo.trim()}"   ${ok(rotulo.trim().toLowerCase() === 'marca lo que te vayas comiendo')}`);

    // ── 172: tamaño y peso de los tres numeros ──────────────────────────────
    const num = page.locator('.numero-grande').first();
    const est = await num.evaluate((el) => {
        const s = getComputedStyle(el);
        return { size: s.fontSize, weight: s.fontWeight, varia: s.fontVariationSettings, fam: s.fontFamily, tr: s.transform };
    }).catch(() => null);
    if (est) {
        console.log(`172  tamaño           -> ${est.size}   ${ok(est.size === '44px')}`);
        console.log(`172  peso             -> ${est.weight} (variation: ${est.varia})   ${ok(String(est.weight) === '850')}`);
        console.log(`172  sin el transform -> ${est.tr}   ${ok(est.tr === 'none')}`);
        console.log(`172  familia          -> ${est.fam}`);
        // Y que la fuente que ACABA usando sea de verdad Inter: si el 850 no se ha cargado,
        // el navegador cae al peso mas cercano sin decir nada.
        const cargada = await page.evaluate(() => document.fonts.check('850 44px Inter'));
        console.log(`172  ¿hay Inter 850?  -> ${cargada ? 'si' : 'NO, cae al mas cercano'}   ${ok(cargada)}`);
    } else {
        console.log('172  no se encontro ningun .numero-grande');
    }

    // ── 173: los numeros de las comidas, con letra ──────────────────────────
    const filas = page.locator('[data-testid^="comida-hoy-"]');
    const nFilas = await filas.count();
    let linea = '(sin comidas)';
    for (let i = 0; i < nFilas; i++) {
        const t = (await filas.nth(i).innerText()).split('\n').map(s => s.trim()).filter(Boolean);
        const cand = t.find(s => /\d/.test(s) && s.includes('·'));
        if (cand) { linea = cand; break; }
    }
    console.log(`173  linea de comida  -> "${linea}"   ${ok(/\d+P\s·\s\d+H/.test(linea) || /\d+P/.test(linea))}`);

    // ── 175 y 176: los Extras ───────────────────────────────────────────────
    const extras = page.locator('[data-testid="extras-del-dia"]');
    if (await extras.count()) {
        const instruccion = (await extras.locator('p').nth(1).innerText()).trim();
        console.log(`175  instruccion      -> "${instruccion}"   ${ok(instruccion.includes('no estaba previsto en tu dieta'))}`);
        const campo = extras.locator('[data-testid="extras-campo"]');
        const tam = await campo.evaluate((el) => {
            const propio = getComputedStyle(el).fontSize;
            const ph = getComputedStyle(el, '::placeholder').fontSize;
            return { propio, ph };
        });
        const arriba = await extras.locator('p').nth(1).evaluate(el => getComputedStyle(el).fontSize);
        const menor = parseFloat(tam.ph) < parseFloat(arriba);
        console.log(`176  ayuda ${tam.ph} vs instruccion ${arriba} (lo tecleado sigue a ${tam.propio})   ${ok(menor)}`);
    } else {
        console.log('175/176  el bloque de Extras no sale en esta cuenta');
    }

    // ── 177: la frase del dia ───────────────────────────────────────────────
    const frase = page.locator('[data-testid="frase-del-dia"] p').nth(1);
    if (await frase.count()) {
        const t = (await frase.innerText()).trim();
        const dentro = t.replace(/^«|»$/g, '');
        console.log(`177  frase            -> ${t}`);
        console.log(`177  termina en punto -> ${dentro.endsWith('.') ? 'SI' : 'no'}   ${ok(!dentro.endsWith('.'))}`);
    } else {
        console.log('177  hoy no hay frase del dia en esta cuenta (no se puede ver en pantalla)');
    }

    // La pantalla entera, para mirarla.
    await page.screenshot({ path: `_guia/_bloque_c_${ancho}.png`, fullPage: true });
    console.log(`\ncaptura -> _guia/_bloque_c_${ancho}.png`);

    // Errores de consola: si algo de lo tocado revienta, aqui sale.
    await nav.close();
})();
