/**
 * BLOQUE A de la parte 5 (puntos 144 a 160): el buscador de alimentos.
 *
 * La bateria son los NUEVE ALIMENTOS DE LA MAQUETA, que Jesus escogio para que entre ellos
 * esten todos los casos: un macro, dos, todos, ninguno; con calibracion y sin ella; generico
 * y marca; por gramos, por unidad y por media unidad.
 *
 * Uso:  node _guia/_bloque_a_2708.js [ancho]
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || process.env.DESTINO || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';

const ok = (b) => (b ? 'BIEN' : 'MAL ');

// Nombre -> las cuatro lineas que tiene que ensenar, tal y como estan en el artifact.
// Los dos minimos marcados con (*) NO son los de la maqueta a proposito: la maqueta los saca
// de CALMA y Jesus los cambio despues (frutos secos a 10 el 07-08, verduras a 100 el 15-08).
const ESPERADO = [
    ['Almendras', 'Genérico', 'Frutos secos sin grasas y/o azúcares añadidos · por 100 g',
        'Te cuenta la grasa', '53,1 G', 'Desde 10 g · necesitas 5,3 G'],           // (*) 5 g en la maqueta
    ['Nueces', 'Genérico', 'Frutos secos sin grasas y/o azúcares añadidos · por 100 g',
        'Te cuenta solo la grasa', '65,2 G', 'Desde 10 g · necesitas 6,5 G'],      // (*)
    ['Huevos enteros L', 'Genérico', 'Huevos frescos · por unidad, de 63 g',
        'Te cuenta todo', '8 P · 6 G', 'Desde 1 unidad · necesitas 8 P · 6 G'],
    ['Arroz blanco (SOS)', 'Ver web', 'Arroces · por 100 g',
        'Te cuenta solo el hidrato', '77 H', 'Desde 25 g · necesitas 19,3 H'],
    ['Hamburguesa angus (Alcampo)', 'Ver web', 'Vacuno o buey preparado · por unidad, de 150 g',
        'Te cuenta todo', '24 P · 19,5 G', 'Desde media hamburguesa · necesitas 12 P · 9,8 G'],
    ['Hamburguesa Angus de Nebraska (Confialiments)', 'Ver web', 'Vacuno o buey preparado · por 100 g',
        'Te cuenta todo', '12 P · 4 H · 15 G', 'Desde 50 g · necesitas 6 P · 2 H · 7,5 G'],
    ['Arroz basmati tarrina al minuto (Brillante)', 'Ver web', 'Arroces · por unidad, de 125 g',
        'Te cuenta solo el hidrato', '38,8 H', 'Desde media tarrina · necesitas 19,4 H'],
    ['Lechuga', 'Genérico', 'Verduras y hortalizas frescas · por 100 g',
        'No te cuenta nada', 'Come lo que quieras', 'Desde 100 g · siempre cabe'],  // (*) 50 g en la maqueta
    ['Kétchup zero (Heinz)', 'Ver web', 'Salsas o siropes zero o muy bajas en kcal · por 100 g',
        'No te cuenta nada', 'Come lo que quieras', 'Desde 10 g · siempre cabe'],
    ['Coca-Cola Zero (Coca-Cola)', 'Ver web', 'Bebidas energéticas y refrescos sin azúcar · por 100 ml',
        'No te cuenta nada', 'Bebe lo que quieras', 'Desde 100 ml · siempre cabe'],
];

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

(async () => {
    const ancho = Number(process.argv[2]) || 390;
    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: ancho, height: 900 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    const fallos = [];
    page.on('pageerror', (e) => fallos.push('ERROR EN LA PAGINA: ' + e.message));

    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: CUENTA, password: CLAVE } });
    const tok = (await r.json()).access_token;
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);
    await page.goto(`${APP}/dashboard/foods`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(8000);
    await quitarRecorrido(page);
    await page.waitForSelector('[data-testid="buscador-campo"]', { timeout: 25000 }).catch(() => {});

    console.log(`\n=== BLOQUE A · ${ancho} px · ${APP} ===\n`);

    // ── 156: el campo de buscar es lo primero que hay bajo el titulo ────────
    const orden = await page.evaluate(() => {
        const campo = document.querySelector('[data-testid="buscador-campo"]');
        if (!campo) return null;
        return { arribaDelCampo: Math.round(campo.getBoundingClientRect().top + window.scrollY) };
    });
    console.log(`156  el campo de buscar empieza a ${orden?.arribaDelCampo} px del principio   ${ok(orden && orden.arribaDelCampo < 220)}`);
    console.log(`156  los dos filtros en la fila      -> ${await page.locator('[data-testid="filtro-genericos"]').count()} + ${await page.locator('[data-testid="filtro-sinMacros"]').count()}   ${ok(await page.locator('[data-testid="filtro-sinMacros"]').count() === 1)}`);
    const nombreFiltro = await page.locator('[data-testid="filtro-sinMacros"]').innerText().catch(() => '?');
    console.log(`150  el filtro se llama             -> "${nombreFiltro}"   ${ok(nombreFiltro === 'No aportan macros')}`);

    // ── 157: la leyenda ya no lleva los tramos ─────────────────────────────
    const cabecera = await page.locator('[data-testid="buscador-campo"]').evaluate(el => el.closest('div.bg-card').innerText);
    console.log(`157  sin los tramos arriba          -> ${ok(!/desde 20 g la mitad/i.test(cabecera))}`);
    console.log(`159  «marcas» en negrita            -> ${ok(await page.locator('b', { hasText: /^marcas$/ }).count() > 0)}`);
    console.log(`159  guion y no dos puntos          -> ${ok(/sin marca - pollo/.test(cabecera))}`);

    // ── 158: el enlace de pedir, al final y no arriba ───────────────────────
    const pedir = page.locator('[data-testid="pedir-alimento"]');
    const arribaDelPedir = await pedir.evaluate(el => Math.round(el.getBoundingClientRect().top + window.scrollY)).catch(() => -1);
    console.log(`158  «Solicitar alimento» a ${arribaDelPedir} px, detrás de la lista   ${ok(arribaDelPedir > (orden?.arribaDelCampo || 0))}`);

    // ── 144: el vacio ───────────────────────────────────────────────────────
    await page.fill('[data-testid="buscador-campo"]', 'zzzzqqq');
    await page.waitForTimeout(1200);
    const vacio = (await page.locator('[data-testid="sin-resultados"]').innerText().catch(() => '(no sale)')).replace(/\n/g, ' | ');
    console.log(`144  al no encontrar nada           -> "${vacio}"   ${ok(vacio.startsWith('No lo tenemos.'))}`);

    // ── Los nueve alimentos, uno a uno ──────────────────────────────────────
    console.log('\n--- los alimentos de la maqueta, linea a linea ---');
    for (const [nombre, esquina, linea2, cuenta, numero, linea4] of ESPERADO) {
        await page.fill('[data-testid="buscador-campo"]', nombre.split(' (')[0]);
        await page.waitForTimeout(900);
        const fichas = page.locator('[data-testid="alimento"]');
        const n = await fichas.count();
        let ficha = null;
        for (let i = 0; i < n; i++) {
            const t = await fichas.nth(i).innerText();
            if (t.split('\n')[0].trim() === nombre) { ficha = fichas.nth(i); break; }
        }
        if (!ficha) { console.log(`  ${nombre}\n     NO SALE en la busqueda`); continue; }
        const lineas = (await ficha.innerText()).split('\n').map(s => s.trim()).filter(Boolean);
        // Sin distinguir mayusculas: la esquina se pinta en versales (`uppercase`), que es
        // como la escriben los puntos 145 y 152 -- «al lado GENÉRICO o Ver web ↗» --, y lo
        // que se compara son las palabras.
        const todo = lineas.join(' ~ ');
        const bien = todo.toLowerCase().includes(esquina.toLowerCase()) && todo.includes(linea2)
            && todo.includes(cuenta) && todo.includes(numero) && todo.includes(linea4);
        console.log(`  ${ok(bien)} ${nombre}`);
        if (!bien) {
            console.log('        se ve: ' + todo);
            console.log('        se espera: ' + [esquina, linea2, cuenta, numero, linea4].join(' ~ '));
        }
    }

    // ── 152 y 154: abrir la ficha, y que la web sea otro sitio ──────────────
    await page.fill('[data-testid="buscador-campo"]', 'Almendras');
    await page.waitForTimeout(1000);
    const primera = page.locator('[data-testid="alimento"]').first();
    const antes = page.url();
    await primera.locator('[data-testid^="abrir-"]').click();
    await page.waitForTimeout(700);
    const ficha = await primera.locator('[data-testid^="ficha-"]').innerText().catch(() => '(no abre)');
    console.log(`\n152/154  al tocar el nombre se abre la ficha y NO se va a la web   ${ok(page.url() === antes && ficha !== '(no abre)')}`);
    console.log('154  dentro pone -> ' + ficha.replace(/\n/g, ' | '));

    await page.fill('[data-testid="buscador-campo"]', '');
    await page.waitForTimeout(1200);
    await page.screenshot({ path: `_guia/_bloque_a_${ancho}.png`, fullPage: false });
    console.log(`\ncaptura -> _guia/_bloque_a_${ancho}.png`);
    if (fallos.length) console.log('\n' + fallos.join('\n'));
    await nav.close();
})();
