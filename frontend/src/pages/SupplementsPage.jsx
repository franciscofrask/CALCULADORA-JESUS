import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Pill, Clock, Beaker, Link2, CalendarClock, StickyNote } from 'lucide-react';

const Wrap = ({ children }) => (
    <div className="px-4 sm:px-6 lg:px-8 py-6 max-w-[1100px] mx-auto animate-fade-in" data-testid="supplements-page">{children}</div>
);

const formatDate = (iso) => {
    if (!iso) return '';
    const [y, m, d] = iso.split('-').map(Number);
    return new Date(y, m - 1, d).toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' });
};

const SupplementCard = ({ item }) => {
    const [imgError, setImgError] = useState(false);
    return (
    <div className="surface p-0 overflow-hidden flex flex-col sm:flex-row" data-testid="supplement-card">
        <div className="hidden sm:flex sm:w-32 items-center justify-center bg-muted/40 p-3 flex-shrink-0">
            {item.imagen && !imgError ? (
                <img
                    src={item.imagen}
                    alt={item.titulo}
                    className="max-h-24 object-contain"
                    onError={() => setImgError(true)}
                />
            ) : (
                <Pill className="w-8 h-8 text-brand/50" />
            )}
        </div>
        <div className="flex-1 p-4">
            <h3 className="font-semibold text-foreground mb-2">{item.titulo}</h3>
            {item.cuando && (
                <p className="text-sm text-muted-foreground flex gap-2 mb-1">
                    <Clock className="w-4 h-4 text-brand flex-shrink-0 mt-0.5" />
                    <span><span className="font-semibold text-foreground">¿Cuándo? </span>{item.cuando}</span>
                </p>
            )}
            {item.cuanto && (
                <p className="text-sm text-muted-foreground flex gap-2 mb-1">
                    <Beaker className="w-4 h-4 text-brand flex-shrink-0 mt-0.5" />
                    <span><span className="font-semibold text-foreground">¿Cuánto? </span>{item.cuanto}</span>
                </p>
            )}
            {item.observaciones && (
                <p className="text-sm text-muted-foreground italic mt-2">{item.observaciones}</p>
            )}
            {item.enlaces?.length > 0 && (
                <div className="flex flex-wrap gap-3 mt-2">
                    {item.enlaces.map((url, i) => (
                        <a key={i} href={url} target="_blank" rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-brand hover:underline font-semibold">
                            <Link2 className="w-3 h-3" /> Enlace {item.enlaces.length > 1 ? i + 1 : ''}
                        </a>
                    ))}
                </div>
            )}
        </div>
    </div>
    );
};

/**
 * UNA LÍNEA DEL PROTOCOLO, COMO LA PIDE EL DOC DEL 16-08 (T2): el producto y, debajo,
 * «1 cacito · después de entrenar».
 *
 * La tarjeta de siempre partía la misma información en dos filas con sus rótulos
 * («¿Cuándo?» / «¿Cuánto?»), que es cómo se rellena en el panel, no cómo se lee: lo que
 * el cliente necesita saber de un vistazo es qué se toma y cuándo, en una frase.
 */
