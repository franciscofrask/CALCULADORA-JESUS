/**
 * EL MENSUAL EN CUATRO PASOS (documento «El reporte mensual», 1-09-2026).
 *
 * Recorre el reporte entero en el navegador, en movil, y saca una captura de cada paso:
 *
 *   1  Actualizar tus datos      selector de periodo, peso, lo que ha hecho, sensaciones y huecos
 *   2  Tus sensaciones y dudas   las preguntas de siempre, ya sin numeros de bloque
 *   3  Tus fotos y tus medidas   con el plazo en su aviso y «van a Mi evolucion»
 *
 * Ademas comprueba lo que no se ve en una captura: que el selector de periodo CAMBIA EL
 * BLOQUE ENTERO (no solo el peso) y que los huecos NO cambian al pasar al programa entero,
 * que es lo que dice el documento.
 *
 * NO envia nada: el paso 4 solo sale despues de mandarlo de verdad.
 *
 * Uso:  node _guia/_verificar_mensual_4pasos_0109.js
 */
const fs = require('fs');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
// Se prueba con el CLIENTE, que es quien rellena el reporte. La cuenta del equipo no vale:
// al admin el enrutador lo manda a /admin y nunca llega a Seguimiento.
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const CARPETA = '_guia/_mensual_4pasos';
if (!fs.existsSync(CARPETA)) fs.mkdirSync(CARPETA, { recursive: true });

