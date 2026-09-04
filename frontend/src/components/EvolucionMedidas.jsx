/**
 * LA EVOLUCIÓN DE CADA MEDIDA. La misma pieza para el coach y para el cliente, con dos
 * formas de leerla.
 *
 * Vivía suelta dentro de la ficha del panel (punto 35 del doc del 07-08). El doc del 16-08
 * (T6) la lleva también a la pantalla de Evolución del cliente: "la pantalla de Evolución
 * ya está hecha: es la pestaña Seguimiento de la ficha del cliente". Se extrae aquí en vez
 * de copiarla, porque son la misma tabla y tienen que decir lo mismo: si un día cambia la
 * forma de leer la diferencia, cambia en los dos sitios a la vez.
 *
 * EN EL PANEL (tono admin): la tabla de siempre, una fila por medida y una columna por
 * toma, hasta ocho, con la diferencia con la anterior y el «Total» contra la primera.
 * Tabla y no gráfico a propósito: son diez series a la vez, y en un gráfico de diez líneas
 * no se lee ninguna.
 *
 * EN LA APP DEL CLIENTE (tono cliente): DOS TOMAS Y SU DIFERENCIA (doc de Jesús del 2-09,
 * «Las medidas: comparar dos, como las fotos»; hecho el 4-09, fase 3). «La tabla de cuatro
 * columnas se cambia por dos tomas y su diferencia, con el mismo selector que las fotos.»
 * A la derecha la última toma («3 sept · hoy»), a la izquierda el inicio de este ciclo (o
 * la primera toma si no hay ciclo), y «Elegir otra toma» abre el mismo selector que la
 * comparativa de fotos. Si una medida falta en una de las dos se dice («no la mediste en
 * esa toma»), nunca un hueco. Las tomas llegan de GET /reports/puntos (`tomas_medidas`),
 * que ya funde las tres puertas por las que entra una medida.
 *
 * Lo único que cambia entre los dos sitios, aparte de la forma, es el `tono`: el panel es
 * oscuro a pelo y la app del cliente va con los colores del tema (que tiene modo claro). Y
 * el pie: en el lado del cliente habla el entrenador en primera persona («eso te lo digo
 * yo, no el color», doc de Jesús del 2-09) y en el panel se dice en tercera, que ahí lo
 * lee el coach.
 */
import React, { useMemo, useState } from 'react';
import { MEDIDAS, valorAnterior, diferencia } from '../lib/medidas';
import { useAuth } from '../context/AuthContext';
import usePuntos from '../hooks/usePuntos';
import SelectorDeTomas from './seguimiento/SelectorDeTomas';
import { prepararSelector, leerAtajoDe, fechaCorta } from '../lib/comparativaFotos';

// Las columnas caben hasta cierto punto: se enseñan las últimas y se dice cuántas quedan
// fuera, que es mejor que cortar en silencio.
const SESIONES_A_LA_VISTA = 8;

/** dd/mm, y con el año en dos cifras cuando las tomas no son del mismo año. */
const _cabeceraFecha = (iso, conAnio) => {
    const [a, m, d] = String(iso).slice(0, 10).split('-');
    return conAnio ? `${d}/${m}/${a.slice(2)}` : `${d}/${m}`;
};

