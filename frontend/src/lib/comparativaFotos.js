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

/*
 * EL SELECTOR DE TOMAS (doc de Jesús del 2-09, fase 3; Francisco, 4-09).
 *
 * «Elegir otra foto» abre un selector con cuatro atajos con nombre (mi primera foto ·
 * inicio de este ciclo · fin del ciclo anterior · hoy) y debajo las tomas agrupadas por
 * ciclo. Lo que hay aquí es la parte que no pinta nada: convertir lo que devuelve
 * GET /reports/puntos en la lista que enseña `SelectorDeTomas` y, a la vuelta, saber qué
 * rótulo y qué nota lleva la toma que el cliente ha elegido. Sirve igual para las fotos
 * y para las medidas: cambia lo que hay dentro de cada toma, no la forma de elegirla.
 *
 * Las dos reglas del doc, aplicadas aquí:
 *   - Un atajo sin dato no se esconde: sale apagado (id null) con su nota.
 *   - Siempre el mismo ángulo: al elegir una toma de fotos se prefiere la pose de la foto
 *     de hoy, y si esa toma no la tiene se enseña la que hay y se dice.
 */

/** Las cuatro claves de `atajos_fotos` y `atajos_medidas`, en el orden de la maqueta. */
export const ORDEN_ATAJOS = ['mi_primera_foto', 'inicio_de_este_ciclo', 'fin_del_ciclo_anterior', 'hoy'];

/** Lo que dice cada atajo en el selector: el de las fotos y el de las medidas. */
export const TEXTO_ATAJO = {
    fotos: {
        mi_primera_foto: 'Mi primera foto',
        inicio_de_este_ciclo: 'Inicio de este ciclo',
        fin_del_ciclo_anterior: 'Fin del ciclo anterior',
        hoy: 'Hoy',
    },
    medidas: {
        mi_primera_foto: 'Mi primera toma',
        inicio_de_este_ciclo: 'Inicio de este ciclo',
        fin_del_ciclo_anterior: 'Fin del ciclo anterior',
        hoy: 'Hoy',
    },
};

/** El rótulo que lleva encima la foto (clave de ROTULO_DOS_FOTOS) cuando se ha elegido
 *  por atajo. */
const ROTULO_DE_ATAJO = {
    mi_primera_foto: 'primera',
    inicio_de_este_ciclo: 'inicio_ciclo',
    fin_del_ciclo_anterior: 'fin_ciclo_anterior',
    hoy: 'hoy',
};
ROTULO_DOS_FOTOS.fin_ciclo_anterior = 'Fin del ciclo anterior';

export const rotuloDeAtajo = (clave) => ROTULO_DE_ATAJO[clave] || null;

/** El mismo rótulo, en minúscula y para ir detrás de una fecha en una cabecera de medidas:
 *  «30 may · inicio del ciclo». */
export const CABECERA_DE_ATAJO = {
    mi_primera_foto: 'mi primera toma',
    inicio_de_este_ciclo: 'inicio del ciclo',
    fin_del_ciclo_anterior: 'fin del ciclo anterior',
    hoy: 'hoy',
};

/** Un atajo de /reports/puntos llega como id, como {id, nota} o como null. Aquí se lee
 *  igual venga como venga. */
export const leerAtajo = (valor) => {
    if (valor == null) return { id: null, nota: null };
    if (typeof valor === 'object') return { id: valor.id ?? null, nota: valor.nota || null };
    return { id: valor, nota: null };
};

/** Un atajo por su clave dentro de `atajos_fotos` o `atajos_medidas`. Los que van como id
 *  a secas (`mi_primera_foto`, `hoy`) llevan su nota al lado en `<clave>_nota` (contrato
 *  del 4-09, core/puntos.py); y en las medidas «mi primera foto» se llama también
 *  `mi_primera_toma`, que es el mismo atajo con nombre de medidas. */
export const leerAtajoDe = (crudo, clave) => {
    if (!crudo) return { id: null, nota: null };
    const alias = clave === 'mi_primera_foto' ? ['mi_primera_foto', 'mi_primera_toma', 'mi_primera'] : [clave];
    const usada = alias.find(a => crudo[a] != null) || clave;
    const { id, nota } = leerAtajo(crudo[usada]);
    return { id, nota: nota || crudo[`${usada}_nota`] || null };
};

