/**
 * UNA SOLA REGLA DE REDONDEO (Francisco, 3-09-2026): «que muestre tambien en el global asi no
 * hay desfase, tal cual lo hace Calma».
 *
 * Lo que se comprueba es que la MISMA comida diga el MISMO numero en los tres sitios donde se
 * lee, que era el fallo:
 *
 *     Inicio, fila de la comida        «16G»            (iba en entero)
 *     Nutricion, comida abierta        «15,7»           (iba a la decima)
 *     Nutricion, comida plegada        «valido +1»      (redondeaba el desvio a entero)
 *
 * Se sacan los tres del DOM, se comparan macro a macro y se deja captura de cada pantalla.
 * No toca datos: lee el dia que haya en la cuenta de pruebas.
 *
 * Uso:  node _guia/_verificar_una_regla_de_redondeo_0309.js
 */
const fs = require('fs');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const CARPETA = '_guia/_una_regla_redondeo';
if (!fs.existsSync(CARPETA)) fs.mkdirSync(CARPETA, { recursive: true });

// EL HOY DEL NAVEGADOR, no el de Madrid: Inicio ensena el dia que vive el cliente y lo saca
// del reloj de su aparato. Con el portatil una hora por detras, Madrid ya esta en el dia
// siguiente y el script montaba la comida en un dia que la pantalla no ensena.
const HOY = new Date().toLocaleDateString('en-CA');

