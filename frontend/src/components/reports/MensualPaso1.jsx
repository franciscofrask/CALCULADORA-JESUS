/**
 * PASO 1 DEL MENSUAL · ACTUALIZAR TUS DATOS
 *
 * Documento «El reporte mensual» (1-09-2026):
 *
 *     «Sale de tus check-in. Si algo no cuadra o te falta, lo arreglas al final.»
 *
 * Este paso NO pregunta: enseña. El peso, lo que ha hecho y cómo se ha sentido salen de lo
 * que ya está guardado, y lo único que contesta son los huecos: los días de los que la app
 * no tiene ni un sí ni un no. De ahí sale el cumplimiento, que es la idea de siempre (no
 * se le pide que se puntúe, se le enseña lo que hay).
 *
 * El selector de arriba CAMBIA EL BLOQUE ENTERO, no solo el peso: al pasar a «Desde que
 * empezaste» se vuelven a pedir el peso, la actividad y las sensaciones del programa
 * completo. Los huecos no: «esos son siempre de los últimos 28», así que se conservan los
 * que llegaron en la primera carga.
 *
 * «Modificar» es el «lo arreglas al final» del subtítulo: abre el peso (y el % de grasa el
 * mes que toca) para corregir lo que la app haya sacado mal.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { DosBotones, Estrellas } from './piezas';
import { PESO_MIN, PESO_MAX } from '../../lib/pesoValido';

const ORANGE = '#FF671F';
const VERDE = '#22C55E';
const ROJO = '#EF4444';

/** «78,4 kg». Con coma, como en toda la app. */
const kg = (v) => (v == null ? null : `${String(v).replace('.', ',')} kg`);

/** «−2,8 kg» / «+1,2 kg». El signo va delante y con el menos de verdad, no un guion. */
const diferenciaKg = (v) => {
    if (v == null) return null;
    const n = Number(v);
    const texto = Math.abs(n).toFixed(1).replace('.', ',');
    return `${n > 0 ? '+' : n < 0 ? '−' : ''}${texto} kg`;
};

/**
 * La línea de la maqueta: una curva pequeña, sin ejes ni números.
 *
 * Es una polilínea en SVG y no una gráfica de verdad a propósito. Aquí no se lee ningún
 * valor concreto -- los números están escritos al lado --, solo la forma: si sube o baja.
 * Meter recharts para esto sería cargar la librería entera para pintar seis puntos.
 *
 * `circulos` son los índices que llevan punto marcado (los reportes anteriores).
 */
const MiniLinea = ({ valores, color = VERDE, circulos = [], ancho = 92, alto = 26 }) => {
    const xs = (valores || []).map(Number).filter((n) => Number.isFinite(n));
    if (xs.length < 2) return <span className="inline-block" style={{ width: ancho }} />;
    const min = Math.min(...xs);
    const max = Math.max(...xs);
    const rango = max - min || 1;
    const paso = ancho / (xs.length - 1);
    const punto = (v, i) => [i * paso, alto - 2 - ((v - min) / rango) * (alto - 4)];
    const puntos = xs.map(punto);
    return (
        <svg width={ancho} height={alto} viewBox={`0 0 ${ancho} ${alto}`} aria-hidden="true"
            className="shrink-0 overflow-visible">
            <polyline fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round"
                strokeLinejoin="round" points={puntos.map(([x, y]) => `${x},${y}`).join(' ')} />
            {circulos.map((i) => {
                const p = puntos[i];
                if (!p) return null;
                return <circle key={i} cx={p[0]} cy={p[1]} r="2.6" fill="none"
                    stroke={color} strokeWidth="1.6" />;
            })}
        </svg>
    );
};

/**
 * De qué color va la línea de una sensación.
 *
 * En la maqueta el descanso (2,9) va en rojo, la energía (3,1) en verde y el hambre (3,6)
 * en rojo. O sea: el listón es el 3, y en el hambre está al revés que en las otras dos,
 * porque tener mucha hambre no es una buena noticia. Se escribe aquí y no en el servidor
 * porque es cómo se pinta, no lo que vale.
 */
const colorDeLaSensacion = (clave, media) => {
    if (media == null) return ORANGE;
    const bien = clave === 'hambre' ? media <= 3 : media >= 3;
    return bien ? VERDE : ROJO;
};

const Tarjeta = ({ titulo, children, testid }) => (
    <div className="rounded-2xl bg-card border border-border p-4 space-y-3" data-testid={testid}>
        {titulo && (
            <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                {titulo}
            </p>
        )}
        {children}
    </div>
);