/** Con el año cuando no es el de ahora: «Mi primera foto» puede ser de hace dos años y un
 *  «3 may» a secas mentiría con la fecha, que es justo lo que Jesús pide que no pase. */
export const fechaCorta = (f) => {
    if (!f) return '';
    const d = new Date(`${String(f).slice(0, 10)}T12:00:00`);
    if (isNaN(d)) return String(f);
    const conAnyo = d.getFullYear() !== new Date().getFullYear();
    return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short', ...(conAnyo ? { year: 'numeric' } : {}) });
};

/** La foto de una toma con el ángulo pedido; si no la tiene, la mejor que haya y se avisa. */
export const fotoConElAngulo = (fotos, angulo) => {
    const ordenadas = ordenarPorPose(fotos);
    if (!ordenadas.length) return { foto: null, sinAngulo: false };
    const igual = angulo ? ordenadas.find(f => f.pose === angulo) : null;
    return igual ? { foto: igual, sinAngulo: false } : { foto: ordenadas[0], sinAngulo: Boolean(angulo) };
};

export const avisoDeAngulo = (angulo) => (angulo ? `no tienes foto ${NOMBRE_POSE[angulo] || angulo} de esa fecha` : null);

// Las fotos de /reports/puntos, un día con fotos = una toma (como en la comparativa).
const _tomasDeFotos = (fotos) => {
    const porDia = new Map();
    for (const f of fotos || []) {
        const fecha = String(f?.fecha || f?.taken_at || '').slice(0, 10);
        if (!fecha || !f?.id) continue;
        if (!porDia.has(fecha)) porDia.set(fecha, { fecha, fotos: [], grupo: null, marca: null });
        const t = porDia.get(fecha);
        t.fotos.push(f);
        if (f.grupo && !t.grupo) t.grupo = f.grupo;
        if (f.marca && !t.marca) t.marca = f.marca;
    }
    return [...porDia.values()]
        .map(t => ({ ...t, fotos: ordenarPorPose(t.fotos) }))
        .sort((a, b) => a.fecha.localeCompare(b.fecha));
};

const _tomasDeMedidas = (tomas) => [...(tomas || [])]
    .filter(t => t?.id && t?.fecha)
    .map(t => ({ ...t, fecha: String(t.fecha).slice(0, 10) }))
    .sort((a, b) => a.fecha.localeCompare(b.fecha));

/** El rótulo de una toma elegida por ciclo, no por atajo: «Ciclo 3 · inicio». Sale del
 *  nombre del grupo, que el cuaderno da como «Ciclo 3 · junio a septiembre» o, para lo
 *  anterior al cuaderno, «Tramo 1 · junio a agosto»: se queda con lo de antes del punto
 *  (un tramo no es un ciclo y llamarlo así mentiría). Sin grupo, la fecha, que es lo
 *  único seguro. */
export const rotuloDeToma = (entrada) => {
    if (!entrada) return '';
    const g = entrada.grupo;
    const nombre = g?.etiqueta ? String(g.etiqueta).split(' · ')[0].trim() : null;
    const base = nombre || (g?.numero != null ? `Ciclo ${g.numero}` : fechaCorta(entrada.fecha));
    return entrada.marca ? `${base} · ${entrada.marca}` : base;
};

/**
 * Prepara el selector a partir de /reports/puntos.
 *
 * @param {'fotos'|'medidas'} tipo
 * @param {object} datos        lo que devuelve GET /reports/puntos
 * @param {string|null} angulo  la pose de la foto de hoy (solo fotos)
 * @param {string|null} derechaId  la toma que ya está a la derecha: se apaga en los atajos
 *        («es la que ya ves a la derecha») y no sale en las pastillas, porque comparar una
 *        foto consigo misma no dice nada
 * @returns {{atajos: Array, grupos: Array, entradas: Array, buscar: function}}
 *          `buscar(id)` devuelve la entrada de esa toma con `rotulo`, `cabecera`, `atajo`,
 *          `nota` y `aviso` ya resueltos, o null si no está.
 */
