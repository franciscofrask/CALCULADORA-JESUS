/**
 * LAS 32 PANTALLAS DE LOS TRES DOCUMENTOS, capturadas de la app de verdad.
 *
 * Lee `_puntos_todos.json` -- los 113 puntos, cada uno con las frases que TIENEN QUE VERSE
 * y la pantalla donde hay que ir -- abre cada pantalla una vez, guarda lo que se ve y
 * recorta la tarjeta de cada frase.
 *
 * TRES REGLAS DEL METODO, que ya mordieron:
 *   1. Se compara sin distinguir mayusculas: `innerText` devuelve el texto YA transformado
 *      por el CSS, y un titulo con `uppercase` sale a gritos.
 *   2. El recorte coge el PRIMER elemento con la frase, no el ultimo: con el ultimo, las
 *      preguntas del cierre recortaban el resumen de abajo, que las nombra todas.
 *   3. `getByText` con `exact: false`: la frase casi siempre es un trozo de un parrafo.
 *
 * Y una cuarta: cuando hay que FORZAR un estado se dice cual y por que. Lo que se fuerza es
 * el estado de partida, nunca el texto que se comprueba -- si el guion escribiera la frase
 * que luego busca, la prueba no valdria nada.
 *
 * Uso:  node _guia/_capturar_todo.js [escena]
 */
const fs = require('fs');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const CARPETA = '_guia/_capturas';
const DIA_CON_DIETA = '2026-08-30';
if (!fs.existsSync(CARPETA)) fs.mkdirSync(CARPETA, { recursive: true });

const PUNTOS = JSON.parse(fs.readFileSync('_guia/_puntos_todos.json', 'utf8'));

// ── Ayudas para conducir la app ─────────────────────────────────────────────
const pulsar = async (p, texto, espera = 2500) => {
    const b = p.getByText(texto, { exact: false }).first();
    if (await b.count()) { await b.click({ force: true }).catch(() => {}); await p.waitForTimeout(espera); }
};
const abrirSeguimiento = async (p, cual) => {
    await p.goto(`${APP}/dashboard/reports`, { waitUntil: 'networkidle' }).catch(() => {});
    await p.waitForTimeout(5000);
    const t = p.locator(`[data-testid="${cual}"]`);
    if (await t.count()) { await t.click().catch(() => {}); await p.waitForTimeout(5000); }
};
/** La ventana del reporte, abierta. Es lo mismo que hace el modo revision del equipo. */
const ventanaAbierta = (tipo) => ['**/api/reports/due*', async (route) => {
    const r = await route.fetch();
    const j = await r.json().catch(() => null);
    if (!j || !j.window) return route.fulfill({ response: r });
    j.window = { ...j.window, due: true, is_open: true, submitted: false,
                 tipos: [tipo], tipo_label: `Reporte ${tipo}` };
    return route.fulfill({ response: r, json: j });
}];

