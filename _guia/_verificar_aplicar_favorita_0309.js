/**
 * «AL PULSAR "APLICAR" EN UNA FAVORITA» (doc de Jesús, 3-09-2026), COMPROBADO EN LA APP.
 *
 * Los cuatro casos y los cinco detalles, uno a uno, en escritorio (1280) y en móvil (390).
 * Monta el escenario en fechas sueltas de la cuenta de pruebas y lo borra al terminar.
 *
 * Uso:  node _guia/_verificar_aplicar_favorita_0309.js
 */
const fs = require('fs');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';

const CARPETA = '_guia/_favorita_0309';
if (!fs.existsSync(CARPETA)) fs.mkdirSync(CARPETA, { recursive: true });

// Un día por escenario, todos en un hueco muerto de diciembre.
const D = {
    vacioEntreno: '2026-12-01',
    vacioDescanso: '2026-12-02',
    vacioEntreno2: '2026-12-03',
    tresEntreno: '2026-12-04',
    unaEntreno: '2026-12-05',
    soloIntra: '2026-12-06',
};

const POLLO = { id: 498, nombre: 'Pechuga de pollo' };
const MERLUZA = { id: 1656, nombre: 'Merluza' };

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

const comidaCon = (f, g) => ({ alimentos: [{ id: f.id, alimento_id: f.id, nombre: f.nombre, cantidad_g: g }] });
const limpio = (t) => (t || '').replace(/\s+/g, ' ').trim();

const fallos = [];
const comprobar = (titulo, bien, visto) => {
    console.log(`   ${bien ? 'OK  ' : 'MAL '} ${titulo}`);
    if (!bien) { console.log(`        visto: ${visto}`); fallos.push(titulo); }
};