const TONOS = {
    admin: {
        caja: 'rounded-xl border bg-[#111] border-[#222] p-5',
        titulo: 'text-xs font-bold text-white/40 uppercase tracking-wider',
        apunte: 'text-[10px] text-white/30',
        vacio: 'text-white/30 text-sm',
        cabecera: 'text-white/40 border-b border-[#222]',
        fila: 'border-b border-[#1a1a1a] last:border-0 hover:bg-white/[0.03]',
        medida: 'px-2 py-1.5 text-white/70 whitespace-nowrap sticky left-0 z-10 bg-[#111]',
        // El fondo de la columna fija: sin él, al desplazar se ve el número por debajo.
        fondoFijo: 'bg-[#111]',
        valor: 'text-white font-medium',
        igual: 'text-white/30',
        sube: 'text-brand',
        baja: 'text-emerald-400',
        pie: 'text-[10px] text-white/25 mt-2',
        pieTexto: 'En verde lo que baja y en naranja lo que sube. Sin juzgar: subir de brazo y subir de cintura no son lo mismo, y eso lo pone el coach, no el color.',
    },
    cliente: {
        caja: 'bg-card border border-border rounded-2xl p-4',
        titulo: 'text-xs font-bold text-foreground/40 uppercase tracking-wider',
        apunte: 'text-[10px] text-muted-foreground',
        vacio: 'text-muted-foreground text-sm',
        cabecera: 'text-muted-foreground border-b border-border',
        fila: 'border-b border-border/50 last:border-0',
        medida: 'px-2 py-1.5 text-foreground/70 whitespace-nowrap sticky left-0 z-10 bg-card',
        fondoFijo: 'bg-card',
        valor: 'text-foreground font-medium',
        igual: 'text-muted-foreground',
        sube: 'text-brand',
        baja: 'text-emerald-500',
        pie: 'text-[10px] text-muted-foreground mt-2',
        // En primera persona del entrenador (doc de Jesús del 2-09): al cliente se lo dice
        // él, no «tu entrenador» en tercera.
        pieTexto: 'En verde lo que baja y en naranja lo que sube. Subir de brazo y subir de cintura no son lo mismo, y eso te lo digo yo, no el color.',
    },
};
// Colores: los de Jesus (doc del 2-09, «verde baja, naranja sube»), elegidos por Francisco el
// 5-09 entre las tres reglas que habia. El informe del mes sigue con verde/rojo segun objetivo.

/**
 * LAS TRES PUERTAS POR LAS QUE ENTRA UNA MEDIDA, en una sola serie (2-09).
 *
 * Esta tabla solo miraba `reports[].measurements`, o sea las que se mandan dentro de un
 * reporte. Pero la app tiene otras dos puertas, y las dos guardaban en sitios que ninguna
 * pantalla pintaba:
 *
 *   - «Añadir medidas · cuando quieras» -> `client_profiles.medidas_sueltas`
 *   - las del día 1, en el cuestionario -> `client_profiles.medidas_inicio`
 *
 * Un cliente las apuntaba, le salía «Medidas guardadas», y aquí abajo seguía leyendo
 * «Todavía no has mandado ningún reporte con medidas». Era literalmente cierto y del todo
 * inútil. El backend ya lo daba por hecho: el propio `POST /clients/me/medidas` dice que
 * «van a su serie y la Evolución las pinta junto a las de los reportes: una toma es una
 * toma, venga de donde venga». La Evolución no lo hacía.
 *
 * `medidas_sueltas` ya viajaba en el perfil, así que esto no necesitó backend. Una toma por
 * día: si el mismo día hay reporte y toma suelta, manda la del reporte, que es la revisada.
 *
 * Desde la fase 3 (4-09) el cliente lee `tomas_medidas` de /reports/puntos, que hace esta
 * misma fusión en el servidor; esto se queda para el panel y como red si esa llamada falla.
 */
const _tomasDelPerfil = (perfil) => {
    const fuera = [];
    for (const t of (perfil?.medidas_sueltas || [])) {
        if (t?.fecha && t?.measurements && Object.keys(t.measurements).length) {
            fuera.push({ created_at: t.fecha, measurements: t.measurements });
        }
    }
    const inicio = perfil?.medidas_inicio;
    if (inicio && inicio.fecha) {
        const { fecha, ...medidas } = inicio;
        if (Object.keys(medidas).length) fuera.push({ created_at: fecha, measurements: medidas });
    }
    return fuera;
};