let TOKEN = '';
const api = async (ruta, o = {}) => {
    const r = await fetch(`${API}/api${ruta}`, { ...o,
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${TOKEN}`, ...(o.headers || {}) } });
    const t = await r.text();
    try { return JSON.parse(t); } catch { return { _texto: t }; }
};

// «15,7» -> 15.7 ; «16» -> 16. Devuelve null si ahi no hay numero.
const aNumero = (t) => {
    if (t == null) return null;
    const m = String(t).replace(/−/g, '-').match(/-?\d+(?:,\d+)?/);
    return m ? Number(m[0].replace(',', '.')) : null;
};

(async () => {
    TOKEN = (await api('/auth/login', { method: 'POST',
        body: JSON.stringify({ email: CUENTA, password: CLAVE }) })).access_token;
    if (!TOKEN) { console.log('no he podido entrar'); return; }

    const dia = await api(`/diets/${HOY}`);
    const conAlimentos = Object.entries(dia?.comidas || {})
        .filter(([, c]) => (c?.alimentos || []).length > 0).map(([k]) => k);
    console.log(`dia ${HOY}: ${conAlimentos.length ? conAlimentos.join(', ') : 'sin comidas montadas'}`);
    if (!conAlimentos.length) { console.log('sin nada que comparar; monta una comida y repite'); return; }

    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: 430, height: 1600 }, deviceScaleFactor: 2 });
    const p = await ctx.newPage();
    const errores = [];
    p.on('console', (m) => { if (m.type() === 'error') errores.push(m.text().slice(0, 200)); });

    await p.goto(APP, { waitUntil: 'domcontentloaded' });
    await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, TOKEN);

    // ─── 1. INICIO ────────────────────────────────────────────────────────────
    await p.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
    await p.waitForTimeout(12000);
    for (let i = 0; i < 4; i++) {
        const s = p.locator('[data-testid="recorrido-saltar"]');
        if (!(await s.count())) break;
        await s.click({ force: true }).catch(() => {});
        await p.waitForTimeout(900);
    }
    await p.locator('[data-testid="vista-dieta"]').click({ force: true }).catch(() => {});
    await p.waitForTimeout(1500);

    const global = {};
    for (const k of ['P', 'H', 'G']) {
        global[k] = {
            numero: await p.locator(`[data-testid="dieta-hoy-dieta-${k}"] .numero-grande`).first().innerText().catch(() => null),
            de: await p.locator(`[data-testid="de-dieta-${k}"]`).first().innerText().catch(() => null),
            palabra: await p.locator(`[data-testid="palabra-dieta-${k}"]`).first().innerText().catch(() => null),
        };
    }
    await p.locator('[data-testid="macros-de-hoy"]').screenshot({ path: `${CARPETA}/1_inicio_global.png` }).catch(() => {});

    const filasInicio = {};
    for (const k of conAlimentos) {
        const f = p.locator(`[data-testid="comida-hoy-${k}"]`);
        if (!(await f.count())) continue;
        filasInicio[k] = await f.first().innerText();
    }
    await p.locator('[data-testid="marca-comidas"]').screenshot({ path: `${CARPETA}/2_inicio_comidas.png` }).catch(() => {});

    // ─── 2. NUTRICIÓN ─────────────────────────────────────────────────────────
    await p.goto(`${APP}/dashboard/nutrition`, { waitUntil: 'networkidle' }).catch(() => {});
    await p.waitForTimeout(14000);
    await p.screenshot({ path: `${CARPETA}/3_nutricion_plegado.png`, fullPage: true }).catch(() => {});

    const marcas = await p.evaluate(() => Array.from(document.querySelectorAll('[data-testid]'))
        .map((n) => n.getAttribute('data-testid'))
        .filter((t) => /meal|comida|^dia-/.test(t)));
    console.log(`
  marcas en Nutrición: ${marcas.join(', ')}`);

    const cabecera = {};
    for (const m of ['P', 'H', 'G']) {
        const c = p.locator(`[data-testid="dia-${m}"]`);
        if (!(await c.count())) continue;
        cabecera[m] = {
            numero: await c.first().locator('.numero-grande').innerText().catch(() => null),
            palabra: await p.locator(`[data-testid="dia-palabra-${m}"]`).first().innerText().catch(() => null),
        };
    }
    await p.locator('[data-testid="dia-resumen"]').first()
        .screenshot({ path: `${CARPETA}/3b_nutricion_cabecera.png` }).catch(() => {});

    // La palabra de la tarjeta PLEGADA, que era la tercera cifra en discordia: decia
    // «valido +1» donde la abierta decia «cuadrado», porque redondeaba el desvio a entero.
    const plegado = {};
    for (const k of conAlimentos) {
        plegado[k] = await p.locator(`[data-testid="estado-comida-${k}"]`).last()
            .innerText().catch(() => null);
    }
    const acordeon = p.locator('[data-testid="meals-accordion"]');
    if (await acordeon.count()) {
        await acordeon.first().screenshot({ path: `${CARPETA}/3c_comidas_plegadas.png` }).catch(() => {});
    }

    const abierto = {};
    for (const k of conAlimentos) {
        // Se abre la comida pulsando su cabecera y se leen los tres numeros de dentro.
        const cab = p.locator(`text=/^Comida ${k.slice(1)}$/`).first();
        await cab.click({ force: true }).catch(() => {});
        await p.locator(`[data-testid="meal-progress-${k}"]`).first()
            .waitFor({ state: 'visible', timeout: 15000 }).catch(() => {});
        await p.waitForTimeout(2500);
        const macros = {};
        for (const m of ['P', 'H', 'G']) {
            const caja = p.locator(`[data-testid="comida-macro-${k}-${m}"]`);
            if (!(await caja.count())) continue;
            macros[m] = {
                numero: await caja.first().locator('.numero-grande').innerText().catch(() => null),
                palabra: await p.locator(`[data-testid="comida-palabra-${k}-${m}"]`).first().innerText().catch(() => null),
            };
        }
        abierto[k] = macros;
        if (Object.keys(macros).length) {
            await p.locator(`[data-testid="meal-progress-${k}"]`).first()
                .screenshot({ path: `${CARPETA}/4_comida_${k}_abierta.png` }).catch(() => {});
        }
        await cab.click({ force: true }).catch(() => {});
        await p.waitForTimeout(900);
    }

    // ─── 3. EL COTEJO ─────────────────────────────────────────────────────────
    const fallos = [];
    console.log('\n── EL GLOBAL DEL DÍA (pestaña Dieta) ──');
    for (const k of ['P', 'H', 'G']) {
        console.log(`  ${k}: ${global[k].numero}   ${global[k].de}   ${global[k].palabra}`);
        const n = aNumero(global[k].numero);
        const meta = aNumero(global[k].de);
        const dicho = aNumero(global[k].palabra);
        if (n == null || meta == null) continue;
        const real = Math.round((n - meta) * 10) / 10;
        if (dicho != null && Math.abs(Math.abs(real) - Math.abs(dicho)) > 0.051) {
            fallos.push(`global ${k}: se lee ${n} de ${meta} (${real}) y la palabra dice ${dicho}`);
        }
    }

    console.log('\n── LA CABECERA DE NUTRICIÓN ──');
    for (const m of ['P', 'H', 'G']) {
        if (!cabecera[m]) continue;
        console.log(`  ${m}: ${cabecera[m].numero}   ${cabecera[m].palabra}`);
        if (aNumero(cabecera[m].numero) !== aNumero(global[m].numero)) {
            fallos.push(`cabecera ${m}: Nutrición dice ${cabecera[m].numero} e Inicio ${global[m].numero}`);
        }
    }
    console.log('\n── CADA COMIDA, EN LOS TRES SITIOS ──');
    for (const k of conAlimentos) {
        console.log(`\n  ${k}`);
        console.log(`    Inicio:              ${(filasInicio[k] || '').replace(/\n/g, ' | ')}`);
        for (const m of ['P', 'H', 'G']) {
            const a = abierto[k]?.[m];
            if (!a) continue;
            console.log(`    Nutrición abierta ${m}: ${a.numero}   ${a.palabra}`);
            // El numero de la comida abierta tiene que aparecer TAL CUAL en la fila de Inicio.
            const enInicio = (filasInicio[k] || '').includes(`${a.numero}${m}`);
            if (!enInicio) {
                fallos.push(`${k}/${m}: la comida abierta dice «${a.numero}» y la fila de Inicio no lo trae`);
            }
        }
        // La plegada nombra el desvio MAYOR de la comida, y tiene que ser el mismo numero
        // que el de la abierta: si una dice «+1» y la otra «(+1,2)», sigue habiendo desfase.
        const pal = plegado[k] || '';
        const desvios = ['P', 'H', 'G'].map((m) => aNumero(abierto[k]?.[m]?.palabra)).filter((x) => x != null);
        const mayor = desvios.sort((x, y) => Math.abs(y) - Math.abs(x))[0];
        console.log(`    Nutrición plegada:   ${pal.replace(/\n/g, ' · ')}`);
        if (/válido/i.test(pal) && mayor != null && Math.abs(Math.abs(aNumero(pal)) - Math.abs(mayor)) > 0.051) {
            fallos.push(`${k}: la plegada dice «${pal}» y el desvío mayor de la abierta es ${mayor}`);
        }
    }

    console.log('\n── RESULTADO ──');
    if (errores.length) console.log(`  errores de consola: ${errores.slice(0, 4).join(' · ')}`);
    if (!fallos.length) console.log('  los tres sitios dicen el mismo número');
    else fallos.forEach((f) => console.log(`  DESFASE  ${f}`));
    console.log(`  capturas en ${CARPETA}`);

    await nav.close();
})();
