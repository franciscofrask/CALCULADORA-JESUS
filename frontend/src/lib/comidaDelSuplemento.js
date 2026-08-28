/**
 * LAS OPCIONES DE «¿CON QUÉ COMIDA SALE?», Y CÓMO SE LEEN EN CASTELLANO.
 *
 * Aquí NO se decide nada: quien decide es el servidor (core/comida_del_suplemento.py) y
 * manda el resultado en `en_comidas`. Esto es solo la lista de opciones y cómo se escribe
 * en pantalla lo que él ha contestado.
 *
 * Se hace así a propósito. Hoy mismo se descubrió lo que pasa cuando el mismo número lo
 * calculan dos sitios: uno de los dos acaba mintiendo. Con los suplementos sería peor,
 * porque no hay número que comparar -- el coach vería una cosa en su panel y el cliente
 * otra en su Inicio, y nadie se enteraría.
 *
 * «La primera» y «la última» y no «Comida 1» y «Comida 4» porque el cliente puede tener de
 * una a cuatro comidas: la cena es la 3 en unos y la 4 en otros.
 */

//: El valor vacío es «que lo deduzca del ¿Cuándo?», que es lo que tienen casi todos.
export const COMIDAS_DEL_SUPLEMENTO = [
    ['', 'Automático'],
    ['primera', 'La primera comida'],
    ['ultima', 'La última comida'],
    ['C1', 'Comida 1'],
    ['C2', 'Comida 2'],
    ['C3', 'Comida 3'],
    ['C4', 'Comida 4'],
    ['ninguna', 'En ninguna'],
];

const NOMBRES = {
    primera: 'la primera comida',
    ultima: 'la última comida',
    C1: 'la Comida 1', C2: 'la Comida 2', C3: 'la Comida 3', C4: 'la Comida 4',
};

/**
 * Dónde sale, en una frase, tal y como lo ha resuelto el servidor.
 *
 * `en_comidas` viaja en cada línea del protocolo. Lista vacía significa «en ninguna», y esa
 * es justo la que hay que decir con todas las letras: es la que pasa desapercibida.
 */
export const dondeSale = (enComidas) => {
    const huecos = (enComidas || []).map((h) => NOMBRES[h]).filter(Boolean);
    if (!huecos.length) return 'No sale debajo de ninguna comida';
    if (huecos.length === 1) return `Sale en ${huecos[0]}`;
    return `Sale en ${huecos.slice(0, -1).join(', ')} y en ${huecos[huecos.length - 1]}`;
};

//: Para pintarlo en gris cuando no sale en ninguna, que es lo que hay que mirar dos veces.
export const noSaleEnNinguna = (enComidas) => !(enComidas || []).length;
