/**
 * «SI UNA FAVORITA LLEVA ALGO QUE EVITAS, DEBE AVISARSE» (Gonzalo, minuto 25:59 del video
 * del 3-09: «quite aves, aplique la dieta que tenia pollo y me añadio el pollo igualmente»).
 *
 * Comprueba EN PANTALLA que el aviso sale al aplicar la favorita, y que la favorita se aplica
 * igual: la app no borra lo que ha puesto el cliente.
 *
 * Deja la cuenta de pruebas como estaba: preferencias, favorita y dia se reponen al final.
 *
 * Uso:  node _guia/_verificar_favorita_con_evitados_0309.js
 */
const fs = require('fs');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const ORIGEN = process.env.ORIGEN || '2026-08-31';   // el dia que ya tiene comida montada
const CARPETA = '_guia/_favorita_evitados';
if (!fs.existsSync(CARPETA)) fs.mkdirSync(CARPETA, { recursive: true });

// El dia que ensena la app es el del reloj del NAVEGADOR, no el de Madrid.
const HOY = new Date().toLocaleDateString('en-CA');

let TOKEN = '';
const api = async (ruta, o = {}) => {
    const r = await fetch(`${API}/api${ruta}`, { ...o,
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${TOKEN}`, ...(o.headers || {}) } });
    const t = await r.text();
    try { return JSON.parse(t); } catch { return { _texto: t }; }
};

(async () => {
    TOKEN = (await api('/auth/login', { method: 'POST',
        body: JSON.stringify({ email: CUENTA, password: CLAVE }) })).access_token;
    if (!TOKEN) { console.log('no he podido entrar'); return; }

    // ── Lo que hay, para reponerlo ───────────────────────────────────────────
    const prefsAntes = await api('/user/preferences');
    const diaAntes = await api(`/diets/${HOY}`);
    const habiaDia = Boolean(diaAntes?.exists);
    const origen = await api(`/diets/${ORIGEN}`);
    if (!origen?.exists) { console.log(`el dia ${ORIGEN} esta vacio, no hay con que hacer la favorita`); return; }

    const conAlimentos = Object.entries(origen.comidas || {})
        .filter(([, c]) => (c?.alimentos || []).length > 0);
    const nombres = conAlimentos.flatMap(([, c]) => c.alimentos.map((a) => a.nombre));
    console.log(`favorita a partir de ${ORIGEN}: ${nombres.join(', ')}`);

    // La palabra a evitar sale del propio dia, para no inventar nada: la primera que aparece.
    const PALABRA = process.env.PALABRA || 'pavo';
    const chocan = nombres.filter((n) => (n || '').toLowerCase().includes(PALABRA));
    if (!chocan.length) { console.log(`ese dia no lleva nada con «${PALABRA}»`); return; }
    console.log(`lo que choca con «${PALABRA}»: ${chocan.join(', ')}`);

    let favId = null;
    let hecho = false;
    try {
        // ── Se prepara el caso ───────────────────────────────────────────────
        await api('/user/preferences', { method: 'POST', body: JSON.stringify({
            food_preferences: (prefsAntes.food_preferences || []).length >= 3
                ? prefsAntes.food_preferences : ['carnes', 'pescados', 'verduras'],
            avoided_categories: prefsAntes.avoided_categories || [],
            avoided_keywords: [...new Set([...(prefsAntes.avoided_keywords || []), PALABRA])],
        }) });

        const fav = await api('/diets/favorites', { method: 'POST', body: JSON.stringify({
            name: `PRUEBA evitados ${PALABRA}`,
            tipo_dia: origen.tipo_dia || 'entrenamiento',
            num_comidas: origen.num_comidas || 4,
            momento_entreno: origen.momento_entreno || 1,
            opcion_peri: origen.opcion_peri || 'intra_post',
            comidas: origen.comidas,
        }) });
        favId = fav?.id || fav?.favorite?.id || fav?.fav_id || null;
        console.log(`favorita creada: ${favId || JSON.stringify(fav).slice(0, 160)}`);

        // El dia de hoy, vacio, para que la favorita entre limpia.
        if (habiaDia) await api(`/diets/${HOY}`, { method: 'DELETE' });

        // ── Y se aplica desde la pantalla ────────────────────────────────────
        const nav = await chromium.launch();
        const p = await (await nav.newContext({ viewport: { width: 430, height: 1500 }, deviceScaleFactor: 2 })).newPage();
        await p.goto(APP, { waitUntil: 'domcontentloaded' });
        await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, TOKEN);
        await p.goto(`${APP}/dashboard/nutrition`, { waitUntil: 'networkidle' }).catch(() => {});
        await p.waitForTimeout(14000);

        // El menu de la pantalla («...») y de ahi «Mis favoritas».
        await p.locator('[data-testid="menu-de-la-pantalla"], button[aria-label*="pciones"]').first()
            .click({ force: true }).catch(() => {});
        await p.waitForTimeout(1200);
        await p.locator('text=/favorit/i').first().click({ force: true }).catch(() => {});
        await p.waitForTimeout(2500);
        await p.screenshot({ path: `${CARPETA}/1_lista_de_favoritas.png`, fullPage: true });

        await p.locator(`text=PRUEBA evitados ${PALABRA}`).first().click({ force: true }).catch(() => {});
        await p.waitForTimeout(2000);
        // Si pregunta antes de sustituir, se confirma.
        await p.locator('button:has-text("Aplicar"), button:has-text("Sustituir"), button:has-text("Sí")')
            .first().click({ force: true }).catch(() => {});
        await p.waitForTimeout(7000);

        const avisos = await p.locator('[data-sonner-toast]').allInnerTexts().catch(() => []);
        await p.screenshot({ path: `${CARPETA}/2_al_aplicarla.png`, fullPage: true });
        console.log('\n── LO QUE DICE LA PANTALLA ──');
        avisos.forEach((t) => console.log(`  · ${t.replace(/\n/g, ' | ')}`));

        const dicho = avisos.some((t) => /entre lo que evitas/i.test(t));
        const dia = await api(`/diets/${HOY}`);
        const entro = Object.values(dia?.comidas || {})
            .some((c) => (c?.alimentos || []).some((a) => (a.nombre || '').toLowerCase().includes(PALABRA)));
        console.log('\n── RESULTADO ──');
        console.log(`  avisa de lo que evitas: ${dicho ? 'SÍ' : 'NO'}`);
        console.log(`  y lo aplica igual:      ${entro ? 'SÍ' : 'NO'}`);
        hecho = dicho && entro;

        await nav.close();
    } finally {
        // ── Se repone todo ───────────────────────────────────────────────────
        await api('/user/preferences', { method: 'POST', body: JSON.stringify({
            food_preferences: prefsAntes.food_preferences || [],
            avoided_categories: prefsAntes.avoided_categories || [],
            avoided_keywords: prefsAntes.avoided_keywords || [],
        }) }).catch(() => {});
        if (favId) await api(`/diets/favorites/${favId}`, { method: 'DELETE' }).catch(() => {});
        await api(`/diets/${HOY}`, { method: 'DELETE' }).catch(() => {});
        if (habiaDia) {
            await api('/diets', { method: 'POST', body: JSON.stringify({
                fecha: HOY, tipo_dia: diaAntes.tipo_dia, num_comidas: diaAntes.num_comidas,
                momento_entreno: diaAntes.momento_entreno, opcion_peri: diaAntes.opcion_peri,
                comidas: diaAntes.comidas,
            }) }).catch(() => {});
        }
        const prefs = await api('/user/preferences');
        console.log(`\n  repuesto · evita: ${JSON.stringify(prefs.avoided_keywords)} · ` +
            `dia ${HOY}: ${(await api(`/diets/${HOY}`))?.exists ? 'como estaba' : 'vacío, como estaba'}`);
        if (!hecho) process.exitCode = 1;
    }
})();
