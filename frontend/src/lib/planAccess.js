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
    return out;
}

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
