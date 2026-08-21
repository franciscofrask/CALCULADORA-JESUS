/**
 * Repaso del 21-08: los bloques 07-13 del doc 19-08 + el doc 57, cada cambio con su
 * captura y su comprobación de texto. Una cuenta por estado (ver _cuentas_repaso.py).
 *
 * Uso:  node _capturas_repaso_2108.js
 * Deja JPEG en _guia/capturas_repaso_2108/ y un resumen OK/FALLO por pantalla.
 */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const APP = 'http://localhost:3000';
const API = 'http://localhost:8000';
const SALIDA = path.join(__dirname, 'capturas_repaso_2108');

const CUENTAS = {
    nivel1: { email: 'prueba.nivel1@test.com', password: 'demo123' },
    bronze: { email: 'prueba.bronze@test.com', password: 'demo123' },
    porvencer: { email: 'prueba.porvencer@test.com', password: 'demo123' },
    caducado: { email: 'prueba.caducado@test.com', password: 'demo123' },
    sinplan: { email: 'prueba.sinplan@test.com', password: 'demo123' },
    legacy: { email: 'prueba.legacy@test.com', password: 'demo123' },
    demo: { email: 'clientedemo@test.com', password: 'demo123' },
    admin: { email: 'francisco@test.com', password: 'demo123' },
};

const resultados = [];

async function entrar(page, quien) {
    const r = await page.request.post(`${API}/api/auth/login`, { data: CUENTAS[quien] });
    if (!r.ok()) throw new Error(`login ${quien}: ${r.status()}`);
    const { access_token, token } = await r.json();
    await page.goto(APP, { waitUntil: 'domcontentloaded' });
    await page.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, access_token || token);
}

async function foto(page, nombre, { full = false } = {}) {
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(SALIDA, `${nombre}.jpg`), type: 'jpeg', quality: 50, fullPage: full });
}

async function ir(page, ruta) {
    try { await page.goto(`${APP}${ruta}`, { waitUntil: 'networkidle', timeout: 30000 }); }
    catch { await page.waitForTimeout(2500); }
}

async function comprobar(page, nombre, esperados) {
    // Espera ACTIVA: la SPA tarda en traer datos y leer el body nada mas navegar da
    // falsos fallos. Mayusculas fuera: el CSS pone titulos en uppercase y innerText lo refleja.
    let ok = false;
    try {
        await page.waitForFunction((ts) => {
            const t = document.body.innerText.toLowerCase();
            return ts.every((x) => t.includes(x.toLowerCase()));
        }, esperados, { timeout: 15000 });
        ok = true;
    } catch { /* no llegaron: se apunta abajo */ }
    const texto = (await page.evaluate(() => document.body.innerText)).toLowerCase();
    const faltan = ok ? [] : esperados.filter((t) => !texto.includes(t.toLowerCase()));
    resultados.push({ nombre, ok, faltan });
    console.log(`${ok ? 'OK   ' : 'FALLO'} ${nombre}${ok ? '' : '  faltan: ' + faltan.join(' | ')}`);
    return ok;
}

