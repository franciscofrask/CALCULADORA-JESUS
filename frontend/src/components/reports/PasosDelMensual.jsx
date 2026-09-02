/**
 * LA CABECERA DE LOS PASOS: «SON 4 PASOS» / «SON 3 PASOS», con el suyo marcado.
 *
 * Del documento «El reporte mensual» (1-09-2026): «Con Son 4 pasos en la cabecera de las
 * cuatro, y el suyo marcado». Va en las cuatro pantallas y siempre con la lista entera,
 * no solo con el paso actual: lo que hace es decirle cuánto le queda, y para eso tiene
 * que ver los cuatro.
 *
 * Y LO MISMO EN EL QUINCENAL, con tres («Todo lo validado antes del 1 de septiembre», «Las
 * tres pantallas»: «Con Son 3 pasos arriba en las tres, y el suyo marcado»). Es la misma
 * pieza y no una copia: el día que cambie cómo se marca el paso, cambia en los dos.
 *
 * Los títulos son los de los documentos, palabra por palabra. No son etiquetas de
 * navegación («Datos», «Fotos»): están escritos contando lo que pasa después («Darte
 * feedback directo y ajustes si procede»), que es el motivo de que el último paso exista.
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

// El quincenal, con sus tres. El primero va en singular («que está bien») y el del mensual
// en plural: son las palabras de cada documento y no se unifican.
export const PASOS_DEL_QUINCENAL = [
    'Actualizar tus datos y confirmar que está bien',
    'Escuchar tus sensaciones y dudas',
    'Darte feedback directo y ajustes si procede',
];

export const ROTULOS_DEL_QUINCENAL = [
    'Actualizar tus datos',
    'Tus sensaciones y tus dudas',
    'Tu feedback y tus ajustes',
];

/**
 * La cabecera entera: la semana, el nombre del reporte y la lista de pasos.
 *
 * `paso` es 1..N. `plazo` trae la semana del ciclo y hasta cuándo tiene, ya redactado
 * («hasta mañana jueves a las ocho»).
 */
export const CabeceraDePasos = ({ paso, plazo, pasos = PASOS_DEL_MENSUAL,
                                  titulo = 'Reporte mensual' }) => (
    <div data-testid="mensual-cabecera">
        {(plazo?.semana != null || plazo?.cierre) && (
            <p className="text-[11px] font-bold uppercase tracking-wider" style={{ color: ORANGE }}>
                {plazo?.semana != null && `Semana ${plazo.semana}`}
                {plazo?.semana != null && plazo?.cierre && ' · '}
                {plazo?.cierre}
            </p>
        )}
        <h2 className="text-2xl font-bold text-foreground uppercase"
            style={{ fontFamily: 'Barlow Condensed', letterSpacing: '0.02em' }}>
            {titulo}
        </h2>

        <div className="mt-3 rounded-2xl bg-muted p-3.5" data-testid={`mensual-son-${pasos.length}-pasos`}>
            <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground mb-2">
                Son {pasos.length} pasos
            </p>
            <ol className="space-y-1.5">
                {pasos.map((texto, i) => {
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
export const RotuloDelPaso = ({ paso, sub, rotulos = ROTULOS }) => (
    <div data-testid={`mensual-rotulo-${paso}`}>
        <p className="flex items-center gap-2">
            <span className="shrink-0 w-5 h-5 rounded-full grid place-items-center text-[11px] font-bold tabular-nums text-white"
                style={{ backgroundColor: ORANGE }}>
                {paso}
            </span>
            <span className="text-[13px] font-bold uppercase tracking-wider text-foreground">
                {rotulos[paso - 1]}
            </span>
        </p>
        {sub && <p className="text-[15px] text-muted-foreground mt-1.5">{sub}</p>}
    </div>
);

/** El del mensual, que es el que ya existía: la cabecera con sus cuatro. */
export const CabeceraDelMensual = ({ paso, plazo }) => (
    <CabeceraDePasos paso={paso} plazo={plazo} pasos={PASOS_DEL_MENSUAL}
        titulo="Reporte mensual" />
);

export default CabeceraDelMensual;
