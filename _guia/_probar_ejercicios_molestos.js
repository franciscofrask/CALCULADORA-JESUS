/**
 * LA PREGUNTA 5 DEL DOC DEL 1-09: «¿Sigue habiendo ejercicios que te dan molestias?»
 *
 * Sustituye al bloque de lesiones -- zona, «como esta este mes» y ejercicios vetados -- por
 * UNA pregunta con etiquetas quitables. Aqui se mira la PANTALLA: que el titulo y la ayuda
 * son los suyos, que salen ya puestos los que dio, que el bloque viejo se ha ido y que la
 * lista se puede quitar y anadir.
 *
 * Donde ACABA el dato no se ve mirando, y es lo importante: va a `client_profiles.injuries`,
 * que es por donde agrupa el generador de rutinas. Hasta el 3-09 la respuesta se guardaba en
 * `lesiones`, que el generador NO mira: se le preguntaba por sus lesiones todos los meses y
 * no llegaba nunca a su rutina. Eso lo fijan los tests de `test_paso1_mensual_0109.py`, que
 * es donde se puede comprobar sin mandar un reporte de verdad.
 *
 * La ventana del mensual solo esta abierta unos dias, asi que se entra con `?ver=mensual`
 * (modo revision, admin o trainer).
 *
 * Uso:  backend/venv/Scripts/python.exe _guia/_escenario_molestias.py
 *       node _guia/_probar_ejercicios_molestos.js
 *       backend/venv/Scripts/python.exe _guia/_escenario_molestias.py --deshacer
 */
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'francisco@test.com';
const CLAVE = process.env.CLAVE || 'demo123';

let fallos = 0;
const bien = (t, d) => console.log(`   OK   ${t}${d ? `  [${d}]` : ''}`);
const mal = (t, d) => { fallos++; console.log(`   MAL  ${t}${d ? `  [${d}]` : ''}`); };

