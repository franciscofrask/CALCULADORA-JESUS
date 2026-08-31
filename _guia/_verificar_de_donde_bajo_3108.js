/**
 * «QUE PREGUNTE DE DÓNDE RECALCULA» (Jesús, nota de voz del 31-08-2026), EN LA APP.
 *
 * Monta una comida con la proteína repartida entre dos alimentos (aislado y queso batido),
 * le da a «Cuadrar» y comprueba que:
 *   1. sale la pregunta, con las tres opciones y sus cantidades,
 *   2. elegir un alimento baja ESE y deja el otro con los gramos que tenía,
 *   3. una comida con una sola fuente del macro NO pregunta nada.
 *
 * Trabaja en una fecha suelta de la cuenta de pruebas y la borra al terminar.
 *
 * Uso:  node _guia/_verificar_de_donde_bajo_3108.js
 */
const fs = require('fs');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';

const FECHA = '2026-12-18';
const CARPETA = '_guia/_de_donde_bajo';
if (!fs.existsSync(CARPETA)) fs.mkdirSync(CARPETA, { recursive: true });

const POLVO = { id: 2822, nombre: 'Aislado de proteína - Whey Prime Isolate (Prozis)' };
const QUESO = { id: 1678, nombre: 'Queso fresco batido 0 %' };
const POLLO = { id: 498, nombre: 'Pechuga de pollo' };
const ARROZ = { id: 1657, nombre: 'Arroz blanco' };