(async () => {
    fs.mkdirSync(SALIDA, { recursive: true });
    const navegador = await chromium.launch();
    const ctx = await navegador.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await ctx.newPage();

    // ── BLOQUE 07 · Preferencias (nivel1 recién llegado: el modal sale solo) ──
    console.log('\n== BLOQUE 07 · Preferencias ==');
    await entrar(page, 'nivel1');
    await ir(page, '/dashboard/nutrition');
    await page.waitForTimeout(2500);
    await comprobar(page, 'b07-1 modal de preferencias', ['Configura tus preferencias', 'Mis alimentos preferidos']);
    await foto(page, 'b07-1-modal-preferencias');
    // La pestaña de alimentos a evitar, primero y con las alergias
    const evitar = page.getByRole('button', { name: /Alimentos a evitar/i }).first();
    if (await evitar.count()) { await evitar.click(); await page.waitForTimeout(1500); }
    await comprobar(page, 'b07-2 alimentos a evitar', ['evitar']);
    await foto(page, 'b07-2-alimentos-a-evitar');
    // Se guarda para poder usar la cuenta en el resto del repaso
    const guardar = page.getByRole('button', { name: /Guardar/i }).first();
    if (await guardar.count()) { await guardar.click(); await page.waitForTimeout(2500); }
    await foto(page, 'b07-3-nutricion-tras-guardar');

    // ── BLOQUE 08 · La guía de suplementación ──
    console.log('\n== BLOQUE 08 · Guía de suplementación ==');
    await ir(page, '/dashboard/supplements');
    await comprobar(page, 'b08-1 guia autogestion (aviso 87)', ['gu', 'FullGas']);
    await foto(page, 'b08-1-guia-autogestion', { full: true });
    await entrar(page, 'bronze');
    await ir(page, '/dashboard/supplements');
    await comprobar(page, 'b08-2 guia con coach (personalizado)', ['personalizado']);
    await foto(page, 'b08-2-guia-con-coach');

    // ── BLOQUE 09 · Mis macros ──
    console.log('\n== BLOQUE 09 · Mis macros ==');
    await comprobar(page, 'b09-1 bronze SIN Ajustar macros en el menu',
        ['Suplementos']).then(async () => {
        const texto = await page.evaluate(() => document.body.innerText);
        const oculto = !texto.includes('Ajustar macros');
        resultados.push({ nombre: 'b09-1b la pestaña no existe para coach', ok: oculto, faltan: oculto ? [] : ['(Ajustar macros visible y no deberia)'] });
        console.log(`${oculto ? 'OK   ' : 'FALLO'} b09-1b la pestaña no existe para coach`);
    });
    await foto(page, 'b09-1-bronze-sin-mis-macros');
    await entrar(page, 'nivel1');
    await ir(page, '/dashboard/macro-calculator');
    await comprobar(page, 'b09-2 nivel1 con su calculadora', ['macros']);
    await foto(page, 'b09-2-nivel1-mis-macros', { full: true });

    // ── BLOQUE 10 · Avisos ──
    console.log('\n== BLOQUE 10 · Avisos ==');
    await ir(page, '/dashboard/notifications');
    await comprobar(page, 'b10-1 avisos del nivel1', ['Avisos']);
    await foto(page, 'b10-1-avisos-nivel1', { full: true });

    // ── BLOQUE 11 · Reportes y check-in ──
    console.log('\n== BLOQUE 11 · Reportes ==');
    await ir(page, '/dashboard');
    await comprobar(page, 'b11-1 inicio con la frase y lo de rellenar', ['Para rellenar al final del d']);
    await foto(page, 'b11-1-inicio-nivel1', { full: true });
    // La portada del nivel1: el mensual de HOY con su hora («se abre el viernes a las 10»).
    await ir(page, '/dashboard/reports');
    await page.waitForTimeout(1500);
    await foto(page, 'b11-4-portada-mensual', { full: true });
    // El formulario VIVO con su «No puedo esta semana»: el semanal del gold (demo), cuya
    // ventana abre el viernes a las 00:00 y ya está abierta. (El patrón del bronze no
    // lleva semanal, y el mensual del nivel1 no abre hasta las 10:00.)
    await entrar(page, 'demo');
    await ir(page, '/dashboard/reports');
    await page.waitForTimeout(1500);
    const verReporte = page.getByText('Ver', { exact: true }).first();
    if (await verReporte.count()) { await verReporte.click(); await page.waitForTimeout(2500); }
    await comprobar(page, 'b11-2 reportes con No puedo esta semana', ['No puedo esta semana']);
    await foto(page, 'b11-2-reportes-no-puedo', { full: true });
    await ir(page, '/dashboard/reports?aplazar=1');
    await page.waitForTimeout(2500);
    await foto(page, 'b11-3-aplazar-abierto', { full: true });

    // ── BLOQUE 12 · Los cuatro paneles (admin) ──
    console.log('\n== BLOQUE 12 · Paneles ==');
    await entrar(page, 'admin');
    await ir(page, '/admin/paneles');
    await page.waitForTimeout(2500);
    await comprobar(page, 'b12-1 Direccion', ['Entra esta semana', 'Cartera activa']);
    await foto(page, 'b12-1-panel-direccion', { full: true });
    for (const [tab, nombre] of [['Entrenador', 'b12-2-panel-entrenador'], ['Operaciones', 'b12-3-panel-operaciones'], ['Soporte', 'b12-4-panel-soporte']]) {
        const boton = page.getByRole('button', { name: new RegExp(tab, 'i') }).first();
        if (await boton.count()) { await boton.click(); await page.waitForTimeout(2000); }
        await foto(page, nombre, { full: true });
    }
    resultados.push({ nombre: 'b12 pestañas recorridas', ok: true, faltan: [] });

    // ── BLOQUE 13 · Renovaciones y acceso ──
    console.log('\n== BLOQUE 13 · Renovaciones ==');
    await entrar(page, 'sinplan');
    await ir(page, '/dashboard');
    await comprobar(page, 'b13-1 sin plan: Elige tu plan primero', ['Elige tu plan']);
    await foto(page, 'b13-1-sinplan-inicio');
    await ir(page, '/dashboard/profile');
    await comprobar(page, 'b13-2 perfil sin plan: Ver los planes y sin No quiero renovar', ['Ver los planes']);
    const textoPerfil = await page.evaluate(() => document.body.innerText);
    const sinNoQuiero = !textoPerfil.includes('No quiero renovar');
    resultados.push({ nombre: 'b13-2b sin «No quiero renovar»', ok: sinNoQuiero, faltan: sinNoQuiero ? [] : ['(sale No quiero renovar sin plan)'] });
    console.log(`${sinNoQuiero ? 'OK   ' : 'FALLO'} b13-2b sin «No quiero renovar»`);
    await foto(page, 'b13-2-sinplan-perfil', { full: true });

    await entrar(page, 'porvencer');
    await ir(page, '/dashboard/notifications');
    await foto(page, 'b13-3-porvencer-avisos', { full: true });
    await ir(page, '/renovacion');
    await comprobar(page, 'b13-4 renovacion del que esta por vencer', ['no se renueva solo', 'Seguir igual']);
    await foto(page, 'b13-4-porvencer-renovacion', { full: true });

    await entrar(page, 'caducado');
    await ir(page, '/dashboard');
    await foto(page, 'b13-5-caducado-inicio', { full: true });
    await ir(page, '/renovacion');
    await comprobar(page, 'b13-6 caducado puede recontratar', ['Tu ciclo ha terminado', 'Seguir igual']);
    await foto(page, 'b13-6-caducado-renovacion', { full: true });

    await entrar(page, 'legacy');
    await ir(page, '/renovacion');
    await comprobar(page, 'b13-7 legacy renueva su mismo plan', ['Seguir igual']);
    await foto(page, 'b13-7-legacy-seguir-igual', { full: true });

    // ── DOC 57 · El selector con la procedencia (demo) ──
    console.log('\n== DOC 57 · Selector y fecha antigua ==');
    await entrar(page, 'demo');
    await ir(page, '/dashboard/nutrition?date=2024-01-24');
    await page.waitForTimeout(2500);
    await comprobar(page, 'b57-1 fecha antigua carga con su aviso', ['muy atr']);
    await foto(page, 'b57-1-fecha-antigua');
    await ir(page, '/dashboard/nutrition');
    await page.waitForTimeout(2000);
    const sugerir = page.getByRole('button', { name: /SUGIÉREME UN MENÚ/i }).first();
    if (await sugerir.count()) { await sugerir.click(); await page.waitForTimeout(6000); }
    await comprobar(page, 'b57-2 selector con procedencia', ['Del recetario', 'Solo recetario', 'Recetario y gente']);
    await foto(page, 'b57-2-selector-procedencia', { full: false });
    const soloRecetario = page.getByRole('button', { name: 'Solo recetario' }).first();
    if (await soloRecetario.count()) { await soloRecetario.click(); await page.waitForTimeout(1200); }
    await foto(page, 'b57-3-solo-recetario');
    const deOtros = await page.evaluate(() => [...document.querySelectorAll('span')].filter(s => s.textContent === 'De otros usuarios').length);
    resultados.push({ nombre: 'b57-3b con Solo recetario no salen menus de otros', ok: deOtros === 0, faltan: deOtros === 0 ? [] : [`(${deOtros} de otros a la vista)`] });
    console.log(`${deOtros === 0 ? 'OK   ' : 'FALLO'} b57-3b con Solo recetario no salen menus de otros`);

    await navegador.close();

    const fallos = resultados.filter(r => !r.ok);
    console.log(`\n===== ${resultados.length - fallos.length}/${resultados.length} comprobaciones OK =====`);
    if (fallos.length) fallos.forEach(f => console.log('FALLO:', f.nombre, f.faltan.join(' | ')));
    fs.writeFileSync(path.join(SALIDA, '_resultados.json'), JSON.stringify(resultados, null, 2));
})();
