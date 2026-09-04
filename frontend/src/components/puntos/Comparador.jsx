/**
 * EL COMPARADOR: DOS PUNTOS, NUNCA TRES (doc de Jesús del 2-09, «El comparador»; fase 3,
 * 4-09). «Donde hay que ver más de dos está la gráfica.»
 *
 * Tres pantallas, en este orden:
 *
 *   1. ELEGIR EL OTRO PUNTO. Un punto ya está elegido (por defecto el de hoy; desde el
 *      detalle de un punto, ese) y se elige el otro con `ListaPorCiclo`: cinco atajos (mi
 *      pico de forma · mi peso más alto · mi peso más bajo · inicio de este ciclo · hoy) y
 *      debajo todos sus puntos agrupados por ciclo, «así puede comparar el bloque 3 de un
 *      ciclo con el bloque 3 de otro». Un atajo sin dato no se esconde: se enseña apagado
 *      con su nota.
 *   2. LA COMPARACIÓN. Las dos fotos, con el mismo ángulo (se elige de cada punto la foto
 *      con la pose de la de hoy, y si no la hay se dice), el rótulo corto encima, la fecha y
 *      el objetivo debajo de cada una («Máxima definición contra recomposición: si compara
 *      dos ciclos con objetivos distintos, los números dicen cosas raras y no porque haya
 *      ido mal») y cuánto tiempo hay entre las dos. Debajo, peso, medidas, grasa y macros,
 *      cada uno con sus dos valores y la diferencia, dos columnas de arriba abajo. Y lo que
 *      falte, dicho con su fecha: «No lo mediste en el reporte del 25 de julio, así que no
 *      se puede comparar». Nunca un hueco.
 *   3. GENERAR COMPARACIÓN. Una imagen con las dos fotos, las fechas y lo que ha movido,
 *      dibujada en el navegador (`lib/imagenComparacion`) y entregada como fichero. «La
 *      generas tú, cuando quieras. No se comparte sola.»
 *
 * El más antiguo va siempre a la izquierda y el más reciente a la derecha, con su rótulo en
 * naranja: el tiempo va en la misma dirección que en el resto de Evolución.
 */
import React, { useMemo, useState } from 'react';
import ListaPorCiclo from '../seguimiento/ListaPorCiclo';
import { MEDIDAS, valorAnterior } from '../../lib/medidas';
import { kg } from '../../lib/pesoValido';
import { NOMBRE_POSE } from '../../lib/comparativaFotos';
import { entregarImagen, generarImagenComparacion } from '../../lib/imagenComparacion';
import {
    FotoDelPunto, colorDeLaDiferencia, diferencia, enEsePunto, fechaCorta, fechaLarga, fotoDelAngulo,
    fotoPrincipal, numero, pieDeFoto, puntosEnOrden, rotuloCorto, tiempoEntre, useDatosDePuntos, useUrlDeFoto,
} from './comun';

// Los cinco atajos, con sus textos de la maqueta y lo que se dice cuando no existen.
const ATAJOS = [
    { clave: 'pico_de_forma', texto: 'Mi pico de forma', sinDato: 'tu entrenador todavía no lo ha marcado' },
    { clave: 'peso_maximo', texto: 'Mi peso más alto', sinDato: 'no tienes ese punto todavía' },
    { clave: 'peso_minimo', texto: 'Mi peso más bajo', sinDato: 'no tienes ese punto todavía' },
    { clave: 'inicio_de_este_ciclo', texto: 'Inicio de este ciclo', sinDato: 'no tienes ese punto todavía' },
    { clave: 'hoy', texto: 'Hoy', sinDato: 'no tienes ese punto todavía' },
];

// Los tres macros, con las claves de `/macros/historial` y sus nombres.
const MACROS = [['proteina', 'Proteína'], ['hidratos', 'Hidratos'], ['grasa', 'Grasa']];

const _mismo = (a, b) => a != null && b != null && String(a) === String(b);

/** Los atajos tal como los pinta `ListaPorCiclo`: id, texto y nota. El punto que ya está
 *  elegido se apaga (nunca los dos iguales), y el que no existe se apaga con su frase. */