let TOKEN = '';
const pide = async (ruta, opciones = {}) => {
    const r = await fetch(`${API}/api${ruta}`, {
        ...opciones,
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${TOKEN}`,
                   ...(opciones.headers || {}) },
    });
    const t = await r.text();
    try { return JSON.parse(t); } catch { return { _status: r.status, _texto: t }; }
};
const al = (f, g) => ({ id: f.id, alimento_id: f.id, nombre: f.nombre, cantidad_g: g });

(async () => {
    TOKEN = (await pide('/auth/login', { method: 'POST',
        body: JSON.stringify({ email: CUENTA, password: CLAVE }) })).access_token;
    if (!TOKEN) { console.log('no he podido entrar'); return; }

    const montar = (comidas) => pide('/diets', { method: 'POST', body: JSON.stringify({
        fecha: FECHA, tipo_dia: 'entrenamiento', num_comidas: 4,
        momento_entreno: 1, opcion_peri: 'intra_post', comidas,
    }) });

    await pide(`/diets/${FECHA}`, { method: 'DELETE' }).catch(() => {});
    // C1: la proteína sale de DOS sitios -> tiene que preguntar.
    // C3: la proteína sale de UNO -> no tiene que preguntar nada.
    await montar({
        C1: { alimentos: [al(POLVO, 60), al(QUESO, 300)] },
        C3: { alimentos: [al(POLLO, 300), al(ARROZ, 100)] },
    });

    const nav = await chromium.launch();
    const ctx = await nav.newContext({ viewport: { width: 1400, height: 1100 }, deviceScaleFactor: 2 });
    const p = await ctx.newPage();
    const errores = [];
    p.on('console', (m) => { if (m.type() === 'error') errores.push(m.text().slice(0, 220)); });

    const abrir = async () => {
        await p.goto(APP, { waitUntil: 'domcontentloaded' });
        await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, TOKEN);
        await p.goto(`${APP}/dashboard/nutrition?date=${FECHA}`, { waitUntil: 'networkidle' }).catch(() => {});
        await p.waitForTimeout(9000);
        for (let i = 0; i < 4; i++) {
            const s = p.locator('[data-testid="recorrido-saltar"]');
            if (!(await s.count())) break;
            await s.click({ force: true }).catch(() => {});
            await p.waitForTimeout(900);
        }
        await p.waitForTimeout(1500);
    };

    const abrirComida = async (k) => {
        const tarjeta = p.locator(`[data-testid="meal-card-${k}"]`);
        if (!(await tarjeta.count())) return false;
        if (!(await p.locator(`[data-testid="cuadrar-${k}"]`).count())) {
            await p.locator(`[data-testid="meal-select-${k}"], [data-testid="meal-tab-${k}"]`).first()
                .click().catch(() => {});
            await p.waitForTimeout(800);
            await tarjeta.click().catch(() => {});
            await p.waitForTimeout(1200);
        }
        return (await p.locator(`[data-testid="cuadrar-${k}"]`).count()) > 0;
    };

    /** Las cantidades tal y como se leen en la tarjeta, del propio contador de gramos, en el
     *  orden en que están puestas. Aquí no se intenta sacar el nombre del DOM: hay más de un
     *  sitio con `title` en cada fila y salía el macro en vez del alimento. Los nombres van
     *  en el volcado del servidor de más abajo, que es donde no hay ambigüedad. */
    const cantidades = async (k) => {
        const salida = [];
        for (let i = 0; i < 8; i++) {
            const q = p.locator(`[data-testid="qty-${k}-${i}"]`).first();
            if (!(await q.count())) break;
            salida.push(`[${i + 1}] ${(await q.innerText()).replace(/\s+/g, ' ').trim()}`);
        }
        return salida.join(' | ') || '(no leo cantidades)';
    };

    await abrir();
    console.log('\n══ C1 · la proteína viene del polvo Y del queso ══');
    console.log('   antes:', await cantidades('C1'));
    if (!(await abrirComida('C1'))) { console.log('   no encuentro el botón Cuadrar'); }
    else {
        // Hay dos: la vista maestro-detalle y el acordeón pintan la misma tarjeta.
        await p.locator('[data-testid="cuadrar-C1"]').first().click();
        await p.waitForTimeout(3000);
        const dlg = p.locator(`[data-testid="confirm-dialog"]`).first();
        if (!(await dlg.count())) {
            console.log('   NO SALE LA PREGUNTA  <-- MAL');
            await p.screenshot({ path: `${CARPETA}/x_sin_pregunta.png`, fullPage: true });
        } else {
            console.log('   la pregunta:');
            (await dlg.innerText()).split('\n').filter(Boolean).forEach(l => console.log('     ', l.trim()));
            await dlg.screenshot({ path: `${CARPETA}/1_la_pregunta.png` });
            // Se elige el polvo: tiene que bajar ESE y dejar el queso en sus 300 g.
            await p.locator(`[data-testid="elegir-${POLVO.id}"]`).first().click();
            await p.waitForTimeout(4000);
            console.log('\n   tras elegir «del polvo»:', await cantidades('C1'));
            await p.screenshot({ path: `${CARPETA}/2_tras_elegir.png`, fullPage: true });
        }
    }

    console.log('\n══ C3 · la proteína viene solo del pollo ══');
    if (!(await abrirComida('C3'))) { console.log('   no encuentro el botón Cuadrar'); }
    else {
        await p.locator('[data-testid="cuadrar-C3"]').first().click();
        await p.waitForTimeout(3000);
        const sale = await p.locator('[data-testid="confirm-dialog"]').count();
        console.log('   ¿pregunta?:', sale ? 'SÍ  <-- MAL, aquí no hay nada que elegir' : 'no  (bien)');
        console.log('   queda    :', await cantidades('C3'));
        await p.screenshot({ path: `${CARPETA}/3_sin_pregunta.png`, fullPage: true });
    }

    // ── Aplicar una favorita: ahí no se pregunta, se marca ───────────────────
    console.log('\n══ Una favorita que recuadra varias comidas ══');
    const fav = await pide('/diets/favorites', { method: 'POST', body: JSON.stringify({
        name: 'PRUEBA 3108 de donde bajo', tipo_dia: 'entrenamiento', num_comidas: 4,
        momento_entreno: 1, opcion_peri: 'intra_post',
        comidas: { C1: { alimentos: [al(POLVO, 60), al(QUESO, 300)] } },
    }) });
    const favId = fav.id || fav.favorite?.id;
    await abrir();
    await p.locator('[data-testid="menu-pantalla"]').first().click().catch(() => {});
    await p.waitForTimeout(700);
    await p.locator('[data-testid="menu-pantalla-favoritas"]').click().catch(() => {});
    await p.waitForTimeout(2500);
    await p.locator(`[data-testid="fav-apply-${favId}"]`).first().click().catch(() => {});
    await p.waitForTimeout(5000);
    const preguntoAlAplicar = await p.locator('[data-testid="confirm-dialog"]').count();
    console.log('   ¿interroga al aplicar?:', preguntoAlAplicar ? 'SÍ  <-- MAL' : 'no  (bien)');
    const avisos = await p.locator('[data-sonner-toast], [role="status"]').allInnerTexts().catch(() => []);
    avisos.map(t => t.replace(/\s+/g, ' ').trim()).filter(Boolean).forEach(t => console.log('   aviso:', t));
    await abrirComida('C1');
    const marca = p.locator('[data-testid="eleccion-pendiente-C1"]').first();
    console.log('   ¿marca en la tarjeta?:', (await marca.count()) ? 'sí  (bien)' : 'NO  <-- MAL');
    if (await marca.count()) {
        await marca.screenshot({ path: `${CARPETA}/4_la_marca.png` }).catch(() => {});
        await marca.click();
        await p.waitForTimeout(3000);
        console.log('   al tocarla, ¿sale la pregunta?:',
            (await p.locator('[data-testid="confirm-dialog"]').count()) ? 'sí  (bien)' : 'NO  <-- MAL');
        await p.screenshot({ path: `${CARPETA}/5_marca_y_pregunta.png`, fullPage: true });
        await p.locator('[data-testid="confirm-cancel"]').first().click().catch(() => {});
    }
    if (favId) await pide(`/diets/favorites/${favId}`, { method: 'DELETE' });

    await p.waitForTimeout(4000);   // que llegue el autoguardado
    const guardado = await pide(`/diets/${FECHA}`);
    console.log('\n   guardado en el servidor:');
    Object.entries(guardado.comidas || {}).forEach(([k, c]) => {
        const lista = (c.alimentos || []).map(a => `${a.nombre.split(' (')[0]} ${a.cantidad_g}g`).join(', ');
        if (lista) console.log(`      ${k.padEnd(6)} ${lista}${c.bajar_de ? '   [eligió: ' + JSON.stringify(c.bajar_de.modo) + ']' : ''}`);
    });

    if (errores.length) console.log('\n   errores de consola:', errores.slice(0, 5));

    await pide(`/diets/${FECHA}`, { method: 'DELETE' });
    console.log(`\n(día de pruebas borrado: ${(await pide(`/diets/${FECHA}`)).exists ? 'NO' : 'sí'})`);
    console.log(`capturas en ${CARPETA}/`);
    await nav.close();
})();
