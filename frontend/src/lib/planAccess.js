// Acceso y habilitaciones por plan.
// Fuente de verdad: catálogo del backend (GET /api/plans). Aquí solo traducimos
// la matriz de "habilitaciones" de un plan a capacidades de UI y a etiquetas legibles.

// Capacidades que la UI consulta para mostrar/ocultar funciones.
export const CAP = {
    RUTINA: 'rutina',
    SUPLEMENTACION: 'suplementacion',
    MACROS_PERSONALIZADOS: 'macros_personalizados',
    REPORTES: 'reportes',
    HARBIZ: 'harbiz',
};

// Deriva capacidades booleanas a partir de la matriz de habilitaciones del plan.
export function deriveCapabilities(habilitaciones) {
    const h = habilitaciones || {};
    const reportes = h.reportes || [];
    return {
        // RUTINA OCULTA temporalmente (petición 19-07-2026) hasta completar la
        // funcionalidad. Al reactivarla, restaurar: !!h.rutina && h.rutina !== 'ninguna'
        // Oculta menú, tarjeta "Entreno de hoy", paso del tour y la ruta directa
        // (CapabilityRoute). El panel de admin de rutinas NO se toca.
        [CAP.RUTINA]: false,
        [CAP.SUPLEMENTACION]: !!h.suplementacion,
        [CAP.MACROS_PERSONALIZADOS]: h.calculadora === 'personalizado',
        [CAP.REPORTES]: reportes.length > 0,
        [CAP.HARBIZ]: !!h.harbiz,
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
    personalizado: 'Macros personalizados por tu coach',
    autogestion: 'Calculadora en autogestión',
    sin_ajuste: 'Calculadora sin ajuste activo',
};
const REPORTE_LABEL = {
    quincenal: 'Reporte quincenal',
    mensual: 'Reporte mensual',
    semanal: 'Reporte semanal',
};

// Lista de "qué incluye el plan" a partir de las habilitaciones (reemplaza las
// features hardcodeadas antiguas).
export function habilitacionesToList(habilitaciones) {
    const h = habilitaciones || {};
    const out = [];
    if (h.calculadora && CALCULADORA_LABEL[h.calculadora]) out.push(CALCULADORA_LABEL[h.calculadora]);
    if (h.rutina && h.rutina !== 'ninguna' && RUTINA_LABEL[h.rutina]) out.push(RUTINA_LABEL[h.rutina]);
    (h.reportes || []).forEach((r) => REPORTE_LABEL[r] && out.push(REPORTE_LABEL[r]));
    if (h.suplementacion) out.push('Suplementación personalizada');
    if (h.harbiz) out.push('Rutina en Harbiz (app calendario)');
    if (h.acompanamiento && h.acompanamiento !== 'solo_app') {
        out.push(ACOMPANAMIENTO_LABEL[h.acompanamiento]);
        if (h.frecuencia_contacto && h.frecuencia_contacto !== 'ninguna') {
            out.push(`Contacto ${h.frecuencia_contacto}`);
        }
    }
    return out;
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
