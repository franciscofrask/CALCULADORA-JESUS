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
import { num1 } from './numeros';

// El margen de Calma (margenValido = 4): un macro está bien mientras no se pase de 4 g.
// Es el mismo número que ya usaban `getMealStatus` y las tarjetas de comida.
export const MARGEN = 4;

/**
 * El margen de un macro: LOS 4 G PLANOS, SIEMPRE (Francisco, 3-09-2026).
 *
 * Aquí vivía un margen proporcional -- una cuarta parte de lo pedido, mínimo 1,5 -- nacido
 * del intra: pide 9 g de proteína y con el margen de 4 un «5/9» salía como «comida
 * cuadrada» faltándole casi la mitad. Pero ese estrechado chocaba con la regla validada
 * del punto 11.1 de Jesús («de 1 a 4, falte o sobre, es válido y sale en verde. Igual en
 * toda la app, sin excepciones»): una grasa de 13 sobre 10 decía «sobran 3» en naranja
 * cuando el 11.1 la da por válida.
 *
 * Francisco eligió el 11.1 a la letra, SABIENDO que el caso del intra vuelve a caber en el
 * margen (5/9 saldrá «válido»): «1-4 plano en todo». Si algún día se revierte, es aquí y
 * en `NutritionChatbot.margen_de`, que es el mismo criterio en el backend.
 */
export const margenDe = () => MARGEN;

export const NOMBRE_MACRO = { P: 'proteína', H: 'hidratos', G: 'grasa' };

// LOS MACROS EN LOS QUE PASARSE ES UN FALLO. La proteína no está, y esa es toda la
// decisión de Jesús: por arriba solo se corrige lo que sobra de hidratos y de grasa.
export const MACROS_QUE_SE_PASAN = ['H', 'G'];

// Con coma decimal, como el resto de los números que se le enseñan a una persona
// (Jesús, 15-08, fallo 43). El redondeo y el «sin decimales cuando son cero» no cambian.
export const fmtGramos = (x) => num1(x);

/**
 * ¿Este macro se ha pasado? La única definición de «pasarse» de la app.
 *
 * `esPeri`: en el intra y en el post la grasa no cuenta para nada, así que tampoco puede
 * pasarse (mismo criterio que ya tenía `getMealStatus`).
 */
export const seExcede = (key, servido, objetivo, { margen = MARGEN, esPeri = false } = {}) => {
    if (!MACROS_QUE_SE_PASAN.includes(key)) return false;
    if (esPeri && key === 'G') return false;
    // ESTRICTO, no >=: «de 1 a 4, falte o sobre, es válido» (punto 11.1) incluye el 4
    // clavado. Con >= aquí, un +4,0 exacto decía «válido» en la palabra y «te pasas» en el
    // aviso a la vez (alineado el 3-09, con la decisión del margen plano).
    return (servido || 0) - (objetivo || 0) > margen;
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