(async () => {
    const login = await fetch(`${API}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: CUENTA, password: CLAVE }),
    }).then(r => r.json());
    if (!login.access_token) { console.log('no he podido entrar:', login); return; }

    const nav = await chromium.launch();
    const p = await (await nav.newContext({ viewport: { width: 390, height: 1500 },
                                            deviceScaleFactor: 2 })).newPage();
    const errores = [];
    p.on('console', (m) => { if (m.type() === 'error') errores.push(m.text().slice(0, 200)); });
    p.on('pageerror', (e) => errores.push('PAGE: ' + String(e).slice(0, 200)));

    // LA VENTANA DE ENVIO, ABIERTA. El mensual de la cuenta de pruebas esta pendiente pero
    // fuera de plazo (`is_open: false`), y con la ventana cerrada la pantalla no pinta el
    // formulario. Se abre SOLO ese interruptor, que es exactamente lo que hace el modo
    // revision del equipo (`VENTANA_DE_MENTIRA` en ReportsPage). Todo lo demas -- los
    // datos, los huecos, el peso -- sigue viniendo del servidor de verdad.
    await p.route('**/api/reports/due*', async (route) => {
        const r = await route.fetch();
        const j = await r.json().catch(() => null);
        if (!j || !j.window) return route.fulfill({ response: r });
        j.window = { ...j.window, due: true, is_open: true, submitted: false };
        return route.fulfill({ response: r, json: j });
    });

    await p.goto(APP, { waitUntil: 'domcontentloaded' });
    await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); },
                     login.access_token);
    // Se entra por Inicio y SOLO DESPUES a Seguimiento. Yendo directo a /reports el
    // enrutador todavia no tiene la sesion montada y rebota a /dashboard.
    await p.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
    await p.waitForTimeout(12000);
    for (let i = 0; i < 4; i++) {
        const s = p.locator('[data-testid="recorrido-saltar"]');
        if (!(await s.count())) break;
        await s.click({ force: true }).catch(() => {});
        await p.waitForTimeout(1000);
    }
    await p.goto(`${APP}/dashboard/reports`, { waitUntil: 'networkidle' }).catch(() => {});
    await p.waitForTimeout(6000);
    // Seguimiento abre en su portada; al formulario se entra por «Empezar», que es el
    // camino del cliente.
    const tarjeta = p.locator('[data-testid="seg-revision"]');
    if (await tarjeta.count()) { await tarjeta.click(); await p.waitForTimeout(6000); }
    console.log('estoy en:', p.url());

    const texto = async (sel) => {
        const l = p.locator(sel).first();
        if (!(await l.count())) return null;
        return (await l.innerText()).split('\n').map(s => s.trim()).filter(Boolean).join(' · ');
    };

    // ── PASO 1 ───────────────────────────────────────────────────────────────
    console.log('\n══ PASO 1 · ACTUALIZAR TUS DATOS ══');
    console.log('  cabecera:', await texto('[data-testid="mensual-son-4-pasos"]'));
    console.log('  peso:', await texto('[data-testid="paso1-peso"]'));
    console.log('  actividad:', await texto('[data-testid="paso1-actividad"]'));
    console.log('  sensaciones:', await texto('[data-testid="paso1-sensaciones"]'));
    const huecos1 = await p.locator('[data-testid^="paso1-hueco-"]').count();
    console.log('  huecos:', huecos1, huecos1 ? await texto('[data-testid^="paso1-hueco-"]') : '');
    await p.screenshot({ path: `${CARPETA}/1_paso1.png`, fullPage: true });

    // ── El selector: tiene que cambiar el bloque entero ──────────────────────
    const antes = { peso: await texto('[data-testid="paso1-peso"]'),
                    actividad: await texto('[data-testid="paso1-actividad"]') };
    await p.locator('[data-testid="paso1-periodo-principio"]').click();
    await p.waitForTimeout(2500);
    const despues = { peso: await texto('[data-testid="paso1-peso"]'),
                      actividad: await texto('[data-testid="paso1-actividad"]') };
    console.log('\n══ EL SELECTOR ══');
    console.log('  el peso cambia:      ', antes.peso !== despues.peso ? 'sí' : 'NO');
    console.log('  la actividad cambia: ', antes.actividad !== despues.actividad ? 'sí' : 'NO');
    console.log('  actividad (programa entero):', despues.actividad);
    const huecos2 = await p.locator('[data-testid^="paso1-hueco-"]').count();
    console.log('  los huecos siguen ahí:', huecos2 === huecos1 ? 'sí' : `NO (${huecos1} -> ${huecos2})`);
    await p.screenshot({ path: `${CARPETA}/2_desde_que_empezaste.png`, fullPage: true });
    await p.locator('[data-testid="paso1-periodo-ultimo"]').click();
    await p.waitForTimeout(2000);

    // Contestar los huecos que haya, que si no el reporte va cojo.
    for (const t of ['entreno', 'dieta']) {
        const b = p.locator(`[data-testid="paso1-hueco-${t}-op-si_pero_no_apunte"]`);
        if (await b.count()) { await b.click(); await p.waitForTimeout(300); }
    }

    // El peso. Esta cuenta no tiene peso de la semana calculado, asi que el paso 1 abre el
    // campo solo (que es justo lo que se queria comprobar) y hay que escribirlo.
    const campoPeso = p.locator('[data-testid="weight-input"]');
    console.log('  el campo del peso sale abierto:', await campoPeso.count() ? 'sí' : 'NO');
    if (await campoPeso.count()) await campoPeso.fill('80');

    // ── PASO 2 ───────────────────────────────────────────────────────────────
    await p.locator('[data-testid="paso1-confirmar"]').click();
    await p.waitForTimeout(2500);
    console.log('\n══ PASO 2 · TUS SENSACIONES Y TUS DUDAS ══');
    console.log('  está:', await p.locator('[data-testid="reporte-mensual"]').count() ? 'sí' : 'NO');
    console.log('  bloques:', (await p.locator('[data-testid^="mensual-"]').count()));
    await p.screenshot({ path: `${CARPETA}/3_paso2.png`, fullPage: true });

    // ── PASO 3 ───────────────────────────────────────────────────────────────
    await p.locator('[data-testid="mensual-siguiente"]').click();
    await p.waitForTimeout(2000);
    console.log('\n══ PASO 3 · TUS FOTOS Y TUS MEDIDAS ══');
    console.log('  está:', await p.locator('[data-testid="mensual-paso3"]').count() ? 'sí' : 'NO');
    console.log('  plazo:', await texto('[data-testid="paso3-plazo"]'));
    console.log('  mi evolución:', await texto('[data-testid="paso3-mi-evolucion"]'));
    console.log('  medidas:', await p.locator('[data-testid^="medida-"]').count(), 'casillas');
    await p.screenshot({ path: `${CARPETA}/4_paso3.png`, fullPage: true });

    // Y que el botón de enviar avisa de las medidas que faltan en vez de mandarlo a medias.
    await p.locator('[data-testid="revisar-y-enviar"]').click();
    await p.waitForTimeout(1200);
    const aviso = await p.locator('[data-role="status"], li[data-sonner-toast]').first();
    console.log('  al enviar sin medidas:', (await aviso.count()) ? (await aviso.innerText()).replace(/\n/g, ' ') : '(sin aviso)');

    console.log('\nerrores de consola:', errores.length ? errores.slice(0, 5) : 'ninguno');
    console.log(`capturas en ${CARPETA}/`);
    await nav.close();
})();
