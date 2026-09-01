/**
 * PASO 4 DEL MENSUAL · TU PLAN NUEVO Y MI FEEDBACK DIRECTO (documento del 1-09-2026).
 *
 * Comprueba las dos caras del paso 4, que son distintas por una razon de fondo:
 *
 *   A) CON EL INFORME PUBLICADO   sale «YA LO TIENES · Tu informe del mes» y el boton.
 *   B) SIN PUBLICAR               esa tarjeta NO sale. El documento lo da por entregado
 *      al momento («Te lo entrego ya»), pero desde T9 (doc 16-08) el informe no le llega
 *      al cliente hasta que Jesus lo revisa. Decirle «ya lo tienes» sin nada que pulsar
 *      seria prometerle media cosa.
 *
 * NO ESCRIBE NADA EN LA BASE. El envio se responde desde aqui, asi que la cuenta de
 * pruebas se queda igual que estaba: no se le crea un reporte ni se le cierra la ventana.
 *
 * Uso:  node _guia/_verificar_mensual_paso4_0109.js
 */
const fs = require('fs');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const CARPETA = '_guia/_mensual_4pasos';
if (!fs.existsSync(CARPETA)) fs.mkdirSync(CARPETA, { recursive: true });

const MEDIDAS = ['hombros', 'mesoesternal', 'brazo_d', 'brazo_i', 'muslo_d', 'muslo_i',
                 'cadera', 'cintura', 'gemelo_d', 'gemelo_i'];