(async () => {
    const login = await fetch(`${API}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: CUENTA, password: CLAVE }),
    }).then((r) => r.json());
    if (!login.access_token) throw new Error('no he podido entrar');
    const token = login.access_token;
    const api = async (ruta, metodo = 'GET', cuerpo) => {
        const r = await fetch(API + ruta, {
            method: metodo,
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
            body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
        });
        if (!r.ok) throw new Error(`${metodo} ${ruta} -> ${r.status} ${await r.text()}`);
        return r.json();
    };

    // LOS DOS EJERCICIOS DE SU MAQUETA, PUESTOS ANTES. No hay endpoint para que el propio
    // cliente se escriba `injuries` -- lo escriben el alta y el panel --, asi que el
    // escenario lo monta un guion aparte, en dev y solo a esta cuenta:
    //
    //     backend/venv/Scripts/python.exe _guia/_escenario_molestias.py
    //     backend/venv/Scripts/python.exe _guia/_escenario_molestias.py --deshacer
    //
    // Aqui solo se comprueba que llegan, que es lo que se puede ver.
    const ficha = await api('/api/reports/formulario?tipo=mensual');
    const puestos = (ficha.datos || {}).ejercicios_molestos || [];
    console.log('lo que le llega ya puesto: ' + JSON.stringify(puestos));
    if (puestos.length) bien('el servidor manda los que ya dio', puestos.join(' · '));
    else mal('no llega ninguno: monta el escenario antes');

    const nav = await chromium.launch();
    const p = await (await nav.newContext({ viewport: { width: 390, height: 1600 },
                                            locale: 'es-ES', timezoneId: 'Europe/Madrid' })).newPage();
    await p.goto(APP, { waitUntil: 'domcontentloaded' });
    await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, token);
    await p.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
    await p.waitForTimeout(11000);
    for (let i = 0; i < 4; i++) {
        const s = p.locator('[data-testid="recorrido-saltar"]');
        if (!(await s.count())) break;
        await s.click({ force: true }).catch(() => {});
        await p.waitForTimeout(900);
    }
    // POR DONDE SE ENTRA, QUE DEPENDE DE LA CUENTA. `?ver=mensual` solo lo ve admin o
    // trainer, y el bloque de lesiones solo lo lleva el perfil «completo», que aquí es la
    // cuenta del CLIENTE. Así que para ella hay que entrar por su tarjeta de Seguimiento,
    // que es el camino de verdad y solo existe con la ventana abierta.
    await p.goto(`${APP}/dashboard/reports?ver=mensual`, { waitUntil: 'networkidle' }).catch(() => {});
    await p.waitForTimeout(8000);
    if (!(await p.locator('[data-testid="mensual-paso1"]').count())) {
        const tarjeta = p.locator('[data-testid="seg-revision"]').first();
        if (await tarjeta.count()) { await tarjeta.click(); await p.waitForTimeout(6000); }
    }
    if (!(await p.locator('[data-testid="mensual-paso1"]').count())) {
        mal('no se abre el mensual con esta cuenta', p.url());
        await p.screenshot({ path: '_guia/_dbg_mensual.png', fullPage: true });
        console.log('   visibles: ' + JSON.stringify((await p.evaluate(() =>
            [...document.querySelectorAll('[data-testid]')].filter((e) => e.offsetParent !== null)
                .map((e) => e.getAttribute('data-testid')))).slice(0, 16)));
        console.log(`\n${fallos} FALLOS`); await nav.close(); process.exit(1);
    }

    // Del paso 1 al 2 (huecos + peso, ver `_probar_mensual_0309.js`).
    const huecos = await p.evaluate(() => [...new Set([...document.querySelectorAll('[data-testid^="paso1-hueco-"][data-testid*="-op-"]')]
        .map((e) => e.getAttribute('data-testid').split('-op-')[0]))]);
    for (const h of huecos) {
        const op = p.locator(`[data-testid^="${h}-op-"]`).first();
        if (await op.count()) { await op.scrollIntoViewIfNeeded(); await op.click().catch(() => {}); await p.waitForTimeout(400); }
    }
    if (!(await p.locator('[data-testid="weight-input"]:visible').count())) {
        const abrir = p.locator('[data-testid="paso1-modificar-btn"]').first();
        if (await abrir.count()) { await abrir.scrollIntoViewIfNeeded(); await abrir.click(); await p.waitForTimeout(1200); }
    }
    const campo = p.locator('[data-testid="weight-input"]:visible').first();
    if (await campo.count() && !(await campo.inputValue())) { await campo.fill('78.2'); await p.waitForTimeout(500); }
    const confirmar = p.locator('[data-testid="paso1-confirmar"]').first();
    if (await confirmar.count()) { await confirmar.scrollIntoViewIfNeeded(); await confirmar.click(); await p.waitForTimeout(4000); }

    // ───────────────────────────────────────────────────────────────────────
    console.log('\nLa pregunta, como la dibuja su maqueta');
    const bloque = p.locator('[data-testid="mensual-molestias"]').first();
    if (!(await bloque.count())) {
        mal('no sale la pregunta de las molestias');
        console.log(`\n${fallos} FALLOS`); await nav.close(); process.exit(1);
    }
    const texto = (await bloque.innerText()).replace(/\s+/g, ' ').trim();
    console.log('   ' + texto);
    if (texto.includes('¿Sigue habiendo ejercicios que te dan molestias?')) bien('el título, literal');
    else mal('el título no es el de su documento');
    if (texto.includes('Estos son los que me diste. Quita los que ya no y añade los nuevos'))
        bien('y su ayuda, literal');
    else mal('la ayuda no es la de su documento');
    for (const e of ['Press militar', 'Sentadilla profunda']) {
        if (texto.includes(e)) bien(`sale puesto «${e}»`); else mal(`no sale «${e}»`);
    }
    if (texto.includes('+ Añadir ejercicio')) bien('y el «+ Añadir ejercicio»');
    else mal('falta el «+ Añadir ejercicio»');

    // Y lo que YA NO está: el bloque viejo.
    if (!(await p.locator('[data-testid="mensual-lesiones"]').count())) bien('el bloque de lesiones ya no está');
    else mal('sigue el bloque de lesiones');
    const estados = await p.locator('[data-testid^="lesion-"]').count();
    if (!estados) bien('y no se pregunta el «peor / igual / mejor / superada»');
    else mal('sigue preguntándose el estado del mes', String(estados));
    // La barra de abajo es fija y se pinta ENCIMA: si el bloque queda pegado al borde,
    // la foto sale con la barra por delante. Se sube un poco antes de retratarlo.
    await bloque.scrollIntoViewIfNeeded();
    await p.evaluate(() => window.scrollBy(0, 160));
    await p.waitForTimeout(400);
    await bloque.screenshot({ path: '_guia/_mensual_molestias.png' });

    // ───────────────────────────────────────────────────────────────────────
    console.log('\nQuita uno, añade otro, y a ver dónde acaba');
    // La «x» del que ya no le molesta.
    const quitar = p.locator('[data-testid="molestias"] button').first();
    await quitar.click().catch(() => {});
    await p.waitForTimeout(500);
    const anadir = p.locator('[data-testid="molestias-anadir"]').first();
    if (await anadir.count()) {
        await anadir.click();
        const input = p.locator('[data-testid="molestias-input"]').first();
        if (await input.count()) { await input.fill('Peso muerto'); await input.press('Enter'); await p.waitForTimeout(600); }
    }
    console.log('   ahora: ' + (await bloque.innerText()).replace(/\s+/g, ' ').trim());

    console.log(`\n${fallos ? `${fallos} FALLOS` : 'la pregunta 5, como su documento'}`);
    await nav.close();
    process.exit(fallos ? 1 : 0);
})();
