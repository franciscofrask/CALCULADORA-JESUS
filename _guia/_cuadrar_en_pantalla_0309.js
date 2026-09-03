/**
 * «LA COMIDA SE AUTOAJUSTA Y SE QUEDA CORTA» (Francisco, 3-09-2026), EN LA PANTALLA.
 *
 * Su caso: objetivo 75 P · 50 H · 20 G y la comida se queda en 69,6 P (faltan 5,4) y 44,4 H
 * (faltan 5,6), con el solomillo en 325 g y el arroz en 200 g. Subiendo A MANO el solomillo
 * a 350 y el arroz a 225 cuadra: sitio había, el automático se paró antes.
 *
 * Aquí NO se llama a ningún endpoint de cálculo. Se conduce la app como el cliente: se abre
 * el día, se monta la comida desde el buscador, se pulsa «Cuadrar» y se lee lo que pone la
 * pantalla. La API solo se usa para dejar el día en blanco antes de empezar.
 *
 * Uso:  node _guia/_cuadrar_en_pantalla_0309.js
 */
const fs = require('fs');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const FECHA = process.env.FECHA || '2026-12-20';

const CARPETA = '_guia/_cuadrar_0309';
if (!fs.existsSync(CARPETA)) fs.mkdirSync(CARPETA, { recursive: true });

// Los cinco de su comida: lo que se teclea en el buscador y el nombre EXACTO que hay que
// elegir de la lista (buscar «calabacín» saca antes la crema de calabacín, y «arroz tres
// delicias» saca antes el de Bonpreu, que no es el suyo).
const COMIDA = [
    { buscar: 'calabacín', elegir: 'calabacín' },
    { buscar: 'solomillo de pavo', elegir: 'solomillo de pavo' },
    { buscar: 'arroz tres delicias', elegir: 'arroz tres delicias ya cocinado' },
    { buscar: 'almendras', elegir: 'almendras' },
    { buscar: 'aceite de oliva virgen extra', elegir: 'aceite de oliva virgen extra una cucharadita' },
];

const limpio = (t) => (t || '').replace(/\s+/g, ' ').trim();

