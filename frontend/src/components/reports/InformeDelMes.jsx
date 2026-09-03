/**
 * EL INFORME DEL MES (documento «El informe del mes», 1-09-2026).
 *
 * «Lo que recibe cuando manda el reporte mensual. Las dos pantallas como tienen que quedar.»
 *
 * Diez bloques y en un orden que no es casual: primero dónde está y qué le vas a decir,
 * después lo que ha pasado con su cuerpo (peso, medidas, grasa, fotos) y al final lo que ha
 * hecho él (cumplimiento, su día tipo, sus alimentos, sus extras).
 *
 * DOS REGLAS DEL DOCUMENTO QUE MANDAN SOBRE TODO LO DEMÁS:
 *
 *   1. «El informe no le pide nada.» Lo único que se puede tocar son los selectores de las
 *      fotos y el botón de guardar el desayuno como plantilla. Ni un campo, ni una
 *      pregunta, ni un «sube tus fotos»: para eso está el reporte.
 *   2. Es UNA pantalla en dos momentos, no dos pantallas. Al enviar sale con el hueco del
 *      feedback en gris y con la hora; cuando le contestas, «el mismo informe, con tu
 *      bloque arriba. No es otro documento: es éste, completado».
 *
 * Un bloque sin datos NO SALE. El informe es lo único que el cliente lee del mes, y una
 * tarjeta vacía con un guion dentro se lee como que la app no sabe de él.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

const ORANGE = '#FF671F';
const VERDE = '#22C55E';
const ROJO = '#EF4444';

const COLOR = { verde: 'text-emerald-500', rojo: 'text-red-500', gris: 'text-foreground/30' };

const Tarjeta = ({ titulo, derecha, children, testid, tono }) => (
    <section
        className={`rounded-2xl p-4 space-y-3 border ${
            tono === 'naranja' ? '' : 'bg-card border-border'}`}
        style={tono === 'naranja'
            ? { borderColor: `${ORANGE}66`, backgroundColor: `${ORANGE}0D` } : undefined}
        data-testid={testid}>
        {(titulo || derecha) && (
            <div className="flex items-baseline justify-between gap-3">
                <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                    {titulo}
                </p>
                {derecha && (
                    <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground text-right">
                        {derecha}
                    </p>
                )}
            </div>
        )}
        {children}
    </section>
);

/** Una fila de «etiqueta ......... valor», que es la forma de medio informe. */
const Fila = ({ que, valor, primera, testid }) => (
    <div className={`flex items-baseline justify-between gap-3 py-2 ${
        primera ? '' : 'border-t border-border'}`} data-testid={testid}>
        <span className="text-sm text-foreground/80">{que}</span>
        {/* El número no se parte nunca: «82,8 / kg» en dos líneas se lee como dos datos. */}
        <span className="text-sm font-bold text-foreground tabular-nums text-right whitespace-nowrap">
            {valor}
        </span>
    </div>
);

/**
 * La curva del peso: la línea con un punto por pesaje, sin ejes.
 *
 * Los cuatro rótulos de debajo son las fechas de los extremos y de los cortes, que es lo
 * que la maqueta enseña: «4 jun · 2 jul · 4 ago · 1 sep». No son los ejes de una gráfica,
 * son las cuatro fechas que sitúan la línea.
 */
const CurvaDePeso = ({ serie }) => {
    const xs = (serie || []).map(p => Number(p.valor)).filter(Number.isFinite);
    if (xs.length < 2) return null;
    const ancho = 300, alto = 64;
    const min = Math.min(...xs), max = Math.max(...xs);
    const rango = max - min || 1;
    const punto = (v, i) => [
        (i * ancho) / (xs.length - 1),
        alto - 6 - ((v - min) / rango) * (alto - 12),
    ];
    const puntos = xs.map(punto);

    const fecha = (f) => {
        const d = new Date(`${String(f).slice(0, 10)}T12:00:00`);
        return isNaN(d) ? '' : d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })
            .replace('.', '');
    };
    // Cuatro fechas repartidas, sin repetir la misma dos veces.
    const idx = [...new Set([0, Math.round((xs.length - 1) / 3),
        Math.round((2 * (xs.length - 1)) / 3), xs.length - 1])];

    return (
        <div data-testid="informe-curva">
            <svg viewBox={`0 0 ${ancho} ${alto}`} className="w-full" style={{ height: alto }}
                preserveAspectRatio="none" aria-hidden="true">
                <polyline fill="none" stroke={VERDE} strokeWidth="2" strokeLinecap="round"
                    strokeLinejoin="round" vectorEffect="non-scaling-stroke"
                    points={puntos.map(([x, y]) => `${x},${y}`).join(' ')} />
                {puntos.map(([x, y], i) => (
                    <circle key={i} cx={x} cy={y} r="3" fill="none" stroke={VERDE}
                        strokeWidth="2" vectorEffect="non-scaling-stroke" />
                ))}
            </svg>
            <div className="flex justify-between mt-1">
                {idx.map(i => (
                    <span key={i} className="text-[13px] text-muted-foreground">
                        {fecha(serie[i]?.fecha)}
                    </span>
                ))}
            </div>
        </div>
    );
};

