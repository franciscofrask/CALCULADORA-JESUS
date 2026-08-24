/**
 * Fase 0 del doc del 24-08, comprobada contra la app real (dev).
 *
 * Las nueve cosas de codigo, en la pantalla que ve el cliente y en la del equipo:
 *   01  la pregunta del movimiento y los botones cortos
 *   02  los cuatro literales del check-in
 *   03  Mi semana ya no dice «0 de N entrenos» a quien no ha registrado ninguno
 *   04  al que tiene rutina en PDF no le sale la caja de «apunta tu entreno»
 *   05  reeditar el cierre no esconde lo que ya contesto
 *   06  el perientreno dice el modo real
 *   07  el historial va partido en «Tus dias» y «Reportes anteriores», sin hora
 *   08  la frase del dia solo sale el dia que es suya
 *   09  el aviso del panel que empezaba por «Y» y los nombres a una letra van aparte
 *       (los comprobo el agente del panel con medidas; aqui solo el cliente)
 *
 * Uso:  node _guia/_verif_fase0_2408.js
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const APP = 'http://localhost:3000';
const API = 'http://127.0.0.1:8000';
const CARPETA = path.join(__dirname, 'capturas_fase0_2408');

const resultados = [];
const mira = (ok, texto) => {
    resultados.push([!!ok, texto]);
    console.log(`${ok ? 'OK   ' : 'FALLO'} ${texto}`);
};

async function entra(page, email, clave) {
    // El backend de dev se reinicia solo cuando alguien guarda un .py: se reintenta.
    let r = null;
    for (let i = 0; i < 20; i++) {
        try {
            r = await page.request.post(`${API}/api/auth/login`, { data: { email, password: clave } });
            if (r.ok()) break;
        } catch { /* reiniciandose */ }
        await new Promise((res) => setTimeout(res, 3000));
    }
    if (!r || !r.ok()) throw new Error(`no entra con ${email}`);
    const { access_token } = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, access_token);
    return access_token;
}