export function prepararSelector({ tipo, datos, angulo = null, derechaId = null }) {
    const esFotos = tipo === 'fotos';
    const tomas = esFotos ? _tomasDeFotos(datos?.fotos) : _tomasDeMedidas(datos?.tomas_medidas);
    const entradas = tomas.map(t => {
        if (!esFotos) {
            return { id: t.id, fecha: t.fecha, grupo: t.grupo || null, marca: t.marca || null, toma: t, foto: null, sinAngulo: false, ids: [t.id] };
        }
        const { foto, sinAngulo } = fotoConElAngulo(t.fotos, angulo);
        return { id: foto.id, fecha: t.fecha, grupo: t.grupo, marca: t.marca, toma: t, foto, sinAngulo, ids: t.fotos.map(f => f.id) };
    });
    const porId = new Map();
    for (const e of entradas) for (const id of e.ids) porId.set(id, e);
    const derecha = derechaId != null ? porId.get(derechaId) || null : null;

    const textos = TEXTO_ATAJO[esFotos ? 'fotos' : 'medidas'];
    const sinDato = esFotos ? 'no tienes foto de ese momento' : 'no tienes medidas de ese momento';
    const crudo = (esFotos ? datos?.atajos_fotos : datos?.atajos_medidas) || {};
    const atajos = ORDEN_ATAJOS.map(clave => {
        const { id, nota } = leerAtajoDe(crudo, clave);
        const e = id != null ? porId.get(id) : null;
        if (!e) return { clave, texto: textos[clave], id: null, nota: nota || sinDato };
        if (derecha && e === derecha) return { clave, texto: textos[clave], id: null, nota: 'es la que ya ves a la derecha' };
        const aviso = e.sinAngulo ? avisoDeAngulo(angulo) : null;
        return { clave, texto: textos[clave], id: e.id, nota: [nota, aviso].filter(Boolean).join(' · ') || null };
    });

    // Los grupos, del ciclo más reciente al más antiguo (como la maqueta), y lo que no
    // tiene ciclo al final. El orden lo da el día en que arrancó cada uno según `ciclos`
    // (el número no vale: el tramo anterior al cuaderno y el primer ciclo son los dos «1»);
    // si una toma trae un grupo que no está ahí, va por la fecha de su primera toma.
    const inicioDe = new Map((datos?.ciclos || []).map(c => [c.id, String(c.inicio || '').slice(0, 10)]));
    const grupos = new Map();
    for (const e of entradas) {
        if (derecha && e === derecha) continue;
        const g = e.grupo;
        const clave = g?.id || 'sin-ciclo';
        if (!grupos.has(clave)) {
            grupos.set(clave, {
                id: clave,
                etiqueta: g?.etiqueta || (g?.numero != null ? `Ciclo ${g.numero}` : 'Sin ciclo'),
                aproximado: Boolean(g?.aproximado),
                orden: g ? (inicioDe.get(g.id) || e.fecha) : '',
                items: [],
            });
        }
        grupos.get(clave).items.push({ id: e.id, texto: fechaCorta(e.fecha), marca: e.marca || null });
    }
    const listaGrupos = [...grupos.values()].sort((a, b) => b.orden.localeCompare(a.orden));

    const buscar = (id) => {
        const e = id != null ? porId.get(id) : null;
        if (!e) return null;
        const atajo = atajos.find(a => a.id != null && a.id === e.id) || null;
        const aviso = e.sinAngulo ? avisoDeAngulo(angulo) : null;
        const notaBackend = atajo ? leerAtajoDe(crudo, atajo.clave).nota : null;
        return {
            ...e,
            atajo: atajo?.clave || null,
            rotulo: atajo ? rotuloDeAtajo(atajo.clave) : rotuloDeToma(e),
            cabecera: atajo ? CABECERA_DE_ATAJO[atajo.clave] : rotuloDeToma(e).toLowerCase(),
            nota: notaBackend,
            aviso,
        };
    };

    return { atajos, grupos: listaGrupos, entradas, buscar };
}
