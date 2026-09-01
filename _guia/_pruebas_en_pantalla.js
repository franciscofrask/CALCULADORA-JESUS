/**
 * LA PRUEBA DE CADA PUNTO, EN LA PANTALLA DE VERDAD.
 *
 * El repaso anterior probaba los puntos con `git grep`: que la frase estuviera en un
 * fichero. Eso no prueba nada -- un texto puede estar escrito en un componente que no se
 * pinta, detras de una condicion que no se cumple, o en un comentario --, y ademas ya
 * mordio antes buscando textos en el bundle.
 *
 * Esto es lo otro: se abre la app de verdad, se va a la pantalla, se busca la frase EN LO
 * QUE SE VE (`innerText` de la pagina) y, si esta, se recorta la tarjeta que la contiene y
 * se guarda como imagen. La prueba de que un punto esta cerrado es su captura.
 *
 * CUANDO HAY QUE FORZAR UN ESTADO -- la rutina sin asignar, el error de carga, la ventana
 * del reporte cerrada -- se responde esa peticion desde aqui y se marca la escena como
 * `forzada`. Es la misma pantalla y el mismo componente; lo unico de mentira es el estado
 * de partida, igual que hace el modo revision del equipo.
 *
 * Uso:  node _guia/_pruebas_en_pantalla.js [escena]
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CUENTA = process.env.CUENTA || 'clientedemo@test.com';
const CLAVE = process.env.CLAVE || 'demo123';
const CARPETA = '_guia/_pruebas_pantalla';
if (!fs.existsSync(CARPETA)) fs.mkdirSync(CARPETA, { recursive: true });

// ── LO QUE HAY QUE VER, POR PANTALLA ────────────────────────────────────────
// `frase` es lo que tiene que estar A LA VISTA. `id` es el mismo punto del repaso.
const ESCENAS = [
    {
        id: 'inicio',
        nombre: 'Inicio',
        ruta: '/dashboard',
        espera: 12000,
        puntos: [
            { id: 'llevas', frase: 'Llevas' },
            { id: 'extras-titulo', frase: 'ponlo aquí, por pequeño que sea' },
            { id: 'extras-o-si-no', frase: 'o si no está' },
            { id: 'extras-a-mano', frase: 'no cuenta en tus macros' },
            { id: 'cola', frase: '¿Cómo fuiste hoy?' },
        ],
    },
    {
        id: 'nutricion',
        nombre: 'Nutrición',
        // Un día con comida de verdad: hoy está sin crear y sin comidas no hay nada que ver.
        ruta: '/dashboard/nutrition?date=2026-08-30&comida=C1',
        espera: 15000,
        antes: async (p) => {
            // Abrir la primera comida: la frase «Te ajusto las cantidades» vive dentro.
            for (const sel of ['[data-testid="meal-select-C1"]', '[data-testid="meal-tab-C1"]']) {
                const c = p.locator(sel).first();
                if (await c.count()) {
                    await c.click({ force: true }).catch(() => {});
                    await p.waitForTimeout(3000);
                }
            }
            if (!(await p.getByText('Ajuste de cantidades', { exact: false }).count())) {
                await p.getByText('COMIDA 1', { exact: false }).first()
                    .click({ force: true }).catch(() => {});
                await p.waitForTimeout(3000);
            }
        },
        puntos: [
            { id: 'numeros-nutricion', frase: 'PROTEÍNA' },
            { id: 'comida-por-dentro', frase: 'Te ajusto las cantidades sin pasarme de tus macros' },
        ],
    },
    {
        id: 'cierre',
        nombre: 'El cierre del día',
        ruta: '/dashboard/checkins',
        espera: 12000,
        antes: async (p) => {
            // El día de hoy ya está cerrado, así que la pantalla enseña «Anotado». Se entra
            // a editarlo, que es donde están las nueve preguntas.
            const b = p.getByText('Editar lo de hoy', { exact: false }).first();
            if (await b.count()) { await b.click().catch(() => {}); await p.waitForTimeout(3500); }
        },
        puntos: [
            { id: 'cierre-suplementacion', frase: '¿Tomaste la suplementación que tenías pautada?' },
            { id: 'cierre-extras', frase: 'Si no lo pusiste en el apartado de extras, ponlo ahora' },
            { id: 'cierre-entreno', frase: '¿Entrenaste hoy?' },
            { id: 'cierre-cardio', frase: '¿Hiciste cardio?' },
            { id: 'cierre-movimiento', frase: '¿Te moviste lo suficiente?' },
            { id: 'cierre-descanso', frase: '¿Cómo descansaste la noche de ayer?' },
            { id: 'cierre-energia', frase: 'Niveles de energía durante el día' },
            { id: 'cierre-hambre', frase: 'Hambre / ansiedad con la dieta' },
            { id: 'cierre-notas', frase: 'Esto es para tu diario' },
            { id: 'cierre-falta', frase: 'Te queda por contestar' },
            // Este NO tendria que estar: el documento lo manda a Mi evolucion.
            { id: 'cierre-peso', frase: 'Registrarlo es opcional', noDeberia: true },
            { id: 'cierre-sensaciones', frase: 'Sensaciones generales del día', noDeberia: true },
        ],
    },
    {
        id: 'perfil',
        nombre: 'Mi perfil · Avisos',
        ruta: '/dashboard/profile',
        espera: 10000,
        puntos: [
            { id: 'avisos-cierre', frase: 'Rellenar el cierre del día' },
            { id: 'avisos-salto', frase: 'Recordármelo si me lo salto' },
            { id: 'avisos-no-apagan', frase: 'no se pueden desactivar' },
            { id: 'avisos-quincenal', frase: 'Recordatorio del reporte quincenal' },
            { id: 'avisos-mensual', frase: 'Recordatorio del reporte mensual' },
            { id: 'avisos-peso', frase: 'Recordatorios del peso' },
            { id: 'avisos-app', frase: 'Avisos en la app' },
        ],
    },
    {
        id: 'suplementos',
        nombre: 'Suplementación',
        ruta: '/dashboard/supplements',
        espera: 10000,
        puntos: [
            { id: 'fullgas', frase: 'mientras dure tu suscripción' },
            { id: 'mis-suplementos-titulo', frase: 'MIS SUPLEMENTOS' },
        ],
    },
    {
        id: 'suplementos-sin-plan',
        nombre: 'Suplementación · sin protocolo',
        ruta: '/dashboard/supplements',
        espera: 10000,
        forzada: 'Se responde el protocolo vacío. La cuenta de pruebas tiene creatina '
               + 'pautada, y el texto de la guía y el «estamos en ello» son justo lo que '
               + 've quien todavía no tiene nada.',
        rutas: [
            ['**/api/supplements/guia*', async (route) => {
                // La respuesta DE VERDAD, con `con_plan` a false: asi sale el texto suyo,
                // no uno inventado aqui.
                const r = await route.fetch();
                const j = await r.json().catch(() => null);
                if (!j) return route.fulfill({ response: r });
                return route.fulfill({ response: r, json: { ...j, con_plan: false } });
            }],
            ['**/api/supplements/current*',
             { status: 200, json: { items: [], nota: null, version: null } }],
        ],
        puntos: [
            { id: 'guia-suplementos', frase: 'te recomiendo empezar por los básicos' },
        ],
    },
    {
        id: 'suplementos-sin-protocolo',
        nombre: 'Suplementación · esperando el suyo',
        ruta: '/dashboard/supplements',
        espera: 10000,
        forzada: 'El protocolo se responde vacío. Es lo que ve quien tiene la pantalla pero '
               + 'todavía no le han pautado nada; la cuenta de pruebas tiene creatina.',
        rutas: [['**/api/supplements/current*',
                 { status: 200, json: { items: [], nota: null, version: null } }],
                // Y la guia general vacia: a este cartel «solo se llega si no hay ni
                // general» (comentario de la propia pantalla).
                ['**/api/supplements/guia*',
                 { status: 200, json: { con_plan: true, texto_entrada: '', categorias: [] } }]],
        puntos: [
            { id: 'mis-suplementos', frase: 'Todavía no tienes tu plan de suplementación personalizado' },
            { id: 'mis-suplementos-espera', frase: 'Estamos en ello, te avisamos en cuanto esté' },
        ],
    },
    {
        id: 'rutina',
        nombre: 'Rutina',
        ruta: '/dashboard/routine',
        espera: 10000,
        puntos: [
            { id: 'rutina-espera', frase: 'Estamos en ello, te avisamos en cuanto esté' },
        ],
    },
    {
        id: 'rutina-error',
        nombre: 'Rutina · cuando algo falla',
        ruta: '/dashboard/routine',
        espera: 9000,
        forzada: 'La rutina se responde con un error, que es el estado que se quiere ver.',
        rutas: [['**/api/routines/**', { status: 500, json: { detail: 'de mentira' } }]],
        puntos: [
            { id: 'error-carga', frase: 'Esto parece cosa nuestra' },
        ],
    },
    // Las tres frases intocables viven DENTRO de la ficha de un alimento, así que hay que
    // buscarlo y abrirlo. Una escena por frase, con su alimento.
    ...[
        ['almendras', 'almendras crudas', 'Su proteína no te cuenta',
         'La frase de las almendras, y el tramo del día debajo'],
        ['pollo', 'pollo', 'Te cuentan los tres',
         'La del pollo, la que se paró hasta decidir el intermedio'],
        ['lechuga', 'lechuga', 'No te cuenta nada',
         'La de la lechuga, que antes no existía'],
    ].map(([id, busca, frase, nombre]) => ({
        id: `alimento-${id}`,
        nombre: `Alimentos · ${nombre}`,
        ruta: '/dashboard/foods',
        espera: 11000,
        antes: async (p) => {
            const caja = p.locator('[data-testid="buscador-campo"]').first();
            if (!(await caja.count())) return;
            await caja.fill(busca);
            await p.waitForTimeout(3500);
            const abrir = p.locator('[data-testid^="abrir-"]').first();
            if (await abrir.count()) { await abrir.click().catch(() => {}); await p.waitForTimeout(2000); }
        },
        puntos: [{ id: `frase-${id}`, frase }].concat(
            id === 'almendras'
                ? [{ id: 'tramo', frase: 'de 20 a 40 g' },
                   { id: 'que-te-cuenta-almendras', frase: 'Te cuenta la grasa' }]
                : []),
    })),
];