const _atajos = (datos, porId, fijoId) => ATAJOS.map(a => {
    const crudo = datos?.atajos_puntos?.[a.clave];
    const id = crudo && typeof crudo === 'object' ? crudo.id : crudo;
    const notaServidor = crudo && typeof crudo === 'object' ? crudo.nota : null;
    const p = id != null ? porId.get(String(id)) : null;
    if (!p) return { clave: a.clave, texto: a.texto, id: null, nota: a.sinDato };
    if (_mismo(id, fijoId)) return { clave: a.clave, texto: a.texto, id: null, nota: 'ya es uno de los dos puntos' };
    return {
        clave: a.clave, texto: a.texto, id: p.id,
        nota: `${p.nombre} · ${fechaCorta(p.fecha)}${notaServidor ? ` · ${notaServidor}` : ''}`,
    };
});

// Dentro del grupo «Ciclo 3 · desde agosto» el nombre no repite el ciclo: «Final bloque 2»
// y ya. La etiqueta del ciclo lleva su tramo de meses detrás; lo que se quita del nombre es
// solo el «Ciclo 3» (o «Tramo 1») de delante.
const _sinElCiclo = (nombre, etiqueta) => {
    const n = String(nombre || '');
    const sufijo = ` · ${String(etiqueta || '').split(' · ')[0]}`;
    return sufijo.length > 3 && n.endsWith(sufijo) ? n.slice(0, -sufijo.length) : n;
};

/** Todos los puntos menos el fijo, agrupados por ciclo y del más antiguo al de hoy. Los
 *  ciclos anteriores al cuaderno llegan como tramos aproximados y se enseñan igual. Un
 *  tramo y un ciclo pueden llevar el mismo número (el tramo 1 de antes del cuaderno y el
 *  ciclo 1 del cuaderno), así que sin `ciclo_id` se casa por número Y por aproximado. */
const _grupos = (datos, puntos, fijoId) => {
    const ciclos = datos?.ciclos || [];
    const cicloDe = (p) => {
        if (p.ciclo_id != null) return ciclos.find(c => _mismo(c.id, p.ciclo_id)) || null;
        if (p.ciclo_numero == null) return null;
        return ciclos.find(c => c.numero === p.ciclo_numero && !!c.aproximado === !!p.aproximado)
            || ciclos.find(c => c.numero === p.ciclo_numero) || null;
    };
    const grupos = new Map();
    for (const p of puntos) {
        if (_mismo(p.id, fijoId)) continue;
        const c = cicloDe(p);
        const clave = String(c?.id ?? p.ciclo_id ?? (p.ciclo_numero != null ? `n${p.ciclo_numero}` : 'sin-ciclo'));
        if (!grupos.has(clave)) {
            const numero = c?.numero ?? p.ciclo_numero ?? null;
            const etiqueta = c?.etiqueta || (numero != null ? `${p.aproximado ? 'Tramo' : 'Ciclo'} ${numero}` : 'Otros puntos');
            grupos.set(clave, { id: clave, etiqueta, aproximado: !!(c?.aproximado ?? p.aproximado), numero: numero ?? Infinity, items: [] });
        }
        const g = grupos.get(clave);
        g.items.push({ id: p.id, texto: _sinElCiclo(p.nombre, g.etiqueta), marca: fechaCorta(p.fecha) });
    }
    return [...grupos.values()].sort((a, b) => a.numero - b.numero);
};

const Tarjeta = ({ titulo, testid, children }) => (
    <div className="bg-card border border-border rounded-2xl p-4 space-y-2" data-testid={testid}>
        <p className="caption">{titulo}</p>
        {children}
    </div>
);

const Falta = ({ children, testid }) => <p className="text-sm text-muted-foreground" data-testid={testid}>{children}</p>;

// Las columnas de las filas: el nombre, el valor de antes, el de ahora y el cambio.
const COLUMNAS = 'grid grid-cols-[minmax(0,1fr)_3.5rem_3.5rem_3.25rem] gap-x-2';