const ESCENAS = {
    inicio: { ruta: '/dashboard', espera: 12000 },

    'inicio-extras-abierto': {
        ruta: '/dashboard', espera: 12000,
        antes: async (p) => { await pulsar(p, 'Extras del día', 1200);
                              await p.locator('button:near(:text("Extras del día"))').first()
                                  .click({ force: true }).catch(() => {});
                              await p.waitForTimeout(2000); },
    },
    'inicio-extras-puestos': {
        ruta: '/dashboard', espera: 12000,
        forzada: 'El día de la cuenta de pruebas se responde con dos extras dentro. Son los '
               + 'del documento; lo que se comprueba es que la pantalla los pinta y los suma.',
        rutas: [['**/api/diets/2026-**', async (route) => {
            const r = await route.fetch();
            const j = await r.json().catch(() => null);
            if (!j) return route.fulfill({ response: r });
            j.extras = [
                { id: 'x1', texto: 'Dos onzas de chocolate negro 85 %', fecha: j.fecha,
                  cantidad_g: 20, macros: { P: 2, H: 4, G: 9 } },
                { id: 'x2', texto: 'Una caña', fecha: j.fecha, cantidad_g: 330,
                  macros: { P: 0, H: 13, G: 0 } },
            ];
            return route.fulfill({ response: r, json: j });
        }]],
    },
    'inicio-con-reporte': { ruta: '/dashboard', espera: 12000,
        forzada: 'La ventana del quincenal, abierta.', rutas: [ventanaAbierta('quincenal')] },

    ...Object.fromEntries([
        ['inicio-ayer-sin-cerrar', { dias_sin_cerrar: 1, es_de_ayer: true }],
        ['inicio-dos-dias', { dias_sin_cerrar: 2, es_de_ayer: false }],
        ['inicio-cuatro-dias', { dias_sin_cerrar: 4, es_de_ayer: false }],
        ['inicio-una-semana', { dias_sin_cerrar: 7, es_de_ayer: false }],
    ].map(([id, estado]) => [id, {
        ruta: '/dashboard', espera: 12000,
        forzada: `Se le dice al servidor que lleva ${estado.dias_sin_cerrar} día(s) sin `
               + 'cerrar. LA FRASE LA ESCRIBE EL SERVIDOR, no este guion: aquí solo se '
               + 'cambia el número de días para que componga la que toca.',
        rutas: [['**/api/checkins/estado*', async (route) => {
            const r = await route.fetch();
            const j = await r.json().catch(() => null);
            if (!j) return route.fulfill({ response: r });
            return route.fulfill({ response: r, json: {
                ...j, hecho: false, quiere_cierre: true, ...estado } });
        }]],
    }])),

    nutricion: { ruta: `/dashboard/nutrition?date=${DIA_CON_DIETA}`, espera: 15000 },
    'nutricion-comida': {
        ruta: `/dashboard/nutrition?date=${DIA_CON_DIETA}&comida=C1`, espera: 15000,
        antes: async (p) => {
            for (const s of ['[data-testid="meal-select-C1"]', '[data-testid="meal-tab-C1"]']) {
                const c = p.locator(s).first();
                if (await c.count()) { await c.click({ force: true }).catch(() => {}); await p.waitForTimeout(2500); }
            }
        },
    },

    cierre: {
        ruta: '/dashboard/checkins', espera: 12000,
        antes: async (p) => { await pulsar(p, 'Editar lo de hoy', 4000); },
    },

    perfil: { ruta: '/dashboard/profile', espera: 10000 },
    'perfil-apagar-cierre': {
        ruta: '/dashboard/profile', espera: 10000,
        forzada: 'Se pulsa el interruptor del cierre del día para ver el aviso que sale '
               + 'antes de apagarlo. No se llega a guardar.',
        antes: async (p) => {
            const sw = p.locator('button[role="switch"], [data-testid*="cierre"]').first();
            if (await sw.count()) { await sw.click({ force: true }).catch(() => {}); await p.waitForTimeout(2500); }
        },
    },

    suplementos: { ruta: '/dashboard/supplements', espera: 10000 },
    'suplementos-sin-plan': {
        ruta: '/dashboard/supplements', espera: 10000,
        forzada: 'La guía se responde con `con_plan: false` (su texto, sin tocar): es lo que '
               + 've quien todavía no tiene protocolo.',
        rutas: [['**/api/supplements/guia*', async (route) => {
            const r = await route.fetch();
            const j = await r.json().catch(() => null);
            if (!j) return route.fulfill({ response: r });
            return route.fulfill({ response: r, json: { ...j, con_plan: false } });
        }]],
    },
    'suplementos-sin-protocolo': {
        ruta: '/dashboard/supplements', espera: 10000,
        forzada: 'El protocolo se responde vacío y la guía general también: a ese cartel '
               + '«solo se llega si no hay ni general», lo dice la propia pantalla.',
        rutas: [['**/api/supplements/current*', { status: 200, json: { items: [] } }],
                ['**/api/supplements/guia*',
                 { status: 200, json: { con_plan: true, texto_entrada: '', categorias: [] } }]],
    },

    rutina: { ruta: '/dashboard/routine', espera: 10000 },
    'rutina-error': {
        ruta: '/dashboard/routine', espera: 9000,
        forzada: 'La rutina se responde con un error.',
        rutas: [['**/api/routines/**', { status: 500, json: { detail: 'de mentira' } }]],
    },
    'rutina-del-mes': {
        ruta: '/dashboard/routine', espera: 10000,
        forzada: 'Se responde que no hay rutina del mes: es el estado del que no la lleva '
               + 'en su plan.',
        rutas: [['**/api/routines/active*', { status: 404, json: { detail: 'sin rutina' } }],
                ['**/api/routines/mes*', { status: 404, json: { detail: 'sin rutina' } }]],
    },

    'alimento-almendras': { ruta: '/dashboard/foods', espera: 11000,
        antes: (p) => buscarAlimento(p, 'almendras crudas') },
    'alimentos-tres-frases': { ruta: '/dashboard/foods', espera: 11000,
        antes: async (p) => {
            // Las tres fichas, una detrás de otra, en la misma pantalla.
            for (const q of ['almendras crudas', 'pollo', 'lechuga']) await buscarAlimento(p, q, false);
        } },

    seguimiento: { ruta: '/dashboard/reports', espera: 9000 },
    evolucion: { ruta: '/dashboard/reports', espera: 9000,
        antes: (p) => abrirSeguimiento(p, 'seg-evolucion') },

    quincenal: {
        ruta: '/dashboard/reports', espera: 9000,
        forzada: 'La ventana del quincenal, abierta, y se entra al formulario. Es donde '
               + 'tendrían que estar los tres pasos.',
        rutas: [ventanaAbierta('quincenal')],
        antes: (p) => abrirSeguimiento(p, 'seg-revision'),
    },

    ...Object.fromEntries([1, 2, 3].map((n) => [`mensual-paso${n}`, {
        ruta: '/dashboard/reports', espera: 9000,
        forzada: 'La ventana del mensual, abierta (fuera de plazo no se pinta el formulario).',
        rutas: [ventanaAbierta('mensual')],
        antes: (p) => irAlPasoDelMensual(p, n),
    }])),
    'mensual-periodo': {
        ruta: '/dashboard/reports', espera: 9000,
        forzada: 'La ventana del mensual, abierta.',
        rutas: [ventanaAbierta('mensual')],
        antes: async (p) => {
            await irAlPasoDelMensual(p, 1);
            const b = p.locator('[data-testid="paso1-periodo-principio"]');
            if (await b.count()) { await b.click().catch(() => {}); await p.waitForTimeout(3000); }
        },
    },
    ...Object.fromEntries([['mensual-paso4', true], ['mensual-paso4-sin', false]].map(
        ([id, conInforme]) => [id, {
            ruta: '/dashboard/reports', espera: 9000,
            forzada: 'El envío se responde desde aquí (no se le crea un reporte a la cuenta '
                   + 'de pruebas) y el informe se dice que '
                   + (conInforme ? 'ya está publicado.' : 'sigue pendiente de revisión.'),
            rutas: [ventanaAbierta('mensual'), ...envioDeMentira(conInforme)],
            antes: (p) => mandarElMensual(p),
        }])),

    ...Object.fromEntries([['informe-enviado', false], ['informe-contestado', true]].map(
        ([id, contestado]) => [id, {
            ruta: '/dashboard/reports', espera: 9000,
            forzada: 'El historial y el informe se responden con el ejemplo montado contra '
                   + 'la base de dev (`_probar_informe_del_mes.py`), '
                   + (contestado ? 'con el feedback escrito.' : 'con el hueco del feedback vacío.'),
            rutas: informeDeMentira(contestado),
            antes: async (p) => {
                await abrirSeguimiento(p, 'seg-historial');
                const b = p.locator('[data-testid="ver-informe-informe-de-prueba"]');
                if (await b.count()) { await b.click().catch(() => {}); await p.waitForTimeout(4500); }
            },
        }])),
};