/** La caja vacía, la misma en los dos tonos. */
const SinMedidas = ({ t, tono, cabecera }) => (
    <div className={t.caja} data-testid="evolucion-medidas-vacio">
        <p className={`${t.titulo} mb-2`}>{cabecera}</p>
        {/* «Ningún reporte con medidas» era media verdad y sonaba a reproche: la serie mira
            también las sueltas y las del alta, así que si sigue vacía es que no hay ninguna
            por ninguna de las tres puertas. */}
        <p className={t.vacio}>
            {tono === 'admin'
                ? 'Todavía no ha apuntado ninguna medida.'
                : 'Todavía no has apuntado ninguna medida. Puedes hacerlo cuando quieras con «Añadir medidas».'}
        </p>
    </div>
);

/**
 * EL LADO DEL CLIENTE: dos tomas y su diferencia.
 *
 * @param tomas   [{id, fecha, measurements, grupo, marca}] ordenadas de antigua a reciente
 * @param puntos  lo de /reports/puntos (para los atajos y los ciclos del selector); null si
 *                no llegó y las tomas vienen de la red local
 */
const MedidasEnDosTomas = ({ t, cabecera, tomas, puntos, sinHistorico }) => {
    const [elegidaId, setElegidaId] = useState(null);
    const [selectorAbierto, setSelectorAbierto] = useState(false);

    const derecha = tomas[tomas.length - 1];
    const datosSelector = useMemo(() => ({ ...(puntos || {}), tomas_medidas: tomas }), [puntos, tomas]);
    const selector = useMemo(
        () => prepararSelector({ tipo: 'medidas', datos: datosSelector, derechaId: derecha?.id || null }),
        [datosSelector, derecha],
    );

    // LA DE LA IZQUIERDA: la elegida a mano; si no, el inicio de este ciclo; si no, la
    // primera toma; y si nada de eso vale (o es la misma que la derecha), la anterior a
    // la última. Con una sola toma no hay izquierda, y se dice.
    const izquierda = useMemo(() => {
        const atajos = puntos?.atajos_medidas || {};
        const candidatas = [
            elegidaId,
            leerAtajoDe(atajos, 'inicio_de_este_ciclo').id,
            leerAtajoDe(atajos, 'mi_primera_foto').id,
            tomas.length > 1 ? tomas[tomas.length - 2].id : null,
        ];
        for (const id of candidatas) {
            const e = id != null ? selector.buscar(id) : null;
            if (e && e.id !== derecha.id) return e;
        }
        return null;
    }, [elegidaId, puntos, tomas, selector, derecha]);

    const filas = MEDIDAS
        .map(({ key, label }) => ({
            key,
            label,
            antes: izquierda ? valorAnterior(izquierda.toma.measurements, key) : null,
            ahora: valorAnterior(derecha.measurements, key),
        }))
        .filter(f => f.antes != null || f.ahora != null);

    // La fecha en una línea y el rótulo debajo: en un móvil «23 ago · inicio del ciclo» se
    // partía en cuatro líneas dentro de una columna de 70 px.
    const cabeceraDe = (entrada, esHoy) => (
        <>
            <span className="block whitespace-nowrap">{fechaCorta(entrada.fecha)}</span>
            <span className="block text-[10px] font-normal">{esHoy ? 'hoy' : entrada.cabecera}</span>
        </>
    );
    // Lo mismo con lo que falta: en dos líneas fijas, que a lo ancho de un móvil «no la
    // mediste en esa toma» se rompía en cuatro y la tabla se hacía eterna.
    const noLaMidio = (
        <span className={`${t.igual} text-[10px] leading-tight`}>
            <span className="block whitespace-nowrap">no la mediste</span>
            <span className="block whitespace-nowrap">en esa toma</span>
        </span>
    );

    return (
        <div className={t.caja} data-testid="evolucion-medidas">
            <div className="flex items-baseline justify-between gap-2 flex-wrap mb-3">
                <p className={t.titulo}>{cabecera}</p>
                <p className={t.apunte}>
                    {tomas.length} {tomas.length === 1 ? 'toma' : 'tomas'} · en cm
                </p>
            </div>
            <table className="w-full text-xs" data-testid="medidas-dos-tomas">
                <thead>
                    <tr className={t.cabecera}>
                        <th className="text-left font-normal px-2 py-1.5 align-bottom">Medida</th>
                        <th className="text-right font-normal px-2 py-1.5 align-bottom" data-testid="medidas-cabecera-antes">
                            {izquierda ? cabeceraDe(izquierda, false) : 'antes'}
                        </th>
                        <th className="text-right font-normal px-2 py-1.5 align-bottom" data-testid="medidas-cabecera-ahora">
                            {cabeceraDe(derecha, true)}
                        </th>
                        <th className="text-right font-normal px-2 py-1.5 align-bottom">Cambio</th>
                    </tr>
                </thead>
                <tbody>
                    {filas.map(({ key, label, antes, ahora }) => {
                        const d = antes != null && ahora != null ? diferencia(ahora, antes) : null;
                        return (
                            <tr key={key} className={t.fila} data-testid={`medida-${key}`}>
                                <td className="px-2 py-1.5 text-foreground/70">{label}</td>
                                {/* Si falta en una de las dos se dice, nunca un hueco (doc de
                                    Jesús del 2-09: «nunca enseñar un hueco»). */}
                                <td className="px-2 py-1.5 text-right tabular-nums">
                                    {antes != null ? <span className={t.valor}>{antes}</span> : noLaMidio}
                                </td>
                                <td className="px-2 py-1.5 text-right tabular-nums">
                                    {ahora != null ? <span className={`${t.valor} font-bold`}>{ahora}</span> : noLaMidio}
                                </td>
                                <td className="px-2 py-1.5 text-right tabular-nums whitespace-nowrap">
                                    {d == null
                                        ? <span className={`${t.igual} text-[10px]`}>sin comparar</span>
                                        : d.signo === 0
                                            ? <span className={t.igual}>igual</span>
                                            : <span className={`font-bold ${d.signo > 0 ? t.sube : t.baja}`}>{d.texto}</span>}
                                </td>
                            </tr>
                        );
                    })}
                </tbody>
            </table>
            {!izquierda && (
                <p className={`${t.apunte} mt-2`} data-testid="medidas-falta-una">
                    Con dos tomas te enseñamos la diferencia. Te falta una.
                </p>
            )}
            {tomas.length > 1 && (
                <button type="button" onClick={() => setSelectorAbierto(true)} data-testid="elegir-otra-toma"
                    className="btn-outline-brand w-full mt-3 px-3 py-2.5 text-xs">
                    Elegir otra toma
                </button>
            )}
            <p className={t.pie}>{t.pieTexto}</p>

            {selectorAbierto && (
                <SelectorDeTomas tipo="medidas" datos={datosSelector}
                    seleccionado={izquierda?.id || null} derechaId={derecha.id}
                    aviso={sinHistorico ? 'No se pudo cargar tu histórico por ciclos. Prueba otra vez en un momento.' : null}
                    onElegir={(id) => setElegidaId(id)}
                    onCerrar={() => setSelectorAbierto(false)} />
            )}
        </div>
    );
};

