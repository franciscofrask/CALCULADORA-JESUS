// Acceso y habilitaciones por plan.
// Fuente de verdad: catálogo del backend (GET /api/plans). Aquí solo traducimos
// la matriz de "habilitaciones" de un plan a capacidades de UI y a etiquetas legibles.
import { prettyToken } from './labels';

// Capacidades que la UI consulta para mostrar/ocultar funciones.
export const CAP = {
    RUTINA: 'rutina',
    SUPLEMENTACION: 'suplementacion',
    MACROS_PERSONALIZADOS: 'macros_personalizados',
    // Si el cliente puede TOCAR sus macros (fallo 08 del doc del 19-08): es el campo del
    // que sale la pestaña «Mis macros». No es lo contrario de MACROS_PERSONALIZADOS: un
    // Mantenimiento no tiene entrenador Y edita; un Gold tiene entrenador y NO edita.
    EDITA_MACROS: 'edita_macros',
    REPORTES: 'reportes',
    // Chat con el entrenador. Sale del `acompanamiento` del plan, que es el único campo de
    // la matriz que no se estaba mirando: al plan «solo app», que por definición no lleva
    // entrenador, se le enseñaba el Chat igual, y lo que encontraba dentro era «Soporte
    // JG12» y un vacío que le decía «envía un mensaje a tu entrenador» (TABLA 20 y 4.16).
    CHAT: 'chat',
};

// Suplementación con sus tres valores (fallo 10 del 19-08: «ninguna · la guía · protocolo
// personalizado»), tolerando el booleano viejo de los overrides guardados. «ninguna» es un
// texto y un texto es truthy: mirarlo a pelo diría que un plan sin nada la incluye.
export const suplementacionIncluida = (h) => {
    const v = (h || {}).suplementacion;
    if (typeof v === 'string') return ['guia', 'guía', 'protocolo'].includes(v.trim().toLowerCase());
    return !!v;
};

// Deriva capacidades booleanas a partir de la matriz de habilitaciones del plan.
//
// `rutinaVisible` es el interruptor `t3_entreno` del panel (db.app_settings), que llega
// por `pantalla('t3_entreno')` desde AuthContext. Su gemelo del backend es
// `core/plan_access.rutina_visible_para_el_cliente()`: los dos leen lo mismo, para que no
// pueda pasar que al cliente le lleguen avisos de una pantalla que no puede abrir.
export function deriveCapabilities(habilitaciones, { rutinaVisible = false } = {}) {
    const h = habilitaciones || {};
    const reportes = h.reportes || [];
    return {
        // La Rutina se escondió el 19-07-2026 con una constante aquí mismo. Ahora manda el
        // interruptor, y por debajo lo de siempre: que el plan la incluya. Cierra menú,
        // tarjeta "Entreno de hoy", paso del tour y las rutas directas (CapabilityRoute).
        // El panel de admin de rutinas NO se toca.
        [CAP.RUTINA]: !!rutinaVisible && !!h.rutina && h.rutina !== 'ninguna',
        [CAP.SUPLEMENTACION]: suplementacionIncluida(h),
        [CAP.MACROS_PERSONALIZADOS]: h.calculadora === 'personalizado',
        // Si el campo no viene (overrides guardados antes del 19-08), se deduce de lo que
        // era verdad hasta hoy: el de autogestión editaba, el de entrenador no.
        [CAP.EDITA_MACROS]: h.edita_macros !== undefined
            ? !!h.edita_macros
            : h.calculadora !== 'personalizado',
        [CAP.REPORTES]: reportes.length > 0,
        // SOLO CON ENTRENADOR DETRÁS (P73 del doc 23-08, decidido por Francisco el
        // mismo día): a Calculadora, ELM y Mantenimiento se les QUITA el Chat. El
        // 21-08 se había abierto a todos como canal de soporte (cobros, «algo no
        // funciona»), pero el doc lo marcó como fallo -- «Contacto: Ninguna» -- y la
        // decisión es la contraria: el Chat es del acompañamiento, no del soporte.
        // Sus incidencias van por el correo del negocio, como antes del 21-08.
        // CUALQUIER acompañamiento con entrenador, no solo el valor exacto (24-08). Con
        // la igualdad, el Premium -- que es `con_entrenador_y_llamadas`, el plan que MÁS
        // acompañamiento tiene y el más caro -- se quedaba sin Chat. La decisión del
        // 23-08 fue «el Chat sale del acompañamiento del plan», no «solo del que ponga
        // exactamente con_entrenador». Mismo criterio que core/renovacion.py:170.
        [CAP.CHAT]: String(h.acompanamiento || '').startsWith('con_entrenador'),
    };
}

// Etiquetas legibles para mostrar el detalle del plan al usuario / admin.
const RUTINA_LABEL = {
    personalizada: 'Rutina personalizada',
    del_mes: 'Rutina del mes',
    opcional: 'Rutina opcional',
    ninguna: 'Sin rutina',
};
const CALCULADORA_LABEL = {
    personalizado: 'Macros personalizados por tu entrenador',
    autogestion: 'Calculadora en autogestión',
    sin_ajuste: 'Calculadora sin ajuste activo',
};
const REPORTE_LABEL = {
    quincenal: 'Reporte quincenal',
    mensual: 'Reporte mensual',
    semanal: 'Reporte semanal',
};

