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
 *
 * ESTAS CUATRO SON LAS DEL PANEL Y LAS DEL INFORME. La pantalla del cliente ya no las usa:
 * desde el doc de Jesús del 2-09 el cliente ve DOS fotos y ya (`elegirDosFotos`, abajo).
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

/*
 * LAS DOS DEL CLIENTE (doc de Jesús del 2-09, «Y la comparativa de fotos»).
 *
 * «Dos fotos, siempre. Inicio del ciclo contra hoy, las dos con su peso.» Y sus dos avisos
 * para que no falle:
 *   - Si en un ciclo no subió fotos, ese hito no existe: se coge la más cercana Y SE DICE.
 *     Nunca enseñar un hueco ni mentir con la fecha.
 *   - Siempre el mismo ángulo: comparar un frente con un perfil no dice nada.
 */

/** El orden en que se prefiere una pose: de frente es la que más dice, y una foto sin
 *  pose (las viejas de Calma que no la traen en el nombre) va la última. */
export const POSE_ORDEN = ['frente', 'perfil', 'espalda'];

export const NOMBRE_POSE = { frente: 'de frente', perfil: 'de perfil', espalda: 'de espalda' };

/** Los rótulos de las dos fotos. Se pintan en mayúsculas por CSS, como los de siempre. */
export const ROTULO_DOS_FOTOS = {
    inicio_ciclo: 'Inicio del ciclo',
    primera: 'Mi primera foto',
    hoy: 'Hoy',
};

/** A partir de cuántos días de distancia se dice que la foto no es del inicio del ciclo
 *  sino «la más próxima». Una semana: las fotos suben con el reporte y el reporte puede
 *  caer unos días antes o después del arranque. */
export const DIAS_PARA_DECIR_LA_MAS_PROXIMA = 7;

const _rangoPose = (pose) => {
    const i = POSE_ORDEN.indexOf(pose);
    return i < 0 ? POSE_ORDEN.length : i;
};

/** Las fotos de una sesión, de frente primero y las sin pose al final. */
export const ordenarPorPose = (fotos) =>
    [...(fotos || [])].sort((a, b) => _rangoPose(a.pose) - _rangoPose(b.pose));

const _dias = (a, b) =>
    Math.abs(new Date(`${a}T12:00:00`).getTime() - new Date(`${b}T12:00:00`).getTime()) / 864e5;

/**
 * Elige las dos fotos del cliente: la de HOY (la sesión más reciente) y la del INICIO.
 *
 * La regla, paso a paso:
 *   1. HOY es la última sesión; su foto es la de frente si la hay, si no la de perfil, si
 *      no la de espalda. Ese es el ÁNGULO al que se ajusta la otra.
 *   2. Las candidatas para la de la izquierda son las sesiones ANTERIORES a hoy (nunca la
 *      misma foto dos veces). Sin ninguna, no hay comparativa: `inicio` sale null.
 *   3. La referencia es el inicio del ciclo (`cycle_start`) cuando lo hay, hay al menos dos
 *      sesiones anteriores y alguna de ellas está más cerca del arranque que la de hoy.
 *      Si no se cumple algo de eso, la referencia es la primera foto de la historia y el
 *      rótulo «Mi primera foto», que nunca miente.
 *   4. Entre las candidatas mandan las que tienen el ángulo de hoy; de esas, la más cercana
 *      a la referencia (en empate, la posterior: la que ya está dentro del ciclo). Si
 *      ninguna tiene ese ángulo, se coge la más cercana de las que hay y se avisa.
 *   5. Se dice lo que no es exacto: «la más próxima al inicio del ciclo» si queda a más de
 *      una semana del arranque, «la primera de frente» si la primera sesión no tenía ese
 *      ángulo, y «no tienes foto de frente de esa fecha» cuando no hubo forma de igualar.
 *
 * @param {Array<{fecha: string, fotos: Array<{pose?: string}>}>} sesiones  Días con fotos.
 * @param {string|null} inicioCiclo  Día en que arrancó el ciclo (perfil.cycle_start), ISO.
 * @returns {{hoy: object, inicio: object|null}|null}  Cada lado trae `sesion`, `foto`,
 *          `rotulo` (clave de ROTULO_DOS_FOTOS), `nota` y `aviso` (textos o null).
 */
export function elegirDosFotos(sesiones, inicioCiclo) {
    const orden = [...(sesiones || [])].filter(s => s.fecha && s.fotos?.length)
        .sort((a, b) => a.fecha.localeCompare(b.fecha));
    if (!orden.length) return null;

    const sesionHoy = orden[orden.length - 1];
    const fotoHoy = ordenarPorPose(sesionHoy.fotos)[0];
    const angulo = fotoHoy.pose || null;
    const hoy = { sesion: sesionHoy, foto: fotoHoy, rotulo: 'hoy', nota: null, aviso: null };

    const antes = orden.slice(0, -1);
    if (!antes.length) return { hoy, inicio: null };

    const arranque = inicioCiclo ? String(inicioCiclo).slice(0, 10) : null;
    const masCercaQueHoy = arranque
        ? Math.min(...antes.map(s => _dias(s.fecha, arranque))) <= _dias(sesionHoy.fecha, arranque)
        : false;
    const porCiclo = Boolean(arranque) && antes.length >= 2 && masCercaQueHoy;
    const referencia = porCiclo ? arranque : antes[0].fecha;

    const conAngulo = angulo ? antes.filter(s => s.fotos.some(f => f.pose === angulo)) : antes;
    const sinAngulo = Boolean(angulo) && !conAngulo.length;
    const candidatas = sinAngulo ? antes : conAngulo;

    let mejor = null, distancia = Infinity;
    for (const s of candidatas) {
        const d = _dias(s.fecha, referencia);
        if (d < distancia || (d === distancia && s.fecha >= referencia)) { mejor = s; distancia = d; }
    }
    const foto = (angulo && !sinAngulo)
        ? mejor.fotos.find(f => f.pose === angulo)
        : ordenarPorPose(mejor.fotos)[0];

    let nota = null;
    if (porCiclo && distancia > DIAS_PARA_DECIR_LA_MAS_PROXIMA) nota = 'la más próxima al inicio del ciclo';
    else if (!porCiclo && mejor !== antes[0] && angulo) nota = `la primera ${NOMBRE_POSE[angulo]}`;
    const aviso = sinAngulo ? `no tienes foto ${NOMBRE_POSE[angulo]} de esa fecha` : null;

    return {
        hoy,
        inicio: { sesion: mejor, foto, rotulo: porCiclo ? 'inicio_ciclo' : 'primera', nota, aviso },
    };
}