const MensualPaso1 = ({ api, valores, set, pideGrasa, grasa, huecosRespuestas,
                        onHueco, onConfirmar }) => {
    const [periodo, setPeriodo] = useState('ultimo');
    const [ficha, setFicha] = useState(null);
    const [huecos, setHuecos] = useState(null);      // siempre los de los últimos 28
    const [cargando, setCargando] = useState(true);
    const [fallo, setFallo] = useState(false);
    // SI NO HAY PESO QUE CONFIRMAR, EL CAMPO SALE ABIERTO. El servidor deja la casilla
    // vacía a propósito cuando el único peso que tiene es viejo (punto 34 del doc del
    // 24-08). En ese caso, «Confirmar» sin nada que confirmar solo daría un aviso rojo:
    // mejor enseñarle el hueco desde el principio.
    const [modificando, setModificando] = useState(() => !valores.weight);

    const cargar = useCallback(async (cual) => {
        setCargando(true);
        try {
            const r = await api.get('/reports/mensual/paso1', { params: { periodo: cual } });
            setFicha(r.data);
            setFallo(false);
            // Los huecos solo llegan en el periodo corto. En el largo vienen a null y se
            // conservan los que ya había: no cambian al mirar el programa entero.
            if (r.data?.huecos) setHuecos(r.data.huecos);
        } catch (e) {
            console.error('No se pudo cargar el paso 1 del mensual', e);
            setFallo(true);
        } finally {
            setCargando(false);
        }
    }, [api]);

    useEffect(() => { cargar(periodo); }, [cargar, periodo]);

    const peso = ficha?.peso || {};
    const serie = (peso.serie || []).map((p) => p.valor);
    // Los círculos van por fecha: son pesajes de la misma serie, así que hay que saber en
    // qué punto de la línea cae cada uno.
    const indices = (peso.circulos || [])
        .map((c) => (peso.serie || []).findIndex((p) => p.fecha === c.fecha))
        .filter((i) => i >= 0);

    const etiquetaPeriodo = periodo === 'principio' ? 'Desde que empezaste' : 'Desde tu último reporte';

    // ── LA OTRA VERSIÓN DEL PASO 1: LA DEL QUE NO TIENE CHECK-IN ──
    //
    // «El paso 1 se acorta, igual que en el quincenal. El peso y las fotos se le piden
    // igual, que ésos no dependen de haber apuntado nada.»
    //
    // Sin cierres con los que llenarlo, este paso salía vacío -- filas sin denominador,
    // sensaciones sin media -- y encima le pedía confirmar una nada. Y tampoco sale el
    // selector de periodo: no hay dos tramos que comparar cuando no hay datos en ninguno.
    if (ficha?.sin_datos) {
        const faltan = (ficha.preguntas || []).filter((p) => valores[p.clave] == null).length;
        return (
            <div className="space-y-4" data-testid="mensual-paso1">
                <p className="text-[15px] text-muted-foreground" data-testid="paso1-sin-datos-sub">
                    Cinco preguntas y pasas al paso 2. El peso y las fotos se te piden igual.
                </p>
                <div className="rounded-2xl border border-[#EF4444]/40 bg-[#EF4444]/5 p-4">
                    <p className="text-[15px] text-foreground">
                        <span className="font-bold">No tengo todos los datos de tus check-in diarios</span>,
                        así que te lo pregunto aquí.
                    </p>
                </div>
                {(ficha.preguntas || []).map((p) => (
                    <Tarjeta key={p.clave} testid={`paso1-pregunta-${p.clave}`}>
                        <p className="text-sm text-foreground">{p.pregunta}</p>
                        <Estrellas testid={p.clave} valor={valores[p.clave]}
                            onChange={(v) => set(p.clave, v)} />
                    </Tarjeta>
                ))}

                {/* EL PESO SE LE PIDE IGUAL, y el % de grasa el mes que toca. No dependen
                    de haber apuntado nada: se pesa hoy y ya está. */}
                <Tarjeta titulo="Tu peso de hoy" testid="paso1-peso-sin-datos">
                    <div className="flex items-center gap-2">
                        <input type="number" step="0.1" min={PESO_MIN} max={PESO_MAX} inputMode="decimal"
                            value={valores.weight} onChange={(e) => set('weight', e.target.value)}
                            placeholder="—" data-testid="weight-input"
                            className="flex-1 min-w-0 bg-muted border border-input rounded-xl px-3 py-3 text-foreground text-2xl font-bold placeholder-foreground/20 focus:outline-none focus:border-[#FF671F] transition-colors" />
                        <span className="text-lg text-foreground/40 font-bold">kg</span>
                    </div>
                    {pideGrasa && (
                        <div className="pt-1">
                            <p className="text-sm text-foreground mb-1.5">Tu porcentaje de grasa</p>
                            <div className="flex items-center gap-2">
                                <input type="number" step="0.5" min="3" max="70" inputMode="decimal"
                                    value={valores.body_fat ?? ''} onChange={(e) => set('body_fat', e.target.value)}
                                    placeholder="—" data-testid="body-fat-input"
                                    className="flex-1 min-w-0 bg-muted border border-input rounded-xl px-3 py-3 text-foreground text-2xl font-bold placeholder-foreground/20 focus:outline-none focus:border-[#FF671F] transition-colors" />
                                <span className="text-lg text-foreground/40 font-bold">%</span>
                            </div>
                        </div>
                    )}
                </Tarjeta>

                <button type="button" onClick={onConfirmar} disabled={faltan > 0}
                    data-testid="paso1-continuar"
                    className="w-full rounded-xl py-3 text-sm font-bold text-white uppercase tracking-wider disabled:opacity-40"
                    style={{ backgroundColor: ORANGE }}>
                    Continuar
                </button>
                {faltan > 0 && (
                    <p className="text-[13px] text-muted-foreground text-center -mt-2">
                        Te {faltan === 1 ? 'queda una' : `quedan ${faltan}`}.
                    </p>
                )}
            </div>
        );
    }

    return (
        <div className="space-y-4" data-testid="mensual-paso1">
            <p className="text-[15px] text-muted-foreground">
                Sale de tus check-in. Si algo no cuadra o te falta, lo arreglas al final.
            </p>
            {/* ── EL SELECTOR ── «cambia el bloque entero, no solo el peso» ── */}
            <div className="grid grid-cols-2 gap-2" data-testid="paso1-periodo">
                {[
                    { v: 'ultimo', l: 'Desde tu último reporte' },
                    { v: 'principio', l: 'Desde que empezaste' },
                ].map((o) => {
                    const activo = periodo === o.v;
                    // Los días los dice el servidor, no se calculan aquí: el periodo corto
                    // se recorta por su fecha de alta, así que no siempre son 28.
                    const dias = activo ? ficha?.periodo?.dias : null;
                    return (
                        <button key={o.v} type="button" data-testid={`paso1-periodo-${o.v}`}
                            onClick={() => setPeriodo(o.v)}
                            className={`rounded-xl border px-3 py-3 text-sm font-bold leading-tight transition-all ${
                                activo ? 'border-[#FF671F] bg-[#FF671F]/10 text-foreground'
                                       : 'border-border bg-card text-foreground/60 hover:border-foreground/30'}`}>
                            {o.l}
                            {dias ? (
                                <span className="block text-[11px] font-normal mt-0.5" style={{ color: ORANGE }}>
                                    {dias} días
                                </span>
                            ) : null}
                        </button>
                    );
                })}
            </div>

            {fallo && (
                <div className="rounded-2xl border border-border bg-card p-4">
                    <p className="text-sm text-foreground">No hemos podido traer tus datos de este mes.</p>
                    <button type="button" onClick={() => cargar(periodo)} data-testid="paso1-reintentar"
                        className="mt-2 text-sm font-bold" style={{ color: ORANGE }}>
                        Probar otra vez
                    </button>
                </div>
            )}

            {cargando && !ficha ? (
                <div className="animate-pulse space-y-3">
                    <div className="h-28 bg-card rounded-2xl" />
                    <div className="h-44 bg-card rounded-2xl" />
                </div>
            ) : ficha ? (
                <>
                    {/* ── TU PESO ── */}
                    <Tarjeta titulo="Tu peso" testid="paso1-peso">
                        <div className="flex items-center gap-3">
                            <p className="text-sm text-foreground/80 leading-tight flex-1 min-w-0">
                                {etiquetaPeriodo}
                            </p>
                            <MiniLinea valores={serie} circulos={indices} />
                            <p className="text-lg font-bold text-foreground tabular-nums shrink-0"
                                data-testid="paso1-peso-actual">
                                {kg(peso.actual) || '—'}
                            </p>
                        </div>
                        {peso.diferencia != null && (
                            <p className="text-[13px] text-muted-foreground tabular-nums">
                                {kg(peso.primero)} <span aria-hidden="true">&rarr;</span> {kg(peso.actual)}
                                <span className="font-bold text-foreground ml-2">{diferenciaKg(peso.diferencia)}</span>
                            </p>
                        )}
                        {peso.nota && <p className="text-sm text-foreground/80">{peso.nota}</p>}
                    </Tarjeta>

                    {/* ── LO QUE HAS HECHO ── */}
                    {(ficha.actividad?.filas || []).length > 0 && (
                        <Tarjeta titulo={ficha.actividad.titulo} testid="paso1-actividad">
                            <div className="-my-1">
                                {ficha.actividad.filas.map((f, i) => (
                                    <div key={f.clave} data-testid={`paso1-fila-${f.clave}`}
                                        className={`flex items-baseline justify-between gap-3 py-2.5 ${
                                            i ? 'border-t border-border' : ''}`}>
                                        <span className="text-sm text-foreground/80">{f.etiqueta}</span>
                                        <span className="text-sm font-bold text-foreground text-right tabular-nums">
                                            {f.valor}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </Tarjeta>
                    )}

                    {/* ── Y CÓMO TE HAS SENTIDO ── */}
                    {(ficha.sensaciones?.filas || []).length > 0 && (
                        <>
                            <Tarjeta titulo="Y cómo te has sentido" testid="paso1-sensaciones">
                                <div className="-my-1">
                                    {ficha.sensaciones.filas.map((f, i) => (
                                        <div key={f.clave} data-testid={`paso1-sensacion-${f.clave}`}
                                            className={`flex items-center gap-3 py-2.5 ${
                                                i ? 'border-t border-border' : ''}`}>
                                            <span className="text-sm text-foreground/80 flex-1 min-w-0">{f.etiqueta}</span>
                                            <MiniLinea valores={f.serie} ancho={72} alto={20}
                                                color={colorDeLaSensacion(f.clave, f.media)} />
                                            <span className="text-base font-bold text-foreground tabular-nums w-10 text-right">
                                                {f.media_label}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            </Tarjeta>
                            <p className="text-[13px] text-muted-foreground -mt-2 px-1">
                                {ficha.sensaciones.pie}
                            </p>
                        </>
                    )}

                    {/* ── LOS HUECOS · lo único que se le pregunta aquí ── */}
                    {(huecos || []).map((h) => (
                        <Tarjeta key={h.tipo} testid={`paso1-hueco-${h.tipo}`}>
                            <p className="text-sm text-foreground">{h.pregunta}</p>
                            <DosBotones testid={`paso1-hueco-${h.tipo}-op`}
                                opciones={h.opciones}
                                valor={huecosRespuestas?.[h.tipo] || ''}
                                onChange={(v) => onHueco(h.tipo, v)} />
                        </Tarjeta>
                    ))}

                    {/* ── MODIFICAR · «si algo no cuadra o te falta, lo arreglas al final» ── */}
                    {modificando && (
                        <Tarjeta titulo="Corrige lo que haga falta" testid="paso1-modificar">
                            <div>
                                <p className="text-sm text-foreground mb-1.5">Tu peso de hoy</p>
                                <div className="flex items-center gap-2">
                                    <input
                                        type="number" step="0.1" min={PESO_MIN} max={PESO_MAX} inputMode="decimal"
                                        value={valores.weight} onChange={(e) => set('weight', e.target.value)}
                                        placeholder="—" data-testid="weight-input"
                                        className="flex-1 min-w-0 bg-muted border border-input rounded-xl px-3 py-3 text-foreground text-2xl font-bold placeholder-foreground/20 focus:outline-none focus:border-[#FF671F] transition-colors" />
                                    <span className="text-lg text-foreground/40 font-bold">kg</span>
                                </div>
                            </div>
                            {/* El % de grasa solo el mes que toca (cada 12 semanas). */}
                            {pideGrasa && (
                                <div>
                                    <p className="text-sm text-foreground mb-1.5">Tu porcentaje de grasa</p>
                                    <div className="flex items-center gap-2">
                                        <input
                                            type="number" step="0.5" min="3" max="70" inputMode="decimal"
                                            value={valores.body_fat ?? ''} onChange={(e) => set('body_fat', e.target.value)}
                                            placeholder="—" data-testid="body-fat-input"
                                            className="flex-1 min-w-0 bg-muted border border-input rounded-xl px-3 py-3 text-foreground text-2xl font-bold placeholder-foreground/20 focus:outline-none focus:border-[#FF671F] transition-colors" />
                                        <span className="text-lg text-foreground/40 font-bold">%</span>
                                    </div>
                                    {grasa?.valor != null && (
                                        <p className="text-[13px] text-muted-foreground mt-1">
                                            El último fue {grasa.valor} %
                                            {grasa.semanas != null && `, hace ${grasa.semanas} semanas`}.
                                        </p>
                                    )}
                                </div>
                            )}
                        </Tarjeta>
                    )}
                </>
            ) : null}

            {/* ── LOS DOS BOTONES DEL PASO ── */}
            <div className="flex gap-2">
                <button type="button" onClick={() => setModificando((m) => !m)}
                    data-testid="paso1-modificar-btn"
                    className="rounded-xl px-4 py-3 text-sm font-bold border border-border bg-card text-foreground/70 hover:border-foreground/30 transition-colors">
                    {modificando ? 'Ya está' : 'Modificar'}
                </button>
                <button type="button" onClick={onConfirmar} data-testid="paso1-confirmar"
                    className="flex-1 rounded-xl py-3 text-sm font-bold text-white uppercase tracking-wider"
                    style={{ backgroundColor: ORANGE }}>
                    Confirmar
                </button>
            </div>
        </div>
    );
};

export default MensualPaso1;
