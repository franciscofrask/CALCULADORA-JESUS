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

// ── Nombres técnicos que se estaban colando en el panel (#64 del informe del 15-08) ──
//
// «RETO12EN12_GOLD, pendiente_pago, nivel1, membresia, y en Cobros el concepto llega de
// Stripe en inglés: 1 × El Lunes Empiezo (at €81.07 / month)». Son códigos de la base y
// texto de la pasarela: valen para consultar, no para leer.

const ESTADO_CLIENTE = {
    activo: 'Activo',
    pendiente_pago: 'Pago pendiente',
    impagado: 'Impagado',
    pausado: 'En pausa',
    baja: 'Baja',
    cancelado: 'Cancelado',
    inactivo: 'Inactivo',
    registro_incompleto: 'Registro sin terminar',
    sin_estado: 'Sin estado',
};
export const estadoClienteLabel = (v) => (v ? lookup(ESTADO_CLIENTE, v) : 'Sin estado');

/**
 * El nombre del plan tal y como lo llamamos de cara al cliente.
 *
 * El código («reto12en12_gold», «nivel1») solo sirve si no hay catálogo cargado, y ahí se
 * escribe legible en vez de gritarlo en mayúsculas.
 */
export const nombreDePlan = (code, catalogo) => {
    if (!code) return 'Sin plan';
    return catalogo?.[code]?.name || prettyToken(code);
};

// Ciclos de cobro como los escribe la pasarela.
const CICLO_PASARELA = {
    month: 'al mes', monthly: 'al mes',
    year: 'al año', yearly: 'al año', annual: 'al año',
    week: 'a la semana', weekly: 'a la semana',
    day: 'al día', daily: 'al día',
    quarter: 'al trimestre',
};

/**
 * El concepto de un cobro, en español y sin la letra de la pasarela.
 *
 *   «1 x El Lunes Empiezo (at €81.07 / month)» -> «El Lunes Empiezo (81,07 € al mes)»
 *   «2 × Nivel 2 (at 150.00 EUR / year)»       -> «2 × Nivel 2 (150,00 € al año)»
 *
 * Lo que no reconoce lo deja tal cual: es preferible un concepto raro que uno recortado.
 */
export const conceptoDeCobro = (txt) => {
    let s = String(txt || '').trim();
    if (!s) return '-';
    // «1 x » no dice nada: solo se mantiene la cantidad cuando de verdad hay varias.
    s = s.replace(/^(\d+)\s*[x×]\s*/i, (todo, n) => (Number(n) === 1 ? '' : `${n} × `));
    // «(at €81.07 / month)» -> «(81,07 € al mes)»
    s = s.replace(
        /\(\s*at\s*([€$£]?)\s*([\d.,]+)\s*([A-Z]{3})?\s*\/\s*([a-z]+)\s*\)/gi,
        (todo, simbolo, importe, iso, ciclo) => {
            const cada = CICLO_PASARELA[String(ciclo).toLowerCase()];
            if (!cada) return todo;
            const moneda = simbolo || { EUR: '€', USD: '$', GBP: '£' }[String(iso || '').toUpperCase()] || '€';
            // Coma decimal solo cuando el número es un «81.07» de la pasarela; un
            // «1,234.56» con miles se deja como viene antes que dejarlo mal.
            const cifra = /^\d+\.\d+$/.test(importe) ? importe.replace('.', ',') : importe;
            return `(${cifra} ${moneda} ${cada})`;
        });
    return s.trim() || '-';
};

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