const login = async () => {
    const r = await fetch(`${API}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: CUENTA, password: CLAVE }),
    }).then((x) => x.json());
    return r.access_token;
};

(async () => {
    const token = await login();
    if (!token) { console.log('no he podido entrar'); return; }
    const soloEsta = process.argv[2];
    const manifiesto = [];

    for (const escena of ESCENAS) {
        if (soloEsta && escena.id !== soloEsta) continue;
        const nav = await chromium.launch();
        const ctx = await nav.newContext({ viewport: { width: 390, height: 1600 },
                                           deviceScaleFactor: 2 });
        const p = await ctx.newPage();
        const errores = [];
        p.on('pageerror', (e) => errores.push(String(e).slice(0, 160)));

        for (const [patron, respuesta] of (escena.rutas || [])) {
            await p.route(patron, typeof respuesta === 'function'
                ? respuesta
                : (route) => route.fulfill(respuesta));
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
        if (escena.antes) await escena.antes(p);

        const visible = await p.evaluate(() => document.body.innerText);
        // SIN DISTINGUIR MAYUSCULAS. `innerText` devuelve el texto YA transformado por el
        // CSS, asi que un titulo con `uppercase` sale a gritos y una comparacion exacta
        // dice que no esta cuando esta delante.
        const plano = visible.toLowerCase();
        fs.writeFileSync(`${CARPETA}/${escena.id}.txt`, visible, 'utf8');
        await p.screenshot({ path: `${CARPETA}/${escena.id}.png`, fullPage: true });

        for (const punto of escena.puntos) {
            const esta = plano.includes(punto.frase.toLowerCase());
            let imagen = null;
            if (esta) {
                // La tarjeta que contiene la frase: se sube por los padres hasta encontrar
                // una caja de tamaño razonable, que es lo que se entiende en una captura.
                try {
                    // `getByText` con `exact: false`: la frase casi siempre es un TROZO de
                    // un parrafo, y `text="..."` entre comillas exige el nodo entero.
                    // LA PRIMERA, NO LA ULTIMA. Con `.last()` las preguntas del cierre
                    // recortaban el resumen «Te queda por contestar» de abajo, que las
                    // nombra todas: la captura decia otra cosa que el punto.
                    const loc = p.getByText(punto.frase, { exact: false }).first();
                    await loc.scrollIntoViewIfNeeded({ timeout: 4000 });
                    await p.waitForTimeout(400);
                    const caja = await loc.evaluate((el) => {
                        let n = el;
                        for (let i = 0; i < 6 && n.parentElement; i++) {
                            const r = n.getBoundingClientRect();
                            if (r.height >= 60 && r.width >= 200) break;
                            n = n.parentElement;
                        }
                        const r = n.getBoundingClientRect();
                        return { x: r.x, y: r.y, w: r.width, h: r.height };
                    });
                    const clip = {
                        x: Math.max(0, caja.x - 8), y: Math.max(0, caja.y - 8),
                        width: Math.min(390, caja.w + 16), height: Math.min(700, caja.h + 16),
                    };
                    if (clip.width > 40 && clip.height > 24) {
                        imagen = `${escena.id}__${punto.id}.jpg`;
                        await p.screenshot({ path: `${CARPETA}/${imagen}`, clip,
                                             type: 'jpeg', quality: 72 });
                    }
                } catch { imagen = null; }
            }
            manifiesto.push({
                escena: escena.id, escena_nombre: escena.nombre, ruta: escena.ruta,
                forzada: escena.forzada || null, punto: punto.id, frase: punto.frase,
                no_deberia: !!punto.noDeberia, visto: esta, imagen,
            });
            const marca = punto.noDeberia ? (esta ? 'SIGUE AHÍ' : 'ya no está')
                                          : (esta ? 'visto' : 'NO SE VE');
            console.log(`  [${marca}] ${escena.id} · ${punto.frase.slice(0, 52)}`
                        + (imagen ? '' : esta ? '  (sin recorte)' : ''));
        }
        if (errores.length) console.log('   errores:', errores.slice(0, 2));
        await nav.close();
    }

    const destino = `${CARPETA}/_manifiesto.json`;
    let previo = [];
    if (soloEsta && fs.existsSync(destino)) {
        previo = JSON.parse(fs.readFileSync(destino, 'utf8'))
            .filter((m) => m.escena !== soloEsta);
    }
    fs.writeFileSync(destino, JSON.stringify(previo.concat(manifiesto), null, 1), 'utf8');
    const vistos = manifiesto.filter((m) => m.visto && !m.no_deberia).length;
    console.log(`\n${vistos} de ${manifiesto.filter(m => !m.no_deberia).length} vistos en pantalla`);
    console.log(`capturas y textos en ${CARPETA}/`);
})();
