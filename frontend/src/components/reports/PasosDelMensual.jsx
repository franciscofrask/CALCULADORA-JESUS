/**
 * LA CABECERA DEL MENSUAL: «SON 4 PASOS», con el suyo marcado.
 *
 * Del documento «El reporte mensual» (1-09-2026): «Con Son 4 pasos en la cabecera de las
 * cuatro, y el suyo marcado». Va en las cuatro pantallas y siempre con la lista entera,
 * no solo con el paso actual: lo que hace es decirle cuánto le queda, y para eso tiene
 * que ver los cuatro.
 *
 * Los títulos son los del documento, palabra por palabra. No son etiquetas de navegación
 * («Datos», «Fotos»): están escritos en primera persona y contando lo que pasa después
 * («Entregarte el plan nuevo con el informe y darte feedback»), que es el motivo de que
 * el cuarto paso exista.
 */
import React from 'react';

const ORANGE = '#FF671F';

export const PASOS_DEL_MENSUAL = [
    'Actualizar tus datos y confirmar que están bien',
    'Escuchar tus sensaciones y dudas',
    'Tus fotos y tus medidas',
    'Entregarte el plan nuevo con el informe y darte feedback',
];

/** El título corto de cada paso, el que va sobre el contenido: «1 ACTUALIZAR TUS DATOS». */
export const ROTULOS = [
    'Actualizar tus datos',
    'Tus sensaciones y tus dudas',
    'Tus fotos y tus medidas',
    'Tu plan nuevo y mi feedback directo',
];

/**
 * La cabecera entera: la semana, el nombre del reporte y la lista de los cuatro pasos.
 *
 * `paso` es 1..4. `plazo` trae la semana del ciclo y hasta cuándo tiene.
 */
export const CabeceraDelMensual = ({ paso, plazo }) => (
    <div data-testid="mensual-cabecera">
        {(plazo?.semana != null || plazo?.cierre) && (
            <p className="text-[11px] font-bold uppercase tracking-wider" style={{ color: ORANGE }}>
                {plazo?.semana != null && `Semana ${plazo.semana}`}
                {plazo?.semana != null && plazo?.cierre && ' · '}
                {plazo?.cierre && `Hasta el ${plazo.cierre}`}
            </p>
        )}
        <h2 className="text-2xl font-bold text-foreground uppercase"
            style={{ fontFamily: 'Barlow Condensed', letterSpacing: '0.02em' }}>
            Reporte mensual
        </h2>

        <div className="mt-3 rounded-2xl bg-muted p-3.5" data-testid="mensual-son-4-pasos">
            <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground mb-2">
                Son 4 pasos
            </p>
            <ol className="space-y-1.5">
                {PASOS_DEL_MENSUAL.map((texto, i) => {
                    const n = i + 1;
                    const suyo = n === paso;
                    return (
                        <li key={n} className="flex gap-2 items-start" data-testid={`mensual-paso-${n}`}>
                            <span
                                className={`shrink-0 w-5 h-5 rounded-full grid place-items-center text-[11px] font-bold tabular-nums ${
                                    suyo ? 'text-white' : 'bg-foreground/10 text-muted-foreground'}`}
                                style={suyo ? { backgroundColor: ORANGE } : undefined}>
                                {n}
                            </span>
                            <span className={`text-[13px] leading-5 ${
                                suyo ? 'font-bold text-foreground' : 'text-muted-foreground'}`}>
                                {texto}
                            </span>
                        </li>
                    );
                })}
            </ol>
        </div>
    </div>
);

/** «1 ACTUALIZAR TUS DATOS», con el número en su círculo, encima del contenido del paso. */
export const RotuloDelPaso = ({ paso, sub }) => (
    <div data-testid={`mensual-rotulo-${paso}`}>
        <p className="flex items-center gap-2">
            <span className="shrink-0 w-5 h-5 rounded-full grid place-items-center text-[11px] font-bold tabular-nums text-white"
                style={{ backgroundColor: ORANGE }}>
                {paso}
            </span>
            <span className="text-[13px] font-bold uppercase tracking-wider text-foreground">
                {ROTULOS[paso - 1]}
            </span>
        </p>
        {sub && <p className="text-[15px] text-muted-foreground mt-1.5">{sub}</p>}
    </div>
);

export default CabeceraDelMensual;
