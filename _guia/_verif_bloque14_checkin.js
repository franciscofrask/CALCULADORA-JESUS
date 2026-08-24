/**
 * Bloque 14 del doc 23-08: el cierre del día («¿Cómo fuiste hoy?»).
 *
 *   P75  guardar no cierra con llave: «Editar lo de hoy» reabre el formulario precargado
 *        y el segundo guardado SUSTITUYE al primero (una sola fila del día).
 *   P76  el historial enseña TODO lo que trae la entrada, no dos cosas de siete.
 *   P77  el contador dice las comidas que FALTAN, no las del día.
 *   P78  la entrada se llama «Cierre del día» aquí y en el Diario, no «DIARIO».
 *   P80  sin rutina contratada hay una nota de entreno opcional, y cae al Diario.
 *   P81  los textos, literales del doc.
 *
 * Cuenta propia de la prueba: p75.checkin@test.com (nivel1 cortesía, sin rutina, con una
 * dieta de hoy de 4 comidas: 2 registradas y 2 vacías, ninguna marcada).
 *
 * Uso:  node _guia/_verif_bloque14_checkin.js
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const APP = 'http://localhost:3000';
const API = 'http://127.0.0.1:8000';
const CARPETA = path.join(__dirname, 'capturas_bloque14_2308');

const resultados = [];
const mira = (ok, texto) => {
    resultados.push([!!ok, texto]);
    console.log(`${ok ? 'OK   ' : 'FALLO'} ${texto}`);
};

(async () => {
    fs.mkdirSync(CARPETA, { recursive: true });
    const navegador = await chromium.launch();
    const page = await navegador.newPage({ viewport: { width: 1360, height: 950 } });

    // El backend de dev se reinicia solo (watchfiles) cuando otro trabajo guarda un .py:
    // el login se reintenta en vez de darlo por muerto.
    let r = null;
    for (let i = 0; i < 20; i++) {
        try {
            r = await page.request.post(`${API}/api/auth/login`, {
                data: { email: 'p75.checkin@test.com', password: 'QaPrueba2026!' } });
            if (r.ok()) break;
        } catch { /* reiniciándose: se reintenta */ }
        await new Promise((res) => setTimeout(res, 3000));
    }
    if (!r || !r.ok()) throw new Error('el backend no levanta');
    const { access_token } = await r.json();
    const auth = { Authorization: `Bearer ${access_token}` };

    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, access_token);
    await page.goto(`${APP}/dashboard/checkins`, { waitUntil: 'domcontentloaded' });
    await page.getByTestId('cierre-guardar').waitFor({ timeout: 45000 });

    // ── P81 · Los textos, uno a uno ──────────────────────────────────────────
    const cuerpo = () => page.evaluate(() => document.body.innerText);
    let texto = await cuerpo();
    // LOS LITERALES SON LOS DEL DOC DEL 24-08, no los del 23. Aquel bloque 14 dejó cuatro
    // textos que Jesús no había pedido y en su documento del 24 los volvió a escribir tal
    // y como los quiere; la fase 0 los devolvió. Si algún día vuelve a fallar la línea del
    // movimiento, mira antes cuál de los dos documentos manda.
    mira(texto.includes('¿Cómo descansaste la noche de ayer?'), 'descanso: «¿Cómo descansaste la noche de ayer?»');
    mira(texto.includes('Fundamental tener una buena rutina de sueño si no la tienes ya'), 'descanso: la línea de ayuda');
    mira(texto.includes('fatal') && texto.includes('genial'), 'P81 descanso: de «fatal» a «genial»');
    mira(texto.includes('Niveles de energía durante el día'), 'energía: «Niveles de energía durante el día»');
    mira(texto.includes('Fuera de tu entrenamiento, en tu día normal'), 'energía: la línea de ayuda');
    mira(texto.includes('bajita') && texto.includes('pletórico'), 'P81 energía: de «bajita» a «pletórico»');
    mira(texto.includes('Hambre / ansiedad con la dieta') && texto.includes('nada') && texto.includes('mucha'), 'hambre: «con la dieta», de «nada» a «mucha»');
    mira(texto.includes('¿Te moviste lo suficiente?') && !texto.includes('desgaste'), 'movimiento: la pregunta de Jesús, sin «desgaste»');
    mira(texto.includes('Como siempre') && !texto.includes('Como me vengo moviendo'), 'movimiento: los botones cortos');
    mira(texto.includes('Moverte es salud y menos grasa: a más te muevas, más gastas\n'), 'P81 lema sin punto final');
    const lemaCursiva = await page.locator('p.italic', { hasText: 'Moverte es salud' }).count();
    mira(lemaCursiva === 1, 'P81 lema en cursiva');
    mira(texto.includes('Compártelo si quieres que lo veamos, o déjalo para ti (opcional).'), 'P81 notas: la frase con la coma y «(opcional)»');
    const placeholder = await page.getByTestId('cierre-notas').getAttribute('placeholder');
    mira(placeholder === 'De lo que quieras acordarte', 'P81 placeholder: «De lo que quieras acordarte»');

    // ── P77 · El contador de comidas: faltan DOS, no cuatro ─────────────────
    mira(texto.includes('Te quedan dos comidas sin registrar.'), 'P77 contador: «Te quedan dos comidas sin registrar.» (2 registradas de 4)');
    mira(!texto.includes('Te quedan cuatro comidas'), 'P77 ya no cuenta las comidas del día');

    // ── P80 · La nota de entreno del que no tiene rutina ─────────────────────
    await page.getByTestId('cierre-entreno-libre').waitFor({ timeout: 5000 });
    mira(true, 'P80 sin rutina: sale «Tu entreno de hoy» con su nota opcional');

    // ── Rellenar y guardar ────────────────────────────────────────────────────
    await page.getByTestId('cierre-descanso-4').click();
    await page.getByTestId('cierre-energia-3').click();
    await page.getByTestId('cierre-hambre-2').click();
    await page.getByTestId('cierre-movimiento-mas').click();
    await page.getByTestId('cierre-entreno-libre-nota').fill('Media hora de bici por mi cuenta');
    await page.getByTestId('cierre-notas').fill('Nota privada de la prueba del bloque 14');
    await page.getByTestId('cierre-peso').fill('70');
    await page.screenshot({ path: path.join(CARPETA, '01_formulario_relleno.jpg'), type: 'jpeg', quality: 60, fullPage: true });
    await page.getByTestId('cierre-guardar').click();

    // ── P75 · La pantalla de anotado con su botón de editar ─────────────────
    await page.getByTestId('cierre-editar').waitFor({ timeout: 30000 });
    texto = await cuerpo();
    mira(texto.includes('Anotado. Mañana seguimos.'), 'guardado: «Anotado. Mañana seguimos.»');
    mira(texto.includes('Editar lo de hoy'), 'P75 el anotado trae «Editar lo de hoy»');
    await page.screenshot({ path: path.join(CARPETA, '02_anotado_con_editar.jpg'), type: 'jpeg', quality: 60 });

    // Reabrir: el formulario vuelve PRECARGADO con lo guardado.
    await page.getByTestId('cierre-editar').click();
    await page.getByTestId('cierre-guardar').waitFor({ timeout: 15000 });
    const notasPrevias = await page.getByTestId('cierre-notas').inputValue();
    const entrenoPrevio = await page.getByTestId('cierre-entreno-libre-nota').inputValue();
    const pesoPrevio = await page.getByTestId('cierre-peso').inputValue();
    mira(notasPrevias === 'Nota privada de la prueba del bloque 14', 'P75 al editar, las notas vuelven puestas');
    mira(entrenoPrevio === 'Media hora de bici por mi cuenta', 'P75 al editar, la nota de entreno vuelve puesta');
    mira(pesoPrevio === '70', 'P75 al editar, el peso vuelve puesto');
    const descansoMarcado = await page.getByTestId('cierre-descanso-4').getAttribute('class');
    mira(/border-brand/.test(descansoMarcado || ''), 'P75 al editar, el descanso 4 sigue marcado');
    texto = await cuerpo();
    mira(texto.includes('Último registro'), 'P81 «Último registro» con U mayúscula');
    await page.screenshot({ path: path.join(CARPETA, '03_edicion_precargada.jpg'), type: 'jpeg', quality: 60, fullPage: true });

    // Corregir y volver a guardar: energía 3 -> 5 y otra nota.
    await page.getByTestId('cierre-energia-5').click();
    await page.getByTestId('cierre-notas').fill('Nota corregida en la edición');
    await page.getByTestId('cierre-guardar').click();
    await page.getByTestId('cierre-editar').waitFor({ timeout: 30000 });

    // ── Por API: lo editado SUSTITUYE ────────────────────────────────────────
    // Con el día del NAVEGADOR, que es el que manda la pantalla (regla del 23-08): sin
    // `?fecha=` el servidor contesta por el día de España, que aquí ya es mañana.
    const diaNavegador = await page.evaluate(() => new Date().toLocaleDateString('en-CA'));
    const hoy = await (await page.request.get(`${API}/api/checkins/hoy?fecha=${diaNavegador}`, { headers: auth })).json();
    mira(hoy.hecho === true && hoy.checkin?.energy === 5, 'P75 API: /checkins/hoy trae la energía corregida (5)');
    mira(hoy.checkin?.notas?.texto === 'Nota corregida en la edición', 'P75 API: la nota corregida sustituyó a la primera');
    mira(hoy.checkin?.entreno_nota === 'Media hora de bici por mi cuenta', 'P80 API: la nota de entreno se guarda con el cierre');
    const lista = await (await page.request.get(`${API}/api/checkins?type=daily&limit=100`, { headers: auth })).json();
    const delDia = lista.filter((c) => c.dia === hoy.fecha);
    mira(delDia.length === 1, `P75 API: una sola fila del día (hay ${delDia.length})`);

    // ── P76 + P78 · El historial entero y la etiqueta unificada ─────────────
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.getByTestId('cierre-editar').waitFor({ timeout: 45000 });
    texto = await cuerpo();
    // La píldora de tipo desapareció con la fase 0: el historial va partido en «Tus días» y
    // «Reportes anteriores», así que el tipo lo dice el título del bloque y no cada línea.
    mira(/Tus días/i.test(texto), 'el historial tiene su bloque «Tus días»');
    mira(!/\bDIARIO\b/.test(texto.replace(/Tu diario/g, '')), 'P78 ya no hay píldora «DIARIO»');
    for (const cosa of ['Energía 5/5', 'Hambre 2/5', 'Descanso 4/5', 'Movimiento: más', '70 kg',
                        'Media hora de bici por mi cuenta', 'Nota corregida en la edición']) {
        mira(texto.includes(cosa), `P76 el historial enseña «${cosa}»`);
    }
    mira(/solo para ti/i.test(texto), 'P76 la nota sale con su marca de privacidad');
    await page.screenshot({ path: path.join(CARPETA, '04_historial_completo.jpg'), type: 'jpeg', quality: 60, fullPage: true });

    // ── El Diario (dentro de Seguimiento) ────────────────────────────────────
    await page.goto(`${APP}/dashboard/reports`, { waitUntil: 'domcontentloaded' });
    const puerta = page.locator('button, [role="button"], div').filter({ hasText: /^Diario/ }).first();
    await puerta.waitFor({ timeout: 30000 });
    await puerta.click();
    await page.getByTestId('diario-dia').first().waitFor({ timeout: 30000 });
    texto = await cuerpo();
    mira(texto.includes('· cierre del día'), 'P78 la entrada del Diario también se llama «cierre del día»');
    mira(texto.includes('Media hora de bici por mi cuenta'), 'P80 la nota de entreno cae al Diario');
    mira(texto.includes('Nota corregida en la edición'), 'las notas del cierre siguen cayendo al Diario');
    await page.screenshot({ path: path.join(CARPETA, '05_diario.jpg'), type: 'jpeg', quality: 60, fullPage: true });

    // ── Una pasada en móvil, que es donde vive esta pantalla ─────────────────
    const movil = await navegador.newPage({ viewport: { width: 390, height: 844 } });
    await movil.goto(APP, { waitUntil: 'domcontentloaded' });
    await movil.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, access_token);
    await movil.goto(`${APP}/dashboard/checkins`, { waitUntil: 'domcontentloaded' });
    await movil.getByTestId('cierre-editar').waitFor({ timeout: 45000 });
    await movil.getByTestId('cierre-editar').click();
    await movil.getByTestId('cierre-guardar').waitFor({ timeout: 15000 });
    await movil.screenshot({ path: path.join(CARPETA, '06_movil_edicion.jpg'), type: 'jpeg', quality: 60, fullPage: true });
    mira(true, 'móvil: el editar reabre el formulario igual');

    await navegador.close();
    const fallos = resultados.filter(([ok]) => !ok).length;
    console.log(`\n${resultados.length - fallos}/${resultados.length} comprobaciones bien. Capturas en ${CARPETA}`);
    process.exit(fallos ? 1 : 0);
})().catch((e) => { console.error('PETÓ:', e); process.exit(2); });