async function buscarAlimento(p, q, limpiar = true) {
    const caja = p.locator('[data-testid="buscador-campo"]').first();
    if (!(await caja.count())) return;
    await caja.fill(q);
    await p.waitForTimeout(3500);
    const b = p.locator('[data-testid^="abrir-"]').first();
    if (await b.count()) { await b.click().catch(() => {}); await p.waitForTimeout(2000); }
    if (limpiar) return;
    // Se deja abierta y se sigue: asi las tres fichas se leen en la misma pasada.
    await p.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await p.waitForTimeout(600);
}

async function irAlPasoDelMensual(p, n) {
    await abrirSeguimiento(p, 'seg-revision');
    if (n === 1) return;
    const peso = p.locator('[data-testid="weight-input"]');
    if (await peso.count()) await peso.fill('80');
    await p.locator('[data-testid="paso1-confirmar"]').click().catch(() => {});
    await p.waitForTimeout(3000);
    if (n === 2) return;
    await p.locator('[data-testid="mensual-siguiente"]').click().catch(() => {});
    await p.waitForTimeout(3000);
}

async function mandarElMensual(p) {
    await irAlPasoDelMensual(p, 3);
    const medidas = ['hombros', 'mesoesternal', 'brazo_d', 'brazo_i', 'muslo_d', 'muslo_i',
                     'cadera', 'cintura', 'gemelo_d', 'gemelo_i'];
    for (const m of medidas) {
        const c = p.locator(`[data-testid="medida-${m}"]`);
        if (await c.count()) await c.fill('100');
    }
    await p.locator('[data-testid="revisar-y-enviar"]').click().catch(() => {});
    await p.waitForTimeout(2500);
    const enviar = p.locator('button:has-text("Enviar")').last();
    if (await enviar.count()) { await enviar.click().catch(() => {}); await p.waitForTimeout(4000); }
}