(async () => {
    fs.mkdirSync(CARPETA, { recursive: true });
    const nav = await chromium.launch();
    const page = await nav.newPage({ viewport: { width: 1360, height: 1000 } });
    const cuerpo = () => page.evaluate(() => document.body.innerText);

    // ── El cliente del bloque 14, que no tiene rutina y tiene dieta de hoy ───────
    await entra(page, 'p75.checkin@test.com', 'QaPrueba2026!');
    await page.goto(`${APP}/dashboard/checkins`, { waitUntil: 'domcontentloaded' });
    await page.getByTestId('cierre-guardar').waitFor({ timeout: 60000 });
    await page.waitForTimeout(2500);   // el ultimo peso y el historial llegan en otra vuelta
    let texto = await cuerpo();
    await page.screenshot({ path: path.join(CARPETA, '01_cierre.png'), fullPage: true });

    // 01 · el movimiento
    mira(texto.includes('¿Te moviste lo suficiente?'), '01 la pregunta es «¿Te moviste lo suficiente?»');
    mira(!/desgaste/i.test(texto), '01 ya no dice «desgaste» en ninguna parte');
    mira(texto.includes('Como siempre') && !texto.includes('Como me vengo moviendo'),
        '01 los botones son «Menos / Como siempre / Más»');

    // 02 · los cuatro literales
    mira(texto.includes('¿Cómo descansaste la noche de ayer?'), '02 descanso en pretérito simple');
    mira(texto.includes('Fundamental tener una buena rutina de sueño si no la tienes ya'),
        '02 descanso: la línea de ayuda');
    mira(texto.includes('Niveles de energía durante el día'), '02 energía: «Niveles de»');
    mira(texto.includes('Fuera de tu entrenamiento, en tu día normal'), '02 energía: la línea de ayuda');
    mira(texto.includes('Hambre / ansiedad con la dieta'), '02 hambre: «con la dieta»');
    mira(texto.includes('Registrarlo es opcional, sólo para ti. Te lo pediremos sólo para los reportes'),
        '02 peso: la ayuda en su renglón');
    mira(/Último registro:.*·/.test(texto), '02 peso: «Último registro» con punto medio');

    // 07 · el historial partido, y sin hora
    mira(/tus d[ií]as/i.test(texto), '07 el historial tiene el bloque «Tus días»');
    const conHora = await page.evaluate(() =>
        /\d{1,2} [a-zé]{3}\.? \d{4},? \d{2}:\d{2}/i.test(document.body.innerText));
    mira(!conHora, '07 las líneas del historial ya no llevan hora');

    // 05 · reeditar no esconde lo contestado
    const yaGuardado = await page.getByTestId('cierre-editar').count();
    if (yaGuardado) {
        await page.getByTestId('cierre-editar').click();
        await page.getByTestId('cierre-guardar').waitFor({ timeout: 20000 });
        texto = await cuerpo();
        mira(texto.includes('Notas personales') || (await page.getByTestId('cierre-notas').count()) > 0,
            '05 al reeditar salen las notas aunque el cierre sea corto');
        mira((await page.getByTestId('cierre-peso').count()) > 0,
            '05 al reeditar sale el peso aunque el cierre sea corto');
        await page.screenshot({ path: path.join(CARPETA, '02_reedicion.png'), fullPage: true });
    } else {
        console.log('     (no hay cierre guardado hoy para esta cuenta: el 05 se comprueba en la batería)');
    }

    // 03 · Mi semana
    await page.goto(`${APP}/dashboard/mi-semana`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3500);
    texto = await cuerpo();
    await page.screenshot({ path: path.join(CARPETA, '03_mi_semana.png'), fullPage: true });
    mira(!/\b0 de \d+ entrenos?\b/.test(texto), '03 Mi semana no dice «0 de N entrenos»');
    mira(!/\b0 entrenos?\b/.test(texto), '03 Mi semana tampoco dice «0 entrenos» a secas');

    // 08 · la frase del día
    await page.goto(`${APP}/dashboard`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3500);
    texto = await cuerpo();
    await page.screenshot({ path: path.join(CARPETA, '04_inicio.png'), fullPage: true });
    const ajustes = await page.evaluate(async () => {
        const r = await fetch('http://127.0.0.1:8000/api/settings/app', {
            headers: { Authorization: 'Bearer ' + localStorage.getItem('token') } });
        return r.ok ? r.json() : null;
    });
    const fraseGuardada = ajustes && ajustes.frase_del_dia;
    const hoy = new Date().toLocaleDateString('en-CA');
    if (fraseGuardada && fraseGuardada.texto) {
        const seVe = texto.includes(fraseGuardada.texto);
        const esDeHoy = fraseGuardada.fecha === hoy;
        mira(seVe === esDeHoy,
            `08 la frase (${fraseGuardada.fecha}) ${esDeHoy ? 'es de hoy y se ve' : 'no es de hoy y no se ve'}`);
    } else {
        mira(true, '08 no hay frase guardada, no hay nada que enseñar');
    }

    // 06 · el perientreno
    await page.goto(`${APP}/dashboard/mis-macros`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3500);
    texto = await cuerpo();
    await page.screenshot({ path: path.join(CARPETA, '05_mis_macros.png'), fullPage: true });
    const conf = await page.evaluate(async () => {
        const r = await fetch('http://127.0.0.1:8000/api/user/diet-config', {
            headers: { Authorization: 'Bearer ' + localStorage.getItem('token') } });
        return r.ok ? r.json() : null;
    });
    if (/perientreno/i.test(texto)) {
        const dicePeri = /Perientreno \(([^)]+)\)/i.exec(texto);
        const modo = (conf && (conf.opcion_peri || conf.diet_opcion_peri)) || '(sin dato)';
        mira(!!dicePeri, `06 el rótulo del peri existe: ${dicePeri ? dicePeri[0] : 'no sale'} · modo real ${modo}`);
        if (dicePeri) {
            const rotulo = dicePeri[1].toLowerCase().replace(/\s+/g, '_');
            mira(String(modo).includes(rotulo.split('_')[0]) || rotulo.includes(String(modo).split('_')[0]),
                `06 el rótulo «${dicePeri[1]}» cuadra con el modo guardado «${modo}»`);
        }
    } else {
        console.log('     (esta cuenta no tiene perientreno en Mis macros)');
    }

    await nav.close();

    const fallos = resultados.filter(([ok]) => !ok);
    console.log(`\n${resultados.length - fallos.length}/${resultados.length} bien.`);
    if (fallos.length) {
        console.log('FALLAN:');
        fallos.forEach(([, t]) => console.log('  - ' + t));
        process.exitCode = 1;
    }
    console.log(`Capturas en ${CARPETA}`);
})();
