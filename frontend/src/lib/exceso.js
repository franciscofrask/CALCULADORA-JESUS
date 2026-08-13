/**
 * PASARSE, EN UN SOLO SITIO.
 *
 * Jesús, 13-08-2026: «Sí, se dice por cuánto: "te pasas 8 g de grasa". Y el rojo por
 * arriba, solo en hidratos y grasa — pasarse de proteína no.» Y el porqué, con sus
 * palabras: «hoy pasarse de proteína pinta el aro rojo, y en tu método eso no es un fallo:
 * le estás marcando en rojo, todos los días, algo que ha hecho bien».
 *
 * El criterio vivía repetido en siete sitios -- `getMealStatus` y `getDayStatus` en
 * NutritionPage, las dos funciones de MealCard, las barras de móvil y de escritorio de
 * DayHeader y la barra de DaySummary --, cada uno con su propio margen y su propia forma
 * de decirlo. Cambiar la regla significaba acertar en los siete. Ahora se cambia aquí.
 *
 * Lo que NO cambia: quedarse corto. Jesús solo habló del exceso, así que «faltan 12 g»
 * sigue avisando igual en los tres macros.
 */

// El margen de Calma (margenValido = 4): un macro está bien mientras no se pase de 4 g.
// Es el mismo número que ya usaban `getMealStatus` y las tarjetas de comida.
export const MARGEN = 4;

export const NOMBRE_MACRO = { P: 'proteína', H: 'hidratos', G: 'grasa' };

// LOS MACROS EN LOS QUE PASARSE ES UN FALLO. La proteína no está, y esa es toda la
// decisión de Jesús: por arriba solo se corrige lo que sobra de hidratos y de grasa.
export const MACROS_QUE_SE_PASAN = ['H', 'G'];

export const fmtGramos = (x) => {
    const n = Math.round((x || 0) * 10) / 10;
    return Number.isInteger(n) ? String(n) : n.toFixed(1);
};

/**
 * ¿Este macro se ha pasado? La única definición de «pasarse» de la app.
 *
 * `esPeri`: en el intra y en el post la grasa no cuenta para nada, así que tampoco puede
 * pasarse (mismo criterio que ya tenía `getMealStatus`).
 */
export const seExcede = (key, servido, objetivo, { margen = MARGEN, esPeri = false } = {}) => {
    if (!MACROS_QUE_SE_PASAN.includes(key)) return false;
    if (esPeri && key === 'G') return false;
    return (servido || 0) - (objetivo || 0) >= margen;
};

/** Los macros pasados, con sus gramos de más: [{ key: 'G', gramos: 8 }]. */
export const excesos = (servido = {}, objetivo = {}, opciones = {}) =>
    ['P', 'H', 'G']
        .filter(k => seExcede(k, servido[k], objetivo[k], opciones))
        .map(k => ({ key: k, gramos: (servido[k] || 0) - (objetivo[k] || 0) }));

/**
 * «8 g de grasa», o «12 g de hidratos y 8 g de grasa». Sin el «Te pasas» delante, para
 * que cada sitio lo monte con su tipografía; el texto es el mismo que ya usa el chat
 * (`ChatMealSummary`), y por eso la app dice lo mismo en todas partes.
 */
export const textoExceso = (servido, objetivo, opciones) => {
    const lista = excesos(servido, objetivo, opciones)
        .map(({ key, gramos }) => `${fmtGramos(gramos)} g de ${NOMBRE_MACRO[key]}`);
    if (!lista.length) return '';
    return lista.length === 1 ? lista[0] : `${lista.slice(0, -1).join(', ')} y ${lista[lista.length - 1]}`;
};

/** «Te pasas 8 g de grasa» ya montado, para los sitios que enseñan una frase suelta. */
export const fraseExceso = (servido, objetivo, opciones) => {
    const t = textoExceso(servido, objetivo, opciones);
    return t ? `Te pasas ${t}` : '';
};