function envioDeMentira(conInforme) { return [
    ['**/api/reports', (route) => (route.request().method() === 'POST'
        ? route.fulfill({ status: 200, json: {
            id: 'de-mentira', tipo: 'mensual', weight: 80,
            mensaje_envio: 'Antes del sábado tienes tu informe completo con mi feedback y tus ajustes.',
            promesa_dia: 'sábado' } })
        : route.continue())],
    ['**/api/reports/de-mentira/informe', (route) => (conInforme
        ? route.fulfill({ status: 200, json: { generado: true } })
        : route.fulfill({ status: 403, json: { detail: 'pendiente' } }))],
]; }

function informeDeMentira(contestado) {
    const base = JSON.parse(fs.readFileSync('_guia/_informe_del_mes_ejemplo.json', 'utf8'));
    if (contestado) {
        base.bloques.feedback = {
            pendiente: false,
            texto: 'Has bajado 2,8 kg cumpliendo 22 de 28 días. El descanso te ha caído y ahí '
                 + 'está el hambre que me cuentas. Te subo los hidratos del perientreno y te '
                 + 'bajo el cardio a dos sesiones.',
            firma: 'Jesús Gallego', iniciales: 'JG', fecha_label: '5 de septiembre',
        };
        base.bloques.medidas = {
            hay: true, hay_mes: true, hay_primera: true,
            filas: [['cuello', 'Cuello', -1, -1], ['mesoesternal', 'Mesoesternal', -1, 3],
                    ['cintura', 'Cintura', -2, -6], ['gemelo_d', 'Gemelo derecho', 0, 0]]
                .map(([clave, etiqueta, mes, primera]) => ({
                    clave, etiqueta, valor: 100,
                    mes: { dif: mes, label: `${mes > 0 ? '+' : mes < 0 ? '−' : ''}${Math.abs(mes)}`,
                           color: mes === 0 ? 'gris' : mes < 0 ? 'verde' : 'rojo' },
                    primera: { dif: primera, label: `${primera > 0 ? '+' : primera < 0 ? '−' : ''}${Math.abs(primera)}`,
                               color: primera === 0 ? 'gris' : primera < 0 ? 'verde' : 'rojo' },
                })),
        };
    }
    const POSES = ['frente', 'espaldas', 'perfil'];
    const FECHAS = ['2026-06-04', '2026-08-25'];
    return [
        ['**/api/reports', (route) => (route.request().method() === 'GET'
            ? route.fulfill({ status: 200, json: [{
                id: 'informe-de-prueba', tipo: 'mensual', weight: 78.4,
                created_at: '2026-08-25T12:00:00+00:00', informe_estado: 'entregado' }] })
            : route.continue())],
        ['**/api/reports/informe-de-prueba/informe', (route) =>
            route.fulfill({ status: 200, json: base })],
        ['**/api/reports/photos', (route) => (route.request().method() === 'GET'
            ? route.fulfill({ status: 200, json: { photos: POSES.flatMap(
                (pose) => FECHAS.map((f) => ({ id: `${pose}-${f}`, pose, taken_at: f }))) } })
            : route.continue())],
        ['**/api/reports/photos/*', (route) => route.fulfill({
            status: 200, contentType: 'image/gif',
            body: Buffer.from('R0lGODlhAQABAIAAAMLCwgAAACH5BAAAAAAALAAAAAABAAEAAAICRAEAOw==', 'base64') })],
    ];
};

