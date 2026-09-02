/**
 * PASO 1 DEL QUINCENAL · ACTUALIZAR TUS DATOS
 *
 * «Todo lo validado antes del 1 de septiembre», «Las tres pantallas» y «Las dos versiones
 * del paso 1». Es el mismo paso que el del mensual -- enseña lo que ya está guardado y solo
 * pregunta los huecos -- con dos cambios, y los dos son suyos:
 *
 *   - EL PESO ES EL DE LA SEMANA, con sus tres días:
 *
 *         Peso semanal                       78,4 kg
 *         78,6  Miércoles          78,2  Jueves          —  Viernes
 *         Dos días seguidos entre el miércoles y el viernes.
 *
 *     El número de arriba solo se entiende si se ven los días de los que sale. Aquí no se
 *     calcula nada: la cascada es la de `core/series_cliente.peso_semanal`, la de siempre.
 *
 *   - SIN SELECTOR DE PERIODO. «Desde que empezaste» es del mensual; en quince días no hay
 *     dos tramos que comparar.
 *
 * Y LA OTRA VERSIÓN, la del que no tiene check-in: «No tengo todos los datos de tus
 * check-in diarios, así que te lo pregunto aquí». Cinco estrellas y al paso 2. No es un
 * caso raro: es el cliente que se apunta y tarda dos semanas en coger el ritmo, y a ese el
 * paso 1 normal le salía vacío y encima le pedía confirmarlo.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { DosBotones, Estrellas } from './piezas';

const ORANGE = '#FF671F';
const VERDE = '#22C55E';
const ROJO = '#EF4444';

/** Igual que en el mensual: el listón es el 3, y en el hambre está al revés. */
const colorDeLaSensacion = (clave, media) => {
    if (media == null) return ORANGE;
    const bien = clave === 'hambre' ? media <= 3 : media >= 3;
    return bien ? VERDE : ROJO;
};

const MiniLinea = ({ valores, color = VERDE, ancho = 72, alto = 20 }) => {
    const xs = (valores || []).map(Number).filter((n) => Number.isFinite(n));
    if (xs.length < 2) return <span className="inline-block" style={{ width: ancho }} />;
    const min = Math.min(...xs);
    const max = Math.max(...xs);
    const rango = max - min || 1;
    const paso = ancho / (xs.length - 1);
    return (
        <svg width={ancho} height={alto} viewBox={`0 0 ${ancho} ${alto}`} aria-hidden="true"
            className="shrink-0 overflow-visible">
            <polyline fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round"
                strokeLinejoin="round"
                points={xs.map((v, i) => `${i * paso},${alto - 2 - ((v - min) / rango) * (alto - 4)}`).join(' ')} />
        </svg>
    );
};

const Tarjeta = ({ titulo, extra, children, testid }) => (
    <div className="rounded-2xl bg-card border border-border p-4 space-y-3" data-testid={testid}>
        {(titulo || extra) && (
            <div className="flex items-baseline justify-between gap-3">
                {titulo && (
                    <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                        {titulo}
                    </p>
                )}
                {extra && (
                    <p className="text-lg font-bold text-foreground tabular-nums shrink-0">{extra}</p>
                )}
            </div>
        )}
        {children}
    </div>
);

/**
 * LOS TRES DÍAS DE LA PESADA. El que entra en la media va marcado; el que no se pesó, con
 * una raya. No es decorativo: es la respuesta a «¿de dónde sale este número?», que es lo
 * primero que se pregunta quien ve un peso que él no ha escrito.
 */
const DiasDelPeso = ({ dias }) => (
    <div className="grid grid-cols-3 gap-2" data-testid="quincenal-peso-dias">
        {(dias || []).map((d) => (
            <div key={d.clave} data-testid={`quincenal-peso-${d.clave}`}
                className={`rounded-xl border px-2 py-2 text-center ${
                    d.en_la_pareja ? 'border-[#FF671F] bg-[#FF671F]/10' : 'border-border bg-muted'}`}>
                <p className={`text-base font-bold tabular-nums ${
                    d.valor == null ? 'text-foreground/30' : 'text-foreground'}`}>
                    {d.label}
                </p>
                <p className="text-[11px] text-muted-foreground">{d.etiqueta}</p>
            </div>
        ))}
    </div>
);