// LO MISMO, PERO CONTADO (#53 del informe del 15-08: «sigue el lenguaje de catálogo»).
//
// Las etiquetas de arriba son las del catálogo: sirven para que el equipo configure un plan
// y por eso nombran la casilla («Con entrenador», «Macros personalizados por tu
// entrenador»). Al cliente esa lista se le enseña como «Tu plan incluye», y ahí una casilla
// no es una frase: lo que compró es que alguien le lleve, no un campo marcado. Se traduce
// solo lo que ve el cliente; el panel del equipo sigue con sus nombres.
const CLIENTE_CALCULADORA = {
    personalizado: 'Tus macros te los ajustamos nosotros',
    autogestion: 'Te calculas los macros tú, con la calculadora',
    sin_ajuste: 'Calculadora, sin ajustes de seguimiento',
};
const CLIENTE_ACOMPANAMIENTO = {
    con_entrenador: 'Un entrenador te lleva el seguimiento',
    con_entrenador_y_llamadas: 'Un entrenador te lleva el seguimiento, con llamadas',
};
const CLIENTE_CONTACTO = {
    semanal: 'Hablamos cada semana',
    quincenal: 'Hablamos cada quince días',
    mensual: 'Hablamos una vez al mes',
};

// Lista de "qué incluye el plan" a partir de las habilitaciones (reemplaza las
// features hardcodeadas antiguas).
export function habilitacionesToList(habilitaciones) {
    const h = habilitaciones || {};
    const out = [];
    if (h.calculadora && CLIENTE_CALCULADORA[h.calculadora]) out.push(CLIENTE_CALCULADORA[h.calculadora]);
    if (h.rutina && h.rutina !== 'ninguna' && RUTINA_LABEL[h.rutina]) out.push(RUTINA_LABEL[h.rutina]);
    (h.reportes || []).forEach((r) => REPORTE_LABEL[r] && out.push(REPORTE_LABEL[r]));
    if (suplementacionIncluida(h)) {
        out.push(String(h.suplementacion).toLowerCase() === 'guia' || String(h.suplementacion).toLowerCase() === 'guía'
            ? 'Guía de suplementación'
            : 'Protocolo de suplementación personalizado');
    }
    if (h.acompanamiento && h.acompanamiento !== 'solo_app') {
        out.push(CLIENTE_ACOMPANAMIENTO[h.acompanamiento] || ACOMPANAMIENTO_LABEL[h.acompanamiento]);
        if (h.frecuencia_contacto && CLIENTE_CONTACTO[h.frecuencia_contacto]) {
            out.push(CLIENTE_CONTACTO[h.frecuencia_contacto]);
        }
    }
    return out;
}

// LO QUE SE LE ENSEÑA AL CLIENTE EN «TU PLAN INCLUYE» (punto 6.4 de la revisión del 09-08).
//
// Manda el campo libre `que_incluye` del catálogo, una línea por punto, escrito a mano y
// pintado tal cual. Las líneas derivadas de las habilitaciones son el respaldo: describen lo
// que la app enciende («Calculadora en autogestión», «Reporte quincenal»), no lo que el
// cliente compró, y eso vale para los planes que ya no se venden pero no para los cuatro que
// sí. Vacío = se sigue derivando, así que quitar el texto no deja la tarjeta en blanco.
export function queIncluyeElPlan(plan) {
    const escrito = (plan?.que_incluye || '').split('\n').map(l => l.trim()).filter(Boolean);
    return escrito.length ? escrito : habilitacionesToList(plan?.habilitaciones);
}

// Acompañamiento y frecuencia de contacto (especificación 31-07-2026): lo que separa
// dos planes que, por lo demás, solo se diferencian en el precio.
export const ACOMPANAMIENTO_OPTS = [
    { value: 'solo_app', label: 'Sin entrenador (solo app)' },
    { value: 'con_entrenador', label: 'Con entrenador' },
    { value: 'con_entrenador_y_llamadas', label: 'Con entrenador y llamadas' },
];
export const FRECUENCIA_CONTACTO_OPTS = [
    { value: 'semanal', label: 'Semanal' },
    { value: 'quincenal', label: 'Quincenal' },
    { value: 'mensual', label: 'Mensual' },
    { value: 'ninguna', label: 'Ninguna' },
];
const ACOMPANAMIENTO_LABEL = Object.fromEntries(ACOMPANAMIENTO_OPTS.map(o => [o.value, o.label]));
const FRECUENCIA_LABEL = Object.fromEntries(FRECUENCIA_CONTACTO_OPTS.map(o => [o.value, o.label]));

// La calculadora del plan, con nombre y no con su código («personalizado»), que es lo que
// se pintaba en la ficha del plan del panel.
export const etiquetaCalculadora = (v) => CALCULADORA_LABEL[v] || prettyToken(v);
export const etiquetaAcompanamiento = (v) => ACOMPANAMIENTO_LABEL[v] || ACOMPANAMIENTO_LABEL.solo_app;
export const etiquetaFrecuencia = (v) => FRECUENCIA_LABEL[v] || FRECUENCIA_LABEL.ninguna;

// Etiqueta corta del estado del plan.
export const ESTADO_LABEL = {
    activo: 'Activo',
    legacy: 'Legacy',
    especial: 'Especial',
    complemento: 'Complemento',
};

// Duración del ciclo en semanas (o null si es mensual indefinido / variable).
export function cicloSemanas(plan) {
    return plan?.ciclo?.semanas ?? null;
}