/** 6 · Tus fotos. Dos, y las elige él: es uno de los dos sitios donde puede tocar algo. */
const TusFotos = ({ api, token }) => {
    const [fotos, setFotos] = useState(null);
    const [pose, setPose] = useState('frente');
    const [izq, setIzq] = useState('');
    const [der, setDer] = useState('');
    const [urls, setUrls] = useState({});

    useEffect(() => {
        api.get('/reports/photos')
            .then(r => setFotos(r.data?.photos || []))
            .catch(() => setFotos([]));
    }, [api]);

    const dePose = (fotos || []).filter(f => (f.pose || 'frente') === pose && f.taken_at)
        .sort((a, b) => String(a.taken_at).localeCompare(String(b.taken_at)));

    // Al cambiar de pose se eligen solas la primera y la última, que es la comparación que
    // más dice. A partir de ahí manda él.
    useEffect(() => {
        if (!dePose.length) { setIzq(''); setDer(''); return; }
        setIzq(dePose[0].id);
        setDer(dePose[dePose.length - 1].id);
    }, [pose, fotos]);   // eslint-disable-line react-hooks/exhaustive-deps

    const base = (process.env.REACT_APP_BACKEND_URL || '').replace(/\/$/, '');
    const traer = useCallback((id) => {
        if (!id || urls[id]) return;
        fetch(`${base}/api/reports/photos/${id}`, { headers: { Authorization: `Bearer ${token}` } })
            .then(r => (r.ok ? r.blob() : Promise.reject(new Error('no'))))
            .then(b => setUrls(u => ({ ...u, [id]: URL.createObjectURL(b) })))
            .catch(() => {});
    }, [base, token, urls]);
    useEffect(() => { traer(izq); traer(der); }, [izq, der, traer]);

    if (fotos === null) return null;
    if (!fotos.length) return null;      // sin fotos, el bloque no sale: no se le pide nada

    const cuando = (f) => {
        const d = new Date(`${String(f.taken_at).slice(0, 10)}T12:00:00`);
        return isNaN(d) ? f.taken_at
            : d.toLocaleDateString('es-ES', { day: 'numeric', month: 'long' });
    };

    return (
        <Tarjeta titulo="Tus fotos" testid="informe-fotos">
            <div className="flex gap-2">
                {/* LA POSE SE GUARDA EN SINGULAR, «espalda». El botón decía «espaldas» y por
                    eso salía apagado SIEMPRE: no hay ni habrá una sola foto con esa pose --
                    `routes/checkins.py` solo acepta frente, espalda y perfil, y lo que no
                    esté en esa lista lo guarda sin pose. El rótulo sí es «Espaldas», que es
                    como se dice; lo que tenía que casar es la clave. */}
                {[['frente', 'Frente'], ['espalda', 'Espaldas'], ['perfil', 'Perfil']].map(([v, l]) => {
                    const hay = (fotos || []).some(f => (f.pose || 'frente') === v);
                    const activo = pose === v;
                    return (
                        <button key={v} type="button" disabled={!hay}
                            onClick={() => setPose(v)} data-testid={`informe-pose-${v}`}
                            className={`px-3 py-1.5 rounded-full text-[13px] font-bold transition-colors disabled:opacity-30 ${
                                activo ? 'text-white' : 'bg-muted text-foreground/60'}`}
                            style={activo ? { backgroundColor: ORANGE } : undefined}>
                            {l}
                        </button>
                    );
                })}
            </div>

            {dePose.length ? (
                <>
                    <div className="grid grid-cols-2 gap-2">
                        {[[izq, setIzq, 'izq'], [der, setDer, 'der']].map(([valor, poner, lado]) => (
                            <select key={lado} value={valor} onChange={(e) => poner(e.target.value)}
                                data-testid={`informe-foto-${lado}`}
                                className="bg-muted border border-border rounded-xl px-3 py-2 text-[13px] text-foreground outline-none focus:border-[#FF671F]">
                                {dePose.map(f => (
                                    <option key={f.id} value={f.id}>{cuando(f)}</option>
                                ))}
                            </select>
                        ))}
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                        {[izq, der].map((id, i) => (
                            <div key={i} className="aspect-[3/4] rounded-xl overflow-hidden bg-muted">
                                {urls[id] && <img src={urls[id]} alt="" className="w-full h-full object-cover" />}
                            </div>
                        ))}
                    </div>
                </>
            ) : (
                <p className="text-sm text-muted-foreground">
                    De esta pose todavía no hay ninguna.
                </p>
            )}
        </Tarjeta>
    );
};