const Cabecera = ({ a, b, unidad }) => (
    <div className={`${COLUMNAS} text-[11px] text-muted-foreground border-b border-border pb-1`}>
        <span>{unidad}</span>
        <span className="text-right tabular-nums">{fechaCorta(a.fecha)}</span>
        <span className="text-right tabular-nums">{fechaCorta(b.fecha)}</span>
        <span className="text-right">Cambio</span>
    </div>
);

const Fila = ({ nombre, antes, despues, decimales = 1, testid }) => {
    const d = diferencia(antes, despues, decimales);
    return (
        <div className={`${COLUMNAS} items-baseline text-sm py-1 border-b border-border/50 last:border-0`} data-testid={testid}>
            <span className="text-foreground/80 leading-tight">{nombre}</span>
            <span className="text-right tabular-nums text-muted-foreground">{numero(antes, decimales)}</span>
            <span className="text-right tabular-nums font-bold text-foreground">{numero(despues, decimales)}</span>
            <span className={`text-right tabular-nums font-bold ${colorDeLaDiferencia(d?.signo)}`}>{d?.texto || ''}</span>
        </div>
    );
};

/** Un lado de la comparación: el rótulo corto, la foto (o por qué no está), la fecha y el
 *  objetivo. El de la derecha es el más reciente y va en naranja. */
const Lado = ({ punto, foto, url, poseRef, reciente }) => {
    let sinFoto = null;
    if (!foto) {
        sinFoto = !(punto.fotos || []).length
            ? 'No subiste fotos en este reporte.'
            : `No tienes foto ${NOMBRE_POSE[poseRef] || 'con ese ángulo'} de ese punto.`;
    }
    return (
        <div className="space-y-1" data-testid={reciente ? 'comparar-lado-reciente' : 'comparar-lado-antiguo'}>
            <p className={`text-[10px] font-bold uppercase tracking-wider leading-tight ${reciente ? 'text-brand' : 'text-muted-foreground'}`}>
                {rotuloCorto(punto.nombre)}
            </p>
            {foto ? (
                <FotoDelPunto url={url} pie={pieDeFoto(punto, foto)} alt={`Tu foto del ${fechaLarga(punto.fecha)}`}
                    testid={reciente ? 'foto-comparar-reciente' : 'foto-comparar-antiguo'} />
            ) : (
                <div className="aspect-[3/4] w-full rounded-xl bg-muted flex items-center justify-center p-3 text-center"
                    data-testid={reciente ? 'sin-foto-reciente' : 'sin-foto-antiguo'}>
                    <p className="text-xs text-muted-foreground leading-snug">{sinFoto}</p>
                </div>
            )}
            <p className="text-[11px] font-bold text-foreground leading-tight">{fechaLarga(punto.fecha)}</p>
            <p className="text-[11px] text-muted-foreground leading-tight">{punto.objetivo_nombre || 'sin objetivo apuntado'}</p>
        </div>
    );
};

/** Las medidas de los dos puntos, fila a fila: las que tienen las dos se comparan y las
 *  que faltan en uno se dicen con su fecha. */
const _medidas = (a, b) => {
    const comunes = [], soloA = [], soloB = [];
    for (const { key, label } of MEDIDAS) {
        const va = valorAnterior(a.medidas, key), vb = valorAnterior(b.medidas, key);
        if (va != null && vb != null) comunes.push({ key, label, antes: va, despues: vb });
        else if (va != null) soloA.push(label.toLowerCase());
        else if (vb != null) soloB.push(label.toLowerCase());
    }
    return { comunes, soloA, soloB };
};

const _lista = (nombres) => (nombres.length <= 1 ? nombres.join('')
    : `${nombres.slice(0, -1).join(', ')} y ${nombres[nombres.length - 1]}`);