const QuincenalPaso1 = ({ api, valores, set, huecosRespuestas, onHueco, onConfirmar }) => {
    const [ficha, setFicha] = useState(null);
    const [cargando, setCargando] = useState(true);
    const [fallo, setFallo] = useState(false);
    // SI NO HAY PESO QUE CONFIRMAR, EL CAMPO SALE ABIERTO. Es lo mismo que hace el mensual:
    // «Confirmar» sin nada que confirmar solo daría un aviso rojo. Se decide cuando llegan
    // los datos, no al montar: al montar todavía no se sabe si hay peso de la semana.
    const [modificando, setModificando] = useState(false);

    const cargar = useCallback(async () => {
        setCargando(true);
        try {
            // `?dia=` es del modo revisión y el servidor solo se lo acepta al equipo: la
            // semana del peso es la del día en que se abre el reporte, así que un martes
            // esta pantalla no puede enseñar una pareja de miércoles y jueves.
            const dia = new URLSearchParams(window.location.search).get('dia');
            const r = await api.get('/reports/quincenal/paso1', { params: dia ? { dia } : {} });
            setFicha(r.data);
            setFallo(false);
        } catch (e) {
            console.error('No se pudo cargar el paso 1 del quincenal', e);
            setFallo(true);
        } finally {
            setCargando(false);
        }
    }, [api]);

    useEffect(() => { cargar(); }, [cargar]);

    // EL PESO DE LA SEMANA VA YA PUESTO EN EL REPORTE, y solo si es de ESTA semana: el
    // servidor deja `valor` a null cuando lo único que tiene es un peso viejo, porque
    // mandarlo sería fechar de hoy un pesaje de hace nueve días (ver `peso_semanal_por_dias`).
    const semanal = ficha?.peso_semanal;
    const puesto = semanal?.valor;
    useEffect(() => {
        if (puesto != null && (valores.weight === '' || valores.weight == null)) {
            set('weight', String(puesto));
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [puesto]);

    // Y en cuanto se sabe que NO hay peso de la semana, el campo se abre solo.
    useEffect(() => {
        if (ficha && !ficha.sin_datos && puesto == null && !valores.weight) setModificando(true);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [ficha, puesto]);

    if (cargando && !ficha) {
        return (
            <div className="animate-pulse space-y-3" data-testid="quincenal-paso1">
                <div className="h-28 bg-card rounded-2xl" />
                <div className="h-44 bg-card rounded-2xl" />
            </div>
        );
    }

    if (fallo && !ficha) {
        return (
            <div className="rounded-2xl border border-border bg-card p-4" data-testid="quincenal-paso1">
                <p className="text-sm text-foreground">No hemos podido traer tus datos de esta quincena.</p>
                <button type="button" onClick={cargar} data-testid="quincenal-paso1-reintentar"
                    className="mt-2 text-sm font-bold" style={{ color: ORANGE }}>
                    Probar otra vez
                </button>
            </div>
        );
    }

    // ── LA VERSIÓN SIN CHECK-IN · «cinco preguntas y pasas al paso 2» ──
    if (ficha?.sin_datos) {
        const contestadas = (ficha.preguntas || []).filter((p) => valores[p.clave] != null).length;
        const faltan = (ficha.preguntas || []).length - contestadas;
        return (
            <div className="space-y-4" data-testid="quincenal-paso1">
                <p className="text-[15px] text-foreground/80" data-testid="quincenal-sin-datos">
                    <span className="font-bold">No tengo todos los datos de tus check-in diarios</span>,
                    así que te lo pregunto aquí.
                </p>
                {(ficha.preguntas || []).map((p) => (
                    <Tarjeta key={p.clave} testid={`quincenal-pregunta-${p.clave}`}>
                        <p className="text-sm text-foreground">{p.pregunta}</p>
                        <Estrellas testid={p.clave} valor={valores[p.clave]}
                            onChange={(v) => set(p.clave, v)} />
                    </Tarjeta>
                ))}
                {/* EL PESO, SOLO SI NO LO TENEMOS. La maqueta de esta versión no lo pide, y
                    con razón: no tener check-in y no haberse pesado son cosas distintas, y
                    al que se pesó ya se le ha cogido. Pero el reporte no se puede mandar sin
                    peso, así que al que tampoco lo tiene se le pide aquí en vez de dejarle
                    pulsar «Continuar» y frenarlo en el paso siguiente. */}
                {!puesto && (
                    <Tarjeta testid="quincenal-peso-suelto">
                        <p className="text-sm text-foreground">
                            No tengo tu peso de esta semana. Ponlo y seguimos.
                        </p>
                        <div className="flex items-center gap-2">
                            <input type="number" step="0.1" min="25" max="300" inputMode="decimal"
                                value={valores.weight} onChange={(e) => set('weight', e.target.value)}
                                placeholder="—" data-testid="weight-input"
                                className="flex-1 min-w-0 bg-muted border border-input rounded-xl px-3 py-3 text-foreground text-2xl font-bold placeholder-foreground/20 focus:outline-none focus:border-[#FF671F] transition-colors" />
                            <span className="text-lg text-foreground/40 font-bold">kg</span>
                        </div>
                    </Tarjeta>
                )}
                <button type="button" onClick={onConfirmar} disabled={faltan > 0}
                    data-testid="quincenal-paso1-continuar"
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
        <div className="space-y-4" data-testid="quincenal-paso1">
            {/* ── PESO SEMANAL ── */}
            <Tarjeta titulo="Peso semanal" extra={semanal?.label || '—'} testid="quincenal-peso">
                <DiasDelPeso dias={semanal?.dias} />
                <p className="text-[13px] text-muted-foreground">{semanal?.pie}</p>
                {semanal?.nota && (
                    <p className="text-[13px] text-foreground/80" data-testid="quincenal-peso-nota">
                        {semanal.nota}
                    </p>
                )}
            </Tarjeta>

            {/* ── LO QUE HAS HECHO ── */}
            {(ficha?.actividad?.filas || []).length > 0 && (
                <Tarjeta titulo={ficha.actividad.titulo} testid="quincenal-actividad">
                    <div className="-my-1">
                        {ficha.actividad.filas.map((f, i) => (
                            <div key={f.clave} data-testid={`quincenal-fila-${f.clave}`}
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
            {(ficha?.sensaciones?.filas || []).length > 0 && (
                <Tarjeta titulo="Y cómo te has sentido" testid="quincenal-sensaciones-datos">
                    <div className="-my-1">
                        {ficha.sensaciones.filas.map((f, i) => (
                            <div key={f.clave} data-testid={`quincenal-sensacion-${f.clave}`}
                                className={`flex items-center gap-3 py-2.5 ${
                                    i ? 'border-t border-border' : ''}`}>
                                <span className="text-sm text-foreground/80 flex-1 min-w-0">{f.etiqueta}</span>
                                <MiniLinea valores={f.serie} color={colorDeLaSensacion(f.clave, f.media)} />
                                <span className="text-base font-bold text-foreground tabular-nums w-10 text-right">
                                    {f.media_label}
                                </span>
                            </div>
                        ))}
                    </div>
                </Tarjeta>
            )}

            {/* ── LOS HUECOS · lo único que se le pregunta ── */}
            {(ficha?.huecos || []).map((h) => (
                <Tarjeta key={h.tipo} testid={`quincenal-hueco-${h.tipo}`}>
                    <p className="text-sm text-foreground">{h.pregunta}</p>
                    <DosBotones testid={`quincenal-hueco-${h.tipo}-op`}
                        opciones={h.opciones}
                        valor={huecosRespuestas?.[h.tipo] || ''}
                        onChange={(v) => onHueco(h.tipo, v)} />
                </Tarjeta>
            ))}

            {/* ── MODIFICAR Y CONFIRMAR ──
                «Si algo no cuadra o te falta, lo modificas al final»: Modificar abre el
                peso para corregir el que ha salido de la media. Los dos botones salen
                siempre, como en la maqueta; lo que aparece y desaparece es el campo. */}
            {modificando && (
                <div className="rounded-2xl bg-card border border-border p-4 space-y-2"
                    data-testid="quincenal-paso1-modificando">
                    <p className="text-sm text-foreground">Tu peso de esta semana</p>
                    <div className="flex items-center gap-2">
                        <input type="number" step="0.1" min="25" max="300" inputMode="decimal"
                            value={valores.weight} onChange={(e) => set('weight', e.target.value)}
                            placeholder="—" data-testid="weight-input"
                            className="flex-1 min-w-0 bg-muted border border-input rounded-xl px-3 py-3 text-foreground text-2xl font-bold placeholder-foreground/20 focus:outline-none focus:border-[#FF671F] transition-colors" />
                        <span className="text-lg text-foreground/40 font-bold">kg</span>
                    </div>
                </div>
            )}
            <div className="flex gap-2">
                <button type="button" onClick={() => setModificando((m) => !m)}
                    data-testid="quincenal-paso1-modificar"
                    className="rounded-xl px-4 py-3 text-sm font-bold border border-border bg-card text-foreground/70 hover:border-foreground/30 transition-colors">
                    {modificando ? 'Ya está' : 'Modificar'}
                </button>
                <button type="button" onClick={onConfirmar} data-testid="quincenal-paso1-confirmar"
                    className="flex-1 rounded-xl py-3 text-sm font-bold text-white uppercase tracking-wider"
                    style={{ backgroundColor: ORANGE }}>
                    Confirmar
                </button>
            </div>
        </div>
    );
};

export default QuincenalPaso1;