(async () => {
    TOKEN = (await pide('/auth/login', { method: 'POST',
        body: JSON.stringify({ email: CUENTA, password: CLAVE }) })).access_token;
    if (!TOKEN) { console.log('no he podido entrar'); return; }

    // ── Escenario ────────────────────────────────────────────────────────────
    for (const f of Object.values(D)) await pide(`/diets/${f}`, { method: 'DELETE' }).catch(() => {});

    const ENTRENO = { tipo_dia: 'entrenamiento', num_comidas: 3, momento_entreno: 1, opcion_peri: 'intra_post' };
    const DESCANSO = { tipo_dia: 'descanso', num_comidas: 3, momento_entreno: 1, opcion_peri: 'ninguno' };

    // Las dos favoritas de prueba (se borran al final).
    const previas = await pide('/diets/favorites');
    for (const f of (Array.isArray(previas) ? previas : previas.favorites || [])) {
        if ((f.name || '').startsWith('PRUEBA 0309')) await pide(`/diets/favorites/${f.id}`, { method: 'DELETE' });
    }
    const tresComidas = { C1: comidaCon(MERLUZA, 200), C2: comidaCon(MERLUZA, 200), C3: comidaCon(MERLUZA, 200) };
    const favE = await pide('/diets/favorites', { method: 'POST', body: JSON.stringify({
        name: 'PRUEBA 0309 de entreno', ...ENTRENO,
        comidas: { ...tresComidas, Intra: comidaCon(POLLO, 100), Post: comidaCon(POLLO, 100) },
    }) });
    const favD = await pide('/diets/favorites', { method: 'POST', body: JSON.stringify({
        name: 'PRUEBA 0309 de descanso', ...DESCANSO, comidas: tresComidas,
    }) });
    const idE = favE.id || favE.favorite?.id;
    const idD = favD.id || favD.favorite?.id;
    if (!idE || !idD) { console.log('no he podido crear las favoritas', favE, favD); return; }

    const dia = (fecha, cfg, comidas) => pide('/diets', { method: 'POST',
        body: JSON.stringify({ fecha, ...cfg, comidas }) });
    // LOS DÍAS SE REMONTAN ANTES DE CADA ANCHO. En la primera pasada el caso 1 aplica la
    // favorita de verdad y el autoguardado deja el día con comidas: sin esto, la segunda
    // pasada abre un día que ya no está vacío y el caso 1 sale «mal» por culpa del guion.
    const montarDias = async () => {
        for (const f of Object.values(D)) await pide(`/diets/${f}`, { method: 'DELETE' }).catch(() => {});
        await dia(D.vacioEntreno, ENTRENO, {});
        await dia(D.vacioDescanso, DESCANSO, {});
        await dia(D.vacioEntreno2, ENTRENO, {});
        await dia(D.tresEntreno, ENTRENO, tresComidas);
        await dia(D.unaEntreno, ENTRENO, { C1: comidaCon(POLLO, 150) });
        await dia(D.soloIntra, ENTRENO, { Intra: comidaCon(POLLO, 120) });
    };

    // ── Navegador ────────────────────────────────────────────────────────────
    const nav = await chromium.launch();

    const pantalla = async (ancho) => {
        const ctx = await nav.newContext(ancho === 390
            ? { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 }
            : { viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2 });
        const p = await ctx.newPage();
        return { ctx, p };
    };

    const abrir = async (p, fecha) => {
        await p.goto(APP, { waitUntil: 'domcontentloaded' });
        await p.evaluate((t) => {
            localStorage.clear();
            localStorage.setItem('token', t);
            localStorage.setItem('primera-dieta-hecha', '1');
            localStorage.setItem('nutrition-intro-seen', '1');
        }, TOKEN);
        await p.goto(`${APP}/dashboard/nutrition?date=${fecha}`, { waitUntil: 'networkidle' }).catch(() => {});
        await p.waitForTimeout(7000);
        for (let i = 0; i < 4; i++) {
            const s = p.locator('[data-testid="recorrido-saltar"]');
            if (!(await s.count())) break;
            await s.click({ force: true }).catch(() => {});
            await p.waitForTimeout(800);
        }
        await p.waitForTimeout(1200);
    };

    /** Abre la lista de favoritas, venga de la pantalla de día vacío o del «···». */
    const abrirFavoritas = async (p) => {
        const vacio = p.locator('[data-testid="dia-vacio-favoritas"]');
        if (await vacio.count()) { await vacio.click(); }
        else {
            await p.locator('[data-testid="menu-pantalla"]').first().click();
            await p.waitForTimeout(600);
            await p.locator('[data-testid="menu-pantalla-favoritas"]').click();
        }
        await p.waitForTimeout(2500);
    };

    const textoPanel = async (p, id) => {
        const panel = p.locator(`[data-testid="fav-adapt-panel-${id}"]`);
        if (!(await panel.count())) return null;
        return limpio(await panel.innerText());
    };

    const foto = async (p, nombre) => {
        const dlg = p.locator('[role="dialog"]').first();
        if (await dlg.count()) await dlg.screenshot({ path: `${CARPETA}/${nombre}.png` }).catch(() => {});
        else await p.screenshot({ path: `${CARPETA}/${nombre}.png` });
    };

    for (const ancho of [1280, 390]) {
        await montarDias();
        const { ctx, p } = await pantalla(ancho);
        console.log(`\n\n════════ ${ancho} px ════════`);

        // ── Caso 1 · día vacío + favorita del mismo tipo: sin aviso ──────────
        console.log('\n1 · Día vacío y favorita del mismo tipo');
        await abrir(p, D.vacioEntreno);
        await abrirFavoritas(p);
        await p.locator(`[data-testid="fav-apply-${idE}"]`).click();
        await p.waitForTimeout(1500);
        comprobar('no sale ningún aviso',
            (await textoPanel(p, idE)) === null, await textoPanel(p, idE));
        comprobar('se aplica: la lista de favoritas se cierra sola',
            (await p.locator('[role="dialog"]').count()) === 0, 'sigue abierta');
        await p.waitForTimeout(4000);
        await foto(p, `${ancho}_caso1_aplicada`);

        // ── Caso 2 · día vacío + otro tipo, hacia DESCANSO ───────────────────
        console.log('\n2a · Día vacío de descanso y favorita de entreno');
        await abrir(p, D.vacioDescanso);
        await abrirFavoritas(p);
        await p.locator(`[data-testid="fav-apply-${idE}"]`).click();
        await p.waitForTimeout(900);
        await foto(p, `${ancho}_caso2_a_descanso`);
        let t = await textoPanel(p, idE);
        comprobar('la frase del tipo de día',
            t?.includes('Esta favorita es de día de entreno; hoy tienes descanso.'), t);
        comprobar('no dice nada de comidas perdidas (el día está vacío)',
            !t?.includes('ya tiene'), t);
        comprobar('botón «Aplicar y adaptar a mi día de hoy»',
            limpio(await p.locator(`[data-testid="fav-adapt-${idE}"]`).innerText()) === 'Aplicar y adaptar a mi día de hoy',
            limpio(await p.locator(`[data-testid="fav-adapt-${idE}"]`).innerText()));
        comprobar('la línea gris: «el intra y el post se quitan»',
            t?.includes('el intra y el post se quitan'), t);
        comprobar('botón «Aplicar como se guardó (pasa el día a entreno)»',
            t?.includes('Aplicar como se guardó (pasa el día a entreno)'), t);
        comprobar('Cancelar', t?.includes('Cancelar'), t);

        // Detalle 5: Cancelar cierra el aviso y NO cierra las favoritas.
        await p.locator(`[data-testid="fav-adapt-panel-${idE}"] button:has-text("Cancelar")`).click();
        await p.waitForTimeout(700);
        comprobar('Cancelar cierra el aviso', (await textoPanel(p, idE)) === null, 'sigue el aviso');
        comprobar('Cancelar deja la lista de favoritas abierta',
            (await p.locator('[role="dialog"]').count()) > 0, 'se cerró la lista');
        // Detalle 5: volver a pulsar Aplicar en esa favorita también cierra el aviso.
        await p.locator(`[data-testid="fav-apply-${idE}"]`).click();
        await p.waitForTimeout(600);
        comprobar('vuelve a salir al pulsar Aplicar', (await textoPanel(p, idE)) !== null, 'no salió');
        await p.locator(`[data-testid="fav-apply-${idE}"]`).click();
        await p.waitForTimeout(600);
        comprobar('y volviendo a pulsar Aplicar se cierra',
            (await textoPanel(p, idE)) === null, 'sigue abierto');

        // ── Caso 2 · día vacío + otro tipo, hacia ENTRENO ────────────────────
        console.log('\n2b · Día vacío de entreno y favorita de descanso');
        await abrir(p, D.vacioEntreno2);
        await abrirFavoritas(p);
        await p.locator(`[data-testid="fav-apply-${idD}"]`).click();
        await p.waitForTimeout(900);
        await foto(p, `${ancho}_caso2_a_entreno`);
        t = await textoPanel(p, idD);
        comprobar('la frase del tipo de día',
            t?.includes('Esta favorita es de día de descanso; hoy tienes entreno.'), t);
        comprobar('la línea gris: «se añaden el intra y el post, que tendrás que rellenar»',
            t?.includes('se añaden el intra y el post, que tendrás que rellenar'), t);
        comprobar('botón «Aplicar como se guardó (pasa el día a descanso)»',
            t?.includes('Aplicar como se guardó (pasa el día a descanso)'), t);

        // Detalle 2 y 3: se aplica adaptando y el peri queda VACÍO pero CON macros,
        // el día queda sin cuadrar y NO se avisa aparte.
        if (ancho === 1280) {
            await p.locator(`[data-testid="fav-adapt-${idD}"]`).click();
            await p.waitForTimeout(7000);
            await p.screenshot({ path: `${CARPETA}/${ancho}_caso2_a_entreno_aplicada.png`, fullPage: true });
            // Por tarjeta, no por pestaña: la vista de comidas puede estar en lista.
            const tarjetas = await p.locator('[data-testid^="meal-card-"]').all();
            const claves = await Promise.all(tarjetas.map(async (c) =>
                (await c.getAttribute('data-testid')).replace('meal-card-', '')));
            comprobar('el intra y el post se añaden',
                claves.includes('Intra') && claves.includes('Post'), claves.join(' · '));
            const objIntra = p.locator('[data-testid="objetivo-Intra"]').first();
            comprobar('y traen sus macros',
                (await objIntra.count()) > 0 && /\d/.test(await objIntra.innerText()),
                (await objIntra.count()) ? await objIntra.innerText() : '(sin objetivo a la vista)');
            // «La app no se inventa qué meter dentro»: vacío de alimentos.
            const dentroIntra = limpio(await p.locator('[data-testid="meal-card-Intra"]').first()
                .innerText().catch(() => ''));
            comprobar('y vienen vacíos de alimentos',
                !dentroIntra.includes(POLLO.nombre) && !dentroIntra.includes(MERLUZA.nombre), dentroIntra);
            const avisos = (await p.locator('[data-sonner-toast]').allInnerTexts().catch(() => []))
                .map(limpio).filter(Boolean);
            console.log('        avisos:', avisos.join(' | ') || '(ninguno)');
            comprobar('no hay un aviso aparte de «sin cuadrar»',
                !avisos.some(a => /sin cuadrar|no cuadra/i.test(a)), avisos.join(' | '));
        }

        // ── Caso 3 · día con comidas + mismo tipo ────────────────────────────
        console.log('\n3 · Día con 3 comidas y favorita del mismo tipo');
        await abrir(p, D.tresEntreno);
        await abrirFavoritas(p);
        await p.locator(`[data-testid="fav-apply-${idE}"]`).click();
        await p.waitForTimeout(900);
        await foto(p, `${ancho}_caso3_tres_comidas`);
        t = await textoPanel(p, idE);
        comprobar('«Este día ya tiene 3 comidas. Al aplicar la favorita se borran y se quedan las de la favorita.»',
            t?.includes('Este día ya tiene 3 comidas. Al aplicar la favorita se borran y se quedan las de la favorita.'), t);
        comprobar('no dice nada del tipo de día (coincide)',
            !t?.includes('Esta favorita es de día'), t);
        comprobar('el botón dice solo «Aplicar»',
            limpio(await p.locator(`[data-testid="fav-reemplazar-${idE}"]`).innerText()) === 'Aplicar',
            limpio(await p.locator(`[data-testid="fav-reemplazar-${idE}"]`).innerText()));

        // ── Caso 4 · día con comidas + otro tipo, y el singular ──────────────
        console.log('\n4 · Día con 1 comida y favorita de otro tipo');
        await abrir(p, D.unaEntreno);
        await abrirFavoritas(p);
        await p.locator(`[data-testid="fav-apply-${idD}"]`).click();
        await p.waitForTimeout(900);
        await foto(p, `${ancho}_caso4_una_comida`);
        t = await textoPanel(p, idD);
        comprobar('«Este día ya tiene 1 comida.» (singular)',
            t?.includes('Este día ya tiene 1 comida.'), t);
        comprobar('las dos frases, y primero la de lo que se pierde',
            t && t.indexOf('Este día ya tiene') >= 0
              && t.indexOf('Este día ya tiene') < t.indexOf('Esta favorita es de día'), t);
        comprobar('y los botones del caso 2',
            t?.includes('Aplicar y adaptar a mi día de hoy')
              && t?.includes('Aplicar como se guardó (pasa el día a descanso)'), t);

        // ── Caso borde · solo el intra montado ───────────────────────────────
        console.log('\n5 · Día con solo el intra montado (0 comidas, pero no vacío)');
        await abrir(p, D.soloIntra);
        await abrirFavoritas(p);
        await p.locator(`[data-testid="fav-apply-${idD}"]`).click();
        await p.waitForTimeout(900);
        await foto(p, `${ancho}_caso_borde_solo_intra`);
        t = await textoPanel(p, idD);
        comprobar('no dice «0 comidas»', !t?.includes('0 comidas'), t);
        comprobar('lo llama por su nombre: «el intra»',
            t?.includes('Este día ya tiene el intra.'), t);

        await ctx.close();
    }

    await nav.close();

    // ── Limpieza ─────────────────────────────────────────────────────────────
    for (const f of Object.values(D)) await pide(`/diets/${f}`, { method: 'DELETE' }).catch(() => {});
    await pide(`/diets/favorites/${idE}`, { method: 'DELETE' }).catch(() => {});
    await pide(`/diets/favorites/${idD}`, { method: 'DELETE' }).catch(() => {});

    console.log(`\n\n════════ RESUMEN ════════`);
    if (!fallos.length) console.log('   Todo lo del documento, comprobado y bien.');
    else { console.log(`   ${fallos.length} sin cumplir:`); fallos.forEach(f => console.log('   ·', f)); }
    console.log(`   Capturas en ${CARPETA}/`);
})();