const EvolucionMedidas = ({ reports, perfil = null, tono = 'cliente', titulo, api = null }) => {
    const t = TONOS[tono] || TONOS.cliente;
    const cabecera = titulo || (tono === 'admin' ? 'Evolución de las medidas' : 'Tus medidas');
    const esCliente = tono !== 'admin';

    // El `api` de la sesión, si no llega por prop: ReportsPage no lo pasa y no hace falta
    // que lo haga. En el panel (tono admin) el hook se queda apagado: el que mira no es el
    // cliente y no tiene /reports/puntos.
    const { api: apiDeSesion } = useAuth();
    const { datos: puntos, cargando, error } = usePuntos(api || apiDeSesion, { activo: esCliente });

    const sesiones = useMemo(() => {
        const deReportes = (reports || [])
            .filter(r => r?.created_at && r?.measurements && Object.keys(r.measurements).length);
        const diasConReporte = new Set(deReportes.map(r => String(r.created_at).slice(0, 10)));
        const conMedidas = [
            ...deReportes,
            ..._tomasDelPerfil(perfil)
                .filter(t2 => !diasConReporte.has(String(t2.created_at).slice(0, 10))),
        ].sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)));
        const vistas = conMedidas.slice(-SESIONES_A_LA_VISTA);
        // EL AÑO, CUANDO LAS TOMAS NO SON DEL MISMO (revisión del 2-09).
        //
        // La cabecera cortaba la fecha a «dd/mm» y las columnas se leían desordenadas:
        // «12/05 · 16/06 · 24/07 · 02/02» parece que febrero va detrás de julio, y en
        // realidad esa toma es del año siguiente. El orden siempre fue el bueno; lo que
        // engañaba era esconder el año. Solo se añade cuando hace falta, para no ensanchar
        // la tabla en el caso normal (todas del mismo año).
        const anios = new Set(vistas.map(r => String(r.created_at).slice(0, 4)));
        // Y LA PRIMERA DE VERDAD, NO LA PRIMERA QUE CABE (3-09-2026). El «Total» decía
        // comparar «con la primera» y comparaba con la primera de las OCHO que se ven, que
        // con más tomas no es la misma toma. Ver abajo.
        return { todas: conMedidas.length, vistas, conAnio: anios.size > 1, completas: conMedidas };
    }, [reports, perfil]);

    // LAS TOMAS DEL CLIENTE: las de /reports/puntos. Si esa llamada falla, la serie local
    // (las tres puertas) sigue valiendo para no dejar la pantalla en blanco; lo que no hay
    // entonces son los atajos ni los ciclos, y el selector lo dice.
    const tomasCliente = useMemo(() => {
        if (!esCliente) return null;
        if (puntos && Array.isArray(puntos.tomas_medidas)) {
            return [...puntos.tomas_medidas]
                .filter(x => x?.id && x?.fecha && x?.measurements && Object.keys(x.measurements).length)
                .map(x => ({ ...x, fecha: String(x.fecha).slice(0, 10) }))
                .sort((a, b) => a.fecha.localeCompare(b.fecha));
        }
        if (cargando) return null;
        return sesiones.completas.map(r => ({
            id: String(r.created_at).slice(0, 10),
            fecha: String(r.created_at).slice(0, 10),
            measurements: r.measurements,
            grupo: null,
            marca: null,
        }));
    }, [esCliente, puntos, cargando, sesiones]);

    if (esCliente) {
        if (tomasCliente == null) {
            return (
                <div className={t.caja} data-testid="evolucion-medidas-cargando">
                    <p className={`${t.titulo} mb-2`}>{cabecera}</p>
                    <p className={t.vacio}>Cargando tus medidas…</p>
                </div>
            );
        }
        if (!tomasCliente.length) return <SinMedidas t={t} tono={tono} cabecera={cabecera} />;
        const sinHistorico = !(puntos && Array.isArray(puntos.tomas_medidas)) && Boolean(error);
        return (
            <MedidasEnDosTomas t={t} cabecera={cabecera} tomas={tomasCliente}
                puntos={puntos && Array.isArray(puntos.tomas_medidas) ? puntos : null}
                sinHistorico={sinHistorico} />
        );
    }

    if (sesiones.vistas.length === 0) return <SinMedidas t={t} tono={tono} cabecera={cabecera} />;

    const fuera = sesiones.todas - sesiones.vistas.length;
    return (
        <div className={t.caja} data-testid="evolucion-medidas">
            <div className="flex items-baseline justify-between gap-2 flex-wrap mb-3">
                <p className={t.titulo}>{cabecera}</p>
                <p className={t.apunte}>
                    {fuera > 0 ? `Las ${sesiones.vistas.length} últimas de ${sesiones.todas}` : `${sesiones.todas} ${sesiones.todas === 1 ? 'toma' : 'tomas'}`}
                    {/* LAS DOS REGLAS, DICHAS (revisión del 2-09). Aquí ponía solo la
                        primera mientras la columna «Total» compara con la toma más
                        antigua: dos formas de leer la misma tabla y una sin explicar. */}
                    {' · '}cada columna se compara con la anterior; «Total», con la primera
                </p>
            </div>
            {/* LA PRIMERA COLUMNA SE QUEDA FIJA (revisión del 2-09, recorrido en móvil).
                La tabla se desplaza de lado, y al hacerlo se perdía de qué fila era cada
                número: «Brazo derecho relajado» pasaba a verse como «relajado» y «Gemelo
                izquierdo» como «do». Con `sticky` en la primera celda, el nombre de la
                medida viaja con la vista. */}
            <div className="overflow-x-auto">
                <table className="w-full text-xs min-w-[520px]">
                    <thead>
                        <tr className={t.cabecera}>
                            <th className={`text-left font-normal px-2 py-1.5 sticky left-0 z-10 ${t.fondoFijo}`}>Medida</th>
                            {sesiones.vistas.map(r => (
                                <th key={r.created_at} className="text-right font-normal px-2 py-1.5 whitespace-nowrap tabular-nums">
                                    {_cabeceraFecha(r.created_at, sesiones.conAnio)}
                                </th>
                            ))}
                            <th className="text-right font-normal px-2 py-1.5 whitespace-nowrap">Total</th>
                        </tr>
                    </thead>
                    <tbody>
                        {MEDIDAS.map(({ key, label }) => {
                            const valores = sesiones.vistas.map(r => valorAnterior(r.measurements, key));
                            if (valores.every(v => v == null)) return null;   // esa medida no la ha dado nunca
                            // EL «TOTAL» VA CONTRA LA PRIMERA TOMA DE VERDAD (3-09-2026).
                            //
                            // Salía de `valores`, que son las OCHO que caben en la tabla, así
                            // que con más de ocho tomas comparaba contra la primera de las
                            // últimas ocho y llamaba a eso «la primera». Medido con un cliente
                            // de 28 tomas: la cintura decía «+2» y contra su primera toma de
                            // verdad son «+7». El informe del mes sí usa la primera absoluta,
                            // así que las dos pantallas daban números distintos del mismo
                            // cliente el mismo día.
                            //
                            // Si esa medida no está en la toma más antigua, se busca la más
                            // antigua QUE LA TENGA: no todas las tomas traen las diez, y un
                            // «Total» contra nada no es un total.
                            let primero = null;
                            for (const toma of (sesiones.completas || [])) {
                                const v = valorAnterior(toma.measurements, key);
                                if (v != null) { primero = v; break; }
                            }
                            if (primero == null) primero = valores.find(v => v != null);
                            const ultimo = [...valores].reverse().find(v => v != null);
                            const total = diferencia(ultimo, primero);
                            return (
                                <tr key={key} className={t.fila}>
                                    <td className={t.medida}>{label}</td>
                                    {valores.map((v, i) => {
                                        const antes = valores.slice(0, i).reverse().find(x => x != null);
                                        const d = v != null ? diferencia(v, antes ?? null) : null;
                                        return (
                                            <td key={i} className="px-2 py-1.5 text-right tabular-nums whitespace-nowrap">
                                                <span className={t.valor}>{v ?? '-'}</span>
                                                {d && d.signo !== 0 && (
                                                    <span className={`ml-1 text-[10px] ${d.signo > 0 ? t.sube : t.baja}`}>{d.texto}</span>
                                                )}
                                            </td>
                                        );
                                    })}
                                    <td className="px-2 py-1.5 text-right tabular-nums whitespace-nowrap">
                                        {total && total.signo !== 0
                                            ? <span className={`font-bold ${total.signo > 0 ? t.sube : t.baja}`}>{total.texto}</span>
                                            : <span className={t.igual}>igual</span>}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
            <p className={t.pie}>{t.pieTexto}</p>
        </div>
    );
};

export default EvolucionMedidas;