const LineaSuplemento = ({ item }) => {
    const [imgError, setImgError] = useState(false);
    const pauta = [item.cuanto, item.cuando].map((t) => (t || '').trim()).filter(Boolean).join(' · ');
    return (
        <div className="surface p-4 flex items-start gap-4" data-testid="supplement-card">
            <div className="w-12 h-12 rounded-xl bg-muted/40 flex items-center justify-center flex-shrink-0 overflow-hidden">
                {item.imagen && !imgError
                    ? <img src={item.imagen} alt={item.titulo} className="max-h-12 object-contain" onError={() => setImgError(true)} />
                    : <Pill className="w-6 h-6 text-brand/50" />}
            </div>
            <div className="min-w-0 flex-1">
                <p className="font-bold text-foreground text-sm">{item.titulo}</p>
                {pauta && <p className="text-muted-foreground text-sm">{pauta}</p>}
                {item.observaciones && <p className="text-muted-foreground text-xs italic mt-1">{item.observaciones}</p>}
                {item.enlaces?.length > 0 && (
                    <div className="flex flex-wrap gap-3 mt-1.5">
                        {item.enlaces.map((url, i) => (
                            <a key={i} href={url} target="_blank" rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 text-xs text-brand hover:underline font-semibold">
                                <Link2 className="w-3 h-3" /> Dónde comprarlo {item.enlaces.length > 1 ? i + 1 : ''}
                            </a>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

/**
 * LA FICHA DE LA GUÍA (doc 19-08, bloque 08): Qué es · ¿Cuándo? · ¿Cuánto? y sus notas
 * sueltas, tal cual vienen de la web de Jesús.
 */
const FichaDeLaGuia = ({ ficha }) => {
    const [imgError, setImgError] = useState(false);
    return (
        <div className="surface p-4 flex items-start gap-4" data-testid="ficha-guia">
            <div className="w-12 h-12 rounded-xl bg-muted/40 flex items-center justify-center flex-shrink-0 overflow-hidden">
                {ficha.imagen && !imgError
                    ? <img src={ficha.imagen} alt={ficha.nombre} className="max-h-12 object-contain" onError={() => setImgError(true)} />
                    : <Pill className="w-6 h-6 text-brand/50" />}
            </div>
            <div className="min-w-0 flex-1">
                <p className="font-bold text-foreground text-sm">{ficha.nombre}</p>
                {ficha.que_es && <p className="text-muted-foreground text-sm mt-0.5">{ficha.que_es}</p>}
                {ficha.cuando && (
                    <p className="text-sm text-muted-foreground mt-1">
                        <span className="font-semibold text-foreground">¿Cuándo? </span>{ficha.cuando}
                    </p>
                )}
                {ficha.cuanto && (
                    <p className="text-sm text-muted-foreground">
                        <span className="font-semibold text-foreground">¿Cuánto? </span>{ficha.cuanto}
                    </p>
                )}
                {ficha.notas && <p className="text-muted-foreground text-xs italic mt-1">{ficha.notas}</p>}
                {ficha.enlaces?.length > 0 && (
                    <div className="flex flex-wrap gap-3 mt-1.5">
                        {ficha.enlaces.map((e, i) => (
                            <a key={i} href={e.url || e} target="_blank" rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 text-xs text-brand hover:underline font-semibold">
                                <Link2 className="w-3 h-3" /> Dónde comprarlo
                            </a>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

/**
 * LA GUÍA ENTERA (doc 19-08): las ocho categorías con su filtro y su orden, la ficha de
 * cada suplemento, el descuento, y el remate que toque por plan (el aviso del plan
 * personalizado o la oferta de los 87). La guía habla en singular porque es de Jesús;
 * el aviso y la oferta en plural, porque los hace el equipo.
 */
const GuiaDeSuplementacion = ({ api, guia }) => {
    const [filtro, setFiltro] = useState('todo');
    const [subfiltro, setSubfiltro] = useState(null);
    const [pidiendo, setPidiendo] = useState(false);

    if (!guia) return null;
    const secciones = (guia.secciones || []).filter(s => s.suplementos.length > 0);
    const sinSeccion = guia.sin_seccion || [];
    const visibles = filtro === 'todo' ? secciones : secciones.filter(s => s.clave === filtro);
    const seccionSalud = secciones.find(s => s.clave === 'salud');

    const pedirRevision = async () => {
        setPidiendo(true);
        try {
            const { data } = await api.post('/billing/ajuste-a-medida/checkout', {});
            if (data?.checkout_url) window.location.href = data.checkout_url;
        } catch (e) {
            console.error('[oferta 87] no se pudo abrir el checkout', e);
        } finally {
            setPidiendo(false);
        }
    };

    return (
        <section className="max-w-2xl" data-testid="guia-suplementacion">
            {/* El aviso de arriba: solo al del plan personalizado (o los 87 ya pagados)
                que todavía no tiene el suyo. Habla en plural: es el equipo. */}
            {guia.aviso_plan_personalizado && (
                <div className="surface bg-brand/[0.06] border-brand/30 p-4 mb-5" data-testid="aviso-guia-basica">
                    <p className="text-sm text-foreground font-medium">
                        Esto es solo la guía básica. En unos días recibirás tu plan de
                        suplementación personalizado.
                    </p>
                </div>
            )}

            {/* El texto de entrada es de Jesús y viene de su web: si aún no está traído,
                no se pinta nada (no se inventa). */}
            {guia.texto_entrada && (
                <p className="text-muted-foreground text-sm mb-5 whitespace-pre-line">{guia.texto_entrada}</p>
            )}

            {/* El filtro de las ocho, en su orden. Solo las que tienen fichas. */}
            {secciones.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-4">
                    <button onClick={() => { setFiltro('todo'); setSubfiltro(null); }}
                        className={`px-3 py-1.5 rounded-full text-xs font-bold ${filtro === 'todo' ? 'bg-brand text-white' : 'bg-muted text-muted-foreground'}`}>
                        Todo
                    </button>
                    {secciones.map(s => (
                        <button key={s.clave} onClick={() => { setFiltro(s.clave); setSubfiltro(null); }}
                            className={`px-3 py-1.5 rounded-full text-xs font-bold ${filtro === s.clave ? 'bg-brand text-white' : 'bg-muted text-muted-foreground'}`}>
                            {s.nombre}
                        </button>
                    ))}
                </div>
            )}
            {/* Los seis apartados de Salud, cuando se filtra por ella. */}
            {filtro === 'salud' && seccionSalud?.subfiltros?.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-4">
                    {seccionSalud.subfiltros.map(sf => (
                        <button key={sf} onClick={() => setSubfiltro(subfiltro === sf ? null : sf)}
                            className={`px-2.5 py-1 rounded-full text-[11px] font-semibold ${subfiltro === sf ? 'bg-brand/20 text-brand' : 'bg-muted text-muted-foreground'}`}>
                            {sf}
                        </button>
                    ))}
                </div>
            )}

            <div className="space-y-6">
                {visibles.map(s => (
                    <div key={s.clave}>
                        <h2 className="caption mb-1">{s.nombre}</h2>
                        {s.explicacion && <p className="text-muted-foreground text-sm mb-3">{s.explicacion}</p>}
                        <div className="space-y-3">
                            {(subfiltro && s.clave === 'salud'
                                ? s.suplementos.filter(f => (f.subfiltros || []).some(x => x.toLowerCase() === subfiltro.toLowerCase()))
                                : s.suplementos
                            ).map(f => <FichaDeLaGuia key={f.id} ficha={f} />)}
                        </div>
                    </div>
                ))}
                {filtro === 'todo' && sinSeccion.length > 0 && (
                    <div>
                        {secciones.length > 0 && <h2 className="caption mb-3">El resto de la guía</h2>}
                        <div className="space-y-3">
                            {sinSeccion.map(f => <FichaDeLaGuia key={f.id} ficha={f} />)}
                        </div>
                    </div>
                )}
            </div>

            {/* El descuento, tal cual: GALLEGOVIP de FullGas, 20 %. */}
            {guia.descuento && (
                <div className="surface p-4 mt-6 border-dashed" data-testid="descuento-guia">
                    <p className="text-sm text-foreground">
                        <span className="font-bold">{guia.descuento.codigo}</span>
                        {' · '}{guia.descuento.porcentaje} % de descuento en {guia.descuento.tienda}.
                        {' '}{guia.descuento.nota}
                    </p>
                </div>
            )}

            {/* LA OFERTA, AL FINAL Y SOLO A QUIEN NO LO TIENE (doc 19-08): «entra a
                consultar qué tomar y lo último que ve es lo que le falta». El botón va al
                mismo checkout que la oferta del final del alta. */}
            {guia.oferta_87 && (
                <div className="surface p-5 mt-6 border-brand/30" data-testid="oferta-87-guia">
                    <p className="font-bold text-foreground mb-1">¿Quieres tu plan de suplementación personalizado?</p>
                    <p className="text-sm text-muted-foreground mb-3">
                        Va incluido con la revisión de tus macros: te los ajustamos a medida
                        y te preparamos tu suplementación con ellos.
                    </p>
                    <button onClick={pedirRevision} disabled={pidiendo} data-testid="solicitar-revision-87"
                        className="w-full sm:w-auto px-5 py-2.5 rounded-full bg-brand text-white text-sm font-bold hover:opacity-90 disabled:opacity-50">
                        {pidiendo ? 'Abriendo el pago...' : 'Solicitar la revisión de mis macros · 87 €'}
                    </button>
                </div>
            )}
        </section>
    );
};

const SupplementsPage = () => {
    const { api, pantalla } = useAuth();
    // El interruptor del panel (doc 16-08): encendido -- que es como nace -- la pantalla
    // habla como el documento; apagado se queda la de siempre, sin desplegar nada.
    const nuevo = pantalla('t2_suplementos', true);
    const [protocol, setProtocol] = useState(null);
    const [guia, setGuia] = useState(null);
    const [loading, setLoading] = useState(true);

    // eslint-disable-next-line react-hooks/exhaustive-deps
    useEffect(() => { fetchProtocol(); }, []);

    const fetchProtocol = async () => {
        try {
            const res = await api.get('/supplements/current');
            setProtocol(res.data);
        } catch (e) {
            console.error('Error fetching supplements:', e);
        }
        // La guía la ven todos, tenga o no protocolo; si falla, la pantalla sigue con lo
        // que haya.
        try {
            const g = await api.get('/supplements/guia');
            setGuia(g.data);
        } catch (e) {
            console.error('No se pudo traer la guía de suplementación:', e);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return <Wrap><div className="animate-pulse space-y-4">
            <div className="h-9 bg-muted rounded w-1/3" />
            <div className="h-24 bg-muted rounded-2xl" />
            <div className="h-24 bg-muted rounded-2xl" />
        </div></Wrap>;
    }

    const tieneActual = protocol?.actual?.length > 0;
    const tieneSiguiente = protocol?.siguiente?.length > 0;
    // La general compuesta murió con el doc 19-08: sin protocolo propio, lo que se ve es
    // LA GUÍA entera de Jesús.
    const esGenerica = !!protocol?.es_generica;
    const hayGuia = (guia?.secciones || []).some(s => s.suplementos.length > 0) || (guia?.sin_seccion || []).length > 0;

    if (!tieneActual && !tieneSiguiente && !protocol?.nota && hayGuia) {
        // SIN PAUTA PROPIA: la pantalla ES la guía (doc 19-08, bloque 08).
        return <Wrap>
            <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground mb-2">
                Suplementación
            </h1>
            <p className="text-muted-foreground text-sm mb-5 max-w-2xl">
                La guía de suplementación, con los suplementos que más utilizo y recomiendo.
            </p>
            <GuiaDeSuplementacion api={api} guia={guia} />
        </Wrap>;
    }

    if (!protocol || (!tieneActual && !tieneSiguiente && !protocol.nota)) {
        return <Wrap>
            <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground mb-6">
                {nuevo ? 'Tu suplementación' : 'Suplementación'}
            </h1>
            <div className="surface p-10 text-center">
                <div className="w-16 h-16 bg-brand/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                    <Pill className="w-8 h-8 text-brand/60" />
                </div>
                {/* YA NO HAY NADA QUE TRAER (punto 4.15, cerrado el 09-08-2026). Este texto
                    decía «lo tienes en el sistema anterior y lo estamos trayendo», que era
                    verdad mientras los protocolos seguían en Calma. Ya no: se migraron los 98
                    clientes que tenían uno, con su histórico entero. Quien llegue aquí ahora es
                    porque de verdad no tiene protocolo puesto, y hay que decírselo tal cual en
                    vez de hacerle esperar algo que no va a llegar.

                    El texto anterior hablaba además de 666 clientes pendientes: un dato interno
                    nuestro que no le decía nada a quien lo leía. */}
                {/* NI «PROTOCOLO» NI «TU ENTRENADOR» (#53 del 15-08: «sigue el lenguaje de
                    catálogo»). «Protocolo» es como lo llamamos nosotros por dentro; el
                    cliente compró que le digamos qué tomar. Y «tu entrenador» le habla de
                    una persona que casi nadie tiene asignada en la app: aquí quien contesta
                    es el equipo. */}
                {/* AQUÍ SOLO SE LLEGA SI NO HAY NI GENERAL (18-08). Este cartel era lo que
                    veía todo el que no tuviera la suya escrita, y es justo lo que Jesús no
                    quiere: mientras no le pongamos la suya, se le enseña la general. El
                    servidor la manda siempre que el catálogo tenga base o intra, así que
                    esto ya solo sale si el catálogo está vacío. */}
                <h2 className="font-heading text-xl font-bold uppercase text-foreground mb-2">Todavía no tienes suplementación</h2>
                <p className="text-muted-foreground text-sm">
                    En cuanto te la pautemos la ves aquí. Si crees que te toca ya, dínoslo
                    por el chat y le echamos un ojo.
                </p>
            </div>
        </Wrap>;
    }

    const Tarjeta = nuevo ? LineaSuplemento : SupplementCard;

    return (
        <Wrap>
            <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground mb-2">
                {nuevo ? 'Tu suplementación' : 'Suplementación'}
            </h1>
            {/* EL SUBTÍTULO ES SUYO, NO UN DESCARGO. Lo que había avisaba de que esto es
                «orientativo» y que «pueden ser necesarios otros suplementos», que es lo que
                se le dice a quien mira un catálogo general. Esto no es un catálogo: es lo
                que le ha pautado a él. */}
            <p className="text-muted-foreground text-sm mb-5 max-w-2xl">
                {esGenerica
                    ? 'Todavía no te he pautado la tuya. Mientras tanto, esta es la que recomiendo de base: en cuanto te ponga la tuya, la ves aquí.'
                    : nuevo
                        ? 'Lo que te he pautado y cuándo tomarlo'
                        : 'Aquí ves algunos de los suplementos más habituales que recomiendo, así como su modo de empleo. Esta información es orientativa: pueden ser necesarios otros suplementos o dosis según tu situación, objetivos o tolerancias.'}
            </p>

            {protocol.nota && (
                <div className="surface bg-brand/[0.04] border-brand/20 p-4 mb-5 flex gap-3 max-w-2xl">
                    <StickyNote className="w-5 h-5 text-brand flex-shrink-0 mt-0.5" />
                    <div>
                        <p className="text-[11px] font-bold text-brand uppercase tracking-wider mb-1">Nota personal</p>
                        <p className="text-sm text-muted-foreground leading-relaxed">{protocol.nota}</p>
                    </div>
                </div>
            )}

            {tieneActual && (
                <section className="mb-7">
                    {/* Sin rótulo cuando no hay nada más: la pantalla entera ya dice qué es
                        esto, y «Suplementación actual» solo hace falta para distinguirla de
                        la que entra más adelante. */}
                    {(!nuevo || tieneSiguiente) && (
                        <h2 className="caption mb-3">
                            {esGenerica ? 'La suplementación general' : 'Suplementación actual'}
                        </h2>
                    )}
                    <div className={nuevo ? 'space-y-3 max-w-2xl' : 'grid md:grid-cols-2 gap-3'}>
                        {protocol.actual.map((it, i) => <Tarjeta key={i} item={it} />)}
                    </div>
                </section>
            )}

            {tieneSiguiente && (
                <section>
                    <div className="flex items-center gap-2 mb-3">
                        <h2 className="caption">Suplementación siguiente</h2>
                        {protocol.siguiente_fecha && (
                            <span className="inline-flex items-center gap-1 text-[11px] font-bold uppercase px-2 py-0.5 rounded-full bg-red-500/10 text-red-500">
                                <CalendarClock className="w-3 h-3" /> A partir del {formatDate(protocol.siguiente_fecha)}
                            </span>
                        )}
                    </div>
                    <div className={nuevo ? 'space-y-3 max-w-2xl' : 'grid md:grid-cols-2 gap-3'}>
                        {protocol.siguiente.map((it, i) => <Tarjeta key={i} item={it} />)}
                    </div>
                </section>
            )}

            {/* Y DEBAJO, LA GUÍA: la ven todos (doc 19-08), también quien ya tiene su
                pauta. Con su rótulo, para que nadie confunda la guía con lo suyo. */}
            {hayGuia && (
                <section className="mt-10">
                    <h2 className="font-heading text-xl font-bold uppercase text-foreground mb-1">La guía de suplementación</h2>
                    <p className="text-muted-foreground text-sm mb-4 max-w-2xl">
                        Los suplementos que más utilizo y recomiendo, por si quieres consultarla.
                    </p>
                    <GuiaDeSuplementacion api={api} guia={guia} />
                </section>
            )}
        </Wrap>
    );
};

export default SupplementsPage;
