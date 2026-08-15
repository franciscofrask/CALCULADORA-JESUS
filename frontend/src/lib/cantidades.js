/**
 * LA CANTIDAD QUE ESCRIBE EL CLIENTE, LEÍDA EN UN SOLO SITIO.
 *
 * Dos fallos de Jesús del 15-08-2026 nacían de que cada campo de cantidad se leía por su
 * cuenta:
 *
 *   - Fallo 4: escribir «-50» o «abc» BORRABA el ingrediente. `parseFloat('abc')` es NaN,
 *     NaN caía en el «por debajo del mínimo» y el mínimo significaba «quítalo». Un guion
 *     puesto sin querer y el alimento desaparecía, sin avisar y sin deshacer.
 *   - Fallo 28: no había tope por arriba. 999999 g de leche de coco entraban tan tranquilos
 *     («sobran 12006.6g»), casi una tonelada de comida en una comida.
 *
 * Aquí no se decide qué hacer -- eso es de cada pantalla, que es la que sabe si puede
 * avisar o deshacer --, solo se dice QUÉ se ha escrito. Lo que no se entiende se rechaza:
 * la cantidad anterior se queda como estaba.
 */

/** Lo máximo que se admite de un mismo alimento en una comida, en gramos o mililitros. */
export const TOPE_GRAMOS = 2000;

export const AVISO_TOPE = `Como mucho ${TOPE_GRAMOS} g o ml de un mismo alimento en una comida.`;
export const AVISO_NO_ES_NUMERO = 'Escribe la cantidad con números. La dejamos como estaba.';
export const AVISO_NEGATIVO = 'La cantidad no puede ser negativa. La dejamos como estaba.';

/**
 * Lee lo tecleado en un campo de cantidad.
 *
 * En los alimentos por unidades se escriben UNIDADES ("2 huevos"), que es como los piensa
 * el cliente; aquí salen ya pasadas a gramos, que es como se guardan.
 *
 * Devuelve `{ estado, gramos }`:
 *   ok ..................... `gramos` es la cantidad buena
 *   no_es_numero ........... no se toca nada
 *   negativo ............... no se toca nada
 *   por_debajo_del_minimo .. el cliente está diciendo «quítalo»
 *   pasa_del_tope .......... `gramos` viene ya recortado al tope
 */
export const leerCantidad = (valor, { porUnidad = false, pesoUnidad = 100, minimo = 1 } = {}) => {
    // Se acepta la coma como decimal, que es como se escribe aquí. `Number` y no
    // `parseFloat`: parseFloat('12abc') da 12, y eso no es lo que ha escrito nadie.
    const texto = String(valor ?? '').trim().replace(',', '.');
    const escrito = texto === '' ? NaN : Number(texto);
    if (!Number.isFinite(escrito)) return { estado: 'no_es_numero' };
    if (escrito < 0) return { estado: 'negativo' };

    const peso = pesoUnidad > 0 ? pesoUnidad : 100;
    const gramos = porUnidad ? escrito * peso : escrito;
    if (gramos < minimo) return { estado: 'por_debajo_del_minimo', gramos };
    if (gramos > TOPE_GRAMOS) {
        // En los de unidades el tope se baja a la unidad entera de debajo: «37,7 ud» no es
        // una cantidad que nadie sirva.
        const tope = porUnidad ? Math.floor(TOPE_GRAMOS / peso) * peso : TOPE_GRAMOS;
        return { estado: 'pasa_del_tope', gramos: Math.max(minimo, tope) };
    }
    return { estado: 'ok', gramos };
};