(async () => {
    const token = await fetch(`${API}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: CUENTA, password: CLAVE }),
    }).then((r) => r.json()).then((r) => r.access_token);
    if (!token) { console.log('no he podido entrar'); return; }

    const soloEsta = process.argv[2];
    const porEscena = {};
    for (const p of PUNTOS) {
        if (!p.escena) continue;
        (porEscena[p.escena] = porEscena[p.escena] || []).push(p);
    }

    const manifiesto = [];
    for (const [id, escena] of Object.entries(ESCENAS)) {
        if (soloEsta && id !== soloEsta) continue;
        const suyos = porEscena[id] || [];
        if (!suyos.length) continue;

        const nav = await chromium.launch();
        const p = await (await nav.newContext({ viewport: { width: 390, height: 1700 },
                                                deviceScaleFactor: 2 })).newPage();
        for (const [patron, resp] of (escena.rutas || [])) {
            await p.route(patron, typeof resp === 'function' ? resp : (r) => r.fulfill(resp));
        }
        await p.goto(APP, { waitUntil: 'domcontentloaded' });
        await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, token);
        await p.goto(`${APP}/dashboard`, { waitUntil: 'networkidle' }).catch(() => {});
        await p.waitForTimeout(escena.espera);
        for (let i = 0; i < 4; i++) {
            const s = p.locator('[data-testid="recorrido-saltar"]');
            if (!(await s.count())) break;
            await s.click({ force: true }).catch(() => {});
            await p.waitForTimeout(900);
        }
        if (escena.ruta !== '/dashboard') {
            await p.goto(APP + escena.ruta, { waitUntil: 'networkidle' }).catch(() => {});
            await p.waitForTimeout(escena.espera);
        }
        if (escena.antes) await escena.antes(p).catch(() => {});
        await p.waitForTimeout(1200);

        const visible = await p.evaluate(() => document.body.innerText);
        const plano = visible.toLowerCase();
        fs.writeFileSync(`${CARPETA}/${id}.txt`, visible, 'utf8');
        await p.screenshot({ path: `${CARPETA}/${id}.png`, fullPage: true });

        for (const punto of suyos) {
            const faltan = punto.debe_verse.filter((f) => !plano.includes(f.toLowerCase()));
            const primera = punto.debe_verse.find((f) => plano.includes(f.toLowerCase()));
            let imagen = null;
            if (primera) {
                try {
                    const loc = p.getByText(primera, { exact: false }).first();
                    await loc.scrollIntoViewIfNeeded({ timeout: 4000 });
                    await p.waitForTimeout(350);
                    const caja = await loc.evaluate((el) => {
                        let n = el;
                        for (let i = 0; i < 7 && n.parentElement; i++) {
                            const r = n.getBoundingClientRect();
                            if (r.height >= 70 && r.width >= 220) break;
                            n = n.parentElement;
                        }
                        const r = n.getBoundingClientRect();
                        return { x: r.x, y: r.y, w: r.width, h: r.height };
                    });
                    const clip = { x: Math.max(0, caja.x - 8), y: Math.max(0, caja.y - 8),
                                   width: Math.min(390, caja.w + 16),
                                   height: Math.min(760, caja.h + 16) };
                    if (clip.width > 40 && clip.height > 24) {
                        imagen = `${id}__${manifiesto.length}.jpg`;
                        await p.screenshot({ path: `${CARPETA}/${imagen}`, clip,
                                             type: 'jpeg', quality: 70 });
                    }
                } catch { imagen = null; }
            }
            manifiesto.push({ ...punto, escena_id: id, forzada: escena.forzada || null,
                              ruta: escena.ruta, faltan, imagen,
                              estado: faltan.length === 0 ? 'completo'
                                    : faltan.length === punto.debe_verse.length ? 'nada' : 'parcial' });
            console.log(`  [${manifiesto[manifiesto.length - 1].estado.padEnd(8)}] ${id} · `
                        + `${punto.titulo.slice(0, 46)}`
                        + (faltan.length ? `  falta: ${faltan[0].slice(0, 42)}` : ''));
        }
        await nav.close();
    }

    const destino = `${CARPETA}/_manifiesto.json`;
    let previo = [];
    if (soloEsta && fs.existsSync(destino)) {
        previo = JSON.parse(fs.readFileSync(destino, 'utf8')).filter((m) => m.escena_id !== soloEsta);
    }
    fs.writeFileSync(destino, JSON.stringify(previo.concat(manifiesto), null, 1), 'utf8');
    const n = (e) => manifiesto.filter((m) => m.estado === e).length;
    console.log(`\n${manifiesto.length} puntos · completos ${n('completo')} · `
                + `a medias ${n('parcial')} · nada ${n('nada')}`);
})();