(async () => {
    // Entrar y dejar el día en blanco: esto es MONTAR EL ESCENARIO, no la prueba.
    const r = await fetch(`${API}/api/auth/login`, { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: CUENTA, password: CLAVE }) });
    const TOKEN = (await r.json()).access_token;
    if (!TOKEN) { console.log('no he podido entrar'); return; }
    await fetch(`${API}/api/diets/${FECHA}`, { method: 'DELETE',
        headers: { Authorization: `Bearer ${TOKEN}` } }).catch(() => {});

    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: 1280, height: 1000 }, deviceScaleFactor: 2 });
    const p = await ctx.newPage();
    p.on('console', (m) => { if (m.type() === 'error') console.log('   [consola]', m.text().slice(0, 160)); });

    await p.goto(APP, { waitUntil: 'domcontentloaded' });
    await p.evaluate((t) => {
        localStorage.clear(); localStorage.setItem('token', t);
        localStorage.setItem('primera-dieta-hecha', '1');
        localStorage.setItem('nutrition-intro-seen', '1');
    }, TOKEN);
    await p.goto(`${APP}/dashboard/nutrition?date=${FECHA}`, { waitUntil: 'networkidle' }).catch(() => {});
    await p.waitForTimeout(8000);
    for (let i = 0; i < 4; i++) {
        const s = p.locator('[data-testid="recorrido-saltar"]');
        if (!(await s.count())) break;
        await s.click({ force: true }).catch(() => {});
        await p.waitForTimeout(800);
    }

    // El día está vacío: se crea desde la pantalla, como el cliente.
    const crear = p.locator('[data-testid="dia-vacio-crear"]');
    if (await crear.count()) { await crear.click(); await p.waitForTimeout(3500); }

    // Abrir C1 y montar la comida con el buscador.
    const tab = p.locator('[data-testid="meal-tab-C1"], [data-testid="meal-select-C1"]').first();
    if (await tab.count()) { await tab.click().catch(() => {}); await p.waitForTimeout(1200); }
    await p.locator('[data-testid="build-meal-C1"]').first().click();
    await p.waitForTimeout(2500);

    const auto = p.locator('[data-testid="modal-mode-auto"]');
    if (await auto.count()) { await auto.click().catch(() => {}); await p.waitForTimeout(600); }

    for (const { buscar, elegir } of COMIDA) {
        const caja = p.locator('input[placeholder="Buscar alimento..."]').first();
        await caja.fill('');
        await caja.type(buscar, { delay: 25 });
        await p.waitForTimeout(2800);
        const filas = await p.locator('[data-testid^="food-item-"]').all();
        if (!filas.length) { console.log(`   no sale nada al buscar «${buscar}»`); continue; }
        let elegida = null, nombreElegido = '';
        for (const f of filas) {
            const n = limpio((await f.innerText()).split('\n')[0]).toLowerCase();
            if (n.startsWith(elegir)) { elegida = f; nombreElegido = n; break; }
        }
        if (!elegida) {
            elegida = filas[0];
            nombreElegido = limpio((await filas[0].innerText()).split('\n')[0]);
            console.log(`   OJO: no encuentro «${elegir}», cojo el primero`);
        }
        console.log(`   añado: ${nombreElegido}`);
        await elegida.click();
        await p.waitForTimeout(1800);
    }
    await p.screenshot({ path: `${CARPETA}/1_modal_montada.png`, fullPage: true });
    await p.locator('[data-testid="save-build-meal"]').click();
    await p.waitForTimeout(4500);

    // La tarjeta abierta. El mismo testid sale dos veces (el detalle y el acordeón), así
    // que todo se busca DENTRO del detalle o Playwright se queja con razón.
    const detalle = p.getByTestId('meal-detail');

    /** Lo que pone la tarjeta de C1: objetivo, las tres palabras y los gramos de cada línea. */
    const leerC1 = async () => {
        const obj = detalle.getByTestId('objetivo-C1').first();
        const objetivo = (await obj.count()) ? limpio(await obj.innerText()) : '(sin objetivo a la vista)';
        const palabras = {};
        for (const k of ['P', 'H', 'G']) {
            const w = detalle.getByTestId(`comida-macro-C1-${k}`).first();
            palabras[k] = (await w.count()) ? limpio(await w.innerText()) : '?';
        }
        const gramos = [];
        for (let i = 0; i < 8; i++) {
            const q = detalle.getByTestId(`qty-C1-${i}`).first();
            if (!(await q.count())) break;
            const fila = q.locator('xpath=ancestor::*[position()<=3]').first();
            const nombre = limpio((await fila.innerText().catch(() => ''))).split(' −')[0];
            gramos.push(`${limpio(await q.innerText())}  ${nombre.slice(0, 70)}`);
        }
        return { objetivo, palabras, gramos };
    };

    const contar = async (titulo, fichero) => {
        const d = await leerC1();
        console.log(`\n── ${titulo} ──`);
        console.log(`   objetivo: ${d.objetivo}`);
        for (const k of ['P', 'H', 'G']) console.log(`   ${k}: ${d.palabras[k]}`);
        d.gramos.forEach((g) => console.log(`      ${g}`));
        const card = detalle.getByTestId('meal-card-C1').first();
        if (await card.count()) await card.screenshot({ path: `${CARPETA}/${fichero}.png` });
        return d;
    };

    await contar('Recién montada (modo Automático)', '2_montada');

    // El botón de cuadrar, pulsado desde la pantalla.
    const cuadrar = detalle.getByTestId('cuadrar-C1').first();
    if (await cuadrar.count()) {
        await cuadrar.click();
        await p.waitForTimeout(6000);
        // Si sale la pregunta de «¿de dónde bajo?», se contesta lo neutro para seguir.
        const prop = p.locator('button:has-text("de todos"), button:has-text("proporcion")').first();
        if (await prop.count()) { await prop.click().catch(() => {}); await p.waitForTimeout(4000); }
        await contar('Después de pulsar «Cuadrar»', '3_cuadrada');
    } else {
        console.log('\n   (no hay botón «Cuadrar» a la vista: la comida ya se da por cuadrada)');
    }

    const avisos = (await p.locator('[data-sonner-toast]').allInnerTexts().catch(() => []))
        .map(limpio).filter(Boolean);
    console.log(`\n   avisos en pantalla: ${avisos.join(' | ') || '(ninguno)'}`);

    // Y ahora lo que hizo él: subir a mano lo que se quedó corto.
    const subir = async (idx, valor) => {
        const q = detalle.getByTestId(`qty-C1-${idx}`).first();
        if (!(await q.count())) return;
        await q.click();
        await p.waitForTimeout(500);
        const campo = detalle.locator('input[aria-label="Gramos"], input[aria-label="Unidades"]').first();
        await campo.fill(String(valor));
        await campo.press('Enter');
        await p.waitForTimeout(2500);
    };
    const antes = await leerC1();
    for (let i = 0; i < antes.gramos.length; i++) {
        const g = antes.gramos[i];
        if (/solomillo/i.test(g)) await subir(i, 350);
        if (/arroz/i.test(g)) await subir(i, 225);
    }
    await contar('Subiendo a mano el solomillo a 350 y el arroz a 225', '4_a_mano');

    await p.screenshot({ path: `${CARPETA}/5_pantalla_entera.png`, fullPage: true });
    await ctx.close();
    await nav.close();
    console.log(`\n   Capturas en ${CARPETA}/`);
})();
