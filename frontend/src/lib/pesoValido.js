/**
 * QUE UN PESO SEA UN PESO (#48 del informe del 15-08).
 *
 * Lo que encontró Jesús en su histórico: «77,1 → 94 → 75 → 94 → 50 kg, saltos de 44 kg
 * entre ajustes seguidos. Sin validación ni aviso». De ese número salen la gráfica, el
 * ritmo de cambio, el ajuste del mes y lo que lee el asistente, así que un dedazo no se
 * queda quieto en su fila: mueve el método entero.
 *
 * Dos filtros, y a propósito no son el mismo:
 *
 *   - EL RANGO. Fuera de 25-300 kg no es un peso, es una errata (o los gramos). Se rechaza
 *     y se deja lo que hubiera. Es el mismo rango que valida el servidor en el reporte y en
 *     el check-in, para que no haya una puerta más blanda que la otra.
 *   - EL SALTO. 10 kg de diferencia con el pesaje anterior puede ser verdad -- alguien que
 *     vuelve después de un año -- así que aquí no se bloquea: se pregunta. Confirmar y
 *     seguir, o corregir.
 *
 * `revisarPeso` no pinta nada ni decide cómo se pregunta: devuelve qué pasa y con qué
 * frase, y cada pantalla lo enseña con lo que ya usa (toast para el error, el diálogo de
 * confirmación para el salto).
 */

export const PESO_MIN = 25;
export const PESO_MAX = 300;
// A partir de aquí se pregunta. Diez kilos entre dos pesajes es mucho hasta para quien
// vuelve tras un parón, y es donde empiezan los dedazos de las pruebas (77 → 94).
export const SALTO_QUE_CANTA = 10;

// Coma decimal, y sin decimales cuando son cero: «75 kg», «77,1 kg».
export const kg = (n) => {
    const v = Math.round(Number(n) * 10) / 10;
    return Number.isFinite(v) ? String(v).replace('.', ',') : '';
};

/**
 * @param {*} valor    lo que ha escrito el cliente (texto o número)
 * @param {*} anterior su último peso conocido, si lo hay
 * @returns {{ok: boolean, peso?: number, error?: string, confirmar?: string}}
 *          `error` = no se guarda. `confirmar` = se guarda si él lo confirma.
 */
export function revisarPeso(valor, anterior = null) {
    const peso = Number(String(valor ?? '').replace(',', '.'));
    if (!Number.isFinite(peso) || peso <= 0) {
        return { ok: false, error: 'Escribe tu peso en kilos, por ejemplo 78,4.' };
    }
    if (peso < PESO_MIN || peso > PESO_MAX) {
        return {
            ok: false,
            error: `${kg(peso)} kg no parece un peso. Ponlo en kilos, entre ${PESO_MIN} y ${PESO_MAX}.`,
        };
    }
    const previo = Number(anterior);
    if (Number.isFinite(previo) && previo > 0) {
        const salto = Math.abs(peso - previo);
        if (salto >= SALTO_QUE_CANTA) {
            return {
                ok: true,
                peso,
                confirmar: `Tu último peso fue ${kg(previo)} kg y ahora pones ${kg(peso)} kg: `
                    + `son ${kg(salto)} kg de diferencia. ¿Está bien?`,
            };
        }
    }
    return { ok: true, peso, confirmar: null };
}
