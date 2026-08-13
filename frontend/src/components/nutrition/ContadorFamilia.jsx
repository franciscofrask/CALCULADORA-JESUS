/**
 * ContadorFamilia - lo que llevas hoy de una familia que se calibra.
 *
 * Jesús, 13-08-2026: «un contador en la línea del alimento desde el primer gramo --
 * "frutos secos hoy: 15 de 20 g"». La calibración progresiva es la regla más difícil de
 * adivinar de toda la app: la proteína de unas almendras no cuenta hasta que el DÍA pasa
 * de 20 g, y hasta ahora eso ocurría sin que nada lo dijera. El cliente veía dos líneas
 * iguales con números distintos y no tenía forma de saber por qué.
 *
 * Se enseña desde el primer gramo, no al cruzar: el aviso de cruce es otra cosa (lo lanza
 * NutritionPage una sola vez). Aquí solo se dice dónde va.
 *
 * Los gramos son del DÍA entero, que es lo que decide el tramo desde el 13-08. Por eso el
 * mismo alimento enseña el mismo contador esté en la comida que esté.
 */
import React from 'react';

// Los tramos de la spec (17-07-2026), los mismos que aplica `calibracion_dia.py`.
const FAMILIAS = {
    fruto_seco: { etiqueta: 'frutos secos', tramos: [20, 40] },
    cereal_pan: { etiqueta: 'cereales y pan', tramos: [50, 100] },
};

export const ContadorFamilia = ({ bloque, gramos }) => {
    const cfg = FAMILIAS[bloque];
    if (!cfg || gramos == null) return null;

    const [primero, segundo] = cfg.tramos;
    const g = Math.round(gramos);
    // Contra qué tramo se mide: mientras no llegues al primero, ese; luego el segundo; y
    // cuando ya cuenta entera no hay meta que enseñar, solo el total.
    const meta = g <= primero ? primero : g <= segundo ? segundo : null;
    const pct = meta ? Math.min(100, Math.round((g / meta) * 100)) : 100;
    const cuenta = g > segundo ? 'te cuenta entera'
        : g > primero ? 'te cuenta a la mitad'
        : 'todavía no te cuenta';

    return (
        <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-foreground"
             data-testid={`contador-${bloque}`}>
            <span className="inline-block w-10 h-1 rounded-full bg-muted overflow-hidden shrink-0">
                <span className="block h-full rounded-full bg-brand/70" style={{ width: `${pct}%` }} />
            </span>
            <span className="truncate">
                {cfg.etiqueta} hoy: <b className="text-foreground">{g}</b>
                {meta ? ` de ${meta} g` : ' g'} · su proteína {cuenta}
            </span>
        </div>
    );
};

export default ContadorFamilia;
