/**
 * LOS DOCE PUNTOS QUE FALTABAN, capturados de la app de verdad.
 *
 * Mismo metodo que `_capturar_todo.js` y las mismas cuatro reglas:
 *   1. Se compara en minusculas: `innerText` viene ya transformado por el CSS.
 *   2. El recorte coge el PRIMER elemento con la frase, no el ultimo.
 *   3. `getByText` con `exact:false`: la frase casi siempre es un trozo de un parrafo.
 *   4. Lo que se fuerza es el ESTADO DE PARTIDA, nunca el texto que se comprueba.
 *
 * Los datos del paso 1 (los pesajes y los cierres) no se fuerzan con un `route`: se montan
 * de verdad en la cuenta de pruebas con `_escenario_quincenal_paso1.py`, y la pantalla los
 * pide al servidor como cualquier dia.
 *
 * Uso:  node _guia/_capturar_los_doce.js [escena]
 */
const fs = require('fs');
const { chromium } = require('playwright');

const APP = process.env.DESTINO || 'http://localhost:3000';
const API = process.env.API || 'http://127.0.0.1:8000';
const CARPETA = '_guia/_capturas_doce';
if (!fs.existsSync(CARPETA)) fs.mkdirSync(CARPETA, { recursive: true });

const EQUIPO = { correo: 'francisco@test.com', clave: 'demo123' };
const AVISOS = JSON.parse(fs.readFileSync('_guia/_avisos_del_calendario.json', 'utf8'));
const LINEAS = JSON.parse(fs.readFileSync('_guia/_lineas_del_cierre.json', 'utf8'));
const CLIENTE = { correo: 'clientedemo@test.com', clave: 'demo123' };

const pulsar = async (p, testid, espera = 2500) => {
    const b = p.locator(`[data-testid="${testid}"]`).first();
    if (await b.count()) { await b.click({ force: true }).catch(() => {}); await p.waitForTimeout(espera); }
};

/**
 * La cola de Inicio del miercoles por la mañana. Se fuerza SOLO el reloj y la ventana:
 * - `toca_pesarse` y el reporte abierto son el estado de partida (hoy es martes).
 * - Los TEXTOS de las dos filas los escribe la app, no este guion.
 */
const colaDelMiercoles = (deadline, tocaPesarse) => [
    ['**/api/checkins/estado*', async (route) => {
        const r = await route.fetch();
        const j = await r.json().catch(() => null);
        if (!j) return route.fulfill({ response: r });
        return route.fulfill({ response: r, json: { ...j, toca_pesarse: tocaPesarse } });
    }],
    ['**/api/reports/due*', async (route) => {
        const r = await route.fetch();
        const j = await r.json().catch(() => null);
        if (!j) return route.fulfill({ response: r });
        j.items = [{ tipo: 'quincenal', tipo_label: 'Reporte quincenal', deadline,
                     overdue: false, is_open: true }];
        j.window = { ...(j.window || {}), due: true, is_open: true, submitted: false,
                     tipos: ['quincenal'], tipo_label: 'Reporte quincenal',
                     closes_at: deadline };
        return route.fulfill({ response: r, json: j });
    }],
];

/** La ventana del quincenal, abierta, para poder entrar al formulario. */
const quincenalAbierto = (submitted = false) => [
    ['**/api/reports/due*', async (route) => {
        const r = await route.fetch();
        const j = await r.json().catch(() => null);
        if (!j) return route.fulfill({ response: r });
        j.window = { ...(j.window || {}), due: true, is_open: true, submitted,
                     tipos: ['quincenal'], tipo_label: 'Reporte quincenal',
                     closes_at: '2026-08-27T18:00:00+00:00' };
        return route.fulfill({ response: r, json: j });
    }],
    ['**/api/reports/formulario*', async (route) => {
        const r = await route.fetch();
        const j = await r.json().catch(() => null);
        if (!j) return route.fulfill({ response: r });
        return route.fulfill({ response: r, json: { ...j, tipo: 'quincenal' } });
    }],
];

