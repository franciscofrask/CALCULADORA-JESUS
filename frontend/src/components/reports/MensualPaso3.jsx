/**
 * PASO 3 DEL MENSUAL · TUS FOTOS Y TUS MEDIDAS
 *
 * Documento «El reporte mensual» (1-09-2026): «Lo último, y es lo que más me dice a mí».
 *
 * Es el mismo contenido que ya estaba dentro del reporte -- las tres fotos y las diez
 * medidas con la del mes pasado al lado --, sacado a su propio paso. Lo que añade el
 * documento son tres cosas escritas:
 *
 *   - las fotos «relajado, siempre en el mismo sitio y con la misma luz que las
 *     anteriores», con el motivo detrás: «es lo único que me deja comparar»,
 *   - el plazo, en su aviso, y no como una línea más de la cabecera,
 *   - y adónde van a parar: «Las fotos y las medidas van a Mi evolución, con las de los
 *     meses anteriores. Ahí es donde las vas a ver comparadas».
 *
 * Esa última frase importa más de lo que parece: es la respuesta a «¿y esto para qué me lo
 * pides?», que es la pregunta que hace que un mes no se manden.
 */
import React from 'react';
import TresFotos from './TresFotos';
import { MEDIDAS, VIDEO_MEDIDAS, valorAnterior, diferencia } from '../../lib/medidas';

const ORANGE = '#FF671F';

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

const MensualPaso3 = ({ api, token, valores, set, prev, plazo }) => {
    const medidaSet = (key, v) => set('measurements', { ...valores.measurements, [key]: v });

    return (
        <div className="space-y-4" data-testid="mensual-paso3">
            {/* ── TUS FOTOS ── */}
            <Tarjeta titulo="Tus fotos" testid="mensual-fotos">
                <TresFotos api={api} token={token} esMensual />
                <p className="text-base text-foreground/80 leading-snug">
                    Relajado, <b className="text-foreground">siempre en el mismo sitio y con la misma
                    luz que las anteriores</b>. Es lo único que me deja comparar.
                </p>
            </Tarjeta>

            {/* ── EL PLAZO ── En su propio aviso: es una fecha límite, no un subtítulo. ── */}
            {plazo?.cierre && (
                <div className="rounded-2xl border p-3.5" data-testid="paso3-plazo"
                    style={{ borderColor: `${ORANGE}55`, backgroundColor: `${ORANGE}0D` }}>
                    <p className="text-sm text-foreground/80">
                        Recuerda que tienes como fecha límite <b className="text-foreground">
                        el {plazo.cierre}</b>{plazo.queda ? ` · ${plazo.queda}` : ''}.
                    </p>
                </div>
            )}

            {/* ── TUS MEDIDAS ── */}
            <Tarjeta titulo="Tus medidas" testid="medidas">
                <p className="text-base text-foreground/80 leading-snug">
                    Con el metro pegado y sin apretar.{' '}
                    {/* El vídeo delante: lo que hace que el error de medir se repita igual
                        cada mes, que es lo que permite comparar. */}
                    <b className="text-foreground">Aquí tienes el vídeo</b> de cómo se toman.
                </p>
                <details className="rounded-xl overflow-hidden border border-border">
                    <summary className="cursor-pointer select-none px-3 py-2 text-[13px] font-bold uppercase tracking-wider text-foreground/70">
                        Cómo medir los perímetros
                    </summary>
                    <div className="bg-black" style={{ aspectRatio: '16 / 9' }}>
                        <iframe src={VIDEO_MEDIDAS} title="Cómo medir los perímetros"
                            allow="fullscreen; picture-in-picture" data-testid="video-medidas"
                            className="w-full h-full border-0" />
                    </div>
                </details>
                <p className="text-[13px] text-muted-foreground">
                    Las diez, en centímetros. Si te puede medir alguien, y siempre el mismo, mejor.
                </p>

                <div className="space-y-2">
                    {MEDIDAS.map(({ key, label }) => {
                        const antes = valorAnterior(prev?.measurements, key);
                        const dif = diferencia(valores.measurements[key], antes);
                        return (
                            <div key={key} className="grid grid-cols-[1fr_5rem_4.5rem] gap-2 items-center">
                                <label className="text-sm text-foreground/80 leading-tight">
                                    {label}
                                    {/* «el mes pasado 127», debajo del nombre y en pequeño: es la
                                        referencia con la que se mide, no un valor que rellenar. */}
                                    {antes != null && (
                                        <span className="block text-[11px] text-muted-foreground">
                                            el mes pasado {String(antes).replace('.', ',')}
                                        </span>
                                    )}
                                </label>
                                <input
                                    type="number" step="0.1" inputMode="decimal"
                                    value={valores.measurements[key] ?? ''}
                                    onChange={(e) => medidaSet(key, e.target.value)}
                                    placeholder="—" data-testid={`medida-${key}`}
                                    className="h-10 px-2 rounded-lg bg-muted text-center text-base font-bold outline-none focus:ring-2 focus:ring-brand"
                                />
                                <span className="text-[11px] text-right tabular-nums">
                                    {dif ? (
                                        <span className={dif.signo === 0 ? 'text-foreground/40'
                                            : dif.signo > 0 ? 'text-blue-500' : 'text-emerald-500'}>
                                            {dif.texto}
                                        </span>
                                    ) : (
                                        <span className="text-foreground/30">cm</span>
                                    )}
                                </span>
                            </div>
                        );
                    })}
                </div>
            </Tarjeta>

            {/* ── ADÓNDE VAN A PARAR ── */}
            <div className="rounded-2xl bg-muted p-3.5" data-testid="paso3-mi-evolucion">
                <p className="text-sm text-foreground/80">
                    Las fotos y las medidas van a <b className="text-foreground">Mi evolución</b>, con
                    las de los meses anteriores. Ahí es donde las vas a ver comparadas.
                </p>
            </div>
        </div>
    );
};

export default MensualPaso3;