/**
 * «GUÁRDAMELA COMO PLANTILLA» (bloque 8 de su documento).
 *
 * Guarda la combinación que él ya reconoce como su desayuno -- los alimentos del día tipo,
 * con las cantidades que enseña la fila, que son la MEDIANA del mes -- como una favorita de
 * COMIDA, que es la que luego se pone de un toque en cualquier comida desde Nutrición.
 *
 * El nombre se pone solo y con la fecha detrás: pedirle que escriba uno sería pedirle algo,
 * y el informe no le pide nada. Si ya tiene una con ese nombre, el servidor no protesta
 * (eso solo lo mira la pantalla de favoritas del día), así que la fecha las distingue.
 */
const ComoPlantilla = ({ api, fila }) => {
    const [estado, setEstado] = useState('');       // '' | 'guardando' | 'hecho'
    const guardar = async () => {
        if (estado) return;
        setEstado('guardando');
        try {
            await api.post('/diets/favorites', {
                name: `${fila.nombre} de siempre · ${new Date().toLocaleDateString('es-ES',
                    { day: 'numeric', month: 'long' })}`,
                ambito: 'comida',
                comida: fila.clave,
                alimentos: (fila.items || [])
                    .filter((x) => x.alimento_id != null)
                    .map((x) => ({ alimento_id: x.alimento_id, nombre: x.nombre,
                                   cantidad_g: x.gramos })),
            });
            setEstado('hecho');
        } catch (e) {
            console.error('[informe] no se pudo guardar la plantilla', e);
            setEstado('');
            toast.error('No hemos podido guardarla. Inténtalo de nuevo.');
        }
    };
    // Ya guardada, el botón se queda diciendo dónde está: guardarla dos veces no aporta
    // nada y dejar el botón igual invita a hacerlo.
    if (estado === 'hecho') {
        return (
            <span className="mt-2 block text-[13px]" style={{ color: VERDE }}
                data-testid="informe-plantilla-hecha">
                Guardada · La tienes en tus comidas favoritas
            </span>
        );
    }
    return (
        <button type="button" onClick={guardar} disabled={estado === 'guardando'}
            data-testid="informe-guardar-plantilla"
            className="mt-2 rounded-full border px-3 py-1.5 text-[13px] font-bold transition-colors
                       disabled:opacity-60"
            style={{ borderColor: ORANGE, color: ORANGE }}>
            {estado === 'guardando' ? 'Guardando...' : 'Guárdamela como plantilla'}
        </button>
    );
};

