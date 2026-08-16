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
 * DOS TOPES, Y NO SON LO MISMO.
 *
 * El de arriba (2000 g) es plano y es un muro: por ahí no se pasa nadie. Con solo ese, en la
 * Comida 3 de un cliente había 1.000 g de leche de almendras, un litro (Jesús, 16-08).
 *
 * Este otro es el que ya usaba el asistente: cuánto de ESE alimento cabe en una comida de
 * verdad (400 g de leche, 30 g de aceite, 60 g de proteína en polvo, 3 huevos). Lo calcula el
 * backend y viaja en la ficha del alimento como `max_razonable`.
 *
 * Y se comporta como el asistente: AVISA, no bloquea. La cantidad se pone igual, porque a
 * veces se quiere así y el cliente sabe lo que come; lo que no puede es pasar en silencio.
 */
export const topeRazonable = (food) => {
    const t = Number(food?.max_razonable);
    return Number.isFinite(t) && t > 0 ? t : 0;
};

/**
 * El aviso de que se pasa de lo razonable, o null si no se pasa (o si no hay tope para ese
 * alimento, que es lo que ocurre con los que aún no han pasado por el catálogo).
 */
export const avisoRazonable = (food, gramos, { porUnidad = false, pesoUnidad = 0 } = {}) => {
    const tope = topeRazonable(food);
    if (!tope || !(gramos > tope)) return null;
    const nombre = food?.nombre || 'Este alimento';
    const peso = porUnidad ? (pesoUnidad || food?.peso_unidad || food?.racion || 0) : 0;
    // En los de unidades se avisa en unidades, que es como se piensan: «3 huevos», no «190 g».
    const enUnidades = porUnidad && peso > 0;
    const escribe = (g) => (enUnidades ? `${Math.round((g / peso) * 2) / 2} ud` : `${Math.round(g)} g`);
    return `${nombre}: ${escribe(gramos)} es mucho para una comida. Lo normal es no pasar de ${escribe(tope)}. Lo dejamos puesto, pero míralo.`;
};

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
 *
 * Y aparte, `aviso`: el texto de que se pasa de lo razonable PARA ESE ALIMENTO (un litro de
 * leche entra dentro de los 2000 g y aun así no es una cantidad). Va suelto y no como estado
 * porque no cambia lo que hay que hacer: la cantidad se pone igual y solo hay que decirlo.
 */
export const leerCantidad = (valor, { porUnidad = false, pesoUnidad = 100, minimo = 1, alimento = null } = {}) => {
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
    return { estado: 'ok', gramos, aviso: avisoRazonable(alimento, gramos, { porUnidad, pesoUnidad: peso }) };
};