const ESCENAS = {
    // ── A · El quincenal en tres pasos ──
    'quincenal-paso1': {
        cuenta: EQUIPO, ruta: '/dashboard/reports?ver=quincenal&dia=2026-08-27',
        espera: 9000, rutas: quincenalAbierto(),
        forzada: 'La ventana del quincenal, abierta (hoy le toca el mensual), y la semana '
               + 'del 27 de agosto, que es la del escenario: hoy es martes y la pareja de '
               + 'miercoles y jueves todavia no ha pasado.',
        debe: ['Reporte quincenal', 'Son 3 pasos',
               // El numero va en su circulo, o sea en otro nodo: `innerText` mete un
               // salto de linea entre el «1» y el texto. Se busca el texto.
               'Actualizar tus datos y confirmar que está bien',
               'Escuchar tus sensaciones y dudas',
               'Darte feedback directo y ajustes si procede',
               'Actualizar tus datos',
               'Sale de tu check-in. Si algo no cuadra o te falta, lo modificas al final.',
               'Peso semanal', '78,4 kg', '78,6', 'Miércoles', '78,2', 'Jueves', 'Viernes',
               'Dos días seguidos entre el miércoles y el viernes.',
               'Lo que has hecho', 'Y cómo te has sentido',
               'Te dejaste 2 entrenos sin registrar.', 'Modificar', 'Confirmar'],
    },

    'quincenal-paso2': {
        cuenta: EQUIPO, ruta: '/dashboard/reports?ver=quincenal&dia=2026-08-27',
        espera: 9000, rutas: quincenalAbierto(),
        antes: async (p) => { await pulsar(p, 'quincenal-paso1-confirmar', 2500); },
        forzada: 'La misma, y ademas se pulsa Confirmar para pasar al paso 2.',
        debe: ['Reporte quincenal', 'Son 3 pasos', 'Tus sensaciones y tus dudas',
               'Sensaciones generales hasta ahora',
               '0 · Muy malas, demasiado exigente para mí', '10 · Genial, mejor imposible',
               '¿Cuánto te está costando?', 'Valoración esfuerzo / resultados',
               '0 · Mal, mucho esfuerzo para pocos avances',
               '¿Algún ejercicio que te dé molestias o alguna máquina que no tengas?',
               'Dudas o lo que quieras contarme', 'Ahora es el momento y el lugar',
               'Enviar reporte'],
    },

    'quincenal-paso3': {
        cuenta: EQUIPO, ruta: '/dashboard/reports?ver=quincenal&dia=2026-08-27',
        espera: 9000,
        rutas: [
            ...quincenalAbierto(),
            // El envio se responde sin escribir en la base: lo unico que se le da es el
            // dia prometido, que es el dato. La FRASE la escribe la pantalla.
            ['**/api/reports', (route) => (route.request().method() === 'POST'
                ? route.fulfill({ status: 200, json: { id: 'de-mentira', promesa_dia: 'viernes' } })
                : route.continue())],
        ],
        antes: async (p) => {
            await pulsar(p, 'quincenal-paso1-confirmar', 2500);
            await pulsar(p, 'submit-report-btn', 3500);
        },
        forzada: 'El envio se responde de mentira para no escribir un reporte en la base. '
               + 'Lo que se le da es el dia prometido; la frase la pone la pantalla.',
        debe: ['Reporte quincenal', 'Son 3 pasos', 'Tu feedback y tus ajustes',
               'Este tercer paso es cosa nuestra.',
               'Recibirás respuesta antes del viernes a las 3, hora de España.'],
    },

    'quincenal-paso1-sin-checkin': {
        cuenta: CLIENTE, ruta: '/dashboard/reports',
        espera: 9000, rutas: quincenalAbierto(),
        // El modo revision es solo del equipo, asi que aqui se entra como entra el: desde
        // la portada, pulsando la tarjeta del reporte.
        antes: async (p) => { await pulsar(p, 'seg-revision', 6000); },
        forzada: 'La ventana del quincenal, abierta. Los pocos check-in son REALES: esta '
               + 'cuenta tiene 4 en catorce dias, que es justo el caso.',
        debe: ['Reporte quincenal', 'Son 3 pasos', 'Actualizar tus datos',
               'No tengo todos los datos de tus check-in diarios',
               '¿En qué grado has cumplido la dieta?',
               '¿Has entrenado todos los días que tocaba?',
               '¿Has cumplido con el cardio que tenías pautado?',
               '¿Has tomado la suplementación que te correspondía?',
               'Descanso · ¿cómo fue?', 'Continuar'],
    },

    // ── B · La cola de Inicio ──
    'inicio-miercoles': {
        cuenta: CLIENTE, ruta: '/dashboard', espera: 12000,
        reloj: '2026-09-02T08:00:00+00:00',   // miercoles, las 10:00 de España
        rutas: colaDelMiercoles('2026-09-03T18:00:00+00:00', true),
        forzada: 'El reporte quincenal, abierto y con plazo mañana a las ocho, y la pesada '
               + 'de la mañana encendida. Los dos son estado, no texto.',
        debe: ['Tu reporte quincenal', 'Hoy toca pesarte',
               'En ayunas y después de ir al baño'],
    },

    'inicio-jueves': {
        cuenta: CLIENTE, ruta: '/dashboard', espera: 12000,
        reloj: '2026-09-03T15:00:00+00:00',   // jueves, las 17:00 de España
        rutas: colaDelMiercoles('2026-09-03T18:00:00+00:00', false),
        forzada: 'El mismo reporte con el plazo HOY a las ocho. La fila es la misma: lo '
               + 'que cambia es lo que dice.',
        debe: ['Tu reporte quincenal', 'Solo recordarte que tienes hasta hoy a las ocho'],
    },

    // ── C · La tarjeta en Hecho ──
    'tarjeta-hecho': {
        cuenta: CLIENTE, ruta: '/dashboard/reports', espera: 9000,
        rutas: quincenalAbierto(true),
        forzada: 'El reporte, ya mandado (`submitted`). La frase de la tarjeta viene del '
               + 'servidor, de `core/promesa_del_reporte`.',
        debe: ['Hecho', 'Reporte quincenal', 'Respondiste a tiempo y ahora nos toca a nosotros',
               'Ver'],
    },

    // ── E · El campo del peso en Mi evolución ──
    'evolucion-campo-peso': {
        cuenta: CLIENTE, ruta: '/dashboard/reports?abrir=peso', espera: 9000,
        debe: ['Tu peso', 'Siempre abierto', 'kg', 'Guardar',
               'Registrarlo es opcional, sólo para ti. Te lo pediremos sólo para los reportes.'],
    },

    // ── D · La comida por dentro ──
    'nutricion-comida': {
        cuenta: CLIENTE, ruta: '/dashboard/nutrition?date=2026-08-30&comida=C1',
        espera: 15000,
        antes: async (p) => {
            for (const t of ['meal-select-C1', 'meal-tab-C1']) await pulsar(p, t, 2500);
        },
        debe: ['Comida 1', 'Proteína', 'Hidratos', 'Grasa', 'Ajuste de cantidades',
               'Automático', 'Manual',
               'Ajusta las cantidades de los alimentos a tus macros',
               'Cuadrar', 'Te ajusto las cantidades sin pasarme de tus macros.'],
    },

    // ── F · Las tres frases intocables, una ficha por pasada ──
    //
    // Las tres juntas no valen: al buscar el siguiente alimento la ficha del anterior se
    // cierra, asi que una sola captura solo probaria la ultima.
    ...Object.fromEntries([
        ['almendras', 'almendras crudas', ['Almendras', 'Su proteína no te cuenta']],
        ['pollo', 'pollo', ['Pollo', 'Te cuentan los tres']],
        ['lechuga', 'lechuga', ['Lechuga', 'No te cuenta nada']],
    ].map(([id, busqueda, debe]) => [`alimento-${id}`, {
        cuenta: CLIENTE, ruta: '/dashboard/foods', espera: 11000,
        antes: async (p) => {
            const caja = p.locator('[data-testid="buscador-campo"]').first();
            if (!(await caja.count())) return;
            await caja.fill(busqueda);
            await p.waitForTimeout(3500);
            const b = p.locator('[data-testid^="abrir-"]').first();
            if (await b.count()) { await b.click().catch(() => {}); await p.waitForTimeout(2500); }
        },
        debe,
    }])),

    // ── LOS AVISOS DEL CALENDARIO (bloques 4 y 6) ──
    //
    // Un aviso nace el dia que le toca y con el estado que le toca; reunir eso seis veces
    // en dev no prueba mas. Los compone el MODULO DE VERDAD
    // (`_guia/_avisos_del_calendario.py` llama a `core/avisos_cliente`) y aqui se le dan a
    // la campanita para que los pinte. El texto sale del codigo de la app, no de este guion.
    ...Object.fromEntries(Object.entries(AVISOS).map(([clave, m]) => [`aviso-${clave}`, {
        cuenta: CLIENTE, ruta: '/dashboard', espera: 11000,
        forzada: `${m.cuando}. Los avisos los compone «core/avisos_cliente» y se le dan a `
               + 'la campanita: lo forzado es el dia, no el texto.',
        rutas: [
            ['**/api/notifications', (route) => (route.request().method() === 'GET'
                ? route.fulfill({ status: 200, json: { notifications: m.avisos } })
                : route.fulfill({ status: 200, json: { ok: true } }))],
            ['**/api/notifications/unread-count',
             (route) => route.fulfill({ status: 200, json: { count: m.avisos.length } })],
        ],
        antes: async (p) => { await pulsar(p, 'client-bell', 2500); },
        debe: m.avisos.flatMap((a) => [a.title, a.body].filter(Boolean)),
    }])),

    // ── EL MENSUAL SIN CHECK-IN ──
    'mensual-paso1-sin-checkin': {
        cuenta: CLIENTE, ruta: '/dashboard/reports', espera: 9000,
        rutas: [
            ['**/api/reports/due*', async (route) => {
                const r = await route.fetch();
                const j = await r.json().catch(() => null);
                if (!j) return route.fulfill({ response: r });
                j.window = { ...(j.window || {}), due: true, is_open: true, submitted: false,
                             tipos: ['mensual'], tipo_label: 'Reporte mensual' };
                return route.fulfill({ response: r, json: j });
            }],
        ],
        antes: async (p) => { await pulsar(p, 'seg-revision', 7000); },
        forzada: 'La ventana del mensual, abierta. Los pocos check-in son REALES: esta '
               + 'cuenta tiene 4 en veintiocho dias, que es justo el caso.',
        debe: ['Reporte mensual', 'Son 4 pasos', 'Actualizar tus datos',
               'Cinco preguntas y pasas al paso 2. El peso y las fotos se te piden igual.',
               'No tengo todos los datos de tus check-in diarios',
               '¿En qué grado has cumplido la dieta?',
               '¿Has entrenado todos los días que tocaba?',
               '¿Has cumplido con el cardio que tenías pautado?',
               '¿Has tomado la suplementación que te correspondía?',
               'Descanso · ¿cómo fue?', 'Tu peso de hoy', 'Continuar'],
    },

    // ── Y A LAS 12:00 LA FILA DE LA PESADA SE APAGA ──
    'inicio-mediodia-sin-pesada': {
        cuenta: CLIENTE, ruta: '/dashboard', espera: 12000,
        reloj: '2026-09-02T10:00:00+00:00',   // miercoles, las 12:00 de España
        forzada: 'El miercoles a las 12:00 en punto. El servidor decide con la hora del '
               + 'cliente, que la pantalla le manda.',
        debe: [],
        noDebe: ['Hoy toca pesarte'],
    },

    // ── LA ESCALADA DE LA FILA DEL CIERRE (2, 4 y 7 dias) ──
    //
    // La compone el servidor con `core/ventana_del_dia.texto_de_la_linea`, y para verla
    // haria falta una cuenta que de verdad lleve esos dias sin cerrar. Se le pide al propio
    // modulo (`_guia/_lineas_del_cierre.py`) y se le da a Inicio: lo forzado es CUANTOS
    // DIAS LLEVA, el texto es el del servidor.
    ...Object.fromEntries(Object.entries(LINEAS).map(([clave, m]) => [`inicio-${clave}`, {
        cuenta: CLIENTE, ruta: '/dashboard', espera: 12000,
        forzada: `${m.cuando}: ${m.racha} dias sin cerrar. La frase la compone `
               + '«core/ventana_del_dia», no este guion.',
        rutas: [['**/api/checkins/estado*', async (route) => {
            const r = await route.fetch();
            const j = await r.json().catch(() => null);
            if (!j) return route.fulfill({ response: r });
            return route.fulfill({ response: r, json: { ...j, abierto: j.abierto || '2026-09-01',
                hecho: false, es_de_ayer: false, quiere_cierre: true,
                dias_sin_cerrar: m.racha, linea: m.linea } });
        }]],
        debe: [m.linea.titulo, m.linea.detalle],
    }])),

    // ── EL AVISO DE LAS COMIDAS SIN REGISTRAR, arriba del cierre ──
    'cierre-comidas-pendientes': {
        cuenta: CLIENTE, ruta: '/dashboard/checkins', espera: 10000,
        forzada: 'Dos comidas del dia sin marcar (Intra y Post). Lo forzado es CUALES le '
               + 'faltan; la frase la escribe la pantalla.',
        rutas: [['**/api/checkins/hoy*', async (route) => {
            const r = await route.fetch();
            const j = await r.json().catch(() => null);
            if (!j) return route.fulfill({ response: r });
            return route.fulfill({ response: r, json: { ...j,
                // Con la forma que manda el servidor: {key, etiqueta}. Con una lista de
                // textos sueltos la pantalla pintaba «·» y parecia que no estaban.
                comidas_pendientes: [{ key: 'Intra', etiqueta: 'Intra-entreno' },
                                     { key: 'Post', etiqueta: 'Post-entreno' }] } });
        }]],
        // Esta cuenta ya cerro el dia, asi que el formulario no esta a la vista: se abre
        // con «Editar lo de hoy», que es lo que haria el cliente.
        antes: async (p) => { await pulsar(p, 'cierre-editar', 4000); },
        debe: ['Te quedan 2 comidas sin registrar', 'Intra-entreno', 'Post-entreno',
               'Puedes cerrarlas antes de seguir'],
    },

    // ── EL AVISO DE ANTES DE APAGAR EL CIERRE ──
    'perfil-apagar-cierre': {
        cuenta: CLIENTE, ruta: '/dashboard/profile', espera: 10000,
        antes: async (p) => { await pulsar(p, 'aviso-cierre-dia', 2500); },
        forzada: 'Se pulsa el interruptor del cierre para ver el aviso que sale ANTES de '
               + 'apagarlo. No se llega a guardar.',
        debe: ['Mi perfil', 'Avisos y recordatorios', 'El cierre del día',
               'Rellenar el cierre del día',
               'Si lo apagas, no podrás registrar tus datos del día',
               'Puedes volver a activarlo cuando quieras.',
               'Dejarlo como está', 'Apagarlo'],
    },

    // ── LOS EJERCICIOS QUE DAN MOLESTIAS, en el paso 2 del mensual ──
    'mensual-paso2-molestias': {
        cuenta: CLIENTE, ruta: '/dashboard/reports', espera: 9000,
        forzada: 'Un plan CON lesiones en sus bloques: ese bloque solo sale a quien lo '
               + 'lleva, y esta cuenta no. Lo forzado es que su plan lo incluya.',
        rutas: [
            ['**/api/reports/due*', async (route) => {
                const r = await route.fetch();
                const j = await r.json().catch(() => null);
                if (!j) return route.fulfill({ response: r });
                j.window = { ...(j.window || {}), due: true, is_open: true, submitted: false,
                             tipos: ['mensual'], tipo_label: 'Reporte mensual' };
                return route.fulfill({ response: r, json: j });
            }],
            ['**/api/reports/formulario*', async (route) => {
                const r = await route.fetch();
                const j = await r.json().catch(() => null);
                if (!j) return route.fulfill({ response: r });
                const bloques = Array.from(new Set([...(j.bloques || []), 'lesiones', 'molestias']));
                // Y una lesion abierta: el bloque de ejercicios vetados cuelga de ella
                // («la mitad util de una lesion»), asi que sin ninguna no hay nada que
                // enseñar. Lo forzado es que la tenga; los textos son de la pantalla.
                const datos = { ...(j.datos || {}),
                                lesiones: [{ zona: 'Hombro derecho', desde: 'marzo',
                                             ejercicios_vetados: ['Press militar'] }] };
                return route.fulfill({ response: r, json: { ...j, tipo: 'mensual', bloques, datos } });
            }],
        ],
        antes: async (p) => {
            await pulsar(p, 'seg-revision', 7000);
            // El paso 1 de esta cuenta es el de «sin check-in»: hasta que no contesta las
            // cinco estrellas, «Continuar» esta apagado. Se contestan como las contestaria
            // el, pulsando la tercera estrella de cada una.
            for (const q of ['dieta_grado', 'entreno_grado', 'cardio_grado',
                             'suplementacion_grado', 'descanso_grado']) {
                await pulsar(p, `${q}-3`, 400);
            }
            const peso = p.locator('[data-testid="weight-input"]').first();
            if (await peso.count()) await peso.fill('80').catch(() => {});
            await pulsar(p, 'paso1-continuar', 3000);
            await pulsar(p, 'paso1-confirmar', 3000);
        },
        debe: ['Quita los que ya no y añade los nuevos'],
    },

    // ── EL CUADRO DE EXTRAS, al pulsar el «+» ──
    'inicio-extras-abierto': {
        cuenta: CLIENTE, ruta: '/dashboard', espera: 13000,
        antes: async (p) => { await pulsar(p, 'extras-abrir', 2500); },
        debe: ['Extras del día',
               'Si comes algo que no está en tu dieta del día, ponlo aquí, por pequeño que sea.',
               'Buscar el alimento', 'o si no está',
               'Escríbelo a mano. En cuanto pase, con la cantidad a ojo si no lo pesas.',
               'Lo que pongas a mano no cuenta en tus macros, simplemente queda el registro. Lo que busques, sí.'],
        recorte: 'Extras del día',
    },

    // ── LA RUTINA, cuando la del mes todavia no esta ──
    'rutina-sin-la-del-mes': {
        cuenta: CLIENTE, ruta: '/dashboard/routine', espera: 11000,
        forzada: 'Un plan con la rutina como OPCIONAL (hoy, Mantenimiento) y la del mes '
               + 'todavia sin preparar. Son los dos datos que llevan a esta rama; los '
               + 'textos los pone la pantalla.',
        rutas: [
            ['**/api/routines/active*', (route) => route.fulfill({ status: 404, json: { detail: 'sin rutina' } })],
            ['**/api/routines/rutina-del-mes/disponible*',
             (route) => route.fulfill({ status: 200, json: { disponible: false } })],
            // La rutina, «opcional» en su plan: no la lleva de serie. Es lo que hace que la
            // pantalla hable de LA DEL MES y no de la personalizada.
            ['**/api/plans*', async (route) => {
                const r = await route.fetch();
                const j = await r.json().catch(() => null);
                if (!j) return route.fulfill({ response: r });
                const tocado = Array.isArray(j) ? j : { ...j };
                for (const k of Object.keys(tocado)) {
                    const plan = tocado[k];
                    if (plan && plan.habilitaciones) {
                        tocado[k] = { ...plan,
                                      habilitaciones: { ...plan.habilitaciones, rutina: 'opcional' } };
                    }
                }
                return route.fulfill({ response: r, json: tocado });
            }],
        ],
        debe: ['Todavía no está la rutina de este mes',
               'Estamos en ello, te avisamos en cuanto esté.'],
    },

    // ── LOS DOS BLOQUES DEL INFORME QUE SALIAN VACIOS ──
    //
    // No estaban mal: es que el cliente del ejemplo no daba pie a ellos (no cambio de peso
    // en el mes y no apunto ningun extra). `_guia/_escenario_informe.py` le monta las dos
    // cosas en dev y `backend/_probar_informe_del_mes.py` vuelve a armar el informe con lo
    // que salga. Los NUMEROS los calcula el servidor; aqui solo se sirve el informe ya
    // armado para no crearle un reporte a nadie.
    'informe-peso-y-extras': {
        cuenta: CLIENTE, ruta: '/dashboard/reports', espera: 9000,
        forzada: 'El historial y el informe se responden con el ejemplo armado contra la '
               + 'base de dev, ya con un mes de peso que baja y dos extras apuntados.',
        rutas: (() => {
            const base = JSON.parse(fs.readFileSync('_guia/_informe_del_mes_ejemplo.json', 'utf8'));
            return [
                ['**/api/reports', (route) => (route.request().method() === 'GET'
                    ? route.fulfill({ status: 200, json: [{
                        id: 'informe-de-prueba', tipo: 'mensual', weight: 82.1,
                        created_at: '2026-08-25T12:00:00+00:00', informe_estado: 'entregado' }] })
                    : route.continue())],
                ['**/api/reports/informe-de-prueba/informe',
                 (route) => route.fulfill({ status: 200, json: base })],
            ];
        })(),
        antes: async (p) => {
            await pulsar(p, 'seg-historial', 5000);
            await pulsar(p, 'ver-informe-informe-de-prueba', 5000);
        },
        debe: ['Porcentaje del peso total que has ido bajando por semana',
               'Semana 1', 'Semana 4', 'Extras registrados',
               'Un trozo de tarta', 'Dos cervezas con la comida'],
        recorte: 'Porcentaje del peso total que has ido bajando por semana',
    },

    'cierre-del-dia-sin-peso': {
        cuenta: CLIENTE, ruta: '/dashboard/checkins', espera: 9000,
        debe: [],
        noDebe: ['Registrarlo es opcional'],
    },
};

