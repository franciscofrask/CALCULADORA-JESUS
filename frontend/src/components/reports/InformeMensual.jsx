/**
 * InformeMensual - Lo que el cliente recibe después de su reporte.
 *
 * Especificación 31-07-2026, parte 6. Ocho apartados, en este orden: dónde está en su
 * ciclo, el peso con el ritmo en porcentaje, el porcentaje de grasa, tres o cuatro
 * fotos, el cumplimiento en verde y rojo, los macros que le tocaban al lado de los que
 * comió, sus macros nuevos con la explicación, y cómo va respecto a gente de su perfil.
 *
 * Dos cosas que se respetan aquí y no son de estilo:
 *   - Sin fotos no hay informe. En vez de enseñar uno a medias se le pide la foto.
 *   - El ritmo se enseña SIEMPRE contra el que le toca a él, que sale de su perfil.
 *     Un -0,4 % semanal es ir bien o ir lento según quién lo firme.
 */
import React from 'react';
import { Camera, TrendingDown, TrendingUp, Minus, Check, AlertCircle, Lock, Users } from 'lucide-react';

const COLOR = {
    verde: 'text-emerald-500',
    ambar: 'text-amber-500',
    rojo: 'text-red-500',
    sin_dato: 'text-muted-foreground',
};
const FONDO = {
    verde: 'bg-emerald-500',
    ambar: 'bg-amber-500',
    rojo: 'bg-red-500',
    sin_dato: 'bg-muted-foreground/30',
};

const pct = (x) => (x == null ? '—' : `${x > 0 ? '+' : ''}${x}%`);

const Apartado = ({ titulo, children, className = '' }) => (
    <section className={`bg-card border border-border rounded-2xl p-4 ${className}`}>
        <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-3">{titulo}</p>
        {children}
    </section>
);

/** El peso: el número grande es el porcentaje, no los kilos. */
const Peso = ({ peso }) => {
    if (!peso?.disponible) {
        return <p className="text-sm text-muted-foreground">{peso?.motivo || 'Nos falta tu peso para comparar.'}</p>;
    }
    const { veredicto, semanal_pct, cambio_pct, cambio_kg, objetivo } = peso;
    const Icono = objetivo.sentido === 'subir' ? TrendingUp : objetivo.sentido === 'bajar' ? TrendingDown : Minus;
    const color = veredicto === 'en_rango' ? 'verde' : veredicto === 'lento' ? 'ambar' : 'rojo';
    const dice = {
        en_rango: 'Al ritmo que te toca',
        lento: 'Más lento de lo que te tocaría',
        rapido: 'Más rápido de lo que conviene',
    }[veredicto] || '';

    return (
        <>
            <div className="flex items-baseline gap-2">
                <Icono className={`w-5 h-5 ${COLOR[color]}`} />
                <span className="font-data text-3xl font-bold text-foreground">{pct(cambio_pct)}</span>
                <span className="text-sm text-muted-foreground">
                    en {peso.semanas} semanas ({cambio_kg > 0 ? '+' : ''}{cambio_kg} kg)
                </span>
            </div>
            <p className={`text-sm font-semibold mt-1 ${COLOR[color]}`}>{dice}</p>
            <p className="text-xs text-muted-foreground mt-2">
                Vas a <span className="font-data text-foreground">{pct(semanal_pct)}</span> por semana.
                A ti te toca entre <span className="font-data">{objetivo.min}%</span> y{' '}
                <span className="font-data">{objetivo.max}%</span>, por tu objetivo y tu punto de partida.
            </p>
        </>
    );
};

/** Cumplimiento: sale de lo registrado, no de lo que él crea que ha cumplido. */
const Barra = ({ etiqueta, dato, sufijo }) => (
    <div>
        <div className="flex items-baseline justify-between mb-1">
            <span className="text-xs text-muted-foreground">{etiqueta}</span>
            <span className={`font-data text-sm font-bold ${COLOR[dato.color]}`}>
                {dato.pct == null ? '—' : `${dato.pct}%`}
            </span>
        </div>
        <div className="h-1.5 rounded-full bg-muted overflow-hidden">
            <div className={`h-full rounded-full ${FONDO[dato.color]}`} style={{ width: `${dato.pct || 0}%` }} />
        </div>
        <p className="text-[11px] text-muted-foreground mt-1">{dato.dias} {sufijo}</p>
    </div>
);

