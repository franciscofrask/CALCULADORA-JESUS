/**
 * «EL REPORTE MENSUAL Y SU INFORME» (doc del 1-09), repasado punto por punto.
 *
 * El documento tiene tres partes y esto las mira las tres, sin dar ninguna por hecha:
 *
 *   00  LOS CUATRO PASOS      la cabecera «Son 4 pasos» con el suyo marcado, y sus rotulos
 *   00  EL PASO 1 Y EL PERIODO  el selector «cambia el BLOQUE ENTERO, no solo el peso»
 *   00  Y SI NO TENGO SUS CHECK-IN  las cinco preguntas con estrellas
 *
 * DOS COSAS QUE HAY QUE SABER PARA QUE ESTO FUNCIONE, y que costaron un rato:
 *
 *   · La ventana del mensual solo esta abierta unos dias. Fuera de ella no hay formulario
 *     que mirar («lo proximo es tu reporte mensual, el viernes 18 sep»), asi que se entra
 *     con `?ver=mensual`, el modo revision del 14-08, que abre la pantalla sin tocar datos.
 *     Eso lo ve admin o trainer: por eso la cuenta es la del equipo y no la del cliente.
 *   · Cual de las DOS versiones del paso 1 sale lo decide `hay_datos_suficientes`: hacen
 *     falta cierres en al menos la mitad de los dias. Para ver las dos:
 *
 *         backend/venv/Scripts/python.exe _guia/_escenario_mensual_con_checkin.py
 *         node _guia/_probar_mensual_0309.js                 -> la version larga
 *         backend/venv/Scripts/python.exe _guia/_escenario_mensual_con_checkin.py --deshacer
 *         node _guia/_probar_mensual_0309.js                 -> la version corta
 *
 * Uso:  node _guia/_probar_mensual_0309.js
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

    const nav = await chromium.launch();
    const p = await (await nav.newContext({ viewport: { width: 390, height: 1600 },
                                            locale: 'es-ES', timezoneId: 'Europe/Madrid' })).newPage();
    const pedidas = [];
    const quejas = [];
    p.on('request', (r) => { if (/mensual\/paso1/.test(r.url())) pedidas.push(r.url()); });
    p.on('console', (m) => { if (m.type() === 'error') quejas.push(m.text().slice(0, 160)); });
    p.on('response', (r) => { if (r.status() >= 400 && /\/api\//.test(r.url()))
        quejas.push(`${r.status()} ${r.url().split('/api/')[1]}`); });

    await p.goto(APP, { waitUntil: 'domcontentloaded' });
    await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, login.access_token);
    await p.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
    await p.waitForTimeout(11000);
    for (let i = 0; i < 4; i++) {
        const s = p.locator('[data-testid="recorrido-saltar"]');
        if (!(await s.count())) break;
        await s.click({ force: true }).catch(() => {});
        await p.waitForTimeout(900);
    }
    await p.goto(`${APP}/dashboard/reports?ver=mensual`, { waitUntil: 'networkidle' }).catch(() => {});
    await p.waitForTimeout(8000);

    const txt = async (sel) => {
        const l = p.locator(sel).first();
        return (await l.count()) ? (await l.innerText()).replace(/\s+/g, ' ').trim() : null;
    };

    if (!(await p.locator('[data-testid="mensual-paso1"]').count())) {
        mal('no se abre el mensual: sin formulario no hay nada que mirar', p.url());
        console.log(`\n${fallos} FALLOS`); await nav.close(); process.exit(1);
    }

    // ───────────────────────────────────────────────────────────────────────
    console.log('\n00 · Los cuatro pasos, con el suyo marcado');
    const cabecera = await txt('[data-testid="mensual-son-4-pasos"]');
    console.log('   ' + cabecera);
    for (const frase of ['Son 4 pasos',
                         'Actualizar tus datos y confirmar que están bien',
                         'Escuchar tus sensaciones y dudas',
                         'Tus fotos y tus medidas',
                         'Entregarte el plan nuevo con el informe y darte feedback']) {
        if ((cabecera || '').toLowerCase().includes(frase.toLowerCase())) bien(`«${frase}»`);
        else mal(`falta «${frase}»`);
    }
    // «El suyo marcado»: no vale mirar si el 1 está pintado, hay que ver que se DISTINGUE
    // de los otros tres. Se compara el aspecto de cada uno con el del paso 1.
    const pintas = await p.evaluate(() => [1, 2, 3, 4].map((n) => {
        const e = document.querySelector(`[data-testid="mensual-paso-${n}"]`);
        if (!e) return null;
        const c = getComputedStyle(e);
        const bola = e.querySelector('span, div');
        const b = bola ? getComputedStyle(bola) : c;
        return `${c.color}|${c.fontWeight}|${b.backgroundColor}`;
    }));
    console.log('   ' + JSON.stringify(pintas));
    if (pintas[0] && pintas.slice(1).every((x) => x !== pintas[0]))
        bien('el paso 1 se distingue de los otros tres');
    else mal('el paso en el que está no se distingue de los demás', JSON.stringify(pintas));

    // ───────────────────────────────────────────────────────────────────────
    const laLarga = await p.locator('[data-testid="paso1-periodo"]').count() > 0;
    console.log(`\n00 · El paso 1 · ${laLarga ? 'la versión que ENSEÑA (con check-in)'
                                              : 'la versión que PREGUNTA (sin check-in)'}`);

    if (!laLarga) {
        // «El paso 1 se acorta, igual que en el quincenal. El peso y las fotos se le piden
        // igual, que ésos no dependen de haber apuntado nada.»
        const sub = await txt('[data-testid="paso1-sin-datos-sub"]');
        console.log('   ' + sub);
        if (sub === 'Cinco preguntas y pasas al paso 2. El peso y las fotos se te piden igual.')
            bien('el subtítulo, literal');
        else mal('el subtítulo no es el de su maqueta', sub);
        const todo = await txt('[data-testid="mensual-paso1"]');
        if (/No tengo todos los datos de tus check-in diarios/.test(todo || ''))
            bien('el aviso de por qué se lo pregunta');
        else mal('falta el aviso «No tengo todos los datos de tus check-in diarios»');
        for (const q of ['¿En qué grado has cumplido la dieta?',
                         '¿Has entrenado todos los días que tocaba?',
                         '¿Has cumplido con el cardio que tenías pautado?']) {
            if ((todo || '').includes(q)) bien(`pregunta «${q}»`);
            else mal(`falta la pregunta «${q}»`);
        }
        // Las estrellas no llevan la palabra «estrella» en el testid: cada pregunta pone el
        // suyo (`dieta_grado-1` ... `-5`), asi que se cuentan por su etiqueta, «N de 5».
        const estrellas = await p.locator('[data-testid="mensual-paso1"] [aria-label$="de 5"]').count();
        console.log('   estrellas: ' + estrellas);
        const cuantas = await p.locator('[data-testid^="paso1-pregunta-"]').count();
        console.log('   preguntas con estrellas: ' + cuantas);
        if (cuantas >= 3 && estrellas === cuantas * 5)
            bien('cinco estrellas en cada una de las preguntas', `${cuantas} x 5`);
        else mal('las estrellas no cuadran con las preguntas', `${cuantas} preguntas, ${estrellas} estrellas`);
        if (await p.locator('[data-testid="weight-input"]').count()) bien('y el peso se pide igual');
        else mal('no pide el peso, y su documento dice que sí');
    } else {
        console.log('   peso : ' + await txt('[data-testid="paso1-peso"]'));
        console.log('   act  : ' + await txt('[data-testid="paso1-actividad"]'));
        console.log('   sens : ' + await txt('[data-testid="paso1-sensaciones"]'));
        for (const [q, sel] of [['el peso', '[data-testid="paso1-peso"]'],
                                ['lo que ha hecho', '[data-testid="paso1-actividad"]'],
                                ['cómo se ha sentido', '[data-testid="paso1-sensaciones"]']]) {
            if (await p.locator(sel).count()) bien(q); else mal(`falta ${q}`);
        }
        // Las cinco filas de la maqueta, por su nombre.
        for (const f of ['dietas', 'extras', 'entrenos', 'movimiento', 'suplementacion']) {
            if (await p.locator(`[data-testid="paso1-fila-${f}"]`).count()) bien(`fila ${f}`);
            else mal(`falta la fila ${f}`);
        }

        // ── «El selector cambia el BLOQUE ENTERO, no solo el peso» ──
        console.log('\n   Y el selector, que es lo que dice ese apartado');
        const antes = { peso: await txt('[data-testid="paso1-peso"]'),
                        act: await txt('[data-testid="paso1-actividad"]') };
        await p.locator('[data-testid="paso1-periodo-principio"]').click();
        // ESPERA LARGA A PROPOSITO: con 2,5 s el bloque todavia no ha vuelto del servidor y
        // parece que no cambia. Es lo que hacia decir que esto estaba roto y no lo estaba.
        await p.waitForTimeout(5000);
        const despues = { peso: await txt('[data-testid="paso1-peso"]'),
                          act: await txt('[data-testid="paso1-actividad"]') };
        console.log('   act ahora: ' + despues.act);
        console.log('   pedidas: ' + JSON.stringify(pedidas.map((u) => u.split('?')[1])));
        if (pedidas.some((u) => /periodo=principio/.test(u))) bien('el periodo viaja en la petición');
        else mal('la petición no lleva el periodo');
        if (despues.act !== antes.act) bien('la actividad cambia con el periodo');
        else mal('la actividad NO cambia: el selector solo mueve el peso', despues.act);
        if (/EN \d+ DÍAS/.test(despues.act || '')) bien('y el título dice los días del periodo largo');
        else mal('el título sigue siendo el de los 28 días');
        // «Los huecos no cambian: ésos son siempre de los últimos 28.»
        const huecos = await p.locator('[data-testid^="paso1-hueco-"]').count();
        if (huecos) bien('los huecos siguen ahí', `${huecos}`);
        else console.log('   (este mes no hay huecos que preguntar)');
        await p.locator('[data-testid="paso1-periodo-ultimo"]').click();
        await p.waitForTimeout(4000);
    }
    await p.screenshot({ path: `_guia/_mensual_0309_paso1${laLarga ? '' : '_sin_checkin'}.png`, fullPage: true });

    // ───────────────────────────────────────────────────────────────────────
    console.log('\nPaso 2 · Tus sensaciones y tus dudas');
    const seguir = async () => {
        // LOS HUECOS PRIMERO. «Si algo no cuadra o te falta, lo arreglas al final»: mientras
        // queden sin contestar, confirmar no pasa de paso, y desde fuera parece que el botón
        // no hace nada.
        const huecos = await p.evaluate(() => [...new Set([...document.querySelectorAll('[data-testid^="paso1-hueco-"][data-testid*="-op-"]')]
            .map((e) => e.getAttribute('data-testid').split('-op-')[0]))]);
        for (const h of huecos) {
            const op = p.locator(`[data-testid^="${h}-op-"]`).first();
            if (await op.count()) { await op.scrollIntoViewIfNeeded(); await op.click().catch(() => {}); await p.waitForTimeout(500); }
        }
        if (huecos.length) console.log(`   (contestados ${huecos.length} huecos, que si no el paso no avanza)`);
        // Y EL PESO. Confirmar el paso 1 lo exige («El peso es obligatorio», y lo dice en un
        // aviso, no se queda callado). Viniendo por `?ver=` no hay borrador del que sacarlo,
        // asi que se escribe por donde lo escribiria el cliente: «Corrige lo que haga falta».
        if (!(await p.locator('[data-testid="weight-input"]:visible').count())) {
            const abrir = p.locator('[data-testid="paso1-modificar-btn"]').first();
            if (await abrir.count()) { await abrir.scrollIntoViewIfNeeded(); await abrir.click(); await p.waitForTimeout(1200); }
        }
        const campo = p.locator('[data-testid="weight-input"]:visible').first();
        if (await campo.count() && !(await campo.inputValue())) {
            await campo.scrollIntoViewIfNeeded();
            // El campo es \: la coma no entra, y con punto tampoco hace falta.
            await campo.fill('78.2');
            await p.waitForTimeout(600);
            console.log('   (puesto el peso: en modo revisión no viene de ningún borrador)');
        }
        for (const sel of ['[data-testid="paso1-confirmar"]', '[data-testid="paso1-continuar"]',
                           '[data-testid="mensual-siguiente"]']) {
            const b = p.locator(sel).first();
            if (!(await b.count())) continue;
            const apagado = await b.isDisabled().catch(() => false);
            console.log(`   botón ${sel}: ${apagado ? 'APAGADO' : 'encendido'} · «${(await b.innerText()).trim()}»`);
            if (apagado) return false;
            await b.scrollIntoViewIfNeeded();
            await b.click().catch(() => {});
            await p.waitForTimeout(4000);
            return true;
        }
        console.log('   (no encuentro el botón de seguir)');
        return false;
    };
    await seguir();
    console.log('   testids: ' + JSON.stringify((await p.evaluate(() =>
        [...document.querySelectorAll('[data-testid]')].filter((e) => e.offsetParent !== null)
            .map((e) => e.getAttribute('data-testid')))).slice(0, 30)));
    console.log('   quejas: ' + JSON.stringify(quejas.slice(-6)));
    const paso2 = await txt('[data-testid="mensual-rotulo-2"], [data-testid="reporte-mensual"]');
    console.log('   ' + (paso2 || '(sin rótulo)'));
    const cuerpo2 = await txt('main, body');
    if (/objetivo/i.test(cuerpo2 || '')) bien('está el paso 2');
    else mal('no llego al paso 2');
    // «Las dos del centro solo salen si falló.»
    const preguntas = await p.evaluate(() =>
        [...document.querySelectorAll('h3, [data-testid^="pregunta-"]')]
            .map((e) => (e.innerText || '').trim()).filter(Boolean).slice(0, 12));
    console.log('   preguntas: ' + JSON.stringify(preguntas));

    console.log(`\n${fallos ? `${fallos} FALLOS` : 'lo mirado, bien'}`);
    await nav.close();
    process.exit(fallos ? 1 : 0);
})();