async function recorrer(conInforme) {
    const login = await fetch(`${API}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: CUENTA, password: CLAVE }),
    }).then(r => r.json());
    if (!login.access_token) { console.log('no he podido entrar'); return; }

    const nav = await chromium.launch();
    const p = await (await nav.newContext({ viewport: { width: 390, height: 1500 },
                                            deviceScaleFactor: 2 })).newPage();
    const errores = [];
    p.on('console', (m) => { if (m.type() === 'error') errores.push(m.text().slice(0, 200)); });
    p.on('pageerror', (e) => errores.push('PAGE: ' + String(e).slice(0, 200)));

    // La ventana de envio, abierta (lo mismo que hace el modo revision del equipo).
    await p.route('**/api/reports/due*', async (route) => {
        const r = await route.fetch();
        const j = await r.json().catch(() => null);
        if (!j || !j.window) return route.fulfill({ response: r });
        j.window = { ...j.window, due: true, is_open: true, submitted: false };
        return route.fulfill({ response: r, json: j });
    });

    let loQueMando = null;
    // El envio NO llega al servidor: se contesta aqui. Asi se ve el paso 4 sin dejarle un
    // reporte a la cuenta de pruebas, y de paso se puede leer lo que iba a mandar.
    await p.route('**/api/reports', async (route) => {
        if (route.request().method() !== 'POST') return route.continue();
        loQueMando = route.request().postDataJSON();
        return route.fulfill({ status: 200, json: {
            id: 'reporte-de-mentira', tipo: 'mensual', weight: 80,
            mensaje_envio: 'Antes del sábado tienes tu informe completo con mi feedback y tus ajustes. Te aviso por aquí.',
            promesa_dia: 'sábado',
        } });
    });
    await p.route('**/api/reports/reporte-de-mentira/informe', (route) => (
        conInforme ? route.fulfill({ status: 200, json: { generado: true } })
                   : route.fulfill({ status: 403, json: { detail: 'pendiente de revision' } })));

    await p.goto(APP, { waitUntil: 'domcontentloaded' });
    await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); },
                     login.access_token);
    await p.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
    await p.waitForTimeout(11000);
    for (let i = 0; i < 4; i++) {
        const s = p.locator('[data-testid="recorrido-saltar"]');
        if (!(await s.count())) break;
        await s.click({ force: true }).catch(() => {});
        await p.waitForTimeout(900);
    }
    await p.goto(`${APP}/dashboard/reports`, { waitUntil: 'networkidle' }).catch(() => {});
    await p.waitForTimeout(5000);
    const tarjeta = p.locator('[data-testid="seg-revision"]');
    if (await tarjeta.count()) { await tarjeta.click(); await p.waitForTimeout(6000); }

    if (!(await p.locator('[data-testid="paso1-confirmar"]').count())) {
        await p.screenshot({ path: `${CARPETA}/x_donde_estoy.png`, fullPage: true });
        console.log('no he llegado al paso 1; estoy en', p.url());
        await nav.close();
        return;
    }

    // Paso 1: el peso y los huecos.
    const campoPeso = p.locator('[data-testid="weight-input"]');
    if (await campoPeso.count()) await campoPeso.fill('80');
    for (const t of ['entreno', 'dieta']) {
        const b = p.locator(`[data-testid="paso1-hueco-${t}-op-no_lo_hice"]`);
        if (await b.count()) { await b.click(); await p.waitForTimeout(200); }
    }
    await p.locator('[data-testid="paso1-confirmar"]').click();
    await p.waitForTimeout(2500);

    // Paso 2: las preguntas nuevas del documento.
    await p.locator('[data-testid="dieta-dificultad-me_cuesta"]').click().catch(() => {});
    const maquinas = p.locator('[data-testid="maquinas-anadir"]');
    if (await maquinas.count()) {
        await maquinas.click();
        await p.locator('[data-testid="maquinas-input"]').fill('Prensa horizontal');
        await p.keyboard.press('Enter');
    }
    await p.locator('[data-testid="compromiso-bastante_bien"]').click().catch(() => {});
    await p.locator('[data-testid="expectativas-8"]').click().catch(() => {});
    await p.locator('[data-testid="objetivo-cambio-no"]').click().catch(() => {});
    await p.waitForTimeout(400);
    await p.locator('[data-testid="mensual-siguiente"]').click();
    await p.waitForTimeout(2000);

    // Paso 3: las diez medidas y a enviar.
    for (const m of MEDIDAS) {
        const c = p.locator(`[data-testid="medida-${m}"]`);
        if (await c.count()) await c.fill('100');
    }
    await p.locator('[data-testid="revisar-y-enviar"]').click();
    await p.waitForTimeout(2500);

    // El resumen, y de ahi al envio.
    const resumen = p.locator('[data-testid="rev-compromiso"], [data-testid="rev-maquinas"]');
    console.log(`\n══ RESUMEN (informe ${conInforme ? 'publicado' : 'pendiente'}) ══`);
    console.log('  compromiso:', await p.locator('[data-testid="rev-compromiso"]').innerText().catch(() => '(no está)'));
    console.log('  expectativas:', await p.locator('[data-testid="rev-expectativas"]').innerText().catch(() => '(no está)'));
    console.log('  máquinas:', await p.locator('[data-testid="rev-maquinas"]').innerText().catch(() => '(no está)'));
    if (!(await resumen.count())) await p.screenshot({ path: `${CARPETA}/x_resumen.png`, fullPage: true });
    const enviar = p.locator('[data-testid="confirmar-envio"], button:has-text("Enviar")').last();
    await enviar.click();
    await p.waitForTimeout(3000);

    console.log('  lo que iba a mandar:', loQueMando ? JSON.stringify({
        compromiso: loQueMando.compromiso, expectativas: loQueMando.expectativas,
        maquinas: loQueMando.maquinas_no_disponibles,
        dieta_dificultad: loQueMando.dieta_dificultad,
        viabilidad_ajuste: loQueMando.viabilidad_ajuste,
        huecos: loQueMando.huecos, proximo_objetivo: loQueMando.proximo_objetivo,
    }) : '(no llegó a enviar)');

    console.log('\n══ PASO 4 ══');
    console.log('  está:', await p.locator('[data-testid="mensual-paso4"]').count() ? 'sí' : 'NO');
    console.log('  tarjeta del informe:', await p.locator('[data-testid="paso4-informe"]').count() ? 'sí' : 'no');
    console.log('  botón «Ver mi informe»:', await p.locator('[data-testid="paso4-ver-informe"]').count() ? 'sí' : 'no');
    const prog = p.locator('[data-testid="paso4-programa"]');
    console.log('  programa:', await prog.count()
        ? (await prog.innerText()).split('\n').map(s => s.trim()).filter(Boolean).join(' · ') : '(no está)');
    await p.screenshot({ path: `${CARPETA}/5_paso4_${conInforme ? 'con' : 'sin'}_informe.png`, fullPage: true });

    if (errores.length) console.log('  errores de consola:', errores.slice(0, 4));
    await nav.close();
}

(async () => {
    await recorrer(true);
    await recorrer(false);
    console.log(`\ncapturas en ${CARPETA}/`);
})();
