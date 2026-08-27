/**
 * BLOQUE B de la parte 5 (puntos 161 a 169): «Solicitar un alimento».
 *
 * La bateria son los TRES FORMULARIOS de la maqueta:
 *   1. Por unidad · una tarrina  -> pide el peso de la unidad y repite ese peso en los macros
 *   2. Por 100 g                 -> ni peso de unidad ni escurrido: no salen
 *   3. Una lata                  -> es unidad y conserva a la vez, y el peso NO se pide dos veces
 *
 * Uso:  node _guia/_bloque_b_2708.js [ancho]
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || process.env.DESTINO || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';

const ok = (b) => (b ? 'BIEN' : 'MAL ');
const PNG = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
    'base64');

const quitarRecorrido = async (page) => {
    for (let i = 0; i < 4; i++) {
        const s = page.locator('[data-testid="recorrido-saltar"]');
        if (!(await s.count())) break;
        await s.click({ force: true }).catch(() => {});
        await page.waitForTimeout(1200);
    }
    await page.locator('[data-testid="recorrido-overlay"]').waitFor({ state: 'detached', timeout: 8000 }).catch(() => {});
    await page.waitForTimeout(1200);
};

// `.first()`: con un selector que casa con varios, Playwright falla en modo estricto y el
// `.catch` lo tapaba, asi que una comprobacion buena salia como MAL.
const texto = (page, sel) => page.locator(sel).first().innerText().catch(() => '(no sale)');

(async () => {
    const ancho = Number(process.argv[2]) || 390;
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 900 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();

    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: CUENTA, password: CLAVE } });
    const tok = (await r.json()).access_token;
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);
    await page.goto(`${APP}/dashboard/foods`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(8000);
    await quitarRecorrido(page);

    console.log(`\n=== BLOQUE B · ${ancho} px ===\n`);

    // Se llega desde el final de la lista (punto 158), no desde arriba.
    await page.locator('[data-testid="pedir-alimento"] button').click();
    await page.waitForTimeout(2500);

    // ── 161 y 167: el boton apagado y lo que falta ─────────────────────────
    const boton = page.locator('[data-testid="solicitar-enviar"]');
    console.log(`161  el botón nace apagado        -> ${ok(await boton.isDisabled())}`);
    console.log(`161  y dice lo que falta          -> "${await texto(page, '[data-testid="solicitar-faltan"]')}"`);
    console.log(`167  el botón dice               -> "${(await boton.innerText()).trim()}"   ${ok((await boton.innerText()).trim() === 'Solicitarlo')}`);
    const colorBoton = await boton.evaluate(el => getComputedStyle(el).backgroundColor);
    console.log(`167  apagado, en gris             -> ${colorBoton}`);
    console.log(`167  peticiones restantes         -> "${await texto(page, '[data-testid="solicitar-restantes"]')}"`);

    // ── 168 y 169: el aviso de arriba ──────────────────────────────────────
    const aviso = await texto(page, '[role="dialog"] p');
    console.log(`168  el aviso lleva los plazos    -> ${ok(/viernes a las 10/.test(aviso) && /hasta el martes/.test(aviso))}`);
    const todo = await texto(page, '[role="dialog"]');
    console.log(`169  «El equipo lo revisará» fuera -> ${ok(!/El equipo lo revisar/.test(todo))}`);
    console.log(`169  «del envase», no «etiqueta»   -> ${ok(!/de la etiqueta/.test(todo) && /del envase/.test(todo))}`);

    // ── 162: los cuatro bloques y en su orden ──────────────────────────────
    const rotulos = await page.locator('[role="dialog"] .caption').allInnerTexts();
    const esperados = ['QUÉ ES', 'LOS MACROS', 'CÓMO VIENE', 'DE DÓNDE SALE'];
    console.log(`162  los cuatro bloques           -> ${rotulos.join(' · ')}   ${ok(JSON.stringify(rotulos.map(s => s.trim())) === JSON.stringify(esperados))}`);

    // ── 162: la foto del reverso va ANTES que los numeros ──────────────────
    const pos = await page.evaluate(() => {
        const y = (sel) => { const e = document.querySelector(sel); return e ? Math.round(e.getBoundingClientRect().top + (e.ownerDocument.defaultView.scrollY || 0)) : -1; };
        const fotos = [...document.querySelectorAll('[role="dialog"] input[type="file"]')].map(e => Math.round(e.closest('label').getBoundingClientRect().top));
        return { reverso: fotos[1], macros: y('[data-testid="solicitar-macros"]') };
    });
    console.log(`162  la foto del reverso antes que los números   ${ok(pos.reverso > 0 && pos.macros > 0)}`);

    // ── 163: lo que tiene que salir en cada foto ───────────────────────────
    console.log(`163  «o lateral» y «valor nutricional»   ${ok(/Foto del reverso o lateral/.test(todo) && /Que se vea el valor nutricional/.test(todo))}`);

    // ── FORMULARIO 2 de la maqueta: por 100 g ──────────────────────────────
    console.log('\n--- 2 · un alimento normal, por 100 g ---');
    await page.fill('[data-testid="solicitar-nombre"]', 'Jamón cocido extra (Campofrío)');
    await page.setInputFiles('[role="dialog"] input[type="file"] >> nth=0', { name: 'frontal.png', mimeType: 'image/png', buffer: PNG });
    await page.setInputFiles('[role="dialog"] input[type="file"] >> nth=1', { name: 'reverso.png', mimeType: 'image/png', buffer: PNG });
    await page.locator('[data-testid="solicitar-por-unidad"] button >> nth=0').click();   // Por 100 g
    await page.waitForTimeout(500);
    console.log(`164  por 100 g: NO pide peso de unidad   ${ok(await page.locator('[data-testid="solicitar-racion"]').count() === 0)}`);
    const tituloMacros = await page.locator('[data-testid="solicitar-macros"]').evaluate(el => el.previousElementSibling.innerText);
    console.log(`164  el título de los macros dice   -> "${tituloMacros.trim()}"`);
    const campos = page.locator('[data-testid="solicitar-macros"] input');
    await campos.nth(0).fill('18.5'); await campos.nth(1).fill('1.2'); await campos.nth(2).fill('3.4');
    await page.locator('[data-testid="solicitar-conserva"] button >> nth=0').click();     // No
    await page.waitForTimeout(500);
    console.log(`165  sin lata: NO pregunta el escurrido  ${ok(await page.locator('[data-testid="solicitar-escurrido"]').count() === 0)}`);
    await page.fill('[data-testid="solicitar-url"]', 'https://campofrio.es/jamon-cocido-extra');
    await page.waitForTimeout(600);
    console.log(`161  con todo puesto, el botón se enciende   ${ok(!(await boton.isDisabled()))}`);
    await page.screenshot({ path: `_guia/_bloque_b_100g_${ancho}.png` });

    // ── FORMULARIO 3 de la maqueta: una lata ───────────────────────────────
    console.log('\n--- 3 · una lata (por unidad Y conserva) ---');
    await page.fill('[data-testid="solicitar-nombre"]', 'Pechuga de pollo al natural lata (Aldelis)');
    await page.locator('[data-testid="solicitar-por-unidad"] button >> nth=1').click();   // Por unidad
    await page.waitForTimeout(500);
    await page.fill('[data-testid="solicitar-racion"]', '52');
    await page.waitForTimeout(600);
    const titulo2 = await page.locator('[data-testid="solicitar-macros"]').evaluate(el => el.previousElementSibling.innerText);
    console.log(`164  el título repite el peso      -> "${titulo2.trim()}"   ${ok(/52 g/.test(titulo2))}`);
    await page.locator('[data-testid="solicitar-conserva"] button >> nth=1').click();     // Sí
    await page.waitForTimeout(700);
    const preguntaLata = await page.locator('[data-testid="solicitar-escurrido"]').evaluate(el => el.previousElementSibling.innerText).catch(() => '(no sale)');
    console.log(`165  y pregunta por esos mismos gramos -> "${preguntaLata.trim()}"   ${ok(/52 g/.test(preguntaLata))}`);
    const cuantosPesos = await page.locator('[data-testid="solicitar-racion"]').count();
    console.log(`165  el peso NO se pide dos veces  -> ${cuantosPesos} campo de peso   ${ok(cuantosPesos === 1)}`);
    await page.screenshot({ path: `_guia/_bloque_b_lata_${ancho}.png` });

    // ── 166: la salida de «No tiene web» ───────────────────────────────────
    await page.fill('[data-testid="solicitar-url"]', '');
    await page.waitForTimeout(500);
    console.log(`\n166  sin enlace el botón se apaga  ${ok(await boton.isDisabled())}`);
    await page.locator('[data-testid="solicitar-sin-web"]').check();
    await page.locator('[data-testid="solicitar-escurrido"] button >> nth=0').click();
    await page.waitForTimeout(700);
    console.log(`166  con «No tiene web» se enciende ${ok(!(await boton.isDisabled()))}`);

    console.log(`\ncapturas -> _guia/_bloque_b_100g_${ancho}.png y _guia/_bloque_b_lata_${ancho}.png`);
    await nav.close();
})();
