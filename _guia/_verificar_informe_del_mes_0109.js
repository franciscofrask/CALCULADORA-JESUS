/**
 * EL INFORME DEL MES, en el navegador (documento del 1-09-2026).
 *
 * Pinta los diez bloques con un informe DE VERDAD -- el que monta `_probar_informe_del_mes.py`
 * contra la base de dev, con 1.278 dias de dietas -- y saca una captura de cada estado:
 *
 *   A) el hueco del feedback en gris, que es como le llega al enviar,
 *   B) el mismo informe con el bloque de Jesus arriba, que es como queda al contestarle.
 *
 * NO ESCRIBE NADA. El listado de reportes y el informe se responden aqui, asi que a la
 * cuenta de pruebas no se le crea ningun reporte ni se le toca el suyo.
 *
 * ANTES HAY QUE GENERAR EL EJEMPLO, que no se guarda en el repositorio porque son las
 * comidas de un cliente de verdad:
 *
 *     cd backend && ./venv/Scripts/python.exe _probar_informe_del_mes.py
 *
 * Uso:  node _guia/_verificar_informe_del_mes_0109.js
 */
const fs = require('fs');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const CARPETA = '_guia/_informe_del_mes';
if (!fs.existsSync(CARPETA)) fs.mkdirSync(CARPETA, { recursive: true });

const BASE = JSON.parse(fs.readFileSync('_guia/_informe_del_mes_ejemplo.json', 'utf8'));
const ID = 'informe-de-prueba';

/** El mismo informe, contestado: es lo que dice el documento («es este, completado»). */
const conFeedback = (informe) => {
    const c = JSON.parse(JSON.stringify(informe));
    c.bloques.feedback = {
        pendiente: false,
        texto: 'Has bajado 2,8 kg cumpliendo 22 de 28 días. El descanso te ha caído y ahí '
             + 'está el hambre que me cuentas. Te subo los hidratos del perientreno y te '
             + 'bajo el cardio a dos sesiones.',
        firma: 'Jesús Gallego', iniciales: 'JG', fecha_label: '5 de septiembre',
    };
    // Y con medidas, que la cuenta de dev no tiene ninguna y ese bloque no se veria.
    c.bloques.medidas = {
        hay: true, hay_mes: true, hay_primera: true,
        filas: [
            ['cuello', 'Cuello', -1, -1], ['mesoesternal', 'Mesoesternal', -1, 3],
            ['brazo_d', 'Brazo derecho relajado', 0, 1], ['cintura', 'Cintura', -2, -6],
            ['muslo_i', 'Muslo izquierdo', -2, -3], ['gemelo_d', 'Gemelo derecho', 0, 0],
        ].map(([clave, etiqueta, mes, primera]) => ({
            clave, etiqueta, valor: 100,
            mes: { dif: mes, label: `${mes > 0 ? '+' : mes < 0 ? '−' : ''}${Math.abs(mes)}`,
                   color: mes === 0 ? 'gris' : mes < 0 ? 'verde' : 'rojo' },
            primera: { dif: primera, label: `${primera > 0 ? '+' : primera < 0 ? '−' : ''}${Math.abs(primera)}`,
                       color: primera === 0 ? 'gris' : primera < 0 ? 'verde' : 'rojo' },
        })),
    };
    return c;
};