export const InformeMensual = ({ informe, onPedirFotos }) => {
    if (!informe) return null;

    // Sin fotos no se genera: se le dice por qué y se le ofrece arreglarlo.
    if (!informe.generado) {
        return (
            <div className="bg-card border border-border rounded-2xl p-6 text-center" data-testid="informe-sin-fotos">
                <Camera className="w-10 h-10 text-muted-foreground/40 mx-auto mb-3" />
                <p className="font-bold text-foreground mb-1">Tu informe está a una foto</p>
                <p className="text-sm text-muted-foreground max-w-sm mx-auto">{informe.mensaje}</p>
                {onPedirFotos && (
                    <button onClick={onPedirFotos} data-testid="informe-subir-fotos"
                        className="mt-4 px-4 py-2.5 rounded-xl bg-brand text-white text-sm font-bold">
                        Subir mis fotos
                    </button>
                )}
            </div>
        );
    }

    const { ciclo, peso, grasa, fotos, cumplimiento, macros, explicacion, referencia } = informe;
    const todasLasFotos = [...(fotos.dia_cero || []), ...(fotos.ahora || [])];

    return (
        <div className="space-y-3" data-testid="informe-mensual">
            <Apartado titulo="Dónde estás">
                <p className="font-heading text-2xl font-bold text-foreground uppercase">
                    Semana {ciclo.semana}
                    {ciclo.semanas_totales ? <span className="text-muted-foreground"> de {ciclo.semanas_totales}</span> : null}
                </p>
            </Apartado>

            <Apartado titulo="Tu peso">
                <Peso peso={peso} />
            </Apartado>

            {(grasa?.actual != null) && (
                <Apartado titulo="Porcentaje de grasa">
                    <div className="flex items-baseline gap-2">
                        <span className="font-data text-3xl font-bold text-foreground">{grasa.actual}%</span>
                        {grasa.anterior != null && (
                            <span className="text-sm text-muted-foreground">
                                venías del {grasa.anterior}%
                            </span>
                        )}
                    </div>
                </Apartado>
            )}

            {todasLasFotos.length > 0 && (
                <Apartado titulo={fotos.dia_cero?.length ? 'Tú, al empezar y ahora' : 'Tus fotos'}>
                    <div className="grid grid-cols-3 gap-2">
                        {todasLasFotos.slice(0, 6).map((src, i) => (
                            <div key={i} className="relative aspect-[3/4] rounded-xl overflow-hidden bg-muted">
                                <img src={src} alt="" className="w-full h-full object-cover" />
                                <span className="absolute bottom-1 left-1 text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-black/60 text-white">
                                    {i < (fotos.dia_cero?.length || 0) ? 'día 1' : 'hoy'}
                                </span>
                            </div>
                        ))}
                    </div>
                </Apartado>
            )}

            <Apartado titulo="Lo que has cumplido">
                <div className="grid grid-cols-2 gap-4">
                    <Barra etiqueta="Dieta registrada" dato={cumplimiento.dieta}
                        sufijo={`de ${cumplimiento.dias_periodo} días`} />
                    <Barra etiqueta="Entrenamientos" dato={cumplimiento.entreno}
                        sufijo={cumplimiento.entreno.previstos ? `de ${cumplimiento.entreno.previstos}` : 'registrados'} />
                </div>
                {cumplimiento.huecos_dieta > 0 && (
                    <p className="text-[11px] text-muted-foreground mt-3">
                        Hay {cumplimiento.huecos_dieta} días sin registrar. Si los hiciste y no los apuntaste, dínoslo:
                        cambia el ajuste.
                    </p>
                )}
            </Apartado>

            <Apartado titulo="Lo que te tocaba y lo que comiste">
                <div className="space-y-2">
                    {macros.filas.map((f) => (
                        <div key={f.macro} className="flex items-center gap-3">
                            <span className="text-xs text-muted-foreground w-20 flex-shrink-0">{f.macro}</span>
                            <span className="font-data text-sm text-foreground flex-1">
                                {f.comido} <span className="text-muted-foreground">/ {f.objetivo} g</span>
                            </span>
                            <span className={`font-data text-xs font-bold ${COLOR[f.color]}`}>
                                {f.desvio_pct == null ? '—' : pct(f.desvio_pct)}
                            </span>
                            {f.color === 'verde'
                                ? <Check className="w-4 h-4 text-emerald-500" />
                                : <AlertCircle className={`w-4 h-4 ${COLOR[f.color]}`} />}
                        </div>
                    ))}
                </div>
            </Apartado>

            <Apartado titulo="Tus macros de este mes" className="border-brand/30">
                {explicacion.pendiente ? (
                    <p className="text-sm text-muted-foreground">
                        Tu entrenador está revisando tu mes. En cuanto lo tenga, te lo contamos aquí.
                    </p>
                ) : (
                    <p className="text-sm text-foreground/80 leading-relaxed">{explicacion.texto}</p>
                )}
                {informe.macros_nuevos?.training && (
                    <div className="mt-3 pt-3 border-t border-border flex gap-4 font-data text-sm">
                        <span className="text-foreground">{informe.macros_nuevos.training.protein} <span className="text-muted-foreground text-xs">P</span></span>
                        <span className="text-foreground">{informe.macros_nuevos.training.carbs} <span className="text-muted-foreground text-xs">H</span></span>
                        <span className="text-foreground">{informe.macros_nuevos.training.fat} <span className="text-muted-foreground text-xs">G</span></span>
                        <span className="text-[11px] text-muted-foreground self-center">día de entreno</span>
                    </div>
                )}
            </Apartado>

            {/* Octavo apartado: cómo va respecto a gente de su perfil. */}
            {referencia?.disponible ? (
                <Apartado icono={Users} titulo="Cómo vas respecto a gente como tú">
                    <p className="text-sm text-foreground/80 leading-relaxed">{referencia.texto}</p>
                    <div className="flex items-baseline gap-2 mt-3">
                        <span className="font-heading text-3xl font-bold text-brand tabular-nums">
                            {referencia.percentil}%
                        </span>
                        <span className="text-xs text-muted-foreground">
                            de las {referencia.cohorte} personas con tu perfil van más lento que tú
                        </span>
                    </div>
                    {/* El objetivo de ritmo sale de SU perfil, no de la media: que no se
                        lea como un ranking donde lo importante es adelantar a alguien. */}
                    <p className="text-[11px] text-muted-foreground mt-3">{referencia.nota}</p>
                </Apartado>
            ) : (
                <div className="flex items-center gap-2 px-4 py-3 rounded-2xl border border-dashed border-border">
                    <Lock className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                    <p className="text-[11px] text-muted-foreground">
                        {referencia?.motivo || 'Cómo vas respecto a gente con tu mismo punto de partida: llegará pronto.'}
                    </p>
                </div>
            )}
        </div>
    );
};

export default InformeMensual;
