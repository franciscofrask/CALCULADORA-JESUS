/**
 * LOS OBJETIVOS DEL CLIENTE (doc de Jesús del 2-09, fase 2). Espejo de
 * `backend/core/objetivos.py`, que es la fuente: si se amplía la lista, se amplía en los dos.
 *
 * Los pone el ENTRENADOR, no el cliente (Jesús: «es un cambio de fondo, no de copy»). Dos
 * niveles: el del ciclo (`profile.ciclo_actual.objetivo`) y el actual
 * (`profile.objetivo_actual`), más el `foco` («tonificación con foco glúteo» son dos campos).
 * El `goal` viejo (volumen / definicion) sigue existiendo para el motor de macros; aquí no
 * se pinta.
 */
export const OBJETIVOS = [
    { clave: 'ganar_volumen', nombre: 'Ganar volumen', definicion: null },
    { clave: 'perder_grasa', nombre: 'Perder grasa', definicion: null },
    { clave: 'maxima_definicion', nombre: 'Máxima definición', definicion: 'Bajar del 14 % de grasa.' },
    { clave: 'recomposicion', nombre: 'Recomposición', definicion: 'Empieza cuando termina una definición.' },
    { clave: 'mantenimiento', nombre: 'Mantenimiento', definicion: null },
    { clave: 'tonificacion', nombre: 'Tonificación', definicion: null },
];

const POR_CLAVE = Object.fromEntries(OBJETIVOS.map((o) => [o.clave, o]));

// De los valores viejos (`goal`) al objetivo nuevo, literal: definición es perder grasa.
const DESDE_GOAL = {
    volumen: 'ganar_volumen', definicion: 'perder_grasa', perdida_grasa: 'perder_grasa',
    'perdida-grasa': 'perder_grasa', mantenimiento: 'mantenimiento',
    recomposicion: 'recomposicion', tonificacion: 'tonificacion',
};

export const normalizarObjetivo = (clave) => {
    const c = String(clave || '').trim().toLowerCase();
    if (POR_CLAVE[c]) return c;
    return DESDE_GOAL[c] || null;
};

/** «Perder grasa», o «» si no hay objetivo. Acepta también un `goal` viejo. */
export const nombreDelObjetivo = (clave) => POR_CLAVE[normalizarObjetivo(clave) || '']?.nombre || '';

export const definicionDelObjetivo = (clave) => POR_CLAVE[normalizarObjetivo(clave) || '']?.definicion || null;

/** El objetivo que se enseña al cliente: el actual de la ficha, y si no, el `goal` viejo traducido. */
export const objetivoVisible = (profile) => normalizarObjetivo(profile?.objetivo_actual || profile?.goal);
