/**
 * PARTE 6 · bloques B y C (puntos 191 a 197): las frases del modo y el color de las comidas.
 *
 *   191  «Ajusta las cantidades de los alimentos a tus macros»  (era «Yo te ajusto...»)
 *   192  la de Manual ya es la buena y NO se toca
 *   193  «Ajusta las cantidades sin pasarse de tus macros», sin punto final
 *   195  «AJUSTE DE CANTIDADES» y la frase visible en el móvil (el 124, ya hecho)
 *   196  «sin crear» en gris y SIN punto
 *   197  se apaga lo hecho en vez de pintar de naranja lo que falta
 *
 * Monta un día A MEDIAS -- una comida hecha y las demás sin crear --, que es el escenario de
 * la maqueta donde se ve si queda algún color. Lo deja como estaba.
 *
 * Uso:  node _guia/_parte6_bc_2708.js [ancho]
 */
const { chromium } = require('playwright');
const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || process.env.DESTINO || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';

const ok = (b) => (b ? 'BIEN' : 'MAL ');
// Los tres macros cubiertos, para que «Cuadrar» pueda dejar la comida cuadrada de verdad:
// con solo arroz no hay proteina ni grasa que ajustar y la comida nunca cuadra.
const POLLO = 498, ARROZ = 1657, ACEITE = 3;

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
    const r = await page.request.post(`${API}/api/auth/login`, { data: { email: CUENTA, password: CLAVE } });
    const tok = (await r.json()).access_token;
    const cab = { Authorization: `Bearer ${tok}` };

    const d = new Date();
    const FECHA = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    console.log(`\n=== PARTE 6 · bloques B y C · ${ancho} px ===\n`);

    const antes = await (await page.request.get(`${API}/api/diets/${FECHA}`, { headers: cab })).json();
    const habia = !!antes.exists;

    // Un día A MEDIAS: la C1 montada y el resto sin crear.
    await page.request.post(`${API}/api/diets`, {
        headers: cab,
        data: { fecha: FECHA, tipo_dia: 'entrenamiento', num_comidas: 4, momento_entreno: 0,
                opcion_peri: 'intra_post',
                comidas: { C1: { alimentos: [
                    { alimento_id: POLLO, cantidad_g: 150 },
                    { alimento_id: ARROZ, cantidad_g: 60 },
                    { alimento_id: ACEITE, cantidad_g: 10 },
                ] } } },
    });

    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, tok);
    await page.goto(`${APP}/dashboard/nutrition?date=${FECHA}`, { waitUntil: 'networkidle' }).catch(() => {});
    await page.waitForTimeout(10000);
    await quitarRecorrido(page);

    // ── 196 · «sin crear», en gris y sin punto ──────────────────────────────
    let mirado = false;
    for (const k of ['C2', 'C3', 'C4']) {
        const est = page.locator(`[data-testid="estado-comida-${k}"]`);
        if (!(await est.count())) continue;
        const texto = (await est.innerText()).trim();
        if (texto !== 'sin crear') continue;
        mirado = true;
        const color = await est.evaluate(el => getComputedStyle(el).color);
        const puntos = await est.locator('span.rounded-full').count();
        console.log(`196  ${k}: «${texto}»`);
        console.log(`     color -> ${color}`);
        console.log(`     ¿lleva punto? -> ${puntos === 0 ? 'no' : 'SÍ, ' + puntos}   ${ok(puntos === 0)}`);
        break;
    }
    if (!mirado) console.log('196  no encuentro ninguna comida «sin crear»');

    // Y «faltan N de X» va en BLANCO, que es la otra mitad del 196: no es lo mismo no
    // haber empezado (gris) que ir corto (blanco), y ninguno de los dos es naranja.
    for (const k of ['C1', 'C2', 'C3', 'C4']) {
        const est = page.locator(`[data-testid="estado-comida-${k}"]`).first();
        if (!(await est.count())) continue;
        const t = (await est.innerText()).trim();
        if (!t.startsWith('faltan')) continue;
        const color = await est.evaluate(el => getComputedStyle(el).color);
        const naranja = /255,\s*90,\s*46/.test(color) || /rgb\(2[35][0-9],\s*[0-9]{1,3},\s*[0-9]{1,3}\)/.test(color);
        console.log(`196  ${k}: «${t}»`);
        console.log(`     color -> ${color}   ${ok(!naranja)}   <- en blanco, no en naranja`);
        break;
    }

    // ── 197 · ni un naranja en toda la pantalla ─────────────────────────────
    const naranjas = await page.evaluate(() => {
        const fuera = [];
        document.querySelectorAll('[data-testid^="meal-card-"]').forEach((tarjeta) => {
            const s = getComputedStyle(tarjeta);
            const naranja = (c) => /rgba?\(\s*25[0-9]|rgba?\(\s*2[0-4][0-9]/.test(c) && /9[0-9],\s*(4[0-9]|3[0-9])/.test(c);
            if (naranja(s.backgroundColor) || naranja(s.borderColor) || /255,\s*90,\s*46/.test(s.boxShadow || ''))
                fuera.push(tarjeta.dataset.testid + ' -> ' + s.backgroundColor + ' / ' + s.boxShadow);
        });
        return fuera;
    });
    console.log(`\n197  tarjetas de comida en naranja -> ${naranjas.length === 0 ? 'ninguna' : naranjas.join(' | ')}   ${ok(naranjas.length === 0)}`);
    // Solo se puede exigir que se apague algo SI hay algo hecho: en este dia de prueba las
    // comidas o estan sin crear o se quedan cortas, y ninguna de las dos se apaga.
    const cuadradas = await page.locator('[data-testid^="estado-comida-"]', { hasText: /^cuadrada$/ }).count();
    const apagadas = await page.evaluate(() => [...document.querySelectorAll('[data-testid^="meal-card-"]')]
        .filter(e => parseFloat(getComputedStyle(e).opacity) < 1).length);
    console.log(`197  comidas cuadradas ${cuadradas} · tarjetas apagadas ${apagadas}   ${cuadradas ? ok(apagadas >= 1) : '(ninguna cuadrada que apagar)'}`);

    await page.screenshot({ path: `_guia/_parte6_medias_${ancho}.png`, fullPage: true });

    // ── 191, 192, 193 y 195 · desplegando una comida ────────────────────────
    // La cabecera es el PRIMER botón VISIBLE de la tarjeta: el primero a secas es el de
    // «Automático», que está dentro y con la tarjeta plegada no se ve.
    const cabecera = page.locator('[data-testid="meal-card-C1"] button:visible').first();
    if (await cabecera.count()) { await cabecera.click(); await page.waitForTimeout(2500); }
    // `:visible`: la pantalla monta la comida en DOS sitios -- el detalle de escritorio y
    // el acordeon del movil -- con el mismo testid, y solo uno de los dos se ve. Sin esto
    // se mira el que esta oculto y la comprobacion dice «no se ve» siendo mentira.
    const modo = page.locator('[data-testid="ajuste-explicacion-C1"]:visible').first();
    if (await modo.count()) {
        const auto = (await modo.innerText()).trim();
        console.log(`\n191  con Automático -> «${auto}»   ${ok(auto === 'Ajusta las cantidades de los alimentos a tus macros')}`);
        const rotulo = await page.locator('[data-testid="meal-card-C1"] p:visible', { hasText: /ajuste de cantidades/i }).first().innerText().catch(() => '?');
        console.log(`195  el rótulo dice -> «${rotulo.trim()}»   ${ok(/ajuste de cantidades/i.test(rotulo))}`);
        const visible = await modo.isVisible();
        console.log(`195  y la frase se ve en ${ancho} px -> ${visible ? 'sí' : 'NO'}   ${ok(visible)}`);
        await page.locator('[data-testid="mode-manual-C1"]:visible').first().click();
        await page.waitForTimeout(1200);
        const man = (await modo.innerText()).trim();
        console.log(`192  con Manual -> «${man}»   ${ok(man === 'Las pones tú y lo compensas en el día')}`);
        await page.locator('[data-testid="mode-auto-C1"]:visible').first().click();
        await page.waitForTimeout(1000);
    } else {
        console.log('\n(no se pudo desplegar la comida 1)');
    }

    const cuadrar = page.locator('[data-testid="cuadrar-C1"]:visible').first();
    if (await cuadrar.count()) {
        const frase = await cuadrar.evaluate(el => el.parentElement.querySelector('p')?.innerText || '');
        console.log(`193  debajo de Cuadrar -> «${frase.trim()}»   ${ok(frase.trim() === 'Ajusta las cantidades sin pasarse de tus macros')}`);
    }
    await page.screenshot({ path: `_guia/_parte6_modo_${ancho}.png` });

    // ── 197, la otra mitad: que la comida YA HECHA se apague ────────────────
    // Para tener una cuadrada se usa el propio botón de Cuadrar, que es justo para eso. Y se
    // pliega la tarjeta antes de mirar: la abierta no se apaga a propósito (`!isExpanded`),
    // porque estando dentro de ella apagarla sería apagar lo que estás tocando.
    if (await cuadrar.count()) {
        await cuadrar.click();
        await page.waitForTimeout(6000);
        await cabecera.click().catch(() => {});
        await page.waitForTimeout(2000);
        const estado = await page.locator('[data-testid="estado-comida-C1"]:visible').first().innerText().catch(() => '?');
        const opacidad = await page.locator('[data-testid="meal-card-C1"]:visible').first()
            .evaluate(el => getComputedStyle(el).opacity).catch(() => '?');
        console.log(`\n197  la C1 queda «${estado.trim()}» y su tarjeta a opacidad ${opacidad}   ${ok(parseFloat(opacidad) < 1)}`);
        await page.screenshot({ path: `_guia/_parte6_apagada_${ancho}.png`, fullPage: true });
    }

    if (habia) {
        await page.request.post(`${API}/api/diets`, {
            headers: cab,
            data: { fecha: FECHA, tipo_dia: antes.tipo_dia, num_comidas: antes.num_comidas,
                    momento_entreno: antes.momento_entreno, opcion_peri: antes.opcion_peri, comidas: antes.comidas },
        });
        console.log('\ndía repuesto');
    } else {
        const b = await page.request.delete(`${API}/api/diets/${FECHA}`, { headers: cab });
        console.log('\ndía de prueba borrado ->', b.status());
    }
    console.log(`capturas -> _guia/_parte6_medias_${ancho}.png y _guia/_parte6_modo_${ancho}.png`);
    await nav.close();
})();
