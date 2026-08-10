// Etiquetas legibles para valores enum/token que se guardan en la BD.
// Evita que se filtren a la UI cosas como "male" o "pesas_libres".

const SEXO = { male: 'Hombre', female: 'Mujer', hombre: 'Hombre', mujer: 'Mujer', ambos: 'Ambos' };

const OBJETIVO = {
    definicion: 'Definición', volumen: 'Volumen', recomposicion: 'Recomposición',
    perdida_grasa: 'Pérdida de grasa', 'perdida-grasa': 'Pérdida de grasa',
    mantenimiento: 'Mantenimiento',
};

const EQUIPAMIENTO = {
    pesas_libres: 'Pesas libres', mancuernas: 'Mancuernas', barra_olimpica: 'Barra olímpica',
    pull_up_bar: 'Barra de dominadas', cardio_machine: 'Máquina de cardio',
    bandas_elasticas: 'Bandas elásticas', kettlebell: 'Kettlebell', trx: 'TRX',
    maquinas: 'Máquinas', gimnasio_completo: 'Gimnasio completo', ninguno: 'Ninguno',
};

const EXPERIENCIA = {
    principiante: 'Principiante', intermedio: 'Intermedio', avanzado: 'Avanzado',
};

const ACTIVIDAD = {
    sedentario: 'Sedentario', bajo: 'Bajo', moderado: 'Moderado', alto: 'Alto', muy_alto: 'Muy alto',
};

const BIOTIPO = {
    ectomorfo: 'Ectomorfo', mesomorfo: 'Mesomorfo', endomorfo: 'Endomorfo',
};

// Momentos/categorías de suplementos (catálogo admin).
const SUPLEMENTO_CAT = {
    base: 'Base', intra: 'Intra-entreno', rendimiento: 'Rendimiento', quemador: 'Quemador',
    salud: 'Salud', sueno: 'Sueño', otro: 'Otro',
};

// snake_case / kebab-case -> "Texto legible" como último recurso.
export const prettyToken = (t) =>
    String(t || '').replace(/[_-]+/g, ' ').replace(/^\w/, (c) => c.toUpperCase());

const lookup = (map, v, fallbackDash = true) => {
    if (v == null || v === '') return fallbackDash ? '-' : '';
    return map[String(v).toLowerCase()] || prettyToken(v);
};

export const sexoLabel = (v) => lookup(SEXO, v);
export const objetivoLabel = (v) => lookup(OBJETIVO, v);
export const equipamientoLabel = (v) => lookup(EQUIPAMIENTO, v, false);
// Para poder pintar el equipamiento como opciones marcables en la ficha del coach.
export const EQUIPAMIENTO_OPCIONES = Object.entries(EQUIPAMIENTO).map(([value, label]) => ({ value, label }));
export const experienciaLabel = (v) => lookup(EXPERIENCIA, v);
export const actividadLabel = (v) => lookup(ACTIVIDAD, v);
export const biotipoLabel = (v) => lookup(BIOTIPO, v);
export const suplementoCatLabel = (v) => lookup(SUPLEMENTO_CAT, v, false);

/**
 * Contadores en singular cuando toca (punto 4.18).
 *
 * «No registraste la dieta 1 día de los últimos 1», «Entreno, 1 comidas», «1 ejercicios
 * programados». Jesús lo pidió como barrido: «conviene barrer todos los contadores de la
 * app». Cada sitio lo resolvía por su cuenta o no lo resolvía, así que aquí vive uno.
 *
 *   plural(1, 'día')            -> "1 día"
 *   plural(3, 'día')            -> "3 días"
 *   plural(1, 'vez', 'veces')   -> "1 vez"
 *
 * El plural por defecto es +s, que cubre día/comida/semana/ejercicio/alimento. Cuando no
 * valga (vez/veces, mes/meses), se pasa el segundo.
 */
export const plural = (n, singular, plural_ = null) => {
    const cantidad = Number(n) || 0;
    return `${cantidad} ${Math.abs(cantidad) === 1 ? singular : (plural_ || singular + 's')}`;
};
