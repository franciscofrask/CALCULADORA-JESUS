/**
 * Las CUATRO fotos de la comparativa y sus reglas (documento de Jesús del 05-08, punto 3.2).
 *
 * Cada foto responde a algo:
 *   de dónde vengo · dónde empezó esta fase · qué he hecho este mes · cómo estoy hoy
 *
 * Reglas suyas:
 *   - La inicial no se mueve nunca de la izquierda; lo que rota es la del medio.
 *   - Si dos etiquetas apuntan a la MISMA foto, se enseña una sola vez con las dos
 *     etiquetas. Pasa el primer mes de una fase nueva, cuando nunca ha cambiado de fase,
 *     y en el mes 2.
 *   - Nunca más de cuatro, nunca la misma dos veces.
 *
 * Con eso el número sale solo y cuadra con su tabla: mes 1 → 1, mes 2 → 2, mes 3 en
 * adelante → 3, y 4 solo tras un cambio de fase.
 *
 * La misma lógica vive en el backend (core/informe_mensual.comparativa_de_fotos) para el
 * informe que se le manda al cliente. Si se toca una, hay que tocar la otra.
 */

export const TITULO_ETIQUETA = {
    inicial: 'De dónde vengo',
    inicio_fase: 'Dónde empezó esta fase',
    mes_anterior: 'Qué he hecho este mes',
    actual: 'Cómo estoy hoy',
};

/**
 * @param {Array<{fecha: string, fotos: Array, peso?: number, medidas?: object}>} sesiones
 *        Días con fotos, en cualquier orden.
 * @param {string|null} faseDesde  Día en que empezó la fase actual (perfil.fase_desde).
 * @returns {Array} hasta cuatro sesiones, de más antigua a más reciente, con `etiquetas`.
 */
export function construirComparativa(sesiones, faseDesde) {
    const orden = [...(sesiones || [])].filter(s => s.fecha && s.fotos?.length)
        .sort((a, b) => a.fecha.localeCompare(b.fecha));
    if (!orden.length) return [];

    const inicial = orden[0];
    const actual = orden[orden.length - 1];
    const mesAnterior = orden.length > 1 ? orden[orden.length - 2] : null;
    // La primera sesión con fotos desde que arrancó la fase. Sin fase_desde no hay
    // etiqueta, y entonces la comparativa se queda en tres, que es lo que él pide.
    const inicioFase = faseDesde ? orden.find(s => s.fecha >= faseDesde) : null;

    const candidatos = [
        ['inicial', inicial],
        ['inicio_fase', inicioFase],
        ['mes_anterior', mesAnterior],
        ['actual', actual],
    ];
    const porFecha = new Map();
    for (const [etiqueta, s] of candidatos) {
        if (!s) continue;
        const ya = porFecha.get(s.fecha);
        if (ya) { ya.etiquetas.push(etiqueta); continue; }
        porFecha.set(s.fecha, { ...s, etiquetas: [etiqueta] });
    }
    return [...porFecha.values()].sort((a, b) => a.fecha.localeCompare(b.fecha)).slice(0, 4);
}