(async () => {
    const soloEsta = process.argv[2];
    const salida = [];
    for (const [id, escena] of Object.entries(ESCENAS)) {
        if (soloEsta && id !== soloEsta) continue;
        const cuenta = escena.cuenta || CLIENTE;
        const token = await fetch(`${API}/api/auth/login`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: cuenta.correo, password: cuenta.clave }),
        }).then((r) => r.json()).then((r) => r.access_token);
        if (!token) { console.log(`${id}: no he podido entrar como ${cuenta.correo}`); continue; }

        const nav = await chromium.launch();
        // EL NAVEGADOR, EN ESPAÑA. Las maquetas son de un cliente de España, y la app hace
        // bien en poner la hora local con la de España detras cuando no coinciden («hasta
        // hoy a las tres (20:00 h España)»). Este ordenador esta en otro huso, asi que para
        // comprobar los textos del documento se dice donde vive el que mira.
        const p = await (await nav.newContext({ viewport: { width: 390, height: 1800 },
                                                deviceScaleFactor: 2,
                                                locale: 'es-ES',
                                                timezoneId: 'Europe/Madrid' })).newPage();
        // EL RELOJ, cuando la escena es de una hora concreta. Un plazo que ya paso hace que
        // la fila desaparezca de Inicio (y es lo correcto), asi que para ver el jueves a
        // las cinco hay que estar a las cinco. Se fija la HORA, no el texto.
        if (escena.reloj) await p.clock.setFixedTime(new Date(escena.reloj));
        for (const [patron, resp] of (escena.rutas || [])) await p.route(patron, resp);
        await p.goto(APP, { waitUntil: 'domcontentloaded' });
        await p.evaluate((t) => { localStorage.clear(); localStorage.setItem('token', t); }, token);
        await p.goto(APP + escena.ruta, { waitUntil: 'networkidle' }).catch(() => {});
        await p.waitForTimeout(escena.espera);
        for (let i = 0; i < 4; i++) {
            const s = p.locator('[data-testid="recorrido-saltar"]');
            if (!(await s.count())) break;
            await s.click({ force: true }).catch(() => {});
            await p.waitForTimeout(900);
        }
        if (escena.antes) await escena.antes(p).catch(() => {});
        await p.waitForTimeout(1200);

        // LO QUE SE LEE EN LA PANTALLA NO ES SOLO `innerText`. Los textos de dentro de un
        // campo vacio -- «Buscar el alimento...», «Escribelo a mano...» -- son
        // `placeholder`, y el cliente los LEE igual. Sin esto salian como si no existieran,
        // que es justo el falso negativo que hay que evitar.
        const visible = await p.evaluate(() => {
            const sueltos = [...document.querySelectorAll('[placeholder]')]
                .map((el) => el.getAttribute('placeholder')).filter(Boolean);
            return [document.body.innerText, ...sueltos].join('\n');
        });
        const plano = visible.toLowerCase();
        fs.writeFileSync(`${CARPETA}/${id}.txt`, visible, 'utf8');
        await p.screenshot({ path: `${CARPETA}/${id}.png`, fullPage: true });

        const faltan = (escena.debe || []).filter((f) => !plano.includes(f.toLowerCase()));
        const sobran = (escena.noDebe || []).filter((f) => plano.includes(f.toLowerCase()));

        // EL RECORTE PARA EL ARTIFACT. Se recorta la tarjeta que contiene la primera frase
        // del punto, con la misma regla del repaso grande: el PRIMER elemento que la lleva,
        // subiendo por sus padres hasta que la caja tenga tamaño de tarjeta.
        let imagen = null;
        const anclaje = escena.recorte
            || (escena.debe || []).find((f) => plano.includes(f.toLowerCase()));
        if (anclaje) {
            try {
                const loc = p.getByText(anclaje, { exact: false }).first();
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
                               height: Math.min(900, caja.h + 16) };
                if (clip.width > 40 && clip.height > 24) {
                    imagen = `doce-${id}.jpg`;
                    await p.screenshot({ path: `${CARPETA}/${imagen}`, clip,
                                         type: 'jpeg', quality: 70 });
                }
            } catch { imagen = null; }
        }

        salida.push({ id, faltan, sobran, imagen, puntos: escena.puntos || [],
                      ruta: escena.ruta, forzada: escena.forzada || null,
                      debe: escena.debe || [] });
        console.log(`\n== ${id}`);
        console.log(faltan.length ? `   FALTAN: ${faltan.join(' | ')}` : '   todas las frases estan');
        if (sobran.length) console.log(`   SOBRAN (deberian haberse ido): ${sobran.join(' | ')}`);
        await nav.close();
    }
    // Se acumula: correr una escena suelta no puede borrar lo que ya se probo.
    const antes = fs.existsSync(`${CARPETA}/_resultado.json`)
        ? JSON.parse(fs.readFileSync(`${CARPETA}/_resultado.json`, 'utf8')) : [];
    const juntos = [...antes.filter((a) => !salida.some((s) => s.id === a.id)), ...salida];
    fs.writeFileSync(`${CARPETA}/_resultado.json`, JSON.stringify(juntos, null, 1), 'utf8');
})();
