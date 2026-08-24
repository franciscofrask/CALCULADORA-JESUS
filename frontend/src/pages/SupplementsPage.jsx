import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Pill, Clock, Beaker, Link2, CalendarClock, StickyNote, ChevronRight, ChevronLeft, Copy, Check } from 'lucide-react';

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
                            <Link2 className="w-3 h-3" /> Dónde encontrarlo {item.enlaces.length > 1 ? i + 1 : ''}
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
                                <Link2 className="w-3 h-3" /> Dónde encontrarlo {item.enlaces.length > 1 ? i + 1 : ''}
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
                                <Link2 className="w-3 h-3" /> Dónde encontrarlo
                            </a>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

/**
 * EL DESCUENTO, CON EL TEXTO QUE DICTÓ JESÚS EL 21-08 (apartado 10 de su doc), tal cual.
 * Antes era una línea recompuesta con los campos («GALLEGOVIP · 20 % de descuento en
 * FullGas...») y solo salía dentro de la guía: ahora el texto es el suyo, el código se
 * copia con un toque, y sale también en la pantalla del protocolo, que no lo tenía.
 */
const Descuento = () => {
    const [copiado, setCopiado] = useState(false);
    const copiar = async () => {
        try {
            await navigator.clipboard.writeText('GALLEGOVIP');
            setCopiado(true);
            setTimeout(() => setCopiado(false), 2000);
        } catch (e) {
            // Sin permiso de portapapeles el código sigue a la vista: no pasa nada.
            console.error('No se pudo copiar el código de descuento', e);
        }
    };
    return (
        <div className="surface p-4 border-dashed" data-testid="descuento-guia">
            <p className="text-sm text-foreground">
                Tienes un código especial en FullGas, la empresa con la que llevo trabajando más de 15 años.
            </p>
            <div className="my-2 flex items-center gap-2">
                <button onClick={copiar} type="button" title="Copiar el código" data-testid="copiar-descuento"
                    className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-brand/10 text-brand font-bold tracking-widest text-sm hover:bg-brand/20">
                    GALLEGOVIP
                    {copiado ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                </button>
                {copiado && <span className="text-xs font-semibold text-brand">Copiado</span>}
            </div>
            <p className="text-sm text-foreground">
                Lo tendrás activo todo el tiempo, mientras dure tu suscripción. Te aplicarán un 20 % en toda la web.
            </p>
        </div>
    );
};

/**
 * EL TEXTO DE ENTRADA DE LA GUÍA, EL SUYO (24-08).
 *
 * Jesús lo escribió en su web, se importó a la base (`app_state.guia_suplementacion`) y el
 * endpoint lo sirve desde entonces, pero esta pantalla pintaba una versión recortada
 * escrita aquí a mano y no lo leía: editarlo en la base no cambiaba nada de lo que ve
 * nadie. Ahora manda el suyo -- que además trae el párrafo de la guía de definición del
 * Catálogo Premium, que aquí se había quedado fuera -- y el de casa queda de respaldo,
 * por si esta base no ha pasado por la importación.
 *
 * Del suyo se cae UNA línea: el «*IMPORTANTE» del descuento, porque va justo debajo en su
 * propio bloque con el texto que dictó el 21-08. Decírselo dos veces en la misma pantalla
 * no es ser literal, es repetirse.
 */
const TEXTO_DE_ENTRADA_DE_CASA = 'Estos son los suplementos que más utilizo y recomiendo. '
    + 'Con pautas exactas sobre su uso. Están organizados por categorías según su función. '
    + 'En condiciones normales, se recomienda empezar por los básicos.';

const TextoDeEntrada = ({ texto }) => {
    const suyos = (texto || '').split('\n').map(p => p.trim())
        .filter(p => p && !p.startsWith('*IMPORTANTE'));
    const parrafos = suyos.length > 0 ? suyos : [TEXTO_DE_ENTRADA_DE_CASA];
    return (
        <div className="mb-5 max-w-2xl space-y-2" data-testid="texto-entrada-guia">
            {parrafos.map((p, i) => <p key={i} className="text-muted-foreground text-sm">{p}</p>)}
        </div>
    );
};

/**
 * LA GUÍA (doc 19-08, presentada como dictó Jesús el 21-08): primero LAS CATEGORÍAS,
 * para pinchar y entrar, no todo el mensaje de golpe. Dentro de cada una, sus fichas.
 * El remate por plan sigue igual (el aviso del plan personalizado o la oferta de los 87).
 * La guía habla en singular porque es de Jesús; el aviso y la oferta en plural, porque
 * los hace el equipo.
 */
const GuiaDeSuplementacion = ({ api, guia, conDescuento = true }) => {
    // La categoría abierta (su clave), o null: la portada con las categorías.
    const [abierta, setAbierta] = useState(null);
    const [subfiltro, setSubfiltro] = useState(null);
    const [pidiendo, setPidiendo] = useState(false);

    if (!guia) return null;
    const secciones = (guia.secciones || []).filter(s => s.suplementos.length > 0);
    const sinSeccion = guia.sin_seccion || [];
    // Las fichas que la web aún no encaja en ninguna categoría entran como una más, al
    // final, para que se pueda llegar a ellas igual.
    const entradas = sinSeccion.length > 0
        ? [...secciones, { clave: '_resto', nombre: 'El resto de la guía', suplementos: sinSeccion }]
        : secciones;
    const seccion = entradas.find(s => s.clave === abierta) || null;

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

            {!seccion ? (
                /* LA PORTADA (Jesús, 21-08): debajo del texto corto, directamente las
                   categorías para pinchar y entrar. El mensaje entero de golpe murió. */
                <div className="space-y-3">
                    {entradas.map(s => (
                        <button key={s.clave} type="button" data-testid={`categoria-${s.clave}`}
                            onClick={() => { setAbierta(s.clave); setSubfiltro(null); }}
                            className="surface w-full p-4 flex items-center justify-between gap-3 text-left hover:border-brand/40 transition-colors">
                            <span className="min-w-0">
                                <span className="block font-bold text-foreground text-sm">{s.nombre}</span>
                                {s.explicacion && (
                                    <span className="block text-muted-foreground text-xs mt-0.5">{s.explicacion}</span>
                                )}
                            </span>
                            <ChevronRight className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                        </button>
                    ))}
                </div>
            ) : (
                /* DENTRO DE UNA CATEGORÍA: su explicación literal, sus fichas, y la vuelta. */
                <div>
                    <button type="button" data-testid="volver-categorias"
                        onClick={() => { setAbierta(null); setSubfiltro(null); }}
                        className="inline-flex items-center gap-1 text-sm font-semibold text-brand mb-3 hover:underline">
                        <ChevronLeft className="w-4 h-4" /> Todas las categorías
                    </button>
                    <h2 className="font-heading text-xl font-bold uppercase text-foreground mb-1">{seccion.nombre}</h2>
                    {seccion.explicacion && <p className="text-muted-foreground text-sm mb-3">{seccion.explicacion}</p>}
                    {/* Los seis apartados de Salud, solo dentro de Salud. */}
                    {seccion.clave === 'salud' && seccion.subfiltros?.length > 0 && (
                        <div className="flex flex-wrap gap-2 mb-4">
                            {seccion.subfiltros.map(sf => (
                                <button key={sf} onClick={() => setSubfiltro(subfiltro === sf ? null : sf)}
                                    className={`px-2.5 py-1 rounded-full text-[11px] font-semibold ${subfiltro === sf ? 'bg-brand/20 text-brand' : 'bg-muted text-muted-foreground'}`}>
                                    {sf}
                                </button>
                            ))}
                        </div>
                    )}
                    <div className="space-y-3">
                        {(subfiltro && seccion.clave === 'salud'
                            ? seccion.suplementos.filter(f => (f.subfiltros || []).some(x => x.toLowerCase() === subfiltro.toLowerCase()))
                            : seccion.suplementos
                        ).map(f => <FichaDeLaGuia key={f.id} ficha={f} />)}
                    </div>
                </div>
            )}

            {/* El descuento, con el texto de Jesús. En la pantalla del protocolo lo pinta
                la propia pantalla junto a la pauta, y aquí se apaga para no repetirlo. */}
            {conDescuento && <div className="mt-6"><Descuento /></div>}

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
        // SIN PAUTA PROPIA: la pantalla ES la guía (doc 19-08, bloque 08), y se llama
        // «Tu suplementación» IGUAL que la del protocolo (Jesús, 21-08). El texto de
        // entrada es el que dictó, tal cual, y debajo van directamente las categorías.
        return <Wrap>
            <h1 className="font-heading text-3xl md:text-4xl font-bold uppercase text-foreground mb-2">
                Tu suplementación
            </h1>
            <TextoDeEntrada texto={guia?.texto_entrada} />
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
                        ? 'Lo que tienes pautado, dosis y cuándo tomarlo.'
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

            {/* EL DESCUENTO, EN LA PANTALLA DEL PROTOCOLO (Jesús, 21-08): antes solo
                vivía dentro de la guía y quien miraba su pauta no lo veía. */}
            <div className="max-w-2xl mt-8"><Descuento /></div>

            {/* Y DEBAJO, LA GUÍA: la ven todos (doc 19-08), también quien ya tiene su
                pauta. Con su rótulo, para que nadie confunda la guía con lo suyo. El
                descuento ya está arriba, junto a la pauta: aquí apagado. */}
            {hayGuia && (
                <section className="mt-10">
                    <h2 className="font-heading text-xl font-bold uppercase text-foreground mb-1">La guía de suplementación</h2>
                    <p className="text-muted-foreground text-sm mb-4 max-w-2xl">
                        Los suplementos que más utilizo y recomiendo, por si quieres consultarla.
                    </p>
                    <GuiaDeSuplementacion api={api} guia={guia} conDescuento={false} />
                </section>
            )}
        </Wrap>
    );
};

export default SupplementsPage;