async function ver(informe, nombre) {
    const login = await fetch(`${API}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: CUENTA, password: CLAVE }),
    }).then(r => r.json());
    if (!login.access_token) { console.log('no he podido entrar'); return; }

    const nav = await chromium.launch();
    const p = await (await nav.newContext({ viewport: { width: 390, height: 1600 },
                                            deviceScaleFactor: 2 })).newPage();
    const errores = [];
    p.on('console', (m) => { if (m.type() === 'error') errores.push(m.text().slice(0, 200)); });
    p.on('pageerror', (e) => errores.push('PAGE: ' + String(e).slice(0, 200)));

    // Un reporte en el historial, y su informe. Los dos de mentira: nada llega al servidor.
    await p.route('**/api/reports', (route) => (
        route.request().method() === 'GET'
            ? route.fulfill({ status: 200, json: [{
                id: ID, tipo: 'mensual', weight: 78.4,
                created_at: '2026-08-25T12:00:00+00:00', informe_estado: 'entregado',
              }] })
            : route.continue()));
    await p.route(`**/api/reports/${ID}/informe`, (route) =>
        route.fulfill({ status: 200, json: informe }));

    // Las fotos: la cuenta de pruebas no tiene ninguna, y sin ellas el bloque 6 no sale
    // (que es lo correcto). Se responden aqui para poder comprobar las pestañas de pose y
    // los dos selectores de fecha, que es lo unico que el cliente puede tocar del informe.
    const POSES = ['frente', 'espaldas', 'perfil'];
    const FECHAS = ['2026-06-04', '2026-07-02', '2026-08-04', '2026-08-25'];
    await p.route('**/api/reports/photos', (route) => (
        route.request().method() === 'GET'
            ? route.fulfill({ status: 200, json: { photos: POSES.flatMap(
                (pose) => FECHAS.map((f) => ({ id: `${pose}-${f}`, pose, taken_at: f }))) } })
            : route.continue()));
    // El binario: un pixel gris, que aqui lo que se prueba es el selector, no la foto.
    await p.route('**/api/reports/photos/*', (route) => route.fulfill({
        status: 200, contentType: 'image/gif',
        body: Buffer.from('R0lGODlhAQABAIAAAMLCwgAAACH5BAAAAAAALAAAAAABAAEAAAICRAEAOw==', 'base64'),
    }));

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

    // Seguimiento -> Reportes -> «Ver mi informe del mes»
    const historial = p.locator('[data-testid="seg-historial"]');
    if (await historial.count()) { await historial.click(); await p.waitForTimeout(2500); }
    const abrir = p.locator(`[data-testid="ver-informe-${ID}"]`);
    if (await abrir.count()) { await abrir.click(); await p.waitForTimeout(4000); }

    const texto = async (sel) => {
        const l = p.locator(sel).first();
        if (!(await l.count())) return null;
        return (await l.innerText()).split('\n').map(s => s.trim()).filter(Boolean).join(' · ');
    };

    console.log(`\n══ ${nombre.toUpperCase()} ══`);
    console.log('  está el informe nuevo:', await p.locator('[data-testid="informe-del-mes"]').count() ? 'sí' : 'NO');
    for (const [clave, sel] of [
        ['1 dónde estás', '[data-testid="informe-donde-estas"]'],
        ['2 feedback', '[data-testid="informe-feedback"], [data-testid="informe-feedback-pendiente"]'],
        ['3 peso', '[data-testid="informe-peso"]'],
        ['4 medidas', '[data-testid="informe-medidas"]'],
        ['5 grasa', '[data-testid="informe-grasa"]'],
        ['6 fotos', '[data-testid="informe-fotos"]'],
        ['7 lo que has hecho', '[data-testid="informe-hecho"]'],
        ['8 día tipo', '[data-testid="informe-dia-tipo"]'],
        ['9 preferencias', '[data-testid="informe-preferencias"]'],
        ['10 extras', '[data-testid="informe-extras"]'],
    ]) {
        const t = await texto(sel);
        console.log(`  ${clave}:`, t ? t.slice(0, 150) : '(no sale)');
    }
    await p.screenshot({ path: `${CARPETA}/${nombre}.png`, fullPage: true });
    if (errores.length) console.log('  errores de consola:', errores.slice(0, 4));
    await nav.close();
}

(async () => {
    await ver(BASE, '1_al_enviarlo');
    await ver(conFeedback(BASE), '2_cuando_le_contestas');
    console.log(`\ncapturas en ${CARPETA}/`);
})();