const InformeDelMes = ({ informe, api, token }) => {
    const b = informe?.bloques;
    if (!b) return null;

    const { periodo, donde_estas: donde, feedback, peso, medidas, grasa, hecho,
            dia_tipo: dia, preferencias, extras } = b;

    return (
        <div className="space-y-3" data-testid="informe-del-mes">
            {/* ── CABECERA ── */}
            <div>
                {periodo?.label && (
                    <p className="text-[11px] font-bold uppercase tracking-wider" style={{ color: ORANGE }}>
                        {periodo.label}
                    </p>
                )}
                <h2 className="text-2xl font-bold text-foreground uppercase"
                    style={{ fontFamily: 'Barlow Condensed', letterSpacing: '0.02em' }}>
                    Tu informe mensual
                </h2>
            </div>

            {/* ── 1 · DÓNDE ESTÁS ── */}
            {(donde?.objetivo_label || donde?.ciclo_label) && (
                <Tarjeta testid="informe-donde-estas">
                    <div className="flex items-start justify-between gap-3">
                        <div>
                            <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                                Tu objetivo
                            </p>
                            <p className="text-base font-bold text-foreground">
                                {donde.objetivo_label || '—'}
                            </p>
                        </div>
                        <div className="text-right">
                            <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                                Tu ciclo
                            </p>
                            <p className="text-base font-bold" style={{ color: ORANGE }}>
                                {donde.ciclo_label || '—'}
                            </p>
                        </div>
                    </div>
                </Tarjeta>
            )}

            {/* ── 2 · TU FEEDBACK Y TU PROGRAMA NUEVO ── */}
            {feedback?.pendiente ? (
                <Tarjeta testid="informe-feedback-pendiente">
                    <p className="text-sm text-muted-foreground">{feedback.aviso}</p>
                </Tarjeta>
            ) : feedback?.texto ? (
                <Tarjeta tono="naranja" testid="informe-feedback">
                    <p className="text-base text-foreground leading-snug">{feedback.texto}</p>
                    <div className="flex items-center gap-2 pt-1">
                        {feedback.iniciales && (
                            <span className="w-7 h-7 rounded-full grid place-items-center text-[11px] font-bold text-white"
                                style={{ backgroundColor: ORANGE }}>
                                {feedback.iniciales}
                            </span>
                        )}
                        <span className="text-[13px] text-muted-foreground">
                            {feedback.firma}{feedback.fecha_label ? ` · ${feedback.fecha_label}` : ''}
                        </span>
                    </div>
                </Tarjeta>
            ) : null}

            {/* ── 3 · TU PESO ── */}
            {peso?.hay && (
                <Tarjeta titulo="Tu peso" derecha={peso.titulo_cambio} testid="informe-peso">
                    <CurvaDePeso serie={peso.serie} />
                    <div className="-my-2">
                        <Fila primera que="Empezaste el mes en" valor={peso.empezaste_label} />
                        <Fila que="Lo acabas en" valor={peso.acabas_label} />
                        <Fila que="Desde tu último reporte" valor={peso.cambio_label} />
                        {peso.al_empezar_label && (
                            <Fila que="Cuando empezaste pesabas" valor={peso.al_empezar_label} />
                        )}
                        {peso.desde_el_principio_label && (
                            <Fila que="Desde que empezaste" valor={peso.desde_el_principio_label} />
                        )}
                    </div>
                    {(peso.por_semana || []).length > 0 && (
                        <div className="pt-2 border-t border-border">
                            <p className="text-[13px] text-muted-foreground mb-1">
                                Porcentaje del peso total que has ido bajando por semana.
                            </p>
                            <div className="-my-2">
                                {peso.por_semana.map((s, i) => (
                                    <Fila key={s.semana} primera={i === 0}
                                        que={`Semana ${s.semana}`} valor={`${s.pct} %`} />
                                ))}
                            </div>
                        </div>
                    )}
                </Tarjeta>
            )}

            {/* ── 4 · TUS MEDIDAS ── */}
            {medidas?.hay && (
                <Tarjeta titulo="Tus medidas" testid="informe-medidas">
                    <div className="grid grid-cols-[1fr_3.5rem_3.5rem] gap-2 items-baseline">
                        <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                            Diez tomas
                        </span>
                        <span className="text-[13px] text-muted-foreground text-right">Mes ant.</span>
                        <span className="text-[13px] text-muted-foreground text-right">1ª toma</span>
                        {medidas.filas.map(f => (
                            <React.Fragment key={f.clave}>
                                <span className="text-sm text-foreground/80 border-t border-border pt-2">
                                    {f.etiqueta}
                                </span>
                                {['mes', 'primera'].map(cual => (
                                    <span key={cual}
                                        className={`text-base font-bold tabular-nums text-right border-t border-border pt-2 ${
                                            f[cual] ? COLOR[f[cual].color] : 'text-foreground/20'}`}>
                                        {f[cual] ? f[cual].label : '—'}
                                    </span>
                                ))}
                            </React.Fragment>
                        ))}
                    </div>
                </Tarjeta>
            )}

            {/* ── 5 · TU PORCENTAJE DE GRASA ── */}
            <Tarjeta titulo="Tu porcentaje de grasa" derecha={grasa?.cuando}
                testid="informe-grasa">
                <p className="text-sm text-foreground/80">{grasa?.explicacion}</p>
                {grasa?.hay && <p className="text-sm text-foreground/80">{grasa.ultima}</p>}
            </Tarjeta>

            {/* ── 6 · TUS FOTOS ── */}
            {api && <TusFotos api={api} token={token} />}

            {/* ── 7 · LO QUE HAS HECHO ── */}
            {hecho?.hay && (
                <Tarjeta titulo="Lo que has hecho" testid="informe-hecho">
                    <div className="-my-1">
                        {hecho.filas.map((f, i) => (
                            <div key={f.clave} data-testid={`informe-hecho-${f.clave}`}
                                className={`grid grid-cols-2 gap-3 py-2.5 ${
                                    i ? 'border-t border-border' : ''}`}>
                                <span className="flex items-baseline justify-between gap-2">
                                    <span className="text-sm text-foreground/80">{f.etiqueta}</span>
                                    <span className="text-sm font-bold text-foreground tabular-nums">{f.valor}</span>
                                </span>
                                {f.valor2 != null && (
                                    <span className="flex items-baseline justify-between gap-2">
                                        <span className="text-sm text-foreground/80">{f.etiqueta2}</span>
                                        <span className="text-sm font-bold text-foreground tabular-nums">{f.valor2}</span>
                                    </span>
                                )}
                            </div>
                        ))}
                    </div>
                </Tarjeta>
            )}

            {/* ── 8 · TU DÍA TIPO ── */}
            {dia?.hay && (
                <Tarjeta titulo="Tu día tipo" testid="informe-dia-tipo">
                    <p className="text-[13px] text-muted-foreground -mt-1">
                        La combinación que más repites en cada comida, y cuántos días.
                    </p>
                    <div className="-my-1">
                        {dia.filas.map((f, i) => (
                            <div key={f.clave} data-testid={`informe-dia-${f.clave}`}
                                className={`grid grid-cols-[4.5rem_1fr] gap-3 py-3 ${
                                    i ? 'border-t border-border' : ''}`}>
                                <span className="text-[13px] font-bold" style={{ color: ORANGE }}>
                                    {f.momento}
                                </span>
                                <span>
                                    <span className="block text-sm font-bold text-foreground">{f.nombre}</span>
                                    <span className="block text-[13px] text-muted-foreground">{f.texto}</span>
                                    <span className="block text-base text-foreground/70 mt-0.5">{f.cuantos}</span>
                                    {/* EL ÚNICO BOTÓN DEL INFORME, ADEMÁS DE LOS SELECTORES DE
                                        LAS FOTOS. Su documento lo dice dos veces: la maqueta lo
                                        dibuja bajo el desayuno y el pie remata «lo único que
                                        puede tocar son los selectores de las fotos y el botón de
                                        guardar SU DESAYUNO como plantilla». Por eso va en la
                                        primera comida del día y no en todas: ponerlo en las seis
                                        convertiría el informe en una pantalla de botones, que es
                                        justo lo que él no quiere.
                                        Solo cuando esa comida es una de verdad: si «cambia casi
                                        cada día» no hay plantilla que guardar. */}
                                    {i === 0 && !f.varia && (f.items || []).some(x => x.alimento_id != null) && (
                                        <ComoPlantilla api={api} fila={f} />
                                    )}
                                </span>
                            </div>
                        ))}
                    </div>
                </Tarjeta>
            )}

            {/* ── 9 · PREFERENCIAS CONCRETAS DE ALIMENTOS ── */}
            {preferencias?.hay && (
                <Tarjeta titulo="Preferencias concretas de alimentos" testid="informe-preferencias">
                    <p className="text-[13px] text-muted-foreground -mt-1">
                        Tus fuentes de proteína, hidratos y grasas preferidas, y{' '}
                        <b className="text-foreground">las veces que las has puesto</b> este mes.
                    </p>
                    {[['proteina', 'Proteína'], ['hidratos', 'Hidratos'], ['grasas', 'Grasas']].map(([k, l]) => (
                        (preferencias[k] || []).length > 0 && (
                            <div key={k} data-testid={`informe-preferencias-${k}`}>
                                <p className="text-[13px] font-bold mb-1" style={{ color: ORANGE }}>{l}</p>
                                <div className="-my-1">
                                    {preferencias[k].map((a, i) => (
                                        <Fila key={a.nombre} primera={i === 0}
                                            que={a.nombre} valor={a.label} />
                                    ))}
                                </div>
                            </div>
                        )
                    ))}
                </Tarjeta>
            )}

            {/* ── 10 · EXTRAS REGISTRADOS ── */}
            {extras?.hay && (
                <Tarjeta titulo="Extras registrados" testid="informe-extras">
                    <p className="text-[13px] text-muted-foreground -mt-1">{extras.titulo}</p>
                    <div className="-my-1">
                        {extras.lista.map((e, i) => (
                            <div key={`${e.fecha}-${i}`}
                                className={`flex items-baseline gap-3 py-2 ${
                                    i ? 'border-t border-border' : ''}`}>
                                <span className="text-[13px] text-muted-foreground w-14 shrink-0">
                                    {e.dia_label}
                                </span>
                                <span className="text-sm text-foreground">{e.texto}</span>
                            </div>
                        ))}
                    </div>
                </Tarjeta>
            )}
        </div>
    );
};

export default InformeDelMes;