const Comparador = ({ api, puntoInicial = null }) => {
    const { datos, error } = useDatosDePuntos(api);
    const puntos = useMemo(() => puntosEnOrden(datos), [datos]);
    const porId = useMemo(() => new Map(puntos.map(p => [String(p.id), p])), [puntos]);

    // EL PUNTO FIJO: el que llega por la URL (desde «Comparar este punto con otro ›» del
    // detalle) o, por defecto, el de hoy. El otro lo elige el cliente.
    const hoyId = datos?.atajos_puntos?.hoy ?? (puntos.length ? puntos[puntos.length - 1].id : null);
    const fijoId = puntoInicial != null && porId.has(String(puntoInicial)) ? puntoInicial : hoyId;
    const [otroId, setOtroId] = useState(null);
    const [paso, setPaso] = useState('elegir');
    const [generando, setGenerando] = useState(false);
    const [avisoImagen, setAvisoImagen] = useState(null);

    const fijo = fijoId != null ? porId.get(String(fijoId)) : null;
    const otro = otroId != null && !_mismo(otroId, fijoId) ? porId.get(String(otroId)) : null;
    // El más antiguo a la izquierda (a) y el más reciente a la derecha (b).
    const [a, b] = paso === 'comparar' && fijo && otro
        ? [fijo, otro].sort((x, y) => String(x.fecha || '').localeCompare(String(y.fecha || '')))
        : [null, null];

    // MISMO ÁNGULO: la pose de la foto principal del más reciente manda; de cada punto se
    // coge la foto con esa pose, y si no la tiene se dice. «Comparar un frente con un
    // perfil no dice nada.»
    const poseRef = fotoPrincipal(b)?.pose || fotoPrincipal(a)?.pose || null;
    const fotoA = a ? fotoDelAngulo(a, poseRef) : null;
    const fotoB = b ? fotoDelAngulo(b, poseRef) : null;
    const urlA = useUrlDeFoto(api, fotoA);
    const urlB = useUrlDeFoto(api, fotoB);

    const atajos = useMemo(() => _atajos(datos, porId, fijoId), [datos, porId, fijoId]);
    const grupos = useMemo(() => _grupos(datos, puntos, fijoId), [datos, puntos, fijoId]);

    if (error) {
        return <div className="bg-card border border-border rounded-2xl p-4"><p className="text-sm text-muted-foreground">{error}</p></div>;
    }
    if (!datos) {
        return <div className="animate-pulse h-40 bg-card border border-border rounded-2xl" data-testid="comparador-cargando" />;
    }
    if (puntos.length < 2 || !fijo) {
        return (
            <div className="bg-card border border-border rounded-2xl p-4 space-y-1" data-testid="comparador-sin-puntos">
                <p className="caption">Comparar</p>
                <p className="text-sm text-foreground">Con dos puntos te enseñamos la comparación.</p>
                <p className="text-sm text-muted-foreground">
                    {puntos.length === 1
                        ? 'Ya tienes uno; el siguiente reporte trae el otro.'
                        : 'Tus puntos de control van saliendo con cada reporte. Todavía no tienes ninguno.'}
                </p>
            </div>
        );
    }

    const elegir = (id) => {
        if (id == null || _mismo(id, fijoId)) return;
        setOtroId(id);
        setAvisoImagen(null);
        setPaso('comparar');
    };

    // ── 1. ELEGIR EL OTRO PUNTO ──
    if (paso !== 'comparar' || !a || !b) {
        const esHoy = _mismo(fijo.id, hoyId);
        return (
            <div className="space-y-4" data-testid="comparador-elegir">
                <div>
                    <p className="caption">Comparar</p>
                    <p className="text-lg font-bold text-foreground">Elige el otro punto</p>
                </div>
                <div className="surface p-3" data-testid="comparador-punto-fijo">
                    <p className="text-xs text-muted-foreground">Un punto ya está elegido{esHoy ? ': el de hoy' : ''}</p>
                    <p className="text-sm font-bold text-foreground">{fijo.nombre} · {fechaCorta(fijo.fecha)}</p>
                </div>
                <ListaPorCiclo atajos={atajos} grupos={grupos} seleccionado={otro?.id ?? null} onElegir={elegir}
                    tituloAtajos="Atajos:" tituloGrupos="Todos tus puntos, por ciclo" />
            </div>
        );
    }

    // ── 2. LA COMPARACIÓN ──
    const medidas = _medidas(a, b);
    const macrosA = a.macros || null, macrosB = b.macros || null;
    const bloquesDeMacros = [['entreno', 'Entreno'], ['descanso', 'Descanso'], ['peri', 'Perientreno']]
        .filter(([k]) => macrosA?.[k] && macrosB?.[k]);
    const periSoloEn = macrosA && macrosB && !!macrosA.peri !== !!macrosB.peri ? (macrosA.peri ? a : b) : null;

    // ── 3. GENERAR COMPARACIÓN ──
    const generar = async () => {
        setGenerando(true);
        setAvisoImagen(null);
        try {
            const filas = [];
            if (a.peso != null && b.peso != null) {
                filas.push({ nombre: 'Peso', antes: `${kg(a.peso)} kg`, despues: `${kg(b.peso)} kg`, diferencia: `${diferencia(a.peso, b.peso).texto} kg` });
            }
            for (const m of medidas.comunes) {
                filas.push({ nombre: m.label, antes: `${numero(m.antes)} cm`, despues: `${numero(m.despues)} cm`, diferencia: diferencia(m.antes, m.despues).texto });
            }
            if (a.grasa != null && b.grasa != null) {
                filas.push({ nombre: 'Grasa', antes: `${numero(a.grasa)} %`, despues: `${numero(b.grasa)} %`, diferencia: diferencia(a.grasa, b.grasa).texto });
            }
            for (const [k, nombre] of MACROS) {
                const va = macrosA?.entreno?.[k], vb = macrosB?.entreno?.[k];
                if (va != null && vb != null) {
                    filas.push({ nombre: `${nombre} (entreno)`, antes: `${numero(va, 0)} g`, despues: `${numero(vb, 0)} g`, diferencia: diferencia(va, vb, 0).texto });
                }
            }
            const lado = (p, url) => ({
                url, rotulo: rotuloCorto(p.nombre), fecha: fechaLarga(p.fecha).toUpperCase(),
                peso: p.peso != null ? `${kg(p.peso)} kg` : null, objetivo: p.objetivo_nombre || null,
            });
            const blob = await generarImagenComparacion({
                izquierda: lado(a, urlA), derecha: lado(b, urlB), tiempo: tiempoEntre(a.fecha, b.fecha), filas,
            });
            if (!blob) throw new Error('el canvas no devolvió imagen');
            const como = await entregarImagen(blob, `comparacion-12en12-${String(a.fecha).slice(0, 10)}-${String(b.fecha).slice(0, 10)}.png`);
            setAvisoImagen(como === 'compartida' ? 'Compartida.' : 'Lista: la tienes en tus descargas.');
        } catch (e) {
            console.error('No se pudo generar la comparación:', e);
            setAvisoImagen('No hemos podido generar la imagen. Prueba otra vez en un momento.');
        } finally {
            setGenerando(false);
        }
    };

    return (
        <div className="space-y-4" data-testid="comparador-comparacion">
            <div>
                <p className="caption">Comparar</p>
                <p className="text-lg font-bold text-foreground">Dos puntos</p>
            </div>

            <Tarjeta titulo="Tus fotos" testid="comparar-fotos">
                <div className="grid grid-cols-2 gap-3">
                    <Lado punto={a} foto={fotoA} url={urlA} poseRef={poseRef} reciente={false} />
                    <Lado punto={b} foto={fotoB} url={urlB} poseRef={poseRef} reciente />
                </div>
                <p className="text-xs text-muted-foreground text-center pt-1" data-testid="tiempo-entre-puntos">
                    {tiempoEntre(a.fecha, b.fecha)}
                </p>
            </Tarjeta>

            <Tarjeta titulo="Tu peso" testid="comparar-peso">
                {a.peso != null && b.peso != null ? (
                    <>
                        <Cabecera a={a} b={b} unidad="kg" />
                        <Fila nombre="Peso" antes={a.peso} despues={b.peso} testid="fila-peso" />
                    </>
                ) : (
                    <Falta>
                        {a.peso == null && b.peso == null
                            ? 'No tenemos tu peso de ninguno de los dos puntos.'
                            : `No tenemos tu peso ${enEsePunto(a.peso == null ? a : b)}, así que no se puede comparar.`}
                    </Falta>
                )}
            </Tarjeta>

            <Tarjeta titulo="Tus medidas" testid="comparar-medidas">
                {medidas.comunes.length ? (
                    <>
                        <Cabecera a={a} b={b} unidad="cm" />
                        {medidas.comunes.map(m => (
                            <Fila key={m.key} nombre={m.label} antes={m.antes} despues={m.despues} testid={`fila-${m.key}`} />
                        ))}
                    </>
                ) : (
                    <Falta testid="medidas-sin-comparar">
                        {!medidas.soloA.length && !medidas.soloB.length
                            ? 'No las mediste en ninguno de los dos puntos.'
                            : `No las mediste ${enEsePunto(medidas.soloA.length ? b : a)}, así que no se pueden comparar.`}
                    </Falta>
                )}
                {medidas.comunes.length > 0 && medidas.soloA.length > 0 && (
                    <p className="text-xs text-muted-foreground">
                        Sin comparar: {_lista(medidas.soloA)}, que no {medidas.soloA.length === 1 ? 'la' : 'las'} mediste {enEsePunto(b)}.
                    </p>
                )}
                {medidas.comunes.length > 0 && medidas.soloB.length > 0 && (
                    <p className="text-xs text-muted-foreground">
                        Sin comparar: {_lista(medidas.soloB)}, que no {medidas.soloB.length === 1 ? 'la' : 'las'} mediste {enEsePunto(a)}.
                    </p>
                )}
            </Tarjeta>

            <Tarjeta titulo="Tu porcentaje de grasa" testid="comparar-grasa">
                {a.grasa != null && b.grasa != null ? (
                    <>
                        <Cabecera a={a} b={b} unidad="%" />
                        <Fila nombre="Grasa" antes={a.grasa} despues={b.grasa} testid="fila-grasa" />
                    </>
                ) : (
                    <Falta testid="grasa-sin-comparar">
                        {a.grasa == null && b.grasa == null
                            ? 'No lo mediste en ninguno de los dos puntos.'
                            : `No lo mediste ${enEsePunto(a.grasa == null ? a : b)}, así que no se puede comparar.`}
                    </Falta>
                )}
            </Tarjeta>

            <Tarjeta titulo="Tus macros" testid="comparar-macros">
                {bloquesDeMacros.length ? (
                    <>
                        <Cabecera a={a} b={b} unidad="g" />
                        {bloquesDeMacros.map(([k, nombre]) => (
                            <div key={k} className="pt-1">
                                {bloquesDeMacros.length > 1 && <p className="text-[11px] font-bold text-foreground/60 pt-1">{nombre}</p>}
                                {MACROS.filter(([m]) => macrosA[k][m] != null && macrosB[k][m] != null).map(([m, etiqueta]) => (
                                    <Fila key={m} nombre={etiqueta} antes={macrosA[k][m]} despues={macrosB[k][m]} decimales={0} testid={`fila-${k}-${m}`} />
                                ))}
                            </div>
                        ))}
                        {periSoloEn && (
                            <p className="text-xs text-muted-foreground">El perientreno solo lo llevabas {enEsePunto(periSoloEn)}.</p>
                        )}
                    </>
                ) : (
                    <Falta testid="macros-sin-comparar">
                        {!macrosA && !macrosB
                            ? 'No tenemos tus macros de ninguno de los dos puntos.'
                            : `No tenemos tus macros ${enEsePunto(!macrosA ? a : b)}, así que no se pueden comparar.`}
                    </Falta>
                )}
            </Tarjeta>

            <div className="space-y-2">
                <button type="button" onClick={() => { setPaso('elegir'); setAvisoImagen(null); }} data-testid="elegir-otro-punto"
                    className="btn-outline-brand w-full text-sm">
                    Elegir otro punto
                </button>
                <button type="button" onClick={generar} disabled={generando} data-testid="generar-comparacion"
                    className="btn-brand w-full text-sm">
                    {generando ? 'Generando…' : 'Generar comparación'}
                </button>
                {avisoImagen && (
                    <p className="text-xs text-muted-foreground text-center" data-testid="aviso-imagen">{avisoImagen}</p>
                )}
                <p className="text-xs text-muted-foreground text-center">La generas tú, cuando quieras. No se comparte sola.</p>
            </div>
        </div>
    );
};

export default Comparador;
